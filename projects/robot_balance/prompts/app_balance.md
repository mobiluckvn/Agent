---
id: app_balance
description: Giao thức khởi động bằng tiếng bíp và vòng cân bằng 4 ms, theo mã tham chiếu đã chạy được của chính bộ kit
---
### Giao thức khởi động — đây là YÊU CẦU, không phải gợi ý

| Trạng thái | Còi | Việc của máy | Việc của người |
|---|---|---|---|
| `CHO_NUT` | **1 bíp** ngay sau khi có điện | đợi nút | bật nguồn, đặt robot sao cũng được |
| `HIEU_CHINH` | **5 bíp**, rải đều suốt quá trình | đo và chốt MỌI số hiệu chỉnh | **giữ robot THẲNG ĐỨNG** cho tới khi hết bíp |
| `SAN_SANG` | **2 bíp** liền | bắt đầu chạy vòng cân bằng | **thả tay ra** |
| `CAN_BANG` | im | giữ thăng bằng | — |
| `NGA` | im | dừng động cơ, xoá tích phân | dựng lại và bấm nút |

Ba mốc bíp là giao diện người–máy DUY NHẤT của robot này. Người thả tay theo
tiếng bíp thứ ba, nên **2 bíp phải kêu SAU khi mọi số hiệu chỉnh đã chốt và
vòng điều khiển đã sẵn sàng nhận mẫu**, không phải trước.

### Vì sao hiệu chỉnh lúc người đang giữ robot đứng

Mã tham chiếu của bộ kit đo số cân bằng bằng một chương trình RIÊNG (`V0`),
người chép số trên màn hình rồi gõ tay vào chương trình chính:

```
int acc_calibration_value = 376;   // Giá trị hiệu chỉnh gia tốc kế, lấy từ V0
```

Một hằng số chép tay là một hằng số sai ngay khi ai đó tháo cảm biến ra lắp
lại, đổi pin, hay siết lại con ốc. Hiệu chỉnh ngay lúc người đang giữ robot ở
đúng tư thế cân bằng làm số ấy **đo lại mỗi lần bật máy**, và nó đo đúng cái
cần đo: giá trị gia tốc kế TẠI điểm cân bằng thật của cái robot này, hôm nay.

Trong `HIEU_CHINH` phải chốt cả hai nhóm:

* **độ trôi con quay hồi chuyển** — trung bình nhiều mẫu liên tiếp; mã tham
  chiếu lấy 500 mẫu cách nhau 3700 µs (khoảng 1,9 s);
* **mốc gia tốc kế ở tư thế đứng** — trung bình số đọc trục thẳng đứng trong
  cùng khoảng thời gian ấy. Đây là thứ `V0` in ra màn hình cho người chép.

Lấy trung bình nhiều mẫu, không lấy một mẫu: tay người có rung.

### Vòng điều khiển — dùng lại đúng công thức đã chạy được

Bộ tham số và cấu trúc dưới đây lấy từ `V3_Balancing_Robot_PID_App.ino` của
chính bộ kit, đã chạy được trên chính cái bo này. **Không thay bằng bộ tham số
của `sim/controller.py`**: hai bên định nghĩa sai số khác nhau, đơn vị khác
nhau, và có `dt` nằm ở chỗ khác nhau — trộn hai bên lại thì robot không đứng.

* Chu kỳ vòng chính **4 ms** (250 Hz). Mọi hằng số dưới đây gắn với con số này.
* Góc từ con quay: `angle += gyro_pitch_raw * 0.000031` mỗi vòng — hằng số ấy
  là `1 / (131 LSB/(°/s) × 250 Hz)` ở dải ±250 °/s.
* Góc từ gia tốc: `asin(raw / 8200) × 57.296` ở dải ±4 g.
* Lọc bù: `angle = angle * 0.9996 + angle_acc * 0.0004`.
* PID: `kp = 12`, `ki = 0.4`, `kd = 10`; nhớ tích phân kẹp ±400; đầu ra kẹp
  ±400; vùng chết ±5.
* Bù phi tuyến động cơ trước khi ra xung:
  `out > 0 → 405 - (1/(out + 9)) * 5500`, và đối xứng cho chiều âm.
* Điểm đặt tự chỉnh: khi không có lệnh đi tới/lùi, dịch điểm cân bằng
  ±0,0015 mỗi vòng ngược chiều đầu ra — nó tự tìm điểm cân bằng thật.
* Ngã: `|angle| > 30°` → dừng động cơ, xoá tích phân, về `NGA`.

Cấu hình cảm biến, đúng thứ tự mã tham chiếu dùng: `PWR_MGMT_1 = 0x00` (đánh
thức), `GYRO_CONFIG = 0x00` (±250 °/s), `ACCEL_CONFIG = 0x08` (±4 g),
`CONFIG = 0x03` (lọc thông thấp ~43 Hz).

### Phát xung bước — ngắt 20 µs, đếm chứ không chia tần

Timer2, CTC, chia trước 8, `OCR2A = 39` → ngắt mỗi 20 µs. Trong ngắt, mỗi động
cơ có một bộ đếm: đếm tới ngưỡng thì nạp lại ngưỡng mới và đặt chiều; đếm bằng
1 thì kéo chân STEP lên; bằng 2 thì hạ xuống. Ngưỡng CÀNG NHỎ thì xung CÀNG
DÀY, tức động cơ CÀNG NHANH.

Chân: `STEP_R/DIR_R = PD5/PD4`, `STEP_L/DIR_L = PD7/PD6`. Không có chân enable
— A4988 bật cứng trên bo.

Chiều tiến của robot cần HAI mức DIR KHÁC NHAU vì hai động cơ lắp đối xứng
gương: trái mức 1, phải mức 0 (đã đo bằng mắt tại DS-07).

### Bốn điều dễ làm sai ở đây

1. **Bíp không được chặn vòng điều khiển.** Ở `CAN_BANG` còi im, nên chỉ cần
   lo điều này trong ba trạng thái đầu — nhưng đừng dùng vòng chờ bận trong
   cùng hàm chạy vòng 4 ms.
2. **Nút phải chống dội** (20 ms, theo `mybutton.h` của bộ kit) và phải bắt
   SƯỜN nhấn, không bắt MỨC — giữ nút không được kích hoạt lại việc hiệu chỉnh.
3. **Vào `CAN_BANG` phải nạp góc khởi đầu bằng góc gia tốc kế**, không nạp 0.
   Nạp 0 nghĩa là nói dối bộ lọc rằng robot đang thẳng đứng hoàn hảo.
4. **`NGA` không tự thoát.** Ra khỏi nó là một quyết định của người: bấm nút.
   Tự đứng dậy khi góc tình cờ về gần 0 là robot bật động cơ trong tay ai đó.
