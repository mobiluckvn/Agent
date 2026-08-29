"""Trình liên kết giả.

Mô phỏng đúng một hành vi của trình liên kết thật, và là hành vi khiến bước này
phải tách khỏi bước dịch: **không có ``main()`` thì không liên kết được.** Nhờ
vậy bài kiểm chứng minh được sự tách bạch mà không cần cài toolchain thật lên
máy chạy test.
"""
import argparse, pathlib, sys

p = argparse.ArgumentParser()
p.add_argument("--output", required=True)
p.add_argument("--map")
p.add_argument("objects", nargs="+")
a = p.parse_args()

noi_dung = []
for ten in a.objects:
    path = pathlib.Path(ten)
    if not path.is_file():
        print(f"ld: khong tim thay tep doi tuong {ten}", file=sys.stderr)
        sys.exit(1)
    noi_dung.append(path.read_bytes())

gop = b"".join(noi_dung)
if b"main(" not in gop:
    print("ld: undefined reference to `main'", file=sys.stderr)
    sys.exit(1)

out = pathlib.Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(gop)
if a.map:
    pathlib.Path(a.map).write_text(f"lien ket {len(a.objects)} tep doi tuong\n", encoding="utf-8")
print(f"da lien ket {len(a.objects)} tep -> {a.output}")
