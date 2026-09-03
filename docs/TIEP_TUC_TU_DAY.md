# Tiếp tục từ đây — bàn giao phiên 03/09/2026

**Robot đứng được.** Thả tay trên sàn, không đổ. Firmware đang chạy trên bo:
commit `80ec03d0d4`, băm ảnh `sha256:06797d7673bd…`, đã đọc ngược khớp sau nạp.

Toàn bộ mã điều khiển trên bo do Agent sinh qua vòng chuẩn — prompt bảy lớp →
LLM → bốn cổng → tự sửa → G3 → merge. Không có dòng nào viết tay chen vào. Đây
là điều cần nói rõ khi báo cáo, vì nó là luận điểm của cả đề án chứ không phải
một chi tiết kỹ thuật: cái được chứng minh không phải "robot cân bằng được" —
thứ ấy nhà sản xuất đã làm — mà là **một quy trình sinh mã có kiểm soát đi được
tới sản phẩm chạy trên phần cứng thật**.

## Ba lỗi cuối, và cả ba cùng một hình dạng

Cả ba đều là mã **đúng công thức nhưng sai thứ tự hoặc sai hợp đồng**. Không cái
nào là "mô hình không biết điều khiển học".

| | Lỗi | Vì sao lọt |
|---|---|---|
| 1 | Chiều DIR ngược so với V1 → robot lao thẳng một phía | Suy ra từ `dir_forward_level` trong hồ sơ phần cứng thay vì chép bảng của V1. Suy luận đúng lý mà sai thực tế, vì hồ sơ mô tả *bo*, còn bảng mô tả *cách bo được lắp vào robot này* |
| 2 | `pid_compute` bị lượt sinh lại tự bỏ tham số `is_running` | Prompt **chưa bao giờ khai chữ ký**. Giao diện tồn tại ngầm, thừa kế từ lượt sinh trước, nên không có gì buộc giữ nguyên |
| 3 | Phép dò `self_balance_setpoint` chạy TRƯỚC vùng chết | Prompt nêu đủ hai khối nhưng không nêu **thứ tự**. V3 đặt vùng chết ở dòng 287, phép dò ở 302 |

Lỗi 3 đáng chú ý nhất vì nó **không lộ ra ở bài kiểm nào**. Đặt phép dò lên
trước thì trong vùng chết điểm đặt vẫn đi 0,0015 mỗi vòng = 0,375°/giây; với
`kp = 12` thì chưa tới một giây nó tự đẩy mình ra khỏi vùng chết, bị kéo vào,
rồi lại đẩy ra — một chu trình giới hạn do chính mã tạo ra, đúng thứ vùng chết
sinh ra để dập. Bắt được bằng cách đọc từng dòng đối chiếu V3 ở G3.

## Bài kiểm mà Agent tự thêm cho lỗi 3 thì YẾU

Tôi yêu cầu thêm bài canh "điểm đặt đứng yên trong vùng chết". Agent thêm
`test_deadband_keeps_setpoint_steady`, và nó **đỏ đúng lúc cần đỏ** ở vòng đầu.
Nhưng đọc kỹ thì nó chỉ chạy 10 vòng — chưa đủ để điểm đặt trôi ra khỏi vùng
chết, nên nó sẽ **xanh cả với mã sai**. Nó đỏ vì lý do khác.

G3 duyệt dựa trên đối chiếu mã với V3, không dựa vào bài kiểm ấy, và hạn chế
này được ghi thẳng vào ghi chú duyệt. Ghi lại ở đây vì đây là một dạng hỏng khó
thấy: **một bài kiểm xanh đúng lúc, vì lý do sai.** Nó nguy hiểm hơn bài kiểm
đỏ, vì lần sau không ai đọc lại nó nữa.

## SL-162 — nửa còn thiếu của SL-154

Lỗi 2 ở trên làm `test_app_balance.py` không dịch nổi. Cổng đỏ, vòng tự sửa mở,
chạy đủ **ba lượt**, cả ba vá vào `logic_pid` — tệp duy nhất nó được phép viết,
và là tệp không có lỗi nào.

Vòng vá không tự thoát được vì nó không biết: cổng `unittests` gộp mọi thất bại
vào MỘT `ToolError` không mang `file`. Với chừng ấy thông tin thì vá mù ba lượt
là hành vi hợp lý nhất nó làm được.

**Đã sửa** (TC-123, 12 bài):

* `unittests` đọc `FAILED <tệp>::<bài>` và `ERROR <tệp>` vào
  `metrics["failing_files"]`. `ERROR` là dạng lỗi THU THẬP — đúng dạng mà lỗi
  biên dịch chéo module hiện ra;
* `run_module` thêm hạng dừng thứ ba cạnh `env_error` và `config_error`: mọi
  tệp đỏ đều ngoài `tep_can_sinh(module_id)` → `blocked` ngay.

Chỗ sửa thật nằm ở **cổng**, không ở vòng vá. Thêm luật cho vòng vá mà cổng vẫn
không quy được lỗi về tệp thì luật ấy không có dữ liệu để chạy.

Và nó ngả về phía **vá** khi không chắc: chặn nhầm thì dừng cả dây chuyền và
đòi người, vá nhầm thì tốn lượt gọi. Hai hạng sai không ngang giá.

## Việc kế tiếp

**~~1 — Canh hợp đồng gọi cho MỌI module~~ — ĐÃ LÀM** cùng phiên, SL-163 /
TC-124. `eaa/contract.py` so khai báo header vừa sinh với bản trên `main`; mất
một hàm hoặc đổi chữ ký là cổng đỏ, kèm câu chỉ thẳng việc phải làm. Nó đi vào
đường VÁ chứ không đường CHẶN — khác SL-162 có chủ ý, vì đây là mã của chính
module ấy và nó sửa được. Lời dặn trong `prompts/logic_pid.md` vẫn giữ, nhưng
giờ nó là hàng rào thứ hai chứ không phải hàng rào duy nhất.

**2 — Ghi lại 10 fixture E2E TC-15.** Nợ từ trước, chưa động tới. Prompt đổi thì
băm đổi, bộ phát lại cố ý không bịa phản hồi. Chạy
`scripts/record_e2e_fixture.py` với mô hình thật.

**3 — Đo giữ nhịp trên bo.** ISR bước chạy 50 kHz trên AVR 16 MHz — 320 chu kỳ
mỗi lần. Chưa ai đo nó ăn bao nhiêu CPU. Robot đứng được không chứng minh nhịp
4 ms được giữ, chỉ chứng minh nó đủ gần. Số này cần cho chương đánh giá.

**4 — `app_init()` không đặt lại `missed_samples`.** Lỗi tiềm ẩn, chưa cắn trên
bo vì `app_init` chỉ chạy một lần. Sẽ cắn ngay khi có đường khởi động lại mềm.

## Trạng thái

Bảy module đã merge; `drv_uart` và `app_telemetry` chưa cần để robot đứng.

Giao thức bíp hiện tại: **1 bíp** → bấm nút → đo trôi con quay 500 mẫu (giữ
robot **YÊN**, không cần thẳng) → **2 bíp** → dựng thẳng, robot tự vào vòng cân
bằng khi `|góc| < 0,5°` → thả tay.

Mốc gia tốc `ACCEL_BALANCE_OFFSET = -535` là **hằng số** trong `drv_imu`, đo một
lần bằng DS-02 ngày 03/09 ở dải ±4 g, có xuất xứ đầy đủ trong
`hardware_profile.yaml`. Đây là chỗ SL-160 sửa, và là điều kiện để cổng `±0,5°`
có nghĩa.

## Ba tài liệu nên đọc cùng bản này

* [`docs/CAI_DAT_VA_CHAY.md`](CAI_DAT_VA_CHAY.md) — máy mới tải kho về thì bắt đầu
  từ đây: cài đặt, công cụ, và trọn luồng tới lúc firmware nằm trên bo.

* `docs/SAI_LECH_THIET_KE.md` — 164 mục, mỗi mục một lỗi và bài kiểm canh nó.
  Đây là dữ liệu gốc của chương đánh giá, không phải phụ lục.
* `docs/DANH_GIA_NANG_LUC_AGENT.md` — Agent tự làm được gì, bảy giới hạn còn
  lại, và phương pháp huấn luyện rút ra.
* `docs/NHAT_KY_TEST_BLKLAB.md` — nhật ký từng lượt nạp trên bo thật.
