# Tiếp tục từ đây — bàn giao phiên 04/09/2026

> Phiên 04/09 nằm ở mục *"Phiên 04/09"* phía dưới. Mục 03/09 ngay sau đây giữ
> nguyên vì firmware đang chạy trên bo vẫn là bản của phiên ấy.

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

## Chốt phiên 03/09 — mở máy tối nay thì đọc mục này trước

Kho **sạch**, mọi thứ đã push lên `origin/main`. Mười một commit trong ngày:

```
7cca74c  docs: dùng một Agent khác để huấn luyện Agent này; README chỉ mục đầy đủ
2a88544  docs: chốt trạng thái phiên 03/09
c353e57  docs: hướng dẫn huấn luyện Agent cho bo mới hoặc chip mới
e8b6bd3  docs: bàn giao khớp với việc đã làm
35303da  docs: hướng dẫn cài đặt và chạy trọn luồng cho máy mới
c3bc048  README: kiến trúc C4 và bảng công nghệ
8680f11  Canh hợp đồng gọi (SL-163, TC-124)
128b760  Lỗi ngoài phạm vi không mở vòng tự sửa (SL-162, TC-123)
5b5f6be  Robot đứng được: PID khớp V3, chiều DIR khớp V1 (80ec03d0)
6ab4035  Phần của lớp là cách chia, không phải cái chặn (SL-161, TC-122)
5b9e197  Đánh giá năng lực Agent và phương pháp huấn luyện
```

Bộ test: **2.374 xanh, 10 đỏ** — đúng 10 bài E2E TC-15 nợ từ trước, không phát
sinh thoái lui nào. Firmware trên bo: `80ec03d0d4`, robot đứng được.

### Một cảnh báo đang bật, và nó đúng

`eaa status` đang báo **TRÔI hồ sơ phần cứng**:

```
⚠ TRÔI: hồ sơ phần cứng trên đĩa băm sha256:5efc569bb1ed…
  Bảng chân LÀ kiến trúc: đổi một chân là đổi mọi module chạm vào chân đó.
  Chốt lại qua gate G1.
```

Nguyên nhân: `ACCEL_BALANCE_OFFSET = -535` được thêm vào `hardware_profile.yaml`
sau khi G1 đã duyệt, và **chưa ai duyệt lại**. Hệ thống nói đúng — nó không
biết thứ vừa thêm là một hằng số vô hại hay một chân bị đổi.

Việc phải làm, một lệnh:

```bash
eaa gate show G1        # đọc diff hồ sơ
eaa gate approve G1 --actor "Vũ Trí Công" --expect <băm vừa xem>
```

Đừng bỏ qua nó. Cảnh báo bị lờ đi hai lần là cảnh báo không còn ai đọc.

### Ba việc engine đã làm trong phiên

| | Chỗ sai | Chỗ sửa |
|---|---|---|
| **SL-162** | Vòng tự sửa đốt cả ba lượt vào lỗi của module khác | Cổng `unittests` quy lỗi về tệp (`metrics["failing_files"]`); `run_module` thêm hạng dừng thứ ba. **TC-123, 12 bài** |
| **SL-163** | Không gì canh hợp đồng gọi của module sinh lại | `eaa/contract.py` so khai báo header với bản trên `main`. Vào đường VÁ, chạy TRƯỚC chuỗi cổng. **TC-124, 16 bài** |
| **SL-164** | Docstring `eaa/agent.py` mô tả một bản `TOOLBOX` không còn tồn tại | Bất biến KHÔNG bị phá — không lệnh DUYỆT nào với tới được. Sửa lời cho khớp mã, thêm 2 bài canh cả hai chiều |

### Bốn tài liệu mới hoặc viết lại

* **`README.md`** — kiến trúc C4 (ba sơ đồ Mermaid), bảng công nghệ kèm cả thứ
  KHÔNG dùng và vì sao, phần Tiến độ quanh mốc robot đứng được, và mục *Tương
  tác bằng ngôn ngữ tự nhiên*.
* **`docs/CAI_DAT_VA_CHAY.md`** — máy mới tải kho về: cài đặt và chạy trọn
  luồng, hai đường A/B, mười ba sự cố thường gặp.
* **`docs/HUAN_LUYEN_AGENT_CHO_BO_MOI.md`** — huấn luyện thủ công cho bo mới
  hoặc chip mới. Ba phần: dựng dự án mới (§1–7), dựng Platform Pack (§8), và
  **dùng một Agent khác để làm việc ấy** (§9–12) — ranh giới, quy trình năm
  bước, ba mẫu câu giao việc, bốn cách hỏng đã gặp thật.
* **`README.md`** còn được thay mục đọc tài liệu bằng **chỉ mục đầy đủ**: bảng
  ba câu hỏi đầu tiên của người vừa tải kho về, rồi bốn nhóm tài liệu, mọi
  đường dẫn là link bấm được.
* **`docs/DANH_GIA_NANG_LUC_AGENT.md`** — số liệu đếm lại từ dữ liệu, thêm §3.8
  về bài kiểm xanh vì lý do sai.

## Phiên 04/09 — rà soát năng lực, bốn việc, và đổi model nền

Kho **sạch**: `pytest -q` → **2.494 xanh, 0 đỏ**. Lần đầu không còn bài đỏ nào
kể từ 01/09.

### Rà soát bảng năng lực

`scripts/kiem_bang_nang_luc.py` — kiểm bảng bằng máy, bốn phép. Phép đáng giá
nhất là phép thứ tư: **mã khai trong bảng có ai gọi không**. Ba phép đầu hỏi
"thứ này có tồn tại không"; phép thứ tư hỏi "Agent có đường nào chạy tới nó".

Nó tìm ra hai module mồ côi và 9 dòng khai quá lời, cộng 6 nghiệp vụ bảng chưa
từng có. Sheet Khoảng trống từ 0 → 15 dòng, nay còn **7**. Chi tiết:
[`docs/RA_SOAT_NANG_LUC_04_09.md`](RA_SOAT_NANG_LUC_04_09.md).

### Bốn việc đã làm

| | Việc | Bài kiểm |
|---|---|---|
| **SL-167** | Lời gọi liên module bị đánh rơi — `app_init()` mất 4 lời gọi khởi tạo, firmware câm, 33 bài kiểm vẫn xanh | TC-127, 33 bài |
| **SL-168** | Đo độ nhạy: chạy bộ kiểm MỚI trên mã vừa bị đánh đỏ | TC-128, 28 bài |
| **SL-169** | Nối thang gỡ lỗi cài vào `doctor` — 7 dòng C5 lên ĐỦ | TC-129, 16 bài |
| **SL-170** | Đổi model nền sang `gemini-3.8-flash`, và bộ đếm token ra thiếu phần suy nghĩ | TC-130, 12 bài |

Mỗi bộ đều qua **kiểm đột biến**: cố ý làm hỏng mã rồi xác nhận đúng bài kiểm
đỏ. Một lần đột biến đi qua được — đọc lại thì lỗi ở phép đột biến, nhưng chính
lần ấy làm lộ một bài canh yếu ở TC-127 và bài ấy đã được siết.

### Model nền: `gemini-3.8-flash`

Mã model **xác minh thật** bằng ListModels + một lượt `generateContent`, không
đoán chuỗi. Vào ≤ 1.048.576, ra ≤ 65.536.

Chính lượt gọi thử làm lộ một lỗi thật: nó trả về đúng chữ `OK` mà báo
`candidatesTokenCount = 1`, `thoughtsTokenCount = 92`. `GeminiClient` chỉ đọc
`candidatesTokenCount`, nên nó đếm 1 trong khi 93 token đã sinh ra và tính tiền.
`llm_calls.jsonl` và `TokenBudget` đều đứng trên con số ấy. Với Pro 3.1 khoảng
lệch không rõ như vậy — lỗi sống được tới đúng ngày đổi model.

**Không sửa lại quá khứ:** `project_state.json`, `llm_calls.jsonl`,
`kpi_log.csv` và câu README *"robot đứng được trên AVR với
`gemini-3.1-pro-preview`"* giữ nguyên. Pro 3.1 vẫn trong danh mục, và
`KHUYEN_NGHI` có mục *"dựng lại số liệu Chương 3"* trỏ về nó.

`.env` cục bộ đã đổi `EAA_LLM_MODEL=gemini-3.8-flash` (tệp này không vào Git).

### Fixture TC-15 đã ghi lại

Chạy `scripts/record_e2e_fixture.py` với mô hình thật. Cố ý làm **sau** khi đổi
model, nên nó gánh hai việc: trả nợ 10 bài đỏ, và là lượt chạy trọn vòng lặp
đầu tiên trên Flash 3.8. Cả hai module qua đủ bốn cổng, **0 vòng tự sửa**.

Số token của fixture mới **không so trực tiếp được** với fixture cũ: luật đếm
vừa đổi ở SL-170. Chưa có phép A/B nào giữa hai model, và không nên nói là có.

## Việc kế tiếp

**1 — N-908: phân biệt "mã tôi sai" với "bài kiểm tôi sai".** Điểm yếu lớn nhất
còn lại. 3 trong 12 lần từ chối G3 là mã tự chỉnh cho vừa đồ đo của chính nó, và
cả ba qua sạch bốn cổng.

**2 — Nối `lifecycle.py` vào một lệnh** (vd `eaa knowledge stale`). Xong cả
N-036 lẫn N-100. Hiện sửa một datasheet thì không lệnh nào trả lời được "mã nào
bị ảnh hưởng".

**3 — N-913: số đo phần cứng chảy ngược vào prompt.** Đắt nhất trong ba, vì nó
đụng bộ ghép prompt và gate tri thức.

**4 — Duyệt lại G1 cho hồ sơ phần cứng.** Cảnh báo TRÔI vẫn đang bật, xem mục
phiên 03/09 ở trên. Chưa làm.

**5 — Đo giữ nhịp trên bo.** ISR bước 50 kHz trên AVR 16 MHz, chưa ai đo nó ăn
bao nhiêu CPU.

**6 — `app_init()` không đặt lại `missed_samples`.** Lỗi tiềm ẩn, chưa cắn vì
`app_init` chỉ chạy một lần.

**7 — Sinh lại 7 module thật của `robot_balance` bằng Flash 3.8** nếu muốn có
một phép A/B có nghĩa giữa hai model. Hai module demo qua cổng dễ, không đủ nói
lên điều gì.

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

* `docs/SAI_LECH_THIET_KE.md` — 170 mục, mỗi mục một lỗi và bài kiểm canh nó.
  Đây là dữ liệu gốc của chương đánh giá, không phải phụ lục.
* `docs/DANH_GIA_NANG_LUC_AGENT.md` — Agent tự làm được gì, bảy giới hạn còn
  lại, và phương pháp huấn luyện rút ra.
* `docs/NHAT_KY_TEST_BLKLAB.md` — nhật ký từng lượt nạp trên bo thật.
