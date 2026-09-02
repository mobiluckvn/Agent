---
id: drv_stepper
description: Phát xung bước bằng ngắt Timer2 20 µs, đếm chứ không chia tần — theo đúng mã tham chiếu của bộ kit
---
Hiện thực **đúng** bộ phát xung trong
`sources/.../V3_Balancing_Robot_PID_App.ino`. Đây là mã đã quay được hai bánh
trên chính cái bo này.

### Nhịp: Timer2, CTC, 20 µs

```c
TCCR2A = 0; TCCR2B = 0;
TCCR2B |= (1 << CS21);      // chia trước 8 → 16 MHz/8 = 2 MHz, mỗi nhịp 0,5 µs
OCR2A  = 39;                // (39+1) × 0,5 µs = 20 µs
TCCR2A |= (1 << WGM21);     // CTC
TIMSK2 |= (1 << OCIE2A);
```

### Thuật toán: ĐẾM số lần ngắt, không chia tần số

Mỗi động cơ giữ ba biến: bộ đếm, ngưỡng đang dùng, và giá trị mới do vòng
chính đặt vào. Trong mỗi ngắt, với từng động cơ:

* tăng bộ đếm;
* **đếm > ngưỡng** → đặt lại bộ đếm về 0, nạp ngưỡng mới từ giá trị vòng chính,
  và đặt chân DIR theo DẤU của nó (âm thì đảo dấu ngưỡng lại thành dương);
* **đếm == 1** → kéo chân STEP lên;
* **đếm == 2** → hạ chân STEP xuống (xung chỉ dài 20 µs).

Ngưỡng CÀNG NHỎ thì xung CÀNG DÀY, tức động cơ CÀNG NHANH. Ngưỡng 400 nghĩa là
một xung mỗi 400 lần ngắt (8 ms) — gần như đứng yên. Đây là chỗ dễ hiểu ngược.

### Chân, và chiều

* Phải: `STEP = PD5`, `DIR = PD4`
* Trái: `STEP = PD7`, `DIR = PD6`
* **Không có chân enable** — A4988 bật cứng trên bo. Đừng sinh mã ghi vào một
  chân enable không tồn tại.

Chiều tiến của robot cần HAI mức DIR **khác nhau**, vì hai động cơ lắp đối
xứng gương: trái mức 1, phải mức 0. Đặt cùng mức cho cả hai thì robot quay
tại chỗ thay vì đi tới — lỗi không cổng phần mềm nào bắt được. Con số này đo
bằng mắt tại DS-07, không suy ra.

Ghi chân bằng thao tác trực tiếp trên thanh ghi cổng (`PORTD`), theo
`style.io: direct_port`.

### Trong ngắt

**Cấm số thực.** Chỉ tăng, so sánh, và thao tác bit. Biến chia sẻ với vòng
chính khai `volatile`; giá trị nhiều byte đọc trong khối nguyên tử ở phía vòng
chính, không ở phía ngắt.

Ngắt này chạy 50 000 lần mỗi giây. Mọi thứ trong nó phải xong trong vài µs —
không vòng lặp, không gọi hàm dài, không phép chia.

### Trạng thái DỪNG phải ra được

Tốc độ 0 nghĩa là không phát xung. Đừng biểu diễn nó bằng một ngưỡng bằng
`UINT16_MAX` rồi so `counter > ngưỡng`: bộ đếm `uint16_t` không bao giờ vượt
quá 65535, nên điều kiện ấy vĩnh viễn sai và driver kẹt ở trạng thái dừng —
`stepper_set_speed()` sau đó ghi gì cũng không ai đọc. Đo trên bo 02/09: bánh
khoá cứng từ giây đầu vì `stepper_init()` để target 0.

Dùng một cờ `bool` riêng cho trạng thái dừng, hoặc kiểm `target == 0` mỗi lần
ngắt. Điều kiện thoát khỏi mọi trạng thái phải ĐẠT ĐƯỢC với kiểu dữ liệu đang
dùng.

### Bài kiểm phải chứng minh

* **đặt tốc độ 0 rồi đặt lại khác 0 thì xung phát trở lại** — chạy ngắt vài
  nghìn lần ở tốc độ 0 TRƯỚC, đúng như lúc khởi động;
* ngưỡng nhỏ cho ra nhiều xung hơn ngưỡng lớn trong cùng số lần ngắt;
* dấu âm và dấu dương cho ra hai mức DIR ngược nhau;
* cùng một giá trị điều khiển thì DIR trái và DIR phải ở hai mức KHÁC nhau;
* xung STEP chỉ kéo dài đúng một khoảng ngắt rồi hạ.
