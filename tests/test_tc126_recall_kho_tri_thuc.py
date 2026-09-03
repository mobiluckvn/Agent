"""TC-126 — kho tri thức phải ĐỌC RA ĐƯỢC bằng một câu hỏi, không chỉ ghi vào.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-166.

Trước bản này ``eaa/rag.py`` chỉ có đúng hai chỗ gọi: ``composer`` (đường sinh
mã) và ``goldenset`` (đo chất lượng truy xuất). Ở tầm hỏi-đáp không có đường
nào tới trích đoạn đã duyệt G2 — nên một câu hỏi của người dùng chỉ còn hai
lối: trí nhớ mô hình, hoặc ra web. Cả hai đều đi vòng qua đúng thứ đã có người
đối chiếu với bản gốc.

| Mã | Yêu cầu | Vì sao mất thì nguy |
|---|---|---|
| TC-126a | Tầng quan hệ chạy khi câu hỏi gọi TÊN một module | chỉ đích danh thì đúng theo định nghĩa |
| TC-126b | Không nhắc module nào thì BM25 làm nốt | câu hỏi thường không có mã module |
| TC-126c | Tên module khớp theo TỪ, không theo chuỗi con | `drv_i2c` không được kéo theo `drv_i2c_mpu6050` |
| TC-126d | Chunk `proposed` KHÔNG bao giờ vào kết quả | chưa ai chịu trách nhiệm về nó |
| TC-126e | Ngưỡng độ phủ vẫn chặn thứ chỉ trùng vài từ | kết quả rỗng thật thà hơn kết quả lấp đầy |
| TC-126f | `recall` có trong danh mục Agent, đứng TRƯỚC `research` | tra kho trước, ra web sau |
| TC-126g | `recall` không mở thêm quyền nào | thêm lệnh không được thành thêm quyền |
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eaa.agent import NGOAI_DANH_MUC, TOOLBOX, _mo_ta_danh_muc
from eaa.rag import BM25, QUAN_HE, search_chunks


@dataclass
class _Chunk:
    id: str
    topic: str = ""
    body: str = ""
    device: str = "atmega328p"
    peripheral: str = ""
    registers: tuple[str, ...] = ()
    status: str = "approved"

    @property
    def is_active(self) -> bool:
        return self.status == "approved"


@dataclass
class _Kho:
    muc: list[_Chunk] = field(default_factory=list)

    def all(self) -> list[_Chunk]:
        return list(self.muc)

    def active(self) -> list[_Chunk]:
        return [c for c in self.muc if c.is_active]


@dataclass
class _Do_thi:
    """Đồ thị giả — chỉ hai phép mà ``search_chunks`` thật sự dùng."""

    modules: tuple[str, ...] = ()
    theo_module: dict = field(default_factory=dict)

    def nodes_of_kind(self, kind: str) -> list[str]:
        return list(self.modules) if kind == "module" else []

    def chunks_for(self, module_id: str, top_k: int = 3) -> list[str]:
        return list(self.theo_module.get(module_id, ()))[:top_k]


def _kho_mau() -> _Kho:
    return _Kho([
        _Chunk("ds-twi", topic="TWI tốc độ bit", peripheral="twi",
               registers=("TWBR", "TWSR"),
               body="Công thức f_SCL phụ thuộc TWBR và hệ số chia trước TWPS"),
        _Chunk("ds-imu", topic="MPU6050 thanh ghi số đo", peripheral="imu",
               registers=("ACCEL_XOUT_H",),
               body="Byte cao gia tốc trục X nằm ở địa chỉ 0x3B"),
        _Chunk("ds-uart", topic="USART khung truyền", peripheral="usart0",
               registers=("UBRR0H",),
               body="Hệ số chia tốc độ baud tính từ tần số dao động"),
    ])


# ══════════════════════ hai tầng, đúng thứ tự ══════════════════════


def test_tc126a_cau_hoi_goi_ten_module_thi_do_thi_chi_dich_danh():
    do_thi = _Do_thi(modules=("drv_imu", "drv_i2c"),
                     theo_module={"drv_imu": ("ds-imu",)})

    ket = search_chunks(_kho_mau(), "drv_imu đọc góc nghiêng thế nào", graph=do_thi)

    assert ket[0].chunk_id == "ds-imu"
    assert ket[0].tier == QUAN_HE
    assert ket[0].confidence_level == "SUY RA"


def test_tc126b_khong_nhac_module_nao_thi_bm25_lam_not():
    ket = search_chunks(_kho_mau(), "TWBR đặt bao nhiêu", graph=_Do_thi())

    assert [r.chunk_id for r in ket] == ["ds-twi"]
    assert ket[0].tier == BM25
    assert ket[0].confidence_level == "GIẢ ĐỊNH"


def test_tc126c_ten_module_khop_theo_tu_khong_theo_chuoi_con():
    """`drv_i2c` nằm trong `drv_i2c_mpu6050` — khớp chuỗi con là kéo nhầm kho."""
    do_thi = _Do_thi(
        modules=("drv_i2c", "drv_i2c_mpu6050"),
        theo_module={"drv_i2c": ("ds-twi",), "drv_i2c_mpu6050": ("ds-imu",)},
    )

    ket = search_chunks(_kho_mau(), "drv_i2c_mpu6050 khởi động ra sao", graph=do_thi)

    assert "ds-imu" in [r.chunk_id for r in ket]
    assert "ds-twi" not in [r.chunk_id for r in ket]


def test_tc126d_chunk_cho_duyet_khong_bao_gio_vao_ket_qua():
    """Cùng luật mà `select_chunks` áp cho đường sinh mã, không nới ở đây."""
    kho = _kho_mau()
    kho.muc.append(
        _Chunk("ds-cho", topic="TWBR bản chờ duyệt", registers=("TWBR",),
               body="TWBR đặt bằng 12", status="proposed")
    )

    ket = search_chunks(kho, "TWBR đặt bao nhiêu", graph=_Do_thi())

    assert "ds-cho" not in [r.chunk_id for r in ket]


def test_tc126e_nguong_do_phu_van_chan_thu_chi_trung_vai_tu():
    """Lấp đủ top_k bằng thứ vô nghĩa còn tệ hơn trả về ít."""
    ket = search_chunks(_kho_mau(), "watchdog nội bị treo", graph=_Do_thi(), top_k=5)

    assert ket == []


def test_tc126_khong_co_do_thi_van_chay():
    """Dự án chưa dựng đồ thị thì tầng 2 vẫn phải trả lời được."""
    ket = search_chunks(_kho_mau(), "TWBR đặt bao nhiêu", graph=None)

    assert [r.chunk_id for r in ket] == ["ds-twi"]


# ══════════════════════ chỗ đứng trong danh mục Agent ══════════════════════


def test_tc126f_recall_co_trong_danh_muc_va_dung_truoc_research():
    ten = [t.argv for t in TOOLBOX]
    assert ("recall",) in ten

    # Thứ tự trong bảng "KHI THIẾU THÔNG TIN" là thứ dạy mô hình tra kho trước.
    # So vị trí TRONG bảng ấy, không so trong cả prompt: `research` còn xuất
    # hiện ở phần mô tả công cụ phía trên, nên so cả prompt là so nhầm chỗ.
    bang = _mo_ta_danh_muc().split("## THỨ TỰ NÊN THEO KHI THIẾU THÔNG TIN")[-1]
    assert "`recall" in bang
    assert bang.index("`recall") < bang.index("`research`")


def test_tc126_recall_la_lenh_chi_doc():
    """Tra kho không ghi gì — xếp nó vào nhóm có ghi là khai sai về chính nó."""
    (muc,) = [t for t in TOOLBOX if t.argv == ("recall",)]
    assert muc.writes is False


def test_tc126g_them_lenh_khong_duoc_thanh_them_quyen():
    """Bất biến trung tâm: không lệnh DUYỆT nào lọt vào danh mục."""
    co_mat = {" ".join(t.argv) for t in TOOLBOX}
    for cam in ("gate approve", "gate reject", "flash approve", "doctor approve",
                "tool approve", "skill approve"):
        assert cam not in co_mat
    assert "datasheet add" not in co_mat
    assert "gate" in NGOAI_DANH_MUC


def test_tc126_resolve_khai_dung_la_lenh_co_ghi():
    """Bậc 3 của `resolve` dựng chunk đề xuất trên đĩa — nó KHÔNG chỉ đọc."""
    (muc,) = [t for t in TOOLBOX if t.argv == ("resolve",)]
    assert muc.writes is True
    assert "--web" in muc.takes
