"""Xưởng công cụ — Agent tự viết công cụ cho chính nó, và người duyệt.

EAA-AIS-05 §9 (môi trường công cụ), §12; FR-ENV-03, NFR-05, NFR-06.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-77.

Nghịch lý module này gỡ
------------------------

Agent sinh mã nhúng qua sáu cổng kiểm chứng, nhưng bốn mươi công cụ của chính
nó đều do người gõ tay. Gặp một việc lặp đi lặp lại mà chưa ai viết lệnh cho —
đổi định dạng một tệp nhật ký, gom số liệu từ mấy bản báo cáo — nó chỉ biết
bảo người dùng tự làm.

Ranh giới quyền vẫn phải nhìn thấy được trong lịch sử Git
----------------------------------------------------------

Đây là chỗ dễ làm hỏng nhất. Nếu Agent tự viết mã Python rồi tự nạp vào danh
mục công cụ, thì danh mục ấy không còn đọc được từ ``eaa/agent.py``, và câu
"Agent này được phép làm gì" không còn trả lời được bằng cách đọc một tệp.

Nên cấu trúc ở đây tách làm hai tầng, và chỉ tầng dưới là động:

* **Quyền chạy công cụ tự sinh** là MỘT mục tĩnh trong ``TOOLBOX``:
  ``tool run``. Nó nằm trong Git, thấy được, đổi được bằng một commit.
* **Danh sách công cụ tự sinh** là DỮ LIỆU, và mỗi mục chỉ chạy được sau khi
  một người duyệt. Agent đề xuất; ``eaa tool approve`` không nằm trong TOOLBOX.

Nói cách khác: Agent mở rộng được *cái nó làm*, không mở rộng được *quyền nó
có*. Hai thứ ấy hay bị gộp làm một, và gộp lại là mất luôn tính kiểm được.

Ba cổng trước khi một công cụ chạy được
----------------------------------------

1. **Cổng cấu tạo** — mã phải có ``run()``, có ``SCHEMA``, có ``MO_TA``, có ít
   nhất một hàm ``test_``. Thiếu bất kỳ cái nào thì nó không phải một công cụ,
   nó là một đoạn mã.
2. **Cổng an toàn** — quét những cấu trúc không được có: ``eval``, ``exec``,
   gọi hệ điều hành trực tiếp, tự mở mạng, và chuỗi trông giống khóa. Danh sách
   ở :data:`CAU_TRUC_CAM`, và nó là dữ liệu để đọc được, kiểm được.
3. **Cổng chạy thử** — chạy các hàm ``test_`` trong tiến trình riêng, thư mục
   riêng, có hạn giờ, và **tắt hẳn mạng** bằng ``EAA_NO_NET=1``.

Ba cổng đều phải xanh thì công cụ mới lên trạng thái ``verified``. Từ
``verified`` lên ``approved`` là việc của con người, không có lệnh nào rút
ngắn được.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "ForgeError",
    "ForgedTool",
    "ForgeCheck",
    "ForgeReport",
    "ToolRegistry",
    "ToolForge",
    "check_structure",
    "check_safety",
    "check_arguments",
    "CAU_TRUC_CAM",
    "TOOLS_DIR",
    "REGISTRY_FILE",
    "DE_XUAT",
    "DA_KIEM_THU",
    "DA_DUYET",
    "TU_CHOI",
]

TOOLS_DIR = "tools_local"
REGISTRY_FILE = "registry.yaml"

#: Bốn trạng thái. Đi một chiều, và bậc cuối chỉ người mở được.
DE_XUAT = "proposed"
DA_KIEM_THU = "verified"
DA_DUYET = "approved"
TU_CHOI = "rejected"

#: Hạn giờ chạy thử. Một công cụ tự sinh chạy quá lâu là một công cụ hỏng, và
#: một vòng lặp vô hạn trong tiến trình con vẫn treo được cả lượt chạy.
TIMEOUT_TEST_S = 30.0

#: Trần độ dài mã. Không phải để tiết kiệm chỗ: một "công cụ" dài hơn thế
#: không còn là công cụ, nó là một module — và module thì phải qua đường của
#: module, có thiết kế và có review.
MAX_DONG_MA = 200

#: Hàm gọi trần bị cấm — tên đứng một mình, ví dụ ``eval(x)``.
HAM_CAM: dict[str, str] = {
    "eval": "eval chạy chuỗi làm mã — nếu chuỗi ấy tới từ đầu vào thì công cụ trở thành một lỗ hổng",
    "exec": "exec chạy chuỗi làm mã, cùng lý do với eval",
    "compile": "compile là đường vòng tới exec",
    "__import__": "nạp module theo tên chuỗi lúc chạy làm cổng an toàn này thành vô nghĩa",
    "input": "công cụ chạy trong tiến trình không có người ngồi trước màn hình",
    "breakpoint": "dừng ở bộ gỡ rối sẽ treo tiến trình con cho tới lúc hết giờ",
}

#: Gọi qua thuộc tính bị cấm — ``os.system(...)``.
THUOC_TINH_CAM: dict[str, str] = {
    "os.system": "gọi thẳng shell — chèn lệnh qua tham số là chuyện của một dòng",
    "os.popen": "cùng lý do với os.system",
    "os.execv": "thay tiến trình hiện tại là mất hẳn quyền kiểm soát",
    "os.remove": "xóa tệp phải là quyết định của người, không phải của một công cụ tự sinh",
    "os.unlink": "cùng lý do với os.remove",
    "os.rmdir": "cùng lý do với os.remove",
    "shutil.rmtree": "xóa cả cây thư mục là thao tác không hoàn tác được",
    "pickle.loads": "giải tuần tự pickle từ dữ liệu ngoài là chạy mã tùy ý",
    "marshal.loads": "cùng lý do với pickle",
}

#: Module bị cấm nhập. Chặn ở tầng ``import`` chứ không ở tầng gọi: một module
#: đã nhập được thì mọi hàm trong nó đều gọi được, và liệt kê hết hàm là việc
#: không bao giờ liệt kê hết.
MODULE_CAM: dict[str, str] = {
    "socket": "công cụ không tự mở mạng; mọi lối ra mạng phải đi qua eaa/web.py để có kiểm nguồn và phân hạng",
    "urllib": "cùng lý do với socket",
    "http": "cùng lý do với socket",
    "requests": "cùng lý do với socket",
    "httpx": "cùng lý do với socket",
    "ftplib": "cùng lý do với socket",
    "smtplib": "cùng lý do với socket",
    "subprocess": "chạy tiến trình khác là vượt qua mọi cổng của hệ này",
    "ctypes": "gọi thư viện gốc vượt qua mọi kiểm tra của Python",
    "pty": "mở shell tương tác",
    "pickle": "giải tuần tự pickle từ dữ liệu ngoài là chạy mã tùy ý",
    "marshal": "cùng lý do với pickle",
    "multiprocessing": "sinh tiến trình con vượt ra ngoài hạn giờ của cổng chạy thử",
}

#: Gộp lại để in ra và để test đếm. Bộ quét dùng ba bộ ở trên, không dùng bộ này.
CAU_TRUC_CAM: dict[str, str] = {**HAM_CAM, **THUOC_TINH_CAM, **MODULE_CAM}

#: Chuỗi trông giống khóa/bí mật bị nhúng thẳng vào mã (NFR-06, TC-14).
_MAU_BI_MAT = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|passwd|bearer)\s*[=:]\s*['\"][^'\"]{12,}['\"]"
)


class ForgeError(Exception):
    """Không dựng hoặc không kiểm được công cụ."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Công cụ và sổ đăng ký
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ForgedTool:
    """Một công cụ Agent tự viết."""

    name: str
    purpose: str
    code: str
    schema: dict[str, Any] = field(default_factory=dict)
    status: str = DE_XUAT
    created_at: str = ""
    created_by: str = ""
    verified_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    note: str = ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()

    @property
    def runnable(self) -> bool:
        return self.status == DA_DUYET

    @property
    def confidence_level(self) -> str:
        """ĐÃ KIỂM chỉ khi đã chạy qua cổng chạy thử; trước đó là GIẢ ĐỊNH."""
        from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA

        if self.status == DA_DUYET:
            return DA_KIEM
        if self.status == DA_KIEM_THU:
            return SUY_RA
        return GIA_DINH

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "schema": self.schema,
            "status": self.status,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "verified_at": self.verified_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "note": self.note,
        }

    def render(self) -> str:
        dau = {DE_XUAT: "…", DA_KIEM_THU: "✓", DA_DUYET: "★", TU_CHOI: "✗"}.get(self.status, "?")
        dong = [f"  {dau} {self.name}  [{self.status}]",
                f"      {self.purpose}"]
        tham_so = list((self.schema.get("properties") or {}).keys())
        if tham_so:
            dong.append(f"      tham số: {', '.join(tham_so)}")
        if self.approved_by:
            dong.append(f"      duyệt bởi {self.approved_by} lúc {self.approved_at}")
        elif self.status == DA_KIEM_THU:
            dong.append("      đã qua 3 cổng — chờ người duyệt: eaa tool approve " + self.name)
        if self.note:
            dong.append(f"      {self.note}")
        return "\n".join(dong)


@dataclass
class ToolRegistry:
    """Sổ công cụ tự sinh. Append-only, và cột trạng thái đi một chiều."""

    root: Path

    @property
    def dir(self) -> Path:
        return self.root / TOOLS_DIR

    @property
    def path(self) -> Path:
        return self.dir / REGISTRY_FILE

    def code_path(self, name: str) -> Path:
        return self.dir / f"{name}.py"

    def history_dir(self, name: str) -> Path:
        return self.dir / "lich_su" / name

    def versions(self, name: str) -> list[Path]:
        """Các bản đã lưu của một công cụ, mới nhất trước."""
        thu_muc = self.history_dir(name)
        if not thu_muc.is_dir():
            return []
        return sorted(thu_muc.glob("*.py"), reverse=True)

    def _giu_ban_cu(self, name: str) -> Path | None:
        """Cất bản hiện tại trước khi ghi đè.

        Vì sao cần: một công cụ **đã được duyệt và đang chạy tốt** bị viết lại
        rồi bản mới hỏng là chuyện sẽ xảy ra — chính ``eaa suggest`` đề nghị
        viết lại những công cụ hay hỏng, nên đường đi ấy là đường thường dùng.
        Không giữ bản cũ thì "viết lại cho tốt hơn" là một canh bạc không có
        đường lui, và người ta sẽ thôi không dám sửa.

        Chỉ giữ bản ĐÃ DUYỆT: một bản đề xuất chưa ai duyệt thì chưa từng chạy
        thật, nên quay lui về nó không mang lại gì.
        """
        cu = self.get(name)
        if cu is None or not cu.runnable or not cu.code:
            return None
        thu_muc = self.history_dir(name)
        thu_muc.mkdir(parents=True, exist_ok=True)
        dich = thu_muc / f"{cu.approved_at.replace(':', '-') or _now().replace(':', '-')}.py"
        dich.write_text(cu.code, encoding="utf-8")
        return dich

    # ----------------------------------------------------------------- đọc ---

    def all(self) -> list[ForgedTool]:
        if not self.path.is_file():
            return []
        du_lieu = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        ket: list[ForgedTool] = []
        for m in du_lieu.get("tools") or []:
            ten = str(m.get("name", ""))
            tep = self.code_path(ten)
            ket.append(ForgedTool(
                name=ten,
                purpose=str(m.get("purpose", "")),
                code=tep.read_text(encoding="utf-8") if tep.is_file() else "",
                schema=m.get("schema") or {},
                status=str(m.get("status", DE_XUAT)),
                created_at=str(m.get("created_at", "")),
                created_by=str(m.get("created_by", "")),
                verified_at=str(m.get("verified_at", "")),
                approved_by=str(m.get("approved_by", "")),
                approved_at=str(m.get("approved_at", "")),
                note=str(m.get("note", "")),
            ))
        return ket

    def get(self, name: str) -> ForgedTool | None:
        for t in self.all():
            if t.name == name:
                return t
        return None

    def approved(self) -> list[ForgedTool]:
        return [t for t in self.all() if t.runnable]

    # ----------------------------------------------------------------- ghi ---

    def save(self, tool: ForgedTool) -> ForgedTool:
        """Ghi mã ra tệp và cập nhật sổ. Mã và sổ luôn đi cùng nhau."""
        self.dir.mkdir(parents=True, exist_ok=True)
        if tool.code:
            cu = self.get(tool.name)
            if cu is not None and cu.code and cu.code != tool.code:
                self._giu_ban_cu(tool.name)
            self.code_path(tool.name).write_text(tool.code, encoding="utf-8")

        ds = [t for t in self.all() if t.name != tool.name] + [tool]
        du_lieu = {"tools": [t.to_dict() for t in sorted(ds, key=lambda t: t.name)]}
        tam = self.path.with_suffix(".tmp")
        tam.write_text(
            "# Sổ công cụ Agent tự sinh. Cột 'status' đi một chiều:\n"
            "#   proposed → verified (3 cổng xanh) → approved (NGƯỜI duyệt)\n"
            "# 'eaa tool approve' KHÔNG nằm trong danh mục Agent tự gọi được.\n"
            + yaml.safe_dump(du_lieu, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        tam.replace(self.path)
        return tool

    def set_status(self, name: str, status: str, **kw: Any) -> ForgedTool:
        cu = self.get(name)
        if cu is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")
        # ``to_dict`` có thêm ``sha256`` (suy ra từ mã), không phải trường khởi
        # tạo — nên dựng bản mới từ các trường thật, không từ bản tuần tự.
        truong = {
            "name": cu.name, "purpose": cu.purpose, "code": cu.code,
            "schema": cu.schema, "created_at": cu.created_at,
            "created_by": cu.created_by, "verified_at": cu.verified_at,
            "approved_by": cu.approved_by, "approved_at": cu.approved_at,
            "note": cu.note,
        }
        return self.save(ForgedTool(**{**truong, **kw, "status": status}))

    def approve(self, name: str, *, by: str) -> ForgedTool:
        """Người duyệt. CHỈ đi được từ ``verified``.

        Duyệt thẳng từ ``proposed`` sẽ bỏ qua cả ba cổng — và một công cụ chưa
        từng chạy thử lần nào thì chữ "duyệt" không nói lên điều gì.
        """
        cu = self.get(name)
        if cu is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")
        if cu.status != DA_KIEM_THU:
            raise ForgeError(
                f"{name!r} đang ở trạng thái {cu.status!r}, không phải {DA_KIEM_THU!r}. "
                f"Chạy 'eaa tool verify {name}' trước — duyệt một công cụ chưa từng "
                "chạy thử thì chữ 'duyệt' không nói lên điều gì."
            )
        if not by.strip():
            raise ForgeError("Phải ghi ai duyệt — một quyết định không có tên là một quyết định không truy được")
        return self.set_status(name, DA_DUYET, approved_by=by.strip(), approved_at=_now())


# --------------------------------------------------------------------------
# Ba cổng
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ForgeCheck:
    """Kết quả một cổng."""

    gate: str
    passed: bool
    detail: str = ""

    def render(self) -> str:
        return f"  {'✓' if self.passed else '✗'} {self.gate}: {self.detail}"


@dataclass
class ForgeReport:
    """Ba cổng, và kết luận."""

    tool: str
    checks: tuple[ForgeCheck, ...] = ()

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def render(self) -> str:
        dong = [f"Kiểm công cụ {self.tool}", ""]
        dong += [c.render() for c in self.checks]
        dong += ["", "→ " + ("qua cả ba cổng — chờ người duyệt" if self.passed
                            else "CHƯA đạt, không được duyệt")]
        return "\n".join(dong)


def check_structure(code: str) -> ForgeCheck:
    """Cổng 1 — nó có phải một công cụ không, hay chỉ là một đoạn mã."""
    try:
        cay = ast.parse(code)
    except SyntaxError as exc:
        return ForgeCheck("cấu tạo", False, f"mã không phân tích được: {exc}")

    ham = {n.name for n in ast.walk(cay) if isinstance(n, ast.FunctionDef)}
    gan: set[str] = set()
    for n in cay.body:
        if isinstance(n, ast.Assign):
            gan |= {t.id for t in n.targets if isinstance(t, ast.Name)}

    thieu: list[str] = []
    if "run" not in ham:
        thieu.append("hàm run()")
    if "SCHEMA" not in gan:
        thieu.append("SCHEMA (lược đồ tham số)")
    if "MO_TA" not in gan:
        thieu.append("MO_TA (mô tả một dòng)")
    if not any(h.startswith("test_") for h in ham):
        thieu.append("ít nhất một hàm test_")
    if thieu:
        return ForgeCheck("cấu tạo", False, "thiếu " + ", ".join(thieu))

    so_dong = len(code.splitlines())
    if so_dong > MAX_DONG_MA:
        return ForgeCheck(
            "cấu tạo", False,
            f"{so_dong} dòng, quá trần {MAX_DONG_MA}. Dài hơn thế thì nó là một "
            "module, và module phải đi đường của module: có thiết kế, có review.",
        )
    return ForgeCheck("cấu tạo", True, f"đủ run/SCHEMA/MO_TA/test, {so_dong} dòng")


def _duong_dan_thuoc_tinh(nut: ast.AST) -> str:
    """``os.path.join`` → ``"os.path.join"``; không đọc được thì trả rỗng."""
    phan: list[str] = []
    hien_tai = nut
    while isinstance(hien_tai, ast.Attribute):
        phan.append(hien_tai.attr)
        hien_tai = hien_tai.value
    if not isinstance(hien_tai, ast.Name):
        return ""
    phan.append(hien_tai.id)
    return ".".join(reversed(phan))


def check_safety(code: str) -> ForgeCheck:
    """Cổng 2 — quét cấu trúc cấm và bí mật nhúng thẳng.

    Quét theo CÂY CÚ PHÁP, không theo chuỗi con. Quét chuỗi con thì ``compile``
    trong danh sách cấm sẽ chặn cả ``re.compile`` — cấu trúc hợp lệ và phổ biến
    nhất trong loại công cụ này — và ``socket`` sẽ chặn cả một dòng chú thích
    nhắc tới chữ ấy. Một cổng an toàn hay báo nhầm thì sớm muộn cũng bị người
    ta tắt đi, và lúc ấy nó không bảo vệ được gì nữa.
    """
    if _MAU_BI_MAT.search(code):
        return ForgeCheck(
            "an toàn", False,
            "có chuỗi trông giống khóa/mật khẩu nhúng thẳng trong mã. Khóa chỉ "
            "được đọc từ biến môi trường (NFR-06).",
        )

    try:
        cay = ast.parse(code)
    except SyntaxError as exc:
        return ForgeCheck("an toàn", False, f"mã không phân tích được: {exc}")

    vi_pham: list[tuple[str, str]] = []
    for nut in ast.walk(cay):
        if isinstance(nut, ast.Call):
            if isinstance(nut.func, ast.Name) and nut.func.id in HAM_CAM:
                vi_pham.append((nut.func.id, HAM_CAM[nut.func.id]))
            elif isinstance(nut.func, ast.Attribute):
                duong = _duong_dan_thuoc_tinh(nut.func)
                if duong in THUOC_TINH_CAM:
                    vi_pham.append((duong, THUOC_TINH_CAM[duong]))
        elif isinstance(nut, ast.Import):
            for a in nut.names:
                goc = a.name.split(".")[0]
                if goc in MODULE_CAM:
                    vi_pham.append((goc, MODULE_CAM[goc]))
        elif isinstance(nut, ast.ImportFrom):
            goc = (nut.module or "").split(".")[0]
            if goc in MODULE_CAM:
                vi_pham.append((goc, MODULE_CAM[goc]))

    if vi_pham:
        # Bỏ trùng nhưng giữ thứ tự gặp — người đọc muốn thấy cái đầu tiên.
        da_co: set[str] = set()
        rieng = [(c, ly) for c, ly in vi_pham if not (c in da_co or da_co.add(c))]
        chi_tiet = "; ".join(f"{c} — {ly}" for c, ly in rieng[:3])
        them = f" (và {len(rieng) - 3} cái nữa)" if len(rieng) > 3 else ""
        return ForgeCheck("an toàn", False, f"dùng cấu trúc bị cấm: {chi_tiet}{them}")
    return ForgeCheck("an toàn", True, f"không chạm {len(CAU_TRUC_CAM)} cấu trúc bị cấm")


def run_tests(
    code: str,
    *,
    workdir: Path,
    timeout_s: float = TIMEOUT_TEST_S,
    runner: Any = None,
) -> ForgeCheck:
    """Cổng 3 — chạy các hàm ``test_`` trong tiến trình riêng, KHÔNG có mạng.

    Chạy ở thư mục tạm riêng chứ không trong kho: một công cụ hỏng ghi đè lên
    tệp của dự án là cách hỏng tệ nhất trong ba cổng này. Và ``EAA_NO_NET=1``
    được đặt trong môi trường tiến trình con để cổng an toàn có một lớp thứ hai
    ở tầng chạy, không chỉ ở tầng đọc mã.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    tep = workdir / "cong_cu_thu.py"
    tep.write_text(code, encoding="utf-8")

    kich_ban = (
        "import sys, cong_cu_thu as m\n"
        "ten = [t for t in dir(m) if t.startswith('test_')]\n"
        "if not ten:\n"
        "    print('KHONG CO TEST'); sys.exit(2)\n"
        "for t in ten:\n"
        "    getattr(m, t)()\n"
        "print('DAT', len(ten))\n"
    )
    (workdir / "chay_thu.py").write_text(kich_ban, encoding="utf-8")

    moi_truong = {
        **os.environ,
        # Lớp thứ hai của cổng an toàn, ở tầng CHẠY: kể cả khi bộ quét đọc mã
        # bỏ sót một lối ra mạng, lối ấy vẫn bị chặn lúc chạy.
        "EAA_NO_NET": "1",
        "PYTHONPATH": str(workdir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    moi_truong.pop("EAA_LLM_KEY", None)  # công cụ tự sinh không cần khóa (NFR-06)

    chay = runner or subprocess.run
    try:
        kq = chay(
            [sys.executable, "chay_thu.py"],
            cwd=str(workdir), env=moi_truong, capture_output=True,
            text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ForgeCheck(
            "chạy thử", False,
            f"quá {timeout_s:g}s — công cụ treo hoặc lặp vô hạn",
        )
    except OSError as exc:
        return ForgeCheck("chạy thử", False, f"không chạy được tiến trình con: {exc}")

    if kq.returncode != 0:
        loi = (kq.stderr or kq.stdout or "").strip().splitlines()
        return ForgeCheck("chạy thử", False, (loi[-1] if loi else f"mã thoát {kq.returncode}")[:300])
    return ForgeCheck("chạy thử", True, (kq.stdout or "").strip()[:120] or "test chạy xong")


#: Kiểu trong JSON Schema → kiểu Python tương ứng.
_KIEU = {
    "string": str, "integer": int, "number": (int, float),
    "boolean": bool, "array": list, "object": dict,
}


def check_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    """Kiểm tham số theo lược đồ TRƯỚC khi gọi. Trả danh sách lỗi; rỗng là đạt.

    Vì sao cần: đo được ở lần chạy thật đầu tiên — một công cụ khai
    ``input_files`` là chuỗi ngăn phẩy, bên gọi truyền vào một danh sách, và
    lỗi hiện ra dưới dạng ``AttributeError: 'list' object has no attribute
    'split'``. Người đọc dòng ấy không biết mình sai ở đâu, và **bên gọi
    thường là chính Agent**, nên nó cũng không tự sửa được.

    Cố ý không dùng thư viện kiểm lược đồ ngoài (NFR-04). Bộ kiểm này chỉ cần
    phủ đúng phần lược đồ mà một công cụ nhỏ thật sự dùng: kiểu, bắt buộc, và
    tên lạ.
    """
    if not isinstance(schema, dict) or not schema:
        return []
    thuoc_tinh = schema.get("properties") or {}
    if not isinstance(thuoc_tinh, dict):
        return []

    loi: list[str] = []
    for ten in schema.get("required") or []:
        if ten not in arguments:
            mo_ta = (thuoc_tinh.get(ten) or {}).get("description", "")
            loi.append(f"thiếu {ten!r}" + (f" — {mo_ta}" if mo_ta else ""))

    if not thuoc_tinh:
        # Lược đồ không khai thuộc tính nào thì không có cơ sở để nói tên nào
        # lạ. Báo lỗi ở đây là đoán, và đoán sai sẽ chặn một lời gọi hợp lệ —
        # tệ hơn hẳn việc bỏ sót một tên gõ nhầm.
        return loi

    for ten, gia_tri in arguments.items():
        khai = thuoc_tinh.get(ten)
        if khai is None:
            loi.append(
                f"{ten!r} không có trong lược đồ; công cụ nhận: "
                + ", ".join(sorted(thuoc_tinh))
            )
            continue
        kieu = khai.get("type")
        mong_doi = _KIEU.get(kieu) if isinstance(kieu, str) else None
        if mong_doi is None:
            continue
        # ``bool`` là lớp con của ``int`` trong Python — không để một cờ trôi
        # vào chỗ đang đợi một con số.
        if kieu in ("integer", "number") and isinstance(gia_tri, bool):
            loi.append(f"{ten!r} phải là {kieu}, đang nhận boolean")
        elif not isinstance(gia_tri, mong_doi):
            mo_ta = khai.get("description", "")
            loi.append(
                f"{ten!r} phải là {kieu}, đang nhận {type(gia_tri).__name__}"
                + (f" — {mo_ta}" if mo_ta else "")
            )
    return loi


def verify(code: str, *, workdir: Path, name: str = "", **kw: Any) -> ForgeReport:
    """Chạy cả ba cổng. Dừng ngay khi một cổng trượt.

    Dừng sớm chứ không chạy hết: cổng 3 CHẠY mã, và chạy một đoạn mã vừa trượt
    cổng an toàn là đúng thứ cổng an toàn sinh ra để ngăn.
    """
    cau_tao = check_structure(code)
    if not cau_tao.passed:
        return ForgeReport(name, (cau_tao,))
    an_toan = check_safety(code)
    if not an_toan.passed:
        return ForgeReport(name, (cau_tao, an_toan))
    return ForgeReport(name, (cau_tao, an_toan, run_tests(code, workdir=workdir, **kw)))


# --------------------------------------------------------------------------
# Xưởng
# --------------------------------------------------------------------------

_LUOC_DO_MA = '''{
  "name": "<tên_hàm_hợp_lệ_bằng_snake_case>",
  "purpose": "<một câu: công cụ này làm gì>",
  "schema": {"type": "object",
             "properties": {"<tên tham số>": {"type": "string", "description": "<mô tả>"}},
             "required": []},
  "code": "<toàn bộ mã Python, xem yêu cầu bên dưới>"
}'''

def _yeu_cau_ma() -> str:
    """Dựng phần yêu cầu của prompt TỪ CHÍNH bộ luật mà cổng an toàn dùng.

    Chép tay danh sách cấm vào prompt là cách nó lệch khỏi bộ luật thật ngay
    lần đầu ai đó thêm một mục. Và nó lệch theo hướng tệ nhất: mô hình bị chặn
    vì một luật chưa ai nói cho nó biết, rồi sửa mò qua vài lượt gọi. Đo được
    ở lần chạy thật đầu tiên — mô hình dùng ``os.remove`` để dọn tệp tạm trong
    test, hoàn toàn hợp lý, và trượt cổng vì một luật không có trong đề bài.
    """
    cam = ", ".join(sorted(HAM_CAM))
    thuoc_tinh = ", ".join(sorted(THUOC_TINH_CAM))
    module = ", ".join(sorted(MODULE_CAM))
    return f"""Mã BẮT BUỘC có đủ bốn thứ:
  1. MO_TA = "<một dòng mô tả>"
  2. SCHEMA = {{...}}  — đúng bằng trường schema ở trên
  3. def run(**kwargs) -> str  — trả VĂN BẢN, không in ra màn hình
  4. ít nhất một def test_...()  — dùng assert, không dùng pytest

CẤM — mã sẽ bị từ chối tự động nếu chạm phải:
  · hàm: {cam}
  · lời gọi: {thuoc_tinh}
  · nhập module: {module}

Hệ quả cần lưu ý khi viết test: KHÔNG được xóa tệp. Test tự dọn dẹp bằng cách
ghi vào thư mục tạm rồi để nguyên, hoặc dùng dữ liệu trong bộ nhớ
(io.StringIO) thay vì tệp thật — đó là cách gọn hơn và cũng không cần dọn.

Muốn ra mạng thì KHÔNG tự mở — nói rõ trong purpose là công cụ này cần mạng;
mọi lối ra mạng của hệ đi qua eaa/web.py.
Không nhúng khóa hay mật khẩu vào mã. Tối đa {MAX_DONG_MA} dòng.
Chỉ dùng thư viện chuẩn của Python."""


@dataclass
class ToolForge:
    """Đặt hàng mô hình viết một công cụ, rồi cho nó qua ba cổng."""

    registry: ToolRegistry
    llm: Any = None
    workdir: Path | None = None

    def design(self, need: str, *, context: str = "") -> ForgedTool:
        """Nhờ mô hình viết một công cụ cho nhu cầu này. Trả về bản ĐỀ XUẤT."""
        if self.llm is None:
            raise ForgeError("Chưa nối mô hình nền — xưởng công cụ cần nó để viết mã")
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=(
                "Bạn viết một công cụ dòng lệnh nhỏ bằng Python cho một agent. "
                "Viết mã CHẠY ĐƯỢC NGAY, không viết khung rỗng, không để TODO. "
                "Kèm test thật kiểm được hành vi, gồm cả một trường hợp biên. "
                "Nếu nhu cầu quá lớn cho một công cụ nhỏ, hãy thu hẹp nó lại và "
                "nói rõ phần bạn đã bỏ trong trường purpose."
            ),
            layers=[
                PromptLayer("task",
                            f"Nhu cầu: {need}\n"
                            + (f"\nBối cảnh:\n{context}\n" if context else "")
                            + f"\n{_yeu_cau_ma()}\n\n"
                            f"Trả về ĐÚNG một khối JSON:\n\n```json\n{_LUOC_DO_MA}\n```",
                            budget=2500, required=True),
            ],
            module="viết công cụ",
            budget=3500,
        )

        try:
            van_ban = (self.llm.complete(prompt) if hasattr(self.llm, "complete")
                       else self.llm.generate(prompt).raw_response)
        except LLMError as exc:
            raise ForgeError(f"Mô hình không viết được công cụ: {exc}") from None

        from eaa.options import boc_json

        du_lieu = boc_json(van_ban, ForgeError)
        ten = str(du_lieu.get("name", "")).strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", ten):
            raise ForgeError(
                f"Tên công cụ {ten!r} không hợp lệ. Phải là snake_case, 3–40 ký "
                "tự — tên công cụ đi thẳng vào tên tệp và vào lệnh gọi."
            )
        ma = str(du_lieu.get("code", ""))
        if not ma.strip():
            raise ForgeError("Mô hình trả về đề xuất không có mã")

        return self.registry.save(ForgedTool(
            name=ten,
            purpose=str(du_lieu.get("purpose", need))[:300],
            code=ma,
            schema=du_lieu.get("schema") or {},
            status=DE_XUAT,
            created_at=_now(),
            created_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        ))

    def verify(self, name: str, **kw: Any) -> ForgeReport:
        """Cho một công cụ đã đề xuất đi qua ba cổng, rồi cập nhật trạng thái."""
        cong_cu = self.registry.get(name)
        if cong_cu is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")
        if cong_cu.status == DA_DUYET:
            raise ForgeError(
                f"{name!r} đã được duyệt. Muốn kiểm lại thì sửa mã — sửa mã đưa "
                "nó về lại trạng thái đề xuất, và phải duyệt lại."
            )

        import tempfile

        goc = self.workdir
        tam = None
        if goc is None:
            tam = tempfile.TemporaryDirectory(prefix="eaa-toolforge-")
            goc = Path(tam.name)
        try:
            bao_cao = verify(cong_cu.code, workdir=goc / name, name=name, **kw)
        finally:
            if tam is not None:
                tam.cleanup()

        self.registry.set_status(
            name,
            DA_KIEM_THU if bao_cao.passed else DE_XUAT,
            verified_at=_now() if bao_cao.passed else "",
            note="" if bao_cao.passed else next(
                (c.detail for c in bao_cao.checks if not c.passed), ""),
        )
        return bao_cao

    def run(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Chạy một công cụ ĐÃ DUYỆT. Chưa duyệt thì không có đường chạy."""
        cong_cu = self.registry.get(name)
        if cong_cu is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")
        if not cong_cu.runnable:
            raise ForgeError(
                f"{name!r} đang ở trạng thái {cong_cu.status!r}, chưa được duyệt. "
                f"Người duyệt bằng: eaa tool approve {name}"
            )

        tham_so = dict(arguments or {})
        loi = check_arguments(cong_cu.schema, tham_so)
        if loi:
            raise ForgeError(
                f"Tham số cho {name!r} không khớp lược đồ:\n  · " + "\n  · ".join(loi)
            )

        import importlib.util
        import time

        spec = importlib.util.spec_from_file_location(
            f"eaa_tool_{name}", self.registry.code_path(name)
        )
        if spec is None or spec.loader is None:
            raise ForgeError(f"Không nạp được mã của {name!r}")
        mod = importlib.util.module_from_spec(spec)

        # Ghi lại MỌI lần gọi, đạt hay hỏng. Ba cổng chứng minh công cụ chạy
        # được lúc duyệt; chúng không nói gì về lần thứ hai mươi, trên dữ liệu
        # thật. Chỉ có số đo sau khi dùng mới nói được (SL-83).
        bat_dau = time.monotonic()
        try:
            spec.loader.exec_module(mod)
            ket = str(mod.run(**(arguments or {})))
        except Exception as exc:  # noqa: BLE001 - công cụ hỏng không được làm sập Agent
            self._ghi_lan_dung(
                name, ok=False,
                ms=int((time.monotonic() - bat_dau) * 1000),
                loi=f"{type(exc).__name__}: {exc}",
            )
            raise ForgeError(f"Công cụ {name!r} chạy lỗi: {type(exc).__name__}: {exc}") from None

        self._ghi_lan_dung(name, ok=True, ms=int((time.monotonic() - bat_dau) * 1000))
        return ket

    def rollback(self, name: str) -> ForgedTool:
        """Quay về bản đã duyệt gần nhất trước bản hiện tại.

        Bản quay về KHÔNG tự lên lại ``approved``: nó về ``proposed`` và phải
        đi lại ba cổng. Mã ấy từng chạy được, nhưng "từng" là ở một môi trường
        khác và có thể ở một phiên bản Python khác — và nếu ba cổng vẫn xanh
        thì chạy lại chúng tốn vài giây, còn nếu không thì đó chính là thứ ta
        cần biết trước khi dựa vào nó.
        """
        # Kiểm sự TỒN TẠI trước. Ngược lại thì một cái tên gõ nhầm nhận được
        # câu "không có bản cũ nào" — đúng về mặt sự thật và sai về mặt giúp
        # đỡ: người dùng đi tìm bản cũ, trong khi thứ họ gõ sai là cái tên.
        hien_tai = self.registry.get(name)
        if hien_tai is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")

        cu = self.registry.versions(name)
        if not cu:
            raise ForgeError(
                f"Không có bản cũ nào của {name!r} để quay về. Chỉ những bản ĐÃ "
                "ĐƯỢC DUYỆT mới được cất — một bản chưa ai duyệt thì chưa từng "
                "chạy thật, nên quay lui về nó không mang lại gì."
            )

        ma = cu[0].read_text(encoding="utf-8")
        moi = self.registry.set_status(
            name, DE_XUAT, code=ma,
            note=f"quay lui về bản {cu[0].stem}; phải chạy lại ba cổng trước khi duyệt",
        )
        return moi

    def document(self, name: str, *, usage: Any = None) -> str:
        """Sinh tài liệu ngắn cho một công cụ tự sinh.

        Dựng từ thứ ĐÃ CÓ TRONG MÃ — ``MO_TA``, ``SCHEMA``, các hàm ``test_``
        — cộng số đo dùng thật. Không hỏi mô hình: một bản mô tả do mô hình
        viết lại có thể lệch khỏi mã, và một tài liệu lệch khỏi mã là thứ tệ
        hơn không có tài liệu.
        """
        t = self.registry.get(name)
        if t is None:
            raise ForgeError(f"Sổ không có công cụ {name!r}")

        thuoc_tinh = (t.schema.get("properties") or {})
        bat_buoc = set(t.schema.get("required") or [])
        vi_du = {k: f"<{k}>" for k in thuoc_tinh}

        dong = [
            f"# {t.name}",
            "",
            t.purpose or "(chưa khai mục đích)",
            "",
            f"- Trạng thái : {t.status}"
            + (f" — duyệt bởi {t.approved_by} lúc {t.approved_at}" if t.approved_by else ""),
            f"- Băm mã     : {t.sha256[:16]}",
            "",
            "## Tham số",
            "",
        ]
        if thuoc_tinh:
            dong.append("| tên | kiểu | bắt buộc | mô tả |")
            dong.append("|---|---|---|---|")
            for k, v in thuoc_tinh.items():
                dong.append(f"| `{k}` | {v.get('type', '?')} | "
                            f"{'có' if k in bat_buoc else '—'} | {v.get('description', '')} |")
        else:
            dong.append("Không nhận tham số nào.")

        dong += ["", "## Gọi nó", "",
                 "```bash",
                 f"eaa tool run {t.name}" + (f" --args '{json.dumps(vi_du, ensure_ascii=False)}'"
                                             if vi_du else ""),
                 "```", ""]

        ham_test = re.findall(r"^def (test_\w+)", t.code, re.M)
        if ham_test:
            dong += ["## Đã kiểm những gì", "",
                     *[f"- `{h}`" for h in ham_test], ""]

        if usage is not None:
            s = usage.stats_for(name)
            if s.runs:
                dong += ["## Đo được sau khi dùng thật", "",
                         f"- {s.runs} lần dùng · {s.ok} đạt / {s.failed} hỏng",
                         f"- trung bình {s.avg_ms} ms"]
                if s.concerning:
                    dong.append(f"- ⚠ HAY HỎNG — lỗi gần nhất: {s.last_error[:120]}")
                dong.append("")

        dong += [
            "## Giới hạn đã biết",
            "",
            "- Công cụ này do Agent sinh ra và một người duyệt. Nó đã qua ba "
            "cổng — cấu tạo, an toàn, chạy thử — nhưng ba cổng ấy kiểm nó ở "
            "**lúc duyệt**, không kiểm nó trên mọi đầu vào.",
            "- Nó không tự mở mạng và không chạy tiến trình khác; đó là ràng "
            "buộc của cổng an toàn, không phải một thiếu sót.",
        ]
        return "\n".join(dong)

    def _ghi_lan_dung(self, name: str, *, ok: bool, ms: int, loi: str = "") -> None:
        """Ghi một lần dùng. Không bao giờ để việc ghi làm hỏng lượt chạy."""
        try:
            from eaa.toolusage import UsageLog

            UsageLog(self.registry.root).record(name, ok=ok, duration_ms=ms, error=loi)
        except Exception:  # noqa: BLE001 - nhật ký hỏng không được che lỗi thật
            pass
