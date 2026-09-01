---
id: ds-atme-gpio-01
device: atmega328p
peripheral: gpio
registers:
- DDRB
- PORTB
- PINB
- MCUCR
topic: 'Cấu hình chân cổng I/O cổng B: DDRB/PORTB/PINB, điện trở kéo lên nội'
source: ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf, tr.85-100
source_hash: sha256:b9b9d83cda56a95d999ea8d54fe5a540748ae9020e5e7ae19b913d384ba9320e
status: approved
confidence: high
note: >-
  Đã chưng cất theo K2 và đối chiếu từng bit với bản gốc ngày 01/09/2026.
  Danh sách `registers` chuẩn hóa từ dạng chung DDRx/PORTx/PINx mà máy trích
  ra: đồ thị tri thức so khớp THEO TÊN, nên để nguyên dạng chung thì chunk
  không bao giờ được truy xuất cho module cần nó.
  Cố ý chỉ giữ CỔNG B — còi ở PB2 và nút ở PB4. Cổng C và D thuộc trích đoạn
  khác, thêm khi có module cần.
approved_by: Vũ Trí Công
approved_at: '2026-09-01T11:24:37+00:00'
---

## Trích đoạn gpio — cổng B của ATmega328P

### Địa chỉ và bit

| Thanh ghi | Địa chỉ I/O (bộ nhớ) | Bit 7…0 | Truy cập | Giá trị đầu |
|---|---|---|---|---|
| `PORTB` | 0x05 (0x25) | PORTB7…PORTB0 | R/W | 0 |
| `DDRB`  | 0x04 (0x24) | DDB7…DDB0 | R/W | 0 |
| `PINB`  | 0x03 (0x23) | PINB7…PINB0 | R/W | không xác định |
| `MCUCR` | 0x35 (0x55) | bit 4 = PUD | R/W | 0 |

### Ba bit cho mỗi chân, và bảng sự thật của chúng

Mỗi chân `Pxn` có đúng ba bit: `DDxn` trong `DDRx`, `PORTxn` trong `PORTx`,
`PINxn` trong `PINx`.

| `DDBn` | `PORTBn` | Chân làm gì |
|---|---|---|
| 0 | 0 | Vào, thả nổi (tri-state) |
| 0 | 1 | **Vào, BẬT điện trở kéo lên nội** |
| 1 | 0 | Ra, kéo xuống mức thấp |
| 1 | 1 | Ra, kéo lên mức cao |

* Đọc mức thật của chân bằng `PINB`, **không** bằng `PORTB` — `PORTB` là giá
  trị đã ghi ra, không phải điện áp đang có trên chân.
* Ghi logic 1 vào `PINBn` sẽ **đảo** `PORTBn`, bất kể `DDBn`. Dùng được để
  nháy một chân mà không đọc–sửa–ghi.
* `MCUCR.PUD = 1` tắt điện trở kéo lên của TOÀN BỘ cổng I/O, kể cả khi
  `{DDxn, PORTxn} = 0b01`. Mặc định sau reset là 0 (kéo lên dùng được).
* Sau reset mọi chân ở trạng thái tri-state, kể cả khi chưa có xung nhịp.

### Áp vào dự án này

* Còi ở **PB2**, mức cao là kêu → `DDRB |= (1<<DDB2)`; bật kêu bằng
  `PORTB |= (1<<PORTB2)`, tắt bằng `PORTB &= ~(1<<PORTB2)`.
* Nút ở **PB4**, nối về GND, cần kéo lên nội → `DDRB &= ~(1<<DDB4)` rồi
  `PORTB |= (1<<PORTB4)`. Đọc bằng `PINB & (1<<PINB4)`; **mức THẤP là đang
  nhấn**.

### Trích đoạn nguyên văn để đối chiếu

> Each port pin consists of three register bits: DDxn, PORTxn, and PINxn. […]
> The DDxn bit in the DDRx Register selects the direction of this pin. If DDxn
> is written logic one, Pxn is configured as an output pin. If DDxn is written
> logic zero, Pxn is configured as an input pin.
>
> If PORTxn is written logic one when the pin is configured as an input pin,
> the pull-up resistor is activated. To switch the pull-up resistor off, PORTxn
> has to be written logic zero or the pin has to be configured as an output
> pin. The port pins are tri-stated when reset condition becomes active, even
> if no clocks are running.
>
> Writing a logic one to PINxn toggles the value of PORTxn, independent on the
> value of DDRxn.
>
> • Bit 4 – PUD: Pull-up Disable — When this bit is written to one, the
> pull-ups in the I/O ports are disabled even if the DDxn and PORTxn Registers
> are configured to enable the pull-ups ({DDxn, PORTxn} = 0b01).

— DS40002061B, mục 14.2.1, 14.2.2 (tr.85) và 14.4 (tr.100)
