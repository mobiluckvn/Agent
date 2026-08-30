"""Agent ĐỀ XUẤT, không chỉ đối chiếu — N-006, N-010, N-011, N-014.

EAA-AIS-05 §6.1 (quy trình P1), EAA-SRS-01 FR-KB-01; công đoạn A1 và B2.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-49.

Khoảng cách mà tệp này lấp
---------------------------

Trước bản này, bốn việc của giai đoạn G0/G1 đều đã có cơ chế và đều thiếu đúng
một nửa: engine ĐỌC được ràng buộc, ĐỐI CHIẾU được tiêu chí nghiệm thu, TRA
được bảng chân — nhưng không tự nói ra được một đề xuất nào. Người dùng vẫn
phải tự biết cần khai gì, và đó là rào cản ở đúng bước đầu tiên.

Đối chiếu là việc dễ hơn: nó bắt đầu từ một danh sách đã có. Đề xuất phải bắt
đầu từ trang trắng, và đó chính là chỗ người mới vào nghề mắc kẹt.

Bốn đề xuất, bốn bất biến riêng
--------------------------------

* **Phạm vi (N-006)** — mỗi mục NGOÀI phạm vi phải có lý do. Một danh sách
  "không làm" không kèm lý do thì tới lúc tranh luận chẳng ai bảo vệ được nó,
  và phạm vi sẽ phình ra từng chút một.
* **Ràng buộc (N-010)** — mỗi ràng buộc phải kèm HỆ QUẢ nếu vi phạm. Người
  duyệt tại G1 cần căn cứ để bác, mà "chu kỳ 10 ms" một mình thì không phải căn
  cứ; "quá 10 ms thì con lắc vượt góc phục hồi và đổ" mới là.
* **Tiêu chí nghiệm thu (N-011)** — phải là MỘT CON SỐ, có ĐƠN VỊ, và có CÁCH
  ĐO. Tiêu chí kiểu "chạy mượt" bị từ chối tại chỗ, kèm câu hỏi làm nó đo được.
* **Bảng chân (N-014)** — mỗi chân phải nói nó phục vụ chức năng gì, và chức
  năng ấy có được chân đó hỗ trợ không. Engine không biết chân nào làm được gì;
  nó đối chiếu với bảng chức năng thay thế do DỰ ÁN khai, và nói thẳng khi
  bảng ấy chưa có.

Điều cuối cùng đáng nhấn: cả bốn đều dừng ở ĐỀ XUẤT. Không cái nào tự có hiệu
lực; chúng in ra một khối để người đọc, sửa, rồi dán vào tệp có phiên bản và
duyệt tại gate. Chính hành động dán ấy là quyết định của người.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "ProposeError",
    "ScopeItem",
    "ScopeProposal",
    "ConstraintItem",
    "ConstraintProposal",
    "AcceptanceCriterion",
    "AcceptanceProposal",
    "PinAssignment",
    "PinMapProposal",
    "PlantParameter",
    "PlantModelProposal",
    "LlmProposer",
    "DA_DO",
    "UOC_LUONG",
    "TU_TAI_LIEU",
    "SCOPE_FILE",
    "TRONG",
    "NGOAI",
]

#: Bản chốt phạm vi ở tầng dự án, cạnh constraints.yaml.
SCOPE_FILE = "scope.yaml"

TRONG = "trong"
NGOAI = "ngoai"

_MA = re.compile(r"^[a-z][a-z0-9_]{2,39}$")

#: Từ ngữ mô tả cảm giác chứ không mô tả số đo. Một tiêu chí chứa chúng mà
#: không kèm ngưỡng là tiêu chí không nghiệm thu được — và nó sẽ được tranh cãi
#: đúng vào lúc bàn giao, khi không còn thời gian để đo lại.
_TU_MO_HO: tuple[str, ...] = (
    "mượt", "ổn định", "nhanh", "chính xác", "tốt", "êm", "đủ", "hợp lý",
    "không giật", "phản hồi tốt", "chạy được",
)


class ProposeError(Exception):
    """Bản đề xuất không dùng được."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _so(gia_tri: Any) -> float | None:
    if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
        return None
    return float(gia_tri)


# --------------------------------------------------------------------------
# N-006 — phạm vi và cái KHÔNG làm
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeItem:
    """Một tính năng, và nó nằm trong hay ngoài phạm vi — kèm lý do."""

    feature: str
    side: str = TRONG
    reason: str = ""
    #: Đây là quyết định kiến trúc hay chỉ là chi tiết kỹ thuật hoãn lại.
    architectural: bool = False

    def __post_init__(self) -> None:
        if not self.feature.strip():
            raise ProposeError("mục phạm vi không có tên tính năng")
        if self.side not in (TRONG, NGOAI):
            raise ProposeError(
                f"{self.feature!r}: phía {self.side!r} không hợp lệ (trong|ngoai)"
            )
        # Chỉ mục NGOÀI phạm vi mới bắt buộc lý do. Mục trong phạm vi thì lý do
        # chính là phát biểu bài toán — bắt viết lại chỉ tạo ra chữ thừa.
        if self.side == NGOAI and not self.reason.strip():
            raise ProposeError(
                f"{self.feature!r}: nằm ngoài phạm vi mà không nêu vì sao. Một "
                "danh sách 'không làm' không kèm lý do thì tới lúc tranh luận "
                "chẳng ai bảo vệ được nó."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "side": self.side,
            "reason": self.reason,
            "architectural": self.architectural,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ScopeItem":
        if not isinstance(d, dict):
            raise ProposeError(f"mục phạm vi phải là ánh xạ, nhận {type(d)}")
        return cls(
            feature=str(d.get("feature", "")),
            side=str(d.get("side", TRONG)),
            reason=str(d.get("reason", "")),
            architectural=bool(d.get("architectural", False)),
        )

    def render(self) -> str:
        dau = "＋" if self.side == TRONG else "－"
        dong = f"  {dau} {self.feature}"
        if self.reason:
            dong += f"\n      {self.reason}"
        if self.architectural:
            dong += "\n      (quyết định KIẾN TRÚC, không phải chi tiết kỹ thuật hoãn lại)"
        return dong


@dataclass
class ScopeProposal:
    """Ranh giới của dự án: làm gì, và không làm gì."""

    items: tuple[ScopeItem, ...] = ()
    goal: str = ""
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)

    @property
    def in_scope(self) -> tuple[ScopeItem, ...]:
        return tuple(i for i in self.items if i.side == TRONG)

    @property
    def out_of_scope(self) -> tuple[ScopeItem, ...]:
        return tuple(i for i in self.items if i.side == NGOAI)

    def gaps(self) -> list[str]:
        thieu: list[str] = []
        if not self.in_scope:
            thieu.append("Chưa có tính năng nào TRONG phạm vi — bản này chưa nói dự án làm gì.")
        if not self.out_of_scope:
            thieu.append(
                "Chưa có mục nào NGOÀI phạm vi. Một dự án không có ranh giới là "
                "một dự án sẽ phình ra từng chút một mà không lần nào ai thấy "
                "được điểm nó bắt đầu phình."
            )
        return thieu

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "goal": self.goal,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "scope": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ScopeProposal":
        if not isinstance(d, dict):
            raise ProposeError("bản phạm vi phải là ánh xạ khóa–giá trị")
        return cls(
            items=tuple(ScopeItem.from_dict(x) for x in (d.get("scope") or [])),
            goal=str(d.get("goal", "")),
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _DAU_TEP_PHAM_VI
            + yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: str | Path) -> "ScopeProposal | None":
        path = Path(path)
        if not path.is_file():
            return None
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ProposeError(f"{path}: YAML không hợp lệ — {exc}") from exc
        return ScopeProposal.from_dict(du_lieu)


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Bản đề xuất chưa qua G1. Lập luận tốt tới đâu thì nó vẫn là một đề xuất.
        """
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self) -> str:
        dong = [f"Phạm vi — {len(self.in_scope)} trong, {len(self.out_of_scope)} ngoài"]
        if self.goal:
            dong += ["", f"Mục tiêu: {self.goal}"]
        dong += ["", "TRONG phạm vi:"]
        dong += [i.render() for i in self.in_scope] or ["  (chưa có)"]
        dong += ["", "NGOÀI phạm vi — và vì sao:"]
        dong += [i.render() for i in self.out_of_scope] or ["  (chưa có)"]
        thieu = self.gaps()
        if thieu:
            dong += ["", "CÒN HỞ:"] + [f"  · {t}" for t in thieu]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# N-010 — ràng buộc cứng, mỗi cái kèm HỆ QUẢ
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstraintItem:
    """Một ràng buộc đề xuất: trị số, nó từ đâu ra, và vi phạm thì sao."""

    key: str
    value: Any
    unit: str = ""
    #: Nó suy ra từ đâu — động lực học của đối tượng, hay năng lực của chip.
    rationale: str = ""
    #: Vi phạm thì chuyện gì xảy ra. Đây là thứ người duyệt cần để mà bác.
    consequence: str = ""

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ProposeError("ràng buộc không có tên khóa")
        if not self.consequence.strip():
            raise ProposeError(
                f"{self.key!r}: không nêu HỆ QUẢ nếu vi phạm. Một con số trần "
                "trụi không phải căn cứ để người duyệt bác hay chấp nhận — "
                "'quá 10 ms thì con lắc vượt góc phục hồi và đổ' mới là."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "unit": self.unit,
            "rationale": self.rationale,
            "consequence": self.consequence,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ConstraintItem":
        if not isinstance(d, dict):
            raise ProposeError(f"ràng buộc phải là ánh xạ, nhận {type(d)}")
        return cls(
            key=str(d.get("key", "")),
            value=d.get("value"),
            unit=str(d.get("unit", "")),
            rationale=str(d.get("rationale", "")),
            consequence=str(d.get("consequence", "")),
        )

    def render(self) -> str:
        don_vi = f" {self.unit}" if self.unit else ""
        dong = [f"  {self.key} = {self.value}{don_vi}"]
        if self.rationale:
            dong.append(f"      suy từ : {self.rationale}")
        dong.append(f"      vi phạm: {self.consequence}")
        return "\n".join(dong)


@dataclass
class ConstraintProposal:
    """Bộ ràng buộc đề xuất, để dán vào ``limits`` của ``constraints.yaml``."""

    items: tuple[ConstraintItem, ...] = ()
    forbidden: tuple[str, ...] = ()
    proposed_by: str = ""

    def to_limits(self) -> dict[str, Any]:
        """Khối ``limits`` để dán. Chỉ trị số — lý do và hệ quả ở phần in ra.

        Cố ý KHÔNG nhét lý do vào tệp ràng buộc: tệp ấy được bảng hóa và nạp
        vào 100% prompt (K1), nên mỗi dòng thừa ở đó là token trả cho mọi lần
        gọi mô hình về sau.
        """
        return {i.key: i.value for i in self.items}


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Suy từ năng lực chip và động lực học, nhưng chưa ai chốt — vẫn là đề xuất.
        """
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self) -> str:
        dong = [f"Ràng buộc cứng — {len(self.items)} mục đề xuất", ""]
        dong += [i.render() for i in self.items] or ["  (chưa có)"]
        if self.forbidden:
            dong += ["", "Điều cấm đề xuất:"]
            dong += [f"  · CẤM {c}" for c in self.forbidden]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# N-011 — tiêu chí nghiệm thu ĐO ĐƯỢC
# --------------------------------------------------------------------------

#: Số đo lấy về từ đâu. Ba nguồn, và chúng không thay thế nhau được.
NGUON_DO: tuple[str, ...] = ("telemetry", "dong_ho_do", "quan_sat_nguoi")


@dataclass(frozen=True)
class AcceptanceCriterion:
    """Một tiêu chí nghiệm thu: con số, đơn vị, cách đo, và lấy từ đâu."""

    name: str
    unit: str = ""
    max: float | None = None
    min: float | None = None
    #: Khóa trong khung telemetry, khi nguồn là kênh máy.
    key: str = ""
    #: Đo bằng cách nào — cụ thể tới mức người khác lặp lại được.
    method: str = ""
    source: str = "telemetry"
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ProposeError("tiêu chí nghiệm thu không có tên")
        if self.max is None and self.min is None:
            raise ProposeError(
                f"{self.name!r}: không có ngưỡng. Tiêu chí nghiệm thu phải là "
                "MỘT CON SỐ so được, không phải một mong muốn."
            )
        if not self.unit.strip():
            raise ProposeError(
                f"{self.name!r}: không có đơn vị. Một con số không đơn vị thì "
                "hai người đọc ra hai đại lượng khác nhau."
            )
        if not self.method.strip():
            raise ProposeError(
                f"{self.name!r}: không nói ĐO BẰNG CÁCH NÀO. Ngưỡng không kèm "
                "cách đo là ngưỡng sẽ được tranh cãi đúng vào lúc bàn giao."
            )
        if self.source not in NGUON_DO:
            raise ProposeError(
                f"{self.name!r}: nguồn {self.source!r} không hợp lệ "
                f"(hợp lệ: {list(NGUON_DO)})"
            )
        if self.source == "telemetry" and not self.key.strip():
            raise ProposeError(
                f"{self.name!r}: lấy từ telemetry thì phải nêu khóa trong khung "
                "telemetry, nếu không thì không ai đối chiếu được với cái gì."
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "unit": self.unit}
        if self.key:
            d["key"] = self.key
        if self.max is not None:
            d["max"] = self.max
        if self.min is not None:
            d["min"] = self.min
        d["note"] = self.note or self.method
        return d

    @classmethod
    def from_dict(cls, d: Any) -> "AcceptanceCriterion":
        if not isinstance(d, dict):
            raise ProposeError(f"tiêu chí phải là ánh xạ, nhận {type(d)}")
        return cls(
            name=str(d.get("name", "")),
            unit=str(d.get("unit", "")),
            max=_so(d.get("max")),
            min=_so(d.get("min")),
            key=str(d.get("key", "")),
            method=str(d.get("method", "")),
            source=str(d.get("source", "telemetry")),
            note=str(d.get("note", "")),
        )

    def render(self) -> str:
        nguong = []
        if self.max is not None:
            nguong.append(f"≤ {self.max:g} {self.unit}")
        if self.min is not None:
            nguong.append(f"≥ {self.min:g} {self.unit}")
        return (
            f"  {self.name}: {' và '.join(nguong)}\n"
            f"      đo bằng: {self.method}\n"
            f"      nguồn  : {self.source}" + (f" (khóa {self.key})" if self.key else "")
        )


def vague_reason(statement: str) -> str:
    """Câu này có phải một mong muốn thay vì một tiêu chí không (N-011).

    Trả về lý do từ chối, hoặc chuỗi rỗng nếu câu có vẻ đo được. Phép kiểm cố ý
    THÔ: nó chỉ bắt được dạng lộ liễu nhất. Nhưng dạng lộ liễu nhất lại là dạng
    hay được viết vào bản yêu cầu nhất, nên bắt được nó vẫn đáng.
    """
    van_ban = (statement or "").lower()
    if not van_ban.strip():
        return "câu rỗng"
    co_so = re.search(r"\d", van_ban)
    tu = [t for t in _TU_MO_HO if t in van_ban]
    if tu and not co_so:
        return (
            f"chứa {', '.join(repr(t) for t in tu)} mà không có con số nào. "
            "Hỏi lại: bao nhiêu thì đủ, đo ở đâu, bằng gì?"
        )
    if not co_so:
        return "không có con số nào để so — chưa phải tiêu chí nghiệm thu"
    return ""


@dataclass
class AcceptanceProposal:
    """Bộ tiêu chí nghiệm thu đề xuất, để dán vào ``acceptance``."""

    criteria: tuple[AcceptanceCriterion, ...] = ()
    #: Câu bị TỪ CHỐI vì chưa đo được, kèm lý do — phần đáng đọc nhất.
    rejected: tuple[tuple[str, str], ...] = ()
    scenarios: tuple[str, ...] = ()
    proposed_by: str = ""

    def to_acceptance(self) -> dict[str, Any]:
        return {
            "scenarios": list(self.scenarios),
            "measurements": [c.to_dict() for c in self.criteria],
        }


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Tiêu chí chưa được chốt tại G1 thì chưa ràng buộc ai.
        """
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self) -> str:
        dong = [f"Tiêu chí nghiệm thu — {len(self.criteria)} số đo", ""]
        dong += [c.render() for c in self.criteria] or ["  (chưa có)"]
        if self.scenarios:
            dong += ["", "Kịch bản nghiệm thu:"] + [f"  · {s}" for s in self.scenarios]
        if self.rejected:
            dong += ["", "TỪ CHỐI vì chưa đo được:"]
            for cau, ly_do in self.rejected:
                dong.append(f"  ✗ {cau}\n      {ly_do}")
        return "\n".join(dong)


# --------------------------------------------------------------------------
# N-014 — bảng chân, và chân có hỗ trợ chức năng cần không
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# N-060 — mô hình đối tượng điều khiển
# --------------------------------------------------------------------------

#: Một tham số vật lý đến từ đâu. Ba mức, và mức giữa là mức nguy hiểm nhất:
#: nó trông như một con số đo được nhưng chưa ai cầm thước.
DA_DO = "da_do"
UOC_LUONG = "uoc_luong"
TU_TAI_LIEU = "tu_tai_lieu"
NGUON_THAM_SO: tuple[str, ...] = (DA_DO, UOC_LUONG, TU_TAI_LIEU)


@dataclass(frozen=True)
class PlantParameter:
    """Một tham số vật lý của đối tượng, kèm xuất xứ."""

    name: str
    value: float
    unit: str
    source: str = UOC_LUONG
    #: Đo bằng cách nào. BẮT BUỘC khi tham số mới chỉ là ước lượng.
    how_to_measure: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ProposeError("tham số mô hình không có tên")
        if not self.unit.strip():
            raise ProposeError(f"{self.name!r}: tham số vật lý không có đơn vị")
        if self.source not in NGUON_THAM_SO:
            raise ProposeError(
                f"{self.name!r}: xuất xứ {self.source!r} không hợp lệ "
                f"(hợp lệ: {list(NGUON_THAM_SO)})"
            )
        if self.source == UOC_LUONG and not self.how_to_measure.strip():
            raise ProposeError(
                f"{self.name!r}: mới là ƯỚC LƯỢNG mà không nói đo bằng cách nào. "
                "Một ước lượng không kèm cách kiểm sẽ lặng lẽ được đọc như một "
                "số đo — và mọi kết luận rút từ mô phỏng thừa hưởng sai số ấy "
                "mà không ai biết."
            )

    @property
    def verified(self) -> bool:
        return self.source == DA_DO

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA

        return {DA_DO: DA_KIEM, TU_TAI_LIEU: SUY_RA}.get(self.source, GIA_DINH)

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "name": self.name,
                "value": self.value,
                "unit": self.unit,
                "source": self.source,
                "how_to_measure": self.how_to_measure,
                "note": self.note,
            }.items()
            if v not in ("", None)
        }

    @classmethod
    def from_dict(cls, d: Any) -> "PlantParameter":
        if not isinstance(d, dict):
            raise ProposeError(f"tham số phải là ánh xạ, nhận {type(d)}")
        so = _so(d.get("value"))
        if so is None:
            raise ProposeError(f"tham số {d.get('name')!r} không có trị số")
        return cls(
            name=str(d.get("name", "")),
            value=so,
            unit=str(d.get("unit", "")),
            source=str(d.get("source", UOC_LUONG)),
            how_to_measure=str(d.get("how_to_measure", "")),
            note=str(d.get("note", "")),
        )

    def render(self) -> str:
        nhan = {DA_DO: "đã đo", UOC_LUONG: "ƯỚC LƯỢNG", TU_TAI_LIEU: "từ tài liệu"}
        dong = [f"  {self.name} = {self.value:g} {self.unit}   [{nhan[self.source]}]"]
        if self.how_to_measure:
            dong.append(f"      đo bằng: {self.how_to_measure}")
        if self.note:
            dong.append(f"      {self.note}")
        return "\n".join(dong)


@dataclass
class PlantModelProposal:
    """Mô hình toán của đối tượng điều khiển, kèm giới hạn của chính nó."""

    kind: str = ""
    states: tuple[str, ...] = ()
    equations: str = ""
    parameters: tuple[PlantParameter, ...] = ()
    #: Hiện tượng mô hình BỎ QUA. Bắt buộc phải có ít nhất một.
    ignored: tuple[str, ...] = ()
    validity: str = ""
    proposed_by: str = ""

    def __post_init__(self) -> None:
        if not self.ignored:
            raise ProposeError(
                "Mô hình không nêu hiện tượng nào bị bỏ qua. Mọi mô hình đều bỏ "
                "qua điều gì đó — một mô hình tự nhận không bỏ qua gì là một mô "
                "hình chưa ai nghĩ tới giới hạn của nó, và người đọc sẽ tin nó "
                "quá mức."
            )

    @property
    def assumptions(self) -> tuple[PlantParameter, ...]:
        """Tham số chưa đo được — vào Assumption Log ở trạng thái proposed."""
        return tuple(p for p in self.parameters if not p.verified)

    def to_assumption_log(self) -> list[dict[str, Any]]:
        """Dựng mục cho Assumption Log của hồ sơ phần cứng."""
        return [
            {
                "id": f"plant-{p.name}",
                "statement": f"{p.name} = {p.value:g} {p.unit} ({p.source})",
                "status": "proposed",
                "how_to_verify": p.how_to_measure or "chưa nêu cách kiểm",
                "blocks": ["mô phỏng", "chỉnh tham số điều khiển"],
            }
            for p in self.assumptions
        ]


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Mô hình chưa đối chiếu với số đo thật của đối tượng.
        """
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self) -> str:
        dong = [f"Mô hình đối tượng — {self.kind or '(chưa nêu loại)'}", ""]
        if self.states:
            dong.append(f"Biến trạng thái: {', '.join(self.states)}")
        if self.equations:
            dong += ["", self.equations]
        dong += ["", "Tham số:"]
        dong += [p.render() for p in self.parameters] or ["  (chưa có)"]

        dong += ["", "Mô hình này BỎ QUA:"]
        dong += [f"  · {x}" for x in self.ignored]
        if self.validity:
            dong += ["", f"Chỉ đúng trong: {self.validity}"]

        chua_do = self.assumptions
        if chua_do:
            dong += [
                "",
                f"{len(chua_do)}/{len(self.parameters)} tham số CHƯA ĐO. Mọi kết "
                "luận rút từ mô phỏng",
                "thừa hưởng sai số của chúng — đưa vào Assumption Log rồi đo dần:",
            ]
            dong += [f"  · {p.name}: {p.how_to_measure}" for p in chua_do]
        return "\n".join(dong)


@dataclass(frozen=True)
class PinAssignment:
    """Một chân được gán: đi đâu, làm gì, hướng nào."""

    pin: str
    function: str
    direction: str = ""
    peripheral: str = ""
    signal: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.pin.strip():
            raise ProposeError("mục bảng chân không có tên chân")
        if not self.function.strip():
            raise ProposeError(
                f"{self.pin!r}: không nêu chân này dùng làm chức năng gì — không "
                "có nó thì không kiểm được chân có hỗ trợ chức năng ấy không."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "pin": self.pin,
                "function": self.function,
                "direction": self.direction,
                "peripheral": self.peripheral,
                "signal": self.signal,
                "note": self.note,
            }.items()
            if v
        }

    @classmethod
    def from_dict(cls, d: Any) -> "PinAssignment":
        if not isinstance(d, dict):
            raise ProposeError(f"mục bảng chân phải là ánh xạ, nhận {type(d)}")
        return cls(
            pin=str(d.get("pin", "")),
            function=str(d.get("function", "")),
            direction=str(d.get("direction", "")),
            peripheral=str(d.get("peripheral", "")),
            signal=str(d.get("signal", "")),
            note=str(d.get("note", "")),
        )


#: Kết cục một phép kiểm chân — ba trạng thái, và trạng thái thứ ba là lý do
#: cơ chế này tồn tại thay vì một cờ đúng/sai.
PIN_HO_TRO = "ho-tro"
PIN_KHONG_HO_TRO = "khong-ho-tro"
PIN_KHONG_KIEM_DUOC = "khong-kiem-duoc"


@dataclass(frozen=True)
class PinCheck:
    """Chân này có làm được chức năng đang gán cho nó không."""

    pin: str
    function: str
    status: str
    detail: str = ""

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return KHONG_KIEM_DUOC if self.status == PIN_KHONG_KIEM_DUOC else SUY_RA

    def render(self) -> str:
        nhan = {
            PIN_HO_TRO: "hỗ trợ",
            PIN_KHONG_HO_TRO: "KHÔNG HỖ TRỢ",
            PIN_KHONG_KIEM_DUOC: "chưa kiểm được",
        }[self.status]
        return f"  {self.pin:<10} {self.function:<16} {nhan}" + (
            f"  — {self.detail}" if self.detail else ""
        )


@dataclass
class PinMapProposal:
    """Bảng chân đề xuất, kèm phép kiểm chức năng thay thế."""

    assignments: tuple[PinAssignment, ...] = ()
    proposed_by: str = ""
    #: Nguồn của bảng: trích từ sơ đồ nguyên lý, hay do mô hình đề xuất.
    source: str = "đề xuất"

    def to_pin_map(self) -> dict[str, Any]:
        return {a.pin: a.to_dict() for a in self.assignments}

    def check(self, pin_functions: Any) -> list[PinCheck]:
        """Đối chiếu từng chân với bảng chức năng thay thế do DỰ ÁN khai.

        ``pin_functions`` là ánh xạ ``tên chân -> danh sách chức năng``, lấy từ
        ``hardware_profile.yaml``. Engine KHÔNG biết chân nào làm được gì — nó
        không được biết, vì biết là ghim một họ vi điều khiển vào engine.

        Chưa khai bảng ấy thì mọi chân về ``khong-kiem-duoc``, và đó là một câu
        trả lời trung thực. Câu trả lời sai là im lặng cho qua rồi để người
        tưởng đã kiểm.
        """
        bang = {
            str(k): [str(x).lower() for x in (v or [])]
            for k, v in (pin_functions or {}).items()
        }
        ket_qua: list[PinCheck] = []
        for a in self.assignments:
            if not bang:
                ket_qua.append(
                    PinCheck(
                        a.pin,
                        a.function,
                        PIN_KHONG_KIEM_DUOC,
                        "hồ sơ phần cứng chưa khai 'pin_functions'",
                    )
                )
                continue
            if a.pin not in bang:
                ket_qua.append(
                    PinCheck(
                        a.pin,
                        a.function,
                        PIN_KHONG_KIEM_DUOC,
                        f"chân {a.pin!r} không có trong bảng chức năng đã khai",
                    )
                )
                continue
            co = bang[a.pin]
            if a.function.lower() in co:
                ket_qua.append(PinCheck(a.pin, a.function, PIN_HO_TRO))
            else:
                ket_qua.append(
                    PinCheck(
                        a.pin,
                        a.function,
                        PIN_KHONG_HO_TRO,
                        f"chân này khai hỗ trợ: {', '.join(co) or '(không gì)'}",
                    )
                )
        return ket_qua

    def conflicts(self) -> list[str]:
        """Hai chức năng cùng đòi một chân — bắt trước khi ai đó hàn dây."""
        thay: dict[str, list[str]] = {}
        for a in self.assignments:
            thay.setdefault(a.pin, []).append(a.function)
        return [
            f"Chân {pin} bị gán {len(fn)} chức năng: {', '.join(fn)}"
            for pin, fn in sorted(thay.items())
            if len(fn) > 1
        ]


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Bảng chân chưa được người xác nhận với sơ đồ nguyên lý trong tay.
        """
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self, pin_functions: Any = None) -> str:
        dong = [f"Bảng chân — {len(self.assignments)} chân ({self.source})", ""]
        dong.append(f"  {'chân':<10} {'chức năng':<16} kiểm chức năng thay thế")
        for k in self.check(pin_functions):
            dong.append(k.render())

        xung_dot = self.conflicts()
        if xung_dot:
            dong += ["", "XUNG ĐỘT:"] + [f"  · {c}" for c in xung_dot]

        khong_ho_tro = [k for k in self.check(pin_functions) if k.status == PIN_KHONG_HO_TRO]
        if khong_ho_tro:
            dong += [
                "",
                "Có chân được gán một chức năng nó KHÔNG hỗ trợ. Đây là loại lỗi",
                "chỉ lộ ra sau khi đã hàn — sửa trên giấy rẻ hơn sửa trên bo.",
            ]
        if any(k.status == PIN_KHONG_KIEM_DUOC for k in self.check(pin_functions)):
            dong += [
                "",
                "Phần 'chưa kiểm được' KHÔNG có nghĩa là 'đạt'. Khai",
                "'pin_functions' trong hardware_profile.yaml (trích từ bảng chức",
                "năng thay thế của datasheet) thì engine mới đối chiếu được.",
            ]
        dong += [
            "",
            "Agent KHÔNG tự chốt bảng này. Mỗi chân quan trọng phải được người",
            "xác nhận với sơ đồ nguyên lý trong tay — xem N-014.",
        ]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Người đề xuất — dùng mô hình nền
# --------------------------------------------------------------------------


_LUOC_DO_PHAM_VI = """{
  "goal": "<phát biểu lại mục tiêu bằng một câu>",
  "scope": [
    {
      "feature": "<tính năng>",
      "side": "trong|ngoai",
      "reason": "<vì sao — BẮT BUỘC với mục ngoài phạm vi>",
      "architectural": true
    }
  ]
}"""

_LUOC_DO_RANG_BUOC = """{
  "limits": [
    {
      "key": "<tên khóa, chữ thường và gạch dưới, ví dụ control_loop_ms>",
      "value": <số>,
      "unit": "<đơn vị>",
      "rationale": "<suy ra từ đâu: động lực học đối tượng, hay năng lực chip>",
      "consequence": "<vi phạm thì chuyện gì xảy ra — BẮT BUỘC>"
    }
  ],
  "forbidden": ["<điều cấm về cách viết mã>"]
}"""

_LUOC_DO_NGHIEM_THU = """{
  "measurements": [
    {
      "name": "<tên số đo>",
      "key": "<khóa trong khung telemetry, khi nguồn là telemetry>",
      "unit": "<đơn vị — BẮT BUỘC>",
      "max": <ngưỡng trên, bỏ nếu không có>,
      "min": <ngưỡng dưới, bỏ nếu không có>,
      "method": "<đo BẰNG CÁCH NÀO, cụ thể tới mức người khác lặp lại được>",
      "source": "telemetry|dong_ho_do|quan_sat_nguoi"
    }
  ],
  "scenarios": ["<kịch bản nghiệm thu>"],
  "rejected": [
    {"statement": "<yêu cầu không đo được>", "reason": "<hỏi lại thế nào cho đo được>"}
  ]
}"""

_LUOC_DO_MO_HINH = """{
  "kind": "<loại đối tượng: con lắc ngược, động cơ một chiều, khối nhiệt…>",
  "states": ["<biến trạng thái kèm đơn vị>"],
  "equations": "<phương trình hoặc mô tả động lực học, ngắn gọn>",
  "parameters": [
    {
      "name": "<tên tham số>",
      "value": <trị số>,
      "unit": "<đơn vị — BẮT BUỘC>",
      "source": "da_do|uoc_luong|tu_tai_lieu",
      "how_to_measure": "<đo bằng cách nào — BẮT BUỘC khi source là uoc_luong>"
    }
  ],
  "ignored": ["<hiện tượng mô hình bỏ qua — BẮT BUỘC có ít nhất một>"],
  "validity": "<mô hình chỉ đúng trong dải nào>"
}"""

_LUOC_DO_BANG_CHAN = """{
  "pin_map": [
    {
      "pin": "<tên chân theo cách gọi của MCU>",
      "function": "<chức năng cần: chức năng thay thế hoặc vào-ra thường>",
      "direction": "in|out|inout",
      "peripheral": "<id ngoại vi trong hồ sơ phần cứng>",
      "signal": "<tín hiệu nối tới đâu>",
      "note": "<điều đáng lưu ý>"
    }
  ]
}"""


@dataclass
class LlmProposer:
    """Dựng bốn bản đề xuất của giai đoạn G0/G1 bằng mô hình nền."""

    llm: Any
    budget: int = 3000

    # -- chung -------------------------------------------------------------

    def _goi(self, *, module: str, he_thong: str, viec: str) -> dict[str, Any]:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=he_thong,
            layers=[PromptLayer("task", viec, budget=self.budget, required=True)],
            module=module,
            budget=self.budget + 800,
        )
        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise ProposeError(f"Không dựng được đề xuất {module}: {exc}") from exc

        from eaa.options import boc_json

        return boc_json(van_ban, ProposeError)

    @property
    def _ten_mo_hinh(self) -> str:
        return getattr(self.llm, "model", "") or getattr(self.llm, "provider", "")

    # -- N-006 -------------------------------------------------------------

    def scope(self, *, goal: str, board: Any = None, hardware: Any = None) -> ScopeProposal:
        du_lieu = self._goi(
            module="phạm vi dự án",
            he_thong=(
                "Bạn chốt phạm vi cho một dự án nhúng. Nêu tính năng TRONG phạm "
                "vi, và quan trọng hơn: nêu thứ NGOÀI phạm vi kèm lý do. Lý do "
                "phải bám vào năng lực bo và công sức thật, không bám vào sở "
                "thích. Đánh dấu architectural=true cho thứ mà bỏ đi là một "
                "quyết định kiến trúc, không phải một chi tiết hoãn lại."
            ),
            viec=(
                f"Mục tiêu: {goal}\n"
                + _mo_ta_bo(board, hardware)
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_PHAM_VI}\n```"
            ),
        )
        return ScopeProposal(
            items=tuple(ScopeItem.from_dict(x) for x in (du_lieu.get("scope") or [])),
            goal=str(du_lieu.get("goal", "")) or goal,
            proposed_by=self._ten_mo_hinh,
        )

    # -- N-010 -------------------------------------------------------------

    def constraints(
        self, *, goal: str, plant: str = "", board: Any = None, hardware: Any = None
    ) -> ConstraintProposal:
        du_lieu = self._goi(
            module="ràng buộc cứng",
            he_thong=(
                "Bạn đề xuất ràng buộc cứng cho một dự án nhúng. Mỗi ràng buộc "
                "phải suy ra từ ĐẶC TÍNH VẬT LÝ của đối tượng hoặc từ NĂNG LỰC "
                "của chip, và phải kèm HỆ QUẢ cụ thể nếu vi phạm — người duyệt "
                "cần căn cứ để bác. Không đề xuất con số tròn trịa mà không nói "
                "được nó từ đâu ra."
            ),
            viec=(
                f"Mục tiêu: {goal}\n"
                + (f"Đối tượng điều khiển: {plant}\n" if plant else "")
                + _mo_ta_bo(board, hardware)
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_RANG_BUOC}\n```"
            ),
        )
        return ConstraintProposal(
            items=tuple(ConstraintItem.from_dict(x) for x in (du_lieu.get("limits") or [])),
            forbidden=tuple(str(x) for x in (du_lieu.get("forbidden") or [])),
            proposed_by=self._ten_mo_hinh,
        )

    # -- N-011 -------------------------------------------------------------

    def acceptance(self, *, goal: str, constraints: Any = None) -> AcceptanceProposal:
        du_lieu = self._goi(
            module="tiêu chí nghiệm thu",
            he_thong=(
                "Bạn ép mọi tiêu chí nghiệm thu thành MỘT CON SỐ có ĐƠN VỊ và "
                "một CÁCH ĐO. Từ chối tiêu chí kiểu 'chạy mượt' và đưa nó vào "
                "mục rejected kèm câu hỏi làm nó đo được. Với mỗi số đo, nói rõ "
                "nó lấy từ đâu: kênh telemetry của thiết bị, đồng hồ đo, hay "
                "quan sát của người."
            ),
            viec=(
                f"Mục tiêu: {goal}\n"
                + _mo_ta_rang_buoc(constraints)
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_NGHIEM_THU}\n```"
            ),
        )
        bi_tu_choi = tuple(
            (str(x.get("statement", "")), str(x.get("reason", "")))
            for x in (du_lieu.get("rejected") or [])
            if isinstance(x, dict)
        )
        return AcceptanceProposal(
            criteria=tuple(
                AcceptanceCriterion.from_dict(x) for x in (du_lieu.get("measurements") or [])
            ),
            rejected=bi_tu_choi,
            scenarios=tuple(str(x) for x in (du_lieu.get("scenarios") or [])),
            proposed_by=self._ten_mo_hinh,
        )

    # -- N-060 -------------------------------------------------------------

    def plant_model(
        self, *, plant: str, goal: str = "", hardware: Any = None
    ) -> PlantModelProposal:
        co_khi = (getattr(hardware, "raw", {}) or {}).get("mechanics") or {}
        du_lieu = self._goi(
            module="mô hình đối tượng",
            he_thong=(
                "Bạn dựng mô hình toán cho đối tượng điều khiển của một hệ "
                "nhúng. Nêu biến trạng thái, phương trình, và tham số vật lý "
                "kèm ĐƠN VỊ. Tham số nào chưa ai đo thì đánh dấu 'uoc_luong' và "
                "BẮT BUỘC nói đo bằng cách nào. Cuối cùng, nêu rõ mô hình BỎ "
                "QUA hiện tượng nào — mọi mô hình đều bỏ qua điều gì đó, và "
                "một mô hình tự nhận không bỏ qua gì sẽ được tin quá mức."
            ),
            viec=(
                f"Đối tượng: {plant}\n"
                + (f"Mục tiêu điều khiển: {goal}\n" if goal else "")
                + (
                    "Thông số cơ khí đã khai: "
                    + ", ".join(f"{k}={v}" for k, v in sorted(co_khi.items()))
                    + "\n"
                    if co_khi
                    else ""
                )
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_MO_HINH}\n```"
            ),
        )
        return PlantModelProposal(
            kind=str(du_lieu.get("kind", "")) or plant,
            states=tuple(str(x) for x in (du_lieu.get("states") or [])),
            equations=str(du_lieu.get("equations", "")),
            parameters=tuple(
                PlantParameter.from_dict(x) for x in (du_lieu.get("parameters") or [])
            ),
            ignored=tuple(str(x) for x in (du_lieu.get("ignored") or [])),
            validity=str(du_lieu.get("validity", "")),
            proposed_by=self._ten_mo_hinh,
        )

    # -- N-014 -------------------------------------------------------------

    def pin_map(self, *, hardware: Any, goal: str = "") -> PinMapProposal:
        ngoai_vi = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
        linh_kien = [str(c.get("id", "")) for c in getattr(hardware, "components", [])]
        if not (ngoai_vi or linh_kien):
            raise ProposeError(
                "Hồ sơ phần cứng chưa khai ngoại vi hay linh kiện nào. Bảng chân "
                "bám vào thứ CÓ THẬT trên bo, không vào trí tưởng tượng."
            )

        du_lieu = self._goi(
            module="bảng chân",
            he_thong=(
                "Bạn đề xuất sơ đồ chân cho một bo nhúng. Với mỗi chân, nêu rõ "
                "chức năng cần dùng (tên chức năng thay thế nếu có), hướng, và "
                "ngoại vi nó phục vụ. KHÔNG gán hai chức năng vào cùng một chân. "
                "Chỉ dùng ngoại vi và linh kiện có trong danh sách."
            ),
            viec=(
                (f"Mục tiêu: {goal}\n" if goal else "")
                + f"Ngoại vi: {', '.join(x for x in ngoai_vi if x) or '(không)'}\n"
                + f"Linh kiện: {', '.join(x for x in linh_kien if x) or '(không)'}\n"
                + _mo_ta_chan_da_khai(hardware)
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_BANG_CHAN}\n```"
            ),
        )
        return PinMapProposal(
            assignments=tuple(
                PinAssignment.from_dict(x) for x in (du_lieu.get("pin_map") or [])
            ),
            proposed_by=self._ten_mo_hinh,
        )


# --------------------------------------------------------------------------


def _mo_ta_bo(board: Any, hardware: Any) -> str:
    phan: list[str] = []
    if board is not None:
        phan.append(
            f"Bo: {getattr(board, 'name', '')} · MCU {getattr(board, 'mcu', '')} · "
            f"flash {getattr(board, 'flash_bytes', 0)} B · RAM {getattr(board, 'sram_bytes', 0)} B"
        )
    if hardware is not None:
        mcu = getattr(hardware, "mcu", {}) or {}
        if mcu:
            phan.append(
                "Chip: "
                + ", ".join(f"{k}={v}" for k, v in sorted(mcu.items()) if v)
            )
        ngoai_vi = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
        if any(ngoai_vi):
            phan.append("Ngoại vi: " + ", ".join(x for x in ngoai_vi if x))
    return ("\n".join(phan) + "\n") if phan else ""


def _mo_ta_rang_buoc(constraints: Any) -> str:
    if constraints is None:
        return ""
    gioi_han = getattr(constraints, "limits", {}) or {}
    if not gioi_han:
        return ""
    return "Ràng buộc đã chốt: " + ", ".join(f"{k}={v}" for k, v in sorted(gioi_han.items())) + "\n"


def _mo_ta_chan_da_khai(hardware: Any) -> str:
    bang = getattr(hardware, "pin_functions", None) or {}
    if not bang:
        return (
            "Hồ sơ chưa khai bảng chức năng thay thế của chân, nên đề xuất sẽ "
            "KHÔNG kiểm được chân có hỗ trợ chức năng cần hay không.\n"
        )
    return (
        "Chân và chức năng chân ấy hỗ trợ:\n"
        + "\n".join(f"  {k}: {', '.join(str(x) for x in (v or []))}" for k, v in sorted(bang.items()))
        + "\n"
    )


_DAU_TEP_PHAM_VI = """\
# Phạm vi dự án — BẢN ĐỀ XUẤT do `eaa propose scope` dựng.
#
# Mục đáng đọc kỹ KHÔNG phải danh sách "làm gì" — cái ấy đã có trong phát biểu
# bài toán — mà là danh sách NGOÀI PHẠM VI kèm lý do. Một dự án không có ranh
# giới viết ra là một dự án phình dần, và không lần nào ai thấy được điểm nó
# bắt đầu phình.
#
# Mục `architectural: true` là thứ mà bỏ đi là một quyết định kiến trúc, không
# phải một chi tiết hoãn lại — thêm nó về sau sẽ đụng tới cấu trúc, không chỉ
# đụng tới thời gian.
#
# Đọc từng dòng rồi chốt cùng G1.

"""
