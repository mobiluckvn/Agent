"""TC-116 — cổng kiểm thử đơn vị dọn sản phẩm dịch ở ĐÚNG chỗ bài kiểm ghi ra.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-152.

Cổng đã có sẵn một bước dọn, kèm một chú thích dài giải thích vì sao nó cần
thiết: bài kiểm dịch mã C thành thư viện dùng chung rồi nạp bằng ``ctypes``, và
nếu nó nuốt lỗi dịch thì ``ctypes`` sẽ nạp thư viện CÒN SÓT của lần trước —
cổng báo ĐẠT trên một tệp nguồn thậm chí không dịch nổi.

Bước dọn ấy quét ``tests_dir``. Thư viện thì nằm ở ``work_dir``::

    cc ... -o ./libdrv_imu.so      # `.` của tiến trình pytest là work_dir

Nên trong suốt thời gian nó tồn tại, bước dọn chưa xoá được một tệp nào của
thứ nó sinh ra để chặn.

Đo được, ngày 02/09/2026
------------------------

Lượt sinh `drv_imu` bị chấm bằng `libdrv_imu.so` dịch từ 23:16 hôm trước. Bài
kiểm mới không tự dịch, chỉ nạp; con số nó đọc được là con số của mã CŨ. Ba
vòng tự sửa và bốn lượt gọi mô hình đi vá một sai lệch mà mã đang sửa không hề
gây ra.

Vì sao không quét đệ quy ``work_dir``
--------------------------------------

``work_dir/build/`` là sản phẩm của cổng dịch chéo chạy TRƯỚC cổng này, và của
`eaa build` chạy sau. Quét đệ quy là cổng này đi phá bằng chứng của cổng khác.
Một tầng là đủ, vì `.` của pytest chỉ có một tầng.
"""

from __future__ import annotations

from pathlib import Path

from eaa.tools.unittests import UnitTestGate


def _du_an(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "firmware"
    tests = work / "tests"
    tests.mkdir(parents=True)
    return work, tests


def test_thu_vien_cu_o_work_dir_bi_xoa_truoc_khi_chay(tmp_path: Path) -> None:
    """Chỗ SL-152 nằm: thư viện ở gốc thư mục làm việc, không phải trong tests/."""
    work, tests = _du_an(tmp_path)
    cu = work / "libdrv_imu.so"
    cu.write_bytes(b"nhi phan cua lan chay truoc")

    da_xoa = UnitTestGate._don_san_pham_dich(tests, work)

    assert not cu.exists(), (
        "Thư viện của lượt trước còn nguyên ở work_dir. Bài kiểm nạp nó bằng "
        "ctypes và cổng sẽ chấm mã mới bằng nhị phân cũ."
    )
    assert "libdrv_imu.so" in da_xoa


def test_van_xoa_trong_tests_dir_nhu_truoc(tmp_path: Path) -> None:
    """Bản quét cũ không sai, chỉ thiếu — nên chỗ nó đã canh phải giữ nguyên."""
    work, tests = _du_an(tmp_path)
    (tests / "libcu.so").write_bytes(b"x")
    (tests / "sau").mkdir()
    (tests / "sau" / "libsau.dylib").write_bytes(b"x")

    da_xoa = UnitTestGate._don_san_pham_dich(tests, work)

    assert not (tests / "libcu.so").exists()
    assert not (tests / "sau" / "libsau.dylib").exists()
    assert sorted(da_xoa) == ["libcu.so", "libsau.dylib"]


def test_khong_dung_toi_build_cua_cong_dich(tmp_path: Path) -> None:
    """`build/` là bằng chứng của cổng dịch chéo — cổng này không được phá."""
    work, tests = _du_an(tmp_path)
    build = work / "build"
    build.mkdir()
    doi_tuong = build / "drv_imu.o"
    doi_tuong.write_bytes(b"elf cua avr-gcc")

    UnitTestGate._don_san_pham_dich(tests, work)

    assert doi_tuong.exists(), (
        "Cổng kiểm thử đơn vị vừa xoá sản phẩm của cổng dịch chéo. Cổng size "
        "và `eaa build` đọc chính thư mục ấy."
    )


def test_ma_nguon_khong_bao_gio_bi_xoa(tmp_path: Path) -> None:
    """Chỉ xoá thứ lượt chạy sau tự tạo lại được."""
    work, tests = _du_an(tmp_path)
    src = work / "src"
    src.mkdir()
    (src / "drv_imu.c").write_text("int main(void){return 0;}", encoding="utf-8")
    (tests / "test_drv_imu.py").write_text("def test_x():\n    pass\n", encoding="utf-8")

    UnitTestGate._don_san_pham_dich(tests, work)

    assert (src / "drv_imu.c").exists()
    assert (tests / "test_drv_imu.py").exists()


def test_chay_that_thi_thu_vien_cu_khong_song_qua_luot(tmp_path: Path) -> None:
    """Đường kiểm đầu-cuối: cổng chạy xong thì tệp cũ đã biến mất.

    Bài kiểm ở đây cố tình PHỤ THUỘC vào tệp cũ. Nếu bước dọn không chạy, nó
    xanh; dọn rồi thì nó đỏ — đúng chiều cổng phải đỏ.
    """
    work, tests = _du_an(tmp_path)
    (work / "libdrv_imu.so").write_bytes(b"x")
    (tests / "test_nap.py").write_text(
        "import os\n"
        "def test_nap():\n"
        "    assert os.path.exists('libdrv_imu.so'), 'khong co thu vien'\n",
        encoding="utf-8",
    )

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=work).run()

    assert not bao_cao.passed
    assert not (work / "libdrv_imu.so").exists()
