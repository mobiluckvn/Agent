"""Mô hình động lực học con lắc ngược trên xe — dự án robot_balance.

Sản phẩm của công đoạn C1 (Ma trận Người–AI): "Tự xây dựng bộ mô phỏng động
lực học bằng AI (Model-in-the-Loop, thay cho Wokwi)". Đây là DỮ LIỆU DỰ ÁN,
không phải engine: mọi hằng số vật lý của robot nằm ở đây và trong
``hardware_profile.yaml``.

**Điều kiện tiên quyết trước khi dùng làm cổng chặn** (EAA-SRS-01 §2.2, ADR-05):
bộ mô phỏng phải được kiểm chứng bằng nghiệm giải tích. Mô hình này cung cấp
sẵn hai lối kiểm chứng đó, và ``tests/test_sim_verification.py`` chạy chúng:

1.  **Tần số dao động nhỏ.** Khóa xe lại và thả con lắc ở gần vị trí TREO
    XUỐNG, ta có dao động điều hòa với ``ω = √(m·g·l / (I + m·l²))`` — nghiệm
    giải tích biết trước. Chu kỳ đo được từ mô phỏng phải khớp.
2.  **Bảo toàn năng lượng.** Tắt ma sát và không tác động lực, tổng động năng
    cộng thế năng phải giữ nguyên.

Vì sao kiểm ở chế độ TREO XUỐNG chứ không phải ở tư thế dựng đứng: dựng đứng
là điểm cân bằng không ổn định, nghiệm của nó phân kỳ theo hàm mũ nên sai số
tích phân bị khuếch đại và không dùng để đối chiếu được. Cùng một hệ phương
trình, kiểm ở chế độ có nghiệm giải tích ổn định rồi mới tin nó ở chế độ kia —
đó là ý nghĩa của "kiểm chứng bằng nghiệm giải tích".

Hệ quy chiếu: ``theta`` là góc nghiêng thân robot tính từ phương thẳng đứng
hướng lên, đơn vị radian, dương khi nghiêng về phía trước. ``x`` là vị trí xe
theo mét. Đầu vào ``u`` là lực đẩy ngang tác dụng lên xe, đơn vị newton.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

G = 9.80665  # gia tốc trọng trường, m/s²


@dataclass
class PendulumParams:
    """Tham số vật lý. Giá trị mặc định lấy từ hardware_profile.yaml của dự án.

    Những giá trị chưa đo được (ví dụ hệ số ma sát) là GIẢ ĐỊNH — chúng phải
    nằm trong Assumption Log ở trạng thái proposed, và bị thay bằng số đo thật
    ngay khi có (AIS §8.1: tri thức thực chứng luôn thắng giả định).
    """

    cart_mass_kg: float = 0.25       # khối lượng phần bánh + trục
    body_mass_kg: float = 0.85       # khối lượng thân, từ hardware_profile
    com_height_m: float = 0.11       # khoảng cách trục bánh tới trọng tâm thân
    wheel_radius_m: float = 0.0425
    #: Mô men quán tính thân quanh trọng tâm. Mặc định coi thân là thanh mảnh
    #: quay quanh một đầu: I_cm = m·L²/12 với L = 2·com_height.
    body_inertia: float | None = None
    cart_damping: float = 0.02       # ma sát lăn, N·s/m — GIẢ ĐỊNH chưa đo
    pivot_damping: float = 0.0008    # ma sát trục, N·m·s/rad — GIẢ ĐỊNH chưa đo
    max_force_n: float = 3.0         # trần lực đẩy, suy từ mô men động cơ bước
    gravity: float = G

    def __post_init__(self) -> None:
        if self.body_inertia is None:
            L = 2.0 * self.com_height_m
            self.body_inertia = self.body_mass_kg * L * L / 12.0

    @classmethod
    def from_hardware_profile(cls, profile: dict[str, Any]) -> "PendulumParams":
        """Dựng tham số từ ``hardware_profile.yaml`` — một nguồn sự thật duy nhất."""
        co_khi = dict(profile.get("mechanics") or {})
        return cls(
            body_mass_kg=float(co_khi.get("body_mass_kg", 0.85)),
            com_height_m=float(co_khi.get("com_height_m", 0.11)),
            wheel_radius_m=float(co_khi.get("wheel_radius_m", 0.0425)),
            cart_damping=float(co_khi.get("friction_coeff", 0.02)),
        )

    @property
    def natural_frequency(self) -> float:
        """Tần số góc dao động nhỏ quanh vị trí TREO XUỐNG, rad/s.

        Nghiệm giải tích dùng để kiểm chứng bộ mô phỏng. Suy từ phương trình
        con lắc vật lý tuyến tính hóa: ``(I + m·l²)·φ̈ = −m·g·l·φ``.
        """
        m, l = self.body_mass_kg, self.com_height_m
        return math.sqrt(m * self.gravity * l / (self.body_inertia + m * l * l))

    @property
    def small_oscillation_period(self) -> float:
        return 2.0 * math.pi / self.natural_frequency


@dataclass
class State:
    """Trạng thái hệ: vị trí xe, vận tốc xe, góc nghiêng, vận tốc góc."""

    x: float = 0.0
    x_dot: float = 0.0
    theta: float = 0.0
    theta_dot: float = 0.0

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x, self.x_dot, self.theta, self.theta_dot)

    @property
    def theta_deg(self) -> float:
        return math.degrees(self.theta)


class InvertedPendulum:
    """Mô hình con lắc ngược trên xe, tích phân bằng Runge–Kutta bậc 4.

    ``cart_locked=True`` khóa xe lại, biến hệ thành con lắc vật lý thuần túy —
    chế độ dùng để kiểm chứng mô hình bằng nghiệm giải tích.
    """

    def __init__(
        self,
        params: PendulumParams | None = None,
        *,
        cart_locked: bool = False,
        frictionless: bool = False,
    ) -> None:
        self.p = params or PendulumParams()
        self.cart_locked = cart_locked
        self.frictionless = frictionless
        self.state = State()

    # ----------------------------------------------------------------------

    def reset(self, *, theta: float = 0.0, theta_dot: float = 0.0, x: float = 0.0) -> None:
        self.state = State(x=x, x_dot=0.0, theta=theta, theta_dot=theta_dot)

    def derivatives(
        self, s: tuple[float, float, float, float], u: float
    ) -> tuple[float, float, float, float]:
        """Vế phải của hệ phương trình vi phân.

        Phương trình cart–pole chuẩn, viết cho ``theta`` đo từ phương thẳng
        đứng hướng lên::

            (M+m)·ẍ + m·l·θ̈·cos θ − m·l·θ̇²·sin θ = u − b·ẋ
            (I+m·l²)·θ̈ + m·l·ẍ·cos θ − m·g·l·sin θ = −c·θ̇
        """
        p = self.p
        x, x_dot, theta, theta_dot = s

        M, m, l = p.cart_mass_kg, p.body_mass_kg, p.com_height_m
        I = p.body_inertia
        g = p.gravity
        b = 0.0 if self.frictionless else p.cart_damping
        c = 0.0 if self.frictionless else p.pivot_damping

        sin_t, cos_t = math.sin(theta), math.cos(theta)

        if self.cart_locked:
            # Xe bị khóa: chỉ còn phương trình con lắc vật lý, có nghiệm giải tích.
            theta_ddot = (m * g * l * sin_t - c * theta_dot) / (I + m * l * l)
            return (0.0, 0.0, theta_dot, theta_ddot)

        # Khử ẍ và θ̈ khỏi hệ hai phương trình tuyến tính.
        a11 = M + m
        a12 = m * l * cos_t
        a21 = m * l * cos_t
        a22 = I + m * l * l

        b1 = u - b * x_dot + m * l * theta_dot * theta_dot * sin_t
        b2 = m * g * l * sin_t - c * theta_dot

        det = a11 * a22 - a12 * a21
        if abs(det) < 1e-12:  # pragma: no cover - cấu hình vật lý suy biến
            raise ZeroDivisionError("Ma trận quán tính suy biến — tham số vật lý sai")

        x_ddot = (b1 * a22 - a12 * b2) / det
        theta_ddot = (a11 * b2 - a21 * b1) / det
        return (x_dot, x_ddot, theta_dot, theta_ddot)

    def step(self, u: float, dt: float) -> State:
        """Tiến một bước tích phân bằng RK4.

        Dùng RK4 chứ không phải Euler: sai số Euler tích lũy theo bậc nhất và
        sẽ tự sinh ra năng lượng, làm phép kiểm bảo toàn năng lượng ở trên thất
        bại vì lỗi của bộ tích phân chứ không phải lỗi của mô hình.
        """
        u = max(-self.p.max_force_n, min(self.p.max_force_n, u))
        s = self.state.as_tuple()

        k1 = self.derivatives(s, u)
        s2 = tuple(si + 0.5 * dt * ki for si, ki in zip(s, k1))
        k2 = self.derivatives(s2, u)  # type: ignore[arg-type]
        s3 = tuple(si + 0.5 * dt * ki for si, ki in zip(s, k2))
        k3 = self.derivatives(s3, u)  # type: ignore[arg-type]
        s4 = tuple(si + dt * ki for si, ki in zip(s, k3))
        k4 = self.derivatives(s4, u)  # type: ignore[arg-type]

        moi = [
            si + (dt / 6.0) * (a + 2.0 * b_ + 2.0 * c_ + d)
            for si, a, b_, c_, d in zip(s, k1, k2, k3, k4)
        ]
        self.state = State(*moi)
        return self.state

    # ----------------------------------------------------------------------

    def energy(self) -> float:
        """Tổng cơ năng — đại lượng phải bảo toàn khi không ma sát, không lực.

        Thế năng lấy mốc ở vị trí treo xuống, nên nó dương ở mọi tư thế khác.
        """
        p = self.p
        s = self.state
        m, l, I = p.body_mass_kg, p.com_height_m, p.body_inertia

        v_com_x = s.x_dot + l * s.theta_dot * math.cos(s.theta)
        v_com_y = -l * s.theta_dot * math.sin(s.theta)
        dong_nang = (
            0.5 * p.cart_mass_kg * s.x_dot * s.x_dot
            + 0.5 * m * (v_com_x * v_com_x + v_com_y * v_com_y)
            + 0.5 * I * s.theta_dot * s.theta_dot
        )
        the_nang = m * p.gravity * l * (1.0 + math.cos(s.theta))
        return dong_nang + the_nang

    @property
    def fallen(self) -> bool:
        """Robot đã ngã chưa — quá 45° thì không cứu được nữa."""
        return abs(self.state.theta) > math.radians(45.0)


@dataclass
class SensorModel:
    """Mô hình cảm biến quán tính: nhiễu nền và trôi điểm không.

    Có mặt ở đây vì nếu mô phỏng cho bộ điều khiển một tín hiệu hoàn hảo thì
    tham số chỉnh trên mô phỏng sẽ vô dụng trên robot thật — và cổng SIL sẽ
    cho qua đúng những bộ tham số nhạy nhiễu nhất.
    """

    angle_noise_rad: float = 0.0035     # ~0,2°
    rate_noise_rad_s: float = 0.02
    gyro_drift_rad_s2: float = 0.0008
    #: Trần trôi điểm không. Con quay hồi chuyển thật có độ trôi bị chặn (vài
    #: phần mười độ/giây với linh kiện MEMS phổ thông) chứ không tăng mãi. Bỏ
    #: trần này thì mọi kịch bản đủ dài đều thất bại vì một lý do không có
    #: thật, và cổng mô phỏng sẽ chặn nhầm những bộ tham số vốn dùng được.
    max_drift_rad_s: float = 0.02
    quantization_rad: float = 0.0       # đặt > 0 để mô phỏng lượng tử hóa ADC
    _drift: float = field(default=0.0, init=False)
    _seed: int = field(default=12345, init=False)

    def reset(self, seed: int = 12345) -> None:
        self._drift = 0.0
        self._seed = seed

    def _noise(self) -> float:
        """Bộ sinh số giả ngẫu nhiên tự viết, tất định theo hạt giống.

        Không dùng ``random`` toàn cục: hai lần chạy cùng kịch bản phải cho
        cùng kết quả, nếu không cổng SIL sẽ lúc đạt lúc không và mất tư cách
        cổng chặn.
        """
        self._seed = (1103515245 * self._seed + 12345) & 0x7FFFFFFF
        return (self._seed / 0x7FFFFFFF) * 2.0 - 1.0

    def measure(self, state: State, dt: float) -> tuple[float, float]:
        self._drift += self.gyro_drift_rad_s2 * dt
        self._drift = min(self._drift, self.max_drift_rad_s)
        goc = state.theta + self.angle_noise_rad * self._noise()
        toc_do = state.theta_dot + self.rate_noise_rad_s * self._noise() + self._drift
        if self.quantization_rad > 0:
            goc = round(goc / self.quantization_rad) * self.quantization_rad
        return goc, toc_do


@dataclass
class ActuatorModel:
    """Mô hình động cơ bước: trần tốc độ bước và trượt bước khi quá tải."""

    #: Trần tốc độ bước, suy từ ràng buộc ``motor_response_us: 50`` của dự án:
    #: 50 µs mỗi bước → 20 kHz. Đây là chỗ ràng buộc cứng của công đoạn A1 đi
    #: vào mô phỏng — nếu bộ điều khiển đòi tốc độ cao hơn thì trên thiết bị
    #: thật nó sẽ trượt bước, và mô phỏng phải phản ánh đúng điều đó.
    max_step_rate_hz: float = 20000.0
    steps_per_rev: float = 200.0 * 16.0   # vi bước 1/16
    wheel_radius_m: float = 0.0425
    torque_limit_n: float = 3.0
    #: Vượt trần tốc độ bao nhiêu phần thì bắt đầu trượt bước.
    slip_margin: float = 1.15
    steps_emitted: int = field(default=0, init=False)
    slips: int = field(default=0, init=False)

    def reset(self) -> None:
        self.steps_emitted = 0
        self.slips = 0

    def apply(self, command_n: float, state: State, dt: float) -> float:
        """Chuyển lệnh lực thành lực thực tế, có kể trượt bước và trần lực."""
        luc = max(-self.torque_limit_n, min(self.torque_limit_n, command_n))

        # Tốc độ bước cần thiết để đạt vận tốc xe hiện tại.
        v = abs(state.x_dot)
        buoc_moi_giay = v / (2.0 * math.pi * self.wheel_radius_m) * self.steps_per_rev
        self.steps_emitted += int(buoc_moi_giay * dt)

        if buoc_moi_giay > self.max_step_rate_hz * self.slip_margin:
            self.slips += 1
            luc *= 0.35   # trượt bước: mất phần lớn lực kéo
        return luc


# --------------------------------------------------------------------------
# Điểm vào mà bộ chạy mô phỏng của engine gọi tới
# --------------------------------------------------------------------------
#
# Engine chỉ biết ba hàm dưới đây; nó không biết "con lắc ngược" là gì. Một dự
# án khác cung cấp ba hàm cùng tên với mô hình vật lý của riêng nó là chạy được
# ngay trên cùng bộ khung (NFR-05).


def create_plant(profile: dict[str, Any] | None = None) -> InvertedPendulum:
    """Dựng đối tượng vật lý từ hồ sơ phần cứng của dự án."""
    tham_so = (
        PendulumParams.from_hardware_profile(profile) if profile else PendulumParams()
    )
    return InvertedPendulum(tham_so)


def create_sensor(overrides: dict[str, Any] | None = None) -> SensorModel:
    """Dựng mô hình cảm biến; kịch bản có thể ghi đè từng tham số."""
    cam_bien = SensorModel()
    for ten, gia_tri in (overrides or {}).items():
        if hasattr(cam_bien, ten):
            setattr(cam_bien, ten, float(gia_tri))
    return cam_bien


def create_actuator(profile: dict[str, Any] | None = None) -> ActuatorModel:
    co_khi = dict((profile or {}).get("mechanics") or {})
    return ActuatorModel(
        wheel_radius_m=float(co_khi.get("wheel_radius_m", 0.0425))
    )
