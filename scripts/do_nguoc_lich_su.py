#!/usr/bin/env python3
"""V3 — chạy bốn bộ dò NGƯỢC lên 13 lần từ chối G3 của lịch sử dự án.

Chân lý nền chốt trước ở `docs/CHAN_LY_NEN_V3.md`, commit TRƯỚC tệp này và
không được sửa sau khi thấy kết quả.

Ba nguồn, cả ba viết trước khi bộ dò tồn tại
---------------------------------------------

* `gates/decisions.jsonl` — 13 lần từ chối G3 kèm lý do nguyên văn;
* `llm_calls.jsonl` — 214 lượt gọi, đủ phản hồi, tức đủ mã ứng viên;
* kho firmware lồng — các bản đã merge.

Dựng lại trạng thái tệp
------------------------

Một lượt vá trong vòng tự sửa chỉ trả về tệp nó sửa, nên không lượt gọi nào
mang đủ module. Bộ chạy **chồng** từng lượt lên trạng thái trước đó, đúng thứ
tự thời gian — ``cu`` là trạng thái NGAY TRƯỚC ứng viên bị từ chối, ``moi`` là
trạng thái sau khi chồng ứng viên ấy.

Ba con số tách riêng, không gộp
--------------------------------

**BẮT ĐƯỢC** · **BỎ SÓT** (trong tầm tự khai, đủ dữ liệu, mà im — con số duy
nhất tính là thất bại) · **KHÔNG CHẠY ĐƯỢC / NGOÀI TẦM**. Gộp hai cái sau là
cách dễ nhất để bảng nói dối.

Chạy: python3 scripts/do_nguoc_lich_su.py
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from eaa import contract, instrument, sensitivity  # noqa: E402
from eaa.tools.base import CodeArtifact  # noqa: E402
from eaa.tools.regcheck import RegCheckGate  # noqa: E402

DU_AN = pathlib.Path("projects/robot_balance")
QUYET_DINH = DU_AN / "gates/decisions.jsonl"
LUOT_GOI = DU_AN / "llm_calls.jsonl"
RA = pathlib.Path("docs/V3_ket_qua_do_nguoc.json")

_KHOI = re.compile(r"```file:(?P<duong>[^\n]+)\n(?P<than>.*?)```", re.S)


def doc_jsonl(p: pathlib.Path) -> list[dict]:
    return [json.loads(d) for d in p.read_text().splitlines() if d.strip()]


def tep_trong(phan_hoi: str) -> dict[str, str]:
    return {m.group("duong").strip(): m.group("than") for m in _KHOI.finditer(phan_hoi)}


def ghep_cap() -> list[dict]:
    """13 lần từ chối, mỗi lần kèm trạng thái tệp trước và sau ứng viên ấy."""
    tu_choi = sorted(
        (x for x in doc_jsonl(QUYET_DINH)
         if x["decision"] == "rejected" and x["gate_id"] == "G3"),
        key=lambda x: x["decided_at"],
    )
    goi = sorted(
        (x for x in doc_jsonl(LUOT_GOI)
         if x.get("response") and "```file:" in x["response"]),
        key=lambda x: x["called_at"],
    )

    ra: list[dict] = []
    for i, tc in enumerate(tu_choi, 1):
        mod, luc = tc["module"], tc["decided_at"]
        truoc = [g for g in goi if g.get("module") == mod and g["called_at"] < luc]
        if not truoc:
            ra.append({"so": i, "luc": luc, "module": mod, "ly_do": tc["reason"],
                       "cu": {}, "moi": {}, "moi_luc": None, "so_luot_truoc": 0})
            continue
        # Chồng mọi lượt TRƯỚC ứng viên cuối → trạng thái cũ.
        cu: dict[str, str] = {}
        for g in truoc[:-1]:
            cu.update(tep_trong(g["response"]))
        moi = dict(cu)
        moi.update(tep_trong(truoc[-1]["response"]))
        ra.append({
            "so": i, "luc": luc, "module": mod, "ly_do": tc["reason"],
            "cu": cu, "moi": moi,
            "moi_luc": truoc[-1]["called_at"], "so_luot_truoc": len(truoc),
        })
    return ra


def _ham_cong_khai_module_khac(mod: str, luc: str) -> set[str]:
    """Hàm công khai của các module KHÁC, lấy từ kho firmware tại thời điểm ấy.

    Không lấy được từ `llm_calls.jsonl`: mỗi lượt gọi chỉ trả tệp của chính
    module nó sinh, nên trạng thái dựng lại KHÔNG bao giờ chứa header của module
    khác. Thiếu chỗ này thì `mat_loi_goi` luôn nhận tập rỗng và luôn im — và
    cái im ấy là lỗi của bộ chạy, không phải của bộ dò.
    """
    kho = DU_AN / "firmware"
    try:
        ma = subprocess.run(
            ["git", "-C", str(kho), "rev-list", "-1", f"--before={luc}", "HEAD"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        if not ma:
            return set()
        ds = subprocess.run(
            ["git", "-C", str(kho), "ls-tree", "-r", "--name-only", ma],
            capture_output=True, text=True, timeout=30,
        ).stdout.split()
    except (subprocess.SubprocessError, OSError):
        return set()

    ra: set[str] = set()
    for d in ds:
        if not d.endswith(".h") or d.endswith(f"{mod}.h"):
            continue
        than = subprocess.run(
            ["git", "-C", str(kho), "show", f"{ma}:{d}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        ra |= set(contract.khai_bao_ham(than))
    return ra


def _tep_chinh(tep: dict[str, str], mod: str) -> str:
    for k, v in tep.items():
        if k.endswith(f"{mod}.c"):
            return v
    return ""


def _tep_kiem(tep: dict[str, str]) -> tuple[str, str]:
    for k, v in sorted(tep.items()):
        if k.endswith(".py"):
            return k, v
    return "", ""


# ── bốn bộ dò ────────────────────────────────────────────────────────────────


def _tep_dau(tep: dict[str, str], mod: str) -> str:
    for k, v in tep.items():
        if k.endswith(f"{mod}.h"):
            return v
    return ""


def chay_contract(c: dict) -> dict:
    cu, moi = _tep_chinh(c["cu"], c["module"]), _tep_chinh(c["moi"], c["module"])
    if not cu:
        return {"trang_thai": "KHÔNG CHẠY ĐƯỢC", "vi_sao": "không có bản cũ"}

    # HỢP ĐỒNG nằm ở tệp đầu, không ở tệp thân: so `.h` với `.h`. So thân với
    # thân thì một hàm bị bỏ khỏi `.c` mà vẫn khai trong `.h` sẽ lọt — và đó là
    # đúng hình dạng của lần từ chối #9.
    dau_cu, dau_moi = _tep_dau(c["cu"], c["module"]), _tep_dau(c["moi"], c["module"])
    pha = contract.pha_vo_hop_dong(dau_cu, dau_moi) if dau_cu else []
    pha += [x for x in contract.pha_vo_hop_dong(cu, moi) if x not in pha]

    quan_tam = _ham_cong_khai_module_khac(c["module"], c["luc"])
    return {
        "trang_thai": "ĐÃ CHẠY",
        "pha_hop_dong": pha,
        "mat_loi_goi": contract.mat_loi_goi(cu, moi, frozenset(quan_tam)),
        "so_ham_module_khac": len(quan_tam),
    }


def chay_instrument(c: dict) -> dict:
    cu, moi = _tep_chinh(c["cu"], c["module"]), _tep_chinh(c["moi"], c["module"])
    if not cu:
        return {"trang_thai": "KHÔNG CHẠY ĐƯỢC", "vi_sao": "không có bản cũ"}
    _, kiem = _tep_kiem(c["moi"])
    nv = instrument.nghi_van_chinh_do_do(cu, moi, nguon_test=kiem, tep=c["module"])
    return {"trang_thai": "ĐÃ CHẠY",
            "dau_vet": [str(d) for d in nv.dau_vet]}


def chay_sensitivity(c: dict, *, chay_that: bool = True) -> dict:
    ten_kiem, kiem_moi = _tep_kiem(c["moi"])
    if not kiem_moi:
        return {"trang_thai": "KHÔNG CHẠY ĐƯỢC", "vi_sao": "ứng viên không có tệp kiểm"}
    _, kiem_cu = _tep_kiem(c["cu"])
    bai_moi = sensitivity.bai_kiem_doi(kiem_cu or None, kiem_moi)
    if not _tep_chinh(c["cu"], c["module"]):
        return {"trang_thai": "KHÔNG CHẠY ĐƯỢC", "vi_sao": "không có mã cũ để chạy",
                "bai_kiem_moi": list(bai_moi)}
    if not bai_moi:
        return {"trang_thai": "ĐÃ CHẠY", "bai_kiem_moi": [],
                "ket_luan": "không bài kiểm nào mới hoặc đổi"}
    if not chay_that:
        return {"trang_thai": "NỬA TĨNH", "bai_kiem_moi": list(bai_moi)}

    # Chạy THẬT: mã CŨ + bài kiểm MỚI. Bài kiểm nào không đỏ là bài không
    # chứng minh được gì.
    with tempfile.TemporaryDirectory() as d:
        goc = pathlib.Path(d)
        (goc / "src").mkdir()
        (goc / "tests").mkdir()
        for duong, than in c["cu"].items():
            if duong.endswith((".c", ".h")):
                (goc / duong).parent.mkdir(parents=True, exist_ok=True)
                (goc / duong).write_text(than)
        (goc / ten_kiem).parent.mkdir(parents=True, exist_ok=True)
        (goc / ten_kiem).write_text(kiem_moi)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-rfEs", "-q", "--no-header",
                 "-p", "no:cacheprovider", str(goc / ten_kiem)],
                capture_output=True, text=True, timeout=180, cwd=goc,
            )
            dau_ra = r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return {"trang_thai": "KHÔNG CHẠY ĐƯỢC", "vi_sao": "quá giờ",
                    "bai_kiem_moi": list(bai_moi)}

    kq = sensitivity.ket_luan(bai_moi, dau_ra)
    return {
        "trang_thai": "ĐÃ CHẠY",
        "bai_kiem_moi": list(bai_moi),
        "phan_biet_duoc": list(kq.phan_biet_duoc),
        "khong_phan_biet": list(kq.khong_phan_biet),
        "dat": kq.dat,
        "cau": kq.cau(),
    }


def chay_regcheck(c: dict) -> dict:
    """Không khai bản đồ ⇒ cổng ĐẠT và im. Đây là kết quả đã dự đoán trước."""
    bao = RegCheckGate(regmap=None).run(
        CodeArtifact(files=dict(c["moi"]))
    )
    return {"trang_thai": "KHÔNG ĐO ĐƯỢC" if bao.metrics.get("skipped") else "ĐÃ CHẠY",
            "vi_sao": bao.metrics.get("skipped", ""),
            "passed": bao.passed, "so_loi": len(bao.errors)}


# ── quét MỌI lượt vá, không chỉ 13 điểm từ chối ──────────────────────────────


def quet_moi_luot() -> list[dict]:
    """Chạy contract + instrument trên TỪNG cặp lượt sinh liền kề.

    13 điểm từ chối chỉ là chỗ NGƯỜI dừng lại đọc. Một khuyết tật có thể lọt
    vào từ một lượt vá sớm hơn và nằm im tới lúc ấy — và đó chính là chuyện đã
    xảy ra với ``imu_start_read()``. Quét mọi lượt trả lời được câu mà quét 13
    điểm không trả lời được: **bộ dò kêu sớm hơn người bao lâu**.
    """
    goi = sorted(
        (x for x in doc_jsonl(LUOT_GOI)
         if x.get("response") and "```file:" in x["response"] and x.get("module")),
        key=lambda x: x["called_at"],
    )
    theo_mod: dict[str, dict[str, str]] = {}
    ra: list[dict] = []
    for g in goi:
        mod = g["module"]
        cu = dict(theo_mod.get(mod, {}))
        moi = dict(cu)
        moi.update(tep_trong(g["response"]))
        theo_mod[mod] = moi
        if not cu:
            continue
        gia = {"so": 0, "luc": g["called_at"], "module": mod, "cu": cu, "moi": moi}
        kc, ki = chay_contract(gia), chay_instrument(gia)
        keu = (kc.get("pha_hop_dong") or []) + (kc.get("mat_loi_goi") or [])
        if keu or ki.get("dau_vet"):
            ra.append({
                "luc": g["called_at"], "module": mod,
                "contract": keu, "instrument": ki.get("dau_vet", []),
            })
    return ra


# ── báo cáo ──────────────────────────────────────────────────────────────────


def main() -> int:
    if not QUYET_DINH.exists():
        print(f"Không thấy {QUYET_DINH}", file=sys.stderr)
        return 1
    if not shutil.which("cc"):
        print("Cần trình dịch `cc` để chạy nửa động của sensitivity", file=sys.stderr)

    cap = ghep_cap()
    print(f"{len(cap)} lần từ chối G3 — chạy bốn bộ dò\n")

    for c in cap:
        c["contract"] = chay_contract(c)
        c["instrument"] = chay_instrument(c)
        c["sensitivity"] = chay_sensitivity(c)
        c["regcheck"] = chay_regcheck(c)

        keu = []
        if c["contract"].get("pha_hop_dong"):
            keu.append(f"contract:hợp đồng×{len(c['contract']['pha_hop_dong'])}")
        if c["contract"].get("mat_loi_goi"):
            keu.append(f"contract:mất gọi×{len(c['contract']['mat_loi_goi'])}")
        if c["instrument"].get("dau_vet"):
            keu.append(f"instrument×{len(c['instrument']['dau_vet'])}")
        if c["sensitivity"].get("khong_phan_biet"):
            keu.append(f"sensitivity×{len(c['sensitivity']['khong_phan_biet'])}")
        print(f"{c['so']:>2}  {c['module']:<12} {' · '.join(keu) or '— im —'}")

    print("\n── quét MỌI lượt vá (không chỉ 13 điểm từ chối) ──")
    quet = quet_moi_luot()
    print(f"{len(quet)} lượt vá có bộ dò kêu\n")
    tu_choi_luc = sorted((c["luc"], c["so"], c["module"]) for c in cap)
    for q in quet:
        sau = next((f"#{s} lúc {l[:19]}" for l, s, m in tu_choi_luc
                    if m == q["module"] and l > q["luc"]), "— không lần từ chối nào sau đó —")
        gio = ""
        if sau.startswith("#"):
            from datetime import datetime
            t1 = datetime.fromisoformat(q["luc"][:19])
            t2 = datetime.fromisoformat(sau.split("lúc ")[1])
            gio = f"  (sớm hơn {int((t2 - t1).total_seconds() // 60)} phút)"
        print(f"  {q['luc'][:19]} {q['module']:<12} → người dừng ở {sau}{gio}")
        for d in q["contract"]:
            print(f"      contract  · {d.splitlines()[0]}")
        for d in q["instrument"]:
            print(f"      instrument· {d[:110]}")

    RA.parent.mkdir(parents=True, exist_ok=True)
    for c in cap:            # bỏ mã nguồn khỏi tệp kết quả cho gọn
        c.pop("cu", None)
        c.pop("moi", None)
    RA.write_text(json.dumps({"tu_choi": cap, "quet_moi_luot": quet},
                             ensure_ascii=False, indent=1))
    print(f"\nĐã ghi {RA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
