"""TC-128 — bài kiểm mới phải phân biệt được mã sai với mã đúng (N-909).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-168.

Ngày 03/09, kỹ sư yêu cầu Agent thêm một bài canh: trong vùng chết, điểm đặt
phải đứng yên. Agent thêm `test_deadband_keeps_setpoint_steady`, và bài ấy **đỏ
ở vòng đầu, xanh sau khi sửa** — nhìn từ ngoài đúng hệt một bài kiểm làm đúng
việc của nó. Đọc kỹ thì nó chạy 10 vòng, điểm đặt trôi 0,015, còn xa ngưỡng
vùng chết. Nó **xanh cả với mã sai**; nó đỏ vì một lý do khác.

Phép đo ở đây trả lời đúng một câu: *bài kiểm vừa thêm có phân biệt được bản
vừa bị cổng đánh đỏ với bản vừa được nhận không?* Chạy lại nó trên mã CŨ.

Và bài kiểm này canh cả RANH GIỚI của phép đo ấy — nó bắt hạng nhẹ hơn hạng đã
sinh ra nó, nên nó không được phép tự nhận là đã thay được người đọc mã ở G3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eaa.orchestrator import Orchestrator
from eaa.sensitivity import (
    KetQuaDoNhay,
    bai_kiem_do,
    bai_kiem_doi,
    bai_kiem_trong,
    co_loi_thu_thap,
    ket_luan,
)
from eaa.tools.base import CodeArtifact, ToolReport


# -- đọc bài kiểm trong một tệp ----------------------------------------------


def test_lay_dung_ham_test_va_bo_ham_khac() -> None:
    nguon = """
def phu_tro():
    return 1

def test_mot():
    assert phu_tro() == 1

def khong_phai_test():
    pass
"""
    assert set(bai_kiem_trong(nguon)) == {"test_mot"}


def test_lay_ca_bai_kiem_nam_trong_lop() -> None:
    nguon = """
class TestNhom:
    def test_trong_lop(self):
        assert True
"""
    assert "test_trong_lop" in bai_kiem_trong(nguon)


def test_tep_hong_cu_phap_tra_ve_rong() -> None:
    """Mô hình sinh ra tệp Python hỏng là chuyện có thật, không phải giả thiết."""
    assert bai_kiem_trong("def test_x(:\n    pass") == {}


def test_chuan_hoa_bang_CAY_CU_PHAP_chu_khong_bang_chuoi() -> None:
    """Thụt lề, chú thích, xuống dòng đổi — việc bài kiểm làm thì không đổi."""
    a = "def test_x():\n    assert 1 == 1\n"
    b = "def test_x():\n    # ghi chú thêm vào\n    assert (\n        1\n        == 1\n    )\n"
    assert bai_kiem_trong(a)["test_x"] == bai_kiem_trong(b)["test_x"]


# -- bài kiểm nào mới hoặc đã đổi --------------------------------------------


def test_module_sinh_lan_dau_thi_moi_bai_deu_moi() -> None:
    moi = "def test_a():\n    pass\ndef test_b():\n    pass\n"
    assert bai_kiem_doi(None, moi) == ("test_a", "test_b")


def test_chi_bai_them_vao_moi_duoc_tinh() -> None:
    cu = "def test_a():\n    assert 1\n"
    moi = cu + "def test_b():\n    assert 2\n"
    assert bai_kiem_doi(cu, moi) == ("test_b",)


def test_doi_than_bai_cu_cung_duoc_tinh() -> None:
    """Sửa một bài kiểm cũ là đưa ra một lời khai mới — phải đo lại."""
    cu = "def test_a():\n    assert 1\n"
    moi = "def test_a():\n    assert 2\n"
    assert bai_kiem_doi(cu, moi) == ("test_a",)


def test_chi_doi_dinh_dang_thi_KHONG_tinh_la_doi() -> None:
    """Nếu không, mọi lượt định dạng lại đều kéo theo một phép đo thừa."""
    cu = "def test_a():\n    assert 1 == 1\n"
    moi = "def test_a():\n    assert (1\n            == 1)\n"
    assert bai_kiem_doi(cu, moi) == ()


def test_bai_bi_XOA_khong_nam_trong_ket_qua() -> None:
    """Phép đo hỏi 'cái vừa thêm chứng minh được gì' — bài đã xoá thì không còn gì."""
    cu = "def test_a():\n    pass\ndef test_b():\n    pass\n"
    moi = "def test_a():\n    pass\n"
    assert bai_kiem_doi(cu, moi) == ()


def test_ban_moi_hong_cu_phap_thi_khong_do_duoc_gi() -> None:
    assert bai_kiem_doi("def test_a():\n    pass\n", "def test_a(:") == ()


def test_thu_tu_on_dinh() -> None:
    moi = "def test_z():\n    pass\ndef test_a():\n    pass\n"
    ra = bai_kiem_doi(None, moi)
    assert ra == tuple(sorted(ra))


# -- đọc đầu ra pytest -------------------------------------------------------


DAU_RA_DO = """
FAILED tests/test_drv_imu.py::test_doc_goc - assert 0 == 1
ERROR tests/test_drv_imu.py::test_khoi_tao
1 failed, 3 passed
"""


def test_doc_ten_bai_kiem_do() -> None:
    assert bai_kiem_do(DAU_RA_DO) == frozenset({"test_doc_goc", "test_khoi_tao"})


def test_cat_phan_tham_so_de_khop_ten_ham() -> None:
    assert bai_kiem_do("FAILED tests/t.py::test_x[1-2] - boom") == frozenset({"test_x"})


def test_dau_ra_xanh_khong_co_ten_nao() -> None:
    assert bai_kiem_do("12 passed in 0.4s") == frozenset()


def test_loi_THU_THAP_nhan_ra_duoc() -> None:
    """`ERROR tests/x.py` không kèm `::` nghĩa là cả tệp không nạp nổi."""
    assert co_loi_thu_thap("ERROR tests/test_drv_imu.py\n1 error") is True


def test_chi_co_bai_do_thi_khong_phai_loi_thu_thap() -> None:
    assert co_loi_thu_thap(DAU_RA_DO) is False


# -- kết luận ----------------------------------------------------------------


def test_bai_kiem_do_tren_ma_cu_thi_PHAN_BIET_DUOC() -> None:
    kq = ket_luan(("test_doc_goc",), DAU_RA_DO)
    assert kq.phan_biet_duoc == ("test_doc_goc",)
    assert kq.khong_phan_biet == ()
    assert kq.dat is True


def test_bai_kiem_XANH_tren_ma_cu_la_bai_kiem_khong_chung_minh_gi() -> None:
    """Chuyện cần bắt: bài mới xanh trên cả bản sai lẫn bản đúng."""
    kq = ket_luan(("test_deadband",), "12 passed in 0.4s")
    assert kq.khong_phan_biet == ("test_deadband",)
    assert kq.dat is False
    assert "XANH CẢ TRÊN MÃ VỪA BỊ ĐÁNH ĐỎ" in kq.cau()


def test_ca_tep_khong_nap_noi_tren_ma_cu_van_la_phan_biet_duoc() -> None:
    kq = ket_luan(("test_a", "test_b"), "ERROR tests/test_x.py\n1 error")
    assert kq.phan_biet_duoc == ("test_a", "test_b")
    assert kq.dat is True


def test_KHONG_DO_DUOC_khac_han_voi_DO_DUOC_VA_DAT() -> None:
    """Hai chuyện khác nhau, và gộp chúng là biến im lặng thành lời khẳng định."""
    khong_do = ket_luan(("test_a",), "", do_duoc=False, ly_do="thiếu cổng")
    assert khong_do.dat is False
    assert khong_do.khong_phan_biet == ()
    assert "KHÔNG đo được" in khong_do.cau()

    khong_co_bai = ket_luan((), "")
    assert khong_co_bai.dat is True
    assert "không có bài kiểm nào mới" in khong_co_bai.cau()


def test_cau_dem_du_so_bai_khi_moi_bai_deu_phan_biet_duoc() -> None:
    kq = ket_luan(("test_doc_goc", "test_khoi_tao"), DAU_RA_DO)
    assert "2/2" in kq.cau()


# -- nối vào vòng lặp --------------------------------------------------------


@dataclass
class CongGia:
    """Cổng `unittests` giả — dataclass, vì mã thật dùng `replace` để đổi thư mục."""

    tests_dir: Path
    work_dir: Path
    name: str = "unittests"
    dau_ra: str = "12 passed in 0.4s"
    no: bool = False
    #: Ảnh chụp thư mục lúc chạy, để bài kiểm soi được mã cũ có thật sự được đặt vào không.
    da_thay: dict[str, str] = field(default_factory=dict)

    def run(self, artifact: Any = None) -> ToolReport:
        if self.no:
            raise RuntimeError("cổng tự nổ")
        for p in sorted(Path(self.work_dir).rglob("*")):
            if p.is_file():
                self.da_thay[str(p.relative_to(self.work_dir))] = p.read_text(
                    encoding="utf-8", errors="replace"
                )
        return ToolReport(gate=self.name, passed=True, raw_output=self.dau_ra)


class OrchGia:
    """Mượn đúng phương thức đang đo, và khai ra nó chỉ cần `gate_chain`."""

    _KHONG_CHEP = Orchestrator._KHONG_CHEP
    _do_nhay_bai_kiem = Orchestrator._do_nhay_bai_kiem

    def __init__(self, gate_chain: list[Any]) -> None:
        self.gate_chain = gate_chain


TEST_CU = "def test_a():\n    assert doc() == 1\n"
TEST_MOI = TEST_CU + "def test_moi():\n    assert doc() == 2\n"


def _du_an(tmp_path: Path) -> Path:
    goc = tmp_path / "firmware"
    (goc / "tests").mkdir(parents=True)
    (goc / "src").mkdir()
    (goc / "src" / "drv_imu.c").write_text("void drv_imu_init(void) { moi(); }\n")
    (goc / "tests" / "test_drv_imu.py").write_text(TEST_MOI)
    return goc


def test_khong_co_tep_test_trong_ban_moi_thi_khong_do(tmp_path: Path) -> None:
    goc = _du_an(tmp_path)
    orch = OrchGia([CongGia(goc / "tests", goc)])
    kq = orch._do_nhay_bai_kiem(
        CodeArtifact(files={}), CodeArtifact(files={"src/drv_imu.c": "x"}), "drv_imu"
    )
    assert kq == KetQuaDoNhay()


def test_khong_bai_kiem_nao_doi_thi_khong_chay_pytest_lan_nao(tmp_path: Path) -> None:
    """Phép đo tốn một lượt chạy pytest — không được chạy khi không có gì để đo."""
    goc = _du_an(tmp_path)
    cong = CongGia(goc / "tests", goc)
    orch = OrchGia([cong])
    truoc = CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI})
    sau = CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI})
    assert orch._do_nhay_bai_kiem(truoc, sau, "drv_imu") == KetQuaDoNhay()
    assert cong.da_thay == {}, "đã chạy cổng dù không có bài kiểm nào đổi"


def test_thieu_cong_unittests_thi_bao_KHONG_DO_DUOC(tmp_path: Path) -> None:
    orch = OrchGia([])
    kq = orch._do_nhay_bai_kiem(
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_CU}),
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI}),
        "drv_imu",
    )
    assert kq.do_duoc is False
    assert "unittests" in kq.ly_do


def test_cong_no_thi_bao_KHONG_DO_DUOC_chu_khong_lam_hong_luot_sinh(
    tmp_path: Path,
) -> None:
    """Một phép đo phụ trợ không được quyền làm hỏng lượt sinh vì lý do của nó."""
    goc = _du_an(tmp_path)
    orch = OrchGia([CongGia(goc / "tests", goc, no=True)])
    kq = orch._do_nhay_bai_kiem(
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_CU}),
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI}),
        "drv_imu",
    )
    assert kq.do_duoc is False
    assert "RuntimeError" in kq.ly_do


def test_ban_sao_mang_ma_CU_va_bai_kiem_MOI(tmp_path: Path) -> None:
    """Đúng phép đo cần: bộ kiểm mới chạy trên mã cũ, không phải trên mã mới."""
    goc = _du_an(tmp_path)
    cong = CongGia(goc / "tests", goc)
    orch = OrchGia([cong])
    truoc = CodeArtifact(
        files={
            "src/drv_imu.c": "void drv_imu_init(void) { CU(); }\n",
            "tests/test_drv_imu.py": TEST_CU,
        }
    )
    sau = CodeArtifact(
        files={
            "src/drv_imu.c": "void drv_imu_init(void) { MOI(); }\n",
            "tests/test_drv_imu.py": TEST_MOI,
        }
    )
    kq = orch._do_nhay_bai_kiem(truoc, sau, "drv_imu")

    assert "CU();" in cong.da_thay["src/drv_imu.c"], "phải là mã CŨ"
    assert cong.da_thay["tests/test_drv_imu.py"] == TEST_MOI, "phải là bài kiểm MỚI"
    # Cổng giả báo toàn xanh → bài mới không phân biệt được hai bản.
    assert kq.khong_phan_biet == ("test_moi",)


def test_ban_sao_KHONG_mang_theo_thu_vien_da_dich(tmp_path: Path) -> None:
    """Chép `.so` sang là dựng lại đúng cái bẫy SL-152 đã dựng cổng để chặn.

    Bộ kiểm dịch mã C thành thư viện rồi nạp bằng `ctypes`. Còn thư viện của
    lần trước thì mã cũ không cần dịch nổi, và phép đo sẽ đo nhị phân của bản
    MỚI trong khi tin rằng mình đang đo bản cũ.
    """
    goc = _du_an(tmp_path)
    (goc / "libdrv_imu.so").write_text("nhị phân của bản mới")
    (goc / "build").mkdir()
    (goc / "build" / "firmware.elf").write_text("ảnh của bản mới")
    cong = CongGia(goc / "tests", goc)
    orch = OrchGia([cong])
    orch._do_nhay_bai_kiem(
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_CU}),
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI}),
        "drv_imu",
    )
    assert "libdrv_imu.so" not in cong.da_thay
    assert not any(t.startswith("build") for t in cong.da_thay)


def test_ban_sao_la_BAN_SAO_du_an_that_khong_bi_dung_toi(tmp_path: Path) -> None:
    """Đo độ nhạy không được ghi mã cũ đè lên thư mục làm việc thật."""
    goc = _du_an(tmp_path)
    orch = OrchGia([CongGia(goc / "tests", goc)])
    orch._do_nhay_bai_kiem(
        CodeArtifact(
            files={
                "src/drv_imu.c": "void drv_imu_init(void) { CU(); }\n",
                "tests/test_drv_imu.py": TEST_CU,
            }
        ),
        CodeArtifact(files={"tests/test_drv_imu.py": TEST_MOI}),
        "drv_imu",
    )
    assert "moi();" in (goc / "src" / "drv_imu.c").read_text()
    assert (goc / "tests" / "test_drv_imu.py").read_text() == TEST_MOI
