# Cốt lõi của từng sản phẩm, và cốt lõi của chúng ta

Đọc sâu ngày 05/09/2026. Bổ sung cho [`KHAO_SAT_AGENT_NHUNG.md`](KHAO_SAT_AGENT_NHUNG.md)
và bảng 42 tính năng.

---

## 1. Vì sao bảng 42 tính năng chưa đủ

Một ma trận tính năng nói **sản phẩm CÓ GÌ**. Nó không nói **sản phẩm LÀ GÌ**.

Hệ quả thấy rõ: trong bảng ấy, EAA "đủ 24 / một phần 11 / chưa 4". Ba con số ấy
không dùng được để trả lời câu của hội đồng — *"vậy đóng góp của đề án là gì"* —
vì chúng mô tả một danh sách, không mô tả một lập trường.

Nên bản này hỏi mỗi sản phẩm **bốn câu**, và chỉ bốn:

1. Nó cho rằng **việc khó nhất** trong lập trình nhúng bằng AI là gì?
2. Nó **xây cái gì TRƯỚC** — thứ mọi thứ khác quay quanh?
3. Nó mạnh **vì** lựa chọn ấy, chứ không phải mạnh tình cờ?
4. Lựa chọn ấy buộc nó **từ bỏ** cái gì?

Câu thứ tư quan trọng nhất. Một sản phẩm không từ bỏ gì là một sản phẩm chưa
chọn gì, và nó sẽ thua mọi sản phẩm đã chọn.

---

## 2. Embedder — cược vào VÒNG KÍN TRÊN SILICON

**Việc khó nhất, theo họ:** không phải viết mã, mà **chứng minh mã khớp với con
chip và cái bo BẠN làm ra** — không phải bo mẫu của hãng. Họ gọi thẳng phần
thiếu của trợ lý đa dụng:

> *"General-purpose assistants can help write code. Embedder adds the
> firmware-specific evidence, toolchain, and hardware loop needed to test
> whether that code matches the actual part and board."*

**Xây trước:** đường vào phần cứng sống. Đầu dò gỡ lỗi, máy đo, nạp và chạy
thật — **quan sát phần cứng là kênh phản hồi CHÍNH, không phải bước cuối**. Rồi
mới tới chỉ mục tài liệu, netlist, sinh mã.

**Mạnh vì lựa chọn ấy:** khi phản hồi đến từ silicon, mọi thứ khác được chấm
bằng một thước không cãi được. Bề rộng của họ (500+ MCU, 3.000+ ngoại vi theo
YC; 500+ nền tảng / 5.500+ ngoại vi theo trang chủ) có nghĩa **vì** nó nhân với
vòng kín ấy — không có vòng kín thì bề rộng chỉ là danh sách.

**Từ bỏ:** vòng kín đòi **thiết bị và quyền chạm vào nó**. Sản phẩm của họ
không dùng được nếu không có bo, đầu dò, máy đo, và một chỗ ngồi cạnh chúng. Và
tính tự chủ mà họ khai — *"builds, flashes, tests and diagnoses autonomously"* —
đổi lấy chỗ đứng của người: người vẫn duyệt, nhưng **duyệt cái nào là cấu hình
được**, tức là tắt được.

---

## 3. Bài arXiv "Skilled AI Agents" — cược vào TRI THỨC ĐƯỢC NGƯỜI NÉN LẠI

**Việc khó nhất, theo họ:** hai điều. Hệ nhúng phân mảnh theo hãng và framework;
và **dịch được không có nghĩa là chạy đúng** — *"code that builds without errors
may still exhibit unexpected behavior due to timing violations, peripheral
misconfigurations, or hardware-specific edge cases."*

**Xây trước:** **kỹ năng** — mỗi ngoại vi một tài liệu ngắn gồm mẫu lập trình,
ràng buộc khởi tạo, và **cách hỏng đã biết**. Không nhồi SDK vào ngữ cảnh.

**Mạnh vì lựa chọn ấy — và họ ĐO được:**

| Nền tảng | Không kỹ năng | Kỹ năng do LLM sinh | Kỹ năng do NGƯỜI soạn |
|---|---|---|---|
| Arduino | 42/42 | 39/42 | 41/42 |
| ESP-IDF | 26/42 | 26/42 | **40/42** |
| Zephyr | 24/42 | **19/42** | **39/42** |
| Token vào trung bình | ~300 | 8.500–9.500 | 650–2.900 |

Ba điều đọc ra từ bảng này, và cả ba đều đáng cho luận văn:

* **Chỗ mô hình đã biết thì kỹ năng không giúp gì** (Arduino 42/42 ngay từ đầu).
  Tri thức chỉ có giá ở chỗ mô hình *không* biết.
* **Kỹ năng do LLM tự sinh làm TỆ ĐI** trên nền tảng khó — Zephyr tụt 24 → 19 —
  và tốn gấp 15–30 lần token. Bài báo giải thích: nó *"reinforcing incorrect
  platform-specific assumptions"*.
* **Kỹ năng do người soạn nâng gần trần** và rẻ hơn nhiều lần.

Đây là **bằng chứng độc lập** cho luật trung tâm của EAA: tri thức phải qua tay
người trước khi thành nền cho sinh mã. Một hệ để mô hình tự viết tri thức cho
chính nó không phải là tự động hoá — nó là khuếch đại cái sai của chính mô hình.

**Từ bỏ:** người phải ngồi soạn. Bài báo khai **~100 giờ người** cho 378 lượt
đánh giá. Và họ dừng ở sinh mã: không quản lý vòng đời tri thức, không cổng, không
truy vết.

---

## 4. Trợ lý của nhà sản xuất (STM32 Sidekick, MCP tài liệu của Espressif) — cược vào THẨM QUYỀN

**Việc khó nhất, theo họ:** tìm đúng trang trong hai nghìn trang tài liệu.

**Xây trước:** một bộ tra cứu **chỉ ăn tài liệu chính thức của hãng**.

**Mạnh vì lựa chọn ấy:** không hãng nào có thể cạnh tranh với ST về tài liệu ST.
Thẩm quyền và độ tươi là thứ mua không được.

**Từ bỏ:** **toàn bộ phần kiểm chứng** — và họ nói thẳng ra. Trang của ST dặn
người dùng *"always verify critical information using the cited source
documentation"* và *"cross-check critical design decisions against official
documentation"*. Tức là: nó trả lời, bạn chịu trách nhiệm. Nó cũng có hạn mức
số câu hỏi mỗi ngày — đây là công cụ tra cứu, không phải chỗ đặt một quy trình.

---

## 5. Trợ lý lập trình đa dụng — cược vào VÒNG SỬA TỆP

**Việc khó nhất, theo họ:** không có gì riêng cho nhúng. Mã là văn bản; sửa văn
bản nhanh hơn thì lập trình nhanh hơn.

**Xây trước:** vòng lặp đọc–sửa–chạy trong chính chỗ kỹ sư ngồi.

**Mạnh vì lựa chọn ấy:** phổ cập, rẻ, và đúng cho 90% mã trên đời.

**Từ bỏ:** mọi thứ sau ranh giới tệp nguồn. Câu gọn nhất tìm được trong khảo sát:

> agent sửa được tệp và chạy được build, nhưng **không nạp được bo, không xem nó
> khởi động, và không đọc ngược được cái vừa xảy ra**.

Quy trình nhúng với chúng, theo chính tài liệu hướng dẫn, là: *bạn mô tả → nó
sinh → **bạn đối chiếu datasheet** → **bạn thử trên phần cứng***. Hai bước cuối
là hai bước đắt nhất, và chúng vẫn nguyên vẹn trên vai người.

---

## 6. Hãng công cụ chứng nhận (Parasoft, LDRA, QA Systems) — cược vào BẰNG CHỨNG

Đây là nhóm tôi bỏ sót ở khảo sát đầu, và nó **gần EAA nhất về triết lý**.

**Việc khó nhất, theo họ:** chứng minh — trước một cơ quan chứng nhận — rằng mã
này đã được kiểm đủ. Với mã do AI sinh, chuẩn không nhân nhượng: *mọi dòng, kể
cả dòng AI viết, chịu đúng bộ luật như dòng người viết.*

**Xây trước:** bộ sinh **bằng chứng chứng nhận** — truy vết hai chiều yêu cầu ↔
mã ↔ kiểm chứng, và bản thân công cụ phải **tất định** mới được *qualify* theo
ISO 26262.

**Mạnh vì lựa chọn ấy:** thứ họ xuất ra đi thẳng vào hồ sơ chứng nhận. Không ai
trong bốn nhóm trên làm được điều đó.

**Điều đáng chú ý nhất:** năm 2026 họ **đi ngược về phía agent**. Parasoft ra
`embedded world 2026` với GoogleTest được TÜV chứng nhận, *agentic AI workflows
for regulated C and C++*, và một **máy chủ MCP nối agent tới dữ liệu chuẩn hoá
của họ**.

**Từ bỏ:** họ không sinh mã, và không chạm phần cứng. Agent của họ là **khách**
đến ăn dữ liệu; quy trình vẫn là quy trình của con người dùng công cụ kiểm.

---

## 7. Bản đồ: năm bên đứng ở năm chỗ khác nhau

Xếp theo **thứ mỗi bên coi là tài sản của mình**:

```
tài liệu        tri thức nén     vòng sửa tệp     silicon        bằng chứng
của hãng        do người soạn                     sống           chứng nhận
   │                 │                │              │                │
Sidekick        arXiv skills      Copilot        Embedder      Parasoft/LDRA
MCP Espressif                     Cursor                        QA Systems
   │                 │                │              │                │
 THẨM QUYỀN      TRI THỨC        PHỔ CẬP        PHẢN HỒI         TRUY VẾT
                                                THẬT
```

Không ai trong năm bên ấy sở hữu thứ nằm giữa: **thủ tục quyết định** — *ai được
tin cái gì, dựa trên bằng chứng nào, và ở đâu thì bắt buộc phải có người*.

* Embedder có phản hồi thật nhưng **cấu hình được chỗ nào cần duyệt**.
* Parasoft có truy vết nhưng **không sinh mã**, nên không có gì để chặn.
* Trợ lý hãng **tự khai là không chịu trách nhiệm**.
* Trợ lý đa dụng không có khái niệm bằng chứng.
* Bài arXiv chứng minh tri thức phải qua người, rồi **dừng ở đó**.

---

## 8. Cốt lõi của EAA

Trả lời đúng bốn câu ở §1:

**1. Việc khó nhất là gì.** Không phải sinh firmware. Là **biết được có nên tin
firmware ấy không** — và biết bằng cái gì. Ba lỗi đắt nhất của chính đề án đều
đi qua sạch mọi cổng tự động: mã tự chỉnh cho vừa đồ đo của nó, `app_init()`
mất bốn lời gọi khởi tạo với 33 bài kiểm vẫn xanh, và một bài kiểm xanh đúng lúc
vì lý do sai.

**2. Xây trước cái gì.** Năm Human Gate mà **không lệnh nào vượt được**, và một
đường merge duy nhất đòi giấy phép neo vào băm nội dung. Mọi thứ khác — kho tri
thức append-only, bốn mức tin cậy, sổ sai lệch, bộ phát lại tất định — mọc ra từ
đó.

**3. Mạnh vì lựa chọn ấy.** Tám năng lực mà khảo sát không thấy ở đâu khác —
vòng đời tri thức, đo độ nhạy bài kiểm, bắt mã chỉnh đồ đo, canh lời gọi bị đánh
rơi, kiểm giá trị theo bản đồ thanh ghi, tất định/tái lập được, sổ 177 mục sai
lệch, và bốn trục đo chất lượng quá trình — **không phải tám ý tưởng rời**.
Chúng là **một** ý tưởng: *hệ thống phải biết, và phải nói ra, nó đáng tin tới
đâu ở từng chỗ.* Bốn mức `ĐÃ KIỂM / SUY RA / GIẢ ĐỊNH / KHÔNG KIỂM ĐƯỢC` gắn vào
mọi đầu ra là câu ấy viết thành mã.

**4. Từ bỏ cái gì.** Ba thứ, và cả ba là **giá phải trả có chủ ý**:

* **Tốc độ.** Người phải bấm ở năm chỗ. Không có cờ nào tắt được.
* **Bề rộng.** Hai Platform Pack, không phải năm trăm. Tri thức đi qua G2 thì
  không nhân bản nhanh được.
* **Tính tự chủ hoàn toàn.** Nạp firmware luôn cần một chữ ký. Đây là chỗ EAA
  tách khỏi Embedder rõ nhất, và nó là một lập trường chứ không phải một mục
  chưa làm.

---

## 9. Ba câu để mô tả điểm mạnh — dùng được khi bảo vệ

**Câu ngắn nhất.**
> Các sản phẩm khác làm cho Agent **viết được firmware**. Đề án này làm cho
> firmware ấy **chứng minh được** — và làm bằng cấu trúc, không bằng lời dặn.

**Câu cho hội đồng kỹ thuật.**
> Đóng góp không nằm ở việc sinh mã — chỗ ấy thị trường đã đi trước. Nó nằm ở
> **thủ tục quyết định**: năm điểm dừng không vượt được bằng bất kỳ lệnh nào,
> tri thức chỉ vào prompt sau khi một người đối chiếu với bản gốc, mọi đầu ra
> mang một trong bốn mức tin cậy, và mọi lượt chạy tái lập được từ nhật ký mà
> bộ phát lại **cố ý không bịa** khi trượt băm. Đó cũng đúng là điều kiện mà
> ISO 26262 đòi để một công cụ được *qualify*.

**Câu nói được điều người khác không nói được.**
> Chúng tôi đo được những thứ chưa benchmark nào hỏi: bao nhiêu phần trăm bài
> kiểm do Agent sinh ra là **rỗng** — xanh cả với mã sai; bao nhiêu bản vá **sửa
> đồ đo thay vì sửa cái bị đo**; bao nhiêu lượt sinh lại **đánh rơi việc** mà mọi
> cổng vẫn xanh. Một hệ đạt `pass@1` cao mà 40% bài kiểm của nó rỗng thì con số
> `pass@1` ấy không có nghĩa như người đọc tưởng.

---

## 10. Chỗ ba câu ấy CHƯA đứng vững

Phải nói ra, nếu không thì chính bản này thành thứ nó phê phán.

| Câu | Chỗ yếu | Cần gì để vững |
|---|---|---|
| *"chứng minh được"* | Chứng minh trên **một** dự án, **một** con chip | Bộ nhiệm vụ trên ≥ 2 Platform Pack (E1) |
| *"đo được thứ chưa ai hỏi"* | Cái **thước** đã có; **số** thì chưa | Chạy bốn trục trên dữ liệu thật |
| *"điều kiện ISO 26262"* | Ta thoả **một** điều kiện (tất định), không phải đã *qualify* | Nói rõ là *"thoả một điều kiện"*, đừng nói *"đạt chuẩn"* |
| *"không lệnh nào vượt được"* | Đúng, và có test canh | — đây là câu **vững nhất** trong ba câu |

Việc rẻ nhất để lấp hai dòng đầu: **đo ngược lịch sử của chính dự án** — 37
commit, 12 lượt chuyển giữa hai bản module, và 177 mục sổ sai lệch đã nằm sẵn
trong Git. Không tốn một token API nào.

---

## Nguồn đọc thêm cho bản này

- [Embedder](https://embedder.com/) · [Embedder trên Y Combinator](https://www.ycombinator.com/companies/embedder)
- [Skilled AI Agents for Embedded and IoT Systems Development — arXiv 2603.19583](https://arxiv.org/html/2603.19583v1)
- [STM32 Sidekick — STMicroelectronics](https://www.st.com/content/st_com/en/about/ai-at-st/stm32-sidekick.html)
- [GitHub Copilot in Espressif-IDE](https://developer.espressif.com/blog/2025/02/github-copilot-in-espressif-ide/)
- [Parasoft — C/C++ test automation với GoogleTest chứng nhận TÜV và agentic AI, embedded world 2026](https://www.parasoft.com/news/c-cpp-test-automation-certified-googletest-agentic-ai/)
- [Claude Skills cho kỹ sư nhúng — Snyk](https://snyk.io/articles/claude-skills-embedded-systems-engineers/)
- [AI-Assisted Hardware-in-the-Loop for Embedded Linux](https://electronicsconsult.com/blog/ai-assisted-hardware-in-the-loop/)
