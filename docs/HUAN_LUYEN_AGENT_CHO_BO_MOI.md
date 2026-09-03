# Huấn luyện Agent cho một bo mạch mới hoặc một chip mới

Tài liệu này dành cho người muốn đưa Agent sang một phần cứng nó chưa từng
thấy. Nó đi từng bước, và nói cả những chỗ **đừng làm** — vì phần lớn công sức
phí phạm trong dự án này đến từ việc sửa đúng vấn đề ở sai chỗ.

> **"Huấn luyện" ở đây không phải tinh chỉnh trọng số mô hình.** Mô hình được
> ghim phiên bản và gọi stateless. Thứ được huấn luyện là **hệ thống quanh mô
> hình**: prompt, cổng kiểm chứng, bất biến engine, và bộ luật của Platform
> Pack. Xem [`DANH_GIA_NANG_LUC_AGENT.md`](DANH_GIA_NANG_LUC_AGENT.md) §4 cho
> phần lý thuyết; tài liệu này là phần thao tác.

---

## 0. Trước hết: bạn đang ở tình huống nào

Hai tình huống, khối lượng công việc **khác nhau một bậc**. Nhận sai tình huống
là cách phổ biến nhất để làm gấp mười lần việc cần làm.

| | Tình huống A | Tình huống B |
|---|---|---|
| **Là gì** | Bo mới, **chip cũ** (đã có Platform Pack) | **Họ chip mới**, chưa có Platform Pack |
| Ví dụ | Bo AVR khác, cùng ATmega328P | Chuyển từ AVR sang RISC-V, ESP32, PIC |
| Phải làm | Chỉ dựng **dự án mới** — §1 tới §7 | Dựng **Platform Pack** trước — §8 — rồi mới §1 |
| Công sức | Nửa ngày tới hai ngày | Ba tới bảy ngày |
| Sửa `eaa/` không? | **Không** | **Cũng không.** Nếu thấy cần thì xem §8.7 |

**Làm một mình hay có Agent trợ lý?** Phần lớn việc dưới đây giao được cho
một trợ lý lập trình (Claude Code, Codex…) — chính dự án mẫu này được dựng
như vậy. **Phần III (§9–§12)** nói cách làm, ranh giới nào không được vượt, và
bốn cách hỏng đã gặp thật.

Kiểm nhanh xem chip của bạn đã có pack chưa:

```bash
eaa packs                    # liệt kê pack đã cài và target mỗi pack nhận
```

Hiện có hai pack: `avr` (atmega328p) và `stm32` (stm32f469ni). Chip cùng họ
nhưng khác mã — ví dụ ATmega2560 — là **tình huống A rưỡi**: thêm một dòng vào
`targets:` của pack, kiểm lại số bộ nhớ, xong. Xem §8.6.

---

# PHẦN I — Tình huống A: bo mới trên chip đã có pack

## 1. Đừng bắt đầu bằng cách gõ. Bắt đầu bằng cách hỏi Agent

```bash
export EAA_HOME=$(pwd)
eaa brief --board "tên bo của bạn" --platform avr --ask
```

Agent **dò trước rồi mới hỏi**, và chỉ hỏi những gì máy không tự biết được. Nó
dựng ra hai tệp ở **dạng đề xuất**:

* `projects/<dự án>/hardware_profile.yaml`
* `projects/<dự án>/constraints.yaml`

Chưa có hiệu lực nào cho tới khi bạn duyệt G1. Đọc kỹ hai tệp này — **đây là
nơi mọi thứ về sau bắt nguồn.**

### Vì sao không nên tự viết tay hai tệp này ngay từ đầu

Bạn sẽ viết đúng những gì bạn đã biết, và bỏ sót đúng những gì bạn chưa biết
mình chưa biết. Để Agent đề xuất trước rồi bạn sửa thì mỗi chỗ bạn sửa là một
chỗ bạn **thật sự đã cân nhắc**, và chỗ bạn không sửa là chỗ bạn đã đọc và
đồng ý — khác hẳn với chỗ bạn chưa từng nghĩ tới.

## 2. Hồ sơ phần cứng — chỗ tốn công nhất, và đáng tốn

`hardware_profile.yaml` có sáu nhóm khoá. Đây là lược đồ thật, lấy từ dự án
mẫu:

```yaml
version: 3
project: robot_balance
mcu:
  part: atmega328p
  clock_hz: 16000000
  flash_bytes: 32768
  sram_bytes: 2048
  eeprom_bytes: 1024

peripherals:
  - id: timer1
    kind: timer
    width_bits: 16
    configured_by: [TCCR1A, TCCR1B, OCR1A, TIMSK1]
    note: "Ngắt chu kỳ cho vòng điều khiển và phát xung bước."

components: …        # linh kiện ngoài: IMU, driver động cơ, cảm biến
programmer: …        # cách nạp: giao thức, tốc độ
pin_map: …           # chân nào nối gì
pin_functions: …     # chức năng thay thế của từng chân
power: …             # nguồn, và chỗ ngắt được
mechanics: …         # hình học, nếu bài toán có phần cơ
```

**Khoá `id` của mỗi ngoại vi là thứ quan trọng nhất trong cả tệp.** Nó là tên
mà `eaa plan add --uses <id>` dùng để bắt xung đột tài nguyên. Đặt sai tên thì
hai module cùng chiếm một timer mà không ai báo, và bạn phát hiện ra ở bước
liên kết — tức sau khi đã đi qua sinh mã, bốn cổng và G3.

**`configured_by` không phải trang trí.** Nó là đường nối vào Knowledge Graph:
khi module chạm tới `TCCR1B`, hệ thống biết truy xuất trích đoạn datasheet nào,
và biết đòi chú thích `// ref: <chunk-id>` ở đúng dòng ấy.

### Ba chỗ người mới hay sai

1. **Ghi số danh nghĩa thay vì số đo.** `clock_hz: 16000000` phải là tần số
   **thật** của thạch anh trên bo bạn, không phải con số ghi trong datasheet
   của chip. Lệch 1% ở đây là lệch 1% ở mọi hằng số thời gian sinh ra sau đó.
2. **Bỏ trống `pin_functions`.** Rồi Agent đề xuất một bảng chân dùng chân đã
   bị chức năng khác chiếm, và nó không có cách nào biết.
3. **Chép hồ sơ của bo khác rồi sửa vài dòng.** Cái bạn quên sửa sẽ là cái sai,
   và nó sai một cách trông rất hợp lý.

## 3. Ràng buộc — mỗi điều cấm phải có luật phát hiện

`constraints.yaml`:

```yaml
version: 2
platform: avr
mcu: atmega328p
clock_hz: 16000000
limits:
  flash_pct_max: 80
  sram_pct_max: 60
forbidden:
  - "delay()"
  - "malloc/new"
  - recursion
style: …
acceptance: …
```

**Phân vai quan trọng:** `constraints.yaml` của dự án nói **cái gì** bị cấm;
`packs/<pack>/rules/forbidden.yaml` nói **phát hiện thế nào** trên họ chip ấy.
Mã luật (`id`) hai bên phải khớp đúng chữ.

Thêm một điều cấm mà pack không có luật khớp thì **cổng static báo hỏng chứ
không im lặng bỏ qua** — đó là chủ ý: một điều cấm không ai kiểm là một điều
cấm không tồn tại.

Nên khi bạn thêm điều cấm riêng cho bo mình, bạn phải làm cả hai đầu. Xem §8.3.

## 4. Duyệt G1 — và cách duyệt cho đúng

```bash
eaa gate show G1
eaa gate approve G1 --actor "Tên bạn" --expect <băm bạn vừa xem>
```

`--expect` neo lời duyệt vào **đúng nội dung bạn đã đọc**. Hồ sơ đổi giữa lúc
xem và lúc duyệt thì lệnh từ chối. Dùng nó — đây là lúc rẻ nhất để bắt một
thay đổi bạn không định duyệt.

## 5. Nạp tri thức — và vì sao chọn trang là việc của bạn

```bash
eaa sources need --lookup                    # tài liệu cần, kèm nguồn chính chủ
eaa errata lookup --rev <rev in trên chip>   # lỗi chip đã công bố cho ĐÚNG rev

eaa datasheet add datasheet.pdf \
    --device ATmega328P --peripheral twi \
    --pages 222-224 --topic "TWI bit rate"

eaa gate approve G2 --actor "Tên bạn"
```

**Bỏ trống `--pages` là nuốt cả tài liệu vào kho.** Đừng làm thế. Một datasheet
300 trang đưa hết vào kho thì mọi truy xuất về sau đều loãng, và ngân sách
8.000 token bị một trích đoạn không liên quan chiếm chỗ.

Chọn trang là việc của kỹ sư vì nó đòi biết **bài toán này cần biết gì** —
Agent không biết điều đó trước khi bạn nói.

`eaa errata lookup --rev` đáng chạy một lần cho mỗi lô chip. Một lỗi silicon đã
công bố mà không ai đọc sẽ trở thành ba ngày gỡ lỗi firmware.

## 6. Prompt của module — đây mới là chỗ "huấn luyện" thật sự diễn ra

Mỗi module có một tệp `projects/<dự án>/prompts/<module>.md`. **Đây là nơi bài
học từ phần cứng của bạn được ghi lại.**

Cấu trúc một tệp prompt đã trưởng thành, lấy từ dự án mẫu:

```markdown
---
id: logic_pid
description: một câu, để người đọc danh sách biết module này làm gì
---

### Chữ ký — HỢP ĐỒNG, không được đổi
```c
float pid_compute(float angle, float pid_setpoint, bool is_running);
```
Nêu rõ ai đang gọi, và hậu quả nếu đổi.

### Công thức, nguyên văn
Chép NGUYÊN VĂN từ mã tham chiếu nếu có. Đừng diễn giải.

### Những con số, và vì sao chúng là những con số ấy
`0.000031` gắn với chu kỳ 4 ms. Nói ra sự gắn kết đó.

### Thứ tự, khi thứ tự quan trọng
"Vùng chết chạy TRƯỚC phép dò điểm cân bằng" — kèm lý do vật lý.

### Bài kiểm phải chứng minh
Liệt kê từng điều. Đây là hợp đồng với cổng `unittests`.
```

### Bốn luật viết prompt, rút từ 164 lần sai

**1. Chép nguyên văn, đừng diễn giải.** Nếu bo của bạn có mã tham chiếu chạy
được — của nhà sản xuất, của một dự án mở — thì chép thẳng khối công thức vào
prompt. Diễn giải là chỗ ý nghĩa rò rỉ ra ngoài.

**2. Nói ra THỨ TỰ, không chỉ nói các thành phần.** Lỗi cuối cùng của dự án
mẫu — và là lỗi không cổng nào bắt được — là hai khối mã đúng cả hai mà đảo chỗ
cho nhau. Prompt nêu đủ cả hai khối, nhưng không nêu thứ tự.

**3. Mỗi con số phải kèm thứ nó gắn vào.** Đừng viết *"hệ số lọc 0,9996"*. Viết
*"0,9996/0,0004 gắn với chu kỳ 4 ms; đổi chu kỳ là phải tính lại"*. Mô hình sẽ
đổi những con số không có neo, và nó đổi để bài kiểm chạy qua.

**4. Nói ra cả điều KHÔNG được làm, kèm hậu quả.** *"Không tự đổi sang dấu phẩy
tĩnh"* là một lời cấm. *"Bộ ba hệ số gắn chặt với công thức sinh ra chúng; đổi
biểu diễn là đổi bài toán, và bộ số ấy không còn đúng nữa"* là một lời cấm có
lý do — và lời cấm có lý do sống lâu hơn.

### Nhưng đừng dừng ở prompt

Đây là điểm quan trọng nhất của cả tài liệu. **Prompt là mức 1 của thang leo
can thiệp, và mức 1 là mức yếu nhất.**

Bằng chứng đo được trong dự án này: `prompts/drv_imu.md` viết rõ *"Ba số ấy
KHÔNG được đổi để bài kiểm vừa số kỳ vọng"*. Mô hình đổi. Câu dặn ấy có mặt
trong prompt của **chính lượt sinh** đã đổi chúng.

| Mức | Hình thức | Độ bền | Dùng khi |
|---|---|---|---|
| 1 | Câu dặn trong prompt | Thấp nhất | Chỉ khi không mức nào cao hơn mã hoá được |
| 2 | Bài kiểm bắt buộc trong hợp đồng `host_test` | Trung bình | Hành vi kiểm được trên máy chủ |
| 3 | **Cổng kiểm chứng** | Cao | Vi phạm nhận ra được từ mã hoặc đầu ra |
| 4 | **Bất biến engine** | Cao nhất | Vi phạm phải là điều bất khả |

**Luôn leo từ dưới lên**, và tiêu chí chọn mức không phải *"cao nhất có thể"*
mà **"cao nhất mà vẫn không báo nhầm"** — một cổng hay báo nhầm sớm muộn cũng
bị tắt đi, và lúc ấy nó không bảo vệ được gì nữa.

## 7. Vòng huấn luyện — sáu bước, lặp cho tới khi hết sai

```bash
eaa plan add drv_imu --uses twi,imu
eaa interface drv_imu --write          # chốt hợp đồng gọi TRƯỚC
eaa gen drv_imu                        # sinh, chạy cổng, tự sửa ≤3, dừng ở G3
eaa gate show G3                       # ĐỌC MÃ
```

### Bước 1 — Đọc mã, đừng đọc màu bài kiểm

Bốn cổng đã xanh mới tới được G3. Việc của bạn ở đây là bắt những thứ cổng
không bắt được. Trong dự án mẫu, **43% lượt tới G3 bị từ chối**, và bốn dạng
lỗi hay gặp nhất đều **không cổng tự động nào bắt được**:

| Dạng | Trông như thế nào |
|---|---|
| Mã tự chỉnh đồ đo cho vừa mình | Vòng vá đổi hằng số vật lý để bài kiểm chạy qua |
| Đúng công thức, sai thứ tự | Mọi bài kiểm xanh; hành vi sai trên phần cứng |
| Phá hợp đồng gọi | Sinh lại module và bỏ bớt tham số |
| Bài kiểm xanh vì lý do sai | Bài kiểm trông đúng, chạy quá ngắn nên xanh cả với mã sai |

**Cách đọc nhanh mà vẫn bắt được:** so từng con số trong mã với từng con số
trong prompt. Con số nào trong mã mà không có trong prompt là con số mô hình tự
nghĩ ra — hỏi vì sao.

### Bước 2 — Từ chối cho đúng cách

```bash
eaa gate reject G3 --reason "nêu SAI Ở ĐÂU và VÌ SAO, không nêu phải làm gì"
```

Câu lý do này **có mặt nguyên văn trong prompt lần sinh lại**. Nó là kênh huấn
luyện chính, nên viết nó như viết cho một kỹ sư mới:

* ✅ *"Thứ tự sai: phép dò điểm cân bằng chạy TRƯỚC vùng chết. Mã tham chiếu đặt
  vùng chết ở dòng 287, phép dò ở 302 — phép dò phải đọc đầu ra ĐÃ bị vùng chết
  dập về 0. Đặt trước thì trong vùng chết điểm đặt vẫn đi 0,0015 mỗi vòng, tự
  tạo chu trình giới hạn."*
* ❌ *"Sai thứ tự, sửa lại đi."*

Câu thứ hai không dạy được gì, và lần sinh lại sẽ đoán.

### Bước 3 — Phân loại lần trượt TRƯỚC khi sửa

Ba loại, ba cách xử lý khác hẳn nhau. **Phân loại sai thì sửa sai chỗ:**

| Loại | Dấu hiệu | Xử lý |
|---|---|---|
| **Lỗi engine** | Cổng nói một đằng, mã làm một nẻo; thông báo chỉ sai chỗ | Ghi sổ sai lệch, sửa ở mức 3–4, viết bài kiểm canh |
| **Hành vi mô hình** | Mã hợp lệ nhưng lệch ý định; lặp lại ở nhiều module | Leo thang, ưu tiên mức 3 |
| **Đặc tả thiếu** | Mô hình làm **đúng** lời được dặn, mà lời ấy sai | Sửa `prompts/<module>.md`, ghi lý do vào G3 |

Loại thứ ba dễ bị đổ oan cho mô hình nhất, và nó chiếm phần lớn số lần trượt ở
một dự án mới. Trước khi trách mô hình, đọc lại câu bạn đã viết.

### Bước 4 — Sửa ở mức cao nhất mà không báo nhầm

Xem thang leo ở §6. Nếu bạn thấy mình viết thêm một câu dặn thứ ba vào prompt
cho **cùng một lỗi**, đó là dấu hiệu phải leo lên mức 3.

### Bước 5 — Sinh lại

```bash
eaa gen drv_imu                        # lý do từ chối đã nằm trong prompt
# module đã merge rồi thì mở lại trước:
eaa plan reopen drv_imu --reason "nêu rõ vì sao mở lại"
```

### Bước 6 — Ghi lại, kể cả khi đã sửa xong

Mỗi lần trượt đáng ghi một mục vào sổ sai lệch của bạn, trả lời sáu câu:

1. **Cách tìm** — triệu chứng nào dẫn tới nó
2. **Chuyện gì xảy ra** — mô tả cơ chế, không mô tả cảm giác
3. **Vì sao lọt** — chỗ nào lẽ ra bắt được mà không bắt
4. **Chỗ sửa thật** — và vì sao không phải chỗ hiển nhiên
5. **Ranh giới** — cách sửa này KHÔNG phủ chuyện gì
6. **Bài canh** — tệp test nào giữ cho nó không quay lại

Nghe như thủ tục thừa cho tới lần thứ ba bạn gặp lại cùng một lỗi ở module
khác. Sổ sai lệch của dự án mẫu có 164 mục, và nó là dữ liệu gốc của chương
đánh giá — không phải phụ lục.

---

# PHẦN II — Tình huống B: họ chip mới, chưa có Platform Pack

## 8. Dựng một Platform Pack

Luật số một, và nó không có ngoại lệ:

> **Engine không bao giờ gọi thẳng một công cụ nào của một họ vi điều khiển.**
> Nó chỉ gọi các năng lực được khai báo trong `pack.yaml`.

Nếu có lúc nào bạn thấy mình muốn viết `if pack.name == ...` trong `eaa/`, đó
là dấu hiệu **interface thiếu một năng lực** — thêm năng lực vào interface,
đừng thêm nhánh rẽ. Xem §8.7.

### 8.1 Cây thư mục

```
packs/<tên>/
├── pack.yaml              # bản khai năng lực — tệp quan trọng nhất
├── tools.yaml             # Tool Manifest: công cụ, cách kiểm phiên bản, cách cài
├── rules/
│   └── forbidden.yaml     # luật phân tích tĩnh của họ chip này
├── templates/
│   ├── main.c.tmpl        # khuôn vòng lặp chính
│   ├── module.h.tmpl      # khuôn tệp tiêu đề
│   └── diagnostic.c.tmpl  # khuôn firmware chẩn đoán
├── hostmock/              # tệp tiêu đề GIẢ để mã dịch được trên máy chủ
├── prompts/               # mẫu prompt nền tảng (dùng chung mọi dự án dùng pack)
└── smoke/                 # bài kiểm khói của chính pack
```

Cách nhanh nhất là **chép `packs/stm32/` rồi sửa**, không phải chép `packs/avr/`.
Lý do: pack STM32 được dựng *sau*, chính là để trả lời câu hỏi "thêm họ chip có
phải sửa engine không", nên nó sạch hơn và các chú thích trong đó nói thẳng vào
những chỗ đã vấp.

### 8.2 `pack.yaml` — tám năng lực

| Năng lực | Bắt buộc? | Làm gì |
|---|---|---|
| `compile` | **Bắt buộc** | Dịch **một** tệp nguồn thành tệp đối tượng. Không liên kết |
| `size` | **Bắt buộc** | Đo chiếm dụng Flash/SRAM. Khoá metric là hợp đồng với `constraints.limits` |
| `static` | **Bắt buộc** | Phân tích tĩnh theo `rules/` |
| `link` | Khi ráp firmware | Gộp tệp đối tượng thành ảnh chạy được |
| `hex` | Khi ráp firmware | Đổi sang định dạng công cụ nạp đọc được |
| `flash` | Khi nạp | **Phải khai `requires_confirmation: true`** — engine từ chối pack thiếu nó |
| `flash_verify` | Khi nạp | Đọc ngược và so. Không cần xác nhận riêng: chỉ đọc |
| `sim` | Tuỳ chọn | Cầu nối cổng mô phỏng |

Mỗi năng lực khai `command` (danh sách, có chỗ giữ `{mcu}`, `{source}`…),
`timeout_s`, và `parse`.

**`parse` là chỗ tốn công nhất, và là chỗ hay sai nhất.** Ba khoá:

```yaml
parse:
  success_exit_codes: [0]
  error_regex: "^(?P<file>[^:]+):(?P<line>\\d+):\\d+:\\s+(?:fatal\\s+)?error:\\s+(?P<msg>.+)$"
  require_regex: "\\b[1-9]\\d* bytes of flash verified\\b"
```

Ba bài học đắt, đã trả giá rồi, đừng trả lại:

* **`error_regex` phải bắt MỌI dạng lỗi công cụ in ra.** Bỏ sót `fatal error:`
  thì công cụ thoát 1 mà bộ phân tích không bắt được dòng nào — cổng báo *"lỗi
  cấu hình của pack"*, chỉ đúng chỗ nhưng nói sai nguyên nhân, và người đọc đi
  sai hướng.
* **Mã thoát 0 không nói công cụ đã LÀM gì.** Dùng `require_regex` để đòi bằng
  chứng. Một công cụ nạp ghi 0 byte rồi thoát 0 đã làm hai phiên làm việc tin
  rằng firmware nằm trên chip trong khi bo vẫn chạy mã cũ.
* **Đọc ngược 0 byte không phải là "khớp".** `flash_verify` phải đòi số byte
  lớn hơn 0 trong `require_regex`.

### 8.3 `rules/forbidden.yaml` — và hợp đồng với dự án

```yaml
rules:
  - id: "delay()"                      # PHẢI khớp chữ trong constraints.forbidden
    kind: regex
    pattern: '\b_?delay(_ms|_us)?\s*\('
    message: >-
      Cấm hàm chặn: hàm này khóa CPU nên phá vỡ ngân sách thời gian của vòng
      điều khiển. Dùng bộ đếm không chặn hoặc máy trạng thái theo tick.
    severity: error
    ref: constraints.yaml · forbidden · delay()
```

Biểu thức chạy trên mã **đã gỡ chú thích**, nên nhắc tên hàm bị cấm trong chú
thích giải thích *"vì sao không dùng"* không bị tính là vi phạm. Chi tiết nhỏ,
nhưng thiếu nó thì mọi prompt dạy về điều cấm đều tự làm mã đỏ.

`message` sẽ đi thẳng vào prompt vá lỗi, nên viết nó như viết cho người sẽ sửa:
nói **vì sao cấm** và **dùng gì thay**, không chỉ nói *"cấm"*.

### 8.4 `host_test` — hợp đồng kiểm thử, và vì sao phải viết dài

Khối `host_test` trong `pack.yaml` là chỗ dài nhất của tệp, và nên như thế. Nó
dạy mô hình cách viết bài kiểm cho họ chip của bạn.

```yaml
host_test:
  compiler: cc
  cflags: ["-std=c11", "-Wall", "-fPIC", "-shared"]
  mock_include: hostmock
  contract: >-
    Bài kiểm là mã PYTHON chạy bằng pytest, đặt ở `tests/test_<module>.py`…
```

Không khai phần này thì **mô hình đoán, và nó đã đoán sai**: có lần nó viết
`tests/test_dummy.c` — một tệp C — cho một cổng chạy pytest.

Hợp đồng của bạn nên nói rõ ít nhất bảy điều:

1. Bài kiểm viết bằng **Python**, chạy bằng pytest, đặt ở đâu
2. Nó **tự dịch** lấy thư viện nó cần, và lệnh dịch hỏng phải làm nó **chết
   ngay** — không `try/except`, không `pytest.skip`
3. Phải đặt **`argtypes` VÀ `restype`** cho mọi hàm (thiếu `restype`, một hàm
   trả `bool` cho ra số rác kiểu 26984449, và bài kiểm đỏ vì lý do không liên
   quan gì tới mã)
4. Cách với tới thanh ghi giả từ Python
5. Module phụ thuộc module khác thì **dịch kèm** nguồn thật, **đừng viết hàm
   giả** trong tệp đang sinh — mã ấy đi thẳng vào firmware và trùng định nghĩa
   lúc liên kết
6. **Không kiểm bằng cách đọc văn bản mã nguồn** (`assert "delay(" not in code`)
   — đó là việc của cổng phân tích tĩnh và không chứng minh gì về hành vi
7. Cái gì kiểm được (phép tính, máy trạng thái, thao tác bit, xử lý biên) và
   cái gì **không** (thời gian, độ trễ ngắt, ngoại vi thật — thuộc G4)

### 8.5 `hostmock/` — tệp tiêu đề giả

Đây là thứ cho phép mã nhúng **chạy trên máy chủ**. Với AVR nó gồm:

```
hostmock/
├── avr/io.h            # thanh ghi thành BIẾN TOÀN CỤC mang đúng tên
├── avr/interrupt.h     # ISR(VECT) thành hàm thường tên VECT_fn
├── util/delay.h
└── eaa_io_space.c      # nơi các biến ấy thật sự tồn tại
```

Hai quy ước làm nên toàn bộ giá trị của nó:

* **Thanh ghi là biến toàn cục mang đúng tên thanh ghi.** Bài kiểm với tới bằng
  `ctypes.c_uint8.in_dll(lib, "PORTB")`, dựng cảnh bằng cách gán `.value` trước
  khi gọi, soi lại `.value` sau khi gọi.
* **Thân ngắt thành hàm thường.** `ISR(TIMER2_COMPA_vect)` trở thành
  `TIMER2_COMPA_vect_fn`, gọi thẳng từ bài kiểm được — nên logic trong ngắt
  cũng kiểm được mà không cần chip.

Làm phần này cho họ chip của bạn là công việc nặng nhất của cả pack. Nó cũng là
phần trả lại nhiều nhất: không có nó thì mọi module chỉ kiểm được sau khi nạp.

### 8.6 Chip cùng họ, khác mã

Nhẹ hơn hẳn. Thêm vào `targets:` của pack, rồi kiểm ba thứ:

```yaml
targets:
  - atmega328p
  - atmega2560        # thêm dòng này
```

1. **Cờ `-mmcu=` có nhận mã mới không** — chạy thử `eaa gen <module> --draft compile`
2. **Số Flash/SRAM trong `hardware_profile.mcu`** phải theo chip mới, không
   chép của chip cũ
3. **Tên thanh ghi có đổi không** — ATmega2560 có `TCCR5A` mà 328P không có,
   và ngược lại một số thanh ghi đổi tên. Đây là chỗ phải đọc datasheet, không
   đoán

### 8.7 Khi bạn thấy cần sửa `eaa/`

Đừng sửa ngay. Trước hết phân biệt hai trường hợp:

**Trường hợp 1 — interface thiếu một tham số.** Đây là chuyện bình thường và
đã xảy ra: pack STM32 làm lộ ra hai thứ interface còn thiếu — đuôi ảnh nạp được
(`.hex` với AVR, `.bin` với ARM) và tệp nguồn do pack cấp (ARM bare-metal cần
mã khởi động và bảng vector; AVR thì bộ dịch kèm sẵn). Cả hai được **thêm vào
interface** dưới dạng tham số khai báo được, không thêm vào engine dưới dạng
`if pack.name == ...`.

Cách làm: thêm khoá vào lược đồ `pack.yaml` trong `eaa/platform.py`, để pack cũ
không khai thì nhận giá trị mặc định cũ. Chạy `pytest tests/test_tc38_engine_purity.py`
để chắc bạn không mang tên phần cứng nào vào engine.

**Trường hợp 2 — bạn đang muốn viết một nhánh rẽ theo tên pack.** Dừng lại. Đây
là chỗ ranh giới bắt đầu mờ, và nó mờ dần chứ không sập một lần. Bài kiểm
`tests/test_tc38_engine_purity.py` quét `eaa/` tìm mọi tham chiếu phần cứng ở
**mỗi commit**; nó sẽ bắt bạn. Nhưng nó chỉ bắt được tên chip và tên thanh ghi
— một nhánh `if pack.name == "esp32"` thì nó không bắt được, và bạn phải tự giữ.

---

# PHẦN III — Dùng một Agent khác để làm việc này

## 9. Vì sao nên, và ranh giới ở đâu

Toàn bộ phần I và II ở trên là việc đọc tài liệu, viết YAML, viết prompt, so mã
với mã tham chiếu, và ghi sổ. Đó đúng là việc một trợ lý lập trình biết dùng
công cụ dòng lệnh — Claude Code, Codex, Cursor — làm nhanh hơn người.

**Toàn bộ dự án mẫu này được dựng theo cách ấy**, nên phần dưới không phải suy
đoán: nó là những gì đã chạy, gồm cả những chỗ Agent ngoài làm sai.

Nhưng phải tách bạch ngay từ đầu, vì đây là chỗ dễ hỏng nhất:

> **Agent ngoài CHUẨN BỊ. Người DUYỆT. Không đảo hai vai ấy.**

Cụ thể, Agent ngoài **không được** chạy: `eaa gate approve/reject`,
`eaa flash approve`, `eaa doctor approve`, `eaa tool approve`. Không phải vì
nó không gõ được — nó gõ được — mà vì lời duyệt của một máy không phải lời
duyệt. Cả năm Human Gate mất nghĩa ngay lúc đó.

Ngược lại, để nó chạy `eaa gen`, `eaa build`, `pytest`, `eaa status`,
`eaa report *` thì hoàn toàn nên: chúng chỉ đọc hoặc chỉ tạo ra thứ chờ duyệt.

### Ba việc Agent ngoài làm tốt hơn người rõ rệt

**1. Đọc mã tham chiếu của nhà sản xuất và rút ra số.** Đây là việc trả lại
nhiều nhất. Trong dự án mẫu, chính bước này gỡ được bế tắc: robot lao về một
phía, tôi đoán sai nguyên nhân hai lần, và chỉ khi đọc thẳng ba bản mã tham
chiếu V0/V1/V3 mới thấy chiều DIR phải chép nguyên bảng của V1 chứ không suy
ra từ hồ sơ phần cứng.

Câu lệnh đáng dùng, đại ý:

```
Đọc toàn bộ mã tham chiếu trong <thư mục>. Rút ra:
(a) thứ tự các bước từ lúc bật máy tới lúc vào vòng điều khiển;
(b) mọi hằng số, kèm chỗ nó được dùng và thứ nó gắn vào;
(c) chỗ nào bản của chúng ta làm KHÁC, và khác ở điểm nào.
Đừng sửa gì. Chỉ báo cáo, kèm số dòng.
```

**2. Dựng khung Platform Pack từ một pack đã có.** `pack.yaml` của AVR dài vài
trăm dòng, phần lớn là `command`, `parse` và `contract`. Chép sang họ chip mới
rồi sửa từng năng lực là việc cơ học, và Agent ngoài làm chính xác hơn người
gõ tay — miễn là bạn bắt nó **giải thích từng chỗ nó đổi**.

**3. Viết bài kiểm canh và mục sổ sai lệch.** Sau mỗi lần bắt được lỗi, việc
"viết một bài kiểm để nó không quay lại" là việc người hay bỏ qua vì đã mệt.
Đây đúng là lúc giao cho Agent ngoài.

### Ba việc phải tự làm, không giao được

**1. Đọc mã ở G3.** Bốn dạng lỗi ở §7 bước 1 — mã tự chỉnh đồ đo, sai thứ tự,
phá hợp đồng, bài kiểm xanh vì lý do sai — không dạng nào bắt được bằng cách
hỏi một mô hình *"mã này đúng không"*. Ba trong bốn dạng ấy do chính một mô
hình sinh ra.

**2. Quan sát phần cứng.** *"Bánh quay cùng chiều hay ngược chiều"*, *"nghe
thấy hai bíp liền chưa"*, *"thả tay thì nó ngã về đâu"* — không Agent nào trả
lời được, và đây là kênh duy nhất phân biệt mã đúng với mã trông đúng.

**3. Quyết định đánh đổi.** Chọn chu kỳ vòng điều khiển, chọn dải đo cảm biến,
chọn có bật watchdog hay không. Agent trình được phương án kèm hậu quả; chọn
là việc của người chịu trách nhiệm.

## 10. Quy trình làm việc với một Agent ngoài

### Bước 1 — Cho nó đọc đúng thứ, theo đúng thứ tự

Đừng thả nó vào kho rồi bảo "làm đi". Thứ tự đọc có ảnh hưởng thật:

```
1. README.md — kiến trúc ba tầng và bất biến
2. docs/HUAN_LUYEN_AGENT_CHO_BO_MOI.md — chính tài liệu này
3. packs/avr/pack.yaml — đọc CẢ chú thích, chúng là tài liệu
4. docs/SAI_LECH_THIET_KE.md — ít nhất 20 mục gần nhất
5. Mã tham chiếu của bo bạn, nếu có
```

Mục 4 đáng để ý: nó dạy Agent ngoài **những lỗi kho này đã mắc**, nên nó không
mắc lại. Bỏ qua mục ấy thì bạn sẽ thấy nó đề xuất đúng những thứ đã bị bác bỏ.

### Bước 2 — Nói rõ luật số một, ngay trong câu giao việc

Câu này nên có mặt trong mọi phiên làm việc:

> Sửa bằng **cấu trúc**, không bằng lời dặn. Trước khi thêm một câu vào prompt,
> hãy hỏi: điều này mã hoá được thành một bài kiểm, một luật của cổng, hay một
> bất biến engine không? Nếu được thì làm thế. Prompt là mức 1 và là mức yếu
> nhất.

Không nói câu này thì Agent ngoài sẽ mặc định thêm câu dặn vào prompt — đó là
cách sửa rẻ nhất và trông giống như đã sửa. Đã đo được trong kho này: đó là
dạng lỗi hay gặp nhất.

### Bước 3 — Bắt nó kiểm trước khi khai

Luật thứ hai, và nó cứu được nhiều giờ:

> Đừng viết vào tài liệu điều bạn chưa chạy. Mỗi lệnh, mỗi khoá YAML, mỗi
> đường dẫn tệp phải đối chiếu với mã thật trước khi đưa vào văn bản.

Đã có ví dụ thật ngay trong phiên viết README: Agent ngoài (là tôi) ghi *"CLI
có 70 lệnh"* — số thật là 52; 70 là số mục trong `TOOLBOX`, tính cả lệnh con.
Và một đoạn mã `authorize_merge` trích trong README không khớp mã thật. Cả hai
chỉ lộ ra khi chạy lệnh để kiểm.

### Bước 4 — Vòng làm việc, và chỗ bạn xen vào

```
Agent ngoài:  eaa gen <module>            → sinh, chạy cổng, tự sửa
Agent ngoài:  đọc mã sinh ra, đối chiếu prompt và mã tham chiếu
Agent ngoài:  báo cáo — "đúng ở đây, nghi ngờ ở kia, vì sao"
      BẠN:    eaa gate show G3, đọc mã, rồi approve hoặc reject
Agent ngoài:  nếu reject — soạn lý do cho chính xác, rồi eaa gen lại
```

**Agent ngoài đọc trước, bạn đọc sau.** Nó bắt được phần lớn lỗi cơ học và nói
cho bạn biết chỗ đáng ngờ, nên khi bạn đọc thì đọc có trọng tâm. Nhưng chữ ký
cuối vẫn là của bạn — và trong dự án mẫu, có lần Agent ngoài **từ chối sai**:
tôi bác một đoạn `logic_pid` xoá `self_balance_setpoint` khi dừng, trong khi
mã tham chiếu V1/V3 làm đúng như thế. Phải tự đảo lại quyết định của chính
mình ở lượt sau.

### Bước 5 — Uỷ quyền việc bấm, không uỷ quyền việc soi

Nếu bạn muốn đi nhanh và chấp nhận rủi ro có tính toán, cách uỷ quyền **đúng**
là: *"đọc kỹ mã, nếu đúng thì duyệt thay tôi"* — tức bạn uỷ quyền **việc bấm**,
với điều kiện Agent ngoài đã thật sự **soi**.

Cách uỷ quyền **sai**: *"cứ duyệt hết đi cho nhanh"*. Khác biệt nằm ở chỗ ai
chịu trách nhiệm đọc. Và dù uỷ quyền cách nào, hai gate này **không uỷ quyền
được**: G4 (nghiệm thu trên thiết bị) và G5 (nạp firmware), vì cả hai đòi mắt
người nhìn vào phần cứng.

## 11. Mẫu câu giao việc

Chép và sửa cho bo của bạn.

**Dựng Platform Pack mới:**

```
Đọc packs/stm32/pack.yaml và eaa/platform.py. Dựng packs/<tên>/ cho họ chip
<mã chip>, toolchain <tên toolchain>.

Yêu cầu:
- Ba năng lực bắt buộc compile/size/static, cộng link/hex/flash/flash_verify.
- flash PHẢI khai requires_confirmation: true.
- Mỗi parse.error_regex chạy thử với đầu ra lỗi THẬT của công cụ, đừng đoán.
- flash và flash_verify phải có require_regex đòi số byte > 0.
- Giải thích từng chỗ khác packs/stm32, và vì sao.
- KHÔNG sửa bất cứ gì trong eaa/. Nếu thấy cần, dừng lại và nói tôi biết
  interface thiếu tham số nào.
Chạy pytest tests/test_tc38_engine_purity.py khi xong.
```

**Rút hồ sơ phần cứng từ tài liệu bo:**

```
Đọc <datasheet, sơ đồ nguyên lý, mã tham chiếu>. Dựng đề xuất
hardware_profile.yaml theo lược đồ trong projects/robot_balance/.

- Mỗi ngoại vi phải có id, kind và configured_by đầy đủ.
- clock_hz: nếu tài liệu không nói rõ thạch anh thật trên bo, ĐỪNG đoán —
  đánh dấu là cần tôi đo.
- Chỗ nào bạn không chắc thì ghi ra thành danh sách câu hỏi, đừng điền bừa.
```

**Sau một lần G3 từ chối:**

```
Tôi vừa từ chối <module> với lý do: "<lý do>".

Trước khi sinh lại, phân loại lần trượt này theo §7 bước 3 của
docs/HUAN_LUYEN_AGENT_CHO_BO_MOI.md: lỗi engine, hành vi mô hình, hay đặc tả
thiếu? Nói rõ căn cứ.

Rồi đề xuất chỗ sửa ở mức CAO NHẤT mà không báo nhầm. Nếu đề xuất là thêm câu
vào prompt, hãy nói rõ vì sao mức 2, 3, 4 không mã hoá được điều này.
```

## 12. Bốn cách hỏng khi dùng Agent ngoài — đã gặp thật

| Cách hỏng | Dấu hiệu | Cách tránh |
|---|---|---|
| **Nó sửa bằng lời dặn** | Lần thứ ba thêm câu vào cùng một tệp prompt cho cùng một lỗi | Bước 2 ở §10. Bắt nó trả lời "vì sao không mã hoá được" |
| **Nó khai điều chưa kiểm** | Con số, tên cờ, đường dẫn trong báo cáo mà nó chưa chạy | Bước 3 ở §10. Đòi lệnh kiểm kèm kết quả |
| **Nó đoán thay vì đọc** | Chẩn đoán nghe hợp lý, dựa trên triệu chứng chứ không dựa trên mã | Đưa mã tham chiếu vào. Trên giá đỡ không có phản hồi cơ học, nên đúng và sai trông giống hệt nhau |
| **Bạn tin nó ở G3** | Duyệt nhanh vì "Agent bảo đúng rồi" | Nó đọc trước để bạn đọc có trọng tâm, không phải để bạn khỏi đọc |

Dòng thứ ba đáng nhắc lại vì nó tốn nhất trong dự án mẫu: từ triệu chứng
*"nghiêng hai chiều mà bánh chạy cùng phía"*, tôi kết luận **trục cảm biến
sai**. Sai hoàn toàn. Đọc mã tham chiếu mới thấy hai hằng số hiệu chỉnh của
nhà sản xuất đều rất xa giá trị mà giả thuyết ấy đòi hỏi — tức cảm biến vẫn
đọc đúng trục, đúng dấu.

**Bài học: khi triệu chứng mơ hồ, đọc mã tham chiếu rẻ hơn đoán.**

---

## 13. Bảng kiểm — dán lên tường

**Bo mới, chip cũ:**

- [ ] `eaa brief` trước, đừng gõ tay hồ sơ
- [ ] `hardware_profile.yaml`: `id` ngoại vi đặt đúng, `configured_by` đầy đủ
- [ ] `clock_hz` là số **đo được**, không phải số danh nghĩa
- [ ] Mỗi điều cấm trong `constraints` có luật khớp trong pack
- [ ] G1 duyệt bằng `--expect`
- [ ] Datasheet nạp **theo trang**, không nạp cả tệp
- [ ] `eaa errata lookup --rev` một lần cho mỗi lô chip
- [ ] `eaa interface <module> --write` trước khi `eaa gen`
- [ ] Ở G3: đọc **mã**, so từng con số với prompt
- [ ] Từ chối thì nêu **sai ở đâu và vì sao**, không nêu phải làm gì
- [ ] Phân loại lần trượt trước khi sửa
- [ ] Cùng một lỗi lặp lần thứ ba → leo lên mức 3

**Họ chip mới, thêm:**

- [ ] Chép `packs/stm32/` làm khung, không chép `packs/avr/`
- [ ] Ba năng lực bắt buộc: `compile`, `size`, `static`
- [ ] `flash` khai `requires_confirmation: true`
- [ ] `error_regex` bắt **mọi** dạng lỗi, kể cả `fatal error:`
- [ ] `flash`/`flash_verify` có `require_regex` đòi số byte > 0
- [ ] `host_test.contract` viết đủ bảy điều ở §8.4
- [ ] `hostmock/`: thanh ghi là biến toàn cục, ISR thành hàm thường
- [ ] Mã luật `rules/forbidden.yaml` khớp chữ với `constraints.forbidden`
- [ ] Chạy `pytest tests/test_tc38_engine_purity.py` sau mỗi lần chạm `eaa/`
- [ ] Không viết `if pack.name == ...` ở bất cứ đâu trong `eaa/`

---

## 14. Kỳ vọng cho đúng

Từ dự án mẫu, để bạn biết mình đang đi nhanh hay chậm:

| | Số đo thật |
|---|---|
| Module firmware để robot đứng được | 7 |
| Lượt gọi mô hình | 214 |
| Vòng tự sửa đã dùng | 81 |
| Lượt tới G3 | 30, trong đó **13 bị từ chối (43%)** |
| Lần nạp firmware | 26 |
| Lỗi chỉ phần cứng chỉ ra được | 5 |
| Mục sổ sai lệch | 164 |

**Tỉ lệ từ chối 43% là con số bạn nên chuẩn bị tinh thần.** Nó gần như không
đổi khi mẫu tăng từ 25 lên 30 quyết định, nên nó là đặc tính của quy trình chứ
không phải nhiễu giai đoạn đầu. Ai kỳ vọng "sinh một lần là xong" sẽ bỏ cuộc ở
module thứ hai.

Và con số đáng nói nhất: **năm lỗi chỉ phần cứng mới chỉ ra được**. Bốn cổng
xanh, G3 duyệt, firmware nạp — rồi bo mới cho biết mã sai. Đó không phải thất
bại của quy trình; đó là lý do G4 và G5 tồn tại.

---

## 15. Đọc tiếp

| Tài liệu | Nội dung |
|---|---|
| [`CAI_DAT_VA_CHAY.md`](CAI_DAT_VA_CHAY.md) | Cài đặt và chạy trọn luồng |
| [`DANH_GIA_NANG_LUC_AGENT.md`](DANH_GIA_NANG_LUC_AGENT.md) | §4: lý thuyết của phương pháp huấn luyện |
| [`SAI_LECH_THIET_KE.md`](SAI_LECH_THIET_KE.md) | 164 mục — đọc mục gần nhất trước khi bắt đầu |
| [`md/EAA-AIS-05_Dac_ta_ky_thuat_AI.md`](md/EAA-AIS-05_Dac_ta_ky_thuat_AI.md) | Nén ngữ cảnh K1–K7, RAG, Knowledge Graph |
| `packs/avr/pack.yaml` | Đọc thẳng — chú thích trong đó là tài liệu tốt nhất về pack |
