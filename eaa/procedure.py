"""THỦ TỤC cho một ngoại vi — lớp K9 (V4, SL-180).

Tên module KHÔNG phải `skills`. Cái tên ấy đã thuộc về `eaa/skills.py`, một
khái niệm khác hẳn: một chuỗi lệnh CLI gọi được bằng một câu (TC-71). Hai thứ
cùng tên trong một kho là hai thứ sẽ bị nhầm, và lần nhầm đầu tiên đã xảy ra
ngay khi viết module này — bản nháp đầu ghi đè mất `skills.py`.

Xem `docs/KE_HOACH_VUOT_LEN.md` §4 và `docs/EAA_Backlog_Tien_hoa.xlsx` việc
B1 (trước là V4 — xem SL-181).

Sở cứ: bài arXiv 2603.19583 — mốc DUY NHẤT trong khảo sát có ablation đo được —
cho thấy tri thức do NGƯỜI nén theo từng ngoại vi nâng kết quả lên gần trần.

Kỹ năng KHÁC trích đoạn tài liệu ở chỗ nào
-------------------------------------------

Câu này phải trả lời được, nếu không thì kỹ năng chỉ là một chunk viết lại và
nó đang tiêu ngân sách của chunk mà không đổi lấy gì.

* **Chunk** là một TRÍCH ĐOẠN: nguyên văn của hãng, kèm số trang. Nó trả lời
  *"thanh ghi này có những bit nào"*.
* **Kỹ năng** là một THỦ TỤC đã được người nén: thứ tự thao tác bắt buộc, và
  những chỗ dễ làm sai. Nó trả lời *"làm theo thứ tự nào, và đã có ai ngã ở
  đâu"*.

Tài liệu của hãng gần như không bao giờ viết ra thứ tự bắt buộc — nó tả từng
thanh ghi một, còn thứ tự nằm trong đầu người đã làm rồi.

Ngân sách LẤY TỪ lớp trích đoạn, không cộng thêm
-------------------------------------------------

Đây là quyết định quan trọng nhất của module, và nó là quyết định về **phép
đo** chứ không phải về kiến trúc.

Nếu bật kỹ năng làm prompt dài thêm, thì mọi cải thiện đo được sau đó đều có
thể chỉ là *"nhiều ngữ cảnh hơn"*, và ablation không kết luận được gì. Lấy
ngân sách từ chính lớp trích đoạn giữ TỔNG không đổi giữa hai nhánh bật/tắt —
lúc ấy con số chênh lệch mới nói về kỹ năng.

Nó cũng là một lời hứa đúng: luận điểm của bài arXiv là tri thức nén THẮNG
trích đoạn thô. Nếu đúng thì kỹ năng phải tự trả được chỗ nó chiếm.

Ba luật, mỗi luật một bài kiểm
-------------------------------

1. **Chưa duyệt G2 thì không vào prompt.** Cùng luật của chunk — kỹ năng là
   tri thức, và tri thức vào kho qua đúng một cửa. Không có cửa sau.
2. **Mỗi bẫy phải có XUẤT XỨ.** Một bẫy không nói được nó đến từ đâu là một
   lời khai, và một lời khai nằm trong prompt thì mô hình đọc nó y như đọc một
   sự thật.
3. **Bẫy ĐÃ XẢY RA khác bẫy NGHĨ RA.** Bẫy rút từ một lần từ chối G3 có thật
   mang mức ĐÃ KIỂM; bẫy do người soạn nghĩ ra mang mức GIẢ ĐỊNH. Trộn hai
   hạng ấy là bỏ mất chính thứ làm kho này khác một tập lời khuyên.

Không một hằng số phần cứng nào trong tệp này
----------------------------------------------

Module này giữ MÔ HÌNH; dữ liệu kỹ năng nằm trong `packs/<nền tảng>/skills/`.
TC-38 quét điều ấy mỗi commit. Một tên thanh ghi lẻn vào đây là engine hết
trung lập, và nó lẻn vào rất dễ vì viết kỹ năng là việc đầy cám dỗ gõ thẳng.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA

__all__ = [
    "Bay",
    "KyNang",
    "KhoKyNang",
    "ProcedureError",
    "lop_ky_nang",
    "ngan_sach_co_ky_nang",
    "TT_DE_XUAT",
    "TT_DA_DUYET",
]

#: Trạng thái, cùng bộ từ với chunk: đề xuất → (G2) → đã duyệt.
#: Tên hằng mang tiền tố `TT_` để không đụng `TT_DE_XUAT`/`TT_DA_DUYET` của
#: `eaa/skills.py`, vốn là một vòng đời khác (proposed → verified → approved).
TT_DE_XUAT = "proposed"
TT_DA_DUYET = "active"

#: Mức tin cậy cho phép trên một bẫy. `KHÔNG KIỂM ĐƯỢC` cố ý vắng mặt: một bẫy
#: không kiểm được thì không có việc gì trong prompt, nó thuộc về câu hỏi cho
#: người.
MUC_CHO_PHEP = (DA_KIEM, SUY_RA, GIA_DINH)

#: Bao nhiêu token lớp thủ tục mượn của lớp trích đoạn khi được bật.
#:
#: Con số này là một CANH BẠC, không phải một phép đo, và phải được đọc như
#: vậy cho tới khi V2 giải nó. Căn cứ chọn 800: đo trên thủ tục DÀI NHẤT của dự
#: án mẫu (7 bước, 5 bẫy) thì trần 400 lược sạch mọi bẫy — lớp còn mỗi thứ tự
#: thao tác, tức mất nửa giá trị và phép ablation không còn đo cái nó định đo;
#: 800 là chỗ cả năm bẫy vừa đủ (786 token).
#:
#: Bản nháp của chú thích này gọi đích danh tên linh kiện, và TC-139 bắt được —
#: một tên phần cứng trong engine vẫn là một tên phần cứng trong engine, kể cả
#: khi nó chỉ đứng trong lời giải thích một con số.
#:
#: Đổi lại, lớp trích đoạn còn 700 trên 1.500. Đó đúng là điều luận điểm arXiv
#: khẳng định — tri thức nén thắng trích đoạn thô — nên đây cũng là chỗ luận
#: điểm ấy bị đem ra cược. Nếu ablation cho thấy thua, con số này phải giảm
#: chứ không phải phép đo bị giải thích lại.
MUON_TU_CHUNK = 800


class ProcedureError(Exception):
    """Kỹ năng sai cấu tạo. Ném lúc NẠP, không phải lúc dựng prompt."""


@dataclass(frozen=True)
class Bay:
    """Một chỗ dễ làm sai, kèm điều đúng và kèm xuất xứ.

    ``xuat_xu`` không được rỗng. Một bẫy không nói được nó đến từ đâu là một
    lời khai — và lời khai nằm trong prompt thì mô hình đọc nó y như sự thật.
    """

    mo_ta: str
    dung_la: str
    xuat_xu: str
    muc: str = GIA_DINH

    def __post_init__(self) -> None:
        for ten in ("mo_ta", "dung_la", "xuat_xu"):
            if not str(getattr(self, ten)).strip():
                raise ProcedureError(f"bẫy thiếu trường `{ten}` — chạy `eaa skills lint`")
        if self.muc not in MUC_CHO_PHEP:
            raise ProcedureError(
                f"mức tin cậy {self.muc!r} không hợp lệ; chỉ nhận "
                f"{', '.join(MUC_CHO_PHEP)}"
            )

    def mot_dong(self) -> str:
        return f"[{self.muc}] {self.mo_ta} → {self.dung_la}  ({self.xuat_xu})"


@dataclass(frozen=True)
class KyNang:
    """Thủ tục đã nén cho MỘT ngoại vi."""

    id: str
    peripheral: str
    thu_tu: tuple[str, ...] = ()
    bay: tuple[Bay, ...] = ()
    chunks: tuple[str, ...] = ()
    status: str = TT_DE_XUAT
    source: str = ""
    note: str = ""

    @property
    def da_duyet(self) -> bool:
        """Chỉ kỹ năng đã qua G2 mới được vào prompt — cùng luật của chunk."""
        return self.status == TT_DA_DUYET

    @property
    def co_bang_chung_that(self) -> bool:
        """Có ít nhất một bẫy rút từ chuyện ĐÃ XẢY RA."""
        return any(b.muc == DA_KIEM for b in self.bay)

    def render(self) -> str:
        """Dạng chữ đưa vào prompt, và cũng là dạng người đọc ở G2."""
        dong = [f"### {self.peripheral} — {self.id}"]
        if self.thu_tu:
            dong.append("THỨ TỰ BẮT BUỘC:")
            dong += [f"  {i}. {b}" for i, b in enumerate(self.thu_tu, 1)]
        if self.bay:
            dong.append("BẪY:")
            dong += [f"  - {b.mot_dong()}" for b in self.bay]
        if self.chunks:
            dong.append(f"Dựa trên trích đoạn: {', '.join(self.chunks)}")
        return "\n".join(dong)


def _doc_bay(muc: Mapping[str, Any], ky: str) -> Bay:
    try:
        return Bay(
            mo_ta=str(muc.get("de_sai", "")),
            dung_la=str(muc.get("dung_la", "")),
            xuat_xu=str(muc.get("xuat_xu", "")),
            muc=str(muc.get("muc", GIA_DINH)),
        )
    except ProcedureError as e:
        raise ProcedureError(f"kỹ năng {ky}: {e}") from e


@dataclass
class KhoKyNang:
    """Kho kỹ năng của MỘT nền tảng, nạp từ `packs/<nền tảng>/skills/`.

    Vắng thư mục thì kho rỗng và mọi thứ vẫn chạy. Đây là luật 1 của kế hoạch:
    thêm một nguồn tri thức không được làm hỏng đường chạy khi nguồn ấy vắng
    mặt.
    """

    muc: tuple[KyNang, ...] = ()

    @classmethod
    def nap(cls, thu_muc: Path | str) -> "KhoKyNang":
        goc = Path(thu_muc)
        if not goc.is_dir():
            return cls()
        try:
            import yaml
        except ImportError as e:  # pragma: no cover
            raise ProcedureError("cần PyYAML để đọc kỹ năng") from e

        ra: list[KyNang] = []
        for tep in sorted(goc.glob("*.yaml")):
            d = yaml.safe_load(tep.read_text(encoding="utf-8")) or {}
            if not isinstance(d, dict):
                raise ProcedureError(f"{tep.name}: nội dung phải là một ánh xạ")
            ky = str(d.get("id") or tep.stem)
            ngoai_vi = str(d.get("peripheral", "")).strip()
            if not ngoai_vi:
                raise ProcedureError(f"{tep.name}: thiếu `peripheral`")
            ra.append(KyNang(
                id=ky,
                peripheral=ngoai_vi,
                thu_tu=tuple(str(x) for x in d.get("thu_tu", ())),
                bay=tuple(_doc_bay(b, ky) for b in d.get("bay", ())),
                chunks=tuple(str(x) for x in d.get("chunks", ())),
                status=str(d.get("status", TT_DE_XUAT)),
                source=str(d.get("source", "")),
                note=str(d.get("note", "")),
            ))
        return cls(muc=tuple(ra))

    @classmethod
    def nap_nhieu(cls, *thu_muc: Path | str) -> "KhoKyNang":
        """Gộp nhiều nguồn — pack và dự án.

        Thủ tục của NGOẠI VI VI ĐIỀU KHIỂN (bus, bộ định thời, chân) thuộc
        Platform Pack; thủ tục của LINH KIỆN NGOÀI gắn trên mạch thuộc dự án.
        Gộp ở đây chứ không gộp trong composer, để chỗ quyết định tầng nào giữ
        cái gì nằm đúng một nơi.

        Trùng `id` giữa hai nguồn là lỗi, không phải chuyện nguồn sau đè nguồn
        trước: hai thủ tục cùng tên mà khác nội dung thì cái nào đang vào
        prompt là chuyện của thứ tự đối số, và đó không phải câu trả lời được.
        """
        ra: list[KyNang] = []
        thay: dict[str, str] = {}
        for d in thu_muc:
            for k in cls.nap(d).tat_ca():
                if k.id in thay:
                    raise ProcedureError(
                        f"thủ tục {k.id!r} có ở cả {thay[k.id]} và {d} — "
                        "đổi tên một trong hai"
                    )
                thay[k.id] = str(d)
                ra.append(k)
        return cls(muc=tuple(ra))

    # ------------------------------------------------------------------

    def tat_ca(self) -> tuple[KyNang, ...]:
        return self.muc

    def da_duyet(self) -> tuple[KyNang, ...]:
        return tuple(k for k in self.muc if k.da_duyet)

    def cho_duyet(self) -> tuple[KyNang, ...]:
        return tuple(k for k in self.muc if not k.da_duyet)

    def cho_ngoai_vi(self, ten: Iterable[str]) -> tuple[KyNang, ...]:
        """Kỹ năng ĐÃ DUYỆT của những ngoại vi được nêu.

        Khớp không phân biệt hoa thường, nhưng khớp CHÍNH XÁC cả tên — cùng lý
        do `Chunk.matches_register` không khớp tiền tố: một kỹ năng "gần đúng"
        đẻ ra thủ tục có vẻ có nguồn gốc, và đó là hạng ảo giác nguy hiểm nhất.
        """
        can = {t.strip().lower() for t in ten if t and t.strip()}
        return tuple(k for k in self.da_duyet() if k.peripheral.lower() in can)

    def chunk_thieu(self, co_that: Iterable[str]) -> list[str]:
        """Kỹ năng trỏ vào trích đoạn KHÔNG có trong kho.

        Cùng hạng lỗi TC-145 đã chặn ở gợi ý CLI: một trích dẫn trỏ vào chỗ
        không tồn tại tệ hơn không trích dẫn, vì nó trông như có nguồn gốc.
        """
        co = {str(x) for x in co_that}
        return [f"{k.id} → {c}" for k in self.muc for c in k.chunks if c not in co]


def lop_ky_nang(
    ky_nang: Iterable[KyNang], *, tran: int = 0, dem: Any = None
) -> str:
    """Lớp K9 cho bộ ghép prompt. Rỗng khi không có thủ tục nào đã duyệt.

    Vượt trần thì BỎ NGUYÊN MỤC, không cắt giữa câu — một thủ tục bị cắt cụt
    vẫn trông như một thủ tục, và nhát cắt có thể rơi đúng vào cái bẫy quan
    trọng nhất. Thứ tự bỏ: bẫy mức thấp trước, vì bẫy ĐÃ KIỂM là bẫy đã xảy ra
    thật trên chính dự án này.

    Và cái gì bị bỏ thì lớp NÓI RA. Một lớp lặng lẽ cắt bớt sẽ được đọc như
    một lớp đầy đủ, và người đọc prompt không có cách nào biết khác đi.
    """
    muc = [k for k in ky_nang if k.da_duyet]
    if not muc:
        return ""

    def dung(k: KyNang) -> KyNang:
        return k

    dau = [
        "## THỦ TỤC ĐÃ ĐÚC KẾT CHO NGOẠI VI NÀY",
        "",
        "Đây KHÔNG phải trích đoạn tài liệu. Đây là thứ tự thao tác và những",
        "chỗ đã có người làm sai — tài liệu của hãng tả từng thanh ghi, nó",
        "không nói thứ tự.",
        f"Bẫy mang nhãn [{DA_KIEM}] là bẫy ĐÃ XẢY RA trên chính dự án này.",
        "",
    ]
    if not tran:
        return "\n".join(dau + [k.render() for k in muc])

    do = dem or (lambda v: max(1, len(v) // 4))
    thu_tu_bo = (GIA_DINH, SUY_RA, DA_KIEM)
    da_bo: dict[str, int] = {}
    hien = [KyNang(**{**k.__dict__}) for k in muc]

    def dung_van() -> str:
        than = "\n".join(dau + [k.render() for k in hien])
        if da_bo:
            # Ghi chú GOM THÀNH SỐ ĐẾM, không liệt kê từng mục. Bản đầu ghi một
            # dòng cho mỗi bẫy bị lược, nên chính ghi chú ấy dài thêm mỗi vòng
            # và ăn hết chỗ nó vừa giải phóng — vòng lược không hội tụ, và nó
            # lược luôn cả bẫy ĐÃ KIỂM đáng lẽ phải giữ lại. TC-139 bắt được.
            than += ("\n\nĐÃ LƯỢC vì hết ngân sách lớp: "
                     + ", ".join(f"{n} bẫy [{m}]" for m, n in da_bo.items())
                     + ". Hỏi người nếu ngoại vi này là chỗ đang mắc.")
        return than

    for muc_bo in thu_tu_bo:
        while do(dung_van()) > tran:
            ung = [(i, j) for i, k in enumerate(hien)
                   for j, b in enumerate(k.bay) if b.muc == muc_bo]
            if not ung:
                break
            i, j = ung[-1]
            k = hien[i]
            da_bo[muc_bo] = da_bo.get(muc_bo, 0) + 1
            hien[i] = KyNang(**{**k.__dict__,
                               "bay": k.bay[:j] + k.bay[j + 1:]})
    return dung_van()


def ngan_sach_co_ky_nang(
    goc: Mapping[str, int], *, bat: bool, muon: int = MUON_TU_CHUNK
) -> dict[str, int]:
    """Ngân sách lớp khi bật/tắt kỹ năng — TỔNG KHÔNG ĐỔI.

    Lớp kỹ năng **mượn** của lớp trích đoạn chứ không cộng thêm. Nếu bật kỹ
    năng làm prompt dài thêm thì mọi chênh lệch đo được sau đó đều có thể chỉ
    là *"nhiều ngữ cảnh hơn"*, và phép ablation không kết luận được gì.

    Đây cũng là một lời hứa đúng với luận điểm đang kiểm: tri thức nén được cho
    là THẮNG trích đoạn thô, vậy nó phải tự trả được chỗ nó chiếm.
    """
    ra = dict(goc)
    if not bat:
        ra["skills"] = 0
        return ra
    co = ra.get("datasheet_chunks", 0)
    that_su = min(muon, co)
    ra["datasheet_chunks"] = co - that_su
    ra["skills"] = that_su
    return ra
