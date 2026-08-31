"""TC-80 — chọn mô hình là việc của NGƯỜI, và hệ không tự chọn thay.

EAA-AIS-05 §2; ADR-03. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-103.

Bài này canh hai thứ khác nhau, và thứ thứ hai quan trọng hơn:

1. Cơ chế chọn có chạy đúng không — thứ tự ưu tiên, cả hai vị trí của cờ.
2. Cơ chế **tự chọn** có bị lén thêm vào không. Cám dỗ "việc nhẹ thì Flash,
   việc nặng thì Pro" rất hợp lý khi nhìn riêng nó, và nó phá đúng hai thứ:
   người trả tiền mất quyền quyết định đánh đổi, và hai lần chạy cùng một lệnh
   không còn so sánh được với nhau (rủi ro R1, EAA-STP-04).
"""

from __future__ import annotations

import argparse

import pytest

from eaa.llm.catalog import CATALOG, KHUYEN_NGHI, get, render_catalog


# ═════════════════════════ danh mục là dữ liệu ═════════════════════════


def test_flash_35_co_trong_danh_muc():
    m = get("gemini-3.5-flash")
    assert m is not None
    assert m.provider == "gemini"
    assert m.input_limit == 1_048_576


def test_moi_muc_deu_ghi_ngay_kiem():
    """Danh mục là ảnh chụp một thời điểm; ảnh chụp không ghi ngày là ảnh vô dụng."""
    for m in CATALOG:
        assert m.verified_on, m.id
        assert m.note.strip(), m.id


def test_ma_ngoai_danh_muc_khong_phai_loi():
    """Nhà cung cấp ra model mới nhanh hơn danh mục được cập nhật."""
    assert get("gemini-9.9-sieu-pro") is None
    ra = render_catalog(dang_dung="gemini-9.9-sieu-pro")
    assert "KHÔNG có trong danh mục" in ra
    assert "Không phải lỗi" in ra


def test_danh_muc_danh_dau_ma_dang_dung():
    ra = render_catalog(dang_dung="gemini-3.5-flash")
    dong = [d for d in ra.splitlines() if "gemini-3.5-flash " in d and d.startswith(" →")]
    assert len(dong) == 1


def test_khuyen_nghi_chi_de_IN_RA_khong_ai_doc_de_quyet_dinh():
    """Bài canh cấu trúc: KHUYEN_NGHI không được có mã nào đọc để tự chọn.

    Nếu một ngày có, thì mục đích của cả module đã bị lật ngược — nên bắt ở
    đây, lúc dòng mã ấy vừa được viết, chứ không phải lúc người dùng thấy
    model đổi ngầm.
    """
    import subprocess
    import sys
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1]
    ra = subprocess.run(
        [sys.executable, "-c",
         "import pathlib,sys;"
         "hits=[str(p) for p in pathlib.Path(sys.argv[1]).rglob('*.py')"
         " if 'KHUYEN_NGHI' in p.read_text(encoding='utf-8')"
         " and p.name != 'catalog.py'];"
         "print('\\n'.join(hits))",
         str(goc / "eaa")],
        capture_output=True, text=True,
    )
    assert ra.stdout.strip() == "", (
        "KHUYEN_NGHI bị đọc ở ngoài catalog.py — đó là dấu hiệu có cơ chế tự "
        f"chọn model:\n{ra.stdout}"
    )
    # Và nó vẫn phải có nội dung để in ra cho người đọc.
    assert KHUYEN_NGHI


def test_danh_muc_noi_ro_he_khong_tu_chon():
    ra = render_catalog()
    assert "KHÔNG tự đổi model" in ra


# ═══════════════════ thứ tự ưu tiên khi quyết mã model ═══════════════════


class _State:
    def __init__(self, model: str = "", provider: str = "gemini"):
        self.llm = {"provider": provider, "model": model}


def _model_da_chon(monkeypatch, tmp_path, *, override="", trong_state="", env=None):
    from eaa import cli

    monkeypatch.setattr(cli, "_MODEL_LUOT_NAY", "")
    if env is None:
        monkeypatch.delenv("EAA_LLM_MODEL", raising=False)
    else:
        monkeypatch.setenv("EAA_LLM_MODEL", env)
    client = cli._tao_llm(_State(trong_state), tmp_path, model_override=override)
    return client.model


def test_co_model_thang_project_state(monkeypatch, tmp_path, capsys):
    assert _model_da_chon(
        monkeypatch, tmp_path,
        override="gemini-3.5-flash", trong_state="gemini-3.1-pro-preview",
    ) == "gemini-3.5-flash"


def test_project_state_thang_bien_moi_truong(monkeypatch, tmp_path):
    assert _model_da_chon(
        monkeypatch, tmp_path,
        trong_state="gemini-3.1-pro-preview", env="gemini-3.5-flash",
    ) == "gemini-3.1-pro-preview"


def test_bien_moi_truong_thang_mac_dinh_adapter(monkeypatch, tmp_path):
    from eaa.llm.gemini import DEFAULT_MODEL

    chon = _model_da_chon(monkeypatch, tmp_path, env="gemini-3.5-flash")
    assert chon == "gemini-3.5-flash" != DEFAULT_MODEL


def test_khong_neu_gi_thi_mac_dinh_adapter(monkeypatch, tmp_path):
    from eaa.llm.gemini import DEFAULT_MODEL

    assert _model_da_chon(monkeypatch, tmp_path) == DEFAULT_MODEL


def test_dung_co_thi_NOI_RA_va_khong_ghi_state(monkeypatch, tmp_path, capsys):
    """Đổi model mà im lặng là đổi ngầm — đúng thứ module này sinh ra để tránh."""
    st = _State("gemini-3.1-pro-preview")
    from eaa import cli

    monkeypatch.setattr(cli, "_MODEL_LUOT_NAY", "")
    cli._tao_llm(st, tmp_path, model_override="gemini-3.5-flash")
    ra = capsys.readouterr().out
    assert "gemini-3.5-flash" in ra and "không ghi vào Project State" in ra
    # Project State không bị đụng tới.
    assert st.llm["model"] == "gemini-3.1-pro-preview"


def test_ma_la_van_chay_kem_ghi_chu(monkeypatch, tmp_path, capsys):
    from eaa import cli

    monkeypatch.setattr(cli, "_MODEL_LUOT_NAY", "")
    c = cli._tao_llm(_State(), tmp_path, model_override="gemini-9.9-sieu-pro")
    assert c.model == "gemini-9.9-sieu-pro"
    assert "chưa có trong danh mục" in capsys.readouterr().out


# ═══════════════ cờ nhận được ở cả hai vị trí trên dòng lệnh ═══════════════


def test_co_model_nhan_duoc_TRUOC_ten_lenh():
    from eaa.cli import build_parser

    args = build_parser().parse_args(["--model", "gemini-3.5-flash", "status"])
    assert args.model == "gemini-3.5-flash"


def test_co_model_nhan_duoc_SAU_ten_lenh():
    """Chỗ người ta gõ theo bản năng: eaa chat --model flash."""
    from eaa.cli import build_parser

    args = build_parser().parse_args(["status", "--model", "gemini-3.5-flash"])
    assert args.model == "gemini-3.5-flash"


def test_mac_dinh_cua_lenh_con_KHONG_xoa_gia_tri_dat_o_parser_goc():
    """Bẫy argparse: lệnh con có default rỗng sẽ đè giá trị của parser gốc.

    Đây là lý do mọi lệnh con khai --model với ``default=SUPPRESS``. Thiếu nó
    thì "eaa --model X chat" im lặng chạy bằng model mặc định — người dùng gõ
    cờ ra, thấy nó được nhận, và nó không có tác dụng gì.
    """
    from eaa.cli import build_parser

    p = build_parser()
    for lenh in ("status", "packs", "models", "policy"):
        assert p.parse_args(["--model", "flash-x", lenh]).model == "flash-x", lenh


def test_moi_lenh_con_deu_nhan_duoc_co_model():
    """Nhớ lệnh nào nhận được cờ là việc không ai nên phải làm."""
    from eaa.cli import build_parser

    p = build_parser()
    sub = [a for a in p._subparsers._group_actions
           if isinstance(a, argparse._SubParsersAction)][0]
    thieu = []
    for ten, con in sub.choices.items():
        if not any("--model" in (a.option_strings or []) for a in con._actions):
            thieu.append(ten)
    assert thieu == [], f"lệnh chưa nhận được --model: {thieu}"


def test_init_giu_nghia_rieng_cua_model():
    """Với 'init', --model nghĩa là GHIM — đó là lệnh đặt mặc định."""
    from eaa.cli import build_parser

    p = build_parser()
    sub = [a for a in p._subparsers._group_actions
           if isinstance(a, argparse._SubParsersAction)][0]
    tro_giup = [a.help for a in sub.choices["init"]._actions
                if "--model" in (a.option_strings or [])][0]
    assert "GHIM" in tro_giup
