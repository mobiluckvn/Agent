"""TC-149 — phát hiện của quy trình thành chẩn đoán cho biên tập (E2, SL-184).

Xem `eaa/diagnostic.py` và `docs/EAA_Backlog_Tien_hoa.xlsx` việc E2.

Năm luật bài này canh
---------------------

1. **Phát hiện KHÔNG có vị trí vẫn phải đi ra.** V3 đo được 8/13 lần từ chối G3
   là lỗi thiết kế không có `file:line` nào. Một bảng lỗi chỉ hiện thứ có vị
   trí dạy người dùng câu sai nhất với sản phẩm này: *"không gạch đỏ nghĩa là
   ổn"*.
2. **Không mất mát.** Số phát hiện đi ra phải bằng số đọc được trong nguồn.
3. **Lịch sử tách khỏi hiện tại.** Sổ lỗi là sổ append-only; bày mục đã sửa
   xong như lỗi hiện tại là để bảng lỗi nói dối.
4. **Vị trí RÚT TỪ CHỮ khác vị trí có CẤU TRÚC**, và phải nói ra là cái nào.
5. **Chỉ đọc.** Lệnh này không chạy lại cổng nào.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from eaa.diagnostic import TEP_NEO, ChanDoan, bang_chu, gom

GOC = pathlib.Path(__file__).resolve().parents[1]
DU_AN_THAT = GOC / "projects/robot_balance"


def _du_an(tmp: pathlib.Path, *, bang_chung=None, quyet_dinh=(), so_loi=()):
    (tmp / ".eaa/runs").mkdir(parents=True)
    for ten, bao_cao in (bang_chung or {}).items():
        (tmp / ".eaa/runs" / f"verification_{ten}.json").write_text(
            json.dumps({"module": ten, "reports": bao_cao}, ensure_ascii=False)
        )
    if quyet_dinh:
        (tmp / "gates").mkdir()
        (tmp / "gates/decisions.jsonl").write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in quyet_dinh)
        )
    if so_loi:
        (tmp / "error_ledger.jsonl").write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in so_loi)
        )
    return tmp


def _bao_cao(gate="compile", passed=False, errors=(), warnings=()):
    return {"gate": gate, "passed": passed, "errors": list(errors),
            "warnings": list(warnings), "metrics": {}, "duration_s": 0.0}


def _loi(msg="hỏng", file=None, line=None, sev="error", rule=None):
    return {"message": msg, "severity": sev, "file": file, "line": line,
            "rule_id": rule}


# ── 1 · phát hiện KHÔNG có vị trí vẫn phải đi ra ─────────────────────────────


def test_loi_KHONG_co_vi_tri_van_di_ra_chu_khong_bi_nuot(tmp_path) -> None:
    """Đây là luật trung tâm của module, và nó đến từ một con số đo được:
    8/13 lần từ chối G3 là lỗi thiết kế không có `file:line` nào (V3)."""
    d = _du_an(tmp_path, bang_chung={"m": [
        _bao_cao(errors=[_loi("có vị trí", "src/m.c", 7),
                         _loi("không vị trí")]),
    ]})
    kq = gom(d)
    assert len(kq.muc) == 2, "một phát hiện bị nuốt"
    khong = [c for c in kq.muc if not c.co_vi_tri]
    assert len(khong) == 1
    assert khong[0].tep == TEP_NEO and khong[0].neo_tam is True


def test_ly_do_NGUOI_tu_choi_gate_cung_thanh_chan_doan(tmp_path) -> None:
    """Hạng phát hiện quan trọng nhất, và là hạng không có vị trí nào."""
    d = _du_an(tmp_path, quyet_dinh=[
        {"module": "m", "gate_id": "G3", "decision": "rejected",
         "decided_at": "2026-09-02T00:00:00", "reason": "sai trục cảm biến"},
    ])
    kq = gom(d)
    assert len(kq.muc) == 1
    c = kq.muc[0]
    assert "sai trục" in c.thong_diep
    # Nguồn phải nói rõ đây là NGƯỜI, không phải máy: hai hạng bằng chứng khác
    # nhau không được hiện thành hai dòng như nhau.
    assert "người" in c.nguon and "G3" in c.nguon


def test_chi_lay_lan_tu_choi_GAN_NHAT_cua_moi_module(tmp_path) -> None:
    """Bốn lần đầu đã được trả lời bằng bốn bản sinh lại — bày cả năm là bày
    lịch sử chứ không bày việc phải làm."""
    d = _du_an(tmp_path, quyet_dinh=[
        {"module": "m", "gate_id": "G3", "decision": "rejected",
         "decided_at": "2026-09-01T00:00:00", "reason": "lần cũ"},
        {"module": "m", "gate_id": "G3", "decision": "rejected",
         "decided_at": "2026-09-02T00:00:00", "reason": "lần mới"},
        {"module": "m", "gate_id": "G3", "decision": "approved",
         "decided_at": "2026-09-03T00:00:00", "reason": "ok"},
    ])
    kq = gom(d)
    assert [c.thong_diep for c in kq.muc] == ["lần mới"]


# ── 2 · không mất mát ────────────────────────────────────────────────────────


def test_so_phat_hien_DI_RA_bang_so_doc_duoc_trong_nguon(tmp_path) -> None:
    d = _du_an(
        tmp_path,
        bang_chung={"a": [_bao_cao(errors=[_loi(), _loi()],
                                   warnings=[_loi(sev="warning")])],
                    "b": [_bao_cao(gate="static", errors=[_loi()])]},
        quyet_dinh=[{"module": "a", "gate_id": "G3", "decision": "rejected",
                     "decided_at": "2026-09-02T00:00:00", "reason": "x"}],
        so_loi=[{"event": "error", "module": "b", "description": "y",
                 "category": "tool_failure"}],
    )
    kq = gom(d)
    assert kq.khop_nguon, f"{len(kq.muc)} đi ra / {kq.so_trong_nguon} trong nguồn"
    assert len(kq.muc) == 6


def test_ho_so_bang_chung_HONG_thanh_mot_phat_hien_chu_khong_bien_mat(tmp_path) -> None:
    (tmp_path / ".eaa/runs").mkdir(parents=True)
    (tmp_path / ".eaa/runs/verification_m.json").write_text("{ hỏng")
    kq = gom(tmp_path)
    assert len(kq.muc) == 1 and "không đọc được" in kq.muc[0].thong_diep


# ── 3 · lịch sử tách khỏi hiện tại ───────────────────────────────────────────


def test_muc_so_loi_cua_module_DA_KHEP_bi_xep_vao_lich_su(tmp_path) -> None:
    """Sổ lỗi là append-only. Module đã qua hết cổng thì lỗi cũ của nó đã sửa
    xong, và bày nó như lỗi hiện tại là để bảng lỗi nói dối."""
    d = _du_an(
        tmp_path,
        bang_chung={"xong": [_bao_cao(passed=True)],
                    "dang_mac": [_bao_cao(passed=False)]},
        so_loi=[
            {"event": "error", "module": "xong", "description": "đã sửa",
             "category": "tool_failure"},
            {"event": "error", "module": "dang_mac", "description": "còn đó",
             "category": "tool_failure"},
        ],
    )
    kq = gom(d)
    assert {c.thong_diep for c in kq.hien_tai} == {"còn đó"}
    assert len(kq.muc) == 2, "mục lịch sử bị xoá thay vì bị xếp loại"


def test_bang_chu_KHONG_giau_so_muc_lich_su_trong_im_lang(tmp_path) -> None:
    d = _du_an(
        tmp_path,
        bang_chung={"xong": [_bao_cao(passed=True)]},
        so_loi=[{"event": "error", "module": "xong", "description": f"cũ {i}",
                 "category": "x"} for i in range(5)],
    )
    kq = gom(d)
    van = bang_chu(kq)
    assert "5" in van and "lịch sử" in van
    assert "cũ 0" in bang_chu(kq, tat_ca=True)


def test_ti_le_tinh_tren_phan_HIEN_TAI_chu_khong_tren_tong(tmp_path) -> None:
    """Tỉ lệ E2 hỏi là 'bảng lỗi vẽ được bao nhiêu', và nó không vẽ lịch sử."""
    d = _du_an(
        tmp_path,
        bang_chung={"xong": [_bao_cao(passed=True)],
                    "mac": [_bao_cao(errors=[_loi("x", "src/mac.c", 3)])]},
        so_loi=[{"event": "error", "module": "xong", "description": "cũ",
                 "category": "x"} for _ in range(9)],
    )
    kq = gom(d)
    assert len(kq.muc) == 10 and len(kq.hien_tai) == 1
    assert kq.ti_le_co_vi_tri == 1.0, "lịch sử bị tính vào mẫu số"


def test_CHUA_DO_DUOC_khac_BANG_KHONG(tmp_path) -> None:
    """Chưa phát hiện nào thì tỉ lệ ấy KHÔNG TỒN TẠI — báo 0% là khai một con
    số chưa đo. Cùng luật `confidence.py` đặt cho mọi đầu ra khác."""
    assert gom(tmp_path).ti_le_co_vi_tri is None


# ── 4 · vị trí rút từ chữ khác vị trí có cấu trúc ────────────────────────────


def test_vi_tri_rut_TU_CHU_duoc_danh_dau_khac_voi_vi_tri_co_CAU_TRUC(tmp_path) -> None:
    d = _du_an(
        tmp_path,
        bang_chung={"m": [_bao_cao(errors=[_loi("a", "src/m.c", 5)])]},
        so_loi=[{"event": "error", "module": "m", "category": "tool_failure",
                 "description": "Cổng compile không đạt: src/m.c:42: hỏng"}],
    )
    kq = gom(d)
    theo_nguon = {c.nguon.split("/")[0]: c for c in kq.muc}
    assert theo_nguon["compile"].vi_tri_do_doc is False
    rut = theo_nguon["ledger"]
    assert rut.vi_tri_do_doc is True and rut.tep == "src/m.c" and rut.dong == 42
    assert rut.to_dict()["position_parsed"] is True


@pytest.mark.parametrize("mo_ta", [
    "không có vị trí nào",
    "phiên bản 1.2.3: gì đó",          # không phải đường dẫn
    "src/m.c:0: dòng 0 không hợp lệ",  # số dòng phải dương
    "xem tài liệu ds-021.pdf:3: ...",  # không phải tệp mã nguồn
])
def test_rut_HONG_thi_phat_hien_van_di_ra_chi_mat_phan_vi_tri(
    tmp_path, mo_ta: str
) -> None:
    """Bỏ phát hiện đi mới là hỏng. Mất vị trí thì chỉ mất vị trí."""
    d = _du_an(tmp_path, so_loi=[
        {"event": "error", "module": "m", "description": mo_ta, "category": "x"}])
    kq = gom(d)
    assert len(kq.muc) == 1
    assert kq.muc[0].co_vi_tri is False and kq.muc[0].thong_diep == mo_ta


# ── 5 · chỉ đọc, và nối đúng vào lớp E1 ──────────────────────────────────────


def test_lenh_problems_la_lenh_CHI_DOC_va_co_json() -> None:
    from eaa.cli import LENH_CHI_DOC, LENH_CO_JSON

    assert "problems" in LENH_CHI_DOC and "problems" in LENH_CO_JSON


def test_lenh_problems_KHONG_doi_gi_tren_dia(tmp_path, monkeypatch) -> None:
    """Chạy cổng là việc của `eaa gen`, và nó đổi trạng thái."""
    import hashlib

    from eaa.cli import main

    du_an = _du_an(
        tmp_path,
        bang_chung={"m": [_bao_cao(errors=[_loi("x", "src/m.c", 1)])]},
    )

    def dau_van_tay() -> dict[str, str]:
        return {
            str(p.relative_to(du_an)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(du_an.rglob("*")) if p.is_file()
        }

    truoc = dau_van_tay()
    main(["--project", str(du_an), "problems"])
    assert dau_van_tay() == truoc, "lệnh chỉ đọc mà đổi tệp trên đĩa"


def test_dau_ra_json_mang_du_TRUONG_cho_bang_loi_bien_tap(tmp_path, capsys) -> None:
    from eaa import jsonout
    from eaa.cli import main

    du_an = _du_an(
        tmp_path,
        bang_chung={"m": [_bao_cao(errors=[_loi("x", "src/m.c", 9, rule="r1")])]},
    )
    try:
        main(["--project", str(du_an), "problems", "--json"])
        o = json.loads(capsys.readouterr().out)
    finally:
        jsonout.tat()
    c = o["data"]["diagnostics"][0]
    for khoa in ("file", "line", "severity", "message", "source", "rule",
                 "module", "anchored", "position_parsed", "state"):
        assert khoa in c, f"thiếu trường {khoa!r} — bảng lỗi biên tập cần nó"
    assert c["file"] == "src/m.c" and c["line"] == 9 and c["severity"] == "error"
    assert o["data"]["counts"]["in_source"] == o["data"]["counts"]["total"]


# ── 6 · trên dữ liệu THẬT của kho ────────────────────────────────────────────


@pytest.mark.skipif(not DU_AN_THAT.is_dir(), reason="chưa có dự án mẫu")
def test_tren_du_an_that_khong_mat_mat_va_co_ca_hai_hang() -> None:
    kq = gom(DU_AN_THAT)
    assert kq.khop_nguon
    assert kq.muc, "không đọc được phát hiện nào từ dự án thật"
    nguon = {c.nguon.split("/")[0].split()[0] for c in kq.muc}
    assert "ledger" in nguon, "mất nguồn sổ lỗi — nguồn duy nhất có vị trí"
    assert any("G3" in c.nguon for c in kq.muc), "mất lý do người từ chối gate"
    assert kq.hien_tai and len(kq.hien_tai) < len(kq.muc), (
        "không tách được lịch sử khỏi hiện tại trên dữ liệu thật"
    )


@pytest.mark.skipif(not DU_AN_THAT.is_dir(), reason="chưa có dự án mẫu")
def test_moc_cua_E2_duoc_ghi_lai_de_khong_ai_doc_nham() -> None:
    """Con số nghiệm thu của E2, đo trên dự án thật.

    Nó nhỏ, và nó phải nhỏ: phần lớn phát hiện đang mở là lý do NGƯỜI từ chối
    tại gate, và chúng không có `file:line` nào. Một bảng lỗi chỉ vẽ gạch đỏ sẽ
    hiện đúng một phần rất nhỏ của cái đang thật sự sai.
    """
    kq = gom(DU_AN_THAT)
    ti_le = kq.ti_le_co_vi_tri
    assert ti_le is not None
    assert ti_le < 0.5, (
        f"tỉ lệ có vị trí nhảy lên {ti_le:.0%} — nếu thật thì mừng, nhưng phải "
        "đọc lại phép đếm trước khi tin"
    )
    assert len(kq.hien_tai) >= 5
