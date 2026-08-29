"""TC-47 — pack thứ hai, và những gì phần cứng thật làm lộ ra.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-47a | NFR-05: thêm họ MCU không sửa engine | pack STM32 không thêm nhánh rẽ nào trong `eaa/` |
| TC-47b | Khác biệt nền tảng đi qua INTERFACE | đuôi ảnh nạp và nguồn do pack cấp là tham số, không phải `if pack.name` |
| TC-47c | Agent tự cấu hình mô hình | thấy khóa thì chọn mô hình thật, không bắt người biết nội tình engine |
| TC-47d | Khớp cổng theo TÊN không đủ để tự chọn | cắm hai bo thì một gợi ý tên có thể trúng nhầm bo |

TC-47d đến từ một lỗi có thật, tìm được trong đúng năm phút đầu tiên có hai bo
cùng cắm: dự án AVR khớp trúng cổng ST-LINK của bo STM32, vì gợi ý tên
``usbmodem`` đúng với cả hai. Engine khi ấy TỰ CHỌN cổng ấy — tức là sẵn sàng
nạp firmware AVR vào một bo ARM. Không lượng test giả lập nào tìm ra được điều
đó, vì nó chỉ tồn tại khi có hai thiết bị thật trên bàn.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from eaa.platform import CAPABILITIES, discover_packs, load_manifest
from eaa.serialport import SerialPort, UsbId, match_declared

REPO = Path(__file__).resolve().parent.parent
PACK_AVR = REPO / "packs" / "avr"
PACK_STM32 = REPO / "packs" / "stm32"


# --------------------------------------------------------------------------
# TC-47a — thêm họ MCU không sửa engine
# --------------------------------------------------------------------------


def test_co_dung_hai_pack() -> None:
    ten = set(discover_packs(REPO / "packs"))
    assert {"avr", "stm32"} <= ten


def test_engine_khong_biet_ten_pack_nao() -> None:
    """NFR-05 đo được: engine không chứa một nhánh rẽ theo tên pack nào.

    Đây là phép kiểm mà một pack duy nhất KHÔNG làm được — với một pack, "engine
    tổng quát" và "engine viết riêng cho pack ấy" trông giống hệt nhau.
    """
    vi_pham = []
    for tep in sorted((REPO / "eaa").rglob("*.py")):
        van_ban = tep.read_text(encoding="utf-8")
        for so, dong in enumerate(van_ban.splitlines(), 1):
            if re.search(r"pack(_name|\.name)?\s*==\s*['\"]", dong):
                vi_pham.append(f"{tep.relative_to(REPO)}:{so}: {dong.strip()}")
            if re.search(r"\bif\s+.*\b(avr|stm32)\b.*:", dong, re.IGNORECASE):
                vi_pham.append(f"{tep.relative_to(REPO)}:{so}: {dong.strip()}")
    assert not vi_pham, "engine rẽ nhánh theo nền tảng:\n" + "\n".join(vi_pham)


def test_hai_pack_dung_chung_bo_nang_luc() -> None:
    """Cùng một interface, hai hiện thực — không pack nào tự thêm năng lực lạ."""
    for goc in (PACK_AVR, PACK_STM32):
        pack = load_manifest(goc)
        assert set(pack.capabilities) <= set(CAPABILITIES), pack.name


def test_hai_pack_goi_hai_bo_cong_cu_khac_han() -> None:
    avr = load_manifest(PACK_AVR)
    stm32 = load_manifest(PACK_STM32)

    cc_avr = {avr.invocation(c).command[0] for c in avr.capabilities}
    cc_stm32 = {stm32.invocation(c).command[0] for c in stm32.capabilities}

    assert "avr-gcc" in cc_avr and "arm-none-eabi-gcc" in cc_stm32
    # Chỉ bộ phân tích tĩnh dùng chung; phần còn lại khác hoàn toàn.
    assert cc_avr & cc_stm32 == {"cppcheck"}


def test_nhu_cau_cong_cu_suy_tu_pack_moi() -> None:
    """Không ai chép tay danh sách công cụ ARM — nó suy ra từ pack.yaml."""
    from eaa.toolsearch import derive_requirements

    can = {r.program for r in derive_requirements(load_manifest(PACK_STM32))}
    assert {"arm-none-eabi-gcc", "arm-none-eabi-objcopy", "st-flash"} <= can

    gcc = next(
        r for r in derive_requirements(load_manifest(PACK_STM32))
        if r.program == "arm-none-eabi-gcc"
    )
    assert gcc.capabilities == ("compile", "link"), "một công cụ phục vụ hai năng lực"


def test_pack_stm32_khai_can_xac_nhan_khi_nap() -> None:
    assert load_manifest(PACK_STM32).invocation("flash").requires_confirmation


# --------------------------------------------------------------------------
# TC-47b — khác biệt nền tảng đi qua interface
# --------------------------------------------------------------------------


def test_duoi_anh_nap_la_tham_so_cua_pack() -> None:
    """Pack đầu dùng Intel HEX, pack thứ hai dùng ảnh nhị phân thô.

    Khác biệt này từng là hằng số trong engine. Pack thứ hai làm nó lộ ra, và
    câu trả lời đúng là thêm một tham số vào interface — không phải thêm một
    nhánh rẽ vào engine.
    """
    assert load_manifest(PACK_AVR).firmware.image_suffix == ".hex"
    assert load_manifest(PACK_STM32).firmware.image_suffix == ".bin"


def test_nguon_do_pack_cap_la_tham_so_cua_pack() -> None:
    """ARM bare-metal cần mã khởi động và bảng vector; AVR thì bộ dịch kèm sẵn."""
    assert load_manifest(PACK_AVR).firmware.sources == ()

    nguon = load_manifest(PACK_STM32).firmware.sources
    assert nguon, "pack STM32 phải cấp mã khởi động"
    for tep in nguon:
        assert Path(tep).is_file(), tep


def test_kich_ban_lien_ket_nam_o_pack() -> None:
    """Bản đồ bộ nhớ là thuộc tính của con chip, không phải của dự án."""
    kich_ban = list((PACK_STM32 / "templates").glob("*.ld"))
    assert kich_ban, "pack STM32 phải có kịch bản liên kết"

    noi_dung = kich_ban[0].read_text(encoding="utf-8")
    assert "FLASH" in noi_dung and "RAM" in noi_dung
    assert "_estack" in noi_dung, "phải định nghĩa đỉnh ngăn xếp cho mã khởi động"


def test_hai_pack_dung_chung_hop_dong_khuon() -> None:
    """Khuôn khác nhau hoàn toàn về nội dung, nhưng cùng chỗ giữ."""
    for goc in (PACK_AVR, PACK_STM32):
        pack = load_manifest(goc)
        khuon = pack.firmware.template.read_text(encoding="utf-8")
        for cho_giu in ("{includes}", "{init_calls}", "{tasks}"):
            assert cho_giu in khuon, f"{pack.name} thiếu {cho_giu}"

        do = pack.diagnostics.template.read_text(encoding="utf-8")
        assert "void diag_run(void);" in do, f"{pack.name}: hợp đồng phần đo"


def test_hai_khuon_dung_hai_nguon_nhip_khac_nhau() -> None:
    """Cùng một bộ định thời hợp tác, hai cách lấy nhịp — chỉ pack mới biết."""
    avr = load_manifest(PACK_AVR).firmware.template.read_text(encoding="utf-8")
    stm32 = load_manifest(PACK_STM32).firmware.template.read_text(encoding="utf-8")

    assert "ISR(" in avr and "ATOMIC_BLOCK" in avr
    assert "SysTick_Handler" in stm32 and "E000E010" in stm32
    assert "ATOMIC_BLOCK" not in stm32, "lõi 32 bit đọc bộ đếm nguyên tử sẵn"


def test_moi_pack_co_bo_quy_tac_tinh_rieng() -> None:
    """Dự án khai Ý ĐỊNH (`delay()`); cách phát hiện trên từng nền tảng do pack lo."""
    import yaml

    ten_quy_tac = {}
    for goc in (PACK_AVR, PACK_STM32):
        du_lieu = yaml.safe_load((goc / "rules" / "forbidden.yaml").read_text(encoding="utf-8"))
        ten_quy_tac[goc.name] = {r["id"] for r in du_lieu["rules"]}

    chung = ten_quy_tac["avr"] & ten_quy_tac["stm32"]
    assert "delay()" in chung and "blocking_io" in chung, (
        "tên quy tắc phải trùng nhau để constraints.yaml không phải viết lại khi đổi pack"
    )


# --------------------------------------------------------------------------
# TC-47c — Agent tự cấu hình mô hình
# --------------------------------------------------------------------------


def test_thay_khoa_thi_chon_mo_hinh_that(monkeypatch: pytest.MonkeyPatch) -> None:
    """Người dùng không có nghĩa vụ biết trường llm.provider tên là gì."""
    from eaa.cli import chon_llm_theo_moi_truong
    from eaa.llm.base import KEY_ENV

    monkeypatch.setenv(KEY_ENV, "khoa-gia-de-thu")
    provider, model, ly_do = chon_llm_theo_moi_truong()

    assert provider == "gemini"
    assert model
    assert KEY_ENV in ly_do, "phải NÓI RA vì sao đã chọn"


def test_khong_co_khoa_thi_dung_gia_lap(monkeypatch: pytest.MonkeyPatch) -> None:
    from eaa.cli import chon_llm_theo_moi_truong
    from eaa.llm.base import KEY_ENV

    monkeypatch.delenv(KEY_ENV, raising=False)
    provider, _, ly_do = chon_llm_theo_moi_truong()

    assert provider == "mock"
    assert "eaa init --force" in ly_do, "lý do phải kèm LỆNH GÕ ĐƯỢC"


def test_khong_bao_gio_lo_gia_tri_khoa(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-06: chỉ hỏi khóa CÓ tồn tại không, không đọc giá trị."""
    from eaa.cli import chon_llm_theo_moi_truong
    from eaa.llm.base import KEY_ENV

    monkeypatch.setenv(KEY_ENV, "AIza-bi-mat-tuyet-doi")
    _, _, ly_do = chon_llm_theo_moi_truong()

    assert "bi-mat" not in ly_do


def test_canh_bao_khi_state_va_moi_truong_lech(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from eaa.cli import canh_bao_lech_cau_hinh
    from eaa.llm.base import KEY_ENV

    gia_lap = SimpleNamespace(llm={"provider": "mock", "model": "x"})
    that = SimpleNamespace(llm={"provider": "gemini", "model": "y"})

    monkeypatch.setenv(KEY_ENV, "co-khoa")
    assert "eaa init --force" in canh_bao_lech_cau_hinh(gia_lap)
    assert canh_bao_lech_cau_hinh(that) == ""

    monkeypatch.delenv(KEY_ENV, raising=False)
    assert canh_bao_lech_cau_hinh(gia_lap) == ""
    assert KEY_ENV in canh_bao_lech_cau_hinh(that)


def test_thong_bao_thieu_bo_tra_cuu_la_lenh_go_duoc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thông báo cũ mô tả nội tình engine; người dùng không đọc được nó."""
    from eaa.doctor import Doctor, DoctorError, EnvLock, ToolManifest
    from eaa.llm.base import KEY_ENV
    from eaa.toolsearch import ToolRequirement

    doctor = Doctor(
        manifest=ToolManifest(specs=()),
        tools_kb=Path("/tmp/khong-dung"),
        env_lock=EnvLock(Path("/tmp/khong-dung/env.json")),
    )
    yc = ToolRequirement(program="x", capabilities=("compile",))

    monkeypatch.setenv(KEY_ENV, "co-khoa")
    with pytest.raises(DoctorError, match="eaa init --force"):
        doctor.research(yc)

    monkeypatch.delenv(KEY_ENV, raising=False)
    with pytest.raises(DoctorError, match=r"\.env"):
        doctor.research(yc)


# --------------------------------------------------------------------------
# TC-47d — khớp theo tên cổng không đủ để tự chọn
# --------------------------------------------------------------------------


def test_khop_theo_ten_khong_duoc_danh_dau_la_da_xac_nhan() -> None:
    cong = [SerialPort(device="/dev/cu.usbmodem1434103")]
    ket_qua = match_declared(cong, [], port_hint="usbmodem")

    assert ket_qua[0].matched
    assert not ket_qua[0].match_confirmed


def test_khop_theo_vid_pid_duoc_danh_dau_da_xac_nhan() -> None:
    cong = [SerialPort(device="/dev/ttyUSB0", vid="1a86", pid="7523", source="pyserial")]
    ket_qua = match_declared(cong, [UsbId(vid="1a86", pid="7523", note="Bo AVR")])

    assert ket_qua[0].match_confirmed


def test_khop_theo_ten_thi_KHONG_tu_chon_cong(tmp_path: Path, monkeypatch) -> None:
    """Lỗi có thật: hai bo cắm cùng lúc, gợi ý tên trúng nhầm bo.

    Engine khi ấy sẵn sàng nạp firmware của nền tảng này vào bo của nền tảng
    kia. Nạp nhầm thiết bị là hỏng thật, không phải một lượt chạy lại.
    """
    from eaa.cli import CliError, _chon_cong

    monkeypatch.setattr(
        "eaa.serialport.list_ports",
        lambda **_: [SerialPort(device="/dev/cu.usbmodem1434103")],
    )

    class _HoSo:
        raw = {"programmer": {"usb": [{"vid": "1a86", "pid": "7523"}], "port_hint": "usbmodem"}}

    with pytest.raises(CliError, match="chưa xác nhận được VID/PID"):
        _chon_cong(tmp_path, _HoSo(), "")


def test_khop_theo_vid_pid_thi_tu_chon_duoc(tmp_path: Path, monkeypatch, capsys) -> None:
    from eaa.cli import _chon_cong

    monkeypatch.setattr(
        "eaa.serialport.list_ports",
        lambda **_: [
            SerialPort(device="/dev/cu.usbserial-1", vid="1a86", pid="7523", source="pyserial"),
            SerialPort(device="/dev/cu.usbmodem-2", vid="0483", pid="374b", source="pyserial"),
        ],
    )

    class _HoSo:
        raw = {"programmer": {"usb": [{"vid": "1a86", "pid": "7523"}]}}

    assert _chon_cong(tmp_path, _HoSo(), "") == "/dev/cu.usbserial-1"


def test_hai_du_an_khai_hai_bo_khac_nhau() -> None:
    """Hai bo thật trên bàn: mỗi dự án phải nhận ra đúng bo của mình."""
    from eaa.kb import HardwareProfile
    from eaa.serialport import declared_usb_ids

    avr, goi_y_avr = declared_usb_ids(
        HardwareProfile.load(REPO / "projects" / "robot_balance" / "hardware_profile.yaml")
    )
    stm32, goi_y_stm32 = declared_usb_ids(
        HardwareProfile.load(REPO / "projects" / "disco_f469" / "hardware_profile.yaml")
    )

    ma_avr = {(u.vid.lower(), u.pid.lower()) for u in avr}
    ma_stm32 = {(u.vid.lower(), u.pid.lower()) for u in stm32}

    assert not ma_avr & ma_stm32, "hai bo không được khai trùng mã"
    assert goi_y_avr != goi_y_stm32, "gợi ý tên cổng cũng phải phân biệt được"
