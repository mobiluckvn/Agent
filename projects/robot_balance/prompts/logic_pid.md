---
id: logic_pid
description: Luật thiết kế PID cho robot cân bằng — fixed-point, đạo hàm theo số đo, chống windup, đổi hệ số không giật
---
Bản tham chiếu: `sim/controller.py` (công đoạn D4). Bản C số nguyên phải giữ
ĐÚNG cấu trúc điều khiển ấy — sai cấu trúc thì không bộ tham số nào cứu được.

### 1. Fixed-point, không phải hệ số nguyên

Hệ số tham chiếu là số thực: `kp = 38.0`, `ki = 90.0`, `kd = 3.4`. Làm tròn
`3.4` → `3` là đổi hệ số 12%, đủ đổi hẳn đáp ứng.

* Mỗi hệ số là số nguyên đã nhân sẵn một tỉ lệ lũy thừa hai (ví dụ Q8 = 256).
* Tỉ lệ là một hằng số CÓ TÊN, không rải số 256 khắp mã.
* Nhân trước, chia sau, trung gian ở bề rộng lớn hơn. Ngược lại thì mất phần
  lẻ đúng lúc sai số còn nhỏ.

### 2. Đạo hàm lấy theo SỐ ĐO

Nguyên văn ràng buộc dự án:

> **Derivative kick** — đạo hàm lấy theo SỐ ĐO chứ không theo sai số.

* `d = -kd * (số_đo - số_đo_trước)`. KHÔNG phải `kd * (sai_số - sai_số_trước)`.
* Dấu trừ là hệ quả của đổi biến, không phải lựa chọn.
* Trạng thái nhớ giữa hai lượt là **số đo trước**, không phải sai số trước.
* Lượt gọi ĐẦU TIÊN: đạo hàm bằng 0. Lấy hiệu với 0 sinh đúng cái xung đang tránh.

### 3. Tích phân ngừng cộng dồn khi đầu ra bão hòa

Nguyên văn:

> **Integral windup** — khi lệnh đã bão hòa, thành phần tích phân ngừng cộng
> dồn, nếu không nó tích một khoản "nợ" hệ không trả được và gây vọt lố.

Cần **CẢ HAI** hàng rào, không phải chọn một:

* (a) ngừng cộng dồn khi đầu ra bão hòa cùng chiều sai số;
* (b) trần riêng cho tích phân — bản tham chiếu đặt `integral_limit = 1.5` SI.

(a) một mình bị **nhiễu đo đánh bại**: thành phần đạo hàm nhiễu kéo đầu ra dự
kiến xuống dưới trần, nên tích phân vẫn cộng. Đo trên chính bản C: nhiễu ±10
mrad, tích phân lên 4896 trong khi trần đầu ra là 3000 — một khoản nợ lớn hơn
cả dải lệnh.

### 4. Chu kỳ cố định — phải ghi cách quy đổi hệ số

`dt` cố định 10 ms, không truyền vào hàm, nên gộp sẵn trong `ki` và `kd`. Hệ số
do đó KHÔNG cùng đơn vị với bản mô phỏng.

Ghi ngay trong tệp tiêu đề: cách quy đổi từ hệ số SI của `sim/controller.py`
(`kp = 38.0`; `ki = 90.0` mỗi giây; `kd = 3.4` giây; góc bằng radian) ra số
nguyên Q8, kèm ĐƠN VỊ của điểm đặt, số đo, **giá trị trả về, `out_min` và
`out_max`**. Chọn đo góc bằng mrad thì đầu ra lệch đúng 1000 lần so với lệnh
SI — nói ra con số ấy, đừng để người đọc tự suy.

### 5. Đổi hệ số khi đang chạy không được làm giật

Ở G4 người chỉnh tham số **trên robot đang cân bằng**. Hàm đặt hệ số KHÔNG được
xóa tích phân, xóa số đo trước, hay đặt lại cờ "lượt đầu" — ba thứ ấy đang giữ
robot đứng. Khởi tạo là việc RIÊNG, tách khỏi đặt hệ số.

### 6. Bài kiểm phải chứng minh từng điều trên

* đổi điểm đặt, số đo giữ nguyên → đạo hàm bằng 0;
* `kd = 3.4` dạng Q8 cho đầu ra khác `kd = 3`;
* giữ sai số lớn tới khi đầu ra bão hòa → tích phân không lớn thêm;
* **số đo nhiễu quanh một lệch tĩnh, chạy dài** → tích phân không vượt trần
  riêng của nó (đây là bài bắt được chỗ thiếu hàng rào (b));
* đổi hệ số giữa chừng → tích phân và số đo trước còn nguyên.
