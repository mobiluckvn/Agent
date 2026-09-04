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

Nửa thứ hai: lời gọi bị đánh rơi (N-910)
-----------------------------------------

Phép so chữ ký ở trên canh cái module này HỨA. Nó không canh cái module này
DÙNG — và đó là nửa đắt hơn.

Chuyện đã xảy ra: một vòng vá làm ``app_init()`` mất bốn lời gọi khởi tạo
driver. Firmware câm hoàn toàn, **33 bài kiểm vẫn xanh**. Không cổng nào đỏ, vì
không có gì sai: mã dịch được, mã chạy được, mã chỉ không làm gì cả. Bài kiểm
đơn vị gọi thẳng hàm cần kiểm nên không đi qua ``app_init()`` lần nào.

Chỗ mất là im lặng theo đúng nghĩa đen. Không có thông báo lỗi nào để đọc.

``mat_loi_goi`` so tập lời gọi LIÊN MODULE của bản đã merge với bản mới. Liên
module nghĩa là: tên hàm ấy được khai báo trong header của một module KHÁC —
không phải hàm nội bộ của chính tệp này, không phải hàm thư viện C.

Vì sao so ở tầm TỆP chứ không tầm HÀM
--------------------------------------

Tách bốn lời gọi ra một hàm phụ rồi gọi hàm phụ ấy là việc tái cấu trúc bình
thường và ĐÚNG. So ở tầm hàm sẽ kêu ở mỗi lần như thế, và một cổng hay kêu
nhầm sớm muộn cũng bị tắt đi.

So ở tầm tệp thì lời gọi dời chỗ trong cùng tệp không bị tính là mất — chỉ lời
gọi **biến khỏi tệp** mới bị tính. Đó đúng là chuyện đã xảy ra, và nó không thể
là tái cấu trúc: một lời gọi liên module biến mất là một việc không còn ai làm.
"""

from __future__ import annotations

import re

__all__ = [
    "khai_bao_ham",
    "loi_goi",
    "mat_loi_goi",
    "pha_vo_hop_dong",
    "than_ham",
]

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


#: Từ khoá đi liền dấu mở ngoặc mà KHÔNG phải lời gọi hàm. Thiếu một từ ở đây
#: thì `if` thành một hàm bị mất, và bộ kiểm kêu ở mọi lượt sinh.
_KHONG_PHAI_LOI_GOI = frozenset(
    {
        "if", "while", "for", "switch", "do", "else", "return", "sizeof",
        "case", "goto", "defined", "_Static_assert", "static_assert",
        "alignof", "_Alignof", "typeof", "__typeof__", "asm", "__asm__",
        "catch",
    }
)

_CHUOI = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.DOTALL)
_LOI_GOI = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_MO_THAN = re.compile(
    # `kiểu tên(tham số) {` — tham số cho phép MỘT tầng ngoặc lồng để con trỏ
    # hàm không làm hỏng phép khớp.
    r"\b(?P<ten>[A-Za-z_]\w*)\s*\((?P<tham>[^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)\s*"
    r"(?:[A-Za-z_]\w*\s*)*\{"
)


def _lam_sach(nguon: str) -> str:
    """Bỏ chú thích, tiền xử lý và RUỘT của mọi chuỗi.

    Ruột chuỗi phải đi, không phải vì nó gây nhiễu tên hàm mà vì nó có thể chứa
    dấu ngoặc nhọn — và một dấu ngoặc nhọn trong chuỗi làm phép đếm ngoặc lệch
    từ đó tới hết tệp.
    """
    van = _CHU_THICH_KHOI.sub(" ", nguon)
    van = _CHU_THICH_DONG.sub(" ", van)
    van = _TIEN_XU_LY.sub(" ", van)
    # Giữ nguyên độ dài không cần thiết; chỉ cần bỏ nội dung.
    return _CHUOI.sub('""', van)


def than_ham(nguon: str) -> dict[str, str]:
    """Tên hàm → thân hàm, đọc từ một tệp mã C.

    Chỉ lấy ĐỊNH NGHĨA (có thân). Khai báo suông thuộc về ``khai_bao_ham``.

    Dùng để NÊU TÊN chỗ mất trong thông báo lỗi, không dùng để quyết định. Phép
    quyết định nằm ở tầm tệp — xem docstring đầu mô-đun.
    """
    van = _lam_sach(nguon)
    ket_qua: dict[str, str] = {}
    for khop in _MO_THAN.finditer(van):
        ten = khop.group("ten")
        if ten in _KHONG_PHAI_LOI_GOI:
            continue
        mo = van.index("{", khop.end() - 1)
        sau = _quet_den_dong_ngoac(van, mo)
        if sau is None:
            continue
        ket_qua[ten] = van[mo + 1 : sau]
    return ket_qua


def _quet_den_dong_ngoac(van: str, mo: int) -> int | None:
    """Vị trí dấu ``}`` khớp với dấu ``{`` ở ``mo``; None nếu tệp cụt."""
    sau = 1
    i = mo + 1
    while i < len(van):
        if van[i] == "{":
            sau += 1
        elif van[i] == "}":
            sau -= 1
            if sau == 0:
                return i
        i += 1
    return None


def loi_goi(nguon: str) -> set[str]:
    """Tên mọi hàm được GỌI trong một đoạn mã C.

    Bỏ từ khoá điều khiển (``if (``, ``while (``…) — chúng đi liền dấu mở ngoặc
    nhưng không phải lời gọi. Bỏ cả ruột chuỗi, để một dòng in ra màn hình có
    chữ ``foo(`` không bị đếm thành lời gọi.
    """
    van = _lam_sach(nguon)
    return {t for t in _LOI_GOI.findall(van) if t not in _KHONG_PHAI_LOI_GOI}


def mat_loi_goi(cu: str, moi: str, quan_tam: frozenset[str] | set[str]) -> list[str]:
    """Lời gọi liên module có trong bản đã merge mà bản mới không còn.

    ``quan_tam`` là tập hàm công khai của các module KHÁC. Giới hạn vào tập ấy
    có chủ ý: hàm nội bộ mất đi thường là tái cấu trúc, còn một lời gọi sang
    module khác mất đi là một việc không còn ai làm.

    Thông báo nêu tên hàm CŨ từng chứa lời gọi ấy, vì "``app_init()`` không còn
    gọi ``drv_imu_init()``" chỉ đúng chỗ, còn "thiếu ``drv_imu_init``" thì bắt
    người đọc đi tìm.
    """
    if not quan_tam:
        return []
    goi_cu = loi_goi(cu) & set(quan_tam)
    mat = sorted(goi_cu - loi_goi(moi))
    if not mat:
        return []

    # Ai từng gọi nó: tra trong thân hàm của bản CŨ. Không tra được thì vẫn báo,
    # chỉ mất một nửa câu — im lặng vì không nêu được tên là đổi một lỗi thật
    # lấy một dòng đẹp.
    than = than_ham(cu)
    ra: list[str] = []
    for ten in mat:
        chu = sorted(h for h, t in than.items() if ten in loi_goi(t))
        if chu:
            ra.append(f"MẤT   {', '.join(f'{h}()' for h in chu)} không còn gọi {ten}()")
        else:
            ra.append(f"MẤT   không còn chỗ nào gọi {ten}()")
    return ra


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
