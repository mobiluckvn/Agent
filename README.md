# Embedded AIDD Agent (EAA)

Agent lập trình nhúng **tổng quát** — bộ điều phối đóng gói quy trình phát triển
phần mềm nhúng có AI hỗ trợ thành một hệ thống chạy được, với các cổng phê duyệt
của con người được **cưỡng chế bằng phần mềm** chứ không bằng quy ước.

Sản phẩm phần mềm của đề án tốt nghiệp Thạc sĩ Kỹ thuật (Kỹ thuật Điện tử, PTIT).

- **Học viên thực hiện:** Vũ Trí Công
- **Giảng viên hướng dẫn:** TS. Nguyễn Trung Hiếu

Thiết kế đã đóng băng; hồ sơ đầy đủ nằm trong [`docs/`](docs/).

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

### Trước khi sinh mã — Agent đề xuất, người chốt

```bash
eaa brief                                 # dò bo, hỏi, dựng hồ sơ nháp
eaa propose scope                         # phạm vi và cái KHÔNG làm, kèm lý do
eaa propose constraints                   # mỗi ràng buộc kèm HỆ QUẢ nếu vi phạm
eaa propose acceptance                    # tiêu chí = số + đơn vị + cách đo
eaa propose pinmap                        # bảng chân, kiểm chức năng thay thế
eaa sources need --lookup                 # tài liệu cần, đích danh, kèm nguồn hãng
eaa errata lookup --rev <rev in trên chip> # lỗi chip đã công bố cho ĐÚNG rev
eaa budget propose                        # chia ngân sách flash/RAM theo module
eaa interface <module> --write            # hợp đồng gọi TRƯỚC khi sinh thân
```

### Sau khi có mạch thật

```bash
eaa flash                                 # nạp, rồi ĐỌC NGƯỢC để đối chiếu
eaa diagnose measure DS-05                # hướng dẫn đo bằng dụng cụ, nhận số về
eaa endurance --port <cổng> --seconds 600 # chạy dài, bắt reset qua bộ đếm
eaa scope-image anh.png --expect loop_period_ms   # ảnh màn hiện sóng → số đo
eaa field "<mô tả triệu chứng>"           # ca hiện trường: dựng lại điều kiện
eaa handover doc --publish                # tài liệu vận hành + điều KHÔNG làm được
eaa handover rollout                      # cập nhật thiết bị: một máy trước đã
```

### Agent tự soi mình

```bash
eaa report retrieval                      # precision@3 trên bộ chuẩn truy xuất
eaa report review                         # khâu nào hay hỏng, và nên sửa gì
eaa budget tokens                         # token và chi phí theo module
eaa deviations --draft                    # chỗ mã và tài liệu kể hai câu chuyện
```

## Tương tác bằng ngôn ngữ tự nhiên

Mặt tiếp xúc đầu tiên của sản phẩm là **70 lệnh rời**. Muốn hỏi được câu đầu
tiên, người dùng phải biết lệnh nào tồn tại và gõ đúng cờ — tức phải hiểu cấu
trúc bên trong trước đã. Tầng hội thoại lấp chỗ đó: nói ra điều mình muốn bằng
tiếng Việt, Agent tự tìm đường.

```bash
eaa chat                                  # mở phiên
eaa chat "robot ngã về bên trái, xem giúp"  # hỏi một câu rồi thoát
eaa chat "còn gì chặn tôi nạp firmware" --max-steps 12
```

Mỗi lượt Agent tự chọn và **tự chạy** lệnh trong danh mục cho tới khi đủ dữ
kiện trả lời, tối đa 8 bước mặc định. Nó không đoán trạng thái dự án — nó chạy
`eaa status`, `eaa gate show`, `eaa report review` và đọc kết quả thật.

### Ranh giới nằm ở việc DUYỆT, không ở việc LÀM

Đây là chỗ một tầng hội thoại dễ phá hỏng cả sản phẩm: mô hình "hiểu" rằng
người dùng muốn duyệt, rồi tự gọi `gate approve`. Nên ranh giới được dựng bằng
**cấu tạo, không bằng lời dặn** — `TOOLBOX` là dữ liệu nằm trong Git, và **không
một lệnh duyệt nào có mặt**:

| Agent tự gọi được | Chỉ người gõ được |
|---|---|
| `status` `gate show` `report *` `deviations` `focus` | `gate approve` · `gate reject` |
| `propose *` `interface` `budget propose` `plan add` | `flash approve` |
| `flash` `doctor --fix` `tool run` | `doctor approve` · `tool approve` · `skill approve` |
| `research` `read` `sources need` `errata lookup` | `tune` · `rollback` · `diagnose run` · `endurance` |

Ba lệnh `flash`, `doctor --fix`, `tool run` **có** trong danh mục, và đó là chủ
ý. Cả ba tự dừng khi chưa có quyết định của người: `flash` đòi một bản duyệt
neo vào **băm nội dung ảnh** (ráp lại là ảnh khác, phải duyệt lại), `doctor
--fix` chỉ chạy đúng những lệnh cài đã duyệt, `tool run` chỉ chạy công cụ đã ở
trạng thái `approved`. Người đã duyệt rồi thì việc bấm nút là việc máy làm
được; bắt người gõ lại lệnh ấy không thêm một lớp an toàn nào.

Cách chia này còn có một tính chất mà cách chia "cấm các lệnh nguy hiểm" không
có: nó **không phụ thuộc vào việc liệt kê đủ**. Danh sách lệnh nguy hiểm dài
thêm mỗi lần có tính năng mới, và một danh sách phải nhớ cập nhật là một danh
sách sẽ sót. Danh sách lệnh duyệt thì đóng — mỗi cổng đúng một lệnh, và thêm
cổng mà quên thêm lệnh duyệt thì cổng ấy không dùng được.

Mô hình có muốn gọi cũng không có gì để gọi: vòng lặp từ chối mọi lệnh ngoài
danh mục, **nói lại cho mô hình biết vì sao**, và nói cho người dùng biết lệnh
nào họ phải tự gõ. Prompt cũng dặn điều đó, nhưng lời dặn chỉ là hàng rào thứ
hai. Canh bằng TC-61 — hai bài độc lập, một bài đọc danh sách từ prompt, một
bài viết thẳng tên lệnh, để một prompt bị sửa không làm cả hai cùng mù.

### "Stateless mỗi lần gọi" vẫn còn đúng

Mỗi lượt vẫn là **một** lời gọi độc lập. Cái trông như trí nhớ do engine dựng
lại từ Project State cộng một bản ghi phiên có giới hạn — đúng cách Composer
vẫn lắp ngữ cảnh cho vòng sinh mã, và bị cắt theo ngân sách token như mọi lớp
khác. Không có trạng thái nào nằm ở phía nhà cung cấp mô hình. Toàn bộ phiên
ghi ra `chat_log.jsonl` nên truy lại được.

Giao thức là **JSON trên `complete()`**, không phải function-calling của nhà
cung cấp. Nhờ vậy vòng hội thoại chạy với mọi adapter theo interface
`LLMClient` — kể cả MockLLM và bộ phát lại dùng trong test. Đó đúng là điều
ADR-03 đòi: đổi nhà cung cấp không đổi hành vi điều phối.

### Những chỗ khác người và Agent nói chuyện bằng tiếng Việt

Hội thoại không chỉ ở `eaa chat`. Ngôn ngữ tự nhiên là **kênh dữ liệu hai
chiều** ở suốt vòng đời:

```bash
eaa brief                                 # Agent dò bo, HỎI người, rồi dựng hồ sơ nháp
eaa field "thả tay thì robot lao về bên trái"   # mô tả triệu chứng → dựng lại điều kiện
eaa decide "chọn chu kỳ vòng điều khiển"  # dựng phương án kèm đánh đổi, người chọn ở gate
eaa resolve drv_imu                       # tri thức còn thiếu: thang ba bậc, bậc 3 phải dẫn nguồn
eaa focus                                 # còn gì chặn giữa đây và việc bạn muốn làm
eaa suggest                               # cái gì đang tốn công nhất, nên làm gì với nó
eaa diagnose measure DS-02                # hướng dẫn đo, HỎI người, nhận số về hồ sơ
eaa skill mine                            # tìm chuỗi việc đã lặp, đặt tên để gọi bằng một câu
```

**Lý do từ chối ở G3 là kênh huấn luyện chính.** Khi người từ chối một module,
câu lý do gõ bằng tiếng Việt được ghi vào Error Ledger và **có mặt nguyên văn
trong prompt lần sinh lại**. Đây là đường duy nhất hiện nay để bài học từ phần
cứng chảy ngược vào mô hình — và cũng là một giới hạn đã ghi nhận: số đo từ bo
chưa tự chảy vào, phải qua câu chữ của kỹ sư.

Ba dạng câu hỏi Agent đặt cho người được thiết kế riêng, vì **hỏi sai câu thì
nhận về câu trả lời vô dụng**:

* **Câu người trả lời được bằng mắt** — *"đèn có nháy không"*, không phải *"giá
  trị thanh ghi TWSR là bao nhiêu"*.
* **Câu có phương án sẵn** ở `decide` và `propose`: người chọn, không phải người
  soạn.
* **Câu kèm cách đo** ở `diagnose measure`: mỗi tiêu chí có số, đơn vị, và mô tả
  dụng cụ — chứ không phải *"kiểm tra xem có ổn không"*.

Chiều ngược lại cũng có kỷ luật: `eaa gapsearch` bậc 3 **bắt buộc dẫn nguồn nằm
trong tập trang đã tải về**; nêu một URL lạ là bị bỏ. Tìm kiếm trả **địa chỉ**,
không trả kết luận.

## Kiểm thử

```bash
.venv/bin/python -m pytest                       # toàn bộ
.venv/bin/python -m pytest tests/test_tc38_engine_purity.py   # engine sạch phần cứng
```

Test được đặt tên theo mã test case trong `docs/md/EAA-STP-04` và
`docs/md/EAA-AIS-05` §11 — 38 test case là thước chấm của sản phẩm.

## Tiến độ

### Mốc: robot cân bằng được trên phần cứng thật — 03/09/2026

Firmware `80ec03d0d4` chạy trên bo BLKLab (ATmega328P, MPU-6500, hai động cơ
bước A4988). Thả tay trên sàn, robot đứng, không đổ.

**Toàn bộ mã điều khiển trên bo do Agent sinh qua vòng lặp chuẩn** — prompt bảy
lớp → mô hình → bốn cổng kiểm chứng → tự sửa → G3 → merge. Không có dòng nào
viết tay chen vào. Điều được chứng minh không phải *"robot cân bằng được"* —
thứ ấy nhà sản xuất bo đã làm — mà là **một quy trình sinh mã có kiểm soát đi
được tới sản phẩm chạy trên phần cứng thật**.

| Đại lượng | Giá trị |
|---|---|
| Module firmware đã merge | **7/9** (`drv_uart`, `app_telemetry` chưa cần cho mục tiêu đứng) |
| Lượt gọi mô hình | **214** — 794.581 token vào, 323.775 ra |
| Lượt chạy cổng kiểm chứng | **334** |
| Vòng tự sửa đã dùng | **81** |
| Quyết định Human Gate | **51** — G1: 13 · G2: 8 · G3: **17 duyệt / 13 từ chối** |
| Lần nạp firmware | **26**, mỗi lần đều đọc ngược đối chiếu băm |
| Firmware ráp được | 6.800 byte flash (20,8%), 134 byte SRAM (6,5%) |
| Bài kiểm engine | **106 tệp TC**, 2.374 bài |
| Sổ sai lệch thiết kế | **163 mục**, mỗi mục có bài kiểm canh |

### Agent tự làm được gì

Những việc dưới đây Agent làm **không có người can thiệp giữa chừng**. Kỹ sư
đứng ở hai đầu — giao nhiệm vụ, và duyệt gate — chứ không ở giữa.

**Sinh mã đi trọn vòng lặp.** Ghép prompt bảy lớp từ Knowledge Base và Project
State; gọi mô hình; chạy chuỗi bốn cổng (dịch → kích thước → phân tích tĩnh →
kiểm thử đơn vị); đọc lỗi và tự vá ≤ 3 vòng dạng patch; commit lên nhánh riêng;
dừng tại G3 chờ người. 7 module firmware ra đời theo đúng đường này.

**Tự viết bài kiểm cho mã của chính nó.** Mỗi module ra đời kèm `test_*.py`
chạy được trên máy chủ qua lớp mock ngoại vi — không phải firmware nạp mới biết
đúng sai.

**Tự chặn mình đúng chỗ.** Không có cờ nào bỏ qua cổng. Chế độ nháp không merge
được *do cấu tạo* — nó không ghi bằng chứng, nên tới bước merge không có gì để
đọc. Ảnh nạp làm thiết bị chuyển động đòi xác nhận **từng mục** checklist an
toàn, và quyết định neo vào **băm nội dung ảnh** nên ráp lại là phải duyệt lại.

**Tự đề xuất trước khi sinh.** Phạm vi, ràng buộc kèm hệ quả nếu vi phạm, tiêu
chí nghiệm thu có số và đơn vị, bảng chân, ngân sách bộ nhớ theo module, danh
sách tài liệu cần và tra được địa chỉ tải chính chủ.

**Tự ra Internet có kỷ luật.** Hai hạng nguồn: `chính chủ` (miền nhà sản xuất)
mới thành trích đoạn tri thức, `mở` chỉ là manh mối gỡ lỗi. Hạng tính theo URL
**cuối** sau chuyển hướng. Tìm kiếm trả **địa chỉ**, không trả kết luận.

**Tự viết công cụ cho mình dùng.** Ba cổng: cấu tạo → an toàn → chạy thử. Danh
sách công cụ là **dữ liệu trong Git**, và mỗi mục chỉ chạy được sau khi người
bấm duyệt — Agent mở rộng *cái nó làm*, không mở rộng *quyền nó có*.

**Tự dẫn người qua một lượt đo trên bo.** Sinh firmware chẩn đoán, hỏi người
đúng câu người trả lời được, nhận số đo về và ghi vào hồ sơ phần cứng có xuất
xứ. Mốc gia tốc `-535` dùng trong bản đang chạy đến từ đúng đường này.

**Tự soi mình.** `eaa report review` (khâu nào hay hỏng), `eaa report retrieval`
(precision@3 truy xuất), `eaa deviations` (chỗ mã và tài liệu kể hai câu chuyện
khác nhau), `eaa budget tokens` (chi phí theo module).

### Còn phải người làm — và đây mới là phần đáng đọc

Tỉ lệ **G3 từ chối 13/30 = 43%** là con số quan trọng nhất của cả bảng trên. Nó
gần như không đổi khi mẫu tăng từ 25 lên 30 quyết định, nên nó là đặc tính của
quy trình chứ không phải nhiễu giai đoạn đầu. Bốn dạng lỗi mà **không cổng tự
động nào bắt được**, đều bắt bằng mắt người ở G3:

1. **Mã tự chỉnh đồ đo cho vừa mình** — vòng vá đổi hằng số vật lý
   (`0.000031` → `1/(131×100)`) để bài kiểm chạy qua, thay vì sửa mã.
2. **Đúng công thức, sai thứ tự** — vùng chết và phép dò điểm cân bằng đảo chỗ
   cho nhau. Mọi bài kiểm xanh; robot tự tạo một chu trình giới hạn.
3. **Phá hợp đồng gọi** — sinh lại một module và bỏ bớt tham số của nó, làm
   module đã merge không dịch được. Nay đã có cổng canh (SL-163).
4. **Bài kiểm xanh vì lý do sai** — bài kiểm trông đúng, đỏ rồi xanh đúng hai
   thời điểm cần, nhưng chạy quá ngắn nên xanh cả với mã sai. Dạng khó thấy
   nhất, vì nó không vi phạm luật nào.

Kết luận rút ra cho quy trình: **màu của bài kiểm không thay được việc đọc mã.**
Chi tiết và phương pháp huấn luyện: [`docs/DANH_GIA_NANG_LUC_AGENT.md`](docs/DANH_GIA_NANG_LUC_AGENT.md).

### Sprint

| Sprint | Mục tiêu | Trạng thái |
|---|---|---|
| **S0** | Khung xương: state bền, policy, interface pack, khung CLI | ✅ TC-03, TC-08, TC-38 xanh |
| **S1** | Tri thức: 5 kho, graph, composer K1–K7, MockLLM | ✅ TC-04, TC-05, TC-10, TC-16, TC-18, TC-19, TC-21 xanh |
| **S2** | Vòng lặp chuẩn 13 bước: tools, orchestrator, gates, git, KPI | ✅ TC-01, TC-02, TC-06, TC-07, TC-09, TC-17 xanh |
| **S3** | Mô phỏng MIL/SIL, ingest, vòng đời tri thức, docs registry, doctor | ✅ TC-12, TC-13, TC-22, TC-24, TC-25, TC-26, TC-29, TC-32..37 xanh |
| **S4** | Mô hình thật, 2 module demo, chẩn đoán phần cứng, phiên bản mã | ✅ TC-11, TC-14, TC-15, TC-27, TC-28, TC-30, TC-31 xanh |
| **S5** | Nghiệm thu trên phần cứng thật; bịt lỗ hổng lộ ra khi chạy bo | 🟡 robot đứng được; TC-116..124 xanh; 10 bài E2E TC-15 chờ ghi lại fixture |

### Còn nợ

* **10 bài E2E TC-15 đỏ** — prompt đổi thì băm đổi, bộ phát lại cố ý không bịa
  phản hồi. Cần chạy lại `scripts/record_e2e_fixture.py` với mô hình thật.
* **Chưa đo được nhịp 4 ms có thật sự được giữ hay không.** ISR bước chạy 50 kHz
  trên AVR 16 MHz — 320 chu kỳ mỗi lần. Robot đứng được chỉ chứng minh nhịp *đủ
  gần*, không chứng minh nó đúng.
* **Một dự án, một nền tảng, một mô hình.** Mọi kết luận rút từ `robot_balance`
  trên AVR với `gemini-3.1-pro-preview`. `disco_f469` mới chạy tới phân rã.

## Đọc hồ sơ thiết kế

1. `docs/md/EAA-MDD-00` — tổng hợp: 15 quyết định đã chốt, kế hoạch sprint
2. `docs/md/EAA-SDD-03` — bản vẽ thi công: cây thư mục, lược đồ dữ liệu, module
3. `docs/md/EAA-AIS-05` — tầng AI: nén ngữ cảnh, RAG, graph, ingest, chẩn đoán
4. `docs/md/EAA-STP-04` — thước chấm
5. `docs/md/EAA-SAD-02`, `docs/md/EAA-SRS-01` — tra cứu kiến trúc và yêu cầu
