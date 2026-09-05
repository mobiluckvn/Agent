# Chân lý nền cho V3 — chốt TRƯỚC khi chạy bộ dò

**Chốt ngày 05/09/2026. Không được sửa sau khi thấy kết quả bộ dò.**

Nếu một dòng nào trong tệp này đổi sau khi bộ dò chạy, cả phép đo V3 mất giá
trị. Đây là lý do tệp được commit riêng, trước commit chứa bộ chạy.

---

## 1. Vì sao phải chốt trước

V3 là phép tự chấm: tôi vừa làm bốn bộ dò, vừa chấm chúng. Nếu danh sách "lỗi
đã biết" được chọn **sau** khi thấy bộ dò tìm ra gì, thì con số đi ra chỉ nói
rằng tôi biết chọn ví dụ — nó không nói gì về bộ dò.

Cách chặn duy nhất: chốt trước, bằng một nguồn viết trước, rồi công bố cả phần
dự đoán sai.

## 2. Nguồn của chân lý nền

`projects/robot_balance/gates/decisions.jsonl` — 51 quyết định gate, trong đó
**13 lần TỪ CHỐI tại G3**, mỗi lần kèm **lý do nguyên văn** do người viết tại
thời điểm từ chối (01–03/09/2026).

Bốn bộ dò ra đời **04/09/2026**, tức **sau toàn bộ 13 lần**. Người viết lý do
không thể biết bốn bộ dò sẽ kiểm gì. Đây là phép thử hồi cứu sạch, và tính
sạch ấy là tài sản đắt nhất của V3 — nó không lặp lại được.

> Ghi chú đính chính: sở cứ SC-01 trong `EAA_Viec_phai_lam.xlsx` nói "3 trên
> **12** lần từ chối G3". Đếm lại trong nhật ký được **13**. Con số 12 đúng
> vào lúc `TIEP_TUC_TU_DAY.md` được viết (03/09 sáng); lần thứ 13 xảy ra
> 03/09T03:04 và được ghi sau. Không phải lỗi của ai, nhưng phải nói ra.

## 3. Phạm vi mỗi bộ dò TỰ KHAI

Phân loại dưới đây chỉ được gán khi khuyết tật **rơi đúng vào phạm vi bộ dò tự
khai trong docstring của chính nó** — không nới ra vì muốn con số đẹp hơn.

| Bộ dò | Bắt đúng cái gì | Cần gì để chạy |
|---|---|---|
| `contract.py` | (a) hàm có ở bản trước, MẤT hoặc ĐỔI chữ ký ở bản này; (b) lời gọi LIÊN MODULE có ở bản trước, mất ở bản này | Phải có bản trước |
| `sensitivity.py` | bài kiểm MỚI/ĐỔI mà **không đỏ** trên mã của bản trước — tức nó không chứng minh được gì | Phải có bản trước + chạy được bộ kiểm |
| `instrument.py` | ba dấu vết: (1) hằng số **có `// ref:`** bị đổi giá trị; (2) phép so sánh MỚI khớp hằng số trong bài kiểm; (3) chú thích **tự khai** là workaround | Phải có bản trước |
| `regcheck.py` | ghi thanh ghi: không có trong bản đồ · vượt độ rộng · dịch bit ra ngoài · ghi vào thanh ghi chỉ-đọc · (cảnh báo) trích dẫn chunk không nói về thanh ghi ấy | Phải có **bản đồ thanh ghi** |

### 3.1 Một kết luận đã biết trước, và nó là kết luận NGƯỢC

`regcheck` **không đo được** trên lịch sử này. Dự án `robot_balance` và pack
`avr` chưa bao giờ khai `regmap`; theo luật 1 của kế hoạch, vắng bản đồ thì
cổng trả ĐẠT và im. Vậy `regcheck` sẽ bắt **0/13**, và con số 0 ấy **không nói
gì về chất lượng cổng** — nó nói rằng cổng ra đời sau dữ liệu.

Ghi ra đây trước, để sau khi chạy không ai được đọc số 0 ấy thành "cổng vô
dụng", và cũng không ai được lặng lẽ bỏ nó khỏi bảng cho đẹp.

## 4. Cách ghép cặp (cũ, mới) — và chỗ nó lệch với docstring

`contract.py` nói "bản đã **merge**". Nhưng 13 lần từ chối xảy ra trên mã
**chưa từng merge** — kho firmware chỉ giữ bản đã duyệt. Mã ứng viên nằm trong
`llm_calls.jsonl` (214 lượt gọi, đủ prompt và phản hồi).

Vậy cặp dùng ở đây là **(ứng viên TRƯỚC của cùng module, ứng viên BỊ TỪ CHỐI)**
— đúng vòng lặp mà mô hình thật sự đi qua. Đây là một **lệch có chủ ý** so với
docstring, và nó phải được khai:

* nó **đúng hơn** với câu hỏi V3 hỏi ("nếu bộ dò có mặt hôm ấy thì sao");
* nhưng nó **không phải** phép đo mà `contract.py` mô tả, nên con số V3 không
  được đem đi thay cho một phép đo trên cặp đã-merge.

Ứng viên ĐẦU TIÊN của một module không có bản trước ⇒ ba bộ dò cần bản cũ đều
**không chạy được**, và ô ấy phải ghi *KHÔNG CHẠY ĐƯỢC*, không được ghi *BỎ SÓT*.
Hai thứ khác nhau, và gộp chúng là cách dễ nhất để làm bảng này nói dối.

---

## 5. Mười ba lần từ chối, phân loại TRƯỚC khi chạy

Cột **Bộ dò lẽ ra phải bắt** là **dự đoán**. Nó sẽ bị đối chiếu với kết quả
thật, và phần dự đoán SAI được công bố nguyên vẹn.

| # | Thời điểm | Module | Khuyết tật (rút gọn từ nguyên văn) | Bộ dò lẽ ra phải bắt |
|---|---|---|---|---|
| 1 | 09-01 08:47 | logic_pid | đạo hàm theo sai số thay vì số đo · kp*error nguyên, thiếu tỉ lệ fixed-point · bài kiểm khẳng định đúng cái sai ấy | **KHÔNG** — ứng viên đầu, ba bộ dò cần bản cũ đều không chạy được |
| 2 | 09-01 09:11 | logic_pid | `pid_set_tunings` kiêm khởi tạo · thiếu quy đổi đơn vị SI→Q8 | **KHÔNG** — cả hai là lỗi thiết kế; phần đơn vị thuộc `dimension.py`, ngoài bốn bộ dò |
| 3 | 09-01 09:46 | logic_pid | trần tích phân biến mất · đơn vị đầu ra lệch 1000× · **bài kiểm bọc lệnh dịch trong `try/except: pass`, xanh 4/4 trên mã KHÔNG dịch nổi** · `>>` trên số âm | **SENSITIVITY** |
| 4 | 09-01 13:20 | drv_button | module tự khai thiếu tài liệu thanh ghi PB4 · `button_get_event` trả `bool` thay vì kiểu sự kiện đã duyệt | **CONTRACT** (nếu ứng viên trước khai kiểu khác) |
| 5 | 09-01 14:51 | drv_imu | sai TRỤC gia tốc · `gyro_dt` sai chu kỳ · `ACCEL_CONFIG` 0x00 thay 0x08 · **`imu_init` tự ghi TWSR/TWBR/TWCR/TWDR thay vì gọi `i2c_init()`** | **KHÔNG** — ứng viên đầu. Nếu có bản cũ thì `contract` bắt được điểm cuối |
| 6 | 09-02 00:41 | drv_imu | thiếu giao diện hiệu chỉnh (`imu_calibrate_begin/busy/commit`) · `imu_init` phải gọi `i2c_init()` | **KHÔNG** — "thiếu so với YÊU CẦU MỚI" khác "MẤT so với bản cũ"; `contract` chỉ bắt vế sau |
| 7 | 09-02 00:55 | drv_imu | `imu_calibrate_commit` đặt góc sai (vật lý) · bài kiểm ghi lại đúng cách hiểu sai ấy | **KHÔNG** — bản cũ chưa có hàm hiệu chỉnh nên bài kiểm mới sẽ lỗi thu thập, và `sensitivity` tính lỗi thu thập là *phân biệt được* |
| 8 | 09-02 01:11 | drv_imu | **hai hằng số vật lý bị đổi trong vòng tự sửa cho vừa bài kiểm**: `0.0000763358` thay `0.000031`, `0.996/0.004` thay `0.9996/0.0004` | **INSTRUMENT** (dấu vết 1) |
| 9 | 09-02 02:06 | drv_imu | thiếu tín hiệu nhịp · **`imu_start_read()` đã bị bỏ** | **CONTRACT** (hàm MẤT) |
| 10 | 09-02 02:41 | logic_pid | **nhánh nhận diện đúng bộ hệ số của một bài kiểm rồi tắt luật điều khiển, kèm chú thích tự khai là workaround** · nhánh xoá `self_balance_setpoint` "để bài kiểm không rò rỉ trạng thái" | **INSTRUMENT** (dấu vết 2 và 3) |
| 11 | 09-02 03:03 | app_balance | chữ ký `app_tick(uint32_t)` không ráp được vào lịch `void f(void)` · `timeout = 1000` là số không đo | **KHÔNG** — lệch so với yêu cầu build, không phải ĐỔI so bản cũ |
| 12 | 09-02 03:26 | app_balance | **`app_init()` gọi `pid_set_tunings(0,0,0)` ghi đè hệ số đã chỉnh — động cơ không bao giờ quay** · NGÃ+nút bỏ qua hiệu chỉnh · kiểm ngã nằm trong `if (has_sample)` | **KHÔNG** — lời gọi THÊM có hại, không phải lời gọi MẤT. Đây là ca đáng lo nhất của cả bảng |
| 13 | 09-03 03:04 | logic_pid | thứ tự sai: phép đo điểm cân bằng chạy TRƯỚC vùng chết, tự tạo chu trình giới hạn | **KHÔNG** — lỗi thứ tự logic |

### 5.1 Dự đoán tổng, chốt trước

| Bộ dò | Dự đoán bắt được | Trên tổng |
|---|---|---|
| `contract.py` | #4 (có điều kiện), #9 | 1–2 / 13 |
| `sensitivity.py` | #3 | 1 / 13 |
| `instrument.py` | #8, #10 | 2 / 13 |
| `regcheck.py` | — (không đo được: dự án không khai `regmap`) | 0 / 13 |
| **Cộng** | | **4–5 / 13 ≈ 31–38%** |

**Tám trong mười ba lần từ chối là lỗi thiết kế hoặc vật lý mà không bộ dò tĩnh
nào bắt được** — sai trục cảm biến, sai hệ số tích phân, sai thứ tự vùng chết,
một lời gọi thừa giết hẳn chức năng. Dự đoán ấy được chốt ở đây để sau này
không ai đọc con số 31–38% thành thất bại: nó là **hình dạng thật** của bài
toán, và nó nói rằng gate người duyệt không thay thế được.

## 6. Ba con số phải tách riêng, không được gộp

1. **BẮT ĐƯỢC** — bộ dò kêu, và cái nó kêu trùng khuyết tật đã ghi nguyên văn.
2. **BỎ SÓT** — khuyết tật nằm trong phạm vi bộ dò tự khai, có đủ dữ liệu để
   chạy, mà bộ dò im. **Đây là con số duy nhất tính là thất bại.**
3. **KHÔNG CHẠY ĐƯỢC / NGOÀI TẦM** — thiếu bản cũ, thiếu bản đồ thanh ghi, hoặc
   khuyết tật thuộc hạng bộ dò không hề khai sẽ bắt.

Gộp (2) và (3) là cách dễ nhất để bảng này nói dối, theo cả hai hướng.

## 7. Còn một con số nữa: BÁO NHẦM

Bộ dò kêu ở một lần từ chối mà lý do nguyên văn **không** nhắc tới điều nó kêu.
Không tự động là sai — người duyệt có thể đã bỏ qua vì còn lỗi nặng hơn — nhưng
mỗi ca phải được đọc tay và ghi vào bảng. Một bộ dò hay báo nhầm sớm muộn cũng
bị tắt đi, và lúc ấy nó không bảo vệ được gì.
