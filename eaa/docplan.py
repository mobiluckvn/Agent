"""Tài liệu đích danh, trang đích danh, và errata theo đúng rev — N-004, N-030, N-037.

EAA-AIS-05 §6.1–6.2 (thu nhận và bậc thang tìm kiếm), FR-GAP-02, FR-ING-02;
công đoạn G0 và G3. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-50.

Ba câu hỏi, và câu thứ ba là câu hay bị bỏ nhất
------------------------------------------------

1. **Cần những tài liệu nào?** (N-004) Không phải "hãy đưa datasheet" mà là một
   danh sách ĐÍCH DANH: datasheet của chip, tài liệu tham chiếu, sơ đồ nguyên
   lý của bo, datasheet của TỪNG linh kiện, và errata.
2. **Cần trang nào trong đó?** (N-030) Một datasheet vài trăm trang chỉ cho ra
   vài chục trích đoạn có ích. Nạp cả tệp là cách chắc chắn để vừa tốn token
   vừa kéo vào những trang chẳng liên quan.
3. **Chip này rev mấy, và rev ấy có lỗi gì đã công bố?** (N-037)

Câu thứ ba đáng nói riêng. Errata là tài liệu hay bị quên nhất, và quên nó thì
mã **đúng theo datasheet** vẫn chạy sai — một loại lỗi mà mọi cổng kiểm chứng
của hệ thống này đều cho qua, vì mã thật sự đúng với thứ nó được bảo. Chỉ có
tài liệu mới nói được, và chỉ có đúng rev mới nói đúng.

Vì sao "chưa biết rev" không được coi là "không có lỗi"
--------------------------------------------------------

Cám dỗ ở đây rất mạnh: chưa hỏi được rev thì để trống, và một danh sách errata
trống trông y hệt một con chip sạch. Nên :class:`ErrataAnalysis` phân biệt rõ
*chưa tra được* với *đã tra và không có* — cùng một nguyên tắc với phép đọc
ngược sau khi nạp ở ``eaa/flash.py``.

Engine suy được gì, và không suy được gì
-----------------------------------------

Suy được: danh sách tài liệu cần (từ hồ sơ phần cứng), thanh ghi nào còn thiếu
trích đoạn (từ đồ thị tri thức), module nào chạm vào một lỗi đã công bố (từ
``uses`` của backlog). Cả ba đều là phép bắc cầu trên dữ liệu của dự án.

Không suy được: đường dẫn tới trang tài liệu của hãng, và nội dung errata. Hai
thứ ấy phải TRA — và mọi thứ tra về đều là *proposed fact*, đi qua G2 như mọi
tri thức khác, với nguồn bị chặn trong danh sách cho phép (FR-GAP-02).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "DocPlanError",
    "DocKind",
    "DocumentNeed",
    "DocumentPlan",
    "PageRequest",
    "PagePlan",
    "ErrataItem",
    "ErrataAnalysis",
    "ErrataImpact",
    "LlmDocLookup",
    "ERRATA_FILE",
    "REV_CHUA_BIET",
]

#: Kho errata ở tầng dự án, cạnh constraints.yaml.
ERRATA_FILE = "errata.yaml"

#: Chưa hỏi được rev silicon. KHÁC hẳn "đã tra và chip sạch".
REV_CHUA_BIET = ""


class DocKind:
    """Loại tài liệu. Danh sách đóng để bảng kiểm không thành trường tự do."""

    DATASHEET = "datasheet"
    REFERENCE_MANUAL = "reference_manual"
    SCHEMATIC = "schematic"
    ERRATA = "errata"
    APP_NOTE = "application_note"
    USER_MANUAL = "user_manual"

    ALL: tuple[str, ...] = (
        DATASHEET,
        REFERENCE_MANUAL,
        SCHEMATIC,
        ERRATA,
        APP_NOTE,
        USER_MANUAL,
    )


class DocPlanError(Exception):
    """Kế hoạch tài liệu sai lược đồ, hoặc thiếu dữ kiện để lập."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# N-004 — cần những tài liệu nào, đích danh
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentNeed:
    """Một tài liệu dự án cần, và vì sao cần."""

    kind: str
    subject: str
    why: str
    required: bool = True
    #: Đường dẫn trang chính thức, nếu đã tra được. Luôn trong danh sách cho phép.
    official_source: str = ""
    #: Phiên bản/rev tài liệu phải khớp, nếu dự án có yêu cầu.
    expected_revision: str = ""
    #: Tệp người đã cung cấp, nếu đã có.
    provided: str = ""

    def __post_init__(self) -> None:
        if self.kind not in DocKind.ALL:
            raise DocPlanError(
                f"Loại tài liệu {self.kind!r} không hợp lệ (hợp lệ: {list(DocKind.ALL)})"
            )
        if not self.subject.strip():
            raise DocPlanError(f"{self.kind}: không nêu tài liệu CỦA CÁI GÌ")
        if not self.why.strip():
            raise DocPlanError(
                f"{self.kind} {self.subject!r}: không nêu vì sao cần. Một danh sách "
                "tài liệu không kèm lý do sẽ bị đọc thành 'đưa hết đi cho chắc'."
            )

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.subject}"

    @property
    def satisfied(self) -> bool:
        return bool(self.provided)

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "kind": self.kind,
                "subject": self.subject,
                "why": self.why,
                "required": self.required,
                "official_source": self.official_source,
                "expected_revision": self.expected_revision,
                "provided": self.provided,
            }.items()
            if v not in ("", None)
        }

    @classmethod
    def from_dict(cls, d: Any) -> "DocumentNeed":
        if not isinstance(d, dict):
            raise DocPlanError(f"mục tài liệu phải là ánh xạ, nhận {type(d)}")
        return cls(
            kind=str(d.get("kind", "")),
            subject=str(d.get("subject", "")),
            why=str(d.get("why", "")),
            required=bool(d.get("required", True)),
            official_source=str(d.get("official_source", "")),
            expected_revision=str(d.get("expected_revision", "")),
            provided=str(d.get("provided", "")),
        )

    def render(self) -> str:
        danh_dau = "✓" if self.satisfied else ("✗" if self.required else "·")
        dong = [f"  {danh_dau} [{self.kind}] {self.subject}"]
        dong.append(f"      cần vì: {self.why}")
        if self.expected_revision:
            dong.append(f"      phải đúng bản: {self.expected_revision}")
        if self.official_source:
            dong.append(f"      nguồn chính thức: {self.official_source}")
        if self.provided:
            dong.append(f"      đã có: {self.provided}")
        return "\n".join(dong)


@dataclass
class DocumentPlan:
    """Danh sách tài liệu cần, suy từ hồ sơ phần cứng."""

    needs: tuple[DocumentNeed, ...] = ()
    silicon_rev: str = REV_CHUA_BIET

    @property
    def missing(self) -> tuple[DocumentNeed, ...]:
        return tuple(n for n in self.needs if n.required and not n.satisfied)

    def with_sources(self, sources: dict[str, str]) -> "DocumentPlan":
        """Gắn đường dẫn chính thức đã tra được vào từng mục.

        Mọi đường dẫn đi qua ``check_web_source``: một trích dẫn ngoài danh
        sách cho phép tạo ra ảo giác CÓ NGUỒN, nguy hiểm hơn hẳn không nguồn.
        """
        from eaa.ingest import check_web_source

        moi: list[DocumentNeed] = []
        for n in self.needs:
            url = sources.get(n.key, "")
            if url:
                check_web_source(url)
            moi.append(
                DocumentNeed(
                    kind=n.kind,
                    subject=n.subject,
                    why=n.why,
                    required=n.required,
                    official_source=url or n.official_source,
                    expected_revision=n.expected_revision,
                    provided=n.provided,
                )
            )
        return DocumentPlan(needs=tuple(moi), silicon_rev=self.silicon_rev)

    def match_provided(self, registry: Any) -> "DocumentPlan":
        """Đối chiếu với tài liệu người đã nộp (``SourceRegistry``).

        Khớp theo TÊN TỆP có chứa chủ thể, cách thô nhưng đủ để nói "đã có" hay
        "còn thiếu" mà không đòi người đặt tên theo một quy ước nào. Khớp nhầm
        thì người nhìn thấy ngay ở dòng "đã có"; khớp thiếu thì mục vẫn ở trạng
        thái thiếu — cả hai đều lộ ra, không có kết cục im lặng.
        """
        da_nop = [
            str(getattr(r, "path", "") or getattr(r, "origin", ""))
            for r in (getattr(registry, "all", lambda: [])() if registry else [])
        ]
        moi: list[DocumentNeed] = []
        for n in self.needs:
            khop = next(
                (
                    p
                    for p in da_nop
                    if _chuan(n.subject) in _chuan(Path(p).name)
                    and (n.kind == DocKind.DATASHEET or _chuan(n.kind) in _chuan(Path(p).name))
                ),
                "",
            )
            moi.append(
                DocumentNeed(
                    kind=n.kind,
                    subject=n.subject,
                    why=n.why,
                    required=n.required,
                    official_source=n.official_source,
                    expected_revision=n.expected_revision,
                    provided=khop or n.provided,
                )
            )
        return DocumentPlan(needs=tuple(moi), silicon_rev=self.silicon_rev)

    def questions(self) -> list[str]:
        """Câu phải hỏi người — thứ không hồ sơ nào trả lời thay được."""
        hoi: list[str] = []
        if not self.silicon_rev:
            hoi.append(
                "Rev silicon của chip là gì? (in trên mặt chip, thường là một mã "
                "ngắn cạnh mã linh kiện)\n"
                "    Không có nó thì KHÔNG tra được errata cho đúng con chip trên "
                "bàn — và errata là tài liệu hay bị quên nhất."
            )
        thieu_ban = [n for n in self.needs if n.expected_revision and not n.provided]
        for n in thieu_ban:
            hoi.append(
                f"{n.subject}: cần đúng bản {n.expected_revision}. Bản đang có là bản nào?"
            )
        return hoi


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Suy từ hồ sơ phần cứng — đúng theo thứ dự án đã khai, chưa ai kiểm là đủ.
        """
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self) -> str:
        dong = [f"Tài liệu cần — {len(self.needs)} mục, còn thiếu {len(self.missing)}", ""]
        for n in self.needs:
            dong.append(n.render())
        hoi = self.questions()
        if hoi:
            dong += ["", "PHẢI HỎI NGƯỜI:"] + [f"  ? {h}" for h in hoi]
        return "\n".join(dong)


def _chuan(van_ban: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (van_ban or "").lower())


def plan_documents(hardware: Any, *, silicon_rev: str = REV_CHUA_BIET) -> DocumentPlan:
    """Suy danh sách tài liệu cần từ hồ sơ phần cứng (N-004).

    Suy chứ không hỏi: mọi thứ ở đây đọc được từ ``hardware_profile.yaml``, nên
    bắt người liệt kê lại là bắt người làm việc của máy. Cái máy KHÔNG suy được
    — rev silicon và đường dẫn trang hãng — thì nằm ở ``questions()``.
    """
    if hardware is None:
        raise DocPlanError("Chưa có hồ sơ phần cứng nên không lập được danh sách tài liệu.")

    mcu = getattr(hardware, "mcu", {}) or {}
    ma_chip = str(mcu.get("part", "")).strip()
    if not ma_chip:
        raise DocPlanError(
            "Hồ sơ phần cứng chưa khai 'mcu.part'. Không biết chip nào thì không "
            "nêu đích danh được tài liệu nào."
        )

    can: list[DocumentNeed] = [
        DocumentNeed(
            DocKind.DATASHEET,
            ma_chip,
            "Đặc tính điện, sơ đồ chân, và bảng thanh ghi của mọi ngoại vi đang dùng.",
        ),
        DocumentNeed(
            DocKind.ERRATA,
            ma_chip,
            "Lỗi chip đã công bố. Đây là tài liệu hay bị quên nhất, và quên nó thì "
            "mã ĐÚNG THEO DATASHEET vẫn chạy sai — loại lỗi mọi cổng kiểm chứng "
            "đều cho qua vì mã thật sự đúng với thứ nó được bảo.",
            expected_revision=silicon_rev,
        ),
    ]

    # Tài liệu tham chiếu tách rời chỉ có ở vài họ chip. Dự án khai thì mới đưa
    # vào — engine không đoán một họ nào có, một họ nào không.
    if mcu.get("reference_manual") or mcu.get("has_reference_manual"):
        can.append(
            DocumentNeed(
                DocKind.REFERENCE_MANUAL,
                ma_chip,
                "Họ chip này tách phần mô tả ngoại vi ra khỏi datasheet; thiếu nó "
                "thì bảng thanh ghi không đầy đủ.",
            )
        )

    ten_bo = str(getattr(hardware, "raw", {}).get("board", "")) or str(
        getattr(hardware, "raw", {}).get("project", "")
    )
    if ten_bo:
        can.append(
            DocumentNeed(
                DocKind.SCHEMATIC,
                ten_bo,
                "Chân nào nối đi đâu. Không có nó thì bảng chân là phỏng đoán, và "
                "một phỏng đoán về chân chỉ lộ ra sau khi đã hàn.",
            )
        )

    # Gộp theo MÃ LINH KIỆN, không theo vị trí lắp. Hai động cơ cùng một mã
    # driver cần đúng một datasheet; liệt kê hai lần chỉ làm danh sách dài ra
    # mà không thêm việc gì phải làm.
    theo_ma: dict[str, list[str]] = {}
    loai_cua: dict[str, str] = {}
    for c in getattr(hardware, "components", []):
        ma = str(c.get("part", "") or c.get("id", "")).strip()
        if not ma:
            continue
        theo_ma.setdefault(ma, []).append(str(c.get("id", ma)))
        loai_cua.setdefault(ma, str(c.get("kind", "") or "linh kiện"))

    for ma, vi_tri in theo_ma.items():
        cho = ", ".join(repr(v) for v in vi_tri)
        can.append(
            DocumentNeed(
                DocKind.DATASHEET,
                ma,
                f"Thanh ghi và dải hoạt động của {loai_cua[ma]} {cho} — "
                "mã cấu hình nó phải trích dẫn được từ đây.",
            )
        )

    return DocumentPlan(needs=tuple(can), silicon_rev=silicon_rev)


# --------------------------------------------------------------------------
# N-030 — cần trang nào, đích danh
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PageRequest:
    """Một mục cần trích: tài liệu nào, phần nào, để lấy thanh ghi nào."""

    document: str
    registers: tuple[str, ...]
    peripheral: str = ""
    section_hint: str = ""
    why: str = ""

    def render(self) -> str:
        dong = [f"  {self.document} — {self.section_hint or 'phần mô tả ' + self.peripheral}"]
        dong.append(f"      thanh ghi cần: {', '.join(self.registers)}")
        if self.why:
            dong.append(f"      {self.why}")
        return "\n".join(dong)


@dataclass
class PagePlan:
    """Những phần tài liệu cần chưng cất, và những phần KHÔNG cần."""

    requests: tuple[PageRequest, ...] = ()
    #: Thanh ghi đã có trích đoạn đang hiệu lực — cố ý không xin lại.
    already_have: tuple[str, ...] = ()
    module_id: str = ""

    @property
    def registers_needed(self) -> tuple[str, ...]:
        ten: list[str] = []
        for r in self.requests:
            for x in r.registers:
                if x not in ten:
                    ten.append(x)
        return tuple(ten)


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Bắc cầu trên đồ thị tài nguyên và kho trích đoạn hiện có.
        """
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self) -> str:
        tieu_de = (
            f"Trang cần trích — module {self.module_id}"
            if self.module_id
            else "Trang cần trích — toàn dự án"
        )
        dong = [tieu_de, ""]
        if not self.requests:
            dong.append(
                "  Không phần nào còn phải trích: mọi thanh ghi cần đều đã có "
                "trích đoạn đang hiệu lực."
            )
        for r in self.requests:
            dong.append(r.render())
        if self.already_have:
            dong += [
                "",
                f"Đã có trích đoạn ({len(self.already_have)}): "
                + ", ".join(self.already_have),
            ]
        dong += [
            "",
            "Cố ý KHÔNG nạp cả tệp. Một datasheet vài trăm trang chỉ cho ra vài",
            "chục trích đoạn có ích; nạp hết là vừa tốn token vừa kéo vào những",
            "trang chẳng liên quan, làm loãng đúng phần cần đọc kỹ.",
        ]
        return "\n".join(dong)


def plan_pages(
    *,
    hardware: Any,
    graph: Any = None,
    datasheets: Any = None,
    module_id: str = "",
    uses: Sequence[str] = (),
) -> PagePlan:
    """Từ đồ thị tài nguyên suy ra cần trích PHẦN NÀO (N-030).

    Bắc cầu ba bước, cả ba đều trên dữ liệu của dự án: module dùng ngoại vi nào
    → ngoại vi ấy cấu hình bằng thanh ghi nào → thanh ghi nào chưa có trích
    đoạn đang hiệu lực. Bước thứ ba là bước khiến danh sách này NGẮN.
    """
    if hardware is None:
        raise DocPlanError("Chưa có hồ sơ phần cứng nên không suy được trang cần trích.")

    mcu = getattr(hardware, "mcu", {}) or {}
    tai_lieu_chip = str(mcu.get("part", "")) or "datasheet chip"

    # Ngoại vi cần xét: của riêng một module, hay của cả dự án.
    if module_id and graph is not None and hasattr(graph, "resources_of"):
        ngoai_vi = list(graph.resources_of(module_id))
    elif uses:
        ngoai_vi = list(uses)
    else:
        ngoai_vi = [str(p.get("id", "")) for p in getattr(hardware, "peripherals", [])]
    ngoai_vi = [x for x in ngoai_vi if x]

    da_co = _thanh_ghi_da_co(datasheets)

    xin: list[PageRequest] = []
    for nv in ngoai_vi:
        thanh_ghi = tuple(getattr(hardware, "registers_of", lambda _: ())(nv))
        con_thieu = tuple(r for r in thanh_ghi if r.upper() not in da_co)
        if not con_thieu:
            continue
        xin.append(
            PageRequest(
                document=tai_lieu_chip,
                registers=con_thieu,
                peripheral=nv,
                section_hint=f"phần mô tả ngoại vi {nv!r}, bảng thanh ghi",
                why=(
                    f"{len(thanh_ghi) - len(con_thieu)}/{len(thanh_ghi)} thanh ghi "
                    "của ngoại vi này đã có trích đoạn; chỉ xin phần còn lại."
                )
                if len(con_thieu) < len(thanh_ghi)
                else "",
            )
        )

    return PagePlan(
        requests=tuple(xin),
        already_have=tuple(sorted(da_co)),
        module_id=module_id,
    )


def _thanh_ghi_da_co(datasheets: Any) -> set[str]:
    """Thanh ghi đã có trích đoạn ĐANG HIỆU LỰC.

    Chỉ tính bản active: một chunk đã bị supersede thì thanh ghi ấy coi như
    chưa có, vì đó đúng là tình trạng của nó.
    """
    if datasheets is None:
        return set()
    hoat_dong = datasheets.active() if hasattr(datasheets, "active") else []
    return {
        str(r).upper()
        for c in hoat_dong
        for r in (getattr(c, "registers", ()) or ())
    }


# --------------------------------------------------------------------------
# N-037 — errata theo đúng rev silicon
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrataItem:
    """Một lỗi chip đã công bố."""

    id: str
    title: str
    #: Ngoại vi / thanh ghi bị ảnh hưởng — khớp với id trong hồ sơ phần cứng.
    affects: tuple[str, ...] = ()
    #: Các rev silicon dính lỗi. Rỗng = tài liệu không nói rõ, coi như MỌI rev.
    revisions: tuple[str, ...] = ()
    workaround: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DocPlanError("mục errata không có mã")
        if not self.title.strip():
            raise DocPlanError(f"errata {self.id}: không nêu lỗi gì")

    def applies_to(self, rev: str) -> bool:
        """Rev này có dính lỗi không.

        Không khai rev nào thì coi là DÍNH. Suy ngược lại — "không nói tức là
        không dính" — là đúng chiều suy diễn nguy hiểm: nó biến một chỗ thiếu
        thông tin thành một lời bảo đảm.
        """
        if not self.revisions:
            return True
        return any(r.lower() == (rev or "").lower() for r in self.revisions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "affects": list(self.affects),
            "revisions": list(self.revisions),
            "workaround": self.workaround,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ErrataItem":
        if not isinstance(d, dict):
            raise DocPlanError(f"mục errata phải là ánh xạ, nhận {type(d)}")
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            affects=tuple(str(x) for x in (d.get("affects") or [])),
            revisions=tuple(str(x) for x in (d.get("revisions") or [])),
            workaround=str(d.get("workaround", "")),
            source=str(d.get("source", "")),
        )

    def render(self, rev: str = "") -> str:
        dong = [f"  [{self.id}] {self.title}"]
        if self.affects:
            dong.append(f"      chạm tới: {', '.join(self.affects)}")
        dong.append(
            f"      rev dính : {', '.join(self.revisions) if self.revisions else 'MỌI rev (tài liệu không nói rõ)'}"
        )
        dong.append(
            f"      né bằng  : {self.workaround or 'CHƯA CÓ CÁCH NÉ — phải quyết định'}"
        )
        if self.source:
            dong.append(f"      nguồn    : {self.source}")
        return "\n".join(dong)


@dataclass(frozen=True)
class ErrataImpact:
    """Một module chạm vào một lỗi đã công bố."""

    module_id: str
    errata: ErrataItem
    resource: str

    def render(self) -> str:
        return (
            f"  {self.module_id} ← [{self.errata.id}] qua {self.resource}: "
            f"{self.errata.title}"
        )


@dataclass
class ErrataAnalysis:
    """Kho errata của một dự án, và phép đối chiếu với module đang làm."""

    items: tuple[ErrataItem, ...] = ()
    silicon_rev: str = REV_CHUA_BIET
    part: str = ""
    #: Đã thật sự tra chưa. Phân biệt "tra rồi, sạch" với "chưa tra" (xem đầu tệp).
    looked_up: bool = False
    source: str = ""
    checked_at: str = field(default_factory=_now)

    @property
    def rev_known(self) -> bool:
        return bool(self.silicon_rev)

    def for_rev(self) -> tuple[ErrataItem, ...]:
        return tuple(i for i in self.items if i.applies_to(self.silicon_rev))

    def impact(self, hardware: Any, modules: Iterable[Any]) -> list[ErrataImpact]:
        """Module nào chạm vào một lỗi đã công bố.

        Đối chiếu hai chiều: ``affects`` của errata gặp ``uses`` của module, và
        gặp cả thanh ghi cấu hình các ngoại vi ấy — errata thường gọi tên thanh
        ghi chứ không gọi tên ngoại vi.
        """
        ket_qua: list[ErrataImpact] = []
        for m in modules:
            ma = str(getattr(m, "id", None) or getattr(m, "module_id", "") or m)
            dung = [str(x) for x in (getattr(m, "uses", ()) or ())]
            thanh_ghi = {
                r.upper()
                for nv in dung
                for r in getattr(hardware, "registers_of", lambda _: ())(nv)
            }
            for e in self.for_rev():
                cham = next(
                    (
                        a
                        for a in e.affects
                        if a in dung or a.upper() in thanh_ghi
                    ),
                    "",
                )
                if cham:
                    ket_qua.append(ErrataImpact(module_id=ma, errata=e, resource=cham))
        return ket_qua

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "part": self.part,
            "silicon_rev": self.silicon_rev,
            "looked_up": self.looked_up,
            "source": self.source,
            "checked_at": self.checked_at,
            "errata": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ErrataAnalysis":
        if not isinstance(d, dict):
            raise DocPlanError("kho errata phải là ánh xạ khóa–giá trị")
        return cls(
            items=tuple(ErrataItem.from_dict(x) for x in (d.get("errata") or [])),
            silicon_rev=str(d.get("silicon_rev", "")),
            part=str(d.get("part", "")),
            looked_up=bool(d.get("looked_up", False)),
            source=str(d.get("source", "")),
            checked_at=str(d.get("checked_at", "")) or _now(),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _DAU_TEP_ERRATA
            + yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load(path: str | Path) -> "ErrataAnalysis | None":
        path = Path(path)
        if not path.is_file():
            return None
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise DocPlanError(f"{path}: YAML không hợp lệ — {exc}") from exc
        return ErrataAnalysis.from_dict(du_lieu)

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC, SUY_RA

        if not self.looked_up:
            return KHONG_KIEM_DUOC
        return DA_KIEM if self.rev_known else SUY_RA

    def confidence(self) -> str:
        """Câu một dòng nói rõ kết luận này đáng tin tới đâu.

        Ba trạng thái, và trạng thái đầu là lý do hàm này tồn tại: một danh
        sách errata trống trông y hệt một con chip sạch.
        """
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC, SUY_RA

        if not self.looked_up:
            return (
                f"[{KHONG_KIEM_DUOC}] CHƯA TRA — chưa ai tra errata cho chip này. "
                "Danh sách trống ở đây KHÔNG có nghĩa là chip sạch."
            )
        if not self.rev_known:
            return (
                f"[{SUY_RA}] ĐÃ TRA nhưng CHƯA BIẾT REV — kết luận áp cho mọi rev, "
                "nên có thể thừa (cảnh báo lỗi của rev khác) hoặc thiếu (bỏ sót lỗi "
                "chỉ có ở rev đang cầm). Hỏi rev in trên mặt chip."
            )
        return (
            f"[{DA_KIEM}] ĐÃ TRA cho rev {self.silicon_rev!r} — "
            f"{len(self.for_rev())} lỗi áp cho rev này."
        )

    def render(self, hardware: Any = None, modules: Iterable[Any] = ()) -> str:
        dong = [
            f"Errata — {self.part or '(chưa rõ chip)'}"
            + (f", rev {self.silicon_rev}" if self.rev_known else ", rev CHƯA BIẾT"),
            "",
            self.confidence(),
            "",
        ]
        ap_dung = self.for_rev()
        if not ap_dung:
            dong.append("  (không mục nào áp cho rev này)")
        for e in ap_dung:
            dong.append(e.render(self.silicon_rev))

        if hardware is not None:
            cham = self.impact(hardware, modules)
            dong += ["", "Module chạm vào lỗi đã công bố:"]
            dong += [c.render() for c in cham] or ["  (không module nào)"]
            if cham:
                dong += [
                    "",
                    "Mã của những module trên có thể ĐÚNG THEO DATASHEET mà vẫn chạy",
                    "sai. Không cổng kiểm chứng nào bắt được điều đó — chỉ tài liệu",
                    "mới nói được. Quyết cách né tại G2 rồi ghi vào ràng buộc.",
                ]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Tra cứu bằng mô hình — mọi thứ tra về đều là proposed fact
# --------------------------------------------------------------------------


_LUOC_DO_NGUON = """{
  "sources": [
    {"key": "<kind:subject, chép đúng từ danh sách>", "url": "<trang CHÍNH THỨC của hãng>"}
  ]
}"""

_LUOC_DO_ERRATA = """{
  "errata": [
    {
      "id": "<mã lỗi theo tài liệu của hãng>",
      "title": "<lỗi gì, một câu>",
      "affects": ["<id ngoại vi hoặc TÊN THANH GHI bị ảnh hưởng>"],
      "revisions": ["<rev silicon dính lỗi; để trống nếu tài liệu không nói rõ>"],
      "workaround": "<cách né theo tài liệu>",
      "source": "<đường dẫn trang chính thức>"
    }
  ]
}"""


@dataclass
class LlmDocLookup:
    """Tra đường dẫn tài liệu và nội dung errata bằng mô hình nền.

    Mọi thứ trả về đều là *proposed fact*: nguồn bị chặn trong danh sách cho
    phép, và nội dung phải qua G2 như mọi tri thức khác (FR-ING-02).
    """

    llm: Any
    budget: int = 2500

    def _goi(self, *, module: str, he_thong: str, viec: str) -> dict[str, Any]:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=he_thong,
            layers=[PromptLayer("task", viec, budget=self.budget, required=True)],
            module=module,
            budget=self.budget + 800,
        )
        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise DocPlanError(f"Không tra được {module}: {exc}") from exc

        from eaa.options import boc_json

        return boc_json(van_ban, DocPlanError)

    def sources(self, plan: DocumentPlan) -> dict[str, str]:
        """Tìm đường dẫn trang chính thức cho từng tài liệu cần."""
        from eaa.ingest import WEB_WHITELIST, SourceRejected, check_web_source

        du_lieu = self._goi(
            module="nguồn tài liệu",
            he_thong=(
                "Bạn tìm trang tài liệu CHÍNH THỨC của nhà sản xuất. Chỉ dùng "
                "tên miền trong danh sách cho phép. Không chắc có trang ấy thì "
                "BỎ QUA mục đó — một đường dẫn bịa ra trông đàng hoàng còn tệ "
                "hơn không có đường dẫn nào."
            ),
            viec=(
                "Tài liệu cần:\n"
                + "\n".join(f"  {n.key}" for n in plan.needs)
                + f"\n\nTên miền cho phép: {', '.join(WEB_WHITELIST)}\n\n"
                "Trả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_NGUON}\n```"
            ),
        )
        ket_qua: dict[str, str] = {}
        hop_le = {n.key for n in plan.needs}
        for x in du_lieu.get("sources") or []:
            if not isinstance(x, dict):
                continue
            khoa, url = str(x.get("key", "")), str(x.get("url", ""))
            if khoa not in hop_le or not url:
                continue
            try:
                check_web_source(url)
            except SourceRejected:
                # Bỏ im lặng là sai; nhưng ném ra ngoài thì một đường dẫn hỏng
                # làm hỏng cả lượt tra. Giữ lại phần đúng, và mục bị loại vẫn
                # hiện ra ở danh sách "còn thiếu nguồn".
                continue
            ket_qua[khoa] = url
        return ket_qua

    def errata(
        self, *, part: str, silicon_rev: str, peripherals: Sequence[str] = ()
    ) -> ErrataAnalysis:
        du_lieu = self._goi(
            module="errata",
            he_thong=(
                "Bạn tra errata (danh sách lỗi chip đã công bố) của một vi điều "
                "khiển. Chỉ nêu lỗi CÓ THẬT trong tài liệu chính thức của hãng. "
                "Nêu rõ rev silicon nào dính; tài liệu không nói rõ thì để trống "
                "chứ ĐỪNG đoán. Ưu tiên lỗi chạm tới các ngoại vi được liệt kê."
            ),
            viec=(
                f"Chip: {part}\n"
                f"Rev silicon: {silicon_rev or '(chưa biết)'}\n"
                + (f"Ngoại vi dự án dùng: {', '.join(peripherals)}\n" if peripherals else "")
                + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_ERRATA}\n```"
            ),
        )
        return ErrataAnalysis(
            items=tuple(ErrataItem.from_dict(x) for x in (du_lieu.get("errata") or [])),
            silicon_rev=silicon_rev,
            part=part,
            looked_up=True,
            source=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )


_DAU_TEP_ERRATA = """\
# Errata — lỗi chip đã công bố. BẢN ĐỀ XUẤT, phải duyệt tại G2.
#
# Vì sao tệp này quan trọng hơn vẻ ngoài của nó: mã ĐÚNG THEO DATASHEET vẫn có
# thể chạy sai nếu con chip có lỗi đã công bố. Đó là loại lỗi mà mọi cổng kiểm
# chứng của hệ thống này đều cho qua — vì mã thật sự đúng với thứ nó được bảo.
#
# `looked_up: false` nghĩa là CHƯA AI TRA, không phải "chip sạch". Một danh
# sách trống ở hai trường hợp ấy trông y hệt nhau, nên trường này tồn tại để
# phân biệt chúng.
#
# `revisions` trống nghĩa là tài liệu không nói rõ rev nào dính → coi như MỌI
# rev. Suy ngược lại sẽ biến một chỗ thiếu thông tin thành một lời bảo đảm.

"""
