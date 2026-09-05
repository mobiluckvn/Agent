"""TC-145 — thông báo lỗi phải nói được VIỆC PHẢI LÀM (SL-178).

Xem `docs/EAA_Benchmark_San_pham.docx` §6 và `docs/SAI_LECH_THIET_KE.md` mục
SL-178.

Phép đo trong báo cáo benchmark chỉ ra một điểm yếu mà so sánh với đối thủ
không chỉ ra được: phần lớn thông báo lỗi nói **cái gì sai** mà không nói
**phải làm gì**. Với một công cụ mà người dùng đang đứng giữa một quy trình có
gate, đó là bỏ họ lại đúng lúc họ cần một mũi tên.

Vì sao sửa Ở MỘT CHỖ chứ không sửa 182 chuỗi
----------------------------------------------

Một gợi ý viết rải rác trong từng thông báo sẽ lệch với lệnh nó nói tới ngay
lần đầu ai đó đổi tên lệnh, và **không gì bắt được chỗ lệch ấy**. Gom vào một
bảng thì bắt được — và bài kiểm quan trọng nhất của tệp này là bài đối chiếu
bảng gợi ý với cây lệnh THẬT.

Đây cũng chính là hình dạng lỗi mà kho này gọi tên nhiều lần nhất: mã lệch với
lời chính nó khai.
"""

from __future__ import annotations

import argparse
import pathlib
import re

from eaa.cli import GOI_Y_KHI_HONG, _goi_y_di_tiep, build_parser

#: Lệnh KHÔNG cần gợi ý, kèm LÝ DO cho từng mục. Đang rỗng — mọi lệnh cấp một
#: đều có gợi ý. Giữ danh sách lại vì lần đầu có lệnh thật sự không cần thì nó
#: phải được ghi kèm lý do, chứ không phải lặng lẽ vắng mặt khỏi bảng.
MIEN_TRU: dict[str, str] = {}


def _lenh_cap_mot() -> set[str]:
    for a in build_parser()._actions:
        if isinstance(a, argparse._SubParsersAction):
            return set(a.choices)
    return set()


def _moi_lenh_day_du() -> set[str]:
    """Mọi lệnh gõ được, kể cả lệnh con — để kiểm gợi ý trỏ vào chỗ có thật."""
    ra: set[str] = set()

    def di(pr, tien_to=""):
        for a in pr._actions:
            if isinstance(a, argparse._SubParsersAction):
                for ten, con in a.choices.items():
                    day_du = (tien_to + " " + ten).strip()
                    ra.add(day_du)
                    di(con, day_du)

    di(build_parser())
    return ra


# ── bảng gợi ý phải khớp cây lệnh thật ───────────────────────────────────────


def test_moi_lenh_cap_mot_deu_co_goi_y() -> None:
    """Thiếu một lệnh là thiếu một chỗ người dùng bị bỏ lại."""
    thieu = sorted(_lenh_cap_mot() - set(GOI_Y_KHI_HONG) - set(MIEN_TRU))
    assert not thieu, f"lệnh chưa có gợi ý khi hỏng: {thieu}"


def test_bang_goi_y_KHONG_chua_lenh_khong_ton_tai() -> None:
    """Chiều ngược: bảng không được nhắc tới một lệnh đã bị xoá."""
    thua = sorted(set(GOI_Y_KHI_HONG) - _lenh_cap_mot())
    assert not thua, f"bảng gợi ý nhắc lệnh không có trong CLI: {thua}"


def test_MOI_GOI_Y_deu_tro_vao_mot_lenh_CO_THAT() -> None:
    """Bài kiểm quan trọng nhất của tệp này.

    Đây là lý do bảng gợi ý được gom về một chỗ: một gợi ý trỏ vào lệnh không
    còn tồn tại là một mũi tên chỉ vào tường, và nó tệ hơn không có mũi tên —
    người dùng gõ theo, thất bại lần hai, rồi thôi tin mọi gợi ý khác.
    """
    co_that = _moi_lenh_day_du()
    hong: list[str] = []
    for lenh, goi_y in GOI_Y_KHI_HONG.items():
        for g in goi_y:
            # Bỏ phần đối số mẫu ('<...>') và cờ để lấy đúng phần tên lệnh.
            phan = [t for t in g.split() if not t.startswith(("-", "'<", "<"))]
            assert phan and phan[0] == "eaa", f"{lenh}: gợi ý {g!r} không bắt đầu bằng 'eaa'"
            ten = " ".join(phan[1:])
            while ten and ten not in co_that:
                ten = " ".join(ten.split()[:-1])
            if not ten:
                hong.append(f"{lenh} → {g}")
    assert not hong, f"gợi ý trỏ vào lệnh không có thật: {hong}"


def test_khong_lenh_nao_tu_goi_y_chinh_no_mot_cach_vo_ich() -> None:
    """`eaa gen` hỏng mà bảo 'làm tiếp: eaa gen' là một vòng tròn.

    Ngoại lệ có lý: lệnh CHỈ ĐỌC tự gợi ý chính nó khi cách dùng đúng là gõ nó
    KHÔNG kèm đối số (ví dụ `eaa observe` báo cáo toàn cảnh).
    """
    chi_doc_tu_goi_y = {"observe", "environ", "models", "deviations", "field"}
    vong_tron = [
        l for l, g in GOI_Y_KHI_HONG.items()
        if l not in chi_doc_tu_goi_y and any(x.strip() == f"eaa {l}" for x in g)
    ]
    assert not vong_tron, f"lệnh tự gợi ý chính nó: {vong_tron}"


# ── hành vi của phần "làm tiếp" ──────────────────────────────────────────────


def test_gan_goi_y_khi_thong_bao_khong_neu_lenh_nao() -> None:
    ra = _goi_y_di_tiep("measured", "Chưa có số đo nào tên 'X' trong sổ.")
    assert "eaa measured list" in ra


def test_KHONG_noi_hai_lan_khi_thong_bao_da_tu_neu_lenh() -> None:
    """Nói hai lần thì lần thứ hai làm loãng lần thứ nhất."""
    assert _goi_y_di_tiep("gen", "Chưa có Project State — chạy 'eaa init' trước.") == ""


def test_lenh_khong_co_trong_bang_thi_im_chu_khong_bia() -> None:
    assert _goi_y_di_tiep("mot-lenh-la", "hỏng gì đó") == ""


def test_nhieu_goi_y_thi_xuong_dong_cho_de_doc() -> None:
    ra = _goi_y_di_tiep("flash", "hỏng gì đó")
    assert ra.count("eaa ") == 2
    assert "\n" in ra.strip("\n")


# ── đo lại chính con số của báo cáo benchmark ────────────────────────────────


def _do_phu() -> tuple[int, int, int]:
    """(tổng, tự nêu lệnh, được bảng phủ) — đếm trên chính `eaa/cli.py`."""
    src = pathlib.Path(__file__).resolve().parents[1].joinpath("eaa/cli.py").read_text()
    lenh = _lenh_cap_mot()

    def ten_lenh_cua(ham: str) -> str:
        t = ham[4:] if ham.startswith("cmd_") else ham.lstrip("_")
        for l in sorted(lenh, key=len, reverse=True):
            khoa = l.replace("-", "_")
            if t == khoa or t.startswith(khoa + "_"):
                return l
        return ""

    def khoi(s: str, dau: int) -> str:
        i = s.index("(", dau)
        muc, j = 0, i
        while j < len(s):
            if s[j] == "(":
                muc += 1
            elif s[j] == ")":
                muc -= 1
                if muc == 0:
                    return s[dau : j + 1]
            j += 1
        return s[dau:]

    ham = [(m.start(), m.group(1)) for m in re.finditer(r"^def (\w+)", src, re.M)]

    def ham_cua(pos: int) -> str:
        ten = "?"
        for p, n in ham:
            if p < pos:
                ten = n
            else:
                break
        return ten

    tong = tu_neu = qua_bang = 0
    for m in re.finditer(r"raise CliError\(", src):
        tong += 1
        k = khoi(src, m.start())
        if re.search(r"\beaa [a-z]", k):
            tu_neu += 1
            continue
        l = ten_lenh_cua(ham_cua(m.start()))
        if l and l in GOI_Y_KHI_HONG:
            qua_bang += 1
    return tong, tu_neu, qua_bang


def test_it_nhat_80_phan_tram_cho_bao_loi_noi_duoc_viec_phai_lam() -> None:
    """Ngưỡng của việc số 1 trong báo cáo benchmark.

    Đây là phép đo TĨNH và nó là **cận dưới**: 32 chỗ còn lại nằm trong hàm phụ
    trợ mà phép quy về lệnh không với tới, nhưng lúc chạy thật chúng VẪN nhận
    gợi ý — vì `main()` biết người dùng vừa gõ lệnh nào, chứ không phải hàm nào
    ném lỗi.
    """
    tong, tu_neu, qua_bang = _do_phu()
    ti_le = (tu_neu + qua_bang) / tong
    assert ti_le >= 0.80, (
        f"chỉ {tu_neu + qua_bang}/{tong} = {ti_le:.0%} chỗ báo lỗi nói được việc "
        "phải làm. Ngưỡng là 80%."
    )


def test_moc_cu_duoc_ghi_lai_de_khong_ai_doc_nham() -> None:
    """Báo cáo benchmark công bố 36%; đo lại bằng phép quét đúng thì mốc THẬT
    trước khi sửa là 14% (25/182).

    Bài này giữ con số cũ khỏi bị quên: phép quét đầu tiên dùng một biểu thức
    chỉ bắt được một dạng viết `raise CliError(`, nên nó đếm thiếu CẢ tử lẫn
    mẫu. Sai số của phép đo, không phải của sản phẩm — nhưng nó vẫn là một con
    số đã công bố, nên nó phải được đính chính chứ không lặng lẽ thay.
    """
    tong, tu_neu, _ = _do_phu()
    assert tong >= 180, "số chỗ raise CliError giảm bất thường — kiểm lại phép đếm"
    assert tu_neu >= 25, "số thông báo TỰ nêu lệnh không được tụt dưới mốc đã công bố"


# ── đầu-cuối: người dùng thật sự thấy gì ─────────────────────────────────────


def test_loi_tu_HAM_PHU_TRO_van_nhan_duoc_goi_y(tmp_path, monkeypatch, capsys) -> None:
    """Đây là chỗ phép đo tĩnh không với tới, và là lý do sửa ở `main()`."""
    from eaa import EXIT_OK
    from eaa.cli import main
    from tests.test_cli_e2e import dung_moi_truong

    dung_moi_truong(tmp_path, monkeypatch)
    assert main(["init"]) == EXIT_OK
    capsys.readouterr()

    # `tune` đọc tệp số đo qua hàm phụ trợ `_doc_so_do`; tệp không có.
    main(["tune", "drv_x", "--input", str(tmp_path / "khong_co.yaml")])
    ra = capsys.readouterr()
    assert "eaa " in (ra.out + ra.err), "lỗi từ hàm phụ trợ không kèm việc phải làm"
