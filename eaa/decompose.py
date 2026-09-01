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
    #: Module ĐÃ CÓ trong backlog từ vòng phân rã trước.
    #:
    #: Bản phân rã vốn giả định mình là tự đủ: mọi phụ thuộc phải nằm trong
    #: chính nó. Giả định ấy đúng ở vòng ĐẦU, và sai ở mọi vòng sau — module
    #: mới dựa vào module đã duyệt là chuyện bình thường. SL-131 đã dạy BỘ
    #: PHÂN RÃ biết danh sách này để dựng prompt và chặn trùng tên; trường
    #: dưới đây là nửa còn lại, để BẢN phân rã kiểm được trên tập đầy đủ
    #: thay vì từ chối thẳng (SL-140).
    known: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.modules:
            raise DecomposeError("Bản phân rã không có module nào")
        ma = [m.id for m in self.modules]
        trung = {x for x in ma if ma.count(x) > 1}
        if trung:
            raise DecomposeError(f"Mã module trùng nhau: {sorted(trung)}")

        # Kiểm trên TẬP ĐẦY ĐỦ, không nới lỏng phép kiểm: một cái tên không có
        # ở cả hai chỗ vẫn là mô hình nêu ra một module chưa từng tồn tại.
        biet = set(ma) | set(self.known)
        for m in self.modules:
            la = [d for d in m.depends_on if d not in biet]
            if la:
                raise DecomposeError(
                    f"Module {m.id!r} phụ thuộc vào module không có trong bản "
                    f"phân rã lẫn trong backlog: {la}"
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
        # Trừ đi module đã có: chúng đã xong nên không tạo ràng buộc thứ tự
        # cho vòng này, và KHÔNG được lọt vào kết quả — `plan accept` đọc
        # danh sách ấy để thêm module mới, thêm nhầm một module đã merge là
        # chạy lại `eaa gen` trên mã đã duyệt (SL-140).
        da_co = set(self.known)
        con_lai = {m.id: set(m.depends_on) - da_co for m in self.modules}
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
        # Trừ đi module đã có: chúng đã xong nên không tạo ràng buộc thứ tự
        # cho vòng này, và KHÔNG được lọt vào kết quả — `plan accept` đọc
        # danh sách ấy để thêm module mới, thêm nhầm một module đã merge là
        # chạy lại `eaa gen` trên mã đã duyệt (SL-140).
        da_co = set(self.known)
        con_lai = {m.id: set(m.depends_on) - da_co for m in self.modules}
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
            "known": list(self.known),
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
            known=tuple(str(x) for x in (d.get("known") or [])),
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
    #: Manifest của Platform Pack. ``None`` thì bản phân rã không biết nền tảng
    #: cho sẵn gì — và nó sẽ đề xuất module dựng lại chính nền tảng (SL-130).
    pack_manifest: Any = None

    def propose(
        self,
        goal: str,
        *,
        hardware: Any = None,
        constraints: Any = None,
        #: Module đã có trong backlog: ``[(id, (tài nguyên nó chiếm, …)), …]``.
        #: Thiếu nó thì bản phân rã đề xuất lại thứ dự án đã làm (SL-131).
        existing: Any = (),
    ) -> DecompositionPlan:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        if not (goal or "").strip():
            raise DecomposeError(
                "Chưa có mục tiêu để phân rã. Mục tiêu đến từ 'eaa brief' hoặc "
                "từ mô tả của bạn — Agent không tự nghĩ ra bài toán."
            )

        boi_canh = self._boi_canh(hardware, constraints)
        nen_tang = _boi_canh_nen_tang(getattr(self, "pack_manifest", None))
        da_co_txt = _boi_canh_da_co(existing)
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
                    f"Mục tiêu: {goal}\n\n{boi_canh}\n{nen_tang}\n{da_co_txt}\n"
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
        canh_bao = (
            _kiem_tai_nguyen(module, hardware)
            + _kiem_chu_ky(module, constraints)
            + _kiem_trung_nen_tang(module, getattr(self, "pack_manifest", None))
            + _kiem_trung_da_co(module, existing)
        )

        return DecompositionPlan(
            modules=module,
            goal=goal,
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
            warnings=tuple(canh_bao),
            # Chuyển tiếp danh sách module đã có xuống bản phân rã. Thiếu dòng
            # này thì bộ phân rã biết chúng còn bản phân rã thì không, và mọi
            # vòng phân rã thứ hai chết ở khâu kiểm phụ thuộc (SL-140).
            known=tuple(_ma_da_co(existing)),
        )

    @staticmethod
    def _boi_canh(hardware: Any, constraints: Any) -> str:
        """Bối cảnh phân rã: tài nguyên có thật, và TOÀN BỘ ràng buộc.

        Phần ràng buộc lấy từ ĐÚNG bảng K1 mà đường sinh mã dùng, không dựng
        lại một tập con. Bản trước chỉ lấy ``limits`` và ``forbidden``, bỏ hẳn
        ``style`` — nên ``arithmetic: integer`` chưa bao giờ tới được bộ phân
        rã, và nó giải thích module lọc góc bằng ``float_in_isr``, một luật hẹp
        hơn nhiều (SL-131).

        Hai chỗ dựng cùng một thứ bằng hai đoạn mã khác nhau thì sớm muộn chúng
        lệch nhau. SL-112 đã là đúng chuyện ấy giữa đường sinh mã và đường hội
        thoại; đây là lần thứ hai.
        """
        phan: list[str] = []
        if hardware is not None:
            dong = _dong_tai_nguyen(getattr(hardware, "peripherals", []))
            dong += _dong_tai_nguyen(getattr(hardware, "components", []))
            if dong:
                phan.append(
                    "Tài nguyên phần cứng CÓ THẬT (chỉ dùng những thứ dưới đây):\n"
                    + "\n".join(dong)
                )
        if constraints is not None:
            from eaa.composer import _bang_rang_buoc

            bang = _bang_rang_buoc(constraints)
            if bang.strip():
                phan.append(bang)
        return "\n".join(phan) + ("\n" if phan else "")


#: Khóa của hồ sơ phần cứng KHÔNG đưa vào bối cảnh phân rã.
#:
#: Danh sách thanh ghi thuộc về đường sinh mã (lớp K6 dựng từ đồ thị), không
#: thuộc bước quyết định "chia thành module nào". Đưa nó vào đây là đốt ngân
#: sách cho thứ chưa dùng tới.
_BO_QUA_KHI_PHAN_RA = frozenset({"configured_by", "whoami_expected", "id"})


def _dong_tai_nguyen(muc_list) -> list[str]:
    """Mỗi tài nguyên MỘT DÒNG, kèm thuộc tính của nó.

    Bản trước rút cả hồ sơ thành một danh sách tên ngăn cách bằng dấu phẩy, và
    mọi thuộc tính bị bỏ: `drive`, `active_level`, `pins`, `kind`, `note`. Bộ
    phân rã nhận một danh sách TÊN rồi phải tự đoán mỗi cái tên cần gì.

    Nó đoán sai theo đúng cách trực giác chung sẽ sai: hồ sơ ghi rõ còi là loại
    tự dao động, chỉ cần đặt mức chân; prompt không mang dòng ấy, nên bản phân
    rã xin một bộ đếm cho còi — lần đầu xin `timer2`, đúng bộ đếm đang phát
    xung bước (SL-141).
    """
    dong: list[str] = []
    for muc in muc_list or ():
        if not isinstance(muc, dict):
            continue
        ma = str(muc.get("id", "")).strip()
        if not ma:
            continue
        thuoc_tinh: list[str] = []
        for khoa, gia_tri in muc.items():
            if khoa in _BO_QUA_KHI_PHAN_RA or gia_tri in (None, "", [], {}):
                continue
            if isinstance(gia_tri, dict):
                gia_tri = ", ".join(f"{k}={v}" for k, v in gia_tri.items())
            elif isinstance(gia_tri, (list, tuple)):
                gia_tri = ", ".join(str(x) for x in gia_tri)
            thuoc_tinh.append(f"{khoa}={gia_tri}")
        dong.append(f"  {ma}" + (f" · {'; '.join(thuoc_tinh)}" if thuoc_tinh else ""))
    return dong


def _boi_canh_da_co(da_co) -> str:
    """Nói cho bộ phân rã biết dự án ĐÃ CÓ module nào và chúng chiếm gì.

    Không có phần này thì mô hình đề xuất thêm một module chiếm đúng ngoại vi
    mà một module đã merge đang giữ — không phải vì nó kém, mà vì prompt không
    có backlog. Người duyệt phải tự nhớ ra, và đó là chỗ dễ quên nhất khi bản
    phân rã dài.
    """
    muc: list[tuple[str, tuple[str, ...], str]] = []
    for x in da_co or []:
        # Chấp nhận cả dạng cũ `(mã, ngoại vi)` lẫn dạng có trách nhiệm.
        ma = str(x[0]).strip()
        dung = tuple(str(y) for y in (x[1] or ())) if len(x) > 1 else ()
        viec = str(x[2]).strip() if len(x) > 2 else ""
        if ma:
            muc.append((ma, dung, viec))
    if not muc:
        return ""
    dong = ["## DỰ ÁN ĐÃ CÓ SẴN — ĐỪNG ĐỀ XUẤT LẠI, VÀ ĐỪNG ÔM LẠI VIỆC CỦA CHÚNG"]
    for i, u, v in muc:
        dong.append(f"  {i}" + (f" (chiếm: {', '.join(u)})" if u else ""))
        # Trách nhiệm, không chỉ tên. Biết một module TỒN TẠI mà không biết nó
        # LÀM GÌ thì vẫn đề xuất chồng lên: bản phân rã đầu tiên đẻ ra `app_hmi`
        # ôm đúng giao thức nút nhấn và tiếng bíp mà `app_balance` đã nhận
        # (SL-141).
        if v:
            dong.append(f"      việc của nó: {v}")
    dong.append(
        "Cần thêm việc cho một module đã có thì nói RÕ là mở rộng module ấy, "
        "đừng đề xuất một module mới chiếm cùng ngoại vi hay ôm cùng trách nhiệm."
    )
    return "\n".join(dong) + "\n"


def _ma_da_co(da_co) -> list[str]:
    """Chỉ lấy MÃ module từ danh sách `(mã, ngoại vi)` của backlog."""
    ket_qua: list[str] = []
    for muc in da_co or ():
        ma = str(muc[0] if isinstance(muc, (tuple, list)) else muc).strip().lower()
        if ma:
            ket_qua.append(ma)
    return ket_qua


def _kiem_trung_da_co(modules, da_co) -> list[str]:
    """Module đề xuất giẫm lên module đã có — trùng tên, hoặc trùng ngoại vi."""
    # Chấp nhận cả dạng cũ `(mã, ngoại vi)` lẫn dạng có kèm trách nhiệm.
    muc = [
        (str(x[0]).strip(), {str(y).strip().lower() for y in (x[1] or ())} if len(x) > 1 else set())
        for x in (da_co or [])
    ]
    muc = [(i, u) for i, u in muc if i]
    if not muc:
        return []

    ra: list[str] = []
    for m in modules:
        for ten, tn_cu in muc:
            if m.id == ten:
                ra.append(
                    f"{m.id}: trùng TÊN module đã có trong backlog. Đề xuất lại "
                    "một module đã làm là đè lên công đã bỏ ra."
                )
                continue
            chung = {str(x).strip().lower() for x in (getattr(m, "uses", ()) or ())} & tn_cu
            if chung:
                ra.append(
                    f"{m.id}: chiếm {', '.join(sorted(chung))} — module {ten!r} "
                    "đã có trong backlog đang giữ tài nguyên này. Hai module "
                    "cùng chiếm một ngoại vi là xung đột, không phải lựa chọn."
                )
    return ra


def _phan_firmware(pack) -> dict:
    """Khối `firmware` của Platform Pack, ở dạng ánh xạ. Không có thì trả rỗng."""
    if pack is None:
        return {}
    fw = getattr(pack, "firmware", None)
    if fw is None and isinstance(pack, dict):
        fw = pack.get("firmware")
    if isinstance(fw, dict):
        return fw
    # PackManifest giữ khối này ở dạng đối tượng; lấy các trường cần bằng tên.
    ra = {}
    for ten in ("reserves", "provides", "contract"):
        gia_tri = getattr(fw, ten, None)
        if gia_tri:
            ra[ten] = gia_tri
    return ra


def _boi_canh_nen_tang(pack) -> str:
    """Nói cho bộ phân rã biết Platform Pack ĐÃ CHO SẴN những gì.

    Không có phần này thì mô hình đề xuất module dựng lại chính nền tảng — và
    nó không sai vì kém, mà vì **không ai nói cho nó**. Prompt phân rã vốn chỉ
    có mục tiêu, hồ sơ phần cứng và ràng buộc; ba thứ ấy không chỗ nào nói
    rằng khuôn của pack đã sinh `main` và đã chiếm một bộ đếm thời gian.

    Cái giá của chỗ thiếu này được trả bằng toàn bộ vòng đời của những module
    thừa: chúng chỉ va nhau ở bước LIÊN KẾT, tức sau khi đã qua sinh mã, bốn
    cổng kiểm chứng và G3 (SL-130).
    """
    fw = _phan_firmware(pack)
    if not fw:
        return ""
    dong = ["## NỀN TẢNG ĐÃ CHO SẴN — ĐỪNG DỰNG LẠI"]
    if fw.get("contract"):
        dong += ["", str(fw["contract"]).strip()]
    if fw.get("provides"):
        dong.append("")
        dong.append(
            "Ký hiệu nền tảng SINH RA (module khai cung cấp trùng tên là trùng "
            "định nghĩa lúc liên kết): " + ", ".join(str(x) for x in fw["provides"])
        )
    if fw.get("reserves"):
        dong.append("")
        dong.append(
            "Ngoại vi nền tảng CHIẾM RIÊNG (có trong hồ sơ phần cứng, nhưng đã "
            "bị giữ trước — đừng phân cho module nào): "
            + ", ".join(str(x) for x in fw["reserves"])
        )
    return "\n".join(dong) + "\n"


def _kiem_trung_nen_tang(modules, pack) -> list[str]:
    """Module nào giẫm lên phần nền tảng đã giữ.

    Phép kiểm tài nguyên thường đối chiếu với HỒ SƠ PHẦN CỨNG, và tài nguyên bị
    nền tảng chiếm thì VẪN CÓ trong hồ sơ — nên nó không bắt được. Đây là phép
    kiểm còn thiếu.
    """
    fw = _phan_firmware(pack)
    if not fw:
        return []
    giu = {str(x).strip().lower() for x in (fw.get("reserves") or [])}
    cho = {str(x).strip().lower() for x in (fw.get("provides") or [])}

    ra: list[str] = []
    for m in modules:
        for tn in getattr(m, "uses", ()) or ():
            if str(tn).strip().lower() in giu:
                ra.append(
                    f"{m.id}: chiếm {tn!r} — nền tảng đã giữ tài nguyên này cho "
                    "khuôn firmware. Hai bên cùng cấu hình một bộ đếm, và ngắt "
                    "sẽ trùng định nghĩa lúc liên kết."
                )
        for ky in getattr(m, "provides", ()) or ():
            if str(ky).strip().lower() in cho:
                ra.append(
                    f"{m.id}: cung cấp {ky!r} — nền tảng đã sinh ký hiệu này. "
                    "Trùng định nghĩa lúc liên kết. Module chỉ cung cấp hàm "
                    "khởi tạo và hàm bước."
                )
    return ra


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
