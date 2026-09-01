"""TC-104 — quy trình phải sinh được thứ chính cổng của nó đòi.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-134.

Tìm ra khi gỡ chỗ chặn của bài robot cân bằng, sau SL-133.

`unittests` nằm trong ``required_gates``: không qua nó thì không merge được,
không merge thì không ráp được firmware. Nhưng bộ điều phối bảo mô hình sinh
**đúng hai tệp**::

    output_files=(f"src/{module_id}.c", f"src/{module_id}.h")

Không bao giờ có test. Nên **một cổng bắt buộc đòi thứ mà không năng lực nào
trong quy trình sinh ra**, và quy trình không có cách nào tự qua cổng của chính
nó. Nó chặn ở đúng module đầu tiên, và nó đã chặn như thế từ sprint đầu.

Vì sao đây không phải chuyện "quên viết test"
-----------------------------------------------

Thiết kế nói firmware được viết TÁCH LỚP TRỪU TƯỢNG PHẦN CỨNG chính là để chạy
được trên máy chủ (công đoạn C2). Lời hứa ấy chỉ thành thật khi mỗi module ra
đời KÈM bài kiểm chứng minh nó chạy được ở đó. Sinh mã mà không sinh test là
giữ lại lời hứa và bỏ đi phần trả giá cho nó.

Và mô hình không tự đoán ra được: ở SL-133 nó thử viết ``tests/test_dummy.c``,
một tệp C, vì không ai nói cổng ấy chạy pytest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent


def test_cong_bat_buoc_va_thu_duoc_sinh_ra_phai_KHOP_nhau() -> None:
    """Bài canh gốc: đừng đòi thứ mình không sinh ra.

    Không so từng tên tệp — nó hỏi một câu mạnh hơn: nếu `unittests` là cổng
    bắt buộc thì trong danh sách tệp phải sinh phải có ít nhất một tệp test.
    """
    from eaa.orchestrator import Orchestrator, OrchestratorConfig

    cong = OrchestratorConfig().required_gates
    tep = Orchestrator.tep_can_sinh("mod_x")

    if "unittests" in cong:
        assert any("test" in t for t in tep), (
            f"cổng bắt buộc {cong} có 'unittests', nhưng danh sách tệp phải "
            f"sinh là {tep} — không có tệp test nào. Quy trình đòi một thứ nó "
            "không sinh ra"
        )


def test_ten_tep_test_dung_quy_uoc_pytest() -> None:
    """Cổng gom `test_*.py`; đặt tên khác thì nó không thấy."""
    from eaa.orchestrator import Orchestrator

    tep = [t for t in Orchestrator.tep_can_sinh("drv_i2c") if "test" in t]
    assert tep, "không có tệp test"
    for t in tep:
        assert Path(t).name.startswith("test_") and t.endswith(".py"), (
            f"{t}: cổng unittests gom 'test_*.py', tệp này nó không thấy"
        )


def test_van_giu_hai_tep_nguon_nhu_cu() -> None:
    """Thêm test không được làm mất phần vốn có."""
    from eaa.orchestrator import Orchestrator

    tep = Orchestrator.tep_can_sinh("drv_i2c")
    assert "src/drv_i2c.c" in tep and "src/drv_i2c.h" in tep


# ═══════════ pack phải nói CÁCH kiểm mã C từ pytest ═══════════


def test_pack_khai_cach_kiem_tren_may_chu() -> None:
    """Mô hình không đoán ra được cách gọi mã C từ Python nếu không ai nói.

    Ở SL-133 nó thử viết `tests/test_dummy.c`. Cách dịch một module cho máy chủ
    là chuyện của NỀN TẢNG — trình dịch nào, cờ gì, tệp tiêu đề giả ở đâu — nên
    nó phải nằm ở pack, không phải trong prompt viết cứng ở engine.
    """
    d = yaml.safe_load((REPO / "packs" / "avr" / "pack.yaml").read_text(encoding="utf-8"))
    ht = d.get("host_test") or {}
    assert ht, "pack chưa khai `host_test`"
    assert ht.get("contract"), "chưa nói cách viết một bài kiểm chạy trên máy chủ"


def test_boi_canh_sinh_ma_co_phan_kiem_tren_may_chu() -> None:
    from eaa.composer import _boi_canh_host_test

    d = yaml.safe_load((REPO / "packs" / "avr" / "pack.yaml").read_text(encoding="utf-8"))
    van_ban = _boi_canh_host_test(d.get("host_test"))
    assert "pytest" in van_ban.lower()
    assert "ctypes" in van_ban.lower() or "thư viện" in van_ban.lower()


def test_khong_co_pack_thi_khong_them_gi() -> None:
    from eaa.composer import _boi_canh_host_test

    assert _boi_canh_host_test(None) == ""


# ═══════════ và cổng phải nhìn vào ĐÚNG chỗ mã được sinh ra ═══════════


def test_cong_unittests_nhin_vao_thu_muc_ma_bo_sinh_GHI_VAO() -> None:
    """Mảnh cuối của chỗ chặn, và là dạng sai khó thấy nhất trong nhóm này.

    Bộ sinh mã ghi vào thư mục làm việc của firmware: `firmware/src/` và
    `firmware/tests/`. Cổng `unittests` lại đọc `<dự án>/tests`. Hai thư mục
    KHÁC NHAU.

    Nên sau khi sửa SL-134, mô hình đã viết đúng `tests/test_logic_pid.py` —
    tệp nằm ngay đó — mà cổng vẫn báo *"không có bộ kiểm thử đơn vị nào"*.

    Không ai sai một mình: bộ sinh ghi đúng chỗ của nó, cổng đọc đúng chỗ của
    nó, và hai chỗ ấy chưa bao giờ được đối chiếu — vì chưa lần nào có tệp test
    thật để lộ ra.
    """
    import inspect

    from eaa import cli

    nguon = inspect.getsource(cli)
    i = nguon.index("UnitTestGate(")
    khoi = nguon[i:i + 400]
    assert 'tests_dir=project / "tests"' not in khoi, (
        "cổng đọc <dự án>/tests, còn bộ sinh ghi vào firmware/tests — tệp test "
        "sinh ra nằm ở chỗ cổng không nhìn"
    )
    assert "firmware" in khoi, "cổng phải đọc thư mục firmware, nơi mã được sinh"
