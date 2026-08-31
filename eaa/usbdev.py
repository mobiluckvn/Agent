"""Thiết bị USB đang cắm — câu hỏi "bo đã nhận chưa" khác câu "có cổng nối tiếp không".

EAA-AIS-05 §7 (chẩn đoán phần cứng); FR-HW-01. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-108.

Khoảng trống module này lấp
----------------------------

``eaa ports`` liệt kê cổng nối tiếp, và với một bo giao tiếp qua UART thì đó
đúng là câu hỏi cần hỏi. Nhưng nhiều bo phát triển nối máy tính qua một **mạch
nạp/gỡ rối gắn sẵn trên bo**, và mạch ấy hiện ra như một thiết bị USB thô —
không phải một cổng nối tiếp. Cắm đúng, nguồn đủ, mạch nạp chạy tốt, mà
``/dev/cu.*`` vẫn không có gì mới.

Hệ quả là câu trả lời *"không cổng nào khớp bo đã khai"* đọc thành *"chưa cắm"*
trong khi sự thật có thể là *"cắm rồi, chỉ là bo này không hiện ra cổng nối
tiếp nào cả"*. Hai câu ấy dẫn tới hai việc khác hẳn nhau: một bên đi kiểm dây
và cổng, một bên đi tiếp.

Module này trả lời câu còn thiếu: **máy đang thấy thiết bị USB nào.**

Không thêm phụ thuộc
---------------------

Mỗi hệ điều hành có một lệnh sẵn có để liệt kê USB. Gọi lệnh ấy và đọc đầu ra
(NFR-04). Không có lệnh nào chạy được thì nói thẳng là không kiểm được, chứ
**không** trả về danh sách rỗng — rỗng đọc thành "không có gì cắm", và đó
chính là câu sai mà module này sinh ra để tránh.

Ranh giới engine
-----------------

Không có tên nhà sản xuất, mã VID/PID hay tên bo nào trong tệp này (TC-38).
Việc so khớp dùng phần khai ``programmer.usb`` của hồ sơ phần cứng từng dự án.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

__all__ = [
    "UsbDevice",
    "UsbScan",
    "list_usb_devices",
    "match_usb",
    "render_usb",
]

#: Hạn giờ gọi lệnh hệ thống. Liệt kê USB là việc mili-giây; quá thế là treo.
TIMEOUT_S = 10.0


@dataclass(frozen=True)
class UsbDevice:
    """Một thiết bị USB máy đang thấy."""

    vid: str = ""
    pid: str = ""
    name: str = ""
    vendor: str = ""
    #: Ghi chú của dự án nếu thiết bị này khớp một mục đã khai.
    matched: str = ""

    @property
    def id(self) -> str:
        return f"{self.vid}:{self.pid}" if self.vid and self.pid else ""

    def render(self) -> str:
        dong = f"  {self.id or '—':<12} {(self.vendor + ' ' + self.name).strip() or '(không tên)'}"
        if self.matched:
            dong += f"   ← {self.matched}"
        return dong


@dataclass(frozen=True)
class UsbScan:
    """Kết quả một lượt quét. Phân biệt 'không có gì' với 'không kiểm được'."""

    devices: tuple[UsbDevice, ...] = ()
    #: Lệnh đã dùng để liệt kê. Rỗng nghĩa là không lệnh nào chạy được.
    tool: str = ""
    note: str = ""

    @property
    def usable(self) -> bool:
        """Có kiểm được không. KHÁC với 'có thiết bị nào không'."""
        return bool(self.tool)

    @property
    def confidence_level(self) -> str:
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC

        return DA_KIEM if self.usable else KHONG_KIEM_DUOC


def _chay(argv: Sequence[str]) -> str:
    try:
        kq = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    return kq.stdout or ""


def _bon_so(x: Any) -> str:
    """Chuẩn hoá một mã VID/PID về bốn chữ số hex thường.

    Hai kiểu vào, và **phân biệt chúng là bắt buộc**:

    * **Chuỗi** — đã là chữ số hex, có thể kèm tiền tố ``0x``. Đây là dạng mọi
      công cụ liệt kê USB in ra, và là dạng người ta gõ vào YAML.
    * **Số nguyên** — giá trị thật. YAML đọc ``0x1234`` thành ``4660``, nên tới
      đây nó là số, và số ấy phải in lại thành hex.

    Gộp hai kiểu bằng một phép ``isdigit()`` là sai, và sai im lặng: một chuỗi
    hex toàn chữ số như ``"1234"`` bị đọc thành **thập phân** rồi in lại thành
    ``04d2`` — một mã khác hẳn, và không có gì báo. Một bo đúng sẽ bị chấm là
    lạ, và một bo lạ có thể lọt.

    Ví dụ ở đây cố ý dùng số bịa: mã VID/PID thật thuộc về hồ sơ dự án, không
    thuộc về engine (TC-38).
    """
    if isinstance(x, bool):
        return ""
    if isinstance(x, int):
        return f"{x:04x}" if 0 <= x <= 0xFFFF else ""

    s = str(x).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if not s or len(s) > 4 or any(c not in "0123456789abcdef" for c in s):
        return ""
    return s.rjust(4, "0")


# --------------------------------------------------------------------------
# Liệt kê theo hệ điều hành
# --------------------------------------------------------------------------


_RE_IOREG_TEN = re.compile(r'"USB Product Name"\s*=\s*"([^"]*)"')
_RE_IOREG_HANG = re.compile(r'"USB Vendor Name"\s*=\s*"([^"]*)"')
_RE_IOREG_VID = re.compile(r'"idVendor"\s*=\s*(\d+)')
_RE_IOREG_PID = re.compile(r'"idProduct"\s*=\s*(\d+)')


def _quet_macos() -> UsbScan:
    ra = _chay(["ioreg", "-p", "IOUSB", "-l", "-w", "0"])
    if not ra:
        return UsbScan()

    ds: list[UsbDevice] = []
    # ioreg in ra theo cây; mỗi nút thiết bị là một khối giữa hai dấu '+-o'.
    for khoi in re.split(r"\n\s*\+-o ", ra)[1:]:
        vid = _RE_IOREG_VID.search(khoi)
        pid = _RE_IOREG_PID.search(khoi)
        if not (vid and pid):
            continue
        ten = _RE_IOREG_TEN.search(khoi)
        hang = _RE_IOREG_HANG.search(khoi)
        # ioreg in giá trị THẬP PHÂN; ép về int rồi mới in lại thành hex.
        ds.append(UsbDevice(
            vid=_bon_so(int(vid.group(1))), pid=_bon_so(int(pid.group(1))),
            name=(ten.group(1) if ten else "").strip(),
            vendor=(hang.group(1) if hang else "").strip(),
        ))
    return UsbScan(devices=tuple(ds), tool="ioreg")


_RE_LSUSB = re.compile(
    r"Bus\s+\d+\s+Device\s+\d+:\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)"
)


def _quet_linux() -> UsbScan:
    ra = _chay(["lsusb"])
    if ra:
        ds = []
        for dong in ra.splitlines():
            m = _RE_LSUSB.match(dong.strip())
            if m:
                ds.append(UsbDevice(vid=m.group(1).lower(), pid=m.group(2).lower(),
                                    name=m.group(3).strip()))
        return UsbScan(devices=tuple(ds), tool="lsusb")

    # Không có lsusb thì đọc thẳng sysfs — có sẵn trên mọi bản Linux.
    from pathlib import Path

    goc = Path("/sys/bus/usb/devices")
    if not goc.is_dir():
        return UsbScan()
    ds = []
    for d in sorted(goc.iterdir()):
        v, p = d / "idVendor", d / "idProduct"
        if not (v.is_file() and p.is_file()):
            continue
        ten = d / "product"
        hang = d / "manufacturer"
        try:
            ds.append(UsbDevice(
                vid=v.read_text().strip().lower(), pid=p.read_text().strip().lower(),
                name=ten.read_text().strip() if ten.is_file() else "",
                vendor=hang.read_text().strip() if hang.is_file() else "",
            ))
        except OSError:
            continue
    return UsbScan(devices=tuple(ds), tool="sysfs")


_RE_WIN_ID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")


def _quet_windows() -> UsbScan:
    ra = _chay([
        "powershell", "-NoProfile", "-Command",
        "Get-PnpDevice -PresentOnly | "
        "Where-Object {$_.InstanceId -like 'USB*'} | "
        "ForEach-Object { \"$($_.InstanceId)|$($_.FriendlyName)\" }",
    ])
    if not ra:
        return UsbScan()
    ds = []
    for dong in ra.splitlines():
        m = _RE_WIN_ID.search(dong)
        if not m:
            continue
        ten = dong.split("|", 1)[1].strip() if "|" in dong else ""
        ds.append(UsbDevice(vid=m.group(1).lower(), pid=m.group(2).lower(), name=ten))
    return UsbScan(devices=tuple(ds), tool="Get-PnpDevice")


def list_usb_devices(*, platform: str = "") -> UsbScan:
    """Liệt kê thiết bị USB. Không kiểm được thì nói ra, không trả rỗng."""
    he = (platform or sys.platform).lower()
    if he.startswith("darwin"):
        kq = _quet_macos()
        ten_lenh = "ioreg"
    elif he.startswith("linux"):
        kq = _quet_linux()
        ten_lenh = "lsusb hoặc /sys/bus/usb"
    elif he.startswith("win"):
        kq = _quet_windows()
        ten_lenh = "Get-PnpDevice"
    else:
        return UsbScan(note=f"Chưa biết cách liệt kê USB trên nền {he!r}.")

    if kq.usable:
        return kq
    return UsbScan(note=(
        f"Không chạy được lệnh liệt kê USB ({ten_lenh}) trên máy này, nên tôi "
        "KHÔNG kết luận được là bạn đã cắm bo hay chưa."
    ))


# --------------------------------------------------------------------------
# So khớp với phần khai của dự án
# --------------------------------------------------------------------------


def match_usb(scan: UsbScan, declared: Iterable[Any]) -> UsbScan:
    """Đánh dấu thiết bị khớp mục ``programmer.usb`` của hồ sơ phần cứng."""
    khai = list(declared or [])
    if not khai:
        return scan

    ra: list[UsbDevice] = []
    for d in scan.devices:
        nhan = ""
        for k in khai:
            v = _bon_so(getattr(k, "vid", "") or "")
            p = _bon_so(getattr(k, "pid", "") or "")
            if v and p and (v, p) == (d.vid, d.pid):
                nhan = str(getattr(k, "note", "") or "bo đã khai trong hồ sơ")
                break
        ra.append(UsbDevice(vid=d.vid, pid=d.pid, name=d.name, vendor=d.vendor,
                            matched=nhan))
    return UsbScan(devices=tuple(ra), tool=scan.tool, note=scan.note)


def render_usb(scan: UsbScan, *, declared: bool = False) -> str:
    """In kết quả. Ba trường hợp, và chúng phải phân biệt được với nhau."""
    from eaa.confidence import header

    dong = [header(scan.confidence_level), ""]

    if not scan.usable:
        dong.append(f"  {scan.note}")
        return "\n".join(dong)

    khop = [d for d in scan.devices if d.matched]
    if khop:
        dong.append(f"  Thấy bo của dự án ({len(khop)} thiết bị khớp phần khai):")
        dong += [d.render() for d in khop]
        return "\n".join(dong)

    if not scan.devices:
        dong.append(f"  Máy KHÔNG thấy thiết bị USB nào (liệt kê bằng {scan.tool}).")
        dong.append("  Nghĩa là bo chưa được máy nhận.")
        dong.append("  Đây KHÔNG phải chuyện thiếu trình điều khiển hay thiếu")
        dong.append("  thư viện — kiểm dây, kiểm đúng cổng trên bo, kiểm nguồn.")
        return "\n".join(dong)

    dong.append(f"  {len(scan.devices)} thiết bị USB đang cắm (liệt kê bằng {scan.tool}):")
    dong += [d.render() for d in scan.devices]
    dong.append("")
    if declared:
        dong.append("  Không thiết bị nào khớp phần 'programmer.usb' của dự án.")
    else:
        dong.append("  Dự án chưa khai 'programmer.usb' nên tôi không nói được")
        dong.append("  cái nào trong số trên là bo của bạn.")
    return "\n".join(dong)
