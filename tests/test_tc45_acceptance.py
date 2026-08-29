"""TC-45 — khép vòng: số đo trên mạch → G4 → hạng ``hw-verified``.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-45a | Không phong hạng cho bản chưa từng chạy trên mạch | commit phong hạng phải khớp commit trong nhật ký nạp |
| TC-45b | Tiêu chí có TRƯỚC số đo | chưa khai `acceptance.measurements` thì không rút được số đo |
| TC-45c | Thiếu số đo đã khai là LỖI | không phải "bỏ qua mục ấy" |
| TC-45d | Vượt ngưỡng thì không phong hạng | đường đi của kết quả không đạt là `--reject` |
| TC-45e | Số đo rút từ telemetry đúng dạng bản ghi đo | nối được thẳng vào `VersionRegistry.promote` |

TC-45a là lý do cả nhóm này tồn tại. Không có nó, quy trình cho phép: nạp bản
A, đo bản A, sửa mã thành bản B, rồi phong ``hw-verified`` cho B. Bản B chưa
bao giờ chạy trên phần cứng — nhưng `known_good.lock` sẽ nói ngược lại, và
`known_good.lock` là thứ mọi lần quay lui về sau tin theo. Một lời nói dối ở
đây không dừng ở đây.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.acceptance import (
    AcceptanceError,
    DeviceCheck,
    AcceptanceSpec,
    MeasurementSpec,
    check_device_commit,
    derive_measurements,
)
from eaa.flash import FlashLog, FlashRecord

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"


def _spec(*muc: dict) -> AcceptanceSpec:
    return AcceptanceSpec.from_acceptance({"measurements": list(muc)})


SPEC_MAU = _spec(
    {"name": "max_tilt_deg", "unit": "°", "max": 1.0},
    {"name": "uptime_s", "unit": "s", "min": 600},
)


# --------------------------------------------------------------------------
# TC-45a — commit phong hạng phải là commit đang chạy trên thiết bị
# --------------------------------------------------------------------------


def _nhat_ky(tmp_path: Path, *commit_passed: tuple[str, bool]) -> FlashLog:
    log = FlashLog(tmp_path / "flash_log.jsonl")
    for i, (commit, dat) in enumerate(commit_passed):
        log.append(
            FlashRecord(
                image="fw.hex",
                image_digest="sha256:" + "0" * 64,
                commit=commit,
                port="/dev/ttyUSB0",
                actor="ky-su",
                flashed_at=f"2026-08-29T0{i}:00:00+00:00",
                passed=dat,
            )
        )
    return log


def test_commit_khop_thi_qua(tmp_path: Path) -> None:
    log = _nhat_ky(tmp_path, ("a" * 40, True))
    kiem = check_device_commit("a" * 40, log)
    assert kiem.verified and not kiem.blocking


def test_phong_hang_cho_ban_chua_tung_nap_bi_chan(tmp_path: Path) -> None:
    """Nạp bản A, đo bản A, rồi phong hạng cho bản B — chốt chính của bước này."""
    log = _nhat_ky(tmp_path, ("a" * 40, True))
    kiem = check_device_commit("b" * 40, log)

    assert not kiem.verified
    assert kiem.blocking, "nhật ký nói bản khác đang trên chip — đây là MÂU THUẪN"
    assert "KHÁC commit đang chạy" in kiem.message
    assert "aaaaaaaaaa" in kiem.message and "bbbbbbbbbb" in kiem.message


def test_chua_nap_lan_nao_la_THIEU_BIET_chu_khong_phai_mau_thuan(tmp_path: Path) -> None:
    """Kỹ sư nạp bằng IDE hay công cụ của hãng thì engine không biết — và
    "engine không biết" khác "engine biết là sai".

    Đối xử với hai chuyện ấy như nhau là sai, và sai theo hướng làm sản phẩm
    không dùng được cho một luồng làm việc hoàn toàn hợp lệ.
    """
    kiem = check_device_commit("a" * 40, FlashLog(tmp_path / "khong-co.jsonl"))

    assert not kiem.verified
    assert not kiem.blocking
    assert "KHÔNG kiểm được" in kiem.message
    assert "device_verified=false" in kiem.message


def test_lan_nap_truot_khong_tinh_la_bang_chung(tmp_path: Path) -> None:
    """Nạp trượt nghĩa là bản ấy KHÔNG chạy trên thiết bị."""
    log = _nhat_ky(tmp_path, ("a" * 40, False))
    assert not check_device_commit("a" * 40, log).verified


def test_lan_nap_thanh_cong_gan_nhat_moi_tinh(tmp_path: Path) -> None:
    log = _nhat_ky(tmp_path, ("a" * 40, True), ("b" * 40, True))
    assert check_device_commit("b" * 40, log).verified
    cu = check_device_commit("a" * 40, log)
    assert cu.blocking, "bản cũ đã bị bản mới ghi đè trên chip"


def test_khong_co_nhat_ky_thi_van_tra_loi_ro(tmp_path: Path) -> None:
    kiem = check_device_commit("a" * 40, None)
    assert not kiem.verified and not kiem.blocking


# --------------------------------------------------------------------------
# TC-45b — tiêu chí có trước số đo
# --------------------------------------------------------------------------


def test_chua_khai_tieu_chi_thi_khong_rut_duoc_so_do() -> None:
    """Nghiệm thu là đối chiếu hành vi thật với ngưỡng đã chốt từ A1.

    Ngưỡng viết sau khi nhìn số thì phép đối chiếu không còn nghĩa gì.
    """
    with pytest.raises(AcceptanceError, match="chưa khai"):
        derive_measurements({"max_tilt_deg": 0.5}, AcceptanceSpec())


def test_du_an_mau_khai_tieu_chi_nghiem_thu() -> None:
    from eaa.kb import Constraints

    rang_buoc = Constraints.load(DU_AN_MAU / "constraints.yaml")
    spec = AcceptanceSpec.from_acceptance(rang_buoc.acceptance)

    assert spec.measurements
    assert all(m.scored for m in spec.measurements), (
        "số đo nghiệm thu phải có ngưỡng — không có ngưỡng thì không chấm được"
    )


def test_nguong_nghiem_thu_khop_rang_buoc_cung() -> None:
    """Trần góc nghiêng ở hai chỗ phải là một con số.

    Hai nguồn sự thật cho cùng một ngưỡng sẽ lệch nhau ở lần sửa đầu tiên.
    """
    from eaa.kb import Constraints

    rang_buoc = Constraints.load(DU_AN_MAU / "constraints.yaml")
    spec = AcceptanceSpec.from_acceptance(rang_buoc.acceptance)

    goc = next(m for m in spec.measurements if m.name == "max_tilt_deg")
    assert goc.high == rang_buoc.acceptance["tilt_tolerance_deg"]

    chu_ky = next(m for m in spec.measurements if m.name == "loop_period_ms")
    assert chu_ky.high == rang_buoc.limits["control_loop_ms"]


def test_nguong_khong_phai_so_bi_tu_choi() -> None:
    with pytest.raises(AcceptanceError, match="không phải số"):
        _spec({"name": "x", "max": "nhanh"})


def test_muc_thieu_ten_bi_tu_choi() -> None:
    with pytest.raises(AcceptanceError, match="thiếu 'name'"):
        _spec({"key": "x"})


# --------------------------------------------------------------------------
# TC-45c — thiếu số đo đã khai là lỗi
# --------------------------------------------------------------------------


def test_thieu_so_do_da_khai_thi_khong_dat() -> None:
    """Một bản ghi có 1 trong 2 số đo trông y hệt một bản có đủ 2."""
    rut_ra = derive_measurements({"max_tilt_deg": 0.5}, SPEC_MAU)

    assert not rut_ra.ok
    assert len(rut_ra.missing) == 1
    assert "uptime_s" in rut_ra.missing[0]
    assert "THIẾU" in rut_ra.render()


def test_gia_tri_khong_phai_so_tinh_la_thieu() -> None:
    rut_ra = derive_measurements(
        {"max_tilt_deg": "khá ổn", "uptime_s": 700}, SPEC_MAU
    )
    assert not rut_ra.ok
    assert "không phải số" in rut_ra.missing[0]


def test_gia_tri_bool_khong_duoc_coi_la_so() -> None:
    """``True`` là 1 trong Python — nhưng "có/không" không phải một số đo."""
    rut_ra = derive_measurements({"max_tilt_deg": True, "uptime_s": 700}, SPEC_MAU)
    assert not rut_ra.ok
    assert any("max_tilt_deg" in t for t in rut_ra.missing)


# --------------------------------------------------------------------------
# TC-45d — vượt ngưỡng thì không phong hạng
# --------------------------------------------------------------------------


def test_vuot_tran_thi_khong_dat() -> None:
    rut_ra = derive_measurements({"max_tilt_deg": 1.4, "uptime_s": 700}, SPEC_MAU)

    assert not rut_ra.ok
    assert rut_ra.violations == ["max_tilt_deg = 1.4° vượt trần 1°"]
    assert "--reject" in rut_ra.render()


def test_duoi_san_thi_khong_dat() -> None:
    rut_ra = derive_measurements({"max_tilt_deg": 0.5, "uptime_s": 120}, SPEC_MAU)
    assert rut_ra.violations == ["uptime_s = 120s dưới sàn 600s"]


def test_vuot_nguong_van_giu_so_do_de_ghi_lai() -> None:
    """Số đo không đạt vẫn là số đo — nó vào bản ghi từ chối nghiệm thu."""
    rut_ra = derive_measurements({"max_tilt_deg": 1.4, "uptime_s": 700}, SPEC_MAU)
    assert len(rut_ra.measurements) == 2


def test_so_do_khong_co_nguong_chi_duoc_ghi_nhan() -> None:
    spec = _spec({"name": "nhiet_do_c", "unit": "°C"})
    rut_ra = derive_measurements({"nhiet_do_c": 41.0}, spec)

    assert rut_ra.ok
    assert not rut_ra.violations


def test_dung_ngay_o_nguong_thi_dat() -> None:
    rut_ra = derive_measurements({"max_tilt_deg": 1.0, "uptime_s": 600}, SPEC_MAU)
    assert rut_ra.ok


# --------------------------------------------------------------------------
# TC-45e — nối thẳng vào phong hạng
# --------------------------------------------------------------------------


def test_so_do_rut_ra_dung_dang_ban_ghi_do() -> None:
    from eaa.versions import Measurement

    rut_ra = derive_measurements({"max_tilt_deg": 0.7, "uptime_s": 900}, SPEC_MAU)

    assert rut_ra.ok
    assert all(isinstance(m, Measurement) for m in rut_ra.measurements)
    goc = next(m for m in rut_ra.measurements if m.name == "max_tilt_deg")
    assert goc.value == 0.7
    assert goc.unit == "°"


def test_khoa_telemetry_khac_ten_so_do() -> None:
    """Firmware đặt tên khóa thế nào là chuyện của firmware."""
    spec = _spec({"name": "goc_nghieng_max", "key": "tilt_max_deg", "max": 1.0})
    rut_ra = derive_measurements({"tilt_max_deg": 0.4}, spec)

    assert rut_ra.ok
    assert rut_ra.measurements[0].name == "goc_nghieng_max"


def test_noi_duoc_vao_phong_hang(tmp_path: Path) -> None:
    """Vòng khép kín: telemetry → số đo → promote(hw-verified)."""
    from eaa.gates import GateDecision
    from eaa.versions import Tier, VersionRegistry

    rut_ra = derive_measurements({"max_tilt_deg": 0.7, "uptime_s": 900}, SPEC_MAU)
    kho = VersionRegistry(
        ledger_path=tmp_path / "build_ledger.jsonl",
        lock_path=tmp_path / "known_good.lock",
    )
    quyet_dinh = GateDecision(
        gate_id="G4",
        decision="approved",
        actor="ky-su",
        decided_at="2026-08-29T00:00:00+00:00",
        payload_digest="sha256:" + "1" * 64,
        module="drv_bus_sensor",
    )

    ban_ghi = kho.promote(
        module="drv_bus_sensor",
        commit="a" * 40,
        tier=Tier.HW_VERIFIED,
        decision=quyet_dinh,
        measurements=rut_ra.measurements,
        reason="nghiệm thu vật lý tại G4",
    )

    assert ban_ghi.tier == Tier.HW_VERIFIED
    assert len(ban_ghi.measurements) == 2
    assert kho.known_good_of("drv_bus_sensor") == "a" * 40


def test_khong_co_so_do_thi_khong_phong_duoc_hang_phan_cung(tmp_path: Path) -> None:
    """Bất biến sẵn có từ Sprint 4, kiểm lại vì bước này đổi nguồn số đo."""
    from eaa.gates import GateDecision
    from eaa.versions import PromotionNotAuthorized, Tier, VersionRegistry

    kho = VersionRegistry(
        ledger_path=tmp_path / "build_ledger.jsonl",
        lock_path=tmp_path / "known_good.lock",
    )
    with pytest.raises(PromotionNotAuthorized):
        kho.promote(
            module="m",
            commit="a" * 40,
            tier=Tier.HW_VERIFIED,
            decision=GateDecision(
                gate_id="G4",
                decision="approved",
                actor="ky-su",
                decided_at="2026-08-29T00:00:00+00:00",
                payload_digest="sha256:" + "1" * 64,
                module="m",
            ),
            measurements=[],
        )
