"""TC-99 — cửa sổ thu telemetry phải dài hơn thời gian kịch bản CHẠY.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-129.

Tìm ra ở DS-07, ngay sau khi tôi vừa tự mắc đúng lỗi ấy bằng tay.

`eaa diagnose run` thu telemetry trong **5 giây** cố định. DS-07 quay hai bánh
**4 giây**, và bootloader cũ của bo chờ 1–2 giây trước khi nhường quyền cho
ứng dụng. Nên lệnh bỏ cuộc trước khi bo kịp phát khung số liệu, và in ra:

    Kênh máy: KHÔNG ĐẠT
      ✗ Số xung bước đã phát: telemetry không có trường 'pulses_emitted'
      ✗ Tần số xung: telemetry không có trường 'pulse_freq_hz'

Bốn dòng `✗` cho một firmware chạy hoàn toàn đúng.

Vì sao chỗ này đáng sửa chứ không chỉ đáng nhớ
-----------------------------------------------

Câu *"telemetry không có trường X"* đọc thành *"firmware không phát trường
ấy"* — tức đổ lỗi cho bo. Sự thật là **người quan sát bỏ đi sớm**. Hai câu ấy
dẫn tới hai việc trái ngược: một bên đi sửa firmware, một bên chỉ cần chờ lâu
hơn.

Và một hằng số 5 giây thì không thể đúng cho mọi kịch bản: đo tĩnh xong trong
một nhịp, còn kịch bản chuyển động chạy vài giây theo thiết kế. Kịch bản biết
nó chạy bao lâu; lệnh thì không — nên con số ấy phải nằm ở kịch bản.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from eaa.diagnostics import ScenarioLibrary

DU_AN = Path(__file__).resolve().parents[1] / "projects" / "robot_balance"
THU_VIEN = DU_AN / "diagnostics.yaml"


def _lib() -> ScenarioLibrary:
    return ScenarioLibrary.load(THU_VIEN)


def test_kich_ban_khai_duoc_cua_so_thu() -> None:
    assert _lib().get("DS-07").collect_seconds > 0


def test_kich_ban_khong_khai_thi_ve_MAC_DINH() -> None:
    """Thêm trường mới không được đổi ngầm hành vi của kịch bản chưa khai nó."""
    assert _lib().get("DS-01").collect_seconds == 0.0


def test_cua_so_thu_DAI_HON_thoi_gian_kich_ban_chay() -> None:
    """Điểm cốt lõi, và nó tính được chứ không phải đoán.

    Thời gian chạy suy từ chính firmware: số xung × chu kỳ. Cộng thêm phần
    bootloader chờ trước khi nhường quyền — trên bo này là 1–2 giây, nên biên
    phải rộng hơn thế.
    """
    import re

    nguon = (DU_AN / "diagnostics" / "DS-07.c").read_text(encoding="utf-8")
    xung = int(re.search(r"#define\s+DIAG_PULSES\s+(\d+)", nguon).group(1))
    nua_chu_ky_us = int(re.search(r"#define\s+DIAG_HALF_US\s+(\d+)", nguon).group(1))
    giay_chay = xung * 2 * nua_chu_ky_us / 1_000_000

    khai = _lib().get("DS-07").collect_seconds
    assert khai > giay_chay + 2.0, (
        f"kịch bản chạy {giay_chay:g}s cộng bootloader chờ tới 2s, mà cửa sổ "
        f"thu chỉ khai {khai:g}s — lệnh sẽ bỏ cuộc trước khi bo kịp nói"
    )


def test_MOI_kich_ban_chuyen_dong_deu_phai_khai_cua_so_thu() -> None:
    """Kịch bản chuyển động chạy vài giây theo thiết kế; mặc định 5 giây không đủ.

    Bài này canh cả những kịch bản viết sau: thêm một kịch bản chuyển động mà
    quên khai cửa sổ thu thì nó sẽ báo "firmware không phát trường X" cho một
    firmware chạy đúng, và người đọc đi sửa nhầm chỗ.
    """
    thieu = [
        s.id for s in _lib().scenarios
        if s.motion and not s.collect_seconds
    ]
    assert not thieu, (
        f"kịch bản chuyển động chưa khai collect_seconds: {thieu}. Mặc định 5 "
        "giây ngắn hơn thời gian chúng chạy"
    )


def test_cua_so_thu_trong_yaml_la_SO() -> None:
    """Gõ nhầm thành chuỗi thì phải hỏng lúc nạp, không phải lúc đo."""
    d = yaml.safe_load(THU_VIEN.read_text(encoding="utf-8"))
    for s in d["scenarios"]:
        if "collect_seconds" in s:
            assert isinstance(s["collect_seconds"], (int, float)), (
                f"{s['id']}: collect_seconds không phải số"
            )
