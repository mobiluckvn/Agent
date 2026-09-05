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

## SL-110 · LỆCH THẬT (×3) · Cổng cài công cụ là một NGÕ CỤT, không phải một cổng

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.4; FR-ENV-02; SL-77 (`tool approve` → `tool run`) |
| **Cách tìm** | Tôi báo với người dùng rằng `doctor --fix` cần họ tự gõ lệnh cài. Họ trả lời: *"Agent phải hỏi bạn về bộ công cụ đó và tự cài chứ"* |
| **Lỗi 1 — dừng mà không nêu lối đi tiếp** | Xác nhận cài chỉ tồn tại dưới dạng câu hỏi trên terminal, **trong cùng tiến trình**. Phiên không có terminal thì doctor dừng và hết đường. So sánh: `gates.confirm_interactive` gặp đúng tình huống ấy còn nêu đích danh `eaa gate approve <G>` — người quyết định ngoài luồng, quyết định được ghi lại, máy đọc ra ở lượt sau |
| **Hệ quả không phải an toàn hơn, mà là KHÔNG DÙNG ĐƯỢC** | Mọi phiên làm việc qua người trung gian, qua chat, qua CI đều cụt đường ở chỗ cài — dù người có đồng ý bao nhiêu lần. Một cổng mà không ai đi qua được thì nó không bảo vệ gì, nó chỉ chặn |
| **Lỗi 2 — "không có ai để hỏi" bị khai thành "người dùng từ chối"** | `_hoi_xac_nhan_cai()` trả `False` cho hai chuyện khác hẳn nhau. Quyết định an toàn vẫn đúng (không cài); **lời khai về lý do** thì sai. Kỹ sư đọc *"người dùng từ chối"* sẽ đi tìm xem ai đã từ chối — hoặc đọc thành "đã có người quyết định không cài" rồi đi tiếp |
| **Trớ trêu** | `doctor.py` đã có sẵn câu đúng (`InstallNotConfirmed`: *"phiên này không có ai để xác nhận"*), nhưng nhánh ấy chỉ chạy khi `confirm is None`, mà CLI luôn truyền vào một hàm. **Mã đúng nằm chết, câu sai thì sống** |
| **Lỗi 3 — lời giải thích cho lệnh hai từ không bao giờ tới người đọc** | `NGOAI_DANH_MUC` có khóa hai từ (`tool approve`, `skill approve`), mà `_vi_sao_khong()` tra bằng `argv[0]`. Nên mọi lời giải thích ấy được viết ra, đi vào prompt, và **không bao giờ khớp** — người hỏi nhận câu chung chung, đúng chỗ một câu cụ thể là hữu ích nhất |
| **Đã sửa — thêm sổ duyệt lệnh cài** | `eaa doctor approve <công cụ>... --actor <tên>` ghi nối tiếp vào `install_approvals.jsonl`. `doctor --fix` có ba đường tới chỗ chạy và chỉ ba: (1) sổ có người duyệt ĐÚNG lệnh này, (2) có người ở terminal và người ấy đồng ý, (3) không còn đường nào |
| **Bất biến KHÔNG đổi** | Không lệnh cài nào chạy mà thiếu một người duyệt **đúng lệnh ấy**. Cái đổi là ai gõ phím lúc chạy — sau khi người duyệt, Agent chạy. Cùng hình dạng `tool approve` (người) → `tool run` (Agent) của SL-77: *Agent mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ* |
| **Duyệt MỘT lệnh, không duyệt chung chung** | Quyết định neo vào băm của **dãy đối số**, không phải chuỗi hiển thị — `["brew","install","a b"]` và `["brew","install","a","b"]` là hai lệnh khác nhau và phải băm khác nhau. Manifest đổi lệnh cài sau khi duyệt thì quyết định cũ hết hiệu lực. Không có tính chất này thì *"duyệt cài X rồi cài Y"* là một đường vòng hợp lệ về mặt kỹ thuật, vì manifest là dữ liệu và dữ liệu thì đổi được — kể cả bởi một đề xuất công cụ mới |
| **Hỏi MỘT LẦN cho cả bộ** | Năm công cụ thiếu thì nêu cả năm rồi dừng một lần. Dừng ở cái đầu tiên bắt người duyệt xong lại chạy lại để biết cái thứ hai — mỗi lượt một tin, và họ không bao giờ thấy toàn cảnh việc mình đang đồng ý |
| **Sổ hỏng đọc thành "chưa duyệt"** | Hướng hỏng an toàn chỉ có một chiều. Dòng JSON hỏng bị bỏ qua, không làm sập lệnh và tuyệt đối không đọc thành "đã duyệt" |
| **Ranh giới quyền** | `doctor approve` **không** nằm trong `TOOLBOX`; `doctor` (quét, chỉ đọc) và `doctor --fix` thì có. Trước đây cả lệnh `doctor` bị chặn kể cả chế độ đọc, trong khi chính lời giải thích đi kèm khai là *"tôi quét và báo được"* — lại một chỗ mã lệch với lời chính nó khai |
| **Lỗi 4 — `tool_for` khớp theo TIỀN TỐ, nên mọi mục là một cửa mở** | Suýt lọt, và **bài canh cũ bắt được**: thêm mục `doctor` để Agent quét máy thì mở luôn `doctor approve`, `doctor --accept-drift`. Đã sửa ở gốc chứ không vá riêng: mục không khai `takes` thì không nhận thêm đối số nào |
| **Vì sao chỗ này đáng sợ hơn cả ba lỗi trên** | Hàng rào của cả sản phẩm là **danh mục**. Một mục đọc như *"được gọi `doctor`"* mà thực tế là *"được gọi bất cứ gì bắt đầu bằng `doctor`"* thì bảng quyền hạn không còn đọc được — và một bảng quyền hạn không đọc được thì không ai kiểm được nó, kể cả người viết ra nó |
| **Bài canh** | `tests/test_tc86_duyet_cai_cong_cu.py` — 11 bài; `tests/test_tc34_doctor.py` +2; `tests/test_tc61_chat.py` và `tests/test_tc71_skills.py` đổi để ghi lập luận mới (`doctor --fix` được phép VÌ nó không cài được gì chưa duyệt; `doctor approve` vào thế chỗ trong danh sách cấm) |

---

## SL-111 · LỆCH THẬT (×3) · Cài trượt mà không nói vì sao, và một lệnh cài chưa từng chạy được

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.4; FR-ENV-02; SL-100 (lớp quan sát bỏ đầu ra); SL-110 |
| **Cách tìm** | Lần ĐẦU TIÊN đường `doctor approve` → `doctor --fix` chạy thật, trên máy thật, với bộ công cụ AVR thật. Ba lỗi, và cả ba chỉ lộ ra khi lệnh cài TRƯỢT — nhánh mà không bài kiểm nào từng đi vào với dữ liệu thật |
| **Lỗi 1 — nhật ký nuốt lỗi của chính lệnh vừa chạy** | `_run_install` bắt đầu ra bằng `capture_output=True` rồi **vứt đi**, chỉ ghi `lần 1 thất bại (mã 1)`. Câu hữu ích nhất — *"No available formula with the name avr-gcc"* — nằm sẵn trong tay và không tới được ai |
| **Vì sao "mã 1" tệ hơn là vô dụng** | Nó *trông như* một chẩn đoán. Người đọc không phân biệt nổi **mạng hỏng** với **sai tên gói**, mà hai chuyện ấy dẫn tới hai việc trái ngược: một bên thử lại, một bên sửa manifest. Và vì không phân biệt được, doctor thử lại **hai lần** một lỗi hoàn toàn tất định |
| **Lỗi 2 — manifest chỉ khai được MỘT lệnh mỗi hệ** | Trên macOS, `avr-gcc` nằm trong kho ngoài `osx-cross/avr` và phải thêm kho trước — hai bước. Nên mục macOS trong `packs/avr/tools.yaml` là một **khẳng định sai**: nó bảo *"cài bằng lệnh này"*, mà lệnh ấy **chưa từng chạy được lần nào** |
| **Sai im lặng, và ngủ yên rất lâu** | Mục ấy mang `approved_by: vu-tri-cong` từ 29/08 — tức là đã đi qua G2. Cổng duyệt được **nội dung do máy đề xuất**, nhưng không ai chạy thử nó; và một lệnh cài chỉ chứng minh được bằng cách chạy. Nó nằm im tới đúng hôm có người thật sự đi cài |
| **Lỗi 3 — quyết định duyệt neo vào MỘT lệnh, trong khi thứ chạy là một DÃY** | Sau khi thêm bước chuẩn bị, nếu băm vẫn chỉ phủ lệnh cuối thì chèn thêm một bước vào trước là **chèn được mã tùy ý sau lưng người duyệt**, mà quyết định cũ vẫn trông hợp lệ. Đó đúng là tính chất duy nhất làm cho việc Agent tự cài là an toàn (SL-110) |
| **Đã sửa** | `ToolSpec.pre_install` (theo hệ điều hành) + `Doctor.install_steps()` trả TOÀN BỘ dãy. Sổ duyệt lưu `commands` (dãy) và băm cả dãy. `_run_install` chạy đủ dãy, **dừng sớm** khi một bước trượt, và in đầu ra thật của lệnh — giữ 12 dòng CUỐI (lỗi nằm ở cuối), khai rõ đã bỏ bao nhiêu dòng |
| **`pre_install` chỉ gắn cho mục thật sự cần** | `avrdude` và `cppcheck` nằm trong kho lõi. Gắn thêm một kho ngoài cho chúng là bắt người duyệt một thứ họ không cần — và một cổng đòi thừa thì sớm muộn bị bấm cho xong |
| **Quan sát về cách tìm ra cả ba** | Không lỗi nào tìm được bằng đọc mã. Cả ba đòi: máy thật, gói thật, và một lệnh **thật sự trượt**. Nhánh xử lý lỗi là nhánh ít được chạy nhất và nhiều giả định nhất |
| **Bài canh** | `tests/test_tc87_cai_that_bai.py` — 8 bài, trong đó một bài đòi manifest thật của pack AVR khai được đường cài **trên chính hệ đang chạy** |



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

---

## SL-112 · LỆCH THẬT (×3) · Ràng buộc cứng KHÔNG vào prompt hội thoại

| | |
|---|---|
| **Tài liệu** | CLAUDE.md (bất biến trung tâm); EAA-SRS-01 FR-KB-01; TC-04 |
| **Cách tìm** | Bài 1 phiên kiểm bo thật. Giao: *"kiểm kênh UART giữa máy tính và bo"*. Agent trả về mã Arduino dùng `delay(1000)` và `Serial.println` ở 9600 baud, kèm hướng dẫn `arduino-cli` |
| **Bốn chỗ sai trong một câu trả lời** | `delay()` — dự án CẤM đích danh. `Serial.println` — I/O chặn, cũng cấm (`blocking_io`). `9600` — hồ sơ khai `115200`. `arduino-cli` — quy trình NGOÀI sản phẩm, không qua cổng nào |
| **Lỗi 1 — bất biến "100%" chỉ đúng một nửa** | CLAUDE.md và FR-KB-01 nói ràng buộc "nạp vào **100% lần gọi LLM**". TC-04 canh điều đó, nhưng **chỉ canh `PromptComposer`** — đường sinh mã. `eaa chat` dựng `Prompt` riêng của nó, và lớp ràng buộc không có ở đó |
| **Cưỡng chế sai chỗ** | Đường được canh là đường máy tự chạy; đường bỏ trống là đường **người dùng gõ câu hỏi vào**. Một con số "100%" chỉ đúng khi có thứ gì đó đếm được cả 100% |
| **Lỗi 2 — prompt không nói mô hình đang làm với chip nào** | Lớp trạng thái có thư mục, pha, gate, backlog — không có MCU, không có tốc độ truyền. Mô hình **không im lặng về chỗ nó không biết: nó đoán**, và một đoán sai ở đây kéo theo sai thanh ghi, sai hệ số chia, sai cả lệnh nạp |
| **Lỗi 3 — danh sách lệnh cấm là tên TRẦN** | Prompt chỉ nói *"KHÔNG có: build, gen, flash…"*. Mô hình đọc thành *"sản phẩm này không làm được việc đó"* rồi đi tìm công cụ ở ngoài. Sự thật ngược lại: đó là phần mạnh nhất của sản phẩm, chỉ là **người** gõ chúng. Lời giải thích đã viết sẵn trong `NGOAI_DANH_MUC` — **mã đúng nằm chết** vì không có đường tới nơi cần nó (lần thứ ba trong phiên gặp đúng dạng này) |
| **Đã sửa** | Lớp `constraints` BẮT BUỘC, đứng đầu prompt hội thoại, gọi lại `composer._bang_rang_buoc` chứ không chép — hai bảng dựng bằng hai đoạn mã sẽ lệch nhau, và lúc lệch thì đường này cho phép đúng thứ đường kia cấm. Thêm dòng phần cứng vào lớp trạng thái. Danh sách lệnh của người kèm câu "ĐỀ NGHỊ người dùng gõ" và cấm đi tìm công cụ ngoài sản phẩm |
| **Đo được sau khi sửa** | Cùng câu hỏi: Agent đi đúng `plan add → gen → build → flash → telemetry`, baud 115200, tự chạy `plan add`, dừng đúng chỗ tắc (thiếu `avr-gcc`, G1 chưa duyệt) |
| **Bộ kiểm ngân sách bắt bản sửa của chính tôi** | Thêm dòng phần cứng làm lớp `state` vượt 416/400 token, và hệ **từ chối gọi API** thay vì gửi một prompt hỏng (TC-16) |
| **Bài canh** | `tests/test_tc88_chat_rang_buoc.py` — 6 bài, trong đó một bài quét mã nguồn dạng TC-38: mọi chỗ dựng `Prompt(` phải có lớp ràng buộc, hoặc nằm trong danh sách miễn trừ **có ghi lý do** |
| **Còn treo** | `eaa/interfaces.py` sinh CHỮ KÝ HÀM cho firmware và đã nhận `constraints.limits`, nhưng **chưa nhận `forbidden`**. Chữ ký chưa phải thân hàm nên chưa xếp là lỗi; nhưng *"hàm này có chặn không"* là đúng câu mà `blocking_io` nói thẳng |

---

## SL-113 · LỆCH THẬT (×2) · Một tính chất an toàn có hàm, có test, KHÔNG có người gọi

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §9.4; TC-35; NFR-07 |
| **Cách tìm** | Đi tìm đường cài `avr-gcc` trên máy mà Homebrew không có bản dựng sẵn. Đường thiết kế đã chừa cho đúng tình huống ấy là `download` + `checksum`. Đọc mã thì thấy đường ấy **không tồn tại** |
| **Lỗi 1 — checksum được KHAI chứ không được TÍNH** | `Doctor.verify_checksum()` có, có bài kiểm riêng, và **không nơi nào trong engine gọi nó**. `fix()` gặp `download` + `checksum` thì in ra *"tải trực tiếp từ …, bắt buộc khớp checksum …"* rồi chạy lệnh cài như thường. Không tải, không tính, không đối chiếu |
| **Vì sao đây là dạng hỏng tệ nhất** | Không phải thiếu một tính năng, mà là **một lời hứa an toàn được in ra cho người đọc tin**. Bảng test xanh, docstring khai có tính chất, đường chạy thật thì trống |
| **Lỗi 2 — duyệt G1 không chốt lại băm ràng buộc** | `eaa status` cảnh báo trôi băm và chỉ sang *"chốt lại bộ ràng buộc mới qua gate G1"*. Làm đúng thế thì cảnh báo **vẫn còn nguyên**: `constraints_version` chỉ được ghi MỘT lần ở `eaa init`, không đường nào chốt lại. Lệnh chỉ sang một cánh cửa không tồn tại — cùng hình dạng ngõ cụt với SL-110 |
| **Đã sửa** | `_run_install` tải → tính băm → đối chiếu → **rồi mới** chạy lệnh nào; chỗ giữ `{tai_ve}` thay bằng đường dẫn gói ĐÃ KIỂM. Khai `download` mà quên `checksum` là lỗi nói ra, không phải một lượt tải im lặng. `_gate_approve` ghim lại băm sau khi người duyệt G1 |
| **Ghim băm ở G1 là AN TOÀN, không phải tiện** | Hồ sơ G1 người vừa đọc CHỨA nội dung ràng buộc, và quyết định neo vào băm hồ sơ ấy. Ta ghi lại băm của **đúng thứ họ vừa duyệt**. Cố ý KHÔNG có lệnh riêng để ghim: một lệnh "chấp nhận băm mới" tách khỏi việc đọc hồ sơ chính là lối tắt thiết kế cấm |
| **Kết quả trên dự án thật** | Nợ kỹ thuật của `robot_balance` từ Sprint 2 — ghi trong sổ bàn giao phiên trước — đã sạch |
| **Bài canh** | `tests/test_tc89_tai_va_kiem_checksum.py` — 5 bài, trong đó một bài quét mã nguồn đòi `verify_checksum` phải **có người gọi trong engine** |
| **Bug tự tôi gây khi viết bài kiểm** | Bài kiểm gán thẳng `eaa.doctor.subprocess.run` — mà thuộc tính ấy là chính module `subprocess` toàn cục. Mọi bài chạy sau trong cùng phiên hỏng theo, và hỏng **im lặng** vì lệnh con vẫn "thành công" |

---

## SL-114 · LỆCH THẬT (×2) · Cổng `size` trượt bằng lỗi CÚ PHÁP CÔNG CỤ, và vòng tự sửa đốt một lượt vì nó

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §6 (vòng tự sửa); FR-ENV-05 (Thẻ công cụ) |
| **Cách tìm** | `eaa gen drv_uart` với toolchain thật: `compile` ĐẠT, `size` KHÔNG ĐẠT — `avr-size: invalid option -- m` |
| **Lỗi 1** | Pack gọi `avr-size --format=avr -mmcu={mcu}`. Dạng `-mmcu` là cờ của **trình biên dịch**; `avr-size` là công cụ binutils và chỉ nhận dạng dài `--mcu=`. Bản dựng nào chấp `-mmcu` là chấp thêm, không phải chuẩn |
| **Hệ quả không dừng ở một cổng trượt** | Vòng tự sửa nhận thông báo lỗi ấy như một lỗi MÃ, gửi cho mô hình, và đốt một lượt gọi để "sửa mã" cho một lỗi **không nằm trong mã**. Vòng ấy chỉ có N=3 lượt |
| **Thẻ công cụ không chứng minh được điều nó khai** | Thẻ ghi *"cú pháp gọi đã được chứng minh chạy được trên chính máy này"*, nhưng bằng chứng chỉ là `avr-size --version` — một lệnh chạy được bất kể cổng `size` có gọi đúng cú pháp hay không |
| **Lỗi 2 — yêu cầu phiên bản khai ở HAI chỗ** | `tool_requirements` trong `pack.yaml` lặp lại `min_version` trong `tools.yaml` của cùng pack, và hai bên **đã lệch nhau**. Không phép kiểm nào đối chiếu, nên chỗ nào đúng thì chưa có gì trả lời được |
| **Đã sửa** | `--mcu={mcu}`; hai danh sách phiên bản kéo về khớp nhau kèm cảnh báo tại chỗ về việc chúng lặp |

---

## SL-115 · LỆCH THẬT · Bảng kiểm sẵn sàng tuyên "THIẾU 0" cho một module không sinh mã nổi

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §6.2 (Readiness Check); FR-KG-01 |
| **Cách tìm** | `eaa resolve drv_uart` → *"CÓ 6 · THIẾU 0 · MÂU THUẪN 0 — Đủ điều kiện mở vòng sinh mã"*. Vòng sinh mã chạy ngay sau đó và mô hình viết vào tệp tiêu đề: *"THIẾU THÔNG TIN: ds-041 không có thông tin về thanh ghi dữ liệu (UDR0) và các cờ trạng thái (UDRE0, RXC0) […] module này không lấp chỗ trống"* |
| **Cả hai đều đúng phần của mình — đó mới là vấn đề** | Bảng kiểm đi theo cạnh `ngoại vi –configured_by→ thanh ghi` của Knowledge Graph, mà `configured_by` là danh sách **VIẾT TAY** trong `hardware_profile.yaml`. Nó liệt kê năm thanh ghi CẤU HÌNH của cổng nối tiếp và không liệt kê thanh ghi DỮ LIỆU |
| **Khoảng cách giữa câu hỏi và câu được hiểu** | Phép kiểm trả lời *"có tài liệu cho những thanh ghi ĐÃ KHAI không"*; người đọc hiểu nó là *"module này sinh mã được chưa"*. Khoảng cách giữa hai câu ấy đúng bằng những thanh ghi không ai nghĩ tới — và thứ duy nhất tìm ra chúng là chính vòng sinh mã, **sau khi đã trả tiền cho nó** |
| **Không sửa được bằng cách làm phép kiểm toàn tri** | Một thanh ghi không ai khai là một chỗ thiếu không ai thấy; đó là giới hạn của mọi bảng kiểm suy từ dữ liệu người nhập. Nhưng **nói đúng phạm vi mình phủ** thì làm được, và đó là khác biệt giữa một phép kiểm hữu ích và một phép kiểm gây hiểu nhầm |
| **Đã sửa** | `eaa resolve` in kèm phạm vi: bảng kiểm đi theo `configured_by`, một danh sách do người viết tay; *"THIẾU 0"* nghĩa là *"không thiếu trong số đã khai"*, không phải *"không thiếu gì"*. Câu kết luận đổi thành *"Đủ điều kiện — TRONG PHẠM VI ĐÃ KHAI"* |
| **Bài canh** | `tests/test_tc90_pham_vi_bang_kiem.py` — 2 bài |

---

## SL-116 · LỆCH THẬT · Bộ rút tên thanh ghi không thấy dạng viết CHUNG của datasheet

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §4.1 (thu nhận, chưng cất); FR-KG-01 |
| **Cách tìm** | Nạp datasheet chính chủ để lấp chỗ thiếu Bài 1. Trích đúng bốn trang mục *Register Description*, kết quả: `DS40002061B, USART, TXB, RXB, FIFO, SBI, CBI, SBIC, SBIS, SREG, SPI, MSPIM` — **không một tên thanh ghi thật nào** |
| **Lỗi** | Biểu thức nhận dạng là `\b[A-Z][A-Z0-9_]{2,}\b` — chỉ chữ hoa. Nhưng datasheet của các họ chip có ngoại vi **nhiều thực thể** không viết tên kèm số hiệu cụ thể; nó viết dạng chung, chèn một chữ thường làm chỗ giữ. Mọi tên như vậy bị loại vì có một chữ thường |
| **Hỏng đúng chỗ dùng nhiều nhất** | Cổng nối tiếp, bus hai dây, bộ đếm thời gian — tất cả đều là loại nhiều thực thể. Với chúng, bộ rút thấy **rỗng** và nhặt bù bằng từ viết tắt của văn xuôi kỹ thuật |
| **Hệ quả không dừng ở một dòng in xấu** | Trường `registers` của chunk là thứ Knowledge Graph dùng dựng cạnh `thanh ghi –documented_in→ chunk`. Chunk mang danh sách sai thì **không bao giờ được truy xuất cho module cần nó** — đường nạp tri thức sinh ra một trích đoạn mà chính phép truy xuất nó phục vụ không tìm thấy |
| **Mã số hiệu tài liệu chiếm chỗ** | `DS40002061B` trông y hệt một tên thanh ghi và nằm ở **chân trang của mọi trang**, nên nó gần như luôn đứng đầu và đẩy tên thật ra khỏi phần bị cắt còn 12 mục |
| **Đã sửa** | Nhận dạng có chữ thường xen giữa (chữ thường chỉ được đứng lẻ — hai chữ thường liền nhau là một từ tiếng Anh); loại mã số hiệu bản in; **xếp tên có dấu hiệu riêng của thanh ghi lên trước** vì danh sách bị cắt nên thứ tự quyết định cái gì sống sót |
| **Đo được** | Cùng bốn trang ấy, sau bản sửa: `UDRn, UDREn, UCSRnA, RXCn, RXCIEn, TXCn, TXCIEn, UDRIEn, FEn, DORn, UPEn, MPCMn` |
| **Thêm: cảnh báo tên dạng chung** | Chunk khai `UDRn` còn hồ sơ khai `UDR0` thì cạnh đồ thị không nối được — chunk vẫn qua G2, vẫn trông tốt, và vô hình. Chuẩn hóa là việc của kỹ sư (chỉ dự án mới biết ngoại vi là thực thể số mấy, engine không được đoán thay — TC-38), nhưng **không nói ra thì kỹ sư không biết có việc phải làm** |
| **Bài canh** | `tests/test_tc91_rut_ten_thanh_ghi.py` — 9 bài, dùng tên BỊA theo đúng lối datasheet viết |

---

## SL-117 · LỆCH THẬT · Trích đoạn tài liệu KHÔNG có đường nào vào kho tri thức

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-KB-02; EAA-AIS-05 §4.1; ADR-04 (G2) |
| **Cách tìm** | Bài 1, cách A. `eaa datasheet add` tạo chunk và nói: *"Chunk đang ở trạng thái 'proposed' nên CHƯA truy xuất được vào prompt nào […] rồi duyệt: `eaa gate show G2` / `eaa gate approve G2`"*. Làm đúng thế. Gate ghi nhận quyết định. **Chunk vẫn `proposed`** |
| **Lỗi** | `DatasheetStore` là kho **CHỈ ĐỌC** — không phương thức nào ghi, và không dòng mã nào trong engine đổi trạng thái một chunk từ `proposed` sang `approved`. Đường ấy **chưa từng tồn tại** |
| **Vì sao không ai phát hiện suốt bốn sprint** | Mọi chunk đang `approved` trong dự án mẫu đều được **VIẾT TAY** sẵn với `status: approved`. Không cái nào đi qua đường nạp. Bài kiểm cũng dựng chunk bằng tay, nên chúng canh đúng phần kho biết đọc |
| **Bất biến đúng theo nghĩa tệ nhất** | *"Tri thức chỉ vào kho qua G2"* đúng — vì **không gì vào được cả**. Một bất biến được giữ bằng cách làm cho hành động bị cấm trở nên bất khả thi cùng lúc với hành động được phép |
| **Cùng họ ngõ cụt với SL-110 và SL-113** | Lệnh nói ra một lối đi tiếp, và lối ấy không dẫn tới đâu. Lần này nó nằm ở **đường nạp tri thức**, tức là ở giữa sản phẩm |
| **Đã sửa** | `DatasheetStore.approve()` — đổi TRẠNG THÁI, tuyệt đối không đụng thân chunk (nội dung đổi phải qua supersede, không thì *"duyệt cái này rồi dùng cái khác"* là đường vòng hợp lệ). Ghi `approved_by`/`approved_at` vào chính tệp, cùng luật với mục công cụ trong manifest của pack. Ghi nguyên tử như Project State (TC-03). `_gate_approve` gọi nó cho mọi chunk trong hồ sơ G2 |
| **Ghép lại tệp bằng cách THAY ĐOẠN, không dựng lại từ mảnh** | Dựng lại làm mất khoảng trắng ở ranh giới, và với kho tri thức thì *"gần như nguyên vẹn"* không phải là nguyên vẹn: bản duyệt phải byte-đối-byte giống bản người vừa đọc, trừ đúng dòng trạng thái |
| **Còn treo — G2 duyệt TẤT CẢ hay không gì cả** | Hồ sơ G2 gom mọi chunk đang chờ, nên một lần duyệt nâng hạng cả lô. Đo được ngay: duyệt `ds-043` kéo theo `ds-032` — chunk mà hồ sơ phần cứng ghi rõ là **cố ý giữ ở `proposed` vì chưa đối chiếu xong hệ số nhạy**. Đã trả `ds-032` về `proposed` bằng tay. Cần một cách duyệt từng chunk |
| **Bài canh** | `tests/test_tc92_duyet_chunk_vao_kho.py` — 7 bài, trong đó một bài quét mã nguồn đòi kho tri thức phải CÓ đường ghi |

---

## SL-118 · LỆCH THẬT (×2) · Khuôn firmware chẩn đoán chưa từng dịch được lần nào

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7 (chẩn đoán phần cứng); TC-44 |
| **Cách tìm** | `eaa diagnose build DS-04` — kịch bản *"UART / telemetry"*, đúng việc Bài 1 cần. Kết quả: bốn thông báo lỗi cho cùng một nguyên nhân |
| **Lỗi 1** | Khuôn `packs/avr/templates/diagnostic.c.tmpl` gọi `<util/setbaud.h>` mà **không khai `BAUD`** trước. Tệp tiêu đề ấy TÍNH hệ số chia từ `BAUD` và `F_CPU`; thiếu một cái thì nó bắn `#error`, rồi chia cho không ở `#if`, rồi cảnh báo tràn |
| **Chỗ giữ đã có sẵn mà khuôn không dùng** | Bộ sinh `firmware.py` đã điền `{baud}` vào bảng thay thế từ lâu. Khuôn chưa bao giờ tham chiếu nó. Lại một chỗ **mã đúng nằm chết** — thứ tư trong phiên |
| **Vì sao im lặng suốt bốn sprint** | Không bài kiểm nào DỰNG THẬT một firmware chẩn đoán bằng `avr-gcc`; chúng kiểm phần sinh chuỗi và phần ghép, không kiểm phần dịch. Khuôn chỉ là văn bản cho tới lúc có người gọi trình biên dịch thật |
| **Lỗi 2 — và đây là một sự thật vật lý bị chặn nhầm thành lỗi mã** | Sau khi khai `BAUD`, khuôn vẫn trượt vì `#warning "Baud rate achieved is higher than allowed"` gặp `-Werror=cpp`. Với thạch anh 16 MHz và 115200 baud, hệ số chia nguyên gần nhất cho sai số **+2,1%**, vượt ngưỡng mặc định 2% của avr-libc |
| **Nới ngưỡng là một KHẲNG ĐỊNH, nên nó phải nằm cạnh lý do** | Khung 8N1 chịu được tổng sai số hai đầu khoảng ±5%, nên 2,1% một đầu là an toàn — **với điều kiện đầu kia cũng chuẩn**. Đặt `BAUD_TOL` trong một cờ dịch không ai đọc thì nó thành một con số vô chủ; đặt cạnh phép tính và lý do thì nó là một quyết định kỹ thuật truy được |
| **Con số ấy mới là TÍNH RA** | 2,1% suy từ tần số danh định của thạch anh. Nó chỉ thành ĐÃ KIỂM sau khi đo trên bo thật — đúng chỗ mà nghiệm thu vật lý G4 tồn tại để làm |
| **Đã sửa** | Khuôn khai `BAUD` từ chỗ giữ `{baud}`, và `BAUD_TOL` kèm toàn bộ lập luận trên |

---

## SL-119 · LỆCH THẬT (×2) · Cổng nạp firmware cũng là ngõ cụt, và đường dẫn ảnh tính sai chỗ đứng

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-DIA-02; EAA-AIS-05 §7.3; SL-110 |
| **Cách tìm** | Nạp thật xuống bo. `eaa flash` qua hết bốn phép kiểm trước — ảnh có, kho sạch, ảnh mới hơn nguồn, cổng tự nhận đúng — rồi dừng ở *"chưa có xác nhận của người"* |
| **Lỗi 1 — cùng ngõ cụt SL-110, ở chặng CUỐI** | Không cờ, không lệnh, không sổ. Một phiên làm việc qua người trung gian **không bao giờ** nạp được firmware. Đây là lần thứ tư cùng một hình dạng xuất hiện ở một chỗ khác |
| **Đã sửa** | `FlashApprovals` + `eaa flash approve --image <ảnh> --actor <tên>`. Neo vào **băm NỘI DUNG ảnh**, không vào đường dẫn: đường dẫn ghi đè được, nên neo vào nó thì *"duyệt ảnh này rồi nạp ảnh khác"* chỉ cần một lần ráp lại xen vào giữa — và bản ghi vẫn nói có người duyệt |
| **Lỗi 2 — do chính bản sửa trên gây ra, và bài canh cũ bắt được** | `flash` CẦN đối số tự do, nên mục mới nuốt luôn `flash approve`. Xét cấm-trước thì lại hỏng `gate show` (được phép) vì `gate` (cấm) chặn mất. Luật đúng cho cả hai chiều: **khớp dài nhất thắng**, kể cả khi bên thắng là bên cấm |
| **Lỗi 3 — đường dẫn ảnh tính theo sai chỗ đứng** | `_tuong_doi` chỉ xử lý vế tuyệt đối; đường dẫn TƯƠNG ĐỐI được trả nguyên si, rồi công cụ nạp diễn giải nó theo thư mục làm việc CỦA NÓ. Kết quả: `file diag_DS-04.hex is not readable` cho một tệp đang nằm ngay đó — đường dẫn in ra trong nhật ký thì đúng, chỉ có chỗ đứng để đọc nó là sai |
| **Bài canh** | `tests/test_tc93_duyet_nap_firmware.py` — 13 bài |

---

## SL-120 · CÒN NGỜ, CHƯA KẾT LUẬN · "Đọc ngược khớp ảnh" có thể đang khẳng định sai

> Mục này ghi lại một **mâu thuẫn chưa giải**, không phải một lỗi đã xác định.
> Ghi ra vì nó chạm bất biến trung tâm, và vì bỏ qua một mâu thuẫn chỉ vì chưa
> biết bên nào sai là cách nhanh nhất để nó biến mất khỏi trí nhớ.

| | |
|---|---|
| **Hiện tượng** | `eaa flash` báo *"Kiểm sau khi nạp: ĐÃ KIỂM — đọc ngược khớp ảnh"*. Đọc ngược bằng tay (`avrdude -U flash:r:…`) rồi so từng byte: **895 / 974 byte trong vùng vừa nạp KHÁC nhau**, và còn 16.345 byte khác `0xFF` ở vùng ngoài, tới `0x7f9d` |
| **Manh mối độc lập** | Byte đọc được trên dây (`7E 02 0C EF`, `7E 03 06 0A EF`) trùng đúng khung lệnh module MP3 trong mã tham chiếu của bộ kit (`Serial.write(0x7E); … Serial.write(0xEF);`). Và nội dung ấy **không đổi** khi ta dựng lại firmware ở tốc độ khác — tức thứ đang chạy trên chip không phải thứ ta nạp |
| **Vì sao chưa kết luận** | Bộ đọc Intel HEX dùng cho phép so tay là mã viết vội trong phiên, chưa được kiểm. Nghi ngờ nó trước, không nghi `eaa` trước |
| **Nếu đúng là `eaa` sai thì đây là lỗi nặng nhất kho** | Nó khẳng định *"thứ trên bàn là thứ đã được duyệt"* trong khi không phải — hỏng đúng bất biến trung tâm, ở chặng cuối, và hỏng theo hướng **nói dối một cách thuyết phục** |
| **Ba bước kiểm đã vạch, chưa chạy** | (1) đọc năng lực `verify` của pack xem nó so cái gì với cái gì; (2) kiểm lại bộ đọc HEX viết tay; (3) nạp một ảnh khác hẳn rồi đọc ngược — nội dung chip không đổi theo thì lệnh nạp không có tác dụng thật |

---

## SL-121 · LỆCH THẬT · Biết rồi mà không nói, rồi sai người đi làm việc chân tay

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7.3–7.4 (giao hai kênh); TC-27 |
| **Cách tìm** | Bài 2 phiên kiểm bo thật. `eaa diagnose run DS-02` thu bốn khung, trong đó `{"who_am_i": "0x72"}`. Kịch bản khai đích danh `who_am_i op: equals expected: "0x68"` — phép kiểm ấy **đã trượt ngay lúc dữ liệu về**. Lệnh không nói một chữ, in thẳng hai câu hỏi cho người |
| **Nguyên nhân** | `if kich_ban.human and not tra_loi:` in câu hỏi rồi `return` — kênh máy **chưa từng được chấm** |
| **Hai chuyện khác nhau** | *Chưa kết luận khi thiếu nửa dữ liệu* — ĐÚNG, giữ nguyên; chẩn đoán là phép giao. *Giấu phần đã biết* — SAI |
| **Cái giá** | Nó sai người đi nghiêng bo, quan sát, gõ trả lời, để rồi mới biết mã nhận dạng chưa bao giờ khớp. Việc chân tay ấy **không đổi được kết cục** |
| **Và phần bị giấu là phần quyết định nhất** | Mã nhận dạng sai nghĩa là có thể **đây không phải con cảm biến dự án đang khai**. Mọi câu hỏi về dấu và trục đều đứng sau câu hỏi ấy |
| **Đã sửa** | Chấm kênh máy TRƯỚC, in kết quả, rồi mới hỏi. Vẫn từ chối kết luận. Thêm một dòng nói thẳng: quan sát của bạn vẫn cần để chốt vùng lỗi, nhưng nó sẽ không lật được kết cục — **biết trước thì bạn chọn được có bỏ công ra bây giờ hay không** |
| **Hai lỗi tự tôi gây khi sửa** | (1) Một chuỗi xuống dòng thật lọt vào giữa literal, làm `eaa/cli.py` không import nổi. (2) Biến tên `telemetry` giữ CHUỖI khung thô chứ không phải dict, nên `evaluate_machine` lấy chỉ số trên chuỗi và sập |
| **Và bài kiểm của tôi suýt che mất lỗi (1)** | Fixture dùng `pytest.skip` khi `eaa init` hỏng. Lỗi cú pháp biến thành **bốn dòng "skipped"**, bảng test xanh, CLI không chạy được. Đã đổi thành `assert` kèm nguyên văn đầu ra. **Một điều kiện bỏ qua rộng hơn cần thiết là một chỗ cho lỗi thật trốn vào** |
| **Bài canh** | `tests/test_tc95_kenh_may_truoc_khi_hoi_nguoi.py` — 4 bài |

---

## SL-122 · BỔ SUNG · Phép so `one_of`, và vì sao nó không phải `equals` nới ra

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §7.2 (kênh máy); hồ sơ phần cứng §components |
| **Cách tìm** | Bài 2 phiên kiểm bo thật: cảm biến trả mã nhận dạng `0x72`, hồ sơ khai `0x68`. Đo trên chính bo ấy cho thấy nó **tương thích thanh ghi** ở mọi thanh ghi dự án dùng |
| **Bằng chứng tương thích, đo được** | Trả lời ở địa chỉ bus `0x68`; đọc được `WHO_AM_I`; ghi `PWR_MGMT_1` đánh thức được (không thì mọi số đọc về là 0); đọc chùm 14 byte từ `ACCEL_XOUT_H` ra dữ liệu hợp lý; và **hệ số thang đo mặc định quy ra 0,36 mg / 0,03 °/s — đúng dải vật lý**. Dòng cuối là bằng chứng mạnh nhất: dải đo mặc định khác thì hai con số ấy đã lệch hẳn một hệ số |
| **Vì sao không sửa `expected` thành `0x72`** | Như thế là **đánh mất `0x68`**. Cắm con chip đúng thiết kế vào thì phép kiểm lại đỏ, và người ta sẽ sửa tiếp — mỗi lần một giá trị, mỗi lần mất giá trị cũ. Sau vài vòng, phép kiểm nhận dạng chỉ còn nhớ con chip cắm gần nhất |
| **Vì sao không bỏ hẳn phép kiểm** | Nó là câu hỏi RẺ NHẤT trong cả kịch bản — *"có đúng con chip ta nghĩ không"*. Sai ở đây thì mọi thanh ghi sau đều đọc nhầm bảng |
| **Đã thêm** | `one_of`: tập chấp nhận được. **Mở rộng có chủ ý** — thêm một mã là một quyết định tại G1, và con chip thứ ba ngoài tập vẫn bị bắt |
| **Tập RỖNG là lỗi nói ra, không phải kết cục im lặng** | Trả đạt thì mọi giá trị lọt; trả trượt thì không ai hiểu vì sao. Nói ra là đường duy nhất còn lại |
| **Bằng chứng phải nằm CẠNH con số** | Lý do nới nằm trong `hardware_profile.yaml`, ngay dưới `whoami_expected`, không nằm trong commit message — bằng chứng trong commit message là bằng chứng không ai đọc lại. Có bài kiểm canh điều đó |
| **Bài canh** | `tests/test_tc96_one_of.py` — 9 bài |

---

## SL-123 · LỆCH THẬT (×2) · Nhiễu nền: đơn vị thô hơn đại lượng, và phép kiểm chỉ có trần

| | |
|---|---|
| **Cách tìm** | DS-02 báo `accel_noise_mg = 0`. Tôi nghi cảm biến không đọc được; người dùng phản biện rằng bo đang nằm yên nên thế là bình thường |
| **Cả hai đều có phần đúng** | Người dùng đúng về **điều kiện đo** — nằm yên chính là điều kiện đo nhiễu nền. Tôi đúng về **độ phân giải**: `nhieu_a * 1000 / 16384` cho ra mg nguyên, mà nhiễu lành mạnh là 4–8 LSB tức 0,2–0,5 mg, nên nó làm tròn thành **0**. Đường con quay ngay dưới, cùng đoạn mã, nhân 100 để giữ hai chữ số thập phân |
| **Giải bằng số, không bằng lời** | Nâng độ phân giải rồi đo lại: **0,36 mg**, lần sau **0,24**, lần sau nữa **0,3** — đúng dải dự đoán, và đổi giữa các lần như nhiễu thật phải thế. Hai giả thuyết trái nhau mà cùng nghe hợp lý thì **đi đo rẻ hơn đi thuyết phục**: ba phút |
| **Lỗi 2 — trần một mình không bắt được cảm biến chết** | Phép kiểm nhiễu chỉ khai `max`. Chip còn ngủ trả về toàn số 0, và **0 nằm dưới mọi trần**. Chính chú thích đầu `DS-02.c` đã cảnh báo *"một loạt số 0 trông y hệt một cảm biến đứng rất yên"* — mà phép kiểm vẫn để hở |
| **Đã sửa** | Cả hai chỉ số dùng `in_range` có **sàn**, lấy từ số đo thật chia đôi để chừa biên. MEMS đang sống không bao giờ cho nhiễu bằng 0 |
| **Bài học chung** | Một phép đo mà đơn vị của nó thô hơn đại lượng cần đo thì nó không đo gì cả — và con số nó trả về vẫn trông như một con số |

---

## SL-124 · LỆCH THẬT · Cánh cửa mới không mang theo thứ cửa cũ mang — và lần này là checklist AN TOÀN

> Chỗ hở này do **chính bản sửa SL-119 của tôi tạo ra**, và nó là chỗ hở nguy
> hiểm nhất cả phiên: nó cho phép nạp một ảnh làm **bánh xe quay** mà người
> duyệt không hề biết.

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-DIA-02; EAA-AIS-05 §7.1 (kịch bản có chuyển động); SL-119 |
| **Cách tìm** | Bài 3 phiên kiểm bo thật. Trước khi nạp DS-03 (`motion: true`), kiểm xem lệnh nạp có cưỡng chế checklist an toàn không |
| **Trước SL-119** | Đường nạp duy nhất là hỏi trên terminal, và bản tóm tắt lúc hỏi kèm thẻ đi kèm ảnh: *"⚠ ẢNH NÀY LÀM THIẾT BỊ CHUYỂN ĐỘNG"* + checklist. Chú thích của chính hàm đọc thẻ nói rõ vì sao: *"một ảnh chẩn đoán làm robot chuyển động trông y hệt một ảnh đo tĩnh… đưa checklist ra đúng lúc người sắp bấm đồng ý, chứ không phải lúc dựng ảnh — giữa hai thời điểm ấy có thể là vài ngày"* |
| **Lỗi** | Sổ duyệt ngoài luồng của SL-119 **đi vòng qua đúng chỗ ấy**. `eaa flash approve --image <ảnh>` in ra tên tệp và băm, hết. Đo được trên ảnh DS-03 thật: ba dòng, không một chữ về chuyển động |
| **Bất biến bị vi phạm** | **Thông tin đi kèm một quyết định không được biến mất khi đường đi tới quyết định ấy đổi.** Mở một cánh cửa mới thì cửa ấy phải mang theo mọi thứ cửa cũ mang |
| **Đã sửa — đường DUYỆT** | `flash approve` đọc thẻ, in cảnh báo và checklist, và **từ chối** nếu chưa có `--confirm-safety` cho từng mục, nguyên văn — cùng cơ chế `eaa diagnose run` đã dùng. Quyết định ghi vào sổ mang theo `motion` và `safety_confirmed` |
| **Đã sửa — đường NẠP, và đây mới là phần bắt buộc** | Sổ là **append-only**, nên mọi bản ghi lỏng lẻo ghi trước khi luật này tồn tại vẫn nằm đó mãi và vẫn hợp lệ về băm. Sửa ở đường duyệt là chưa đủ: `Flasher.da_duoc_duyet()` nay nhận `required_safety` và từ chối quyết định không phủ đủ |
| **Tôi tự chứng minh chỗ ấy cần thiết** | Lúc thử xem `flash approve` có cảnh báo không, tôi đã ghi một quyết định THẬT cho ảnh DS-03 với tên người vô nghĩa và không xác nhận an toàn nào. Sổ append-only nên nó nằm đó; sau bản sửa, nó không còn mở được đường nạp |
| **Cổng mới không làm phiền đường không nguy hiểm** | Ảnh đo tĩnh và ảnh không có thẻ vẫn duyệt như cũ. Một cổng đòi thừa thì sớm muộn bị bấm cho xong, và lúc nó đòi đúng thì cũng bị bấm cho xong |
| **Bài canh** | `tests/test_tc97_duyet_anh_chuyen_dong.py` — 9 bài |

---

## SL-125 · LỆCH THẬT · Hồ sơ phần cứng mô tả một THIẾT KẾ, không phải cái bo trên bàn

| | |
|---|---|
| **Cách tìm** | Bài 3. DS-03 báo đủ 200 xung ở 1 kHz trên cả hai động cơ; người dùng nhìn thấy **không bánh nào nhúc nhích**. Phép giao hai kênh kết luận *"vùng lỗi: điện — KHÔNG mở vòng sửa mã"* |
| **Nguyên nhân thật** | Bản đồ chân sai **cả cổng**. Hồ sơ khai PB1/PB2/PB3/PB4 (D9–D12); bo thật dùng PD5/PD4/PD7/PD6 (D5/D4/D7/D6). Trên bo này **D11 là chân dữ liệu dải LED WS2812**, nên bản đo đầu tiên phát xung vào dải LED trong khi hai chân STEP thật nằm im |
| **Hai nguồn độc lập, cả hai nằm sẵn trong `sources/`** | Sơ đồ nguyên lý của kit (các nét `STEP1/DIR1/STEP2/DIR2`, và **không có nét ENABLE** nào về vi điều khiển) và mã tham chiếu V3 (`#define STEP1 5 / DIR1 4 / STEP2 7 / DIR2 6`) |
| **`enable` bỏ hẳn, không để trống** | A4988 bật cứng trên bo. Khai một chân enable không tồn tại là mời mã đi ghi vào chân của khối khác — bản trước ghi mức thấp vào PB0 |
| **Vì sao nằm im bốn sprint** | Chưa lần nào có **xung thật đi ra chân thật**. Mọi cổng kiểm chứng đều xanh: mã dịch được, vừa bộ nhớ, sạch phân tích tĩnh — vì không cổng nào biết chân nào nối đi đâu |
| **Vùng lỗi hệ chấm là "điện", bệnh thật là "hồ sơ sai"** | Chỉ dẫn *"kiểm lại dây theo pin map"* dẫn tới đúng chỗ, nhưng bộ luật chỉ có các vùng kiểu *điện / cơ khí / mã* — **không có vùng "hồ sơ phần cứng sai"**, mà đó lại là vùng dễ xảy ra nhất khi hồ sơ viết từ thiết kế còn bo thì mua sẵn |
| **Kết quả sau khi sửa** | Bánh quay. Đổi hồ sơ ⇒ duyệt lại G1 |
| **Còn là giả định** | Động cơ 1 ↔ trái, 2 ↔ phải. Sơ đồ và mã tham chiếu đều chỉ đánh số 1/2 |

---

## SL-126 · LỆCH THẬT · Câu hỏi cho NGƯỜI mâu thuẫn với firmware, và biến robot tốt thành "lỗi cơ khí"

| | |
|---|---|
| **Cách tìm** | Ngay sau khi động cơ quay được lần đầu, đọc lại ba câu hỏi mà DS-03 sắp hỏi người |
| **Lỗi** | Câu hỏi: *"Có quay **đủ một vòng** không (không trượt bước, không kêu lạ)?"* — trong khi firmware của chính kịch bản ấy cố ý chỉ phát **200 xung = 1/16 vòng** (~22°), và chú thích nói rõ vì sao: *"một lệnh quay nhiều vòng vẫn đủ để một sợi dây bị cuốn vào bánh"* |
| **Hậu quả** | Người quan sát TRUNG THỰC buộc phải trả lời "không". Bộ luật có đúng một dòng cho tổ hợp `{truc_quay: có, dung_chieu: có, du_mot_vong: không}` → **vùng lỗi: cơ khí**. Một robot chạy hoàn toàn đúng bị chấm là hỏng cơ, và người ta đi tháo bánh ra kiểm |
| **Vì sao nguy hơn một câu chữ vụng** | Kênh người được dựng lên để làm ĐỐI CHỨNG cho kênh máy — nó tồn tại vì số liệu một mình có thể "đẹp" mà sai. Một câu hỏi sai ở đây không chỉ mất tác dụng đối chứng: nó **chủ động bơm dữ liệu sai** vào phép giao, và phép giao không có cách nào biết |
| **Đã sửa** | Đổi câu hỏi cho khớp thứ firmware thật sự làm, và **đổi luôn tên khóa** (`du_mot_vong` → `quay_tron_deu`): cái tên cũ tự nó đã mang giả định sai |
| **Khai `steps_per_rev` vào hồ sơ** | Phép quy đổi xung → góc vốn dựa vào con số 200 nằm trong đầu người viết. Một hằng số không khai thì không đối chiếu được — và đó chính là lý do câu hỏi lệch khỏi firmware mà bốn sprint không ai thấy |
| **Bài canh** | `tests/test_tc98_cau_hoi_khop_firmware.py` — 4 bài, canh quan hệ giữa hai thứ nằm ở hai tệp khác nhau: số xung trong firmware và câu chữ trong kịch bản. Thêm hai bài canh bộ luật: khóa nào luật dùng cũng phải có câu hỏi, và câu hỏi nào cũng phải có ít nhất một luật dùng tới |
| **Ba bài canh cũ phải sửa theo** | `test_tc18_graph.py` dựa vào việc hai driver **tình cờ** dùng chung chân enable của dự án mẫu; bỏ enable là bài kiểm mất thứ nó đang canh dù engine không đổi một dòng. Đã dựng hồ sơ riêng ngay trong bài — một bài canh engine mà phụ thuộc dữ liệu dự án thì nó đo hai thứ cùng lúc và không nói được thứ nào vừa đổi |

---

## SL-127 · BỔ SUNG · Kịch bản DS-07, và hai sự thật phần cứng chốt bằng mắt

| | |
|---|---|
| **Cách tìm** | Người dùng đề nghị: *"cho 02 động cơ cùng chạy tiến liên tục thì sẽ dễ phát hiện hơn"* — sau khi nhìn tám lượt giật 22° của DS-03 mà vẫn khó chấm "quay trơn đều" |
| **Đúng, và DS-03 không với tới được** | Một cú giật 1/16 vòng kết thúc trước khi tai kịp phân biệt tiếng rít với tiếng khởi động. Và quay TỪNG bánh một thì không bao giờ thấy được hai bánh có cùng chiều VẬT LÝ hay không |
| **Hai sự thật phần cứng chốt bằng quan sát** | **(1) Trái/phải đảo.** Hồ sơ gán động cơ 1 (D5/D4) cho bên trái — một giả định, vì sơ đồ và mã tham chiếu chỉ đánh số 1/2. Người dùng thấy bánh PHẢI quay trước. Mã tham chiếu xác nhận: khối `right_motor` thao tác D5/D4. **(2) `dir_forward_level` khác nhau hai bên.** Đo được: cả hai DIR = 0 thì bánh phải LÙI, bánh trái TIẾN — hai động cơ lắp đối xứng gương |
| **Vì sao điều (2) đáng khai vào hồ sơ** | Không khai thì module đầu tiên điều khiển hai bánh sẽ đặt cùng mức cho cả hai, và **robot quay tại chỗ thay vì đi tới**. Mã hoàn toàn đúng với thứ nó được bảo, nên không cổng phần mềm nào bắt được |
| **DS-07 là phép kiểm của chính khai báo ấy** | Nó cho hai bánh chạy cùng lúc, cùng chiều tiến, và hỏi người: *"hai bánh có quay cùng một chiều vật lý không"*. Trả lời "không" → vùng lỗi **`hồ sơ phần cứng`**, một vùng lỗi mà bộ luật trước đây không có (SL-125 đã nêu chỗ thiếu này) |
| **Giới hạn có chủ ý** | 4000 xung ≈ 1,25 vòng, không phải "chạy tới khi ai rút điện". Và checklist an toàn có thêm một mục DS-03 không có: **dây đã buộc gọn** — DS-03 quay 1/16 vòng, kịch bản này quay hơn một vòng, và một vòng là đủ để cuốn một sợi dây vào bánh |
| **Ba bài canh cũ phải sửa, và lý do đáng ghi** | Hai bài so số kịch bản bằng dấu BẰNG (`== 6`, `== [DS-01…DS-06]`), nên thêm một kịch bản là đỏ. Nhưng thêm kịch bản là việc bình thường của một dự án; thứ đáng canh là **sáu kịch bản của thiết kế phải CÓ MẶT**, không phải "chỉ được có sáu". Đổi sang phép so bao hàm |
| **Lỗi phép đo của chính tôi, tự lộ trong một lượt** | Chạy tám lượt với cửa sổ thu 2,2 giây → cả tám báo `KHÁC THƯỜNG`, thiếu khung động cơ phải. Bo không sai: bootloader cũ chờ 1–2 giây trước khi nhường quyền, và tôi cắt mất khung bằng chính phép đo của mình. Báo cáo con số ấy như dữ kiện thì người dùng đã đi tìm lỗi ở động cơ phải. Cùng loại với SL-120, khác mỗi chỗ nó lộ ra sau một phút thay vì sau hai ngày |

---

## SL-128 · LỆCH THẬT · Chốt một đại lượng mức HỆ THỐNG bằng một phép đo mức LINH KIỆN

> Chỗ sai này nằm ở **suy luận của tôi**, không ở quan sát của người dùng và
> không ở mã. Ghi lại vì nó là dạng sai khó thấy nhất: dữ liệu đúng, người
> trung thực, kết luận vẫn sai.

| | |
|---|---|
| **Cách tìm** | DS-07 cho hai bánh chạy cùng lúc với `dir_left=0, dir_right=1`. Người quan sát: *"Hai bánh quay đều. Hướng di chuyển về phía sau"* |
| **Điều tôi đã làm** | DS-03 quay TỪNG bánh một. Người dùng nói *"trái tiến, phải lùi"*, và tôi đọc câu ấy thành `dir_forward_level` trái = 0, phải = 1, rồi ghi vào hồ sơ kèm chữ "đo được" |
| **Vì sao sai** | Nhìn MỘT bánh quay thì không suy ra được **robot** sẽ đi về đâu. Chiều tiến của cả xe chỉ có nghĩa khi hai bánh cùng chạy, và còn phụ thuộc bánh nằm bên nào của thân xe. Quan hệ giữa hai mức (phải KHÁC nhau) thì DS-03 chốt được; chiều tuyệt đối thì không |
| **Quy tắc rút ra, đã ghi vào hồ sơ** | **Đại lượng nào chỉ có nghĩa ở mức HỆ THỐNG thì đừng chốt nó bằng một phép đo ở mức LINH KIỆN**, dù phép đo ấy sạch và người quan sát trung thực |
| **Đã sửa** | Đảo cả hai giá trị; DS-07 xác nhận robot đi tới |
| **Phần canh được và phần không** | Bài kiểm đòi hai bánh khai mức DIR **khác nhau** — đó là bất biến của việc lắp đối xứng gương và kiểm được bằng dữ liệu. Chiều tuyệt đối thì **không bài kiểm nào canh nổi**: nó cần mắt người nhìn robot chạy. Ghi rõ ranh giới ấy trong chính bài kiểm |

---

## SL-129 · LỆCH THẬT · Cửa sổ thu telemetry là hằng số, và nó đổ lỗi cho bo khi hết giờ

| | |
|---|---|
| **Cách tìm** | `eaa diagnose run DS-07` in ra bốn dòng `✗ telemetry không có trường …` cho một firmware vừa chạy hoàn toàn đúng — người dùng đứng cạnh và nhìn thấy bánh quay đủ 4 giây |
| **Lỗi** | Cửa sổ thu là hằng số **5 giây**. DS-07 quay 4 giây, bootloader cũ chờ 1–2 giây trước khi nhường quyền — nên lệnh bỏ cuộc **trước khi bo kịp phát khung** |
| **Hỏng theo hướng đổ lỗi nhầm** | *"Telemetry không có trường `pulses_emitted`"* đọc thành *"firmware không phát trường ấy"*. Sự thật là **người quan sát bỏ đi sớm**. Hai câu dẫn tới hai việc trái ngược: một bên đi sửa firmware, một bên chỉ cần chờ lâu hơn |
| **Đã sửa** | `Scenario.collect_seconds`. Thứ tự ưu tiên: cờ người gõ → khai báo của kịch bản → mặc định. **Kịch bản biết nó chạy bao lâu; lệnh thì không** |
| **Bài kiểm bắt luôn hai kịch bản khác** | DS-03 và DS-05 cũng chưa khai. DS-03 *tình cờ* đủ với mặc định — nhưng "tình cờ đủ" không phải một khai báo, và kịch bản viết sau sẽ không may như thế. Có bài canh đòi **mọi** kịch bản chuyển động phải khai |
| **Tôi vừa tự mắc đúng lỗi ấy một phút trước** | Chạy tám lượt DS-03 với cửa sổ thu 2,2 giây, cả tám báo `KHÁC THƯỜNG`. Khác biệt duy nhất: lỗi của tôi lộ ra sau một phút, còn lỗi trong sản phẩm thì nằm im tới khi có kịch bản chạy đủ lâu để chạm trần |
| **Bài canh** | `tests/test_tc99_cua_so_thu.py` — 5 bài, trong đó một bài **tính** thời gian chạy từ chính firmware (`DIAG_PULSES × chu kỳ`) rồi đòi cửa sổ thu rộng hơn thế cộng biên bootloader |

---

## SL-130 · LỆCH THẬT · Bộ phân rã không biết Platform Pack cho sẵn gì, nên nó đề xuất dựng lại nền tảng

| | |
|---|---|
| **Tài liệu** | EAA-SRS-01 FR-PLT-01; EAA-SAD-02 ADR-09 (ranh giới engine–pack); N-040..N-043 |
| **Cách tìm** | Bài "robot tự cân bằng tại chỗ", lần đầu chạy `eaa plan propose`. Bản phân rã tám module rất hợp lý — trừ hai module dựng lại chính nền tảng |
| **Hai va chạm** | `[system_timer]` chiếm `timer0` và cung cấp `timer_init` — nhưng khuôn của pack đã có ngắt `TIMER0_COMPA_vect` đếm mili giây. `[main_coordinator]` cung cấp `main` — khuôn đã sinh `int main(void)`. Cả hai cho **trùng định nghĩa lúc LIÊN KẾT** |
| **Vì sao mô hình đề xuất như thế** | Vì **không ai nói cho nó**. Prompt phân rã chỉ có mục tiêu, hồ sơ phần cứng, ràng buộc — không một chữ nào về Platform Pack, không nói pack sinh `main`, không nói pack đã chiếm Timer0, không nói hợp đồng của module là `init`/`step` |
| **Và phép kiểm tài nguyên không bắt được** | `_kiem_tai_nguyen` đối chiếu với hồ sơ phần cứng, mà `timer0` **CÓ** trong hồ sơ — nó chỉ đã bị nền tảng giữ trước. Một tài nguyên bị chiếm trông y hệt một tài nguyên rảnh |
| **Cái giá** | Hai va chạm chỉ lộ ra ở bước liên kết — tức sau khi cả hai module đã đi qua sinh mã, bốn cổng kiểm chứng, và G3. Chi phí của một chỗ thiếu thông tin trong prompt được trả bằng **toàn bộ vòng đời của hai module** |
| **Đã sửa — pack tự khai** | `firmware.reserves` (ngoại vi khuôn chiếm riêng), `firmware.provides` (ký hiệu khuôn sinh ra), `firmware.contract` (hợp đồng `init`/`step`, và ba điều module KHÔNG được làm) |
| **Đã sửa — bộ phân rã được biết và bị chặn** | `_boi_canh_nen_tang()` đưa ba thứ ấy vào prompt; `_kiem_trung_nen_tang()` cảnh báo module giẫm lên phần nền tảng giữ. Không có pack thì cả hai trả rỗng — dự án chưa cài pack vẫn phân rã được |
| **Khai báo phải KHỚP khuôn thật** | Có bài kiểm đọc thẳng `main.c.tmpl`: khuôn có `int main` thì pack phải khai `provides: [main]`; khuôn có `ISR(TIMER0_…)` thì pack phải khai `reserves: [timer0]`. Khai một đằng khuôn làm một nẻo còn tệ hơn không khai |
| **Đo được sau khi sửa** | Cùng một mục tiêu: **8 module → 6**, hai module dựng lại nền tảng biến mất, và tải CPU ước lượng **60% → 34%** — đúng phần công thừa |
| **Bài canh** | `tests/test_tc100_phan_ra_biet_nen_tang.py` — 8 bài |

---

## SL-131 · LỆCH THẬT (×2) · Bối cảnh phân rã thiếu PHONG CÁCH và thiếu THỨ ĐÃ CÓ

| | |
|---|---|
| **Cách tìm** | Soi bản phân rã bài robot cân bằng TRƯỚC khi nhận — nhận một bản phân rã là một quyết định kiến trúc, nên nó phải được đọc như một bản vẽ |
| **Lỗi 1 — `style` không bao giờ tới nơi** | `constraints.yaml` có `style.arithmetic: integer`. `_boi_canh()` chỉ đưa `limits` và `forbidden`. Nên bộ phân rã giải thích module lọc góc bằng `float_in_isr` — một luật HẸP hơn — và không hề biết có luật cấm số thực ở cả vòng điều khiển |
| **Lần thứ hai cùng một hình dạng** | Đường sinh mã lấy ràng buộc qua bảng K1 (`composer._bang_rang_buoc`); đường phân rã tự dựng một tập con. **Hai chỗ dựng cùng một thứ bằng hai đoạn mã thì sớm muộn chúng lệch nhau** — SL-112 đã là đúng chuyện ấy giữa sinh mã và hội thoại |
| **Lỗi 2 — không biết dự án đã có gì** | Backlog có `drv_uart` với mã đã sinh, đã qua ba cổng. Bản phân rã đề xuất thêm `telemetry` chiếm `usart0` mà không nhắc tới nó. Prompt không có backlog, nên mô hình không thể biết |
| **Đã sửa** | `_boi_canh` dùng CHUNG bảng K1. Thêm `_boi_canh_da_co()` đưa backlog vào prompt, và `_kiem_trung_da_co()` cảnh báo trùng tên hoặc trùng ngoại vi |
| **Bài canh không so từng chữ** | Nó đòi bối cảnh phân rã chứa MỌI mục mà bảng K1 chứa. Thêm một luật vào `constraints.yaml` mà chỉ một trong hai đường thấy nó là đúng cái đã xảy ra một lần |
| **Một vật giả mô phỏng thiếu thì che mất cả một nhánh** | Bài kiểm cũ TC-50 dùng ràng buộc giả **không có trường `style`**. Nó lọt vì bối cảnh phân rã hồi ấy cũng bỏ qua `style` — cái giả và cái thật cùng thiếu một chỗ, nên không ai thấy. Chuyển sang bảng chung là nó lộ ra ngay |
| **Bài canh** | `tests/test_tc101_boi_canh_phan_ra.py` — 7 bài |

---

## SL-132 · LỆCH THẬT · Ảnh firmware CHÍNH không có thẻ an toàn, và nó là ảnh nguy hiểm nhất

| | |
|---|---|
| **Cách tìm** | Chuẩn bị bài robot cân bằng: kiểm xem cổng nạp sẽ nói gì khi duyệt firmware điều khiển |
| **Lỗi** | `_ghi_the_kem` chỉ chạy ở đường CHẨN ĐOÁN. Ảnh do `eaa build` ráp — firmware THẬT của sản phẩm — không có `.meta.json` nào. `eaa flash approve` đọc thẻ không thấy gì và duyệt nó **y như một ảnh đo tĩnh** |
| **Cùng hình dạng SL-124, ở chỗ nguy hơn hẳn** | SL-124 là ảnh chẩn đoán quay bánh 22° **trên giá**. Ảnh ở đây điều khiển một robot **đứng trên hai bánh**: nó không quay một nhịp rồi dừng, nó chạy vô hạn, và khi ngã thì không ai biết trước ngã về phía nào |
| **Checklist cũ KHÔNG dùng lại được** | Mọi kịch bản chẩn đoán mở đầu bằng *"robot đã kê lên giá, bánh KHÔNG chạm đất"*. Cân bằng thì bắt buộc bánh CHẠM đất. **Tình huống an toàn đảo chiều**, nên chép checklist sang là dán một câu vô nghĩa vào đúng chỗ người ta cần đọc kỹ nhất |
| **Đã sửa** | `firmware.yaml` khai mục `safety` (motion + checklist) — đó là tệp mô tả chính ảnh ấy. `eaa build` ghi thẻ; chưa khai thì in cảnh báo rằng cổng nạp sẽ coi đây là ảnh đo tĩnh |
| **Không khai gì thì KHÔNG ghi thẻ rỗng** | Thẻ rỗng đọc thành *"đã xét và thấy không nguy hiểm"*; không có thẻ thì đọc đúng nghĩa *"chưa ai xét"* |
| **Checklist cho robot cân bằng, do dự án khai** | Sàn trống bán kính 1 m · có người đứng cạnh biết tắt nguồn ở đâu · công tắc ngắt trong tầm với chứ không phải rút giắc · đặt trên sàn chứ không trên mặt bàn cao · dây đủ dài để robot ngã mà không giật đứt |
| **Bài canh** | `tests/test_tc102_the_an_toan_firmware_chinh.py` — 6 bài, trong đó một bài đòi checklist cân bằng KHÁC checklist chẩn đoán |

---

## SL-133 · LỆCH THẬT · Vòng tự sửa đốt cả ba lượt cho một cổng nó không thể sửa

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §6 (vòng tự sửa ≤ N=3); TC-06, TC-19 |
| **Cách tìm** | Module đầu tiên của bài robot cân bằng. `eaa gen logic_pid`: compile/size/static ĐẠT cả ba lượt, `unittests` KHÔNG ĐẠT cả ba lượt, rồi hết lượt |
| **Lỗi** | Lý do trượt là *"không có bộ kiểm thử đơn vị nào trong projects/…/tests"*. Mã module hoàn toàn đúng — nó vừa qua ba cổng còn lại. Thứ còn thiếu là **một phần của DỰ ÁN**, không nằm trong tệp đang sửa. **Không bản vá nào của module làm cổng ấy đạt được** |
| **Cơ chế đã có sẵn và đã đúng** | `orchestrator` biết dừng khi gặp lỗi cấu hình, và câu nó nói ra đã đúng sẵn: *"Lỗi CẤU HÌNH, không phải lỗi mã — vòng tự sửa không mở… đưa nó vào vòng vá chỉ đốt lượt gọi và làm hỏng mã đang đúng"* |
| **Cổng chỉ không đặt cờ** | `UnitTestGate` không đặt `config_error`, nên lỗi rơi vào nhánh mặc định "chắc tại mã". **Cơ chế đúng, phân loại thiếu** — và cái giá là 3 lượt gọi mô hình mỗi module, tức 15 lượt cho cả bản phân rã |
| **Phân biệt hai chuyện** | *Chưa có test* là lỗi dự án. *Test có mà đỏ* ĐÚNG là việc của vòng tự sửa. Đánh dấu cả hai là lỗi cấu hình sẽ tắt vòng ấy ở đúng chỗ nó có ích |
| **Lỗi thứ hai — mô hình không biết cổng chạy bằng gì** | Lượt vá cuối nó thử tạo `tests/test_dummy.c` — một tệp **C** — cho một cổng chạy **pytest**. Không chỗ nào nói điều đó, nên nó đoán bằng thứ quen nhất với ngữ cảnh: đây là dự án C |
| **Đã sửa** | Đặt `config_error` khi CHƯA CÓ test (không đặt khi `allow_empty`, vì đó là chế độ có chủ ý). Thông báo nói thẳng ba điều: đây không phải lỗi mã · cổng chạy bằng pytest · test là mã Python gọi vào lớp giả lập, không phải mã C |
| **Lần thứ ba cùng một hình dạng trong phiên** | SL-114 (lỗi cú pháp công cụ `avr-size`), SL-129 (hết giờ thu telemetry), và giờ là đây. Vòng tự sửa mặc định coi mọi cổng trượt là lỗi mã, và **ba lần trong một phiên nó sai** |
| **Bài canh** | `tests/test_tc103_thieu_bo_kiem_khong_phai_loi_ma.py` — 6 bài |

---

## SL-134 · LỆCH THẬT (×3) · Quy trình đòi một thứ mà chính nó không sinh ra

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §6; công đoạn C2 (firmware viết tách lớp trừu tượng để chạy được trên máy chủ); FR-VER-01 |
| **Cách tìm** | Gỡ chỗ chặn của bài robot cân bằng, ngay sau SL-133 |
| **Lỗi 1 — cổng bắt buộc đòi thứ không ai sinh** | `unittests` nằm trong `required_gates`, nhưng bộ điều phối bảo mô hình sinh **đúng hai tệp**: `src/<mod>.c` và `.h`. Không bao giờ có test. **Quy trình không có cách nào tự qua cổng của chính nó** — và nó đã chặn như thế từ sprint đầu, chỉ chưa ai đi tới module nào để phát hiện |
| **Vì sao không phải "quên viết test"** | Thiết kế nói firmware được viết tách lớp trừu tượng phần cứng CHÍNH LÀ để chạy được trên máy chủ. Lời hứa ấy chỉ thành thật khi mỗi module ra đời KÈM bài kiểm chứng minh nó chạy được ở đó — sinh mã mà không sinh test là giữ lại lời hứa và bỏ phần trả giá cho nó |
| **Lỗi 2 — không ai nói cổng ấy chạy bằng gì** | Cách dịch một module cho máy chủ là chuyện của NỀN TẢNG. Pack nay khai `host_test`: trình dịch máy chủ, cờ, thư mục tiêu đề giả, và hợp đồng — *bài kiểm là mã Python dịch `.c` bằng `cc` rồi gọi qua `ctypes`* |
| **Lỗi 3 — cổng nhìn vào sai thư mục** | Bộ sinh mã ghi vào `firmware/src/` và `firmware/tests/`; cổng đọc `<dự án>/tests`. **Hai thư mục khác nhau.** Sau khi sửa hai lỗi trên, mô hình đã viết đúng `tests/test_logic_pid.py` — tệp nằm ngay đó — mà cổng vẫn báo *"không có bộ kiểm thử đơn vị nào"* |
| **Không ai sai một mình** | Bộ sinh ghi đúng chỗ của nó, cổng đọc đúng chỗ của nó, và hai chỗ ấy **chưa bao giờ được đối chiếu** — vì chưa lần nào có tệp test thật để lộ ra |
| **Kết quả** | `logic_pid` qua **đủ 4 cổng, 0 vòng tự sửa** — module đầu tiên của cả dự án làm được thế |
| **Bài kiểm Agent tự viết là bài kiểm THẬT** | Nó dịch chính `src/logic_pid.c` bằng đúng cờ pack khai, nạp bằng `ctypes`, mirror cấu trúc, và kiểm riêng P/I/D, chặn biên, chống bão hòa tích phân. **Không** chép thuật toán sang Python rồi kiểm bản chép |
| **Nhưng một lượt ghi khác cho thấy nó không luôn thế** | Khi ghi lại fixture E2E, mô hình sinh một test kiểu `assert "delay(" not in code` — **soi văn bản mã nguồn**, tức làm lại việc của cổng phân tích tĩnh, và không chứng minh gì về hành vi. Hợp đồng của pack nay cấm thẳng kiểu ấy |
| **Cái giá của một prompt đổi** | Bộ phát lại của TC-15 khớp theo **băm prompt**, nên mọi cải tiến prompt làm 10 bài E2E đỏ. Nó nói đúng câu cần nói — *"Phát lại KHÔNG bịa phản hồi: một lượt tự sinh nội dung sẽ tạo bằng chứng giả"* — và chỉ sang `scripts/record_e2e_fixture.py`. Đã ghi lại bằng mô hình thật |
| **Bài canh** | `tests/test_tc104_sinh_ma_kem_bo_kiem.py` — 7 bài, trong đó một bài đối chiếu **danh sách cổng bắt buộc** với **danh sách tệp phải sinh**: đòi `unittests` thì phải sinh ít nhất một tệp test |

## SL-135 · LỆCH THẬT (×3) · Ý ĐỊNH của module bị vứt trước khi tới bộ sinh mã

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §3.2 (backlog), §4 (lớp K4 của prompt); EAA-AIS-05 (thư viện mẫu prompt, NFR-05) |
| **Cách tìm** | Review G3 module `logic_pid` — module đầu tiên qua đủ bốn cổng, 0 vòng tự sửa. Mã dịch được, test xanh, và **hai lỗi thiết kế thật** |
| **Lỗi trong mã sinh ra** | `d_term = kd * (error - prev_error)` — đạo hàm lấy theo **sai số**; và `kp * error` với hệ số nguyên, **không có tỉ lệ fixed-point**, dù bản phân rã đã duyệt ghi rõ *"PID số nguyên (fixed-point)"* và hệ số tham chiếu của dự án là `kd = 3.4` |
| **Vì sao bốn cổng không bắt được** | Cổng đo mã **có chạy được không**, không đo mã **có làm đúng việc không**. Không cổng nào biết module này phải làm gì, nên không cổng nào có thể biết nó làm sai |
| **Lỗi 1 — `plan accept` vứt `purpose`** | Bản phân rã có `purpose`, `provides`, `period_ms`; người đọc và duyệt ở G1 chính những câu ấy. Vào backlog chỉ còn `id`, `uses`, `depends_on`. **Thứ người vừa duyệt bị vứt ngay tại chỗ nhận** |
| **Lỗi 2 — nhiệm vụ giao đi giống hệt nhau cho mọi module** | `goal = "Hiện thực module X theo ràng buộc và tài liệu đã duyệt"`. Đổi `X` là hết khác biệt. Một prompt sinh mã không mang ý định nào cả thì mô hình phải tự bịa ra một ý định — và nó bịa bằng thứ quen nhất, là PID sách giáo khoa |
| **Lỗi 3 — `PromptLibrary` được nạp mà không đường nào đọc** | Nó là cơ chế thiết kế dành riêng cho việc này: *"mẫu của dự án ghi đè mẫu của pack… để một dự án chỉnh được cách diễn đạt cho bài toán của nó mà không phải sửa pack"* (NFR-05). Có từ sprint đầu, `KnowledgeBase.prompts` trỏ đúng chỗ, và `grep -rn "\.prompts\b" eaa/*.py` ngoài `kb.py` ra **không có gì**. Lần thứ **năm** của dạng "mã đúng nằm chết" |
| **Tri thức đã có sẵn, chỉ nằm sai chỗ** | `sim/controller.py` của dự án nêu đích danh hai lỗi kinh điển phải tránh — *"Integral windup — khi lệnh đã bão hòa, thành phần tích phân ngừng cộng dồn"* và *"Derivative kick — đạo hàm lấy theo SỐ ĐO chứ không theo sai số"*. Chúng nằm đó dưới dạng **văn xuôi trong docstring của một tệp bộ sinh mã không đọc**. Không thiếu tri thức; thiếu đường dẫn |
| **Vì sao bài kiểm tự viết cũng sai theo** | Bài kiểm do **cùng một mô hình** viết, nên nó kiểm đúng cái hiểu sai ấy là đúng: `test_pid_compute_derivative` khẳng định `out == 20` cho `kd * (error - prev)`. **Một bài kiểm tự viết chỉ bắt được chỗ mã lệch với ý định — không bắt được ý định sai.** Muốn nó bắt được thì ý định phải đến từ chỗ khác |
| **Đã sửa** | `BacklogItem` giữ `purpose` và `provides` (đọc được state cũ không có hai trường này); `plan accept` chép sang; `Orchestrator.dung_nhiem_vu()` lấy trách nhiệm module làm mục tiêu và đặt cả trách nhiệm lẫn danh sách hàm phải xuất thành **tiêu chí nghiệm thu**; `_boi_canh_mau_du_an()` nối `PromptLibrary` vào lớp nhiệm vụ, lấy đúng mẫu mang tên module |
| **Mẫu của dự án** | `projects/robot_balance/prompts/logic_pid.md` — chép nguyên văn hai ràng buộc từ `sim/controller.py`, nói rõ `d = -kd * (số_đo - số_đo_trước)`, và **đòi bài kiểm chứng minh từng điều**: đổi điểm đặt mà đạo hàm nhảy là lấy sai; `kd = 3.4` phải khác `kd = 3` |
| **Chỗ mất mát cũ** | `purpose` của bản phân rã đã duyệt không còn trong state (tệp bản phân rã bị xóa sau khi nhận). Khôi phục lại từ `llm_calls.jsonl` — nhật ký gọi mô hình giữ nguyên văn phản hồi, nên bản phân rã còn đọc lại được |
| **Đường khác cũng được nối lại** | `eaa interface` đã đọc `getattr(muc, "purpose", "")` từ trước — nó luôn nhận chuỗi rỗng. Hợp đồng gọi của mọi module cho tới nay được thiết kế mà không biết module ấy để làm gì |
| **Bài canh** | `tests/test_tc105_y_dinh_toi_duoc_bo_sinh_ma.py` — 9 bài: `purpose` sống sót qua đĩa, state cũ vẫn đọc được, nhiệm vụ mang ý định, mẫu của module khác không bị lấy nhầm, và dự án phải khai đủ ba luật thiết kế |

## SL-136 · LỆCH THẬT (×4) · Lý do người từ chối gate không tới được prompt

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §3 (K5, Hình 1); §12 (KPI theo dõi mất ngữ cảnh); FR-KB-03, TC-10 |
| **Cách tìm** | KIỂM một lời hứa thay vì tin nó. `eaa gate reject` in ra *"Lý do đã ghi vào Error Ledger và sẽ có mặt trong prompt lần sinh lại"*. Dựng lại đúng prompt ấy ngoài luồng rồi đếm token từng lớp |
| **Cái đếm được** | `TỔNG: 2070/8000` · `đã bị lược: ['error_rules']`. **Lý do từ chối không có trong prompt.** Thừa 5930 token mà lớp 300 token bị xóa sạch |
| **Lỗi 1 — chặn độ dài sai nhánh** | `LedgerEntry.as_rule` cắt ở nhánh SUY RA từ mô tả lỗi và **không cắt nhánh quy tắc do người viết** — đúng nhánh `gate reject` dùng, và đúng nhánh dễ dài, vì người viết lý do thì viết cho người đọc |
| **Lỗi 2 — K5 lấy top-3 rồi ghép thẳng** | Không nhét vừa phần của lớp. Ba quy tắc dài là chắc chắn vượt 300 token |
| **Lỗi 3 — vượt phần thì XÓA CẢ LỚP** | Bộ lược ngân sách cắt bỏ nguyên lớp `error_rules` chứ không rút gọn. Mất toàn bộ thay vì mất phần đuôi |
| **Lỗi 4 — và cái giấu được cả ba** | `prompt.trimmed` có từ sprint đầu, chú thích ghi *"để KPI theo dõi"*. KPI **chưa bao giờ nhận được nó**; không lệnh nào in nó ra. Việc lược là im lặng tuyệt đối. Lần thứ **sáu** của dạng "mã đúng nằm chết" |
| **Vì sao lỗi 4 mới là lỗi đắt nhất** | Ba lỗi trên đều lộ ra ngay nếu có một dòng chữ nói "đã lược error_rules". Không có dòng ấy, mã sinh ra thiếu đúng phần quan trọng nhất và mọi thứ trông vẫn xanh. Vòng tự sửa chạm N vì THIẾU NGỮ CẢNH và vì mã khó trông giống hệt nhau trong số liệu — mà cách chữa của chúng thì ngược nhau |
| **Đã sửa** | `_lop_quy_tac_loi` nhét vừa phần của lớp, giữ NGUYÊN VẸN quy tắc đầu bảng (lỗi của chính module, vừa bị người từ chối) thay vì cắt cụt cả ba; không quy tắc nào vừa thì cắt **có dấu** kèm chỗ đọc bản đầy đủ. `Orchestrator.canh_bao_luoc()` nói ra ở cả lượt sinh đầu lẫn mọi vòng vá. Cột KPI `trimmed` |
| **Đo lại sau khi sửa** | `error_rules 242 token` · `TỔNG 2312` · `đã lược: (không)`, và câu *"pid_set_tunings kiêm luôn khởi tạo"* có mặt trong prompt |
| **Lỗi 5 — sản phẩm dịch lọt vào diff review** | Cổng kiểm trên máy chủ (SL-134) dịch mã C thành thư viện dùng chung ngay trong kho firmware, sinh `tests/__pycache__/` và `tests/*.so`. `GitRepo.BUILD_DIRS` chỉ có `build/` và không được nới theo. Chúng vào commit module và vào **đúng bản diff người phải đọc ở G3**; rồi một tệp `.pyc` đổi nội dung chặn luôn `git checkout` và làm hỏng cả lượt sinh |
| **Hai cổng đã chặn đúng trên đường sửa** | Thêm cột KPI bị chặn vì *"Cột KPI không có trong lược đồ"*; rồi bị chặn lần nữa vì tệp cũ có lược đồ khác, kèm chỉ dẫn giữ lại số liệu đã thu. Cả hai lần đều nói đúng lối đi tiếp — đối lập với nhóm "ngõ cụt" |
| **Phụ — thông báo vượt ngân sách chỉ sang chỗ không liên quan** | Nó luôn nói *"giảm top-k chunk, rút gọn lớp interface, chưng cất thêm quy tắc lỗi"*, đúng cho ba lớp và sai cho những lớp còn lại. Gặp hai lần trong một buổi (`task`, rồi `project_rules`). Nay mỗi lớp có lối đi riêng, và một bài canh đòi lớp nào cũng phải có |
| **Bài canh** | `tests/test_tc106_ly_do_tu_choi_toi_duoc_prompt.py` — 9 bài; `tests/test_tc105_*` thêm 2 bài cho thông báo vượt ngân sách |

## SL-137 · LỆCH THẬT (×2) · Cổng kiểm thử chạy trên thư viện của lần trước

| | |
|---|---|
| **Tài liệu** | EAA-SDD-03 §2 (pytest runner); FR-VER-01; công đoạn C2 |
| **Cách tìm** | Review G3 vòng ba của `logic_pid`, đọc phần đầu tệp test do mô hình sinh |
| **Cái nó viết** | ``try: subprocess.check_call(['cc', ...]) / except Exception: pass  # Bỏ qua nếu test runner đã tự biên dịch`` rồi ``ctypes.CDLL(lib_path)`` |
| **Đo, không suy đoán** | Xóa MỘT dấu chấm phẩy trong `logic_pid.c` rồi chạy lại: `4 passed in 0.09s`. **Bốn bài kiểm xanh trên một tệp nguồn không dịch nổi** |
| **Vì sao nguy hiểm** | `unittests` là mắt xích thứ tư của chuỗi kiểm chứng và là cổng bắt buộc để merge. Ở trạng thái ấy nó không kiểm chứng gì cả — cùng họ với SL-120, nơi `avrdude` báo thành công sau khi đọc 0 byte |
| **Đã sửa — cấu trúc, không phải lời dặn** | Cổng xóa sản phẩm dịch (`*.so`, `*.dylib`, `*.dll`, `*.o`, `*.a`) trong thư mục test TRƯỚC mỗi lần chạy. Không còn thư viện cũ thì việc nuốt lỗi dịch **không còn chỗ ẩn**: `ctypes` sập, cổng đỏ đúng lúc phải đỏ |
| **Và lời dặn vẫn giữ** | Hợp đồng `host_test` của pack cấm thẳng `try/except` quanh lệnh dịch — nó nói VÌ SAO, còn cưỡng chế nằm ở cấu trúc. Một luật chỉ sống trong prompt là luật phụ thuộc vào việc mô hình có đọc kỹ hay không, mà chính mô hình ấy vừa viết ra `except Exception: pass` kèm lời giải thích nghe rất hợp lý |
| **Lỗi kèm — sản phẩm dịch vào diff review** | `GitRepo.BUILD_DIRS` chỉ loại trừ `build/`. Cổng kiểm trên máy chủ sinh `tests/__pycache__/` và `tests/*.so` ngay trong kho firmware, nên chúng vào commit module và vào **đúng bản diff người phải đọc ở G3**; rồi một tệp `.pyc` đổi nội dung chặn luôn `git checkout` và làm hỏng cả lượt sinh |
| **Bài canh** | `tests/test_tc107_cong_kiem_khong_chay_tren_thu_vien_cu.py` — 6 bài, trong đó một bài **dựng lại đúng cái bẫy**: dịch một thư viện chạy được, viết bộ test nuốt lỗi y bản mô hình sinh, làm hỏng nguồn, rồi đòi cổng phải đỏ |

## SL-138 · PHƯƠNG PHÁP · Sửa cái được nêu tên, làm hỏng cái không được nêu

| | |
|---|---|
| **Cách tìm** | Ba vòng review G3 liên tiếp của `logic_pid`, mỗi vòng đo lại bằng ctypes trên chính bản C |
| **Hình dạng** | Vòng 2 nêu 2 điểm → sửa đúng 2, **thoái lui 3 chỗ khác**. Vòng 3 nêu 3 điểm → sửa đúng 3, **thoái lui 2 chỗ khác** |
| **Thoái lui ở vòng 3, đo được** | (a) tích phân cộng dồn SAU khi chia cho tỉ lệ Q8: sai số 1 mrad kéo dài 1 s → tích phân = **0**, mất 100%; 2 mrad → mất 44%. Integrator chết đúng ở dải sai số nhỏ mà nó sinh ra để khử. Vòng 2 làm đúng (`int64` giữ nguyên thang Q8). (b) mất `int64` ở trung gian: `kd_Q8 × d_meas` tràn `int32` từ 24672 mrad; một lượt đọc I²C hỏng trả 32767 làm đạo hàm **đổi dấu** — đo được đầu ra `+3000` ở chỗ phải là `-3000`, tức lệnh hết cỡ về phía ngược lại |
| **Vì sao không phải "mô hình cẩu thả"** | Mỗi vòng, `eaa gen` sinh lại CẢ tệp test. Không có gì neo lại hành vi đã được duyệt ở vòng trước: mã cũ bị xóa, test cũ bị xóa, và mọi bảo đảm bốc hơi cùng lúc. **Vòng tự sửa không có bánh cóc.** Cái duy nhất tích lũy qua các vòng là danh sách yêu cầu tôi viết tay trong mẫu prompt của dự án |
| **Bài học phương pháp** | Một bản review nêu N điểm sẽ được sửa đúng N điểm. Nó không giữ giùm những điểm đã đúng — chỉ có TEST mới giữ được, và test phải sống sót qua lần sinh lại |
| **Chưa sửa** | Đề xuất: prompt sinh lại mang theo TÊN + docstring của những bài kiểm đã có (khoảng 150 token, không phải cả tệp), kèm luật "những hành vi này đã được duyệt, chỉ được thêm, không được bỏ hay làm yếu đi" |

## SL-139 · LỆCH THẬT · Quyết định G1 chỉ neo vào MỘT NỬA hồ sơ

| | |
|---|---|
| **Tài liệu** | EAA-AIS-05 §8.1; EAA-SDD-03 §2; FR-GATE-01 |
| **Cách tìm** | Sửa `hardware_profile.yaml` để thêm còi và nút nhấn cho giao thức khởi động mới: đổi bảng chân của bốn chân động cơ, thêm hai linh kiện, thêm một bộ đếm. Rồi chạy `eaa status` — `✓ G1 approved`, không cảnh báo, không đòi duyệt lại |
| **Thiết kế nói ngược lại, bằng chữ, ở ngay đầu tệp bị sửa** | *"Sửa tệp này kích hoạt phân tích ảnh hưởng và phải duyệt lại tại G1 (AIS §8.1) — đổi một chân là đổi mọi module chạm vào chân đó."* |
| **Ba chỗ để câu ấy rơi** | (a) hồ sơ G1 in `hardware_profile.yaml v{version}` — **số phiên bản khai TRONG tệp**, không phải băm nội dung, nên sửa nội dung mà giữ `version: 1` thì dòng ấy giống nhau từng ký tự; (b) `content_digest` của G1 chỉ là băm `constraints.yaml`, nên quyết định của người **không neo vào** thứ họ vừa đọc ở dòng trên; (c) phép kiểm trôi băm ở `eaa status` cũng chỉ soi `constraints.yaml` |
| **Và băm ấy vẫn được tính** | `HardwareProfile.content_version` có sẵn, đúng tên, đúng cách tính, dùng ở chỗ khác trong `cli.py` để ghi phẩm xuất. Cổng chỉ không hỏi tới. Lần thứ **bảy** của dạng "mã đúng nằm chết" |
| **Vì sao đắt hơn vẻ ngoài** | G1 tên là *chốt ràng buộc cứng và kiến trúc*. Bảng chân LÀ kiến trúc. Một cổng neo vào nửa hồ sơ là một cổng cho qua nửa còn lại — và nửa bị bỏ qua là nửa quyết định mã sinh ra sẽ ghi mức logic vào chân nào |
| **Còn một chỗ nữa cùng tệp** | `pin_map` khai bốn chân động cơ trên PB0–PB4 trong khi khối `components` đã sửa sang PD4–PD7 từ trước. **Hai chỗ trong CÙNG MỘT TỆP nói hai điều khác nhau suốt bốn sprint**, vì chưa module nào đọc cả hai. Nó thành nguy hiểm thật hôm nay: còi ở PB2 và nút ở PB4 — đúng hai chân bảng cũ đang khai là DIR_L/DIR_R |
| **Đã sửa** | `dau_van_tay_G1()` gộp băm hai tệp; hồ sơ G1 cho người đọc **cả** `hardware_profile.yaml`; `ProjectState.hardware_version` chốt cùng lúc khi duyệt; phép kiểm trôi soi cả hai |
| **Trường hợp di trú nói ra, không im** | Dự án cũ có G1 approved mà chưa có mốc phần cứng: `status` báo *"CHƯA NEO"*. Im ở đây sẽ giữ nguyên đúng lỗ vừa vá — không có mốc thì không phát hiện được trôi, và "không phát hiện được" đọc y hệt "không có gì trôi" |
| **Bài canh** | `tests/test_tc108_g1_neo_ca_ho_so_phan_cung.py` — 8 bài, trong đó một bài neo vào chính câu chữ đã hứa trong `hardware_profile.yaml` để nó không bị lặng lẽ bỏ đi |

## SL-140 · LỆCH THẬT · Phân rã vòng hai không bao giờ hợp lệ

| | |
|---|---|
| **Cách tìm** | `eaa plan propose` lần thứ hai, sau khi hồ sơ phần cứng khai thêm còi và nút: *"Module 'app_ui' phụ thuộc vào module không có trong bản phân rã: ['app_balance']"* |
| **Mô hình làm đúng** | `app_balance` đã ở trong backlog và đã duyệt; module mới phụ thuộc vào nó là chuyện bình thường. Chỗ sai nằm ở bộ kiểm |
| **Nửa còn lại của SL-131** | SL-131 dạy BỘ PHÂN RÃ biết module đã có (`propose(..., existing=...)` → prompt + chặn trùng tên). `DecompositionPlan` vẫn giữ giả định cũ rằng **một bản phân rã là tự đủ**. Bộ phân rã biết, còn bản phân rã thì không |
| **Vì sao bốn sprint không ai thấy** | Đây là lần đầu một dự án chạy tới vòng phân rã thứ hai; mọi bài kiểm cũ đều dựng bản phân rã từ backlog rỗng |
| **KHÔNG nới lỏng phép kiểm** | Cách sai là bỏ phép kiểm phụ thuộc — nó bắt lỗi thật (mô hình nêu một cái tên nó chưa từng đề xuất). Cách đúng là cho bản phân rã BIẾT tập module đã tồn tại rồi vẫn kiểm nghiêm ngặt trên tập đầy đủ |
| **Đã sửa** | `DecompositionPlan.known`, đi qua cả `to_dict/from_dict` (bản phân rã được ghi ra đĩa giữa `propose` và `accept` — mất `known` ở giữa thì chỗ chặn chỉ dời đi một lệnh). `order()` trừ module đã có ra khỏi kết quả: thêm nhầm một module đã merge là chạy lại `eaa gen` trên mã đã duyệt |
| **Bài canh** | `tests/test_tc109_phan_ra_vong_hai.py` — 7 bài |

## SL-141 · LỆCH THẬT (×2) · Bối cảnh phân rã chỉ mang TÊN, không mang THUỘC TÍNH

| | |
|---|---|
| **Cách tìm** | Bản phân rã đề xuất `drv_buzzer` **chiếm `timer2`** — đúng bộ đếm đang phát xung bước. Một cái còi cướp nhịp bước là robot ngã, và không cổng phần mềm nào bắt được |
| **Sửa hồ sơ vẫn không ăn thua** | Ghi thẳng vào hồ sơ rằng đây là còi CHỦ ĐỘNG (`drive: dc_on_off`, tự dao động, chỉ đặt mức chân), kèm bằng chứng từ mã tham chiếu. Phân rã lại: `drv_buzzer` **chiếm `timer1`**. Nó chỉ đổi sang bộ đếm khác |
| **Lỗi 1 — hồ sơ bị rút thành danh sách tên** | `_boi_canh` lấy `[c["id"] for c in components]` rồi `", ".join(...)`. Mọi thuộc tính bị bỏ: `drive`, `active_level`, `pins`, `kind`, `note`. Bộ phân rã nhận một DANH SÁCH TÊN và phải tự đoán mỗi tên cần gì — nên nó đoán "còi" thì cần bộ đếm, đúng theo trực giác chung về còi thụ động |
| **Lỗi 2 — module đã có không kèm trách nhiệm** | `_boi_canh_da_co` in `id (chiếm: ...)`, không có `purpose`. Bộ phân rã biết `app_balance` TỒN TẠI mà không biết nó LÀM GÌ, nên đề xuất thêm `app_hmi` ôm đúng giao thức nút nhấn và tiếng bíp mà `app_balance` đã nhận. `purpose` nằm sẵn trong backlog từ SL-135; chỗ dựng danh sách `existing` chỉ lấy `(id, uses)` |
| **Kết quả sau khi sửa** | `drv_buzzer` chiếm ĐÚNG `buzzer`, không xin bộ đếm nào; không còn module ôm lại việc của `app_balance`; và bộ phân rã tự nhận ra dự án thiếu đường telemetry cho nghiệm thu G4, đề xuất `app_telemetry` |
| **Bài canh** | `tests/test_tc110_boi_canh_phan_ra_du_thuoc_tinh.py` — 8 bài |

## SL-142 · LỆCH THẬT · Hồ sơ đang chờ ở gate bị ghi đè, mất bằng chứng review

| | |
|---|---|
| **Cách tìm** | Sinh hai driver liên tiếp. Sau đó: ba module ở `in_review`, và `gates/pending_G3.json` chỉ còn hồ sơ của module CUỐI |
| **Cơ chế** | Một tệp cho mỗi CỔNG chứ không phải mỗi MODULE: `pending_{gate_id}.json`. `request()` ghi thẳng vào đó |
| **Mất mát thật** | Hồ sơ G3 mang **bản diff và băm nội dung** mà quyết định của người neo vào. Mất nó thì hai module kia không còn đường ra khỏi `in_review`: `gate approve` báo không có gì đang chờ, mã đã sinh nằm trên nhánh không ai merge được |
| **Và một cách hiểu sai rất dễ xảy ra** | Màn hình vừa báo ba module qua bốn cổng; người bấm duyệt sẽ tin mình vừa duyệt cả ba, trong khi chỉ một module được merge |
| **Đã sửa — chặn, không xếp hàng** | `request()` từ chối ghi đè hồ sơ của MODULE KHÁC, kèm câu nói rõ module nào đang giữ chỗ và hai lệnh đi tiếp. Ghi đè hồ sơ của CHÍNH module ấy vẫn được — đó là đường đi sau mỗi lần từ chối G3 |
| **Lựa chọn có ý thức** | Cách giàu hơn là mỗi module một hồ sơ, review theo lô. Chặn thì không đánh mất gì và nói rõ lối đi tiếp; xếp hàng là cơ chế lớn hơn, chỉ đáng làm khi thật sự có người review theo lô |
| **Bài canh** | `tests/test_tc111_ho_so_gate_khong_bi_ghi_de.py` — 5 bài |

## SL-143 · LỆCH THẬT (×4) · Đường kiểm trên máy chủ chưa từng chạy được với mã chạm thanh ghi

| | |
|---|---|
| **Cách tìm** | Sinh `drv_button` — module đầu tiên của cả dự án thật sự đọc một chân |
| **Lỗi 1 — bảng kiểm sẵn sàng không thấy thanh ghi cổng** | `button_set` không khai `configured_by`, nên `eaa resolve` chấm *"THIẾU 0 · đủ điều kiện"* và mở vòng sinh mã. Agent viết đúng kỷ luật: `// Thiếu thông tin tài liệu thanh ghi cho PB4. Không lấp chỗ trống.` — **module qua sạch bốn cổng mà không đọc nổi một chân**. Chính bảng kiểm đã tự khai giới hạn ấy bằng chữ; giờ nó có thật |
| **Lỗi 2 — `hostmock` được khai mà chưa bao giờ được tạo** | `pack.yaml` khai `host_test.mock_include: hostmock` từ SL-134. Thư mục ấy **không tồn tại**. Mọi module chạm thanh ghi chết ở cổng thứ tư với `fatal error: 'avr/io.h' file not found`, và vòng tự sửa đốt ba lượt cho một thứ không bản vá nào của module sửa được |
| **Lỗi 3 — nói TÊN thư mục, không nói CHỖ** | Prompt viết *"thư mục `hostmock` của Platform Pack"*, mô hình viết `-Ihostmock` — đường dẫn tương đối so với thư mục firmware, nơi không có thư mục ấy. Nay engine giải đường dẫn tại chỗ biết pack nằm đâu, và nêu cả tệp `.c` phải dịch kèm |
| **Lỗi 4 — cổng phân tích tĩnh đỏ vì lý do thẩm mỹ** | `--enable=...,style` cộng `--error-exitcode=1`: ghi chú *"phạm vi biến này thu hẹp được"* làm cổng đỏ. Tệ hơn, `error_regex` chỉ bắt `error|warning` nên thoát mã 1 mà **không parse được gì**, và orchestrator coi đó là lỗi mã. Bỏ `style`, mở rộng regex cho mọi mức, và đưa thư mục tiêu đề giả cho cppcheck để nó thôi báo `unknown type name 'uint32_t'` |
| **Và một luật chung rút ra** | Công cụ thoát khác 0 mà luật parse không bắt được gì nay được đánh dấu `config_error`: thứ cần sửa là một biểu thức chính quy trong `pack.yaml`, không nằm trong tệp mã đang xét. Cùng họ SL-133, khác cổng |
| **Trích đoạn tài liệu bổ sung** | `ds-atme-gpio-01` — DDRB/PORTB/PINB/MCUCR, trích tr.85 và tr.100 của datasheet chính chủ, chưng cất theo K2 rồi duyệt G2. Danh sách `registers` phải chuẩn hóa từ dạng chung `DDRx/PORTx/PINx` mà máy trích ra: đồ thị so khớp THEO TÊN, để nguyên thì chunk không bao giờ được truy xuất |
| **`ds-032` cũng được gỡ treo** | Chỗ *"chưa đối chiếu xong hệ số nhạy"* giải bằng chính mã nhà sản xuất, hai con số độc lập: `GYRO_CONFIG=0x00` với hằng số 0.000031 = 1/(131 × 250 Hz), và `ACCEL_CONFIG=0x08` với `asin(raw/8200)`. Hai chỗ khác nhau trong mã cùng chỉ về một cấu hình |

## SL-144 · LỆCH THẬT · Một tài nguyên giàu tài liệu bỏ đói tài nguyên kia

| | |
|---|---|
| **Cách tìm** | Duyệt `ds-032` cho driver cảm biến làm **chín bài kiểm đỏ cùng lúc**, trong đó bộ chuẩn truy xuất TC-20 tụt precision xuống 0,889 |
| **Hiện tượng** | Module dùng `twi` + `imu`: ba chỗ trong prompt thành `(ds-031, ds-032, ds-021)` — cảm biến lấy hai, bus lấy một, và **chunk MÃ TRẠNG THÁI BUS bị đẩy ra** |
| **Vì sao nguy hiểm** | Mã trạng thái là thứ quyết định bước tiếp theo sau mỗi lần bus báo xong; thiếu nó thì driver không hoàn tất nổi một lượt truyền. Mất tài liệu về một ngoại vi mình đang dùng chính là chỗ mô hình bắt đầu bịa — và bịa ở tầng bus thì mọi thứ bên trên sai theo |
| **Nguyên nhân** | Xếp hạng thuần theo điểm. Một tài nguyên có nhiều trích đoạn sẽ chiếm hết ba chỗ, tài nguyên kia không còn dòng nào |
| **Đã sửa** | Chia đều theo tài nguyên: mỗi tài nguyên được một chỗ trước khi tài nguyên nào lấy chỗ thứ hai. Thứ tự trong mỗi vòng vẫn theo xếp hạng cũ nên kết quả vẫn TẤT ĐỊNH |
| **Thứ tự vòng có căn cứ, không tùy tiện** | Với hai tài nguyên và ba chỗ, tài nguyên đi trước lấy chỗ thứ ba — xếp theo bảng chữ cái là để một chi tiết vô nghĩa quyết định tài liệu nào vào prompt. Hồ sơ phần cứng đã có quan hệ ấy: cạnh `on_bus` từ linh kiện tới ngoại vi. **Bus đi trước thiết bị nằm trên nó**, vì con cảm biến không đọc được byte nào trước khi bus chạy được |
| **Một mắt xích nữa suýt làm phép sửa vô hiệu** | Chunk nối với THANH GHI chứ không nối thẳng với ngoại vi. Bản sửa đầu tra `_edges_from(res, "documented_in")` nên mọi chunk rơi vào "không thuộc ai" và phép chia đều không bao giờ chạy — im lặng, không lỗi |
| **Đọc bộ chuẩn theo hướng nào** | `retrieval_golden.yaml` tự viết sẵn bài học cho đúng tình huống này: một ca đỏ ở đây có HAI nguyên nhân trái ngược — bộ chọn kém đi, hoặc kho vừa có thêm thứ đúng. Lần này là cả hai: ds-032 liên quan thật (nên bộ chuẩn được cập nhật lên bốn mục), NHƯNG cách bộ chọn nhường chỗ thì sai (nên bộ chọn được sửa) |
| **Và một dữ kiện dự án bị dùng làm đạo cụ** | Năm bài kiểm dùng `ds-032` làm "chunk chưa duyệt G2". Duyệt nó vì nhu cầu thật của dự án làm cả năm đỏ. Nay vai ấy do `ds-atme-gpio-02` (cổng D) đóng — một trích đoạn dự án **thật sự** đang cần và **thật sự** chưa ai đối chiếu |

## SL-145 · LỆCH THẬT (×2) · Tiêu đề giả không giống thật ở đúng chỗ mã chạm tới

| | |
|---|---|
| **Cách tìm** | Sinh bảy module liên tiếp cho robot cân bằng, mỗi module chạm thanh ghi một kiểu khác nhau |
| **Lỗi 1 — thanh ghi là MACRO nên không có ký hiệu** | Bản mock đầu định nghĩa `#define PORTB eaa_io[0x05]`. Bài kiểm sinh ra viết `ctypes.c_uint8.in_dll(lib, "PORTB")` — phản xạ đầu tiên của bất cứ ai — và chết với `symbol not found` dù mã C hoàn toàn đúng. Đổi sang BIẾN TOÀN CỤC mang đúng tên thanh ghi |
| **Lỗi 2 — thiếu tên chân kiểu cũ** | avr-libc định nghĩa `PD4`, `PB2`…; mã thật hay dùng `(1 << PD4)`. Mock thiếu chúng thì cổng dịch AVR ĐẠT còn cổng kiểm máy chủ đỏ với `use of undeclared identifier 'PD4'` — mô hình bị đẩy vào vòng vá cho một lỗi CỦA MOCK |
| **Luật rút ra** | Mock phải giống thật ở MỌI tên mã sẽ dùng. Thiếu một tên là dựng ra một lỗi không tồn tại trên thiết bị, và mô hình không có cách nào biết đó không phải lỗi của nó |

## SL-146 · LỆCH THẬT · Duyệt một module là mở cửa ra khỏi cả pha phát triển

| | |
|---|---|
| **Cách tìm** | Merge `drv_i2c` — module thứ ba trên bảy — rồi duyệt G2 cho một trích đoạn. Máy in *"Dự án chuyển sang pha E"*, và lệnh kế tiếp chết: *"vòng sinh mã chỉ chạy ở pha D"*. Bốn module còn nguyên `todo` |
| **Cơ chế** | Cung D → E gác bằng G3, và `check_transition` chỉ nhìn `gates`. G3 là cổng của TỪNG MODULE nhưng trạng thái của nó là một ô duy nhất, và nó không quay về `pending` sau merge — nên duyệt lần đầu là mở cửa vĩnh viễn |
| **Cái giá** | Pha E đặt mức phân quyền về HUMAN. Ra khỏi D không chỉ là một nhãn sai: nó ĐÓNG vòng sinh mã, và người phải tự sửa state để đi tiếp |
| **Đã sửa** | `check_transition` nhận thêm `backlog`; cung D → E đòi mọi module `merged`. Lỗi tách riêng thành `PhaseNotComplete` vì nó đòi một hành động khác hẳn `GateNotApproved`: "làm nốt việc", không phải "đi tìm người bấm duyệt" |
| **Bài canh** | `tests/test_tc113_khong_roi_pha_D_khi_con_module.py` — 7 bài |

## SL-147 · LỆCH THẬT · Trần của lớp vá chặn vòng tự sửa khi còn nửa ngân sách trống

| | |
|---|---|
| **Cách tìm** | Ba lần liên tiếp trong một buổi: `repair: 1836/1600` rồi `1916/1800`, với prompt tổng 4752 và 4255 trên 8000 |
| **Vì sao lớp này khác mọi lớp khác** | Nó là lớp CUỐI được thêm và nó THAY CHỖ lớp `task` — không cạnh tranh với ai. Kích thước của nó do THÂN HÀM ĐANG HỎNG quyết định, thứ không kiểm soát được |
| **Cách chữa sai** | Nới số. Tôi nới hai lần và nó chạm lại ngay module sau; nới lần ba là thừa nhận con số ấy không dựa trên gì |
| **Đã sửa** | Phần của `repair` là SÀN, không phải trần: nó dùng chỗ trống thật còn lại. Trần TỔNG vẫn chặn |
| **Bài canh** | `tests/test_tc114_lop_va_dung_duoc_cho_trong.py` — 4 bài |

## SL-148 · LỆCH THẬT · Đường dẫn tiêu đề giả phụ thuộc việc mô hình nhớ gõ cờ

| | |
|---|---|
| **Cách tìm** | Module thứ bảy: lệnh dịch trong bài kiểm có `-Isrc` và `eaa_io_space.c` nhưng THIẾU `-I<hostmock>`. Cổng đỏ vì `avr/io.h` không tìm thấy |
| **Vì sao lặp lại được** | Lệnh dịch do mô hình tự gõ lại ở MỖI module. Hợp đồng nói rõ đường dẫn, và nó quên đúng một lần trong bảy — đủ để đốt một lượt gọi |
| **Đã sửa** | Cổng `unittests` đặt `C_INCLUDE_PATH` cho tiến trình pytest. Lệnh dịch nào cũng tìm thấy, nhớ hay không nhớ cờ |

## SL-149 · LỆCH THẬT · Prompt vá mời mô hình hỏi, đường ống không có kênh nhận câu hỏi

| | |
|---|---|
| **Cách tìm** | SÁU vòng tự sửa liên tiếp kết thúc bằng *"Phản hồi không chứa khối ```file: nào"*. Sáu lượt gọi, sáu lần tính là hỏng, không lần nào là lỗi của mô hình |
| **Cơ chế** | Khi lỗi không định vị được về một dòng nguồn — bài kiểm đỏ, lỗi liên kết — `extract_function` không trích được gì, và prompt rơi vào nhánh dự phòng: *"hãy hỏi lại phần mã cần thiết thay vì viết lại cả tệp"*. Mô hình làm đúng lời dặn: nó hỏi. `parse_file_blocks` chỉ bóc khối ```file:```, nên câu hỏi bị tính là sai định dạng |
| **Ý đúng, chỗ áp sai** | Nhánh ấy muốn ngăn viết lại cả tệp một cách tùy tiện. Nhưng nó bảo mô hình làm một việc mà hệ thống KHÔNG NHẬN, và biến một nhánh dự phòng thành một ngõ cụt tất định |
| **Đã sửa** | Không định vị được thì gửi TOÀN VĂN các tệp liên quan, nhét vừa chỗ trống thật, ưu tiên tệp được thông báo lỗi nhắc tên; tệp nào không vừa thì NÊU TÊN. Vẫn đòi khối `file:`, và nói rõ đó là bắt buộc. Nhánh định vị được thì KHÔNG đổi — TC-19 giữ nguyên |
| **Bài canh** | `tests/test_tc115_vong_va_luon_doi_duoc_ban_va.py` — 5 bài |

## SL-150 · LỆCH THẬT · Cổng phân tích tĩnh áp luật mã C lên tệp kiểm viết bằng Python

| | |
|---|---|
| **Cách tìm** | `tests/test_drv_imu.py:41: [ref-citation] hàm i2c_write_async() cấu hình TWCR nhưng không có trích dẫn` |
| **Vì sao vô nghĩa** | Dòng ấy nói về một hàm GIẢ trong bài kiểm, dựng ra để lái driver. Nó không chạy trên chip và không cấu hình gì. Cổng đỏ, vòng tự sửa mở, và mô hình được yêu cầu thêm trích dẫn tài liệu vào mã Python |
| **Vì sao mới lộ ra** | Luật của cổng có từ Sprint 2 và chưa bao giờ được hỏi "áp lên tệp nào". Bộ sinh mã chỉ bắt đầu trả về tệp test từ SL-134 |
| **Đã sửa** | Cổng chỉ quét `.c` và `.h` |

## SL-151 · LỆCH THẬT · Một lượt sinh hỏng khoá cứng lượt sau

| | |
|---|---|
| **Cách tìm** | Bốn lần trong một buổi: `git checkout -q main thất bại — Your local changes would be overwritten` |
| **Vì sao đây là ngõ cụt** | Mã chưa commit ấy là do CHÍNH Agent vừa viết hỏng. Thông báo bảo người dùng đi "commit or stash" nó, và không nói ra điều đó |
| **Đã sửa** | `start_module` dọn cây trước khi đổi nhánh — xóa được vì đây là kho SẢN PHẨM SINH, mọi thứ chưa commit là rác của lượt trước. Nhưng vẫn TRẢ VỀ danh sách đã xóa và in ra: dọn dẹp im lặng là cách một tệp ai đó sửa tay biến mất mà không ai biết |

## SL-152 · LỆCH THẬT · Bước dọn thư viện cũ quét thư mục mà thư viện không nằm ở đó

| | |
|---|---|
| **Cách tìm** | `eaa gen drv_imu` ngày 02/09: bài kiểm báo `Expected ~0.0183, got 0.0`. Con số ấy đúng với mã HÔM TRƯỚC. `libdrv_imu.so` mang dấu thời gian 23:16 ngày 01/09, trong khi lượt chạy là 06:0x ngày 02/09 |
| **Cơ chế** | Cổng `unittests` có sẵn `_don_san_pham_dich`, kèm chú thích dài đúng về vì sao nó cần thiết. Nó quét `tests_dir`. Lệnh dịch trong bài kiểm ghi `-o ./libX.so`, và `.` của tiến trình pytest là `work_dir`. Hai thư mục khác nhau — nên trong suốt thời gian tồn tại, bước dọn chưa xoá được một tệp nào của thứ nó sinh ra để chặn |
| **Vì sao đắt** | Một lượt sinh + ba vòng tự sửa, bốn lượt gọi mô hình, đi vá một sai lệch mà mã đang sửa không gây ra. Và cổng KHÔNG sai theo cách nhìn thấy được: nó đỏ, chỉ là đỏ vì nhị phân cũ |
| **Chiều nguy hơn** | Cùng cơ chế ấy làm cổng XANH trên mã không dịch nổi, nếu bài kiểm nuốt lỗi dịch — đúng cái chú thích của hàm đã cảnh báo |
| **Đã sửa** | Quét cả `work_dir`, MỘT TẦNG. Không đệ quy: `work_dir/build/` là sản phẩm của cổng dịch chéo chạy trước và của `eaa build` chạy sau; quét đệ quy là cổng này đi phá bằng chứng của cổng khác |
| **Bài canh** | `tests/test_tc116_don_thu_vien_cu_dung_cho.py` — 5 bài |

## SL-153 · LỆCH THẬT · Bài kiểm tự bỏ qua chính nó được đọc thành ĐẠT

| | |
|---|---|
| **Cách tìm** | Bài kiểm sinh cho `drv_imu` mở đầu bằng `if not os.path.exists(lib): pytest.skip("Library not found")`. Câu ấy biến đúng cái hỏng cổng phải bắt — mã không dịch được nên không có thư viện — thành một lượt chạy màu xanh |
| **Cơ chế** | `dat = returncode == 0`, và pytest thoát 0 cho một lượt chỉ toàn `skipped` |
| **Vì sao là lỗ thứ hai chứ không phải hệ quả của SL-152** | Hai chỗ hở ngược chiều nhau và cùng dẫn tới một chỗ: có thư viện cũ thì cổng chấm nhầm bằng nó (SL-152); không có thì cổng bỏ qua và báo đạt (SL-153). Bịt một chỗ là mở chỗ kia |
| **Ý đã có sẵn** | Cổng đã nói đúng câu ấy cho trường hợp KHÔNG CÓ test nào: *"chưa có gì để chạy" không phải là "đã kiểm chứng"*. Bỏ qua là đúng trường hợp ấy, chỉ khác ở chỗ tệp test có tồn tại |
| **Đã sửa** | `skipped > 0` → cổng KHÔNG ĐẠT, kèm tên bài và lý do bỏ qua để vòng tự sửa biết sửa gì. Cổng không phân biệt được "bỏ qua vì không liên quan" với "bỏ qua vì thứ cần kiểm không tồn tại", và giữa hai cách đọc chỉ một cách an toàn |
| **Bẫy đi kèm** | Cờ `-r` của pytest THAY THẾ mặc định chứ không cộng thêm. `-rs` một mình xoá luôn dòng `FAILED` — đổi một cổng nói rõ tên bài kiểm hỏng thành một cổng chỉ nói rằng có cái gì đó hỏng. Phải là `-rfEs` |
| **Bài canh** | `tests/test_tc117_bo_qua_khong_phai_da_kiem.py` — 5 bài |

## SL-154 · LỆCH THẬT · Vòng sinh mã của module này viết đè module đã merge

| | |
|---|---|
| **Cách tìm** | `AttributeError: dlsym(i2c_init): symbol not found`. `eaa gen drv_imu` trả về `src/drv_i2c.c` ở CẢ BA vòng tự sửa, mỗi lần viết lại từ đầu, xoá mất bốn hàm công khai của một module đã merge từ hôm trước |
| **Mô hình không làm sai lời nó được dặn** | Cổng `unittests` chạy CẢ thư mục test; báo cáo lỗi nó nhận được mang tên `tests/test_drv_i2c.py`; nó đi sửa chỗ được chỉ |
| **Chỗ hở** | `write_artifact` chặn đường dẫn THOÁT RA NGOÀI thư mục làm việc — và chỉ thế. Bên trong thư mục ấy thì tệp nào cũng ghi được. Danh sách `output_files` có tồn tại, nhưng nó chỉ đi vào một câu trong prompt: *"Tệp cần sinh: …"*. Lại là một luật sống trong lời dặn |
| **Bất biến đặt ra** | **Mã đã merge chỉ đổi qua vòng sinh của CHÍNH module đó.** Mỗi tệp trên nhánh chính đã qua một lượt review G3 mang tên một module; một lượt sinh cho module khác viết đè lên nó là xoá quyết định ấy mà không ai bấm nút gì |
| **Ranh giới** | Chặn theo "đã có trên nhánh chính", KHÔNG theo "ngoài danh sách tệp cần sinh". Một module có quyền thêm tệp phụ của chính nó, và tệp chưa merge thì chưa là tài sản của ai. Một cổng hay báo nhầm sớm muộn cũng bị tắt đi |
| **Đã sửa** | `Orchestrator.khoa_pham_vi_tep` chạy ngay sau MỖI lượt gọi mô hình — cả lượt sinh đầu lẫn từng vòng vá — và lọc TRƯỚC bước gộp bản vá. Danh sách cho phép sinh từ chính `tep_can_sinh`, cùng hàm viết câu trong prompt. Tệp bị bỏ được NÊU TÊN vào nhật ký từng vòng |
| **Còn nợ** | Nguyên nhân gốc chưa đụng tới: cổng `unittests` của module M báo lỗi bài kiểm của module N như thể là lỗi của M. Bộ lọc chặn được hậu quả, không chặn được việc vòng tự sửa đốt lượt gọi cho một cổng nó không sửa được |
| **Bài canh** | `tests/test_tc118_khong_ghi_de_module_da_merge.py` — 12 bài |

## SL-155 · LỆCH THẬT (×2) · Bộ đếm token sai cả hai chiều, và chính nó khoá công việc lại

| | |
|---|---|
| **Cách tìm** | `eaa gen drv_imu` bị chặn: *"215.015 / 120.000 (179,2%)"*. Chạy `eaa budget tokens` ngay sau đó đọc ra **430.030** cho cùng một module — đúng gấp đôi, sau đúng một lượt chạy KHÔNG gọi mô hình lần nào |
| **Chiều thổi phồng** | `spent_tokens` cộng mọi dòng KPI có cột token khác 0. Nhật ký có ba loại dòng CHÉP LẠI con số đã đếm: `gate_request` mang token của artifact cuối (truy vết, cùng một lượt gọi); `module_start` khi sắp chạm trần và `handoff` khi vượt trần mang TỔNG TÍCH LŨY mà chính phép kiểm ấy vừa tính. Hai dòng sau biến bộ đếm thành cái bơm tự thổi |
| **Ratchet** | Mỗi lần chạy bị chặn lại ghi một dòng `handoff` mang cả tổng, nên lần sau đọc ra gấp đôi. Bị chặn một lần là vĩnh viễn không quay lại được: càng thử càng vượt xa |
| **Chiều đếm sót** | Chỉ lượt sinh ĐẦU ghi token vào KPI. Mỗi vòng vá gọi mô hình rồi không ghi gì. `drv_imu` có **26** lượt gọi trong `llm_calls.jsonl` và **13** dòng trong `kpi_log.csv` |
| **Số thật** | 193.292 token / 26 lượt (đọc từ `llm_calls.jsonl`). Bộ đếm báo 430.030, rồi sau khi bịt chiều thổi phồng báo 105.385. Không con số nào của nó từng đúng |
| **Vì sao đây là lỗi tệ nhất trong bốn lỗi cùng buổi** | Ba lỗi kia làm hỏng một lượt chạy. Lỗi này khoá cả module lại, và lối thoát duy nhất hệ thống chỉ ra — nới trần tại G1 — là đi sửa một ràng buộc đang đúng vì một con số đo sai |
| **Đã sửa** | `spent_tokens` chỉ cộng những sự kiện ứng với một lượt gọi THẬT (`SU_KIEN_TINH_TIEN`), và `_va_loi` ghi token của lượt vá. Số đo giờ dựng lại được từ chính các lượt gọi |
| **Còn nợ** | Token của những vòng vá ĐÃ CHẠY không có trong `kpi_log.csv` và sẽ không được thêm vào: nhật ký KPI là bằng chứng append-only cho Chương 3, bịa dòng vào đó để số đẹp lên là đúng thứ nó sinh ra để chặn. `drv_imu` vì thế vẫn hiện 105.385 thay vì 193.292 — chênh lệch ghi ở đây |
| **Bài canh** | `tests/test_tc119_dong_tom_tat_khong_duoc_dem_lai.py` — 7 bài, trong đó một bài chạy trọn vòng lặp chuẩn với MockLLM rồi đối chiếu số bộ đếm đọc ra với tổng token mô hình thật sự trả về |

## SL-156 · LỆCH THẬT · Vòng thử lại bỏ trống đúng cái hay đứt nhất

| | |
|---|---|
| **Cách tìm** | Một lượt `eaa gen drv_imu` chết bằng đúng một dòng: `Không lắp ráp hoặc không sinh được mã: IncompleteRead(0 bytes read)` |
| **Cơ chế** | Vòng thử lại của adapter phủ ba nhánh: `HTTPError` (máy chủ bảo thử lại), `URLError` (không nối được), `TimeoutError` (chờ quá lâu). `IncompleteRead`, `RemoteDisconnected`, `ConnectionReset` không thuộc nhánh nào — chúng là `http.client.HTTPException`, không phải lỗi của `urllib` |
| **Vì sao đúng chỗ này đau** | Ba nhánh có sẵn phủ *không nối được* và *máy chủ từ chối*. Cái còn trống là **nối được, gửi được, rồi đường truyền chết khi câu trả lời đang về** — dạng hỏng hay gặp nhất với lượt gọi dài, và lượt sinh mã là lượt gọi dài nhất trong hệ |
| **Thử lại có đúng không khi mỗi lượt gọi đều tính tiền** | Có. Phản hồi đã đứt thì không còn gì dùng được — lượt gọi ấy đã mất tiền rồi. Không thử lại chỉ đổi "mất một lượt" thành "mất một lượt VÀ hỏng cả lượt chạy" |
| **Đã sửa** | Bắt `http.client.HTTPException` và `ConnectionError` vào cùng nhánh backoff với `URLError`. Đặt SAU `URLError` vì `URLError` cũng là `OSError` và có thông điệp riêng đã đúng |
| **Bài canh** | `tests/test_tc120_dut_giua_chung_van_thu_lai.py` — 7 bài, ba dạng đứt × (thử lại được / hết lượt) + một bài canh khoá API không lọt ra trong thông báo mới |

## SL-157 · LỆCH THẬT · Quy trình đòi đưa module về `todo` mà không có lệnh nào làm được

| | |
|---|---|
| **Cách tìm** | `eaa gen drv_i2c` → *"Module 'drv_i2c' đã merge. Sinh lại thì đưa nó về trạng thái todo trước."* `eaa plan` có propose/accept/add/list/order — không có lệnh nào đặt lại trạng thái |
| **Vì sao đây là ngõ cụt** | Lối duy nhất còn lại là sửa tay `project_state.json`: đúng cái tệp có khoá, có ghi nguyên tử, và có TC-03 canh nó không bị sửa ngoài luồng. Câu thông báo đúng, chỉ thiếu mất chỗ làm việc ấy |
| **Cùng họ với** | SL-13x (commit 624537f, "Quy trình đòi một thứ chính nó không sinh ra"). Lần này ở máy trạng thái backlog thay vì ở cổng |
| **Đã sửa** | `eaa plan reopen <module> --reason ...`. Bắt buộc kèm lý do vì mở lại mã đã merge là gỡ một quyết định G3 đã có người bấm; lý do vào Error Ledger nên lịch sử trả lời được câu "vì sao mã đã duyệt bị viết lại" |
| **Không nới lỏng gì** | Module quay về `todo` rồi phải đi lại TRỌN vòng lặp chuẩn, qua đủ cổng, rồi qua G3 một lần nữa. Mã trên nhánh chính giữ nguyên cho tới lúc đó |
| **Bẫy gặp ngay lần chạy đầu** | Bản đầu đổi trạng thái TRƯỚC rồi ghi ledger sau. Ledger từ chối phân loại `reopen` (không có trong danh mục), và để lại một module đã mở lại mà không dòng nào nói vì sao. Nay: kiểm (chỉ đọc) → ghi lý do → mới đổi trạng thái. Việc cuối cùng phải là việc KHÔNG hỏng được |

## SL-158 · LỆCH THẬT · Nhánh làm việc không mọc từ `main` khi sinh LẠI

| | |
|---|---|
| **Cách tìm** | Ngay lần đầu dùng `plan reopen`: sinh lại `drv_i2c` chạy trên `feature/drv_i2c` mở từ trước khi `drv_stepper` merge. `main` có bốn tệp kiểm, cây làm việc có ba — thiếu `tests/test_drv_stepper.py` |
| **Cơ chế** | `start_module` gọi `checkout(branch, create=True)`. Nhánh chưa có thì tạo mới từ `main` — đúng. Nhánh ĐÃ CÓ thì chỉ nhảy sang, và nó đứng yên từ lần sinh trước |
| **Hậu quả** | Cổng `unittests` báo ĐẠT trên một bộ kiểm thiếu hẳn một module đã merge. Cùng họ với SL-152 (chấm bằng nhị phân cũ) và SL-153 (bỏ qua đọc thành đạt): **cổng xanh vì nó không chạy thứ cần chạy**. Diff trong hồ sơ G3 cũng tính trên nền cũ |
| **Vì sao chưa lộ ra trước đó** | Chỉ cắn khi sinh LẠI một module ĐÃ có nhánh. Lần sinh đầu của mỗi module luôn mọc từ `main`, và `drv_imu` sinh lại nhiều lần trong lúc `main` đứng yên. Nó ra đời cùng lúc với `plan reopen` — luồng đầu tiên làm cho việc ấy thành thường xuyên |
| **Đã sửa** | `checkout -B <branch> main`: nhánh làm việc LUÔN đặt gốc ở nhánh chính hiện tại. Mất con trỏ nhánh của lần thử trước, KHÔNG mất bằng chứng — mỗi lượt chạy đã có hồ sơ riêng trong `.eaa/runs/`, `llm_calls.jsonl`, `kpi_log.csv` và nhật ký quyết định gate |
| **Bài canh** | `tests/test_tc121_nhanh_lam_viec_luon_moc_tu_main.py` — 4 bài, gồm một bài canh `main` không bị chạm |

## SL-159 · LỆCH THẬT (×2) · Ráp firmware dịch với đường tiêu đề không chứa tiêu đề

| | |
|---|---|
| **Cách tìm** | `eaa build` đầu tiên có module thật: `build/main.c:20:10: fatal error: app_balance.h: No such file or directory` |
| **Cơ chế** | `FirmwareAssembler` truyền `include_dir = source_dir` — thư mục `firmware/`. Bộ sinh mã ghi vào `firmware/src/`, và `_nguon_module` tìm tệp `.c` bằng `rglob` nên vẫn tìm ra. Kết quả: từng tệp module dịch được (chúng include theo đường tương đối cạnh nhau), còn `build/main.c` thì không — nó `#include "app_balance.h"` và `-I` trỏ vào thư mục KHÔNG chứa tệp ấy |
| **Vì sao im lặng bốn sprint** | `firmware.yaml` còn `modules: []` cho tới hôm nay. Chưa lượt ráp nào có module thật để lộ ra. Cùng loại với SL-134: hai chỗ mỗi chỗ đúng theo cách của nó, và chưa lần nào được đối chiếu |
| **Đã sửa** | `include_dir` lấy từ thư mục cha CHUNG của các nguồn ĐÃ TÌM ĐƯỢC, không ghim tên `src`: quy ước đặt tên là của bộ sinh mã, engine đọc được vị trí thật thì không cần đoán lại |
| **Lỗi thứ hai, lộ ra cùng lúc** | `parse.error_regex` của pack không khớp `fatal error:`. avr-gcc thoát 1 mà bộ parse không bắt được dòng nào, nên cổng báo *"lỗi CẤU HÌNH của Platform Pack — sửa parse.error_regex"*. Câu ấy chỉ đúng một nửa: regex đúng là thiếu, nhưng nguyên nhân thật là đường `-I`. Một cổng đoán sai nguyên nhân còn tệ hơn một cổng im lặng, vì nó gửi người đọc đi sai hướng |
| **Đã sửa** | `error_regex` nhận cả `(?:fatal\s+)?error:` |

## SL-160 · LỆCH THẬT · Hiệu chỉnh gộp hai đại lượng khác bản chất vào một bước

| | |
|---|---|
| **Cách tìm** | Robot lao thẳng đi ngay khi buông tay, dù mọi thứ khác đã đúng: trục, dấu, hằng số, chiều DIR, nhịp lấy mẫu |
| **Nhà cung cấp làm gì** | V3 đo **trôi con quay** mỗi lần bật máy trong `setup()`, còn **mốc gia tốc** là hằng số `acc_calibration_value` đo MỘT LẦN bằng chương trình riêng V0, lúc robot **thật sự đứng cân bằng trên hai bánh** |
| **Ta làm gì** | Đo cả hai cùng lúc, mỗi lần bật máy, ở tư thế TAY NGƯỜI đang giữ |
| **Vì sao sai** | Hai đại lượng khác bản chất. Trôi con quay đổi theo nhiệt độ nên PHẢI đo lại. Mốc gia tốc là HÌNH HỌC của robot — trọng tâm ở đâu so với trục bánh — nó không đổi giữa hai lần bật, và tay người không đo được nó: giữ cho "trông thẳng đứng" không phải điểm cân bằng thật |
| **Hậu quả kép** | (1) Ta tuyên bố một tư thế nghiêng là "không độ", nên robot đuổi theo một điểm cân bằng sai. (2) Cổng `\|góc\| < 0,5°` thêm vào để chặn việc bật PID quá sớm trở thành VÔ NGHĨA: `imu_calibrate_commit()` đặt góc về 0 nên điều kiện luôn đúng theo định nghĩa, cổng mở tức thì |
| **`self_balance_setpoint` không cứu được** | Nó dò lại điểm cân bằng ở tốc độ 0,0015 mỗi vòng — sửa lệch 1° mất ~2,7 giây, trong khi robot đã lao mất |
| **Cách sửa** | Tách hai bước: lúc bật máy chỉ đo trôi con quay; mốc gia tốc lấy từ `hardware_profile.yaml`, đo một lần bằng chẩn đoán kiểu V0. Lúc ấy cổng `±0,5°` mới đo được góc THẬT so với điểm cân bằng, và giai đoạn 5 bíp đổi nghĩa thành "giữ YÊN" thay vì "giữ THẲNG" |
| **Đã sửa** | `ACCEL_BALANCE_OFFSET = -535` thành hằng số trong `drv_imu`, đo bằng DS-02 ngày 03/09 ở ±4 g (`accel_z_mean = -535`, độ lớn véc-tơ 8275 ≈ 1,010 g). Lúc bật máy chỉ còn đo trôi con quay: 500 mẫu `gyro_y`, robot đứng YÊN chứ không cần THẲNG |
| **Đã kiểm trên bo** | 03/09, firmware `80ec03d0d4` — robot đứng cân bằng thật trên sàn, thả tay không đổ. Đây là lần đầu cổng `\|góc\| < 0,5°` đo được góc THẬT, vì mốc không còn do tay người định nghĩa |

## SL-161 · LỆCH THẬT · Trần lớp `project_rules` chặn mười lần trong một buổi

| | |
|---|---|
| **Cách tìm** | Mười lần liên tiếp: *"project_rules: 1248 token / ngân sách 1200"*, mỗi lần một vòng đi lại trong khi người dùng ngồi chờ ở bàn thí nghiệm |
| **Số liệu** | Prompt tổng dùng ~3.200/8.000 — hơn nửa trần tổng bỏ trống |
| **Vì sao đây là SL-147 lặp lại** | Kích thước lớp này do **số bài học rút từ phần cứng** quyết định. Mỗi lỗi bắt được trên bo lại thêm một dòng ràng buộc vào `prompts/<module>.md`. Đó là một đại lượng CHỈ TĂNG, và một trần cố định đặt lên nó là một trần sẽ bị chạm — bị chạm đúng lúc ta học được nhiều nhất |
| **Khác SL-147 ở đâu** | Lớp vá THAY CHỖ lớp task nên không cạnh tranh với ai; `project_rules` thì có cạnh tranh. Nên cách sửa không phải "cho dùng chỗ trống" mà cần cân nhắc lại bảng chia |
| **Không nới số** | Nới bừa một con số lúc đang gấp là đúng cái sai mà SL-147 đã dạy — nên chỗ sửa KHÔNG phải bảng ngân sách |
| **Chỗ sai thật** | Phần của một lớp là cách chia công bằng **khi có tranh chấp**. Trần TỔNG còn trống nghĩa là chưa có tranh chấp, nên chặn ở đó là chặn một tình huống giả định. Câu biện hộ của phép kiểm — *"một prompt quá dài luôn có thủ phạm cụ thể"* — chỉ đúng khi prompt QUÁ DÀI |
| **Đã sửa** | Vượt phần lớp mà tổng còn chỗ: **ghi vào `Prompt.over_share` và đi tiếp**, không ném. Tổng thật sự vượt thì ném y như cũ, kèm nguyên danh sách lớp thủ phạm. Không đổi một con số nào trong `LAYER_BUDGETS` |
| **Không im lặng** | `canh_bao_luoc` in ra lớp dùng quá phần, vào nhật ký từng vòng. Im lặng ở đây là cách một lớp phình dần tới lúc lấn chỗ thật mà không ai thấy quá trình ấy |
| **Ba bài kiểm cũ phải đổi** | Chúng dựng cảnh "chật" bằng phần của LỚP trong khi trần tổng thoải mái — tức canh chính hành vi vừa bỏ. Nay dựng bằng trần TỔNG. Kho đã học đúng điều này một lần ở SL-136, và ba bài này còn sót |
| **Bài canh** | `tests/test_tc122_phan_lop_khong_chan_khi_con_cho.py` — 7 bài, gồm bài canh việc chỉ đích danh thủ phạm KHÔNG mất đi khi tổng thật sự vượt |

## SL-162 · LỆCH THẬT · Vòng tự sửa đốt cả ba lượt vào lỗi của module khác

| | |
|---|---|
| **Cách tìm** | Sinh lại `logic_pid` ngày 03/09. Bản sinh tự bỏ tham số `is_running` khỏi `pid_compute`, làm `test_app_balance.py` — bài kiểm của một module ĐÃ MERGE — không dịch nổi: `src/app_balance.c:125: too many arguments to function call, expected 2, have 3` |
| **Chuyện gì xảy ra** | Cổng `unittests` đỏ. Vòng tự sửa mở, chạy đủ ba lượt, cả ba đều vá vào `logic_pid` — tệp DUY NHẤT nó được phép viết, và là tệp không có lỗi nào. Ba lượt gọi mô hình đổi lấy không gì cả, rồi module vẫn bàn giao cho người |
| **Vì sao vòng vá không tự thoát được** | Vì nó không biết. Cổng gộp mọi thất bại vào MỘT `ToolError` không mang `file`, nên phía trên chỉ đọc được *"có lỗi"*, không đọc được *"lỗi ở đâu"*. Với chừng ấy thông tin thì vá mù ba lượt là hành vi hợp lý nhất nó làm được |
| **Chỗ sửa thật nằm ở CỔNG** | Không phải ở vòng vá. Thêm luật cho vòng vá mà cổng vẫn không quy được lỗi về tệp thì luật ấy không có dữ liệu để chạy. `unittests` nay đọc dòng tóm tắt `FAILED <tệp>::<bài>` và `ERROR <tệp>` của pytest vào `metrics["failing_files"]` — `ERROR` là dạng lỗi THU THẬP, đúng dạng mà lỗi biên dịch chéo module hiện ra |
| **Nửa còn thiếu của SL-154** | Khoá phạm vi tệp chặn module này ghi đè tệp module kia. Nhưng module sinh lại vẫn chỉ viết tệp của CHÍNH NÓ — mà đổi một chữ ký trong header của mình là đủ làm module đã merge không dịch được. Quyền ghi bị canh, hợp đồng gọi thì không |
| **Đã sửa** | Hạng dừng thứ ba trong `run_module`, cạnh `env_error` và `config_error`: mọi tệp đỏ đều ngoài `tep_can_sinh(module_id)` → `blocked` ngay, không mở vòng vá, kèm câu chỉ thẳng vào nghi phạm thường gặp nhất là đổi chữ ký header |
| **Ngả về phía VÁ khi không chắc** | Chặn nhầm thì dừng cả dây chuyền và đòi người; vá nhầm thì tốn lượt gọi. Hai hạng sai không ngang giá. Nên chỉ dừng khi quy được MỌI thất bại về tệp VÀ mọi tệp đều ngoài phạm vi; quy được một phần, hoặc không quy được, thì vòng vá vẫn mở |
| **Chưa sửa** | Việc đổi chữ ký vẫn chỉ bị bắt GIÁN TIẾP, qua một module khác tình cờ gọi tới. Module chưa ai gọi thì đổi chữ ký vẫn lọt. Chỗ sửa thẳng: so khai báo trong header cũ trên `main` với header mới ngay khi sinh xong. Hiện đang vá bằng cách ghi chữ ký vào `prompts/logic_pid.md` — đó là lời dặn, và lời dặn chỉ giữ được đúng một module |
| **Bài canh** | `tests/test_tc123_loi_ngoai_pham_vi_khong_mo_vong_va.py` — 12 bài, trong đó 4 bài canh chiều ngả về phía vá và 1 bài canh việc không biến dòng `ERROR` do người viết test in ra thành tên tệp |

## SL-163 · BỔ SUNG · Không có gì canh hợp đồng gọi của một module sinh lại

| | |
|---|---|
| **Cách tìm** | Nửa còn lại của SL-162. SL-162 chặn được vòng vá đốt lượt cho lỗi module khác, nhưng việc ĐỔI CHỮ KÝ vẫn chỉ bị bắt **gián tiếp** — qua một module khác tình cờ gọi tới. Module chưa ai gọi thì đổi chữ ký lọt sạch, và nó sẽ lọt tới đúng lúc có người viết module gọi tới: muộn nhất có thể |
| **Vì sao SL-154 không phủ chỗ này** | `khoa_pham_vi_tep` canh QUYỀN GHI — module này không viết được tệp của module kia. Nhưng module sinh lại vẫn chỉ viết tệp của CHÍNH NÓ, và đổi một chữ ký trong header của mình là đủ làm mọi module đã merge gọi tới nó không dịch được. Quyền ghi bị canh, hợp đồng gọi thì không |
| **Đã thêm** | `eaa/contract.py` — đọc khai báo hàm từ header, so bản vừa sinh với bản đang nằm trên `main`. Hai hạng vi phạm: **mất** một hàm, và **đổi** chữ ký. Thêm hàm mới KHÔNG phải vi phạm: mở rộng là việc bình thường của một lượt sinh lại, chỉ thu hẹp hay đổi mới là phá |
| **Vào đường VÁ, không vào đường CHẶN** | Khác SL-162 có chủ ý. Lỗi ngoài phạm vi là thứ vòng vá KHÔNG có quyền sửa nên phải chặn; còn đây là mã của chính nó và nó sửa được — thêm lại một tham số đã bỏ là một lượt vá bình thường. Chặn ở đây là đòi người làm hộ việc máy làm được |
| **Đi TRƯỚC chuỗi cổng** | Không phải để tiết kiệm thời gian. Một header đã thu hẹp làm cổng dịch đỏ ở tệp của module KHÁC, và thông điệp lúc ấy nói về `app_balance.c:125` chứ không nói về cái vừa bị đổi. Cùng một lỗi, hai câu — và chỉ một câu chỉ đúng chỗ |
| **Bỏ tên tham số trước khi so** | Đổi tên tham số không đổi cách gọi. So cả tên thì cổng này sẽ kêu ở mỗi lần đổi tên, và một cổng hay báo nhầm sớm muộn cũng bị tắt đi — lúc ấy nó không bảo vệ được gì nữa. Cùng lý lẽ với cổng an toàn của `eaa tool` |
| **Ranh giới, nói thẳng** | Đây là bộ so KHAI BÁO, không phải bộ dịch C. Không hiểu macro, không mở `#include`. Với con trỏ hàm và mảng thì so **nguyên văn** thay vì tách tên — tức có thể kêu thừa ở đó. Ngả về phía kêu thừa là có chủ ý ở những chỗ hiếm; ở chỗ thường (đổi tên tham số) thì tuyệt đối không kêu |
| **Bài canh** | `tests/test_tc124_hop_dong_goi_khong_duoc_doi.py` — 16 bài, trong đó 4 bài canh chiều "đừng kêu nhầm" và 1 bài canh việc `unsigned int` không bị cắt cụt thành `unsigned` |

## SL-164 · DỜI CHỖ · Docstring `eaa/agent.py` mô tả một bản `TOOLBOX` không còn tồn tại

| | |
|---|---|
| **Cách tìm** | Đọc lại danh mục để viết mục README về tầng hội thoại. Docstring khẳng định `TOOLBOX` **không chứa** `flash`, `doctor --fix`; danh mục thật thì có cả ba (`tool run` nữa) |
| **Bất biến KHÔNG bị phá** | Kiểm ngay: `gate approve/reject`, `flash approve`, `doctor approve`, `tool approve`, `skill approve`, `tune`, `rollback`, `diagnose run`, `endurance` — **không cái nào** trong danh mục. Năm Human Gate vẫn không thể bị vượt |
| **Thiết kế đã đổi, lời khai thì không** | Ranh giới dời từ *"cấm lệnh nguy hiểm"* sang *"cấm lệnh DUYỆT"*. `flash`, `doctor --fix`, `tool run` được vào danh mục vì cả ba tự dừng khi chưa có quyết định của người — `flash` đòi bản duyệt neo vào băm nội dung ảnh, `doctor --fix` chỉ chạy lệnh cài đã duyệt, `tool run` chỉ chạy công cụ `approved` |
| **Vì sao cách chia mới TỐT HƠN** | Nó không phụ thuộc vào việc liệt kê đủ. Danh sách "lệnh nguy hiểm" dài thêm mỗi lần có tính năng mới, và một danh sách phải nhớ cập nhật là một danh sách sẽ sót. Danh sách lệnh DUYỆT thì đóng: mỗi cổng đúng một lệnh, và thêm cổng mà quên thêm lệnh duyệt thì cổng ấy không dùng được — không ai quên |
| **Vì sao vẫn phải sửa** | Docstring là thứ kỹ sư tiếp theo tin. Một tệp khai sai về chính mình sẽ khiến người đọc hoặc tưởng có lỗ hổng và đi bịt cái không hở, hoặc tưởng đã có rào ở chỗ chưa có. Đây đúng dạng lỗi hay gặp nhất của kho này: **mã lệch với lời chính nó khai** |
| **Đã sửa** | Viết lại docstring theo ranh giới thật, kèm mục *"Ranh giới nằm ở việc DUYỆT, không ở việc LÀM"* nói rõ vì sao ba lệnh kia được vào |
| **Bài canh** | Thêm 2 bài vào `tests/test_tc61_chat.py`: một bài liệt kê thẳng tên sáu lệnh duyệt và đòi chúng vắng mặt; một bài canh **chiều ngược** — ba lệnh `flash`/`doctor --fix`/`tool run` phải CÒN đó và phải tự nói ra rằng chúng đòi duyệt trước, để người sau tưởng là lỗ hổng mà gỡ đi thì bài kiểm đỏ và dẫn về đúng lý lẽ |
| **Vì sao hai đường độc lập** | Bài canh cũ (TC-61c) đọc danh sách từ PROMPT rồi đối chiếu danh mục. Bài mới viết thẳng tên. Một prompt bị sửa không làm cả hai cùng mù |

---

## SL-165 · BỔ SUNG · Đứng trong thư mục dự án mà vẫn phải khai lại tên dự án

| | |
|---|---|
| **Cách tìm** | Người dùng đối chiếu với Claude Code: mở công cụ trong thư mục dự án thì công cụ biết đó là dự án nào. Ở đây `eaa status` chạy ngay trong `projects/disco_f469` vẫn báo *"Có nhiều dự án — chỉ rõ bằng --project hoặc EAA_PROJECT"* |
| **Lệch với cái gì** | FR-PLT-03 dự trù nhiều dự án song song, và `resolve_project` cài đúng ba đường: tham số → biến môi trường → dự án DUY NHẤT. Đường thứ ba tắt ngay khi kho có dự án thứ hai, tức là tắt đúng lúc FR-PLT-03 bắt đầu có nghĩa |
| **Vì sao là lỗi chứ không phải bất tiện** | Nó bắt khai một thứ hệ thống **nhìn thấy được**. Mỗi lần khai lại là một lần khai nhầm được, và một lệnh sinh mã chạy nhầm dự án ghi mã theo sơ đồ chân của bo khác — hỏng im lặng, đúng hạng nguy hiểm nhất của kho này |
| **Đã sửa** | Thêm bậc **vị trí** vào giữa: tham số → biến môi trường → **thư mục đang đứng** → duy nhất. `du_an_chua_thu_muc()` đi ngược lên như `git` tìm `.git`, nhận theo dấu hiệu `project_state.json` **hoặc** `constraints.yaml` |
| **Vì sao hai dấu hiệu chứ không một** | `eaa brief` dựng `constraints.yaml` trước, `eaa init` mới ghi Project State. Nhận theo một tệp thì đúng quãng người dùng cần nhất — giữa hai lệnh ấy — lại là quãng không nhận ra |
| **Vì sao vị trí KHÔNG đặt trên biến môi trường** | Cái được gõ ra thắng cái được suy ra. Một biến đã export là một câu người dùng đã nói thành lời; vị trí thư mục thì không |
| **Chỗ dễ hỏng và cách chặn** | Hai thứ ấy chỉ về hai dự án khác nhau là chuyện sẽ xảy ra thật (export một lần trong `.zshrc`, rồi `cd` sang dự án khác). Chọn im lặng ở đây là cách một buổi làm việc đi nhầm dự án mà không ai biết — nên khi lệch, hệ **in cảnh báo ra stderr** kèm đúng hai cách sửa. Không lệch thì không in: một cảnh báo bắn cả lúc không có gì lệch là một cảnh báo sẽ bị bỏ qua |
| **Bài canh** | `tests/test_tc125_du_an_theo_thu_muc.py`, 9 bài: nhận từ gốc dự án và từ thư mục con; chỉ có `constraints.yaml` cũng nhận; gốc kho **không** bị nhận nhầm; `--project` và `EAA_PROJECT` đều thắng vị trí; lệch thì phải cảnh báo, không lệch thì phải im |

---

## SL-166 · BỔ SUNG · Kho tri thức chỉ đọc ra được từ đường sinh mã

| | |
|---|---|
| **Cách tìm** | Câu hỏi của người dùng: *"khi người dùng hỏi thì Agent có biết tìm trong RAG, Graph để trả lời không"*. Truy ngược chỗ gọi: `eaa/rag.py` chỉ được `composer.py` (ghép prompt sinh mã) và `goldenset.py` (đo chất lượng truy xuất) gọi tới. Không lệnh nào khác, và **không mục nào trong `TOOLBOX`** |
| **Hệ quả** | Ở tầng hội thoại, trích đoạn đã qua G2 nằm trên đĩa mà không có đường lấy ra. `datasheet list` chỉ liệt kê mã và trạng thái, không trả nội dung. Nên một câu hỏi kỹ thuật chỉ còn hai lối: **trí nhớ mô hình**, hoặc **ra web** — cả hai đều đi vòng qua đúng thứ đã có người đối chiếu với bản gốc |
| **Vì sao nặng hơn nó trông** | Toàn bộ giá trị của G2 nằm ở chỗ một người đã đọc bản gốc và chịu trách nhiệm. Nếu đường hỏi-đáp không chạm được vào kết quả ấy thì công duyệt G2 bị bỏ phí ở đúng chỗ người dùng tương tác nhiều nhất, và câu trả lời tụt xuống hạng chưa kiểm mà **không có gì nói ra điều đó** |
| **Đã sửa** | `rag.search_chunks()` — truy xuất theo MỘT CÂU HỎI TỰ DO, giữ nguyên hai tầng: đồ thị chỉ đích danh trước (chỉ khi câu hỏi gọi tên một module của dự án), BM25 lấp sau với ngưỡng độ phủ. Lệnh `eaa recall "<câu hỏi>"` và một mục `recall` trong `TOOLBOX` |
| **Chỉ chunk ĐÃ DUYỆT** | Dùng chung `_kho_van_ban()` với `select_chunks` để luật *"chỉ `active()`"* được phát biểu đúng một lần. Chunk `proposed` **được nêu ra** trong đầu ra — kèm câu nói rõ nó chưa tính vào kết quả — vì im lặng về nó khiến người dùng kết luận "kho không có" trong khi thứ họ cần nằm sau đúng một lần bấm G2 |
| **Sửa kèm: mẫu số của độ phủ** | Ngưỡng độ phủ được chỉnh cho câu truy vấn do MÁY dựng (toàn tên thanh ghi). Với câu NGƯỜI hỏi, hư từ nuốt mất mẫu số: *"TWBR đặt bao nhiêu"* có 4 từ, 3 từ không nằm trong tài liệu kỹ thuật nào, nên trích đoạn nói đúng về `TWBR` chỉ đạt 1/4 và bị loại. Nay mẫu số **chỉ tính từ có mặt đâu đó trong kho** — một từ không trích đoạn nào chứa thì không trích đoạn nào phủ được, để nó trong mẫu số là đặt điều kiện bất khả rồi phạt mọi ứng viên. Ngưỡng 1/3 giữ nguyên; thứ đổi là *đếm cái gì* |
| **Thứ tự dạy lại cho mô hình** | Bảng *"khi thiếu thông tin"* trong prompt chèn `recall` thành bậc 2, trước `research`: một trích đoạn đã qua G2 là thứ đã có người đối chiếu với bản gốc, còn một trang web mới tải thì chưa. Ra web trước khi tra kho là đổi nguồn đã kiểm lấy nguồn chưa kiểm |
| **Không mở thêm quyền** | `recall` là lệnh chỉ đọc. `datasheet add` vẫn **không** có trong danh mục — nạp tri thức và chọn trang vẫn là việc của người (G2, AIS §4.1) |
| **Sửa kèm: `resolve` khai sai về chính nó** | `resolve` nằm ở nhóm "chỉ đọc" của `TOOLBOX` trong khi bậc 3 của nó dựng chunk đề xuất trên đĩa và ghi sổ đếm vòng tìm. Đã chuyển sang nhóm **có ghi** và nêu rõ `--web` trong mô tả — trước đó mô hình không có cách nào biết bậc 3 tồn tại, nên năng lực tự ra web nạp tài liệu **có trong mã mà không bao giờ được gọi** |
| **Bài canh** | `tests/test_tc126_recall_kho_tri_thuc.py`, 10 bài: hai tầng đúng thứ tự; tên module khớp theo TỪ chứ không chuỗi con (`drv_i2c` không kéo theo `drv_i2c_mpu6050`); chunk `proposed` không lọt; ngưỡng độ phủ vẫn chặn câu hỏi không liên quan; `recall` đứng trước `research` trong bảng thứ tự; và bài canh chiều ngược — thêm lệnh **không** được thành thêm quyền |

---

## SL-167 · BỔ SUNG · Lời gọi liên module bị đánh rơi — hỏng im lặng theo đúng nghĩa đen (N-910)

| | |
|---|---|
| **Cách tìm** | Rà soát bảng năng lực 04/09 (`docs/RA_SOAT_NANG_LUC_04_09.md`). Mục N-910 mới thêm nêu chuyện đã xảy ra: một vòng vá làm `app_init()` mất bốn lời gọi khởi tạo driver, firmware **câm hoàn toàn**, mà **33 bài kiểm vẫn xanh** |
| **Vì sao không cổng nào đỏ** | Vì không có gì sai. Mã dịch được, phân tích tĩnh sạch, bài kiểm đơn vị gọi thẳng hàm cần kiểm nên không đi qua `app_init()` lần nào. Mã chỉ đơn giản là không làm gì cả — và không có thông báo lỗi nào để đọc |
| **Nửa còn thiếu của SL-163** | `pha_vo_hop_dong` canh cái module này **HỨA** (chữ ký trong header của nó). Không gì canh cái nó **DÙNG**. Hai thứ hỏng theo hai kiểu và chỉ một kiểu đang có người canh |
| **Đã sửa** | `eaa/contract.py` thêm `than_ham()`, `loi_goi()`, `mat_loi_goi()`. Orchestrator dựng tập hàm công khai của module KHÁC từ `src/*.h` trên `main`, rồi so tập lời gọi liên module của bản đã merge với bản mới. Đi cùng đường VÁ với hợp đồng chữ ký |
| **Vì sao so ở tầm TỆP, không tầm HÀM** | Tách mấy lời gọi ra một hàm phụ rồi gọi hàm phụ ấy là tái cấu trúc ĐÚNG, và nó xảy ra thường. So ở tầm hàm sẽ kêu ở mỗi lần như thế — một cổng hay kêu nhầm sớm muộn cũng bị tắt đi, và lúc ấy nó không bảo vệ được gì nữa. Ở tầm tệp thì lời gọi dời chỗ không tính là mất; chỉ lời gọi **biến khỏi tệp** mới tính, và đó đúng là chuyện đã xảy ra |
| **Vì sao chỉ LIÊN MODULE** | Ba lần giới hạn, mỗi lần một lý do: hàm nội bộ mất đi thường là tái cấu trúc; hàm thư viện C không nằm trong header nào của dự án nên tự rơi ra; hàm công khai của chính module này đã có `pha_vo_hop_dong` canh ở tầng khai báo. Còn lại đúng một hạng — **một việc sang module khác không còn ai làm** |
| **Thông báo nêu tên chỗ mất** | *"`app_init()` không còn gọi `drv_imu_init()`"* chỉ đúng chỗ; *"thiếu `drv_imu_init`"* bắt người đọc đi tìm. Tra trong thân hàm của bản CŨ. Không tra được thì vẫn báo — im lặng vì thiếu nửa câu là đổi một lỗi thật lấy một dòng đẹp |
| **Hai lỗi riêng, không gộp** | Vi phạm chữ ký gắn `src/<m>.h`, lời gọi bị rơi gắn `src/<m>.c`. Gộp một dòng thì lớp quy lỗi về tệp của SL-162 chỉ còn quy được về một chỗ và nửa kia mất địa chỉ |
| **Ruột chuỗi phải bỏ trước khi đếm ngoặc** | Một dấu `{` trong chuỗi làm phép đếm lệch từ đó tới hết tệp, và hàm sau bị nuốt vào hàm trước — sai im lặng, không ném ngoại lệ nào. Có bài canh riêng |
| **Bài canh** | `tests/test_tc127_loi_goi_khong_duoc_danh_roi.py`, 33 bài. Chiều bắt: mất lời gọi, mất nhiều lời gọi (thứ tự ổn định), xoá cả hàm chứa nó, chú thích lại một lời gọi. Chiều **đừng kêu nhầm** (nhiều bài hơn, cố ý): dời sang hàm khác cùng tệp, gom vào hàm phụ, mất lời gọi nội bộ, mất lời gọi thư viện C, thêm lời gọi mới, viết lại cả tệp mà giữ đủ việc. Và luật "rỗng khi chưa có gì để so": module sinh lần đầu, kho chưa dựng, kho không đọc được — không cái nào được làm hỏng lượt sinh |

---

## SL-168 · BỔ SUNG · Bài kiểm xanh chưa phải bằng chứng — phép đo độ nhạy (N-909)

| | |
|---|---|
| **Cách tìm** | Rà soát bảng năng lực 04/09. Mục N-909 mới thêm, rút từ `DANH_GIA_NANG_LUC_AGENT §3.8` — giới hạn khó thấy nhất trong tám giới hạn |
| **Chuyện đã xảy ra** | Kỹ sư yêu cầu thêm bài canh *"trong vùng chết, điểm đặt phải đứng yên"*. Agent thêm `test_deadband_keeps_setpoint_steady`, bài ấy **đỏ ở vòng đầu, xanh sau khi sửa** — nhìn từ ngoài đúng hệt một bài kiểm làm đúng việc. Đọc kỹ: nó chạy 10 vòng, điểm đặt trôi 0,015, còn xa ngưỡng 5 của vùng chết. Nó **xanh cả với mã sai** |
| **Vì sao khó thấy hơn mọi dạng khác** | Khác §3.1 và §3.4: ở đó mô hình chỉnh đồ đo cho vừa mã, và cả hai để lại dấu vết đọc ra được — một hằng số bị đổi, một chú thích tự khai. Ở đây **không có gì bị chỉnh**. Bài kiểm trông đúng, tên đúng, và kết quả đúng ở đúng hai thời điểm cần đúng |
| **Đã sửa** | `eaa/sensitivity.py` — chạy lại bộ kiểm MỚI trên mã CŨ (bản vừa bị cổng đánh đỏ) trong một bản sao tạm. Xanh trên cả hai bản nghĩa là nó không chứng minh được gì về lần sửa vừa rồi |
| **Ranh giới, và ranh giới này quan trọng** | Phép đo KHÔNG nói bài kiểm đủ mạnh. Chính ca `deadband` vẫn đỏ trên mã cũ (vì lý do khác) nên nó sẽ QUA được phép đo. Bộ đo bắt hạng nhẹ hơn: bài kiểm hoàn toàn không phân biệt được gì. Nói rõ điều này trong docstring, vì một bộ đo tự nhận thay được người sẽ tái lập đúng cái sai nó sinh ra để chặn |
| **KHÔNG chặn — vào hồ sơ G3** | Bài học của chính ca ấy là *màu của bài kiểm không thay thế được việc đọc mã ở G3*. Kết quả đi vào nhật ký, vào KPI (`test_sensitivity`), và vào **đầu checklist G3** khi có bài không phân biệt được — nó là câu duy nhất trong hồ sơ nói rằng một màu xanh ở đây không có nghĩa |
| **Chỉ đo khi vòng vá đã chạy** | Chưa vá thì chưa có "bản mã sai đã biết" nào để so. Và chỉ đo khi có bài kiểm MỚI hoặc ĐỔI — phép đo tốn một lượt chạy pytest, không được tiêu vào lượt không có gì để đo |
| **Chuẩn hoá bằng cây cú pháp** | "Bài kiểm đã đổi" so bằng `ast.dump`, không bằng chuỗi. Thụt lề đổi, chú thích đổi, xuống dòng đổi — không cái nào đổi việc bài kiểm làm, và so chuỗi thì mọi lượt định dạng lại đều kéo theo một phép đo thừa |
| **Bản sao KHÔNG mang theo sản phẩm dịch** | `.so`, `.o`, `build/` bị lọc khỏi bản sao. Chép sang là dựng lại đúng cái bẫy SL-152: bộ kiểm dịch mã C thành thư viện rồi nạp bằng `ctypes`, còn thư viện của lần trước thì mã cũ không cần dịch nổi — phép đo sẽ đo nhị phân của bản MỚI trong khi tin rằng mình đang đo bản cũ |
| **KHÔNG ĐO ĐƯỢC khác ĐO ĐƯỢC VÀ ĐẠT** | Hai trường riêng (`do_duoc`, `khong_phan_biet`). Gộp lại là biến im lặng thành lời khẳng định — đúng hạng lỗi mà `eaa/confidence.py` sinh ra để chặn |
| **Bài canh** | `tests/test_tc128_do_nhay_bai_kiem.py`, 28 bài. Kèm kiểm ĐỘT BIẾN: bỏ luật lọc sản phẩm dịch → 1 bài đỏ; đảo thứ tự ghi mã cũ / bài kiểm mới → 1 bài đỏ. Và bài canh bản sao là BẢN SAO — thư mục làm việc thật không bị mã cũ ghi đè |

---

## SL-169 · LỆCH THẬT · Thang gỡ lỗi cài đặt là một thư viện không ai gọi (C5.1–C5.3, C5.5, C5.6, C5.9, C5.10)

| | |
|---|---|
| **Cách tìm** | `scripts/kiem_bang_nang_luc.py` — phép kiểm thứ tư: mã khai trong bảng có ai gọi không. `eaa/installerr.py` không được module nào trong `eaa/` hay `packs/` import |
| **Bảy dòng đứng trên một chỗ trống** | C5.1 phân loại lỗi, C5.2 thử lại có giãn, C5.3 đổi tham số, C5.5 đổi công cụ tương đương, C5.6 tự viết thay thế, C5.9 quay lui, C5.10 phân biệt lỗi công cụ với lỗi đầu vào — cả bảy khai ĐỦ, cả bảy chỉ được ra hàm cụ thể, và cả bảy đều đúng theo nghĩa "có mã, có test" |
| **Bảng đã tự mâu thuẫn mà không ai thấy** | Dòng C5.7 viết *"với lỗi cài đặt thì mỏng hơn vì C5.1–C5.5 còn trống"* trong khi cả năm dòng ấy đang đánh ĐỦ. Hai ô cạnh nhau nói ngược nhau, và không có gì kiểm nên nó sống được bốn ngày |
| **Chỗ hở thật** | `doctor._run_install` thử lại **mù hai lần** cho mọi thất bại rồi in đúng một câu: *"cài thất bại sau 2 lần — cài tay theo hướng dẫn của nhà phát hành"*. Một lỗi quyền được thử lại y hệt một lần rớt gói; một lỗi sai tên gói cũng vậy |
| **Đã sửa** | `_run_install` gọi `classify()` trên mọi lần trượt (kể cả timeout và `OSError`), thử lại **chỉ khi** `diagnosis.retryable` — tức chỉ lỗi MẠNG — với giãn cách `retry_delays()` 2s/4s/8s. Trượt hẳn thì in `InstallDiagnosis.render()`: loại lỗi, dấu hiệu nhận ra, **mức tin cậy**, thang gỡ đủ bậc |
| **Quay lui: NÊU chứ không CHẠY** | `rollback_command` suy lệnh gỡ cho **mọi bước đã chạy**, không chỉ bước trượt — bước 1 xong rồi thì máy đã đổi. Nhưng doctor không tự chạy: gỡ cũng là một lần đổi máy người dùng, và nó phải qua đúng cái cửa mà lệnh cài vừa đi qua (N-022 ở mức T2). Suy không ra thì im, không đoán — một lệnh gỡ đoán sai chạy với quyền quản trị tệ hơn hẳn việc không có lệnh gỡ nào |
| **Hàm nghỉ tiêm được** | `Doctor.sleep` mặc định `time.sleep`, bộ kiểm thay bằng một hàm ghi lại. Một phép giãn không đo được là một phép giãn sẽ lặng lẽ biến mất trong lần sửa sau |
| **Sửa kèm: ba chỗ cắt đầu ra đi hai chiều ngược nhau** | Nối đường gọi làm lộ ra một mâu thuẫn nằm im: `doctor._loi_cua_lenh` giữ 12 dòng **CUỐI** — và ghi đúng lý lẽ trong chú thích của nó — trong khi `InstallDiagnosis.render()` giữ 8 dòng **ĐẦU**, còn bậc "tra thông báo lỗi" đem **dòng đầu tiên** đi hỏi Internet. Đầu ra của trình quản lý gói mở màn bằng hàng chục dòng tải về rồi mới tới câu nói thật, nên cả hai chỗ sau đều đang lấy đúng phần vô nghĩa. Nay cả ba cùng giữ phần cuối |
| **Bài canh** | `tests/test_tc129_chan_doan_loi_cai.py`, 16 bài. Kèm kiểm ĐỘT BIẾN, cả ba đều bị bắt: bỏ điều kiện `retryable` → 3 bài đỏ; bỏ lời gọi `sleep` → 2 bài đỏ; cho doctor tự chạy lệnh quay lui → 3 bài đỏ |
| **Bài học rộng hơn** | Cột "bằng chứng" của bảng năng lực đòi chỉ ra được MODULE. Nó cần đòi thêm một thứ: chỉ ra được ĐƯỜNG GỌI. Phép kiểm ấy nay nằm trong `scripts/kiem_bang_nang_luc.py` và chạy được bất cứ lúc nào |

---

## SL-170 · QUYẾT ĐỊNH + LỆCH THẬT · Đổi mô hình nền sang `gemini-3.8-flash`, và bộ đếm token ra thiếu phần suy nghĩ

| | |
|---|---|
| **Ai quyết** | Người dùng, ngày 04/09/2026. Đây là đánh đổi chi phí/chất lượng của **người trả tiền**, không phải của công cụ — `eaa/llm/catalog.py` đã viết sẵn lý lẽ ấy, và hệ vẫn không bao giờ tự chọn |
| **Mã model xác minh thật, không đoán** | Chưa xác minh thì không được ghi vào `CATALOG`: mỗi mục ở đó khai *"đã kiểm bằng ListModels + một lượt generateContent thật"*. Đã gọi `ListModels` (54 model, 24 mã có chữ *flash*), rồi gọi thẳng `models/gemini-3.8-flash` và một lượt `generateContent` thật. Vào ≤ 1.048.576, ra ≤ 65.536, có `generateContent` và `countTokens` |
| **Lỗi tìm ra nhờ chính lượt gọi thử** | Lượt gọi trả về đúng chữ `OK` báo `candidatesTokenCount = 1` — và `thoughtsTokenCount = 92`. `GeminiClient` đọc `tokens_out` từ **mình `candidatesTokenCount`**, nên nó đếm 1 trong khi 93 token đã được sinh ra và tính tiền |
| **Vì sao lỗi này sống được tới hôm nay** | Với Pro 3.1 khoảng lệch không rõ như vậy. Nó là hạng lỗi mà kho này gọi tên nhiều lần: **đúng cho tới khi một giả định lặng lẽ đổi** — và lần đổi ấy chính là hôm nay |
| **Nó làm hỏng cái gì** | `llm_calls.jsonl` là dữ liệu gốc của chương đánh giá, và `eaa/budget.py TokenBudget` (N-904) là thứ chặn chi phí. Cả hai đứng trên con số ấy |
| **Đã sửa** | `tokens_out = candidatesTokenCount + thoughtsTokenCount`. **Cộng vào chứ không tách trường thứ hai**: mọi nơi đọc `tokens_out` đều đang hỏi *"lượt này sinh ra bao nhiêu token"*, và câu trả lời đúng gồm cả phần suy nghĩ. Một trường mới thì mọi chỗ tính tiền phải nhớ cộng, và chỗ nào quên sẽ sai im lặng |
| **Ghi chú danh mục nói đúng cái đã biết** | Nêu tầng suy nghĩ ăn vào trần `maxOutputTokens`, và nói thẳng **dự án CHƯA đo A/B nó với Pro 3.1 trên việc sinh mã nhúng**. Chưa có số thì chưa nói được cái nào sinh mã tốt hơn — có bài kiểm canh đúng câu ấy |
| **KHÔNG sửa lại quá khứ** | `projects/*/project_state.json`, `llm_calls.jsonl`, `kpi_log.csv`, và câu README *"robot đứng được trên AVR với `gemini-3.1-pro-preview`"* giữ nguyên. Đó là ghi chép việc đã xảy ra; sửa theo model mới là làm hỏng bằng chứng Chương 3. Pro 3.1 vẫn ở trong danh mục, và `KHUYEN_NGHI` có thêm mục *"dựng lại số liệu Chương 3"* trỏ về nó |
| **Bài kiểm cũ ghim chuỗi được nới đúng chỗ** | Hai bài trong TC-11 so `model` với chuỗi `"gemini-3.1-pro-preview"` gõ tay. Chúng canh *"mã model có được ghi vào bằng chứng không"*, không canh *"mặc định đang là model nào"* — nay so với `DEFAULT_MODEL` |
| **Bài canh** | `tests/test_tc130_token_ra_gom_phan_suy_nghi.py`, 12 bài. Cả hai chiều: có tầng suy nghĩ thì cộng, không có thì giữ nguyên số cũ không đổi một ly; usage rỗng hoặc toàn số không vẫn lùi về ước lượng chứ không trả 0 — trả 0 sẽ làm `TokenBudget` tin lượt gọi ấy miễn phí. Kiểm đột biến: bỏ phép cộng → 2 bài đỏ |

---

## SL-171 · BỔ SUNG · Mã tự chỉnh cho vừa ĐỒ ĐO của chính nó (N-908)

| | |
|---|---|
| **Cách tìm** | Rà soát bảng năng lực 04/09 xếp N-908 là ưu tiên Cao và là **điểm yếu lớn nhất** còn lại. Dữ liệu gốc: `DANH_GIA_NANG_LUC_AGENT §3.1` |
| **Ba ca thật, một hình dạng** | Cổng đỏ → vòng vá mở → bản vá sửa **cái đang đo** thay vì **cái bị đo**. `drv_imu` đổi `0.000031` thành `1/(131*100)` và đổi hệ số lọc bù để bài kiểm 3000 mẫu kịp hội tụ — trong khi con số `20,9654` bài kiểm cho là sai thực ra ĐÚNG (`30·(1−e^−1,2) = 20,964`). `logic_pid` thêm nhánh nhận đúng bộ hệ số của một bài kiểm rồi tắt luật điều khiển. `app_balance` gọi `pid_set_tunings(0,0,0)` |
| **Vì sao bốn cổng không bắt được** | Vì không có gì sai theo nghĩa cổng hiểu: mã dịch được, phân tích tĩnh sạch, bài kiểm xanh — xanh **vì nó vừa được chỉnh cho xanh**. Cổng đo *"mã có chạy không"*, không đo *"mã có đang đo đúng thứ nó nhận không"* |
| **Điều bộ này CỐ Ý KHÔNG làm** | Nó **không kiểm vật lý**. Câu *"20,9654 mới là số đúng"* đòi biết bài toán, và máy ở đây không biết. Nói thẳng trong docstring, và có bài kiểm canh đúng câu ấy — một bộ dò tự nhận làm được nhiều hơn nó làm được sẽ khiến người đọc thôi đọc |
| **Đã sửa — ba DẤU VẾT, mỗi dấu vết một ca thật** | Module mới `eaa/instrument.py`, nối vào `eaa/orchestrator.py` ngay sau khi nhận bản vá và TRƯỚC khi chạy chuỗi cổng — vì cổng sẽ báo ĐẠT cho một bản vá như thế, và đó đúng là lý do dạng này lọt được ba lần. Ba dấu vết: (1) **hằng số có trích dẫn bị đổi**: số nằm trong hàm mang `// ref:` là số lấy từ tài liệu, và tài liệu không đổi vì một bài kiểm đỏ — dấu vết ca `drv_imu`, chắc nhất trong ba; (2) **mã vừa mọc nhánh nhận đúng con số của bài kiểm**: một hằng số vừa xuất hiện trong phép so của mã mà cũng có trong tệp test — ca `logic_pid`; (3) **chú thích tự khai** `workaround`/`hack`/`tạm thời`/`để test qua` — rẻ nhất và thật nhất, vì mô hình tự nói |
| **Phạm vi dùng chung với cổng static** | Dấu vết 1 lấy phạm vi HÀM, đúng bằng phạm vi mà luật trích dẫn TC-17 đã chọn. Hai nơi cùng đọc một dấu `// ref:` thì phải cùng một phạm vi, nếu không chúng sẽ nói hai chuyện về cùng một thứ |
| **Vì sao DỪNG chứ không cảnh báo** | Cả ba ca đều bị người bắt ở G3 bằng cách đọc từng dòng. Một dòng cảnh báo chỉ thêm chữ vào chỗ đã có người đọc. Dừng thì rẻ hơn: câu *"bài kiểm sai hay mã sai"* là câu của người (N-908 ở mức T1), và hỏi sớm thì không đốt nốt ngân sách vá vào một hướng có thể đang sai |
| **Không tự sửa, không tự bỏ bản vá** | Sửa một bài kiểm sai là quyết định của người, y như sửa một trích đoạn datasheet phải đi qua G2. Thông báo nêu **cả hai nhánh** của câu hỏi, không chỉ nhánh "mã sai" — nêu một nhánh là đã trả lời hộ |
| **Sửa kèm: `eaa/contract.py` có phép làm sạch GIỮ ĐỘ DÀI** | `than_ham` bỏ chú thích để đếm ngoặc cho đúng, nên nó không trả về được chú thích — mà dấu `// ref:` thì nằm trong chú thích. Thêm `vung_than_ham()` trả VỊ TRÍ trên chính chuỗi gốc, nhờ phép làm sạch thay ký tự bằng dấu cách đúng số lượng. Chỗ gọi tự quyết cắt bản có chú thích hay bản đã sạch |
| **Hai lỗi tự tìm ra khi viết bài kiểm** | `0x1F` bị cắt hậu tố thành `0x1` — `F` vừa là hậu tố kiểu vừa là chữ số hệ 16, và bộ dò sẽ tin hằng số đã đổi trong khi nó không đổi. Và dấu vết 3 so CẢ DÒNG nên một chú thích cũ nằm trên dòng mã vừa sửa bị đọc thành chú thích mới; nay so RUỘT chú thích |
| **Bài canh** | `tests/test_tc131_ma_tu_chinh_cho_vua_do_do.py`, 25 bài, dựng trên đúng hai ca thật. Chiều "đừng kêu nhầm" nặng hơn — bộ dò này DỪNG vòng vá, nên một lần báo nhầm là một lần bắt người vào cuộc vô ích. Kiểm ĐỘT BIẾN 5 phép, cả 5 đều bị bắt: bỏ điều kiện `// ref:` → 3 bài đỏ; đếm cả số trong chú thích → 2; bỏ lọc số tầm thường → 1; không so chú thích với bản cũ → 1; không trừ hằng số đã có từ trước → 1 |

---

## SL-172 · LỆCH THẬT · Vòng đời tri thức không có cửa vào (N-036, N-100)

| | |
|---|---|
| **Cách tìm** | `scripts/kiem_bang_nang_luc.py`, phép kiểm thứ tư: `eaa/lifecycle.py` không được module nào trong `eaa/` hay `packs/` import, và không lệnh CLI nào gọi tới. Cùng hình dạng với SL-113 và SL-169 — **có mã, có test, không có người gọi** |
| **Module ấy đầy đủ tới mức nào** | Ba đường truy ngược (đồ thị · trích dẫn `// ref:` trong mã · trường `chunk-ids` của commit), `supersede`, `deprecate`, `apply`, cưỡng chế duyệt G2, và TC-29 canh từng đường. Thiếu đúng một thứ: cửa vào |
| **Hệ quả đúng bằng cái nó sinh ra để chữa** | Docstring của chính nó viết: *"một trích đoạn tài liệu bị phát hiện sai, được sửa, nhưng ba module đã sinh dựa trên bản sai vẫn nằm trong `main` và vẫn được coi là đã kiểm chứng."* Không có lệnh gọi tới thì đó chính xác là tình trạng của kho |
| **Đã sửa** | Lệnh `eaa knowledge` với ba nhánh: `stale <chunk>` (chỉ đọc — trả lời câu hỏi của N-100), `supersede <cũ> <mới> --reason`, `deprecate <chunk> --reason` (cả hai đòi quyết định G2) |
| **`stale` là CHỈ ĐỌC, và nói ra điều đó** | Một lệnh vừa trả lời vừa đổi trạng thái là lệnh người ta ngại gõ — mà đây đúng là lệnh cần gõ thường. Đầu ra kết bằng câu *"Lệnh này KHÔNG đổi gì"* kèm lệnh phải gõ nếu muốn hạ cấp thật |
| **Nhãn SUY RA, không phải ĐÃ KIỂM** | Ba đường bắt ba loại lệ khác nhau, nhưng đường đồ thị đọc khai báo `uses` — khai báo thiếu thì đường ấy mù (đúng rủi ro "đồ thị lệch thực tế" AIS §12 nêu). Tập trả về có thể THIẾU, nên nó là suy ra. Có bài kiểm canh đúng nhãn ấy |
| **`apply` chạy trong CÙNG lệnh** | Hạ module xuống `stale` không tách thành bước rời phải nhớ gõ. Cả giá trị của việc này nằm ở chỗ không module nào lặng lẽ giữ nhãn "đã kiểm chứng" khi cơ sở của nhãn ấy vừa đổi — một bước rời là một bước sẽ quên, và quên ở đây thì im lặng |
| **Không tự mở vòng sinh lại** | Hạ tin cậy là việc của máy; sinh lại hay sửa tay là quyết định của kỹ sư. Đầu ra nói thẳng câu ấy |
| **Thêm lệnh KHÔNG phải thêm quyền** | Chỉ `knowledge stale` vào `TOOLBOX`, ở nhóm chỉ đọc. `supersede`/`deprecate` **không** có trong danh mục Agent — chúng đổi kho tri thức và đòi G2, cùng hạng với `datasheet add`. Có bài kiểm canh cả hai chiều |
| **Đo trên dự án thật** | `eaa knowledge stale ds-021` trong `robot_balance` trả về 2 module: `drv_i2c` bị **cả ba** đường bắt, `drv_imu` chỉ bị hai — nó không trích dẫn `// ref:` trong mã, đúng ca mà đường thứ ba (chunk-ids của commit) sinh ra để bắt |
| **Sửa kèm: ngân sách lớp danh mục** | Thêm một mục vào `TOOLBOX` làm lớp danh mục chạm 2.810/2.800, và TC-78 đỏ đúng lúc phải đỏ — bài ấy sinh ra để *"bắt được ngay lần thêm công cụ làm tràn lớp"*. Xử lý theo hai bước: rút mô tả của mục mới cho gọn, rồi **DỜI** 100 token từ lớp vai trò sang lớp danh mục — dời chứ không NỚI, nên tổng ba lớp giữ nguyên 7.600 và trần 8.000 không bị đụng. Căn cứ là một phép đo: lớp vai trò dùng thật 1.018/1.400 |
| **Bài canh** | `tests/test_tc132_vong_doi_tri_thuc_co_cua_vao.py`, 13 bài chạy qua CLI thật. Kiểm ĐỘT BIẾN 4 phép, cả 4 đều bị bắt: tự cấp quyết định G2 → 6 bài đỏ; bỏ `apply` → 3; khai `stale` là ĐÃ KIỂM → 1; cho Agent gọi `supersede` → 1 |

---

## SL-173 · BỔ SUNG · Số đo trên bo chảy ngược vào prompt — lớp K8 (N-913)

| | |
|---|---|
| **Cách tìm** | Rà soát bảng năng lực 04/09, mục N-913. Dữ liệu gốc: `DANH_GIA_NANG_LUC_AGENT §3.7` — *"số đo từ phần cứng không tự chảy ngược vào prompt"* |
| **Chỗ hở** | Ba nơi giữ số đo — `measurements.jsonl` (phán quyết DS-xx), `flash_log.jsonl` (tốc độ nạp), `hardware_profile.yaml` (hằng số ai đó chép tay) — và **không nơi nào có đường chạm tới bộ ghép prompt**. Bài học từ bo chỉ tới mô hình qua LÝ DO TỪ CHỐI kỹ sư gõ tay ở G3; mất một lần gõ là mất hẳn |
| **Đo được** | Mốc gia tốc `-535` phải một người đo bằng DS-02 rồi tự tay chép vào hồ sơ phần cứng. Tốc độ bootloader `57600` (không phải 115200) phải một người phát hiện rồi tự nhớ. Lượt sinh mã kế tiếp không biết gì về cả hai |
| **Đã sửa** | `eaa/measured.py` — sổ nối tiếp `board_facts.jsonl` cho số đo của CHÍNH bo này, cộng lớp ngữ cảnh **K8 `board_facts`** trong `eaa/composer.py`, cộng lệnh `eaa measured list/add/approve` |
| **Vì sao tách khỏi hồ sơ phần cứng** | `hardware_profile.yaml` tả một **thiết kế**: chân nối vào đâu, chip gì, thạch anh bao nhiêu. Sổ này tả **cái bo trên bàn**: số đọc được từ chính nó, hôm nào, bằng kịch bản nào. SL-125 là lần hai thứ ấy bị lẫn, và cái giá là robot lao thẳng một phía. Hai loại sự thật hỏng theo hai kiểu và sửa bằng hai cách, nên chúng đứng riêng — kể cả khi cùng chảy vào một prompt |
| **Chỉ số ĐÃ DUYỆT mới vào prompt** | Agent chạy chẩn đoán và đọc telemetry nên nó ĐỀ XUẤT được (`measured add`, có trong danh mục, khai đúng là CÓ GHI). `measured approve` là lệnh DUYỆT nên **không** có trong danh mục — cùng luật SL-164. Một con số máy tự đo rồi tự tin là đúng sẽ đi thẳng vào mã của mọi module sau đó, và lúc ấy không còn ai đứng giữa để hỏi *"đo bằng gì"* |
| **Append-only + supersede** | Duyệt là GHI THÊM một bản ghi, không sửa bản cũ. Đo lại cho số khác thì bản sau thắng theo **thứ tự ghi**, không theo mốc thời gian — sổ nối tiếp nên thứ tự ghi là thứ tự thật, còn mốc thời gian là thứ người gõ vào và gõ sai được. Số cũ vẫn nằm nguyên trong sổ: hôm ấy bo đọc ra thế, và đó là dữ liệu của chương đánh giá |
| **Lớp nói thẳng thứ tự ưu tiên** | *"Khi số đo và tài liệu lệch nhau thì SỐ ĐO THẮNG: tài liệu tả một dòng sản phẩm, số đo tả đúng cái bo trên bàn."* Câu ấy nằm TRONG lớp, không nằm trong lời dặn chung |
| **Vị trí lớp là một quyết định** | K8 đứng **ngay trước** lớp trích đoạn tài liệu. Đặt sau thì mô hình đã đọc xong tài liệu và đã tin tài liệu trước khi gặp số đo. Có bài kiểm canh đúng thứ tự ấy |
| **Ngân sách: DỜI, không NỚI** | Lớp mới lấy 300 token **từ `repair`** (1.800 → 1.500), tổng vẫn đúng 8.000. Lấy từ đúng lớp ấy là có căn cứ: SL-147 đã đổi phần của `repair` thành **SÀN chứ không phải trần** — nó dùng chỗ trống thật còn lại, nên con số danh nghĩa là sổ sách chứ không phải cái chặn nó. Có bài kiểm ghim ba lớp còn lại để lần sửa sau không lặng lẽ đổi chỗ lấy |
| **Đo trên dự án thật** | Trên `robot_balance`: đề xuất `ACCEL_BALANCE_OFFSET = -535 LSB (DS-02)` → lớp K8 **rỗng**; duyệt xong → lớp K8 có 115 token kèm đủ xuất xứ. Bản ghi thử đã xoá khỏi dự án thật — duyệt là quyết định của kỹ sư, và máy không được ký thay |
| **Bài canh** | `tests/test_tc133_so_do_tren_bo_vao_prompt.py`, 21 bài. Đột biến 4 phép, cả 4 bị bắt: cho số chờ duyệt vào prompt → 2 bài đỏ; bỏ câu "số đo thắng tài liệu" → 2; đặt lớp sau lớp tài liệu → 1; cho Agent tự duyệt → 1 |

---

## SL-174 · BỔ SUNG · Chú thích số học sai thứ nguyên (N-911)

| | |
|---|---|
| **Ca thật** | Mã sinh ra mang chú thích `// 4ms per step / 0.000031s per sample = 129`. Phép chia ấy **đúng số học**: 0,004 / 0,000031 = 129,03. Nó sai ở chỗ khác — `0.000031` không phải *giây trên mẫu*, nó là hệ số thang con quay, đơn vị **độ trên LSB**. Chú thích tự gán cho hằng số một đơn vị nó không có, con số ra vô nghĩa, và đó là nguyên nhân robot không lấy đủ mẫu |
| **Vì sao không cổng nào bắt được** | Mã dịch được, phân tích tĩnh sạch, và chú thích nghe hợp lý. Người đọc lướt qua thấy một phép chia có đơn vị hai bên thì tin |
| **Đã sửa** | `eaa/dimension.py`, nối vào `StaticGate._quet_tep` ở mức **CẢNH BÁO**. Hai phép soi, và chúng bắt hai chuyện khác nhau |
| **Phép soi 1 — đơn vị khai chọi với đơn vị đã đăng ký** | Bắt đúng ca trên, nhưng CHỈ khi hằng số ấy có trong sổ số đo với đơn vị thật. Đây là lý do N-913 phải làm trước N-911: **phép kiểm chỉ mạnh bằng cái sổ đứng sau nó**, và tài liệu của hàm nói thẳng điều ấy thay vì im lặng tỏ ra chắc chắn |
| **Phép soi 2 — phép tính không ra kết quả nó khai** | Tự chứa, không cần sổ nào. Có quy đổi tiền tố thời gian, nên chính ca thật **KHÔNG** bị phép này kêu — và đó là đúng, nó đúng số học. Phép này bắt hạng khác: chú thích dựng một dẫn giải nghe được nhưng cộng trừ sai |
| **Không quy đổi giữa hai đại lượng khác nhau** | `4ms / 2V` giữ nguyên số. Quy đổi bừa giữa giây và vôn là làm đúng cái sai mà bộ này sinh ra để tìm |
| **CẢNH BÁO chứ không chặn** | Chú thích là văn xuôi tự do. Một bộ đọc văn xuôi mà chặn được đường merge sẽ chặn nhầm, và một cổng chặn nhầm sớm muộn cũng bị tắt đi. Cảnh báo đi vào `ToolReport.warnings` → hồ sơ G3 |
| **Không áp lên tệp kiểm viết bằng Python** | Cùng hàng rào SL-150 đã dựng |
| **Một bài kiểm RỖNG tự bắt được trong lúc viết** | Bài canh hàng rào Python ban đầu dùng chú thích `#`, mà bộ soi chỉ đọc chú thích C — nên nó xanh dù có hàng rào hay không. Kiểm đột biến lộ ra: bỏ hàng rào mà bài vẫn xanh. Đã sửa thành đoạn C **nhúng trong chuỗi Python** — ca thật, vì bài kiểm trên máy chủ ở kho này dịch mã C từ trong chính tệp test — và thêm vế ngược: cùng nội dung ấy trong tệp `.c` thì PHẢI kêu. Đúng dạng hỏng mà N-909 sinh ra để chặn, lần này bắt được ở chính bài kiểm của mình |
| **Bài canh** | `tests/test_tc134_chu_thich_sai_thu_nguyen.py`, 20 bài. Đột biến 4 phép, cả 4 bị bắt sau khi sửa bài rỗng: bỏ quy đổi tiền tố → 1 đỏ; coi ms và s là hai đại lượng → 2; cho cảnh báo thành lỗi chặn → 2; bỏ hàng rào tệp Python → 1 |

---

## SL-175 · BỔ SUNG · Làm cho lỗi KÊU LÊN ĐƯỢC (N-912)

| | |
|---|---|
| **Ca thật** | Ba lượt nạp đầu tiên, robot chỉ **im** hoặc **ngã**. Hai trạng thái ấy không phân biệt được với chip chết, với nguồn tụt, hay với mã chạy sai — và cũng không phân biệt được với nhau. Mỗi lần gỡ phải bắt đầu bằng câu *"nó có chạy không"*, thứ lẽ ra mạch tự trả lời được |
| **Điều đáng chú ý hơn** | Mọi đường báo hiệu về sau — nhịp bíp khởi động, nút thoát, cảnh báo mất mẫu — đều do **người** nghĩ ra và thêm vào. **Không bản phân rã nào tự đề nghị lấy một cái.** Đây không phải lỗi mã; nó là một khoảng trống trong THIẾT KẾ, và không có gì trong quy trình hỏi tới nó |
| **Đã sửa** | `eaa/observability.py` + hai trường `dau_hieu_song` / `dau_hieu_hong` trong mục backlog + lệnh `eaa observe` (báo cáo) và `eaa observe set` (khai) + một dòng checklist ở hồ sơ G3 |
| **Hai câu, và chúng là hai câu khác nhau** | *Người nhận ra module này ĐANG CHẠY bằng cách nào, không cần máy đo?* và *Khi nó HỎNG, người nhận ra bằng cách nào?* Trả lời một câu không phải trả lời cả hai — báo cáo nêu riêng từng cái còn thiếu |
| **Ranh giới engine, và nó chặt ở đây** | Engine **không biết** thứ gì kêu được, thứ gì sáng được, thứ gì người nghe được. Nó đọc cờ `observable` mà hồ sơ dự án gắn cho linh kiện và coi giá trị là **chuỗi mờ** — đúng cách nó đối xử với `uses` (SDD §3.2). Dự án nói cái gì quan sát được; engine chỉ đếm xem có cái nào không. Biết "còi thì kêu" là đã thành công cụ cho đúng một cái bo, và TC-38 quét chuyện ấy mỗi commit |
| **Phát hiện to nhất được tách riêng** | *"Bo không có kênh quan sát nào"* là hạng khác hẳn *"module này chưa khai"*: thiếu dấu hiệu ở một module còn sửa được bằng cách khai thêm; không có kênh nào thì **không module nào khai được gì**, và mọi lần gỡ lỗi về sau đều bắt đầu từ con số không. Khai đủ dấu hiệu mà bo không nói được gì thì báo cáo vẫn KHÔNG đạt |
| **Báo cáo, không phải cổng** | `eaa observe` luôn thoát 0. Chặn đường merge vì thiếu dấu hiệu sẽ biến một câu hỏi hay thành một thủ tục người ta tìm cách đi vòng. Chỗ nó xuất hiện là **checklist G3** — lúc người đang đọc mã của đúng module ấy, và là lúc cuối trước khi nó vào `main` |
| **Ai chốt** | `observe set` **không** có trong danh mục Agent: dấu hiệu nào đủ rõ trên bo cụ thể là quyết định của người (N-912 ở mức tự chủ T1). Agent đọc được báo cáo, và chỉ thế |
| **Đo trên dự án thật** | `eaa observe` trên `robot_balance`: **9/9 module chưa khai**, và **không kênh quan sát nào**. Hồ sơ phần cứng có ghi *"kênh báo hiệu DUY NHẤT người dùng nghe được"* — nhưng bằng lời **chú thích**, thứ engine không đọc được. Đúng hình dạng SL-125: một sự thật có trong đầu người mà không có trong dữ liệu |
| **Chưa sửa hồ sơ dự án** | Thêm `observable:` vào `hardware_profile.yaml` là sửa dữ liệu dự án và phải duyệt lại G1 — việc của kỹ sư, không của máy. Cảnh báo TRÔI hồ sơ đang bật sẵn từ phiên 03/09 nên càng không được thêm lặng lẽ |
| **Bài canh** | `tests/test_tc135_loi_phai_keu_len_duoc.py`, 23 bài. Đột biến 4 phép, cả 4 bị bắt: coi bo không kênh là ĐẠT → 1 đỏ; hỏi cả module đã bỏ → 1; quên ghi trường mới ra đĩa → 2; cho Agent tự chốt dấu hiệu → 1 |

---

## SL-176 · BỔ SUNG · Bản đồ thanh ghi máy đọc được, và cổng thứ năm `regcheck` (GĐ1)

| | |
|---|---|
| **Cách tìm** | `docs/KE_HOACH_VUOT_LEN.md` §2 — giai đoạn đầu của kế hoạch vượt lên, chọn trước vì nó **nuôi được chiều sâu** chứ không chỉ mua bề rộng |
| **Chỗ hở** | Luật `// ref:` (TC-17) kiểm **CÓ trích dẫn**, không kiểm **trích dẫn ĐÚNG**. Một mã chunk hợp lệ dán lên một giá trị sai đi qua sạch bốn cổng: cổng dịch bắt mã không dịch được; cổng tĩnh bắt điều cấm; cổng kiểm thử chạy trên bộ giả lập nơi ghi `0x1F` vào trường 3 bit là hợp lệ. Còn lại đúng một hạng lỗi không ai bắt — **giá trị hợp cú pháp, có trích dẫn, mà sai với silicon** |
| **Đã làm** | `eaa/regmap.py` (mô hình trung tính) + `eaa/regmap_svd.py` + `eaa/regmap_atdf.py` (hai bộ đọc) + `eaa/tools/regcheck.py` (cổng 5) + trường `regmap` trong lược đồ `pack.yaml` |
| **Ranh giới ba tầng — chỗ dễ sai nhất** | Bỏ bộ đọc SVD/ATDF vào `eaa/` có phá quy tắc số một không? **Không**: ranh giới của kho là **hằng số phần cứng**, không phải **định dạng tệp**. Engine biết cách đi trong một cây XML; nó không biết trong cây ấy có tên gì. Đúng cùng cách `platform.py` biết gọi một toolchain mà không biết tên chương trình. TC-38 vẫn xanh |
| **Bốn phép CHẶN** | thanh ghi không có trong bản đồ · giá trị vượt độ rộng · dịch bit ra ngoài độ rộng · ghi vào thanh ghi chỉ-đọc. Chặn vì **máy chứng minh được**, không phải suy từ văn xuôi |
| **Một phép CẢNH BÁO** | hàm cấu hình thanh ghi X mà trích dẫn chunk không nói về X. Cảnh báo vì ánh xạ chunk↔thanh ghi do **người** khai trong frontmatter, nên một chỗ khai thiếu sẽ thành cổng đỏ oan. Đây đúng là chỗ *"có trích dẫn"* khác *"trích dẫn đúng"* |
| **Phép thứ sáu, ở tầng khác** | Hồ sơ phần cứng khai một thanh ghi mà bản đồ của hãng KHÔNG có → ĐỎ. Đây là lỗi của **hồ sơ**, không của mã — nhưng phải đỏ ở đây vì đây là chỗ đầu tiên hai nguồn ấy gặp nhau. Gõ nhầm một tên trong `hardware_profile.yaml` thì mọi lượt sinh sau nhận một cái tên không tồn tại, và không gì khác trong hệ hỏi lại |
| **KHÔNG vào `required_gates`** | Thêm vào đó sẽ làm bằng chứng merge của **mọi module đã có** thành thiếu cổng, và ép mọi dự án phải có tệp bản đồ. Cổng vẫn **chặn được** vì chuỗi cổng dừng ở cổng hỏng đầu tiên — `required_gates` chỉ chi phối giấy phép merge |
| **Vắng bản đồ thì cổng ĐẠT và im** | Luật 1 của kế hoạch. `pack.yaml` chưa khai `regmap` thì cổng trả ĐẠT ngay, không một dòng nào. Có bài kiểm riêng cho điều này |
| **Nối vào N-908** | `instrument.py` nhận thêm bản đồ: trước GĐ1 nó chỉ biết một hằng số có trích dẫn *đã bị đổi*; nay biết thêm giá trị mới **có còn hợp lệ không**. Ba trạng thái chứ không hai — *hợp lệ · không hợp lệ · **không biết*** — vì gộp trạng thái thứ ba vào hai cái kia là đúng lỗi mà `confidence.py` sinh ra để chặn. Bản đồ lấy **từ chuỗi cổng**, không dựng đường đọc riêng: hai chỗ đọc hai bản là hai chỗ lệch nhau được |
| **KHÔNG nối vào N-911, và đây là một kết luận** | Kế hoạch nêu chỗ nối này; làm xong thì thấy nó tạo báo nhầm. Ca sinh ra N-911 là hệ số thang `0.000031` — một số thực **không bao giờ** nằm trong bản đồ thanh ghi. Phép duy nhất bản đồ đóng góp được là suy từ *giá trị reset*, mà reset `0` có ở gần như mọi thanh ghi: nó sẽ gắn nhãn "không thứ nguyên" cho số `0` rồi kêu ở mọi chú thích có `0 ms`. Có **bài kiểm giữ cho kết luận này không bị lặng lẽ đảo lại** — ai nối lại phải xoá bài ấy, và xoá một bài kiểm là hành động nhìn thấy được trong diff |
| **Hai bài kiểm RỖNG tự bắt được khi viết** | Bài canh hàng rào tệp Python viết hai lần đều rỗng: lần đầu dùng đoạn C nhúng trong chuỗi Python (bộ bỏ chú thích xoá ruột chuỗi nên vô hình ở **cả hai** tệp); lần hai bỏ dấu chấm phẩy (phép khớp lệnh ghi đòi dấu ấy). Bản dùng được là `CTRL_A = 0x1FF;` — hợp lệ trong cả hai ngôn ngữ — kèm vế ngược, và kèm lời nói thẳng rằng đây là lớp phòng thủ thứ hai |
| **Một bài kiểm cũ làm đúng việc của nó** | Lớp `OrchGia` của TC-131 khai *"hai phương thức ấy chỉ được đụng tới `self.repo`"*. Khi GĐ1 cho `_nghi_van_do_do` đọc `gate_chain`, bài kiểm đỏ **ngay tại đó** thay vì đỏ ở một chỗ xa |
| **Bài canh** | `tests/test_tc136_ban_do_thanh_ghi.py` 30 bài · `tests/test_tc137_ban_do_noi_vao_bo_do.py` 8 bài. Đột biến 6 phép, cả 6 bị bắt: bỏ kiểm độ rộng → 3 đỏ; cảnh báo thành lỗi chặn → 1; soi cả tệp Python → 1; ATDF quên đổi byte sang bit → 2; SVD bỏ sót thanh ghi lồng trong cluster → 1; vắng bản đồ mà kết luận "không hợp lệ" → 1 |

---

## SL-177 · BỔ SUNG · Thước đo: chỉ số của văn liệu, cộng bốn trục chưa ai có (GĐ2)

| | |
|---|---|
| **Cách tìm** | `docs/KE_HOACH_VUOT_LEN.md` §3. Luật 2 của kế hoạch: *"tốt hơn" phải ĐO ĐƯỢC, không được là một lời khai* — mà muốn đo thì phải có thước |
| **Nửa A — thước của họ** | `pass@1`, `pass@5`, và các hạng *trượt dịch / sai hành vi / đúng*. Phải có, vì không có thì không đối thoại được với văn liệu: IoT-SkillsBench và mọi benchmark sinh mã đều nói bằng những chữ ấy |
| **Nửa B — đóng góp** | Bốn trục không benchmark nào trong khảo sát hỏi: **độ nhạy bài kiểm** (bao nhiêu % bài kiểm xanh cả với mã sai) · **vá chỉnh đồ đo** · **mất việc im lặng** · **truy về được**. Chúng đo **chất lượng của quá trình**, không đo chất lượng một lượt sinh. Một hệ đạt `pass@1` cao mà 40% bài kiểm của nó rỗng thì con số ấy không có nghĩa như người đọc tưởng — và không ai nói ra, vì không ai đo |
| **Không tự đo lại** | Bốn trục lấy số từ các bộ đo **ĐÃ CÓ**: `sensitivity`, `instrument`, `contract`, `regcheck`. `bench.py` chỉ gom. Tự đo là dựng bộ đo thứ hai, và hai bộ đo cùng một thứ là hai bộ lệch nhau được |
| **Không tự chấm đúng/sai** | Hạng suy từ **báo cáo của chính chuỗi cổng**. Một kết cục khai `status='merged'` mà báo cáo cổng dịch nói trượt thì hạng là **trượt dịch** — báo cáo cổng là thứ đã CHẠY, `status` là thứ được GÁN. Dựng bộ chấm riêng cho benchmark là dựng con đường thứ hai, và con số đi ra nói về con đường ấy chứ không nói về sản phẩm |
| **Hai hạng thêm vào ba hạng của văn liệu** | **BLOCKED** (lỗi môi trường/cấu hình) — tính vào *sai hành vi* là ghi lỗi của máy tính vào sổ của mô hình. **HANDOFF** (hết vòng vá, hoặc dừng vì dấu vết chỉnh đồ đo) — khác *sai hành vi* ở chỗ hệ đã **chủ động dừng và hỏi người**, và gộp hai cái là xoá mất chính thứ sản phẩm này làm khác |
| **KHÔNG gộp hai hạng bằng chứng** | Kết quả trên bo thật và trên máy chủ đứng riêng trong mọi bản báo cáo. Trộn rồi báo một con số là nói dối, kể cả khi con số ấy đúng về số học. Đây là bài chống lại chính cám dỗ của đề án |
| **CHƯA ĐO ĐƯỢC khác BẰNG KHÔNG** | Bộ chuẩn không sinh bài kiểm nào thì tỉ lệ bài kiểm rỗng của nó **không phải 0%** — nó không tồn tại. Báo 0% là khai một thành tích chưa đo. Cùng luật `confidence.py` đã đặt cho mọi đầu ra khác |
| **Một bài kiểm RỖNG tự bắt được** | Bài canh `pass@k` ban đầu chỉ dùng `k=1` và `k=5` — hai chỗ mà công thức chuẩn và "tỉ lệ lượt đúng" TRÙNG NHAU, nên đột biến đổi công thức vẫn xanh. Chỗ chúng tách nhau là `k>1` với đủ lượt trượt: n=5, c=1, k=2 cho 0,4 theo công thức chuẩn và 0,2 theo tỉ lệ. Đã thêm ba mốc ấy |
| **Bài canh** | `tests/test_tc138_thuoc_do.py`, 22 bài. Đột biến 5 phép, cả 5 bị bắt sau khi vá bài rỗng: gộp HANDOFF/BLOCKED → 1 đỏ; chấm bằng trường tự khai → 2; CHƯA ĐO ĐƯỢC thành 0% → 1; gộp hai hạng bằng chứng → 1; `pass@k` thành tỉ lệ lượt đúng → 1 |
| **Còn thiếu để đóng E1** | Module này là cái **thước**; bộ **nhiệm vụ** thì chưa có. Đó là việc kế tiếp và nó tốn lượt gọi mô hình thật, nên tách khỏi mục này thay vì làm dở |

---

## SL-178 · BỔ SUNG · Thông báo lỗi phải nói được VIỆC PHẢI LÀM (việc số 1 của bản benchmark)

| | |
|---|---|
| **Cách tìm** | `docs/EAA_Benchmark_San_pham.docx` §6, hàng UI/UX. So với đối thủ thì đây là chỗ ta thua rõ nhất mà **không phải vì thiếu tính năng** — chỉ vì thông báo nói *cái gì sai* rồi dừng lại đúng lúc người dùng cần một mũi tên. Với một công cụ có 5 cổng người duyệt, bị bỏ lại giữa quy trình là hỏng nặng hơn ở một công cụ chạy một phát |
| **MỐC THẬT trước khi sửa: 14%, không phải 36%** | Bản báo cáo đã công bố 36% (40/112). Con số ấy **SAI** — biểu thức quét chỉ bắt được một dạng viết `raise CliError(`, nên nó đếm thiếu **cả tử lẫn mẫu**. Quét lại bằng phép đếm ngoặc cân cho **25/182 = 14%**. Sai số của phép đo chứ không phải của sản phẩm, nhưng nó đã được in ra nên nó phải được **đính chính**, không được lặng lẽ thay. Bài `test_moc_cu_duoc_ghi_lai_de_khong_ai_doc_nham` giữ mốc ấy khỏi bị quên |
| **KHÔNG đổi định nghĩa phép đo cho dễ đạt** | Cám dỗ ở đây rất cụ thể: đổi "nêu được lệnh cụ thể" thành "có tính hành động" thì 14% lên 60% mà không sửa một dòng nào. Đó đúng là hạng lỗi mà `instrument.py` (SL-171) sinh ra để bắt — vá cái đồ đo thay vì vá cái được đo. Ngưỡng và định nghĩa giữ nguyên từ đầu đến cuối |
| **Sửa Ở MỘT CHỖ, không sửa 182 chuỗi** | Viết gợi ý vào từng thông báo thì mỗi gợi ý là một bản sao của cây lệnh, và nó lệch khỏi cây lệnh **ngay lần đầu ai đó đổi tên một lệnh** — không gì bắt được chỗ lệch ấy. Gom vào bảng `GOI_Y_KHI_HONG` (56 lệnh cấp một) thì bắt được: `test_MOI_GOI_Y_deu_tro_vao_mot_lenh_CO_THAT` đối chiếu bảng với cây lệnh THẬT dựng từ argparse, hai chiều |
| **Gắn ở `main()`, không gắn ở chỗ ném** | `main()` biết **người dùng vừa gõ lệnh nào**; hàm ném lỗi chỉ biết chính nó. Nhờ vậy lỗi ném từ hàm phụ trợ (`_doc_so_do`, `_nap_kho`, `_chon_cong`…) vẫn nhận đúng gợi ý của lệnh đang chạy — đây là 32 chỗ mà phép đo tĩnh **không với tới được** |
| **Không nói hai lần** | Thông báo đã tự nêu một lệnh thì không gắn thêm. Nói hai lần làm loãng lần thứ nhất |
| **Con số sau khi sửa — báo cả hai** | Phép đo tĩnh: **150/182 = 82%** (25 tự nêu + 125 được bảng phủ). Đây là **cận dưới**, vì 32 chỗ còn lại nằm trong hàm phụ trợ mà phép quy về lệnh không với tới, dù lúc chạy thật chúng vẫn có gợi ý. Báo cả hai con số chứ không báo mỗi con số đẹp |
| **Bài canh** | `tests/test_tc145_thong_bao_loi_noi_duoc_viec_phai_lam.py`, 11 bài. Đột biến 4 phép, cả 4 bị bắt: gợi ý trỏ vào lệnh không tồn tại → 2 đỏ; xoá một lệnh khỏi bảng → 1; bỏ luật "không nói hai lần" → 1; bỏ gợi ý khỏi đường in lỗi của `main()` → 1 (bài đầu-cuối) |
