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
:data:`TOOLBOX` — danh mục lệnh Agent được gọi — **không chứa** ``gate
approve/reject``, ``flash``, ``doctor --fix``, ``tune``, ``rollback``,
``diagnose run``, ``endurance``. Mô hình có muốn gọi cũng không có gì để gọi;
vòng lặp từ chối mọi lệnh ngoài danh mục và nói lại cho mô hình biết vì sao.

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
    Tool(("plan", "list"), "Backlog module và trạng thái từng module"),
    Tool(("ledger", "list"), "Nhật ký lỗi ảo giác đã gặp"),
    Tool(("safety", "show"), "Phân tích hỏng hóc và chế độ an toàn, kèm chỗ còn hở"),
    Tool(("budget", "show"), "Ngân sách flash/RAM chia theo module"),
    Tool(("budget", "tokens"), "Token và chi phí đã tiêu theo module"),
    Tool(("sources", "need"), "Danh sách tài liệu cần, nêu đích danh"),
    Tool(("sources", "pages"), "Phần tài liệu còn phải trích", takes="mã module"),
    Tool(("errata", "show"), "Lỗi chip đã công bố và module nào chạm vào"),
    Tool(("datasheet", "list"), "Trích đoạn tài liệu trong kho và trạng thái duyệt"),
    Tool(("docs", "list"), "Phẩm xuất đã đăng ký"),
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
    Tool(("resolve",), "Đi tìm tri thức còn thiếu của một module", takes="mã module"),
    Tool(
        ("survey",),
        "Khảo sát một kho nén hồ sơ dự án: kiểm kê, phân loại, rút dữ kiện từ mã "
        "nguồn kèm theo. Thêm --extract để giải ra đĩa",
        takes="đường dẫn .zip [--extract]",
    ),
    # -- có ghi ra tệp, nhưng KHÔNG quyết định thay người --------------------
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
    "flash": (
        "Nạp firmware chạm vào thiết bị thật. Luôn cần chính bạn xác nhận — "
        "một phiên không có người không được diễn giải thành một người đã đồng ý."
    ),
    "doctor": (
        "Cài đặt công cụ đổi máy của bạn. Tôi quét và báo được ('doctor' không "
        "cờ là chỉ đọc), nhưng '--fix' phải do bạn chạy và xác nhận từng lệnh."
    ),
    "tune": (
        "Phong hạng hw-verified là một khẳng định về phần cứng. Nó chỉ được "
        "đặt bởi người vừa cầm thiết bị và đọc số đo."
    ),
    "rollback": "Quay lui đổi mã đang chạy trên thiết bị — quyết định của bạn.",
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


def tool_for(argv: Sequence[str]) -> Tool | None:
    """Tìm công cụ khớp phần đầu của argv, ưu tiên khớp dài nhất."""
    for t in sorted(TOOLBOX, key=lambda x: -len(x.argv)):
        if tuple(argv[: len(t.argv)]) == t.argv:
            return t
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
        "## KHÔNG có lệnh nào khác. Đặc biệt KHÔNG có: " + ", ".join(vang_han),
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
        "  2. lệnh đọc trong dự án (`status`, `sources need`, `datasheet list`…)",
        "  3. `research` — đi tìm và ĐỌC thật ngoài web",
        "  4. `hoi_lai` — hỏi người dùng",
        "",
        "Bỏ qua bậc 1 để nhảy thẳng ra web là đốt thời gian và tiền của người "
        "dùng cho thứ bạn đã biết.",
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

    @property
    def commands_run(self) -> list[str]:
        return [" ".join(s.argv) for s in self.steps if s.action == "chay_lenh" and not s.refused]

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

Mỗi lượt bạn trả về ĐÚNG một khối JSON, không kèm chữ nào ngoài khối ấy:

```json
{
  "suy_nghi": "<một câu: bạn đang cần gì để trả lời>",
  "hanh_dong": "chay_lenh | tra_loi | hoi_lai | de_nghi_nguoi_chay",
  "lenh": ["<từng phần của lệnh>", "..."],
  "noi_dung": "<câu trả lời, hoặc câu hỏi lại, tùy hành động>"
}
```

* ``chay_lenh`` — điền "lenh", ví dụ ["budget","show"] hoặc ["resolve","drv_i2c"].
* ``tra_loi`` — điền "noi_dung" bằng câu trả lời cuối cùng cho người dùng.
* ``hoi_lai`` — điền "noi_dung" bằng câu hỏi.
* ``de_nghi_nguoi_chay`` — điền "lenh" và "noi_dung" giải thích vì sao cần nó.
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
                ket.steps.append(buoc)
                break

            if buoc.action == "hoi_lai":
                ket.clarifying = str(hanh_dong.get("noi_dung", "")).strip()
                ket.steps.append(buoc)
                break

            if buoc.action == "de_nghi_nguoi_chay":
                ket.suggested.extend(_danh_sach_lenh(hanh_dong.get("lenh")))
                ket.answer = str(hanh_dong.get("noi_dung", "")).strip()
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
            PromptLayer("toolbox", _mo_ta_danh_muc(), budget=2200, required=True),
            PromptLayer("state", self._tom_tat_du_an(), budget=400),
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
            # Chỉ giữ vài quan sát gần nhất: mô hình cần thứ vừa thấy, không
            # cần toàn bộ lịch sử — và ngân sách ngữ cảnh thì có hạn.
            lop.append(
                PromptLayer(
                    "observations",
                    "## KẾT QUẢ CÁC LỆNH BẠN VỪA CHẠY\n\n" + "\n\n".join(quan_sat[-3:]),
                    budget=2600,
                )
            )
        lop.append(
            PromptLayer("task", f"## NGƯỜI DÙNG HỎI\n\n{question}", budget=500, required=True)
        )

        prompt = Prompt(
            system_instruction=_VAI_TRO,
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
            f"- pha: {state.phase}\n"
            f"- gate: {gates}\n"
            f"- backlog: {backlog}"
        )

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
        ly_do = NGOAI_DANH_MUC.get(argv[0] if argv else "", "")
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
