"""Phiên gỡ lỗi sâu — Agent dựng kế hoạch và ghi vết; người cầm dụng cụ.

EAA-AIS-05 §7 (chẩn đoán phần cứng); N-085 ở mức tự chủ **T0**.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-86.

Vì sao module này trông nhỏ hơn bạn tưởng
------------------------------------------

N-085 nằm ở mức tự chủ T0, và T0 có một định nghĩa rất cụ thể trong hệ này:
*"Người làm, Agent ghi vết — Agent không làm được việc này. Nó chỉ ghi lại ai
làm, làm lúc nào, kết quả ra sao."*

Nên module này **không** điều khiển mạch nạp, **không** đặt điểm dừng, **không**
chạy phiên gỡ lỗi. Làm những việc ấy đòi một mạch gỡ lỗi cắm vào bo thật và
một trình gỡ lỗi chạy tương tác — hai thứ nằm ngoài phạm vi đề án, và đã ghi
như vậy từ đầu.

Thứ nó làm là ba việc mà T0 đòi, và cả ba đều có giá trị thật:

1. **Dò xem có mạch gỡ lỗi nào đang cắm không**, và nói rõ cần thêm gì.
2. **Dựng kế hoạch phiên** từ kịch bản chẩn đoán đã có: xem biến nào, dừng ở
   đâu, và — quan trọng nhất — *thấy cái gì thì kết luận cái gì*.
3. **Ghi lại** người đã làm gì và thấy gì, để lần sau tra được.

Vì sao bước 2 là phần đáng giá nhất
------------------------------------

Người ta hiếm khi bí ở chỗ "gõ lệnh gì trong gdb". Người ta bí ở chỗ **nhìn
vào đâu**, và nhất là ở chỗ *thấy giá trị này thì suy ra được gì*. Một phiên gỡ
lỗi không có giả thuyết là một phiên đi lang thang: đặt vài điểm dừng, xem vài
biến, rồi kết luận theo thứ tình cờ nhìn thấy.

Kế hoạch ở đây vì thế bắt mỗi bước phải khai trước **hai nhánh**: thấy thế này
thì nghĩ gì, thấy thế kia thì nghĩ gì. Khai trước hai nhánh là cách rẻ nhất để
không tự thuyết phục mình sau khi đã nhìn thấy số.

Cảnh báo đi kèm mọi kế hoạch
-----------------------------

Gỡ lỗi sâu là **dụng cụ đắt tiền cho một câu hỏi rẻ**. Phần lớn lỗi nhúng lộ ra
qua UART và một lần nạp lại, nhanh hơn nhiều lần dựng phiên JTAG. Nên
:meth:`DebugPlan.render` luôn hỏi ngược lại: bạn đã thử hai kênh rẻ hơn chưa?
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "DebugError",
    "Probe",
    "DebugStep",
    "DebugPlan",
    "SessionRecord",
    "SessionLog",
    "detect_probes",
    "build_plan",
    "SESSION_FILE",
    "DAU_HIEU_MACH_GO_LOI",
]

SESSION_FILE = "debug_sessions.jsonl"

#: Dấu hiệu nhận mạch nạp/gỡ lỗi trong mô tả cổng USB.
#:
#: Là DỮ LIỆU, không phải một chuỗi ``if``: danh sách này sẽ dài thêm theo thời
#: gian, và nó phải sửa được mà không đụng vào logic. Cố ý chỉ chứa từ khóa
#: chung của LOẠI dụng cụ, không chứa tên bo hay tên chip nào (FR-PLT-01).
DAU_HIEU_MACH_GO_LOI: dict[str, str] = {
    "debug": "mạch gỡ lỗi",
    "jtag": "giao diện JTAG",
    "swd": "giao diện SWD",
    "probe": "mạch dò",
    "programmer": "mạch nạp",
    "ice": "mạch mô phỏng trong mạch",
    "cmsis-dap": "chuẩn CMSIS-DAP",
    "ftdi": "cầu USB–nối tiếp (có thể dùng làm JTAG)",
}


class DebugError(Exception):
    """Không dựng được kế hoạch hoặc không ghi được phiên."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Probe:
    """Một thiết bị có thể là mạch gỡ lỗi."""

    device: str
    description: str = ""
    matched: str = ""
    reason: str = ""

    @property
    def likely(self) -> bool:
        return bool(self.matched)

    def render(self) -> str:
        dau = "✓" if self.likely else "·"
        dong = f"  {dau} {self.device}"
        if self.description:
            dong += f"   {self.description}"
        if self.reason:
            dong += f"\n      khớp dấu hiệu {self.matched!r} — {self.reason}"
        return dong


def detect_probes(ports: Iterable[Any]) -> list[Probe]:
    """Nhận mạch gỡ lỗi từ danh sách cổng đã dò.

    Nhận danh sách cổng đã dò thay vì tự đi dò: cổng nối tiếp do
    ``eaa/serialport.py`` lo, và hai chỗ cùng dò một thứ là hai chỗ sẽ lệch
    nhau. Ở đây chỉ làm phần NHẬN DẠNG.
    """
    ket: list[Probe] = []
    for p in ports:
        ten = str(getattr(p, "device", "") or getattr(p, "port", "") or p)
        mo_ta = str(getattr(p, "description", "") or "")
        gop = f"{ten} {mo_ta}".lower()
        khop = next((k for k in DAU_HIEU_MACH_GO_LOI if k in gop), "")
        ket.append(Probe(
            device=ten, description=mo_ta, matched=khop,
            reason=DAU_HIEU_MACH_GO_LOI.get(khop, ""),
        ))
    return ket


@dataclass(frozen=True)
class DebugStep:
    """Một bước trong phiên, kèm HAI nhánh kết luận khai trước."""

    action: str
    look_at: str = ""
    if_expected: str = ""
    if_unexpected: str = ""

    def render(self, so: int) -> str:
        dong = [f"  {so}. {self.action}"]
        if self.look_at:
            dong.append(f"      nhìn vào : {self.look_at}")
        if self.if_expected:
            dong.append(f"      nếu đúng như dự đoán → {self.if_expected}")
        if self.if_unexpected:
            dong.append(f"      nếu KHÁC dự đoán     → {self.if_unexpected}")
        return "\n".join(dong)


@dataclass
class DebugPlan:
    """Kế hoạch một phiên gỡ lỗi sâu — để NGƯỜI cầm dụng cụ thi hành."""

    scenario_id: str = ""
    symptom: str = ""
    hypothesis: str = ""
    steps: tuple[DebugStep, ...] = ()
    probes: tuple[Probe, ...] = ()
    cheaper_first: tuple[str, ...] = ()
    missing_tools: tuple[str, ...] = ()

    @property
    def has_probe(self) -> bool:
        return any(p.likely for p in self.probes)

    @property
    def confidence_level(self) -> str:
        """GIẢ ĐỊNH: đây là một kế hoạch, chưa có phép đo nào được thực hiện."""
        from eaa.confidence import GIA_DINH

        return GIA_DINH

    def render(self) -> str:
        from eaa.confidence import header

        dong = ["Kế hoạch phiên gỡ lỗi sâu", "", header(self.confidence_level), ""]
        dong.append(
            "Tôi KHÔNG chạy phiên này. Gỡ lỗi sâu cần một mạch gỡ lỗi cắm vào bo "
            "thật và một trình gỡ lỗi chạy tương tác — bạn cầm dụng cụ, tôi dựng "
            "kế hoạch và ghi lại kết quả (N-085 ở mức tự chủ T0)."
        )
        dong.append("")

        # Hỏi ngược trước khi đưa kế hoạch. Dụng cụ đắt cho một câu hỏi rẻ là
        # cách tốn buổi chiều phổ biến nhất trong nghề này.
        if self.cheaper_first:
            dong += ["TRƯỚC KHI DỰNG PHIÊN — bạn đã thử hai kênh rẻ hơn chưa?"]
            dong += [f"  · {c}" for c in self.cheaper_first]
            dong += ["", "Phần lớn lỗi nhúng lộ ra qua UART và một lần nạp lại, "
                         "nhanh hơn nhiều lần dựng phiên JTAG.", ""]

        if self.symptom:
            dong.append(f"Triệu chứng : {self.symptom}")
        if self.hypothesis:
            dong.append(f"Giả thuyết  : {self.hypothesis}")
        dong.append("")

        dong.append("── Dụng cụ")
        if self.probes:
            dong += [p.render() for p in self.probes]
            if not self.has_probe:
                dong.append("      Không cổng nào trông giống mạch gỡ lỗi.")
        else:
            dong.append("  (không dò thấy cổng nào)")
        if self.missing_tools:
            dong.append(f"  ✗ chưa có trên máy: {', '.join(self.missing_tools)}")
        dong.append("")

        dong.append("── Các bước — MỖI bước khai trước hai nhánh kết luận")
        if self.steps:
            dong += [s.render(i) for i, s in enumerate(self.steps, 1)]
        else:
            dong.append("  (kịch bản chưa khai bước nào — xem 'eaa diagnose list')")
        dong += [
            "",
            "Khai trước hai nhánh là cách rẻ nhất để không tự thuyết phục mình "
            "sau khi đã nhìn thấy số. Một phiên không có giả thuyết là một phiên "
            "đi lang thang.",
            "",
            "Làm xong thì ghi lại:  eaa debug record --note '<thấy gì, kết luận gì>'",
        ]
        return "\n".join(dong)


def build_plan(
    *,
    scenario: Any = None,
    ports: Iterable[Any] = (),
    which: Callable[[str], str | None] | None = None,
    tools: Sequence[str] = (),
) -> DebugPlan:
    """Dựng kế hoạch từ một kịch bản chẩn đoán đã có.

    Không tự nghĩ ra bước nào: kịch bản chẩn đoán là tri thức đã qua gate của
    dự án, còn module này chỉ dịch nó sang dạng một phiên gỡ lỗi. Tự bịa bước
    là đưa vào một giả thuyết không ai duyệt.

    ``tools`` mặc định RỖNG, và đó là một ràng buộc kiến trúc chứ không phải
    một chỗ chưa điền: tên trình gỡ lỗi là đặc thù họ MCU, nên nó thuộc về
    Platform Pack (``debug_tools`` trong ``pack.yaml``), không thuộc về engine
    (FR-PLT-01). Engine ở đây chỉ biết "có một danh sách công cụ cần kiểm".
    """
    import shutil

    tim = which or shutil.which
    thieu = tuple(t for t in tools if not tim(t))

    # Các bước rút ra TỪ TIÊU CHÍ của kịch bản, không tự nghĩ.
    #
    # Kịch bản chẩn đoán đã khai sẵn thứ quan trọng nhất: đại lượng nào cần
    # nhìn và khoảng nào là đúng. Một phiên gỡ lỗi rốt cuộc chỉ là cách nhìn
    # những đại lượng ấy từ bên trong chip thay vì qua nhật ký — nên bước của
    # phiên chính là tiêu chí của kịch bản, dịch sang chỗ đặt điểm dừng.
    buoc: list[DebugStep] = []
    for c in getattr(scenario, "machine", ()) or ():
        mong_doi = _mo_ta_khoang(c)
        buoc.append(DebugStep(
            action=f"Dừng ở chỗ {c.key!r} được tính xong, rồi đọc giá trị của nó",
            look_at=f"{c.key} — {c.description}" if c.description else c.key,
            if_expected=(f"{mong_doi} → đại lượng này đúng; loại nó khỏi diện nghi "
                         "và chuyển sang tiêu chí kế tiếp"),
            if_unexpected=("khác thế → đi ngược lên: giá trị này được tính từ đâu, "
                           "và đầu vào của phép tính ấy có đúng không"),
        ))
    for h in getattr(scenario, "human", ()) or ():
        buoc.append(DebugStep(
            action=f"Đối chiếu với quan sát của mắt: {h.question}",
            look_at="thiết bị thật, không phải biến trong chip",
            if_expected="hai kênh khớp nhau → kết luận đứng vững",
            if_unexpected=("hai kênh nói khác nhau → đây mới là manh mối thật; "
                           "chip đang tin một điều mà thiết bị không làm"),
        ))

    re_hon: list[str] = []
    if scenario is not None:
        if getattr(scenario, "firmware_template", ""):
            re_hon.append(
                f"Chạy firmware đo của chính kịch bản này: eaa diagnose measure "
                f"{getattr(scenario, 'id', '')}"
            )
        if getattr(scenario, "manual", None):
            re_hon.append("Đo bằng dụng cụ tay theo hướng dẫn của kịch bản (kênh thứ hai)")
    re_hon.append("Xem lại nhật ký UART quanh lúc lỗi xảy ra")

    trieu_chung = ", ".join(getattr(scenario, "symptoms", ()) or ())
    return DebugPlan(
        scenario_id=str(getattr(scenario, "id", "")),
        symptom=trieu_chung or str(getattr(scenario, "title", "")),
        hypothesis=str(getattr(scenario, "description", "")),
        steps=tuple(buoc),
        probes=tuple(detect_probes(ports)),
        cheaper_first=tuple(re_hon),
        missing_tools=thieu,
    )


def _mo_ta_khoang(c: Any) -> str:
    """Diễn đạt khoảng đúng của một tiêu chí bằng lời."""
    thap, cao = getattr(c, "low", None), getattr(c, "high", None)
    if thap is not None and cao is not None:
        return f"nằm trong [{thap}, {cao}]"
    if thap is not None:
        return f"không nhỏ hơn {thap}"
    if cao is not None:
        return f"không lớn hơn {cao}"
    mong = getattr(c, "expected", None)
    if mong is not None:
        return f"bằng {mong!r}"
    return "có mặt và đọc được"


# --------------------------------------------------------------------------
# Ghi vết — phần T0 đòi
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionRecord:
    """Một phiên đã diễn ra: AI làm, LÚC NÀO, KẾT QUẢ ra sao."""

    scenario_id: str
    actor: str
    note: str
    outcome: str = ""
    tool: str = ""
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"scenario_id": self.scenario_id, "actor": self.actor, "note": self.note,
                "outcome": self.outcome, "tool": self.tool, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionRecord":
        return cls(
            scenario_id=str(d.get("scenario_id", "")),
            actor=str(d.get("actor", "")),
            note=str(d.get("note", "")),
            outcome=str(d.get("outcome", "")),
            tool=str(d.get("tool", "")),
            at=str(d.get("at", "")),
        )

    @property
    def confidence_level(self) -> str:
        """ĐÃ KIỂM: đây là ghi chép về một việc đã thật sự xảy ra."""
        from eaa.confidence import DA_KIEM

        return DA_KIEM

    def render(self) -> str:
        dong = [f"  · {self.at} — {self.actor}"
                + (f" (kịch bản {self.scenario_id})" if self.scenario_id else "")
                + (f" · {self.tool}" if self.tool else "")]
        dong.append(f"      {self.note}")
        if self.outcome:
            dong.append(f"      kết luận: {self.outcome}")
        return "\n".join(dong)


@dataclass
class SessionLog:
    """Nhật ký phiên gỡ lỗi — append-only, ở trong dự án."""

    root: Path
    filename: str = SESSION_FILE

    @property
    def path(self) -> Path:
        return self.root / self.filename

    def record(
        self, *, actor: str, note: str, scenario_id: str = "",
        outcome: str = "", tool: str = "",
    ) -> SessionRecord:
        if not actor.strip():
            raise DebugError(
                "Phải ghi AI làm. Ở mức tự chủ T0, 'ai làm' chính là phần thông "
                "tin duy nhất mà máy không tự biết được."
            )
        if not note.strip():
            raise DebugError("Phải ghi thấy gì — một phiên không ghi lại thì như chưa làm")

        ban = SessionRecord(
            scenario_id=scenario_id.strip(), actor=actor.strip(),
            note=note.strip(), outcome=outcome.strip(), tool=tool.strip(), at=_now(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ban.to_dict(), ensure_ascii=False) + "\n")
        return ban

    def all(self) -> list[SessionRecord]:
        if not self.path.is_file():
            return []
        ds: list[SessionRecord] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                ds.append(SessionRecord.from_dict(json.loads(dong)))
            except json.JSONDecodeError:
                continue
        return ds

    def render(self) -> str:
        from eaa.confidence import DA_KIEM, header

        ds = self.all()
        dong = ["Nhật ký phiên gỡ lỗi sâu", "", header(DA_KIEM), ""]
        if not ds:
            dong += [
                "  (chưa có phiên nào)",
                "",
                "  Dựng kế hoạch trước khi làm:  eaa debug plan --scenario DS-0x",
            ]
            return "\n".join(dong)
        dong += [r.render() for r in ds]
        dong += ["", f"{len(ds)} phiên đã ghi."]
        return "\n".join(dong)
