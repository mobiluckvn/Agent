---
id: app_balance
description: Máy trạng thái bíp và vòng cân bằng 4 ms, ghép năm driver đã merge
---
### Giao thức khởi động — YÊU CẦU, không phải gợi ý

`CHO_NUT` **1 bíp** khi có điện, đợi nút → `HIEU_CHINH` **5 bíp** rải đều,
người giữ robot thẳng đứng → `SAN_SANG` **2 bíp** liền, người thả tay →
`CAN_BANG` im → `NGA` im, đợi nút.

### Chữ ký PHẢI khớp bộ định thời của firmware

`eaa build` sinh `main()` với bộ định thời khai `void (*step)(void)`. Module
xuất ra ĐÚNG `void app_init(void)` và `void app_step(void)` — không tham số.
Bộ đếm ms trong `main.c` không xuất ra ngoài, nên `app_step()` TỰ đếm: biến
tĩnh cộng 4 mỗi lượt, dùng làm `now_ms` cho còi và nút.

`app_init()` PHẢI gọi `imu_init()`, `stepper_init()`, `buzzer_init()`,
`button_init()` — thiếu là firmware CÂM hoàn toàn.

`drv_i2c` không nằm trong danh sách phụ thuộc nhưng app PHẢI gọi
`void i2c_tick(void)`.

### Mỗi lượt `app_step()`, theo thứ tự

1. `i2c_tick()`;
2. bơm `imu_update()` tới khi trả `true` rồi DỪNG — đúng một mẫu mỗi nhịp.
   `#define IMU_PUMP_LIMIT 20000`: đây là **lưới chặn treo, KHÔNG phải ngân
   sách thời gian**. Vòng bơm phải chờ đủ ~430 µs của một lượt đọc 14 byte ở
   400 kHz và tự thoát khi mẫu về. Trần 129 đã làm robot ngã (đo 02/09);
3. `buzzer_update(now_ms)`, đọc nút, chạy máy trạng thái;
4. ở `CAN_BANG`: `out = pid_compute(imu_get_tilt_angle(), 0.0f, true)`, bù phi
   tuyến rồi `stepper_set_speed`.

Bù phi tuyến, nguyên văn mã tham chiếu: `out > 0 → 405 - (1/(out + 9)) * 5500`,
đối xứng cho chiều âm; rồi `motor = 400 - out` (và `-400 - out` chiều âm).

`HIEU_CHINH`: `imu_calibrate_begin()` một lần, mỗi nhịp vẫn bơm `imu_update()`,
chờ `imu_calibrate_busy()` false rồi `imu_calibrate_commit()`.

**Trạng thái này phải KÊU LÊN khi hỏng.** Quá `CALIB_TIMEOUT_MS` (hằng số đầu
tệp, 10000) mà còn `busy` thì sang `NGA` và bíp **ba tiếng ngắn lặp lại**, khác
hẳn 1/5/2; nút cũng phải thoát được về `CHO_NUT`.

`SAN_SANG` KHÔNG chuyển sang `CAN_BANG` theo thời gian. Nó chờ tới khi
`|imu_get_tilt_angle()| < 0.5` — robot THẬT SỰ đã thăng bằng — rồi mới bật PID,
đúng như V3. Vào vòng điều khiển lúc còn nghiêng là động cơ phóng đi trước khi
robot ở tư thế cứu được.

Ngã: `|góc| > 30°` → `stepper_set_speed(0, 0)`, `pid_compute(..., false)`, sang
`NGA`.

### Ba chỗ dễ sai

1. **`NGA` không tự thoát.** Nút đưa về `CHO_NUT`, chạy lại TRỌN giao thức.
2. **ĐỪNG gọi `pid_set_tunings`** — driver mang sẵn bộ hệ số đã chỉnh.
3. **Mất mẫu 10 nhịp liên tiếp → dừng động cơ, sang `NGA`.**

### Bài kiểm phải chứng minh

* `app_init()` gọi ĐỦ bốn hàm khởi tạo driver, mỗi hàm đúng một lần;
* đủ năm trạng thái, đi đúng thứ tự trên;
* số bíp đúng 1 / 5 / 2 ở ba mốc;
* `SAN_SANG` chỉ tới SAU khi `imu_calibrate_commit()` đã gọi, và chỉ rời sang
  `CAN_BANG` khi `|góc| < 0.5`, không phải theo thời gian;
* mỗi nhịp lấy đúng MỘT mẫu, hết trần không mẫu thì KHÔNG gọi `pid_compute`;
* hiệu chỉnh quá `CALIB_TIMEOUT_MS` cho nhịp bíp lỗi và sang `NGA`;
* nút trong `HIEU_CHINH` đưa về `CHO_NUT`;
* `|góc| > 30°` cho `stepper_set_speed(0, 0)` và sang `NGA`;
* mất mẫu N nhịp liên tiếp cho `stepper_set_speed(0, 0)` và sang `NGA`.
