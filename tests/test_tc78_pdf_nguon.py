"""TC-78 — đọc PDF, soi kỹ kho tài liệu, và kỷ luật NÊU NGUỒN.

Ba việc, một gốc: bài kiểm hồ sơ robot BLKLab ngày 31/08/2026.

Bài 2 của lần kiểm ấy hỏng theo cách đáng nhớ. Agent được hỏi quy trình trong
**tài liệu của người dùng**; nó chạy ba lệnh đọc tài liệu **của chính công cụ
này**, rồi tóm tắt thứ đọc được như thể đó là câu trả lời. Từng câu đều đúng —
chỉ là đúng về một tài liệu khác.

Không phép kiểm nào bắt được điều đó, vì lệnh chạy hợp lệ và đầu ra hợp lệ.
Thứ bắt được là bắt Agent **nói ra nó đang trả lời từ đâu**.

Bài này không dùng tệp trong ``data/`` — thư mục ấy không nằm trong Git. Nó
dựng một PDF nhỏ ngay tại chỗ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA
from eaa.pdftext import PdfError, PdfText, extract_text


# --------------------------------------------------------------------------
# Dựng PDF thử ngay tại chỗ
# --------------------------------------------------------------------------


def _pdf(trang_noi_dung: list[bytes]) -> bytes:
    """Dựng một PDF nhiều trang, đủ chuẩn để ``pypdf`` mở được.

    Dựng tại chỗ chứ không dùng tệp trong ``data/``: thư mục ấy không nằm trong
    Git, nên một bài test dựa vào nó sẽ hỏng ở mọi máy khác.
    """
    doi_tuong: list[bytes] = []

    def them(than: bytes) -> int:
        doi_tuong.append(than)
        return len(doi_tuong)

    so_font = them(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    so_trang: list[int] = []
    for noi_dung in trang_noi_dung:
        so_nd = them(b"<< /Length %d >>\nstream\n" % len(noi_dung) + noi_dung + b"\nendstream")
        so_trang.append(them(
            b"<< /Type /Page /Parent 999 0 R /MediaBox [0 0 612 792]"
            b" /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (so_font, so_nd)
        ))
    kids = b" ".join(b"%d 0 R" % n for n in so_trang)
    so_pages = them(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(so_trang)))
    so_root = them(b"<< /Type /Catalog /Pages %d 0 R >>" % so_pages)

    ra = bytearray(b"%PDF-1.4\n")
    lech: list[int] = []
    for i, than in enumerate(doi_tuong, 1):
        lech.append(len(ra))
        ra += b"%d 0 obj\n" % i + than + b"\nendobj\n"
    bat_dau_xref = len(ra)
    ra += b"xref\n0 %d\n" % (len(doi_tuong) + 1)
    ra += b"0000000000 65535 f \n"
    for x in lech:
        ra += b"%010d 00000 n \n" % x
    ra += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
           % (len(doi_tuong) + 1, so_root, bat_dau_xref))

    # Trang cha trỏ tới 999 0 R (không tồn tại) chỉ để giữ cấu trúc; pypdf
    # không cần nó để rút chữ.
    return bytes(ra)


def _pdf_toi_thieu(noi_dung: bytes, **_kw) -> bytes:
    return _pdf([noi_dung])


def _pdf_hai_trang(mot: bytes, hai: bytes) -> bytes:
    return _pdf([mot, hai])


def _viet(tmp_path: Path, raw: bytes, ten: str = "thu.pdf") -> Path:
    p = tmp_path / ten
    p.write_bytes(raw)
    return p


# ═══════════════════════════ rút chữ từ PDF ═══════════════════════════
#
# Bộ rút bọc ``pypdf`` (đã khai trong dependencies). Bài này kiểm PHẦN MODULE
# TỰ THÊM — nhận PDF quét ảnh, gắn mức tin cậy, nói rõ giới hạn — chứ không
# kiểm lại chính pypdf.


def test_rut_duoc_chu(tmp_path):
    raw = _pdf_toi_thieu(b"BT /F1 12 Tf (Hello) Tj ET")
    kq = extract_text(_viet(tmp_path, raw))
    assert "Hello" in kq.text
    assert kq.confidence_level == SUY_RA


def test_pdf_khong_co_chu_thi_bao_RONG_kem_ly_do(tmp_path):
    """Trả về chuỗi rác trông như chữ còn tệ hơn báo rỗng."""
    raw = _pdf_toi_thieu(b"1 0 0 RG 100 100 m 200 200 l S")
    kq = extract_text(_viet(tmp_path, raw))
    assert kq.empty is True
    assert kq.confidence_level == KHONG_KIEM_DUOC
    ra = kq.render()
    assert "QUÉT ẢNH" in ra and "OCR" in ra


def test_trang_khong_co_chu_duoc_dem_va_bao(tmp_path):
    """Một trang quét ảnh lẫn giữa các trang chữ là chỗ dễ mất nội dung nhất."""
    raw = _pdf_hai_trang(b"BT /F1 12 Tf (Co chu) Tj ET",
                         b"1 0 0 RG 10 10 m 20 20 l S")
    kq = extract_text(_viet(tmp_path, raw))
    assert "Co chu" in kq.text
    assert kq.blank_pages == 1
    assert "1 trang KHÔNG có chữ" in kq.render()


def test_khong_phai_pdf_thi_tu_choi(tmp_path):
    p = tmp_path / "gia.pdf"
    p.write_bytes(b"day khong phai pdf")
    with pytest.raises(PdfError, match="%PDF"):
        extract_text(p)


def test_tep_khong_co(tmp_path):
    with pytest.raises(PdfError, match="Không có tệp"):
        extract_text(tmp_path / "khong-co.pdf")


def test_pdf_hong_khong_lam_sap_luot_chay(tmp_path):
    """Một hồ sơ người dùng đưa vào có thể chứa tệp hỏng — không được ném."""
    p = tmp_path / "hong.pdf"
    p.write_bytes(b"%PDF-1.7\n" + b"rac" * 200)
    kq = extract_text(p)
    assert kq.empty is True
    assert kq.note


def test_ban_in_noi_ro_KHONG_dung_lai_bo_cuc(tmp_path):
    raw = _pdf_toi_thieu(b"BT /F1 12 Tf (AB) Tj ET")
    assert "Bố cục KHÔNG được dựng lại" in extract_text(_viet(tmp_path, raw)).render()


def test_gioi_han_so_trang_duoc_ton_trong(tmp_path):
    raw = _pdf_hai_trang(b"BT /F1 12 Tf (Trang mot) Tj ET",
                         b"BT /F1 12 Tf (Trang hai) Tj ET")
    kq = extract_text(_viet(tmp_path, raw), max_pages=1)
    assert "Trang mot" in kq.text and "Trang hai" not in kq.text


# ═══════════════════ kỷ luật nêu nguồn trong hội thoại ═══════════════════


def _ket_qua(**kw):
    from eaa.agent import ChatResult, Step

    ket = ChatResult(question="q", **{k: v for k, v in kw.items() if k != "lenh"})
    for argv in kw.get("lenh", ()):
        ket.steps.append(Step(action="chay_lenh", argv=tuple(argv.split()), exit_code=0))
    return ket


def test_co_chay_lenh_co_tra_loi_ma_khong_khai_nguon_thi_BAO_DONG():
    kq = _ket_qua(answer="quy trình gồm ba bước", lenh=["handover doc", "docs list"])
    assert kq.unsourced is True
    ra = kq.render()
    assert "KHÔNG khai câu trả lời dựa trên" in ra
    assert "handover doc" in ra
    assert "không phải tài liệu bạn hỏi" in ra


def test_khai_nguon_thi_in_ra_nguon():
    kq = _ket_qua(answer="xong", lenh=["survey --read a.pdf"],
                  sources=("survey --read a.pdf",))
    assert kq.unsourced is False
    ra = kq.render()
    assert "Trả lời này dựa trên:" in ra
    assert "· survey --read a.pdf" in ra


def test_khong_chay_lenh_nao_thi_khong_doi_nguon():
    """Trả lời từ hiểu biết chung không có nguồn nào để khai."""
    kq = _ket_qua(answer="chào bạn")
    assert kq.unsourced is False
    assert "KHÔNG khai" not in kq.render()


def test_hoi_lai_thi_khong_doi_nguon():
    kq = _ket_qua(clarifying="bạn muốn module nào?", lenh=["status"])
    assert kq.unsourced is False


def test_lenh_bi_tu_choi_khong_tinh_la_nguon():
    from eaa.agent import ChatResult, Step

    kq = ChatResult(question="q", answer="xong")
    kq.steps.append(Step(action="chay_lenh", argv=("ls",), refused="ngoài danh mục"))
    assert kq.commands_run == []
    assert kq.unsourced is False


def test_nguon_doc_duoc_ca_chuoi_lan_danh_sach():
    from eaa.agent import _danh_sach_nguon

    assert _danh_sach_nguon("a") == ["a"]
    assert _danh_sach_nguon(["a", "b"]) == ["a", "b"]
    assert _danh_sach_nguon("") == []
    assert _danh_sach_nguon(None) == []


def test_luat_neu_nguon_co_trong_prompt():
    """Luật này sinh ra từ một lỗi thật, nên ca hỏng ấy phải nằm trong prompt."""
    from eaa.agent import _VAI_TRO

    assert "NÊU NGUỒN" in _VAI_TRO
    assert "TÀI LIỆU CỦA HỌ" in _VAI_TRO
    assert "CHƯA MỞ" in _VAI_TRO


def test_luoc_do_tra_loi_co_truong_nguon():
    from eaa.agent import _VAI_TRO

    assert '"nguon"' in _VAI_TRO


# ═══════════ vòng hội thoại biết dự án CÓ kho hồ sơ đã giải nén ═══════════


def test_kho_da_giai_nen_hien_trong_ngu_canh(tmp_path):
    from eaa.agent import AgentLoop

    goc = tmp_path / "sources" / "kho"
    (goc / "Huong_Dan").mkdir(parents=True)
    (goc / "Huong_Dan" / "quy_trinh.pdf").write_bytes(b"%PDF-1.7\n")
    (goc / "ma.ino").write_text("void setup(){}", encoding="utf-8")

    tom_tat = AgentLoop(project=tmp_path, llm=None)._tom_tat_kho_tai_lieu()
    assert "KHO HỒ SƠ đã giải nén" in tom_tat
    assert "2 tệp" in tom_tat
    assert "quy_trinh.pdf" in tom_tat
    assert "survey --read" in tom_tat


def test_khong_co_kho_thi_khong_them_gi(tmp_path):
    from eaa.agent import AgentLoop

    assert AgentLoop(project=tmp_path, llm=None)._tom_tat_kho_tai_lieu() == ""


def test_ngan_sach_hoi_thoai_TACH_khoi_ngan_sach_sinh_ma():
    """Mượn của nhau thì mỗi lần thêm công cụ lại phải nới số của việc khác."""
    from eaa.agent import NGAN_SACH_DANH_MUC, NGAN_SACH_QUAN_SAT, NGAN_SACH_VAI_TRO
    from eaa.llm.base import LAYER_BUDGETS, TOTAL_BUDGET

    assert NGAN_SACH_VAI_TRO != LAYER_BUDGETS["role_constraints"]
    tong = NGAN_SACH_VAI_TRO + NGAN_SACH_DANH_MUC + NGAN_SACH_QUAN_SAT
    assert tong < TOTAL_BUDGET, "ba lớp lớn nhất vẫn phải nằm dưới trần 8.000"


def test_danh_muc_va_vai_tro_vua_ngan_sach_cua_no():
    """Bài này bắt được ngay lần thêm công cụ làm tràn lớp."""
    from eaa.agent import (
        NGAN_SACH_DANH_MUC,
        NGAN_SACH_VAI_TRO,
        _VAI_TRO,
        _mo_ta_danh_muc,
    )
    from eaa.llm.base import estimate_tokens

    assert estimate_tokens(_VAI_TRO) <= NGAN_SACH_VAI_TRO
    assert estimate_tokens(_mo_ta_danh_muc()) <= NGAN_SACH_DANH_MUC


# ═════════════ lớp quan sát TỰ CẮT cho vừa, và nói ra đã cắt ═════════════


def test_quan_sat_vua_ngan_sach_thi_giu_het():
    from eaa.agent import _lop_quan_sat

    ra = _lop_quan_sat(["a" * 40, "b" * 40, "c" * 40])
    assert "a" * 40 in ra and "b" * 40 in ra and "c" * 40 in ra
    assert "đã bỏ" not in ra


# Bộ ước lượng token đếm theo TỪ, không theo ký tự — nên đầu vào thử phải có
# dấu cách, nếu không một chuỗi dài vẫn chỉ tính là một token và phép cắt
# không bao giờ chạm tới.
def _van_ban(nhan: str, so_tu: int) -> str:
    return " ".join([nhan] * so_tu)


def test_quan_sat_qua_dai_thi_bo_cai_CU_giu_cai_MOI():
    from eaa.agent import _lop_quan_sat

    ra = _lop_quan_sat([_van_ban("CU", 3000), _van_ban("MOI", 10)], budget=900)
    than, _, ghi_chu = ra.partition("(đã bỏ đầu ra của")
    assert "MOI" in than
    assert "CU" not in than, "đầu ra của quan sát cũ phải bị bỏ khỏi phần nội dung"
    assert "CU" in ghi_chu, "nhưng TÊN lệnh phải còn, để Agent khỏi chạy lại"


def test_bo_quan_sat_thi_NOI_RA_da_bo_bao_nhieu():
    """Bỏ im lặng thì mô hình tưởng nó đã thấy hết, rồi kết luận trên một nửa."""
    from eaa.agent import _lop_quan_sat

    ra = _lop_quan_sat(
        [_van_ban("x", 3000), _van_ban("y", 3000), _van_ban("z", 10)], budget=900
    )
    assert "đã bỏ đầu ra của 2 lệnh cũ" in ra
    assert "đừng chạy lại" in ra


def test_quan_sat_moi_nhat_KHONG_BAO_GIO_bi_bo():
    """Bỏ hẳn thứ vừa chạy là bỏ đúng thứ mô hình đang cần."""
    from eaa.agent import _lop_quan_sat

    ra = _lop_quan_sat([_van_ban("cu", 100), _van_ban("MOI_NHAT", 5000)], budget=200)
    assert "MOI_NHAT" in ra
    assert "cắt cho vừa ngân sách" in ra


def test_lop_quan_sat_luon_vua_ngan_sach():
    """Đây là bài canh: tràn lớp làm cả lượt chạy hỏng trước khi gọi API."""
    from eaa.agent import NGAN_SACH_QUAN_SAT, _lop_quan_sat
    from eaa.llm.base import estimate_tokens

    for so_tu in (10, 1_000, 20_000, 100_000):
        ra = _lop_quan_sat([f"$ eaa x\n{_van_ban('kk', so_tu)}"] * 5)
        assert estimate_tokens(ra) <= NGAN_SACH_QUAN_SAT, so_tu


def test_bo_quan_sat_thi_NEU_DICH_DANH_lenh_da_chay():
    """Chỉ nói 'đã bỏ 3 quan sát' là chưa đủ — và thiếu sót ấy gây ra một vòng lặp.

    Đo được: Agent mất trí nhớ về tệp mình vừa đọc, đọc lại đúng tệp ấy, đầu ra
    lại đẩy quan sát cũ ra ngoài, và nó quay vòng tới khi chạm trần số bước.
    """
    from eaa.agent import _lop_quan_sat

    qs = [
        f"$ eaa survey --read tep_{i}.pdf\n(mã thoát 0)\n" + _van_ban("noi dung", 2000)
        for i in range(3)
    ]
    qs.append("$ eaa status\n(mã thoát 0)\nngan")
    ra = _lop_quan_sat(qs, budget=400)

    assert "BẠN ĐÃ CHẠY" in ra and "đừng chạy lại" in ra
    for i in range(3):
        assert f"survey --read tep_{i}.pdf" in ra, i


def test_ghi_chu_khong_lam_lop_vuot_tran():
    """Ghi chú sinh ra để cứu lượt chạy, không phải để làm hỏng nó."""
    from eaa.agent import NGAN_SACH_QUAN_SAT, _lop_quan_sat
    from eaa.llm.base import estimate_tokens

    for so_lenh in (2, 10, 40):
        qs = [
            f"$ eaa survey --read mot_duong_dan_kha_dai_{i}.pdf\n(mã thoát 0)\n"
            + _van_ban("chu", 5000)
            for i in range(so_lenh)
        ]
        assert estimate_tokens(_lop_quan_sat(qs)) <= NGAN_SACH_QUAN_SAT, so_lenh


def test_de_nghi_nguoi_chay_cung_doi_nguon():
    """Nhánh này cũng sinh ra một câu trả lời dựa trên đầu ra lệnh."""
    kq = _ket_qua(answer="cần thêm bốn module", lenh=["survey --files *.ino"])
    kq.suggested.append("plan add drv_imu")
    assert kq.unsourced is True


def test_de_nghi_nguoi_chay_khai_nguon_thi_khong_canh_bao():
    """Cảnh báo không thể thỏa mãn dạy người ta bỏ qua cảnh báo."""
    kq = _ket_qua(answer="cần thêm bốn module", lenh=["survey --files *.ino"],
                  sources=("survey --files *.ino",))
    kq.suggested.append("plan add drv_imu")
    assert kq.unsourced is False
    assert "Trả lời này dựa trên:" in kq.render()


def test_ca_hai_nhanh_tra_loi_deu_doc_truong_nguon():
    import inspect

    from eaa import agent

    src = inspect.getsource(agent.AgentLoop.ask)
    assert src.count("_danh_sach_nguon(") == 2, "cả tra_loi lẫn de_nghi_nguoi_chay"


# ═══════ xung đột phần cứng ghi trong hồ sơ, và mã module hợp lệ ═══════


def _ho_so(tmp_path, them: str = "") -> "object":
    from eaa.kb import HardwareProfile

    p = tmp_path / "hardware_profile.yaml"
    p.write_text(
        "version: 1\nproject: thu\nmcu: {part: x, clock_hz: 1}\n"
        "peripherals: []\ncomponents: []\n" + them,
        encoding="utf-8",
    )
    return HardwareProfile.load(p)


def test_xung_dot_chua_phan_xu_thi_hien_ra(tmp_path):
    ho_so = _ho_so(tmp_path, """
conflicts:
  - pin: PB3
    claimed_by: [bluetooth.tx, rgb_leds.data]
    status: chưa phân xử
""")
    assert len(ho_so.conflicts) == 1
    assert ho_so.conflicts[0]["pin"] == "PB3"


def test_xung_dot_da_phan_xu_thi_khong_hien(tmp_path):
    ho_so = _ho_so(tmp_path, """
conflicts:
  - pin: PB3
    claimed_by: [a, b]
    status: đã phân xử
""")
    assert ho_so.conflicts == []


def test_khong_khai_xung_dot_thi_rong(tmp_path):
    assert _ho_so(tmp_path).conflicts == []


def test_tim_xung_dot_theo_chan(tmp_path):
    ho_so = _ho_so(tmp_path, """
conflicts:
  - pin: PB3
    claimed_by: [a, b]
  - pin: PD5
    claimed_by: [c, d]
""")
    assert [c["pin"] for c in ho_so.conflicts_on(["pb3"])] == ["PB3"]
    assert len(ho_so.conflicts_on(["PB3", "PD5"])) == 2
    assert ho_so.conflicts_on(["PC0"]) == []


@pytest.mark.parametrize("ma_xau", [
    "drv_x --uses twi",     # biến shell không được tách từ — đo được thật
    "Drv_X",
    "1drv",
    "d",
    "drv-x",
    "drv x",
    "",
])
def test_ma_module_khong_hop_le_bi_chan(ma_xau):
    """Mã module đi vào TÊN NHÁNH GIT và tên tệp sinh ra, nên nó phải hẹp."""
    import re

    assert not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", ma_xau)


@pytest.mark.parametrize("ma_tot", ["drv_mpu6050", "alg_pid", "app_balance", "ab"])
def test_ma_module_hop_le_duoc_nhan(ma_tot):
    import re

    assert re.fullmatch(r"[a-z][a-z0-9_]{1,39}", ma_tot)


def test_plan_add_kiem_ma_module():
    import inspect

    from eaa import cli

    src = inspect.getsource(cli._plan_add)
    assert "TÊN NHÁNH GIT" in src
    assert "re.fullmatch" in src


def test_du_an_blklab_khai_xung_dot_that():
    """Dự án dựng từ hồ sơ người dùng phải mang theo xung đột đã phát hiện."""
    from pathlib import Path

    from eaa.kb import HardwareProfile

    goc = Path(__file__).resolve().parent.parent / "projects" / "blklab_robot"
    if not goc.is_dir():
        pytest.skip("chưa có dự án blklab_robot")
    ho_so = HardwareProfile.load(goc / "hardware_profile.yaml")
    xd = ho_so.conflicts
    assert xd, "xung đột D11 tìm được khi đọc mã gốc phải nằm trong hồ sơ"
    assert xd[0]["pin"] == "PB3"
    assert "V1_Balancing_Robot_HC05_JQ6500.ino" in xd[0]["found_in"]
