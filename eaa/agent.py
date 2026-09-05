"""Vòng hội thoại — người nói bằng tiếng Việt, Agent tự chọn và chạy lệnh.

EAA-AIS-05 §2 (lắp ráp ngữ cảnh), ADR-03 (đổi nhà cung cấp không đổi hành vi
điều phối). Xem `docs/SAI_LECH_THIET_KE.md` mục SL-65.

Trước module này, mặt tiếp xúc duy nhất là 35 lệnh rời. Người dùng phải biết
lệnh nào tồn tại và gõ đúng cờ — tức là phải hiểu cấu trúc bên trong trước khi
hỏi được câu đầu tiên. Module này lấp chỗ đó: nói ra điều mình muốn, Agent tự
tìm đường.

Điều KHÔNG được đổi khi thêm hội thoại
---------------------------------------

Toàn bộ giá trị của sản phẩm nằm ở chỗ 5 Human Gate không thể bị vượt. Một
tầng hội thoại là đúng loại thứ có thể phá điều đó một cách êm ái: mô hình
"hiểu" rằng người dùng muốn duyệt, rồi tự gọi ``gate approve``.

Nên ranh giới ở đây được dựng bằng **cấu tạo, không bằng lời dặn**:
:data:`TOOLBOX` — danh mục lệnh Agent được gọi — **không chứa một lệnh DUYỆT
nào**: ``gate approve/reject``, ``flash approve``, ``doctor approve``, ``tool
approve``, ``skill approve``, và cũng không chứa ``tune``, ``rollback``,
``diagnose run``, ``endurance``. Mô hình có muốn gọi cũng không có gì để gọi;
vòng lặp từ chối mọi lệnh ngoài danh mục và nói lại cho mô hình biết vì sao.

Ranh giới nằm ở việc DUYỆT, không ở việc LÀM
---------------------------------------------

``flash``, ``doctor --fix`` và ``tool run`` thì CÓ trong danh mục, và đó là
chủ ý chứ không phải sót. Cả ba đều tự dừng khi chưa có quyết định của người:
``flash`` đòi một bản duyệt neo vào **băm nội dung ảnh**, ``doctor --fix`` chỉ
chạy đúng những lệnh cài đã duyệt, ``tool run`` chỉ chạy công cụ đã ở trạng
thái ``approved``. Người đã duyệt rồi thì việc bấm nút là việc máy làm được,
và bắt người gõ lại lệnh ấy không thêm một lớp an toàn nào — nó chỉ thêm một
bước gõ.

Cách chia này còn giữ được một tính chất mà cách chia cũ không có: nó **không
phụ thuộc vào việc liệt kê đủ**. Danh sách lệnh nguy hiểm sẽ dài thêm mỗi lần
có tính năng mới, và một danh sách phải nhớ cập nhật là một danh sách sẽ sót.
Danh sách lệnh DUYỆT thì đóng: mỗi cổng đúng một lệnh, và thêm cổng mới là
thêm một mục người ta không quên được, vì không có nó thì cổng không dùng được.

Prompt cũng dặn điều đó, nhưng lời dặn chỉ là hàng rào thứ hai. Hàng rào thứ
nhất là danh mục, và nó là dữ liệu — đọc được, kiểm được bằng test, đổi được
mà không sửa mã.

"Stateless mỗi lần gọi" có còn đúng không
------------------------------------------

MDD chốt: *không trí nhớ hội thoại — stateless call + Project State.* Vòng lặp
này giữ đúng tinh thần ấy. Mỗi lượt vẫn là MỘT lời gọi độc lập; cái được gọi
là "trí nhớ" do engine dựng lại từ Project State cộng một bản ghi phiên **có
giới hạn**, đúng cách Composer vẫn lắp ngữ cảnh cho vòng sinh mã.

Khác biệt so với thiết kế gốc: bản ghi phiên là một lớp ngữ cảnh mới. Nó được
ghi ra ``chat_log.jsonl`` nên phiên nào cũng truy lại được, và nó bị cắt theo
ngân sách token như mọi lớp khác. Không có trạng thái nào nằm ở phía nhà cung
cấp mô hình.

Vì sao giao thức là JSON chứ không phải function-calling
---------------------------------------------------------

Adapter Gemini hiện gửi một lượt ``contents`` duy nhất và trả về văn bản.
Dựng vòng lặp trên ``complete()`` với một khối JSON hành động khiến nó chạy
được với **mọi** adapter theo interface ``LLMClient`` — kể cả MockLLM và bộ
phát lại. Đó đúng là điều ADR-03 đòi hỏi: đổi nhà cung cấp không đổi hành vi
điều phối.
"""

from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "AgentError",
    "Tool",
    "TOOLBOX",
    "NGOAI_DANH_MUC",
    "Step",
    "ChatResult",
    "AgentLoop",
    "CHAT_LOG",
    "MAX_STEPS",
]

#: Bản ghi phiên hội thoại, cạnh Project State.
CHAT_LOG = "chat_log.jsonl"

#: Trần số bước trong MỘT lượt hỏi. Cùng tinh thần với vòng tự sửa ≤ 3: một
#: vòng lặp không có trần là một vòng lặp sẽ quay cho tới lúc hết tiền.
MAX_STEPS = 8

#: Cắt đầu ra của mỗi lệnh trước khi đưa lại cho mô hình. Một báo cáo dài
#: nghìn dòng sẽ nuốt hết ngân sách ngữ cảnh và đẩy phần hỏi ra ngoài.
MAX_OUTPUT_CHARS = 3200

#: Ngân sách RIÊNG của vòng hội thoại — không mượn của vòng sinh mã.
#:
#: ``LAYER_BUDGETS`` trong ``eaa/llm/base.py`` chia 8.000 token theo Hình 1 của
#: AIS §2, và cách chia ấy dành cho prompt SINH MÃ: chunk datasheet, hợp đồng
#: giao diện, quy tắc lỗi, phần dự phòng cho vòng vá. Prompt hội thoại có hình
#: dạng khác hẳn — phần lớn ngân sách của nó là DANH MỤC CÔNG CỤ, thứ không tồn
#: tại trong prompt sinh mã.
#:
#: Nên hai bên khai ngân sách riêng. Mượn của nhau thì mỗi lần thêm một công cụ
#: lại phải nới một con số thuộc về bản thiết kế của việc khác — và đó là cách
#: một bảng ngân sách có căn cứ biến dần thành một bảng số ai cũng sửa được.
#: Trần TỔNG vẫn là 8.000 và vẫn kiểm trước khi gọi (TC-16).
#: Dời 100 token từ lớp VAI TRÒ sang lớp DANH MỤC ngày 04/09/2026 (SL-172), khi
#: `knowledge stale` làm danh mục chạm 2.810/2.800. Dời chứ không NỚI: tổng ba
#: lớp giữ nguyên 7.600, nên trần 8.000 không bị đụng tới và không lớp nào của
#: prompt sinh mã bị lấn.
#:
#: Căn cứ để dời là một phép đo, không phải một cảm giác: lớp vai trò dùng thật
#: 1.018 token trên 1.400 — dư 382. Sau khi dời nó còn dư 282, vẫn rộng hơn
#: khoảng lớp danh mục vừa cần.
NGAN_SACH_VAI_TRO = 1_300
NGAN_SACH_DANH_MUC = 2_900
#: Ngân sách lớp ràng buộc cứng trong prompt hội thoại. Lớp này BẮT BUỘC —
#: cắt nó là bỏ mất luật, và bỏ luật im lặng thì câu trả lời vẫn trông đúng.
NGAN_SACH_RANG_BUOC = 900
#: Ngân sách lớp trạng thái dự án. Nới từ 400 lên khi thêm dòng phần cứng
#: (SL-112): mô hình phải biết nó đang viết cho chip nào, nếu không nó ĐOÁN.
NGAN_SACH_TRANG_THAI = 700

#: Ngân sách cho đầu ra các lệnh vừa chạy.
#:
#: Nới lên từ 2.600 khi Agent đọc được PDF: nội dung một trang tài liệu dài hơn
#: hẳn đầu ra của một lệnh trạng thái, và cắt nó xuống vừa ngân sách cũ thì
#: đúng phần Agent cần đọc bị mất. Tổng vẫn dưới trần 8.000.
NGAN_SACH_QUAN_SAT = 3_400


class AgentError(Exception):
    """Vòng hội thoại không chạy được."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Danh mục công cụ — HÀNG RÀO THỨ NHẤT
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    """Một lệnh Agent được phép tự gọi."""

    argv: tuple[str, ...]
    purpose: str
    #: Mô tả tham số tự do, nếu lệnh nhận thêm. Rỗng = không nhận gì thêm.
    takes: str = ""
    #: Lệnh có ghi ra tệp không. Chỉ để BÁO CHO NGƯỜI biết, không để nới quyền.
    writes: bool = False

    @property
    def name(self) -> str:
        return " ".join(self.argv)

    def render(self) -> str:
        dau = "✎" if self.writes else " "
        dong = f"  {dau} {self.name}"
        if self.takes:
            dong += f" <{self.takes}>"
        return f"{dong}\n      {self.purpose}"


#: Lệnh Agent ĐƯỢC tự gọi trong hội thoại.
#:
#: Đọc danh mục này là đọc chính xác quyền hạn của Agent — không cần đọc mã.
#: Thêm một lệnh vào đây là một quyết định về quyền, nên nó phải là một thay
#: đổi nhìn thấy được trong lịch sử Git, không phải một nhánh rẽ trong hàm.
TOOLBOX: tuple[Tool, ...] = (
    # -- chỉ đọc ------------------------------------------------------------
    Tool(("status",), "Dự án đang ở pha nào, gate nào chờ, bước kế tiếp là gì"),
    Tool(
        ("capabilities",),
        "Chính bạn làm được gì: lệnh nào có, năng lực nền tảng nào pack khai, "
        "công cụ ngoài nào đang thiếu. Gọi cái này khi người dùng hỏi bạn có "
        "làm được việc gì đó không",
    ),
    Tool(("policy",), "Bảng phân quyền và máy trạng thái 5 pha"),
    Tool(("packs",), "Platform Pack nào đang cài"),
    # 'doctor' không cờ là CHỈ ĐỌC — quét máy, không đổi gì. Trước đây cả lệnh
    # bị chặn, kể cả chế độ đọc, trong khi chính lời giải thích đi kèm lại khai
    # là "tôi quét và báo được". Mã lệch với lời chính nó khai.
    Tool(("doctor",), "Công cụ nào thiếu, công cụ thiếu chặn cổng nào"),
    # Chỉ ĐỌC danh mục. Agent không đổi được model của chính nó — việc ấy là
    # của người dùng, qua cờ --model hoặc eaa init. Đây chỉ để nó trả lời được
    # câu "có những model nào" thay vì đoán tên.
    Tool(("models",), "Danh mục mô hình đã kiểm; người dùng chọn bằng cờ --model"),
    Tool(("plan", "list"), "Backlog module và trạng thái từng module"),
    Tool(("ledger", "list"), "Nhật ký lỗi ảo giác đã gặp"),
    Tool(("safety", "show"), "Phân tích hỏng hóc và chế độ an toàn, kèm chỗ còn hở"),
    Tool(("budget", "show"), "Ngân sách flash/RAM chia theo module"),
    Tool(("budget", "tokens"), "Token và chi phí đã tiêu theo module"),
    Tool(("sources", "need"), "Danh sách tài liệu cần, nêu đích danh"),
    Tool(("sources", "pages"), "Phần tài liệu còn phải trích", takes="mã module"),
    Tool(("errata", "show"), "Lỗi chip đã công bố và module nào chạm vào"),
    Tool(("datasheet", "list"), "Trích đoạn tài liệu trong kho và trạng thái duyệt"),
    # Chỉ nhánh `stale` — nó CHỈ ĐỌC và trả lời "mã nào dựa trên trích đoạn
    # này". Hai nhánh `supersede`/`deprecate` KHÔNG có ở đây: chúng đổi kho tri
    # thức và đòi quyết định G2, cùng hạng với `datasheet add`.
    Tool(
        ("knowledge", "stale"),
        "Module nào dựa trên một trích đoạn tài liệu",
        takes="mã trích đoạn",
    ),
    Tool(("measured", "list"), "Số đo trên bo: đã chốt và còn chờ"),
    # Agent ĐỀ XUẤT số đo được — nó là bên chạy chẩn đoán và đọc telemetry, nên
    # bắt người chép tay lại con số máy vừa đọc là bỏ phí đúng chỗ máy làm tốt.
    # Bản đề xuất KHÔNG vào prompt; `measured approve` mới vào, và lệnh ấy là
    # lệnh DUYỆT nên nó không có trong danh mục này (cùng luật SL-164).
    Tool(
        ("measured", "add"),
        "Đề xuất một số đo trên bo (chưa vào prompt, chờ người chốt)",
        takes="tên, giá trị, --unit, --source",
        writes=True,
    ),
    Tool(("docs", "list"), "Phẩm xuất đã đăng ký"),
    Tool(("design", "list"), "Khuôn mẫu tài liệu thiết kế và định dạng xuất được"),
    # Dựng tài liệu chỉ đọc hồ sơ dự án rồi ghi ra artifacts/ — không đụng gate,
    # không đụng thiết bị, và không hỏi mô hình chữ nào. Cùng hạng với 'report'.
    Tool(("design", "gen"), "Dựng URD/SRS/SDD/danh sách chức năng/luồng nghiệp vụ "
                            "từ hồ sơ dự án", takes="loại tài liệu [--format md|docx|xlsx|pptx|pdf]"),
    Tool(("diagnose", "list"), "Thư viện kịch bản chẩn đoán của dự án"),
    Tool(("diagnose", "select"), "Chọn kịch bản từ triệu chứng", takes="mô tả triệu chứng"),
    Tool(("diagnose", "measure"), "Hướng dẫn đo bằng dụng cụ", takes="mã kịch bản"),
    Tool(("report", "kpi"), "Số liệu định lượng của các lượt chạy"),
    Tool(("report", "review"), "Khâu nào hay hỏng nhất và nên sửa gì"),
    Tool(("report", "retrieval"), "Chất lượng truy xuất tri thức trên bộ chuẩn"),
    Tool(("report", "versions"), "Phiên bản mã theo hạng chất lượng"),
    Tool(("deviations",), "Chỗ nào mã và tài liệu kể hai câu chuyện khác nhau"),
    Tool(("gate", "show"), "Xem hồ sơ đang chờ quyết định tại một gate", takes="mã gate"),
    Tool(("field",), "Phân tích một ca sự cố hiện trường", takes="mô tả triệu chứng"),
    Tool(("handover", "doc"), "Tài liệu vận hành, kèm mục điều hệ thống KHÔNG làm được"),
    Tool(("handover", "rollout"), "Kế hoạch cập nhật thiết bị đã triển khai"),
    Tool(("sim", "run"), "Chạy mô phỏng, gồm cả kịch bản tiêm lỗi", takes="--scenario <tên>"),
    # Kho tri thức của dự án, đọc được bằng MỘT CÂU HỎI. Trước mục này, đường
    # duy nhất tới trích đoạn đã duyệt là đường sinh mã — nên ở hội thoại, thứ
    # đã qua G2 nằm trên đĩa mà không có lệnh nào lấy ra được.
    Tool(
        ("recall",),
        "TRA KHO TRI THỨC ĐÃ DUYỆT của dự án bằng một câu hỏi. Gọi TRƯỚC "
        "`research`. Nó nêu cả chunk đang chờ G2, nhưng không tính vào kết quả",
        takes="câu hỏi [--top-k N]",
    ),
    Tool(
        ("survey",),
        "Khảo sát một kho nén hồ sơ dự án: kiểm kê, phân loại, rút dữ kiện từ mã "
        "nguồn. Thêm --extract để giải ra đĩa.\n"
        "      Bản khảo sát tổng BỊ CẮT BỚT, nên sau khi giải nén hãy soi tiếp:\n"
        "        --files '*.pdf'   liệt kê tệp khớp mẫu trong kho\n"
        "        --read <tệp>      ĐỌC một tệp, kể cả PDF\n"
        "      Hỏi về nội dung một tài liệu thì phải --read nó ra đã, đừng trả "
        "lời từ tài liệu khác",
        takes="đường dẫn .zip [--extract] | --files <mẫu> | --read <tệp>",
    ),
    # -- có ghi ra tệp, nhưng KHÔNG quyết định thay người --------------------
    # `resolve` nằm ở NHÓM CÓ GHI, không nhóm chỉ đọc: bậc 3 của nó dựng chunk
    # ĐỀ XUẤT trên đĩa và bộ đếm vòng tìm sống qua phiên. Xếp nó vào nhóm chỉ
    # đọc là khai với mô hình một điều không đúng về chính nó.
    Tool(("resolve",), "Tri thức còn thiếu của một module, thang ba bậc: kho "
                       "→ hỏi người → web. `--web` bật bậc 3: tìm, TẢI trang "
                       "nhà sản xuất, trích thành chunk ĐỀ XUẤT chờ G2",
         takes="mã module [--web]", writes=True),
    Tool(("plan", "add"), "Khai một module vào backlog", takes="mã module --uses a,b", writes=True),
    Tool(("budget", "propose"), "Đề xuất cách chia ngân sách theo backlog", writes=True),
    Tool(("propose", "scope"), "Đề xuất phạm vi và cái KHÔNG làm", writes=True),
    Tool(("propose", "constraints"), "Đề xuất ràng buộc, mỗi cái kèm hệ quả"),
    Tool(("propose", "acceptance"), "Đề xuất tiêu chí nghiệm thu đo được"),
    Tool(("propose", "pinmap"), "Đề xuất bảng chân, kèm kiểm chức năng thay thế"),
    Tool(("propose", "plant"), "Đề xuất mô hình đối tượng", takes="--plant <đối tượng>"),
    Tool(("interface",), "Sinh hợp đồng gọi của module", takes="mã module", writes=True),
    Tool(("errata", "lookup"), "Tra errata cho đúng rev silicon", takes="--rev <rev>", writes=True),
    Tool(("handover", "swap"), "So linh kiện thay thế", takes="--old X --new Y"),
    Tool(("safety", "propose"), "Dựng bản phân tích hỏng hóc và chế độ an toàn", writes=True),

    # -- năng lực độc lập: nhìn ra ngoài và nhớ lại -------------------------
    #
    # Nhóm này không gắn với dự án nào. Nó là thứ trả lời được câu hỏi người ta
    # hỏi TRƯỚC khi có dự án — "máy này thiếu gì", "cái này cài thế nào", "lần
    # trước lỗi này sửa sao".
    Tool(
        ("environ",),
        "Máy đang chạy là máy gì: hệ điều hành, kiến trúc CPU, quyền, trình cài "
        "gói nào có, và MẠNG RA NGOÀI CÓ THÔNG KHÔNG (thử thật). Gọi cái này "
        "trước khi hứa sẽ đi tra cứu hay đi cài gì",
    ),
    Tool(
        ("research",),
        "ĐI TÌM trên web rồi ĐỌC trang thật. Trả về nội dung tải về kèm địa chỉ "
        "và hạng tin cậy — KHÔNG phải thứ bạn nhớ được. Dùng khi cần tài liệu "
        "kỹ thuật, cách cài một công cụ, hay lời giải cho một thông báo lỗi",
        takes="câu cần tra [--site microchip.com] [--official-only]",
    ),
    Tool(
        ("read",),
        "Tải MỘT trang web đã biết địa chỉ và đọc nội dung chữ của nó",
        takes="URL",
    ),
    Tool(
        ("memory", "list"),
        "Bộ nhớ liên dự án: môi trường đã dò, công cụ đã cài, bài học đã rút. "
        "Tra đây trước khi hỏi lại người dùng thứ họ đã nói lần trước",
    ),
    Tool(
        ("playbook", "lookup"),
        "Tra sổ tay lỗi: lỗi giống thế này lần trước sửa bằng cách nào. "
        "LUÔN tra đây TRƯỚC khi ra web — rẻ hơn và sát hoàn cảnh hơn",
        takes="nguyên văn thông báo lỗi",
    ),
    Tool(("playbook", "list"), "Toàn bộ sổ tay lỗi, kèm tỉ lệ trúng của từng cách sửa"),
    Tool(("tool", "list"), "Công cụ do chính bạn viết ra: cái nào đã được duyệt, cái nào chưa"),
    Tool(
        ("memory", "add"),
        "Ghi một điều đáng nhớ sang dự án sau. Khai rõ phạm vi",
        takes="<chủ thể> <nội dung> [--scope 'mcu:<họ>']", writes=True,
    ),
    Tool(
        ("playbook", "record"),
        "Ghi lại một cặp (lỗi → cách sửa đã hiệu quả) để lần sau tra được",
        takes="<lỗi> <cách sửa> [--source URL]", writes=True,
    ),
    Tool(
        ("tool", "propose"),
        "Tự viết một công cụ mới cho chính bạn khi việc cần làm không có lệnh "
        "nào sẵn. Nó ra ở trạng thái ĐỀ XUẤT — chưa chạy được",
        takes="mô tả việc cần làm", writes=True,
    ),
    Tool(
        ("tool", "verify"),
        "Cho một công cụ vừa viết đi qua ba cổng: cấu tạo, an toàn, chạy thử",
        takes="tên công cụ", writes=True,
    ),
    Tool(
        ("tool", "run"),
        "Chạy một công cụ ĐÃ ĐƯỢC NGƯỜI DUYỆT (xem 'tool list')",
        takes="tên công cụ --args '{...}'", writes=True,
    ),
    # Cùng hình dạng với 'tool run': người duyệt bằng 'doctor approve', tôi
    # chạy. Không có quyết định nào khớp đúng dãy đối số sắp chạy thì lệnh này
    # dừng và nêu đích danh lệnh duyệt — nó không cài được gì tự mình.
    # Cùng hình dạng 'tool run' và 'doctor --fix': người duyệt bằng
    # 'flash approve', tôi nạp. Không có chữ ký khớp đúng ảnh sắp nạp thì lệnh
    # này dừng và nêu đích danh lệnh duyệt.
    Tool(
        ("flash",),
        "Nạp một ảnh firmware ĐÃ ĐƯỢC NGƯỜI DUYỆT bằng 'eaa flash approve'. "
        "Chưa duyệt thì lệnh này dừng và nói cần duyệt gì",
        takes="--image <ảnh>", writes=True,
    ),
    Tool(
        ("doctor", "--fix"),
        "Cài công cụ thiếu — CHỈ những lệnh người dùng đã duyệt bằng "
        "'eaa doctor approve'. Chưa duyệt thì lệnh này dừng và nói cần duyệt gì",
        writes=True,
    ),
    Tool(
        ("scratch",),
        "Dựng chỗ làm nháp khi người dùng chỉ muốn hỏi nhanh một việc mà chưa "
        "có hồ sơ dự án nào. Cổng và gate vẫn chạy đủ",
        takes="[--name X]", writes=True,
    ),

    # -- nhìn cả quãng đường, và gộp việc hay lặp ---------------------------
    Tool(
        ("focus",),
        "CÒN GÌ CHẶN giữa đây và việc sinh mã cho một module — CẢ quãng đường "
        "một lần, kèm ai làm được chặng nào. Gọi cái này khi người dùng hỏi "
        "'sao chưa làm được' hoặc 'giờ tôi phải làm gì'",
        takes="mã module",
    ),
    Tool(("skill", "list"), "Kỹ năng đã đặt tên: chuỗi việc gọi lại được bằng một câu"),
    Tool(
        ("skill", "mine"),
        "Tìm chuỗi việc bạn ĐÃ lặp trong nhật ký hội thoại, để rút thành kỹ năng",
        takes="[--save <tên>]",
    ),
    Tool(
        ("skill", "run"),
        "Chạy một kỹ năng ĐÃ ĐƯỢC NGƯỜI DUYỆT (xem 'skill list')",
        takes="tên kỹ năng [--args '{...}']", writes=True,
    ),
    Tool(
        ("skill", "verify"),
        "Cho một kỹ năng đi qua ba cổng: quyền, tham số, chạy khô",
        takes="tên kỹ năng", writes=True,
    ),
    Tool(
        ("suggest",),
        "Tự nhìn lại nhật ký: việc gì đang tốn công nhất, nên viết công cụ mới "
        "hay rút một kỹ năng. Gọi khi người dùng hỏi 'có gì cải tiến được không'",
    ),
    Tool(
        ("assess",),
        "Một gói phần mềm có đáng cài không: còn ai bảo trì, license gì, tên có "
        "thật hay chỉ gần giống một gói nổi tiếng",
        takes="tên gói [--registry pypi|npm|github]",
    ),
    Tool(
        ("debug", "plan"),
        "Dựng kế hoạch một phiên gỡ lỗi sâu để NGƯỜI thi hành. Tôi không chạy "
        "phiên; tôi dò dụng cụ, rút bước từ kịch bản chẩn đoán, và ghi vết",
        takes="--scenario DS-0x",
    ),
    Tool(("debug", "log"), "Các phiên gỡ lỗi sâu đã ghi: ai làm, thấy gì, kết luận gì"),
    Tool(
        ("tool", "doc"),
        "Sinh tài liệu ngắn cho một công cụ tự sinh: tham số, cách gọi, đã kiểm "
        "những gì, và số đo sau khi dùng thật",
        takes="tên công cụ",
    ),
    Tool(
        ("tool", "rollback"),
        "Quay một công cụ về bản đã duyệt gần nhất, khi bản mới hỏng. Bản quay "
        "về phải đi lại ba cổng",
        takes="tên công cụ", writes=True,
    ),
)

#: Lệnh Agent KHÔNG BAO GIỜ được tự gọi, kèm lý do nói cho người nghe.
#:
#: Danh sách này không phải để kiểm tra — hàng rào thật là "không có trong
#: TOOLBOX". Nó tồn tại để khi mô hình đòi gọi một trong số này, vòng lặp trả
#: lời được câu "vì sao không" thay vì một lời từ chối trống rỗng.
NGOAI_DANH_MUC: dict[str, str] = {
    "gate": (
        "Quyết định tại gate là của con người, và đó là bất biến trung tâm của "
        "cả sản phẩm. Tôi trình được hồ sơ ('gate show'), nhưng bạn là người gõ "
        "'eaa gate approve'."
    ),
    "flash approve": (
        "Duyệt một ảnh để nạp là quyết định chạm vào thiết bị thật, nên chỉ bạn "
        "gõ được 'eaa flash approve --image <ảnh>'. Sau khi bạn duyệt, tôi nạp "
        "đúng ảnh ấy — không ảnh nào khác, vì quyết định của bạn neo vào băm "
        "nội dung của chính nó."
    ),
    "doctor approve": (
        "Duyệt một lệnh cài là quyết định đổi máy của bạn, nên chỉ bạn gõ được "
        "'eaa doctor approve'. Tôi quét và nêu đích danh lệnh cần chạy; sau khi "
        "bạn duyệt, tôi chạy đúng lệnh ấy bằng 'doctor --fix' — không lệnh nào "
        "khác, vì quyết định của bạn neo vào chính dãy đối số đó."
    ),
    "tune": (
        "Phong hạng hw-verified là một khẳng định về phần cứng. Nó chỉ được "
        "đặt bởi người vừa cầm thiết bị và đọc số đo."
    ),
    "rollback": "Quay lui đổi mã đang chạy trên thiết bị — quyết định của bạn.",
    "init": (
        "Khởi tạo dự án và ghim mô hình vào Project State là hai việc đặt điều "
        "kiện cho mọi lượt chạy sau. Tôi liệt kê được danh mục mô hình "
        "('models'), nhưng chọn cái nào là đánh đổi chi phí–chất lượng của "
        "người trả tiền, không phải của tôi — và một model tôi tự đổi làm hai "
        "lần chạy cùng một lệnh không so sánh được với nhau nữa."
    ),
    "endurance": "Lệnh này chiếm cổng nối tiếp và chạy hàng giờ; bạn nên tự bố trí.",
    "build": "Ráp firmware là bước trước khi nạp; bạn chạy để còn kiểm ảnh sinh ra.",
    "skill approve": (
        "Cho phép một kỹ năng được chạy là mở rộng quyền của tôi. Tôi rút được "
        "chuỗi việc ra và cho nó qua ba cổng; bước cuối phải là bạn."
    ),
    "tool approve": (
        "Cho phép một công cụ tự sinh được CHẠY là mở rộng quyền của tôi, không "
        "phải mở rộng việc tôi làm. Tôi viết được nó và cho nó qua ba cổng; "
        "bước cuối phải là bạn."
    ),
    "init": "Khởi tạo dự án là quyết định mở đầu, không nên nằm giữa một câu hỏi.",
    "brief": "Lệnh này hỏi bạn trực tiếp — tôi gọi hộ thì mất đúng phần hỏi.",
    "decide": "Trình phương án để BẠN chọn; tôi gọi hộ thì mất đúng chỗ bạn chọn.",
    "scope-image": "Cần bạn đối chiếu ảnh gốc rồi chốt số đo.",
    "gen": (
        "Vòng sinh mã ghi số liệu vào kpi_log.csv, và những dòng ấy là DỮ LIỆU "
        "THÍ NGHIỆM của Chương 3. Tôi tự khởi động nó sẽ chèn vào bảng số liệu "
        "những lượt chạy mà người làm thí nghiệm không định chạy — nên bạn là "
        "người bấm nút."
    ),
    "telemetry": "Lệnh này chiếm cổng nối tiếp của thiết bị; bạn nên tự cắm và chạy.",
    "ports": "Đọc cổng nối tiếp là việc chạm tới máy của bạn.",
    "datasheet": (
        "Nạp tài liệu vào kho là đưa tri thức mới vào hệ thống. Bạn chọn tệp và "
        "chọn trang — việc chọn trang là việc của kỹ sư (AIS §4.1)."
    ),
    "docs": (
        "Tôi liệt kê được ('docs list'), nhưng 'get'/'regen' tạo phiên bản phẩm "
        "xuất mới; đó là một hành động phát hành."
    ),
}


def _danh_sach_lenh(gia_tri: Any) -> list[str]:
    """Đọc trường ``lenh`` ở cả hai dạng: một lệnh, hoặc nhiều lệnh.

    Mô hình trả về ``["gate","approve","G1"]`` khi có một lệnh, và
    ``[["gate","approve","G1"], ["gate","approve","G2"]]`` khi có nhiều. Chấp
    cả hai thay vì ép một dạng: người hỏi thường cần một chuỗi vài bước, và
    bắt mô hình gói một lệnh vào danh sách lồng chỉ để cho đều là thêm một chỗ
    để nó làm sai.
    """
    if not isinstance(gia_tri, (list, tuple)) or not gia_tri:
        return []
    if all(isinstance(x, (list, tuple)) for x in gia_tri):
        return [" ".join(str(p) for p in lenh) for lenh in gia_tri if lenh]
    return [" ".join(str(p) for p in gia_tri)]


def _lenh_cua_eaa() -> frozenset[str]:
    """Tên các lệnh con của ``eaa``, đọc từ chính bộ phân tích đối số."""
    try:
        from eaa.cli import build_parser

        p = build_parser()
        ten: set[str] = set()
        if getattr(p, "_subparsers", None):
            for hd in p._subparsers._group_actions:
                ten |= set(getattr(hd, "choices", {}) or {})
        if ten:
            return frozenset(ten)
    except Exception:  # noqa: BLE001 - nhập vòng hoặc CLI hỏng
        pass
    return frozenset({t.argv[0] for t in TOOLBOX} | {k.split()[0] for k in NGOAI_DANH_MUC})


def _dong_lenh(lenh: str) -> str:
    """Dựng dòng lệnh gợi ý, gắn tiền tố ``eaa`` CHỈ khi đúng là lệnh của eaa.

    Gắn mù quáng thì một gợi ý hoàn toàn đúng — một lệnh cài của trình quản lý
    gói — bị in ra thành ``eaa brew install …``, một lệnh không tồn tại. Người
    dùng gõ theo, nhận lỗi, và mất lòng tin vào cả câu trả lời đúng nằm ngay
    phía trên nó.
    """
    phan = lenh.strip().split()
    if not phan:
        return ""
    if phan[0] == "eaa":
        return lenh.strip()
    return f"eaa {lenh.strip()}" if phan[0] in _lenh_cua_eaa() else lenh.strip()


def _cat_vua(
    van_ban: str, tran_token: int, dem: Callable[[str], int] | None = None
) -> str:
    """Cắt một chuỗi cho vừa số token, bằng CHÍNH bộ ước lượng.

    Không quy đổi "mấy ký tự một token": bộ ước lượng của hệ này đếm theo TỪ,
    nên mọi hằng số quy đổi đều sai — và sai theo hướng vượt trần, tức là hỏng
    đúng thứ phép cắt sinh ra để tránh. Chia đôi dần thì đúng với bất kỳ công
    thức ước lượng nào, kể cả khi nó đổi.
    """
    from eaa.llm.base import estimate_tokens

    do = dem or estimate_tokens
    if tran_token <= 0:
        return ""
    if do(van_ban) <= tran_token:
        return van_ban

    # Ước lượng chỗ cắt bằng bộ ĐO RẺ trước, rồi mới thu nhỏ dần bằng bộ đo
    # thật. Chia đôi hoàn toàn bằng bộ đếm của nhà cung cấp là hàng chục lời
    # gọi mạng cho một việc chuẩn bị prompt.
    thap, cao = 0, len(van_ban)
    while thap < cao:
        giua = (thap + cao + 1) // 2
        if estimate_tokens(van_ban[:giua]) <= tran_token:
            thap = giua
        else:
            cao = giua - 1
    cat = van_ban[:thap]

    for _ in range(4):
        thuc = do(cat)
        if thuc <= tran_token or not cat:
            break
        cat = cat[: max(1, int(len(cat) * tran_token / thuc * 0.92))]
    return cat


def _dong_lenh_ngan(quan_sat: str) -> str:
    """Dòng ``$ eaa …`` mở đầu một quan sát, cắt cho ngắn.

    Cắt là bắt buộc chứ không phải cho gọn: chỗ chừa cho ghi chú được tính từ
    những dòng này, nên một dòng bất thường dài sẽ nuốt hết ngân sách của
    chính phần nội dung mà ghi chú sinh ra để bảo vệ.
    """
    dau = (quan_sat or "").splitlines()[0] if quan_sat else ""
    return dau[:120]


def _lop_quan_sat(
    quan_sat: Sequence[str],
    budget: int = 0,
    counter: Callable[[str], int] | None = None,
) -> str:
    """Dựng lớp quan sát sao cho VỪA ngân sách, thay vì để nó tràn.

    Nới ngân sách mỗi lần một lệnh trả về nhiều chữ hơn là chạy theo đuôi:
    ``MAX_OUTPUT_CHARS`` cho mỗi lệnh 3.200 ký tự, ba quan sát là 9.600 — quá
    bất kỳ ngân sách hợp lý nào. Đọc được một trang PDF đưa lượt chạy vào đúng
    tình huống ấy ngay lần đầu.

    Nên lớp này **tự cắt**: giữ quan sát mới nhất trước, thêm ngược dần chừng
    nào còn chỗ, và **nói ra đã bỏ bao nhiêu**. Bỏ im lặng thì mô hình tưởng
    nó đã thấy hết những gì vừa chạy, và đó là cách nó kết luận trên một nửa
    dữ liệu mà không biết.

    Quan sát MỚI NHẤT không bao giờ bị bỏ, kể cả khi một mình nó đã quá dài —
    khi ấy nó bị cắt đuôi. Bỏ hẳn thứ vừa chạy là bỏ đúng thứ mô hình đang cần.
    """
    from eaa.llm.base import estimate_tokens

    # Đếm bằng CHÍNH bộ đếm sẽ kiểm, khi có.
    #
    # ``estimate_tokens`` cố ý ước lượng hơi CAO — nhưng cao so với tiếng Anh.
    # Với tiếng Việt có dấu, bộ tách token thật cắt nhỏ hơn hẳn, nên ước lượng
    # hoá ra THẤP. Đo được: một lớp quan sát ước lượng 3.400 token bị bộ đếm
    # thật tính là 4.327. Cắt theo ước lượng rồi để bộ đếm thật chặn là cắt
    # cho vui.
    dem = counter or estimate_tokens
    tran = budget or NGAN_SACH_QUAN_SAT
    dau = "## KẾT QUẢ CÁC LỆNH BẠN VỪA CHẠY\n\n"

    # Chừa chỗ cho ĐÚNG hai dòng ghi chú có thể thêm vào cuối, đo bằng chính
    # bộ ước lượng. Chừa một con số tròn đoán bằng mắt thì lệch — và ở đây
    # lệch một token cũng đủ làm cả lượt chạy hỏng trước khi gọi API.
    # Chừa chỗ cho trường hợp XẤU NHẤT: mọi quan sát đều bị bỏ, và dòng tên
    # lệnh của tất cả chúng đều phải in ra. Chừa theo trường hợp trung bình thì
    # đúng phần ghi chú lại đẩy lớp vượt trần — mà ghi chú ấy sinh ra để cứu
    # lượt chạy, không phải để làm hỏng nó.
    ghi_chu = (
        "\n…(cắt cho vừa ngân sách ngữ cảnh)"
        "\n\n(đã bỏ đầu ra của 999 lệnh cũ cho vừa ngân sách. BẠN ĐÃ CHẠY "
        "chúng rồi — đừng chạy lại:\n"
        + "\n".join(f"    {_dong_lenh_ngan(q)}" for q in quan_sat)
        + "\nCần lại nội dung nào thì chạy lại đúng lệnh ấy.)"
    )
    con_lai = tran - dem(dau) - dem(ghi_chu)

    giu: list[str] = []
    for q in reversed(quan_sat):
        chi_phi = dem(q) + 2
        if giu and chi_phi > con_lai:
            break
        if not giu and chi_phi > con_lai:
            # Quan sát mới nhất mà đã quá dài: cắt đuôi chứ không bỏ.
            giu.append(
                _cat_vua(q, max(0, con_lai), dem)
                + "\n…(cắt cho vừa ngân sách ngữ cảnh)"
            )
            con_lai = 0
            break
        giu.append(q)
        con_lai -= chi_phi

    bo = len(quan_sat) - len(giu)
    than = dau + "\n\n".join(reversed(giu))
    if bo > 0:
        # Nêu ĐÍCH DANH những lệnh đã chạy mà đầu ra bị bỏ.
        #
        # Chỉ nói "đã bỏ 3 quan sát" là chưa đủ, và thiếu sót ấy gây ra một lỗi
        # đo được: Agent mất trí nhớ về việc mình vừa đọc tệp nào, đọc lại
        # đúng tệp ấy, đầu ra lại đẩy quan sát cũ ra ngoài — và nó quay vòng
        # cho tới khi chạm trần số bước. Một dòng tên lệnh rẻ hơn hẳn một lượt
        # gọi mô hình bị đốt.
        da_chay = [_dong_lenh_ngan(q) for q in quan_sat[:bo]]
        than += (
            f"\n\n(đã bỏ đầu ra của {bo} lệnh cũ cho vừa ngân sách. BẠN ĐÃ CHẠY "
            "chúng rồi — đừng chạy lại:\n"
            + "\n".join(f"    {d}" for d in da_chay)
            + "\nCần lại nội dung nào thì chạy lại đúng lệnh ấy.)"
        )
    return than


def _danh_sach_nguon(gia_tri: Any) -> list[str]:
    """Đọc trường ``nguon`` ở cả hai dạng: một chuỗi, hoặc danh sách chuỗi."""
    if isinstance(gia_tri, str):
        return [gia_tri] if gia_tri.strip() else []
    if isinstance(gia_tri, (list, tuple)):
        return [str(x) for x in gia_tri if str(x).strip()]
    return []


def tool_for(argv: Sequence[str]) -> Tool | None:
    """Tìm công cụ khớp phần đầu của argv, ưu tiên khớp dài nhất.

    Một mục KHÔNG khai ``takes`` thì không nhận thêm đối số nào. Thiếu luật
    này, mọi mục trong danh mục đều là một tiền tố mở: thêm ``doctor`` để Agent
    quét được máy sẽ mở luôn ``doctor approve`` — tức là mở đúng cái quyền mà
    mục ấy sinh ra để không đụng tới.

    Hàng rào là danh mục, nên danh mục phải nói ĐÚNG cái nó cho phép. Một mục
    đọc như "được gọi `doctor`" mà thực tế là "được gọi bất cứ gì bắt đầu bằng
    `doctor`" thì bảng quyền hạn không còn đọc được nữa.
    """
    # KHỚP DÀI NHẤT THẮNG, kể cả khi bên thắng là bên CẤM.
    #
    # Danh mục có cả cặp cha–con trái dấu nhau, ở cả hai chiều:
    #
    #   `gate show`  được phép   ·  `gate`          cấm   → con thắng cha
    #   `flash`      được phép   ·  `flash approve` cấm   → con thắng cha
    #
    # Xét cấm trước thì hỏng cặp thứ nhất; xét cho phép trước thì hỏng cặp thứ
    # hai — và cặp thứ hai hỏng theo hướng NGUY HIỂM: một mục nhận đối số tự do
    # là một tiền tố mở, nên `flash --image <ảnh>` nuốt luôn `flash approve`,
    # tức mở đúng cái quyền mà mục ấy sinh ra để không đụng tới.
    #
    # Chỉ có một luật đúng cho cả hai: cái nào khớp SÂU HƠN thì cái ấy đang nói
    # về đúng lệnh này.
    cam = 0
    for so_tu in (2, 1):
        if " ".join(str(x) for x in argv[:so_tu]) in NGOAI_DANH_MUC:
            cam = so_tu
            break

    for t in sorted(TOOLBOX, key=lambda x: -len(x.argv)):
        if tuple(argv[: len(t.argv)]) != t.argv:
            continue
        if not t.takes and len(argv) > len(t.argv):
            continue
        return None if cam >= len(t.argv) else t
    return None


def _mo_ta_danh_muc() -> str:
    chi_doc = [t for t in TOOLBOX if not t.writes]
    co_ghi = [t for t in TOOLBOX if t.writes]
    dong = ["## LỆNH BẠN ĐƯỢC GỌI", ""]
    dong += [t.render() for t in chi_doc]
    dong += ["", "## LỆNH GHI RA TỆP (vẫn được gọi, nhưng nói cho người biết)", ""]
    dong += [t.render() for t in co_ghi]
    # Chỉ nêu những động từ KHÔNG có mặt dưới bất kỳ dạng nào. `datasheet` và
    # `docs` có trong danh mục ở dạng `list`, nên liệt chúng vào phần "không
    # có" sẽ mâu thuẫn với chính bảng ngay phía trên.
    co_mat = {t.argv[0] for t in TOOLBOX}
    vang_han = sorted(k for k in NGOAI_DANH_MUC if k not in co_mat)
    dong += [
        "",
        "## LỆNH CỦA NGƯỜI — bạn KHÔNG gọi được, nhưng chúng TỒN TẠI",
        "",
        "  " + "  ".join(f"eaa {k}" for k in vang_han),
        "",
        "Cần một trong số đó thì ĐỀ NGHỊ người dùng gõ nó, nêu đúng dòng lệnh.",
        "TUYỆT ĐỐI không đi tìm công cụ NGOÀI SẢN PHẨM này để né chúng: quy",
        "trình của dự án nằm trong `eaa`, và mã sinh ra ngoài quy trình ấy",
        "không qua cổng nào — không ràng buộc, không trích dẫn, không kiểm.",
        "Đường sinh mã cho thiết bị là: eaa plan add → eaa gen → eaa build →",
        "eaa flash. Bạn trình được từng bước; người gõ.",
        "",
        "Với `datasheet` và `docs` bạn chỉ có `list`; các hành động khác của "
        "hai lệnh ấy là việc của người.",
        "",
        "Với `tool` và `skill` bạn KHÔNG có `approve`. Bạn viết được công cụ "
        "mới, rút được kỹ năng mới, và cho cả hai qua ba cổng — nhưng bước cuối, "
        "cho phép nó chạy, là của người. Bạn mở rộng được CÁI BẠN LÀM, không mở "
        "rộng được QUYỀN BẠN CÓ.",
        "",
        "## THỨ TỰ NÊN THEO KHI THIẾU THÔNG TIN",
        "",
        "  1. `memory list` / `playbook lookup` — thứ đã biết từ lần trước, rẻ nhất",
        "  2. `recall \"<câu hỏi>\"` — KHO TRI THỨC ĐÃ DUYỆT của dự án này",
        "  3. lệnh đọc trong dự án (`status`, `sources need`, `datasheet list`…)",
        "  4. `research` — đi tìm và ĐỌC thật ngoài web",
        "  5. `hoi_lai` — hỏi người dùng",
        "",
        "Bỏ qua bậc 1 để nhảy thẳng ra web là đốt thời gian và tiền của người "
        "dùng cho thứ bạn đã biết.",
        "Ra web trước khi tra kho là đổi một nguồn ĐÃ KIỂM lấy nguồn chưa "
        "kiểm. `recall` không có gì thì NÓI RA, rồi mới `research` — và nêu "
        "địa chỉ kèm hạng nguồn.",
    ]
    return "\n".join(dong)


def _goc_kho(project: Any) -> Any:
    """Đi ngược từ thư mục dự án lên gốc kho mã.

    Không dùng ``project.parent.parent``: dự án thật nằm ở ``projects/<tên>``
    còn chỗ làm nháp nằm ở ``.eaa/scratch/<tên>``, hai độ sâu khác nhau. Tìm
    theo DẤU HIỆU của gốc kho thì đúng cho cả hai và cho mọi chỗ đặt sau này.
    """
    from pathlib import Path

    hien_tai = Path(project).resolve()
    for thu_muc in (hien_tai, *hien_tai.parents):
        if (thu_muc / "packs").is_dir() and (thu_muc / "eaa").is_dir():
            return thu_muc
    return hien_tai.parent


def _mo_ta_cong_cu_tu_sinh(repo: Any) -> str:
    """Liệt kê công cụ tự sinh ĐÃ ĐƯỢC DUYỆT, đọc từ sổ lúc chạy.

    Đây là phần DUY NHẤT của danh mục thay đổi được mà không cần commit — và
    nó chỉ thay đổi được bằng một lần người bấm duyệt. Ranh giới quyền vẫn nằm
    trong Git (mục ``tool run`` ở :data:`TOOLBOX`); thứ động ở đây là danh sách
    việc, không phải danh sách quyền.
    """
    try:
        from eaa.toolforge import ToolRegistry

        ds = ToolRegistry(repo).approved()
    except Exception:  # noqa: BLE001 - chưa có sổ là chuyện bình thường
        return ""
    if not ds:
        return ""
    dong = ["## CÔNG CỤ BẠN ĐÃ TỰ VIẾT VÀ ĐƯỢC NGƯỜI DUYỆT", ""]
    for t in ds:
        tham_so = ", ".join((t.schema.get("properties") or {}).keys()) or "(không có)"
        dong.append(f"  ✎ tool run {t.name} --args '{{...}}'")
        dong.append(f"      {t.purpose}")
        dong.append(f"      tham số: {tham_so}")
    return "\n".join(dong)


# --------------------------------------------------------------------------
# Một lượt hỏi
# --------------------------------------------------------------------------


@dataclass
class Step:
    """Một bước trong lượt: Agent nghĩ gì, làm gì, thấy gì."""

    thinking: str = ""
    action: str = ""
    argv: tuple[str, ...] = ()
    output: str = ""
    exit_code: int | None = None
    refused: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking,
            "action": self.action,
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "output": self.output,
            "refused": self.refused,
        }

    def render(self) -> str:
        if self.refused:
            return f"  ✗ từ chối gọi `{' '.join(self.argv)}` — {self.refused}"
        if self.action == "chay_lenh":
            return f"  → eaa {' '.join(self.argv)}   (mã {self.exit_code})"
        return ""


@dataclass
class ChatResult:
    """Kết cục một lượt hỏi."""

    question: str
    answer: str = ""
    steps: list[Step] = field(default_factory=list)
    #: Lệnh Agent đề nghị BẠN chạy — nó không tự chạy được.
    suggested: list[str] = field(default_factory=list)
    #: Agent hỏi lại vì thiếu dữ kiện.
    clarifying: str = ""
    hit_limit: bool = False
    #: Nguồn Agent tự khai cho câu trả lời — xem :attr:`unsourced`.
    sources: tuple[str, ...] = ()

    @property
    def commands_run(self) -> list[str]:
        return [" ".join(s.argv) for s in self.steps if s.action == "chay_lenh" and not s.refused]

    @property
    def unsourced(self) -> bool:
        """Có chạy lệnh, có trả lời, mà KHÔNG khai nguồn.

        Đây là hình dạng của một lỗi đo được ngày 31/08/2026: người dùng hỏi
        quy trình trong tài liệu của HỌ, Agent chạy ba lệnh đọc tài liệu của
        DỰ ÁN NÀY, rồi tóm tắt thứ nó đọc được như thể đó là câu trả lời. Mọi
        câu trong câu trả lời ấy đều đúng — chỉ là đúng về một tài liệu khác.

        Không phép kiểm nào bắt được điều đó, vì lệnh chạy hợp lệ và đầu ra
        hợp lệ. Thứ bắt được là **bắt Agent nói ra nó đang trả lời từ đâu**:
        có dòng ấy thì chính người đọc nhận ra ngay nguồn không khớp câu hỏi.
        """
        return bool(self.answer) and bool(self.commands_run) and not self.sources

    def render(self) -> str:
        dong: list[str] = []
        for s in self.steps:
            v = s.render()
            if v:
                dong.append(v)
        if dong:
            dong.append("")
        if self.clarifying:
            dong.append(self.clarifying)
        elif self.answer:
            dong.append(self.answer)
            if self.sources:
                dong += ["", "Trả lời này dựa trên:"]
                dong += [f"    · {n}" for n in self.sources]
            elif self.unsourced:
                dong += [
                    "",
                    "⚠ Tôi đã chạy lệnh nhưng KHÔNG khai câu trả lời dựa trên "
                    "đầu ra nào. Hãy đọc nó dè dặt: một câu trả lời đúng về "
                    "MỘT tài liệu vẫn sai nếu đó không phải tài liệu bạn hỏi.",
                    f"    Lệnh đã chạy: {', '.join(self.commands_run)}",
                ]
        if self.suggested:
            dong += ["", "Lệnh bạn cần tự chạy (tôi không được phép):"]
            dong += [f"    {_dong_lenh(c)}" for c in self.suggested]
        if self.hit_limit:
            dong += [
                "",
                f"Đã chạm trần {MAX_STEPS} bước trong một lượt nên tôi dừng ở đây.",
                "Hỏi hẹp lại một chút thì tôi đi tới nơi được.",
            ]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Vòng lặp
# --------------------------------------------------------------------------


_VAI_TRO = """\
Bạn là trợ lý của một kỹ sư nhúng, làm việc bên trong công cụ EAA.

Bạn TRẢ LỜI BẰNG TIẾNG VIỆT, ngắn và cụ thể. Bạn có thể tự chạy các lệnh trong
danh mục dưới đây để tự tìm câu trả lời thay vì hỏi lại người dùng.

Bốn luật, và luật đầu là luật không bao giờ được phá:

1. KHÔNG BAO GIỜ nói rằng bạn đã làm một việc mà bạn chưa chạy lệnh để làm.
   Không đoán nội dung đầu ra của một lệnh. Chưa chạy thì chưa biết.
2. Quyết định tại gate, nạp firmware, cài công cụ, phong hạng — là việc của
   NGƯỜI. Bạn không có lệnh nào để làm những việc ấy.

   Khi người dùng nhờ bạn làm một trong số đó, BẮT BUỘC dùng hành động
   "de_nghi_nguoi_chay" và điền "lenh" bằng lệnh CỤ THỂ họ cần gõ — đừng chỉ
   nói "bạn tự làm đi". Người hỏi đang cần biết gõ gì tiếp theo; một lời từ
   chối không kèm lệnh bắt họ đi tra tài liệu, và đó là đúng việc bạn có mặt
   để làm thay.

   Cần nhiều lệnh thì điền "lenh" là danh sách các lệnh, ví dụ:
       "lenh": [["gate","approve","G1"], ["gate","approve","G2"]]

   "lenh" nhận cả lệnh của hệ điều hành khi việc cần làm nằm ngoài `eaa` — ví
   dụ ["brew","install","cppcheck"]. Đừng thêm "eaa" vào đầu những lệnh ấy.
3. Thiếu dữ kiện thì HỎI LẠI, đừng đoán. Một câu hỏi tốn một lượt; một phỏng
   đoán sai tốn cả buổi.
4. Khi đã đủ dữ kiện thì trả lời, và nêu rõ điều bạn CHƯA kiểm được.
5. NÊU NGUỒN. Trả lời dựa trên đầu ra của lệnh nào thì điền lệnh ấy vào
   "nguon". Và trước khi trả lời, tự hỏi một câu:

       nguồn tôi vừa đọc có đúng là thứ người ta hỏi không?

   Đây là chỗ đã hỏng thật, nên nó thành luật. Người dùng hỏi quy trình trong
   TÀI LIỆU CỦA HỌ; đã có lần chạy ba lệnh đọc tài liệu CỦA DỰ ÁN NÀY, rồi tóm
   tắt thứ đọc được như thể đó là câu trả lời. Từng câu đều đúng — chỉ là đúng
   về một tài liệu khác.

   Hỏi về nội dung một tài liệu mà bạn CHƯA MỞ nó ra: nói thẳng là chưa đọc
   được, nêu tên tệp cần mở. Đừng bao giờ thay bằng một tài liệu khác.

Mỗi lượt bạn trả về ĐÚNG một khối JSON, không kèm chữ nào ngoài khối ấy:

```json
{
  "suy_nghi": "<một câu: bạn đang cần gì để trả lời>",
  "hanh_dong": "chay_lenh | tra_loi | hoi_lai | de_nghi_nguoi_chay",
  "lenh": ["<từng phần của lệnh>", "..."],
  "noi_dung": "<câu trả lời, hoặc câu hỏi lại, tùy hành động>",
  "nguon": ["<lệnh mà câu trả lời dựa trên đầu ra của nó>"]
}
```

* ``chay_lenh`` — điền "lenh", ví dụ ["budget","show"] hoặc ["resolve","drv_i2c"].
* ``tra_loi`` — điền "noi_dung" bằng câu trả lời cuối cùng, VÀ điền "nguon"
  bằng những lệnh mà câu trả lời dựa trên. Có chạy lệnh mà bỏ trống "nguon"
  thì câu trả lời bị in ra kèm một dòng cảnh báo cho người đọc.
* ``hoi_lai`` — điền "noi_dung" bằng câu hỏi.
* ``de_nghi_nguoi_chay`` — điền "lenh" và "noi_dung" giải thích vì sao cần nó,
  VÀ điền "nguon" như ``tra_loi``: nhánh này cũng đưa ra một câu trả lời.
"""


@dataclass
class AgentLoop:
    """Vòng hội thoại: hỏi → chạy lệnh → đọc → lặp → trả lời."""

    llm: Any
    project: Path
    #: ``(argv) -> (mã thoát, đầu ra)``. Mặc định gọi CLI ngay trong tiến trình.
    runner: Callable[[Sequence[str]], tuple[int, str]] | None = None
    max_steps: int = MAX_STEPS
    #: Bản ghi phiên, giữ trong bộ nhớ và ghi ra đĩa.
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.project = Path(self.project)
        if self.runner is None:
            # Gắn sẵn dự án đang làm việc vào mọi lệnh Agent chạy.
            #
            # Không có bước này thì lệnh con tự đi tìm dự án lại từ đầu, và khi
            # kho có nhiều hơn một dự án nó không chọn được — Agent gọi đúng
            # lệnh, nhận mã thoát 4, rồi kể lại cho người dùng một lỗi môi
            # trường thay vì câu trả lời. Lỗi ấy chỉ hiện ra ở kho nhiều dự án,
            # nên nó đi lọt qua mọi bài test dùng đúng một dự án.
            self.runner = lambda argv: _chay_cli(
                ["--project", str(self.project), *argv]
            )

    # -- vòng --------------------------------------------------------------

    def ask(self, question: str) -> ChatResult:
        """Một lượt hỏi, tối đa ``max_steps`` bước."""
        if not question.strip():
            raise AgentError("Câu hỏi rỗng.")

        ket = ChatResult(question=question)
        quan_sat: list[str] = []

        for _ in range(self.max_steps):
            hanh_dong = self._hoi_mo_hinh(question, quan_sat)
            buoc = Step(
                thinking=str(hanh_dong.get("suy_nghi", "")),
                action=str(hanh_dong.get("hanh_dong", "")),
                argv=tuple(str(x) for x in (hanh_dong.get("lenh") or [])),
            )

            if buoc.action == "tra_loi":
                ket.answer = str(hanh_dong.get("noi_dung", "")).strip()
                ket.sources = tuple(
                    str(x).strip() for x in _danh_sach_nguon(hanh_dong.get("nguon"))
                )
                ket.steps.append(buoc)
                break

            if buoc.action == "hoi_lai":
                ket.clarifying = str(hanh_dong.get("noi_dung", "")).strip()
                ket.steps.append(buoc)
                break

            if buoc.action == "de_nghi_nguoi_chay":
                ket.suggested.extend(_danh_sach_lenh(hanh_dong.get("lenh")))
                ket.answer = str(hanh_dong.get("noi_dung", "")).strip()
                # Đọc "nguon" ở ĐÂY nữa, không chỉ ở nhánh trả lời.
                #
                # Nhánh này cũng sinh ra một câu trả lời, và câu ấy cũng dựa
                # trên đầu ra lệnh. Bỏ sót chỗ này thì cảnh báo "không khai
                # nguồn" bắn vào một trường hợp mà mô hình KHÔNG CÓ CÁCH tuân
                # thủ — và một cảnh báo không thể thỏa mãn dạy người ta bỏ qua
                # cảnh báo.
                ket.sources = tuple(
                    str(x).strip() for x in _danh_sach_nguon(hanh_dong.get("nguon"))
                )
                ket.steps.append(buoc)
                break

            if buoc.action != "chay_lenh" or not buoc.argv:
                quan_sat.append(
                    "Hành động không hợp lệ. Dùng đúng một trong: chay_lenh, "
                    "tra_loi, hoi_lai, de_nghi_nguoi_chay."
                )
                ket.steps.append(buoc)
                continue

            cong_cu = tool_for(buoc.argv)
            if cong_cu is None:
                buoc.refused = self._vi_sao_khong(buoc.argv)
                quan_sat.append(
                    f"KHÔNG chạy `{' '.join(buoc.argv)}`: {buoc.refused} "
                    "Chọn một lệnh trong danh mục, hoặc dùng de_nghi_nguoi_chay."
                )
                ket.steps.append(buoc)
                continue

            ma, dau_ra = self.runner(list(buoc.argv))
            buoc.exit_code = ma
            buoc.output = dau_ra[:MAX_OUTPUT_CHARS]
            ket.steps.append(buoc)
            quan_sat.append(
                f"$ eaa {' '.join(buoc.argv)}\n(mã thoát {ma})\n{buoc.output}"
            )
        else:
            ket.hit_limit = True

        self._ghi_ban_ghi(ket)
        return ket

    # -- gọi mô hình -------------------------------------------------------

    def _hoi_mo_hinh(self, question: str, quan_sat: Sequence[str]) -> dict[str, Any]:
        from eaa.llm.base import LLMError, Prompt, PromptLayer
        from eaa.options import boc_json

        lop = [
            # Ràng buộc cứng đứng ĐẦU và là lớp BẮT BUỘC.
            #
            # CLAUDE.md và FR-KB-01 nói ràng buộc vào "100% lần gọi LLM". Trước
            # SL-112 câu ấy chỉ đúng ở đường sinh mã (`PromptComposer`); đường
            # hội thoại — đúng chỗ người dùng gõ câu hỏi vào — không có lớp này.
            # Hậu quả đo được: được hỏi mã kiểm UART, Agent trả về `delay(1000)`
            # và `Serial.println`, hai thứ dự án CẤM đích danh.
            PromptLayer("constraints", self._lop_rang_buoc(),
                        budget=NGAN_SACH_RANG_BUOC, required=True),
            PromptLayer("toolbox", _mo_ta_danh_muc(), budget=NGAN_SACH_DANH_MUC,
                        required=True),
            PromptLayer("state", self._tom_tat_du_an(), budget=NGAN_SACH_TRANG_THAI),
        ]
        # Công cụ tự sinh đã duyệt — phần động của danh mục. Không bắt buộc:
        # thiếu nó thì Agent mất mấy việc làm được, không mất khả năng trả lời.
        tu_sinh = _mo_ta_cong_cu_tu_sinh(_goc_kho(self.project))
        if tu_sinh:
            lop.append(PromptLayer("forged", tu_sinh, budget=600))
        ban_ghi = self._tom_tat_ban_ghi()
        if ban_ghi:
            lop.append(PromptLayer("history", ban_ghi, budget=1200))
        if quan_sat:
            lop.append(
                PromptLayer(
                    "observations",
                    _lop_quan_sat(quan_sat, counter=self.llm.count_tokens),
                    budget=NGAN_SACH_QUAN_SAT,
                )
            )
        lop.append(
            PromptLayer("task", f"## NGƯỜI DÙNG HỎI\n\n{question}", budget=500, required=True)
        )

        prompt = Prompt(
            system_instruction=_VAI_TRO,
            system_budget=NGAN_SACH_VAI_TRO,
            layers=lop,
            module="hội thoại",
            budget=7_600,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise AgentError(f"Không hỏi được mô hình: {exc}") from exc

        return boc_json(van_ban, AgentError)

    # -- ngữ cảnh ----------------------------------------------------------

    def _tom_tat_kho_tai_lieu(self) -> str:
        """Nói cho mô hình biết dự án CÓ một kho hồ sơ đã giải nén, và có gì.

        Không có mấy dòng này thì kho nằm trên đĩa mà Agent không biết là có.
        Đo được ngày 31/08/2026: hỏi về quy trình trong tài liệu, Agent tra kho
        tri thức của dự án, không thấy, rồi hỏi lại người dùng đường dẫn — trong
        khi tệp cần đọc đã nằm sẵn ở ``sources/`` từ một lượt trước.

        Chỉ đếm và nêu vài tên: một danh sách 308 mục sẽ nuốt hết lớp trạng
        thái. Agent thấy có kho thì tự gọi ``survey --files`` để soi tiếp.
        """
        goc = self.project / "sources"
        if not goc.is_dir():
            return ""
        try:
            tep = [p for p in goc.rglob("*") if p.is_file()]
        except OSError:
            return ""
        if not tep:
            return ""

        theo_duoi: dict[str, int] = {}
        for p in tep:
            theo_duoi[p.suffix.lower() or "(không đuôi)"] = (
                theo_duoi.get(p.suffix.lower() or "(không đuôi)", 0) + 1
            )
        pho_bien = ", ".join(
            f"{n}{d}" for d, n in sorted(theo_duoi.items(), key=lambda x: -x[1])[:8]
        )
        tai_lieu = [p for p in tep if p.suffix.lower() in (".pdf", ".md", ".txt")][:5]

        dong = [
            "",
            f"- KHO HỒ SƠ đã giải nén ở sources/ — {len(tep)} tệp: {pho_bien}",
            "  Soi tiếp: `survey --files '<mẫu>'` · Đọc một tệp: `survey --read '<đường dẫn>'`",
        ]
        if tai_lieu:
            dong.append("  Tệp tài liệu thấy được:")
            dong += [f"    {p.relative_to(goc)}" for p in tai_lieu]
        return "\n".join(dong)

    def _lop_rang_buoc(self) -> str:
        """Bảng ràng buộc cứng của dự án — đúng bảng K1 mà đường sinh mã dùng.

        Gọi lại ``composer._bang_rang_buoc`` chứ không chép: hai bảng ràng buộc
        dựng bằng hai đoạn mã khác nhau sẽ lệch nhau, và lúc lệch thì đường này
        cho phép đúng thứ đường kia cấm — mà không ai thấy.

        Không đọc được ràng buộc thì NÓI RA. Trả một lớp rỗng là để mô hình
        tưởng dự án không có luật nào, và đó là giả định nguy hiểm nhất nó có
        thể mang.
        """
        try:
            from eaa.composer import _bang_rang_buoc
            from eaa.kb import Constraints

            bang = _bang_rang_buoc(Constraints.load(self.project / "constraints.yaml"))
        except Exception as exc:  # noqa: BLE001 - dự án chưa dựng, tệp hỏng…
            return (
                "## RÀNG BUỘC CỨNG\n\n"
                f"(KHÔNG đọc được ràng buộc của dự án: {exc}). "
                "Đừng đề xuất mã cho thiết bị khi chưa biết dự án cấm gì — "
                "nói cho người dùng biết chỗ này thiếu trước đã."
            )
        if not bang.strip():
            return (
                "## RÀNG BUỘC CỨNG\n\n"
                "(dự án chưa có ràng buộc nào). Đừng coi đó là 'được phép mọi "
                "thứ': nó nghĩa là bước chốt ràng buộc tại G1 chưa làm, và mã "
                "sinh ra bây giờ chưa có gì để đối chiếu."
            )
        return bang

    def _tom_tat_du_an(self) -> str:
        """Vài dòng trạng thái — đủ để mô hình biết đang đứng ở đâu."""
        from eaa.state import StateStore

        try:
            state = StateStore(self.project / "project_state.json").load()
        except Exception:
            return "## DỰ ÁN\n\n(chưa khởi tạo — người dùng có thể cần chạy 'eaa init')"

        gates = " ".join(f"{k}={v}" for k, v in sorted((state.gates or {}).items()))
        backlog = ", ".join(f"{m.id}[{m.status}]" for m in state.backlog) or "(trống)"
        return (
            "## DỰ ÁN\n\n"
            f"- thư mục: {self.project.name}\n"
            + self._dong_phan_cung()
            + f"- pha: {state.phase}\n"
            f"- gate: {gates}\n"
            f"- backlog: {backlog}"
            + self._tom_tat_kho_tai_lieu()
        )

    def _dong_phan_cung(self) -> str:
        """Con chip và cái bo đang làm việc cùng — vài chữ, đổi cả câu trả lời.

        Thiếu dòng này thì mô hình **không biết nó đang viết mã cho chip nào**,
        và nó không im lặng về chỗ không biết: nó đoán. Đo được ở Bài 1 phiên
        kiểm bo thật — Agent đoán sai họ bo, sai tốc độ truyền, sai cả tên cổng
        nối tiếp, trong khi cả ba thứ ấy đều đã nằm trong hồ sơ dự án.

        Một đoán sai ở đây không dừng lại ở đó: nó kéo theo sai thanh ghi, sai
        hệ số chia tốc độ, sai cả lệnh nạp.

        Mọi GIÁ TRỊ đều đọc từ hồ sơ dự án lúc chạy; tệp này không được chứa
        tên chip, tên bo hay con số nào của phần cứng cụ thể (TC-38) — kể cả
        trong lời chú thích, vì chú thích cũng là engine.
        """
        dong = []
        try:
            from eaa.kb import Constraints

            rb = Constraints.load(self.project / "constraints.yaml")
            if getattr(rb, "mcu", ""):
                dong.append(f"- MCU: {rb.mcu}")
            if getattr(rb, "platform", ""):
                dong.append(f"- Platform Pack: {rb.platform}")
        except Exception:  # noqa: BLE001 - chưa có hồ sơ thì thôi
            pass
        try:
            from eaa.kb import HardwareProfile

            hs = HardwareProfile.load(self.project / "hardware_profile.yaml")
            tho = getattr(hs, "raw", {}) or {}
            for ng in (tho.get("peripherals") or []):
                if ng.get("baud"):
                    dong.append(f"- {ng.get('id', 'uart')}: {ng['baud']} baud")
            ct = (tho.get("programmer") or {})
            if ct.get("tool"):
                dong.append(f"- nạp qua: {ct['tool']}")
        except Exception:  # noqa: BLE001
            pass
        return ("\n".join(dong) + "\n") if dong else ""

    def _tom_tat_ban_ghi(self) -> str:
        """Bản ghi phiên, cắt còn vài lượt gần nhất.

        Đây là chỗ "trí nhớ hội thoại" nằm — và nó nằm ở PHÍA ENGINE, dựng lại
        mỗi lượt, chứ không phải ở phía nhà cung cấp mô hình.
        """
        if not self.transcript:
            return ""
        dong = ["## CÁC LƯỢT TRƯỚC TRONG PHIÊN NÀY", ""]
        for luot in self.transcript[-3:]:
            dong.append(f"Người dùng: {luot['question']}")
            if luot.get("commands_run"):
                dong.append(f"Bạn đã chạy: {', '.join(luot['commands_run'])}")
            tra_loi = (luot.get("answer") or luot.get("clarifying") or "").strip()
            if tra_loi:
                dong.append(f"Bạn trả lời: {tra_loi[:300]}")
            dong.append("")
        return "\n".join(dong)

    def _vi_sao_khong(self, argv: Sequence[str]) -> str:
        """Vì sao lệnh này không gọi được — nói cụ thể khi nói được.

        Khóa của ``NGOAI_DANH_MUC`` có cả loại hai từ ('tool approve',
        'doctor approve', 'skill approve'), vì cấm cả lệnh cha thì cấm luôn
        những chế độ vô hại của nó. Tra bằng ``argv[0]`` thì mọi khóa hai từ
        **không bao giờ khớp**: lời giải thích được viết ra, đi vào prompt, mà
        không tới được người hỏi — họ nhận câu chung chung, đúng chỗ mà một
        câu cụ thể là hữu ích nhất.

        Khớp phần đầu DÀI NHẤT: 'doctor approve x' phải ra lý do của
        'doctor approve', không phải của 'doctor' (nếu có).
        """
        ly_do = ""
        for so_tu in (2, 1):
            khoa = " ".join(str(x) for x in argv[:so_tu])
            if khoa in NGOAI_DANH_MUC:
                ly_do = NGOAI_DANH_MUC[khoa]
                break
        if ly_do:
            return ly_do
        return (
            f"lệnh {' '.join(argv)!r} không có trong danh mục tôi được gọi. "
            "Danh mục là dữ liệu, không phải lời dặn — tôi không có đường nào "
            "gọi ngoài nó."
        )

    # -- ghi vết -----------------------------------------------------------

    def _ghi_ban_ghi(self, ket: ChatResult) -> None:
        ban_ghi = {
            "ts": _now(),
            "question": ket.question,
            "commands_run": ket.commands_run,
            "answer": ket.answer,
            "clarifying": ket.clarifying,
            "suggested": ket.suggested,
            "steps": [s.to_dict() for s in ket.steps],
            "hit_limit": ket.hit_limit,
        }
        self.transcript.append(ban_ghi)

        duong_dan = self.project / CHAT_LOG
        try:
            duong_dan.parent.mkdir(parents=True, exist_ok=True)
            with open(duong_dan, "a", encoding="utf-8") as f:
                f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            # Không ghi được bản ghi thì phiên vẫn phải chạy tiếp; mất một dòng
            # nhật ký nhẹ hơn mất câu trả lời người dùng đang chờ.
            pass


def _chay_cli(argv: Sequence[str]) -> tuple[int, str]:
    """Chạy một lệnh EAA ngay trong tiến trình và thu lại đầu ra.

    Trong tiến trình chứ không qua ``subprocess``: nhanh hơn nhiều lần khi một
    lượt phải chạy vài lệnh, và quan trọng hơn — bài test thay được hàm này
    bằng một hàm giả để kiểm vòng lặp mà không chạm tới hệ thống tệp.
    """
    from eaa.cli import main

    ra, loi = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(ra), redirect_stderr(loi):
            ma = main(list(argv))
    except SystemExit as exc:  # pragma: no cover - argparse thoát sớm
        ma = int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001
        return 4, f"Lệnh ném ngoại lệ: {exc}"

    dau_ra = (ra.getvalue() + loi.getvalue()).strip()
    return ma, dau_ra or "(không có đầu ra)"
