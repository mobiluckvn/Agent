"""TC-69 — cài hỏng thì làm gì: phân loại đúng, leo thang đúng, dừng đúng chỗ.

Ba bất biến:

* **Chỉ lỗi mạng mới đáng thử lại.** Thử lại một lỗi quyền là đốt thời gian
  của người dùng, và làm thế mãi thì thông báo cuối cùng cũng vẫn là lỗi ấy.
* **Thang gỡ luôn dừng ở con người.** Không bậc nào cho Agent tự chạy lệnh cài.
* **Lệnh quay lui suy ra, không đoán.** Không suy được thì trả rỗng — một lệnh
  gỡ đoán sai chạy với quyền quản trị tệ hơn hẳn không có lệnh gỡ nào.
"""

from __future__ import annotations

import pytest

from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA
from eaa.installerr import (
    BUILD,
    KHAC,
    KHONG_TIM_THAY,
    MANG,
    PHU_THUOC,
    QUYEN,
    SO_LAN_THU_LAI,
    classify,
    remedies,
    retry_delays,
    rollback_command,
)


# ------------------------------------------------------------ phân loại ---


@pytest.mark.parametrize("van_ban,loai", [
    ("E: Could not resolve host: archive.ubuntu.com", MANG),
    ("curl: (7) Failed to connect: Connection timed out", MANG),
    ("npm ERR! network ETIMEDOUT", MANG),
    ("Error: HTTP 503 from registry", MANG),

    ("mkdir: /usr/local/bin: Permission denied", QUYEN),
    ("Error: Operation not permitted", QUYEN),
    ("npm ERR! Error: EACCES: permission denied", QUYEN),
    ("This command must be run as root", QUYEN),

    ("E: Unable to locate package gcc-avr", KHONG_TIM_THAY),
    ("Error: No formulae found in taps.", KHONG_TIM_THAY),
    ("ERROR: Could not find a version that satisfies the requirement foo", KHONG_TIM_THAY),
    ("bash: avr-gcc: command not found", KHONG_TIM_THAY),

    ("The following packages have unmet dependencies:", PHU_THUOC),
    ("ERROR: pip's dependency resolver: version conflict", PHU_THUOC),
    ("error while loading shared libraries: libusb.so.1: cannot open shared object file", PHU_THUOC),

    ("fatal error: Python.h: No such file or directory", BUILD),
    ("ERROR: Failed building wheel for pyserial", BUILD),
    ("make: *** [all] Error 2", BUILD),
])
def test_nhan_dung_loai(van_ban, loai):
    assert classify(van_ban).kind == loai


def test_khong_khop_mau_nao_thi_la_loai_khac_chu_khong_doan_bua():
    chan = classify("Something inexplicable happened in module 7")
    assert chan.kind == KHAC
    assert chan.confidence_level == KHONG_KIEM_DUOC


def test_nhan_ra_duoc_thi_suy_ra_khong_bao_gio_da_kiem():
    """So mẫu trên chuỗi lỗi không phải một phép đo."""
    assert classify("Permission denied").confidence_level == SUY_RA


def test_dau_hieu_nhan_ra_duoc_neu_ra_de_nguoi_kiem_lai():
    chan = classify("mkdir: /usr/local: Permission denied")
    assert "permission denied" in chan.signal.lower()
    assert "permission denied" in chan.render().lower()


def test_mau_hep_thang_mau_rong():
    """Một thông báo chạm nhiều mẫu; cái đúng phải thắng."""
    # có cả 'permission denied' lẫn 'connection' — quyền phải thắng
    assert classify("connection setup: permission denied on socket").kind == QUYEN


def test_giu_lai_ma_thoat_va_nguyen_van_dau_ra():
    chan = classify("E: Unable to locate package x", returncode=100, tool="avr-gcc")
    assert chan.returncode == 100 and chan.tool == "avr-gcc"
    assert "Unable to locate package" in chan.output


# --------------------------------------------------------------- thử lại ---


def test_chi_loi_mang_moi_dang_thu_lai():
    assert classify("Connection timed out").retryable is True
    for van_ban in ("Permission denied", "unmet dependencies",
                    "Unable to locate package x", "make: *** Error 2", "chuyện lạ"):
        assert classify(van_ban).retryable is False, van_ban


def test_gian_cach_thu_lai_tang_gap_doi_va_co_tran():
    g = retry_delays()
    assert len(g) == SO_LAN_THU_LAI
    assert g == [2.0, 4.0, 8.0]


# ------------------------------------------------------------ thang gỡ ---


def test_moi_loai_deu_co_thang_va_thang_luon_ket_thuc_o_nguoi():
    for loai in (MANG, QUYEN, PHU_THUOC, BUILD, KHONG_TIM_THAY, KHAC):
        thang = remedies(loai, tool="x")
        assert thang, loai
        assert "Bàn giao người" in thang[-1].action


def test_khong_bac_nao_cho_agent_tu_chay_lenh_cai():
    """Cài phần mềm là đổi máy người dùng — N-022 ở mức tự chủ T2."""
    from eaa.environ import TRINH_QUAN_LY_GOI
    from eaa.installerr import _DONG_TU_CAI, _GO

    dong_tu = set(_DONG_TU_CAI) | {v for bo in _GO.values() for v in bo}
    for loai in (MANG, QUYEN, PHU_THUOC, BUILD, KHONG_TIM_THAY, KHAC):
        for r in remedies(loai, tool="x", install_command=("brew", "install", "x")):
            if not r.agent_can_do or not r.command:
                continue
            # So theo TỪNG PHẦN TỬ argv, không theo chuỗi con: "installation
            # guide" chứa chuỗi "install" mà không cài gì cả.
            dau = r.command[0].lstrip("sudo").strip() or r.command[0]
            assert dau not in TRINH_QUAN_LY_GOI, f"{loai}: {r.command}"
            assert not (set(r.command) & dong_tu), f"{loai}: {r.command}"


def test_bac_dau_cua_loi_mang_la_thu_lai_va_agent_lam_duoc():
    dau = remedies(MANG)[0]
    assert "Thử lại" in dau.action and dau.agent_can_do is True


def test_bac_dau_cua_loi_quyen_KHONG_phai_thu_lai():
    dau = remedies(QUYEN)[0]
    assert "Thử lại" not in dau.action
    assert "KHÔNG đáng thử lại" in dau.detail


def test_loi_phu_thuoc_noi_ro_phai_cai_thu_khac_truoc():
    assert "cài NÓ trước" in remedies(PHU_THUOC)[0].action


def test_cong_cu_thay_the_chi_xuat_hien_khi_co_khai():
    khong = remedies(KHONG_TIM_THAY, tool="x")
    assert not any("tương đương" in r.action for r in khong)
    co = remedies(KHONG_TIM_THAY, tool="x", alternatives=["y", "z"])
    bac = next(r for r in co if "tương đương" in r.action)
    assert "y, z" in bac.detail
    assert bac.agent_can_do is False, "đổi công cụ là đổi cả cổng kiểm chứng"


def test_co_lenh_cai_thi_co_bac_quay_lui():
    thang = remedies(MANG, install_command=("brew", "install", "cppcheck"))
    bac = next(r for r in thang if "Quay lui" in r.action)
    assert bac.command == ("brew", "uninstall", "cppcheck")


def test_bac_thang_danh_so_lien_tuc():
    thang = remedies(BUILD, tool="x", alternatives=["y"], install_command=("brew", "install", "x"))
    assert [r.step for r in thang] == list(range(1, len(thang) + 1))


def test_ban_chan_doan_in_ra_duoc_ca_thang():
    ra = classify("E: Could not resolve host: x", tool="avr-gcc").render()
    assert "MẠNG" in ra and "Thang gỡ" in ra
    assert "Agent tự làm được" in ra and "CẦN BẠN chạy" in ra


# ------------------------------------------------------------- quay lui ---


@pytest.mark.parametrize("cai,go", [
    (("brew", "install", "cppcheck"), ("brew", "uninstall", "cppcheck")),
    (("sudo", "apt-get", "install", "-y", "gcc-avr"), ("sudo", "apt-get", "remove", "-y", "gcc-avr")),
    (("pip", "install", "pyserial"), ("pip", "uninstall", "-y", "pyserial")),
    (("npm", "install", "-g", "x"), ("npm", "uninstall", "-g", "x")),
    (("choco", "install", "avrdude", "-y"), ("choco", "uninstall", "-y", "avrdude")),
    (("cargo", "install", "ripgrep"), ("cargo", "uninstall", "ripgrep")),
])
def test_suy_dung_lenh_go(cai, go):
    assert rollback_command(cai) == go


@pytest.mark.parametrize("cai", [
    (),
    ("mot-trinh-la", "install", "x"),
    ("brew",),
    ("brew", "install"),
    ("sudo",),
    ("curl", "-fsSL", "https://x/install.sh"),
])
def test_khong_suy_duoc_thi_tra_rong_chu_khong_doan(cai):
    """Một lệnh gỡ đoán sai chạy với quyền quản trị tệ hơn không có lệnh gỡ nào."""
    assert rollback_command(cai) == ()


def test_go_giu_nguyen_tien_to_nang_quyen():
    assert rollback_command(("sudo", "apt", "install", "x"))[0] == "sudo"


def test_go_bo_co_nhung_giu_ten_goi():
    assert rollback_command(("sudo", "apt-get", "install", "-y", "--no-install-recommends", "a", "b")) == (
        "sudo", "apt-get", "remove", "-y", "a", "b")
