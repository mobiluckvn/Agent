"""TC-53 — ngân sách tài nguyên và token chia theo module.

Nghiệp vụ N-015 (chia flash/RAM theo module), N-071 (khoảng trống ngăn xếp ở
tầm firmware), N-904 (trần token, chi phí, cảnh báo).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-53a | Bản chia tự mâu thuẫn bị bắt | tổng phần chia vượt dung lượng dùng được |
| TC-53b | Module ăn quá phần thì cổng kích thước KHÔNG đạt | không phải cảnh báo |
| TC-53c | Sắp chạm phần thì cảnh báo, còn kịp đổi hướng | ngưỡng ``warn_at_pct`` |
| TC-53d | Khoảng trống ngăn xếp là số liệu SUY RA và chỉ có ở tầm firmware | N-071 |
| TC-53e | Trần token theo module chặn TRƯỚC khi gọi mô hình | N-904, không cờ nào bỏ qua |
| TC-53f | Chi phí quy ra tiền từ đơn giá của DỰ ÁN | engine không ghim đơn giá |
| TC-53g | Đề xuất cách chia giải thích được | mỗi phần kèm trọng số đã dùng |

Điểm đáng chú ý là TC-53d. Ngưỡng ``stack_headroom_bytes`` nằm trong
``constraints.yaml`` của dự án mẫu từ Sprint 0 và **chưa bao giờ được thi
hành**: cổng kích thước chỉ áp quy ước ``_max``/``_min``, mà khóa ấy viết trần
trụi nên nó rơi qua khe. Một ngưỡng có khai mà không ai áp còn tệ hơn không
khai — nó tạo cảm giác đã kiểm.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eaa.budget import (
    SAP_CHAM,
    TRONG_PHAN,
    VUOT_PHAN,
    Allotment,
    BudgetError,
    DerivedMetric,
    ResourceBudget,
    TokenBudget,
    TokenUsage,
    propose_split,
    spent_tokens,
    weights_from_modules,
)
from eaa.kb import Constraints
from eaa.kpi import KpiLogger
from eaa.platform import load_manifest
from eaa.tools.compile import SCOPE_FIRMWARE, SCOPE_MODULE, SizeGate
from eaa.tools.runner import ToolRunner

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"


def _constraints(tmp_path: Path, khoi: str) -> Constraints:
    p = tmp_path / "constraints.yaml"
    p.write_text("version: 1\nplatform: demo\n" + khoi, encoding="utf-8")
    return Constraints.load(p)


@pytest.fixture()
def runner(tmp_path: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


@pytest.fixture()
def anh(tmp_path: Path) -> Path:
    p = tmp_path / "mod.o"
    p.write_bytes(b"x" * 64)
    return p


def _ngan_sach(**kw) -> ResourceBudget:
    kw.setdefault("capacity", {"flash_bytes": 32768, "sram_bytes": 2048})
    kw.setdefault("reserve_pct", 20.0)
    return ResourceBudget(**kw)


# --------------------------------------------------------------------------
# TC-53a — bản chia tự mâu thuẫn
# --------------------------------------------------------------------------


def test_tong_phan_chia_vuot_dung_luong_dung_duoc_bi_bat() -> None:
    """Cộng lại đã quá chỗ thì mọi module đều 'trong phần' mà firmware không nạp nổi."""
    ns = _ngan_sach(
        allotments=(
            Allotment("a", {"flash_bytes": 20000}),
            Allotment("b", {"flash_bytes": 20000}),
        )
    )
    van_de = ns.validate()
    assert len(van_de) == 1
    assert "vượt dung lượng dùng được" in van_de[0]
    assert "26,214" in van_de[0], "phải nói rõ mẫu số sau khi trừ dự phòng"


def test_ban_chia_vua_van_thi_khong_bao_gi() -> None:
    ns = _ngan_sach(
        allotments=(
            Allotment("a", {"flash_bytes": 13000}),
            Allotment("b", {"flash_bytes": 13000}),
        )
    )
    assert ns.validate() == []


def test_chia_phan_cho_so_lieu_chua_khai_dung_luong_la_van_de() -> None:
    ns = ResourceBudget(capacity={"flash_bytes": 100}, allotments=(Allotment("a", {"cpu_pct": 5}),))
    assert any("không đối chiếu được" in v for v in ns.validate())


def test_khai_phan_hai_lan_cho_mot_module_bi_bat() -> None:
    ns = _ngan_sach(
        allotments=(Allotment("a", {"flash_bytes": 100}), Allotment("a", {"flash_bytes": 200}))
    )
    assert any("hai lần" in v for v in ns.validate())


def test_khai_bao_sai_luoc_do_bi_bat_ngay_luc_nap(tmp_path: Path) -> None:
    with pytest.raises(BudgetError, match="số dương"):
        ResourceBudget.from_constraints(
            _constraints(tmp_path, "budget:\n  capacity:\n    flash_bytes: -1\n")
        )
    with pytest.raises(BudgetError, match="reserve_pct"):
        ResourceBudget.from_constraints(
            _constraints(tmp_path, "budget:\n  capacity:\n    f: 10\n  reserve_pct: 120\n")
        )
    with pytest.raises(BudgetError, match="derived"):
        ResourceBudget.from_constraints(
            _constraints(
                tmp_path,
                "budget:\n  capacity:\n    f: 10\n"
                "  derived:\n    h:\n      capacity: khong_co\n      used: f\n",
            )
        )


def test_khong_khai_budget_thi_tra_none_chu_khong_phai_loi(tmp_path: Path) -> None:
    """Dự án nhỏ chỉ cần trần tổng. Không khai KHÔNG phải lỗi."""
    assert ResourceBudget.from_constraints(_constraints(tmp_path, "")) is None
    assert TokenBudget.from_constraints(_constraints(tmp_path, "")) is None


# --------------------------------------------------------------------------
# TC-53b, TC-53c — cổng kích thước áp phần được chia
# --------------------------------------------------------------------------


def test_module_an_qua_phan_thi_cong_khong_dat(runner: ToolRunner, anh: Path) -> None:
    ns = _ngan_sach(allotments=(Allotment("drv_bus", {"flash_bytes": 10}),))
    bao_cao = SizeGate(runner, budget=ns, module="drv_bus").run(anh, scope=SCOPE_MODULE)

    assert not bao_cao.passed, "vượt phần là KHÔNG ĐẠT, không phải cảnh báo"
    assert any("vượt phần" in str(e) for e in bao_cao.errors)
    assert any("budget.modules" in str(e) for e in bao_cao.errors)


def test_module_trong_phan_thi_qua(runner: ToolRunner, anh: Path) -> None:
    ns = _ngan_sach(allotments=(Allotment("drv_bus", {"flash_bytes": 1_000_000}),))
    bao_cao = SizeGate(runner, budget=ns, module="drv_bus").run(anh, scope=SCOPE_MODULE)
    assert bao_cao.passed
    assert not bao_cao.warnings


def test_sap_cham_phan_thi_canh_bao_chu_khong_chan(runner: ToolRunner, anh: Path) -> None:
    """Cảnh báo có giá trị đúng ở chỗ nó còn kịp."""
    do_duoc = runner.run("size", {"binary": str(anh)}).metrics["flash_bytes"]
    ns = _ngan_sach(
        allotments=(Allotment("drv_bus", {"flash_bytes": do_duoc / 0.9}),),
        warn_at_pct=80.0,
    )
    bao_cao = SizeGate(runner, budget=ns, module="drv_bus").run(anh, scope=SCOPE_MODULE)

    assert bao_cao.passed, "sắp chạm thì vẫn đi tiếp được"
    assert any("Còn kịp đổi hướng" in str(w) for w in bao_cao.warnings)


def test_module_khong_duoc_chia_phan_thi_khong_bi_ap_gi(runner: ToolRunner, anh: Path) -> None:
    """Bản chia còn dở dang không được biến thành trần 0 cho các module còn lại."""
    ns = _ngan_sach(allotments=(Allotment("khac", {"flash_bytes": 10}),))
    bao_cao = SizeGate(runner, budget=ns, module="chua_chia").run(anh, scope=SCOPE_MODULE)
    assert bao_cao.passed


def test_khong_co_ngan_sach_thi_hanh_vi_y_nhu_truoc(runner: ToolRunner, anh: Path) -> None:
    assert SizeGate(runner).run(anh, scope=SCOPE_MODULE).passed


# --------------------------------------------------------------------------
# TC-53d — khoảng trống ngăn xếp (N-071)
# --------------------------------------------------------------------------


def test_khoang_trong_ngan_xep_duoc_suy_ra_o_tam_firmware(
    runner: ToolRunner, anh: Path
) -> None:
    do_duoc = runner.run("size", {"binary": str(anh)}).metrics["sram_bytes"]
    ns = _ngan_sach(
        derived=(DerivedMetric("stack_headroom_bytes", "sram_bytes", "sram_bytes"),)
    )
    bao_cao = SizeGate(runner, budget=ns).run(anh, scope=SCOPE_FIRMWARE)

    assert bao_cao.metrics["stack_headroom_bytes"] == 2048 - do_duoc


def test_khoang_trong_ngan_xep_KHONG_suy_o_tam_module(runner: ToolRunner, anh: Path) -> None:
    """Một module lẻ chưa biết những module khác sẽ ăn bao nhiêu.

    Suy ở tầm module sẽ cho một con số rộng rãi giả tạo, và một con số rộng rãi
    giả tạo là đúng loại số làm người ta yên tâm nhầm.
    """
    ns = _ngan_sach(
        derived=(DerivedMetric("stack_headroom_bytes", "sram_bytes", "sram_bytes"),)
    )
    bao_cao = SizeGate(runner, budget=ns).run(anh, scope=SCOPE_MODULE)
    assert "stack_headroom_bytes" not in bao_cao.metrics


def test_nguong_ngan_xep_thi_hanh_duoc_sau_khi_co_so_lieu_suy_ra(
    runner: ToolRunner, anh: Path
) -> None:
    """Đây là điều `stack_headroom_bytes` trong dự án mẫu chưa từng làm được."""
    ns = _ngan_sach(
        derived=(DerivedMetric("stack_headroom_bytes", "sram_bytes", "sram_bytes"),)
    )
    cong = SizeGate(
        runner, limits={"stack_headroom_bytes_min": 1_000_000}, budget=ns
    )
    bao_cao = cong.run(anh, scope=SCOPE_FIRMWARE)

    assert not bao_cao.passed
    assert any("stack_headroom_bytes" in str(e) and "dưới sàn" in str(e) for e in bao_cao.errors)


def test_du_an_mau_da_doi_khoa_sang_dang_thi_hanh_duoc() -> None:
    """Khóa cũ viết trần trụi rơi qua khe của quy ước `_max`/`_min`."""
    c = Constraints.load(REPO / "projects" / "robot_balance" / "constraints.yaml")
    assert "stack_headroom_bytes" not in c.limits, "khóa không đuôi = ngưỡng không ai áp"
    assert c.limits["stack_headroom_bytes_min"] == 128

    ns = ResourceBudget.from_constraints(c)
    assert ns is not None
    assert any(d.name == "stack_headroom_bytes" for d in ns.derived)


# --------------------------------------------------------------------------
# TC-53e, TC-53f — trần token và chi phí (N-904)
# --------------------------------------------------------------------------


def _kpi_voi_token(tmp_path: Path, module: str, *cap: tuple[int, int]) -> KpiLogger:
    kpi = KpiLogger(tmp_path / "kpi_log.csv")
    for vao, ra in cap:
        kpi.log(event="generate", module=module, tokens_in=vao, tokens_out=ra)
    return kpi


def test_cong_token_da_tieu_tu_nhat_ky_kpi(tmp_path: Path) -> None:
    kpi = _kpi_voi_token(tmp_path, "drv_bus", (1000, 300), (900, 200))
    dung = spent_tokens(kpi, "drv_bus")

    assert dung.tokens_in == 1900
    assert dung.tokens_out == 500
    assert dung.total == 2400
    assert dung.calls == 2


def test_dong_khong_co_token_khong_bi_dem_thanh_mot_luot(tmp_path: Path) -> None:
    kpi = _kpi_voi_token(tmp_path, "drv_bus", (1000, 300))
    kpi.log(event="merge", module="drv_bus", result="pass")
    assert spent_tokens(kpi, "drv_bus").calls == 1


def test_vuot_tran_thi_bao_vuot_va_noi_ro_loi_ra(tmp_path: Path) -> None:
    tran = TokenBudget(per_module=1000)
    kiem = tran.check(TokenUsage("drv_bus", tokens_in=900, tokens_out=200))

    assert kiem.status == VUOT_PHAN and kiem.blocked
    van_ban = kiem.render()
    assert "ĐÃ VƯỢT TRẦN" in van_ban
    assert "eaa resolve drv_bus" in van_ban, "phải chỉ nguyên nhân thường gặp"
    assert "G1" in van_ban, "nới trần phải đi qua gate, không qua cờ dòng lệnh"


def test_sap_cham_tran_thi_bao_som(tmp_path: Path) -> None:
    kiem = TokenBudget(per_module=1000, warn_at_pct=80).check(
        TokenUsage("drv_bus", tokens_in=850)
    )
    assert kiem.status == SAP_CHAM and not kiem.blocked
    assert "Sắp chạm trần" in kiem.render()


def test_khong_khai_tran_thi_khong_chan_ai() -> None:
    kiem = TokenBudget().check(TokenUsage("drv_bus", tokens_in=10**9))
    assert kiem.status == TRONG_PHAN and not kiem.blocked
    assert "chưa khai trần" in kiem.render()


def test_chi_phi_quy_tu_don_gia_cua_du_an() -> None:
    tran = TokenBudget(
        per_module=10_000, price_in_per_mtok=1.25, price_out_per_mtok=10.0, currency="USD"
    )
    assert tran.cost(1_000_000, 100_000) == pytest.approx(1.25 + 1.0)
    assert "USD" in tran.check(TokenUsage("m", 1000, 100)).render()


def test_chua_khai_don_gia_thi_khong_gia_vo_la_mien_phi() -> None:
    kiem = TokenBudget(per_module=10_000).check(TokenUsage("m", 1000, 100))
    assert kiem.cost == 0.0
    assert not kiem.currency
    assert "USD" not in kiem.render()


def test_engine_khong_ghim_don_gia_nao() -> None:
    """Đơn giá phụ thuộc mô hình và hợp đồng — hai thứ engine không được biết."""
    ma = (REPO / "eaa" / "budget.py").read_text(encoding="utf-8")
    assert "price_in_per_mtok: float = 0.0" in ma
    for so in ("1.25", "10.0 ", "USD"):
        assert f'= "{so}"' not in ma


def test_orchestrator_chan_truoc_khi_goi_mo_hinh(tmp_path: Path) -> None:
    """Trần chỉ kiểm sau khi gọi thì không phải trần."""
    from eaa.orchestrator import Orchestrator

    kpi = _kpi_voi_token(tmp_path, "drv_bus", (5000, 1000))

    class _LlmNo:
        def count_tokens(self, text: str) -> int:  # pragma: no cover - không được gọi
            raise AssertionError("đã vượt trần thì không được chạm tới mô hình")

    class _StoreGia:
        path = tmp_path / "project_state.json"

        def load(self):
            raise AssertionError("chặn phải xảy ra trước khi đọc trạng thái sâu hơn")

    orch = Orchestrator(
        state_store=_StoreGia(),
        composer=None,
        llm=_LlmNo(),
        gates=None,
        repo=None,
        graph=None,
        kpi=kpi,
        token_budget=TokenBudget(per_module=1000),
    )
    ket = orch._kiem_tran_token("drv_bus")

    assert ket is not None
    assert ket.status == "handoff"
    assert "ĐÃ VƯỢT TRẦN" in ket.message
    assert any(
        r["event"] == "handoff" and r["note"] == "vượt trần token theo module"
        for r in kpi.rows()
    ), "lần bị chặn phải vào KPI — không đo thì không tối ưu được"


class _StoreTrong:
    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "project_state.json"


def test_chua_vuot_tran_thi_khong_chan(tmp_path: Path) -> None:
    from eaa.orchestrator import Orchestrator

    orch = Orchestrator(
        state_store=_StoreTrong(tmp_path),
        composer=None,
        llm=None,
        gates=None,
        repo=None,
        graph=None,
        kpi=_kpi_voi_token(tmp_path, "drv_bus", (10, 5)),
        token_budget=TokenBudget(per_module=100_000),
    )
    assert orch._kiem_tran_token("drv_bus") is None


# --------------------------------------------------------------------------
# TC-53g — đề xuất cách chia
# --------------------------------------------------------------------------


class _MucBacklog:
    def __init__(self, ma: str, uses: tuple[str, ...] = (), scheduled: bool = False):
        self.id = ma
        self.uses = uses
        self.scheduled = scheduled


def test_de_xuat_chia_theo_trong_so_doc_duoc_tu_backlog() -> None:
    modules = [
        _MucBacklog("drv_bus", uses=("twi", "timer1"), scheduled=True),
        _MucBacklog("lib_toan", uses=()),
    ]
    de_xuat = propose_split(
        weights_from_modules(modules),
        {"flash_bytes": 32768},
        metrics=["flash_bytes"],
        reserve_pct=20.0,
    )

    phan = {a.module: a.limits["flash_bytes"] for a in de_xuat.allotments}
    assert phan["drv_bus"] > phan["lib_toan"], "module dùng nhiều tài nguyên hơn thì phần lớn hơn"
    assert sum(phan.values()) <= 32768 * 0.8 + 1
    assert de_xuat.validate() == []


def test_moi_phan_kem_can_cu_de_nguoi_sua_duoc() -> None:
    de_xuat = propose_split(
        [("a", 2.0), ("b", 1.0)], {"flash_bytes": 1000}, metrics=["flash_bytes"]
    )
    assert all("trọng số" in a.note for a in de_xuat.allotments)


def test_de_xuat_khong_co_module_hoac_khong_co_mau_so_thi_dung() -> None:
    with pytest.raises(BudgetError, match="Không có module"):
        propose_split([], {"f": 10}, metrics=["f"])
    with pytest.raises(BudgetError, match="mẫu số"):
        propose_split([("a", 1.0)], {}, metrics=["f"])
    with pytest.raises(BudgetError, match="trọng số"):
        propose_split([("a", 0.0)], {"f": 10}, metrics=["f"])


def test_khoi_yaml_dung_lai_duoc_de_chep_vao_constraints() -> None:
    de_xuat = propose_split(
        [("a", 1.0)],
        {"flash_bytes": 1000},
        metrics=["flash_bytes"],
        derived=(DerivedMetric("h", "flash_bytes", "flash_bytes"),),
    )
    khoi = de_xuat.to_yaml_block()
    assert khoi["modules"]["a"]["flash_bytes"] == 800
    assert khoi["derived"]["h"] == {"capacity": "flash_bytes", "used": "flash_bytes"}


# --------------------------------------------------------------------------
# Ranh giới engine
# --------------------------------------------------------------------------


def test_engine_khong_biet_flash_hay_sram_nghia_la_gi() -> None:
    """Tên số liệu do pack đặt, dung lượng do dự án khai. Engine chỉ cộng và so."""
    ma = (REPO / "eaa" / "budget.py").read_text(encoding="utf-8")
    for ten in ("flash_bytes", "sram_bytes", "stack_headroom"):
        assert f'"{ten}"' not in ma, f"{ten} bị ghim trong engine"
