---
id: ds-031
device: mpu6050
peripheral: imu
registers: [WHO_AM_I, PWR_MGMT_1, SMPLRT_DIV, CONFIG]
topic: Nhận dạng thiết bị và trình tự khởi động
source: MPU-6000/MPU-6050 Register Map rev. 4.2, tr.40-45
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000004
status: approved
---

## MPU6050 — nhận dạng và khởi động

| Thanh ghi | Địa chỉ | Giá trị | Ý nghĩa |
|---|---|---|---|
| WHO_AM_I | 0x75 | 0x68 | Chỉ 6 bit giữa có nghĩa; bit 0 và bit 7 luôn đọc ra 0 |
| PWR_MGMT_1 | 0x6B | 0x80 | Đặt DEVICE_RESET, tự xóa sau khi reset xong |
| PWR_MGMT_1 | 0x6B | 0x00 | Thoát chế độ ngủ, chọn nguồn xung nội 8 MHz |
| PWR_MGMT_1 | 0x6B | 0x01 | Thoát ngủ, chọn nguồn xung PLL theo trục X con quay (ổn định hơn) |
| SMPLRT_DIV | 0x19 | N | Tần số lấy mẫu = tần số ra con quay / (1 + N) |
| CONFIG | 0x1A | 0x03 | Bộ lọc thông thấp số 44 Hz, trễ nhóm 4,9 ms |

Địa chỉ thiết bị trên bus là 0x68 khi chân AD0 nối đất, 0x69 khi nối nguồn.

Sau khi thoát chế độ ngủ phải chờ ít nhất 100 ms trước khi đọc số đo đầu tiên;
đọc sớm hơn sẽ nhận dữ liệu chưa ổn định.
