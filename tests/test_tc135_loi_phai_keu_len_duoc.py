"""TC-135 — làm cho lỗi KÊU LÊN ĐƯỢC (N-912).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-175.

Ba lượt nạp đầu tiên, robot chỉ **im** hoặc **ngã**. Hai trạng thái ấy không
phân biệt được với chip chết, với nguồn tụt, hay với mã chạy sai — và cũng
không phân biệt được với nhau. Mọi đường báo hiệu về sau đều do **người** nghĩ
ra; không bản phân rã nào tự đề nghị lấy một cái.

Bộ này hỏi đúng hai câu cho mỗi module: người nhận ra nó ĐANG CHẠY bằng cách
nào, và khi nó HỎNG thì nhận ra bằng cách nào.

Ranh giới engine, và bài này canh nó
-------------------------------------

Engine **không biết** thứ gì kêu được, thứ gì sáng được, thứ gì người nghe
được. Nó chỉ đọc cờ ``observable`` mà hồ sơ dự án gắn cho linh kiện và coi giá
trị là **chuỗi mờ** — đúng cách nó đối xử với ``uses``. Biết "còi thì kêu" là
đã thành công cụ cho đúng một cái bo, và TC-38 quét chuyện ấy mỗi commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from eaa import EXIT_OK
from eaa.cli import main
from eaa.observability import Kenh, kenh_quan_sat, soi_quan_sat
from eaa.state import BacklogItem
from tests.test_cli_e2e import dung_moi_truong


@dataclass
class HoSoGia:
    """Hồ sơ phần cứng tối thiểu — đúng hai thuộc tính phép soi cần."""

    components: list[dict[str, Any]]
    peripherals: list[dict[str, Any]]


def _mod(ten: str, song: str = "", hong: str = "", status: str = "todo") -> BacklogItem:
    return BacklogItem(
        id=ten, status=status, dau_hieu_song=song, dau_hieu_hong=hong
    )


# ── đọc kênh quan sát từ hồ sơ ───────────────────────────────────────────────


def test_doc_kenh_tu_ca_components_lan_peripherals() -> None:
    """Dự án khai đường báo hiệu ở chỗ nào cũng được."""
    ho_so = HoSoGia(
        components=[{"id": "bao_am", "observable": "nghe"}],
        peripherals=[{"id": "bao_sang", "observable": "nhìn"}],
    )
    assert kenh_quan_sat(ho_so) == [Kenh("bao_am", "nghe"), Kenh("bao_sang", "nhìn")]


def test_linh_kien_khong_gan_co_thi_khong_phai_kenh() -> None:
    ho_so = HoSoGia(components=[{"id": "cam_bien", "part": "x"}], peripherals=[])
    assert kenh_quan_sat(ho_so) == []


def test_gia_tri_co_la_CHUOI_MO_engine_khong_dien_giai() -> None:
    """Engine chỉ chuyển tiếp; nó không biết 'rung' nghĩa là gì."""
    ho_so = HoSoGia(components=[{"id": "x", "observable": "rung tay cầm"}], peripherals=[])
    assert kenh_quan_sat(ho_so)[0].cach == "rung tay cầm"


def test_khong_co_ho_so_thi_khong_no() -> None:
    assert kenh_quan_sat(None) == []


def test_ho_so_hong_khong_lam_hong_phep_soi() -> None:
    class HoSoHong:
        @property
        def components(self):
            raise RuntimeError("hồ sơ hỏng")

        @property
        def peripherals(self):
            raise RuntimeError("hồ sơ hỏng")

    assert kenh_quan_sat(HoSoHong()) == []


# ── soi bản phân rã ──────────────────────────────────────────────────────────


def test_thieu_ca_hai_dau_hieu_thi_neu_ca_hai() -> None:
    bc = soi_quan_sat([_mod("drv_x")])
    assert bc.thieu[0].thieu == ("dấu hiệu sống", "dấu hiệu hỏng")


def test_thieu_MOT_dau_hieu_thi_chi_neu_cai_thieu() -> None:
    """Hai câu là hai câu khác nhau — trả lời một câu không phải trả lời cả hai."""
    bc = soi_quan_sat([_mod("drv_x", song="phát một nhịp mỗi giây")])
    assert bc.thieu[0].thieu == ("dấu hiệu hỏng",)


def test_khai_du_ca_hai_thi_khong_nam_trong_danh_sach_thieu() -> None:
    bc = soi_quan_sat([_mod("drv_x", song="nhịp đều", hong="im hẳn")])
    assert bc.thieu == ()
    assert bc.so_module == 1


def test_chuoi_toan_dau_cach_khong_tinh_la_da_khai() -> None:
    assert soi_quan_sat([_mod("drv_x", song="   ")]).thieu[0].thieu[0] == "dấu hiệu sống"


def test_module_da_BO_thi_khong_hoi() -> None:
    """Hỏi câu này cho module đã bỏ là làm báo cáo dài ra mà không ai đọc hết."""
    bc = soi_quan_sat([_mod("bo_roi", status="dropped"), _mod("dang_lam")])
    assert bc.so_module == 1
    assert [t.module_id for t in bc.thieu] == ["dang_lam"]


# ── phát hiện to nhất: không có kênh nào ─────────────────────────────────────


def test_khong_co_kenh_nao_la_phat_hien_RIENG(caplog) -> None:
    """Thiếu dấu hiệu ở một module còn sửa được; không có kênh thì KHÔNG module
    nào khai được gì."""
    bc = soi_quan_sat([_mod("drv_x", song="a", hong="b")], HoSoGia([], []))
    assert bc.khong_co_kenh_nao is True
    assert bc.dat is False, "khai đủ dấu hiệu vẫn chưa đủ khi bo không nói được gì"
    assert "KHÔNG CÓ KÊNH QUAN SÁT NÀO" in bc.render()


def test_co_kenh_va_du_dau_hieu_thi_DAT() -> None:
    ho_so = HoSoGia(components=[{"id": "bao_am", "observable": "nghe"}], peripherals=[])
    bc = soi_quan_sat([_mod("drv_x", song="a", hong="b")], ho_so)
    assert bc.dat is True
    assert "bao_am" in bc.render()


def test_bao_cao_neu_HAI_CAU_phai_tra_loi() -> None:
    """Nêu thiếu mà không nêu câu hỏi thì người đọc không biết bắt đầu từ đâu."""
    van = soi_quan_sat([_mod("drv_x")], HoSoGia([{"id": "k", "observable": "nghe"}], [])).render()
    assert "ĐANG CHẠY" in van and "HỎNG" in van
    assert "câu của người" in van


# ── qua CLI thật ─────────────────────────────────────────────────────────────


@pytest.fixture()
def du_an(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> Path:
    project = dung_moi_truong(tmp_path, monkeypatch)
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    capsys.readouterr()
    return project


def test_observe_neu_module_chua_khai(du_an: Path, capsys) -> None:
    assert main(["observe"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "drv_bus_sensor" in ra
    assert "dấu hiệu sống" in ra


def test_observe_set_ghi_duoc_va_observe_thay_ngay(du_an: Path, capsys) -> None:
    assert main(["observe", "set", "drv_bus_sensor", "--song", "nhịp đều mỗi giây"]) == EXIT_OK
    assert main(["observe", "set", "drv_bus_sensor", "--hong", "im hẳn quá 2 giây"]) == EXIT_OK
    capsys.readouterr()

    main(["observe"])
    ra = capsys.readouterr().out
    assert "chưa khai" not in ra


def test_observe_set_KHONG_neu_gi_thi_tu_choi(du_an: Path, capsys) -> None:
    """Hai câu khác nhau; một lệnh không nêu câu nào là một lệnh không làm gì."""
    assert main(["observe", "set", "drv_bus_sensor"]) != EXIT_OK


def test_observe_set_module_khong_co_thi_tu_choi(du_an: Path, capsys) -> None:
    assert main(["observe", "set", "khong_co", "--song", "x"]) != EXIT_OK


def test_observe_LUON_thoat_0_vi_no_la_bao_cao_khong_phai_cong(du_an: Path, capsys) -> None:
    """Chặn merge vì thiếu dấu hiệu sẽ biến một câu hỏi hay thành thủ tục."""
    assert main(["observe"]) == EXIT_OK


def test_dau_hieu_song_sot_qua_mot_vong_ghi_doc_state(du_an: Path, capsys) -> None:
    """Trường mới phải đi qua to_dict/from_dict, nếu không nó mất lúc lưu."""
    main(["observe", "set", "drv_bus_sensor", "--song", "nhịp đều"])
    capsys.readouterr()
    from eaa.cli import STATE_FILE
    from eaa.state import StateStore

    muc = StateStore(du_an / STATE_FILE).load().module("drv_bus_sensor")
    assert muc.dau_hieu_song == "nhịp đều"


# ── vào hồ sơ G3 ─────────────────────────────────────────────────────────────


def test_checklist_G3_hoi_khi_module_chua_khai() -> None:
    """G3 là lúc người đang đọc mã của đúng module ấy — lúc rẻ nhất để hỏi."""
    from types import SimpleNamespace

    from eaa.orchestrator import Orchestrator

    class KhoState:
        def load(self):
            return SimpleNamespace(module=lambda _: _mod("drv_x"))

    orch = SimpleNamespace(state_store=KhoState())
    muc = Orchestrator._muc_quan_sat(orch, "drv_x")
    assert len(muc) == 1
    assert "drv_x" in muc[0] and "eaa observe" in muc[0]


def test_checklist_G3_IM_khi_da_khai_du() -> None:
    from types import SimpleNamespace

    from eaa.orchestrator import Orchestrator

    class KhoState:
        def load(self):
            return SimpleNamespace(module=lambda _: _mod("drv_x", song="a", hong="b"))

    assert Orchestrator._muc_quan_sat(SimpleNamespace(state_store=KhoState()), "drv_x") == ()


def test_checklist_G3_khong_no_khi_khong_doc_duoc_state() -> None:
    from types import SimpleNamespace

    from eaa.orchestrator import Orchestrator

    class KhoHong:
        def load(self):
            raise RuntimeError("state hỏng")

    assert Orchestrator._muc_quan_sat(SimpleNamespace(state_store=KhoHong()), "x") == ()


# ── ranh giới quyền ──────────────────────────────────────────────────────────


def test_agent_doc_duoc_bao_cao_nhung_KHONG_tu_chot_dau_hieu() -> None:
    """Dấu hiệu nào đủ rõ trên bo là quyết định của người (N-912 ở mức T1)."""
    from eaa.agent import TOOLBOX

    argv = {" ".join(t.argv) for t in TOOLBOX}
    assert "observe" in argv
    assert "observe set" not in argv
