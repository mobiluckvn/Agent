"""Đọc telemetry từ cổng nối tiếp — kênh máy của chẩn đoán hai kênh.

EAA-AIS-05 §7 (chẩn đoán hai kênh), FR-DIA-01. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-34.

Chẩn đoán hai kênh là phép GIAO của thứ máy đo được và thứ người quan sát được.
Kênh người đã có từ Sprint 4. Kênh máy tới giờ vẫn đọc từ MỘT TỆP — nghĩa là ai
đó phải tự nối dây, tự bắt log, tự dán vào tệp. Module này thay đoạn "tự" ấy
bằng một đường đọc thẳng từ mạch.

Ba điều quyết định module này đáng tin hay không
------------------------------------------------

1. **Luôn có hạn thời gian.** Một lệnh đọc cổng nối tiếp không có hạn chờ sẽ
   treo mãi khi mạch không nói gì — và "treo" trông giống hệt "đang đo". Mọi
   đường vào đây đều bị chặn trên bằng ``duration_s``.

2. **Khung hỏng được ĐẾM, không bị nuốt.** Bỏ lặng lẽ những khung sai checksum
   là cách giấu đúng thứ cần biết: sai baud, dây dài quá, nguồn sụt khi động cơ
   chạy. Một phiên đo mà 40% khung hỏng vẫn cho ra vài con số trông hợp lý, và
   những con số ấy sẽ đi vào Chương 3.

3. **Giữ nguyên văn thứ nhận được.** Bản ghi thô nằm cạnh bản đã lọc. Khi một
   số đo gây tranh cãi, câu hỏi "mạch thật sự gửi gì" phải trả lời được từ dữ
   liệu chứ không từ trí nhớ — cùng nguyên tắc với nhật ký lời gọi mô hình.

Định dạng khung do DỰ ÁN khai
------------------------------

Firmware gửi gì là chuyện giữa firmware và dự án; engine chỉ biết một quy ước
duy nhất: **mỗi khung là một dòng, phần tải là JSON**, đúng thứ
``DiagnosticSession.parse_telemetry`` vốn đã đọc. Cách gắn checksum và giá trị
baud nằm trong ``diagnostics.yaml``, không nằm ở đây.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml

__all__ = [
    "TelemetryError",
    "FrameSpec",
    "TelemetryFrame",
    "Capture",
    "SerialTelemetryReader",
    "verify_frame",
    "load_frame_spec",
    "read_capture",
    "CHECKSUMS",
]


class TelemetryError(Exception):
    """Không đọc được telemetry, hoặc khai báo khung tin sai."""


# --------------------------------------------------------------------------
# Khung tin
# --------------------------------------------------------------------------


def _xor8(du_lieu: bytes) -> int:
    gia_tri = 0
    for b in du_lieu:
        gia_tri ^= b
    return gia_tri


def _sum8(du_lieu: bytes) -> int:
    return sum(du_lieu) & 0xFF


#: Phép kiểm tổng được hỗ trợ. Đây là số học thuần túy, không phải tri thức về
#: một họ vi điều khiển nào — thêm một phép mới là thêm một dòng ở đây.
CHECKSUMS: dict[str, Callable[[bytes], int]] = {
    "xor8": _xor8,
    "sum8": _sum8,
}


#: Tốc độ truyền mặc định — chỉ là điểm khởi đầu hợp lý khi dự án chưa khai.
#: Định nghĩa một chỗ để không có hai giá trị "mặc định" lệch nhau.
_BAUD_MAC_DINH = 115200


@dataclass(frozen=True)
class FrameSpec:
    """Cách một khung telemetry được đóng gói — do dự án khai."""

    #: ``none`` hoặc một khóa trong :data:`CHECKSUMS`.
    checksum: str = "none"
    #: Ký tự ngăn phần tải với checksum, ví dụ ``{...}*3F``.
    separator: str = "*"
    baud: int = _BAUD_MAC_DINH
    #: Trong khoảng này sau khi mở cổng, khung HỎNG bị bỏ qua lặng lẽ. Mở cổng
    #: nối tiếp làm nhiều bo tự khởi động lại, nên những byte đầu thường là rác
    #: của quá trình khởi động — không phải dấu hiệu đường truyền có vấn đề.
    #:
    #: Chỉ khung hỏng mới bị bỏ. Một khung ĐẠT thì đã là dữ liệu thật, và vứt
    #: nó đi chỉ vì nó tới sớm là mất đúng thứ đang cần đo.
    settle_ms: int = 200
    #: Tỉ lệ khung hỏng vượt ngưỡng này thì cả phiên đo bị coi là không tin được.
    max_bad_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.checksum != "none" and self.checksum not in CHECKSUMS:
            raise TelemetryError(
                f"Phép kiểm tổng {self.checksum!r} không được hỗ trợ "
                f"(đang có: none, {', '.join(sorted(CHECKSUMS))})"
            )
        if self.baud <= 0:
            raise TelemetryError(f"baud phải dương, nhận {self.baud}")

    @classmethod
    def from_dict(cls, du_lieu: Any) -> "FrameSpec":
        if du_lieu is None:
            return cls()
        if not isinstance(du_lieu, dict):
            raise TelemetryError("mục 'telemetry' phải là ánh xạ khóa–giá trị")
        return cls(
            checksum=str(du_lieu.get("checksum", "none")),
            separator=str(du_lieu.get("separator", "*")),
            baud=int(du_lieu.get("baud", _BAUD_MAC_DINH)),
            settle_ms=int(du_lieu.get("settle_ms", 200)),
            max_bad_ratio=float(du_lieu.get("max_bad_ratio", 0.2)),
        )


def load_frame_spec(path: str | Path) -> FrameSpec:
    """Đọc mục ``telemetry`` trong ``diagnostics.yaml`` của dự án."""
    path = Path(path)
    if not path.is_file():
        return FrameSpec()
    try:
        du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TelemetryError(f"{path}: YAML không hợp lệ — {exc}") from exc
    if not isinstance(du_lieu, dict):
        return FrameSpec()
    return FrameSpec.from_dict(du_lieu.get("telemetry"))


@dataclass(frozen=True)
class TelemetryFrame:
    """Một dòng nhận được từ mạch, đã kiểm."""

    raw: str
    payload: str = ""
    ok: bool = False
    reason: str = ""

    @property
    def data(self) -> dict[str, Any]:
        if not self.ok:
            return {}
        try:
            muc = json.loads(self.payload)
        except json.JSONDecodeError:
            return {}
        return muc if isinstance(muc, dict) else {}


def verify_frame(line: str, spec: FrameSpec) -> TelemetryFrame:
    """Tách phần tải khỏi checksum và kiểm — không ném, luôn trả kết quả.

    Trả về khung KHÔNG ĐẠT kèm lý do thay vì ném ngoại lệ: một dòng rác giữa
    phiên đo không được phép làm đứt cả phiên, nhưng cũng không được biến mất
    không dấu vết.
    """
    tho = line.strip()
    if not tho:
        return TelemetryFrame(raw=line, reason="dòng rỗng")

    if spec.checksum == "none":
        payload = tho
    else:
        if spec.separator not in tho:
            return TelemetryFrame(
                raw=line, reason=f"thiếu dấu {spec.separator!r} ngăn checksum"
            )
        payload, _, phan_kiem = tho.rpartition(spec.separator)
        payload = payload.strip()
        try:
            mong_doi = int(phan_kiem.strip(), 16)
        except ValueError:
            return TelemetryFrame(
                raw=line, payload=payload, reason=f"checksum {phan_kiem!r} không phải hex"
            )
        thuc_te = CHECKSUMS[spec.checksum](payload.encode("utf-8"))
        if thuc_te != mong_doi:
            return TelemetryFrame(
                raw=line,
                payload=payload,
                reason=f"checksum lệch: nhận {mong_doi:02X}, tính ra {thuc_te:02X}",
            )

    if not payload.startswith("{"):
        return TelemetryFrame(raw=line, payload=payload, reason="phần tải không phải JSON")
    try:
        json.loads(payload)
    except json.JSONDecodeError as exc:
        return TelemetryFrame(raw=line, payload=payload, reason=f"JSON hỏng — {exc}")

    return TelemetryFrame(raw=line, payload=payload, ok=True)


# --------------------------------------------------------------------------
# Phiên thu
# --------------------------------------------------------------------------


@dataclass
class Capture:
    """Kết quả một phiên thu telemetry."""

    frames: list[TelemetryFrame] = field(default_factory=list)
    port: str = ""
    duration_s: float = 0.0
    spec: FrameSpec = field(default_factory=FrameSpec)

    @property
    def good(self) -> list[TelemetryFrame]:
        return [f for f in self.frames if f.ok]

    @property
    def bad(self) -> list[TelemetryFrame]:
        return [f for f in self.frames if not f.ok]

    @property
    def bad_ratio(self) -> float:
        return len(self.bad) / len(self.frames) if self.frames else 0.0

    @property
    def trustworthy(self) -> bool:
        """Có đủ khung đạt, và tỉ lệ khung hỏng dưới ngưỡng dự án khai."""
        return bool(self.good) and self.bad_ratio <= self.spec.max_bad_ratio

    def stream(self) -> str:
        """Dạng JSON từng dòng — đúng thứ DiagnosticSession.parse_telemetry đọc."""
        return "\n".join(f.payload for f in self.good) + ("\n" if self.good else "")

    def raw_text(self) -> str:
        return "".join(f.raw if f.raw.endswith("\n") else f.raw + "\n" for f in self.frames)

    def write(self, path: str | Path) -> tuple[Path, Path]:
        """Ghi bản đã lọc và bản NGUYÊN VĂN cạnh nhau.

        Bản nguyên văn là bằng chứng: khi một số đo gây tranh cãi, câu "mạch
        thật sự gửi gì" phải trả lời được từ dữ liệu chứ không từ trí nhớ.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.stream(), encoding="utf-8")
        tho = path.with_suffix(path.suffix + ".raw")
        tho.write_text(self.raw_text(), encoding="utf-8")
        return path, tho

    def render(self) -> str:
        dong = [
            f"  Cổng        : {self.port}",
            f"  Thời gian   : {self.duration_s:.1f}s",
            f"  Khung nhận  : {len(self.frames)} ({len(self.good)} đạt, {len(self.bad)} hỏng)",
        ]
        if self.bad:
            dong.append(f"  Tỉ lệ hỏng  : {self.bad_ratio:.0%}")
            ly_do: dict[str, int] = {}
            for f in self.bad:
                ly_do[f.reason] = ly_do.get(f.reason, 0) + 1
            for nguyen_nhan, so in sorted(ly_do.items(), key=lambda x: -x[1])[:3]:
                dong.append(f"      {so}× {nguyen_nhan}")
        if not self.frames:
            dong += [
                "",
                "  Không nhận được gì. Kiểm theo thứ tự:",
                "    · Đã nạp firmware có phát telemetry chưa?",
                "    · Tốc độ truyền hai đầu có khớp không?",
                "    · Dây TX/RX có bị đảo không?",
            ]
        elif not self.trustworthy:
            dong += [
                "",
                "  PHIÊN ĐO KHÔNG TIN ĐƯỢC — quá nhiều khung hỏng.",
                "  Số rút ra từ phiên này không nên đưa vào kết luận: sai tốc độ",
                "  truyền hay nhiễu đường dây vẫn cho ra vài con số trông hợp lý.",
            ]
        return "\n".join(dong)


def read_capture(path: str | Path, spec: FrameSpec | None = None) -> Capture:
    """Đọc lại một bản thu nguyên văn — phát lại không cần mạch.

    Cùng vai trò với ``ReplayClient`` ở tầng mô hình: chạy lại phân tích trên
    đúng dữ liệu đã nhận, không tốn một lần đo nào.
    """
    path = Path(path)
    if not path.is_file():
        raise TelemetryError(f"Không có bản thu: {path}")
    spec = spec or FrameSpec()
    khung = [verify_frame(d, spec) for d in path.read_text(encoding="utf-8").splitlines() if d.strip()]
    return Capture(frames=khung, port=f"(phát lại {path.name})", spec=spec)


@dataclass
class SerialTelemetryReader:
    """Thu telemetry từ một cổng nối tiếp, luôn có hạn thời gian."""

    port: str
    spec: FrameSpec = field(default_factory=FrameSpec)
    #: ``(port, baud, timeout_s) -> đối tượng có readline() và close()``.
    #: Bỏ trống thì dùng pyserial. Tiêm vào được để kiểm thử không cần mạch.
    open_port: Callable[[str, int, float], Any] | None = None
    #: Hạn chờ một dòng. Nhỏ hơn hẳn tổng thời gian để vòng đọc còn kiểm hạn.
    line_timeout_s: float = 0.5

    def read(self, *, duration_s: float = 5.0, max_frames: int = 0) -> Capture:
        if duration_s <= 0:
            raise TelemetryError("duration_s phải dương — đọc không hạn sẽ treo mãi")

        mo = self.open_port or _mo_bang_pyserial
        cong = mo(self.port, self.spec.baud, self.line_timeout_s)

        khung: list[TelemetryFrame] = []
        bat_dau = time.monotonic()
        het_on_dinh = bat_dau + self.spec.settle_ms / 1000.0
        try:
            while time.monotonic() - bat_dau < duration_s:
                dong = cong.readline()
                if isinstance(dong, bytes):
                    dong = dong.decode("utf-8", errors="replace")
                if not dong:
                    continue
                da_kiem = verify_frame(dong, self.spec)
                # Giai đoạn bo tự khởi động lại: bỏ rác, GIỮ dữ liệu thật.
                if not da_kiem.ok and time.monotonic() < het_on_dinh:
                    continue
                khung.append(da_kiem)
                if max_frames and len([f for f in khung if f.ok]) >= max_frames:
                    break
        finally:
            dong_lai = getattr(cong, "close", None)
            if callable(dong_lai):
                dong_lai()

        return Capture(
            frames=khung,
            port=self.port,
            duration_s=time.monotonic() - bat_dau,
            spec=self.spec,
        )


def _mo_bang_pyserial(port: str, baud: int, timeout_s: float) -> Any:
    try:
        import serial
    except ImportError as exc:
        raise TelemetryError(
            "Đọc telemetry từ mạch cần pyserial:\n"
            "    pip install pyserial\n"
            "Không có nó thì vẫn phân tích được bản thu sẵn "
            "('eaa diagnose run --telemetry <tệp>'), nhưng không đọc thẳng từ mạch."
        ) from exc
    try:
        return serial.Serial(port, baudrate=baud, timeout=timeout_s)
    except Exception as exc:  # serial.SerialException và họ hàng
        raise TelemetryError(
            f"Không mở được cổng {port!r} ở {baud} baud — {exc}\n"
            "Xem 'eaa ports' để biết máy đang thấy cổng nào."
        ) from exc
