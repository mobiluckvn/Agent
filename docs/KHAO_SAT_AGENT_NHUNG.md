# Khảo sát Agent lập trình nhúng, và EAA đứng ở đâu

Khảo sát ngày **05/09/2026**. Bảng số liệu: [`EAA_So_sanh_Agent_nhung.xlsx`](EAA_So_sanh_Agent_nhung.xlsx),
sinh lại bằng `python scripts/lam_bang_so_sanh.py`.

**42 tính năng · 9 nguồn · EAA đủ 22, một phần 11, chưa 6, cố ý không theo 3.**

---

## 1. Đọc bảng này thế nào cho đúng

Hai cột trong bảng **không cùng hạng bằng chứng**, và đây là điều phải nói
trước mọi con số:

| Cột | Nó là gì | Kiểm lại được không |
|---|---|---|
| Đối thủ | **"Họ khai có"** — đọc từ trang chính chủ hoặc bài báo | Không. Ta không chạy thử sản phẩm thương mại của ai |
| EAA | **"Đã đo được"** — mỗi ô truy về một mã TC chạy được | Có, bằng `pytest -q` |

Với sản phẩm thương mại, khoảng cách giữa *"khai có"* và *"đo được"* là khoảng
cách không đo được từ bên ngoài. Nên bảng **cố ý không gộp hai cột thành một
điểm số**: một bảng xếp hạng dựng trên hai hạng bằng chứng khác nhau là một
bảng xếp hạng sai.

Khảo sát cũng chịu đúng luật hai hạng nguồn mà chính đề án đặt ra (SL-71..80):
**chính chủ** (trang nhà cung cấp, bài báo đọc được toàn văn) mới được rút tính
năng; **mở** (tin tức, trang tổng hợp) chỉ là manh mối. 3 trong 9 nguồn là chính
chủ, và không dòng tính năng nào đứng một mình trên một nguồn hạng mở.

Một nguồn bị đánh dấu **CHƯA ĐỌC TOÀN VĂN**: bài benchmark của MDPI trả HTTP 403
khi tải. Bảng không rút tính năng nào từ nó.

---

## 2. Ba dạng đối thủ, và họ khác nhau về CHẤT

Khảo sát cho thấy thị trường không phải một khối:

**a. Nền tảng chuyên nhúng, vòng kín trên silicon.** Đại diện: **Embedder**.
Đây là đối thủ gần EAA nhất về ý tưởng: nối đất bằng tài liệu phần cứng, trích
dẫn nguồn cho từng giá trị thanh ghi, và tự chạy build → nạp → kiểm → sửa trên
bo thật. Họ đi xa hơn EAA ở **bề rộng phần cứng** (khai 500+ nền tảng, 13 hãng,
5.500+ ngoại vi) và ở **chiều sâu công cụ đo** (probe, logic analyzer, dao động
ký, đo công suất tương quan với thực thi).

**b. Kiến trúc nghiên cứu.** Đại diện: bài arXiv *Skilled AI Agents for Embedded
and IoT Systems Development*. Đóng góp của nó là **kỹ năng (skills)**: thay vì
nhồi cả SDK vào ngữ cảnh, chưng cất cho từng ngoại vi một tài liệu ngắn gồm mẫu
lập trình, ràng buộc khởi tạo, và **cách hỏng đã biết**. Kèm benchmark
**IoT-SkillsBench**: 42 nhiệm vụ, 23 ngoại vi, 3 cặp nền tảng–framework, 378
lượt chạy **trên phần cứng thật**.

Kết quả của họ đáng chú ý cho đề án này: kỹ năng do **người soạn** đạt 41–42/42
nhiệm vụ; kỹ năng do **LLM tự sinh** cho lợi ích *thất thường* và đôi khi làm
tệ đi. Đó là một bằng chứng độc lập cho luận điểm trung tâm của EAA — tri thức
phải qua tay người trước khi thành nền cho sinh mã.

**c. Trợ lý đa dụng và trợ lý tra cứu của hãng.** GitHub Copilot trong IDE của
Espressif; STM32 Sidekick của ST huấn luyện trên tài liệu chính thức; máy chủ
MCP tài liệu của Espressif nối agent tới nguồn chính chủ. Nhóm này **dừng lại ở
ranh giới phần cứng**. Câu gọn nhất tìm được, từ một bài kỹ thuật về HIL:

> agent sửa được tệp và chạy được build, nhưng **không nạp được bo, không xem nó
> khởi động, và không đọc ngược được cái vừa xảy ra**.

EAA đã vượt ranh giới ấy từ phiên 01/09: nạp, đọc ngược đối chiếu băm ảnh, thu
telemetry, và kết luận chẩn đoán bằng phép giao của kênh máy và kênh người.

---

## 3. Năm việc phải làm để ngang bằng

Xếp theo ưu tiên trong sheet **Việc phải làm** (14 dòng, 5 ưu tiên Cao):

| | Việc | Vì sao |
|---|---|---|
| **A2** | Nạp **SVD** / file mô tả thanh ghi của hãng | SVD là bảng thanh ghi **máy đọc được, chính hãng phát hành**. Nó làm đúng việc mà trích đoạn thủ công đang làm — nhanh hơn nhiều lần và ít sai hơn. Đây là chỗ rẻ nhất để mua bề rộng |
| **A3** | Nạp **sơ đồ nguyên lý / netlist** thành bối cảnh bo | Embedder đọc Altium/KiCad/Eagle rồi giải netlist ra chân, pull-up, địa chỉ bus. EAA nhận việc ấy bằng `hardware_profile.yaml` **gõ tay** — và SL-125 là lần chính chỗ gõ tay ấy sai, giá phải trả là robot lao thẳng một phía |
| **B3** | **Kỹ năng phần cứng** cho từng ngoại vi | `eaa/skills.py` hiện rút kỹ năng *quy trình* (chuỗi lệnh hay lặp). Bài arXiv nói kỹ năng *phần cứng*: mẫu khởi tạo, thứ tự bắt buộc, cách hỏng đã biết — và họ **đo được** rằng nó nâng kết quả lên gần trần |
| **E1** | **Benchmark có phần cứng thật**, công bố được | EAA có chiều **sâu** trên một bài (robot đứng được, 26 lượt nạp có đọc ngược) nhưng chưa có chiều **rộng**. IoT-SkillsBench có 42 nhiệm vụ trên 3 nền tảng |
| **E2** | **Chỉ số chuẩn**: trượt dịch / sai hành vi / đúng, pass@k | Đây là **ngôn ngữ** mà người đọc luận văn dùng để so EAA với văn liệu. Dữ liệu đã nằm sẵn trong `kpi_log.csv` và `llm_calls.jsonl`; thiếu cách tính, không thiếu số |

Bốn dòng ưu tiên Vừa đáng nói thêm:

* **C5 — điều khiển máy đo.** Khoảng cách phần cứng lớn nhất, và nó tốn **thiết
  bị** chứ không chỉ tốn mã.
* **D5 — trọng tài phần cứng.** Sẽ thành lỗi thật ngay khi có người thứ hai chạy
  cùng một bo. Rẻ: một khoá tệp trên cổng nối tiếp.
* **E4 — truy vết hai chiều.** ISO 26262 đòi *yêu cầu ↔ mã ↔ bài kiểm*. EAA
  mạnh ở nhánh *tri thức ↔ mã* nhưng chưa nối tiêu chí nghiệm thu xuống từng
  bài kiểm.
* **F1 — tích hợp IDE.** Mặt tiếp xúc mà kỹ sư nhúng ngồi trong đó cả ngày.
  Không đụng lõi: một lớp mỏng gọi CLI.

---

## 4. Sáu chỗ EAA đang đi trước

Đây là phần đáng viết vào luận văn, vì **không nguồn nào trong khảo sát nêu tới
chúng**:

| | Năng lực | Vì sao nó đáng kể |
|---|---|---|
| **A7** | Vòng đời tri thức — thay trích đoạn thì truy ngược ra mã bị ảnh hưởng | Sửa một datasheet mà không biết mã nào đứng trên bản cũ là để lỗi nằm im chờ ngày lộ |
| **C10** | Đo **độ nhạy** của bài kiểm mới sinh | Cả ba benchmark khảo sát được đều đo *pass/fail*; không cái nào hỏi *bài kiểm ấy có phân biệt được gì không*. Một bài kiểm xanh chưa phải bằng chứng |
| **C11** | Bắt mã **tự chỉnh cho vừa đồ đo** của chính nó | Dạng hỏng đi qua sạch **mọi** cổng tự động. 3 trong 12 lần từ chối G3 của chính đề án là nó |
| **C12** | Canh hợp đồng gọi và **lời gọi bị đánh rơi** | Bằng chứng: `app_init()` mất bốn lời gọi khởi tạo, firmware câm hoàn toàn, **33 bài kiểm vẫn xanh** |
| **E5** | **Tất định và tái lập được** | ISO 26262 đòi công cụ phân tích phải tất định mới *qualify*. Bộ phát lại của EAA cố ý **không bịa phản hồi** khi trượt băm — một lượt phát lại tự sinh nội dung là bằng chứng giả |
| **E6** | Sổ ghi **mọi sai lệch** giữa thiết kế và mã | 175 mục, mỗi mục một lỗi và một bài kiểm canh nó. Đây là dữ liệu gốc của phương pháp huấn luyện — và là thứ một sản phẩm thương mại không có lý do gì công bố |

Bốn trong sáu dòng ấy (C10, C11, C12, E6) nói về **cùng một chuyện**: hệ thống
tự soi chính mình và tự ghi lại chỗ mình sai. Đó là trục mà EAA đi sâu hơn hẳn,
và nó không phải tình cờ — nó đến từ việc mọi lỗi gặp trên bo đều bị bắt viết
thành một mục sổ kèm một bài kiểm.

---

## 5. Ba chỗ khác biệt là QUYẾT ĐỊNH, không phải thiếu sót

Phải tách ba dòng này ra khỏi danh sách việc, nếu không bảng sẽ mang những món
nợ giả:

**C7 — vòng kín hoàn toàn tự động.** Embedder khai chạy *autonomously* và cho
cấu hình bước nào cần duyệt. EAA đặt **duyệt-nạp thành bất biến không cờ nào
tắt được**. Đây là chỗ hai triết lý tách nhau, và luận văn nên nói thẳng thay vì
ghi thành một ô thiếu.

**C9 — nhiều agent kiểm chạy song song.** Song song phá tính tái lập, mà tái lập
là điều kiện *qualify* công cụ theo ISO 26262. Với một đề án lấy bằng chứng làm
trung tâm, đây là đánh đổi sai hướng.

**D7 — chứng nhận SOC 2 / ISO 27001.** Đây là chứng nhận của một **doanh
nghiệp**, không phải tính năng phần mềm. Ghi vào bảng để không ai nhầm nó là
khoảng trống kỹ thuật.

---

## 6. Kết luận một câu

Thị trường đi trước EAA về **bề rộng phần cứng** (SVD, schematic, số nền tảng,
máy đo) và về **đo lường công bố được** (benchmark, pass@k). EAA đi trước về
**kỷ luật quy trình và khả năng tự soi** — và bốn năng lực mạnh nhất của nó
(C10, C11, C12, E6) không xuất hiện trong bất kỳ nguồn nào khảo sát được.

Hai nhóm khoảng cách ấy không cùng độ khó: bề rộng là công việc **tuyến tính**
(TC-47 đã chứng minh thêm một Platform Pack không phải sửa engine), còn kỷ luật
tự soi là thứ phải trả bằng 175 lần sai và 175 bài kiểm.

---

## Nguồn

- [Embedder — Enterprise AI Platform for Embedded Software](https://embedder.com/) *(chính chủ, đã đọc)*
- [Skilled AI Agents for Embedded and IoT Systems Development — arXiv 2603.19583](https://arxiv.org/html/2603.19583v1) *(chính chủ, đã đọc)*
- [GitHub Copilot in Espressif-IDE — Espressif Developer Portal](https://developer.espressif.com/blog/2025/02/github-copilot-in-espressif-ide/) *(chính chủ, đã đọc)*
- [Embedder v0.3.1 nominated for Embedded Award 2026 — Embedded Computing Design](https://embeddedcomputing.com/technology/ai-machine-learning/ai-logic-devices-worload-acceleration/embedder-v031-ai-powered-firmware-engineering-platform-nominated-for-embedded-award-2026-in-the-startup-category) *(mở)*
- [Benchmarking LLMs for Embedded Systems Programming — MDPI Future Internet 18(2) 94](https://www.mdpi.com/1999-5903/18/2/94) *(mở, chưa đọc toàn văn — HTTP 403)*
- [AI assistant for STM32 developers — Dataweek](https://www.dataweek.co.za/27366r) *(mở)*
- [AI coding assistants in the embedded domain — Avnet](https://www.avnet.com/americas/resources/article/ai-coding-assistants-in-the-embedded-domain/) *(mở)*
- [AI-Assisted Hardware-in-the-Loop for Embedded Linux — Electronics Consult](https://electronicsconsult.com/blog/ai-assisted-hardware-in-the-loop/) *(mở)*
- [MISRA: ISO 26262 Software Compliance — Parasoft](https://www.parasoft.com/learning-center/iso-26262/misra/) *(mở)*
