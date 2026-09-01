"""TC-109 — phân rã lần thứ hai trên một dự án ĐANG SỐNG.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-140.

Tìm ra khi chạy `eaa plan propose` lần thứ hai, sau khi hồ sơ phần cứng khai
thêm còi và nút nhấn::

    Lỗi: Module 'app_ui' phụ thuộc vào module không có trong bản phân rã:
         ['app_balance']

Mô hình làm đúng: `app_balance` đã nằm trong backlog và đã được duyệt, nên
module mới phụ thuộc vào nó là chuyện bình thường. Chỗ sai nằm ở bộ kiểm.

Nửa còn lại của SL-131
-----------------------

SL-131 dạy BỘ PHÂN RÃ biết những module đã có: `propose(..., existing=...)`
đưa danh sách ấy vào prompt và chặn đề xuất trùng tên. Nhưng
`DecompositionPlan` — cái đối tượng mang kết quả — vẫn giữ giả định cũ rằng
**một bản phân rã là tự đủ**. Nên bộ phân rã biết, còn bản phân rã thì không,
và mọi vòng phân rã thứ hai đều chết ở khâu kiểm tính nhất quán.

Không ai thấy suốt bốn sprint vì đây là lần đầu có dự án chạy tới vòng thứ
hai: mọi bài kiểm cũ đều dựng một bản phân rã từ backlog rỗng.

Vì sao không nới lỏng phép kiểm
--------------------------------

Cách sai là bỏ luôn phép kiểm phụ thuộc. Phép kiểm ấy bắt lỗi thật — mô hình
nêu một cái tên nó chưa từng đề xuất. Cách đúng là cho bản phân rã BIẾT tập
module đã tồn tại, rồi vẫn kiểm nghiêm ngặt trên tập hợp đầy đủ.
"""

from __future__ import annotations

import pytest

from eaa.decompose import DecomposeError, DecompositionPlan, ModuleProposal


def _mod(ma: str, **kw) -> ModuleProposal:
    return ModuleProposal(id=ma, purpose=f"làm việc của {ma}", **kw)


def test_phu_thuoc_vao_module_DA_CO_thi_hop_le() -> None:
    """Đúng cảnh đã gặp: module mới dựa vào module đã duyệt từ vòng trước."""
    ban = DecompositionPlan(
        modules=(_mod("app_ui", depends_on=("app_balance",)),),
        known=("app_balance", "drv_i2c"),
    )
    assert ban.modules[0].depends_on == ("app_balance",)


def test_phu_thuoc_vao_cai_ten_KHONG_AI_BIET_van_bi_chan() -> None:
    """Nới cho module đã có KHÔNG được biến thành bỏ luôn phép kiểm.

    Một cái tên không có trong bản phân rã và cũng không có trong backlog là
    mô hình nêu ra một module chưa từng tồn tại — đúng thứ phép kiểm này sinh
    ra để bắt.
    """
    with pytest.raises(DecomposeError, match="app_bay"):
        DecompositionPlan(
            modules=(_mod("app_ui", depends_on=("app_bay",)),),
            known=("app_balance",),
        )


def test_khong_khai_known_thi_giu_nguyen_hanh_vi_cu() -> None:
    with pytest.raises(DecomposeError, match="app_balance"):
        DecompositionPlan(modules=(_mod("app_ui", depends_on=("app_balance",)),))


def test_thu_tu_lam_KHONG_liet_ke_module_da_co() -> None:
    """`order()` trả về việc PHẢI LÀM, không phải việc đã xong.

    Nhét module đã merge vào danh sách này sẽ khiến `plan accept` tưởng chúng
    là module mới, và `eaa gen` chạy lại từ đầu trên mã đã duyệt.
    """
    ban = DecompositionPlan(
        modules=(
            _mod("app_ui", depends_on=("app_balance", "drv_buzzer")),
            _mod("drv_buzzer"),
        ),
        known=("app_balance",),
    )
    thu_tu = ban.order()
    assert thu_tu == ["drv_buzzer", "app_ui"]
    assert "app_balance" not in thu_tu


def test_vong_phu_thuoc_van_bi_bat_khi_co_known() -> None:
    """Trừ đi module đã có KHÔNG được làm mất phép bắt vòng phụ thuộc."""
    ban = DecompositionPlan(
        modules=(
            _mod("mod_a", depends_on=("mod_b",)),
            _mod("mod_b", depends_on=("mod_a",)),
        ),
        known=("app_balance",),
    )
    with pytest.raises(DecomposeError, match="vòng"):
        ban.order()


def test_known_song_sot_qua_ghi_va_doc_lai(tmp_path) -> None:
    """Bản phân rã được ghi ra đĩa giữa `propose` và `accept`.

    Mất `known` ở giữa thì `plan accept` dựng lại đối tượng và ném đúng lỗi
    mà `plan propose` vừa vượt qua — chỗ chặn chỉ dời đi một lệnh.
    """
    DecompositionPlan(
        modules=(_mod("app_ui", depends_on=("app_balance",)),),
        known=("app_balance",),
    ).save(tmp_path / "plan.json")

    doc_lai = DecompositionPlan.load(tmp_path / "plan.json")
    assert doc_lai is not None
    assert "app_balance" in doc_lai.known


def test_plan_propose_TRUYEN_known_xuong(tmp_path) -> None:
    """Bộ phân rã đã biết module đã có; bản phân rã phải nhận lại điều đó."""
    import inspect

    from eaa.decompose import LlmDecomposer

    nguon = inspect.getsource(LlmDecomposer.propose)
    assert "known=" in nguon, (
        "`propose` nhận `existing` để dựng prompt mà không chuyển nó vào bản "
        "phân rã — bộ phân rã biết, còn bản phân rã thì không"
    )
