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
status: proposed
confidence: medium
note: >-
  CHƯA DUYỆT, và cố ý để vậy. Danh sách `registers` đã chuẩn hóa từ đám tên
  bit máy trích ra (PORTD7, PORTD6...) về đúng ba thanh ghi — đồ thị so khớp
  theo tên, để nguyên dạng bit thì chunk không bao giờ được truy xuất. Nhưng
  THÂN chunk vẫn là bản máy trích, chưa ai đối chiếu từng bit với bản gốc.

  Đây là trạng thái trung gian thật: đã chưng cất phần siêu dữ liệu, chưa
  chưng cất phần nội dung. Duyệt nó khi `drv_stepper` cần — bốn chân xung
  bước PD4–PD7 nằm ở cổng này.
---

## Trích đoạn gpio

### Trích đoạn nguyên văn (CHƯA chưng cất — kỹ sư đối chiếu và rút gọn)

ATmega48A/PA/88A/PA/168A/PA/328/P
 2020 Microchip Technology Inc.        Da ta Sheet Complete      DS40002061B-page 101 
14.4.7 PINC – The Port C Input Pins Address (1)
14.4.8 PORTD – The Port D Data Register
14.4.9 DDRD – The Port D Data Direction Register
14.4.10 PIND – The Port D Input Pins Address(1)
Note: 1. Writing to the pin register prov ides toggle functionality for IO (see ”Toggling the Pin” on page 85)
B i t 76543210
0x06 (0x26) – PINC6 PINC5 PINC4 PINC3 PINC2 PINC1 PINC0 PINC
Read/Write R R/W R/W R/W R/W R/W R/W R/W
Initial Value 0 N/A N /A N/A N/A N/A N/A N/A
B i t 76543210
0x0B (0x2B) PORTD7 PORTD6 PORTD5 PORTD4 PORT D3 PORTD2 PORTD1 PORTD0 PORTD
Read/Write R/W R/W R/W R/W R/W R/W R/W R/W
I n i t i a l  V a l u e 00000000
B i t 76543210
0x0A (0x2A) DDD7 DDD6 DDD5 DDD4 DDD3 DDD2 DDD1 DDD0 DDRD
Read/Write R/W R/W R/W R/W R/W R/W R/W R/W
Initial Value 0 0 0 0 0 0 0 0
B i t 76543210
0x09 (0x29) PIND7 PIND6 PIND5 PIND4 PI ND3 PIND2 PIND1 PIND0 PIND
Read/Write R/W R/W R/W R/W R/W R/W R/W R/W
Initial Value N/A N/A N /A N/A N/A N/A N/A N/A
