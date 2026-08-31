"""Mô hình tài liệu — một bản vẽ, nhiều định dạng xuất.

EAA-AIS-05 §8.5 (kho phẩm xuất); EAA-SDD-03 §5. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-105.

Vì sao có lớp trung gian này
-----------------------------

Yêu cầu là xuất URD/SRS/SDD ra ``.docx``, ``.xlsx``, ``.pptx`` và ``.pdf``.
Cách làm hiển nhiên — mỗi định dạng một hàm sinh, đọc thẳng dữ liệu dự án — dẫn
tới bốn bản sao của cùng một logic "SRS gồm những mục gì". Sửa một mục là sửa
bốn chỗ, và chỗ thứ tư sẽ bị quên.

Nên ở giữa có một mô hình **không biết gì về định dạng**: một tài liệu là một
dãy khối (:class:`Heading`, :class:`Para`, :class:`Table`…). Phần dựng nội dung
sinh ra mô hình ấy một lần; phần xuất dịch nó sang từng định dạng.

Mô hình cố ý NGHÈO
-------------------

Không có màu chữ, không có căn lề, không có font. Chỉ có cấu trúc: đây là tiêu
đề mức 2, đây là một bảng có tiêu đề cột, đây là một ghi chú.

Đó là một lựa chọn, không phải một chỗ chưa làm. Một mô hình đủ giàu để mô tả
mọi thứ Word làm được thì chính nó trở thành một định dạng tài liệu — và lúc ấy
dịch sang PowerPoint (nơi không có khái niệm "lề trang") lại phải bỏ gần hết.
Nghèo thì dịch sang đâu cũng được.

:class:`Note` và vì sao nó là một khối riêng
---------------------------------------------

Tài liệu thiết kế do máy dựng luôn có chỗ **dữ liệu chưa có**. Cách tệ nhất là
để trống — một mục trống trong SRS đọc như "mục này không cần", trong khi thật
ra là "chưa ai điền". :class:`Note` mang mức tin cậy theo bộ từ vựng N-903 và
được xuất ra **nhìn thấy được** ở mọi định dạng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

__all__ = [
    "Block",
    "Heading",
    "Para",
    "Bullets",
    "Table",
    "Code",
    "Note",
    "PageBreak",
    "Doc",
]


class Block:
    """Một khối nội dung. Lớp cha rỗng — để bộ xuất so kiểu."""


@dataclass(frozen=True)
class Heading(Block):
    text: str
    level: int = 1


@dataclass(frozen=True)
class Para(Block):
    text: str


@dataclass(frozen=True)
class Bullets(Block):
    items: tuple[str, ...] = ()
    numbered: bool = False


@dataclass(frozen=True)
class Table(Block):
    """Bảng. ``header`` rỗng nghĩa là bảng không có hàng tiêu đề."""

    header: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    caption: str = ""

    @property
    def cols(self) -> int:
        return max([len(self.header), *(len(r) for r in self.rows)] or [0])


@dataclass(frozen=True)
class Code(Block):
    text: str
    language: str = ""


@dataclass(frozen=True)
class Note(Block):
    """Chỗ dữ liệu chưa có, hoặc một khẳng định cần gắn mức tin cậy.

    ``level`` dùng bộ từ vựng của ``eaa/confidence.py``. Để rỗng thì khối này
    là một ghi chú thường.
    """

    text: str
    level: str = ""


@dataclass(frozen=True)
class PageBreak(Block):
    pass


@dataclass
class Doc:
    """Một tài liệu: siêu dữ liệu + dãy khối."""

    title: str = ""
    subtitle: str = ""
    #: Loại tài liệu (``urd``, ``srs``…) — bộ xuất dùng để đặt tên tệp.
    kind: str = ""
    project: str = ""
    author: str = ""
    #: Mốc thời gian dựng. Truyền vào chứ không tự lấy: một tài liệu dựng lại
    #: từ cùng dữ liệu phải ra cùng nội dung, nếu không thì không so được hai
    #: bản với nhau.
    created_at: str = ""
    blocks: list[Block] = field(default_factory=list)

    def add(self, *blocks: Block) -> "Doc":
        self.blocks.extend(blocks)
        return self

    def heading(self, text: str, level: int = 1) -> "Doc":
        return self.add(Heading(text, level))

    def para(self, text: str) -> "Doc":
        return self.add(Para(text))

    def bullets(self, items: Iterable[str], *, numbered: bool = False) -> "Doc":
        ds = tuple(str(i) for i in items if str(i).strip())
        return self.add(Bullets(ds, numbered)) if ds else self

    def table(self, header: Sequence[str], rows: Iterable[Sequence[str]],
              *, caption: str = "") -> "Doc":
        ds = tuple(tuple(str(c) for c in r) for r in rows)
        return self.add(Table(tuple(header), ds, caption))

    def note(self, text: str, level: str = "") -> "Doc":
        return self.add(Note(text, level))

    @property
    def headings(self) -> list[Heading]:
        return [b for b in self.blocks if isinstance(b, Heading)]

    def render_text(self) -> str:
        """Bản chữ thuần — dùng để xem nhanh và để so hai lần dựng."""
        dong: list[str] = []
        if self.title:
            dong += [self.title, "=" * len(self.title), ""]
        if self.subtitle:
            dong += [self.subtitle, ""]
        for b in self.blocks:
            if isinstance(b, Heading):
                dong += ["", f"{'#' * b.level} {b.text}", ""]
            elif isinstance(b, Para):
                dong += [b.text, ""]
            elif isinstance(b, Bullets):
                for i, x in enumerate(b.items, 1):
                    dong.append(f"  {i}. {x}" if b.numbered else f"  · {x}")
                dong.append("")
            elif isinstance(b, Table):
                if b.caption:
                    dong.append(f"Bảng: {b.caption}")
                if b.header:
                    dong.append("  | " + " | ".join(b.header) + " |")
                    dong.append("  |" + "---|" * len(b.header))
                for r in b.rows:
                    dong.append("  | " + " | ".join(r) + " |")
                dong.append("")
            elif isinstance(b, Code):
                dong += ["```" + b.language, b.text, "```", ""]
            elif isinstance(b, Note):
                nhan = f"[{b.level}] " if b.level else ""
                dong += [f"> {nhan}{b.text}", ""]
            elif isinstance(b, PageBreak):
                dong += ["---", ""]
        return "\n".join(dong).strip() + "\n"

    def render_markdown(self) -> str:
        """Markdown — định dạng xuất rẻ nhất, và là bản để đọc lúc gỡ rối."""
        return self.render_text()
