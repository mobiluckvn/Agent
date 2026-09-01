"""Chế độ chẩn đoán phần cứng cộng tác — hai kênh quan sát.

EAA-AIS-05 §7, quy trình P8; FR-DIA-01/02/03; TC-27, TC-28.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-22.

Trả lời câu hỏi vận hành quan trọng nhất sau khi lắp ráp: *"cảm biến có hoạt
động không, động cơ có quay không?"*

**Nguyên tắc hai kênh** (AIS §7.1). Thế giới vật lý chia làm hai phần:

* **Kênh máy đọc được** — mọi thứ đi qua điện và dữ liệu: giá trị cảm biến, mã
  nhận dạng thiết bị, số xung đã phát, chu kỳ ngắt đo được. Firmware chẩn đoán
  stream JSON từng dòng, máy phân tích tự động.
* **Kênh chỉ người quan sát được** — trục có quay thật không, đúng chiều không,
  có rung, nóng, kêu lạ không.

Chẩn đoán chính xác là phép **GIAO** của hai kênh. Máy nói "đã phát 200 xung
bước" mà người nói "trục không quay" thì lỗi nằm ở dây nối hoặc dòng cấp, chứ
không nằm ở mã. Một mình máy không bao giờ kết luận được điều đó; một mình
người cũng mất hàng giờ mò — ghép lại thì ra trong một phiên.

Đó cũng là lý do module này từ chối kết luận khi thiếu một trong hai kênh: một
kết luận dựa trên nửa dữ liệu vẫn phát ra với vẻ chắc chắn y hệt, và nó sẽ dẫn
kỹ sư đi sửa nhầm chỗ.

**Khung kịch bản là TỔNG QUÁT** (thuộc engine); bộ DS-01..06 là dữ liệu của
từng dự án, khai báo trong ``diagnostics.yaml``. Dự án khác, pack khác thì
khai báo bộ kịch bản riêng theo ngoại vi của nó.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "DiagnosticError",
    "SafetyChecklistNotConfirmed",
    "FlashNotConfirmed",
    "Channel",
    "Verdict",
    "MachineCriterion",
    "HumanCheck",
    "ManualMeasurement",
    "FieldCase",
    "ScenarioMatch",
    "TU_KHOA",
    "MO_HINH",
    "TAI_HIEN_DUOC",
    "KHONG_TAI_HIEN",
    "CHUA_THU",
    "Scenario",
    "ScenarioLibrary",
    "MatrixRow",
    "Diagnosis",
    "DiagnosticSession",
]


class Channel:
    MACHINE = "máy"
    HUMAN = "người"
    BOTH = "cả hai"


class Verdict:
    """Vùng lỗi mà phép giao hai kênh chỉ ra."""

    CODE = "code"           # lỗi mã hoặc cấu hình — mở vòng sửa mã
    ELECTRICAL = "điện"     # dây nối, dòng cấp, nguồn — người xử lý
    MECHANICAL = "cơ khí"   # kẹt, trượt, lắp sai — người xử lý
    POWER = "nguồn"         # sụt áp, brown-out
    WIRING = "nối dây"      # đảo chiều, nhầm chân
    OK = "không phát hiện lỗi"
    INCONCLUSIVE = "chưa kết luận được"


class DiagnosticError(Exception):
    """Phiên chẩn đoán không chạy được."""


class SafetyChecklistNotConfirmed(DiagnosticError):
    """Kịch bản có chuyển động mà chưa xác nhận checklist an toàn — TC-28."""


class FlashNotConfirmed(DiagnosticError):
    """Nạp firmware chẩn đoán mà chưa có xác nhận của người — FR-DIA-02."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class MachineCriterion:
    """Một tiêu chí kênh máy: đọc gì từ telemetry và kỳ vọng ra sao."""

    key: str
    description: str
    #: So khớp: ``equals`` · ``one_of`` · ``in_range`` · ``present`` ·
    #: ``min`` · ``max`` · ``contains``.
    op: str = "present"
    expected: Any = None
    low: float | None = None
    high: float | None = None

    def evaluate(self, telemetry: dict[str, Any]) -> tuple[bool, str]:
        if self.key not in telemetry:
            return False, f"telemetry không có trường {self.key!r}"
        gia_tri = telemetry[self.key]

        if self.op == "present":
            return True, f"{self.key}={gia_tri}"
        if self.op == "equals":
            dat = str(gia_tri).lower() == str(self.expected).lower()
            return dat, f"{self.key}={gia_tri}, kỳ vọng {self.expected}"
        if self.op == "one_of":
            # "Thuộc tập chấp nhận được" — KHÁC `equals` nới ra.
            #
            # Có những đại lượng mà nhiều giá trị đều đúng: một linh kiện có
            # bản tương thích, một nhà cung cấp đổi mã giữa hai lô. Sửa
            # `expected` sang giá trị mới thì ĐÁNH MẤT giá trị cũ, và lần sau
            # cắm đúng con chip thiết kế vào thì phép kiểm lại đỏ. Sau vài
            # vòng như thế, nó chỉ còn nhớ thứ cắm gần nhất.
            #
            # Tập mở rộng CÓ CHỦ Ý: mỗi giá trị vào tập là một lần người quyết
            # định, và thứ ngoài tập vẫn bị bắt.
            tap = (
                self.expected if isinstance(self.expected, (list, tuple, set))
                else [self.expected]
            )
            tap = [x for x in tap if x is not None]
            if not tap:
                raise DiagnosticError(
                    f"{self.key}: phép so 'one_of' có tập kỳ vọng RỖNG. Trả đạt "
                    "thì mọi giá trị lọt; trả trượt thì không ai hiểu vì sao. "
                    "Khai đủ tập, hoặc dùng phép so khác."
                )
            dat = any(str(gia_tri).lower() == str(x).lower() for x in tap)
            return dat, (
                f"{self.key}={gia_tri}, chấp nhận "
                + "/".join(str(x) for x in tap)
            )
        if self.op == "contains":
            day = gia_tri if isinstance(gia_tri, (list, tuple)) else [gia_tri]
            dat = any(str(x).lower() == str(self.expected).lower() for x in day)
            return dat, f"{self.key}={gia_tri}, cần có {self.expected}"
        try:
            so = float(gia_tri)
        except (TypeError, ValueError):
            return False, f"{self.key}={gia_tri!r} không phải số"
        if self.op == "min":
            return so >= float(self.low or 0), f"{self.key}={so:g}, sàn {self.low}"
        if self.op == "max":
            return so <= float(self.high or 0), f"{self.key}={so:g}, trần {self.high}"
        if self.op == "in_range":
            dat = float(self.low) <= so <= float(self.high)
            return dat, f"{self.key}={so:g}, dải [{self.low}, {self.high}]"
        raise DiagnosticError(f"Phép so không hiểu được: {self.op!r}")


@dataclass(frozen=True)
class HumanCheck:
    """Một mục checklist quan sát mà chỉ người trả lời được."""

    key: str
    question: str
    #: Câu trả lời "đúng như mong đợi" — thường là True.
    expected: bool = True


@dataclass(frozen=True)
class ManualMeasurement:
    """Một phép đo bằng dụng cụ, do NGƯỜI thực hiện — N-084.

    Kênh thứ ba, bên cạnh kênh máy và kênh quan sát. Nó tồn tại vì có những đại
    lượng không con chip nào tự đo được về chính nó: dòng tiêu thụ tổng, sụt áp
    trên dây, nhiệt độ vỏ linh kiện. Bỏ trống chúng thì phần "kiểm nguồn dưới
    tải" chỉ kiểm được nửa mà mình đo được, và nửa ấy lại là nửa ít nói nhất.

    Bốn trường bắt buộc là bốn câu mà một hướng dẫn đo phải trả lời: **đo cái
    gì, ở đâu, trong điều kiện nào, và chờ đợi con số bao nhiêu**. Thiếu một
    trong bốn thì hai người đo sẽ ra hai kết quả và không ai sai.
    """

    key: str
    quantity: str
    instrument: str
    where: str
    condition: str
    unit: str
    low: float | None = None
    high: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        for ten, gia_tri in (
            ("quantity", self.quantity),
            ("instrument", self.instrument),
            ("where", self.where),
            ("condition", self.condition),
            ("unit", self.unit),
        ):
            if not str(gia_tri).strip():
                raise DiagnosticError(
                    f"Phép đo tay {self.key!r} thiếu {ten!r}. Một hướng dẫn đo "
                    "phải trả lời đủ bốn câu — đo cái gì, ở đâu, trong điều kiện "
                    "nào, chờ đợi bao nhiêu — nếu không thì hai người đo sẽ ra "
                    "hai kết quả và không ai sai."
                )
        if self.low is None and self.high is None:
            raise DiagnosticError(
                f"Phép đo tay {self.key!r} không có ngưỡng nào. Một số đo không "
                "có ngưỡng thì ghi lại được nhưng không kết luận được gì."
            )

    def expected_text(self) -> str:
        if self.low is not None and self.high is not None:
            return f"{self.low:g}–{self.high:g} {self.unit}"
        if self.low is not None:
            return f"≥ {self.low:g} {self.unit}"
        return f"≤ {self.high:g} {self.unit}"

    def evaluate(self, value: float) -> tuple[bool, str]:
        if self.low is not None and value < self.low:
            return False, f"{value:g} {self.unit} dưới sàn {self.low:g}"
        if self.high is not None and value > self.high:
            return False, f"{value:g} {self.unit} vượt trần {self.high:g}"
        return True, f"{value:g} {self.unit} trong khoảng {self.expected_text()}"

    def instructions(self) -> str:
        """Hướng dẫn đo đích danh, đủ để người khác lặp lại được."""
        dong = [f"  [{self.key}] {self.quantity}"]
        dong.append(f"      dụng cụ    : {self.instrument}")
        dong.append(f"      đo ở đâu   : {self.where}")
        dong.append(f"      điều kiện  : {self.condition}")
        dong.append(f"      chờ đợi    : {self.expected_text()}")
        if self.note:
            dong.append(f"      lưu ý      : {self.note}")
        return "\n".join(dong)


@dataclass(frozen=True)
class Scenario:
    """Một kịch bản chẩn đoán — DS-01..06 của dự án."""

    id: str
    title: str
    description: str = ""
    #: Kịch bản có gây chuyển động cơ khí → bắt buộc checklist an toàn (TC-28).
    motion: bool = False
    safety_checklist: tuple[str, ...] = ()
    machine: tuple[MachineCriterion, ...] = ()
    human: tuple[HumanCheck, ...] = ()
    #: Phép đo bằng dụng cụ, do người thực hiện — kênh thứ ba (N-084).
    manual: tuple[ManualMeasurement, ...] = ()
    #: Mẫu firmware đo dùng để sinh; rỗng nghĩa là chưa có.
    firmware_template: str = ""
    #: Triệu chứng gợi tới kịch bản này — dùng để chọn kịch bản từ mô tả người.
    symptoms: tuple[str, ...] = ()
    #: Thời gian thu telemetry cho kịch bản này, giây. 0 = dùng mặc định.
    #:
    #: Cửa sổ thu phải dài hơn thời gian kịch bản CHẠY, cộng phần bootloader
    #: chờ trước khi nhường quyền. Mặc định 5 giây vừa cho kịch bản đo tĩnh và
    #: NGẮN HƠN kịch bản chuyển động — DS-07 quay 4 giây, và với 5 giây thì
    #: lệnh bỏ cuộc trước khi bo kịp phát khung.
    #:
    #: Hỏng theo hướng dễ đọc nhầm nhất: bản in nói *"telemetry không có
    #: trường pulses_emitted"*, nghe như firmware hỏng, trong khi thật ra là
    #: người quan sát bỏ đi sớm (SL-129).
    collect_seconds: float = 0.0

    @property
    def fully_automatic(self) -> bool:
        return not self.human and not self.manual

    @property
    def buildable(self) -> bool:
        """Dựng được firmware đo cho kịch bản này chưa.

        Kịch bản chưa khai phần đo thì DỪNG, không dựng một firmware rỗng
        (N-081): một ảnh nạp được mà chẳng đo gì sẽ chạy trơn tru và trả về
        không có gì, và "không có gì" thì không phân biệt được với "đo xong,
        mọi thứ bình thường".
        """
        return bool(self.firmware_template)


class ScenarioLibrary:
    """Thư viện kịch bản chẩn đoán của một dự án — ``diagnostics.yaml``."""

    def __init__(self, scenarios: Sequence[Scenario], matrix: Sequence["MatrixRow"] = ()) -> None:
        self.scenarios = list(scenarios)
        self.matrix = list(matrix)

    @classmethod
    def load(cls, path: str | Path) -> "ScenarioLibrary":
        path = Path(path)
        if not path.is_file():
            raise DiagnosticError(f"Không tìm thấy thư viện kịch bản chẩn đoán: {path}")
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise DiagnosticError(f"{path}: YAML không hợp lệ — {exc}") from exc

        kich_ban = [cls._parse(s, path) for s in du_lieu.get("scenarios") or []]
        ma_tran = [MatrixRow.from_dict(r) for r in du_lieu.get("matrix") or []]
        return cls(kich_ban, ma_tran)

    @staticmethod
    def _parse(d: Any, path: Path) -> Scenario:
        if not isinstance(d, dict) or not d.get("id"):
            raise DiagnosticError(f"{path}: có kịch bản thiếu 'id'")

        co_chuyen_dong = bool(d.get("motion", False))
        checklist = tuple(str(x) for x in (d.get("safety_checklist") or []))
        if co_chuyen_dong and not checklist:
            raise DiagnosticError(
                f"{path}: kịch bản {d['id']} có chuyển động nhưng không khai báo "
                "checklist an toàn. Kịch bản làm thiết bị chuyển động mà không có "
                "checklist là kịch bản không chạy được (FR-DIA-02)."
            )

        return Scenario(
            id=str(d["id"]),
            title=str(d.get("title", d["id"])),
            description=str(d.get("description", "")),
            motion=co_chuyen_dong,
            safety_checklist=checklist,
            machine=tuple(
                MachineCriterion(
                    key=str(m["key"]),
                    description=str(m.get("description", m["key"])),
                    op=str(m.get("op", "present")),
                    expected=m.get("expected"),
                    low=m.get("low"),
                    high=m.get("high"),
                )
                for m in (d.get("machine") or [])
            ),
            human=tuple(
                HumanCheck(
                    key=str(h["key"]),
                    question=str(h.get("question", h["key"])),
                    expected=bool(h.get("expected", True)),
                )
                for h in (d.get("human") or [])
            ),
            manual=tuple(
                ManualMeasurement(
                    key=str(m["key"]),
                    quantity=str(m.get("quantity", "")),
                    instrument=str(m.get("instrument", "")),
                    where=str(m.get("where", "")),
                    condition=str(m.get("condition", "")),
                    unit=str(m.get("unit", "")),
                    low=m.get("low"),
                    high=m.get("high"),
                    note=str(m.get("note", "")),
                )
                for m in (d.get("manual") or [])
            ),
            firmware_template=str(d.get("firmware_template", "")),
            symptoms=tuple(str(x) for x in (d.get("symptoms") or [])),
            collect_seconds=float(d.get("collect_seconds", 0) or 0),
        )

    def get(self, scenario_id: str) -> Scenario:
        for s in self.scenarios:
            if s.id.lower() == scenario_id.lower():
                return s
        raise DiagnosticError(
            f"Không có kịch bản {scenario_id!r} (đang có: {[s.id for s in self.scenarios]})"
        )

    def select(self, symptom: str) -> list[Scenario]:
        """Chọn kịch bản từ mô tả triệu chứng của người — AIS §7.3 bước 1.

        Trả về TỔ HỢP kịch bản chứ không một cái: "robot không phản ứng khi
        nghiêng" cần cả quét bus lẫn kiểm cảm biến, vì hỏng ở khâu nào cũng cho
        ra cùng một triệu chứng.

        Đây là bậc 1: khớp chuỗi con với danh sách ``symptoms`` dự án đã khai.
        Tất định, rẻ, và **kiểm lại được** — nhìn là biết từ nào đã khớp. Nó
        chỉ trượt khi người dùng gọi tên hiện tượng bằng chữ khác; bậc 2 ở
        :meth:`select_smart` lo phần ấy.
        """
        van_ban = symptom.lower()
        khop = [
            s for s in self.scenarios if any(t.lower() in van_ban for t in s.symptoms)
        ]
        return khop or []

    def select_smart(
        self, symptom: str, llm: Any = None
    ) -> "list[ScenarioMatch]":
        """Bậc 1 khớp từ khóa; trượt thì bậc 2 hỏi mô hình (N-903, AIS §7.3).

        Thứ tự này quan trọng và không đảo được. Bậc 1 cho kết quả **tất định
        và kiểm lại được**: người đọc thấy đúng từ nào đã khớp, và cùng một câu
        hỏi luôn cho cùng một kết quả — điều kiện để thực nghiệm Chương 3 tái
        lập. Hỏi mô hình trước sẽ ném bỏ tính chất ấy để đổi lấy một thứ ta chỉ
        cần khi bậc 1 trượt.

        Kết quả của hai bậc KHÔNG được trộn lẫn: mỗi mục mang theo bậc đã tìm
        ra nó, vì một kịch bản do mô hình đoán là một khẳng định yếu hơn hẳn
        một kịch bản khớp đúng từ dự án đã khai.
        """
        khop = self.select(symptom)
        if khop:
            van_ban = symptom.lower()
            return [
                ScenarioMatch(
                    scenario=s,
                    tier=TU_KHOA,
                    evidence=", ".join(t for t in s.symptoms if t.lower() in van_ban),
                )
                for s in khop
            ]

        if llm is None or not self.scenarios:
            return []
        return self._hoi_mo_hinh(symptom, llm)

    def _hoi_mo_hinh(self, symptom: str, llm: Any) -> "list[ScenarioMatch]":
        from eaa.llm.base import LLMError, Prompt, PromptLayer
        from eaa.options import boc_json

        danh_sach = "\n".join(
            f"- {s.id}: {s.title} — dùng khi: "
            + (", ".join(s.symptoms) or "(chưa khai triệu chứng)")
            for s in self.scenarios
        )
        prompt = Prompt(
            system_instruction=(
                "Bạn chọn kịch bản chẩn đoán phù hợp với triệu chứng người dùng "
                "mô tả. CHỈ chọn trong danh sách được cho; không bịa mã kịch "
                "bản. Không kịch bản nào hợp thì trả danh sách rỗng — đó là một "
                "câu trả lời đúng, và nó nói rằng dự án còn thiếu một kịch bản."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Người dùng mô tả: {symptom}\n\n"
                    f"Kịch bản có sẵn:\n{danh_sach}\n\n"
                    'Trả về ĐÚNG một khối JSON: {"chon": [{"id": "<mã>", '
                    '"vi_sao": "<một câu>"}]}',
                    budget=1500,
                    required=True,
                )
            ],
            module="chọn kịch bản chẩn đoán",
            budget=2300,
        )
        try:
            van_ban = (
                llm.complete(prompt)
                if hasattr(llm, "complete")
                else llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise DiagnosticError(f"Không chọn được kịch bản: {exc}") from exc

        du_lieu = boc_json(van_ban, DiagnosticError)
        ket_qua: list[ScenarioMatch] = []
        for m in du_lieu.get("chon") or []:
            if not isinstance(m, dict):
                continue
            try:
                kb = self.get(str(m.get("id", "")))
            except DiagnosticError:
                # Mô hình bịa mã kịch bản thì bỏ, không tạo ra một mục trỏ vào
                # hư không. Bịa ở đây đặc biệt tệ: người sẽ đi nạp một firmware
                # chẩn đoán không tồn tại.
                continue
            ket_qua.append(
                ScenarioMatch(scenario=kb, tier=MO_HINH, evidence=str(m.get("vi_sao", "")))
            )
        return ket_qua


#: Bậc 1 — khớp chuỗi con với danh sách triệu chứng dự án đã khai. Tất định.
TU_KHOA = "tu-khoa"
#: Bậc 2 — mô hình đoán ý người dùng. Cần người xác nhận trước khi chạy.
MO_HINH = "mo-hinh"


@dataclass(frozen=True)
class ScenarioMatch:
    """Một kịch bản được chọn, kèm BẬC đã tìm ra nó.

    Mang theo bậc chứ không trả về kịch bản trần: một kịch bản khớp đúng từ dự
    án đã khai và một kịch bản mô hình đoán ra là hai khẳng định có sức nặng
    khác hẳn nhau. Trộn chúng vào một danh sách là làm mất đúng điều người đọc
    cần để quyết định có tin hay không.
    """

    scenario: "Scenario"
    tier: str
    evidence: str = ""

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import GIA_DINH, SUY_RA

        return SUY_RA if self.tier == TU_KHOA else GIA_DINH

    def render(self) -> str:
        if self.tier == TU_KHOA:
            return (
                f"  {self.scenario.id} — {self.scenario.title}\n"
                f"      khớp triệu chứng đã khai: {self.evidence}"
            )
        return (
            f"  {self.scenario.id} — {self.scenario.title}\n"
            f"      [mô hình đoán] {self.evidence}\n"
            "      Không khớp từ nào dự án đã khai, nên đây là PHỎNG ĐOÁN về ý "
            "bạn.\n"
            "      Đọc lại mô tả kịch bản trước khi chạy."
        )


#: Sự cố hiện trường có dựng lại được trên bàn không — ba trạng thái.
TAI_HIEN_DUOC = "tai-hien-duoc"
KHONG_TAI_HIEN = "khong-tai-hien"
CHUA_THU = "chua-thu"


@dataclass
class FieldCase:
    """Một sự cố ngoài hiện trường, và đường đi từ triệu chứng tới kết luận — N-102.

    Khác với một phiên chẩn đoán trên bàn ở đúng một điểm, và điểm ấy quyết
    định mọi thứ: **hiện tượng không xảy ra trước mặt ta.** Nên bước đầu không
    phải là đo, mà là DỰNG LẠI ĐIỀU KIỆN — và nếu dựng lại không ra thì kết
    luận trung thực là *chưa kết luận được*, không phải một chẩn đoán nghe hợp
    lý dựa trên nửa dữ kiện.
    """

    symptom: str
    #: Điều kiện lúc sự cố xảy ra: nhiệt độ, tải, thời gian chạy, nguồn cấp…
    conditions: dict[str, Any] = field(default_factory=dict)
    #: Đã gặp bao nhiêu lần. Một lần và hai mươi lần là hai bài toán khác nhau.
    occurrences: int = 1
    reproduced: str = CHUA_THU
    scenarios: tuple[str, ...] = ()
    notes: str = ""
    reported_at: str = field(default_factory=_now)

    def missing_context(self) -> list[str]:
        """Điều kiện nào còn thiếu để dựng lại được cảnh ấy.

        Danh sách cố ý NGẮN và cố định: đây là những thứ mà thiếu chúng thì
        gần như không dựng lại được sự cố nào, chứ không phải mọi thứ có thể
        hỏi. Một bảng hỏi dài sẽ không ai điền.
        """
        can = {
            "uptime": "thiết bị đã chạy bao lâu thì xảy ra",
            "load": "lúc ấy đang tải nặng hay nhẹ",
            "power": "nguồn cấp thế nào (pin yếu? vừa cắm? vừa mất điện?)",
            "environment": "nhiệt độ / độ ẩm / rung khác thường không",
            "recent_change": "trước đó có ai đổi gì không (firmware, dây, linh kiện)",
        }
        return [
            f"{khoa}: {mo_ta}" for khoa, mo_ta in can.items() if khoa not in self.conditions
        ]

    def plan(self, library: "ScenarioLibrary") -> list[Scenario]:
        """Kịch bản nên chạy, chọn từ triệu chứng người mô tả."""
        if self.scenarios:
            return [library.get(x) for x in self.scenarios]
        return library.select(self.symptom)

    def verdict(self) -> str:
        if self.reproduced == TAI_HIEN_DUOC:
            return (
                "TÁI HIỆN ĐƯỢC — chạy kịch bản chẩn đoán trên cảnh vừa dựng lại, "
                "kết luận sẽ có căn cứ như mọi phiên trên bàn."
            )
        if self.reproduced == KHONG_TAI_HIEN:
            return (
                "CHƯA KẾT LUẬN ĐƯỢC — không dựng lại được sự cố trên bàn.\n"
                "    Mọi kết luận lúc này đều dựa trên lời kể, và lời kể về một "
                "hiện tượng không lặp lại là dữ kiện yếu nhất trong chẩn đoán.\n"
                "    Việc cần làm KHÔNG phải đoán nguyên nhân mà là ĐI LẤY THÊM "
                "DỮ KIỆN: nạp firmware có ghi telemetry liên tục rồi trả thiết bị "
                "về hiện trường, và chờ nó xảy ra lần nữa — lần này có số liệu."
            )
        return (
            "CHƯA THỬ DỰNG LẠI — bước đầu tiên của một ca hiện trường không phải "
            "là đo mà là dựng lại điều kiện, vì hiện tượng không xảy ra trước mặt ta."
        )

    def render(self, library: "ScenarioLibrary | None" = None) -> str:
        dong = [f"Ca hiện trường: {self.symptom}", ""]
        dong.append(f"  Đã gặp     : {self.occurrences} lần")
        if self.conditions:
            dong.append("  Điều kiện  :")
            dong += [f"      {k} = {v}" for k, v in sorted(self.conditions.items())]

        thieu = self.missing_context()
        if thieu:
            dong += ["", "  CÒN THIẾU để dựng lại được cảnh ấy:"]
            dong += [f"      ? {t}" for t in thieu]
            dong.append(
                "      Hỏi người ở hiện trường. Không có những mục này thì việc"
            )
            dong.append(
                "      dựng lại chỉ là đoán, và đoán trúng một lần không chứng minh gì."
            )

        if library is not None:
            ke_hoach = self.plan(library)
            dong += ["", "  Kịch bản nên chạy:"]
            dong += [
                f"      {s.id} — {s.title}" for s in ke_hoach
            ] or ["      (không kịch bản nào khớp triệu chứng này)"]
            if not ke_hoach:
                dong.append(
                    "      Triệu chứng chưa có kịch bản nào phủ. Đây cũng là một"
                )
                dong.append(
                    "      dữ kiện: bổ sung một kịch bản sau khi tìm ra nguyên nhân."
                )

        dong += ["", self.verdict()]
        return "\n".join(dong)


@dataclass(frozen=True)
class MatrixRow:
    """Một dòng của ma trận chẩn đoán — AIS §7.4."""

    machine: str        # mô tả tình trạng kênh máy
    human: str          # mô tả tình trạng kênh người
    verdict: str
    action: str
    #: Điều kiện máy đọc được, dạng ``{khóa: kỳ vọng}`` để khớp tự động.
    when_machine: dict[str, Any] = field(default_factory=dict)
    when_human: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MatrixRow":
        return cls(
            machine=str(d.get("machine", "")),
            human=str(d.get("human", "")),
            verdict=str(d.get("verdict", Verdict.INCONCLUSIVE)),
            action=str(d.get("action", "")),
            when_machine=dict(d.get("when_machine") or {}),
            when_human=dict(d.get("when_human") or {}),
        )

    def matches(self, machine_pass: bool, human: dict[str, bool]) -> bool:
        """Dòng này có ứng với tình trạng hai kênh đang quan sát không."""
        if "machine_pass" in self.when_machine:
            if bool(self.when_machine["machine_pass"]) != machine_pass:
                return False
        for khoa, mong_doi in self.when_human.items():
            if khoa not in human or bool(human[khoa]) != bool(mong_doi):
                return False
        return bool(self.when_machine) or bool(self.when_human)


@dataclass
class Diagnosis:
    """Kết luận của một phiên chẩn đoán."""

    scenario: str
    verdict: str
    machine_passed: bool
    machine_evidence: list[str] = field(default_factory=list)
    human_answers: dict[str, bool] = field(default_factory=dict)
    action: str = ""
    at: str = field(default_factory=_now)

    @property
    def opens_repair_loop(self) -> bool:
        """Chỉ lỗi mã mới mở vòng sửa mã.

        Đây là điểm cốt lõi của TC-27: máy báo xung phát đủ mà người báo trục
        không quay thì mã KHÔNG có lỗi, và mở vòng sửa mã ở đó là bắt AI sửa
        một thứ không hỏng — vừa tốn, vừa gần như chắc chắn làm hỏng thứ đang
        đúng.
        """
        return self.verdict == Verdict.CODE

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Chẩn đoán là phép GIAO của hai kênh, nên mức tin cậy của nó do kênh yếu
        hơn quyết định:

        * Đủ cả hai kênh → ĐÃ KIỂM. Có số đo từ mạch và có quan sát của người.
        * Thiếu kênh người → SUY RA. Máy chỉ biết nó đã phát xung, không biết
          trục có quay — kết luận rút ra khi thiếu nửa ấy là một phép bắc cầu.
        * Kênh máy không đạt và cũng không có quan sát người → KHÔNG KIỂM ĐƯỢC.
        """
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC, SUY_RA

        if self.human_answers and self.machine_evidence:
            return DA_KIEM
        if not self.machine_evidence and not self.human_answers:
            return KHONG_KIEM_DUOC
        return SUY_RA

    def render(self) -> str:
        from eaa.confidence import header

        dong = [
            f"── Kết luận chẩn đoán {self.scenario} ──",
            header(self.confidence_level),
            "",
            f"Vùng lỗi: {self.verdict}",
            "",
            f"Kênh máy: {'ĐẠT' if self.machine_passed else 'KHÔNG ĐẠT'}",
        ]
        dong += [f"  • {b}" for b in self.machine_evidence]
        if self.human_answers:
            dong.append("")
            dong.append("Kênh người:")
            dong += [
                f"  • {k}: {'có' if v else 'không'}"
                for k, v in sorted(self.human_answers.items())
            ]
        if self.action:
            dong.append("")
            dong.append(f"Hành động đề xuất: {self.action}")
        if not self.opens_repair_loop and self.verdict not in (Verdict.OK, Verdict.INCONCLUSIVE):
            dong.append("")
            dong.append(
                "KHÔNG mở vòng sửa mã: vùng lỗi nằm ngoài phần mềm. Sửa mã ở đây "
                "là bắt AI sửa một thứ không hỏng."
            )
        return "\n".join(dong)


@dataclass
class DiagnosticSession:
    """Một phiên chẩn đoán — quy trình P8 của AIS §7.3."""

    library: ScenarioLibrary
    #: Bộ nạp firmware; ``None`` nghĩa là chưa nối phần cứng.
    flasher: Any = None
    #: Nơi ghi kết quả — Measurement Records.
    records_path: Path | None = None
    ledger: Any = None

    # ----------------------------------------------------------------------
    # TC-28 — checklist an toàn trước kịch bản có chuyển động
    # ----------------------------------------------------------------------

    def prepare(
        self,
        scenario_id: str,
        *,
        safety_confirmed: Sequence[str] = (),
        flash_confirmed_by: str = "",
    ) -> Scenario:
        """Kiểm điều kiện an toàn TRƯỚC khi nạp và chạy — FR-DIA-02, TC-28.

        Hai cửa, và cửa nào thiếu cũng dừng:

        1. Kịch bản có chuyển động thì MỌI mục checklist an toàn phải được xác
           nhận. Robot chưa kê lên mà cho động cơ quay là làm hỏng thiết bị và
           có thể làm đau người.
        2. Nạp firmware luôn cần người xác nhận, kể cả kịch bản không chuyển
           động — nạp là ghi đè bộ nhớ của một thiết bị đang có firmware khác.
        """
        kich_ban = self.library.get(scenario_id)

        if kich_ban.motion:
            da_xac_nhan = {c.strip().lower() for c in safety_confirmed}
            thieu = [
                muc
                for muc in kich_ban.safety_checklist
                if muc.strip().lower() not in da_xac_nhan
            ]
            if thieu:
                raise SafetyChecklistNotConfirmed(
                    f"Kịch bản {kich_ban.id} làm thiết bị CHUYỂN ĐỘNG. Chưa xác "
                    f"nhận {len(thieu)} mục an toàn:\n"
                    + "\n".join(f"  [ ] {m}" for m in thieu)
                    + "\n\nXác nhận từng mục rồi chạy lại. Kịch bản có chuyển "
                    "động không bao giờ chạy khi checklist còn thiếu (FR-DIA-02)."
                )

        if self.flasher is not None and not flash_confirmed_by:
            raise FlashNotConfirmed(
                f"Nạp firmware chẩn đoán cho {kich_ban.id} cần người xác nhận. "
                "Nạp là ghi đè bộ nhớ của một thiết bị đang có firmware khác — "
                "thao tác này không bao giờ tự động (FR-DIA-02)."
            )

        return kich_ban

    # ----------------------------------------------------------------------
    # Thu hai kênh
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_telemetry(stream: str) -> dict[str, Any]:
        """Đọc telemetry JSON từng dòng do firmware chẩn đoán stream về.

        Dòng hỏng bị BỎ QUA chứ không làm hỏng cả phiên: đường truyền nối tiếp
        thật hay có ký tự rác lúc khởi động, và mất cả phiên đo vì một dòng
        nhiễu là cái giá quá đắt. Số dòng hỏng được đếm và trả về, để nhiều
        dòng rác không âm thầm trôi qua.
        """
        du_lieu: dict[str, Any] = {}
        hong = 0
        for dong in stream.splitlines():
            dong = dong.strip()
            if not dong or not dong.startswith("{"):
                continue
            try:
                muc = json.loads(dong)
            except json.JSONDecodeError:
                hong += 1
                continue
            if isinstance(muc, dict):
                du_lieu.update(muc)
        if hong:
            du_lieu["_malformed_lines"] = hong
        return du_lieu

    def evaluate_machine(
        self, scenario: Scenario, telemetry: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        bang_chung: list[str] = []
        dat = True
        for tieu_chi in scenario.machine:
            ok, mo_ta = tieu_chi.evaluate(telemetry)
            bang_chung.append(f"{'✓' if ok else '✗'} {tieu_chi.description}: {mo_ta}")
            dat = dat and ok
        return dat, bang_chung

    # ----------------------------------------------------------------------
    # TC-27 — giao hai kênh
    # ----------------------------------------------------------------------

    def diagnose(
        self,
        scenario_id: str,
        *,
        telemetry: dict[str, Any] | str,
        human_answers: dict[str, bool] | None = None,
    ) -> Diagnosis:
        """Giao hai kênh và kết luận vùng lỗi — AIS §7.3 bước 5, §7.4.

        Từ chối kết luận khi kịch bản đòi quan sát của người mà chưa có: một
        kết luận dựa trên nửa dữ liệu vẫn phát ra với vẻ chắc chắn y hệt, và nó
        sẽ dẫn kỹ sư đi sửa nhầm chỗ.
        """
        kich_ban = self.library.get(scenario_id)
        so_lieu = (
            self.parse_telemetry(telemetry) if isinstance(telemetry, str) else dict(telemetry)
        )
        tra_loi = dict(human_answers or {})

        dat_may, bang_chung = self.evaluate_machine(kich_ban, so_lieu)

        thieu_nguoi = [h.key for h in kich_ban.human if h.key not in tra_loi]
        if thieu_nguoi:
            return Diagnosis(
                scenario=kich_ban.id,
                verdict=Verdict.INCONCLUSIVE,
                machine_passed=dat_may,
                machine_evidence=bang_chung,
                human_answers=tra_loi,
                action=(
                    "Thiếu quan sát của người cho: "
                    + ", ".join(thieu_nguoi)
                    + ". Chẩn đoán là phép GIAO của hai kênh — với nửa dữ liệu, "
                    "kết luận nào cũng có thể sai mà vẫn nghe chắc chắn."
                ),
            )

        dong_khop = next(
            (r for r in self.library.matrix if r.matches(dat_may, tra_loi)), None
        )
        if dong_khop is not None:
            ket_luan = Diagnosis(
                scenario=kich_ban.id,
                verdict=dong_khop.verdict,
                machine_passed=dat_may,
                machine_evidence=bang_chung,
                human_answers=tra_loi,
                action=dong_khop.action,
            )
        else:
            nguoi_dat = all(
                tra_loi.get(h.key) == h.expected for h in kich_ban.human
            )
            if dat_may and nguoi_dat:
                ket_luan = Diagnosis(
                    scenario=kich_ban.id,
                    verdict=Verdict.OK,
                    machine_passed=True,
                    machine_evidence=bang_chung,
                    human_answers=tra_loi,
                    action="Không phát hiện lỗi trong phạm vi kịch bản này.",
                )
            elif not dat_may:
                ket_luan = Diagnosis(
                    scenario=kich_ban.id,
                    verdict=Verdict.CODE,
                    machine_passed=False,
                    machine_evidence=bang_chung,
                    human_answers=tra_loi,
                    action=(
                        "Kênh máy không đạt — mở vòng sửa mã, đối chiếu tiêu chí "
                        "không đạt với trích đoạn tài liệu tương ứng."
                    ),
                )
            else:
                ket_luan = Diagnosis(
                    scenario=kich_ban.id,
                    verdict=Verdict.INCONCLUSIVE,
                    machine_passed=True,
                    machine_evidence=bang_chung,
                    human_answers=tra_loi,
                    action=(
                        "Kênh máy đạt nhưng quan sát của người không như mong "
                        "đợi, và ma trận chẩn đoán chưa có dòng nào ứng với tổ "
                        "hợp này. Bổ sung một dòng vào ma trận sau khi tìm ra "
                        "nguyên nhân — phiên chẩn đoán cũng là phiên nạp tri thức."
                    ),
                )

        self._ghi_ket_qua(ket_luan)
        return ket_luan

    # ----------------------------------------------------------------------

    def _ghi_ket_qua(self, ket_luan: Diagnosis) -> None:
        """Ghi vào Measurement Records; lỗi thuộc về mã thì ghi thêm Error Ledger.

        AIS §7.3 bước 5: phiên chẩn đoán cũng là phiên nạp tri thức.
        """
        if self.records_path is not None:
            self.records_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.records_path, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "scenario": ket_luan.scenario,
                            "verdict": ket_luan.verdict,
                            "machine_passed": ket_luan.machine_passed,
                            "machine_evidence": ket_luan.machine_evidence,
                            "human_answers": ket_luan.human_answers,
                            "action": ket_luan.action,
                            "at": ket_luan.at,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                f.flush()
                os.fsync(f.fileno())

        if self.ledger is not None and ket_luan.opens_repair_loop:
            self.ledger.add(
                module=f"chẩn đoán {ket_luan.scenario}",
                category="tool_failure",
                description=(
                    f"Kịch bản {ket_luan.scenario} không đạt kênh máy: "
                    + "; ".join(
                        b for b in ket_luan.machine_evidence if b.startswith("✗")
                    )
                ),
                evidence=ket_luan.action,
            )
