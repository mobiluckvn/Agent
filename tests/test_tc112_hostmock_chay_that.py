"""TC-112 — tiêu đề giả của pack phải THẬT SỰ dịch và chạy được.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-143.

`pack.yaml` khai `host_test.mock_include: hostmock` từ SL-134, và thư mục ấy
không tồn tại suốt từ đó. Không ai phát hiện vì tới tận `drv_button` mới có
module đầu tiên thật sự chạm một thanh ghi — và lúc ấy nó chết ở cổng thứ tư
với `fatal error: 'avr/io.h' file not found`, sau khi đã đốt ba lượt gọi mô
hình cho một thứ không bản vá nào của module sửa được.

Bài này dịch một module chạm thanh ghi bằng ĐÚNG cờ pack khai, rồi lái nó qua
`ctypes` như một bài kiểm thật. Nó tốn vài trăm mili giây và thay thế được một
lượt gọi mô hình để phát hiện cùng một lỗi.

Bốn điều nó chứng minh
-----------------------

1.  `<avr/io.h>` và `<avr/interrupt.h>` phân giải được trên máy chủ.
2.  Thanh ghi hành xử như ô nhớ, và bài kiểm ĐỌC/GHI được chúng — không có
    điều này thì không dựng được cảnh cho bất kỳ driver nào.
3.  Cấu hình chân để lại dấu vết KIỂM ĐƯỢC: hướng ở `DDRB`, kéo lên nội ở
    `PORTB`. Đây là chỗ một driver hay sai âm thầm.
4.  Thân `ISR(...)` gọi được từ bài kiểm. Đó là cách duy nhất kiểm logic trong
    ngắt mà không cần con chip — và `drv_stepper` sống hay chết ở chỗ này.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
PACK = REPO / "packs" / "avr"

NGUON = """\
#include <stdint.h>
#include <stdbool.h>
#include <avr/io.h>
#include <avr/interrupt.h>

void x_init(void) {
    DDRB  &= ~(1 << DDB4);      /* nút: chân vào */
    PORTB |=  (1 << PORTB4);    /* bật điện trở kéo lên nội */
    DDRB  |=  (1 << DDB2);      /* còi: chân ra */
}
bool x_nhan(void)      { return (PINB & (1 << PINB4)) == 0; }
void x_coi(bool bat)   { if (bat) PORTB |= (1 << PORTB2); else PORTB &= ~(1 << PORTB2); }

static volatile uint16_t dem;
ISR(TIMER2_COMPA_vect) { dem++; }
uint16_t x_dem(void)   { return dem; }
"""


def test_thu_muc_tieu_de_gia_ton_tai() -> None:
    """Khai một thư mục không tồn tại là khai một lời hứa không ai giữ."""
    d = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))
    ten = (d.get("host_test") or {}).get("mock_include")
    assert ten, "pack không khai `host_test.mock_include`"
    assert (PACK / ten).is_dir(), (
        f"pack khai thư mục tiêu đề giả {ten!r} mà nó không tồn tại — mọi module "
        "chạm thanh ghi sẽ chết ở cổng unittests"
    )


def test_co_du_tieu_de_ma_firmware_thuong_dung() -> None:
    thu_muc = PACK / "hostmock"
    for tep in ("avr/io.h", "avr/interrupt.h", "util/delay.h"):
        assert (thu_muc / tep).is_file(), f"thiếu {tep}"


@pytest.fixture(scope="module")
def thu_vien(tmp_path_factory) -> ctypes.CDLL:
    """Dịch module thử bằng ĐÚNG cờ pack khai, không phải cờ tự nghĩ ra."""
    if shutil.which("cc") is None:  # pragma: no cover - máy không có trình dịch
        pytest.skip("máy này không có `cc`")

    d = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))
    ht = d["host_test"]
    gia = PACK / ht["mock_include"]

    tmp = tmp_path_factory.mktemp("hostmock")
    (tmp / "m.c").write_text(NGUON, encoding="utf-8")
    thu_vien_path = tmp / "libm.so"

    lenh = [ht["compiler"], *ht["cflags"], f"-I{gia}", "-o", str(thu_vien_path),
            str(tmp / "m.c"), *[str(p) for p in sorted(gia.glob("*.c"))]]
    ket_qua = subprocess.run(lenh, capture_output=True, text=True)
    assert ket_qua.returncode == 0, (
        "không dịch được module chạm thanh ghi bằng tiêu đề giả của pack:\n"
        + ket_qua.stderr
    )

    lib = ctypes.CDLL(str(thu_vien_path))
    lib.x_nhan.restype = ctypes.c_bool
    lib.x_dem.restype = ctypes.c_uint16
    return lib


def _reg(lib: ctypes.CDLL, ten: str):
    """Với tới thanh ghi đúng cách bài kiểm sinh ra sẽ làm: qua tên ký hiệu.

    Đây là phản xạ đầu tiên của bất cứ ai viết bài kiểm, và mô hình cũng làm
    đúng thế — bản mock đầu dùng macro trỏ vào mảng nên câu này chết với
    `symbol not found` dù mã C hoàn toàn đúng (SL-145).
    """
    return ctypes.c_uint8.in_dll(lib, ten)


def test_cau_hinh_chan_de_lai_dau_vet_kiem_duoc(thu_vien) -> None:
    ddrb, portb = _reg(thu_vien, "DDRB"), _reg(thu_vien, "PORTB")
    ddrb.value = 0
    portb.value = 0
    thu_vien.x_init()

    assert ddrb.value & (1 << 4) == 0, "nút phải là chân VÀO"
    assert portb.value & (1 << 4), "chưa bật điện trở kéo lên nội — nút sẽ thả nổi"
    assert ddrb.value & (1 << 2), "còi phải là chân RA"


def test_doc_chan_theo_PINB_khong_theo_PORTB(thu_vien) -> None:
    """`PORTB` là giá trị đã ghi ra, không phải điện áp đang có trên chân."""
    pinb = _reg(thu_vien, "PINB")
    thu_vien.x_init()

    pinb.value = 0xFF
    assert thu_vien.x_nhan() is False
    pinb.value = 0xFF & ~(1 << 4)
    assert thu_vien.x_nhan() is True, "kéo chân xuống mà không thấy là nhấn"


def test_ghi_chan_ra_chi_dung_dung_bit(thu_vien) -> None:
    portb = _reg(thu_vien, "PORTB")
    thu_vien.x_init()
    truoc = portb.value

    thu_vien.x_coi(True)
    assert (portb.value >> 2) & 1 == 1
    thu_vien.x_coi(False)
    assert (portb.value >> 2) & 1 == 0
    assert portb.value & ~(1 << 2) == truoc & ~(1 << 2), (
        "ghi chân còi làm đổi bit khác — đây là cách một driver phá cấu hình "
        "của driver bên cạnh"
    )


def test_than_ngat_goi_duoc_tu_bai_kiem(thu_vien) -> None:
    """`drv_stepper` sống hay chết ở chỗ này: logic phát xung nằm trong ngắt."""
    truoc = thu_vien.x_dem()
    for _ in range(40):
        thu_vien.TIMER2_COMPA_vect_fn()
    assert thu_vien.x_dem() - truoc == 40
