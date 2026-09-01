"""TC-103 — "dự án chưa có bộ kiểm" là lỗi DỰ ÁN, không phải lỗi mã.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-133.

Tìm ra ở module đầu tiên của bài robot cân bằng. `eaa gen logic_pid`:

    ── sinh lần đầu ──   compile ĐẠT · size ĐẠT · static ĐẠT · unittests KHÔNG ĐẠT
    ── vòng vá 1 ──      compile ĐẠT · size ĐẠT · static ĐẠT · unittests KHÔNG ĐẠT
    ── vòng vá 2 ──      compile ĐẠT · size ĐẠT · static ĐẠT · unittests KHÔNG ĐẠT

    Vòng vá thất bại: Phản hồi chứa hai khối cho cùng một tệp:
    'tests/test_dummy.c'

Ba lượt gọi mô hình bị đốt cho một cổng mà **không bản vá nào của module có
thể làm đạt**: lý do trượt là *"không có bộ kiểm thử đơn vị nào trong
projects/…/tests"*. Mã nguồn module hoàn toàn đúng — nó vừa qua ba cổng còn
lại. Thứ còn thiếu là một phần của DỰ ÁN, không nằm trong tệp đang sửa.

Cơ chế đã có sẵn và đúng
-------------------------

`orchestrator` đã biết dừng khi gặp lỗi cấu hình, và câu nó nói ra đã đúng
sẵn:

    Lỗi CẤU HÌNH, không phải lỗi mã — vòng tự sửa không mở.
    Mô hình không sửa được một luật còn thiếu trong pack hay một ràng buộc
    khai báo sai; đưa nó vào vòng vá chỉ đốt lượt gọi và làm hỏng mã đang đúng.

Cổng `unittests` chỉ **không đặt cờ ấy**. Cơ chế đúng, phân loại thiếu — nên
lỗi rơi vào nhánh mặc định là "chắc tại mã".

Và mô hình không biết cổng ấy chạy bằng gì
-------------------------------------------

Nó thử tạo ``tests/test_dummy.c`` — một tệp **C**. Cổng chạy **pytest**, vì
theo công đoạn C2 firmware được viết tách lớp trừu tượng phần cứng để chạy
được trên máy chủ. Không chỗ nào nói điều đó cho mô hình, nên nó đoán bằng
thứ quen nhất với ngữ cảnh: đây là dự án C.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.tools.unittests import UnitTestGate


def test_khong_co_bo_kiem_thi_danh_dau_LOI_CAU_HINH(tmp_path: Path) -> None:
    """Điểm cốt lõi: vòng tự sửa không được mở cho chuyện này."""
    (tmp_path / "tests").mkdir()
    bao_cao = UnitTestGate(work_dir=tmp_path, tests_dir=tmp_path / "tests").run()

    assert bao_cao.passed is False
    assert bao_cao.metrics.get("config_error") is True, (
        "không đánh dấu là lỗi cấu hình — vòng tự sửa sẽ đốt cả ba lượt cho "
        "một cổng mà không bản vá nào của module làm đạt được"
    )


def test_thong_bao_NEU_TEN_khung_kiem_thu(tmp_path: Path) -> None:
    """Mô hình đoán bằng thứ quen nhất nếu không ai nói.

    Nó đã thử viết `tests/test_dummy.c` — tệp C — cho một cổng chạy pytest.
    """
    (tmp_path / "tests").mkdir()
    loi = " ".join(
        str(e) for e in UnitTestGate(work_dir=tmp_path, tests_dir=tmp_path / "tests").run().errors
    )
    assert "pytest" in loi.lower(), "không nói cổng này chạy bằng gì"
    assert "python" in loi.lower() or ".py" in loi, "không nói tệp test viết bằng gì"


def test_thong_bao_noi_ro_MA_MODULE_KHONG_PHAI_van_de(tmp_path: Path) -> None:
    """Người đọc — và mô hình đọc lại — phải biết đừng đi sửa module."""
    (tmp_path / "tests").mkdir()
    loi = " ".join(
        str(e) for e in UnitTestGate(work_dir=tmp_path, tests_dir=tmp_path / "tests").run().errors
    )
    thap = loi.lower()
    assert "không phải lỗi mã" in thap or "không nằm ở mã" in thap


def test_CO_bo_kiem_ma_TRUOT_thi_KHONG_phai_loi_cau_hinh(tmp_path: Path) -> None:
    """Phân biệt hai chuyện: 'chưa có test' và 'test chạy rồi và đỏ'.

    Cái sau ĐÚNG là việc của vòng tự sửa — mã vừa sinh làm một bài kiểm đỏ thì
    mô hình sửa được. Đánh dấu cả hai là lỗi cấu hình sẽ tắt luôn vòng tự sửa
    ở đúng chỗ nó có ích.
    """
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_that_bai.py").write_text(
        "def test_x():\n    assert 1 == 2\n", encoding="utf-8"
    )
    bao_cao = UnitTestGate(work_dir=tmp_path, tests_dir=tests).run()

    assert bao_cao.passed is False
    assert not bao_cao.metrics.get("config_error"), (
        "test đỏ là việc của vòng tự sửa, không phải lỗi cấu hình"
    )


def test_CO_bo_kiem_va_XANH_thi_dat(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    assert UnitTestGate(work_dir=tmp_path, tests_dir=tests).run().passed is True


def test_allow_empty_van_giu_duong_cu(tmp_path: Path) -> None:
    """Chế độ cho phép rỗng không được đổi ngầm: nó vẫn ĐẠT và không phải lỗi."""
    (tmp_path / "tests").mkdir()
    bao_cao = UnitTestGate(
        work_dir=tmp_path, tests_dir=tmp_path / "tests", allow_empty=True
    ).run()
    assert bao_cao.passed is True
    assert not bao_cao.metrics.get("config_error")
