"""TC-66 — tìm kiếm web: trả địa chỉ, không trả kết luận.

Bất biến chính bài này canh: **tìm kiếm không được sinh ra nội dung.** Cái mô
hình hay máy tìm kiếm nói chỉ là địa chỉ; nội dung phải do bộ tải lấy về, qua
bộ kiểm nguồn. Trộn hai việc lại là cách một đoạn văn do mô hình bịa ra có
được một đường dẫn trông đàng hoàng.
"""

from __future__ import annotations

import json

import pytest

from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA
from eaa.web import CHINH_CHU, MO, WebFetcher
from eaa.websearch import (
    SEARCH_URL_ENV,
    ChainSearch,
    GeminiGroundedSearch,
    JsonEndpointSearch,
    NullSearch,
    ResearchResult,
    SearchError,
    SearchHit,
    SearchUnavailable,
    WebResearcher,
    build_query,
    default_backend,
    rank_hits,
)

CONG_KHAI = ["93.184.216.34"]
HEAD = {"Content-Type": "text/html; charset=utf-8"}
JSON_HEAD = {"Content-Type": "application/json"}


def _fetcher(trang, **kw):
    def gui(url, timeout, max_bytes):
        if url not in trang:
            raise OSError(f"không dựng trang cho {url}")
        status, headers, than = trang[url]
        return status, url, headers, than[: max_bytes + 1]

    kw.setdefault("resolver", lambda h: CONG_KHAI)
    kw.setdefault("max_retries", 0)
    return WebFetcher(transport=gui, **kw)


def _html(tieu_de: str, than: str) -> bytes:
    return f"<html><head><title>{tieu_de}</title></head><body><p>{than}</p></body></html>".encode()


# --------------------------------------------------------------- SearchHit ---


def test_hit_tu_phan_hang_theo_mien():
    assert SearchHit(url="https://www.microchip.com/a").tier == CHINH_CHU
    assert SearchHit(url="https://forum.example.com/a").tier == MO


def test_chinh_chu_luon_len_truoc_va_giu_thu_tu_trong_hang():
    ds = [
        SearchHit(url="https://blog.example.com/1", title="b1"),
        SearchHit(url="https://www.microchip.com/1", title="m1"),
        SearchHit(url="https://blog.example.com/2", title="b2"),
        SearchHit(url="https://www.st.com/1", title="s1"),
    ]
    assert [h.title for h in rank_hits(ds)] == ["m1", "s1", "b1", "b2"]


def test_ghep_truy_van_bo_trung_va_cat_ngan():
    assert build_query("timer1", "Timer1 mode", "  ") == "timer1 mode"
    assert len(build_query(" ".join(str(i) for i in range(40))).split()) == 16


# ------------------------------------------------------- JsonEndpointSearch ---


def test_endpoint_json_tra_ve_dia_chi():
    du_lieu = json.dumps({"results": [
        {"url": "https://www.microchip.com/a", "title": "A", "content": "noi dung a"},
        {"url": "https://blog.example.com/b", "title": "B"},
        {"url": "khong-phai-url", "title": "C"},
    ]}).encode()
    f = _fetcher({"https://tim.example.com/s?q=abc": (200, JSON_HEAD, du_lieu)})
    b = JsonEndpointSearch(url_template="https://tim.example.com/s?q={q}", fetcher=f)
    ket = b.search("abc")
    assert [h.url for h in ket] == ["https://www.microchip.com/a", "https://blog.example.com/b"]
    assert ket[0].snippet == "noi dung a"


def test_endpoint_json_nhan_nhieu_hinh_dang_json():
    for than in (
        {"items": [{"link": "https://a.example.com/x", "name": "X"}]},
        [{"href": "https://a.example.com/x", "title": "X"}],
        {"web": {"results": [{"url": "https://a.example.com/x"}]}},
    ):
        f = _fetcher({"https://t/s?q=q": (200, JSON_HEAD, json.dumps(than).encode())})
        b = JsonEndpointSearch(url_template="https://t/s?q={q}", fetcher=f)
        assert b.search("q")[0].url == "https://a.example.com/x"


def test_endpoint_tra_ve_html_thi_bao_loi_ro():
    f = _fetcher({"https://t/s?q=q": (200, HEAD, b"<html><body>ket qua</body></html>")})
    b = JsonEndpointSearch(url_template="https://t/s?q={q}", fetcher=f)
    with pytest.raises(SearchError, match="JSON"):
        b.search("q")


def test_endpoint_thieu_cho_giu_thi_khong_kha_dung(monkeypatch):
    monkeypatch.delenv(SEARCH_URL_ENV, raising=False)
    assert JsonEndpointSearch().available is False
    with pytest.raises(SearchUnavailable, match=SEARCH_URL_ENV):
        JsonEndpointSearch(url_template="https://t/s?q=co-dinh").search("q")


def test_endpoint_doc_duoc_tu_bien_moi_truong(monkeypatch):
    monkeypatch.setenv(SEARCH_URL_ENV, "https://t/s?q={q}")
    assert JsonEndpointSearch().available is True


# ------------------------------------------------------ GeminiGroundedSearch ---


class _LlmGia:
    def __init__(self, ket=None, loi=None):
        self.ket, self.loi, self.hoi = ket or [], loi, []

    def search_web(self, query, *, k=8):
        self.hoi.append(query)
        if self.loi:
            raise self.loi
        return self.ket


def test_grounding_tra_dia_chi_va_giu_doan_trich():
    llm = _LlmGia([{"url": "https://www.st.com/a", "title": "A", "snippet": "mo hinh noi"}])
    ket = GeminiGroundedSearch(llm=llm).search("cau hoi")
    assert ket[0].url == "https://www.st.com/a"
    assert ket[0].tier == CHINH_CHU
    assert llm.hoi == ["cau hoi"]


def test_mock_khong_tim_web_duoc_va_noi_ro_vi_sao():
    from eaa.llm.mock import MockLLM

    b = GeminiGroundedSearch(llm=MockLLM())
    assert b.available is False
    with pytest.raises(SearchUnavailable, match="MockLLM"):
        b.search("q")


def test_loi_nha_cung_cap_khong_lam_sap_luot_chay():
    b = GeminiGroundedSearch(llm=_LlmGia(loi=RuntimeError("429")))
    with pytest.raises(SearchError, match="429"):
        b.search("q")


# ------------------------------------------------------------- ChainSearch ---


def test_chuoi_dung_nguon_dau_tien_chay_duoc():
    hong = GeminiGroundedSearch(llm=_LlmGia(loi=RuntimeError("hong")))
    tot = GeminiGroundedSearch(llm=_LlmGia([{"url": "https://a.example.com/x"}]))
    assert ChainSearch(backends=(hong, tot)).search("q")[0].url == "https://a.example.com/x"


def test_khong_nguon_nao_thi_bao_loi_chu_khong_tra_rong():
    """Danh sách rỗng bị hiểu nhầm thành 'tìm rồi, không có gì'."""
    with pytest.raises(SearchUnavailable, match=SEARCH_URL_ENV):
        NullSearch().search("q")
    with pytest.raises(SearchUnavailable):
        ChainSearch(backends=()).search("q")


def test_nguon_mac_dinh_khong_cau_hinh_gi_thi_la_null(monkeypatch):
    monkeypatch.delenv(SEARCH_URL_ENV, raising=False)
    assert isinstance(default_backend(llm=None), NullSearch)


def test_nguon_mac_dinh_uu_tien_endpoint_hon_mo_hinh(monkeypatch):
    monkeypatch.setenv(SEARCH_URL_ENV, "https://t/s?q={q}")
    b = default_backend(llm=_LlmGia([{"url": "https://a/x"}]))
    assert isinstance(b, ChainSearch)
    assert b.backends[0].name == "endpoint"


# ------------------------------------------------------------ WebResearcher ---


def _researcher(hits, trang, **kw):
    class _B:
        name = "gia"
        available = True

        def search(self, query, *, k=8):
            return [SearchHit(url=u) for u in hits]

    return WebResearcher(backend=_B(), fetcher=_fetcher(trang), **kw)


def test_tra_cuu_tra_ve_trang_da_doc_khong_phai_tom_tat():
    r = _researcher(
        ["https://www.microchip.com/a", "https://blog.example.com/b"],
        {
            "https://www.microchip.com/a": (200, HEAD, _html("Chinh chu", "so lieu that")),
            "https://blog.example.com/b": (200, HEAD, _html("Blog", "y kien")),
        },
    )
    kq = r.research("cau hoi")
    assert len(kq.documents) == 2
    assert "so lieu that" in kq.documents[0].text
    assert kq.documents[0].tier == CHINH_CHU
    assert kq.confidence_level == SUY_RA


def test_khong_doc_duoc_trang_chinh_chu_nao_thi_ha_muc_tin_cay():
    r = _researcher(
        ["https://blog.example.com/b"],
        {"https://blog.example.com/b": (200, HEAD, _html("Blog", "y kien"))},
    )
    kq = r.research("cau hoi")
    assert kq.official == []
    assert kq.confidence_level == KHONG_KIEM_DUOC
    assert "MANH MỐI" in kq.render()


def test_che_do_chi_chinh_chu_bo_qua_trang_hang_mo():
    r = _researcher(
        ["https://blog.example.com/b", "https://www.microchip.com/a"],
        {"https://www.microchip.com/a": (200, HEAD, _html("Chinh chu", "so lieu"))},
        official_only=True,
    )
    kq = r.research("cau hoi")
    assert [d.url for d in kq.documents] == ["https://www.microchip.com/a"]


def test_tran_so_trang_doc_duoc_ton_trong():
    urls = [f"https://a{i}.example.com/x" for i in range(8)]
    r = _researcher(urls, {u: (200, HEAD, _html("T", "n")) for u in urls}, max_docs=3)
    assert len(r.research("q").documents) == 3


def test_trang_doc_hut_duoc_ghi_lai_chu_khong_nuot():
    r = _researcher(
        ["https://a.example.com/song", "https://a.example.com/chet"],
        {"https://a.example.com/song": (200, HEAD, _html("T", "n"))},
    )
    kq = r.research("q")
    assert len(kq.documents) == 1
    assert kq.failures and kq.failures[0][0] == "https://a.example.com/chet"
    assert "đọc hụt" in kq.render()


def test_ngu_canh_kem_dia_chi_ngay_canh_trich_doan():
    r = _researcher(
        ["https://www.microchip.com/a"],
        {"https://www.microchip.com/a": (200, HEAD, _html("T", "gia tri X la 42"))},
    )
    nc = r.research("q").context()
    assert "--- NGUỒN https://www.microchip.com/a" in nc
    assert "gia tri X la 42" in nc


def test_ngu_canh_danh_dau_trang_hang_mo_la_khong_dung_lam_nguon():
    r = _researcher(
        ["https://blog.example.com/b"],
        {"https://blog.example.com/b": (200, HEAD, _html("T", "y kien"))},
    )
    assert "KHÔNG được dùng làm nguồn tri thức" in r.research("q").context()


def test_ket_qua_rong_van_render_duoc():
    assert "Tra cứu" in ResearchResult(query="q").render()


# --------------------------------------- URL bọc qua trạm chuyển hướng ---


TRAM = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/ABC123"


def test_url_boc_duoc_phan_hang_theo_ten_mien_that():
    """Không có gợi ý này thì mọi kết quả rơi xuống hạng mở, kể cả datasheet gốc."""
    h = SearchHit(url=TRAM, title="microchip.com", domain_hint="microchip.com")
    assert h.wrapped is True
    assert h.tier == CHINH_CHU
    assert h.domain == "microchip.com"


def test_url_boc_khong_co_goi_y_thi_van_la_hang_mo():
    assert SearchHit(url=TRAM).tier == MO


def test_goi_y_khong_phai_ten_mien_thi_bo_qua():
    h = SearchHit(url=TRAM, domain_hint="Bai viet ve Timer1")
    assert h.tier == MO
    assert h.domain == "vertexaisearch.cloud.google.com"


def test_goi_y_khong_nang_hang_cho_url_that():
    """Chỉ URL bọc mới được dùng gợi ý — nếu không thì gợi ý là một đường vượt rào."""
    h = SearchHit(url="https://blog.example.com/x", domain_hint="microchip.com")
    assert h.tier == MO


def test_grounding_truyen_ten_mien_that_sang_lam_goi_y():
    llm = _LlmGia([{"url": TRAM, "title": "www.microchip.com", "snippet": ""}])
    assert GeminiGroundedSearch(llm=llm).search("q")[0].tier == CHINH_CHU


def test_render_noi_ro_day_la_url_boc():
    assert "qua trạm chuyển hướng" in SearchHit(url=TRAM, domain_hint="microchip.com").render()


# ------------------------------------------------- buộc truy vấn về đúng nơi ---


def test_buoc_truy_van_ve_mot_ten_mien():
    from eaa.websearch import restrict_to_sites

    assert restrict_to_sites("timer1 ctc", ["microchip.com"]) == "timer1 ctc site:microchip.com"


def test_buoc_truy_van_ve_nhieu_ten_mien():
    from eaa.websearch import restrict_to_sites

    assert restrict_to_sites("q", ["a.com", "b.com"]) == "q (site:a.com OR site:b.com)"


def test_khong_neu_ten_mien_thi_giu_nguyen_truy_van():
    from eaa.websearch import restrict_to_sites

    assert restrict_to_sites("q", []) == "q"
    assert restrict_to_sites("q", ["", "  "]) == "q"


def test_researcher_chuyen_rang_buoc_ten_mien_xuong_nguon_tim():
    da_hoi = []

    class _B:
        name, available = "gia", True

        def search(self, query, *, k=8):
            da_hoi.append(query)
            return []

    WebResearcher(backend=_B()).research("timer1", sites=["microchip.com"])
    assert da_hoi == ["timer1 site:microchip.com"]


# ═══════════════ nối web vào chế độ tìm công cụ (TC-66c) ═══════════════


class _LlmDeXuat:
    provider, model = "gia", "mo-hinh-gia"

    def __init__(self):
        self.prompts = []

    def count_tokens(self, text):
        return len(text) // 4

    def complete(self, prompt):
        import json as _j

        self.prompts.append(prompt)
        return "```json\n" + _j.dumps({
            "name": "cppcheck", "description": "phân tích tĩnh",
            "min_version": "2.10", "check": ["cppcheck", "--version"],
            "install": {"macos": ["brew", "install", "cppcheck"]},
            "rationale": "cần cho cổng static", "homepage": "https://cppcheck.sourceforge.io",
            "smoke": ["cppcheck", "--version"], "smoke_expect": "Cppcheck",
        }) + "\n```"


def _yeu_cau():
    from eaa.toolsearch import ToolRequirement

    return ToolRequirement(program="cppcheck", capabilities=("static",), pack="avr")


def test_de_xuat_cong_cu_doc_trang_cai_that_va_ghi_lai_nguon():
    from eaa.toolsearch import LlmToolResearcher

    trang = "https://cppcheck.sourceforge.io/install"
    r = _researcher([trang], {trang: (200, HEAD, _html("Cai dat", "brew install cppcheck"))})
    llm = _LlmDeXuat()

    dx = LlmToolResearcher(llm=llm, researcher=r).propose(_yeu_cau(), os_key="macos")

    assert dx.evidence == (trang,)
    assert "brew install cppcheck" in llm.prompts[0].full_text()
    assert trang in dx.render()


def test_khong_doc_duoc_trang_thi_van_de_xuat_nhung_noi_ro_la_tri_nho():
    from eaa.toolsearch import LlmToolResearcher

    dx = LlmToolResearcher(llm=_LlmDeXuat(), researcher=None).propose(_yeu_cau())
    assert dx.evidence == ()
    assert "TRÍ NHỚ" in dx.render()


def test_mang_chap_khong_lam_che_do_tim_cong_cu_ngung_hoat_dong():
    """Mạng hỏng đúng lúc người ta cần chế độ này nhất."""
    from eaa.toolsearch import LlmToolResearcher
    from eaa.websearch import SearchError

    class _Hong:
        def research(self, *a, **kw):
            raise SearchError("mạng chập")

    dx = LlmToolResearcher(llm=_LlmDeXuat(), researcher=_Hong()).propose(_yeu_cau())
    assert dx.name == "cppcheck" and dx.evidence == ()


def test_nguon_di_qua_luu_tru_khong_mat():
    from eaa.toolsearch import ToolProposal

    dx = ToolProposal(name="x", description="d", min_version="1", check=("x",),
                      install={"macos": ("brew", "install", "x")}, rationale="r",
                      evidence=("https://a/b",))
    assert ToolProposal.from_dict(dx.to_dict()).evidence == ("https://a/b",)
    assert dx.to_manifest_entry()["evidence"] == ["https://a/b"]
