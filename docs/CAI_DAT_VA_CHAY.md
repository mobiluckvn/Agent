# Cài đặt và chạy — từ máy trắng tới firmware nạp được

Tài liệu này đi trọn một lượt: tải mã về, dựng môi trường, cài công cụ, rồi
chạy hết vòng đời một module — sinh mã, qua cổng, duyệt gate, ráp firmware,
nạp xuống bo thật.

Có **hai đường**. Đường A chạy lại dự án mẫu đã có sẵn (nhanh nhất để thấy hệ
thống hoạt động, khoảng 15 phút). Đường B dựng một dự án mới từ đầu. Đọc hết
phần 1–4 trước, rồi chọn đường.

---

## 1. Yêu cầu máy

| | Tối thiểu | Ghi chú |
|---|---|---|
| Hệ điều hành | macOS, Linux | Đã chạy thật trên macOS 15 (Darwin 25.6) và Ubuntu 22.04 |
| Python | **≥ 3.10** | Cần `X \| None` và `match`. Bản đang dùng: 3.12.13 |
| Git | ≥ 2.30 | Engine gọi `git` như một tiến trình ngoài, không dùng thư viện |
| Bộ dịch máy chủ | `cc` / `gcc` / `clang` | Để chạy **bài kiểm firmware trên máy chủ** — xem §3.2 |
| Toolchain nhúng | avr-gcc, avr-objcopy, avr-size, avrdude | Chỉ cần khi thật sự dịch và nạp firmware |
| Phân tích tĩnh | cppcheck | Cổng `static` gọi tới |
| Mạng | tuỳ chọn | Tắt hẳn bằng `EAA_NO_NET=1` |

Không cần: cơ sở dữ liệu, Docker, dịch vụ nền, GPU. Toàn hệ chạy bằng một
tiến trình Python trên một máy.

---

## 2. Lấy mã về và dựng môi trường Python

```bash
git clone git@github.com:mobiluckvn/Agent.git KTDT
cd KTDT

python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`-e` (editable) là chủ ý: sửa mã trong `eaa/` có tác dụng ngay, không phải cài
lại. `[dev]` kéo thêm `pytest` và `pytest-cov`.

Ba phụ thuộc của engine — `pyyaml`, `networkx`, `pypdf` — được cài kèm. Không
có gói thứ tư nào.

**Kiểm ngay là nó chạy được:**

```bash
.venv/bin/python -m eaa.cli --version
.venv/bin/python -m eaa.cli capabilities        # Agent làm được gì, kiểm bằng gì
```

Từ đây tài liệu viết `eaa` cho gọn. Trên máy bạn hoặc gõ đầy đủ
`.venv/bin/python -m eaa.cli`, hoặc `source .venv/bin/activate` một lần rồi
gõ `eaa`.

> **Đừng đặt bí danh `eaa` trỏ tới Python hệ thống.** Gói cài trong `.venv`;
> chạy bằng Python khác sẽ báo thiếu `pyyaml` chứ không báo sai môi trường.

---

## 3. Kiểm bộ test trước khi tin vào bất cứ thứ gì

```bash
.venv/bin/python -m pytest -q
```

Mất khoảng **4–5 phút**. Kết quả mong đợi hiện nay:

```
10 failed, 2374 passed in 259.51s
```

**10 bài đỏ là đã biết và đã ghi nhận**, tất cả trong `tests/test_tc15_e2e.py`.
Chúng là bài phát lại các lượt gọi mô hình đã ghi; prompt đổi thì băm prompt
đổi, và bộ phát lại **cố ý không bịa phản hồi** — bịa ra là tạo bằng chứng giả
cho chương đánh giá. Muốn xanh thì ghi lại bản ghi bằng mô hình thật:

```bash
.venv/bin/python scripts/record_e2e_fixture.py     # cần EAA_LLM_KEY
```

Nếu bạn thấy **nhiều hơn 10** bài đỏ, dừng lại — môi trường có vấn đề, đừng đi
tiếp. Chạy riêng bài canh nền tảng nhất:

```bash
.venv/bin/python -m pytest tests/test_tc38_engine_purity.py -q   # engine sạch phần cứng
.venv/bin/python -m pytest tests/test_tc03_state.py -q           # state ghi nguyên tử
```

### 3.1 Chạy nhanh khi đang sửa mã

```bash
.venv/bin/python -m pytest -q -m "not cham"     # bỏ bài gọi LibreOffice
.venv/bin/python -m pytest tests/test_tc124_hop_dong_goi_khong_duoc_doi.py -q
```

Đừng bỏ nhóm `cham` trước khi giao — chúng là thứ duy nhất kiểm được nhánh PDF.

### 3.2 Vì sao cần bộ dịch máy chủ

Bài kiểm của firmware **không chạy trên bo**. Mã C của mỗi module được dịch
thành thư viện `.so` cùng lớp mock ngoại vi trong `packs/avr/hostmock/`, rồi
nạp vào pytest qua `ctypes`:

```python
lib = ctypes.CDLL("./liblogic_pid.so")
lib.pid_compute.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_bool]
lib.pid_compute.restype  = ctypes.c_float
```

Đó là lý do firmware được viết tách lớp trừu tượng phần cứng — không phải vì
đẹp mã, mà để **kiểm được trước khi có bo**. Máy thiếu `cc` thì cổng
`unittests` sẽ đỏ ở mọi module.

---

## 4. Công cụ nền tảng — và vì sao cài cũng phải duyệt

```bash
eaa doctor                       # CHỈ ĐỌC, không đổi gì trên máy
```

Kết quả trên một máy đã đủ công cụ:

```
công cụ           trạng thái  phiên bản
git               OK          2.50.1
python            OK          3.12.13
avr-gcc           OK          7.3.0
avr-objcopy       OK          2.46.0
avr-size          OK          2.46.0
avrdude           OK          8.2
cppcheck          OK          2.21.0

Mọi công cụ bắt buộc đã sẵn sàng.
env_hash: sha256:5dccf65a84bca…
```

Thiếu công cụ thì **Agent không tự cài**. Quy trình ba bước, và bước giữa là
của người:

```bash
eaa doctor --plan                              # cài theo THỨ TỰ nào, và chỗ nào đá nhau
eaa doctor approve avr-gcc avrdude --actor "Tên bạn"   # bạn đọc lệnh cài rồi duyệt
eaa doctor --fix                               # chỉ chạy lệnh ĐÃ duyệt
```

`eaa doctor --fix` không có chế độ tự duyệt. Chạy nó khi chưa duyệt thì nó
dừng và nói cần duyệt gì — đây là Human Gate, không phải một lời nhắc.

Cài tay cũng được, nếu bạn thích:

```bash
# macOS
brew tap osx-cross/avr && brew install avr-gcc avrdude cppcheck

# Ubuntu / Debian
sudo apt install gcc-avr binutils-avr avr-libc avrdude cppcheck
```

Cài xong chạy lại `eaa doctor` để nó cập nhật `env_hash`. Con số ấy đi vào
Project State: nếu môi trường đổi giữa chừng, hệ thống biết và nói ra thay vì
âm thầm cho ra kết quả khác.

### 4.1 Khoá API mô hình

```bash
export EAA_LLM_KEY="…"            # KHÔNG bao giờ commit, không ghi ra log (TC-14)
eaa models                        # xem danh mục và mô hình đang ghim
```

Chưa có khoá vẫn chạy được **gần hết** hệ thống: mọi lệnh chỉ đọc, mọi báo
cáo, bộ test, và chế độ `--preview`. Chỉ những lệnh thật sự gọi mô hình mới
cần.

### 4.2 Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `EAA_LLM_KEY` | Khoá API. Bắt buộc khi gọi mô hình thật |
| `EAA_LLM_MODEL` | Ghim mô hình cho mọi lượt chạy; cờ `--model` mạnh hơn |
| `EAA_LLM_TIMEOUT_S` | Hạn chờ mỗi lượt gọi |
| `EAA_PROJECT` | Dự án mặc định, khỏi gõ `--project` mỗi lệnh |
| `EAA_HOME` | Gốc cây `projects/` và `packs/`. Mặc định là thư mục kho |
| `EAA_ACTOR` | Tên người quyết định mặc định ở các gate |
| `EAA_NO_NET=1` | **Cắt hẳn mạng.** Bộ test tự xoá biến này để không phụ thuộc shell |
| `EAA_SCRATCH` | Chỗ làm nháp |

Kho có ba dự án sẵn: `robot_balance` (dự án mẫu, đã chạy trên bo),
`blklab_robot`, `disco_f469` (STM32, mới tới bước phân rã). Có nhiều hơn một
dự án thì **phải** nêu rõ:

```bash
export EAA_PROJECT=projects/robot_balance
# hoặc thêm --project projects/robot_balance vào từng lệnh
```

---

## 5. Đường A — chạy lại dự án mẫu

Nhanh nhất để thấy hệ thống hoạt động thật. Không sinh mã mới, không tốn token.

```bash
export EAA_PROJECT=projects/robot_balance

eaa status                    # pha nào, gate nào chờ, bước kế tiếp là gì
eaa resume                    # khôi phục phiên từ Project State
eaa plan list                 # 9 module, 7 đã merge
eaa report kpi                # số liệu Chương 3
eaa report review             # khâu nào hay hỏng, và nên sửa gì
eaa deviations                # chỗ mã và tài liệu kể hai câu chuyện khác nhau
```

### 5.1 Ráp firmware từ mã đã merge

```bash
eaa build
```

Chỉ mã đã qua G3 mới vào được ảnh. Bản thiết kế ráp nhắc tới một module chưa
merge thì lệnh dừng ngay — **không có đường tắt nào đưa mã chưa duyệt xuống
thiết bị**. Kết quả:

```
Vòng lặp chính: …/firmware/build/main.c
Ảnh liên kết  : …/firmware/build/firmware.elf
Ảnh nạp được  : …/firmware/build/firmware.hex
Thẻ an toàn   : đã ghi (cổng nạp sẽ đọc trước khi bạn duyệt)
```

### 5.2 Nạp xuống bo — Human Gate G5

Cắm bo trước, rồi:

```bash
eaa ports                     # cổng nối tiếp nào đang có, bo nào được nhận
eaa flash                     # sẽ TỪ CHỐI: chưa có xác nhận của người
```

Lệnh in ra checklist an toàn và đòi xác nhận **từng mục, nguyên văn**:

```bash
eaa flash approve \
  --image projects/robot_balance/firmware/build/firmware.hex \
  --actor "Tên bạn" \
  --confirm-safety "Sàn quanh robot trống trong bán kính 1 m, không có vật cứng hay cạnh bàn" \
  --confirm-safety "Có người đứng cạnh, tay sẵn sàng đỡ, và biết tắt nguồn động lực ở đâu" \
  --confirm-safety "Nguồn động lực có công tắc ngắt trong tầm với, KHÔNG phải rút giắc" \
  --confirm-safety "Robot đặt trên sàn phẳng, không phải mặt bàn cao" \
  --confirm-safety "Dây nối máy tính đủ dài để robot ngã mà không giật đứt hoặc kéo đổ đồ"

eaa flash --image projects/robot_balance/firmware/build/firmware.hex
```

Quyết định neo vào **băm nội dung ảnh**, không vào đường dẫn — ráp lại là ảnh
khác, và phải duyệt lại. Nạp xong hệ thống **đọc ngược** bộ nhớ chip và đối
chiếu:

```
Đã nạp sha256:06797d7673bd… lên /dev/cu.usbserial-143410.
Commit đang chạy trên thiết bị: 80ec03d0d4
Kiểm sau khi nạp: ĐÃ KIỂM — đọc ngược khớp ảnh.
```

Từ đây mọi số đo lấy về đều gắn với commit ấy. Xem lại: `eaa flash --history`.

### 5.3 Robot làm gì sau khi nạp

Giao thức bíp của firmware hiện tại:

1. **1 bíp** — sẵn sàng, đang đợi bạn bấm nút
2. Bấm nút → đo trôi con quay, 500 mẫu. **Giữ robot YÊN**, không cần thẳng
3. **2 bíp liền** — đo xong
4. Dựng robot thẳng đứng; khi `|góc| < 0,5°` nó tự vào vòng cân bằng, bánh bắt
   đầu làm việc → **thả tay từ từ**

**3 bíp lặp lại đều đều** nghĩa là quá hạn hiệu chỉnh và động cơ đã tắt — bo
đang tự nói ra nó hỏng ở đâu, không phải chết.

---

## 6. Đường B — dựng dự án mới từ đầu

Đây là luồng đầy đủ, mười bước, ba Human Gate trước khi có dòng mã đầu tiên.

### Bước 1 — Agent dò bo và hỏi bạn

```bash
eaa brief --board "tên bo của bạn" --ask
```

Chạy **trước** `eaa init`. Agent dò trước rồi mới hỏi, và chỉ hỏi những gì máy
không tự biết được. Kết quả là `constraints.yaml` và `hardware_profile.yaml`
ở **dạng đề xuất** — chưa có hiệu lực cho tới khi bạn duyệt G1.

### Bước 2 — Khởi tạo Project State

```bash
eaa init --model gemini-3.1-pro-preview
eaa status
```

`init` cần hai tệp bước 1 dựng ra. Mô hình được **ghim vào Project State**, để
mọi lượt sinh sau này tái lập được.

### Bước 3 — Agent đề xuất, bạn chốt

```bash
eaa propose scope             # phạm vi, và cái KHÔNG làm, kèm lý do
eaa propose constraints       # mỗi ràng buộc kèm HỆ QUẢ nếu vi phạm
eaa propose acceptance        # tiêu chí = số + đơn vị + cách đo
eaa propose pinmap            # bảng chân, kiểm chức năng thay thế
eaa safety propose            # phân tích hỏng hóc và chế độ an toàn
eaa budget propose            # chia flash/RAM theo module TRƯỚC khi viết mã
```

Mỗi lệnh dựng một **đề xuất**, không phải một quyết định.

### Bước 4 — G1: chốt ràng buộc và kiến trúc

```bash
eaa gate show G1
eaa gate approve G1 --actor "Tên bạn" --expect <băm bạn vừa xem>
```

`--expect` là chỗ đáng dùng: nó neo lời duyệt vào **đúng nội dung bạn đã đọc**.
Hồ sơ đổi giữa lúc xem và lúc duyệt thì lệnh từ chối.

### Bước 5 — Nạp tri thức và G2

```bash
eaa sources need --lookup     # tài liệu cần, đích danh, kèm nguồn chính chủ
eaa errata lookup --rev <rev in trên chip>    # lỗi chip đã công bố cho ĐÚNG rev

eaa datasheet add tai_lieu.pdf \
    --device ATmega328P --peripheral twi \
    --pages 222-224 --topic "TWI bit rate"

eaa datasheet list
eaa gate show G2
eaa gate approve G2 --actor "Tên bạn"
```

**Chọn trang là việc của kỹ sư**, không phải của Agent — bỏ trống `--pages` là
nuốt cả tài liệu vào kho. Chỉ trích đoạn đã qua G2 mới được truy xuất; đây là
hàng rào chống nhiễm bẩn kho tri thức.

### Bước 6 — Phân rã và hợp đồng gọi

```bash
eaa plan add drv_i2c --uses twi,imu
eaa plan add logic_pid --depends-on drv_imu
eaa plan list
eaa interface logic_pid --write     # sinh HEADER trước khi sinh thân
```

`eaa interface --write` đáng làm, không phải tuỳ chọn cho đẹp: hợp đồng gọi
được chốt trước thì lượt sinh sau không tự bịa ra một chữ ký khác. Có một cổng
canh việc này (SL-163), nhưng chốt trước vẫn rẻ hơn sửa sau.

### Bước 7 — Sinh mã

```bash
eaa gen logic_pid --preview      # xem mô hình sẽ viết gì, KHÔNG chạy cổng nào
eaa gen logic_pid                # thật: 13 bước, dừng ở G3
```

Một lượt thật chạy: ghép prompt 7 lớp → gọi mô hình → **hợp đồng gọi** → chuỗi
bốn cổng (dịch → kích thước → phân tích tĩnh → kiểm thử đơn vị) → tự sửa ≤ 3
vòng dạng vá → commit lên nhánh riêng → **dừng, chờ người**.

Mã thoát: `0` xong · `2` chờ gate · `3` quá số lần tự sửa · `4` lỗi môi trường.

### Bước 8 — G3: đọc mã, rồi mới duyệt

```bash
eaa gate show G3                 # diff + checklist sinh từ Knowledge Graph
eaa gate approve G3 --actor "Tên bạn"
# hoặc
eaa gate reject G3 --reason "nêu rõ sai ở đâu và vì sao"
```

**Đây là bước tốn công nhất, và không rút ngắn được.** Tỉ lệ từ chối trong dự
án mẫu là 13/30 ≈ 43%, và bốn dạng lỗi hay gặp nhất **không cổng tự động nào
bắt được** — mã tự chỉnh đồ đo cho vừa mình, đúng công thức nhưng sai thứ tự,
phá hợp đồng gọi, và bài kiểm xanh vì lý do sai. Xem
[`DANH_GIA_NANG_LUC_AGENT.md`](DANH_GIA_NANG_LUC_AGENT.md) §3.

Câu lý do bạn gõ khi từ chối **có mặt nguyên văn trong prompt lần sinh lại** —
đó là kênh huấn luyện chính, nên viết cho rõ.

Duyệt xong module tự merge vào `main`. Cần sinh lại một module đã merge:

```bash
eaa plan reopen logic_pid --reason "nêu rõ vì sao mở lại"
```

### Bước 9 — Ráp và nghiệm thu

```bash
eaa build                     # ngưỡng bộ nhớ đo trên CẢ firmware, không từng module
eaa sim run <kịch bản>        # mô phỏng MIL/SIL nếu dự án có mô hình
eaa gate approve G4           # nghiệm thu: tiêu chí đặt TRƯỚC, không phải diff
```

### Bước 10 — Nạp và đo trên bo

```bash
eaa flash approve --image … --actor … --confirm-safety "…"   # G5
eaa flash --image …
eaa telemetry --port <cổng> --seconds 30      # kênh máy
eaa diagnose measure DS-02                    # kênh người: hỏi câu người trả lời được
eaa endurance --port <cổng> --seconds 600     # chạy dài, bắt reset qua bộ đếm
```

Chẩn đoán ở đây **hai kênh** có chủ ý: máy đọc telemetry, người trả lời câu hỏi
quan sát được bằng mắt. Một kênh nói dối thì kênh kia lộ ra.

---

## 7. Nói chuyện với Agent bằng tiếng Việt

Không nhớ lệnh nào cũng làm việc được:

```bash
eaa chat                                    # mở phiên
eaa chat "còn gì chặn tôi nạp firmware"
eaa chat "robot ngã về bên trái, xem giúp"
eaa focus                                   # cả quãng đường còn lại, một lần
eaa suggest                                 # cái gì đang tốn công nhất
```

Agent tự chọn và tự chạy lệnh để tìm câu trả lời — nó không đoán trạng thái, nó
chạy `eaa status` rồi đọc kết quả thật. Nhưng **không một lệnh duyệt nào nằm
trong danh mục nó gọi được**: `gate approve/reject`, `flash approve`,
`doctor approve`, `tool approve`, `skill approve`. Không phải vì bị dặn — mà vì
danh mục không chứa chúng.

---

## 8. Sự cố thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| `ModuleNotFoundError: yaml` | Đang chạy bằng Python khác `.venv`. Gõ đầy đủ `.venv/bin/python -m eaa.cli` |
| `Không có thư mục dự án` | Có 3 dự án nên phải nêu rõ: `--project projects/robot_balance` hoặc đặt `EAA_PROJECT` |
| `Đã có Project State` | Dùng `eaa resume`. Chỉ `init --force` khi thật sự muốn làm lại từ đầu |
| Cổng `unittests` đỏ ở **mọi** module | Máy thiếu bộ dịch máy chủ (`cc`). Xem §3.2 |
| Cổng `compile` báo lỗi **cấu hình** | Thiếu avr-gcc, hoặc `parse.error_regex` của pack không khớp. `eaa doctor` trước |
| `eaa gen` dừng ngay: *"Cổng đỏ vì mã NGOÀI phạm vi module này"* | Module này đổi chữ ký làm module đã merge chết. Xem diff header trước khi sinh lại (SL-162) |
| `eaa build`: *"nhắc tới module chưa merge"* | Đúng như thiết kế. Duyệt G3 cho module ấy, hoặc bỏ nó khỏi `firmware.yaml` |
| `eaa flash` từ chối | Thiếu một trong bốn điều: ảnh đã ráp, kho sạch, ảnh mới hơn nguồn, người xác nhận |
| Duyệt lại sau khi ráp lại | Đúng như thiết kế: quyết định neo vào băm nội dung ảnh |
| Bo im, không bíp | Kiểm `eaa ports` trước. Nếu bo được nhận mà vẫn im thì đọc §5.3 — 3 bíp lặp là quá hạn hiệu chỉnh |
| Prompt quá dài | `eaa gen` in ra lớp nào dùng quá phần. Cắt trong `projects/<dự án>/prompts/<module>.md` |
| Không có mạng | `export EAA_NO_NET=1`. Mọi lệnh tra cứu sẽ nói rõ nó không đi được, thay vì bịa |

---

## 9. Những chỗ KHÔNG có đường tắt

Nếu bạn đang tìm cờ để bỏ qua một trong những điều dưới đây thì không có, và
đó là toàn bộ giá trị của sản phẩm:

* **Merge** chỉ xảy ra khi toàn bộ `ToolReport.passed` **và** G3 đã duyệt. Phép
  kiểm nằm trong hàm dựng `MergeAuthorization`, nên không ai dựng được giấy
  phép mà bỏ qua kiểm.
* **Chế độ nháp** (`--draft`) không merge được — không phải vì bị chặn, mà vì
  nó không ghi bằng chứng, nên tới bước merge không có gì để đọc.
* **Cài công cụ** và **nạp firmware** luôn cần người xác nhận.
* **Ảnh làm thiết bị chuyển động** đòi xác nhận từng mục checklist an toàn.
* **Vòng tự sửa** tối đa 3 lần; quá thì dừng và bàn giao người.
* **Ngân sách prompt** ≤ 8.000 token vào, đếm **trước** khi gọi mô hình.
* **Mọi kho tri thức** append-only + supersede; mâu thuẫn thì người phân xử.
* **Khoá API** không bao giờ ghi ra log hay commit.

---

## 10. Đọc tiếp

| Tài liệu | Khi nào cần |
|---|---|
| [`../README.md`](../README.md) | Kiến trúc C4, công nghệ, tiến độ |
| [`HUAN_LUYEN_AGENT_CHO_BO_MOI.md`](HUAN_LUYEN_AGENT_CHO_BO_MOI.md) | Đưa Agent sang bo mới hoặc chip mới, từng bước |
| [`TIEP_TUC_TU_DAY.md`](TIEP_TUC_TU_DAY.md) | Bàn giao phiên gần nhất, việc kế tiếp |
| [`DANH_GIA_NANG_LUC_AGENT.md`](DANH_GIA_NANG_LUC_AGENT.md) | Agent tự làm được gì, và phương pháp huấn luyện |
| [`SAI_LECH_THIET_KE.md`](SAI_LECH_THIET_KE.md) | 164 mục lỗi đã gặp, mỗi mục có bài kiểm canh |
| [`HUONG_DAN_KIEM_THU.md`](HUONG_DAN_KIEM_THU.md) | Chạy và đọc bộ test |
| [`md/EAA-SDD-03_Thiet_ke_chi_tiet.md`](md/EAA-SDD-03_Thiet_ke_chi_tiet.md) | Bản vẽ thi công: cây thư mục, lược đồ dữ liệu |
