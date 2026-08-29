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
