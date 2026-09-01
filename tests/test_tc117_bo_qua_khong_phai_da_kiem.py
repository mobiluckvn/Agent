"""TC-117 — một bài kiểm tự bỏ qua chính nó không phải là một bài kiểm đã đạt.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-153.

Bài kiểm sinh cho `drv_imu` ngày 02/09/2026 mở đầu bằng::

    lib_path = os.environ.get("LIB_PATH", "./libdrv_imu.so")
    if not os.path.exists(lib_path):
        pytest.skip("Library not found")

pytest thoát 0 cho một lượt chạy chỉ toàn `skipped`, và cổng đọc mã thoát. Nên
câu trên biến ĐÚNG cái hỏng mà cổng phải bắt — mã không dịch được nên không có
thư viện — thành một lượt chạy màu xanh.

Cổng này đã nói sẵn câu đúng cho trường hợp KHÔNG CÓ test nào::

    "chưa có gì để chạy" không phải là "đã kiểm chứng"

Bỏ qua là đúng trường hợp ấy, chỉ khác ở chỗ tệp test có tồn tại.

Vì sao chặn cả khi các bài kiểm khác xanh
------------------------------------------

Cổng chạy CẢ thư mục test, nên số bài xanh phần lớn là của module khác. Một
lượt "16 passed, 1 skipped" trong đó bài bị bỏ qua đúng là bài của module đang
sinh vẫn là một lượt chưa kiểm gì về module ấy — mà nhìn vào mã thoát thì không
phân biệt được.
"""

from __future__ import annotations

from pathlib import Path

from eaa.tools.unittests import UnitTestGate


def _du_an(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "firmware"
    tests = work / "tests"
    tests.mkdir(parents=True)
    return work, tests


def test_toan_bo_bi_bo_qua_thi_cong_khong_dat(tmp_path: Path) -> None:
    work, tests = _du_an(tmp_path)
    (tests / "test_imu.py").write_text(
        "import os\n"
        "import pytest\n"
        "def test_imu():\n"
        "    if not os.path.exists('./libdrv_imu.so'):\n"
        "        pytest.skip('Library not found')\n"
        "    assert True\n",
        encoding="utf-8",
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    assert not bao_cao.passed, (
        "pytest thoát 0 cho một lượt chỉ toàn skipped. Cổng đọc mã thoát là đủ "
        "để 'chưa kiểm gì' thành ĐẠT."
    )
    assert bao_cao.metrics["skipped"] == 1
    assert bao_cao.metrics["passed"] == 0


def test_mot_bai_bi_bo_qua_giua_nhung_bai_xanh_van_chan(tmp_path: Path) -> None:
    """Hình dạng thật của lỗi: 16 xanh + 1 bỏ qua, và bài bỏ qua là bài quan trọng."""
    work, tests = _du_an(tmp_path)
    (tests / "test_khac.py").write_text(
        "\n".join(f"def test_khac_{i}():\n    assert True\n" for i in range(16)),
        encoding="utf-8",
    )
    (tests / "test_imu.py").write_text(
        "import pytest\n"
        "def test_imu():\n"
        "    pytest.skip('Library not found')\n",
        encoding="utf-8",
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    assert not bao_cao.passed
    assert bao_cao.metrics["passed"] == 16
    assert bao_cao.metrics["skipped"] == 1


def test_thong_bao_neu_ten_bai_va_ly_do_bo_qua(tmp_path: Path) -> None:
    """Một cổng đỏ mà không nói vì sao thì vòng tự sửa không có gì để sửa (SL-149)."""
    work, tests = _du_an(tmp_path)
    (tests / "test_imu.py").write_text(
        "import pytest\n"
        "def test_imu():\n"
        "    pytest.skip('Library not found')\n",
        encoding="utf-8",
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    van_ban = "\n".join(str(e) for e in bao_cao.errors)
    assert "Library not found" in van_ban
    assert "test_imu" in van_ban


def test_bai_hong_van_neu_dich_danh_ten_bai(tmp_path: Path) -> None:
    """Cờ `-r` THAY THẾ mặc định. Thêm `s` mà quên `f` là mất dòng FAILED."""
    work, tests = _du_an(tmp_path)
    (tests / "test_x.py").write_text(
        "def test_hong():\n    assert 1 == 2\n", encoding="utf-8"
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    assert not bao_cao.passed
    assert "test_hong" in bao_cao.errors[0].message


def test_moi_bai_deu_xanh_thi_cong_van_dat(tmp_path: Path) -> None:
    """Luật mới không được làm đỏ những lượt chạy vốn lành."""
    work, tests = _du_an(tmp_path)
    (tests / "test_x.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    assert bao_cao.passed
    assert bao_cao.metrics["skipped"] == 0
