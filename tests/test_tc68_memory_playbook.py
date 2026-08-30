"""TC-68 — bộ nhớ liên dự án và sổ tay lỗi.

Hai bất biến bài này canh:

* **Append-only.** Sửa là ghi thêm, không ghi đè. Sau mỗi thao tác, số DÒNG
  trong tệp chỉ tăng — vì câu hỏi "lúc ấy ta tin cái gì" phải trả lời được.
* **Phạm vi được tôn trọng.** Bài học của dự án A không tự chảy sang dự án B.
  Đó là chỗ một bộ nhớ dùng chung gây hại nhất.
"""

from __future__ import annotations

import json

import pytest

from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA
from eaa.memory import (
    KIND_BAI_HOC,
    KIND_CONG_CU,
    KIND_MOI_TRUONG,
    TOAN_CUC,
    MemoryError_,
    MemoryStore,
    scope_du_an,
    scope_mcu,
)
from eaa.playbook import Playbook, PlaybookEntry, normalise, signature


def _so_dong(store) -> int:
    return len(store.path.read_text(encoding="utf-8").strip().splitlines())


# ══════════════════════════════════════════════════ bộ nhớ liên dự án ═══


def test_ghi_va_doc_lai_duoc(tmp_path):
    s = MemoryStore(tmp_path)
    f = s.add(KIND_CONG_CU, "cppcheck", "đã cài, bản 2.13", evidence="doctor 30/08")
    assert s.get(f.id).statement == "đã cài, bản 2.13"
    assert s.active() == [f]


def test_loai_ngoai_bo_bi_tu_choi(tmp_path):
    with pytest.raises(MemoryError_, match="không có trong bộ"):
        MemoryStore(tmp_path).add("linh tinh", "x", "y")


def test_su_kien_rong_bi_tu_choi(tmp_path):
    with pytest.raises(MemoryError_):
        MemoryStore(tmp_path).add(KIND_BAI_HOC, "  ", "có nội dung")


def test_thay_the_khong_xoa_ban_cu(tmp_path):
    s = MemoryStore(tmp_path)
    cu = s.add(KIND_CONG_CU, "cppcheck", "bản 2.13")
    truoc = _so_dong(s)
    moi = s.supersede(cu.id, "bản 2.14")

    assert _so_dong(s) == truoc + 1, "append-only: số dòng chỉ được tăng"
    assert len(s.all()) == 2
    assert len(s.active()) == 1
    assert s.active()[0].id == moi.id
    assert s.get(cu.id).superseded_by == moi.id
    assert s.get(cu.id).active is False


def test_thay_the_giu_nguyen_loai_va_pham_vi(tmp_path):
    s = MemoryStore(tmp_path)
    cu = s.add(KIND_BAI_HOC, "nạp", "phải kiểm sau khi nạp", scope=scope_mcu("avr"))
    moi = s.supersede(cu.id, "phải kiểm cả trước lẫn sau")
    assert moi.kind == KIND_BAI_HOC and moi.scope == scope_mcu("avr")


def test_thay_the_su_kien_khong_ton_tai_thi_bao_loi(tmp_path):
    with pytest.raises(MemoryError_, match="để thay"):
        MemoryStore(tmp_path).supersede("m-khong-co", "gì đó")


def test_bai_hoc_du_an_khac_khong_tu_chay_sang(tmp_path):
    """Chỗ một bộ nhớ dùng chung gây hại nhất."""
    s = MemoryStore(tmp_path)
    s.add(KIND_BAI_HOC, "bo A", "chân 9 bị nhiễu", scope=scope_du_an("robot"))
    s.add(KIND_BAI_HOC, "bo B", "nguồn cần tụ lọc", scope=scope_du_an("khac"))
    s.add(KIND_MOI_TRUONG, "máy", "có brew", scope=TOAN_CUC)

    lien_quan = s.relevant(project="robot")
    assert {f.subject for f in lien_quan} == {"bo A", "máy"}


def test_bai_hoc_theo_ho_mcu_ap_dung_dung_ho(tmp_path):
    s = MemoryStore(tmp_path)
    s.add(KIND_BAI_HOC, "cầu chì", "đừng đụng", scope=scope_mcu("avr"))
    s.add(KIND_BAI_HOC, "khác", "chuyện khác", scope=scope_mcu("stm32"))
    assert [f.subject for f in s.relevant(mcu="avr")] == ["cầu chì"]
    assert [f.subject for f in s.relevant(mcu="AVR")] == ["cầu chì"]


def test_tim_theo_loai_pham_vi_va_noi_dung(tmp_path):
    s = MemoryStore(tmp_path)
    s.add(KIND_CONG_CU, "cppcheck", "đã cài")
    s.add(KIND_CONG_CU, "git", "đã cài")
    s.add(KIND_BAI_HOC, "x", "cppcheck hay báo nhầm")
    assert len(s.find(kind=KIND_CONG_CU)) == 2
    assert len(s.find(contains="cppcheck")) == 2
    assert len(s.find(kind=KIND_BAI_HOC, contains="cppcheck")) == 1


def test_su_kien_co_bang_chung_thi_suy_ra_khong_thi_gia_dinh(tmp_path):
    s = MemoryStore(tmp_path)
    assert s.add(KIND_CONG_CU, "a", "b", evidence="doctor").confidence_level == SUY_RA
    assert s.add(KIND_CONG_CU, "c", "d").confidence_level == GIA_DINH


def test_bo_nho_khong_bao_gio_noi_da_kiem(tmp_path):
    """Sự kiện nhớ từ lần trước có thể đã cũ — máy đổi, công cụ gỡ."""
    s = MemoryStore(tmp_path)
    f = s.add(KIND_MOI_TRUONG, "máy", "có brew", evidence="đo lúc 30/08")
    assert f.confidence_level != DA_KIEM


def test_nho_ban_do_moi_truong(tmp_path):
    from eaa.environ import probe

    s = MemoryStore(tmp_path)
    ds = s.remember_environment(probe(network=False), machine="may-thu")
    assert len(ds) == 2
    assert any("hệ điều hành" in f.subject for f in ds)
    assert all(f.kind == KIND_MOI_TRUONG for f in ds)


def test_dong_hong_trong_tep_khong_lam_sap(tmp_path):
    s = MemoryStore(tmp_path)
    s.add(KIND_CONG_CU, "a", "b")
    with s.path.open("a", encoding="utf-8") as f:
        f.write("{ khong phai json\n\n")
    s.add(KIND_CONG_CU, "c", "d")
    assert len(s.all()) == 2


def test_kho_rong_van_render_duoc(tmp_path):
    assert "chưa nhớ gì" in MemoryStore(tmp_path).render()


def test_render_dem_dung_ban_ghi_va_su_kien_hieu_luc(tmp_path):
    s = MemoryStore(tmp_path)
    cu = s.add(KIND_CONG_CU, "a", "b")
    s.supersede(cu.id, "c")
    assert "1 sự kiện đang hiệu lực / 2 bản ghi" in s.render()


# ═══════════════════════════════════════════════════════ sổ tay lỗi ═══


LOI_1 = ("/Users/v/du-an/build/motor.c:42:7: error: 'TIMER_TOP' undeclared "
         "(first use in this function)")
LOI_2 = ("/home/khac/kho/src/servo.c:187:3: error: 'TIMER_TOP' undeclared "
         "(first use in this function)")


def test_cung_loi_khac_duong_dan_va_so_dong_thi_cung_van_tay():
    """Tra theo chuỗi nguyên văn thì tỉ lệ trúng gần bằng không."""
    assert signature(LOI_1) == signature(LOI_2)


def test_loi_khac_han_thi_khac_van_tay():
    assert signature(LOI_1) != signature("undefined reference to `main'")


def test_chuan_hoa_giu_lai_tu_mang_nghia():
    c = normalise(LOI_1)
    assert "undeclared" in c and "error" in c
    assert "/users/v" not in c and "42" not in c


def test_chuan_hoa_bo_phien_ban_va_hex():
    c = normalise("libfoo 2.14.3 not found at 0x7ffee4")
    assert "2.14.3" not in c and "0x7ffee4" not in c
    assert "not found" in c


def test_van_tay_chuoi_rong_la_rong():
    assert signature("   ") == ""


def test_ghi_va_tra_lai_duoc(tmp_path):
    p = Playbook(tmp_path)
    p.record(LOI_1, "thêm #include <config.h>", context="cổng compile")
    ds = p.lookup(LOI_2)
    assert len(ds) == 1
    assert ds[0].fix == "thêm #include <config.h>"


def test_ghi_them_lan_thu_khong_sua_dong_cu(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách A")
    truoc = _so_dong(p)
    p.mark(m.signature, worked=False)
    p.mark(m.signature, worked=True)

    assert _so_dong(p) == truoc + 2, "append-only: số dòng chỉ được tăng"
    gop = p.get(m.signature)
    assert (gop.worked, gop.failed) == (2, 1)


def test_danh_dau_muc_khong_co_thi_bao_loi(tmp_path):
    with pytest.raises(KeyError):
        Playbook(tmp_path).mark("e-khong-co", worked=True)


def test_cach_sua_moi_nhat_thang(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách cũ")
    p.mark(m.signature, worked=True, fix="cách mới")
    assert p.get(m.signature).fix == "cách mới"


def test_xep_theo_ti_le_trung_khong_theo_thoi_gian(tmp_path):
    p = Playbook(tmp_path)
    p.record("error: permission denied opening /a/b", "chạy với sudo")
    p.record("error: permission denied opening /c/d", "sửa quyền thư mục")
    xau = p.all()[0].signature
    for _ in range(4):
        p.mark(xau, worked=False)

    ds = p.lookup("error: permission denied opening /x/y")
    assert ds[0].success_rate >= ds[-1].success_rate


def test_mot_lan_trung_khong_nhay_len_100_phan_tram(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách A")
    assert p.get(m.signature).success_rate < 1.0


def test_nhieu_lan_trung_xep_tren_it_lan_trung(tmp_path):
    p = Playbook(tmp_path)
    it = PlaybookEntry(signature="e-1", symptom="x", fix="f", worked=1)
    nhieu = PlaybookEntry(signature="e-2", symptom="x", fix="f", worked=20)
    assert nhieu.success_rate > it.success_rate


def test_khop_gan_dung_khi_khong_khop_van_tay(tmp_path):
    p = Playbook(tmp_path)
    p.record("ld: undefined reference to `phep_nhan' in module x", "khai báo hàm")
    ds = p.lookup("ld: undefined reference to `phep_nhan' in module y at line 9")
    assert ds and ds[0].fix == "khai báo hàm"


def test_loi_khong_lien_quan_thi_khong_tra_bua(tmp_path):
    p = Playbook(tmp_path)
    p.record("ld: undefined reference to `x'", "khai báo hàm")
    assert p.lookup("network is unreachable, could not connect") == []


def test_so_tay_rong_thi_tra_rong(tmp_path):
    assert Playbook(tmp_path).lookup(LOI_1) == []
    assert Playbook(tmp_path).hint(LOI_1) == ""


def test_goi_y_noi_ro_muc_tin_cay_va_khong_cho_bo_qua_cong(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "thêm include")
    p.mark(m.signature, worked=False)
    g = p.hint(LOI_2)
    assert "1 lần trúng / 1 lần trượt" in g
    assert "GỢI Ý" in g and "qua đủ cổng" in g


def test_muc_chua_tung_trung_la_gia_dinh(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách A", worked=False)
    assert p.get(m.signature).confidence_level == GIA_DINH


def test_muc_da_trung_la_suy_ra_khong_phai_da_kiem(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách A")
    assert p.get(m.signature).confidence_level == SUY_RA


def test_tran_so_goi_y_duoc_ton_trong(tmp_path):
    p = Playbook(tmp_path)
    for i in range(6):
        p.record(f"error: permission denied opening /a/{i}", f"cách {i}")
    assert len(p.lookup("error: permission denied opening /z/z", limit=2)) <= 2


def test_ghi_loi_rong_bi_tu_choi(tmp_path):
    with pytest.raises(ValueError):
        Playbook(tmp_path).record("   ", "cách nào đó")


def test_so_tay_rong_van_render_duoc(tmp_path):
    assert "chưa ghi lỗi nào" in Playbook(tmp_path).render()


def test_render_dem_dung_ti_le(tmp_path):
    p = Playbook(tmp_path)
    m = p.record(LOI_1, "cách A")
    p.mark(m.signature, worked=False)
    assert "1/2 lần áp dụng thành công" in p.render()


def test_nguon_web_duoc_giu_lai_trong_muc(tmp_path):
    """Cách sửa tra từ web phải mang theo địa chỉ, nếu không nó thành lời đồn."""
    p = Playbook(tmp_path)
    p.record(LOI_1, "cách A", source_url="https://example.com/issue/1")
    assert "https://example.com/issue/1" in p.hint(LOI_2)
