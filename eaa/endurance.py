"""Kiểm độ bền dài hạn — N-086.

EAA-SRS-01 FR-DIA-03, tiêu chí `uptime_s ≥ 600` ở `constraints.yaml`; công
đoạn G8. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-55.

Ba thứ chỉ lộ ra khi chạy dài
------------------------------

1. **Reset ngầm.** Thiết bị khởi động lại rồi chạy tiếp; nếu không ai nhìn đúng
   lúc ấy thì phiên đo trông vẫn liền mạch. Dấu vết duy nhất là bộ đếm thời
   gian chạy NHẢY VỀ GẦN 0 — và dấu vết ấy chỉ đọc được nếu có ai đi tìm nó.
2. **Trôi.** Một đại lượng lệch dần theo thời gian: trôi điểm không, tích lũy
   sai số, nhiệt độ tăng dần. Đo trong một phút không thấy gì.
3. **Rò bộ nhớ.** Vùng nhớ tự do giảm đều. Trên hệ nhúng nó không cần nhiều
   giờ mới hạ gục thiết bị, nhưng cần nhiều giờ mới NHÌN THẤY được.

Điều bất biến của module này
-----------------------------

**Nó không suy rộng.** Chạy 10 phút thì kết luận chỉ nói về 10 phút. Cám dỗ ở
đây rất mạnh: một phiên 10 phút sạch sẽ trông y hệt bằng chứng cho 10 giờ, và
người đọc sẽ mang cảm giác ấy đi. Nên mọi báo cáo ở đây mở đầu bằng thời gian
đã quan sát THẬT, và nếu nó ngắn hơn yêu cầu thì câu đầu tiên nói ra điều đó —
trước cả khi nói mọi thứ đều tốt.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "EnduranceError",
    "ResetEvent",
    "DriftReport",
    "EnduranceReport",
    "analyse",
]

#: Bộ đếm thời gian chạy phải TỤT ít nhất chừng này thì mới coi là reset. Một
#: chút xáo trộn thứ tự khung (đệm nối tiếp, khung tới trễ) không được đọc
#: thành một lần khởi động lại — báo động giả thì người ta học cách phớt lờ.
NGUONG_TUT_S = 1.0


class EnduranceError(Exception):
    """Không phân tích được phiên chạy dài."""


def _so(gia_tri: Any) -> float | None:
    if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
        return None
    if not math.isfinite(float(gia_tri)):
        return None
    return float(gia_tri)


@dataclass(frozen=True)
class ResetEvent:
    """Một lần bộ đếm thời gian chạy tụt về gần 0 — dấu vết của reset."""

    frame_index: int
    before_s: float
    after_s: float

    def render(self) -> str:
        return (
            f"  khung #{self.frame_index}: thời gian chạy {self.before_s:g}s → "
            f"{self.after_s:g}s (tụt {self.before_s - self.after_s:g}s)"
        )


@dataclass(frozen=True)
class DriftReport:
    """Một đại lượng có trôi theo thời gian không."""

    key: str
    first: float
    last: float
    minimum: float
    maximum: float
    samples: int
    span_s: float

    @property
    def delta(self) -> float:
        return self.last - self.first

    @property
    def per_hour(self) -> float | None:
        """Tốc độ trôi quy về mỗi giờ. ``None`` khi khoảng quan sát quá ngắn.

        Quy đổi từ một khoảng ngắn ra tốc độ mỗi giờ là phép ngoại suy, và
        ngoại suy từ 30 giây lên một giờ là nhân sai số lên 120 lần. Dưới một
        phút thì không quy đổi — nói là chưa đủ dữ liệu.
        """
        if self.span_s < 60.0:
            return None
        return self.delta / self.span_s * 3600.0

    def render(self) -> str:
        dong = (
            f"  {self.key}: {self.first:g} → {self.last:g} "
            f"(lệch {self.delta:+g}; dải {self.minimum:g}…{self.maximum:g}, "
            f"{self.samples} mẫu)"
        )
        toc_do = self.per_hour
        if toc_do is None:
            dong += "\n      chưa quy được tốc độ trôi: quan sát dưới 1 phút"
        else:
            dong += f"\n      tốc độ trôi ≈ {toc_do:+.4g}/giờ"
        return dong


@dataclass
class EnduranceReport:
    """Kết quả một phiên chạy dài."""

    #: Thời gian thiết bị TỰ BÁO đã chạy, lấy từ bộ đếm — không phải thời gian
    #: máy tính ngồi nghe. Hai con số này lệch nhau khi có reset.
    observed_s: float = 0.0
    #: Thời gian phiên thu kéo dài, đo ở phía máy tính.
    capture_s: float = 0.0
    required_s: float = 0.0
    frames: int = 0
    resets: tuple[ResetEvent, ...] = ()
    drifts: tuple[DriftReport, ...] = ()
    bad_ratio: float = 0.0
    uptime_key: str = "uptime_s"
    #: Bộ đếm thời gian chạy có mặt trong telemetry không.
    uptime_present: bool = True

    @property
    def long_enough(self) -> bool:
        return self.required_s <= 0 or self.observed_s >= self.required_s

    @property
    def ok(self) -> bool:
        return self.long_enough and not self.resets and self.uptime_present

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import DA_KIEM, GIA_DINH, KHONG_KIEM_DUOC

        if not self.uptime_present:
            return KHONG_KIEM_DUOC
        if not self.long_enough:
            # Chạy chưa đủ lâu KHÔNG phải là không kiểm được — nó kiểm được,
            # chỉ là chưa ai bỏ thời gian ra. Hai việc phải làm khác hẳn nhau.
            return GIA_DINH
        return DA_KIEM

    def verdict(self) -> str:
        """Câu đầu tiên, và nó luôn nói về THỜI GIAN trước khi nói về kết quả."""
        if not self.uptime_present:
            return (
                f"KHÔNG KẾT LUẬN ĐƯỢC — telemetry không có trường {self.uptime_key!r}, "
                "nên không cách nào phát hiện thiết bị đã khởi động lại giữa chừng.\n"
                "    Một phiên có reset trông y hệt một phiên liền mạch nếu không "
                "ai đi tìm dấu vết ấy."
            )
        if self.resets:
            return (
                f"KHÔNG ĐẠT — phát hiện {len(self.resets)} lần khởi động lại trong "
                f"{self.observed_s:g}s quan sát."
            )
        if not self.long_enough:
            return (
                f"CHƯA KẾT LUẬN ĐƯỢC — mới chạy {self.observed_s:g}s, yêu cầu "
                f"{self.required_s:g}s.\n"
                "    Sạch trong quãng đã chạy KHÔNG suy ra được sạch trong quãng "
                "chưa chạy: 10 phút không nói gì về 10 giờ."
            )
        return f"ĐẠT — {self.observed_s:g}s liên tục, không lần nào khởi động lại."

    def render(self) -> str:
        dong = ["Kiểm độ bền dài hạn", "", self.verdict(), ""]
        dong.append(f"  Thiết bị tự báo đã chạy : {self.observed_s:g}s")
        dong.append(f"  Phiên thu kéo dài       : {self.capture_s:g}s")
        dong.append(f"  Khung nhận              : {self.frames}")
        if self.bad_ratio:
            dong.append(f"  Tỉ lệ khung hỏng        : {self.bad_ratio:.0%}")

        if self.resets:
            dong += ["", "Lần khởi động lại phát hiện được:"]
            dong += [r.render() for r in self.resets]
            dong += [
                "",
                "  Reset giữa phiên đo làm mọi số liệu sau đó thuộc về một lượt",
                "  chạy KHÁC. Tìm nguyên nhân trước khi đo lại: 'eaa diagnose run DS-05'",
                "  kiểm sụt áp dưới tải, kịch bản hay đứng sau reset ngẫu nhiên nhất.",
            ]

        if self.drifts:
            dong += ["", "Trôi theo thời gian:"]
            dong += [d.render() for d in self.drifts]

        if self.long_enough and not self.resets:
            dong += [
                "",
                f"  Kết luận này chỉ nói về {self.observed_s:g}s đã quan sát.",
                "  Muốn nói về một quãng dài hơn thì phải chạy quãng dài hơn.",
            ]
        return "\n".join(dong)


def analyse(
    capture: Any,
    *,
    uptime_key: str = "uptime_s",
    required_s: float = 0.0,
    drift_keys: Sequence[str] = (),
) -> EnduranceReport:
    """Phân tích một phiên thu telemetry dài (N-086).

    ``capture`` là ``eaa.telemetry.Capture``, hoặc bất cứ vật nào có ``good``
    (danh sách khung đạt, mỗi khung có ``payload`` JSON) và ``duration_s``.

    Cách phát hiện reset: bộ đếm thời gian chạy là đại lượng ĐƠN ĐIỆU TĂNG khi
    thiết bị còn chạy. Nó tụt xuống nghĩa là con chip đã khởi động lại — không
    có cách nào khác để một bộ đếm đi lùi. Đây là bằng chứng trực tiếp, khác
    hẳn việc suy từ một khoảng lặng trên đường truyền (khoảng lặng cũng có thể
    do rút dây).
    """
    khung_tot = list(getattr(capture, "good", []) or [])
    ban_ghi: list[dict[str, Any]] = []
    for f in khung_tot:
        try:
            du_lieu = json.loads(getattr(f, "payload", "") or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(du_lieu, dict):
            ban_ghi.append(du_lieu)

    co_uptime = any(uptime_key in d for d in ban_ghi)

    resets: list[ResetEvent] = []
    truoc: float | None = None
    cao_nhat = 0.0
    for i, d in enumerate(ban_ghi):
        gia_tri = _so(d.get(uptime_key))
        if gia_tri is None:
            continue
        if truoc is not None and gia_tri < truoc - NGUONG_TUT_S:
            resets.append(ResetEvent(frame_index=i, before_s=truoc, after_s=gia_tri))
        truoc = gia_tri
        cao_nhat = max(cao_nhat, gia_tri)

    troi: list[DriftReport] = []
    for khoa in drift_keys:
        gia_tri = [v for d in ban_ghi if (v := _so(d.get(khoa))) is not None]
        if len(gia_tri) < 2:
            continue
        troi.append(
            DriftReport(
                key=khoa,
                first=gia_tri[0],
                last=gia_tri[-1],
                minimum=min(gia_tri),
                maximum=max(gia_tri),
                samples=len(gia_tri),
                span_s=cao_nhat or float(getattr(capture, "duration_s", 0.0) or 0.0),
            )
        )

    return EnduranceReport(
        # Thời gian quan sát lấy theo bộ đếm CAO NHẤT thấy được, không lấy tổng
        # cộng dồn qua các lần reset: sau một lần khởi động lại thì "đã chạy
        # liên tục bao lâu" bắt đầu đếm lại từ đầu, và đó đúng là điều tiêu chí
        # uptime_s muốn hỏi.
        observed_s=cao_nhat,
        capture_s=float(getattr(capture, "duration_s", 0.0) or 0.0),
        required_s=required_s,
        frames=len(getattr(capture, "frames", []) or []),
        resets=tuple(resets),
        drifts=tuple(troi),
        bad_ratio=float(getattr(capture, "bad_ratio", 0.0) or 0.0),
        uptime_key=uptime_key,
        uptime_present=co_uptime,
    )
