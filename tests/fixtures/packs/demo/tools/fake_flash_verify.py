"""Đọc ngược giả — so nội dung 'trên chip' với ảnh đã gửi (N-075).

Mã thoát 1 kèm một dòng khớp ``error_regex`` của pack khi hai bên lệch nhau;
đó đúng là cách avrdude và st-flash báo verification error.
"""
import sys
from pathlib import Path

anh = Path(sys.argv[1])
tren_chip = Path(str(anh) + ".on-device")

if not tren_chip.is_file():
    print("verify: error: chip rong, chua co gi de doc nguoc")
    sys.exit(1)

if tren_chip.read_bytes() != anh.read_bytes():
    print("verify: error: noi dung doc ve khac anh da gui")
    sys.exit(1)

print(f"verify ok: {anh}")
