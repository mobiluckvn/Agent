**EMBEDDED AIDD AGENT**

**TÀI LIỆU THIẾT KẾ KIẾN TRÚC (SAD)**

*Bộ tài liệu thiết kế phần mềm · Đề án tốt nghiệp Thạc sĩ Kỹ thuật –
ngành Kỹ thuật Điện tử*

| **Thuộc tính**         | **Giá trị**                                                                              |
|------------------------|------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-SAD-02                                                                               |
| **Phiên bản**          | 1.0 (Bản thảo trình thầy hướng dẫn)                                                      |
| **Ngày lập**           | 28/08/2026                                                                               |
| **Người lập**          | Vũ Trí Công                                                                              |
| **Sản phẩm**           | Embedded AIDD Agent — MVP v0.1                                                           |
| **Tài liệu liên quan** | Đề cương đề án; Ma trận Người–AI (Excel); EAA-SRS-01; EAA-SAD-02; EAA-SDD-03; EAA-STP-04 |

| **Phiên bản** | **Ngày**   | **Người sửa** | **Nội dung thay đổi** |
|---------------|------------|---------------|-----------------------|
| **1.0**       | 28/08/2026 | Vũ Trí Công   | Phát hành lần đầu     |

**1. Giới thiệu và nguyên tắc kiến trúc**

Tài liệu mô tả kiến trúc phần mềm Embedded AIDD Agent theo các góc nhìn:
ngữ cảnh, thành phần, hành vi, dữ liệu và triển khai; kèm các quyết định
kiến trúc (ADR) và cơ chế hóa giải ba điểm yếu cố hữu của AI. Kiến trúc
tuân theo ba nguyên tắc đã xác lập trong SRS:

- **NT1 — Con người giữ mọi quyết định kiến trúc và an toàn:** các quyết
  định được mã hóa thành Human Gate G1–G5, cưỡng chế trong Orchestrator
  (FR-GATE-01).

- **NT2 — Không mã nào đến tay người mà chưa qua kiểm chứng máy:** chuỗi
  Tool Layer là đường đi bắt buộc của mọi sản phẩm LLM (FR-VER-01).

- **NT3 — Tri thức tích lũy thay trí nhớ hội thoại:** mọi lần gọi LLM là
  stateless; ngữ cảnh nạp lại từ Knowledge Base + Project State
  (FR-ORC-02).

**2. Góc nhìn ngữ cảnh**

<img
src="handoff/docs/md/media_EAA-SAD-02_Thiet_ke_kien_truc/media/2983eb47084221b4cdd87847f29e8d5b6bd96dde.png"
style="width:6.66667in;height:4.6875in" />

***Hình 1. Sơ đồ khối tổng thể — Agent giữa Con người và Thế giới vật
lý***

Ranh giới hệ thống: EAA chạy trọn trên máy của kỹ sư; giao tiếp ra ngoài
chỉ gồm (a) lời gọi LLM API qua Internet và (b) toolchain cục bộ. Robot
thật nằm ngoài ranh giới: firmware đến robot qua tay kỹ sư, dữ liệu đo
trở về qua kỹ sư nhập tại Gate G4 hoặc file log UART — thiết kế này cố ý
biến con người thành "cảm biến và cơ cấu chấp hành" của Agent, đúng
triết lý đề án.

**3. Góc nhìn thành phần**

| **Thành phần**              | **Trách nhiệm**                                                                           | **Giao tiếp với**                            |
|-----------------------------|-------------------------------------------------------------------------------------------|----------------------------------------------|
| **Orchestrator**            | Máy trạng thái 6 giai đoạn; điều phối vòng lặp chuẩn; quản lý Project State               | Mọi thành phần                               |
| **Policy Engine**           | Bảng phân quyền AUTO/APPROVE/HUMAN dịch từ Ma trận Người–AI                               | Orchestrator (tra cứu trước mỗi chuyển bước) |
| **Knowledge Base**          | 5 kho: Constraints, Datasheet Store (RAG), Prompt Library, Hardware Profile, Error Ledger | Prompt Composer (đọc); Gates (ghi)           |
| **Prompt Composer**         | Ghép prompt: role + constraints + datasheet chunk + mẫu + ví dụ phủ định                  | Knowledge Base, LLM Core                     |
| **LLM Core**                | Gọi mô hình sinh mã qua adapter hoán đổi được; retry/timeout                              | Prompt Composer, Tool Layer                  |
| **Tool Layer**              | Chuỗi cổng kiểm chứng: compile, size, static, unit, MIL/SIL; trả ToolReport               | LLM Core (feedback), Git, KPI Logger         |
| **Human Interface (Gates)** | Điểm phê duyệt G1–G5 trên CLI; nhập số đo vật lý                                          | Kỹ sư, Orchestrator, Error Ledger            |
| **KPI Logger**              | Ghi số liệu định lượng từng chu trình; xuất CSV cho Chương 3                              | Orchestrator, Tool Layer                     |

**4. Góc nhìn hành vi**

**4.1. Máy trạng thái của Orchestrator**

<img
src="handoff/docs/md/media_EAA-SAD-02_Thiet_ke_kien_truc/media/955aaf3d907d2b7e154d7fc174b6f54481b421b2.png"
style="width:6.66667in;height:3.57292in" />

***Hình 2. Máy trạng thái 6 giai đoạn với các Human Gate trên cung
chuyển tiếp***

Hai vòng phản hồi quan trọng: vòng tự sửa nội bộ trạng thái D (Tool
Layer fail → LLM sửa, ≤ N lần) và vòng tinh chỉnh E2→D4 khi kiểm thử vật
lý không đạt — vòng sau luôn đi qua con người vì chỉ con người quan sát
được robot thật.

**4.2. Trình tự vòng lặp sinh mã chuẩn**

<img
src="handoff/docs/md/media_EAA-SAD-02_Thiet_ke_kien_truc/media/82737d210023665817f0b746a052e426ab408743.png"
style="width:6.66667in;height:4.70833in" />

***Hình 3. Sequence diagram vòng lặp chuẩn cho một module***

**5. Góc nhìn dữ liệu (tóm tắt)**

Toàn bộ dữ liệu là file văn bản phẳng đặt trong thư mục dự án, theo dõi
được bằng Git: constraints.yaml (ràng buộc cứng), project_state.json
(trạng thái), datasheets/\*.md (chunk RAG), prompts/\*.md (mẫu),
error_ledger.jsonl (nhật ký lỗi), kpi_log.csv (số liệu). Lược đồ chi
tiết từng file định nghĩa tại EAA-SDD-03, mục 3.

**6. Góc nhìn triển khai**

| **Nút triển khai**                           | **Thành phần chạy trên đó**                                            | **Kết nối**                                                 |
|----------------------------------------------|------------------------------------------------------------------------|-------------------------------------------------------------|
| **Máy phát triển của kỹ sư (Windows/Linux)** | Toàn bộ EAA (Python CLI), toolchain AVR, bộ mô phỏng MIL/SIL, Git repo | Internet (LLM API); USB/UART (đọc log robot)                |
| **Dịch vụ LLM (cloud)**                      | Mô hình sinh mã (Gemini/GPT/Claude)                                    | HTTPS API, xác thực bằng API key                            |
| **Robot tự cân bằng**                        | Firmware Nano-OS do quy trình sinh ra                                  | Không nối với EAA; qua kỹ sư (nạp ISP/bootloader, log UART) |

**7. Quyết định kiến trúc (ADR)**

| **Mã**     | **Quyết định**                                                                                 | **Lý do**                                                                                                                                                          | **Đánh đổi chấp nhận**                                                                 |
|------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| **ADR-01** | CLI thay vì GUI                                                                                | Phạm vi MVP của đề án; kỹ sư là người dùng duy nhất                                                                                                                | Kém trực quan; giảm rào cản bằng lệnh ngắn gọn                                         |
| **ADR-02** | State ngoài LLM, gọi stateless                                                                 | Diệt Context Loss tận gốc; tái lập được mọi lần gọi                                                                                                                | Prompt dài hơn, tốn token hơn hội thoại nối tiếp                                       |
| **ADR-03** | Adapter LLM hoán đổi được                                                                      | Chương 3 cần so sánh nhiều model trên cùng quy trình                                                                                                               | Không dùng được tính năng riêng của từng nhà cung cấp                                  |
| **ADR-04** | Gate cưỡng chế trong Orchestrator, không phải quy ước                                          | Bảo đảm kỹ thuật cho luận điểm vai trò con người                                                                                                                   | Chậm hơn khi làm việc; đây là chủ đích, không phải nhược điểm                          |
| **ADR-05** | Bộ mô phỏng tự viết (MIL/SIL) thay Wokwi                                                       | Chạy hàng loạt tự động, quét tham số, tính đóng góp học thuật                                                                                                      | Mất giả lập mức thanh ghi; bù bằng kiểm thử vật lý E2                                  |
| **ADR-06** | Dữ liệu file phẳng + Git, không database server                                                | Truy vết bằng công cụ chuẩn; đơn giản, bền vững                                                                                                                    | Không phù hợp đa người dùng — ngoài phạm vi MVP                                        |
| **ADR-09** | Kiến trúc 3 tầng Engine – Platform Pack – Project; engine sạch tuyệt đối khỏi phần cứng cụ thể | Sản phẩm là AGENT NHÚNG TỔNG QUÁT; robot tự cân bằng chỉ là reference project kiểm chứng; giá trị chuyển giao của đề án nằm ở engine + quy trình, không ở một mạch | Thêm một tầng trừu tượng (interface PlatformPack) phải thiết kế và test kỹ ngay từ MVP |

**8. Cơ chế hóa giải ba điểm yếu của AI**

| **Điểm yếu**                          | **Thành phần chịu trách nhiệm**             | **Cơ chế**                                                                                             |
|---------------------------------------|---------------------------------------------|--------------------------------------------------------------------------------------------------------|
| **Hallucination (ảo giác phần cứng)** | Datasheet Store + Tool Layer + Error Ledger | Injection tự động ở mọi prompt; compile + đối chiếu thanh ghi chặn mã bịa; lỗi cũ thành ví dụ phủ định |
| **Context Loss (mất ngữ cảnh)**       | Orchestrator + Prompt Composer              | Stateless call + Project State + constraints nạp lại mỗi lần gọi (ADR-02)                              |
| **Physical Blindness (mù vật lý)**    | Bộ mô phỏng MIL/SIL + Gate G4               | Mô phỏng thu hẹp vùng mù; phần còn lại thuộc con người tại G4                                          |
