"""Ngân sách tài nguyên — chia TRƯỚC khi viết mã, không đo sau.

Nghiệp vụ N-015 (chia ngân sách flash/RAM/CPU theo module), N-071 (khoảng
trống ngăn xếp ở tầm firmware), N-904 (trần token và chi phí theo module).
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-46.

Vì sao ba việc ấy nằm chung một tệp
------------------------------------

Chúng là cùng một hình dạng: một nguồn lực có hạn, chia thành phần cho từng
module, rồi đối chiếu phần đã dùng với phần được chia. Bộ nhớ chương trình,
bộ nhớ dữ liệu, và token gọi mô hình khác nhau ở đơn vị chứ không khác nhau ở
cách quản. Tách ba tệp thì luật "cảnh báo khi một module ăn quá phần của nó"
phải viết ba lần, và ba lần viết là ba cơ hội để chúng lệch nhau.

Điều mà cổng kích thước hiện có KHÔNG trả lời được
---------------------------------------------------

``SizeGate`` đối chiếu số đo với trần TỔNG (``flash_pct_max``). Phép kiểm ấy
đúng nhưng dễ dãi hơn nó trông: mỗi module lẻ đều "dưới 50%", và người ta chỉ
biết mình đã tiêu hết chỗ vào lúc liên kết — tức là vào lúc muộn nhất, khi mọi
module đã viết xong và việc cắt bớt trở thành viết lại.

Chia ngân sách trước thì câu hỏi đổi từ *"còn chỗ không?"* thành *"module này
có ở trong phần của nó không?"*, và câu sau trả lời được ngay ở module đầu
tiên.

Engine không biết đơn vị nào là gì
-----------------------------------

``flash_bytes``, ``sram_bytes`` là tên số liệu do **pack** đặt; dung lượng chip
là con số do **dự án** khai. Engine chỉ cộng, chia và so sánh. Nhờ vậy một nền
tảng có ba vùng nhớ, hay một dự án muốn chia cả ngân sách năng lượng, đều dùng
lại đúng bộ khung này mà không sửa một dòng engine (FR-PLT-01).

Số liệu suy ra (N-071)
-----------------------

Khoảng trống ngăn xếp không phải thứ công cụ đo kích thước in ra; nó là *dung
lượng trừ đi phần đã dùng*. Nên nó được khai như một số liệu SUY RA — dự án nói
"lấy khóa dung lượng nào trừ khóa số đo nào, gọi kết quả là tên gì" — rồi từ
đó nó đi qua đúng cơ chế ngưỡng ``_min`` như mọi số liệu khác. Không có mục
này thì dòng ``stack_headroom_bytes`` trong ``constraints.yaml`` chỉ là một
dòng chữ: có khai, không ai thi hành.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "BudgetError",
    "Allotment",
    "DerivedMetric",
    "ResourceBudget",
    "MetricUsage",
    "ModuleBudgetCheck",
    "TokenBudget",
    "TokenUsage",
    "TokenBudgetCheck",
    "propose_split",
    "spent_tokens",
    "TRONG_PHAN",
    "SAP_CHAM",
    "VUOT_PHAN",
]

#: Đang ở trong phần được chia.
TRONG_PHAN = "trong-phan"
#: Đã dùng quá ngưỡng cảnh báo nhưng chưa vượt phần.
SAP_CHAM = "sap-cham-tran"
#: Đã ăn quá phần của mình.
VUOT_PHAN = "vuot-phan"

#: Dùng bao nhiêu phần trăm phần được chia thì bắt đầu cảnh báo. Cảnh báo sớm
#: có giá trị đúng ở chỗ nó còn kịp: biết một module đã tiêu 85% phần của nó
#: khi mã mới viết được nửa thì còn đổi hướng được.
WARN_AT_PCT_DEFAULT = 80.0

#: Phần dung lượng chip cố ý không chia cho ai. Bản vá về sau, mã khởi động,
#: và những thứ chưa ai nghĩ tới đều lấy từ đây.
RESERVE_PCT_DEFAULT = 20.0


class BudgetError(Exception):
    """Khai báo ngân sách sai lược đồ, hoặc tự mâu thuẫn."""


def _so(gia_tri: Any) -> float | None:
    if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
        return None
    return float(gia_tri)


# --------------------------------------------------------------------------
# Ngân sách tài nguyên (N-015, N-071)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Allotment:
    """Phần tài nguyên chia cho một module."""

    module: str
    #: tên số liệu (do pack đặt) → trần của module này, cùng đơn vị pack đo.
    limits: dict[str, float] = field(default_factory=dict)
    note: str = ""

    def cap(self, metric: str) -> float | None:
        return self.limits.get(metric)


@dataclass(frozen=True)
class DerivedMetric:
    """Một số liệu engine tính ra, không phải số liệu công cụ in ra (N-071).

    ``name = capacity[capacity_key] - metrics[used_key]``. Chỉ một phép trừ,
    nhưng nó là phép trừ biến một ngưỡng khai suông thành một ngưỡng thi hành
    được.
    """

    name: str
    capacity_key: str
    used_key: str


@dataclass(frozen=True)
class MetricUsage:
    """Một số liệu của một module, đặt cạnh phần nó được chia."""

    metric: str
    used: float
    cap: float | None
    status: str

    @property
    def pct(self) -> float | None:
        if not self.cap:
            return None
        return round(self.used / self.cap * 100.0, 1)

    def render(self) -> str:
        if self.cap is None:
            return f"  {self.metric:<20} {self.used:>10,.0f}   (chưa chia phần)"
        nhan = {TRONG_PHAN: "", SAP_CHAM: "  ← sắp chạm", VUOT_PHAN: "  ← VƯỢT PHẦN"}
        return (
            f"  {self.metric:<20} {self.used:>10,.0f} / {self.cap:>10,.0f}"
            f"  ({self.pct:>5.1f}%){nhan[self.status]}"
        )


@dataclass
class ModuleBudgetCheck:
    """Kết quả đối chiếu số đo của một module với phần nó được chia."""

    module: str
    usages: list[MetricUsage] = field(default_factory=list)

    @property
    def over(self) -> list[MetricUsage]:
        return [u for u in self.usages if u.status == VUOT_PHAN]

    @property
    def warnings(self) -> list[MetricUsage]:
        return [u for u in self.usages if u.status == SAP_CHAM]

    @property
    def ok(self) -> bool:
        return not self.over

    def render(self) -> str:
        if not self.usages:
            return f"{self.module}: chưa có số đo nào để đối chiếu ngân sách."
        dong = [f"Ngân sách module {self.module}:"]
        dong += [u.render() for u in self.usages]
        if self.over:
            dong.append(
                "\nModule này ăn quá phần đã chia. Ba lối, và cả ba đều là quyết "
                "định của người:\n"
                "  · cắt bớt mã cho vừa phần,\n"
                "  · lấy thêm từ dự phòng (sửa 'budget' trong constraints.yaml, "
                "duyệt lại tại G1),\n"
                "  · nhận là bản chia ban đầu sai và chia lại."
            )
        return "\n".join(dong)


@dataclass(frozen=True)
class ResourceBudget:
    """Bản chia ngân sách của một dự án, đọc từ ``constraints.yaml``."""

    #: tên khóa dung lượng → tổng dung lượng chip. Do dự án khai.
    capacity: dict[str, float] = field(default_factory=dict)
    reserve_pct: float = RESERVE_PCT_DEFAULT
    allotments: tuple[Allotment, ...] = ()
    derived: tuple[DerivedMetric, ...] = ()
    warn_at_pct: float = WARN_AT_PCT_DEFAULT

    # -- đọc khai báo -------------------------------------------------------

    @classmethod
    def from_constraints(cls, constraints: Any) -> "ResourceBudget | None":
        """Đọc khối ``budget`` của ``constraints.yaml``. Không khai thì trả None.

        Không khai KHÔNG phải lỗi: một dự án nhỏ có thể chỉ cần trần tổng. Lỗi
        là khai nửa vời — và những cái nửa vời ấy được bắt ở đây chứ không để
        lộ ra giữa một vòng sinh mã.
        """
        raw = (getattr(constraints, "raw", None) or {}).get("budget")
        if not raw:
            return None
        if not isinstance(raw, dict):
            raise BudgetError("'budget' trong constraints.yaml phải là ánh xạ khóa–giá trị")

        dung_luong: dict[str, float] = {}
        for khoa, gia_tri in (raw.get("capacity") or {}).items():
            so = _so(gia_tri)
            if so is None or so <= 0:
                raise BudgetError(
                    f"budget.capacity[{khoa!r}] phải là số dương, nhận {gia_tri!r}"
                )
            dung_luong[str(khoa)] = so

        phan_chia: list[Allotment] = []
        modules_raw = raw.get("modules") or {}
        if not isinstance(modules_raw, dict):
            raise BudgetError("'budget.modules' phải là ánh xạ module → phần được chia")
        for ten, than in modules_raw.items():
            if not isinstance(than, dict):
                raise BudgetError(f"budget.modules[{ten!r}] phải là ánh xạ")
            gioi_han: dict[str, float] = {}
            for khoa, gia_tri in than.items():
                if khoa == "note":
                    continue
                so = _so(gia_tri)
                if so is None or so < 0:
                    raise BudgetError(
                        f"budget.modules[{ten!r}][{khoa!r}] phải là số không âm, "
                        f"nhận {gia_tri!r}"
                    )
                gioi_han[str(khoa)] = so
            phan_chia.append(
                Allotment(module=str(ten), limits=gioi_han, note=str(than.get("note", "")))
            )

        suy_ra: list[DerivedMetric] = []
        for ten, than in (raw.get("derived") or {}).items():
            if not isinstance(than, dict) or not than.get("capacity") or not than.get("used"):
                raise BudgetError(
                    f"budget.derived[{ten!r}] phải nêu cả 'capacity' và 'used' — "
                    "engine không đoán số liệu nào trừ số liệu nào."
                )
            khoa_dl = str(than["capacity"])
            if khoa_dl not in dung_luong:
                raise BudgetError(
                    f"budget.derived[{ten!r}].capacity = {khoa_dl!r} không có trong "
                    f"budget.capacity (đang có: {sorted(dung_luong)})"
                )
            suy_ra.append(
                DerivedMetric(name=str(ten), capacity_key=khoa_dl, used_key=str(than["used"]))
            )

        du_phong = _so(raw.get("reserve_pct", RESERVE_PCT_DEFAULT))
        if du_phong is None or not 0 <= du_phong < 100:
            raise BudgetError(
                f"budget.reserve_pct phải trong [0, 100), nhận {raw.get('reserve_pct')!r}"
            )
        canh_bao = _so(raw.get("warn_at_pct", WARN_AT_PCT_DEFAULT))
        if canh_bao is None or not 0 < canh_bao <= 100:
            raise BudgetError(
                f"budget.warn_at_pct phải trong (0, 100], nhận {raw.get('warn_at_pct')!r}"
            )

        return cls(
            capacity=dung_luong,
            reserve_pct=du_phong,
            allotments=tuple(phan_chia),
            derived=tuple(suy_ra),
            warn_at_pct=canh_bao,
        )

    # -- tra cứu ------------------------------------------------------------

    def for_module(self, module: str) -> Allotment | None:
        for a in self.allotments:
            if a.module == module:
                return a
        return None

    def metrics(self) -> tuple[str, ...]:
        """Mọi số liệu có ít nhất một module được chia phần."""
        ten: list[str] = []
        for a in self.allotments:
            for k in a.limits:
                if k not in ten:
                    ten.append(k)
        return tuple(ten)

    def usable(self, metric: str) -> float | None:
        """Dung lượng thật sự đem chia — đã trừ dự phòng."""
        tong = self.capacity.get(metric)
        if tong is None:
            return None
        return tong * (100.0 - self.reserve_pct) / 100.0

    def allotted(self, metric: str) -> float:
        return sum(a.limits.get(metric, 0.0) for a in self.allotments)

    # -- kiểm ---------------------------------------------------------------

    def validate(self) -> list[str]:
        """Bản chia có tự mâu thuẫn không: tổng phần chia vượt dung lượng dùng được.

        Đây là phép kiểm rẻ nhất và bắt được lỗi đắt nhất — một bản chia cộng
        lại đã quá chỗ thì mọi module đều có thể "trong phần của mình" mà
        firmware vẫn không nạp nổi.
        """
        van_de: list[str] = []

        for metric in self.metrics():
            dung_duoc = self.usable(metric)
            if dung_duoc is None:
                van_de.append(
                    f"Số liệu {metric!r} có module được chia phần nhưng "
                    f"budget.capacity không khai dung lượng cho nó — phần chia ấy "
                    "không đối chiếu được với cái gì."
                )
                continue
            tong = self.allotted(metric)
            if tong > dung_duoc:
                van_de.append(
                    f"Tổng phần chia cho {metric!r} là {tong:,.0f}, vượt dung lượng "
                    f"dùng được {dung_duoc:,.0f} "
                    f"(= {self.capacity[metric]:,.0f} trừ {self.reserve_pct:g}% dự phòng). "
                    "Bản chia này không thể đúng cho mọi module cùng lúc."
                )

        trung = [
            m for m in {a.module for a in self.allotments}
            if sum(1 for a in self.allotments if a.module == m) > 1
        ]
        for m in sorted(trung):
            van_de.append(f"Module {m!r} được khai phần hai lần trong budget.modules.")

        return van_de

    def derive(self, metrics: Mapping[str, Any]) -> dict[str, float]:
        """Tính các số liệu suy ra từ dung lượng và số đo (N-071)."""
        ket_qua: dict[str, float] = {}
        for d in self.derived:
            da_dung = _so(metrics.get(d.used_key))
            if da_dung is None:
                continue
            ket_qua[d.name] = self.capacity[d.capacity_key] - da_dung
        return ket_qua

    def check_module(self, module: str, metrics: Mapping[str, Any]) -> ModuleBudgetCheck:
        """Đối chiếu số đo của một module với phần nó được chia."""
        phan = self.for_module(module)
        ket = ModuleBudgetCheck(module=module)

        quan_tam = list(self.metrics())
        for ten in quan_tam:
            do_duoc = _so(metrics.get(ten))
            if do_duoc is None:
                continue
            tran = phan.cap(ten) if phan else None
            if tran is None:
                trang_thai = TRONG_PHAN
            elif do_duoc > tran:
                trang_thai = VUOT_PHAN
            elif tran and do_duoc >= tran * self.warn_at_pct / 100.0:
                trang_thai = SAP_CHAM
            else:
                trang_thai = TRONG_PHAN
            ket.usages.append(
                MetricUsage(metric=ten, used=do_duoc, cap=tran, status=trang_thai)
            )
        return ket

    def render(self) -> str:
        dong = ["Ngân sách tài nguyên — chia trước khi viết mã (N-015)", ""]
        # Nêu cả số liệu đã khai dung lượng mà CHƯA chia cho ai: một dung lượng
        # không được chia là một khoảng trống người đọc cần thấy, không phải một
        # dòng để bỏ qua.
        quan_tam = list(self.capacity) + [
            m for m in self.metrics() if m not in self.capacity
        ]
        for metric in quan_tam:
            tong_dl = self.capacity.get(metric)
            dung_duoc = self.usable(metric)
            da_chia = self.allotted(metric)
            if tong_dl is None:
                dong.append(f"{metric}: có module được chia phần nhưng chưa khai dung lượng")
                continue
            dong.append(
                f"{metric}: dung lượng {tong_dl:,.0f}, dự phòng {self.reserve_pct:g}% "
                f"→ chia được {dung_duoc:,.0f}; đã chia {da_chia:,.0f} "
                f"({da_chia / dung_duoc * 100:.1f}%)"
            )
        dong.append("")
        if not self.allotments:
            dong.append(
                "  Chưa module nào được chia phần. Trần TỔNG ở 'limits' vẫn đang\n"
                "  chạy, nhưng nó chỉ nói được vào lúc liên kết.\n"
                "  Đề xuất một bản chia: eaa budget propose"
            )
        for a in sorted(self.allotments, key=lambda x: x.module):
            phan = "  ".join(f"{k}={v:,.0f}" for k, v in sorted(a.limits.items()))
            dong.append(f"  {a.module:<18} {phan}" + (f"   — {a.note}" if a.note else ""))
        if self.derived:
            dong.append("")
            for d in self.derived:
                dong.append(
                    f"  suy ra: {d.name} = {d.capacity_key} − {d.used_key}"
                )
        van_de = self.validate()
        if van_de:
            dong.append("\nBản chia có vấn đề:")
            dong += [f"  · {v}" for v in van_de]
        return "\n".join(dong)

    def to_yaml_block(self) -> dict[str, Any]:
        """Dựng lại khối ``budget`` để ghi vào ``constraints.yaml``."""
        khoi: dict[str, Any] = {
            "capacity": {k: int(v) if v.is_integer() else v for k, v in self.capacity.items()},
            "reserve_pct": self.reserve_pct,
            "modules": {
                a.module: {
                    **{k: int(v) if float(v).is_integer() else v for k, v in a.limits.items()},
                    **({"note": a.note} if a.note else {}),
                }
                for a in sorted(self.allotments, key=lambda x: x.module)
            },
        }
        if self.warn_at_pct != WARN_AT_PCT_DEFAULT:
            khoi["warn_at_pct"] = self.warn_at_pct
        if self.derived:
            khoi["derived"] = {
                d.name: {"capacity": d.capacity_key, "used": d.used_key}
                for d in self.derived
            }
        return khoi


# --------------------------------------------------------------------------
# Đề xuất cách chia (N-015, mức tự chủ T1 — Agent đề xuất, người duyệt tại G1)
# --------------------------------------------------------------------------


def propose_split(
    modules: Sequence[tuple[str, float]],
    capacity: Mapping[str, float],
    *,
    metrics: Sequence[str],
    reserve_pct: float = RESERVE_PCT_DEFAULT,
    derived: Sequence[DerivedMetric] = (),
    notes: Mapping[str, str] | None = None,
) -> ResourceBudget:
    """Chia dung lượng dùng được cho các module theo trọng số.

    Cách chia cố ý ĐƠN GIẢN và giải thích được bằng một câu: *phần của mỗi
    module tỉ lệ với trọng số của nó*. Một công thức tinh vi hơn sẽ cho những
    con số trông có căn cứ hơn mà thật ra vẫn là phỏng đoán — và ở G1 người
    duyệt cần thấy được vì sao mỗi con số ra như thế để mà sửa nó, chứ không
    cần một con số đẹp hơn.

    Trọng số đến từ dữ liệu đã có (số tài nguyên module dùng, có chạy định kỳ
    hay không), không phải từ mô hình — xem ``weights_from_backlog`` ở tầng CLI.
    """
    if not modules:
        raise BudgetError("Không có module nào để chia ngân sách.")
    tong_trong_so = sum(max(0.0, w) for _, w in modules)
    if tong_trong_so <= 0:
        raise BudgetError("Tổng trọng số phải dương — không chia được theo trọng số 0.")

    thieu = [m for m in metrics if m not in capacity]
    if thieu:
        raise BudgetError(
            f"Chưa khai dung lượng cho {thieu} — không có mẫu số thì không chia được."
        )

    phan_chia: list[Allotment] = []
    for ten, trong_so in modules:
        gioi_han: dict[str, float] = {}
        for metric in metrics:
            dung_duoc = capacity[metric] * (100.0 - reserve_pct) / 100.0
            # Làm tròn XUỐNG, không làm tròn gần nhất. Làm tròn gần nhất có thể
            # đẩy tổng vượt dung lượng dùng được đúng vài byte — và một bản đề
            # xuất vừa sinh ra đã tự vi phạm phép kiểm của chính nó thì người
            # duyệt sẽ mất lòng tin vào cả bản chia, vì một lý do hoàn toàn máy
            # móc. Vài byte dôi ra rơi về dự phòng, đúng chỗ của chúng.
            gioi_han[metric] = float(int(dung_duoc * max(0.0, trong_so) / tong_trong_so))
        phan_chia.append(
            Allotment(
                module=ten,
                limits=gioi_han,
                note=(notes or {}).get(ten, f"trọng số {trong_so:g}/{tong_trong_so:g}"),
            )
        )

    return ResourceBudget(
        capacity=dict(capacity),
        reserve_pct=reserve_pct,
        allotments=tuple(phan_chia),
        derived=tuple(derived),
    )


# --------------------------------------------------------------------------
# Ngân sách token và chi phí (N-904)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    """Token đã tiêu cho một module, đọc từ nhật ký KPI."""

    module: str
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass(frozen=True)
class TokenBudgetCheck:
    """Module này còn được gọi mô hình nữa không, và tốn bao nhiêu rồi."""

    module: str
    usage: TokenUsage
    cap: int
    status: str
    cost: float = 0.0
    currency: str = ""

    @property
    def pct(self) -> float | None:
        if not self.cap:
            return None
        return round(self.usage.total / self.cap * 100.0, 1)

    @property
    def blocked(self) -> bool:
        return self.status == VUOT_PHAN

    def render(self) -> str:
        tien = f"  ≈ {self.cost:,.4f} {self.currency}" if self.currency else ""
        if not self.cap:
            return (
                f"Token module {self.module}: {self.usage.total:,} "
                f"({self.usage.calls} lượt gọi){tien} — chưa khai trần theo module."
            )
        dong = (
            f"Token module {self.module}: {self.usage.total:,} / {self.cap:,} "
            f"({self.pct:.1f}%, {self.usage.calls} lượt gọi){tien}"
        )
        if self.status == SAP_CHAM:
            dong += "\n  Sắp chạm trần. Còn kịp đổi hướng: thu hẹp phạm vi module, "
            dong += "hoặc bổ sung tri thức còn thiếu để bớt vòng tự sửa."
        if self.status == VUOT_PHAN:
            dong += (
                "\n  ĐÃ VƯỢT TRẦN — không mở thêm lượt gọi mô hình cho module này.\n"
                "  Một module ăn hết phần của mình mà chưa xong thường không phải "
                "vì trần chật, mà vì nó đang thiếu tri thức và vòng tự sửa đang "
                "quay không: 'eaa resolve " + self.module + "'.\n"
                "  Quyết định nới trần là của người, và nới bằng cách sửa "
                "'budget.tokens.per_module' trong constraints.yaml — tức là đi "
                "qua G1, không phải qua một cờ dòng lệnh."
            )
        return dong


@dataclass(frozen=True)
class TokenBudget:
    """Trần token tích lũy cho một module, và cách quy ra tiền."""

    per_module: int = 0
    warn_at_pct: float = WARN_AT_PCT_DEFAULT
    #: Đơn giá cho một triệu token. Thuộc DỰ ÁN: nó phụ thuộc mô hình và hợp
    #: đồng, hai thứ engine không được ghim.
    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0
    currency: str = ""

    @classmethod
    def from_constraints(cls, constraints: Any) -> "TokenBudget | None":
        raw = ((getattr(constraints, "raw", None) or {}).get("budget") or {}).get("tokens")
        if not raw:
            return None
        if not isinstance(raw, dict):
            raise BudgetError("'budget.tokens' phải là ánh xạ khóa–giá trị")

        tran = raw.get("per_module", 0)
        if not isinstance(tran, int) or isinstance(tran, bool) or tran < 0:
            raise BudgetError(
                f"budget.tokens.per_module phải là số nguyên không âm, nhận {tran!r}"
            )
        canh_bao = _so(raw.get("warn_at_pct", WARN_AT_PCT_DEFAULT))
        if canh_bao is None or not 0 < canh_bao <= 100:
            raise BudgetError(
                f"budget.tokens.warn_at_pct phải trong (0, 100], nhận {raw.get('warn_at_pct')!r}"
            )
        return cls(
            per_module=tran,
            warn_at_pct=canh_bao,
            price_in_per_mtok=_so(raw.get("price_in_per_mtok", 0)) or 0.0,
            price_out_per_mtok=_so(raw.get("price_out_per_mtok", 0)) or 0.0,
            currency=str(raw.get("currency", "")),
        )

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        """Quy token ra tiền. Chưa khai đơn giá thì trả 0 — và ``currency`` rỗng
        là cách nói "con số này chưa có nghĩa", chứ không phải "miễn phí"."""
        return (
            tokens_in / 1_000_000 * self.price_in_per_mtok
            + tokens_out / 1_000_000 * self.price_out_per_mtok
        )

    def check(self, usage: TokenUsage) -> TokenBudgetCheck:
        if not self.per_module:
            trang_thai = TRONG_PHAN
        elif usage.total >= self.per_module:
            trang_thai = VUOT_PHAN
        elif usage.total >= self.per_module * self.warn_at_pct / 100.0:
            trang_thai = SAP_CHAM
        else:
            trang_thai = TRONG_PHAN
        return TokenBudgetCheck(
            module=usage.module,
            usage=usage,
            cap=self.per_module,
            status=trang_thai,
            cost=self.cost(usage.tokens_in, usage.tokens_out),
            currency=self.currency,
        )


def spent_tokens(kpi: Any, module: str) -> TokenUsage:
    """Cộng token đã tiêu cho một module từ ``kpi_log.csv``.

    Nguồn số liệu là nhật ký KPI chứ không phải một bộ đếm trong bộ nhớ: vòng
    lặp chuẩn dừng ở G3 và có thể chạy tiếp hôm sau trong một tiến trình khác,
    nên bộ đếm nào không sống sót qua ranh giới tiến trình thì không đếm được
    thứ cần đếm.
    """
    vao = ra = luot = 0
    for dong in (kpi.rows_for(module) if kpi is not None else []):
        co_token = False
        for cot, cong in (("tokens_in", "vao"), ("tokens_out", "ra")):
            try:
                gia_tri = int(float(dong.get(cot) or 0))
            except (TypeError, ValueError):
                continue
            if gia_tri <= 0:
                continue
            co_token = True
            if cong == "vao":
                vao += gia_tri
            else:
                ra += gia_tri
        if co_token:
            luot += 1
    return TokenUsage(module=module, tokens_in=vao, tokens_out=ra, calls=luot)


def weights_from_modules(modules: Iterable[Any]) -> list[tuple[str, float]]:
    """Trọng số suy từ dữ liệu đã khai, không từ phỏng đoán của mô hình.

    Một module dùng nhiều tài nguyên phần cứng hơn thì phần mã cấu hình của nó
    dài hơn; một module chạy định kỳ thì có thêm phần thân vòng lặp. Hai dấu
    hiệu ấy thô, nhưng chúng ĐỌC ĐƯỢC từ backlog, nên bản chia đầu tiên có căn
    cứ kiểm lại được thay vì là một con số rơi từ trên xuống.
    """
    ket_qua: list[tuple[str, float]] = []
    for m in modules:
        ma = str(getattr(m, "id", None) or getattr(m, "module_id", "") or m)
        dung = getattr(m, "uses", ()) or ()
        dinh_ky = bool(getattr(m, "step", "") or getattr(m, "scheduled", False))
        ket_qua.append((ma, 1.0 + 0.5 * len(tuple(dung)) + (0.5 if dinh_ky else 0.0)))
    return ket_qua
