"""Đọc định dạng CMSIS-SVD về mô hình trung tính của `eaa/regmap.py`.

Module này biết cách đi trong một cây XML. Nó **không** biết trong cây ấy có
tên gì — mọi tên đều lấy nguyên từ tệp, và không có một danh sách tên nào được
gõ vào đây. Xem docstring của `eaa/regmap.py` để biết vì sao chia như thế mà
vẫn giữ được ranh giới ba tầng.

Ba cách khai trường bit, và tệp thật dùng cả ba
------------------------------------------------

Chuẩn cho phép khai vị trí–độ rộng của một trường theo ba lối, và các nhà sản
xuất dùng lẫn lộn cả ba trong cùng một tệp:

1. ``<bitOffset>`` + ``<bitWidth>``;
2. ``<lsb>`` + ``<msb>``;
3. ``<bitRange>[msb:lsb]</bitRange>``.

Đọc thiếu một lối là bỏ trống một phần bản đồ **mà không báo gì** — và một bản
đồ thiếu chỗ thì cổng kiểm sẽ im đúng ở chỗ nó cần nói. Nên cả ba đều được đọc,
và có bài kiểm cho từng lối.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from eaa.regmap import BitField, Register, RegisterMap, RegmapError

__all__ = ["doc"]

_BIT_RANGE = re.compile(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]")


def _so(van_ban: str | None, mac_dinh: int | None = None) -> int | None:
    """Đọc một số của SVD: thập phân, ``0x…``, ``#…`` nhị phân, hậu tố ``UL``."""
    if van_ban is None:
        return mac_dinh
    s = van_ban.strip().rstrip("uUlL")
    if not s:
        return mac_dinh
    try:
        if s.startswith("#"):
            return int(s[1:].replace("x", "0"), 2)
        return int(s, 0)
    except ValueError:
        return mac_dinh


def _chu(nut: ET.Element, ten: str) -> str:
    con = nut.find(ten)
    return (con.text or "").strip() if con is not None and con.text else ""


def _truong(nut: ET.Element) -> BitField | None:
    ten = _chu(nut, "name")
    if not ten:
        return None

    vi_tri = _so(_chu(nut, "bitOffset") or None)
    do_rong = _so(_chu(nut, "bitWidth") or None)

    if vi_tri is None or do_rong is None:
        lsb, msb = _so(_chu(nut, "lsb") or None), _so(_chu(nut, "msb") or None)
        if lsb is not None and msb is not None:
            vi_tri, do_rong = lsb, msb - lsb + 1

    if vi_tri is None or do_rong is None:
        khop = _BIT_RANGE.search(_chu(nut, "bitRange"))
        if khop:
            msb, lsb = int(khop.group(1)), int(khop.group(2))
            vi_tri, do_rong = lsb, msb - lsb + 1

    if vi_tri is None or do_rong is None or do_rong <= 0:
        return None
    return BitField(
        name=ten, offset=vi_tri, width=do_rong, access=_chu(nut, "access")
    )


def doc(van_ban: str, *, nguon: str = "") -> RegisterMap:
    """Cây SVD → RegisterMap. Ném RegmapError khi XML không phân tích nổi."""
    try:
        goc = ET.fromstring(van_ban)
    except ET.ParseError as exc:
        raise RegmapError(f"{nguon or 'SVD'}: XML hỏng — {exc}") from exc

    thanh_ghi: dict[str, Register] = {}
    for ngoai_vi in goc.iter("peripheral"):
        ten_nv = _chu(ngoai_vi, "name")
        # `iter` chứ không `findall`: chuẩn cho phép lồng `<cluster>` giữa
        # `<registers>` và `<register>`, và một tệp dùng cluster sẽ mất sạch
        # phần lồng nếu chỉ tìm con trực tiếp.
        for r in ngoai_vi.iter("register"):
            ten = _chu(r, "name")
            if not ten:
                continue
            truong = tuple(
                t for t in (_truong(f) for f in r.iter("field")) if t is not None
            )
            thanh_ghi[ten.upper()] = Register(
                name=ten,
                size_bits=_so(_chu(r, "size") or None, 8) or 8,
                reset_value=_so(_chu(r, "resetValue") or None),
                access=_chu(r, "access"),
                peripheral=ten_nv,
                fields=truong,
            )
    return RegisterMap(device=_chu(goc, "name"), nguon=nguon, registers=thanh_ghi)
