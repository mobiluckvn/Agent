"""TC-64 — BM25 làm tầng 2 của truy xuất, đặt SAU tầng quan hệ (AIS §4.2, ADR-07).

Module `eaa/rag.py` được ghi là "hoãn có chủ ý" từ Sprint 1 (SL-06). Nó tồn tại
để lấp một chỗ hở cụ thể: trích đoạn có nội dung liên quan mà **đồ thị chưa có
cạnh nào dẫn tới** — thường vì dự án chưa khai `configured_by` cho một linh
kiện, hoặc vì tài liệu nói về một khái niệm chứ không về một thanh ghi.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-64a | Tầng quan hệ chạy trước và luôn thắng | thứ tự không đảo được |
| TC-64b | BM25 chỉ lấp chỗ CÒN TRỐNG | không đẩy được ai ra |
| TC-64c | Ngưỡng ĐỘ PHỦ chặn ứng viên chỉ trùng vài từ chung | không phụ thuộc cỡ kho |
| TC-64d | BM25 tìm được thứ đồ thị bỏ sót | lý do module này tồn tại |
| TC-64e | Kết quả tất định | cùng đầu vào → cùng prompt |
| TC-64f | Tên thanh ghi KHÔNG bị tách theo gạch dưới | `WHO_AM_I` là một định danh |
| TC-64g | Thêm tầng 2 KHÔNG làm tụt precision của bộ chuẩn TC-20 | |

TC-64c là điều giữ cho tầng 2 khỏi thành tầng nhiễu. Không có ngưỡng, BM25 luôn
lấp đủ `top_k` bằng thứ tốt nhất nó tìm được — kể cả khi thứ tốt nhất ấy chẳng
liên quan gì, và một prompt lấp đủ ba chỗ bằng hai chỗ vô nghĩa còn tệ hơn một
prompt chỉ có một chỗ đúng.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.confidence import GIA_DINH, SUY_RA
from eaa.rag import BM25, DO_PHU_TOI_THIEU, QUAN_HE, Bm25Index, select_chunks, tokenize

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


class _Chunk:
    def __init__(self, ma: str, topic: str, registers=(), peripheral="", body="") -> None:
        self.id = ma
        self.topic = topic
        self.registers = registers
        self.peripheral = peripheral
        self.device = ""
        self.body = body


class _Kho:
    def __init__(self, *chunks: _Chunk) -> None:
        self._c = chunks

    def active(self):
        return list(self._c)

    def get(self, ma: str):
        return next(c for c in self._c if c.id == ma)


class _DoThiGia:
    """Đồ thị giả: trả về đúng thứ được dựng sẵn."""

    def __init__(self, chunks: list[str], registers=(), resources=()) -> None:
        self._chunks = chunks
        self._registers = list(registers)
        self._resources = list(resources)

    def chunks_for(self, module_id: str, top_k: int = 3):
        return self._chunks[:top_k]

    def registers_for(self, module_id: str):
        return self._registers

    def resources_of(self, module_id: str):
        return self._resources


# --------------------------------------------------------------------------
# TC-64f — tách từ giữ được định danh kỹ thuật
# --------------------------------------------------------------------------


def test_ten_thanh_ghi_khong_bi_tach_theo_gach_duoi() -> None:
    """`who`, `am`, `i` là ba từ vô nghĩa; `who_am_i` là một định danh."""
    assert "who_am_i" in tokenize("WHO_AM_I và PWR_MGMT_1")
    assert "pwr_mgmt_1" in tokenize("WHO_AM_I và PWR_MGMT_1")
    assert "who" not in tokenize("WHO_AM_I")


def test_bo_tu_qua_ngan() -> None:
    assert tokenize("a bc def") == ["bc", "def"]


def test_tach_tu_khong_phan_biet_hoa_thuong() -> None:
    assert tokenize("TWBR") == tokenize("twbr")


# --------------------------------------------------------------------------
# TC-64a, TC-64b — thứ tự hai tầng
# --------------------------------------------------------------------------


def test_tang_quan_he_chay_truoc_va_giu_nguyen_thu_tu() -> None:
    kho = _Kho(_Chunk("ds-1", "a"), _Chunk("ds-2", "b"), _Chunk("ds-3", "c"))
    g = _DoThiGia(["ds-3", "ds-1", "ds-2"], registers=["REG_X"])
    ket = select_chunks(g, kho, "m", top_k=3)

    assert [r.chunk_id for r in ket] == ["ds-3", "ds-1", "ds-2"]
    assert all(r.tier == QUAN_HE for r in ket)


def test_tang_quan_he_day_du_thi_KHONG_goi_bm25() -> None:
    """BM25 không đẩy được ai ra — nó chỉ lấp chỗ trống."""
    kho = _Kho(*[_Chunk(f"ds-{i}", "twbr twcr") for i in range(1, 6)])
    g = _DoThiGia(["ds-1", "ds-2", "ds-3"], registers=["TWBR", "TWCR"])
    ket = select_chunks(g, kho, "m", top_k=3)

    assert len(ket) == 3
    assert all(r.tier == QUAN_HE for r in ket)


def test_bm25_khong_lay_lai_chunk_tang_1_da_lay() -> None:
    kho = _Kho(_Chunk("ds-1", "twbr"), _Chunk("ds-2", "twbr twcr twsr"))
    g = _DoThiGia(["ds-1"], registers=["TWBR", "TWCR", "TWSR"])
    ket = select_chunks(g, kho, "m", top_k=3)

    ma = [r.chunk_id for r in ket]
    assert ma.count("ds-1") == 1


# --------------------------------------------------------------------------
# TC-64c — ngưỡng độ phủ
# --------------------------------------------------------------------------


def test_nguong_do_phu_chan_ung_vien_chi_trung_tu_chung() -> None:
    """Một prompt lấp đủ ba chỗ bằng hai chỗ vô nghĩa tệ hơn một chỗ đúng."""
    kho = _Kho(
        _Chunk("ds-lien-quan", "cấu hình bộ đếm", registers=("TCCR1A", "TCCR1B")),
        _Chunk("ds-vo-can", "hướng dẫn hàn linh kiện", body="dùng mỏ hàn nhiệt độ"),
    )
    g = _DoThiGia([], registers=["TCCR1A", "TCCR1B"])
    ket = select_chunks(g, kho, "m", top_k=3)

    assert [r.chunk_id for r in ket] == ["ds-lien-quan"]


def test_ha_nguong_thi_nhieu_lot_vao() -> None:
    """Chứng minh ngưỡng là thứ đang chặn, không phải một sự may mắn."""
    kho = _Kho(
        _Chunk("ds-lien-quan", "bộ đếm", registers=("TCCR1A", "TCCR1B")),
        _Chunk("ds-mo", "bộ đếm thời gian nói chung"),
    )
    g = _DoThiGia([], registers=["TCCR1A", "TCCR1B"])

    chat = select_chunks(g, kho, "m", top_k=3)
    long_ = select_chunks(g, kho, "m", top_k=3, min_coverage=0.0)

    assert len(long_) > len(chat)


def test_nguong_khong_phu_thuoc_co_kho() -> None:
    """Bản đầu dùng sàn ĐIỂM và sai đúng ở đây: điểm co lại khi kho nhỏ.

    Cùng một mức khớp hoàn hảo, kho hai tài liệu và kho hai mươi tài liệu phải
    cho cùng một phán quyết NHẬN — dù điểm BM25 của chúng khác nhau nhiều lần.
    """
    nho = {"a": "tccr1a tccr1b", "b": "chuyện khác hẳn"}
    lon = {**{f"x{i}": "chuyện khác hẳn" for i in range(20)}, "a": "tccr1a tccr1b"}

    for kho in (nho, lon):
        idx = Bm25Index(kho)
        assert idx.coverage("TCCR1A TCCR1B", "a") == 1.0
        assert [m for m, _ in idx.search("TCCR1A TCCR1B", top_k=3)] == ["a"]


def test_nguong_mac_dinh_la_mot_ti_le_co_that() -> None:
    assert 0.0 < DO_PHU_TOI_THIEU < 1.0


# --------------------------------------------------------------------------
# TC-64d — lấp đúng chỗ hở mà module này sinh ra để lấp
# --------------------------------------------------------------------------


def test_bm25_tim_duoc_thu_do_thi_bo_sot() -> None:
    """Trích đoạn liên quan mà đồ thị chưa có cạnh nào dẫn tới.

    Đây đúng là cảnh xảy ra khi dự án quên khai `configured_by` cho một linh
    kiện — chính là lỗi mà TC-20 tìm ra ở lượt chạy đầu tiên.
    """
    kho = _Kho(
        _Chunk(
            "ds-cam-bien",
            "khởi động cảm biến quán tính",
            registers=("WHO_AM_I", "PWR_MGMT_1"),
            peripheral="imu",
        )
    )
    g = _DoThiGia([], registers=["WHO_AM_I", "PWR_MGMT_1"], resources=["imu"])
    ket = select_chunks(g, kho, "drv_bus", top_k=3)

    assert [r.chunk_id for r in ket] == ["ds-cam-bien"]
    assert ket[0].tier == BM25
    assert ket[0].score > 0


def test_ket_qua_bm25_duoc_danh_dau_la_phong_doan() -> None:
    kho = _Kho(_Chunk("ds-1", "bộ đếm", registers=("TCCR1A",)))
    g = _DoThiGia([], registers=["TCCR1A"])
    r = select_chunks(g, kho, "m")[0]

    assert r.confidence_level == GIA_DINH
    assert "chưa chắc liên quan" in r.render()


def test_ket_qua_tang_quan_he_manh_hon() -> None:
    kho = _Kho(_Chunk("ds-1", "x"))
    g = _DoThiGia(["ds-1"], registers=["R"])
    r = select_chunks(g, kho, "m")[0]

    assert r.confidence_level == SUY_RA
    assert "đồ thị chỉ đích danh" in r.render()


def test_module_khong_dung_tai_nguyen_nao_thi_khong_goi_bm25() -> None:
    """Câu truy vấn rỗng thì mọi trích đoạn đều cùng điểm — chọn là chọn bừa."""
    kho = _Kho(_Chunk("ds-1", "gì đó"), _Chunk("ds-2", "gì khác"))
    g = _DoThiGia([], registers=[], resources=[])
    assert select_chunks(g, kho, "lib_toan", top_k=3) == []


def test_kho_rong_thi_khong_no() -> None:
    g = _DoThiGia([], registers=["R"])
    assert select_chunks(g, _Kho(), "m") == []
    assert select_chunks(g, None, "m") == []


# --------------------------------------------------------------------------
# TC-64e — tất định
# --------------------------------------------------------------------------


def test_ket_qua_tat_dinh() -> None:
    """Cùng đầu vào phải cho cùng prompt, nếu không A/B không tái lập được."""
    kho = _Kho(*[_Chunk(f"ds-{i}", "twbr twcr twsr") for i in range(1, 6)])
    g = _DoThiGia([], registers=["TWBR", "TWCR", "TWSR"])

    a = [r.chunk_id for r in select_chunks(g, kho, "m", top_k=3)]
    b = [r.chunk_id for r in select_chunks(g, kho, "m", top_k=3)]
    assert a == b


def test_diem_bang_nhau_thi_sap_theo_ma() -> None:
    kho = {f"ds-{i}": "twbr twcr" for i in (3, 1, 2)}
    ket = Bm25Index(kho).search("twbr twcr", top_k=3)
    assert [m for m, _ in ket] == ["ds-1", "ds-2", "ds-3"]


def test_bm25_cho_diem_cao_hon_cho_tai_lieu_dung_chu_de() -> None:
    kho = {
        "dung": "twbr twsr twcr cấu hình tốc độ bit bus hai dây",
        "lac": "tccr1a tccr1b bộ đếm chế độ ctc",
    }
    idx = Bm25Index(kho)
    assert idx.score("TWBR TWSR", "dung") > idx.score("TWBR TWSR", "lac")


# --------------------------------------------------------------------------
# TC-64g — không làm tụt bộ chuẩn TC-20
# --------------------------------------------------------------------------


def test_them_tang_2_khong_lam_tut_precision() -> None:
    from eaa.cli import build_context
    from eaa.goldenset import GOLDEN_FILE, PRECISION_TOI_THIEU, GoldenSet

    ctx = build_context(DU_AN)
    bo = GoldenSet.load(DU_AN / GOLDEN_FILE)

    chi_do_thi = bo.evaluate(ctx.graph)
    ca_hai = bo.evaluate(ctx.graph, datasheets=ctx.kb.datasheets)

    assert ca_hai.precision_at_k >= chi_do_thi.precision_at_k
    assert ca_hai.precision_at_k >= PRECISION_TOI_THIEU
    assert ca_hai.noise_leaks == (), ca_hai.render()


def test_bo_chon_van_biet_DUNG_khi_het_thu_lien_quan() -> None:
    """Tính chất này dễ mất nhất khi thêm một tầng lấp chỗ trống."""
    from eaa.cli import build_context
    from eaa.rag import select_chunks as chon

    ctx = build_context(DU_AN)
    ctx.graph.add_module("drv_timer_tick", uses=["timer1"])
    ket = chon(ctx.graph, ctx.kb.datasheets, "drv_timer_tick", top_k=3)

    assert len(ket) < 3, "chỉ một trích đoạn liên quan tới timer1"
