"""TC-48 — thang tìm kiếm bổ sung, bước 3 của quy trình P7.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-48a | Bậc 1 lục lại tài liệu đã nạp | tìm cả chunk CHƯA DUYỆT — thứ cần thường đã nằm trong kho |
| TC-48b | Bậc 2 hỏi ĐÍCH DANH | nêu tên thanh ghi, không hỏi chung chung; không có ai để hỏi thì không tự trả lời hộ |
| TC-48c | Bậc 3 bắt buộc kèm nguồn hợp lệ | thiếu nguồn, hoặc nguồn ngoài miền cho phép → bỏ kết quả |
| TC-48d | Ngân sách vòng tìm | chỉ trừ lượt khi tìm KHÔNG ra; hết lượt thì chuyển người |
| TC-48e | Thứ tìm được là ĐỀ XUẤT | mọi bậc đều ghi chunk ở trạng thái chờ G2, không vào kho ngay |

Vì sao nhóm này tồn tại: RIC đã biết nói "thiếu thanh ghi X" từ Sprint 3, và
Readiness Check đã biết chặn. Nhưng giữa hai việc ấy Agent KHÔNG làm gì —
``search_rounds`` và ``MAX_SEARCH_ROUNDS`` có sẵn trong mã mà không ai tăng bộ
đếm, vì không ai đi tìm. Người dùng phải tự đoán ra rằng mình cần nạp thêm tài
liệu, và tự đoán xem cần nạp trang nào.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from eaa.gapsearch import (
    EXHAUSTED,
    FOUND,
    NOT_FOUND,
    SKIPPED,
    GapResolver,
    GapSearchError,
    SearchLedger,
)
from eaa.readiness import MAX_SEARCH_ROUNDS, ItemStatus, Ric, RicItem

REPO = Path(__file__).resolve().parent.parent


CHUNK = """\
    ---
    id: {ma}
    device: atmega328p
    peripheral: twi
    registers: [{thanh_ghi}]
    topic: Thanh ghi tốc độ bit
    source: Tài liệu nhà sản xuất, tr.222
    source_hash: sha256:{bam}
    status: {trang_thai}
    ---

    ## Bảng thanh ghi

    | Thanh ghi | Bit | Giá trị |
    |---|---|---|
    | {thanh_ghi} | 7:0 | 12 |
"""


class _HoSoGia:
    """Hồ sơ phần cứng tối thiểu — chỉ hai thứ GapResolver hỏi tới."""

    mcu = {"part": "atmega328p"}
    peripherals = [{"id": "twi", "configured_by": ["TWBR", "TWCR"]}]
    pin_map: dict = {}
    components: list = []


class _KbGia:
    def __init__(self, thu_muc: Path) -> None:
        from eaa.kb import DatasheetStore

        self.datasheets = DatasheetStore(thu_muc)
        self.hardware = _HoSoGia()


def _viet_chunk(thu_muc: Path, ma: str, thanh_ghi: str, trang_thai: str) -> None:
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / f"{ma}.md").write_text(
        textwrap.dedent(CHUNK).format(
            ma=ma, thanh_ghi=thanh_ghi, trang_thai=trang_thai, bam="0" * 64
        ),
        encoding="utf-8",
    )


def _ric(*khoa: str) -> Ric:
    return Ric(
        module_id="drv_bus",
        items=[
            RicItem(key=k, kind="register", status=ItemStatus.MISSING, detail="chưa có nguồn")
            for k in khoa
        ],
    )


@pytest.fixture()
def moi_truong(tmp_path: Path) -> tuple[_KbGia, SearchLedger]:
    return _KbGia(tmp_path / "datasheets"), SearchLedger(tmp_path / "gap.json")


def _bac(bao_cao, khoa: str, so: int):
    return next(r for r in bao_cao.results if r.item_key == khoa and r.tier == so)


# --------------------------------------------------------------------------
# TC-48a — bậc 1: lục lại tài liệu đã nạp
# --------------------------------------------------------------------------


def test_bac1_tim_thay_chunk_chua_duyet(moi_truong, tmp_path: Path) -> None:
    """Thứ cần tìm rất thường đã nằm trong kho, chỉ là chưa ai duyệt tại G2."""
    kb, so = moi_truong
    _viet_chunk(tmp_path / "datasheets", "ds-021", "TWBR", "proposed")

    bao_cao = GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))
    b1 = _bac(bao_cao, "TWBR", 1)

    assert b1.outcome == FOUND
    assert "ds-021" in b1.detail
    assert "duyệt tại G2 là đủ" in b1.detail


def test_bac1_khong_tinh_chunk_da_duyet(moi_truong, tmp_path: Path) -> None:
    """Chunk đã duyệt mà mục vẫn THIẾU nghĩa là nó không nói về mục này."""
    kb, so = moi_truong
    _viet_chunk(tmp_path / "datasheets", "ds-030", "TWBR", "approved")

    b1 = _bac(GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR")), "TWBR", 1)
    assert b1.outcome == NOT_FOUND


def test_bac1_tim_ca_trong_than_chunk(moi_truong, tmp_path: Path) -> None:
    """Thanh ghi có thể nằm trong bảng mà không có trong danh sách registers."""
    kb, so = moi_truong
    _viet_chunk(tmp_path / "datasheets", "ds-040", "TWCR", "proposed")

    b1 = _bac(GapResolver(kb=kb, ledger=so).resolve(_ric("TWCR")), "TWCR", 1)
    assert b1.outcome == FOUND


def test_tim_thay_o_bac_1_thi_khong_leo_tiep(moi_truong, tmp_path: Path) -> None:
    kb, so = moi_truong
    _viet_chunk(tmp_path / "datasheets", "ds-021", "TWBR", "proposed")

    bao_cao = GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))
    assert [r.tier for r in bao_cao.results] == [1], "bậc rẻ tìm được thì dừng"


# --------------------------------------------------------------------------
# TC-48b — bậc 2: hỏi đích danh
# --------------------------------------------------------------------------


def test_bac2_hoi_dich_danh_ten_thanh_ghi(moi_truong) -> None:
    """Câu hỏi mơ hồ đẩy việc chẩn đoán ngược lại cho người."""
    kb, so = moi_truong
    bao_cao = GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))

    (cau_hoi,) = bao_cao.questions
    assert "TWBR" in cau_hoi
    assert "thanh ghi" in cau_hoi


def test_khong_co_ai_de_hoi_thi_khong_tu_tra_loi_ho(moi_truong) -> None:
    kb, so = moi_truong
    bao_cao = GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))

    assert not bao_cao.proposals, "không được bịa câu trả lời thay người"
    assert bao_cao.questions


def test_nguoi_tra_loi_thi_thanh_de_xuat(moi_truong, tmp_path: Path) -> None:
    kb, so = moi_truong
    resolver = GapResolver(
        kb=kb,
        ledger=so,
        datasheets_dir=tmp_path / "datasheets",
        ask=lambda _: "| TWBR | 7:0 | 12 |",
    )
    bao_cao = resolver.resolve(_ric("TWBR"))

    assert len(bao_cao.proposals) == 1
    de_xuat = bao_cao.proposals[0]
    assert "người dùng cung cấp" in de_xuat.source
    assert de_xuat.peripheral == "twi", "tra ngoại vi từ hồ sơ phần cứng"


def test_nguoi_khong_tra_loi_thi_di_tiep(moi_truong) -> None:
    kb, so = moi_truong
    bao_cao = GapResolver(kb=kb, ledger=so, ask=lambda _: "  ").resolve(_ric("TWBR"))

    assert _bac(bao_cao, "TWBR", 2).outcome == NOT_FOUND
    assert _bac(bao_cao, "TWBR", 3), "phải leo tiếp lên bậc 3"


# --------------------------------------------------------------------------
# TC-48c — bậc 3: bắt buộc nguồn hợp lệ
# --------------------------------------------------------------------------


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        #: Giữ lại prompt để kiểm được rằng bậc 3 đưa NỘI DUNG TRANG cho mô
        #: hình, chứ không chỉ đưa câu hỏi rồi nhận lại thứ mô hình nhớ được.
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def _json(**kw) -> str:
    import json

    return "```json\n" + json.dumps({"found": True, **kw}) + "\n```"


def test_bac3_tat_mac_dinh(moi_truong) -> None:
    """Bậc 3 tốn lời gọi mô hình và cần mạng — không bật ngầm."""
    kb, so = moi_truong
    bao_cao = GapResolver(kb=kb, ledger=so, llm=_LlmGia("")).resolve(_ric("TWBR"))
    assert _bac(bao_cao, "TWBR", 3).outcome == SKIPPED


class _TraGia:
    """Bộ tra web giả: trả về đúng những trang bài test dựng sẵn.

    Bậc 3 giờ ĐỌC trang thật rồi mới trích. Kiểm nó bằng mạng thật thì bài test
    hỏng theo nhịp của máy chủ người khác, nên bộ tra được tiêm vào.
    """

    def __init__(self, *trang, hut=()):
        from eaa.web import CHINH_CHU, MO, WebDocument

        self.documents = tuple(
            WebDocument(url=u, requested=u, status=200, content_type="text/html",
                        text=t, title="tài liệu", tier=CHINH_CHU if chinh_chu else MO,
                        fetched_at="2026-08-30T00:00:00+00:00")
            for u, t, chinh_chu in trang
        )
        self.hut = tuple(hut)
        self.da_tim = []

    def research(self, query, **kw):
        from eaa.websearch import ResearchResult

        self.da_tim.append(query)
        return ResearchResult(query=query, hits=(), documents=self.documents,
                              failures=self.hut)


TRANG_GOC = "https://ww1.microchip.com/downloads/tai-lieu.html"


def test_bac3_trich_tu_trang_da_tai_thi_thanh_de_xuat(moi_truong, tmp_path: Path) -> None:
    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "TWBR la thanh ghi toc do bit, 8 bit", True))
    llm = _LlmGia(_json(source=TRANG_GOC, topic="Tốc độ bit",
                        registers=["TWBR"], body="| TWBR | 7:0 | 12 |"))

    bao_cao = GapResolver(
        kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra,
        datasheets_dir=tmp_path / "datasheets",
    ).resolve(_ric("TWBR"))

    assert len(bao_cao.proposals) == 1
    assert bao_cao.proposals[0].source == TRANG_GOC


def test_bac3_dua_noi_dung_that_cho_mo_hinh_khong_hoi_tri_nho(moi_truong) -> None:
    """Cả điểm của bậc 3 mới: mô hình TRÍCH từ trang, không NHỚ lại."""
    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "noi dung that cua trang", True))
    llm = _LlmGia(_json(source=TRANG_GOC, body="x"))

    GapResolver(kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra).resolve(_ric("TWBR"))

    assert "noi dung that cua trang" in llm.prompts[0].full_text()


def test_bac3_nguon_ngoai_tap_trang_da_tai_thi_bo(moi_truong) -> None:
    """Cái chặn quan trọng nhất: nêu URL lạ nghĩa là vừa quay về trả lời từ trí nhớ."""
    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "noi dung", True))
    llm = _LlmGia(_json(source="https://www.microchip.com/mot-trang-khac", body="x"))

    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == NOT_FOUND
    assert "không nằm trong" in b3.detail


def test_bac3_khong_nguon_thi_bo(moi_truong) -> None:
    """Một câu trả lời trôi chảy trông y hệt một trích đoạn tra được."""
    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "noi dung", True))
    llm = _LlmGia(_json(source="", body="| TWBR | 7:0 | 12 |"))

    bao_cao = GapResolver(kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra).resolve(_ric("TWBR"))
    b3 = _bac(bao_cao, "TWBR", 3)

    assert b3.outcome == NOT_FOUND
    assert "không nằm trong" in b3.detail
    assert not bao_cao.proposals


def test_bac3_trang_hang_mo_khong_duoc_dung_lam_nguon_tri_thuc(moi_truong) -> None:
    kb, so = moi_truong
    tra = _TraGia(("https://dien-dan-linh-tinh.net/twbr", "co ai biet khong", False))
    llm = _LlmGia(_json(source="https://dien-dan-linh-tinh.net/twbr", body="x"))

    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == NOT_FOUND
    assert "không trang chính chủ nào đọc được" in b3.detail


def test_bac3_doc_hut_duoc_ke_lai(moi_truong) -> None:
    kb, so = moi_truong
    tra = _TraGia(hut=(("https://www.microchip.com/x", "HTTP 404"),))
    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=_LlmGia(""), allow_web=True, researcher=tra).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == NOT_FOUND
    assert "1 trang đọc hụt" in b3.detail


def test_bac3_mo_hinh_noi_khong_chac_thi_ton_trong(moi_truong) -> None:
    """Không chắc mà vẫn nhận là mở cửa cho giá trị bịa vào kho tri thức."""
    import json as _json

    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "noi dung", True))
    llm = _LlmGia("```json\n" + _json.dumps({"found": False}) + "\n```")

    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=llm, allow_web=True, researcher=tra).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == NOT_FOUND
    assert "không trang nào nói điều đang hỏi" in b3.detail


def test_bac3_khong_co_nguon_tim_kiem_thi_noi_ro_cach_bat(moi_truong, monkeypatch) -> None:
    from eaa.websearch import SEARCH_URL_ENV

    monkeypatch.delenv(SEARCH_URL_ENV, raising=False)
    kb, so = moi_truong
    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=_LlmGia(""), allow_web=True).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == NOT_FOUND
    assert SEARCH_URL_ENV in b3.detail


def test_bac3_cau_tim_hep_lai_theo_goi_y_nha_san_xuat(moi_truong) -> None:
    kb, so = moi_truong
    tra = _TraGia((TRANG_GOC, "noi dung", True))
    GapResolver(kb=kb, ledger=so, llm=_LlmGia(_json(source=TRANG_GOC, body="x")),
                allow_web=True, researcher=tra, vendor_hint="ho-chip-x").resolve(_ric("TWBR"))
    assert "ho-chip-x" in tra.da_tim[0]
    assert "TWBR" in tra.da_tim[0]


def test_bac3_khong_co_mo_hinh_thi_bao_ro(moi_truong) -> None:
    kb, so = moi_truong
    b3 = _bac(
        GapResolver(kb=kb, ledger=so, llm=None, allow_web=True).resolve(_ric("TWBR")),
        "TWBR", 3,
    )
    assert b3.outcome == SKIPPED
    assert "mô hình nền" in b3.detail


# --------------------------------------------------------------------------
# TC-48d — ngân sách vòng tìm
# --------------------------------------------------------------------------


def test_tim_khong_ra_thi_tru_luot(moi_truong) -> None:
    kb, so = moi_truong
    GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))
    assert so.rounds("drv_bus", "TWBR") == 1


def test_tim_THAY_thi_KHONG_tru_luot(moi_truong, tmp_path: Path) -> None:
    """Ngân sách sinh ra để chặn việc tìm mãi không thấy, không để phạt việc tìm thấy.

    Lỗi thật khi chạy lần đầu: trừ lượt cả khi thành công, nên một mục tra được
    ngay từ bậc 1 vẫn cạn lượt sau hai lần gõ lệnh.
    """
    kb, so = moi_truong
    _viet_chunk(tmp_path / "datasheets", "ds-021", "TWBR", "proposed")

    for _ in range(5):
        GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))
    assert so.rounds("drv_bus", "TWBR") == 0


def test_het_luot_thi_chuyen_nguoi(moi_truong) -> None:
    kb, so = moi_truong
    r = GapResolver(kb=kb, ledger=so)

    for _ in range(MAX_SEARCH_ROUNDS):
        r.resolve(_ric("TWBR"))
    bao_cao = r.resolve(_ric("TWBR"))

    assert bao_cao.handed_off == ["TWBR"]
    assert _bac(bao_cao, "TWBR", 3).outcome == EXHAUSTED
    assert "KHÔNG đoán giá trị" in bao_cao.render()


def test_so_dem_song_qua_nhieu_phien(moi_truong, tmp_path: Path) -> None:
    """Đếm trong bộ nhớ thì trần MAX_SEARCH_ROUNDS không bao giờ chạm tới."""
    kb, so = moi_truong
    GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))

    so_khac = SearchLedger(tmp_path / "gap.json")
    assert so_khac.rounds("drv_bus", "TWBR") == 1


def test_moi_module_dem_rieng(moi_truong) -> None:
    kb, so = moi_truong
    GapResolver(kb=kb, ledger=so).resolve(_ric("TWBR"))

    assert so.rounds("drv_bus", "TWBR") == 1
    assert so.rounds("module_khac", "TWBR") == 0


def test_so_dem_hong_thi_bao_ro(tmp_path: Path) -> None:
    duong_dan = tmp_path / "gap.json"
    duong_dan.write_text("khong-phai-json", encoding="utf-8")
    with pytest.raises(GapSearchError, match="hỏng"):
        SearchLedger(duong_dan).rounds("m", "X")


def test_muc_khong_thieu_thi_khong_tim(moi_truong) -> None:
    kb, so = moi_truong
    ric = Ric(
        module_id="drv_bus",
        items=[RicItem(key="TWBR", kind="register", status=ItemStatus.PRESENT)],
    )
    bao_cao = GapResolver(kb=kb, ledger=so).resolve(ric)

    assert bao_cao.results == []
    assert so.rounds("drv_bus", "TWBR") == 0


# --------------------------------------------------------------------------
# TC-48e — thứ tìm được là đề xuất
# --------------------------------------------------------------------------


def test_de_xuat_ghi_ra_o_trang_thai_cho_duyet(moi_truong, tmp_path: Path) -> None:
    kb, so = moi_truong
    thu_muc = tmp_path / "datasheets"
    GapResolver(
        kb=kb, ledger=so, datasheets_dir=thu_muc, ask=lambda _: "| TWBR | 7:0 | 12 |"
    ).resolve(_ric("TWBR"))

    tep = list(thu_muc.glob("gs-*.md"))
    assert len(tep) == 1
    noi_dung = tep[0].read_text(encoding="utf-8")
    assert "status: proposed" in noi_dung
    # YAML ngắt dòng phần ghi chú, nên kiểm cụm không bị ngắt.
    assert "Là ĐỀ XUẤT" in noi_dung
    assert "duyệt tại G2" in noi_dung


def test_de_xuat_khong_vao_kho_hoat_dong_ngay(moi_truong, tmp_path: Path) -> None:
    """Chunk đề xuất không được truy xuất cho tới khi người duyệt tại G2."""
    kb, so = moi_truong
    thu_muc = tmp_path / "datasheets"
    GapResolver(
        kb=kb, ledger=so, datasheets_dir=thu_muc, ask=lambda _: "| TWBR | 7:0 | 12 |"
    ).resolve(_ric("TWBR"))

    kb.datasheets.reload()
    assert not [c for c in kb.datasheets.active() if c.id.startswith("gs-")]
    assert [c for c in kb.datasheets.all() if c.id.startswith("gs-")]


def test_bao_cao_nhac_phai_duyet_G2(moi_truong, tmp_path: Path) -> None:
    kb, so = moi_truong
    bao_cao = GapResolver(
        kb=kb,
        ledger=so,
        datasheets_dir=tmp_path / "datasheets",
        ask=lambda _: "| TWBR | 7:0 | 12 |",
    ).resolve(_ric("TWBR"))

    van_ban = bao_cao.render()
    assert "chờ duyệt tại G2" in van_ban
    assert "eaa gate approve G2" in van_ban


# --------------------------------------------------------------------------
# Nối vào phần còn lại
# --------------------------------------------------------------------------


def test_thong_bao_thieu_tri_thuc_chi_dung_lenh() -> None:
    """Thông báo phải là LỆNH GÕ ĐƯỢC, không phải mô tả tình trạng."""
    from eaa.readiness import NotReady, ReadinessChecker

    class _GraphGia:
        class _G:
            @staticmethod
            def has_node(_):
                return True

        graph = _G()

        @staticmethod
        def registers_for(_):
            return ["TWBR"]

        @staticmethod
        def pins_for(_):
            return []

        @staticmethod
        def resources_of(_):
            return []

    class _KbTrong:
        class _DS:
            @staticmethod
            def by_register(_):
                return []

            @staticmethod
            def active():
                return []

            @staticmethod
            def all():
                return []

        datasheets = _DS()
        hardware = _HoSoGia()

    with pytest.raises(NotReady) as loi:
        ReadinessChecker(kb=_KbTrong(), graph=_GraphGia()).check("drv_bus")

    assert "eaa resolve drv_bus" in str(loi.value)
    assert "--ask" in str(loi.value)


def test_lenh_resolve_co_du_co() -> None:
    import argparse

    from eaa.cli import build_parser

    for hanh_dong in build_parser()._actions:
        if isinstance(hanh_dong, argparse._SubParsersAction):
            resolve = hanh_dong.choices["resolve"]
            break
    co = {c for a in resolve._actions for c in a.option_strings}
    assert {"--ask", "--web"} <= co
