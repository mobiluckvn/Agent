"""Tìm kiếm web — biến một khoảng trống thành một câu truy vấn, rồi đi đọc.

EAA-AIS-05 §6.2 bậc 3, §9.2 (tìm công cụ chưa biết), §12; FR-GAP-02, FR-ENV-03.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-72.

Vì sao tìm kiếm và đọc là HAI việc
-----------------------------------

Một mô hình có công cụ tìm kiếm gắn sẵn sẽ vui vẻ trả lời cả câu hỏi kèm mấy
đường dẫn. Nhận nguyên câu trả lời ấy là quay lại đúng chỗ ta vừa rời khỏi:
một đoạn văn trôi chảy do mô hình viết, đính kèm URL trông đàng hoàng, không
ai biết đoạn văn có thật sự lấy từ URL ấy hay không.

Nên ở đây tìm kiếm chỉ trả về **địa chỉ**:

* :class:`SearchHit` mang url, tiêu đề, và đoạn trích của máy tìm kiếm — không
  mang kết luận.
* Nội dung do :mod:`eaa.web` tải về, qua bộ kiểm nguồn và phân hạng tin cậy.
* :class:`WebResearcher` ghép hai bước ấy và trả về **tài liệu đã đọc**, để
  bên gọi trích dẫn được đúng câu trong đúng trang.

Ba nguồn tìm kiếm, xếp theo thứ tự dùng
----------------------------------------

1. :class:`JsonEndpointSearch` — endpoint JSON tự cấu hình qua ``EAA_SEARCH_URL``
   (dạng SearxNG/Brave). Đây là lựa chọn tốt nhất khi có: không đi qua mô hình,
   nên kết quả tái lập được và không tốn token.
2. :class:`GeminiGroundedSearch` — công cụ tìm kiếm gắn sẵn của nhà cung cấp
   mô hình. Không cần dựng thêm hạ tầng, đổi lại kết quả phụ thuộc nhà cung cấp.
3. :class:`NullSearch` — không có gì. Nói thẳng ra là không tìm được và chỉ
   cách bật, thay vì trả danh sách rỗng để bên gọi hiểu nhầm thành "không có
   kết quả nào trên đời".

Sắp xếp: chính chủ luôn lên trước
----------------------------------

:func:`rank_hits` đẩy mọi kết quả thuộc miền nhà sản xuất lên đầu, giữ nguyên
thứ tự tương đối trong từng hạng. Không phải vì máy tìm kiếm xếp sai, mà vì
tiêu chí của ta khác tiêu chí của nó: một trang datasheet gốc xếp thứ tám vẫn
đáng đọc trước một bài blog xếp thứ nhất.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, Sequence
from urllib.parse import quote_plus, urlparse

from eaa.web import CHINH_CHU, MO, WebDocument, WebError, WebFetcher, classify

__all__ = [
    "SearchError",
    "SearchUnavailable",
    "SearchHit",
    "SearchBackend",
    "JsonEndpointSearch",
    "GeminiGroundedSearch",
    "NullSearch",
    "ChainSearch",
    "WebResearcher",
    "ResearchResult",
    "rank_hits",
    "build_query",
    "restrict_to_sites",
    "SEARCH_URL_ENV",
    "MAX_DOCS",
]

#: Endpoint JSON tự cấu hình. Phải chứa ``{q}`` — chỗ chèn câu truy vấn đã
#: mã hóa. Ví dụ: ``https://searx.mien-cua-ban/search?q={q}&format=json``
SEARCH_URL_ENV = "EAA_SEARCH_URL"

#: Trần số trang đọc trong MỘT lượt tra cứu. Cùng tinh thần với vòng tự sửa ≤ 3
#: và MAX_STEPS = 8: một vòng đọc không có trần là một vòng sẽ đọc tới lúc hết
#: ngân sách ngữ cảnh.
MAX_DOCS = 4


class SearchError(Exception):
    """Không tìm được."""


class SearchUnavailable(SearchError):
    """Chưa cấu hình nguồn tìm kiếm nào."""


# --------------------------------------------------------------------------
# Kết quả
# --------------------------------------------------------------------------


#: Trạm chuyển hướng của nhà cung cấp máy tìm kiếm.
#:
#: ĐO ĐƯỢC trên API thật (30/08/2026): công cụ tìm kiếm gắn sẵn KHÔNG trả URL
#: thật, nó trả một URL bọc dạng ``…/grounding-api-redirect/<mã>``. Phân hạng
#: theo URL bọc thì mọi kết quả đều rơi xuống hạng mở — kể cả một trang
#: datasheet gốc — và bộ lọc "chỉ chính chủ" sẽ lọc sạch mọi thứ. Tên miền thật
#: nằm ở trường tiêu đề, nên nó được dùng làm gợi ý phân hạng cho tới khi trang
#: được tải về và hạng được tính lại trên URL cuối cùng.
_TRAM_CHUYEN_HUONG: tuple[str, ...] = (
    "vertexaisearch.cloud.google.com",
    "googleusercontent.com",
    "duckduckgo.com",
    "r.jina.ai",
)

_MIEN = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$")


def _la_tram_chuyen_huong(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == t or host.endswith("." + t) for t in _TRAM_CHUYEN_HUONG)


@dataclass(frozen=True)
class SearchHit:
    """Một địa chỉ máy tìm kiếm trả về. KHÔNG chứa kết luận."""

    url: str
    title: str = ""
    snippet: str = ""
    source: str = ""
    tier: str = ""
    #: Tên miền thật, khi ``url`` chỉ là một URL bọc qua trạm chuyển hướng.
    domain_hint: str = ""

    def __post_init__(self) -> None:
        if not self.tier:
            goi_y = self.domain_hint.strip().lower()
            if goi_y and _MIEN.match(goi_y) and _la_tram_chuyen_huong(self.url):
                object.__setattr__(self, "tier", classify(f"https://{goi_y}/"))
            else:
                object.__setattr__(self, "tier", classify(self.url))

    @property
    def domain(self) -> str:
        goi_y = self.domain_hint.strip().lower()
        if goi_y and _MIEN.match(goi_y):
            return goi_y
        return (urlparse(self.url).hostname or "").lower()

    @property
    def wrapped(self) -> bool:
        """URL này có phải chỉ là một cái bọc, chưa phải địa chỉ thật không."""
        return _la_tram_chuyen_huong(self.url)

    def render(self) -> str:
        dau = "★" if self.tier == CHINH_CHU else "·"
        dia_chi = self.url if not self.wrapped else f"{self.domain}  (qua trạm chuyển hướng)"
        dong = [f"  {dau} {self.title or self.domain}", f"      {dia_chi}   [{self.tier}]"]
        if self.snippet:
            dong.append(f"      {self.snippet[:200]}")
        return "\n".join(dong)


def rank_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    """Chính chủ lên trước, giữ nguyên thứ tự tương đối trong từng hạng."""
    ds = list(hits)
    return [h for h in ds if h.tier == CHINH_CHU] + [h for h in ds if h.tier != CHINH_CHU]


def build_query(*phan: str) -> str:
    """Ghép các mảnh thành một truy vấn ngắn, bỏ trùng và bỏ rỗng.

    Truy vấn dài không làm máy tìm kiếm hiểu hơn; nó chỉ làm kết quả hẹp lại
    quanh những từ tình cờ đứng cạnh nhau.
    """
    tu: list[str] = []
    da_co: set[str] = set()
    for p in phan:
        for t in re.split(r"\s+", (p or "").strip()):
            k = t.lower().strip(".,;:()[]\"'")
            if k and k not in da_co:
                da_co.add(k)
                tu.append(t)
    return " ".join(tu[:16])


def restrict_to_sites(query: str, sites: Sequence[str] = ()) -> str:
    """Buộc truy vấn về đúng mấy tên miền, bằng cú pháp ``site:``.

    ĐO ĐƯỢC trên máy tìm kiếm thật: một câu hỏi về thanh ghi của một con chip
    trả về gần như toàn diễn đàn, trang chia sẻ tài liệu và blog — không có
    trang nhà sản xuất nào trong tám kết quả đầu. Hạng tin cậy lọc được thứ
    rác ấy SAU khi tìm, nhưng lọc xong thì không còn gì. Nên chỗ cần sửa là
    câu hỏi, không phải bộ lọc: hỏi đúng nơi thì mới có cái để lọc.
    """
    ds = [s.strip().lower() for s in sites if s and s.strip()]
    if not ds:
        return query
    if len(ds) == 1:
        return f"{query} site:{ds[0]}"
    return f"{query} (" + " OR ".join(f"site:{s}" for s in ds) + ")"


# --------------------------------------------------------------------------
# Các nguồn tìm kiếm
# --------------------------------------------------------------------------


class SearchBackend(Protocol):
    """Giao diện chung — đổi nguồn tìm kiếm không đổi bên gọi (ADR-03)."""

    name: str

    def search(self, query: str, *, k: int = 8) -> list[SearchHit]: ...


@dataclass
class JsonEndpointSearch:
    """Endpoint JSON tự cấu hình. Không đi qua mô hình, nên tái lập được."""

    url_template: str = ""
    fetcher: WebFetcher | None = None
    name: str = "endpoint"

    def __post_init__(self) -> None:
        if not self.url_template:
            self.url_template = os.environ.get(SEARCH_URL_ENV, "").strip()

    @property
    def available(self) -> bool:
        return "{q}" in self.url_template

    def search(self, query: str, *, k: int = 8) -> list[SearchHit]:
        if not self.available:
            raise SearchUnavailable(
                f"Chưa đặt {SEARCH_URL_ENV} (chuỗi phải chứa chỗ giữ '{{q}}')."
            )
        f = self.fetcher or WebFetcher()
        # Truy vấn nằm trong URL nên bộ đệm ăn theo truy vấn — đúng cái ta muốn
        # (C8.4: không tra lại cùng một câu hỏi hai lần).
        doc = f.fetch(self.url_template.replace("{q}", quote_plus(query)))
        try:
            du_lieu = json.loads(doc.text)
        except json.JSONDecodeError as exc:
            raise SearchError(
                f"{SEARCH_URL_ENV} trả về thứ không phải JSON ({exc}). Kiểm lại "
                "endpoint: nó phải trả JSON, không phải trang HTML kết quả."
            ) from None
        return self._doc_ket_qua(du_lieu, k)

    @staticmethod
    def _doc_ket_qua(du_lieu: Any, k: int) -> list[SearchHit]:
        """Chấp nhận vài hình dạng JSON hay gặp thay vì ép đúng một dạng."""
        muc: Sequence[Any] = ()
        if isinstance(du_lieu, dict):
            for khoa in ("results", "web", "items", "data", "hits"):
                gt = du_lieu.get(khoa)
                if isinstance(gt, dict):
                    gt = gt.get("results") or gt.get("items")
                if isinstance(gt, list):
                    muc = gt
                    break
        elif isinstance(du_lieu, list):
            muc = du_lieu

        ket: list[SearchHit] = []
        for m in muc:
            if not isinstance(m, dict):
                continue
            url = str(m.get("url") or m.get("link") or m.get("href") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            ket.append(SearchHit(
                url=url,
                title=str(m.get("title") or m.get("name") or "").strip(),
                snippet=str(m.get("content") or m.get("snippet") or m.get("description") or "").strip()[:400],
                source="endpoint",
            ))
            if len(ket) >= k:
                break
        return ket


@dataclass
class GeminiGroundedSearch:
    """Công cụ tìm kiếm gắn sẵn của nhà cung cấp mô hình."""

    llm: Any = None
    name: str = "gemini-grounding"

    @property
    def available(self) -> bool:
        return self.llm is not None and hasattr(self.llm, "search_web")

    def search(self, query: str, *, k: int = 8) -> list[SearchHit]:
        if not self.available:
            raise SearchUnavailable(
                "Mô hình đang dùng không có công cụ tìm kiếm gắn sẵn. "
                "MockLLM không tìm web được — đó là chủ ý: một bài kiểm tất định "
                "không được phụ thuộc vào thứ ngoài kho mã."
            )
        try:
            tho = self.llm.search_web(query, k=k)
        except Exception as exc:  # noqa: BLE001 - lỗi nhà cung cấp không được làm sập lượt
            raise SearchError(f"Nhà cung cấp mô hình không tìm được: {exc}") from None
        # Nhà cung cấp đặt TÊN MIỀN THẬT vào ô tiêu đề và một URL bọc vào ô url.
        # Truyền tiêu đề sang làm gợi ý phân hạng, nếu không thì mọi kết quả
        # đều rơi xuống hạng mở — xem ``_TRAM_CHUYEN_HUONG``.
        return [
            SearchHit(url=m.get("url", ""), title=m.get("title", ""),
                      snippet=m.get("snippet", ""), source=self.name,
                      domain_hint=m.get("title", ""))
            for m in tho if m.get("url")
        ]


@dataclass
class NullSearch:
    """Không có nguồn nào. Nói thẳng, không trả danh sách rỗng."""

    name: str = "none"
    available: bool = False

    def search(self, query: str, *, k: int = 8) -> list[SearchHit]:
        raise SearchUnavailable(
            "Chưa có nguồn tìm kiếm nào được cấu hình. Bật một trong hai:\n"
            f"  · export {SEARCH_URL_ENV}='https://<máy tìm kiếm của bạn>/search?q={{q}}&format=json'\n"
            "  · dùng mô hình thật (Gemini) — nó có công cụ tìm kiếm gắn sẵn.\n"
            "Danh sách rỗng sẽ bị hiểu nhầm thành 'tìm rồi, không có gì', nên "
            "chỗ này báo lỗi thay vì trả về rỗng."
        )


@dataclass
class ChainSearch:
    """Thử lần lượt, dùng nguồn đầu tiên chạy được."""

    backends: tuple[Any, ...] = ()
    name: str = "chain"

    def search(self, query: str, *, k: int = 8) -> list[SearchHit]:
        loi: list[str] = []
        for b in self.backends:
            if not getattr(b, "available", True):
                continue
            try:
                ket = b.search(query, k=k)
            except SearchError as exc:
                loi.append(f"{getattr(b, 'name', b)}: {exc}")
                continue
            if ket:
                return ket
            loi.append(f"{getattr(b, 'name', b)}: không có kết quả")
        if loi:
            raise SearchUnavailable("Không nguồn tìm kiếm nào trả kết quả:\n  " + "\n  ".join(loi))
        # Không nguồn nào KHẢ DỤNG — thông điệp "bật thế nào" nằm ở một chỗ duy
        # nhất, trong NullSearch, để hai chỗ không kể hai cách bật khác nhau.
        return NullSearch().search(query, k=k)


def default_backend(llm: Any = None, fetcher: WebFetcher | None = None) -> Any:
    """Nguồn tìm kiếm mặc định: endpoint tự cấu hình trước, mô hình sau."""
    endpoint = JsonEndpointSearch(fetcher=fetcher)
    grounding = GeminiGroundedSearch(llm=llm)
    co = tuple(b for b in (endpoint, grounding) if b.available)
    return ChainSearch(backends=co) if co else NullSearch()


# --------------------------------------------------------------------------
# Tra cứu = tìm + đọc
# --------------------------------------------------------------------------


@dataclass
class ResearchResult:
    """Kết quả một lượt tra cứu: địa chỉ đã tìm, trang đã đọc, chỗ đọc hụt."""

    query: str
    hits: tuple[SearchHit, ...] = ()
    documents: tuple[WebDocument, ...] = ()
    failures: tuple[tuple[str, str], ...] = ()

    @property
    def official(self) -> list[WebDocument]:
        return [d for d in self.documents if d.tier == CHINH_CHU]

    @property
    def confidence_level(self) -> str:
        """SUY RA nếu đọc được ít nhất một trang chính chủ; ngược lại KHÔNG KIỂM ĐƯỢC."""
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return SUY_RA if self.official else KHONG_KIEM_DUOC

    def context(self, *, per_doc: int = 2500) -> str:
        """Ngữ cảnh để đưa vào prompt — mỗi trích đoạn KÈM địa chỉ và hạng.

        Địa chỉ đi liền trích đoạn chứ không nằm ở một danh sách cuối bài: khi
        mô hình phải viết ``// ref:`` thì nguồn phải ở ngay cạnh câu nó dùng.
        """
        khoi: list[str] = []
        for d in self.documents:
            khoi.append(
                f"--- NGUỒN {d.url}\n"
                f"--- hạng: {d.tier} · tải lúc {d.fetched_at}"
                + ("" if d.usable_as_knowledge else " · KHÔNG được dùng làm nguồn tri thức")
                + f"\n{d.excerpt(per_doc)}"
            )
        return "\n\n".join(khoi)

    def render(self) -> str:
        from eaa.confidence import header

        dong = [f'Tra cứu: "{self.query}"', "", header(self.confidence_level), ""]
        if self.hits:
            dong.append(f"── tìm được {len(self.hits)} địa chỉ")
            dong += [h.render() for h in self.hits]
            dong.append("")
        if self.documents:
            dong.append(f"── đọc được {len(self.documents)} trang"
                        f" ({len(self.official)} chính chủ)")
            for d in self.documents:
                dong.append(f"  {d.title or d.domain}  [{d.tier}]")
                dong.append(f"      {d.url}  ·  {len(d.text)} ký tự")
        if self.failures:
            dong.append("")
            dong.append("── đọc hụt")
            dong += [f"  ✗ {u}\n      {ly}" for u, ly in self.failures]
        if not self.official:
            dong += [
                "",
                "Không trang chính chủ nào đọc được. Mọi thứ trên đây là MANH MỐI: "
                "dùng để gỡ lỗi hoặc so công cụ, không dùng làm nguồn cho giá trị "
                "cấu hình phần cứng.",
            ]
        return "\n".join(dong)


@dataclass
class WebResearcher:
    """Ghép tìm và đọc thành một việc, có trần và có phân hạng."""

    backend: Any = None
    fetcher: WebFetcher | None = None
    max_docs: int = MAX_DOCS
    #: Chỉ đọc trang chính chủ. Bật khi đang đi tìm tri thức phần cứng, tắt khi
    #: đang gỡ một lỗi cài đặt.
    official_only: bool = False

    def search(self, query: str, *, k: int = 8, sites: Sequence[str] = ()) -> list[SearchHit]:
        b = self.backend or default_backend()
        return rank_hits(b.search(restrict_to_sites(query, sites), k=k))

    def read(self, url: str) -> WebDocument:
        return (self.fetcher or WebFetcher()).fetch(url)

    def research(
        self,
        query: str,
        *,
        k: int = 8,
        max_docs: int | None = None,
        sites: Sequence[str] = (),
    ) -> ResearchResult:
        hits = self.search(query, k=k, sites=sites)
        can_doc = [h for h in hits if not self.official_only or h.tier == CHINH_CHU]
        tran = self.max_docs if max_docs is None else max_docs

        docs: list[WebDocument] = []
        hut: list[tuple[str, str]] = []
        for h in can_doc:
            if len(docs) >= tran:
                break
            try:
                docs.append(self.read(h.url))
            except WebError as exc:
                hut.append((h.url, str(exc)))
        return ResearchResult(
            query=query,
            hits=tuple(hits),
            documents=tuple(docs),
            failures=tuple(hut),
        )
