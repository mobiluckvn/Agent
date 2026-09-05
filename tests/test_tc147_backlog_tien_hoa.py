"""TC-147 — canh tính toàn vẹn của backlog tiến hoá (SL-181).

Xem `scripts/lam_bang_tien_hoa.py` và `docs/EAA_Backlog_Tien_hoa.xlsx`.

Bài này canh cái gì
-------------------

Không canh "backlog đúng" — thứ tự ưu tiên là phán đoán của người. Nó canh ba
thứ mà nếu trôi đi thì bảng nói dối mà không ai biết:

1. **Mỗi việc phải khai sở cứ có thật**, và mỗi sở cứ phải có việc dùng. Một
   danh sách việc phải làm không có sở cứ là một danh sách ước muốn.
2. **Đồ thị phụ thuộc phải nhất quán và không vòng tròn.** Bản đầu khai cả hai
   chiều bằng tay và có 15 cạnh không đối xứng cùng ba cặp vòng tròn. Một đồ
   thị tự mâu thuẫn còn tệ hơn không có đồ thị, vì người đọc tin nó.
3. **Không mã việc nào bị đánh rơi khi bảng được thiết kế lại.** V1..V14 của
   bảng cũ phải còn tra được.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

GOC = pathlib.Path(__file__).resolve().parents[1]
KICH_BAN = GOC / "scripts/lam_bang_tien_hoa.py"

pytestmark = pytest.mark.skipif(
    not KICH_BAN.exists(), reason="chưa có bộ sinh backlog trong kho này"
)


def _nap():
    spec = importlib.util.spec_from_file_location("_backlog", KICH_BAN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


#: Vị trí cột trong mỗi dòng VIEC — đặt tên để bài kiểm không đọc bằng số trần.
MA, MA_CU, MANG, TEN, HANG, SO_CU, CACH, TEP, NGHIEM_THU = range(9)
BAI_CANH, CHO, CHAN, RUI_RO, CONG, UU_TIEN, TRANG_THAI = range(9, 16)

_MA_VIEC = re.compile(r"[A-F]\d+")


# ── 1 · sở cứ ────────────────────────────────────────────────────────────────


def test_moi_viec_deu_khai_so_cu_CO_THAT() -> None:
    m = _nap()
    co = {s[0] for s in m.SO_CU}
    hong = [
        f"{v[MA]} → {x}"
        for v in m.VIEC for x in v[SO_CU].split(", ")
        if x.strip() and x.strip() not in co
    ]
    assert not hong, f"việc khai sở cứ không có trong sổ: {hong}"


def test_moi_so_cu_deu_co_viec_DUNG_NO() -> None:
    """Chiều ngược: một sở cứ không việc nào dùng là một dòng đã cũ đi."""
    m = _nap()
    dung = {x.strip() for v in m.VIEC for x in v[SO_CU].split(", ")}
    thua = sorted({s[0] for s in m.SO_CU} - dung)
    assert not thua, f"sở cứ không việc nào dùng: {thua}"


def test_moi_so_cu_deu_mang_HANG_hop_le() -> None:
    """Hạng là thứ chặn bảng thành danh sách những gì người viết thấy hay."""
    m = _nap()
    hop_le = {m.DO, m.SO, m.VL, m.KHAI, m.SR}
    for ma, hang, _, tra in m.SO_CU:
        assert hang in hop_le, f"{ma} mang hạng lạ: {hang!r}"
        assert tra.strip(), f"{ma} không nói tra ở đâu — không kiểm lại được"


def test_so_cu_hang_SUY_RA_phai_TU_KHAI_la_chua_co_so() -> None:
    """Việc dựa trên lập luận suông không được lẫn vào việc dựa trên lỗi thật."""
    m = _nap()
    for ma, hang, noi, tra in m.SO_CU:
        if hang == m.SR:
            assert "chưa" in (noi + tra).lower(), (
                f"{ma} mang hạng SUY RA mà không nói ra rằng nó chưa có số"
            )


# ── 2 · đồ thị phụ thuộc ─────────────────────────────────────────────────────


def _canh(m) -> dict[str, list[str]]:
    return {
        v[MA]: [x.strip() for x in v[CHO].split(" · ")
                if _MA_VIEC.fullmatch(x.strip())]
        for v in m.VIEC
    }


def test_phu_thuoc_tro_vao_viec_CO_THAT() -> None:
    m = _nap()
    ma = {v[MA] for v in m.VIEC}
    hong = [f"{a} → {b}" for a, ds in _canh(m).items() for b in ds if b not in ma]
    assert not hong, f"phụ thuộc trỏ vào việc không có: {hong}"


def test_cot_CHAN_khop_hoan_toan_voi_cot_CHO() -> None:
    """Cột `Chặn` phải SUY RA từ cột `Chờ`, không khai tay.

    Bản đầu khai cả hai chiều và có 15 cạnh không đối xứng. Hai danh sách cho
    cùng một mục đích là hai danh sách sẽ lệch nhau — cùng hình dạng lỗi V3
    tìm ra trong `contract.py`.
    """
    m = _nap()
    suy_ra: dict[str, set[str]] = {}
    for a, ds in _canh(m).items():
        for b in ds:
            suy_ra.setdefault(b, set()).add(a)
    for v in m.VIEC:
        khai = {x.strip() for x in v[CHAN].split(" · ")
                if _MA_VIEC.fullmatch(x.strip())}
        assert khai == suy_ra.get(v[MA], set()), (
            f"{v[MA]}: cột Chặn khai {sorted(khai)} nhưng suy từ cột Chờ là "
            f"{sorted(suy_ra.get(v[MA], set()))}"
        )


def test_do_thi_phu_thuoc_KHONG_co_vong_tron() -> None:
    """Ba cặp vòng tròn (C1↔C4, C3↔D2, D2↔D3) đã lọt vào bản đầu.

    Một việc chờ chính nó qua vài bước là một việc không bao giờ bắt đầu được.
    """
    canh = _canh(_nap())
    tham: set[str] = set()

    def di(n: str, duong: tuple[str, ...]) -> list[str] | None:
        if n in duong:
            return list(duong[duong.index(n):]) + [n]
        if n in tham:
            return None
        tham.add(n)
        for k in canh.get(n, []):
            r = di(k, duong + (n,))
            if r:
                return r
        return None

    for goc in canh:
        vong = di(goc, ())
        assert vong is None, f"vòng tròn phụ thuộc: {' → '.join(vong)}"


def test_viec_XONG_khong_cho_mot_viec_CHUA_XONG() -> None:
    """Nếu có thì hoặc trạng thái sai, hoặc phụ thuộc là bịa."""
    m = _nap()
    tt = {v[MA]: v[TRANG_THAI] for v in m.VIEC}
    hong = [
        f"{a} ({tt[a]}) chờ {b} ({tt[b]})"
        for a, ds in _canh(m).items() if tt[a].startswith("XONG")
        for b in ds if not tt[b].startswith("XONG")
    ]
    assert not hong, f"việc đã xong mà vẫn khai chờ việc chưa xong: {hong}"


# ── 3 · không đánh rơi mã cũ ─────────────────────────────────────────────────


def test_moi_ma_cua_bang_CU_deu_con_tra_duoc() -> None:
    """Thiết kế lại một bảng không được làm mất dấu vết của bảng trước."""
    m = _nap()
    cu = {v[MA_CU] for v in m.VIEC}
    thieu = [f"V{i}" for i in range(1, 15) if f"V{i}" not in cu]
    assert not thieu, f"mã của bảng cũ bị đánh rơi: {thieu}"


def test_khong_ma_cu_nao_bi_gan_cho_HAI_viec() -> None:
    m = _nap()
    cu = [v[MA_CU] for v in m.VIEC if v[MA_CU] != "—"]
    trung = sorted({x for x in cu if cu.count(x) > 1})
    assert not trung, f"một mã cũ gán cho nhiều việc: {trung}"


# ── 4 · mỗi việc phải nói đủ ba câu ──────────────────────────────────────────


def test_moi_viec_noi_du_LAM_GI_LAM_THE_NAO_va_XONG_THI_DO_BANG_GI() -> None:
    m = _nap()
    for v in m.VIEC:
        assert len(v[TEN]) > 15, f"{v[MA]}: tên việc quá mỏng"
        assert len(v[CACH]) > 80, f"{v[MA]}: chưa nói được LÀM THẾ NÀO"
        assert len(v[NGHIEM_THU]) > 20, f"{v[MA]}: chưa nói xong thì ĐO bằng gì"
        assert len(v[RUI_RO]) > 30, f"{v[MA]}: chưa nói cái gì dễ làm hỏng"
        assert v[MANG] in {x[0] for x in m.MANG}, f"{v[MA]}: mảng lạ {v[MANG]!r}"


def test_hai_mang_MOI_du_day_dan() -> None:
    """Mô phỏng và IDE là hai mảng dựng mới; mỏng thì bảng không dùng được."""
    m = _nap()
    for ten, toi_thieu in (("Mô phỏng", 6), ("IDE", 6)):
        mang = next(x[0] for x in m.MANG if ten in x[0])
        so = sum(1 for v in m.VIEC if v[MANG] == mang)
        assert so >= toi_thieu, f"mảng {ten} chỉ có {so} việc, cần ≥ {toi_thieu}"


def test_viec_XONG_phai_neu_duoc_BAI_KIEM_CANH() -> None:
    """Một việc XONG mà không có bài canh là một việc đã chạy thử một lần."""
    m = _nap()
    for v in m.VIEC:
        if v[TRANG_THAI].startswith("XONG"):
            assert re.search(r"TC-\d+", v[BAI_CANH]), (
                f"{v[MA]} ghi XONG mà không nêu bài kiểm canh: {v[BAI_CANH]!r}"
            )


# ── 5 · bảng cũ đã được rút, không để song song ──────────────────────────────


def test_bang_CU_khong_con_ton_tai() -> None:
    """Hai danh sách việc phải làm là hai danh sách sẽ lệch nhau (SL-181)."""
    for cu in ("docs/EAA_Viec_phai_lam.xlsx", "scripts/lam_bang_viec_phai_lam.py"):
        assert not (GOC / cu).exists(), (
            f"{cu} còn đó — hai bảng việc phải làm song song sẽ lệch nhau"
        )


def test_ma_SONG_khong_con_tro_vao_bang_da_rut() -> None:
    """Sổ sai lệch và chân lý nền V3 được PHÉP nhắc tên cũ — đó là lịch sử.

    Mã đang chạy thì không: một đường dẫn trỏ vào tệp đã xoá là mũi tên chỉ
    vào tường, cùng hạng lỗi TC-145 chặn ở gợi ý CLI.
    """
    hong: list[str] = []
    for d in list((GOC / "eaa").rglob("*.py")) + list((GOC / "scripts").glob("*.py")):
        van = d.read_text(encoding="utf-8")
        if "EAA_Viec_phai_lam" in van or "lam_bang_viec_phai_lam" in van:
            if d.name != "lam_bang_tien_hoa.py":   # nó nói về việc THAY THẾ
                hong.append(str(d.relative_to(GOC)))
    assert not hong, f"mã đang chạy còn trỏ vào bảng đã rút: {hong}"
