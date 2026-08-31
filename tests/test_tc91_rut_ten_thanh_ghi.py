"""TC-91 — bộ rút tên thanh ghi không thấy dạng viết CHUNG của datasheet.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-116.

Tìm ra khi nạp datasheet chính chủ để lấp chỗ thiếu của Bài 1. Trích đúng bốn
trang mục *Register Description* của khối nối tiếp, và kết quả:

    Thanh ghi đoán được: DS40002061B, USART, TXB, RXB, FIFO, SBI, CBI, SBIC,
                         SBIS, SREG, SPI, MSPIM

Không một tên thanh ghi thật nào. Toàn từ viết tắt và **mã số hiệu tài liệu**.

Nguyên nhân: biểu thức nhận dạng là ``\\b[A-Z][A-Z0-9_]{2,}\\b`` — chỉ chữ hoa.
Nhưng datasheet của các họ vi điều khiển có ngoại vi **nhiều thực thể** không
viết tên thanh ghi kèm số hiệu cụ thể; nó viết dạng chung, chèn một chữ thường
làm chỗ giữ số hiệu. Mọi tên như vậy đều bị loại vì có một chữ thường.

Hệ quả không dừng ở một dòng in xấu. Trường ``registers`` của chunk là thứ
Knowledge Graph dùng dựng cạnh ``thanh ghi –documented_in→ chunk``. Một chunk
mang danh sách thanh ghi SAI thì **không bao giờ được truy xuất cho module cần
nó** — đường nạp tri thức sinh ra một trích đoạn mà chính phép truy xuất nó
phục vụ không tìm thấy.

Và nó hỏng đúng ở lớp ngoại vi mà dự án này dùng: cổng nối tiếp, bus hai dây,
bộ đếm thời gian — tất cả đều là loại nhiều thực thể.
"""

from __future__ import annotations

import pytest

from eaa.ingest import _doan_thanh_ghi

# Mẫu viết theo ĐÚNG lối các datasheet dùng chỗ giữ số hiệu, nhưng dùng tên
# BỊA — engine không được chứa tên thanh ghi thật (TC-38).
VAN_BAN = """\
DS12345678X-page 200

24.11 Register Description

24.11.1 ABCn – Peripheral I/O Data Register n
The ABCn register is the buffer. Writing to ABCn sets the transmit buffer.

24.11.2 DEFnA – Peripheral Control and Status Register n A
• Bit 7 – GHIn: Receive Complete
• Bit 5 – JKLn: Data Register Empty
The DEFnA register holds the flags. See also DEFnB and DEFnC.

24.11.3 MNOnH and MNOnL – Baud Rate Registers
"""


def test_thay_ten_dang_CHUNG_co_cho_giu_so_hieu() -> None:
    """Đây là dạng datasheet thật dùng, và trước SL-116 nó bị loại sạch."""
    thay = _doan_thanh_ghi(VAN_BAN)

    for ten in ("ABCn", "DEFnA", "DEFnB", "DEFnC", "MNOnH", "MNOnL"):
        assert ten in thay, f"bỏ sót tên dạng chung: {ten} (thấy: {thay})"


def test_thay_ca_ten_co_bit_dang_chung() -> None:
    """Cờ trạng thái cũng viết cùng lối, và mã cấu hình phải trích dẫn được chúng."""
    thay = _doan_thanh_ghi(VAN_BAN)
    assert "GHIn" in thay and "JKLn" in thay


def test_KHONG_nhat_ma_so_hieu_tai_lieu() -> None:
    """`DS12345678X` là số hiệu bản in, không phải thanh ghi.

    Nó lọt vào vì trông giống: chữ hoa, có số, đủ dài. Nhưng nó xuất hiện ở
    CHÂN TRANG của mọi trang, nên nó gần như luôn đứng đầu danh sách và đẩy
    tên thật ra khỏi phần bị cắt.
    """
    thay = _doan_thanh_ghi(VAN_BAN)
    assert not any(t.startswith("DS") and any(c.isdigit() for c in t) for t in thay), \
        f"nhặt cả mã số hiệu tài liệu: {thay}"


def test_ten_that_duoc_XEP_TRUOC_tu_viet_tat() -> None:
    """Danh sách bị cắt còn 12 mục, nên THỨ TỰ quyết định cái gì sống sót.

    Từ viết tắt của văn xuôi kỹ thuật xuất hiện dày hơn tên thanh ghi rất
    nhiều. Xếp theo thứ tự xuất hiện thì chúng chiếm hết chỗ, và người đọc
    nhận một danh sách trông đầy đủ mà không có gì dùng được.
    """
    nhieu_nhieu = "SPI FIFO SREG SBI CBI USART MCU CPU XTAL PWM ADC UART " + VAN_BAN
    thay = _doan_thanh_ghi(nhieu_nhieu)
    assert "ABCn" in thay, f"tên thật bị từ viết tắt đẩy ra ngoài: {thay}"
    assert "DEFnA" in thay


def test_van_giu_duoc_ten_toan_CHU_HOA() -> None:
    """Không được sửa thành chỉ nhận dạng chung — nhiều chip viết tên đầy đủ."""
    thay = _doan_thanh_ghi("Thanh ghi PQR7 và STU12A điều khiển khối này.")
    assert "PQR7" in thay and "STU12A" in thay


def test_khong_nhat_tu_thuong_va_tu_tieng_Anh() -> None:
    thay = _doan_thanh_ghi("The Register Description section describes Data Sheet items.")
    assert thay == (), f"nhặt cả chữ thường/từ thường: {thay}"


# ═══════════ ranh giới engine ═══════════


def test_khong_co_ten_thanh_ghi_that_trong_module() -> None:
    """TC-38 quét cả kho; bài này canh riêng chỗ vừa sửa."""
    from pathlib import Path

    nguon = (Path(__file__).resolve().parents[1] / "eaa" / "ingest.py").read_text(
        encoding="utf-8"
    ).lower()
    for cam in ("udr0", "ucsr0a", "ubrr0h", "twbr", "tccr1a", "atmega"):
        assert cam not in nguon, f"engine chứa tên thanh ghi/chip cụ thể: {cam}"


# ═══════════ tên dạng chung phải được NÊU RA, không để im lặng ═══════════


def test_ten_dang_CHUNG_bi_canh_bao_de_ky_su_chuan_hoa() -> None:
    """Đồ thị tri thức so khớp theo TÊN, nên tên dạng chung là ngõ cụt im lặng.

    Chunk khai ``ABCn`` còn hồ sơ phần cứng khai ``ABC0`` thì cạnh
    ``thanh ghi –documented_in→ chunk`` không bao giờ nối được. Chunk vẫn ở đó,
    vẫn qua G2, vẫn trông như một trích đoạn tốt — và phép truy xuất nó sinh ra
    để phục vụ không tìm thấy nó.

    Chuẩn hóa là việc của kỹ sư tại G2 (chỉ dự án mới biết ngoại vi này là thực
    thể số mấy). Nhưng KHÔNG NÓI RA thì kỹ sư không biết có việc phải làm.
    """
    from eaa.ingest import canh_bao_ten_chung

    canh = canh_bao_ten_chung(("ABCn", "DEFnA", "PQR7"))
    assert canh, "không cảnh báo gì về tên dạng chung"
    assert "ABCn" in canh and "DEFnA" in canh
    assert "PQR7" not in canh, "tên đã gắn số hiệu thì không phải chuẩn hóa"
    assert "chuẩn hóa" in canh.lower() or "chuẩn hoá" in canh.lower()


def test_ten_da_gan_so_hieu_thi_KHONG_canh_bao() -> None:
    """Cảnh báo bắn vào mọi trường hợp là cảnh báo bị bỏ qua."""
    from eaa.ingest import canh_bao_ten_chung

    assert canh_bao_ten_chung(("PQR7", "STU12A")) == ""
