"""Chú thích số học có đúng thứ nguyên không — N-911.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-174.

Ca thật
-------

Mã sinh ra mang chú thích::

    // 4ms per step / 0.000031s per sample = 129

Phép chia ấy **đúng số học**: 0,004 / 0,000031 = 129,03. Nó sai ở chỗ khác —
``0.000031`` không phải *giây trên mẫu*, nó là hệ số thang của con quay, đơn vị
**độ trên LSB**. Chú thích tự gán cho hằng số ấy một đơn vị mà nó không có, con
số ra vô nghĩa, và đó là nguyên nhân robot không lấy đủ mẫu.

Điều đáng chú ý: không cổng nào bắt được, vì mã dịch được và chú thích nghe hợp
lý. Người đọc lướt qua thấy một phép chia có đơn vị hai bên thì tin.

Hai phép soi, và chúng bắt hai chuyện khác nhau
-----------------------------------------------

1. **Đơn vị khai trong chú thích chọi với đơn vị đã đăng ký.** Đây là phép bắt
   được đúng ca trên — nhưng chỉ khi hằng số ấy có mặt trong sổ số đo với đơn
   vị thật của nó. Đó là lý do N-913 (sổ số đo) phải làm trước N-911: **phép
   kiểm này chỉ mạnh bằng cái sổ đứng sau nó**, và nó nói thẳng điều ấy thay vì
   im lặng tỏ ra chắc chắn.

2. **Phép tính không ra kết quả nó khai.** Tự chứa, không cần sổ nào. Bắt hạng
   khác: chú thích dựng một dẫn giải nghe được nhưng cộng trừ sai. Có quy đổi
   tiền tố thời gian, nên ``4ms / 0.000031s = 129`` KHÔNG bị kêu — nó đúng.

Cả hai ra **CẢNH BÁO**, không chặn cổng. Chú thích là văn xuôi tự do; một bộ
đọc văn xuôi mà chặn được đường merge sẽ chặn nhầm, và một cổng chặn nhầm sớm
muộn cũng bị tắt đi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "PhepTinh",
    "DauHieu",
    "doc_phep_tinh",
    "don_vi_khai_trong_chu_thich",
    "soi_chu_thich_so_hoc",
    "HE_SO",
]

#: Hệ số quy về đơn vị gốc, theo ĐẠI LƯỢNG. Chỉ những đơn vị mà mã nhúng dùng
#: hằng ngày; danh sách dài thêm là danh sách báo nhầm thêm.
HE_SO: dict[str, tuple[str, float]] = {
    "s": ("thời gian", 1.0),
    "ms": ("thời gian", 1e-3),
    "us": ("thời gian", 1e-6),
    "µs": ("thời gian", 1e-6),
    "ns": ("thời gian", 1e-9),
    "hz": ("tần số", 1.0),
    "khz": ("tần số", 1e3),
    "mhz": ("tần số", 1e6),
    "v": ("điện áp", 1.0),
    "mv": ("điện áp", 1e-3),
    "a": ("dòng điện", 1.0),
    "ma": ("dòng điện", 1e-3),
}

_SO = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
#: Một số kèm đơn vị dính liền hoặc cách một dấu cách: `4ms`, `0.5 V`, `129`.
_HANG = re.compile(rf"(?P<so>{_SO})\s*(?P<dv>[A-Za-zµ°%]+)?")
#: `A <toán tử> B = C` trong một dòng chú thích.
_PHEP = re.compile(
    rf"(?P<a>{_SO}\s*[A-Za-zµ°%]*)\s*(?P<op>[*/])\s*"
    rf"(?P<b>{_SO}\s*[A-Za-zµ°%]*)\s*=\s*(?P<c>{_SO})"
)
_RUOT_CHU_THICH = re.compile(r"//([^\n]*)|/\*(.*?)\*/", re.DOTALL)

#: Sai lệch tương đối cho phép giữa kết quả tính và kết quả khai. Chú thích làm
#: tròn, nên 2% là chỗ cho việc làm tròn chứ không phải chỗ cho việc tính sai.
SAI_SO_CHO_PHEP = 0.02


@dataclass(frozen=True)
class PhepTinh:
    """Một phép tính viết trong chú thích."""

    dong: int
    nguyen_van: str
    a: float
    don_vi_a: str
    op: str
    b: float
    don_vi_b: str
    c: float

    def ket_qua_thuc(self) -> float | None:
        """Kết quả thật, đã quy đổi tiền tố khi hai vế cùng đại lượng.

        Không cùng đại lượng thì KHÔNG quy đổi — quy đổi bừa giữa hai đại lượng
        khác nhau là làm đúng cái sai mà bộ này sinh ra để tìm.
        """
        a, b = self.a, self.b
        da, ha = HE_SO.get(self.don_vi_a.lower(), ("", 1.0))
        db, hb = HE_SO.get(self.don_vi_b.lower(), ("", 1.0))
        if da and db and da == db:
            a, b = a * ha, b * hb
        if self.op == "/":
            return None if b == 0 else a / b
        return a * b


@dataclass(frozen=True)
class DauHieu:
    """Một chỗ đáng ngờ trong chú thích."""

    loai: str
    dong: int
    chi_tiet: str

    def __str__(self) -> str:
        return f"dòng {self.dong} — {self.loai}: {self.chi_tiet}"


def _tach_hang(van: str) -> tuple[float, str]:
    khop = _HANG.match(van.strip())
    if not khop:
        return 0.0, ""
    return float(khop.group("so")), (khop.group("dv") or "")


def doc_phep_tinh(nguon: str) -> list[PhepTinh]:
    """Mọi phép ``A op B = C`` viết trong chú thích của một tệp mã."""
    ra: list[PhepTinh] = []
    for khop_ct in _RUOT_CHU_THICH.finditer(nguon):
        ruot = khop_ct.group(1) or khop_ct.group(2) or ""
        dong = nguon.count("\n", 0, khop_ct.start()) + 1
        for m in _PHEP.finditer(ruot):
            a, da = _tach_hang(m.group("a"))
            b, db = _tach_hang(m.group("b"))
            ra.append(
                PhepTinh(
                    dong=dong,
                    nguyen_van=" ".join(m.group(0).split()),
                    a=a,
                    don_vi_a=da,
                    op=m.group("op"),
                    b=b,
                    don_vi_b=db,
                    c=float(m.group("c")),
                )
            )
    return ra


def don_vi_khai_trong_chu_thich(nguon: str) -> dict[str, set[str]]:
    """Giá trị số → tập đơn vị mà chú thích gán cho nó.

    Khoá là chuỗi số nguyên văn, không phải số đã chuẩn hoá: hai cách viết khác
    nhau của cùng một giá trị là hai lần mô hình gõ ra, và ta muốn so đúng cái
    nó gõ với cái sổ ghi.
    """
    ra: dict[str, set[str]] = {}
    for khop_ct in _RUOT_CHU_THICH.finditer(nguon):
        ruot = khop_ct.group(1) or khop_ct.group(2) or ""
        for m in _HANG.finditer(ruot):
            dv = (m.group("dv") or "").strip()
            if not dv or dv.lower() not in HE_SO:
                continue
            ra.setdefault(m.group("so"), set()).add(dv)
    return ra


def _cung_dai_luong(x: str, y: str) -> bool:
    dx = HE_SO.get(x.lower(), ("", 0.0))[0]
    dy = HE_SO.get(y.lower(), ("", 0.0))[0]
    return bool(dx) and dx == dy


def soi_chu_thich_so_hoc(
    nguon: str, don_vi_da_dang_ky: dict[str, str] | None = None
) -> list[DauHieu]:
    """Hai phép soi, gộp kết quả.

    ``don_vi_da_dang_ky`` ánh xạ giá trị số → đơn vị THẬT, dựng từ sổ số đo
    (``eaa measured``). Thiếu nó thì phép soi thứ nhất im — và im vì thiếu dữ
    liệu khác hẳn im vì không có gì sai. Chỗ nói ra khác biệt ấy là tài liệu của
    hàm này và bản báo cáo, không phải một dòng cảnh báo úp mở.
    """
    ra: list[DauHieu] = []

    # 1 — đơn vị khai trong chú thích chọi với đơn vị đã đăng ký.
    so_do = don_vi_da_dang_ky or {}
    for gia_tri, khai in sorted(don_vi_khai_trong_chu_thich(nguon).items()):
        that = so_do.get(gia_tri)
        if not that:
            continue
        lech = sorted(d for d in khai if not _cung_dai_luong(d, that))
        if lech:
            ra.append(
                DauHieu(
                    "ĐƠN VỊ CHỌI VỚI SỔ SỐ ĐO",
                    _dong_cua(nguon, gia_tri),
                    f"chú thích gán cho {gia_tri} đơn vị {', '.join(lech)}, "
                    f"nhưng sổ số đo ghi nó là {that}. Một hằng số bị gán nhầm "
                    "đơn vị cho ra một con số vô nghĩa mà phép tính vẫn chạy",
                )
            )

    # 2 — phép tính không ra kết quả nó khai.
    for phep in doc_phep_tinh(nguon):
        thuc = phep.ket_qua_thuc()
        if thuc is None or phep.c == 0:
            continue
        if abs(thuc - phep.c) / abs(phep.c) > SAI_SO_CHO_PHEP:
            ra.append(
                DauHieu(
                    "PHÉP TÍNH KHÔNG RA KẾT QUẢ NÓ KHAI",
                    phep.dong,
                    f"`{phep.nguyen_van}` — tính ra {thuc:.6g}, chú thích ghi "
                    f"{phep.c:g}",
                )
            )
    return ra


def _dong_cua(nguon: str, gia_tri: str) -> int:
    for i, dong in enumerate(nguon.splitlines(), 1):
        if gia_tri in dong and ("//" in dong or "/*" in dong or "*" in dong.strip()[:1]):
            return i
    return 0
