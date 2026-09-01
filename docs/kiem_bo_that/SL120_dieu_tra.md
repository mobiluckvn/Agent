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

---

## Bản sửa — ba tầng, vì chỉ đổi chữ định dạng thì lần sau vẫn hỏng im lặng

| Tầng | Sửa gì |
|---|---|
| Dữ liệu pack | `:e` → `:i`; `error_regex` bắt cả `Error:` lẫn `avrdude: error:` |
| Dữ liệu pack | thêm `require_regex` đòi `N bytes of flash written/verified`, N > 0 |
| Engine | `ParseSpec.require_regex` + cưỡng chế trong `ToolRunner.doc_ket_qua()` |

Tầng thứ ba mới là tầng đáng kể: nó là cái duy nhất còn đúng khi công cụ đổi
phiên bản hay đổi câu chữ. **Mã thoát 0 chỉ nói công cụ không thấy lý do phàn
nàn; nó không nói công cụ đã làm gì.**

Tách `doc_ket_qua()` thành hàm lớp để kiểm được bằng **đầu ra THẬT đã ghi lại**
— chính đoạn văn bản từng lừa được hai phiên làm việc giờ nằm trong bộ kiểm.

Pack chưa khai `require_regex` thì hành vi giữ nguyên: thêm một luật mới không
được đổi ngầm kết cục của những pack chưa biết tới nó.

## Nạp lại, và KIỂM ĐỘC LẬP

`eaa flash` in ra **đúng câu như hôm qua** — nên không tin, đọc chip ra nhị
phân thô rồi so bằng `cmp`:

```
✅ KHỚP — 974 byte trên chip trùng ảnh đã nạp
vector ngắt: 0c94 3400   (hôm qua: 0c94 8100 — mã của bộ kit)
```

Firmware của ta nằm trên chip **lần đầu tiên**.

## Số đo Bài 1 — kênh UART, trên bo thật

```
Khung nhận  : 104 (104 đạt, 0 hỏng)
loopback_ok : True          (kỳ vọng True)
frame_rate  : 162 Hz        (sàn 50)
Vùng lỗi    : không phát hiện lỗi
```

## Nhìn lại cách làm

Việc gì đã tiết kiệm thời gian:

* **Nghi mã mình trước, nghi sản phẩm sau.** Bước 1 tốn 3 phút và loại sạch
  một nhánh; nếu bỏ qua nó thì mọi kết luận sau đều lung lay.
* **Bỏ hẳn mã tự viết ra khỏi phép so** (`avr-objcopy` + đọc nhị phân thô)
  thay vì đi soi bộ đọc HEX từng dòng.
* **Chạy tay đúng lệnh mà pack khai.** Nguyên nhân hiện ra ngay dòng đầu.
  Không cần đọc mã engine dòng nào.

Việc gì đã tốn thời gian vô ích hôm qua:

* Đoán tốc độ truyền bằng cách quét baud và chấm điểm "tỉ lệ ký tự đọc được".
  Dữ liệu trên dây khi ấy **không phải của ta**, nên mọi con số đều vô nghĩa.
  Đáng lẽ phải kiểm "firmware có thật sự nằm trên chip không" TRƯỚC khi đo bất
  cứ thứ gì — rẻ hơn hẳn và trả lời được câu quan trọng hơn.
* Đọc cầu chì qua bootloader: trả `0x00` cả ba byte vì bootloader không hỗ trợ
  lệnh ấy, và **không báo lỗi**. Một phép đo trông như dữ liệu.

Bài học chung của cả hai: **kiểm cái nền trước khi đo cái xây trên nó.** Hôm
qua tôi đo tín hiệu của một chương trình chưa từng được nạp.

---

# Bài 2 — cảm biến. Phần đo được, và một tranh luận đã giải bằng số

## Số đo trên bo

| Kịch bản | Đo được |
|---|---|
| DS-01 quét bus I2C | `i2c_addresses=['0x68']` — cảm biến có mặt, đúng địa chỉ hồ sơ khai |
| DS-02 | `who_am_i = 0x72` (hồ sơ khai `0x68`) |
| | `accel_noise_mg` 0.36 rồi 0.24 ở lần sau |
| | `gyro_noise_dps` 0.03 rồi 0.05 |
| | `samples = 100` |

## Một tranh luận, và cách giải nó

Tôi nghi `accel_noise_mg = 0` là dấu hiệu cảm biến không đọc được. Người dùng
phản biện: *"Nó đang được đặt nằm yên trên mặt phẳng thì đó là bình thường mà."*

Cả hai đều có phần đúng, và **phép đo giải quyết được, tranh luận thì không**:

* Người dùng đúng về **điều kiện đo** — nằm yên chính là điều kiện đo nhiễu nền.
* Tôi đúng về **độ phân giải** — `nhieu_a * 1000 / 16384` cho ra mg nguyên,
  trong khi nhiễu lành mạnh là 4–8 LSB tức 0,2–0,5 mg, nên nó làm tròn thành 0.
  Đường con quay ngay dưới, cùng đoạn mã, nhân 100 để giữ hai chữ số thập phân.

Nâng độ phân giải rồi đo lại: **0,36 mg**. Đúng dải dự đoán. Cảm biến lành, và
phép đo thì đang làm tròn mất toàn bộ tín hiệu nó sinh ra để đo.

Bài học về cách làm: khi hai bên có hai giả thuyết trái nhau và cả hai đều
nghe hợp lý, **đi đo rẻ hơn đi thuyết phục** — ở đây là ba phút.

## Cách C giải bằng thực nghiệm, không cần tài liệu mới

Đã thử lấy register map MPU-6500/9250 từ `invensense.tdk.com`: cả hai URL
chuyển hướng sang trang HTML động, không có PDF tĩnh. `eaa research
--official-only` trả về 5 địa chỉ, **không trang chính chủ nào đọc được**, và
lệnh nói thẳng mọi thứ còn lại là hạng *mở* — manh mối, không phải nguồn cho
giá trị cấu hình. Lớp phân hạng nguồn làm đúng việc của nó.

Người dùng chỉ ra đường ngắn hơn: **dùng tài liệu chính chủ đã có** (MPU6050,
qua G2) làm phép thử. Con chip đã trả lời 100 mẫu bằng đúng bản đồ thanh ghi
ấy — nên câu hỏi tương thích trả lời được bằng chính dữ liệu đã có:

| Thanh ghi MPU6050 dự án dùng | Trên con chip này |
|---|---|
| địa chỉ bus `0x68` | ✓ |
| `WHO_AM_I` `0x75` | ✓ đọc được, trả `0x72` |
| `PWR_MGMT_1` `0x6B` | ✓ ghi vào đánh thức được |
| `ACCEL_XOUT_H` `0x3B`, chùm 14 byte | ✓ ra gia tốc + con quay hợp lý |
| 16384 LSB/g và 131 LSB/(°/s) | ✓ quy ra 0,36 mg và 0,03 °/s — đúng dải vật lý |

Dòng cuối là bằng chứng mạnh nhất: dải đo mặc định khác thì hai con số ấy đã
lệch hẳn một hệ số.

## Lỗi thứ hai phơi ra từ số 0

Phép kiểm nhiễu chỉ có **trần**, nên **cảm biến chết cũng đạt**: chip còn ngủ
trả về toàn số 0, và 0 nằm dưới mọi trần. Đã thêm **sàn** cho cả hai, lấy từ
số đo thật chia đôi để chừa biên. MEMS đang sống không bao giờ cho nhiễu 0.
