**EMBEDDED AIDD AGENT**

**KẾ HOẠCH KIỂM THỬ (TEST PLAN)**

*Bộ tài liệu thiết kế phần mềm · Đề án tốt nghiệp Thạc sĩ Kỹ thuật –
ngành Kỹ thuật Điện tử*

| **Thuộc tính**         | **Giá trị**                                                                              |
|------------------------|------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-STP-04                                                                               |
| **Phiên bản**          | 1.0 (Bản thảo trình thầy hướng dẫn)                                                      |
| **Ngày lập**           | 28/08/2026                                                                               |
| **Người lập**          | Vũ Trí Công                                                                              |
| **Sản phẩm**           | Embedded AIDD Agent — MVP v0.1                                                           |
| **Tài liệu liên quan** | Đề cương đề án; Ma trận Người–AI (Excel); EAA-SRS-01; EAA-SAD-02; EAA-SDD-03; EAA-STP-04 |

| **Phiên bản** | **Ngày**   | **Người sửa** | **Nội dung thay đổi** |
|---------------|------------|---------------|-----------------------|
| **1.0**       | 28/08/2026 | Vũ Trí Công   | Phát hành lần đầu     |

**1. Giới thiệu và phạm vi**

Tài liệu định nghĩa chiến lược, môi trường, danh mục test case và tiêu
chí nghiệm thu cho Embedded AIDD Agent MVP. Phạm vi gồm kiểm thử chính
phần mềm Agent; việc kiểm thử firmware do Agent sinh ra (unit test,
static analysis, kiểm thử vật lý trên robot) là NỘI DUNG NGHIỆP VỤ của
Agent và thuộc quy trình đề án — tại đây chỉ kiểm thử rằng Agent thực
hiện đúng các bước đó.

**2. Chiến lược kiểm thử — bốn mức**

| **Mức**         | **Đối tượng**                                                                         | **Phương pháp**                                               | **Công cụ**                       |
|-----------------|---------------------------------------------------------------------------------------|---------------------------------------------------------------|-----------------------------------|
| **Unit**        | Từng module Python (policy, state, composer, tools adapter)                           | pytest, độ phủ ≥ 80% cho orchestrator/gates/state             | pytest, coverage                  |
| **Integration** | Vòng lặp chuẩn với LLM giả lập (mock trả code định sẵn: đúng, sai, vi phạm ràng buộc) | Kịch bản hóa các nhánh pass/fail/reject mà không tốn API thật | pytest + mock LLMClient           |
| **System**      | Chạy end-to-end với LLM thật trên 2 module demo (driver I2C MPU6050, PID)             | Chạy theo kịch bản người dùng thật, đo KPI                    | CLI + LLM API + toolchain         |
| **Acceptance**  | Toàn bộ quy trình gắn tiêu chí đề cương (mục 2.5)                                     | Đối chiếu ngưỡng Flash/SRAM/ổn định, biên bản nghiệm thu      | kpi_log.csv, avr-size, robot thật |

**3. Môi trường kiểm thử**

Máy phát triển Windows/Linux, Python 3.10+, avr-gcc ≥ 12, cppcheck,
pytest, Git; bộ mô phỏng MIL/SIL đã kiểm chứng bằng nghiệm giải tích
(điều kiện tiên quyết — nếu chưa đạt thì các test liên quan SIL bị
chặn); API key LLM cấu hình qua biến môi trường; robot thật chỉ cần cho
mức Acceptance.

**4. Danh mục test case**

| **Mã**    | **Mục tiêu**                      | **Kịch bản chính**                                                       | **Kết quả mong đợi**                                                               | **Mức**  |
|-----------|-----------------------------------|--------------------------------------------------------------------------|------------------------------------------------------------------------------------|----------|
| **TC-01** | Gate không thể vượt               | Gọi eaa gen khi G1 chưa duyệt; thử mọi tổ hợp lệnh để merge không qua G3 | Bị từ chối trong mọi trường hợp; không tồn tại đường vòng                          | Unit+Int |
| **TC-02** | Reject có hệ quả đúng             | Reject diff tại G3 kèm lý do                                             | Không merge; lý do xuất hiện trong error_ledger.jsonl và trong prompt lần sinh lại | Int      |
| **TC-03** | State bền qua crash               | Kill tiến trình giữa vòng lặp; chạy eaa resume                           | Trạng thái, backlog, retries khôi phục đúng; không hỏng file                       | Unit+Int |
| **TC-04** | Constraints luôn có mặt           | Soi prompt thực gửi đi ở mọi công đoạn                                   | 100% prompt chứa nội dung constraints.yaml hiện hành                               | Int      |
| **TC-05** | Datasheet Injection đúng chunk    | Sinh driver I2C                                                          | Prompt chứa chunk TWBR/TWCR; không chứa chunk Timer1 không liên quan               | Int      |
| **TC-06** | Vòng tự sửa dừng đúng N           | Mock LLM luôn trả code lỗi                                               | Đúng 3 lần thử; thoát mã 3; bàn giao kèm log đủ 3 vòng                             | Int      |
| **TC-07** | Ràng buộc chặn tại static         | Mock LLM trả code chứa delay(), malloc, đệ quy                           | Cổng static analysis fail, mã không tới bước commit                                | Int      |
| **TC-08** | Máy trạng thái tuần tự            | Thử nhảy cóc phase (A→D)                                                 | Bị từ chối; chỉ chuyển khi đủ điều kiện + gate                                     | Unit     |
| **TC-09** | KPI ghi đúng và đủ                | Chạy trọn một module với mock                                            | kpi_log.csv đủ cột, Tdev \> 0, retries khớp thực tế, một dòng mỗi build            | Int      |
| **TC-10** | Error Ledger thành ví dụ phủ định | Thêm lỗi hallucinated_register rồi sinh lại module                       | Prompt lần sau chứa lỗi này trong phần ví dụ cần tránh                             | Int      |
| **TC-11** | Hoán đổi model                    | Đổi provider trong cấu hình, chạy lại TC-09                              | Hành vi Orchestrator/gate không đổi; chỉ trường llm_model trong KPI đổi            | Int      |
| **TC-12** | SIL là cổng chặn thật             | Mock code biên dịch được nhưng robot ảo ngã                              | Không commit; báo cáo nêu rõ fail tại cổng mô phỏng                                | Int      |
| **TC-13** | Quét tham số MIL                  | eaa sim run --sweep trên dải Kp, Ki, Kd                                  | Xuất bảng kết quả; vùng ổn định được đánh dấu; thời gian chạy hợp lý               | Sys      |
| **TC-14** | Bảo mật API key                   | Chạy toàn bộ luồng, grep key trong log/commit/kpi                        | Không xuất hiện key ở bất kỳ đầu ra nào                                            | Sys      |
| **TC-15** | End-to-end 2 module demo          | Chạy thật driver I2C + PID với LLM thật                                  | Cả hai module qua đủ cổng, merge sau G3; KPI đầy đủ cho báo cáo                    | Sys      |

**5. Tiêu chí nghiệm thu (Acceptance)**

- 100% test case mức Unit/Integration gắn yêu cầu Must đạt; TC-15 đạt
  với LLM thật.

- Firmware sinh ra bởi quy trình thỏa ngưỡng đề cương: Flash \< 50%, RAM
  \< 40%, không tràn stack, dung lượng không vượt 10% so với mã viết tay
  tối ưu.

- Trên robot thật (mức Acceptance, tại G4): giữ cân bằng với dao động
  trong khoảng ±1°, vượt 3 kịch bản của mục 3.3.1 đề cương (khởi động
  tĩnh, kháng nhiễu, hoạt động dài hạn 10–20 phút).

- Nhật ký chứng minh: không gate nào bị vượt tự động; mọi mã merge đều
  truy vết được prompt/model/constraints (NFR-07).

**6. Rủi ro và giảm thiểu**

| **Rủi ro**                                  | **Ảnh hưởng**                          | **Giảm thiểu**                                                                                   |
|---------------------------------------------|----------------------------------------|--------------------------------------------------------------------------------------------------|
| **LLM API đổi hành vi/giới hạn giữa chừng** | Kết quả A/B không tái lập              | Ghim phiên bản model trong cấu hình; lưu prompt hash + phản hồi để tái lập                       |
| **Bộ mô phỏng chưa được kiểm chứng kịp**    | Cổng SIL cho kết quả sai, test bị chặn | Điều kiện tiên quyết mục 3; kế hoạch B: tạm thay cổng SIL bằng unit test mở rộng, ghi rõ hạn chế |
| **Chi phí token cho mức System**            | Vượt ngân sách thực nghiệm             | Mock ở Integration; chỉ 2 module chạy LLM thật; đặt trần token mỗi lần gọi                       |
| **Khác biệt môi trường Windows/Linux**      | Test pass một nơi, fail nơi khác       | CI chạy cả hai; tránh lệnh đặc thù hệ điều hành trong adapter                                    |
