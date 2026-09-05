"""Đọc định dạng ATDF về mô hình trung tính của `eaa/regmap.py`.

Cùng ranh giới với `eaa/regmap_svd.py`: module này biết đi trong một cây XML,
không biết trong cây ấy có tên gì.

Khác SVD ở đúng một chỗ, và chỗ ấy quan trọng
----------------------------------------------

SVD khai trường bit bằng cặp **vị trí–độ rộng**. ATDF khai bằng **mặt nạ**::

    <bitfield name="..." mask="0xF0" .../>

Nên bộ đọc này phải suy vị trí và độ rộng ra từ mặt nạ — việc mà
:func:`eaa.regmap.doc_mask` làm, và docstring của hàm ấy nói rõ nó xử lý mặt nạ
ngắt quãng theo hướng NỚI chứ không chặt: nới thì bỏ lọt, chặt thì báo nhầm, và
ở một bộ kiểm mới thì báo nhầm là cái giết nó.

Quyền truy cập cũng khai khác: thuộc tính ``rw`` nhận ``R``, ``W``, hoặc ``RW``.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from eaa.regmap import (
    CHI_DOC,
    CHI_GHI,
    DOC_GHI,
    BitField,
    Register,
    RegisterMap,
    RegmapError,
    doc_mask,
)

__all__ = ["doc"]

#: Thuộc tính `rw` của ATDF → cách nói của mô hình trung tính. Không khai thì
#: để RỖNG, vì *không khai* khác *khai là đọc-ghi*.
_QUYEN = {"R": CHI_DOC, "W": CHI_GHI, "RW": DOC_GHI}


def _so(van_ban: str | None, mac_dinh: int | None = None) -> int | None:
    if not van_ban:
        return mac_dinh
    try:
        return int(van_ban.strip(), 0)
    except ValueError:
        return mac_dinh


def doc(van_ban: str, *, nguon: str = "") -> RegisterMap:
    """Cây ATDF → RegisterMap. Ném RegmapError khi XML không phân tích nổi."""
    try:
        goc = ET.fromstring(van_ban)
    except ET.ParseError as exc:
        raise RegmapError(f"{nguon or 'ATDF'}: XML hỏng — {exc}") from exc

    thanh_ghi: dict[str, Register] = {}
    for mo_dun in goc.iter("module"):
        ten_nv = mo_dun.get("name", "")
        for r in mo_dun.iter("register"):
            ten = r.get("name", "").strip()
            if not ten:
                continue

            truong: list[BitField] = []
            for bf in r.iter("bitfield"):
                ten_bf = bf.get("name", "").strip()
                mask = _so(bf.get("mask"))
                if not ten_bf or mask is None:
                    continue
                vi_tri, do_rong = doc_mask(mask)
                if do_rong <= 0:
                    continue
                truong.append(
                    BitField(
                        name=ten_bf,
                        offset=vi_tri,
                        width=do_rong,
                        access=_QUYEN.get((bf.get("rw") or "").strip().upper(), ""),
                    )
                )

            # `size` của ATDF tính bằng BYTE; mô hình trung tính tính bằng BIT.
            # Nhầm đơn vị ở đây làm mọi phép kiểm độ rộng lệch tám lần, và nó
            # lệch theo hướng NỚI — tức là im lặng bỏ lọt.
            so_byte = _so(r.get("size"), 1) or 1
            thanh_ghi[ten.upper()] = Register(
                name=ten,
                size_bits=so_byte * 8,
                reset_value=_so(r.get("initval")),
                access=_QUYEN.get((r.get("rw") or "").strip().upper(), ""),
                peripheral=ten_nv,
                fields=tuple(truong),
            )

    thiet_bi = next((d.get("name", "") for d in goc.iter("device")), "")
    return RegisterMap(device=thiet_bi, nguon=nguon, registers=thanh_ghi)
