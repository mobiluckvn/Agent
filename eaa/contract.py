"""Hợp đồng gọi — canh việc một lượt sinh lại đổi giao diện công khai (SL-163).

Vì sao cần
----------

`khoa_pham_vi_tep` (SL-154) canh QUYỀN GHI: module này không viết được tệp của
module kia. Nhưng một module sinh lại vẫn chỉ viết tệp của CHÍNH NÓ — và đổi
một chữ ký trong header của mình là đủ làm mọi module đã merge gọi tới nó
không dịch được nữa. Quyền ghi bị canh, hợp đồng gọi thì không.

Chuyện đã xảy ra ngày 03/09: bản sinh lại `logic_pid` bỏ tham số `is_running`
khỏi `pid_compute`, và `app_balance` — đã qua G3, đã merge — chết ở khâu dịch.

SL-162 bắt được chuyện ấy nhưng **gián tiếp**: qua một module khác tình cờ gọi
tới. Module chưa ai gọi thì đổi chữ ký vẫn lọt, và nó sẽ lọt cho tới đúng lúc
có người viết module gọi tới — tức là muộn nhất có thể.

Bộ này so thẳng: khai báo trên `main` với khai báo vừa sinh.

Ranh giới của nó
----------------

Đây là bộ so KHAI BÁO, không phải bộ dịch C. Nó không hiểu macro, không mở
`#include`, và với con trỏ hàm hay mảng thì nó so **nguyên văn** thay vì tách
tên tham số ra. Ngả về phía báo NHẦM ở những chỗ ấy là có chủ ý: một hợp đồng
đổi mà không ai biết thì đắt hơn nhiều một lần hỏi thừa.

Nhưng nó KHÔNG được báo nhầm ở chỗ thường: đổi tên tham số là chuyện vô hại và
xảy ra suốt, nên tên tham số bị bỏ trước khi so.
"""

from __future__ import annotations

import re

__all__ = ["khai_bao_ham", "pha_vo_hop_dong"]

#: Từ khoá kiểu — một định danh cuối cùng thuộc tập này là KIỂU chứ không phải
#: tên tham số, và bỏ nó đi sẽ biến ``unsigned int`` thành ``unsigned``.
TU_KHOA_KIEU = frozenset(
    {
        "void", "char", "short", "int", "long", "float", "double",
        "signed", "unsigned", "bool", "const", "volatile", "struct",
        "union", "enum", "size_t", "ptrdiff_t", "wchar_t",
    }
)

_CHU_THICH_KHOI = re.compile(r"/\*.*?\*/", re.DOTALL)
_CHU_THICH_DONG = re.compile(r"//[^\n]*")
_TIEN_XU_LY = re.compile(r"^[ \t]*#[^\n]*", re.MULTILINE)
_KHAI_BAO = re.compile(
    r"^(?P<ret>[A-Za-z_][\w\s\*]*?[\s\*])(?P<ten>[A-Za-z_]\w*)\s*\((?P<tham>.*)\)$",
    re.DOTALL,
)


def _la_kieu(dinh_danh: str) -> bool:
    return dinh_danh in TU_KHOA_KIEU or bool(re.fullmatch(r"u?int\d+_t", dinh_danh))


def _gon(van_ban: str) -> str:
    return " ".join(van_ban.split())


def _kieu_tham_so(tham: str) -> str:
    """Một tham số, đã bỏ TÊN và chỉ còn KIỂU.

    Đổi tên tham số không phá hợp đồng nào — nó không đổi cách gọi. So cả tên
    thì bộ này sẽ kêu ở mỗi lần đổi tên, và một cổng hay kêu nhầm sớm muộn
    cũng bị tắt đi.
    """
    t = _gon(tham)
    if not t or t == "void":
        return t
    # Con trỏ hàm và mảng: cấu trúc không tách được bằng một biểu thức chính
    # quy, nên so nguyên văn. Thà kêu thừa còn hơn bỏ lọt một hợp đồng đã đổi.
    if "(" in t or "[" in t:
        return t
    khop = re.fullmatch(r"(?P<dau>.*[\s\*])(?P<cuoi>[A-Za-z_]\w*)", t)
    if not khop or _la_kieu(khop.group("cuoi")):
        return t
    return _gon(khop.group("dau"))


def khai_bao_ham(nguon: str) -> dict[str, str]:
    """Tên hàm → chữ ký đã chuẩn hoá, đọc từ một tệp header.

    Chỉ lấy KHAI BÁO. Định nghĩa có thân hàm (``static inline`` trong header)
    bị bỏ qua: thân hàm đổi không phải hợp đồng đổi.
    """
    van_ban = _CHU_THICH_KHOI.sub(" ", nguon)
    van_ban = _CHU_THICH_DONG.sub(" ", van_ban)
    van_ban = _TIEN_XU_LY.sub(" ", van_ban)

    ket_qua: dict[str, str] = {}
    for doan in van_ban.split(";"):
        if "{" in doan or "}" in doan:
            continue
        khop = _KHAI_BAO.match(doan.strip())
        if not khop:
            continue
        ten = khop.group("ten")
        # `typedef` và các từ khoá mở đầu khác không phải kiểu trả về.
        tra_ve = _gon(khop.group("ret"))
        if tra_ve.split()[0] in {"typedef", "return", "if", "while", "for", "switch"}:
            continue
        tham = khop.group("tham").strip()
        danh_sach = [_kieu_tham_so(t) for t in tham.split(",")] if tham else []
        ket_qua[ten] = f"{tra_ve} {ten}({', '.join(danh_sach)})"
    return ket_qua


def pha_vo_hop_dong(cu: str, moi: str) -> list[str]:
    """Những hàm mà bản mới đã phá hợp đồng của bản đã merge.

    Hai hạng, và chỉ hai:

    * **mất** — hàm có trên ``main`` mà bản mới không còn khai báo;
    * **đổi** — còn đó nhưng chữ ký khác.

    Hàm MỚI thêm vào không phải vi phạm: mở rộng cái nó làm là việc bình
    thường của một lượt sinh lại. Chỉ thu hẹp hoặc đổi mới là phá.
    """
    ban_cu = khai_bao_ham(cu)
    ban_moi = khai_bao_ham(moi)

    vi_pham: list[str] = []
    for ten, chu_ky in ban_cu.items():
        if ten not in ban_moi:
            vi_pham.append(f"MẤT   {chu_ky};")
        elif ban_moi[ten] != chu_ky:
            vi_pham.append(f"ĐỔI   {chu_ky};\n      → {ban_moi[ten]};")
    return vi_pham
