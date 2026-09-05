#!/usr/bin/env python3
"""Dựng báo cáo benchmark EAA với các sản phẩm tốt nhất trên thị trường.

    python scripts/lam_bao_cao_benchmark.py

Sinh ``docs/EAA_Benchmark_San_pham.docx`` (và ``.md`` cạnh nó).

Vì sao báo cáo này do CHÍNH SẢN PHẨM xuất ra
---------------------------------------------

Dùng ``eaa/docmodel.py`` + ``eaa/office.py`` chứ không dùng một thư viện ngoài.
Hai lý do, và lý do thứ hai mới là lý do thật:

1. Không thêm phụ thuộc (NFR-04).
2. Một báo cáo nói rằng sản phẩm xuất được tài liệu nộp được, mà bản thân nó
   lại do một công cụ khác xuất ra, thì nó đang tự bác mình ở dòng đầu tiên.

Hai hạng bằng chứng — luật của cả báo cáo
------------------------------------------

* **ĐO** — con số lấy bằng cách chạy lệnh trên chính kho này, ngày ghi ở bìa.
  Mọi ô của cột EAA đều hạng này, hoặc ghi thẳng là CHƯA CÓ.
* **KHAI** — thứ nhà cung cấp công bố trên trang chính chủ hoặc trong bài báo.
  Không chạy thử được, và báo cáo không giả vờ ngược lại.

Cột ĐO và cột KHAI **không cộng lại thành điểm số**. Một bảng xếp hạng dựng
trên hai hạng bằng chứng khác nhau là một bảng xếp hạng sai, và nó sai theo
hướng có lợi cho người viết — tức là hướng khó tự phát hiện nhất.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC))

RA_DOCX = GOC / "docs" / "EAA_Benchmark_San_pham.docx"
RA_MD = GOC / "docs" / "EAA_Benchmark_San_pham.md"

NGAY = "05/09/2026"

# ==========================================================================
# SỐ ĐO — mọi con số dưới đây lấy bằng cách chạy lệnh trên kho này ngày 05/09.
# Lệnh tái lập ghi ngay cạnh, để người đọc kiểm lại được chứ không phải tin.
# ==========================================================================

DO: list[tuple[str, str, str]] = [
    # (đại lượng, giá trị, lệnh tái lập)
    ("Bộ test", "2.656 bài, 0 đỏ, 7 phút 28", "pytest -q"),
    ("Tệp ca kiểm thử", "120 tệp TC", "ls tests/test_tc*.py | wc -l"),
    ("Hàm test", "2.409", "grep -rc '^def test' tests/*.py"),
    ("Độ phủ mã phần lõi",
     "92% (composer · gates · orchestrator · state · vcs)",
     "pytest --cov=eaa.orchestrator --cov=eaa.gates --cov=eaa.state "
     "--cov=eaa.vcs --cov=eaa.composer"),
    ("Quy mô engine", "89 tệp, 48.230 dòng Python", "find eaa -name '*.py' | xargs wc -l"),
    ("Quy mô bộ kiểm", "136 tệp, 36.565 dòng", "find tests -name '*.py' | xargs wc -l"),
    ("Ranh giới engine", "TC-38 xanh — 0 hằng số phần cứng trong eaa/",
     "pytest tests/test_tc38_engine_purity.py"),
    ("Lệnh CLI", "56 lệnh cấp một, 103 lệnh đầy đủ", "eaa --help"),
    ("Công cụ Agent tự gọi", "75 mục trong TOOLBOX", "eaa capabilities"),
    ("Cổng kiểm chứng", "5 cổng (4 bắt buộc + regcheck)",
     "OrchestratorConfig().required_gates"),
    ("Lớp ngữ cảnh prompt", "10 lớp, trần tổng 8.000 token, kiểm TRƯỚC khi gọi",
     "eaa.llm.base.LAYER_BUDGETS"),
    ("Lớp kết luận mang nhãn tin cậy", "23 lớp", "pytest tests/test_tc63_confidence_coverage.py"),
    ("Sổ sai lệch thiết kế", "178 mục, mỗi mục một bài kiểm canh",
     "grep -c '^## SL-' docs/SAI_LECH_THIET_KE.md"),
    ("Độ trễ lệnh đọc",
     "status 0,57s · observe 0,66s · recall 0,66s · knowledge stale 0,76s",
     "đo 3 lần, lấy nhanh nhất"),
    ("Tính tất định", "TC-15 chạy hai lần cho cùng 13/13 xanh, không cần khoá API",
     "pytest tests/test_tc15_e2e.py (×2)"),
    ("Thông báo lỗi nêu được lệnh phải gõ",
     "150/182 — 82% (mốc trước khi sửa: 25/182 — 14%)",
     "quét `raise CliError(` bằng phép đếm ngoặc cân; TC-145 canh"),
    ("Lệnh thiếu dòng trợ giúp", "0/103", "duyệt cây argparse"),
    ("Mã thoát phân biệt", "4 mã: 0 · 2 chờ gate · 3 hết vòng vá · 4 lỗi môi trường", "eaa/__init__.py"),
]

# ==========================================================================
# BỐN LỚP BENCHMARK
# ==========================================================================

# (tiêu chí, EAA — ĐO được, đối thủ mạnh nhất ở tiêu chí này — KHAI, kết luận)
TINH_NANG: list[tuple[str, str, str, str]] = [
    ("Nối đất bằng tài liệu phần cứng",
     "ĐO: trích đoạn qua G2; luật `// ref:` cưỡng chế ở cổng tĩnh (TC-17); "
     "cổng `regcheck` kiểm giá trị lọt vừa trường bit theo SVD/ATDF",
     "Embedder KHAI: chỉ mục manual/datasheet/errata/SVD, trích dẫn từng giá trị",
     "NGANG, và ta cưỡng chế mạnh hơn: thiếu trích dẫn là cổng ĐỎ. Không nguồn "
     "nào khảo sát được nêu phép kiểm ĐỘ RỘNG TRƯỜNG BIT"),
    ("Bối cảnh bo từ sơ đồ nguyên lý",
     "CHƯA CÓ. Hồ sơ phần cứng gõ tay",
     "Embedder KHAI: đọc Altium/KiCad/Eagle/PADS, giải netlist ra chân, pull-up, "
     "địa chỉ bus",
     "THIẾU RÕ. Và SL-125 là lần chính chỗ gõ tay ấy sai — giá phải trả là robot "
     "lao thẳng một phía"),
    ("Bề rộng nền tảng",
     "ĐO: 2 Platform Pack (avr, stm32), dùng chung engine — TC-47",
     "Embedder KHAI: 500+ nền tảng, 13 hãng, 5.500+ ngoại vi",
     "KHOẢNG CÁCH LỚN. Nhưng TC-47 đã chứng minh thêm pack không phải sửa engine "
     "— đây là công việc tuyến tính, không phải rào kiến trúc"),
    ("Tri thức nén theo ngoại vi (kỹ năng)",
     "MỘT PHẦN: `eaa/skills.py` rút kỹ năng QUY TRÌNH; chưa có kỹ năng PHẦN CỨNG",
     "arXiv KHAI + ĐO: kỹ năng người soạn nâng ESP-IDF 26→40/42, Zephyr 24→39/42",
     "THIẾU, và bài ấy đo được rằng nó đáng làm. Ghi chú quan trọng: kỹ năng do "
     "LLM TỰ SINH làm TỆ ĐI (Zephyr 24→19) và tốn gấp 15–30 lần token"),
    ("Nạp firmware và đọc ngược xác minh",
     "ĐO: `eaa/flash.py` preflight + đối chiếu băm ảnh; 26 lượt nạp có đọc ngược",
     "Embedder KHAI: flash + serial smoke test",
     "NGANG trở lên — ta đối chiếu băm ảnh, họ không nêu bước đọc ngược"),
    ("Điều khiển máy đo, phiên gỡ lỗi tự động",
     "CHƯA CÓ. `eaa/debugsession.py` dựng kế hoạch phiên, NGƯỜI chạy (mức T0)",
     "Embedder KHAI: 30+ đầu dò, logic analyzer, dao động ký, đo công suất tương "
     "quan với thực thi",
     "KHOẢNG CÁCH PHẦN CỨNG LỚN NHẤT. Tốn thiết bị, không chỉ tốn mã"),
    ("Vòng đời tri thức: sửa tài liệu → truy ngược mã",
     "ĐO: `eaa knowledge stale` hợp BA đường; chạy thật trên robot_balance trả 2 "
     "module, một cái bị cả ba đường bắt",
     "Không nguồn nào khảo sát được nêu",
     "**TA HƠN**"),
    ("Trả lời câu hỏi từ kho tri thức đã duyệt",
     "ĐO: `eaa recall`, hai tầng đồ thị → BM25, chỉ trả chunk qua G2 (TC-126)",
     "Sidekick / MCP Espressif KHAI: tra cứu tài liệu chính chủ",
     "NGANG về chức năng; khác về trách nhiệm — họ dặn người dùng tự đối chiếu, "
     "ta chỉ trả thứ đã có người đối chiếu"),
]

KIEN_TRUC: list[tuple[str, str, str, str]] = [
    ("Ranh giới tầng cưỡng chế bằng máy",
     "ĐO: TC-38 quét mỗi commit — 0 hằng số phần cứng trong 89 tệp / 48.230 dòng "
     "engine. Thêm pack thứ hai không sửa một dòng engine (TC-47)",
     "Không nguồn nào nêu một phép kiểm tự động cho ranh giới của chính mình",
     "**TA HƠN.** Đây là tính chất KIẾN TRÚC duy nhất trong bảng có bài kiểm canh"),
    ("Điểm dừng của con người",
     "ĐO: 5 Human Gate; `TOOLBOX` là danh sách TĨNH trong Git và không chứa lệnh "
     "DUYỆT nào; merge đòi giấy phép neo vào BĂM NỘI DUNG (TC-01, TC-02)",
     "Embedder KHAI: người duyệt kế hoạch, xem từng diff, và CHỌN hành động nào "
     "cần duyệt",
     "KHÁC VỀ CHẤT. Của họ cấu hình được, tức tắt được. Của ta là bất biến — "
     "Agent KHÔNG CÓ ĐƯỜNG GỌI tới lệnh duyệt, chứ không phải được dặn đừng gọi"),
    ("Kho tri thức nối tiếp, không ghi đè",
     "ĐO: append-only + supersede ở cả 5 kho; hạ cấp một trích đoạn giữ NỘI DUNG "
     "nguyên từng byte, chỉ đổi siêu dữ liệu (TC-29, TC-132)",
     "Không nguồn nào nêu",
     "**TA HƠN.** Lịch sử truy vết chỉ có giá khi không ai được phép viết lại"),
    ("Ngân sách ngữ cảnh cưỡng chế TRƯỚC khi gọi",
     "ĐO: 10 lớp, trần tổng 8.000 token, `check_budget()` chạy trước mọi lượt gọi "
     "(TC-16). Đếm cả token SUY NGHĨ của model có tầng suy luận (SL-170)",
     "arXiv KHAI: đo token vào trung bình theo cấu hình kỹ năng",
     "TA HƠN ở chỗ CƯỠNG CHẾ: họ đo, ta chặn trước khi tiêu"),
    ("Tính tất định và tái lập",
     "ĐO: model ghim phiên bản, prompt stateless, bộ phát lại đọc nhật ký và CỐ Ý "
     "không bịa khi trượt băm; env_lock băm toolchain. TC-15 chạy hai lần cho cùng "
     "kết quả, không cần khoá API",
     "Parasoft/LDRA KHAI: công cụ phải tất định mới *qualify* theo ISO 26262",
     "**TA HƠN trong nhóm sinh mã.** Đây là điều kiện chuẩn đòi, và ta thoả MỘT "
     "trong các điều kiện ấy — không phải 'đạt chuẩn'"),
    ("Tự soi: hệ ghi lại chỗ chính nó sai",
     "ĐO: 177 mục sổ sai lệch, mỗi mục một bài kiểm; `eaa deviations` quét mã ↔ "
     "tài liệu mỗi lần chạy (TC-60)",
     "Không nguồn nào nêu",
     "**TA HƠN.** Đây là dữ liệu gốc của phương pháp huấn luyện, và là thứ một "
     "sản phẩm thương mại không có lý do gì công bố"),
    ("Bộ dò 'mã tự chỉnh cho vừa đồ đo'",
     "ĐO: `eaa/instrument.py` ba dấu vết, dừng vòng vá và hỏi người (TC-131, 25 bài)",
     "Không nguồn nào nêu",
     "**TA HƠN.** 3/12 lần từ chối G3 của chính đề án là hạng lỗi này, và cả ba "
     "đi qua sạch bốn cổng"),
    ("Đo độ nhạy của bài kiểm sinh ra",
     "ĐO: `eaa/sensitivity.py` chạy bộ kiểm mới trên mã vừa bị đánh đỏ (TC-128)",
     "Không benchmark nào trong khảo sát hỏi — cả ba đều đo pass/fail",
     "**TA HƠN.** Một bài kiểm xanh chưa phải bằng chứng"),
]

PHI_CHUC_NANG: list[tuple[str, str, str, str]] = [
    ("Độ phủ mã phần lõi",
     "ĐO: 92% trên composer/gates/orchestrator/state/vcs. Yêu cầu của đề án là ≥80%",
     "Không nguồn nào công bố",
     "VƯỢT yêu cầu tự đặt. Không so được với ai vì không ai công bố"),
    ("Thời gian chạy bộ kiểm",
     "ĐO: 2.656 bài trong 7 phút 28 trên một máy để bàn",
     "Không nguồn nào công bố",
     "Đủ nhanh để chạy mỗi commit — và nó ĐANG chạy mỗi commit"),
    ("Độ trễ tương tác",
     "ĐO: lệnh đọc 0,25–0,79 giây",
     "Không nguồn nào công bố",
     "Đủ nhanh cho vòng hỏi–đáp. Lượt SINH MÃ thì do mô hình quyết định, không "
     "phải do ta"),
    ("Bảo mật khoá API",
     "ĐO: khoá chỉ qua biến môi trường; TC-14 canh khoá không lọt vào log, ngoại "
     "lệ, `repr`, hay nhật ký lời gọi",
     "Embedder KHAI: SOC 2 Type II, ISO 27001, GDPR, triển khai air-gapped",
     "KHÁC HẠNG — của họ là chứng nhận TỔ CHỨC, của ta là tính chất PHẦN MỀM có "
     "test. Hai thứ không thay nhau được, và ta không có cái thứ nhất"),
    ("Chạy ngoại tuyến",
     "ĐO: `EAA_NO_NET=1` cắt mọi lối ra mạng; MockLLM và bộ phát lại chạy không "
     "cần khoá",
     "Embedder KHAI: triển khai on-prem và air-gapped",
     "MỘT PHẦN. Ta chạy được không mạng, nhưng lượt gọi mô hình THẬT vẫn ra API "
     "ngoài. Air-gapped đòi mô hình chạy tại chỗ"),
    ("Chi phí mỗi lượt gọi",
     "ĐO: `llm_calls.jsonl` ghi token vào/ra từng lượt; `TokenBudget` chặn trước",
     "arXiv KHAI: token vào trung bình theo cấu hình",
     "NGANG trở lên"),
    ("Chạy nhiều phiên trên cùng một bo",
     "CHƯA CÓ",
     "Embedder KHAI: trọng tài phần cứng, chặn hai phiên cùng lái một bo",
     "THIẾU, và nó thành lỗi thật ngay khi có người thứ hai. Rẻ: một khoá tệp "
     "trên cổng nối tiếp"),
]

UI_UX: list[tuple[str, str, str, str]] = [
    ("Mặt tiếp xúc chính",
     "ĐO: CLI 56 lệnh cấp một + tầng hội thoại tiếng Việt `eaa chat`",
     "Embedder KHAI: extension VS Code là mặt chính, kèm CLI và daemon cho "
     "terminal/GitHub/Slack/CI. Espressif KHAI: Copilot trong IDE của hãng",
     "THIẾU IDE. Đây là chỗ kỹ sư nhúng ngồi cả ngày. Không đụng lõi: một lớp "
     "mỏng gọi CLI"),
    ("Trợ giúp và khám phá",
     "ĐO: 0/103 lệnh thiếu dòng trợ giúp; `eaa capabilities` bày 4 tầng năng lực",
     "Không nguồn nào công bố",
     "TỐT, và đo được"),
    ("Chất lượng thông báo lỗi",
     "ĐO: 150/182 thông báo lỗi (82%) nói được VIỆC PHẢI LÀM. Mốc trước khi "
     "sửa là 25/182 — 14%",
     "Không nguồn nào công bố",
     "**ĐÃ SỬA (SL-178).** Bảng `GOI_Y_KHI_HONG` gắn ở `main()`, nên lỗi ném "
     "từ hàm phụ trợ vẫn nhận đúng gợi ý của lệnh đang chạy. TC-145 đối chiếu "
     "bảng với cây lệnh thật, hai chiều — một gợi ý trỏ vào lệnh đã bị xoá là "
     "đỏ"),
    ("Nói ra mức tin cậy của mỗi câu trả lời",
     "ĐO: 23 lớp kết luận mang một trong bốn mức ĐÃ KIỂM / SUY RA / GIẢ ĐỊNH / "
     "KHÔNG KIỂM ĐƯỢC; TC-63 canh không lớp nào quên",
     "Sidekick KHAI ngược lại: dặn người dùng TỰ đối chiếu tài liệu gốc",
     "**TA HƠN.** Nhưng nói cho đúng: 23 LỚP KẾT LUẬN, không phải mọi dòng đầu ra"),
    ("Mã thoát cho tự động hoá",
     "ĐO: 4 mã phân biệt — 0 · 2 chờ gate · 3 hết vòng vá · 4 lỗi môi trường",
     "Embedder KHAI: CLI và daemon cho CI",
     "NGANG. Bốn mã ấy là thứ một pipeline CI cần"),
    ("Ngôn ngữ",
     "ĐO: toàn bộ giao diện, thông báo và tài liệu bằng tiếng Việt",
     "Sidekick KHAI: hỏi được nhiều thứ tiếng, giao diện chính tiếng Anh",
     "KHÁC BIỆT CÓ CHỦ ĐÍCH cho bối cảnh đề án; đồng thời là rào nếu muốn ra "
     "ngoài — phải nói ra chứ không giấu"),
]

VIEC_PHAI_LAM: list[tuple[str, str, str, str]] = [
    # (ưu tiên, việc, vì sao, đo được bằng gì khi xong)
    ("1 · XONG",
     "Sửa thông báo lỗi: nâng tỉ lệ nói được việc phải làm lên ≥80% — ĐẠT 82%",
     "Điểm yếu UI/UX ĐO ĐƯỢC duy nhất trong bảng, và là chỗ rẻ nhất. Đo lại "
     "bằng phép quét đúng thì mốc thật là 14%, không phải 36% như bản trước "
     "công bố — bản này đính chính",
     "ĐÃ ĐO: 150/182 = 82%. TC-145 (11 bài, 4 đột biến đều bị bắt) canh cả tỉ "
     "lệ lẫn tính đúng của từng gợi ý. Xem SL-178"),
    ("2 · Cao",
     "Bộ nhiệm vụ cho thước đo, trên ≥2 Platform Pack",
     "Cái thước đã có (GĐ2) nhưng chưa đo gì. Bốn trục đang báo CHƯA ĐO ĐƯỢC — "
     "và một đóng góp không có số là một lời khai",
     "`eaa report bench` ra số thật cho cả bốn trục"),
    ("3 · Cao",
     "Đo ngược lịch sử dự án bằng bốn bộ dò",
     "37 commit và 12 lượt chuyển module đã nằm trong Git. Không tốn token API. "
     "Nếu bốn bộ dò tìm lại được các lỗi đã biết thì đó là bằng chứng hồi cứu; "
     "nếu bỏ sót thì đó là phát hiện còn giá trị hơn",
     "Bảng số cho Chương 3, và danh sách lỗi bộ dò bỏ sót"),
    ("4 · Vừa",
     "Kỹ năng phần cứng theo ngoại vi, duyệt qua G2",
     "Chỗ DUY NHẤT bài arXiv đo được là nâng kết quả lên gần trần. Và nó chặn "
     "hạng lỗi đã làm robot ngã: mã đúng mọi dòng, sai ở THỨ TỰ",
     "So pass@k trước/sau khi bật lớp kỹ năng, trên cùng bộ nhiệm vụ"),
    ("5 · Vừa",
     "Đọc netlist và ĐỐI CHIẾU với hồ sơ phần cứng ở G1",
     "Bắt hạng lỗi SL-125 — hồ sơ gõ tay lệch với mạch thật",
     "Số chỗ lệch tìm được trên dự án thật"),
    ("6 · Vừa",
     "Trọng tài phần cứng: khoá cổng nối tiếp",
     "Thành lỗi thật ngay khi có người thứ hai chạy cùng bo",
     "Hai phiên đồng thời: phiên thứ hai phải bị chặn với thông báo rõ"),
    ("7 · Vừa",
     "Lớp mỏng tích hợp IDE",
     "Mặt tiếp xúc mà kỹ sư nhúng ngồi trong đó cả ngày. Không đụng lõi",
     "Số bước từ mở IDE tới lượt sinh đầu tiên"),
    ("8 · Thấp",
     "Điều khiển máy đo và phiên gỡ lỗi tự động",
     "Khoảng cách phần cứng lớn nhất, nhưng tốn THIẾT BỊ chứ không chỉ tốn mã. "
     "Và chỉ có nghĩa khi đã có thước để chứng minh nó cải thiện được gì",
     "Số kịch bản chẩn đoán chạy được không cần người cầm que đo"),
]


def dung_tai_lieu():
    from eaa.docmodel import Bullets, Doc, Heading, Note, PageBreak, Para, Table

    b: list = []

    def h(t, l=1):
        b.append(Heading(t, level=l))

    def p(t):
        b.append(Para(t))

    def bang(header, rows, caption=""):
        b.append(Table(header=list(header), rows=[list(r) for r in rows], caption=caption))

    # ---------------------------------------------------------------- §1 --
    h("1. Báo cáo này đọc thế nào")
    p("Báo cáo so sản phẩm của đề án với những sản phẩm mạnh nhất hiện có trên "
      "thị trường Agent lập trình nhúng, theo bốn lớp: tính năng · kiến trúc lõi "
      "· phi chức năng · giao diện và trải nghiệm.")
    b.append(Note(
        "Hai hạng bằng chứng, và chúng KHÔNG cộng lại thành điểm số. "
        "ĐO — con số lấy bằng cách chạy lệnh trên chính kho này ngày "
        f"{NGAY}; lệnh tái lập ghi ở §2. KHAI — thứ nhà cung cấp công bố, không "
        "chạy thử được. Một bảng xếp hạng dựng trên hai hạng bằng chứng khác "
        "nhau là bảng xếp hạng sai, và nó sai theo hướng có lợi cho người viết "
        "— tức là hướng khó tự phát hiện nhất.",
        level="canh_bao"))
    p("Vì lý do ấy, báo cáo không cho một điểm tổng. Nó cho bốn bảng, và một "
      "danh sách việc phải làm ở §7 — trong đó có cả những việc lộ ra từ chính "
      "phép đo của ta, không phải từ so với ai.")

    h("Bốn sản phẩm được lấy làm mốc", 2)
    bang(
        ["Sản phẩm", "Cốt lõi nó cược vào", "Vì sao lấy làm mốc"],
        [
            ["Embedder", "Vòng kín trên silicon thật — quan sát phần cứng là kênh "
             "phản hồi CHÍNH", "Gần đề án nhất về ý tưởng, và đi trước về bề rộng"],
            ["Skilled AI Agents (arXiv 2603.19583)", "Tri thức do NGƯỜI nén lại "
             "theo từng ngoại vi", "Mốc duy nhất có ablation đo được"],
            ["STM32 Sidekick · MCP Espressif", "Thẩm quyền trên tài liệu của hãng",
             "Mốc về chất lượng nguồn tri thức"],
            ["Parasoft · LDRA · QA Systems", "Bằng chứng chứng nhận, truy vết hai "
             "chiều", "Mốc về kỷ luật bằng chứng — gần ta nhất về triết lý"],
        ],
        caption="Bảng 1 — bốn mốc, mỗi mốc mạnh nhất ở một trục khác nhau",
    )

    b.append(PageBreak())

    # ---------------------------------------------------------------- §2 --
    h("2. Số đo của EAA — và lệnh để kiểm lại")
    p("Mọi con số trong báo cáo lấy từ bảng này. Cột lệnh có đó để người đọc "
      f"chạy lại chứ không phải để tin. Đo ngày {NGAY}.")
    bang(["Đại lượng", "Giá trị đo được", "Lệnh tái lập"], DO,
         caption="Bảng 2 — 18 số đo, tất cả chạy được lại")

    b.append(PageBreak())

    # ---------------------------------------------------------------- §3 --
    h("3. Lớp 1 — Tính năng sản phẩm")
    bang(["Tiêu chí", "EAA (ĐO)", "Mốc mạnh nhất (KHAI)", "Kết luận"], TINH_NANG,
         caption="Bảng 3 — tính năng")
    p("Đọc ra: ta ngang hoặc hơn ở phần TRI THỨC và KIỂM CHỨNG, và thua rõ ở "
      "phần CHẠM VÀO PHẦN CỨNG cùng BỀ RỘNG. Hai khoảng cách ấy không cùng độ "
      "khó — bề rộng là công việc tuyến tính đã có TC-47 chứng minh, còn máy đo "
      "thì tốn thiết bị.")

    b.append(PageBreak())

    # ---------------------------------------------------------------- §4 --
    h("4. Lớp 2 — Kiến trúc lõi")
    bang(["Tiêu chí", "EAA (ĐO)", "Mốc mạnh nhất (KHAI)", "Kết luận"], KIEN_TRUC,
         caption="Bảng 4 — kiến trúc")
    b.append(Note(
        "Đây là lớp EAA mạnh nhất, và sáu dòng 'TA HƠN' trong bảng không phải "
        "sáu ý tưởng rời. Chúng là MỘT: hệ thống phải biết, và phải nói ra, nó "
        "đáng tin tới đâu ở từng chỗ. Bốn mức tin cậy gắn vào 23 lớp kết luận "
        "là câu ấy viết thành mã.",
        level="ghi_nho"))

    b.append(PageBreak())

    # ---------------------------------------------------------------- §5 --
    h("5. Lớp 3 — Phi chức năng")
    bang(["Tiêu chí", "EAA (ĐO)", "Mốc mạnh nhất (KHAI)", "Kết luận"], PHI_CHUC_NANG,
         caption="Bảng 5 — phi chức năng")
    p("Chỗ phải nói thẳng: chứng nhận tổ chức (SOC 2, ISO 27001) là thứ ta "
      "KHÔNG có và cũng không phải tính năng phần mềm để mà làm. Nó là chứng "
      "nhận của một doanh nghiệp. Ghi vào đây để không ai nhầm nó là một khoảng "
      "trống kỹ thuật cần lấp.")

    # ---------------------------------------------------------------- §6 --
    h("6. Lớp 4 — Giao diện và trải nghiệm")
    bang(["Tiêu chí", "EAA (ĐO)", "Mốc mạnh nhất (KHAI)", "Kết luận"], UI_UX,
         caption="Bảng 6 — UI/UX")
    b.append(Note(
        "Phép đo tự chỉ ra một điểm yếu mà so sánh với đối thủ không chỉ ra "
        "được — và bản này phải đính chính chính nó. Bản trước công bố 36% "
        "(40/112); con số ấy SAI vì biểu thức quét chỉ bắt được một dạng viết "
        "`raise CliError(`, nên nó đếm thiếu cả tử lẫn mẫu. Quét lại bằng phép "
        "đếm ngoặc cân cho mốc thật: 25/182 — 14%. Sai số của phép đo chứ "
        "không phải của sản phẩm, nhưng nó đã được in ra nên nó được sửa công "
        "khai chứ không thay lặng lẽ.\n\n"
        "Đã sửa (SL-178): 150/182 — 82%. Cách sửa đáng nói hơn con số. Không "
        "viết gợi ý vào 182 chuỗi — mỗi chuỗi như vậy là một bản sao của cây "
        "lệnh, và nó lệch khỏi cây lệnh ngay lần đầu ai đó đổi tên một lệnh, "
        "mà không gì bắt được. Gom vào một bảng thì bắt được: TC-145 đối chiếu "
        "bảng gợi ý với cây lệnh dựng từ argparse, hai chiều.\n\n"
        "82% là CẬN DƯỚI. 32 chỗ còn lại nằm trong hàm phụ trợ mà phép quy về "
        "lệnh không với tới; lúc chạy thật chúng vẫn có gợi ý, vì bảng gắn ở "
        "`main()` — nơi biết người dùng vừa gõ lệnh nào. Báo cả hai con số.",
    ))

    b.append(PageBreak())

    # ---------------------------------------------------------------- §7 --
    h("7. Việc phải làm — thẳng thắn")
    bang(["Ưu tiên", "Việc", "Vì sao", "Xong thì đo bằng gì"], VIEC_PHAI_LAM,
         caption="Bảng 7 — tám việc, xếp theo giá trị trên chi phí")
    p("Ba việc đầu đều là việc BIẾN LỜI KHAI THÀNH SỐ, không phải việc thêm "
      "tính năng. Đó là chỗ đề án đang yếu nhất: sáu năng lực không ai có, "
      "nhưng chưa có số nào chứng minh chúng cải thiện được gì.")

    h("Điều kiện dừng", 2)
    b.append(Bullets([
        "Bốn trục đo mới có số liệu trên ít nhất hai Platform Pack.",
        "~~Tỉ lệ thông báo lỗi nói được việc phải làm đạt ≥ 80%, có bài kiểm "
        "canh.~~ XONG — 82%, TC-145.",
        "Bốn bộ dò chạy lại được trên 12 lượt chuyển module của lịch sử dự án, "
        "và kết quả — dù tìm ra hay bỏ sót — được ghi vào sổ sai lệch.",
    ]))
    p("Đến đó thì câu “Agent này tốt hơn” thôi là một lời khai; nó thành một "
      "bảng số mà người khác kiểm lại được.")

    # ---------------------------------------------------------------- §8 --
    h("8. Điều báo cáo này KHÔNG chứng minh")
    b.append(Bullets([
        "Không chạy thử sản phẩm thương mại nào. Cột KHAI là thứ nhà cung cấp "
        "công bố, và khoảng cách giữa “khai có” với “đo được” là khoảng cách "
        "không đo được từ bên ngoài.",
        "Không so chất lượng mã sinh ra của các bên. Muốn so thì phải có bộ "
        "nhiệm vụ chung chạy trên cùng phần cứng — chính là việc số 2 ở §7.",
        "Không khẳng định đề án “đạt chuẩn ISO 26262”. Nó thoả MỘT điều kiện "
        "mà chuẩn đòi — tính tất định của công cụ — và chỉ thế.",
    ]))

    return Doc(
        title="Benchmark: EAA với các sản phẩm Agent lập trình nhúng tốt nhất",
        subtitle=f"Bốn lớp: tính năng · kiến trúc lõi · phi chức năng · UI/UX — đo ngày {NGAY}",
        kind="bao_cao",
        project="Embedded AIDD Agent (EAA)",
        author="Vũ Trí Công — GVHD: TS. Nguyễn Trung Hiếu",
        created_at=date.today().isoformat(),
        blocks=b,
    )


def main() -> int:
    from eaa.office import write_docx, write_markdown

    doc = dung_tai_lieu()
    RA_DOCX.parent.mkdir(parents=True, exist_ok=True)
    write_docx(doc, RA_DOCX)
    write_markdown(doc, RA_MD)

    n_bang = sum(1 for x in doc.blocks if type(x).__name__ == "Table")
    print(f"Đã ghi {RA_DOCX.relative_to(GOC)}  ({RA_DOCX.stat().st_size:,} byte)")
    print(f"Đã ghi {RA_MD.relative_to(GOC)}")
    print(f"  khối    : {len(doc.blocks)} · bảng: {n_bang}")
    print(f"  số đo   : {len(DO)} đại lượng, mỗi cái kèm lệnh tái lập")
    print(f"  tiêu chí: {len(TINH_NANG)} tính năng · {len(KIEN_TRUC)} kiến trúc · "
          f"{len(PHI_CHUC_NANG)} phi chức năng · {len(UI_UX)} UI/UX")
    print(f"  việc    : {len(VIEC_PHAI_LAM)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
