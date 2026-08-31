"""TC-83 — câu trả lời "cần người làm gì" phải ĐỦ, không chỉ đúng.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-106.

Tìm ra trong phiên kiểm có người đứng giữa: hỏi Agent *"có việc gì bắt buộc
cần con người làm trước khi bạn sinh mã được?"*, nó chạy ``eaa status``, rồi
trả lời **2 trong 3 việc** — bỏ mất chuyện máy thiếu cả năm công cụ toolchain.
Hỏi lại lần hai, ép nó kiểm, thì nó nêu đủ. Tức là năng lực CÓ, chỉ là nó
không nghĩ tới.

Vì sao chữa bằng cấu trúc chứ không bằng lời dặn
-------------------------------------------------

Cách hiển nhiên là dặn Agent "nhớ gọi thêm ``capabilities``". Lời dặn ấy sẽ
đúng cho câu hỏi này và trượt ở câu hỏi diễn đạt khác — mà số cách diễn đạt
thì vô hạn.

``eaa status`` là **đường tắt hấp dẫn** vì nó trông như đã trả lời. Nên chỗ
sửa là chính nó: cho bản tóm tắt nói ra công cụ còn thiếu, thì đường tắt cũng
thành đường đúng — cho cả Agent lẫn người đọc.

Và ``eaa focus`` — lệnh hứa "cả quãng đường, một lần" — cũng thiếu đúng chặng
ấy. Nó kiểm Platform Pack **khai đủ cổng** chưa, nhưng không kiểm công cụ chạy
các cổng ấy **có trên máy** không. Hai câu hỏi khác nhau, và trả lời câu thứ
nhất rồi tích xanh là trả lời nhầm câu.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.focus import CHUA, DAT, NGUOI, analyse


# ═══════════════ eaa focus phải kể cả công cụ còn thiếu ═══════════════


def _lo_trinh(**kw):
    class _S:
        phase = "D"
        gates = {"G1": "approved", "G2": "approved"}
        backlog = ()

        def module(self, mid):
            class _M:
                id = mid
                status = "todo"
                uses = ()
                depends_on = ()
            return _M()

    return analyse(module_id="mod_a", state=_S(), **kw)


def test_thieu_cong_cu_thi_focus_BAO_RA():
    lo = _lo_trinh(missing_tools=[("bo-bien-dich", ("compile",)),
                                  ("bo-phan-tich", ("static",))])
    chan = [p for p in lo.blocked_by if "Công cụ" in p.name]
    assert len(chan) == 1, "focus không nêu chuyện thiếu công cụ"
    p = chan[0]
    assert p.status == CHUA
    assert "bo-bien-dich" in p.detail and "bo-phan-tich" in p.detail
    assert "compile" in p.detail and "static" in p.detail, \
        "phải nói công cụ ấy chặn cổng nào"


def test_thieu_cong_cu_la_chang_CUA_NGUOI():
    """Cài đặt đổi máy người dùng — không bao giờ là chặng Agent tự lo (N-022)."""
    lo = _lo_trinh(missing_tools=[("x", ("compile",))])
    p = [q for q in lo.blocked_by if "Công cụ" in q.name][0]
    assert p.who == NGUOI
    assert p.fix == ("doctor", "--fix")
    assert p.reason, "chặng của người phải nói VÌ SAO nó là của người"


def test_du_cong_cu_thi_chang_ay_DAT():
    lo = _lo_trinh(missing_tools=())
    p = [q for q in lo.preconditions if "Công cụ" in q.name]
    assert len(p) == 1 and p[0].status == DAT


def test_hai_cau_hoi_KHAC_NHAU_va_ca_hai_deu_duoc_hoi():
    """"Pack khai đủ cổng" và "máy này chạy được các cổng ấy" là hai chuyện.

    Trước bản sửa chỉ có câu thứ nhất, và nó tích xanh trong khi năm công cụ
    không tồn tại. Người dùng đọc dấu tích, duyệt G1, chờ sinh mã, rồi mới đâm
    vào bức tường mà chính lệnh này sinh ra để báo trước.
    """
    lo = _lo_trinh(missing_chain_gates=(), missing_tools=[("x", ("compile",))])
    ten = [p.name for p in lo.preconditions]
    assert "Chuỗi kiểm chứng đủ cổng" in ten
    assert "Công cụ chạy được các cổng ấy" in ten
    # Câu thứ nhất đạt, câu thứ hai không — đúng tình huống đã gặp.
    theo_ten = {p.name: p for p in lo.preconditions}
    assert theo_ten["Chuỗi kiểm chứng đủ cổng"].status == DAT
    assert theo_ten["Công cụ chạy được các cổng ấy"].status == CHUA


def test_focus_khong_tu_di_do_cong_cu():
    """Kỷ luật của module: nhận dữ kiện đã đo, không phát biểu luật mới.

    Hai bộ dò công cụ ở hai chỗ thì cái lỏng hơn luôn là cái được tin.
    """
    nguon = (Path(__file__).resolve().parents[1] / "eaa" / "focus.py").read_text(
        encoding="utf-8")
    for cam in ("shutil.which", "subprocess", "Doctor("):
        assert cam not in nguon, f"focus.py tự đi dò công cụ: {cam}"


# ═══════════════ eaa status phải nói ra, để đường tắt cũng đúng ═══════════════


def _du_an(tmp_path: Path) -> Path:
    p = tmp_path / "du_an"
    p.mkdir(exist_ok=True)
    (p / "project_state.json").write_text(json.dumps({
        "schema_version": 1, "phase": "A",
        "gates": {"G1": "pending", "G2": "pending", "G3": "pending",
                  "G4": "pending", "G5": "pending"},
        "backlog": [], "constraints_version": "", "llm": {},
        "created_at": "", "updated_at": "",
    }), encoding="utf-8")
    return p


class _BaoCao:
    def __init__(self, ten, cong, chan=True):
        self.spec = type("S", (), {"name": ten, "gates": cong})()
        self.blocking = chan


def test_status_NOI_RA_cong_cu_con_thieu(tmp_path, monkeypatch, capsys):
    from eaa import cli

    monkeypatch.setattr(cli, "_tao_doctor", lambda p: type("D", (), {
        "scan": lambda self: [_BaoCao("bo-bien-dich", ("compile",)),
                              _BaoCao("bo-phan-tich", ("static",)),
                              _BaoCao("bo-du", (), chan=False)],
    })())
    cli._in_cong_cu_thieu(_du_an(tmp_path))
    ra = capsys.readouterr().out
    assert "2 công cụ bắt buộc chưa có" in ra
    assert "bo-bien-dich" in ra and "bo-phan-tich" in ra
    assert "bo-du" not in ra, "công cụ không chặn thì không được kể vào"
    assert "compile, static" in ra
    assert "chưa merge được" in ra, "phải nói hậu quả, không chỉ nói thiếu"
    assert "doctor --fix" in ra


def test_du_cong_cu_thi_status_IM_LANG(tmp_path, monkeypatch, capsys):
    """Dòng "mọi thứ ổn" lặp ở mọi bản tóm tắt sẽ bị mắt bỏ qua.

    Và lúc nó đổi thành cảnh báo thì cũng bị bỏ qua nốt.
    """
    from eaa import cli

    monkeypatch.setattr(cli, "_tao_doctor", lambda p: type("D", (), {
        "scan": lambda self: [_BaoCao("bo-du", ("compile",), chan=False)],
    })())
    cli._in_cong_cu_thieu(_du_an(tmp_path))
    assert capsys.readouterr().out == ""


def test_khong_do_duoc_cong_cu_thi_KHONG_bao_nham_la_du(tmp_path, monkeypatch, capsys):
    """Dò hỏng thì im, chứ không in ra một bản tóm tắt trông như đã đủ."""
    from eaa import cli

    def _no(p):
        raise RuntimeError("manifest hỏng")

    monkeypatch.setattr(cli, "_tao_doctor", _no)
    with pytest.raises(RuntimeError):
        cli._in_cong_cu_thieu(_du_an(tmp_path))
    # _in_tom_tat bọc lỗi lại; bản tóm tắt vẫn ra, chỉ không có mục công cụ.
    from eaa.state import StateStore

    p = _du_an(tmp_path)
    cli._in_tom_tat(StateStore(p / "project_state.json").load(), p)
    ra = capsys.readouterr().out
    assert "Human Gate" in ra
    assert "công cụ bắt buộc chưa có" not in ra


def test_canh_bao_cong_cu_nam_TRUOC_bang_gate(tmp_path, monkeypatch, capsys):
    """Thứ tự đọc: cái chặn cứng phải hiện trước cái chờ quyết định."""
    from eaa import cli
    from eaa.state import StateStore

    monkeypatch.setattr(cli, "_tao_doctor", lambda p: type("D", (), {
        "scan": lambda self: [_BaoCao("bo-bien-dich", ("compile",))],
    })())
    p = _du_an(tmp_path)
    cli._in_tom_tat(StateStore(p / "project_state.json").load(), p)
    ra = capsys.readouterr().out
    assert ra.index("công cụ bắt buộc chưa có") < ra.index("Human Gate")
