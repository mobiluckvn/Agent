"""TC-58 — hoàn thiện tầng đo trên thiết bị thật (N-081, N-083, N-084, N-086).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-58a | Đủ 6 kịch bản DS có phần đo | N-081 — chưa khai thì DỪNG, không dựng ảnh rỗng |
| TC-58b | Đo thời gian thực báo TRƯỜNG HỢP XẤU NHẤT | N-083 — không chỉ trung bình |
| TC-58c | Hướng dẫn đo tay trả lời đủ bốn câu | N-084 — thiếu một câu là từ chối |
| TC-58d | Số đo tay chưa nhập ⇒ chưa đo, không phải đạt | Agent không đoán con số |
| TC-58e | Reset phát hiện qua bộ đếm thời gian chạy tụt | N-086 |
| TC-58f | Chạy ngắn hơn yêu cầu ⇒ CHƯA KẾT LUẬN ĐƯỢC | 10 phút không nói gì về 10 giờ |
| TC-58g | Không có bộ đếm thời gian chạy ⇒ KHÔNG KẾT LUẬN ĐƯỢC | không phải "đạt" |

TC-58f và TC-58g là hai mặt của cùng một điều: một phiên đo sạch sẽ trông y
hệt bằng chứng, và người đọc sẽ mang cảm giác ấy đi xa hơn dữ liệu cho phép.
Nên phần kết luận ở đây luôn nói về THỜI GIAN trước khi nói về kết quả.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.diagnostics import DiagnosticError, ManualMeasurement, ScenarioLibrary
from eaa.endurance import EnduranceReport, analyse

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


@pytest.fixture(scope="module")
def thu_vien() -> ScenarioLibrary:
    return ScenarioLibrary.load(DU_AN / "diagnostics.yaml")


# --------------------------------------------------------------------------
# TC-58a — đủ 6 kịch bản có phần đo (N-081)
# --------------------------------------------------------------------------


def test_moi_kich_ban_deu_co_phan_do(thu_vien: ScenarioLibrary) -> None:
    """Trước bản này mới 2/6 kịch bản khai firmware_template."""
    thieu = [s.id for s in thu_vien.scenarios if not s.buildable]
    assert thieu == [], f"kịch bản chưa có phần đo: {thieu}"
    assert len(thu_vien.scenarios) == 6


def test_tep_do_cua_moi_kich_ban_ton_tai_that(thu_vien: ScenarioLibrary) -> None:
    """Khai một đường dẫn không có tệp thì `eaa diagnose build` mới báo — quá muộn."""
    for s in thu_vien.scenarios:
        duong_dan = DU_AN / s.firmware_template
        assert duong_dan.is_file(), f"{s.id}: thiếu {duong_dan}"


def test_moi_tep_do_ton_trong_hop_dong_voi_bo_khung(thu_vien: ScenarioLibrary) -> None:
    """Bộ khung gọi ``diag_run()`` và cấp ``eaa_emit()`` — cả hai phải có mặt."""
    for s in thu_vien.scenarios:
        ma = (DU_AN / s.firmware_template).read_text(encoding="utf-8")
        assert "void diag_run(void)" in ma, f"{s.id}: thiếu diag_run()"
        assert "eaa_emit" in ma, f"{s.id}: không gửi khung telemetry nào"


def test_moi_khoa_kenh_may_deu_duoc_tep_do_sinh_ra(thu_vien: ScenarioLibrary) -> None:
    """Một tiêu chí đối chiếu khóa mà firmware không gửi là một tiêu chí luôn trượt.

    Phép kiểm này thô — nó chỉ tìm chuỗi — nhưng nó bắt được đúng loại lệch hay
    xảy ra nhất: đổi tên khóa ở một trong hai nơi rồi quên nơi kia.
    """
    for s in thu_vien.scenarios:
        ma = (DU_AN / s.firmware_template).read_text(encoding="utf-8")
        for m in s.machine:
            assert m.key in ma, f"{s.id}: kênh máy chờ {m.key!r} mà tệp đo không gửi"


def test_kich_ban_chua_khai_phan_do_thi_khong_dung_duoc() -> None:
    from eaa.diagnostics import Scenario

    assert not Scenario(id="DS-99", title="thử").buildable


# --------------------------------------------------------------------------
# TC-58b — trường hợp xấu nhất (N-083)
# --------------------------------------------------------------------------


def test_do_thoi_gian_thuc_bao_ca_truong_hop_xau_nhat(thu_vien: ScenarioLibrary) -> None:
    """Trung bình gần như luôn đẹp; chính chu kỳ dài nhất quyết định robot đứng hay ngã."""
    ds06 = thu_vien.get("DS-06")
    khoa = {m.key for m in ds06.machine}

    assert "isr_period_ms" in khoa, "trung bình"
    assert "isr_period_max_ms" in khoa, "TRƯỜNG HỢP XẤU NHẤT"
    assert "jitter_us" in khoa, "dao động chu kỳ"
    assert "cpu_load_pct" in khoa, "tải CPU"


def test_nguong_truong_hop_xau_nhat_sat_rang_buoc_cung() -> None:
    """Ràng buộc control_loop_ms = 10 ms phải áp lên chu kỳ dài nhất, không lên trung bình."""
    from eaa.kb import Constraints

    ds06 = ScenarioLibrary.load(DU_AN / "diagnostics.yaml").get("DS-06")
    xau_nhat = next(m for m in ds06.machine if m.key == "isr_period_max_ms")
    rang_buoc = Constraints.load(DU_AN / "constraints.yaml").limits["control_loop_ms"]

    assert xau_nhat.op == "max"
    assert float(xau_nhat.high) <= float(rang_buoc) * 1.05, (
        "ngưỡng cho trường hợp xấu nhất phải bám sát ràng buộc cứng, "
        "nếu không thì nó chỉ là một con số dễ dãi khác"
    )


def test_so_mau_duoc_kiem_de_khong_ket_luan_tu_vai_chu_ky(thu_vien: ScenarioLibrary) -> None:
    mau = next(m for m in thu_vien.get("DS-06").machine if m.key == "samples")
    assert mau.op == "min" and float(mau.low) >= 100


# --------------------------------------------------------------------------
# TC-58c, TC-58d — đo tay (N-084)
# --------------------------------------------------------------------------


def _do_tay(**kw) -> ManualMeasurement:
    kw.setdefault("key", "dong_a")
    kw.setdefault("quantity", "Dòng tiêu thụ")
    kw.setdefault("instrument", "Ampe kìm")
    kw.setdefault("where", "Dây dương từ pin")
    kw.setdefault("condition", "Lúc động cơ tăng tốc")
    kw.setdefault("unit", "A")
    kw.setdefault("high", 2.5)
    return ManualMeasurement(**kw)


@pytest.mark.parametrize(
    "thieu", ["quantity", "instrument", "where", "condition", "unit"]
)
def test_huong_dan_do_thieu_mot_trong_bon_cau_thi_tu_choi(thieu: str) -> None:
    """Thiếu một câu thì hai người đo ra hai kết quả, và không ai sai."""
    with pytest.raises(DiagnosticError, match=thieu):
        _do_tay(**{thieu: ""})


def test_do_tay_khong_co_nguong_thi_tu_choi() -> None:
    with pytest.raises(DiagnosticError, match="ngưỡng"):
        _do_tay(high=None, low=None)


def test_huong_dan_do_neu_du_bon_cau() -> None:
    van_ban = _do_tay().instructions()
    for muc in ("dụng cụ", "đo ở đâu", "điều kiện", "chờ đợi"):
        assert muc in van_ban


def test_doi_chieu_so_do_voi_nguong() -> None:
    m = _do_tay(high=2.5)
    assert m.evaluate(1.8)[0]
    dat, mo_ta = m.evaluate(3.1)
    assert not dat and "vượt trần" in mo_ta


def test_nguong_hai_dau_hien_ra_dung_dang() -> None:
    assert _do_tay(low=4.5, high=5.5).expected_text() == "4.5–5.5 A"
    assert _do_tay(low=4.5, high=None).expected_text() == "≥ 4.5 A"


def test_du_an_mau_khai_du_ba_phep_do_dien_nhiet(thu_vien: ScenarioLibrary) -> None:
    """N-084 nêu đích danh: dòng tiêu thụ, sụt áp khi tải, nhiệt độ linh kiện."""
    ds05 = thu_vien.get("DS-05")
    khoa = {m.key for m in ds05.manual}

    assert len(ds05.manual) == 3
    assert any("dong" in k for k in khoa)
    assert any("sut_ap" in k for k in khoa)
    assert any("nhiet" in k for k in khoa)


def test_kich_ban_co_do_tay_thi_khong_con_tu_dong_hoan_toan(thu_vien: ScenarioLibrary) -> None:
    """Đo tay là việc của người, nên kịch bản có nó không tự chạy hết được."""
    assert not thu_vien.get("DS-05").fully_automatic
    assert thu_vien.get("DS-01").fully_automatic


# --------------------------------------------------------------------------
# TC-58e, TC-58f, TC-58g — chạy dài (N-086)
# --------------------------------------------------------------------------


class _Khung:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.ok = True


class _BanThu:
    """Bản thu tối giản — cùng hình dạng với ``telemetry.Capture``."""

    def __init__(self, ban_ghi: list[dict], duration_s: float = 0.0) -> None:
        self.frames = [_Khung(json.dumps(d)) for d in ban_ghi]
        self.duration_s = duration_s
        self.bad_ratio = 0.0

    @property
    def good(self) -> list[_Khung]:
        return self.frames


def _chay(n: int, reset_tai: int | None = None, buoc: float = 1.0) -> _BanThu:
    ban_ghi, t = [], 0.0
    for i in range(n):
        t = 0.5 if i == reset_tai else t + buoc
        ban_ghi.append({"uptime_s": round(t, 2), "tilt": 0.3 + i * 0.001})
    return _BanThu(ban_ghi, duration_s=n * buoc)


def test_reset_phat_hien_qua_bo_dem_tut_ve_gan_khong() -> None:
    bao_cao = analyse(_chay(400, reset_tai=250), required_s=100)

    assert len(bao_cao.resets) == 1
    assert bao_cao.resets[0].frame_index == 250
    assert not bao_cao.ok
    assert "KHÔNG ĐẠT" in bao_cao.verdict()


def test_xao_tron_nho_khong_bi_doc_thanh_reset() -> None:
    """Báo động giả thì người ta học cách phớt lờ, làm hỏng luôn lần báo đúng."""
    ban_thu = _BanThu(
        [{"uptime_s": 10.0}, {"uptime_s": 10.5}, {"uptime_s": 10.2}, {"uptime_s": 11.0}]
    )
    assert analyse(ban_thu).resets == ()


def test_thoi_gian_quan_sat_lay_theo_bo_dem_cao_nhat_khong_cong_don() -> None:
    """Sau một lần khởi động lại, 'đã chạy liên tục bao lâu' đếm lại từ đầu."""
    bao_cao = analyse(_chay(400, reset_tai=250))
    assert bao_cao.observed_s == 250.0


def test_chay_ngan_hon_yeu_cau_la_CHUA_KET_LUAN_DUOC() -> None:
    bao_cao = analyse(_chay(100), required_s=600)

    assert not bao_cao.long_enough and not bao_cao.ok
    van_ban = bao_cao.verdict()
    assert "CHƯA KẾT LUẬN ĐƯỢC" in van_ban
    assert "10 phút không nói gì về 10 giờ" in van_ban


def test_chay_du_lau_va_khong_reset_thi_dat() -> None:
    bao_cao = analyse(_chay(700), required_s=600)

    assert bao_cao.ok
    assert "ĐẠT" in bao_cao.verdict()
    assert "chỉ nói về" in bao_cao.render(), "kết luận vẫn phải khoanh vùng thời gian"


def test_khong_co_bo_dem_thoi_gian_chay_la_KHONG_KET_LUAN_DUOC() -> None:
    """Một phiên có reset trông y hệt phiên liền mạch nếu không ai đi tìm dấu vết."""
    ban_thu = _BanThu([{"tilt": 0.3}, {"tilt": 0.4}])
    bao_cao = analyse(ban_thu, required_s=600)

    assert not bao_cao.uptime_present and not bao_cao.ok
    assert "KHÔNG KẾT LUẬN ĐƯỢC" in bao_cao.verdict()


def test_troi_duoc_bao_cao_kem_toc_do_moi_gio() -> None:
    bao_cao = analyse(_chay(700), required_s=600, drift_keys=("tilt",))

    assert len(bao_cao.drifts) == 1
    troi = bao_cao.drifts[0]
    assert troi.delta == pytest.approx(0.699, abs=1e-3)
    assert troi.per_hour is not None


def test_quan_sat_qua_ngan_thi_khong_quy_doi_toc_do_troi() -> None:
    """Ngoại suy từ 30 giây lên một giờ là nhân sai số lên 120 lần."""
    bao_cao = analyse(_chay(30), drift_keys=("tilt",))
    assert bao_cao.drifts[0].per_hour is None
    assert "chưa quy được tốc độ trôi" in bao_cao.drifts[0].render()


def test_khong_yeu_cau_thoi_luong_thi_khong_chan_vi_thoi_luong() -> None:
    assert analyse(_chay(10)).long_enough


def test_bao_cao_luon_mo_dau_bang_thoi_gian_da_quan_sat() -> None:
    van_ban = analyse(_chay(700), required_s=600).render()
    vi_tri_thoi_gian = van_ban.index("Thiết bị tự báo đã chạy")
    assert vi_tri_thoi_gian < len(van_ban) // 2
