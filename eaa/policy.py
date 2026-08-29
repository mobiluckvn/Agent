"""Policy Engine — bảng phân quyền và luật chuyển pha.

EAA-SAD-02 §3 ("Bảng phân quyền AUTO/APPROVE/HUMAN dịch từ Ma trận Người–AI"),
EAA-SDD-03 §4 (``level(task) -> AUTO|APPROVE|HUMAN``), FR-ORC-01, ADR-04.

Module này là nơi DUY NHẤT phát biểu hai luật:

1.  **Ai được quyết** ở từng công đoạn — dịch từ Ma trận Người–AI (6 giai đoạn,
    13 công đoạn A1..F1). Tỷ trọng Người/AI trong ma trận không phải số trang
    trí: nó quy ra mức phân quyền, và mức phân quyền quy ra việc Orchestrator
    có được tự chạy tiếp hay phải dừng chờ người.
2.  **Được đi từ pha nào sang pha nào, với chữ ký của gate nào** — máy trạng
    thái 6 giai đoạn ở SAD Hình 2.

Orchestrator (Sprint 2) TRA CỨU luật ở đây chứ không tự phát biểu luật riêng.
Đó là điều kiện để câu "không tồn tại đường vòng nào vượt gate" (NFR-01) kiểm
chứng được bằng test thay vì bằng lời hứa: chỉ có một chỗ để đọc, và chỗ đó
có TC-08 canh.

Ghi chú sai lệch có chủ đích so với EAA-SDD-03 §4: SDD xếp ``advance_phase()``
vào ``orchestrator.py``. Ở đây chỉ đặt BẢNG LUẬT và hàm kiểm tra thuần túy
(``check_transition``) — bản thân hành vi chuyển pha, ghi state và gọi gate
vẫn thuộc Orchestrator. Tách như vậy vì Sprint 0 chưa có Orchestrator nhưng
TC-08 đã phải xanh (MDD §6), và vì luật thuần túy thì test được mà không cần
dựng cả một dự án giả.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Level",
    "Stage",
    "STAGES",
    "PHASE_ORDER",
    "PHASE_NAMES",
    "PHASE_LEVEL",
    "GATE_ORDER",
    "GATE_PURPOSE",
    "PolicyViolation",
    "PhaseSkip",
    "GateNotApproved",
    "level",
    "stage",
    "stages_of_phase",
    "gate_for_transition",
    "check_transition",
    "can_transition",
]


class Level(Enum):
    """Mức phân quyền của một công đoạn.

    * ``AUTO``    — máy tự chạy; người xem kết quả sau.
    * ``APPROVE`` — máy làm, nhưng phải có người bấm duyệt mới đi tiếp.
    * ``HUMAN``   — người chủ trì; máy chỉ hỗ trợ, không được tự quyết.
    """

    AUTO = "AUTO"
    APPROVE = "APPROVE"
    HUMAN = "HUMAN"

    def __str__(self) -> str:  # pragma: no cover - tiện in ra CLI
        return self.value


@dataclass(frozen=True)
class Stage:
    """Một công đoạn trong Ma trận Người–AI."""

    code: str
    phase: str
    name: str
    level: Level
    human_share: int
    ai_share: int
    description: str


# Sáu giai đoạn — SAD §4.1, Hình 2.
PHASE_ORDER: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")

PHASE_NAMES: dict[str, str] = {
    "A": "Phân tích yêu cầu & mô hình hóa",
    "B": "Thiết kế kiến trúc",
    "C": "Mô phỏng & kiểm chứng thiết kế",
    "D": "Phát triển firmware",
    "E": "Kiểm thử & tinh chỉnh",
    "F": "Đánh giá & đúc kết",
}

#: Mức phân quyền ở cấp giai đoạn — nhãn trong SAD Hình 2.
PHASE_LEVEL: dict[str, Level] = {
    "A": Level.HUMAN,
    "B": Level.HUMAN,
    "C": Level.APPROVE,
    "D": Level.AUTO,
    "E": Level.HUMAN,
    "F": Level.HUMAN,
}

GATE_ORDER: tuple[str, ...] = ("G1", "G2", "G3", "G4", "G5")

GATE_PURPOSE: dict[str, str] = {
    "G1": "chốt ràng buộc cứng & kiến trúc",
    # Trích đoạn tài liệu và công cụ đều là tri thức trong hệ thống này: AIS
    # §9.1 nói Tool Manifest cũng là một kho tri thức và mọi thay đổi của nó
    # phải qua gate. Nên G2 duyệt cả hai, không riêng tài liệu.
    "G2": "duyệt trích đoạn tài liệu và công cụ vào kho tri thức",
    "G3": "review diff từng module trước khi merge",
    "G4": "nghiệm thu trên thiết bị thật",
    "G5": "duyệt kết luận",
}

# 13 công đoạn A1..F1. Tên và mô tả được viết lại ở dạng TỔNG QUÁT: bản gốc
# trong Excel nêu đích danh linh kiện và thanh ghi của dự án mẫu, thứ không
# được phép xuất hiện trong engine (FR-PLT-01).
STAGES: dict[str, Stage] = {
    stage_.code: stage_
    for stage_ in (
        Stage(
            code="A1",
            phase="A",
            name="Phân tích yêu cầu chức năng & phi chức năng",
            level=Level.HUMAN,
            human_share=80,
            ai_share=20,
            description=(
                "Người khảo sát bài toán vật lý và chốt bộ ràng buộc cứng "
                "(chu kỳ điều khiển, đáp ứng cơ cấu chấp hành, trần bộ nhớ, "
                "kiểu số học). Máy tổng hợp tài liệu và gợi ý checklist."
            ),
        ),
        Stage(
            code="A2",
            phase="A",
            name="Mô hình hóa toán học",
            level=Level.HUMAN,
            human_share=70,
            ai_share=30,
            description=(
                "Người chọn mô hình động lực học, đặt giả thiết đơn giản hóa và "
                "kiểm chứng phương trình. Máy hỗ trợ biến đổi, rời rạc hóa, "
                "kiểm tra thứ nguyên."
            ),
        ),
        Stage(
            code="B1",
            phase="B",
            name="Thiết kế kiến trúc phần mềm nhúng",
            level=Level.HUMAN,
            human_share=80,
            ai_share=20,
            description=(
                "Người quyết định phân tầng thời gian thực và ngân sách thời "
                "gian cho từng tầng. Máy đề xuất thực hành tốt và dựng khung "
                "minh họa."
            ),
        ),
        Stage(
            code="B2",
            phase="B",
            name="Thiết kế phần cứng & sơ đồ kết nối",
            level=Level.HUMAN,
            human_share=90,
            ai_share=10,
            description=(
                "Người chọn linh kiện, vẽ sơ đồ nguyên lý, quy hoạch chân và "
                "thiết kế cấp nguồn. Đây là công đoạn máy mù ngữ cảnh vật lý "
                "nhất: nhiễu, sụt áp và rung cơ khí không hiện ra trong văn bản."
            ),
        ),
        Stage(
            code="C1",
            phase="C",
            name="Xây bộ mô phỏng động lực học (model-in-the-loop)",
            level=Level.APPROVE,
            human_share=50,
            ai_share=50,
            description=(
                "Máy sinh mã mô phỏng từ phương trình và quét hàng loạt tham số. "
                "Người đặt giả thiết vật lý và kiểm chứng bộ mô phỏng bằng "
                "nghiệm giải tích trước khi cho phép dùng nó làm cổng chặn."
            ),
        ),
        Stage(
            code="C2",
            phase="C",
            name="Chạy chính mã firmware trên mô phỏng (software-in-the-loop)",
            level=Level.APPROVE,
            human_share=50,
            ai_share=50,
            description=(
                "Máy sinh lớp trừu tượng phần cứng giả lập để biên dịch mã thật "
                "trên máy tính. Người vạch ranh giới: cái gì tin được từ mô "
                "phỏng, cái gì bắt buộc đo trên thiết bị thật."
            ),
        ),
        Stage(
            code="D1",
            phase="D",
            name="Khởi tạo khung dự án",
            level=Level.AUTO,
            human_share=20,
            ai_share=80,
            description=(
                "Máy sinh cấu trúc thư mục, tệp tiêu đề, cấu trúc dữ liệu và "
                "giao diện giữa các tầng theo lệnh người."
            ),
        ),
        Stage(
            code="D2",
            phase="D",
            name="Driver ngoại vi và lớp trừu tượng phần cứng",
            level=Level.AUTO,
            human_share=30,
            ai_share=70,
            description=(
                "Máy viết mã thao tác thanh ghi từ trích đoạn tài liệu được nạp "
                "vào ngữ cảnh. Người trích đúng đoạn, đối chiếu từng bit và bắt "
                "ảo giác phần cứng."
            ),
        ),
        Stage(
            code="D3",
            phase="D",
            name="Hiện thực nhân điều phối tác vụ",
            level=Level.AUTO,
            human_share=40,
            ai_share=60,
            description=(
                "Máy sinh bộ điều phối và cấu trúc điều khiển tác vụ tiết kiệm "
                "bộ nhớ. Người thiết kế cơ chế truy cập nguyên tử và rà tranh "
                "chấp giữa ngắt và vòng lặp chính."
            ),
        ),
        Stage(
            code="D4",
            phase="D",
            name="Thuật toán điều khiển & xử lý tín hiệu",
            level=Level.AUTO,
            human_share=40,
            ai_share=60,
            description=(
                "Máy chuyển công thức sang mã số nguyên tối ưu. Người chọn cấu "
                "trúc bộ điều khiển, dải tham số và logic dừng khẩn cấp."
            ),
        ),
        Stage(
            code="E1",
            phase="E",
            name="Kiểm thử đơn vị & phân tích tĩnh",
            level=Level.AUTO,
            human_share=30,
            ai_share=70,
            description=(
                "Máy sinh kịch bản kiểm thử và chạy rà soát mã tĩnh. Người định "
                "nghĩa tiêu chí đạt và phân loại mức nghiêm trọng của cảnh báo."
            ),
        ),
        Stage(
            code="E2",
            phase="E",
            name="Kiểm thử trên thiết bị thật & tinh chỉnh tham số",
            level=Level.HUMAN,
            human_share=80,
            ai_share=20,
            description=(
                "Người nạp firmware, đo bằng thiết bị, quan sát rung và nhiệt, "
                "tinh chỉnh bằng cảm nhận vật lý. Máy phân tích nhật ký đo và "
                "gợi ý hướng chỉnh từ triệu chứng người mô tả."
            ),
        ),
        Stage(
            code="F1",
            phase="F",
            name="So sánh đối chứng và đúc kết quy trình",
            level=Level.HUMAN,
            human_share=70,
            ai_share=30,
            description=(
                "Người thiết kế thực nghiệm đối chứng, diễn giải kết quả và rút "
                "kết luận khoa học. Máy hỗ trợ tổng hợp số liệu và dựng bảng."
            ),
        ),
    )
}

#: Cung chuyển pha hợp lệ → gate bắt buộc trên cung đó (``None`` = không gate).
#: Đích ``None`` nghĩa là kết thúc dự án. Bảng này chính là SAD Hình 2 viết
#: thành dữ liệu; mọi cung KHÔNG có trong bảng đều bị cấm.
_TRANSITIONS: dict[tuple[str, str | None], str | None] = {
    ("A", "B"): "G1",
    ("B", "C"): None,
    ("C", "D"): "G2",
    ("D", "E"): "G3",
    ("E", "F"): "G4",
    ("F", None): "G5",
    # Vòng phản hồi: kiểm thử vật lý không đạt thì quay lại chỉnh thuật
    # toán/tham số (SAD §4.1). Vòng này luôn đi qua con người vì chỉ con người
    # quan sát được thiết bị thật — nên nó không phải một lối tắt.
    ("E", "D"): None,
}


class PolicyViolation(Exception):
    """Hành vi bị luật điều phối từ chối."""


class PhaseSkip(PolicyViolation):
    """Cố chuyển sang một pha không kề — ví dụ A→D."""


class GateNotApproved(PolicyViolation):
    """Cung chuyển pha hợp lệ nhưng gate trên cung đó chưa có chữ ký người."""


# --------------------------------------------------------------------------
# Tra cứu phân quyền
# --------------------------------------------------------------------------


def stage(code: str) -> Stage:
    """Tra một công đoạn theo mã A1..F1."""
    try:
        return STAGES[code.upper()]
    except KeyError:
        raise KeyError(
            f"Không có công đoạn {code!r} trong Ma trận Người–AI "
            f"(hợp lệ: {sorted(STAGES)})"
        ) from None


def stages_of_phase(phase: str) -> list[Stage]:
    return [s for s in STAGES.values() if s.phase == phase.upper()]


def level(task: str) -> Level:
    """Mức phân quyền của một công đoạn (``"D2"``) hoặc cả một pha (``"D"``)."""
    key = task.upper()
    if key in PHASE_LEVEL:
        return PHASE_LEVEL[key]
    return stage(key).level


# --------------------------------------------------------------------------
# Luật chuyển pha
# --------------------------------------------------------------------------


def _validate_phase(phase: str | None, nhan: str) -> None:
    if phase is None:
        return
    if phase not in PHASE_ORDER:
        raise PolicyViolation(
            f"{nhan} không hợp lệ: {phase!r} (hợp lệ: {list(PHASE_ORDER)})"
        )


def gate_for_transition(current: str, target: str | None) -> str | None:
    """Gate bắt buộc trên cung ``current → target``.

    Ném ``PhaseSkip`` nếu cung đó không tồn tại trong máy trạng thái.
    """
    _validate_phase(current, "Pha hiện tại")
    _validate_phase(target, "Pha đích")

    try:
        return _TRANSITIONS[(current, target)]
    except KeyError:
        raise PhaseSkip(
            f"Không có cung chuyển pha {current} → {target}: máy trạng thái đi "
            f"tuần tự {' → '.join(PHASE_ORDER)} (chỉ có một vòng lùi E → D để "
            "tinh chỉnh). Không được nhảy cóc pha kể cả khi mọi gate đã duyệt."
        ) from None


def check_transition(
    current: str, target: str | None, gates: dict[str, str]
) -> None:
    """Kiểm tra một lần chuyển pha; im lặng nghĩa là được phép.

    Hai điều kiện độc lập, phải thỏa CẢ HAI (FR-ORC-01):

    * cung ``current → target`` có trong máy trạng thái;
    * gate trên cung đó ở trạng thái ``approved``.

    Gate vắng mặt trong ``gates`` được coi là ``pending``. Đây là chi tiết an
    toàn chứ không phải chi tiết cài đặt: một state bị cắt xén hay một dự án
    mới tinh không được vô tình mở đường đi tiếp.
    """
    gate = gate_for_transition(current, target)
    if gate is None:
        return

    trang_thai = gates.get(gate, "pending")
    if trang_thai != "approved":
        dich = target if target is not None else "kết thúc"
        raise GateNotApproved(
            f"Gate {gate} ({GATE_PURPOSE[gate]}) đang ở trạng thái "
            f"{trang_thai!r} — chưa thể chuyển {current} → {dich}. "
            f"Chạy 'eaa gate show' rồi 'eaa gate approve {gate}'."
        )


def can_transition(current: str, target: str | None, gates: dict[str, str]) -> bool:
    """Dạng boolean của :func:`check_transition`, tiện cho hiển thị CLI."""
    try:
        check_transition(current, target, gates)
    except PolicyViolation:
        return False
    return True
