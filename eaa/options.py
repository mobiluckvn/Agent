"""Trình nhiều phương án để người chọn — cổng quyết định, không chỉ cổng duyệt.

EAA-SRS-01 FR-GATE-01, EAA-SAD-02 ADR-04 (5 Human Gate), EAA-AIS-05 §3.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-37.

Năm Human Gate tới giờ chỉ hỏi được một câu nhị phân: *duyệt hay không duyệt?*
Câu ấy đúng cho G3 (review diff) và G4 (nghiệm thu) — ở đó có đúng một vật thể
để chấp nhận hay bác bỏ. Nhưng ở những chỗ có **nhiều cách làm đều đúng** —
chọn kiến trúc tại G1, chọn hướng đi khi vòng tự sửa cạn N lần — thì một nút
"duyệt" buộc con người phải duyệt cái mà Agent đã tự chọn, và lựa chọn thật sự
đã xảy ra trước đó, ở chỗ không ai nhìn thấy.

Ba điều module này giữ
-----------------------

1. **Đủ hai phương án trở lên.** Một "lựa chọn" có đúng một mục là một quyết
   định đã có sẵn, chỉ khoác áo lựa chọn. Nó tệ hơn không có lựa chọn, vì nó
   tạo cảm giác đã cân nhắc.

2. **Mỗi phương án phải nói cả mặt trái.** Một danh sách chỉ toàn ưu điểm
   không giúp ai chọn được gì; nó chỉ chuyển trách nhiệm sang người bấm nút.
   Phương án thiếu ``cons`` bị từ chối ngay khi dựng.

3. **Phương án bị loại vẫn được lưu.** Sáu tháng sau, câu hỏi hữu ích không
   phải "ta đã chọn gì" — Git trả lời được — mà là "ta đã cân nhắc những gì và
   vì sao loại chúng". Quyết định ghi lại toàn bộ tập phương án, không chỉ cái
   thắng.

Ai sinh ra phương án
---------------------

Con người viết tay được, và mô hình đề xuất được. Cả hai đi qua cùng một cửa
kiểm ở đây, vì đề xuất của mô hình là *proposed fact* y như mọi trích xuất khác
trong hệ thống này — và Agent gợi ý ba cách rồi tự chọn một cách hộ người dùng
thì lại quay về đúng vấn đề ban đầu.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "OptionError",
    "Option",
    "OptionSet",
    "LlmOptionProposer",
    "OPTIONS_FILE",
]

#: Nơi giữ các tập phương án đang chờ người chọn, theo từng gate.
OPTIONS_FILE = ".eaa/gate_options.json"

_MA_HOP_LE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


class OptionError(Exception):
    """Tập phương án không dùng được để đặt lên bàn quyết định."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Option:
    """Một cách làm, kèm đánh đổi của nó."""

    id: str
    title: str
    summary: str = ""
    pros: tuple[str, ...] = ()
    cons: tuple[str, ...] = ()
    #: Agent nghĩ đây là cách nên chọn — GỢI Ý, không phải quyết định.
    recommended: bool = False
    #: Vì sao gợi ý (hoặc vì sao không). Đây là phần "tự giải thích".
    rationale: str = ""

    def __post_init__(self) -> None:
        if not _MA_HOP_LE.match(self.id or ""):
            raise OptionError(
                f"Mã phương án không hợp lệ: {self.id!r}. Chỉ chữ, số, gạch — "
                "mã này được gõ lại trên dòng lệnh khi chọn."
            )
        if not self.title.strip():
            raise OptionError(f"Phương án {self.id!r} thiếu tiêu đề")
        if not self.cons:
            raise OptionError(
                f"Phương án {self.id!r} không nêu mặt trái nào.\n"
                "Một danh sách chỉ toàn ưu điểm không giúp ai chọn được gì — nó "
                "chỉ chuyển trách nhiệm sang người bấm nút. Mọi cách làm đều có "
                "cái giá của nó; nếu chưa thấy, nghĩa là chưa tìm."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "pros": list(self.pros),
            "cons": list(self.cons),
            "recommended": self.recommended,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "Option":
        if not isinstance(d, dict):
            raise OptionError(f"phương án phải là ánh xạ khóa–giá trị: {d!r}")
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            summary=str(d.get("summary", "")),
            pros=tuple(str(x) for x in (d.get("pros") or [])),
            cons=tuple(str(x) for x in (d.get("cons") or [])),
            recommended=bool(d.get("recommended", False)),
            rationale=str(d.get("rationale", "")),
        )

    def render(self, *, chosen: bool = False) -> str:
        nhan = "  ← ĐÃ CHỌN" if chosen else ("  ← Agent gợi ý" if self.recommended else "")
        dong = [f"  [{self.id}] {self.title}{nhan}"]
        if self.summary:
            dong.append(f"      {self.summary}")
        for p in self.pros:
            dong.append(f"      + {p}")
        for c in self.cons:
            dong.append(f"      − {c}")
        if self.rationale:
            dong.append(f"      lý do: {self.rationale}")
        return "\n".join(dong)


@dataclass(frozen=True)
class OptionSet:
    """Câu hỏi cần quyết, cùng các cách trả lời nó."""

    question: str
    options: tuple[Option, ...]
    gate_id: str = ""
    #: Ai/cái gì dựng ra tập này — người, hay mã model nào.
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise OptionError("Tập phương án phải nêu rõ câu hỏi cần quyết")
        if len(self.options) < 2:
            raise OptionError(
                f"Chỉ có {len(self.options)} phương án. Một 'lựa chọn' có đúng "
                "một mục là một quyết định đã có sẵn, chỉ khoác áo lựa chọn — "
                "và nó tệ hơn không có lựa chọn, vì tạo cảm giác đã cân nhắc."
            )
        ma = [o.id for o in self.options]
        trung = {m for m in ma if ma.count(m) > 1}
        if trung:
            raise OptionError(f"Mã phương án trùng nhau: {sorted(trung)}")
        if sum(1 for o in self.options if o.recommended) > 1:
            raise OptionError(
                "Nhiều hơn một phương án được đánh dấu 'nên chọn'. Gợi ý hai "
                "cách cùng lúc thì không còn là gợi ý."
            )

    def get(self, option_id: str) -> Option:
        for o in self.options:
            if o.id.lower() == (option_id or "").lower():
                return o
        raise OptionError(
            f"Không có phương án {option_id!r} (đang có: {[o.id for o in self.options]})"
        )

    @property
    def recommended(self) -> Option | None:
        return next((o for o in self.options if o.recommended), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "gate_id": self.gate_id,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "options": [o.to_dict() for o in self.options],
        }

    @classmethod
    def from_dict(cls, d: Any) -> "OptionSet":
        if not isinstance(d, dict):
            raise OptionError("tập phương án phải là ánh xạ khóa–giá trị")
        return cls(
            question=str(d.get("question", "")),
            options=tuple(Option.from_dict(o) for o in (d.get("options") or [])),
            gate_id=str(d.get("gate_id", "")),
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
        )

    def render(self, *, chosen_id: str = "") -> str:
        dong = [f"Cần quyết: {self.question}", ""]
        for o in self.options:
            dong.append(o.render(chosen=o.id.lower() == (chosen_id or "").lower()))
            dong.append("")
        if not chosen_id:
            dong.append(
                "Agent KHÔNG tự chọn. Chọn bằng: "
                f"eaa gate approve {self.gate_id or '<gate>'} --option <mã>"
            )
        return "\n".join(dong).rstrip() + "\n"

    # -- lưu trữ -----------------------------------------------------------

    @staticmethod
    def load_all(path: str | Path) -> dict[str, "OptionSet"]:
        path = Path(path)
        if not path.is_file():
            return {}
        try:
            du_lieu = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise OptionError(f"{path}: hồ sơ phương án hỏng — {exc}") from exc
        return {str(g): OptionSet.from_dict(d) for g, d in (du_lieu or {}).items()}

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        hien_co = {g: t.to_dict() for g, t in OptionSet.load_all(path).items()}
        hien_co[self.gate_id] = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(hien_co, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path

    @staticmethod
    def clear(path: str | Path, gate_id: str) -> None:
        path = Path(path)
        hien_co = {g: t.to_dict() for g, t in OptionSet.load_all(path).items()}
        if hien_co.pop(gate_id, None) is None:
            return
        path.write_text(
            json.dumps(hien_co, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


# --------------------------------------------------------------------------
# Đề xuất bằng mô hình nền
# --------------------------------------------------------------------------

_LUOC_DO = """{
  "options": [
    {
      "id": "<mã ngắn, chỉ chữ/số/gạch>",
      "title": "<tên phương án, một dòng>",
      "summary": "<mô tả cách làm, 1-2 câu>",
      "pros": ["<ưu điểm cụ thể>"],
      "cons": ["<mặt trái cụ thể — BẮT BUỘC, mọi cách làm đều có cái giá>"],
      "recommended": false,
      "rationale": "<vì sao nên hoặc không nên chọn cách này>"
    }
  ]
}"""


@dataclass
class LlmOptionProposer:
    """Hỏi mô hình nền các cách làm khả dĩ, kèm đánh đổi.

    Đề xuất là *proposed fact*: nó đi qua cùng cửa kiểm với phương án viết tay,
    và nó KHÔNG tự chọn thay người. Đánh dấu ``recommended`` là gợi ý có lý do,
    không phải một quyết định đã đưa ra hộ.
    """

    llm: Any
    budget: int = 2500

    def propose(
        self, question: str, *, context: str = "", gate_id: str = "", count: int = 3
    ) -> OptionSet:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=(
                "Bạn giúp một kỹ sư nhúng chọn giữa các cách làm. Nêu các phương "
                "án KHÁC NHAU VỀ BẢN CHẤT, không phải các biến thể của cùng một "
                "cách. Mỗi phương án BẮT BUỘC nêu mặt trái thật sự — nếu chưa "
                "thấy mặt trái nào thì nghĩa là chưa tìm, không phải là không có. "
                "Được đánh dấu nhiều nhất MỘT phương án nên chọn, kèm lý do. "
                "Không tự quyết định thay người."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Quyết định cần đưa ra: {question}\n\n"
                    + (f"Bối cảnh:\n{context}\n\n" if context else "")
                    + f"Nêu {count} phương án. Trả về ĐÚNG một khối JSON theo "
                    f"lược đồ sau, không kèm giải thích ngoài khối:\n\n"
                    f"```json\n{_LUOC_DO}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module=f"phương án cho {gate_id or 'quyết định'}",
            budget=self.budget + 800,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise OptionError(f"Không đề xuất được phương án: {exc}") from exc

        du_lieu = _boc_json(van_ban)
        return OptionSet(
            question=question,
            options=tuple(Option.from_dict(o) for o in (du_lieu.get("options") or [])),
            gate_id=gate_id,
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )


def _boc_json(van_ban: str) -> dict[str, Any]:
    khop = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", van_ban, re.DOTALL)
    tho = khop.group(1) if khop else van_ban[van_ban.find("{") : van_ban.rfind("}") + 1]
    if not tho.strip():
        raise OptionError(
            "Phản hồi không chứa khối JSON nào. Bỏ đề xuất, không đoán thay."
        )
    try:
        du_lieu = json.loads(tho)
    except json.JSONDecodeError as exc:
        raise OptionError(f"JSON hỏng — {exc}. Bỏ đề xuất.") from exc
    if not isinstance(du_lieu, dict):
        raise OptionError("JSON trả về không phải một đối tượng")
    return du_lieu


def boc_json(van_ban: str, loi: type[Exception] = OptionError) -> dict[str, Any]:
    """Bóc khối JSON, rồi ĐỔI loại ngoại lệ sang loại của module gọi tới.

    Vì sao cần lớp vỏ này: tám module dùng chung bộ bóc JSON, nhưng CLI bắt
    ngoại lệ THEO MODULE (``ProposeError``, ``InterfaceError``, …). Ném thẳng
    ``OptionError`` từ trong ``eaa propose`` khiến nó lọt qua mọi lớp bắt lỗi và
    đổ ra một traceback thô — người dùng thấy một vệt stack thay vì một câu nói
    rõ chuyện gì vừa xảy ra.

    Lỗi ấy chỉ lộ ra khi chạy bằng MockLLM: adapter giả lập không trả lời prompt
    dạng lược đồ JSON, và đó chính là cảnh của một người thử sản phẩm khi chưa
    có khóa API — tức là cảnh đầu tiên họ gặp.
    """
    try:
        return _boc_json(van_ban)
    except OptionError as exc:
        if loi is OptionError:
            raise
        raise loi(str(exc)) from exc
