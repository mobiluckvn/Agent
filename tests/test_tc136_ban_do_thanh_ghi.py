"""TC-136 — bản đồ thanh ghi máy đọc được, và cổng `regcheck` (GĐ1, A2).

Xem `docs/KE_HOACH_VUOT_LEN.md` §2 và `docs/SAI_LECH_THIET_KE.md` mục SL-176.

Mỗi giá trị thanh ghi trong mã mang một dòng ``// ref:``, và cổng phân tích tĩnh
cưỡng chế dòng ấy phải có (TC-17). Nhưng nó chỉ kiểm **có trích dẫn hay không**
— một mã chunk hợp lệ dán lên một giá trị sai vẫn đi qua sạch.

Bản đồ do hãng phát hành là bảng **máy đọc được**, nên câu *"giá trị này có lọt
vừa trường bit ấy không"* trả lời được bằng máy.

Ba chuyện bài này canh
-----------------------

1. **Hai định dạng, MỘT mô hình.** SVD khai vị trí–độ rộng, ATDF khai mặt nạ.
   Đọc ra hai mô hình khác nhau thì mọi phép kiểm phía sau phải biết mình đang
   cầm cái nào — và nó sẽ quên.
2. **Bốn phép CHẶN, một phép CẢNH BÁO.** Chặn khi máy chứng minh được; cảnh báo
   khi phải suy từ ánh xạ do người khai.
3. **Vắng bản đồ thì mọi thứ chạy y như trước.** Luật 1 của kế hoạch, và là chỗ
   một tính năng mới hay làm hỏng đường chạy cũ nhất.

Tên thanh ghi trong tệp này là tên BỊA (`CTRL_A`, `STAT_A`) — cố ý, để bài kiểm
không phụ thuộc con chip nào và để nó nói đúng điều engine biết: mọi cái tên đều
đến từ tệp.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.regmap import RegmapError, doc_mask, nap_ban_do, tu_pack
from eaa.regmap_atdf import doc as doc_atdf
from eaa.regmap_svd import doc as doc_svd
from eaa.tools.base import CodeArtifact, Severity
from eaa.tools.regcheck import RegCheckGate

SVD = """<device><name>CHIP_X</name><peripherals>
 <peripheral><name>BUS0</name><registers>
  <register><name>CTRL_A</name><size>8</size><resetValue>0x00</resetValue>
   <access>read-write</access>
   <fields>
     <field><name>MODE</name><bitOffset>0</bitOffset><bitWidth>3</bitWidth></field>
     <field><name>EN</name><bitRange>[7:7]</bitRange></field>
     <field><name>PRE</name><lsb>4</lsb><msb>5</msb></field>
   </fields></register>
  <register><name>STAT_A</name><size>8</size><access>read-only</access></register>
 </registers></peripheral></peripherals></device>"""

ATDF = """<avr-tools-device-file><devices><device name="CHIP_Y"/></devices><modules>
 <module name="BUS0"><register-group name="BUS0">
  <register name="CTRL_A" offset="0xB8" size="1" initval="0x00" rw="RW">
    <bitfield name="MODE" mask="0x07" rw="RW"/>
    <bitfield name="PRE" mask="0x30" rw="RW"/>
  </register>
  <register name="STAT_A" size="1" rw="R"/>
 </register-group></module></modules></avr-tools-device-file>"""


def _cong(**ghi_de):
    ghi_de.setdefault("regmap", doc_svd(SVD))
    return RegCheckGate(**ghi_de)


def _chay(cong, ma: str, ten: str = "src/drv_bus.c"):
    return cong.run(CodeArtifact(files={ten: ma}))


def _ma(rule_id: str, bao_cao) -> list:
    return [e for e in list(bao_cao.errors) + list(bao_cao.warnings)
            if e.rule_id == rule_id]


# ── đọc SVD ──────────────────────────────────────────────────────────────────


def test_doc_svd_du_ba_loi_khai_truong_bit() -> None:
    """Tệp thật dùng lẫn cả ba lối; đọc thiếu một lối là bỏ trống bản đồ mà
    KHÔNG báo gì — và bản đồ thiếu chỗ thì cổng im đúng chỗ nó cần nói."""
    r = doc_svd(SVD).get("CTRL_A")
    assert {f.name: (f.offset, f.width) for f in r.fields} == {
        "MODE": (0, 3),   # bitOffset + bitWidth
        "EN": (7, 1),     # bitRange
        "PRE": (4, 2),    # lsb + msb
    }


def test_doc_svd_lay_do_rong_va_quyen() -> None:
    m = doc_svd(SVD)
    assert m.device == "CHIP_X"
    assert m.get("CTRL_A").size_bits == 8
    assert m.get("CTRL_A").reset_value == 0
    assert m.get("STAT_A").ghi_duoc is False


def test_doc_svd_lay_ca_thanh_ghi_long_trong_cluster() -> None:
    """Chuẩn cho phép lồng `<cluster>`; tìm con trực tiếp sẽ mất sạch phần lồng."""
    x = """<device><name>C</name><peripherals><peripheral><name>P</name>
      <registers><cluster><name>G</name>
        <register><name>DEEP_A</name><size>8</size></register>
      </cluster></registers></peripheral></peripherals></device>"""
    assert doc_svd(x).get("DEEP_A") is not None


# ── đọc ATDF ─────────────────────────────────────────────────────────────────


def test_doc_atdf_suy_truong_tu_MAT_NA() -> None:
    r = doc_atdf(ATDF).get("CTRL_A")
    assert {f.name: (f.offset, f.width) for f in r.fields} == {
        "MODE": (0, 3),
        "PRE": (4, 2),
    }


def test_doc_atdf_doi_size_tu_BYTE_sang_BIT() -> None:
    """Nhầm đơn vị ở đây làm mọi phép kiểm độ rộng lệch tám lần — và lệch theo
    hướng NỚI, tức im lặng bỏ lọt."""
    assert doc_atdf(ATDF).get("CTRL_A").size_bits == 8


def test_doc_atdf_doc_quyen_tu_thuoc_tinh_rw() -> None:
    assert doc_atdf(ATDF).get("STAT_A").ghi_duoc is False


def test_mat_na_ngat_quang_tra_khoang_BAO_NGOAI() -> None:
    """Nới thì bỏ lọt, chặt thì báo nhầm — ở một bộ kiểm mới, báo nhầm giết nó."""
    assert doc_mask(0xA0) == (5, 3)
    assert doc_mask(0) == (0, 0)


def test_HAI_dinh_dang_cho_MOT_mo_hinh() -> None:
    """Khác nhau ở tên thiết bị thôi; phần phép kiểm dùng thì phải trùng khít."""
    a, b = doc_svd(SVD).get("CTRL_A"), doc_atdf(ATDF).get("CTRL_A")
    assert (a.size_bits, a.ghi_duoc) == (b.size_bits, b.ghi_duoc)
    for ten in ("MODE", "PRE"):
        fa, fb = a.truong(ten), b.truong(ten)
        assert (fa.offset, fa.width) == (fb.offset, fb.width)


# ── nạp từ tệp ───────────────────────────────────────────────────────────────


def test_xml_hong_la_loi_CAU_HINH_chu_khong_phai_loi_ma(tmp_path: Path) -> None:
    p = tmp_path / "x.svd"
    p.write_text("<device><name>", encoding="utf-8")
    with pytest.raises(RegmapError, match="XML hỏng"):
        nap_ban_do(p, "svd")


def test_thieu_tep_va_dinh_dang_la_bao_ro_rang(tmp_path: Path) -> None:
    with pytest.raises(RegmapError, match="Không có tệp"):
        nap_ban_do(tmp_path / "khong_co.svd", "svd")
    p = tmp_path / "x.svd"
    p.write_text(SVD, encoding="utf-8")
    with pytest.raises(RegmapError, match="không nhận ra"):
        nap_ban_do(p, "dinh-dang-la")


def test_ban_do_RONG_bi_tu_choi(tmp_path: Path) -> None:
    """Bản đồ rỗng lặng lẽ làm cổng im, và im trông y hệt đã kiểm."""
    p = tmp_path / "x.svd"
    p.write_text("<device><name>C</name></device>", encoding="utf-8")
    with pytest.raises(RegmapError, match="KHÔNG có thanh ghi nào"):
        nap_ban_do(p, "svd")


def test_pack_khong_khai_regmap_thi_tra_None() -> None:
    """Đây là đường chạy BÌNH THƯỜNG, không phải lỗi."""
    from types import SimpleNamespace

    assert tu_pack(SimpleNamespace(regmap={}), ".") is None
    assert tu_pack(None, ".") is None


def test_pack_khai_thieu_nua_thi_bao(tmp_path: Path) -> None:
    from types import SimpleNamespace

    with pytest.raises(RegmapError, match="cả 'format' lẫn 'path'"):
        tu_pack(SimpleNamespace(regmap={"format": "svd"}), tmp_path)


def test_duong_dan_tuong_doi_tinh_tu_goc_du_an(tmp_path: Path) -> None:
    from types import SimpleNamespace

    (tmp_path / "regmap").mkdir()
    (tmp_path / "regmap" / "chip.svd").write_text(SVD, encoding="utf-8")
    m = tu_pack(
        SimpleNamespace(regmap={"format": "svd", "path": "regmap/chip.svd"}), tmp_path
    )
    assert m.device == "CHIP_X"


# ── cổng: bốn phép CHẶN ──────────────────────────────────────────────────────


def test_ghi_dung_thi_DAT() -> None:
    bc = _chay(_cong(), "void f(void) { CTRL_A = 0x0F; }")
    assert bc.passed is True
    assert bc.metrics["writes_checked"] == 1


def test_gia_tri_vuot_do_rong_thanh_ghi_thi_DO() -> None:
    bc = _chay(_cong(), "void f(void) { CTRL_A = 0x1FF; }")
    assert bc.passed is False
    e = _ma("regmap-value-overflow", bc)[0]
    assert "8 bit" in str(e) and "255" in str(e), "phải nêu độ rộng và giá trị lớn nhất"
    assert e.line == 1


def test_dich_bit_ra_ngoai_do_rong_thi_DO() -> None:
    bc = _chay(_cong(), "void f(void) { CTRL_A |= (1 << 9); }")
    assert bc.passed is False
    assert "bit 9" in str(_ma("regmap-bit-out-of-range", bc)[0])


def test_dich_bit_trong_do_rong_thi_DAT() -> None:
    assert _chay(_cong(), "void f(void) { CTRL_A |= (1 << 7); }").passed is True


def test_ghi_vao_thanh_ghi_CHI_DOC_thi_DO() -> None:
    bc = _chay(_cong(), "void f(void) { STAT_A = 0x01; }")
    assert bc.passed is False
    assert _ma("regmap-read-only", bc)


def test_doc_thanh_ghi_chi_doc_thi_KHONG_sao() -> None:
    assert _chay(_cong(), "void f(void) { int x = STAT_A; }").passed is True


def test_ho_so_khai_thanh_ghi_ban_do_KHONG_co_thi_DO() -> None:
    """Gõ nhầm một tên trong hồ sơ thì mọi lượt sinh sau nhận một tên không có
    thật, và không gì khác trong hệ hỏi lại."""
    bc = _cong(registers=["CTRL_A", "KHONG_CO_THAT"]).run(CodeArtifact(files={}))
    assert bc.passed is False
    e = _ma("regmap-profile-mismatch", bc)[0]
    assert "KHONG_CO_THAT" in str(e) and "CTRL_A" not in str(e)


def test_ten_khong_co_trong_ban_do_thi_BO_QUA() -> None:
    """Một macro viết hoa không phải một thanh ghi — chặn nó là báo nhầm."""
    bc = _chay(_cong(), "void f(void) { MOT_MACRO_NAO_DO = 0xFFFF; }")
    assert bc.passed is True
    assert bc.metrics["writes_checked"] == 0


def test_tra_ten_KHONG_phan_biet_hoa_thuong() -> None:
    """Báo 'không có thanh ghi này' cho đúng thanh ghi đang có là dạng báo nhầm
    tệ nhất — nó nghe rất thuyết phục."""
    assert _chay(_cong(), "void f(void) { ctrl_a = 0x1FF; }").passed is False


# ── cổng: phép CẢNH BÁO ──────────────────────────────────────────────────────


MA_TRICH_DAN_LECH = """
void bus_init(void) {
    // ref: ds-stat
    CTRL_A = 0x0F;
}
"""


def test_trich_dan_khong_noi_ve_thanh_ghi_ay_thi_CANH_BAO() -> None:
    """Đây đúng là chỗ 'CÓ trích dẫn' khác 'trích dẫn ĐÚNG'."""
    bc = _chay(
        _cong(chunk_registers={"ds-stat": ("STAT_A",)}), MA_TRICH_DAN_LECH
    )
    assert bc.passed is True, "cảnh báo không được làm cổng đỏ"
    w = _ma("regmap-citation-mismatch", bc)[0]
    assert w.severity == Severity.WARNING
    assert "bus_init()" in str(w) and "CTRL_A" in str(w)


def test_trich_dan_dung_thi_IM() -> None:
    bc = _chay(_cong(chunk_registers={"ds-stat": ("CTRL_A",)}), MA_TRICH_DAN_LECH)
    assert not _ma("regmap-citation-mismatch", bc)


def test_khong_co_anh_xa_chunk_thi_phep_canh_bao_IM() -> None:
    """Thiếu dữ liệu thì im, chứ không đoán."""
    assert not _ma("regmap-citation-mismatch", _chay(_cong(), MA_TRICH_DAN_LECH))


# ── ranh giới ────────────────────────────────────────────────────────────────


def test_KHONG_ap_len_tep_kiem_viet_bang_python() -> None:
    """Hàng rào SL-150, dựng lại cho cổng mới.

    Nội dung phải là thứ CẢ HAI ngôn ngữ đọc được, nếu không bài kiểm rỗng.
    Bản đầu tôi viết dùng đoạn C nhúng trong chuỗi Python — nhưng bộ bỏ chú
    thích xoá luôn ruột chuỗi, nên đoạn ấy vô hình ở cả hai tệp và bài xanh dù
    có hàng rào hay không.

    Bản thứ hai bỏ dấu chấm phẩy — cũng rỗng, vì phép khớp lệnh ghi của cổng
    đòi dấu ấy. Bản đang dùng có chấm phẩy: hợp lệ trong CẢ HAI ngôn ngữ, nên
    nó thật sự chạm được vào hàng rào.

    Nói thẳng giới hạn: Python có chấm phẩy cuối câu là cách viết hiếm, nên
    hàng rào này là lớp phòng thủ thứ hai chứ không phải lớp hay được dùng.
    Nhưng một lớp phòng thủ không kiểm được thì không biết nó còn sống hay
    không — và đó mới là lý do bài này tồn tại.
    """
    ma = "CTRL_A = 0x1FF;\n"
    assert _chay(_cong(), ma, ten="tests/test_drv_bus.py").passed is True
    # Vế ngược: cùng nội dung trong tệp .c THÌ phải đỏ. Không có vế này thì bài
    # trên xanh vì cổng mù chứ không vì hàng rào có tác dụng.
    assert _chay(_cong(), ma, ten="src/drv_bus.c").passed is False


def test_VANG_BAN_DO_thi_cong_DAT_va_im() -> None:
    """Luật 1 của kế hoạch: thêm một nguồn sự thật không được làm hỏng đường
    chạy khi nguồn ấy vắng mặt."""
    bc = RegCheckGate(regmap=None, registers=["KHONG_CO_THAT"]).run(
        CodeArtifact(files={"src/drv_bus.c": "void f(void) { CTRL_A = 0x1FF; }"})
    )
    assert bc.passed is True
    assert bc.errors == [] and bc.warnings == []
    assert "skipped" in bc.metrics


def test_module_khong_cham_thanh_ghi_nao_thi_DAT_im_lang() -> None:
    bc = _chay(_cong(), "int cong(int a, int b) { return a + b; }")
    assert bc.passed is True and bc.metrics["writes_checked"] == 0


def test_cong_KHONG_nam_trong_required_gates() -> None:
    """Thêm vào đó sẽ làm bằng chứng merge của mọi module đã có thành THIẾU
    cổng, và ép mọi dự án phải có tệp bản đồ. Cổng vẫn chặn được vì chuỗi cổng
    dừng ở cổng hỏng đầu tiên."""
    from eaa.orchestrator import OrchestratorConfig

    assert "regcheck" not in OrchestratorConfig().required_gates
