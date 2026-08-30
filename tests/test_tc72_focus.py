"""TC-72 — vào thẳng việc cần làm: nói cả quãng đường, không bỏ chặng nào.

Bất biến bài này canh: ``focus`` **đảo chiều thông tin, không nới quyền**.
Cùng bộ tiền điều kiện của ``Orchestrator``, cùng những gate ấy — chỉ khác chỗ
nó đi hết thay vì ném ở cái chặn đầu tiên.

Chặng nào thuộc về người thì vẫn thuộc về người, và ``agent_steps`` **cắt** ở
chặng ấy: một chặng "người" ở giữa nghĩa là mọi chặng sau nó phụ thuộc vào một
quyết định chưa có.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from eaa.confidence import SUY_RA
from eaa.focus import AGENT, CHUA, DAT, NGUOI, FocusPlan, Precondition, analyse


@dataclass
class _Muc:
    id: str
    status: str = "todo"
    uses: tuple = ()
    depends_on: tuple = ()


@dataclass
class _State:
    phase: str = "D"
    gates: dict = field(default_factory=lambda: {"G1": "approved", "G2": "approved"})
    backlog: list = field(default_factory=list)

    def module(self, ma):
        for m in self.backlog:
            if m.id == ma:
                return m
        return None


def _san_sang(**kw):
    """Trạng thái đã qua mọi chặng — dùng làm nền để đổi từng thứ một."""
    return _State(backlog=[_Muc("drv_i2c")], **kw)


# ═══════════════════════════ đường thông suốt ═══════════════════════════


def test_moi_dieu_kien_dat_thi_khong_con_gi_chan():
    lo = analyse(module_id="drv_i2c", state=_san_sang())
    assert lo.ready is True
    assert lo.blocked_by == []
    assert "chạy được ngay" in lo.render()


def test_lo_trinh_luon_la_suy_ra_khong_phai_da_kiem():
    """Lộ trình đọc từ trạng thái hiện tại, chưa chạy thử bước nào."""
    assert analyse(module_id="x", state=_san_sang()).confidence_level == SUY_RA


# ══════════════════════════ chặng: chuỗi cổng ══════════════════════════


def test_thieu_cong_kiem_chung_thi_chan_va_chi_sang_pack():
    lo = analyse(module_id="drv_i2c", state=_san_sang(),
                 missing_chain_gates=["static", "unittests"])
    p = lo.preconditions[0]
    assert p.met is False and p.who == NGUOI
    assert "static" in p.detail
    assert "sửa pack, không sửa engine" in p.reason


# ═════════════════════════════ chặng: pha ═════════════════════════════


def test_o_pha_A_thi_ke_du_ca_hai_gate_phai_duyet():
    lo = analyse(module_id="drv_i2c",
                 state=_State(phase="A", gates={}, backlog=[_Muc("drv_i2c")]),
                 gate_purpose={"G1": "chốt ràng buộc", "G2": "duyệt tri thức"})
    ten = [p.name for p in lo.preconditions]
    assert any("G1" in t for t in ten) and any("G2" in t for t in ten)


def test_cung_khong_gate_KHONG_thanh_mot_chang_rieng():
    """Cung B→C tự chuyển sau khi G1 duyệt — liệt nó ra là bịa thêm một bước."""
    lo = analyse(module_id="drv_i2c",
                 state=_State(phase="A", gates={}, backlog=[_Muc("drv_i2c")]))
    assert not any("B → C" in p.name for p in lo.preconditions)
    g1 = next(p for p in lo.preconditions if "G1" in p.name)
    assert "tự đi tiếp B→C" in g1.detail


def test_gate_da_duyet_thi_dat():
    lo = analyse(module_id="drv_i2c",
                 state=_State(phase="A", gates={"G1": "approved"},
                              backlog=[_Muc("drv_i2c")]))
    assert next(p for p in lo.preconditions if "G1" in p.name).met is True
    assert next(p for p in lo.preconditions if "G2" in p.name).met is False


def test_moi_gate_deu_thuoc_ve_NGUOI_khong_ngoai_le():
    lo = analyse(module_id="drv_i2c",
                 state=_State(phase="A", gates={}, backlog=[_Muc("drv_i2c")]))
    for p in lo.preconditions:
        if "Gate" in p.name:
            assert p.who == NGUOI
            assert p.fix[:2] == ("gate", "approve")
            assert "bất biến trung tâm" in p.reason


def test_da_qua_pha_D_thi_noi_ro_khong_lui_duoc():
    lo = analyse(module_id="drv_i2c",
                 state=_State(phase="F", backlog=[_Muc("drv_i2c")]))
    p = lo.preconditions[1]
    assert p.met is False and p.who == NGUOI
    assert "không lùi pha được" in p.detail


def test_pha_khong_hop_le_thi_bao_ro():
    lo = analyse(module_id="drv_i2c", state=_State(phase="Z"))
    assert any("Pha dự án đọc được" in p.name and not p.met for p in lo.preconditions)


# ════════════════════════════ chặng: backlog ════════════════════════════


def test_module_chua_co_thi_agent_tu_them_duoc():
    lo = analyse(module_id="drv_moi", state=_State(backlog=[_Muc("drv_i2c")]))
    p = next(p for p in lo.preconditions if "backlog" in p.name)
    assert p.met is False
    assert p.who == AGENT
    assert p.fix == ("plan", "add", "drv_moi")
    assert "drv_i2c" in p.detail


def test_module_da_merge_thi_thuoc_ve_nguoi():
    lo = analyse(module_id="drv_i2c",
                 state=_State(backlog=[_Muc("drv_i2c", status="merged")]))
    p = next(p for p in lo.preconditions if "chưa merge" in p.name)
    assert p.met is False and p.who == NGUOI
    assert "phiên bản mã" in p.reason


# ════════════════════════════ chặng: xung đột ═══════════════════════════


@dataclass
class _XungDot:
    message: str = "drv_a và drv_b cùng dùng timer1"


def test_xung_dot_tai_nguyen_thuoc_ve_ky_su():
    lo = analyse(module_id="drv_i2c", state=_san_sang(), conflicts=[_XungDot()])
    p = next(p for p in lo.preconditions if "xung đột" in p.name)
    assert p.met is False and p.who == NGUOI
    assert "timer1" in p.detail
    assert "FR-KG-02" in p.reason


# ════════════════════════════ chặng: tri thức ═══════════════════════════


def test_thieu_tri_thuc_thi_agent_tu_di_tim_duoc():
    lo = analyse(module_id="drv_i2c", state=_san_sang(),
                 readiness_error="Thiếu thanh ghi X cho chế độ Y\ndòng hai")
    p = next(p for p in lo.preconditions if "tri thức" in p.name)
    assert p.met is False
    assert p.who == AGENT and p.fix == ("resolve", "drv_i2c")
    assert p.detail == "Thiếu thanh ghi X cho chế độ Y"


def test_het_ngan_sach_token_thuoc_ve_nguoi():
    lo = analyse(module_id="drv_i2c", state=_san_sang(),
                 budget_error="module đã tiêu hết phần token")
    p = next(p for p in lo.preconditions if "ngân sách" in p.name)
    assert p.met is False and p.who == NGUOI
    assert "duyệt lại tại G1" in p.reason


# ═══════════════════ ranh giới agent / người khi chạy ═══════════════════


def test_agent_steps_cat_o_chang_dau_tien_thuoc_ve_nguoi():
    """Chạy tiếp sau một chặng của người là làm việc trên giả định chưa có."""
    lo = analyse(module_id="drv_moi",
                 state=_State(phase="A", gates={}, backlog=[]))
    # Chặng đầu tiên bị chặn là gate G1 (người) → không có chặng nào tự lo được
    assert lo.agent_steps == []
    assert lo.first_human_step is not None and "G1" in lo.first_human_step.name


def test_agent_steps_gom_du_cac_chang_lien_tiep_thuoc_ve_agent():
    lo = analyse(module_id="drv_moi", state=_State(backlog=[]),
                 readiness_error="thiếu tri thức")
    # backlog (agent) rồi tri thức (agent) — cả hai đều tự lo được
    assert [p.fix[0] for p in lo.agent_steps] == ["plan", "resolve"]
    assert lo.first_human_step is None


def test_khong_chang_nao_thuoc_ve_agent_ma_lai_la_gate():
    """Một chặng 'người' không bao giờ tự chuyển thành 'agent' qua focus."""
    for state in (_State(phase="A", gates={}), _State(phase="C", gates={"G1": "approved"})):
        lo = analyse(module_id="drv_i2c", state=state)
        for p in lo.agent_steps:
            assert "gate" not in p.fix[0]


def test_ban_in_ra_noi_ro_ai_lam_gi():
    lo = analyse(module_id="drv_moi", state=_State(backlog=[]),
                 readiness_error="thiếu tri thức")
    ra = lo.render()
    assert "Tôi tự lo được ngay" in ra
    assert "eaa plan add drv_moi" in ra
    assert "--run" in ra


def test_ban_in_ra_dem_dung_so_chang():
    lo = analyse(module_id="drv_moi", state=_State(phase="A", gates={}, backlog=[]))
    ra = lo.render()
    assert f"Còn {len(lo.blocked_by)}/{len(lo.preconditions)} chặng" in ra


def test_ke_hoach_rong_van_render_duoc():
    assert "Để làm gì đó" in FocusPlan(target="làm gì đó").render()


def test_tien_dieu_kien_dat_khong_in_lenh_go():
    p = Precondition("xong rồi", DAT, fix=("plan", "add"))
    assert "→" not in p.render()
