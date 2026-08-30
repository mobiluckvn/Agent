"""TC-20 và TC-23 — hai test case của thiết kế còn thiếu tới bản này.

TC-20 (AIS): "Chạy golden set sau khi thêm chunk nhiễu → precision@3 vẫn ≥ 0,9;
chunk nhiễu không được chọn cho module không liên quan."

TC-23 (AIS): "Nộp ảnh màn oscilloscope đo chu kỳ ngắt → Số đo đề xuất khớp ảnh
(sai số khai báo); người sửa được giá trị trước khi lưu vào Measurement Records."

| Mã | Kiểm ở đây |
|---|---|
| TC-20a | precision@3 trên bộ chuẩn của dự án mẫu ≥ 0,9 |
| TC-20b | Chunk nhiễu KHÔNG lọt vào module không liên quan |
| TC-20c | Bộ chuẩn trỏ vào chunk không có thật thì bị bắt |
| TC-20d | Bộ chọn biết DỪNG khi hết thứ liên quan, không lấp đủ k |
| TC-23a | Số đo từ ảnh mang SAI SỐ đọc ảnh |
| TC-23b | Thiếu sai số thì nói thẳng, không im lặng |
| TC-23c | Không tự vào Measurement Records — phải có người chốt |
| TC-23d | Người sửa được giá trị, và bản ghi giữ CẢ HAI con số |

Ghi chú về TC-20: bộ chuẩn của dự án mẫu, ở lượt chạy đầu tiên, cho
precision@3 = 0,889 và để chunk nhiễu `ds-023` đẩy `ds-031` ra khỏi top-3.
Nguyên nhân là đồ thị chưa nối `configured_by` cho LINH KIỆN (chỉ nối cho ngoại
vi), nên trích đoạn về con cảm biến không có đường nào để được xếp hạng cao.
Đó đúng là loại thoái lui mà TC-20 sinh ra để bắt — và nó bắt được ngay lượt
đầu.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.goldenset import (
    GOLDEN_FILE,
    PRECISION_TOI_THIEU,
    CaseResult,
    GoldenCase,
    GoldenSet,
    GoldenSetError,
)
from eaa.ingest import IngestError, ProposedMeasurement, ScopeImageReader

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


@pytest.fixture(scope="module")
def do_thi():
    from eaa.cli import build_context

    return build_context(DU_AN).graph


@pytest.fixture(scope="module")
def kho_chunk():
    from eaa.cli import build_context

    return build_context(DU_AN).kb.datasheets


@pytest.fixture(scope="module")
def bo_chuan() -> GoldenSet:
    bo = GoldenSet.load(DU_AN / GOLDEN_FILE)
    assert bo is not None, "dự án mẫu phải có bộ chuẩn truy xuất"
    return bo


# --------------------------------------------------------------------------
# TC-20
# --------------------------------------------------------------------------


def test_tc20_precision_tren_nguong_sau_khi_them_chunk_nhieu(
    bo_chuan: GoldenSet, do_thi
) -> None:
    bao_cao = bo_chuan.evaluate(do_thi)

    assert bao_cao.precision_at_k >= PRECISION_TOI_THIEU, bao_cao.render()
    assert bao_cao.ok


def test_tc20_chunk_nhieu_khong_lot_vao_module_khong_lien_quan(
    bo_chuan: GoldenSet, do_thi
) -> None:
    """Đây là phép kiểm mà precision một mình không thay được.

    Một bộ chọn có thể giữ precision cao mà vẫn kéo một chunk chẳng liên quan
    vào một module chẳng liên quan — và đó là đường mà ảo giác 'có nguồn' đi
    vào prompt.
    """
    bao_cao = bo_chuan.evaluate(do_thi)

    assert bo_chuan.noise_ids, "bộ chuẩn phải có chunk nhiễu, nếu không nó không đo gì"
    assert bao_cao.noise_leaks == (), bao_cao.render()


def test_tc20_chunk_nhieu_that_su_nam_trong_kho(bo_chuan: GoldenSet, kho_chunk) -> None:
    """Chunk nhiễu phải CÓ THẬT và đã duyệt, nếu không phép kiểm là vô nghĩa."""
    hoat_dong = {c.id for c in kho_chunk.active()}
    for cid in bo_chuan.noise_ids:
        assert cid in hoat_dong, (
            f"{cid} không phải chunk đang hiệu lực — một chunk nhiễu bị lọc ở "
            "tầng khác thì nó không thử được bộ chọn"
        )


def test_tc20_bo_chuan_khong_tro_vao_hu_khong(bo_chuan: GoldenSet, kho_chunk) -> None:
    """Đáp án trỏ vào chunk không có thật kéo precision xuống mãi mãi."""
    assert bo_chuan.check_ids(kho_chunk) == []


def test_bo_chuan_tro_sai_thi_bi_bat() -> None:
    class _KhoGia:
        def all(self):
            class _C:
                id = "ds-001"

            return [_C()]

    bo = GoldenSet(cases=(GoldenCase("m", ("x",), ("ds-999",)),))
    assert any("ds-999" in s for s in bo.check_ids(_KhoGia()))


def test_tc20_bo_chon_biet_dung_khi_het_thu_lien_quan(do_thi) -> None:
    """Không lấp đủ k bằng bất cứ thứ gì gần nhất."""
    do_thi.add_module("drv_timer_tick", uses=["timer1"])
    chon = do_thi.chunks_for("drv_timer_tick", top_k=3)

    assert len(chon) < 3, "chỉ một trích đoạn liên quan tới timer1"
    assert "ds-012" in chon


def test_mau_so_cua_precision_la_so_chunk_that_su_chon() -> None:
    """Chia cho k khi kho chưa đủ chunk là phạt bộ chọn vì một chỗ thiếu của kho."""
    ket = CaseResult(module_id="m", selected=("a",), relevant=("a", "b", "c"))
    assert ket.precision == 1.0


def test_precision_trung_binh_theo_ca_khong_gop_chung() -> None:
    """Mỗi module một phiếu — module nhiều chunk không được có tiếng nói lớn hơn."""
    from eaa.goldenset import RetrievalReport

    bao_cao = RetrievalReport(
        cases=(
            CaseResult("nhieu", ("a", "b", "c"), ("a", "b", "c")),
            CaseResult("it", ("x",), ("y",)),
        )
    )
    assert bao_cao.precision_at_k == pytest.approx(0.5)


def test_ca_khong_co_dap_an_bi_tu_choi() -> None:
    with pytest.raises(GoldenSetError, match="không khai trích đoạn nào"):
        GoldenCase("m", ("x",), ())


def test_linh_kien_khai_thanh_ghi_thi_do_thi_noi_duoc(do_thi) -> None:
    """Đây là chỗ TC-20 đã tìm ra và đã sửa: linh kiện cũng có thanh ghi riêng."""
    do_thi.add_module("drv_bus_sensor", uses=["twi", "imu"])
    thanh_ghi = do_thi.registers_for("drv_bus_sensor")

    assert "WHO_AM_I" in thanh_ghi, (
        "thanh ghi của linh kiện phải vào được đồ thị; thiếu cạnh này thì trích "
        "đoạn về con cảm biến bị chunk cùng bus đẩy ra khỏi prompt"
    )


# --------------------------------------------------------------------------
# TC-23
# --------------------------------------------------------------------------


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


@pytest.fixture()
def anh(tmp_path: Path) -> Path:
    p = tmp_path / "man_hien_song.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    return p


def _doc(anh: Path, **so_do) -> list[ProposedMeasurement]:
    llm = _json({"measurements": [so_do]})
    return ScopeImageReader(llm=llm).read(anh)


def test_tc23_so_do_tu_anh_mang_sai_so_doc_anh(anh: Path) -> None:
    ket = _doc(
        anh,
        key="loop_period_ms",
        value=10.2,
        unit="ms",
        uncertainty=0.25,
        reading="2,04 ô × 5 ms/ô",
    )

    assert len(ket) == 1
    m = ket[0]
    assert m.value == 10.2 and m.unit == "ms"
    assert m.uncertainty_declared
    assert m.interval() == pytest.approx((9.95, 10.45))
    assert "2,04 ô" in m.render()


def test_tc23_thieu_sai_so_thi_noi_thang(anh: Path) -> None:
    """Thiếu sai số thì số đọc từ ảnh trông y hệt số máy đo gửi về."""
    m = _doc(anh, key="loop_period_ms", value=10.2, unit="ms")[0]

    assert not m.uncertainty_declared
    assert "CHƯA KHAI SAI SỐ" in m.render()


def test_so_do_khong_co_don_vi_bi_tu_choi() -> None:
    with pytest.raises(IngestError, match="đơn vị"):
        ProposedMeasurement(key="x", value=1.0, unit="")


def test_tc23_khong_tu_vao_measurement_records(anh: Path) -> None:
    """Không có người chốt thì nó không thành bản ghi."""
    m = _doc(anh, key="loop_period_ms", value=10.2, unit="ms", uncertainty=0.25)[0]

    assert m.status == "proposed"
    with pytest.raises(IngestError, match="người chốt"):
        m.accept(None, actor="")


def test_tc23_nguoi_sua_duoc_gia_tri_va_ban_ghi_giu_ca_hai(anh: Path) -> None:
    """Câu 'máy đọc ra bao nhiêu, người sửa thành bao nhiêu' phải trả lời được."""
    m = _doc(anh, key="loop_period_ms", value=10.2, unit="ms", uncertainty=0.25)[0]
    ban_ghi = m.accept(10.0, actor="Vũ Trí Công")

    assert ban_ghi["value"] == 10.0
    assert ban_ghi["proposed_value"] == 10.2
    assert ban_ghi["edited"] is True
    assert ban_ghi["actor"] == "Vũ Trí Công"
    assert ban_ghi["channel"] == "anh_man_hien_song"


def test_tc23_giu_nguyen_so_may_doc_thi_khong_danh_dau_la_sua(anh: Path) -> None:
    m = _doc(anh, key="loop_period_ms", value=10.2, unit="ms", uncertainty=0.25)[0]
    assert m.accept(None, actor="ky-su")["edited"] is False


def test_tc23_anh_goc_duoc_giu_lai(anh: Path, tmp_path: Path) -> None:
    """Câu 'máy đọc nhầm ảnh' chỉ kiểm chứng lại được khi ảnh còn đó."""
    from eaa.ingest import MediaStore

    kho = MediaStore(tmp_path / "media")
    llm = _json({"measurements": [{"key": "t", "value": 1.0, "unit": "ms", "uncertainty": 0.1}]})
    ket = ScopeImageReader(llm=llm, media=kho).read(anh)

    luu = Path(ket[0].source_image)
    assert luu.is_file() and luu.parent == tmp_path / "media"
    assert luu.read_bytes() == anh.read_bytes()


def test_tc23_anh_di_kem_prompt(anh: Path) -> None:
    llm = _json({"measurements": []})
    ScopeImageReader(llm=llm).read(anh, expect=["loop_period_ms"])

    prompt = llm.prompts[0]
    assert prompt.image_path.endswith(".png")
    assert "loop_period_ms" in "\n".join(l.content for l in prompt.layers)


def test_tep_khong_phai_anh_thi_tu_choi(tmp_path: Path) -> None:
    tep = tmp_path / "khong-phai-anh.pdf"
    tep.write_bytes(b"%PDF-1.4")

    with pytest.raises(IngestError, match="không phải ảnh"):
        ScopeImageReader(llm=_json({})).read(tep)


def test_khong_doc_duoc_so_nao_la_ket_cuc_hop_le(anh: Path) -> None:
    """Một con số bịa ra kèm đơn vị đúng còn tệ hơn không có con số nào."""
    llm = _json({"measurements": [{"key": "t", "unit": "ms", "value": "không rõ"}]})
    assert ScopeImageReader(llm=llm).read(anh) == []
