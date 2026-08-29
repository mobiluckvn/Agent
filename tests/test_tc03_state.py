"""TC-03 — Project State bền qua crash (FR-ORC-02, NFR-02).

Kịch bản EAA-STP-04: "Kill tiến trình giữa vòng lặp; chạy eaa resume →
Trạng thái, backlog, retries khôi phục đúng; không hỏng file."

Ba lớp kiểm chứng, từ tất định tới thực chiến:

1.  Vòng đời dữ liệu — ghi rồi đọc lại phải giữ nguyên phase, gates, backlog,
    retries, constraints_version (không mất, không đổi kiểu).
2.  Nguyên tử có mô phỏng sự cố — ép hỏng ĐÚNG vào khe giữa "ghi file tạm" và
    "đổi tên": file cũ phải còn nguyên vẹn. Đây là bằng chứng tất định cho
    NFR-02, không phụ thuộc may rủi về thời điểm.
3.  Kill -9 thật — tiến trình con ghi state liên tục, bị giết ở thời điểm ngẫu
    nhiên; file trên đĩa luôn phải là JSON hợp lệ và resume được.

Lý do phải có cả (3) dù đã có (2): (2) chứng minh thiết kế đúng, (3) chứng minh
hiện thực đúng trên hệ điều hành thật — đây là loại lỗi chỉ lộ ra khi hệ điều
hành, chứ không phải Python, quyết định lúc nào tiến trình chết.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from eaa.state import (
    BacklogItem,
    ProjectState,
    StateCorruptError,
    StateLockTimeout,
    StateStore,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Trợ giúp
# --------------------------------------------------------------------------


def _state_mau() -> ProjectState:
    """State mẫu theo đúng lược đồ EAA-SDD-03 §3.2."""
    return ProjectState(
        phase="D",
        gates={"G1": "approved", "G2": "approved", "G3": "pending"},
        backlog=[
            BacklogItem(id="drv_bus_sensor", status="in_verify", retries=1),
            BacklogItem(id="kernel_scheduler", status="todo", retries=0),
        ],
        constraints_version="sha256:ab12cd34",
        llm={"provider": "mock", "model": "mock-deterministic-1"},
    )


@pytest.fixture()
def store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "project_state.json")


# --------------------------------------------------------------------------
# Lớp 1 — vòng đời dữ liệu
# --------------------------------------------------------------------------


def test_ghi_roi_doc_lai_giu_nguyen_moi_truong(store: StateStore) -> None:
    goc = _state_mau()
    store.save(goc)

    lai = store.load()

    assert lai.phase == "D"
    assert lai.gates == {"G1": "approved", "G2": "approved", "G3": "pending"}
    assert lai.constraints_version == "sha256:ab12cd34"
    assert lai.llm == {"provider": "mock", "model": "mock-deterministic-1"}
    assert [m.id for m in lai.backlog] == ["drv_bus_sensor", "kernel_scheduler"]
    assert lai.backlog[0].status == "in_verify"
    # retries phải là số nguyên, không phải chuỗi — vòng tự sửa so sánh với N=3.
    assert lai.backlog[0].retries == 1
    assert isinstance(lai.backlog[0].retries, int)
    assert lai.backlog[1].retries == 0


def test_moi_lan_ghi_deu_dong_dau_thoi_gian(store: StateStore) -> None:
    """"Mỗi thay đổi kèm timestamp phục vụ đo Tdev" — EAA-SDD-03 §3.2."""
    state = _state_mau()
    store.save(state)
    lan_dau = store.load().updated_at
    assert lan_dau, "state phải mang updated_at sau khi ghi"

    time.sleep(0.01)
    state.phase = "E"
    store.save(state)
    lan_sau = store.load().updated_at

    assert lan_sau > lan_dau, "updated_at phải tiến lên sau mỗi lần ghi"
    assert store.load().created_at == store.load().created_at  # ổn định


def test_file_state_la_json_nguoi_doc_duoc(store: StateStore) -> None:
    """ADR-06: dữ liệu file phẳng, truy vết bằng công cụ chuẩn (git diff)."""
    store.save(_state_mau())
    raw = store.path.read_text(encoding="utf-8")

    du_lieu = json.loads(raw)
    assert du_lieu["phase"] == "D"
    assert raw.endswith("\n"), "kết thúc bằng newline để git diff sạch"
    assert "\n  " in raw, "phải xuống dòng thụt lề, không dồn một dòng"


def test_load_khi_chua_co_file_bao_loi_ro_rang(store: StateStore) -> None:
    with pytest.raises(FileNotFoundError):
        store.load()


def test_file_json_hong_bao_StateCorruptError_khong_nuot_am_tham(
    store: StateStore,
) -> None:
    store.path.write_text("{ đây không phải json", encoding="utf-8")
    with pytest.raises(StateCorruptError):
        store.load()


# --------------------------------------------------------------------------
# Lớp 2 — nguyên tử, mô phỏng sự cố tất định
# --------------------------------------------------------------------------


def test_hong_giua_chung_khong_lam_mat_state_cu(
    store: StateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ép sự cố vào khe giữa ghi file tạm và đổi tên."""
    store.save(_state_mau())
    truoc = store.path.read_bytes()

    state_moi = _state_mau()
    state_moi.phase = "F"
    state_moi.backlog[0].retries = 99

    def replace_hong(*args: object, **kwargs: object) -> None:
        raise OSError("mô phỏng mất điện đúng lúc đổi tên")

    monkeypatch.setattr(os, "replace", replace_hong)
    with pytest.raises(OSError):
        store.save(state_moi)
    monkeypatch.undo()

    assert store.path.read_bytes() == truoc, "state cũ phải còn nguyên byte-for-byte"
    khoi_phuc = store.load()
    assert khoi_phuc.phase == "D"
    assert khoi_phuc.backlog[0].retries == 1


def test_khong_bao_gio_mo_file_dich_o_che_do_cat_ngan(
    store: StateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chặn tận gốc lối ghi ngây thơ open(path,'w') — nguồn của file cụt.

    Ghi đè trực tiếp lên file đích nghĩa là có một khoảnh khắc file rỗng trên
    đĩa; chết đúng lúc đó là mất trắng state. Test này canh đúng hành vi đó.
    """
    store.save(_state_mau())
    duong_dan_dich = str(store.path.resolve())
    open_that = open

    def open_canh(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
        if str(Path(file).resolve()) == duong_dan_dich and any(
            k in mode for k in ("w", "a", "+")
        ):
            raise AssertionError(
                f"save() mở thẳng file đích ở chế độ {mode!r} — phải ghi ra "
                "file tạm rồi os.replace (NFR-02)"
            )
        return open_that(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", open_canh)
    state = _state_mau()
    state.phase = "E"
    store.save(state)

    monkeypatch.undo()
    assert store.load().phase == "E"


def test_don_sach_file_tam_khong_de_lai_rac(store: StateStore) -> None:
    store.save(_state_mau())
    store.save(_state_mau())
    con_lai = [p.name for p in store.path.parent.iterdir() if p.name.endswith(".tmp")]
    assert not con_lai, f"còn sót file tạm: {con_lai}"


def test_file_tam_sot_lai_tu_lan_crash_truoc_khong_pha_load(store: StateStore) -> None:
    store.save(_state_mau())
    (store.path.parent / f"{store.path.name}.abc123.tmp").write_text(
        "rác từ lần crash trước", encoding="utf-8"
    )
    assert store.load().phase == "D"


# --------------------------------------------------------------------------
# Lớp 2b — khóa file chống ghi đè (EAA-SDD-03 §4: with_lock)
# --------------------------------------------------------------------------


def test_lock_ngan_hai_tien_trinh_ghi_dong_thoi(store: StateStore) -> None:
    store.save(_state_mau())
    khac = StateStore(store.path)

    with store.with_lock():
        with pytest.raises(StateLockTimeout):
            with khac.with_lock(timeout=0.3):
                pytest.fail("không được cấp lock thứ hai khi lock đầu còn giữ")


def test_lock_duoc_nha_khi_thoat_ke_ca_luc_co_ngoai_le(store: StateStore) -> None:
    store.save(_state_mau())

    with pytest.raises(RuntimeError):
        with store.with_lock():
            raise RuntimeError("lỗi giữa vùng găng")

    # Lấy lại được ngay: lock không bị kẹt sau ngoại lệ.
    with store.with_lock(timeout=0.5):
        pass


def test_lock_mo_coi_do_tien_trinh_chet_khong_khoa_vinh_vien(
    store: StateStore, tmp_path: Path
) -> None:
    """Kill -9 không chạy được finally — lock mồ côi phải tự được thu hồi."""
    store.save(_state_mau())
    kich_ban = tmp_path / "giu_lock.py"
    kich_ban.write_text(
        textwrap.dedent(
            f"""
            import sys, time
            sys.path.insert(0, {str(PROJECT_ROOT)!r})
            from eaa.state import StateStore
            store = StateStore({str(store.path)!r})
            ctx = store.with_lock()
            ctx.__enter__()
            print("locked", flush=True)
            time.sleep(60)
            """
        ),
        encoding="utf-8",
    )

    proc = subprocess.Popen(
        [sys.executable, str(kich_ban)], stdout=subprocess.PIPE, text=True, encoding="utf-8"
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "locked"
        proc.kill()
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:  # pragma: no cover
            proc.kill()

    # Lock trên đĩa còn đó nhưng chủ nó đã chết → phải nhận ra và thu hồi.
    with store.with_lock(timeout=5.0):
        assert store.load().phase == "D"


# --------------------------------------------------------------------------
# Lớp 3 — kill -9 thật, lặp nhiều lần
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lan", range(12))
def test_tc03_kill_9_giua_vong_lap_state_van_doc_duoc(
    tmp_path: Path, lan: int
) -> None:
    """Giết tiến trình đang ghi state liên tục; file phải luôn dùng lại được."""
    duong_dan = tmp_path / f"state_{lan}.json"
    kich_ban = tmp_path / f"ghi_lien_tuc_{lan}.py"
    kich_ban.write_text(
        textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(PROJECT_ROOT)!r})
            from eaa.state import BacklogItem, ProjectState, StateStore

            store = StateStore({str(duong_dan)!r})
            state = ProjectState(
                phase="D",
                gates={{"G1": "approved", "G2": "approved", "G3": "pending"}},
                backlog=[BacklogItem(id="drv_bus_sensor", status="in_verify", retries=1)],
                constraints_version="sha256:ab12cd34",
                llm={{"provider": "mock", "model": "mock-deterministic-1"}},
            )
            store.save(state)
            print("ready", flush=True)
            n = 0
            while True:
                n += 1
                state.backlog[0].retries = n % 4
                store.save(state)
            """
        ),
        encoding="utf-8",
    )

    proc = subprocess.Popen(
        [sys.executable, str(kich_ban)], stdout=subprocess.PIPE, text=True, encoding="utf-8"
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        # Điểm giết rải đều để rơi vào các pha khác nhau của vòng ghi.
        time.sleep(0.01 + 0.004 * lan)
        proc.kill()
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:  # pragma: no cover
            proc.kill()

    # Đây chính là "eaa resume" sau crash.
    khoi_phuc = StateStore(duong_dan).load()
    assert khoi_phuc.phase == "D"
    assert khoi_phuc.gates["G3"] == "pending"
    assert [m.id for m in khoi_phuc.backlog] == ["drv_bus_sensor"]
    assert khoi_phuc.backlog[0].status == "in_verify"
    assert 0 <= khoi_phuc.backlog[0].retries <= 3
    assert khoi_phuc.constraints_version == "sha256:ab12cd34"
