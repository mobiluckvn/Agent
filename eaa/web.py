"""Truy cập mạng — Agent đi đọc thật, không đọc từ trí nhớ mô hình.

EAA-AIS-05 §6.2 bậc 3 (tra nguồn cho phép), §9.2 (tìm công cụ), §12 (ảo giác);
FR-GAP-02, NFR-06. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-71.

Khoảng trống module này lấp
----------------------------

Trước module này engine chỉ mở mạng tới đúng một nơi: API mô hình. Bậc 3 của
``eaa/gapsearch.py`` mang tên "tra nguồn trên web" nhưng thực chất là *hỏi mô
hình rồi lọc tên miền của URL mà mô hình khai ra*. Kiểm nguồn thì có, ĐI TÌM
thì không — và với một tài liệu công bố sau ngày cắt dữ liệu huấn luyện thì mô
hình không có gì để khai.

Hai hạng tin cậy, không phải một danh sách trắng
------------------------------------------------

Một danh sách trắng duy nhất buộc phải chọn giữa hai cái sai: chặt thì Agent
không tra được lỗi cài đặt trên diễn đàn, lỏng thì một bài blog trở thành
"nguồn" cho một giá trị thanh ghi. Nên ở đây có hai hạng, và chúng khác nhau ở
**thứ kết quả được phép trở thành**, không ở việc có tải được hay không:

* :data:`CHINH_CHU` — miền nhà sản xuất (``ingest.WEB_WHITELIST``). Nội dung
  tải về ĐƯỢC PHÉP thành trích đoạn tri thức ở trạng thái ``proposed``, rồi đi
  tiếp qua gate như mọi chunk khác.
* :data:`MO` — phần còn lại của web. Tải được, đọc được, dùng để gỡ một lỗi
  cài đặt hay so hai thư viện. Nhưng :meth:`WebDocument.usable_as_knowledge`
  trả về ``False``, và mức tin cậy đính kèm là KHÔNG KIỂM ĐƯỢC. Nó là **manh
  mối**, không phải **nguồn**.

Ranh giới ấy nằm ở dữ liệu trả về chứ không ở lời dặn trong prompt, vì đây
đúng là chỗ một lời dặn sẽ bị mô hình diễn giải trôi đi.

Bốn cái chặn, và vì sao từng cái tồn tại
-----------------------------------------

* **Chỉ http/https, và chặn địa chỉ nội bộ.** Tên miền được phân giải TRƯỚC
  khi nối, và mọi địa chỉ vòng lặp / mạng riêng / link-local bị từ chối. Không
  có cái chặn này thì một URL do mô hình sinh ra là một đường để đọc dịch vụ
  siêu dữ liệu nội bộ hoặc quét cổng trên máy người dùng.
* **Kiểm lại từng chặng chuyển hướng.** Một URL chính chủ chuyển hướng ra
  ngoài phải bị hạ hạng, không được giữ hạng của chặng đầu. Đây là cách một
  danh sách trắng bị vượt mà trông vẫn đúng.
* **Trần byte và trần thời gian.** Một trang lớn nuốt hết ngân sách ngữ cảnh;
  một máy chủ chậm treo cả lượt chạy.
* **Công tắc ngắt** ``EAA_NO_NET=1``. Có để CI và bài kiểm chạy được mà chắc
  chắn không chạm mạng, và để người dùng tắt hẳn khi làm việc ở nơi không được
  phép ra ngoài.

Bộ đệm không phải để chạy nhanh
-------------------------------

Bộ đệm đĩa ở đây trước hết là để **tái lập**: một kết luận rút từ một trang web
phải kiểm lại được sau vài tháng, kể cả khi trang ấy đã đổi. Nội dung được lưu
kèm băm và mốc thời gian, nên "trang này lúc ấy nói gì" là câu trả lời được.
Chạy nhanh hơn chỉ là hệ quả.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import urljoin, urlparse

__all__ = [
    "WebError",
    "NetworkDisabled",
    "UnsafeUrl",
    "FetchFailed",
    "WebDocument",
    "WebCache",
    "WebFetcher",
    "fetch",
    "html_to_text",
    "classify",
    "CHINH_CHU",
    "MO",
    "NO_NET_ENV",
    "mang_bi_tat",
    "MAX_BYTES",
    "TIMEOUT_S",
    "MAX_REDIRECTS",
]

#: Hạng nguồn — xem phần đầu tài liệu module.
CHINH_CHU = "chính chủ"
MO = "mở"

#: Đặt ``EAA_NO_NET=1`` là ngắt hẳn MỌI lối ra mạng của sản phẩm — không riêng
#: module này. Engine có đúng ba lối ra: ``eaa/web.py`` (tải trang),
#: ``eaa/llm/gemini.py`` (gọi mô hình, kể cả tìm kiếm có grounding), và phép dò
#: kết nối trong ``eaa/environ.py``. Cả ba đọc :func:`mang_bi_tat`.
NO_NET_ENV = "EAA_NO_NET"


def mang_bi_tat() -> bool:
    """Lối ra mạng có đang bị tắt có chủ ý không.

    Một hàm chứ không phải ba lần đọc biến môi trường: một công tắc mà mỗi chỗ
    tự diễn giải một kiểu là một công tắc **trông như** đã tắt. Chỗ này từng
    hụt đúng như thế — ``eaa research`` đi qua lối grounding của adapter mô
    hình chứ không qua module này, nên ``EAA_NO_NET=1`` không chạm tới nó và
    lệnh vẫn ra mạng thật.
    """
    import os as _os

    return _os.environ.get(NO_NET_ENV, "").strip().lower() in ("1", "true", "yes")

#: Trần một trang. 2 MiB đã lớn hơn mọi trang tài liệu kỹ thuật dạng chữ; cái
#: vượt trần gần như luôn là tệp nhị phân tải nhầm.
MAX_BYTES = 2_000_000

TIMEOUT_S = 20.0
MAX_REDIRECTS = 3

#: Nói thật mình là ai. Một agent tự động giấu mặt sau chuỗi trình duyệt là
#: thứ khiến chủ trang không có cách nào chặn đúng thứ họ muốn chặn.
USER_AGENT = "EAA-Agent/1.0 (+embedded AIDD agent; python-urllib)"

_KIEU_CHU = ("text/", "application/json", "application/xml", "+json", "+xml", "application/xhtml")


class WebError(Exception):
    """Không lấy được nội dung từ mạng."""


class NetworkDisabled(WebError):
    """Lối ra mạng đang bị tắt."""


class UnsafeUrl(WebError):
    """URL không đi được: sai giao thức, hoặc trỏ vào mạng nội bộ."""


class FetchFailed(WebError):
    """Máy chủ từ chối, quá hạn, hoặc trả nội dung không đọc được."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Phân hạng nguồn
# --------------------------------------------------------------------------


def classify(url: str) -> str:
    """Trả :data:`CHINH_CHU` nếu miền thuộc danh sách nhà sản xuất, ngược lại :data:`MO`.

    Dùng chính bộ lọc của ``eaa.ingest`` chứ không viết lại: hai bộ lọc so tên
    miền mà lệch nhau thì cái lỏng hơn sẽ luôn là cái được dùng.
    """
    from eaa.ingest import SourceRejected, check_web_source

    try:
        check_web_source(url)
    except SourceRejected:
        return MO
    return CHINH_CHU


# --------------------------------------------------------------------------
# HTML → chữ
# --------------------------------------------------------------------------


class _BocChu(HTMLParser):
    """Bóc phần chữ đọc được, bỏ script/style và giữ lại đường dẫn.

    Không dùng thư viện ngoài (NFR-04). Bộ bóc này không cần đúng với mọi HTML
    hỏng trên đời — nó chỉ cần đủ tốt để mô hình đọc được nội dung, và đủ đơn
    giản để không có chỗ nào bất ngờ.
    """

    # ``head`` KHÔNG nằm trong danh sách này: bỏ cả head thì mất luôn ``title``,
    # mà tiêu đề trang là thứ duy nhất cho biết ta vừa đọc đúng trang hay chưa.
    # Phần rác trong head (meta, link) không sinh ra chữ nên không cần bỏ.
    _BO_QUA = {"script", "style", "noscript", "svg"}
    _NGAT = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "pre", "table", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.phan: list[str] = []
        self.tieu_de = ""
        self.lien_ket: list[tuple[str, str]] = []
        self._bo_qua = 0
        self._trong_title = False
        self._href = ""
        self._chu_link: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BO_QUA:
            self._bo_qua += 1
        if tag == "title":
            self._trong_title = True
        if tag in self._NGAT:
            self.phan.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._chu_link = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BO_QUA and self._bo_qua:
            self._bo_qua -= 1
        if tag == "title":
            self._trong_title = False
        if tag in self._NGAT:
            self.phan.append("\n")
        if tag == "a":
            chu = " ".join(self._chu_link).strip()
            if self._href and chu:
                self.lien_ket.append((chu, self._href))
            self._href = ""
            self._chu_link = []

    def handle_data(self, data: str) -> None:
        if self._bo_qua:
            return
        if self._trong_title:
            self.tieu_de += data.strip()
            return
        self.phan.append(data)
        if self._href:
            self._chu_link.append(data.strip())


def html_to_text(html: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Trả ``(chữ, tiêu đề, [(chữ liên kết, href)])``."""
    boc = _BocChu()
    try:
        boc.feed(html)
        boc.close()
    except Exception:  # noqa: BLE001 - HTML hỏng không được làm sập lượt chạy
        pass
    chu = "".join(boc.phan)
    chu = re.sub(r"[ \t\r\f\v]+", " ", chu)
    chu = re.sub(r"\n\s*\n\s*\n+", "\n\n", chu)
    dong = [d.strip() for d in chu.split("\n")]
    return "\n".join(d for d in dong if d), boc.tieu_de.strip(), boc.lien_ket


# --------------------------------------------------------------------------
# Tài liệu tải về
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WebDocument:
    """Một trang đã tải, kèm đủ dấu vết để kiểm lại về sau."""

    url: str
    """URL CUỐI CÙNG sau khi đi hết chuyển hướng — hạng tin cậy tính theo cái này."""

    requested: str
    status: int
    content_type: str
    text: str
    title: str = ""
    links: tuple[tuple[str, str], ...] = ()
    tier: str = MO
    byte_count: int = 0
    sha256: str = ""
    fetched_at: str = ""
    truncated: bool = False
    from_cache: bool = False

    @property
    def usable_as_knowledge(self) -> bool:
        """Nội dung này có được phép thành trích đoạn tri thức không.

        Chỉ hạng chính chủ. Hạng mở dùng để gỡ lỗi và so sánh công cụ, và dừng
        ở đó — một câu trên diễn đàn đi kèm đường dẫn trông đàng hoàng là thứ
        khó bị nghi ngờ hơn hẳn một câu không có gì (AIS §12).
        """
        return self.tier == CHINH_CHU and self.status == 200

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung (N-903).

        Hạng chính chủ là SUY RA chứ KHÔNG phải ĐÃ KIỂM. Thứ ta kiểm được khi
        tải một trang là nó **từ đâu ra**, không phải nó **nói đúng không** —
        và ĐÃ KIỂM trong hệ này nghĩa là có một phép đo hoặc một cổng đã chạy.
        Gắn ĐÃ KIỂM cho một trang web là đúng loại nhầm lẫn mà cả bộ từ vựng
        này sinh ra để chặn: nó biến "đọc được ở nguồn tin cậy" thành "đã kiểm
        chứng", và một giá trị thanh ghi sai sẽ đi thẳng vào mã với nhãn cao
        nhất. Nội dung chỉ lên ĐÃ KIỂM sau khi qua gate tri thức.
        """
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return SUY_RA if self.tier == CHINH_CHU else KHONG_KIEM_DUOC

    @property
    def domain(self) -> str:
        return (urlparse(self.url).hostname or "").lower()

    def excerpt(self, limit: int = 4000) -> str:
        return self.text if len(self.text) <= limit else self.text[:limit] + "\n…(cắt)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "requested": self.requested,
            "status": self.status,
            "content_type": self.content_type,
            "text": self.text,
            "title": self.title,
            "links": [list(x) for x in self.links],
            "tier": self.tier,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "fetched_at": self.fetched_at,
            "truncated": self.truncated,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WebDocument":
        return cls(
            url=d.get("url", ""),
            requested=d.get("requested", ""),
            status=int(d.get("status", 0)),
            content_type=d.get("content_type", ""),
            text=d.get("text", ""),
            title=d.get("title", ""),
            links=tuple(tuple(x) for x in d.get("links", []) if len(x) == 2),
            tier=d.get("tier", MO),
            byte_count=int(d.get("byte_count", 0)),
            sha256=d.get("sha256", ""),
            fetched_at=d.get("fetched_at", ""),
            truncated=bool(d.get("truncated", False)),
            from_cache=True,
        )

    def render(self) -> str:
        from eaa.confidence import describe

        dong = [
            f"{self.title or '(không có tiêu đề)'}",
            f"  {self.url}",
            f"  hạng: {self.tier} · HTTP {self.status} · {self.byte_count} byte"
            + ("  · lấy từ bộ đệm" if self.from_cache else ""),
            f"  {describe(self.confidence_level)}",
        ]
        if not self.usable_as_knowledge and self.tier == MO:
            dong.append(
                "  ⚠ Hạng MỞ: dùng làm manh mối để gỡ lỗi hoặc so công cụ. "
                "KHÔNG được dùng làm nguồn cho giá trị cấu hình phần cứng."
            )
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Bộ đệm
# --------------------------------------------------------------------------


@dataclass
class WebCache:
    """Bộ đệm đĩa — để tái lập trước, để nhanh sau."""

    root: Path
    #: Số âm nghĩa là giữ mãi. ``0`` nghĩa là bản đệm nào cũng coi như quá hạn
    #: — dùng khi cần chắc chắn đang đọc bản mới nhất.
    ttl_s: float = 7 * 24 * 3600

    def _tep(self, url: str) -> Path:
        return self.root / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:32] + ".json")

    def get(self, url: str) -> WebDocument | None:
        tep = self._tep(url)
        if not tep.is_file():
            return None
        try:
            d = json.loads(tep.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if self.ttl_s >= 0:
            try:
                cu = datetime.fromisoformat(d.get("fetched_at", ""))
                if (datetime.now(timezone.utc) - cu).total_seconds() > self.ttl_s:
                    return None
            except ValueError:
                return None
        return WebDocument.from_dict(d)

    def put(self, doc: WebDocument) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tep = self._tep(doc.requested or doc.url)
        tam = tep.with_suffix(".tmp")
        tam.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        tam.replace(tep)


# --------------------------------------------------------------------------
# Kiểm an toàn URL
# --------------------------------------------------------------------------


def _kiem_url(url: str, *, resolver: Callable[[str], list[str]] | None = None) -> str:
    """Kiểm một URL trước khi nối. Trả về host; ném :class:`UnsafeUrl` nếu không đi được.

    Phân giải tên miền TRƯỚC khi nối và từ chối mọi địa chỉ nội bộ. Không có
    bước này thì ``http://localhost:8080/…`` hay một tên miền công cộng trỏ về
    ``169.254.169.254`` đều là đường để một URL do mô hình sinh ra đọc được thứ
    nằm trong máy người dùng.
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise UnsafeUrl(
            f"Chỉ nối http/https; {url!r} dùng {p.scheme or '(không có)'}. "
            "Giao thức khác (file, ftp, gopher) là đường đọc tệp nội bộ."
        )
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeUrl(f"Không đọc được tên miền từ {url!r}")

    lay = resolver or _phan_giai
    try:
        dia_chi = lay(host)
    except OSError as exc:
        raise FetchFailed(f"Không phân giải được tên miền {host!r}: {exc}") from None
    if not dia_chi:
        raise FetchFailed(f"Không phân giải được tên miền {host!r}")

    for a in dia_chi:
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise UnsafeUrl(
                f"{host!r} phân giải ra địa chỉ nội bộ {a}. Từ chối: một URL trỏ "
                "vào mạng riêng của bạn không phải một nguồn tài liệu."
            )
    return host


def _phan_giai(host: str) -> list[str]:
    return sorted({t[4][0] for t in socket.getaddrinfo(host, None)})


# --------------------------------------------------------------------------
# Bộ tải
# --------------------------------------------------------------------------


@dataclass
class WebFetcher:
    """Tải trang, có chặn, có trần, có bộ đệm.

    Lớp vận chuyển tiêm được (``transport``) vì mọi nhánh xử lý lỗi — 404, quá
    hạn, chuyển hướng ra khỏi hạng, trang quá lớn — đều là những nhánh sẽ chạy
    vào đúng lúc tệ nhất, nên chúng phải kiểm được bằng test.
    """

    cache: WebCache | None = None
    timeout_s: float = TIMEOUT_S
    max_bytes: int = MAX_BYTES
    max_redirects: int = MAX_REDIRECTS
    #: ``(url, timeout) -> (status, url_cuối, headers, bytes)``
    transport: Any = None
    resolver: Callable[[str], list[str]] | None = None
    #: Số lần thử lại cho lỗi tạm thời, cùng kỷ luật với adapter mô hình.
    max_retries: int = 2
    backoff_s: float = 1.5
    sleep: Callable[[float], None] = time.sleep

    def enabled(self) -> bool:
        return not mang_bi_tat()

    def fetch(self, url: str, *, refresh: bool = False) -> WebDocument:
        if not self.enabled():
            raise NetworkDisabled(
                f"Lối ra mạng đang tắt ({NO_NET_ENV}=1). Bỏ biến ấy đi để cho phép, "
                "hoặc nạp tài liệu từ tệp bằng 'eaa datasheet add'."
            )
        if self.cache is not None and not refresh:
            cu = self.cache.get(url)
            if cu is not None:
                return cu

        doc = self._tai(url)
        if self.cache is not None:
            self.cache.put(doc)
        return doc

    # ----------------------------------------------------------------------

    def _tai(self, url: str) -> WebDocument:
        hien_tai = url
        for _ in range(self.max_redirects + 1):
            _kiem_url(hien_tai, resolver=self.resolver)
            status, url_cuoi, headers, than = self._gui(hien_tai)

            if status in (301, 302, 303, 307, 308):
                dich = headers.get("Location") or headers.get("location") or ""
                if not dich:
                    raise FetchFailed(f"HTTP {status} nhưng không có Location: {hien_tai}")
                hien_tai = urljoin(hien_tai, dich)
                continue

            if status != 200:
                raise FetchFailed(f"HTTP {status} khi tải {hien_tai}")

            return self._dung_tai_lieu(url, url_cuoi or hien_tai, status, headers, than)

        raise FetchFailed(
            f"Quá {self.max_redirects} lần chuyển hướng từ {url!r}. Chuỗi chuyển "
            "hướng dài bất thường thường là một vòng, hoặc một trang chặn bot."
        )

    def _gui(self, url: str) -> tuple[int, str, dict[str, str], bytes]:
        gui = self.transport or self._urllib
        loi_cuoi: Exception | None = None
        for lan in range(self.max_retries + 1):
            try:
                return gui(url, self.timeout_s, self.max_bytes)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                # Lỗi mạng là loại đáng thử lại; 4xx thì không, và nhánh ấy đi
                # qua HTTPError bên dưới nên không rơi vào đây.
                loi_cuoi = FetchFailed(f"Lỗi mạng khi tải {url}: {exc}")
                if lan < self.max_retries:
                    self.sleep(self.backoff_s * (2**lan))
                    continue
                raise loi_cuoi from None
        raise loi_cuoi or FetchFailed(f"Không tải được {url}")

    @staticmethod
    def _urllib(url: str, timeout: float, max_bytes: int) -> tuple[int, str, dict[str, str], bytes]:
        class _KhongTheoChuyenHuong(urllib.request.HTTPRedirectHandler):
            """Không tự đi theo chuyển hướng — mỗi chặng phải qua lại bộ kiểm.

            ``urllib`` mặc định đi theo tới 10 chặng và không kể lại. Với một
            danh sách trắng theo tên miền thì đó chính là cách bị vượt.
            """

            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
                return None

        opener = urllib.request.build_opener(_KhongTheoChuyenHuong)
        yeu_cau = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.5",
                "Accept-Language": "en,vi;q=0.8",
            },
        )
        try:
            with opener.open(yeu_cau, timeout=timeout) as ph:
                return (
                    int(ph.status),
                    ph.geturl(),
                    {k: v for k, v in ph.headers.items()},
                    ph.read(max_bytes + 1),
                )
        except urllib.error.HTTPError as exc:
            than = b""
            try:
                than = exc.read(max_bytes + 1)
            except Exception:  # pragma: no cover - thân lỗi không đọc được
                pass
            return int(exc.code), url, {k: v for k, v in (exc.headers or {}).items()}, than

    def _dung_tai_lieu(
        self, goc: str, cuoi: str, status: int, headers: dict[str, str], than: bytes
    ) -> WebDocument:
        cat = len(than) > self.max_bytes
        if cat:
            than = than[: self.max_bytes]

        kieu = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
        if kieu and not any(k in kieu for k in _KIEU_CHU):
            raise FetchFailed(
                f"{cuoi} trả kiểu {kieu.split(';')[0]!r}, không phải nội dung chữ. "
                "Tệp nhị phân (PDF, ảnh, gói cài) phải nạp qua 'eaa datasheet add' "
                "để đi đúng đường kiểm nguồn, không qua bộ đọc trang."
            )

        ma_hoa = "utf-8"
        khop = re.search(r"charset=([\w\-]+)", kieu)
        if khop:
            ma_hoa = khop.group(1)
        try:
            van_ban = than.decode(ma_hoa, errors="replace")
        except LookupError:
            van_ban = than.decode("utf-8", errors="replace")

        if "html" in kieu or van_ban.lstrip()[:200].lower().startswith(("<!doctype", "<html")):
            chu, tieu_de, lien_ket = html_to_text(van_ban)
        else:
            chu, tieu_de, lien_ket = van_ban, "", []

        return WebDocument(
            url=cuoi,
            requested=goc,
            status=status,
            content_type=kieu.split(";")[0],
            text=chu,
            title=tieu_de,
            links=tuple(lien_ket[:200]),
            # Hạng tính theo URL CUỐI: một miền chính chủ chuyển hướng ra ngoài
            # phải mất hạng, nếu không thì danh sách trắng chỉ là trang trí.
            tier=classify(cuoi),
            byte_count=len(than),
            sha256=hashlib.sha256(than).hexdigest(),
            fetched_at=_now(),
            truncated=cat,
        )


def fetch(url: str, **kw: Any) -> WebDocument:
    """Tải một trang bằng bộ tải mặc định."""
    cache_dir = kw.pop("cache_dir", None)
    fetcher = WebFetcher(cache=WebCache(Path(cache_dir)) if cache_dir else None, **kw)
    return fetcher.fetch(url)
