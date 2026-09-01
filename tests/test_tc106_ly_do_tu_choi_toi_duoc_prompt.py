"""TC-106 — lý do người từ chối gate phải TỚI ĐƯỢC prompt lần sinh lại.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-136.

Tìm ra ngay sau SL-135, khi đang KIỂM một lời hứa thay vì tin nó. `eaa gate
reject` in ra:

    Lý do đã ghi vào Error Ledger và sẽ có mặt trong prompt lần sinh lại.

Dựng lại đúng prompt ấy ngoài luồng và đếm:

    == token theo lớp ==
      datasheet_chunks     42
      project_rules        988
      host_test            423
      task                 311
      system_instruction   306
      TỔNG: 2070
    == đã bị lược == ['error_rules']

**Lý do từ chối không có trong prompt.** Prompt dùng 2070/8000 — thừa 5930
token — mà lớp 300 token bị xóa SẠCH.

Ba chỗ hợp lại thành một chỗ mất
---------------------------------

1.  `LedgerEntry.as_rule` chặn độ dài ở nhánh SUY RA từ mô tả lỗi, và **không
    chặn nhánh quy tắc do người viết** — đúng nhánh mà `gate reject` dùng, và
    đúng nhánh dễ dài, vì người viết lý do thì viết cho người đọc.
2.  `_lop_quy_tac_loi` lấy top-3 rồi ghép thẳng, không nhét vừa phần của lớp.
3.  Lớp vượt phần → bộ lược ngân sách **xóa cả lớp**, không cắt bớt.

Và cái giấu được cả ba là chỗ thứ tư
-------------------------------------

`prompt.trimmed` có từ sprint đầu, chú thích ghi *"để KPI theo dõi"*. KPI chưa
bao giờ nhận được nó; không lệnh nào in nó ra. Nên việc lược là **im lặng tuyệt
đối** — mã sinh ra thiếu đúng phần quan trọng nhất và không dòng nào nói.

Lần thứ SÁU của dạng "mã đúng nằm chết".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaa.composer import ComposerConfig, PromptComposer, Task


class _DoiGia:
    """Đồ thị tối giản — lớp quy tắc lỗi chỉ hỏi nó danh sách thanh ghi."""

    graph: Any = type("G", (), {"has_node": staticmethod(lambda _: True)})()

    @staticmethod
    def registers_for(_module: str) -> tuple[str, ...]:
        return ()


class _SoGia:
    """Nhật ký lỗi trả về đúng những quy tắc được đưa vào."""

    def __init__(self, *quy_tac: str) -> None:
        self._quy_tac = list(quy_tac)

    def rules_for(self, *_a: Any, **_k: Any) -> list[str]:
        return self._quy_tac


def _bo_ghep(ledger: Any) -> PromptComposer:
    bo = PromptComposer.__new__(PromptComposer)
    bo.kb = None
    bo.graph = _DoiGia()
    bo.ledger = ledger
    bo.config = ComposerConfig()
    bo.host_test = None
    return bo


_LY_DO_THAT = (
    "KHÔNG lặp lại lỗi đã bị từ chối tại G3: Hai chỗ ở review. (1) hàm đặt hệ số "
    "kiêm luôn khởi tạo nên đổi hệ số giữa chừng xóa sạch trạng thái đang giữ hệ "
    "đứng, mỗi lần chỉnh là một cú giật. (2) chu kỳ cố định gộp trong hệ số nhưng "
    "không dòng nào ghi cách quy đổi từ hệ số SI của bản tham chiếu sang số nguyên, "
    "cũng không ghi đơn vị của điểm đặt, số đo và giá trị trả về, nên bảng tham số "
    "quét được từ mô phỏng thành một dãy số không ai dùng được."
)


def test_ly_do_tu_choi_DAI_van_vao_duoc_lop_quy_tac() -> None:
    """Điểm cốt lõi: một lý do viết cẩn thận không được biến mất vì nó dài."""
    from eaa.llm.base import LAYER_BUDGETS, estimate_tokens

    bo = _bo_ghep(_SoGia(_LY_DO_THAT, "KHÔNG lặp lại: lỗi cũ đã sửa"))
    van_ban = bo._lop_quy_tac_loi(Task(module_id="logic_pid"), ())

    assert van_ban.strip(), "lớp quy tắc rỗng — lý do từ chối không tới được prompt"
    assert estimate_tokens(van_ban) <= LAYER_BUDGETS["error_rules"], (
        "vượt phần của lớp, và lúc ấy bộ lược ngân sách sẽ xóa sạch cả lớp"
    )
    assert "đổi hệ số giữa chừng" in van_ban, "phần đầu của lý do bị mất"


def test_giu_NGUYEN_VEN_quy_tac_dau_bang_thay_vi_cat_cut_ca_ba() -> None:
    """Thà một quy tắc đủ nghĩa còn hơn ba quy tắc cụt.

    Quy tắc đầu bảng là lỗi của CHÍNH module này, vừa bị người từ chối. Hai
    quy tắc sau là lỗi cũ đã khép. Cắt cụt cả ba để "công bằng" là làm hỏng
    cái quan trọng nhất.
    """
    bo = _bo_ghep(_SoGia(_LY_DO_THAT, "x " * 200, "y " * 200))
    van_ban = bo._lop_quy_tac_loi(Task(module_id="logic_pid"), ())

    assert _LY_DO_THAT in van_ban, "quy tắc đầu bảng bị cắt dù nó vừa phần của lớp"


def test_quy_tac_DAU_BANG_khong_duoc_nhuong_cho_quy_tac_CU_HON() -> None:
    """Bẫy của chính bản sửa đầu tiên, và nó lặng lẽ y như lỗi gốc.

    "Nhét vừa" theo kiểu duyệt lần lượt và bỏ qua cái không vừa sẽ **nhảy qua**
    lý do từ chối MỚI NHẤT (dài, vì người vừa review kỹ) để giữ lý do của vòng
    TRƯỚC (ngắn hơn, và đã sửa xong rồi). Nhìn vào prompt thì thấy có lớp quy
    tắc, có vẻ ổn — chỉ là nó dạy mô hình tránh đúng cái lỗi nó vừa tránh.

    Phát hiện bằng cách in thẳng nội dung lớp ra xem, chứ không phải bằng cách
    tin rằng "đã nhét vừa" nghĩa là "nhét đúng cái cần".
    """
    moi_va_dai = "KHÔNG lặp lại lỗi vừa bị từ chối: " + "chi tiết review " * 90
    cu_va_ngan = "KHÔNG lặp lại: lỗi cũ đã sửa xong"

    bo = _bo_ghep(_SoGia(moi_va_dai, cu_va_ngan))
    van_ban = bo._lop_quy_tac_loi(Task(module_id="logic_pid"), ())

    assert "lỗi vừa bị từ chối" in van_ban, (
        "quy tắc đầu bảng bị bỏ để lấy quy tắc cũ hơn chỉ vì nó ngắn hơn"
    )


def test_qua_dai_thi_CAT_CO_DAU_chu_khong_bien_mat() -> None:
    """Kể cả quy tắc đầu bảng cũng không vừa: cắt, và nói là đã cắt."""
    bo = _bo_ghep(_SoGia("KHÔNG lặp lại: " + "chữ dài " * 400))
    van_ban = bo._lop_quy_tac_loi(Task(module_id="logic_pid"), ())

    assert van_ban.strip(), "biến mất thay vì cắt"
    assert "rút gọn" in van_ban, "cắt mà không nói là đã cắt"
    assert "ledger" in van_ban.lower(), "không chỉ chỗ đọc bản đầy đủ"


def test_khong_co_nhat_ky_thi_khong_sap() -> None:
    assert _bo_ghep(None)._lop_quy_tac_loi(Task(module_id="m"), ()) == ""


def test_khong_co_quy_tac_thi_lop_rong() -> None:
    assert _bo_ghep(_SoGia())._lop_quy_tac_loi(Task(module_id="m"), ()) == ""


# ═══════════ việc lược bỏ KHÔNG được im lặng ═══════════


def test_co_cau_noi_ra_rang_prompt_da_bi_luoc() -> None:
    """Không có câu này thì mọi mất mát ngữ cảnh đều vô hình."""
    from eaa.orchestrator import Orchestrator

    class _P:
        trimmed = ["error_rules", "interfaces→chỉ khai báo"]

    cau = Orchestrator.canh_bao_luoc(_P())
    assert "error_rules" in cau and "interfaces" in cau
    assert cau.strip(), "lược rồi mà không nói gì"


def test_khong_luoc_gi_thi_khong_noi_gi() -> None:
    """Cảnh báo lúc nào cũng hiện thì chẳng mấy chốc không ai đọc nó nữa."""
    from eaa.orchestrator import Orchestrator

    class _P:
        trimmed: list[str] = []

    assert Orchestrator.canh_bao_luoc(_P()) == ""
    assert Orchestrator.canh_bao_luoc(object()) == ""


def test_KPI_ghi_lai_lop_da_bi_luoc() -> None:
    """`prompt.trimmed` mang chú thích "để KPI theo dõi" từ sprint đầu.

    KPI chưa bao giờ nhận được nó. Vòng tự sửa chạm N vì THIẾU NGỮ CẢNH là một
    chẩn đoán khác hẳn vì mã khó, và phân biệt được hai thứ ấy là lý do trường
    này tồn tại (AIS §12).
    """
    import inspect

    from eaa.orchestrator import Orchestrator

    nguon = inspect.getsource(Orchestrator._sinh_ma)
    assert "trimmed" in nguon, "KPI vẫn không biết prompt đã bị lược phần nào"


def test_vong_va_cung_noi_ra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vòng vá là chỗ ngân sách chật nhất, nên cũng là chỗ dễ mất ngữ cảnh nhất."""
    import inspect

    from eaa.orchestrator import Orchestrator

    nguon = inspect.getsource(Orchestrator._va_loi)
    assert "canh_bao_luoc" in nguon, "vòng vá lược ngữ cảnh mà không nói"
