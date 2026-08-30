---
id: ds-023
device: atmega328p
peripheral: twi
registers: [TWAR, TWAMR, TWCR]
topic: Bus hai dây ở chế độ slave — địa chỉ và mặt nạ địa chỉ
source: ATmega328P datasheet rev. DS40002061B, tr.235-240
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000007
status: approved
note: >-
  CHUNK NHIỄU CÓ CHỦ Ý cho bộ chuẩn truy xuất (TC-20). Nó đúng về nội dung và
  đã duyệt G2, nhưng dự án này KHÔNG dùng chế độ slave — mọi module đều là
  master. Nó tồn tại để đo một điều mà chunk sai không đo được: bộ chọn có bị
  kéo bởi một chunk ĐÚNG, CÙNG NGOẠI VI, CHIA SẺ MỘT THANH GHI (TWCR) mà vẫn
  chẳng liên quan hay không.

  Chunk nhiễu ngây thơ — nói về một ngoại vi chẳng ai dùng — không đo được gì:
  bộ chọn theo quan hệ loại nó ngay vì không có cạnh nào dẫn tới. Chunk khó là
  chunk gần đúng.
---

## TWI — chế độ slave: địa chỉ và mặt nạ

| Thanh ghi | Bit | Ý nghĩa |
|---|---|---|
| TWAR | 7:1 | Địa chỉ slave của thiết bị này |
| TWAR | 0 (TWGCE) | 1 = trả lời cả lệnh gọi chung (địa chỉ 0x00) |
| TWAMR | 7:1 | Mặt nạ địa chỉ: bit = 1 thì bit địa chỉ tương ứng được bỏ qua khi so |
| TWCR | 6 (TWEA) | 1 = phát ACK khi được gọi đúng địa chỉ |

Ở chế độ slave, phần cứng tự so địa chỉ trên bus với TWAR và chỉ dựng cờ TWINT
khi trùng. Firmware không phải theo dõi từng byte trên bus.

// ref: ds-023
