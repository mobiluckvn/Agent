"""Chạy bộ ca xấu (unhappy case) và ghi lại kết quả nguyên văn.

Cách dùng::

    python scripts/chay_ca_xau.py            # chạy hết, in bảng
    python scripts/chay_ca_xau.py --ma C-03  # chạy một ca

Vì sao là một script chứ không phải một bộ pytest
--------------------------------------------------

Bộ test có sẵn (1.966 bài) đã canh những đường xấu mà thiết kế lường trước.
Script này làm việc khác: nó **chạy sản phẩm như một người dùng đang gõ sai**,
và chấm câu trả lời theo tiêu chí của người dùng chứ không của lập trình viên:

* Có sập không (traceback lọt ra ngoài là hỏng).
* Mã thoát có ĐÚNG NGHĨA không — 2 là *đang chờ người*, không phải lỗi.
* Thông điệp có nói **phải làm gì tiếp** không, hay chỉ nói *sai rồi*.

Tiêu chí thứ ba là tiêu chí khó nhất và cũng là tiêu chí duy nhất người dùng
thật sự quan tâm. Một lỗi đúng mà không chỉ được đường ra thì với người đang
kẹt, nó không khác gì một lỗi sai.

Script chạy lại được: nó tự dựng hồ sơ hỏng trong thư mục tạm, không đụng vào
dự án thật.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
PY = sys.executable

#: Mã thoát theo EAA-SDD-03 §6.
TEN_MA = {0: "ok", 1: "lỗi chung", 2: "ĐANG CHỜ NGƯỜI", 3: "hết lượt tự sửa",
          4: "lỗi môi trường"}


@dataclass
class CaXau:
    ma: str
    ten: str
    #: Vì sao ca này đáng thử — phần này đi thẳng vào nhật ký.
    ly_do: str
    argv: list[str]
    #: Mã thoát chấp nhận được. Rỗng nghĩa là chỉ cần không sập.
    ma_thoat_mong_doi: tuple[int, ...] = ()
    #: Chuỗi PHẢI có trong đầu ra — đây là chỗ chấm "có chỉ đường ra không".
    phai_co: tuple[str, ...] = ()
    #: Chuỗi KHÔNG được có.
    khong_duoc_co: tuple[str, ...] = ()
    #: Hàm dựng hồ sơ hỏng, nhận thư mục tạm, trả về map thay thế cho argv.
    dung: object = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class KetQua:
    ca: CaXau
    ma_thoat: int
    ra: str
    dat: bool
    vi_sao: str


# ══════════════════════════ hồ sơ hỏng ══════════════════════════


def _zip_hong(tmp: Path) -> dict[str, str]:
    p = tmp / "hong.zip"
    p.write_bytes(b"PK\x03\x04" + b"r\xc3\xa1c kh\xc3\xb4ng ph\xe1\xba\xa3i zip")
    return {"TEP": str(p), "DUAN": str(_du_an_thu(tmp))}


def _tep_rong(tmp: Path) -> dict[str, str]:
    p = tmp / "rong.zip"
    p.write_bytes(b"")
    return {"TEP": str(p), "DUAN": str(_du_an_thu(tmp))}


def _pdf_gia(tmp: Path) -> dict[str, str]:
    """Đúng đuôi, sai nội dung — đây là ca nguy hiểm nhất trong nhóm hồ sơ."""
    du_an = _du_an_thu(tmp)
    p = du_an / "sources" / "khong_phai_pdf.pdf"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("Đây là văn bản thường, người dùng đổi đuôi tệp.", encoding="utf-8")
    return {"DUAN": str(du_an), "TEP": "khong_phai_pdf.pdf"}


def _yaml_sai(tmp: Path) -> dict[str, str]:
    du_an = _du_an_thu(tmp)
    (du_an / "constraints.yaml").write_text(
        "mcu: atmega328p\n  pins: [\n   - hong\n", encoding="utf-8")
    return {"DUAN": str(du_an)}


def _du_an_bien_mat(tmp: Path) -> dict[str, str]:
    du_an = tmp / "da_xoa"
    return {"DUAN": str(du_an)}


def _du_an_thu(tmp: Path) -> Path:
    """Bản sao dự án mẫu — để làm hỏng mà không đụng dự án thật."""
    dich = tmp / "du_an_thu"
    if not dich.exists():
        shutil.copytree(GOC / "projects" / "robot_balance", dich)
    return dich


def _state_hong(tmp: Path) -> dict[str, str]:
    du_an = _du_an_thu(tmp)
    (du_an / "project_state.json").write_text("{ khong phai json", encoding="utf-8")
    return {"DUAN": str(du_an)}


def _gate_sua_tay(tmp: Path) -> dict[str, str]:
    """Người sửa tay tệp gate để tự duyệt cho mình — bất biến trung tâm."""
    du_an = _du_an_thu(tmp)
    g = du_an / "gates"
    g.mkdir(exist_ok=True)
    (g / "G3_drv_gia.json").write_text(json.dumps({
        "gate": "G3", "module": "drv_gia", "status": "approved",
        "approved_by": "toi_tu_go_vao", "evidence": [],
    }, ensure_ascii=False), encoding="utf-8")
    return {"DUAN": str(du_an)}


def _du_an_binh_thuong(tmp: Path) -> dict[str, str]:
    return {"DUAN": str(_du_an_thu(tmp))}


# ══════════════════════════ bộ ca ══════════════════════════

CA: tuple[CaXau, ...] = (
    CaXau(
        "C-01", "Kho nén hỏng",
        "Người dùng tải một tệp .zip đứt giữa chừng. Bộ giải nén phải nói tệp "
        "hỏng, không được ném traceback của zipfile.",
        ["--project", "DUAN", "survey", "TEP"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_zip_hong,
    ),
    CaXau(
        "C-02", "Tệp rỗng 0 byte",
        "Hay gặp khi tải hụt. Rỗng KHÁC hỏng, và thông điệp nên phân biệt được.",
        ["--project", "DUAN", "survey", "TEP"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_tep_rong,
    ),
    CaXau(
        "C-03", "Tệp .pdf nhưng ruột không phải PDF",
        "Ca nguy hiểm nhất nhóm hồ sơ: đúng đuôi thì mọi lớp phía trên tin là "
        "PDF. Nếu bộ đọc trả về chuỗi rỗng thay vì báo lỗi, cả hệ hiểu thành "
        "'tài liệu này trống' — gần đúng tệ hơn hỏng hẳn.",
        ["--project", "DUAN", "survey", "--read", "TEP"],
        ma_thoat_mong_doi=(1, 4),
        phai_co=("PDF",),
        khong_duoc_co=("Traceback",),
        dung=_pdf_gia,
    ),
    CaXau(
        "C-04", "constraints.yaml sai cú pháp",
        "Người sửa tay ràng buộc rồi thụt lề lệch. Thông điệp phải chỉ ra TỆP "
        "nào — một lỗi 'yaml.scanner.ScannerError' trần không nói được tệp.",
        ["--project", "DUAN", "budget", "show"],
        ma_thoat_mong_doi=(1, 4),
        phai_co=("constraints.yaml", "YAML"),
        khong_duoc_co=("Traceback",),
        dung=_yaml_sai,
    ),
    CaXau(
        "C-05", "Project State hỏng JSON",
        "Đây là tệp sống sót qua crash (TC-03). Nếu chính nó hỏng thì hệ phải "
        "nói ra chứ không được im lặng dựng một state rỗng đè lên.",
        ["--project", "DUAN", "status"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_state_hong,
    ),
    CaXau(
        "C-06", "Thư mục dự án không tồn tại",
        "Gõ nhầm tên dự án. Thông điệp nên gợi ý dự án đang có.",
        ["--project", "DUAN", "status"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_du_an_bien_mat,
    ),
    CaXau(
        "C-07", "Đường dẫn leo ra ngoài dự án",
        "'../../etc/passwd' trong tham số đọc tệp. Đường dẫn này do MÔ HÌNH "
        "điền được, nên nó là bề mặt tấn công thật chứ không phải giả tưởng.",
        ["--project", "DUAN", "survey", "--read", "../../../../etc/passwd"],
        ma_thoat_mong_doi=(1, 4),
        phai_co=("ngoài",),
        khong_duoc_co=("root:", "Traceback"),
        dung=_du_an_binh_thuong,
    ),
    CaXau(
        "C-08", "Gate bị sửa tay thành approved",
        "Bất biến trung tâm: merge chỉ khi mọi ToolReport passed VÀ G3 approved "
        "VÀ bằng chứng phủ đủ. Một tệp gate chép tay, bằng chứng rỗng, KHÔNG "
        "được mở đường merge.",
        ["--project", "DUAN", "gate", "show", "G3"],
        ma_thoat_mong_doi=(0, 1, 2, 4),
        khong_duoc_co=("Traceback",),
        dung=_gate_sua_tay,
    ),
    CaXau(
        "C-09", "Nhà cung cấp thật nhưng KHÔNG có khóa API",
        "Chạy trên máy CI hoặc máy mới. Phải nói rõ tên biến môi trường cần "
        "đặt, và tuyệt đối không in ra thứ gì giống khóa.",
        ["--project", "DUAN", "chat", "xin chào"],
        ma_thoat_mong_doi=(1, 4),
        phai_co=("EAA_LLM_KEY",),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
        env={"EAA_LLM_KEY": "", "EAA_LLM_PROVIDER": "gemini"},
    ),
    CaXau(
        "C-10", "Mất mạng giữa chừng",
        "EAA_NO_NET=1 mô phỏng máy không có lối ra mạng. Lệnh tra web phải "
        "hỏng SẠCH và nói ra là vì mạng, không phải vì không tìm thấy gì.",
        ["--project", "DUAN", "research", "ATmega328P TWI"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
        env={"EAA_NO_NET": "1"},
    ),
    CaXau(
        "C-11", "Mã model không tồn tại",
        "Người dùng gõ sai mã model. Phải nói mã không tồn tại và chỉ sang "
        "'eaa models', không trả về một lỗi mạng chung chung.",
        ["--project", "DUAN", "--model", "gemini-khong-co-that", "chat", "xin chào"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
    ),
    CaXau(
        "C-12", "Tên module sai định dạng",
        "Mã module thành tên nhánh Git. Một chuỗi có khoảng trắng hay dấu gạch "
        "phải bị chặn tại chỗ nhập, không phải lúc tạo nhánh.",
        ["--project", "DUAN", "plan", "add", "drv x --uses twi"],
        ma_thoat_mong_doi=(1, 4),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
    ),
    CaXau(
        "C-13", "Lệnh không tồn tại",
        "Gõ nhầm tên lệnh — ca tầm thường nhất, và cũng là ca đầu tiên người "
        "dùng mới gặp.",
        ["--project", "DUAN", "khong-co-lenh-nay"],
        ma_thoat_mong_doi=(2,),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
    ),
    CaXau(
        "C-14", "Thiếu tham số bắt buộc",
        "Bỏ trống tham số. argparse lo được, nhưng phải kiểm là nó KHÔNG chạy "
        "tiếp với giá trị rỗng.",
        ["--project", "DUAN", "playbook", "record"],
        ma_thoat_mong_doi=(2,),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
    ),
    CaXau(
        "C-15", "Duyệt gate cho một module không tồn tại",
        "Người gõ nhầm tên module lúc duyệt. Duyệt nhầm là chuyện nghiêm trọng "
        "nhất trong hệ này, nên chỗ này phải từ chối rõ ràng.",
        ["--project", "DUAN", "gate", "approve", "G3", "module_khong_ton_tai"],
        ma_thoat_mong_doi=(1, 2, 4),
        khong_duoc_co=("Traceback",),
        dung=_du_an_binh_thuong,
    ),
)


def chay(ca: CaXau, tmp_goc: Path) -> KetQua:
    tmp = tmp_goc / ca.ma
    tmp.mkdir(parents=True, exist_ok=True)
    thay = ca.dung(tmp) if ca.dung else {}

    argv = [thay.get(a, a) for a in ca.argv]
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # Đặt thành chuỗi rỗng chứ KHÔNG xóa: load_env_file() nạp .env cho biến
    # nào chưa có trong môi trường, nên xóa biến đi lại thành nạp khóa thật từ
    # .env — đúng ca C-09 muốn kiểm thì lại không kiểm được gì.
    for k, v in ca.env.items():
        env[k] = v

    try:
        p = subprocess.run([PY, "-m", "eaa.cli", *argv], cwd=GOC, env=env,
                           capture_output=True, text=True, timeout=180)
        ra = (p.stdout + p.stderr).strip()
        ma_thoat = p.returncode
    except subprocess.TimeoutExpired:
        return KetQua(ca, -1, "(quá 180 giây)", False, "treo quá hạn giờ")

    ly_do = []
    if "Traceback (most recent call last)" in ra:
        ly_do.append("SẬP: traceback lọt ra ngoài")
    for s in ca.khong_duoc_co:
        if s != "Traceback" and s in ra:
            ly_do.append(f"đầu ra chứa chuỗi cấm {s!r}")
    for s in ca.phai_co:
        if s.lower() not in ra.lower():
            ly_do.append(f"đầu ra thiếu {s!r}")
    if ca.ma_thoat_mong_doi and ma_thoat not in ca.ma_thoat_mong_doi:
        ly_do.append(f"mã thoát {ma_thoat}, mong đợi {ca.ma_thoat_mong_doi}")
    # Khóa API không bao giờ được lọt ra (NFR-06, TC-14).
    khoa = os.environ.get("EAA_LLM_KEY", "")
    if khoa and len(khoa) > 8 and khoa in ra:
        ly_do.append("KHÓA API LỌT RA ĐẦU RA")

    return KetQua(ca, ma_thoat, ra, not ly_do, "; ".join(ly_do) or "đạt")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ma", default="", help="Chỉ chạy một ca, ví dụ C-03")
    ap.add_argument("--dai", action="store_true", help="In toàn bộ đầu ra từng ca")
    args = ap.parse_args()

    bo = [c for c in CA if not args.ma or c.ma == args.ma]
    if not bo:
        print(f"Không có ca {args.ma}")
        return 1

    tmp_goc = Path(tempfile.mkdtemp(prefix="eaa_ca_xau_"))
    ket: list[KetQua] = []
    try:
        for c in bo:
            k = chay(c, tmp_goc)
            ket.append(k)
            dau = "ĐẠT " if k.dat else "HỎNG"
            print(f"[{dau}] {c.ma} {c.ten}")
            print(f"        mã thoát {k.ma_thoat} ({TEN_MA.get(k.ma_thoat, '?')})"
                  f" · {k.vi_sao}")
            if args.dai or not k.dat:
                for dong in k.ra.splitlines()[:14]:
                    print(f"        │ {dong}")
            print()
    finally:
        shutil.rmtree(tmp_goc, ignore_errors=True)

    hong = [k for k in ket if not k.dat]
    print("═" * 62)
    print(f"{len(ket) - len(hong)}/{len(ket)} ca xử lý đúng.")
    for k in hong:
        print(f"  HỎNG {k.ca.ma} {k.ca.ten} — {k.vi_sao}")
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
