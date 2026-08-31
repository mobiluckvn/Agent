"""Công cụ tự sinh chạy ra sao khi dùng THẬT — đo, không đoán.

EAA-AIS-05 §11 (đo và cải tiến), NFR-08. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-83.

Khoảng trống module này lấp
----------------------------

Ba cổng của ``eaa/toolforge.py`` chứng minh một công cụ **chạy được lúc duyệt**.
Chúng không nói gì về việc nó chạy ra sao ở lần thứ hai mươi, trên dữ liệu
thật, khi tệp đầu vào có một dòng lạ.

Một công cụ qua cổng rồi hỏng bốn lần trong sáu lần dùng vẫn mang nhãn
``approved`` và vẫn nằm trong prompt của Agent — nó sẽ được gọi lại, hỏng lại,
và mỗi lần hỏng là một lượt gọi mô hình bị đốt để xử lý hậu quả. Cái thiếu
không phải một cổng nữa; cái thiếu là **số đo sau khi dùng**.

Cùng kỷ luật với sổ tay lỗi
----------------------------

Append-only, hai bộ đếm, và tỉ lệ làm mềm Laplace — giống hệt
``eaa/playbook.py``, và vì cùng một lý do: một bản ghi chỉ đếm thành công sẽ
tự tin dần lên theo hướng sai.

Điều module này KHÔNG làm
--------------------------

Nó **không tự gỡ một công cụ hay hỏng**. Gỡ là một quyết định, và quyết định
thuộc về người: có khi công cụ đúng còn dữ liệu vào sai, có khi nó chỉ hỏng ở
một loại đầu vào hiếm. Module này bày số ra và **cảnh báo**; ``eaa suggest``
là chỗ biến số ấy thành một đề nghị cụ thể.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from eaa.memory import MEMORY_DIR

__all__ = [
    "ToolUse",
    "ToolStats",
    "UsageLog",
    "USAGE_FILE",
    "TI_LE_DANG_LO",
    "SO_LAN_DU_DE_KET_LUAN",
    "CHAM_MS",
]

USAGE_FILE = "tool_usage.jsonl"

#: Dưới ngưỡng này thì công cụ đáng xem lại. Không phải một hằng số tùy tiện:
#: một công cụ hỏng hơn một phần tư số lần dùng thì thời gian nó tiết kiệm
#: được đã bị thời gian xử lý hậu quả ăn hết.
TI_LE_DANG_LO = 0.75

#: Ít hơn thế thì chưa đủ để kết luận — hai lần hỏng liên tiếp có thể chỉ là
#: hai lần đầu vào xấu.
SO_LAN_DU_DE_KET_LUAN = 4

#: Công cụ nhỏ chạy lâu hơn thế là dấu hiệu nó đang làm việc của một module.
CHAM_MS = 5_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ToolUse:
    """Một lần gọi một công cụ tự sinh."""

    tool: str
    ok: bool
    duration_ms: int = 0
    error: str = ""
    at: str = ""
    #: Dự án lúc gọi. Công cụ dùng chung mọi dự án, nhưng dữ liệu vào thì
    #: không — một công cụ đọc tệp nhật ký có thể chạy tốt ở dự án này và hỏng
    #: ở dự án kia vì định dạng tệp khác. Không ghi chỗ nó hỏng thì số đo chỉ
    #: nói "hay hỏng" mà không nói "hỏng ở đâu", và người sửa phải đoán.
    project: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "ok": self.ok, "duration_ms": self.duration_ms,
                "error": self.error, "at": self.at, "project": self.project}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolUse":
        return cls(
            tool=str(d.get("tool", "")),
            ok=bool(d.get("ok", False)),
            duration_ms=int(d.get("duration_ms", 0)),
            error=str(d.get("error", "")),
            at=str(d.get("at", "")),
            project=str(d.get("project", "")),
        )


@dataclass(frozen=True)
class ToolStats:
    """Số đo tích luỹ của một công cụ."""

    tool: str
    ok: int = 0
    failed: int = 0
    total_ms: int = 0
    last_error: str = ""
    last_at: str = ""
    #: Những dự án công cụ này đã chạy ở đó.
    projects: tuple[str, ...] = ()

    @property
    def runs(self) -> int:
        return self.ok + self.failed

    @property
    def success_rate(self) -> float:
        """Làm mềm Laplace — một lần dùng không đủ để nói 100% hay 0%."""
        return (self.ok + 1.0) / (self.runs + 2.0)

    @property
    def avg_ms(self) -> int:
        return self.total_ms // self.runs if self.runs else 0

    @property
    def enough_data(self) -> bool:
        return self.runs >= SO_LAN_DU_DE_KET_LUAN

    @property
    def concerning(self) -> bool:
        """Đáng xem lại chưa — CHỈ khi đã đủ số lần để kết luận.

        Không cảnh báo sớm: hai lần hỏng đầu tiên có thể chỉ là hai lần đầu
        vào xấu, và một cảnh báo sai làm người ta thôi đọc cảnh báo.
        """
        return self.enough_data and self.success_rate < TI_LE_DANG_LO

    @property
    def slow(self) -> bool:
        return self.enough_data and self.avg_ms > CHAM_MS

    @property
    def confidence_level(self) -> str:
        """Đủ số lần thì ĐÃ KIỂM — đây là số đo thật, không phải suy đoán."""
        from eaa.confidence import DA_KIEM, SUY_RA

        return DA_KIEM if self.enough_data else SUY_RA

    def render(self) -> str:
        if not self.runs:
            return f"      chưa dùng lần nào"
        dong = f"      đã dùng {self.runs} lần · {self.ok} đạt / {self.failed} hỏng"
        if len(self.projects) > 1:
            dong += f" · ở {len(self.projects)} dự án: {', '.join(self.projects)}"
        if self.avg_ms:
            dong += f" · trung bình {self.avg_ms} ms"
        canh_bao = []
        if self.concerning:
            canh_bao.append("HAY HỎNG")
        if self.slow:
            canh_bao.append("CHẬM")
        if canh_bao:
            dong += f"   ⚠ {' · '.join(canh_bao)}"
            if self.last_error:
                dong += f"\n      lỗi gần nhất: {self.last_error[:120]}"
        return dong


@dataclass
class UsageLog:
    """Nhật ký dùng công cụ — append-only, ở gốc kho như sổ công cụ."""

    root: Path
    filename: str = USAGE_FILE

    @property
    def path(self) -> Path:
        return self.root / MEMORY_DIR / self.filename

    def record(self, tool: str, *, ok: bool, duration_ms: int = 0,
               error: str = "", project: str = "") -> ToolUse:
        lan = ToolUse(tool=tool, ok=ok, duration_ms=duration_ms,
                      error=" ".join((error or "").split())[:300], at=_now(),
                      project=project)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(lan.to_dict(), ensure_ascii=False) + "\n")
        return lan

    def all(self) -> list[ToolUse]:
        if not self.path.is_file():
            return []
        ds: list[ToolUse] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                ds.append(ToolUse.from_dict(json.loads(dong)))
            except json.JSONDecodeError:
                continue
        return ds

    def stats(self, tool: str = "", *, project: str = "") -> dict[str, ToolStats]:
        """Số đo tích luỹ. Nêu ``project`` thì chỉ tính lần gọi ở dự án ấy.

        Mặc định gộp mọi dự án: một công cụ hỏng ở khắp nơi là chuyện khác hẳn
        một công cụ chỉ hỏng ở một dự án, và cả hai đều đáng biết.
        """
        gop: dict[str, ToolStats] = {}
        for u in self.all():
            if tool and u.tool != tool:
                continue
            if project and u.project != project:
                continue
            cu = gop.get(u.tool, ToolStats(tool=u.tool))
            gop[u.tool] = ToolStats(
                tool=u.tool,
                ok=cu.ok + (1 if u.ok else 0),
                failed=cu.failed + (0 if u.ok else 1),
                total_ms=cu.total_ms + u.duration_ms,
                last_error=(u.error or cu.last_error) if not u.ok else cu.last_error,
                last_at=max(cu.last_at, u.at),
                projects=tuple(sorted(set(cu.projects) | ({u.project} if u.project else set()))),
            )
        return gop

    def stats_for(self, tool: str, *, project: str = "") -> ToolStats:
        return self.stats(tool, project=project).get(tool, ToolStats(tool=tool))

    def concerning(self) -> list[ToolStats]:
        """Công cụ đáng xem lại. Không tự gỡ cái nào — gỡ là một quyết định."""
        return sorted(
            (s for s in self.stats().values() if s.concerning or s.slow),
            key=lambda s: s.success_rate,
        )
