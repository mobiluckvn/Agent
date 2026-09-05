# V3 — kết quả đo ngược lịch sử dự án bằng bốn bộ dò

Chạy 05/09/2026. Chân lý nền và **dự đoán** chốt trước ở
[`CHAN_LY_NEN_V3.md`](CHAN_LY_NEN_V3.md), commit `f8313d9`, trước bộ chạy.
Bộ chạy: `scripts/do_nguoc_lich_su.py`. Số thô: `docs/V3_ket_qua_do_nguoc.json`.

---

## 1. Con số

### 1.1 Tại 13 điểm người dừng lại từ chối

| Hạng | Số ca | Là những ca nào |
|---|---|---|
| **BẮT ĐƯỢC** — kêu, và trúng khuyết tật ghi nguyên văn | **3** | #3 `sensitivity` · #6 `contract` · #10 `instrument` |
| **TRÚNG MỘT PHẦN** — trúng điểm phụ, trượt điểm chính | **1** | #12 `contract` |
| **KÊU NHƯNG TRẬT LÝ DO** | **7** | #1, #2, #7, #8, #9, #11, #13 |
| **IM ĐÚNG** — không có gì trong tầm để bắt | **2** | #4, #5 |
| **BỎ SÓT** — trong tầm, đủ dữ liệu, mà im | **0** | — |

Dự đoán chốt trước: **4–5 / 13 ≈ 31–38%**.
Thực tế: **3 / 13 = 23%** nếu chấm chặt, **4 / 13 = 31%** nếu tính cả ca trúng
một phần. Nằm ở mép dưới của dải đã dự đoán.

### 1.2 Ba chỗ dự đoán của tôi SAI

Dự đoán nêu **5 cặp (ca, bộ dò)** cụ thể. Đối chiếu:

| Dự đoán | Thực tế |
|---|---|
| #3 `sensitivity` | ✅ đúng |
| #10 `instrument` | ✅ đúng |
| #8 `instrument` bắt "hai hằng số vật lý bị đổi" | ⚠️ `instrument` CÓ kêu, nhưng kêu về *"phép so mới với 500"* — **trật lý do**. Trace 1 im vì hai hằng số ấy nằm trong hàm KHÔNG mang `// ref:` |
| #9 `contract` bắt `imu_start_read()` bị bỏ | ❌ im — vì hàm ấy **đã mất từ trước**, không mất ở lượt này. Xem §2 |
| #4 `contract` (có điều kiện) | ➖ điều kiện không thành: `.h` bản cũ và bản mới khai `button_event_t button_get_event(uint32_t)` **y hệt nhau**. Im là đúng |
| — (không dự đoán) | ✅ **#6 `contract`** bắt được: *"imu_init() không còn gọi i2c_init()"*, khớp **nguyên văn** lý do từ chối |

Hai đúng, hai sai, một điều kiện không thành, một bắt được ngoài dự đoán.

### 1.3 `regcheck` — 0/13, đúng như đã chốt trước

Dự án chưa bao giờ khai `regmap`, nên cổng trả ĐẠT và im ở cả 13 ca. Con số 0
ấy nói rằng **cổng ra đời sau dữ liệu**, không nói rằng cổng vô dụng. Nó được
ghi vào `CHAN_LY_NEN_V3.md` **trước** khi chạy, đúng để không ai đọc nhầm theo
cả hai hướng.

---

## 2. Kết quả đáng giá nhất — và nó chỉ lộ ra khi bỏ cách đếm ban đầu

13 điểm từ chối là chỗ **NGƯỜI** dừng lại đọc, không phải chỗ khuyết tật **lọt
vào**. Quét lại **mọi lượt vá** (không chỉ 13 điểm) trả lời được câu mà cách
đếm ban đầu không trả lời được.

`imu_start_read()` biến mất lúc **02/09 01:00:49**, trong một lượt vá của vòng
tự sửa. Người phát hiện ở lần từ chối #9, lúc **01:55:07**.

> **`contract` kêu sớm hơn người 54 phút.**

Ở #9 thì `contract` im — đúng, vì so hai bản liền kề thì hàm ấy đã mất từ
trước. Dự đoán của tôi gán nó **sai chỗ**; nhưng khẳng định nền ("`contract`
bắt được hạng lỗi này") thì **đúng**, và đúng kèm một con số về độ sớm.

Đây là lý do §1.1 phải có hạng *BỎ SÓT = 0*: không ca nào bộ dò có đủ dữ liệu,
khuyết tật nằm trong tầm nó tự khai, mà nó im.

---

## 3. Cái giá: 67 lần kêu trên toàn bộ lịch sử

Quét mọi lượt vá cho **67 lượt có bộ dò kêu**. Tại 13 điểm từ chối, **7/13 là
kêu trật lý do**.

Chân lý nền đã viết trước: *"Một bộ dò hay báo nhầm sớm muộn cũng bị tắt đi, và
lúc ấy nó không bảo vệ được gì."* Con số 7/13 là con số phải mang ra bàn, không
phải con số để giấu dưới ba ca bắt đúng.

Ba nguồn nhiễu tách được:

1. **Chữ ký còn đang chảy.** Ở những lượt đầu của một module, chữ ký đổi mỗi
   vòng là chuyện bình thường của thiết kế đang hình thành. `contract` kêu ở
   #1, #2, #3, #13 đều thuộc loại này. Bộ dò làm đúng việc nó khai; **cái sai
   là đem nó chạy ở giai đoạn chưa có hợp đồng để phá**.
2. **`instrument` trace 2 quá rộng.** *"Phép so mới với 25"*, *"với 150, 300"* —
   một số nhỏ trùng nhau giữa mã và bài kiểm là chuyện thường, không phải dấu
   vết. Bốn trong sáu lần `instrument` kêu là loại này.
3. **`instrument` trace 1 đếm nhầm hằng số DI CHUYỂN thành hằng số BỊ ĐỔI.**
   *"`imu_update()` mất hằng số 0x19, 0x75, 25"* — chúng được chuyển sang hàm
   khác chứ không mất. Phép so theo từng hàm, nên tái cấu trúc đọc thành xoá.

---

## 4. Một chỗ lệch trong `contract.py` — và trách nhiệm thuộc về ai

Ở lượt vá `app_balance` lúc 02/09 10:34:00, `contract` báo:

```
MẤT   else if(seq_time == 200) buzzer_beep_async(now_ms, 50);
```

Đó không phải khai báo hàm. Nhưng phải nói cho đúng trách nhiệm: `khai_bao_ham`
tự khai trong docstring là **"đọc từ một tệp header"**, còn bộ chạy V3 cho nó
ăn cả tệp `.c`. **Lỗi dùng sai là của bộ chạy, không phải của bộ dò.**

Dù vậy nó phơi ra một chỗ lệch có thật, và chỗ lệch ấy đáng sửa: trong cùng một
module có **HAI danh sách từ khoá cho cùng một mục đích**. `_KHONG_PHAI_LOI_GOI`
(dùng khi đọc lời gọi) có `else`, `do`, `case`, `goto`; còn danh sách viết thẳng
trong `khai_bao_ham` chỉ có `typedef`, `return`, `if`, `while`, `for`, `switch`.
Hai danh sách cùng một mục đích là hai danh sách **sẽ** lệch nhau — và lúc lệch,
một câu lệnh thành một khai báo, rồi ở bản sau nó thành *"hàm bị mất"* bịa ra
từ đầu tới cuối.

Đã sửa: một bộ dùng chung cho cả hai phép. Cảnh báo bịa biến mất (kiểm lại: 0),
49 bài của TC-124 và TC-127 vẫn xanh.

Chỗ lệch này không lộ ra trong 33 bài của TC-127, vì bài kiểm ở đó dùng mã C
sạch và đúng loại tệp. Nó chỉ lộ khi chạy trên **mã thật của lịch sử thật**, kể
cả khi dùng sai — và đó là lý do V3 đáng làm dù nó không tốn một lượt gọi mô
hình nào.

## 5. Điều V3 KHÔNG chứng minh

* **Không** chứng minh bốn bộ dò làm quy trình tốt hơn. Nó chỉ nói: nếu chúng
  có mặt hôm ấy, ba lần chúng đã kêu đúng, một lần sớm hơn người 54 phút, và
  bảy lần chúng kêu trật.
* **Không** đo được `regcheck`. Bốn cổng của nó chưa từng chạy trên dữ liệu thật.
* **Không** lặp lại được. Tính sạch của phép thử này (bộ dò ra đời sau dữ liệu)
  chỉ có đúng một lần; mọi lượt sinh từ nay trở đi đều diễn ra trong một quy
  trình đã có bốn bộ dò.
* **Không** nói gì về tám lần từ chối vì lỗi thiết kế hoặc vật lý — sai trục
  cảm biến, sai hệ số tích phân, sai thứ tự vùng chết, một lời gọi thừa giết
  hẳn chức năng. Không bộ dò tĩnh nào bắt được chúng, và điều ấy đã được chốt
  trước khi chạy. **Gate người duyệt không thay thế được.**
