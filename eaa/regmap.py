"""Bản đồ thanh ghi máy đọc được — mô hình trung tính (GĐ1, A2).

Xem `docs/KE_HOACH_VUOT_LEN.md` §2 và `docs/SAI_LECH_THIET_KE.md` mục SL-176.

Khoảng trống module này lấp
----------------------------

Mỗi giá trị thanh ghi trong mã sinh ra mang một dòng ``// ref: <mã chunk>``, và
cổng phân tích tĩnh cưỡng chế dòng ấy phải có (TC-17). Nhưng nó chỉ kiểm **có
trích dẫn hay không** — nó không kiểm **trích dẫn ấy có đúng không**. Một mã
chunk hợp lệ dán lên một giá trị sai vẫn đi qua sạch.

Nhà sản xuất phát hành sẵn bảng thanh ghi ở dạng **máy đọc được**: tên thanh
ghi, tên trường bit, độ rộng, vị trí, giá trị sau reset, quyền đọc/ghi. Có nó
thì câu *"giá trị này có lọt vừa trường bit ấy không"* trả lời được bằng máy,
chứ không phải bằng cách đọc lại datasheet.

Ranh giới ba tầng — chỗ dễ sai nhất của module này
---------------------------------------------------

Bỏ bộ đọc của một định dạng do ARM hay Microchip đặt ra vào ``eaa/`` có phá quy
tắc số một không? **Không, nếu chia đúng chỗ.**

Ranh giới của kho này là **hằng số phần cứng**, không phải **định dạng tệp**:

* ``eaa/regmap.py`` — mô hình trung tính. Nó không biết cái tên nào tồn tại
  trên đời; mọi tên đều đến từ tệp.
* ``eaa/regmap_svd.py``, ``eaa/regmap_atdf.py`` — biết cách đọc một cây XML.
  Không biết trong cây ấy có gì.
* ``packs/<pack>/pack.yaml`` — khai định dạng và đường dẫn.
* ``projects/<dự án>/`` — giữ tệp thật của con chip dự án dùng.

Đúng cùng cách ``eaa/platform.py`` biết *gọi một toolchain* mà không biết tên
chương trình nào. TC-38 vẫn quét sạch.

Điều mô hình này CỐ Ý không mang
---------------------------------

Không có địa chỉ tuyệt đối, không có nhóm ngoại vi lồng nhau, không có mô tả
văn xuôi. Ba thứ ấy có trong tệp gốc và bộ đọc bỏ qua chúng, vì phép kiểm cần
đúng bốn câu: **tên có thật không · trường có thật không · giá trị lọt vừa
không · có được ghi không**. Mang thêm là mang thêm chỗ để lệch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "BitField",
    "Register",
    "RegisterMap",
    "RegmapError",
    "DINH_DANG",
    "nap_ban_do",
    "doc_mask",
]

#: Quyền truy cập, chuẩn hoá về ba giá trị. Chuỗi rỗng nghĩa là tệp không khai —
#: và *không khai* khác *khai là đọc-ghi*, nên nó không được quy về mặc định.
DOC_GHI = "read-write"
CHI_DOC = "read-only"
CHI_GHI = "write-only"


class RegmapError(Exception):
    """Không đọc được bản đồ thanh ghi."""


@dataclass(frozen=True)
class BitField:
    """Một trường bit trong thanh ghi."""

    name: str
    offset: int
    width: int
    access: str = ""

    @property
    def gia_tri_lon_nhat(self) -> int:
        return (1 << self.width) - 1

    def vua(self, gia_tri: int) -> bool:
        return 0 <= gia_tri <= self.gia_tri_lon_nhat

    def __str__(self) -> str:
        vi_tri = (
            f"bit {self.offset}"
            if self.width == 1
            else f"bit {self.offset + self.width - 1}:{self.offset}"
        )
        return f"{self.name} ({vi_tri}, rộng {self.width})"


@dataclass(frozen=True)
class Register:
    """Một thanh ghi, kèm các trường bit của nó."""

    name: str
    size_bits: int = 8
    reset_value: int | None = None
    access: str = ""
    peripheral: str = ""
    fields: tuple[BitField, ...] = ()

    @property
    def gia_tri_lon_nhat(self) -> int:
        return (1 << self.size_bits) - 1

    def vua(self, gia_tri: int) -> bool:
        return 0 <= gia_tri <= self.gia_tri_lon_nhat

    @property
    def ghi_duoc(self) -> bool:
        """Chưa khai quyền thì coi là GHI ĐƯỢC.

        Ngả về phía cho qua ở đây là có chủ ý: một tệp thiếu thuộc tính
        ``access`` mà làm cổng đỏ hàng loạt thì cổng ấy bị tắt trong buổi đầu
        tiên, và lúc ấy nó không chặn được gì nữa.
        """
        return self.access != CHI_DOC

    def truong(self, ten: str) -> BitField | None:
        muc_tieu = ten.upper()
        return next((f for f in self.fields if f.name.upper() == muc_tieu), None)


@dataclass(frozen=True)
class RegisterMap:
    """Bản đồ thanh ghi của một con chip."""

    device: str = ""
    nguon: str = ""
    registers: dict[str, Register] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.registers)

    def __len__(self) -> int:
        return len(self.registers)

    def get(self, ten: str) -> Register | None:
        """Tra theo tên, KHÔNG phân biệt hoa thường.

        Tệp của hãng và mã C không phải lúc nào cũng viết hoa giống nhau, và
        một phép tra phân biệt hoa thường sẽ báo *"không có thanh ghi này"* cho
        đúng thanh ghi đang có — dạng báo nhầm tệ nhất, vì nó nghe rất thuyết
        phục.
        """
        return self.registers.get(ten.upper())

    def ten(self) -> list[str]:
        return sorted(self.registers)


def doc_mask(mask: int) -> tuple[int, int]:
    """Mặt nạ bit → (vị trí, độ rộng). Trả (0, 0) khi mặt nạ rỗng.

    Định dạng của Microchip khai trường bằng MẶT NẠ chứ không bằng cặp
    vị trí–độ rộng. Mặt nạ ngắt quãng (ví dụ ``0b10100000``) là chuyện có thật
    với vài thanh ghi cấu hình; lúc ấy hàm này trả về khoảng BAO NGOÀI, và phép
    kiểm độ rộng sẽ nới hơn thực tế. Nới thì bỏ lọt, chặt thì báo nhầm — và ở
    một bộ kiểm mới, báo nhầm là cái giết nó.
    """
    if mask <= 0:
        return 0, 0
    vi_tri = (mask & -mask).bit_length() - 1
    do_rong = mask.bit_length() - vi_tri
    return vi_tri, do_rong


#: Định dạng → hàm đọc. Thêm một định dạng là thêm một dòng ở đây cộng một
#: module đọc; không sửa gì trong phần còn lại của engine.
DINH_DANG: dict[str, str] = {
    "svd": "eaa.regmap_svd",
    "atdf": "eaa.regmap_atdf",
}


def nap_ban_do(duong_dan: str | Path, dinh_dang: str) -> RegisterMap:
    """Nạp bản đồ từ một tệp, theo định dạng pack khai.

    Lỗi ở đây là lỗi **CẤU HÌNH**, không phải lỗi mã: tệp thiếu, định dạng lạ,
    XML hỏng — không bản vá nào của module sửa được. Chỗ gọi phải đánh dấu như
    vậy để orchestrator dừng thay vì đốt ba lượt gọi mô hình (bài học SL-133).
    """
    import importlib

    khoa = (dinh_dang or "").strip().lower()
    if khoa not in DINH_DANG:
        raise RegmapError(
            f"Định dạng bản đồ thanh ghi không nhận ra: {dinh_dang!r}. "
            f"Đang hỗ trợ: {', '.join(sorted(DINH_DANG))}."
        )
    p = Path(duong_dan)
    if not p.is_file():
        raise RegmapError(f"Không có tệp bản đồ thanh ghi: {p}")
    try:
        van_ban = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RegmapError(f"{p}: không đọc được — {exc}") from exc

    mo_dun = importlib.import_module(DINH_DANG[khoa])
    ban_do: RegisterMap = mo_dun.doc(van_ban, nguon=str(p))
    if not ban_do:
        raise RegmapError(
            f"{p}: đọc được nhưng KHÔNG có thanh ghi nào. Tệp đúng định dạng "
            f"{khoa!r} chứ? Một bản đồ rỗng lặng lẽ sẽ làm cổng regcheck im, "
            "và im thì trông y hệt như đã kiểm."
        )
    return ban_do


def tu_pack(pack: Any, goc_du_an: str | Path) -> RegisterMap | None:
    """Đọc khai báo ``regmap`` của Platform Pack; None khi pack không khai.

    None là đường chạy BÌNH THƯỜNG, không phải lỗi: dự án chưa có tệp bản đồ
    thì mọi thứ chạy y như trước khi có module này.
    """
    khai = getattr(pack, "regmap", None) if pack is not None else None
    if not isinstance(khai, dict) or not khai:
        return None
    duong_dan = str(khai.get("path") or "").strip()
    dinh_dang = str(khai.get("format") or "").strip()
    if not duong_dan or not dinh_dang:
        raise RegmapError(
            "Khai báo 'regmap' của pack phải có cả 'format' lẫn 'path'. "
            f"Đang có: {khai!r}"
        )
    p = Path(duong_dan)
    if not p.is_absolute():
        p = Path(goc_du_an) / p
    return nap_ban_do(p, dinh_dang)
