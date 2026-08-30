"""TC-75 — đánh giá gói, và phiên gỡ lỗi sâu ở mức tự chủ T0.

Hai bất biến khác nhau, gộp một bài vì cả hai đều nói về ranh giới:

* **Đánh giá gói đánh dấu, KHÔNG loại.** Loại là việc của người duyệt; máy chỉ
  chỉ ra chỗ đáng nhìn kỹ. Và số liệu kho gói là hạng MỞ — không bao giờ được
  dùng làm nguồn cho một giá trị cấu hình phần cứng.
* **N-085 ở mức T0 nghĩa là Agent KHÔNG làm.** Nó dò dụng cụ, dựng kế hoạch từ
  tri thức đã duyệt, và ghi vết. Kế hoạch không được tự bịa ra bước nào.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from eaa.confidence import DA_KIEM, GIA_DINH, KHONG_KIEM_DUOC, SUY_RA
from eaa.debugsession import (
    DAU_HIEU_MACH_GO_LOI,
    DebugError,
    SessionLog,
    build_plan,
    detect_probes,
)
from eaa.toolassess import (
    NGAY_COI_LA_BO_HOANG,
    AssessError,
    assess,
)
from eaa.web import WebFetcher

CONG_KHAI = ["93.184.216.34"]
JSON_HEAD = {"Content-Type": "application/json"}


def _fetcher(trang):
    def gui(url, timeout, max_bytes):
        if url not in trang:
            raise __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                url, 404, "Not Found", {}, None)
        return 200, url, JSON_HEAD, json.dumps(trang[url]).encode()

    return WebFetcher(transport=gui, resolver=lambda h: CONG_KHAI, max_retries=0)


def _ngay(cach_day: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=cach_day)).isoformat()


def _pypi(ten, **kw):
    return {f"https://pypi.org/pypi/{ten}/json": {
        "info": {"version": kw.get("version", "1.0.0"),
                 "license": kw.get("license", "MIT"),
                 "summary": kw.get("summary", "mô tả"),
                 "home_page": kw.get("home_page", "")},
        "releases": {kw.get("version", "1.0.0"): [
            {"upload_time_iso_8601": _ngay(kw.get("cach_day", 30))}]},
    }}


# ═════════════════════════ đánh giá gói ═════════════════════════


def test_goi_lanh_manh_khong_bi_danh_dau():
    kq = assess("pyserial", fetcher=_fetcher(_pypi("pyserial")))
    assert kq.facts.exists is True
    assert kq.clean is True
    assert kq.confidence_level == SUY_RA
    assert "Không có dấu hiệu nào đáng ngại" in kq.render()


def test_khong_tim_thay_la_KET_QUA_khong_phai_loi():
    """Đó chính là câu trả lời cho 'tên này có thật không'."""
    kq = assess("goi-khong-ton-tai", fetcher=_fetcher({}))
    assert kq.facts.exists is False
    assert kq.confidence_level == KHONG_KIEM_DUOC
    ra = kq.render()
    assert "KHÔNG TÌM THẤY" in ra
    assert "gõ nhầm một ký tự" in ra.lower() or "GÕ NHẦM" in ra


def test_lau_khong_phat_hanh_thi_danh_dau():
    kq = assess("cu-ky", fetcher=_fetcher(_pypi("cu-ky", cach_day=NGAY_COI_LA_BO_HOANG + 100)))
    assert any("bỏ hoang" in c for c in kq.flags)


def test_mot_nam_chua_phat_hanh_thi_KHONG_danh_dau_ma_ghi_chu():
    """Một công cụ nhỏ làm xong việc của nó thì không cần phát hành thêm."""
    kq = assess("on-dinh", fetcher=_fetcher(_pypi("on-dinh", cach_day=400)))
    assert kq.clean is True
    assert any("chưa chắc là bỏ hoang" in g for g in kq.notes)


def test_khong_khai_license_thi_danh_dau():
    kq = assess("khong-license", fetcher=_fetcher(_pypi("khong-license", license="")))
    assert any("license" in c for c in kq.flags)


def test_license_la_thi_danh_dau_chu_khong_loai():
    """Đánh dấu, KHÔNG loại — loại là việc của người."""
    kq = assess("la", fetcher=_fetcher(_pypi("la", license="AGPL-3.0")))
    assert any("AGPL" in c for c in kq.flags)
    assert kq.facts.exists is True   # vẫn trả về đầy đủ dữ kiện


def test_ten_khac_mot_ky_tu_bi_danh_dau():
    """Kiểu nhầm này nhắm đúng vào người đọc lướt."""
    kq = assess("pyseria1", fetcher=_fetcher(_pypi("pyseria1")),
                similar_to=["pyserial"])
    assert any("một ký tự" in c for c in kq.flags)


def test_ten_dung_khong_bi_danh_dau_nham():
    kq = assess("pyserial", fetcher=_fetcher(_pypi("pyserial")),
                similar_to=["pyserial"])
    assert not any("một ký tự" in c for c in kq.flags)


def test_ten_khac_han_khong_bi_danh_dau():
    kq = assess("requests", fetcher=_fetcher(_pypi("requests")),
                similar_to=["pyserial"])
    assert not any("một ký tự" in c for c in kq.flags)


def test_ban_in_noi_ro_day_la_hang_MO():
    kq = assess("x", fetcher=_fetcher(_pypi("x")))
    ra = kq.render()
    assert "hạng MỞ" in ra
    assert "KHÔNG dùng làm nguồn cho bất kỳ giá trị cấu hình phần cứng nào" in ra


def test_kho_khong_ho_tro_bao_ro():
    with pytest.raises(AssessError, match="Đang hỗ trợ"):
        assess("x", registry="kho-la")


def test_ten_rong_bi_tu_choi():
    with pytest.raises(AssessError, match="tên gói"):
        assess("  ")


def test_doc_duoc_npm():
    trang = {"https://registry.npmjs.org/abc": {
        "dist-tags": {"latest": "2.1.0"}, "license": "MIT",
        "time": {"2.1.0": _ngay(10)}, "description": "d"}}
    kq = assess("abc", registry="npm", fetcher=_fetcher(trang))
    assert kq.facts.version == "2.1.0" and kq.facts.days_since_release <= 11


def test_doc_duoc_github_va_it_sao_thi_danh_dau():
    trang = {"https://api.github.com/repos/ai/do": {
        "default_branch": "main", "license": {"spdx_id": "MIT"},
        "pushed_at": _ngay(5), "stargazers_count": 3, "open_issues_count": 1}}
    kq = assess("ai/do", registry="github", fetcher=_fetcher(trang))
    assert kq.facts.stars == 3
    assert any("ít người dùng" in c for c in kq.flags)


# ═══════════════════ phiên gỡ lỗi sâu — mức T0 ═══════════════════


class _Cong:
    def __init__(self, device, description=""):
        self.device, self.description = device, description


def test_nhan_ra_mach_go_loi():
    ds = detect_probes([_Cong("/dev/cu.usbmodem1", "CMSIS-DAP debug probe"),
                        _Cong("/dev/cu.Bluetooth", "loa")])
    assert ds[0].likely is True and ds[0].matched in DAU_HIEU_MACH_GO_LOI
    assert ds[1].likely is False


def test_moi_dau_hieu_deu_co_ly_do():
    assert all(v.strip() for v in DAU_HIEU_MACH_GO_LOI.values())


def test_khong_co_cong_nao_thi_khong_sap():
    assert detect_probes([]) == []


class _TieuChi:
    def __init__(self, key, description="", low=None, high=None, expected=None):
        self.key, self.description = key, description
        self.low, self.high, self.expected = low, high, expected


class _Hoi:
    def __init__(self, question):
        self.question = question


class _KichBan:
    id = "DS-09"
    title = "thử"
    description = "giả thuyết của kịch bản"
    symptoms = ("không chạy",)
    firmware_template = "DS-09.c"
    manual = ()

    def __init__(self):
        self.machine = (_TieuChi("f_hz", "tần số", low=900, high=1100),
                        _TieuChi("co_mat", "có mặt"))
        self.human = (_Hoi("Trục có quay không?"),)


def test_ke_hoach_rut_TU_TIEU_CHI_khong_tu_bia():
    """Tự bịa bước là đưa vào một giả thuyết không ai duyệt."""
    kh = build_plan(scenario=_KichBan(), which=lambda t: None)
    assert len(kh.steps) == 3          # 2 máy + 1 người
    assert "f_hz" in kh.steps[0].look_at
    assert "[900, 1100]" in kh.steps[0].if_expected
    assert "có mặt và đọc được" in kh.steps[1].if_expected


def test_moi_buoc_khai_TRUOC_hai_nhanh_ket_luan():
    """Khai trước hai nhánh là cách rẻ nhất để không tự thuyết phục mình."""
    kh = build_plan(scenario=_KichBan(), which=lambda t: None)
    for b in kh.steps:
        assert b.if_expected and b.if_unexpected


def test_ke_hoach_hoi_nguoc_ve_hai_kenh_re_hon():
    kh = build_plan(scenario=_KichBan(), which=lambda t: None)
    ra = kh.render()
    assert "TRƯỚC KHI DỰNG PHIÊN" in ra
    assert "eaa diagnose measure DS-09" in ra
    assert "nhanh hơn nhiều lần dựng phiên JTAG" in ra


def test_ke_hoach_noi_ro_Agent_KHONG_chay_phien():
    ra = build_plan(scenario=_KichBan(), which=lambda t: None).render()
    assert "Tôi KHÔNG chạy phiên này" in ra
    assert "T0" in ra


def test_ke_hoach_luon_la_GIA_DINH():
    """Đây là một kế hoạch, chưa có phép đo nào được thực hiện."""
    assert build_plan(scenario=_KichBan()).confidence_level == GIA_DINH


def test_thieu_dung_cu_thi_neu_ra():
    kh = build_plan(scenario=_KichBan(), which=lambda t: None,
                    tools=("trinh-go-loi-x", "trinh-go-loi-y"))
    assert set(kh.missing_tools) == {"trinh-go-loi-x", "trinh-go-loi-y"}
    assert "chưa có trên máy" in kh.render()


def test_du_dung_cu_thi_khong_neu():
    kh = build_plan(scenario=_KichBan(), which=lambda t: f"/usr/bin/{t}",
                    tools=("trinh-go-loi-x",))
    assert kh.missing_tools == ()


def test_engine_KHONG_biet_ten_trinh_go_loi_nao():
    """Tên trình gỡ lỗi là đặc thù họ MCU — nó thuộc Platform Pack (FR-PLT-01).

    Mặc định rỗng ở đây là một ràng buộc kiến trúc, không phải một chỗ chưa
    điền. TC-38 quét chuỗi, còn bài này canh chính cái mặc định.
    """
    import inspect

    from eaa import debugsession

    chu_ky = inspect.signature(debugsession.build_plan)
    assert chu_ky.parameters["tools"].default == ()
    assert build_plan(scenario=_KichBan(), which=lambda t: None).missing_tools == ()


def test_pack_khai_trinh_go_loi_cua_ho_MCU():
    """Hai pack phải khai được, và engine chỉ nhận danh sách."""
    from pathlib import Path

    from eaa.platform import load_manifest

    goc = Path(__file__).resolve().parent.parent
    for ten in ("avr", "stm32"):
        m = load_manifest(goc / "packs" / ten)
        assert m.debug_tools, f"pack {ten} chưa khai debug_tools"


def test_khong_co_kich_ban_thi_van_dung_duoc_ke_hoach():
    kh = build_plan(scenario=None, which=lambda t: None)
    assert kh.steps == ()
    assert "eaa diagnose list" in kh.render()


# -- ghi vết, phần T0 đòi --


def test_ghi_va_doc_lai_phien(tmp_path):
    n = SessionLog(tmp_path)
    b = n.record(actor="vu-tri-cong", note="thấy f_hz = 0",
                 scenario_id="DS-09", outcome="timer chưa chạy", tool="gdb")
    assert b.confidence_level == DA_KIEM
    assert n.all() == [b]
    ra = n.render()
    assert "vu-tri-cong" in ra and "timer chưa chạy" in ra


def test_khong_ghi_ai_lam_thi_tu_choi(tmp_path):
    """Ở mức T0, 'ai làm' là phần thông tin duy nhất máy không tự biết được."""
    with pytest.raises(DebugError, match="AI làm"):
        SessionLog(tmp_path).record(actor="  ", note="thấy gì đó")


def test_khong_ghi_thay_gi_thi_tu_choi(tmp_path):
    with pytest.raises(DebugError, match="thấy gì"):
        SessionLog(tmp_path).record(actor="x", note="   ")


def test_chua_co_phien_nao(tmp_path):
    assert "chưa có phiên nào" in SessionLog(tmp_path).render()


def test_dong_hong_khong_lam_sap(tmp_path):
    n = SessionLog(tmp_path)
    n.record(actor="a", note="n1")
    with n.path.open("a", encoding="utf-8") as f:
        f.write("hong\n")
    n.record(actor="a", note="n2")
    assert len(n.all()) == 2
