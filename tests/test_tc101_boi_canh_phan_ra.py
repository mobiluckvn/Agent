"""TC-101 — bối cảnh phân rã thiếu hai thứ: PHONG CÁCH và THỨ ĐÃ CÓ.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-131.

Tìm ra khi soi bản phân rã bài "robot tự cân bằng" trước lúc nhận. Hai chỗ,
cùng một gốc: `_boi_canh()` tự dựng lấy phần ràng buộc thay vì dùng bảng chung,
và nó không biết dự án đã có gì.

Thứ nhất — `style` không bao giờ tới nơi
-----------------------------------------

`constraints.yaml` có `style.arithmetic: integer` (số học số nguyên ở vòng điều
khiển). Bộ phân rã chỉ nhận `limits` và `forbidden`. Nên khi nó giải thích
module lọc góc nghiêng, nó viện đúng `float_in_isr` — một mục trong `forbidden`
— và **không hề biết** còn một luật rộng hơn cấm số thực ở cả vòng điều khiển.

Bộ lọc bù viết bằng số thực sẽ qua được lệnh cấm hẹp mà vi phạm lệnh rộng.

Và đây là lần thứ hai cùng một hình dạng: đường sinh mã lấy ràng buộc qua bảng
K1 (`composer._bang_rang_buoc`), còn đường phân rã tự dựng lấy một tập con.
**Hai chỗ dựng cùng một thứ bằng hai đoạn mã khác nhau thì sớm muộn chúng lệch
nhau** — SL-112 đã là đúng chuyện ấy giữa đường sinh mã và đường hội thoại.

Thứ hai — không biết dự án đã có module nào
---------------------------------------------

Backlog đang có `drv_uart` với mã đã sinh, đã qua compile/size/static. Bản phân
rã đề xuất thêm một module `telemetry` chiếm `usart0` mà không nhắc gì tới nó.

Mô hình không thể biết: prompt không có backlog. Hậu quả là hai module cùng
chiếm một ngoại vi, và người duyệt phải tự nhớ ra.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


class _Rang:
    forbidden = ["delay()", "float_in_isr"]
    limits = {"control_loop_ms": 10}
    style = {"arithmetic": "integer", "io": "direct_port"}


class _PhanCung:
    peripherals = [{"id": "twi"}, {"id": "usart0"}]
    components = [{"id": "imu"}]


# ═══════════ 1. phong cách phải tới nơi ═══════════


def test_boi_canh_co_PHONG_CACH_khong_chi_dieu_cam() -> None:
    """`arithmetic: integer` rộng hơn `float_in_isr`, và nó phải tới được mô hình."""
    from eaa.decompose import LlmDecomposer

    van_ban = LlmDecomposer._boi_canh(_PhanCung(), _Rang())
    assert "integer" in van_ban, "phong cách số học không vào bối cảnh phân rã"
    assert "float_in_isr" in van_ban, "vẫn phải giữ điều cấm"


def test_boi_canh_dung_CHUNG_bang_voi_duong_sinh_ma() -> None:
    """Hai chỗ dựng cùng một thứ bằng hai đoạn mã thì sớm muộn chúng lệch nhau.

    Bài này không so từng chữ — nó đòi bối cảnh phân rã chứa MỌI mục mà bảng
    K1 của đường sinh mã chứa. Thêm một luật vào constraints.yaml mà chỉ một
    trong hai đường thấy nó là đúng cái SL-112 đã xảy ra một lần.
    """
    from eaa.composer import _bang_rang_buoc
    from eaa.decompose import LlmDecomposer

    bang = _bang_rang_buoc(_Rang())
    boi_canh = LlmDecomposer._boi_canh(_PhanCung(), _Rang())
    for cam in _Rang.forbidden:
        assert cam in bang and cam in boi_canh, f"{cam!r} lệch giữa hai đường"
    for gia_tri in _Rang.style.values():
        assert gia_tri in boi_canh, f"phong cách {gia_tri!r} thiếu ở đường phân rã"


# ═══════════ 2. phải biết dự án ĐÃ CÓ gì ═══════════


def test_boi_canh_neu_module_DA_CO() -> None:
    from eaa.decompose import _boi_canh_da_co

    van_ban = _boi_canh_da_co([("drv_uart", ("usart0",))])
    assert "drv_uart" in van_ban and "usart0" in van_ban
    assert "đã có" in van_ban.lower() or "sẵn" in van_ban.lower()


def test_backlog_rong_thi_khong_them_gi() -> None:
    """Dự án mới thì không có phần này, và bối cảnh không được đầy rác."""
    from eaa.decompose import _boi_canh_da_co

    assert _boi_canh_da_co([]) == ""


def test_module_moi_TRUNG_ngoai_vi_voi_module_da_co_thi_canh_bao() -> None:
    """Hai module cùng chiếm một ngoại vi là xung đột tài nguyên, không phải lựa chọn."""
    from eaa.decompose import ModuleProposal, _kiem_trung_da_co

    m = ModuleProposal(id="telemetry", purpose="gửi log", uses=("usart0",))
    canh = _kiem_trung_da_co((m,), [("drv_uart", ("usart0",))])
    assert canh
    noi_dung = " ".join(canh)
    assert "telemetry" in noi_dung and "drv_uart" in noi_dung and "usart0" in noi_dung


def test_module_moi_KHONG_trung_thi_im_lang() -> None:
    from eaa.decompose import ModuleProposal, _kiem_trung_da_co

    m = ModuleProposal(id="pid_controller", purpose="PID")
    assert _kiem_trung_da_co((m,), [("drv_uart", ("usart0",))]) == []


def test_trung_TEN_module_cung_bi_canh_bao() -> None:
    """Đề xuất một module trùng tên module đã có là đè lên công đã làm."""
    from eaa.decompose import ModuleProposal, _kiem_trung_da_co

    m = ModuleProposal(id="drv_uart", purpose="viết lại")
    canh = _kiem_trung_da_co((m,), [("drv_uart", ("usart0",))])
    assert canh and "drv_uart" in " ".join(canh)
