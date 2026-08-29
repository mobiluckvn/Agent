# Sổ sai lệch thiết kế (Design Deviation Register)

Thiết kế đã đóng băng ngày 28/08/2026. Quy tắc trong `CLAUDE.md`: code bám
thiết kế; nếu buộc phải lệch thì **ghi rõ và cập nhật tài liệu tương ứng,
không lệch ngầm**.

Tệp này là nơi ghi. Mỗi mục nêu: lệch ở đâu, vì sao, và tài liệu nào cần sửa
khi phát hành phiên bản tiếp theo. Trước khi bảo vệ, gom các mục ở đây vào bản
cập nhật của tài liệu gốc rồi tăng phiên bản — mục đích là thiết kế và code
không bao giờ rời nhau, chứ không phải là hợp thức hóa việc đi chệch.

Ba loại:

- **BỔ SUNG** — tài liệu chưa nói tới, code phải có. Thường do EAA-AIS-05 v1.1
  và v1.2 thêm năng lực sau khi EAA-SDD-03 v1.0 đã phát hành.
- **DỜI CHỖ** — vẫn đúng chức năng thiết kế, nhưng đặt ở module khác.
- **LỆCH THẬT** — hành vi khác thiết kế. Loại này phải hiếm và phải có lý do
  kỹ thuật, không phải lý do tiện tay.

---

## SL-01 · DỜI CHỖ · Luật chuyển pha đặt ở `policy.py`

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4 |
| **Thiết kế nói** | `orchestrator.py` giữ máy trạng thái, có `advance_phase()` |
| **Code làm** | Bảng cung chuyển pha và hàm kiểm tra thuần túy `check_transition()` nằm ở `eaa/policy.py`; `orchestrator.py` sẽ *gọi* chứ không tự phát biểu luật |
| **Vì sao** | MDD §6 yêu cầu TC-08 xanh ngay Sprint 0, trong khi Orchestrator thuộc Sprint 2. Quan trọng hơn: luật thuần túy thì test được mà không cần dựng cả một dự án giả, và ADR-04 đòi hỏi có **đúng một** nơi phát biểu luật gate — hai nơi là hai chỗ để lọt lưới |
| **Ảnh hưởng chức năng** | Không. `advance_phase()` vẫn thuộc Orchestrator ở Sprint 2 |
| **Cần cập nhật** | EAA-SDD-03 §4: thêm dòng `policy.py` — "bảng phân quyền + bảng cung chuyển pha; `level(task)`, `check_transition()`" |
| **Sprint** | S0 |

## SL-02 · DỜI CHỖ · Đọc `constraints.yaml` tạm nằm ở `cli.py`

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 |
| **Thiết kế nói** | Cây thư mục không có module đọc cấu hình dự án |
| **Code làm** | `eaa/cli.py` có `_load_yaml()` và `constraints_version()` tạm thời |
| **Vì sao** | `eaa init` (Sprint 0) cần đọc ràng buộc, nhưng bộ nạp 5 kho tri thức thuộc Sprint 1 (MDD §6) |
| **Trạng thái** | **Đã đóng ở S1** — chuyển sang `eaa/kb.py`; `cli.py` chỉ còn gọi |
| **Sprint** | S0 → đóng ở S1 |

## SL-03 · BỔ SUNG · `eaa/kb.py` — bộ nạp 5 kho tri thức

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 (cây thư mục), EAA-SAD-02 §3 (Knowledge Base) |
| **Thiết kế nói** | SAD định nghĩa Knowledge Base là một *thành phần* gồm 5 kho; SDD không cấp cho nó module nào — chỉ có `composer.py` "ghép prompt từ Knowledge Base" |
| **Code làm** | Thêm `eaa/kb.py`: nạp Constraints, Datasheet Store, Prompt Library, Hardware Profile |
| **Vì sao** | MDD §6 liệt kê "Loaders 5 kho" là hạng mục của Sprint 1 nhưng SDD không nói đặt ở đâu. Dồn hết vào `composer.py` sẽ trộn hai việc khác nhau: *đọc kho* và *nén để ghép prompt* — tách ra thì mỗi phần test được riêng |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4: thêm `kb.py` |
| **Sprint** | S1 |

## SL-04 · BỔ SUNG · `eaa/graph.py` — Knowledge Graph

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §5, ADR-08 |
| **Thiết kế nói** | AIS v1.1 đặc tả đầy đủ đồ thị tri thức (`graph.yaml` + networkx, kiểm xung đột, Graph-RAG); EAA-SDD-03 v1.0 phát hành trước đó nên cây thư mục không có module này |
| **Code làm** | Thêm `eaa/graph.py` |
| **Vì sao** | Không có chỗ nào khác đặt được. Đây là khoảng trống do thứ tự phát hành tài liệu, không phải bất đồng thiết kế |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4 |
| **Sprint** | S1 |

## SL-05 · BỔ SUNG · `eaa/llm/mock.py` — MockLLM

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2, MDD §5 |
| **Thiết kế nói** | Cây thư mục liệt kê `llm/gemini.py|gpt.py|claude.py`; MDD §5 chốt "Sprint 1–3 chạy hoàn toàn bằng MockLLM" nhưng không đặt tên tệp |
| **Code làm** | Thêm `eaa/llm/mock.py` như một adapter ngang hàng các adapter thật |
| **Vì sao** | MockLLM phải là adapter thật sự cùng interface, không phải một nhánh `if test:` trong engine — nếu không, cái được test ở Sprint 1–3 sẽ không phải cái chạy ở Sprint 4 |
| **Cần cập nhật** | EAA-SDD-03 §2 |
| **Sprint** | S1 |

## SL-06 · BỔ SUNG · Không có `eaa/rag.py` riêng; truy xuất nằm trong `kb.py` + `graph.py`

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §4.2, ADR-07 |
| **Thiết kế nói** | Truy vấn hai tầng: tầng 1 Graph-RAG, tầng 2 khớp `registers[]` trong frontmatter, "bổ sung BM25 khi cần"; top-k = 3 |
| **Code làm** | Tầng 1 ở `graph.chunks_for()`; tầng 2 ở `kb.DatasheetStore.by_register()` (khớp chính xác, không phân biệt hoa thường). **BM25 chưa làm** |
| **Vì sao** | Không có module thứ ba nào cần tồn tại: truy xuất theo quan hệ thuộc về đồ thị, truy xuất theo metadata thuộc về kho. Một `rag.py` ở giữa chỉ chuyển tiếp lời gọi. Về BM25 — AIS nói "bổ sung khi cần"; với bộ chunk hiện tại, khớp chính xác tên thanh ghi đã trả đúng kết quả, nên thêm BM25 lúc này là thêm một tầng xác suất chưa cần thiết |
| **Rủi ro đã biết** | Khi kho chunk lớn lên, truy vấn theo mô tả nhiệm vụ (không nêu tên thanh ghi) sẽ không có đường vào. Dấu hiệu phải làm BM25: golden set (FR-RAG-03, TC-20) tụt dưới precision@3 = 0,9 |
| **Cần cập nhật** | EAA-AIS-05 §4.2: ghi rõ BM25 là tùy chọn có điều kiện kích hoạt, kèm ngưỡng ở trên |
| **Sprint** | S1 |

## SL-07 · BỔ SUNG · `eaa/tools/runner.py` — bộ chạy công cụ dùng chung

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2, EAA-AIS-05 §9.5 |
| **Thiết kế nói** | `tools/` gồm `base.py`, `compile.py`, `static.py`, `unittests.py`, `sim.py`; adapter "ĐỌC lệnh gọi và quy tắc parse từ Tool Card thay vì hard-code" |
| **Code làm** | Thêm `eaa/tools/runner.py` giữ toàn bộ phần chạy tiến trình ngoài và đọc kết quả; các adapter chỉ quyết định tham số |
| **Vì sao** | Nếu mỗi adapter tự gọi `subprocess` thì luật "thiếu công cụ là KHÔNG ĐẠT" phải được nhớ ở bốn chỗ, và chỉ cần một chỗ quên là có một cổng im lặng cho qua. Gom về một nơi thì luật đó chỉ có một chỗ để đúng — và một chỗ để test |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4: thêm `tools/runner.py` |
| **Sprint** | S2 |

## SL-08 · BỔ SUNG · `eaa/vcs.py` và giấy phép merge (`MergeAuthorization`)

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4, NFR-01, NFR-07, EAA-AIS-05 §8.4 |
| **Thiết kế nói** | "Hàm merge của orchestrator chỉ gọi được khi ToolReport.passed cho toàn bộ chuỗi cổng VÀ gates.request('G3') trả về approved — không tồn tại nhánh mã nào khác dẫn tới merge". Cây thư mục không có module Git |
| **Code làm** | Thêm `eaa/vcs.py`. Merge không nằm trong Orchestrator mà nằm sau một vật thể giấy phép: `GitRepo.merge()` chỉ nhận `MergeAuthorization`, và vật thể đó tự kiểm lại toàn bộ bằng chứng lúc được dựng |
| **Vì sao** | Một câu `if` kiểm hai điều kiện là đúng nhưng không ngăn được lối merge thứ hai viết sau này quên mất câu `if` ấy. Đặt phép kiểm vào hàm dựng khiến "dựng được giấy phép" và "đủ điều kiện merge" là cùng một việc |
| **Bổ sung so với thiết kế** | Giấy phép mang băm nội dung đã được duyệt, và `merge()` đối chiếu với nội dung thực tế trên nhánh. Điều kiện nguyên văn của SDD chưa bịt khe "duyệt bản này rồi merge bản khác" |
| **Cần cập nhật** | EAA-SDD-03 §4: mô tả `MergeAuthorization` và bổ sung điều kiện thứ ba (băm nội dung khớp); §2 thêm `vcs.py` |
| **Sprint** | S2 |

## SL-09 · LỆCH THẬT · Duyệt G2 qua `eaa gate approve G2`, chưa có `eaa datasheet`

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §5 |
| **Thiết kế nói** | `eaa datasheet add <file> / approve` là lệnh nạp và duyệt chunk tại Gate G2 (UC03) |
| **Code làm** | Sprint 2 mới có `eaa gate approve G2`, duyệt cả kho chunk hiện có như một hồ sơ. Lệnh `eaa datasheet` vẫn báo "chưa hiện thực hóa" |
| **Vì sao** | `datasheet add` là đường ống nạp liệu — nó thuộc tầng thu nhận đầu vào đa phương thức (AIS §6, quy trình P1/P6) và cả tầng đó thuộc Sprint 3. Làm nửa vời ở Sprint 2 sẽ phải viết lại |
| **Hệ quả hiện tại** | Chunk phải đặt tay vào `datasheets/` rồi mới duyệt. Băm hồ sơ G2 tính trên tập `(id, trạng thái)` của toàn kho, nên thêm hay đổi trạng thái một chunk sẽ làm quyết định cũ hết khớp — đúng hành vi mong muốn |
| **Trạng thái** | **Đã đóng ở S3** — `eaa datasheet add` nạp trích đoạn PDF thành chunk đề xuất, `eaa datasheet list` hiện trạng thái từng chunk; duyệt vẫn qua `eaa gate approve G2` |
| **Sprint** | S2 → đóng ở S3 |

## SL-10 · BỔ SUNG · Bằng chứng kiểm chứng được cất xuống đĩa

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4, EAA-SAD-02 Hình 3 |
| **Thiết kế nói** | Sequence diagram vẽ bước 9 (commit + báo cáo build) và bước 11 (approve → merge) như một mạch liền |
| **Code làm** | Sau bước 10, danh sách `ToolReport` được ghi vào `.eaa/runs/verification_<module>.json`; bước 11 đọc lại |
| **Vì sao** | Trên sequence diagram hai bước ấy liền nhau, nhưng giữa chúng có một con người — nghĩa là có thể cách nhau một ngày và một tiến trình khác. Không cất bằng chứng thì tới lúc merge không còn gì để chứng minh "toàn bộ cổng đã đạt", và lối thoát dễ dãi lúc đó sẽ là bỏ qua phép kiểm ấy |
| **Vì sao vẫn an toàn** | Bằng chứng cất lại không tự đứng một mình: giấy phép merge còn đòi băm nội dung nhánh khớp với thứ người đã duyệt. Không có phép kiểm băm, bằng chứng cũ chỉ chứng minh "đã từng đạt" — một câu khác hẳn "đang đạt" |
| **Cần cập nhật** | EAA-SDD-03 §4: ghi rõ bằng chứng kiểm chứng là dữ liệu bền, kèm điều kiện băm |
| **Sprint** | S2 |

## SL-11 · BỔ SUNG · `eaa/tools/sim_runner.py` — khung chạy mô phỏng

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2, ADR-05, FR-SIM-01 |
| **Thiết kế nói** | `tools/sim.py` — "gate mo phong, binding tu PlatformPack + Project"; mô hình vật lý nằm ở `projects/<dự án>/sim/` |
| **Code làm** | Tách đôi: `tools/sim.py` là CỔNG (chấm điểm, chặn, quét tham số), `tools/sim_runner.py` là KHUNG CHẠY, được Platform Pack gọi như một công cụ ngoài |
| **Vì sao** | Cổng SIL phải chạy chính firmware đã biên dịch, tức một tiến trình khác. Nếu khung chạy nằm trong tiến trình của engine thì chế độ MIL và chế độ SIL sẽ đi hai đường khác nhau — và thứ được kiểm ở MIL không còn bảo đảm gì cho SIL. Tách ra thì cả hai chế độ dùng chung một vòng lặp, chỉ khác nguồn của bộ điều khiển |
| **Engine vẫn sạch** | Khung chạy chỉ biết ba khái niệm *plant*, *controller*, *scenario*; cả ba do dự án cung cấp qua ba hàm `create_plant` / `create_sensor` / `create_actuator` |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4: thêm `tools/sim_runner.py` và mô tả giao thức JSON từng dòng của chế độ SIL |
| **Sprint** | S3 |

## SL-12 · LỆCH THẬT · Bộ điều khiển tham chiếu có thêm vòng ngoài giữ vận tốc

| | |
|---|---|
| **Tài liệu** | Đề cương mục 1.4.2, Ma trận Người–AI công đoạn D4 |
| **Thiết kế nói** | Bộ điều khiển là "PID rời rạc + bộ lọc bù", chống Derivative Kick và Integral Windup |
| **Code làm** | Thêm một vòng ngoài chậm: điểm đặt góc nghiêng tỉ lệ nghịch với vận tốc xe (`speed_gain`) |
| **Vì sao** | **Chính bộ mô phỏng phát hiện ra.** Ở kịch bản chạy dài 60 giây, trôi điểm không của con quay hồi chuyển để lại một sai lệch góc tĩnh; PID thuần túy hiểu đó là "chưa thẳng" nên ra lệnh lực không đổi, xe tăng tốc mãi cho tới lúc trượt bước rồi ngã. Đây là khoảng trống về CẤU TRÚC điều khiển, không bộ tham số nào cứu được — quét cả 60 tổ hợp PID đều ngã |
| **Ý nghĩa với đề án** | Đúng loại kết quả mà công đoạn C1 sinh ra để tìm, và là một mục cụ thể cho Chương 3: mô phỏng bắt được lỗi cấu trúc mà đọc mã và kiểm thử đơn vị không bắt được |
| **Cần cập nhật** | Đề cương mục 1.4.2 và EAA-SRS-01 FR-TUN-01: bộ điều khiển là PID hai vòng, kèm lý do vật lý |
| **Sprint** | S3 |

## SL-13 · BỔ SUNG · `eaa/lifecycle.py` — vòng đời tri thức và tập lỗi thời

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.1–8.3, quy trình P9, FR-KLC-01/02/03 |
| **Thiết kế nói** | AIS đặc tả đầy đủ append-only + supersede + stale set; cây thư mục SDD v1.0 phát hành trước nên không có module này |
| **Code làm** | Thêm `eaa/lifecycle.py` |
| **Bổ sung so với thiết kế** | AIS §8.3 nêu HAI đường truy vấn ngược (đồ thị · trích dẫn trong mã). Code làm thêm đường thứ ba: trường `chunk-ids` trong commit. Nó bắt trường hợp mà hai đường kia bỏ sót — chunk ĐÃ vào prompt và ảnh hưởng tới mã nhưng mã sinh ra không trích dẫn nó ở đâu. Module ấy càng đáng ngờ chứ không phải ít đáng ngờ hơn |
| **Ranh giới bất biến** | FR-RAG-01 nói chunk sau duyệt là bất biến. Code hiểu bất biến ấy là bất biến của NỘI DUNG: trạng thái vòng đời phải chuyển được, nếu không thì không có cách nào đánh dấu một trích đoạn đã sai. Có test canh phần thân không đổi một byte |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §8.3 bổ sung đường truy vấn thứ ba; FR-RAG-01 nói rõ "bất biến về nội dung" |
| **Sprint** | S3 |

## SL-14 · BỔ SUNG · `eaa/readiness.py` — RIC và Readiness Check

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2, quy trình P7, FR-GAP-01/02/03 |
| **Thiết kế nói** | Bốn bước: lập RIC → đối chiếu bộ nhớ → tìm kiếm leo thang ba bậc → Readiness Check |
| **Code làm** | Thêm `eaa/readiness.py`; Orchestrator gọi Readiness Check trong tiền điều kiện của vòng lặp chuẩn, ngay sau kiểm xung đột tài nguyên |
| **Quyết định cần ghi vào tài liệu** | (1) Mục MÂU THUẪN chặn ở MỌI mức ưu tiên, kể cả Should — kho tự mâu thuẫn là vấn đề của cả kho. (2) Bộ dò mâu thuẫn quy mọi cách viết số về cùng giá trị (`0b00` = `0x00` = `0`); không có bước này thì ba cách viết của số không đều thành cờ báo động giả, và một cơ chế báo động giả sẽ bị phớt lờ. (3) Bộ dò cố ý CHỈ đọc dạng có cấu trúc (bảng thanh ghi–bit và dòng công thức) — thà bỏ sót một mâu thuẫn tinh vi còn hơn dựng cờ giả |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §6.2 ghi rõ ba quyết định trên |
| **Sprint** | S3 |

## SL-15 · BỔ SUNG · `eaa/ingest.py` — tầng thu nhận đầu vào

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6, §4.1, quy trình P1/P6, FR-ING-01..04 |
| **Thiết kế nói** | Bốn loại đầu vào; mọi trích xuất là proposed facts; ba kho mở rộng Media Store / Source Registry / Assumption Log |
| **Code làm** | Thêm `eaa/ingest.py` gồm cả ba kho; `PdfIngestor` nạp đúng những trang người chọn |
| **Phạm vi đã làm** | PDF → chunk đề xuất (TC-22); danh sách nguồn web cho phép (TC-25); Source Registry; Assumption Log; Media Store |
| **Phạm vi CHƯA làm** | Trích xuất bằng mô hình đa phương thức (ảnh sơ đồ → netlist đề xuất, ảnh màn hiện sóng → số đo đề xuất, TC-23). Cần mô hình thật nên thuộc Sprint 4. Hiện `PdfIngestor` nhận một `formatter` để cắm mô hình vào; chưa có thì dùng bộ chưng cất theo luật, và nó ĐÁNH DẤU RÕ phần chưa chưng cất thay vì giả vờ đã xong |
| **Quyết định cần ghi vào tài liệu** | Danh sách nguồn cho phép so theo tên miền có hậu tố khớp, không so chuỗi con — `microchip.com` không được khớp `microchip.com.kho-lau.example`. Kiểm cẩu thả ở đây tệ hơn không kiểm: nó cấp cho nguồn giả mạo đúng cái vẻ chính thống mà danh sách sinh ra để bảo vệ |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §6.2 ghi rõ quy tắc so tên miền |
| **Sprint** | S3 |

## SL-16 · BỔ SUNG · `eaa/registry.py` — kho phẩm xuất

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.5, FR-DOC-01/02/03 |
| **Thiết kế nói** | Artifact Registry kèm hash, phiên bản, dòng dõi dữ liệu; phân biệt "gửi lại" và "làm mới"; hỏi rõ khi yêu cầu chưa phân định |
| **Code làm** | Thêm `eaa/registry.py`; `interpret_request()` trả `AMBIGUOUS` để nơi gọi hỏi lại |
| **Quyết định cần ghi vào tài liệu** | (1) `resend()` KIỂM BĂM trước khi trao: một tệp phát hành bị sửa sau lưng thì gửi lại nó không còn là "gửi lại bản đã nộp" mà là gửi thứ khác mang cùng tên — thà báo lỗi. (2) Chuyển đổi định dạng chỉ hỗ trợ những cặp làm được TRỌN VẸN bằng mã trong kho; cặp cần công cụ ngoài thì báo lỗi thay vì trả tệp gần đúng, vì một báo cáo mất bảng biểu vẫn mang đúng tên và đúng ngày nên sai lệch sẽ không ai phát hiện |
| **Ghi chú hiện thực** | Bộ sinh PDF viết thẳng ~40 dòng, không thêm phụ thuộc: phẩm xuất ở đây là báo cáo văn bản và bảng, và định dạng đầu ra không đổi theo phiên bản thư viện — điều đáng giá với tệp sẽ nộp kèm đề án |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §8.5 ghi rõ hai quyết định trên |
| **Sprint** | S3 |

## SL-17 · BỔ SUNG · `eaa/doctor.py` + `tools.yaml`

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9, quy trình P10, FR-ENV-01..05 |
| **Thiết kế nói** | Ba chế độ quét / sửa / tìm công cụ mới; manifest chia phần chung và phần theo pack; env_lock; Thẻ công cụ sau smoke test |
| **Code làm** | Thêm `eaa/doctor.py`, `tools.yaml` (engine) và `packs/avr/tools.yaml` (pack) |
| **Quyết định cần ghi vào tài liệu** | Lệnh kiểm tra hỗ trợ chỗ giữ `{python}` trỏ tới trình thông dịch ĐANG CHẠY engine, không phải cái đầu tiên trong PATH. Phát hiện khi chạy thật: máy có `python3` = 3.9 trong PATH nhưng engine chạy trên 3.12, và doctor báo "QUÁ CŨ" cho một môi trường hoàn toàn dùng được. Nguy hiểm hơn là chiều ngược lại — báo "đạt" cho một trình thông dịch mà cổng kiểm thử đơn vị không hề dùng tới |
| **Phạm vi CHƯA làm** | Chế độ ba của AIS §9.2 (tra cứu và đề xuất công cụ MỚI ngoài manifest) cần tìm kiếm web nên gắn với mô hình thật — Sprint 4. Hai chế độ quét và sửa đã đủ cho FR-ENV-01/02/04/05 |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §9.1 ghi rõ chỗ giữ `{python}` |
| **Sprint** | S3 |

## SL-18 · LỆCH THẬT · Mã model trong AIS §2 không tồn tại; trần token thật nhỏ hơn

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §2, quyết định #1 của MDD |
| **Thiết kế nói** | Model `gemini-pro-3.1`, ghim phiên bản, `max_output_tokens` 200.000 |
| **Thực tế đo được** | Tra danh sách model của nhà cung cấp bằng khóa thật: **không có mã nào tên `gemini-pro-3.1`**, và cũng không có mã nào chứa `pro-3`. Model Pro 3.x duy nhất sinh được văn bản là **`gemini-3.1-pro-preview`** (Gemini 3.1 Pro Preview). Trần token đầu ra thật của nó là **65.536**, không phải 200.000 |
| **Code làm** | Ghim `gemini-3.1-pro-preview`. Trần đầu ra được KẸP theo trần thật của model, tra một lần rồi nhớ |
| **AIS đã lường trước một nửa** | §2 viết "hiệu lực = min(200.000, trần thực tế của model tại thời điểm gọi)" — hóa ra không phải phòng xa. Bản adapter đầu gửi thẳng 200.000, tức gửi một con số model không nhận; đã sửa |
| **Rủi ro còn lại, cần ghi vào đề án** | `gemini-3.1-pro-preview` là bản **preview**. AIS §2 chốt ghim phiên bản để tránh rủi ro R1 (mô hình trôi phiên bản phá hỏng so sánh A/B), nhưng một bản preview vẫn có thể đổi hành vi dưới cùng một mã. Giảm thiểu đã có: mọi lời gọi được ghi vào `llm_calls.jsonl`, và `CallLog.drift()` phát hiện khi cùng một băm prompt cho hai phản hồi khác nhau. Nếu Hội đồng đòi tính tái lập chặt hơn, phương án thay thế là `gemini-2.5-pro` (bản chính thức) — đổi một dòng cấu hình |
| **Cần cập nhật** | EAA-AIS-05 §2 và MDD quyết định #1: thay mã model, ghi trần đầu ra thật, và ghi rõ rủi ro của bản preview |
| **Sprint** | S4 |

## SL-19 · BỔ SUNG · `eaa/llm/calllog.py` — nhật ký lời gọi và bộ phát lại

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §12 ("lưu prompt hash → phản hồi làm bằng chứng"), EAA-STP-04 §6 rủi ro R1 |
| **Thiết kế nói** | Nêu biện pháp giảm thiểu nhưng không cấp module |
| **Code làm** | Thêm `eaa/llm/calllog.py`: ghi mọi lời gọi, phát hiện trôi hành vi, và `ReplayClient` phát lại đúng phản hồi đã ghi |
| **Giá trị thêm** | Phát lại cho phép chạy lại trọn vòng lặp chuẩn mà không tốn lời gọi API, nên kiểm thử end-to-end chạy được cả trong CI không có khóa. Bộ phát lại KHÔNG bịa phản hồi khi thiếu bản ghi — một lượt phát lại tự sinh nội dung sẽ tạo bằng chứng giả cho Chương 3 |
| **Giới hạn phải nói rõ** | Phát lại chứng minh *quy trình xử lý đúng phản hồi ấy*, không chứng minh *mô hình hôm nay vẫn trả lời như vậy*. Hai câu khác nhau; TC-15 với khóa thật mới chứng minh câu sau |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §12 ghi rõ cơ chế |
| **Sprint** | S4 |

## SL-20 · BỔ SUNG · Nạp cấu hình từ `.env`

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 NFR-06 |
| **Thiết kế nói** | "API key lưu qua biến môi trường; không ghi key ra log" |
| **Code làm** | `eaa/cli.py::load_env_file()` nạp `.env` vào `os.environ` lúc khởi động |
| **Vì sao không nới lỏng NFR-06** | Adapter mô hình vẫn chỉ đọc `os.environ` và không biết tệp nào tồn tại. `.env` nằm trong `.gitignore`, và có test đỏ nếu ai gỡ dòng ignore. Biến đã đặt trong shell luôn THẮNG giá trị trong tệp. Hàm nạp trả về TÊN biến, không trả giá trị — danh sách ấy có thể đi vào log |
| **Cần cập nhật** | EAA-SRS-01 NFR-06: ghi nhận `.env` là chỗ nạp được phép, kèm ba điều kiện trên |
| **Sprint** | S4 |

## SL-21 · BỔ SUNG · `eaa/versions.py` — ba hạng chất lượng và bản known-good

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.4, FR-VER-01/02 |
| **Thiết kế nói** | Ba hạng build-ok < sim-verified < hw-verified; `known_good.lock` chỉ cập nhật tại G4; `eaa rollback` một lệnh |
| **Code làm** | Thêm `eaa/versions.py` |
| **Bổ sung so với thiết kế** | Hạng `hw-verified` đòi CÓ SỐ ĐO đi kèm, không chỉ đòi chữ ký G4. Hạng này khẳng định một điều về thiết bị thật; một lần phong không kèm số đo là một khẳng định không có bằng chứng, và nó sẽ nằm trong `known_good.lock` như thể đã được chứng minh |
| **Bổ sung thứ hai** | Tách `reject_acceptance` khỏi `rollback`. Ghi nhận thất bại và quay lui là hai việc: kỹ sư có thể quyết định sửa tiếp thay vì lùi, và bản ghi thất bại phải tồn tại trong cả hai trường hợp |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §8.4 ghi rõ hai điều trên |
| **Sprint** | S4 |

## SL-22 · BỔ SUNG · `eaa/diagnostics.py` — chẩn đoán hai kênh

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7, quy trình P8, FR-DIA-01/02/03 |
| **Thiết kế nói** | Hai kênh quan sát, thư viện DS-01..06, ma trận chẩn đoán, nạp bán tự động có xác nhận |
| **Code làm** | Thêm `eaa/diagnostics.py` (khung tổng quát) + `projects/robot_balance/diagnostics.yaml` (dữ liệu dự án) |
| **Bổ sung so với thiết kế** | Engine TỪ CHỐI kết luận khi kịch bản đòi quan sát của người mà chưa có. AIS mô tả phép giao hai kênh nhưng không nói rõ phải làm gì khi thiếu một kênh; im lặng kết luận trên nửa dữ liệu vẫn phát ra với vẻ chắc chắn y hệt, và sẽ dẫn kỹ sư đi sửa nhầm chỗ |
| **Bổ sung thứ hai** | Tổ hợp hai kênh chưa có trong ma trận thì trả "chưa kết luận được" kèm đề nghị bổ sung một dòng — phiên chẩn đoán cũng là phiên nạp tri thức (AIS §7.3) |
| **Cần cập nhật** | EAA-SDD-03 §2 và §4; EAA-AIS-05 §7.4 ghi rõ hai điều trên |
| **Sprint** | S4 |

## SL-23 · LỆCH THẬT · Trần thời gian chờ mô hình 120s quá ngắn

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §6 |
| **Thiết kế nói** | `LLMClient.generate`: timeout 120s |
| **Đo được** | Model Pro lớp suy luận sinh một module ~250 dòng có lúc vượt 120s. Một lần quá hạn làm hỏng cả lượt chạy vốn sắp xong, và ba lần thử lại tốn 6 phút mà vẫn hỏng |
| **Code làm** | Mặc định 300s, cấu hình qua `EAA_LLM_TIMEOUT_S` |
| **Cần cập nhật** | EAA-SDD-03 §6: đổi trần và ghi rõ đây là tham số vận hành, không phải khẳng định thiết kế |
| **Sprint** | S4 |

## SL-24 · BỔ SUNG · Lỗi cấu hình không đi vào vòng tự sửa

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-GEN-01, EAA-AIS-05 §3.2 |
| **Thiết kế nói** | Cổng kiểm chứng báo hỏng → mở vòng tự sửa, tối đa N lần |
| **Phát hiện khi chạy thật** | Cổng phân tích tĩnh báo "constraints cấm X nhưng pack không có luật phát hiện". Đó là lỗi CẤU HÌNH, không phải lỗi mã — nhưng vòng tự sửa vẫn khởi động và mô hình trả về văn xuôi vì trong mã chẳng có gì để sửa |
| **Code làm** | Báo cáo cổng gắn cờ `config_error`; Orchestrator dừng ngay như với `env_error`, không mở vòng vá |
| **Vì sao đáng ghi** | Ba vòng vá cho một thứ mô hình không thể sửa vừa đốt lượt gọi vừa gần như chắc chắn làm hỏng mã đang đúng. Giới hạn N chặn được thiệt hại, nhưng tốt hơn là không bắt đầu |
| **Cần cập nhật** | EAA-SRS-01 FR-GEN-01: phân biệt lỗi mã (vào vòng vá) với lỗi môi trường và lỗi cấu hình (dừng, chuyển người) |
| **Sprint** | S4 |

## SL-25 · BỔ SUNG · Ràng buộc `blocking_io` cho dự án mẫu

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §3.1 (`constraints.yaml`) |
| **Thiết kế nói** | `forbidden` gồm bốn mục: `delay()`, `malloc/new`, `recursion`, `float_in_isr` |
| **Phát hiện khi chạy thật** | Bản sinh đầu tiên của driver bus có ba vòng `while (!(REG & bit)) {}` không lối thoát. Mã ấy qua sạch cả bốn cổng — vì cổng static chỉ chặn được thứ nó ĐƯỢC BẢO là cấm. Pack AVR vốn đã có luật `blocking_io`, nhưng dự án không liệt kê nên luật không được áp; và mẫu nhận dạng của luật ấy cũng chỉ khớp dạng `);`, bỏ lọt đúng dạng `) {}` mà mô hình sinh ra |
| **Code làm** | Thêm `blocking_io` vào `forbidden`; sửa mẫu nhận dạng bắt cả hai dạng thân rỗng; nâng mức từ cảnh báo lên lỗi |
| **Kết quả quan sát được** | Sinh lại dưới ràng buộc đã siết, mô hình đổi hẳn kiến trúc: từ vòng chờ chặn sang máy trạng thái không chặn. Một dòng ràng buộc đổi kiến trúc mã sinh ra — đáng đưa vào Chương 3 |
| **Cần cập nhật** | EAA-SDD-03 §3.1: bổ sung mục thứ năm vào ví dụ `forbidden` |
| **Sprint** | S4 |

---

## SL-26 · BỔ SUNG · `eaa/toolsearch.py` — tự tìm công cụ chưa biết

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.2 (chế độ "Tìm công cụ mới"), §9.1, §9.4; FR-ENV-03 |
| **Thiết kế nói** | `eaa doctor` có ba chế độ; chế độ ba đề xuất công cụ mới, đề xuất qua gate rồi mới vào manifest, nguồn cài giới hạn ở trình quản lý gói chính thống hoặc miền cho phép kèm checksum |
| **SDD nói** | EAA-SDD-03 v1.0 không có module nào cho chế độ ba — `eaa/doctor.py` chỉ phủ hai chế độ đầu |
| **Code làm** | Thêm `eaa/toolsearch.py`: `derive_requirements()` suy nhu cầu từ `pack.yaml`; `LlmToolResearcher` tra cứu bằng mô hình nền; `validate_proposal()` kiểm nguồn cài; `append_to_manifest()` ghi append + supersede. `Doctor.discover()/research()`, cờ `--discover/--propose`, và nhánh ghi manifest sau khi duyệt G2 |
| **Lý do** | Nhu cầu công cụ đã nằm sẵn trong `pack.yaml` — phần tử đầu của mỗi `command`. Chép lại danh sách ấy vào manifest là dựng nguồn sự thật thứ hai, và nó lệch ngay lần đầu pack đổi lệnh, theo hướng nguy hiểm: doctor báo "đủ công cụ" trong khi cổng kiểm chứng sắp gọi một chương trình không có |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/toolsearch.py` vào cây module và mô tả đường đi phát hiện → tra cứu → G2 → manifest |
| **Sprint** | S4 |

---

## SL-27 · LỆCH THẬT · Manifest công cụ bị chép sẵn bằng tay

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.1 ("Tool Manifest là một kho tri thức, mọi thay đổi qua gate"), §9.2 |
| **Thiết kế nói** | Manifest ghi những công cụ đã được duyệt; nhu cầu thì suy từ pack |
| **Code trước đó làm** | `packs/avr/tools.yaml` được viết tay sẵn ba mục `avr-gcc`, `avr-size`, `avrdude`; `tools.yaml` của engine viết tay thêm `cppcheck` |
| **Phát hiện khi chạy thật** | Không có gì hỏng — và đó chính là vấn đề: manifest viết tay trông y hệt manifest đã qua gate. Không có cách nào phân biệt "công cụ này đã được xác nhận cách kiểm và cách cài" với "ai đó gõ vào đây". `cppcheck` còn nằm sai tầng: pack AVR gọi nó kèm `--platform=avr8`, nhưng nó được khai ở manifest engine, nên mọi dự án đều bị đòi nó kể cả dự án dùng nền khác |
| **Code làm** | Xóa cả bốn mục viết tay; chúng đi lại đường chính quy `--discover --propose` → G2 → manifest, và mang theo `approved_by`/`approved_at`. Một test khóa lại: mục nào trong manifest của pack không có dấu vết người duyệt thì hỏng |
| **Kết quả quan sát được** | Mô hình đề xuất `avr-gcc ≥7.3`, còn `pack.yaml` khai `>=12.0`. Hai con số khác nhau, và nếu lấy theo mô hình thì doctor sẽ chấp nhận một toolchain mà pack không chạy nổi. `derive_requirements()` vì thế lấy ràng buộc phiên bản theo pack — pack là tài liệu đã qua G1, đề xuất của mô hình chỉ là tri thức tra cứu |
| **Cần cập nhật** | EAA-AIS-05 §9.1: nói rõ mục manifest bắt buộc mang `approved_by`/`approved_at`, và ràng buộc phiên bản của pack đè lên đề xuất |
| **Sprint** | S4 |

---

## SL-28 · LỆCH THẬT · Adapter mô hình chỉ có một lối gọi, và nó đòi khối `file:`

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §5 (giao diện `LLMClient`) |
| **Thiết kế nói** | `LLMClient.generate(prompt) -> CodeArtifact` |
| **Phát hiện khi chạy thật** | `eaa doctor --discover --propose` hỏng cho cả ba công cụ: *"Phản hồi không chứa khối ```file:<đường dẫn> nào"*. Mô hình trả lời đúng — một khối JSON như prompt yêu cầu — nhưng `generate()` luôn chạy `parse_file_blocks()`, nên mọi phản hồi đúng đắn của một câu hỏi KHÔNG PHẢI sinh mã đều bị tính là hỏng định dạng |
| **Code làm** | Thêm `complete(prompt) -> str` cho cả ba adapter (`GeminiClient`, `MockLLM`, `ReplayClient`); `generate()` và `complete()` dùng chung một đường gọi, chỉ khác ở chỗ có bóc khối tệp hay không |
| **Lý do** | Không phải mọi lời gọi mô hình đều là sinh mã. Tra cứu công cụ, và sau này phân loại lỗi hay phân tích số đo tại G4, đều là câu hỏi văn xuôi. Một giao diện chỉ có `generate()` buộc chúng phải giả trang thành sinh mã |
| **Cần cập nhật** | EAA-SDD-03 §5: giao diện `LLMClient` có hai phương thức |
| **Sprint** | S4 |

---

## SL-29 · LỆCH THẬT · Lệnh dịch của pack liên kết luôn, nên mọi module đều trượt

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 (Tool Layer), EAA-SRS-01 FR-VER-01 |
| **Thiết kế nói** | Chuỗi kiểm chứng bắt đầu bằng biên dịch → đo kích thước; pack khai báo năng lực `compile` |
| **Code trước đó làm** | `packs/avr/pack.yaml` khai `compile` với `-o {output}` mà không có `-c`, kèm cả cờ `-Wl,--gc-sections` — tức là một lệnh **dịch và liên kết** |
| **Phát hiện khi chạy thật** | Liên kết đòi `main()`, mà một module driver không có và không cần có. Mọi module sinh ra sẽ trượt cổng đầu tiên với *undefined reference to main* — trượt vì một lý do chẳng liên quan gì tới chất lượng mã. Lỗi này không lộ suốt bốn sprint vì máy phát triển chưa cài `avr-gcc`: cổng "không đạt vì thiếu công cụ" che mất "không đạt vì lắp lệnh sai" |
| **Code làm** | Tách thành ba năng lực: `compile` (`-c`, một tệp nguồn → một tệp đối tượng), `link` (các tệp đối tượng + `main()` → ảnh ELF), `hex` (ELF → định dạng nạp được). `CompileGate` dịch từng nguồn rồi gộp báo cáo; thêm `LinkGate`; `SizeGate` đo được nhiều tệp và cộng số liệu |
| **Hệ quả cho cổng đo kích thước** | Ở tầm module nó đo chiếm dụng của chính module ấy, số của cả firmware chỉ có sau khi liên kết. Báo cáo ghi `size_scope` để người đọc thấy trần "Flash < 50%" đang áp lên cái gì |
| **Kết quả quan sát được** | `avr-objcopy` là chương trình mới, và `eaa doctor --discover` phát hiện ra nó ngay mà không ai khai báo — đúng điều SL-27 dựng ra: đổi pack thì nhu cầu công cụ tự đổi theo |
| **Cần cập nhật** | EAA-SDD-03 §2: Tool Layer có `LinkGate`; danh sách năng lực của pack thêm `link`, `hex` |
| **Sprint** | S4 |

---

## SL-30 · LỆCH THẬT · Gộp báo cáo đánh rơi cờ lỗi môi trường

| | |
|---|---|
| **Tài liệu** | SL-24 (lỗi cấu hình không đi vào vòng tự sửa) |
| **Phát hiện khi chạy thật** | Ngay khi tách cổng dịch: cổng dịch giờ chạy nhiều lượt và gộp kết quả, mà bản gộp đầu tiên dựng `ToolReport` mới **không mang theo `metrics`**. Cờ `env_error` biến mất, Orchestrator tưởng là lỗi mã, và gửi mô hình vá ba lần một thứ mô hình không sửa được. TC-15 bắt được ngay trong lượt chạy đầu |
| **Code làm** | `_gop_bao_cao` gộp `metrics`; riêng `env_error` và `config_error` được **HỢP** qua các lượt chứ không lấy theo lượt cuối — một lượt hỏng vì môi trường là cả cổng hỏng vì môi trường |
| **Điều rút ra** | Bất biến SL-24 nằm trong một trường dữ liệu, nên bất kỳ chỗ nào dựng lại `ToolReport` đều có thể lặng lẽ phá nó. Đã thêm test đơn vị riêng cho phép gộp thay vì chỉ dựa vào test end-to-end |
| **Sprint** | S4 |

---

## SL-31 · BỔ SUNG · `eaa/firmware.py` — ráp module đã merge thành firmware

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-VER-01, EAA-SDD-03 §2, công đoạn E của máy trạng thái |
| **Thiết kế nói** | Vòng lặp chuẩn kiểm từng module qua bốn cổng, rồi merge |
| **Chỗ trống** | Bốn cổng nói *từng mảnh* đúng. Không cổng nào nói rằng các mảnh ghép lại thì chạy — mà thứ nạp xuống mạch là bản đã ghép. SDD v1.0 không có module nào cho công đoạn ráp |
| **Code làm** | Thêm `eaa/firmware.py`: `AssemblyPlan` (đọc `firmware.yaml` ở tầng dự án), `FirmwareAssembler` (sinh vòng lặp chính từ khuôn của pack → dịch mọi module + main → liên kết → ảnh nạp được → đo lại kích thước). Thêm lệnh `eaa build`. `PackManifest` thêm mục `firmware` (`FirmwareTemplates`) |
| **Ranh giới ba tầng** | Khuôn vòng lặp chính nằm ở **pack**, không ở engine: nguồn xung nhịp, cú pháp ngắt, cách bật bộ định thời đều là chuyện của nền tảng. Engine chỉ thay chỗ giữ, và ngay cả ba dòng mẫu (`include_line`, `init_line`, `task_line`) cũng do pack cấp — nếu engine tự sinh câu lệnh C thì ranh giới TC-38 canh sẽ mờ dần từ đúng chỗ đó |
| **Bất biến mới** | Module đã merge mà vắng mặt trong bản thiết kế ráp là **lỗi**, không phải cảnh báo. Merge nghĩa là mã ấy đã qua đủ cổng và đã được duyệt tại G3; bỏ quên nó thì firmware thiếu một phần mà mọi bằng chứng đều nói là có. Module chỉ để module khác gọi thì khai `step: null` — nói ra thì được, im lặng thì không |
| **Hệ quả cho ngưỡng bộ nhớ** | Đây là lần đầu `flash_pct_max` được đo trên **cả firmware**. Ở vòng kiểm module, một module chiếm 20% thì "dưới 50%" nghe như đạt, trong khi mười module như thế thì không — con số ở tầm module luôn dễ dãi hơn |
| **Điểm còn hở** | Chu kỳ chạy của mỗi module là quyết định vật lý (đến từ động lực học của đối tượng), nên nó được KHAI BÁO trong `firmware.yaml` chứ không suy từ mã. Máy đọc được tên hàm trong tệp tiêu đề, không đọc được rằng con lắc ngược cần 10 ms |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/firmware.py` và `firmware.yaml` vào cây thư mục; §2 mô tả công đoạn ráp; danh sách lệnh CLI thêm `eaa build` |
| **Sprint** | S4 |

---

## SL-32 · BỔ SUNG · `eaa/serialport.py` — liệt kê cổng, nhận diện mạch

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (kênh máy của chẩn đoán hai kênh), FR-DIA-02 |
| **Chỗ trống** | SDD v1.0 không có module nào cho việc tìm thiết bị. Chẩn đoán hai kênh giả định telemetry "có sẵn", nhưng ai nối dây và nối vào đâu thì không nói |
| **Code làm** | `list_ports()` (pyserial nếu có, không thì glob theo quy ước POSIX), `UsbId`/`match_declared()` đối chiếu với danh sách bo dự án khai, `eaa ports` |
| **Ranh giới ba tầng** | Cặp VID/PID nằm ở **tầng dự án** (`hardware_profile.yaml → programmer.usb`), không ở pack và càng không ở engine: cầu USB-nối tiếp là thuộc tính của cái bo cụ thể đang nằm trên bàn, không phải của họ vi điều khiển. Cùng một MCU có thể nằm trên bo dùng cầu này hay cầu khác |
| **Nguyên tắc trung thực** | Không có `pyserial` thì không đọc được VID/PID, và lúc ấy báo cáo nói thẳng "không đọc được" thay vì trả danh sách trông y hệt trường hợp đọc được rồi để người tưởng mạch không khớp. Một dòng "không nhận diện được" đúng đáng hơn một dòng "không khớp" sai |
| **TC-38 bắt được một lần** | Docstring của `UsbId._chuan` lấy mã một hãng làm ví dụ — đúng cái bẫy đã bắt bốn lần ở các sprint trước. Đã viết lại tổng quát. TC-42 thêm một phép kiểm hẹp hơn: quét riêng `serialport.py` tìm mã hãng |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/serialport.py`; `hardware_profile.yaml` thêm mục `programmer` |
| **Sprint** | S4 |

---

## SL-33 · BỔ SUNG · `eaa/flash.py` — nạp firmware và nhật ký nạp

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-DIA-02, EAA-AIS-05 §7.3 |
| **Thiết kế nói** | Nạp firmware LUÔN cần người xác nhận |
| **Chỗ trống** | Điều khoản ấy đã được thi hành ở tầng pack (`flash` phải khai `requires_confirmation`) nhưng chưa có đường nào từ CLI tới đó: trường `DiagnosticSession.flasher` chưa nơi nào gán |
| **Code làm** | `Flasher` (bốn phép kiểm + xác nhận), `FlashLog` append-only, lệnh `eaa flash` và `eaa flash --history` |
| **Bốn phép kiểm, đều là "không" chứ không phải "cảnh báo"** | (1) có ảnh đã ráp; (2) kho mã sạch — còn thay đổi chưa commit thì câu "đã nạp commit X" là câu sai, và sai lệch ấy đi theo tới lúc bảo vệ; (3) ảnh mới hơn nguồn — nạp ảnh cũ là cách hỏng âm thầm nhất vì mạch chạy mã cũ còn người đọc mã mới; (4) người xác nhận, phiên không có terminal tính là chưa xác nhận |
| **Ghi cả lần trượt** | "Đã thử nạp và trượt" là dữ kiện chẩn đoán y như "đã nạp xong" |
| **Engine không đoán cổng** | Nhận ra đúng một cổng thì tự chọn; không nhận ra, hoặc nhận ra nhiều, thì dừng và đòi `--port`. Nạp nhầm thiết bị là hỏng thật, không phải một lượt chạy lại |
| **Lỗi phát sinh và cách sửa** | `eaa build` ghi vào `firmware/build/`, nên `has_changes()` luôn đúng và phép kiểm "kho sạch" sẽ chặn MỌI lần nạp. Đã loại `build/` qua `.git/info/exclude` (loại trừ cục bộ, không cần commit vào một kho đang ở giữa nhánh module). Một phép kiểm luôn báo động là một phép kiểm sẽ bị tắt |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/flash.py`, `flash_log.jsonl`, lệnh `eaa ports` và `eaa flash` |
| **Sprint** | S4 |

---

## SL-34 · BỔ SUNG · `eaa/telemetry.py` — kênh máy đọc thẳng từ mạch

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (chẩn đoán hai kênh), FR-DIA-01 |
| **Thiết kế nói** | Chẩn đoán là phép GIAO của kênh máy (telemetry) và kênh người (quan sát) |
| **Chỗ trống** | Kênh người đã có từ Sprint 4. Kênh máy vẫn đọc từ MỘT TỆP — nghĩa là ai đó phải tự nối dây, tự bắt log, tự dán vào tệp. Đoạn "tự" ấy nằm ngoài mọi bằng chứng của hệ thống |
| **Code làm** | `FrameSpec` (định dạng khung do dự án khai), `verify_frame`, `SerialTelemetryReader`, `Capture`, `read_capture`; lệnh `eaa telemetry`; `eaa diagnose run --port` đọc thẳng từ mạch |
| **Ba bất biến** | (1) **Luôn có hạn thời gian** — đọc không hạn sẽ treo mãi khi mạch câm, và "treo" trông giống hệt "đang đo"; (2) **khung hỏng được ĐẾM, không bị nuốt** — tỉ lệ vượt ngưỡng thì cả phiên bị coi là không tin được; (3) **giữ nguyên văn** — bản thô nằm cạnh bản đã lọc, phát lại được không cần mạch, cùng nguyên tắc với `ReplayClient` |
| **Vì sao (2) là mục quan trọng nhất** | Một phiên 40% khung hỏng vẫn cho ra vài con số trông hoàn toàn hợp lý. Sai tốc độ truyền, dây dài quá, nguồn sụt khi động cơ chạy — cả ba biểu hiện như vậy, và cả ba sẽ đi thẳng vào Chương 3 nếu khung hỏng bị bỏ lặng lẽ. Nên `eaa diagnose run --port` TỪ CHỐI kết luận trên một phiên không tin được |
| **Lỗi đã mắc và đã sửa** | Cửa sổ ổn định (`settle_ms`, bỏ rác lúc bo tự khởi động lại khi mở cổng) ban đầu bỏ theo THỜI GIAN, nên một nguồn dữ liệu nhanh bị vứt sạch kể cả khung hợp lệ. Nay nó chỉ bỏ khung KHÔNG kiểm được: một khung đạt đã là dữ liệu thật, vứt nó chỉ vì nó tới sớm là mất đúng thứ đang cần đo |
| **Ranh giới ba tầng** | Engine chỉ biết một quy ước: mỗi khung một dòng, phần tải là JSON — đúng thứ `parse_telemetry` vốn đã đọc. Checksum gắn kiểu gì, tốc độ truyền bao nhiêu nằm ở `diagnostics.yaml` của dự án |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/telemetry.py`, lệnh `eaa telemetry`; `diagnostics.yaml` thêm mục `telemetry`; EAA-AIS-05 §7 nói rõ ngưỡng tin cậy của một phiên thu |
| **Sprint** | S4 |

---

## SL-35 · BỔ SUNG · Sinh firmware chẩn đoán — lấp trường `firmware_template`

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7.2, FR-DIA-01 |
| **Thiết kế nói** | Mỗi kịch bản chẩn đoán có `firmware_template` — mẫu firmware đo dùng để sinh |
| **Chỗ trống** | Trường ấy được khai trong lược đồ `Scenario` và được nạp từ YAML từ Sprint 4, nhưng **chưa nơi nào dùng**. Kịch bản chẩn đoán vì thế chỉ chạy được nếu người tự viết lấy firmware đo |
| **Code làm** | `DiagnosticFirmwareBuilder` trong `eaa/firmware.py`; `DiagnosticTemplates` trong `eaa/platform.py`; bộ khung `packs/avr/templates/diagnostic.c.tmpl`; phần đo `projects/robot_balance/diagnostics/DS-01.c` và `DS-04.c`; lệnh `eaa diagnose build` |
| **Ba tầng** | **Pack** giữ bộ khung (bật UART, đóng gói khung telemetry, gọi `diag_run()`). **Dự án** giữ phần đo của từng kịch bản — nó biết bus nào, địa chỉ nào, thanh ghi nào. **Engine** ghép hai tệp bằng cách LIÊN KẾT, không dán chuỗi: cả hai đều là mã C thật nên bộ dịch kiểm được cả hai |
| **Bất biến** | Kịch bản chưa khai phần đo thì DỪNG, không dựng một firmware rỗng. Một ảnh nạp được mà không đo gì sẽ chạy, sẽ im lặng, và sự im lặng ấy không phân biệt được với "mạch hỏng" — sinh bừa một ảnh để lệnh có vẻ thành công là cách nhanh nhất biến công cụ chẩn đoán thành nguồn kết luận sai |
| **An toàn** | Ảnh chẩn đoán đi kèm một thẻ `.meta.json` ghi kịch bản, cờ `motion` và checklist an toàn. `eaa flash` đọc thẻ và đưa checklist ra **đúng lúc người sắp bấm đồng ý** — giữa lúc dựng ảnh và lúc nạp có thể là vài ngày, và một ảnh làm robot chuyển động trông y hệt một ảnh đo tĩnh |
| **Vòng khép kín được kiểm bằng bộ dịch thật** | TC-44 dịch bộ khung + phần đo bằng `cc`, chạy nó, rồi cho chính `eaa/telemetry.py` bóc đầu ra. Bộ sinh mã và bộ đọc do hai tệp khác nhau giữ, nên chỉ chạy thật mới biết checksum bên này tính có khớp bên kia kiểm |
| **Phạm vi đã làm** | 2/6 kịch bản có phần đo (DS-01 quét bus, DS-04 tự kiểm kênh telemetry). Bốn kịch bản còn lại vẫn báo rõ "chưa khai phần đo" thay vì im lặng |
| **Cần cập nhật** | EAA-SDD-03: `DiagnosticFirmwareBuilder`, mục `diagnostics` của pack, thư mục `projects/*/diagnostics/`, lệnh `eaa diagnose build` |
| **Sprint** | S4 |

---

## SL-36 · BỔ SUNG · `eaa/acceptance.py` — khép vòng số đo tới hạng `hw-verified`

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.4 (ba hạng chất lượng), FR-VER-01, UC07 |
| **Thiết kế nói** | Hạng `hw-verified` đòi phê duyệt G4 và đòi có SỐ ĐO đi kèm |
| **Chỗ trống** | Bất biến ấy đã được thi hành từ Sprint 4, nhưng "số đo" là một tệp `measures.yaml` người tự gõ — và một tệp tự gõ thì khẳng định được bất cứ điều gì. Không có mắt xích nào nối số đo với thiết bị |
| **Code làm** | `MeasurementSpec`/`AcceptanceSpec` (khai trong `constraints.yaml → acceptance.measurements`), `derive_measurements()`, `check_device_commit()`; `eaa tune --port` thu telemetry rồi rút số đo |
| **Chốt 1 — bất biến mới, và là lý do cả bước này tồn tại** | Commit sắp phong hạng phải là commit **đang chạy trên thiết bị**, đối chiếu với nhật ký nạp. Không có nó, quy trình cho phép: nạp bản A, đo bản A, sửa mã thành bản B, rồi phong `hw-verified` cho B. Bản B chưa bao giờ chạy trên phần cứng — nhưng `known_good.lock` sẽ nói ngược lại, và đó là thứ mọi lần quay lui về sau tin theo. Một lần nạp TRƯỢT cũng không tính là bằng chứng |
| **Sửa ngay trong bước: "thiếu bằng chứng" ≠ "bằng chứng nói ngược lại"** | Bản đầu tiên chặn cả hai như nhau, và TC-15 đỏ ngay: ba bài end-to-end phong hạng bằng `--input` mà chưa từng chạy `eaa flash`. Đó là một luồng hoàn toàn hợp lệ — kỹ sư nạp bằng IDE hay công cụ của hãng. Nhật ký nói bản A đang trên chip mà ta phong cho B là **mâu thuẫn** → chặn; nhật ký trống là **engine không biết** → nói rõ mình không kiểm được, ghi `device_verified=false` vào bản ghi phong hạng, rồi để người quyết. Một phép kiểm chặn cả việc đúng lẫn việc sai là phép kiểm sẽ bị gỡ |
| **Chốt 2** | Số đo đã khai mà telemetry không có là **lỗi**, không phải "bỏ qua mục ấy". Một bản ghi nghiệm thu có 2 trong 4 số đo trông y hệt một bản có đủ 4 |
| **Chốt 3** | Vượt ngưỡng thì KHÔNG phong hạng; đường đi của kết quả không đạt là `eaa tune --reject`. Số đo không đạt vẫn được giữ để vào bản ghi từ chối |
| **Tiêu chí có trước số đo** | `acceptance.measurements` phải khai trước; chưa khai thì engine từ chối rút số đo thay vì tự đoán khóa nào là số đo. Nghiệm thu là đối chiếu hành vi thật với ngưỡng đã chốt từ công đoạn A1 — ngưỡng viết sau khi nhìn số thì phép đối chiếu không còn nghĩa gì |
| **Một nguồn sự thật cho mỗi ngưỡng** | Test khóa lại: `max_tilt_deg.max` phải bằng `acceptance.tilt_tolerance_deg`, `loop_period_ms.max` phải bằng `limits.control_loop_ms`. Hai nguồn cho cùng một ngưỡng sẽ lệch nhau ở lần sửa đầu tiên |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/acceptance.py`, mục `acceptance.measurements` của `constraints.yaml`, cờ `--port/--seconds/--out` của `eaa tune`; EAA-AIS-05 §8.4 nói rõ điều kiện "commit phải đang chạy trên thiết bị" |
| **Sprint** | S4 |

---

## SL-37 · BỔ SUNG · `eaa/options.py` — cổng quyết định, không chỉ cổng duyệt

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-GATE-01, EAA-SAD-02 ADR-04, EAA-AIS-05 §3 |
| **Thiết kế nói** | Năm Human Gate: con người phê duyệt hoặc từ chối |
| **Chỗ trống** | Câu nhị phân ấy đúng cho G3 (review diff) và G4 (nghiệm thu) — ở đó có đúng một vật thể để chấp nhận hay bác bỏ. Nhưng ở chỗ có **nhiều cách làm đều đúng** (chọn kiến trúc tại G1, chọn hướng đi khi vòng tự sửa cạn N lần), một nút "duyệt" buộc con người duyệt cái Agent đã tự chọn — và lựa chọn thật sự đã xảy ra trước đó, ở chỗ không ai nhìn thấy |
| **Code làm** | `Option`/`OptionSet`/`LlmOptionProposer` trong `eaa/options.py`; `GatePayload.options`, `GateDecision.chosen_option` + `.options`; `HumanGate.approve(..., option=)`; lệnh `eaa decide` và cờ `eaa gate approve --option` |
| **Bất biến 1 — đủ hai phương án** | Một "lựa chọn" có đúng một mục là quyết định đã có sẵn, chỉ khoác áo lựa chọn. Nó tệ hơn không có lựa chọn, vì tạo cảm giác đã cân nhắc |
| **Bất biến 2 — phải nói mặt trái** | Phương án thiếu `cons` bị từ chối ngay khi dựng. Danh sách chỉ toàn ưu điểm không giúp ai chọn được gì; nó chỉ chuyển trách nhiệm sang người bấm nút |
| **Bất biến 3 — gợi ý không phải mặc định** | Có phương án thì `approve` ĐÒI một mã, và engine **không** lấy phương án được gợi ý làm mặc định. Nếu lấy, lựa chọn thật sự lại quay về chỗ không ai nhìn thấy — đúng vấn đề cả bước này dựng ra để tránh |
| **Bất biến 4 — phương án bị loại vẫn lưu** | Quyết định mang cả tập, kể cả những cái bị loại và lý do. Sáu tháng sau, câu hỏi hữu ích không phải "ta đã chọn gì" — Git trả lời được — mà là "ta đã cân nhắc những gì và vì sao loại chúng". Từ chối cả tập cũng được lưu, để lần sau khỏi đề xuất lại y hệt |
| **Bất biến 5 — băm phủ cả phương án** | Đổi tập phương án sau khi trình lên là đổi chính câu hỏi người đang trả lời, nên `payload.digest` tính cả chúng |
| **Đề xuất của mô hình là proposed fact** | `LlmOptionProposer` đi qua **cùng cửa kiểm** với phương án viết tay. Prompt cấm mô hình tự quyết định và buộc nêu mặt trái thật sự; đề xuất thiếu `cons` hoặc chỉ có một phương án bị chặn ngay |
| **Chạy thật** | Mô hình nêu ba cách đọc cảm biến khác nhau về bản chất (hỏi vòng / ngắt / DMA+timer), mỗi cách 2–3 mặt trái cụ thể, gợi ý một cách kèm lý do. `eaa gate approve G1` không kèm `--option` bị chặn đúng như thiết kế |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/options.py`, lệnh `eaa decide`, cờ `--option`; EAA-SAD-02 ADR-04 nói rõ gate có hai dạng — nhị phân và nhiều phương án |
| **Sprint** | S4 |

---

## SL-38 · BỔ SUNG · `packs/stm32/` — pack thứ hai, và NFR-05 từ lập luận thành bằng chứng

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 NFR-05, EAA-SAD-02 ADR-09 |
| **Thiết kế nói** | Thêm một họ MCU = thêm `packs/<tên>/`, KHÔNG sửa engine |
| **Chỗ trống** | Với đúng một pack, câu ấy không kiểm được: "engine tổng quát" và "engine viết riêng cho pack ấy" trông giống hệt nhau |
| **Code làm** | `packs/stm32/` (Cortex-M4F, toolchain `arm-none-eabi-*`, nạp qua `st-flash`), gồm mã khởi động + bảng vector + kịch bản liên kết + hai khuôn; `projects/disco_f469/` cho bo STM32F469I-DISCO trên bàn |
| **Kết quả** | Thêm pack KHÔNG thêm một nhánh rẽ nào trong `eaa/` — TC-47a quét và khóa điều này. Nhưng nó LÀM LỘ RA hai tham số interface còn thiếu, và đó mới là phát hiện đáng giá |
| **Tham số thứ nhất** | **Đuôi ảnh nạp được.** AVR dùng Intel HEX, STM32 dùng ảnh nhị phân thô. Đuôi `.hex` từng là hằng số trong engine |
| **Tham số thứ hai** | **Tệp nguồn do pack cấp.** ARM bare-metal cần mã khởi động và bảng vector; AVR thì bộ dịch kèm sẵn. Engine trước đó giả định firmware chỉ gồm module của dự án cộng `main.c` |
| **Điều rút ra** | Cả hai đi vào INTERFACE, không đi vào engine dưới dạng `if pack.name == ...` — đúng điều `eaa/platform.py` dặn ngay ở đầu tệp. Một pack thứ hai là cách rẻ nhất để tìm ra chỗ interface còn thiếu |
| **Cần cập nhật** | EAA-SDD-03: `FirmwareTemplates.image_suffix`, `.sources`; EAA-SRS-01 NFR-05 dẫn TC-47 làm bằng chứng |
| **Sprint** | S4 |

---

## SL-39 · LỆCH THẬT · Khớp cổng theo TÊN được coi ngang với khớp theo VID/PID

| | |
|---|---|
| **Tài liệu** | SL-32 (`eaa/serialport.py`), FR-DIA-02 |
| **Phát hiện khi chạy thật** | Cắm cùng lúc bo STM32F469I-DISCO và một bo AVR dùng cầu CH340. Dự án AVR khai `port_hint: usbmodem` — gợi ý ấy khớp trúng cổng ST-LINK của bo STM32, và vì "đúng một cổng khớp" nên `_chon_cong` **TỰ CHỌN** nó. Engine khi ấy sẵn sàng nạp firmware AVR vào một bo ARM |
| **Vì sao không test nào bắt được** | Lỗi chỉ tồn tại khi có HAI thiết bị thật trên bàn. Mọi test trước đó dựng một bo |
| **Code làm** | `SerialPort.match_confirmed` phân biệt khớp bằng VID/PID (chắc chắn) với khớp bằng tên cổng (phỏng đoán). `_chon_cong` chỉ tự chọn khi danh tính ĐÃ XÁC NHẬN; khớp theo tên thì dừng và đòi `--port`, kèm gợi ý cài `pyserial` để đọc được VID/PID |
| **Sửa thêm** | `port_hint` của dự án mẫu đổi từ `usbmodem` sang `usbserial` — bo AVR thật trên bàn dùng cầu CH340 nên hệ điều hành đặt tên khác. Một gợi ý tên sai không báo lỗi, nó chỉ trỏ sang nhầm thiết bị |
| **Điều rút ra** | Bản báo cáo vốn đã ghi rõ "chưa xác nhận VID/PID" — tức là phần TRUNG THỰC đã đúng, nhưng phần HÀNH ĐỘNG vẫn đối xử với phỏng đoán như với sự thật. Nói đúng chưa đủ; phải hành động theo đúng mức tin cậy mình vừa nói |
| **Sprint** | S4 |

---

## SL-40 · LỆCH THẬT · Mặc định `mock` đứng yên sau khi Sprint 4 có khóa thật

| | |
|---|---|
| **Tài liệu** | MDD §5 ("Sprint 1–3 chạy hoàn toàn bằng MockLLM; Gemini thật chỉ vào từ Sprint 4") |
| **Phát hiện khi chạy thật** | Tạo dự án thứ hai cho bo STM32: `eaa init` chọn `mock`, rồi `eaa doctor --discover --propose` chết với thông báo *"chọn provider gemini trong Project State"* — một câu mô tả NỘI TÌNH engine, không phải một lệnh gõ được. Người dùng phải biết Project State có trường tên `llm.provider` mới dùng tiếp được |
| **Code làm** | `chon_llm_theo_moi_truong()`: thấy `EAA_LLM_KEY` thì chọn mô hình thật và NÓI RA vì sao; không thấy thì dùng giả lập, kèm lệnh để chuyển. `--provider` người nêu vẫn thắng. `canh_bao_lech_cau_hinh()` báo khi Project State và môi trường nói khác nhau — báo chứ không tự sửa, vì Project State nằm trong Git và là một phần điều kiện thí nghiệm |
| **Rủi ro tự tạo, và cách chặn** | Đổi mặc định làm bộ test có thể vô tình gọi API thật: máy phát triển có `.env`, mà 20 bài test gọi `eaa init` trần. Thêm `tests/conftest.py` với hai chốt — xóa khóa khỏi môi trường mọi bài test, VÀ chặn `urlopen`. Chốt thứ hai cần vì chốt thứ nhất chỉ đúng khi bài test đặt `EAA_HOME` sang thư mục tạm, và một chốt an toàn phụ thuộc điều kiện ngầm sẽ hỏng lặng lẽ |
| **Điều rút ra** | Thông báo lỗi tốt là một LỆNH GÕ ĐƯỢC. Mô tả trạng thái bên trong bắt người dùng phải hiểu kiến trúc mới dùng được sản phẩm — và họ không có nghĩa vụ ấy |
| **Sprint** | S4 |

---

## SL-41 · BỔ SUNG · `eaa/gapsearch.py` — bậc thang tìm kiếm, P7 bước 3

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2 bước 3, FR-GAP-02; quy trình P7 |
| **Thiết kế nói** | Mục THIẾU được tìm bổ sung theo thang ba bậc: ① lục tài liệu người dùng đã đưa mà chưa trích hết ② hỏi người ĐÍCH DANH ③ tra miền nhà sản xuất cho phép. Tối đa 2 vòng mỗi mục rồi chuyển người |
| **Chỗ trống** | Bước 1, 2 và 4 của P7 đã làm từ Sprint 3; **bước 3 thì chưa**. Dấu vết nằm ngay trong mã: `RicItem.search_rounds` tồn tại, `MAX_SEARCH_ROUNDS` tồn tại, dòng chặn "đã tìm N vòng" tồn tại — mà **không chỗ nào tăng bộ đếm**, vì không ai đi tìm. Agent nói "thiếu thanh ghi X" rồi đứng đó |
| **Code làm** | `GapResolver` (ba bậc), `SearchLedger` (bộ đếm sống qua nhiều phiên), lệnh `eaa resolve <module> [--ask] [--web]`; thông báo `NotReady` nay chỉ đúng lệnh thay vì chỉ mô tả tình trạng |
| **Bậc 1 rẻ và đáng tin nhất** | Tìm cả chunk ở trạng thái `proposed`. Chạy thật trên dự án mẫu: hạ một chunk xuống `proposed` rồi gọi `eaa resolve` → Agent trả lời *"đã có trong kho nhưng CHƯA DUYỆT: ds-021 — duyệt tại G2 là đủ, không cần tìm thêm ở đâu"*. Đó là câu trả lời tôn trọng công sức người đã bỏ ra |
| **Bậc 3 buộc kèm nguồn** | Một câu trả lời trôi chảy của mô hình trông y hệt một trích đoạn tra được từ tài liệu gốc. Nên: `found=false` thì tôn trọng; không có nguồn thì BỎ kết quả (không hạ xuống thành "tham khảo"); nguồn phải qua bộ lọc miền của `ingest.check_web_source` |
| **Lỗi tìm ra khi chạy thật** | Bản đầu trừ lượt TRƯỚC khi tìm, nên một vòng tìm **thành công** cũng tiêu một lượt — mục tra được ngay từ bậc 1 vẫn cạn ngân sách sau hai lần gõ lệnh. Ngân sách hai vòng sinh ra để chặn việc tìm mãi không thấy, không phải để phạt việc tìm thấy. Nay chỉ trừ khi tìm không ra |
| **Bất biến giữ nguyên** | Mọi bậc chỉ sinh ĐỀ XUẤT (`status: proposed`), phải qua G2. Mâu thuẫn thì thang KHÔNG chạy — kho đang tự mâu thuẫn thì tìm thêm chỉ làm rối. Agent vẫn cấm đoán giá trị (FR-GAP-03) |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/gapsearch.py`, lệnh `eaa resolve` |
| **Sprint** | S4 |

---

## SL-42 · BỔ SUNG · `eaa/brief.py` — khởi tạo dự án bằng hội thoại

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1, quy trình P1; nghiệp vụ N-001..N-006 |
| **Thiết kế nói** | Công đoạn A1 (ràng buộc cứng) và B2 (hồ sơ phần cứng) là "90% con người" |
| **Chỗ trống** | Câu ấy được hiện thực thành: `eaa init` ĐÒI hai tệp đã có sẵn, và không lệnh nào giúp tạo ra chúng. "90% con người" khác hẳn "100% con người, không ai hỏi giúp một câu" — người dùng phải tự biết cần khai trường gì, tự tra tần số đồng hồ, tức là phải hiểu kiến trúc bên trong mới bắt đầu được |
| **Bằng chứng khoảng trống có thật** | Ngay trong phiên dựng tính năng này, `constraints.yaml` và `hardware_profile.yaml` cho bo STM32F469I-DISCO là do **tôi gõ tay**. Người dùng chỉ ra hai lần rằng tôi đang làm thay Agent |
| **Code làm** | `probe_hardware()` (cổng + VID/PID + ổ nạp), `identify_board()` (ứng viên kèm cách phân biệt), `QUESTIONS` (danh mục hỏi), `ProjectDraft` (sinh hai tệp ở dạng nháp); lệnh `eaa brief` chạy TRƯỚC `eaa init` |
| **Thứ tự bốn bước là điểm chính** | ① dò trước khi hỏi — máy tự biết được gì thì không hỏi ② nhận dạng, không chắc thì đưa ứng viên KÈM CÁCH PHÂN BIỆT ③ hỏi đúng phần máy không biết ④ sinh hồ sơ ở dạng đề xuất |
| **Ba loại dữ kiện không trộn** | ĐÃ KIỂM (máy tự đo trên máy này) · NGƯỜI NÓI · TRA CỨU. Thứ chưa kiểm xuống mục `assumptions` kèm cách kiểm, không nằm lẫn như sự thật — sáu tháng sau không ai nhớ con số nào đo được, con số nào đoán ra |
| **Agent không đoán chỗ nào** | Tiêu chí nghiệm thu để TRỐNG: nó phải đo được và phải do người chốt TRƯỚC khi có số đo. Chu kỳ điều khiển và chế độ an toàn là câu hỏi bắt buộc, không có mặc định |
| **Không ghi đè** | Hồ sơ đã có thì dừng: bản cũ có thể đã qua G1 và mã sinh ra đang dựa vào nó |
| **Chốt mạng của bộ test bắt được một lãng phí** | Bản đầu gọi mô hình để nhận dạng bo NGAY CẢ KHI người đã nêu rõ `--board`. Hỏi lại thứ vừa được nói là tốn một lời gọi để xác nhận điều đã chắc chắn hơn mọi phỏng đoán. Nay bỏ qua bước nhận dạng khi bo được nêu rõ |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/brief.py`, lệnh `eaa brief`; EAA-AIS-05 §6.1 nói rõ A1/B2 có Agent dẫn dắt |
| **Sprint** | S4 |

---

## Chưa lệch nhưng cần bổ sung tài liệu sau


Các năng lực do EAA-AIS-05 v1.1/v1.2 thêm vào mà EAA-SDD-03 v1.0 chưa có chỗ
trong cây thư mục. Ghi trước ở đây để khi tới sprint tương ứng không phải nghĩ
lại, và để bản cập nhật SDD gom một lần:

| Năng lực | Nguồn | Module dự kiến | Sprint |
|---|---|---|---|
| BM25 bổ trợ cho truy xuất theo từ khóa (tầng 2 của AIS §4.2) | AIS §4.2, ADR-07 | `eaa/rag.py` | hoãn |
| Thu nhận đầu vào đa phương thức, proposed facts | AIS §6 | `eaa/ingest.py` | S3 |
| Vòng tự đánh giá đủ thông tin (RIC, Readiness Check) | AIS §6.2 | `eaa/readiness.py` | S3 |
| Vòng đời tri thức: supersede + stale set | AIS §8.1–8.3 | `eaa/lifecycle.py` | S3 |
| Kho phẩm xuất (Artifact Registry) | AIS §8.5 | `eaa/registry.py` | S3 |
| `eaa doctor`, tool manifest, env_lock, Tool Card | AIS §9 | `eaa/doctor.py` | S3 |
| Chế độ chẩn đoán phần cứng DS-01..06 | AIS §7 | `eaa/diagnostics.py` | S4 |
| Phiên bản mã 3 hạng, `known_good.lock`, rollback | AIS §8.4 | `eaa/versions.py` | S4 |
