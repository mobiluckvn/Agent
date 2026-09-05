"""TC-137 — bản đồ thanh ghi nối vào bộ dò đã có (GĐ1, phần 3).

Xem `docs/KE_HOACH_VUOT_LEN.md` §2.5 và `docs/SAI_LECH_THIET_KE.md` mục SL-176.

Kế hoạch nêu hai chỗ nối: `eaa/instrument.py` (N-908) và `eaa/dimension.py`
(N-911). Làm xong thì chỉ **một** chỗ nối được, và bài này canh cả hai kết luận:

* **N-908 nối được, và nối có giá trị.** Trước GĐ1 bộ dò chỉ biết một hằng số
  có trích dẫn *đã bị đổi*. Có bản đồ thì nó biết thêm giá trị mới **có còn hợp
  lệ không** — hai lỗi chồng nhau khác hẳn một lỗi, và người phân xử cần biết
  mình đang đứng trước cái nào.
* **N-911 KHÔNG nối.** Ca sinh ra N-911 là hệ số thang `0.000031` — một số thực
  không bao giờ nằm trong bản đồ thanh ghi. Phép duy nhất bản đồ đóng góp được
  là suy từ *giá trị reset*, mà giá trị reset `0` có ở gần như mọi thanh ghi:
  nó sẽ gắn nhãn "không thứ nguyên" cho số `0` rồi kêu ở mọi chú thích có
  `0 ms`. Đó là bộ sinh báo nhầm, không phải bộ dò.

Bài canh cuối cùng của tệp này giữ cho kết luận thứ hai không bị lặng lẽ đảo
lại: `dimension.py` phải KHÔNG biết gì về bản đồ thanh ghi.

Và bài quan trọng nhất vẫn là bài cũ: **vắng bản đồ thì mọi thứ chạy y như
trước** — luật 1 của kế hoạch.
"""

from __future__ import annotations

from typing import Any

from eaa.instrument import nghi_van_chinh_do_do
from eaa.regmap_svd import doc as doc_svd

SVD = """<device><name>CHIP_X</name><peripherals>
 <peripheral><name>BUS0</name><registers>
  <register><name>CTRL_A</name><size>8</size><access>read-write</access></register>
 </registers></peripheral></peripherals></device>"""

CU = """
void bus_init(void) {
    // ref: ds-01, tr.222
    CTRL_A = 72;
}
"""
# Giá trị mới VẪN lọt vừa thanh ghi 8 bit.
MOI_HOP_LE = CU.replace("CTRL_A = 72;", "CTRL_A = 96;")
# Giá trị mới KHÔNG lọt vừa thanh ghi nào trong bản đồ.
MOI_VUOT = CU.replace("CTRL_A = 72;", "CTRL_A = 999;")


def _ban_do() -> Any:
    return doc_svd(SVD)


# ── N-908: có bản đồ thì nói được nhiều hơn ──────────────────────────────────


def test_khong_co_ban_do_van_bat_duoc_hang_so_bi_doi() -> None:
    """Đây là hành vi trước GĐ1, và nó phải giữ nguyên."""
    nghi = nghi_van_chinh_do_do(CU, MOI_HOP_LE)
    assert nghi.co
    assert "72" in nghi.cau()


def test_co_ban_do_va_gia_tri_moi_HOP_LE_thi_khong_them_gi() -> None:
    """Vẫn dừng vòng vá — dấu vết cũ không đổi — nhưng không doạ thêm."""
    nghi = nghi_van_chinh_do_do(CU, MOI_HOP_LE, ban_do=_ban_do())
    assert nghi.co
    assert "KHÔNG lọt vừa" not in nghi.cau()


def test_co_ban_do_va_gia_tri_moi_VUOT_thi_neu_them() -> None:
    """Hai lỗi chồng nhau khác hẳn một lỗi."""
    nghi = nghi_van_chinh_do_do(CU, MOI_VUOT, ban_do=_ban_do())
    van = nghi.cau()
    assert "72" in van, "dấu vết cũ vẫn phải còn"
    assert "999" in van and "KHÔNG lọt vừa" in van


def test_ban_do_HONG_khong_lam_hong_bo_do() -> None:
    """Một nguồn phụ trợ không được quyền làm hỏng bộ dò vì lý do của nó."""

    class BanDoHong:
        @property
        def registers(self):
            raise RuntimeError("bản đồ hỏng")

    nghi = nghi_van_chinh_do_do(CU, MOI_VUOT, ban_do=BanDoHong())
    assert nghi.co
    assert "KHÔNG lọt vừa" not in nghi.cau()


def test_gia_tri_khong_doc_noi_thi_IM_chu_khong_doan() -> None:
    """Ba trạng thái, không hai: hợp lệ · không hợp lệ · KHÔNG BIẾT."""
    cu = "void f(void) {\n    // ref: ds-01\n    CTRL_A = MOT_MACRO;\n}"
    moi = "void f(void) {\n    // ref: ds-01\n    CTRL_A = MOT_MACRO_KHAC;\n}"
    assert nghi_van_chinh_do_do(cu, moi, ban_do=_ban_do()).co is False


# ── luật 1 của kế hoạch ──────────────────────────────────────────────────────


def test_VANG_BAN_DO_thi_ba_bo_do_chay_y_NHU_TRUOC() -> None:
    """Thêm một nguồn sự thật không được làm hỏng đường chạy khi nó vắng mặt."""
    co = nghi_van_chinh_do_do(CU, MOI_HOP_LE, ban_do=_ban_do())
    khong = nghi_van_chinh_do_do(CU, MOI_HOP_LE, ban_do=None)
    assert co.co == khong.co
    assert len(co.dau_vet) == len(khong.dau_vet)


def test_orchestrator_lay_ban_do_TU_CHUOI_CONG() -> None:
    """Không dựng đường lấy riêng: bản đồ đã nằm trong cổng `regcheck`, và hai
    chỗ đọc hai bản là hai chỗ lệch nhau được."""
    from types import SimpleNamespace

    from eaa.orchestrator import Orchestrator
    from eaa.tools.base import CodeArtifact
    from eaa.tools.regcheck import RegCheckGate

    class OrchGia:
        _nghi_van_do_do = Orchestrator._nghi_van_do_do

        def __init__(self, gate_chain):
            self.gate_chain = gate_chain
            self.repo = SimpleNamespace()

    tep = {"src/drv_bus.c": MOI_VUOT}
    truoc = CodeArtifact(files={"src/drv_bus.c": CU})
    sau = CodeArtifact(files=tep)

    co_cong = OrchGia([RegCheckGate(regmap=_ban_do())])
    assert "KHÔNG lọt vừa" in co_cong._nghi_van_do_do(truoc, sau, "drv_bus").cau()

    khong_cong = OrchGia([])
    assert "KHÔNG lọt vừa" not in khong_cong._nghi_van_do_do(truoc, sau, "drv_bus").cau()


# ── kết luận thứ hai: N-911 KHÔNG nối ────────────────────────────────────────


def test_dimension_KHONG_biet_gi_ve_ban_do_thanh_ghi() -> None:
    """Kế hoạch nêu chỗ nối này; làm xong thì thấy nó tạo báo nhầm.

    Ca sinh ra N-911 là hệ số thang `0.000031` — một số thực không bao giờ nằm
    trong bản đồ thanh ghi. Phép duy nhất bản đồ đóng góp được là suy từ giá
    trị reset, mà reset `0` có ở gần như mọi thanh ghi.

    Bài này giữ cho kết luận ấy không bị lặng lẽ đảo lại: ai nối lại thì phải
    xoá bài này, và xoá một bài kiểm là một hành động nhìn thấy được trong diff.
    """
    import inspect

    from eaa import dimension

    nguon = inspect.getsource(dimension)
    assert "regmap" not in nguon
    assert "ban_do" not in nguon
