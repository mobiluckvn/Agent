"""Mức tin cậy — một bộ từ vựng duy nhất cho toàn hệ. N-903.

EAA-AIS-05 §6.1 (proposed fact), §12 (rủi ro ảo giác có nguồn); FR-ING-02.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-57.

Vấn đề mà tệp này giải
-----------------------

Nhiều chỗ trong hệ đã phân biệt đúng ba loại phát biểu — `flash.VerifyResult`
có "đã kiểm / lệch / không kiểm được", `docplan.ErrataAnalysis` có "đã tra /
chưa tra", `propose.PlantParameter` có "đã đo / ước lượng" — nhưng mỗi chỗ tự
đặt tên theo cách riêng. Người đọc phải học lại từ vựng ở từng màn hình, và
điều tệ hơn: những chỗ CHƯA phân biệt thì chẳng có gì nhắc rằng chúng nên
phân biệt.

Một từ vựng chung không tự làm các đầu ra trung thực hơn. Nó làm cho việc
*thiếu nhãn* trở nên nhìn thấy được — và đó là bước đầu tiên.

Bốn mức, và ranh giới giữa mức ba với mức bốn
----------------------------------------------

* **ĐÃ KIỂM** — có bằng chứng trực tiếp: một phép đo, một lần đọc ngược, một
  cổng đã chạy. Câu mạnh nhất hệ này được phép nói.
* **SUY RA** — đúng theo dữ liệu đã có, nhưng chưa ai kiểm ở đời thật. Kết quả
  bắc cầu trên đồ thị tri thức nằm ở đây.
* **GIẢ ĐỊNH** — chưa có căn cứ, chỉ là con số phải điền vào để đi tiếp. BẮT
  BUỘC kèm cách kiểm.
* **KHÔNG KIỂM ĐƯỢC** — đã thử và không với tới: công cụ không hỗ trợ, dữ liệu
  không có, thiết bị không báo.

Ranh giới GIẢ ĐỊNH / KHÔNG KIỂM ĐƯỢC hay bị gộp, và gộp là mất thông tin: cái
đầu còn kiểm được nếu ai đó bỏ công, cái sau thì không — nó cần một cách khác
hoặc một dụng cụ khác. Hai tình huống ấy dẫn tới hai việc phải làm khác hẳn.

Điều bộ từ vựng này KHÔNG làm
------------------------------

Nó không xếp hạng, không tính điểm, không gộp nhiều nhãn thành một con số tin
cậy. Một con số như thế nghe khoa học và che mất đúng thứ cần thấy: phát biểu
NÀO đang ở mức nào.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, Sequence, runtime_checkable

__all__ = [
    "DA_KIEM",
    "SUY_RA",
    "GIA_DINH",
    "KHONG_KIEM_DUOC",
    "LEVELS",
    "ConfidenceError",
    "Claim",
    "ClaimSet",
    "Judged",
    "label",
    "describe",
    "header",
]

#: Có bằng chứng trực tiếp — một phép đo, một lần đọc ngược, một cổng đã chạy.
DA_KIEM = "ĐÃ KIỂM"
#: Đúng theo dữ liệu đã có, chưa ai kiểm ở đời thật.
SUY_RA = "SUY RA"
#: Chưa có căn cứ; phải kèm cách kiểm.
GIA_DINH = "GIẢ ĐỊNH"
#: Đã thử và không với tới.
KHONG_KIEM_DUOC = "KHÔNG KIỂM ĐƯỢC"

#: Bốn mức, xếp từ mạnh tới yếu. Thứ tự dùng để SẮP XẾP khi in, không dùng để
#: cộng trừ — xem phần cuối docstring đầu tệp.
LEVELS: tuple[str, ...] = (DA_KIEM, SUY_RA, GIA_DINH, KHONG_KIEM_DUOC)


class ConfidenceError(Exception):
    """Phát biểu gắn nhãn sai quy ước."""


def label(level: str, statement: str) -> str:
    """Gắn nhãn vào một câu, đúng một cách viết cho toàn hệ."""
    if level not in LEVELS:
        raise ConfidenceError(f"Mức tin cậy không hợp lệ: {level!r} (hợp lệ: {list(LEVELS)})")
    return f"[{level}] {statement}"


#: Một dòng giải thích mỗi mức, để đầu ra nào cũng tự nói được ý nghĩa nhãn của
#: nó mà không bắt người đọc đi tra tài liệu.
_GIAI_THICH: dict[str, str] = {
    DA_KIEM: "có bằng chứng trực tiếp — một phép đo, một lần đọc ngược, một cổng đã chạy",
    SUY_RA: "bắc cầu đúng trên dữ liệu dự án đã khai, nhưng chưa ai kiểm ở đời thật",
    GIA_DINH: "chưa có căn cứ; cần người duyệt hoặc cần đi đo trước khi dựa vào",
    KHONG_KIEM_DUOC: "đã thử và không với tới — cần cách khác hoặc dụng cụ khác",
}


def describe(level: str) -> str:
    """Giải thích một mức bằng một dòng."""
    if level not in LEVELS:
        raise ConfidenceError(f"Mức tin cậy không hợp lệ: {level!r}")
    return _GIAI_THICH[level]


def header(level: str, title: str = "") -> str:
    """Dòng mở đầu của một báo cáo, nói ngay kết luận này đáng tin tới đâu.

    Đặt ở ĐẦU chứ không ở cuối: người đọc quyết định tin tới đâu trước khi đọc
    nội dung, không phải sau. Một bản đề xuất đọc hết rồi mới thấy dòng "đây
    chỉ là phỏng đoán" thì dòng ấy tới muộn.
    """
    dau = f"[{level}]"
    if title:
        dau += f" {title}"
    return f"{dau}\n    {describe(level)}"


@runtime_checkable
class Judged(Protocol):
    """Vật thể mang kết luận thì phải nói được kết luận ấy ở mức nào.

    Đây là hợp đồng của N-903. Nó cố ý nhỏ: một thuộc tính. Nhờ vậy mọi lớp
    sinh ra kết luận đều theo được mà không phải kế thừa gì, và một bài test
    duyệt qua danh sách các lớp ấy để chắc không lớp nào bị bỏ quên khi thêm
    tính năng mới.
    """

    @property
    def confidence_level(self) -> str: ...


@dataclass(frozen=True)
class Claim:
    """Một phát biểu, kèm mức tin cậy và căn cứ."""

    statement: str
    level: str
    #: Bằng chứng hoặc nguồn. Bắt buộc với ĐÃ KIỂM — không có nguồn thì nó
    #: không phải "đã kiểm", nó chỉ là một câu nói chắc.
    source: str = ""
    #: Cách kiểm. Bắt buộc với GIẢ ĐỊNH — một giả định không kèm cách kiểm sẽ
    #: lặng lẽ được đọc như một sự thật.
    how_to_verify: str = ""
    #: Vì sao không kiểm được. Bắt buộc với KHÔNG KIỂM ĐƯỢC.
    why_not: str = ""

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ConfidenceError(
                f"Mức tin cậy không hợp lệ: {self.level!r} (hợp lệ: {list(LEVELS)})"
            )
        if not self.statement.strip():
            raise ConfidenceError("phát biểu rỗng")
        if self.level == DA_KIEM and not self.source.strip():
            raise ConfidenceError(
                f"{self.statement!r}: gắn nhãn ĐÃ KIỂM mà không nêu bằng chứng. "
                "Không có nguồn thì đây không phải 'đã kiểm', chỉ là một câu nói chắc."
            )
        if self.level == GIA_DINH and not self.how_to_verify.strip():
            raise ConfidenceError(
                f"{self.statement!r}: là GIẢ ĐỊNH mà không nói kiểm bằng cách nào. "
                "Một giả định không kèm cách kiểm sẽ lặng lẽ được đọc như một sự thật."
            )
        if self.level == KHONG_KIEM_DUOC and not self.why_not.strip():
            raise ConfidenceError(
                f"{self.statement!r}: nói KHÔNG KIỂM ĐƯỢC mà không nói vì sao. "
                "Thiếu lý do thì người đọc không biết cần dụng cụ khác hay cần "
                "cách khác — hai việc phải làm hoàn toàn khác nhau."
            )

    @property
    def actionable(self) -> str:
        """Việc phải làm để nâng mức tin cậy của phát biểu này."""
        if self.level == DA_KIEM:
            return ""
        if self.level == GIA_DINH:
            return self.how_to_verify
        if self.level == KHONG_KIEM_DUOC:
            return f"cần cách khác hoặc dụng cụ khác: {self.why_not}"
        return "kiểm lại ở đời thật để nâng lên ĐÃ KIỂM"

    def render(self) -> str:
        dong = [label(self.level, self.statement)]
        if self.source:
            dong.append(f"      nguồn: {self.source}")
        viec = self.actionable
        if viec:
            dong.append(f"      để chắc hơn: {viec}")
        return "\n".join(dong)


@dataclass
class ClaimSet:
    """Một nhóm phát biểu — thường là toàn bộ kết luận của một lệnh."""

    title: str = ""
    claims: list[Claim] = field(default_factory=list)

    def add(self, statement: str, level: str, **kw: Any) -> Claim:
        muc = Claim(statement=statement, level=level, **kw)
        self.claims.append(muc)
        return muc

    def by_level(self, level: str) -> list[Claim]:
        return [c for c in self.claims if c.level == level]

    @property
    def weakest(self) -> str:
        """Mức yếu nhất trong nhóm — mức mà cả kết luận thực sự đứng trên.

        Một kết luận gồm chín câu ĐÃ KIỂM và một câu GIẢ ĐỊNH thì mạnh ngang
        câu giả định ấy, nếu chín câu kia phụ thuộc vào nó. Không có cách nào
        tính điều đó tự động, nên hàm này chỉ nêu ra để người đọc tự xét — và
        nêu ra vẫn hơn hẳn im lặng.
        """
        if not self.claims:
            return KHONG_KIEM_DUOC
        return max(self.claims, key=lambda c: LEVELS.index(c.level)).level

    def render(self) -> str:
        dong = [self.title] if self.title else []
        for muc in sorted(self.claims, key=lambda c: LEVELS.index(c.level)):
            dong.append("  " + muc.render().replace("\n", "\n  "))
        if self.claims and self.weakest != DA_KIEM:
            dong += [
                "",
                f"  Mức yếu nhất trong nhóm: {self.weakest}. Nếu các câu khác dựa",
                "  vào câu ấy thì cả kết luận chỉ chắc tới mức ấy.",
            ]
        return "\n".join(dong)
