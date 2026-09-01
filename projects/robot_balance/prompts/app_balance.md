---
id: app_balance
description: Giao thức khởi động bằng tiếng bíp và vòng cân bằng 4 ms, theo mã tham chiếu đã chạy được của bộ kit
---
### Giao thức khởi động — YÊU CẦU, không phải gợi ý

| Trạng thái | Còi | Máy làm | Người làm |
|---|---|---|---|
| `CHO_NUT` | **1 bíp** khi có điện | đợi nút | bật nguồn |
| `HIEU_CHINH` | **5 bíp** rải đều | đo và chốt MỌI số hiệu chỉnh | **giữ robot THẲNG ĐỨNG** |
| `SAN_SANG` | **2 bíp** liền | vào vòng cân bằng | **thả tay** |
| `CAN_BANG` | im | giữ thăng bằng | — |
| `NGA` | im | dừng động cơ, xoá tích phân | dựng lại, bấm nút |

Ba mốc bíp là giao diện người–máy DUY NHẤT của robot này. Người thả tay theo
tiếng bíp thứ ba, nên **2 bíp phải kêu SAU khi mọi số hiệu chỉnh đã chốt và
vòng điều khiển đã sẵn sàng**, không phải trước.

### Vì sao hiệu chỉnh lúc người đang giữ robot đứng

Mã tham chiếu đo số cân bằng bằng một chương trình RIÊNG (`V0`), người chép số
trên màn hình rồi gõ tay vào chương trình chính:

```c
int acc_calibration_value = 376;   // lấy từ V0
```

Một hằng số chép tay là hằng số sai ngay khi ai đó tháo cảm biến lắp lại, đổi
pin, hay siết lại con ốc. Đo ngay lúc người giữ robot ở đúng tư thế cân bằng
làm số ấy **đo lại mỗi lần bật máy**, và đo đúng cái cần đo.

Trong `HIEU_CHINH` chốt cả hai nhóm, mỗi nhóm là TRUNG BÌNH nhiều mẫu liên
tiếp (tay người có rung — mã tham chiếu lấy 500 mẫu cách nhau 3700 µs, ~1,9 s):

* **độ trôi con quay hồi chuyển** — trừ khỏi mọi số đọc sau đó;
* **mốc gia tốc kế ở tư thế đứng** — chính là thứ `V0` in ra cho người chép.

### Vòng chính — 4 ms, đúng công thức mã tham chiếu

* Góc từ con quay: `angle += gyro_pitch_raw * 0.000031` mỗi vòng.
  Hằng số ấy là `1 / (131 LSB/(°/s) × 250 Hz)` ở dải ±250 °/s — nó GẮN với
  chu kỳ 4 ms, đổi chu kỳ là phải đổi nó.
* Góc từ gia tốc: `asin(raw / 8200) * 57.296` ở dải ±4 g.
* Lọc bù: `angle = angle * 0.9996 + angle_acc * 0.0004`.
* PID: gọi `logic_pid` (xem luật riêng của module ấy).
* Bù phi tuyến trước khi ra xung: `out > 0 → 405 - (1/(out + 9)) * 5500`,
  đối xứng cho chiều âm; rồi `motor = 400 - out` (và `-400 - out` chiều âm).
* Ngã: `|angle| > 30°` → dừng động cơ, xoá tích phân, sang `NGA`.

Cấu hình cảm biến, đúng thứ tự mã tham chiếu dùng: `PWR_MGMT_1 = 0x00`
(đánh thức), `GYRO_CONFIG = 0x00` (±250 °/s), `ACCEL_CONFIG = 0x08` (±4 g),
`CONFIG = 0x03` (lọc thông thấp ~43 Hz).

Giá trị `motor` giao cho `drv_stepper`; cách nó thành xung là việc của module
ấy, không phải của app.

### Bốn chỗ dễ sai

1. **Bíp không được chặn vòng điều khiển.** Không dùng vòng chờ bận; đếm nhịp.
2. **Nút phải chống dội 20 ms và bắt SƯỜN nhấn, không bắt MỨC** — giữ nút
   không được kích hoạt lại việc hiệu chỉnh.
3. **Vào `CAN_BANG` phải nạp góc khởi đầu bằng góc gia tốc kế**, không nạp 0.
   Nạp 0 là nói dối bộ lọc rằng robot đang thẳng đứng hoàn hảo.
4. **`NGA` không tự thoát.** Ra khỏi nó là quyết định của người: bấm nút. Tự
   đứng dậy khi góc tình cờ về gần 0 là bật động cơ trong tay ai đó.
