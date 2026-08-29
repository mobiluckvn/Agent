"""TC-49 — khởi tạo dự án bằng hội thoại (N-001..N-006).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-49a | Dò TRƯỚC khi hỏi | thứ máy tự biết được thì không hỏi lại |
| TC-49b | Không chắc thì không chọn hộ | nhiều ứng viên bo → dừng, đòi người chỉ rõ |
| TC-49c | Chỉ hỏi phần máy không biết | chu kỳ điều khiển, chế độ an toàn — không suy được từ dấu hiệu nào |
| TC-49d | Ba loại dữ kiện không trộn | đã kiểm / người nói / tra cứu; chưa kiểm thì xuống `assumptions` |
| TC-49e | Không ghi đè hồ sơ đã có | bản cũ có thể đã qua G1 và mã đang dựa vào |

Vì sao nhóm này tồn tại: trước nó, ``eaa init`` đòi ``constraints.yaml`` và
``hardware_profile.yaml`` ĐÃ CÓ SẴN mà không lệnh nào giúp tạo ra chúng. Người
dùng phải hiểu kiến trúc bên trong mới bắt đầu được — rào cản ở đúng bước đầu.
Trong chính phiên làm việc dựng ra tính năng này, hai tệp ấy cho bo STM32 là do
người viết tay, và đó là bằng chứng rõ nhất rằng khoảng trống có thật.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from eaa.brief import (
    QUESTIONS,
    BoardCandidate,
    BriefError,
    ProbedDevice,
    ProbeResult,
    ProjectDraft,
    identify_board,
    probe_hardware,
    remaining_questions,
)

REPO = Path(__file__).resolve().parent.parent


def _bo(**kw) -> BoardCandidate:
    kw.setdefault("name", "Bo thử")
    kw.setdefault("mcu", "chip-thu")
    kw.setdefault("platform", "avr")
    return BoardCandidate(**kw)


def _do_duoc(*thiet_bi: ProbedDevice) -> ProbeResult:
    return ProbeResult(devices=list(thiet_bi))


# --------------------------------------------------------------------------
# TC-49a — dò trước khi hỏi
# --------------------------------------------------------------------------


def test_do_duoc_thi_khong_hoi_lai(monkeypatch) -> None:
    """Mỗi câu hỏi tiết kiệm được là một câu người không phải trả lời."""
    from eaa.serialport import SerialPort

    monkeypatch.setattr(
        "eaa.serialport.list_ports",
        lambda **_: [SerialPort(device="/dev/ttyUSB0", vid="1a86", pid="7523", source="pyserial")],
    )
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: [])

    ket_qua = probe_hardware()
    assert len(ket_qua.devices) == 1
    assert ket_qua.devices[0].vid == "1a86"
    assert ket_qua.devices[0].identifiable


def test_noi_ro_dieu_may_KHONG_biet(monkeypatch) -> None:
    """Im lặng về giới hạn của mình là để người tưởng máy đã kiểm hết."""
    monkeypatch.setattr("eaa.serialport.pyserial_available", lambda: False)
    monkeypatch.setattr("eaa.serialport.list_ports", lambda **_: [])
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: [])

    ket_qua = probe_hardware()
    assert any("pyserial" in t for t in ket_qua.limits)
    assert "KHÔNG tự biết được" in ket_qua.render()


def test_thay_o_nap_tha_tep(monkeypatch) -> None:
    monkeypatch.setattr("eaa.serialport.list_ports", lambda **_: [])
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: ["/Volumes/BO_NAP"])

    ket_qua = probe_hardware()
    assert ket_qua.devices[0].volume_label == "BO_NAP"
    assert ket_qua.devices[0].identifiable


def test_khong_thay_gi_thi_goi_y_viec_can_lam(monkeypatch) -> None:
    monkeypatch.setattr("eaa.serialport.list_ports", lambda **_: [])
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: [])

    van_ban = probe_hardware().render()
    assert "đã cắm và đã cấp nguồn" in van_ban


# --------------------------------------------------------------------------
# TC-49b — không chắc thì không chọn hộ
# --------------------------------------------------------------------------


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def _json_bo(*ung_vien: dict) -> str:
    return "```json\n" + json.dumps({"candidates": list(ung_vien)}) + "\n```"


def test_nhan_dang_tra_ve_ung_vien_kem_cach_phan_biet() -> None:
    llm = _LlmGia(
        _json_bo(
            {"name": "Bo A", "mcu": "chip-a", "platform": "avr", "confidence": "medium",
             "how_to_tell": "đọc mã in trên chip"},
            {"name": "Bo B", "mcu": "chip-b", "platform": "avr", "confidence": "low",
             "how_to_tell": "xem nhãn dán mặt sau"},
        )
    )
    ung_vien = identify_board(
        _do_duoc(ProbedDevice(port="/dev/ttyUSB0", vid="1a86", pid="7523")), llm
    )

    assert len(ung_vien) == 2
    assert all(c.how_to_tell for c in ung_vien), (
        "danh sách không có cách phân biệt thì người cũng chọn bừa như máy"
    )


def test_khong_co_dau_hieu_thi_khong_goi_mo_hinh() -> None:
    """Không dò được gì thì hỏi mô hình cũng chỉ nhận về phỏng đoán."""
    llm = _LlmGia(_json_bo({"name": "Bo A", "confidence": "high"}))
    assert identify_board(_do_duoc(ProbedDevice(port="/dev/cu.BLTH")), llm) == []
    assert llm.prompts == []


def test_khong_co_mo_hinh_thi_tra_rong() -> None:
    ket_qua = identify_board(_do_duoc(ProbedDevice(vid="1a86", pid="7523")), None)
    assert ket_qua == []


def test_prompt_cam_bia_dung_luong_bo_nho() -> None:
    llm = _LlmGia(_json_bo({"name": "Bo A", "confidence": "high"}))
    identify_board(_do_duoc(ProbedDevice(vid="1a86", pid="7523")), llm)

    van_ban = llm.prompts[0].full_text()
    assert "Không bịa dung lượng bộ nhớ" in van_ban
    assert "BẮT BUỘC kèm cách phân biệt" in van_ban


def test_ung_vien_thieu_ten_bi_tu_choi() -> None:
    llm = _LlmGia(_json_bo({"mcu": "chip-a"}))
    with pytest.raises(BriefError, match="thiếu 'name'"):
        identify_board(_do_duoc(ProbedDevice(vid="1a86", pid="7523")), llm)


# --------------------------------------------------------------------------
# TC-49c — chỉ hỏi phần máy không biết
# --------------------------------------------------------------------------


def test_cau_hoi_bat_buoc_deu_la_thu_khong_suy_duoc() -> None:
    """Chu kỳ điều khiển và chế độ an toàn không có dấu hiệu vật lý nào cho ra."""
    bat_buoc = {q.key for q in QUESTIONS if q.required}
    assert {"muc_tieu", "doi_tuong", "chu_ky_ms", "an_toan"} <= bat_buoc


def test_moi_cau_hoi_deu_noi_VI_SAO_hoi() -> None:
    """Câu hỏi không nói vì sao thì người trả lời qua loa."""
    for q in QUESTIONS:
        assert q.why.strip(), q.key
        assert q.prompt.strip().endswith("?"), q.key


def test_da_tra_loi_thi_khong_hoi_lai() -> None:
    con_lai = remaining_questions({"muc_tieu": "giữ thăng bằng", "chu_ky_ms": 10})
    khoa = {q.key for q in con_lai}

    assert "muc_tieu" not in khoa and "chu_ky_ms" not in khoa
    assert "an_toan" in khoa


def test_tra_loi_rong_khong_tinh_la_da_tra_loi() -> None:
    con_lai = remaining_questions({"muc_tieu": "   "})
    assert "muc_tieu" in {q.key for q in con_lai}


# --------------------------------------------------------------------------
# TC-49d — ba loại dữ kiện không trộn
# --------------------------------------------------------------------------


def _ban_nhap(tmp_path: Path, **kw) -> ProjectDraft:
    kw.setdefault("board", _bo(clock_hz=16_000_000))
    kw.setdefault("answers", {"chu_ky_ms": 10})
    kw.setdefault(
        "probe",
        _do_duoc(
            ProbedDevice(port="/dev/cu.usbserial-1", vid="1a86", pid="7523",
                         description="cầu USB rời"),
            ProbedDevice(volume="/Volumes/BO_NAP", volume_label="BO_NAP"),
        ),
    )
    return ProjectDraft(project_dir=tmp_path / "du_an", **kw)


def test_dieu_DA_KIEM_ghi_thang_vao_ho_so(tmp_path: Path) -> None:
    du_lieu = yaml.safe_load(_ban_nhap(tmp_path).hardware_profile())
    usb = du_lieu["programmer"]["usb"]

    assert usb[0]["vid"] == "1a86" and usb[0]["pid"] == "7523"
    assert du_lieu["programmer"]["mass_storage"] == "/Volumes/BO_NAP"


def test_goi_y_ten_cong_lay_tu_cong_do_duoc(tmp_path: Path) -> None:
    """Không đoán tên cổng — rút từ chính cổng máy vừa thấy."""
    du_lieu = yaml.safe_load(_ban_nhap(tmp_path).hardware_profile())
    assert du_lieu["programmer"]["port_hint"] == "usbserial"


def test_dieu_CHUA_KIEM_xuong_muc_gia_dinh(tmp_path: Path) -> None:
    """Sáu tháng sau không ai nhớ con số nào đo được, con số nào đoán ra."""
    ban = _ban_nhap(tmp_path)
    ban.gia_dinh("so_do_chan", "Sơ đồ chân chưa nạp", "Đọc sơ đồ nguyên lý", ["mọi module"])

    du_lieu = yaml.safe_load(ban.hardware_profile())
    (gd,) = du_lieu["assumptions"]

    assert gd["status"] == "proposed"
    assert gd["how_to_verify"]
    assert gd["blocks"] == ["mọi module"]


def test_ho_so_noi_ro_ba_loai_du_kien(tmp_path: Path) -> None:
    van_ban = _ban_nhap(tmp_path).hardware_profile()
    assert "ĐÃ KIỂM" in van_ban and "TRA CỨU" in van_ban and "CHƯA KIỂM" in van_ban


def test_rang_buoc_ghi_ro_la_ban_nhap(tmp_path: Path) -> None:
    van_ban = _ban_nhap(tmp_path).constraints()
    assert "BẢN NHÁP" in van_ban
    assert "CHƯA PHẢI QUYẾT ĐỊNH" in van_ban
    assert "duyệt tại G1" in van_ban


def test_khong_doan_tieu_chi_nghiem_thu(tmp_path: Path) -> None:
    """Tiêu chí phải đo được và phải do người chốt TRƯỚC khi có số đo."""
    du_lieu = yaml.safe_load(_ban_nhap(tmp_path).constraints())
    assert du_lieu["acceptance"]["measurements"] == []
    assert du_lieu["acceptance"]["scenarios"] == []


def test_chu_ky_nguoi_tra_loi_di_vao_rang_buoc(tmp_path: Path) -> None:
    du_lieu = yaml.safe_load(_ban_nhap(tmp_path, answers={"chu_ky_ms": 25}).constraints())
    assert du_lieu["limits"]["control_loop_ms"] == 25


def test_chua_chon_bo_thi_khong_dung_duoc_ho_so(tmp_path: Path) -> None:
    ban = ProjectDraft(project_dir=tmp_path / "du_an", board=None)
    with pytest.raises(BriefError, match="Chưa chọn bo"):
        ban.constraints()


def test_ho_so_sinh_ra_nap_lai_duoc(tmp_path: Path) -> None:
    """Vòng khép kín: thứ brief ghi ra phải là thứ eaa init đọc được."""
    from eaa.kb import Constraints, HardwareProfile

    da_ghi = _ban_nhap(tmp_path).write()
    assert len(da_ghi) == 2

    rang_buoc = Constraints.load(tmp_path / "du_an" / "constraints.yaml")
    ho_so = HardwareProfile.load(tmp_path / "du_an" / "hardware_profile.yaml")

    assert rang_buoc.platform == "avr"
    assert rang_buoc.limits["control_loop_ms"] == 10
    assert ho_so.raw["programmer"]["usb"]


# --------------------------------------------------------------------------
# TC-49e — không ghi đè hồ sơ đã có
# --------------------------------------------------------------------------


def test_khong_ghi_de_ho_so_da_co(tmp_path: Path) -> None:
    """Bản cũ có thể đã qua G1 và mã sinh ra đang dựa vào nó."""
    ban = _ban_nhap(tmp_path)
    ban.write()

    with pytest.raises(BriefError, match="KHÔNG ghi đè"):
        ban.write()


def test_thong_bao_ghi_de_noi_ro_phai_lam_gi(tmp_path: Path) -> None:
    ban = _ban_nhap(tmp_path)
    ban.write()

    with pytest.raises(BriefError) as loi:
        ban.write()
    assert "tự xóa nếu thật sự muốn" in str(loi.value)


# --------------------------------------------------------------------------
# Nối vào CLI
# --------------------------------------------------------------------------


def test_lenh_brief_chay_truoc_init(tmp_path: Path, monkeypatch, capsys) -> None:
    """brief là thứ TẠO RA dự án, nên nó không đòi dự án phải tồn tại trước."""
    from eaa import EXIT_OK, EXIT_WAITING_GATE
    from eaa.cli import main
    from eaa.serialport import SerialPort

    du_an = tmp_path / "du_an_moi"
    monkeypatch.setenv("EAA_PROJECT", str(du_an))
    monkeypatch.setenv("EAA_HOME", str(REPO))
    monkeypatch.setattr(
        "eaa.serialport.list_ports",
        lambda **_: [SerialPort(device="/dev/cu.usbserial-1", vid="1a86", pid="7523",
                                source="pyserial")],
    )
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: [])

    tra_loi = tmp_path / "tra_loi.yaml"
    tra_loi.write_text(
        yaml.safe_dump(
            {"muc_tieu": "x", "doi_tuong": "y", "chu_ky_ms": 10, "an_toan": "z"},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    ma = main(["brief", "--board", "Bo thử", "--platform", "avr",
               "--answers", str(tra_loi)])
    capsys.readouterr()

    assert ma == EXIT_WAITING_GATE, "bản nháp phải chờ người duyệt"
    assert (du_an / "constraints.yaml").is_file()
    assert (du_an / "hardware_profile.yaml").is_file()

    # Và eaa init phải chạy được trên chính hồ sơ vừa dựng.
    assert main(["init"]) == EXIT_OK


def test_thieu_cau_tra_loi_bat_buoc_thi_dung_va_hoi(tmp_path: Path, monkeypatch, capsys) -> None:
    from eaa import EXIT_WAITING_GATE
    from eaa.cli import main

    du_an = tmp_path / "du_an_moi"
    monkeypatch.setenv("EAA_PROJECT", str(du_an))
    monkeypatch.setattr("eaa.serialport.list_ports", lambda **_: [])
    monkeypatch.setattr("eaa.brief._o_dia_roi", lambda: [])

    assert main(["brief", "--board", "Bo thử", "--platform", "avr"]) == EXIT_WAITING_GATE
    ra = capsys.readouterr().out

    assert "Agent KHÔNG tự trả lời hộ" in ra
    assert "chu_ky_ms" in ra
    assert not (du_an / "constraints.yaml").exists(), "thiếu câu trả lời thì không ghi gì"
