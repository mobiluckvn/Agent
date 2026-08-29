"""Phân tích tĩnh giả: chỉ bắt một dấu hiệu, để chứng minh cổng có chạy thật."""
import pathlib, sys

path = pathlib.Path(sys.argv[1])
loi = 0
for i, dong in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if "goto " in dong:
        print(f"{sys.argv[1]}:{i}: error: goto bi cam boi cong cu ngoai")
        loi += 1
sys.exit(1 if loi else 0)
