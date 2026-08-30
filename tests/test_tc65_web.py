"""TC-65 — lớp truy cập mạng: hai hạng tin cậy và bốn cái chặn.

Mọi bài ở đây tiêm lớp vận chuyển. Một bài kiểm mạng mà thật sự ra mạng thì
hỏng theo nhịp của người khác, và những nhánh cần kiểm nhất — chuyển hướng ra
khỏi hạng, trang quá lớn, tên miền trỏ về mạng nội bộ — lại đúng là những
nhánh không đặt hàng được từ một máy chủ thật.
"""

from __future__ import annotations

import json

import pytest

from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC, SUY_RA
from eaa.web import (
    CHINH_CHU,
    MO,
    NO_NET_ENV,
    FetchFailed,
    NetworkDisabled,
    UnsafeUrl,
    WebCache,
    WebDocument,
    WebFetcher,
    classify,
    html_to_text,
)

CONG_KHAI = ["93.184.216.34"]


def _transport(trang: dict[str, tuple[int, dict[str, str], bytes]]):
    """Máy chủ giả: url → (status, headers, thân)."""

    def gui(url: str, timeout: float, max_bytes: int):
        if url not in trang:
            raise AssertionError(f"bài test không dựng trang cho {url}")
        status, headers, than = trang[url]
        return status, url, headers, than[: max_bytes + 1]

    return gui


def _fetcher(trang, **kw) -> WebFetcher:
    kw.setdefault("resolver", lambda host: CONG_KHAI)
    return WebFetcher(transport=_transport(trang), **kw)


HTML = (
    b"<html><head><title>Trang thu</title><style>a{}</style></head>"
    b"<body><h1>Tieu de</h1><p>Noi dung mot.</p>"
    b"<script>var x=1;</script><p>Noi dung <a href='/tiep'>hai</a>.</p></body></html>"
)
HEAD_HTML = {"Content-Type": "text/html; charset=utf-8"}


# ---------------------------------------------------------------- hạng ---


def test_mien_nha_san_xuat_la_hang_chinh_chu():
    assert classify("https://www.microchip.com/en-us/product/x") == CHINH_CHU
    assert classify("https://ww1.microchip.com/downloads/a.pdf") == CHINH_CHU


def test_mien_khac_la_hang_mo():
    assert classify("https://stackoverflow.com/questions/1") == MO
    assert classify("https://blog.example.com/bai-viet") == MO


def test_mien_gia_mao_khong_duoc_len_hang_chinh_chu():
    """Hậu tố phải khớp theo NHÃN tên miền, không theo chuỗi con."""
    assert classify("https://microchip.com.kho-tai-lieu-lau.net/x") == MO


def test_hang_chinh_chu_dung_duoc_lam_tri_thuc_hang_mo_thi_khong():
    f = _fetcher({"https://www.microchip.com/a": (200, HEAD_HTML, HTML)})
    doc = f.fetch("https://www.microchip.com/a")
    assert doc.usable_as_knowledge is True
    # Chính chủ vẫn KHÔNG phải ĐÃ KIỂM: ta kiểm được nguồn, không kiểm được nội
    # dung. Nội dung chỉ lên ĐÃ KIỂM sau khi qua gate tri thức.
    assert doc.confidence_level == SUY_RA
    assert doc.confidence_level != DA_KIEM

    f2 = _fetcher({"https://forum.example.com/a": (200, HEAD_HTML, HTML)})
    doc2 = f2.fetch("https://forum.example.com/a")
    assert doc2.usable_as_knowledge is False
    assert doc2.confidence_level == KHONG_KIEM_DUOC
    assert "manh mối" in doc2.render() or "KHÔNG được dùng làm nguồn" in doc2.render()


# ------------------------------------------------------------- chuyển hướng ---


def test_chuyen_huong_ra_khoi_hang_thi_mat_hang():
    """Đây là cách một danh sách trắng bị vượt mà trông vẫn đúng."""
    f = _fetcher({
        "https://www.microchip.com/di": (302, {"Location": "https://cdn.example.net/that"}, b""),
        "https://cdn.example.net/that": (200, HEAD_HTML, HTML),
    })
    doc = f.fetch("https://www.microchip.com/di")
    assert doc.tier == MO
    assert doc.usable_as_knowledge is False
    assert doc.url == "https://cdn.example.net/that"
    assert doc.requested == "https://www.microchip.com/di"


def test_chuyen_huong_tuong_doi_duoc_noi_dung_goc():
    f = _fetcher({
        "https://www.microchip.com/a": (301, {"Location": "/b"}, b""),
        "https://www.microchip.com/b": (200, HEAD_HTML, HTML),
    })
    assert f.fetch("https://www.microchip.com/a").tier == CHINH_CHU


def test_vong_chuyen_huong_bi_chan_theo_tran():
    f = _fetcher(
        {"https://a.example.com/x": (302, {"Location": "https://a.example.com/x"}, b"")},
        max_redirects=2,
    )
    with pytest.raises(FetchFailed, match="chuyển hướng"):
        f.fetch("https://a.example.com/x")


def test_chuyen_huong_khong_co_location_la_loi_ro_rang():
    f = _fetcher({"https://a.example.com/x": (302, {}, b"")})
    with pytest.raises(FetchFailed, match="Location"):
        f.fetch("https://a.example.com/x")


# ------------------------------------------------------------------ SSRF ---


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254"])
def test_ten_mien_tro_ve_mang_noi_bo_bi_tu_choi(ip):
    f = WebFetcher(transport=_transport({}), resolver=lambda host: [ip])
    with pytest.raises(UnsafeUrl, match="nội bộ"):
        f.fetch("https://tro-vao-trong.example.com/x")


def test_chuyen_huong_vao_mang_noi_bo_cung_bi_chan():
    """Chặng đầu công khai không mua được quyền cho chặng sau."""
    dia_chi = {"ngoai.example.com": CONG_KHAI, "trong.example.com": ["127.0.0.1"]}
    f = WebFetcher(
        transport=_transport({
            "https://ngoai.example.com/a": (302, {"Location": "https://trong.example.com/b"}, b""),
        }),
        resolver=lambda host: dia_chi[host],
    )
    with pytest.raises(UnsafeUrl, match="nội bộ"):
        f.fetch("https://ngoai.example.com/a")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://a.example.com/x", "gopher://a/b"])
def test_giao_thuc_khac_bi_tu_choi(url):
    f = WebFetcher(transport=_transport({}), resolver=lambda host: CONG_KHAI)
    with pytest.raises(UnsafeUrl, match="http"):
        f.fetch(url)


# ------------------------------------------------------------------ trần ---


def test_trang_qua_lon_bi_cat_va_danh_dau():
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, b"<p>" + b"x" * 5000)}, max_bytes=500)
    doc = f.fetch("https://a.example.com/x")
    assert doc.truncated is True
    assert doc.byte_count == 500


def test_kieu_nhi_phan_bi_tu_choi_va_chi_sang_duong_dung():
    f = _fetcher({"https://a.example.com/x.pdf": (200, {"Content-Type": "application/pdf"}, b"%PDF")})
    with pytest.raises(FetchFailed, match="datasheet add"):
        f.fetch("https://a.example.com/x.pdf")


def test_loi_mang_duoc_thu_lai_co_backoff():
    lan = {"n": 0}
    cho = []

    def gui(url, timeout, max_bytes):
        lan["n"] += 1
        if lan["n"] < 3:
            raise OSError("mạng chập")
        return 200, url, HEAD_HTML, HTML

    f = WebFetcher(transport=gui, resolver=lambda h: CONG_KHAI, sleep=cho.append)
    assert f.fetch("https://a.example.com/x").status == 200
    assert lan["n"] == 3
    assert cho == [1.5, 3.0]


def test_het_luot_thu_thi_bao_loi_chu_khong_treo():
    def gui(url, timeout, max_bytes):
        raise OSError("mạng chập")

    f = WebFetcher(transport=gui, resolver=lambda h: CONG_KHAI, sleep=lambda s: None)
    with pytest.raises(FetchFailed, match="Lỗi mạng"):
        f.fetch("https://a.example.com/x")


# ------------------------------------------------------------ công tắc ngắt ---


def test_cong_tac_ngat_chan_moi_loi_ra(monkeypatch):
    monkeypatch.setenv(NO_NET_ENV, "1")
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)})
    with pytest.raises(NetworkDisabled, match=NO_NET_ENV):
        f.fetch("https://a.example.com/x")


def test_bo_cong_tac_thi_lai_di_duoc(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)})
    assert f.fetch("https://a.example.com/x").status == 200


# ------------------------------------------------------------------ bộ đệm ---


def test_bo_dem_tra_lai_dung_noi_dung_va_danh_dau_la_tu_dem(tmp_path):
    cache = WebCache(tmp_path / "web")
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)}, cache=cache)
    d1 = f.fetch("https://a.example.com/x")
    assert d1.from_cache is False

    f2 = WebFetcher(transport=_transport({}), cache=cache, resolver=lambda h: CONG_KHAI)
    d2 = f2.fetch("https://a.example.com/x")
    assert d2.from_cache is True
    assert d2.text == d1.text
    assert d2.sha256 == d1.sha256


def test_bo_dem_giu_lai_moc_thoi_gian_va_bam_de_kiem_lai_sau(tmp_path):
    cache = WebCache(tmp_path / "web")
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)}, cache=cache)
    f.fetch("https://a.example.com/x")
    tep = next((tmp_path / "web").glob("*.json"))
    d = json.loads(tep.read_text(encoding="utf-8"))
    assert d["sha256"] and d["fetched_at"]


def test_bo_dem_qua_han_thi_tai_lai(tmp_path):
    cache = WebCache(tmp_path / "web", ttl_s=0)
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)}, cache=cache)
    f.fetch("https://a.example.com/x")
    f2 = WebFetcher(transport=_transport({}), cache=cache, resolver=lambda h: CONG_KHAI)
    with pytest.raises(AssertionError):
        f2.fetch("https://a.example.com/x")


def test_refresh_bo_qua_bo_dem(tmp_path):
    cache = WebCache(tmp_path / "web")
    f = _fetcher({"https://a.example.com/x": (200, HEAD_HTML, HTML)}, cache=cache)
    f.fetch("https://a.example.com/x")
    assert f.fetch("https://a.example.com/x", refresh=True).from_cache is False


# -------------------------------------------------------------- HTML → chữ ---


def test_boc_chu_bo_script_style_va_giu_lien_ket():
    chu, tieu_de, lien_ket = html_to_text(HTML.decode())
    assert tieu_de == "Trang thu"
    assert "Noi dung mot." in chu
    assert "var x=1" not in chu
    assert "a{}" not in chu
    assert ("hai", "/tiep") in lien_ket


def test_html_hong_khong_lam_sap():
    chu, _, _ = html_to_text("<p>chua dong the<div><span>")
    assert "chua dong the" in chu


def test_noi_dung_khong_phai_html_giu_nguyen():
    f = _fetcher({"https://a.example.com/x.json": (200, {"Content-Type": "application/json"}, b'{"a": 1}')})
    assert f.fetch("https://a.example.com/x.json").text == '{"a": 1}'


# ------------------------------------------------------------------- khác ---


def test_status_khac_200_la_loi_neu_nhin_thay_ma():
    f = _fetcher({"https://a.example.com/x": (404, HEAD_HTML, b"khong co")})
    with pytest.raises(FetchFailed, match="404"):
        f.fetch("https://a.example.com/x")


def test_tai_lieu_di_va_ve_qua_dict_khong_mat_gi():
    doc = WebDocument(
        url="https://a/b", requested="https://a/b", status=200, content_type="text/html",
        text="chu", title="tieu de", links=(("x", "/y"),), tier=CHINH_CHU,
        byte_count=3, sha256="ff", fetched_at="2026-08-30T00:00:00+00:00",
    )
    lai = WebDocument.from_dict(doc.to_dict())
    assert lai.url == doc.url and lai.tier == doc.tier and lai.links == doc.links
    assert lai.from_cache is True
