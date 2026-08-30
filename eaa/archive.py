"""Đọc một kho nén hồ sơ dự án — giải nén, phân loại, rút dữ kiện.

EAA-AIS-05 §6.1 (FR-ING-01: nhận và phân loại bốn loại đầu vào), §6.3 (giữ
nguyên bản gốc); nghiệp vụ N-004. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-69.

Vì sao cần một module riêng cho cái vỏ đựng
--------------------------------------------

``eaa/ingest.py`` nhận được PDF, ảnh, mã nguồn — từng tệp một. Nhưng hồ sơ gốc
của một dự án hiếm khi tới từng tệp: nó tới dưới dạng **một kho nén** mà ai đó
gửi qua. Trước module này, Agent đứng trước một tệp ``.zip`` và không có gì để
làm với nó, nên người dùng phải tự giải nén, tự nhìn, tự chọn tệp nào đáng
nạp — tức là phải làm xong phần khó trước khi nhờ được.

Ba việc, và việc thứ ba là việc đáng giá nhất
----------------------------------------------

1. **Giải nén an toàn.** Kho nén là dữ liệu từ bên ngoài, nên nó được đối xử
   như dữ liệu từ bên ngoài: chặn đường dẫn thoát ra ngoài thư mục đích, chặn
   liên kết mềm, chặn bom nén.
2. **Phân loại** theo đúng bốn loại của FR-ING-01, rồi đếm và xếp nhóm.
3. **Rút dữ kiện XÁC ĐỊNH từ mã nguồn.** Mã mẫu trong hồ sơ nói được nhiều thứ
   mà không tài liệu nào nói rõ bằng: chân nào nối vào đâu, thư viện nào đang
   dùng, thanh ghi nào bị chạm. Những thứ ấy rút được bằng biểu thức chính quy,
   không cần mô hình — nên chúng **tất định và kiểm lại được**.

Điều module này KHÔNG làm
--------------------------

Nó không kết luận "đây là bo X". Nó bày ra thứ đọc được và đánh dấu tất cả là
*proposed*. Suy từ vài dòng ``#define`` ra một khẳng định về phần cứng là đúng
loại bước nhảy mà cả sản phẩm này sinh ra để chặn — và nó đặc biệt dễ ở đây,
vì một kho nén trông như một nguồn đáng tin.
"""

from __future__ import annotations

import os
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "ArchiveError",
    "ArchiveEntry",
    "CodeFact",
    "ArchiveSurvey",
    "read_archive",
    "extract_archive",
    "MAX_TONG_BYTE",
    "MAX_TI_LE_NEN",
]

#: Trần tổng dung lượng sau giải nén. Một kho nén 100 MB bung ra 50 GB là một
#: bom nén, và nó không cần cố ý độc hại mới làm đầy đĩa của người dùng.
MAX_TONG_BYTE = 2 * 1024**3

#: Trần tỉ lệ nén của MỘT tệp. Vượt ngưỡng này thì gần như chắc chắn là dữ liệu
#: dựng để bung, không phải tài liệu.
MAX_TI_LE_NEN = 200

#: Thư mục siêu dữ liệu macOS nhét vào mọi kho nén tạo trên máy Mac. Bỏ đi để
#: bản kiểm kê nói về hồ sơ, không nói về hệ điều hành của người gửi.
_RAC = ("__MACOSX/", ".DS_Store", "Thumbs.db")

#: Đuôi tệp mã nguồn mà ta đọc để rút dữ kiện.
_DUOI_MA = (".ino", ".c", ".h", ".cpp", ".hpp", ".cc", ".py")

#: Dấu hiệu một tệp thuộc THƯ VIỆN ĐI KÈM chứ không thuộc dự án.
#:
#: Phân biệt này quyết định chất lượng bản khảo sát. Một hồ sơ thật thường kèm
#: cả cây `libraries/` của bên thứ ba, và mã ví dụ trong đó khai đủ thứ chân
#: chẳng liên quan tới con robot. Trộn chúng vào thì phần dữ kiện — thứ đáng
#: giá nhất — chìm trong nhiễu, và người đọc mất lòng tin vào cả bản.
_DAU_HIEU_THU_VIEN = ("/libraries/", "/library/", "/examples/", "/example/",
                      "/third_party/", "/vendor/", "/.pio/", "/node_modules/")

#: ``#define TÊN giá_trị`` — nguồn dữ kiện chân và hằng số cấu hình.
_DEFINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(.+?)\s*(?://.*)?$", re.M)
#: ``#include <thư_viện.h>`` — nói được dự án dựa vào những gì.
_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
#: Gán một định danh viết HOA kiểu ``REG = ...`` / ``REG |= ...``. Quy ước
#: viết hoa cho thanh ghi là chung cho mọi họ MCU, nên mẫu này không cần biết
#: tên thanh ghi cụ thể nào — và không được biết (FR-PLT-01).
_THANH_GHI = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\s*(?:\|=|&=|=)(?!=)")
#: Khai chân kiểu ``pinMode(9, OUTPUT)`` — quy ước của một lớp thư viện phổ
#: thông; tên hàm là dấu hiệu cú pháp, không phải tri thức nền tảng.
_PIN_MODE = re.compile(r"\bpinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z_]+)")

#: Từ khóa gợi ý chân, dùng để lọc ``#define`` nào đáng gọi là khai báo chân.
_GOI_Y_CHAN = ("pin", "chan", "port", "step", "dir", "enable", "en_", "_en",
               "sda", "scl", "rx", "tx", "led", "buzz", "trig", "echo")


class ArchiveError(Exception):
    """Không đọc được kho nén, hoặc kho nén không an toàn để giải."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _la_rac(ten: str) -> bool:
    return any(r in ten for r in _RAC)


@dataclass(frozen=True)
class ArchiveEntry:
    """Một tệp trong kho, đã phân loại."""

    path: str
    kind: str
    size: int
    #: Thuộc thư viện đi kèm chứ không thuộc dự án — xem :data:`_DAU_HIEU_THU_VIEN`.
    vendored: bool = False

    @property
    def suffix(self) -> str:
        return Path(self.path).suffix.lower()

    @property
    def name(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class CodeFact:
    """Một dữ kiện rút từ mã nguồn — tất định, kiểm lại được.

    Mang theo ``source`` là tệp và ``line`` là dòng, để người đọc mở đúng chỗ
    mà đối chiếu. Một dữ kiện không chỉ được nguồn thì không hơn gì lời đồn.
    """

    kind: str          # pin · define · include · register · pin_mode
    name: str
    value: str
    source: str
    line: int = 0
    vendored: bool = False

    def render(self) -> str:
        return f"  {self.name} = {self.value}   ({self.source}:{self.line})"


@dataclass
class ArchiveSurvey:
    """Bản khảo sát một kho nén — mọi thứ ở trạng thái ĐỀ XUẤT."""

    archive: str
    entries: tuple[ArchiveEntry, ...] = ()
    facts: tuple[CodeFact, ...] = ()
    extracted_to: str = ""
    surveyed_at: str = field(default_factory=_now)

    # -- kiểm kê ------------------------------------------------------------

    @property
    def by_kind(self) -> dict[str, int]:
        return dict(Counter(e.kind for e in self.entries))

    @property
    def by_suffix(self) -> dict[str, int]:
        return dict(Counter(e.suffix or "(không đuôi)" for e in self.entries))

    def of_kind(self, kind: str) -> list[ArchiveEntry]:
        return [e for e in self.entries if e.kind == kind]

    @property
    def total_bytes(self) -> int:
        return sum(e.size for e in self.entries)

    # -- dữ kiện ------------------------------------------------------------

    def facts_of(self, kind: str, *, vendored: bool | None = False) -> list[CodeFact]:
        """Dữ kiện theo loại. Mặc định CHỈ lấy mã của dự án.

        ``vendored=None`` để lấy cả thư viện đi kèm — hữu ích khi muốn biết
        thư viện làm gì, nhưng mặc định phải là mã dự án: đó là thứ nói về con
        robot này, còn mã ví dụ của thư viện nói về con robot của người khác.
        """
        return [
            f for f in self.facts
            if f.kind == kind and (vendored is None or f.vendored == vendored)
        ]

    @property
    def libraries(self) -> list[str]:
        """Thư viện mã DỰ ÁN dựa vào — thứ nói nhiều nhất về nền tảng đang dùng."""
        return sorted({f.value for f in self.facts_of("include")})

    def pin_declarations(self) -> list[tuple[str, str, str]]:
        """Khai báo chân, gom theo TÊN + GIÁ TRỊ.

        Hồ sơ thật hay có vài bản mã cùng khai một chân; in ra ba lần thì bản
        khảo sát dài gấp ba mà không thêm dữ kiện nào. Gom lại và nói rõ nó
        xuất hiện ở mấy chỗ — con số ấy tự nó là một dữ kiện: một chân khai
        giống nhau ở mọi bản thì gần như chắc là chân thật.
        """
        gom: dict[tuple[str, str], list[str]] = {}
        for f in self.facts_of("pin") + self.facts_of("pin_mode"):
            gom.setdefault((f.name, f.value), []).append(f"{f.source}:{f.line}")
        ket: list[tuple[str, str, str]] = []
        for (ten, gia_tri), cho in sorted(gom.items(), key=lambda x: (-len(x[1]), x[0])):
            o_dau = cho[0] if len(cho) == 1 else f"{len(cho)} chỗ, ví dụ {cho[0]}"
            ket.append((ten, gia_tri, o_dau))
        return ket

    @property
    def project_files(self) -> list[ArchiveEntry]:
        return [e for e in self.entries if not e.vendored]

    @property
    def vendored_files(self) -> list[ArchiveEntry]:
        return [e for e in self.entries if e.vendored]

    @property
    def registers(self) -> list[str]:
        return sorted({f.name for f in self.facts_of("register")})

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Bản kiểm kê tệp là ĐÃ KIỂM — đó là thứ đọc thẳng ra từ kho. Nhưng bản
        khảo sát nói chung mang cả dữ kiện rút từ mã, và một ``#define`` tên
        ``MOTOR_PIN`` mới chỉ nói rằng có một hằng số tên như thế, chưa nói
        rằng chân ấy nối vào động cơ. Nên cả bản đứng ở mức SUY RA.
        """
        from eaa.confidence import DA_KIEM, SUY_RA

        return SUY_RA if self.facts else DA_KIEM

    # -- trình bày ----------------------------------------------------------

    def render(self, limit: int = 12) -> str:
        from eaa.confidence import header

        dong = [
            f"Khảo sát kho tài liệu — {Path(self.archive).name}",
            "",
            header(self.confidence_level),
            "",
            f"  {len(self.entries)} tệp, {self.total_bytes / 1e6:.0f} MB sau giải nén",
            f"  {len(self.project_files)} tệp của dự án · "
            f"{len(self.vendored_files)} tệp thư viện đi kèm (đã tách riêng)",
        ]
        if self.extracted_to:
            dong.append(f"  Đã giải ra: {self.extracted_to}")

        dong += ["", "Phân loại theo FR-ING-01:"]
        for loai, n in sorted(self.by_kind.items(), key=lambda x: -x[1]):
            dong.append(f"  {loai:<10} {n}")

        dong += ["", "Theo đuôi tệp:"]
        for duoi, n in sorted(self.by_suffix.items(), key=lambda x: -x[1])[:10]:
            dong.append(f"  {duoi:<14} {n}")

        if self.libraries:
            dong += ["", f"Thư viện mã nguồn dựa vào ({len(self.libraries)}):"]
            dong += [f"  {t}" for t in self.libraries[:limit]]

        if self.registers:
            dong += ["", f"Thanh ghi bị chạm tới ({len(self.registers)}):"]
            dong.append("  " + ", ".join(self.registers[:24]))

        chan = self.pin_declarations()
        if chan:
            dong += ["", f"Khai báo trông như chân ({len(chan)} tên khác nhau):"]
            for ten, gia_tri, o_dau in chan[:limit * 2]:
                dong.append(f"  {ten} = {gia_tri}   ({o_dau})")

        for loai, nhan in (
            ("pdf", "Tài liệu PDF"),
            ("image", "Ảnh (sơ đồ, chụp màn hình, ảnh mạch)"),
            ("code", "Mã nguồn"),
        ):
            muc = [e for e in self.of_kind(loai) if not e.vendored]
            if not muc:
                continue
            dong += ["", f"{nhan} — {len(muc)} tệp của dự án:"]
            dong += [f"  {e.path}" for e in sorted(muc, key=lambda x: -x.size)[:limit]]
            if len(muc) > limit:
                dong.append(f"  … còn {len(muc) - limit} tệp nữa")

        dong += [
            "",
            "Mọi mục trên là ĐỀ XUẤT. Bản khảo sát này nói được thứ CÓ TRONG kho,",
            "không nói được thứ chúng NGHĨA LÀ GÌ: một `#define MOTOR_PIN 9` mới chỉ",
            "nói rằng có một hằng số tên như vậy, chưa nói rằng chân 9 nối vào động cơ.",
            "Bước tiếp: đọc để dựng hồ sơ phần cứng, rồi chốt tại G1.",
        ]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Giải nén an toàn
# --------------------------------------------------------------------------


def _kiem_an_toan(zf: zipfile.ZipFile, dich: Path) -> None:
    """Chặn ba kiểu kho nén không an toàn TRƯỚC khi ghi byte nào ra đĩa."""
    tong = 0
    goc = dich.resolve()

    for muc in zf.infolist():
        ten = muc.filename

        # Đường dẫn thoát ra ngoài thư mục đích (zip-slip).
        duong = (goc / ten).resolve()
        if not duong.is_relative_to(goc):
            raise ArchiveError(
                f"Kho nén chứa đường dẫn thoát ra ngoài thư mục đích: {ten!r}. "
                "Dừng trước khi ghi bất cứ thứ gì — đây là dạng kho nén được "
                "dựng để ghi đè tệp ngoài vùng giải."
            )

        # Liên kết mềm: giải ra rồi thì mọi phép đọc sau đó có thể đi ra ngoài.
        if (muc.external_attr >> 16) & 0o170000 == 0o120000:
            raise ArchiveError(f"Kho nén chứa liên kết mềm: {ten!r}. Không giải.")

        tong += muc.file_size
        if tong > MAX_TONG_BYTE:
            raise ArchiveError(
                f"Kho nén bung ra quá {MAX_TONG_BYTE / 1024**3:.0f} GB — dừng. "
                "Nếu đây là hồ sơ thật thì giải tay rồi trỏ Agent vào thư mục."
            )
        if muc.compress_size and muc.file_size / muc.compress_size > MAX_TI_LE_NEN:
            raise ArchiveError(
                f"Tệp {ten!r} có tỉ lệ nén {muc.file_size / muc.compress_size:.0f}:1 "
                "— gần như chắc chắn là dữ liệu dựng để bung, không phải tài liệu."
            )


def extract_archive(archive: str | Path, dest: str | Path) -> Path:
    """Giải nén sau khi đã kiểm an toàn. Trả về thư mục đích."""
    archive, dich = Path(archive), Path(dest)
    if not archive.is_file():
        raise ArchiveError(f"Không tìm thấy kho nén: {archive}")
    if not zipfile.is_zipfile(archive):
        raise ArchiveError(
            f"{archive} không phải kho .zip. Định dạng khác (.rar, .7z) cần công "
            "cụ ngoài — giải tay rồi trỏ Agent vào thư mục đã giải."
        )

    dich.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        _kiem_an_toan(zf, dich)
        for muc in zf.infolist():
            if muc.is_dir() or _la_rac(muc.filename):
                continue
            zf.extract(muc, dich)
    return dich


# --------------------------------------------------------------------------
# Rút dữ kiện từ mã nguồn — tất định, không dùng mô hình
# --------------------------------------------------------------------------


def _dong_cua(van_ban: str, vi_tri: int) -> int:
    return van_ban.count("\n", 0, vi_tri) + 1


def _la_thu_vien(duong_dan: str) -> bool:
    thap = "/" + duong_dan.replace("\\", "/").lower()
    return any(d in thap for d in _DAU_HIEU_THU_VIEN)


def _du_kien_tu_ma(ten_tep: str, noi_dung: str) -> list[CodeFact]:
    tv = _la_thu_vien(ten_tep)
    ket: list[CodeFact] = []

    for m in _INCLUDE.finditer(noi_dung):
        ket.append(
            CodeFact("include", "include", m.group(1), ten_tep, _dong_cua(noi_dung, m.start()), tv)
        )

    for m in _DEFINE.finditer(noi_dung):
        ten, gia_tri = m.group(1), m.group(2).strip()
        if len(gia_tri) > 80:
            continue
        loai = "pin" if any(t in ten.lower() for t in _GOI_Y_CHAN) else "define"
        ket.append(CodeFact(loai, ten, gia_tri, ten_tep, _dong_cua(noi_dung, m.start()), tv))

    for m in _PIN_MODE.finditer(noi_dung):
        ket.append(
            CodeFact(
                "pin_mode", m.group(1), m.group(2), ten_tep,
                _dong_cua(noi_dung, m.start()), tv,
            )
        )

    for m in _THANH_GHI.finditer(noi_dung):
        ket.append(
            CodeFact("register", m.group(1), "bị gán", ten_tep, _dong_cua(noi_dung, m.start()), tv)
        )

    return ket


def _doc_van_ban(duong_dan: Path, gioi_han: int = 400_000) -> str:
    try:
        return duong_dan.read_text(encoding="utf-8", errors="replace")[:gioi_han]
    except OSError:
        return ""


# --------------------------------------------------------------------------


def read_archive(
    archive: str | Path,
    *,
    extract_to: str | Path | None = None,
    max_code_files: int = 60,
) -> ArchiveSurvey:
    """Khảo sát một kho nén: kiểm kê, phân loại, rút dữ kiện từ mã.

    ``extract_to`` bỏ trống thì CHỈ đọc mục lục, không ghi gì ra đĩa — và khi
    ấy phần dữ kiện mã nguồn vẫn rút được, vì nội dung đọc thẳng từ kho.
    """
    from eaa.ingest import classify

    archive = Path(archive)
    if not archive.is_file():
        raise ArchiveError(f"Không tìm thấy kho nén: {archive}")
    if not zipfile.is_zipfile(archive):
        raise ArchiveError(
            f"{archive} không phải kho .zip. Định dạng khác cần giải tay trước."
        )

    muc_luc: list[ArchiveEntry] = []
    du_kien: list[CodeFact] = []

    with zipfile.ZipFile(archive) as zf:
        if extract_to is not None:
            _kiem_an_toan(zf, Path(extract_to))

        for muc in zf.infolist():
            if muc.is_dir() or _la_rac(muc.filename):
                continue
            muc_luc.append(
                ArchiveEntry(
                    path=muc.filename,
                    kind=classify(muc.filename),
                    size=muc.file_size,
                    vendored=_la_thu_vien(muc.filename),
                )
            )

        # Đọc mã nguồn theo thứ tự tệp LỚN NHẤT trước: tệp lớn thường là bản
        # chính, còn hàng chục tệp nhỏ hay là thư viện đi kèm.
        ma_nguon = sorted(
            (e for e in muc_luc if e.suffix in _DUOI_MA),
            key=lambda e: (e.vendored, -e.size),
        )[:max_code_files]
        for e in ma_nguon:
            try:
                noi_dung = zf.read(e.path).decode("utf-8", errors="replace")[:400_000]
            except (KeyError, OSError):
                continue
            du_kien += _du_kien_tu_ma(e.path, noi_dung)

    da_giai = ""
    if extract_to is not None:
        da_giai = str(extract_archive(archive, extract_to))

    return ArchiveSurvey(
        archive=str(archive),
        entries=tuple(muc_luc),
        facts=tuple(du_kien),
        extracted_to=da_giai,
    )
