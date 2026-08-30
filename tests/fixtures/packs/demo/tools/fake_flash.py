"""Nạp firmware giả — chỉ để chứng minh cổng này luôn cần người xác nhận.

Ngoài việc in một dòng, nó còn ghi lại "nội dung đang nằm trên chip" vào một
tệp cạnh ảnh. ``fake_flash_verify.py`` đọc chính tệp ấy, nên phép đọc ngược
trong test là một phép so THẬT giữa hai nội dung, không phải một hằng số True
trá hình. Muốn dựng cảnh nạp hỏng thì sửa tệp ấy — đúng cách một khối flash
mòn làm hỏng dữ liệu ngoài đời.
"""
import sys
from pathlib import Path

anh = Path(sys.argv[1])
Path(str(anh) + ".on-device").write_bytes(anh.read_bytes())
print(f"da nap {anh}")
