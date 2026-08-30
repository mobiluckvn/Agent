"""Truy xuất hai tầng — quan hệ trước, BM25 bổ trợ sau. AIS §4.2, ADR-07.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-66 (và SL-06, nơi module này từng được
ghi là "hoãn có chủ ý").

Vì sao BM25 chứ không phải embedding
-------------------------------------

ADR-07 chốt: **khớp chính xác + BM25 thay embedding**. Lý do không phải là tiết
kiệm. Với tài liệu kỹ thuật, định danh mạnh nhất là TÊN THANH GHI — và tên
thanh ghi là thứ mà khớp gần đúng làm hỏng chứ không làm tốt hơn.

Tên thanh ghi của hai bộ đếm khác nhau trên cùng một chip thường chỉ lệch nhau
một chữ số, tới mức mọi phép đo khoảng cách ngữ nghĩa đều coi chúng là một —
trong khi cấu hình nhầm bộ đếm là sai từ gốc, và cái sai ấy đi qua sạch mọi
cổng kiểm chứng vì mã vẫn dịch được và vẫn đúng cú pháp.

BM25 giữ được tính chất ấy: nó đếm từ, và hai chuỗi khác nhau là hai từ khác
nhau. Nó cũng chạy được không cần mô hình, không cần mạng, và cho cùng một kết
quả mỗi lần — điều kiện để thực nghiệm Chương 3 tái lập.

Thứ tự hai tầng, và vì sao không đảo được
------------------------------------------

**Tầng 1 — quan hệ (đồ thị tri thức).** Module dùng ngoại vi nào → ngoại vi ấy
cấu hình bằng thanh ghi nào → thanh ghi ấy được tài liệu hóa ở trích đoạn nào.
Đây là bắc cầu trên dữ liệu dự án đã khai, nên nó đúng theo định nghĩa chứ
không đúng theo xác suất.

**Tầng 2 — BM25.** Chỉ chạy khi tầng 1 chưa lấp đủ ``top_k``, và chỉ nhận ứng
viên đủ ĐỘ PHỦ từ khóa. Nó lấp đúng một chỗ hở: trích đoạn có nội dung liên quan
mà đồ thị chưa có cạnh nào dẫn tới — thường vì dự án chưa khai ``configured_by``
cho một linh kiện, hoặc vì tài liệu nói về một khái niệm chứ không về một
thanh ghi.

Đảo thứ tự sẽ hỏng: BM25 cho điểm mọi trích đoạn chia sẻ vài từ, nên chạy nó
trước sẽ đẩy một trích đoạn "gần giống" lên trên một trích đoạn mà đồ thị chỉ
đích danh. Bộ chuẩn TC-20 đo đúng điều này.

Ngưỡng nhận là ĐỘ PHỦ TỪ KHÓA, không phải điểm BM25
-----------------------------------------------------

Không có ngưỡng, BM25 luôn lấp đủ ``top_k`` bằng thứ tốt nhất nó tìm được — kể
cả khi thứ tốt nhất ấy chẳng liên quan gì. Một prompt lấp đủ ba chỗ bằng hai
chỗ vô nghĩa còn tệ hơn một prompt chỉ có một chỗ đúng: nó tốn token, và nó
làm loãng đúng phần cần đọc kỹ.

Ngưỡng ấy **không dùng điểm BM25**, và đây là một bài học phải trả giá mới
biết. Điểm BM25 phụ thuộc cỡ kho qua thành phần idf: một trích đoạn khớp hoàn
hảo trong kho hai tài liệu cho khoảng 0,3 điểm, còn một trích đoạn khớp vừa
phải trong kho năm mươi tài liệu cho vài điểm. Một con số sàn tuyệt đối vì thế
sẽ quá chặt lúc kho còn nhỏ và quá lỏng khi kho lớn lên — tức là sai ở cả hai
đầu vòng đời dự án.

Thứ dùng thay là **độ phủ**: trích đoạn phải chứa ít nhất một phần ba số từ
khóa khác nhau của câu truy vấn. Đại lượng này không phụ thuộc cỡ kho, và nó
nói thẳng điều ta thật sự muốn hỏi — *trích đoạn này có nói về những thứ module
đang cần không* — thay vì hỏi vòng qua một con số thống kê.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

__all__ = [
    "Bm25Index",
    "Retrieved",
    "tokenize",
    "select_chunks",
    "QUAN_HE",
    "BM25",
    "DO_PHU_TOI_THIEU",
]

#: Tầng 1 — đồ thị chỉ đích danh.
QUAN_HE = "quan-he"
#: Tầng 2 — BM25 bổ trợ.
BM25 = "bm25"

#: Phần từ khóa KHÁC NHAU của câu truy vấn mà một trích đoạn phải chứa để được
#: nhận ở tầng 2. Xem phần cuối docstring đầu tệp để biết vì sao là độ phủ chứ
#: không phải điểm BM25.
#:
#: Một phần ba: đủ chặt để loại trích đoạn chỉ tình cờ trùng một hai từ (trên
#: dự án mẫu, trích đoạn chế độ slave phủ 2/10 từ khóa của module master nên bị
#: loại), đủ lỏng để nhận một trích đoạn nói đúng chủ đề mà dùng chữ khác ta.
DO_PHU_TOI_THIEU = 1.0 / 3.0

#: Từ quá ngắn thì không mang thông tin định danh. Ngưỡng 2 giữ được các tên
#: thanh ghi ngắn nhất mà vẫn bỏ đi hư từ.
_MIN_TOKEN = 2

_TACH = re.compile(r"[^0-9a-zà-ỹ_]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Tách từ, giữ nguyên chữ số và gạch dưới của tên thanh ghi.

    Không tách theo gạch dưới có chủ ý. Tên thanh ghi thường gồm nhiều mảnh nối
    bằng gạch dưới, và cả cụm mới là MỘT định danh — tách ra thì mỗi mảnh là
    một từ ba chữ cái vô nghĩa, trùng với hàng chục thứ khác trong kho. Đây
    đúng là chỗ mà một bộ tách từ ngôn ngữ tự nhiên làm hỏng tài liệu kỹ thuật.
    """
    return [t for t in _TACH.split((text or "").lower()) if len(t) >= _MIN_TOKEN]


@dataclass
class Bm25Index:
    """Chỉ mục BM25 trên một tập văn bản.

    Cài đặt thẳng theo công thức chuẩn, không phụ thuộc thư viện ngoài: bộ này
    chạy trong CI của một đề án, và một phụ thuộc thêm là một thứ nữa có thể
    vắng mặt vào đúng hôm bảo vệ.
    """

    docs: dict[str, str]
    k1: float = 1.5
    b: float = 0.75

    _tf: dict[str, Counter] = field(default_factory=dict, init=False)
    _df: Counter = field(default_factory=Counter, init=False)
    _len: dict[str, int] = field(default_factory=dict, init=False)
    _avg: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        for ma, van_ban in self.docs.items():
            tu = tokenize(van_ban)
            self._tf[ma] = Counter(tu)
            self._len[ma] = len(tu)
            for t in set(tu):
                self._df[t] += 1
        self._avg = (sum(self._len.values()) / len(self._len)) if self._len else 0.0

    def _idf(self, tu: str) -> float:
        n = len(self.docs)
        df = self._df.get(tu, 0)
        # Dạng cộng 1 bên trong log: luôn dương, nên một từ có mặt ở MỌI tài
        # liệu vẫn đóng góp một chút thay vì bị triệt tiêu về 0 hoặc âm.
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, doc_id: str) -> float:
        if doc_id not in self._tf or not self._avg:
            return 0.0
        tf = self._tf[doc_id]
        do_dai = self._len[doc_id]
        tong = 0.0
        for tu in set(tokenize(query)):
            f = tf.get(tu, 0)
            if not f:
                continue
            mau = f + self.k1 * (1.0 - self.b + self.b * do_dai / self._avg)
            tong += self._idf(tu) * f * (self.k1 + 1.0) / mau
        return tong

    def coverage(self, query: str, doc_id: str) -> float:
        """Phần từ khóa khác nhau của câu truy vấn mà tài liệu này chứa.

        Không phụ thuộc cỡ kho — khác hẳn điểm BM25 — nên nó dùng làm ngưỡng
        nhận được, còn điểm chỉ dùng để XẾP HẠNG những cái đã qua ngưỡng.
        """
        tu = set(tokenize(query))
        if not tu or doc_id not in self._tf:
            return 0.0
        tf = self._tf[doc_id]
        return sum(1 for t in tu if tf.get(t)) / len(tu)

    def search(
        self, query: str, *, top_k: int = 3,
        min_coverage: float = DO_PHU_TOI_THIEU,
        exclude: Iterable[str] = (),
    ) -> list[tuple[str, float]]:
        """Ứng viên đủ ĐỘ PHỦ, xếp theo điểm BM25 giảm dần rồi theo mã.

        Hai đại lượng, hai việc: độ phủ quyết định *có nhận không*, điểm BM25
        quyết định *xếp trước hay sau*. Dùng điểm cho cả hai việc là chỗ mà bản
        đầu tiên sai — điểm phụ thuộc cỡ kho nên một ngưỡng tuyệt đối trên nó
        sai ở cả kho nhỏ lẫn kho lớn.

        Sắp thêm theo MÃ khi điểm bằng nhau: hai trích đoạn cùng điểm phải cho
        ra cùng thứ tự ở mọi lần chạy, nếu không thì prompt đổi giữa hai lượt
        và thực nghiệm A/B không tái lập được.
        """
        bo = set(exclude)
        dat = [
            (ma, self.score(query, ma))
            for ma in self.docs
            if ma not in bo and self.coverage(query, ma) >= min_coverage
        ]
        dat.sort(key=lambda x: (-x[1], x[0]))
        return dat[:top_k]


@dataclass(frozen=True)
class Retrieved:
    """Một trích đoạn được chọn, kèm TẦNG đã tìm ra nó."""

    chunk_id: str
    tier: str
    score: float = 0.0

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Tầng quan hệ là bắc cầu trên dữ liệu dự án đã khai — SUY RA. Tầng BM25
        là trùng từ ngữ, tức một phỏng đoán rằng trùng từ nghĩa là liên quan —
        GIẢ ĐỊNH.
        """
        from eaa.confidence import GIA_DINH, SUY_RA

        return SUY_RA if self.tier == QUAN_HE else GIA_DINH

    def render(self) -> str:
        if self.tier == QUAN_HE:
            return f"  {self.chunk_id}  (đồ thị chỉ đích danh)"
        return f"  {self.chunk_id}  (BM25, điểm {self.score:.2f} — trùng từ, chưa chắc liên quan)"


def _truy_van(graph: Any, module_id: str) -> str:
    """Dựng câu truy vấn từ thứ module ĐỤNG TỚI, không từ tên module.

    Tên module là do người đặt và có thể chẳng nói gì (``drv_a``); thanh ghi và
    tài nguyên mới là thứ nói được module này cần đọc gì.
    """
    phan: list[str] = []
    if hasattr(graph, "registers_for"):
        phan += list(graph.registers_for(module_id))
    if hasattr(graph, "resources_of"):
        phan += list(graph.resources_of(module_id))
    return " ".join(phan)


def select_chunks(
    graph: Any,
    datasheets: Any,
    module_id: str,
    *,
    top_k: int = 3,
    min_coverage: float = DO_PHU_TOI_THIEU,
    enable_bm25: bool = True,
) -> list[Retrieved]:
    """Chọn trích đoạn cho một module: quan hệ trước, BM25 lấp chỗ trống.

    ``enable_bm25=False`` cho ra đúng hành vi trước khi có module này — hữu ích
    khi cần một kết quả chỉ phụ thuộc đồ thị, và để đo xem tầng 2 thêm được gì.
    """
    quan_he = list(graph.chunks_for(module_id, top_k=top_k))
    ket_qua = [Retrieved(chunk_id=c, tier=QUAN_HE) for c in quan_he]

    con_thieu = top_k - len(ket_qua)
    if con_thieu <= 0 or not enable_bm25 or datasheets is None:
        return ket_qua

    hoat_dong = datasheets.active() if hasattr(datasheets, "active") else []
    kho = {
        c.id: f"{getattr(c, 'topic', '')} {' '.join(getattr(c, 'registers', ()) or ())} "
        f"{getattr(c, 'peripheral', '')} {getattr(c, 'device', '')} {getattr(c, 'body', '')}"
        for c in hoat_dong
    }
    if not kho:
        return ket_qua

    truy_van = _truy_van(graph, module_id)
    if not truy_van.strip():
        return ket_qua

    for ma, diem in Bm25Index(kho).search(
        truy_van, top_k=con_thieu, min_coverage=min_coverage, exclude=quan_he
    ):
        ket_qua.append(Retrieved(chunk_id=ma, tier=BM25, score=diem))
    return ket_qua
