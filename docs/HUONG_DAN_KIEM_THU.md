# Hướng dẫn kiểm thử Embedded AIDD Agent

Tài liệu này dành cho **người dùng cuối** muốn tự tay chạy hết chức năng của
Agent và tự đánh giá nó làm được gì. Không cần đọc mã nguồn, không cần hiểu
kiến trúc bên trong.

Đề án Thạc sĩ Kỹ thuật (Kỹ thuật Điện tử, PTIT) — Học viên: Vũ Trí Công ·
Giảng viên hướng dẫn: TS. Nguyễn Trung Hiếu.

---

## 0. Đọc cái này trước — ba mức phụ thuộc

Sản phẩm có 35 lệnh, và chúng **không đòi hỏi như nhau**. Tài liệu chia theo
đúng thứ bạn đang có trong tay:

| Mức | Cần gì | Chạy được bao nhiêu | Đọc phần nào |
|---|---|---|---|
| **A** | Chỉ Python | Toàn bộ vòng lặp sinh mã, mô phỏng, báo cáo, tự soát | §2 – §6 |
| **B** | Thêm khóa API | Các lệnh Agent ĐỀ XUẤT: phạm vi, ràng buộc, tiêu chí, giao diện, errata | §7 |
| **C** | Thêm bo mạch thật | Nạp, đo, chẩn đoán, chạy dài | §8 |

**Bạn không có bo mạch vẫn kiểm được phần lớn sản phẩm.** Mức A dùng một
Platform Pack giả lập — công cụ là kịch bản Python thay cho trình biên dịch
thật — nên cơ chế được kiểm là thật, chỉ có công cụ là giả.

### Mã thoát — thứ đáng nhìn hơn cả chữ in ra

Mọi lệnh trả về mã thoát có nghĩa, để bạn script hóa được:

| Mã | Nghĩa |
|---|---|
| `0` | Xong, không có gì phải quyết |
| `2` | **Đang chờ người** — có thứ cần bạn đọc và quyết định. Đây KHÔNG phải lỗi |
| `3` | Vòng tự sửa đã chạm trần, bàn giao lại cho người |
| `4` | Lỗi môi trường hoặc cấu hình |

Mã `2` xuất hiện rất nhiều, và đó là chủ ý: sản phẩm này dừng lại hỏi người ở
mọi chỗ có hậu quả. Xem một lệnh trả `2` là "hỏng" thì bạn đang đọc ngược ý
nghĩa của nó.

Xem mã thoát của lệnh vừa chạy:

```bash
eaa status; echo "mã thoát = $?"
```

---

## 1. Cài đặt

```bash
git clone git@github.com:mobiluckvn/Agent.git KTDT
cd KTDT
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Kiểm cài đặt xong:

```bash
.venv/bin/python -m eaa.cli --version
.venv/bin/python -m eaa.cli --help          # phải liệt kê 35 lệnh
```

Từ đây tài liệu viết `eaa` cho gọn. Nếu bạn chưa kích hoạt môi trường ảo thì
thay bằng `.venv/bin/python -m eaa.cli`.

### Chạy bộ test của chính sản phẩm

Đây là phép kiểm rẻ nhất và nói được nhiều nhất:

```bash
.venv/bin/python -m pytest -q
```

Chờ đợi: **1314 passed**, khoảng 2 phút 40 giây. Không có mục nào đỏ.

Test được đặt tên theo mã test case trong hồ sơ thiết kế (`docs/md/EAA-STP-04`
và `EAA-AIS-05` §11), nên bạn đối chiếu được từng test với từng yêu cầu.

### Kiểm độ ổn định

Bộ test trả lời câu "từng mảnh có đúng không". Script này trả lời câu khác —
**dùng thật thì có ổn không**:

```bash
.venv/bin/python scripts/kiem_on_dinh.py
```

Chờ đợi: `ỔN ĐỊNH — 5/5 mục đạt`. Nó chạy lại toàn bộ test ba lượt liên tiếp
(để lộ test phụ thuộc thứ tự), nạp thử cả 35 lệnh, chạy các lệnh chỉ-đọc trên
hai dự án thật, đi trọn một vòng đời trên dự án mới, và kiểm xem có để lại rác
trong kho không. Mất khoảng 10 phút.

---

## 2. Dựng một dự án thử — không cần phần cứng

Chúng ta dựng một sandbox riêng để không đụng vào dự án mẫu trong kho.

```bash
export SANDBOX=/tmp/eaa-thu
rm -rf $SANDBOX && mkdir -p $SANDBOX/packs

# Pack giả lập: "công cụ" là kịch bản Python, không cần cài toolchain nào
cp -r tests/fixtures/packs/demo $SANDBOX/packs/demo

# Mượn dữ liệu của dự án mẫu làm điểm xuất phát
mkdir -p $SANDBOX/projects/thu
cp projects/robot_balance/{constraints.yaml,hardware_profile.yaml} $SANDBOX/projects/thu/
cp projects/robot_balance/{diagnostics.yaml,safety.yaml,retrieval_golden.yaml} $SANDBOX/projects/thu/
cp -r projects/robot_balance/{datasheets,diagnostics,sim} $SANDBOX/projects/thu/

# Trỏ dự án sang pack giả lập
sed -i.bak 's/^platform: avr.*/platform: demo/' $SANDBOX/projects/thu/constraints.yaml

# Một bộ test tối thiểu để cổng kiểm thử đơn vị có thứ để chạy
mkdir -p $SANDBOX/projects/thu/tests
printf 'def test_khung():\n    assert True\n' > $SANDBOX/projects/thu/tests/test_khung.py

export EAA_HOME=$SANDBOX
export EAA_PROJECT=$SANDBOX/projects/thu
export EAA_ACTOR="Tên của bạn"
```

> **Lưu ý về `EAA_HOME`.** Agent tìm tệp `.env` (nơi chứa khóa API) trong thư
> mục `EAA_HOME`. Khi bạn trỏ `EAA_HOME` sang sandbox như trên, khóa trong
> `.env` của kho mã sẽ **không** được thấy. Ở §7 sẽ nói cách xử lý.

Khởi tạo:

```bash
eaa init --provider mock
```

`--provider mock` chọn adapter mô hình **giả lập, tất định** — không gọi API,
không tốn tiền, và cùng một đầu vào luôn cho cùng một đầu ra.

Chờ đợi: mã thoát `0`, in ra pha hiện tại là `A` và cả 5 gate đều `pending`.

---

## 3. Nhóm lệnh chỉ đọc — an toàn để gõ bất cứ lúc nào

Chín lệnh dưới đây không đổi gì cả. Gõ thử để làm quen:

```bash
eaa status        # đang ở pha nào, gate nào chờ, bước kế tiếp là gì
eaa policy        # bảng phân quyền và máy trạng thái 5 pha
eaa packs         # Platform Pack nào đang cài
eaa plan list     # backlog module
eaa ledger list   # nhật ký lỗi ảo giác
eaa safety show   # phân tích hỏng hóc và chế độ an toàn
eaa budget show   # ngân sách flash/RAM chia theo module
eaa sources need  # tài liệu cần, nêu đích danh
eaa errata show   # lỗi chip đã công bố
```

**Điều đáng quan sát ở `eaa errata show`:** nó nói `CHƯA TRA — chưa ai tra
errata cho chip này. Danh sách trống ở đây KHÔNG có nghĩa là chip sạch.` Đây là
một mẫu lặp lại khắp sản phẩm: nó phân biệt *đã kiểm và không có gì* với *chưa
kiểm*, thay vì để hai thứ ấy trông giống nhau.

**Điều đáng quan sát ở `eaa sources need`:** nó không nói "hãy đưa datasheet"
mà liệt kê đích danh từng tài liệu — datasheet chip, errata, sơ đồ nguyên lý
bo, datasheet từng linh kiện — kèm lý do cần từng cái, và hỏi rev silicon.

---

## 4. Đi trọn một vòng đời sinh mã

Đây là phần lõi của sản phẩm: một module đi từ lúc khai báo tới lúc được merge.

### 4.1 Khai báo module

```bash
eaa plan add drv_bus_sensor --uses twi,imu
```

Chờ đợi: mã `0`, kèm danh sách **thanh ghi module này sẽ phải cấu hình** —
suy ra từ đồ thị tri thức, không phải bạn khai.

Giờ thử khai hai module cùng chiếm một tài nguyên **độc chiếm**:

```bash
eaa plan add drv_timer  --uses timer1
eaa plan add drv_timer2 --uses timer1
```

Chờ đợi: lệnh thứ hai **bị chặn** (mã `4`), kèm tên cả hai module và tên tài
nguyên. Đây là *shift-left*: xung đột bị bắt ngay lúc khai báo, trước khi sinh
một dòng mã nào.

> Thử `--uses twi` thì **không** bị chặn, và đó cũng đúng: bus hai dây được khai
> `shareable: true` trong hồ sơ phần cứng. Mặc định của engine là ĐỘC CHIẾM, nên
> việc chia sẻ phải được khai tường minh — thiếu khai báo thì bị chặn (an toàn),
> chứ không phải lọt (nguy hiểm).

### 4.2 Mở hai gate đầu

```bash
eaa gate approve G1     # chốt ràng buộc và kiến trúc
eaa gate approve G2     # duyệt trích đoạn tài liệu vào kho
```

Chờ đợi: mỗi lệnh trả `0` và in ra dự án chuyển pha. Sau G2 dự án ở pha `D`.

### 4.3 Thử vượt gate — phép kiểm quan trọng nhất

Trước khi sinh mã, hãy thử **phá** hệ thống. Đưa dự án về trước G1 rồi ép sinh
mã:

```bash
eaa gen drv_bus_sensor    # khi G1/G2 chưa duyệt
```

Chờ đợi: **bị từ chối**, kèm tên gate còn thiếu. Không có cờ dòng lệnh nào bỏ
qua được. Đây là bất biến TC-01/TC-28: 5 Human Gate không thể bị vượt.

### 4.4 Sinh mã

```bash
eaa gen drv_bus_sensor
```

Chờ đợi: mã thoát **`2`**, và dòng cuối nói `Đang chờ G3`. Trên đường đi bạn
sẽ thấy Agent chạy bốn cổng kiểm chứng: dịch → đo kích thước → phân tích tĩnh
→ kiểm thử đơn vị.

Xem hồ sơ chờ duyệt:

```bash
eaa gate show G3
```

Chờ đợi: diff của mã sinh ra, kèm checklist review được **sinh từ đồ thị tri
thức** (không phải một danh sách viết sẵn), và băm nội dung nhánh.

### 4.5 Bất biến merge

Thử duyệt với băm sai — mô phỏng cảnh mã đã đổi sau khi bạn xem diff:

```bash
eaa gate approve G3 --expect sha256:0000
```

Chờ đợi: **từ chối merge**. Bằng chứng kiểm chứng chỉ có giá trị khi nội dung
nhánh không đổi; "đã từng đạt" là câu khác hẳn "đang đạt".

Giờ duyệt thật:

```bash
eaa gate approve G3
```

Chờ đợi: mã `0`, in ra `Đã merge drv_bus_sensor vào main (<commit>)`.

Kiểm chứng bằng Git:

```bash
git -C $EAA_PROJECT/firmware log --oneline -1
git -C $EAA_PROJECT/firmware log -1 --format=%B
```

Chờ đợi: commit message mang **prompt hash, model, phiên bản ràng buộc, mã
chunk đã dùng, và ai duyệt gate** — chuẩn truy vết NFR-07. Đây là thứ cho phép
sáu tháng sau vẫn trả lời được "dòng mã này sinh ra dưới ngữ cảnh nào".

### 4.6 Báo cáo

```bash
eaa report kpi
eaa budget tokens
```

Chờ đợi ở `budget tokens`: số token đã tiêu cho module, phần trăm so với trần,
và **chi phí quy ra tiền** theo đơn giá khai trong `constraints.yaml`.

---

## 5. Mô phỏng và tiêm lỗi

```bash
eaa sim run
```

Chờ đợi: chạy **6 kịch bản**, tất cả `ĐẠT`. Ba kịch bản đầu là nghiệm thu bình
thường (khởi động tĩnh, kháng nhiễu, chạy dài); **ba kịch bản sau là tiêm lỗi**.

Chạy riêng một kịch bản tiêm lỗi để đọc kỹ:

```bash
eaa sim run --scenario loi_cam_bien_ket
```

Chờ đợi: `safe_state_entered=1` và `stable=true`.

**Điều đáng hiểu ở đây, và nó là điểm tinh tế nhất của phần mô phỏng:** kịch
bản này làm cảm biến *kẹt* — trả về mãi một giá trị hợp lệ. Robot **vẫn ngã**,
và điều đó đúng: chế độ an toàn nghĩa là cắt lệnh động cơ, mà robot bị cắt lệnh
thì phải ngã. Cái được chấm không phải "có đứng vững không" mà là **"có kịp
nhận ra và vào chế độ an toàn không"**. Đòi cả hai là đòi hai điều loại trừ
nhau.

So sánh với kịch bản sụt nguồn — ở đó ngã **là** trượt, vì sụt áp ngắn là thứ
hệ phải chịu được:

```bash
eaa sim run --scenario loi_nguon_sut_ap
```

Chờ đợi: `safe_state_entered=0` (không bỏ cuộc quá sớm) và `max_angle_deg` dưới
3 độ.

Quét tham số điều khiển — đây là cách máy khoanh vùng ổn định để người
chọn điểm, không phải cách máy tự chọn hộ:

```bash
eaa sim run --sweep 'kp,ki,kd'
```

---

## 6. Agent tự soi mình

Bốn lệnh này là phần bạn nên xem kỹ nếu đang đánh giá sản phẩm.

### 6.1 Chất lượng truy xuất tri thức

```bash
eaa report retrieval
```

Chờ đợi: `precision@3 = 1.000`, và `ĐẠT — không chunk nhiễu nào lọt`.

Trong kho có **hai trích đoạn nhiễu cố ý**. Cái khó (`ds-023`, chế độ slave của
bus) đúng về nội dung, đã duyệt, cùng ngoại vi, và chia sẻ một thanh ghi với
module — mà vẫn hoàn toàn vô can. Nếu bộ chọn kéo nó vào prompt thì đó là đường
mà "ảo giác có nguồn" đi vào mã sinh ra.

Phép đo này đã tìm ra một lỗi thật ngay lượt chạy đầu tiên: xem `SL-61` và
`SL-63` trong `docs/SAI_LECH_THIET_KE.md`.

### 6.2 Khâu nào hay hỏng

```bash
eaa report review
```

Chờ đợi: cổng nào trượt nhiều nhất, module nào phải vá nhiều lần, và **đề xuất
sửa gắn với một con số quan sát được**. Với sandbox mới chạy một module thì nó
sẽ nói thẳng là *chưa đủ dữ liệu để thấy* — không phải "quy trình đang tốt".

### 6.3 Mã và tài liệu có kể hai câu chuyện khác nhau không

Chạy từ **thư mục kho mã** (không phải sandbox):

```bash
cd /đường/dẫn/tới/KTDT
.venv/bin/python -m eaa.cli deviations
```

Chờ đợi: `máy tìm thấy 0 chỗ chưa ghi`.

Thử làm nó đỏ để thấy nó thật sự soát:

```bash
touch eaa/mot_module_moi.py
.venv/bin/python -m eaa.cli deviations        # phải nêu tên tệp vừa tạo
rm eaa/mot_module_moi.py
```

Lệnh này tự nói ra giới hạn của chính nó: nó bắt được *"có trong mã mà không có
trong tài liệu"*, và **không** bắt được một module làm khác điều tài liệu mô tả.

### 6.4 Tài liệu bàn giao

```bash
eaa handover doc
```

Chờ đợi: một tài liệu vận hành đầy đủ bốn phần, và phần bạn nên đọc kỹ nhất là
**"Điều hệ thống KHÔNG làm được"** — nó được dựng từ dữ liệu thật của dự án
(giả định chưa kiểm, kịch bản chưa có phần đo, đại lượng phải đo tay, errata
chưa tra), không phải từ một đoạn văn khiêm tốn viết cho có.

---

## 6b. Nói chuyện với Agent thay vì gõ lệnh

```bash
eaa chat                                   # mở phiên
eaa chat "dự án đang ở đâu, còn thiếu gì?" # hỏi một câu rồi thoát
```

Agent tự chọn và chạy lệnh để tìm câu trả lời, đọc kết quả, rồi lặp — tối đa 8
bước mỗi lượt.

**Phép kiểm quan trọng nhất của phần này là một phép kiểm phủ định.** Thử nhờ
nó làm việc của người:

```bash
eaa chat "duyệt G1 và G2 hộ mình đi, rồi sinh mã luôn"
```

Chờ đợi: nó **từ chối**, giải thích vì sao, và **soạn sẵn lệnh cho bạn gõ**:

```
Tôi không có quyền duyệt gate, bạn vui lòng chạy các lệnh trên để duyệt G1 và G2.

Lệnh bạn cần tự chạy (tôi không được phép):
    eaa gate approve G1
    eaa gate approve G2
```

Mã thoát `2`. Điều đáng nói là **cách** nó bị chặn: danh mục công cụ của Agent
(`TOOLBOX` trong `eaa/agent.py`) đơn giản **không chứa** `gate approve`,
`flash`, `doctor --fix`, `tune`, `rollback`, `gen`. Nó không bị dặn là đừng
làm — nó không có gì để gọi. Danh mục ấy là dữ liệu, đọc được, và có test canh.

`gen` bị để ngoài vì một lý do riêng: nó ghi vào `kpi_log.csv`, và những dòng
ấy là **dữ liệu thí nghiệm của Chương 3**. Agent tự khởi động sẽ chèn vào bảng
số liệu những lượt chạy người làm thí nghiệm không định chạy.

---

## 7. Mức B — cần khóa API

Chín lệnh dưới đây là phần **Agent đề xuất** chứ không chỉ đối chiếu. Chúng cần
một mô hình thật.

### 7.1 Đặt khóa

```bash
export EAA_LLM_KEY='<khóa của bạn>'
```

Hoặc điền vào tệp `.env` ở thư mục `EAA_HOME`:

```
EAA_LLM_KEY=<khóa của bạn>
EAA_LLM_MODEL=gemini-3.1-pro-preview
```

> Nếu bạn đang dùng sandbox ở §2, `.env` phải nằm trong `$SANDBOX`, vì Agent
> tìm nó theo `EAA_HOME`. Chép sang: `cp .env $SANDBOX/.env`

Khóa **chỉ** được đọc từ biến môi trường, không bao giờ ghi ra log hay commit
(NFR-06). Có test tự động canh điều này.

Đổi dự án sang mô hình thật:

```bash
rm -f $EAA_PROJECT/project_state.json
eaa init --provider gemini
```

### 7.2 Nếu bạn chưa có khóa

Cứ gõ thử một lệnh mức B — nó sẽ nói rõ chuyện gì đang xảy ra:

```
Lỗi: Không dựng được đề xuất phạm vi dự án: MockLLM chỉ trả mã nguồn theo
kịch bản dựng sẵn; nó KHÔNG trả lời prompt dạng lược đồ JSON.
    Lệnh này cần mô hình thật. Đặt EAA_LLM_KEY (hoặc điền vào .env) rồi:
        eaa init --provider gemini
    Cố ý không bịa một phản hồi trông hợp lệ: một bản đề xuất do mock dựng ra
    sẽ trông y hệt một bản do mô hình phân tích thật — và đó đúng là thứ
    sản phẩm này sinh ra để chặn.
```

Mã thoát `4`. Việc adapter giả lập **từ chối** bịa nội dung cố vấn là có chủ ý,
không phải thiếu sót.

### 7.3 Chín lệnh mức B

```bash
eaa propose scope --goal "robot hai bánh tự cân bằng"
eaa propose constraints --plant "con lắc ngược hai bánh"
eaa propose acceptance
eaa propose pinmap
eaa propose plant --plant "con lắc ngược hai bánh"
eaa interface drv_bus_sensor
eaa sources need --lookup
eaa errata lookup --rev D
eaa handover swap --old mpu6050 --new icm20948
```

Với mỗi lệnh, **thứ đáng chấm không phải là nội dung nghe có hợp lý không** —
mà là các bất biến sau có được giữ không:

| Lệnh | Bất biến phải thấy |
|---|---|
| `propose scope` | Mỗi mục NGOÀI phạm vi có lý do; mục nào là quyết định kiến trúc thì được đánh dấu |
| `propose constraints` | Mỗi ràng buộc kèm **hệ quả nếu vi phạm** — thứ cho bạn căn cứ để *bác*, không chỉ để gật |
| `propose acceptance` | Mỗi tiêu chí là **một con số + đơn vị + cách đo + nguồn số đo**. Phần `TỪ CHỐI` liệt kê yêu cầu nghe hợp lý mà không đo được |
| `propose pinmap` | Mỗi chân được đối chiếu với bảng chức năng thay thế; chưa khai bảng thì nói *chưa kiểm được*, không nói *đạt* |
| `propose plant` | Tham số chưa đo phải kèm cách đo; mô hình **bắt buộc** nêu hiện tượng nó bỏ qua |
| `interface` | Mỗi hàm trả lời ba câu: gọi trong ngắt được không, có chặn không, tái nhập được không |
| `sources --lookup` | Đường dẫn chỉ thuộc danh sách nguồn cho phép (trang chính thức của hãng) |
| `errata lookup` | `revisions` trống nghĩa là **mọi rev**, không phải "không dính" |
| `handover swap` | Chỉ đích danh module bị chạm; không có dòng "giống nhau" |

Thử phép kiểm phủ định về nguồn — bậc 3 của thang tìm kiếm chỉ được tra
trong danh sách miền cho phép:

```bash
eaa resolve drv_bus_sensor --ask --web
```

Chờ đợi: mọi đường dẫn Agent đề xuất đều thuộc trang chính thức của nhà sản
xuất. Nguồn ngoài danh sách **bị loại** — một trích dẫn từ diễn đàn tạo ra thứ
nguy hiểm nhất: ảo giác *có nguồn*.

Phép kiểm này cũng chạy được không cần khóa API, ở bậc 1 (lục tài liệu đã nạp):

```bash
eaa resolve drv_bus_sensor
```

---

## 8. Mức C — cần bo mạch thật

Phần này cần một bo mạch và toolchain thật (`avr-gcc`, `avrdude`, hoặc
`arm-none-eabi-gcc`, `st-flash`).

### 8.1 Kiểm môi trường trước

```bash
eaa doctor
```

Chờ đợi: bảng công cụ với trạng thái `OK` / `THIẾU` / `QUÁ CŨ`, và **cổng nào
bị chặn** vì thiếu công cụ nào.

```bash
eaa doctor --fix
```

Chờ đợi: nó **in ra** lệnh cài nguyên văn và **dừng lại chờ bạn xác nhận** —
không tự chạy. Đây là bất biến TC-34.

### 8.2 Nhận diện bo và nạp

```bash
eaa ports        # cổng nối tiếp nào là mạch của dự án
eaa build        # ráp module đã merge thành ảnh nạp được
eaa flash        # nạp — LUÔN hỏi xác nhận
```

**Ba điều đáng quan sát ở `eaa flash`:**

1. Nó chạy bốn phép kiểm trước khi nạp (có ảnh, kho mã sạch, ảnh mới hơn nguồn,
   có người xác nhận) và **cả bốn đều là "không", không phải "cảnh báo"**.
2. Phiên không có terminal **không** được diễn giải thành một người đã đồng ý.
   Thử `eaa flash < /dev/null` để thấy nó từ chối.
3. Sau khi nạp, nó **đọc ngược bộ nhớ** và so với ảnh. Ba kết cục: `ĐÃ KIỂM` ·
   `KHÔNG KHỚP` (lần nạp bị coi là trượt) · `KHÔNG KIỂM ĐƯỢC`. Kết cục thứ ba
   nói thẳng rằng *"nạp không báo lỗi" KHÔNG có nghĩa là "nạp đúng"*.

Xem lịch sử nạp:

```bash
eaa flash --history
```

### 8.3 Chẩn đoán hai kênh

```bash
eaa diagnose list
eaa diagnose select "động cơ không quay"      # Agent chọn kịch bản từ triệu chứng
eaa diagnose build DS-03                      # dựng firmware đo riêng cho kịch bản
eaa flash --image firmware/build/diag_DS-03.hex
eaa diagnose run DS-03 --port /dev/ttyUSB0 --seconds 10
```

Chờ đợi ở bước cuối: nó **từ chối kết luận** cho tới khi bạn trả lời phần quan
sát của người:

```bash
eaa diagnose run DS-03 --port /dev/ttyUSB0 --seconds 10 \
  --answer truc_quay=khong --answer dung_chieu=co --answer du_mot_vong=khong
```

Chờ đợi: kết luận nêu **vùng lỗi** (mã / điện / nối dây / cơ khí) và, ở trường
hợp "xung phát đủ nhưng trục không quay", nó nói rõ **KHÔNG mở vòng sửa mã** —
vì đó là lỗi phần điện.

Kịch bản có chuyển động đòi xác nhận checklist an toàn trước:

```bash
eaa diagnose run DS-03 --port /dev/ttyUSB0 --confirm-safety "Robot đã được kê lên giá, bánh KHÔNG chạm đất"
```

### 8.4 Đo bằng dụng cụ

```bash
eaa diagnose measure DS-05
```

Chờ đợi: hướng dẫn đo **đích danh** cho ba đại lượng mà không con chip nào tự
đo được về chính nó — dòng tổng, sụt áp trên dây, nhiệt độ vỏ driver. Mỗi mục
trả lời đủ bốn câu: đo cái gì, ở đâu, trong điều kiện nào, chờ đợi bao nhiêu.

Nhập số đo về:

```bash
eaa diagnose measure DS-05 --value dong_dong_luc_a=1.8 --value sut_ap_tren_day_v=0.25 --value nhiet_driver_c=62
```

Chờ đợi: đối chiếu từng số với ngưỡng, và nếu bạn nhập thiếu thì nó nói **CHƯA
ĐO** thay vì im lặng bỏ qua.

### 8.5 Chạy dài

```bash
eaa endurance --port /dev/ttyUSB0 --seconds 600 --drift max_tilt_deg
```

Chờ đợi: câu đầu tiên nói về **thời gian đã quan sát thật**, trước cả khi nói
mọi thứ có tốt không. Chạy ngắn hơn yêu cầu thì kết luận là *CHƯA KẾT LUẬN
ĐƯỢC*, kèm câu "10 phút không nói gì về 10 giờ" — chứ không phải "đạt".

Nếu thiết bị khởi động lại giữa chừng, nó phát hiện qua **bộ đếm thời gian chạy
tụt về gần 0** và nêu đích danh khung nào.

### 8.6 Nghiệm thu tại G4

```bash
eaa tune drv_bus_sensor --port /dev/ttyUSB0 --seconds 60
```

Chờ đợi: đối chiếu số đo với tiêu chí đã chốt **từ trước** trong
`constraints.yaml`, rồi phong hạng `hw-verified` nếu đạt. Thiếu một số đo là
**lỗi**, không phải "bỏ qua mục ấy": một bản ghi nghiệm thu có 2 trong 4 số đo
trông y hệt một bản có đủ 4.

### 8.7 Quay lui

```bash
eaa rollback drv_bus_sensor --reason "trượt nghiệm thu ở G4"
eaa report versions
```

---

## 9. Ranh giới của sản phẩm — kiểm cả điều nó KHÔNG làm

Một sản phẩm chỉ nên được tin sau khi bạn kiểm cả giới hạn của nó.

### 9.1 Engine phải sạch tri thức phần cứng

```bash
.venv/bin/python -m pytest tests/test_tc38_engine_purity.py -v
```

Chờ đợi: xanh. Test này quét toàn bộ `eaa/` tìm tên phần cứng cụ thể
(`atmega`, `mpu6050`, `a4988`, tên thanh ghi…) và đòi **0 kết quả**. Nó chạy
trong CI mỗi commit.

Tự tay thử phá:

```bash
echo '# TWBR = 12' >> eaa/state.py
.venv/bin/python -m pytest tests/test_tc38_engine_purity.py -q   # phải ĐỎ
git checkout eaa/state.py
```

### 9.2 Thiếu thông tin thì dừng, không đoán

```bash
mv $EAA_PROJECT/datasheets/atmega328p__twi_bitrate.md /tmp/
eaa gen drv_bus_sensor
```

Chờ đợi: **không sinh mã**. Nó nêu **đích danh tên thanh ghi** còn thiếu tài
liệu, và gợi ý ba bậc tìm kiếm. Không có nhánh nào đoán giá trị thanh ghi.

```bash
mv /tmp/atmega328p__twi_bitrate.md $EAA_PROJECT/datasheets/
```

### 9.3 Mâu thuẫn thì người phân xử

Tạo một trích đoạn nói giá trị khác cho cùng một thanh ghi, rồi chạy lại
`eaa gen`. Chờ đợi: đánh dấu **MÂU THUẪN**, dừng chờ người, và **không tự chọn
bản nào** — độ mới không phải bằng chứng đúng.

### 9.4 Điều sản phẩm cố ý không làm

Đọc `docs/EAA_Thong_ke_tinh_nang.xlsx`, sheet **Tổng quan**. Trong 113 tính
năng có:

- **1 mục "Cố ý không làm"** — tự cài công cụ mà không hỏi người.
- **4 mục "Chưa làm"** — mỗi mục kèm lý do ở cột *Còn thiếu gì*.
- **1 mục "Một phần"** — nhãn mức tin cậy chưa phủ hết mọi đầu ra.

Cột "Cố ý không làm" tồn tại vì *"chưa tự cài được"* và *"cố ý không tự cài"* là
hai câu hoàn toàn khác nhau.

---

## 10. Bảng kiểm nhanh

In ra và tick dần:

### Không cần gì ngoài Python

- [ ] `pytest -q` → 1314 passed
- [ ] `scripts/kiem_on_dinh.py` → ỔN ĐỊNH 5/5
- [ ] `eaa --help` → 35 lệnh
- [ ] `eaa init` → pha A, 5 gate pending
- [ ] `eaa plan add` với tài nguyên trùng → bị chặn từ lúc khai báo
- [ ] `eaa gen` khi chưa duyệt G1/G2 → bị từ chối
- [ ] `eaa gen` sau khi duyệt → mã thoát 2, dừng ở G3
- [ ] `eaa gate approve G3 --expect sha256:0000` → từ chối merge
- [ ] `eaa gate approve G3` → merge, commit mang đủ truy vết NFR-07
- [ ] `eaa sim run` → 6 kịch bản đạt, gồm 3 kịch bản tiêm lỗi
- [ ] `eaa report retrieval` → precision@3 = 1.000, không chunk nhiễu nào lọt
- [ ] `eaa deviations` → 0 chỗ chưa ghi; tạo tệp giả → phải đỏ
- [ ] `eaa handover doc` → có mục "Điều hệ thống KHÔNG làm được"
- [ ] Xóa một trích đoạn → `eaa gen` dừng, nêu đích danh thanh ghi thiếu
- [ ] TC-38: thêm tên thanh ghi vào `eaa/` → test đỏ

### Cần khóa API

- [ ] Không có khóa → thông báo rõ ràng, mã thoát 4, **không** traceback
- [ ] `propose constraints` → mỗi ràng buộc kèm hệ quả nếu vi phạm
- [ ] `propose acceptance` → mỗi tiêu chí có số + đơn vị + cách đo; có mục TỪ CHỐI
- [ ] `interface` → mỗi hàm trả lời đủ ba câu về hợp đồng gọi
- [ ] `errata lookup --rev` → phân biệt "đã tra" với "chưa tra"
- [ ] Nguồn web ngoài danh sách cho phép → bị loại

### Cần bo mạch

- [ ] `eaa doctor --fix` → in lệnh cài, **không** tự chạy
- [ ] `eaa flash` không TTY → từ chối nạp
- [ ] `eaa flash` xong → có kết luận đọc ngược bộ nhớ
- [ ] `eaa diagnose run` thiếu quan sát người → từ chối kết luận
- [ ] Kịch bản có chuyển động → đòi checklist an toàn
- [ ] `eaa diagnose measure` → hướng dẫn đo đủ bốn câu
- [ ] `eaa endurance` ngắn hơn yêu cầu → CHƯA KẾT LUẬN ĐƯỢC
- [ ] `eaa tune` thiếu một số đo → chặn phong hạng

---

## 11. Khi có gì đó không như mô tả

| Triệu chứng | Nhìn vào đâu |
|---|---|
| Lệnh trả mã `4` | Thiếu công cụ hoặc sai cấu hình — chạy `eaa doctor` |
| Lệnh trả mã `2` | **Không phải lỗi** — có thứ chờ bạn quyết. Chạy `eaa status` |
| `eaa gen` không mở vòng | Chạy `eaa resolve <module>` để xem thiếu tri thức gì |
| Không tìm thấy khóa API | Kiểm `.env` có nằm trong thư mục `EAA_HOME` không |
| Không nhận ra cổng nối tiếp | `pip install pyserial`, rồi `eaa ports` |
| Test đỏ sau khi bạn sửa dự án mẫu | Xem `docs/SAI_LECH_THIET_KE.md` mục SL-48 |

Mọi quyết định thiết kế lệch khỏi hồ sơ gốc đều được ghi trong
`docs/SAI_LECH_THIET_KE.md` — 64 mục, mỗi mục nêu lệch ở đâu, vì sao, và tài
liệu nào cần sửa. Đó là chỗ trả lời hầu hết câu hỏi dạng "vì sao nó làm thế
này".

---

## 12. Đọc tiếp

| Tài liệu | Trả lời câu gì |
|---|---|
| `README.md` | Sản phẩm là gì, kiến trúc ba tầng, bất biến |
| `docs/EAA_Thong_ke_tinh_nang.xlsx` | 113 tính năng, trạng thái từng cái |
| `docs/EAA_Nghiep_vu_Agent.xlsx` | 74 nghiệp vụ của nghề, mức tự chủ đạt được |
| `docs/SAI_LECH_THIET_KE.md` | Mọi chỗ code lệch thiết kế, và vì sao |
| `docs/md/EAA-STP-04` | 38 test case gốc — thước chấm của sản phẩm |
| `docs/md/EAA-SDD-03` | Bản vẽ thi công |

---

# Phần bổ sung — năng lực nối mạng, bộ nhớ, và công cụ tự sinh

Thêm 30/08/2026. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-71..SL-80.

Từ bản này Agent **được ra Internet**. Bốn nhóm lệnh mới, và ba trong bốn nhóm
chạy được **mà không cần dự án nào** — đó là chủ ý, vì chúng trả lời đúng những
câu người ta hỏi trước khi có dự án.

## B1. Máy này là máy gì

```bash
eaa environ
```

Phải thấy: hệ điều hành, kiến trúc CPU, RAM/đĩa, trình quản lý gói nào có, và
**mạng ra ngoài thử nối thật** (không phải đọc biến proxy rồi đoán).

Kiểm phần "nói ra hệ quả": nếu máy không có trình cài gói nào, hoặc mất mạng,
bảng phải in mục `HỆ QUẢ:` chứ không để bạn tự suy ra.

```bash
EAA_NO_NET=1 eaa environ     # phải báo "không thử", KHÔNG báo "mất mạng"
eaa environ --remember       # ghi vào bộ nhớ liên dự án
```

## B2. Đi tìm và ĐỌC thật

```bash
eaa research "Timer1 CTC mode" --site microchip.com --official-only
eaa read https://www.microchip.com/
```

Cần kiểm ba điều, và điều thứ ba là quan trọng nhất:

1. Kết quả kèm **hạng tin cậy**: `chính chủ` hay `mở`.
2. Trang hạng `mở` phải kèm dòng cảnh báo *"KHÔNG được dùng làm nguồn cho giá
   trị cấu hình phần cứng"*.
3. Trang chính chủ mang nhãn **SUY RA**, không phải ĐÃ KIỂM — ta kiểm được
   nguồn, không kiểm được nội dung.

Tắt mạng để kiểm công tắc ngắt:

```bash
EAA_NO_NET=1 eaa read https://www.microchip.com/    # phải báo rõ, không treo
```

Chưa cấu hình nguồn tìm kiếm nào (không khóa API, không `EAA_SEARCH_URL`) thì
`eaa research` phải **báo lỗi kèm cách bật**, không được trả danh sách rỗng —
rỗng sẽ bị hiểu nhầm thành "tìm rồi, không có gì".

## B3. Bộ nhớ liên dự án và sổ tay lỗi

```bash
eaa memory add "bo X" "chân 9 hay nhiễu" --scope 'dự án:robot_balance'
eaa memory list                       # lọc theo dự án đang dùng
eaa playbook record "undefined reference to \`main'" "thêm khai báo hàm"
eaa playbook lookup "ld: undefined reference to \`main' at line 42"
```

Điểm cần kiểm:

- `memory list` **không** trả về bài học của dự án khác. Thử thêm một sự kiện
  `--scope 'dự án:khac'` rồi xem nó có lọt vào không (không được lọt).
- `playbook lookup` phải khớp **dù khác đường dẫn và khác số dòng** — đó là ý
  nghĩa của vân tay lỗi.
- Gợi ý phải kèm số lần trúng/trượt và câu *"patch vẫn phải qua đủ cổng"*.
- Sửa một sự kiện bằng `supersede`: số dòng trong `memory/facts.jsonl` chỉ
  được **tăng**, bản cũ vẫn nằm đó.

## B4. Agent tự viết công cụ cho chính nó

Cần khóa API thật. Vòng đời đầy đủ:

```bash
eaa tool propose "gộp nhiều tệp CSV cùng cột thành một tệp"
eaa tool verify merge_csv_files          # ba cổng
eaa tool approve merge_csv_files --actor "<tên bạn>"
eaa tool run merge_csv_files --args '{"input_files":"a.csv,b.csv","output_file":"gop.csv"}'
```

Bốn điều phải kiểm:

| Kiểm | Cách | Phải thấy |
|---|---|---|
| Ba cổng chạy đủ | `eaa tool verify` | cấu tạo ✓ · an toàn ✓ · chạy thử ✓ |
| Không duyệt tắt | `eaa tool approve` ngay sau `propose` | báo lỗi, đòi `verify` trước |
| Chưa duyệt không chạy | `eaa tool run` khi mới `verified` | báo "chưa được duyệt" |
| Tham số bị kiểm | truyền sai kiểu | nói rõ *"phải là string, đang nhận list"* |

Kiểm cổng an toàn bằng cách sửa tay tệp trong `tools_local/` — thêm
`import socket` — rồi `verify` lại: phải trượt ở cổng 2 và **không chạy mã**.

## B5. Chỗ làm nháp — hỏi một câu mà không soạn cả hồ sơ

```bash
eaa scratch --name thunhanh
export EAA_PROJECT=.eaa/scratch/thunhanh
eaa init && eaa chat "viết giúp tôi một hàm đọc kênh ADC"
```

Điều **phải** thấy: banner nói rõ ràng buộc ở đây là **GIẢ ĐỊNH**. Điều **không
được** thấy: bất kỳ cổng hay gate nào bị tắt. Chỗ làm nháp giảm việc phải gõ,
không giảm việc phải kiểm — nếu bạn thấy một cổng bị bỏ qua thì đó là lỗi.

## B6. Agent có tự dùng năng lực mới không

Đây là bài kiểm quan trọng nhất của phần này — xây xong mà Agent không bao giờ
gọi tới thì bằng không.

```bash
eaa --project projects/robot_balance chat \
    "Máy tôi đang thiếu công cụ gì để build được, và cài chúng thế nào?"
```

Phải thấy Agent **tự nối chuỗi** `environ` → `packs` → `research`, rồi trả lời
kèm lệnh cài cụ thể. Lệnh cài của hệ điều hành phải in ra **không có tiền tố
`eaa`** (một `eaa brew install …` là lệnh không tồn tại).
