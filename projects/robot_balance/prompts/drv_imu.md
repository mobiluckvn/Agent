---
id: drv_imu
description: Đọc MPU6050 và tính góc nghiêng theo đúng công thức mã tham chiếu — trục Z, dải ±4g/±250dps, chu kỳ 4 ms
---
Hiện thực **đúng** phần đọc cảm biến và tính góc trong
`sources/.../V3_Balancing_Robot_PID_App.ino`. Mã ấy chạy được trên chính cái
bo này; đừng sáng tác lại.

### Trục nào đo cái gì — đây là chuyện GÁ, không suy ra được

* Góc nghiêng lấy từ **ACCEL_Z** (`0x3F`), KHÔNG phải ACCEL_X.
* Tốc độ góc lấy từ **GYRO_Y** (`0x45`), tức cặp byte THỨ HAI khi đọc 4 byte
  bắt đầu ở `0x43`.

Chọn nhầm trục là một lựa chọn hợp lý trên giấy và sai trên bàn: mã dịch sạch,
bài kiểm xanh, robot ngã. Không cổng phần mềm nào bắt được.

### Dải đo, và những hằng số gắn chặt với nó

```c
PWR_MGMT_1  (0x6B) = 0x00   // đánh thức
GYRO_CONFIG (0x1B) = 0x00   // ±250 °/s  → 131 LSB/(°/s)
ACCEL_CONFIG(0x1C) = 0x08   // ±4 g      → 8192 LSB/g
CONFIG      (0x1A) = 0x03   // lọc thông thấp ~43 Hz
```

Đổi dải đo mà quên đổi hằng số quy đổi là sai hệ số góc, và sai hệ số góc thì
bộ tham số PID đã chỉnh không còn đúng nữa.

### Công thức, nguyên văn

```c
angle_acc  = asin((float)accel_z / 8200.0) * 57.296;   // độ
angle_gyro += gyro_y_raw * 0.000031;                   // mỗi vòng 4 ms
angle_gyro  = angle_gyro * 0.9996 + angle_acc * 0.0004;
```

* `8200` là hằng số của mã tham chiếu cho dải ±4 g (xấp xỉ 8192), kèm kẹp số
  đọc trong `±8200` trước khi lấy `asin`.
* `0.000031` = `1 / (131 × 250 Hz)`. Nó **gắn với chu kỳ 4 ms**: đổi chu kỳ là
  phải đổi số này. Dùng `10/131` là ngầm giả định 10 ms, và góc sẽ trôi 2,5 lần.
* Hệ số lọc bù `0.9996 / 0.0004` cũng gắn với 4 ms. Đừng thay bằng `0.98/0.02`.

`constraints.yaml` v2 cho phép số thực ngoài ngắt, nên viết thẳng như trên.

### Đọc cảm biến KHÔNG được chặn vòng điều khiển

Bus dùng `drv_i2c` chạy bằng ngắt. Module này là một máy trạng thái: mỗi lần
`imu_update()` được gọi thì tiến một bước, không chờ bận. Dịch kèm
`src/drv_i2c.c` khi viết bài kiểm; đừng viết hàm giả cho nó.

Một lượt đọc hỏng (bus báo lỗi) thì giữ nguyên góc cũ và thử lại ở vòng sau —
đừng nhét số 0 vào, vì 0 nghĩa là "robot đang thẳng đứng hoàn hảo".

### Bài kiểm phải chứng minh

* trình tự khởi động ghi ĐÚNG bốn thanh ghi trên với ĐÚNG bốn giá trị;
* lượt đọc lấy dữ liệu từ đúng vị trí byte của ACCEL_Z và GYRO_Y;
* cùng một số đọc gia tốc cho ra cùng một góc, và dấu đúng chiều;
* bus báo lỗi thì góc KHÔNG nhảy về 0.
