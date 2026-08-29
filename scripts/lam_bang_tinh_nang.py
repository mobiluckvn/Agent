"""Sinh bảng Excel thống kê tính năng của Embedded AIDD Agent.

Chạy: python scripts/lam_bang_tinh_nang.py [đường-dẫn-xlsx]

Bảng này là DỮ LIỆU, không phải văn bản viết tay: mỗi dòng nêu tính năng, module
hiện thực, bằng chứng (mã test), và trạng thái. Nhờ vậy khi sprint sau đổi trạng
thái một dòng thì sửa đúng một chỗ, và con số ở sheet Tổng quan tự tính lại.

Bốn trạng thái, và ranh giới giữa chúng có ý nghĩa:

* ĐÃ LÀM — có mã, có test, chạy được end-to-end.
* MỘT PHẦN — có mã nhưng còn mắt xích thiếu; ghi rõ thiếu gì ở cột "Còn thiếu".
* CHƯA LÀM — chưa có mã.
* CỐ Ý KHÔNG LÀM — có thể làm nhưng thiết kế cấm; ghi rõ điều khoản cấm. Cột
  này quan trọng với người đọc bảng: "chưa tự cài được" và "cố ý không tự cài"
  là hai câu hoàn toàn khác nhau.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DA = "Đã làm"
PHAN = "Một phần"
CHUA = "Chưa làm"
COY = "Cố ý không làm"

# --------------------------------------------------------------------------
# Dữ liệu: (nhóm, tính năng, mô tả, module/lệnh, bằng chứng, trạng thái, còn thiếu)
# --------------------------------------------------------------------------

TINH_NANG: list[tuple[str, str, str, str, str, str, str]] = [
    # -- A. Khung xương & trạng thái ---------------------------------------
    ("A. Khung & trạng thái", "Project State ghi nguyên tử",
     "Ghi tạm → fsync → os.replace → fsync thư mục; sống sót qua crash giữa chừng",
     "eaa/state.py", "TC-03 (24 test)", DA, ""),
    ("A. Khung & trạng thái", "Khóa liên tiến trình",
     "Khóa tái nhập, tự thu hồi khóa mồ côi khi tiến trình giữ khóa đã chết",
     "eaa/state.py", "TC-03", DA, ""),
    ("A. Khung & trạng thái", "Máy trạng thái 13 công đoạn",
     "A1..F1, mỗi cung chuyển khai báo gate phải qua; không có cung tắt",
     "eaa/policy.py", "TC-08 (58 test)", DA, ""),
    ("A. Khung & trạng thái", "Bảng phân quyền AUTO / HUMAN",
     "Pha nào máy tự đi, pha nào bắt buộc có người",
     "eaa/policy.py", "TC-08", DA, ""),
    ("A. Khung & trạng thái", "Khôi phục phiên sau khi tắt máy",
     "Đọc lại Project State và nói bước kế tiếp",
     "eaa resume / status", "test_cli_s0.py", DA, ""),

    # -- B. Kiến trúc ba tầng ----------------------------------------------
    ("B. Kiến trúc ba tầng", "Engine sạch phần cứng",
     "Không một hằng số, tên thanh ghi hay tên chip nào trong eaa/",
     "toàn bộ eaa/", "TC-38 quét mỗi commit", DA, ""),
    ("B. Kiến trúc ba tầng", "Platform Pack qua interface",
     "Engine gọi toolchain chỉ qua eaa/platform.py; pack khai báo năng lực bằng YAML",
     "eaa/platform.py", "test_platform_pack.py", DA, ""),
    ("B. Kiến trúc ba tầng", "Thêm họ MCU mới không sửa engine (NFR-05)",
     "Cấu trúc đã tách đúng, nhưng mới có duy nhất pack AVR",
     "packs/avr/", "—", PHAN,
     "Chưa có pack thứ hai (STM32/ESP32) để chứng minh bằng thực nghiệm"),

    # -- C. Tri thức, RAG, vòng đời ----------------------------------------
    ("C. Tri thức & RAG", "Kho ràng buộc + hồ sơ phần cứng + thư viện prompt",
     "constraints.yaml, hardware_profile.yaml, prompt nền tảng theo pack",
     "eaa/kb.py", "test_kb.py", DA, ""),
    ("C. Tri thức & RAG", "Knowledge Graph module→ngoại vi→thanh ghi→chunk",
     "Đồ thị tự dựng từ kho tri thức; khớp tên thanh ghi chính xác, không nhúng vector",
     "eaa/graph.py", "TC-18 (31 test)", DA, ""),
    ("C. Tri thức & RAG", "Truy xuất chunk tất định",
     "Cùng câu hỏi cho cùng top-k; không phụ thuộc thứ tự ngẫu nhiên",
     "eaa/graph.py", "TC-18", DA, ""),
    ("C. Tri thức & RAG", "Nén ngữ cảnh K1–K7, ngân sách 8.000 token",
     "7 tầng có ngân sách con; cắt luật lỗi rồi tới interface, KHÔNG BAO GIỜ cắt chunk",
     "eaa/composer.py", "TC-04 (36 test), TC-16", DA, ""),
    ("C. Tri thức & RAG", "Bắt buộc trích dẫn // ref: <chunk-id>",
     "Mã cấu hình thanh ghi không có trích dẫn thì cổng static chặn",
     "eaa/tools/static.py", "TC-17", DA, ""),
    ("C. Tri thức & RAG", "Append-only + supersede + stale set",
     "Không ghi đè vật lý; chunk bị thay thì mã dùng nó bị đánh dấu cần xem lại",
     "eaa/lifecycle.py", "TC-29 (23 test)", DA, ""),
    ("C. Tri thức & RAG", "Ba đường truy vấn ngược",
     "Từ chunk tìm ra mã: qua đồ thị, qua // ref:, qua trailer chunk-ids của commit",
     "eaa/lifecycle.py", "TC-29", DA, ""),
    ("C. Tri thức & RAG", "Nạp PDF thành proposed fact",
     "Trích đoạn luôn ở trạng thái 'proposed', phải qua G2 mới thành tri thức",
     "eaa/ingest.py", "TC-22 (44 test)", DA, ""),
    ("C. Tri thức & RAG", "Nguồn web giới hạn miền nhà sản xuất",
     "So theo hậu tố tên miền, không so chuỗi con",
     "eaa/ingest.py", "TC-22", DA, ""),
    ("C. Tri thức & RAG", "Sổ giả định (Assumption Log)",
     "Giả định được ghi, và bị thay khi có số đo thật",
     "eaa/ingest.py", "TC-22", DA, ""),
    ("C. Tri thức & RAG", "Tự đánh giá đủ thông tin (RIC)",
     "Trả về CÓ / THIẾU / MÂU THUẪN; chuẩn hóa số nên 0b00 == 0x00 == 0",
     "eaa/readiness.py", "TC-24 (18 test)", DA, ""),
    ("C. Tri thức & RAG", "BM25 bổ trợ truy xuất theo từ khóa",
     "Tầng 2 của AIS §4.2",
     "eaa/rag.py (chưa có)", "—", CHUA,
     "Đã hoãn có chủ ý: đồ thị + khớp tên thanh ghi đang đủ cho phạm vi MVP"),

    # -- D. Sinh mã ---------------------------------------------------------
    ("D. Sinh mã", "Vòng lặp chuẩn 13 bước",
     "Từ chọn module tới merge, mỗi bước ghi vết vào Project State",
     "eaa/orchestrator.py", "TC-06 (28 test)", DA, ""),
    ("D. Sinh mã", "Vòng tự sửa ≤ 3 lần, dạng patch",
     "Gửi patch chứ không gửi lại cả tệp; quá 3 lần thì dừng và bàn giao người",
     "eaa/orchestrator.py", "TC-06, TC-19", DA, ""),
    ("D. Sinh mã", "Kiểm ngân sách token TRƯỚC khi gọi mô hình",
     "count_tokens chạy trước; vượt ngân sách thì không gọi API",
     "eaa/llm/base.py", "TC-16", DA, ""),
    ("D. Sinh mã", "Adapter Gemini Pro 3.1 ghim phiên bản",
     "REST thuần bằng urllib, stateless mỗi lần gọi, clamp output limit theo model thật",
     "eaa/llm/gemini.py", "TC-11 (31 test)", DA, ""),
    ("D. Sinh mã", "Lối gọi văn xuôi complete()",
     "Tra cứu / phân loại lỗi không phải sinh mã, nên không bị đòi khối ```file:",
     "eaa/llm/*.py", "TC-39", DA, ""),
    ("D. Sinh mã", "MockLLM tất định cho Sprint 1–3",
     "Cùng interface với mô hình thật; kiểm thử tích hợp không tốn API",
     "eaa/llm/mock.py", "toàn bộ test tích hợp", DA, ""),
    ("D. Sinh mã", "Nhật ký lời gọi + phát lại",
     "Lưu (băm prompt → phản hồi) làm bằng chứng; ReplayClient chạy lại không tốn API",
     "eaa/llm/calllog.py", "TC-15", DA, ""),
    ("D. Sinh mã", "Phát hiện mô hình trôi hành vi",
     "Cùng băm prompt mà hai phản hồi khác nhau thì hiện ra",
     "eaa/llm/calllog.py", "TC-15", DA, ""),
    ("D. Sinh mã", "Che khóa API ở mọi lối ra",
     "Không vào log, commit, repr, thông báo lỗi hay băm prompt",
     "eaa/llm/base.py", "TC-14", DA, ""),
    ("D. Sinh mã", "Ráp firmware hoàn chỉnh (main + scheduler)",
     "Sinh vòng lặp chính từ khuôn của pack, dịch mọi module đã merge, liên kết, ra ảnh nạp được",
     "eaa/firmware.py + eaa build", "TC-41 (24 test)", DA, ""),
    ("D. Sinh mã", "Bộ định thời hợp tác",
     "Bảng việc định kỳ; ngắt chỉ tăng bộ đếm, đọc bộ đếm trong khối nguyên tử",
     "packs/avr/templates/main.c.tmpl", "TC-41", DA, ""),
    ("D. Sinh mã", "Module đã merge không được bỏ quên khi ráp",
     "Merge mà vắng mặt trong firmware.yaml là LỖI; không chạy định kỳ thì khai step: null",
     "eaa/firmware.py", "TC-41b", DA, ""),
    ("D. Sinh mã", "Mã chưa merge không vào được firmware",
     "Bản thiết kế ráp nhắc tới module chưa qua G3 thì dừng",
     "eaa/firmware.py", "TC-41c", DA, ""),

    # -- E. Kiểm chứng & cổng ----------------------------------------------
    ("E. Kiểm chứng & cổng", "Bốn cổng công cụ",
     "compile, static, unittests, size — mỗi cổng trả ToolReport có bằng chứng",
     "eaa/tools/", "TC-07 (43 test)", DA, ""),
    ("E. Kiểm chứng & cổng", "Bất biến merge",
     "Chỉ merge khi TOÀN BỘ ToolReport.passed VÀ G3 duyệt; không có nhánh thứ hai",
     "eaa/vcs.py + orchestrator", "TC-01 (45 test)", DA, ""),
    ("E. Kiểm chứng & cổng", "Băm nội dung xuyên suốt",
     "Hồ sơ gate → quyết định → ủy quyền merge cùng một băm: người duyệt X thì merge đúng X",
     "eaa/gates.py, eaa/vcs.py", "TC-01", DA, ""),
    ("E. Kiểm chứng & cổng", "5 Human Gate không vượt được",
     "Không có cờ --yes / --force / --skip-gate nào tồn tại trong CLI",
     "eaa/gates.py", "TC-01, TC-28, TC-34", DA, ""),
    ("E. Kiểm chứng & cổng", "Phiên không có người ≠ người đồng ý",
     "Không phải TTY thì ném GateNotInteractive chứ không mặc định duyệt",
     "eaa/gates.py", "TC-28", DA, ""),
    ("E. Kiểm chứng & cổng", "Lỗi cấu hình không đi vào vòng tự sửa",
     "Thiếu luật, thiếu công cụ → chặn ngay, không đốt 3 lượt sửa vô ích",
     "eaa/orchestrator.py", "TC-06", DA, ""),
    ("E. Kiểm chứng & cổng", "Sổ lỗi ảo giác",
     "Append-only; phân xử ghi thành sự kiện mới chứ không sửa sự kiện cũ",
     "eaa/ledger.py", "TC-10 (20 test)", DA, ""),
    ("E. Kiểm chứng & cổng", "Báo cáo KPI",
     "Tỉ lệ qua cổng, số lượt tự sửa, token tiêu thụ theo module",
     "eaa/kpi.py + eaa report", "TC-09", DA, ""),
    ("E. Kiểm chứng & cổng", "Cổng SIL cho mã C sinh ra",
     "Chạy chính mã C sinh ra trong mô phỏng, không chỉ mô hình Python",
     "—", "—", CHUA,
     "Cố ý để ngoài chuỗi tự động: nếu nối vào mà không thật sự chạy artifact "
     "thì cổng sẽ 'đạt' mà chẳng kiểm gì — nguy hiểm hơn là không có cổng"),

    # -- F. Mô phỏng --------------------------------------------------------
    ("F. Mô phỏng", "Mô hình con lắc ngược + MIL",
     "Mô phỏng động lực học, đánh giá theo tiêu chí nghiệm thu",
     "eaa/tools/sim.py, sim_runner.py", "TC-12 (12 test)", DA, ""),
    ("F. Mô phỏng", "Quét tham số",
     "Quét lưới bộ tham số điều khiển, xếp hạng theo chỉ số",
     "eaa sim --sweep", "TC-12", DA, ""),
    ("F. Mô phỏng", "Chỉ số thời gian ổn định đo đúng",
     "Đo từ lần cuối tín hiệu rời dải, tính từ lúc nhiễu kết thúc",
     "eaa/tools/sim.py", "test_sim_verification.py", DA, ""),

    # -- G. Công cụ & môi trường -------------------------------------------
    ("G. Công cụ & môi trường", "Chế độ 1 — quét công cụ đã có",
     "Có gì trên máy, phiên bản bao nhiêu, thiếu thì chặn cổng nào",
     "eaa doctor", "TC-34 (37 test)", DA, ""),
    ("G. Công cụ & môi trường", "Chế độ 2 — sinh lệnh cài",
     "Sinh đúng lệnh theo hệ điều hành, hỏi người trước từng lệnh",
     "eaa doctor --fix", "TC-34, TC-37", DA, ""),
    ("G. Công cụ & môi trường", "Chế độ 3 — TỰ TÌM công cụ chưa biết",
     "Phát hiện → tra cứu bằng mô hình → đề xuất; đây là phần vừa làm xong",
     "eaa/toolsearch.py", "TC-39 (29 test)", DA, ""),
    ("G. Công cụ & môi trường", "Nhu cầu công cụ suy từ Platform Pack",
     "Không chép tay danh sách: pack.yaml đã ghi mọi chương trình nó gọi",
     "eaa/toolsearch.py", "TC-39", DA, ""),
    ("G. Công cụ & môi trường", "Kiểm nguồn cài trước khi tới tay người",
     "10 trình quản lý gói chính thống; tải trực tiếp phải HTTPS + miền cho phép + sha256",
     "eaa/toolsearch.py", "TC-39", DA, ""),
    ("G. Công cụ & môi trường", "Đề xuất công cụ vào manifest qua G2",
     "Append + supersede, mang theo approved_by / approved_at",
     "eaa gate approve G2", "TC-39", DA, ""),
    ("G. Công cụ & môi trường", "Ràng buộc phiên bản của pack đè lên đề xuất",
     "pack.yaml ghi avr-gcc >=12.0, mô hình đề xuất 7.3 — lấy theo pack",
     "eaa/toolsearch.py", "TC-39", DA, ""),
    ("G. Công cụ & môi trường", "Khóa môi trường + cảnh báo trôi",
     "env_lock.json; toolchain đổi phiên bản thì cảnh báo trước khi so sánh A/B",
     "eaa/doctor.py", "TC-36", DA, ""),
    ("G. Công cụ & môi trường", "Thẻ công cụ",
     "Cú pháp gọi, cách đọc dòng lỗi, phiên bản đã xác nhận",
     "eaa/doctor.py", "TC-37", DA, ""),
    ("G. Công cụ & môi trường", "Tự cài KHÔNG hỏi người",
     "Kỹ thuật làm được trong một buổi, nhưng FR-ENV-02 và AIS §9.4 cấm",
     "eaa/doctor.py", "TC-34", COY,
     "Cài phần mềm là thay đổi máy kỹ sư. Một agent tự cài im lặng là một agent "
     "có quyền ghi tùy ý lên máy — bỏ chốt này thì hai chốt còn lại mất ý nghĩa"),
    ("G. Công cụ & môi trường", "Tự phát hiện cổng USB / thiết bị cắm vào",
     "Liệt kê cổng nối tiếp, khớp VID/PID với bo dự án khai; không đọc được thì nói thẳng",
     "eaa/serialport.py + eaa ports", "TC-42a (8 test)", DA, ""),

    # -- H. Phiên bản mã ----------------------------------------------------
    ("H. Phiên bản mã", "Ba hạng chất lượng",
     "build-ok < sim-verified < hw-verified; hạng cao đòi bằng chứng tương ứng",
     "eaa/versions.py", "TC-30 (26 test)", DA, ""),
    ("H. Phiên bản mã", "known_good.lock chỉ cập nhật tại G4",
     "Phong hạng hw-verified đòi quyết định G4 VÀ số đo thật",
     "eaa/versions.py", "TC-30", DA, ""),
    ("H. Phiên bản mã", "Quay lui về bản known-good",
     "Rollback không làm mất bản known-good đang giữ",
     "eaa rollback", "TC-30", DA, ""),
    ("H. Phiên bản mã", "Commit truy vết đầy đủ (NFR-07)",
     "Mỗi commit mang băm prompt, model, phiên bản ràng buộc, danh sách chunk",
     "eaa/vcs.py", "TC-01", DA, ""),
    ("H. Phiên bản mã", "Kho phẩm xuất",
     "list / get / regen; gửi lại có kiểm băm để biết bản gửi có bị đổi không",
     "eaa docs", "TC-32 (33 test)", DA, ""),

    # -- I. Tương tác người dùng -------------------------------------------
    ("I. Tương tác", "17 lệnh CLI phủ 10 use case",
     "init, plan, gen, gate, sim, doctor, docs, tune, rollback, diagnose...",
     "eaa/cli.py", "test_cli_e2e.py", DA, ""),
    ("I. Tương tác", "Hồ sơ gate đủ để quyết định",
     "Tóm tắt + chi tiết + băm nội dung; G4 nêu tiêu chí trước, số đo sau",
     "eaa/gates.py", "TC-01, TC-28", DA, ""),
    ("I. Tương tác", "Từ chối phải có lý do",
     "GateDecision đòi tên người, và đòi lý do khi từ chối",
     "eaa/gates.py", "TC-28", DA, ""),
    ("I. Tương tác", "Trình NHIỀU phương án để người chọn",
     "Hiện gate chỉ nhị phân duyệt/từ chối — không có 'ba cách làm, chọn một'",
     "—", "—", CHUA,
     "Cần GatePayload dạng nhiều lựa chọn + GateDecision ghi phương án đã chọn; "
     "đây là thứ gần nhất với điều bạn vừa nêu"),
    ("I. Tương tác", "Agent tự giải thích 'vì sao chọn cách này'",
     "Kèm lập luận thiết kế vào hồ sơ gate, không chỉ kèm mã",
     "—", "—", CHUA,
     "Phụ thuộc mục trên; cùng một lượt làm thì gọn hơn"),
    ("I. Tương tác", "Giao diện hội thoại / TUI",
     "Hiện là CLI từng lệnh rời",
     "—", "—", CHUA,
     "Không chặn gì về kỹ thuật; là tiện dụng, nên xếp sau các mắt xích mạch thật"),

    # -- J. Chẩn đoán & mạch thật -------------------------------------------
    ("J. Mạch thật & chẩn đoán", "Chẩn đoán hai kênh",
     "Giao của telemetry máy và quan sát người; thiếu một kênh thì TỪ CHỐI kết luận",
     "eaa/diagnostics.py", "TC-27 (33 test)", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Bộ kịch bản chẩn đoán DS-01..06",
     "Khai báo bằng YAML ở tầng dự án, engine không biết nội dung",
     "projects/*/diagnostics.yaml", "TC-27", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Checklist an toàn trước kịch bản gây chuyển động",
     "Kịch bản làm mạch chuyển động đòi xác nhận đủ checklist",
     "eaa/diagnostics.py", "TC-27", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Biên dịch từng module rồi liên kết riêng",
     "compile dùng -c sinh tệp đối tượng; link và hex là hai năng lực riêng của pack",
     "eaa/tools/compile.py, packs/avr/pack.yaml", "TC-40 (19 test)", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Ráp ảnh nạp được (.elf → .hex)",
     "LinkGate gộp tệp đối tượng thành ELF rồi đổi sang định dạng nạp được",
     "eaa/tools/compile.py", "TC-40c", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Đo kích thước nói rõ đang đo tầm nào",
     "size_scope phân biệt chiếm dụng của một module lẻ với của cả firmware",
     "eaa/tools/compile.py", "TC-40d", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Ngưỡng bộ nhớ đo trên CẢ firmware",
     "flash_pct_max lần đầu áp lên thứ sẽ nạp xuống mạch, không lên module lẻ",
     "eaa/firmware.py", "TC-41e", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Nạp firmware xuống mạch qua USB",
     "eaa flash gọi năng lực flash của pack; bốn phép kiểm rồi mới hỏi người",
     "eaa/flash.py + eaa flash", "TC-42 (30 test)", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Bốn phép kiểm trước khi nạp",
     "Có ảnh · kho mã sạch · ảnh mới hơn nguồn · người xác nhận — đều là 'không', không phải cảnh báo",
     "eaa/flash.py", "TC-42b, TC-42c", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Nhật ký nạp append-only",
     "Commit nào, ảnh nào (kèm băm), cổng nào, ai, lúc nào — ghi cả lần trượt",
     "eaa flash --history", "TC-42d", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Engine không đoán cổng để nạp",
     "Nhận ra đúng một cổng thì tự chọn; mơ hồ thì dừng và đòi --port",
     "eaa/cli.py", "TC-42e", DA, ""),
    ("J. Mạch thật & chẩn đoán", "Đọc telemetry UART thật",
     "Hiện --telemetry đọc từ TỆP, không đọc từ cổng nối tiếp",
     "eaa diagnose --telemetry", "—", PHAN,
     "Cần bộ đọc serial (pyserial), khung tin có checksum + nhãn thời gian, "
     "và hạn thời gian chờ để không treo phiên"),
    ("J. Mạch thật & chẩn đoán", "Sinh firmware chẩn đoán từ mẫu",
     "diagnostics.yaml đã có trường firmware_template nhưng chưa nơi nào dùng",
     "eaa/diagnostics.py:156", "—", CHUA,
     "Mỗi kịch bản DS-xx cần một firmware nhỏ tự in số đo ra UART"),
    ("J. Mạch thật & chẩn đoán", "Chốt vòng: số đo thật → G4 → phong hạng",
     "Đường ống đã có ở hai đầu (diagnose, tune, versions) nhưng chưa nối liền",
     "eaa tune", "TC-30", PHAN,
     "Hiện phải nhập số đo bằng tay; nối được UART thì vòng này tự khép"),
    ("J. Mạch thật & chẩn đoán", "Debug sâu qua debugWIRE / JTAG / SWD",
     "Đặt điểm dừng, đọc thanh ghi lúc chạy",
     "—", "—", CHUA,
     "Ngoài phạm vi đề án; UART + nạp lại là đủ cho vòng chẩn đoán hai kênh"),
]

# --------------------------------------------------------------------------
# Lộ trình nối mạch thật — thứ tự có ý nghĩa, mỗi bước mở khóa bước sau
# --------------------------------------------------------------------------

LO_TRINH: list[tuple[str, str, str, str, str]] = [
    ("1 ✔", "Tách biên dịch và liên kết — XONG",
     "compile dùng -c cho từng tệp nguồn; link gộp tệp đối tượng + main() thành "
     ".elf; hex đổi sang định dạng nạp được. TC-40, 19 test",
     "Chưa có bước này thì KHÔNG CÓ TỆP ĐỂ NẠP — mọi bước sau vô nghĩa",
     "packs/avr/pack.yaml, eaa/tools/compile.py, eaa/platform.py"),
    ("2 ✔", "Ráp firmware hoàn chỉnh — XONG",
     "Khuôn vòng lặp chính ở pack (bộ định thời hợp tác); firmware.yaml khai "
     "module nào chạy mỗi bao nhiêu ms; `eaa build` dịch, liên kết, ra .hex. TC-41",
     "Biến các module rời thành một chương trình chạy được trên chip",
     "packs/avr/templates/, eaa/firmware.py, eaa/cli.py"),
    ("3 ✔", "Liệt kê cổng USB — XONG",
     "eaa ports; khớp VID/PID với bo khai ở hardware_profile.yaml; thiếu pyserial "
     "thì nói thẳng là không đọc được VID/PID. TC-42a",
     "Agent trả lời được 'bạn đang cắm mạch nào vào cổng nào'",
     "eaa/serialport.py"),
    ("4 ✔", "Lệnh nạp firmware — XONG",
     "eaa flash: bốn phép kiểm (có ảnh · kho sạch · ảnh mới hơn nguồn · người xác "
     "nhận) rồi mới nạp; nhật ký append-only ghi cả lần trượt. TC-42",
     "Đây là lần đầu Agent chạm vào phần cứng thật",
     "eaa/flash.py, eaa/cli.py"),
    ("5", "Bộ đọc telemetry UART",
     "Đọc cổng nối tiếp theo khung tin có checksum + nhãn thời gian; có hạn chờ; "
     "ghi nguyên văn vào tệp để tái lập lại được",
     "Kênh máy của chẩn đoán hai kênh chuyển từ 'đọc tệp' sang 'đọc mạch'",
     "eaa/telemetry.py (mới), phụ thuộc pyserial"),
    ("6", "Sinh firmware chẩn đoán",
     "Dùng firmware_template của từng kịch bản DS-xx để sinh firmware nhỏ tự in số đo",
     "Mỗi kịch bản chẩn đoán tự chạy được thay vì cần người viết mã đo",
     "eaa/diagnostics.py"),
    ("7", "Khép vòng số đo → G4",
     "Số đo từ UART chảy thẳng vào eaa tune; G4 duyệt thì phong hạng hw-verified",
     "Vòng đời ba hạng chất lượng khép kín, không còn nhập tay",
     "eaa/versions.py, eaa/cli.py"),
    ("8", "Gate nhiều phương án",
     "GatePayload trình N cách làm kèm đánh đổi; GateDecision ghi phương án đã chọn "
     "và lý do; phương án bị loại vẫn lưu để tra lại",
     "Đúng điều bạn nêu: 'tương tác với người dùng chọn giải pháp phù hợp'",
     "eaa/gates.py, eaa/cli.py"),
]

# --------------------------------------------------------------------------
# Kiểu dáng
# --------------------------------------------------------------------------

MAU = {
    DA: "C6EFCE",
    PHAN: "FFEB9C",
    CHUA: "FFC7CE",
    COY: "D9E1F2",
}
MAU_CHU = {
    DA: "006100",
    PHAN: "9C5700",
    CHUA: "9C0006",
    COY: "1F4E79",
}

DAM = Font(bold=True)
TRANG_DAM = Font(bold=True, color="FFFFFF")
NEN_TIEU_DE = PatternFill("solid", fgColor="2F5597")
VIEN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
TREN_TRAI = Alignment(vertical="top", wrap_text=True)


def _tieu_de(ws, tieu_de: list[str], do_rong: list[int]) -> None:
    ws.append(tieu_de)
    for i, rong in enumerate(do_rong, 1):
        ws.column_dimensions[get_column_letter(i)].width = rong
    for o in ws[1]:
        o.font = TRANG_DAM
        o.fill = NEN_TIEU_DE
        o.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        o.border = VIEN
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"


def _to_dep(ws, cot_trang_thai: int | None = None) -> None:
    for hang in ws.iter_rows(min_row=2):
        for o in hang:
            o.alignment = TREN_TRAI
            o.border = VIEN
        if cot_trang_thai is not None:
            o_tt = hang[cot_trang_thai - 1]
            if o_tt.value in MAU:
                o_tt.fill = PatternFill("solid", fgColor=MAU[o_tt.value])
                o_tt.font = Font(bold=True, color=MAU_CHU[o_tt.value])
                o_tt.alignment = Alignment(
                    vertical="center", horizontal="center", wrap_text=True
                )


def dung_bang(dich: Path) -> Path:
    wb = Workbook()

    # ---- Sheet 1: Tổng quan ------------------------------------------------
    ws = wb.active
    ws.title = "Tổng quan"

    nhom = sorted({t[0] for t in TINH_NANG})
    ws.append(["Embedded AIDD Agent — thống kê tính năng"])
    ws["A1"].font = Font(bold=True, size=16, color="2F5597")
    ws.append([f"Vũ Trí Công · đề án Thạc sĩ Kỹ thuật, PTIT · cập nhật {_hom_nay()}"])
    ws["A2"].font = Font(italic=True, color="7F7F7F")
    ws.append([])

    ws.append(["Nhóm", "Tổng", DA, PHAN, CHUA, COY, "% đã làm"])
    for o in ws[4]:
        o.font = TRANG_DAM
        o.fill = NEN_TIEU_DE
        o.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        o.border = VIEN

    for ten in nhom:
        hang = [t for t in TINH_NANG if t[0] == ten]
        d = sum(1 for t in hang if t[5] == DA)
        p = sum(1 for t in hang if t[5] == PHAN)
        c = sum(1 for t in hang if t[5] == CHUA)
        k = sum(1 for t in hang if t[5] == COY)
        # Mục CỐ Ý KHÔNG LÀM không tính vào mẫu số: nó không phải việc còn nợ.
        mau_so = len(hang) - k
        ws.append([ten, len(hang), d, p, c, k, (d / mau_so) if mau_so else 1.0])

    tong = len(TINH_NANG)
    td = sum(1 for t in TINH_NANG if t[5] == DA)
    tp = sum(1 for t in TINH_NANG if t[5] == PHAN)
    tc = sum(1 for t in TINH_NANG if t[5] == CHUA)
    tk = sum(1 for t in TINH_NANG if t[5] == COY)
    ws.append(["TỔNG CỘNG", tong, td, tp, tc, tk, td / (tong - tk)])

    for i, rong in enumerate([30, 8, 10, 11, 11, 17, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = rong
    for hang in ws.iter_rows(min_row=5, max_row=ws.max_row):
        for o in hang:
            o.border = VIEN
            o.alignment = Alignment(vertical="center", wrap_text=True)
        hang[6].number_format = "0 %"
        for i, tt in enumerate((DA, PHAN, CHUA, COY), start=2):
            hang[i].alignment = Alignment(vertical="center", horizontal="center")
            if hang[i].value:
                hang[i].font = Font(color=MAU_CHU[tt], bold=True)
    for o in ws[ws.max_row]:
        o.font = Font(bold=True)
        o.fill = PatternFill("solid", fgColor="EDEDED")

    ws.append([])
    ws.append(["Số liệu nền"])
    ws[f"A{ws.max_row}"].font = Font(bold=True, size=12, color="2F5597")
    for nhan, gia_tri in [
        ("Test tự động đang xanh", "799"),
        ("Dòng mã engine (eaa/)", "14.792"),
        ("Lệnh CLI", "20"),
        ("Platform Pack", "1 (AVR 8-bit)"),
        ("Mô hình nền", "gemini-3.1-pro-preview (ghim phiên bản)"),
        ("Sai lệch thiết kế đã ghi", "33 mục (SL-01..SL-33)"),
    ]:
        ws.append([nhan, gia_tri])
        ws[f"A{ws.max_row}"].font = DAM

    ws.append([])
    ws.append(["Ý nghĩa bốn trạng thái"])
    ws[f"A{ws.max_row}"].font = Font(bold=True, size=12, color="2F5597")
    for tt, y in [
        (DA, "Có mã, có test, chạy được end-to-end"),
        (PHAN, "Có mã nhưng còn mắt xích thiếu — xem cột 'Còn thiếu gì'"),
        (CHUA, "Chưa có mã"),
        (COY, "Làm được nhưng thiết kế cấm — xem cột 'Còn thiếu gì' để rõ điều khoản"),
    ]:
        ws.append([tt, y])
        o = ws[f"A{ws.max_row}"]
        o.fill = PatternFill("solid", fgColor=MAU[tt])
        o.font = Font(bold=True, color=MAU_CHU[tt])
        o.border = VIEN

    # ---- Sheet 2: Đã làm được ---------------------------------------------
    ws2 = wb.create_sheet("Đã làm được")
    _tieu_de(
        ws2,
        ["#", "Nhóm", "Tính năng", "Làm được gì", "Module / Lệnh", "Bằng chứng"],
        [5, 24, 34, 56, 30, 22],
    )
    for i, t in enumerate([x for x in TINH_NANG if x[5] == DA], 1):
        ws2.append([i, t[0], t[1], t[2], t[3], t[4]])
    _to_dep(ws2)
    ws2.auto_filter.ref = f"A1:F{ws2.max_row}"

    # ---- Sheet 3: Chưa làm được -------------------------------------------
    ws3 = wb.create_sheet("Chưa làm được")
    _tieu_de(
        ws3,
        ["#", "Nhóm", "Tính năng", "Hiện trạng", "Trạng thái", "Còn thiếu gì / vì sao"],
        [5, 24, 32, 46, 16, 62],
    )
    con_lai = [x for x in TINH_NANG if x[5] != DA]
    thu_tu = {PHAN: 0, CHUA: 1, COY: 2}
    con_lai.sort(key=lambda x: (thu_tu[x[5]], x[0]))
    for i, t in enumerate(con_lai, 1):
        ws3.append([i, t[0], t[1], t[2], t[5], t[6]])
    _to_dep(ws3, cot_trang_thai=5)
    ws3.auto_filter.ref = f"A1:F{ws3.max_row}"

    # ---- Sheet 4: Lộ trình -------------------------------------------------
    ws4 = wb.create_sheet("Lộ trình mạch thật")
    ws4.append(["Lộ trình nối Agent với mạch thật qua USB"])
    ws4["A1"].font = Font(bold=True, size=14, color="2F5597")
    ws4.append([
        "Thứ tự có ý nghĩa: mỗi bước mở khóa bước sau. Bước 1 là mắt xích chặn — "
        "chưa tách biên dịch/liên kết thì không có tệp .hex để nạp."
    ])
    ws4["A2"].font = Font(italic=True, color="7F7F7F")
    ws4.append([])
    ws4.append(["Bước", "Việc", "Làm gì cụ thể", "Mở khóa điều gì", "Chạm vào đâu"])
    for o in ws4[4]:
        o.font = TRANG_DAM
        o.fill = NEN_TIEU_DE
        o.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        o.border = VIEN
    for b in LO_TRINH:
        ws4.append(list(b))
    for i, rong in enumerate([7, 30, 62, 46, 34], 1):
        ws4.column_dimensions[get_column_letter(i)].width = rong
    for hang in ws4.iter_rows(min_row=5):
        for o in hang:
            o.alignment = TREN_TRAI
            o.border = VIEN
        hang[0].font = DAM
        hang[1].font = DAM
    ws4.freeze_panes = "A5"

    dich.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dich)
    return dich


def _hom_nay() -> str:
    from datetime import date

    return date.today().isoformat()


if __name__ == "__main__":
    dich = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/EAA_Thong_ke_tinh_nang.xlsx")
    print(f"Đã ghi: {dung_bang(dich)}")
