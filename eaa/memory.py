"""Bộ nhớ liên dự án — thứ học được ở dự án này mang sang được dự án sau.

EAA-AIS-05 §7 (vòng đời tri thức), §11; FR-KB-04. Xem
`docs/SAI_LECH_THIET_KE.md` mục SL-74.

Khoảng trống module này lấp
----------------------------

Mọi kho tri thức hiện có đều nằm TRONG một dự án: ``kb/``, ``sources.yaml``,
``ledger``, ``kpi_log.csv``. Đó là đúng cho tri thức phần cứng — bảng thanh ghi
của một con chip không nói gì về con chip khác. Nhưng có một lớp thứ hai không
thuộc về dự án nào cả:

* máy này chạy hệ gì, có trình cài gói nào, mạng có thông không;
* công cụ nào đã cài, phiên bản bao nhiêu, ai duyệt lúc nào;
* lỗi nào đã gặp và cách nào sửa được nó.

Lớp ấy trước đây bị dựng lại từ đầu ở mỗi dự án — nghĩa là bị dựng lại từ đầu
ở mỗi lần dùng. Một Agent quên sạch sau mỗi dự án thì mọi thứ nó "học" chỉ là
cách nói.

Cùng kỷ luật với kho tri thức dự án
------------------------------------

**Append-only + supersede, không ghi đè vật lý.** Sửa một sự kiện là ghi thêm
một bản mới trỏ ngược về bản cũ; bản cũ vẫn nằm đó. Lý do giống hệt lý do ở
``eaa/kb.py``: khi một kết luận hóa ra sai, câu hỏi đầu tiên luôn là "lúc ấy ta
tin cái gì" — và một tệp bị ghi đè không trả lời được câu đó.

**Phạm vi phải khai rõ.** ``toàn cục`` cho thứ đúng ở mọi nơi (máy này có
brew), ``mcu:<họ>`` cho thứ đúng theo họ chip, ``dự án:<tên>`` cho thứ chỉ đúng
ở một dự án. Không khai phạm vi thì một bài học rút ra từ một bo sẽ được đem
áp lên bo khác — đúng loại sai mà một "bộ nhớ dùng chung" dễ gây ra nhất.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

__all__ = [
    "MemoryError_",
    "MemoryFact",
    "MemoryStore",
    "TOAN_CUC",
    "scope_du_an",
    "scope_mcu",
    "KIND_MOI_TRUONG",
    "KIND_CONG_CU",
    "KIND_BAI_HOC",
    "KIND_NGUON",
    "MEMORY_DIR",
    "FACTS_FILE",
]

MEMORY_DIR = "memory"
FACTS_FILE = "facts.jsonl"

#: Phạm vi — xem phần cuối tài liệu module.
TOAN_CUC = "toàn cục"


def scope_du_an(ten: str) -> str:
    return f"dự án:{ten}"


def scope_mcu(ho: str) -> str:
    return f"mcu:{ho.lower()}"


KIND_MOI_TRUONG = "môi trường"
KIND_CONG_CU = "công cụ"
KIND_BAI_HOC = "bài học"
KIND_NGUON = "nguồn"

_KINDS = (KIND_MOI_TRUONG, KIND_CONG_CU, KIND_BAI_HOC, KIND_NGUON)


class MemoryError_(Exception):
    """Không ghi/đọc được bộ nhớ."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class MemoryFact:
    """Một sự kiện nhớ được, kèm phạm vi và bằng chứng."""

    id: str
    kind: str
    subject: str
    statement: str
    scope: str = TOAN_CUC
    evidence: str = ""
    created_at: str = ""
    supersedes: str = ""
    #: Điền khi có bản sau thay thế bản này. KHÔNG sửa tệp — trường này được
    #: dựng lại lúc đọc, từ trường ``supersedes`` của các bản sau.
    superseded_by: str = ""

    @property
    def active(self) -> bool:
        return not self.superseded_by

    @property
    def confidence_level(self) -> str:
        """Có bằng chứng thì SUY RA, không có thì GIẢ ĐỊNH.

        Không bao giờ là ĐÃ KIỂM: một sự kiện nhớ từ lần trước có thể đã cũ.
        Máy đã đổi, công cụ đã gỡ, tài liệu đã sửa — bộ nhớ không tự biết điều
        đó, nên nó không được phép nói giọng chắc chắn nhất.
        """
        from eaa.confidence import GIA_DINH, SUY_RA

        return SUY_RA if self.evidence else GIA_DINH

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "subject": self.subject,
            "statement": self.statement,
            "scope": self.scope,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "supersedes": self.supersedes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MemoryFact":
        return cls(
            id=str(d.get("id", "")),
            kind=str(d.get("kind", "")),
            subject=str(d.get("subject", "")),
            statement=str(d.get("statement", "")),
            scope=str(d.get("scope", TOAN_CUC)),
            evidence=str(d.get("evidence", "")),
            created_at=str(d.get("created_at", "")),
            supersedes=str(d.get("supersedes", "")),
        )

    def render(self) -> str:
        dau = " " if self.active else "×"
        dong = [f" {dau} [{self.kind}] {self.subject}  ({self.scope})",
                f"      {self.statement}"]
        if self.evidence:
            dong.append(f"      bằng chứng: {self.evidence}")
        if self.superseded_by:
            dong.append(f"      ↳ đã bị thay bởi {self.superseded_by}")
        return "\n".join(dong)


@dataclass
class MemoryStore:
    """Kho append-only ở GỐC kho mã, dùng chung cho mọi dự án."""

    root: Path
    filename: str = FACTS_FILE

    @property
    def path(self) -> Path:
        return self.root / MEMORY_DIR / self.filename

    # ----------------------------------------------------------------- ghi ---

    def add(
        self,
        kind: str,
        subject: str,
        statement: str,
        *,
        scope: str = TOAN_CUC,
        evidence: str = "",
        supersedes: str = "",
    ) -> MemoryFact:
        if kind not in _KINDS:
            raise MemoryError_(
                f"Loại {kind!r} không có trong bộ: {', '.join(_KINDS)}. "
                "Loại tự do làm kho không tra được — mỗi lần tra phải đoán xem "
                "lần trước người ta gọi nó là gì."
            )
        if not subject.strip() or not statement.strip():
            raise MemoryError_("Sự kiện phải có cả chủ thể lẫn nội dung")

        su_kien = MemoryFact(
            id=self._ma(kind, subject, statement),
            kind=kind,
            subject=subject.strip(),
            statement=statement.strip(),
            scope=scope,
            evidence=evidence.strip(),
            created_at=_now(),
            supersedes=supersedes,
        )
        self._noi_them(su_kien)
        return su_kien

    def supersede(self, cu: str, statement: str, **kw: Any) -> MemoryFact:
        """Thay một sự kiện bằng bản mới. Bản cũ KHÔNG bị xóa."""
        goc = self.get(cu)
        if goc is None:
            raise MemoryError_(f"Không có sự kiện {cu!r} để thay")
        kw.setdefault("kind", goc.kind)
        kw.setdefault("subject", goc.subject)
        kw.setdefault("scope", goc.scope)
        return self.add(statement=statement, supersedes=cu, **kw)

    def remember_environment(self, report: Any, *, machine: str = "") -> list[MemoryFact]:
        """Ghi lại bản dò môi trường thành mấy sự kiện tra được."""
        import platform

        may = machine or platform.node() or "máy này"
        ket = [
            self.add(KIND_MOI_TRUONG, f"{may} · hệ điều hành",
                     f"{report.os_name} {report.os_release} ({report.arch})",
                     evidence=f"eaa environ lúc {report.probed_at}"),
            self.add(KIND_MOI_TRUONG, f"{may} · trình cài gói",
                     ", ".join(report.package_managers) or "không có cái nào",
                     evidence=f"eaa environ lúc {report.probed_at}"),
        ]
        if report.network is not None and not report.network.skipped:
            ket.append(self.add(
                KIND_MOI_TRUONG, f"{may} · mạng ra ngoài",
                "thông" if report.network.reachable else f"không thông ({report.network.detail})",
                evidence=f"thử nối {report.network.host} lúc {report.probed_at}"))
        return ket

    def _noi_them(self, su_kien: MemoryFact) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(su_kien.to_dict(), ensure_ascii=False) + "\n")

    @staticmethod
    def _ma(kind: str, subject: str, statement: str) -> str:
        v = hashlib.sha256(f"{kind}|{subject}|{statement}|{_now()}".encode()).hexdigest()
        return f"m-{v[:10]}"

    # ----------------------------------------------------------------- đọc ---

    def all(self) -> list[MemoryFact]:
        """Đọc toàn kho và dựng lại quan hệ thay thế.

        Trường ``superseded_by`` KHÔNG nằm trong tệp — nó được suy ra lúc đọc,
        từ trường ``supersedes`` của các bản sau. Ghi nó vào tệp sẽ buộc phải
        sửa dòng cũ, và sửa dòng cũ là đúng cái append-only sinh ra để cấm.
        """
        if not self.path.is_file():
            return []
        ds: list[MemoryFact] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                ds.append(MemoryFact.from_dict(json.loads(dong)))
            except json.JSONDecodeError:
                continue

        bi_thay: dict[str, str] = {}
        for f in ds:
            if f.supersedes:
                bi_thay[f.supersedes] = f.id
        return [
            f if f.id not in bi_thay
            else MemoryFact(**{**f.to_dict(), "superseded_by": bi_thay[f.id]})
            for f in ds
        ]

    def active(self) -> list[MemoryFact]:
        return [f for f in self.all() if f.active]

    def get(self, ma: str) -> MemoryFact | None:
        for f in self.all():
            if f.id == ma:
                return f
        return None

    def find(
        self,
        *,
        kind: str = "",
        scope: str = "",
        subject: str = "",
        contains: str = "",
        include_superseded: bool = False,
    ) -> list[MemoryFact]:
        ds = self.all() if include_superseded else self.active()
        if kind:
            ds = [f for f in ds if f.kind == kind]
        if scope:
            ds = [f for f in ds if f.scope == scope]
        if subject:
            ds = [f for f in ds if subject.lower() in f.subject.lower()]
        if contains:
            k = contains.lower()
            ds = [f for f in ds if k in f.statement.lower() or k in f.subject.lower()]
        return ds

    def relevant(self, *, project: str = "", mcu: str = "") -> list[MemoryFact]:
        """Sự kiện áp dụng được cho bối cảnh này: toàn cục + đúng họ + đúng dự án.

        Không trả về sự kiện của DỰ ÁN KHÁC. Đó là chỗ một bộ nhớ dùng chung dễ
        gây hại nhất: một bài học rút từ bo A đem áp lên bo B mà không ai kịp
        hỏi nó có còn đúng không.
        """
        pham_vi = {TOAN_CUC}
        if project:
            pham_vi.add(scope_du_an(project))
        if mcu:
            pham_vi.add(scope_mcu(mcu))
        return [f for f in self.active() if f.scope in pham_vi]

    def render(self, *, project: str = "", mcu: str = "") -> str:
        from eaa.confidence import header
        from eaa.confidence import SUY_RA

        ds = self.relevant(project=project, mcu=mcu) if (project or mcu) else self.active()
        dong = ["Bộ nhớ liên dự án", "", header(SUY_RA), ""]
        if not ds:
            dong.append("  (chưa nhớ gì)")
            return "\n".join(dong)
        for k in _KINDS:
            nhom = [f for f in ds if f.kind == k]
            if not nhom:
                continue
            dong.append(f"── {k} ({len(nhom)})")
            dong += [f.render() for f in nhom]
            dong.append("")
        tong = len(self.all())
        dong.append(f"{len(ds)} sự kiện đang hiệu lực / {tong} bản ghi (kho append-only).")
        return "\n".join(dong)
