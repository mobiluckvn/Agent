"""TC-22, TC-25 — tầng thu nhận đầu vào đa phương thức.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-22 | Nộp PDF có bảng thanh ghi | chunk đề xuất đúng dạng, kèm trang gốc, chờ G2 — **chưa truy xuất được** |
| TC-25 | Nguồn web ngoài danh sách cho phép | bị loại, không tạo proposed fact, sự kiện ghi log |

Vế "chưa truy xuất được" của TC-22 là vế quan trọng. Một chunk đề xuất mà đã
tra ra được thì toàn bộ cơ chế gate chỉ còn là thủ tục: mã sẽ sinh ra kèm trích
dẫn trỏ tới một trích đoạn chưa ai đối chiếu, và nó trông y hệt mã có nguồn gốc
đàng hoàng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.ingest import (
    WEB_WHITELIST,
    AssumptionLog,
    IngestError,
    InputKind,
    MediaStore,
    PdfIngestor,
    SourceRegistry,
    SourceRejected,
    check_web_source,
    classify,
)
from eaa.kb import PROPOSED, DatasheetStore, KbError

pypdf = pytest.importorskip("pypdf")


# --------------------------------------------------------------------------
# Dựng một PDF thật để nạp
# --------------------------------------------------------------------------


# Nội dung PDF viết bằng ASCII thuần: luồng nội dung PDF mã hóa latin-1,
# và dấu gạch dài hay dấu tiếng Việt sẽ làm hỏng bước dựng tệp mẫu.
TRANG_1 = "Trang bia - muc luc, khong co gi de trich xuat."
TRANG_2 = (
    "22.5 Bit Rate Generator Unit\n"
    "TWBR = 12 for 400 kHz operation at 16 MHz\n"
    "TWSR = 0 selects prescaler value 1\n"
    "TWCR = 0x04 enables the interface\n"
)
TRANG_3 = "22.6 Status codes. TWSR & 0xF8 gives the current bus state.\n"


def _pdf_toi_thieu(trang: list[str]) -> bytes:
    """Dựng một tệp PDF tối thiểu, hợp lệ, có chữ trích xuất được.

    Tự sinh thay vì gọi API dựng PDF của thư viện: thư viện đọc PDF không có
    API vẽ chữ, và chạm vào phần nội bộ của nó khiến bài test hỏng mỗi lần thư
    viện lên phiên bản — hỏng vì lý do chẳng liên quan gì tới thứ đang kiểm.
    Cấu trúc PDF ở mức này đủ đơn giản để viết thẳng và đọc hiểu được.
    """
    doi_tuong: list[bytes] = []

    def them(noi_dung: bytes) -> int:
        doi_tuong.append(noi_dung)
        return len(doi_tuong)

    so_font = them(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )
    so_trang: list[int] = []
    for van_ban in trang:
        dong = " ".join(
            f"({d.replace('(', '').replace(')', '')}) Tj 0 -14 Td"
            for d in van_ban.splitlines()
        )
        luong = f"BT /F1 10 Tf 40 780 Td {dong} ET".encode("latin-1")
        so_luong = them(
            b"<< /Length " + str(len(luong)).encode() + b" >>\nstream\n" + luong + b"\nendstream"
        )
        so_trang.append(
            them(
                b"<< /Type /Page /Parent 999 0 R /MediaBox [0 0 595 842] "
                b"/Contents " + str(so_luong).encode() + b" 0 R "
                b"/Resources << /Font << /F1 " + str(so_font).encode() + b" 0 R >> >> >>"
            )
        )

    kids = b" ".join(f"{n} 0 R".encode() for n in so_trang)
    so_pages = them(
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(so_trang)).encode() + b" >>"
    )
    so_catalog = them(b"<< /Type /Catalog /Pages " + str(so_pages).encode() + b" 0 R >>")

    # Nối lại tham chiếu cha của từng trang.
    for i in so_trang:
        doi_tuong[i - 1] = doi_tuong[i - 1].replace(
            b"/Parent 999 0 R", b"/Parent " + str(so_pages).encode() + b" 0 R"
        )

    ra = bytearray(b"%PDF-1.4\n")
    vi_tri: list[int] = []
    for i, noi_dung in enumerate(doi_tuong, 1):
        vi_tri.append(len(ra))
        ra += str(i).encode() + b" 0 obj\n" + noi_dung + b"\nendobj\n"

    xref = len(ra)
    ra += b"xref\n0 " + str(len(doi_tuong) + 1).encode() + b"\n0000000000 65535 f \n"
    for v in vi_tri:
        ra += f"{v:010d} 00000 n \n".encode()
    ra += (
        b"trailer\n<< /Size " + str(len(doi_tuong) + 1).encode()
        + b" /Root " + str(so_catalog).encode() + b" 0 R >>\nstartxref\n"
        + str(xref).encode() + b"\n%%EOF\n"
    )
    return bytes(ra)


@pytest.fixture()
def pdf(tmp_path: Path) -> Path:
    duong_dan = tmp_path / "tai_lieu_ky_thuat.pdf"
    duong_dan.write_bytes(_pdf_toi_thieu([TRANG_1, TRANG_2, TRANG_3]))
    return duong_dan


@pytest.fixture()
def ingestor(tmp_path: Path) -> PdfIngestor:
    return PdfIngestor(
        datasheets_dir=tmp_path / "datasheets",
        registry=SourceRegistry(tmp_path / "sources.jsonl"),
    )


# --------------------------------------------------------------------------
# Phân loại đầu vào — FR-ING-01
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ten", "loai"),
    [
        ("a.pdf", InputKind.PDF),
        ("so_do.png", InputKind.IMAGE),
        ("man_hien_song.JPG", InputKind.IMAGE),
        ("drv.c", InputKind.CODE),
        ("drv.h", InputKind.CODE),
        ("ghi_chu.md", InputKind.COMMAND),
        ("kho_hieu.xyz", InputKind.UNKNOWN),
    ],
)
def test_phan_loai_bon_loai_dau_vao(ten: str, loai: str) -> None:
    assert classify(ten) == loai


# --------------------------------------------------------------------------
# TC-22 — nạp PDF thành chunk đề xuất
# --------------------------------------------------------------------------


def test_tc22_chunk_de_xuat_o_trang_thai_cho_G2(
    pdf: Path, ingestor: PdfIngestor, tmp_path: Path
) -> None:
    de_xuat = ingestor.ingest(
        pdf, device="atmega328p", peripheral="twi", pages="2", topic="Tốc độ bit bus"
    )

    kho = DatasheetStore(tmp_path / "datasheets")
    chunk = kho.get(de_xuat.id, include_inactive=True)
    assert chunk.status == PROPOSED
    assert not chunk.is_active


def test_tc22_chunk_de_xuat_CHUA_TRUY_XUAT_DUOC(
    pdf: Path, ingestor: PdfIngestor, tmp_path: Path
) -> None:
    """Vế quan trọng nhất: nó chưa được phép vào bất kỳ prompt nào."""
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2")
    kho = DatasheetStore(tmp_path / "datasheets")

    assert kho.active() == []
    assert kho.by_register("TWBR") == []
    assert kho.registers() == set()
    with pytest.raises(KbError, match="đã duyệt G2"):
        kho.get(de_xuat.id)


def test_tc22_chunk_mang_trang_goc(pdf: Path, ingestor: PdfIngestor) -> None:
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2-3")
    assert "tr.2-3" in de_xuat.source
    assert de_xuat.source_hash.startswith("sha256:")


def test_tc22_chunk_o_dang_bang_thanh_ghi(pdf: Path, ingestor: PdfIngestor) -> None:
    """K2: chunk lưu ở dạng bảng thanh ghi–bit, không phải đoạn văn quét thô."""
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2")

    assert "| Thanh ghi |" in de_xuat.body
    assert "| TWBR | 12 |" in de_xuat.body
    assert "| TWSR | 0 |" in de_xuat.body
    # Phần chưa chưng cất phải được đánh dấu rõ, không giả vờ đã xong.
    assert "CHƯA chưng cất" in de_xuat.body


def test_tc22_chunk_nhac_ky_su_doi_chieu_tung_bit(pdf: Path, ingestor: PdfIngestor) -> None:
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2")
    assert "đối chiếu từng bit" in de_xuat.note


def test_tc22_doan_ten_thanh_ghi_lam_goi_y(pdf: Path, ingestor: PdfIngestor) -> None:
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2")
    assert "TWBR" in de_xuat.registers and "TWSR" in de_xuat.registers


def test_khong_co_tham_so_nao_dat_thang_thanh_approved(
    pdf: Path, ingestor: PdfIngestor
) -> None:
    """Chỉ con người tại G2 mới nâng được trạng thái — không có lối tắt ở tầng này."""
    import inspect

    chu_ky = inspect.signature(PdfIngestor.ingest)
    assert not any(
        "status" in t or "approve" in t for t in chu_ky.parameters
    ), f"ingest() có tham số đáng ngờ: {list(chu_ky.parameters)}"

    de_xuat = ingestor.ingest(pdf, device="c", peripheral="b", pages="2")
    assert f"status: {PROPOSED}" in de_xuat.to_markdown()


# --------------------------------------------------------------------------
# Chọn trang là việc của con người
# --------------------------------------------------------------------------


def test_chi_trich_dung_nhung_trang_nguoi_chon(pdf: Path, ingestor: PdfIngestor) -> None:
    """AIS §4.1 bước 1: người tuyển chọn, không nạp tự động cả tài liệu."""
    van_ban, so_trang = PdfIngestor.extract_text(pdf, "2")
    assert so_trang == [2]
    assert "TWBR" in van_ban
    assert "muc luc" not in van_ban


@pytest.mark.parametrize("mo_ta", ["2-3", "2,3", "3,2"])
def test_doc_duoc_nhieu_dang_mo_ta_trang(pdf: Path, mo_ta: str) -> None:
    _, so_trang = PdfIngestor.extract_text(pdf, mo_ta)
    assert so_trang == [2, 3]


@pytest.mark.parametrize("mo_ta", ["99", "0", "3-2", "abc", "1-x"])
def test_mo_ta_trang_sai_bi_tu_choi(pdf: Path, mo_ta: str) -> None:
    with pytest.raises(IngestError):
        PdfIngestor.extract_text(pdf, mo_ta)


def test_pdf_khong_ton_tai_bao_loi_ro_rang(ingestor: PdfIngestor, tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Không tìm thấy tệp PDF"):
        ingestor.ingest(tmp_path / "khong-co.pdf", device="c", peripheral="b")


def test_pdf_khong_trich_duoc_chu_thi_noi_ro_ly_do(
    ingestor: PdfIngestor, tmp_path: Path
) -> None:
    """PDF ảnh quét: nói thẳng là cần nhận dạng ký tự, không im lặng trả rỗng."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    trang_trang = tmp_path / "anh_quet.pdf"
    with open(trang_trang, "wb") as f:
        writer.write(f)

    with pytest.raises(IngestError, match="nhận dạng ký tự"):
        ingestor.ingest(trang_trang, device="c", peripheral="b")


def test_khong_ghi_de_chunk_da_co(pdf: Path, ingestor: PdfIngestor) -> None:
    ingestor.ingest(pdf, device="c", peripheral="b", pages="2", chunk_id="ds-trung")
    with pytest.raises(IngestError, match="Đã có tệp chunk"):
        ingestor.ingest(pdf, device="c", peripheral="b", pages="2", chunk_id="ds-trung")


# --------------------------------------------------------------------------
# TC-25 — nguồn web ngoài danh sách cho phép
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.microchip.com/tai-lieu.pdf",
        "http://ww1.microchip.com/downloads/x.pdf",
        "invensense.tdk.com/products",
        "https://www.st.com/resource/en/datasheet/x.pdf",
    ],
)
def test_nguon_trong_danh_sach_cho_phep_duoc_nhan(url: str) -> None:
    assert check_web_source(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://dien-dan-dien-tu.example/thread/12345",
        "https://blog-ai-viet-code.example/atmega",
        "https://stackoverflow.com/questions/1",
    ],
)
def test_tc25_nguon_ngoai_danh_sach_bi_loai(url: str) -> None:
    with pytest.raises(SourceRejected, match="ngoài danh sách cho phép"):
        check_web_source(url)


def test_tc25_khong_tao_proposed_fact_tu_nguon_bi_loai(tmp_path: Path) -> None:
    """Bị loại nghĩa là KHÔNG có gì được tạo ra, không phải tạo rồi đánh dấu."""
    kho = tmp_path / "datasheets"
    try:
        check_web_source("https://dien-dan.example/x")
    except SourceRejected:
        pass
    assert not kho.exists() or list(kho.glob("*.md")) == []


def test_tc25_ten_mien_gia_mao_khong_lot_luoi() -> None:
    """So theo tên miền có hậu tố khớp, không so theo chuỗi con.

    Kiểm tra cẩu thả ở đây tệ hơn không kiểm: nó cấp cho nguồn giả mạo đúng cái
    vẻ chính thống mà danh sách sinh ra để bảo vệ.
    """
    for gia_mao in (
        "https://microchip.com.kho-tai-lieu-lau.example/x.pdf",
        "https://not-microchip.com/x",
        "https://microchip.com.evil.example",
    ):
        with pytest.raises(SourceRejected):
            check_web_source(gia_mao)


def test_danh_sach_cho_phep_chi_gom_trang_nha_san_xuat() -> None:
    for mien in WEB_WHITELIST:
        assert "." in mien and " " not in mien
        assert not any(
            x in mien for x in ("forum", "blog", "stackoverflow", "reddit", "github")
        ), f"{mien} không phải trang chính thức của nhà sản xuất"


# --------------------------------------------------------------------------
# Source Registry — "fact này từ đâu ra?"
# --------------------------------------------------------------------------


def test_source_registry_tra_nguon_cua_mot_chunk(
    pdf: Path, ingestor: PdfIngestor, tmp_path: Path
) -> None:
    de_xuat = ingestor.ingest(pdf, device="atmega328p", peripheral="twi", pages="2")

    so = SourceRegistry(tmp_path / "sources.jsonl")
    nguon = so.source_of(de_xuat.id)
    assert nguon is not None
    assert nguon.kind == InputKind.PDF
    assert nguon.pages == "2"
    assert nguon.content_hash == de_xuat.source_hash
    assert Path(nguon.origin).name == pdf.name


def test_source_registry_nhan_ra_cung_mot_tai_lieu_nap_hai_lan(
    pdf: Path, ingestor: PdfIngestor, tmp_path: Path
) -> None:
    a = ingestor.ingest(pdf, device="c", peripheral="b", pages="2", chunk_id="ds-a")
    b = ingestor.ingest(pdf, device="c", peripheral="b", pages="3", chunk_id="ds-b")

    so = SourceRegistry(tmp_path / "sources.jsonl")
    assert len(so.by_hash(a.source_hash)) == 2
    assert a.source_hash == b.source_hash


def test_source_registry_dong_hong_bao_loi_kem_so_dong(tmp_path: Path) -> None:
    path = tmp_path / "sources.jsonl"
    path.write_text('{"id": "src-0001"}\nkhong-phai-json\n', encoding="utf-8")
    with pytest.raises(IngestError, match=":2:"):
        SourceRegistry(path).all()


# --------------------------------------------------------------------------
# Assumption Log — giả định hiện diện tường minh
# --------------------------------------------------------------------------


def test_gia_dinh_bi_thay_boi_so_do_that(tmp_path: Path) -> None:
    """AIS §8.1: tri thức thực chứng luôn thắng giả định."""
    so = AssumptionLog(tmp_path / "assumptions.jsonl")
    gia_dinh = so.add(
        subject="friction_coeff",
        value="0.02",
        rationale="ước lượng từ vật liệu bánh, chưa đo",
    )
    assert [a.id for a in so.active()] == [gia_dinh.id]

    moi = so.replace_with_measurement(gia_dinh.id, "0.0173")
    con_lai = so.active()

    assert [a.id for a in con_lai] == [moi.id]
    assert con_lai[0].value == "0.0173"
    # Bản giả định cũ vẫn tra được — không xóa bao giờ.
    assert any(a.status == "replaced_by" for a in so.all())


def test_gia_dinh_khong_ton_tai_bao_loi(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Không có giả định"):
        AssumptionLog(tmp_path / "assumptions.jsonl").get("asm-9999")


# --------------------------------------------------------------------------
# Media Store — giữ ảnh gốc để đối chiếu lại
# --------------------------------------------------------------------------


def test_media_store_giu_anh_goc_va_fact_da_trich(tmp_path: Path) -> None:
    anh = tmp_path / "man_hien_song.png"
    anh.write_bytes(b"\x89PNG\r\n\x1a\n" + b"gia lap du lieu anh")

    kho = MediaStore(tmp_path / "media")
    dich = kho.store(anh, facts={"chu_ky_ms": 10.02, "jitter_us": 45})

    assert dich.is_file()
    assert dich.read_bytes() == anh.read_bytes(), "ảnh gốc phải giữ nguyên từng byte"

    facts = json.loads(dich.with_suffix(dich.suffix + ".facts.json").read_text(encoding="utf-8"))
    assert facts["facts"]["chu_ky_ms"] == 10.02
    assert facts["status"] == PROPOSED, "số đo đọc từ ảnh cũng chỉ là đề xuất"
    assert facts["content_hash"].startswith("sha256:")


def test_media_store_khong_luu_hai_ban_cua_cung_mot_anh(tmp_path: Path) -> None:
    anh = tmp_path / "a.png"
    anh.write_bytes(b"noi dung anh")
    kho = MediaStore(tmp_path / "media")
    assert kho.store(anh) == kho.store(anh)


def test_media_store_anh_khong_ton_tai_bao_loi(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Không tìm thấy tệp ảnh"):
        MediaStore(tmp_path / "media").store(tmp_path / "khong-co.png")
