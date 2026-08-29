"""TC-06, TC-09 và vòng lặp chuẩn 13 bước end-to-end.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-06 | Vòng tự sửa dừng đúng N | mock luôn trả mã hỏng → 3 vòng vá, thoát mã 3, log đủ 3 vòng |
| TC-09 | KPI ghi đúng và đủ | đủ cột, Tdev > 0, retries khớp thực tế, một dòng mỗi build |
| TC-01 | Gate không thể vượt | `eaa gen` khi G1 chưa duyệt bị từ chối |
| TC-02 | Reject có hệ quả đúng | không merge; lý do vào ledger; module quay lại todo |

**Cách đọc N = 3.** N là số vòng TỰ SỬA, không phải tổng số lần gọi mô hình.
Một module hỏng đến cùng có 1 lần sinh đầu + 3 lần vá = 4 lần gọi mô hình.
Cách đọc theo AIS §3.2 và FR-GEN-01; ghi rõ vì TC-06 chỉ nói "đúng 3 lần thử".

Định nghĩa hoàn thành Sprint 2 (MDD §6): "một module mock đi trọn vòng, merge
chỉ qua G3" — đó là `test_mot_module_di_tron_vong_lap_chuan` ở cuối tệp.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_REPAIR_LIMIT, EXIT_WAITING_GATE
from eaa.composer import ComposerConfig, PromptComposer
from eaa.gates import HumanGate
from eaa.graph import KnowledgeGraph
from eaa.kb import KnowledgeBase
from eaa.kpi import COLUMNS, KpiLogger
from eaa.ledger import ErrorLedger
from eaa.llm.mock import MockLLM
from eaa.orchestrator import (
    Orchestrator,
    OrchestratorConfig,
    PreconditionFailed,
)
from eaa.platform import load_manifest
from eaa.state import BacklogItem, ProjectState, StateStore
from eaa.tools.compile import CompileGate, SizeGate
from eaa.tools.runner import ToolRunner
from eaa.tools.static import StaticGate
from eaa.tools.unittests import UnitTestGate
from eaa.vcs import MERGE_GATE, GitRepo

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"


# --------------------------------------------------------------------------
# Mã mẫu mà MockLLM trả về
# --------------------------------------------------------------------------

MA_DAT = """```file:src/drv_bus_sensor.c
#include "drv_bus_sensor.h"

// ref: ds-021, tr.222
void drv_bus_sensor_init(void)
{
    static uint8_t trang_thai;
    trang_thai = 0u;
}
```

```file:src/drv_bus_sensor.h
#ifndef DRV_BUS_SENSOR_H
#define DRV_BUS_SENSOR_H
void drv_bus_sensor_init(void);
#endif
```
"""

MA_HONG_BIEN_DICH = """```file:src/drv_bus_sensor.c
#include "drv_bus_sensor.h"

void drv_bus_sensor_init(void)
{
    undeclared_helper(1);
}
```
"""

MA_VI_PHAM_RANG_BUOC = """```file:src/drv_bus_sensor.c
#include "drv_bus_sensor.h"
#include <stdlib.h>

void drv_bus_sensor_init(void)
{
    char *p = malloc(16);
    _delay_ms(100);
    free(p);
}
```
"""


# --------------------------------------------------------------------------
# Dựng một dự án đầy đủ
# --------------------------------------------------------------------------


class Duan:
    """Gói toàn bộ vật tư cần cho một lượt chạy vòng lặp chuẩn."""

    def __init__(self, tmp_path: Path, *, llm: MockLLM, phase: str = "D") -> None:
        self.root = tmp_path / "robot_balance"
        self.root.mkdir(parents=True)
        for ten in ("constraints.yaml", "hardware_profile.yaml"):
            (self.root / ten).write_text(
                (DU_AN_MAU / ten).read_text(encoding="utf-8"), encoding="utf-8"
            )
        ds = self.root / "datasheets"
        ds.mkdir()
        for p in (DU_AN_MAU / "datasheets").glob("*.md"):
            (ds / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        # Bộ kiểm thử đơn vị tối thiểu để cổng unittests có cái để chạy.
        tests = self.root / "tests"
        tests.mkdir()
        (tests / "test_smoke.py").write_text(
            "def test_khung_du_an():\n    assert True\n", encoding="utf-8"
        )

        self.kb = KnowledgeBase.load(self.root)
        self.graph = KnowledgeGraph.build(self.kb.hardware, self.kb.datasheets)
        self.ledger = ErrorLedger(self.root / "error_ledger.jsonl")
        self.kpi = KpiLogger(self.root / "kpi_log.csv", env_hash="sha256:env-test")
        self.composer = PromptComposer(
            self.kb, self.graph, self.ledger, ComposerConfig()
        )
        self.llm = llm

        self.store = StateStore(self.root / "project_state.json")
        self.store.save(
            ProjectState(
                phase=phase,
                gates={"G1": "approved", "G2": "approved", "G3": "pending"},
                backlog=[
                    BacklogItem(id="drv_bus_sensor", status="todo", uses=["twi", "imu"]),
                    BacklogItem(id="pid_controller", status="todo"),
                ],
                constraints_version=self.kb.constraints.content_version,
                llm={"provider": llm.provider, "model": llm.model},
            )
        )

        self.gates = HumanGate(self.root / "gates", self.store, self.ledger)

        self.firmware = self.root / "firmware"
        self.repo = GitRepo(self.firmware)
        self.repo.init()

        self.runner = ToolRunner(
            manifest=load_manifest(PACK_DEMO),
            work_dir=self.firmware,
            base_params={
                **self.kb.constraints.platform_params(),
                "python": sys.executable,
                "pack_dir": str(PACK_DEMO),
            },
        )
        self.chain = [
            CompileGate(self.runner),
            SizeGate(self.runner, limits=self.kb.constraints.limits),
            StaticGate(
                runner=self.runner,
                manifest=self.runner.manifest,
                forbidden=list(self.kb.constraints.forbidden),
                limits=self.kb.constraints.limits,
                registers=self.graph.registers_for("drv_bus_sensor"),
                allowed_chunk_ids=[c.id for c in self.kb.datasheets.active()],
            ),
            UnitTestGate(tests_dir=tests, work_dir=self.root),
        ]

        self.orch = Orchestrator(
            state_store=self.store,
            composer=self.composer,
            llm=self.llm,
            gates=self.gates,
            repo=self.repo,
            graph=self.graph,
            kpi=self.kpi,
            ledger=self.ledger,
            gate_chain=self.chain,
            config=OrchestratorConfig(actor="Vũ Trí Công"),
        )


@pytest.fixture()
def du_an_dat(tmp_path: Path) -> Duan:
    return Duan(tmp_path, llm=MockLLM(responses=MA_DAT))


@pytest.fixture()
def du_an_hong(tmp_path: Path) -> Duan:
    return Duan(tmp_path, llm=MockLLM(responses=MA_HONG_BIEN_DICH))


# --------------------------------------------------------------------------
# Tiền điều kiện — TC-01 gõ cửa đầu tiên ở đây
# --------------------------------------------------------------------------


def test_tc01_gen_khi_G1_chua_duyet_bi_tu_choi(tmp_path: Path) -> None:
    du_an = Duan(tmp_path, llm=MockLLM(responses=MA_DAT), phase="A")
    with du_an.store.with_lock():
        state = du_an.store.load()
        state.gates["G1"] = "pending"
        du_an.store.save(state)

    with pytest.raises(PreconditionFailed, match="G1"):
        du_an.orch.run_module("drv_bus_sensor")

    assert du_an.llm.call_count == 0, "không được gọi mô hình khi gate chưa mở"


def test_gen_o_pha_sai_bi_tu_choi(tmp_path: Path) -> None:
    du_an = Duan(tmp_path, llm=MockLLM(responses=MA_DAT), phase="B")
    with pytest.raises(PreconditionFailed, match="pha B"):
        du_an.orch.run_module("drv_bus_sensor")


def test_module_khong_co_trong_backlog_bi_tu_choi(du_an_dat: Duan) -> None:
    with pytest.raises(PreconditionFailed, match="không có trong backlog"):
        du_an_dat.orch.run_module("module_khong_ton_tai")


def test_chuoi_cong_khuyet_thi_khong_chay(du_an_dat: Duan) -> None:
    """Một cổng vắng mặt là một loại lỗi không được kiểm (FR-VER-01)."""
    du_an_dat.orch.gate_chain = du_an_dat.chain[:2]
    with pytest.raises(PreconditionFailed, match="thiếu cổng bắt buộc"):
        du_an_dat.orch.run_module("drv_bus_sensor")


def test_xung_dot_tai_nguyen_chan_truoc_khi_sinh_ma(du_an_dat: Duan) -> None:
    """FR-KG-02 shift-left: chặn ở giây thứ nhất, không phải trên thiết bị thật."""
    with du_an_dat.store.with_lock():
        state = du_an_dat.store.load()
        state.backlog.append(BacklogItem(id="kernel_tick", status="todo", uses=["timer1"]))
        state.backlog[0].uses = ["timer1"]
        du_an_dat.store.save(state)
    du_an_dat.graph.add_module("kernel_tick", uses=["timer1"])

    with pytest.raises(PreconditionFailed, match="Xung đột tài nguyên"):
        du_an_dat.orch.run_module("drv_bus_sensor")
    assert du_an_dat.llm.call_count == 0


# --------------------------------------------------------------------------
# TC-06 — vòng tự sửa dừng đúng N
# --------------------------------------------------------------------------


def test_tc06_ba_vong_tu_sua_roi_ban_giao_nguoi(du_an_hong: Duan) -> None:
    ket_qua = du_an_hong.orch.run_module("drv_bus_sensor")

    assert ket_qua.status == "handoff"
    assert ket_qua.exit_code == EXIT_REPAIR_LIMIT
    assert ket_qua.repairs == 3, "đúng 3 vòng tự sửa"
    # 1 lần sinh đầu + 3 lần vá.
    assert du_an_hong.llm.call_count == 4


def test_tc06_ban_giao_kem_log_du_ba_vong(du_an_hong: Duan) -> None:
    """Người cần thấy ba vòng hỏng khác nhau thế nào, không chỉ thấy 'hỏng'."""
    ket_qua = du_an_hong.orch.run_module("drv_bus_sensor")

    assert len(ket_qua.attempts_log) == 4  # lần sinh đầu + 3 vòng vá
    assert "sinh lần đầu" in ket_qua.attempts_log[0]
    for i in (1, 2, 3):
        assert f"vòng vá {i}" in ket_qua.attempts_log[i]
    assert "undeclared_helper" in ket_qua.message or "implicit declaration" in ket_qua.message


def test_tc06_state_ghi_dung_so_lan_da_thu(du_an_hong: Duan) -> None:
    du_an_hong.orch.run_module("drv_bus_sensor")
    muc = du_an_hong.store.load().module("drv_bus_sensor")
    assert muc.status == "handoff"
    assert muc.retries == 3


def test_so_vong_tu_sua_cau_hinh_duoc(tmp_path: Path) -> None:
    """FR-GEN-01: N cấu hình được, mặc định 3."""
    du_an = Duan(tmp_path, llm=MockLLM(responses=MA_HONG_BIEN_DICH))
    du_an.orch.config = OrchestratorConfig(max_repairs=1)

    ket_qua = du_an.orch.run_module("drv_bus_sensor")
    assert ket_qua.repairs == 1
    assert du_an.llm.call_count == 2


def test_sua_duoc_o_vong_thu_hai_thi_di_tiep(tmp_path: Path) -> None:
    du_an = Duan(
        tmp_path,
        llm=MockLLM(responses=[MA_HONG_BIEN_DICH, MA_HONG_BIEN_DICH, MA_DAT]),
    )
    ket_qua = du_an.orch.run_module("drv_bus_sensor")

    assert ket_qua.status == "awaiting_gate"
    assert ket_qua.repairs == 2
    assert ket_qua.exit_code == EXIT_WAITING_GATE


def test_vong_va_ghi_nhat_ky_loi(du_an_hong: Duan) -> None:
    du_an_hong.orch.run_module("drv_bus_sensor")
    muc = du_an_hong.ledger.entries()
    assert len(muc) == 3, "mỗi vòng vá ghi một mục"
    assert all(e.category == "tool_failure" for e in muc)


# --------------------------------------------------------------------------
# TC-07 trong ngữ cảnh vòng lặp — ràng buộc chặn tại static
# --------------------------------------------------------------------------


def test_ma_vi_pham_rang_buoc_khong_toi_duoc_buoc_commit(tmp_path: Path) -> None:
    du_an = Duan(tmp_path, llm=MockLLM(responses=MA_VI_PHAM_RANG_BUOC))
    ket_qua = du_an.orch.run_module("drv_bus_sensor")

    assert ket_qua.status == "handoff"
    cong_hong = [r.gate for r in ket_qua.reports if not r.passed]
    assert "static" in cong_hong
    assert du_an.gates.pending(MERGE_GATE) == [], "không được xin duyệt mã vi phạm"


def test_chuoi_cong_dung_o_cong_hong_dau_tien(du_an_hong: Duan) -> None:
    """Cổng sau ăn sản phẩm của cổng trước — chạy tiếp chỉ tạo lỗi dây chuyền."""
    ket_qua = du_an_hong.orch.run_module("drv_bus_sensor")
    assert [r.gate for r in ket_qua.reports] == ["compile"]


# --------------------------------------------------------------------------
# TC-09 — KPI ghi đúng và đủ
# --------------------------------------------------------------------------


def test_tc09_kpi_du_cot_va_dung_so_lieu(du_an_dat: Duan) -> None:
    du_an_dat.orch.run_module("drv_bus_sensor")
    dong = du_an_dat.kpi.rows()

    assert dong, "phải có dòng KPI"
    for r in dong:
        assert list(r.keys()) == list(COLUMNS), "mọi dòng phải đủ cột"

    su_kien = [r["event"] for r in dong]
    assert "generate" in su_kien
    assert "verify" in su_kien
    assert "gate_request" in su_kien

    # Một dòng verify cho mỗi cổng đã chạy.
    assert len([r for r in dong if r["event"] == "verify"]) == 4


def test_tc09_tdev_lon_hon_khong_va_retries_khop_thuc_te(tmp_path: Path) -> None:
    du_an = Duan(
        tmp_path, llm=MockLLM(responses=[MA_HONG_BIEN_DICH, MA_DAT])
    )
    du_an.orch.run_module("drv_bus_sensor")

    gate_request = [r for r in du_an.kpi.rows() if r["event"] == "gate_request"][0]
    assert float(gate_request["tdev_min"]) > 0
    assert int(gate_request["retries"]) == 1
    assert gate_request["llm_model"] == "mock-deterministic-1"
    assert gate_request["prompt_hash"].startswith("sha256:")


def test_tc09_kpi_mang_env_hash_va_ma_chunk(du_an_dat: Duan) -> None:
    """AIS §9.3: mỗi dòng KPI gắn env_hash để phát hiện trôi toolchain."""
    du_an_dat.orch.run_module("drv_bus_sensor")
    for r in du_an_dat.kpi.rows():
        assert r["env_hash"] == "sha256:env-test"


def test_tc09_so_lieu_kich_thuoc_di_vao_cot_dung(du_an_dat: Duan) -> None:
    du_an_dat.orch.run_module("drv_bus_sensor")
    dong_size = [r for r in du_an_dat.kpi.rows() if r["gate"] == "size"][0]
    assert float(dong_size["flash_bytes"]) > 0
    assert float(dong_size["flash_pct"]) > 0


def test_tong_hop_kpi_cho_bao_cao(du_an_dat: Duan) -> None:
    du_an_dat.orch.run_module("drv_bus_sensor")
    tom_tat = du_an_dat.kpi.summary()

    assert tom_tat["rows"] > 0
    assert tom_tat["modules"] == ["drv_bus_sensor"]
    assert tom_tat["tokens_in_total"] > 0
    assert tom_tat["models"] == ["mock-deterministic-1"]


def test_kpi_tu_choi_ghi_tiep_khi_luoc_do_doi(tmp_path: Path) -> None:
    """Số liệu đã thu không thu lại được — không trộn hai lược đồ trong một tệp."""
    from eaa.kpi import KpiError

    path = tmp_path / "kpi_log.csv"
    path.write_text("ts,module,cot_la\n", encoding="utf-8")
    with pytest.raises(KpiError, match="lược đồ khác"):
        KpiLogger(path).log(event="merge", module="m")


# --------------------------------------------------------------------------
# Bước 10 — dừng lại chờ người
# --------------------------------------------------------------------------


def test_vong_lap_dung_o_G3_va_thoat_ma_2(du_an_dat: Duan) -> None:
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")

    assert ket_qua.status == "awaiting_gate"
    assert ket_qua.exit_code == EXIT_WAITING_GATE
    assert "eaa gate approve G3" in ket_qua.message
    assert du_an_dat.store.load().module("drv_bus_sensor").status == "in_review"


def test_ho_so_gui_len_gate_kem_checklist_tu_do_thi(du_an_dat: Duan) -> None:
    """AIS §5.4: review từ đọc tự do thành đối chiếu có hệ thống."""
    du_an_dat.orch.run_module("drv_bus_sensor")
    yeu_cau = du_an_dat.gates.pending(MERGE_GATE)[0]

    assert yeu_cau.payload.checklist
    assert any("ds-021" in muc for muc in yeu_cau.payload.checklist)
    assert yeu_cau.payload.content_digest.startswith("sha256:")
    assert "diff --git" in yeu_cau.payload.details


def test_khong_tu_dong_merge_sau_khi_xin_gate(du_an_dat: Duan) -> None:
    """Không có chế độ nào nối liền bước 10 sang bước 11."""
    du_an_dat.orch.run_module("drv_bus_sensor")
    assert du_an_dat.repo.current_branch() == "feature/drv_bus_sensor"
    assert "feature/drv_bus_sensor" not in du_an_dat.repo._git(
        "log", "--oneline", "main"
    )


def test_finalize_khi_chua_co_quyet_dinh_thi_van_cho(du_an_dat: Duan) -> None:
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")
    lai = du_an_dat.orch.finalize_module("drv_bus_sensor", ket_qua.reports)

    assert lai.status == "awaiting_gate"
    assert lai.exit_code == EXIT_WAITING_GATE


# --------------------------------------------------------------------------
# TC-02 — reject có hệ quả đúng
# --------------------------------------------------------------------------


def test_tc02_tu_choi_thi_khong_merge_va_module_quay_lai_todo(du_an_dat: Duan) -> None:
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")
    du_an_dat.gates.reject(
        MERGE_GATE, actor="Vũ Trí Công", reason="thiếu kiểm mã trạng thái sau thao tác bus"
    )

    lai = du_an_dat.orch.finalize_module("drv_bus_sensor", ket_qua.reports)

    assert lai.status == "rejected"
    assert lai.exit_code != EXIT_OK
    assert du_an_dat.repo.current_branch() != "main" or "Merge" not in du_an_dat.repo.commit_message()
    assert du_an_dat.store.load().module("drv_bus_sensor").status == "todo"

    ly_do = [e for e in du_an_dat.ledger.entries() if e.category == "gate_rejection"]
    assert ly_do and "thiếu kiểm mã trạng thái" in ly_do[0].description


def test_tc02_ly_do_tu_choi_vao_prompt_lan_sinh_lai(du_an_dat: Duan) -> None:
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")
    du_an_dat.gates.reject(
        MERGE_GATE, actor="Vũ Trí Công", reason="thiếu kiểm mã trạng thái"
    )
    du_an_dat.orch.finalize_module("drv_bus_sensor", ket_qua.reports)

    task = du_an_dat.orch._dung_task(du_an_dat.store.load(), "drv_bus_sensor")
    prompt = du_an_dat.composer.build(task, du_an_dat.store.load())
    assert "thiếu kiểm mã trạng thái" in prompt.full_text()


# --------------------------------------------------------------------------
# Định nghĩa hoàn thành Sprint 2
# --------------------------------------------------------------------------


def test_mot_module_di_tron_vong_lap_chuan(du_an_dat: Duan) -> None:
    """DoD Sprint 2: một module mock đi trọn vòng, merge CHỈ qua G3."""
    # Bước 1–10.
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")
    assert ket_qua.status == "awaiting_gate"
    assert all(r.passed for r in ket_qua.reports)
    assert [r.gate for r in ket_qua.reports] == ["compile", "size", "static", "unittests"]

    # Bước 11 — con người quyết định. Đây là hành động DUY NHẤT mở đường merge.
    du_an_dat.gates.approve(MERGE_GATE, actor="Vũ Trí Công")

    # Bước 11–13.
    xong = du_an_dat.orch.finalize_module("drv_bus_sensor", ket_qua.reports)

    assert xong.status == "merged"
    assert xong.exit_code == EXIT_OK
    assert "pid_controller" in xong.message, "phải chỉ ra module kế tiếp (bước 13)"

    assert du_an_dat.repo.current_branch() == "main"
    assert (du_an_dat.firmware / "src" / "drv_bus_sensor.c").is_file()
    assert du_an_dat.store.load().module("drv_bus_sensor").status == "merged"

    # Commit merge mang bằng chứng: cổng nào đạt, ai duyệt.
    thong_diep = du_an_dat.repo.commit_message()
    assert "gate-decision: G3 approved by Vũ Trí Công" in thong_diep
    assert "compile, size, static, unittests" in thong_diep

    # Nhật ký quyết định — bằng chứng cho tiêu chí nghiệm thu STP-04 §5.
    quyet_dinh = du_an_dat.gates.decisions(MERGE_GATE)
    assert len(quyet_dinh) == 1 and quyet_dinh[0].approved

    # KPI đủ để dựng bảng Chương 3.
    su_kien = [r["event"] for r in du_an_dat.kpi.rows()]
    assert "merge" in su_kien and "gate_decision" in su_kien


def test_sua_ma_sau_khi_duyet_thi_merge_bi_chan(du_an_dat: Duan) -> None:
    """Duyệt xong rồi lén đổi mã — cả chuỗi neo băm phải chặn được.

    Có hai lớp cùng canh việc này: hàm dựng giấy phép (so băm người đã duyệt
    với băm nhánh hiện tại) và ``merge()`` (so lại lần nữa ngay trước khi hợp
    nhất). Lớp đầu bắt trước, nên thông điệp đến từ đó — test chấp nhận cả hai
    để không khóa cứng vào thứ tự nội bộ, nhưng vẫn đòi phải bị chặn.
    """
    ket_qua = du_an_dat.orch.run_module("drv_bus_sensor")
    du_an_dat.gates.approve(MERGE_GATE, actor="Vũ Trí Công")

    (du_an_dat.firmware / "src" / "len_them.c").write_text(
        "void bat_ngo(void) {}\n", encoding="utf-8"
    )
    du_an_dat.repo.commit_artifact(ket_qua.artifact, module_id="drv_bus_sensor")

    lai = du_an_dat.orch.finalize_module("drv_bus_sensor", ket_qua.reports)

    assert lai.status == "blocked"
    assert any(
        dau_hieu in lai.message
        for dau_hieu in ("không phải nội dung sắp merge", "đã thay đổi kể từ khi được duyệt")
    ), lai.message
    assert du_an_dat.repo.current_branch() == "feature/drv_bus_sensor"


def test_khong_merge_duoc_voi_bao_cao_cong_hong(du_an_dat: Duan) -> None:
    from eaa.tools.base import ToolError, ToolReport

    du_an_dat.orch.run_module("drv_bus_sensor")
    du_an_dat.gates.approve(MERGE_GATE, actor="Vũ Trí Công")

    lai = du_an_dat.orch.finalize_module(
        "drv_bus_sensor",
        [ToolReport(gate="compile", passed=False, errors=[ToolError("hỏng")])],
    )
    assert lai.status == "blocked"
    assert "chưa đạt" in lai.message
