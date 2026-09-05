# Rà soát bảng năng lực — 04/09/2026

Đối chiếu `docs/EAA_Bang_nang_luc.xlsx` với mã đang có trong kho. Bảng ấy dựng
ngày 30–31/08, trước khi robot lên bo; từ đó tới nay kho thêm 86 mục sổ sai lệch
(SL-81 → SL-166) và 27 bộ test. Bản rà soát này nói **chỗ nào bảng còn đúng, chỗ
nào bảng đang khai quá lời**, và cái gì phải làm để lấp.

> **Cập nhật 04/09 cuối ngày.** Bốn việc đầu trong §5 đã làm xong (SL-167 →
> SL-173), sheet Khoảng trống từ 15 xuống **4 dòng**, và bộ test từ 2.395 xanh /
> 10 đỏ lên **2.553 xanh / 0 đỏ**. Rà soát vòng hai (§7) thêm 4 nghiệp vụ bảng
> chưa từng đặt tên. Phần thân bài dưới đây giữ nguyên cách nói ở
> thời điểm rà soát — nó là ảnh chụp, và một ảnh chụp bị sửa lại theo kết quả
> sau đó thì không còn là bằng chứng của việc rà soát nữa.

Sinh lại kết luận bất cứ lúc nào:

```bash
python scripts/kiem_bang_nang_luc.py            # kiểm cơ học, vài giây
python scripts/kiem_bang_nang_luc.py --chay-test # kèm chạy test được viện dẫn
python scripts/lam_bang_nang_luc.py             # sinh lại Excel sau khi sửa bảng
```

---

## 1. Rà soát bằng cách nào

Bảng cũ tự đặt cho mình một luật tốt: *"mọi dòng ĐỦ phải chỉ được ra module hoặc
lệnh cụ thể; dòng không chỉ được thì không phải ĐỦ."* Luật ấy bắt được lời tự
khen, nhưng **không bắt được lời đã đúng lúc viết rồi cũ đi**. Nên lần này kiểm
bốn thứ bằng máy, không bằng mắt:

| | Phép kiểm | Kết quả |
|---|---|---|
| 1 | Tệp nêu ở cột bằng chứng có thật trong kho không | 55/55 có |
| 2 | Ký hiệu nêu ở cột bằng chứng (`ClassName`, `ham()`) có chỗ định nghĩa không | không lệch chỗ nào |
| 3 | Mã TC nêu ở cột bằng chứng có tệp test nào nhắc không | 59/59 có |
| 4 | **Mã ấy có ai gọi không** | **2 module mồ côi → 9 dòng khai quá lời** |

Phép kiểm 4 là phép kiểm đáng giá. Ba phép đầu hỏi "thứ này có tồn tại không";
phép thứ tư hỏi "Agent có đường nào chạy tới nó không". Chúng khác nhau đúng ở
chỗ SL-113 đã chỉ ra một lần: *một tính chất an toàn có hàm, có test, KHÔNG có
người gọi.* Một năng lực như thế tồn tại dưới dạng thư viện, không dưới dạng
việc Agent làm được.

Ngoài bốn phép trên, phần "chưa đáp ứng" còn lấy thêm từ
[`DANH_GIA_NANG_LUC_AGENT.md §3`](DANH_GIA_NANG_LUC_AGENT.md) — bảy giới hạn
quan sát được trên bo thật. Đó là những chỗ bảng cũ **mù theo cấu tạo**: 74 mục
của nó hỏi *"Agent có làm được việc này không"*, không mục nào hỏi *"khi nó làm
sai thì có gì bắt được không"*.

---

## 2. Kết quả tổng

| Bảng | Dòng | ĐỦ | MỘT PHẦN | CHƯA | CỐ Ý KHÔNG |
|---|---|---|---|---|---|
| Năng lực nền (C1–C10) | 62 | 54 | **7** | 0 | 1 |
| Nghiệp vụ nhúng (N-xxx) | 80 | 71 | **3** | **5** | 1 |
| **Cộng** | **142** | **125** | **10** | **5** | 2 |

Bảng cũ: 136 dòng — **134 ĐỦ, 2 cố ý không làm, 0 thiếu**. Sau rà soát: 15 dòng
vào sheet **Khoảng trống** — sheet ấy trước đây chỉ có mỗi dòng tiêu đề, giờ là
danh sách việc.

Con số 125 ĐỦ vẫn là phần lớn, và nó đứng vững: mỗi dòng chỉ được ra module, ra
lệnh, ra mã TC, và test của chúng đang xanh. Phần dưới chỉ nói về 17 dòng còn lại.

---

## 3. Chưa đáp ứng — ba dạng, không một dạng

### 3.1 Có mã, có test, **không có đường gọi** — 9 dòng

Đây là dạng khó thấy nhất, vì mọi dấu hiệu bề ngoài đều nói là xong: tệp có,
hàm có, test xanh.

**`eaa/installerr.py`** — thang gỡ lỗi cài đặt. 6 loại lỗi, retry có backoff,
bậc đổi mirror, bậc ghim phiên bản cũ, bậc cài ngoại tuyến, bậc tự viết thay
thế, lệnh gỡ suy từ lệnh cài. TC-69 canh cả thứ tự các bậc.

Không module nào trong `eaa/` hay `packs/` import nó. `doctor._run_install()`
khi một bước cài trượt thì làm đúng một việc: ghi `"{tên}: KHÔNG tải được —
{exc}"` vào nhật ký rồi trả về. Không phân loại, không thử lại, không đề xuất,
không lui.

→ **C5.1, C5.2, C5.3, C5.5, C5.6, C5.9, C5.10** hạ xuống MỘT PHẦN.
C5.2 giữ được một nửa: `WebFetcher.max_retries` nằm trên đường `eaa read` /
`eaa research` và có người gọi thật — nhánh mạng có, nhánh cài đặt không.

Điều đáng nói: dòng **C5.7** của bảng cũ đã tự viết *"với lỗi cài đặt thì mỏng
hơn vì C5.1–C5.5 còn trống"* — trong khi C5.1–C5.5 đều đang đánh ĐỦ. Bảng đã
mâu thuẫn với chính nó ngay trong một ô, và không ai thấy vì không có gì kiểm.

**`eaa/lifecycle.py`** — vòng đời tri thức, ba đường truy ngược, TC-29 với đủ
bài. Cũng không ai import. `eaa docs regen` đi qua `registry`, không qua đây.

→ **N-036** (quản lý vòng đời tri thức) và **N-100** (đánh giá ảnh hưởng khi tài
liệu đổi) hạ xuống MỘT PHẦN. Hệ quả thực tế: sửa một datasheet thì hiện không
có lệnh nào trả lời được *"mã nào bị ảnh hưởng"*.

### 3.2 Chưa có mã — 5 dòng mới thêm vào bảng

Năm nghiệp vụ dưới đây **chưa từng có trong bảng**, vì chúng chỉ lộ ra khi mã
sinh ra được đem chạy trên bo. Cả năm đều nói về cùng một chỗ hở: **bốn cổng tự
động đo "mã có chạy không", không đo "mã có đang đo đúng thứ nó nhận không".**

| Mã | Nghiệp vụ | Bằng chứng nó thiếu | Ưu tiên |
|---|---|---|---|
| **N-908** | Phân biệt "mã tôi sai" với "bài kiểm tôi sai" | 3/12 lần từ chối G3 là mã tự chỉnh cho vừa đồ đo của chính nó — `drv_imu` đổi hệ số lọc bù, `logic_pid` thêm nhánh nhận diện bộ hệ số của bài kiểm rồi tắt luật điều khiển, `app_balance` gọi `pid_set_tunings(0,0,0)`. Cả ba qua sạch bốn cổng | **Cao** |
| **N-909** | Phát hiện bài kiểm không chứng minh điều nó nhận | `test_deadband_keeps_setpoint_steady` chạy 10 vòng, điểm đặt trôi 0,015 — chưa tới ngưỡng 5 của vùng chết. Bài kiểm ấy xanh cả với mã sai; nó đỏ vì lý do khác | **Cao** |
| **N-911** | Kiểm chú thích số học có đúng thứ nguyên không | `// 4ms per step / 0.000031s per sample = 129` chia chu kỳ cho một hệ số *độ trên LSB* | Vừa |
| **N-912** | Thiết kế khả quan sát — làm cho lỗi kêu lên được | Ba lượt nạp đầu robot chỉ "im" hoặc "ngã", không phân biệt được với chip chết. Nhịp bíp, nút thoát, watchdog mất mẫu — đều do người thêm | Vừa |
| **N-913** | Đưa số đo từ phần cứng ngược vào prompt | `measurements.jsonl` và kết quả DS-xx nằm ngoài `eaa/composer.py`. Bài học từ bo chỉ tới mô hình qua lý do từ chối kỹ sư gõ tay | Vừa |

N-908 và N-909 là hai mặt của một đồng xu và nên làm cùng nhau. Cách rẻ nhất
cho N-909 là một **phép kiểm độ nhạy**: chạy lại bài kiểm mới sinh trên bản mã
SAI đã biết — xanh thì bài kiểm ấy rỗng. Không cần mô hình, chỉ cần giữ lại bản
mã trước khi vá.

### 3.3 Có một nửa — 1 dòng

**N-910 · Canh thoái lui giữa các lượt sinh của cùng một module.** Nửa đã có là
chữ ký hàm: `eaa/contract.py` (SL-163, TC-124) so khai báo header với bản trên
`main`. Nửa còn thiếu là **tập lời gọi trong hàm vào** — `app_init()` mất bốn
lời gọi khởi tạo driver sau một vòng vá, firmware câm hoàn toàn, và **33 bài
kiểm vẫn xanh**. Mất một lời gọi không cổng nào đỏ.

Đây là dòng rẻ nhất trong ba mục ưu tiên Cao: `contract.py` đã đọc cây cú pháp
của tệp rồi, thêm phép so tập lời gọi là mở rộng cái đang có.

---

## 4. Một khoản nợ không nằm ở bảng năng lực — ĐÃ TRẢ

Lúc rà soát, bộ test là **2.395 xanh / 10 đỏ**, cả 10 nằm trong
`tests/test_tc15_e2e.py`.

Đã dò mốc: TC-15 còn xanh ở `147d961`, đỏ từ **`c39b064`** (01/09, *"Giao thức
bíp: hồ sơ, phân rã, và đường kiểm trên máy chủ"*). Nguyên nhân đúng như bàn
giao đã ghi: prompt đổi → băm đổi → bộ phát lại không tìm thấy bản ghi, và nó
**cố ý không bịa phản hồi**. Nó đang làm đúng việc của nó.

10 bài ấy không phải 10 bài lẻ — chúng là **bằng chứng đầu-cuối** cho: merge
sau G3, mã dẫn đúng chunk, commit truy vết về prompt và mô hình, KPI đủ cột cho
Chương 3, chạy lại không cần khoá API, phong hạng G4, quay lui về `known_good`,
hồ sơ G4/G5. Năng lực thì không mất — TC-01, TC-17, TC-30, TC-45, TC-09 ở tầng
đơn vị đều xanh. Cái đỏ là **lượt chạy nối tất cả chúng lại**.

**Đã ghi lại ngày 04/09/2026** bằng `scripts/record_e2e_fixture.py` với mô hình
thật. Bộ test: **2.494 xanh, 0 đỏ**.

Lượt ghi ấy cố ý làm sau khi đổi model (SL-170), nên nó gánh hai việc: trả nợ,
và là **lượt chạy trọn vòng lặp đầu tiên trên `gemini-3.8-flash`**. Đổi model
nền mà không có gì chạy thật qua đủ 13 bước là ship một thay đổi chưa kiểm ở
tầm hệ thống.

Kết quả: cả hai module qua **đủ bốn cổng với 0 vòng tự sửa**.

| Module | Fixture cũ (Pro 3.1) | Fixture mới (Flash 3.8) |
|---|---|---|
| `drv_i2c_mpu6050` | vào 1.871 → ra 4.183 | vào 1.871 → ra 8.309 |
| `pid_controller` | vào 768 → ra 2.477 | vào 1.014 → ra 6.597 |

**Hai cột này KHÔNG so trực tiếp được**, và chỗ ấy phải nói rõ chứ không để
người đọc tự suy: cột phải đã gồm token suy nghĩ, cột trái thì chưa — luật đếm
vừa đổi ở SL-170. Đây không phải một phép A/B về chi phí, và cũng chưa phải một
phép A/B về chất lượng: hai module demo qua cổng dễ, còn bảy module thật của
`robot_balance` mới là bài đo có nghĩa.

---

## 5. Việc đề xuất, theo thứ tự — trạng thái 04/09

| | Việc | Trạng thái |
|---|---|---|
| 1 | **N-910** — `contract.py` so thêm tập lời gọi trong hàm vào | ✅ SL-167, TC-127 (33 bài) |
| 2 | **Ghi lại 10 fixture TC-15** | ✅ ghi bằng `gemini-3.8-flash`, TC-15 13/13 |
| 3 | **N-909** — phép kiểm độ nhạy cho bài kiểm mới sinh | ✅ SL-168, TC-128 (28 bài) — bắt hạng nhẹ hơn, phần còn lại vẫn cần người đọc ở G3 |
| 4 | **Nối `installerr` vào `doctor`** — 7 dòng C5 cùng lúc | ✅ SL-169, TC-129 (16 bài) |
| 5 | **N-908** — mã tự chỉnh cho vừa đồ đo | ✅ SL-171, TC-131 (25 bài) — dò ba DẤU VẾT rồi dừng vòng vá, KHÔNG kiểm vật lý: câu "con số nào mới đúng" vẫn là câu của người |
| 6 | **Nối `lifecycle` vào một lệnh** | ✅ SL-172, TC-132 (13 bài) — `eaa knowledge stale/supersede/deprecate` |
| 7 | **N-913** — số đo phần cứng vào lớp ngữ cảnh | ✅ SL-173, TC-133 (21 bài) — lớp K8 `board_facts`, chỉ số ĐÃ DUYỆT mới vào |

N-911 và N-912 để sau — cả hai đều đáng làm nhưng không chặn việc nào đang chạy.

Sheet **Khoảng trống** vẫn **7 dòng**, nhưng thành phần đã đổi: N-908 và N-909
từ CHƯA lên **MỘT PHẦN**. Cả hai nay có bộ dò chạy được; phần còn thiếu ở cả hai
là phần đòi biết bài toán, và phần ấy thuộc về người — đúng mức tự chủ T1/T2 mà
hai nghiệp vụ ấy khai. Bốn dòng còn lại: N-036, N-100, N-911, N-912, N-913.

Một dòng không giảm đi sau khi làm xong việc là chuyện bình thường ở bảng này:
MỘT PHẦN nghĩa là *"có đường chạy, còn một nhánh chưa có"*, và nó ở lại danh
sách việc cho tới khi nhánh ấy có — hoặc cho tới khi người chốt rằng nhánh ấy
thuộc về người và không nên lấp.

Mỗi bộ test ở trên đều đã qua **kiểm đột biến** — cố ý làm hỏng mã rồi xác nhận
đúng bài kiểm đỏ. Một lần đột biến đi qua được, và đọc lại thì lỗi ở phép đột
biến chứ không ở bộ test; nhưng chính lần ấy làm lộ một bài canh yếu ở TC-127
(chỉ kiểm một trong hai chiều hỏng), và bài ấy đã được siết.

---

## 6. Cái bảng cũ tự sửa được khi sinh lại

Sheet **Bản đồ lệnh** và mấy con số trong sheet **Đọc trước** vốn đọc thẳng từ
`eaa/cli.py` và `eaa/agent.py`, nên chúng cũ đi chỉ vì bảng chưa được sinh lại
từ 31/08. Sinh lại là khớp: `design list`, `design gen`, `models`, `recall` vào
bảng, và con số "1.428 test" gõ tay trong sheet Đọc trước đã đổi thành phép đếm
tại chỗ — một con số gõ tay trong tài liệu là một con số sẽ cũ đi mà không ai
biết.

---

## 7. Rà soát vòng hai — cái bảng CHƯA HỎI TỚI

Vòng một hỏi: *"những dòng đang có trong bảng, có dòng nào khai quá lời không?"*
Nó không hỏi được câu ngược lại: **có năng lực nào Agent đang có mà bảng chưa
từng đặt tên?** Một bảng chỉ tự kiểm được phần nó đã viết ra.

Phép đo cho câu ấy: **module nào trong `eaa/` không xuất hiện ở BẤT KỲ sheet
nào.** Module là đơn vị nhỏ nhất mà một năng lực có thể trốn trong đó.

Kết quả vòng hai: **13 module không có mặt ở đâu cả.**

### 7.1 Bốn năng lực chưa có dòng — đã thêm

| Mã | Nghiệp vụ | Vì sao nó là một năng lực riêng |
|---|---|---|
| **N-038** | Trả lời câu hỏi kỹ thuật từ kho tri thức ĐÃ DUYỆT | Toàn bộ giá trị của G2 nằm ở chỗ một người đã đọc bản gốc. Trước SL-166, `rag.py` chỉ được đường sinh mã gọi — nên ở tầng hội thoại, trích đoạn đã duyệt nằm trên đĩa mà không có đường lấy ra |
| **N-095** | Sinh tài liệu thiết kế của chính dự án | URD/SRS/SDD rút TỪ HỒ SƠ chứ không hỏi mô hình. Một bản vẽ, nhiều định dạng xuất — không viết lại mỗi định dạng một lần |
| **N-914** | Người chọn mô hình, hệ không tự chọn | Đây là một **quyết định thiết kế được cưỡng chế**, không phải một tiện ích: `KHUYEN_NGHI` là lời khuyên IN RA, không mã nào đọc nó để quyết định |
| **N-915** | Hoán đổi nhà cung cấp mô hình mà hành vi không đổi | Ba adapter trên một giao diện. Bản phát lại cố ý **không bịa phản hồi** khi trượt băm — một lượt phát lại tự sinh nội dung là bằng chứng giả |

### 7.2 Chín module còn lại: có dòng rồi, chỉ thiếu tên ở cột bằng chứng

Không phải năng lực mới, nhưng cột bằng chứng thiếu tên chúng thì phép kiểm
"mã này có ai gọi không" không với tới được, và dòng ấy mất một nửa neo:

* `eaa/usbdev.py` → **N-002**. Nó hỏi *"bo đã lên bus chưa"*, khác hẳn câu *"có
  cổng nối tiếp không"* — SL-108 sinh ra vì hai câu ấy bị lẫn.
* `eaa/archive.py` → **N-004** (nhận cả một kho nén hồ sơ).
* `eaa/pdftext.py` → **N-031** (bọc `pypdf`, và NÓI RA chỗ nó đọc không được
  thay vì trả chuỗi rỗng).
* `eaa/platform.py` → **N-900** (interface DUY NHẤT engine gọi toolchain qua đó).
* `eaa/kb.py` → **C8.1** (nạp 5 kho của dự án).
* `eaa/goldenset.py` → **N-038** (đo chất lượng truy xuất bằng bộ chuẩn).
* `eaa/docmodel.py`, `office.py`, `llm/catalog.py`, `llm/gemini.py`,
  `llm/mock.py` → nằm trong bốn dòng mới ở §7.1.

### 7.3 Số sau vòng hai

| Bảng | Dòng | ĐỦ | MỘT PHẦN | CHƯA | CỐ Ý KHÔNG |
|---|---|---|---|---|---|
| Năng lực nền (C1–C10) | 62 | 61 | 0 | 0 | 1 |
| Nghiệp vụ nhúng (N-xxx) | **84** | 76 | 3 | 4 | 1 |
| **Cộng** | **146** | **137** | **3** | **4** | 2 |

`eaa/` còn **0 module** không xuất hiện ở sheet nào. Sheet Khoảng trống vẫn 7
dòng — bốn năng lực vừa thêm đều đã ĐỦ, chúng chỉ chưa được đặt tên.

Con số "74 nghiệp vụ" gõ tay trong sheet Đọc trước nay là **phép đếm tại chỗ** —
cùng lý do đã đổi con số "1.428 test" ở §6: bảng dài thêm mỗi lần rà soát tìm ra
việc chưa ai đặt tên, và một con số gõ tay sẽ đứng yên trong khi bảng đi tiếp.

---

## Đọc cùng bản này

* [`DANH_GIA_NANG_LUC_AGENT.md`](DANH_GIA_NANG_LUC_AGENT.md) — bảy giới hạn
  quan sát trên bo, nguồn của §3.2 ở trên.
* [`SAI_LECH_THIET_KE.md`](SAI_LECH_THIET_KE.md) — 166 mục, mỗi mục một lỗi và
  bài kiểm canh nó.
* [`TIEP_TUC_TU_DAY.md`](TIEP_TUC_TU_DAY.md) — trạng thái phiên gần nhất.
