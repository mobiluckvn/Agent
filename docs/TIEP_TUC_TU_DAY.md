# Tiếp tục từ đây — phiên kiểm Agent với bo thật

Dừng lúc: **2026-08-31**, sau khi xác định lỗi USB cần khởi động lại máy.
Nhánh `main`, commit cuối `e24fe70`. **2077 test xanh.** Mọi thứ đã đẩy.

---

## 1. Việc đầu tiên sau khi khởi động lại máy

```bash
cd /Users/v/Documents/KTDT
.venv/bin/python -m eaa.cli --project .eaa/scratch/stm32f411_disco ports
```

Nhìn mục **Thiết bị USB**:

| Thấy gì | Nghĩa là | Đi tiếp thế nào |
|---|---|---|
| Có thiết bị ngoài (mã KHÔNG phải `05ac`) | Cổng USB đã sống lại | Sang mục 3 |
| Vẫn chỉ `05ac` (Apple) | Khởi động lại chưa gỡ được | Sang mục 2 |

Muốn vừa cắm vừa xem thì: `ports --watch` — nó báo ngay lúc cắm vào và rút ra.

---

## 2. Nếu khởi động lại vẫn không thấy

Đã loại trừ được (đừng mất công kiểm lại):

* **Không phải trình điều khiển.** `ioreg` liệt kê ở tầng bus, trước cả driver.
  Thiếu driver thì thiết bị vẫn hiện, chỉ là không sinh `/dev/cu.*`.
* **Không phải công cụ đo.** Hai mặt phẳng `ioreg` độc lập cho cùng kết quả,
  cộng một máy canh chạy nền theo thời gian thực suốt buổi.
* **Không phải cái bo.** Đã thử **hai bo khác nhau** (AVR và STM32), hai chip
  USB khác nhau, hai sợi dây. Không lần nào có gì xuất hiện.

Bằng chứng mạnh nhất thu được:

```
XHC1@14   (bộ điều khiển các cổng USB-C ngoài)   →   0 thiết bị
Apple T2 Controller                              →   8 thiết bị (đồ bên trong máy)
```

Cổng ngoài trống rỗng ở tầng phần cứng. Và **cáp chuyển/hub cũng không hiện
ra** — mà một hub đang hoạt động luôn tự khai báo là một thiết bị USB kể cả
khi chưa cắm gì vào nó. Nên mắt xích đứt nằm **trước** cái bo.

**Phép thử tách bạch, 30 giây:** cắm một thứ chắc chắn còn tốt (USB thường,
chuột, điện thoại) vào **đúng cổng ấy, đúng cáp chuyển ấy**.

* Hiện ra → cổng và cáp chuyển tốt, vấn đề ở dây nối bo hoặc ở bo.
* Cũng không hiện → cổng hoặc cáp chuyển hỏng; đổi sang cổng USB-C khác.

---

## 3. Trạng thái dự án F411

Chỗ làm nháp: `.eaa/scratch/stm32f411_disco/`

> **Lưu ý:** `.eaa/` nằm trong `.gitignore`, nên thư mục này **không có trong
> Git**. Khởi động lại không mất (nó trên đĩa), nhưng đừng trông vào `git
> checkout` để khôi phục nó.

Đã có:

* `constraints.yaml` — Platform Pack `stm32` (suy từ tên, đã ghi rõ lý do ở
  đầu tệp). **Số ràng buộc còn là GIẢ ĐỊNH:** flash 32 KB, RAM 2 KB, 16 MHz —
  đó là số của một họ chip khác, sẽ sửa sau khi đọc UM1842.
* `hardware_profile.yaml` — mới có khung, chưa mô tả bo.
* `datasheets/` — **UM1842 đã nạp** (1,7 MB, tải thẳng từ `st.com`, hạng
  *chính chủ*), thành chunk `ds-stm3-boar-01`, 36 trang.

### Đang chờ người — hai việc

**a. Duyệt G2** cho chunk vừa nạp. Đây là chỗ kỹ sư đối chiếu nội dung với
bản gốc trước khi cho nó vào kho tri thức:

```bash
eaa --project .eaa/scratch/stm32f411_disco gate show G2
eaa --project .eaa/scratch/stm32f411_disco gate approve G2
```

Lần trước lệnh duyệt **không tới được dự án này** — `project_state.json` không
đổi từ lúc tạo. Chỗ nháp nằm trong `.eaa/scratch/` nên **lệnh trần không bao
giờ tìm ra nó**; bắt buộc phải có `--project`.

**b. Cắm được bo** (mục 1–2).

Chưa cần ngay: toolchain ARM (`arm-none-eabi-gcc`, `st-flash`, `cppcheck`) —
chỉ chặn lúc biên dịch, chưa chặn việc khám phá cấu hình.

---

## 4. Cách làm việc đang dùng

Người dùng ra yêu cầu → tôi chuyển cho Agent bằng tiếng Việt tự nhiên → Agent
làm; khi nó **cần người** (duyệt gate, cắm mạch, đo số, cài công cụ) tôi báo
lại → người dùng làm → tôi báo cho Agent.

Mục tiêu là **tìm lỗi của Agent rồi sửa**. Người dùng có cài bẫy: đã từng cố ý
cắm bo sai họ để xem Agent có bắt được không.

---

## 5. Đã tìm và sửa được gì trong phiên này

**18 commit.** Test đi từ 1.949 → **2.077**.

### Bốn việc theo yêu cầu

| Việc | Kết quả |
|---|---|
| Cách ly dữ liệu giữa dự án | Kho dùng chung lọc theo dự án + họ MCU (TC-79) |
| Thêm Gemini 3.5 Flash | Danh mục model; **người chọn**, hệ không tự chọn (TC-80) |
| Test unhappy case | 15 ca; tìm ra **3 lỗi thật** (TC-81) |
| Sinh tài liệu thiết kế | URD/SRS/SDD theo C4 + chức năng + luồng, 4 định dạng (TC-82) |

### Mười lăm lỗi thật tìm được khi chạy với dữ liệu và phần cứng thật

Gần như tất cả đều thuộc **một loại**: *mã lệch với lời chính nó khai.*

1. `EAA_NO_NET=1` không chặn lối ra mạng qua mô hình — công tắc **trông như**
   đã tắt.
2. Băm ràng buộc không bao giờ được đối chiếu với tệp; băm ấy đi vào commit
   message làm bằng chứng xuất xứ (NFR-07).
3. Biến môi trường đặt rỗng bị `.env` điền đè, dù docstring khai ngược lại.
4. PDF sinh ra **đè** bản `.docx` người dùng đã có.
5. Hai lượt chuyển PDF song song đụng nhau — đo được 2/3 thành công.
6. `eaa/docspec/*.yaml` không nằm trong gói cài đặt.
7. Agent trả lời "cần người làm gì" **thiếu** chuyện thiếu toolchain.
8. `eaa focus` — lệnh hứa "cả quãng đường, một lần" — cũng thiếu đúng chặng ấy.
9. `eaa scratch` sinh `mcu` sai kiểu → chỗ nháp **sinh ra đã hỏng**.
10. Sập bằng traceback Python trần, lọt qua mọi lớp bắt lỗi.
11. `eaa scratch` mặc định sai Platform Pack cho bo họ khác — **im lặng**.
12. `datasheet add` chỉ nhận tệp cục bộ → đường nạp tri thức **đi vòng qua**
    lớp phân hạng nguồn.
13. Nhãn "chỗ nháp" chỉ hiện **một lần** lúc dựng.
14. `eaa ports` trả lời sai **loại** câu hỏi cho bo dùng mạch nạp trên bo.
15. `_bon_so()` gộp hex và thập phân — lỗi **tôi tự gây khi sửa**, và nó làm
    một bo đúng bị chấm là lạ.

Chi tiết đầy đủ: `docs/SAI_LECH_THIET_KE.md` mục **SL-102 … SL-108**.

### Nợ kỹ thuật đã ghi, chưa xử — thuộc quyền người dùng

`projects/robot_balance` đang **trôi băm ràng buộc** từ sprint S2:
`constraints.yaml` sửa ở `f6b9d49`, `project_state.json` chưa động từ
`ea63c88`. `eaa status` sẽ cảnh báo cho tới khi được chốt lại.

**Không tự ghim lại**: chốt bộ ràng buộc là quyết định của người tại G1, và
một lệnh tự ghim băm chính là lối tắt mà thiết kế cấm.

---

## 6. Chạy lại bộ kiểm

```bash
.venv/bin/python -m pytest -q                 # đủ, ~4 phút
.venv/bin/python -m pytest -q -m "not cham"   # bỏ 4 bài gọi LibreOffice, ~3 phút
.venv/bin/python scripts/chay_ca_xau.py       # 15 ca xấu
.venv/bin/python scripts/kiem_on_dinh.py      # kiểm độ ổn định
```
