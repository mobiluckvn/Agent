"""TC-134 — chú thích số học sai thứ nguyên (N-911).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-174.

Ca thật: mã sinh ra mang chú thích ``// 4ms per step / 0.000031s per sample =
129``. Phép chia ấy **đúng số học** — 0,004 / 0,000031 = 129,03. Nó sai ở chỗ
khác: ``0.000031`` không phải *giây trên mẫu*, nó là hệ số thang của con quay,
đơn vị **độ trên LSB**. Chú thích tự gán cho hằng số một đơn vị nó không có,
con số ra vô nghĩa, và đó là nguyên nhân robot không lấy đủ mẫu.

Không cổng nào bắt được: mã dịch được, chú thích nghe hợp lý, và người đọc lướt
qua thấy phép chia có đơn vị hai bên thì tin.

Hai phép soi bắt hai chuyện khác nhau
--------------------------------------

1. **Đơn vị khai chọi với đơn vị đã đăng ký** — bắt đúng ca trên, nhưng CHỈ khi
   hằng số ấy có trong sổ số đo. Bài này canh cả chuyện đó: phép kiểm chỉ mạnh
   bằng cái sổ đứng sau nó, và nó phải nói ra chứ không im lặng tỏ ra chắc chắn.
2. **Phép tính không ra kết quả nó khai** — tự chứa, có quy đổi tiền tố thời
   gian, nên chính ca thật KHÔNG bị phép này kêu. Đó là đúng.

Cả hai ra CẢNH BÁO, không chặn cổng: chú thích là văn xuôi tự do.
"""

from __future__ import annotations

import pytest

from eaa.dimension import (
    doc_phep_tinh,
    don_vi_khai_trong_chu_thich,
    soi_chu_thich_so_hoc,
)
from eaa.tools.base import CodeArtifact, Severity
from eaa.tools.static import StaticGate

CA_THAT = """
void drv_imu_init(void) {
    // 4ms per step / 0.000031s per sample = 129
    imu_pump_limit = 129;
}
"""


class SoGia:
    """Sổ số đo tối thiểu — đúng cái mặt cổng cần."""

    def __init__(self, **don_vi: str) -> None:
        from eaa.measured import BoardFact

        self._facts = [
            BoardFact(name=k, value=v.split()[0], unit=v.split()[1])
            for k, v in don_vi.items()
        ]

    def active(self):
        return list(self._facts)


class SoHong:
    def active(self):
        raise RuntimeError("sổ hỏng")


# ── đọc phép tính trong chú thích ────────────────────────────────────────────


def test_doc_duoc_phep_tinh_kem_don_vi() -> None:
    phep = doc_phep_tinh("// 4ms / 0.000031s = 129")
    assert len(phep) == 1
    assert (phep[0].a, phep[0].don_vi_a) == (4.0, "ms")
    assert (phep[0].b, phep[0].don_vi_b) == (0.000031, "s")
    assert phep[0].c == 129.0


def test_bo_qua_phep_tinh_nam_ngoai_chu_thich() -> None:
    """`x = a / b` trong mã là mã, không phải một lời khai."""
    assert doc_phep_tinh("int x = 4 / 2;") == []


def test_doc_duoc_ca_chu_thich_khoi() -> None:
    assert len(doc_phep_tinh("/* chu kỳ 10ms / 2ms = 5 lát */")) == 1


def test_don_vi_khai_gom_theo_gia_tri() -> None:
    ra = don_vi_khai_trong_chu_thich("// 4ms mỗi bước, 0.000031s mỗi mẫu")
    assert ra["4"] == {"ms"}
    assert ra["0.000031"] == {"s"}


# ── phép soi 1: đơn vị chọi với sổ ───────────────────────────────────────────


def test_KHONG_co_so_thi_ca_that_khong_bi_keu() -> None:
    """Phép tính đúng số học — không có sổ thì không có gì để chọi."""
    assert soi_chu_thich_so_hoc(CA_THAT) == []


def test_CO_so_thi_bat_duoc_ca_that() -> None:
    dau = soi_chu_thich_so_hoc(CA_THAT, {"0.000031": "°/LSB"})
    assert len(dau) == 1
    assert dau[0].loai == "ĐƠN VỊ CHỌI VỚI SỔ SỐ ĐO"
    assert "0.000031" in dau[0].chi_tiet and "°/LSB" in dau[0].chi_tiet


def test_don_vi_KHOP_voi_so_thi_im() -> None:
    """Sổ ghi giây, chú thích viết giây — không có gì chọi."""
    assert soi_chu_thich_so_hoc("// chu kỳ 0.004s mỗi bước", {"0.004": "s"}) == []


def test_khac_TIEN_TO_cung_dai_luong_thi_KHONG_phai_choi() -> None:
    """`ms` và `s` là cùng đại lượng — khai `4ms` khi sổ ghi `s` là hợp lệ."""
    assert soi_chu_thich_so_hoc("// trễ 4ms mỗi bước", {"4": "s"}) == []


def test_gia_tri_khong_co_trong_so_thi_im() -> None:
    assert soi_chu_thich_so_hoc("// trễ 7ms", {"0.000031": "°/LSB"}) == []


# ── phép soi 2: phép tính không ra kết quả nó khai ───────────────────────────


def test_bat_duoc_phep_tinh_sai() -> None:
    dau = soi_chu_thich_so_hoc("// 4 / 0.000031 = 129")
    assert len(dau) == 1
    assert dau[0].loai == "PHÉP TÍNH KHÔNG RA KẾT QUẢ NÓ KHAI"
    assert "129032" in dau[0].chi_tiet


def test_QUY_DOI_tien_to_truoc_khi_so() -> None:
    """`4ms / 0.000031s = 129` phải IM: nó đúng khi quy đổi ms sang s."""
    assert soi_chu_thich_so_hoc("// 4ms / 0.000031s = 129") == []


def test_KHONG_quy_doi_giua_hai_dai_luong_khac_nhau() -> None:
    """Quy đổi bừa giữa giây và vôn là làm đúng cái sai bộ này đi tìm."""
    phep = doc_phep_tinh("// 4ms / 2V = 2")[0]
    assert phep.ket_qua_thuc() == pytest.approx(2.0)


def test_lam_tron_trong_sai_so_cho_phep_thi_im() -> None:
    assert soi_chu_thich_so_hoc("// 10 / 3 = 3.33") == []


def test_chia_cho_khong_thi_bo_qua_chu_khong_no() -> None:
    assert soi_chu_thich_so_hoc("// 5 / 0 = 0") == []


def test_phep_nhan_cung_duoc_soi() -> None:
    dau = soi_chu_thich_so_hoc("// 8 * 4 = 30")
    assert len(dau) == 1


# ── nối vào cổng phân tích tĩnh ──────────────────────────────────────────────


def test_ra_CANH_BAO_chu_khong_chan_cong() -> None:
    """Chú thích là văn xuôi tự do; chặn merge bằng nó sẽ chặn nhầm."""
    cong = StaticGate(measured=SoGia(GYRO_SCALE="0.000031 °/LSB"))
    bao_cao = cong.run(CodeArtifact(files={"src/drv_imu.c": CA_THAT}))

    assert bao_cao.passed is True, "cảnh báo không được làm cổng đỏ"
    assert any(w.rule_id == "dimension" for w in bao_cao.warnings)
    assert all(e.rule_id != "dimension" for e in bao_cao.errors)


def test_canh_bao_neu_dung_TEP_va_DONG() -> None:
    """Nêu chỗ mà không nêu dòng thì người đọc phải đi dò cả tệp."""
    cong = StaticGate(measured=SoGia(GYRO_SCALE="0.000031 °/LSB"))
    w = next(
        w
        for w in cong.run(CodeArtifact(files={"src/drv_imu.c": CA_THAT})).warnings
        if w.rule_id == "dimension"
    )
    assert w.file == "src/drv_imu.c"
    assert w.line == 3
    assert w.severity == Severity.WARNING


def test_KHONG_ap_len_tep_kiem_viet_bang_python() -> None:
    """Cùng luật SL-150: luật của mã C không áp lên tệp Python.

    Đoạn C nhúng trong chuỗi Python là ca THẬT, không phải ca dựng ra: bài kiểm
    trên máy chủ ở kho này dịch mã C từ trong chính tệp test rồi nạp bằng
    ``ctypes``. Dùng chú thích Python `#` ở đây thì bài kiểm rỗng — bộ soi chỉ
    đọc chú thích C, nên nó im dù có hàng rào hay không.
    """
    tep_python = (
        "NGUON_C = '''\n"
        "void f(void) {\n"
        "    // 4 / 0.000031 = 129\n"
        "}\n"
        "'''\n"
    )
    cong = StaticGate(measured=SoGia(GYRO_SCALE="0.000031 °/LSB"))
    bao_cao = cong.run(CodeArtifact(files={"tests/test_drv_imu.py": tep_python}))
    assert all(w.rule_id != "dimension" for w in bao_cao.warnings)

    # Và cùng nội dung ấy trong một tệp .c THÌ phải kêu — nếu không, bài trên
    # xanh vì bộ soi mù chứ không vì hàng rào có tác dụng.
    trong_c = cong.run(CodeArtifact(files={"src/drv_imu.c": tep_python}))
    assert any(w.rule_id == "dimension" for w in trong_c.warnings)


def test_khong_co_so_thi_cong_chay_y_nhu_truoc() -> None:
    cong = StaticGate()
    bao_cao = cong.run(CodeArtifact(files={"src/drv_imu.c": CA_THAT}))
    assert bao_cao.passed is True
    assert all(w.rule_id != "dimension" for w in bao_cao.warnings)


def test_so_hong_khong_lam_hong_cong() -> None:
    """Một phép soi phụ trợ không được quyền làm hỏng cổng vì lý do của nó."""
    cong = StaticGate(measured=SoHong())
    assert cong.run(CodeArtifact(files={"src/drv_imu.c": CA_THAT})).passed is True
