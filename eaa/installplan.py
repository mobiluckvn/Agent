"""Cài theo THỨ TỰ NÀO, bằng CÁCH NÀO, và có chỗ nào đá nhau không.

EAA-AIS-05 §9.1, §9.2, §9.4; FR-ENV-02, FR-ENV-04.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-90.

Ba câu hỏi module này trả lời
------------------------------

``eaa doctor --fix`` in ra danh sách lệnh cài. Danh sách ấy đúng từng dòng một
mà thiếu ba thứ, và cả ba đều chỉ lộ ra khi có nhiều hơn một công cụ:

1. **Thứ tự.** Thư viện hệ thống phải có trước gói dựa vào nó. Cài sai thứ tự
   thì lệnh thứ hai hỏng bằng một thông báo nói về thứ khác hẳn, và người dùng
   đi sửa nhầm chỗ.
2. **Cách cài.** Không phải công cụ nào cũng nằm trong một trình quản lý gói.
   Có cái phải tải nhị phân, có cái phải dựng từ nguồn, có cái nên nhốt trong
   một môi trường riêng.
3. **Xung đột.** Hai Tool Card cùng đòi một thứ ở hai phiên bản không tương
   thích. Cài cái sau làm hỏng cái trước, và cái trước thì đã báo "đạt" rồi.

Vì sao ba câu ấy gộp vào một module
------------------------------------

Vì cả ba chỉ trả lời được khi nhìn **toàn bộ manifest cùng lúc**. Một Tool Card
đọc riêng thì không biết mình đứng sau ai, và không biết mình đá nhau với ai.
Đặt phép kiểm ở tầng từng thẻ là đặt nó ở chỗ không có đủ thông tin.

Ranh giới không đổi
--------------------

Module này **không cài gì cả**. Nó sắp thứ tự và chỉ ra chỗ đá nhau; việc chạy
vẫn là của người, qua ``eaa doctor --fix`` (N-022 ở mức tự chủ T2). Một bản kế
hoạch cài không phải một lần cài.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

__all__ = [
    "InstallPlanError",
    "CircularDependency",
    "Conflict",
    "PlannedStep",
    "InstallPlan",
    "plan_installs",
    "find_conflicts",
    "CACH_CAI",
    "GOI",
    "NHI_PHAN",
    "NGUON",
    "CONTAINER",
    "VENV",
]

#: Năm cách cài, và mỗi cách hỏng theo một kiểu khác nhau.
GOI = "gói"
NHI_PHAN = "nhị phân"
NGUON = "nguồn"
CONTAINER = "container"
VENV = "môi trường riêng"

CACH_CAI: dict[str, str] = {
    GOI: "trình quản lý gói của hệ điều hành hoặc của ngôn ngữ — cách gọn nhất, "
         "và cách duy nhất có sẵn đường gỡ",
    NHI_PHAN: "tải bản dựng sẵn. Nhanh, nhưng BẮT BUỘC kèm checksum: một tệp "
              "nhị phân tải về không ai đọc được nội dung",
    NGUON: "dựng từ mã nguồn. Cần trình biên dịch và tệp tiêu đề của hệ — đây "
           "là cách sinh ra nhiều lỗi cài nhất",
    CONTAINER: "chạy trong container. Không đụng vào máy, đổi lại phải có sẵn "
               "trình chạy container và phải nối thư mục làm việc vào",
    VENV: "nhốt trong một môi trường riêng, để không phá phụ thuộc sẵn có của máy",
}


class InstallPlanError(Exception):
    """Không dựng được kế hoạch cài."""


class CircularDependency(InstallPlanError):
    """Phụ thuộc vòng — không có thứ tự nào thỏa mãn."""


# --------------------------------------------------------------------------
# Xung đột
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Conflict:
    """Hai Tool Card đòi cùng một thứ ở hai ràng buộc không đội trời chung."""

    subject: str
    left: str
    left_constraint: str
    right: str
    right_constraint: str

    def render(self) -> str:
        return (f"  ⚠ {self.subject}: {self.left} đòi {self.left_constraint}, "
                f"{self.right} đòi {self.right_constraint}")


_PHIEN_BAN = re.compile(r"(\d+(?:\.\d+)*)")


def _so(rang_buoc: str) -> tuple[int, ...]:
    khop = _PHIEN_BAN.search(rang_buoc or "")
    return tuple(int(x) for x in khop.group(1).split(".")) if khop else ()


def _toan_tu(rang_buoc: str) -> str:
    v = (rang_buoc or "").strip()
    for t in (">=", "<=", "==", ">", "<", "~=", "^"):
        if v.startswith(t):
            return t
    return ">=" if v else ""


def find_conflicts(specs: Sequence[Any]) -> list[Conflict]:
    """Tìm chỗ hai thẻ đòi cùng một thứ ở hai ràng buộc loại trừ nhau.

    Chỉ báo khi **chắc chắn** loại trừ nhau: ``>=3.0`` và ``<2.0``. Hai ràng
    buộc chỉ *có thể* đá nhau thì không báo — một cảnh báo sai ở đây làm người
    dùng bỏ qua cả những cảnh báo đúng, và bộ kiểm này chạy mỗi lần chạy doctor.
    """
    doi_hoi: dict[str, list[tuple[str, str]]] = {}
    for s in specs:
        for ten, rb in (getattr(s, "requires", None) or {}).items():
            doi_hoi.setdefault(str(ten), []).append((getattr(s, "name", "?"), str(rb)))

    ket: list[Conflict] = []
    for chu_the, ds in doi_hoi.items():
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                (t1, r1), (t2, r2) = ds[i], ds[j]
                if _loai_tru(r1, r2):
                    ket.append(Conflict(chu_the, t1, r1, t2, r2))
    return ket


def _loai_tru(a: str, b: str) -> bool:
    """Hai ràng buộc có CHẮC CHẮN loại trừ nhau không."""
    va, vb = _so(a), _so(b)
    if not va or not vb:
        return False
    ta, tb = _toan_tu(a), _toan_tu(b)

    # sàn của cái này cao hơn trần của cái kia
    if ta in (">=", ">") and tb in ("<=", "<"):
        return va > vb or (va == vb and (ta == ">" or tb == "<"))
    if tb in (">=", ">") and ta in ("<=", "<"):
        return vb > va or (va == vb and (tb == ">" or ta == "<"))
    # hai lần ghim cứng vào hai giá trị khác nhau
    if ta == "==" and tb == "==" and va != vb:
        return True
    if ta == "==" and tb in (">=", ">"):
        return va < vb
    if tb == "==" and ta in (">=", ">"):
        return vb < va
    return False


# --------------------------------------------------------------------------
# Thứ tự
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedStep:
    """Một bước trong kế hoạch cài."""

    name: str
    method: str = GOI
    command: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    note: str = ""
    present: bool = False

    def render(self, so: int) -> str:
        if self.present:
            return f"  {so}. {self.name}   ✓ đã có, bỏ qua"
        dong = [f"  {so}. {self.name}   [{self.method}]"]
        if self.after:
            dong.append(f"      sau khi có: {', '.join(self.after)}")
        if self.command:
            dong.append(f"      $ {' '.join(self.command)}")
        else:
            dong.append(f"      (thẻ công cụ chưa khai lệnh cài cho hệ điều hành này)")
        if self.note:
            dong.append(f"      {self.note}")
        return "\n".join(dong)


@dataclass
class InstallPlan:
    """Cài cái gì, theo thứ tự nào, và chỗ nào đá nhau."""

    steps: tuple[PlannedStep, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    os_key: str = ""

    @property
    def todo(self) -> list[PlannedStep]:
        return [s for s in self.steps if not s.present]

    @property
    def blocked(self) -> bool:
        return bool(self.conflicts)

    @property
    def confidence_level(self) -> str:
        """SUY RA: thứ tự suy từ khai báo, chưa lần cài nào chạy để xác nhận."""
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self) -> str:
        from eaa.confidence import header

        dong = ["Kế hoạch cài", "", header(self.confidence_level), ""]

        if self.conflicts:
            dong += [
                "DỪNG — có xung đột phải phân xử trước khi cài gì:",
                *[c.render() for c in self.conflicts],
                "",
                "Cài chồng lên nhau khi đang xung đột thì cái sau làm hỏng cái "
                "trước, và cái trước thì đã báo 'đạt' rồi — nên lỗi lộ ra ở một "
                "chỗ chẳng liên quan gì.",
                "",
            ]

        if not self.todo:
            dong.append("Không thiếu công cụ nào.")
            return "\n".join(dong)

        dong.append(f"── {len(self.todo)} công cụ cần cài, theo ĐÚNG thứ tự này")
        for i, s in enumerate(self.steps, 1):
            dong.append(s.render(i))
        dong += [
            "",
            "Thứ tự quan trọng: thư viện hệ thống phải có trước gói dựa vào nó. "
            "Cài ngược thì lệnh sau hỏng bằng một thông báo nói về thứ khác hẳn.",
            "",
            "Tôi KHÔNG chạy những lệnh này — cài phần mềm là thay đổi máy của "
            "bạn (N-022, mức tự chủ T2). Chạy từng cái và xác nhận: eaa doctor --fix",
        ]
        return "\n".join(dong)


def plan_installs(
    specs: Sequence[Any],
    *,
    os_key: str = "",
    present: Iterable[str] = (),
) -> InstallPlan:
    """Sắp thứ tự cài theo phụ thuộc đã khai. Ném khi có vòng.

    Sắp xếp tô-pô ổn định: cùng một manifest luôn ra cùng một thứ tự, để hai
    lần chạy doctor không in ra hai danh sách khác nhau mà không ai hiểu vì sao.
    """
    da_co = set(present)
    theo_ten = {getattr(s, "name", ""): s for s in specs}

    # Chỉ giữ phụ thuộc trỏ tới công cụ CÓ TRONG manifest. Một phụ thuộc trỏ ra
    # ngoài (thư viện hệ thống chẳng hạn) là ghi chú cho người, không phải một
    # nút trong đồ thị — xếp thứ tự theo nó thì xếp theo thứ không tồn tại.
    canh: dict[str, set[str]] = {}
    for ten, s in theo_ten.items():
        canh[ten] = {
            d for d in (getattr(s, "requires", None) or {}) if d in theo_ten and d != ten
        }

    thu_tu: list[str] = []
    da_xep: set[str] = set()
    dang_xet: set[str] = set()

    def tham(ten: str, duong: tuple[str, ...] = ()) -> None:
        if ten in da_xep:
            return
        if ten in dang_xet:
            vong = " → ".join([*duong, ten])
            raise CircularDependency(
                f"Phụ thuộc vòng: {vong}. Không có thứ tự nào thỏa mãn — phải "
                "gỡ vòng ở manifest, máy không tự chọn hộ được cái nào đi trước."
            )
        dang_xet.add(ten)
        for d in sorted(canh.get(ten, ())):
            tham(d, (*duong, ten))
        dang_xet.discard(ten)
        da_xep.add(ten)
        thu_tu.append(ten)

    for ten in sorted(theo_ten):
        tham(ten)

    buoc: list[PlannedStep] = []
    for ten in thu_tu:
        s = theo_ten[ten]
        cach = str(getattr(s, "method", "") or GOI)
        lenh = tuple((getattr(s, "install", None) or {}).get(os_key, ()) or ())

        chu: list[str] = []
        if cach == NHI_PHAN and not getattr(s, "checksum", ""):
            chu.append("⚠ tải nhị phân mà thẻ chưa khai checksum — một tệp nhị "
                       "phân không ai đọc được nội dung (AIS §9.4)")
        elif cach != GOI and cach in CACH_CAI:
            # Chỉ giải thích cách cài KHÁC mặc định. Nhắc lại "đây là trình
            # quản lý gói" ở từng dòng làm bản kế hoạch dài gấp đôi mà không
            # thêm một chữ nào người đọc chưa biết — và thứ đáng chú ý thật
            # (dòng cần checksum, dòng cần thư viện có trước) chìm trong đó.
            chu.append(CACH_CAI[cach])

        # Phụ thuộc trỏ RA NGOÀI manifest không xếp thứ tự được, nhưng bỏ im
        # lặng thì tệ hơn: nó vẫn là thứ phải có trước, và người dùng không có
        # cách nào biết. Nêu ra kèm chữ "kiểm bằng tay" là cách trung thực nhất.
        ngoai = sorted(
            f"{d} {rb}".strip()
            for d, rb in (getattr(s, "requires", None) or {}).items()
            if d not in theo_ten
        )
        if ngoai:
            chu.append(f"cần sẵn (không có trong manifest, kiểm bằng tay): {', '.join(ngoai)}")

        ghi_chu = " · ".join(chu)
        buoc.append(PlannedStep(
            name=ten, method=cach, command=lenh,
            after=tuple(sorted(canh.get(ten, ()))),
            note=ghi_chu, present=ten in da_co,
        ))

    return InstallPlan(
        steps=tuple(buoc),
        conflicts=tuple(find_conflicts(specs)),
        os_key=os_key,
    )
