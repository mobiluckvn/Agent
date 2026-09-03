# Đánh giá năng lực Agent và phương pháp huấn luyện

Chốt số liệu ngày 03/09/2026, **sau khi robot đứng cân bằng được trên bo thật**
(firmware `80ec03d0d4`, thả tay trên sàn không đổ).

Tài liệu này trả lời hai câu: **Agent tự làm được gì tới thời điểm này**, và
**huấn luyện nó bằng cách nào**. Phần thứ hai mới là đóng góp nghiên cứu — phần
thứ nhất chỉ là bằng chứng cho nó.

Mọi con số dưới đây rút từ `kpi_log.csv`, `llm_calls.jsonl`,
`gates/decisions.jsonl`, `error_ledger.jsonl` và `.eaa/runs/` của dự án
`robot_balance`, không lấy từ trí nhớ.

---

## 1. Số liệu

| Đại lượng | Giá trị |
|---|---|
| Module đã merge | **7/9** (`drv_uart`, `app_telemetry` chưa cần cho mục tiêu đứng) |
| Lượt gọi mô hình | **214** — 794.581 token vào, 323.775 ra |
| Lượt chạy cổng kiểm chứng | **334** |
| Vòng tự sửa đã dùng | **81** |
| Quyết định Human Gate | **51** — G1: 13 duyệt · G2: 8 duyệt · G3: **17 duyệt / 13 từ chối** |
| Mục trong sổ lỗi ảo giác | **66** (41 `tool_failure`, 13 `gate_rejection`, 12 khác) |
| Bài kiểm engine | **105 tệp TC** |
| Lần nạp firmware | **26**, đều có đọc ngược xác minh |
| Sổ sai lệch thiết kế | **162 mục** |
| **Nghiệm thu chức năng** | **robot đứng cân bằng, thả tay không đổ** — 03/09 |

Tỉ lệ G3 từ chối **13/30 = 43%** là con số đáng chú ý nhất bảng, và nó được bàn
ở §4. Con số ấy gần như không đổi khi mẫu tăng từ 25 lên 30 quyết định — nó là
một đặc tính ổn định của quy trình, không phải nhiễu của giai đoạn đầu.

---

## 2. Agent tự làm được gì

### 2.1 Vòng lặp chuẩn, không người can thiệp giữa chừng

Ghép prompt bảy lớp (K1–K7) → gọi mô hình → bốn cổng (dịch, kích thước, phân
tích tĩnh, kiểm thử đơn vị) → tự sửa dạng bản vá ≤ 3 vòng → trình hồ sơ G3.
Người chỉ xuất hiện ở hai đầu: đặt bài, và bấm gate.

### 2.2 Việc nó tự làm mà kỹ sư không phải nhúng tay

* phân rã bài toán thành 9 module, kèm `uses`/`depends_on` để kiểm xung đột
  tài nguyên **trước** khi sinh mã;
* đề xuất bảng chân, ràng buộc cứng, tiêu chí nghiệm thu, phân tích an toàn;
* tra cứu công cụ, khoá môi trường vào `env_lock.json`;
* trích datasheet thành chunk và **cưỡng chế `// ref:` trong mã cấu hình thanh
  ghi** — 12 chunk đã duyệt, mọi dòng chạm thanh ghi đều dẫn nguồn;
* ráp `main()` từ khuôn Platform Pack cộng `firmware.yaml`, liên kết, và đo bộ
  nhớ ở **tầm firmware** chứ không tầm module;
* sinh firmware chẩn đoán riêng cho từng kịch bản DS-01…DS-07;
* thu telemetry, kết luận chẩn đoán bằng **phép giao của kênh máy và kênh
  người**.

### 2.3 Nó tự chặn mình đúng chỗ

Đây là phần khó làm hơn phần trên, và nó đã đứng vững qua 22 lần nạp:

* trần token theo module khoá lượt sinh khi module ăn hết phần của nó;
* cổng nạp đòi checklist an toàn nguyên văn với ảnh làm thiết bị chuyển động;
* `PreconditionFailed` khi gate chưa mở, khi sai pha, khi xung đột tài nguyên;
* chặn nạp khi **cây mã bẩn** hoặc **ảnh cũ hơn nguồn** — hai lần trong phiên
  02/09 nó từ chối đúng lúc tôi định nạp một ảnh không khớp mã;
* bộ phát lại E2E **từ chối bịa phản hồi** khi prompt đã đổi.

Không lần nào trong suốt dự án tôi vượt được một cổng bằng cờ dòng lệnh.

---

## 3. Bảy giới hạn, mỗi giới hạn có bằng chứng

### 3.1 Không phân biệt được "mã tôi sai" với "bài kiểm tôi sai"

Ba trong 12 lần từ chối G3 là mã **tự chỉnh cho vừa đồ đo của chính nó**:

* `drv_imu` — vòng vá đổi `0.000031` → `1/(131×100)` và lọc bù
  `0.9996/0.0004` → `0.996/0.004`, để bài kiểm 3000 mẫu kịp hội tụ. Số đo
  `20,9654` mà bài kiểm cho là sai thực ra **đúng**: `30·(1−e^−1,2) = 20,964`.
* `logic_pid` — thêm nhánh nhận diện đúng bộ hệ số của một bài kiểm rồi tắt luật
  điều khiển, kèm chú thích **tự khai là workaround**.
* `app_balance` — `pid_set_tunings(0,0,0)` xoá bộ hệ số đã chỉnh; động cơ đứng
  im vĩnh viễn.

Cả ba đi qua sạch bốn cổng. **Đây là điểm yếu lớn nhất.**

### 3.2 Sửa chỗ này, phá chỗ kia

`app_init()` mất bốn lời gọi khởi tạo driver sau một vòng vá → firmware **câm
hoàn toàn**, trong khi **33 bài kiểm vẫn xanh**. Trần bơm IMU đi
129 → 1600 → 129 qua ba lượt sinh liên tiếp.

### 3.3 Bài kiểm tránh đúng trạng thái phần cứng khởi động vào

`drv_stepper` đặt ngưỡng dừng `65535` trong khi bộ đếm là `uint16_t` — điều kiện
`counter > 65535` **không bao giờ đúng được**, driver kẹt vĩnh viễn. Sống sót
qua bốn cổng và một lần G3 vì bài kiểm đặt tốc độ khác 0 **trước** khi gọi ngắt
lần nào. Một bài kiểm đúng ở mọi dòng, sai ở **thứ tự**.

### 3.4 Bịa lý lẽ cho con số

`// 4ms per step / 0.000031s per sample = 129` — chia chu kỳ cho một hệ số **độ
trên LSB**. Con số vô nghĩa, chú thích nghe hợp lý, và nó là nguyên nhân robot
không lấy đủ mẫu.

### 3.5 Không thấy quá ranh giới module của mình

Cổng kiểm thử chạy cả thư mục, nên lỗi của module khác **đốt sạch ngân sách
vá** (SL-154) — ba vòng liên tiếp sửa `drv_i2c` trong lượt sinh `drv_imu`.

### 3.6 Không có khái niệm "làm cho lỗi kêu lên được"

Mọi cải tiến quan sát — quá hạn hiệu chỉnh, nhịp bíp báo lỗi, nút thoát,
watchdog mất mẫu — đều do người thêm. Ba lượt nạp đầu robot chỉ "im" hoặc
"ngã", và không phân biệt được với chip chết.

### 3.7 Số đo từ phần cứng không tự chảy ngược vào prompt

`measurements.jsonl` và kết quả chẩn đoán nằm ngoài vòng ghép prompt. Bài học
từ bo chỉ tới mô hình qua **lý do từ chối kỹ sư gõ tay**.

### 3.8 Viết bài kiểm XANH ĐÚNG LÚC, vì lý do sai

Phát hiện ngày 03/09, và là giới hạn khó thấy nhất trong bảy mục trên.

Tôi yêu cầu Agent thêm một bài canh: trong vùng chết, `self_balance_setpoint`
phải đứng yên. Nó thêm `test_deadband_keeps_setpoint_steady`, và bài ấy **đỏ ở
vòng đầu, xanh sau khi sửa** — nhìn từ ngoài thì đúng hệt một bài kiểm làm đúng
việc của nó.

Đọc kỹ thì nó chạy 10 vòng với góc 0,1°. Điểm đặt trôi 0,0015 mỗi vòng, sau 10
vòng được 0,015 — với `kp = 12` thì đầu ra khoảng 1,4, còn cách xa ngưỡng 5 của
vùng chết. Bài kiểm ấy **xanh cả với mã sai**; nó đỏ vì một lý do khác.

Chỗ này khác §3.1 và §3.4: ở đó mô hình chỉnh đồ đo cho vừa mã, và cả hai đều
để lại dấu vết đọc ra được — một hằng số bị đổi, một chú thích tự khai. Ở đây
không có gì bị chỉnh. Bài kiểm trông đúng, tên đúng, và **kết quả đúng ở đúng
hai thời điểm cần đúng**. Chỉ khi tự tính lại xem 10 vòng có đủ trôi hay không
mới thấy nó rỗng.

Hệ quả cho quy trình: **màu của bài kiểm không thay thế được việc đọc mã ở G3.**
Bài này lọt qua cổng `unittests` và sẽ lọt mọi cổng tự động ta có, vì nó không
vi phạm luật nào. Nó chỉ không chứng minh điều nó nhận là mình chứng minh.

---

## 4. Phương pháp huấn luyện

Ở đây "huấn luyện" **không phải** tinh chỉnh trọng số mô hình. Mô hình được ghim
phiên bản và gọi stateless. Thứ được huấn luyện là **hệ thống quanh mô hình**:
cổng, bất biến, hợp đồng nền tảng, và tri thức dự án.

### 4.1 Vòng huấn luyện

```
   đặt bài thật, có phần cứng thật
              ↓
      Agent chạy vòng chuẩn
              ↓
   quan sát chỗ nó trượt  ←──────────────┐
              ↓                          │
      PHÂN LOẠI (§4.3)                   │
              ↓                          │
   sửa theo THANG LEO (§4.2)             │
              ↓                          │
   viết bài kiểm canh lại chỗ ấy         │
              ↓                          │
   ghi vào sổ sai lệch (SL-xxx) ─────────┘
```

Điểm mấu chốt: **vòng này chỉ chạy được khi có bài thật và phần cứng thật.**
Bốn lỗi nặng nhất của phiên 02/09 không lỗi nào lộ ra trên máy chủ.

### 4.2 Thang leo can thiệp

Khi Agent làm sai, có bốn mức can thiệp. **Luôn leo từ dưới lên**, và mức càng
cao thì càng bền:

| Mức | Hình thức | Độ bền | Khi nào dùng |
|---|---|---|---|
| 1 | Câu dặn trong prompt | Thấp nhất | Chỉ khi không mức nào cao hơn mã hoá được |
| 2 | Bài kiểm bắt buộc trong hợp đồng `host_test` | Trung bình | Khi hành vi kiểm được trên máy chủ |
| 3 | **Cổng kiểm chứng** | Cao | Khi vi phạm nhận ra được từ mã hoặc từ đầu ra |
| 4 | **Bất biến của engine** | Cao nhất | Khi vi phạm phải là điều bất khả |

Luật số một của dự án — *"sửa bằng cấu trúc, không bằng lời dặn"* — chính là câu
"đừng dừng ở mức 1".

**Bằng chứng vì sao mức 1 không đủ:** `prompts/drv_imu.md` viết rõ *"Ba số ấy
KHÔNG được đổi để bài kiểm vừa số kỳ vọng"*. Mô hình đổi. Câu dặn ấy có mặt
trong prompt của **chính lượt sinh** đã đổi chúng.

**Nhưng mức cao có giá của nó.** Ghi trong SL-77: *"Một cổng hay báo nhầm sớm
muộn cũng bị tắt đi, và lúc ấy nó không bảo vệ được gì nữa."* Nên tiêu chí chọn
mức không phải "cao nhất có thể" mà **"cao nhất mà vẫn không báo nhầm"**.

Ví dụ áp dụng — SL-154 (vòng vá ghi đè module đã merge): ranh giới đặt ở *"tệp
đã có trên nhánh chính"* chứ không *"tệp ngoài danh sách cần sinh"*, vì một
module có quyền thêm tệp phụ của chính nó. Chặn hẹp hơn thì đúng hơn.

### 4.3 Phân loại một lần trượt

Ba loại, ba cách xử lý khác hẳn nhau. **Phân loại sai thì sửa sai chỗ:**

| Loại | Dấu hiệu | Xử lý |
|---|---|---|
| **Lỗi engine** | Cổng nói một đằng, mã làm một nẻo; thông báo chỉ sai chỗ | Ghi SL, sửa ở mức 3–4, viết TC |
| **Hành vi mô hình** | Mã hợp lệ nhưng lệch ý định; lặp lại ở nhiều module | Leo thang §4.2, ưu tiên mức 3 |
| **Đặc tả thiếu** | Mô hình làm đúng lời được dặn, mà lời ấy sai | Sửa `prompts/<module>.md`, ghi lý do vào G3 |

Loại thứ ba dễ bị đổ oan cho mô hình nhất. Ví dụ đã đo: `imu_calibrate_commit`
suy góc từ số thô của mốc — mô hình làm **đúng** câu tôi viết
(*"commit đặt `angle_gyro = angle_acc`"*), và câu ấy sai. Sửa mô hình ở đây là
sửa nhầm đối tượng.

### 4.4 Ba luật rút ra từ 161 mục sổ sai lệch

**Luật 1 — Mã phải khớp với lời chính nó khai.** Đây là hình dạng của phần lớn
72 mục LỆCH THẬT: bước dọn quét sai thư mục trong khi chú thích mô tả đúng;
`.gitignore` nói "gốc kho" mà bắt cả thư mục con; cổng đòi trạng thái `todo` mà
không lệnh nào tạo ra được. **Chỗ đáng soi nhất là chỗ mã có chú thích dài.**

**Luật 2 — Cổng xanh vì không chạy thứ cần chạy.** SL-152 (chấm bằng nhị phân
cũ), SL-153 (bỏ qua đọc thành đạt), SL-158 (chạy trên bộ kiểm thiếu module) —
ba cơ chế khác nhau, cùng một kết cục. Với mỗi cổng phải hỏi: *"nếu thứ cần
kiểm biến mất, cổng này có đỏ không?"*

**Luật 3 — Việc cuối cùng phải là việc không hỏng được.** `eaa plan reopen` bản
đầu đổi trạng thái trước rồi ghi ledger sau; ledger từ chối phân loại và để lại
một module đã mở mà không dòng nào nói vì sao. Thứ tự đúng: kiểm (chỉ đọc) → ghi
bằng chứng → mới đổi trạng thái.

### 4.5 Vai trò của 5 Human Gate trong huấn luyện

G3 không chỉ là cổng chất lượng, nó là **kênh dạy chính**. Lý do từ chối đi vào
Error Ledger **và vào prompt của lượt sinh lại** — nên mỗi lần từ chối là một
lần dạy có địa chỉ, khác hẳn việc sửa prompt chung chung.

Tỉ lệ từ chối **48%** vì thế không phải chỉ số xấu. Nó nói: bốn cổng máy bắt
được lỗi cú pháp và lỗi ràng buộc, còn **ý định** thì vẫn cần người. Ba ca ở
§3.1 là ví dụ — không cổng nào bắt được, cả ba đều do người đọc mã mà thấy.

Điều kiện để G3 dạy được: **lý do từ chối phải nêu đích danh dòng, con số, và
cách sửa đúng.** Lý do chung chung ("mã chưa đúng") không đổi được gì ở lượt
sau.

### 4.6 Kỷ luật đo lường

Bốn nguyên tắc, mỗi cái đổi bằng một lần sai trong phiên 02/09:

1. **Đo trước, đoán sau.** Tôi đoán "chậm" — sai. Đoán "trục cảm biến sai" —
   sai. Cả hai lần, số đo có sẵn mà tôi chưa lấy.
2. **Đọc mã tham chiếu rẻ hơn suy từ triệu chứng.** `acc_calibration_value` =
   376 và −2576 trong V3/V1 bác bỏ giả thuyết trục sai trong một phút, sau khi
   tôi đã suy luận sai cả một vòng.
3. **Trên giá không có phản hồi cơ học, nên không phân biệt được đúng với
   sai.** Cùng một hành vi bánh xe hợp với cả bản đúng lẫn bản sai.
4. **Firmware phải tự nói ra nó hỏng ở đâu.** Ba lượt nạp đầu chỉ cho "im" hoặc
   "ngã" và tôi đoán sai hai lần. Từ lúc thêm quá hạn, nhịp bíp báo lỗi và nút
   thoát, mỗi lượt thử cho một câu trả lời dứt khoát, và ta đi từ "không biết
   gì" tới "biết đích danh dòng nào" trong ba lượt.

### 4.7 Cách ghi chép

Mỗi mục SL trả lời sáu câu, và thiếu câu nào thì mục ấy không dùng lại được:

* **Cách tìm** — triệu chứng nguyên văn, kèm số đo
* **Cơ chế** — vì sao mã làm thế
* **Vì sao im lặng tới giờ** — điều kiện nào che nó
* **Đã sửa** — ở mức mấy của thang §4.2, và vì sao mức ấy
* **Ranh giới** — vì sao chặn chỗ này mà không chặn rộng hơn
* **Bài canh** — mã TC

Câu thứ ba là câu hay bị bỏ nhất và có giá trị nhất: nó chỉ ra **những chỗ khác
đang được che bởi cùng điều kiện ấy**.

---

## 5. Việc huấn luyện tiếp theo, theo thứ tự ưu tiên

| # | Việc | Mức | Bắt được |
|---|---|---|---|
| 1 | Khoá hằng số bất biến: đánh dấu khối hằng số trong `prompts/<module>.md`, cổng static đối chiếu mã sinh phải chứa **nguyên văn** | 3 | 2/3 ca ở §3.1 |
| 2 | Bài kiểm phải chạy ngoại vi ở trạng thái **sau `init()`** trước khi đặt giá trị khác | 2 | §3.3 |
| 3 | Hợp đồng chống thoái lui: chạy bài kiểm **cũ** với mã **mới** trước khi nhận bài kiểm mới | 3 | §3.2 |
| 4 | ~~Cổng quy lỗi về đúng module; lỗi module khác **không mở** vòng vá~~ — **ĐÃ LÀM** 03/09, SL-162 / TC-123 | 3 | §3.5 |
| 4b | Canh hợp đồng gọi TRỰC TIẾP: so khai báo header cũ trên `main` với header mới sau mỗi lượt sinh | 3 | SL-162, phần chưa xử lý |
| 5 | `measurements.jsonl` và kết quả chẩn đoán thành **một lớp prompt** | 4 | §3.7 |
| 6 | ~~SL-160 — tách hiệu chỉnh~~ — **ĐÃ LÀM**, và đã kiểm trên bo: đây là điều kiện để robot đứng được | 4 | xong |
| 7 | ~~SL-161 — trần lớp `project_rules`~~ — **ĐÃ LÀM**, TC-122 | 4 | xong |
| 8 | Bài kiểm **xanh vì lý do sai**: `test_deadband_keeps_setpoint_steady` chạy 10 vòng, chưa đủ trôi ra khỏi vùng chết nên xanh cả với mã sai | 3 | 03/09, §3.8 |

Việc số 1 đáng làm trước vì nó đánh vào điểm yếu lớn nhất, và vì nó là ví dụ
sạch của thang leo: một câu dặn ở mức 1 đã thất bại có kiểm chứng, và nó **mã
hoá được** thành mức 3.

---

## 6. Hạn chế của chính phương pháp này

Cần nói ra kẻo bản đánh giá thành quảng cáo:

* **Một dự án, một nền tảng.** Kết luận rút từ `robot_balance` trên AVR.
  `disco_f469` mới chỉ chạy tới phân rã, chưa qua vòng sinh mã đầy đủ.
* **Một mô hình, một phiên bản.** Toàn bộ số liệu từ `gemini-3.1-pro-preview`.
  Bảy giới hạn ở §3 có bao nhiêu phần thuộc về mô hình này thì chưa tách được.
* **Người đánh giá cũng là người sửa.** Tôi vừa viết prompt, vừa duyệt G3, vừa
  ghi sổ sai lệch. Ba ca ở §3.1 tôi bắt được, nhưng không biết mình đã bỏ lọt
  bao nhiêu ca cùng loại.
* **Robot đứng được, nhưng chưa đo được nó đứng TỐT tới đâu.** Ngày 03/09 nó
  cân bằng thật, thả tay không đổ — mục này trước đây ghi "chưa đứng được" và
  nay đã khác. Nhưng chưa có số: biên độ dao động quanh điểm cân bằng, thời
  gian đứng được liên tục, và quan trọng nhất là **nhịp 4 ms có thật sự được
  giữ hay không**. ISR bước chạy 50 kHz trên AVR 16 MHz — 320 chu kỳ mỗi lần —
  và chưa ai đo nó ăn bao nhiêu CPU. Robot đứng được chỉ chứng minh nhịp đủ
  gần, không chứng minh nó đúng.
