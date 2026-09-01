"""TC-94 — một phép kiểm KHÔNG KIỂM GÌ phải là KHÔNG ĐẠT.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-120.

Đây là lỗi nặng nhất tìm được trong cả bốn sprint, và nó nằm ở chặng cuối.

`eaa flash` báo *"Đã nạp sha256:1de31df1baac… lên /dev/cu.usbserial-143410"* rồi
*"Kiểm sau khi nạp: ĐÃ KIỂM — đọc ngược khớp ảnh"*. Sự thật, chạy tay đúng lệnh
pack khai:

    Error: cannot use build/diag_DS-04.hex as an ELF input file
    Reading 0 bytes for flash from input file diag_DS-04.hex
    mã thoát: 0

**Không byte nào từng được ghi xuống chip**, cả hai phiên làm việc. Bo vẫn chạy
firmware gốc của bộ kit suốt thời gian ấy.

Ba khiếm khuyết chồng lên nhau:

1. Sai chữ định dạng: ``flash:w:{binary}:e`` khai tệp là ELF, trong khi nó là
   Intel HEX. Chữ đúng là ``i``.
2. Công cụ **thoát 0** dù in ra dòng ``Error:`` — và pack tin ``exit == 0``.
3. ``error_regex`` của pack chờ ``^avrdude:\\s+error``, còn bản 8.2 in
   ``Error: …``. Dòng lỗi **vô hình** với lớp phân tích.

Bài này canh cái bao trùm cả ba, và là cái duy nhất còn đúng khi công cụ đổi
phiên bản hay đổi câu chữ: **xử lý 0 byte thì không phải là đạt.** Một phép
kiểm chỉ có ý nghĩa khi nó chứng minh được nó đã làm việc gì đó.
"""

from __future__ import annotations

import pytest

from eaa.platform import PackError, ParseSpec
from eaa.tools.runner import ToolRunner


DAU_RA_0_BYTE = (
    "Error: cannot use build/anh.hex as an ELF input file\n"
    "Reading 0 bytes for flash from input file anh.hex\n"
    "\nAvrdude done.  Thank you.\n"
)

DAU_RA_THAT = (
    "Reading 974 bytes for flash from input file anh.hex\n"
    "Writing 974 bytes to flash\n"
    "974 bytes of flash written\n"
    "Avrdude done.  Thank you.\n"
)


# ═══════════ luật chung: đòi BẰNG CHỨNG ĐÃ LÀM VIỆC ═══════════


def test_parse_nhan_require_regex() -> None:
    """Pack khai được "muốn ĐẠT thì đầu ra phải có dấu hiệu này"."""
    p = ParseSpec(require_regex=r"\b([1-9]\d*) bytes of flash (?:written|verified)\b")
    assert p.require_regex


def test_require_regex_sai_cu_phap_thi_BAO_NGAY() -> None:
    with pytest.raises(PackError):
        ParseSpec(require_regex="(((")


def test_thieu_dau_hieu_thi_KHONG_DAT_du_ma_thoat_0() -> None:
    """Điểm cốt lõi. Mã thoát 0 KHÔNG phải bằng chứng đã làm việc.

    Công cụ có quyền coi "không có gì để làm" là thành công. Người gọi thì
    không: với một cổng kiểm chứng, "không kiểm gì" và "kiểm và thấy khớp" là
    hai kết cục trái ngược, và gộp chúng lại là nói dối bằng đúng cái từ mà
    người đọc tin nhất.
    """
    parse = ParseSpec(
        success_exit_codes=(0,),
        require_regex=r"\b([1-9]\d*) bytes",
    )
    bao_cao = ToolRunner.doc_ket_qua(parse, exit_code=0, output=DAU_RA_0_BYTE)
    assert bao_cao.passed is False
    ly_do = " ".join(str(getattr(e, "message", e)) for e in bao_cao.errors)
    assert "0" in ly_do or "không" in ly_do.lower()


def test_co_dau_hieu_thi_DAT() -> None:
    parse = ParseSpec(success_exit_codes=(0,), require_regex=r"\b([1-9]\d*) bytes")
    assert ToolRunner.doc_ket_qua(parse, exit_code=0, output=DAU_RA_THAT).passed is True


def test_khong_khai_require_thi_giu_nguyen_hanh_vi_cu() -> None:
    """Thêm luật mới không được đổi ngầm kết cục của những pack chưa khai nó."""
    parse = ParseSpec(success_exit_codes=(0,))
    assert ToolRunner.doc_ket_qua(parse, exit_code=0, output=DAU_RA_0_BYTE).passed is True


def test_ma_thoat_xau_van_KHONG_DAT_du_co_dau_hieu() -> None:
    parse = ParseSpec(success_exit_codes=(0,), require_regex=r"\b([1-9]\d*) bytes")
    assert ToolRunner.doc_ket_qua(parse, exit_code=1, output=DAU_RA_THAT).passed is False


# ═══════════ pack AVR: chữ định dạng và biểu thức lỗi ═══════════


def _nang_luc(ten: str):
    from pathlib import Path

    from eaa.platform import load_manifest

    m = load_manifest(Path(__file__).resolve().parents[1] / "packs" / "avr")
    return m.invocation(ten)


@pytest.mark.parametrize("ten", ["flash", "flash_verify"])
def test_pack_khai_dung_chu_dinh_dang_tep(ten: str) -> None:
    """`:e` là ELF. Ảnh nạp của pack này là Intel HEX, nên phải là `:i`.

    Sai một chữ, và công cụ đọc 0 byte rồi báo thành công.
    """
    lenh = " ".join(_nang_luc(ten).command)
    assert ":e" not in lenh, f"{ten}: còn khai định dạng ELF cho một tệp Intel HEX"
    assert ":i" in lenh, f"{ten}: chưa khai định dạng Intel HEX"


@pytest.mark.parametrize("ten", ["flash", "flash_verify"])
def test_pack_doi_bang_chung_da_lam_viec(ten: str) -> None:
    """Hai năng lực chạm phần cứng này KHÔNG được đạt bằng mã thoát suông."""
    parse = _nang_luc(ten).parse
    assert parse.require_regex, (
        f"{ten}: chưa đòi dấu hiệu nào chứng minh công cụ đã thật sự làm việc"
    )


@pytest.mark.parametrize("ten", ["flash", "flash_verify"])
def test_error_regex_bat_duoc_dinh_dang_loi_doi_moi(ten: str) -> None:
    """avrdude 8.2 in `Error: …`, không phải `avrdude: error: …`.

    Biểu thức chỉ khớp định dạng cũ làm dòng lỗi VÔ HÌNH với lớp phân tích —
    và một lớp phân tích không thấy lỗi thì nó không phải lớp phân tích.
    """
    import re

    mau = _nang_luc(ten).parse.error_regex
    assert mau, f"{ten}: không có error_regex"
    bd = re.compile(mau, re.M)
    assert bd.search("Error: cannot use build/anh.hex as an ELF input file"), \
        f"{ten}: không bắt được định dạng lỗi của avrdude đời mới"
    assert bd.search("avrdude: error: could not open port"), \
        f"{ten}: bỏ mất định dạng lỗi đời cũ"


def test_dau_ra_0_byte_that_bi_pack_AVR_cham_KHONG_DAT() -> None:
    """Ráp cả ba lại: đúng đầu ra thật đã lừa được cả hai phiên làm việc."""
    parse = _nang_luc("flash").parse
    assert ToolRunner.doc_ket_qua(parse, exit_code=0, output=DAU_RA_0_BYTE).passed is False
