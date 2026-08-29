**EMBEDDED AIDD AGENT**

**ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)**

*Bộ tài liệu thiết kế phần mềm · Đề án tốt nghiệp Thạc sĩ Kỹ thuật –
ngành Kỹ thuật Điện tử*

| **Thuộc tính**         | **Giá trị**                                                                              |
|------------------------|------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-SRS-01                                                                               |
| **Phiên bản**          | 1.0 (Bản thảo trình thầy hướng dẫn)                                                      |
| **Ngày lập**           | 28/08/2026                                                                               |
| **Người lập**          | Vũ Trí Công                                                                              |
| **Sản phẩm**           | Embedded AIDD Agent — MVP v0.1                                                           |
| **Tài liệu liên quan** | Đề cương đề án; Ma trận Người–AI (Excel); EAA-SRS-01; EAA-SAD-02; EAA-SDD-03; EAA-STP-04 |

| **Phiên bản** | **Ngày**   | **Người sửa** | **Nội dung thay đổi** |
|---------------|------------|---------------|-----------------------|
| **1.0**       | 28/08/2026 | Vũ Trí Công   | Phát hành lần đầu     |

**1. Giới thiệu**

**1.1. Mục đích tài liệu**

Tài liệu đặc tả yêu cầu cho phần mềm Embedded AIDD Agent (viết tắt: EAA)
— bộ điều phối đóng gói quy trình phát triển phần mềm nhúng có AI hỗ trợ
thành một hệ thống chạy được, với các cổng phê duyệt của con người
(Human Gate) được cưỡng chế bằng phần mềm. Tài liệu là căn cứ để thiết
kế (EAA-SAD-02, EAA-SDD-03), lập trình và nghiệm thu (EAA-STP-04).

**1.2. Phạm vi sản phẩm — Agent lập trình nhúng TỔNG QUÁT**

EAA là Agent lập trình nhúng dùng chung, KHÔNG chuyên dụng cho một mạch
cụ thể nào. Sản phẩm chia ba tầng: (1) ENGINE — toàn bộ logic điều phối,
gate, vòng lặp sinh mã, kỹ thuật AI — tuyệt đối không chứa bất kỳ hằng
số phần cứng nào; (2) PLATFORM PACK — gói nền tảng theo họ MCU
(toolchain adapter, luật static analysis, quy ước thanh ghi, trình nạp,
smoke test), tầng dữ liệu + adapter cắm vào engine; (3) PROJECT — dữ
liệu của từng dự án cụ thể (constraints, hardware profile, datasheet
chunks, backlog). Phiên bản MVP v0.1 giao: engine hoàn chỉnh + Platform
Pack đầu tiên (AVR 8-bit) + một dự án mẫu để kiểm chứng toàn bộ quy
trình: Robot 2 bánh tự cân bằng (ATmega328P, MPU6050, A4988, Nano-OS).
Robot đóng vai trò REFERENCE PROJECT — sản phẩm mẫu chứng minh, không
phải đích chuyên dụng của Agent. Sản phẩm KHÔNG bao gồm: giao diện đồ
họa, làm việc nhóm nhiều người, tự động nạp firmware không cần xác nhận,
và mọi hình thức tự ra quyết định kiến trúc thay con người.

**1.3. Thuật ngữ và viết tắt**

| **Thuật ngữ**          | **Giải nghĩa**                                                                                                                                |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| **AIDD**               | AI-Driven Development — quy trình phát triển trong đó AI thực thi mã nguồn chi tiết, con người giữ vai trò kiến trúc sư và người kiểm định    |
| **Human Gate (G1–G5)** | Điểm dừng bắt buộc trong quy trình, chỉ con người phê duyệt mới được đi tiếp                                                                  |
| **MIL / SIL**          | Model-in-the-Loop / Software-in-the-Loop — mô phỏng thuật toán trên mô hình động lực học / chạy chính mã firmware trên PC qua lớp HAL giả lập |
| **RAG**                | Retrieval-Augmented Generation — tự động truy xuất trích đoạn datasheet đưa vào prompt (Datasheet Injection)                                  |
| **Project State**      | Trạng thái dự án lưu ngoài LLM (JSON/SQLite), giúp hệ thống miễn nhiễm Context Loss                                                           |
| **Error Ledger**       | Nhật ký lỗi ảo giác của AI, dùng làm ví dụ phủ định cho các prompt sau                                                                        |
| **KPI**                | Bộ chỉ số đo lường của đề án: Tdev, tỷ lệ lỗi ban đầu, Flash, SRAM, Loop Latency, Jitter                                                      |

**2. Mô tả tổng quan**

**2.1. Tác nhân (Actors)**

| **Tác nhân**                                        | **Loại**         | **Vai trò đối với EAA**                                                                              |
|-----------------------------------------------------|------------------|------------------------------------------------------------------------------------------------------|
| **Kỹ sư nhúng (Chief Architect / Verifier)**        | Người dùng chính | Khởi tạo dự án, cung cấp ràng buộc và datasheet, phê duyệt tại mọi Gate, nhập số đo vật lý, kết luận |
| **LLM API**                                         | Hệ thống ngoài   | Sinh mã nguồn theo prompt; hoán đổi được giữa các nhà cung cấp (Gemini/GPT/Claude)                   |
| **Toolchain (avr-gcc, avr-size, cppcheck, pytest)** | Hệ thống ngoài   | Thực thi các cổng kiểm chứng tự động; EAA gọi qua subprocess                                         |
| **Robot tự cân bằng**                               | Thực thể vật lý  | KHÔNG nối trực tiếp với EAA; mọi tương tác đi qua kỹ sư (nạp firmware, đo đạc, nhập kết quả)         |

**2.2. Giả định và phụ thuộc**

- Kỹ sư có khả năng đọc hiểu datasheet — chất lượng trích đoạn nạp vào
  RAG quyết định chất lượng mã sinh ra (hạn chế 3.4.3 của đề cương).

- LLM API khả dụng qua Internet; toolchain AVR và Python 3.10+ đã cài
  trên máy kỹ sư.

- Bộ mô phỏng MIL/SIL (sản phẩm của công đoạn C1, C2) đã được kiểm chứng
  bằng nghiệm giải tích trước khi dùng làm cổng kiểm chứng.

**3. Use case**

<img
src="handoff/docs/md/media_EAA-SRS-01_Dac_ta_yeu_cau/media/6cdd4d26423d36bac95bc792e01ee0e28804f261.png"
style="width:6.45833in;height:4.66667in" />

***Hình 1. Sơ đồ use case của Embedded AIDD Agent (MVP)***

| **Mã**   | **Tên use case**                          | **Tác nhân**        | **Mô tả ngắn**                                                            |
|----------|-------------------------------------------|---------------------|---------------------------------------------------------------------------|
| **UC01** | Khởi tạo dự án                            | Kỹ sư               | Nạp constraints.yaml, Hardware Profile; tạo Project State                 |
| **UC02** | Quản lý backlog module                    | Kỹ sư               | Khai báo danh sách module (driver, kernel, PID...) và thứ tự ưu tiên      |
| **UC03** | Duyệt trích đoạn datasheet (G2)           | Kỹ sư               | Duyệt các chunk datasheet trước khi vào Datasheet Store                   |
| **UC04** | Sinh mã module (vòng lặp chuẩn)           | Kỹ sư, LLM          | Chu trình 13 bước: prompt → sinh mã → kiểm chứng → tự sửa ≤ N → chờ duyệt |
| **UC05** | Phê duyệt / từ chối diff (G3)             | Kỹ sư               | Review diff đã qua kiểm chứng; reject kèm lý do → Error Ledger            |
| **UC06** | Chạy mô phỏng MIL/SIL                     | Kỹ sư, Toolchain    | Kiểm chứng thuật toán và firmware trên robot ảo                           |
| **UC07** | Nhập số đo vật lý, nhận gợi ý tuning (G4) | Kỹ sư, LLM          | Nhập latency/jitter/triệu chứng; nhận phân tích và gợi ý Kp, Ki, Kd       |
| **UC08** | Ghi nhận lỗi ảo giác                      | Kỹ sư               | Thêm lỗi mới vào Error Ledger (thanh ghi bịa, sai prescaler...)           |
| **UC09** | Xuất báo cáo KPI                          | Kỹ sư               | Xuất CSV/bảng phục vụ so sánh A/B của Chương 3                            |
| **UC10** | Khôi phục phiên làm việc                  | Kỹ sư               | Resume từ Project State sau khi tắt máy/crash                             |
| **UC11** | Tự kiểm chứng mã nguồn                    | Toolchain (include) | Chuỗi compile → size → static → unit → SIL, được UC04/UC06 gọi            |

**3.1. Đặc tả chi tiết UC04 — Sinh mã module**

| **Mục**                                  | **Nội dung**                                                                                                                                                                      |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Tiền điều kiện**                       | Dự án đã khởi tạo (UC01); backlog đã duyệt tại G1; datasheet liên quan đã duyệt tại G2                                                                                            |
| **Luồng chính**                          | \(1\) Kỹ sư chọn module → (2) EAA tra Policy Engine → (3) ghép prompt từ Knowledge Base → (4) gọi LLM → (5) chạy chuỗi kiểm chứng UC11 → (6) pass: tạo commit + diff, chuyển UC05 |
| **Luồng thay thế A — kiểm chứng fail**   | Báo lỗi trả về LLM tự sửa, lặp tối đa N = 3 lần; quá N: dừng, bàn giao kỹ sư kèm toàn bộ log                                                                                      |
| **Luồng thay thế B — kỹ sư reject diff** | Lý do reject ghi vào Error Ledger; module quay về bước (3) với prompt bổ sung lý do                                                                                               |
| **Hậu điều kiện**                        | Mã nguồn được merge (hoặc bàn giao xử lý tay); KPI của chu trình đã ghi                                                                                                           |

**4. Yêu cầu chức năng (MoSCoW)**

| **Mã**         | **Yêu cầu**                                                                                                                                                                                          | **Ưu tiên** |
|----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| **FR-ORC-01**  | Máy trạng thái 6 giai đoạn A→F; chỉ chuyển trạng thái khi thỏa điều kiện kiểm chứng VÀ phê duyệt gate (nếu có)                                                                                       | Must        |
| **FR-ORC-02**  | Lưu và khôi phục Project State qua các phiên làm việc; mọi lần gọi LLM đều stateless                                                                                                                 | Must        |
| **FR-GATE-01** | 5 Human Gate G1–G5 không thể bị bỏ qua bằng bất kỳ lệnh nào của phần mềm (chỉ con người xác nhận)                                                                                                    | Must        |
| **FR-KB-01**   | Nạp Hard Constraints Spec vào system prompt của MỌI lần gọi LLM                                                                                                                                      | Must        |
| **FR-KB-02**   | Datasheet Injection tự động: truy xuất chunk theo ngoại vi/thanh ghi liên quan tới module đang sinh                                                                                                  | Must        |
| **FR-KB-03**   | Error Ledger: ghi lỗi ảo giác và tự đưa vào prompt như ví dụ phủ định                                                                                                                                | Should      |
| **FR-GEN-01**  | Vòng lặp sinh mã chuẩn 13 bước với giới hạn tự sửa N cấu hình được (mặc định 3)                                                                                                                      | Must        |
| **FR-VER-01**  | Chuỗi kiểm chứng bắt buộc: compile → avr-size (Flash \< 50%, RAM \< 40%) → static analysis → unit test → SIL                                                                                         | Must        |
| **FR-VER-02**  | Mã vi phạm ràng buộc (delay(), malloc, đệ quy, floating-point ở vòng điều khiển) bị chặn tại static analysis                                                                                         | Must        |
| **FR-LLM-01**  | Giao diện LLM hoán đổi được giữa các nhà cung cấp, không đổi hành vi Orchestrator                                                                                                                    | Should      |
| **FR-KPI-01**  | Tự ghi Tdev, số vòng tự sửa, lỗi build lần đầu, Flash/SRAM mỗi bản build; xuất CSV                                                                                                                   | Must        |
| **FR-TUN-01**  | Nhận số đo vật lý kỹ sư nhập tại G4, phân tích telemetry và gợi ý hướng tinh chỉnh tham số                                                                                                           | Should      |
| **FR-SIM-01**  | Tích hợp bộ mô phỏng MIL/SIL tự viết như một cổng kiểm chứng và như công cụ quét tham số                                                                                                             | Should      |
| **FR-CLI-01**  | Bộ lệnh CLI đầy đủ cho mọi use case (init, plan, gen, gate, sim, tune, report, resume)                                                                                                               | Must        |
| **FR-PLT-01**  | Engine không chứa bất kỳ tham chiếu phần cứng cụ thể nào (tên MCU, thanh ghi, linh kiện) — mọi đặc thù nằm trong Platform Pack và Project; có test tự động quét vi phạm                              | Must        |
| **FR-PLT-02**  | Platform Pack đóng gói trọn đặc thù một họ MCU: toolchain adapter (compile/size/flash), luật static analysis, quy ước thanh ghi, mẫu prompt nền tảng, smoke test; cắm vào engine qua interface chuẩn | Must        |
| **FR-PLT-03**  | Một cài đặt quản lý nhiều dự án song song (eaa new/switch); Knowledge Base, state, KPI, phẩm xuất tách biệt theo từng dự án                                                                          | Should      |

**5. Yêu cầu phi chức năng**

| **Mã**     | **Nhóm**                  | **Yêu cầu**                                                                                                                                                           |
|------------|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **NFR-01** | An toàn quy trình         | Không tồn tại đường thực thi nào cho phép merge mã chưa qua đủ chuỗi kiểm chứng và gate tương ứng                                                                     |
| **NFR-02** | Tin cậy                   | Project State bền vững qua crash (ghi nguyên tử — atomic write); resume không mất dữ liệu                                                                             |
| **NFR-03** | Hiệu năng                 | Một vòng kiểm chứng đầy đủ (không tính thời gian LLM) ≤ 2 phút trên máy phát triển thông thường                                                                       |
| **NFR-04** | Di động                   | Chạy trên Windows/Linux; chỉ phụ thuộc Python 3.10+, toolchain AVR và Git                                                                                             |
| **NFR-05** | Mở rộng (định vị cốt lõi) | Là agent nhúng tổng quát: thêm họ MCU mới (STM32, RISC-V...) = thêm một Platform Pack (dữ liệu + adapter), KHÔNG sửa một dòng engine; robot chỉ là dự án mẫu đầu tiên |
| **NFR-06** | Bảo mật                   | API key lưu qua biến môi trường; không ghi key và không gửi datasheet ngoài phạm vi cần thiết vào log                                                                 |
| **NFR-07** | Truy vết                  | Mọi mã nguồn sinh ra truy vết được: prompt nào, model nào, phiên bản constraints nào (ghi trong commit message)                                                       |

**6. Tiêu chí nghiệm thu tổng quát**

Sản phẩm MVP được nghiệm thu khi: (1) chạy trọn vòng lặp chuẩn cho 2
module đại diện (driver I2C MPU6050 và PID) với đầy đủ cổng kiểm chứng;
(2) toàn bộ test case Must trong EAA-STP-04 đạt; (3) firmware do quy
trình sinh ra thỏa các ngưỡng của đề cương: Flash \< 50%, RAM \< 40%,
không tràn stack, và không vượt quá 10% dung lượng so với mã viết tay
tối ưu; (4) chứng minh được bằng nhật ký rằng không gate nào bị vượt tự
động trong toàn bộ quá trình.
