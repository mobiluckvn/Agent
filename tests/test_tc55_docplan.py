"""TC-55 — tài liệu đích danh, trang đích danh, errata theo rev (N-004, N-030, N-037).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-55a | Danh sách tài liệu suy từ hồ sơ, không hỏi lại thứ máy tự biết | N-004 |
| TC-55b | Rev silicon là câu PHẢI HỎI người | không hồ sơ nào trả lời thay được |
| TC-55c | Nguồn ngoài danh sách cho phép bị loại | ảo giác CÓ NGUỒN, FR-GAP-02 |
| TC-55d | Chỉ xin phần tài liệu còn THIẾU trích đoạn | N-030 — bắc cầu trên đồ thị |
| TC-55e | Chunk đã bị supersede coi như chưa có | đó đúng là tình trạng của nó |
| TC-55f | "Chưa tra errata" khác hẳn "chip sạch" | N-037, cùng nguyên tắc với N-075 |
| TC-55g | `revisions` trống nghĩa là MỌI rev | không biến chỗ thiếu tin thành lời bảo đảm |
| TC-55h | Module chạm lỗi đã công bố được gọi tên | đối chiếu cả ngoại vi lẫn thanh ghi |

TC-55f là phần đáng nói nhất. Một danh sách errata trống trông y hệt một con
chip sạch, và cám dỗ khi cài đặt là để trống rồi đi tiếp. Mã đúng theo
datasheet vẫn chạy sai nếu chip có lỗi đã công bố — và đó là loại lỗi mà mọi
cổng kiểm chứng của hệ thống này đều cho qua, vì mã thật sự đúng với thứ nó
được bảo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.docplan import (
    ERRATA_FILE,
    REV_CHUA_BIET,
    DocKind,
    DocPlanError,
    DocumentNeed,
    DocumentPlan,
    ErrataAnalysis,
    ErrataItem,
    LlmDocLookup,
    plan_documents,
    plan_pages,
)
from eaa.ingest import SourceRejected

REPO = Path(__file__).resolve().parent.parent


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def _json(du_lieu) -> _LlmGia:
    return _LlmGia("```json\n" + json.dumps(du_lieu, ensure_ascii=False) + "\n```")


class _HoSoGia:
    """Hồ sơ tối thiểu, không mang tên một họ chip có thật."""

    raw = {"board": "bo-thu-nghiem", "project": "du-an-gia"}
    mcu = {"part": "chip-gia-1"}
    peripherals = [
        {"id": "bus_a", "configured_by": ["REG_A1", "REG_A2"]},
        {"id": "timer_b", "configured_by": ["REG_B1"]},
    ]
    components = [
        {"id": "cam_bien", "part": "linh-kien-1", "kind": "sensor"},
        {"id": "chap_hanh_trai", "part": "linh-kien-2", "kind": "actuator"},
        {"id": "chap_hanh_phai", "part": "linh-kien-2", "kind": "actuator"},
    ]

    def registers_of(self, peripheral_id: str):
        for p in self.peripherals:
            if p["id"] == peripheral_id:
                return tuple(p["configured_by"])
        return ()


class _Chunk:
    def __init__(self, *registers: str) -> None:
        self.registers = registers


class _KhoTrichDoan:
    def __init__(self, *chunks: _Chunk) -> None:
        self._chunks = chunks

    def active(self):
        return list(self._chunks)


class _Module:
    def __init__(self, ma: str, *uses: str) -> None:
        self.id = ma
        self.uses = uses


# --------------------------------------------------------------------------
# TC-55a, TC-55b — tài liệu cần
# --------------------------------------------------------------------------


def test_danh_sach_suy_tu_ho_so_khong_hoi_lai_thu_may_tu_biet() -> None:
    ke_hoach = plan_documents(_HoSoGia())
    khoa = {n.key for n in ke_hoach.needs}

    assert f"{DocKind.DATASHEET}:chip-gia-1" in khoa
    assert f"{DocKind.ERRATA}:chip-gia-1" in khoa
    assert f"{DocKind.SCHEMATIC}:bo-thu-nghiem" in khoa
    assert f"{DocKind.DATASHEET}:linh-kien-1" in khoa


def test_hai_linh_kien_cung_ma_chi_can_mot_datasheet() -> None:
    """Liệt kê hai lần chỉ làm danh sách dài ra mà không thêm việc phải làm."""
    ke_hoach = plan_documents(_HoSoGia())
    muc = [n for n in ke_hoach.needs if n.subject == "linh-kien-2"]

    assert len(muc) == 1
    assert "chap_hanh_trai" in muc[0].why and "chap_hanh_phai" in muc[0].why


def test_tai_lieu_tham_chieu_chi_them_khi_du_an_khai() -> None:
    """Engine không đoán họ chip nào tách tài liệu tham chiếu, họ nào không."""
    assert not any(
        n.kind == DocKind.REFERENCE_MANUAL for n in plan_documents(_HoSoGia()).needs
    )

    class _CoTaiLieuThamChieu(_HoSoGia):
        mcu = {"part": "chip-gia-1", "reference_manual": True}

    assert any(
        n.kind == DocKind.REFERENCE_MANUAL
        for n in plan_documents(_CoTaiLieuThamChieu()).needs
    )


def test_moi_tai_lieu_phai_neu_vi_sao_can() -> None:
    with pytest.raises(DocPlanError, match="vì sao cần"):
        DocumentNeed(DocKind.DATASHEET, "chip", "")


def test_khong_khai_ma_chip_thi_dung_lai() -> None:
    class _Trong:
        raw: dict = {}
        mcu: dict = {}
        peripherals: list = []
        components: list = []

    with pytest.raises(DocPlanError, match="mcu.part"):
        plan_documents(_Trong())


def test_rev_silicon_la_cau_phai_hoi_nguoi() -> None:
    ke_hoach = plan_documents(_HoSoGia())
    hoi = ke_hoach.questions()

    assert any("Rev silicon" in h for h in hoi)
    assert any("in trên mặt chip" in h for h in hoi)


def test_biet_rev_thi_khong_hoi_nua() -> None:
    ke_hoach = plan_documents(_HoSoGia(), silicon_rev="D")
    assert not any("Rev silicon" in h for h in ke_hoach.questions())


def test_tai_lieu_nguoi_da_nop_duoc_danh_dau_la_da_co(tmp_path: Path) -> None:
    from eaa.ingest import SourceRegistry

    kho = SourceRegistry(tmp_path / "sources.jsonl")
    kho.register(
        origin=str(tmp_path / "chip-gia-1.pdf"), kind="pdf", content_hash="sha256:x"
    )
    ke_hoach = plan_documents(_HoSoGia()).match_provided(kho)

    da_co = [n for n in ke_hoach.needs if n.satisfied]
    assert any(n.subject == "chip-gia-1" for n in da_co)
    assert len(ke_hoach.missing) < len(ke_hoach.needs)


# --------------------------------------------------------------------------
# TC-55c — nguồn phải trong danh sách cho phép
# --------------------------------------------------------------------------


def test_nguon_ngoai_danh_sach_bi_loai() -> None:
    ke_hoach = plan_documents(_HoSoGia())
    khoa = ke_hoach.needs[0].key
    with pytest.raises(SourceRejected):
        ke_hoach.with_sources({khoa: "https://dien-dan-nao-do.example/tai-lieu.pdf"})


def test_nguon_hop_le_duoc_gan_vao_muc() -> None:
    ke_hoach = plan_documents(_HoSoGia())
    khoa = ke_hoach.needs[0].key
    moi = ke_hoach.with_sources({khoa: "https://www.microchip.com/tai-lieu.pdf"})

    assert moi.needs[0].official_source.endswith("tai-lieu.pdf")


def test_mo_hinh_tra_ve_nguon_ban_thi_bo_muc_ay_chu_khong_hong_ca_luot() -> None:
    """Một đường dẫn hỏng không được làm mất phần tra đúng.

    Mục bị loại vẫn hiện ra ở danh sách 'còn thiếu nguồn', nên không có kết
    cục im lặng — chỉ có kết cục cục bộ.
    """
    ke_hoach = plan_documents(_HoSoGia())
    tot, xau = ke_hoach.needs[0].key, ke_hoach.needs[1].key
    llm = _json(
        {
            "sources": [
                {"key": tot, "url": "https://www.microchip.com/a.pdf"},
                {"key": xau, "url": "https://blog-nao-do.example/b.pdf"},
            ]
        }
    )
    nguon = LlmDocLookup(llm=llm).sources(ke_hoach)

    assert tot in nguon
    assert xau not in nguon


def test_mo_hinh_bia_them_khoa_khong_co_trong_danh_sach_thi_bo() -> None:
    ke_hoach = plan_documents(_HoSoGia())
    llm = _json({"sources": [{"key": "datasheet:khong-he-yeu-cau", "url": "https://st.com/x"}]})
    assert LlmDocLookup(llm=llm).sources(ke_hoach) == {}


# --------------------------------------------------------------------------
# TC-55d, TC-55e — trang cần trích
# --------------------------------------------------------------------------


def test_chi_xin_phan_con_thieu_trich_doan() -> None:
    kho = _KhoTrichDoan(_Chunk("REG_A1", "REG_A2"))
    ke_hoach = plan_pages(hardware=_HoSoGia(), datasheets=kho)

    xin = {r.peripheral for r in ke_hoach.requests}
    assert xin == {"timer_b"}, "ngoại vi đã đủ trích đoạn thì không xin lại"
    assert ke_hoach.registers_needed == ("REG_B1",)


def test_xin_mot_phan_thi_noi_ro_da_co_bao_nhieu() -> None:
    kho = _KhoTrichDoan(_Chunk("REG_A1"))
    ke_hoach = plan_pages(hardware=_HoSoGia(), datasheets=kho)
    muc = next(r for r in ke_hoach.requests if r.peripheral == "bus_a")

    assert muc.registers == ("REG_A2",)
    assert "1/2 thanh ghi" in muc.why


def test_chua_co_trich_doan_nao_thi_xin_het() -> None:
    ke_hoach = plan_pages(hardware=_HoSoGia(), datasheets=None)
    assert len(ke_hoach.requests) == 2


def test_du_trich_doan_thi_danh_sach_rong_va_noi_ro() -> None:
    kho = _KhoTrichDoan(_Chunk("REG_A1", "REG_A2", "REG_B1"))
    ke_hoach = plan_pages(hardware=_HoSoGia(), datasheets=kho)

    assert ke_hoach.requests == ()
    assert "đã có trích đoạn đang hiệu lực" in ke_hoach.render()


def test_chi_tinh_trich_doan_dang_hieu_luc() -> None:
    """Chunk đã bị supersede thì thanh ghi ấy coi như chưa có — đúng tình trạng của nó."""

    class _KhoCoBanBiThayThe:
        def active(self):
            return [_Chunk("REG_A1")]  # REG_A2 từng có nhưng đã bị supersede

    ke_hoach = plan_pages(hardware=_HoSoGia(), datasheets=_KhoCoBanBiThayThe())
    assert "REG_A2" in ke_hoach.registers_needed


def test_khoanh_theo_module_thi_chi_xet_ngoai_vi_module_ay_dung() -> None:
    ke_hoach = plan_pages(
        hardware=_HoSoGia(), datasheets=None, module_id="drv_a", uses=("bus_a",)
    )
    assert {r.peripheral for r in ke_hoach.requests} == {"bus_a"}
    assert "drv_a" in ke_hoach.render()


def test_khong_nap_ca_tep_duoc_noi_thanh_loi() -> None:
    van_ban = plan_pages(hardware=_HoSoGia(), datasheets=None).render()
    assert "KHÔNG nạp cả tệp" in van_ban


# --------------------------------------------------------------------------
# TC-55f, TC-55g, TC-55h — errata
# --------------------------------------------------------------------------


def _errata(**kw) -> ErrataItem:
    kw.setdefault("id", "E-01")
    kw.setdefault("title", "bộ đếm bỏ nhịp khi ghi lúc tràn")
    return ErrataItem(**kw)


def test_chua_tra_khac_han_chip_sach() -> None:
    chua = ErrataAnalysis(part="chip-gia-1", looked_up=False)
    da_tra = ErrataAnalysis(part="chip-gia-1", silicon_rev="D", looked_up=True)

    assert "CHƯA TRA" in chua.confidence()
    assert "KHÔNG có nghĩa là chip sạch" in chua.confidence()
    assert "ĐÃ TRA" in da_tra.confidence() and "CHƯA TRA" not in da_tra.confidence()


def test_da_tra_ma_chua_biet_rev_thi_noi_ro_ket_luan_co_the_thua_hoac_thieu() -> None:
    ban = ErrataAnalysis(part="chip-gia-1", silicon_rev=REV_CHUA_BIET, looked_up=True)
    van_ban = ban.confidence()

    assert "CHƯA BIẾT REV" in van_ban
    assert "thừa" in van_ban and "thiếu" in van_ban


def test_revisions_trong_nghia_la_moi_rev() -> None:
    """Suy ngược lại sẽ biến một chỗ thiếu thông tin thành một lời bảo đảm."""
    assert _errata(revisions=()).applies_to("D")
    assert _errata(revisions=()).applies_to("")


def test_loc_dung_rev_dang_cam() -> None:
    ban = ErrataAnalysis(
        items=(_errata(id="E-01", revisions=("C",)), _errata(id="E-02", revisions=("D",))),
        silicon_rev="D",
        looked_up=True,
    )
    assert [e.id for e in ban.for_rev()] == ["E-02"]


def test_module_cham_loi_qua_ngoai_vi_duoc_goi_ten() -> None:
    ban = ErrataAnalysis(
        items=(_errata(affects=("bus_a",)),), silicon_rev="D", looked_up=True
    )
    cham = ban.impact(_HoSoGia(), [_Module("drv_a", "bus_a"), _Module("drv_b", "timer_b")])

    assert len(cham) == 1
    assert cham[0].module_id == "drv_a"


def test_module_cham_loi_qua_TEN_THANH_GHI_cung_duoc_goi_ten() -> None:
    """Errata thường gọi tên thanh ghi chứ không gọi tên ngoại vi."""
    ban = ErrataAnalysis(
        items=(_errata(affects=("REG_B1",)),), silicon_rev="D", looked_up=True
    )
    cham = ban.impact(_HoSoGia(), [_Module("drv_b", "timer_b")])

    assert len(cham) == 1
    assert cham[0].resource == "REG_B1"


def test_bao_cao_noi_ro_cong_kiem_chung_khong_bat_duoc_loai_loi_nay() -> None:
    ban = ErrataAnalysis(
        items=(_errata(affects=("bus_a",)),), silicon_rev="D", looked_up=True
    )
    van_ban = ban.render(_HoSoGia(), [_Module("drv_a", "bus_a")])

    assert "ĐÚNG THEO DATASHEET" in van_ban
    assert "Không cổng kiểm chứng nào bắt được" in van_ban


def test_muc_khong_co_cach_ne_thi_noi_thang() -> None:
    assert "CHƯA CÓ CÁCH NÉ" in _errata(workaround="").render()


def test_errata_song_sot_qua_vong_ghi_doc(tmp_path: Path) -> None:
    goc = ErrataAnalysis(
        items=(_errata(affects=("bus_a",), revisions=("D",), workaround="đọc lại sau 1 chu kỳ"),),
        silicon_rev="D",
        part="chip-gia-1",
        looked_up=True,
    )
    goc.save(tmp_path / ERRATA_FILE)
    doc = ErrataAnalysis.load(tmp_path / ERRATA_FILE)

    assert doc is not None
    assert doc.looked_up and doc.silicon_rev == "D"
    assert doc.items[0].workaround == "đọc lại sau 1 chu kỳ"


def test_khong_co_tep_thi_tra_none(tmp_path: Path) -> None:
    assert ErrataAnalysis.load(tmp_path / "khong-co.yaml") is None


def test_tra_errata_bang_mo_hinh_danh_dau_da_tra() -> None:
    llm = _json(
        {
            "errata": [
                {
                    "id": "E-01",
                    "title": "bộ đếm bỏ nhịp",
                    "affects": ["bus_a"],
                    "revisions": ["D"],
                    "workaround": "đọc lại",
                    "source": "https://www.microchip.com/errata.pdf",
                }
            ]
        }
    )
    ban = LlmDocLookup(llm=llm).errata(
        part="chip-gia-1", silicon_rev="D", peripherals=["bus_a"]
    )

    assert ban.looked_up, "tra rồi thì phải đánh dấu — nếu không thì không phân biệt được"
    assert ban.items[0].id == "E-01"
    assert ban.silicon_rev == "D"


def test_mo_hinh_thay_duoc_rev_va_ngoai_vi_trong_prompt() -> None:
    llm = _json({"errata": []})
    LlmDocLookup(llm=llm).errata(part="chip-gia-1", silicon_rev="D", peripherals=["bus_a"])
    van_ban = "\n".join(l.content for l in llm.prompts[0].layers)

    assert "Rev silicon: D" in van_ban
    assert "bus_a" in van_ban


def test_khong_biet_rev_thi_prompt_noi_thang_la_chua_biet() -> None:
    llm = _json({"errata": []})
    LlmDocLookup(llm=llm).errata(part="chip-gia-1", silicon_rev="")
    van_ban = "\n".join(l.content for l in llm.prompts[0].layers)

    assert "(chưa biết)" in van_ban


# --------------------------------------------------------------------------
# Ranh giới engine
# --------------------------------------------------------------------------


def test_engine_khong_ghim_ten_mot_ho_chip_nao() -> None:
    ma = (REPO / "eaa" / "docplan.py").read_text(encoding="utf-8").lower()
    for ten in ("atmega", "stm32", "mpu6050", "a4988", "cortex"):
        assert ten not in ma, f"{ten} bị ghim trong engine"


def test_chay_duoc_tren_du_an_that() -> None:
    """Bốn sprint trước không có gì bắt buộc hồ sơ thật phải đủ dữ kiện cho phần này."""
    from eaa.kb import HardwareProfile

    hp = HardwareProfile.load(REPO / "projects" / "robot_balance" / "hardware_profile.yaml")
    ke_hoach = plan_documents(hp)

    assert any(n.kind == DocKind.ERRATA for n in ke_hoach.needs)
    assert ke_hoach.questions(), "dự án mẫu chưa khai rev nên phải còn câu để hỏi"
