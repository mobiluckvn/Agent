"""Error Ledger — nhật ký lỗi ảo giác, và là nguồn ví dụ phủ định cho prompt.

EAA-SDD-03 §3.4 và §4, EAA-SRS-01 FR-KB-03, EAA-AIS-05 §3.1 (kỹ thuật nén K5)
và §8.1 (append-only thuần túy).

Ý tưởng: mỗi lần AI bịa một thanh ghi hay sai một hệ số chia, cái giá đã trả
rồi — ít nhất hãy thu lại tri thức. Lỗi được cô đọng thành một QUY TẮC một
dòng và nạp ngược vào prompt lần sau như ví dụ phủ định. Nhật ký dài vô hạn
nhưng phần đưa vào ngữ cảnh luôn chỉ khoảng 300 token: chọn top-3 lỗi liên
quan nhất tới module đang sinh (K5).

**Append-only thuần túy** (AIS §8.1): không sửa, không xóa dòng nào. Một lỗi
được khép lại bằng cách GHI THÊM một sự kiện ``resolution`` trỏ về nó, chứ
không phải bằng cách sửa dòng cũ. Nhờ vậy nhật ký vừa là trạng thái hiện tại
vừa là lịch sử — và lịch sử ấy chính là dữ liệu cho "danh mục lỗi ảo giác
điển hình của AI với phần cứng", một trong ba nhóm tri thức đề án sinh ra.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "LedgerError",
    "LedgerEntry",
    "ErrorLedger",
    "CATEGORIES",
    "OPEN",
    "RESOLVED",
]

OPEN = "open"
RESOLVED = "resolved"

#: Phân loại lỗi. Cố ý là danh từ chung về HÀNH VI SAI của mô hình, không phải
#: về một phần cứng cụ thể — nhờ vậy danh mục này dùng lại được cho mọi nền tảng.
CATEGORIES: tuple[str, ...] = (
    "hallucinated_register",   # bịa thanh ghi không tồn tại trên thiết bị
    "wrong_bitfield",          # đúng thanh ghi, sai bit hoặc sai giá trị
    "wrong_timing",            # sai hệ số chia, sai công thức chu kỳ
    "constraint_violation",    # vi phạm ràng buộc cứng của dự án
    "concurrency",             # tranh chấp giữa ngắt và vòng lặp chính
    "missing_citation",        # cấu hình thanh ghi mà không trích dẫn nguồn
    "gate_rejection",          # người từ chối tại gate, kèm lý do
    "tool_failure",            # mã không qua được một cổng kiểm chứng
    "other",
)

_MAX_RULE_LEN = 160


class LedgerError(Exception):
    """Nhật ký lỗi sai lược đồ hoặc bản ghi không hợp lệ."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class LedgerEntry:
    """Một mục lỗi ở trạng thái hiện hành (đã gộp các sự kiện liên quan)."""

    id: str
    ts: str
    module: str
    category: str
    description: str
    evidence: str = ""
    peripheral: str = ""
    registers: tuple[str, ...] = ()
    rule: str = ""
    status: str = OPEN
    resolved_by: str = ""
    resolved_at: str = ""
    resolution_note: str = ""

    @property
    def as_rule(self) -> str:
        """Dạng quy tắc một dòng để nạp vào prompt — kỹ thuật nén K5.

        Ưu tiên câu quy tắc do người viết: nó nói "đừng làm gì", còn mô tả lỗi
        chỉ nói "đã xảy ra chuyện gì". Mệnh lệnh ngắn được mô hình tuân thủ tốt
        hơn văn xuôi kể chuyện (cùng lý do với K1).
        """
        if self.rule:
            return self.rule.strip()

        dong = " ".join(self.description.split())
        if len(dong) > _MAX_RULE_LEN:
            dong = dong[: _MAX_RULE_LEN - 1].rstrip() + "…"
        return f"KHÔNG lặp lại: {dong}"

    def to_event(self) -> dict[str, Any]:
        return {
            "event": "error",
            "id": self.id,
            "ts": self.ts,
            "module": self.module,
            "category": self.category,
            "description": self.description,
            "evidence": self.evidence,
            "peripheral": self.peripheral,
            "registers": list(self.registers),
            "rule": self.rule,
        }


class ErrorLedger:
    """Nhật ký lỗi của một dự án — tệp ``error_ledger.jsonl``."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    # -- ghi ---------------------------------------------------------------

    def add(
        self,
        *,
        module: str,
        category: str,
        description: str,
        evidence: str = "",
        peripheral: str = "",
        registers: Sequence[str] = (),
        rule: str = "",
        entry_id: str | None = None,
        ts: str | None = None,
    ) -> LedgerEntry:
        """Ghi một lỗi mới. Chỉ THÊM dòng, không bao giờ sửa dòng cũ."""
        if category not in CATEGORIES:
            raise LedgerError(
                f"Phân loại lỗi không hợp lệ: {category!r} "
                f"(hợp lệ: {list(CATEGORIES)})"
            )
        if not description.strip():
            raise LedgerError("Mục lỗi phải có mô tả — một dòng trống không dạy được gì")

        entry = LedgerEntry(
            id=entry_id or self._next_id(),
            ts=ts or _now(),
            module=module,
            category=category,
            description=description.strip(),
            evidence=evidence,
            peripheral=peripheral,
            registers=tuple(str(r).upper() for r in registers),
            rule=rule.strip(),
        )
        self._append(entry.to_event())
        return entry

    def resolve(self, entry_id: str, *, commit: str = "", note: str = "") -> None:
        """Khép một lỗi bằng cách GHI THÊM sự kiện, không sửa dòng cũ (AIS §8.1)."""
        if entry_id not in {e.id for e in self.entries()}:
            raise LedgerError(f"Không có mục lỗi {entry_id!r} trong {self.path}")
        self._append(
            {
                "event": "resolution",
                "resolves": entry_id,
                "ts": _now(),
                "commit": commit,
                "note": note,
            }
        )

    def _next_id(self) -> str:
        return f"err-{len(self._events()) + 1:04d}"

    def _append(self, event: dict[str, Any]) -> None:
        """Ghi thêm một dòng JSON, bền qua crash.

        Mở ở chế độ ``a`` rồi ``fsync``: khác với Project State, ở đây không
        cần ghi-tạm-rồi-đổi-tên vì mỗi thao tác chỉ nối thêm — chết giữa chừng
        thì mất đúng dòng đang viết, không hỏng những dòng đã có.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # -- đọc ---------------------------------------------------------------

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        su_kien: list[dict[str, Any]] = []
        for so_dong, dong in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                su_kien.append(json.loads(dong))
            except json.JSONDecodeError as exc:
                raise LedgerError(
                    f"{self.path}:{so_dong}: dòng không phải JSON hợp lệ — {exc}. "
                    "Nhật ký là append-only: khôi phục từ Git, đừng sửa tay."
                ) from exc
        return su_kien

    def entries(self, *, include_resolved: bool = True) -> list[LedgerEntry]:
        """Trạng thái hiện hành của từng lỗi, gộp từ chuỗi sự kiện."""
        theo_id: dict[str, LedgerEntry] = {}
        khep: dict[str, dict[str, Any]] = {}

        for su_kien in self._events():
            loai = su_kien.get("event", "error")
            if loai == "error":
                theo_id[su_kien["id"]] = LedgerEntry(
                    id=su_kien["id"],
                    ts=su_kien.get("ts", ""),
                    module=su_kien.get("module", ""),
                    category=su_kien.get("category", "other"),
                    description=su_kien.get("description", ""),
                    evidence=su_kien.get("evidence", ""),
                    peripheral=su_kien.get("peripheral", ""),
                    registers=tuple(su_kien.get("registers", ())),
                    rule=su_kien.get("rule", ""),
                )
            elif loai == "resolution":
                khep[su_kien.get("resolves", "")] = su_kien

        ket_qua: list[LedgerEntry] = []
        for entry_id, entry in theo_id.items():
            if entry_id in khep:
                su_kien = khep[entry_id]
                entry = LedgerEntry(
                    **{
                        **entry.__dict__,
                        "status": RESOLVED,
                        "resolved_by": su_kien.get("commit", ""),
                        "resolved_at": su_kien.get("ts", ""),
                        "resolution_note": su_kien.get("note", ""),
                    }
                )
            if include_resolved or entry.status != RESOLVED:
                ket_qua.append(entry)
        return ket_qua

    def get(self, entry_id: str) -> LedgerEntry:
        for entry in self.entries():
            if entry.id == entry_id:
                return entry
        raise LedgerError(f"Không có mục lỗi {entry_id!r} trong {self.path}")

    def __len__(self) -> int:
        return len(self.entries())

    # -- K5: chưng cất lỗi thành quy tắc ----------------------------------

    def rules_for(
        self,
        module: str = "",
        *,
        peripheral: str = "",
        registers: Iterable[str] = (),
        top_k: int = 3,
    ) -> list[str]:
        """Top-k quy tắc liên quan nhất, dạng một dòng — kỹ thuật nén K5.

        Xếp hạng theo mức liên quan tới việc đang làm, vì ngân sách ngữ cảnh
        chỉ đủ cho vài dòng: lỗi của chính module này > lỗi cùng thanh ghi >
        lỗi cùng ngoại vi > lỗi mới nhất. Lỗi CHƯA khép được ưu tiên hơn lỗi đã
        khép — nhưng lỗi đã khép vẫn giữ lại, vì mô hình không "nhớ" rằng lần
        trước nó đã bị sửa.
        """
        muc_tieu = {str(r).upper() for r in registers}

        def diem(entry: LedgerEntry) -> tuple[int, int, int, int, str]:
            return (
                1 if entry.status == OPEN else 0,
                1 if module and entry.module == module else 0,
                len(muc_tieu & set(entry.registers)),
                1 if peripheral and entry.peripheral.lower() == peripheral.lower() else 0,
                entry.ts,
            )

        xep_hang = sorted(self.entries(), key=diem, reverse=True)
        return [e.as_rule for e in xep_hang[:top_k]]

    def categories_seen(self) -> dict[str, int]:
        """Thống kê theo phân loại — nguyên liệu cho danh mục lỗi ở Chương 3."""
        dem: dict[str, int] = {}
        for entry in self.entries():
            dem[entry.category] = dem.get(entry.category, 0) + 1
        return dict(sorted(dem.items(), key=lambda kv: (-kv[1], kv[0])))
