"""Từ số đo trên mạch tới hạng ``hw-verified`` — khép vòng nghiệm thu.

EAA-AIS-05 §8.4 (ba hạng chất lượng, `known_good.lock`), EAA-SRS-01 FR-VER-01,
UC07. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-36.

Ba hạng chất lượng đã có từ Sprint 4: ``build-ok`` máy tự chấm, ``sim-verified``
máy tự chấm, ``hw-verified`` thì không — nó khẳng định một điều về thế giới vật
lý. Nhưng "khẳng định về thế giới vật lý" tới giờ vẫn là một tệp YAML người tự
gõ, và một tệp tự gõ thì khẳng định được bất cứ điều gì.

Module này nối số đo thật vào chỗ ấy, và dựng ba chốt quanh nó.

Chốt 1 — commit đang phong hạng phải là commit ĐANG CHẠY trên thiết bị
----------------------------------------------------------------------

Đây là chốt quan trọng nhất của cả bước này. Không có nó, quy trình cho phép:
nạp bản A, đo bản A, rồi sửa mã thành bản B và phong hạng ``hw-verified`` cho
B. Bản B chưa bao giờ chạy trên phần cứng, mà `known_good.lock` sẽ nói ngược
lại — và `known_good.lock` là thứ mọi lần quay lui về sau tin theo.

Nhật ký nạp đã ghi sẵn commit nào lên thiết bị nào lúc nào, nên phép so này
không tốn gì ngoài việc chịu nhìn.

**Nhưng "thiếu bằng chứng" và "bằng chứng nói ngược lại" là hai chuyện khác
nhau, và đối xử với chúng như nhau là sai.** Nhật ký ghi rõ bản A đang trên
chip mà ta đòi phong hạng cho bản B — đó là mâu thuẫn, và mâu thuẫn thì CHẶN.
Nhật ký trống, vì kỹ sư nạp bằng công cụ của hãng hay bằng một IDE — đó chỉ là
engine không biết, và engine không biết thì nó nói là nó không biết chứ không
cấm người làm việc. Bản ghi phong hạng mang theo cờ ``device_verified`` để câu
"lần ấy có kiểm được không" tra lại được, thay vì phải nhớ.

Chốt 2 — số đo đã khai mà telemetry không có là LỖI
----------------------------------------------------

Không phải "bỏ qua mục ấy". Một bản ghi nghiệm thu có 2 trong 5 số đo trông y
hệt một bản có đủ 5, trừ khi ai đó ngồi đếm. Thiếu thì nói thiếu.

Chốt 3 — vượt ngưỡng thì KHÔNG phong hạng
------------------------------------------

Số đo nằm ngoài ngưỡng dự án khai là kết quả "không đạt", và đường đi của nó là
``eaa tune --reject`` chứ không phải ``promote``. Engine không tự quyết định
thay người, nhưng cũng không lặng lẽ ghi một bản không đạt thành đạt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "AcceptanceError",
    "DeviceCheck",
    "MeasurementSpec",
    "AcceptanceSpec",
    "DerivedMeasurements",
    "derive_measurements",
    "check_device_commit",
]


class AcceptanceError(Exception):
    """Khai báo nghiệm thu sai, hoặc số đo không dùng được."""


@dataclass(frozen=True)
class MeasurementSpec:
    """Một số đo dự án chờ đợi ở kỳ nghiệm thu, và lấy nó từ đâu."""

    name: str
    #: Khóa trong telemetry. Bỏ trống thì lấy chính ``name``.
    key: str = ""
    unit: str = ""
    #: Ngưỡng đạt. Bỏ trống cả hai thì số đo chỉ được GHI NHẬN, không chấm.
    low: float | None = None
    high: float | None = None
    note: str = ""

    @property
    def telemetry_key(self) -> str:
        return self.key or self.name

    @property
    def scored(self) -> bool:
        return self.low is not None or self.high is not None

    def violation(self, value: float) -> str:
        """Câu mô tả vi phạm, hoặc chuỗi rỗng nếu đạt."""
        if self.high is not None and value > self.high:
            return f"{self.name} = {value:g}{self.unit} vượt trần {self.high:g}{self.unit}"
        if self.low is not None and value < self.low:
            return f"{self.name} = {value:g}{self.unit} dưới sàn {self.low:g}{self.unit}"
        return ""

    @classmethod
    def from_dict(cls, d: Any) -> "MeasurementSpec":
        if not isinstance(d, dict) or not d.get("name"):
            raise AcceptanceError(f"mục số đo nghiệm thu thiếu 'name': {d!r}")
        return cls(
            name=str(d["name"]),
            key=str(d.get("key", "")),
            unit=str(d.get("unit", "")),
            low=_so(d.get("min")),
            high=_so(d.get("max")),
            note=str(d.get("note", "")),
        )


def _so(gia_tri: Any) -> float | None:
    if gia_tri is None or isinstance(gia_tri, bool):
        return None
    try:
        return float(gia_tri)
    except (TypeError, ValueError):
        raise AcceptanceError(f"ngưỡng nghiệm thu không phải số: {gia_tri!r}") from None


@dataclass(frozen=True)
class AcceptanceSpec:
    """Phần ``acceptance.measurements`` của ``constraints.yaml``."""

    measurements: tuple[MeasurementSpec, ...] = ()

    @classmethod
    def from_acceptance(cls, acceptance: Mapping[str, Any] | None) -> "AcceptanceSpec":
        muc = (acceptance or {}).get("measurements") or []
        if not isinstance(muc, list):
            raise AcceptanceError("'acceptance.measurements' phải là một danh sách")
        return cls(tuple(MeasurementSpec.from_dict(m) for m in muc))

    def __bool__(self) -> bool:
        return bool(self.measurements)


@dataclass
class DerivedMeasurements:
    """Kết quả rút số đo từ một phiên thu telemetry."""

    measurements: list[Any] = field(default_factory=list)
    #: Số đo đã khai mà telemetry không có, hoặc có nhưng không phải số.
    missing: list[str] = field(default_factory=list)
    #: Số đo vượt ngưỡng dự án khai.
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.measurements) and not self.missing and not self.violations

    def render(self) -> str:
        dong = [f"  {m}" for m in self.measurements]
        if self.missing:
            dong += ["", "  THIẾU số đo đã khai:"]
            dong += [f"    · {t}" for t in self.missing]
            dong += [
                "  Một bản ghi nghiệm thu thiếu số đo trông y hệt một bản đủ,",
                "  trừ khi có người ngồi đếm — nên thiếu thì dừng.",
            ]
        if self.violations:
            dong += ["", "  KHÔNG ĐẠT ngưỡng:"]
            dong += [f"    · {v}" for v in self.violations]
            dong += [
                "  Đây là kết quả 'không đạt', và đường đi của nó là",
                "  'eaa tune <module> --reject \"<lý do>\"'.",
            ]
        return "\n".join(dong)


def derive_measurements(
    telemetry: Mapping[str, Any], spec: AcceptanceSpec
) -> DerivedMeasurements:
    """Rút số đo từ telemetry theo đúng những gì dự án đã khai."""
    from eaa.versions import Measurement

    if not spec:
        raise AcceptanceError(
            "constraints.yaml chưa khai 'acceptance.measurements', nên engine "
            "không biết số nào trong telemetry là số đo nghiệm thu.\n"
            "Nghiệm thu là đối chiếu hành vi thật với tiêu chí đã chốt từ công "
            "đoạn A1 — tiêu chí phải có trước, không suy ra từ dữ liệu."
        )

    ket_qua = DerivedMeasurements()
    for m in spec.measurements:
        if m.telemetry_key not in telemetry:
            ket_qua.missing.append(f"{m.name} (telemetry không có {m.telemetry_key!r})")
            continue

        gia_tri = telemetry[m.telemetry_key]
        if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
            ket_qua.missing.append(
                f"{m.name}: telemetry trả {gia_tri!r}, không phải số đo được"
            )
            continue

        so = float(gia_tri)
        ket_qua.measurements.append(
            Measurement(name=m.name, value=so, unit=m.unit, note=m.note)
        )
        vi_pham = m.violation(so)
        if vi_pham:
            ket_qua.violations.append(vi_pham)

    return ket_qua


@dataclass(frozen=True)
class DeviceCheck:
    """Kết quả đối chiếu commit sắp phong hạng với nhật ký nạp."""

    verified: bool
    #: Có mâu thuẫn tới mức phải dừng không.
    blocking: bool = False
    message: str = ""

    def __bool__(self) -> bool:
        return self.verified


def check_device_commit(head_commit: str, flash_log: Any) -> DeviceCheck:
    """Commit sắp phong hạng có đúng là commit đang chạy trên thiết bị không.

    Ba kết cục, và ranh giới giữa hai kết cục sau là điều đáng nói:

    * **Khớp** — có bằng chứng, đi tiếp.
    * **Lệch** — nhật ký nói bản khác đang trên chip. Đây là MÂU THUẪN, và
      mâu thuẫn thì chặn.
    * **Trống** — engine không biết bản nào đang trên chip, vì kỹ sư nạp bằng
      đường khác. Đây là THIẾU BIẾT, không phải mâu thuẫn; engine nói rõ mình
      không kiểm được rồi để người quyết, chứ không cấm người làm việc.
    """
    lan_cuoi = flash_log.last_success() if flash_log is not None else None
    if lan_cuoi is None:
        return DeviceCheck(
            verified=False,
            blocking=False,
            message=(
                "Chưa lần nạp nào thành công được ghi lại, nên engine KHÔNG kiểm "
                "được bản này có đang chạy trên thiết bị hay không.\n"
                "    Bản ghi phong hạng sẽ mang device_verified=false.\n"
                "    Muốn kiểm được: nạp qua 'eaa flash' rồi đo bằng "
                "'eaa tune ... --port <cổng>'."
            ),
        )
    if lan_cuoi.commit != head_commit:
        return DeviceCheck(
            verified=False,
            blocking=True,
            message=(
                f"Commit đang phong hạng ({head_commit[:10]}) KHÁC commit đang chạy "
                f"trên thiết bị ({lan_cuoi.commit[:10]}, nạp lúc {lan_cuoi.flashed_at}).\n"
                "    Hạng hw-verified khẳng định một điều về phần cứng; khẳng định ấy "
                "chỉ đúng cho đúng bản đã chạy trên phần cứng.\n"
                "    Nạp lại bản hiện tại rồi đo: 'eaa flash'"
            ),
        )
    return DeviceCheck(verified=True)
