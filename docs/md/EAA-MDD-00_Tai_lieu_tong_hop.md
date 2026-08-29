**EMBEDDED AIDD AGENT**

**TÀI LIỆU THIẾT KẾ TỔNG HỢP (MASTER DESIGN DOCUMENT)**

*Điều phối toàn bộ hồ sơ thiết kế và kế hoạch triển khai lập trình · Đề
án tốt nghiệp Thạc sĩ Kỹ thuật – ngành Kỹ thuật Điện tử*

| **Thuộc tính**         | **Giá trị**                                                                                      |
|------------------------|--------------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-MDD-00                                                                                       |
| **Phiên bản**          | 1.0                                                                                              |
| **Ngày lập**           | 28/08/2026                                                                                       |
| **Người lập**          | Vũ Trí Công                                                                                      |
| **Trạng thái**         | ĐÓNG BĂNG THIẾT KẾ (design freeze) — sẵn sàng bắt đầu lập trình 29/08/2026                       |
| **Bộ hồ sơ điều phối** | EAA-SRS-01 · EAA-SAD-02 · EAA-SDD-03 · EAA-STP-04 · EAA-AIS-05 (v1.1) · Ma trận Người–AI (Excel) |

**1. Mục đích và cách dùng tài liệu này**

Đây là tài liệu ĐIỀU PHỐI: nó không lặp lại nội dung chi tiết của năm
tài liệu thành phần, mà chốt lại (a) bản đồ đọc bộ hồ sơ, (b) toàn bộ
quyết định thiết kế đã đóng băng — nguồn chân lý duy nhất khi code, (c)
phạm vi MVP, (d) kế hoạch triển khai lập trình theo sprint bắt đầu từ
ngày 29/08/2026, và (e) định nghĩa hoàn thành. Khi lập trình, gặp bất kỳ
câu hỏi "làm thế nào" — tra bảng mục 2 để biết mở tài liệu nào; gặp câu
hỏi "đã quyết thế nào" — tra bảng mục 4.

**2. Bản đồ bộ hồ sơ thiết kế**

| **Mã**              | **Tài liệu**                                 | **Trả lời câu hỏi gì**                                                                                                                                                      | **Dùng nhiều nhất khi**                                               |
|---------------------|----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| **Excel**           | Ma trận Người–AI (6 giai đoạn, 13 công đoạn) | Ai làm gì ở đâu, tri thức sinh ra là gì — nền tảng phương pháp luận                                                                                                         | Viết Chương 2 đề án; giải thích triết lý cho Hội đồng                 |
| **EAA-SRS-01**      | Đặc tả yêu cầu phần mềm                      | Sản phẩm phải LÀM GÌ: 4 tác nhân, 11 use case, 14 FR + NFR                                                                                                                  | Kiểm tra một tính năng có thuộc phạm vi không; viết test              |
| **EAA-SAD-02**      | Thiết kế kiến trúc                           | Hệ thống được TỔ CHỨC ra sao: 7 khối, máy trạng thái, sequence, 6 ADR                                                                                                       | Quyết định đặt code ở khối nào; hiểu luồng tổng                       |
| **EAA-SDD-03**      | Thiết kế chi tiết                            | Code CỤ THỂ thế nào: cây thư mục, schema dữ liệu, module Python, 10 lệnh CLI                                                                                                | MỞ THƯỜNG TRỰC KHI CODE — đây là bản vẽ thi công                      |
| **EAA-STP-04**      | Kế hoạch kiểm thử                            | Thế nào là ĐÚNG: 4 mức kiểm thử, TC-01..15, tiêu chí nghiệm thu                                                                                                             | Viết pytest; nghiệm thu sprint                                        |
| **EAA-AIS-05 v1.1** | Đặc tả kỹ thuật AI                           | Tầng TRÍ TUỆ: Gemini 3.1, nén ngữ cảnh K1–K7, RAG, Knowledge Graph, thu nhận đa phương thức, chẩn đoán phần cứng, vòng đời tri thức, kho phẩm xuất; FR/TC bổ sung tới TC-33 | Code composer, tools, ingest, registry — mọi thứ chạm LLM và tri thức |

Thứ tự đọc cho người mới trong 90 phút: SAD (hiểu khung) → SDD mục 2–4
(cây thư mục + module) → AIS mục 3 (đường ống ngữ cảnh) → STP mục 4
(biết mình sẽ bị chấm bằng test nào). SRS dùng để tra cứu, không cần đọc
tuyến tính.

**3. Tóm tắt hệ thống một trang**

**Định vị sản phẩm:** EAA là AGENT LẬP TRÌNH NHÚNG TỔNG QUÁT theo kiến
trúc 3 tầng — Engine (logic điều phối, gate, kỹ thuật AI; sạch tuyệt đối
khỏi phần cứng cụ thể) / Platform Pack (đặc thù họ MCU: toolchain, luật,
quy ước — AVR là pack đầu tiên) / Project (dữ liệu từng dự án). Robot 2
bánh tự cân bằng chỉ là DỰ ÁN MẪU (reference project) để kiểm chứng quy
trình trong đề án; giá trị chuyển giao nằm ở engine và phương pháp,
không ở một mạch cụ thể. Hệ quả khi code: mọi tên MCU, thanh ghi, linh
kiện chỉ được phép xuất hiện trong packs/ và projects/ — xuất hiện trong
engine là bug (FR-PLT-01, TC-38).

<img
src="handoff/docs/md/media_EAA-MDD-00_Tai_lieu_tong_hop/media/2983eb47084221b4cdd87847f29e8d5b6bd96dde.png"
style="width:6.45833in;height:4.54167in" />

***Kiến trúc 7 khối — Con người ở trên (5 Human Gate), Thế giới vật lý ở
dưới (chỉ nối qua con người)***

**Ba nguyên tắc + một bất biến, không thương lượng khi code:** (1) mọi
quyết định kiến trúc/an toàn thuộc con người — 5 gate G1–G5 cưỡng chế
trong Orchestrator; (2) không mã nào đến tay người khi chưa qua đủ chuỗi
kiểm chứng máy; (3) không trí nhớ hội thoại — stateless call + Project
State + Knowledge Base; và bất biến quan trọng nhất (SDD mục 4): hàm
merge CHỈ được gọi khi toàn bộ ToolReport.passed VÀ gate G3 approved —
không tồn tại nhánh code thứ hai dẫn tới merge. TC-01 tồn tại để chứng
minh điều này.

**4. Bảng quyết định đã chốt (đóng băng thiết kế)**

| **\#** | **Hạng mục**        | **Quyết định cuối cùng**                                                                                                                                                      | **Nguồn**                    |
|--------|---------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------|
| **1**  | Mô hình nền         | Gemini Pro 3.1, ghim phiên bản; temperature 0.2 (code) / 0.4 (tuning); max_output_tokens 200.000 (hiệu lực = min với trần model)                                              | AIS §2                       |
| **2**  | Ngân sách ngữ cảnh  | ≤ 8.000 token vào/lần gọi, cưỡng chế bằng count_tokens TRƯỚC khi gọi; nén bằng K1–K7                                                                                          | AIS §3                       |
| **3**  | Vòng tự sửa         | Tối đa N = 3 lần, dạng vá (patch); quá N → dừng, bàn giao người kèm log                                                                                                       | SRS FR-GEN-01, AIS §3.2      |
| **4**  | RAG                 | Khớp chính xác tên thanh ghi + BM25; KHÔNG embedding/vector DB; top-k = 3; chunk ≤ 300 token, bất biến sau G2; trích dẫn chunk id bắt buộc trong code                         | AIS §4, ADR-07               |
| **5**  | Knowledge Graph     | graph.yaml + networkx; dựng tự động từ hardware_profile + uses\[\]; kiểm tra xung đột trước sinh mã; Graph-RAG chọn chunk                                                     | AIS §5, ADR-08               |
| **6**  | Mô phỏng            | Tự viết MIL + SIL (thay Wokwi); là cổng kiểm chứng bắt buộc trước merge                                                                                                       | SAD ADR-05                   |
| **7**  | Vòng đời tri thức   | Append-only + supersede; không ghi đè vật lý; mâu thuẫn → người phân xử; supersede → stale set + re-verify                                                                    | AIS §8.1–8.3                 |
| **8**  | Phiên bản mã        | 3 hạng: build-ok \< sim-verified \< hw-verified; known_good.lock cập nhật chỉ tại G4; eaa rollback một lệnh                                                                   | AIS §8.4                     |
| **9**  | Đầu vào             | 4 loại: lệnh, PDF, ảnh, code; mọi trích xuất là proposed facts qua gate; RIC + Readiness Check trước mỗi module; tìm kiếm leo thang 3 bậc, web chỉ whitelist                  | AIS §6                       |
| **10** | Chẩn đoán phần cứng | Thư viện DS-01..06; hai kênh máy/người; nạp cần xác nhận + checklist an toàn                                                                                                  | AIS §7                       |
| **11** | Phẩm xuất           | Artifact Registry; phân biệt "gửi lại" (bất biến) và "làm mới" (tái sinh)                                                                                                     | AIS §8.5                     |
| **12** | Nền tảng            | Python 3.10+ CLI; file phẳng + Git (không DB server, không GUI); Windows/Linux                                                                                                | SAD ADR-01/02/06             |
| **13** | KPI                 | kpi_log.csv: Tdev, retries, first_build_errors, Flash/SRAM, tokens, cost — nguồn số liệu Chương 3                                                                             | SRS FR-KPI-01, AIS P5        |
| **14** | Định vị sản phẩm    | Agent nhúng TỔNG QUÁT, kiến trúc 3 tầng Engine – Platform Pack – Project; engine không chứa hằng số phần cứng nào; robot tự cân bằng = reference project, AVR = pack đầu tiên | SRS §1.2, FR-PLT; SAD ADR-09 |
| **15** | Môi trường công cụ  | eaa doctor: quét theo tool manifest, cài có xác nhận + whitelist + checksum; env_lock chống trôi toolchain; Tool Card ghi cách dùng công cụ vào bộ nhớ sau khi cài            | AIS §9                       |

**5. Phạm vi MVP đợt lập trình này**

- **LÀM:** ENGINE tổng quát (điều phối, gate, composer, vòng đời tri
  thức, doctor) + interface PlatformPack; PLATFORM PACK AVR đầu tiên; DỰ
  ÁN MẪU robot_balance với toàn bộ vòng lặp chuẩn cho 2 module demo
  (drv_i2c_mpu6050, pid_controller); 5 gate trên CLI; Knowledge Base đầy
  đủ các kho; graph + conflict check; ingest PDF→chunk đề xuất; MIL/SIL
  tối thiểu; KPI logger; docs registry; kịch bản chẩn đoán DS-01..03.

- **CHƯA LÀM (ghi nhận, không code):** GUI; đa người dùng; embedding; tự
  nạp firmware không cần xác nhận; Platform Pack thứ hai (STM32/RISC-V —
  hướng phát triển, chính là phép thử chứng minh tính tổng quát); ingest
  ảnh oscilloscope (Should — làm nếu dư thời gian).

- **Chiến thuật LLM:** Sprint 1–3 chạy hoàn toàn bằng MockLLM (trả code
  định sẵn cho các kịch bản pass/fail/vi phạm) — không tốn API, test tất
  định; Gemini thật chỉ vào từ Sprint 4.

**6. Kế hoạch lập trình theo sprint (bắt đầu 29/08/2026)**

| **Sprint**                                     | **Mục tiêu**                                    | **Module code**                                                                                                                            | **Test phải xanh**                                     | **Định nghĩa xong**                                                          |
|------------------------------------------------|-------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|------------------------------------------------------------------------------|
| **S0 — Khung xương (ngày 1–2)**                | Repo chạy được, state bền, policy đúng          | Cây thư mục theo SDD §2; state.py (atomic + lock); policy.py; cli.py khung lệnh; constraints.yaml + hardware_profile.yaml mẫu; pytest + CI | TC-03, TC-08                                           | eaa init && eaa resume chạy đúng; kill -9 giữa chừng không hỏng state        |
| **S1 — Tri thức (ngày 3–5)**                   | Knowledge Base + Graph + Composer               | Loaders 5 kho; graph builder + conflict check; composer.py với K1–K7; MockLLM; ledger.py                                                   | TC-04, TC-05, TC-18, TC-21, TC-16                      | Prompt lắp ráp đúng ngân sách, đúng chunk, có quy tắc lỗi                    |
| **S2 — Vòng lặp chuẩn (ngày 6–9)**             | Sinh mã → kiểm chứng → gate → merge             | tools/compile.py, static.py, unittests.py; orchestrator.py vòng lặp 13 bước; gates.py CLI; git integration; kpi.py                         | TC-01, TC-02, TC-06, TC-07, TC-09, TC-17               | Một module mock đi trọn vòng, merge chỉ qua G3; bất biến merge có test riêng |
| **S3 — Mô phỏng + tri thức sống (ngày 10–13)** | MIL/SIL + ingest + vòng đời tri thức + registry | sim/ (con lắc ngược + mock HAL); tools/sim.py; ingest PDF→chunk đề xuất; supersede + stale set; docs registry + regen                      | TC-12, TC-13, TC-22, TC-24, TC-26, TC-29, TC-32, TC-33 | Robot ảo giữ cân bằng làm cổng chặn thật; đổi chunk → stale set đúng         |
| **S4 — Chạy thật (ngày 14–17)**                | Gemini thật + 2 module demo + chẩn đoán         | llm/gemini.py; end-to-end 2 module; DS-01..03 + P8; rollback + known_good; report versions                                                 | TC-11, TC-14, TC-15, TC-25, TC-27, TC-28, TC-30, TC-31 | TC-15 xanh với Gemini thật; KPI đủ cột cho Chương 3                          |

Nhịp mỗi sprint: code theo SDD → test theo STP/AIS → cuối sprint chạy
lại TOÀN BỘ test đã xanh (chống thoái lui) → ghi lại sai lệch so với
thiết kế (nếu buộc phải lệch, cập nhật tài liệu tương ứng và tăng phiên
bản — thiết kế và code không được rời nhau). Riêng tính tổng quát:
interface PlatformPack (compile/size/flash/rules/sim bindings) chốt ngay
trong S0–S1 và mọi lời gọi toolchain từ S2 trở đi đều đi qua interface
này — code cho AVR nhưng KHÔNG code vào AVR; test TC-38 (quét engine
không chứa tên phần cứng) chạy trong CI từ ngày đầu.

**7. Checklist bắt đầu ngày 29/08**

**8. Định nghĩa hoàn thành MVP (nhắc lại từ SRS §6 + STP §5)**

MVP xong khi: (1) 2 module demo đi trọn vòng lặp chuẩn với Gemini Pro
3.1 thật; (2) 100% test case Must (TC-01..33 trừ các TC gắn FR Should)
xanh; (3) firmware sinh ra đạt ngưỡng đề cương: Flash \< 50%, RAM \<
40%, không tràn stack, ≤ 110% kích thước mã viết tay; (4) nhật ký chứng
minh không gate nào bị vượt tự động và mọi commit truy vết được (prompt
hash, model, constraints_version, chunk ids); (5) kpi_log.csv xuất được
bảng so sánh A/B cho Chương 3. Khi cả năm điều trên xanh — sản phẩm phần
mềm của đề án coi như hoàn thành vòng một, phần còn lại là thực nghiệm
trên robot thật tại G4.
