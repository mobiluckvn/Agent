"""TC-105 — Ý ĐỊNH của module phải tới được bộ sinh mã.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-135.

Tìm ra khi review G3 module `logic_pid` — module đầu tiên qua đủ bốn cổng. Mã
chạy, test xanh, và **hai lỗi thật**:

1.  ``d_term = kd * (error - prev_error)`` — đạo hàm lấy theo SAI SỐ. Chính
    `sim/controller.py` của dự án viết đích danh: *"Derivative kick — đạo hàm
    lấy theo SỐ ĐO chứ không theo sai số; đổi điểm đặt sẽ tạo một xung đạo hàm
    vô nghĩa nếu lấy theo sai số."*
2.  ``kp * error`` với hệ số nguyên, không có tỉ lệ fixed-point. Bản phân rã
    ghi rõ *"PID số nguyên (fixed-point)"* — không biểu diễn được `kp = 0.6`,
    mà hệ số phân số là chuyện thường của robot cân bằng.

Nguyên nhân là một, và nó nằm ở chỗ giao việc
-----------------------------------------------

Nhiệm vụ giao cho bộ sinh mã chỉ có hai câu, GIỐNG HỆT NHAU cho mọi module::

    goal       = "Hiện thực module {module_id} theo ràng buộc và tài liệu đã duyệt."
    acceptance = ("Qua toàn bộ chuỗi cổng kiểm chứng.",
                  "Mọi hàm cấu hình thanh ghi có dòng trích dẫn nguồn.")

`purpose` mà Agent viết ra và người đã duyệt ở bước phân rã **bị vứt đi tại
`plan accept`** — backlog chỉ giữ `id`, `uses`, `depends_on`. Và
`sim/controller.py`, tài liệu nêu đích danh hai lỗi kinh điển phải tránh,
**chưa bao giờ được đưa vào prompt sinh mã**.

Bài kiểm cũng sai theo, và đó là tính chất chứ không phải xui
--------------------------------------------------------------

Bài kiểm do CÙNG MỘT mô hình viết, nên nó kiểm đúng cái hiểu sai ấy là đúng.
**Một bài kiểm tự viết chỉ bắt được chỗ mã lệch với ý định — không bắt được ý
định sai.** Muốn nó bắt được thì ý định phải đến từ chỗ khác.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


# ═══════════ 1. `purpose` phải sống sót qua `plan accept` ═══════════


def test_backlog_giu_duoc_purpose() -> None:
    from eaa.state import BacklogItem

    m = BacklogItem(id="logic_pid", purpose="PID số nguyên fixed-point")
    assert m.purpose == "PID số nguyên fixed-point"
    assert "purpose" in m.to_dict()


def test_purpose_di_qua_luu_va_doc_lai(tmp_path: Path) -> None:
    """Ghi ra đĩa rồi đọc lại mà mất thì bằng không giữ."""
    from eaa.state import BacklogItem, ProjectState, StateStore

    kho = StateStore(tmp_path / "project_state.json")
    kho.save(ProjectState(backlog=[BacklogItem(id="mod_x", purpose="ý định của tôi")]))
    assert kho.load().backlog[0].purpose == "ý định của tôi"


def test_muc_cu_khong_co_purpose_van_doc_duoc(tmp_path: Path) -> None:
    """State cũ trên đĩa không có trường này — đọc nó không được sập."""
    import json

    from eaa.state import StateStore

    (tmp_path / "project_state.json").write_text(
        json.dumps({"phase": "D", "backlog": [{"id": "cu", "status": "todo"}]}),
        encoding="utf-8",
    )
    assert StateStore(tmp_path / "project_state.json").load().backlog[0].purpose == ""


# ═══════════ 2. nhiệm vụ giao đi phải MANG ý định ấy ═══════════


def test_nhiem_vu_dung_PURPOSE_lam_muc_tieu() -> None:
    """Hai câu chung chung giống nhau cho mọi module thì không giao việc gì cả."""
    from eaa.orchestrator import Orchestrator
    from eaa.state import BacklogItem

    muc = BacklogItem(id="logic_pid", purpose="PID số nguyên fixed-point")
    task = Orchestrator.dung_nhiem_vu("logic_pid", muc)

    assert "fixed-point" in task.goal, (
        "ý định của module không vào tới nhiệm vụ — mọi module nhận cùng một câu"
    )


def test_khong_co_purpose_thi_ve_cau_chung(tmp_path: Path) -> None:
    """Module cũ chưa có ý định thì vẫn phải sinh được, chỉ là mờ hơn."""
    from eaa.orchestrator import Orchestrator
    from eaa.state import BacklogItem

    task = Orchestrator.dung_nhiem_vu("mod_cu", BacklogItem(id="mod_cu"))
    assert task.goal.strip()


# ═══════════ 3. tri thức thiết kế của DỰ ÁN phải tới được prompt ═══════════


def test_thu_vien_mau_prompt_duoc_DOC(tmp_path: Path) -> None:
    """`PromptLibrary` được nạp vào kho tri thức mà không đường nào đọc nó.

    Nó là cơ chế thiết kế dành riêng cho việc này: *"mẫu của dự án ghi đè mẫu
    của pack… để một dự án chỉnh được cách diễn đạt cho bài toán của nó"*
    (NFR-05). Chưa nối thì tri thức thiết kế của dự án không có đường vào.
    """
    from eaa.composer import _boi_canh_mau_du_an
    from eaa.kb import PromptLibrary

    du_an = tmp_path / "da"
    (du_an / "prompts").mkdir(parents=True)
    (du_an / "prompts" / "logic_pid.md").write_text(
        "---\nid: logic_pid\ndescription: luật thiết kế\n---\n"
        "Đạo hàm lấy theo SỐ ĐO, không theo sai số.\n",
        encoding="utf-8",
    )
    thu_vien = PromptLibrary(None, du_an / "prompts")

    van_ban = _boi_canh_mau_du_an(thu_vien, "logic_pid")
    assert "SỐ ĐO" in van_ban


def test_mau_cua_module_KHAC_thi_khong_lay(tmp_path: Path) -> None:
    """Nhét luật của module này vào prompt module kia là làm nhiễu, không làm giàu."""
    from eaa.composer import _boi_canh_mau_du_an
    from eaa.kb import PromptLibrary

    du_an = tmp_path / "da"
    (du_an / "prompts").mkdir(parents=True)
    (du_an / "prompts" / "logic_pid.md").write_text("Luật của PID.\n", encoding="utf-8")

    assert _boi_canh_mau_du_an(PromptLibrary(None, du_an / "prompts"), "drv_i2c") == ""


def test_khong_co_thu_vien_thi_khong_sap() -> None:
    from eaa.composer import _boi_canh_mau_du_an

    assert _boi_canh_mau_du_an(None, "mod_x") == ""


def test_luat_thiet_ke_SONG_SOT_qua_vong_va() -> None:
    """Vòng vá bỏ lớp `task`. Luật thiết kế nằm trong đó là biến mất đúng lúc
    mô hình đang sửa mã — lúc dễ tái phạm nhất.

    SL-133 chính là thế: mô hình viết `tests/test_dummy.c` trong một vòng vá,
    khi không còn dòng nào nói cổng ấy chạy pytest.
    """
    import inspect

    from eaa.composer import PromptComposer

    nguon = inspect.getsource(PromptComposer.build_repair)
    assert 'l.name != "task"' in nguon, "vòng vá không còn bỏ lớp task — đọc lại bài này"

    dung = inspect.getsource(PromptComposer.build)
    for ten in ('"project_rules"', '"host_test"'):
        assert ten in dung, f"{ten} phải là LỚP RIÊNG, không nằm trong lớp task"


def test_lop_vuot_ngan_sach_phai_noi_RUT_GON_O_DAU() -> None:
    """Cổng chặn đúng mà chỉ sang chỗ không liên quan thì vẫn là ngõ cụt.

    Gặp hai lần trong một buổi: lớp `task` vượt phần, rồi lớp `project_rules`
    vượt phần. Cả hai lần thông báo nói đúng một câu — *"giảm top-k chunk, rút
    gọn lớp interface, chưng cất thêm quy tắc lỗi"* — ba việc **không liên quan
    gì** tới hai lớp ấy. Người vừa viết dài một tệp mẫu prompt bị chỉ sang ba
    chỗ khác, và phải tự suy ra chỗ đúng.
    """
    from eaa.llm.base import BudgetExceeded, Prompt, PromptLayer

    prompt = Prompt(
        system_instruction="",
        layers=[PromptLayer("project_rules", "chữ " * 500, budget=10)],
        module="mod_x",
    )
    try:
        prompt.check_budget()
    except BudgetExceeded as exc:
        loi = str(exc)
    else:  # pragma: no cover - phải vượt mới đúng đề bài
        pytest.fail("không báo vượt ngân sách")

    assert "prompts/" in loi, (
        "báo lớp `project_rules` vượt phần mà không nói tệp mẫu prompt nằm ở "
        f"đâu để rút gọn:\n{loi}"
    )


def test_moi_lop_deu_co_loi_khuyen_rieng() -> None:
    """Một lớp không có lối đi tiếp là một ngõ cụt còn sót."""
    from eaa.llm.base import LAYER_BUDGETS
    from eaa.llm.base import _LOI_KHUYEN_LOP as khuyen

    thieu = sorted(set(LAYER_BUDGETS) - set(khuyen))
    assert not thieu, f"các lớp này vượt phần mà không nói rút gọn ở đâu: {thieu}"


def test_ngan_sach_lop_van_cong_dung_tran_tong() -> None:
    """Thêm lớp thì phần của nó phải lấy từ đâu đó, không phải in thêm ra."""
    from eaa.llm.base import LAYER_BUDGETS, TOTAL_BUDGET

    assert sum(LAYER_BUDGETS.values()) == TOTAL_BUDGET
    for ten in ("project_rules", "host_test"):
        assert LAYER_BUDGETS.get(ten), f"lớp {ten} không có ngân sách riêng"


# ═══════════ dự án robot_balance phải khai hai luật ấy ═══════════


def test_du_an_khai_luat_thiet_ke_cho_PID() -> None:
    """Hai lỗi kinh điển đã nằm trong `sim/controller.py` từ đầu.

    Chúng ở đó dưới dạng văn xuôi trong docstring của một tệp mà bộ sinh mã
    không đọc. Đưa chúng thành mẫu prompt của dự án là biến một ghi chú cho
    người thành một ràng buộc cho máy.
    """
    mau = REPO / "projects" / "robot_balance" / "prompts" / "logic_pid.md"
    assert mau.is_file(), "dự án chưa khai luật thiết kế cho logic_pid"

    van_ban = mau.read_text(encoding="utf-8").lower()
    assert "số đo" in van_ban, "chưa nói đạo hàm lấy theo số đo"
    assert "fixed-point" in van_ban or "dấu phẩy tĩnh" in van_ban
    assert "bão hòa" in van_ban or "windup" in van_ban
