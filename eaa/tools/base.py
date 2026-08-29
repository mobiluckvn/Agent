"""Giao diện cổng kiểm chứng và báo cáo chuẩn hóa.

EAA-SDD-03 §4: ``run(artifact) -> ToolReport{passed, errors[], metrics{}}``.

Vì sao mọi cổng phải trả về CÙNG một kiểu báo cáo: bất biến quan trọng nhất
của sản phẩm (SDD §4) phát biểu rằng merge chỉ xảy ra khi TOÀN BỘ
``ToolReport.passed`` đúng và gate G3 đã duyệt. Câu "toàn bộ" chỉ kiểm chứng
được nếu các cổng nói chung một ngôn ngữ; nếu mỗi adapter trả một hình thù
riêng thì Orchestrator buộc phải hiểu từng cổng một, và mỗi cách hiểu là một
chỗ để lọt lưới.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Severity",
    "ToolError",
    "ToolReport",
    "ToolGate",
    "CodeArtifact",
]


class Severity:
    """Mức nghiêm trọng của một phát hiện.

    Người định nghĩa tiêu chí đạt và phân loại cảnh báo (công đoạn E1) — engine
    chỉ mang mức đi cùng phát hiện chứ không tự quyết mức nào thì bỏ qua được.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ToolError:
    """Một phát hiện của cổng kiểm chứng, đủ để đưa thẳng vào vòng tự sửa.

    ``file``/``line`` có mặt để prompt sửa lỗi chỉ đính kèm ĐÚNG hàm liên quan
    thay vì cả tệp — đó là kỹ thuật vá của AIS §3.2 (FR-CTX-03, TC-19).
    """

    message: str
    severity: str = Severity.ERROR
    file: str | None = None
    line: int | None = None
    #: Mã quy tắc đã bắt được lỗi này (nếu đến từ phân tích tĩnh).
    rule_id: str | None = None

    def __str__(self) -> str:
        vi_tri = ""
        if self.file:
            vi_tri = f"{self.file}:{self.line}: " if self.line else f"{self.file}: "
        ma = f"[{self.rule_id}] " if self.rule_id else ""
        return f"{vi_tri}{ma}{self.message}"


@dataclass
class ToolReport:
    """Kết quả chuẩn hóa của một cổng kiểm chứng."""

    gate: str
    passed: bool
    errors: list[ToolError] = field(default_factory=list)
    warnings: list[ToolError] = field(default_factory=list)
    #: Số liệu định lượng đi thẳng vào kpi_log.csv (FR-KPI-01).
    metrics: dict[str, Any] = field(default_factory=dict)
    #: Đầu ra thô của công cụ, giữ lại để truy vết và để tinh chỉnh quy tắc parse.
    raw_output: str = ""
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        # Một báo cáo vừa "passed" vừa có lỗi mức ERROR là mâu thuẫn nội tại,
        # và là đúng loại mâu thuẫn có thể lọt mã hỏng qua cổng.
        if self.passed and any(e.severity == Severity.ERROR for e in self.errors):
            raise ValueError(
                f"Cổng {self.gate!r} báo passed=True nhưng vẫn có lỗi mức ERROR — "
                "báo cáo tự mâu thuẫn, không được phép đi tiếp."
            )

    @property
    def summary(self) -> str:
        trang_thai = "ĐẠT" if self.passed else "KHÔNG ĐẠT"
        return (
            f"{self.gate}: {trang_thai} "
            f"({len(self.errors)} lỗi, {len(self.warnings)} cảnh báo, "
            f"{self.duration_s:.2f}s)"
        )


@dataclass
class CodeArtifact:
    """Sản phẩm mã nguồn của một lần gọi LLM.

    ``files`` ánh xạ đường dẫn tương đối → nội dung, bóc từ khối
    ```` ```file:<path> ```` theo quy ước EAA-SDD-03 §6.

    Các trường truy vết đi kèm artifact chứ không nằm rời, để commit message
    chuẩn NFR-07 (prompt hash, model, constraints_version, chunk ids) luôn dựng
    được từ chính vật thể được commit.
    """

    files: dict[str, str] = field(default_factory=dict)
    prompt_hash: str = ""
    model: str = ""
    constraints_version: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    raw_response: str = ""


@runtime_checkable
class ToolGate(Protocol):
    """Một cổng trong chuỗi kiểm chứng."""

    #: Tên cổng, xuất hiện trong ToolReport và trong báo cáo build.
    name: str

    def run(self, artifact: CodeArtifact) -> ToolReport:
        """Chạy cổng trên một artifact và trả báo cáo chuẩn hóa."""
        ...
