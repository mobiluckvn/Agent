# Nhật ký test tổng hợp — hồ sơ robot BLKLab

Người ra đề: Vũ Trí Công · Người thao tác: Claude (thay mặt) · Ngày 30/08/2026

Vật liệu: `data/BLKLab_BalancingRobot.zip` — 142 MB nén, ~279 MB giải nén,
308 mục. Gồm 44 tệp `.ino`, 30 `.h`, 22 `.cpp`, 22 ảnh PNG, 6 ảnh JPG,
14 mô hình in 3D `.stl`, 4 PDF, 6 `.md`, 18 `.mp3`, 4 `.apk`.

Ba bài:

1. Agent tự giải nén, khai phá, đưa ra mô tả và toàn bộ thông tin hữu ích về mạch.
2. Agent nêu quy trình hiện tại mà tài liệu cung cấp.
3. Agent viết mã mới để robot tự đứng được.

Nhật ký này ghi **nguyên văn** câu lệnh tôi ra cho Agent và **nguyên văn** thứ
Agent trả về, kể cả khi nó từ chối. Chỗ nào tôi can thiệp thì ghi rõ là tôi
can thiệp, không trộn vào phần Agent làm.

---

## Vòng 0 — đo năng lực hiện có, trước khi sửa gì

Chạy trước khi động vào mã, để có mốc so sánh. Nếu Agent làm được ngay thì
không cần thêm gì; nếu không thì chỗ nó dừng lại chính là chỗ cần xây.

### Bài 1 — giải nén và khai phá

> **Tôi ra lệnh:** Mình vừa đặt toàn bộ tài liệu của con robot vào tệp
> `data/BLKLab_BalancingRobot.zip` — trong đó có ảnh, file PDF, sơ đồ mạch và
> code mẫu. Bạn hãy tự giải nén nó ra, đọc hết, rồi mô tả cho mình con mạch
> đó: dùng vi điều khiển gì, có những ngoại vi và linh kiện nào, nối chân ra
> sao.

**Agent làm gì:** không chạy lệnh nào.

> **Agent trả lời:** Tôi không có lệnh để tự giải nén tệp zip hay đọc trực
> tiếp các tệp bên trong đó. Bạn cần tự giải nén và đưa các tài liệu (PDF, sơ
> đồ) vào hệ thống (ví dụ thông qua công cụ quản lý datasheet của EAA), hoặc
> cung cấp trực tiếp thông tin về vi điều khiển, ngoại vi và sơ đồ chân để tôi
> có thể hỗ trợ tiếp.

**Nhận xét.** Từ chối đúng và **không bịa** — nó không dựng ra một mô tả mạch
nghe hợp lý từ cái tên tệp, dù cái tên ấy có chữ "BalancingRobot" và thừa sức
gợi ý. Nhưng đây là một khoảng trống năng lực thật: hồ sơ gốc của một dự án
thường tới dưới dạng một kho nén, và AIS §6.1 (FR-ING-01) vốn đã đặc tả việc
nhận và phân loại bốn loại đầu vào — kho nén chỉ là cái vỏ đựng chúng.

### Bài 2 — quy trình hiện tại trong tài liệu

> **Tôi ra lệnh:** Trong bộ tài liệu robot đó có mô tả quy trình làm việc hiện
> tại. Bạn đọc rồi tóm tắt lại cho mình: người ta đang làm theo các bước nào,
> từ lúc nạp firmware tới lúc robot đứng được.

**Agent làm gì:** chạy `eaa docs list` (mã 0), rồi `eaa datasheet list` (mã 2).

> **Agent trả lời:** Hiện tại kho tài liệu của dự án đang trống và các trích
> đoạn datasheet chỉ chứa thông tin về thanh ghi của ATmega328P và MPU6050.
> Tôi không tìm thấy tài liệu nào mô tả quy trình làm việc của robot từ lúc
> nạp firmware đến lúc đứng được. Bạn có thể cung cấp thêm tài liệu hoặc chỉ
> rõ tài liệu đó nằm ở đâu không?

**Nhận xét.** Đây là hành vi đúng nhất trong ba bài: nó **đi tìm trước rồi mới
kết luận**, nói rõ đã tìm ở đâu, và hỏi lại thay vì đoán. Nhưng nó chỉ tìm
được trong kho tri thức của dự án — kho nén nằm ngoài tầm với.

### Bài 3 — viết mã mới

> **Tôi ra lệnh:** Bây giờ bạn viết mã mới cho con robot này để nó tự đứng
> được nhé.

**Agent làm gì:** chạy `eaa status` (mã 2), rồi `eaa gate show G1` (mã 2).

> **Agent trả lời:** Dự án hiện đang ở pha A (Phân tích yêu cầu) và backlog
> chưa có module nào. Để có thể lên kế hoạch và viết mã, chúng ta cần chốt
> ràng buộc cứng và kiến trúc. Bạn vui lòng chạy lệnh duyệt G1 trước nhé.
> Lệnh bạn cần tự chạy: `eaa gate approve G1`

**Nhận xét.** Đây **không** phải một khoảng trống — đây là sản phẩm đang làm
đúng điều nó sinh ra để làm. Mã không đến từ một câu trả lời trong hội thoại;
nó đến từ vòng lặp có cổng, và cổng đầu tiên là G1. Một Agent trả lời câu này
bằng cách dán ra hai trăm dòng C mới là Agent đã hỏng.

### Kết luận vòng 0

| Bài | Kết cục | Loại |
|---|---|---|
| 1 | Không làm được | **Thiếu năng lực** — cần xây |
| 2 | Tìm đúng chỗ, không thấy, hỏi lại | Thiếu năng lực (cùng gốc với bài 1) |
| 3 | Điều hướng về quy trình có cổng | **Đúng thiết kế** — không sửa |

Việc phải làm: cho Agent đọc được một kho nén tài liệu. Bài 3 giữ nguyên.

---

## Vòng 1 — sau khi bổ sung năng lực đọc kho tài liệu

Chạy ngày 31/08/2026, sau khi Agent đã có thêm: `survey` (đọc kho nén),
`research`/`read` (ra web thật), `focus` (nhìn cả quãng đường), và
`gen --preview` (sinh mã khi máy chưa có toolchain).

Mô hình: Gemini 3.1 Pro, gọi thật. Dự án: `projects/robot_balance`
(ràng buộc ATmega328P, khớp với bo BLKLab — xác nhận ở bài 1).

### Bài 1 — giải nén và khai phá

> **Tôi ra lệnh** (nguyên văn, không đổi so với vòng 0): Mình vừa đặt toàn bộ
> tài liệu của con robot vào tệp `data/BLKLab_BalancingRobot.zip` — trong đó có
> ảnh, file PDF, sơ đồ mạch và code mẫu. Bạn hãy tự giải nén nó ra, đọc hết,
> rồi mô tả cho mình con mạch đó: dùng vi điều khiển gì, có những ngoại vi và
> linh kiện nào, nối chân ra sao.

**Agent làm gì:** `eaa survey data/BLKLab_BalancingRobot.zip --extract` (mã 0).
Một lệnh, tự chọn, tự thêm cờ `--extract`.

> **Agent trả lời** (rút gọn phần trình bày, giữ nguyên nội dung):
>
> **1. Vi điều khiển:** họ AVR (khả năng cao là ATmega328P trên Arduino
> Nano/Uno). Thể hiện qua đuôi `.ino` và việc can thiệp thẳng vào `OCR2A`,
> `TCCR2A`, `TIMSK2` (Timer 2) và `TWBR` (I2C).
>
> **2. Linh kiện và ngoại vi:** động cơ bước điều khiển bánh xe · cảm biến siêu
> âm SRF04 · IMU qua I2C (`Wire.h`) dùng `SimpleKalmanFilter.h` (thường là
> MPU6050) · module âm thanh JQ6500 qua UART mềm · LED RGB qua
> `Adafruit_NeoPixel.h` · nút nhấn và còi.
>
> **3. Sơ đồ nối chân (trích từ mã nguồn):** chân 2 SRF04_ECHO · 4 DIR1 ·
> 5 STEP1 · 6 DIR2 · 7 STEP2 · 12 BUTTON_SET_PIN · 13 output (thường là LED
> onboard) · I2C ở A4/A5. *"Các chân cho còi, NeoPixel, JQ6500, SRF04_TRIG chưa
> hiện đầy đủ trong bản tóm tắt nhưng chắc chắn có mặt trong mã."*

**Tôi kiểm chéo** bằng cách `grep` thẳng vào mã nguồn đã giải nén:

| Agent nói | Mã nguồn thật | |
|---|---|---|
| SRF04_ECHO = 2 | `#define SRF04_ECHO  2` | ✓ |
| DIR1 = 4 | `#define DIR1        4` | ✓ |
| STEP1 = 5 | `#define STEP1       5` | ✓ |
| DIR2 = 6 | `#define DIR2        6` | ✓ |
| STEP2 = 7 | `#define STEP2       7` | ✓ |
| BUTTON_SET_PIN = 12 | `#define BUTTON_SET_PIN 12` | ✓ |
| SimpleKalmanFilter, Wire, NeoPixel, SoftwareSerial | đều có trong `#include` | ✓ |

**6/6 chân đúng nguyên văn.** Không có con số nào bịa.

**Nhận xét.** Đây là bước tiến rõ so với vòng 0 (khi ấy: không làm được gì).
Hai điểm đáng ghi:

- Nó **tự nói ra chỗ mình chưa thấy đủ** (`SRF04_TRIG`, chân còi, NeoPixel)
  thay vì điền một con số nghe hợp lý. Đối chiếu lại: `SRF04_TRIG` thật sự là
  3 — nó đã có thể đoán đúng, và nó không đoán.
- **Chỗ còn thiếu:** kho có `DistanceGP2Y0A41SK.h`, `DistanceGP2Y0A21YK.h`
  (cảm biến hồng ngoại Sharp) và `BLEPeripheral.h` mà Agent không nhắc. Đây là
  **thiếu sót về độ phủ**, không phải bịa — bản tóm tắt của `survey` cắt bớt,
  và Agent chỉ đọc bản tóm tắt ấy.

### Bài 2 — quy trình hiện tại trong tài liệu

> **Tôi ra lệnh:** Trong bộ tài liệu robot đó có mô tả quy trình làm việc hiện
> tại. Bạn đọc rồi tóm tắt lại cho mình: người ta đang làm theo các bước nào,
> từ lúc nạp firmware tới lúc robot đứng được.

**Agent làm gì:** thử `ls -la` → **bị danh mục từ chối**; rồi `eaa datasheet
list` (mã 2), `eaa docs list` (mã 0), `eaa handover doc` (mã 2).

> **Agent trả lời:** Dựa vào tài liệu vận hành, quy trình hiện tại gồm 3 bước
> chính: **1. Nạp firmware** (`eaa build` → `eaa ports` → `eaa flash`).
> **2. Đo và nghiệm thu** (`eaa telemetry`, `eaa tune` với ngưỡng góc nghiêng
> ≤ 1.0°, `eaa endurance` 10 phút). **3. Chẩn đoán sự cố** (`eaa diagnose
> select` → `build` → `run`).

**Đây là câu trả lời SAI — và là phát hiện quan trọng nhất của vòng này.**

Câu hỏi là về quy trình trong **tài liệu BLKLab**. Agent trả lời quy trình vận
hành **của chính công cụ EAA**, đọc từ `eaa handover doc`. Hai thứ không liên
quan gì tới nhau.

**Tôi kiểm** xem tài liệu quy trình thật nằm ở đâu:

```
BLKLab_Huong_Dan/BLKLab_Balancing_Robot_Nguyen_Ly.pdf
BLKLab_Huong_Dan/BLKLab_Balancing_Robot_Tong_Quan.pdf
```

Hai tệp PDF tiếng Việt. Mọi tệp `.md` trong kho đều là README của thư viện bên
thứ ba (`SimpleKalmanFilter`, `Adafruit_NeoPixel`), không phải tài liệu dự án.

**Hai lỗi chồng lên nhau, và cái thứ hai nặng hơn:**

1. **Thiếu năng lực** — Agent không đọc được nội dung PDF trong kho đã giải
   nén. `survey` kiểm kê được *có những tệp gì* nhưng không mở được chúng ra.
   Dấu vết rất rõ: nó đã thử `ls -la` và bị danh mục chặn — nó **muốn** đi đọc
   và không có đường.
2. **Lỗi hành vi** — thay vì nói "quy trình nằm trong hai PDF này, tôi chưa đọc
   được", nó trả lời **chắc nịch từ một nguồn không liên quan**. Không một câu
   nào trong câu trả lời gắn nhãn mức tin cậy, và không câu nào nói rõ nguồn là
   tài liệu của EAA chứ không phải của BLKLab.

Lỗi thứ hai đúng là thứ mà cả bộ từ vựng tin cậy (N-903) sinh ra để chặn, và ở
đây nó không chặn được vì `handover doc` trả về một tài liệu **hợp lệ** — chỉ
là hợp lệ cho một câu hỏi khác.

### Bài 3 — viết mã mới

> **Tôi ra lệnh:** Bây giờ bạn viết mã mới cho con robot này để nó tự đứng
> được nhé.

**Agent làm gì:** không chạy lệnh nào; trả lời và soạn lệnh cho tôi.

> **Agent trả lời:** Dự án hiện đang ở Pha A, backlog trống và Gate 1 đang chờ
> duyệt. Tôi không thể tự viết toàn bộ mã ngay lập tức. Bạn cần duyệt Gate 1
> trước, sau đó tôi sẽ giúp bạn thêm các module cần thiết (như IMU, PID, điều
> khiển động cơ) vào backlog bằng lệnh `plan add`.
> Lệnh bạn cần tự chạy: `eaa gate approve G1`

**Nhận xét.** Giống vòng 0 và vẫn **đúng thiết kế**, nhưng khá hơn: lần này nó
nêu đích danh ba module cần có thay vì chỉ nói "cần duyệt gate".

#### Tôi đi tiếp đường có cổng, thay mặt anh

Từ đây là **tôi thao tác**, không phải Agent — ghi rõ để khỏi lẫn.

```
$ eaa init                                                    → mã 0
$ eaa plan add drv_imu --uses twi                             → mã 0
$ eaa plan add ctl_balance --uses timer1 --depends-on drv_imu → mã 0
$ eaa focus ctl_balance
```

`focus` bày ra cả quãng đường: 4/6 chặng đã qua (chuỗi cổng đủ, module có trong
backlog, không xung đột tài nguyên, **đủ tri thức để sinh mã**), còn 2 chặng và
cả hai là gate của người.

Máy này chưa có toolchain AVR, nên tôi dùng chế độ xem trước:

```
$ eaa gen ctl_balance --preview
```

**Mã Agent sinh ra** (nguyên văn, rút gọn phần `.h`):

```c
void ctl_balance_init(void) {
    // ref: ds-012, ATmega328P datasheet rev. DS40002061B, tr.140-145
    TCCR1A = 0x00;
    TCCR1B = (1 << WGM12) | (1 << CS11);
    OCR1A = 19999;
    TIMSK1 = (1 << OCIE1A);
}

ISR(TIMER1_COMPA_vect) {
    ctl_balance_flag = 1;
}

void ctl_balance_update(void) {
    if (ctl_balance_flag) {
        ctl_balance_flag = 0;
        // TODO: Tích hợp drv_imu và logic điều khiển cân bằng tại đây
        // khi module drv_imu sẵn sàng.
    }
}
```

**Tôi kiểm hai điều nó khẳng định:**

| Kiểm | Kết quả |
|---|---|
| `ds-012` có thật không, nói về gì | Có — `atmega328p__timer1_ctc.md`, khai đúng bốn thanh ghi `TCCR1A, TCCR1B, OCR1A, TIMSK1` mà mã chạm tới |
| Chu kỳ vòng điều khiển | 16 MHz ÷ 8 (CS11) = 2 MHz; (19999+1) ÷ 2 MHz = **10,00 ms = 100 Hz**. Đúng cho một vòng cân bằng |

**Nhận xét.** Ba điều đáng ghi, và điều thứ ba là điều tôi muốn anh chú ý nhất:

- **Trích dẫn đúng và kiểm được.** `// ref: ds-012` trỏ tới một chunk có thật,
  phủ đúng những thanh ghi mã dùng. Đây là bất biến TC-17 đang làm việc.
- **Số học đúng.** 100 Hz là lựa chọn hợp lý cho vòng cân bằng con lắc ngược,
  và nó tính đúng chứ không chọn một số tròn nghe hay.
- **Nó DỪNG ở chỗ đúng, và nói ra.** Nó không viết luật PID, mà để một `TODO`
  nêu rõ đang chờ `drv_imu`. Vì `ctl_balance` khai `--depends-on drv_imu` mà
  module ấy chưa merge, nên hợp đồng gọi của nó chưa tồn tại — viết bừa một
  lời gọi vào một API chưa ai định nghĩa là đúng loại mã trông chạy được mà
  không dịch nổi.

  **Nhưng** so với câu tôi hỏi ("robot tự đứng được") thì đây là **chưa xong**.
  Muốn xong thì phải sinh `drv_imu` trước, merge nó, rồi mới sinh
  `ctl_balance` — tức là đi đủ vòng có cổng, và vòng ấy cần toolchain.

### Kết luận vòng 1

| Bài | Vòng 0 | Vòng 1 | Đánh giá |
|---|---|---|---|
| 1 — khai phá mạch | Không làm được | **Làm được, 6/6 chân đúng** | Đạt; thiếu độ phủ (bỏ sót 2 cảm biến) |
| 2 — quy trình trong tài liệu | Tìm đúng chỗ, hỏi lại | **Trả lời SAI từ nguồn khác** | **Không đạt — và tệ hơn vòng 0** |
| 3 — viết mã mới | Điều hướng về gate | Điều hướng về gate, rồi **sinh được mã đúng trích dẫn, đúng số học** | Đạt phần khung; chưa xong luật điều khiển |

**Bài 2 đi lùi**, và đó là kết quả đáng giá nhất của vòng này. Ở vòng 0, Agent
không có năng lực nên nó **hỏi lại**. Ở vòng 1, nó có thêm nhiều nguồn để đọc
— và nó dùng nhầm một nguồn rồi trả lời như thể đã đọc đúng chỗ. Thêm năng lực
mà không thêm kỷ luật về nguồn thì làm câu trả lời sai *tự tin hơn*, không
phải đúng hơn.

### Việc phải làm, rút từ vòng này

1. **Đọc được nội dung PDF trong kho đã giải nén.** Quy trình BLKLab nằm trong
   hai PDF tiếng Việt; không đọc được chúng thì bài 2 không thể đạt.
2. **Buộc nêu NGUỒN khi trả lời về nội dung tài liệu.** Câu trả lời bài 2 lẽ ra
   phải mang một câu kiểu *"đọc từ `eaa handover doc` — tài liệu vận hành của
   dự án EAA, KHÔNG phải tài liệu BLKLab"*. Có câu ấy thì chính người đọc phát
   hiện ra ngay.
3. **`survey` nên bày đủ hơn**, hoặc cho Agent hỏi tiếp về một phần cụ thể của
   kho thay vì chỉ đọc một bản tóm tắt cắt sẵn.

Bài 3 vẫn giữ nguyên: không sửa gì: nó đang làm đúng.

---

## Vòng 2 — sau khi sửa ba việc rút từ vòng 1

Chạy 31/08/2026. Ba việc đã làm, đúng thứ tự tôi đề ra ở cuối vòng 1:

1. `eaa/pdftext.py` + `eaa survey --read` — đọc được nội dung PDF.
2. Kỷ luật **nêu nguồn** — `ChatResult.sources`, trường `nguon`, luật thứ 5
   trong vai trò, và cảnh báo khi trả lời mà không khai nguồn.
3. `eaa survey --files` để soi kỹ một phần kho, và lớp trạng thái **nói cho
   Agent biết dự án CÓ một kho đã giải nén**.

### Bài 1 — giải nén và khai phá

Cùng câu hỏi nguyên văn ba vòng.

**Agent làm gì — sáu lệnh, tự chọn cả sáu:**

```
survey --read …/BLKLab_Balancing_Robot_Tong_Quan.pdf
survey --read …/BLKLab_Balancing_Robot_Nguyen_Ly.pdf
survey --files *.ino
survey --read …/V0_Balancing_Hardware/V0_Balancing_Hardware.ino
survey --read …/V1_Balancing_Robot_HC05_JQ6500/V1_…_JQ6500.ino
survey --read …/BLKLab_Balancing_Robot_Nguyen_Ly.pdf     (đọc lại sơ đồ)
```

> **Agent trả lời:**
>
> **1. Vi điều khiển:** Arduino Nano.
>
> **2. Ngoại vi và linh kiện:** MPU6050 (IMU 6 trục) · **2 driver A4988** điều
> khiển **2 động cơ bước Nema17 (42×38mm)** · Bluetooth HC-05 · module MP3
> JQ6500 kèm **loa 1W 8Ω** · **4 LED RGB WS2812** · còi chip 5V · nguồn **2
> cell Li-ion 18650** qua IC **78M05** · header chờ cho SRF04.
>
> **3. Nối chân:** MPU6050 I2C (SDA→A4, SCL→A5) · JQ6500 dùng TX/RX phần cứng
> D0/D1 *(lưu ý tháo module khi nạp code)* · nút SET→D12 · WS2812→D11 ·
> HC-05 SoftwareSerial D9 (RX), D11 (TX).
>
> *"Lưu ý: Trong code đang có sự trùng lặp chân D11 giữa TX của HC-05 và LED
> WS2812, bạn cần kiểm tra lại thực tế mạch."*

**Tôi kiểm chéo** vào chính tệp `V1_..._JQ6500.ino`:

| Agent nói | Mã nguồn thật | |
|---|---|---|
| WS2812 ở D11, 4 LED | dòng 70–71: `const int ledPin = 11; const int numLeds = 4;` | ✓ |
| HC-05 SoftwareSerial D9/D11 | dòng 68: `SoftwareSerial mySerial(9, 11); // RX, TX` | ✓ |
| Nút SET ở D12 | dòng 58: `#define BUTTON_SET_PIN 12` | ✓ |
| **Xung đột chân D11** | cả hai dòng trên cùng dùng 11 | ✓ **có thật** |

**Nhận xét.** Hơn hẳn vòng 1 ở ba điểm:

- **Độ phủ.** Vòng 1 đọc một bản tóm tắt cắt sẵn và bỏ sót cảm biến. Vòng 2 nó
  *tự đi tìm tiếp* — liệt kê `.ino`, chọn hai tệp, đọc thẳng — và ra được cả
  A4988, Nema17, 18650, 78M05, 78M05, số lượng LED. Đây đúng là thứ `--files`
  và `--read` sinh ra để cho phép.
- **Nó tìm ra một lỗi trong mã của người khác.** Xung đột D11 là thật, và nó
  nêu kèm câu *"bạn cần kiểm tra lại thực tế mạch"* — không khẳng định là lỗi,
  vì SoftwareSerial TX của HC-05 có thể không bao giờ được dùng. Đây là hành vi
  đúng: chỉ ra chỗ đáng nhìn, không phán.
- **Nó khai nguồn**, và khai đúng hai tệp mang thông tin quyết định.

### Bài 2 — quy trình hiện tại trong tài liệu

Cùng câu hỏi nguyên văn.

**Agent làm gì:** `survey --read` **cả hai PDF**.

> **Agent trả lời:** Mình đã đọc 2 tài liệu PDF trong thư mục `BLKLab_Huong_Dan`
> (Tổng quan và Nguyên lý) nhưng **không có** tài liệu nào mô tả quy trình từ
> lúc nạp firmware tới lúc robot đứng được.
>
> Bản 'Tổng quan' chỉ liệt kê các tính năng (cân bằng PID, điều khiển
> Bluetooth, tránh vật cản, chỉnh PID realtime) và linh kiện. Bản 'Nguyên lý'
> là sơ đồ mạch điện (schematic).
>
> Bạn có muốn mình quét thử các tệp mã nguồn (`.ino`, `.cpp`) để xem có ghi
> chú nào hướng dẫn quy trình này không?
>
> **Trả lời này dựa trên:** hai lệnh `survey --read` nêu trên.

**Tôi kiểm:** đúng. `Tong_Quan.pdf` là trang giới thiệu tính năng;
`Nguyen_Ly.pdf` là netlist sơ đồ mạch. Kho **không có** tài liệu quy trình
từng bước — mọi tệp `.md` trong kho đều là README của thư viện bên thứ ba.

**Nhận xét.** Bài này đi từ **không đạt** lên **đạt**, và đạt theo cách đáng
tin nhất: nó **đọc thật rồi mới kết luận**, nói rõ mỗi tệp chứa gì, khai nguồn,
và đề nghị một bước tiếp hợp lý.

Đáng ghi thêm: hoá ra **tiền đề của bài 2 hơi lệch** — kho không thật sự có
tài liệu quy trình. Vòng 1 Agent "trả lời được" chính là vì nó lấy tài liệu
khác thế vào. Vòng 2 nó nói ra sự thật ấy. Một câu trả lời "không có" đúng thì
giá trị hơn một câu tóm tắt trôi chảy về nhầm tài liệu.

### Bài 3 — viết mã mới

**Agent làm gì:** `eaa status`, `eaa gate show G1`.

> **Agent trả lời:** Dự án hiện đang ở pha A và backlog đang trống… cần khai
> báo module (`eaa plan add`), chia ngân sách (`eaa budget propose`), và bạn
> cần duyệt G1.
>
> *"Bạn muốn tự khai báo các module, hay muốn mình **đọc các tài liệu PDF
> trong kho** (`…Tong_Quan.pdf`, `…Nguyen_Ly.pdf`) để **đề xuất danh sách
> module** cho bạn?"*

**Nhận xét.** Vẫn điều hướng về quy trình có cổng — đúng thiết kế, không đổi
qua cả ba vòng. Nhưng câu cuối là mới và là bước tiến thật: nó **nối bài 1 với
bài 3**, đề nghị dùng chính tài liệu vừa đọc được để đề xuất phân rã module.
Vòng 0 và vòng 1 không có ý ấy.

Phần sinh mã thật đã chạy ở vòng 1 (`gen ctl_balance --preview`, Timer1 CTC
100 Hz, trích dẫn `ds-012` — đã kiểm đúng cả hai). Vòng 2 không chạy lại vì
phần ấy không đổi.

### Kết luận vòng 2

| Bài | Vòng 0 | Vòng 1 | Vòng 2 |
|---|---|---|---|
| 1 — khai phá mạch | Không làm được | Đạt, 6/6 chân đúng, **thiếu độ phủ** | **Đạt, phủ rộng hơn hẳn, tìm ra một xung đột chân thật** |
| 2 — quy trình trong tài liệu | Hỏi lại | **Trả lời SAI từ nguồn khác** | **Đạt — đọc thật, kết luận đúng "không có", khai nguồn** |
| 3 — viết mã mới | Điều hướng về gate | Điều hướng + sinh mã đúng ở `--preview` | Điều hướng + **đề nghị dùng tài liệu để phân rã module** |

### Bốn lần hệ thống tự chặn tôi trong vòng này

Đáng ghi riêng, vì cả bốn đều là cổng làm đúng việc:

1. **Ngân sách lớp `role_constraints`** chặn khi tôi thêm luật nêu nguồn. Đúng
   — đó là ngân sách của *vòng sinh mã* theo AIS §2, không phải của hội thoại.
   Sửa: vòng hội thoại khai ngân sách riêng (SL-97).
2. **Ngân sách lớp `observations`** chặn khi Agent đọc PDF. Nới một lần thì
   chạy, nhưng lần sau lại tràn — nới mãi là chạy theo đuôi. Sửa: lớp quan sát
   **tự cắt cho vừa** và nói ra đã bỏ bao nhiêu.
3. **Bộ đếm token thật** chặn tiếp: tôi cắt theo `estimate_tokens`, mà bộ ấy cố
   ý đếm *cao* cho tiếng Anh nên hoá ra đếm *thấp* cho tiếng Việt có dấu —
   3.400 ước lượng bị đếm thật thành 4.327. Sửa: cắt bằng chính bộ đếm sẽ kiểm.
4. **`ls -la`** bị danh mục từ chối ở vòng 1 — và chính lần từ chối ấy là manh
   mối chỉ ra khoảng trống: Agent *muốn* đi đọc tệp và không có đường.

### Điều còn lại, nói cho đủ

- **Ảnh không đọc được.** Kho có `BLKLab_Balancing_Robot_HD1/HD2/HD3.png` —
  ba trang hướng dẫn dạng ảnh. Nếu quy trình từng bước tồn tại ở đâu đó thì
  nhiều khả năng nằm trong ba tệp ấy. Đọc chúng cần OCR, một công cụ ngoài mà
  hệ này chưa có, và `pdftext` nói thẳng điều đó thay vì trả về chuỗi rác.
- **40/1884 ký tự rụng** khi đọc `Tong_Quan.pdf`. Đã kiểm: `'á'` không nằm
  trong bất kỳ bảng `ToUnicode` nào của tệp — mất mát nằm ở **tệp**, không ở
  bộ đọc. Bộ đọc đếm và báo đúng con số ấy.
- **Bài 3 chưa xong tới đích.** Muốn robot thật sự đứng được thì phải sinh
  `drv_imu`, merge, rồi mới sinh `ctl_balance` — tức là đi đủ vòng có cổng, và
  vòng ấy cần toolchain AVR mà máy này chưa có.

