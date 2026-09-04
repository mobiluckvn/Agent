"""TC-132 — vòng đời tri thức phải có CỬA VÀO (N-036, N-100).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-172.

`eaa/lifecycle.py` có đủ ba đường truy ngược, có TC-29 canh từng đường, và
không module nào trong `eaa/` hay `packs/` gọi tới nó. Đó là dạng hỏng mà
`scripts/kiem_bang_nang_luc.py` sinh ra để bắt: **có mã, có test, không có
người gọi** — cùng hình dạng với SL-113 và SL-169.

Hệ quả đúng bằng cái module ấy sinh ra để chữa: sửa một trích đoạn tài liệu
xong thì không có cách nào hỏi *"mã nào bị ảnh hưởng"*, và mã sinh trên bản sai
vẫn nằm trong `main` mang nhãn đã kiểm chứng.

Hai chuyện bài này canh
------------------------

1. **`stale` là CHỈ ĐỌC.** Nó trả lời một câu hỏi, không đổi gì. Một lệnh vừa
   trả lời vừa đổi trạng thái là lệnh người ta ngại gõ.
2. **`supersede`/`deprecate` KHÔNG vượt được G2**, và khi chúng chạy thì việc
   hạ tin cậy module xảy ra **trong cùng lệnh** — một bước rời là một bước sẽ
   quên, và quên ở đây thì im lặng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa import EXIT_OK
from eaa.cli import main
from tests.test_cli_e2e import dung_moi_truong

#: Tên tệp của chunk ds-021 trong dự án mẫu. Bài kiểm đọc thẳng tệp để chứng
#: minh NỘI DUNG không đổi một byte, nên nó phải biết đúng tệp nào.
TEP_CHUNK = "atmega328p__twi_bitrate.md"

CHUNK_MOI = """---
id: ds-021-v2
device: atmega328p
peripheral: twi
registers: [TWBR, TWSR, TWCR]
topic: Cấu hình tốc độ bit bus hai dây, bản sửa
source: ATmega328P datasheet rev. DS40002061B, tr.222-224
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000009
status: approved
---

TWBR bản sửa: hệ số chia bus khác với bản trước.
"""


@pytest.fixture()
def du_an(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> Path:
    project = dung_moi_truong(tmp_path, monkeypatch)
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    # Một tệp mã trích dẫn ds-021 — đường thứ hai của phép truy ngược.
    src = project / "firmware" / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "drv_bus_sensor.c").write_text(
        '#include "drv_bus_sensor.h"\n'
        "// ref: ds-021, tr.222\n"
        "void drv_bus_sensor_init(void) { TWBR = 12u; }\n",
        encoding="utf-8",
    )
    capsys.readouterr()
    return project


def _trang_thai(project: Path, module: str) -> str:
    du_lieu = json.loads((project / "project_state.json").read_text(encoding="utf-8"))
    for m in du_lieu["backlog"]:
        if m["id"] == module:
            return m["status"]
    raise AssertionError(f"không có module {module} trong backlog")


# ── stale: trả lời được câu hỏi của N-100 ────────────────────────────────────


def test_stale_tra_loi_ma_nao_dua_tren_trich_doan(du_an: Path, capsys) -> None:
    """Câu hỏi mà trước SL-172 không lệnh nào trả lời được."""
    assert main(["knowledge", "stale", "ds-021"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "drv_bus_sensor" in ra


def test_stale_neu_BANG_CHUNG_chu_khong_chi_neu_ten(du_an: Path, capsys) -> None:
    """Nêu tên mà không nêu vì sao thì người đọc phải tự đi kiểm lại từ đầu."""
    main(["knowledge", "stale", "ds-021"])
    ra = capsys.readouterr().out
    assert "trích dẫn trong mã" in ra
    assert "drv_bus_sensor.c" in ra


def test_stale_gan_nhan_SUY_RA_chu_khong_phai_DA_KIEM(du_an: Path, capsys) -> None:
    """Đường đồ thị đọc khai báo `uses`; khai báo thiếu thì đường ấy mù."""
    main(["knowledge", "stale", "ds-021"])
    ra = capsys.readouterr().out
    assert "[SUY RA]" in ra
    assert "[ĐÃ KIỂM]" not in ra


def test_stale_KHONG_doi_gi(du_an: Path, capsys) -> None:
    """Một lệnh vừa trả lời vừa đổi trạng thái là lệnh người ta ngại gõ."""
    truoc = (du_an / "project_state.json").read_text(encoding="utf-8")
    chunk = du_an / "datasheets" / TEP_CHUNK
    chunk_truoc = chunk.read_text(encoding="utf-8")

    main(["knowledge", "stale", "ds-021"])

    assert (du_an / "project_state.json").read_text(encoding="utf-8") == truoc
    assert chunk.read_text(encoding="utf-8") == chunk_truoc
    assert "KHÔNG đổi gì" in capsys.readouterr().out


def test_stale_voi_trich_doan_khong_ai_dung_thi_noi_ro_la_khong_co(
    du_an: Path, capsys
) -> None:
    main(["knowledge", "stale", "ds-khong-ai-dung"])
    assert "Không module nào dựa trên" in capsys.readouterr().out


# ── supersede / deprecate: không vượt được G2 ────────────────────────────────


def test_deprecate_khong_co_duyet_G2_thi_TU_CHOI(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Chưa duyệt G2 thì không được đổi kho tri thức — dù lệnh gõ đúng."""
    project = dung_moi_truong(tmp_path, monkeypatch)
    main(["init"])
    main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"])
    capsys.readouterr()

    ma = main(["knowledge", "deprecate", "ds-021", "--reason", "sai hệ số"])
    assert ma != EXIT_OK
    ra = capsys.readouterr()
    assert "G2" in (ra.out + ra.err)
    # Và chunk vẫn nguyên trạng thái cũ.
    chunk = (project / "datasheets" / TEP_CHUNK).read_text(encoding="utf-8")
    assert "deprecated" not in chunk


def test_deprecate_co_duyet_G2_thi_HA_CAP_va_ha_module_trong_CUNG_lenh(
    du_an: Path, capsys
) -> None:
    """Một bước rời là một bước sẽ quên, và quên ở đây thì im lặng."""
    assert _trang_thai(du_an, "drv_bus_sensor") != "stale"

    ma = main(["knowledge", "deprecate", "ds-021", "--reason", "hệ số chia sai"])
    assert ma == EXIT_OK
    ra = capsys.readouterr().out

    assert "drv_bus_sensor" in ra
    assert "stale" in ra
    assert _trang_thai(du_an, "drv_bus_sensor") == "stale"


def test_ha_cap_giu_NOI_DUNG_nguyen_tung_byte(du_an: Path, capsys) -> None:
    """FR-RAG-01: bất biến là bất biến của NỘI DUNG, không của siêu dữ liệu."""
    chunk = du_an / "datasheets" / TEP_CHUNK
    than_truoc = chunk.read_text(encoding="utf-8").split("---", 2)[2]

    main(["knowledge", "deprecate", "ds-021", "--reason", "hệ số chia sai"])
    capsys.readouterr()

    van_ban = chunk.read_text(encoding="utf-8")
    assert van_ban.split("---", 2)[2] == than_truoc
    assert "deprecated" in van_ban
    assert "hệ số chia sai" in van_ban


def test_supersede_can_ban_thay_the_va_cung_doi_duyet_G2(du_an: Path, capsys) -> None:
    (du_an / "datasheets" / "twi_bitrate_v2.md").write_text(CHUNK_MOI, encoding="utf-8")
    ma = main(["knowledge", "supersede", "ds-021", "ds-021-v2", "--reason", "rev mới"])
    assert ma == EXIT_OK
    ra = capsys.readouterr().out
    assert "ds-021-v2" in ra
    assert _trang_thai(du_an, "drv_bus_sensor") == "stale"


def test_khong_the_ha_cap_hai_lan(du_an: Path, capsys) -> None:
    main(["knowledge", "deprecate", "ds-021", "--reason", "sai"])
    capsys.readouterr()
    ma = main(["knowledge", "deprecate", "ds-021", "--reason", "sai lần nữa"])
    assert ma != EXIT_OK


def test_he_KHONG_tu_mo_vong_sinh_lai(du_an: Path, capsys) -> None:
    """Hạ tin cậy là việc của máy; sinh lại hay sửa tay là quyết định của người."""
    main(["knowledge", "deprecate", "ds-021", "--reason", "sai"])
    ra = capsys.readouterr().out
    assert "KHÔNG tự mở vòng sinh lại" in ra


# ── ranh giới quyền ──────────────────────────────────────────────────────────


def test_agent_goi_duoc_stale_nhung_KHONG_goi_duoc_hai_nhanh_kia() -> None:
    """Thêm một lệnh không được thành thêm quyền — cùng luật với `datasheet add`."""
    from eaa.agent import TOOLBOX

    argv = {" ".join(t.argv) for t in TOOLBOX}
    assert "knowledge stale" in argv
    assert "knowledge supersede" not in argv
    assert "knowledge deprecate" not in argv


def test_stale_nam_o_nhom_CHI_DOC_cua_danh_muc() -> None:
    """Nó chỉ đọc thật — khai là có ghi sẽ khiến người đọc dè chừng nhầm chỗ."""
    from eaa.agent import TOOLBOX

    muc = next(t for t in TOOLBOX if t.argv == ("knowledge", "stale"))
    assert muc.writes is False
