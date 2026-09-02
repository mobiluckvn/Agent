---
id: drv_imu
description: Đọc MPU6050 và tính góc nghiêng theo đúng công thức mã tham chiếu — trục Z, dải ±4g/±250dps, chu kỳ 4 ms
---
Theo ĐÚNG phần đọc cảm biến và tính góc của
`sources/.../V3_Balancing_Robot_PID_App.ino` — mã đã chạy trên chính bo này.

### Trục — chuyện GÁ, không suy từ tài liệu chip

* Góc nghiêng: **ACCEL_Z** (`0x3F`), KHÔNG phải ACCEL_X.
* Tốc độ góc: **GYRO_Y** (`0x45`).

### Dải đo và công thức, nguyên văn

```c
PWR_MGMT_1  (0x6B) = 0x00   // đánh thức
GYRO_CONFIG (0x1B) = 0x00   // ±250 °/s  → 131 LSB/(°/s)
ACCEL_CONFIG(0x1C) = 0x08   // ±4 g      → 8192 LSB/g
CONFIG      (0x1A) = 0x03   // lọc thông thấp ~43 Hz

angle_acc  = asin((float)accel_z / 8200.0) * 57.296;   // kẹp accel_z ở ±8200
angle_gyro += gyro_y_raw * 0.000031;                   // mỗi vòng 4 ms
angle_gyro  = angle_gyro * 0.9996 + angle_acc * 0.0004;
```

`0.000031` và `0.9996/0.0004` GẮN với chu kỳ 4 ms; `10/131` là ngầm giả định
10 ms và góc trôi 2,5 lần. Ba số ấy KHÔNG được đổi để bài kiểm vừa số kỳ vọng —
bài kiểm tính kỳ vọng TỪ công thức. Số thực ngoài ngắt được phép.

### Nhịp và bus

`drv_i2c` chạy bằng ngắt; module này là máy trạng thái, mỗi `imu_update()` tiến
một bước, không chờ bận. Bài kiểm dịch kèm `src/drv_i2c.c` THẬT.

`imu_update()` trả `bool`: true đúng ở lượt vừa tích phân một mẫu mới, false ở
mọi lượt khác. Vòng điều khiển bơm tới khi thấy true rồi dừng — `0.000031` giả
định ĐÚNG MỘT lần tích phân mỗi 4 ms, mà một lượt đọc cần vài lượt gọi và số ấy
đổi theo lúc ngắt nổ.

Bus lỗi thì GIỮ NGUYÊN góc cũ, thử lại vòng sau. Đừng nhét 0 vào: 0 nghĩa là
"robot thẳng đứng hoàn hảo". `imu_init()` gọi `i2c_init()`.

### Hiệu chỉnh — BẮT BUỘC

`app_balance` chốt hai số mỗi lần bật máy, lúc người giữ robot thẳng đứng:

```c
void imu_calibrate_begin(void);   // xoá tích luỹ, bắt đầu gom mẫu
bool imu_calibrate_busy(void);    // còn đang gom thì true
void imu_calibrate_commit(void);  // chốt trung bình các mẫu đã gom
```

* **Trôi con quay** — trung bình `gyro_y` thô, TRỪ khỏi mọi số đọc sau đó,
  TRƯỚC khi nhân `0.000031`.
* **Mốc gia tốc đứng** — trung bình `accel_z` thô; sau đó dùng `accel_z - mốc`
  trước khi vào `asin`.
* `commit` đặt góc về **0**: tư thế lúc gom mẫu LÀ mốc không, nên `accel_z-mốc`
  bằng 0. Đừng suy góc từ số THÔ của mốc — gá lệch bao nhiêu thì robot tin mình
  nghiêng bấy nhiêu, và lọc bù cần ~10 s mới gột.

Gom 500 mẫu (theo mã tham chiếu, ~1,9 s), hằng số khai ở đầu tệp.

### Bài kiểm phải chứng minh

* khởi động ghi ĐÚNG bốn thanh ghi trên với ĐÚNG bốn giá trị;
* lượt đọc lấy đúng vị trí byte của ACCEL_Z và GYRO_Y;
* trong một lượt đọc trọn vẹn, `imu_update()` trả `true` ĐÚNG MỘT lần;
* bus lỗi thì góc KHÔNG nhảy về 0 và lượt gọi ấy trả `false`;
* gom mẫu với `gyro_y` lệch một hằng số rồi `commit` thì góc NGỪNG trôi;
* ngay sau `commit`, vẫn ở tư thế gom mẫu, góc bằng **0** — kể cả khi số thô
  lúc gom lệch xa 0 (gá nghiêng);
* rồi cho `accel_z` lệch khỏi mốc một lượng ứng với góc đã biết thì lượt đọc kế
  trả về đúng góc ấy.
