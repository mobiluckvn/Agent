"""Đề xuất phân rã module — N-040..N-043, công đoạn C.

EAA-AIS-05 §3, quy trình P2; FR-KG-02. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-43.

``eaa plan add`` đã có từ Sprint 0, nhưng nó chỉ GHI LẠI thứ người đã nghĩ ra.
Người dùng phải tự chia bài toán thành module, tự biết module nào chiếm ngoại
vi nào, tự xếp thứ tự làm, tự chọn chu kỳ chạy. Bốn việc ấy đòi đúng loại kiến
thức mà Agent có sẵn — nó đọc được hồ sơ phần cứng, biết ngoại vi nào tồn tại,
biết ràng buộc thời gian đã chốt.

Bốn thứ đề xuất cùng lúc, vì chúng ràng buộc nhau
--------------------------------------------------

* **Danh sách module** — chia theo ngoại vi và theo tầng (driver / logic / điều phối).
* **Tài nguyên mỗi module chiếm** — nguồn để phát hiện xung đột NGAY lúc khai báo.
* **Phụ thuộc** — quyết định thứ tự làm, và quyết định module nào chạy song song được.
* **Chu kỳ chạy** — quyết định tải CPU, mà tải CPU lại quyết định phân rã có
  khả thi không.

Tách bốn thứ này ra bốn lượt hỏi thì lượt sau phá kết quả lượt trước: chọn chu
kỳ 1 ms cho một module vừa được xếp phụ thuộc vào một module 100 ms là vô nghĩa.

Điều Agent KHÔNG làm
---------------------

Nó không tự thêm module vào backlog. Phân rã là quyết định kiến trúc, và kiến
trúc sai thì mọi module sau đều đúng quy trình mà sai chỗ. Đề xuất là *proposed
fact*; người xem rồi mới nhận.

Và ước lượng tải CPU ở đây là **ước lượng**, không phải số đo. Nó dùng để phát
hiện phân rã bất khả thi ngay từ trên giấy — mười việc mỗi việc 3 ms trong chu
kỳ 10 ms là không chạy được, và biết điều đó trước khi viết dòng mã nào thì rẻ
hơn nhiều. Số thật chỉ có khi đo trên thiết bị (N-083).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "DecomposeError",
    "ModuleProposal",
    "DecompositionPlan",
    "LlmDecomposer",
    "PLAN_FILE",
    "TRAN_TAI_CPU",
]

#: Bản đề xuất phân rã đang chờ người nhận.
PLAN_FILE = ".eaa/plan_proposal.json"

#: Trần tải CPU ước lượng. Trên mức này thì bộ định thời hợp tác hết chỗ xoay:
#: một việc chạy lâu hơn dự kiến sẽ đẩy trễ mọi việc sau nó, và không còn biên
#: nào để hấp thụ. Con số nằm ở đây vì nó là tính chất của KIỂU điều phối, không
#: phải của một dự án hay một con chip.
TRAN_TAI_CPU = 0.70


class DecomposeError(Exception):
    """Bản phân rã không dùng được."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_MA_MODULE = re.compile(r"^[a-z][a-z0-9_]{2,39}$")


@dataclass(frozen=True)
class ModuleProposal:
    """Một module trong bản phân rã đề xuất."""

    id: str
    purpose: str
    #: Tài nguyên phần cứng module chiếm — khớp id ngoại vi/linh kiện trong hồ sơ.
    uses: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    #: Hàm module này cung cấp cho module khác — nguồn để sinh tệp tiêu đề trước.
    provides: tuple[str, ...] = ()
    #: Chu kỳ chạy, 0 nghĩa là không chạy định kỳ (thư viện thuần).
    period_ms: int = 0
    #: Ước lượng thời gian chạy một lượt. Là ƯỚC LƯỢNG, không phải số đo.
    est_exec_ms: float = 0.0
    layer: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if not _MA_MODULE.match(self.id or ""):
            raise DecomposeError(
                f"Mã module không hợp lệ: {self.id!r}. Chỉ chữ thường, số và gạch "
                "dưới, bắt đầu bằng chữ — mã này thành tên tệp và tên hàm."
            )
        if not self.purpose.strip():
            raise DecomposeError(f"Module {self.id!r} không nêu trách nhiệm")
        if self.period_ms < 0:
            raise DecomposeError(f"Module {self.id!r} có chu kỳ âm")
        if self.est_exec_ms < 0:
            raise DecomposeError(f"Module {self.id!r} có ước lượng thời gian âm")

    @property
    def scheduled(self) -> bool:
        return self.period_ms > 0

    @property
    def load(self) -> float:
        """Phần CPU module này chiếm, theo ước lượng."""
        if not self.scheduled or not self.est_exec_ms:
            return 0.0
        return self.est_exec_ms / self.period_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "purpose": self.purpose,
            "uses": list(self.uses),
            "depends_on": list(self.depends_on),
            "provides": list(self.provides),
            "period_ms": self.period_ms,
            "est_exec_ms": self.est_exec_ms,
            "layer": self.layer,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ModuleProposal":
        if not isinstance(d, dict) or not d.get("id"):
            raise DecomposeError(f"mục module thiếu 'id': {d!r}")
        return cls(
            id=str(d["id"]).strip().lower(),
            purpose=str(d.get("purpose", "")),
            uses=tuple(str(x) for x in (d.get("uses") or [])),
            depends_on=tuple(str(x).strip().lower() for x in (d.get("depends_on") or [])),
            provides=tuple(str(x) for x in (d.get("provides") or [])),
            period_ms=int(d.get("period_ms") or 0),
            est_exec_ms=float(d.get("est_exec_ms") or 0.0),
            layer=str(d.get("layer", "")),
            rationale=str(d.get("rationale", "")),
        )

    def render(self) -> str:
        nhip = f"mỗi {self.period_ms} ms" if self.scheduled else "không chạy định kỳ"
        dong = [f"  [{self.id}] {self.purpose}"]
        dong.append(f"      tầng {self.layer or '?'} · {nhip}")
        if self.uses:
            dong.append(f"      chiếm: {', '.join(self.uses)}")
        if self.depends_on:
            dong.append(f"      phụ thuộc: {', '.join(self.depends_on)}")
        if self.provides:
            dong.append(f"      cung cấp: {', '.join(self.provides)}")
        if self.scheduled and self.est_exec_ms:
            dong.append(
                f"      ước lượng {self.est_exec_ms:g} ms/lượt → {self.load:.0%} CPU"
            )
        if self.rationale:
            dong.append(f"      lý do: {self.rationale}")
        return "\n".join(dong)


@dataclass(frozen=True)
class DecompositionPlan:
    """Bản phân rã đề xuất, đã kiểm tính nhất quán."""

    modules: tuple[ModuleProposal, ...]
    goal: str = ""
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)
    #: Cảnh báo phát hiện lúc kiểm — không chặn, nhưng phải đọc.
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.modules:
            raise DecomposeError("Bản phân rã không có module nào")
        ma = [m.id for m in self.modules]
        trung = {x for x in ma if ma.count(x) > 1}
        if trung:
            raise DecomposeError(f"Mã module trùng nhau: {sorted(trung)}")

        biet = set(ma)
        for m in self.modules:
            la = [d for d in m.depends_on if d not in biet]
            if la:
                raise DecomposeError(
                    f"Module {m.id!r} phụ thuộc vào module không có trong bản "
                    f"phân rã: {la}"
                )

    @property
    def total_load(self) -> float:
        return sum(m.load for m in self.modules)

    @property
    def overloaded(self) -> bool:
        return self.total_load > TRAN_TAI_CPU

    def order(self) -> list[str]:
        """Thứ tự làm theo phụ thuộc — sắp topo, ổn định.

        Ném lỗi khi có vòng: một vòng phụ thuộc nghĩa là không module nào làm
        được trước, và phát hiện điều đó lúc lập kế hoạch rẻ hơn nhiều so với
        lúc đã viết nửa số module.
        """
        con_lai = {m.id: set(m.depends_on) for m in self.modules}
        ket_qua: list[str] = []
        while con_lai:
            san_sang = sorted(k for k, v in con_lai.items() if not v)
            if not san_sang:
                raise DecomposeError(
                    "Phụ thuộc thành vòng: " + ", ".join(sorted(con_lai))
                    + ". Không module nào làm được trước — phải cắt vòng bằng "
                    "cách tách một interface ra thành module riêng."
                )
            for k in san_sang:
                ket_qua.append(k)
                del con_lai[k]
            for v in con_lai.values():
                v.difference_update(san_sang)
        return ket_qua

    def parallel_groups(self) -> list[list[str]]:
        """Nhóm module làm song song được — cùng bậc phụ thuộc."""
        con_lai = {m.id: set(m.depends_on) for m in self.modules}
        nhom: list[list[str]] = []
        while con_lai:
            bac = sorted(k for k, v in con_lai.items() if not v)
            if not bac:
                raise DecomposeError("Phụ thuộc thành vòng")
            nhom.append(bac)
            for k in bac:
                del con_lai[k]
            for v in con_lai.values():
                v.difference_update(bac)
        return nhom

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "warnings": list(self.warnings),
            "modules": [m.to_dict() for m in self.modules],
        }

    @classmethod
    def from_dict(cls, d: Any) -> "DecompositionPlan":
        if not isinstance(d, dict):
            raise DecomposeError("bản phân rã phải là ánh xạ khóa–giá trị")
        return cls(
            modules=tuple(ModuleProposal.from_dict(m) for m in (d.get("modules") or [])),
            goal=str(d.get("goal", "")),
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
            warnings=tuple(str(x) for x in (d.get("warnings") or [])),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: str | Path) -> "DecompositionPlan | None":
        path = Path(path)
        if not path.is_file():
            return None
        try:
            return DecompositionPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise DecomposeError(f"{path}: bản phân rã hỏng — {exc}") from exc

    def render(self) -> str:
        dong = [f"Bản phân rã đề xuất cho: {self.goal}", ""]
        for m in self.modules:
            dong.append(m.render())
            dong.append("")

        dong.append("Thứ tự làm (theo phụ thuộc):")
        for i, nhom in enumerate(self.parallel_groups(), 1):
            song_song = " · làm song song được" if len(nhom) > 1 else ""
            dong.append(f"  {i}. {', '.join(nhom)}{song_song}")
        dong.append("")

        dong.append(
            f"Tải CPU ước lượng: {self.total_load:.0%} (trần {TRAN_TAI_CPU:.0%})"
        )
        if self.overloaded:
            dong += [
                "  ⚠ VƯỢT TRẦN. Phân rã này nhiều khả năng không chạy được:",
                "    một việc chạy lâu hơn dự kiến sẽ đẩy trễ mọi việc sau nó,",
                "    và không còn biên nào để hấp thụ.",
                "    Cách xử lý: giãn chu kỳ, gộp module, hoặc đẩy việc nặng ra ngắt.",
            ]
        dong.append(
            "  Đây là ƯỚC LƯỢNG, không phải số đo. Số thật chỉ có khi đo trên "
            "thiết bị."
        )

        if self.warnings:
            dong += ["", "Cảnh báo:"]
            dong += [f"  · {c}" for c in self.warnings]

        dong += [
            "",
            "Agent KHÔNG tự thêm vào backlog: phân rã là quyết định kiến trúc, và",
            "kiến trúc sai thì mọi module sau đều đúng quy trình mà sai chỗ.",
            "  Nhận bản này: eaa plan accept",
        ]
        return "\n".join(dong)


_LUOC_DO = """{
  "modules": [
    {
      "id": "<mã ngắn, chữ thường và gạch dưới>",
      "purpose": "<một câu: module này chịu trách nhiệm gì>",
      "layer": "driver|logic|dieu_phoi",
      "uses": ["<id ngoại vi hoặc linh kiện trong hồ sơ phần cứng>"],
      "depends_on": ["<mã module khác trong danh sách này>"],
      "provides": ["<tên hàm module này cho module khác gọi>"],
      "period_ms": <chu kỳ chạy; 0 nếu là thư viện không chạy định kỳ>,
      "est_exec_ms": <ước lượng thời gian một lượt chạy, mili giây>,
      "rationale": "<vì sao tách thành module riêng>"
    }
  ]
}"""


@dataclass
class LlmDecomposer:
    """Đề xuất phân rã bằng mô hình nền."""

    llm: Any
    budget: int = 3000

    def propose(
        self,
        goal: str,
        *,
        hardware: Any = None,
        constraints: Any = None,
    ) -> DecompositionPlan:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        if not (goal or "").strip():
            raise DecomposeError(
                "Chưa có mục tiêu để phân rã. Mục tiêu đến từ 'eaa brief' hoặc "
                "từ mô tả của bạn — Agent không tự nghĩ ra bài toán."
            )

        boi_canh = self._boi_canh(hardware, constraints)
        prompt = Prompt(
            system_instruction=(
                "Bạn phân rã một bài toán nhúng thành module. Mỗi module đúng MỘT "
                "trách nhiệm. Chỉ dùng tài nguyên phần cứng CÓ TRONG hồ sơ được "
                "cung cấp — không bịa ngoại vi. Chu kỳ chạy phải suy từ yêu cầu "
                "vật lý, không đặt bừa. Ước lượng thời gian chạy thì nói thật là "
                "ước lượng thô; thà rộng còn hơn hẹp."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Mục tiêu: {goal}\n\n{boi_canh}\n"
                    "Phân rã thành module. Trả về ĐÚNG một khối JSON theo lược "
                    f"đồ sau, không kèm giải thích ngoài khối:\n\n"
                    f"```json\n{_LUOC_DO}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module="phân rã module",
            budget=self.budget + 800,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise DecomposeError(f"Không đề xuất được phân rã: {exc}") from exc

        from eaa.options import boc_json

        du_lieu = boc_json(van_ban, DecomposeError)
        module = tuple(ModuleProposal.from_dict(m) for m in (du_lieu.get("modules") or []))
        canh_bao = _kiem_tai_nguyen(module, hardware) + _kiem_chu_ky(module, constraints)

        return DecompositionPlan(
            modules=module,
            goal=goal,
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
            warnings=tuple(canh_bao),
        )

    @staticmethod
    def _boi_canh(hardware: Any, constraints: Any) -> str:
        phan: list[str] = []
        if hardware is not None:
            ngoai_vi = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
            linh_kien = [str(c.get("id", "")) for c in getattr(hardware, "components", [])]
            co = [x for x in ngoai_vi + linh_kien if x]
            if co:
                phan.append("Tài nguyên phần cứng CÓ THẬT: " + ", ".join(co))
        if constraints is not None:
            gioi_han = getattr(constraints, "limits", {}) or {}
            if gioi_han:
                phan.append(
                    "Ràng buộc: "
                    + ", ".join(f"{k}={v}" for k, v in sorted(gioi_han.items()))
                )
            cam = getattr(constraints, "forbidden", []) or []
            if cam:
                phan.append("Điều cấm: " + ", ".join(cam))
        return "\n".join(phan) + ("\n" if phan else "")


def _kiem_tai_nguyen(
    modules: Sequence[ModuleProposal], hardware: Any
) -> list[str]:
    """Module có chiếm tài nguyên không tồn tại không.

    Mô hình rất hay bịa một ngoại vi nghe hợp lý. Bịa ở đây thì cả nhánh mã sau
    đó cấu hình một thứ không có trên chip, và lỗi chỉ lộ ra lúc chạy thật.
    """
    if hardware is None:
        return []
    co = {str(p.get("id", "")).lower() for p in getattr(hardware, "peripherals", [])}
    co |= {str(c.get("id", "")).lower() for c in getattr(hardware, "components", [])}
    if not co:
        return []

    canh_bao: list[str] = []
    for m in modules:
        la = [u for u in m.uses if u.lower() not in co]
        if la:
            canh_bao.append(
                f"{m.id}: chiếm tài nguyên KHÔNG CÓ trong hồ sơ phần cứng: "
                f"{', '.join(la)}. Hoặc mô hình bịa, hoặc hồ sơ còn thiếu — "
                "phải làm rõ trước khi nhận."
            )
    return canh_bao


def _kiem_chu_ky(
    modules: Sequence[ModuleProposal], constraints: Any
) -> list[str]:
    """Ba phép kiểm chu kỳ THẬT SỰ nói lên điều gì.

    Bản đầu của hàm này cảnh báo mọi module tầng logic có chu kỳ lớn hơn
    ``control_loop_ms`` — và nó báo động giả ngay lần chạy thật đầu tiên: một
    việc gửi telemetry mỗi 100 ms là hoàn toàn đúng, vì trần ấy là trần của
    VÒNG ĐIỀU KHIỂN, không phải của mọi việc. Một cơ chế báo động sai thì người
    ta học cách phớt lờ, và làm hỏng luôn những lần báo đúng.

    Ba điều dưới đây thì nói lên thật:
    """
    canh_bao: list[str] = []

    # 1. Một việc không chạy xong nổi trong chính chu kỳ của nó.
    for m in modules:
        if m.scheduled and m.est_exec_ms and m.est_exec_ms > m.period_ms:
            canh_bao.append(
                f"{m.id}: ước lượng {m.est_exec_ms:g} ms/lượt LỚN HƠN chu kỳ "
                f"{m.period_ms} ms. Việc không chạy xong nổi trong chu kỳ của "
                "chính nó thì lịch chạy không tồn tại."
            )

    if constraints is None:
        return canh_bao

    tran = (getattr(constraints, "limits", {}) or {}).get("control_loop_ms")
    if not isinstance(tran, (int, float)) or tran <= 0:
        return canh_bao

    # 2. Không việc nào chạy đủ nhanh để làm vòng điều khiển.
    dinh_ky = [m for m in modules if m.scheduled]
    if dinh_ky and not any(m.period_ms <= tran for m in dinh_ky):
        canh_bao.append(
            f"Không module nào có chu kỳ ≤ {tran} ms, trong khi dự án khai "
            f"control_loop_ms = {tran}. Vòng điều khiển đã chốt ở công đoạn A1 "
            "không có ai thực hiện — hoặc phân rã thiếu, hoặc ràng buộc thừa."
        )

    # 3. Chu kỳ không chia hết cho việc nhanh nhất: bộ định thời hợp tác chỉ
    #    chạy được bội số của nhịp, nên phần dư thành trôi chu kỳ.
    nhanh_nhat = min((m.period_ms for m in dinh_ky), default=0)
    if nhanh_nhat:
        le = [m.id for m in dinh_ky if m.period_ms % nhanh_nhat]
        if le:
            canh_bao.append(
                f"Chu kỳ không phải bội số của việc nhanh nhất ({nhanh_nhat} ms): "
                f"{', '.join(le)}. Bộ định thời hợp tác chỉ chạy được bội số của "
                "nhịp, nên phần dư thành trôi chu kỳ tích lũy."
            )

    return canh_bao
