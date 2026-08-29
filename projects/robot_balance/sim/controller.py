"""Bộ điều khiển tham chiếu cho chế độ Model-in-the-Loop — dự án robot_balance.

Sản phẩm của công đoạn D4 ở dạng mô hình: PID rời rạc kèm bộ lọc bù, viết bằng
Python để quét tham số hàng loạt (TC-13). Firmware thật trên thiết bị là bản C
số nguyên do quy trình sinh ra; bản Python này KHÔNG thay thế nó.

Ranh giới cần nói rõ, đúng như công đoạn C2 đòi hỏi ("người vạch ranh giới:
cái gì tin được từ mô phỏng, cái gì bắt buộc đo trên thiết bị thật"):

* Mô phỏng với bộ điều khiển này kiểm chứng được **cấu trúc điều khiển và dải
  tham số** — chọn sai cấu trúc thì tham số nào cũng vô nghĩa.
* Nó KHÔNG kiểm chứng được mã thao tác thanh ghi, thời gian ngắt, hiệu ứng làm
  tròn của số học số nguyên, hay nhiễu điện. Những thứ đó thuộc cổng SIL (chạy
  chính firmware qua lớp giả lập) và cuối cùng là Gate G4 trên robot thật.

Chống hai lỗi kinh điển mà đề cương nêu đích danh:

* **Integral windup** — khi lệnh đã bão hòa, thành phần tích phân ngừng cộng
  dồn, nếu không nó sẽ tích một khoản "nợ" mà hệ không thể trả và gây vọt lố.
* **Derivative kick** — đạo hàm lấy theo SỐ ĐO chứ không theo sai số; đổi
  điểm đặt sẽ tạo một xung đạo hàm vô nghĩa nếu lấy theo sai số.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComplementaryFilter:
    """Bộ lọc bù: hợp nhất góc từ gia tốc kế và tốc độ từ con quay hồi chuyển.

    Chọn bộ lọc bù thay vì Kalman theo đúng ràng buộc của dự án: nó chỉ tốn
    vài phép nhân, chạy được trong ngân sách của một vòng điều khiển 10 ms trên
    lõi 8 bit, và tham số duy nhất của nó (hằng số thời gian) giải thích được
    bằng vật lý chứ không phải bằng ma trận hiệp phương sai.
    """

    tau: float = 0.75      # hằng số thời gian, giây
    angle: float = 0.0

    def reset(self, angle: float = 0.0) -> None:
        self.angle = angle

    def update(self, angle_meas: float, rate_meas: float, dt: float) -> float:
        alpha = self.tau / (self.tau + dt)
        self.angle = alpha * (self.angle + rate_meas * dt) + (1.0 - alpha) * angle_meas
        return self.angle


@dataclass
class PidController:
    """PID rời rạc có chống bão hòa tích phân và chống xung đạo hàm."""

    kp: float = 38.0
    ki: float = 90.0
    kd: float = 3.4
    setpoint: float = 0.0
    output_limit: float = 3.0
    #: Vòng ngoài giữ vận tốc — hệ số quy từ vận tốc sang góc nghiêng đặt.
    #:
    #: Vì sao phải có: một sai lệch góc tĩnh dù nhỏ (do trôi điểm không của con
    #: quay hồi chuyển) khiến vòng trong ra lệnh lực không đổi, và xe tăng tốc
    #: mãi cho tới lúc trượt bước rồi ngã. Chính bộ mô phỏng đã phát hiện điều
    #: này ở kịch bản chạy dài — một khoảng trống về CẤU TRÚC điều khiển, thứ
    #: không bộ tham số nào cứu được. Vòng ngoài nghiêng nhẹ về phía ngược
    #: chiều chuyển động để triệt tiêu vận tốc.
    speed_gain: float = 0.25        # rad trên mỗi m/s
    max_lean_rad: float = 0.05      # trần góc đặt, ~2,9°
    #: Trần riêng cho thành phần tích phân — hàng rào thứ hai sau anti-windup.
    integral_limit: float = 1.5
    filter: ComplementaryFilter = field(default_factory=ComplementaryFilter)

    _integral: float = field(default=0.0, init=False)
    _last_measurement: float = field(default=0.0, init=False)
    _primed: bool = field(default=False, init=False)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "PidController":
        return cls(
            kp=float(params.get("kp", 38.0)),
            ki=float(params.get("ki", 90.0)),
            kd=float(params.get("kd", 3.4)),
            # Hệ số vòng ngoài cũng phải quét được: chính nó — chứ không phải
            # bộ ba PID — đặt sàn cho thời gian ổn định, và điều đó chỉ lộ ra
            # khi cho nó vào bảng quét.
            speed_gain=float(params.get("speed_gain", 0.25)),
        )

    def reset(self) -> None:
        self._integral = 0.0
        self._last_measurement = 0.0
        self._primed = False
        self.filter.reset()

    def step(self, measurement: dict[str, float], dt: float) -> float:
        """Một chu kỳ điều khiển. ``measurement`` mang ``angle`` và ``rate``.

        **Quy ước dấu — chỗ dễ sai nhất của bài toán này.** Với con lắc ngược,
        muốn kéo thân về thẳng đứng thì xe phải chạy VỀ PHÍA đang nghiêng để
        chui xuống dưới trọng tâm. Tuyến tính hóa phương trình cho thấy điều
        đó: ``(I+m·l²)·θ̈ = m·g·l·θ − m·l·ẍ``, nên θ̈ chỉ âm khi ``ẍ > g·θ``.
        Sai số vì thế lấy là ``góc − điểm đặt``, không phải ``điểm đặt − góc``
        như phản hồi âm thông thường.

        Đây đúng là loại lỗi mà mô phỏng bắt được còn đọc mã thì không: mã sai
        dấu vẫn biên dịch sạch, vẫn qua phân tích tĩnh, và chỉ lộ ra khi robot
        lao đi theo hướng ngược lại rồi ngã.
        """
        goc = self.filter.update(
            float(measurement.get("angle", 0.0)),
            float(measurement.get("rate", 0.0)),
            dt,
        )

        # Vòng ngoài: nghiêng ngược chiều chuyển động để hãm vận tốc trôi.
        van_toc = float(measurement.get("speed", 0.0))
        diem_dat = self.setpoint - self.speed_gain * van_toc
        diem_dat = max(-self.max_lean_rad, min(self.max_lean_rad, diem_dat))

        sai_so = goc - diem_dat

        # Đạo hàm theo SỐ ĐO chứ không theo sai số — chống derivative kick khi
        # đổi điểm đặt. Cùng dấu với sai số theo quy ước ở trên.
        if not self._primed:
            self._last_measurement = goc
            self._primed = True
        dao_ham = (goc - self._last_measurement) / dt if dt > 0 else 0.0
        self._last_measurement = goc

        tich_phan_thu = self._integral + sai_so * dt
        tich_phan_thu = max(-self.integral_limit, min(self.integral_limit, tich_phan_thu))

        lenh_thu = self.kp * sai_so + self.ki * tich_phan_thu + self.kd * dao_ham

        # Anti-windup: chỉ cộng dồn tích phân khi lệnh CHƯA bão hòa.
        if abs(lenh_thu) < self.output_limit:
            self._integral = tich_phan_thu
            lenh = lenh_thu
        else:
            lenh = self.kp * sai_so + self.ki * self._integral + self.kd * dao_ham

        return max(-self.output_limit, min(self.output_limit, lenh))


def create(params: dict[str, Any] | None = None) -> PidController:
    """Điểm vào mà bộ chạy mô phỏng gọi tới."""
    return PidController.from_params(params or {})
