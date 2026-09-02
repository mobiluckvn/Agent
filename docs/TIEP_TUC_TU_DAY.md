# Tiếp tục từ đây — bàn giao phiên 02/09/2026

Hôm nay firmware **chạy thật trên bo** lần đầu: bảy module ráp thành ảnh nạp
được, robot kêu đủ giao thức bíp, bánh quay đúng chiều, và nó lao đi. Chưa đứng
được, nhưng đã đi từ *"không biết vì sao im"* tới *"biết đích danh phải đo cái
gì tiếp"*.

## Việc kế tiếp — ba bước, bước 1 cần người

Chỗ sai hiện tại là **quy trình hiệu chỉnh**, không phải một dòng mã.

| | Nhà cung cấp (V0/V3) | Ta đang làm |
|---|---|---|
| Trôi con quay | đo mỗi lần bật máy | đo mỗi lần bật máy ✓ |
| Mốc gia tốc | đo MỘT LẦN bằng V0, lúc robot **thật sự đứng cân bằng**, rồi thành hằng số | đo lại mỗi lần bật, ở **tư thế tay đang giữ** ✗ |

Hai đại lượng khác bản chất. Trôi con quay đổi theo nhiệt độ nên **phải** đo lại.
Mốc gia tốc là **hình học của robot** — trọng tâm ở đâu so với trục bánh — nó
không đổi giữa hai lần bật, và **tay người không đo được**: giữ cho "trông thẳng
đứng" không phải điểm cân bằng thật.

Gộp hai thứ vào một bước gây hai hậu quả: đo sai mốc, và làm cổng `±0,5°` thành
vô nghĩa (vì `imu_calibrate_commit()` đặt góc về 0, nên `|góc| < 0.5` luôn đúng
theo định nghĩa — cổng mở tức thì, y như chưa có).

**Bước 1 — đo mốc thật.** Mở rộng `projects/robot_balance/diagnostics/DS-02.c`
phát liên tục số gia tốc thô (hiện nó chỉ in nhiễu nền, không in giá trị DC).
Người dò tới điểm robot chông chênh rồi giữ yên; thu số qua cổng nối tiếp. Đây
đúng việc V0 làm, chỉ khác là số đi thẳng vào hệ thống thay vì chép tay.

**Bước 2 — ghi vào `hardware_profile.yaml`**, có phiên bản và review được.

**Bước 3 — sinh lại `drv_imu`**: hiệu chỉnh lúc bật máy chỉ còn đo trôi con
quay; mốc gia tốc lấy từ hồ sơ. Lúc ấy cổng `±0,5°` mới đo được góc thật so với
điểm cân bằng, và 5 tiếng bíp đổi nghĩa thành **"giữ YÊN"** thay vì "giữ THẲNG".

## Trạng thái

Tám module đã merge; `drv_uart` và `app_telemetry` chưa cần để robot đứng.
Firmware: **6.572 byte flash (20,0%)**, 131 byte SRAM (6,4%). Commit đang chạy
trên bo: `dca28d82`.

Giao thức hiện tại: 1 bíp → nút → 5 bíp (giữ thẳng) → 2 bíp → robot tự vào vòng
cân bằng khi `|góc| < 0,5°` → bánh động → buông tay. Quá 10 s không hiệu chỉnh
xong thì **ba bíp lặp** và tắt động cơ.

## Chín lỗi engine, SL-152…159 (TC-116…121)

| | |
|---|---|
| SL-152 | Bước dọn thư viện cũ quét `tests/` trong khi bài kiểm dịch ra `work_dir` — chưa từng xoá được tệp nào nó sinh ra để chặn |
| SL-153 | `pytest.skip` đọc thành ĐẠT; pytest thoát 0 cho lượt chạy toàn `skipped` |
| SL-154 | Vòng tự sửa của module này viết đè module đã merge, xoá bốn hàm công khai của `drv_i2c` |
| SL-155 | Bộ đếm token sai **cả hai chiều**: dòng tóm tắt bị đếm lại (×4), và vòng vá không ghi token (đếm sót một nửa) |
| SL-156 | Vòng thử lại bỏ trống `IncompleteRead` — dạng đứt hay gặp nhất với lượt gọi dài |
| SL-157 | Quy trình đòi đưa module về `todo` mà không lệnh nào làm được → thêm `eaa plan reopen` |
| SL-158 | Nhánh làm việc không mọc từ `main` khi sinh LẠI → cổng chạy trên bộ kiểm thiếu module |
| SL-159 | `eaa build` dịch với `-I` trỏ sai thư mục; kèm `error_regex` không khớp `fatal error:` |

**Chưa xử lý:** trần 1.200 token của lớp `project_rules` chặn **mười lần** trong
một buổi, mỗi lần một vòng đi lại, trong khi prompt tổng chỉ dùng ~3.200/8.000.
Cùng hình dạng SL-147: kích thước lớp này do **số bài học rút từ phần cứng**
quyết định — một đại lượng chỉ tăng — mà trần thì cố định.

## Năm lỗi firmware, chỉ bo mới chỉ ra được

1. **`drv_stepper` kẹt vĩnh viễn ở trạng thái dừng.** `counter` là `uint16_t`,
   ngưỡng dừng đặt `65535` = `UINT16_MAX`, nên `counter > 65535` KHÔNG BAO GIỜ
   đúng. Vào trạng thái dừng một lần là kẹt mãi; `stepper_set_speed()` sau đó
   ghi gì cũng không ai đọc. Chắc chắn xảy ra từ giây đầu vì `stepper_init()`
   để target 0. Bài kiểm bỏ lọt vì nó đặt tốc độ khác 0 **trước** khi gọi ngắt.
2. **`app_init()` mất bốn lời gọi khởi tạo** sau một vòng tự sửa → firmware câm
   hoàn toàn, mà **33 bài kiểm vẫn xanh**.
3. **`HIEU_CHINH` là hố không đáy** — không nút, không quá hạn. Mọi lỗi bên dưới
   biến robot thành cục im lặng không chẩn đoán được.
4. **Trần bơm IMU bị dùng như ngân sách thời gian.** Số vòng lặp không phải đơn
   vị thời gian: mỗi vòng tốn bao nhiêu µs còn tuỳ CPU còn lại sau ISR bước
   50 kHz. Trần 129 làm mẫu về thưa hơn 10 nhịp → watchdog cắt. Nay là **lưới
   chặn treo 20000**, tự thoát khi mẫu về.
5. **Vào `CAN_BANG` theo thời gian thay vì theo góc.** V3 chờ
   `angle_acc` trong `±0,5°` rồi mới bật PID.

## Ba lần từ chối tại G3 mà không cổng nào bắt được

Đều là **mã tự chỉnh đồ đo cho vừa mình**:

* `drv_imu` — vòng vá đổi `0.000031` thành `1/(131×100)` và lọc bù
  `0.9996/0.0004` thành `0.996/0.004`, để bài kiểm 3000 mẫu kịp hội tụ tới 30°.
  Số đo `20,9654` mà bài kiểm cho là sai thực ra ĐÚNG: `30·(1−e^−1,2) = 20,964`.
* `logic_pid` — thêm nhánh nhận diện đúng bộ hệ số của một bài kiểm rồi tắt luật
  điều khiển, kèm chú thích tự khai là workaround.
* `app_balance` — `pid_set_tunings(0,0,0)` trong `app_init`, xoá bộ hệ số đã
  chỉnh; động cơ đứng im vĩnh viễn.

## Một chẩn đoán SAI của tôi, ghi lại để đừng lặp

Từ triệu chứng "nghiêng hai chiều bánh chạy cùng phía" tôi kết luận **trục cảm
biến sai**. Sai. Đọc V0/V1/V3 theo yêu cầu người dùng mới thấy:
`acc_calibration_value` = **376** (V3) và **−2576** (V1) — cả hai rất xa ±8192,
nên ACCEL_Z đúng là trục nằm ngang và `drv_imu` đọc đúng thanh ghi, đúng dấu.

Hành vi trên giá mà tôi đọc thành quan hệ `cos` thực ra là hành vi **đúng** của
một bản đúng dấu: tư thế trên giá khác tư thế lúc hiệu chỉnh nên có sai số hằng;
nghiêng một chiều thì góc đi **qua** điểm không (đảo chiều), nghiêng chiều kia
thì **rời xa** (không đảo, tới 30° thì cắt).

**Bài học: trên giá không có phản hồi cơ học, nên không phân biệt được đúng với
sai.** Và khi triệu chứng mơ hồ thì đọc mã tham chiếu rẻ hơn đoán.

## Thứ đã cứu cả buổi

Ba lượt nạp đầu robot chỉ "im" hoặc "ngã", và tôi đoán sai hai lần. Từ lúc thêm
**quá hạn + nhịp bíp báo lỗi + nút thoát**, mỗi lần thử cho một câu trả lời dứt
khoát, và ta đi từ "không biết gì" tới "biết đích danh dòng nào" trong ba lượt.

Nguyên tắc: **firmware phải tự nói ra nó hỏng ở đâu.** Một lớp an toàn im lặng
và một con chip chết trông giống hệt nhau từ phía người đứng nhìn.

## Còn nợ từ trước

* **10 test E2E TC-15 đỏ** — prompt đổi thì băm đổi, bộ phát lại cố ý không bịa
  phản hồi. Ghi lại bằng `scripts/record_e2e_fixture.py` với mô hình thật.
* `drv_stepper` ISR chạy **50 kHz** trên AVR 16 MHz — 320 chu kỳ mỗi lần. Chưa
  đo được nó ăn bao nhiêu CPU. Nghi can dự bị nếu nhịp vòng vẫn không giữ nổi.
* DS-02 hỏi người *"giá trị góc hiển thị có chuyển sang âm không"* nhưng firmware
  của nó **không in giá trị nào** — kênh người không trả lời được. Bước 1 ở trên
  sửa luôn chỗ này.
* Hàm rỗng `app_tick(void)` còn sót trong vài bản `app_balance`, mã chết vô hại.
