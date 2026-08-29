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
