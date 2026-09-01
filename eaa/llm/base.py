"""Giao diện chung của các adapter LLM, và lược đồ Prompt có ngân sách.

EAA-SDD-03 §4 và §6, EAA-AIS-05 §2 và §3, ADR-02, ADR-03, FR-CTX-01.

Hai vật thể chính:

* :class:`Prompt` — prompt đã lắp ráp, gồm các LỚP có tên và có ngân sách
  riêng. Giữ prompt ở dạng nhiều lớp thay vì một chuỗi dài là điều kiện để
  (a) báo được lớp nào vượt ngân sách chứ không chỉ báo "prompt quá dài", và
  (b) chứng minh được ràng buộc có mặt trong 100% lần gọi (TC-04).
* :class:`LLMClient` — hợp đồng mà mọi adapter phải theo, gồm ``count_tokens``
  vì ngân sách phải kiểm bằng bộ đếm CỦA CHÍNH mô hình sẽ gọi, không phải bằng
  ước lượng chung chung.

Ba điều bị cấm ở tầng này:

* Không giữ trạng thái hội thoại. Mỗi lần gọi là stateless (ADR-02, NT3) —
  ngữ cảnh lắp ráp lại từ các kho, nên hệ thống không có khái niệm "quên".
* Không ghi khóa API ra bất kỳ đâu. Khóa chỉ đọc từ biến môi trường
  ``EAA_LLM_KEY`` và bị che trong mọi log (NFR-06, TC-14).
* Không tự gọi khi vượt ngân sách. Vượt là LỖI LẮP RÁP, không phải "cứ gửi thử".
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from eaa.tools.base import CodeArtifact

__all__ = [
    "KEY_ENV",
    "LLMError",
    "LLMTimeout",
    "BudgetExceeded",
    "PromptLayer",
    "Prompt",
    "LLMClient",
    "estimate_tokens",
    "mask_secrets",
    "parse_file_blocks",
    "TOTAL_BUDGET",
    "LAYER_BUDGETS",
]

#: Ngân sách ngữ cảnh — AIS §2 và §3, quyết định #2 của MDD.
TOTAL_BUDGET = 8_000

#: Ngân sách từng lớp, theo Hình 1 của EAA-AIS-05 (đường ống lắp ráp ngữ cảnh).
#: Tổng đúng bằng 8.000. Tên lớp là khóa hợp đồng giữa composer và tầng này.
LAYER_BUDGETS: dict[str, int] = {
    "role_constraints": 800,     # Vai trò + ràng buộc cứng (K1)
    "hardware_facts": 400,       # Hồ sơ phần cứng trích lọc (K6)
    "datasheet_chunks": 1_500,   # Chunk top-3 (K2 + K7)
    "interfaces": 800,         # Interface các module phụ thuộc (K3)
    "error_rules": 300,          # Quy tắc từ Error Ledger (K5)
    "project_rules": 1_200,      # Luật thiết kế riêng của dự án (NFR-05)
    "host_test": 700,            # Hợp đồng bài kiểm trên máy chủ, từ pack
    "task": 500,                 # Nhiệm vụ + tiêu chí nghiệm thu
    "repair": 1_800,             # Dự phòng cho vòng tự sửa dạng vá (K, §3.2)
}
# `project_rules` và `host_test` tách ra khỏi `task`, phần ngân sách lấy từ
# `repair` để tổng vẫn đúng 8.000 (SL-135). Hai lý do, và lý do thứ hai mới là
# lý do thật:
#
# 1. Chúng không phải "nhiệm vụ". Một cái là tri thức thiết kế của dự án, một
#    cái là hợp đồng của nền tảng — gộp vào lớp nhiệm vụ thì không ai chỉnh
#    được phần của mình mà không đụng phần của người khác.
# 2. `build_repair` **bỏ lớp `task`**. Nằm trong đó nghĩa là biến mất ở đúng
#    vòng vá — lúc mô hình đang sửa mã và dễ tái phạm nhất. SL-133 chính là
#    thế: nó viết `tests/test_dummy.c` trong một vòng vá, khi không còn gì
#    nói cổng ấy chạy pytest.
#
# `repair` về lại 1.800 sau khi 1.600 chặn một vòng vá thật: cổng dịch trả về
# ba dòng lỗi kèm thân hàm liên quan là 1.836 token, trong khi prompt tổng mới
# dùng 4.752/8.000. Phần bù lấy từ `interfaces` (1.000 → 800) — lớp ấy chỉ chứa
# KHAI BÁO của module phụ thuộc, và 800 token vẫn đủ cho vài tệp tiêu đề.
#
# `repair` 1.800 vẫn dư: prompt vá cố ý KHÔNG chứa toàn văn tệp, chỉ có
# thông báo lỗi và đúng những hàm liên quan (AIS §3.2) — một hàm C cỡ vài chục
# dòng vào khoảng 300 token.
#
# `host_test` nâng 500 → 700 theo hai bước, mỗi bước sau một lần chạm trần
# thật. Hợp đồng này mang ĐƯỜNG DẪN ĐÃ GIẢI của thư mục tiêu đề giả (dài ngắn
# tùy máy) cộng những luật rút ra từ chính các lượt sinh hỏng: cách với tới
# thanh ghi qua `in_dll`, và bắt buộc đặt `restype`. Mỗi luật ấy đổi bằng một
# lượt gọi mô hình bị đốt, nên chỗ cho chúng là chỗ rẻ nhất trong cả bảng.
#
# `project_rules` được nâng 1.000 → 1.200 sau một lần đo thật, không phải đoán:
# luật thiết kế của một module điều khiển gồm sáu điều, mỗi điều kèm con số làm
# bằng chứng, rơi vào khoảng 1.100 token. Con số 1.000 ban đầu không dựa trên
# gì cả.

#: Lớp nào vượt phần thì rút gọn Ở ĐÂU. Không có bảng này, thông báo chỉ nói
#: đúng một câu — *"giảm top-k chunk, rút gọn lớp interface, chưng cất thêm quy
#: tắc lỗi"* — và câu ấy đúng cho ba lớp, sai cho những lớp còn lại: người vừa
#: viết dài một tệp mẫu prompt bị chỉ sang ba chỗ không liên quan gì tới nó.
#: Một cổng chặn đúng mà không nói được lối đi tiếp thì vẫn là ngõ cụt.
_LOI_KHUYEN_LOP: dict[str, str] = {
    "datasheet_chunks": "  → giảm top_k_chunks",
    "interfaces": "  → rút interface còn khai báo, hoặc bớt phụ thuộc",
    "error_rules": "  → giảm top_k_error_rules",
    "project_rules": "  → rút gọn tệp mẫu prompt của dự án: <dự án>/prompts/<module>.md",
    "host_test": "  → rút gọn khối `host_test` trong pack.yaml của nền tảng",
    "task": "  → rút gọn trách nhiệm/tiêu chí nghiệm thu của module trong backlog",
    "hardware_facts": "  → bớt tài nguyên `uses` của module, hoặc gộp sự kiện trong đồ thị",
    "repair": "  → lỗi cổng quá dài hoặc hàm liên quan quá lớn; tách hàm ra nhỏ hơn",
    # Lớp K1 mang tên `role_constraints` trong bảng ngân sách nhưng đi trong
    # prompt dưới tên `system_instruction` — tra bằng khóa của bảng ngân sách.
    "role_constraints": "  → rút gọn bảng ràng buộc trong constraints.yaml",
}

_FILE_BLOCK = re.compile(
    r"```(?:[a-zA-Z0-9_+-]*\s*)?file:(?P<path>[^\n`]+)\n(?P<body>.*?)```",
    re.DOTALL,
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password|bearer)\b\s*[:=]\s*\S+"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{16,}\b"),
)


class LLMError(Exception):
    """Lỗi khi gọi mô hình hoặc khi bóc tách phản hồi."""


class LLMTimeout(LLMError):
    """Quá thời gian chờ phản hồi."""


class BudgetExceeded(LLMError):
    """Prompt vượt ngân sách ngữ cảnh — chặn TRƯỚC khi gọi API (FR-CTX-01).

    Đây là lỗi LẮP RÁP chứ không phải lỗi mạng: nó nói rằng bộ nén đã không
    làm đủ việc của nó. Gửi đi một prompt phình to là làm hỏng cả ba thứ cùng
    lúc — chi phí, tính tái lập, và tỷ lệ mô hình bám ràng buộc (AIS §1).
    """

    def __init__(self, message: str, *, total: int, budget: int, layers: dict[str, int]):
        super().__init__(message)
        self.total = total
        self.budget = budget
        self.layers = layers


def estimate_tokens(text: str) -> int:
    """Ước lượng số token khi chưa có bộ đếm thật của nhà cung cấp.

    CHỈ dùng để lắp ráp và kiểm thử ngoại tuyến. Ngân sách trước mỗi lần gọi
    thật phải kiểm bằng ``count_tokens`` của chính mô hình sẽ gọi (AIS §2) —
    ước lượng sai vài phần trăm là đủ để một prompt sát trần lọt qua.

    Cách ước lượng: đếm từ và ký hiệu rồi nhân hệ số. Cố ý ước lượng HƠI CAO
    để sai số nghiêng về phía chặn nhầm chứ không phải cho qua nhầm.
    """
    if not text:
        return 0
    tu = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, math.ceil(len(tu) * 1.3))


#: Tên biến môi trường chứa khóa API — NFR-06 nói khóa CHỈ đi qua đường này.
#: Một hằng số vì tên ấy xuất hiện ở adapter, ở doctor, ở CLI; ba bản sao của
#: cùng một chuỗi là ba chỗ có thể lệch nhau.
KEY_ENV = "EAA_LLM_KEY"


def mask_secrets(text: str) -> str:
    """Che khóa và token trong bất cứ thứ gì sắp được ghi ra (NFR-06, TC-14)."""
    ket_qua = text
    khoa = os.environ.get(KEY_ENV)
    if khoa and len(khoa) >= 8:
        ket_qua = ket_qua.replace(khoa, "***")
    for mau in _SECRET_PATTERNS:
        ket_qua = mau.sub("***", ket_qua)
    return ket_qua


def parse_file_blocks(response: str) -> dict[str, str]:
    """Bóc tách phản hồi thành các tệp theo quy ước ```` ```file:<đường dẫn> ````.

    EAA-SDD-03 §6: phản hồi sai định dạng tính là MỘT LẦN FAIL của vòng tự sửa,
    không phải một lỗi hạ tầng. Lý do: sai định dạng thường đi kèm mô hình đang
    trả lời lệch nhiệm vụ, và cách xử lý đúng là cho nó biết để sửa, giống mọi
    lỗi khác của cổng kiểm chứng.
    """
    tep: dict[str, str] = {}
    for khop in _FILE_BLOCK.finditer(response):
        duong_dan = khop.group("path").strip()
        if not duong_dan:
            continue
        if duong_dan in tep:
            raise LLMError(
                f"Phản hồi chứa hai khối cho cùng một tệp: {duong_dan!r} — "
                "không xác định được bản nào là bản cuối."
            )
        tep[duong_dan] = khop.group("body")
    if not tep:
        raise LLMError(
            "Phản hồi không chứa khối ```file:<đường dẫn> nào. Tính là một lần "
            "fail của vòng tự sửa (SDD §6)."
        )
    return tep


@dataclass(frozen=True)
class PromptLayer:
    """Một lớp của prompt, có tên và có ngân sách riêng."""

    name: str
    content: str
    budget: int = 0
    #: Lớp bắt buộc thì không bao giờ được cắt bỏ để lấy chỗ (ví dụ ràng buộc).
    required: bool = False

    def tokens(self, counter: Any = None) -> int:
        dem = counter or estimate_tokens
        return dem(self.content)


@dataclass
class Prompt:
    """Prompt đã lắp ráp, giữ nguyên cấu trúc lớp để kiểm được từng lớp."""

    system_instruction: str = ""
    layers: list[PromptLayer] = field(default_factory=list)
    #: Siêu dữ liệu truy vết đi vào commit message (NFR-07).
    module: str = ""
    constraints_version: str = ""
    chunk_ids: tuple[str, ...] = ()
    temperature: float = 0.2
    budget: int = TOTAL_BUDGET
    #: Ngân sách riêng cho system instruction. AIS §2 đặt lớp Vai trò + Ràng
    #: buộc cứng (K1) vào system_instruction chứ không vào phần nội dung —
    #: Gemini tách hai thứ này, và ràng buộc đặt ở đó thì không bị "trôi".
    system_budget: int = LAYER_BUDGETS["role_constraints"]
    #: Ghi lại phần đã bị lược bớt để vừa ngân sách; rỗng nghĩa là không lược
    #: gì. Đưa vào KPI để hiệu chỉnh top-k khi vòng tự sửa chạm N vì thiếu ngữ
    #: cảnh ("context miss", AIS §12).
    trimmed: list[str] = field(default_factory=list)
    #: Ảnh gửi kèm — năng lực đa phương thức của AIS §6.1 (FR-ING-01/03).
    #:
    #: Là ĐƯỜNG DẪN chứ không phải nội dung ảnh: adapter tự quyết mã hóa thế
    #: nào cho nhà cung cấp của nó, và giữ đường dẫn ở đây nghĩa là ảnh gốc vẫn
    #: nằm nguyên trong kho — điều kiện để câu "máy đọc nhầm ảnh" kiểm chứng
    #: lại được. Adapter không hỗ trợ ảnh thì bỏ qua trường này.
    image_path: str = ""

    def layer(self, name: str) -> PromptLayer | None:
        for lop in self.layers:
            if lop.name == name:
                return lop
        return None

    def render(self) -> str:
        """Nội dung người dùng gửi đi, các lớp nối theo đúng thứ tự lắp ráp."""
        return "\n\n".join(lop.content for lop in self.layers if lop.content.strip())

    def full_text(self) -> str:
        """Toàn bộ những gì được tính vào ngân sách, kể cả system instruction."""
        return "\n\n".join(x for x in (self.system_instruction, self.render()) if x.strip())

    def token_report(self, counter: Any = None) -> dict[str, int]:
        dem = counter or estimate_tokens
        bao_cao = {lop.name: lop.tokens(dem) for lop in self.layers}
        if self.system_instruction:
            bao_cao["system_instruction"] = dem(self.system_instruction)
        return bao_cao

    def total_tokens(self, counter: Any = None) -> int:
        return sum(self.token_report(counter).values())

    def check_budget(self, counter: Any = None) -> None:
        """Cưỡng chế ngân sách TRƯỚC khi gọi API — FR-CTX-01, TC-16.

        Báo cả tổng lẫn lớp nào vượt phần của nó: một prompt quá dài luôn có
        thủ phạm cụ thể, và biết thủ phạm thì mới chỉnh đúng chỗ (giảm top-k,
        rút ngắn interface…) thay vì cắt bừa.
        """
        bao_cao = self.token_report(counter)
        tong = sum(bao_cao.values())

        vuot_lop = [
            f"  - {lop.name}: {bao_cao.get(lop.name, 0)} token / ngân sách "
            f"{lop.budget}{_LOI_KHUYEN_LOP.get(lop.name, '')}"
            for lop in self.layers
            if lop.budget and bao_cao.get(lop.name, 0) > lop.budget
        ]
        if self.system_budget and bao_cao.get("system_instruction", 0) > self.system_budget:
            vuot_lop.insert(
                0,
                f"  - system_instruction: {bao_cao['system_instruction']} token "
                f"/ ngân sách {self.system_budget}"
                f"{_LOI_KHUYEN_LOP.get('role_constraints', '')}",
            )

        if tong <= self.budget and not vuot_lop:
            return

        dong = [
            f"Prompt vượt ngân sách ngữ cảnh: {tong} token / trần {self.budget}."
            if tong > self.budget
            else f"Prompt trong trần tổng ({tong}/{self.budget}) nhưng có lớp vượt phần của nó."
        ]
        if vuot_lop:
            dong.append("Lớp vượt ngân sách:")
            dong.extend(vuot_lop)
        dong.append(
            "Không gọi API. Đây là lỗi lắp ráp, và chỗ sửa là chính lớp nêu "
            "trên — không phải cắt bừa một lớp khác (AIS §3)."
        )
        raise BudgetExceeded(
            "\n".join(dong), total=tong, budget=self.budget, layers=bao_cao
        )

    @property
    def hash(self) -> str:
        """Băm prompt — đi vào commit message và nhật ký gọi mô hình (NFR-07).

        Băm nội dung ĐÃ CHE khóa: nếu khóa lỡ lọt vào prompt thì băm vẫn không
        phải là kênh để suy ngược ra nó.
        """
        return "sha256:" + hashlib.sha256(
            mask_secrets(self.full_text()).encode("utf-8")
        ).hexdigest()


@runtime_checkable
class LLMClient(Protocol):
    """Hợp đồng của một adapter LLM."""

    #: Tên nhà cung cấp, ví dụ ``"mock"``. Đi vào kpi_log.csv.
    provider: str
    #: Mã mô hình ĐÃ GHIM PHIÊN BẢN — không dùng bí danh kiểu "latest", vì mô
    #: hình trôi phiên bản làm hỏng so sánh A/B (rủi ro R1 của STP-04).
    model: str

    def count_tokens(self, text: str) -> int:
        """Đếm token bằng bộ đếm của chính mô hình này."""
        ...

    def generate(self, prompt: Prompt) -> CodeArtifact:
        """Gọi mô hình và bóc tách phản hồi thành artifact mã nguồn.

        Adapter PHẢI gọi ``prompt.check_budget(self.count_tokens)`` trước khi
        phát yêu cầu đi.
        """
        ...
