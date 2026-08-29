---
id: ds-041
device: atmega328p
peripheral: usart0
registers: [UBRR0H, UBRR0L, UCSR0A, UCSR0B, UCSR0C]
topic: Cấu hình tốc độ và khung truyền nối tiếp
source: ATmega328P datasheet rev. DS40002061B, tr.180-190
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000006
status: approved
---

## USART0 — tốc độ baud và khung truyền

| Thanh ghi | Bit | Giá trị | Ý nghĩa |
|---|---|---|---|
| UBRR0H:UBRR0L | 11:0 | N | Hệ số chia tốc độ baud |
| UCSR0A | U2X0 (bit 1) | 1 | Nhân đôi tốc độ, giảm sai số baud |
| UCSR0B | TXEN0 (bit 3) | 1 | Bật bộ phát |
| UCSR0B | RXEN0 (bit 4) | 1 | Bật bộ thu |
| UCSR0C | UCSZ01:UCSZ00 | 0b11 | Khung 8 bit dữ liệu |
| UCSR0C | USBS0 (bit 3) | 0 | Một bit dừng |

Công thức chế độ thường: `UBRR = f_CPU / (16 × baud) - 1`.
Chế độ U2X0 = 1: `UBRR = f_CPU / (8 × baud) - 1`.

Với f_CPU = 16 MHz và baud 115200: chế độ thường cho UBRR = 8 với sai số
-3,5% (rủi ro lỗi khung); bật U2X0 cho UBRR = 16 với sai số 2,1%.
