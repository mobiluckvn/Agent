# Đầu vào đã đóng băng của TC-15

Ba tệp/thư mục ở đây là **bản chụp** ràng buộc, hồ sơ phần cứng và trích đoạn
tài liệu tại thời điểm `tests/fixtures/llm_calls/demo_two_modules.jsonl` được
ghi bằng mô hình thật.

## Vì sao chúng không đọc thẳng từ `projects/robot_balance/`

Băm prompt phủ toàn bộ ngữ cảnh, nên đổi một dòng trong ràng buộc của dự án
mẫu là đổi băm và bộ phát lại không tìm thấy bản ghi. Trước bản này, TC-15 đọc
thẳng từ dự án mẫu, và hệ quả là **mọi lần sửa dự án mẫu đều đòi ghi lại
fixture bằng một lượt gọi API thật** — kể cả khi thay đổi ấy chẳng liên quan
gì tới thứ TC-15 đang chứng minh.

Còn một lý do nặng hơn lý do tiện lợi. Phản hồi trong fixture được mô hình sinh
ra **dưới đúng bộ ràng buộc này**. Ghép ràng buộc mới với phản hồi cũ thì băm
có khớp cũng vẫn là một cảnh không có thật: mô hình chưa bao giờ nhìn thấy bộ
ràng buộc ấy. Bằng chứng đã ghi phải đi cùng đầu vào đã sinh ra nó.

`tests/test_tc15_e2e.py` kiểm điều đó bằng một phép so trực tiếp: băm nội dung
của `constraints.yaml` ở đây phải trùng `constraints_version` ghi trong từng
bản ghi. Lệch là đỏ, kèm lời chỉ dẫn.

## Làm mới khi nào, và làm thế nào

Khi muốn TC-15 chạy trên một bộ ràng buộc mới:

1. Chép `constraints.yaml`, `hardware_profile.yaml`, `datasheets/` từ dự án mẫu
   vào đây.
2. Chạy `.venv/bin/python scripts/record_e2e_fixture.py` (cần `EAA_LLM_KEY`,
   có tính phí).

Hai bước, có chủ ý. Đây là một hành động cố ý, không phải một hệ quả phụ của
việc sửa dự án mẫu.
