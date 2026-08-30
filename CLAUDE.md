# CLAUDE.md — Embedded AIDD Agent (EAA)

Dự án: xây dựng **Agent lập trình nhúng tổng quát** (Embedded AIDD Agent) theo bộ tài liệu thiết kế
trong `docs/`. Đây là sản phẩm phần mềm của đề án tốt nghiệp Thạc sĩ Kỹ thuật (Kỹ thuật Điện tử, PTIT).

- **Học viên thực hiện:** Vũ Trí Công
- **Giảng viên hướng dẫn:** TS. Nguyễn Trung Hiếu

Thiết kế đã ĐÓNG BĂNG (design freeze) — code bám thiết kế; nếu buộc phải lệch,
ghi rõ và cập nhật tài liệu tương ứng, không lệch ngầm.

## Đọc tài liệu theo thứ tự này

1. `docs/md/EAA-MDD-00_Tai_lieu_tong_hop.md` — tổng hợp: bảng 15 quyết định đã chốt, kế hoạch sprint S0–S4, checklist ngày đầu, DoD.
2. `docs/md/EAA-SDD-03_Thiet_ke_chi_tiet.md` — **bản vẽ thi công**: cây thư mục, schema dữ liệu, module Python, 10 lệnh CLI. Mở thường trực khi code.
3. `docs/md/EAA-AIS-05_Dac_ta_ky_thuat_AI.md` — tầng AI: nén ngữ cảnh K1–K7, RAG, Knowledge Graph, ingest đa phương thức, chẩn đoán phần cứng, vòng đời tri thức, eaa doctor + Tool Card.
4. `docs/md/EAA-STP-04_Ke_hoach_kiem_thu.md` + phần TC bổ sung trong AIS — **38 test case là thước chấm**.
5. `docs/md/EAA-SAD-02_Thiet_ke_kien_truc.md`, `docs/md/EAA-SRS-01_Dac_ta_yeu_cau.md` — tra cứu kiến trúc/yêu cầu.

Bản gốc Word/PDF/hình trong `docs/docx/`, `docs/EAA_Full_Design.pdf`, `docs/hinh/`.

## Kiến trúc 3 tầng — quy tắc số 1

- `eaa/` — **ENGINE**: điều phối, gate, composer, tools, doctor. **CẤM tuyệt đối** mọi tham chiếu
  phần cứng cụ thể (atmega, mpu6050, a4988, tccr, twbr, tên thanh ghi...). Test TC-38 quét điều này
  trong CI mỗi commit — vi phạm là fail.
- `packs/avr/` — **PLATFORM PACK**: toolchain adapter, luật static analysis, mẫu prompt nền tảng,
  smoke test. Engine gọi toolchain CHỈ qua interface `eaa/platform.py`.
- `projects/robot_balance/` — **DỰ ÁN MẪU** (reference project): constraints, hardware profile,
  datasheets, mô hình mô phỏng con lắc ngược. Agent là tổng quát; robot chỉ để kiểm chứng.

## Các bất biến KHÔNG thương lượng (có test tương ứng)

- Merge chỉ xảy ra khi TOÀN BỘ ToolReport.passed == True VÀ gate G3 approved. Không có nhánh code
  thứ hai dẫn tới merge. (TC-01, TC-02)
- 5 Human Gate G1–G5 không thể bị vượt bằng bất kỳ lệnh nào; cài công cụ / nạp firmware luôn cần
  người xác nhận. (TC-01, TC-28, TC-34)
- Vòng tự sửa ≤ N=3 lần, dạng patch (không gửi lại cả file); quá N → dừng, bàn giao người. (TC-06, TC-19)
- Ngân sách prompt ≤ 8.000 token vào, kiểm bằng count_tokens TRƯỚC khi gọi LLM. (TC-16)
- Mọi kho tri thức: append-only + supersede, không ghi đè vật lý; mâu thuẫn → người phân xử. (TC-26, TC-29)
- Mã cấu hình thanh ghi phải có trích dẫn `// ref: <chunk-id>`. (TC-17)
- Project State ghi nguyên tử, sống sót qua crash. (TC-03)
- LLM: Gemini Pro 3.1, ghim phiên bản, stateless mỗi lần gọi; Sprint 1–3 dùng MockLLM, chưa gọi API thật.

## Kế hoạch — bắt đầu từ Sprint 0 (MDD §6)

S0 khung xương (state, policy, cli, doctor tối thiểu) → S1 tri thức (KB, graph, composer, MockLLM)
→ S2 vòng lặp chuẩn (tools, orchestrator, gates, git, kpi) → S3 mô phỏng + ingest + vòng đời tri thức
+ docs registry → S4 Gemini thật + 2 module demo + chẩn đoán. Mỗi sprint có danh sách TC phải xanh
trong MDD; cuối sprint chạy lại toàn bộ test cũ (chống thoái lui).

Việc đầu tiên: viết `eaa/state.py` với test TC-03 viết TRƯỚC (test-first cho phần lõi), và test TC-38
đưa vào CI ngay từ commit đầu.

## Quy ước

- Python ≥ 3.10, pytest, coverage ≥ 80% cho orchestrator/gates/state.
- Commit message chuẩn NFR-07: kèm prompt hash, model, constraints_version, chunk ids (với mã sinh);
  với code engine thường: mô tả + mã TC liên quan.
- Mỗi module trên nhánh `feature/<tên>`, vào main qua review.
- API key qua biến môi trường `EAA_LLM_KEY`; không bao giờ ghi key ra log/commit. (TC-14)
