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

## SL-43 · BỔ SUNG · `eaa/decompose.py` — Agent đề xuất phân rã module

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §3, quy trình P2; nghiệp vụ N-040..N-043 |
| **Chỗ trống** | `eaa plan add` có từ Sprint 0, nhưng nó chỉ GHI LẠI thứ người đã nghĩ ra. Người dùng phải tự chia module, tự biết module nào chiếm ngoại vi nào, tự xếp thứ tự, tự chọn chu kỳ — bốn việc đòi đúng loại kiến thức Agent có sẵn |
| **Code làm** | `ModuleProposal`, `DecompositionPlan` (sắp topo, nhóm song song, ước lượng tải), `LlmDecomposer`; lệnh `eaa plan propose` và `eaa plan accept` |
| **Bốn thứ đề xuất CÙNG LÚC** | module · tài nguyên chiếm · phụ thuộc · chu kỳ. Tách ra bốn lượt hỏi thì lượt sau phá kết quả lượt trước — chọn chu kỳ 1 ms cho một module vừa được xếp phụ thuộc vào một module 100 ms là vô nghĩa |
| **Ước lượng tải CPU** | Dùng để phát hiện phân rã bất khả thi NGAY TRÊN GIẤY: mười việc mỗi việc 3 ms trong chu kỳ 10 ms là không chạy được, và biết trước khi viết dòng mã nào thì rẻ hơn nhiều. Vượt trần 70% thì `plan accept` từ chối, phải nói rõ ý định bằng `--du-biet-qua-tai`. Luôn ghi rõ đây là ƯỚC LƯỢNG, số thật chỉ có khi đo trên thiết bị |
| **Lỗi tự tạo, tìm ra ở lần chạy thật đầu tiên** | Bộ kiểm chu kỳ bản đầu cảnh báo MỌI module tầng logic có chu kỳ lớn hơn `control_loop_ms`. Chạy thật trên dự án STM32: nó báo động cả module gửi telemetry mỗi 100 ms và module nháy LED mỗi 500 ms — cả hai đều hoàn toàn đúng, vì trần ấy là trần của VÒNG ĐIỀU KHIỂN, không phải của mọi việc |
| **Thay bằng ba phép kiểm nói lên thật** | ① một việc không chạy xong nổi trong chính chu kỳ của nó ② không việc nào chạy đủ nhanh để làm vòng điều khiển đã khai ③ chu kỳ không phải bội số của việc nhanh nhất (bộ định thời hợp tác chỉ chạy được bội số của nhịp). Một cơ chế báo động sai thì người ta học cách phớt lờ, và làm hỏng luôn những lần báo đúng |
| **Không bịa tài nguyên** | Module chiếm ngoại vi không có trong hồ sơ phần cứng thì cảnh báo đích danh: hoặc mô hình bịa, hoặc hồ sơ còn thiếu — phải làm rõ trước khi nhận |
| **Agent không tự thêm vào backlog** | Phân rã là quyết định kiến trúc; kiến trúc sai thì mọi module sau đều đúng quy trình mà sai chỗ |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/decompose.py`, lệnh `eaa plan propose/accept` |
| **Sprint** | S4 |

---

## SL-44 · BỔ SUNG · `eaa/safety.py` — phân tích hỏng hóc và chế độ an toàn

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-DIA-01; công đoạn B2; nghiệp vụ N-016, N-017 |
| **Chỗ trống** | Thiết kế có chẩn đoán (tìm nguyên nhân SAU khi hỏng) nhưng không có phân tích hỏng hóc (liệt kê TRƯỚC những gì có thể hỏng và cách nhận ra). Hai việc khác nhau: cái sau quyết định firmware có phát hiện được sự cố hay không |
| **Code làm** | `FailureMode`, `SafeState`, `SafetyAnalysis` (đo độ phủ và chỗ hở), `LlmSafetyAnalyst`; lệnh `eaa safety propose` và `eaa safety show`; tệp `safety.yaml` ở tầng dự án |
| **Câu hỏi trung tâm** | KHÔNG phải "cái gì có thể hỏng" — danh sách ấy dài vô hạn — mà là **hỏng thì có ai biết không**. Hệ nhúng không có ai ngồi nhìn: một cảm biến trả rác sẽ được xử lý như số thật cho tới khi có gì đó cháy |
| **Ba bất biến** | ① mỗi kiểu hỏng phải có CÁCH PHÁT HIỆN; thiếu thì nêu đích danh, và mức cao/nguy hiểm thì nhấn mạnh ② phủ hết tài nguyên trong hồ sơ; thứ chưa phủ được gọi tên ③ chế độ an toàn phải nói rõ điều kiện VÀO và RA — vào mà không ra được là một cục gạch, và nếu chủ ý chỉ thoát bằng reset thì phải viết ra |
| **Sạch ranh giới** | Nhận biết "có cơ cấu chấp hành hay không" qua KHAI BÁO của dự án (`kind: actuator`), không qua tên linh kiện — engine không được biết tên một họ linh kiện nào |
| **Chạy thật trên dự án mẫu** | Mô hình dựng 7 kiểu hỏng phủ đủ 7 tài nguyên, không mục nào thiếu cách phát hiện, và cách phát hiện là cụ thể chứ không chung chung: giới hạn tốc độ biến thiên góc, đối chiếu lệnh PWM với gia tốc đo được, dùng một bộ đếm giám sát bộ đếm kia. Chế độ an toàn nêu rõ chỉ thoát bằng khởi động lại nguồn |
| **Mức tự chủ thấp có chủ ý** | Đây là nơi hậu quả của việc sai lớn nhất trong cả sản phẩm. Agent dựng bản đầy đủ và nêu chỗ còn hở; người đọc từng dòng rồi chốt tại G1. Không có đường nào để bản này tự có hiệu lực |
| **Cần cập nhật** | EAA-SDD-03: thêm `eaa/safety.py`, `safety.yaml`, lệnh `eaa safety` |
| **Sprint** | S4 |

---

## SL-45 · BỔ SUNG · Năng lực `flash_verify` — đọc ngược sau khi nạp

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-DIA-02, EAA-AIS-05 §7.3; nghiệp vụ N-075 |
| **Chỗ trống** | Thiết kế đặc tả nạp firmware phải có người xác nhận, nhưng dừng lại ở đó. Không chỗ nào nói *sau khi nạp thì kiểm gì* — nên mã thoát 0 của công cụ nạp đang âm thầm đóng vai bằng chứng cho câu "trên chip đúng là bản này" |
| **Code làm** | Thêm năng lực `flash_verify` vào `CAPABILITIES` của `eaa/platform.py`; `VerifyResult` + `Flasher.verify()` trong `eaa/flash.py`; hai trường mới trong `FlashRecord`; hai pack khai lệnh đọc ngược của mình |
| **Ba kết cục, không phải hai** | `khop` (đã kiểm) · `lech` (đã kiểm và hỏng — lần nạp bị coi là TRƯỢT dù công cụ trả 0) · `khong-kiem-duoc` (mạch nạp không hỗ trợ hoặc thiếu công cụ). Gộp hai cái sau vào một cờ nhị phân là đúng chỗ thông tin bị mất |
| **Vì sao tách khỏi `flash`** | Không phải mạch nạp nào cũng đọc ngược được. Pack thiếu năng lực này phải *nói ra là không kiểm được*, và điều đó chỉ diễn đạt được khi năng lực là một mục khai báo riêng |
| **Không đòi xác nhận lần hai** | Đọc ngược không đổi gì trên thiết bị, và nó chạy bên trong một lần nạp mà người đã xác nhận. Bắt bấm 'có' hai lần sẽ làm nhạt chính lần xác nhận có ý nghĩa |
| **Bản ghi cũ** | Mặc định `khong-kiem-duoc`, không phải `khop` — suy ngược lại sẽ gán một bằng chứng chưa từng tồn tại cho các lần nạp đã qua |
| **Lan sang phong hạng** | `DeviceCheck` có thêm `readback_verified`: commit khớp nhật ký mà chưa đọc ngược thì vẫn đi tiếp được (đây là thiếu biết, không phải mâu thuẫn) nhưng phải nói ra |
| **Cần cập nhật** | EAA-SDD-03 §2 (`platform.py` — thêm năng lực), EAA-AIS-05 §7.3 |
| **Test** | TC-52a..e |

---

## SL-46 · BỔ SUNG · `eaa/budget.py` — ngân sách tài nguyên và token theo module

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §3.1 (`limits`), EAA-AIS-05 P5 (ngân sách token); nghiệp vụ N-015, N-071, N-904 |
| **Chỗ trống** | Thiết kế có trần TỔNG (`flash_pct_max`) và trần MỖI LẦN GỌI (8.000 token), nhưng không có gì ở giữa: không chia phần theo module, và không có trần tích lũy cho một module |
| **Vì sao cần** | Trần tổng chỉ trả lời được vào lúc liên kết — lúc muộn nhất, khi cắt bớt đã thành viết lại. Mỗi module lẻ đều "dưới 50%" cho tới khi cộng lại thì không |
| **Code làm** | `ResourceBudget` (chia phần, kiểm bản chia tự mâu thuẫn, số liệu suy ra), `TokenBudget` + `spent_tokens`, `propose_split`; khối `budget` trong `constraints.yaml`; lệnh `eaa budget show/propose/tokens` |
| **Ba việc một tệp** | Bộ nhớ chương trình, bộ nhớ dữ liệu và token khác nhau ở đơn vị chứ không khác ở cách quản. Tách ba tệp thì luật "cảnh báo khi ăn quá phần" phải viết ba lần — ba cơ hội để lệch nhau |
| **Sạch ranh giới** | Tên số liệu do pack đặt, dung lượng do dự án khai, đơn giá do dự án khai. Engine chỉ cộng, chia, so sánh — TC-53 quét để chắc không tên số liệu nào bị ghim vào engine |
| **Lỗi bắt được ngay** | Bản `propose_split` đầu tiên làm tròn gần nhất và sinh ra một bản chia vượt dung lượng đúng 1 byte — tự vi phạm phép kiểm của chính nó. Đã đổi sang làm tròn xuống; phần dôi rơi về dự phòng |
| **Test** | TC-53a..g |

## SL-47 · LỆCH THẬT · `stack_headroom_bytes` khai từ Sprint 0 mà chưa bao giờ được thi hành

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §3.1; nghiệp vụ N-071 |
| **Thiết kế nói** | `constraints.yaml` của dự án mẫu khai `stack_headroom_bytes: 128` — "không tràn stack" |
| **Code làm (trước)** | `SizeGate` chỉ áp quy ước `<tên>_max` / `<tên>_min`. Khóa viết trần trụi rơi qua khe `continue`, nên **ngưỡng ấy im lặng suốt bốn sprint**. Thêm nữa, không công cụ nào in ra số liệu tên `stack_headroom_bytes` để mà so |
| **Code làm (nay)** | Đổi khóa thành `stack_headroom_bytes_min`; thêm `budget.derived` để engine SUY RA số liệu ấy bằng `dung_lượng − đã_dùng`; chỉ suy ở tầm firmware, vì ở tầm module con số sẽ rộng rãi giả tạo |
| **Vì sao xếp loại LỆCH THẬT** | Đây không phải chỗ trống của tài liệu mà là một ngưỡng **có khai, không ai áp** — thứ tệ hơn không khai, vì nó tạo cảm giác đã kiểm |
| **Cần cập nhật** | EAA-SDD-03 §3.1: nêu rõ quy ước đuôi `_max`/`_min` là điều kiện để một ngưỡng được thi hành |
| **Test** | TC-53d |

## SL-48 · DỜI CHỖ · Đầu vào của TC-15 đóng băng cạnh fixture, không đọc từ dự án mẫu

| | |
|---|---|
| **Tài liệu** | EAA-STP-04 TC-15 |
| **Trước** | `tests/test_tc15_e2e.py` chép `constraints.yaml`, `hardware_profile.yaml`, `datasheets/` thẳng từ `projects/robot_balance/` |
| **Vấn đề** | Băm prompt phủ toàn bộ ngữ cảnh, nên **mọi lần sửa dự án mẫu đều làm trượt băm và đòi ghi lại fixture bằng một lượt gọi API thật** — kể cả khi thay đổi ấy chẳng liên quan tới thứ TC-15 chứng minh. Phát hiện đúng lúc thêm khối `budget` |
| **Lý do nặng hơn lý do tiện lợi** | Phản hồi trong fixture được mô hình sinh ra *dưới đúng bộ ràng buộc cũ*. Ghép ràng buộc mới với phản hồi cũ là dựng một cảnh mô hình chưa bao giờ nhìn thấy. Bằng chứng đã ghi phải đi cùng đầu vào đã sinh ra nó |
| **Nay** | `tests/fixtures/e2e_project/` giữ bản chụp ba đầu vào ấy, kèm README nói rõ cách làm mới (hai bước, có chủ ý). Bộ mô phỏng vẫn đọc từ dự án mẫu vì nó KHÔNG vào prompt |
| **Ghi nhận thêm** | Lệnh thay dòng `platform:` sau khi chép đã bỏ: nó khiến tệp được băm khác tệp nằm trong kho, nên không cách nào đối chiếu bản ghi với đầu vào |
| **Test** | `test_dau_vao_anh_huong_bam_prompt_deu_da_dong_bang` canh đúng điều này |

---

## SL-49 · BỔ SUNG · `eaa/propose.py` — Agent đề xuất ở G0/G1, không chỉ đối chiếu

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1 (quy trình P1), FR-KB-01; công đoạn A1, B2; nghiệp vụ N-006, N-010, N-011, N-014 |
| **Chỗ trống** | Bốn việc của giai đoạn đầu đều có cơ chế và đều thiếu đúng một nửa: engine ĐỌC được ràng buộc, ĐỐI CHIẾU được tiêu chí nghiệm thu, TRA được bảng chân — nhưng không tự nói ra được một đề xuất nào. Người dùng vẫn phải tự biết cần khai gì |
| **Vì sao đáng làm** | Đối chiếu bắt đầu từ một danh sách đã có; đề xuất phải bắt đầu từ trang trắng. Trang trắng mới là chỗ người mới vào nghề mắc kẹt, và Ma trận Người–AI xếp cả bốn việc này ở mức T1 (Agent đề xuất, người chốt) chứ không phải T0 |
| **Code làm** | `ScopeProposal`, `ConstraintProposal`, `AcceptanceProposal`, `PinMapProposal`, `LlmProposer`; lệnh `eaa propose scope/constraints/acceptance/pinmap`; tệp `scope.yaml`; khóa `pin_functions` trong `hardware_profile.yaml` |
| **Bốn bất biến riêng** | ① mục NGOÀI phạm vi phải có lý do ② mỗi ràng buộc kèm HỆ QUẢ nếu vi phạm — người duyệt cần căn cứ để **bác**, mà một con số trần trụi không phải căn cứ ③ tiêu chí nghiệm thu = số + đơn vị + cách đo + nguồn số đo; câu kiểu "chạy mượt" bị từ chối kèm câu hỏi làm nó đo được ④ mỗi chân phải nói phục vụ chức năng gì, và chức năng ấy được đối chiếu với bảng chức năng thay thế |
| **Ba kết cục ở phép kiểm chân** | `hỗ trợ` · `KHÔNG hỗ trợ` · `chưa kiểm được`. Kết cục thứ ba tồn tại vì engine **không được biết** chân nào làm được gì — tri thức ấy thuộc đúng một họ vi điều khiển. Chưa khai `pin_functions` thì nói thẳng là chưa kiểm, không im lặng cho qua |
| **Bất biến chặn cả nguồn từ mô hình** | Ràng buộc thiếu hệ quả, tiêu chí thiếu đơn vị… bị từ chối ngay lúc dựng đối tượng, nên mô hình cũng không lách được — không chỉ chặn khi người gõ tay |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/propose.py`, `scope.yaml`; EAA-SDD-03 §3.2: thêm `pin_functions` vào lược đồ Hardware Profile |
| **Test** | TC-54a..g |

---

## SL-50 · BỔ SUNG · `eaa/docplan.py` — tài liệu đích danh, trang đích danh, errata theo rev

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1–6.2, FR-GAP-02, FR-ING-02; nghiệp vụ N-004, N-030, N-037 |
| **Chỗ trống** | Thiết kế có tầng THU NHẬN tài liệu (`ingest.py`) và tầng ĐI TÌM khi thiếu (`gapsearch.py`), nhưng không có tầng nói **cần gì ngay từ đầu**. Người dùng vẫn phải tự biết mình cần đưa những tài liệu nào |
| **Code làm** | `plan_documents` (N-004), `plan_pages` (N-030), `ErrataAnalysis` + `LlmDocLookup` (N-037); lệnh `eaa sources need/pages`, `eaa errata show/lookup`; tệp `errata.yaml` |
| **Suy được vs phải tra** | Suy từ dữ liệu dự án: danh sách tài liệu (hồ sơ phần cứng), thanh ghi còn thiếu trích đoạn (đồ thị + kho chunk), module chạm lỗi (backlog). Phải tra: đường dẫn trang hãng và nội dung errata — cả hai là *proposed fact*, nguồn chặn trong danh sách cho phép, duyệt tại G2 |
| **Vì sao errata quan trọng hơn vẻ ngoài** | Mã **đúng theo datasheet** vẫn chạy sai nếu chip có lỗi đã công bố. Đây là loại lỗi mà **mọi cổng kiểm chứng của hệ thống này đều cho qua** — vì mã thật sự đúng với thứ nó được bảo. Không tài liệu nào khác nói được điều đó |
| **Bất biến trung tâm** | `looked_up: false` nghĩa là CHƯA AI TRA, không phải "chip sạch" — một danh sách trống ở hai trường hợp ấy trông y hệt nhau. Cùng nguyên tắc với `verify_status` ở SL-45 |
| **Bất biến thứ hai** | `revisions` trống = tài liệu không nói rõ → coi là DÍNH mọi rev. Suy ngược lại biến một chỗ thiếu thông tin thành một lời bảo đảm |
| **Danh sách ngắn là điểm chính của N-030** | Chỉ xin phần còn THIẾU trích đoạn, và chỉ tính bản `active` — chunk đã bị supersede thì thanh ghi ấy coi như chưa có, vì đó đúng là tình trạng của nó |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/docplan.py`, `errata.yaml`; EAA-AIS-05 §6.2: nêu bước "lập danh sách tài liệu cần" trước bậc thang tìm kiếm |
| **Test** | TC-55a..h |

---

## SL-51 · BỔ SUNG · `eaa/interfaces.py` + khuôn `interfaces` của pack — giao diện sinh trước thân

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §3 (K3 interface-only), FR-CTX-02; nghiệp vụ N-041 |
| **Chỗ trống** | Lớp K3 của composer đọc tệp tiêu đề của module phụ thuộc, nhưng tệp ấy chỉ tồn tại SAU khi module kia sinh xong và merge. Hệ quả: thứ tự làm việc bị ép thành một hàng dọc — không ai bắt đầu được cho tới khi người trước xong |
| **Code làm** | `FunctionContract`, `InterfaceSpec`, `InterfaceGenerator`, `LlmInterfaceDesigner`; `InterfaceTemplates` trong `eaa/platform.py`; khuôn `templates/module.h.tmpl` ở cả hai pack; lệnh `eaa interface <module> [--write]` |
| **Ba câu chữ ký không nói được** | gọi trong ngắt được không · có chặn không · tái nhập được không. Cả ba mặc định là KHÔNG, không phải "chắc là được" — một mặc định êm ái sẽ được nhận vì tiện, và sai lệch chỉ lộ ra dưới tải |
| **Một mâu thuẫn bị chặn tại chỗ** | `isr_safe` **và** `blocking` cùng đúng bị từ chối ngay lúc dựng đối tượng, kể cả khi nguồn là mô hình |
| **Engine không viết C** | Tệp tiêu đề là mã C nên khuôn nằm ở pack — cùng ranh giới với khuôn ráp firmware (SL-31). TC-56 quét engine tìm `#ifndef`/`#define` để chắc điều đó không trôi |
| **Mắt xích dễ tuột** | Tệp tiêu đề đề xuất mang dòng đầu `GIAO DIỆN ĐỀ XUẤT — thân module CHƯA sinh`, và composer lấy đúng dòng chú thích đầu tiên làm tóm tắt lớp K3. Nhờ vậy mô hình biết nó đang dựa vào một lời hứa chứ không vào mã đã kiểm |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/interfaces.py`, mục `interfaces` trong lược đồ `pack.yaml` |
| **Test** | TC-56a..e |

## SL-52 · BỔ SUNG · Cổng test đơn vị nêu đích danh phần KHÔNG kiểm được

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 (pytest runner), FR-VER-01; nghiệp vụ N-053 |
| **Chỗ trống** | Cổng chạy được và chặn được, nhưng một dòng "12 passed" không phân biệt *đã kiểm* với *không kiểm được ở đây*. Người đọc mang cảm giác đã phủ hết sang bước tiếp theo |
| **Code làm** | `host_gaps()` trong `eaa/tools/unittests.py`; `UnitTestGate` nhận thêm `module`/`graph`/`constraints` |
| **Suy từ đâu** | Đồ thị tài nguyên của chính module: thanh ghi nó cấu hình, ngoại vi nó chiếm, ràng buộc thời gian của dự án. Ba loại, và tách ra có ích vì mỗi loại được đóng ở một chỗ khác — thanh ghi ở G4, ngoại vi ở chẩn đoán hai kênh, thời gian ở cổng mô phỏng |
| **Cảnh báo, không phải lỗi** | Thiếu sót này không sửa được bằng cách viết thêm test trên máy chủ, nên chặn ở đây là vô ích. Nó được NÊU RA, và nêu cả khi mọi test đều xanh — nhất là khi mọi test đều xanh |
| **Tương thích ngược** | Không truyền ba tham số mới thì cổng chạy y như trước, chỉ im lặng hơn |
| **Test** | TC-56f, TC-56g |

---

## SL-53 · BỔ SUNG · Tiêm lỗi trong mô phỏng — `FaultSpec` trong `sim_runner.py`

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-SIM-01, EAA-SAD-02 ADR-05; công đoạn C2; nghiệp vụ N-063 (nối với N-016, N-017) |
| **Chỗ trống** | Bộ mô phỏng kiểm được "hệ có giữ được thăng bằng khi mọi thứ hoạt động không". Nó không có cách nào hỏi câu quan trọng hơn: **khi cảm biến hỏng thì hệ có kịp vào chế độ an toàn không** — trong khi `safety.yaml` (N-016) đã liệt kê sẵn các kiểu hỏng ấy từ S4 |
| **Code làm** | `FaultSpec` + `_TiemLoi` + `_trang_thai_an_toan()` trong `eaa/tools/sim_runner.py`; ngưỡng `require_safe_state`; ba kịch bản tiêm lỗi trong `projects/robot_balance/sim/scenarios.yaml`; chế độ an toàn trong bộ điều khiển tham chiếu |
| **Bốn kiểu hỏng, đặt tên theo HÀNH VI** | `stuck` · `garbage` · `dropout` · `power_sag`. Không đặt theo tên linh kiện, vì engine không được biết tên một họ cảm biến nào |
| **Đặt GIỮA mô hình và bộ điều khiển** | Không đặt trong mô hình: một mô hình có sẵn chỗ để hỏng thì mãi mãi chỉ hỏng theo những cách đã nghĩ ra lúc viết nó. Ở đây, thêm một kiểu hỏng là thêm một dòng YAML |
| **Ba trạng thái, không phải hai** | `safe_state_entered` = 1 / 0 / **−1 (không kiểm được)**. Bộ điều khiển không khai `safe`/`is_safe()` thì kết luận là *chưa kiểm được*, không phải *không vào* — cùng nguyên tắc với `verify_status` ở SL-45 |
| **Một ngoại lệ có lý do vật lý** | Kịch bản đòi chế độ an toàn mà hệ vào được thì việc robot NGÃ không bị tính là trượt: chế độ an toàn nghĩa là cắt lệnh chấp hành, và một robot bị cắt lệnh thì ngã. Đòi cả hai là đòi hai điều loại trừ nhau |

### Hai con số do tiêm lỗi chọn ra, không do trực giác

| | |
|---|---|
| **Ngưỡng phát hiện cảm biến kẹt** | Bản đầu đặt 50 chu kỳ (0,5 s) vì "nghe hợp lý". Kịch bản `loi_cam_bien_ket` cho thấy robot **đã ngã trước khi bộ phát hiện kịp bật**. Quét lại: vách đứng nằm giữa 20 và 30 chu kỳ — cửa sổ chỉ ~200 ms. Chốt 10 chu kỳ (100 ms) để còn biên |
| **Thời lượng kịch bản sụt nguồn** | Ở mức còn 30% lực: chịu được 1,0 s (đỉnh 1,2°), NGÃ ở 2,0 s. Đặt kịch bản ở 1,0 s — ngay dưới vách. Đặt ở 0,3 s thì mọi bộ tham số đều qua và phép kiểm thành trang trí |
| **Vì sao ghi lại** | Cả hai đều là kết luận **quan sát được**, không phải lựa chọn thẩm mỹ. Đây đúng là loại giá trị mà tiêm lỗi sinh ra: nó biến một tham số đặt theo cảm tính thành một tham số có căn cứ |

| **Test** | TC-57a..e; TC-12 đổi từ đếm cứng 3 kịch bản sang "mọi kịch bản dự án khai" |

## SL-54 · BỔ SUNG · `PlantModelProposal` — đề xuất mô hình đối tượng (N-060)

| | |
|---|---|
| **Tài liệu** | EAA-SAD-02 ADR-05; công đoạn C1; nghiệp vụ N-060 |
| **Chỗ trống** | Dự án mẫu có mô hình con lắc viết tay, nhưng Agent không đề xuất được mô hình cho một đối tượng mới — nên phần tổng quát của bộ mô phỏng dừng ở khung chạy, không tới được nội dung |
| **Code làm** | `PlantParameter`, `PlantModelProposal`, `LlmProposer.plant_model()`; lệnh `eaa propose plant --plant "<đối tượng>"` |
| **Hai bất biến** | ① tham số `uoc_luong` BẮT BUỘC nói cách đo — một ước lượng không kèm cách kiểm sẽ lặng lẽ được đọc như một số đo ② mô hình BẮT BUỘC nêu hiện tượng nó bỏ qua; một mô hình tự nhận không bỏ qua gì là mô hình chưa ai nghĩ tới giới hạn của nó, và sẽ được tin quá mức |
| **Nối vào Assumption Log** | `to_assumption_log()` dựng sẵn mục `proposed` kèm `how_to_verify` để dán vào `hardware_profile.yaml` — đúng đường đi của tri thức chưa thực chứng ở AIS §8.1 |
| **Test** | TC-57f, TC-57g |

---

## SL-55 · BỔ SUNG · Hoàn thiện tầng đo trên thiết bị thật (N-081, N-083, N-084, N-086)

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (DS-01..06), EAA-SRS-01 FR-DIA-01/03; công đoạn G8 |
| **Chỗ trống** | Cơ chế chẩn đoán đủ từ S4, nhưng **mới 2/6 kịch bản có phần đo**; kịch bản thời gian chỉ đo trung bình; không có kênh nào cho phép đo bằng dụng cụ; và tiêu chí `uptime_s ≥ 600` trong `constraints.yaml` không có gì thi hành nó |
| **N-081 · đủ sáu phần đo** | Viết `DS-02.c`, `DS-03.c`, `DS-05.c`, `DS-06.c` ở tầng dự án. Thêm `Scenario.buildable` — kịch bản chưa khai phần đo thì DỪNG, không dựng một ảnh rỗng: một firmware chạy trơn tru và trả về không có gì thì "không có gì" không phân biệt được với "đo xong, mọi thứ bình thường" |
| **N-083 · trường hợp xấu nhất** | DS-06 đo thêm `isr_period_max_ms` và `cpu_load_pct`. Ràng buộc `control_loop_ms` được đối chiếu với **chu kỳ dài nhất**, không với trung bình — trung bình gần như luôn đẹp, còn con lắc ngược thì ngã vì đúng cái chu kỳ 23 ms mỗi vài giây |
| **N-083 · hai bộ đếm độc lập** | Timer1 là vật được đo, Timer0 là thước. Một bộ đếm tự đo chính mình thì mọi sai số nguồn xung nhịp triệt tiêu và ta luôn được một con số hoàn hảo — hoàn hảo vì nó không đo gì cả |
| **N-084 · kênh thứ ba** | `ManualMeasurement` + `eaa diagnose measure`. Bốn trường bắt buộc là bốn câu một hướng dẫn đo phải trả lời: **đo cái gì, ở đâu, trong điều kiện nào, chờ đợi bao nhiêu**. Thiếu một câu thì hai người đo ra hai kết quả và không ai sai. Số đo về ghi vào `measurements.jsonl`, append-only |
| **N-084 · vì sao cần** | Dòng tổng, sụt áp **trên dây**, nhiệt độ vỏ linh kiện — không con chip nào tự đo được về chính nó. ADC nội đo được điện áp tại chân chip, còn sụt áp nằm trên đoạn dây trước đó |
| **N-086 · `eaa/endurance.py`** | Phát hiện reset qua **bộ đếm thời gian chạy tụt xuống** — bằng chứng trực tiếp, khác hẳn suy từ một khoảng lặng trên đường truyền (khoảng lặng cũng có thể do rút dây) |
| **Bất biến của N-086** | Báo cáo **không suy rộng**. Câu đầu tiên luôn nói về THỜI GIAN đã quan sát thật, trước cả khi nói mọi thứ đều tốt; chạy ngắn hơn yêu cầu là *CHƯA KẾT LUẬN ĐƯỢC*, và thiếu bộ đếm là *KHÔNG KẾT LUẬN ĐƯỢC* — không cái nào là "đạt" |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/endurance.py`, `measurements.jsonl`, lệnh `eaa endurance` và `eaa diagnose measure`; EAA-AIS-05 §7.2: thêm khối `manual` vào lược đồ kịch bản |
| **Test** | TC-58a..g; TC-27 cập nhật vì DS-06 đổi từ 2 lên 5 tiêu chí |

---

## SL-56 · BỔ SUNG · `eaa/handover.py` + `FieldCase` — giai đoạn bàn giao và vận hành

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7, §8.5; FR-DOC-01; công đoạn G9, G10; nghiệp vụ N-094, N-101, N-102, N-103 |
| **Chỗ trống** | Thiết kế dừng ở nghiệm thu G4/G5. Bốn việc sau đó — bàn giao, đổi linh kiện, sự cố hiện trường, cập nhật thiết bị đã triển khai — không có chỗ nào trong cây thư mục, dù chúng chiếm phần lớn vòng đời một sản phẩm nhúng |
| **N-094 · `OperationsHandbook`** | Sinh tài liệu vận hành từ dữ liệu dự án. Toàn bộ nội dung đã nằm rải rác sẵn (bảng chân, kịch bản chẩn đoán, Assumption Log, nhật ký nạp) — việc ở đây là GOM, không phải nghĩ ra, nên nó sinh được và nên sinh chứ đừng chép tay |
| **Mục "KHÔNG làm được" là phần chính** | Dựng từ bốn nguồn dữ liệu thật: giả định chưa kiểm, kịch bản chưa có phần đo, đại lượng phải đo tay, errata chưa tra, kiểu hỏng không phát hiện được. Một mục viết tay sẽ liệt kê những giới hạn người viết NHỚ RA — tức là những giới hạn ít nguy hiểm nhất |
| **N-101 · `SwapAnalysis`** | So hai linh kiện rồi bắc cầu trên đồ thị tài nguyên ra module bị chạm. Báo cáo nói rõ nó nêu được module *đụng tới* thứ đã đổi, KHÔNG nói được mã ấy sai ở đâu. `drop_in: true` vẫn kèm câu "phải chạy lại chẩn đoán" — "thay thẳng được" là lời hứa về chân, không phải về dải hoạt động |
| **Một dòng bị cấm** | `ComponentDelta` từ chối mục có `old == new`. Bảng so sánh đầy dòng "giống nhau" sẽ được lướt qua, và dòng khác biệt thật sự lướt qua cùng |
| **N-102 · `FieldCase`** | Ca hiện trường khác một phiên trên bàn ở đúng một điểm: **hiện tượng không xảy ra trước mặt ta**. Nên bước đầu là DỰNG LẠI ĐIỀU KIỆN, và ba trạng thái `tái-hiện-được` / `không-tái-hiện` / `chưa-thử` được phân biệt. Không tái hiện ⇒ *CHƯA KẾT LUẬN ĐƯỢC*, kèm việc phải làm: đi lấy thêm dữ kiện, không đoán nguyên nhân |
| **N-103 · `RolloutPlan`** | Bậc đầu tiên có **đúng một** thiết bị — không thương lượng; số thiết bị phải tăng dần; mỗi bậc phải nêu ĐIỀU KIỆN DỪNG; phải có bản quay lui, và bản ấy lấy từ `known_good.lock` (chỉ cập nhật tại G4 sau khi có số đo vật lý) chứ không từ một commit trông có vẻ ổn định |
| **Engine không tự chuyển bậc** | Điều kiện dừng là thứ người quan sát, không phải thứ đọc được từ một tệp |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/handover.py`, `rollout.yaml`, lệnh `eaa handover` và `eaa field`; EAA-AIS-05 §7: thêm mục ca hiện trường |
| **Test** | TC-59a..h |

---

## SL-57 · BỔ SUNG · `eaa/confidence.py` — một bộ từ vựng mức tin cậy cho toàn hệ

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1 (proposed fact), §12; FR-ING-02; nghiệp vụ N-903 |
| **Chỗ trống** | Nhiều chỗ đã phân biệt đúng ba loại phát biểu — `flash.VerifyResult`, `docplan.ErrataAnalysis`, `propose.PlantParameter` — nhưng **mỗi chỗ tự đặt tên theo cách riêng**. Người đọc phải học lại từ vựng ở từng màn hình, và những chỗ CHƯA phân biệt thì không có gì nhắc rằng chúng nên |
| **Code làm** | `DA_KIEM` / `SUY_RA` / `GIA_DINH` / `KHONG_KIEM_DUOC`, `Claim`, `ClaimSet`; năm module hiện có expose `confidence_level` quy về đúng bốn mức ấy |
| **Ranh giới hay bị gộp** | GIẢ ĐỊNH vs KHÔNG KIỂM ĐƯỢC. Cái đầu còn kiểm được nếu ai đó bỏ công; cái sau cần một cách khác hoặc một dụng cụ khác. Hai tình huống dẫn tới hai việc phải làm khác hẳn, nên gộp là mất thông tin |
| **Ba bất buộc của `Claim`** | ĐÃ KIỂM phải có nguồn (không có nguồn thì đó chỉ là một câu nói chắc) · GIẢ ĐỊNH phải có cách kiểm · KHÔNG KIỂM ĐƯỢC phải có lý do |
| **Điều nó cố ý KHÔNG làm** | Không xếp hạng, không tính điểm tin cậy tổng. Một con số như thế nghe khoa học và che mất đúng thứ cần thấy: phát biểu NÀO đang ở mức nào |
| **Cần cập nhật** | EAA-SDD-03 §2; EAA-AIS-05 §6.1: nêu bốn mức là quy ước chung |
| **Test** | TC-60a..c |

## SL-58 · BỔ SUNG · `eaa/deviation.py` — Agent tự phát hiện sai lệch (N-905)

| | |
|---|---|
| **Tài liệu** | `CLAUDE.md` ("không lệch ngầm"); nghiệp vụ N-905 |
| **Chỗ trống** | Sổ này đầy đủ nhưng được ghi TAY, và một sổ ghi tay im lặng khi ai đó thêm một module rồi quên ghi. Đúng thứ mà quy tắc "không lệch ngầm" sinh ra để chặn |
| **Code làm** | `scan()` đối chiếu module trong `eaa/` và lệnh CLI với cây thư mục EAA-SDD-03 và với chính sổ này; lệnh `eaa deviations [--draft]` |
| **Đối chiếu danh sách, không đọc ý định** | Nó bắt được *"có trong mã mà không có trong tài liệu"*; nó **không** bắt được một module làm khác điều tài liệu mô tả. Giới hạn ấy được in ra cùng kết quả, không giấu |
| **Không dùng mô hình có chủ ý** | Một phép đối chiếu danh sách chạy bằng mô hình sẽ chậm hơn, tốn tiền, và có thể bỏ sót theo cách không tái hiện được |
| **Chỉ dựng nháp** | Phân loại BỔ SUNG / DỜI CHỖ / LỆCH THẬT là phán đoán về ý định, và lý do của lệch chỉ người làm mới biết. Máy dựng khung kèm chỗ trống rõ ràng |
| **Lệnh lấy từ chính bộ phân tích đối số** | Chép tay danh sách lệnh thì nó lệch ngay lần thêm lệnh sau, và một bộ dò sai lệch tự nó lệch thì tệ hơn không có |
| **Test** | TC-60d..f |

## SL-59 · BỔ SUNG · Bốn lệnh CLI có từ trước mà chưa lần nào được ghi nhận

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §6 (10 lệnh CLI) |
| **Phát hiện bởi** | Chính `eaa deviations` ở lượt chạy đầu tiên — đây là bằng chứng cơ chế N-905 làm được việc nó sinh ra để làm |
| **Bốn lệnh** | `eaa status` (xem trạng thái, chỉ đọc) · `eaa policy` (in bảng phân quyền và máy trạng thái) · `eaa packs` (liệt kê Platform Pack đã cài) · `eaa docs` (kho phẩm xuất, AIS §8.5) |
| **Phân loại** | BỔ SUNG. Cả bốn đều là lệnh CHỈ ĐỌC, không tạo ra quyết định nào và không chạm vào thiết bị — chúng bày ra thứ đã có. Đó là lý do chúng lọt qua mọi lần rà trước: không lệnh nào trong số đó làm gì đáng ngờ |
| **Vì sao vẫn phải ghi** | Danh sách lệnh là mặt tiếp xúc của sản phẩm với người dùng. Một lệnh không có trong tài liệu là một lệnh không ai biết để dùng, và cũng là một lệnh không ai nhớ để bảo trì |
| **Cần cập nhật** | EAA-SDD-03 §6: mở rộng bảng lệnh từ 10 lên số lệnh hiện có |

## SL-60 · BỔ SUNG · `KpiLogger.weak_points()` — tự đánh giá quy trình (N-906)

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-KPI-01; công đoạn F1; nghiệp vụ N-906 |
| **Chỗ trống** | `summary()` tổng hợp được số liệu nhưng cố ý KHÔNG diễn giải. Nên không chỗ nào trả lời câu "khâu nào hay hỏng nhất, và nên sửa gì" |
| **Code làm** | `ProcessReview` + bảng `_HUONG_SUA`; lệnh `eaa report review` |
| **Ranh giới giữ nguyên** | `summary()` vẫn không diễn giải; phần diễn giải nằm ở một hàm khác, và mọi đề xuất **gắn với một con số quan sát được**. Trộn hai việc thì người đọc không còn biết đâu là quan sát, đâu là suy đoán |
| **Hướng sửa là DỮ LIỆU** | Bảng "cổng X trượt nhiều thì thường vì Y" đến từ quan sát, không từ suy luận — thêm một cổng mới là thêm một dòng, không sửa mã |
| **Câu quan trọng khi chưa có dữ liệu** | "Chưa thấy khâu nào nổi lên" **không** có nghĩa là quy trình đang tốt; nó có nghĩa là chưa đủ dữ liệu để thấy |
| **Test** | TC-60g..i |

---

## SL-61 · BỔ SUNG · `eaa/goldenset.py` — bộ chuẩn đánh giá truy xuất (TC-20)

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §4, ADR-07, FR-KG-03; **TC-20** — test case của thiết kế, tới bản này mới có |
| **Chỗ trống** | Không có gì đo được chất lượng truy xuất. Kho lớn dần, mỗi trích đoạn mới là một ứng viên nữa cạnh tranh ba chỗ trong prompt — và đó là kiểu thoái lui **không làm đỏ một test nào**: mã vẫn chạy, prompt vẫn lắp được, chỉ là nội dung dần kém liên quan. Hậu quả hiện ra ở chỗ khác hẳn, dưới dạng mô hình bịa giá trị vì thứ nó cần không có trong prompt |
| **Code làm** | `GoldenCase`, `GoldenSet`, `RetrievalReport`; `retrieval_golden.yaml` ở tầng dự án; hai chunk nhiễu có chủ ý; lệnh `eaa report retrieval` |
| **Vì sao precision@k chứ không recall** | Prompt chỉ có chỗ cho k trích đoạn, nên câu hỏi đúng là "trong k cái được chọn, bao nhiêu cái liên quan". Recall đo một thứ mà ngân sách token vốn đã chặn |
| **Mẫu số là số chunk THẬT SỰ chọn** | Chia cho k khi kho chưa đủ chunk là phạt bộ chọn vì một chỗ thiếu của kho — một phép đo đổ lỗi nhầm chỗ |
| **Chunk nhiễu phải KHÓ** | `ds-023` (TWI chế độ slave) đúng về nội dung, đã duyệt G2, cùng ngoại vi, chia sẻ một thanh ghi — mà vẫn vô can. Chunk nhiễu ngây thơ (nói về ngoại vi chẳng ai dùng) không đo được gì: bộ chọn theo quan hệ loại nó ngay |

### Lỗi mà TC-20 tìm ra ngay lượt chạy đầu tiên

| | |
|---|---|
| **Quan sát** | precision@3 = **0,889** (dưới ngưỡng 0,9), và `ds-023` đẩy `ds-031` — trích đoạn khởi động chính con cảm biến — ra khỏi ba chỗ của prompt |
| **Nguyên nhân gốc** | `KnowledgeGraph.build` nối cạnh `configured_by` cho **ngoại vi** nhưng không cho **linh kiện**. Nên trích đoạn về cảm biến chỉ được nối qua quan hệ "module dùng linh kiện" — yếu hơn hẳn — và thua một trích đoạn chỉ tình cờ chia sẻ MỘT thanh ghi của bus |
| **Sửa** | Linh kiện cũng nhận cạnh `configured_by`; `hardware_profile.yaml` khai `configured_by` cho `imu`. precision@3 lên **1,000**, không chunk nhiễu nào lọt |
| **Một quyết định đi kèm** | Danh sách chỉ có bốn thanh ghi của phần nhận dạng/khởi động — đúng phần `ds-031` đã qua G2. Thanh ghi cấu hình dải đo thuộc `ds-032` còn ở trạng thái proposed; khai chúng bây giờ sẽ khiến Readiness Check chặn vòng sinh mã, và chặn ĐÚNG |
| **Vì sao đáng ghi lại** | Đây là loại lỗi mà không test nào khác bắt được: mọi test cũ vẫn xanh, prompt vẫn lắp được, chỉ là nội dung sai chỗ. Nó lộ ra đúng vào lượt chạy đầu tiên của phép đo sinh ra để bắt nó |
| **Test** | TC-20a..d |

## SL-62 · BỔ SUNG · `ScopeImageReader` — ảnh màn hiện sóng thành số đo (TC-23)

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1, FR-ING-03; **TC-23** — test case của thiết kế, tới bản này mới có |
| **Chỗ trống** | `ingest.py` phân loại được đầu vào ảnh và giữ được ảnh gốc, nhưng không có gì đọc ảnh thành số đo. FR-ING-03 đặc tả đầy đủ mà không có nơi cài đặt |
| **Code làm** | `ProposedMeasurement`, `ScopeImageReader`; trường `Prompt.image_path`; lệnh `eaa scope-image` |
| **Ba trường quyết định tệp này có ích hay có hại** | `uncertainty` — sai số ĐỌC ẢNH, và thiếu nó thì số đọc từ ảnh trông y hệt số máy đo gửi về · `reading` — thấy gì trên ảnh để ra con số ấy, để người kiểm lại mà không cần tin · `status` luôn là `proposed` |
| **Người sửa được trước khi lưu** | `accept(value, actor=...)` nhận giá trị NGƯỜI chốt, và bản ghi giữ **cả hai** con số kèm cờ `edited`. Nếu về sau số đo gây tranh cãi, câu "máy đọc ra bao nhiêu, người sửa thành bao nhiêu" phải trả lời được từ dữ liệu |
| **Không đọc được là kết cục hợp lệ** | Một con số bịa ra kèm đơn vị đúng còn tệ hơn không có con số nào |
| **Ảnh gốc giữ lại trước khi trích** | Câu "máy đọc nhầm ảnh" chỉ kiểm chứng lại được khi ảnh còn đó |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/goldenset.py`, `retrieval_golden.yaml`, `measurements.jsonl`, lệnh `eaa scope-image` và `eaa report retrieval` |
| **Test** | TC-23a..d |

---

## SL-63 · LỆCH THẬT · Đồ thị tri thức không nối thanh ghi cho LINH KIỆN

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §5 (Knowledge Graph), ADR-08; FR-KG-01 |
| **Thiết kế nói** | Node MCU / Peripheral / Register / Pin, cạnh `has` / `configured_by` / `outputs_on` được suy từ hồ sơ phần cứng |
| **Code làm (trước)** | `KnowledgeGraph.build` nối `configured_by` cho **ngoại vi**, nhưng linh kiện chỉ nhận `on_bus` và `connects_to`. Nên một cảm biến trên bus — thứ có bảng thanh ghi của riêng nó — không có đường nào nối tới trích đoạn tài liệu nói về nó |
| **Hậu quả quan sát được** | Với `drv_bus_sensor`, trích đoạn khởi động cảm biến (`ds-031`) bị một trích đoạn về **chế độ slave của bus** (`ds-023`) đẩy khỏi top-3, chỉ vì cái sau tình cờ chia sẻ một thanh ghi. precision@3 = 0,889 |
| **Vì sao xếp loại LỆCH THẬT** | Đây không phải chỗ trống của tài liệu. Thiết kế mô tả một đồ thị nối *thanh ghi với thứ cấu hình nó*; code chỉ hiện thực một nửa danh mục thứ ấy, và nửa thiếu là nửa mà Graph-RAG dựa vào nhiều nhất |
| **Code làm (nay)** | Linh kiện cũng nhận cạnh `configured_by`. precision@3 lên 1,000 |
| **Phát hiện bởi** | TC-20, ngay lượt chạy đầu tiên — xem SL-61 |
| **Cần cập nhật** | EAA-AIS-05 §5.1: nêu rõ `configured_by` xuất phát từ **cả** ngoại vi lẫn linh kiện |

## SL-64 · BỔ SUNG · `Prompt.image_path` — đường đi của ảnh vào prompt

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §2 (lược đồ Prompt), §6.1; FR-ING-01/03 |
| **Chỗ trống** | AIS đặc tả thu nhận đa phương thức và đọc ảnh màn hiện sóng, nhưng lược đồ `Prompt` chỉ có lớp văn bản — không có chỗ nào cho ảnh đi qua |
| **Code làm** | Thêm trường `image_path` vào `Prompt` |
| **Là ĐƯỜNG DẪN, không phải nội dung** | Adapter tự quyết mã hóa thế nào cho nhà cung cấp của nó, và giữ đường dẫn ở đây nghĩa là ảnh gốc vẫn nằm nguyên trong kho — điều kiện để câu "máy đọc nhầm ảnh" kiểm chứng lại được. Adapter không hỗ trợ ảnh thì bỏ qua trường này, không vỡ |
| **Cần cập nhật** | EAA-AIS-05 §2: thêm `image_path` vào lược đồ Prompt |
| **Test** | TC-23 (`test_tc23_anh_di_kem_prompt`) |

---

## SL-65 · LỆCH THẬT · `eaa/agent.py` — vòng hội thoại, và trí nhớ phiên

| | |
|---|---|
| **Tài liệu** | EAA-MDD-00 §"quyết định đã chốt": *"không trí nhớ hội thoại — stateless call + Project State"*; EAA-AIS-05 §2; ADR-03 |
| **Thiết kế nói** | Mô hình được gọi **stateless** mỗi lần; ngữ cảnh lắp lại từ Knowledge Base + Project State. Mặt tiếp xúc là các lệnh CLI rời |
| **Code làm** | Thêm `eaa chat`: người nói bằng tiếng Việt, Agent tự chọn và chạy lệnh, đọc kết quả, lặp, rồi trả lời |
| **Phần LỆCH** | Xuất hiện một lớp ngữ cảnh mới — **bản ghi phiên** — mà thiết kế gốc không có |
| **Phần KHÔNG lệch** | Mỗi lượt vẫn là MỘT lời gọi độc lập. "Trí nhớ" nằm ở phía engine, dựng lại mỗi lượt từ Project State + bản ghi phiên bị cắt theo ngân sách token, đúng cách Composer vẫn lắp ngữ cảnh. **Không có trạng thái nào nằm phía nhà cung cấp mô hình** — đó mới là điều quyết định ấy bảo vệ |
| **Ghi vết** | Toàn bộ lượt hỏi ghi ra `chat_log.jsonl`: câu hỏi, lệnh đã chạy, mã thoát, đầu ra, câu trả lời. Phiên nào cũng dựng lại được |

### Hàng rào dựng bằng cấu tạo, không bằng lời dặn

| | |
|---|---|
| **Rủi ro** | Tầng hội thoại là đúng loại thứ phá được bất biến trung tâm một cách êm ái: mô hình "hiểu" rằng người dùng muốn duyệt, rồi tự gọi `gate approve` |
| **Cách chặn** | `TOOLBOX` — danh mục lệnh Agent được gọi — **không chứa** `gate approve/reject`, `flash`, `doctor --fix`, `tune`, `rollback`, `endurance`, `build`, `gen`, `telemetry`, `ports`, `scope-image`, `datasheet add`, `docs regen`. Vòng lặp từ chối mọi thứ ngoài danh mục |
| **Vì sao là cấu tạo** | Danh mục là **dữ liệu**: đọc được, kiểm được bằng test, và thêm một lệnh vào đó là một thay đổi nhìn thấy trong lịch sử Git — không phải một nhánh rẽ trong hàm. Prompt cũng dặn, nhưng lời dặn chỉ là hàng rào thứ hai |
| **`gen` bị loại có lý do riêng** | Nó ghi vào `kpi_log.csv`, và những dòng ấy là **dữ liệu thí nghiệm của Chương 3**. Agent tự khởi động sẽ chèn vào bảng số liệu những lượt chạy người làm thí nghiệm không định chạy |
| **Từ chối phải kèm lệnh** | Khi người nhờ làm việc ngoài quyền, Agent BẮT BUỘC dùng `de_nghi_nguoi_chay` và soạn lệnh cụ thể. Một lời từ chối không kèm lệnh bắt người đi tra tài liệu — đúng việc Agent có mặt để làm thay |
| **Trần số bước** | 8 bước mỗi lượt. Cùng tinh thần với vòng tự sửa ≤ 3: một vòng lặp không có trần là vòng lặp quay tới lúc hết tiền |
| **Giao thức JSON, không dùng function-calling** | Adapter Gemini gửi một lượt `contents` và trả văn bản. Dựng vòng lặp trên `complete()` khiến nó chạy với **mọi** adapter theo interface `LLMClient`, kể cả MockLLM và bộ phát lại — đúng điều ADR-03 đòi |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/agent.py`, `chat_log.jsonl`, lệnh `eaa chat`; EAA-MDD-00: ghi chú quyết định "không trí nhớ hội thoại" áp cho phía nhà cung cấp, không cấm engine tự dựng lại ngữ cảnh phiên |
| **Test** | TC-61a..g |

---

## SL-66 · BỔ SUNG · `eaa/rag.py` — BM25 làm tầng 2 của truy xuất (ADR-07)

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §4.2, ADR-07; **SL-06** ghi module này là "hoãn có chủ ý" từ Sprint 1 |
| **Chỗ trống** | Truy xuất chỉ có tầng quan hệ. Trích đoạn có nội dung liên quan mà đồ thị chưa có cạnh nào dẫn tới thì không bao giờ vào được prompt — và đó đúng là cảnh xảy ra khi dự án quên khai `configured_by` cho một linh kiện, chính là lỗi TC-20 tìm ra ở SL-63 |
| **Code làm** | `Bm25Index` (cài thẳng theo công thức, không phụ thuộc thư viện ngoài), `select_chunks` hai tầng; Composer và bộ chuẩn TC-20 đều đi qua nó |
| **Thứ tự không đảo được** | Quan hệ trước — nó đúng theo định nghĩa, không theo xác suất. BM25 chỉ lấp chỗ CÒN TRỐNG và không đẩy được ai ra. Chạy BM25 trước sẽ đưa một trích đoạn "gần giống" lên trên một trích đoạn mà đồ thị chỉ đích danh |
| **Không tách theo gạch dưới** | Tên thanh ghi là một định danh nguyên khối; tách ra thì mỗi mảnh là một từ ba chữ cái trùng hàng chục thứ khác. Đây là chỗ bộ tách từ ngôn ngữ tự nhiên làm hỏng tài liệu kỹ thuật |

### Một lỗi thiết kế phải trả giá mới thấy

| | |
|---|---|
| **Bản đầu** | Dùng **sàn điểm BM25** tuyệt đối (1,0) để quyết định nhận hay loại |
| **Sai ở đâu** | Điểm BM25 phụ thuộc cỡ kho qua thành phần idf. Test dựng kho hai tài liệu cho thấy một trích đoạn **khớp hoàn hảo** chỉ đạt ~0,29 điểm — dưới sàn, nên bị loại. Cùng mức khớp ấy trong kho năm mươi tài liệu sẽ đạt vài điểm |
| **Hệ quả nếu để nguyên** | Sàn quá chặt lúc kho còn nhỏ và quá lỏng khi kho lớn lên — sai ở **cả hai đầu** vòng đời dự án, và sai theo cách chỉ lộ ra sau nhiều tháng |
| **Sửa** | Ngưỡng nhận đổi sang **độ phủ từ khóa** (≥ 1/3 số từ khác nhau của câu truy vấn). Không phụ thuộc cỡ kho, và nói thẳng điều ta muốn hỏi. Điểm BM25 giữ lại nhưng chỉ để **xếp hạng** những ứng viên đã qua ngưỡng |
| **Hai đại lượng, hai việc** | Độ phủ quyết định *có nhận không*; điểm quyết định *xếp trước hay sau*. Dùng một đại lượng cho cả hai việc là chỗ bản đầu sai |
| **Đo được** | precision@3 trên bộ chuẩn giữ nguyên 1,000; `drv_timer_tick` vẫn chỉ trả 1 trích đoạn — bộ chọn vẫn "biết dừng" |
| **Test** | TC-64a..g |

## SL-67 · BỔ SUNG · Bậc hai hiểu ngữ nghĩa cho chọn kịch bản và truy hồi phẩm xuất

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7.3 ("chọn kịch bản từ mô tả triệu chứng"), FR-DOC-03 ("truy hồi bằng mô tả tự nhiên") |
| **Khoảng cách** | Cả hai chỗ nhận câu tiếng Việt tự do nhưng xử lý bằng **khớp chuỗi con**. Tài liệu gọi là "mô tả tự nhiên", nên người đọc dễ hiểu thành hiểu ngữ nghĩa — trong khi *"bánh xe đứng im"* trượt sạch dù nghĩa y hệt *"động cơ không quay"* |
| **Code làm** | `ScenarioLibrary.select_smart`, `ArtifactRegistry.find_smart` |
| **Bậc 1 vẫn chạy trước và vẫn thắng** | Tất định, rẻ, và **kiểm lại được** — nhìn là biết từ nào đã khớp. Hỏi mô hình cho mọi câu sẽ ném bỏ tính chất ấy để đổi lấy thứ chỉ cần khi bậc 1 trượt, và tốn tiền cho những ca một phép so chuỗi đã trả lời đúng |
| **Không trộn hai bậc** | Mỗi kết quả mang theo bậc đã tìm ra nó. Kết quả bậc 2 được in kèm chữ *PHỎNG ĐOÁN* và mức tin cậy GIẢ ĐỊNH, vì một kịch bản mô hình đoán ra là khẳng định yếu hơn hẳn một kịch bản khớp đúng từ dự án đã khai |
| **Mô hình bịa mã thì bị loại** | Bịa ở đây đặc biệt tệ: người sẽ đi nạp một firmware chẩn đoán không tồn tại |
| **Test** | TC-62a..f |

## SL-68 · BỔ SUNG · `Judged` — hợp đồng mức tin cậy, và test canh độ phủ (N-903)

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1, §12; nghiệp vụ N-903 |
| **Trạng thái trước** | SL-57 dựng bộ từ vựng chung nhưng mới năm chỗ dùng nó; N-903 vẫn ở mức MỘT PHẦN vì "mọi đầu ra" chưa kiểm được |
| **Code làm** | Protocol `Judged`, hàm `describe()` và `header()`; **23 lớp mang kết luận** expose `confidence_level` |
| **Cách "mọi đầu ra" trở nên kiểm được** | TC-63 liệt kê các lớp kết luận và đòi từng lớp có nhãn hợp lệ. Thêm một tính năng sinh kết luận mới mà quên gắn nhãn thì test đỏ — chứ không đợi ai đó tình cờ nhận ra |
| **Test tự nó tìm ra hai chỗ** | `VerifyResult` đặt tên thuộc tính là `confidence` chứ không phải `confidence_level`; `DeviceCheck` chưa có nhãn nào |
| **Mức do MỤC YẾU NHẤT quyết định** | Bảng kiểm mười mục CÓ và một mục MÂU THUẪN thì cả bảng chỉ chắc tới mức mục mâu thuẫn ấy — vì module sắp sinh ra sẽ dùng đúng giá trị đang tranh chấp |
| **Nhãn đứng ở ĐẦU báo cáo** | Người đọc quyết định tin tới đâu **trước** khi đọc nội dung. Một bản đọc hết rồi mới thấy dòng "đây chỉ là phỏng đoán" thì dòng ấy tới muộn |
| **Test** | TC-63a..e |

---

## SL-69 · BỔ SUNG · `eaa/archive.py` — Agent đọc được kho nén hồ sơ dự án

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1 (FR-ING-01: nhận và phân loại bốn loại đầu vào), §6.3; nghiệp vụ N-004 |
| **Chỗ trống** | `ingest.py` nhận PDF, ảnh, mã nguồn — **từng tệp một**. Nhưng hồ sơ gốc của một dự án hiếm khi tới từng tệp: nó tới dưới dạng một kho nén. Người dùng phải tự giải, tự nhìn, tự chọn tệp nào đáng nạp — tức là làm xong phần khó trước khi nhờ được |
| **Phát hiện bởi** | Bài test tổng hợp trên hồ sơ robot BLKLab (`docs/NHAT_KY_TEST_BLKLAB.md`). Vòng 0: Agent từ chối, **không bịa** mô tả mạch dù tên tệp thừa sức gợi ý |
| **Code làm** | `ArchiveSurvey`, `read_archive`, `extract_archive`; lệnh `eaa survey <zip> [--extract]`; vào danh mục `eaa chat` |
| **Ba việc** | ① giải nén an toàn — chặn zip-slip, liên kết mềm, bom nén, **trước khi ghi byte nào** ② phân loại theo bốn loại của FR-ING-01 ③ rút dữ kiện XÁC ĐỊNH từ mã nguồn bằng biểu thức chính quy, không dùng mô hình — nên chúng tất định và kiểm lại được |
| **Tách mã dự án khỏi thư viện đi kèm** | Hồ sơ thật kèm cả cây `libraries/` của bên thứ ba, và mã ví dụ trong đó khai đủ thứ chân chẳng liên quan. Lượt chạy đầu trên hồ sơ BLKLab cho 68 "khai báo chân" trong đó phần lớn là của thư viện NeoPixel; tách ra còn **39 khai báo, 6 thư viện, 6 thanh ghi** — tất cả đều của con robot |
| **Dữ kiện phải chỉ được nguồn** | Mỗi `CodeFact` mang tệp và số dòng. Một dữ kiện không chỉ được nguồn thì không hơn gì lời đồn |
| **Điều nó KHÔNG làm** | Không kết luận "đây là bo X". Nó bày ra thứ đọc được và đánh dấu tất cả là *proposed*. Suy từ vài dòng `#define` ra một khẳng định về phần cứng là đúng loại bước nhảy sản phẩm này sinh ra để chặn — và đặc biệt dễ ở đây, vì một kho nén trông như một nguồn đáng tin |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/archive.py`, lệnh `eaa survey`; EAA-AIS-05 §6.1: kho nén là loại đầu vào thứ năm, hoặc là cái vỏ đựng bốn loại kia |

## SL-70 · BỔ SUNG · `eaa capabilities` — một chỗ trả lời "Agent làm được gì"

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9 (môi trường công cụ), FR-ENV-01, NFR-05 |
| **Chỗ trống** | Câu "Agent này làm được gì, cái nào đang chạy được" phải ghép từ **bốn chỗ**: `eaa --help`, `eaa/agent.py`, `eaa packs`, `eaa doctor`. Bốn chỗ đều đúng và không chỗ nào trả lời trọn — người mới đến phải đọc mã trước khi biết mình có gì trong tay |
| **Code làm** | `survey_capabilities()`, `CapabilityReport`; lệnh `eaa capabilities [--verbose]`; vào danh mục `eaa chat` để Agent tự trả lời được câu ấy |
| **Bốn tầng, bốn cách hỏng** | ① lệnh CLI — hỏng nghĩa là bản cài hỏng ② lệnh Agent tự gọi — ranh giới này là quyết định về QUYỀN, không về kỹ thuật ③ năng lực nền tảng — thiếu thì thêm pack, KHÔNG sửa engine ④ công cụ ngoài — thiếu thì `doctor --fix`. Bảng in ra **cả cách bổ sung cho từng tầng**, vì trộn chúng lại là cách nhanh nhất để người dùng đi sửa nhầm chỗ |
| **Dựng từ dữ liệu thật** | Danh sách lệnh đọc từ chính bộ phân tích đối số, năng lực nền tảng đọc từ `pack.yaml`, công cụ ngoài kiểm bằng `shutil.which`. Chép tay thì bảng lệch ngay lần thêm lệnh sau — và một bảng năng lực tự nó sai còn tệ hơn không có bảng |
| **Nói rõ giới hạn của chính nó** | Bảng kiểm **sự có mặt**, không chạy thử năng lực nào. Câu "nó chạy đúng không" thuộc về bộ test và `kiem_on_dinh.py`, và bảng nói thẳng điều đó thay vì để người đọc tưởng mình vừa được kiểm chứng |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/capabilities.py`, lệnh `eaa capabilities` |

## SL-71 · BỔ SUNG · `eaa/web.py` — Agent đi đọc thật, không đọc từ trí nhớ mô hình

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2 bậc 3, §9.2, §12; FR-GAP-02, NFR-06 |
| **Chỗ trống** | Engine chỉ mở mạng tới đúng một nơi: API mô hình. Bậc 3 của `eaa/gapsearch.py` mang tên "tra nguồn trên web" nhưng thực chất là *hỏi mô hình rồi lọc tên miền của URL mà chính mô hình khai ra*. Kiểm nguồn thì có, **đi tìm thì không** — và tài liệu công bố sau ngày cắt dữ liệu huấn luyện thì mô hình không có gì để khai |
| **Code làm** | `WebFetcher`, `WebDocument`, `WebCache`, `html_to_text`, `classify`; lệnh `eaa read` |
| **Hai hạng, không một danh sách trắng** | `chính chủ` (miền nhà sản xuất) → nội dung được phép thành trích đoạn tri thức `proposed`. `mở` (phần còn lại) → tải được, đọc được, dùng để gỡ lỗi và so công cụ, nhưng `usable_as_knowledge` là `False`. Một danh sách trắng duy nhất buộc phải chọn giữa hai cái sai: chặt thì không tra được lỗi cài đặt, lỏng thì một bài blog thành nguồn cho giá trị thanh ghi |
| **Bốn cái chặn** | ① chỉ http/https, phân giải tên miền TRƯỚC khi nối và từ chối mọi địa chỉ nội bộ (SSRF) ② **kiểm lại hạng ở từng chặng chuyển hướng** — một URL chính chủ chuyển hướng ra ngoài phải mất hạng, đây là cách một danh sách trắng bị vượt mà trông vẫn đúng ③ trần byte và trần thời gian ④ công tắc ngắt `EAA_NO_NET=1` |
| **Chính chủ vẫn KHÔNG phải ĐÃ KIỂM** | Thứ kiểm được khi tải một trang là nó **từ đâu ra**, không phải nó **nói đúng không**. Nhãn là SUY RA; lên ĐÃ KIỂM chỉ sau khi qua gate tri thức |
| **Bộ đệm để tái lập, không để nhanh** | Nội dung lưu kèm băm và mốc thời gian, nên "trang này lúc ấy nói gì" là câu trả lời được sau vài tháng |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/web.py`, lệnh `eaa read` |

## SL-72 · BỔ SUNG · `eaa/websearch.py` — tìm kiếm trả ĐỊA CHỈ, không trả kết luận

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2 bậc 3, §9.2, §12; FR-GAP-02, FR-ENV-03 |
| **Chỗ trống** | Không có đường nào biến một khoảng trống năng lực thành một truy vấn rồi đi tìm |
| **Code làm** | `SearchHit`, `JsonEndpointSearch`, `GeminiGroundedSearch`, `ChainSearch`, `WebResearcher`, `restrict_to_sites`; lệnh `eaa research`; `GeminiClient.search_web()` |
| **Tách tìm khỏi đọc** | Máy tìm kiếm trả **địa chỉ**; nội dung do `eaa/web.py` tải về qua bộ kiểm nguồn. Gộp hai việc là quay lại đúng chỗ vừa rời khỏi: một đoạn văn trôi chảy do mô hình viết, đính kèm URL trông đàng hoàng, không ai biết đoạn văn có thật lấy từ URL ấy không |
| **ĐO ĐƯỢC 30/08/2026 · công cụ được bật ≠ công cụ được dùng** | Gửi thẳng câu truy vấn kèm công cụ tìm kiếm thì model **không tìm** — nó trả lời từ trí nhớ và `groundingMetadata` rỗng. Cũng câu ấy, thêm một câu lệnh tìm rõ ràng thì có 14–16 `groundingChunks`. Đây là kiểu hỏng im lặng tệ nhất: hàm vẫn trả về, chỉ là trả về thứ lấy từ trí nhớ. Câu lệnh tìm vì thế nằm trong adapter, không để bên gọi tự nhớ |
| **ĐO ĐƯỢC · URL bọc qua trạm chuyển hướng** | Công cụ tìm kiếm gắn sẵn KHÔNG trả URL thật mà trả `…/grounding-api-redirect/<mã>`. Phân hạng theo URL bọc thì **mọi** kết quả rơi xuống hạng mở, kể cả datasheet gốc, và bộ lọc "chỉ chính chủ" lọc sạch mọi thứ. Tên miền thật nằm ở trường tiêu đề → dùng làm gợi ý phân hạng, và gợi ý chỉ có hiệu lực cho URL bọc |
| **ĐO ĐƯỢC · phải hỏi đúng nơi mới có cái để lọc** | Một câu hỏi về thanh ghi trả về gần như toàn diễn đàn và trang chia sẻ tài liệu — không trang nhà sản xuất nào trong tám kết quả đầu. Hạng tin cậy lọc được rác ấy *sau* khi tìm, nhưng lọc xong thì không còn gì. Nên `restrict_to_sites()` sửa **câu hỏi**, không sửa bộ lọc |
| **Không nguồn nào thì BÁO LỖI** | `NullSearch` ném lỗi kèm cách bật, không trả danh sách rỗng — rỗng sẽ bị hiểu nhầm thành "tìm rồi, không có gì" |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/websearch.py`, lệnh `eaa research` |

## SL-73 · BỔ SUNG · `eaa/environ.py` — máy này là máy gì

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.1, FR-ENV-01 |
| **Chỗ trống** | `doctor` biết kiểm **những công cụ đã có trong Tool Manifest**, không biết gì về máy đang chạy nó: kiến trúc CPU, quyền quản trị, mạng, đĩa. Hệ quả không lý thuyết — một lệnh cài chép đúng từ tài liệu vẫn hỏng vì máy dùng chip ARM chứ không phải x86, và Agent chỉ biết sau khi đã chạy và đã hỏng |
| **Code làm** | `EnvironmentReport`, `NetworkCheck`, `probe()`, `TRINH_QUAN_LY_GOI`; lệnh `eaa environ [--remember]` |
| **Mạng là PHÉP ĐO** | Thử nối TCP thật, hạn giờ 3s → nhãn ĐÃ KIỂM. Khác hẳn đọc biến proxy rồi đoán. Kể từ khi có `eaa/web.py`, gần như mọi năng lực mới đều treo vào mạng; một Agent không biết mình có mạng hay không sẽ hứa "để tôi đi tra" rồi im lặng hỏng sau hai mươi giây |
| **Nói ra HỆ QUẢ, không chỉ nói ra số** | Không có trình cài gói → `doctor --fix` sẽ không đề xuất được lệnh nào. Mất mạng → mọi năng lực tra cứu sẽ hỏng. Một bảng thông số mà người đọc phải tự suy ra điều đó là bảng chưa làm xong việc |
| **Che thông tin đăng nhập trong proxy** | `http_proxy` hay chứa `user:mật_khẩu@host`. `mask_secrets` che thứ giống khóa API nhưng không biết gì về phần userinfo của URL — hai kiểu bí mật, hai bộ che (NFR-06) |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/environ.py`, lệnh `eaa environ` |

## SL-74 · BỔ SUNG · `eaa/memory.py` — bộ nhớ liên dự án

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7, §11; FR-KB-04 |
| **Chỗ trống** | Mọi kho tri thức đều nằm TRONG một dự án. Đúng cho tri thức phần cứng, nhưng có một lớp thứ hai không thuộc dự án nào: máy này có gì, công cụ nào đã cài, lỗi nào đã gặp. Lớp ấy bị dựng lại từ đầu ở mỗi dự án — một Agent quên sạch sau mỗi dự án thì mọi thứ nó "học" chỉ là cách nói |
| **Code làm** | `MemoryFact`, `MemoryStore`, `scope_du_an()`, `scope_mcu()`; lệnh `eaa memory list/add` |
| **Cùng kỷ luật với kho dự án** | Append-only + supersede, không ghi đè vật lý. `superseded_by` **không** nằm trong tệp — nó suy ra lúc đọc từ `supersedes` của bản sau; ghi nó vào tệp sẽ buộc sửa dòng cũ, đúng cái append-only sinh ra để cấm |
| **Phạm vi phải khai rõ** | `toàn cục` / `mcu:<họ>` / `dự án:<tên>`. `relevant()` **không** trả về sự kiện của dự án khác — đó là chỗ một bộ nhớ dùng chung gây hại nhất: một bài học rút từ bo A đem áp lên bo B mà không ai kịp hỏi nó còn đúng không |
| **Không bao giờ ĐÃ KIỂM** | Sự kiện nhớ từ lần trước có thể đã cũ: máy đã đổi, công cụ đã gỡ. Có bằng chứng → SUY RA; không có → GIẢ ĐỊNH |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/memory.py`, lệnh `eaa memory` |

## SL-75 · BỔ SUNG · `eaa/playbook.py` — sổ tay lỗi

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7, §12; FR-KB-04, NFR-08 |
| **Chỗ trống** | Vòng tự sửa sửa xong hàng trăm lỗi rồi vứt đi thứ đắt nhất nó vừa tạo ra: cặp **(lỗi này → cách sửa này đã hiệu quả)**. Lần sau gặp đúng lỗi ấy, Agent lại đốt một lượt gọi mô hình để nghĩ lại từ đầu |
| **Code làm** | `PlaybookEntry`, `Playbook`, `signature()`, `normalise()`; lệnh `eaa playbook list/lookup/record` |
| **Vân tay: bỏ phần thay đổi, giữ phần lặp** | Hai lần gặp cùng một lỗi thì thông báo gần như không bao giờ giống hệt: khác đường dẫn, số dòng, địa chỉ. Chuẩn hóa bỏ đường dẫn / số dòng / hex / phiên bản / chuỗi trong nháy, **giữ** từ mang nghĩa (`undefined reference`, `permission denied`) |
| **Hai bộ đếm, không một** | Một cách sửa từng hiệu quả một lần không có nghĩa nó luôn hiệu quả. Xếp theo tỉ lệ trúng (làm mềm Laplace) chứ không theo thời gian. Một sổ tay chỉ ghi thành công sẽ tự tin dần lên theo hướng sai — và tự tin nhất đúng ở chỗ nó sai nhiều nhất |
| **Không tự áp cách sửa** | `lookup()` trả gợi ý; patch vẫn phải qua đủ cổng. Bỏ qua cổng vì "lần trước cách này chạy được" là đúng loại lối tắt cả hệ thống này dựng ra để chặn |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/playbook.py`, lệnh `eaa playbook` |

## SL-76 · BỔ SUNG · `eaa/installerr.py` — cài hỏng thì làm gì

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.2, §9.4; FR-ENV-02, FR-ENV-04 |
| **Chỗ trống** | `doctor --fix` biết in lệnh cài và hỏi người, không biết gì về việc lệnh ấy hỏng: mọi thất bại ra cùng một dòng "lệnh trả mã khác 0" |
| **Code làm** | `classify()`, `InstallDiagnosis`, `remedies()`, `rollback_command()`, `retry_delays()` |
| **Sáu loại, sáu cách xử lý** | mạng (thử lại hợp lý) · quyền (thử lại vô ích, và mãi cũng vô ích) · phụ thuộc (phải cài thứ khác TRƯỚC) · build (thiếu trình biên dịch / tệp tiêu đề) · không tìm thấy (sai tên gói) · khác |
| **Thứ tự mẫu quan trọng** | BUILD hẹp đứng **trước** "không tìm thấy": `Python.h: No such file or directory` chạm cả hai, và đọc nó thành "không có gói tên Python.h" đẩy người dùng đi tìm một gói không tồn tại. Ngược lại, `no such file or directory` trần bị **bỏ khỏi** bộ dấu hiệu — một dấu hiệu khớp mọi thứ là một dấu hiệu vô dụng |
| **Thang gỡ luôn dừng ở con người** | Rẻ trước, đắt sau, và **không bậc nào cho Agent tự chạy lệnh cài** — cài phần mềm là đổi máy người dùng (N-022 ở mức T2). Đây không phải hạn chế tạm thời chờ ai gỡ |
| **Quay lui suy ra, không chép** | `rollback_command()` suy lệnh gỡ từ chính lệnh cài; không suy được thì trả **rỗng**. Một lệnh gỡ đoán sai chạy với quyền quản trị tệ hơn hẳn không có lệnh gỡ nào |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/installerr.py` |

## SL-77 · BỔ SUNG · `eaa/toolforge.py` — Agent tự viết công cụ cho chính nó

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9, §12; FR-ENV-03, NFR-05, NFR-06 |
| **Chỗ trống** | Agent sinh mã nhúng qua sáu cổng kiểm chứng, nhưng bốn mươi công cụ của **chính nó** đều do người gõ tay. Gặp một việc lặp lại mà chưa ai viết lệnh cho, nó chỉ biết bảo người dùng tự làm |
| **Code làm** | `ForgedTool`, `ToolRegistry`, `ToolForge`, `check_structure()`, `check_safety()`, `run_tests()`; lệnh `eaa tool list/propose/verify/approve/run` |
| **Mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ** | Quyền chạy công cụ tự sinh là **một** mục tĩnh trong `TOOLBOX` (`tool run`), nằm trong Git, đổi bằng một commit. **Danh sách** công cụ là dữ liệu, và mỗi mục chỉ chạy được sau khi một người bấm duyệt. Hai thứ ấy hay bị gộp làm một, và gộp lại là mất luôn tính kiểm được |
| **Ba cổng, dừng sớm khi trượt** | ① cấu tạo: phải có `run()`, `SCHEMA`, `MO_TA`, ít nhất một `test_` ② an toàn: quét cấu trúc cấm và bí mật nhúng ③ chạy thử: tiến trình riêng, thư mục riêng, hạn giờ, `EAA_NO_NET=1`, và **xóa khóa API khỏi môi trường con**. Trượt cổng 2 thì KHÔNG chạy cổng 3 — chạy một đoạn mã vừa trượt cổng an toàn là đúng thứ cổng ấy sinh ra để ngăn |
| **Quét theo cây cú pháp, không theo chuỗi con** | Quét chuỗi con thì `compile` trong danh sách cấm chặn cả `re.compile` — cấu trúc hợp lệ phổ biến nhất của loại công cụ này — và `socket` chặn cả một dòng chú thích. **Một cổng an toàn hay báo nhầm thì sớm muộn cũng bị người ta tắt đi, và lúc ấy nó không bảo vệ được gì nữa** |
| **Duyệt chỉ đi từ `verified`** | Không có đường tắt từ `proposed`: duyệt một công cụ chưa từng chạy thử thì chữ "duyệt" không nói lên điều gì |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/toolforge.py`, lệnh `eaa tool` |

## SL-78 · BỔ SUNG · `eaa/scratch.py` — chỗ làm nháp, hạ cửa vào mà không hạ cổng

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-PLT-03, EAA-MDD-00 §6 |
| **Chỗ trống** | **34/38 lệnh đòi một dự án đầy đủ** — `constraints.yaml` và `hardware_profile.yaml` phải có sẵn trước lệnh đầu tiên. Đúng cho sản phẩm sắp bàn giao, sai cho câu người ta thật sự mở công cụ ra để hỏi: *"viết giúp tôi một hàm đọc kênh này"*. Cửa vào cao ở đúng chỗ người dùng chưa có gì để điền |
| **Code làm** | `create_scratch()`, `is_scratch()`, `warning_banner()`; lệnh `eaa scratch` |
| **KHÔNG tắt cổng nào** | Chỗ làm nháp là một dự án **thật, đầy đủ**, chỉ khác ở chỗ phần YAML khuôn mẫu được sinh ra thay vì bắt người gõ. Rào cản hạ bằng cách giảm **việc phải gõ**, không phải giảm **việc phải kiểm** |
| **Vì sao không làm cách dễ hơn** | Cách "dễ" — một cờ cho phép bỏ qua cổng khi làm nháp — phá đúng bất biến trung tâm: *merge chỉ khi toàn bộ `ToolReport.passed` và G3 approved*. Một cờ bỏ qua tồn tại là một cờ sẽ được dùng, và nó sẽ được dùng đúng vào lúc gấp |
| **Ràng buộc sinh sẵn mang nhãn GIẢ ĐỊNH** | Ghi thẳng trong tệp và nhắc lại ở banner. Một con số mặc định trông y hệt một con số đã chốt, và đó là cách một bản nháp lặng lẽ trở thành một bản bàn giao |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/scratch.py`, lệnh `eaa scratch` |

## SL-79 · LỆCH THẬT · Bậc 3 của `gapsearch` đổi hợp đồng: đọc trước, trích sau

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2 bậc 3; TC-24, TC-48 |
| **Trước** | Hỏi mô hình → mô hình trả JSON kèm một URL nó tự nêu → lọc tên miền của URL ấy → ghi thành chunk đề xuất |
| **Sau** | Tìm địa chỉ (hẹp về miền nhà sản xuất) → **TẢI trang về** → đưa **nội dung thật** cho mô hình trích xuất → **nguồn ghi vào chunk bắt buộc phải là một trong các URL đã tải được** |
| **Vì sao là LỆCH THẬT chứ không phải bổ sung** | Hợp đồng của bậc 3 đổi, và 4 bài TC-48 cũ phải viết lại. Hai chỗ hỏng của cách cũ: ① URL do mô hình sinh có thể không tồn tại, hoặc tồn tại mà không nói điều mô hình bảo nó nói — bộ lọc miền không phát hiện được cả hai ② tài liệu công bố sau ngày cắt dữ liệu thì mô hình không có gì để khai, và nó sẽ khai một thứ trông hợp lý |
| **Cái chặn quan trọng nhất** | Mô hình nêu một URL ngoài tập đã tải nghĩa là nó vừa quay về trả lời từ trí nhớ, và nội dung kèm theo không còn chỗ nào kiểm được → bỏ kết quả |
| **Bù lại** | `GapResolver` thêm `researcher` (tiêm được, để kiểm bậc 3 mà không chạm mạng) và `vendor_hint` (dữ liệu do bên gọi truyền xuống, không phải hằng số trong engine — FR-PLT-01) |
| **Cần cập nhật** | EAA-AIS-05 §6.2: mô tả lại bậc 3 theo thứ tự tìm → đọc → trích |

## SL-80 · BỔ SUNG · Đề xuất công cụ mang theo bằng chứng đã tải

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.2, §9.4 |
| **Chỗ trống** | `LlmToolResearcher` đề xuất công cụ hoàn toàn từ trí nhớ mô hình. Người duyệt không phân biệt được đề xuất dựa trên trang cài đặt thật với đề xuất dựa trên trí nhớ — hai thứ đáng tin khác hẳn nhau và **trông giống hệt nhau khi in ra** |
| **Code làm** | `ToolProposal.evidence`; `LlmToolResearcher.researcher` |
| **Cách làm** | Có bộ tra web → tìm và đọc trang cài đặt chính thức, đưa nội dung vào prompt, ghi URL vào `evidence`. Không đọc được → vẫn đề xuất, nhưng bản in **nói thẳng** rằng nó dựa vào trí nhớ mô hình và cần đọc kỹ hơn |
| **Không chặn khi mạng chập** | Chặn hẳn sẽ làm chế độ tìm công cụ ngừng hoạt động mỗi khi mạng hỏng — mà đó đúng lúc người ta cần nó nhất |
| **Cần cập nhật** | EAA-AIS-05 §9.2: đề xuất công cụ có hai mức bằng chứng |


## SL-81 · BỔ SUNG · `eaa/skills.py` — kỹ năng: GỘP quyền đã có, không cấp quyền mới

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9, §11; FR-ORC-01, NFR-08 |
| **Chỗ trống** | Agent đã tự viết được **công cụ** (SL-77). Nhưng phần lớn việc lặp lại không thiếu công cụ — nó thiếu **cách gọi một chuỗi công cụ đã có**. Trả lời "module này còn thiếu tri thức gì" luôn là cùng bốn lệnh theo cùng thứ tự; mỗi lần hỏi, Agent lại đi lại từ đầu và tốn một lượt gọi mô hình cho mỗi bước. Chuỗi ấy hiện bị đóng cứng trong quy trình G0→G10 hoặc nằm trong đầu người dùng |
| **Code làm** | `Skill`, `SkillStep`, `SkillRegistry`, `verify_skill()`, `mine()`; lệnh `eaa skill list/mine/verify/approve/run` |
| **BẤT BIẾN TRUNG TÂM của module** | **Mọi bước phải nằm trong `eaa/agent.py` `TOOLBOX`.** Không có nó, một kỹ năng tên "chốt xong module" với `gate approve` nhét ở giữa sẽ cấp cho Agent đúng cái quyền mà cả sản phẩm này dựng ra để giữ cho con người — bằng một dòng YAML không ai đọc kỹ. Kỹ năng là cách **gộp** quyền đã có, không phải cách **cấp** quyền mới |
| **Cổng quyền chạy HAI lần** | Lúc duyệt, và **lại lúc chạy**. Sổ là một tệp YAML sửa tay được: một kỹ năng đã duyệt rồi bị chèn thêm bước vẫn mang trạng thái `approved`. Cổng lúc duyệt bảo vệ quy trình; cổng lúc chạy bảo vệ lượt chạy này (có test canh) |
| **Ba cổng** | ① quyền ② tham số — chỗ giữ và khai báo khớp **cả hai chiều**; một tham số không ai dùng là một tham số người gọi sẽ điền nhầm chỗ ③ chạy khô — dựng đủ chuỗi lệnh cuối cùng để thấy chính xác cái gì sẽ chạy trước khi có gì chạy |
| **Khai thác từ nhật ký, không từ trí tưởng tượng** | `mine()` đọc `chat_log.jsonl` tìm chuỗi **thật sự đã lặp**. Đề xuất cho việc chưa ai làm bao giờ là đoán; đề xuất cho việc đã làm bốn lần là quan sát. Bỏ chuỗi con không mang thêm thông tin |
| **Dừng ở bước đầu tiên không đạt** | Bước sau chạy trên kết quả của bước trước hỏng là chạy trên nền cát. Bước khai `optional` thì được bỏ qua |
| **Sổ đặt ở DỰ ÁN, không ở gốc kho** | Khác sổ công cụ: "module nào còn thiếu tri thức" chỉ có nghĩa khi có backlog. Đặt chung thì một kỹ năng của dự án này hiện ra ở dự án khác và chạy hỏng vì thiếu dữ liệu, chứ không phải vì nó sai |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/skills.py`, lệnh `eaa skill` |

## SL-82 · BỔ SUNG · `eaa/focus.py` — đảo chiều thông tin, không nới quyền

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-PLT-03, EAA-SAD-02 §3; UC04 |
| **Chỗ trống** | `eaa resume` khôi phục sau gián đoạn, nhưng khôi phục **không phải** bắt đầu giữa chừng. Người dùng muốn "sinh mã cho module này" và nhận được một thông báo tiền điều kiện: sai pha. Sửa xong thì tới cái sau: module chưa có trong backlog. Rồi cái sau nữa. Mỗi lần một câu, và mỗi câu chỉ nói về **cái vừa chặn**, không nói về **cả quãng đường** — người dùng đi mò từng bước trong một quy trình họ không nhìn thấy hình dạng |
| **Code làm** | `Precondition`, `FocusPlan`, `analyse()`; lệnh `eaa focus <module> [--run]` |
| **KHÔNG bỏ tiền điều kiện nào** | Cùng bộ luật của `Orchestrator._kiem_tien_dieu_kien`, chỉ khác chỗ nó **không ném** ở cái chặn đầu tiên mà đi hết. Cách "dễ" hơn — một cờ nhảy thẳng vào pha D — phá đúng bất biến trung tâm, và nó sẽ được dùng vào đúng lúc gấp |
| **Không phát biểu lại luật nào** | `analyse()` **nhận** dữ kiện đã đo sẵn thay vì tự đi đọc. Trùng luật ở hai chỗ là cách chúng lệch nhau về sau, và cái lỏng hơn sẽ luôn là cái được dùng |
| **Ranh giới agent/người là ranh giới CŨ** | `_ai_chay()` đọc từ chính `TOOLBOX`. Một chặng "người" không bao giờ tự chuyển thành "agent" bằng cách đi qua `focus` (có test canh) |
| **`agent_steps` CẮT ở chặng người đầu tiên** | Không lấy hết những chặng agent rải rác phía sau: một chặng "người" ở giữa nghĩa là mọi chặng sau nó phụ thuộc vào một quyết định chưa có. Chạy trước chúng là làm việc trên một giả định người dùng chưa đưa ra |
| **Cung không gate không phải một chặng** | B→C tự chuyển ngay sau khi G1 duyệt (engine đi hết những bước gate vừa mở). Liệt nó ra là bịa thêm một bước cho người dùng — và tệ hơn, một bước không có lệnh nào gỡ được. Nó thành ghi chú gắn vào gate đứng trước |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/focus.py`, lệnh `eaa focus` |


## SL-83 · BỔ SUNG · `eaa/toolusage.py` — công cụ tự sinh chạy ra sao khi dùng THẬT

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §11, NFR-08 |
| **Chỗ trống** | Ba cổng của SL-77 chứng minh một công cụ **chạy được lúc duyệt**. Chúng không nói gì về lần thứ hai mươi, trên dữ liệu thật. Một công cụ qua cổng rồi hỏng bốn trong sáu lần dùng vẫn mang nhãn `approved` và vẫn nằm trong prompt của Agent — nó sẽ được gọi lại, hỏng lại, và mỗi lần hỏng là một lượt gọi mô hình bị đốt |
| **Code làm** | `ToolUse`, `ToolStats`, `UsageLog`; `ToolForge.run()` ghi MỌI lần gọi; `eaa tool list` hiện số đo |
| **Không cảnh báo sớm** | `concerning` chỉ đúng khi đã đủ `SO_LAN_DU_DE_KET_LUAN` = 4. Hai lần hỏng đầu có thể chỉ là hai lần đầu vào xấu, và **một cảnh báo sai làm người ta thôi đọc cảnh báo** |
| **Không tự gỡ công cụ nào** | Gỡ là một quyết định: có khi công cụ đúng còn dữ liệu vào sai. Module bày số ra và cảnh báo; `eaa suggest` biến số ấy thành đề nghị cụ thể |
| **Ghi hỏng không được che lỗi thật** | `_ghi_lan_dung` nuốt mọi ngoại lệ của chính nó — nhật ký hỏng không được biến một lỗi công cụ thành một lỗi nhật ký |
| **Cần cập nhật** | EAA-SDD-03 §2: thêm `eaa/toolusage.py` |

## SL-84 · BỔ SUNG · `eaa/suggest.py` — tự nhìn lại, và mọi đề nghị đều kèm SỐ

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §11; N-906, NFR-08 |
| **Chỗ trống** | Agent viết được công cụ (SL-77) và rút được kỹ năng (SL-81), nhưng cả hai vẫn phải do người gợi ý. Đó đúng là chỗ Agent có lợi thế mà con người không có: nó có **nhật ký**, biết chính xác lần thứ mấy nó bị hỏi một việc nó không làm được — còn người chỉ có cảm giác mơ hồ rằng "cái này hơi phiền" |
| **Code làm** | `Suggestion`, `SuggestionReport`, `analyse()`; lệnh `eaa suggest` |
| **Luật duy nhất: đề nghị phải có SỐ** | Một đề nghị không kèm bằng chứng đếm được là một ý kiến, và **một agent đưa ý kiến về việc nên xây gì tiếp là một agent sớm muộn cũng đề nghị xây thứ nó thích** |
| **Tách RANH GIỚI QUYỀN khỏi khoảng trống năng lực** | Đây là phần quan trọng nhất. Agent bị chặn ở `gate approve` mười lần **không** phải một khoảng trống năng lực, và đề nghị "viết công cụ" cho nó là đề nghị lách rào. Hai loại ấy được tách ở đúng chỗ đọc nhật ký, và loại thứ hai in ra dưới nhãn *"ĐÚNG như thiết kế, không phải thiếu sót"* |
| **Không có tín hiệu thì nói KHÔNG CÓ GÌ** | Cám dỗ lớn nhất của một lệnh tên `suggest` là luôn tìm ra điều gì đó để nói. Nhật ký sạch thì đầu ra là "chưa thấy gì đáng làm" — một câu trả lời đúng, không phải một thất bại |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/suggest.py`, lệnh `eaa suggest` |

## SL-85 · BỔ SUNG · `eaa/toolassess.py` — gói này có đáng cài không

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.2, §9.4; FR-ENV-03 |
| **Chỗ trống** | Từ SL-80 đề xuất công cụ đọc được trang cài đặt thật, nhưng phần **đánh giá** vẫn đổ hết lên người duyệt: còn ai bảo trì không, license gì, bao nhiêu người dùng, tên có gõ đúng không. Người duyệt ngồi trước một đề xuất trông rất chỉn chu và không có cách nào kiểm nhanh mấy câu ấy |
| **Code làm** | `PackageFacts`, `Assessment`, `assess()`; lệnh `eaa assess`; đọc PyPI / npm / GitHub qua `eaa/web.py` |
| **Chống gõ nhầm tên: hỏi ĐẢO LẠI** | `toolsearch` đã chặn nguồn cài lạ, nhưng không chặn được một tên gõ nhầm một ký tự trỏ tới một gói khác **có thật** — kiểu nhắm đúng vào người đọc lướt. Câu trả lời không phải một danh sách đen (không bao giờ đủ) mà là: *gói này có tồn tại không, và nó trông ra sao?* Bốn con số nói được điều mà danh sách đen không nói được |
| **"Không tìm thấy" là KẾT QUẢ, không phải lỗi** | Đó chính là câu trả lời cho "tên này có thật không" |
| **Đánh dấu, KHÔNG loại** | Mọi cờ đều là "chỗ cần nhìn kỹ", kể cả license lạ. Loại là việc của người duyệt |
| **Hai năm chứ không phải sáu tháng** | Ngưỡng bỏ hoang đặt ở 730 ngày: một công cụ dòng lệnh nhỏ **làm xong việc của nó** thì không cần phát hành thêm, và phạt nó vì điều đó là đọc sai chỉ số |
| **Hạng MỞ, và nói rõ** | Kho gói không thuộc miền nhà sản xuất chip. Số liệu dùng để so công cụ và gỡ lỗi; tuyệt đối không làm nguồn cho giá trị cấu hình phần cứng |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/toolassess.py`, lệnh `eaa assess` |

## SL-86 · BỔ SUNG · `eaa/debugsession.py` — N-085 ở mức tự chủ T0

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7; N-085 (mức T0) |
| **Chỗ trống** | N-085 là mục duy nhất trong bảng nghiệp vụ mang trạng thái CHƯA CÓ, ghi "ngoài phạm vi đề án". Nhưng T0 có một định nghĩa cụ thể — *"Người làm, Agent ghi vết"* — và ba việc mà T0 đòi thì **làm được**, chỉ là chưa ai làm |
| **Code làm** | `Probe`, `DebugStep`, `DebugPlan`, `SessionLog`, `detect_probes()`, `build_plan()`; lệnh `eaa debug plan/log/record` |
| **Điều module này KHÔNG làm** | Không điều khiển mạch nạp, không đặt điểm dừng, không chạy phiên gỡ lỗi. Những việc ấy đòi một mạch gỡ lỗi cắm vào bo thật — nằm ngoài phạm vi, đã ghi từ đầu |
| **Phần đáng giá nhất là bước 2** | Người ta hiếm khi bí ở chỗ "gõ lệnh gì trong gdb"; người ta bí ở chỗ **nhìn vào đâu**, và *thấy giá trị này thì suy ra được gì*. Nên mỗi bước bắt khai trước **hai nhánh** kết luận — cách rẻ nhất để không tự thuyết phục mình sau khi đã nhìn thấy số |
| **Bước rút TỪ tiêu chí kịch bản, không tự bịa** | Kịch bản chẩn đoán là tri thức đã qua gate; tự nghĩ ra bước là đưa vào một giả thuyết không ai duyệt. Tiêu chí `machine` → điểm dừng và khoảng đúng; `human` → kênh đối chiếu thứ hai |
| **Luôn hỏi ngược trước** | Gỡ lỗi sâu là dụng cụ đắt tiền cho một câu hỏi rẻ. Kế hoạch nào cũng bắt đầu bằng "bạn đã thử hai kênh rẻ hơn chưa?" |
| **Tên trình gỡ lỗi thuộc PACK, không thuộc engine** | TC-38 bắt được `openocd`/`avarice` viết thẳng trong engine. Đã dời sang `debug_tools:` trong `pack.yaml` của cả hai pack; `build_plan(tools=())` mặc định RỖNG — đó là ràng buộc kiến trúc, không phải chỗ chưa điền (FR-PLT-01) |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/debugsession.py`, lệnh `eaa debug`; EAA-AIS-05 §7: N-085 chuyển từ "ngoài phạm vi" sang "đủ ở mức T0" |

## SL-87 · LỆCH THẬT · Giấy phép merge đòi bằng chứng PHỦ ĐỦ, không chỉ đòi cái có mặt đều đạt

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4, NFR-01, FR-VER-01; TC-01, TC-73 |
| **Lỗ hổng** | `MergeAuthorization.__post_init__` kiểm *"mọi báo cáo CÓ MẶT đều đạt"*. Nó **không** kiểm chúng có phủ đủ bộ cổng bắt buộc không. Một bằng chứng chỉ chứa mỗi `compile` — đạt — vẫn thỏa phép kiểm ấy: câu "toàn bộ ToolReport.passed" khi đó đúng về mặt chữ nghĩa mà rỗng về mặt nội dung, vì **bộ báo cáo mới là thứ quyết định câu ấy có nghĩa gì** |
| **Hôm nay chưa với tới được** | `_kiem_tien_dieu_kien` đòi chuỗi đủ cổng, nên một lượt chạy bình thường luôn sinh đủ bốn báo cáo. Nhưng thêm chế độ nháp (SL-88) là mở đúng đường tới lỗ hổng ấy |
| **Đã sửa** | `MergeAuthorization.required_gates`; `authorize_merge(required_gates=…)`; `finalize_module` truyền `self.config.required_gates` xuống. Một cổng **vắng mặt** là một loại lỗi không được kiểm, y hệt một cổng trượt |
| **Vì sao ghi là LỆCH THẬT** | Đây là một phép kiểm THÊM vào bất biến trung tâm, không phải một tính năng mới. SDD §4 phát biểu bất biến bằng "toàn bộ ToolReport.passed"; câu ấy cần thêm vế "và bộ báo cáo phủ đủ chuỗi cổng" |
| **Cần cập nhật** | EAA-SDD-03 §4: bổ sung vế phủ đủ vào phát biểu bất biến |

## SL-88 · BỔ SUNG · Chế độ nháp — hạ ceremony mà không hạ bất biến

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4, NFR-01; C10.4 trong bảng năng lực |
| **Yêu cầu** | Người dùng muốn chọn tập cổng nhẹ hơn để thử nhanh |
| **Vì sao cách hiển nhiên là sai** | Một cờ cho phép **bỏ qua cổng** phá đúng bất biến trung tâm. Một cờ bỏ qua tồn tại là một cờ sẽ được dùng, và nó sẽ được dùng đúng vào lúc gấp |
| **Cách làm** | `OrchestratorConfig.draft_gates`; `eaa gen <module> --draft compile,static`. Nhánh nháp **trả về TRƯỚC** khi chạm `_xin_gate` và `_luu_bang_chung` |
| **Bất biến giữ được do CẤU TẠO** | Bản nháp không merge được **không phải vì bị chặn** — mà vì nó không ghi vào tệp mà `load_evidence` đọc. Tới bước merge đơn giản là không có bằng chứng nào để đọc. **Không có câu `if` nào ở phía merge phải nhớ đặt cho đúng**, và test canh điều ấy bằng cách đọc thứ tự trong mã |
| **Hai lớp, độc lập nhau** | Lớp một: không để lại bằng chứng. Lớp hai: SL-87 đòi phủ đủ bộ cổng. Kể cả khi ai đó vô tình nối bằng chứng nháp vào đường merge, lớp hai vẫn chặn |
| **Thứ tự cổng giữ nguyên** | Chuỗi nháp lọc theo tập đã chọn nhưng **giữ thứ tự gốc**: cổng sau ăn sản phẩm của cổng trước |
| **Cần cập nhật** | EAA-SDD-03 §6: `eaa gen --draft` |

## SL-89 · BỔ SUNG · Chỗ làm nháp tự khởi tạo — hạ nốt bậc thềm cuối

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-PLT-03; C10.1 |
| **Chỗ trống** | SL-78 sinh sẵn YAML nhưng vẫn để lại một bậc: `eaa init` trước khi vào `eaa chat` |
| **Code làm** | `_tu_khoi_tao_neu_la_nhap()`; `eaa scratch` chạy `init` luôn |
| **Ranh giới hẹp có chủ ý** | Trên dự án THẬT, `eaa init` là một quyết định: nó đọc ràng buộc đã chốt, chọn nhà cung cấp mô hình, ghi Project State — làm hộ ở đó là lấy mất một quyết định. Ở chỗ nháp thì không có gì để lấy: ràng buộc do máy sinh và mang nhãn GIẢ ĐỊNH, nên bước ấy chỉ còn là thủ tục |
| **Cần cập nhật** | EAA-SDD-03 §6: `eaa scratch` bao gồm `init` |


## SL-90 · BỔ SUNG · `eaa/installplan.py` — cài theo thứ tự nào, cách nào, và chỗ nào đá nhau

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.1, §9.2, §9.4; FR-ENV-02, FR-ENV-04 |
| **Chỗ trống** | `doctor --fix` in ra danh sách lệnh cài đúng từng dòng một, mà thiếu ba thứ — và cả ba chỉ lộ ra khi có nhiều hơn một công cụ: ① **thứ tự** (cài ngược thì lệnh sau hỏng bằng một thông báo nói về thứ khác hẳn, và người dùng đi sửa nhầm chỗ) ② **cách cài** (không phải cái nào cũng nằm trong một trình quản lý gói) ③ **xung đột** (hai thẻ cùng đòi một thứ ở hai phiên bản; cài cái sau làm hỏng cái trước, mà cái trước thì đã báo "đạt" rồi) |
| **Code làm** | `PlannedStep`, `InstallPlan`, `plan_installs()`, `find_conflicts()`; `ToolSpec.method` / `.requires` / `.alternatives`; lệnh `eaa doctor --plan` |
| **Vì sao ba câu gộp một module** | Cả ba chỉ trả lời được khi nhìn **toàn bộ manifest cùng lúc**. Một Tool Card đọc riêng thì không biết mình đứng sau ai và không biết mình đá nhau với ai — đặt phép kiểm ở tầng từng thẻ là đặt nó ở chỗ không có đủ thông tin |
| **Sắp xếp tô-pô ỔN ĐỊNH** | Cùng một manifest luôn ra cùng một thứ tự. Hai lần chạy doctor in ra hai danh sách khác nhau là hai lần không ai hiểu vì sao |
| **Phụ thuộc vòng: dừng, không tự gỡ** | Máy không chọn hộ được cái nào đi trước — phải gỡ ở manifest |
| **Chỉ báo xung đột khi CHẮC CHẮN loại trừ** | `>=3.0` và `<2.0` thì báo; hai ràng buộc chỉ *có thể* đá nhau thì không. Một cảnh báo sai làm người dùng bỏ qua cả những cảnh báo đúng, và bộ kiểm này chạy mỗi lần chạy doctor |
| **Phụ thuộc ra ngoài manifest: nêu ra, không nuốt** | Không xếp thứ tự theo nó được (nó không phải một nút trong đồ thị), nhưng nó vẫn là thứ phải có trước. Nêu kèm chữ "kiểm bằng tay" là cách trung thực nhất |
| **Không cài gì cả** | Module sắp thứ tự và chỉ ra chỗ đá nhau; chạy vẫn là của người (N-022, mức T2) |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/installplan.py`, cờ `eaa doctor --plan`; AIS §9.1: Tool Card có thêm `method`, `requires`, `alternatives` |

## SL-91 · BỔ SUNG · `eaa gen --preview` — xem mã khi máy chưa có toolchain

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4; C10.3 trong bảng năng lực |
| **Chỗ trống** | Máy chưa có toolchain là hoàn cảnh **rất thường gặp** — chính máy làm đề án này đang thiếu 5/7 công cụ. Khi ấy cổng `compile` hỏng vì lỗi môi trường và người dùng không xem được cả dòng mã nào, trong khi thứ họ muốn chỉ là *nhìn xem Agent sẽ viết gì* |
| **Code làm** | `OrchestratorConfig.preview`; `eaa gen <module> --preview` |
| **An toàn hơn cả chế độ nháp** | Nháp không ghi bằng chứng (SL-88); xem trước thậm chí **không tạo ra một nhánh nào để mà merge**. Nó trả về TRƯỚC `repo.start_module()` — kể cả nếu ai đó sau này viết nhầm một lối merge thứ hai, lối ấy sẽ không tìm thấy nhánh nào của lượt chạy này |
| **Nới ĐÚNG một tiền điều kiện: pha** | Cổng pha kiểm soát thứ **đi vào** sản phẩm; xem trước không đưa gì vào cả. Mọi tiền điều kiện khác vẫn áp — backlog, xung đột tài nguyên, đủ tri thức — vì ba cái ấy quyết định mã sinh ra **có nghĩa hay không**; bỏ chúng thì thứ in ra là mã bịa, không phải mã xem trước |
| **Cảnh báo khi chạy trước pha D** | Kiến trúc chưa chốt xong thì mã dựng trên ràng buộc còn có thể đổi. Rủi ro ở đây là **tâm lý**, không phải kỹ thuật: nhìn thấy mã hợp lý trước khi chốt ràng buộc dễ chốt hộ một quyết định chưa ai đưa ra. Nên đây là một cảnh báo, không phải một cái chặn |
| **KPI ghi riêng** | `preview` và `draft_run` là sự kiện riêng trong `EVENTS`, không gộp vào `generate`: gộp thì tỉ lệ đạt của Chương 3 đẹp lên vì một lý do không liên quan gì tới chất lượng mã |
| **Cần cập nhật** | EAA-SDD-03 §6: cờ `eaa gen --preview` |

## SL-92 · BỔ SUNG · Công cụ tự sinh: giữ bản cũ, quay lui, và tự sinh tài liệu

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.4 (phiên bản), §11; C6.8, C7.3 |
| **Chỗ trống** | `eaa suggest` (SL-84) **đề nghị viết lại** những công cụ hay hỏng — nên "viết lại" là một đường đi thường dùng. Không giữ bản cũ thì nó là một canh bạc không có đường lui, và người ta sẽ thôi không dám sửa |
| **Code làm** | `ToolRegistry.versions()` / `_giu_ban_cu()`; `ToolForge.rollback()`, `.document()`; lệnh `eaa tool rollback`, `eaa tool doc` |
| **Chỉ giữ bản ĐÃ DUYỆT** | Một bản đề xuất chưa ai duyệt thì chưa từng chạy thật — quay lui về nó không mang lại gì |
| **Bản quay về KHÔNG tự lên lại `approved`** | Nó về `proposed` và phải đi lại ba cổng. Mã ấy từng chạy được, nhưng "từng" là ở một môi trường khác và có thể ở một phiên bản Python khác — nếu ba cổng vẫn xanh thì chạy lại tốn vài giây, còn nếu không thì đó chính là thứ ta cần biết trước khi dựa vào nó |
| **Tài liệu dựng TỪ MÃ, không hỏi mô hình** | `MO_TA`, `SCHEMA`, các hàm `test_`, cộng số đo dùng thật. Một bản mô tả do mô hình viết lại có thể lệch khỏi mã, và **một tài liệu lệch khỏi mã tệ hơn không có tài liệu** |
| **Cần cập nhật** | EAA-SDD-03 §6: `eaa tool rollback`, `eaa tool doc` |

## SL-93 · BỔ SUNG · Liệt kê gói runtime, và xưởng công cụ là bậc áp chót của thang gỡ

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.1, §9.2; C2.4, C5.6 |
| **C2.4 — chỗ trống** | `doctor` chỉ kiểm được **thứ đã có trong Tool Card**. Nó trả lời "công cụ tôi cần đã cài chưa", không trả lời "máy này sẵn có gì" — hai câu khác nhau, và câu thứ hai là câu người ta hỏi TRƯỚC khi quyết định cài thêm hay dùng thứ đang có |
| **Code làm (C2.4)** | `eaa/environ.py` `list_packages()`, `LENH_LIET_KE_GOI`; lệnh `eaa environ --packages [python\|npm]` |
| **Hỏi bằng trình thông dịch ĐANG CHẠY** | `{python}` thay bằng `sys.executable`, cùng lý do với `doctor` (SL-18): hỏi cái đầu tiên gặp trong PATH là hỏi một môi trường khác |
| **C5.6 — chỗ trống** | Thang gỡ lỗi cài đặt (SL-76) kết thúc ở "bàn giao người". Nhưng từ SL-77 còn một bậc nữa: tự viết một thứ tối thiểu thay thế |
| **Đặt SAU mọi bậc cài thật** | Một công cụ tự viết chỉ làm được phần hẹp của việc, và **không có ai bảo trì ngoài chính dự án này**. Nó là lối thoát khi mọi cách khác đã hết, không phải một lựa chọn ngang hàng |
| **Cần cập nhật** | EAA-SDD-03 §6: cờ `eaa environ --packages`; AIS §9.2: thang gỡ có thêm bậc tự viết |


## SL-94 · BỔ SUNG · `eaa/pdftext.py` — đọc được PDF, bằng thư viện chuẩn

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1 (đầu vào đa phương thức); FR-ING-01, NFR-04 |
| **Chỗ trống** | `eaa survey` kiểm kê được **có những tệp gì** nhưng không mở được PDF. Tài liệu quy trình của một dự án nhúng gần như luôn ở dạng PDF — hồ sơ robot dùng kiểm thử sản phẩm này có đúng hai tệp như vậy, và chúng chứa chính thứ Agent được hỏi |
| **Code làm** | `PdfText`, `extract_text()`; `eaa survey --read <tệp>` |
| **Tự viết thay vì thêm thư viện** | NFR-04 chốt chỉ phụ thuộc Python, toolchain, Git. Phần cần dùng của PDF lại hẹp: `zlib` giải luồng, đọc bảng `ToUnicode`, bóc chuỗi giữa toán tử vẽ chữ |
| **Ba lỗi tìm ra khi dựng, cả ba đều "gần đúng"** | ① **Gộp bảng font của mọi trang** — hai trang cùng đặt tên `/F2` cho hai font khác nhau, gộp lại thì trang sau ghi đè trang trước ② **Bỏ qua `/ObjStm`** — từ PDF 1.5 phần lớn đối tượng nằm trong luồng nén; tài liệu thật để lộ 73 đối tượng trong khi có 728, và bảng font nằm trong số bị giấu ③ **Coi font đơn giản là 2 byte** — chúng dùng `/WinAnsiEncoding`, mã 1 byte cp1252 |
| **Vì sao ba lỗi ấy đáng ghi** | Cả ba đều **không làm hỏng hẳn**. Chúng làm rụng đúng những nguyên âm có dấu của tiếng Việt: `toán`→`ton`, `giúp`→`gip`. Văn bản vẫn đọc được, chỉ sai ở chỗ ít ai soi — **gần đúng ở đây tệ hơn hỏng hẳn, vì nó trông như đọc được** |
| **Định vị bằng `Tm`, không phải `Td`** | Tài liệu thật có 723 lần `Tm` và **không một lần** `Td`. Coi mọi `Tm` là xuống dòng thì ra 723 dòng rời; coi là dấu cách thì mất cấu trúc đoạn. Phải nhìn tọa độ: đổi theo chiều dọc là dòng mới |
| **Nói thẳng điều KHÔNG làm được** | Không đọc PDF quét ảnh (báo rỗng kèm lý do, không trả chuỗi rác); không dựng lại bố cục; **đếm và báo** số glyph không tra được. Trên tài liệu thật: 40/1884 ký tự rụng vì font nhúng thiếu bảng — đã kiểm và xác nhận `'á'` không nằm trong bất kỳ `ToUnicode` nào của tệp, tức là mất mát nằm ở tệp chứ không ở bộ đọc |
| **Cần cập nhật** | EAA-SDD-03 §2 và §6: thêm `eaa/pdftext.py`, cờ `eaa survey --read` |

## SL-95 · LỆCH THẬT · Câu trả lời phải NÊU NGUỒN, và nguồn phải khớp câu hỏi

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §12; N-903 |
| **Lỗi đo được** | Bài kiểm BLKLab 31/08/2026, bài 2. Người dùng hỏi quy trình trong **tài liệu của họ**. Agent chạy `datasheet list`, `docs list`, `handover doc` — ba lệnh hợp lệ — rồi tóm tắt tài liệu vận hành **của chính công cụ EAA** như thể đó là câu trả lời. Từng câu đều đúng; chỉ là đúng về một tài liệu khác |
| **Vì sao không phép kiểm nào bắt được** | Lệnh hợp lệ, đầu ra hợp lệ, câu trả lời mạch lạc. Bộ từ vựng tin cậy (N-903) không chặn được vì `handover doc` trả về một tài liệu **thật** — chỉ là thật cho một câu hỏi khác |
| **Điều đáng lo hơn** | Ở vòng trước Agent **không có** năng lực nên nó hỏi lại. Vòng này nó có thêm nguồn để đọc, dùng nhầm một nguồn, rồi trả lời như đã đọc đúng chỗ. **Thêm năng lực mà không thêm kỷ luật về nguồn thì làm câu trả lời sai TỰ TIN HƠN, không phải đúng hơn** |
| **Code làm** | `ChatResult.sources` / `.unsourced`; trường `nguon` trong lược đồ trả lời; luật thứ 5 trong `_VAI_TRO` nêu thẳng ca hỏng này |
| **Cưỡng chế thế nào** | Có chạy lệnh + có trả lời + không khai nguồn → bản in kèm dòng cảnh báo và liệt kê lệnh đã chạy. Không chặn câu trả lời — chặn thì mất cả những câu đúng — mà **bắt nó nói ra nó đang trả lời từ đâu**, để chính người đọc nhận ra nguồn không khớp câu hỏi |
| **Kết quả sau khi sửa** | Chạy lại cùng câu hỏi: Agent tự tìm hai PDF, **đọc cả hai**, kết luận đúng rằng chúng không mô tả quy trình ấy, tóm tắt đúng thứ mỗi tệp thật sự chứa, và khai nguồn |
| **Cần cập nhật** | EAA-AIS-05 §12: bổ sung luật nêu nguồn cho tầng hội thoại |

## SL-96 · BỔ SUNG · Soi kỹ kho tài liệu, và cho Agent biết kho có tồn tại

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.1; FR-ING-01 |
| **Chỗ trống 1** | Bản khảo sát tổng của `survey` phải cắt bớt để không nuốt ngân sách ngữ cảnh, và **cái bị cắt thì Agent không biết là có**. Đo được ở bài 1: Agent mô tả đúng phần nó thấy nhưng bỏ sót hai cảm biến Sharp và module BLE chỉ vì chúng nằm ngoài phần tóm tắt |
| **Chỗ trống 2** | Kho đã giải nén nằm trên đĩa mà Agent **không biết là có**. Đo được ở bài 2 sau khi đã có `--read`: Agent vẫn hỏi lại người dùng đường dẫn, trong khi tệp cần đọc đã nằm sẵn ở `sources/` từ một lượt trước |
| **Code làm** | `eaa survey --files <mẫu>`; `AgentLoop._tom_tat_kho_tai_lieu()` nêu kho trong lớp trạng thái |
| **Chặn đường dẫn** | Tham số `--read` do mô hình điền, nên mọi đường dẫn phải nằm trong `<dự án>/sources/` sau khi giải hết liên kết mềm — một `../../..` trong đó là đường đọc bất cứ tệp nào trên máy |
| **Chỉ đếm, không liệt kê hết** | Lớp trạng thái nêu số tệp, phân bố đuôi, và vài tên tài liệu. Một danh sách 308 mục sẽ nuốt hết lớp ấy; Agent thấy có kho thì tự gọi `survey --files` để soi tiếp |
| **Cần cập nhật** | EAA-SDD-03 §6: cờ `eaa survey --files` |

## SL-97 · LỆCH THẬT · Vòng hội thoại khai ngân sách ngữ cảnh RIÊNG

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §2, §3 (Hình 1); TC-16 |
| **Vấn đề** | `LAYER_BUDGETS` chia 8.000 token theo Hình 1 của AIS §2, và cách chia ấy dành cho prompt **sinh mã**: chunk datasheet, hợp đồng giao diện, quy tắc lỗi, phần dự phòng cho vòng vá. Prompt **hội thoại** có hình dạng khác hẳn — phần lớn ngân sách của nó là DANH MỤC CÔNG CỤ, thứ không tồn tại trong prompt sinh mã. Vòng hội thoại đang mượn `role_constraints` của vòng sinh mã |
| **Lộ ra thế nào** | Thêm luật nêu nguồn vào vai trò và thêm hai cờ vào mô tả `survey` làm cả hai lớp vượt phần của mình. Bộ kiểm ngân sách chặn trước khi gọi API — đúng việc của nó (TC-16) |
| **Đã sửa** | `NGAN_SACH_VAI_TRO`, `NGAN_SACH_DANH_MUC`, `NGAN_SACH_QUAN_SAT` khai riêng trong `eaa/agent.py`. Trần **tổng** vẫn 8.000 và vẫn kiểm trước khi gọi |
| **Vì sao không nới `LAYER_BUDGETS`** | Mượn của nhau thì mỗi lần thêm một công cụ lại phải nới một con số thuộc về bản thiết kế của việc khác — và đó là cách một bảng ngân sách có căn cứ biến dần thành một bảng số ai cũng sửa được |
| **Cần cập nhật** | EAA-AIS-05 §2: nêu rõ Hình 1 đặc tả prompt sinh mã; tầng hội thoại có bảng riêng |


## SL-98 · BỔ SUNG · Xung đột phần cứng ghi được vào hồ sơ, và hiện ở mọi bản trạng thái

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 (Hardware Profile); FR-KG-02 |
| **Chỗ trống** | `graph.check_module()` bắt được xung đột giữa hai MODULE trong backlog. Nó không có chỗ nào để ghi một xung đột **đã có sẵn trong bo của người dùng** — hai linh kiện được khai cho cùng một chân trong mã hoặc sơ đồ của người khác |
| **Đo được** | Hồ sơ robot BLKLab: `SoftwareSerial mySerial(9, 11)` khai D11 làm TX cho Bluetooth, `const int ledPin = 11` khai đúng chân ấy làm đường dữ liệu LED. Agent tìm ra khi đọc mã — và nếu không có chỗ để ghi thì phát hiện ấy chỉ sống được trong một lượt hội thoại |
| **Code làm** | `HardwareProfile.conflicts` / `.conflicts_on()`; `_in_xung_dot_phan_cung()` in ở `eaa init` và mọi bản tóm tắt trạng thái |
| **Máy KHÔNG tự dời chân** | Đây là bo của người dùng. Có thể mạch đã đi dây theo một cách mã chưa phản ánh, hoặc TX ấy thật sự không bao giờ được dùng. Máy ghi lại và nhắc; chọn dời cái nào là quyết định về phần cứng |
| **In ở MỌI chỗ, không một chỗ** | Một xung đột đã biết mà chỉ hiện ở một lệnh ít ai gõ thì cũng như không ghi — nó phải đập vào mắt đúng lúc người ta sắp sinh mã |
| **Cần cập nhật** | EAA-SDD-03 §2: `hardware_profile.yaml` có thêm khối `conflicts` |

## SL-99 · BỔ SUNG · Mã module phải hẹp, vì nó đi vào tên nhánh Git

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §4; NFR-07 |
| **Đo được** | `eaa plan add "drv_x --uses twi"` tạo ra một module có mã là **cả chuỗi ấy** — và cái tên đó im lặng đi tiếp cho tới lúc dựng nhánh Git. Lộ ra vì một biến shell không được tách từ (zsh không tách biến không trích dẫn như bash) |
| **Đã sửa** | `_plan_add` đòi `[a-z][a-z0-9_]{1,39}`, kèm gợi ý đúng cú pháp truyền cờ |
| **Vì sao đáng chặn ở đây** | Mã module đi vào tên nhánh, tên tệp sinh ra, khóa trong Project State và cột `module` của `kpi_log.csv`. Chặn muộn hơn nghĩa là dọn ở bốn chỗ |

## SL-100 · LỆCH THẬT · Lớp quan sát bỏ đầu ra thì phải NÊU TÊN lệnh đã chạy

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §2, §3; SL-97 |
| **Lỗi do chính bản sửa trước gây ra** | SL-97 cho lớp quan sát tự cắt cho vừa ngân sách. Nhưng nó chỉ nói "đã bỏ N quan sát" — **không nói bỏ những lệnh nào**. Hệ quả đo được ngay: Agent mất trí nhớ về tệp mình vừa đọc, đọc lại đúng tệp ấy, đầu ra mới lại đẩy quan sát cũ ra ngoài, và nó **quay vòng cho tới khi chạm trần 8 bước** — bốn lượt gọi mô hình bị đốt cho ba tệp |
| **Đã sửa** | Ghi chú nêu ĐÍCH DANH dòng `$ eaa …` của từng lệnh bị bỏ, kèm câu "BẠN ĐÃ CHẠY chúng rồi — đừng chạy lại". Một dòng tên lệnh rẻ hơn hẳn một lượt gọi mô hình |
| **Chỗ chừa tính theo trường hợp XẤU NHẤT** | Mọi quan sát đều bị bỏ và mọi tên lệnh đều phải in. Chừa theo trung bình thì đúng phần ghi chú lại đẩy lớp vượt trần — mà ghi chú ấy sinh ra để cứu lượt chạy |
| **Dòng lệnh bị cắt 120 ký tự** | Bắt buộc chứ không phải cho gọn: chỗ chừa tính từ những dòng này, nên một dòng bất thường dài sẽ nuốt hết ngân sách của chính phần nội dung nó bảo vệ |
| **Bài học** | Một bản sửa đúng về ngân sách có thể sai về **trí nhớ trong lượt**. Cắt là bỏ thông tin, và bỏ thông tin im lặng thì bên nhận không biết mình đang thiếu gì |

## SL-101 · LỆCH THẬT · Nhánh `de_nghi_nguoi_chay` cũng phải khai nguồn

| | |
|---|---|
| **Tài liệu** | SL-95 |
| **Lỗi** | SL-95 chỉ đọc trường `nguon` ở nhánh `tra_loi`. Nhưng `de_nghi_nguoi_chay` **cũng sinh ra một câu trả lời**, và câu ấy cũng dựa trên đầu ra lệnh — nên cảnh báo "không khai nguồn" bắn vào một trường hợp mà mô hình **không có cách tuân thủ** |
| **Vì sao nghiêm trọng hơn vẻ ngoài** | Một cảnh báo không thể thỏa mãn dạy người ta bỏ qua cảnh báo. Sau vài lần, dòng cảnh báo ấy thành nhiễu — và lúc nó bắn ĐÚNG thì không ai đọc nữa |
| **Đã sửa** | Đọc `nguon` ở cả hai nhánh; lược đồ trả lời nói rõ điều đó |

## SL-102 · BỔ SUNG · Kho dùng chung phải lọc theo phạm vi (cách ly dữ liệu giữa dự án)

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §3 (một kho, nhiều dự án); FR-PLT-03; AIS §8 |
| **Vấn đề** | Kho dữ liệu của hệ chia hai loại. Loại **riêng dự án** — `sources/`, `datasheets/`, `state.json`, kỹ năng, nhật ký hội thoại, phẩm xuất — nằm trong thư mục dự án nên tự nó đã cách ly. Loại **dùng chung** — bộ nhớ liên dự án, sổ tay lỗi, nhật ký dùng công cụ, bộ đệm web — nằm ở gốc kho, và **đó là điểm của nó**: thứ học ở bo này mang sang bo sau |
| **Dùng chung không có nghĩa là áp bừa** | `avr-gcc: undefined reference` và `arm-none-eabi-ld: undefined reference` là hai lỗi trông giống nhau và có hai cách sửa khác hẳn. Một sổ tay không phân biệt họ chip sẽ gợi ý `-mmcu` cho một dự án ARM — và **gợi ý sai chỗ trông y hệt gợi ý đúng** |
| **Đã làm** | `PlaybookEntry.scope` + `Playbook.in_scope()`, `lookup()`, `hint()` lọc theo dự án/họ MCU (cùng bộ từ vựng `scope_du_an` / `scope_mcu` / `TOAN_CUC` mà `eaa/memory.py` đã dùng). `ToolUse.project` + `UsageLog.stats(project=)`: công cụ dùng chung, dữ liệu vào thì không — một công cụ đọc tệp nhật ký chạy tốt ở dự án này có thể hỏng ở dự án kia. `_boi_canh_du_an()` trong CLI dò dự án + họ MCU rồi truyền xuống |
| **Không ẩn im lặng** | `playbook list` in `0/1 mục áp dụng được ở đây` chứ không giấu. Ẩn im lặng biến "kinh nghiệm của họ chip khác" thành "chưa có kinh nghiệm", và người dùng sẽ đi hỏi lại thứ hệ đã biết |
| **Đứng ngoài mọi dự án thì thấy tất cả** | Không có bối cảnh thì không có gì để lọc theo. Mặc định lọc-hết ở đó là mặc định sai |
| **Bài canh** | `tests/test_tc79_cach_ly_du_an.py` — 16 bài, canh cả hai chiều: kho riêng không thấy dữ liệu dự án khác, kho chung phải có đường lọc. Có một bài canh **cấu trúc**: thêm kho dùng chung mới mà quên phần lọc thì đỏ ngay |

## SL-103 · BỔ SUNG · `eaa/llm/catalog.py` và lệnh `eaa models` — người chọn mô hình, hệ không tự chọn

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §2 (cấu hình mô hình); ADR-03; EAA-SDD-03 §6 (danh sách lệnh) |
| **Vì sao thêm** | AIS §2 chốt "ghim phiên bản mô hình", và mã model là **cấu hình** chứ không phải hằng số. Nhưng cấu hình ấy trước đây chỉ là một chuỗi trong `eaa init --model <chuỗi>` — đòi người dùng thuộc lòng mã của nhà cung cấp (`gemini-3.5-flash`? `gemini-3-5-flash`?), và gõ sai thì lỗi hiện ra lúc gọi API, sau khi đã dựng xong ngữ cảnh |
| **Đã thêm** | `eaa/llm/catalog.py` — danh mục mô hình là DỮ LIỆU, mỗi mục kèm chỗ mạnh/chỗ yếu và **ngày kiểm với API**. Lệnh `eaa models` in danh mục kèm mã đang dùng. Bổ sung `gemini-3.5-flash` và `gemini-3.5-flash-lite`, đã kiểm bằng `ListModels` + một lượt `generateContent` thật ngày 2026-08-31 (Flash: 2.057 ms, trần vào 1.048.576 token) |
| **Cờ `--model` cho một lượt chạy** | Thứ tự thắng: `--model` > Project State > `EAA_LLM_MODEL` > mặc định adapter. Cờ mạnh nhất vì nó là hành động có chủ ý **ngay tại chỗ dùng** — người dùng gõ nó ra, thấy nó, và nó biến mất sau lượt chạy. Adapter in ra dòng `[--model] lượt chạy này dùng …, không ghi vào Project State`: đổi model mà im lặng chính là thứ cần tránh |
| **Nhận được ở CẢ HAI vị trí** | Trước và sau tên lệnh. Mọi lệnh con khai `--model` với `default=argparse.SUPPRESS` — thiếu nó thì mặc định rỗng của lệnh con đè giá trị đặt ở parser gốc, và `eaa --model X chat` im lặng chạy bằng model khác. Riêng `init` giữ nghĩa **ghim vào state**, vì đó là lệnh đặt mặc định |
| **CỐ Ý KHÔNG có: tự chọn model theo loại việc** | "Việc nhẹ thì Flash, việc nặng thì Pro" nghe hợp lý và phá hai thứ. (1) Chi phí–chất lượng là đánh đổi của **người trả tiền**: một người chạy thí nghiệm luận văn có thể muốn Pro cho MỌI lượt để số liệu so sánh được. (2) Model đổi ngầm giữa chừng phá tính tái lập — hai lần chạy cùng một lệnh rơi vào hai model, và lúc kết quả lệch thì không biết lệch vì model hay vì đầu vào (rủi ro R1, EAA-STP-04). Một cơ chế tự chọn sai thì người dùng **không thấy nó sai**, chỉ thấy câu trả lời tệ hơn |
| **Canh bằng cấu trúc** | `KHUYEN_NGHI` là dict để IN RA cho người đọc. TC-80 quét cả `eaa/` và đỏ nếu có tệp nào ngoài `catalog.py` đọc dict ấy — dấu hiệu cơ chế tự chọn vừa được lén thêm vào |
| **Danh mục là gợi ý, không phải hàng rào** | Mã ngoài danh mục vẫn chạy, kèm ghi chú "chưa kiểm". Nhà cung cấp ra model mới nhanh hơn tài liệu được cập nhật; một danh sách trắng cứng sẽ chặn đúng thứ người dùng cần |
| **Ranh giới quyền** | `models` vào TOOLBOX (chỉ đọc). `init` vào `NGOAI_DANH_MUC`: Agent liệt kê được lựa chọn nhưng không tự đổi model của chính nó |
| **Bài canh** | `tests/test_tc80_chon_model.py` — 17 bài |

## SL-104 · LỆCH THẬT (×3) · Ba chỗ mã lệch với chính lời nó khai — bộ ca xấu tìm ra

| | |
|---|---|
| **Tài liệu** | `docs/NHAT_KY_CA_XAU.md`; `scripts/chay_ca_xau.py`; NFR-06, NFR-07 |
| **Cách tìm** | Bộ 15 ca xấu chạy sản phẩm **như một người dùng đang gõ sai**. Vòng 1 đạt 10/15; sau ba vòng đạt 15/15. Ba lỗi thật, không cái nào bị 1.966 bài test sẵn có chạm tới — vì cả ba là chỗ **mã lệch với lời chính nó khai**, và một bài test viết từ cùng hiểu nhầm sẽ xanh |
| **Lỗi 1 — `EAA_NO_NET=1` không chặn lối ra qua mô hình** | Công tắc chỉ được đọc trong `eaa/web.py`. Engine có BA lối ra mạng: tải trang, gọi API mô hình (kể cả tìm kiếm có grounding), dò kết nối. `eaa research` đi lối thứ hai, nên `EAA_NO_NET=1 eaa research …` vẫn ra Internet thật và trả về 8 địa chỉ. Kiểu hỏng tệ nhất của một công tắc an toàn: nó **trông như đã tắt** — một công tắc hỏng mà báo lỗi thì người ta sửa, hỏng mà im lặng thì người ta tin |
| **Đã sửa 1** | `eaa/web.py::mang_bi_tat()` — một chỗ định nghĩa luật, ba chỗ hỏi. Chặn ở `GeminiClient._post()` chứ không ở từng phương thức công khai, để mọi đường tới nhà cung cấp kể cả đường thêm sau này đều đi qua. Chặn cả `output_limit()`: tra trần token cũng là một lượt gọi ra ngoài. Thông điệp chỉ đường: `--provider mock` / `replay`. TC-81 quét `eaa/` và đỏ nếu có tệp nào tự đọc `EAA_NO_NET` thay vì hỏi `mang_bi_tat()` |
| **Lỗi 2 — băm ràng buộc không bao giờ được đối chiếu** | `eaa status` in `constraints_version` đọc từ Project State, không đối chiếu với `constraints.yaml` trên đĩa. Sửa tệp xong, băm trên màn hình không đổi, và không có gì báo. Nghiêm trọng vì băm ấy đi vào **commit message** làm bằng chứng xuất xứ (NFR-07): băm cũ + tệp mới = mọi commit sau đó mang một khẳng định sai, **vĩnh viễn trong lịch sử Git** |
| **Đã sửa 2** | `_troi_rang_buoc()` gọi từ `_in_tom_tat` — cảnh báo nằm ở lệnh gõ hằng ngày, không ở lệnh ẩn. Nói ba thứ: băm thật, vì sao quan trọng (NFR-07), đường chốt lại (G1). Khớp thì im lặng |
| **Bộ dò bắt ngay một ca thật trong kho** | `projects/robot_balance` đang trôi: `constraints.yaml` sửa ở `f6b9d49`, `project_state.json` chưa động từ `ea63c88` — sớm hơn nhiều sprint. **Chưa tự ghim lại**: chốt bộ ràng buộc là quyết định của người tại G1, và một lệnh tự ghim lại băm chính là lối tắt thiết kế cấm |
| **Lỗi 3 — biến môi trường đặt RỖNG bị `.env` điền đè** | `load_env_file()` khai "biến đã đặt trong shell luôn thắng" nhưng kiểm bằng truthiness, nên `EAA_LLM_KEY=""` bị coi như chưa đặt. Hệ quả: trên máy có sẵn `.env` **không có cách nào** chạy thử đường không-có-khóa — đúng đường CI và máy mới sẽ đi |
| **Đã sửa 3** | `if ten in os.environ` thay cho truthiness; docstring nói rõ trường hợp chuỗi rỗng |
| **Ghi nhận** | Một ca test tôi viết SAI (C-04 dùng `eaa status`, lệnh không nạp constraints) lại là chỗ tìm ra lỗi 2. Nếu nó đạt ngay từ đầu thì đã không ai hỏi vì sao `status` in được một băm từ một tệp hỏng |
| **Bài canh** | `tests/test_tc81_ca_xau.py` — 14 bài; `scripts/chay_ca_xau.py` — 15 ca, chạy lại được |

## SL-105 · BỔ SUNG · Sinh tài liệu thiết kế: `eaa/docmodel.py`, `eaa/office.py`, `eaa/designdoc.py`, lệnh `eaa design`

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.5 (kho phẩm xuất); EAA-SDD-03 §2 (cây thư mục), §6 (danh sách lệnh) |
| **Vì sao thêm** | AIS §8.5 chốt có kho phẩm xuất nhưng chưa nói ai **dựng** ra phẩm xuất dạng tài liệu thiết kế. Yêu cầu: URD, SRS, SDD theo chuẩn 4C, danh sách chức năng, luồng nghiệp vụ — ra `.docx`, `.xlsx`, `.pptx`, `.pdf` |
| **"Chuẩn 4C" đọc là mô hình C4** | Context / Container / Component / Code (Simon Brown). Đã hỏi và người dùng xác nhận. SDD trình bày đúng bốn mức ấy, mỗi mức trả lời một câu hỏi và chỉ một |
| **CỐ Ý KHÔNG hỏi mô hình một chữ nào** | Toàn bộ nội dung rút từ hồ sơ dự án đã có. Một tài liệu thiết kế do mô hình viết **đọc rất hay và không truy được về đâu cả**: nó điền đầy mọi mục kể cả mục dự án chưa có dữ liệu, và người đọc không phân biệt được đâu là sự thật của dự án, đâu là văn mẫu. Với tài liệu thiết kế đó là hỏng hoàn toàn, vì công dụng duy nhất của nó là **được tin** |
| **Mục thiếu dữ liệu thì NÓI RA** | Không để trống. Một mục trống trong SRS đọc như "mục này không cần", trong khi thật ra là "chưa ai điền" — hai câu khác hẳn nhau. Mỗi chỗ thiếu kèm đúng lệnh phải chạy để có, và phụ lục đếm lại tổng số |
| **Khuôn mẫu là DỮ LIỆU** | `eaa/docspec/*.yaml` — 5 khuôn mẫu. Cấu trúc một tài liệu thiết kế là thứ mỗi đơn vị mỗi khác; nhúng cứng vào mã là đúng cho đúng một nơi. Mã chỉ cấp dữ liệu (`NGUON`, 23 bộ), khuôn mẫu nêu tên chúng. Khuôn mẫu nêu một tên chưa khai thì tài liệu nói thẳng là thiếu bộ cấp dữ liệu, không im lặng bỏ mục |
| **Ba lớp, một bản vẽ nhiều định dạng** | `docmodel.py` (mô hình không biết định dạng) → `office.py` (bộ xuất). Không có lớp giữa thì "SRS gồm những mục gì" bị chép ra bốn bản, và bản thứ tư sẽ bị quên. Mô hình cố ý **nghèo** — không màu, không lề, không font: đủ giàu để tả mọi thứ Word làm được thì chính nó thành một định dạng tài liệu, và lúc dịch sang PowerPoint lại phải bỏ gần hết |
| **Tự dựng OOXML, không thêm phụ thuộc (NFR-04)** | `.docx` và `.pptx` dựng bằng `zipfile` + XML. `.xlsx` qua `openpyxl` (đã là phụ thuộc dev) vì định dạng bảng tính có nhiều bẫy hơn hẳn — tự dựng ở đó là chuốc rủi ro để đổi lấy đúng số không. Mọi chỗ chèn chữ qua `_thoat()`: một dấu `&` trong tên linh kiện là đủ để tệp không mở được, và trình mở chỉ báo "tệp hỏng" chứ không báo dòng nào sai |
| **`.pdf` KHÔNG tự dựng** | Sinh PDF có bố cục cần bộ dàn trang. Tự viết là viết một nửa bộ dàn trang, và một nửa cho ra tài liệu **trông như đã hỏng** thay vì hỏng hẳn. Đường đi: sinh `.docx` rồi nhờ LibreOffice chuyển — công cụ ngoài, dò trước khi dùng, thiếu thì nói cách cài |
| **Nhánh PDF đã kiểm (31/08/2026)** | Cài LibreOffice 26.8.0.3 và chạy thật. Cả 5 tài liệu ra PDF (SRS 204 KB, 6 trang, ~18 s cho lượt đầu). **Vòng khép kín**: đọc ngược PDF bằng chính `eaa/pdftext.py` — 9/9 chuỗi mốc còn nguyên, dấu tiếng Việt không rụng qua chặng `docx → pdf`. `PageBreak` ra trang mới thật (ô vuông thấy trong bản Quick Look của `.docx` chỉ là cách Apple vẽ, không phải lỗi) |
| **Lỗi 1 tìm ra khi kiểm: PDF ĐÈ bản .docx đang có** | Bản `.docx` trung gian được dựng **cạnh tệp đích**, nên `design gen srs --format pdf` ghi ra `srs.docx` — đúng tên tệp lần chạy `--format docx` trước đó đã tạo. Mất một tệp bàn giao vì chạy một lệnh sinh tệp *khác* là loại hỏng người dùng không có cách nào đoán trước. Đã sửa: dựng trong thư mục tạm, chỉ chuyển PDF ra đích |
| **Lỗi 2: hai lượt chuyển song song đụng nhau** | `soffice --headless` dùng chung hồ sơ người dùng mặc định. **Đo được**: ba tiến trình song song → chỉ **2/3** sinh ra tệp. Thêm `-env:UserInstallation` riêng cho từng lượt → **3/3**. Đây không phải bắt chước: đã dựng lại đúng chế độ hỏng trước khi sửa |
| **Vì sao lỗi 2 nguy hiểm** | Chế độ hỏng của nó là `--convert-to` **trả mã 0 mà không sinh gì**. Kiểm `returncode` là chưa đủ; phải kiểm tệp có thật. Người dùng đang mở LibreOffice bằng giao diện là đủ để gặp |
| **`eaa design list` dò công cụ ngay** | Đánh dấu `✓` / `✗ CHƯA DÙNG ĐƯỢC trên máy này` cho `pdf`. Một danh sách nói được thứ nó không làm được thì tệ hơn một danh sách ngắn hơn |
| **Nhãn `cham`** | Bốn bài gọi LibreOffice thật tốn ~58 s trên tổng ~235 s. Chạy **mặc định** vì chúng là thứ duy nhất kiểm được nhánh PDF; bỏ qua bằng `pytest -m "not cham"` khi cần vòng lặp nhanh. Tự bỏ qua trên máy chưa cài LibreOffice, và "xanh vì bỏ qua" hiện ra trong bản tóm tắt pytest chứ không im lặng |
| **`--at`** | Mốc thời gian truyền vào chứ không tự lấy: dựng lại từ cùng dữ liệu phải ra cùng nội dung, nếu không thì không so được hai bản |
| **Bài canh** | `tests/test_tc82_tai_lieu_thiet_ke.py` |

## SL-106 · LỆCH THẬT (×2) · Câu trả lời "cần người làm gì" thiếu mất chuyện thiếu công cụ

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.2 (doctor); SL-82 (`eaa focus`); N-022 |
| **Cách tìm** | Phiên kiểm có người đứng giữa: người dùng ra yêu cầu, tôi chuyển cho Agent, Agent đòi gì thì tôi báo lại. Câu hỏi mở đầu — *"có việc gì BẮT BUỘC cần con người làm trước khi bạn sinh mã được?"* |
| **Lỗi 1 — Agent trả lời ĐÚNG nhưng THIẾU** | Nó chạy `eaa status`, rồi nêu **2 trong 3** việc: phân xử xung đột chân, duyệt G1. Bỏ mất chuyện máy thiếu cả **5** công cụ toolchain, nên mọi cổng kiểm chứng đều không chạy được. Hỏi lại lần hai và ép nó kiểm thì nó gọi `capabilities` và nêu đủ — **năng lực CÓ, chỉ là nó không nghĩ tới** |
| **Lỗi 2 — `eaa focus` cũng thiếu đúng chặng ấy** | Nặng hơn, vì lệnh này hứa "cả quãng đường, một lần". Nó in `✓ Chuỗi kiểm chứng đủ cổng` trong khi 5 công cụ chạy chuỗi ấy không tồn tại: nó kiểm Platform Pack **khai đủ cổng** chưa, không kiểm công cụ **có trên máy** không. Hai câu hỏi khác nhau; trả lời câu thứ nhất rồi tích xanh là trả lời nhầm câu |
| **Hệ quả nếu không sửa** | Người dùng đọc dấu tích, đi duyệt G1, chờ sinh mã — rồi mới đâm vào đúng bức tường mà lệnh này sinh ra để báo trước |
| **Sửa bằng CẤU TRÚC, không bằng lời dặn** | Cách hiển nhiên là dặn Agent "nhớ gọi thêm `capabilities`". Lời dặn ấy đúng cho câu hỏi này và trượt ở câu diễn đạt khác — mà số cách diễn đạt thì vô hạn. `eaa status` là **đường tắt hấp dẫn** vì nó trông như đã trả lời, nên chỗ sửa là chính nó: cho bản tóm tắt nói ra công cụ còn thiếu thì đường tắt cũng thành đường đúng, cho cả Agent lẫn người đọc |
| **Đã sửa** | `_in_cong_cu_thieu()` trong `eaa/cli.py`, gọi từ `_in_tom_tat` — nêu tên công cụ, cổng bị chặn, **hậu quả** ("chưa merge được"), và `→ CẦN BẠN: eaa doctor --fix`. Đặt TRƯỚC bảng gate: cái chặn cứng phải hiện trước cái chờ quyết định. `analyse()` trong `eaa/focus.py` nhận thêm `missing_tools` và sinh chặng "Công cụ chạy được các cổng ấy", thuộc `NGƯỜI` vì cài đặt đổi máy người dùng (N-022) |
| **Giữ kỷ luật của `focus.py`** | Nó vẫn **không tự đi dò** — CLI hỏi doctor rồi truyền xuống. Hai bộ dò công cụ ở hai chỗ thì cái lỏng hơn luôn là cái được tin. TC-83 quét `focus.py` và đỏ nếu thấy `shutil.which` / `subprocess` / `Doctor(` |
| **Im lặng khi đủ** | Không in dòng "mọi thứ ổn". Một dòng như thế lặp ở mọi bản tóm tắt sẽ bị mắt bỏ qua, và lúc nó đổi thành cảnh báo thì cũng bị bỏ qua nốt |
| **Kiểm lại bằng chính câu hỏi cũ** | Hỏi Agent y nguyên câu ban đầu. Cùng một lệnh `status`, giờ nó nêu **đủ 3 việc** và tách riêng phần "lệnh bạn cần tự chạy (tôi không được phép)" |
| **Kèm theo** | Một bài TC-72 cũ dò chặng theo **chỉ số** `preconditions[1]` nên vỡ khi thêm chặng mới. Đổi sang dò theo tên — chỉ số vào một danh sách còn dài ra là cách viết sẽ vỡ lại |
| **Bài canh** | `tests/test_tc83_san_sang_day_du.py` — 9 bài |

## SL-107 · LỆCH THẬT (×4) · Chỗ nháp sinh ra đã hỏng, và đường nạp tri thức đi vòng qua kiểm nguồn

| | |
|---|---|
| **Tài liệu** | SL-78 (`eaa scratch`); SL-71 (hai hạng nguồn); AIS §4.1 |
| **Cách tìm** | Phiên kiểm có người đứng giữa, với một kit thật thuộc **họ MCU khác** dự án đang mở. Người dùng chỉ nói tên bo; mọi thứ còn lại do Agent tự dò |
| **Lỗi 1 — chỗ nháp sinh ra đã hỏng** | `eaa scratch` ghi `mcu: "chưa xác định"` — một **chuỗi** ở chỗ lược đồ `eaa/kb.py` đòi ánh xạ. Mọi lệnh dựng Knowledge Graph sập ngay từ lượt chạy đầu tiên. Một chỗ làm nháp không chạy nổi một lệnh thì nó không giảm việc phải gõ, nó thêm việc phải gỡ |
| **Lỗi 2 — sập bằng traceback Python** | `dict("chuỗi")` ném `ValueError: dictionary update sequence element #0 has length 1; 2 is required` — không nói tệp nào, trường nào, sửa thế nào. Nó lọt qua **mọi** lớp bắt lỗi của CLI và ra tới người dùng nguyên vẹn, dù `main()` khai rõ "lỗi miền được đổi thành thông điệp + mã thoát, không phải traceback" |
| **Đã sửa 1–2** | `_HARDWARE` dùng `mcu: {}` — rỗng-nhưng-đúng-kiểu nói cùng một chuyện với "chưa xác định", bằng thứ ngôn ngữ phần còn lại của hệ đọc được. `HardwareProfile._anh_xa()` / `._danh_sach()` ném `KbError` nêu **tệp, trường, kiểu đúng, và cách để trống** |
| **Lỗi 3 — sai Platform Pack, IM LẶNG** | `eaa scratch --platform` mặc định một pack cố định, nên chỗ nháp cho bo họ khác nhận sai trình biên dịch, sai bộ luật phân tích tĩnh, sai khuôn mẫu firmware. **Tệ hơn một lần sập**: sập thì người ta sửa, còn giá trị sai mà im lặng thì mọi thứ dựng lên trên nó đều sai theo, và cái sai chỉ lộ ra ở cổng biên dịch |
| **Đã sửa 3** | `chon_platform()` suy từ tên chỗ nháp, đối chiếu **tên pack đang cài**; khớp đúng một thì dùng và **khai rõ là GIẢ ĐỊNH**; không suy được thì **HỎI** kèm danh sách pack, không mặc định bừa. Lý do chọn ghi thẳng vào đầu `constraints.yaml`. Suy từ tên vẫn là đoán — nhưng đoán từ bằng chứng, nói ra là mình đoán, và từ chối khi bằng chứng không đủ; một hằng số cũng là đoán, chỉ khác là nó bỏ qua bằng chứng và không nói gì |
| **Lỗi 4 — đường nạp tri thức ĐI VÒNG qua kiểm nguồn** | `eaa read` từ chối PDF và chỉ sang `eaa datasheet add`, nhưng lệnh ấy **chỉ nhận tệp cục bộ**. Người dùng phải tự tải bằng trình duyệt — việc tải ấy nằm **ngoài** `eaa/web.py`, nên **không có phân hạng nguồn nào xảy ra**. Một PDF lấy từ trang chia sẻ tài liệu bất kỳ vào kho tri thức y hệt bản lấy từ miền nhà sản xuất, và không gì ghi lại khác biệt. Cả hệ thống hai hạng bị đi vòng qua bởi đúng con đường duy nhất thật sự nạp tri thức |
| **Đã sửa 4** | `WebFetcher.fetch_binary()` — cùng bộ chặn URL, cùng phép kiểm từng chặng chuyển hướng, cùng phép tính hạng theo **URL cuối**; khác đúng chỗ không bóc chữ và có trần riêng 80 MB. `eaa datasheet add` nhận URL, tải qua đó, **từ chối hạng `mở`**, lưu vào `datasheets/_taive/`. Lệnh vẫn là lệnh CỦA NGƯỜI (G2) — cái thêm vào là chỗ tải, không phải quyền duyệt |
| **Kiểm thật** | Tải `UM1842` từ `st.com`: 1.695.359 byte, hạng `chính chủ`, dựng chunk đề xuất 36 trang. Chiều ngược: một URL `wikipedia.org` bị từ chối đúng lý do |
| **Ghi nhận** | TC-38 bắt tôi ngay khi tôi viết tên bo cụ thể vào comment của `eaa/scratch.py`. Cổng thuần khiết engine làm đúng việc của nó — kể cả với người đang sửa nó |
| **Lỗi 5 (tìm khi kiểm lại) — nhãn "chỗ nháp" chỉ hiện MỘT lần** | `eaa/scratch.py` khai ở đầu module: *"Chúng mang nhãn GIẢ ĐỊNH trong chính tệp, và `eaa status` nhắc lại."* Vế sau không đúng — `warning_banner()` chỉ được gọi bởi chính lệnh `eaa scratch`, tức đúng một lần lúc dựng. Mọi lệnh sau đó im. Hậu quả là đúng thứ chính module ấy cảnh báo: *"một con số mặc định trông y hệt một con số đã chốt, và đó là cách một bản nháp lặng lẽ trở thành một bản bàn giao"* |
| **Đã sửa 5** | `_in_nhan_nhap()` gọi từ `_in_tom_tat`. Và nhãn giờ nêu **đích danh** những số đang giả định (`flash_bytes = … · ram_bytes = … · f_cpu_hz = …`) kèm câu "bo thật của bạn gần như chắc chắn KHÁC những số này". Nói "có giả định" thì không ai kiểm được; nói ra con số thì người đang cầm bo nhìn một cái là biết sai |
| **Bài canh** | `tests/test_tc84_scratch_va_nap_url.py` — 22 bài |

## SL-108 · LỆCH THẬT · `eaa ports` trả lời sai LOẠI câu hỏi, và không bắt được cắm nhầm bo

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (chẩn đoán phần cứng); EAA-SDD-03 §2 (cây thư mục) |
| **Cách tìm** | Người dùng báo đã cắm bo. `eaa ports` trả lời *"Không cổng nào khớp bo đã khai"* — và câu ấy không trả lời được câu hỏi thật |
| **Lỗi — "có cổng nối tiếp không" KHÁC "bo đã nhận chưa"** | `eaa ports` chỉ liệt kê cổng nối tiếp. Nhưng nhiều bo phát triển nối máy qua **mạch nạp/gỡ rối gắn sẵn trên bo**, hiện ra như một thiết bị USB thô và **không sinh cổng nối tiếp nào**. Cắm đúng, nguồn đủ, mạch nạp chạy tốt, mà `/dev/cu.*` vẫn không có gì mới |
| **Vì sao nhập nhằng ở đây tốn kém** | *"Chưa cắm"* và *"cắm rồi nhưng bo này không có cổng nối tiếp"* dẫn tới hai việc khác hẳn: một bên đi kiểm dây và cổng, một bên đi tiếp. Đây là **bước đầu tiên chạm vào thế giới vật lý**, nên đi sai đường ở đây kéo theo cả chuỗi |
| **Đã sửa** | `eaa/usbdev.py` — liệt kê thiết bị USB bằng lệnh sẵn có của từng hệ (`ioreg` / `lsusb` / sysfs / `Get-PnpDevice`), không thêm phụ thuộc (NFR-04). `eaa ports` in thêm mục "Thiết bị USB" và đối chiếu với `programmer.usb` của dự án |
| **"Không kiểm được" KHÁC "không có gì"** | Không lệnh nào chạy được thì trả `UsbScan` mang mức KHÔNG KIỂM ĐƯỢC kèm lý do — **không** trả danh sách rỗng. Rỗng đọc thành "không có gì cắm", đúng câu sai module này sinh ra để tránh. Kiểm được mà thấy rỗng thì nói dứt khoát: *"bo chưa được máy nhận; đây KHÔNG phải chuyện thiếu trình điều khiển — kiểm dây, kiểm đúng cổng trên bo, kiểm nguồn"* |
| **Thêm: bắt CẮM NHẦM BO** | Câu lệnh này chưa từng trả lời. Người dùng cắm một bo thuộc họ khác thì mã dịch xong, nạp xong, rồi mới không chạy — kiểu hỏng đắt nhất trong nhóm này. Giờ có cảnh báo nêu đích danh thiết bị lạ. Chỉ bắn khi dự án ĐÃ khai bo của mình: chưa khai thì mọi thiết bị đều "không khớp", và một cảnh báo bắn vào mọi trường hợp là một cảnh báo bị bỏ qua |
| **Lọc thiết bị của máy chủ** | Bàn phím, camera, bộ điều khiển nội bộ không phải bo người dùng vừa cắm. Danh sách vendor ấy là dữ liệu về MÁY CHỦ, không phải về phần cứng đích, nên không vi phạm ranh giới engine |
| **Bug tự tôi gây khi sửa** | `_bon_so()` gộp hai kiểu vào bằng một phép `isdigit()`. `ioreg` in **thập phân**, `lsusb` in **hex** — nên một chuỗi hex toàn chữ số bị đọc thành thập phân rồi in lại thành một mã khác hẳn, im lặng. Một bo đúng sẽ bị chấm là lạ, và một bo lạ có thể lọt. Đã tách hợp đồng: chuỗi = hex, số nguyên = giá trị thật |
| **TC-38 bắt tôi hai lần** | Tôi viết mã VID thật vào ví dụ trong docstring. Ví dụ giờ dùng số bịa: mã VID/PID thật thuộc về hồ sơ dự án, không thuộc về engine |
| **Thêm: `eaa ports --watch`** | Chụp-một-lần là chưa đủ khi bo không hiện ra: người dùng phải đoán giữa nhiều nguyên nhân — dây chỉ có nguồn, sai cổng trên bo, hỏng cáp chuyển, cổng máy chết — và cách duy nhất phân biệt là **thử từng cái rồi xem ngay kết quả**. Chụp một lần thì mỗi lần thử phải gõ lại lệnh và tự nhớ lần trước thấy gì. Chế độ canh chỉ ĐỌC, có hạn giờ, nên nó là một phép đo có kết thúc chứ không phải một chế độ chạy dài |
| **Hết giờ mà bus không đổi là một KẾT LUẬN** | Không phải một sự im lặng. Lệnh nói thẳng: máy không nhận được gì mới, chuyện này xảy ra **trước cả tầng trình điều khiển**, nên đi kiểm dây có đủ đường dữ liệu chưa và đúng cổng trên bo chưa |
| **Bài canh** | `tests/test_tc85_thiet_bi_usb.py` — 21 bài |

---

## SL-109 · LỆCH THẬT (×2) · Bộ đọc `ioreg` nuốt mọi thiết bị cắm qua hub

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (chẩn đoán phần cứng); SL-108 |
| **Cách tìm** | Người dùng cắm bo AVR qua đế cắm. `ioreg` thấy nó; `eaa ports` liệt kê 6 thiết bị và **không có nó**. Đối chiếu thẳng đầu ra `ioreg` với bản in của lệnh |
| **Lỗi 1 — tiền tố nhánh không phải khoảng trắng** | Bộ đọc tách nút bằng `re.split(r"\n\s*\+-o ")`. `ioreg` vẽ nhánh đang mở bằng **gạch dọc**: một nút nằm sâu có dạng `\|   \| +-o Tên@địa-chỉ`. `\s` không khớp `\|`, nên **mọi nút con không được nhận ra là nút** |
| **Hỏng theo hướng nguy nhất** | Không sập, không cảnh báo. Nội dung nút con bị gộp vào khối của nút cha, `re.search` lấy mã đầu tiên trong khối — nên mỗi nhánh chỉ còn lại **thiết bị đầu tiên**, mà thiết bị đầu tiên của một nhánh chính là **cái hub**. Cái bị nuốt luôn là cái đang đi tìm. Bản in vẫn mang nhãn **ĐÃ KIỂM** |
| **Đo được** | Cùng một máy, cùng một lúc: trước 6 thiết bị, sau **16**. Bo của dự án mẫu (`1a86:7523`, nằm sau hai tầng hub) từ *không thấy* thành *khớp phần khai* |
| **Vì sao bài kiểm cũ không bắt được** | Đầu ra `ioreg` giả trong bài kiểm **phẳng hơn đời thật** — mọi nút cùng một mức thụt lề bằng khoảng trắng. Bài kiểm dựng lại đầu ra mà không đối chiếu với đầu ra thật thì nó canh đúng cái nó tưởng tượng ra |
| **Lỗi 2 — cảnh báo "cắm nhầm bo" bắn cả khi bo ĐANG CÓ MẶT** | Sau khi sửa lỗi 1, lệnh nhận đúng bo rồi **vẫn** cảnh báo *"đang cắm 7 thiết bị ngoài, KHÔNG cái nào khớp"* — bảy thứ ấy là hub, card mạng, đầu đọc thẻ |
| **Vì sao nghiêm trọng** | Lý do cảnh báo tồn tại rất hẹp: *mã dịch xong, nạp xong, rồi mới không chạy*. Lý do ấy **tắt ngay khi bo đã khai có mặt trên bus**. Bắn tiếp là nổ ở mọi bàn có đế cắm — tức là thành thứ bị bỏ qua, đúng cái bẫy mà chính docstring của hàm nêu ra để tránh (SL-108) |
| **Đã sửa** | `eaa/usbdev.py`: tách nút bằng `^[ \t\|]*\+-o ` theo từng dòng. `eaa/cli.py::_thiet_bi_la`: thấy bo đã khai thì trả rỗng — câu hỏi đã có trả lời |
| **Bài học** | Hai bản sửa trước (SL-108) dựng đúng *kiến trúc* câu trả lời — phân biệt "không kiểm được" với "không có gì", bắt cắm nhầm bo — trên một tầng đọc đầu ra sai. Kiến trúc đúng không cứu được dữ liệu vào sai, và cái sai ấy chỉ lộ ra khi có **phần cứng thật cắm qua đế cắm thật** |
| **Bài canh** | `tests/test_tc85_thiet_bi_usb.py` — 25 bài (thêm 4), trong đó đầu ra `ioreg` giả nay dựng đúng cây có nhánh `\|` |



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
