# SL-120 — điều tra: "đọc ngược khớp ảnh" có đang khẳng định sai không?

Sổ ghi TỪNG BƯỚC, kể cả bước đi sai. Mục đích không chỉ là ra đáp án mà còn để
sau này đọc lại xem cách làm có chỗ nào phí, chỗ nào đi vòng.

**Câu hỏi:** `eaa flash` báo *"Kiểm sau khi nạp: ĐÃ KIỂM — đọc ngược khớp ảnh"*.
Phép so bằng tay cuối phiên trước nói **895/974 byte khác nhau**. Một trong hai
sai.

**Nguyên tắc dẫn đường:** nghi mã mình vừa viết vội TRƯỚC, nghi sản phẩm SAU.

---

## Bước 0 — trạng thái xuất phát (2026-09-01)

* Bo cắm lại, `eaa ports` nhận đúng `1a86:7523` trên `/dev/cu.usbserial-143410`
* Kho sạch, `main` ở `83f9d27`
* Ảnh đang xét: `projects/robot_balance/firmware/build/diag_DS-04.hex`
  (bản 9600 baud, băm `sha256:1de31df1baac…`, là ảnh đã nạp lần cuối)

## Bước 1 — loại nghi vấn "bộ đọc HEX của tôi sai"

Bỏ hẳn mã tự viết khỏi phép so. Dùng `avr-objcopy` chuyển ảnh HEX sang nhị
phân, và đọc chip ra **nhị phân thô** (`-U flash:r:…:r`) để không phải phân
tích HEX lần nào.

```bash
avr-objcopy -I ihex -O binary diag_DS-04.hex anh_da_nap.bin      # 974 byte
avrdude -c arduino -p m328p -P /dev/cu.usbserial-143410 -b 57600 \
        -U flash:r:doc_chip.bin:r                                 # 32768 byte
head -c 974 doc_chip.bin > dau_chip.bin
cmp -l anh_da_nap.bin dau_chip.bin | wc -l
```

**Kết quả: 895 byte lệch** — trùng đúng con số bộ đọc tự viết đưa ra.

Bảng vector ngắt 32 byte đầu:

```
ảnh nạp: 0c94 3400  0c94 4900  0c94 4900  0c94 4900 …
chip   : 0c94 8100  0c94 a900  0c94 a900  0c94 b708 …
```

Cả hai đều là bảng vector hợp lệ (`0c 94` = `jmp`), nhưng chip trỏ tới
`0x08b7`, `0x0a4e` — **ngoài vùng 974 byte của ảnh ta nạp**. Chip đang chứa
một chương trình khác, lớn hơn.

→ **Nghi vấn 1 bị loại.** Mã tôi viết đúng. Chip thật sự không chứa ảnh ta nạp.

## Bước 2 — đọc năng lực `flash_verify` của pack, rồi chạy tay đúng lệnh ấy

```yaml
flash_verify:
  command: [avrdude, -c, "{programmer}", -p, "{mcu}", -P, "{port}",
            -b, "{baud}", -U, "flash:v:{binary}:e"]
  parse:
    success_exit_codes: [0]
    error_regex: "^avrdude:\\s+(?:error|ERROR|verification error)[:\\s]+(?P<msg>.+)$"
```

Chạy tay:

```
Error: cannot use build/diag_DS-04.hex as an ELF input file
Verifying 0 bytes of flash against input file diag_DS-04.hex
mã thoát: 0
```

**NGUYÊN NHÂN.** Hậu tố `:e` khai định dạng tệp là **ELF**; tệp là **Intel
HEX**. avrdude không đọc được, kiểm **0 byte**, rồi **thoát 0**.

## Bước 3 — lệnh GHI cũng cùng bệnh

```yaml
flash:
  command: [… -U, "flash:w:{binary}:e"]
```

```
Error: cannot use build/diag_DS-04.hex as an ELF input file
Reading 0 bytes for flash from input file diag_DS-04.hex
mã thoát: 0
```

→ **Chưa có gì từng được ghi xuống chip**, cả hai phiên.

## Kết luận

Chuỗi hỏng trọn vẹn:

| Bước | avrdude thật sự làm | `eaa` báo |
|---|---|---|
| ghi | đọc 0 byte từ tệp, ghi 0 byte, thoát 0 | *"Đã nạp sha256:1de31df1baac… lên /dev/cu.usbserial-143410"* |
| đọc ngược | kiểm 0 byte, thoát 0 | *"ĐÃ KIỂM — đọc ngược khớp ảnh"* |

Ba khiếm khuyết chồng lên nhau:

1. **Sai chữ định dạng** — `:e` (ELF) cho tệp Intel HEX. Đáng lẽ `:i`.
2. **avrdude thoát 0 dù có dòng `Error:`** — và pack tin `success_exit_codes: [0]`.
3. **`error_regex` không khớp định dạng lỗi của avrdude 8.2.** Nó chờ
   `^avrdude:\s+error`, còn bản 8.2 in `Error: cannot use …`. Nên dòng lỗi
   **vô hình** với lớp phân tích.

Và bao trùm cả ba: **kiểm 0 byte vẫn được tính là đạt.** Một phép kiểm không
kiểm gì phải là KHÔNG ĐẠT, không phải đạt.

Bo vẫn đang chạy firmware gốc của bộ kit — khớp với những byte `7E 02 0C EF`
đọc được trên dây (khung lệnh module MP3 trong mã tham chiếu BLKLab), và giải
thích vì sao đổi baud firmware mà dữ liệu trên dây không đổi.

