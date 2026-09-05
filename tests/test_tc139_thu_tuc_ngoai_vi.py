"""TC-139 — thủ tục theo ngoại vi, lớp K9 (V4, SL-180).

Xem `docs/KE_HOACH_VUOT_LEN.md` §4 và `eaa/procedure.py`.

Bốn luật bài này canh
---------------------

1. **Chưa duyệt G2 thì không vào prompt.** Kỹ năng là tri thức, và tri thức
   vào kho qua đúng một cửa.
2. **Ngân sách MƯỢN của lớp trích đoạn, không cộng thêm.** Nếu bật thủ tục làm
   prompt dài thêm thì mọi cải thiện đo được sau đó đều có thể chỉ là *"nhiều
   ngữ cảnh hơn"*, và ablation của V4 không kết luận được gì.
3. **Mỗi bẫy phải có xuất xứ, và bẫy ĐÃ XẢY RA khác bẫy NGHĨ RA.**
4. **Lược thì lược nguyên mục và NÓI RA.** Một thủ tục bị cắt giữa câu vẫn
   trông như một thủ tục đầy đủ.
"""

from __future__ import annotations

import pathlib

import pytest

from eaa.confidence import DA_KIEM, GIA_DINH, KHONG_KIEM_DUOC, SUY_RA
from eaa.llm.base import LAYER_BUDGETS, TOTAL_BUDGET, estimate_tokens
from eaa.procedure import (
    TT_DA_DUYET,
    TT_DE_XUAT,
    Bay,
    KhoKyNang,
    KyNang,
    ProcedureError,
    lop_ky_nang,
    ngan_sach_co_ky_nang,
)

GOC = pathlib.Path(__file__).resolve().parents[1]


def _bay(muc: str = DA_KIEM) -> Bay:
    return Bay(mo_ta="làm X", dung_la="phải làm Y", xuat_xu="quyết định G3 #5", muc=muc)


def _ky(**thay) -> KyNang:
    goc = dict(id="p1", peripheral="BUS", thu_tu=("bước một",),
               bay=(_bay(),), status=TT_DA_DUYET)
    goc.update(thay)
    return KyNang(**goc)


# ── 1 · chưa duyệt G2 thì không vào prompt ───────────────────────────────────


def test_thu_tuc_CHUA_DUYET_khong_bao_gio_vao_prompt() -> None:
    """Cửa sau nguy hiểm hơn cửa trước hỏng: không ai nhớ nó tồn tại."""
    assert lop_ky_nang([_ky(status=TT_DE_XUAT)]) == ""
    assert lop_ky_nang([_ky(status="verified")]) == ""
    assert lop_ky_nang([_ky(status=TT_DA_DUYET)]) != ""


def test_kho_tach_da_duyet_khoi_cho_duyet() -> None:
    kho = KhoKyNang(muc=(_ky(id="a"), _ky(id="b", status=TT_DE_XUAT)))
    assert [k.id for k in kho.da_duyet()] == ["a"]
    assert [k.id for k in kho.cho_duyet()] == ["b"]


def test_KHONG_co_lenh_duyet_thu_tuc_rieng() -> None:
    """`eaa procedure approve` không được tồn tại — G2 là cửa duy nhất."""
    from eaa.cli import build_parser

    import argparse

    for a in build_parser()._actions:
        if isinstance(a, argparse._SubParsersAction) and "procedure" in a.choices:
            con = a.choices["procedure"]
            hanh_dong: set[str] = set()
            for b in con._actions:
                if isinstance(b, argparse._SubParsersAction):
                    hanh_dong |= set(b.choices)
            assert "approve" not in hanh_dong, (
                "có lệnh duyệt thủ tục riêng — đó là cửa sau vòng qua G2"
            )
            return
    pytest.fail("không thấy lệnh `procedure` trong CLI")


# ── 2 · ngân sách mượn, không cộng thêm ──────────────────────────────────────


def test_TONG_ngan_sach_KHONG_doi_khi_bat_thu_tuc() -> None:
    """Luật quan trọng nhất, và nó là luật về PHÉP ĐO.

    Bật thủ tục mà prompt dài thêm thì chênh lệch đo được sau đó có thể chỉ là
    'nhiều ngữ cảnh hơn'. Lúc ấy ablation của V4 không kết luận được gì về
    thủ tục.
    """
    tat = ngan_sach_co_ky_nang(LAYER_BUDGETS, bat=False)
    bat = ngan_sach_co_ky_nang(LAYER_BUDGETS, bat=True)
    assert sum(tat.values()) == sum(bat.values()) == TOTAL_BUDGET


def test_ngan_sach_lay_dung_tu_lop_TRICH_DOAN() -> None:
    """Lấy từ lớp khác thì phép so không còn nói về 'nén thắng trích đoạn'."""
    goc = dict(LAYER_BUDGETS)
    bat = ngan_sach_co_ky_nang(goc, bat=True, muon=300)
    assert bat["skills"] == 300
    assert bat["datasheet_chunks"] == goc["datasheet_chunks"] - 300
    for k in goc:
        if k != "datasheet_chunks":
            assert bat[k] == goc[k], f"lớp {k} bị đụng vào"


def test_tat_thu_tuc_tra_ve_dung_hanh_vi_truoc_khi_co_no() -> None:
    """Nhánh ĐỐI CHỨNG của ablation phải là hành vi mặc định, không cần dựng gì."""
    assert ngan_sach_co_ky_nang(LAYER_BUDGETS, bat=False) == {
        **LAYER_BUDGETS, "skills": 0
    }


def test_muon_khong_vuot_qua_cai_dang_co() -> None:
    n = ngan_sach_co_ky_nang({"datasheet_chunks": 100}, bat=True, muon=800)
    assert n["skills"] == 100 and n["datasheet_chunks"] == 0


# ── 3 · bẫy phải có xuất xứ, và phân hạng bằng chứng ─────────────────────────


@pytest.mark.parametrize("thieu", ["mo_ta", "dung_la", "xuat_xu"])
def test_bay_thieu_truong_bi_chan_NGAY_LUC_NAP(thieu: str) -> None:
    """Một bẫy không nói được nó đến từ đâu là một lời khai.

    Và lời khai nằm trong prompt thì mô hình đọc nó y như đọc sự thật.
    """
    d = dict(mo_ta="x", dung_la="y", xuat_xu="z")
    d[thieu] = "   "
    with pytest.raises(ProcedureError):
        Bay(**d)


def test_muc_KHONG_KIEM_DUOC_khong_duoc_vao_bay() -> None:
    """Bẫy không kiểm được thì thuộc về câu hỏi cho người, không thuộc prompt."""
    with pytest.raises(ProcedureError):
        Bay(mo_ta="x", dung_la="y", xuat_xu="z", muc=KHONG_KIEM_DUOC)


def test_phan_biet_bay_DA_XAY_RA_voi_bay_NGHI_RA() -> None:
    """Trộn hai hạng là bỏ mất chính thứ làm kho này khác một tập lời khuyên."""
    assert _ky(bay=(_bay(DA_KIEM),)).co_bang_chung_that
    assert not _ky(bay=(_bay(GIA_DINH), _bay(SUY_RA))).co_bang_chung_that
    van = lop_ky_nang([_ky(bay=(_bay(DA_KIEM),))])
    assert f"[{DA_KIEM}]" in van


def test_thu_tuc_tro_vao_trich_doan_KHONG_CO_THAT_bi_neu_ra() -> None:
    """Cùng hạng lỗi TC-145 chặn ở gợi ý CLI: mũi tên chỉ vào tường."""
    kho = KhoKyNang(muc=(_ky(chunks=("ds-co-that", "ds-bia-ra")),))
    assert kho.chunk_thieu({"ds-co-that"}) == ["p1 → ds-bia-ra"]
    assert kho.chunk_thieu({"ds-co-that", "ds-bia-ra"}) == []


# ── 4 · lược thì lược nguyên mục và nói ra ───────────────────────────────────


def test_luoc_bo_NGUYEN_MUC_chu_khong_cat_giua_cau() -> None:
    nhieu = _ky(bay=tuple(_bay(GIA_DINH) for _ in range(30)))
    van = lop_ky_nang([nhieu], tran=200, dem=estimate_tokens)
    assert "ĐÃ LƯỢC" in van
    # Mỗi dòng bẫy còn lại vẫn là một dòng trọn vẹn.
    for d in van.splitlines():
        if d.strip().startswith("- ["):
            assert "→" in d and d.rstrip().endswith(")")


def _dong_bay(van: str) -> list[str]:
    """Chỉ những DÒNG BẪY, không tính phần đầu của lớp.

    Bản đầu của bài dưới đây tìm chuỗi `[ĐÃ KIỂM]` ở bất kỳ đâu trong lớp — mà
    phần đầu lớp vốn đã có sẵn chuỗi ấy trong câu giải thích nhãn. Bài kiểm
    xanh bất kể thứ tự lược, và đột biến đảo thứ tự đi qua được. Đây là hạng
    bài kiểm rỗng mà `sensitivity.py` sinh ra để bắt.
    """
    return [d.strip() for d in van.splitlines() if d.strip().startswith("- [")]


def test_luoc_bay_GIA_DINH_TRUOC_bay_DA_KIEM() -> None:
    """Bẫy ĐÃ KIỂM là bẫy đã xảy ra thật — nó ra đi sau cùng.

    Tính chất đúng KHÔNG phải "mọi bẫy còn lại đều ĐÃ KIỂM": vòng lược dừng
    ngay khi vừa đủ, nên nó thường chưa kịp bỏ hết bẫy mức thấp. Tính chất
    đúng là: **bẫy ĐÃ KIỂM còn sống chừng nào còn bẫy nào sống**, và bẫy mức
    thấp là bẫy bị bỏ.
    """
    k = _ky(bay=tuple(_bay(GIA_DINH) for _ in range(20)) + (_bay(DA_KIEM),))
    dong = _dong_bay(lop_ky_nang([k], tran=400, dem=estimate_tokens))
    assert 0 < len(dong) < 21, "trần này không phân biệt được gì"
    assert any(f"[{DA_KIEM}]" in d for d in dong), (
        "bẫy đã xảy ra thật bị lược trong khi bẫy nghĩ ra còn sống"
    )
    assert sum(1 for d in dong if f"[{GIA_DINH}]" in d) < 20, "chưa lược gì"


def test_bay_DA_KIEM_ra_di_SAU_CUNG_ke_ca_khi_tran_rat_chat() -> None:
    """Chiều gắt nhất: trần chặt tới mức chỉ còn một bẫy thì bẫy ấy phải là
    bẫy đã xảy ra thật."""
    k = _ky(bay=tuple(_bay(SUY_RA) for _ in range(20)) + (_bay(DA_KIEM),))
    assert len(_dong_bay(lop_ky_nang([k]))) == 21

    # Quét dần cho tới lúc chỉ còn một bẫy — đó là chỗ thứ tự lược lộ ra rõ nhất.
    con_mot = None
    for tran in range(150, 500, 5):
        dong = _dong_bay(lop_ky_nang([k], tran=tran, dem=estimate_tokens))
        if len(dong) == 1:
            con_mot = dong
            break
    assert con_mot is not None, "không tìm được trần nào để lại đúng một bẫy"
    assert f"[{DA_KIEM}]" in con_mot[0], (
        f"bẫy cuối cùng sống sót lại là bẫy nghĩ ra: {con_mot}"
    )


def test_ghi_chu_LUOC_khong_dai_them_theo_so_muc_bi_luoc() -> None:
    """Bản đầu ghi một dòng cho MỖI bẫy bị lược, nên chính ghi chú ấy ăn hết
    chỗ nó vừa giải phóng — vòng lược không hội tụ và nó lược luôn cả bẫy
    ĐÃ KIỂM. Ghi chú phải gom thành số đếm."""
    it = _ky(bay=tuple(_bay(GIA_DINH) for _ in range(10)))
    nhieu = _ky(bay=tuple(_bay(GIA_DINH) for _ in range(80)))

    def ghi_chu(k: KyNang) -> str:
        # Trần đặt bằng NỬA kích thước đầy đủ của chính ca ấy, để cả hai ca
        # chắc chắn có lược — so hai ghi chú mà một ca không lược thì không so
        # được gì.
        tran = estimate_tokens(lop_ky_nang([k])) // 2
        van = lop_ky_nang([k], tran=tran, dem=estimate_tokens)
        return van.split("ĐÃ LƯỢC")[1] if "ĐÃ LƯỢC" in van else ""

    a, b = ghi_chu(it), ghi_chu(nhieu)
    assert a and b, "cả hai ca đều phải có lược để so được"
    assert abs(len(b) - len(a)) < 40, (
        f"ghi chú dài thêm theo số mục bị lược: {len(a)} → {len(b)} ký tự"
    )


# ── 5 · ba tầng: engine giữ mô hình, dữ liệu ở pack và dự án ─────────────────


def test_engine_KHONG_giu_mot_hang_so_phan_cung_nao() -> None:
    """TC-38 quét cả `eaa/`; bài này nói riêng vì viết thủ tục là việc đầy cám
    dỗ gõ thẳng tên thanh ghi vào engine."""
    van = (GOC / "eaa/procedure.py").read_text().lower()
    for tu in ("twbr", "twsr", "twcr", "atmega", "mpu6050", "0x6b", "0x3b"):
        assert tu not in van, f"hằng số phần cứng {tu!r} lẻn vào engine"


def test_du_lieu_that_cua_kho_nap_duoc_va_dung_tang() -> None:
    pack = GOC / "packs/avr/procedures"
    du_an = GOC / "projects/robot_balance/procedures"
    if not pack.is_dir() or not du_an.is_dir():
        pytest.skip("chưa có dữ liệu thủ tục trong kho này")

    kho = KhoKyNang.nap_nhieu(pack, du_an)
    assert kho.tat_ca(), "nạp được 0 thủ tục"
    for k in kho.tat_ca():
        assert k.thu_tu, f"{k.id} không có bước nào — thủ tục mà không nói thứ tự"
        assert k.bay, f"{k.id} không có bẫy nào"
        assert k.co_bang_chung_that, (
            f"{k.id} chưa có bẫy nào rút từ chuyện đã xảy ra — nó là lời khuyên"
        )
        assert not k.da_duyet, (
            f"{k.id} đã ở trạng thái duyệt trong Git — G2 là việc của NGƯỜI, "
            "không phải một dòng YAML"
        )

    # Ngoại vi của vi điều khiển thuộc pack; linh kiện ngoài thuộc dự án.
    tu_pack = {k.peripheral for k in KhoKyNang.nap(pack).tat_ca()}
    tu_du_an = {k.peripheral for k in KhoKyNang.nap(du_an).tat_ca()}
    assert tu_pack and tu_du_an and not (tu_pack & tu_du_an)


def test_trung_id_giua_hai_nguon_la_LOI_chu_khong_de_len_nhau() -> None:
    """Cái nào vào prompt không được là chuyện của thứ tự đối số."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        a, b = pathlib.Path(d) / "a", pathlib.Path(d) / "b"
        a.mkdir(); b.mkdir()
        noi_dung = ("id: trung\nperipheral: X\nthu_tu: [b1]\n"
                    "bay:\n  - de_sai: x\n    dung_la: y\n    xuat_xu: z\n")
        (a / "t.yaml").write_text(noi_dung)
        (b / "t.yaml").write_text(noi_dung)
        with pytest.raises(ProcedureError, match="trung"):
            KhoKyNang.nap_nhieu(a, b)


# ── 6 · điều V4 CHƯA đo được ─────────────────────────────────────────────────


def test_ablation_chua_do_duoc_va_dieu_ay_phai_duoc_noi_ra() -> None:
    """V4 dựng CƠ CHẾ; con số pass@k trước/sau cần bộ nhiệm vụ của V2.

    Bài này giữ cho `MUON_TU_CHUNK` khỏi bị đọc thành một con số đã được đo.
    """
    from eaa import procedure

    assert "CANH BẠC" in procedure.__doc__ or "CANH BẠC" in (
        pathlib.Path(procedure.__file__).read_text()
    ), "mất lời khai rằng con số mượn ngân sách chưa được đo"
