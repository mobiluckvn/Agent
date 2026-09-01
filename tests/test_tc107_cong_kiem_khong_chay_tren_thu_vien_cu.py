"""TC-107 — cổng kiểm thử không được chạy trên thư viện của lần trước.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-137.

Tìm ra khi review G3 vòng thứ ba của `logic_pid`. Bộ test do mô hình sinh mở
đầu thế này::

    try:
        subprocess.check_call(['cc', ..., '-o', lib_path, src_path])
    except Exception:
        pass  # Bỏ qua nếu test runner đã tự biên dịch

    return ctypes.CDLL(lib_path)

Lệnh dịch hỏng thì bị nuốt, và ``ctypes`` nạp thư viện CÒN SÓT của lần chạy
trước. Đo thật, không suy đoán — xóa một dấu chấm phẩy trong `logic_pid.c` rồi
chạy lại::

    >>> giờ làm HỎNG mã nguồn (xoá dấu chấm phẩy) rồi chạy lại:
    ....                                                        [100%]
    4 passed in 0.09s

**Bốn bài kiểm xanh trên một tệp nguồn không dịch nổi.** Cổng kiểm thử là mắt
xích thứ tư của chuỗi kiểm chứng, và ở trạng thái ấy nó không kiểm chứng gì cả.

Vì sao sửa bằng cấu trúc chứ không bằng lời dặn
-----------------------------------------------

Hợp đồng của pack nay cấm thẳng việc nuốt lỗi dịch. Nhưng một luật chỉ sống
trong prompt là một luật phụ thuộc vào việc mô hình có đọc kỹ hay không — và
chính mô hình ấy vừa viết ra ``except Exception: pass`` kèm lời giải thích
nghe rất hợp lý.

Xóa sản phẩm dịch cũ trước mỗi lần chạy làm việc nuốt lỗi KHÔNG CÒN CHỖ ẨN:
không có thư viện cũ thì ``ctypes`` sập, và cổng đỏ đúng lúc phải đỏ. Luật
trong prompt vẫn giữ — nó nói cho mô hình biết vì sao — nhưng cái cưỡng chế
nằm ở cấu trúc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.tools.unittests import UnitTestGate

REPO = Path(__file__).resolve().parent.parent


def test_xoa_thu_vien_da_dich_cua_lan_truoc(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    cu = tests / "logic_pid.so"
    cu.write_bytes(b"\x7fELF")

    UnitTestGate(work_dir=tmp_path, tests_dir=tests).run()

    assert not cu.exists(), (
        "thư viện của lần chạy trước còn nguyên — một bộ test nuốt lỗi dịch sẽ "
        "nạp đúng nó và cổng báo ĐẠT trên mã không dịch nổi"
    )


def test_xoa_ca_cac_duoi_san_pham_dich_KHAC(tmp_path: Path) -> None:
    """Máy chủ khác thì đuôi khác; bỏ sót một đuôi là bỏ ngỏ đúng lối ấy."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    rac = [tests / f"m{d}" for d in UnitTestGate.DUOI_SAN_PHAM_DICH]
    for r in rac:
        r.write_bytes(b"x")

    UnitTestGate(work_dir=tmp_path, tests_dir=tests).run()

    assert not [r.name for r in rac if r.exists()]


def test_KHONG_dung_toi_ma_test(tmp_path: Path) -> None:
    """Dọn sản phẩm dịch không được biến thành dọn cả bộ test."""
    tests = tmp_path / "tests"
    (tests / "du_lieu").mkdir(parents=True)
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (tests / "conftest.py").write_text("", encoding="utf-8")
    (tests / "du_lieu" / "mau.csv").write_text("a,b\n", encoding="utf-8")

    UnitTestGate(work_dir=tmp_path, tests_dir=tests).run()

    assert (tests / "test_x.py").is_file()
    assert (tests / "conftest.py").is_file()
    assert (tests / "du_lieu" / "mau.csv").is_file()


def test_khong_co_thu_muc_test_thi_khong_sap(tmp_path: Path) -> None:
    assert UnitTestGate._don_san_pham_dich(tmp_path / "khong_co") == []


def test_bo_test_NUOT_LOI_DICH_thi_cong_van_do(tmp_path: Path) -> None:
    """Bài canh thật: dựng lại đúng cái bẫy, và đòi cổng phải đỏ.

    Bộ test dưới đây nuốt lỗi dịch y như bản mô hình đã sinh. Nguồn C hỏng cú
    pháp. Nếu còn thư viện cũ nằm đó thì nó sẽ xanh — và đó chính là chỗ phải
    chặn.
    """
    import shutil
    import subprocess

    if shutil.which("cc") is None:  # pragma: no cover - máy không có trình dịch
        pytest.skip("máy này không có `cc`")

    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    # Bản chạy được, để sinh ra thư viện "của lần trước".
    (src / "m.c").write_text("int cong(int a, int b) { return a + b; }\n", encoding="utf-8")
    subprocess.run(
        ["cc", "-std=c11", "-fPIC", "-shared", "-o", str(tests / "m.so"), str(src / "m.c")],
        check=True,
    )
    assert (tests / "m.so").is_file()

    (tests / "test_m.py").write_text(
        "import ctypes, os, subprocess\n"
        "here = os.path.dirname(__file__)\n"
        "try:\n"
        "    subprocess.check_call(['cc', '-std=c11', '-fPIC', '-shared',\n"
        "                           '-o', os.path.join(here, 'm.so'),\n"
        "                           os.path.join(here, '..', 'src', 'm.c')])\n"
        "except Exception:\n"
        "    pass\n"
        "lib = ctypes.CDLL(os.path.join(here, 'm.so'))\n"
        "def test_cong():\n"
        "    assert lib.cong(2, 3) == 5\n",
        encoding="utf-8",
    )

    # Giờ làm hỏng nguồn: cổng PHẢI đỏ, dù thư viện cũ vẫn trả lời đúng.
    (src / "m.c").write_text("int cong(int a, int b) { return a + b }\n", encoding="utf-8")

    bao_cao = UnitTestGate(work_dir=tmp_path, tests_dir=tests).run()

    assert bao_cao.passed is False, (
        "cổng báo ĐẠT trên mã nguồn không dịch nổi — nó đang kiểm thư viện của "
        "lần chạy trước"
    )


# ═══════════ và hợp đồng của pack phải nói ra luật ấy ═══════════


def test_pack_cam_nuot_loi_dich() -> None:
    """Cấu trúc chặn được, nhưng mô hình vẫn nên biết VÌ SAO đừng viết thế."""
    import yaml

    d = yaml.safe_load((REPO / "packs" / "avr" / "pack.yaml").read_text(encoding="utf-8"))
    hop_dong = ((d.get("host_test") or {}).get("contract") or "").lower()

    assert "dịch" in hop_dong
    assert "try" in hop_dong or "nuốt" in hop_dong, (
        "hợp đồng không nói gì về việc nuốt lỗi dịch"
    )
