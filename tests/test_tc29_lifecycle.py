"""TC-29 — vòng đời tri thức và tập lỗi thời.

TC-29 (AIS §11): "Deprecate một chunk đang được 2 module trích dẫn → Stale set
liệt kê đúng 2 module đó; cả hai bị hạ tin cậy và buộc re-verify; module không
liên quan không bị đụng."

Câu cuối là phần dễ làm hỏng nhất. Một tập lỗi thời quá rộng cũng vô dụng như
một tập quá hẹp: nếu mọi thay đổi tri thức đều bắt kiểm chứng lại toàn bộ dự
án thì chẳng ai chạy nó, và cơ chế trở thành hình thức.

Ba đường truy vấn ngược (đồ thị · trích dẫn trong mã · dấu vết commit) được
kiểm riêng từng đường, vì mỗi đường bắt một loại lệ mà hai đường kia bỏ sót.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from eaa.gates import APPROVED, REJECTED, GateDecision
from eaa.graph import KnowledgeGraph
from eaa.kb import ACTIVE, DEPRECATED, DatasheetStore, HardwareProfile
from eaa.ledger import ErrorLedger
from eaa.lifecycle import (
    KNOWLEDGE_GATE,
    STALE_STATUS,
    KnowledgeLifecycle,
    LifecycleError,
    SupersedeNotAuthorized,
)
from eaa.state import BacklogItem, ProjectState, StateStore
from eaa.vcs import GitRepo

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"


def _quyet_dinh(gate: str = KNOWLEDGE_GATE, decision: str = APPROVED) -> GateDecision:
    return GateDecision(
        gate_id=gate,
        decision=decision,
        actor="Vũ Trí Công",
        decided_at="2026-08-29T12:00:00+00:00",
        payload_digest="sha256:payload",
        content_digest="sha256:kho",
        reason="" if decision == APPROVED else "chưa đối chiếu xong",
    )


CHUNK_THAY_THE = """\
---
id: ds-021b
device: atmega328p
peripheral: twi
registers: [TWBR, TWSR, TWCR]
topic: Cấu hình tốc độ bit bus hai dây — bản sửa
source: ATmega328P datasheet rev. DS40002061B, tr.222-224
status: proposed
---

## TWI — tốc độ bit (bản đã đối chiếu lại)

Công thức: `f_SCL = f_CPU / (16 + 2 × TWBR × 4^TWPS)`.
Với f_CPU = 16 MHz, TWPS = 0, f_SCL = 400 kHz → TWBR = 12.

Bản trước ghi nhầm điều kiện tối thiểu của TWBR.
"""


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    project = tmp_path / "du_an"
    project.mkdir()
    shutil.copytree(DU_AN_MAU / "datasheets", project / "datasheets")
    shutil.copy(DU_AN_MAU / "hardware_profile.yaml", project / "hardware_profile.yaml")
    (project / "datasheets" / "twi_bitrate_v2.md").write_text(
        CHUNK_THAY_THE, encoding="utf-8"
    )

    # Hai module trích dẫn ds-021, một module hoàn toàn không liên quan.
    src = project / "firmware" / "src"
    src.mkdir(parents=True)
    (src / "drv_bus_sensor.c").write_text(
        textwrap.dedent(
            """\
            #include "drv_bus_sensor.h"
            // ref: ds-021, tr.222
            void drv_bus_sensor_init(void) { TWBR = 12u; }
            """
        ),
        encoding="utf-8",
    )
    (src / "drv_bus_eeprom.c").write_text(
        textwrap.dedent(
            """\
            #include "drv_bus_eeprom.h"
            // ref: ds-021
            void drv_bus_eeprom_init(void) { TWBR = 12u; }
            """
        ),
        encoding="utf-8",
    )
    (src / "pid_controller.c").write_text(
        "// Không chạm bus, không trích dẫn gì.\nvoid pid_step(void) {}\n",
        encoding="utf-8",
    )
    return project


@pytest.fixture()
def store(du_an: Path) -> StateStore:
    s = StateStore(du_an / "project_state.json")
    s.save(
        ProjectState(
            phase="D",
            gates={"G1": ACTIVE, "G2": ACTIVE},
            backlog=[
                BacklogItem(id="drv_bus_sensor", status="merged", uses=["twi", "imu"]),
                BacklogItem(id="drv_bus_eeprom", status="merged", uses=["twi"]),
                BacklogItem(id="pid_controller", status="merged"),
                BacklogItem(id="kernel_tick", status="merged", uses=["timer1"]),
            ],
        )
    )
    return s


@pytest.fixture()
def vong_doi(du_an: Path, store: StateStore) -> KnowledgeLifecycle:
    kho = DatasheetStore(du_an / "datasheets")
    ho_so = HardwareProfile.load(du_an / "hardware_profile.yaml")
    graph = KnowledgeGraph.build(ho_so, kho, modules=store.load().backlog)
    return KnowledgeLifecycle(
        datasheets=kho,
        graph=graph,
        state_store=store,
        firmware_dir=du_an / "firmware",
        ledger=ErrorLedger(du_an / "error_ledger.jsonl"),
    )


# --------------------------------------------------------------------------
# TC-29 — kịch bản chính
# --------------------------------------------------------------------------


def test_tc29_stale_set_liet_ke_dung_hai_module_trich_dan(
    vong_doi: KnowledgeLifecycle,
) -> None:
    tap = vong_doi.deprecate(
        "ds-021", reason="ghi nhầm điều kiện tối thiểu", decision=_quyet_dinh()
    )

    assert tap.module_ids == ["drv_bus_eeprom", "drv_bus_sensor"]
    assert "pid_controller" not in tap.module_ids, "module không liên quan bị đụng"
    assert "kernel_tick" not in tap.module_ids


def test_tc29_ca_hai_module_bi_ha_tin_cay_va_buoc_re_verify(
    vong_doi: KnowledgeLifecycle, store: StateStore
) -> None:
    tap = vong_doi.deprecate("ds-021", reason="sai", decision=_quyet_dinh())
    da_doi = vong_doi.apply(tap)

    assert sorted(da_doi) == ["drv_bus_eeprom", "drv_bus_sensor"]
    state = store.load()
    assert state.module("drv_bus_sensor").status == STALE_STATUS
    assert state.module("drv_bus_eeprom").status == STALE_STATUS
    # Module không liên quan giữ nguyên nhãn đã kiểm chứng.
    assert state.module("pid_controller").status == "merged"
    assert state.module("kernel_tick").status == "merged"


def test_tc29_bao_cao_neu_ro_bang_chung_cho_tung_module(
    vong_doi: KnowledgeLifecycle,
) -> None:
    """Kỹ sư phải biết VÌ SAO một module bị lôi vào, nếu không sẽ bỏ qua cả tập."""
    tap = vong_doi.deprecate("ds-021", reason="sai", decision=_quyet_dinh())
    van_ban = tap.render()

    assert "drv_bus_sensor" in van_ban and "drv_bus_eeprom" in van_ban
    assert "trích dẫn trong mã" in van_ban
    assert "drv_bus_sensor.c:2" in van_ban
    assert "chạy lại chuỗi kiểm chứng" in van_ban


def test_chunk_khong_module_nao_dung_thi_stale_set_rong(
    vong_doi: KnowledgeLifecycle,
) -> None:
    tap = vong_doi.deprecate("ds-041", reason="không dùng nữa", decision=_quyet_dinh())
    assert not tap
    assert "Không module nào" in tap.render()


# --------------------------------------------------------------------------
# Ba đường truy vấn ngược — mỗi đường bắt một loại lệ
# --------------------------------------------------------------------------


def test_duong_do_thi_bat_module_qua_quan_he_tai_nguyen(
    vong_doi: KnowledgeLifecycle,
) -> None:
    qua_do_thi = vong_doi.modules_from_graph("ds-021")
    assert set(qua_do_thi) == {"drv_bus_sensor", "drv_bus_eeprom"}
    assert all("đồ thị" in v for v in qua_do_thi.values())


def test_duong_trich_dan_bat_module_do_thi_khong_noi_toi(
    du_an: Path, store: StateStore, vong_doi: KnowledgeLifecycle
) -> None:
    """Module quên khai báo `uses` thì đồ thị không nối tới — trích dẫn vẫn bắt được."""
    with store.with_lock():
        state = store.load()
        state.backlog.append(BacklogItem(id="drv_quen_khai_bao", status="merged"))
        store.save(state)
    (du_an / "firmware" / "src" / "drv_quen_khai_bao.c").write_text(
        "// ref: ds-021\nvoid f(void) {}\n", encoding="utf-8"
    )

    qua_trich_dan = vong_doi.modules_from_citations("ds-021")
    assert "drv_quen_khai_bao" in qua_trich_dan
    assert "drv_quen_khai_bao" not in vong_doi.modules_from_graph("ds-021")

    tap = vong_doi.stale_set("ds-021")
    assert "drv_quen_khai_bao" in tap.module_ids


def test_duong_commit_bat_module_khong_trich_dan_gi(
    du_an: Path, store: StateStore, vong_doi: KnowledgeLifecycle
) -> None:
    """Chunk đã vào prompt nhưng mã sinh ra không trích dẫn nó ở đâu.

    Module ấy càng đáng ngờ chứ không phải ít đáng ngờ hơn — nó vừa dựa trên
    tri thức đã đổi, vừa bỏ sót nghĩa vụ trích dẫn.
    """
    repo = GitRepo(du_an / "firmware")
    repo.init()
    (du_an / "firmware" / "src" / "drv_im_lang.c").write_text(
        "void im_lang(void) {}\n", encoding="utf-8"
    )
    repo._git("add", "-A")
    repo._git(
        "commit", "-q", "-m", "drv_im_lang: mã sinh bởi quy trình AIDD",
        "-m", "chunk-ids: ds-021,ds-022\nmodel: mock-deterministic-1",
    )
    with store.with_lock():
        state = store.load()
        state.backlog.append(BacklogItem(id="drv_im_lang", status="merged"))
        store.save(state)

    vong_doi.repo = repo
    qua_commit = vong_doi.modules_from_commits("ds-021")
    assert "drv_im_lang" in qua_commit
    assert "drv_im_lang" not in vong_doi.modules_from_citations("ds-021")
    assert "drv_im_lang" in vong_doi.stale_set("ds-021").module_ids


def test_ten_module_dai_khong_bi_ten_ngan_nuot_mat(
    du_an: Path, store: StateStore, vong_doi: KnowledgeLifecycle
) -> None:
    """`drv_bus` không được nuốt mất `drv_bus_sensor` khi suy module từ tên tệp."""
    with store.with_lock():
        state = store.load()
        state.backlog.append(BacklogItem(id="drv_bus", status="merged"))
        store.save(state)

    qua_trich_dan = vong_doi.modules_from_citations("ds-021")
    assert "drv_bus_sensor" in qua_trich_dan
    assert "drv_bus" not in qua_trich_dan


# --------------------------------------------------------------------------
# Thay thế phải qua gate, và không bao giờ xóa
# --------------------------------------------------------------------------


def test_thay_the_khi_chua_co_phe_duyet_bi_tu_choi(vong_doi: KnowledgeLifecycle) -> None:
    with pytest.raises(SupersedeNotAuthorized, match="chưa có phê duyệt"):
        vong_doi.supersede("ds-021", "ds-021b", reason="sửa", decision=None)


@pytest.mark.parametrize("gate_khac", ["G1", "G3", "G4", "G5"])
def test_duyet_gate_khac_khong_thay_the_duoc_tri_thuc(
    vong_doi: KnowledgeLifecycle, gate_khac: str
) -> None:
    with pytest.raises(SupersedeNotAuthorized, match="cần quyết định tại G2"):
        vong_doi.supersede(
            "ds-021", "ds-021b", reason="sửa", decision=_quyet_dinh(gate=gate_khac)
        )


def test_gate_tu_choi_thi_khong_thay_the_duoc(vong_doi: KnowledgeLifecycle) -> None:
    with pytest.raises(SupersedeNotAuthorized, match="rejected"):
        vong_doi.supersede(
            "ds-021", "ds-021b", reason="sửa", decision=_quyet_dinh(decision=REJECTED)
        )


def test_thay_the_hop_le_chuyen_trang_thai_dung_hai_ben(
    du_an: Path, vong_doi: KnowledgeLifecycle
) -> None:
    tap = vong_doi.supersede(
        "ds-021", "ds-021b", reason="ghi nhầm điều kiện tối thiểu", decision=_quyet_dinh()
    )

    kho = DatasheetStore(du_an / "datasheets")
    cu = kho.get("ds-021", include_inactive=True)
    moi = kho.get("ds-021b")

    assert cu.status == DEPRECATED
    assert cu.superseded_by == "ds-021b"
    assert moi.status == ACTIVE
    assert moi.supersedes == "ds-021"
    assert tap.module_ids == ["drv_bus_eeprom", "drv_bus_sensor"]


def test_thay_the_KHONG_lam_doi_mot_byte_noi_dung_nao(
    du_an: Path, vong_doi: KnowledgeLifecycle
) -> None:
    """FR-RAG-01: chunk sau khi duyệt là bất biến về NỘI DUNG.

    Trạng thái vòng đời phải chuyển được — không thì chẳng có cách nào đánh dấu
    một trích đoạn đã sai. Nhưng phần thân, thứ được trích dẫn và đối chiếu
    từng bit, thì không ai được phép viết lại.
    """
    duong_dan = DatasheetStore(du_an / "datasheets").get("ds-021").path
    than_truoc = duong_dan.read_text(encoding="utf-8").split("---", 2)[2]

    vong_doi.supersede("ds-021", "ds-021b", reason="sửa", decision=_quyet_dinh())

    than_sau = duong_dan.read_text(encoding="utf-8").split("---", 2)[2]
    assert than_sau == than_truoc


def test_khong_thay_the_hai_lan(vong_doi: KnowledgeLifecycle) -> None:
    vong_doi.supersede("ds-021", "ds-021b", reason="sửa", decision=_quyet_dinh())
    with pytest.raises(LifecycleError, match="đã ở trạng thái deprecated"):
        vong_doi.supersede("ds-021", "ds-022", reason="sửa nữa", decision=_quyet_dinh())


def test_chunk_khong_tu_thay_the_chinh_no(vong_doi: KnowledgeLifecycle) -> None:
    with pytest.raises(LifecycleError, match="tự thay thế chính nó"):
        vong_doi.supersede("ds-021", "ds-021", reason="x", decision=_quyet_dinh())


def test_sau_khi_thay_the_truy_xuat_chi_thay_ban_moi(
    du_an: Path, vong_doi: KnowledgeLifecycle
) -> None:
    vong_doi.supersede("ds-021", "ds-021b", reason="sửa", decision=_quyet_dinh())

    kho = DatasheetStore(du_an / "datasheets")
    assert [c.id for c in kho.by_register("TWBR")] == ["ds-021b"]
    # Bản cũ vẫn tra được để đối chứng — không xóa bao giờ.
    assert kho.get("ds-021", include_inactive=True).status == DEPRECATED


def test_thay_the_ghi_vao_error_ledger(du_an: Path, vong_doi: KnowledgeLifecycle) -> None:
    vong_doi.supersede(
        "ds-021", "ds-021b", reason="chunk sai điều kiện tối thiểu", decision=_quyet_dinh()
    )
    muc = ErrorLedger(du_an / "error_ledger.jsonl").entries()
    assert muc and "ds-021" in muc[0].description and "ds-021b" in muc[0].description


# --------------------------------------------------------------------------
# Áp tập lỗi thời
# --------------------------------------------------------------------------


def test_ap_hai_lan_khong_lam_gi_them(vong_doi: KnowledgeLifecycle) -> None:
    tap = vong_doi.deprecate("ds-021", reason="sai", decision=_quyet_dinh())
    assert len(vong_doi.apply(tap)) == 2
    assert vong_doi.apply(tap) == [], "áp lại lần hai không được đổi gì"


def test_ap_tap_rong_khong_dung_toi_state(
    vong_doi: KnowledgeLifecycle, store: StateStore
) -> None:
    truoc = store.load().updated_at
    tap = vong_doi.deprecate("ds-041", reason="x", decision=_quyet_dinh())
    assert vong_doi.apply(tap) == []
    assert store.load().updated_at == truoc


def test_khong_tu_mo_vong_sinh_lai(vong_doi: KnowledgeLifecycle, store: StateStore) -> None:
    """Máy đánh dấu; quyết định sinh lại hay sửa tay thuộc về kỹ sư."""
    tap = vong_doi.deprecate("ds-021", reason="sai", decision=_quyet_dinh())
    vong_doi.apply(tap)
    for muc in store.load().backlog:
        assert muc.status != "in_gen", "engine tự mở vòng sinh lại"
