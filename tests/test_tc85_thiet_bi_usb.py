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


#: Đầu ra ``ioreg`` THẬT — cây, không phải danh sách phẳng.
#:
#: Khác biệt duy nhất so với `_IOREG` ở trên, và là khác biệt làm hỏng mọi thứ:
#: nút con được vẽ bằng **gạch dọc** ``|`` chứ không phải khoảng trắng. Bo cắm
#: qua hub — cách gần như mọi máy xách tay ngày nay nối ra ngoài — nằm sâu hai,
#: ba tầng, nên dòng của nó luôn mang tiền tố ấy.
#:
#: Mã VID/PID bịa: mã thật thuộc về hồ sơ dự án, không thuộc về engine (TC-38).
_IOREG_CAY = """\
+-o Root  <class IORegistryEntry, id 0x100000100>
  +-o XHC1@14000000  <class AppleUSBXHCITR, id 0x1000004ff>
  | {
  |   "IOClass" = "AppleUSBXHCITR"
  | }
  |
  | +-o Hub tang 1@14300000  <class IOUSBHostDevice, id 0x100000501>
  |   {
  |     "idVendor" = 4369
  |     "idProduct" = 4369
  |     "USB Product Name" = "Hub tang 1"
  |   }
  |
  |   +-o Hub tang 2@14340000  <class IOUSBHostDevice, id 0x100000502>
  |   | {
  |   |   "idVendor" = 8738
  |   |   "idProduct" = 8738
  |   |   "USB Product Name" = "Hub tang 2"
  |   | }
  |   |
  |   | +-o Bo cua du an@14341000  <class IOUSBHostDevice, id 0x100000503>
  |   |     {
  |   |       "idVendor" = 43981
  |   |       "idProduct" = 48059
  |   |       "USB Product Name" = "Mach nap tren bo"
  |   |       "USB Vendor Name" = "Hang bia"
  |   |     }
  |   |
  |   +-o Thiet bi canh@14350000  <class IOUSBHostDevice, id 0x100000504>
  |       {
  |         "idVendor" = 4369
  |         "idProduct" = 8191
  |         "USB Product Name" = "Thiet bi canh"
  |       }
  |
  +-o XHC2@00000000  <class AppleUSBXHCITR, id 0x100000600>
    +-o Thiet bi goc@00100000  <class IOUSBHostDevice, id 0x100000601>
        {
          "idVendor" = 61455
          "idProduct" = 61455
          "USB Product Name" = "Thiet bi goc"
        }
"""


def test_ioreg_cay_KHONG_duoc_nuot_thiet_bi_con(monkeypatch):
    """Bo cắm qua hub nằm sâu trong cây. Nuốt nó là nuốt đúng cái cần tìm.

    Tìm ra với bo thật: máy đang cắm một mạch nạp qua hai tầng hub, ``ioreg``
    thấy nó, mà ``eaa ports`` thì không. Lý do là bài kiểm cũ dựng đầu ra
    **phẳng hơn đời thật** — mọi nút cùng một mức thụt lề bằng khoảng trắng.
    Đầu ra thật vẽ nhánh bằng ``|``, và dấu ấy không phải khoảng trắng.

    Hỏng kiểu tệ nhất: không sập, không cảnh báo. Nút con bị **gộp vào khối
    của nút cha**, nên lệnh vẫn in ra một danh sách trông đầy đủ — chỉ là mỗi
    nhánh chỉ còn lại thiết bị đầu tiên, và bo của người dùng thì biến mất
    trong khi bản in vẫn mang nhãn ĐÃ KIỂM.
    """
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: _IOREG_CAY)
    s = u.list_usb_devices(platform="darwin")

    ma = [d.id for d in s.devices]
    assert "abcd:bbbb" in ma, f"nuốt mất bo nằm sau hai tầng hub; chỉ thấy {ma}"
    assert ma == ["1111:1111", "2222:2222", "abcd:bbbb", "1111:1fff", "f00f:f00f"], \
        "phải thấy ĐỦ mọi nút, kể cả nút nằm trên nhánh vẽ bằng '|'"

    bo = [d for d in s.devices if d.id == "abcd:bbbb"][0]
    assert bo.name == "Mach nap tren bo", "lấy nhầm tên của nút cha"
    assert bo.vendor == "Hang bia"


def test_ioreg_bo_sau_hub_van_KHOP_phan_khai(monkeypatch):
    """Nuốt thiết bị con thì so khớp cũng hỏng theo — im lặng.

    Người dùng khai đúng mã bo của mình, cắm đúng bo ấy, mà lệnh vẫn trả lời
    *"không thiết bị nào khớp"*. Đó lại đúng câu *"chưa cắm"* mà cả module này
    sinh ra để tránh — chỉ là lần này nó sai ở tầng đọc đầu ra.
    """
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: _IOREG_CAY)
    quet = u.list_usb_devices(platform="darwin")
    s = match_usb(quet, [_Khai("0xabcd", "0xbbbb", "mạch nạp trên bo")])

    assert [d.id for d in s.devices if d.matched] == ["abcd:bbbb"]
    assert "Thấy bo của dự án" in render_usb(s, declared=True)


def test_ioreg_khong_nut_nao_thi_van_la_KIEM_DUOC(monkeypatch):
    """Lệnh chạy được mà cây rỗng là "không có gì cắm" — khác "không kiểm được"."""
    import eaa.usbdev as u

    monkeypatch.setattr(u, "_chay", lambda argv: "+-o Root  <class IORegistryEntry>\n")
    s = u.list_usb_devices(platform="darwin")
    assert s.usable and s.devices == ()


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


def test_bo_dung_CO_MAT_thi_khong_canh_bao_du_con_thiet_bi_khac():
    """Thấy bo của dự án rồi thì câu "có cắm nhầm bo không" ĐÃ có trả lời: không.

    Tìm ra với bo thật cắm qua đế cắm: lệnh nhận đúng bo, rồi vẫn cảnh báo
    *"đang cắm 7 thiết bị ngoài, KHÔNG cái nào khớp"* — và bảy thứ ấy là hub,
    card mạng, đầu đọc thẻ. Một cảnh báo bắn ở mọi bàn làm việc có đế cắm là
    một cảnh báo bị bỏ qua, và lúc nó bắn đúng thì cũng bị bỏ qua nốt — đúng
    cái bẫy mà chính docstring của hàm này nêu ra để tránh.

    Lý do cảnh báo tồn tại là *"mã dịch xong, nạp xong, rồi mới không chạy"*.
    Lý do ấy tắt ngay khi bo đã khai có mặt trên bus.
    """
    from eaa.cli import _thiet_bi_la

    khai = [_Khai("1111", "2222", "bo của dự án")]
    quet = match_usb(
        _quet(UsbDevice("1111", "2222", "Bo đúng"),
              UsbDevice("aaaa", "bbbb", "Hub", "Hãng đế cắm"),
              UsbDevice("cccc", "dddd", "Card mạng", "Hãng khác")),
        khai,
    )
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


# ═══════════════ --watch: thử từng cách và xem NGAY kết quả ═══════════════


def _lan_luot(*quets):
    """Trả một hàm giả `list_usb_devices` lần lượt trả từng lượt quét."""
    hop = list(quets)

    def _goi(**k):
        return hop.pop(0) if len(hop) > 1 else hop[0]

    return _goi


def test_watch_bao_khi_CAM_VAO(monkeypatch, capsys):
    """Chụp-một-lần bắt người dùng tự nhớ lần trước thấy gì. Canh thì không."""
    import eaa.usbdev as u
    from eaa.cli import _canh_usb

    truoc = _quet(UsbDevice("05ac", "0340", "Keyboard", "Apple"))
    sau = _quet(UsbDevice("05ac", "0340", "Keyboard", "Apple"),
                UsbDevice("aaaa", "bbbb", "Bo vua cam", "Hang X"))
    monkeypatch.setattr(u, "list_usb_devices", _lan_luot(truoc, sau))

    _canh_usb([_Khai("1111", "2222")], timeout_s=0.3, nhip_s=0.01)
    ra = capsys.readouterr().out
    assert "+ CẮM VÀO" in ra and "aaaa:bbbb" in ra
    assert "KHÔNG khớp bo đã khai" in ra, "cắm nhầm bo phải bị nói ngay lúc cắm"


def test_watch_bao_khi_RUT_RA(monkeypatch, capsys):
    import eaa.usbdev as u
    from eaa.cli import _canh_usb

    truoc = _quet(UsbDevice("aaaa", "bbbb", "Bo", "Hang X"))
    sau = _quet()
    monkeypatch.setattr(u, "list_usb_devices", _lan_luot(truoc, sau))

    _canh_usb([], timeout_s=0.3, nhip_s=0.01)
    assert "− RÚT RA" in capsys.readouterr().out


def test_watch_bo_DUNG_thi_bao_KHOP_chu_khong_canh_bao(monkeypatch, capsys):
    import eaa.usbdev as u
    from eaa.cli import _canh_usb

    khai = [_Khai("aaaa", "bbbb", "bo của dự án")]
    monkeypatch.setattr(u, "list_usb_devices", _lan_luot(
        _quet(), _quet(UsbDevice("aaaa", "bbbb", "Bo dung", "Hang X"))))

    _canh_usb(khai, timeout_s=0.3, nhip_s=0.01)
    ra = capsys.readouterr().out
    assert "KHỚP bo của dự án" in ra
    assert "KHÔNG khớp" not in ra


def test_watch_khong_doi_gi_thi_noi_HAU_QUA(monkeypatch, capsys):
    """Hết giờ mà bus không đổi là một kết luận, không phải một sự im lặng."""
    import eaa.usbdev as u
    from eaa.cli import _canh_usb

    monkeypatch.setattr(u, "list_usb_devices", _lan_luot(_quet(UsbDevice("05ac", "0340"))))
    _canh_usb([], timeout_s=0.05, nhip_s=0.01)
    ra = capsys.readouterr().out
    assert "không thấy thay đổi" in ra
    assert "trước cả tầng trình điều khiển" in ra, "phải loại trừ nguyên nhân sai"
    assert "đường dữ liệu" in ra, "phải nêu nguyên nhân hay gặp nhất"


def test_watch_khong_liet_ke_duoc_thi_KHONG_canh(monkeypatch, capsys):
    """Không đo được thì đừng bày ra một màn hình canh chẳng canh gì."""
    import eaa.usbdev as u
    from eaa.cli import EXIT_ENV_ERROR, _canh_usb

    monkeypatch.setattr(u, "list_usb_devices",
                        lambda **k: UsbScan(note="không chạy được lệnh nào"))
    assert _canh_usb([], timeout_s=0.05, nhip_s=0.01) == EXIT_ENV_ERROR
    assert "không chạy được" in capsys.readouterr().out
