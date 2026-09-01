"""TC-114 — phần của lớp vá là SÀN, không phải trần.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-147.

Ba lần liên tiếp trong một buổi sinh mã, vòng tự sửa bị chặn bởi chính bộ lắp
ráp chứ không phải bởi mô hình::

    Prompt trong trần tổng (4752/8000) nhưng có lớp vượt phần của nó.
      - repair: 1836 token / ngân sách 1600

    Prompt trong trần tổng (4255/8000) nhưng có lớp vượt phần của nó.
      - repair: 1916 token / ngân sách 1800

Gần nửa trần tổng bỏ trống, và thông điệp thực tế là *"hàm của bạn to quá,
chúng tôi thậm chí không thử sửa"*.

Vì sao lớp này khác mọi lớp khác
---------------------------------

Nó là lớp CUỐI được thêm vào, và nó THAY CHỖ lớp `task` — nên nó không cạnh
tranh với ai. Phần các lớp khác không dùng tới thì để trống chứ không ai lấy.

Và kích thước của nó do THÂN HÀM ĐANG HỎNG quyết định, thứ thay đổi theo từng
module. Một trần cố định cho một đại lượng không kiểm soát được là một trần sẽ
bị chạm, và bị chạm đúng lúc cần nhất.

Cách chữa sai là nới số
------------------------

Tôi đã nới hai lần (1.600 → 1.800) và nó chạm lại ngay module sau. Nới lần thứ
ba là thừa nhận con số ấy không dựa trên gì cả. Cách đúng là để lớp vá dùng
CHỖ TRỐNG THẬT, còn trần TỔNG vẫn là trần thật và vẫn chặn.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.composer import ComposerConfig, PromptComposer, Task
from eaa.graph import KnowledgeGraph
from eaa.kb import KnowledgeBase
from eaa.llm.base import BudgetExceeded, LAYER_BUDGETS, estimate_tokens
from eaa.tools.base import ToolError, ToolReport

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"

NHIEM_VU = Task(
    module_id="drv_bus_sensor",
    goal="Đọc số đo cảm biến qua bus nối tiếp.",
    uses=("twi", "imu"),
    output_files=("src/drv_bus_sensor.c",),
)


@pytest.fixture()
def composer() -> PromptComposer:
    kb = KnowledgeBase.load(DU_AN)
    return PromptComposer(kb, KnowledgeGraph.build(kb.hardware, kb.datasheets))


def _bao_cao_hong() -> ToolReport:
    return ToolReport(
        gate="compile",
        passed=False,
        errors=[ToolError("giá trị liệt kê chưa xử lý", file="src/m.c", line=3)],
    )


def _ham_dai(so_dong: int) -> str:
    than = "\n".join(f"    int bien_{i} = {i};" for i in range(so_dong))
    return "void ham_co_loi(void)\n{\n" + than + "\n}\n"


def test_lop_va_dung_duoc_cho_trong_thay_vi_bi_chan(composer: PromptComposer) -> None:
    """Điểm cốt lõi: còn chỗ trong trần tổng thì đừng chặn vòng vá."""
    nguon = {"src/m.c": _ham_dai(300)}
    prompt = composer.build_repair(NHIEM_VU, None, _bao_cao_hong(), nguon)

    lop = prompt.layer("repair")
    assert lop is not None
    assert lop.tokens(estimate_tokens) > LAYER_BUDGETS["repair"], (
        "bài này chỉ có nghĩa khi lớp vá thật sự vượt phần khai trong bảng"
    )
    prompt.check_budget()  # không được ném: trần tổng vẫn còn chỗ


def test_tran_TONG_van_la_tran_that(composer: PromptComposer) -> None:
    """Nới cho lớp vá KHÔNG được biến thành bỏ luôn trần ngữ cảnh."""
    composer.config = ComposerConfig(budget=3000)
    with pytest.raises(BudgetExceeded):
        composer.build_repair(NHIEM_VU, None, _bao_cao_hong(), {"src/m.c": _ham_dai(900)})


def test_lop_va_nho_thi_giu_nguyen_phan_khai(composer: PromptComposer) -> None:
    """Sàn vẫn là sàn: lớp vá ngắn không vì thế mà mất ngân sách của mình."""
    prompt = composer.build_repair(NHIEM_VU, None, _bao_cao_hong(), {"src/m.c": _ham_dai(3)})
    lop = prompt.layer("repair")
    assert lop is not None and lop.budget >= LAYER_BUDGETS["repair"]


def test_rang_buoc_van_co_mat_trong_prompt_va(composer: PromptComposer) -> None:
    """TC-04 không được hy sinh cho chỗ trống."""
    prompt = composer.build_repair(NHIEM_VU, None, _bao_cao_hong(), {"src/m.c": _ham_dai(300)})
    assert "CẤM delay()" in prompt.full_text()
