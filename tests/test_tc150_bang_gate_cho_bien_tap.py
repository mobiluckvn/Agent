"""TC-150 — bảng trạng thái gate cho biên tập (E3, SL-185).

Xem `eaa/gates.py` và `docs/EAA_Backlog_Tien_hoa.xlsx` việc E3.

Vì sao bảng gate mới là mặt tiếp xúc chính
-------------------------------------------

E2 (SL-184) đo được trên dự án thật: **21 trong 22 phát hiện đang mở là lý do
NGƯỜI từ chối tại gate**, và chúng không có `file:line` nào. Gạch đỏ trong biên
tập hiện đúng 1 trong 22. Nên với sản phẩm này, bảng gate — chứ không phải danh
sách lỗi trình dịch — là thứ kỹ sư cần thấy trước.

Bốn luật bài này canh
---------------------

1. **Không có đường thứ hai sinh ra quyết định DUYỆT.** Một nút bấm trong biên
   tập phải đi đúng đường mọi người khác đi.
2. **Ghi lại việc người duyệt có khẳng định nội dung không**, ở BA trạng thái —
   `None` là KHÔNG KIỂM ĐƯỢC, không phải "không khẳng định".
3. **Công tắc cưỡng chế tắt thì không đổi hành vi cũ**; bật thì phiên không có
   người phải khẳng định băm.
4. **Bảng gate trả lời được "đang mắc ở đâu" trong MỘT lệnh.**
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from eaa import jsonout
from eaa.gates import (
    APPROVED,
    BIEN_DOI_BAM,
    GateDecision,
    GateError,
    GatePayload,
    HumanGate,
)

GOC = pathlib.Path(__file__).resolve().parents[1]
DU_AN_THAT = GOC / "projects/robot_balance"


@pytest.fixture(autouse=True)
def _sach(monkeypatch):
    monkeypatch.delenv(BIEN_DOI_BAM, raising=False)
    yield
    jsonout.tat()


def _cong(tmp_path) -> HumanGate:
    return HumanGate(tmp_path / "gates")


def _ho_so(gate="G3", **thay) -> GatePayload:
    d = dict(gate_id=gate, title="thử", summary=("a",), details="chi tiết",
             content_digest="sha256:abc", module="m")
    d.update(thay)
    return GatePayload(**d)


# ── 1 · không có đường thứ hai sinh ra quyết định DUYỆT ──────────────────────


def test_chi_MOT_cho_trong_engine_dung_ra_mot_quyet_dinh_DUYET() -> None:
    """Bất biến trung tâm của E3, và của cả dự án.

    Một nút "Duyệt" trong biên tập chỉ an toàn khi nó không có đường riêng để
    đi. Bài này quét cây cú pháp tìm mọi chỗ dựng `GateDecision(...)` với
    quyết định là DUYỆT, và đòi chúng nằm trong `eaa/gates.py`.
    """
    pham: list[str] = []
    for tep in sorted((GOC / "eaa").rglob("*.py")):
        cay = ast.parse(tep.read_text(encoding="utf-8"))
        for nut in ast.walk(cay):
            if not isinstance(nut, ast.Call):
                continue
            ten = getattr(nut.func, "id", None) or getattr(nut.func, "attr", None)
            if ten != "GateDecision":
                continue
            for kw in nut.keywords:
                if kw.arg != "decision":
                    continue
                v = kw.value
                la_duyet = (
                    (isinstance(v, ast.Constant) and v.value == APPROVED)
                    or (isinstance(v, ast.Name) and v.id == "APPROVED")
                )
                if la_duyet and tep.name != "gates.py":
                    pham.append(f"{tep.relative_to(GOC)}:{nut.lineno}")
    assert not pham, f"quyết định DUYỆT được dựng ngoài eaa/gates.py: {pham}"


def test_quyet_dinh_duyet_van_doi_ten_NGUOI_chiu_trach_nhiem() -> None:
    with pytest.raises(GateError, match="người quyết định"):
        GateDecision(gate_id="G3", decision=APPROVED, actor="  ",
                     decided_at="2026-09-05", payload_digest="d")


# ── 2 · ghi lại việc có khẳng định nội dung không, ở BA trạng thái ───────────


def test_duyet_KEM_bam_duoc_ghi_la_co_khang_dinh(tmp_path) -> None:
    g = _cong(tmp_path)
    ho_so = _ho_so()
    g.request(ho_so)
    qd = g.approve("G3", actor="ai đó", expect_digest=ho_so.digest)
    assert qd.digest_asserted is True


def test_duyet_KHONG_kem_bam_duoc_ghi_la_KHONG_khang_dinh(tmp_path) -> None:
    g = _cong(tmp_path)
    g.request(_ho_so())
    assert g.approve("G3", actor="ai đó").digest_asserted is False


def test_ban_ghi_CU_doc_ra_KHONG_KIEM_DUOC_chu_khong_phai_False() -> None:
    """38 quyết định đã đóng trong dự án thật được ghi trước khi trường này tồn
    tại. Đọc chúng thành 'không khẳng định' là khai một điều ta không biết."""
    cu = {"gate_id": "G3", "decision": APPROVED, "actor": "x",
          "decided_at": "2026-09-01", "payload_digest": "d"}
    assert GateDecision.from_dict(cu).digest_asserted is None


def test_truong_moi_di_qua_duoc_vong_ghi_doc(tmp_path) -> None:
    g = _cong(tmp_path)
    ho_so = _ho_so()
    g.request(ho_so)
    g.approve("G3", actor="x", expect_digest=ho_so.digest)
    assert g.latest("G3").digest_asserted is True


def test_ba_trang_thai_KHONG_duoc_gop_khi_dem(tmp_path) -> None:
    """Gộp KHÔNG KIỂM ĐƯỢC vào 'duyệt mù' là báo một con số chưa đo."""
    from eaa.cli import _duyet_mu

    class Gia:
        def __init__(self, ds):
            self._ds = ds

        def decisions(self, gate_id=None):
            return self._ds

    def qd(khang_dinh):
        d = GateDecision(gate_id="G3", decision=APPROVED, actor="x",
                         decided_at="t", payload_digest="d")
        object.__setattr__(d, "digest_asserted", khang_dinh)
        return d

    class Ctx:
        gates = Gia([qd(True), qd(False), qd(False), qd(None)])

    assert _duyet_mu(Ctx()) == {"asserted": 1, "blind": 2, "unknown": 1}

    # Chiều nguy hiểm nhất: KHÔNG KIỂM ĐƯỢC bị gộp vào một trong hai hạng kia.
    # Dự án thật có 38 quyết định đều thuộc hạng ấy, nên gộp nhầm sẽ dựng ra
    # một con số 38 nghe như đã đo.
    class ChiKhongBiet:
        gates = Gia([qd(None), qd(None)])

    assert _duyet_mu(ChiKhongBiet()) == {"asserted": 0, "blind": 0, "unknown": 2}


# ── 3 · công tắc cưỡng chế ───────────────────────────────────────────────────


def test_cong_tac_TAT_thi_khong_doi_hanh_vi_cu(tmp_path, monkeypatch) -> None:
    """Mặc định phải im: bật nó lên đụng mọi kịch bản đã viết, và đó là quyết
    định của người chủ dự án chứ không phải của lớp giao diện."""
    monkeypatch.delenv(BIEN_DOI_BAM, raising=False)
    g = _cong(tmp_path)
    g.request(_ho_so())
    assert g.approve("G3", actor="x").approved


def test_cong_tac_BAT_thi_phien_khong_nguoi_phai_khang_dinh_bam(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(BIEN_DOI_BAM, "1")
    g = _cong(tmp_path)
    ho_so = _ho_so()
    g.request(ho_so)
    with pytest.raises(GateError) as e:
        g.approve("G3", actor="x")
    # Thông báo phải nêu ĐÚNG băm cần dùng — bắt người đi tìm là cách nhanh
    # nhất để họ tắt công tắc đi (cùng luật SL-178).
    assert ho_so.digest in str(e.value) and "--expect" in str(e.value)


def test_cong_tac_BAT_ma_CO_bam_thi_van_duyet_duoc(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(BIEN_DOI_BAM, "1")
    g = _cong(tmp_path)
    ho_so = _ho_so()
    g.request(ho_so)
    assert g.approve("G3", actor="x", expect_digest=ho_so.digest).approved


def test_bam_LECH_bi_tu_choi_du_cong_tac_tat(tmp_path) -> None:
    """Luật cũ không được nới ra: duyệt bản A rồi merge bản B là chỗ hở."""
    g = _cong(tmp_path)
    g.request(_ho_so())
    with pytest.raises(GateError, match="đã thay đổi"):
        g.approve("G3", actor="x", expect_digest="sha256:khac")


# ── 4 · bảng gate trả lời được "đang mắc ở đâu" trong MỘT lệnh ───────────────


@pytest.mark.skipif(not DU_AN_THAT.is_dir(), reason="chưa có dự án mẫu")
def test_MOT_lenh_du_de_biet_dang_mac_o_gate_nao(capsys) -> None:
    from eaa.cli import main

    main(["--project", str(DU_AN_THAT), "gate", "show", "--json"])
    o = json.loads(capsys.readouterr().out)["data"]

    assert len(o["gates"]) == 5
    for g in o["gates"]:
        for khoa in ("id", "purpose", "status", "label", "last_decision"):
            assert khoa in g, f"bảng gate thiếu trường {khoa!r}"
    assert any(g["status"] == "pending" for g in o["gates"]), (
        "không gate nào pending — bảng không nói được đang mắc ở đâu"
    )
    assert set(o["digest_use"]) == {"asserted", "blind", "unknown"}


def test_gate_da_tu_choi_mang_theo_LY_DO_NGUYEN_VAN(tmp_path) -> None:
    """21/22 phát hiện đang mở là lý do người từ chối (E2). Bảng gate mất lý do
    thì lớp IDE không còn gì để hiện.

    Dựng một lần TỪ CHỐI thật thay vì đọc dự án mẫu: trên dự án mẫu, quyết định
    gần nhất của MỌI gate đều là `approved`, nên bản đầu của bài này không bao
    giờ chạy tới phép khẳng định — một bài kiểm rỗng, và đột biến xoá lý do đi
    qua được nó.
    """
    from eaa.cli import _bang_gate

    g = _cong(tmp_path)
    g.request(_ho_so())
    g.reject("G3", actor="người duyệt", reason="sai trục cảm biến, xem lại gá")

    class Trang:
        @staticmethod
        def gate_status(gate: str) -> str:
            return "rejected" if gate == "G3" else "pending"

    class Ctx:
        gates = g

    bang = _bang_gate(Ctx(), Trang())
    g3 = next(x for x in bang if x["id"] == "G3")
    d = g3["last_decision"]
    assert d is not None, "gate vừa bị từ chối mà bảng không mang quyết định nào"
    assert d["decision"] == "rejected"
    assert "sai trục" in d["reason"], "bảng gate đánh rơi lý do từ chối"
    assert d["actor"] == "người duyệt" and d["at"]


@pytest.mark.skipif(not DU_AN_THAT.is_dir(), reason="chưa có dự án mẫu")
def test_tren_du_an_that_moi_quyet_dinh_deu_du_truong(capsys) -> None:
    from eaa.cli import main

    main(["--project", str(DU_AN_THAT), "gate", "show", "--json"])
    o = json.loads(capsys.readouterr().out)["data"]
    co = [g for g in o["gates"] if g["last_decision"]]
    assert co, "không gate nào có quyết định gần nhất"
    for g in co:
        d = g["last_decision"]
        assert d["actor"] and d["at"] and "digest_asserted" in d


def test_gate_show_van_la_lenh_CHI_DOC() -> None:
    from eaa.cli import LENH_CHI_DOC, LENH_CO_JSON

    assert "gate show" in LENH_CHI_DOC and "gate show" in LENH_CO_JSON
    # Và chiều nguy hiểm: nhánh GHI của cùng cây lệnh không được nhận cờ.
    for d in ("gate approve", "gate reject"):
        assert d not in LENH_CO_JSON
