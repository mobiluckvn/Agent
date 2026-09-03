---
id: drv_imu
description: Đọc MPU6050 và tính góc nghiêng theo đúng công thức mã tham chiếu — trục Z, dải ±4g/±250dps, chu kỳ 4 ms
---
Theo ĐÚNG phần đọc cảm biến và tính góc của V3 — mã đã chạy trên bo này.

### Trục — chuyện GÁ, đã ĐO trên bo

* Góc nghiêng: **ACCEL_Z** (`0x3F`). Tốc độ góc: **GYRO_Y** (`0x45`).

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

Bus lỗi thì GIỮ NGUYÊN góc cũ (0 nghĩa là "thẳng đứng hoàn hảo").
`imu_init()` gọi `i2c_init()`.

### Hai đại lượng hiệu chỉnh, KHÁC BẢN CHẤT — theo đúng V3

**Mốc gia tốc là HẰNG SỐ, khai ở đầu tệp:**

```c
#define ACCEL_BALANCE_OFFSET  (-535)   /* hồ sơ phần cứng, đo ở ±4 g */
```

Hình học của robot, không đổi giữa hai lần bật. Mọi số đọc dùng
`accel_z - ACCEL_BALANCE_OFFSET` trước khi vào `asin`. **KHÔNG đo lại lúc bật
máy** — đo ở tư thế tay người giữ là tuyên bố một tư thế nghiêng bất kỳ là
"không độ", và cổng ±0,5° của `app_balance` mất hết ý nghĩa.

**Trôi con quay thì PHẢI đo mỗi lần bật** — nó đổi theo nhiệt độ:

```c
void imu_calibrate_begin(void);   // bắt đầu gom mẫu gyro
bool imu_calibrate_busy(void);    // còn đang gom thì true
void imu_calibrate_commit(void);  // chốt trung bình
```

Gom **500 mẫu** `gyro_y` thô (V3: 500 vòng cách nhau 3700 µs), lấy trung bình,
TRỪ khỏi mọi số đọc sau đó TRƯỚC khi nhân `0.000031`. Robot chỉ cần đứng YÊN,
không cần thẳng.

`commit` đặt góc bằng `angle_acc` — góc THẬT tính từ mốc cố định, như V3.
Đặt về 0 là nói dối bộ lọc.

### Bài kiểm phải chứng minh

* khởi động ghi ĐÚNG bốn thanh ghi trên với ĐÚNG bốn giá trị;
* lượt đọc lấy đúng vị trí byte của ACCEL_Z và GYRO_Y;
* trong một lượt đọc trọn vẹn, `imu_update()` trả `true` ĐÚNG MỘT lần;
* bus lỗi thì góc KHÔNG nhảy về 0 và lượt gọi ấy trả `false`;
* gom mẫu với `gyro_y` lệch một hằng số rồi `commit` thì góc NGỪNG trôi;
* `accel_z` bằng đúng `ACCEL_BALANCE_OFFSET` cho góc **0**; lệch khỏi nó một
  lượng ứng với góc đã biết thì trả về đúng góc ấy — kể cả TRƯỚC khi hiệu chỉnh,
  vì mốc là hằng số chứ không phải thứ đo lúc chạy.
