---
id: app_balance
description: Máy trạng thái bíp và vòng cân bằng 4 ms, ghép năm driver đã merge
---
### Giao thức khởi động — YÊU CẦU, không phải gợi ý

| Trạng thái | Còi | Người làm |
|---|---|---|
| `CHO_NUT` | **1 bíp** khi có điện | bật nguồn, bấm nút |
| `HIEU_CHINH` | **5 bíp** rải đều | **giữ robot THẲNG ĐỨNG** |
| `SAN_SANG` | **2 bíp** liền | **thả tay** |
| `CAN_BANG` | im | — |
| `NGA` | im | dựng lại, bấm nút |

Người thả tay theo bíp thứ ba, nên **2 bíp kêu SAU khi hiệu chỉnh đã chốt**.

### Chữ ký PHẢI khớp bộ định thời của firmware

`eaa build` sinh `main()` với bộ định thời khai `void (*step)(void)`. Module
xuất ra ĐÚNG `void app_init(void)` và `void app_step(void)` — không tham số.

Bộ đếm mili giây trong `main.c` không xuất ra ngoài, nên `app_step()` TỰ đếm:
biến tĩnh cộng 4 mỗi lượt, dùng làm `now_ms` cho `buzzer_update()` và
`button_get_event()`.

App KHÔNG tự tính góc: `imu_get_tilt_angle()` đã hiệu chỉnh và lọc bù.
`drv_i2c` không nằm trong danh sách phụ thuộc nhưng app PHẢI gọi
`void i2c_tick(void)` — thiếu nó thì bus treo là treo luôn.

### Mỗi lượt `app_step()`, theo thứ tự

1. `i2c_tick()`;
2. bơm `imu_update()` tới khi trả `true` rồi DỪNG — đúng một mẫu mỗi nhịp, vì
   `0.000031` trong driver giả định thế. Trần vòng bơm là hằng số khai ở đầu
   tệp kèm cách tính. Hết trần mà chưa có mẫu thì BỎ QUA nhịp: không gọi PID;
3. `buzzer_update(now_ms)`, đọc nút, chạy máy trạng thái;
4. ở `CAN_BANG`: `out = pid_compute(imu_get_tilt_angle(), 0.0f, true)`, bù phi
   tuyến rồi `stepper_set_speed`.

Bù phi tuyến, nguyên văn mã tham chiếu: `out > 0 → 405 - (1/(out + 9)) * 5500`,
đối xứng cho chiều âm; rồi `motor = 400 - out` (và `-400 - out` chiều âm).

`HIEU_CHINH`: `imu_calibrate_begin()` một lần, mỗi nhịp vẫn bơm `imu_update()`,
chờ `imu_calibrate_busy()` false rồi `imu_calibrate_commit()`. Năm bíp rải đều
trong lúc gom (~1,9 s).

Ngã: `|góc| > 30°` → `stepper_set_speed(0, 0)`, `pid_compute(..., false)` để xoá
tích phân, sang `NGA`.

### Bốn chỗ dễ sai

1. **Nút bắt SƯỜN nhấn** (`BUTTON_EVENT_PRESSED`), không bắt mức.
2. **`NGA` không tự thoát.** Nút đưa về `CHO_NUT` để chạy lại TRỌN giao thức
   kể cả hiệu chỉnh — robot vừa ngã là lúc gá cảm biến dễ xê dịch nhất.
3. **ĐỪNG gọi `pid_set_tunings`.** `logic_pid` mang sẵn kp=12/ki=0.4/kd=10 đã
   chỉnh; gọi lại với số khác (nhất là 0) là xoá bộ số ấy và động cơ đứng im.
4. **Mất mẫu N nhịp liên tiếp → dừng động cơ, sang `NGA`.** Bỏ qua một nhịp là
   đúng; bỏ qua mãi thì bus chết cũng giữ nguyên lệnh động cơ cuối và không ai
   phát hiện robot đã ngã. N là hằng số khai ở đầu tệp.

### Bài kiểm phải chứng minh

* đủ năm trạng thái, đi đúng thứ tự trên;
* số bíp đúng 1 / 5 / 2 ở ba mốc;
* `SAN_SANG` chỉ tới SAU khi `imu_calibrate_commit()` đã gọi;
* `i2c_tick()` gọi đúng một lần mỗi nhịp;
* mỗi nhịp lấy đúng MỘT mẫu, và hết trần không có mẫu thì KHÔNG gọi `pid_compute`;
* `|góc| > 30°` cho `stepper_set_speed(0, 0)` và sang `NGA`;
* ở `NGA`, góc về 0 KHÔNG tự đưa robot chạy lại; nút đưa về `CHO_NUT`;
* mất mẫu N nhịp liên tiếp cho `stepper_set_speed(0, 0)` và sang `NGA`.
