"""TC-123 — cổng đỏ vì mã module KHÁC thì KHÔNG mở vòng tự sửa.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-162.

Đo được ngày 03/09, lúc sinh lại `logic_pid`: bản sinh tự bỏ tham số
`is_running` khỏi `pid_compute`, làm `test_app_balance.py` — bài kiểm của một
module ĐÃ MERGE — không dịch nổi::

    src/app_balance.c:125:41: error: too many arguments to function call,
                              expected 2, have 3

Cổng `unittests` đỏ. Vòng tự sửa mở, chạy đủ ba lượt, và cả ba đều vá vào
`logic_pid` — tệp DUY NHẤT nó được phép viết, và là tệp không có lỗi nào. Ba
lượt gọi mô hình đổi lấy không gì cả, rồi module vẫn bàn giao lại cho người.

Vì sao vòng vá không tự thoát được
-----------------------------------

Vì nó không biết. Cổng gộp mọi thất bại vào MỘT `ToolError` không mang `file`,
nên phía trên chỉ đọc được "có lỗi", không đọc được "lỗi ở đâu". Với thông tin
ấy thì vá mù ba lượt là hành vi hợp lý nhất nó làm được.

Nên bài này canh HAI chỗ, và chỗ thứ nhất mới là chỗ sửa thật:

1. cổng `unittests` phải quy được thất bại về tệp (`metrics["failing_files"]`);
2. vòng lặp đọc danh sách ấy, đối chiếu `tep_can_sinh`, và dừng khi mọi tệp đỏ
   đều ngoài tầm tay mình.

Ngả về phía VÁ khi không chắc
------------------------------

Chặn nhầm thì dừng cả dây chuyền và đòi người; vá nhầm thì tốn lượt gọi. Hai
hạng sai không ngang giá, nên khi không quy được thất bại về tệp — hoặc chỉ quy
được một phần — vòng vá vẫn mở. Ba bài cuối canh đúng chiều ngả ấy.
"""

from __future__ import annotations

from eaa.orchestrator import Orchestrator
from eaa.tools.base import Severity, ToolError, ToolReport
from eaa.tools.unittests import UnitTestGate


# -- 1. cổng phải quy được thất bại về tệp ---------------------------------


def test_cong_doc_ra_tep_do_tu_dong_FAILED() -> None:
    dau_ra = (
        "=========================== short test summary info ====================\n"
        "FAILED tests/test_app_balance.py::test_init - assert 0 == 1\n"
        "FAILED tests/test_app_balance.py::test_step - assert 0 == 1\n"
    )
    assert UnitTestGate._tep_that_bai(dau_ra) == ["tests/test_app_balance.py"]


def test_cong_doc_ra_ca_loi_luc_THU_THAP() -> None:
    """`ERROR <tệp>` là dạng mà lỗi biên dịch chéo module hiện ra — đúng SL-162."""
    dau_ra = "ERROR tests/test_app_balance.py - subprocess.CalledProcessError: ...\n"
    assert UnitTestGate._tep_that_bai(dau_ra) == ["tests/test_app_balance.py"]


def test_cong_khong_bien_dong_ERROR_cua_nguoi_viet_thanh_ten_tep() -> None:
    """Danh sách này dùng để QUYẾT ĐỊNH dừng — đoán bừa ở đây là chặn nhầm."""
    dau_ra = "ERROR could not connect to the device\nFAILED to open /dev/null\n"
    assert UnitTestGate._tep_that_bai(dau_ra) == []


def test_cong_khong_neo_file_khi_NHIEU_tep_do() -> None:
    """Một `ToolError` chỉ có một `file`; neo vào một trong nhiều tệp là nói dối."""
    dau_ra = (
        "FAILED tests/test_logic_pid.py::test_a - x\n"
        "ERROR tests/test_app_balance.py - y\n"
    )
    assert UnitTestGate._tep_that_bai(dau_ra) == [
        "tests/test_logic_pid.py",
        "tests/test_app_balance.py",
    ]


# -- 2. vòng lặp phải dừng ---------------------------------------------------


def _bao_cao(tep: list[str] | None, *, neo: str | None = None) -> ToolReport:
    so_lieu = {"failing_files": tep} if tep is not None else {}
    return ToolReport(
        gate="unittests",
        passed=False,
        errors=[ToolError("1 test không đạt", file=neo)],
        metrics=so_lieu,
    )


def test_moi_tep_do_deu_ngoai_pham_vi_thi_bao_ngoai() -> None:
    """Chỗ SL-162 nằm."""
    ngoai = Orchestrator._loi_ngoai_pham_vi(
        _bao_cao(["tests/test_app_balance.py"]), "logic_pid"
    )
    assert ngoai == ["tests/test_app_balance.py"]


def test_tep_cua_chinh_module_thi_KHONG_chan() -> None:
    assert (
        Orchestrator._loi_ngoai_pham_vi(
            _bao_cao(["tests/test_logic_pid.py"]), "logic_pid"
        )
        == []
    )


def test_do_CA_HAI_thi_van_mo_vong_va() -> None:
    """Có phần lỗi thuộc về mình thì vá được — dừng ở đây là bỏ việc đang làm."""
    assert (
        Orchestrator._loi_ngoai_pham_vi(
            _bao_cao(["tests/test_logic_pid.py", "tests/test_app_balance.py"]),
            "logic_pid",
        )
        == []
    )


def test_khong_quy_duoc_ve_tep_nao_thi_van_mo_vong_va() -> None:
    """Không biết thì vá, không phải không biết thì chặn."""
    assert Orchestrator._loi_ngoai_pham_vi(_bao_cao(None), "logic_pid") == []


def test_quy_duoc_mot_phan_thi_van_mo_vong_va() -> None:
    """Một lỗi có neo, một lỗi không — chưa đủ chắc để dừng."""
    bao_cao = ToolReport(
        gate="unittests",
        passed=False,
        errors=[
            ToolError("hỏng", file="tests/test_app_balance.py"),
            ToolError("hỏng ở đâu không rõ"),
        ],
    )
    assert Orchestrator._loi_ngoai_pham_vi(bao_cao, "logic_pid") == []


def test_neo_file_tren_ToolError_cung_dung_duoc() -> None:
    """`metrics` là đường chính, `file` là đường dự phòng cho cổng khác."""
    bao_cao = ToolReport(
        gate="compile",
        passed=False,
        errors=[ToolError("hỏng", file="src/app_balance.c")],
    )
    assert Orchestrator._loi_ngoai_pham_vi(bao_cao, "logic_pid") == [
        "src/app_balance.c"
    ]


def test_canh_bao_khong_tinh_vao_phan_hang() -> None:
    """Chỉ lỗi mức ERROR mới quyết định — cảnh báo ngoài phạm vi là bình thường."""
    bao_cao = ToolReport(
        gate="static",
        passed=False,
        errors=[ToolError("hỏng ở đâu không rõ", severity=Severity.ERROR)],
        warnings=[ToolError("nhắc nhở", file="src/app_balance.c")],
    )
    assert Orchestrator._loi_ngoai_pham_vi(bao_cao, "logic_pid") == []


def test_duong_dan_co_tien_to_van_doi_chieu_dung() -> None:
    """`./tests/...` và `tests/...` là một tệp."""
    assert (
        Orchestrator._loi_ngoai_pham_vi(
            _bao_cao(["./tests/test_logic_pid.py"]), "logic_pid"
        )
        == []
    )
