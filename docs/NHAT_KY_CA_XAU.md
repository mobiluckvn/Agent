# Nhật ký kiểm ca xấu (unhappy case)

Ngày chạy: **2026-08-31** · Sản phẩm: EAA · Nhánh `main`
Chạy lại: `python scripts/chay_ca_xau.py`

---

## Vì sao có bài kiểm này, khi đã có 1.966 bài test

Bộ test sẵn có canh những đường xấu mà **thiết kế đã lường trước**. Nó không
canh được loại lỗi nguy hiểm nhất: chỗ **mã lệch với lời chính nó khai**. Một
bài test viết ra từ cùng một hiểu nhầm với mã sẽ xanh, và cứ xanh mãi.

Bộ ca xấu chạy sản phẩm **như một người dùng đang gõ sai**, và chấm theo ba
tiêu chí của người dùng chứ không của lập trình viên:

1. Có sập không — traceback lọt ra ngoài là hỏng.
2. Mã thoát có đúng nghĩa không — **2 là "đang chờ người", không phải lỗi**.
3. Thông điệp có nói **phải làm gì tiếp** không, hay chỉ nói *sai rồi*.

Tiêu chí 3 là tiêu chí khó nhất và cũng là tiêu chí duy nhất người dùng thật
sự quan tâm. Với một người đang kẹt, một lỗi đúng mà không chỉ được đường ra
thì không khác gì một lỗi sai.

---

## Kết quả

| Vòng | Đạt | Ghi chú |
|---|---|---|
| Vòng 1 | **10/15** | 5 ca hỏng: 3 do kịch bản test của tôi sai, **2 là lỗi thật của sản phẩm** |
| Vòng 2 | **14/15** | sau khi sửa kịch bản và 2 lỗi thật; ca còn lại lộ ra **lỗi thứ ba** |
| Vòng 3 | **15/15** | sau khi sửa lỗi thứ ba |

**Ba lỗi thật tìm được.** Cả ba đều là chỗ mã lệch với chính lời nó khai —
đúng loại mà một bài test viết cùng lúc với mã sẽ không bắt được.

---

## Bộ 15 ca

| Mã | Ca | Vì sao đáng thử |
|---|---|---|
| C-01 | Kho nén hỏng | `.zip` tải đứt giữa chừng |
| C-02 | Tệp rỗng 0 byte | rỗng KHÁC hỏng, thông điệp nên phân biệt |
| C-03 | `.pdf` nhưng ruột không phải PDF | đúng đuôi thì mọi lớp trên tin là PDF |
| C-04 | `constraints.yaml` sai cú pháp | thông điệp phải chỉ ra TỆP nào |
| C-05 | Project State hỏng JSON | tệp này phải sống sót qua crash (TC-03) |
| C-06 | Thư mục dự án không tồn tại | gõ nhầm tên dự án |
| C-07 | Đường dẫn leo ra ngoài dự án | đường dẫn này **mô hình điền được** |
| C-08 | Gate bị sửa tay thành approved | bất biến trung tâm của cả sản phẩm |
| C-09 | Nhà cung cấp thật, không có khóa API | máy CI, máy mới |
| C-10 | Mất mạng giữa chừng | `EAA_NO_NET=1` |
| C-11 | Mã model không tồn tại | người dùng gõ sai mã |
| C-12 | Tên module sai định dạng | mã module thành tên nhánh Git |
| C-13 | Lệnh không tồn tại | ca đầu tiên người dùng mới gặp |
| C-14 | Thiếu tham số bắt buộc | không được chạy tiếp với giá trị rỗng |
| C-15 | Duyệt gate cho module không tồn tại | duyệt nhầm là chuyện nghiêm trọng nhất |

---

## Lỗi thật số 1 — `EAA_NO_NET=1` không chặn lối ra mạng qua mô hình

**Ca C-10.** Lệnh chạy:

```
EAA_NO_NET=1 eaa --project projects/robot_balance research "ATmega328P TWI"
```

**Mong đợi:** hỏng sạch, nói rõ là vì mạng đã tắt.
**Thực tế vòng 1:** mã thoát 0, và đầu ra:

```
── tìm được 8 địa chỉ
  · medium.com  (qua trạm chuyển hướng)   [mở]
  · arxterra.com  (qua trạm chuyển hướng)   [mở]
  ...
```

Nó **ra Internet thật**, tám lần.

### Vì sao hụt

`EAA_NO_NET` chỉ được đọc trong `eaa/web.py`. Nhưng engine có **ba** lối ra
mạng, không phải một:

| lối ra | tệp | có đọc công tắc không (trước bản sửa) |
|---|---|---|
| tải trang web | `eaa/web.py` | có |
| gọi API mô hình, **kể cả tìm kiếm có grounding** | `eaa/llm/gemini.py` | **không** |
| dò kết nối | `eaa/environ.py` | có |

`eaa research` đi qua lối thứ hai. Người dùng tin rằng mình đã ngắt mạng thì
vẫn đang gọi ra ngoài.

Đây là kiểu hỏng tệ nhất một công tắc an toàn có thể mắc: nó **trông như đã
tắt**. Một công tắc không hoạt động mà báo lỗi thì người ta sửa; một công tắc
không hoạt động mà im lặng thì người ta tin.

### Đã sửa

* `eaa/web.py` có hàm `mang_bi_tat()` — **một** chỗ định nghĩa luật, ba chỗ hỏi.
* `GeminiClient._post()` chặn trước khi gửi; chặn ở `_post` chứ không ở từng
  phương thức công khai, để mọi đường tới nhà cung cấp — kể cả đường thêm sau
  này — đều đi qua nó.
* Cả phép tra siêu dữ liệu model (`output_limit()`) cũng bị chặn: tra trần
  token cũng là một lượt gọi ra ngoài.
* Thông điệp chỉ đường ra: `--provider mock` hoặc `--provider replay`.

Kiểm lại:

```
$ EAA_NO_NET=1 eaa --project projects/robot_balance research "ATmega328P TWI"
Lỗi: Không nguồn tìm kiếm nào trả kết quả:
  gemini-grounding: Nhà cung cấp mô hình không tìm được: Lối ra mạng đang tắt
  (EAA_NO_NET=1) nên không gọi được mô hình. Bỏ biến ấy đi để cho phép, hoặc
  chuyển sang nhà cung cấp không cần mạng: 'eaa init --provider mock' (tất
  định) hoặc '--provider replay' (phát lại nhật ký đã ghi).
```

Có **bài canh cấu trúc**: quét cả `eaa/`, đỏ nếu có tệp nào tự đọc
`EAA_NO_NET` thay vì hỏi `mang_bi_tat()`. Thêm lối ra mạng thứ tư mà quên
công tắc thì đỏ ngay, không đợi tới lúc ai đó tin nhầm.

---

## Lỗi thật số 2 — băm ràng buộc không bao giờ được đối chiếu với tệp

**Ca C-04.** Ca này ban đầu chạy `eaa status` và **đạt** — nhưng đạt vì lý do
sai. `status` in ra một băm ràng buộc trong khi `constraints.yaml` trên đĩa đã
hỏng hoàn toàn. Nó không đọc tệp; nó đọc lại con số đã ghi trong Project State.

Thử tiếp:

```
$ eaa --project <bản sao> status | grep "Ràng buộc"
Ràng buộc     : sha256:c11ca8719e...

$ printf '\n# ghi chú thêm\n' >> <bản sao>/constraints.yaml
$ eaa --project <bản sao> status | grep "Ràng buộc"
Ràng buộc     : sha256:c11ca8719e...      ← KHÔNG ĐỔI

$ sha256sum <bản sao>/constraints.yaml
695f873ed26a...                            ← băm thật
```

### Vì sao nghiêm trọng hơn vẻ ngoài

`constraints_version` không phải một nhãn trang trí. Theo **NFR-07** nó đi vào
**commit message** làm bằng chứng xuất xứ: *"mã này sinh ra dưới bộ ràng buộc
ấy"*. Băm cũ + tệp mới = mọi commit sau đó mang một khẳng định **sai**, và
khẳng định ấy nằm vĩnh viễn trong lịch sử Git — chỗ không sửa lại được.

### Bộ dò bắt được một ca thật ngay trong kho này

Chạy trên cả ba dự án, **`projects/robot_balance` đang trôi thật**:

```
── projects/blklab_robot/   (khớp)
── projects/disco_f469/     (khớp)
── projects/robot_balance/
Ràng buộc : sha256:c11ca8719e...
            ⚠ TRÔI: tệp trên đĩa băm sha256:9a50760e21...
```

Lịch sử Git giải thích:

```
$ git log --oneline -1 -- projects/robot_balance/constraints.yaml
f6b9d49 Hoàn thiện 25 nghiệp vụ còn thiếu + hai test case của thiết kế

$ git log --oneline -1 -- projects/robot_balance/project_state.json
ea63c88 S2 xong: Orchestrator 13 bước + KPI + CLI
```

`constraints.yaml` sửa ở `f6b9d49`; `project_state.json` chưa động từ `ea63c88`
— sớm hơn nhiều sprint. Băm đã lệch từ đó, im lặng, và không có gì báo.

**Chưa tự sửa chỗ này.** Ghi lại băm mới là một hành động thuộc gate G1 —
chốt bộ ràng buộc là quyết định của người, và một lệnh tự ghim lại băm chính
là lối tắt mà thiết kế cấm. Cảnh báo sẽ hiện ở mỗi `eaa status` cho tới khi
được chốt qua G1.

### Đã sửa (phần cơ chế)

`_troi_rang_buoc()` trong `eaa/cli.py`, gọi từ `_in_tom_tat` — cảnh báo nằm ở
lệnh người ta gõ hằng ngày, không ở một lệnh ẩn. Nói ba thứ: băm thật là bao
nhiêu, vì sao chuyện này quan trọng (NFR-07), và đường chốt lại (G1). Khớp thì
im lặng.

---

## Lỗi thật số 3 — biến môi trường đặt RỖNG bị `.env` điền đè

**Ca C-09.** Đặt `EAA_LLM_KEY=""` để thử đường không-có-khóa. Agent vẫn trả
lời bình thường — nó lấy khóa thật từ `.env`.

`load_env_file()` khai ở docstring:

> **Biến đã đặt trong shell luôn thắng.**

nhưng mã kiểm bằng truthiness:

```python
if os.environ.get(ten):   # chuỗi rỗng là falsy
    continue
```

Một biến đặt thành chuỗi rỗng **là** một biến đã đặt. Mã lệch với chính luật
nó khai ba dòng phía trên.

Hệ quả thực tế: trên một máy có sẵn `.env`, **không có cách nào** chạy thử
đường không-có-khóa. Đúng đường mà CI và máy mới sẽ đi.

### Đã sửa

`if ten in os.environ` thay cho truthiness, và docstring nói rõ trường hợp
chuỗi rỗng. Kiểm lại:

```
$ EAA_LLM_KEY= eaa --project <bản sao> chat "xin chào"
Lỗi: Không hỏi được mô hình: Chưa có khóa API trong biến môi trường
EAA_LLM_KEY. Khóa chỉ được đọc từ biến môi trường và không bao giờ ghi ra log
hay commit (NFR-06).
    export EAA_LLM_KEY='<khóa của bạn>'
```

Mã thoát 4 (lỗi môi trường) — đúng nghĩa.

---

## Ba ca hỏng vòng 1 do kịch bản test của tôi sai

Ghi lại vì chúng cũng là dữ liệu:

* **C-01, C-02** — tôi dùng cờ `--archive` không tồn tại; `survey` nhận kho nén
  ở tham số vị trí. Sản phẩm từ chối đúng (mã 2, "đang chờ người"), kịch bản
  chấm sai.
* **C-04** — tôi chọn `eaa status`, lệnh không nạp `constraints.yaml`. Đổi
  sang `eaa budget show` thì thông điệp hiện ra rất tốt: đường dẫn đầy đủ,
  lý do, số dòng, số cột.

Chỗ C-04 đáng chú ý: **một ca test viết sai lại là chỗ tìm ra lỗi thật số 2.**
Nếu nó "đạt" ngay từ đầu tôi đã không nhìn kỹ vì sao `status` in được một băm
từ một tệp hỏng.

---

## Những ca đã đúng ngay từ vòng 1

| Ca | Sản phẩm xử lý |
|---|---|
| C-03 | Từ chối tệp `.pdf` không có chữ ký `%PDF`, mã 4. Không trả chuỗi rỗng — nếu trả rỗng thì cả hệ hiểu thành "tài liệu này trống", và **gần đúng tệ hơn hỏng hẳn** |
| C-05 | Báo Project State hỏng, không im lặng dựng state rỗng đè lên |
| C-06 | Báo dự án không tồn tại |
| C-07 | Chặn `../../../../etc/passwd`, không có chuỗi `root:` nào trong đầu ra |
| C-08 | Tệp gate chép tay với `evidence: []` không mở được đường merge |
| C-11 | Mã model sai → báo mã không tồn tại, chỉ sang `eaa models` |
| C-12 | `"drv x --uses twi"` bị chặn tại chỗ nhập (mã module thành tên nhánh Git) |
| C-13, C-14, C-15 | argparse và tầng gate từ chối đúng, mã thoát 2 |

---

## Điều bài kiểm này nói về sản phẩm

Mười hai trên mười lăm ca đúng ngay lần đầu, kể cả những ca khó (C-07 leo
đường dẫn, C-08 gate chép tay). Ba lỗi tìm được đều **không nằm ở đường
chính** — chúng nằm ở chỗ hai phần của hệ nói hai chuyện khác nhau:

* một công tắc và một lối ra mạng nó không biết,
* một con số và cái tệp nó lẽ ra phải mô tả,
* một dòng docstring và ba dòng mã ngay dưới nó.

Không lỗi nào bắt được bằng cách đọc kỹ hơn một tệp. Cả ba chỉ hiện ra khi
**chạy thật và gõ sai**.
