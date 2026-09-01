---
id: logic_pid
description: Luật thiết kế bộ điều khiển PID cho robot cân bằng — số nguyên fixed-point, chống windup, chống xung đạo hàm
---
Bộ điều khiển tham chiếu của dự án nằm ở `sim/controller.py` (công đoạn D4, chạy
Model-in-the-Loop). Bản C số nguyên phải giữ ĐÚNG cấu trúc điều khiển ấy — chọn
sai cấu trúc thì không bộ tham số nào cứu được.

### Số học fixed-point, không phải hệ số nguyên

Hệ số của bộ điều khiển tham chiếu là số thực: `kp = 38.0`, `ki = 90.0`,
`kd = 3.4`. Một `int` không biểu diễn được `3.4`, và làm tròn xuống `3` là đổi
hệ số 12% — đủ để đổi hẳn đáp ứng của hệ.

Vì vậy hệ số được lưu ở dạng **dấu phẩy tĩnh (fixed-point)**: mỗi hệ số là số
nguyên đã nhân sẵn với một hệ số tỉ lệ lũy thừa hai (ví dụ `Q8`, tỉ lệ 256), và
mọi tích `hệ_số × sai_số` phải **dịch phải trả lại tỉ lệ ấy** trước khi cộng vào
đầu ra. Khai hệ số tỉ lệ thành một hằng số có tên, đừng rải số 256 khắp mã.

Nhân trước, dịch sau, và tính trung gian ở bề rộng lớn hơn — làm ngược lại thì
mất hết phần lẻ đúng ở chỗ nó quan trọng nhất, là lúc sai số còn nhỏ.

### Đạo hàm lấy theo SỐ ĐO, không theo sai số

Nguyên văn ràng buộc của dự án:

> **Derivative kick** — đạo hàm lấy theo SỐ ĐO chứ không theo sai số; đổi điểm
> đặt sẽ tạo một xung đạo hàm vô nghĩa nếu lấy theo sai số.

Nghĩa là `d = -kd * (số_đo - số_đo_trước)`, **không phải**
`kd * (sai_số - sai_số_trước)`. Dấu trừ là hệ quả của việc đổi biến, không phải
một lựa chọn. Trạng thái nhớ lại giữa hai lượt gọi là **số đo trước**, không
phải sai số trước.

Ở lượt gọi ĐẦU TIÊN chưa có số đo trước; lấy hiệu với 0 sẽ sinh đúng cái xung ta
đang tránh. Lượt đầu phải cho thành phần đạo hàm bằng 0.

### Tích phân ngừng cộng dồn khi đầu ra đã bão hòa

Nguyên văn:

> **Integral windup** — khi lệnh đã bão hòa, thành phần tích phân ngừng cộng
> dồn, nếu không nó sẽ tích một khoản "nợ" mà hệ không thể trả và gây vọt lố.

Đây là điều kiện theo **trạng thái bão hòa của đầu ra**, không chỉ là kẹp tích
phân vào một trần cố định. Trần riêng cho tích phân (`integral_limit` trong bản
tham chiếu) là **hàng rào thứ hai**, không thay được hàng rào thứ nhất.

### Bài kiểm phải chứng minh những điều trên

Bài kiểm sinh kèm phải có ít nhất:

* một phép thử **đổi điểm đặt** trong khi số đo giữ nguyên — thành phần đạo hàm
  phải bằng 0; nếu nó nhảy lên thì mã đang lấy đạo hàm theo sai số;
* một phép thử hệ số **phân số** (ví dụ `kd = 3.4` ở dạng fixed-point) cho ra
  đầu ra khác với khi làm tròn thành `3`;
* một phép thử **giữ sai số lớn kéo dài cho tới khi đầu ra bão hòa** — tích phân
  không được tiếp tục lớn lên.
