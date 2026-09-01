# Tiếp tục từ đây — bàn giao phiên 01/09/2026

Mục tiêu đang đuổi: **robot đứng được**, theo giao thức khởi động bằng tiếng bíp
(1 bíp chờ nút → nút → 5 bíp hiệu chỉnh khi người giữ robot thẳng đứng → 2 bíp
thả tay → cân bằng).

## Trạng thái backlog

| Module | Trạng thái | Ghi chú |
|---|---|---|
| `drv_buzzer` | **merged** | bật/tắt mức PB2, không chặn, đúng còi chủ động |
| `drv_button` | **merged** | PINB4, kéo lên nội, chống dội 20 ms, bắt sườn nhấn |
| `drv_i2c` | **merged** | TWI master chạy bằng ngắt, 400 kHz |
| `drv_stepper` | **merged** | Timer2 CTC 20 µs, đếm ngưỡng, DIR trái=1/phải=0 |
| `drv_imu` | `handoff` | mã C ĐÚNG rồi; chỉ bài kiểm còn lệch (xem dưới) |
| `logic_pid` | `in_review` | bản cũ theo công thức fixed-point — **phải sinh lại** |
| `app_balance` | `todo` | máy trạng thái bíp + vòng 4 ms |
| `app_telemetry` | `todo` | cần cho đo nghiệm thu G4, chưa cần để robot đứng |
| `drv_uart` | `todo` | tồn từ bài UART cũ, không cần cho việc đứng |

Pha D. G1/G2 approved, G3 vừa bị từ chối cho `drv_imu`.

## Việc kế tiếp, theo đúng thứ tự

1. **`eaa gen drv_imu`** — lần chạy cuối cho mã C đúng: đọc chùm từ `0x3B` lấy
   byte [4:5] = ACCEL_Z, gyro Y, `0.000031`, `0.9996/0.0004`, `ACCEL_CONFIG=0x08`.
   Chỗ còn đỏ là **bài kiểm** tự đặt một con số kỳ vọng (`0.0429`) rồi không
   khớp. Đọc bài kiểm trước khi sinh lại: nếu mã C vẫn đúng như trên thì chỉ
   cần bài kiểm tính lại kỳ vọng từ chính công thức.
2. **`eaa gen logic_pid`** — bản đang `in_review` viết theo công thức Q8
   fixed-point của `sim/`; `prompts/logic_pid.md` nay đã đổi sang công thức
   nhà sản xuất (float, kp=12/ki=0.4/kd=10, kẹp ±400, vùng chết ±5).
3. **`eaa gen app_balance`** — máy trạng thái năm trạng thái + vòng 4 ms.
4. `eaa build` → `eaa flash` → thử đứng.

Nhớ: G3 chỉ giữ được hồ sơ của MỘT module. Duyệt hoặc từ chối xong mới sinh
module kế (SL-142 cưỡng chế điều này).

## Đã sửa trong phiên này — bảy lỗi engine chặn đường sinh mã

| | |
|---|---|
| SL-145 | Tiêu đề giả không giống thật: thanh ghi là macro nên `in_dll` không thấy; thiếu tên chân kiểu cũ `PD4` |
| SL-146 | Duyệt G3 một module là mở cửa ra khỏi cả pha D, và pha E đóng vòng sinh mã |
| SL-147 | Trần lớp vá chặn vòng tự sửa khi còn nửa ngân sách trống |
| SL-148 | Đường dẫn tiêu đề giả phụ thuộc việc mô hình nhớ gõ `-I` |
| SL-149 | Prompt vá mời mô hình HỎI, mà đường ống chỉ nhận bản vá — sáu lượt gọi bị đốt |
| SL-150 | Cổng phân tích tĩnh áp luật mã C lên tệp kiểm Python |
| SL-151 | Một lượt sinh hỏng để lại cây bẩn, khoá cứng lượt sau |

Cùng SL-140…144 ghi ở phiên trước đó trong cùng ngày.

## Tri thức đã nạp

* `ds-atme-gpio-01` — DDRB/PORTB/PINB (cổng B: còi PB2, nút PB4)
* `ds-atme-gpio-02` — DDRD/PORTD/PIND (cổng D: bốn chân xung bước)
* `ds-atme-timer2-01` — TCCR2A/B, OCR2A, TIMSK2, bảng chia trước RIÊNG của Timer2
* `ds-032` — gỡ treo bằng chính mã nhà sản xuất (hai con số độc lập xác nhận
  `GYRO_CONFIG=0x00` và `ACCEL_CONFIG=0x08`)

Hồ sơ phần cứng nay khai đủ: còi, nút, timer2, `tilt_axis` (accel Z / gyro Y),
dải đo, và bảng chân đã sửa sang PD4–PD7.

## Còn nợ

* **10 test E2E TC-15 đỏ** — prompt đổi thì băm đổi, bộ phát lại cố ý không bịa
  phản hồi. Ghi lại bằng `scripts/record_e2e_fixture.py` với mô hình thật.
* `stepper_set_speed` gọi `sei()` vô điều kiện thay vì khôi phục `SREG` — bật
  ngắt sớm nếu người gọi đang trong đoạn găng. Chưa chặn được gì, nhưng phải
  sửa trước khi có module khác gọi nó từ trong ngắt.
* `drv_i2c` không có quá hạn: bus treo thì trạng thái ở `BUSY` mãi. Lớp an toàn
  của `app_balance` (số đo bất động N chu kỳ) che được, nhưng đó là che chứ
  không phải sửa.
