"""Đầu ra MÁY ĐỌC ĐƯỢC cho các lệnh CHỈ ĐỌC — nền móng mảng IDE (E1, SL-182).

Xem `docs/EAA_Backlog_Tien_hoa.xlsx` việc E1.

Vì sao module này là việc đầu tiên của cả mảng IDE
---------------------------------------------------

CLI có 103 lệnh và 0 lệnh thiếu dòng trợ giúp — mặt người dùng đã kín. Nhưng
nó có **0 lệnh nào cho đầu ra máy đọc được**, và một extension biên tập không
đọc được văn xuôi tiếng Việt. Bảy trong tám việc của mảng IDE chờ đúng chỗ này.

Luật số một: CHỈ lệnh chỉ đọc
-----------------------------

`--json` chỉ gắn cho lệnh **không đổi trạng thái gì**. Lệnh ghi vẫn đi đúng
đường cũ.

Đây không phải sự cẩn thận thừa. Một `--json` cho lệnh ghi *"cho tiện tự động
hoá"* chính là **con đường thứ hai dẫn tới merge** mà bất biến số một của dự án
cấm (TC-01, TC-02): lúc ấy có hai chỗ trong mã cùng có quyền đổi trạng thái, và
chỉ một trong hai được canh. Bài kiểm TC-148 canh cả hai chiều — lệnh chỉ đọc
phải CÓ `--json`, lệnh ghi phải KHÔNG.

Luật số hai: mức tin cậy phải sống sót qua JSON
------------------------------------------------

23 lớp kết luận của hệ mang một trong bốn mức ĐÃ KIỂM / SUY RA / GIẢ ĐỊNH /
KHÔNG KIỂM ĐƯỢC (TC-63). Nếu đầu ra JSON làm phẳng chúng thành chuỗi, thì lớp
IDE đọc nó sẽ hiện một con số trần — và người nhìn màn hình mất đúng thứ
`confidence.py` sinh ra để giữ.

Nên giá trị mang mức tin cậy đi qua :func:`muc`, thành một đối tượng có trường
``muc`` riêng, không phải một câu đã trộn sẵn.

Luật số ba: lược đồ là HỢP ĐỒNG
---------------------------------

``SCHEMA`` là số phiên bản. Đổi hình dạng đầu ra mà không tăng số ấy là làm
hỏng mọi thứ đang đọc nó, im lặng. Tăng số ấy phải kèm một mục sổ sai lệch.

Không có dấu thời gian trong đầu ra
------------------------------------

Cố ý. Cùng đầu vào phải cho cùng byte đầu ra, để so được hai lượt chạy — cùng
luật tất định TC-15 đã đặt cho lượt gọi mô hình. Ai cần biết lúc nào thì chính
họ vừa chạy nó.
"""

from __future__ import annotations

import json
import sys
from typing import Any

__all__ = [
    "SCHEMA",
    "bat",
    "dang_bat",
    "ket_qua",
    "muc",
    "in_ket_qua",
    "in_loi",
    "tat",
]

#: Phiên bản lược đồ. Đổi hình dạng đầu ra phải tăng số này VÀ ghi sổ sai lệch.
SCHEMA = 1

#: Chỗ hứng dữ liệu có cấu trúc của lượt chạy này. `None` nghĩa là không bật —
#: và lúc không bật thì mọi hàm ở đây không đổi hành vi của lệnh nào.
_THU: dict[str, Any] | None = None
_LENH: str = ""


def bat(lenh: str) -> None:
    """Bật chế độ máy đọc cho lượt chạy này. Chỉ `main()` gọi."""
    global _THU, _LENH
    _THU, _LENH = {}, lenh


def tat() -> None:
    """Tắt và quên — để bộ kiểm không rò trạng thái giữa các bài."""
    global _THU, _LENH
    _THU, _LENH = None, ""


def dang_bat() -> bool:
    return _THU is not None


def muc(gia_tri: Any, muc_tin_cay: str) -> dict[str, Any]:
    """Một giá trị KÈM mức tin cậy, không trộn thành câu.

    Trộn mức vào chuỗi thì lớp đọc JSON chỉ còn cách dò chữ, và dò chữ thì sớm
    muộn cũng sai. Mức là một TRƯỜNG.
    """
    return {"gia_tri": gia_tri, "muc": muc_tin_cay}


def ket_qua(**du_lieu: Any) -> None:
    """Lệnh nộp dữ liệu có cấu trúc của nó.

    Không bật `--json` thì đây là một lệnh rỗng — nên gọi nó vô điều kiện
    trong thân lệnh là an toàn, và không ai phải viết `if` quanh mỗi chỗ.
    """
    if _THU is None:
        return
    _THU.update(du_lieu)


def _phong_bi(ma_thoat: int, loi: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "command": _LENH,
        "ok": loi is None and ma_thoat == 0,
        "exit_code": ma_thoat,
        **({"error": loi} if loi else {"data": dict(_THU or {})}),
    }


def _in(o: dict[str, Any], luong: Any) -> None:
    json.dump(o, luong, ensure_ascii=False, indent=1, sort_keys=True)
    luong.write("\n")


def in_ket_qua(ma_thoat: int) -> None:
    """In phong bì kết quả ra stdout. Chỉ `main()` gọi, đúng một lần."""
    if _THU is None:
        return
    _in(_phong_bi(ma_thoat), sys.stdout)


def in_loi(ma_thoat: int, thong_diep: str, lam_tiep: tuple[str, ...] = ()) -> None:
    """In phong bì LỖI ra stderr.

    Lệnh hỏng mà không có gì máy đọc được thì lớp IDE chỉ biết "có chuyện" chứ
    không biết chuyện gì — nên nhánh lỗi cũng phải ra JSON. Trường ``next``
    mang chính những câu "làm tiếp" của SL-178, nay ở dạng danh sách chứ không
    còn là văn xuôi đã ghép.
    """
    if _THU is None:
        return
    _in(
        _phong_bi(ma_thoat, {"message": thong_diep, "next": list(lam_tiep)}),
        sys.stderr,
    )
