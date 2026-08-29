---
id: ds-012
device: atmega328p
peripheral: timer1
registers: [TCCR1A, TCCR1B, OCR1A, TIMSK1]
topic: Timer1 chế độ CTC và ngắt so khớp
source: ATmega328P datasheet rev. DS40002061B, tr.140-145
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000001
status: approved
note: Duyệt tại G2 ngày 29/08/2026, đối chiếu từng bit với bản gốc.
---

## Timer1 — chế độ CTC (WGM = 4), ngắt so khớp kênh A

| Thanh ghi | Bit | Giá trị | Ý nghĩa |
|---|---|---|---|
| TCCR1A | WGM11:WGM10 | 0b00 | Cùng WGM13:12 = 0b01 chọn chế độ CTC, đỉnh đếm là OCR1A |
| TCCR1B | WGM13:WGM12 | 0b01 | Chế độ 4: CTC, TOP = OCR1A |
| TCCR1B | CS12:CS10 | 0b001 | Không chia tần (clk/1) |
| TCCR1B | CS12:CS10 | 0b010 | Chia 8 |
| TCCR1B | CS12:CS10 | 0b011 | Chia 64 |
| OCR1A | 15:0 | N | Bộ đếm reset khi TCNT1 == OCR1A |
| TIMSK1 | OCIE1A (bit 1) | 1 | Cho phép ngắt TIMER1_COMPA |

Chu kỳ ngắt: `T = (OCR1A + 1) × prescaler / f_clk`.
Với f_clk = 16 MHz, prescaler = 8, OCR1A = 19999 → T = 10 ms.

OCR1A là thanh ghi 16 bit có bộ đệm; ghi phải theo thứ tự byte cao trước,
byte thấp sau. Trình biên dịch sinh đúng thứ tự khi gán nguyên cả `OCR1A`.
