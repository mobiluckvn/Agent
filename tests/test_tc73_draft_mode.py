"""TC-73 — chế độ nháp: hạ ceremony mà KHÔNG hạ bất biến merge.

Đây là bài canh phần nhạy cảm nhất của cả sản phẩm. Yêu cầu "cho người dùng tự
chọn cổng nào bật" đụng thẳng vào *merge chỉ xảy ra khi TOÀN BỘ
ToolReport.passed*. Cách hiển nhiên — một cờ bỏ qua cổng — phá bất biến ấy, và
cờ đó sẽ được dùng đúng vào lúc gấp.

Bản nháp ở đây không merge được **do cấu tạo**: nó không ghi bằng chứng vào
tệp mà đường merge đọc. Không có câu ``if`` nào ở phía merge phải nhớ đặt cho
đúng — nên bài này kiểm đúng điều ấy, chứ không kiểm một thông báo lỗi.

Bài này cũng canh một lỗ hổng bịt kèm: ``MergeAuthorization`` trước đây kiểm
"mọi báo cáo CÓ MẶT đều đạt" mà không kiểm chúng có **phủ đủ** bộ cổng bắt
buộc không. Hai phép kiểm ấy khác nhau ở chỗ nguy hiểm.
"""

from __future__ import annotations

import pytest

from eaa.gates import APPROVED, GateDecision
from eaa.orchestrator import OrchestratorConfig
from eaa.tools.base import ToolReport
from eaa.vcs import MergeNotAuthorized, authorize_merge

BO_DAY_DU = ("compile", "size", "static", "unittests")


def _bao_cao(*ten: str, passed: bool = True) -> list[ToolReport]:
    return [ToolReport(gate=t, passed=passed) for t in ten]


def _quyet_dinh(digest: str = "abc123") -> GateDecision:
    return GateDecision(
        gate_id="G3", decision=APPROVED, actor="vu-tri-cong",
        decided_at="2026-08-30T00:00:00+00:00", payload_digest="p1",
        reason="ok", content_digest=digest,
    )


# ═════════════════ lỗ hổng phủ cổng — bịt kèm chế độ nháp ═════════════════


def test_bang_chung_du_cong_thi_cap_giay_phep():
    giay = authorize_merge(
        module_id="drv_i2c", branch="feature/drv_i2c",
        reports=_bao_cao(*BO_DAY_DU), decision=_quyet_dinh(),
        content_digest="abc123", required_gates=BO_DAY_DU,
    )
    assert giay.gates_passed == BO_DAY_DU


def test_bang_chung_THIEU_cong_bi_tu_choi_du_cong_co_mat_deu_dat():
    """'Toàn bộ ToolReport.passed' đúng về chữ nghĩa mà rỗng về nội dung.

    Một bằng chứng chỉ chứa mỗi ``compile`` — đạt — vẫn thỏa phép kiểm cũ. Bộ
    báo cáo mới là thứ quyết định câu ấy có nghĩa gì.
    """
    with pytest.raises(MergeNotAuthorized, match="thiếu cổng"):
        authorize_merge(
            module_id="drv_i2c", branch="b",
            reports=_bao_cao("compile"), decision=_quyet_dinh(),
            content_digest="abc123", required_gates=BO_DAY_DU,
        )


@pytest.mark.parametrize("thieu", BO_DAY_DU)
def test_thieu_bat_ky_cong_nao_cung_bi_chan(thieu):
    con_lai = [g for g in BO_DAY_DU if g != thieu]
    with pytest.raises(MergeNotAuthorized) as loi:
        authorize_merge(
            module_id="drv_i2c", branch="b", reports=_bao_cao(*con_lai),
            decision=_quyet_dinh(), content_digest="abc123",
            required_gates=BO_DAY_DU,
        )
    assert thieu in str(loi.value)


def test_khong_neu_bo_bat_buoc_thi_giu_hanh_vi_cu():
    """Bên gọi không nêu thì chỉ kiểm được 'cổng nào có thì cổng ấy đạt'."""
    giay = authorize_merge(
        module_id="drv_i2c", branch="b", reports=_bao_cao("compile"),
        decision=_quyet_dinh(), content_digest="abc123",
    )
    assert giay.gates_passed == ("compile",)


def test_cong_truot_van_bi_chan_nhu_cu():
    with pytest.raises(MergeNotAuthorized, match="chưa đạt"):
        authorize_merge(
            module_id="drv_i2c", branch="b",
            reports=_bao_cao("compile", "size") + _bao_cao("static", passed=False)
            + _bao_cao("unittests"),
            decision=_quyet_dinh(), content_digest="abc123",
            required_gates=BO_DAY_DU,
        )


def test_orchestrator_truyen_bo_cong_bat_buoc_xuong_giay_phep():
    """Nếu không truyền, lỗ hổng phủ cổng vẫn mở dù đã bịt ở vcs.py."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.finalize_module)
    assert "required_gates=self.config.required_gates" in src


# ═══════════════════════════ cấu hình chế độ nháp ═══════════════════════════


def test_mac_dinh_khong_phai_nhap():
    c = OrchestratorConfig()
    assert c.is_draft is False
    assert c.gates_to_run == BO_DAY_DU


def test_khai_cong_nhap_thi_doi_tap_cong_chay():
    c = OrchestratorConfig(draft_gates=("compile",))
    assert c.is_draft is True
    assert c.gates_to_run == ("compile",)
    # Bộ ĐẦY ĐỦ vẫn nguyên — nó là thứ giấy phép merge đối chiếu.
    assert c.required_gates == BO_DAY_DU


def test_ban_nhap_KHONG_ghi_bang_chung():
    """Bất biến giữ được do CẤU TẠO, không do một phép kiểm thêm.

    Bài này đọc mã: nhánh nháp phải trả về TRƯỚC khi chạm ``_luu_bang_chung``.
    Kiểm bằng cách chạy thì phải dựng cả một dự án; kiểm bằng cách đọc thì bắt
    được ngay cả khi ai đó dời lời gọi ấy lên trên.
    """
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    i_nhap = src.index("if self.config.is_draft:")
    i_luu = src.index("self._luu_bang_chung(")
    i_gate = src.index("self._xin_gate(")
    assert i_nhap < i_luu, "nhánh nháp phải trả về trước khi lưu bằng chứng"
    assert i_nhap < i_gate, "nhánh nháp phải trả về trước khi xin gate"


def test_ban_nhap_khong_dat_trang_thai_cho_duyet():
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    nhanh_nhap = src[src.index("if self.config.is_draft:"):src.index('# Bước 10')]
    assert "in_review" not in nhanh_nhap
    assert '"draft"' in nhanh_nhap


def test_tien_dieu_kien_theo_tap_cong_SE_CHAY():
    """Nháp chỉ chạy vài cổng thì đòi đủ cả bốn cổng là chặn nhầm."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator._kiem_tien_dieu_kien)
    assert "self.config.gates_to_run" in src
    assert "self.config.required_gates" not in src


def test_chuoi_cong_nhap_giu_nguyen_thu_tu_goc():
    """Cổng sau ăn sản phẩm của cổng trước — đảo thứ tự là chạy trên thứ chưa có."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator._chay_chuoi_cong)
    assert "for g in chuoi" in src or "in chuoi if" in src
    assert "self.config.draft_gates" in src
