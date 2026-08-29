"""TC-27, TC-28 — chẩn đoán phần cứng cộng tác hai kênh.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-27 | Telemetry báo xung phát đủ, người báo trục không quay | kết luận vùng lỗi PHẦN ĐIỆN, **KHÔNG mở vòng sửa mã**, hướng dẫn theo pin map |
| TC-28 | Chạy DS-03 khi chưa xác nhận checklist an toàn | kịch bản có chuyển động không chạy; đòi xác nhận robot đã kê an toàn |

TC-27 là test thể hiện rõ nhất luận điểm trung tâm của đề án. Máy biết nó ĐÃ
PHÁT xung; nó không biết trục có QUAY. Người thấy trục không quay; người không
biết xung có ra hay không. Một mình mỗi bên đều kết luận sai — máy sẽ sửa mã
đang đúng, người sẽ nghi ngờ mã trong khi lỗi nằm ở sợi dây.

Hệ quả kỹ thuật đáng chú ý: **không mở vòng sửa mã** là một hành vi tích cực,
không phải sự thụ động. Mở vòng sửa ở đó là bắt mô hình sửa một thứ không hỏng
— tốn tiền, và gần như chắc chắn làm hỏng thứ đang đúng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.diagnostics import (
    Diagnosis,
    DiagnosticError,
    DiagnosticSession,
    FlashNotConfirmed,
    SafetyChecklistNotConfirmed,
    ScenarioLibrary,
    Verdict,
)
from eaa.ledger import ErrorLedger

REPO = Path(__file__).resolve().parent.parent
THU_VIEN = REPO / "projects" / "robot_balance" / "diagnostics.yaml"

CHECKLIST_DS03 = (
    "Robot đã được kê lên giá, bánh KHÔNG chạm đất",
    "Không có vật cản hay tay người trong vùng bánh quay",
    "Nguồn động lực đã cấp đúng điện áp và dòng giới hạn đã chỉnh",
)


@pytest.fixture()
def thu_vien() -> ScenarioLibrary:
    return ScenarioLibrary.load(THU_VIEN)


@pytest.fixture()
def phien(thu_vien: ScenarioLibrary, tmp_path: Path) -> DiagnosticSession:
    return DiagnosticSession(
        library=thu_vien,
        records_path=tmp_path / "measurements.jsonl",
        ledger=ErrorLedger(tmp_path / "error_ledger.jsonl"),
    )


# --------------------------------------------------------------------------
# Thư viện kịch bản của dự án
# --------------------------------------------------------------------------


def test_thu_vien_du_sau_kich_ban(thu_vien: ScenarioLibrary) -> None:
    assert [s.id for s in thu_vien.scenarios] == [
        "DS-01", "DS-02", "DS-03", "DS-04", "DS-05", "DS-06"
    ]


def test_kich_ban_tu_dong_hoan_toan_khong_co_muc_nguoi(thu_vien: ScenarioLibrary) -> None:
    """DS-01 quét bus — máy tự kết luận, không cần ai nhìn (AIS §7.2)."""
    assert thu_vien.get("DS-01").fully_automatic
    assert not thu_vien.get("DS-03").fully_automatic


def test_moi_kich_ban_co_chuyen_dong_deu_co_checklist(thu_vien: ScenarioLibrary) -> None:
    for s in thu_vien.scenarios:
        if s.motion:
            assert s.safety_checklist, f"{s.id} có chuyển động mà thiếu checklist"


def test_kich_ban_co_chuyen_dong_ma_thieu_checklist_bi_tu_choi_luc_nap(
    tmp_path: Path,
) -> None:
    (tmp_path / "d.yaml").write_text(
        "scenarios:\n  - id: DS-X\n    motion: true\n", encoding="utf-8"
    )
    with pytest.raises(DiagnosticError, match="không chạy được"):
        ScenarioLibrary.load(tmp_path / "d.yaml")


def test_chon_kich_ban_tu_trieu_chung_cua_nguoi(thu_vien: ScenarioLibrary) -> None:
    """AIS §7.3: người mô tả triệu chứng, Agent tổ hợp kịch bản."""
    chon = thu_vien.select("robot không phản ứng khi nghiêng")
    ma = {s.id for s in chon}
    assert "DS-01" in ma and "DS-02" in ma, "cần cả quét bus lẫn kiểm cảm biến"

    dong_co = thu_vien.select("động cơ không quay")
    assert "DS-03" in {s.id for s in dong_co}


def test_trieu_chung_khong_khop_thi_tra_rong(thu_vien: ScenarioLibrary) -> None:
    assert thu_vien.select("màu sơn không đẹp") == []


# --------------------------------------------------------------------------
# TC-28 — checklist an toàn
# --------------------------------------------------------------------------


def test_tc28_chay_DS03_khi_chua_xac_nhan_an_toan_bi_chan(
    phien: DiagnosticSession,
) -> None:
    with pytest.raises(SafetyChecklistNotConfirmed) as loi:
        phien.prepare("DS-03")

    thong_diep = str(loi.value)
    assert "CHUYỂN ĐỘNG" in thong_diep
    assert "kê lên giá" in thong_diep, "phải nêu đích danh mục an toàn còn thiếu"
    assert "bánh KHÔNG chạm đất" in thong_diep


def test_tc28_xac_nhan_THIEU_MOT_muc_van_bi_chan(phien: DiagnosticSession) -> None:
    """Checklist an toàn không có phần trăm — thiếu một mục là chưa an toàn."""
    with pytest.raises(SafetyChecklistNotConfirmed):
        phien.prepare("DS-03", safety_confirmed=CHECKLIST_DS03[:2])


def test_tc28_xac_nhan_du_thi_chay_duoc(phien: DiagnosticSession) -> None:
    kich_ban = phien.prepare("DS-03", safety_confirmed=CHECKLIST_DS03)
    assert kich_ban.id == "DS-03"


def test_kich_ban_khong_chuyen_dong_khong_doi_checklist(phien: DiagnosticSession) -> None:
    assert phien.prepare("DS-01").id == "DS-01"


def test_nap_firmware_luon_can_xac_nhan_ke_ca_kich_ban_tinh(
    thu_vien: ScenarioLibrary,
) -> None:
    """FR-DIA-02: nạp là ghi đè bộ nhớ thiết bị — không bao giờ tự động."""
    phien = DiagnosticSession(library=thu_vien, flasher=object())

    with pytest.raises(FlashNotConfirmed, match="cần người xác nhận"):
        phien.prepare("DS-01")

    assert phien.prepare("DS-01", flash_confirmed_by="Vũ Trí Công").id == "DS-01"


# --------------------------------------------------------------------------
# TC-27 — giao hai kênh
# --------------------------------------------------------------------------


TELEMETRY_XUNG_DU = {"pulses_emitted": 200, "pulse_freq_hz": 1000}


def test_tc27_xung_du_ma_truc_khong_quay_la_loi_PHAN_DIEN(
    phien: DiagnosticSession,
) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )

    assert ket_luan.verdict == Verdict.ELECTRICAL
    assert ket_luan.machine_passed is True


def test_tc27_KHONG_mo_vong_sua_ma(phien: DiagnosticSession) -> None:
    """Mở vòng sửa ở đây là bắt mô hình sửa một thứ không hỏng."""
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )

    assert not ket_luan.opens_repair_loop
    assert "KHÔNG mở vòng sửa mã" in ket_luan.render()


def test_tc27_huong_dan_kiem_theo_pin_map(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )
    assert "pin map" in ket_luan.action or "hardware_profile" in ket_luan.action
    assert "Vref" in ket_luan.action


def test_tc27_khong_ghi_vao_error_ledger_khi_loi_khong_thuoc_ma(
    phien: DiagnosticSession, tmp_path: Path
) -> None:
    """Error Ledger là nhật ký lỗi của AI — lỗi dây nối không thuộc về nó."""
    phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )
    assert ErrorLedger(tmp_path / "error_ledger.jsonl").entries() == []


def test_xung_khong_phat_duoc_thi_MOI_la_loi_ma(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry={"pulses_emitted": 0, "pulse_freq_hz": 0},
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )

    assert ket_luan.verdict == Verdict.CODE
    assert ket_luan.opens_repair_loop
    assert "bộ đếm chưa chạy" in ket_luan.action


def test_loi_ma_thi_ghi_vao_error_ledger(phien: DiagnosticSession, tmp_path: Path) -> None:
    """AIS §7.3: phiên chẩn đoán cũng là phiên nạp tri thức."""
    phien.diagnose(
        "DS-03",
        telemetry={"pulses_emitted": 0, "pulse_freq_hz": 0},
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    )
    muc = ErrorLedger(tmp_path / "error_ledger.jsonl").entries()
    assert muc and "DS-03" in muc[0].description


def test_quay_nguoc_chieu_la_loi_NOI_DAY(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": True, "dung_chieu": False, "du_mot_vong": False},
    )
    assert ket_luan.verdict == Verdict.WIRING
    assert not ket_luan.opens_repair_loop
    assert "DIR" in ket_luan.action


def test_quay_giat_truot_buoc_la_loi_CO_KHI(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": True, "dung_chieu": True, "du_mot_vong": False},
    )
    assert ket_luan.verdict == Verdict.MECHANICAL
    assert not ket_luan.opens_repair_loop


def test_ca_hai_kenh_deu_dat_thi_khong_phat_hien_loi(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": True, "dung_chieu": True, "du_mot_vong": True},
    )
    assert ket_luan.verdict == Verdict.OK
    assert not ket_luan.opens_repair_loop


# --------------------------------------------------------------------------
# Từ chối kết luận khi thiếu một kênh
# --------------------------------------------------------------------------


def test_thieu_quan_sat_cua_nguoi_thi_KHONG_ket_luan(phien: DiagnosticSession) -> None:
    """Kết luận trên nửa dữ liệu vẫn nghe chắc chắn y hệt — và dẫn đi sửa nhầm."""
    ket_luan = phien.diagnose("DS-03", telemetry=TELEMETRY_XUNG_DU)

    assert ket_luan.verdict == Verdict.INCONCLUSIVE
    assert not ket_luan.opens_repair_loop
    assert "truc_quay" in ket_luan.action
    assert "phép GIAO của hai kênh" in ket_luan.action


def test_thieu_MOT_muc_quan_sat_cung_khong_ket_luan(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": True, "dung_chieu": True},
    )
    assert ket_luan.verdict == Verdict.INCONCLUSIVE
    assert "du_mot_vong" in ket_luan.action


def test_kich_ban_tu_dong_hoan_toan_ket_luan_duoc_ngay(phien: DiagnosticSession) -> None:
    """DS-01 không cần người — máy kết luận được một mình."""
    ket_luan = phien.diagnose("DS-01", telemetry={"i2c_addresses": ["0x68", "0x76"]})
    assert ket_luan.verdict == Verdict.OK

    hong = phien.diagnose("DS-01", telemetry={"i2c_addresses": ["0x76"]})
    assert hong.verdict == Verdict.CODE
    assert hong.opens_repair_loop


def test_to_hop_chua_co_trong_ma_tran_thi_de_nghi_bo_sung(
    phien: DiagnosticSession,
) -> None:
    """Phiên chẩn đoán cũng là phiên nạp tri thức."""
    ket_luan = phien.diagnose(
        "DS-02",
        telemetry={
            "who_am_i": "0x68",
            "accel_noise_mg": 10,
            "gyro_noise_dps": 0.5,
            "samples": 100,
        },
        human_answers={"nghieng_trai_gia_tri_am": False, "truc_dung_chieu": True},
    )
    assert ket_luan.verdict == Verdict.INCONCLUSIVE
    assert "Bổ sung một dòng vào ma trận" in ket_luan.action


# --------------------------------------------------------------------------
# Đọc telemetry
# --------------------------------------------------------------------------


def test_doc_telemetry_json_tung_dong() -> None:
    du_lieu = DiagnosticSession.parse_telemetry(
        '{"who_am_i": "0x68"}\n{"samples": 100}\n{"accel_noise_mg": 12}\n'
    )
    assert du_lieu == {"who_am_i": "0x68", "samples": 100, "accel_noise_mg": 12}


def test_dong_rac_bi_bo_qua_nhung_duoc_DEM() -> None:
    """Mất cả phiên đo vì một dòng nhiễu là cái giá quá đắt — nhưng không im lặng."""
    du_lieu = DiagnosticSession.parse_telemetry(
        "rác khởi động\x00\n{\"samples\": 100}\n{hỏng\n{\"who_am_i\": \"0x68\"}\n"
    )
    assert du_lieu["samples"] == 100
    assert du_lieu["who_am_i"] == "0x68"
    assert du_lieu["_malformed_lines"] == 1


def test_chan_doan_nhan_ca_chuoi_lan_dict(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-01", telemetry='{"i2c_addresses": ["0x68"]}\n'
    )
    assert ket_luan.verdict == Verdict.OK


# --------------------------------------------------------------------------
# Tiêu chí kênh máy
# --------------------------------------------------------------------------


def test_thieu_truong_telemetry_la_khong_dat(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose("DS-01", telemetry={})
    assert not ket_luan.machine_passed
    assert any("không có trường" in b for b in ket_luan.machine_evidence)


def test_bang_chung_kenh_may_neu_ro_tung_tieu_chi(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-06", telemetry={"isr_period_ms": 10.05, "jitter_us": 180}
    )
    assert ket_luan.verdict == Verdict.OK
    assert len(ket_luan.machine_evidence) == 2
    assert all(b.startswith("✓") for b in ket_luan.machine_evidence)


def test_chu_ky_ngat_lech_nguong_bi_bat(phien: DiagnosticSession) -> None:
    ket_luan = phien.diagnose(
        "DS-06", telemetry={"isr_period_ms": 12.4, "jitter_us": 180}
    )
    assert ket_luan.verdict == Verdict.CODE
    assert any("✗" in b and "isr_period_ms" in b for b in ket_luan.machine_evidence)


# --------------------------------------------------------------------------
# Ghi kết quả
# --------------------------------------------------------------------------


def test_ket_luan_ghi_vao_measurement_records(
    phien: DiagnosticSession, tmp_path: Path
) -> None:
    phien.diagnose("DS-01", telemetry={"i2c_addresses": ["0x68"]})

    dong = (tmp_path / "measurements.jsonl").read_text(encoding="utf-8").strip()
    ban_ghi = json.loads(dong)
    assert ban_ghi["scenario"] == "DS-01"
    assert ban_ghi["verdict"] == Verdict.OK
    assert ban_ghi["at"]


def test_bao_cao_ket_luan_doc_duoc(phien: DiagnosticSession) -> None:
    van_ban = phien.diagnose(
        "DS-03",
        telemetry=TELEMETRY_XUNG_DU,
        human_answers={"truc_quay": False, "dung_chieu": False, "du_mot_vong": False},
    ).render()

    assert "Kênh máy: ĐẠT" in van_ban
    assert "Kênh người:" in van_ban
    assert "truc_quay: không" in van_ban
    assert "Hành động đề xuất:" in van_ban


def test_kich_ban_khong_ton_tai_bao_loi(phien: DiagnosticSession) -> None:
    with pytest.raises(DiagnosticError, match="Không có kịch bản"):
        phien.diagnose("DS-99", telemetry={})
