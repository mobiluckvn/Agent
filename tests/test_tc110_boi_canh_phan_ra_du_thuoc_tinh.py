"""TC-110 — bối cảnh phân rã phải mang THUỘC TÍNH, không chỉ TÊN.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-141.

Tìm ra khi phân rã lại dự án robot sau khi khai thêm còi và nút nhấn. Bản đề
xuất đầu::

    [drv_buzzer] ... chiếm: buzzer, timer2

`timer2` là bộ đếm đang phát xung bước. Một cái còi cướp mất nhịp bước là robot
ngã, và không cổng phần mềm nào bắt được.

Tôi ghi thẳng vào hồ sơ rằng đây là còi CHỦ ĐỘNG — tự dao động, chỉ cần đặt
mức chân, không cần bộ đếm nào — kèm bằng chứng từ mã tham chiếu. Phân rã lại::

    [drv_buzzer] ... chiếm: buzzer, timer1

Nó chỉ đổi sang bộ đếm khác. Vì dòng chữ ấy **chưa bao giờ tới được prompt**.

Hồ sơ phần cứng bị rút thành một danh sách tên
-----------------------------------------------

``_boi_canh`` dựng phần phần cứng như sau::

    ngoai_vi = [p.get("id") for p in hardware.peripherals]
    linh_kien = [c.get("id") for c in hardware.components]
    "Tài nguyên phần cứng CÓ THẬT: " + ", ".join(...)

Mọi thuộc tính bị bỏ: `drive`, `active_level`, `pins`, `note`, `kind`. Bộ phân
rã nhận được một DANH SÁCH TÊN và phải tự đoán mỗi cái tên ấy cần gì — nên nó
đoán rằng "còi" thì cần một bộ đếm, đúng như trực giác chung về còi thụ động.

Và module đã có được liệt kê mà không kèm trách nhiệm
------------------------------------------------------

``_boi_canh_da_co`` in ``id (chiếm: ...)``. Không có `purpose`. Nên bộ phân rã
biết `app_balance` TỒN TẠI mà không biết nó LÀM GÌ, và đề xuất thêm `app_hmi`
ôm đúng phần việc `app_balance` đã nhận — giao thức nút nhấn và tiếng bíp.

`purpose` nằm sẵn trong backlog từ SL-135. Chỗ dựng danh sách `existing` chỉ
lấy `(id, uses)` và bỏ nó lại. Cùng một hình dạng, lần thứ hai.
"""

from __future__ import annotations

import pytest


class _HoSo:
    peripherals = [
        {"id": "timer2", "kind": "timer", "note": "Ngắt 20 µs phát xung bước."},
        {"id": "twi", "kind": "i2c"},
    ]
    components = [
        {
            "id": "buzzer",
            "part": "buzzer_5v",
            "pins": {"signal": "PB2"},
            "drive": "dc_on_off",
            "active_level": 1,
            "note": "Còi chip 5V tự dao động.",
        },
        {"id": "imu", "part": "mpu6050", "bus": "twi", "address": 0x68},
    ]


def test_boi_canh_mang_THUOC_TINH_cua_linh_kien() -> None:
    """Điểm cốt lõi: `drive: dc_on_off` phải tới được bộ phân rã."""
    from eaa.decompose import LlmDecomposer

    van_ban = LlmDecomposer._boi_canh(_HoSo(), None)

    assert "dc_on_off" in van_ban, (
        "hồ sơ nói còi tự dao động, prompt không mang theo — mô hình đoán rằng "
        "còi cần một bộ đếm, và nó xin đúng bộ đếm đang phát xung bước"
    )
    assert "PB2" in van_ban, "không nói còi nằm ở chân nào"


def test_boi_canh_van_neu_du_TEN_tai_nguyen() -> None:
    """Thêm thuộc tính không được làm mất danh sách tên vốn có."""
    from eaa.decompose import LlmDecomposer

    van_ban = LlmDecomposer._boi_canh(_HoSo(), None)
    for ten in ("timer2", "twi", "buzzer", "imu"):
        assert ten in van_ban


def test_boi_canh_neu_LOAI_cua_ngoai_vi() -> None:
    """"timer2" một mình không nói nó là bộ đếm; "kind" thì có."""
    from eaa.decompose import LlmDecomposer

    assert "timer" in LlmDecomposer._boi_canh(_HoSo(), None)


def test_khong_co_ho_so_thi_khong_sap() -> None:
    from eaa.decompose import LlmDecomposer

    assert isinstance(LlmDecomposer._boi_canh(None, None), str)


# ═══════════ module đã có phải kèm TRÁCH NHIỆM ═══════════


def test_module_da_co_kem_trach_nhiem() -> None:
    """Biết một module TỒN TẠI mà không biết nó LÀM GÌ thì vẫn đề xuất chồng lên."""
    from eaa.decompose import _boi_canh_da_co

    van_ban = _boi_canh_da_co(
        [("app_balance", (), "Máy trạng thái khởi động bằng tiếng bíp và vòng 4 ms")]
    )
    assert "tiếng bíp" in van_ban, (
        "chỉ liệt kê tên module đã có; mô hình không biết app_balance đã ôm "
        "giao thức nút nhấn nên đề xuất thêm một module ôm đúng việc ấy"
    )


def test_dang_cu_hai_phan_tu_van_dung_duoc() -> None:
    """Backlog cũ chưa có `purpose` thì vẫn phải phân rã được."""
    from eaa.decompose import _boi_canh_da_co

    van_ban = _boi_canh_da_co([("drv_i2c", ("twi",))])
    assert "drv_i2c" in van_ban and "twi" in van_ban


def test_rong_thi_khong_them_gi() -> None:
    from eaa.decompose import _boi_canh_da_co

    assert _boi_canh_da_co([]) == ""
    assert _boi_canh_da_co(None) == ""


def test_cli_TRUYEN_purpose_xuong_bo_phan_ra() -> None:
    """`purpose` nằm sẵn trong backlog từ SL-135; chỗ dựng danh sách bỏ nó lại."""
    import inspect

    from eaa import cli

    nguon = inspect.getsource(cli._plan_propose)
    assert "purpose" in nguon, (
        "danh sách module đã có dựng từ (id, uses) và bỏ purpose — bộ phân rã "
        "biết module tồn tại mà không biết nó làm gì"
    )
