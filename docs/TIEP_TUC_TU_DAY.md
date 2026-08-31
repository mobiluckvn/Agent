# Tiếp tục từ đây — phiên kiểm Agent với bo thật

Dừng lúc: **2026-08-31 tối**. Nhánh `main`, mọi thứ đã đẩy.
Bo AVR đang **cắm và nhận được**. Toolchain **đủ**. Đã nạp firmware xuống bo.

---

## 1. VIỆC ĐẦU TIÊN SÁNG MAI — một mâu thuẫn chưa giải

`eaa flash` báo:

```
Kiểm sau khi nạp: ĐÃ KIỂM — đọc ngược khớp ảnh.
```

Nhưng đọc ngược **bằng tay** thì không khớp:

```bash
cd /private/tmp/.../scratchpad   # hoặc bất kỳ thư mục tạm nào
avrdude -c arduino -p m328p -P /dev/cu.usbserial-143410 -b 57600 -U flash:r:doc_ve.hex:i
```

So với ảnh đã nạp:

| | |
|---|---|
| Ảnh đã nạp | 974 byte, `0x0000–0x03cd` |
| Khác nhau trong vùng ấy | **895 / 974 byte** |
| Ngoài vùng ảnh | còn **16.345 byte khác `0xFF`**, tới `0x7f9d` — mã cũ vẫn nằm đó |

Hai phép đọc ngược nói ngược nhau. **Đúng một trong hai là sai, và cần biết cái nào.**

Vì sao đây là việc quan trọng nhất: nếu bản báo "ĐÃ KIỂM" sai thì sản phẩm
đang khẳng định *"thứ trên bàn là thứ đã được duyệt"* trong khi không phải —
hỏng đúng bất biến trung tâm, ở chặng cuối.

**Cách kiểm chưa làm:**

1. Xem `eaa` chạy lệnh đọc ngược nào (`packs/avr/pack.yaml`, năng lực `verify`)
   và nó so cái gì với cái gì.
2. Kiểm bộ đọc Intel HEX tôi viết trong phép so tay — nó có thể sai chứ không
   phải `eaa` sai. Ưu tiên nghi ngờ chỗ này trước.
3. Nạp một ảnh khác hẳn (ví dụ DS-01) rồi đọc ngược: nếu nội dung chip KHÔNG
   đổi theo, thì lệnh nạp không có tác dụng thật.

**Manh mối mạnh:** những byte đọc được trên dây (`7E 02 0C EF`, `7E 03 06 0A EF`)
trùng đúng khung lệnh module MP3 JQ6500 trong mã tham chiếu BLKLab V3
(`Serial.write(0x7E); … Serial.write(0xEF);` ở cuối tệp `.ino`). Tức **bo đang
chạy firmware gốc của bộ kit**, không phải firmware ta nạp.

---

## 2. Trạng thái phần cứng — đã đo, đã chốt

| Tham số | Hồ sơ khai ban đầu | Đo được | Ghi ở đâu |
|---|---|---|---|
| Cổng | — | `/dev/cu.usbserial-143410` | `eaa ports` tự nhận |
| Chip | atmega328p | `1E 95 0F` ✓ đúng | đọc bằng avrdude |
| Tốc độ bootloader | 115200 ✗ | **57600** | đã sửa `hardware_profile.yaml`, duyệt lại G1 |
| Tốc độ telemetry | 115200 | đang thử 9600 | `diagnostics.yaml` |

Bo trả về hai chùm **đúng 19 byte** cách nhau đều (~3,3 s), và nội dung
**không đổi** khi ta đổi baud của firmware từ 115200 xuống 9600 — đó chính là
manh mối dẫn tới mục 1.

Đọc cầu chì qua bootloader Arduino trả `0x00` cho cả ba byte: nó **không hỗ
trợ lệnh ấy** và không báo lỗi. Đừng dùng số đó.

---

## 3. Bài 1 (UART) — tới đâu

Mã `drv_uart` đã sinh, **đúng**, nằm trên nhánh `feature/drv_uart` của kho
`projects/robot_balance/firmware` (kho Git riêng):

* chờ `UDRE0` **có hạn giờ** — tôn trọng lệnh cấm `blocking_io`
* đọc cờ lỗi **trước** khi đọc `UDR0`, đúng luật datasheet
* mọi truy cập thanh ghi có `// ref: ds-041` / `ds-043`
* `compile` / `size` / `static` **ĐẠT** với toolchain thật

**Chưa merge được** vì cổng `unittests` chưa đạt: dự án chưa có bộ kiểm thử
đơn vị nào. Cổng nói đúng — *"chưa có gì để chạy" không phải "đã kiểm chứng"*.
Muốn qua G3 thì phải viết test chạy trên máy chủ qua lớp phần cứng giả
(`eaa/tools/unittests.py` giải thích cách).

Tri thức đã đủ: `ds-043` (datasheet chính chủ Microchip, tr.200-203, đã qua
G2) phủ `UDR0`, `UDRE0`, `RXC0`, `TXC0`.

---

## 4. Bài 2 (cảm biến) — chưa bắt đầu

Đường đã rõ, dùng đúng thứ có sẵn: kịch bản **DS-02 "Kiểm cảm biến MPU6050"**
(`eaa diagnose build DS-02`). Nhưng nó chặn sau mục 1: chưa tin được là
firmware ta nạp có thật sự chạy hay không thì mọi số đo cảm biến đều vô nghĩa.

Chunk `ds-032` (dải đo và hệ số nhạy MPU6050) **cố ý còn ở `proposed`** —
đừng duyệt nó cho tới khi đối chiếu xong hệ số nhạy. Tôi đã lỡ duyệt nó một
lần và trả về ngay (xem SL-117, mục còn treo).

---

## 5. Review mã tham chiếu — đã làm một phần

`eaa chat` đọc `sources/…/V3_Balancing_Robot_PID_App.ino` và bắt đúng ba vi
phạm ràng buộc cứng:

| Thư viện | Vi phạm |
|---|---|
| `Adafruit_NeoPixel` | tắt ngắt toàn cục >120 µs khi đẩy dữ liệu LED — vượt trần `motor_response_us` 50 µs, mất xung bước |
| `SoftwareSerial` | chặn CPU, can thiệp ngắt — vi phạm `CẤM blocking_io`, phá chu kỳ 10 ms |
| `SimpleKalmanFilter` | số thực nặng — vi phạm `arithmetic: integer` |

Sơ đồ chân rút được: MPU6050 `0x68`, nút D12, còi D10, HC-05 TX=D8 RX=D9.

**Giới hạn đã lộ:** Agent chỉ đọc được PHẦN ĐẦU tệp — lớp quan sát cắt đầu ra
cho vừa ngân sách, và `survey --read` **không có cách đọc tiếp phần sau**
(không có offset/khoảng dòng). Nó tự khai điều đó rồi thử `cat` và bị từ chối
đúng. Đây là việc nên sửa: thêm `--lines` hay `--from` cho `survey --read`.

---

## 6. Đã tìm và sửa được gì trong phiên này

**Mười lăm lỗi thật**, ghi đầy đủ ở `docs/SAI_LECH_THIET_KE.md` mục
**SL-109 … SL-119**. Test đi từ 2.077 → **2.145**.

Bốn nhóm đáng nhớ nhất:

1. **Ngõ cụt, không phải cổng** (SL-110, SL-113, SL-117, SL-119). Cùng một
   hình dạng lặp lại bốn lần ở bốn chỗ khác nhau: lệnh dừng lại và **không
   nêu lối đi tiếp**, nên một phiên làm việc qua người trung gian không bao
   giờ đi qua được — dù người có đồng ý bao nhiêu lần. Đã dựng cửa cho cả
   bốn: `doctor approve`, ghim băm ở G1, `DatasheetStore.approve`,
   `flash approve`.

2. **Mã đúng nằm chết** — bốn lần. Câu trả lời đúng đã được viết ra, nằm
   trong tệp, đi vào prompt, và **không có đường tới nơi cần nó**:
   `InstallNotConfirmed`, lời giải thích trong `NGOAI_DANH_MUC`, chỗ giữ
   `{baud}` trong khuôn firmware, `verify_checksum()` không ai gọi.

3. **Bất biến đúng theo nghĩa tệ nhất** (SL-117). *"Tri thức chỉ vào kho qua
   G2"* đúng — vì `DatasheetStore` là kho chỉ đọc và **không gì vào được cả**.
   Mọi chunk `approved` trong dự án đều được viết tay sẵn.

4. **Lời hứa an toàn không có gì đứng sau** (SL-113). `verify_checksum` có
   hàm, có test, không có người gọi; và `fix()` in ra một dòng khẳng định việc
   ấy đã xảy ra.

Và bốn lần **bài canh cũ bắt lỗi tôi vừa tự gây ra**: TC-38 (tên chip thật
trong docstring engine), `tool_for` nuốt `doctor approve`, rồi nuốt
`flash approve`, và một bài kiểm của tôi gán `subprocess.run` toàn cục làm
hỏng mọi bài chạy sau.

---

## 7. Lệnh hay dùng

```bash
cd /Users/v/Documents/KTDT
P="--project projects/robot_balance"

.venv/bin/python -m eaa.cli $P status
.venv/bin/python -m eaa.cli $P ports
.venv/bin/python -m eaa.cli $P doctor
.venv/bin/python -m eaa.cli $P diagnose list
.venv/bin/python -m eaa.cli $P diagnose build DS-04
.venv/bin/python -m eaa.cli $P flash approve --image <hex> --actor "Vũ Trí Công"
.venv/bin/python -m eaa.cli $P flash --image <hex> --actor "Vũ Trí Công"
.venv/bin/python -m eaa.cli $P diagnose run DS-04 --port /dev/cu.usbserial-143410

.venv/bin/python -m pytest -q -m "not cham"      # ~3 phút
```

Nhật ký từng bước của phiên: `docs/kiem_bo_that/`.

**Lưu ý về cách làm việc:** người dùng đã ủy quyền tôi gõ hộ các lệnh duyệt
(`doctor approve`, `gate approve`, `flash approve`) dưới tên họ. Sổ ghi
"Vũ Trí Công" còn phím thì tôi bấm — giới hạn ấy đã nêu rõ trong phiên và
đúng với mọi lệnh duyệt của sản phẩm này.
