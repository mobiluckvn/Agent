"""TC-98 — câu hỏi cho NGƯỜI phải khớp thứ firmware THẬT SỰ làm.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-126.

Tìm ra ở Bài 3 phiên kiểm bo thật, ngay sau khi động cơ quay được lần đầu.

DS-03 hỏi người: *"Có quay đủ một vòng không (không trượt bước, không kêu
lạ)?"* — trong khi firmware của chính kịch bản ấy cố ý chỉ phát **200 xung**,
và với vi bước 1/16 trên động cơ 200 bước/vòng thì đó là **1/16 vòng**, khoảng
22°. Chú thích trong firmware nói rõ vì sao chọn dưới một vòng: *"một lệnh quay
nhiều vòng vẫn đủ để một sợi dây bị cuốn vào bánh."*

Nên người quan sát TRUNG THỰC buộc phải trả lời "không". Và bộ luật có đúng một
dòng cho tổ hợp ấy:

    {truc_quay: true, dung_chieu: true, du_mot_vong: false} → vùng lỗi: cơ khí

Tức một robot đang chạy hoàn toàn đúng bị chấm là **hỏng cơ khí**, và người ta
sẽ đi tháo bánh ra kiểm.

Vì sao chỗ này nguy hiểm hơn một câu chữ vụng
----------------------------------------------

Kênh người là kênh được dựng lên để làm ĐỐI CHỨNG cho kênh máy — nó tồn tại vì
số liệu một mình có thể "đẹp" mà sai. Một câu hỏi sai ở đây không chỉ mất tác
dụng đối chứng: nó **chủ động bơm dữ liệu sai** vào phép giao hai kênh, và phép
giao ấy không có cách nào biết.

Bài này canh quan hệ giữa hai thứ vốn nằm ở hai tệp khác nhau và không ai đối
chiếu: số xung trong firmware, và câu chữ trong kịch bản.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

DU_AN = Path(__file__).resolve().parents[1] / "projects" / "robot_balance"


def _so_xung() -> int:
    nguon = (DU_AN / "diagnostics" / "DS-03.c").read_text(encoding="utf-8")
    m = re.search(r"#define\s+DIAG_PULSES\s+(\d+)", nguon)
    assert m, "không đọc được DIAG_PULSES từ firmware"
    return int(m.group(1))


def _driver() -> dict:
    hs = yaml.safe_load((DU_AN / "hardware_profile.yaml").read_text(encoding="utf-8"))
    return next(c for c in hs["components"] if c["id"].startswith("motor_driver"))


def _tep() -> dict:
    return yaml.safe_load((DU_AN / "diagnostics.yaml").read_text(encoding="utf-8"))


def _ds03() -> dict:
    return next(s for s in _tep()["scenarios"] if s["id"] == "DS-03")


def _luat() -> list:
    """Bộ luật nằm ở `matrix` TOÀN CỤC, không trong từng kịch bản."""
    return _tep().get("matrix") or []


def test_phep_quy_doi_xung_sang_goc_duoc_KHAI_du() -> None:
    """`steps_per_rev` phải nằm trong hồ sơ, không nằm trong đầu người viết.

    Một hằng số không khai thì không đối chiếu được — và đó chính là lý do câu
    hỏi cho người lệch khỏi firmware mà bốn sprint không ai thấy.
    """
    drv = _driver()
    assert drv.get("steps_per_rev"), "hồ sơ chưa khai số bước mỗi vòng"
    assert drv.get("microstep"), "hồ sơ chưa khai vi bước"


def test_cau_hoi_KHONG_doi_mot_vong_khi_firmware_quay_it_hon() -> None:
    """Điểm cốt lõi: đừng hỏi người một câu mà firmware không cho phép trả lời "có"."""
    drv = _driver()
    mot_vong = int(drv["steps_per_rev"]) * int(drv["microstep"])
    xung = _so_xung()

    cau = " ".join(h["question"] for h in _ds03()["human"]).lower()
    if xung < mot_vong:
        assert "một vòng" not in cau and "đủ vòng" not in cau, (
            f"firmware chỉ phát {xung}/{mot_vong} xung (~{360*xung//mot_vong}°) "
            "mà vẫn hỏi người về MỘT VÒNG — trả lời trung thực sẽ thành một "
            "kết luận hỏng sai"
        )


def test_moi_khoa_trong_LUAT_deu_co_cau_hoi_tuong_ung() -> None:
    """Luật tham chiếu một khóa không ai hỏi thì nó không bao giờ khớp.

    Đổi tên khóa mà quên đổi ở bộ luật là cách làm một dòng luật chết lặng lẽ:
    không lỗi, không cảnh báo, chỉ là một tổ hợp không bao giờ xảy ra.
    """
    # Gom mọi khóa mọi kịch bản hỏi: bộ luật là toàn cục nên nó được phép
    # tham chiếu khóa của kịch bản khác.
    co_hoi = {
        h["key"] for s in _tep()["scenarios"] for h in (s.get("human") or [])
    }
    for luat in _luat():
        for khoa in (luat.get("when_human") or {}):
            assert khoa in co_hoi, (
                f"luật dùng khóa {khoa!r} mà không kịch bản nào hỏi câu cho nó"
            )


def test_moi_cau_hoi_deu_duoc_it_nhat_MOT_luat_dung_toi() -> None:
    """Hỏi người một câu rồi không dùng câu trả lời là lấy công của họ mà bỏ đi."""
    dung_toi = set()
    for luat in _luat():
        dung_toi |= set((luat.get("when_human") or {}).keys())
    for h in _ds03()["human"]:
        assert h["key"] in dung_toi, (
            f"câu hỏi {h['key']!r} không luật nào dùng tới"
        )
