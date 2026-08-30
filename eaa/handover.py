"""Bàn giao và vận hành — N-094, N-101, N-103.

EAA-AIS-05 §8.5 (kho phẩm xuất), FR-DOC-01; công đoạn G9 và G10.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-56.

Ba việc của giai đoạn cuối, và cả ba đều là việc viết ra thứ đã biết
--------------------------------------------------------------------

* **Tài liệu vận hành (N-094)** — nạp thế nào, đo thế nào, chẩn đoán thế nào,
  và **hệ thống KHÔNG làm được gì**. Toàn bộ nội dung đã nằm rải rác trong dự
  án: bảng chân ở hồ sơ phần cứng, kịch bản chẩn đoán ở `diagnostics.yaml`,
  giả định chưa kiểm ở Assumption Log. Việc ở đây là GOM lại, không phải nghĩ
  ra — nên nó sinh được, và nên sinh chứ đừng chép tay.

* **Đổi linh kiện (N-101)** — so hai linh kiện rồi chỉ đích danh mã nào bị
  chạm. Đây là phép bắc cầu trên đồ thị tri thức, thứ đã có sẵn từ Sprint 1.

* **Cập nhật thiết bị đã triển khai (N-103)** — có đường lui, và **thử trên một
  thiết bị trước**. Không có hai điều ấy thì một bản vá hỏng nhân lên bằng số
  thiết bị ngoài hiện trường.

Điều mà mục "KHÔNG làm được" phục vụ
-------------------------------------

Một tài liệu bàn giao chỉ nói hệ thống làm được gì là một tài liệu đặt bẫy cho
người tiếp nhận: họ sẽ giả định phần còn lại cũng chạy, và giả định ấy vỡ ra
vào lúc tệ nhất. Nên `OperationsHandbook` bắt buộc có mục giới hạn, và mục ấy
được dựng từ dữ liệu thật — giả định chưa kiểm, kịch bản chưa có phần đo, số
đo chưa lấy — chứ không từ một đoạn văn khiêm tốn viết cho có.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "HandoverError",
    "OperationsHandbook",
    "ComponentDelta",
    "SwapImpact",
    "SwapAnalysis",
    "RolloutStage",
    "RolloutPlan",
    "LlmSwapAnalyst",
    "ROLLOUT_FILE",
]

#: Kế hoạch triển khai ở tầng dự án.
ROLLOUT_FILE = "rollout.yaml"


class HandoverError(Exception):
    """Không dựng được hồ sơ bàn giao."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# N-094 — tài liệu vận hành
# --------------------------------------------------------------------------


@dataclass
class OperationsHandbook:
    """Tài liệu vận hành, sinh từ dữ liệu dự án chứ không chép tay."""

    project: str
    hardware: Any = None
    constraints: Any = None
    scenarios: Sequence[Any] = ()
    safety: Any = None
    errata: Any = None
    flash_log: Any = None
    generated_at: str = field(default_factory=_now)

    # -- phần "KHÔNG làm được" ---------------------------------------------

    def limitations(self) -> list[str]:
        """Điều hệ thống KHÔNG làm được, dựng từ dữ liệu thật.

        Bốn nguồn, và cả bốn đều là chỗ dự án tự biết mình còn hở:
        giả định chưa kiểm, kịch bản chưa có phần đo, tiêu chí chưa có số đo,
        và errata chưa tra.
        """
        gioi_han: list[str] = []

        gia_dinh = (getattr(self.hardware, "raw", {}) or {}).get("assumptions") or []
        chua_kiem = [
            a for a in gia_dinh
            if isinstance(a, dict) and str(a.get("status", "")) != "verified"
        ]
        for a in chua_kiem:
            gioi_han.append(
                f"Giả định CHƯA KIỂM: {a.get('statement', a.get('id', '?'))}"
                + (f" (kiểm bằng: {a['how_to_verify']})" if a.get("how_to_verify") else "")
            )

        chua_do = [
            s for s in self.scenarios if not getattr(s, "firmware_template", "")
        ]
        for s in chua_do:
            gioi_han.append(
                f"Kịch bản chẩn đoán {getattr(s, 'id', '?')} chưa có phần đo — "
                "chạy được lệnh nhưng không thu được số liệu nào."
            )

        can_do_tay = [
            (getattr(s, "id", "?"), m)
            for s in self.scenarios
            for m in getattr(s, "manual", ())
        ]
        for ma, m in can_do_tay:
            gioi_han.append(
                f"{ma}: {getattr(m, 'quantity', '?')} phải ĐO BẰNG DỤNG CỤ — "
                "thiết bị không tự báo được đại lượng này."
            )

        if self.errata is not None and not getattr(self.errata, "looked_up", False):
            gioi_han.append(
                "Chưa tra errata của chip. Mã đúng theo datasheet vẫn có thể chạy "
                "sai nếu chip có lỗi đã công bố, và không cổng kiểm chứng nào bắt "
                "được điều đó."
            )

        ho_hong = (
            [m for m in getattr(self.safety, "modes", ()) if not getattr(m, "detectable", True)]
            if self.safety is not None
            else []
        )
        for m in ho_hong:
            gioi_han.append(
                f"Kiểu hỏng {getattr(m, 'id', '?')!r} KHÔNG phát hiện được bằng "
                "firmware — nó sẽ chỉ lộ ra qua quan sát của người."
            )

        return gioi_han

    # -- dựng tài liệu -----------------------------------------------------

    def render(self) -> str:
        dong: list[str] = [
            f"# Tài liệu vận hành — {self.project}",
            "",
            f"Sinh tự động từ dữ liệu dự án lúc {self.generated_at} bằng `eaa handover doc`.",
            "Mọi con số ở đây đến từ tệp cấu hình và nhật ký của chính dự án, không",
            "chép tay — nên sửa dự án rồi sinh lại là tài liệu đúng trở lại.",
            "",
        ]

        dong += self._phan_nap()
        dong += self._phan_do()
        dong += self._phan_chan_doan()
        dong += self._phan_gioi_han()
        return "\n".join(dong)

    def _phan_nap(self) -> list[str]:
        dong = ["## 1. Nạp firmware", ""]
        lan_cuoi = (
            self.flash_log.last_success() if self.flash_log is not None else None
        )
        dong += [
            "```",
            "eaa build                    # ráp các module đã merge thành ảnh nạp được",
            "eaa ports                    # xem cổng nào là mạch của dự án",
            "eaa flash                    # nạp — LUÔN hỏi xác nhận trước",
            "```",
            "",
            "Sau khi nạp, Agent đọc ngược bộ nhớ và so với ảnh đã gửi. Ba kết cục:",
            "*đã kiểm và khớp* · *đọc ngược lệch* (lần nạp bị coi là trượt) ·",
            "*không kiểm được* (mạch nạp không hỗ trợ). Kết cục thứ ba KHÔNG có",
            "nghĩa là nạp đúng.",
            "",
        ]
        if lan_cuoi is not None:
            dong += [
                f"Bản đang nằm trên thiết bị: commit `{lan_cuoi.commit[:10]}`, "
                f"nạp lúc {lan_cuoi.flashed_at}.",
                "",
            ]
        else:
            dong += [
                "Chưa lần nạp nào được ghi lại, nên engine KHÔNG biết bản nào đang trên thiết bị.",
                "",
            ]
        return dong

    def _phan_do(self) -> list[str]:
        dong = ["## 2. Đo và nghiệm thu", ""]
        so_do = (getattr(self.constraints, "acceptance", {}) or {}).get("measurements") or []
        if so_do:
            dong += ["| Số đo | Ngưỡng | Lấy từ đâu |", "|---|---|---|"]
            for m in so_do:
                nguong = []
                if m.get("max") is not None:
                    nguong.append(f"≤ {m['max']}")
                if m.get("min") is not None:
                    nguong.append(f"≥ {m['min']}")
                dong.append(
                    f"| {m.get('name', '?')} | {' và '.join(nguong)} {m.get('unit', '')} | "
                    f"{m.get('key', '—')} |"
                )
            dong.append("")
        dong += [
            "```",
            "eaa telemetry --port <cổng> --seconds 60      # thu số đo từ mạch",
            "eaa tune --port <cổng>                        # nghiệm thu tại G4",
            "eaa endurance --port <cổng> --seconds 600     # chạy dài, bắt reset",
            "```",
            "",
        ]
        return dong

    def _phan_chan_doan(self) -> list[str]:
        dong = ["## 3. Chẩn đoán khi có sự cố", ""]
        if not self.scenarios:
            dong += ["Dự án chưa khai kịch bản chẩn đoán nào.", ""]
            return dong

        dong += ["| Kịch bản | Dùng khi | Có chuyển động |", "|---|---|---|"]
        for s in self.scenarios:
            trieu_chung = ", ".join(getattr(s, "symptoms", ()) or []) or "—"
            dong.append(
                f"| `{getattr(s, 'id', '?')}` {getattr(s, 'title', '')} | "
                f"{trieu_chung} | {'CÓ — cần checklist an toàn' if getattr(s, 'motion', False) else 'không'} |"
            )
        dong += [
            "",
            "```",
            "eaa diagnose select \"<mô tả triệu chứng>\"   # Agent chọn kịch bản",
            "eaa diagnose build <DS-xx>                  # dựng firmware đo",
            "eaa diagnose run <DS-xx> --port <cổng>      # chạy và kết luận",
            "```",
            "",
            "Kết luận là phép GIAO của kênh máy và kênh người. Với nửa dữ liệu,",
            "kết luận nào cũng có thể sai mà vẫn nghe chắc chắn.",
            "",
        ]
        return dong

    def _phan_gioi_han(self) -> list[str]:
        gioi_han = self.limitations()
        dong = ["## 4. Điều hệ thống KHÔNG làm được", ""]
        if not gioi_han:
            dong += [
                "Không tìm thấy giới hạn nào trong dữ liệu dự án — và đó là một",
                "kết quả đáng ngờ hơn là đáng mừng. Kiểm lại xem Assumption Log,",
                "kho errata và các kịch bản chẩn đoán đã được điền chưa.",
                "",
            ]
            return dong

        dong += [
            "Phần này được dựng từ dữ liệu thật của dự án, không phải từ một đoạn",
            "văn khiêm tốn viết cho có. Người tiếp nhận đọc kỹ phần này trước phần",
            "khác: một tài liệu chỉ nói hệ thống làm được gì là một tài liệu đặt bẫy.",
            "",
        ]
        dong += [f"- {g}" for g in gioi_han]
        dong.append("")
        return dong


# --------------------------------------------------------------------------
# N-101 — đổi linh kiện
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentDelta:
    """Một khác biệt giữa linh kiện cũ và linh kiện thay thế."""

    aspect: str
    old: str
    new: str
    impact: str = ""
    #: Thanh ghi / chân / khóa cấu hình bị chạm — dùng để tra ngược ra mã.
    touches: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.aspect.strip():
            raise HandoverError("khác biệt không nêu ở mặt nào")
        if self.old.strip() == self.new.strip():
            raise HandoverError(
                f"{self.aspect!r}: hai bên giống nhau nên đây không phải một khác "
                "biệt. Một bảng so sánh đầy dòng 'giống nhau' sẽ được lướt qua, "
                "và dòng khác biệt thật sự lướt qua cùng."
            )

    def render(self) -> str:
        dong = [f"  {self.aspect}: {self.old}  →  {self.new}"]
        if self.impact:
            dong.append(f"      {self.impact}")
        if self.touches:
            dong.append(f"      chạm tới: {', '.join(self.touches)}")
        return "\n".join(dong)


@dataclass(frozen=True)
class SwapImpact:
    """Một module bị ảnh hưởng bởi việc đổi linh kiện."""

    module_id: str
    reason: str
    delta: ComponentDelta | None = None

    def render(self) -> str:
        return f"  {self.module_id}: {self.reason}"


@dataclass
class SwapAnalysis:
    """So hai linh kiện, rồi chỉ đích danh mã nào phải sửa."""

    old_part: str
    new_part: str
    deltas: tuple[ComponentDelta, ...] = ()
    drop_in: bool = False
    proposed_by: str = ""

    def impacts(self, hardware: Any, modules: Iterable[Any], graph: Any = None) -> list[SwapImpact]:
        """Module nào chạm vào một khác biệt.

        Bắc cầu trên dữ liệu đã có: khác biệt nêu tên thanh ghi hoặc tài nguyên
        → module nào dùng tài nguyên ấy, hoặc cấu hình thanh ghi ấy. Không đoán
        theo tên module.
        """
        ket_qua: list[SwapImpact] = []
        for m in modules:
            ma = str(getattr(m, "id", None) or getattr(m, "module_id", "") or m)
            dung = {str(x) for x in (getattr(m, "uses", ()) or ())}
            thanh_ghi = {
                r.upper()
                for nv in dung
                for r in getattr(hardware, "registers_of", lambda _: ())(nv)
            }
            if graph is not None and hasattr(graph, "registers_for"):
                thanh_ghi |= {r.upper() for r in graph.registers_for(ma)}

            for d in self.deltas:
                cham = [
                    t for t in d.touches if t in dung or t.upper() in thanh_ghi
                ]
                if cham:
                    ket_qua.append(
                        SwapImpact(
                            module_id=ma,
                            reason=f"{d.aspect} đổi ({d.old} → {d.new}), qua {', '.join(cham)}",
                            delta=d,
                        )
                    )
        return ket_qua

    def render(self, hardware: Any = None, modules: Iterable[Any] = (), graph: Any = None) -> str:
        dong = [f"Đổi linh kiện: {self.old_part}  →  {self.new_part}", ""]
        if self.drop_in and not self.deltas:
            dong += [
                "Nhà sản xuất công bố THAY THẲNG ĐƯỢC, và bản so sánh không tìm",
                "thấy khác biệt nào chạm tới dự án.",
                "",
                "Vẫn phải chạy lại bộ kịch bản chẩn đoán trên linh kiện mới. 'Thay",
                "thẳng được' là một lời hứa về chân và về giao thức, không phải một",
                "lời hứa về dải hoạt động, về nhiễu, hay về thời gian đáp ứng.",
            ]
            return "\n".join(dong)

        dong += ["Khác biệt:"]
        dong += [d.render() for d in self.deltas] or ["  (chưa tìm thấy)"]

        if hardware is not None:
            cham = self.impacts(hardware, modules, graph)
            dong += ["", "Mã phải xem lại:"]
            dong += [c.render() for c in cham] or [
                "  (không module nào chạm tới các khác biệt trên)"
            ]
            if cham:
                dong += [
                    "",
                    "Danh sách trên suy từ đồ thị tài nguyên, nên nó nêu được module",
                    "nào ĐỤNG TỚI thứ đã đổi. Nó không nói được mã ấy sai ở đâu —",
                    "đó vẫn là việc đọc mã của người.",
                ]
        return "\n".join(dong)


_LUOC_DO_SWAP = """{
  "drop_in": false,
  "deltas": [
    {
      "aspect": "<mặt so sánh: sơ đồ chân, dải điện áp, thanh ghi, thời gian đáp ứng…>",
      "old": "<linh kiện cũ ra sao>",
      "new": "<linh kiện mới ra sao>",
      "impact": "<khác biệt này gây ra chuyện gì trong mã>",
      "touches": ["<TÊN THANH GHI hoặc id tài nguyên bị chạm>"]
    }
  ]
}"""


@dataclass
class LlmSwapAnalyst:
    """So hai linh kiện bằng mô hình nền — kết quả là proposed fact."""

    llm: Any
    budget: int = 2500

    def compare(
        self, *, old_part: str, new_part: str, used_for: str = "", registers: Sequence[str] = ()
    ) -> SwapAnalysis:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=(
                "Bạn so hai linh kiện điện tử để trả lời câu: đổi cái này lấy "
                "cái kia thì phải sửa gì trong firmware. Chỉ nêu khác biệt CÓ "
                "THẬT theo tài liệu nhà sản xuất. Với mỗi khác biệt, nêu tên "
                "THANH GHI hoặc tài nguyên bị chạm để tra ngược ra mã. Không "
                "liệt kê những mặt giống nhau — một bảng đầy dòng 'giống nhau' "
                "sẽ được lướt qua cùng với dòng khác biệt thật sự."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Linh kiện đang dùng: {old_part}\n"
                    f"Linh kiện thay thế: {new_part}\n"
                    + (f"Dự án dùng nó để: {used_for}\n" if used_for else "")
                    + (
                        f"Thanh ghi dự án đang cấu hình: {', '.join(registers)}\n"
                        if registers
                        else ""
                    )
                    + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                    f"```json\n{_LUOC_DO_SWAP}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module="đổi linh kiện",
            budget=self.budget + 800,
        )
        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise HandoverError(f"Không so được hai linh kiện: {exc}") from exc

        from eaa.options import _boc_json

        du_lieu = _boc_json(van_ban)
        return SwapAnalysis(
            old_part=old_part,
            new_part=new_part,
            drop_in=bool(du_lieu.get("drop_in", False)),
            deltas=tuple(
                ComponentDelta(
                    aspect=str(d.get("aspect", "")),
                    old=str(d.get("old", "")),
                    new=str(d.get("new", "")),
                    impact=str(d.get("impact", "")),
                    touches=tuple(str(x) for x in (d.get("touches") or [])),
                )
                for d in (du_lieu.get("deltas") or [])
                if isinstance(d, dict)
            ),
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )


# --------------------------------------------------------------------------
# N-103 — cập nhật thiết bị đã triển khai
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RolloutStage:
    """Một bậc triển khai: bao nhiêu thiết bị, và dừng khi nào."""

    name: str
    devices: int
    soak_hours: float
    stop_if: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.devices < 1:
            raise HandoverError(f"Bậc {self.name!r} không có thiết bị nào")
        if not self.stop_if:
            raise HandoverError(
                f"Bậc {self.name!r} không nêu ĐIỀU KIỆN DỪNG. Một kế hoạch triển "
                "khai không có điều kiện dừng sẽ chạy hết mọi bậc dù bậc đầu đã "
                "hỏng — vì không ai định nghĩa thế nào là hỏng."
            )

    def render(self) -> str:
        dong = [f"  {self.name}: {self.devices} thiết bị, theo dõi {self.soak_hours:g} giờ"]
        dong += [f"      DỪNG nếu: {x}" for x in self.stop_if]
        return "\n".join(dong)


@dataclass
class RolloutPlan:
    """Quy trình cập nhật firmware cho thiết bị đã triển khai."""

    from_commit: str
    to_commit: str
    stages: tuple[RolloutStage, ...] = ()
    #: Bản để quay lui — phải có, và phải là bản ĐÃ TỪNG chạy trên thiết bị.
    rollback_to: str = ""
    #: Điều bản mới đòi hỏi mà bản cũ không có (định dạng dữ liệu lưu, giao thức).
    compatibility_notes: tuple[str, ...] = ()

    def problems(self) -> list[str]:
        van_de: list[str] = []
        if not self.rollback_to:
            van_de.append(
                "Không có bản để quay lui. Cập nhật không có đường lui là cập nhật "
                "mà mọi thiết bị hỏng đều phải mang về xưởng."
            )
        if not self.stages:
            van_de.append("Chưa chia bậc triển khai.")
        elif self.stages[0].devices != 1:
            van_de.append(
                f"Bậc đầu có {self.stages[0].devices} thiết bị. Phải là ĐÚNG MỘT — "
                "một bản vá hỏng nhân lên bằng số thiết bị đã nhận nó, và số ấy "
                "chỉ giảm được bằng cách bắt đầu từ một."
            )
        tang = [s.devices for s in self.stages]
        if tang != sorted(tang):
            van_de.append(
                "Số thiết bị mỗi bậc không tăng dần. Bậc sau nhỏ hơn bậc trước thì "
                "bậc trước đã gánh rủi ro mà chẳng để làm gì."
            )
        if self.rollback_to and self.rollback_to == self.to_commit:
            van_de.append(
                "Bản quay lui trùng bản đang triển khai — không phải một đường lui."
            )
        return van_de

    @property
    def ok(self) -> bool:
        return not self.problems()

    def render(self) -> str:
        dong = [
            f"Kế hoạch cập nhật: {self.from_commit[:10] or '?'} → {self.to_commit[:10] or '?'}",
            "",
        ]
        dong += ["Bậc triển khai:"]
        dong += [s.render() for s in self.stages] or ["  (chưa chia bậc)"]

        dong += ["", f"Quay lui về: {self.rollback_to[:10] or 'CHƯA CÓ'}"]
        if self.compatibility_notes:
            dong += ["", "Tương thích ngược — phải kiểm trước khi bấm nút:"]
            dong += [f"  · {x}" for x in self.compatibility_notes]

        van_de = self.problems()
        if van_de:
            dong += ["", "KHÔNG TRIỂN KHAI ĐƯỢC:"]
            dong += [f"  · {v}" for v in van_de]
        else:
            dong += [
                "",
                "Kế hoạch hợp lệ. Nó vẫn cần người bấm nút ở từng bậc — engine",
                "không tự chuyển bậc, vì điều kiện dừng là thứ người quan sát chứ",
                "không phải thứ đọc được từ một tệp.",
            ]
        return "\n".join(dong)

    @classmethod
    def default(cls, *, from_commit: str, to_commit: str, rollback_to: str) -> "RolloutPlan":
        """Kế hoạch mặc định: một thiết bị, rồi một nhóm nhỏ, rồi tất cả.

        Con số ở đây là ĐỀ XUẤT — số thiết bị và thời gian theo dõi phụ thuộc
        vào quy mô triển khai thật, thứ engine không biết. Điều KHÔNG thương
        lượng là bậc đầu tiên có đúng một thiết bị.
        """
        return cls(
            from_commit=from_commit,
            to_commit=to_commit,
            rollback_to=rollback_to,
            stages=(
                RolloutStage(
                    "thử nghiệm",
                    devices=1,
                    soak_hours=24.0,
                    stop_if=(
                        "thiết bị khởi động lại dù chỉ một lần",
                        "bất kỳ số đo nghiệm thu nào ra ngoài ngưỡng",
                        "không nạp ngược lại được bản cũ",
                    ),
                ),
                RolloutStage(
                    "nhóm nhỏ",
                    devices=10,
                    soak_hours=72.0,
                    stop_if=(
                        "quá một thiết bị báo lỗi",
                        "xuất hiện triệu chứng chưa từng thấy ở bậc trước",
                    ),
                ),
                RolloutStage(
                    "toàn bộ",
                    devices=1000,
                    soak_hours=0.0,
                    stop_if=("tỉ lệ lỗi vượt mức của bậc nhóm nhỏ",),
                ),
            ),
        )
