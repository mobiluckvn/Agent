**EMBEDDED AIDD AGENT**

**TÀI LIỆU THIẾT KẾ CHI TIẾT (SDD)**

*Bộ tài liệu thiết kế phần mềm · Đề án tốt nghiệp Thạc sĩ Kỹ thuật –
ngành Kỹ thuật Điện tử*

| **Thuộc tính**         | **Giá trị**                                                                              |
|------------------------|------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-SDD-03                                                                               |
| **Phiên bản**          | 1.0 (Bản thảo trình thầy hướng dẫn)                                                      |
| **Ngày lập**           | 28/08/2026                                                                               |
| **Người lập**          | Vũ Trí Công                                                                              |
| **Sản phẩm**           | Embedded AIDD Agent — MVP v0.1                                                           |
| **Tài liệu liên quan** | Đề cương đề án; Ma trận Người–AI (Excel); EAA-SRS-01; EAA-SAD-02; EAA-SDD-03; EAA-STP-04 |

| **Phiên bản** | **Ngày**   | **Người sửa** | **Nội dung thay đổi** |
|---------------|------------|---------------|-----------------------|
| **1.0**       | 28/08/2026 | Vũ Trí Công   | Phát hành lần đầu     |

**1. Giới thiệu**

Tài liệu đặc tả mức hiện thực hóa của Embedded AIDD Agent MVP: cấu trúc
thư mục, lược đồ dữ liệu của từng kho, thiết kế các module Python, bộ
lệnh CLI và các giao diện nội bộ. Đọc cùng EAA-SAD-02; bảng truy vết yêu
cầu ở mục 8 nối về EAA-SRS-01.

**2. Cấu trúc thư mục dự án**

eaa/ \# ENGINE - tong quat, khong chua hang so phan cung nao

├── cli.py \# diem vao, bo lenh CLI

├── orchestrator.py \# may trang thai 6 giai doan

├── state.py \# doc/ghi project_state.json (atomic)

├── policy.py \# bang phan quyen AUTO/APPROVE/HUMAN

├── composer.py \# ghep prompt tu Knowledge Base

├── llm/

│ ├── base.py \# interface LLMClient

│ └── gemini.py\|gpt.py\|claude.py \# cac adapter

├── tools/

│ ├── base.py \# interface ToolGate + ToolReport

│ ├── compile.py \# goi toolchain QUA PlatformPack, khong goi thang
avr-gcc

│ ├── static.py \# nap luat tu PlatformPack

│ ├── unittests.py \# pytest runner

│ └── sim.py \# gate mo phong, binding tu PlatformPack + Project

├── platform.py \# interface PlatformPack: compile/size/flash/rules/sim

├── gates.py \# Human Gate G1..G5 (xac nhan CLI)

├── kpi.py \# ghi kpi_log.csv

└── ledger.py \# error_ledger.jsonl

packs/ \# PLATFORM PACK - dac thu theo ho MCU

└── avr/ \# pack dau tien (MVP)

├── pack.yaml \# khai bao toolchain, lenh, phien ban

├── rules/ \# luat static analysis cho AVR

├── prompts/ \# mau prompt dac thu nen tang

└── smoke/ \# smoke test cua pack

projects/ \# PROJECT - du lieu tung du an

└── robot_balance/ \# DU AN MAU (reference project)

├── constraints.yaml \# rang buoc cung (A1)

├── hardware_profile.yaml \# schematic, pin map (B2)

├── datasheets/\*.md \# chunk RAG da duyet (G2)

├── firmware/ \# ma nguon sinh ra (Git repo)

├── sim/ \# mo hinh vat ly rieng (con lac nguoc)

├── project_state.json \# trang thai (Orchestrator ghi)

├── error_ledger.jsonl \# nhat ky loi ao giac

└── kpi_log.csv \# so lieu cho Chuong 3

**3. Thiết kế dữ liệu**

**3.1. constraints.yaml — Hard Constraints Spec**

mcu: atmega328p

clock_hz: 16000000

limits:

control_loop_ms: 10 \# chu ky dieu khien toi da

motor_response_us: 50 \# dap ung dong co

flash_pct_max: 50

sram_pct_max: 40

forbidden:

\- delay() \# cam ham chan (blocking)

\- malloc/new \# cam cap phat dong

\- recursion \# cam de quy

\- float_in_isr \# cam so thuc trong ngat

style:

arithmetic: integer \# so hoc so nguyen o vong dieu khien

io: direct_port \# thay cho digitalWrite()

**3.2. project_state.json — Project State**

{

"phase": "D", // A..F

"gates": {"G1": "approved", "G2": "approved", "G3": "pending"},

"backlog": \[

{"id": "drv_i2c_mpu6050", "status": "in_verify", "retries": 1},

{"id": "kernel_scheduler", "status": "todo", "retries": 0}

\],

"constraints_version": "sha256:ab12...", // truy vet (NFR-07)

"llm": {"provider": "gemini", "model": "gemini-pro-3"}

}

Ghi bằng cơ chế nguyên tử (ghi file tạm rồi rename) để thỏa NFR-02; mỗi
thay đổi kèm timestamp phục vụ đo Tdev.

**3.3. Datasheet Store — chunk RAG**

Mỗi file datasheets/\<ngoại_vi\>\_\_\<chủ_đề\>.md gồm frontmatter (thiết
bị, thanh ghi liên quan, trang datasheet gốc, trạng thái duyệt G2) và
phần trích đoạn nguyên văn. Composer truy xuất theo trường registers
khớp với module đang sinh — ví dụ sinh driver I2C sẽ nạp các chunk có
TWBR, TWCR, TWSR.

**3.4. error_ledger.jsonl và kpi_log.csv**

| **Tệp**                | **Mỗi dòng/ cột**                                                                                                             | **Ví dụ nội dung**                                                                                   |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| **error_ledger.jsonl** | JSON: {ts, module, category, description, evidence}                                                                           | category=hallucinated_register, description="AI dùng thanh ghi TCCR2C không tồn tại trên ATmega328P" |
| **kpi_log.csv**        | Cột: ts, module, phase, event, tdev_min, retries, first_build_errors, flash_bytes, flash_pct, sram_bytes, sram_pct, llm_model | Một dòng cho mỗi lần build/merge — nguồn số liệu trực tiếp cho Bảng 3.1 của đề cương                 |

**4. Thiết kế module**

| **Module**             | **Trách nhiệm chính**                                        | **Giao diện tiêu biểu**                                     |
|------------------------|--------------------------------------------------------------|-------------------------------------------------------------|
| **orchestrator.py**    | Máy trạng thái; vòng lặp chuẩn 13 bước; điều phối retry ≤ N  | run_module(id); advance_phase(); handle_fail(report)        |
| **state.py**           | Đọc/ghi Project State nguyên tử; khóa file chống ghi đè      | load(); save(state); with_lock()                            |
| **policy.py**          | Tra mức phân quyền theo công đoạn                            | level(task) -\> AUTO\|APPROVE\|HUMAN                        |
| **composer.py**        | Ghép prompt 5 lớp; chọn chunk datasheet theo module          | build(task, state) -\> Prompt                               |
| **llm/base.py**        | Interface chung các adapter; retry, timeout, đếm token       | generate(prompt) -\> CodeArtifact                           |
| **tools/base.py**      | Interface cổng kiểm chứng; chuẩn hóa báo cáo                 | run(artifact) -\> ToolReport{passed, errors\[\], metrics{}} |
| **gates.py**           | Hiện diff/di liệu, chờ xác nhận người; ghi kết quả vào state | request(gate_id, payload) -\> approved\|rejected(reason)    |
| **kpi.py / ledger.py** | Ghi số liệu và nhật ký lỗi (append-only)                     | log_event(...); add_error(...)                              |

**Bất biến quan trọng nhất (invariant):** hàm merge của orchestrator chỉ
gọi được khi ToolReport.passed == True cho toàn bộ chuỗi cổng VÀ
gates.request("G3") trả về approved — không tồn tại nhánh mã nào khác
dẫn tới merge (FR-GATE-01, NFR-01). Đây là điểm phải có unit test riêng
(TC-01, TC-02 trong EAA-STP-04).

**5. Thiết kế CLI**

| **Lệnh**                                    | **Chức năng**                                                          | **Use case** |
|---------------------------------------------|------------------------------------------------------------------------|--------------|
| **eaa init**                                | Khởi tạo dự án: đọc constraints.yaml, hardware_profile.yaml, tạo state | UC01         |
| **eaa plan add\|list\|order**               | Quản lý backlog module                                                 | UC02         |
| **eaa datasheet add \<file\> / approve**    | Nạp và duyệt chunk datasheet (Gate G2)                                 | UC03         |
| **eaa gen \<module_id\>**                   | Chạy vòng lặp sinh mã chuẩn cho module                                 | UC04, UC11   |
| **eaa gate show\|approve\|reject --reason** | Xem diff và phê duyệt tại gate hiện hành                               | UC05, G1–G5  |
| **eaa sim run \[--sweep kp,ki,kd\]**        | Chạy MIL/SIL; quét tham số hàng loạt                                   | UC06         |
| **eaa tune --input measures.yaml**          | Nhập số đo vật lý, nhận phân tích và gợi ý (G4)                        | UC07         |
| **eaa ledger add**                          | Ghi lỗi ảo giác mới                                                    | UC08         |
| **eaa report kpi \[--csv out.csv\]**        | Xuất báo cáo KPI                                                       | UC09         |
| **eaa resume**                              | Khôi phục phiên từ Project State                                       | UC10         |

**6. Giao tiếp LLM và xử lý lỗi**

- LLMClient.generate: timeout 120s, retry 2 lần với backoff khi lỗi
  mạng; mọi lời gọi ghi lại (prompt hash, model, thời gian, token) phục
  vụ truy vết NFR-07.

- Phản hồi LLM được bóc tách thành file mã nguồn theo quy ước khối
  \`\`\`file:\<đường_dẫn\>; phản hồi sai định dạng tính là một lần fail
  của vòng tự sửa.

- API key chỉ đọc từ biến môi trường EAA_LLM_KEY; bị che trong mọi log
  (NFR-06).

- Mã thoát CLI: 0 thành công; 2 chờ gate; 3 quá N lần tự sửa (bàn giao
  người); 4 lỗi môi trường (thiếu toolchain) — phục vụ script hóa thực
  nghiệm A/B.

**7. Truy vết yêu cầu → module**

| **Yêu cầu (SRS)**           | **Module hiện thực hóa**           | **Kiểm chứng bởi (STP)** |
|-----------------------------|------------------------------------|--------------------------|
| **FR-ORC-01/02**            | orchestrator.py, state.py          | TC-03, TC-08             |
| **FR-GATE-01**              | gates.py + invariant merge (mục 4) | TC-01, TC-02             |
| **FR-KB-01/02/03**          | composer.py, ledger.py             | TC-04, TC-05, TC-10      |
| **FR-GEN-01, FR-VER-01/02** | orchestrator.py, tools/\*          | TC-06, TC-07             |
| **FR-LLM-01**               | llm/base.py + adapters             | TC-11                    |
| **FR-KPI-01**               | kpi.py                             | TC-09                    |
| **FR-TUN-01, FR-SIM-01**    | cli tune, tools/sim.py             | TC-12, TC-13             |
