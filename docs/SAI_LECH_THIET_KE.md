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
