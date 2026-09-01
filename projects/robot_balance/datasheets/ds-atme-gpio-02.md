---
id: ds-atme-gpio-02
device: atmega328p
peripheral: gpio
registers:
- DDRD
- PORTD
- PIND
topic: 'Thanh ghi cổng D: DDRD/PORTD/PIND — bốn chân xung bước nằm ở đây'
source: ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf, tr.101
source_hash: sha256:b9b9d83cda56a95d999ea8d54fe5a540748ae9020e5e7ae19b913d384ba9320e
status: approved
confidence: high
note: >-
  Chưng cất theo K2 và đối chiếu từng bit với bản gốc ngày 01/09/2026, cùng
  lúc `drv_stepper` cần tới. Quy tắc ba bit và điện trở kéo lên giống hệt cổng
  B (xem ds-atme-gpio-01) — chỉ khác địa chỉ; không chép lại phần ấy.
approved_by: Vũ Trí Công
approved_at: '2026-09-01T14:04:04+00:00'
---

## Trích đoạn gpio — cổng D của ATmega328P

### Địa chỉ và bit

| Thanh ghi | Địa chỉ I/O (bộ nhớ) | Bit 7…0 | Truy cập | Giá trị đầu |
|---|---|---|---|---|
| `PORTD` | 0x0B (0x2B) | PORTD7…PORTD0 | R/W | 0 |
| `DDRD`  | 0x0A (0x2A) | DDD7…DDD0 | R/W | 0 |
| `PIND`  | 0x09 (0x29) | PIND7…PIND0 | R/W | không xác định |

Quy tắc ba bit `DDxn`/`PORTxn`/`PINxn`, bảng sự thật vào–ra, điện trở kéo lên
nội và `MCUCR.PUD` giống hệt cổng B — xem `ds-atme-gpio-01`.

### Áp vào dự án này

Bốn chân xung bước nằm trên cổng này, và **không có chân enable** (A4988 bật
cứng trên bo):

| Nét | Chân | Bit |
|---|---|---|
| `STEP_R` | PD5 | `DDD5` / `PORTD5` |
| `DIR_R`  | PD4 | `DDD4` / `PORTD4` |
| `STEP_L` | PD7 | `DDD7` / `PORTD7` |
| `DIR_L`  | PD6 | `DDD6` / `PORTD6` |

Cả bốn là chân RA: `DDRD |= (1<<DDD7)|(1<<DDD6)|(1<<DDD5)|(1<<DDD4);`

PD0 và PD1 là RXD/TXD của cổng nối tiếp — **đừng đụng tới hai bit ấy** khi
cấu hình cổng D, nếu không kênh telemetry chết. Dùng phép hoặc/và theo mặt nạ,
đừng gán thẳng cả byte.

### Trích đoạn nguyên văn để đối chiếu

```
0x0B (0x2B) PORTD7 PORTD6 PORTD5 PORTD4 PORTD3 PORTD2 PORTD1 PORTD0  PORTD
0x0A (0x2A) DDD7   DDD6   DDD5   DDD4   DDD3   DDD2   DDD1   DDD0    DDRD
0x09 (0x29) PIND7  PIND6  PIND5  PIND4  PIND3  PIND2  PIND1  PIND0   PIND
```

— DS40002061B, mục 14.4.8–14.4.10 (tr.101)
