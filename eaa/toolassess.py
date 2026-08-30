"""Công cụ này có đáng cài không — đọc kho gói, không hỏi trí nhớ mô hình.

EAA-AIS-05 §9.2, §9.4; FR-ENV-03. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-85.

Khoảng trống module này lấp
----------------------------

``eaa doctor --discover --propose`` đề xuất được một công cụ, và từ SL-80 nó
đọc được cả trang cài đặt thật. Nhưng phần **đánh giá** vẫn đổ hết lên người
duyệt: gói này còn ai bảo trì không, license gì, có bao nhiêu người dùng, tên
có gõ đúng không. Người duyệt ngồi trước một đề xuất trông rất chỉn chu và
không có cách nào kiểm nhanh mấy câu ấy.

Bốn câu hỏi, và cả bốn đều tra được
------------------------------------

* **Còn bảo trì không** — lần phát hành gần nhất cách đây bao lâu.
* **License gì** — có phải loại dùng được trong sản phẩm không.
* **Bao nhiêu người dùng** — không phải thước đo chất lượng, nhưng một gói
  không ai dùng thì cũng không ai tìm ra lỗi giúp bạn.
* **Tên có thật không** — và đây là câu quan trọng nhất, xem phần dưới.

Chống gõ nhầm tên gói: kiểm SỰ TỒN TẠI
---------------------------------------

``eaa/toolsearch.py`` đã chặn nguồn cài lạ (danh sách trắng trình quản lý gói,
đòi checksum khi tải trực tiếp). Nó **không** chặn được một tên gói gõ nhầm
một ký tự trỏ tới một gói khác **có thật** — kiểu tấn công nhắm đúng vào người
đọc lướt.

Ở đây câu trả lời không phải một danh sách đen (không bao giờ đủ) mà là một
câu hỏi đảo lại: *gói này có tồn tại trong kho chính thức không, và nó trông
ra sao?* Một gói mới tạo hôm qua, không license, ba lượt tải, mang cái tên gần
giống một gói nổi tiếng — bốn con số ấy nói lên điều mà một danh sách đen
không nói được.

Hạng tin cậy của những số này
------------------------------

Kho gói (PyPI, npm, GitHub) **không** thuộc miền nhà sản xuất chip, nên theo
``eaa/web.py`` chúng là hạng ``mở``. Điều đó đúng và cần giữ: những số ở đây
dùng để **so công cụ và gỡ lỗi**, tuyệt đối không để làm nguồn cho một giá trị
cấu hình phần cứng. Nhãn đi kèm luôn là SUY RA, và bản in nói rõ điều đó.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

__all__ = [
    "AssessError",
    "PackageFacts",
    "Assessment",
    "assess",
    "KHO_HO_TRO",
    "NGAY_COI_LA_BO_HOANG",
    "LICENSE_THOANG",
]

#: Kho gói tra được, và cách dựng URL siêu dữ liệu JSON của chúng.
KHO_HO_TRO: dict[str, str] = {
    "pypi": "https://pypi.org/pypi/{ten}/json",
    "npm": "https://registry.npmjs.org/{ten}",
    "github": "https://api.github.com/repos/{ten}",
}

#: Không phát hành gì quá lâu thì coi như bỏ hoang. Hai năm chứ không phải sáu
#: tháng: một công cụ dòng lệnh nhỏ làm xong việc của nó thì KHÔNG cần phát
#: hành thêm, và phạt nó vì điều đó là đọc sai chỉ số.
NGAY_COI_LA_BO_HOANG = 730

#: License dùng được trong một sản phẩm mà không kéo theo ràng buộc lan tỏa.
#: Danh sách này KHÔNG phải lời khuyên pháp lý — nó chỉ đánh dấu chỗ cần người
#: đọc kỹ, và mọi thứ ngoài danh sách đều được đánh dấu chứ không bị loại.
LICENSE_THOANG: tuple[str, ...] = (
    "mit", "bsd", "apache", "isc", "zlib", "python software foundation", "psf",
    "unlicense", "cc0", "mpl",
)


class AssessError(Exception):
    """Không tra được siêu dữ liệu gói."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _doc_ngay(gia_tri: Any) -> datetime | None:
    van_ban = str(gia_tri or "").strip()
    if not van_ban:
        return None
    van_ban = van_ban.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(van_ban)
    except ValueError:
        khop = re.match(r"(\d{4})-(\d{2})-(\d{2})", van_ban)
        if not khop:
            return None
        d = datetime(*(int(x) for x in khop.groups()))  # type: ignore[arg-type]
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PackageFacts:
    """Dữ kiện đọc được từ kho gói. Chỉ dữ kiện, chưa phán xét."""

    name: str
    registry: str
    exists: bool = False
    version: str = ""
    license: str = ""
    last_release: datetime | None = None
    downloads: int = 0
    stars: int = 0
    open_issues: int = 0
    homepage: str = ""
    summary: str = ""
    url: str = ""

    @property
    def days_since_release(self) -> int | None:
        if self.last_release is None:
            return None
        return max(0, (_now() - self.last_release).days)


@dataclass(frozen=True)
class Assessment:
    """Dữ kiện, cộng với những chỗ người duyệt cần nhìn kỹ."""

    facts: PackageFacts
    flags: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.flags

    @property
    def confidence_level(self) -> str:
        """Không tra được thì KHÔNG KIỂM ĐƯỢC; tra được thì SUY RA.

        Không bao giờ ĐÃ KIỂM: những số này tới từ kho gói (hạng ``mở``), và
        chúng nói về gói chứ không nói về việc gói ấy có hợp với dự án này
        không — câu ấy vẫn là của người duyệt.
        """
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return SUY_RA if self.facts.exists else KHONG_KIEM_DUOC

    def render(self) -> str:
        from eaa.confidence import header

        f = self.facts
        dong = [f"Đánh giá gói {f.name!r} trên {f.registry}", "",
                header(self.confidence_level), ""]

        if not f.exists:
            dong += [
                f"  ✗ KHÔNG TÌM THẤY gói này trên {f.registry}.",
                "",
                "  Đây là dấu hiệu đáng dừng lại: một lệnh cài trỏ tới một gói "
                "không tồn tại sẽ hỏng ngay — nhưng một TÊN GÕ NHẦM một ký tự có "
                "thể trỏ tới một gói khác CÓ THẬT. Kiểm lại tên trước khi cài.",
            ]
            return "\n".join(dong)

        tuoi = f.days_since_release
        dong += [
            f"  phiên bản     : {f.version or '(không rõ)'}",
            f"  license       : {f.license or '(không khai)'}",
            f"  phát hành cuối: " + (f"{tuoi} ngày trước" if tuoi is not None else "(không rõ)"),
        ]
        if f.downloads:
            dong.append(f"  lượt tải      : {f.downloads:,}".replace(",", "."))
        if f.stars:
            dong.append(f"  sao / issue mở: {f.stars} / {f.open_issues}")
        if f.homepage:
            dong.append(f"  trang chính   : {f.homepage}")
        if f.summary:
            dong.append(f"  mô tả         : {f.summary[:120]}")

        if self.flags:
            dong += ["", "CẦN NHÌN KỸ:"]
            dong += [f"  ⚠ {c}" for c in self.flags]
        else:
            dong += ["", "Không có dấu hiệu nào đáng ngại trong bốn chỉ số tra được."]

        if self.notes:
            dong += [""] + [f"  {g}" for g in self.notes]

        dong += [
            "",
            "Những số trên tới từ kho gói — hạng MỞ. Dùng để so công cụ và gỡ lỗi;",
            "KHÔNG dùng làm nguồn cho bất kỳ giá trị cấu hình phần cứng nào.",
            "Câu 'gói này có hợp với dự án của tôi không' vẫn là câu của bạn.",
        ]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Đọc từng kho
# --------------------------------------------------------------------------


def _doc_pypi(ten: str, d: dict[str, Any], url: str) -> PackageFacts:
    thong_tin = d.get("info") or {}
    ban = d.get("releases") or {}
    phien_ban = str(thong_tin.get("version", ""))
    ngay = None
    for tep in ban.get(phien_ban) or []:
        ngay = _doc_ngay(tep.get("upload_time_iso_8601") or tep.get("upload_time"))
        if ngay:
            break
    giay_phep = str(thong_tin.get("license") or "")
    if not giay_phep:
        for phan_loai in thong_tin.get("classifiers") or []:
            if str(phan_loai).startswith("License ::"):
                giay_phep = str(phan_loai).split("::")[-1].strip()
                break
    return PackageFacts(
        name=ten, registry="pypi", exists=True, version=phien_ban,
        license=giay_phep, last_release=ngay,
        homepage=str(thong_tin.get("home_page") or thong_tin.get("project_url") or ""),
        summary=str(thong_tin.get("summary") or ""), url=url,
    )


def _doc_npm(ten: str, d: dict[str, Any], url: str) -> PackageFacts:
    thoi_gian = d.get("time") or {}
    moi_nhat = str((d.get("dist-tags") or {}).get("latest", ""))
    return PackageFacts(
        name=ten, registry="npm", exists=True, version=moi_nhat,
        license=str(d.get("license") or ""),
        last_release=_doc_ngay(thoi_gian.get(moi_nhat) or thoi_gian.get("modified")),
        homepage=str(d.get("homepage") or ""),
        summary=str(d.get("description") or ""), url=url,
    )


def _doc_github(ten: str, d: dict[str, Any], url: str) -> PackageFacts:
    return PackageFacts(
        name=ten, registry="github", exists=True,
        version=str(d.get("default_branch") or ""),
        license=str((d.get("license") or {}).get("spdx_id") or ""),
        last_release=_doc_ngay(d.get("pushed_at")),
        stars=int(d.get("stargazers_count") or 0),
        open_issues=int(d.get("open_issues_count") or 0),
        homepage=str(d.get("homepage") or d.get("html_url") or ""),
        summary=str(d.get("description") or ""), url=url,
    )


_BO_DOC = {"pypi": _doc_pypi, "npm": _doc_npm, "github": _doc_github}


def assess(
    name: str,
    *,
    registry: str = "pypi",
    fetcher: Any = None,
    similar_to: Sequence[str] = (),
) -> Assessment:
    """Tra một gói và đánh dấu những chỗ người duyệt cần nhìn kỹ.

    ``similar_to`` là danh sách tên gói phổ biến để so — dùng để bắt tên gõ
    nhầm một ký tự. Không truyền thì bỏ qua phần kiểm ấy.
    """
    if registry not in KHO_HO_TRO:
        raise AssessError(
            f"Chưa tra được kho {registry!r}. Đang hỗ trợ: {', '.join(KHO_HO_TRO)}"
        )
    ten = (name or "").strip()
    if not ten:
        raise AssessError("Phải nêu tên gói")

    from eaa.web import WebError, WebFetcher

    url = KHO_HO_TRO[registry].format(ten=ten)
    f = fetcher or WebFetcher()
    try:
        doc = f.fetch(url)
        du_lieu = json.loads(doc.text)
    except WebError as exc:
        # Không tìm thấy là một KẾT QUẢ, không phải một lỗi: đó chính là câu
        # trả lời cho "tên này có thật không".
        if "404" in str(exc):
            return Assessment(
                facts=PackageFacts(name=ten, registry=registry, exists=False, url=url),
                flags=(f"không tồn tại trên {registry}",),
            )
        raise AssessError(f"Không tra được {ten!r} trên {registry}: {exc}") from None
    except json.JSONDecodeError:
        raise AssessError(f"{registry} trả về thứ không phải JSON cho {ten!r}") from None

    du_kien = _BO_DOC[registry](ten, du_lieu, url)
    return Assessment(facts=du_kien, flags=tuple(_danh_dau(du_kien, similar_to)),
                      notes=tuple(_ghi_chu(du_kien)))


def _danh_dau(f: PackageFacts, similar_to: Sequence[str] = ()) -> list[str]:
    """Những chỗ đáng dừng lại. Đánh dấu, KHÔNG loại — loại là việc của người."""
    co: list[str] = []

    tuoi = f.days_since_release
    if tuoi is not None and tuoi > NGAY_COI_LA_BO_HOANG:
        co.append(f"phát hành cuối cách đây {tuoi} ngày — có thể đã bỏ hoang")

    if not f.license:
        co.append("không khai license — không biết dùng được trong sản phẩm hay không")
    elif not any(k in f.license.lower() for k in LICENSE_THOANG):
        co.append(f"license {f.license!r} nằm ngoài nhóm quen thuộc — đọc kỹ trước khi dùng")

    if f.registry == "github" and f.stars and f.stars < 20:
        co.append(f"chỉ {f.stars} sao — ít người dùng thì cũng ít người tìm ra lỗi giúp bạn")

    # Gõ nhầm một ký tự: tên gần giống một gói phổ biến nhưng KHÔNG phải nó.
    for pho_bien in similar_to:
        if f.name != pho_bien and _khoang_cach_mot(f.name, pho_bien):
            co.append(
                f"tên chỉ khác {pho_bien!r} một ký tự — kiểu nhầm này nhắm đúng "
                "vào người đọc lướt. Xác nhận lại tên trước khi cài."
            )
    return co


def _ghi_chu(f: PackageFacts) -> list[str]:
    tuoi = f.days_since_release
    if tuoi is not None and tuoi > 365 and tuoi <= NGAY_COI_LA_BO_HOANG:
        return ["Lâu không phát hành chưa chắc là bỏ hoang: một công cụ nhỏ làm "
                "xong việc của nó thì không cần phát hành thêm."]
    return []


def _khoang_cach_mot(a: str, b: str) -> bool:
    """Hai tên có cách nhau đúng một phép sửa không (thêm/bớt/đổi một ký tự)."""
    a, b = a.lower(), b.lower()
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    dai, ngan = (a, b) if len(a) > len(b) else (b, a)
    for i in range(len(dai)):
        if dai[:i] + dai[i + 1:] == ngan:
            return True
    return False
