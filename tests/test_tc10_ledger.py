"""TC-10 — Error Ledger thành ví dụ phủ định; append-only (FR-KB-03, FR-KLC-01).

TC-10 (STP-04): "Thêm lỗi hallucinated_register rồi sinh lại module → prompt
lần sau chứa lỗi này trong phần ví dụ cần tránh." Ở tầng này kiểm chứng nửa
đầu — nhật ký ghi đúng và chưng cất được thành quy tắc một dòng; nửa sau (quy
tắc thật sự có mặt trong prompt) nằm ở bộ test của composer.

Bất biến được canh: **append-only thuần túy** (AIS §8.1). Khép một lỗi là GHI
THÊM một sự kiện, không phải sửa dòng cũ. Nếu sửa được dòng cũ thì nhật ký mất
tư cách bằng chứng — mà bằng chứng chính là thứ Chương 3 cần.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.ledger import OPEN, RESOLVED, ErrorLedger, LedgerError


@pytest.fixture()
def so(tmp_path: Path) -> ErrorLedger:
    return ErrorLedger(tmp_path / "error_ledger.jsonl")


def _them_loi_ao_giac(so: ErrorLedger, **ghi_de) -> object:
    mac_dinh = dict(
        module="drv_bus_sensor",
        category="hallucinated_register",
        description="Mô hình dùng một thanh ghi không tồn tại trên thiết bị đích",
        evidence="dòng 42 của bản sinh lần 1",
        peripheral="bus",
        registers=["REG_KHONG_CO"],
        rule="KHÔNG dùng REG_KHONG_CO — thiết bị đích không có thanh ghi này",
    )
    mac_dinh.update(ghi_de)
    return so.add(**mac_dinh)


# --------------------------------------------------------------------------
# Ghi và đọc
# --------------------------------------------------------------------------


def test_ghi_loi_roi_doc_lai_du_truong(so: ErrorLedger) -> None:
    entry = _them_loi_ao_giac(so)

    assert entry.id == "err-0001"
    assert entry.status == OPEN

    lai = so.get(entry.id)
    assert lai.category == "hallucinated_register"
    assert lai.module == "drv_bus_sensor"
    assert lai.registers == ("REG_KHONG_CO",)
    assert lai.evidence == "dòng 42 của bản sinh lần 1"
    assert lai.ts


def test_moi_dong_la_mot_json_doc_duoc_bang_cong_cu_chuan(so: ErrorLedger) -> None:
    """ADR-06: file phẳng, truy vết bằng công cụ chuẩn."""
    import json

    _them_loi_ao_giac(so)
    _them_loi_ao_giac(so, description="Lỗi thứ hai", rule="")

    dong = so.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(dong) == 2
    for d in dong:
        assert json.loads(d)["event"] == "error"


def test_phan_loai_khong_hop_le_bi_tu_choi(so: ErrorLedger) -> None:
    with pytest.raises(LedgerError, match="Phân loại lỗi"):
        so.add(module="m", category="tự_nghĩ_ra", description="x")


def test_mo_ta_rong_bi_tu_choi(so: ErrorLedger) -> None:
    with pytest.raises(LedgerError, match="mô tả"):
        so.add(module="m", category="other", description="   ")


def test_nhat_ky_chua_ton_tai_thi_rong(tmp_path: Path) -> None:
    assert ErrorLedger(tmp_path / "chua-co.jsonl").entries() == []


def test_dong_hong_bao_loi_kem_so_dong(so: ErrorLedger) -> None:
    _them_loi_ao_giac(so)
    with open(so.path, "a", encoding="utf-8") as f:
        f.write("{không phải json\n")
    with pytest.raises(LedgerError, match=":2:"):
        so.entries()


# --------------------------------------------------------------------------
# Append-only — khép lỗi mà không sửa dòng cũ
# --------------------------------------------------------------------------


def test_khep_loi_bang_cach_ghi_them_khong_sua_dong_cu(so: ErrorLedger) -> None:
    entry = _them_loi_ao_giac(so)
    dong_goc = so.path.read_text(encoding="utf-8").splitlines()[0]

    so.resolve(entry.id, commit="abc1234", note="Sinh lại với chunk đúng")

    # Dòng gốc còn nguyên từng byte.
    assert so.path.read_text(encoding="utf-8").splitlines()[0] == dong_goc
    assert len(so.path.read_text(encoding="utf-8").strip().splitlines()) == 2

    lai = so.get(entry.id)
    assert lai.status == RESOLVED
    assert lai.resolved_by == "abc1234"
    assert lai.resolution_note == "Sinh lại với chunk đúng"
    assert lai.description == "Mô hình dùng một thanh ghi không tồn tại trên thiết bị đích"


def test_loc_bo_loi_da_khep_khi_can(so: ErrorLedger) -> None:
    a = _them_loi_ao_giac(so)
    _them_loi_ao_giac(so, description="Lỗi còn mở")
    so.resolve(a.id, commit="abc1234")

    assert len(so.entries()) == 2
    assert len(so.entries(include_resolved=False)) == 1


def test_khep_mot_loi_khong_ton_tai_bi_tu_choi(so: ErrorLedger) -> None:
    with pytest.raises(LedgerError, match="Không có mục lỗi"):
        so.resolve("err-9999")


# --------------------------------------------------------------------------
# K5 — chưng cất lỗi thành quy tắc một dòng
# --------------------------------------------------------------------------


def test_quy_tac_uu_tien_cau_menh_lenh_do_nguoi_viet(so: ErrorLedger) -> None:
    entry = _them_loi_ao_giac(so)
    assert entry.as_rule == "KHÔNG dùng REG_KHONG_CO — thiết bị đích không có thanh ghi này"


def test_khong_co_quy_tac_thi_sinh_tu_mo_ta(so: ErrorLedger) -> None:
    entry = so.add(
        module="m", category="wrong_timing", description="Sai hệ số chia bộ đếm", rule=""
    )
    assert entry.as_rule == "KHÔNG lặp lại: Sai hệ số chia bộ đếm"


def test_quy_tac_sinh_tu_mo_ta_dai_bi_cat_thanh_mot_dong(so: ErrorLedger) -> None:
    entry = so.add(module="m", category="other", description="x " * 300, rule="")
    assert len(entry.as_rule) <= 180
    assert "\n" not in entry.as_rule
    assert entry.as_rule.endswith("…")


def test_chi_lay_top_3_du_nhat_ky_dai_bao_nhieu(so: ErrorLedger) -> None:
    """Nhật ký dài vô hạn nhưng phần vào prompt luôn ~300 token (K5)."""
    for i in range(20):
        so.add(module="m", category="other", description=f"Lỗi số {i}")
    assert len(so.rules_for("m")) == 3


def test_uu_tien_loi_cua_chinh_module_dang_sinh(so: ErrorLedger) -> None:
    so.add(module="module_khac", category="other", description="Lỗi module khác", rule="R-KHAC")
    so.add(module="module_dich", category="other", description="Lỗi module đích", rule="R-DICH")
    assert so.rules_for("module_dich")[0] == "R-DICH"


def test_uu_tien_loi_cung_thanh_ghi(so: ErrorLedger) -> None:
    so.add(module="a", category="other", description="không liên quan", rule="R-XA")
    so.add(
        module="a",
        category="hallucinated_register",
        description="cùng thanh ghi",
        registers=["REG_X"],
        rule="R-GAN",
    )
    assert so.rules_for("b", registers=["REG_X"])[0] == "R-GAN"


def test_uu_tien_loi_cung_ngoai_vi(so: ErrorLedger) -> None:
    so.add(module="a", category="other", description="khác ngoại vi", peripheral="uart", rule="R-XA")
    so.add(module="b", category="other", description="cùng ngoại vi", peripheral="bus", rule="R-GAN")
    assert so.rules_for("c", peripheral="bus")[0] == "R-GAN"


def test_loi_con_mo_duoc_uu_tien_hon_loi_da_khep(so: ErrorLedger) -> None:
    a = so.add(module="m", category="other", description="đã sửa", rule="R-DA-KHEP")
    so.add(module="m", category="other", description="chưa sửa", rule="R-CON-MO")
    so.resolve(a.id, commit="abc")

    quy_tac = so.rules_for("m")
    assert quy_tac[0] == "R-CON-MO"
    # Lỗi đã khép vẫn giữ lại: mô hình không "nhớ" rằng lần trước nó đã bị sửa.
    assert "R-DA-KHEP" in quy_tac


def test_nhat_ky_rong_thi_khong_co_quy_tac_nao(so: ErrorLedger) -> None:
    assert so.rules_for("m") == []


def test_thong_ke_theo_phan_loai_cho_chuong_3(so: ErrorLedger) -> None:
    _them_loi_ao_giac(so)
    _them_loi_ao_giac(so, description="lần hai")
    so.add(module="m", category="wrong_timing", description="sai hệ số chia")

    assert so.categories_seen() == {"hallucinated_register": 2, "wrong_timing": 1}


# --------------------------------------------------------------------------
# TC-02 — lý do reject tại gate cũng vào nhật ký
# --------------------------------------------------------------------------


def test_ly_do_reject_tai_gate_ghi_duoc_vao_nhat_ky(so: ErrorLedger) -> None:
    """TC-02: reject tại G3 kèm lý do → lý do xuất hiện trong error_ledger."""
    entry = so.add(
        module="drv_bus_sensor",
        category="gate_rejection",
        description="Kỹ sư từ chối tại G3: thiếu kiểm tra mã trạng thái sau mỗi thao tác bus",
        evidence="G3, bản sinh lần 2",
    )
    assert entry.category == "gate_rejection"
    assert "G3" in so.rules_for("drv_bus_sensor")[0]
