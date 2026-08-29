"""Trình dịch giả: 'dịch' được trừ khi mã có dấu hiệu hỏng cú pháp rõ ràng."""
import argparse, pathlib, re, sys

p = argparse.ArgumentParser()
p.add_argument("--output", required=True)
p.add_argument("sources", nargs="+")
a = p.parse_args()

loi = 0
for ten in a.sources:
    path = pathlib.Path(ten)
    if not path.is_file():
        print(f"{ten}:0: error: khong tim thay tep", file=sys.stderr)
        loi += 1
        continue
    for i, dong in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        sach = dong.strip()
        # Câu lệnh gán/khai báo thiếu dấu chấm phẩy.
        if re.match(r"^[A-Za-z_][\w \*]+\w\s*=\s*[^;{}]+$", sach) and not sach.endswith(("{", ",", "\\")):
            print(f"{ten}:{i}: error: expected ';' before end of statement", file=sys.stderr)
            loi += 1
        if "undeclared_helper" in sach:
            print(f"{ten}:{i}: error: implicit declaration of function 'undeclared_helper'", file=sys.stderr)
            loi += 1
        if re.search(r"\bint\s+unused_\w+\s*;", sach):
            print(f"{ten}:{i}: warning: unused variable", file=sys.stderr)

if loi:
    sys.exit(1)

out = pathlib.Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(b"".join(pathlib.Path(s).read_bytes() for s in a.sources))
print(f"da dich {len(a.sources)} tep -> {a.output}")
