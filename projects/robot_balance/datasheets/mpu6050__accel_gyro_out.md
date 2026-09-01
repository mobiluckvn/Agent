---
id: ds-032
device: mpu6050
peripheral: imu
registers: [ACCEL_XOUT_H, GYRO_XOUT_H, ACCEL_CONFIG, GYRO_CONFIG]
topic: Thanh ghi số đo và dải đo
source: MPU-6000/MPU-6050 Register Map rev. 4.2, tr.29-31
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000005
status: approved
note: >-
  CHƯA duyệt G2 — còn phải đối chiếu hệ số nhạy của dải ±4g với bản gốc.
  Trạng thái proposed nên chunk này không được truy xuất vào prompt.
approved_by: Vũ Trí Công
approved_at: '2026-09-01T11:24:37+00:00'
---

## MPU6050 — thanh ghi số đo

| Thanh ghi | Địa chỉ | Ý nghĩa |
|---|---|---|
| ACCEL_XOUT_H | 0x3B | Byte cao gia tốc trục X; 14 byte liên tiếp là toàn bộ số đo |
| GYRO_XOUT_H | 0x43 | Byte cao vận tốc góc trục X |
| ACCEL_CONFIG | 0x1C | AFS_SEL bit 4:3 chọn dải ±2/4/8/16 g |
| GYRO_CONFIG | 0x1B | FS_SEL bit 4:3 chọn dải ±250/500/1000/2000 °/s |

Hệ số nhạy dải ±2 g là 16384 LSB/g; dải ±250 °/s là 131 LSB/(°/s).
Số đo là số bù hai 16 bit, byte cao đọc trước.
