"""Vòng tự đánh giá đủ thông tin — RIC và Readiness Check.

EAA-AIS-05 §6.2, quy trình P7; FR-GAP-01/02/03; TC-24, TC-26.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-14.

Trước khi mở vòng sinh mã cho một module, Agent tự trả lời câu hỏi "mình đã
biết đủ chưa?" một cách có cấu trúc, thay vì cứ sinh mã rồi để lỗi lộ ra.

Bốn bước của quy trình P7:

1.  **Lập bảng kiểm thông tin cần (RIC)** — sinh tự động từ Knowledge Graph và
    Task Spec: module này đụng ngoại vi nào, cần thanh ghi nào, chân nào, tham
    số nào, ràng buộc nào.
2.  **Đối chiếu bộ nhớ** — mỗi mục nhận một trong ba trạng thái: CÓ (kèm con
    trỏ nguồn), THIẾU, hoặc MÂU THUẪN.
3.  **Tìm kiếm bổ sung leo thang ba bậc** cho mục THIẾU.
4.  **Readiness Check** — 100% mục Must có nguồn thì vòng sinh mã mới mở.

Hai điều tuyệt đối, và chúng là lý do module này tồn tại:

* **Cấm đoán.** Agent không được bịa giá trị thanh ghi hay tham số điện để lấp
  chỗ trống. Thiếu là thiếu. Một giá trị đoán trông y hệt một giá trị tra được,
  và nó sẽ đi qua mọi cổng kiểm chứng phía sau — vì cổng nào cũng chỉ kiểm
  được rằng mã *chạy*, không kiểm được rằng con số *đúng*.
* **Mâu thuẫn thì người phân xử.** Hai nguồn cho hai giá trị khác nhau thì máy
  DỪNG. Nó không được chọn bản mới hơn, bản dài hơn, hay bản của nguồn có vẻ
  chính thống hơn — độ mới không phải bằng chứng đúng (AIS §8.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

__all__ = [
    "ReadinessError",
    "NotReady",
    "ItemStatus",
    "Priority",
    "RicItem",
    "Ric",
    "SearchTier",
    "ReadinessChecker",
    "SEARCH_TIERS",
]


class ItemStatus:
    """Ba trạng thái của một mục trong bảng kiểm — AIS §6.2 bước 2."""

    PRESENT = "CÓ"
    MISSING = "THIẾU"
    CONFLICT = "MÂU THUẪN"


class Priority:
    MUST = "Must"
    SHOULD = "Should"


class ReadinessError(Exception):
    """Không lập được bảng kiểm."""


class NotReady(Exception):
    """Readiness Check chặn vòng sinh mã — FR-GAP-03.

    Mang theo bảng kiểm để nơi gọi in ra được đích danh cái gì thiếu, chứ không
    chỉ báo "chưa sẵn sàng".
    """

    def __init__(self, message: str, ric: "Ric") -> None:
        super().__init__(message)
        self.ric = ric


@dataclass(frozen=True)
class SearchTier:
    """Một bậc của thang tìm kiếm bổ sung — AIS §6.2 bước 3."""

    level: int
    name: str
    action: str


#: Ba bậc leo thang. Thứ tự có ý nghĩa: bậc rẻ và đáng tin trước, bậc đắt và
#: cần kiểm chứng nhiều nhất sau cùng.
SEARCH_TIERS: tuple[SearchTier, ...] = (
    SearchTier(
        1,
        "tài liệu người dùng đã cung cấp",
        "Tìm trong tài liệu đã nạp nhưng chưa trích xuất hết — rẻ nhất và đáng "
        "tin nhất vì nguồn đã được người chọn.",
    ),
    SearchTier(
        2,
        "hỏi người dùng đích danh",
        "Nêu ĐÍCH DANH thứ còn thiếu, không hỏi chung chung. "
        "Ví dụ: 'cần trang tài liệu mô tả thanh ghi X ở chế độ Y'.",
    ),
    SearchTier(
        3,
        "tra nguồn cho phép trên web",
        "Chỉ trong danh sách nguồn cho phép (trang chính thức của nhà sản "
        "xuất). Kết quả dù từ bậc nào cũng chỉ là đề xuất và phải qua gate.",
    ),
)

#: Mỗi mục chỉ được tìm tối đa hai vòng rồi chuyển người (AIS §6.2 bước 4).
MAX_SEARCH_ROUNDS = 2

_SO = r"0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+"

#: Giá trị nêu trong bảng thanh ghi–bit: ``| TÊN_THANH_GHI | 7:0 | 12 | …``.
_GIA_TRI_BANG = re.compile(
    rf"\|\s*(?P<reg>[A-Z][A-Z0-9_]{{2,}})\s*\|[^|]*\|\s*(?P<val>{_SO})\s*\|"
)

#: Giá trị nêu trong phần văn xuôi: ``→ TÊN_THANH_GHI = 12``. Cần cả hai vì
#: bảng thường viết ký hiệu (``N``) còn con số cụ thể nằm ở dòng công thức bên
#: dưới — chỉ dò bảng thì bỏ sót đúng những mâu thuẫn về giá trị thực.
_GIA_TRI_VAN_XUOI = re.compile(
    rf"\b(?P<reg>[A-Z][A-Z0-9_]{{2,}})\s*(?:=|→|:)\s*(?P<val>{_SO})\b"
)


def _chuan_hoa_so(van_ban: str) -> int | None:
    """Quy mọi cách viết số về cùng một giá trị.

    ``0b00``, ``0x00`` và ``0`` là CÙNG một giá trị. So sánh chuỗi thô sẽ dựng
    cờ mâu thuẫn cho ba cách viết của số không — và một cơ chế báo động giả
    thì người ta học cách phớt lờ, làm hỏng luôn những lần báo đúng.
    """
    try:
        return int(van_ban, 0)
    except ValueError:  # pragma: no cover - regex đã lọc dạng số
        return None


@dataclass
class RicItem:
    """Một mục trong Bảng kiểm thông tin cần."""

    key: str
    kind: str            # register · pin · parameter · constraint
    priority: str = Priority.MUST
    status: str = ItemStatus.MISSING
    #: Con trỏ nguồn khi trạng thái là CÓ; danh sách nguồn khi MÂU THUẪN.
    sources: tuple[str, ...] = ()
    detail: str = ""
    search_rounds: int = 0

    @property
    def blocking(self) -> bool:
        """Mục này có chặn vòng sinh mã không.

        Mâu thuẫn chặn ở MỌI mức ưu tiên, kể cả Should: một mục Should mà hai
        nguồn nói khác nhau nghĩa là kho tri thức đang tự mâu thuẫn, và đó là
        vấn đề của cả kho chứ không riêng mục ấy.
        """
        if self.status == ItemStatus.CONFLICT:
            return True
        return self.status == ItemStatus.MISSING and self.priority == Priority.MUST

    def __str__(self) -> str:
        nhan = f"[{self.status}] {self.kind} {self.key}"
        if self.sources:
            nhan += f" ← {', '.join(self.sources)}"
        if self.detail:
            nhan += f" — {self.detail}"
        return nhan


@dataclass
class Ric:
    """Bảng kiểm thông tin cần của một module."""

    module_id: str
    items: list[RicItem] = field(default_factory=list)

    def by_status(self, status: str) -> list[RicItem]:
        return [i for i in self.items if i.status == status]

    @property
    def missing_must(self) -> list[RicItem]:
        return [
            i
            for i in self.items
            if i.status == ItemStatus.MISSING and i.priority == Priority.MUST
        ]

    @property
    def conflicts(self) -> list[RicItem]:
        return self.by_status(ItemStatus.CONFLICT)

    @property
    def ready(self) -> bool:
        return not any(i.blocking for i in self.items)

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Do MỤC YẾU NHẤT quyết định, không do đa số. Một bảng kiểm có mười mục
        CÓ và một mục MÂU THUẪN thì cả bảng chỉ chắc tới mức mục mâu thuẫn ấy
        — vì module sắp sinh ra sẽ dùng đúng giá trị đang tranh chấp.
        """
        from eaa.confidence import DA_KIEM, GIA_DINH, KHONG_KIEM_DUOC, SUY_RA

        if not self.items:
            return SUY_RA
        if self.conflicts:
            return KHONG_KIEM_DUOC
        if self.missing_must:
            return GIA_DINH
        if any(i.status == ItemStatus.MISSING for i in self.items):
            return SUY_RA
        return DA_KIEM

    def render(self) -> str:
        dong = [f"Bảng kiểm thông tin cần — {self.module_id}", ""]
        if not self.items:
            dong.append("  (module không đụng tài nguyên nào cần tra tài liệu)")
            return "\n".join(dong)

        for muc in sorted(self.items, key=lambda i: (i.status != ItemStatus.CONFLICT, i.status, i.key)):
            danh_dau = "✗" if muc.blocking else ("✓" if muc.status == ItemStatus.PRESENT else "·")
            dong.append(f"  {danh_dau} {muc}")

        dong.append("")
        dong.append(
            f"CÓ {len(self.by_status(ItemStatus.PRESENT))} · "
            f"THIẾU {len(self.by_status(ItemStatus.MISSING))} · "
            f"MÂU THUẪN {len(self.conflicts)}"
        )
        return "\n".join(dong)

    def guidance(self) -> str:
        """Hướng dẫn cụ thể cho từng mục còn chặn."""
        dong: list[str] = []

        for muc in self.conflicts:
            dong.append(
                f"MÂU THUẪN — {muc.kind} {muc.key}: {muc.detail}\n"
                f"  Nguồn: {', '.join(muc.sources)}\n"
                "  Máy KHÔNG tự chọn. Kỹ sư xem cả hai bản kèm xuất xứ rồi phân "
                "xử tại G2; bản thua chuyển deprecated kèm lý do (AIS §8.2)."
            )

        for muc in self.missing_must:
            dong.append(
                f"THIẾU — {muc.kind} {muc.key}"
                + (f": {muc.detail}" if muc.detail else "")
            )
            for bac in SEARCH_TIERS:
                dong.append(f"  Bậc {bac.level} ({bac.name}): {bac.action}")
            if muc.search_rounds >= MAX_SEARCH_ROUNDS:
                dong.append(
                    f"  Đã tìm {muc.search_rounds} vòng — chuyển kỹ sư xử lý, "
                    "không tìm tiếp."
                )
        return "\n\n".join(dong)


class ReadinessChecker:
    """Lập bảng kiểm và chấm điều kiện mở vòng sinh mã."""

    def __init__(self, *, kb: Any, graph: Any) -> None:
        self.kb = kb
        self.graph = graph

    # ----------------------------------------------------------------------

    def build_ric(
        self, module_id: str, *, uses: Sequence[str] = (), extra: Iterable[RicItem] = ()
    ) -> Ric:
        """Bước 1–2: lập bảng kiểm rồi đối chiếu với bộ nhớ hệ thống."""
        if not self.graph.graph.has_node(module_id):
            self.graph.add_module(module_id, uses=uses)

        muc: list[RicItem] = []
        muc.extend(self._muc_thanh_ghi(module_id))
        muc.extend(self._muc_chan(module_id))
        muc.extend(self._muc_tai_nguyen(module_id))
        muc.extend(extra)
        return Ric(module_id=module_id, items=muc)

    def check(
        self, module_id: str, *, uses: Sequence[str] = (), ric: Ric | None = None
    ) -> Ric:
        """Bước 4: Readiness Check. Ném :class:`NotReady` nếu chưa đủ điều kiện."""
        ric = ric or self.build_ric(module_id, uses=uses)
        if ric.ready:
            return ric

        ly_do: list[str] = []
        if ric.conflicts:
            ly_do.append(
                f"{len(ric.conflicts)} mục MÂU THUẪN cần người phân xử: "
                + ", ".join(i.key for i in ric.conflicts)
            )
        if ric.missing_must:
            ly_do.append(
                f"{len(ric.missing_must)} mục Must còn THIẾU: "
                + ", ".join(i.key for i in ric.missing_must)
            )

        raise NotReady(
            f"Chưa đủ thông tin để sinh mã module {module_id!r}. "
            + "; ".join(ly_do)
            + ".\nVòng sinh mã KHÔNG mở: Agent bị cấm đoán giá trị thanh ghi "
            "hay tham số điện để lấp chỗ trống (FR-GAP-03).\n\n"
            + ric.render()
            + "\n\n"
            + ric.guidance()
            + (
                "\n\nAgent ĐI TÌM được ba bậc này thay vì để bạn tự làm:\n"
                f"    eaa resolve {module_id}            # bậc 1: lục tài liệu đã nạp\n"
                f"    eaa resolve {module_id} --ask      # bậc 2: hỏi bạn đích danh\n"
                f"    eaa resolve {module_id} --ask --web  # bậc 3: tra nguồn cho phép"
            ),
            ric,
        )

    # ----------------------------------------------------------------------
    # Từng loại mục
    # ----------------------------------------------------------------------

    def _muc_thanh_ghi(self, module_id: str) -> list[RicItem]:
        """Mỗi thanh ghi module phải cấu hình là một mục Must."""
        ket_qua: list[RicItem] = []
        for reg in self.graph.registers_for(module_id):
            chunks = self.kb.datasheets.by_register(reg)
            if not chunks:
                ket_qua.append(
                    RicItem(
                        key=reg,
                        kind="thanh ghi",
                        status=ItemStatus.MISSING,
                        detail="không có trích đoạn tài liệu nào đã duyệt mô tả thanh ghi này",
                    )
                )
                continue

            mau_thuan = self._tim_mau_thuan(reg, chunks)
            if mau_thuan:
                ket_qua.append(
                    RicItem(
                        key=reg,
                        kind="thanh ghi",
                        status=ItemStatus.CONFLICT,
                        sources=tuple(c.id for c in chunks),
                        detail=mau_thuan,
                    )
                )
                continue

            ket_qua.append(
                RicItem(
                    key=reg,
                    kind="thanh ghi",
                    status=ItemStatus.PRESENT,
                    sources=tuple(c.id for c in chunks),
                )
            )
        return ket_qua

    def _muc_chan(self, module_id: str) -> list[RicItem]:
        """Chân phải có trong sơ đồ nối dây — nguồn là hồ sơ phần cứng."""
        so_do = self.kb.hardware.pin_map
        return [
            RicItem(
                key=chan,
                kind="chân",
                status=ItemStatus.PRESENT if chan in so_do else ItemStatus.MISSING,
                sources=("hardware_profile.yaml",) if chan in so_do else (),
                detail="" if chan in so_do else "không có trong sơ đồ nối dây",
            )
            for chan in self.graph.pins_for(module_id)
        ]

    def _muc_tai_nguyen(self, module_id: str) -> list[RicItem]:
        """Tài nguyên module khai báo dùng phải tồn tại trong hồ sơ phần cứng."""
        ket_qua: list[RicItem] = []
        for res in self.graph.resources_of(module_id):
            loai = self.graph.kind_of(res)
            ket_qua.append(
                RicItem(
                    key=res,
                    kind="tài nguyên",
                    status=(
                        ItemStatus.MISSING if loai == "unknown" else ItemStatus.PRESENT
                    ),
                    sources=() if loai == "unknown" else ("hardware_profile.yaml",),
                    detail=(
                        "khai báo dùng nhưng hồ sơ phần cứng không có tài nguyên này"
                        if loai == "unknown"
                        else ""
                    ),
                )
            )
        return ket_qua

    @staticmethod
    def _tim_mau_thuan(register: str, chunks: Sequence[Any]) -> str:
        """Hai chunk cùng active cho hai giá trị khác nhau của một thanh ghi — TC-26.

        Dò trên bảng thanh ghi–bit đã chưng cất: lấy các giá trị gán cho thanh
        ghi trong mỗi chunk rồi so tập hợp. Cố ý chỉ so những gì có cấu trúc rõ
        ràng — thà bỏ sót một mâu thuẫn tinh vi còn hơn dựng cờ báo động giả
        khiến người ta học cách phớt lờ nó.
        """
        if len(chunks) < 2:
            return ""

        muc_tieu = register.upper()
        theo_chunk: dict[str, set[int]] = {}
        for chunk in chunks:
            gia_tri: set[int] = set()
            for mau in (_GIA_TRI_BANG, _GIA_TRI_VAN_XUOI):
                for m in mau.finditer(chunk.body):
                    if m.group("reg").upper() != muc_tieu:
                        continue
                    so = _chuan_hoa_so(m.group("val"))
                    if so is not None:
                        gia_tri.add(so)
            if gia_tri:
                theo_chunk[chunk.id] = gia_tri

        if len(theo_chunk) < 2:
            return ""

        tat_ca = set().union(*theo_chunk.values())
        if len(tat_ca) <= 1:
            return ""

        mo_ta = "; ".join(
            f"{cid} nói {sorted(v)}" for cid, v in sorted(theo_chunk.items())
        )
        return f"hai nguồn cho hai giá trị khác nhau ({mo_ta})"
