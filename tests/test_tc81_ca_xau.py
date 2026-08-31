"""TC-81 — ba lỗi thật do bộ ca xấu tìm ra, và bài canh để chúng không quay lại.

`scripts/chay_ca_xau.py` chạy sản phẩm như một người dùng đang gõ sai. Vòng
chạy đầu (15 ca) tìm ra ba chỗ hỏng mà 1.966 bài test sẵn có không chạm tới —
vì cả ba đều là chỗ **mã lệch với lời chính nó khai**, và một bài test viết từ
cùng hiểu nhầm ấy sẽ xanh.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-104.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


# ══════════ Lỗi 1: EAA_NO_NET=1 không chặn lối ra mạng qua mô hình ══════════


def test_no_net_chan_ca_loi_goi_mo_hinh(monkeypatch):
    """Công tắc tắt mạng phải chặn MỌI lối ra, kể cả lối qua API mô hình.

    Ca C-10 phát hiện: ``EAA_NO_NET=1 eaa research "..."`` vẫn ra Internet thật
    và trả về tám địa chỉ. ``EAA_NO_NET`` chỉ được đọc trong ``eaa/web.py``,
    còn ``research`` đi qua tìm kiếm có grounding của chính adapter mô hình.

    Đây là kiểu hỏng tệ nhất của một công tắc an toàn: nó **trông như đã tắt**.
    """
    from eaa.llm.gemini import GeminiClient, NetworkDisabled

    monkeypatch.setenv("EAA_LLM_KEY", "khoa-gia-de-kiem")
    monkeypatch.setenv("EAA_NO_NET", "1")

    da_goi = []
    c = GeminiClient(transport=lambda *a, **k: da_goi.append(a) or {})
    with pytest.raises(NetworkDisabled, match="EAA_NO_NET"):
        c._post("generateContent", {"contents": []})
    assert da_goi == [], "lớp vận chuyển bị gọi dù mạng đã tắt"


def test_no_net_noi_ra_duong_chay_tiep(monkeypatch):
    """Chặn xong phải chỉ được đường ra — mock và replay đều chạy không cần mạng."""
    from eaa.llm.gemini import GeminiClient, NetworkDisabled

    monkeypatch.setenv("EAA_LLM_KEY", "khoa-gia")
    monkeypatch.setenv("EAA_NO_NET", "1")
    with pytest.raises(NetworkDisabled) as exc:
        GeminiClient(transport=lambda *a, **k: {})._post("generateContent", {})
    tin = str(exc.value)
    assert "mock" in tin and "replay" in tin


def test_no_net_khong_hoi_sieu_du_lieu_model(monkeypatch):
    """Tra trần token cũng là một lượt gọi ra ngoài."""
    from eaa.llm.gemini import GeminiClient

    monkeypatch.setenv("EAA_LLM_KEY", "khoa-gia")
    monkeypatch.setenv("EAA_NO_NET", "1")
    c = GeminiClient()
    assert c.output_limit() == c.max_output_tokens


def test_moi_loi_ra_mang_deu_doc_cung_MOT_ham():
    """Bài canh cấu trúc: thêm lối ra mạng mới mà tự đọc biến thì đỏ ở đây.

    Ba lối ra của engine — ``web.py``, ``llm/gemini.py``, ``environ.py`` — phải
    hỏi ``mang_bi_tat()``. Mỗi chỗ tự đọc ``os.environ`` một kiểu là cách công
    tắc này hụt lần đầu.
    """
    goc = Path(__file__).resolve().parents[1] / "eaa"
    xau = []
    for p in goc.rglob("*.py"):
        noi_dung = p.read_text(encoding="utf-8")
        if "EAA_NO_NET" not in noi_dung and "NO_NET_ENV" not in noi_dung:
            continue
        # web.py định nghĩa hàm; toolforge truyền biến vào tiến trình con.
        if p.name in ("web.py", "toolforge.py"):
            continue
        if "mang_bi_tat" not in noi_dung:
            xau.append(str(p.relative_to(goc.parent)))
    assert xau == [], f"tự đọc EAA_NO_NET thay vì hỏi mang_bi_tat(): {xau}"


# ═══ Lỗi 2: băm ràng buộc trong state không được đối chiếu với tệp trên đĩa ═══


def _du_an(tmp_path: Path, *, noi_dung: str, bam: str) -> Path:
    p = tmp_path / "du_an"
    p.mkdir()
    (p / "constraints.yaml").write_text(noi_dung, encoding="utf-8")
    (p / "project_state.json").write_text(json.dumps({
        "phase": "A", "constraints_version": bam,
    }), encoding="utf-8")
    return p


_RANG_BUOC = "mcu: atmega328p\nplatform: avr\nflash_bytes: 32768\nram_bytes: 2048\n"


def _bam(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_bam_khop_thi_im_lang(tmp_path):
    from eaa.cli import _troi_rang_buoc
    from eaa.state import StateStore

    p = _du_an(tmp_path, noi_dung=_RANG_BUOC, bam=_bam(_RANG_BUOC))
    state = StateStore(p / "project_state.json").load()
    assert _troi_rang_buoc(state, p) == ""


def test_bam_lech_thi_BAO_TROI(tmp_path):
    """Ca C-04 phát hiện: sửa constraints.yaml xong, băm trên màn hình không đổi.

    Băm ấy đi vào commit message làm bằng chứng xuất xứ (NFR-07). Để lệch là
    ghi một khẳng định sai vào lịch sử Git — và lịch sử Git thì không sửa lại.
    """
    from eaa.cli import _troi_rang_buoc
    from eaa.state import StateStore

    p = _du_an(tmp_path, noi_dung=_RANG_BUOC, bam=_bam("nội dung cũ hẳn"))
    state = StateStore(p / "project_state.json").load()
    ra = _troi_rang_buoc(state, p)
    assert "TRÔI" in ra
    assert _bam(_RANG_BUOC) in ra, "phải nói băm THẬT của tệp là bao nhiêu"
    assert "NFR-07" in ra, "phải nói vì sao chuyện này quan trọng"
    assert "G1" in ra, "phải chỉ đường chốt lại"


def test_tep_hong_cung_la_mot_dang_troi(tmp_path):
    from eaa.cli import _troi_rang_buoc
    from eaa.state import StateStore

    p = _du_an(tmp_path, noi_dung="mcu: x\n  sai: [\n", bam=_bam("gì đó"))
    state = StateStore(p / "project_state.json").load()
    assert "KHÔNG ĐỌC ĐƯỢC" in _troi_rang_buoc(state, p)


def test_khong_co_bam_thi_khong_noi_gi(tmp_path):
    """Dự án chưa qua G1 thì chưa có gì để đối chiếu — im lặng mới đúng."""
    from eaa.cli import _troi_rang_buoc
    from eaa.state import StateStore

    p = _du_an(tmp_path, noi_dung=_RANG_BUOC, bam="")
    state = StateStore(p / "project_state.json").load()
    assert _troi_rang_buoc(state, p) == ""


def test_canh_bao_troi_hien_trong_status(tmp_path, capsys):
    """Cảnh báo phải nằm ở lệnh người ta gõ hằng ngày, không ở một lệnh ẩn."""
    from eaa.cli import _in_tom_tat
    from eaa.state import StateStore

    p = _du_an(tmp_path, noi_dung=_RANG_BUOC, bam=_bam("cũ"))
    _in_tom_tat(StateStore(p / "project_state.json").load(), p)
    assert "TRÔI" in capsys.readouterr().out


# ═══ Lỗi 3: biến môi trường đặt RỖNG bị .env lặng lẽ điền đè ═══


def test_bien_dat_rong_van_la_bien_da_dat(tmp_path, monkeypatch):
    """Ca C-09 phát hiện: không có cách nào chạy thử đường KHÔNG-CÓ-KHÓA.

    ``load_env_file`` khai "biến đã đặt trong shell luôn thắng" nhưng lại kiểm
    bằng truthiness, nên một biến đặt thành chuỗi rỗng bị coi như chưa đặt và
    ``.env`` điền vào. Mã lệch với chính luật nó khai ở docstring.
    """
    from eaa.cli import load_env_file

    (tmp_path / ".env").write_text("EAA_LLM_KEY=khoa-trong-tep\n", encoding="utf-8")
    monkeypatch.setenv("EAA_LLM_KEY", "")
    assert load_env_file(tmp_path) == []
    import os

    assert os.environ["EAA_LLM_KEY"] == ""


def test_bien_chua_dat_thi_van_nap_tu_tep(tmp_path, monkeypatch):
    from eaa.cli import load_env_file

    (tmp_path / ".env").write_text("EAA_LLM_KEY=khoa-trong-tep\n", encoding="utf-8")
    monkeypatch.delenv("EAA_LLM_KEY", raising=False)
    assert load_env_file(tmp_path) == ["EAA_LLM_KEY"]
    import os

    assert os.environ["EAA_LLM_KEY"] == "khoa-trong-tep"


def test_bien_dat_that_thi_thang_tep(tmp_path, monkeypatch):
    from eaa.cli import load_env_file

    (tmp_path / ".env").write_text("EAA_LLM_KEY=khoa-trong-tep\n", encoding="utf-8")
    monkeypatch.setenv("EAA_LLM_KEY", "khoa-tu-shell")
    assert load_env_file(tmp_path) == []
    import os

    assert os.environ["EAA_LLM_KEY"] == "khoa-tu-shell"


def test_load_env_khong_bao_gio_tra_ve_GIA_TRI(tmp_path, monkeypatch):
    """NFR-06: danh sách trả về có thể đi vào log, nên chỉ được chứa TÊN biến."""
    from eaa.cli import load_env_file

    (tmp_path / ".env").write_text("EAA_LLM_KEY=bi-mat-tuyet-doi-123\n", encoding="utf-8")
    monkeypatch.delenv("EAA_LLM_KEY", raising=False)
    ra = load_env_file(tmp_path)
    assert "bi-mat-tuyet-doi-123" not in " ".join(ra)


# ═══════════════ bộ ca xấu tự nó phải chạy được và đủ ═══════════════


def test_bo_ca_xau_moi_ca_deu_noi_LY_DO():
    """Một ca không nói vì sao nó đáng thử là một ca sẽ bị xóa nhầm sau này."""
    import importlib.util
    import sys

    goc = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("chay_ca_xau", goc / "scripts" / "chay_ca_xau.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["chay_ca_xau"] = mod
    spec.loader.exec_module(mod)

    assert len(mod.CA) >= 15
    for c in mod.CA:
        assert c.ly_do.strip(), c.ma
        assert "Traceback" in c.khong_duoc_co, f"{c.ma}: mọi ca đều phải canh sập"
