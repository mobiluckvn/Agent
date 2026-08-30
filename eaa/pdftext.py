"""Rút chữ từ PDF — bằng thư viện chuẩn, không thêm phụ thuộc.

EAA-AIS-05 §6.1 (đầu vào đa phương thức); FR-ING-01, NFR-04.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-94.

Khoảng trống module này lấp
----------------------------

``eaa survey`` kiểm kê được **có những tệp gì** trong một kho hồ sơ, và rút
được dữ kiện từ mã nguồn. Nó không mở được PDF. Nhưng tài liệu quy trình của
một dự án nhúng gần như luôn ở dạng PDF — hồ sơ robot dùng để kiểm thử sản
phẩm này có đúng hai tệp như vậy, và chúng chứa chính thứ Agent được hỏi.

Đo được trong bài kiểm ngày 31/08/2026: thiếu năng lực này, Agent đi tìm quy
trình, không thấy, rồi **trả lời từ một tài liệu khác** — xem SL-95.

Vì sao tự viết thay vì thêm một thư viện
-----------------------------------------

NFR-04 chốt sản phẩm chỉ phụ thuộc Python, toolchain và Git. Thêm một thư
viện đọc PDF là thêm một thứ có thể lên phiên bản giữa kỳ thực nghiệm — đúng
loại rủi ro R1 mà EAA-STP-04 đã lường.

Phần cần dùng của PDF lại hẹp: giải nén luồng bằng ``zlib`` (có sẵn), đọc bảng
``ToUnicode`` để ánh xạ mã glyph sang Unicode, rồi bóc chuỗi giữa các toán tử
vẽ chữ. Không cần dựng lại bố cục, không cần hiểu hình.

Điều module này KHÔNG làm, và nói thẳng ra
-------------------------------------------

* **Không đọc được PDF quét ảnh.** Chữ nằm trong ảnh thì phải OCR, và OCR là
  một công cụ ngoài. Khi gặp, module trả về kết quả rỗng kèm lý do — chứ không
  trả về một chuỗi rác trông như chữ.
* **Không dựng lại bố cục.** Bảng biểu sẽ ra thành các dòng rời. Đủ để đọc
  hiểu và để đưa vào prompt; không đủ để trích một ô cụ thể trong bảng.
* **Không giải mã mọi PDF trên đời.** Mã hóa, font không kèm ``ToUnicode``,
  luồng nén kiểu khác — đều có thật. Module báo phần rút được và phần bỏ sót
  thay vì im lặng.

Bài học từ nguyên mẫu: phân giải font THEO TỪNG TRANG
------------------------------------------------------

Gộp bảng font của mọi trang lại rồi tra chung là sai, và sai theo cách khó
thấy: hai trang đều đặt tên tài nguyên là ``/F2`` nhưng trỏ tới hai đối tượng
font khác nhau. Gộp lại thì trang sau ghi đè trang trước, và chữ của một trang
bị giải mã bằng bảng của trang kia — ra một văn bản **gần đúng**, rụng mất
đúng những ký tự có dấu. Gần đúng ở đây tệ hơn hỏng hẳn, vì nó trông như đọc
được.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "PdfError",
    "PdfPage",
    "PdfText",
    "extract_text",
    "MAX_BYTES",
    "KERNING_LA_KHOANG_TRANG",
]

#: Trần kích thước tệp. Một PDF lớn hơn thế gần như luôn là tài liệu quét ảnh
#: — thứ module này không đọc được — và giải nén nó chỉ tốn bộ nhớ.
MAX_BYTES = 80 * 1024 * 1024

#: Trong mảng ``TJ``, số âm là dịch chuyển ngược (kerning). Dịch đủ xa thì đó
#: là khoảng cách giữa hai từ, không phải chỉnh nét giữa hai chữ cái.
#:
#: Ngưỡng 100 phần nghìn em là quy ước quen dùng: nhỏ hơn là kerning trong một
#: từ, lớn hơn là dấu cách mà trình sinh PDF đã bỏ đi để tiết kiệm chỗ. Không
#: có ngưỡng này thì mọi từ dính liền nhau — đo được ở nguyên mẫu.
KERNING_LA_KHOANG_TRANG = 100.0

_OBJ = re.compile(rb"(\d+)\s+0\s+obj\b(.*?)\bendobj", re.S)
_STREAM = re.compile(rb"stream\r?\n")
_TO_UNICODE = re.compile(rb"/ToUnicode\s+(\d+)\s+0\s+R")
_FONT_DICT = re.compile(rb"/Font\s*<<(.*?)>>", re.S)
_FONT_REF = re.compile(rb"/(\w+)\s+(\d+)\s+0\s+R")
_RESOURCES_REF = re.compile(rb"/Resources\s+(\d+)\s+0\s+R")
_CONTENTS = re.compile(rb"/Contents\s+(?:(\d+)\s+0\s+R|\[(.*?)\])", re.S)
_REF = re.compile(rb"(\d+)\s+0\s+R")

#: Toán tử trong luồng nội dung mà module này quan tâm.
_TOKEN = re.compile(
    rb"/(\w+)\s+[-\d.]+\s+Tf"          # 1: đổi font
    rb"|<([0-9A-Fa-f\s]*)>\s*Tj"       # 2: chuỗi hex
    rb"|\[(.*?)\]\s*TJ"                # 3: mảng có kerning
    rb"|(T\*|Td|TD|'|\")"              # 4: xuống dòng
    rb"|[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)\s+Tm",  # 5,6: đặt lại vị trí
    re.S,
)

#: Chênh lệch tọa độ dọc (đơn vị PDF, 1/72 inch) coi là sang dòng mới.
#:
#: Nhiều trình sinh PDF không dùng ``Td``/``T*`` mà đặt lại ma trận chữ
#: (``Tm``) trước từng đoạn — tài liệu dùng để kiểm sản phẩm này có 723 lần
#: ``Tm`` và không một lần ``Td``. Coi mọi ``Tm`` là xuống dòng thì ra 723
#: dòng rời; coi mọi ``Tm`` là dấu cách thì mất hết cấu trúc đoạn. Nên phải
#: nhìn vào tọa độ: đổi chỗ theo chiều dọc là dòng mới, chỉ đổi theo chiều
#: ngang là khoảng cách giữa hai từ trên cùng một dòng.
NGUONG_DONG_MOI = 2.0
_HEX_TRONG_MANG = re.compile(rb"<([0-9A-Fa-f\s]*)>|([-\d.]+)")


class PdfError(Exception):
    """Không đọc được PDF."""


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str
    unmapped: int = 0

    @property
    def empty(self) -> bool:
        return not self.text.strip()


@dataclass
class PdfText:
    """Chữ rút được, kèm những chỗ rút không ra."""

    path: str = ""
    pages: tuple[PdfPage, ...] = ()
    #: Số mã glyph không tra được trong bảng ToUnicode.
    unmapped: int = 0
    note: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def empty(self) -> bool:
        return not self.text.strip()

    @property
    def confidence_level(self) -> str:
        """SUY RA khi rút được; KHÔNG KIỂM ĐƯỢC khi rỗng.

        Không bao giờ ĐÃ KIỂM: bộ rút này bỏ bố cục, có thể rụng ký tự ở font
        thiếu bảng ToUnicode, và không đọc được tài liệu quét ảnh. Nó cho một
        bản đọc được, không cho một bản sao trung thành.
        """
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return KHONG_KIEM_DUOC if self.empty else SUY_RA

    def render(self, *, limit: int = 3000) -> str:
        from eaa.confidence import header

        dong = [f"Chữ rút từ {self.path or 'PDF'}", "", header(self.confidence_level), ""]
        if self.empty:
            dong += [
                "  Không rút được chữ nào.",
                "",
                "  Thường là PDF QUÉT ẢNH: chữ nằm trong hình, không phải trong "
                "luồng văn bản. Đọc nó cần OCR — một công cụ ngoài mà hệ này "
                "chưa có. Tôi báo rỗng thay vì trả về một chuỗi rác trông như chữ.",
            ]
            if self.note:
                dong += ["", f"  {self.note}"]
            return "\n".join(dong)

        dong.append(f"  {len(self.pages)} trang · {len(self.text)} ký tự")
        if self.unmapped:
            dong.append(
                f"  ⚠ {self.unmapped} mã glyph không tra được trong bảng ToUnicode "
                "— những chỗ ấy rụng ký tự. Thường là font nhúng thiếu bảng."
            )
        dong += ["", "  Bố cục KHÔNG được dựng lại: bảng biểu ra thành dòng rời.", ""]
        dong.append(self.text if len(self.text) <= limit else self.text[:limit] + "\n…(cắt)")
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Bóc đối tượng
# --------------------------------------------------------------------------


def _giai_nen(body: bytes) -> bytes | None:
    m = _STREAM.search(body)
    if not m:
        return None
    ket_thuc = body.find(b"endstream", m.end())
    tho = body[m.end():ket_thuc if ket_thuc > 0 else len(body)]
    if b"/FlateDecode" not in body:
        return tho
    try:
        return zlib.decompress(tho)
    except zlib.error:
        # Vài trình sinh PDF để lại byte thừa ở cuối; thử cắt dần.
        for bot in (1, 2):
            try:
                return zlib.decompressobj().decompress(tho[:-bot] if bot else tho)
            except zlib.error:
                continue
        return None


def _bung_luong_doi_tuong(objs: dict[int, bytes]) -> dict[int, bytes]:
    """Bung các đối tượng nằm trong luồng nén ``/ObjStm``.

    Từ PDF 1.5, phần lớn đối tượng không còn nằm rời ở thân tệp mà bị gom vào
    những luồng nén. Tài liệu dùng để kiểm sản phẩm này chỉ để lộ 73 đối tượng
    rời trong khi thật ra có hơn bảy trăm — và **bảng ToUnicode của vài font
    nằm trong số bị giấu**. Hệ quả không phải là đọc hỏng: nó là đọc GẦN ĐÚNG,
    rụng đúng những ký tự có dấu, và một bản gần đúng trông như đọc được là thứ
    tệ hơn một bản hỏng hẳn.

    Cấu trúc luồng: từ điển có ``/N`` (số đối tượng) và ``/First`` (chỗ bắt đầu
    phần thân). Phần đầu là ``N`` cặp ``<số hiệu> <độ lệch>``; thân nằm ngay
    sau, mỗi đối tượng ở ``First + độ lệch``.
    """
    them: dict[int, bytes] = {}
    for than in list(objs.values()):
        if b"/ObjStm" not in than:
            continue
        mn = re.search(rb"/N\s+(\d+)", than)
        mf = re.search(rb"/First\s+(\d+)", than)
        d = _giai_nen(than)
        if not (mn and mf and d):
            continue
        so_luong, dau_than = int(mn.group(1)), int(mf.group(1))
        cap = re.findall(rb"(\d+)\s+(\d+)", d[:dau_than])[:so_luong]
        for i, (so, lech) in enumerate(cap):
            bat_dau = dau_than + int(lech)
            ket_thuc = (
                dau_than + int(cap[i + 1][1]) if i + 1 < len(cap) else len(d)
            )
            if 0 <= bat_dau < ket_thuc <= len(d):
                them.setdefault(int(so), d[bat_dau:ket_thuc])
    return them


def _doc_cmap(data: bytes) -> dict[int, str]:
    """Đọc bảng ToUnicode: ``beginbfchar`` và ``beginbfrange``."""
    bang: dict[int, str] = {}
    for khoi in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for nguon, dich in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", khoi):
            bang[int(nguon, 16)] = _hex_sang_chu(dich)
    for khoi in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dich in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", khoi
        ):
            a, b, goc = int(lo, 16), int(hi, 16), int(dich, 16)
            if b - a > 65535:
                continue
            for k in range(a, b + 1):
                bang[k] = chr(goc + k - a)
    return bang


def _hex_sang_chu(h: bytes) -> str:
    ra = []
    for i in range(0, len(h) - 3, 4):
        try:
            ra.append(chr(int(h[i:i + 4], 16)))
        except ValueError:
            pass
    return "".join(ra)


# --------------------------------------------------------------------------
# Rút chữ
# --------------------------------------------------------------------------


def extract_text(path: str | Path, *, max_pages: int = 0) -> PdfText:
    """Rút chữ từ một tệp PDF. Không ném khi PDF khó — báo rỗng kèm lý do."""
    p = Path(path)
    if not p.is_file():
        raise PdfError(f"Không có tệp: {p}")
    if p.stat().st_size > MAX_BYTES:
        raise PdfError(
            f"{p.name} lớn hơn trần {MAX_BYTES // 1024 // 1024} MB. PDF lớn thế "
            "gần như luôn là tài liệu quét ảnh — thứ bộ rút này không đọc được."
        )

    raw = p.read_bytes()
    if not raw.startswith(b"%PDF"):
        raise PdfError(f"{p.name} không phải tệp PDF (thiếu chữ ký %PDF)")

    objs = {int(m.group(1)): m.group(2) for m in _OBJ.finditer(raw)}
    objs.update(_bung_luong_doi_tuong(objs))
    if not objs:
        return PdfText(path=str(p), note=(
            "Không đọc được đối tượng nào. PDF này có thể dùng luồng đối tượng "
            "nén (/ObjStm) hoặc đã bị mã hóa."
        ))

    # Bảng ToUnicode theo SỐ HIỆU đối tượng font.
    cmap_theo_font: dict[int, dict[int, str]] = {}
    for so, than in objs.items():
        m = _TO_UNICODE.search(than)
        if not m:
            continue
        d = _giai_nen(objs.get(int(m.group(1)), b""))
        if d:
            cmap_theo_font[so] = _doc_cmap(d)

    trang = _tim_trang(objs)
    if not trang:
        # Không nhận ra cấu trúc trang thì lùi về: coi mọi luồng có toán tử vẽ
        # chữ là một trang. Kém chính xác hơn, nhưng vẫn hơn trả về rỗng.
        trang = [(so, than) for so, than in objs.items()
                 if (d := _giai_nen(than)) and (b"Tj" in d or b"TJ" in d)]

    ket: list[PdfPage] = []
    tong_hut = 0
    for i, (so_trang, than_trang) in enumerate(trang, 1):
        if max_pages and i > max_pages:
            break
        chu, hut = _doc_mot_trang(than_trang, objs, cmap_theo_font)
        tong_hut += hut
        if chu.strip():
            ket.append(PdfPage(number=i, text=chu, unmapped=hut))

    ra = PdfText(path=str(p), pages=tuple(ket), unmapped=tong_hut)
    if ra.empty:
        ra.note = (
            "Đọc được cấu trúc nhưng không có luồng văn bản nào — dấu hiệu của "
            "PDF quét ảnh."
        )
    return ra


def _tim_trang(objs: dict[int, bytes]) -> list[tuple[int, bytes]]:
    return [(so, than) for so, than in sorted(objs.items()) if b"/Type" in than
            and re.search(rb"/Type\s*/Page\b", than)]


def _bang_font_cua_trang(
    than_trang: bytes, objs: dict[int, bytes], cmap_theo_font: dict[int, dict[int, str]]
) -> dict[str, tuple[int, dict[int, str] | None]]:
    """Ánh xạ tên tài nguyên (``F2``) → bảng ToUnicode, RIÊNG cho trang này.

    Đây là chỗ nguyên mẫu đầu tiên sai: gộp bảng của mọi trang rồi tra chung.
    Hai trang cùng đặt tên ``/F2`` cho hai font khác nhau là chuyện bình thường,
    và gộp lại thì chữ của trang này bị giải mã bằng bảng của trang kia — ra một
    văn bản gần đúng, rụng đúng những ký tự có dấu.
    """
    tai_nguyen = than_trang
    m = _RESOURCES_REF.search(than_trang)
    if m:
        tai_nguyen = objs.get(int(m.group(1)), b"")

    bang: dict[str, tuple[int, dict[int, str] | None]] = {}
    for md in _FONT_DICT.finditer(tai_nguyen):
        for ten, so in _FONT_REF.findall(md.group(1)):
            n = int(so)
            cm = cmap_theo_font.get(n)
            if cm:
                # Type0 + ToUnicode: mã 2 byte, tra bảng.
                bang[ten.decode("latin-1")] = (2, cm)
                continue
            than_font = objs.get(n, b"")
            if b"/WinAnsiEncoding" in than_font:
                # Font đơn giản: mã MỘT byte theo cp1252.
                #
                # Đây là chỗ nguyên mẫu sai lần thứ hai, và sai êm hơn lần
                # trước: gặp font không có ToUnicode, nó GIỮ NGUYÊN bảng của
                # font trước đó rồi giải mã tiếp như thể không có gì xảy ra.
                # Kết quả là rụng đúng những ký tự cp1252 có mà bảng kia không
                # có — tức là toàn bộ nguyên âm có dấu sắc/huyền/mũ của tiếng
                # Việt. Văn bản vẫn đọc được, chỉ sai ở chỗ ít ai soi.
                bang[ten.decode("latin-1")] = (1, None)
    return bang


def _noi_dung_cua_trang(than_trang: bytes, objs: dict[int, bytes]) -> bytes:
    m = _CONTENTS.search(than_trang)
    if not m:
        return _giai_nen(than_trang) or b""
    if m.group(1):
        return _giai_nen(objs.get(int(m.group(1)), b"")) or b""
    phan = [_giai_nen(objs.get(int(x), b"")) or b"" for x in _REF.findall(m.group(2) or b"")]
    return b"\n".join(phan)


def _doc_mot_trang(
    than_trang: bytes, objs: dict[int, bytes], cmap_theo_font: dict[int, dict[int, str]]
) -> tuple[str, int]:
    noi_dung = _noi_dung_cua_trang(than_trang, objs)
    if not noi_dung:
        return "", 0
    bang = _bang_font_cua_trang(than_trang, objs, cmap_theo_font)

    ra: list[str] = []
    # Mặc định 1 byte / cp1252: khi luồng chưa có ``Tf`` nào, đoán một font
    # đơn giản an toàn hơn đoán một font 2 byte — đoán sai bề rộng thì mọi ký
    # tự sau đó lệch, còn đoán sai bảng tra thì chỉ rụng vài ký tự.
    hien_tai: tuple[int, dict[int, str] | None] = (1, None)
    hut = 0
    y_truoc: float | None = None

    for tok in _TOKEN.finditer(noi_dung):
        if tok.group(5) is not None:
            # Đặt lại ma trận chữ: dọc thì sang dòng, ngang thì cách một dấu.
            try:
                y = float(tok.group(6))
            except ValueError:
                continue
            if y_truoc is not None:
                ra.append("\n" if abs(y - y_truoc) > NGUONG_DONG_MOI else " ")
            y_truoc = y
        elif tok.group(1):
            hien_tai = bang.get(tok.group(1).decode("latin-1"), hien_tai)
        elif tok.group(2) is not None:
            chu, h = _giai_hex(tok.group(2), hien_tai)
            ra.append(chu)
            hut += h
        elif tok.group(3) is not None:
            for mm in _HEX_TRONG_MANG.finditer(tok.group(3)):
                if mm.group(1) is not None:
                    chu, h = _giai_hex(mm.group(1), hien_tai)
                    ra.append(chu)
                    hut += h
                elif mm.group(2):
                    try:
                        if -float(mm.group(2)) >= KERNING_LA_KHOANG_TRANG:
                            ra.append(" ")
                    except ValueError:
                        pass
        else:
            ra.append("\n")

    chu = "".join(ra)
    chu = re.sub(r"[ \t]+", " ", chu)
    chu = re.sub(r"\n[ \t]+", "\n", chu)
    chu = re.sub(r"\n{3,}", "\n\n", chu)
    return chu.strip(), hut


def _giai_hex(h: bytes, font: tuple[int, dict[int, str] | None]) -> tuple[str, int]:
    """Giải một chuỗi hex theo đúng bề rộng mã của font đang dùng."""
    rong, cmap = font
    sach = bytes(h).replace(b"\n", b"").replace(b"\r", b"").replace(b" ", b"")
    if len(sach) % 2:
        sach += b"0"

    if rong == 1 or cmap is None:
        try:
            return bytes.fromhex(sach.decode("ascii")).decode("cp1252", errors="replace"), 0
        except (ValueError, UnicodeDecodeError):
            return "", 0

    ra: list[str] = []
    hut = 0
    for i in range(0, len(sach) - 3, 4):
        try:
            ma = int(sach[i:i + 4], 16)
        except ValueError:
            continue
        chu = cmap.get(ma)
        if chu is None:
            hut += 1
        else:
            ra.append(chu)
    return "".join(ra), hut
