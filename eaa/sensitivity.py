"""Độ nhạy của bài kiểm — màu xanh chưa phải bằng chứng (N-909).

Vì sao cần
----------

Ngày 03/09, kỹ sư yêu cầu Agent thêm một bài canh: trong vùng chết, điểm đặt
phải đứng yên. Agent thêm ``test_deadband_keeps_setpoint_steady``, và bài ấy
**đỏ ở vòng đầu, xanh sau khi sửa** — nhìn từ ngoài thì đúng hệt một bài kiểm
làm đúng việc của nó.

Đọc kỹ thì nó chạy 10 vòng. Điểm đặt trôi 0,0015 mỗi vòng, sau 10 vòng được
0,015 — còn cách xa ngưỡng của vùng chết. Bài kiểm ấy **xanh cả với mã sai**;
nó đỏ vì một lý do khác.

Dạng hỏng này khó thấy hơn mọi dạng khác trong sổ: không có hằng số nào bị
chỉnh, không có chú thích nào tự khai là workaround. Bài kiểm trông đúng, tên
đúng, và kết quả đúng ở đúng hai thời điểm cần đúng.

Bộ này đo cái gì
----------------

Đúng một câu hỏi, và nó trả lời được bằng máy:

    **Bài kiểm vừa thêm có phân biệt được bản vừa bị cổng đánh đỏ với bản vừa
    được nhận không?**

Chạy lại chính bài kiểm ấy trên mã CŨ. Nếu nó xanh trên cả hai bản thì nó không
chứng minh được điều gì về lần sửa vừa rồi — dù nó xanh, dù tên nó nghe đúng.

Ranh giới — và ranh giới này quan trọng
----------------------------------------

Phép đo này **không** nói bài kiểm ấy đủ mạnh. Ca ``deadband`` ở trên vẫn đỏ
trên mã cũ (vì một lý do khác), nên nó sẽ QUA được phép đo này. Bộ đo bắt được
hạng nhẹ hơn: bài kiểm hoàn toàn không phân biệt được gì.

Nên kết quả đi vào **hồ sơ G3 cho người đọc**, không đi vào đường chặn. Bài học
của chính ca ấy là: *màu của bài kiểm không thay thế được việc đọc mã ở G3*. Một
bộ đo tự nhận thay được người ở đây sẽ tái lập đúng cái sai nó sinh ra để chặn.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

__all__ = [
    "KetQuaDoNhay",
    "bai_kiem_do",
    "bai_kiem_doi",
    "bai_kiem_trong",
    "co_loi_thu_thap",
    "ket_luan",
]

#: `FAILED tests/test_x.py::test_ten` và `ERROR tests/test_x.py::test_ten`.
_DONG_DO = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)


@dataclass(frozen=True)
class KetQuaDoNhay:
    """Kết quả một phép đo độ nhạy.

    ``do_duoc`` sai nghĩa là phép đo KHÔNG chạy được — thiếu cổng, thiếu tệp,
    tệp test không phân tích nổi. Lúc ấy ``khong_phan_biet`` rỗng, và cái rỗng
    ấy **không phải** lời khẳng định mọi bài kiểm đều tốt. Hai chuyện khác
    nhau, nên chúng có hai trường.
    """

    bai_kiem_moi: tuple[str, ...] = ()
    phan_biet_duoc: tuple[str, ...] = ()
    khong_phan_biet: tuple[str, ...] = ()
    do_duoc: bool = True
    ly_do: str = ""

    @property
    def dat(self) -> bool:
        """Đúng khi mọi bài kiểm mới đều phân biệt được, hoặc không có bài nào."""
        return self.do_duoc and not self.khong_phan_biet

    def cau(self) -> str:
        """Một dòng cho nhật ký và cho hồ sơ G3."""
        if not self.do_duoc:
            return f"Độ nhạy bài kiểm: KHÔNG đo được — {self.ly_do}"
        if not self.bai_kiem_moi:
            return "Độ nhạy bài kiểm: không có bài kiểm nào mới hoặc đổi"
        if not self.khong_phan_biet:
            return (
                f"Độ nhạy bài kiểm: {len(self.phan_biet_duoc)}/"
                f"{len(self.bai_kiem_moi)} bài mới phân biệt được bản cũ với bản mới"
            )
        return (
            "Độ nhạy bài kiểm: "
            + ", ".join(self.khong_phan_biet)
            + " XANH CẢ TRÊN MÃ VỪA BỊ ĐÁNH ĐỎ — bài kiểm ấy không chứng minh "
            "được gì về lần sửa này. Đọc mã ở G3, đừng đọc màu."
        )


def bai_kiem_trong(nguon: str) -> dict[str, str]:
    """Tên bài kiểm → dạng chuẩn hoá của thân nó, đọc từ một tệp test Python.

    Chuẩn hoá bằng cây cú pháp chứ không bằng chuỗi: thụt lề đổi, chú thích
    đổi, xuống dòng đổi — không cái nào đổi việc bài kiểm ấy làm. So chuỗi thì
    mọi lượt định dạng lại đều thành "bài kiểm đã đổi", và phép đo sẽ chạy ở
    những lượt không cần chạy.

    Tệp không phân tích nổi trả về rỗng. Đó là chuyện có thật — mô hình sinh ra
    tệp Python hỏng cú pháp — và nó phải phân biệt được với "tệp không có bài
    kiểm nào"; chỗ phân biệt nằm ở :func:`ket_luan`, qua ``do_duoc``.
    """
    try:
        cay = ast.parse(nguon)
    except SyntaxError:
        return {}
    ra: dict[str, str] = {}
    for nut in ast.walk(cay):
        if isinstance(nut, (ast.FunctionDef, ast.AsyncFunctionDef)) and nut.name.startswith(
            "test"
        ):
            ra[nut.name] = ast.dump(nut, include_attributes=False)
    return ra


def bai_kiem_doi(cu: str | None, moi: str) -> tuple[str, ...]:
    """Bài kiểm MỚI hoặc đã ĐỔI giữa hai bản của cùng một tệp test.

    ``cu`` là None khi module sinh lần đầu — lúc ấy mọi bài kiểm đều mới.

    Bài kiểm bị XOÁ không nằm trong kết quả: phép đo này hỏi "cái vừa thêm có
    chứng minh được gì không", và một bài đã xoá thì không còn gì để đo.
    """
    ban_moi = bai_kiem_trong(moi)
    if not ban_moi:
        return ()
    ban_cu = bai_kiem_trong(cu) if cu else {}
    return tuple(sorted(t for t, than in ban_moi.items() if ban_cu.get(t) != than))


def bai_kiem_do(dau_ra: str) -> frozenset[str]:
    """Tên bài kiểm ĐỎ, đọc từ đầu ra pytest ``-rfEs``.

    Chỉ lấy phần sau ``::`` — cổng chạy trong một thư mục khác nên phần đường
    dẫn không so được thẳng với đường dẫn trong artifact. Bài kiểm có tham số
    (``test_x[1-2]``) bị cắt phần ngoặc vuông để khớp với tên hàm.
    """
    ra: set[str] = set()
    for nut in _DONG_DO.findall(dau_ra):
        if "::" not in nut:
            continue
        ten = nut.rsplit("::", 1)[1]
        ra.add(ten.split("[", 1)[0])
    return frozenset(ra)


def co_loi_thu_thap(dau_ra: str) -> bool:
    """Có lỗi THU THẬP không — tức cả tệp không nạp nổi.

    Lúc ấy pytest in ``ERROR tests/test_x.py`` không kèm ``::``, và không bài
    kiểm nào chạy. Đó vẫn là "bộ kiểm phân biệt được hai bản mã": bản cũ làm cả
    tệp không nạp được, bản mới thì được.
    """
    return any("::" not in nut for nut in _DONG_DO.findall(dau_ra))


def ket_luan(
    bai_moi: tuple[str, ...],
    dau_ra_tren_ma_cu: str,
    *,
    do_duoc: bool = True,
    ly_do: str = "",
) -> KetQuaDoNhay:
    """Ghép phép đo lại thành kết luận.

    Một bài kiểm PHÂN BIỆT ĐƯỢC khi nó đỏ trên mã cũ. Cả tệp không nạp nổi trên
    mã cũ cũng tính là phân biệt được: bản cũ hỏng tới mức không chạy nổi thì
    bộ kiểm rõ ràng không xanh trên nó.
    """
    if not do_duoc:
        return KetQuaDoNhay(bai_kiem_moi=bai_moi, do_duoc=False, ly_do=ly_do)
    if not bai_moi:
        return KetQuaDoNhay()
    if co_loi_thu_thap(dau_ra_tren_ma_cu):
        return KetQuaDoNhay(bai_kiem_moi=bai_moi, phan_biet_duoc=bai_moi)
    do = bai_kiem_do(dau_ra_tren_ma_cu)
    return KetQuaDoNhay(
        bai_kiem_moi=bai_moi,
        phan_biet_duoc=tuple(t for t in bai_moi if t in do),
        khong_phan_biet=tuple(t for t in bai_moi if t not in do),
    )
