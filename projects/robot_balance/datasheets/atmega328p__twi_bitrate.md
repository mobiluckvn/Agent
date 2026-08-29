---
id: ds-021
device: atmega328p
peripheral: twi
registers: [TWBR, TWSR, TWCR]
topic: Cấu hình tốc độ bit bus hai dây
source: ATmega328P datasheet rev. DS40002061B, tr.222-224
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000002
status: approved
note: Duyệt tại G2 ngày 29/08/2026.
---

## TWI — tốc độ bit và bật ngoại vi

| Thanh ghi | Bit | Giá trị | Ý nghĩa |
|---|---|---|---|
| TWBR | 7:0 | N | Hệ số chia tốc độ bit |
| TWSR | TWPS1:TWPS0 (bit 1:0) | 0b00 | Hệ số chia trước = 1 |
| TWCR | TWEN (bit 2) | 1 | Bật giao diện TWI, chiếm quyền chân SDA/SCL |
| TWCR | TWSTA (bit 5) | 1 | Phát điều kiện START |
| TWCR | TWSTO (bit 4) | 1 | Phát điều kiện STOP |
| TWCR | TWINT (bit 7) | 1 | Ghi 1 để xóa cờ và bắt đầu thao tác kế tiếp |

Công thức: `f_SCL = f_CPU / (16 + 2 × TWBR × 4^TWPS)`.
Với f_CPU = 16 MHz, TWPS = 0, f_SCL = 400 kHz → TWBR = 12.

TWBR phải ≥ 10 khi thiết bị hoạt động ở chế độ master, nếu không xung SCL
sinh ra không đạt yêu cầu thời gian của chuẩn.
