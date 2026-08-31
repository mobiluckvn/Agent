"""TC-85 — "bo đã nhận chưa" khác "có cổng nối tiếp không", và cắm nhầm bo phải bị bắt.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-108.

Tìm ra khi người dùng cắm một bo thật vào máy và ``eaa ports`` trả lời *"không
cổng nào khớp bo đã khai"*. Câu ấy đọc thành *"chưa cắm"*, nhưng nó không có
nghĩa đó: nhiều bo nối máy qua **mạch nạp gắn sẵn trên bo**, hiện ra như một
thiết bị USB thô và **không sinh cổng nối tiếp nào**. Cắm đúng, nguồn đủ, mạch
nạp chạy tốt, mà ``/dev/cu.*`` vẫn không có gì mới.

Hai câu ấy dẫn tới hai việc khác hẳn: một bên đi kiểm dây và cổng, một bên đi
tiếp. Trả lời nhập nhằng ở đây làm người dùng đi sai đường ngay từ bước đầu
chạm vào thế giới vật lý.

Và một câu nữa mà lệnh này chưa từng trả lời: **bạn có đang cắm nhầm bo không.**
"""

from __future__ import annotations

import pytest

from eaa.usbdev import (
    UsbDevice,
    UsbScan,
    list_usb_devices,
    match_usb,
    render_usb,
)


class _Khai:
    def __init__(self, vid, pid, note=""):
        self.vid, self.pid, self.note = vid, pid, note


# ═══════ "không kiểm được" KHÁC "không có gì" — phân biệt được ═══════


def test_khong_chay_duoc_lenh_thi_NOI_RA_chu_khong_tra_rong(monkeypatch):
    """Rỗng đọc thành "không có gì cắm" — đúng câu sai module này sinh ra để tránh."""
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: "")
    s = u.list_usb_devices(platform="darwin")
    assert not s.usable
    assert s.devices == ()
    assert "KHÔNG kết luận được" in s.note
    from eaa.confidence import KHONG_KIEM_DUOC

    assert s.confidence_level == KHONG_KIEM_DUOC


def test_khong_kiem_duoc_thi_ban_in_ra_noi_ro(monkeypatch):
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: "")
    ra = render_usb(u.list_usb_devices(platform="darwin"))
    assert "KHÔNG kết luận được" in ra
    assert "thiết bị USB nào" not in ra, "không được kết luận thay"


def test_khong_co_thiet_bi_nao_thi_noi_DUT_KHOAT(monkeypatch):
    """Kiểm được và thấy rỗng là một câu trả lời MẠNH — nói cho ra câu."""
    s = UsbScan(devices=(), tool="ioreg")
    ra = render_usb(s)
    assert "KHÔNG thấy thiết bị USB nào" in ra
    assert "chưa được máy nhận" in ra
    assert "KHÔNG phải chuyện thiếu trình điều khiển" in ra, \
        "phải loại trừ nguyên nhân sai"
    assert "kiểm dây" in ra, "phải chỉ chỗ đi kiểm"


def test_nen_la_thi_noi_chua_biet_cach_liet_ke():
    s = list_usb_devices(platform="plan9")
    assert not s.usable and "Chưa biết cách liệt kê" in s.note


# ═══════════════ đọc đầu ra từng hệ điều hành ═══════════════


_IOREG = """
+-o Root
  +-o AppleUSBXHCI
    |   "idVendor" = 1452
    |   "idProduct" = 33027
    |   "USB Product Name" = "Touch Bar Display"
    |   "USB Vendor Name" = "Apple Inc."
  +-o BoNao@14200000
    |   "idVendor" = 9025
    |   "idProduct" = 67
    |   "USB Product Name" = "Bo thử nghiệm"
    |   "USB Vendor Name" = "Nha San Xuat"
"""


def test_doc_duoc_ioreg(monkeypatch):
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: _IOREG)
    s = u.list_usb_devices(platform="darwin")
    assert s.tool == "ioreg" and len(s.devices) == 2
    assert s.devices[1].vid == "2341" and s.devices[1].pid == "0043"
    assert s.devices[1].name == "Bo thử nghiệm"


_LSUSB = (
    "Bus 001 Device 002: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
    "Bus 001 Device 005: ID 2341:0043 Bo thử nghiệm\n"
)


def test_doc_duoc_lsusb(monkeypatch):
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: _LSUSB)
    s = u.list_usb_devices(platform="linux")
    assert s.tool == "lsusb" and len(s.devices) == 2
    assert (s.devices[1].vid, s.devices[1].pid) == ("2341", "0043")


_WIN = "USB\\VID_2341&PID_0043\\85035\\|Bo thử nghiệm (COM3)\n"


def test_doc_duoc_windows(monkeypatch):
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: _WIN)
    s = u.list_usb_devices(platform="win32")
    assert len(s.devices) == 1
    assert (s.devices[0].vid, s.devices[0].pid) == ("2341", "0043")
    assert "COM3" in s.devices[0].name


# ═══════════════ so khớp với phần khai của dự án ═══════════════


def _quet(*ds: UsbDevice) -> UsbScan:
    return UsbScan(devices=ds, tool="ioreg")


def test_khop_thi_danh_dau_kem_ghi_chu():
    s = match_usb(
        _quet(UsbDevice("1111", "2222", "Bo A")),
        [_Khai("0x1111", "0x2222", "mạch nạp trên bo")],
    )
    assert s.devices[0].matched == "mạch nạp trên bo"
    assert "mạch nạp trên bo" in render_usb(s, declared=True)


def test_khop_khong_phu_thuoc_cach_viet_ma():
    """0x2341, 2341, '2341' phải là cùng một mã."""
    for viet in ("0x2341", "2341", 0x2341, 9025):
        s = match_usb(_quet(UsbDevice("2341", "0043")), [_Khai(viet, "0x0043")])
        assert s.devices[0].matched, f"không khớp với cách viết {viet!r}"


def test_chua_khai_thi_khong_khop_gi_va_NOI_RA():
    s = match_usb(_quet(UsbDevice("2341", "0043", "Bo lạ")), [])
    ra = render_usb(s, declared=False)
    assert "chưa khai" in ra
    assert "không nói được" in ra


# ═══════════════ CẮM NHẦM BO — câu hỏi lệnh này chưa từng trả lời ═══════════════


def test_cam_nham_bo_thi_CANH_BAO(capsys):
    """Người dùng cắm một bo thuộc họ khác. Mã dịch xong, nạp xong, rồi không chạy.

    Đây là kiểu hỏng đắt nhất trong nhóm này: nó tiêu hết một vòng sinh mã,
    một lượt nạp, và thời gian gỡ rối trên một giả định sai từ đầu.
    """
    from eaa.cli import _thiet_bi_la

    quet = match_usb(
        _quet(UsbDevice("05ac", "8103", "Headset", "Apple"),
              UsbDevice("aaaa", "bbbb", "Bo họ khác", "Hãng khác")),
        [_Khai("1111", "2222", "bo của dự án")],
    )
    la = _thiet_bi_la(quet, [_Khai("1111", "2222")])
    assert [d.id for d in la] == ["aaaa:bbbb"], "phải nêu đúng thiết bị lạ"


def test_thiet_bi_cua_MAY_CHU_khong_bi_ke_la():
    """Bàn phím và camera của máy không phải bo người dùng vừa cắm."""
    from eaa.cli import _thiet_bi_la

    quet = match_usb(
        _quet(UsbDevice("05ac", "8103", "Headset", "Apple"),
              UsbDevice("05ac", "0340", "Keyboard", "Apple")),
        [_Khai("1111", "2222")],
    )
    assert _thiet_bi_la(quet, [_Khai("1111", "2222")]) == []


def test_dung_bo_thi_KHONG_canh_bao():
    from eaa.cli import _thiet_bi_la

    khai = [_Khai("1111", "2222", "bo của dự án")]
    quet = match_usb(_quet(UsbDevice("1111", "2222", "Bo đúng")), khai)
    assert _thiet_bi_la(quet, khai) == []


def test_chua_khai_bo_thi_KHONG_canh_bao():
    """Chưa khai thì mọi thiết bị đều "không khớp".

    Một cảnh báo bắn vào mọi trường hợp là một cảnh báo bị bỏ qua — và lúc nó
    bắn đúng thì cũng bị bỏ qua nốt.
    """
    from eaa.cli import _thiet_bi_la

    quet = match_usb(_quet(UsbDevice("aaaa", "bbbb", "Bo lạ")), [])
    assert _thiet_bi_la(quet, []) == []


def test_khong_kiem_duoc_thi_KHONG_canh_bao():
    """Không liệt kê được USB thì không kết luận là cắm nhầm."""
    from eaa.cli import _thiet_bi_la

    assert _thiet_bi_la(UsbScan(note="không chạy được"), [_Khai("1", "2")]) == []


# ═══════════════ ranh giới engine ═══════════════


def test_khong_co_ten_phan_cung_cu_the_trong_module():
    """TC-38 quét cả kho; bài này canh riêng module vừa thêm, sát chỗ dễ sai."""
    from pathlib import Path

    nguon = (Path(__file__).resolve().parents[1] / "eaa" / "usbdev.py").read_text(
        encoding="utf-8").lower()
    for cam in ("stlink", "st-link", "stmicro", "atmel", "arduino", "0483", "2341"):
        assert cam not in nguon, f"engine chứa tên/mã phần cứng cụ thể: {cam}"
