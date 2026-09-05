# Kế hoạch để Agent tốt hơn, không chỉ ngang bằng

Dựng ngày 05/09/2026 từ [`KHAO_SAT_AGENT_NHUNG.md`](KHAO_SAT_AGENT_NHUNG.md) và
sheet **Việc phải làm** của [`EAA_So_sanh_Agent_nhung.xlsx`](EAA_So_sanh_Agent_nhung.xlsx).

---

## 0. Luận điểm của cả kế hoạch

Chạy theo danh sách tính năng của đối thủ là cách chắc chắn **không** vượt được
họ: họ có nhiều kỹ sư hơn, nhiều bo hơn, nhiều hãng chip ký hợp tác hơn. Đuổi
theo bề rộng là đuổi trên đường của họ.

Bảng so sánh chỉ ra một chỗ khác. Sáu năng lực mạnh nhất của EAA — vòng đời tri
thức, đo độ nhạy bài kiểm, bắt mã tự chỉnh đồ đo, canh lời gọi bị đánh rơi, tất
định/tái lập được, sổ sai lệch — **không xuất hiện trong bất kỳ nguồn nào khảo
sát được**. Chúng cùng một trục: *hệ thống tự soi chính mình và ghi lại chỗ mình
sai*.

Nên kế hoạch này chọn hai luật:

> **Luật 1.** Chỉ lấp khoảng trống bề rộng nào **nuôi được** chiều sâu. Một
> tính năng chỉ để bằng người ta thì xếp sau.
>
> **Luật 2.** "Tốt hơn" phải **đo được**, không được là một lời khai. Mà muốn đo
> thì phải có thước — và thước ấy hiện chưa ai làm.

Từ luật 2 rút ra đóng góp nghiên cứu của đề án: **không đua trên thước của họ,
mà đề xuất thước mới.** IoT-SkillsBench đo *pass@k* — mã có chạy đúng không.
Không benchmark nào trong khảo sát hỏi những câu mà EAA đã trả lời được:

* bài kiểm sinh ra có **phân biệt được mã sai với mã đúng** không?
* bản vá có **sửa đồ đo thay vì sửa cái bị đo** không?
* lượt sinh lại có **đánh rơi việc** mà mọi cổng vẫn xanh không?
* mã sinh ra có **truy về được tài liệu** không?

Bốn câu ấy là bốn trục đo, và EAA là hệ duy nhất khảo sát được có sẵn bộ đo cho
cả bốn. Đó là chỗ để vượt lên.

---

## 1. Bốn giai đoạn, xếp theo *nuôi được chiều sâu bao nhiêu*

| GĐ | Tên | Lấp gì | Nuôi chiều sâu thế nào | Nặng |
|---|---|---|---|---|
| **1** | Bản đồ thanh ghi máy đọc được | A2 | Biến `// ref:` từ *có trích dẫn* thành *trích dẫn ĐÚNG*, và cho N-908/N-911 một nguồn sự thật | vừa |
| **2** | Thước đo mới | E1, E2 | Biến sáu điểm mạnh thành **số công bố được** | vừa |
| **3** | Kỹ năng phần cứng | B3, C8 | Chỗ duy nhất bài arXiv **đo được** là nâng kết quả lên gần trần | vừa |
| **4** | Bối cảnh bo từ sơ đồ | A3 | Bắt đúng hạng lỗi SL-125 — hồ sơ gõ tay lệch với mạch thật | nặng |

Ba nhóm còn lại (D5, E4, F1 / C5, C6 / A6, B5) xếp sau, lý do ở §6.

---

## 2. Giai đoạn 1 — Bản đồ thanh ghi máy đọc được

### 2.1 Vì sao đây là mục đầu tiên

Hôm nay mỗi giá trị thanh ghi trong mã mang một dòng `// ref: <mã chunk>`, và
cổng phân tích tĩnh cưỡng chế dòng ấy phải có (TC-17). Nhưng nó chỉ kiểm **có
trích dẫn hay không** — nó không kiểm **trích dẫn ấy có đúng không**. Một mã
chunk hợp lệ dán lên một giá trị sai vẫn qua cổng.

Bản đồ thanh ghi do chính hãng phát hành (CMSIS-SVD cho ARM, ATDF cho AVR) là
bảng **máy đọc được**: tên thanh ghi, tên trường bit, độ rộng, vị trí, giá trị
sau reset, quyền đọc/ghi. Có nó thì ba thứ đang có mạnh hẳn lên:

| Đang có | Sau khi có bản đồ thanh ghi |
|---|---|
| `// ref:` — kiểm *có trích dẫn* | Kiểm **thanh ghi có thật**, **trường bit có thật**, **giá trị lọt vừa độ rộng trường** |
| `eaa/dimension.py` (N-911) — chọi đơn vị với sổ số đo | Thêm nguồn thứ hai: độ rộng và thang của trường |
| `eaa/instrument.py` (N-908) — hằng số có `// ref:` bị đổi | Biết **giá trị mới có còn hợp lệ** không, chứ không chỉ biết nó đã đổi |

Đây là ý nghĩa của Luật 1: A2 không phải để bằng Embedder, nó là để ba bộ dò
của ta sắc hơn.

### 2.2 Kiến trúc — ba tầng vẫn nguyên

Chỗ dễ sai nhất: SVD là chuẩn của ARM, ATDF là của Microchip. Bỏ hai bộ đọc vào
`eaa/` có phá quy tắc số một không?

**Không, nếu chia đúng chỗ.** Ranh giới của kho này là *hằng số phần cứng*, chứ
không phải *định dạng tệp*. Chia như sau:

```
eaa/regmap.py        ENGINE — mô hình trung tính: RegisterMap, Register, BitField
                              + interface đọc. KHÔNG biết TWBR hay GPIOA là gì.
eaa/regmap_svd.py    ENGINE — bộ đọc định dạng CMSIS-SVD (XML)
eaa/regmap_atdf.py   ENGINE — bộ đọc định dạng ATDF (XML)
packs/avr/pack.yaml  PACK   — khai: regmap: {format: atdf, path: ...}
projects/<x>/regmap/ PROJECT— tệp thật của con chip dự án dùng
```

Engine biết *cách đọc một định dạng XML*; nó không biết trong đó có gì. Đúng
cùng cách `eaa/platform.py` biết *cách gọi một toolchain* mà không biết
`avr-gcc` là gì. TC-38 vẫn quét sạch.

### 2.3 Cổng mới: `regcheck`

Cổng thứ năm, đứng **sau** `static` và **trước** `unittests`:

* mã ghi vào một thanh ghi không có trong bản đồ → **ĐỎ**;
* ghi vào một trường bit không có → **ĐỎ**;
* giá trị vượt độ rộng trường (ví dụ ghi `0x1F` vào trường 3 bit) → **ĐỎ**;
* ghi vào thanh ghi chỉ-đọc → **ĐỎ**;
* `// ref:` trỏ tới một chunk **không** nói về thanh ghi đang cấu hình →
  **CẢNH BÁO** (trích dẫn dán nhầm chỗ).

Bốn mục đầu là **chặn**: chúng sai theo nghĩa máy chứng minh được, không phải
theo nghĩa văn xuôi. Mục cuối là **cảnh báo**, vì nó suy từ ánh xạ chunk↔thanh
ghi vốn do người khai.

### 2.4 Kịch bản kiểm thử — TC-136

| # | Kịch bản | Phải xảy ra |
|---|---|---|
| 1 | Đọc SVD mẫu → tên thanh ghi, trường, độ rộng, reset value đúng | khớp từng trường |
| 2 | Đọc ATDF mẫu → cùng mô hình `RegisterMap` | hai định dạng, một mô hình |
| 3 | Tệp XML hỏng | báo lỗi CẤU HÌNH, **không** mở vòng tự sửa (bài học SL-133) |
| 4 | Không khai `regmap` trong pack | cổng **bỏ qua**, mọi thứ chạy như trước |
| 5 | Ghi `TWBR = 72` khi bản đồ có TWBR | ĐẠT |
| 6 | Ghi vào thanh ghi không có trong bản đồ | ĐỎ, nêu tên thanh ghi |
| 7 | Ghi `0x1F` vào trường 3 bit | ĐỎ, nêu **độ rộng trường và giá trị lớn nhất** |
| 8 | Ghi vào thanh ghi chỉ-đọc | ĐỎ |
| 9 | Trích dẫn trỏ chunk không nói về thanh ghi ấy | CẢNH BÁO, không chặn |
| 10 | Mã trong tệp `.py` của bài kiểm | **không** áp luật (hàng rào SL-150) |
| 11 | Bản đồ có mà module không chạm thanh ghi nào | ĐẠT, im lặng |
| **Đột biến** | Bỏ phép kiểm độ rộng trường | ≥1 bài đỏ |
| **Đột biến** | Cho cổng chặn cả cảnh báo trích dẫn | ≥1 bài đỏ |
| **Đột biến** | Áp luật lên tệp `.py` | ≥1 bài đỏ |

### 2.5 Nối vào cái đang có — TC-137

| # | Kịch bản | Phải xảy ra |
|---|---|---|
| 1 | `instrument.py`: vá đổi hằng số `// ref:` sang giá trị **vẫn lọt** trường | vẫn dừng vòng vá (dấu vết cũ), nhưng thông báo nêu thêm "giá trị mới hợp lệ theo bản đồ" |
| 2 | `instrument.py`: vá đổi sang giá trị **vượt** trường | dừng, và nêu đây là hai lỗi chồng nhau |
| 3 | `dimension.py`: chú thích gán đơn vị cho một hằng số mà bản đồ nói là trường 3 bit không đơn vị | cảnh báo |
| 4 | Không có bản đồ | ba bộ dò chạy y như hôm nay, không bài nào đỏ |

Bài thứ tư quan trọng nhất: **thêm một nguồn sự thật không được làm hỏng đường
chạy khi nguồn ấy vắng mặt.**

---

## 3. Giai đoạn 2 — Thước đo mới

### 3.1 Hai nửa

**Nửa A — thước của họ.** Phải có, vì không có thì không đối thoại được với văn
liệu: `pass@1`, `pass@5`, và ba hạng kết quả *trượt dịch / sai hành vi / đúng*.
Dữ liệu đã nằm sẵn trong `kpi_log.csv` và `llm_calls.jsonl`; thiếu **cách tính**,
không thiếu số.

**Nửa B — thước của ta.** Bốn trục không benchmark nào trong khảo sát có:

| Trục | Đo bằng | Câu nó trả lời |
|---|---|---|
| **Độ nhạy bài kiểm** | `eaa/sensitivity.py` | Bao nhiêu % bài kiểm sinh ra **xanh cả với mã sai**? |
| **Vá chỉnh đồ đo** | `eaa/instrument.py` | Bao nhiêu % bản vá sửa cái đang đo thay vì cái bị đo? |
| **Mất việc im lặng** | `eaa/contract.py` | Bao nhiêu lượt sinh lại đánh rơi lời gọi mà mọi cổng vẫn xanh? |
| **Truy về được** | `regcheck` + `lifecycle` | Bao nhiêu % giá trị thanh ghi truy được về một trích đoạn **đúng**? |

Bốn trục này đo **chất lượng của quá trình**, không đo chất lượng một lượt sinh.
Đó là khác biệt đáng nói trong luận văn: một hệ đạt pass@1 cao mà 40% bài kiểm
của nó rỗng thì con số pass@1 ấy không có nghĩa như người đọc tưởng.

### 3.2 Kiến trúc

```
eaa/bench.py         ENGINE — chạy một bộ nhiệm vụ, gom kết quả, tính chỉ số
bench/<bo>/<task>/   DỰ ÁN  — mỗi nhiệm vụ: mô tả, tiêu chí, hồ sơ, tài liệu
eaa report bench     CLI    — bảng cho luận văn, xuất được ra .docx qua office.py
```

`bench.py` **không** tự chấm đúng/sai: nó chạy đúng vòng chuẩn 13 bước rồi đọc
kết quả các cổng — nên con số nó cho ra là con số của hệ thật, không phải của
một đường tắt dựng riêng để đo.

### 3.3 Kịch bản kiểm thử — TC-138

| # | Kịch bản | Phải xảy ra |
|---|---|---|
| 1 | Bộ 3 nhiệm vụ, 2 đúng 1 trượt dịch | pass@1 = 2/3, CF = 1 |
| 2 | Chạy lại cùng bộ với bộ phát lại | **con số y hệt** — tất định là điều kiện của thước |
| 3 | Một nhiệm vụ hết vòng vá | xếp vào hạng riêng, không lẫn vào "sai hành vi" |
| 4 | pass@5 với 5 lượt, 2 lượt đúng | pass@5 = 1, pass@1 = 0.4 |
| 5 | Bộ có nhiệm vụ mà bài kiểm sinh ra **rỗng** | trục *độ nhạy* đếm được nó |
| 6 | Bộ có lượt vá chỉnh đồ đo | trục *vá chỉnh đồ đo* đếm được |
| 7 | Báo cáo nêu rõ **số nhiệm vụ chạy trên bo thật** so với chạy trên host | không gộp hai loại bằng chứng vào một số |
| 8 | Bộ rỗng | báo "chưa có nhiệm vụ nào", không chia cho 0 |
| **Đột biến** | Gộp "hết vòng vá" vào "sai hành vi" | ≥1 bài đỏ |
| **Đột biến** | Cho `bench` chấm bằng đường riêng thay vì vòng chuẩn | ≥1 bài đỏ |

Bài số 7 là bài chống lại chính cám dỗ của đề án: một benchmark trộn kết quả
host với kết quả trên bo rồi báo một con số là một benchmark nói dối.

---

## 4. Giai đoạn 3 — Kỹ năng phần cứng

### 4.1 Điều bài arXiv đo được

Kỹ năng do **người soạn**: 41–42/42 nhiệm vụ. Kỹ năng do **LLM tự sinh**: lợi
ích thất thường, đôi khi làm tệ đi. Đây là bằng chứng độc lập cho luật trung tâm
của EAA — tri thức phải qua tay người trước khi thành nền cho sinh mã.

Nên kỹ năng ở EAA **đi đúng đường của tri thức**: soạn → đề xuất → **duyệt G2** →
mới vào prompt. Giống hệt trích đoạn tài liệu, và giống hệt số đo trên bo (N-913).

### 4.2 Kiến trúc

```
packs/<pack>/skills/<ngoại vi>.md   PACK — mẫu khởi tạo, THỨ TỰ bắt buộc,
                                            cách hỏng đã biết. Có frontmatter,
                                            có trạng thái duyệt.
eaa/composer.py lớp K9              ENGINE — chọn kỹ năng theo `uses` của module
```

Kỹ năng nằm ở **pack**, không ở engine — vì nó là tri thức của một họ chip. Engine
chỉ biết chọn theo `uses`, đúng cách nó đã chọn chunk theo đồ thị.

Ngân sách: lớp K9 lấy từ `repair` như lớp K8 đã lấy (SL-173) — `repair` là **sàn**
chứ không phải trần (SL-147), nên con số danh nghĩa của nó là sổ sách.

### 4.3 Kỹ năng khác chunk tài liệu ở chỗ nào

Đây là câu phải trả lời rõ, nếu không kỹ năng chỉ là chunk đổi tên:

| | Trích đoạn tài liệu | Kỹ năng |
|---|---|---|
| Nội dung | Bảng thanh ghi–bit, **sự thật tĩnh** | Mẫu khởi tạo, **thứ tự**, cách hỏng |
| Trả lời câu | "Bit này nghĩa là gì" | "Làm sao cho nó chạy, và nó hay hỏng kiểu gì" |
| Nguồn | Datasheet | Kinh nghiệm — của người, hoặc rút từ sổ sai lệch |
| Sai thì | Mã sai giá trị | Mã đúng giá trị mà **sai thứ tự** |

Cột cuối đúng là hạng lỗi đã làm robot ngã: *"phép dò `self_balance_setpoint`
chạy TRƯỚC vùng chết"* — mã đúng mọi dòng, sai ở thứ tự, và không bài kiểm nào
bắt được.

### 4.4 Kịch bản kiểm thử — TC-139

| # | Kịch bản | Phải xảy ra |
|---|---|---|
| 1 | Module `uses: twi` → kỹ năng `twi.md` vào prompt | có trong lớp K9 |
| 2 | Kỹ năng trạng thái `proposed` | **không** vào prompt |
| 3 | Không kỹ năng nào khớp `uses` | lớp K9 rỗng, không câu thừa |
| 4 | Hai kỹ năng khớp, ngân sách chỉ đủ một | giữ cái khớp **đích danh** hơn, và **nói ra đã cắt** |
| 5 | Kỹ năng nằm trong pack thứ hai | dùng được, engine không sửa dòng nào |
| 6 | Kỹ năng có mục "cách hỏng đã biết" | đoạn ấy **phải** vào prompt, kể cả khi cắt |
| 7 | Kỹ năng LLM tự sinh chưa duyệt | không vào prompt, và `eaa skill list` nêu nó đang chờ |
| **Đột biến** | Cho kỹ năng `proposed` vào prompt | ≥1 bài đỏ |
| **Đột biến** | Cắt mất mục "cách hỏng đã biết" khi thiếu chỗ | ≥1 bài đỏ |
| **Đột biến** | Hard-code tên ngoại vi trong engine | TC-38 đỏ |

Bài số 6 là chỗ kỹ năng khác chunk: khi phải cắt, thứ giữ lại là **cách hỏng**,
không phải mẫu mã — vì mẫu mã thì mô hình đoán được, còn cách hỏng thì không.

---

## 5. Giai đoạn 4 — Bối cảnh bo từ sơ đồ nguyên lý

### 5.1 Lỗi nó chặn

SL-125: *"Hồ sơ phần cứng mô tả một THIẾT KẾ, không phải cái bo trên bàn."* Giá
phải trả là robot lao thẳng một phía. `hardware_profile.yaml` gõ tay là chỗ ấy.

Netlist của KiCad là **định dạng mở**, đọc được, và nó nói đúng thứ hồ sơ đang
gõ tay: linh kiện gì nối vào chân nào.

### 5.2 Điều quan trọng: KHÔNG thay hồ sơ, mà ĐỐI CHIẾU với nó

Cám dỗ là sinh `hardware_profile.yaml` từ netlist. **Đừng.** Hồ sơ mang cả thứ
netlist không có: mức tích cực, có pull-up nội hay không, ghi chú vì sao chọn bộ
đếm này. Sinh đè lên là mất phần đắt nhất.

Việc đúng là **đối chiếu**, và báo khi hai bên nói hai chuyện:

* hồ sơ nói `buzzer` ở `PB2`, netlist nói `PB4` → **ĐỎ ở G1**, không phải cảnh báo;
* netlist có linh kiện hồ sơ không nhắc → cảnh báo (đúng ca SL-143: còi và nút
  có trên bo từ đầu mà hồ sơ chưa bao giờ khai);
* hồ sơ nhắc chân netlist không có → ĐỎ.

### 5.3 Kịch bản kiểm thử — TC-140

| # | Kịch bản | Phải xảy ra |
|---|---|---|
| 1 | Netlist khớp hồ sơ | im lặng |
| 2 | Lệch một chân | ĐỎ, nêu **cả hai** giá trị và **cả hai** nguồn |
| 3 | Netlist có linh kiện hồ sơ thiếu | cảnh báo, nêu tên và chân |
| 4 | Hồ sơ có chân netlist không có | ĐỎ |
| 5 | Không có netlist | im lặng, mọi thứ chạy như trước |
| 6 | Netlist hỏng | lỗi CẤU HÌNH, không mở vòng tự sửa |
| 7 | Đối chiếu **không** ghi đè hồ sơ | tệp hồ sơ không đổi một byte |
| **Đột biến** | Cho phép sinh đè hồ sơ | bài 7 đỏ |
| **Đột biến** | Hạ "lệch chân" xuống cảnh báo | bài 2 đỏ |

Bài số 7 canh đúng cám dỗ ở §5.2.

---

## 6. Vì sao ba nhóm còn lại xếp sau

| Nhóm | Lý do xếp sau |
|---|---|
| **D5** trọng tài phần cứng · **E4** truy vết hai chiều · **F1** tích hợp IDE | Đều rẻ và đều đáng làm, nhưng **không nuôi chiều sâu** — làm xong ta bằng người ta, không hơn. Xếp vào khe trống giữa hai giai đoạn lớn. D5 nên làm sớm nhất trong ba, vì nó thành lỗi thật ngay khi có người thứ hai chạy cùng bo |
| **C5** máy đo · **C6** debugger tự động | Tốn **thiết bị**, không chỉ tốn mã. Và chúng chỉ có nghĩa khi đã có benchmark để chứng minh chúng cải thiện được gì — tức là sau giai đoạn 2 |
| **A6** MCP tài liệu hãng · **B5** thêm nền tảng | Công việc **tuyến tính**, TC-47 đã chứng minh thêm pack không phải sửa engine. Làm bất cứ lúc nào cần một con số bề rộng cho luận văn |

---

## 7. Bốn luật giữ cho kế hoạch không trượt

Rút từ chính sổ sai lệch — mỗi luật là một lỗi đã trả giá:

1. **Mọi nguồn sự thật mới đều phải chịu phép kiểm "vắng mặt thì sao".** Bản đồ
   thanh ghi, netlist, kỹ năng — thiếu cái nào thì đường chạy vẫn nguyên. Đây là
   bài học SL-172: một module không có người gọi thì nó không tồn tại; và mặt
   trái của nó là một module có người gọi thì nó không được làm hỏng người gọi.

2. **Cái gì vào prompt cũng phải qua một cửa duyệt.** Trích đoạn qua G2, số đo
   qua `measured approve`, kỹ năng qua G2. Không có ngoại lệ nào cho "cái này
   máy đọc được nên chắc đúng" — SVD cũng do người chọn tệp nào là của chip nào.

3. **Thêm một cổng thì phải trả lời được: nó chặn cái gì mà cổng cũ không
   chặn.** `regcheck` trả lời được. Một cổng không trả lời được câu ấy là một
   cổng làm chậm mọi lượt sinh để đổi lấy cảm giác an toàn.

4. **Mỗi tính năng mới kèm một trục đo, hoặc nó không vào benchmark.** Nếu không
   đo được nó cải thiện gì thì §0 Luật 2 đã bác nó từ đầu.

---

## 8. Thứ tự đề nghị, và điều kiện dừng

```
GĐ1  bản đồ thanh ghi  →  cổng regcheck  →  nối vào N-908/N-911     (TC-136, TC-137)
GĐ2  bench.py + 4 trục đo mới  →  eaa report bench                  (TC-138)
       ↑ điều kiện dừng: chạy lại cho ra CON SỐ Y HỆT
GĐ3  kỹ năng phần cứng trong pack  →  lớp K9                        (TC-139)
       ↑ đo bằng GĐ2: kỹ năng có nâng được số không?
GĐ4  netlist  →  đối chiếu hồ sơ ở G1                               (TC-140)
xen kẽ  D5 (khoá cổng nối tiếp) → E4 (truy vết) → F1 (lớp mỏng IDE)
```

Điều kiện dừng của cả kế hoạch, và nó là một con số chứ không phải một cảm giác:
**bốn trục đo mới ở §3.1 phải có số liệu trên ít nhất hai Platform Pack.** Đến
đó thì câu *"Agent này tốt hơn"* không còn là lời khai — nó là một bảng.

---

## Đọc cùng bản này

* [`KHAO_SAT_AGENT_NHUNG.md`](KHAO_SAT_AGENT_NHUNG.md) — khảo sát và nguồn
* [`EAA_So_sanh_Agent_nhung.xlsx`](EAA_So_sanh_Agent_nhung.xlsx) — 42 tính năng
* [`SAI_LECH_THIET_KE.md`](SAI_LECH_THIET_KE.md) — 175 mục, nguồn của bốn luật §7
