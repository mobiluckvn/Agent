"""Phân tích hỏng hóc và chế độ an toàn — N-016, N-017.

EAA-SRS-01 FR-DIA-01; công đoạn B2. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-44.

Hệ nhúng không có ai ngồi nhìn. Trên máy tính, một tiến trình hỏng thì có log,
có người dùng phàn nàn, có bảng điều khiển đỏ lên. Trên một bo mạch trong tủ
điện, một cảm biến trả rác sẽ được xử lý như số thật cho tới khi có gì đó cháy.

Nên câu hỏi trung tâm của module này không phải "cái gì có thể hỏng" — danh
sách ấy dài vô hạn — mà là **hỏng thì có ai biết không**.

Ba điều bắt buộc, và điều thứ hai là điều hay thiếu nhất
---------------------------------------------------------

1. **Phủ hết cơ cấu chấp hành và cảm biến.** Mỗi thứ trong hồ sơ phần cứng có
   thể hỏng theo cách riêng của nó. Bỏ sót một cái là bỏ sót đúng cái sẽ hỏng.

2. **Mỗi hỏng hóc phải có CÁCH PHÁT HIỆN.** Một hỏng hóc không phát hiện được
   là một hỏng hóc sẽ được phát hiện trên bàn thí nghiệm, bằng khói. Phân tích
   liệt kê được mười kiểu hỏng mà không nói cách nhận ra chúng thì nó chỉ là
   một danh sách lo lắng.

3. **Chế độ an toàn phải nói rõ điều kiện VÀO và RA.** Vào mà không ra được là
   một cục gạch; ra tự động mà không kiểm điều kiện là quay lại đúng sự cố vừa
   thoát.

Agent đề xuất, người chốt
--------------------------

Phân tích an toàn là nơi hậu quả của việc sai lớn nhất trong cả sản phẩm, nên
nó ở mức tự chủ thấp: Agent dựng bản đề xuất đầy đủ và nêu rõ chỗ nó không
chắc, người đọc từng dòng rồi chốt tại G1. Không có đường nào để bản này tự có
hiệu lực.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "SafetyError",
    "FailureMode",
    "SafeState",
    "SafetyAnalysis",
    "LlmSafetyAnalyst",
    "SAFETY_FILE",
    "MUC_NGHIEM_TRONG",
]

#: Tệp phân tích an toàn ở tầng dự án, cạnh constraints.yaml.
SAFETY_FILE = "safety.yaml"

#: Mức nghiêm trọng, từ nhẹ tới nặng. Mức cao nhất đòi cách phát hiện.
MUC_NGHIEM_TRONG: tuple[str, ...] = ("thap", "trung_binh", "cao", "nguy_hiem")

_MA = re.compile(r"^[a-z][a-z0-9_]{2,39}$")


class SafetyError(Exception):
    """Bản phân tích an toàn không dùng được."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FailureMode:
    """Một kiểu hỏng: hỏng gì → biểu hiện ra sao → hậu quả gì → nhận ra bằng gì."""

    id: str
    resource: str
    failure: str
    symptom: str = ""
    effect: str = ""
    #: Làm sao FIRMWARE biết điều này đang xảy ra. Rỗng = không phát hiện được.
    detection: str = ""
    mitigation: str = ""
    severity: str = "trung_binh"

    def __post_init__(self) -> None:
        if not _MA.match(self.id or ""):
            raise SafetyError(f"Mã kiểu hỏng không hợp lệ: {self.id!r}")
        if not self.resource.strip():
            raise SafetyError(f"{self.id}: không nêu hỏng ở đâu")
        if not self.failure.strip():
            raise SafetyError(f"{self.id}: không nêu hỏng cái gì")
        if self.severity not in MUC_NGHIEM_TRONG:
            raise SafetyError(
                f"{self.id}: mức nghiêm trọng {self.severity!r} không hợp lệ "
                f"(hợp lệ: {list(MUC_NGHIEM_TRONG)})"
            )

    @property
    def detectable(self) -> bool:
        return bool(self.detection.strip())

    @property
    def serious(self) -> bool:
        return self.severity in ("cao", "nguy_hiem")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource": self.resource,
            "failure": self.failure,
            "symptom": self.symptom,
            "effect": self.effect,
            "detection": self.detection,
            "mitigation": self.mitigation,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "FailureMode":
        if not isinstance(d, dict) or not d.get("id"):
            raise SafetyError(f"kiểu hỏng thiếu 'id': {d!r}")
        return cls(
            id=str(d["id"]).strip().lower(),
            resource=str(d.get("resource", "")),
            failure=str(d.get("failure", "")),
            symptom=str(d.get("symptom", "")),
            effect=str(d.get("effect", "")),
            detection=str(d.get("detection", "")),
            mitigation=str(d.get("mitigation", "")),
            severity=str(d.get("severity", "trung_binh")),
        )

    def render(self) -> str:
        dau = "!" if self.serious else "·"
        dong = [f"  {dau} [{self.id}] {self.resource}: {self.failure} ({self.severity})"]
        if self.symptom:
            dong.append(f"      biểu hiện: {self.symptom}")
        if self.effect:
            dong.append(f"      hậu quả  : {self.effect}")
        dong.append(
            f"      phát hiện: {self.detection}" if self.detectable
            else "      phát hiện: KHÔNG CÓ CÁCH NÀO — sẽ lộ ra trên bàn thí nghiệm"
        )
        if self.mitigation:
            dong.append(f"      xử lý    : {self.mitigation}")
        return "\n".join(dong)


@dataclass(frozen=True)
class SafeState:
    """Trạng thái đưa thiết bị về khi mất điều khiển."""

    description: str
    entry: tuple[str, ...] = ()
    exit: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise SafetyError("Chế độ an toàn không nêu nó là trạng thái gì")
        if not self.entry:
            raise SafetyError(
                "Chế độ an toàn không nêu điều kiện VÀO. Một trạng thái không "
                "biết khi nào phải vào thì không bao giờ được vào."
            )
        if not self.exit:
            raise SafetyError(
                "Chế độ an toàn không nêu điều kiện RA. Vào mà không ra được là "
                "một cục gạch; và nếu chủ ý không cho ra thì phải viết ra điều "
                "đó (ví dụ: 'chỉ thoát bằng khởi động lại nguồn')."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "entry": list(self.entry),
            "exit": list(self.exit),
            "actions": list(self.actions),
        }

    @classmethod
    def from_dict(cls, d: Any) -> "SafeState":
        if not isinstance(d, dict):
            raise SafetyError("chế độ an toàn phải là ánh xạ khóa–giá trị")
        return cls(
            description=str(d.get("description", "")),
            entry=tuple(str(x) for x in (d.get("entry") or [])),
            exit=tuple(str(x) for x in (d.get("exit") or [])),
            actions=tuple(str(x) for x in (d.get("actions") or [])),
        )

    def render(self) -> str:
        dong = [f"  Trạng thái an toàn: {self.description}"]
        dong.append("      vào khi:")
        dong += [f"        · {x}" for x in self.entry]
        dong.append("      ra khi:")
        dong += [f"        · {x}" for x in self.exit]
        if self.actions:
            dong.append("      việc phải làm khi vào:")
            dong += [f"        · {x}" for x in self.actions]
        return "\n".join(dong)


@dataclass(frozen=True)
class SafetyAnalysis:
    """Bản phân tích hỏng hóc + chế độ an toàn của một dự án."""

    modes: tuple[FailureMode, ...]
    safe_state: SafeState | None = None
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Bản phân tích an toàn là ĐỀ XUẤT cho tới khi người chốt tại G1, nên
        mức cao nhất nó đạt được là GIẢ ĐỊNH. Còn kiểu hỏng nào chưa có cách
        phát hiện thì tụt xuống KHÔNG KIỂM ĐƯỢC — đúng nghĩa đen: hỏng ấy xảy
        ra mà firmware không có cách nào biết.
        """
        from eaa.confidence import GIA_DINH, KHONG_KIEM_DUOC

        return KHONG_KIEM_DUOC if self.undetectable else GIA_DINH

    @property
    def undetectable(self) -> list[FailureMode]:
        """Hỏng hóc không có cách phát hiện — điều hay thiếu nhất."""
        return [m for m in self.modes if not m.detectable]

    def uncovered(self, hardware: Any) -> list[str]:
        """Tài nguyên trong hồ sơ mà không kiểu hỏng nào nhắc tới.

        Bỏ sót một cơ cấu chấp hành là bỏ sót đúng cái sẽ hỏng — và không ai
        phát hiện ra sự bỏ sót ấy bằng cách đọc một danh sách dài.
        """
        if hardware is None:
            return []
        co = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
        co += [str(c.get("id", "")) for c in getattr(hardware, "components", [])]
        da_phu = {m.resource.lower() for m in self.modes}
        return sorted(x for x in co if x and x.lower() not in da_phu)

    def gaps(self, hardware: Any = None) -> list[str]:
        """Mọi chỗ bản phân tích còn hở — gom một chỗ để không ai phải tự soát."""
        thieu: list[str] = []

        khong_thay = self.undetectable
        if khong_thay:
            thieu.append(
                f"{len(khong_thay)} kiểu hỏng KHÔNG có cách phát hiện: "
                + ", ".join(m.id for m in khong_thay)
                + ". Hỏng không phát hiện được là hỏng sẽ lộ ra trên bàn thí "
                "nghiệm, bằng khói."
            )

        nang_ma_khong_thay = [m for m in khong_thay if m.serious]
        if nang_ma_khong_thay:
            thieu.append(
                "Trong đó có mức CAO/NGUY HIỂM: "
                + ", ".join(m.id for m in nang_ma_khong_thay)
                + ". Mức này bắt buộc phải có cách phát hiện."
            )

        chua_phu = self.uncovered(hardware)
        if chua_phu:
            thieu.append(
                "Tài nguyên chưa có kiểu hỏng nào: " + ", ".join(chua_phu)
                + ". Mỗi thứ trong hồ sơ đều hỏng được theo cách riêng của nó."
            )

        if self.safe_state is None and _co_co_cau_chap_hanh(hardware):
            thieu.append(
                "Có cơ cấu chấp hành nhưng CHƯA định nghĩa chế độ an toàn. "
                "Không có nó thì lỗi phần mềm thành hỏng cơ khí."
            )
        return thieu

    def to_dict(self) -> dict[str, Any]:
        du_lieu: dict[str, Any] = {
            "version": 1,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "failure_modes": [m.to_dict() for m in self.modes],
        }
        if self.safe_state is not None:
            du_lieu["safe_state"] = self.safe_state.to_dict()
        return du_lieu

    @classmethod
    def from_dict(cls, d: Any) -> "SafetyAnalysis":
        if not isinstance(d, dict):
            raise SafetyError("bản phân tích an toàn phải là ánh xạ khóa–giá trị")
        an_toan = d.get("safe_state")
        return cls(
            modes=tuple(FailureMode.from_dict(m) for m in (d.get("failure_modes") or [])),
            safe_state=SafeState.from_dict(an_toan) if an_toan else None,
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _DAU_TEP + yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: str | Path) -> "SafetyAnalysis | None":
        path = Path(path)
        if not path.is_file():
            return None
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise SafetyError(f"{path}: YAML không hợp lệ — {exc}") from exc
        return SafetyAnalysis.from_dict(du_lieu)

    def render(self, hardware: Any = None) -> str:
        dong = [f"Phân tích hỏng hóc — {len(self.modes)} kiểu hỏng", ""]
        for m in sorted(self.modes, key=lambda x: (-MUC_NGHIEM_TRONG.index(x.severity), x.id)):
            dong.append(m.render())
            dong.append("")

        if self.safe_state is not None:
            dong.append(self.safe_state.render())
            dong.append("")

        thieu = self.gaps(hardware)
        if thieu:
            dong.append("CÒN HỞ:")
            dong += [f"  · {t}" for t in thieu]
            dong.append("")

        dong += [
            "Agent KHÔNG tự chốt bản này. Phân tích an toàn là nơi hậu quả của",
            "việc sai lớn nhất trong cả sản phẩm — người đọc từng dòng rồi chốt.",
            "  Chốt cùng ràng buộc và kiến trúc: eaa gate approve G1",
        ]
        return "\n".join(dong)


def _co_co_cau_chap_hanh(hardware: Any) -> bool:
    """Hồ sơ có thứ gì làm ra chuyển động hay công suất không.

    Nhận biết qua khai báo của DỰ ÁN (``kind``/``actuator``), không qua tên
    linh kiện — engine không được biết tên một họ linh kiện nào.
    """
    if hardware is None:
        return False
    for c in getattr(hardware, "components", []):
        if bool(c.get("actuator")) or str(c.get("kind", "")).lower() == "actuator":
            return True
    return False


_DAU_TEP = """\
# Phân tích hỏng hóc và chế độ an toàn — BẢN ĐỀ XUẤT do `eaa safety propose` dựng.
#
# Câu hỏi trung tâm của tệp này KHÔNG phải "cái gì có thể hỏng" — danh sách ấy
# dài vô hạn — mà là HỎNG THÌ CÓ AI BIẾT KHÔNG. Hệ nhúng không có ai ngồi nhìn:
# một cảm biến trả rác sẽ được xử lý như số thật cho tới khi có gì đó cháy.
#
# Mỗi mục thiếu `detection` là một kiểu hỏng sẽ lộ ra trên bàn thí nghiệm.
# Đọc từng dòng rồi chốt tại G1.

"""


_LUOC_DO = """{
  "failure_modes": [
    {
      "id": "<mã ngắn, chữ thường và gạch dưới>",
      "resource": "<id ngoại vi hoặc linh kiện TRONG hồ sơ phần cứng>",
      "failure": "<hỏng cái gì, cụ thể>",
      "symptom": "<firmware nhìn thấy gì khi điều này xảy ra>",
      "effect": "<hậu quả với hệ thống và với người>",
      "detection": "<firmware nhận ra bằng cách nào — BẮT BUỘC với mức cao/nguy hiểm>",
      "mitigation": "<làm gì khi phát hiện>",
      "severity": "thap|trung_binh|cao|nguy_hiem"
    }
  ],
  "safe_state": {
    "description": "<trạng thái an toàn là gì>",
    "entry": ["<điều kiện phải vào trạng thái này>"],
    "exit": ["<điều kiện được rời khỏi; nếu chỉ thoát bằng reset thì ghi rõ>"],
    "actions": ["<việc phải làm ngay khi vào>"]
  }
}"""


@dataclass
class LlmSafetyAnalyst:
    """Dựng bản phân tích hỏng hóc bằng mô hình nền."""

    llm: Any
    budget: int = 3000

    def analyse(
        self, *, hardware: Any = None, constraints: Any = None, goal: str = ""
    ) -> SafetyAnalysis:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        tai_nguyen = _liet_ke_tai_nguyen(hardware)
        if not tai_nguyen:
            raise SafetyError(
                "Hồ sơ phần cứng chưa khai ngoại vi hay linh kiện nào, nên không "
                "có gì để phân tích. Phân tích hỏng hóc bám vào thứ CÓ THẬT trên "
                "bo, không phải vào trí tưởng tượng."
            )

        prompt = Prompt(
            system_instruction=(
                "Bạn phân tích hỏng hóc cho một hệ nhúng. Với MỖI tài nguyên "
                "được liệt kê, nêu các kiểu hỏng thực tế. Câu hỏi quan trọng "
                "nhất là FIRMWARE NHẬN RA BẰNG CÁCH NÀO — mức cao và nguy hiểm "
                "BẮT BUỘC có cách phát hiện cụ thể (quá hạn chờ, kiểm tổng, giới "
                "hạn dải, đối chiếu hai nguồn). Không nêu cách phát hiện chung "
                "chung kiểu 'theo dõi'. Chỉ dùng tài nguyên có trong danh sách."
            ),
            layers=[
                PromptLayer(
                    "task",
                    (f"Mục tiêu hệ thống: {goal}\n\n" if goal else "")
                    + f"Tài nguyên CÓ THẬT: {', '.join(tai_nguyen)}\n"
                    + _mo_ta_rang_buoc(constraints)
                    + "\nPhân tích hỏng hóc và định nghĩa chế độ an toàn. Trả về "
                    "ĐÚNG một khối JSON theo lược đồ:\n\n"
                    f"```json\n{_LUOC_DO}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module="phân tích an toàn",
            budget=self.budget + 800,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise SafetyError(f"Không dựng được phân tích an toàn: {exc}") from exc

        from eaa.options import boc_json

        du_lieu = boc_json(van_ban, SafetyError)
        an_toan = du_lieu.get("safe_state")
        return SafetyAnalysis(
            modes=tuple(
                FailureMode.from_dict(m) for m in (du_lieu.get("failure_modes") or [])
            ),
            safe_state=SafeState.from_dict(an_toan) if an_toan else None,
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )


def _liet_ke_tai_nguyen(hardware: Any) -> list[str]:
    if hardware is None:
        return []
    co = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
    co += [str(c.get("id", "")) for c in getattr(hardware, "components", [])]
    return [x for x in co if x]


def _mo_ta_rang_buoc(constraints: Any) -> str:
    if constraints is None:
        return ""
    gioi_han = getattr(constraints, "limits", {}) or {}
    if not gioi_han:
        return ""
    return "Ràng buộc: " + ", ".join(f"{k}={v}" for k, v in sorted(gioi_han.items())) + "\n"
