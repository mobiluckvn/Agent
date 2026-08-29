"""Kiểm chứng bộ mô phỏng bằng nghiệm giải tích — ĐIỀU KIỆN TIÊN QUYẾT.

EAA-SRS-01 §2.2: "Bộ mô phỏng MIL/SIL (sản phẩm của công đoạn C1, C2) đã được
kiểm chứng bằng nghiệm giải tích trước khi dùng làm cổng kiểm chứng."
EAA-STP-04 §3 nói rõ hơn: nếu chưa đạt thì **các test liên quan SIL bị chặn**.

Bộ test này là cái "chưa đạt thì chặn" ấy. Nó phải xanh trước khi bất kỳ kết
luận nào từ mô phỏng được coi là bằng chứng — vì mô hình sai thì mô phỏng đẹp
vẫn vô nghĩa (Ma trận Người–AI, công đoạn C1).

Ba lớp:

1.  **Nghiệm giải tích** — chu kỳ dao động nhỏ ở chế độ treo xuống phải khớp
    ``T = 2π√((I + m·l²)/(m·g·l))``.
2.  **Định luật bảo toàn** — không ma sát, không lực thì cơ năng không đổi.
3.  **Tính chất định tính** — điểm cân bằng đúng chỗ, hệ có tắt dần khi có ma
    sát, và mô phỏng TẤT ĐỊNH.

Lớp 3 bắt những lỗi mà hai lớp đầu bỏ sót: một mô hình sai dấu vẫn có thể cho
đúng chu kỳ và vẫn bảo toàn năng lượng.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SIM_DIR = REPO / "projects" / "robot_balance" / "sim"

sys.path.insert(0, str(SIM_DIR))
import model as pendulum  # noqa: E402


@pytest.fixture()
def params() -> "pendulum.PendulumParams":
    return pendulum.PendulumParams()


def _mo_phong(plant, theta0: float, duration: float, dt: float = 1e-4):
    """Chạy tự do không lực, trả về chuỗi (thời gian, góc)."""
    plant.reset(theta=theta0)
    mau = [(0.0, plant.state.theta)]
    for i in range(int(duration / dt)):
        plant.step(0.0, dt)
        mau.append(((i + 1) * dt, plant.state.theta))
    return mau


def _chu_ky_do_duoc(mau) -> float:
    """Đo chu kỳ bằng khoảng cách giữa các lần cắt không theo cùng một chiều.

    Nội suy tuyến tính quanh điểm cắt để độ phân giải không bị giới hạn bởi
    bước thời gian — nếu không, sai số đo sẽ lấn át sai số của mô hình và phép
    kiểm mất khả năng phát hiện.
    """
    cat_khong: list[float] = []
    for (t0, a0), (t1, a1) in zip(mau, mau[1:]):
        if a0 <= 0.0 < a1:
            cat_khong.append(t0 + (t1 - t0) * (-a0) / (a1 - a0))
    if len(cat_khong) < 2:
        raise AssertionError("Không đo được chu kỳ: chưa đủ hai lần cắt không")
    khoang = [b - a for a, b in zip(cat_khong, cat_khong[1:])]
    return sum(khoang) / len(khoang)


# --------------------------------------------------------------------------
# Lớp 1 — nghiệm giải tích
# --------------------------------------------------------------------------


def test_chu_ky_dao_dong_nho_khop_nghiem_giai_tich(params) -> None:
    """T đo được từ mô phỏng phải khớp T = 2π√((I+m·l²)/(m·g·l))."""
    plant = pendulum.InvertedPendulum(params, cart_locked=True, frictionless=True)

    # Thả gần vị trí TREO XUỐNG (theta = π), lệch 2° — đủ nhỏ để tuyến tính hóa.
    theta0 = math.pi - math.radians(2.0)
    mau = _mo_phong(plant, theta0, duration=5.0)

    # Đo theo biến lệch φ = θ − π để dùng lại phép đo cắt không.
    lech = [(t, a - math.pi) for t, a in mau]
    do_duoc = _chu_ky_do_duoc(lech)
    giai_tich = params.small_oscillation_period

    sai_so = abs(do_duoc - giai_tich) / giai_tich
    assert sai_so < 0.01, (
        f"Chu kỳ mô phỏng {do_duoc:.5f}s lệch {sai_so*100:.2f}% so với nghiệm "
        f"giải tích {giai_tich:.5f}s. Mô hình chưa dùng làm cổng chặn được."
    )


@pytest.mark.parametrize("bien_do_deg", [0.5, 1.0, 2.0])
def test_bien_do_cang_nho_cang_sat_nghiem_tuyen_tinh_hoa(params, bien_do_deg) -> None:
    """Sai số phải GIẢM khi biên độ giảm — dấu hiệu mô hình phi tuyến đúng.

    Con lắc thật có chu kỳ tăng dần theo biên độ. Nếu chu kỳ mô phỏng không đổi
    theo biên độ thì mô hình đã bị tuyến tính hóa ở đâu đó, và nó sẽ nói dối ở
    những góc lớn — đúng vùng mà robot cần được cứu nhất.
    """
    plant = pendulum.InvertedPendulum(params, cart_locked=True, frictionless=True)
    theta0 = math.pi - math.radians(bien_do_deg)
    mau = [(t, a - math.pi) for t, a in _mo_phong(plant, theta0, duration=5.0)]

    do_duoc = _chu_ky_do_duoc(mau)
    giai_tich = params.small_oscillation_period
    sai_so = (do_duoc - giai_tich) / giai_tich

    # Xấp xỉ bậc hai: T ≈ T₀·(1 + θ₀²/16).
    du_bao = math.radians(bien_do_deg) ** 2 / 16.0
    assert sai_so > 0, "chu kỳ phải LỚN hơn nghiệm tuyến tính hóa, không nhỏ hơn"
    assert abs(sai_so - du_bao) < 5e-4, (
        f"biên độ {bien_do_deg}°: sai lệch chu kỳ {sai_so:.6f} không khớp xấp xỉ "
        f"bậc hai {du_bao:.6f} — mô hình phi tuyến sai"
    )


# --------------------------------------------------------------------------
# Lớp 2 — định luật bảo toàn
# --------------------------------------------------------------------------


def test_bao_toan_nang_luong_khi_khong_ma_sat(params) -> None:
    plant = pendulum.InvertedPendulum(params, cart_locked=True, frictionless=True)
    plant.reset(theta=math.pi - math.radians(20.0))

    ban_dau = plant.energy()
    cuc_tri = [ban_dau]
    for _ in range(int(3.0 / 1e-4)):
        plant.step(0.0, 1e-4)
        cuc_tri.append(plant.energy())

    troi = max(abs(e - ban_dau) for e in cuc_tri) / ban_dau
    assert troi < 1e-6, (
        f"Cơ năng trôi {troi:.2e} sau 3s — bộ tích phân tự sinh hoặc tự tiêu "
        "năng lượng, mọi kết luận về ổn định đều không tin được."
    )


def test_bao_toan_nang_luong_ca_khi_xe_khong_bi_khoa(params) -> None:
    """Hệ đầy đủ hai bậc tự do cũng phải bảo toàn — kiểm phần khử ma trận."""
    plant = pendulum.InvertedPendulum(params, frictionless=True)
    plant.reset(theta=math.radians(10.0))

    ban_dau = plant.energy()
    troi_max = 0.0
    for _ in range(int(1.0 / 1e-4)):
        plant.step(0.0, 1e-4)
        troi_max = max(troi_max, abs(plant.energy() - ban_dau) / ban_dau)

    assert troi_max < 1e-5, f"cơ năng trôi {troi_max:.2e} ở hệ hai bậc tự do"


def test_co_ma_sat_thi_nang_luong_giam_don_dieu(params) -> None:
    plant = pendulum.InvertedPendulum(params, cart_locked=True)
    plant.reset(theta=math.pi - math.radians(20.0))

    truoc = plant.energy()
    for _ in range(2000):
        plant.step(0.0, 1e-3)
        hien_tai = plant.energy()
        assert hien_tai <= truoc + 1e-9, "ma sát mà năng lượng lại tăng"
        truoc = hien_tai


# --------------------------------------------------------------------------
# Lớp 3 — tính chất định tính
# --------------------------------------------------------------------------


def test_dung_thang_la_diem_can_bang_KHONG_on_dinh(params) -> None:
    """Lệch một chút khỏi phương thẳng đứng thì phải ngã, không phải quay về."""
    plant = pendulum.InvertedPendulum(params, cart_locked=True)
    plant.reset(theta=math.radians(0.5))

    for _ in range(3000):
        plant.step(0.0, 1e-3)

    assert abs(plant.state.theta) > math.radians(5.0), (
        "Robot tự đứng dậy khi không có điều khiển — dấu của mô hình sai, và "
        "toàn bộ bài toán điều khiển sẽ trở nên vô nghĩa."
    )


def test_treo_xuong_la_diem_can_bang_on_dinh(params) -> None:
    """Hội tụ về vị trí treo xuống — nhưng phải cho đủ thời gian.

    Hằng số thời gian tắt dần của hệ là ``τ = 2(I+m·l²)/c ≈ 34s`` với hệ số cản
    trục hiện tại. Một phép kiểm chỉ chạy 20s sẽ thấy con lắc còn dao động ~2,8°
    và kết luận nhầm là mô hình sai — lỗi của kỳ vọng, không phải của mô hình.
    """
    plant = pendulum.InvertedPendulum(params, cart_locked=True)
    plant.reset(theta=math.pi - math.radians(5.0))

    tau = 2.0 * (params.body_inertia + params.body_mass_kg * params.com_height_m ** 2)
    tau /= params.pivot_damping
    for _ in range(int(5.0 * tau / 1e-3)):
        plant.step(0.0, 1e-3)

    assert abs(plant.state.theta - math.pi) < math.radians(1.0), (
        "Con lắc không hội tụ về vị trí treo xuống dù có ma sát"
    )


def test_toc_do_tat_dan_khop_hang_so_thoi_gian_giai_tich(params) -> None:
    """Phép kiểm giải tích thứ ba: số hạng cản phải đúng độ lớn, không chỉ đúng dấu.

    Với cản nhớt nhỏ, biên độ tắt theo ``A(t) = A₀·e^(−t/τ)`` với
    ``τ = 2(I+m·l²)/c``. Hai phép kiểm trước (chu kỳ, bảo toàn năng lượng) đều
    chạy ở chế độ KHÔNG ma sát nên không nói gì về số hạng này — một hệ số cản
    sai mười lần vẫn qua được cả hai.
    """
    plant = pendulum.InvertedPendulum(params, cart_locked=True)
    bien_do_0 = math.radians(5.0)
    plant.reset(theta=math.pi - bien_do_0)

    I_eff = params.body_inertia + params.body_mass_kg * params.com_height_m ** 2
    tau = 2.0 * I_eff / params.pivot_damping

    dt, t_do = 1e-4, 30.0
    dinh: list[float] = []
    truoc = truoc_nua = 0.0
    for i in range(int(t_do / dt)):
        plant.step(0.0, dt)
        lech = plant.state.theta - math.pi
        # Bắt cực đại địa phương của |φ| để đo đường bao biên độ.
        if truoc > truoc_nua and truoc > lech and truoc > 0:
            dinh.append((i * dt, truoc))
        truoc_nua, truoc = truoc, lech

    assert len(dinh) >= 5, "không đo được đủ đỉnh để dựng đường bao"
    t_cuoi, a_cuoi = dinh[-1]
    du_bao = bien_do_0 * math.exp(-t_cuoi / tau)

    assert abs(a_cuoi - du_bao) / du_bao < 0.05, (
        f"Biên độ tại t={t_cuoi:.1f}s là {math.degrees(a_cuoi):.4f}°, đường bao "
        f"giải tích cho {math.degrees(du_bao):.4f}° (τ={tau:.1f}s) — hệ số cản "
        "trong mô hình sai độ lớn."
    )


def test_nghieng_ve_phia_truoc_thi_nga_ve_phia_truoc(params) -> None:
    """Quy ước dấu phải nhất quán, nếu không bộ điều khiển sẽ đẩy ngược chiều."""
    plant = pendulum.InvertedPendulum(params, cart_locked=True)
    plant.reset(theta=math.radians(1.0))
    for _ in range(500):
        plant.step(0.0, 1e-3)
    assert plant.state.theta > math.radians(1.0)

    plant.reset(theta=math.radians(-1.0))
    for _ in range(500):
        plant.step(0.0, 1e-3)
    assert plant.state.theta < math.radians(-1.0)


def test_luc_bi_gioi_han_theo_tran_cua_co_cau_chap_hanh(params) -> None:
    """Mô phỏng không được cho phép một lực mà động cơ thật không tạo nổi."""
    plant = pendulum.InvertedPendulum(params)
    plant.reset(theta=0.0)
    plant.step(1e6, 0.01)
    hoang_duong = plant.state.x_dot

    plant.reset(theta=0.0)
    plant.step(params.max_force_n, 0.01)
    assert abs(hoang_duong - plant.state.x_dot) < 1e-9, (
        "lực vượt trần không bị cắt — mô phỏng sẽ cứu được robot mà thiết bị "
        "thật thì không"
    )


def test_mo_phong_tat_dinh(params) -> None:
    """Hai lần chạy cùng đầu vào phải cho cùng kết quả tới từng bit.

    Nếu không, cổng SIL lúc đạt lúc không và mất tư cách cổng chặn — và thực
    nghiệm A/B của Chương 3 mất khả năng tái lập.
    """
    def chay():
        p = pendulum.InvertedPendulum(pendulum.PendulumParams())
        p.reset(theta=math.radians(3.0))
        cam_bien = pendulum.SensorModel()
        cam_bien.reset()
        vet = []
        for i in range(500):
            goc, toc = cam_bien.measure(p.state, 0.01)
            p.step(0.5 * math.sin(i * 0.05), 0.01)
            vet.append((goc, toc, p.state.theta))
        return vet

    assert chay() == chay()


def test_cam_bien_them_nhieu_va_troi_diem_khong() -> None:
    """Mô phỏng cho tín hiệu hoàn hảo sẽ cho qua đúng bộ tham số nhạy nhiễu nhất."""
    cam_bien = pendulum.SensorModel()
    cam_bien.reset()
    trang_thai = pendulum.State(theta=0.1, theta_dot=0.0)

    goc_do = [cam_bien.measure(trang_thai, 0.01)[0] for _ in range(200)]
    assert any(abs(g - 0.1) > 1e-6 for g in goc_do), "cảm biến không có nhiễu"
    assert max(goc_do) - min(goc_do) < math.radians(2.0), "nhiễu lớn phi lý"

    cam_bien.reset()
    toc_dau = cam_bien.measure(trang_thai, 0.01)[1]
    for _ in range(1000):
        cam_bien.measure(trang_thai, 0.01)
    toc_sau = cam_bien.measure(trang_thai, 0.01)[1]
    assert toc_sau > toc_dau, "con quay hồi chuyển không trôi điểm không"


def test_co_cau_chap_hanh_truot_buoc_khi_qua_toc_do() -> None:
    co_cau = pendulum.ActuatorModel(max_step_rate_hz=100.0)
    co_cau.reset()

    # Ở trần 100 bước/s, vận tốc 0,001 m/s ứng với ~12 bước/s — thoải mái trong
    # trần; 5 m/s ứng với ~60 nghìn bước/s — vượt xa.
    binh_thuong = co_cau.apply(2.0, pendulum.State(x_dot=0.001), 0.01)
    assert abs(binh_thuong - 2.0) < 1e-9 and co_cau.slips == 0

    qua_nhanh = co_cau.apply(2.0, pendulum.State(x_dot=5.0), 0.01)
    assert co_cau.slips == 1
    assert abs(qua_nhanh) < 2.0, "trượt bước mà lực không giảm"


# --------------------------------------------------------------------------
# Tham số lấy từ hồ sơ phần cứng — một nguồn sự thật duy nhất
# --------------------------------------------------------------------------


def test_tham_so_vat_ly_lay_tu_hardware_profile() -> None:
    from eaa.kb import HardwareProfile

    ho_so = HardwareProfile.load(
        REPO / "projects" / "robot_balance" / "hardware_profile.yaml"
    )
    p = pendulum.PendulumParams.from_hardware_profile(ho_so.raw)

    assert p.body_mass_kg == ho_so.mechanics["body_mass_kg"]
    assert p.com_height_m == ho_so.mechanics["com_height_m"]
    assert p.cart_damping == ho_so.mechanics["friction_coeff"]
