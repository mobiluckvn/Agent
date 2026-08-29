"""Bộ đổi định dạng giả — ảnh liên kết sang định dạng nạp được."""
import argparse, pathlib, sys

p = argparse.ArgumentParser()
p.add_argument("input")
p.add_argument("output")
a = p.parse_args()

nguon = pathlib.Path(a.input)
if not nguon.is_file():
    print(f"objcopy: khong doc duoc {a.input}", file=sys.stderr)
    sys.exit(1)

dich = pathlib.Path(a.output)
dich.parent.mkdir(parents=True, exist_ok=True)
# Định dạng nạp giả: mỗi byte một cặp chữ số hex, kết thúc bằng bản ghi EOF.
dich.write_text(nguon.read_bytes().hex() + "\n:00000001FF\n", encoding="utf-8")
print(f"da doi {a.input} -> {a.output}")
