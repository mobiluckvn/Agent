"""TC-96 — phép so "thuộc tập chấp nhận được", và vì sao nó không phải `equals` nới ra.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-122.

Tìm ra ở Bài 2 phiên kiểm bo thật. Con cảm biến trên bo trả mã nhận dạng
``0x72`` trong khi hồ sơ khai ``0x68``. Đo trên chính bo ấy cho thấy nó **tương
thích thanh ghi** ở mọi thanh ghi dự án dùng — địa chỉ bus, thanh ghi nguồn,
đọc chùm dữ liệu, và cả hệ số thang đo (nhiễu quy ra 0,36 mg và 0,03 °/s, đúng
dải vật lý; dải đo mặc định khác thì hai số ấy đã lệch hẳn một hệ số).

Nên câu đúng không phải *"mã nhận dạng phải là 0x68"*, mà là *"mã nhận dạng
phải nằm trong tập đã được kiểm chứng là dùng được"*.

Vì sao không sửa `expected` thành ``0x72`` cho xong
---------------------------------------------------

Vì như thế là **đánh mất `0x68`**. Cắm con chip đúng như thiết kế vào thì phép
kiểm lại đỏ, và người ta sẽ sửa tiếp — mỗi lần một giá trị, mỗi lần mất giá trị
cũ. Sau vài vòng, phép kiểm nhận dạng chỉ còn nhớ con chip cắm gần nhất.

Và vì sao không bỏ hẳn phép kiểm: nó là câu hỏi RẺ NHẤT trong cả kịch bản —
*"có đúng con chip ta nghĩ không"*. Sai ở đây thì mọi thanh ghi sau đều đọc
nhầm bảng.

`one_of` giữ được cả hai: tập **mở rộng có chủ ý**, từng giá trị vào tập là một
lần người quyết định, và cắm con thứ ba vẫn bị bắt.
"""

from __future__ import annotations

import pytest

from eaa.diagnostics import DiagnosticError, MachineCriterion


def _kiem(**kw) -> MachineCriterion:
    return MachineCriterion(key="ma", description="Mã nhận dạng", **kw)


def test_gia_tri_trong_tap_thi_DAT() -> None:
    k = _kiem(op="one_of", expected=["0x68", "0x72"])
    dat, mo_ta = k.evaluate({"ma": "0x72"})
    assert dat
    assert "0x72" in mo_ta and "0x68" in mo_ta, "phải nêu cả giá trị đo và cả tập"


def test_gia_tri_NGOAI_tap_thi_TRUOT() -> None:
    """Cắm con thứ ba vẫn phải bị bắt — đó là lý do phép kiểm này tồn tại."""
    dat, _ = _kiem(op="one_of", expected=["0x68", "0x72"]).evaluate({"ma": "0x71"})
    assert not dat


def test_khong_phan_biet_hoa_thuong() -> None:
    dat, _ = _kiem(op="one_of", expected=["0X68"]).evaluate({"ma": "0x68"})
    assert dat


def test_tap_MOT_phan_tu_van_chay() -> None:
    """Khai một giá trị thì `one_of` phải cư xử y như `equals`."""
    assert _kiem(op="one_of", expected=["0x68"]).evaluate({"ma": "0x68"})[0]
    assert not _kiem(op="one_of", expected=["0x68"]).evaluate({"ma": "0x72"})[0]


def test_khai_mot_chuoi_tran_thi_cung_chap() -> None:
    """Người viết YAML quên dấu ngoặc vuông là chuyện thường; đừng sập vì thế."""
    assert _kiem(op="one_of", expected="0x68").evaluate({"ma": "0x68"})[0]


def test_tap_RONG_thi_BAO_LOI_chu_khong_am_tham_dat() -> None:
    """Tập rỗng nghĩa là "không giá trị nào chấp nhận được".

    Trả ĐẠT ở đây là hỏng theo hướng nguy hiểm: một phép kiểm khai thiếu dữ
    liệu sẽ im lặng cho mọi thứ đi qua. Trả TRƯỢT thì đúng về mặt logic nhưng
    người đọc không biết vì sao. Nói ra là đường duy nhất còn lại.
    """
    with pytest.raises(DiagnosticError, match="(?i)rỗng"):
        _kiem(op="one_of", expected=[]).evaluate({"ma": "0x68"})


def test_thieu_truong_thi_TRUOT_nhu_moi_phep_so_khac() -> None:
    dat, mo_ta = _kiem(op="one_of", expected=["0x68"]).evaluate({})
    assert not dat and "không có trường" in mo_ta


# ═══════════ hồ sơ và kịch bản thật của dự án ═══════════


def test_ho_so_phan_cung_ghi_KEM_BANG_CHUNG() -> None:
    """Nới một phép kiểm nhận dạng phải kèm lý do, ngay cạnh con số.

    Bằng chứng nằm trong commit message là bằng chứng không ai đọc lại. Sáu
    tháng sau, người đọc hồ sơ phải thấy được VÌ SAO tập này có hai giá trị.
    """
    from pathlib import Path

    ho_so = (Path(__file__).resolve().parents[1] / "projects" / "robot_balance"
             / "hardware_profile.yaml").read_text(encoding="utf-8")
    assert "0x72" in ho_so, "chưa ghi mã đo được"
    assert "0x68" in ho_so, "đánh mất mã của con chip đúng thiết kế"
    # Lý do phải nằm ngay đó, không phải ở chỗ khác.
    assert "tương thích" in ho_so.lower() or "đo được" in ho_so.lower()


def test_kich_ban_DS02_dung_one_of() -> None:
    from pathlib import Path

    import yaml

    d = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "projects" / "robot_balance"
         / "diagnostics.yaml").read_text(encoding="utf-8")
    )
    ds02 = next(s for s in d["scenarios"] if s["id"] == "DS-02")
    kiem = next(m for m in ds02["machine"] if m["key"] == "who_am_i")
    assert kiem["op"] == "one_of"
    assert set(str(x).lower() for x in kiem["expected"]) == {"0x68", "0x72"}
