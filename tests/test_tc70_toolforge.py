"""TC-70 — xưởng công cụ: Agent mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ.

Bốn bất biến bài này canh:

* **Ba cổng, không cổng nào bỏ được.** Cấu tạo → an toàn → chạy thử.
* **Duyệt chỉ đi từ ``verified``.** Không có đường tắt từ ``proposed``.
* **Chưa duyệt thì không có đường chạy.**
* **Cổng an toàn quét theo cây cú pháp, không theo chuỗi con.** Một cổng hay
  báo nhầm sớm muộn cũng bị tắt đi, và lúc ấy nó không bảo vệ được gì nữa.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA
from eaa.toolforge import (
    CAU_TRUC_CAM,
    DA_DUYET,
    DA_KIEM_THU,
    DE_XUAT,
    MAX_DONG_MA,
    ForgeError,
    ForgedTool,
    ToolForge,
    ToolRegistry,
    check_safety,
    check_structure,
    run_tests,
    verify,
)

TOT = '''"""Đếm dòng không rỗng."""
MO_TA = "Đếm số dòng không rỗng trong một chuỗi"
SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


def run(text: str = "") -> str:
    return str(len([d for d in text.splitlines() if d.strip()]))


def test_dem_binh_thuong():
    assert run(text="a\\nb") == "2"


def test_dong_rong_khong_tinh():
    assert run(text="a\\n\\n\\nb") == "2"
'''


def _kho(tmp_path) -> ToolRegistry:
    return ToolRegistry(tmp_path)


def _luu(tmp_path, code=TOT, name="dem_dong", status=DE_XUAT) -> ToolRegistry:
    kho = _kho(tmp_path)
    kho.save(ForgedTool(name=name, purpose="đếm dòng", code=code, status=status,
                        schema={"type": "object", "properties": {"text": {}}}))
    return kho


# ══════════════════════════════════════════════ cổng 1 — cấu tạo ═══


def test_ma_du_bon_thu_thi_qua_cong_cau_tao():
    assert check_structure(TOT).passed is True


@pytest.mark.parametrize("doi,thanh,thieu", [
    # Đổi TÊN chứ không xóa dòng: xóa dòng ``def`` để lại thân hàm mồ côi, và
    # bài test khi ấy kiểm lỗi cú pháp chứ không kiểm cổng cấu tạo.
    ("def run(", "def chay(", "hàm run()"),
    ("SCHEMA =", "LUOC_DO =", "SCHEMA"),
    ("MO_TA =", "MOTA =", "MO_TA"),
    ("def test_dem_binh_thuong", "def kiem_dem_binh_thuong", "test_"),
])
def test_thieu_mot_thu_thi_khong_phai_cong_cu(doi, thanh, thieu):
    hong = TOT.replace(doi, thanh).replace(
        "def test_dong_rong_khong_tinh", "def kiem_dong_rong"
        if thieu == "test_" else "def test_dong_rong_khong_tinh")
    kq = check_structure(hong)
    assert kq.passed is False, kq.detail
    assert thieu in kq.detail


def test_ma_sai_cu_phap_bao_ro():
    kq = check_structure("def run(:\n  pass")
    assert kq.passed is False and "không phân tích được" in kq.detail


def test_ma_qua_dai_thi_no_la_module_khong_phai_cong_cu():
    dai = TOT + "\n" + "\n".join(f"# dòng {i}" for i in range(MAX_DONG_MA))
    kq = check_structure(dai)
    assert kq.passed is False
    assert "module" in kq.detail


# ══════════════════════════════════════════════ cổng 2 — an toàn ═══


def test_ma_sach_qua_cong_an_toan():
    assert check_safety(TOT).passed is True


def test_re_compile_KHONG_bi_chan():
    """Quét chuỗi con sẽ chặn cấu trúc hợp lệ phổ biến nhất của loại công cụ này."""
    ma = TOT + '\nimport re\n_M = re.compile(r"\\d+")\n'
    assert check_safety(ma).passed is True


def test_chu_trong_chu_thich_KHONG_bi_chan():
    ma = TOT + "\n# công cụ này không dùng socket, không dùng subprocess\n"
    assert check_safety(ma).passed is True


def test_ten_bien_trung_tu_cam_KHONG_bi_chan():
    ma = TOT + "\nsocket_path = '/tmp/x'\ndef helper():\n    return socket_path\n"
    assert check_safety(ma).passed is True


@pytest.mark.parametrize("ma_xau", [
    "eval('1+1')",
    "exec('x=1')",
    "compile('x', '<s>', 'exec')",
    "__import__('os')",
    "input('nhập: ')",
])
def test_ham_cam_bi_chan(ma_xau):
    kq = check_safety(TOT + f"\ndef them():\n    return {ma_xau}\n")
    assert kq.passed is False and "bị cấm" in kq.detail


@pytest.mark.parametrize("ma_xau", [
    "import os\ndef them():\n    os.system('rm -rf /')",
    "import os\ndef them():\n    os.popen('ls')",
    "import shutil\ndef them():\n    shutil.rmtree('/')",
    "import os\ndef them():\n    os.remove('/x')",
])
def test_goi_qua_thuoc_tinh_bi_chan(ma_xau):
    assert check_safety(TOT + "\n" + ma_xau).passed is False


@pytest.mark.parametrize("nhap", [
    "import socket",
    "import subprocess",
    "import ctypes",
    "from urllib.request import urlopen",
    "from subprocess import run as chay",
    "import requests",
    "import pickle",
])
def test_module_cam_bi_chan_o_tang_import(nhap):
    """Nhập được module thì mọi hàm trong nó đều gọi được."""
    kq = check_safety(nhap + "\n" + TOT)
    assert kq.passed is False


def test_khoa_nhung_thang_vao_ma_bi_chan():
    kq = check_safety(TOT + '\nAPI_KEY = "sk-abcdefghijklmnop"\n')
    assert kq.passed is False and "NFR-06" in kq.detail


def test_ly_do_cam_duoc_neu_ra_chu_khong_chi_bao_cam():
    kq = check_safety(TOT + "\nimport socket\n")
    assert "eaa/web.py" in kq.detail


def test_moi_cau_truc_cam_deu_co_ly_do():
    assert all(ly.strip() for ly in CAU_TRUC_CAM.values())


# ═══════════════════════════════════════════ cổng 3 — chạy thử ═══


def test_test_dat_thi_cong_qua(tmp_path):
    kq = run_tests(TOT, workdir=tmp_path / "w")
    assert kq.passed is True and "DAT 2" in kq.detail


def test_test_truot_thi_cong_khong_qua(tmp_path):
    xau = TOT.replace('assert run(text="a\\nb") == "2"', 'assert run(text="a\\nb") == "99"')
    kq = run_tests(xau, workdir=tmp_path / "w")
    assert kq.passed is False


def test_chay_thu_khong_co_mang(tmp_path):
    """Lớp thứ hai của cổng an toàn, ở tầng CHẠY."""
    ma = TOT + '''

def test_mang_bi_tat():
    import os
    assert os.environ.get("EAA_NO_NET") == "1"
'''
    assert run_tests(ma, workdir=tmp_path / "w").passed is True


def test_chay_thu_khong_thay_khoa_api(tmp_path, monkeypatch):
    monkeypatch.setenv("EAA_LLM_KEY", "sk-that-su-bi-mat")
    ma = TOT + '''

def test_khong_co_khoa():
    import os
    assert "EAA_LLM_KEY" not in os.environ
'''
    assert run_tests(ma, workdir=tmp_path / "w").passed is True


def test_cong_cu_treo_thi_bi_cat_theo_han_gio(tmp_path):
    treo = TOT + '''

def test_treo():
    while True:
        pass
'''
    kq = run_tests(treo, workdir=tmp_path / "w", timeout_s=1.5)
    assert kq.passed is False and "treo" in kq.detail


def test_chay_thu_o_thu_muc_rieng_khong_dung_vao_kho(tmp_path):
    w = tmp_path / "w"
    run_tests(TOT, workdir=w)
    assert (w / "cong_cu_thu.py").is_file()


# ══════════════════════════════════════ ba cổng chạy theo thứ tự ═══


def test_truot_cong_1_thi_khong_chay_cong_2_va_3(tmp_path):
    bc = verify("def run(): pass", workdir=tmp_path, name="x")
    assert len(bc.checks) == 1 and bc.passed is False


def test_truot_cong_2_thi_KHONG_chay_ma(tmp_path):
    """Chạy một đoạn mã vừa trượt cổng an toàn là đúng thứ cổng ấy sinh ra để ngăn."""
    xau = TOT + "\nimport socket\n"
    bc = verify(xau, workdir=tmp_path, name="x")
    assert len(bc.checks) == 2 and bc.passed is False
    assert not (tmp_path / "cong_cu_thu.py").exists()


def test_qua_ca_ba_cong(tmp_path):
    bc = verify(TOT, workdir=tmp_path, name="x")
    assert len(bc.checks) == 3 and bc.passed is True
    assert "chờ người duyệt" in bc.render()


# ═══════════════════════════════════════════════ sổ đăng ký ═══


def test_luu_va_doc_lai_ca_ma_lan_so(tmp_path):
    kho = _luu(tmp_path)
    t = kho.get("dem_dong")
    assert t.code == TOT and t.status == DE_XUAT
    assert kho.code_path("dem_dong").is_file()


def test_khong_duyet_thang_tu_de_xuat(tmp_path):
    """Duyệt một công cụ chưa từng chạy thử thì chữ 'duyệt' không nói lên điều gì."""
    kho = _luu(tmp_path)
    with pytest.raises(ForgeError, match="verify"):
        kho.approve("dem_dong", by="vu-tri-cong")


def test_duyet_duoc_tu_verified_va_ghi_ai_duyet(tmp_path):
    kho = _luu(tmp_path, status=DA_KIEM_THU)
    t = kho.approve("dem_dong", by="vu-tri-cong")
    assert t.status == DA_DUYET and t.approved_by == "vu-tri-cong"
    assert t.approved_at


def test_duyet_khong_ten_bi_tu_choi(tmp_path):
    kho = _luu(tmp_path, status=DA_KIEM_THU)
    with pytest.raises(ForgeError, match="ai duyệt"):
        kho.approve("dem_dong", by="  ")


def test_duyet_cong_cu_khong_co_bao_loi(tmp_path):
    with pytest.raises(ForgeError, match="không có công cụ"):
        _kho(tmp_path).approve("khong-co", by="x")


def test_chi_cong_cu_da_duyet_moi_hien_trong_danh_sach_chay_duoc(tmp_path):
    kho = _luu(tmp_path)
    assert kho.approved() == []
    kho.set_status("dem_dong", DA_KIEM_THU)
    assert kho.approved() == []
    kho.approve("dem_dong", by="x")
    assert [t.name for t in kho.approved()] == ["dem_dong"]


def test_muc_tin_cay_theo_trang_thai(tmp_path):
    kho = _luu(tmp_path)
    assert kho.get("dem_dong").confidence_level == GIA_DINH
    kho.set_status("dem_dong", DA_KIEM_THU)
    assert kho.get("dem_dong").confidence_level == SUY_RA
    kho.approve("dem_dong", by="x")
    assert kho.get("dem_dong").confidence_level == DA_KIEM


def test_so_ghi_ro_quy_tac_mot_chieu_trong_chinh_tep(tmp_path):
    kho = _luu(tmp_path)
    noi_dung = kho.path.read_text(encoding="utf-8")
    assert "KHÔNG nằm trong danh mục Agent tự gọi" in noi_dung


# ═══════════════════════════════════════════════════ xưởng ═══


def test_verify_dat_thi_len_verified(tmp_path):
    kho = _luu(tmp_path)
    bc = ToolForge(registry=kho).verify("dem_dong")
    assert bc.passed is True
    assert kho.get("dem_dong").status == DA_KIEM_THU
    assert kho.get("dem_dong").verified_at


def test_verify_truot_thi_o_lai_de_xuat_va_ghi_ly_do(tmp_path):
    kho = _luu(tmp_path, code=TOT + "\nimport socket\n")
    bc = ToolForge(registry=kho).verify("dem_dong")
    assert bc.passed is False
    t = kho.get("dem_dong")
    assert t.status == DE_XUAT and "socket" in t.note


def test_khong_verify_lai_cong_cu_da_duyet(tmp_path):
    kho = _luu(tmp_path, status=DA_KIEM_THU)
    kho.approve("dem_dong", by="x")
    with pytest.raises(ForgeError, match="đã được duyệt"):
        ToolForge(registry=kho).verify("dem_dong")


def test_chua_duyet_thi_khong_co_duong_chay(tmp_path):
    kho = _luu(tmp_path)
    with pytest.raises(ForgeError, match="chưa được duyệt"):
        ToolForge(registry=kho).run("dem_dong", {"text": "a\nb"})


def test_da_duyet_thi_chay_duoc_va_tra_ve_van_ban(tmp_path):
    kho = _luu(tmp_path, status=DA_KIEM_THU)
    kho.approve("dem_dong", by="x")
    assert ToolForge(registry=kho).run("dem_dong", {"text": "a\n\nb"}) == "2"


def test_cong_cu_chay_loi_khong_lam_sap_agent(tmp_path):
    ma = TOT.replace("return str(len(", "return str(1 // 0 + len(")
    kho = _luu(tmp_path, code=ma, status=DA_KIEM_THU)
    kho.approve("dem_dong", by="x")
    with pytest.raises(ForgeError, match="ZeroDivisionError"):
        ToolForge(registry=kho).run("dem_dong", {"text": "a"})


def test_chay_cong_cu_khong_co_trong_so(tmp_path):
    with pytest.raises(ForgeError, match="không có công cụ"):
        ToolForge(registry=_kho(tmp_path)).run("khong-co")


# ═══════════════════════════════════════════ đặt hàng mô hình ═══


class _Llm:
    provider, model = "gia", "mo-hinh-gia"

    def __init__(self, du_lieu):
        self.du_lieu = du_lieu

    def count_tokens(self, text):
        return len(text) // 4

    def complete(self, prompt):
        return "```json\n" + json.dumps(self.du_lieu) + "\n```"


def test_dat_hang_luu_thanh_de_xuat(tmp_path):
    kho = _kho(tmp_path)
    llm = _Llm({"name": "dem_dong", "purpose": "đếm dòng", "schema": {}, "code": TOT})
    t = ToolForge(registry=kho, llm=llm).design("đếm dòng không rỗng")
    assert t.status == DE_XUAT and t.created_by == "mo-hinh-gia"
    assert kho.get("dem_dong").code == TOT


@pytest.mark.parametrize("ten", ["", "Ten Hoa", "a", "có-dấu", "1_bat_dau_bang_so"])
def test_ten_cong_cu_khong_hop_le_bi_tu_choi(tmp_path, ten):
    llm = _Llm({"name": ten, "purpose": "x", "code": TOT})
    with pytest.raises(ForgeError, match="không hợp lệ"):
        ToolForge(registry=_kho(tmp_path), llm=llm).design("x")


def test_de_xuat_khong_co_ma_bi_tu_choi(tmp_path):
    llm = _Llm({"name": "cong_cu_x", "purpose": "x", "code": "   "})
    with pytest.raises(ForgeError, match="không có mã"):
        ToolForge(registry=_kho(tmp_path), llm=llm).design("x")


def test_chua_noi_mo_hinh_thi_noi_ro(tmp_path):
    with pytest.raises(ForgeError, match="mô hình nền"):
        ToolForge(registry=_kho(tmp_path), llm=None).design("x")


def test_vong_doi_day_du_tu_dat_hang_toi_chay(tmp_path):
    """Đường đi đầy đủ: đặt hàng → ba cổng → người duyệt → chạy."""
    kho = _kho(tmp_path)
    xuong = ToolForge(registry=kho, llm=_Llm(
        {"name": "dem_dong", "purpose": "đếm dòng", "schema": {}, "code": TOT}))

    t = xuong.design("đếm dòng không rỗng")
    assert t.status == DE_XUAT
    assert xuong.verify("dem_dong").passed is True
    with pytest.raises(ForgeError):
        xuong.run("dem_dong", {"text": "a"})     # verified vẫn chưa chạy được
    kho.approve("dem_dong", by="vu-tri-cong")
    assert xuong.run("dem_dong", {"text": "a\nb\n\nc"}) == "3"


# ═════════════════════════ kiểm tham số trước khi gọi ═════════════════════


LUOC_DO = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "Nội dung cần xử lý"},
        "lan": {"type": "integer"},
        "hoa": {"type": "boolean"},
        "muc": {"type": "array"},
    },
    "required": ["text"],
}


def test_tham_so_dung_thi_khong_bao_loi():
    from eaa.toolforge import check_arguments

    assert check_arguments(LUOC_DO, {"text": "a", "lan": 2, "hoa": True, "muc": [1]}) == []


def test_thieu_tham_so_bat_buoc_duoc_neu_ten_va_mo_ta():
    from eaa.toolforge import check_arguments

    loi = check_arguments(LUOC_DO, {"lan": 1})
    assert len(loi) == 1
    assert "'text'" in loi[0] and "Nội dung cần xử lý" in loi[0]


def test_sai_kieu_noi_ro_dang_nhan_kieu_gi():
    """AttributeError nội bộ không cho bên gọi biết mình sai ở đâu."""
    from eaa.toolforge import check_arguments

    loi = check_arguments(LUOC_DO, {"text": ["a", "b"]})
    assert "phải là string" in loi[0] and "đang nhận list" in loi[0]


def test_boolean_khong_troi_vao_cho_doi_so():
    """bool là lớp con của int trong Python — một cờ không được thành một con số."""
    from eaa.toolforge import check_arguments

    loi = check_arguments(LUOC_DO, {"text": "a", "lan": True})
    assert loi and "đang nhận boolean" in loi[0]


def test_ten_tham_so_la_duoc_neu_kem_danh_sach_ten_dung():
    from eaa.toolforge import check_arguments

    loi = check_arguments(LUOC_DO, {"text": "a", "tên_sai": 1})
    assert "không có trong lược đồ" in loi[0]
    assert "text" in loi[0] and "lan" in loi[0]


def test_luoc_do_rong_thi_khong_kiem_gi():
    from eaa.toolforge import check_arguments

    assert check_arguments({}, {"bat_ky": 1}) == []
    assert check_arguments({"type": "object"}, {"bat_ky": 1}) == []


def test_chay_voi_tham_so_sai_bi_chan_truoc_khi_nap_ma(tmp_path):
    kho = _luu(tmp_path, status=DA_KIEM_THU)
    kho.approve("dem_dong", by="x")
    # Sổ dựng ở _luu khai 'text' không kiểu, nên thêm kiểu để kiểm cho chặt.
    kho.set_status("dem_dong", DA_DUYET, schema={
        "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})

    with pytest.raises(ForgeError, match="không khớp lược đồ"):
        ToolForge(registry=kho).run("dem_dong", {"text": 123})
    with pytest.raises(ForgeError, match="thiếu 'text'"):
        ToolForge(registry=kho).run("dem_dong", {})
    assert ToolForge(registry=kho).run("dem_dong", {"text": "a\nb"}) == "2"
