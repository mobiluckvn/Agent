"""Liệt kê cổng nối tiếp và nhận diện mạch đang cắm.

EAA-AIS-05 §7 (chẩn đoán hai kênh — kênh máy đi qua đây), FR-DIA-02.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-32.

Đây là mắt xích đầu tiên chạm vào thế giới vật lý. Trước nó, mọi thứ Agent làm
đều nằm trong máy tính: đọc tài liệu, sinh mã, chạy cổng, ghi Git. Từ đây trở
đi có một sợi dây USB, và ở đầu kia là thứ có thể cháy nếu nạp nhầm.

Engine không biết mạch nào là mạch nào
---------------------------------------

Mã ở đây liệt kê cổng và so với DANH SÁCH DO DỰ ÁN KHAI. Cặp VID/PID nào là bo
nào, tên cổng trông ra sao — đều nằm trong ``hardware_profile.yaml``, vì đó là
thuộc tính của cái bo cụ thể đang nằm trên bàn, không phải của họ vi điều khiển
và càng không phải của engine.

Nói rõ mình KHÔNG biết gì
--------------------------

Không có ``pyserial`` thì trên POSIX vẫn liệt kê được tên cổng, nhưng không đọc
được VID/PID — và lúc ấy hàm này nói thẳng là không đọc được, thay vì trả về
danh sách trông y hệt trường hợp đọc được rồi để người tưởng là mạch không khớp.
Một dòng "không nhận diện được" trung thực đáng giá hơn một dòng "không khớp"
sai.
"""

from __future__ import annotations

import glob
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "SerialPort",
    "UsbId",
    "list_ports",
    "match_declared",
    "render_ports",
    "pyserial_available",
]

#: Cổng ảo luôn có trên máy nhưng không bao giờ là bo mạch — Bluetooth, debug
#: console của hệ điều hành. Lọc ra để danh sách không chôn mất cổng thật.
_BO_QUA = re.compile(
    r"(bluetooth|blth|debug-console|wlan-debug|incoming-port)", re.IGNORECASE
)


def pyserial_available() -> bool:
    try:
        import serial.tools.list_ports  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass(frozen=True)
class UsbId:
    """Một cặp VID/PID mà dự án khai là bo của mình."""

    vid: str
    pid: str = ""
    note: str = ""

    @staticmethod
    def _chuan(gia_tri: Any) -> str:
        """Bỏ tiền tố ``0x``, hạ chữ thường, đệm đủ bốn chữ số hex.

        Cùng một mã có nhiều cách viết trong tài liệu và trong hệ điều hành;
        chuẩn hóa ở một chỗ thì phần so sánh không phải biết chuyện đó.
        """
        van_ban = str(gia_tri or "").strip().lower()
        if van_ban.startswith("0x"):
            van_ban = van_ban[2:]
        return van_ban.zfill(4) if van_ban else ""

    def matches(self, vid: str, pid: str) -> bool:
        if not vid:
            return False
        if self._chuan(self.vid) != self._chuan(vid):
            return False
        # Khai VID mà không khai PID nghĩa là "mọi bo của hãng này".
        return not self.pid or self._chuan(self.pid) == self._chuan(pid)

    @classmethod
    def from_dict(cls, d: Any) -> "UsbId":
        if not isinstance(d, dict):
            raise ValueError(f"mục usb phải là ánh xạ khóa–giá trị, nhận {d!r}")
        return cls(
            vid=str(d.get("vid", "")),
            pid=str(d.get("pid", "")),
            note=str(d.get("note", "")),
        )


@dataclass
class SerialPort:
    """Một cổng nối tiếp thấy được trên máy này."""

    device: str
    description: str = ""
    vid: str = ""
    pid: str = ""
    serial_number: str = ""
    #: Lấy từ đâu — ``pyserial`` (có VID/PID) hay ``glob`` (chỉ có tên cổng).
    source: str = "glob"
    #: Ghi chú của dự án nếu cổng này khớp một mục đã khai.
    matched: str = ""

    @property
    def identifiable(self) -> bool:
        """Có đủ dữ liệu để nói "đúng/không đúng bo đã khai" hay không."""
        return bool(self.vid)

    def render(self) -> str:
        cot = [f"  {self.device:<28}"]
        if self.identifiable:
            cot.append(f"{self.vid}:{self.pid}")
        else:
            cot.append("VID/PID không đọc được")
        if self.matched:
            cot.append(f"← {self.matched}")
        elif self.description:
            cot.append(self.description)
        return "  ".join(c for c in cot if c)


def list_ports(*, include_virtual: bool = False) -> list[SerialPort]:
    """Liệt kê cổng nối tiếp, ưu tiên nguồn nào cho biết nhiều nhất."""
    cong = _qua_pyserial() if pyserial_available() else _qua_glob()
    if not include_virtual:
        cong = [c for c in cong if not _BO_QUA.search(f"{c.device} {c.description}")]
    return sorted(cong, key=lambda c: c.device)


def _qua_pyserial() -> list[SerialPort]:
    from serial.tools import list_ports as _lp

    ket_qua: list[SerialPort] = []
    for p in _lp.comports():
        vid = f"{p.vid:04x}" if getattr(p, "vid", None) is not None else ""
        pid = f"{p.pid:04x}" if getattr(p, "pid", None) is not None else ""
        ket_qua.append(
            SerialPort(
                device=p.device,
                description=(p.description or "").strip(),
                vid=vid,
                pid=pid,
                serial_number=(getattr(p, "serial_number", "") or ""),
                source="pyserial",
            )
        )
    return ket_qua


#: Mẫu tên cổng trên các hệ POSIX. Đây là quy ước ĐẶT TÊN của hệ điều hành, chứ
#: không phải tri thức về một họ vi điều khiển nào — engine vẫn không biết bo
#: nào đang cắm, nó chỉ biết chỗ hệ điều hành bày cổng ra.
_MAU_POSIX: tuple[str, ...] = (
    "/dev/cu.*",          # macOS
    "/dev/ttyUSB*",       # Linux, cầu USB-nối tiếp
    "/dev/ttyACM*",       # Linux, thiết bị CDC
    "/dev/serial/by-id/*",
)


def _qua_glob() -> list[SerialPort]:
    ket_qua: list[SerialPort] = []
    da_thay: set[str] = set()
    for mau in _MAU_POSIX:
        for duong_dan in sorted(glob.glob(mau)):
            that = str(Path(duong_dan).resolve()) if "by-id" in mau else duong_dan
            if that in da_thay:
                continue
            da_thay.add(that)
            ket_qua.append(
                SerialPort(
                    device=duong_dan,
                    description=Path(duong_dan).name if "by-id" in mau else "",
                    source="glob",
                )
            )
    return ket_qua


def match_declared(
    ports: Sequence[SerialPort],
    declared: Iterable[UsbId],
    *,
    port_hint: str = "",
) -> list[SerialPort]:
    """Đánh dấu cổng nào khớp danh sách bo dự án khai.

    Khi không đọc được VID/PID, ``port_hint`` cho phép khớp theo tên cổng — kém
    chắc chắn hơn hẳn, nên nhãn ghi rõ là "theo tên cổng" để người đọc biết mức
    tin cậy của nó.
    """
    khai = list(declared)
    for cong in ports:
        cong.matched = ""
        if cong.identifiable:
            for muc in khai:
                if muc.matches(cong.vid, cong.pid):
                    cong.matched = muc.note or f"khai trong hồ sơ ({muc.vid}:{muc.pid})"
                    break
        elif port_hint and port_hint.lower() in cong.device.lower():
            cong.matched = f"khớp theo TÊN CỔNG ({port_hint!r}), chưa xác nhận VID/PID"
    return list(ports)


def render_ports(ports: Sequence[SerialPort]) -> str:
    """Bảng cổng, kèm câu nói rõ engine đang biết tới đâu."""
    if not ports:
        return (
            "Không thấy cổng nối tiếp nào.\n"
            "  · Mạch đã cắm và đã bật chưa?\n"
            "  · Máy đã có trình điều khiển cho cầu USB-nối tiếp chưa?"
        )

    dong = [c.render() for c in ports]
    khop = [c for c in ports if c.matched]

    if khop:
        dong += ["", f"{len(khop)} cổng khớp bo đã khai trong hồ sơ phần cứng."]
    else:
        dong += ["", "Không cổng nào khớp bo đã khai trong hồ sơ phần cứng."]

    if not pyserial_available():
        dong += [
            "",
            "Máy này chưa có pyserial nên KHÔNG đọc được VID/PID — danh sách trên",
            "chỉ là tên cổng. Nhận diện chắc chắn cần:",
            "    pip install pyserial",
        ]
    return "\n".join(dong)


def declared_usb_ids(hardware_profile: Any) -> tuple[list[UsbId], str]:
    """Đọc phần khai bo USB từ hồ sơ phần cứng của dự án.

    Trả về danh sách rỗng khi dự án chưa khai — không phải lỗi: nhận diện bo là
    tiện ích, còn việc nạp vẫn chạy được khi người tự chỉ đúng cổng.
    """
    nap = getattr(hardware_profile, "raw", {}) or {}
    khai = nap.get("programmer") or {}
    if not isinstance(khai, dict):
        return [], ""
    muc = khai.get("usb") or []
    if not isinstance(muc, list):
        return [], str(khai.get("port_hint", ""))
    return [UsbId.from_dict(m) for m in muc], str(khai.get("port_hint", ""))
