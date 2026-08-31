"""TC-84 — chỗ làm nháp phải sinh ra CHẠY ĐƯỢC, và nạp tài liệu phải qua kiểm nguồn.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-107.

Bốn lỗi tìm ra trong một lượt kiểm với bo thật, khi người dùng đưa một kit
thuộc họ MCU khác với dự án đang mở:

1. ``eaa scratch`` ghi ``mcu: "chưa xác định"`` — một chuỗi ở chỗ lược đồ đòi
   ánh xạ. Chỗ nháp **sinh ra đã hỏng**.
2. Lỗi ấy nổ thành ``ValueError`` trần, lọt qua mọi lớp bắt lỗi của CLI và ra
   tới người dùng dưới dạng traceback Python.
3. ``eaa scratch`` mặc định một Platform Pack cố định, nên bo họ khác nhận sai
   toolchain — **im lặng**.
4. ``eaa datasheet add`` chỉ nhận tệp cục bộ, nên tài liệu nhà sản xuất trên
   web phải tải bằng tay — **ngoài** ``eaa/web.py``, tức là không có phân hạng
   nguồn nào xảy ra.

Trong đó lỗi 3 và 4 nguy hiểm hơn 1 và 2: sập thì người ta sửa, còn một giá
trị sai mà im lặng thì mọi thứ dựng lên trên nó đều sai theo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eaa.scratch import ScratchError, chon_platform, create_scratch, packs_co_san


def _kho(tmp_path: Path, *packs: str) -> Path:
    for p in packs:
        (tmp_path / "packs" / p).mkdir(parents=True)
    return tmp_path


# ═════════════ chỗ nháp phải sinh ra ĐÚNG KIỂU mà kb.py đọc ═════════════


def test_ho_so_phan_cung_sinh_ra_dung_kieu(tmp_path):
    """``mcu`` phải là ánh xạ. Sai kiểu là chỗ nháp sinh ra đã hỏng."""
    goc = create_scratch(_kho(tmp_path, "pack_thu"), name="thu")
    d = yaml.safe_load((goc / "hardware_profile.yaml").read_text(encoding="utf-8"))
    assert isinstance(d["mcu"], dict)
    assert isinstance(d["pin_functions"], dict)
    assert isinstance(d["components"], list)


def test_kb_doc_duoc_ho_so_scratch_vua_sinh(tmp_path):
    """Bài canh thật: nạp bằng chính bộ đọc của sản phẩm, không tự kiểm kiểu."""
    from eaa.kb import HardwareProfile

    goc = create_scratch(_kho(tmp_path, "pack_thu"), name="thu")
    hp = HardwareProfile.load(goc / "hardware_profile.yaml")
    assert hp.mcu == {} and hp.components == [] and hp.peripherals == []


def test_dung_duoc_Knowledge_Graph_tu_ho_so_scratch(tmp_path):
    """Chỗ sập thật nằm ở đây — dựng graph là bước đầu của gần như mọi lệnh."""
    from eaa.graph import KnowledgeGraph
    from eaa.kb import DatasheetStore, HardwareProfile

    goc = create_scratch(_kho(tmp_path, "pack_thu"), name="thu")
    hp = HardwareProfile.load(goc / "hardware_profile.yaml")
    KnowledgeGraph.build(hp, DatasheetStore(goc / "datasheets"), modules=[])


# ═════════ sai kiểu phải thành lỗi MIỀN, không thành traceback ═════════


def _ho_so(tmp_path: Path, noi_dung: str) -> Path:
    p = tmp_path / "hardware_profile.yaml"
    p.write_text(noi_dung, encoding="utf-8")
    return p


def test_mcu_la_chuoi_thi_bao_LOI_MIEN_kem_ten_tep(tmp_path):
    """``dict("chuỗi")`` ném ValueError không nói tệp nào, trường nào, sửa sao."""
    from eaa.kb import HardwareProfile, KbError

    hp = HardwareProfile.load(_ho_so(tmp_path, "version: 1\nmcu: chưa xác định\n"))
    with pytest.raises(KbError) as exc:
        _ = hp.mcu
    tin = str(exc.value)
    assert "hardware_profile.yaml" in tin, "phải nêu tệp nào"
    assert "mcu" in tin, "phải nêu trường nào"
    assert "ánh xạ" in tin, "phải nói kiểu đúng là gì"
    assert "{}" in tin, "phải chỉ cách để trống"


def test_danh_sach_sai_kieu_cung_bao_loi_mien(tmp_path):
    from eaa.kb import HardwareProfile, KbError

    hp = HardwareProfile.load(_ho_so(tmp_path, "version: 1\ncomponents: chưa có\n"))
    with pytest.raises(KbError, match="danh sách"):
        _ = hp.components


def test_truong_vang_mat_van_tra_ve_RONG(tmp_path):
    """Thiếu khác sai kiểu — thiếu là bình thường, không được ném."""
    from eaa.kb import HardwareProfile

    hp = HardwareProfile.load(_ho_so(tmp_path, "version: 1\n"))
    assert hp.mcu == {} and hp.components == [] and hp.pin_map == {}


# ═════════════ chọn Platform Pack: không mặc định bừa ═════════════


def test_suy_platform_tu_ten_cho_nhap(tmp_path):
    kho = _kho(tmp_path, "pack_mot", "pack_hai")
    ten, ly_do = chon_platform(kho, "bo_pack_mot_kit")
    assert ten == "pack_mot"
    assert "suy từ tên" in ly_do and "GIẢ ĐỊNH" in ly_do, \
        "suy đoán phải tự khai là suy đoán"


def test_khong_suy_duoc_thi_HOI_chu_khong_mac_dinh(tmp_path):
    """Mặc định bừa một pack là sai trình biên dịch, và sai một cách im lặng."""
    kho = _kho(tmp_path, "pack_mot", "pack_hai")
    with pytest.raises(ScratchError) as exc:
        chon_platform(kho, "cho_nhap_khong_ten_ho")
    tin = str(exc.value)
    assert "--platform" in tin, "phải chỉ cách nêu rõ"
    assert "pack_mot" in tin and "pack_hai" in tin, "phải liệt kê cái đang có"


def test_chi_mot_pack_thi_dung_luon(tmp_path):
    ten, ly_do = chon_platform(_kho(tmp_path, "pack_duy_nhat"), "gì đó")
    assert ten == "pack_duy_nhat"
    assert "chỉ có một" in ly_do


def test_ten_khop_nhieu_pack_thi_HOI(tmp_path):
    kho = _kho(tmp_path, "abc", "abcd")
    with pytest.raises(ScratchError, match="khớp nhiều"):
        chon_platform(kho, "bo_abcd_kit")


def test_neu_ro_platform_thi_thang_moi_suy_doan(tmp_path):
    kho = _kho(tmp_path, "pack_mot", "pack_hai")
    ten, ly_do = chon_platform(kho, "bo_pack_mot_kit", "pack_hai")
    assert ten == "pack_hai" and "--platform" in ly_do


def test_constraints_GHI_LAI_vi_sao_chon_pack_ay(tmp_path):
    """Chọn sai pack chỉ lộ ra ở cổng biên dịch — phải đọc lại được lý do."""
    goc = create_scratch(_kho(tmp_path, "pack_thu"), name="thu")
    van_ban = (goc / "constraints.yaml").read_text(encoding="utf-8")
    assert "Platform Pack chọn được vì" in van_ban
    assert "Sai pack là sai trình biên dịch" in van_ban
    assert yaml.safe_load(van_ban)["platform"] == "pack_thu"


# ═══════ nạp tài liệu từ URL: phải đi qua lớp phân hạng nguồn ═══════


class _Doc:
    def __init__(self, url, tier):
        self.url, self.tier = url, tier


def test_URL_chinh_chu_thi_tai_ve_va_dung_tep(tmp_path, monkeypatch):
    from eaa import cli
    from eaa.web import CHINH_CHU

    du_an = tmp_path / "du_an"
    (du_an / "datasheets").mkdir(parents=True)
    monkeypatch.setattr(
        cli, "WebFetcher", None, raising=False)

    import eaa.web as web

    monkeypatch.setattr(
        web.WebFetcher, "fetch_binary",
        lambda self, url, **k: (b"%PDF-1.7\n", _Doc(url, CHINH_CHU)))

    tep = cli._tep_tai_lieu("https://nha-san-xuat.example/um.pdf", du_an)
    assert tep.is_file() and tep.read_bytes().startswith(b"%PDF-")
    assert tep.name == "um.pdf"
    assert "_taive" in str(tep), "tệp tải về phải nằm riêng, không lẫn tệp người đưa"


def test_URL_hang_MO_bi_TU_CHOI(tmp_path, monkeypatch):
    """Cả hệ hai hạng nguồn vô nghĩa nếu con đường nạp tri thức đi vòng qua nó."""
    import eaa.web as web
    from eaa import cli
    from eaa.web import MO

    du_an = tmp_path / "du_an"
    (du_an / "datasheets").mkdir(parents=True)
    monkeypatch.setattr(
        web.WebFetcher, "fetch_binary",
        lambda self, url, **k: (b"%PDF-1.7\n", _Doc(url, MO)))

    with pytest.raises(cli.CliError) as exc:
        cli._tep_tai_lieu("https://blog.example/um.pdf", du_an)
    tin = str(exc.value)
    assert "không phải nguồn chính chủ" in tin
    assert "kiểm được nguồn chứ không kiểm được nội dung" in tin
    assert "đường dẫn tệp" in tin, "phải chừa đường cho người đã tự đối chiếu"


def test_duong_dan_TEP_van_di_thang_nhu_cu(tmp_path):
    from eaa import cli

    p = tmp_path / "co_san.pdf"
    p.write_bytes(b"%PDF-1.7\n")
    assert cli._tep_tai_lieu(str(p), tmp_path) == p


def test_fetch_binary_tinh_hang_theo_URL_CUOI(monkeypatch):
    """Một miền chính chủ chuyển hướng ra ngoài phải MẤT hạng."""
    from eaa.web import MO, WebFetcher

    chang = {"n": 0}

    def _gia(url, timeout, max_bytes):
        chang["n"] += 1
        if chang["n"] == 1:
            return 302, url, {"Location": "https://blog.example/um.pdf"}, b""
        return 200, "https://blog.example/um.pdf", {"Content-Type": "application/pdf"}, b"%PDF-"

    f = WebFetcher(transport=_gia, resolver=lambda h: ["93.184.216.34"])
    than, doc = f.fetch_binary("https://www.st.com/um.pdf")
    assert than == b"%PDF-"
    assert doc.tier == MO, "hạng phải tính theo URL cuối, không theo chặng đầu"


def test_fetch_binary_ton_trong_cong_tac_tat_mang(monkeypatch):
    from eaa.web import NetworkDisabled, WebFetcher

    monkeypatch.setenv("EAA_NO_NET", "1")
    with pytest.raises(NetworkDisabled):
        WebFetcher().fetch_binary("https://www.st.com/um.pdf")
