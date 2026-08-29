"""TC-08 — Máy trạng thái tuần tự, gate không thể bị vượt.

Kịch bản EAA-STP-04: "Thử nhảy cóc phase (A→D) → Bị từ chối; chỉ chuyển khi
đủ điều kiện + gate."

Ở đây kiểm chứng LUẬT chuyển pha (``eaa/policy.py``) — Orchestrator ở Sprint 2
sẽ gọi luật này chứ không tự phát minh luật riêng. Đó là điểm mấu chốt của
ADR-04: gate được cưỡng chế bằng phần mềm chứ không phải bằng quy ước, nên
phải có đúng MỘT nơi phát biểu luật, và nơi đó phải có test.

Kèm theo là bảng phân quyền AUTO/APPROVE/HUMAN dịch từ Ma trận Người–AI
(6 giai đoạn, 13 công đoạn A1..F1) — nguồn của FR-ORC-01.
"""

from __future__ import annotations

import itertools

import pytest

from eaa.policy import (
    GATE_ORDER,
    PHASE_ORDER,
    STAGES,
    GateNotApproved,
    Level,
    PhaseSkip,
    PolicyViolation,
    check_transition,
    gate_for_transition,
    level,
    stage,
)

TAT_CA_DUYET = {gate: "approved" for gate in GATE_ORDER}


# --------------------------------------------------------------------------
# Luật chuyển pha
# --------------------------------------------------------------------------


def test_tc08_nhay_coc_phase_bi_tu_choi() -> None:
    """A→D là kịch bản chính của TC-08."""
    with pytest.raises(PhaseSkip) as loi:
        check_transition("A", "D", TAT_CA_DUYET)

    # Ngay cả khi MỌI gate đã duyệt: duyệt gate không mua được quyền bỏ pha.
    assert "A" in str(loi.value) and "D" in str(loi.value)


@pytest.mark.parametrize(
    ("tu", "den"),
    [
        (tu, den)
        for tu, den in itertools.product(PHASE_ORDER, PHASE_ORDER)
        # Hợp lệ: tiến đúng một bước, hoặc lùi về D để tinh chỉnh (E2→D4).
        if PHASE_ORDER.index(den) - PHASE_ORDER.index(tu) not in (1,)
        and (tu, den) != ("E", "D")
        and tu != den
    ],
)
def test_moi_buoc_nhay_khong_hop_le_deu_bi_chan(tu: str, den: str) -> None:
    with pytest.raises(PolicyViolation):
        check_transition(tu, den, TAT_CA_DUYET)


@pytest.mark.parametrize(
    ("tu", "den", "gate"),
    [
        ("A", "B", "G1"),
        ("C", "D", "G2"),
        ("D", "E", "G3"),
        ("E", "F", "G4"),
    ],
)
def test_chuyen_pha_bi_chan_khi_gate_chua_duyet(tu: str, den: str, gate: str) -> None:
    """Đủ điều kiện tuần tự vẫn chưa đủ — phải có chữ ký người ở gate."""
    for trang_thai in ("pending", "rejected"):
        gates = dict(TAT_CA_DUYET, **{gate: trang_thai})
        with pytest.raises(GateNotApproved) as loi:
            check_transition(tu, den, gates)
        assert gate in str(loi.value)


def test_gate_khuyet_trong_state_coi_nhu_chua_duyet() -> None:
    """Thiếu dữ liệu không bao giờ được diễn giải thành có quyền đi tiếp."""
    with pytest.raises(GateNotApproved):
        check_transition("A", "B", {})


@pytest.mark.parametrize(
    ("tu", "den"),
    [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")],
)
def test_chuyen_pha_hop_le_khi_du_dieu_kien(tu: str, den: str) -> None:
    check_transition(tu, den, TAT_CA_DUYET)  # không ném là đạt


def test_B_sang_C_khong_can_gate() -> None:
    """SAD Hình 2: không có ô vàng trên cung B→C."""
    assert gate_for_transition("B", "C") is None
    check_transition("B", "C", {})


def test_vong_lui_E_ve_D_duoc_phep_de_tinh_chinh() -> None:
    """SAD §4.1: "E2 không đạt → quay lại D4 chỉnh thuật toán/tham số"."""
    check_transition("E", "D", TAT_CA_DUYET)


def test_ket_thuc_du_an_can_G5() -> None:
    assert gate_for_transition("F", None) == "G5"
    with pytest.raises(GateNotApproved):
        check_transition("F", None, dict(TAT_CA_DUYET, G5="pending"))
    check_transition("F", None, TAT_CA_DUYET)


def test_phase_la_khong_hop_le_bi_bao_loi() -> None:
    with pytest.raises(PolicyViolation):
        check_transition("A", "Z", TAT_CA_DUYET)
    with pytest.raises(PolicyViolation):
        check_transition("Z", "B", TAT_CA_DUYET)


# --------------------------------------------------------------------------
# Bảng phân quyền — Ma trận Người–AI
# --------------------------------------------------------------------------


def test_ma_tran_du_13_cong_doan_tren_6_giai_doan() -> None:
    assert len(STAGES) == 13, "Ma trận Người–AI có đúng 13 công đoạn A1..F1"
    assert {s.phase for s in STAGES.values()} == set(PHASE_ORDER)


@pytest.mark.parametrize(
    ("ma", "muc"),
    [
        ("A1", Level.HUMAN),   # chốt ràng buộc cứng — 80/20
        ("A2", Level.HUMAN),   # mô hình hóa toán học — 70/30
        ("B1", Level.HUMAN),   # kiến trúc phần mềm — 80/20
        ("B2", Level.HUMAN),   # thiết kế phần cứng — 90/10
        ("C1", Level.APPROVE), # xây bộ mô phỏng — 50/50
        ("C2", Level.APPROVE), # software-in-the-loop — 50/50
        ("D1", Level.AUTO),    # khởi tạo khung dự án — 20/80
        ("D2", Level.AUTO),    # driver ngoại vi / HAL — 30/70
        ("D3", Level.AUTO),    # nhân hệ điều hành nhỏ — 40/60
        ("D4", Level.AUTO),    # thuật toán điều khiển — 40/60
        ("E1", Level.AUTO),    # unit test + phân tích tĩnh — 30/70
        ("E2", Level.HUMAN),   # kiểm thử vật lý + tuning — 80/20
        ("F1", Level.HUMAN),   # so sánh A/B, kết luận — 70/30
    ],
)
def test_muc_phan_quyen_tung_cong_doan(ma: str, muc: Level) -> None:
    assert level(ma) is muc


def test_ty_trong_nguoi_ai_khop_ma_tran_va_cong_du_100() -> None:
    for ma, cd in STAGES.items():
        assert cd.human_share + cd.ai_share == 100, f"{ma}: tỷ trọng không cộng đủ 100"


def test_cong_doan_nguoi_chu_tri_thi_khong_bao_gio_la_AUTO() -> None:
    """Bất biến NT1: người giữ quyền ở đâu thì máy không được tự quyết ở đó."""
    for ma, cd in STAGES.items():
        if cd.human_share >= 70:
            assert cd.level is not Level.AUTO, f"{ma} do người chủ trì mà lại AUTO"


def test_muc_phan_quyen_tra_cuu_duoc_ca_theo_giai_doan() -> None:
    assert level("D") is Level.AUTO
    assert level("A") is Level.HUMAN
    assert level("C") is Level.APPROVE


def test_tra_cuu_cong_doan_khong_ton_tai_bao_loi_ro_rang() -> None:
    with pytest.raises(KeyError):
        level("X9")
    assert stage("D2").phase == "D"


def test_bang_phan_quyen_khong_ro_ri_ten_phan_cung() -> None:
    """Bảo hiểm kép cho TC-38: bảng này dịch từ ma trận có nêu tên linh kiện.

    Bản trong engine phải được viết lại ở dạng tổng quát; nếu ai đó dán nguyên
    văn từ Excel vào, test này kêu trước cả TC-38.
    """
    cam = ("atmega", "mpu6050", "a4988", "tccr", "twbr", "timer1", "arduino", "avr")
    for ma, cd in STAGES.items():
        chuoi = f"{cd.name} {cd.description}".lower()
        for tu in cam:
            assert tu not in chuoi, f"{ma} nhắc tên phần cứng cụ thể: {tu!r}"
