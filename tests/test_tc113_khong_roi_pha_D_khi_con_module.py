"""TC-113 — không rời pha phát triển khi còn module chưa viết.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-146.

Tìm ra giữa lúc sinh mã cho robot cân bằng. Duyệt G3 cho `drv_i2c` — module
thứ ba trong bảy — rồi duyệt G2 cho một trích đoạn tài liệu mới. Máy trạng
thái in ra::

    Dự án chuyển sang pha E — Kiểm thử & tinh chỉnh.

Và lệnh kế tiếp chết::

    Lỗi: Dự án đang ở pha E; vòng sinh mã chỉ chạy ở pha D.

Bốn module còn nguyên `todo`.

G3 là cổng CỦA TỪNG MODULE, máy trạng thái đọc nó như cổng của cả dự án
--------------------------------------------------------------------------

Cung D → E gác bằng G3, và `check_transition` chỉ nhìn `gates`. Duyệt G3 lần
đầu tiên cho module đầu tiên là mở vĩnh viễn cánh cửa ra khỏi pha phát triển —
vì trạng thái gate không quay về `pending` sau khi merge.

Nó không lộ ra suốt bốn sprint vì chưa dự án nào đi qua hơn một module.

Vì sao chặn ở đây chứ không chỗ khác
-------------------------------------

Ra khỏi pha D là tuyên bố "firmware viết xong". Tuyên bố ấy sai khi backlog
còn `todo`, và cái giá không phải là một thông báo khó hiểu: pha E đặt mức
phân quyền về HUMAN, nên vòng sinh mã đóng lại và người phải tự gỡ trạng thái
để đi tiếp.
"""

from __future__ import annotations

import pytest

from eaa.policy import GateNotApproved, PolicyViolation, check_transition


def _muc(ma: str, trang_thai: str):
    from eaa.state import BacklogItem

    return BacklogItem(id=ma, status=trang_thai)


GATES = {"G1": "approved", "G2": "approved", "G3": "approved"}


def test_con_module_todo_thi_KHONG_roi_pha_D() -> None:
    with pytest.raises(PolicyViolation) as loi:
        check_transition(
            "D", "E", GATES,
            backlog=[_muc("drv_i2c", "merged"), _muc("app_balance", "todo")],
        )
    thong_diep = str(loi.value)
    assert "app_balance" in thong_diep, "không nói module nào còn dở"
    assert "drv_i2c" not in thong_diep, "module đã merge không phải chuyện đang cản"


def test_module_dang_review_cung_can_lam_xong() -> None:
    """`in_review` là đang chờ người quyết — chưa phải xong."""
    with pytest.raises(PolicyViolation):
        check_transition("D", "E", GATES, backlog=[_muc("logic_pid", "in_review")])


def test_merged_het_thi_di_tiep_duoc() -> None:
    check_transition(
        "D", "E", GATES,
        backlog=[_muc("drv_i2c", "merged"), _muc("app_balance", "merged")],
    )


def test_backlog_rong_van_di_tiep_duoc() -> None:
    """Dự án không có module nào thì không có gì cản — giữ hành vi cũ."""
    check_transition("D", "E", GATES, backlog=[])
    check_transition("D", "E", GATES)


def test_gate_chua_duyet_van_la_ly_do_chan_TRUOC() -> None:
    """Thiếu G3 vẫn phải báo thiếu G3, không báo nhầm sang chuyện backlog."""
    with pytest.raises(GateNotApproved):
        check_transition(
            "D", "E", {"G1": "approved"}, backlog=[_muc("x", "merged")]
        )


def test_cung_KHAC_khong_bi_anh_huong() -> None:
    """Chỉ cung D → E mới quan tâm backlog; C → D thì không."""
    check_transition("C", "D", GATES, backlog=[_muc("app_balance", "todo")])


def test_orchestrator_TRUYEN_backlog_xuong() -> None:
    """Luật đúng mà không ai gọi kèm dữ liệu thì luật không chạy."""
    import inspect

    from eaa.orchestrator import Orchestrator

    nguon = inspect.getsource(Orchestrator.advance_phase)
    assert "backlog" in nguon, (
        "advance_phase gọi check_transition mà không đưa backlog — luật mới "
        "không bao giờ được áp"
    )
