#!/usr/bin/env python3
"""Kiểm lại bảng năng lực bằng MÁY, không bằng mắt.

    python scripts/kiem_bang_nang_luc.py

Vì sao cần tệp này
------------------

``scripts/lam_bang_nang_luc.py`` và ``scripts/lam_bang_nghiep_vu.py`` giữ hai
bảng gõ tay: mỗi dòng khai một trạng thái và một cột "bằng chứng". Bảng ấy
không tự sai được lúc viết — nó sai dần theo thời gian, vì mã đổi mà dòng khai
đứng yên. Đúng dạng hỏng mà sổ sai lệch gọi tên nhiều lần nhất: **mã lệch với
lời chính nó khai**.

Tệp này kiểm bốn điều máy kiểm được, và cố ý KHÔNG kiểm điều thứ năm:

1. **Tệp khai có thật không.** Cột bằng chứng nêu ``eaa/x.py`` thì tệp ấy phải
   tồn tại.
2. **Ký hiệu khai có thật không.** Nêu ``ClassName`` hay ``ham()`` thì phải tìm
   được chỗ định nghĩa.
3. **Mã ấy có ai gọi không.** Đây là phép kiểm đáng giá nhất. Một module có mã,
   có test, mà không module nào khác trong ``eaa/`` hay ``packs/`` import — thì
   năng lực ấy tồn tại dưới dạng thư viện, không dưới dạng thứ Agent làm được.
   SL-113 là đúng hình dạng này: "một tính chất an toàn có hàm, có test, KHÔNG
   có người gọi".
4. **Mã TC khai có tệp test không**, và tệp ấy có đang xanh không (cần
   ``--chay-test``, chậm hơn nhiều).

Điều thứ năm — "năng lực này có ĐÁNG gọi là đủ không" — thuộc về người đọc.
Máy chỉ nói được: dòng khai và mã đang kể hai câu chuyện khác nhau ở đâu.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent

#: Từ trông giống ký hiệu mã nhưng là tiếng Anh thường trong câu văn. Bỏ qua để
#: báo động không bị loãng — một bộ kiểm hay báo nhầm sớm muộn cũng bị tắt đi.
BO_QUA = {
    "Agent", "Tool", "Card", "ToolCard", "Git", "Python", "Excel", "Sprint",
    "Human", "Gate", "Platform", "Pack", "Internet", "GitHub", "PyPI",
    "StackOverflow", "README",
}


def _nap(ten: str):
    spec = importlib.util.spec_from_file_location(ten, GOC / "scripts" / f"{ten}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[ten] = m
    spec.loader.exec_module(m)
    return m


def _doc_nguon() -> dict[Path, str]:
    nguon: dict[Path, str] = {}
    for thu_muc, mau in (("eaa", "**/*.py"), ("packs", "**/*"), ("projects", "**/*.yaml")):
        for p in (GOC / thu_muc).glob(mau):
            if p.is_file() and p.suffix in (".py", ".yaml", ".yml", ".md", ".c", ".h"):
                try:
                    nguon[p] = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
    return nguon


def _module_khong_ai_goi(nguon: dict[Path, str]) -> dict[str, list[str]]:
    """Module trong ``eaa/`` mà không nơi nào ngoài chính nó nhắc tên.

    Nhắc tên tính cả import Python lẫn chuỗi trong ``pack.yaml`` — một module
    chạy bằng ``python -m`` từ Platform Pack vẫn là module có người gọi, dù
    không ai import nó (``eaa/tools/sim_runner.py`` là ca ấy).
    """
    mo_coi: dict[str, list[str]] = {}
    for p in sorted((GOC / "eaa").glob("**/*.py")):
        if p.name == "__init__.py":
            continue
        ten = p.stem
        goi = [
            str(q.relative_to(GOC))
            for q, t in nguon.items()
            if q != p and re.search(rf"\b{re.escape(ten)}\b", t)
        ]
        if not goi:
            mo_coi[str(p.relative_to(GOC))] = []
    return mo_coi


def _dinh_nghia_o_dau(ky_hieu: str, nguon: dict[Path, str]) -> list[str]:
    mau = re.compile(rf"^\s*(class|def|async def)\s+{re.escape(ky_hieu)}\b", re.M)
    return [str(p.relative_to(GOC)) for p, t in nguon.items() if mau.search(t)]


def _tep_test_theo_tc() -> dict[str, list[str]]:
    theo: dict[str, list[str]] = {}
    for p in (GOC / "tests").glob("**/*.py"):
        m = re.search(r"tc(\d+)", p.name)
        if m:
            theo.setdefault(f"TC-{int(m.group(1)):02d}", []).append(str(p.relative_to(GOC)))
    return theo


def _tep_nhac(tc: str) -> list[str]:
    """Tệp test nhắc mã TC trong nội dung, dù tên tệp mang số hiệu khác."""
    return [
        str(p.relative_to(GOC))
        for p in sorted((GOC / "tests").glob("**/*.py"))
        if tc in p.read_text(encoding="utf-8", errors="ignore")
    ]


def _ky_hieu_trong(van: str) -> set[str]:
    ra = set(re.findall(r"\b([a-z_][a-z0-9_]{4,})\(\)", van))
    ra |= {s for s in re.findall(r"\b([A-Z][a-z]+[A-Z][A-Za-z]+)\b", van)}
    return {s for s in ra if s not in BO_QUA}


def _thu_thap() -> list[tuple[str, str, str, str]]:
    """Trả (mã, trạng thái, bằng chứng, ghi chú thiếu) cho cả hai bảng."""
    nl = _nap("lam_bang_nang_luc")
    nv = _nap("lam_bang_nghiep_vu")
    hang: list[tuple[str, str, str, str]] = []
    for ma, _nhom, _ten, tt, bc, gc, _ut in nl.NEN:
        hang.append((ma, tt, bc, gc))
    for ma, tt, bc, thieu, _tc in nv.DOI_CHIEU:
        hang.append((ma, tt, bc, thieu))
    return hang


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chay-test", action="store_true",
                    help="chạy pytest cho từng tệp test được viện dẫn (chậm)")
    args = ap.parse_args(argv)

    nguon = _doc_nguon()
    theo_tc = _tep_test_theo_tc()
    mo_coi = _module_khong_ai_goi(nguon)
    hang = _thu_thap()

    thieu_tep: list[str] = []
    thieu_ky_hieu: list[str] = []
    thieu_nguoi_goi: list[str] = []
    da_nhan: list[str] = []
    thieu_test: list[str] = []
    tc_can_chay: set[str] = set()

    # Nhãn "đủ" viết khác nhau ở hai bảng ("ĐỦ" và "Đủ"); so bằng chữ thường.
    def khai_du(tt: str) -> bool:
        return tt.strip().lower() == "đủ"

    for ma, tt, bc, _gc in hang:
        van = f"{bc}"
        # Một dòng ĐÃ NHẬN là MỘT PHẦN / CHƯA thì mã mồ côi không phải chỗ lệch —
        # nó đúng là điều dòng ấy đang nói. Chỉ dòng khai ĐỦ mới bị tính là lệch.
        ghi = thieu_nguoi_goi if khai_du(tt) else da_nhan
        for tep in re.findall(r"\b(?:eaa|packs|scripts|projects)/[\w/*.-]+\.(?:py|yaml)", van):
            if "*" in tep:
                continue
            if not (GOC / tep).exists():
                thieu_tep.append(f"{ma}: khai {tep} — không có tệp này")
            elif tep in mo_coi:
                ghi.append(
                    f"{ma} [{tt}]: {tep} có mã, có test, KHÔNG module nào trong eaa/ hay packs/ gọi"
                )
        for s in _ky_hieu_trong(van):
            noi = _dinh_nghia_o_dau(s, nguon)
            if not noi:
                thieu_ky_hieu.append(f"{ma}: khai {s} — không tìm được chỗ định nghĩa")
            # Dòng nêu tên hàm mà không nêu đường dẫn vẫn phải chịu phép kiểm
            # người-gọi: `installerr.remedies()` nằm trong một module mồ côi thì
            # dòng ấy khai một năng lực không có đường nào chạy tới.
            for tep in noi:
                if tep in mo_coi:
                    ghi.append(
                        f"{ma} [{tt}]: {s} định nghĩa ở {tep} — module ấy không có người gọi"
                    )
        for tc in {f"TC-{int(x):02d}" for x in re.findall(r"TC-(\d+)", van)}:
            # Ưu tiên tệp mang đúng số hiệu; không có thì tìm mã TC nhắc trong
            # nội dung tệp test khác — nhiều TC được canh trong tệp của TC khác.
            tep = theo_tc.get(tc) or _tep_nhac(tc)
            if tep:
                tc_can_chay.update(tep)
            else:
                thieu_test.append(f"{ma}: khai {tc} — không tệp test nào nhắc tới")

    do = 0

    def khoi(tieu_de: str, muc: list[str]) -> None:
        nonlocal do
        print(f"\n── {tieu_de} — {len(muc)}")
        for m in sorted(set(muc)):
            print(f"   ✗ {m}")
            do += 1
        if not muc:
            print("   ✓ không có")

    print("Kiểm bảng năng lực so với mã")
    print(f"  dòng đối chiếu : {len(hang)}")
    print(f"  tệp nguồn đọc  : {len(nguon)}")

    khoi("Tệp khai trong bảng mà không có trong kho", thieu_tep)
    khoi("Ký hiệu khai trong bảng mà không có trong mã", thieu_ky_hieu)
    khoi("Dòng khai ĐỦ mà mã không có người gọi", thieu_nguoi_goi)
    khoi("Mã TC khai mà không tệp test nào nhắc", thieu_test)

    # Không tính vào số chỗ lệch: dòng đã khai MỘT PHẦN / CHƯA thì mã mồ côi là
    # điều nó đang nói, không phải điều nó giấu. Vẫn in ra để danh sách việc còn
    # nợ nằm ngay cạnh phép kiểm, khỏi phải mở Excel mới thấy.
    print(f"\n── Đã nhận là còn thiếu, nêu để theo dõi — {len(set(da_nhan))}")
    for m in sorted(set(da_nhan)):
        print(f"   · {m}")
    if not da_nhan:
        print("   ✓ không có")

    if args.chay_test:
        tep = sorted(tc_can_chay)
        print(f"\n── Chạy {len(tep)} tệp test được viện dẫn")
        kq = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *tep],
            cwd=GOC, capture_output=True, text=True,
        )
        cuoi = [d for d in kq.stdout.splitlines() if d.strip()][-1:]
        print("   " + (cuoi[0] if cuoi else "không đọc được kết quả"))
        for d in kq.stdout.splitlines():
            if d.startswith("FAILED"):
                print(f"   ✗ {d}")
                do += 1

    print(f"\n{'ĐẠT — bảng khớp mã' if do == 0 else f'{do} chỗ bảng lệch mã'}")
    return 0 if do == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
