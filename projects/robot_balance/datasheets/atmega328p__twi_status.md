---
id: ds-022
device: atmega328p
peripheral: twi
registers: [TWSR, TWDR, TWCR]
topic: Mã trạng thái bus hai dây ở chế độ master
source: ATmega328P datasheet rev. DS40002061B, tr.228-232
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000003
status: approved
---

## TWI — mã trạng thái master (đọc TWSR sau khi che 3 bit thấp)

| TWSR & 0xF8 | Ý nghĩa |
|---|---|
| 0x08 | Đã phát START |
| 0x10 | Đã phát START lặp lại |
| 0x18 | Đã gửi SLA+W, nhận ACK |
| 0x20 | Đã gửi SLA+W, nhận NACK |
| 0x28 | Đã gửi byte dữ liệu, nhận ACK |
| 0x40 | Đã gửi SLA+R, nhận ACK |
| 0x50 | Đã nhận byte dữ liệu, đã trả ACK |
| 0x58 | Đã nhận byte dữ liệu, đã trả NACK |
| 0x38 | Mất quyền trọng tài |

Ba bit thấp của TWSR là bit chia trước, phải che bằng `TWSR & 0xF8` trước khi
so sánh. Bỏ bước che là lỗi kinh điển khiến máy trạng thái bus treo.

TWDR giữ byte đang gửi hoặc vừa nhận; chỉ hợp lệ khi TWINT đã được set.
