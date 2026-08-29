"""Kiểm độ ổn định của Agent — chạy lại được, không phải một lần rồi thôi.

Chạy: python scripts/kiem_on_dinh.py [--nhanh]

Bộ test đơn vị trả lời câu "từng mảnh có đúng không". Script này trả lời câu
khác: **dùng thật thì có ổn không** — và nó kiểm những thứ mà test đơn vị theo
định nghĩa không thấy:

* Chạy lại nhiều lượt có ra cùng kết quả không (test phụ thuộc thứ tự, hoặc
  phụ thuộc trạng thái sót lại, sẽ lộ ra ở lượt thứ hai chứ không phải lượt đầu).
* Mọi lệnh có nạp được không — một lỗi nhập khẩu trong một nhánh hiếm chỉ hiện
  ra khi ai đó gõ đúng lệnh ấy.
* Lệnh chỉ-đọc có chạy sạch trên dự án THẬT không, chứ không chỉ trên dữ liệu
  dựng sẵn trong test.
* Chạy xong có để lại rác trong kho không.

Mỗi mục in ĐẠT / KHÔNG ĐẠT kèm lý do. Không mục nào "gần đạt".
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
PY = str(GOC / ".venv" / "bin" / "python")


@dataclass
class KetQua:
    ten: str
    dat: bool
    chi_tiet: str = ""
    dong: list[str] = field(default_factory=list)

    def render(self) -> str:
        nhan = "ĐẠT     " if self.dat else "KHÔNG ĐẠT"
        van_ban = f"  [{nhan}] {self.ten}"
        if self.chi_tiet:
            van_ban += f" — {self.chi_tiet}"
        for d in self.dong:
            van_ban += f"\n            {d}"
        return van_ban


def _chay(*argv: str, cwd: Path | None = None, env: dict | None = None,
          timeout: int = 600) -> subprocess.CompletedProcess:
    moi_truong = {**os.environ, **(env or {})}
    return subprocess.run(
        list(argv), cwd=str(cwd or GOC), env=moi_truong,
        capture_output=True, text=True, timeout=timeout,
    )


# --------------------------------------------------------------------------
# A — chạy lại nhiều lượt có ra cùng kết quả không
# --------------------------------------------------------------------------


def kiem_lap_lai(so_luot: int = 3) -> KetQua:
    """Test phụ thuộc thứ tự hoặc trạng thái sót lại lộ ra ở lượt thứ hai."""
    import re as _re

    ket: list[str] = []
    for i in range(so_luot):
        r = _chay(PY, "-m", "pytest", "-q", timeout=900)
        dong_cuoi = [d for d in r.stdout.splitlines() if "passed" in d or "failed" in d]
        tho = dong_cuoi[-1].strip() if dong_cuoi else f"(lượt {i+1}: không đọc được)"
        # So SỐ LƯỢNG, không so thời gian chạy: bản đầu của hàm này so nguyên
        # dòng tóm tắt, mà dòng ấy có cả "in 137.90s" — nên ba lượt cùng ra
        # 1035 passed vẫn bị báo là khác nhau. Một phép so bắt cả thứ vốn dĩ
        # phải khác thì nó đang đo nhiễu, không đo cái cần đo.
        so = _re.findall(r"(\d+)\s+(passed|failed|error[s]?|skipped)", tho)
        ket.append(", ".join(f"{n} {t}" for n, t in so) or tho)

    giong_nhau = len(set(ket)) == 1 and "failed" not in ket[0] and "error" not in ket[0]
    return KetQua(
        ten=f"Chạy toàn bộ test {so_luot} lượt liên tiếp",
        dat=giong_nhau,
        chi_tiet=ket[0] if giong_nhau else "kết quả KHÁC nhau giữa các lượt",
        dong=[] if giong_nhau else ket,
    )


# --------------------------------------------------------------------------
# B — mọi lệnh có nạp được không
# --------------------------------------------------------------------------


def kiem_moi_lenh_nap_duoc() -> KetQua:
    """Lỗi nhập khẩu trong một nhánh hiếm chỉ hiện ra khi ai đó gõ đúng lệnh ấy."""
    # Hỏi thẳng bộ phân tích tham số thay vì bóc văn bản trợ giúp: bản đầu của
    # hàm này cắt chữ đầu mỗi dòng thụt lề, nên nó nhặt cả một chữ trong câu mô
    # tả rồi báo "lệnh lỗi". Đọc cấu trúc bao giờ cũng chắc hơn đọc bản in.
    doc = _chay(
        PY, "-c",
        "import argparse, sys; sys.path.insert(0, '.');"
        "from eaa.cli import build_parser;"
        "print('\\n'.join(c for a in build_parser()._actions"
        " if isinstance(a, argparse._SubParsersAction) for c in a.choices))",
    )
    if doc.returncode != 0:
        return KetQua(
            "Mọi lệnh nạp được", False,
            (doc.stderr or doc.stdout).strip().splitlines()[-1:] and
            (doc.stderr or doc.stdout).strip().splitlines()[-1] or "không đọc được danh sách lệnh",
        )
    lenh = [d.strip() for d in doc.stdout.splitlines() if d.strip()]

    hong: list[str] = []
    for ten in lenh:
        con = _chay(PY, "-m", "eaa.cli", ten, "--help")
        if con.returncode != 0:
            dau = (con.stderr or con.stdout).strip().splitlines()
            hong.append(f"{ten}: {dau[-1] if dau else 'mã thoát ' + str(con.returncode)}")

    return KetQua(
        ten=f"Mọi lệnh nạp được ({len(lenh)} lệnh)",
        dat=not hong,
        chi_tiet="" if not hong else f"{len(hong)} lệnh lỗi",
        dong=hong,
    )


# --------------------------------------------------------------------------
# C — lệnh chỉ-đọc chạy sạch trên dự án THẬT
# --------------------------------------------------------------------------

#: Lệnh không đổi trạng thái gì. Chạy được trên dự án thật là bằng chứng dữ
#: liệu thật của dự án vẫn hợp lệ — thứ mà dữ liệu dựng sẵn trong test không nói.
CHI_DOC: tuple[tuple[str, ...], ...] = (
    ("status",),
    ("policy",),
    ("packs",),
    ("plan", "list"),
    ("doctor", "--discover"),
    ("ports",),
    ("ledger", "list"),
    ("docs", "list"),
    ("diagnose", "list"),
    ("decide", "--show"),
    ("flash", "--history"),
)


def kiem_lenh_chi_doc() -> KetQua:
    du_an = sorted(
        p for p in (GOC / "projects").iterdir() if (p / "constraints.yaml").is_file()
    )
    if not du_an:
        return KetQua("Lệnh chỉ-đọc trên dự án thật", False, "không có dự án nào")

    hong: list[str] = []
    so_lan = 0
    for p in du_an:
        for argv in CHI_DOC:
            so_lan += 1
            r = _chay(PY, "-m", "eaa.cli", *argv, env={"EAA_PROJECT": str(p)}, timeout=120)
            # Mã thoát 2 (chờ gate) và 4 (thiếu công cụ) là kết luận hợp lệ của
            # một lệnh chỉ-đọc; chỉ ngoại lệ chưa bắt mới là hỏng.
            if r.returncode not in (0, 2, 3, 4) or "Traceback" in r.stderr:
                dau = (r.stderr or r.stdout).strip().splitlines()
                hong.append(f"{p.name} · {' '.join(argv)}: {dau[-1] if dau else r.returncode}")

    return KetQua(
        ten=f"Lệnh chỉ-đọc trên {len(du_an)} dự án thật ({so_lan} lượt)",
        dat=not hong,
        chi_tiet="" if not hong else f"{len(hong)} lượt hỏng",
        dong=hong,
    )


# --------------------------------------------------------------------------
# D — vòng đời đầy đủ trên dự án tạm
# --------------------------------------------------------------------------


def kiem_vong_doi_day_du() -> KetQua:
    """Đi trọn từ brief tới build trên một dự án mới toanh, dùng adapter giả lập.

    Đây là phép kiểm gần nhất với việc một người mới mở hộp ra dùng.
    """
    pack_demo = GOC / "tests" / "fixtures" / "packs" / "demo"
    if not pack_demo.is_dir():
        return KetQua("Vòng đời đầy đủ", False, "thiếu pack giả lập")

    with tempfile.TemporaryDirectory() as tam:
        goc_tam = Path(tam)
        (goc_tam / "packs").mkdir()
        shutil.copytree(pack_demo, goc_tam / "packs" / "demo")
        du_an = goc_tam / "projects" / "thu"
        du_an.mkdir(parents=True)

        mau = GOC / "projects" / "robot_balance"
        for ten in ("constraints.yaml", "hardware_profile.yaml"):
            noi_dung = (mau / ten).read_text(encoding="utf-8")
            if ten == "constraints.yaml":
                noi_dung = "\n".join(
                    "platform: demo" if d.startswith("platform:") else d
                    for d in noi_dung.splitlines()
                )
            (du_an / ten).write_text(noi_dung, encoding="utf-8")
        shutil.copytree(mau / "datasheets", du_an / "datasheets")
        (du_an / "tests").mkdir()
        (du_an / "tests" / "test_khung.py").write_text(
            "def test_khung():\n    assert True\n", encoding="utf-8"
        )

        env = {
            "EAA_HOME": str(goc_tam),
            "EAA_PROJECT": str(du_an),
            "EAA_ACTOR": "kiem-on-dinh",
            "EAA_LLM_KEY": "",
        }
        buoc: list[tuple[tuple[str, ...], tuple[int, ...]]] = [
            (("init", "--provider", "mock"), (0,)),
            (("plan", "add", "drv_bus_sensor", "--uses", "twi,imu"), (0,)),
            (("gate", "approve", "G1"), (0, 2)),
            (("gate", "approve", "G2"), (0, 2)),
            (("resolve", "drv_bus_sensor"), (0, 2, 3)),
            (("gen", "drv_bus_sensor"), (2,)),
            (("gate", "approve", "G3"), (0,)),
            (("status",), (0,)),
            (("report", "kpi"), (0,)),
        ]

        hong: list[str] = []
        for argv, cho_phep in buoc:
            r = _chay(PY, "-m", "eaa.cli", *argv, env=env, timeout=300)
            if r.returncode not in cho_phep or "Traceback" in r.stderr:
                dau = (r.stderr or r.stdout).strip().splitlines()
                hong.append(
                    f"{' '.join(argv)}: mã {r.returncode} — "
                    f"{dau[-1] if dau else '(không có thông báo)'}"
                )
                break

        da_merge = (du_an / "firmware" / "src").is_dir()
        if not hong and not da_merge:
            hong.append("chạy hết các bước nhưng không có mã nào được merge")

    return KetQua(
        ten="Vòng đời đầy đủ trên dự án mới (brief → gen → merge)",
        dat=not hong,
        chi_tiet="" if not hong else "dừng giữa chừng",
        dong=hong,
    )


# --------------------------------------------------------------------------
# E — chạy xong có để lại rác không
# --------------------------------------------------------------------------


def _trang_thai_kho() -> set[str]:
    r = _chay("git", "status", "--porcelain")
    return {d for d in r.stdout.splitlines() if d.strip()} if r.returncode == 0 else set()


def kiem_khong_de_lai_rac(truoc: set[str]) -> KetQua:
    """Chạy kiểm mà làm bẩn kho là chính phép kiểm gây ra tác dụng phụ.

    So TRƯỚC với SAU chứ không đòi kho phải sạch sẵn: người chạy script này
    thường đang có việc dở dang, và bắt họ commit trước mới kiểm được là một
    yêu cầu vô cớ.
    """
    them = sorted(_trang_thai_kho() - truoc)
    return KetQua(
        ten="Chạy kiểm không làm bẩn kho",
        dat=not them,
        chi_tiet="" if not them else f"{len(them)} tệp mới thay đổi",
        dong=them[:10],
    )


# --------------------------------------------------------------------------


def main() -> int:
    dt = argparse.ArgumentParser(description="Kiểm độ ổn định của Agent")
    dt.add_argument("--nhanh", action="store_true", help="Chỉ chạy test một lượt")
    tham_so = dt.parse_args()

    print("Kiểm độ ổn định — Embedded AIDD Agent")
    print("═" * 70)

    truoc = _trang_thai_kho()
    ket_qua = [
        kiem_moi_lenh_nap_duoc(),
        kiem_lenh_chi_doc(),
        kiem_vong_doi_day_du(),
        kiem_lap_lai(1 if tham_so.nhanh else 3),
        kiem_khong_de_lai_rac(truoc),
    ]

    for k in ket_qua:
        print(k.render())

    print("═" * 70)
    hong = [k for k in ket_qua if not k.dat]
    if hong:
        print(f"KHÔNG ỔN ĐỊNH — {len(hong)}/{len(ket_qua)} mục không đạt.")
        return 1
    print(f"ỔN ĐỊNH — {len(ket_qua)}/{len(ket_qua)} mục đạt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
