---
id: ds-atme-timer2-01
device: atmega328p
peripheral: timer2
registers:
- TCCR2A
- TCCR2B
- TCNT2
- OCR2A
- TIMSK2
topic: 'Timer2 chế độ CTC: TCCR2A/TCCR2B/OCR2A/TIMSK2, chọn bộ chia trước'
source: ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf, tr.155,165-166
source_hash: sha256:b9b9d83cda56a95d999ea8d54fe5a540748ae9020e5e7ae19b913d384ba9320e
status: approved
confidence: high
note: >-
  Chưng cất theo K2 và đối chiếu từng bit với bản gốc ngày 01/09/2026. Bảng
  chọn bộ chia trước của Timer2 KHÁC Timer0/Timer1 — nó có nấc /32 và /128,
  hai nấc kia không có. Chép nhầm bảng của bộ đếm khác là sai chu kỳ ngắt mà
  không lỗi dịch nào báo.
approved_by: Vũ Trí Công
approved_at: '2026-09-01T14:12:42+00:00'
---

## Trích đoạn timer2 — chế độ CTC

### Thanh ghi

| Thanh ghi | Địa chỉ | Bit 7…0 |
|---|---|---|
| `TCCR2A` | 0xB0 | COM2A1 COM2A0 COM2B1 COM2B0 – – WGM21 WGM20 |
| `TCCR2B` | 0xB1 | FOC2A FOC2B – – WGM22 CS22 CS21 CS20 |
| `TCNT2`  | 0xB2 | TCNT2[7:0] |
| `OCR2A`  | 0xB3 | OCR2A[7:0] |
| `TIMSK2` | 0x70 | – – – – – OCIE2B OCIE2A TOIE2 |

### Chế độ CTC

`WGM22:0 = 2`, tức **`WGM21 = 1`** trong `TCCR2A`, `WGM20 = 0`, `WGM22 = 0`.
Bộ đếm đếm từ 0 tới `OCR2A` rồi tự về 0 và sinh ngắt so khớp.

Cho phép ngắt so khớp A: **`TIMSK2 |= (1 << OCIE2A)`** (bit 1). Ngắt chỉ chạy
khi cờ ngắt toàn cục cũng bật.

### Chọn bộ chia trước — bảng của RIÊNG Timer2

| CS22 | CS21 | CS20 | Nguồn xung |
|---|---|---|---|
| 0 | 0 | 0 | dừng |
| 0 | 0 | 1 | không chia |
| 0 | 1 | 0 | **/8** |
| 0 | 1 | 1 | /32 |
| 1 | 0 | 0 | /64 |
| 1 | 0 | 1 | /128 |
| 1 | 1 | 0 | /256 |
| 1 | 1 | 1 | /1024 |

Bảng này KHÁC Timer0 và Timer1: hai bộ đếm kia không có nấc /32 và /128. Chép
nhầm bảng là sai chu kỳ ngắt, và không lỗi dịch nào báo.

### Tính chu kỳ ngắt

    T = (OCR2A + 1) × chia_trước / f_CPU

Với `f_CPU = 16 MHz`, chia trước 8 (`CS21 = 1`), `OCR2A = 39`:

    T = 40 × 8 / 16e6 = 20 µs   →   50 000 ngắt mỗi giây

Đây đúng là cấu hình mã tham chiếu của bộ kit dùng để phát xung bước.

### Trích đoạn nguyên văn để đối chiếu

> In Clear Timer on Compare or CTC mode (WGM22:0 = 2), the OCR2A Register is
> used to manipulate the counter resolution.
>
> • Bit 2:0 – CS22:0: Clock Select — The three Clock Select bits select the
> clock source to be used by the Timer/Counter.
>
> • Bit 1 – OCIE2A: Timer/Counter2 Output Compare Match A Interrupt Enable
>
> 0 1 0 clkT2S/8 (From prescaler)

— DS40002061B, mục 18.7.2 (tr.155) và 18.11 (tr.165-166)
