# Embedded AIDD Agent (EAA)

Agent lập trình nhúng **tổng quát** — bộ điều phối đóng gói quy trình phát triển
phần mềm nhúng có AI hỗ trợ thành một hệ thống chạy được, với các cổng phê duyệt
của con người được **cưỡng chế bằng phần mềm** chứ không bằng quy ước.

Sản phẩm phần mềm của đề án tốt nghiệp Thạc sĩ Kỹ thuật (Kỹ thuật Điện tử, PTIT)
— Vũ Trí Công. Thiết kế đã đóng băng; hồ sơ đầy đủ nằm trong [`docs/`](docs/).

## Kiến trúc ba tầng

| Tầng | Thư mục | Nội dung | Luật |
|---|---|---|---|
| **Engine** | `eaa/` | Điều phối, gate, composer, tool layer, doctor | **Không chứa một hằng số phần cứng nào.** TC-38 quét mỗi commit |
| **Platform Pack** | `packs/avr/` | Toolchain, quy tắc phân tích tĩnh, mẫu prompt, smoke test theo họ MCU | Engine chỉ gọi qua `eaa/platform.py` |
| **Project** | `projects/robot_balance/` | Ràng buộc, hồ sơ phần cứng, trích đoạn tài liệu, firmware | Dự án mẫu để kiểm chứng quy trình |

Robot 2 bánh tự cân bằng là **dự án mẫu**, không phải đích chuyên dụng. Giá trị
chuyển giao nằm ở engine và phương pháp. Thêm một họ MCU mới = thêm một Platform
Pack, không sửa một dòng engine (NFR-05).

## Bất biến không thương lượng

- Merge chỉ xảy ra khi **toàn bộ** `ToolReport.passed` **và** gate G3 đã duyệt —
  không tồn tại nhánh mã thứ hai dẫn tới merge.
- Năm Human Gate G1–G5 không thể bị vượt bằng bất kỳ lệnh nào. Cài công cụ và
  nạp firmware luôn cần người xác nhận.
- Vòng tự sửa ≤ 3 lần, dạng vá; quá số lần thì dừng và bàn giao người.
- Ngân sách prompt ≤ 8.000 token vào, kiểm trước khi gọi mô hình.
- Mọi kho tri thức append-only + supersede; mâu thuẫn thì người phân xử.
- Mọi lần gọi mô hình là stateless — không có trí nhớ hội thoại, ngữ cảnh lắp
  ráp lại từ Knowledge Base + Project State.

## Bắt đầu

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Một module đi trọn vòng lặp chuẩn:

```bash
eaa init                                  # UC01 — tạo Project State
eaa plan add drv_i2c --uses twi,imu       # UC02 — kiểm xung đột ngay lúc khai báo
eaa gate approve G1                       # chốt ràng buộc và kiến trúc
eaa gate approve G2                       # duyệt trích đoạn tài liệu vào kho
eaa gen drv_i2c                           # UC04 — 13 bước, dừng ở G3 (thoát 2)
eaa gate show G3                          # xem diff + checklist sinh từ đồ thị
eaa gate approve G3                       # UC05 — con người mở cổng → merge
eaa report kpi                            # UC09 — số liệu cho Chương 3
```

Các lệnh tra cứu: `eaa resume` · `eaa status` · `eaa policy` · `eaa packs` ·
`eaa plan list` · `eaa ledger list`.

Mã thoát (để script hóa thực nghiệm A/B): `0` thành công · `2` chờ gate ·
`3` quá số lần tự sửa · `4` lỗi môi trường.

## Kiểm thử

```bash
.venv/bin/python -m pytest                       # toàn bộ
.venv/bin/python -m pytest tests/test_tc38_engine_purity.py   # engine sạch phần cứng
```

Test được đặt tên theo mã test case trong `docs/md/EAA-STP-04` và
`docs/md/EAA-AIS-05` §11 — 38 test case là thước chấm của sản phẩm.

## Tiến độ

| Sprint | Mục tiêu | Trạng thái |
|---|---|---|
| **S0** | Khung xương: state bền, policy, interface pack, khung CLI | ✅ TC-03, TC-08, TC-38 xanh |
| **S1** | Tri thức: 5 kho, graph, composer K1–K7, MockLLM | ✅ TC-04, TC-05, TC-10, TC-16, TC-18, TC-19, TC-21 xanh |
| **S2** | Vòng lặp chuẩn 13 bước: tools, orchestrator, gates, git, KPI | ✅ TC-01, TC-02, TC-06, TC-07, TC-09, TC-17 xanh |
| **S3** | Mô phỏng MIL/SIL, ingest, vòng đời tri thức, docs registry, doctor | ✅ TC-12, TC-13, TC-22, TC-24, TC-25, TC-26, TC-29, TC-32..37 xanh |
| S4 | Mô hình thật, 2 module demo, chẩn đoán phần cứng | ⬜ |

## Đọc hồ sơ thiết kế

1. `docs/md/EAA-MDD-00` — tổng hợp: 15 quyết định đã chốt, kế hoạch sprint
2. `docs/md/EAA-SDD-03` — bản vẽ thi công: cây thư mục, lược đồ dữ liệu, module
3. `docs/md/EAA-AIS-05` — tầng AI: nén ngữ cảnh, RAG, graph, ingest, chẩn đoán
4. `docs/md/EAA-STP-04` — thước chấm
5. `docs/md/EAA-SAD-02`, `docs/md/EAA-SRS-01` — tra cứu kiến trúc và yêu cầu
