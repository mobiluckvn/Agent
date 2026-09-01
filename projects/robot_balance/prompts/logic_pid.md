---
id: logic_pid
description: PID theo đúng công thức mã tham chiếu của bộ kit — vòng 4 ms, số thực ngoài ngắt, kẹp ±400, vùng chết ±5
---
Module này hiện thực **đúng** bộ điều khiển trong
`sources/.../V3_Balancing_Robot_PID_App.ino` — mã đã chạy được trên chính cái
bo đang nằm trên bàn. Không sáng tác lại, không "cải tiến".

### Công thức, nguyên văn

```c
pid_error_temp = angle - self_balance_setpoint - pid_setpoint;
if (pid_output > 10 || pid_output < -10)
    pid_error_temp += pid_output * 0.015;          // hàm phanh

pid_i_mem += pid_i_gain * pid_error_temp;
if (pid_i_mem >  400) pid_i_mem =  400;            // kẹp tích phân
if (pid_i_mem < -400) pid_i_mem = -400;

pid_output = pid_p_gain * pid_error_temp
           + pid_i_mem
           + pid_d_gain * (pid_error_temp - pid_last_d_error);
if (pid_output >  400) pid_output =  400;
if (pid_output < -400) pid_output = -400;

pid_last_d_error = pid_error_temp;
if (pid_output < 5 && pid_output > -5) pid_output = 0;   // vùng chết
```

Hệ số mặc định: `kp = 12`, `ki = 0.4`, `kd = 10`. Chu kỳ vòng **4 ms**.

### Số thực, và ranh giới của nó

`constraints.yaml` v2 cho phép số thực **ngoài ngắt**. Module này chạy ở vòng
chính nên dùng `float` thẳng, đúng như mã tham chiếu. Trong ngắt vẫn cấm tuyệt
đối — nhưng module này không có hàm nào chạy trong ngắt.

Không tự ý đổi sang dấu phẩy tĩnh. Bộ ba hệ số trên gắn chặt với công thức
sinh ra chúng; đổi biểu diễn là đổi bài toán, và bộ số ấy không còn đúng nữa.

### Đạo hàm ở đây lấy theo SAI SỐ — và đó là có chủ ý

`sim/controller.py` của dự án nêu **derivative kick** như một lỗi phải tránh,
và bảo lấy đạo hàm theo số đo. Mã tham chiếu lấy theo sai số. Ta theo mã tham
chiếu, vì:

* xung đạo hàm chỉ xuất hiện khi **điểm đặt nhảy bậc**;
* bài toán là *đứng yên tại chỗ*: `pid_setpoint` luôn bằng 0, còn
  `self_balance_setpoint` dịch ±0,0015 mỗi vòng — tức khoảng 0,4 đơn vị mỗi
  giây, không phải một bậc;
* với điểm đặt gần như không đổi, hai cách chỉ khác nhau về DẤU, và dấu ấy đã
  nằm sẵn trong hệ số của mã tham chiếu.

**Phải xem lại điều này ngay khi thêm lệnh đi tới / lùi / quay**: lúc ấy điểm
đặt nhảy bậc thật, và derivative kick trở thành lỗi thật. Ghi chú ấy để trong
mã, đừng chỉ để trong đầu.

### Điểm cân bằng tự tìm

Khi không có lệnh di chuyển, dịch điểm cân bằng ngược chiều đầu ra:

```c
if (pid_setpoint == 0) {
    if (pid_output < 0) self_balance_setpoint += 0.0015;
    if (pid_output > 0) self_balance_setpoint -= 0.0015;
}
```

Đây là thứ khử lệch tĩnh do gá cảm biến không hoàn toàn thẳng. Bỏ nó thì robot
đứng được vài giây rồi trôi dần về một phía.

### Điều kiện dừng

`|angle| > 30°`, hoặc chưa được lệnh chạy, hoặc pin yếu → `pid_output = 0`,
**xoá `pid_i_mem`**, và không tự chạy lại.

### Bài kiểm phải chứng minh

* kẹp tích phân ở ±400 và kẹp đầu ra ở ±400;
* vùng chết: `|out| < 5` trả về đúng 0;
* xoá trạng thái khi dừng: `pid_i_mem` về 0;
* đổi hệ số giữa chừng KHÔNG xoá `pid_i_mem` và `pid_last_d_error` — ở G4
  người chỉnh tham số trên robot đang cân bằng, mỗi lần chỉnh không được giật;
* điểm cân bằng tự tìm dịch đúng chiều: đầu ra âm kéo dài thì nó tăng.
