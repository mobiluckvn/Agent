"""Rút chữ từ PDF — bọc ``pypdf``, thêm phần nói ra chỗ mình đọc không được.

EAA-AIS-05 §6.1, §4.1 bước 1 (trích văn bản từ trang người chọn); FR-ING-01.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-94.

Khoảng trống module này lấp
----------------------------

``eaa survey`` kiểm kê được **có những tệp gì** trong một kho hồ sơ nhưng không
mở được PDF. Tài liệu quy trình của một dự án nhúng gần như luôn ở dạng PDF, và
hồ sơ robot dùng kiểm thử sản phẩm này có đúng hai tệp như vậy.

Vì sao bọc ``pypdf`` chứ không tự bóc PDF
------------------------------------------

Bản đầu của module này tự bóc: giải nén luồng bằng ``zlib``, đọc bảng
``ToUnicode``, bám ma trận chữ. Nó chạy được, và nó **kém hơn hẳn**.

Đo trên chính tệp dùng để kiểm — ``BLKLab_Balancing_Robot_Tong_Quan.pdf``:

===================  ==========  ===============================
bộ rút               ký tự       chất lượng
===================  ==========  ===============================
tự bóc               1.884       rụng 40 glyph — mất dấu tiếng Việt
``pypdf``            2.765       đủ dấu
===================  ==========  ===============================

Chữ bản tự bóc trả về: *"Dự Bằng một nền tảng học tập tưởng kỹ sư"*.
Chữ ``pypdf`` trả về: *"Dự án Xe Robot Cân Bằng là một nền tảng học tập lý
tưởng dành cho sinh viên, kỹ sư"*.

Và ``pypdf`` vốn **đã nằm trong ``dependencies`` của ``pyproject.toml``** từ
đầu, khai đúng cho việc này (AIS §4.1). Tự viết lại một thứ đã khai là thêm mã
để nhận kết quả tệt hơn — nên bản tự bóc bị bỏ, không giữ làm phương án lùi.

Phần module này thêm vào, và vì sao nó đáng có
-----------------------------------------------

``pypdf`` trả về chuỗi. Nó không trả lời được câu quan trọng nhất khi đọc tài
liệu của người khác: **chỗ nào tôi đọc không được?** Module này thêm:

* Nhận ra **PDF quét ảnh** — không có luồng văn bản nào — và nói thẳng là cần
  OCR, thay vì trả về chuỗi rỗng để bên gọi tự hiểu nhầm thành "tài liệu trống".
* Gắn **mức tin cậy** theo bộ từ vựng chung (N-903).
* Nói rõ **bố cục không được dựng lại**: bảng biểu ra thành dòng rời.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "PdfError",
    "PdfPage",
    "PdfText",
    "extract_text",
    "MAX_BYTES",
]

#: Trần kích thước tệp. Một PDF lớn hơn thế gần như luôn là tài liệu quét ảnh —
#: thứ module này không đọc được — và mở nó chỉ tốn bộ nhớ.
MAX_BYTES = 80 * 1024 * 1024


class PdfError(Exception):
    """Không đọc được PDF."""


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str

    @property
    def empty(self) -> bool:
        return not self.text.strip()


@dataclass
class PdfText:
    """Chữ rút được, kèm những chỗ rút không ra."""

    path: str = ""
    pages: tuple[PdfPage, ...] = ()
    #: Số trang có trong tệp nhưng không có chữ nào — dấu hiệu trang quét ảnh.
    blank_pages: int = 0
    note: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def empty(self) -> bool:
        return not self.text.strip()

    @property
    def confidence_level(self) -> str:
        """SUY RA khi rút được; KHÔNG KIỂM ĐƯỢC khi rỗng.

        Không bao giờ ĐÃ KIỂM: bộ rút bỏ bố cục, và một bảng biểu ra thành các
        dòng rời có thể đọc sai quan hệ hàng–cột. Nó cho một bản đọc được,
        không cho một bản sao trung thành.
        """
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return KHONG_KIEM_DUOC if self.empty else SUY_RA

    def render(self, *, limit: int = 3000) -> str:
        from eaa.confidence import header

        dong = [f"Chữ rút từ {self.path or 'PDF'}", "", header(self.confidence_level), ""]
        if self.empty:
            dong += [
                "  Không rút được chữ nào.",
                "",
                "  Thường là PDF QUÉT ẢNH: chữ nằm trong hình, không phải trong "
                "luồng văn bản. Đọc nó cần OCR — một công cụ ngoài mà hệ này "
                "chưa có. Tôi báo rỗng thay vì trả về một chuỗi rác trông như chữ.",
            ]
            if self.note:
                dong += ["", f"  {self.note}"]
            return "\n".join(dong)

        dong.append(f"  {len(self.pages)} trang có chữ · {len(self.text)} ký tự")
        if self.blank_pages:
            dong.append(
                f"  ⚠ {self.blank_pages} trang KHÔNG có chữ nào — nhiều khả năng "
                "là trang quét ảnh; phần nội dung ấy tôi không đọc được."
            )
        dong += ["", "  Bố cục KHÔNG được dựng lại: bảng biểu ra thành dòng rời.", ""]
        dong.append(self.text if len(self.text) <= limit else self.text[:limit] + "\n…(cắt)")
        return "\n".join(dong)


def extract_text(path: str | Path, *, max_pages: int = 0) -> PdfText:
    """Rút chữ từ một tệp PDF. Không ném khi PDF khó — báo rỗng kèm lý do."""
    p = Path(path)
    if not p.is_file():
        raise PdfError(f"Không có tệp: {p}")
    if p.stat().st_size > MAX_BYTES:
        raise PdfError(
            f"{p.name} lớn hơn trần {MAX_BYTES // 1024 // 1024} MB. PDF lớn thế "
            "gần như luôn là tài liệu quét ảnh — thứ bộ rút này không đọc được."
        )
    if p.read_bytes()[:5] != b"%PDF-":
        raise PdfError(f"{p.name} không phải tệp PDF (thiếu chữ ký %PDF)")

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - phụ thuộc đã khai ở pyproject
        raise PdfError(
            "Thiếu pypdf — nó nằm trong dependencies của pyproject.toml. "
            'Cài lại: pip install -e ".[dev]"'
        ) from exc

    try:
        doc = PdfReader(str(p))
        so_trang = len(doc.pages)
    except Exception as exc:  # noqa: BLE001 - PDF hỏng không được làm sập lượt chạy
        return PdfText(path=str(p), note=f"pypdf không mở được tệp: {exc}")

    trang: list[PdfPage] = []
    trong = 0
    for i, t in enumerate(doc.pages, 1):
        if max_pages and i > max_pages:
            break
        try:
            chu = (t.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 - một trang hỏng không được bỏ cả tệp
            chu = ""
        if chu:
            trang.append(PdfPage(number=i, text=chu))
        else:
            trong += 1

    ra = PdfText(path=str(p), pages=tuple(trang), blank_pages=trong)
    if ra.empty:
        ra.note = (
            f"Mở được {so_trang} trang nhưng không trang nào có luồng văn bản — "
            "dấu hiệu của PDF quét ảnh."
        )
    return ra
