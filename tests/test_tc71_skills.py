"""TC-71 — kỹ năng: GỘP quyền đã có, KHÔNG cấp quyền mới.

Bất biến quan trọng nhất bài này canh nằm ở cổng 1. Một tầng "kỹ năng" là chỗ
dễ phá hỏng cả sản phẩm nhất: đặt tên một kỹ năng là "chốt xong module", nhét
``gate approve`` vào giữa, và từ đó Agent duyệt gate được — bằng đúng một dòng
YAML không ai đọc kỹ.

Nên bài này kiểm cổng ấy ở CẢ HAI thời điểm: lúc duyệt, và lúc chạy. Sổ là một
tệp YAML sửa tay được, nên một kỹ năng đã duyệt rồi bị chèn thêm bước vẫn mang
trạng thái ``approved``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA
from eaa.skills import (
    DA_DUYET,
    DA_KIEM_THU,
    DE_XUAT,
    SO_BUOC_TOI_DA,
    Skill,
    SkillError,
    SkillRegistry,
    SkillStep,
    mine,
    verify_skill,
)


def _kn(*argv_list, name="xem_nhanh", params=(), **kw) -> Skill:
    return Skill(
        name=name,
        purpose="thử",
        steps=tuple(SkillStep(argv=tuple(a.split())) for a in argv_list),
        params=tuple(params),
        **kw,
    )


def _kho(tmp_path, ky_nang=None) -> SkillRegistry:
    kho = SkillRegistry(tmp_path)
    if ky_nang is not None:
        kho.save(ky_nang)
    return kho


# ═══════════════════════════════ cổng 1 — quyền ═══════════════════════════


def test_moi_buoc_trong_danh_muc_thi_qua():
    kq = verify_skill(_kn("status", "plan list", "sources need"))
    assert kq.passed is True
    assert kq.checks[0].gate == "quyền"


@pytest.mark.parametrize("lenh_cam", [
    "gate approve G3",
    "flash --module drv_i2c",
    "doctor --fix",
    "tune drv_i2c",
    "rollback",
    "gen drv_i2c",
    "tool approve x",
])
def test_buoc_ngoai_danh_muc_bi_chan(lenh_cam):
    """Đây là cổng quan trọng nhất của cả module."""
    kq = verify_skill(_kn("status", lenh_cam))
    assert kq.passed is False
    assert "ngoài danh mục" in kq.checks[0].detail


def test_ly_do_ngoai_danh_muc_duoc_nhac_lai_chu_khong_chi_bao_cam():
    kq = verify_skill(_kn("gate approve G1"))
    assert "gate là của con người" in kq.checks[0].detail
    assert "GỘP quyền đã có" in kq.checks[0].detail or "gộp quyền đã có" in kq.checks[0].detail


def test_ky_nang_rong_bi_tu_choi():
    assert verify_skill(_kn()).passed is False


def test_qua_nhieu_buoc_bi_tu_choi():
    kq = verify_skill(_kn(*(["status"] * (SO_BUOC_TOI_DA + 1))))
    assert kq.passed is False
    assert "quy trình thì có gate" in kq.checks[0].detail


def test_dung_tran_so_buoc_van_qua():
    assert verify_skill(_kn(*(["status"] * SO_BUOC_TOI_DA))).passed is True


# ═══════════════════════════ cổng 2 — tham số ═══════════════════════════


def test_cho_giu_khop_khai_bao_thi_qua():
    kq = verify_skill(_kn("resolve {module}", "sources pages {module}", params=["module"]))
    assert kq.passed is True


def test_dung_tham_so_ma_khong_khai_thi_truot():
    kq = verify_skill(_kn("resolve {module}", params=[]))
    assert kq.passed is False
    assert "không khai" in kq.checks[1].detail


def test_khai_tham_so_ma_khong_dung_thi_truot():
    """Một tham số không ai dùng là một tham số người gọi sẽ điền nhầm chỗ."""
    kq = verify_skill(_kn("status", params=["module"]))
    assert kq.passed is False
    assert "không bước nào dùng" in kq.checks[1].detail


# ═══════════════════════════ cổng 3 — chạy khô ═══════════════════════════


def test_chay_kho_dung_du_chuoi_lenh_cuoi_cung():
    kq = verify_skill(_kn("resolve {module}", "plan list", params=["module"]),
                      sample={"module": "drv_i2c"})
    assert kq.passed is True
    assert kq.preview == (("resolve", "drv_i2c"), ("plan", "list"))
    assert "eaa resolve drv_i2c" in kq.render()


def test_khong_co_mau_thi_dung_cho_giu_de_nguoi_van_thay_duoc():
    kq = verify_skill(_kn("resolve {module}", params=["module"]))
    assert kq.preview == (("resolve", "<module>"),)


def test_truot_cong_1_thi_khong_chay_cong_2_va_3():
    assert len(verify_skill(_kn("gate approve G1")).checks) == 1


def test_truot_cong_2_thi_khong_chay_cong_3():
    assert len(verify_skill(_kn("resolve {x}", params=[])).checks) == 2


# ═══════════════════════════════ sổ đăng ký ═══════════════════════════════


def test_luu_va_doc_lai_khong_mat_gi(tmp_path):
    goc = _kn("status", "plan list", name="xem_nhanh")
    kho = _kho(tmp_path, goc)
    lai = kho.get("xem_nhanh")
    assert lai.steps == goc.steps and lai.purpose == goc.purpose


def test_khong_duyet_thang_tu_de_xuat(tmp_path):
    kho = _kho(tmp_path, _kn("status"))
    with pytest.raises(SkillError, match="verify"):
        kho.approve("xem_nhanh", by="vu-tri-cong")


def test_duyet_duoc_tu_verified(tmp_path):
    kho = _kho(tmp_path, _kn("status", "plan list"))
    assert kho.verify("xem_nhanh").passed is True
    s = kho.approve("xem_nhanh", by="vu-tri-cong")
    assert s.status == DA_DUYET and s.approved_by == "vu-tri-cong"


def test_verify_truot_thi_o_lai_de_xuat_va_ghi_ly_do(tmp_path):
    kho = _kho(tmp_path, _kn("status", "gate approve G1"))
    assert kho.verify("xem_nhanh").passed is False
    s = kho.get("xem_nhanh")
    assert s.status == DE_XUAT and "ngoài danh mục" in s.note


def test_muc_tin_cay_theo_trang_thai(tmp_path):
    kho = _kho(tmp_path, _kn("status", "plan list"))
    assert kho.get("xem_nhanh").confidence_level == GIA_DINH
    kho.verify("xem_nhanh")
    assert kho.get("xem_nhanh").confidence_level == SUY_RA
    kho.approve("xem_nhanh", by="x")
    assert kho.get("xem_nhanh").confidence_level == DA_KIEM


def test_so_ghi_ro_bat_bien_trong_chinh_tep(tmp_path):
    kho = _kho(tmp_path, _kn("status"))
    assert "KHÔNG cấp quyền mới" in kho.path.read_text(encoding="utf-8")


# ═══════════════════════════════════ chạy ═══════════════════════════════════


def _runner(ket: dict[str, tuple[int, str]]):
    da_chay: list[tuple[str, ...]] = []

    def chay(argv):
        da_chay.append(tuple(argv))
        return ket.get(" ".join(argv), (0, "ok"))

    chay.da_chay = da_chay  # type: ignore[attr-defined]
    return chay


def _da_duyet(tmp_path, *argv_list, params=()):
    kho = _kho(tmp_path, _kn(*argv_list, params=params))
    kho.verify("xem_nhanh")
    kho.approve("xem_nhanh", by="x")
    return kho


def test_chua_duyet_thi_khong_chay_duoc(tmp_path):
    kho = _kho(tmp_path, _kn("status"))
    with pytest.raises(SkillError, match="chưa được duyệt"):
        kho.run("xem_nhanh", runner=_runner({}))
    kho.verify("xem_nhanh")
    with pytest.raises(SkillError, match="chưa được duyệt"):
        kho.run("xem_nhanh", runner=_runner({}))


def test_chay_dung_thu_tu_cac_buoc(tmp_path):
    kho = _da_duyet(tmp_path, "status", "plan list", "sources need")
    r = _runner({})
    lan = kho.run("xem_nhanh", runner=r)
    assert r.da_chay == [("status",), ("plan", "list"), ("sources", "need")]
    assert lan.ok is True


def test_dien_tham_so_vao_buoc(tmp_path):
    kho = _da_duyet(tmp_path, "resolve {module}", "sources pages {module}", params=["module"])
    r = _runner({})
    kho.run("xem_nhanh", {"module": "drv_i2c"}, runner=r)
    assert r.da_chay == [("resolve", "drv_i2c"), ("sources", "pages", "drv_i2c")]


def test_thieu_tham_so_thi_bao_ten_no(tmp_path):
    kho = _da_duyet(tmp_path, "resolve {module}", params=["module"])
    with pytest.raises(SkillError, match="module"):
        kho.run("xem_nhanh", {}, runner=_runner({}))


def test_dung_o_buoc_dau_tien_khong_dat(tmp_path):
    """Bước sau chạy trên kết quả của bước trước hỏng là chạy trên nền cát."""
    kho = _da_duyet(tmp_path, "status", "plan list", "sources need")
    # Mã 4 = lỗi môi trường. Mã 2 KHÔNG dùng ở đây: nó nghĩa là "đang chờ
    # người", một trạng thái của dự án chứ không phải lỗi của lệnh.
    r = _runner({"plan list": (4, "thiếu công cụ")})
    lan = kho.run("xem_nhanh", runner=r)
    assert r.da_chay == [("status",), ("plan", "list")]
    assert lan.ok is False and lan.stopped_at == "plan list"
    assert "nền cát" in lan.render()


def test_buoc_tuy_chon_hong_thi_van_di_tiep(tmp_path):
    kho = SkillRegistry(tmp_path)
    kho.save(Skill(
        name="xem_nhanh", purpose="thử",
        steps=(SkillStep(("status",)),
               SkillStep(("ledger", "list"), optional=True),
               SkillStep(("plan", "list"))),
    ))
    kho.verify("xem_nhanh")
    kho.approve("xem_nhanh", by="x")
    r = _runner({"ledger list": (2, "chưa có")})
    lan = kho.run("xem_nhanh", runner=r)
    assert len(r.da_chay) == 3
    assert lan.stopped_at == ""


def test_ky_nang_bi_sua_tay_sau_khi_duyet_van_bi_chan_luc_chay(tmp_path):
    """Sổ là một tệp YAML sửa tay được — cổng lúc duyệt không bảo vệ được lượt chạy."""
    kho = _da_duyet(tmp_path, "status")

    import yaml

    d = yaml.safe_load(kho.path.read_text(encoding="utf-8"))
    d["skills"][0]["steps"].append({"argv": ["gate", "approve", "G3"]})
    kho.path.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")

    assert kho.get("xem_nhanh").status == DA_DUYET   # trạng thái vẫn là đã duyệt
    with pytest.raises(SkillError, match="cổng quyền"):
        kho.run("xem_nhanh", runner=_runner({}))


def test_chay_ky_nang_khong_co_trong_so(tmp_path):
    with pytest.raises(SkillError, match="không có kỹ năng"):
        SkillRegistry(tmp_path).run("khong-co")


# ═════════════════════════ khai thác từ nhật ký ═════════════════════════


def _nhat_ky(tmp_path, *luot) -> Path:
    p = tmp_path / "chat_log.jsonl"
    p.write_text(
        "\n".join(json.dumps({"commands_run": list(l)}, ensure_ascii=False) for l in luot),
        encoding="utf-8",
    )
    return p


def test_chuoi_lap_du_nhieu_lan_thi_duoc_de_xuat(tmp_path):
    p = _nhat_ky(tmp_path,
                 ["status", "plan list", "sources need"],
                 ["status", "plan list", "sources need"],
                 ["ledger list"])
    ds = mine(p)
    assert ds and ds[0].commands == ("status", "plan list", "sources need")
    assert ds[0].count == 2


def test_chuoi_chi_xuat_hien_mot_lan_thi_khong_de_xuat(tmp_path):
    """Đề xuất cho việc chưa ai làm bao giờ là đoán."""
    p = _nhat_ky(tmp_path, ["status", "plan list"], ["ledger list", "deviations"])
    assert mine(p) == []


def test_chuoi_con_khong_lam_nhieu_hon_thi_bi_bo(tmp_path):
    """[a,b] lặp 3 lần và [a,b,c] cũng lặp 3 lần thì cái ngắn không thêm gì."""
    p = _nhat_ky(tmp_path, *[["status", "plan list", "sources need"]] * 3)
    ds = mine(p)
    assert len(ds) == 1
    assert len(ds[0].commands) == 3


def test_chuoi_con_lap_NHIEU_hon_thi_van_duoc_giu(tmp_path):
    p = _nhat_ky(tmp_path,
                 ["status", "plan list", "sources need"],
                 ["status", "plan list", "sources need"],
                 ["status", "plan list"])
    ds = mine(p)
    assert any(c.commands == ("status", "plan list") and c.count == 3 for c in ds)


def test_nhat_ky_chua_co_thi_tra_rong(tmp_path):
    assert mine(tmp_path / "khong-co.jsonl") == []


def test_dong_hong_khong_lam_sap(tmp_path):
    p = tmp_path / "chat_log.jsonl"
    p.write_text('{"commands_run": ["status", "plan list"]}\nkhong phai json\n'
                 '{"commands_run": ["status", "plan list"]}\n', encoding="utf-8")
    assert mine(p)[0].count == 2


def test_bien_de_xuat_thanh_ky_nang_qua_duoc_ba_cong(tmp_path):
    p = _nhat_ky(tmp_path, *[["status", "plan list"]] * 2)
    kn = mine(p)[0].to_skill(source="chat_log.jsonl")
    assert kn.status == DE_XUAT
    assert verify_skill(kn).passed is True
    assert kn.name == "status_plan"


def test_de_xuat_rut_ra_ghi_ro_nguon(tmp_path):
    p = _nhat_ky(tmp_path, *[["status", "plan list"]] * 2)
    kn = mine(p)[0].to_skill(source="chat_log.jsonl")
    assert "chat_log.jsonl" in kn.render()
    assert "lặp 2 lần" in kn.purpose


# ═══════ mã 2 là TRẠNG THÁI, không phải lỗi (đo được ở lần chạy thật) ═══════


def test_ma_2_khong_lam_dut_chuoi(tmp_path):
    """'Đang chờ người' là trạng thái của dự án, không phải lỗi của lệnh.

    Đo được ở kỹ năng đầu tiên viết thử: một chuỗi xem-xét hoàn toàn hợp lý
    đứt ngay bước một, chỉ vì dự án đang chờ duyệt một gate — đúng cái mà
    người dùng chạy kỹ năng ấy để tìm hiểu.
    """
    kho = _da_duyet(tmp_path, "focus x", "sources need", "ledger list")
    r = _runner({"focus x": (2, "còn 2 chặng")})
    lan = kho.run("xem_nhanh", runner=r)

    assert len(r.da_chay) == 3, "chuỗi phải chạy hết"
    assert lan.stopped_at == ""
    assert lan.ok is True
    assert len(lan.waiting) == 1
    assert "ĐANG CHỜ NGƯỜI" in lan.render()
    assert "⏸" in lan.render()


@pytest.mark.parametrize("ma", [1, 3, 4])
def test_ma_loi_that_thi_dut_chuoi(ma):
    """Mã 1 (lỗi lệnh), 3 (cạn lượt sửa), 4 (lỗi môi trường) thì dừng thật."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        kho = _da_duyet(Path(d), "status", "plan list")
        r = _runner({"status": (ma, "hỏng")})
        lan = kho.run("xem_nhanh", runner=r)
        assert len(r.da_chay) == 1
        assert lan.stopped_at == "status" and lan.ok is False


def test_ma_dung_chuoi_khong_chua_ma_2():
    from eaa.skills import MA_DUNG_CHUOI

    assert 2 not in MA_DUNG_CHUOI
    assert MA_DUNG_CHUOI == {1, 3, 4}


def test_buoc_tuy_chon_van_bo_qua_duoc_ca_loi_that(tmp_path):
    kho = SkillRegistry(tmp_path)
    kho.save(Skill(name="xem_nhanh", purpose="thử",
                   steps=(SkillStep(("status",), optional=True), SkillStep(("plan", "list"),))))
    kho.verify("xem_nhanh")
    kho.approve("xem_nhanh", by="x")
    r = _runner({"status": (4, "lỗi môi trường")})
    lan = kho.run("xem_nhanh", runner=r)
    assert len(r.da_chay) == 2 and lan.stopped_at == ""
