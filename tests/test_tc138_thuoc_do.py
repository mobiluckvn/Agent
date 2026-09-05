"""TC-138 — thước đo: chỉ số của văn liệu, cộng bốn trục chưa ai có (GĐ2).

Xem `docs/KE_HOACH_VUOT_LEN.md` §3 và `docs/SAI_LECH_THIET_KE.md` mục SL-177.

Nửa A là thước của họ (``pass@k``, các hạng *trượt dịch / sai hành vi / đúng*):
phải có, vì không có thì không đối thoại được với văn liệu.

Nửa B là đóng góp: bốn trục không benchmark nào trong khảo sát hỏi — độ nhạy
bài kiểm, vá chỉnh đồ đo, mất việc im lặng, truy về được. Một hệ đạt ``pass@1``
cao mà 40% bài kiểm của nó rỗng thì con số ấy không có nghĩa như người đọc
tưởng, và không ai đo nên không ai nói.

Ba chuyện bài này canh gắt nhất
--------------------------------

1. **Không gộp hai hạng bằng chứng.** Kết quả trên bo thật và kết quả trên máy
   chủ đứng riêng. Trộn rồi báo một con số là nói dối, kể cả khi con số ấy đúng
   về số học — và đây là bài chống lại chính cám dỗ của đề án.
2. **`HANDOFF` và `BLOCKED` đứng riêng.** Gộp *hết vòng vá* vào *sai hành vi*
   là xoá mất chính thứ sản phẩm này làm khác; gộp *lỗi môi trường* vào đó là
   ghi lỗi của máy tính vào sổ của mô hình.
3. **Hạng suy từ BÁO CÁO CỔNG, không từ trường tự khai.** Dựng bộ chấm riêng
   cho benchmark là dựng con đường thứ hai, và con số đi ra nói về con đường ấy
   chứ không nói về sản phẩm.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eaa.bench import (
    BAN_GIAO,
    CHAN,
    DUNG,
    SAI_HANH_VI,
    TRUOT_DICH,
    KetQuaBench,
    LuotChay,
    NhiemVu,
    doc_bo_chuan,
    gom,
    hang_tu_ket_cuc,
    pass_at_k,
)
from eaa.tools.base import ToolReport


def _bao_cao(gate: str, passed: bool, **metrics) -> ToolReport:
    return ToolReport(gate=gate, passed=passed, metrics=metrics)


def _ket_cuc(status: str = "merged", *bao_cao: ToolReport) -> SimpleNamespace:
    return SimpleNamespace(status=status, reports=list(bao_cao))


# ── xếp hạng từ báo cáo cổng ─────────────────────────────────────────────────


def test_moi_cong_dat_thi_DUNG() -> None:
    assert hang_tu_ket_cuc(
        _ket_cuc("merged", _bao_cao("compile", True), _bao_cao("unittests", True))
    ) == DUNG


def test_cong_DICH_truot_thi_TRUOT_DICH() -> None:
    assert hang_tu_ket_cuc(
        _ket_cuc("awaiting_gate", _bao_cao("compile", False))
    ) == TRUOT_DICH


def test_cong_khac_truot_thi_SAI_HANH_VI() -> None:
    assert hang_tu_ket_cuc(
        _ket_cuc("awaiting_gate", _bao_cao("compile", True), _bao_cao("unittests", False))
    ) == SAI_HANH_VI


def test_HANDOFF_dung_rieng_khong_lan_vao_sai_hanh_vi() -> None:
    """Hệ đã CHỦ ĐỘNG dừng và hỏi người — gộp vào 'sai hành vi' là xoá mất
    chính thứ sản phẩm này làm khác."""
    assert hang_tu_ket_cuc(
        _ket_cuc("handoff", _bao_cao("unittests", False))
    ) == BAN_GIAO


def test_loi_MOI_TRUONG_dung_rieng() -> None:
    """Tính lỗi thiếu công cụ vào sổ của mô hình là ghi nhầm sổ."""
    assert hang_tu_ket_cuc(
        _ket_cuc("awaiting_gate", _bao_cao("compile", False, env_error=True))
    ) == CHAN
    assert hang_tu_ket_cuc(
        _ket_cuc("awaiting_gate", _bao_cao("static", False, config_error=True))
    ) == CHAN


def test_hang_suy_tu_BAO_CAO_khong_tu_truong_tu_khai() -> None:
    """`status` là thứ được GÁN; báo cáo cổng là thứ đã CHẠY."""
    assert hang_tu_ket_cuc(
        _ket_cuc("merged", _bao_cao("compile", False))
    ) == TRUOT_DICH


def test_khong_co_bao_cao_nao_thi_khong_dam_goi_la_DUNG() -> None:
    assert hang_tu_ket_cuc(_ket_cuc("merged")) == BAN_GIAO


# ── pass@k ───────────────────────────────────────────────────────────────────


def test_pass_at_k_dung_cong_thuc_khong_chech() -> None:
    """n=5, c=2 → pass@1 = 0.4 và pass@5 = 1."""
    assert pass_at_k(5, 2, 1) == pytest.approx(0.4)
    assert pass_at_k(5, 2, 5) == pytest.approx(1.0)


def test_pass_at_k_KHAC_ti_le_luot_dung() -> None:
    """Chỗ hai công thức TÁCH NHAU, và nó là chỗ duy nhất phân biệt được chúng.

    Ở ``k=1`` cả hai cho cùng một số, và ở ``k >= n-c+1`` cả hai cho 1. Bài kiểm
    chỉ dùng hai chỗ ấy sẽ xanh với một phép tính sai — tôi viết đúng như thế
    lần đầu, và kiểm đột biến mới lộ ra.

    ``1 - C(n-c, k)/C(n, k)`` với n=5, c=1, k=2 cho 0,4; tỉ lệ lượt đúng cho
    0,2. Con số thứ hai trả lời câu khác: *"một lượt bất kỳ có đúng không"*,
    chứ không phải *"thử k lượt thì có ít nhất một lượt đúng không"*.
    """
    assert pass_at_k(5, 1, 2) == pytest.approx(0.4)
    assert pass_at_k(4, 1, 2) == pytest.approx(0.5)
    assert pass_at_k(6, 2, 3) == pytest.approx(0.8)


def test_pass_at_k_bien() -> None:
    assert pass_at_k(0, 0, 1) == 0.0
    assert pass_at_k(3, 0, 3) == 0.0
    assert pass_at_k(3, 3, 1) == 1.0
    # k lớn hơn số lượt thì cắt về số lượt, không chia cho 0.
    assert pass_at_k(2, 1, 5) == pytest.approx(1.0)


def test_ba_nhiem_vu_hai_dung_mot_truot_dich() -> None:
    bo = gom([
        NhiemVu("t1", luot=(LuotChay(DUNG),)),
        NhiemVu("t2", luot=(LuotChay(DUNG),)),
        NhiemVu("t3", luot=(LuotChay(TRUOT_DICH),)),
    ])
    assert bo.pass_at(1) == pytest.approx(2 / 3)
    assert bo.dem_hang()[TRUOT_DICH] == 1


# ── bốn trục mới ─────────────────────────────────────────────────────────────


def test_truc_do_nhay_dem_duoc_bai_kiem_RONG() -> None:
    bo = gom([NhiemVu("t", luot=(
        LuotChay(DUNG, bai_kiem_moi=4, bai_kiem_khong_phan_biet=1),))])
    assert bo.truc_moi()["do_nhay"] == pytest.approx(0.25)


def test_truc_chinh_do_do_dem_theo_LUOT() -> None:
    bo = gom([
        NhiemVu("t1", luot=(LuotChay(BAN_GIAO, dau_vet_chinh_do_do=3),)),
        NhiemVu("t2", luot=(LuotChay(DUNG),)),
    ])
    assert bo.truc_moi()["chinh_do_do"] == pytest.approx(0.5)


def test_truc_mat_viec_im_lang_dem_tong() -> None:
    bo = gom([NhiemVu("t", luot=(
        LuotChay(DUNG, loi_goi_bi_danh_roi=2), LuotChay(DUNG, loi_goi_bi_danh_roi=1)))])
    assert bo.truc_moi()["mat_viec_im_lang"] == 3


def test_truc_truy_ve_duoc() -> None:
    bo = gom([NhiemVu("t", luot=(
        LuotChay(DUNG, ghi_thanh_ghi=4, ghi_trich_dan_dung=3),))])
    assert bo.truc_moi()["truy_ve_duoc"] == pytest.approx(0.75)


def test_CHUA_DO_DUOC_khac_han_bang_KHONG() -> None:
    """Bộ chuẩn không sinh bài kiểm nào thì tỉ lệ bài kiểm rỗng KHÔNG phải 0% —
    nó không tồn tại. Báo 0% là khai một thành tích chưa đo."""
    bo = gom([NhiemVu("t", luot=(LuotChay(DUNG),))])
    truc = bo.truc_moi()
    assert truc["do_nhay"] is None
    assert truc["truy_ve_duoc"] is None
    assert "CHƯA ĐO ĐƯỢC" in bo.render()


# ── hai hạng bằng chứng, không gộp ───────────────────────────────────────────


def test_bao_cao_TACH_bo_that_khoi_may_chu(capsys) -> None:
    """Bài chống lại chính cám dỗ của đề án."""
    bo = gom([
        NhiemVu("t1", tren_bo=True, luot=(LuotChay(DUNG),)),
        NhiemVu("t2", luot=(LuotChay(DUNG),)),
        NhiemVu("t3", luot=(LuotChay(DUNG),)),
    ])
    assert bo.tach_theo_bang_chung() == {"tren_bo": 1, "tren_may_chu": 2}
    van = bo.render()
    assert "KHÔNG gộp" in van
    assert "BO THẬT   : 1" in van and "máy chủ   : 2" in van


# ── bộ rỗng ──────────────────────────────────────────────────────────────────


def test_bo_RONG_khong_chia_cho_khong() -> None:
    bo = KetQuaBench()
    assert bo.pass_at(1) == 0.0
    assert bo.dem_hang()[DUNG] == 0
    assert all(v is None for v in bo.truc_moi().values())
    assert "chưa có nhiệm vụ nào" in bo.render()
    assert "báo 0 là khai một kết quả chưa đo" in bo.render()


# ── đọc sổ ───────────────────────────────────────────────────────────────────


def test_doc_so_ket_qua(tmp_path: Path) -> None:
    p = tmp_path / "bench_results.jsonl"
    p.write_text(
        json.dumps({
            "ma": "t1", "nen_tang": "avr", "tren_bo": True,
            "luot": [{"hang": "BC", "bai_kiem_moi": 2, "bai_kiem_khong_phan_biet": 1}],
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    bo = doc_bo_chuan(p)
    assert len(bo.nhiem_vu) == 1
    assert bo.nhiem_vu[0].tren_bo is True
    assert bo.truc_moi()["do_nhay"] == pytest.approx(0.5)


def test_chua_chay_lan_nao_KHONG_phai_loi(tmp_path: Path) -> None:
    """Trạng thái hợp lệ, và `render()` nói thẳng ra thay vì báo một con số 0."""
    bo = doc_bo_chuan(tmp_path / "khong_co.jsonl")
    assert bo.nhiem_vu == ()
    assert "chưa có nhiệm vụ nào" in bo.render()


def test_dong_hong_bao_ro_so_dong(tmp_path: Path) -> None:
    p = tmp_path / "b.jsonl"
    p.write_text('{"ma": "t1"}\n{ đây không phải JSON\n', encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        doc_bo_chuan(p)


# ── tất định ─────────────────────────────────────────────────────────────────


def test_CHAY_LAI_CHO_CON_SO_Y_HET(tmp_path: Path) -> None:
    """Tất định là điều kiện của một cái thước. Một thước cho hai số cho cùng
    một vật thì nó không đo gì cả."""
    p = tmp_path / "b.jsonl"
    p.write_text(
        "\n".join(
            json.dumps({"ma": f"t{i}", "luot": [{"hang": "BC" if i % 2 else "CF"}]})
            for i in range(6)
        ),
        encoding="utf-8",
    )
    a, b = doc_bo_chuan(p), doc_bo_chuan(p)
    assert a.render() == b.render()
    assert a.pass_at(1) == b.pass_at(1)
    assert a.truc_moi() == b.truc_moi()
