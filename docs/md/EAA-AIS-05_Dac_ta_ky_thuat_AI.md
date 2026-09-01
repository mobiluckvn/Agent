**EMBEDDED AIDD AGENT**

**ĐẶC TẢ KỸ THUẬT AI (AI ENGINEERING SPEC)**

*Thu nhận đầu vào đa phương thức · Nén ngữ cảnh · Quản lý RAG · Đồ thị
tri thức phần cứng · Vòng tự đánh giá thông tin · Cấu hình Gemini Pro
3.1*

| **Thuộc tính**         | **Giá trị**                                                                                                                         |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| **Mã tài liệu**        | EAA-AIS-05                                                                                                                          |
| **Phiên bản**          | 1.2 (Bản thảo trình thầy hướng dẫn)                                                                                                 |
| **Ngày lập**           | 28/08/2026                                                                                                                          |
| **Người lập**          | Vũ Trí Công                                                                                                                         |
| **Mô hình nền**        | Google Gemini Pro 3.1 (ghim phiên bản)                                                                                              |
| **Tài liệu liên quan** | EAA-SRS-01 (bổ sung FR mục 7); EAA-SAD-02 (chi tiết hóa Knowledge Base); EAA-SDD-03 (bổ sung module); EAA-STP-04 (bổ sung TC mục 7) |

| **Phiên bản** | **Ngày**   | **Người sửa** | **Nội dung thay đổi**                                                                                                                                                                                                                          |
|---------------|------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **1.0**       | 28/08/2026 | Vũ Trí Công   | Phát hành lần đầu — đặc tả tầng kỹ thuật AI của sản phẩm                                                                                                                                                                                       |
| **1.1**       | 28/08/2026 | Vũ Trí Công   | max_output_tokens 200.000; bổ sung mục 6 (thu nhận đầu vào đa phương thức, vòng tự đánh giá đủ thông tin), mục 7 (chế độ chẩn đoán phần cứng cộng tác), mục 8 (vòng đời tri thức, phiên bản mã, kho phẩm xuất); quy trình P6–P9; FR/TC bổ sung |
| **1.2**       | 28/08/2026 | Vũ Trí Công   | Bổ sung mục 9: tự động phát hiện, tìm và cài đặt công cụ (eaa doctor, tool manifest, env_lock chống trôi phiên bản toolchain); quy trình P10; FR-ENV, TC-34..36                                                                                |

**1. Giới thiệu và vị trí trong bộ tài liệu**

Tài liệu đặc tả tầng kỹ thuật AI của Embedded AIDD Agent — phần "trí
tuệ" nằm giữa Knowledge Base và LLM Core đã định nghĩa trong EAA-SAD-02.
Bốn câu hỏi tài liệu này trả lời: (1) đưa GÌ vào ngữ cảnh của mô hình và
nén thế nào để nhỏ mà không mất thông tin quyết định; (2) quản lý kho
tri thức RAG (Datasheet Store) theo vòng đời nào để chống ảo giác một
cách có kiểm soát; (3) tổ chức tri thức phần cứng thành đồ thị
(Knowledge Graph) để máy suy luận được về quan hệ — thứ mà truy xuất văn
bản thuần túy không làm được; (4) thu nhận đầu vào đa phương thức (lệnh,
PDF, ảnh, code) và tự đánh giá đủ thông tin trước khi làm việc — trách
nhiệm chủ động "đi tìm cái mình thiếu" của Agent. Mô hình nền được chốt
là Google Gemini Pro 3.1.

**Luận điểm xuyên suốt:** với lập trình nhúng, ngữ cảnh NHỎ và ĐÚNG
thắng ngữ cảnh DÀI và ĐỦ. Cửa sổ ngữ cảnh của Gemini Pro 3.1 rất lớn,
nhưng đề án chủ động KHÔNG tận dụng tối đa: ngữ cảnh càng dài, tín hiệu
quan trọng (một bit trong thanh ghi) càng dễ chìm trong nhiễu, chi phí
càng cao và kết quả càng khó tái lập. Toàn bộ mục 3 phục vụ nguyên tắc
này.

**2. Cấu hình mô hình nền — Gemini Pro 3.1**

| **Tham số**            | **Giá trị**                                                                                                  | **Lý do**                                                                                                                                                                                        |
|------------------------|--------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Model**              | gemini-pro-3.1 (ghim mã phiên bản đầy đủ, không dùng alias "latest")                                         | Tái lập thực nghiệm A/B — model trôi phiên bản làm hỏng so sánh (rủi ro R1, EAA-STP-04)                                                                                                          |
| **temperature**        | 0.2 (sinh mã) / 0.4 (phân tích tuning tại G4)                                                                | Mã nhúng cần tất định; phân tích chẩn đoán cần thoáng hơn một chút                                                                                                                               |
| **max_output_tokens**  | 200.000 (hiệu lực = min(200.000, trần thực tế của model tại thời điểm gọi))                                  | Đặt cao để không bao giờ cắt cụt phản hồi (file dài, nhiều file, kèm giải thích); kỷ luật "module ≤ 300 dòng" KHÔNG dựa vào trần token mà được cưỡng chế ở cổng static analysis (Modular Design) |
| **system_instruction** | Lớp Vai trò + Ràng buộc cứng (K1)                                                                            | Gemini tách system instruction khỏi user content — tận dụng để ràng buộc không bị "trôi"                                                                                                         |
| **response format**    | Khối \`\`\`file:\<path\> cho sinh mã; JSON schema (structured output) cho tuning và phân loại lỗi            | Bóc tách máy được; phản hồi sai định dạng tính là 1 lần fail vòng tự sửa                                                                                                                         |
| **Ngân sách**          | ≤ 8.000 token vào / lần gọi; count_tokens kiểm tra TRƯỚC khi gọi                                             | Cưỡng chế kỷ luật nén (FR-CTX-01); vượt ngân sách = lỗi lắp ráp, không phải cứ gửi                                                                                                               |
| **An toàn dữ liệu**    | Chỉ gửi: constraints, chunk đã duyệt, interface, nhiệm vụ. Không gửi: toàn bộ datasheet, thông tin định danh | Giảm bề mặt rò rỉ; datasheet có bản quyền chỉ trích dẫn đoạn ngắn cần thiết                                                                                                                      |

**3. Kỹ thuật ngữ cảnh và nén ngữ cảnh (Context Engineering)**

<img
src="handoff/docs/md/media_EAA-AIS-05_Dac_ta_ky_thuat_AI/media/f2193936784e151167f09351370c496cc2bf7a2b.png"
style="width:6.66667in;height:4.35417in" />

***Hình 1. Đường ống lắp ráp ngữ cảnh: nguồn thô → bộ nén 7 kỹ thuật →
prompt có ngân sách → Gemini Pro 3.1***

**3.1. Bảy kỹ thuật nén (K1–K7)**

| **Mã** | **Kỹ thuật**                | **Cách làm**                                                                                                                                                    | **Hiệu quả nén (ước tính)**                                                              |
|--------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| **K1** | Bảng hóa ràng buộc          | constraints.yaml được dịch thành bảng markdown ngắn dạng lệnh ("CẤM delay()", "RAM \< 2KB") thay vì văn xuôi giải thích                                         | ~60% so với mô tả văn xuôi; quan trọng hơn: mệnh lệnh ngắn được mô hình tuân thủ tốt hơn |
| **K2** | Chưng cất bảng thanh ghi    | Chunk datasheet lưu ở dạng bảng thanh ghi–bit–ý nghĩa, không phải đoạn văn quét từ PDF                                                                          | ~70%; mỗi chunk ≤ 300 token                                                              |
| **K3** | Interface-only context      | Module đã merge chỉ xuất hiện qua file .h + 1 dòng tóm tắt chức năng; KHÔNG BAO GIỜ gửi lại body đã viết                                                        | ~80–90% trên phần mã nguồn; đây là kỹ thuật nén quan trọng nhất khi dự án lớn dần        |
| **K4** | Trích chọn trạng thái       | Chỉ gửi phần Project State liên quan module hiện tại (module đó + phụ thuộc trực tiếp), không gửi cả backlog                                                    | Giữ ngữ cảnh trạng thái ~100 token bất kể dự án lớn đến đâu                              |
| **K5** | Chưng cất lỗi thành quy tắc | Mỗi mục Error Ledger được cô đọng thành quy tắc 1 dòng ("KHÔNG dùng TCCR2C — không tồn tại trên ATmega328P"); chọn top-3 lỗi cùng ngoại vi với module đang sinh | Nhật ký lỗi dài vô hạn nhưng phần đưa vào prompt luôn ~300 token                         |
| **K6** | Truy vấn đồ thị             | Knowledge Graph trả về danh sách thanh ghi/chân liên quan + cảnh báo xung đột, dưới dạng vài dòng sự kiện (facts), thay vì mô tả phần cứng dài                  | Thay thế việc gửi cả hardware_profile                                                    |
| **K7** | Graph-RAG chọn chunk        | Đồ thị quyết định chunk nào được nạp (mục 5.3) — nén bằng cách LOẠI đúng thứ không cần                                                                          | Giữ lớp datasheet ổn định ở top-3 chunk                                                  |

**3.2. Vòng tự sửa dạng vá (patch-based repair)**

Ở các vòng tự sửa (bước 7–8 của vòng lặp chuẩn), Agent KHÔNG gửi lại
toàn bộ file: prompt sửa lỗi chỉ gồm thông báo lỗi của cổng kiểm chứng +
hàm/đoạn liên quan + yêu cầu trả về bản vá theo định dạng khối thay thế
hàm. Kỹ thuật này vừa nén (~70% ở vòng sửa), vừa chống một lỗi kinh điển
của LLM: "sửa chỗ này, hỏng chỗ kia" do viết lại cả file. Ngân sách
3.500 token dự phòng trong Hình 1 dành cho lớp này.

> **Điều chỉnh 01/09/2026 (SL-135).** Lớp này rút còn **2.000 token**; 1.500
> token chuyển sang hai lớp mới: `project_rules` (1.000 — luật thiết kế riêng
> của dự án, lấy từ thư viện mẫu prompt của NFR-05) và `host_test` (500 — hợp
> đồng bài kiểm trên máy chủ, do Platform Pack khai). Tổng vẫn đúng 8.000.
>
> Lý do rút được: prompt vá cố ý KHÔNG chứa toàn văn tệp, chỉ có thông báo lỗi
> và đúng những hàm liên quan — 2.000 token vẫn dư cho việc đó.
>
> Lý do PHẢI tách: hai khối trên trước đây nằm trong lớp `task`, mà vòng vá bỏ
> lớp `task`. Chúng biến mất ở đúng vòng vá — lúc mô hình đang sửa mã và dễ
> tái phạm nhất. Nay chúng là lớp riêng nên có mặt ở cả lượt sinh đầu lẫn mọi
> vòng vá.

**3.3. Chống Context Loss — khẳng định lại thiết kế**

Vì mọi lần gọi là stateless và ngữ cảnh luôn được LẮP RÁP LẠI từ các kho
(không phải hội thoại nối dài), hệ thống không có khái niệm "quên": ràng
buộc xuất hiện trong 100% lần gọi (TC-04), và một prompt bất kỳ tái lập
được từ (constraints_version, chunk ids, interface set, task) — bốn
thành phần này ghi trong commit message (NFR-07).

**4. Quản lý RAG — vòng đời Datasheet Store**

**4.1. Đường ống nạp liệu (ingest) — quy trình P1**

| **Bước** | **Ai**      | **Việc**                                                                                          | **Kiểm soát**                                                   |
|----------|-------------|---------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| **1**    | Kỹ sư       | Chọn trang/bảng cần thiết từ PDF datasheet gốc (ATmega328P ~660 trang → chỉ vài chục chunk)       | Con người tuyển chọn — không nạp tự động cả PDF                 |
| **2**    | Kỹ sư + LLM | Chuyển trích đoạn sang bảng thanh ghi–bit (K2); LLM hỗ trợ định dạng, người đối chiếu với bản gốc | Đối chiếu từng bit — chunk sai là nguồn ảo giác "được đóng dấu" |
| **3**    | Agent       | Gắn frontmatter: device, peripheral, registers\[\], topic, source (trang PDF), hash bản gốc       | Metadata là khóa truy xuất và truy vết                          |
| **4**    | Kỹ sư       | Duyệt tại Gate G2                                                                                 | Chỉ chunk approved mới được truy xuất (chống nhiễm bẩn kho)     |
| **5**    | Agent       | Đánh chỉ mục: khớp chính xác tên thanh ghi + BM25 cho từ khóa; cập nhật Knowledge Graph           | MVP không dùng embedding (mục 4.3)                              |

**4.2. Truy xuất và trích dẫn**

- **Truy vấn hai tầng:** tầng 1 — Graph-RAG (mục 5.3) cho danh sách
  thanh ghi của module; tầng 2 — khớp registers\[\] trong frontmatter,
  bổ sung BM25 khi cần; lấy top-k = 3, mỗi chunk ≤ 300 token.

- **Trích dẫn bắt buộc (FR-RAG-02):** mã sinh ra phải ghi chunk id trong
  comment (// ref: atmega328p\_\_timer1_ctc \#ds-012, tr.140). Cổng
  static analysis kiểm tra sự tồn tại của trích dẫn ở mỗi hàm cấu hình
  thanh ghi — mã cấu hình phần cứng không trích dẫn là mã không nguồn
  gốc, bị chặn.

- **Bất biến kho (FR-RAG-01):** chunk sau khi duyệt G2 là bất biến; sửa
  nghĩa là tạo chunk mới + đánh dấu deprecated chunk cũ — lịch sử truy
  vết không bao giờ đứt.

**4.3. Vì sao MVP không dùng embedding/vector database**

Tên thanh ghi (TCCR1A, TWBR, OCR1A) là định danh mạnh, duy nhất và không
nhập nhằng ngữ nghĩa — khớp chính xác + đồ thị cho kết quả tất định,
giải thích được và kiểm thử được (precision@3 đo trực tiếp), trong khi
embedding thêm một tầng xác suất khó giải thích trước Hội đồng và một
phụ thuộc hạ tầng. Đây là quyết định ADR-07, có thể xem xét lại khi mở
rộng sang MCU nhiều họ (hướng phát triển).

**4.4. Đánh giá chất lượng truy xuất — quy trình P4**

Bộ vàng (golden set) ~20 cặp (mô tả nhiệm vụ → chunk đúng) xây một lần
khi kho ổn định; chạy tự động mỗi khi kho thay đổi: precision@3 ≥ 0,9 và
recall thanh ghi bắt buộc = 100% (mọi thanh ghi mà module cấu hình phải
có chunk tương ứng được nạp). Kết quả ghi vào kpi_log.csv — trở thành
một số liệu định lượng mới cho Chương 3.

**5. Đồ thị tri thức phần cứng (Hardware Knowledge Graph)**

**5.1. Lược đồ**

| **Thành phần**  | **Loại**                                                                                         | **Ví dụ**                                                                                 |
|-----------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| **Nút (node)**  | MCU · Peripheral · Register · Pin · Module firmware · Constraint · Chunk datasheet               | ATmega328P; Timer1; TCCR1A; PB1; drv_stepper; "RAM\<2KB"; \#ds-012                        |
| **Cạnh (edge)** | has · configured_by · outputs_on · uses · conflicts_with · documented_in · constrained_by        | Timer1 –configured_by→ TCCR1A; drv_stepper –uses→ Timer1; TCCR1A –documented_in→ \#ds-012 |
| **Nguồn dựng**  | hardware_profile.yaml + khai báo uses: \[...\] của từng module trong backlog + frontmatter chunk | Đồ thị DỰNG TỰ ĐỘNG từ dữ liệu đã có, không nhập tay hai lần                              |
| **Lưu trữ**     | graph.yaml (danh sách node/edge) + networkx trong bộ nhớ; không dùng graph database              | Đủ cho quy mô ~vài trăm nút của một dự án MCU (ADR-08)                                    |

<img
src="handoff/docs/md/media_EAA-AIS-05_Dac_ta_ky_thuat_AI/media/c64ff567e2a22c0d9eb4bbb4510cd6f87eb51d63.png"
style="width:6.66667in;height:4.20833in" />

***Hình 2. Ví dụ đồ thị tri thức và tình huống phát hiện xung đột
Timer1***

**5.2. Ứng dụng 1 — Kiểm tra xung đột tài nguyên trước khi sinh mã
(shift-left)**

Trước khi sinh mã một module, Agent truy vấn đồ thị: hai module cùng
uses một timer/kênh ngắt/chân → CHẶN và báo cáo xung đột để kỹ sư phân
xử (như Hình 2: kernel_tick phải chuyển sang Timer0). Ý nghĩa: loại lỗi
tranh chấp tài nguyên — loại lỗi AI hoàn toàn không nhìn thấy vì nó nằm
NGOÀI file đang viết — được bắt ở giây thứ nhất thay vì trên robot thật.
Đây là đóng góp kỹ thuật đáng trình bày riêng trong Chương 2.

**5.3. Ứng dụng 2 — Graph-RAG: chọn chunk bằng suy luận quan hệ**

Chuỗi truy vấn: module –uses→ peripheral –configured_by→ registers
–documented_in→ chunks. Kết quả là tập chunk ĐÚNG theo cấu trúc phần
cứng chứ không phải "giống về từ ngữ": sinh drv_stepper sẽ nạp chunk
Timer1/OC1A và chunk A4988, không bao giờ nạp nhầm chunk Timer0 dù văn
bản hai chunk gần giống nhau. Tính tất định này là thứ khớp văn bản
thuần túy không bảo đảm được.

**5.4. Ứng dụng 3 — Phân tích ảnh hưởng và checklist review G3**

Khi một module đổi tài nguyên (ví dụ đổi chân), truy vấn ngược đồ thị
liệt kê mọi module/chunk/ràng buộc bị ảnh hưởng — thành danh sách việc
phải kiểm tra lại. Đồng thời, với mỗi diff chờ duyệt tại G3, Agent sinh
checklist từ đồ thị: "module này đụng Timer1 và PB1 — kiểm tra prescaler
khớp \#ds-012; xác nhận không đụng Timer0 của kernel_tick" — biến review
của kỹ sư từ đọc tự do thành đối chiếu có hệ thống.

**6. Tầng thu nhận đầu vào đa phương thức và vòng tự đánh giá đủ thông
tin**

Agent nhận bốn loại đầu vào — lệnh/mô tả của người dùng, file PDF, ảnh
và mã nguồn — và chịu trách nhiệm phân tích, trích xuất thông tin, tự
đánh giá xem thông tin đã đủ để làm việc chưa, chủ động đi tìm phần còn
thiếu, rồi nạp kết quả vào bộ nhớ hệ thống. Tầng này đứng TRƯỚC toàn bộ
đường ống ngữ cảnh ở mục 3: nó là nơi tri thức đi VÀO các kho, còn mục 3
là nơi tri thức đi RA khỏi kho để vào prompt.

<img
src="handoff/docs/md/media_EAA-AIS-05_Dac_ta_ky_thuat_AI/media/69b55a359421b6ac0705589fbe072f8e3c8ef38a.png"
style="width:6.66667in;height:4.42708in" />

***Hình 3. Bốn loại đầu vào → trích xuất → gate → bộ nhớ hệ thống, và
vòng tự đánh giá đủ thông tin***

**6.1. Bốn loại đầu vào và trách nhiệm xử lý của Agent**

| **Đầu vào**                                                      | **Agent trích xuất gì (Gemini Pro 3.1 đa phương thức)**                                                                                                                                                                                                    | **Đích trong bộ nhớ**                                | **Gate**          |
|------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------|-------------------|
| **Lệnh / mô tả của người dùng**                                  | Chuẩn hóa thành Task Spec: mục tiêu, module đích, tiêu chí nghiệm thu, ràng buộc kèm theo; ánh xạ vào use case. Mô tả mơ hồ → HỎI LẠI ngay bằng câu hỏi cụ thể, tuyệt đối không đoán ý                                                                     | Backlog + Project State                              | G1                |
| **PDF (datasheet, app note, schematic xuất PDF)**                | Bảng thanh ghi–bit (K2), đặc tính điện (dòng, áp, tần số), sơ đồ chân, khuyến nghị của hãng → chunk đề xuất + facts cho Knowledge Graph; hash và số trang gốc ghi vào Source Registry                                                                      | Datasheet Store + Graph + Source Registry            | G2                |
| **Ảnh (schematic vẽ tay/chụp, màn oscilloscope, ảnh linh kiện)** | Schematic → netlist đề xuất cho Hardware Profile; màn oscilloscope → số đo đề xuất (chu kỳ, latency, jitter) cho hồ sơ G4; ảnh linh kiện → nhận diện mã linh kiện → kích hoạt tìm datasheet tương ứng. Ảnh mờ/thiếu góc → yêu cầu chụp lại, không suy diễn | Media Store + Hardware Profile + Measurement Records | G1 / G4           |
| **Code (firmware có sẵn, thư viện tham khảo)**                   | Trích interface (.h) và hợp đồng hàm cho Interface Context (K3); nhận diện phong cách đặt tên; quét vi phạm ràng buộc (delay(), malloc...); code viết tay dùng làm baseline Nhóm A của thực nghiệm A/B                                                     | Interface Context + Source Registry                  | G3 (khi tích hợp) |

**Nguyên tắc bất di bất dịch:** mọi thứ máy trích xuất đều chỉ là
PROPOSED FACTS — mang nhãn nguồn, độ tin cậy và trang gốc, nằm ngoài bộ
nhớ hệ thống cho tới khi con người duyệt tại gate tương ứng. Trích xuất
đa phương thức sai (đọc nhầm ảnh, OCR sai bảng PDF) vì thế không bao giờ
nhiễm thẳng vào kho tri thức — nó chết ở cửa gate.

**6.2. Vòng tự đánh giá đủ thông tin (Information Sufficiency Loop) —
quy trình P7**

Trước khi mở vòng sinh mã cho một module, Agent tự trả lời câu hỏi "mình
đã biết đủ chưa?" một cách có cấu trúc, thay vì cứ sinh mã rồi để lỗi lộ
ra:

- **Bước 1 — Lập bảng kiểm thông tin cần (RIC — Required Information
  Checklist):** sinh tự động từ Knowledge Graph + Task Spec: module này
  đụng ngoại vi nào → cần những thanh ghi nào, tham số điện nào, timing
  nào, chân nào, ràng buộc nào.

- **Bước 2 — Đối chiếu bộ nhớ:** mỗi mục RIC nhận một trong ba trạng
  thái: CÓ (kèm con trỏ nguồn), THIẾU, hoặc MÂU THUẪN (hai nguồn cho hai
  giá trị khác nhau — bắt buộc con người phân xử, máy không tự chọn).

- **Bước 3 — Tìm kiếm bổ sung leo thang 3 bậc cho mục THIẾU:** (1) tìm
  trong tài liệu người dùng đã cung cấp nhưng chưa trích xuất hết; (2)
  hỏi người dùng đích danh mục còn thiếu ("cần trang datasheet về Timer1
  chế độ CTC"); (3) tìm trên web trong danh sách nguồn cho phép — trang
  chính thức của nhà sản xuất (Microchip, TDK InvenSense, Allegro...).
  Kết quả tìm được dù từ bậc nào cũng chỉ là proposed facts và phải qua
  G2 như mọi chunk khác.

- **Bước 4 — Readiness Check:** 100% mục Must trong RIC có nguồn thì
  vòng sinh mã mới mở. Agent bị CẤM đoán giá trị thanh ghi hay tham số
  điện để lấp chỗ trống — thiếu là thiếu, và mỗi mục chỉ được tối đa 2
  vòng tìm trước khi chuyển con người xử lý.

**6.3. Bộ nhớ hệ thống mở rộng**

Bên cạnh 5 kho đã định nghĩa (Constraints, Datasheet Store, Prompt
Library, Hardware Profile + Graph, Error Ledger) và Project State, tầng
thu nhận bổ sung ba kho: Media Store (ảnh gốc kèm facts đã trích, phục
vụ đối chiếu lại khi nghi ngờ), Source Registry (danh mục mọi tài liệu
đã nạp: hash, xuất xứ, trang, trạng thái trích xuất — trả lời câu hỏi
"fact này từ đâu ra?" trong một lần tra), và Assumption Log (những giả
định bất khả kháng đã được con người duyệt, ví dụ hệ số ma sát ước lượng
— để chúng hiện diện tường minh thay vì trốn trong code). Cả ba đều là
file phẳng theo dõi bằng Git, nhất quán với góc nhìn dữ liệu của
EAA-SAD-02.

**7. Chế độ chẩn đoán phần cứng cộng tác (Diagnostic Mode)**

Trả lời câu hỏi vận hành quan trọng nhất sau khi lắp ráp: "cảm biến có
hoạt động không, động cơ có quay không?". Agent xử lý bằng cách TỰ SINH
FIRMWARE CHẨN ĐOÁN, đưa xuống mạch, rồi kết hợp hai kênh quan sát để kết
luận — đây là dạng hợp tác Người–Máy đậm đặc nhất của sản phẩm.

**7.1. Nguyên tắc hai kênh quan sát**

**Thế giới vật lý được chia thành hai kênh:** kênh MÁY ĐỌC ĐƯỢC — mọi
thứ đi qua điện và dữ liệu (giá trị cảm biến, mã WHO_AM_I, số xung đã
phát, chu kỳ ngắt đo được), firmware chẩn đoán stream về dưới dạng JSON
từng dòng qua UART và Serial Log Parser phân tích tự động; và kênh CHỈ
NGƯỜI QUAN SÁT ĐƯỢC — trục có quay thật không, đúng chiều không, có
rung, nóng, kêu lạ không. Chẩn đoán chính xác là phép GIAO của hai kênh:
máy nói "đã phát 200 xung bước" mà người nói "trục không quay" thì lỗi
nằm ở dây nối hoặc dòng cấp A4988 — không phải ở code. Một mình AI không
bao giờ kết luận được điều đó; một mình người cũng mất hàng giờ mò —
ghép lại thì ra trong một phiên.

**7.2. Thư viện kịch bản chẩn đoán (Diagnostic Scenarios)**

Khung kịch bản chẩn đoán là TỔNG QUÁT (thuộc engine): mỗi kịch bản =
firmware đo tự sinh + tiêu chí kênh máy + checklist kênh người. Bộ
DS-01..06 dưới đây là thư viện mẫu của dự án robot_balance trên pack
AVR; dự án khác/pack khác khai báo bộ kịch bản riêng theo ngoại vi của
nó.

| **Mã**    | **Kịch bản**                     | **Kênh máy tự kết luận**                                                    | **Kênh người xác nhận**                                                         |
|-----------|----------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| **DS-01** | Quét bus I2C                     | Danh sách địa chỉ trả lời; kỳ vọng 0x68 (MPU6050)                           | — (tự động hoàn toàn)                                                           |
| **DS-02** | Kiểm cảm biến MPU6050            | WHO_AM_I đúng; 100 mẫu gia tốc/gyro trong dải hợp lệ, nhiễu nền bình thường | Nghiêng robot theo lệnh Agent ("nghiêng trái") để đối chiếu dấu và trục dữ liệu |
| **DS-03** | Kiểm động cơ bước (từng động cơ) | Số xung đã phát, tần số xung đo tại chân OC1A                               | Trục quay thật? đúng chiều? đủ 1 vòng? có trượt bước/kêu lạ?                    |
| **DS-04** | UART/telemetry                   | Loopback + đo tốc độ khung thực tế                                          | —                                                                               |
| **DS-05** | Kiểm nguồn dưới tải              | Đọc Vcc bằng ADC nội khi động cơ chạy; phát hiện sụt áp (nguy cơ brown-out) | Quan sát LED nguồn, độ nóng driver                                              |
| **DS-06** | Kiểm timing ngắt                 | Firmware tự đo chu kỳ ngắt Timer1, so ngưỡng 10ms/jitter                    | — (đối chiếu oscilloscope khi cần, qua ảnh — mục 6.1)                           |

**7.3. Quy trình một phiên chẩn đoán — quy trình P8**

- **Chọn kịch bản:** người mô tả triệu chứng (có thể kèm ảnh — mục 6);
  Agent tra Knowledge Graph để khoanh vùng và tổ hợp kịch bản ("robot
  không phản ứng khi nghiêng" → DS-01 + DS-02).

- **Sinh firmware chẩn đoán:** từ template + Datasheet Injection, qua
  cổng biên dịch và static analysis như firmware thường (được phép bỏ
  qua cổng SIL theo Policy vì đây là firmware đo, không phải firmware
  điều khiển).

- **Nạp bán tự động:** board cắm USB vào máy kỹ sư thì Agent tự chạy
  lệnh nạp (avrdude), nhưng lệnh nạp LUÔN cần người xác nhận một phím —
  nhất quán triết lý gate; với kịch bản có chuyển động (DS-03), người
  phải xác nhận checklist an toàn trước: robot đã kê lên, bánh không
  chạm đất.

- **Chạy và thu hai kênh song song:** firmware tự chạy và stream JSON
  qua UART — Serial Log Parser phân tích ngay trên máy kỹ sư; đồng thời
  Agent hiện checklist quan sát từng bước cho người trả lời (có/không/mô
  tả).

- **Giao hai kênh và kết luận:** Agent đối chiếu theo ma trận chẩn đoán
  (mục 7.4), nêu vùng lỗi và bước xử lý đề xuất; kết luận ghi vào
  Measurement Records, lỗi thuộc về code thì vào Error Ledger — phiên
  chẩn đoán cũng là phiên nạp tri thức.

**7.4. Ma trận chẩn đoán ví dụ — bài toán "động cơ không quay"**

| **Kênh máy (UART)**                  | **Kênh người**               | **Kết luận của Agent**                                   | **Hành động đề xuất**                                |
|--------------------------------------|------------------------------|----------------------------------------------------------|------------------------------------------------------|
| **Không phát được xung (đếm = 0)**   | Trục không quay              | Lỗi CODE/cấu hình: Timer1 chưa chạy hoặc prescaler sai   | Mở vòng sửa mã; đối chiếu chunk \#ds Timer1          |
| **Xung phát đủ, tần số đúng**        | Trục không quay, driver nóng | Lỗi PHẦN ĐIỆN: dòng A4988 chưa chỉnh / dây STEP-DIR lỏng | Hướng dẫn chỉnh Vref A4988, kiểm dây theo pin map    |
| **Xung phát đủ**                     | Quay nhưng ngược chiều       | Chân DIR đảo                                             | Đảo logic DIR trong HAL hoặc đảo cặp dây cuộn        |
| **Xung phát đủ**                     | Quay giật, trượt bước, kêu   | Cơ/điện: thiếu dòng, tăng tốc quá gắt, hoặc kẹt cơ khí   | Giảm tốc độ thử; chỉnh dòng; người kiểm cơ khí       |
| **Vcc sụt khi động cơ chạy (DS-05)** | Reset ngẫu nhiên             | Nguồn: brown-out — đúng rủi ro đã lường ở thiết kế B2    | Tách nguồn động lực/điều khiển theo Hardware Profile |

**8. Quản trị vòng đời tri thức và phiên bản mã nguồn**

**8.1. Tri thức mới ghi vào đâu — quy tắc theo từng kho**

**Nguyên tắc chung: KHÔNG BAO GIỜ ghi đè vật lý.** Mọi kho đều là
append-only kết hợp cơ chế thay thế (supersede): bản ghi mới được THÊM
vào kèm con trỏ supersedes trỏ tới bản cũ; bản cũ chuyển trạng thái
deprecated nhưng không bị xóa. Mỗi bản ghi mang đủ: id, timestamp,
nguồn, trạng thái (active / deprecated / resolved), supersedes /
superseded_by. Truy vấn mặc định của Prompt Composer và Graph-RAG chỉ
nhìn thấy bản active — còn lịch sử đầy đủ luôn tra lại được khi cần đối
chứng.

| **Kho**                      | **Tri thức mới ghi thế nào**                                       | **"Đè" tri thức cũ thế nào**                                                                                              | **Gate**                                               |
|------------------------------|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| **Datasheet Store**          | Chunk mới (từ P1 hoặc tìm kiếm bổ sung P7)                         | Chunk mới supersedes chunk cũ; chunk cũ → deprecated kèm lý do; không sửa tại chỗ (FR-RAG-01)                             | G2                                                     |
| **Hard Constraints Spec**    | Phiên bản constraints mới (tăng version, ghi changelog trong file) | Toàn bộ phiên bản cũ đóng băng; mã đã sinh vẫn tra được nó sinh dưới constraints_version nào                              | G1 (bắt buộc duyệt lại vì ảnh hưởng MỌI prompt sau đó) |
| **Hardware Profile + Graph** | Sửa profile → đồ thị dựng lại tự động, đánh version                | Phiên bản đồ thị cũ lưu kèm; mọi thay đổi kích hoạt phân tích ảnh hưởng (8.3)                                             | G1                                                     |
| **Error Ledger**             | Append-only thuần túy                                              | KHÔNG bao giờ sửa/xóa; lỗi được khép lại bằng trạng thái resolved + trỏ tới commit sửa, không xóa dòng                    | —                                                      |
| **Measurement Records**      | Bản ghi đo mới, gắn commit firmware được đo                        | Số đo không bao giờ đè nhau — mỗi bản ghi thuộc về một commit cụ thể                                                      | G4                                                     |
| **Assumption Log**           | Giả định mới ở trạng thái proposed                                 | Vòng đời: proposed → approved → replaced_by khi có SỐ ĐO THẬT thay thế giả định (tri thức thực chứng luôn thắng giả định) | G1/G4                                                  |

**8.2. Khi tri thức mới mâu thuẫn tri thức cũ**

Tri thức mới KHÔNG tự động thắng. Nếu một fact mới mâu thuẫn với fact
đang active (hai giá trị khác nhau cho cùng thanh ghi, hai netlist khác
nhau cho cùng chân), Agent đánh dấu MÂU THUẪN — đúng cơ chế của RIC (mục
6.2) — và dừng ở đó chờ con người phân xử tại gate: người xem cả hai bản
kèm nguồn gốc từng bản, chọn bản thắng; bản thua chuyển deprecated kèm
lý do phân xử ghi lại vĩnh viễn. Máy tuyệt đối không tự chọn "bản mới
hơn" hay "nguồn dài hơn" — độ mới không phải bằng chứng đúng.

**8.3. Thay tri thức thì mã cũ ra sao — tập lỗi thời (stale set)**

Vì mọi hàm cấu hình thanh ghi buộc phải trích dẫn chunk id (FR-RAG-02)
và mọi commit ghi lại constraints_version + chunk ids đã dùng (NFR-07),
nên khi một chunk/fact bị deprecated, Agent truy vấn ngược hai chiều —
đồ thị tri thức và các trích dẫn trong mã — để liệt kê chính xác những
module đã sinh DỰA TRÊN tri thức vừa bị thay. Danh sách đó là stale set:
từng module trong đó bị hạ cấp trạng thái tin cậy và bắt buộc chạy lại
chuỗi kiểm chứng (re-verify); module nào fail thì mở vòng sinh lại với
tri thức mới. Không có chuyện tri thức đã đổi mà mã cũ vẫn nghiễm nhiên
được coi là đúng.

**8.4. Quản lý phiên bản mã — bản nào là tốt, nằm ở đâu**

Git là nguồn sự thật duy nhất, với quy ước ba tầng chất lượng gắn vào
từng commit:

| **Hạng**         | **Điều kiện đạt**                                                                                   | **Ghi nhận ở đâu**                                                        |
|------------------|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| **build-ok**     | Qua compile + avr-size + static analysis + unit test                                                | Kết quả từng cổng ghi vào build ledger (kpi_log) theo commit              |
| **sim-verified** | Thêm: qua cổng mô phỏng SIL (robot ảo giữ cân bằng theo kịch bản)                                   | Nhãn trong build ledger; điều kiện để được merge qua G3 vào main          |
| **hw-verified**  | Thêm: người nghiệm thu trên robot thật tại G4 (±1°, 3 kịch bản), số đo nhập vào Measurement Records | Git tag hw-verified/\<module\>/vN gắn id bản ghi đo; đây là hạng cao nhất |

- **Bản tốt nhất hiện hành — known_good.lock:** file ghi commit
  "biết-là-tốt" cho từng module và cho toàn firmware, CHỈ được cập nhật
  tại G4 khi có hw-verified mới. Câu hỏi "bản nào là tốt, ở đâu?" luôn
  có một câu trả lời máy đọc được: eaa report versions in ra bảng module
  × (commit hiện tại, hạng chất lượng, known-good gần nhất, số đo kèm
  theo).

- **Quay lui (rollback):** bản mới fail nghiệm thu vật lý → một lệnh eaa
  rollback \<module\> đưa mã về known-good gần nhất (git revert/checkout
  theo tag), robot luôn có firmware chạy được; sự kiện rollback ghi vào
  build ledger kèm lý do — thất bại cũng là tri thức.

- **Nhánh và merge:** mỗi module sinh trên nhánh ngắn
  feature/\<module_id\>; chỉ vào main qua G3; commit message chuẩn hóa
  mang prompt hash, model, constraints_version, chunk ids — mỗi commit
  tự mô tả nó được sinh từ tri thức nào, đóng vòng truy vết hai chiều
  tri thức ⇄ mã.

**8.5. Kho phẩm xuất — quản lý tài liệu output và gửi lại theo yêu cầu**

Mọi sản phẩm đầu ra Agent tạo — báo cáo docx/pdf, file mã nguồn, ảnh sơ
đồ, bảng CSV — được đăng ký vào Artifact Registry
(deliverables/registry.json) ngay lúc sinh ra, mỗi phẩm xuất gồm: id,
loại (docx/pdf/code/ảnh/csv), tiêu đề + mô tả ngắn (để tìm bằng ngôn ngữ
tự nhiên), ngày, phiên bản, hash, đường dẫn trong deliverables/, và dòng
dõi dữ liệu (data lineage): sinh từ commit nào, khoảng dữ liệu KPI nào,
phiên bản đồ thị/constraints nào. Phẩm xuất tuân đúng quy tắc vòng đời
của mục 8.1: bản phát hành là bất biến; sinh lại tạo phiên bản mới
supersedes bản cũ.

| **Yêu cầu của người dùng**                     | **Agent xử lý**                                                                                                                                            | **Lệnh CLI**                               |
|------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| **"Gửi lại báo cáo KPI tuần trước, dạng PDF"** | Tra registry theo mô tả + loại + thời gian → trả ĐÚNG BẢN ĐÃ PHÁT HÀNH (bất biến, đúng hash); cần định dạng khác thì chuyển đổi (docx→pdf) từ chính bản đó | eaa docs get \<id\|mô tả\> --format pdf    |
| **"Cho tôi bản KPI mới nhất"**                 | Phân biệt rõ với gửi lại: TÁI SINH tài liệu từ dữ liệu hiện hành (kpi_log, graph, state hôm nay) → thành phiên bản mới trong registry, supersedes bản cũ   | eaa docs regen \<id\>                      |
| **"Đang có những tài liệu gì?"**               | Liệt kê theo loại/ngày/trạng thái (current/superseded), kèm mô tả và lineage                                                                               | eaa docs list \[--type docx\|code\|image\] |
| **"File code driver I2C bản hw-verified"**     | Registry nối với Git: xuất file mã đúng commit của tag chất lượng yêu cầu (8.4), không phải bản đang dở trên nhánh                                         | eaa docs get drv_i2c --rev hw-verified     |

**Điểm thiết kế quan trọng:** tài liệu là HÀM của dữ liệu — báo cáo KPI
là hàm của kpi_log, sơ đồ là hàm của graph. Vì vậy "gửi lại" (trả bản
bất biến đã phát hành) và "làm mới" (chạy lại hàm trên dữ liệu mới) là
hai thao tác khác nhau, và Agent luôn hỏi rõ khi yêu cầu của người dùng
chưa phân định — tránh tình huống người cầm bản làm mới mà tưởng là bản
đã nộp cho thầy.

**9. Tự động phát hiện, tìm và cài đặt công cụ (Tool Provisioning — eaa
doctor)**

Agent phụ thuộc một chuỗi công cụ ngoài (avr-gcc, avr-size, cppcheck,
pytest, avrdude, Git...). Thiếu hoặc lệch phiên bản bất kỳ mắt xích nào
thì cổng kiểm chứng thành vô nghĩa — vì vậy việc phát hiện, tìm và cài
công cụ được thiết kế thành năng lực riêng của Agent, theo đúng triết lý
chung: máy làm phần quét/tìm/chuẩn bị lệnh, con người xác nhận trước khi
máy được phép thay đổi máy tính của họ.

**9.1. Tool Manifest — tools.yaml**

Danh mục công cụ là dữ liệu, không phải code cứng: mỗi công cụ khai báo
tên; lệnh kiểm tra (ví dụ avr-gcc --version); phiên bản tối thiểu; mức
bắt buộc (Must/Optional); dùng ở cổng/sprint nào; và cách cài theo từng
hệ điều hành (winget/choco trên Windows, apt trên Linux), kèm checksum
khi phải tải trực tiếp. Manifest là một kho tri thức như mọi kho khác —
tuân vòng đời append + supersede của mục 8 và mọi thay đổi qua gate.
Manifest chia hai phần đúng kiến trúc 3 tầng: phần CHUNG thuộc engine
(Python, Git, pytest) và phần THEO PLATFORM PACK (avr-gcc, avrdude thuộc
pack AVR; pack STM32 sau này mang toolchain riêng của nó) — cài pack nào
thì doctor quét thêm phần của pack đó.

**9.2. Ba chế độ của eaa doctor**

| **Chế độ**                 | **Máy làm gì**                                                                                                                                                                                 | **Người làm gì**                                                                                                                                      |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Quét (eaa doctor)**      | Chạy lệnh kiểm tra từng công cụ trong manifest; so phiên bản (semver); in bảng trạng thái: OK / THIẾU / QUÁ CŨ, kèm công cụ đó chặn cổng nào nếu thiếu                                         | Đọc báo cáo — chế độ này chỉ đọc, không thay đổi gì trên máy                                                                                          |
| **Sửa (eaa doctor --fix)** | Với mỗi mục THIẾU/QUÁ CŨ: sinh sẵn lệnh cài đúng hệ điều hành từ manifest, HIỂN THỊ NGUYÊN VĂN lệnh sẽ chạy; tải trực tiếp thì kiểm checksum trước khi thực thi; cài xong tự quét lại xác nhận | Xác nhận từng lệnh cài (hoặc chọn cài tay theo hướng dẫn từng bước Agent in ra) — cài đặt là thay đổi máy của kỹ sư nên không bao giờ tự động im lặng |
| **Tìm công cụ mới**        | Nhiệm vụ cần công cụ chưa có trong manifest → Agent tra cứu trong danh sách nguồn cho phép (trang chính thức, package index chính thống), đề xuất: công cụ, phiên bản, nguồn cài, lý do        | Duyệt đề xuất → công cụ mới được THÊM vào manifest (qua gate) rồi mới cài — manifest luôn là nguồn chân lý về "máy này được phép có gì"               |

**9.3. Environment Lock — chống trôi phiên bản toolchain**

Sau mỗi lần quét đạt, doctor ghi env_lock.json: phiên bản chính xác của
từng công cụ + hệ điều hành, băm thành env_hash. Mỗi bản build trong
build ledger và mỗi dòng KPI gắn env_hash này — vì toolchain trôi phiên
bản phá hỏng so sánh A/B y như model trôi phiên bản (rủi ro R1 của
EAA-STP-04). Doctor tự chạy ở đầu mỗi phiên làm việc; phát hiện lệch so
với lock → cảnh báo và người quyết định: chấp nhận (cập nhật lock, ghi
sự kiện) hay khôi phục phiên bản cũ. Nhờ đó câu "hôm qua build được mà
hôm nay không" luôn trả lời được bằng diff hai env_hash.

**9.4. Giới hạn an toàn**

- Không bao giờ tự thực thi lệnh cài khi chưa có xác nhận của người — kể
  cả trong phiên chạy tự động.

- Nguồn cài chỉ gồm package manager chính thống và trang chính thức của
  nhà phát hành trong danh sách cho phép; tải trực tiếp bắt buộc khớp
  checksum ghi trong manifest, sai là từ chối.

- Không sửa PATH hay biến môi trường một cách ngầm định — mọi thay đổi
  môi trường được in ra và ghi vào nhật ký phiên.

- Cài thất bại sau 2 lần → dừng, in hướng dẫn cài tay từng bước; không
  lặp vô hạn.

**9.5. Cập nhật bộ nhớ sau khi cài — Thẻ công cụ (Tool Card)**

Cài xong chưa phải là xong: Agent phải BIẾT rằng công cụ đã có và biết
CÁCH DÙNG nó. Ngay sau khi cài thành công, doctor chạy một smoke test tự
động (ví dụ: biên dịch một file C tối thiểu bằng avr-gcc, chạy cppcheck
trên một file mẫu) rồi ghi/cập nhật Thẻ công cụ (Tool Card) vào bộ nhớ
hệ thống — kho tools_kb/ — gồm: tên và phiên bản đã kiểm; đường dẫn thực
thi trên máy này; công cụ phục vụ cổng kiểm chứng nào; CÚ PHÁP GỌI CHUẨN
đã được smoke test chứng minh chạy được trên chính máy này; cách đọc kết
quả (mã thoát, regex bắt lỗi/cảnh báo trong output); và các lỗi thường
gặp kèm cách xử lý (tích lũy dần qua sử dụng, như Error Ledger nhưng cho
công cụ).

**Điểm thiết kế quan trọng:** các adapter trong Tool Layer
(tools/compile.py, static.py...) ĐỌC lệnh gọi và quy tắc parse từ Tool
Card thay vì hard-code — "cách xài công cụ" là dữ liệu trong bộ nhớ,
không phải hằng số trong code. Nhờ vậy đổi phiên bản công cụ hay đổi máy
chỉ là cập nhật thẻ (qua vòng đời supersede của mục 8), adapter không
phải sửa; và mọi thay đổi hành vi công cụ đều truy vết được như mọi tri
thức khác. Tool Card cũng được nạp (dạng nén một dòng mỗi công cụ) vào
ngữ cảnh khi Agent cần sinh lệnh liên quan công cụ — tránh ảo giác cú
pháp lệnh y như Datasheet Injection tránh ảo giác thanh ghi.

**10. Các quy trình vận hành (P1–P10)**

| **Mã**  | **Quy trình**                          | **Chu kỳ**                         | **Tóm tắt**                                                                                                                                                                |
|---------|----------------------------------------|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **P1**  | Nạp liệu datasheet vào RAG             | Khi bắt đầu và khi thêm ngoại vi   | 5 bước tại mục 4.1, kết thúc bằng Gate G2; đồ thị cập nhật tự động                                                                                                         |
| **P2**  | Thêm module mới vào backlog            | Mỗi module                         | Khai báo id + uses\[\] + phụ thuộc → Agent kiểm tra xung đột đồ thị NGAY LÚC KHAI BÁO → duyệt vào backlog                                                                  |
| **P3**  | Vòng tự sửa dạng vá                    | Mỗi lần fail cổng kiểm chứng       | Chỉ gửi lỗi + đoạn liên quan, nhận bản vá; ≤ N = 3 lần (mục 3.2)                                                                                                           |
| **P4**  | Đánh giá chất lượng RAG                | Mỗi khi kho thay đổi               | Chạy golden set; precision@3 ≥ 0,9; recall thanh ghi bắt buộc 100% (mục 4.4)                                                                                               |
| **P5**  | Quản lý ngân sách token/chi phí        | Liên tục                           | count_tokens trước mỗi lần gọi; kpi_log thêm cột tokens_in, tokens_out, cost_est; báo cáo chi phí/module trong eaa report                                                  |
| **P6**  | Thu nhận đầu vào đa phương thức        | Khi có đầu vào mới                 | Phân loại (lệnh/PDF/ảnh/code) → trích xuất bằng Gemini đa phương thức → proposed facts → gate tương ứng → nạp bộ nhớ + cập nhật Graph + Source Registry (mục 6.1)          |
| **P7**  | Vòng tự đánh giá đủ thông tin          | Trước mỗi module                   | RIC từ Graph + Task Spec → đối chiếu bộ nhớ (CÓ/THIẾU/MÂU THUẪN) → tìm kiếm leo thang 3 bậc → Readiness Check mở vòng sinh mã (mục 6.2)                                    |
| **P8**  | Phiên chẩn đoán phần cứng cộng tác     | Khi bring-up / có triệu chứng      | Chọn kịch bản DS từ triệu chứng + Graph → sinh firmware chẩn đoán → nạp có xác nhận + checklist an toàn → thu 2 kênh song song → giao kênh, kết luận, ghi bộ nhớ (mục 7.3) |
| **P9**  | Cập nhật tri thức & xử lý stale set    | Khi tri thức bị thay thế           | Supersede qua gate → truy vấn ngược graph + trích dẫn trong mã → lập stale set → re-verify từng module, fail thì sinh lại (mục 8.3)                                        |
| **P10** | Kiểm tra & chuẩn bị môi trường công cụ | Đầu mỗi phiên; khi cần công cụ mới | eaa doctor quét theo manifest → báo cáo OK/THIẾU/QUÁ CŨ → --fix sinh lệnh cài chờ người xác nhận → cập nhật env_lock, gắn env_hash vào build/KPI (mục 9)                   |

**11. Yêu cầu và test case bổ sung (nối vào SRS/STP)**

| **Mã**        | **Yêu cầu bổ sung**                                                                                                                                                                                             | **Ưu tiên** |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| **FR-CTX-01** | Ngân sách token vào ≤ 8.000 được cưỡng chế bằng count_tokens trước khi gọi; vượt = lỗi lắp ráp, không gọi API                                                                                                   | Must        |
| **FR-CTX-02** | Interface-only: body của module đã merge không bao giờ xuất hiện trong prompt                                                                                                                                   | Must        |
| **FR-CTX-03** | Vòng tự sửa dùng bản vá (patch), không gửi lại toàn bộ file                                                                                                                                                     | Should      |
| **FR-RAG-01** | Chunk sau duyệt G2 bất biến; sửa = chunk mới + deprecate chunk cũ                                                                                                                                               | Must        |
| **FR-RAG-02** | Mã cấu hình thanh ghi phải trích dẫn chunk id; static analysis kiểm tra                                                                                                                                         | Must        |
| **FR-RAG-03** | Golden set truy xuất: precision@3 ≥ 0,9; recall thanh ghi bắt buộc 100%                                                                                                                                         | Should      |
| **FR-KG-01**  | Đồ thị dựng tự động từ hardware_profile + khai báo uses + frontmatter chunk                                                                                                                                     | Must        |
| **FR-KG-02**  | Kiểm tra xung đột tài nguyên trước khi sinh mã và ngay khi khai báo module (P2)                                                                                                                                 | Must        |
| **FR-KG-03**  | Graph-RAG là bộ chọn chunk mặc định; checklist G3 sinh từ đồ thị                                                                                                                                                | Should      |
| **FR-ING-01** | Nhận và phân loại 4 loại đầu vào: lệnh/mô tả, PDF, ảnh, code; trích xuất bằng năng lực đa phương thức của Gemini Pro 3.1                                                                                        | Must        |
| **FR-ING-02** | Mọi kết quả trích xuất là proposed facts (nguồn + độ tin cậy + trang gốc); chỉ vào bộ nhớ hệ thống sau gate tương ứng                                                                                           | Must        |
| **FR-ING-03** | Ảnh màn oscilloscope được đọc thành số đo đề xuất cho hồ sơ G4, người sửa được trước khi lưu                                                                                                                    | Should      |
| **FR-ING-04** | Code có sẵn nạp theo nguyên tắc interface-only (K3); toàn văn chỉ khi người dùng yêu cầu tường minh                                                                                                             | Must        |
| **FR-GAP-01** | RIC sinh tự động từ Knowledge Graph + Task Spec trước mỗi module                                                                                                                                                | Must        |
| **FR-GAP-02** | Tìm kiếm bổ sung leo thang 3 bậc; web chỉ trong danh sách nguồn cho phép; kết quả vẫn qua G2                                                                                                                    | Must        |
| **FR-GAP-03** | Readiness Check chặn vòng sinh mã khi RIC còn mục Must thiếu; cấm đoán giá trị thanh ghi/tham số điện; mâu thuẫn nguồn phải do con người phân xử                                                                | Must        |
| **FR-DIA-01** | Thư viện kịch bản chẩn đoán DS-01..06; firmware chẩn đoán sinh tự động, qua cổng compile + static analysis                                                                                                      | Must        |
| **FR-DIA-02** | Nạp firmware bán tự động (avrdude) luôn cần người xác nhận; kịch bản có chuyển động bắt buộc checklist an toàn trước khi chạy                                                                                   | Must        |
| **FR-DIA-03** | Kết luận chẩn đoán bằng phép giao hai kênh (telemetry máy + quan sát người); kết quả ghi vào Measurement Records / Error Ledger                                                                                 | Must        |
| **FR-KLC-01** | Mọi kho append-only + supersede; không ghi đè vật lý; truy vấn mặc định chỉ trả bản active                                                                                                                      | Must        |
| **FR-KLC-02** | Tri thức mới mâu thuẫn tri thức active → người phân xử tại gate; bản thua deprecated kèm lý do; máy không tự chọn theo độ mới                                                                                   | Must        |
| **FR-KLC-03** | Supersede kích hoạt stale set (truy vấn ngược graph + trích dẫn trong mã); module trong stale set bị hạ tin cậy và buộc re-verify                                                                               | Must        |
| **FR-VER-01** | Ba hạng chất lượng build-ok \< sim-verified \< hw-verified; hạng ghi trong build ledger; tag hw-verified gắn bản ghi đo G4                                                                                      | Must        |
| **FR-VER-02** | known_good.lock chỉ cập nhật tại G4; eaa rollback đưa module về known-good gần nhất bằng một lệnh                                                                                                               | Must        |
| **FR-DOC-01** | Mọi phẩm xuất (docx, pdf, code, ảnh, csv) đăng ký vào Artifact Registry kèm mô tả, hash, phiên bản, data lineage                                                                                                | Must        |
| **FR-DOC-02** | Phân biệt "gửi lại" (bản phát hành bất biến, đúng hash) và "làm mới" (tái sinh từ dữ liệu hiện hành, thành phiên bản mới); chưa rõ thì hỏi                                                                      | Must        |
| **FR-DOC-03** | Truy hồi phẩm xuất bằng mô tả tự nhiên + bộ lọc loại/thời gian; xuất file code theo đúng hạng chất lượng yêu cầu (--rev hw-verified)                                                                            | Should      |
| **FR-ENV-01** | Tool manifest (tools.yaml) khai báo công cụ, lệnh kiểm tra, phiên bản tối thiểu, cách cài theo OS; eaa doctor quét và báo cáo OK/THIẾU/QUÁ CŨ                                                                   | Must        |
| **FR-ENV-02** | doctor --fix sinh lệnh cài từ manifest, hiển thị nguyên văn và LUÔN cần người xác nhận; nguồn cài chỉ trong danh sách cho phép; tải trực tiếp phải khớp checksum                                                | Must        |
| **FR-ENV-03** | Công cụ ngoài manifest: Agent tra cứu nguồn cho phép, đề xuất; người duyệt mới thêm vào manifest (manifest theo vòng đời tri thức mục 8)                                                                        | Should      |
| **FR-ENV-04** | env_lock.json ghi phiên bản đã kiểm; build ledger và KPI gắn env_hash; lệch lock → cảnh báo, người quyết chấp nhận hay khôi phục                                                                                | Must        |
| **FR-ENV-05** | Sau cài đặt thành công: chạy smoke test và ghi/cập nhật Tool Card (phiên bản, đường dẫn, cú pháp gọi đã kiểm chứng, quy tắc parse output) vào bộ nhớ; adapter Tool Layer đọc lệnh từ Tool Card, không hard-code | Must        |

| **Mã**    | **Test case bổ sung**                                                                          | **Kết quả mong đợi**                                                                                                               | **Mức** |
|-----------|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|---------|
| **TC-16** | Lắp prompt vượt ngân sách (ép nhiều chunk)                                                     | Bị chặn trước khi gọi API; báo lớp nào vượt                                                                                        | Int     |
| **TC-17** | Sinh driver có cấu hình thanh ghi, xóa trích dẫn                                               | Static analysis fail vì thiếu // ref: chunk id                                                                                     | Int     |
| **TC-18** | Hai module khai báo cùng uses Timer1                                                           | Bị chặn từ bước khai báo (P2), báo cáo nêu hai module và tài nguyên                                                                | Int     |
| **TC-19** | Vòng tự sửa với file 200 dòng                                                                  | Prompt sửa không chứa toàn bộ file; chỉ hàm lỗi + thông báo lỗi                                                                    | Int     |
| **TC-20** | Chạy golden set sau khi thêm chunk nhiễu                                                       | precision@3 vẫn ≥ 0,9; chunk nhiễu không được chọn cho module không liên quan                                                      | Int     |
| **TC-21** | Module đã merge, sinh module mới phụ thuộc nó                                                  | Prompt chỉ chứa .h của module cũ, không chứa body (K3)                                                                             | Int     |
| **TC-22** | Nộp PDF datasheet có bảng thanh ghi                                                            | Chunk đề xuất đúng dạng bảng thanh ghi–bit, kèm trang gốc, nằm ở trạng thái chờ G2 — chưa truy xuất được                           | Sys     |
| **TC-23** | Nộp ảnh màn oscilloscope đo chu kỳ ngắt                                                        | Số đo đề xuất khớp ảnh (sai số khai báo); người sửa được giá trị trước khi lưu vào Measurement Records                             | Sys     |
| **TC-24** | Xóa một chunk bắt buộc rồi yêu cầu sinh module                                                 | Readiness Check báo THIẾU đích danh thanh ghi; vòng sinh mã không mở; gợi ý 3 bậc tìm kiếm                                         | Int     |
| **TC-25** | Mô phỏng kết quả web ngoài danh sách cho phép                                                  | Nguồn bị loại, không tạo proposed fact; sự kiện ghi log                                                                            | Int     |
| **TC-26** | Hai chunk cho hai giá trị khác nhau của cùng thanh ghi                                         | RIC đánh dấu MÂU THUẪN; Agent dừng chờ người phân xử, không tự chọn                                                                | Int     |
| **TC-27** | DS-03: telemetry báo xung phát đủ, người báo trục không quay                                   | Kết luận vùng lỗi phần điện (dây/dòng A4988), KHÔNG mở vòng sửa mã; hướng dẫn kiểm tra theo pin map                                | Sys     |
| **TC-28** | Chạy DS-03 khi chưa xác nhận checklist an toàn                                                 | Kịch bản có chuyển động không chạy; yêu cầu xác nhận robot đã kê an toàn                                                           | Int     |
| **TC-29** | Deprecate một chunk đang được 2 module trích dẫn                                               | Stale set liệt kê đúng 2 module đó; cả hai bị hạ tin cậy và buộc re-verify; module không liên quan không bị đụng                   | Int     |
| **TC-30** | Bản build mới fail nghiệm thu vật lý tại G4                                                    | eaa rollback đưa module về known-good gần nhất; build ledger ghi sự kiện kèm lý do; known_good.lock không đổi                      | Sys     |
| **TC-31** | Hỏi "bản tốt nhất hiện tại của toàn firmware?"                                                 | eaa report versions trả về commit hw-verified mới nhất kèm số đo đi kèm                                                            | Int     |
| **TC-32** | "Gửi lại báo cáo KPI hôm qua dạng pdf"                                                         | Trả đúng bản phát hành hôm qua (khớp hash), chuyển đổi sang pdf từ chính bản đó — không tái sinh từ dữ liệu mới                    | Sys     |
| **TC-33** | "Cho bản KPI mới nhất" khi dữ liệu đã thay đổi                                                 | Tài liệu tái sinh thành phiên bản mới, supersedes bản cũ trong registry; bản cũ vẫn tra được nguyên vẹn                            | Sys     |
| **TC-34** | Gỡ cppcheck khỏi PATH rồi chạy eaa doctor                                                      | Báo THIẾU kèm cổng bị chặn; --fix sinh đúng lệnh cài theo OS; KHÔNG tự thực thi khi chưa xác nhận                                  | Int     |
| **TC-35** | Giả lập gói tải trực tiếp có checksum sai                                                      | Từ chối cài, báo rõ lý do; sự kiện ghi nhật ký phiên                                                                               | Int     |
| **TC-36** | Nâng phiên bản avr-gcc khác với env_lock rồi build                                             | Cảnh báo trôi môi trường; sau khi người chấp nhận, lock cập nhật và KPI ghi env_hash mới                                           | Int     |
| **TC-37** | Cài mới một công cụ qua doctor --fix                                                           | Smoke test tự chạy; Tool Card xuất hiện trong bộ nhớ với cú pháp gọi chạy được; adapter tương ứng hoạt động ngay mà không sửa code | Int     |
| **TC-38** | Quét toàn bộ mã nguồn engine (eaa/) tìm tên phần cứng cụ thể (atmega, mpu6050, a4988, tccr...) | 0 kết quả — mọi đặc thù phần cứng chỉ nằm trong packs/ và projects/; test chạy trong CI mỗi commit (FR-PLT-01)                     | Unit    |

Hai quyết định kiến trúc mới ghi nhận vào EAA-SAD-02: ADR-07 (khớp chính
xác + BM25 thay embedding — mục 4.3) và ADR-08 (graph.yaml + networkx
thay graph database — mục 5.1).

**12. Rủi ro riêng của tầng AI và giảm thiểu**

| **Rủi ro**                                                         | **Ảnh hưởng**                                                        | **Giảm thiểu**                                                                                                                                     |
|--------------------------------------------------------------------|----------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Chunk sai được duyệt nhầm tại G2**                               | Ảo giác "có đóng dấu" — nguy hiểm hơn ảo giác thường vì có trích dẫn | Quy trình P1 bước 2 đối chiếu từng bit; lỗi phát hiện muộn → deprecate chunk + ghi Error Ledger + chạy lại impact analysis (5.4)                   |
| **Nén quá tay làm mất thông tin quyết định**                       | Mã sai vì thiếu ngữ cảnh, khó chẩn đoán                              | Mọi kỹ thuật nén có TC tương ứng; khi vòng tự sửa chạm N do thiếu ngữ cảnh, Agent ghi nhận "context miss" vào KPI để hiệu chỉnh top-k              |
| **Gemini Pro 3.1 đổi hành vi giữa kỳ thực nghiệm**                 | Hỏng so sánh A/B                                                     | Ghim phiên bản; lưu (prompt hash → phản hồi) làm bằng chứng; nếu buộc nâng cấp: chạy lại golden set + 2 module chuẩn trước khi tiếp tục            |
| **Đồ thị lệch thực tế (khai báo uses thiếu)**                      | Xung đột lọt lưới, chọn chunk sai                                    | Static analysis đối chiếu thanh ghi xuất hiện trong mã với đồ thị — mã đụng Timer1 mà module không khai báo uses timer1 → cảnh báo cập nhật đồ thị |
| **Trích xuất đa phương thức sai (đọc nhầm ảnh, OCR sai bảng PDF)** | Fact sai vào kho nếu lọt gate                                        | Mọi trích xuất là proposed + gate bắt buộc (FR-ING-02); ảnh gốc giữ trong Media Store để đối chiếu lại; ảnh mờ bị từ chối thay vì suy diễn         |
| **Tìm kiếm web kéo về nguồn kém tin cậy**                          | Ảo giác "có nguồn" từ diễn đàn/blog                                  | Danh sách nguồn cho phép chỉ gồm trang nhà sản xuất; mọi kết quả vẫn qua G2; TC-25 kiểm chứng                                                      |
| **Tự cài công cụ từ nguồn độc hại hoặc sai phiên bản**             | Máy kỹ sư bị xâm hại; toolchain lệch phá A/B                         | Whitelist nguồn + checksum bắt buộc + người xác nhận từng lệnh cài (FR-ENV-02); env_lock phát hiện trôi phiên bản (FR-ENV-04)                      |
