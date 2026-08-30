"""Sinh giao diện TRƯỚC khi sinh phần thân — N-041.

EAA-AIS-05 §3 (K3 interface-only), EAA-SRS-01 FR-CTX-02; công đoạn D.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-51.

Vì sao thứ tự này quan trọng
-----------------------------

Vòng lặp chuẩn sinh từng module một, và một module phụ thuộc module khác thì
prompt của nó cần tệp tiêu đề của module kia (kỹ thuật nén K3). Trước bản này,
tệp tiêu đề chỉ xuất hiện SAU khi module kia đã sinh xong và merge — nên thứ
tự làm việc bị ép thành một hàng dọc: không ai bắt đầu được cho tới khi người
trước xong.

Sinh giao diện trước gỡ ràng buộc ấy. Hợp đồng gọi có trước, hai thân module
viết song song, và mỗi bên chỉ trông vào những gì bên kia đã hứa.

Ba câu hỏi mà một chữ ký hàm không trả lời được
------------------------------------------------

Một dòng ``void drv_step(void);`` nói được tên và kiểu, nhưng không nói được ba
điều mà người viết mã nhúng buộc phải biết trước khi gọi:

* **Gọi trong ngắt được không?** Gọi một hàm không an-toàn-ngắt từ ISR là lỗi
  chỉ lộ ra dưới tải, ở đúng lúc khó tái hiện nhất.
* **Nó có chặn không?** Một hàm chặn trong vòng điều khiển 10 ms là một vòng
  điều khiển sẽ trễ nhịp mà chẳng cổng nào báo.
* **Tái nhập được không?** Trạng thái tĩnh dùng chung giữa hai lời gọi lồng
  nhau hỏng theo cách im lặng.

Nên :class:`FunctionContract` bắt buộc trả lời cả ba. Không có mặc định "chắc
là được" — mỗi trường là một quyết định phải viết ra.

Engine không viết C
--------------------

Tệp tiêu đề là mã C, và mã C thuộc về Platform Pack. Engine cấp DỮ LIỆU (tên
module, danh sách hàm, hợp đồng gọi); pack cấp khuôn. Cùng ranh giới với khuôn
ráp firmware ở ``eaa/firmware.py`` — nếu engine tự sinh câu lệnh C thì cái
ranh giới TC-38 canh sẽ mờ dần từ đúng chỗ đó.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "InterfaceError",
    "FunctionContract",
    "InterfaceSpec",
    "InterfaceGenerator",
    "LlmInterfaceDesigner",
    "BANNER_DE_XUAT",
]

#: Dòng đầu tệp tiêu đề đề xuất. Composer lấy dòng chú thích đầu tiên làm tóm
#: tắt cho lớp K3, nên dòng này đi thẳng vào prompt — và đó chính là mục đích:
#: mô hình phải biết nó đang dựa vào một lời hứa, không phải vào mã đã chạy.
BANNER_DE_XUAT = (
    "GIAO DIỆN ĐỀ XUẤT — thân module CHƯA sinh. Chỉ là hợp đồng gọi, chưa là mã đã kiểm."
)

_TEN_HAM = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


class InterfaceError(Exception):
    """Không dựng được giao diện module."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FunctionContract:
    """Một hàm module cung cấp, kèm hợp đồng gọi.

    Ba trường ``isr_safe`` / ``blocking`` / ``reentrant`` cố ý KHÔNG có mặc
    định êm ái: mỗi cái là một quyết định người viết phải nói ra. Một mặc định
    "chắc là an toàn" sẽ được nhận vì nó tiện, và sai lệch chỉ lộ ra dưới tải.
    """

    signature: str
    purpose: str = ""
    isr_safe: bool = False
    blocking: bool = False
    reentrant: bool = False
    #: Điều người gọi phải bảo đảm trước khi gọi.
    precondition: str = ""

    def __post_init__(self) -> None:
        if not self.signature.strip():
            raise InterfaceError("hàm không có chữ ký")
        if "(" not in self.signature or ")" not in self.signature:
            raise InterfaceError(
                f"chữ ký {self.signature!r} không phải một khai báo hàm — thiếu "
                "danh sách tham số."
            )
        if self.signature.strip().endswith(";"):
            raise InterfaceError(
                f"chữ ký {self.signature!r} đã kèm dấu chấm phẩy. Engine không "
                "ghép cú pháp C; dấu kết thúc câu lệnh do khuôn của pack đặt."
            )
        if self.isr_safe and self.blocking:
            raise InterfaceError(
                f"{self.name!r}: vừa an-toàn-ngắt vừa CHẶN là mâu thuẫn. Một hàm "
                "chặn gọi trong ISR sẽ giữ ngắt mở quá hạn và làm trễ mọi thứ "
                "khác — nếu thật sự cần thì tách thành hai hàm."
            )

    @property
    def name(self) -> str:
        khop = _TEN_HAM.search(self.signature)
        return khop.group(1) if khop else self.signature.strip()

    def contract_text(self) -> str:
        """Hợp đồng gọi, viết thành một dòng người đọc được."""
        phan = [
            "gọi trong ngắt: ĐƯỢC" if self.isr_safe else "gọi trong ngắt: KHÔNG",
            "CHẶN" if self.blocking else "không chặn",
            "tái nhập được" if self.reentrant else "KHÔNG tái nhập",
        ]
        van_ban = " · ".join(phan)
        if self.precondition:
            van_ban += f" · trước khi gọi: {self.precondition}"
        return van_ban

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "purpose": self.purpose,
            "isr_safe": self.isr_safe,
            "blocking": self.blocking,
            "reentrant": self.reentrant,
            "precondition": self.precondition,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "FunctionContract":
        if not isinstance(d, dict):
            raise InterfaceError(f"hàm phải là ánh xạ, nhận {type(d)}")
        return cls(
            signature=str(d.get("signature", "")).strip().rstrip(";").strip(),
            purpose=str(d.get("purpose", "")),
            isr_safe=bool(d.get("isr_safe", False)),
            blocking=bool(d.get("blocking", False)),
            reentrant=bool(d.get("reentrant", False)),
            precondition=str(d.get("precondition", "")),
        )

    def render(self) -> str:
        dong = [f"  {self.signature}"]
        if self.purpose:
            dong.append(f"      {self.purpose}")
        dong.append(f"      {self.contract_text()}")
        return "\n".join(dong)


@dataclass
class InterfaceSpec:
    """Giao diện một module: nó hứa cung cấp những gì."""

    module_id: str
    purpose: str = ""
    functions: tuple[FunctionContract, ...] = ()
    includes: tuple[str, ...] = ()
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.module_id.strip():
            raise InterfaceError("giao diện không gắn với module nào")
        ten = [f.name for f in self.functions]
        trung = sorted({t for t in ten if ten.count(t) > 1})
        if trung:
            raise InterfaceError(
                f"{self.module_id}: khai hai lần các hàm {trung}. Trùng tên trong "
                "một tệp tiêu đề là lỗi liên kết, phát hiện muộn hơn nhiều."
            )

    @property
    def guard(self) -> str:
        """Tên macro chống nạp trùng, suy từ mã module."""
        return re.sub(r"[^A-Z0-9]", "_", self.module_id.upper()) + "_H"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module_id,
            "purpose": self.purpose,
            "includes": list(self.includes),
            "functions": [f.to_dict() for f in self.functions],
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "InterfaceSpec":
        if not isinstance(d, dict):
            raise InterfaceError("giao diện phải là ánh xạ khóa–giá trị")
        return cls(
            module_id=str(d.get("module", "")),
            purpose=str(d.get("purpose", "")),
            functions=tuple(
                FunctionContract.from_dict(x) for x in (d.get("functions") or [])
            ),
            includes=tuple(str(x) for x in (d.get("includes") or [])),
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
        )

    def gaps(self) -> list[str]:
        thieu: list[str] = []
        if not self.functions:
            thieu.append(
                "Giao diện trống — module không hứa gì thì module khác không dựa "
                "vào được, và sinh song song mất hết ý nghĩa."
            )
        for f in self.functions:
            if not f.purpose.strip():
                thieu.append(f"{f.name}: chưa nói hàm này làm gì")
        return thieu

    def render(self) -> str:
        dong = [f"Giao diện {self.module_id} — {len(self.functions)} hàm"]
        if self.purpose:
            dong += ["", self.purpose]
        dong.append("")
        dong += [f.render() for f in self.functions] or ["  (chưa có hàm nào)"]
        thieu = self.gaps()
        if thieu:
            dong += ["", "CÒN HỞ:"] + [f"  · {t}" for t in thieu]
        dong += [
            "",
            "Đây là HỢP ĐỒNG, chưa là mã. Sinh nó trước gỡ được ràng buộc thứ tự:",
            "hai thân module viết song song, mỗi bên chỉ trông vào lời hứa của bên kia.",
        ]
        return "\n".join(dong)


@dataclass
class InterfaceGenerator:
    """Dựng tệp tiêu đề từ khuôn của Platform Pack.

    Engine cấp dữ liệu, pack cấp khuôn — cùng ranh giới với khuôn ráp firmware.
    """

    manifest: Any

    def render(self, spec: InterfaceSpec) -> str:
        khuon = getattr(self.manifest, "interfaces", None)
        if khuon is None:
            raise InterfaceError(
                f"Pack {getattr(self.manifest, 'name', '?')!r} chưa khai khuôn "
                "'interfaces' trong pack.yaml. Tệp tiêu đề là mã C, và mã C "
                "thuộc về pack — engine không tự ghép cú pháp C."
            )
        van_ban = Path(khuon.template).read_text(encoding="utf-8")

        khai_bao: list[str] = []
        for f in spec.functions:
            if f.purpose:
                khai_bao.append(khuon.comment_line.replace("{comment}", f.purpose))
            khai_bao.append(khuon.comment_line.replace("{comment}", f.contract_text()))
            khai_bao.append(khuon.function_line.replace("{signature}", f.signature))
            khai_bao.append("")

        nap = [khuon.include_line.replace("{header}", h) for h in spec.includes]

        # Thay bằng ``replace`` chứ không bằng ``format``: khuôn là mã C và mã C
        # đầy dấu ngoặc nhọn, nên ``format`` sẽ vấp ngay khối lệnh đầu tiên.
        for cho_giu, gia_tri in (
            ("{guard}", spec.guard),
            ("{module}", spec.module_id),
            ("{purpose}", spec.purpose or spec.module_id),
            ("{status}", BANNER_DE_XUAT),
            ("{includes}", "\n".join(nap)),
            ("{declarations}", "\n".join(khai_bao).rstrip()),
        ):
            van_ban = van_ban.replace(cho_giu, gia_tri)
        return van_ban

    def write(self, spec: InterfaceSpec, firmware_dir: str | Path) -> Path:
        """Ghi tệp tiêu đề vào cây firmware để lớp K3 dùng được ngay.

        KHÔNG ghi đè: một tệp tiêu đề đã có thể là của module đã merge, và ghi
        đè nó bằng một bản đề xuất sẽ làm mọi module phụ thuộc dựa vào một hợp
        đồng chưa ai kiểm.
        """
        khuon = getattr(self.manifest, "interfaces", None)
        if khuon is None:
            raise InterfaceError("Pack chưa khai khuôn 'interfaces'.")
        thu_muc = Path(firmware_dir)
        thu_muc.mkdir(parents=True, exist_ok=True)
        duong_dan = thu_muc / khuon.output.replace("{module}", spec.module_id)
        if duong_dan.is_file():
            raise InterfaceError(
                f"{duong_dan} đã có. Agent KHÔNG ghi đè tệp tiêu đề: bản cũ có thể "
                "là của module đã merge, và mọi module phụ thuộc đang dựa vào nó.\n"
                "    Xem lại rồi tự xóa nếu thật sự muốn dựng lại."
            )
        duong_dan.write_text(self.render(spec), encoding="utf-8")
        return duong_dan


_LUOC_DO = """{
  "purpose": "<module này chịu trách nhiệm gì, một câu>",
  "includes": ["<tệp tiêu đề chuẩn cần nạp>"],
  "functions": [
    {
      "signature": "<khai báo hàm, KHÔNG có dấu chấm phẩy cuối>",
      "purpose": "<hàm này làm gì>",
      "isr_safe": false,
      "blocking": false,
      "reentrant": false,
      "precondition": "<điều người gọi phải bảo đảm trước khi gọi>"
    }
  ]
}"""


@dataclass
class LlmInterfaceDesigner:
    """Dựng hợp đồng gọi bằng mô hình nền, TRƯỚC khi sinh thân."""

    llm: Any
    budget: int = 2500

    def design(
        self,
        *,
        module_id: str,
        purpose: str = "",
        provides: Sequence[str] = (),
        uses: Sequence[str] = (),
        constraints: Any = None,
    ) -> InterfaceSpec:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        gioi_han = getattr(constraints, "limits", {}) or {}
        prompt = Prompt(
            system_instruction=(
                "Bạn thiết kế GIAO DIỆN của một module firmware, chưa viết thân. "
                "Với MỖI hàm, trả lời dứt khoát ba câu: gọi trong ngắt được "
                "không, có chặn không, tái nhập được không. Không để mặc định "
                "cho tiện — một hàm chặn gọi trong vòng điều khiển là một vòng "
                "sẽ trễ nhịp mà chẳng cổng nào báo. Chữ ký KHÔNG kèm dấu chấm "
                "phẩy: dấu kết câu do khuôn của nền tảng đặt."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Module: {module_id}\n"
                    + (f"Trách nhiệm: {purpose}\n" if purpose else "")
                    + (f"Phải cung cấp: {', '.join(provides)}\n" if provides else "")
                    + (f"Chiếm tài nguyên: {', '.join(uses)}\n" if uses else "")
                    + (
                        "Ràng buộc: "
                        + ", ".join(f"{k}={v}" for k, v in sorted(gioi_han.items()))
                        + "\n"
                        if gioi_han
                        else ""
                    )
                    + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                    f"```json\n{_LUOC_DO}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module=module_id,
            budget=self.budget + 800,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise InterfaceError(f"Không dựng được giao diện {module_id}: {exc}") from exc

        from eaa.options import _boc_json

        du_lieu = _boc_json(van_ban)
        return InterfaceSpec(
            module_id=module_id,
            purpose=str(du_lieu.get("purpose", "")) or purpose,
            functions=tuple(
                FunctionContract.from_dict(x) for x in (du_lieu.get("functions") or [])
            ),
            includes=tuple(str(x) for x in (du_lieu.get("includes") or [])),
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )
