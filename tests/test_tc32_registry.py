"""TC-32, TC-33 — kho phẩm xuất: gửi lại và làm mới là hai việc khác nhau.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-32 | "Gửi lại báo cáo hôm qua dạng pdf" | trả ĐÚNG bản đã phát hành (khớp băm), chuyển định dạng TỪ CHÍNH BẢN ẤY — không tái sinh |
| TC-33 | "Cho bản mới nhất" khi dữ liệu đã đổi | tái sinh thành phiên bản mới supersedes bản cũ; bản cũ vẫn tra được nguyên vẹn |

Tình huống mà sự phân biệt này ngăn được, và là lý do nó đáng có một cơ chế
riêng: người dùng xin "báo cáo chỉ số" rồi nhận về một bản vừa tái sinh, trong
khi họ tưởng đó là bản đã nộp tuần trước. Hai bản khác số liệu, và không ai
biết cho tới lúc bị hỏi trước hội đồng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.registry import (
    CURRENT,
    SUPERSEDED,
    AmbiguousRequest,
    ArtifactNotFound,
    ArtifactRegistry,
    RegistryError,
    RequestKind,
    convert,
    interpret_request,
)

BAO_CAO_HOM_QUA = (
    "ts,module,event,tdev_min,retries\n"
    "2026-08-28T09:00:00Z,drv_bus_sensor,merge,12.5,1\n"
    "2026-08-28T11:00:00Z,pid_controller,merge,8.25,0\n"
)
BAO_CAO_HOM_NAY = BAO_CAO_HOM_QUA + (
    "2026-08-29T10:00:00Z,kernel_tick,merge,6.75,2\n"
)


@pytest.fixture()
def kho(tmp_path: Path) -> ArtifactRegistry:
    return ArtifactRegistry(tmp_path / "deliverables")


@pytest.fixture()
def da_phat_hanh(kho: ArtifactRegistry):
    return kho.publish(
        family="bao_cao_kpi",
        kind="csv",
        title="Báo cáo chỉ số tuần 35",
        description="Số liệu Tdev và số vòng tự sửa cho Chương 3",
        content=BAO_CAO_HOM_QUA,
        lineage={
            "commit": "ab12cd34",
            "kpi_range": "2026-08-22..2026-08-28",
            "constraints_version": "sha256:c0nstr",
        },
    )


# --------------------------------------------------------------------------
# Phát hành và dòng dõi dữ liệu — FR-DOC-01
# --------------------------------------------------------------------------


def test_pham_xuat_dang_ky_kem_bam_phien_ban_va_dong_doi(da_phat_hanh, kho) -> None:
    assert da_phat_hanh.version == 1
    assert da_phat_hanh.status == CURRENT
    assert da_phat_hanh.content_hash.startswith("sha256:")
    assert da_phat_hanh.lineage["commit"] == "ab12cd34"
    assert da_phat_hanh.lineage["kpi_range"] == "2026-08-22..2026-08-28"
    assert (kho.root / da_phat_hanh.path).is_file()


def test_loai_pham_xuat_khong_hop_le_bi_tu_choi(kho: ArtifactRegistry) -> None:
    with pytest.raises(RegistryError, match="không hợp lệ"):
        kho.publish(family="x", kind="tu_nghi_ra", title="x", content="y")


def test_so_dang_ky_la_van_ban_doc_duoc(da_phat_hanh, kho) -> None:
    du_lieu = json.loads(kho.index_path.read_text(encoding="utf-8"))
    assert du_lieu["artifacts"][0]["id"] == da_phat_hanh.id


# --------------------------------------------------------------------------
# TC-32 — gửi lại
# --------------------------------------------------------------------------


def test_tc32_gui_lai_tra_dung_ban_da_phat_hanh(da_phat_hanh, kho) -> None:
    duong_dan = kho.resend(da_phat_hanh.id)
    assert duong_dan.read_text(encoding="utf-8") == BAO_CAO_HOM_QUA


def test_tc32_gui_lai_dang_pdf_chuyen_tu_CHINH_BAN_AY(da_phat_hanh, kho) -> None:
    """Không tái sinh từ dữ liệu mới — chuyển đổi từ bản đã phát hành."""
    # Dữ liệu đã đổi kể từ lúc phát hành.
    kho.publish(
        family="bao_cao_kpi",
        kind="csv",
        title="Báo cáo chỉ số tuần 35",
        content=BAO_CAO_HOM_NAY,
        lineage={"kpi_range": "2026-08-22..2026-08-29"},
    )

    pdf = kho.resend(da_phat_hanh.id, fmt="pdf")
    noi_dung = pdf.read_bytes()

    assert noi_dung.startswith(b"%PDF-")
    assert b"%%EOF" in noi_dung
    # Số liệu của bản CŨ, không phải bản mới.
    assert b"drv_bus_sensor" in noi_dung
    assert b"kernel_tick" not in noi_dung, "gửi lại mà lại kèm số liệu mới"


def test_tc32_gui_lai_KHONG_tao_phien_ban_moi(da_phat_hanh, kho) -> None:
    truoc = len(kho.all())
    kho.resend(da_phat_hanh.id, fmt="pdf")
    kho.resend(da_phat_hanh.id, fmt="md")
    assert len(kho.all()) == truoc, "gửi lại không được đẻ ra phiên bản mới"


def test_tc32_ban_phat_hanh_bi_sua_thi_tu_choi_gui_lai(da_phat_hanh, kho) -> None:
    """Một tệp phát hành bị sửa sau lưng thì gửi lại nó không còn là gửi lại."""
    (kho.root / da_phat_hanh.path).write_text("ai do da sua\n", encoding="utf-8")

    with pytest.raises(RegistryError, match="đã bị sửa"):
        kho.resend(da_phat_hanh.id)


def test_tc32_tep_phat_hanh_bi_xoa_thi_bao_loi(da_phat_hanh, kho) -> None:
    (kho.root / da_phat_hanh.path).unlink()
    with pytest.raises(RegistryError, match="mất tính bất biến"):
        kho.resend(da_phat_hanh.id)


def test_tc32_tim_ban_theo_mo_ta_va_ngay(da_phat_hanh, kho) -> None:
    """FR-DOC-03: truy hồi bằng mô tả tự nhiên + bộ lọc loại/thời gian."""
    tim_thay = kho.find("báo cáo chỉ số", kind="csv")
    assert [a.id for a in tim_thay] == [da_phat_hanh.id]

    assert kho.find("báo cáo", on_date=da_phat_hanh.created_at[:10])
    assert kho.find("báo cáo", on_date="1999-01-01") == []
    assert kho.find("một thứ hoàn toàn khác") == []


# --------------------------------------------------------------------------
# TC-33 — làm mới
# --------------------------------------------------------------------------


def test_tc33_lam_moi_tao_phien_ban_moi_supersedes_ban_cu(da_phat_hanh, kho) -> None:
    moi = kho.regen(
        "bao_cao_kpi",
        lambda: (BAO_CAO_HOM_NAY, {"kpi_range": "2026-08-22..2026-08-29"}),
    )

    assert moi.version == 2
    assert moi.status == CURRENT
    assert moi.supersedes == da_phat_hanh.id

    cu = kho.get(da_phat_hanh.id)
    assert cu.status == SUPERSEDED
    assert cu.superseded_by == moi.id


def test_tc33_ban_cu_van_tra_duoc_NGUYEN_VEN(da_phat_hanh, kho) -> None:
    """Điều kiện để so được hai bản khi có ai hỏi "số liệu đổi chỗ nào"."""
    bam_cu = da_phat_hanh.content_hash
    kho.regen("bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY, {}))

    duong_dan = kho.resend(da_phat_hanh.id)
    assert duong_dan.read_text(encoding="utf-8") == BAO_CAO_HOM_QUA
    assert kho.get(da_phat_hanh.id).content_hash == bam_cu


def test_tc33_lam_moi_lay_du_lieu_HIEN_HANH(da_phat_hanh, kho) -> None:
    moi = kho.regen(
        "bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY, {"kpi_range": "tới 2026-08-29"})
    )
    noi_dung = (kho.root / moi.path).read_text(encoding="utf-8")
    assert "kernel_tick" in noi_dung
    assert moi.lineage["kpi_range"] == "tới 2026-08-29"


def test_lam_moi_khi_chua_co_ban_nao(kho: ArtifactRegistry) -> None:
    moi = kho.regen("bao_cao_moi_tinh", lambda: ("noi dung", {}), kind="md", title="Mới")
    assert moi.version == 1 and moi.supersedes == ""


def test_lich_su_phien_ban_giu_du_thu_tu(da_phat_hanh, kho) -> None:
    kho.regen("bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY, {}))
    kho.regen("bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY + "x\n", {}))

    lich_su = kho.versions("bao_cao_kpi")
    assert [a.version for a in lich_su] == [1, 2, 3]
    assert [a.status for a in lich_su] == [SUPERSEDED, SUPERSEDED, CURRENT]


def test_ban_hien_hanh_luon_la_ban_moi_nhat(da_phat_hanh, kho) -> None:
    moi = kho.regen("bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY, {}))
    assert kho.current("bao_cao_kpi").id == moi.id


def test_khong_co_ban_nao_thi_bao_loi_ro_rang(kho: ArtifactRegistry) -> None:
    with pytest.raises(ArtifactNotFound):
        kho.current("khong-ton-tai")
    with pytest.raises(ArtifactNotFound):
        kho.get("khong-ton-tai@v1")


# --------------------------------------------------------------------------
# FR-DOC-02 — chưa rõ thì HỎI, không đoán
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yeu_cau",
    [
        "gửi lại báo cáo KPI hôm qua dạng pdf",
        "cho tôi bản đã nộp tuần trước",
        "bản cũ của báo cáo",
    ],
)
def test_cach_noi_nghieng_ve_gui_lai(yeu_cau: str) -> None:
    assert interpret_request(yeu_cau) == RequestKind.RESEND


@pytest.mark.parametrize(
    "yeu_cau",
    [
        "cho tôi bản KPI mới nhất",
        "làm mới báo cáo",
        "cập nhật bảng số liệu",
    ],
)
def test_cach_noi_nghieng_ve_lam_moi(yeu_cau: str) -> None:
    assert interpret_request(yeu_cau) == RequestKind.REGEN


@pytest.mark.parametrize(
    "yeu_cau",
    [
        "cho tôi báo cáo KPI",
        "gửi lại bản mới nhất",          # có dấu hiệu của CẢ HAI phía
        "xuất báo cáo",
    ],
)
def test_cach_noi_chua_ro_thi_phai_HOI_chu_khong_doan(yeu_cau: str) -> None:
    """Đoán bừa ở đây tạo sai lệch âm thầm; dừng lại hỏi chỉ tốn một câu."""
    assert interpret_request(yeu_cau) == RequestKind.AMBIGUOUS


# --------------------------------------------------------------------------
# Chuyển đổi định dạng
# --------------------------------------------------------------------------


def test_chuyen_csv_sang_bang_markdown() -> None:
    ra = convert(BAO_CAO_HOM_QUA.encode(), "csv", "md").decode()
    assert ra.splitlines()[0].startswith("| ts | module |")
    assert "| --- |" in ra.replace("|---|", "| --- |")
    assert "drv_bus_sensor" in ra


def test_chuyen_sang_html_thoat_ky_tu_dac_biet() -> None:
    ra = convert(b"a < b & c > d", "md", "html").decode()
    assert "&lt;" in ra and "&amp;" in ra and "&gt;" in ra


def test_chuyen_cung_dinh_dang_tra_nguyen_ban() -> None:
    assert convert(b"x", "md", "md") == b"x"


def test_pdf_sinh_ra_hop_le_va_phan_trang() -> None:
    van_ban = "\n".join(f"dong so {i}" for i in range(200))
    ra = convert(van_ban.encode(), "md", "pdf", title="Thu nghiem")

    assert ra.startswith(b"%PDF-") and ra.rstrip().endswith(b"%%EOF")
    assert ra.count(b"/Type /Page\n") >= 0
    assert b"/Count 4" in ra, "200 dòng phải chia thành nhiều trang"


def test_cap_chuyen_doi_chua_ho_tro_thi_bao_loi_chu_khong_tra_ban_gan_dung() -> None:
    """Một báo cáo mất bảng biểu khi chuyển vẫn mang đúng tên và đúng ngày."""
    with pytest.raises(RegistryError, match="cần công cụ ngoài"):
        convert(b"\x00\x01", "docx", "pdf")


# --------------------------------------------------------------------------
# Trình bày
# --------------------------------------------------------------------------


def test_liet_ke_hien_trang_thai_va_dong_doi(da_phat_hanh, kho) -> None:
    kho.regen("bao_cao_kpi", lambda: (BAO_CAO_HOM_NAY, {"commit": "ffee11"}))
    van_ban = kho.render_list()

    assert "bao_cao_kpi@v1" in van_ban and "bao_cao_kpi@v2" in van_ban
    assert SUPERSEDED in van_ban and CURRENT in van_ban
    assert "dòng dõi" in van_ban and "commit=ffee11" in van_ban


def test_kho_rong_khong_no(kho: ArtifactRegistry) -> None:
    assert kho.all() == []
    assert "trống" in kho.render_list()


def test_so_dang_ky_hong_bao_loi(kho: ArtifactRegistry) -> None:
    kho.root.mkdir(parents=True)
    kho.index_path.write_text("{khong phai json", encoding="utf-8")
    with pytest.raises(RegistryError, match="JSON hỏng"):
        kho.all()
