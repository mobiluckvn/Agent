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


