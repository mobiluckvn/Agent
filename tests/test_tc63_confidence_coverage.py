"""TC-63 — mọi đầu ra mang kết luận đều nói được nó ở mức tin cậy nào (N-903).

N-903 đòi: *"Phân biệt ĐÃ KIỂM / SUY RA / GIẢ ĐỊNH ở mọi đầu ra. Không đọc
được thì nói không đọc được, thay vì trả một câu trả lời trông giống như đã
kiểm."*

Tệp này là cách "mọi đầu ra" trở nên **kiểm được**. Nó liệt kê các lớp mang
kết luận và đòi từng lớp có `confidence_level` hợp lệ. Thêm một tính năng sinh
ra kết luận mới mà quên gắn nhãn thì thêm một dòng vào bảng dưới đây sẽ làm
test đỏ — chứ không phải đợi ai đó tình cờ nhận ra.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-63a | Mỗi lớp kết luận có `confidence_level` thuộc bốn mức | |
| TC-63b | Mức phản ánh đúng tình trạng, không phải một hằng số cho đẹp | |
| TC-63c | Mức yếu nhất quyết định, không phải đa số | |
| TC-63d | Mỗi mức tự giải thích được bằng một dòng | |
| TC-63e | Nhãn xuất hiện ở ĐẦU báo cáo, không phải cuối | |
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
    ConfidenceError,
    Judged,
    describe,
    header,
)

REPO = Path(__file__).resolve().parent.parent


def _lop_ket_luan() -> list[tuple[str, Any]]:  # noqa: F821
    """Danh sách lớp mang kết luận, dựng bằng đối tượng thật.

    Dựng đối tượng chứ không chỉ kiểm lớp: một thuộc tính khai mà ném ngoại lệ
    lúc chạy thì cũng như không có.
    """
    from eaa.acceptance import DeviceCheck
    from eaa.budget import ModuleBudgetCheck, TokenBudget, TokenUsage
    from eaa.diagnostics import Diagnosis, ScenarioLibrary, Scenario, ScenarioMatch, TU_KHOA
    from eaa.docplan import DocumentPlan, ErrataAnalysis, PagePlan
    from eaa.endurance import EnduranceReport
    from eaa.flash import VERIFY_KHOP, VerifyResult
    from eaa.goldenset import RetrievalReport
    from eaa.handover import SwapAnalysis
    from eaa.interfaces import InterfaceSpec
    from eaa.kpi import ProcessReview
    from eaa.propose import (
        DA_DO,
        AcceptanceProposal,
        ConstraintProposal,
        PinCheck,
        PIN_HO_TRO,
        PinMapProposal,
        PlantModelProposal,
        PlantParameter,
        ScopeProposal,
    )
    from eaa.readiness import Ric
    from eaa.safety import SafetyAnalysis

    kb = Scenario(id="DS-01", title="thử")
    return [
        ("VerifyResult", VerifyResult(VERIFY_KHOP)),
        ("ErrataAnalysis", ErrataAnalysis(looked_up=True, silicon_rev="D")),
        ("DocumentPlan", DocumentPlan()),
        ("PagePlan", PagePlan()),
        ("PlantParameter", PlantParameter("m", 1.0, "kg", DA_DO)),
        ("PinCheck", PinCheck("P1", "scl", PIN_HO_TRO)),
        ("EnduranceReport", EnduranceReport(observed_s=700, required_s=600)),
        ("ScenarioMatch", ScenarioMatch(scenario=kb, tier=TU_KHOA)),
        ("Diagnosis", Diagnosis(scenario="DS-01", verdict="code", machine_passed=False)),
        ("Ric", Ric(module_id="m")),
        ("SafetyAnalysis", SafetyAnalysis(modes=())),
        ("ScopeProposal", ScopeProposal()),
        ("ConstraintProposal", ConstraintProposal()),
        ("AcceptanceProposal", AcceptanceProposal()),
        ("PinMapProposal", PinMapProposal()),
        ("PlantModelProposal", PlantModelProposal(ignored=("ma sát",))),
        ("InterfaceSpec", InterfaceSpec(module_id="m")),
        ("SwapAnalysis", SwapAnalysis(old_part="a", new_part="b")),
        ("RetrievalReport", RetrievalReport()),
        ("ProcessReview", ProcessReview()),
        ("ModuleBudgetCheck", ModuleBudgetCheck("m")),
        ("TokenBudgetCheck", TokenBudget(per_module=10).check(TokenUsage("m"))),
        ("DeviceCheck", DeviceCheck(verified=True, readback_verified=True)),
    ]


from typing import Any  # noqa: E402  (đặt sau để _lop_ket_luan đọc được)


# --------------------------------------------------------------------------
# TC-63a — phủ hết
# --------------------------------------------------------------------------


@pytest.mark.parametrize("ten,vat", _lop_ket_luan(), ids=lambda x: x if isinstance(x, str) else "")
def test_moi_lop_ket_luan_deu_noi_duoc_muc_tin_cay(ten: str, vat: Any) -> None:
    muc = vat.confidence_level
    assert muc in LEVELS, f"{ten} trả về mức lạ: {muc!r}"
    assert isinstance(vat, Judged), f"{ten} không theo hợp đồng Judged"


def test_danh_sach_nay_phu_du_cac_module_sinh_ket_luan() -> None:
    """Canh chính bảng ở trên: thiếu một module là thiếu một chỗ có thể lọt."""
    module = {ten for ten, _ in _lop_ket_luan()}
    assert len(module) >= 20, "bảng bị rút ngắn — kiểm lại xem có lớp nào bị bỏ"


# --------------------------------------------------------------------------
# TC-63b, TC-63c — mức phản ánh đúng tình trạng
# --------------------------------------------------------------------------


def test_chan_doan_du_hai_kenh_la_DA_KIEM() -> None:
    from eaa.diagnostics import Diagnosis

    du = Diagnosis(
        scenario="DS-03", verdict="điện", machine_passed=True,
        machine_evidence=["✓ pulses_emitted=200"], human_answers={"truc_quay": False},
    )
    assert du.confidence_level == DA_KIEM


def test_chan_doan_thieu_kenh_nguoi_chi_la_SUY_RA() -> None:
    """Máy biết nó đã phát xung; nó không biết trục có quay."""
    from eaa.diagnostics import Diagnosis

    thieu = Diagnosis(
        scenario="DS-03", verdict="code", machine_passed=True,
        machine_evidence=["✓ pulses_emitted=200"],
    )
    assert thieu.confidence_level == SUY_RA


def test_chan_doan_khong_co_gi_la_KHONG_KIEM_DUOC() -> None:
    from eaa.diagnostics import Diagnosis

    trong = Diagnosis(scenario="DS-01", verdict="chưa kết luận", machine_passed=False)
    assert trong.confidence_level == KHONG_KIEM_DUOC


def test_bang_kiem_lay_muc_YEU_NHAT_khong_lay_da_so() -> None:
    """Mười mục CÓ và một mục MÂU THUẪN thì cả bảng chỉ chắc tới mức mục ấy."""
    from eaa.readiness import ItemStatus, Ric, RicItem

    day_du = Ric("m", items=[RicItem(key=f"R{i}", kind="thanh ghi", status=ItemStatus.PRESENT) for i in range(10)])
    assert day_du.confidence_level == DA_KIEM

    co_mau_thuan = Ric(
        "m",
        items=[RicItem(key=f"R{i}", kind="thanh ghi", status=ItemStatus.PRESENT) for i in range(10)]
        + [RicItem(key="RX", kind="thanh ghi", status=ItemStatus.CONFLICT)],
    )
    assert co_mau_thuan.confidence_level == KHONG_KIEM_DUOC


def test_an_toan_con_kieu_hong_khong_phat_hien_duoc_thi_tut_muc() -> None:
    from eaa.safety import FailureMode, SafetyAnalysis

    sach = SafetyAnalysis(modes=(FailureMode(id="a_hong", resource="x", failure="y", detection="quá hạn 50ms"),))
    ho = SafetyAnalysis(modes=(FailureMode(id="b_hong", resource="x", failure="y"),))

    assert sach.confidence_level == GIA_DINH
    assert ho.confidence_level == KHONG_KIEM_DUOC


def test_chay_dai_chua_du_lau_la_GIA_DINH_khong_phai_KHONG_KIEM_DUOC() -> None:
    """Kiểm được mà chưa ai bỏ thời gian ra — khác hẳn với không với tới."""
    from eaa.endurance import EnduranceReport

    assert EnduranceReport(observed_s=10, required_s=600).confidence_level == GIA_DINH
    assert EnduranceReport(uptime_present=False).confidence_level == KHONG_KIEM_DUOC


def test_ngan_sach_chua_co_so_do_thi_khong_ket_luan_gi() -> None:
    from eaa.budget import ModuleBudgetCheck, MetricUsage, TRONG_PHAN

    assert ModuleBudgetCheck("m").confidence_level == KHONG_KIEM_DUOC
    co_do = ModuleBudgetCheck("m", usages=[MetricUsage("flash_bytes", 100, 200, TRONG_PHAN)])
    assert co_do.confidence_level == DA_KIEM


def test_de_xuat_chua_duyet_luon_la_GIA_DINH() -> None:
    """Lập luận tốt tới đâu thì một bản chưa qua gate vẫn là một đề xuất."""
    from eaa.propose import ConstraintProposal, ScopeProposal

    assert ScopeProposal().confidence_level == GIA_DINH
    assert ConstraintProposal().confidence_level == GIA_DINH


# --------------------------------------------------------------------------
# TC-63d, TC-63e — nhãn tự giải thích và đứng ở đầu
# --------------------------------------------------------------------------


def test_moi_muc_tu_giai_thich_duoc() -> None:
    for muc in LEVELS:
        assert len(describe(muc)) > 30, f"{muc} giải thích quá ngắn"


def test_muc_la_thi_bi_tu_choi() -> None:
    with pytest.raises(ConfidenceError):
        describe("KHÁ CHẮC")
    with pytest.raises(ConfidenceError):
        header("KHÁ CHẮC")


def test_nhan_dung_o_DAU_bao_cao() -> None:
    """Một bản đọc hết rồi mới thấy dòng 'đây chỉ là phỏng đoán' thì tới muộn."""
    from eaa.diagnostics import Diagnosis

    van_ban = Diagnosis(scenario="DS-01", verdict="code", machine_passed=False).render()
    dong = [d for d in van_ban.splitlines() if d.strip()]

    vi_tri = next(i for i, d in enumerate(dong) if "[" in d and "]" in d)
    assert vi_tri <= 1, "nhãn phải nằm trong hai dòng đầu"


def test_header_kem_giai_thich() -> None:
    van_ban = header(SUY_RA, "Kết luận chẩn đoán")
    assert SUY_RA in van_ban
    assert "chưa ai kiểm ở đời thật" in van_ban
