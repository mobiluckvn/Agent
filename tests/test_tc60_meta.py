"""TC-60 — mức tin cậy, tự ghi sai lệch, tự đánh giá quy trình (N-903, N-905, N-906).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-60a | Bốn mức tin cậy là MỘT bộ từ vựng cho toàn hệ | N-903 |
| TC-60b | ĐÃ KIỂM đòi nguồn, GIẢ ĐỊNH đòi cách kiểm | không có thì đó là câu nói chắc |
| TC-60c | Các module hiện có quy về đúng bốn mức ấy | nhất quán, không mỗi nơi một kiểu |
| TC-60d | Quét ra module có trong mã mà không có trong tài liệu | N-905 |
| TC-60e | Máy KHÔNG tự phân loại loại sai lệch | phân loại là phán đoán về ý định |
| TC-60f | Sổ hiện tại khép kín | mọi thứ trong mã đều đã được ghi |
| TC-60g | Chỉ ra cổng trượt nhiều nhất kèm hướng sửa | N-906 |
| TC-60h | Mỗi đề xuất gắn với một con số quan sát được | không phải cảm giác |
| TC-60i | Ít dữ liệu ⇒ nói rõ là chưa đủ để thấy | không phải "quy trình đang tốt" |

TC-60f là phép kiểm tự quy chiếu: nó chạy chính bộ dò của N-905 lên chính kho
mã này và đòi kết quả sạch. Nhờ vậy, lần sau ai thêm một module mà quên ghi
vào sổ thì bộ test đỏ ngay — chứ không đợi tới lúc ai đó tình cờ nhận ra.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.confidence import (
    DA_KIEM,
    GIA_DINH,
    KHONG_KIEM_DUOC,
    LEVELS,
    SUY_RA,
    Claim,
    ClaimSet,
    ConfidenceError,
    label,
)
from eaa.deviation import BO_SUNG, DeviationScan, scan
from eaa.kpi import KpiLogger, ProcessReview

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# TC-60a, TC-60b, TC-60c — mức tin cậy
# --------------------------------------------------------------------------


def test_bon_muc_xep_tu_manh_toi_yeu() -> None:
    assert LEVELS == (DA_KIEM, SUY_RA, GIA_DINH, KHONG_KIEM_DUOC)


def test_muc_khong_hop_le_bi_tu_choi() -> None:
    with pytest.raises(ConfidenceError, match="không hợp lệ"):
        label("KHÁ CHẮC", "gì đó")


def test_da_kiem_ma_khong_co_nguon_thi_tu_choi() -> None:
    """Không có nguồn thì đây không phải 'đã kiểm', chỉ là một câu nói chắc."""
    with pytest.raises(ConfidenceError, match="bằng chứng"):
        Claim("chu kỳ đúng 10 ms", DA_KIEM)


def test_gia_dinh_ma_khong_noi_cach_kiem_thi_tu_choi() -> None:
    with pytest.raises(ConfidenceError, match="kiểm bằng cách nào"):
        Claim("ma sát ≈ 0,02", GIA_DINH)


def test_khong_kiem_duoc_ma_khong_noi_vi_sao_thi_tu_choi() -> None:
    """Thiếu lý do thì không biết cần dụng cụ khác hay cần cách khác."""
    with pytest.raises(ConfidenceError, match="vì sao"):
        Claim("không đọc ngược được", KHONG_KIEM_DUOC)


def test_moi_muc_neu_viec_phai_lam_de_chac_hon() -> None:
    assert Claim("x", DA_KIEM, source="đo tại G4").actionable == ""
    assert "thả dốc" in Claim("y", GIA_DINH, how_to_verify="thả dốc").actionable
    assert "dụng cụ khác" in Claim("z", KHONG_KIEM_DUOC, why_not="mạch nạp không hỗ trợ").actionable


def test_muc_yeu_nhat_cua_nhom_duoc_neu_ra() -> None:
    """Chín câu đã kiểm và một câu giả định thì mạnh ngang câu giả định ấy."""
    nhom = ClaimSet(title="thử")
    for i in range(9):
        nhom.add(f"đo {i}", DA_KIEM, source="telemetry")
    nhom.add("ma sát", GIA_DINH, how_to_verify="thả dốc")

    assert nhom.weakest == GIA_DINH
    assert "Mức yếu nhất trong nhóm" in nhom.render()


def test_nhom_toan_da_kiem_thi_khong_nhac_gi_them() -> None:
    nhom = ClaimSet()
    nhom.add("x", DA_KIEM, source="telemetry")
    assert nhom.weakest == DA_KIEM
    assert "Mức yếu nhất" not in nhom.render()


def test_cac_module_hien_co_quy_ve_dung_bon_muc() -> None:
    """Nhất quán toàn hệ nghĩa là năm chỗ này nói cùng một thứ tiếng."""
    from eaa.docplan import ErrataAnalysis
    from eaa.endurance import EnduranceReport
    from eaa.flash import VERIFY_KHONG_KIEM_DUOC, VERIFY_KHOP, VerifyResult
    from eaa.propose import DA_DO, UOC_LUONG, PinCheck, PlantParameter
    from eaa.propose import PIN_KHONG_KIEM_DUOC

    assert VerifyResult(VERIFY_KHOP).confidence == DA_KIEM
    assert VerifyResult(VERIFY_KHONG_KIEM_DUOC, "x").confidence == KHONG_KIEM_DUOC

    assert ErrataAnalysis(looked_up=False).confidence_level == KHONG_KIEM_DUOC
    assert ErrataAnalysis(looked_up=True, silicon_rev="D").confidence_level == DA_KIEM
    assert ErrataAnalysis(looked_up=True).confidence_level == SUY_RA

    assert PlantParameter("m", 1.0, "kg", DA_DO).confidence_level == DA_KIEM
    assert (
        PlantParameter("b", 0.02, "1", UOC_LUONG, how_to_measure="thả dốc").confidence_level
        == GIA_DINH
    )

    assert PinCheck("P1", "scl", PIN_KHONG_KIEM_DUOC).confidence_level == KHONG_KIEM_DUOC

    assert EnduranceReport(uptime_present=False).confidence_level == KHONG_KIEM_DUOC
    assert (
        EnduranceReport(observed_s=10, required_s=600).confidence_level == GIA_DINH
    ), "chạy chưa đủ lâu là kiểm được mà chưa kiểm, không phải không kiểm được"
    assert EnduranceReport(observed_s=700, required_s=600).confidence_level == DA_KIEM


def test_nhan_hien_ra_trong_dau_ra_cho_nguoi_doc() -> None:
    from eaa.flash import VERIFY_KHOP, VerifyResult

    assert DA_KIEM in VerifyResult(VERIFY_KHOP).render()


# --------------------------------------------------------------------------
# TC-60d, TC-60e, TC-60f — tự phát hiện sai lệch
# --------------------------------------------------------------------------


def _kho_gia(tmp_path: Path, *, modules: list[str], sdd: str, so: str) -> Path:
    (tmp_path / "eaa").mkdir()
    for m in modules:
        (tmp_path / "eaa" / m).write_text("", encoding="utf-8")
    (tmp_path / "docs" / "md").mkdir(parents=True)
    (tmp_path / "docs" / "md" / "EAA-SDD-03_Thiet_ke_chi_tiet.md").write_text(
        sdd, encoding="utf-8"
    )
    (tmp_path / "docs" / "SAI_LECH_THIET_KE.md").write_text(so, encoding="utf-8")
    return tmp_path


def test_module_khong_co_trong_tai_lieu_bi_neu_ten(tmp_path: Path) -> None:
    goc = _kho_gia(
        tmp_path, modules=["state.py", "la_mat.py"], sdd="cây thư mục: state.py", so=""
    )
    ket_qua = scan(goc)

    assert len(ket_qua.found) == 1
    assert "la_mat.py" in ket_qua.found[0].subject


def test_module_da_duoc_ghi_trong_so_thi_khong_bi_neu_lai(tmp_path: Path) -> None:
    """Sổ là nơi hợp lệ để ghi một module phát sinh sau thiết kế."""
    goc = _kho_gia(
        tmp_path,
        modules=["state.py", "moi.py"],
        sdd="cây thư mục: state.py",
        so="## SL-01 · BỔ SUNG · `eaa/moi.py` — module mới\n",
    )
    assert scan(goc).clean


def test_tep_khoi_tao_khong_bi_tinh_la_sai_lech(tmp_path: Path) -> None:
    goc = _kho_gia(tmp_path, modules=["__init__.py"], sdd="", so="")
    assert scan(goc).clean


def test_lenh_khong_co_trong_tai_lieu_bi_neu_ten(tmp_path: Path) -> None:
    goc = _kho_gia(tmp_path, modules=[], sdd="lệnh: eaa init, eaa gen", so="")
    ket_qua = scan(goc, cli_commands=["init", "gen", "la-mat"])

    assert len(ket_qua.found) == 1
    assert "la-mat" in ket_qua.found[0].subject


def test_so_hieu_ke_tiep_doc_duoc_tu_so(tmp_path: Path) -> None:
    goc = _kho_gia(
        tmp_path,
        modules=[],
        sdd="",
        so="## SL-01 · BỔ SUNG · a\n\n## SL-07 · DỜI CHỖ · b\n",
    )
    ket_qua = scan(goc)
    assert ket_qua.recorded == 2 and ket_qua.next_number == 8


def test_may_khong_tu_phan_loai_loai_sai_lech(tmp_path: Path) -> None:
    """Phân loại là phán đoán về ý định; lý do chỉ người làm mới biết."""
    goc = _kho_gia(tmp_path, modules=["la.py"], sdd="", so="")
    ket_qua = scan(goc)
    nhap = ket_qua.draft_all()

    assert ket_qua.found[0].suggested_class == BO_SUNG
    assert "_(điền: lý do KỸ THUẬT — máy không biết ý định)_" in nhap
    assert "KHÔNG tự phân loại" in ket_qua.render()


def test_nhap_danh_so_tiep_tu_so_hien_co(tmp_path: Path) -> None:
    goc = _kho_gia(tmp_path, modules=["a.py", "b.py"], sdd="", so="## SL-05 · BỔ SUNG · x\n")
    nhap = scan(goc).draft_all()

    assert "## SL-06 ·" in nhap and "## SL-07 ·" in nhap


def test_bao_cao_noi_ro_gioi_han_cua_chinh_no(tmp_path: Path) -> None:
    goc = _kho_gia(tmp_path, modules=[], sdd="", so="")
    van_ban = scan(goc).render()

    assert "KHÔNG bắt được" in van_ban
    assert "làm khác điều tài liệu mô tả" in van_ban


def test_kho_ma_nay_khep_kin() -> None:
    """Phép kiểm tự quy chiếu: chạy bộ dò của N-905 lên chính kho này.

    Lần sau ai thêm một module mà quên ghi vào sổ thì bộ test đỏ ngay, chứ
    không đợi tới lúc ai đó tình cờ nhận ra. Đây đúng là điều một sổ ghi tay
    không làm được.
    """
    from eaa.cli import build_parser

    bo = build_parser()
    lenh: list[str] = []
    for hd in (bo._subparsers._group_actions if bo._subparsers else []):
        lenh.extend(getattr(hd, "choices", {}) or {})

    ket_qua = scan(REPO, cli_commands=sorted(set(lenh)))
    assert ket_qua.clean, (
        "Có chỗ mã và tài liệu kể hai câu chuyện khác nhau:\n" + ket_qua.render()
    )


# --------------------------------------------------------------------------
# TC-60g, TC-60h, TC-60i — tự đánh giá quy trình
# --------------------------------------------------------------------------


def _kpi_mau(tmp_path: Path) -> KpiLogger:
    kpi = KpiLogger(tmp_path / "kpi_log.csv")
    for _ in range(4):
        kpi.log(event="verify", module="drv_a", gate="static", result="fail")
    kpi.log(event="verify", module="drv_a", gate="compile", result="fail")
    for _ in range(3):
        kpi.log(event="repair", module="drv_a")
    kpi.log(event="merge", module="drv_a", result="pass")
    kpi.log(event="handoff", module="drv_b", result="fail")
    kpi.log(event="gate_decision", module="drv_a", gate="G3", result="reject")
    return kpi


def test_chi_ra_cong_truot_nhieu_nhat(tmp_path: Path) -> None:
    review = _kpi_mau(tmp_path).weak_points()

    assert review.worst_gate == "static"
    assert review.gate_failures["static"] == 4


def test_de_xuat_gan_voi_mot_con_so_quan_sat_duoc(tmp_path: Path) -> None:
    """Không đo thì mọi cải tiến chỉ là cảm giác — nên mỗi đề xuất phải có số."""
    y_kien = _kpi_mau(tmp_path).weak_points().suggestions()

    assert any("'static' trượt 4 lần" in y for y in y_kien)
    assert any("forbidden" in y for y in y_kien), "hướng sửa phải cụ thể"


def test_module_va_nhieu_lan_duoc_goi_ten_kem_viec_phai_lam(tmp_path: Path) -> None:
    y_kien = _kpi_mau(tmp_path).weak_points().suggestions()
    assert any("eaa resolve drv_a" in y for y in y_kien)


def test_ban_giao_nguoi_va_tu_choi_deu_thanh_de_xuat(tmp_path: Path) -> None:
    y_kien = _kpi_mau(tmp_path).weak_points().suggestions()

    assert any("chạm trần tự sửa" in y for y in y_kien)
    assert any("TỪ CHỐI tại gate" in y for y in y_kien)


def test_ti_le_ao_giac_cao_thanh_de_xuat(tmp_path: Path) -> None:
    class _SoAoGiac:
        def all(self):
            return [object(), object(), object()]

    y_kien = _kpi_mau(tmp_path).weak_points(ledger=_SoAoGiac()).suggestions()
    assert any("Error Ledger cho mỗi lần merge" in y for y in y_kien)


def test_so_ao_giac_hong_khong_lam_dut_phan_tong_hop(tmp_path: Path) -> None:
    class _SoHong:
        def all(self):
            raise RuntimeError("tệp hỏng")

    review = _kpi_mau(tmp_path).weak_points(ledger=_SoHong())
    assert review.ledger_entries == 0
    assert review.worst_gate == "static"


def test_chua_co_du_lieu_thi_noi_ro_la_chua_du_de_thay(tmp_path: Path) -> None:
    """Không phải 'quy trình đang tốt'."""
    kpi = KpiLogger(tmp_path / "kpi_log.csv")
    kpi.log(event="merge", module="drv_a", result="pass")
    van_ban = kpi.weak_points().render()

    assert "chưa đủ" in van_ban and "dữ liệu để thấy" in van_ban


def test_khong_co_dong_nao_thi_noi_thang(tmp_path: Path) -> None:
    van_ban = KpiLogger(tmp_path / "khong-co.csv").weak_points().render()
    assert "cảm giác" in van_ban


def test_bao_cao_noi_ro_day_la_de_xuat_khong_phai_ket_luan(tmp_path: Path) -> None:
    van_ban = _kpi_mau(tmp_path).weak_points().render()

    assert "ĐỀ XUẤT" in van_ban
    assert "vẫn là việc của người" in van_ban


def test_summary_van_khong_dien_giai(tmp_path: Path) -> None:
    """Ranh giới phải giữ: một hàm tổng hợp, một hàm diễn giải."""
    tom_tat = _kpi_mau(tmp_path).summary()
    assert "worst_gate" not in tom_tat
    assert set(tom_tat) >= {"rows", "modules", "merges", "repairs"}
