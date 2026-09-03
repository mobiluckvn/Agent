"""TC-122 — lớp vượt phần của nó KHÔNG chặn khi trần TỔNG còn chỗ.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-161.

`check_budget` chặn khi bất kỳ lớp nào vượt phần nominal, kể cả lúc prompt tổng
mới dùng hơn nửa trần. Đo được trong hai ngày làm việc với phần cứng: **mười hai
lần** bị chặn, tổng dao động 3.100–4.300 trên 8.000::

    Prompt trong trần tổng (3997/8000) nhưng có lớp vượt phần của nó.
      - project_rules: 1214 token / ngân sách 1200

Không lần nào là thiếu chỗ thật. Mỗi lần là một vòng đi lại: cắt chữ trong
`prompts/<module>.md`, chạy lại, lại chạm, lại cắt.

Vì sao chặn ở đó là sai
------------------------

Phần của mỗi lớp là cách chia công bằng **khi có tranh chấp**. Trần tổng còn
trống nghĩa là chưa có tranh chấp, nên chặn ở đó là chặn một tình huống giả
định.

Câu biện hộ cho phép kiểm ấy — *"một prompt quá dài luôn có thủ phạm cụ thể"* —
vẫn đúng, và nó vẫn được nói ra ở đúng chỗ nó có nghĩa: khi tổng THẬT SỰ vượt,
danh sách lớp vẫn đi kèm nguyên vẹn.

Vì sao `project_rules` là lớp chạm trần
----------------------------------------

Nó lớn dần theo SỐ BÀI HỌC RÚT TỪ PHẦN CỨNG: mỗi lỗi bắt được trên bo lại thêm
một dòng ràng buộc vào tệp mẫu prompt của module. Một trần cố định đặt lên đại
lượng chỉ tăng là một trần sẽ bị chạm — và bị chạm đúng lúc ta học được nhiều
nhất.

Khác gì SL-147
---------------

SL-147 làm phần của lớp `repair` thành SÀN vì lớp ấy THAY CHỖ lớp `task`, nên
nó không cạnh tranh với ai. `project_rules` thì có cạnh tranh, nên bài này
KHÔNG cho nó lấy chỗ trống — chỉ thôi chặn, và ghi lại để việc phình không diễn
ra trong im lặng.
"""

from __future__ import annotations

import pytest

from eaa.llm.base import BudgetExceeded, Prompt, PromptLayer, estimate_tokens


def _lop(ten: str, so_token: int, ngan_sach: int) -> PromptLayer:
    """Một lớp dài xấp xỉ `so_token` token theo bộ ước lượng."""
    # estimate_tokens nhân 1.3 lần số từ; chọn số từ cho ra xấp xỉ mong muốn.
    so_tu = max(1, int(so_token / 1.3))
    return PromptLayer(name=ten, content=" ".join(["tu"] * so_tu), budget=ngan_sach)


def test_lop_vuot_phan_ma_tong_con_cho_thi_KHONG_chan() -> None:
    """Chỗ SL-161 nằm."""
    prompt = Prompt(layers=[_lop("project_rules", 1_400, 1_200)], budget=8_000)

    prompt.check_budget()  # không được ném

    assert prompt.over_share, "vượt phần mà không ghi lại là phình trong im lặng"
    assert "project_rules" in prompt.over_share[0]


def test_van_chan_khi_tong_that_su_vuot() -> None:
    """Trần TỔNG vẫn là trần thật — bài này canh phần KHÔNG được nới lỏng."""
    prompt = Prompt(
        layers=[_lop("datasheet_chunks", 9_000, 1_500)],
        budget=8_000,
    )

    with pytest.raises(BudgetExceeded) as thong_tin:
        prompt.check_budget()

    assert "vượt ngân sách ngữ cảnh" in str(thong_tin.value)


def test_tong_vuot_thi_VAN_neu_dich_danh_lop_thu_pham() -> None:
    """Lý do tồn tại của phép kiểm theo lớp: chỉ đúng thủ phạm khi thiếu chỗ thật.

    Bỏ chặn ở trường hợp còn chỗ KHÔNG được làm mất khả năng này.
    """
    prompt = Prompt(
        layers=[_lop("datasheet_chunks", 7_000, 1_500), _lop("task", 2_000, 500)],
        budget=8_000,
    )

    with pytest.raises(BudgetExceeded) as thong_tin:
        prompt.check_budget()

    van_ban = str(thong_tin.value)
    assert "Lớp vượt ngân sách" in van_ban
    assert "datasheet_chunks" in van_ban and "task" in van_ban


def test_khong_vuot_gi_thi_over_share_rong() -> None:
    prompt = Prompt(layers=[_lop("project_rules", 500, 1_200)], budget=8_000)
    prompt.check_budget()
    assert prompt.over_share == []


def test_canh_bao_noi_ra_viec_dung_qua_phan() -> None:
    """Không chặn, nhưng cũng không im — người chạy phải thấy được."""
    from eaa.orchestrator import Orchestrator

    prompt = Prompt(layers=[_lop("project_rules", 1_400, 1_200)], budget=8_000)
    prompt.check_budget()

    cau = Orchestrator.canh_bao_luoc(prompt)
    assert "quá phần nominal" in cau
    assert "project_rules" in cau


def test_hai_loai_canh_bao_khong_de_len_nhau() -> None:
    """Lược bỏ và dùng quá phần là hai chuyện khác nhau, phải đọc ra được cả hai."""
    from eaa.orchestrator import Orchestrator

    prompt = Prompt(layers=[_lop("project_rules", 1_400, 1_200)], budget=8_000)
    prompt.trimmed = ["datasheet_chunks"]
    prompt.check_budget()

    cau = Orchestrator.canh_bao_luoc(prompt)
    assert "đã lược khỏi prompt" in cau
    assert "quá phần nominal" in cau


def test_bo_uoc_luong_dung_dung_ham_cua_prompt() -> None:
    """Canh giả định của chính bài kiểm này: `_lop` phải ra đúng cỡ token."""
    lop = _lop("x", 1_300, 1_000)
    assert 1_100 <= estimate_tokens(lop.content) <= 1_500
