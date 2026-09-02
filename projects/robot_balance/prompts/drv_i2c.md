---
id: drv_i2c
description: TWI master chạy bằng ngắt, 400 kHz — khởi tạo lại được và không kẹt cứng khi bus treo
---
Sinh lại module đã merge. Giữ NGUYÊN bốn hàm dưới đây, kể cả tên và chữ ký:
`drv_imu` đang gọi chúng, đổi là hỏng một module đã qua G3.

```c
void         i2c_init(void);
bool         i2c_write_async(uint8_t addr, const uint8_t *data, uint8_t len);
bool         i2c_read_async(uint8_t addr, uint8_t *data, uint8_t len);
i2c_status_t i2c_get_status(void);   // IDLE / BUSY / SUCCESS / ERROR
```

Phần lõi giữ như bản đang chạy: TWI master, `TWSR = 0x00` (chia trước 1),
`TWBR = 12` cho 400 kHz ở 16 MHz, `TWCR` bật `TWEN|TWIE`, toàn bộ chuyển trạng
thái nằm trong `ISR(TWI_vect)` theo mã trạng thái `TWSR & 0xF8`. Không chờ bận
ở bất kỳ đâu.

### Hai chỗ phải sửa

**1. `i2c_init()` ĐẶT LẠI trạng thái về `IDLE` và bỏ giao dịch đang dở.**

Bản hiện tại chỉ ghi `TWSR/TWBR/TWCR` rồi thôi. Đo được: sau một
`i2c_write_async` thành công, gọi `i2c_init()` thì `i2c_get_status()` vẫn trả
`BUSY`, và mọi `i2c_write_async` sau đó trả `false` — vĩnh viễn. Một driver bus
không khởi tạo lại được là driver kẹt cứng sau mỗi lần truyền dở dang, và trên
bo thì triệu chứng là "cảm biến im" chứ không phải một lỗi đọc được.

`i2c_init()` phải: phát STOP nếu đang giữ bus, xoá con trỏ đệm và bộ đếm, đặt
`i2c_status = IDLE`.

**2. Quá hạn cho giao dịch treo.**

Bus treo (dây chạm, thiết bị giữ SDA thấp) thì ngắt KHÔNG bao giờ nổ, nên
không có gì tự thoát ra được: trạng thái ở `BUSY` mãi. Thêm

```c
void i2c_tick(void);   // vòng điều khiển gọi mỗi 4 ms
```

Mỗi tick tăng bộ đếm khi đang `BUSY`; quá `I2C_TIMEOUT_TICKS` thì phát STOP,
đặt `i2c_status = ERROR` và trả bus về dùng được. Đặt `I2C_TIMEOUT_TICKS = 5`
(~20 ms): một giao dịch 14 byte ở 400 kHz mất ~350 µs, nên 20 ms là rộng rãi
mà vẫn kịp trước khi vòng cân bằng mất phương hướng.

Bộ đếm là `volatile` và bị ISR chạm tới. Đọc–sửa–ghi nó ngoài ngắt phải chặn
ngắt quanh đoạn găng, và **khôi phục `SREG`** chứ đừng `sei()` vô điều kiện —
người gọi có thể đang ở trong một đoạn găng khác.

### Bài kiểm phải chứng minh

* `i2c_init()` giữa lúc đang `BUSY` thì sau đó `i2c_get_status()` trả `IDLE`
  và `i2c_write_async` kế tiếp trả `true` — đây là bài kiểm của chỗ sửa 1, và
  nó phải ĐỎ trên bản cũ;
* trình tự ghi: START → SLA+W → thanh ghi → dữ liệu → STOP, đúng thứ tự, và
  `TWDR` mang đúng byte ở mỗi bước;
* trình tự đọc nhiều byte: ACK cho các byte trước, NACK cho byte cuối;
* NACK ở SLA+W cho `status == ERROR` và bus được nhả (STOP);
* treo giả lập: `i2c_write_async` rồi KHÔNG gọi ISR lần nào, gọi `i2c_tick()`
  đủ `I2C_TIMEOUT_TICKS` lần → `status == ERROR` và giao dịch mới bắt đầu được;
* chưa đủ số tick thì vẫn `BUSY` — quá hạn không được nổ sớm.
