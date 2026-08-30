---
id: ds-051
device: atmega328p
peripheral: spi
registers: [SPCR, SPSR, SPDR]
topic: Giao tiếp nối tiếp đồng bộ ở chế độ master
source: ATmega328P datasheet rev. DS40002061B, tr.170-178
source_hash: sha256:0000000000000000000000000000000000000000000000000000000000000008
status: approved
note: >-
  CHUNK NHIỄU CÓ CHỦ Ý cho bộ chuẩn truy xuất (TC-20). Dự án này không dùng SPI
  — hồ sơ phần cứng không khai ngoại vi ấy, và không module nào đụng tới nó.

  Đây là dạng nhiễu DỄ: bộ chọn theo quan hệ loại nó ngay vì đồ thị không có
  cạnh nào từ module tới các thanh ghi này. Giữ nó trong bộ chuẩn vẫn có ích —
  nó là chốt canh cho ngày ai đó đổi bộ chọn sang so khớp theo từ ngữ, lúc ấy
  "nối tiếp" trong topic sẽ bắt đầu kéo nó về phía module telemetry.
---

## SPI — chế độ master

| Thanh ghi | Bit | Ý nghĩa |
|---|---|---|
| SPCR | 6 (SPE) | 1 = bật ngoại vi SPI |
| SPCR | 4 (MSTR) | 1 = chế độ master |
| SPCR | 1:0 (SPR1:0) | Chọn hệ số chia tần xung nhịp |
| SPSR | 7 (SPIF) | Cờ hoàn tất truyền một byte |
| SPDR | 7:0 | Ghi để phát, đọc để nhận |

// ref: ds-051
