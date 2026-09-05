"""TC-148 — đầu ra máy đọc được cho lệnh CHỈ ĐỌC (E1, SL-182).

Xem `eaa/jsonout.py` và `docs/EAA_Backlog_Tien_hoa.xlsx` việc E1.

Bốn luật bài này canh
---------------------

1. **`--json` CHỈ cho lệnh chỉ đọc.** Một `--json` cho lệnh ghi *"cho tiện tự
   động hoá"* chính là con đường thứ hai dẫn tới merge mà bất biến số một cấm
   (TC-01, TC-02). Canh cả hai chiều.
2. **Bật `--json` thì stdout chỉ có JSON.** Trộn văn xuôi với JSON trên cùng
   một luồng thì không bên nào đọc được.
3. **Mức tin cậy phải sống sót.** 23 lớp kết luận mang một trong bốn mức
   (TC-63); làm phẳng chúng thành chuỗi là bỏ mất đúng thứ `confidence.py`
   sinh ra để giữ.
4. **Lược đồ là hợp đồng, và đầu ra TẤT ĐỊNH.** Cùng đầu vào cho cùng byte đầu
   ra — cùng luật TC-15 đặt cho lượt gọi mô hình.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib

import pytest

from eaa import jsonout
from eaa.cli import (
    GOI_Y_KHI_HONG,
    LENH_CHI_DOC,
    LENH_CO_JSON,
    build_parser,
    main,
)

GOC = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _khong_ro_trang_thai():
    """Chế độ máy đọc là biến toàn cục; bài nào bật thì bài ấy dọn."""
    yield
    jsonout.tat()


def _parser_cua(duong: str):
    pr = build_parser()
    for ten in duong.split():
        con = next(
            (a for a in pr._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        if con is None or ten not in con.choices:
            return None
        pr = con.choices[ten]
    return pr


def _nhan_json(duong: str) -> bool:
    pr = _parser_cua(duong)
    return pr is not None and any(
        "--json" in (a.option_strings or ()) for a in pr._actions
    )


def _moi_parser():
    """(đường dẫn lệnh, parser) cho mọi nút trong cây lệnh."""
    ra: list[tuple[str, argparse.ArgumentParser]] = []

    def di(pr, tien_to=""):
        for a in pr._actions:
            if isinstance(a, argparse._SubParsersAction):
                for ten, con in a.choices.items():
                    d = (tien_to + " " + ten).strip()
                    ra.append((d, con))
                    di(con, d)

    di(build_parser())
    return ra


# ── 1 · chỉ lệnh chỉ đọc mới có --json ───────────────────────────────────────


def test_moi_lenh_trong_LENH_CO_JSON_deu_nhan_co() -> None:
    thieu = [d for d in LENH_CO_JSON if not _nhan_json(d)]
    assert not thieu, f"khai có `--json` mà parser không nhận: {thieu}"


def test_KHONG_lenh_nao_NGOAI_danh_sach_nhan_co_json() -> None:
    """Chiều quan trọng hơn: một cờ mọc thêm ở đâu đó là một đường không ai canh."""
    thua = [d for d, _ in _moi_parser() if _nhan_json(d) and d not in LENH_CO_JSON]
    assert not thua, f"lệnh nhận `--json` mà không khai trong LENH_CO_JSON: {thua}"


def test_LENH_CO_JSON_la_tap_con_that_su_cua_LENH_CHI_DOC() -> None:
    """Không được lén thêm một lệnh GHI vào danh sách đã làm."""
    thua = sorted(set(LENH_CO_JSON) - LENH_CHI_DOC)
    assert not thua, f"lệnh có `--json` mà không nằm trong nhóm chỉ đọc: {thua}"


def test_moi_lenh_khai_CHI_DOC_deu_CO_THAT_trong_cay_lenh() -> None:
    co_that = {d for d, _ in _moi_parser()}
    ma = sorted(LENH_CHI_DOC - co_that)
    assert not ma, f"khai là lệnh chỉ đọc nhưng không có trong CLI: {ma}"


#: Tên hàm mà một lệnh CHỈ ĐỌC không được gọi. Danh sách này là HÀNG RÀO MỘT
#: CHIỀU: nó bắt được lệnh khai chỉ đọc mà thật ra có ghi, nhưng nó KHÔNG
#: chứng minh được chiều ngược — chuỗi gọi sâu quá hai tầng thì nó bỏ sót.
_HAM_GHI = frozenset({
    "save", "with_lock", "write_text", "write_bytes", "mkdir", "unlink",
    "rename", "replace", "approve", "reject", "rmtree", "touch", "chmod",
})


def _ham_trong_cli() -> dict[str, ast.FunctionDef]:
    cay = ast.parse((GOC / "eaa/cli.py").read_text())
    return {
        n.name: n for n in ast.walk(cay)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _goi_ghi(ten: str, ham: dict, sau: int = 0, tham: set | None = None) -> set[str]:
    tham = tham if tham is not None else set()
    if ten in tham or sau > 2 or ten not in ham:
        return set()
    tham.add(ten)
    goi: set[str] = set()
    for x in ast.walk(ham[ten]):
        if isinstance(x, ast.Call):
            f = x.func
            goi.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
        if isinstance(x, ast.With):
            for it in x.items:
                e = it.context_expr
                if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute):
                    goi.add(e.func.attr)
    ra = goi & _HAM_GHI
    for c in goi:
        if c.startswith(("_", "cmd_")):
            ra |= _goi_ghi(c, ham, sau + 1, tham)
    return ra


def test_lenh_CO_JSON_khong_goi_ham_GHI_nao_bat_duoc() -> None:
    """Phép soi cây cú pháp — hàng rào một chiều, không phải bằng chứng.

    Nó bỏ sót `gen` và `build` khi thử, vì chuỗi gọi của chúng sâu hơn hai
    tầng. Nên nó chỉ canh danh sách khai tay khỏi trôi, chứ không thay được
    việc khai tay.
    """
    ham = _ham_trong_cli()
    hong: list[str] = []
    for duong in LENH_CO_JSON:
        pr = _parser_cua(duong)
        f = pr.get_default("func") if pr else None
        if f is None:
            continue
        ghi = _goi_ghi(f.__name__, ham)
        if ghi:
            hong.append(f"{duong} → {sorted(ghi)}")
    assert not hong, f"lệnh khai chỉ đọc mà bắt được lời gọi ghi: {hong}"


# ── 2 · bật --json thì stdout chỉ có JSON ────────────────────────────────────


def _chay(argv: list[str], capsys) -> tuple[int, dict, str]:
    ma = main(argv)
    ra = capsys.readouterr()
    return ma, json.loads(ra.out) if ra.out.strip() else {}, ra.err


@pytest.mark.parametrize("lenh", ["policy", "packs"])
def test_stdout_chi_co_JSON_khong_lan_van_xuoi(lenh: str, capsys) -> None:
    ma, o, _ = _chay([lenh, "--json"], capsys)
    assert o["schema"] == jsonout.SCHEMA
    assert o["command"] == lenh
    assert o["ok"] is True and o["exit_code"] == ma
    assert o["data"], "phong bì rỗng — lệnh chưa nộp dữ liệu nào"


def test_khong_bat_json_thi_dau_ra_KHONG_doi(capsys) -> None:
    """Bật một cờ mới không được đổi hành vi của mọi người dùng cũ."""
    main(["policy"])
    van = capsys.readouterr().out
    assert van.strip() and not van.lstrip().startswith("{")


def test_dau_ra_TAT_DINH_chay_hai_lan_cho_cung_byte(capsys) -> None:
    """Cùng luật TC-15: có dấu thời gian trong phong bì là mất tính này."""
    main(["policy", "--json"])
    a = capsys.readouterr().out
    jsonout.tat()
    main(["policy", "--json"])
    b = capsys.readouterr().out
    assert a == b


# ── 3 · nhánh LỖI cũng phải ra JSON ──────────────────────────────────────────


def test_loi_ra_JSON_tren_stderr_kem_cau_LAM_TIEP(tmp_path, monkeypatch, capsys) -> None:
    """Lệnh hỏng mà không có gì máy đọc được thì lớp IDE chỉ biết 'có chuyện'."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EAA_PROJECT", raising=False)
    ma = main(["status", "--json"])
    ra = capsys.readouterr()
    assert ma != 0
    o = json.loads(ra.err)
    assert o["ok"] is False and o["command"] == "status"
    assert o["error"]["message"]
    # Chính những câu "làm tiếp" của SL-178, nay là DANH SÁCH chứ không phải
    # văn xuôi đã ghép — lớp IDE dựng nút bấm được từ nó.
    assert o["error"]["next"] == list(GOI_Y_KHI_HONG["status"])


# ── 4 · mức tin cậy sống sót qua JSON ────────────────────────────────────────


def test_muc_tin_cay_la_MOT_TRUONG_khong_phai_mot_chuoi_da_tron() -> None:
    from eaa.confidence import DA_KIEM

    o = jsonout.muc(42, DA_KIEM)
    assert o == {"gia_tri": 42, "muc": DA_KIEM}


def test_thu_tuc_ra_JSON_van_mang_MUC_TIN_CAY_tung_bay(capsys) -> None:
    from eaa.confidence import DA_KIEM

    kho = GOC / "projects/robot_balance/procedures"
    if not kho.is_dir():
        pytest.skip("chưa có dữ liệu thủ tục")
    _, o, _ = _chay(["--project", "projects/robot_balance", "procedure", "--json"],
                    capsys)
    bay = [b for p in o["data"]["procedures"] for b in p["traps"]]
    assert bay, "không bẫy nào ra được JSON"
    assert all("level" in b and b["level"] for b in bay), (
        "bẫy ra JSON mà mất mức tin cậy — lớp IDE sẽ hiện nó như một sự thật"
    )
    assert any(b["level"] == DA_KIEM for b in bay)
    assert all(b["source"] for b in bay), "bẫy mất xuất xứ khi ra JSON"


def test_gate_ra_JSON_van_mang_DAU_VAN_TAY_noi_dung(capsys) -> None:
    """Lớp IDE duyệt gate thì nó duyệt đúng nội dung này. Không có dấu vân tay
    thì không ai kiểm lại được cái vừa được duyệt là cái gì."""
    du_an = GOC / "projects/robot_balance"
    if not du_an.is_dir():
        pytest.skip("chưa có dự án mẫu")
    _, o, _ = _chay(["--project", str(du_an), "gate", "show", "--json"], capsys)
    d = o["data"]
    for ho_so in list(d.get("pending", [])) + ([d["draft"]] if d.get("draft") else []):
        assert ho_so["content_digest"].startswith("sha256:")


# ── 5 · tỉ lệ phủ, báo thẳng chứ không thu hẹp mẫu số ────────────────────────


def test_ti_le_phu_duoc_bao_that_chu_khong_thu_hep_mau_so() -> None:
    """`LENH_CO_JSON` phải là tập con THẬT SỰ của `LENH_CHI_DOC`.

    Nếu hai tập bằng nhau thì hoặc đã làm xong, hoặc ai đó vừa xoá bớt mẫu số
    cho tỉ lệ đẹp lên. Bài này bắt trường hợp thứ hai bằng cách đòi mẫu số
    không được nhỏ đi.
    """
    assert len(LENH_CHI_DOC) >= 30, (
        f"nhóm lệnh chỉ đọc chỉ còn {len(LENH_CHI_DOC)} — mẫu số bị thu hẹp?"
    )
    assert set(LENH_CO_JSON) <= LENH_CHI_DOC


def test_lenh_GHI_tieu_bieu_KHONG_nhan_co_json() -> None:
    """Danh sách đích danh, để một cờ mọc thêm ở đây là đỏ ngay."""
    for d in ("gen", "init", "gate approve", "gate reject", "flash", "build",
              "plan accept", "measured approve", "tool approve", "skill approve",
              "rollback", "resume"):
        if _parser_cua(d) is None:
            continue
        assert not _nhan_json(d), (
            f"`{d}` nhận `--json` — đó là đường thứ hai tới merge (TC-01, TC-02)"
        )
