# Bảng năng lực Agent — bản để review

Dựng ngày 30/08/2026 từ **dữ liệu thật** trong kho, không chép tay: danh sách
lệnh đọc từ bộ phân tích đối số, năng lực nền tảng đọc từ `pack.yaml`, mức tự
chủ đọc từ bảng nghiệp vụ, công cụ ngoài kiểm bằng `shutil.which`.

Sinh lại bất cứ lúc nào: `eaa capabilities --verbose`

---

## 1. Thang mức tự chủ — cột quan trọng nhất

Đọc bảng này trước, vì mọi con số phía dưới chỉ có nghĩa khi gắn với một mức.

| Mức | Nghĩa | Dùng khi |
|---|---|---|
| **T0** | Người làm, Agent ghi vết | Việc đòi tay người hoặc dụng cụ. Agent chỉ ghi ai làm, lúc nào, kết quả gì |
| **T1** | Agent đề xuất, người quyết | Agent dựng phương án ở trạng thái ĐỀ XUẤT. Không có hiệu lực tới khi người chọn |
| **T2** | Agent làm, người duyệt trước khi có hiệu lực | Agent làm trọn và trình kết quả; vào hệ thống sau khi qua một gate |
| **T3** | Agent tự làm, báo lại | Có hiệu lực ngay, nhưng để lại bằng chứng đầy đủ. Chỉ khi việc hoàn tác được |
| **T4** | Agent tự làm, không cần báo | Chỉ việc đọc, việc tính. **Mọi việc GHI ra ngoài đều không thuộc mức này** |

---

## 2. Toàn cảnh: 74 nghiệp vụ theo 12 giai đoạn

**72/74 đủ · 1 cố ý không làm · 1 ngoài phạm vi đề án.**

Ký hiệu: `✓` đủ · `⊘` cố ý không làm · `✗` chưa có

### G0 — Tiếp nhận & khảo sát · 6/6

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-001 Tiếp nhận yêu cầu bằng lời của người dùng | T1 |
| ✓ | N-002 Dò phần cứng đang cắm vào máy | T4 |
| ✓ | N-003 Nhận dạng bo/MCU từ dấu hiệu dò được | T1 |
| ✓ | N-004 Thu thập tài liệu gốc | T1 |
| ✓ | N-005 Lập danh mục giả định ban đầu | T3 |
| ✓ | N-006 Xác định phạm vi và cái KHÔNG làm | T1 |

### G1 — Chốt ràng buộc & kiến trúc · 8/8

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-010 Chốt ràng buộc cứng | T1 |
| ✓ | N-011 Định nghĩa tiêu chí nghiệm thu ĐO ĐƯỢC | T1 |
| ✓ | N-012 Chọn kiến trúc phần mềm | T1 |
| ✓ | N-013 Phân bổ tài nguyên phần cứng | T3 |
| ✓ | N-014 Chốt sơ đồ chân | T1 |
| ✓ | N-015 Lập ngân sách tài nguyên | T1 |
| ✓ | N-016 Phân tích hỏng hóc và hệ quả | T1 |
| ✓ | N-017 Xác định chế độ an toàn | T1 |

### G2 — Môi trường & công cụ · 5/5

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-020 Kiểm công cụ đã có trên máy | T4 |
| ✓ | N-021 Tìm công cụ chưa biết cách cài | T1 |
| ✓ | N-022 Cài công cụ | T2 |
| ✓ | N-023 Khóa phiên bản môi trường | T3 |
| ✓ | N-024 Dựng kho mã và quy ước commit | T3 |

### G3 — Tri thức & tài liệu · 8/8

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-030 Chọn trang tài liệu cần trích | T1 |
| ✓ | N-031 Chưng cất trích đoạn thành bảng thanh ghi–bit | T2 |
| ✓ | N-032 Dựng đồ thị tri thức | T4 |
| ✓ | N-033 Phát hiện mâu thuẫn nguồn | T1 |
| ✓ | N-034 Tự đánh giá đủ thông tin trước khi sinh mã | T3 |
| ✓ | N-035 Đi tìm thứ còn thiếu (leo thang 3 bậc) | T2 |
| ✓ | N-036 Quản lý vòng đời tri thức | T3 |
| ✓ | N-037 Theo dõi errata của nhà sản xuất | T1 |

### G4 — Phân rã & giao diện · 4/4

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-040 Phân rã bài toán thành module | T1 |
| ✓ | N-041 Định nghĩa giao diện giữa module | T2 |
| ✓ | N-042 Xếp thứ tự làm theo phụ thuộc | T3 |
| ✓ | N-043 Thiết kế lịch chạy | T1 |

### G5 — Sinh mã & kiểm chứng · 8/8

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-050 Sinh mã một module | T2 |
| ✓ | N-051 Biên dịch | T4 |
| ✓ | N-052 Phân tích tĩnh theo ràng buộc dự án | T4 |
| ✓ | N-053 Kiểm thử đơn vị trên máy chủ | T4 |
| ✓ | N-054 Đo chiếm dụng bộ nhớ | T4 |
| ✓ | N-055 Vòng tự sửa khi cổng không đạt | T3 |
| ✓ | N-056 Review và hợp nhất | T2 |
| ✓ | N-057 Ghi nhận lỗi mô hình bịa ra | T3 |

### G6 — Mô phỏng · 4/5

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-060 Dựng mô hình đối tượng điều khiển | T1 |
| ✓ | N-061 Chạy mô phỏng vòng kín | T4 |
| ✓ | N-062 Quét tham số và đề xuất bộ tham số | T1 |
| ✓ | N-063 Tiêm lỗi trong mô phỏng | T3 |
| ⊘ | **N-064 Chạy chính mã C sinh ra trong mô phỏng** | T0 |

### G7 — Ráp & nạp · 6/6

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-070 Ráp firmware hoàn chỉnh | T2 |
| ✓ | N-071 Kiểm bộ nhớ ở tầm firmware | T4 |
| ✓ | N-072 Kiểm trước khi nạp | T2 |
| ✓ | N-073 Chọn đúng thiết bị để nạp | T3 |
| ✓ | N-074 Nạp và ghi nhật ký | T2 |
| ✓ | N-075 Kiểm sau khi nạp | T3 |

### G8 — Đo trên thiết bị · 6/7

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-080 Thiết lập kênh đo | T3 |
| ✓ | N-081 Sinh firmware đo cho từng kịch bản chẩn đoán | T2 |
| ✓ | N-082 Chẩn đoán hai kênh | T1 |
| ✓ | N-083 Đo đặc tính thời gian thực | T3 |
| ✓ | N-084 Đo điện và nhiệt | T0 |
| ✗ | **N-085 Chẩn đoán sâu bằng công cụ gỡ lỗi** | T0 |
| ✓ | N-086 Kiểm độ bền dài hạn | T3 |

### G9 — Bàn giao · 5/5

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-090 Đối chiếu tiêu chí nghiệm thu | T2 |
| ✓ | N-091 Phong hạng chất lượng bản mã | T2 |
| ✓ | N-092 Giữ bản chạy tốt và quay lui | T3 |
| ✓ | N-093 Xuất báo cáo và dấu vết | T3 |
| ✓ | N-094 Bàn giao tài liệu vận hành | T1 |

### G10 — Vận hành & bảo trì · 4/4

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-100 Đánh giá ảnh hưởng khi tài liệu đổi | T1 |
| ✓ | N-101 Đánh giá ảnh hưởng khi linh kiện đổi | T1 |
| ✓ | N-102 Chẩn đoán sự cố ngoài hiện trường | T1 |
| ✓ | N-103 Cập nhật firmware cho thiết bị đã triển khai | T2 |

### XS — Xuyên suốt · 8/8

| | Nghiệp vụ | Tự chủ |
|---|---|---|
| ✓ | N-900 Giữ ranh giới tổng quát / nền tảng / dự án | T4 |
| ✓ | N-901 Bảo vệ khóa và bí mật | T4 |
| ✓ | N-902 Không bao giờ hành động ngoài ý muốn người | T2 |
| ✓ | N-903 Nói rõ mức tin cậy của mọi điều mình nói | T3 |
| ✓ | N-904 Quản lý chi phí gọi mô hình | T3 |
| ✓ | N-905 Ghi nhận mọi sai lệch so với thiết kế | T3 |
| ✓ | N-906 Tự đánh giá và cải tiến quy trình | T1 |
| ✓ | N-907 Khôi phục sau gián đoạn | T4 |

---

## 3. Ranh giới người / máy trong hội thoại

`eaa chat` cho Agent tự gọi **39 lệnh**. Ranh giới không nằm ở lời dặn trong
prompt mà ở **danh mục công cụ** (`TOOLBOX` trong `eaa/agent.py`) — Agent
không có đường nào gọi thứ không nằm trong đó.

### Agent tự gọi được — chỉ đọc (28)

`capabilities` · `status` · `policy` · `packs` · `plan list` · `ledger list` ·
`safety show` · `budget show` · `budget tokens` · `sources need` ·
`sources pages` · `errata show` · `datasheet list` · `docs list` ·
`diagnose list` · `diagnose select` · `diagnose measure` · `report kpi` ·
`report review` · `report retrieval` · `report versions` · `deviations` ·
`gate show` · `field` · `handover doc` · `handover rollout` · `sim run` ·
`resolve` · `survey`

### Agent tự gọi được — có ghi ra tệp, nhưng không quyết định thay người (11)

`plan add` · `budget propose` · `propose scope` · `propose constraints` ·
`propose acceptance` · `propose pinmap` · `propose plant` · `interface` ·
`errata lookup` · `handover swap` · `safety propose`

### Agent KHÔNG BAO GIỜ tự gọi — 12 lệnh, mỗi lệnh một lý do

| Lệnh | Vì sao |
|---|---|
| `gate approve/reject` | Quyết định tại gate là bất biến trung tâm của cả sản phẩm |
| `flash` | Chạm vào thiết bị thật; luôn cần chính người xác nhận |
| `doctor --fix` | Cài đặt đổi máy của người dùng |
| `tune` | Phong hạng `hw-verified` là khẳng định về phần cứng |
| `rollback` | Đổi mã đang chạy trên thiết bị |
| `gen` | **Ghi vào `kpi_log.csv` — dữ liệu thí nghiệm Chương 3** |
| `build` | Bước trước khi nạp; người chạy để còn kiểm ảnh sinh ra |
| `endurance` | Chiếm cổng nối tiếp và chạy hàng giờ |
| `telemetry`, `ports` | Chạm tới cổng nối tiếp của máy người dùng |
| `init` | Quyết định mở đầu, không nên nằm giữa một câu hỏi |
| `brief`, `decide` | Chính chúng hỏi người — gọi hộ thì mất phần hỏi |
| `scope-image` | Cần người đối chiếu ảnh gốc rồi chốt số đo |
| `datasheet add`, `docs regen` | Đưa tri thức mới vào / phát hành phiên bản mới |

---

## 4. Năng lực nền tảng — 11/11 (pack `avr`)

`compile` · `link` · `hex` · `size` · `static` · `flash` · `flash_verify` ·
`sim` · khuôn firmware · khuôn firmware chẩn đoán · khuôn tệp tiêu đề

Pack `stm32` khai đủ như trên. **Thêm họ MCU mới = thêm `packs/<tên>/`, không
sửa một dòng engine** — đã chứng minh bằng pack thứ hai (NFR-05, TC-47).

---

## 5. Công cụ ngoài — **1/7 có mặt trên máy này**

| Công cụ | Trạng thái |
|---|---|
| `git` | ✓ `/usr/bin/git` |
| `avr-gcc` | ✗ chưa cài |
| `avr-objcopy` | ✗ chưa cài |
| `avr-size` | ✗ chưa cài |
| `avrdude` | ✗ chưa cài |
| `cppcheck` | ✗ chưa cài |
| `python` | ✗ máy chỉ có `python3` — xem ghi chú dưới |

**Đây là chỗ chặn thật cho phần lắp mạch.** Không có `avr-gcc` và `avrdude`
thì không dịch được, không nạp được, và cổng `compile`/`static` sẽ báo KHÔNG
ĐẠT — đúng như thiết kế, vì *"một cổng im lặng cho qua vì không tìm thấy công
cụ còn tệ hơn không có cổng"*.

Cài bằng: `eaa doctor --fix` (in lệnh, hỏi từng lệnh, **không tự chạy**).

> Ghi chú về `python`: bảng này kiểm thô bằng `shutil.which`, còn khi chạy
> thật engine truyền `sys.executable` vào chỗ giữ `{python}`. Nên mục này là
> một cảnh báo giả của bảng, không phải một thiếu sót thật — nhưng tôi để
> nguyên thay vì lọc đi, vì bảng phải nói đúng thứ nó đo được.

---

## 6. Hai mục chưa làm — và cả hai đều có lý do

### N-064 · Chạy chính mã C sinh ra trong mô phỏng — **cố ý không làm**

Cổng SIL hiện chạy bộ điều khiển Python tham chiếu, không chạy mã C mà Agent
sinh ra. Nối vào mà không thật sự dịch và chạy artifact thì cổng sẽ báo "đạt"
mà chẳng kiểm gì — nguy hiểm hơn là không có cổng.

*Làm thật thì cần:* lớp giả lập phần cứng ở tầng dự án + dịch mã sinh ra cho
máy chủ + nối qua giao thức `process:` mà `sim_runner` đã có sẵn. Phần khung
đã có; phần thiếu là mã HAL giả của dự án.

### N-085 · Chẩn đoán sâu bằng debugWIRE/JTAG/SWD — **ngoài phạm vi đề án**

Đã ghi từ đầu. UART cộng nạp lại là đủ cho vòng chẩn đoán hai kênh.

---

## 7. Chỗ tôi nghĩ đáng bổ sung — để anh cân nhắc

Không có mục nào dưới đây là lỗi; chúng là những chỗ năng lực **có** nhưng
mỏng hơn phần còn lại.

| # | Chỗ mỏng | Vì sao đáng làm | Cỡ việc |
|---|---|---|---|
| 1 | **Đọc nội dung PDF và ảnh trong kho tài liệu.** `survey` mới liệt kê được PDF/ảnh, chưa trích nội dung. Hồ sơ BLKLab có 2 PDF hướng dẫn và 14 ảnh sơ đồ mà Agent chưa đọc được | Đây là chỗ thiếu lộ ra ngay ở bài test đầu tiên: Agent mô tả được mạch từ **mã nguồn**, nhưng sơ đồ nối dây nằm trong ảnh | Vừa |
| 2 | **Dựng thẳng `hardware_profile.yaml` từ bản khảo sát.** Hiện `survey` bày dữ kiện ra, người vẫn phải gõ lại vào hồ sơ | Rút ngắn đúng đoạn tốn công nhất khi tiếp nhận một dự án có sẵn | Nhỏ |
| 3 | **N-064 — cổng SIL chạy mã C thật.** Khung đã có, thiếu HAL giả của dự án | Đây là mắt xích duy nhất còn để trống trong chuỗi kiểm chứng | Lớn |
| 4 | **Agent đọc được thư mục đã giải nén**, không chỉ tệp `.zip` | Hồ sơ thật hay tới ở dạng thư mục, hoặc `.rar` mà ta không giải được | Nhỏ |
| 5 | **`survey` ghi kết quả vào kho nguồn** (`SourceRegistry`) thay vì chỉ in ra | Để bản khảo sát thành tri thức có phiên bản, không phải một lần chạy rồi mất | Nhỏ |

---

## 8. Kiểm bằng gì

| Tầng | Kiểm bằng |
|---|---|
| Lệnh CLI | `pytest -q` (1428 test) · `scripts/kiem_on_dinh.py` |
| Lệnh Agent tự gọi | `pytest tests/test_tc61_chat.py` |
| Năng lực nền tảng | `pytest tests/test_platform_pack.py tests/test_tc47_pack_thu_hai.py` |
| Công cụ ngoài | `eaa doctor` · smoke test + Tool Card sau khi cài |
| Mã và tài liệu có lệch nhau không | `eaa deviations` |
| Chất lượng truy xuất tri thức | `eaa report retrieval` |

**Bảng năng lực kiểm SỰ CÓ MẶT, không chạy thử.** Câu "nó chạy đúng không"
thuộc về bộ test — và đó là chỗ duy nhất trả lời được.
