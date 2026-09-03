# Đánh giá năng lực Agent và phương pháp huấn luyện

Chốt số liệu ngày 03/09/2026, sau khi firmware chạy thật trên bo lần đầu.

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
| Module đã merge | **8/9** (chỉ `drv_uart` chưa cần cho mục tiêu đứng) |
| Lượt gọi mô hình | **196** — 700.768 token vào, 273.112 ra, **≈ 3,61 USD** |
| Lượt chạy cổng kiểm chứng | **262** |
| Vòng tự sửa đã dùng | **61** |
| Quyết định Human Gate | **46** — G1: 13 duyệt · G2: 8 duyệt · G3: **13 duyệt / 12 từ chối** |
| Mục trong sổ lỗi ảo giác | **51** (31 `tool_failure`, 12 `gate_rejection`, 8 khác) |
| Lệnh CLI | **52**, trong đó **70 điểm gọi** Agent tự dùng được |
| Bài kiểm engine | **103 tệp TC** |
| Trích đoạn datasheet đã duyệt | **12** |
| Lần nạp firmware | **22**, đều có đọc ngược xác minh |
| Nghiệm thu trên bo thật | **5** lượt chẩn đoán hai kênh |
| Firmware ráp được | **6.572 byte flash (20,0%)**, 131 byte SRAM (6,4%) |
| Sổ sai lệch thiết kế | **161 mục** — 72 LỆCH THẬT, 84 BỔ SUNG, 3 DỜI CHỖ |

Tỉ lệ G3 từ chối **12/25 = 48%** là con số đáng chú ý nhất bảng, và nó được bàn
ở §4.

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
| 4 | Cổng quy lỗi về đúng module; lỗi module khác đánh `config_error`, **không mở** vòng vá | 3 | §3.5 |
| 5 | `measurements.jsonl` và kết quả chẩn đoán thành **một lớp prompt** | 4 | §3.7 |
| 6 | SL-160 — tách hiệu chỉnh: trôi con quay đo mỗi lần bật, mốc gia tốc từ hồ sơ | 4 | đang treo |
| 7 | SL-161 — trần lớp `project_rules` chặn 10 lần/buổi trong khi prompt tổng dùng 3.200/8.000 | 4 | đang treo |

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
* **Robot chưa đứng được.** Mọi kết luận về vòng điều khiển vẫn là suy ra từ
  cổng và từ một lần chạy trên bo, chưa phải từ một hệ đã nghiệm thu ở G4.
