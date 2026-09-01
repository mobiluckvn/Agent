"""TC-115 — prompt vá phải luôn ĐÒI được một bản vá.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-149.

Sáu vòng tự sửa liên tiếp trong một buổi kết thúc bằng đúng một câu::

    Vòng vá thất bại: Phản hồi không chứa khối ```file:<đường dẫn> nào.
    Tính là một lần fail của vòng tự sửa (SDD §6).

Sáu lượt gọi mô hình, sáu lần tính là hỏng, và không lần nào là lỗi của mô
hình.

Prompt mời hỏi lại, đường ống không có kênh nhận câu hỏi
---------------------------------------------------------

Khi báo cáo cổng không định vị được lỗi về một dòng trong tệp nguồn — bài kiểm
đỏ, lỗi liên kết, lỗi định dạng — thì `extract_function` không trích được gì,
và prompt rơi vào nhánh dự phòng::

    (không định vị được hàm chứa lỗi từ báo cáo; hãy hỏi lại phần mã cần
     thiết thay vì viết lại cả tệp)

Mô hình làm đúng lời dặn: nó hỏi. Mà `parse_file_blocks` chỉ bóc khối
```file:``` — một câu hỏi không có khối nào, nên nó bị tính là phản hồi sai
định dạng.

Nhánh dự phòng ấy đúng ở chỗ nó không muốn mô hình viết lại cả tệp một cách
tùy tiện. Nó sai ở chỗ nó bảo mô hình làm một việc mà hệ thống không nhận.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.composer import PromptComposer, Task
from eaa.graph import KnowledgeGraph
from eaa.kb import KnowledgeBase
from eaa.llm.base import parse_file_blocks
from eaa.tools.base import ToolError, ToolReport

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"

NHIEM_VU = Task(module_id="drv_bus_sensor", uses=("twi",), output_files=("src/m.c",))
NGUON = {
    "src/m.c": "#include \"m.h\"\nint f(void) { return 1; }\n",
    "tests/test_m.py": "def test_f():\n    assert lib.f() == 2\n",
}


@pytest.fixture()
def composer() -> PromptComposer:
    kb = KnowledgeBase.load(DU_AN)
    return PromptComposer(kb, KnowledgeGraph.build(kb.hardware, kb.datasheets))


def _khong_dinh_vi_duoc() -> ToolReport:
    """Bài kiểm đỏ: lỗi có thật, nhưng không gắn với dòng nào của tệp nguồn."""
    return ToolReport(
        gate="unittests",
        passed=False,
        errors=[ToolError("1 test không đạt: assert 1 == 2")],
    )


def test_KHONG_moi_mo_hinh_hoi_lai(composer: PromptComposer) -> None:
    """Điểm cốt lõi: đừng bảo mô hình làm việc mà đường ống không nhận."""
    van_ban = composer.build_repair(NHIEM_VU, None, _khong_dinh_vi_duoc(), NGUON).full_text()
    assert "hỏi lại" not in van_ban, (
        "prompt vẫn mời mô hình đặt câu hỏi, trong khi phản hồi chỉ được bóc "
        "theo khối ```file:``` — mọi câu hỏi đều bị tính là một lần hỏng"
    )


def test_van_DOI_khoi_file_va_noi_ro_la_bat_buoc(composer: PromptComposer) -> None:
    van_ban = composer.build_repair(NHIEM_VU, None, _khong_dinh_vi_duoc(), NGUON).full_text()
    assert "```file:" in van_ban
    assert "Bắt buộc" in van_ban or "BẮT BUỘC" in van_ban


def test_dua_TOAN_VAN_tep_khi_khong_dinh_vi_duoc(composer: PromptComposer) -> None:
    """Không định vị được thì thứ mô hình cần là toàn văn, không phải lời mời."""
    van_ban = composer.build_repair(NHIEM_VU, None, _khong_dinh_vi_duoc(), NGUON).full_text()
    for ten in NGUON:
        assert ten in van_ban, f"không đưa {ten} vào prompt vá"
    assert "assert lib.f() == 2" in van_ban, "thiếu nội dung tệp test đang đỏ"


def test_DINH_VI_DUOC_thi_van_chi_gui_HAM(composer: PromptComposer) -> None:
    """Nhánh cũ không được nới lỏng: lỗi có dòng thì vẫn chỉ gửi hàm liên quan.

    Đây là bất biến của TC-19 — prompt vá KHÔNG chứa toàn văn tệp. Sửa nhánh
    dự phòng mà làm hỏng nhánh chính là đổi một lỗi lấy một lỗi to hơn.
    """
    nguon = {
        "src/m.c": "#include \"m.h\"\n"
        + "\n".join(f"// đệm {i}" for i in range(60))
        + "\nvoid ham_loi(void)\n{\n    int x = 1\n}\n"
        + "\n".join(f"// đệm cuối {i}" for i in range(60))
        + "\n"
    }
    bao_cao = ToolReport(
        gate="compile",
        passed=False,
        errors=[ToolError("thiếu dấu chấm phẩy", file="src/m.c", line=63)],
    )
    van_ban = composer.build_repair(NHIEM_VU, None, bao_cao, nguon).full_text()

    assert "ham_loi" in van_ban
    assert "đệm cuối 59" not in van_ban, "prompt vá chứa toàn văn tệp (vi phạm TC-19)"


def test_dinh_dang_neu_ra_bóc_duoc_that(composer: PromptComposer) -> None:
    """Định dạng prompt dặn phải là định dạng bộ bóc tách thật sự hiểu."""
    mau = "```file:src/m.c\nint f(void) { return 2; }\n```"
    assert parse_file_blocks(mau) == {"src/m.c": "int f(void) { return 2; }\n"}
