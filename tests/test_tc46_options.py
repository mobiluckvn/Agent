"""TC-46 — cổng quyết định: trình nhiều phương án để người chọn.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-46a | Một lựa chọn phải có ít nhất hai phương án | tập một mục bị từ chối ngay khi dựng |
| TC-46b | Mỗi phương án phải nói mặt trái | thiếu `cons` là lỗi, không phải thiếu sót nhỏ |
| TC-46c | Có phương án thì BẮT BUỘC chọn | `approve` không lấy gợi ý làm mặc định |
| TC-46d | Phương án bị loại vẫn được lưu | quyết định mang cả tập, không chỉ cái thắng |
| TC-46e | Băm nội dung phủ cả phương án | đổi tập sau khi trình lên thì quyết định cũ hết khớp |

Vì sao TC-46c là mục quan trọng nhất: Agent gợi ý một phương án, và nếu engine
lấy gợi ý ấy làm mặc định khi người chỉ gõ "approve" thì lựa chọn thật sự đã
xảy ra ở chỗ không ai nhìn thấy — đúng vấn đề mà cả bước này dựng ra để tránh.
Ba tháng sau, không ai biết đã chọn gì, kể cả người đã bấm.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.gates import GateError, GatePayload, HumanGate
from eaa.options import (
    LlmOptionProposer,
    Option,
    OptionError,
    OptionSet,
)

REPO = Path(__file__).resolve().parent.parent


def _pa(ma: str, **kw) -> Option:
    kw.setdefault("title", f"Cách {ma}")
    kw.setdefault("cons", ("có cái giá của nó",))
    return Option(id=ma, **kw)


def _tap(*pa: Option, gate_id: str = "G1") -> OptionSet:
    return OptionSet(
        question="Chọn cách đọc cảm biến trong vòng điều khiển?",
        options=pa or (_pa("a"), _pa("b")),
        gate_id=gate_id,
    )


# --------------------------------------------------------------------------
# TC-46a / TC-46b — điều kiện để một "lựa chọn" là lựa chọn thật
# --------------------------------------------------------------------------


def test_mot_phuong_an_khong_phai_mot_lua_chon() -> None:
    """Nó tệ hơn không có lựa chọn, vì tạo cảm giác đã cân nhắc."""
    with pytest.raises(OptionError, match="khoác áo lựa chọn"):
        OptionSet(question="x?", options=(_pa("a"),))


def test_khong_co_phuong_an_nao_cung_bi_tu_choi() -> None:
    with pytest.raises(OptionError):
        OptionSet(question="x?", options=())


def test_phuong_an_khong_neu_mat_trai_bi_tu_choi() -> None:
    """Danh sách chỉ toàn ưu điểm chỉ chuyển trách nhiệm sang người bấm nút."""
    with pytest.raises(OptionError, match="mặt trái"):
        Option(id="a", title="Cách a", pros=("nhanh",), cons=())


def test_ma_phuong_an_phai_go_lai_duoc() -> None:
    for xau in ("", "có dấu", "a b", "-batdau", "x" * 40):
        with pytest.raises(OptionError, match="Mã phương án"):
            _pa(xau)


def test_ma_trung_nhau_bi_tu_choi() -> None:
    with pytest.raises(OptionError, match="trùng nhau"):
        _tap(_pa("a"), _pa("a"))


def test_chi_duoc_goi_y_mot_phuong_an() -> None:
    """Gợi ý hai cách cùng lúc thì không còn là gợi ý."""
    with pytest.raises(OptionError, match="không còn là gợi ý"):
        _tap(_pa("a", recommended=True), _pa("b", recommended=True))


def test_khong_goi_y_cach_nao_van_hop_le() -> None:
    tap = _tap(_pa("a"), _pa("b"))
    assert tap.recommended is None


def test_thieu_cau_hoi_bi_tu_choi() -> None:
    with pytest.raises(OptionError, match="câu hỏi"):
        OptionSet(question="   ", options=(_pa("a"), _pa("b")))


# --------------------------------------------------------------------------
# TC-46c — có phương án thì bắt buộc chọn
# --------------------------------------------------------------------------


@pytest.fixture()
def gate(tmp_path: Path) -> HumanGate:
    return HumanGate(tmp_path / "gates")


def _dat_len_ban(gate: HumanGate, tap: OptionSet) -> GatePayload:
    payload = GatePayload(
        gate_id=tap.gate_id or "G1",
        title="Chốt kiến trúc",
        options=tap,
    )
    gate.request(payload)
    return payload


def test_duyet_ma_khong_chon_bi_chan(gate: HumanGate) -> None:
    """Engine KHÔNG lấy phương án được gợi ý làm mặc định."""
    _dat_len_ban(gate, _tap(_pa("a", recommended=True), _pa("b")))

    with pytest.raises(GateError, match="phải nói rõ duyệt phương án nào"):
        gate.approve("G1", actor="ky-su")


def test_thong_bao_neu_ro_goi_y_nhung_khong_dung_no(gate: HumanGate) -> None:
    _dat_len_ban(gate, _tap(_pa("a", recommended=True), _pa("b")))

    with pytest.raises(GateError) as loi:
        gate.approve("G1", actor="ky-su")

    assert "'a'" in str(loi.value)
    assert "gợi ý không phải quyết định" in str(loi.value)


def test_chon_ma_khong_ton_tai_bi_chan(gate: HumanGate) -> None:
    _dat_len_ban(gate, _tap())
    with pytest.raises(GateError, match="Không có phương án"):
        gate.approve("G1", actor="ky-su", option="khong-co")


def test_chon_dung_thi_duyet_duoc(gate: HumanGate) -> None:
    _dat_len_ban(gate, _tap(_pa("a"), _pa("b")))
    quyet_dinh = gate.approve("G1", actor="ky-su", option="b")

    assert quyet_dinh.approved
    assert quyet_dinh.chosen_option == "b"


def test_chon_khong_phan_biet_hoa_thuong(gate: HumanGate) -> None:
    _dat_len_ban(gate, _tap(_pa("Polling"), _pa("b")))
    assert gate.approve("G1", actor="ky-su", option="polling").chosen_option == "Polling"


def test_gate_khong_co_phuong_an_ma_nhan_option_thi_bao_nham(gate: HumanGate) -> None:
    gate.request(GatePayload(gate_id="G1", title="Chốt kiến trúc"))
    with pytest.raises(GateError, match="Nhầm gate"):
        gate.approve("G1", actor="ky-su", option="a")


def test_gate_khong_co_phuong_an_van_duyet_binh_thuong(gate: HumanGate) -> None:
    """Quyết định nhị phân vẫn là quyết định nhị phân — G3, G4 không đổi."""
    gate.request(GatePayload(gate_id="G3", title="Review diff"))
    quyet_dinh = gate.approve("G3", actor="ky-su")

    assert quyet_dinh.approved
    assert quyet_dinh.chosen_option == ""


# --------------------------------------------------------------------------
# TC-46d — phương án bị loại vẫn được lưu
# --------------------------------------------------------------------------


def test_quyet_dinh_mang_ca_tap_phuong_an(gate: HumanGate) -> None:
    """Câu hỏi hữu ích sáu tháng sau là "đã cân nhắc những gì", không chỉ "đã chọn gì"."""
    _dat_len_ban(gate, _tap(_pa("a"), _pa("b"), _pa("c")))
    quyet_dinh = gate.approve("G1", actor="ky-su", option="b")

    assert quyet_dinh.options is not None
    assert [o.id for o in quyet_dinh.options.options] == ["a", "b", "c"]


def test_phuong_an_song_sot_qua_luu_va_doc_lai(gate: HumanGate, tmp_path: Path) -> None:
    _dat_len_ban(
        gate,
        _tap(
            _pa("a", cons=("chậm",), rationale="đơn giản nhưng phí CPU"),
            _pa("b", recommended=True, cons=("phức tạp",)),
        ),
    )
    gate.approve("G1", actor="ky-su", option="a")

    dong = (tmp_path / "gates" / "decisions.jsonl").read_text(encoding="utf-8").strip()
    du_lieu = json.loads(dong)

    assert du_lieu["chosen_option"] == "a"
    assert len(du_lieu["options"]["options"]) == 2
    bi_loai = next(o for o in du_lieu["options"]["options"] if o["id"] == "b")
    assert bi_loai["cons"] == ["phức tạp"]


def test_tu_choi_cung_giu_lai_tap_phuong_an(gate: HumanGate) -> None:
    """Từ chối cả ba cách cũng là dữ kiện: lần sau khỏi đề xuất lại y hệt."""
    _dat_len_ban(gate, _tap(_pa("a"), _pa("b")))
    quyet_dinh = gate.reject("G1", actor="ky-su", reason="cả hai đều quá tốn RAM")

    assert quyet_dinh.options is not None
    assert len(quyet_dinh.options.options) == 2


def test_quyet_dinh_doc_lai_duoc_tu_ban_ghi(gate: HumanGate) -> None:
    _dat_len_ban(gate, _tap(_pa("a"), _pa("b")))
    gate.approve("G1", actor="ky-su", option="a")

    doc_lai = gate.latest("G1")
    assert doc_lai.chosen_option == "a"
    assert doc_lai.options.get("b").title == "Cách b"


# --------------------------------------------------------------------------
# TC-46e — băm nội dung phủ cả phương án
# --------------------------------------------------------------------------


def test_bam_doi_khi_tap_phuong_an_doi() -> None:
    """Đổi tập phương án sau khi trình lên là đổi chính câu hỏi người đang trả lời."""
    a = GatePayload(gate_id="G1", title="x", options=_tap(_pa("a"), _pa("b")))
    b = GatePayload(gate_id="G1", title="x", options=_tap(_pa("a"), _pa("c")))

    assert a.digest != b.digest


def test_bam_doi_khi_mat_trai_doi() -> None:
    a = GatePayload(gate_id="G1", title="x", options=_tap(_pa("a", cons=("chậm",)), _pa("b")))
    b = GatePayload(gate_id="G1", title="x", options=_tap(_pa("a", cons=("tốn RAM",)), _pa("b")))

    assert a.digest != b.digest


def test_duyet_sau_khi_tap_phuong_an_doi_bi_chan(gate: HumanGate) -> None:
    payload = _dat_len_ban(gate, _tap(_pa("a"), _pa("b")))
    bam_da_xem = payload.digest

    gate.request(GatePayload(gate_id="G1", title="Chốt kiến trúc", options=_tap(_pa("a"), _pa("c"))))

    with pytest.raises(GateError, match="đã thay đổi"):
        gate.approve("G1", actor="ky-su", option="a", expect_digest=bam_da_xem)


# --------------------------------------------------------------------------
# Lưu trữ tập phương án đang chờ
# --------------------------------------------------------------------------


def test_luu_va_doc_lai_nhieu_gate(tmp_path: Path) -> None:
    duong_dan = tmp_path / "gate_options.json"
    _tap(gate_id="G1").save(duong_dan)
    _tap(gate_id="G5").save(duong_dan)

    tat_ca = OptionSet.load_all(duong_dan)
    assert set(tat_ca) == {"G1", "G5"}


def test_xoa_tap_cua_mot_gate(tmp_path: Path) -> None:
    duong_dan = tmp_path / "gate_options.json"
    _tap(gate_id="G1").save(duong_dan)
    _tap(gate_id="G5").save(duong_dan)

    OptionSet.clear(duong_dan, "G1")
    assert set(OptionSet.load_all(duong_dan)) == {"G5"}


def test_ho_so_hong_thi_bao_ro(tmp_path: Path) -> None:
    duong_dan = tmp_path / "gate_options.json"
    duong_dan.write_text("khong-phai-json", encoding="utf-8")
    with pytest.raises(OptionError, match="hỏng"):
        OptionSet.load_all(duong_dan)


# --------------------------------------------------------------------------
# Đề xuất bằng mô hình — vẫn là proposed fact
# --------------------------------------------------------------------------

_JSON_TOT = """```json
{
  "options": [
    {"id": "polling", "title": "Hỏi vòng", "summary": "Chờ trong vòng lặp",
     "pros": ["đơn giản"], "cons": ["phí chu kỳ CPU"], "recommended": false,
     "rationale": "chỉ hợp khi cảm biến rất nhanh"},
    {"id": "interrupt", "title": "Ngắt", "summary": "ISR cập nhật biến",
     "pros": ["giải phóng CPU"], "cons": ["tranh chấp dữ liệu"], "recommended": true,
     "rationale": "hợp với chu kỳ không đều"}
  ]
}
```"""


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def test_de_xuat_bang_mo_hinh_boc_duoc() -> None:
    llm = _LlmGia(_JSON_TOT)
    tap = LlmOptionProposer(llm=llm).propose("Đọc cảm biến kiểu gì?", gate_id="G1")

    assert [o.id for o in tap.options] == ["polling", "interrupt"]
    assert tap.recommended.id == "interrupt"
    assert tap.proposed_by == "mo-hinh-gia-1"


def test_de_xuat_thieu_mat_trai_bi_chan_ngay() -> None:
    """Đề xuất của mô hình đi qua CÙNG cửa kiểm với phương án viết tay."""
    llm = _LlmGia(
        '```json\n{"options": [{"id": "a", "title": "A", "pros": ["nhanh"]},'
        ' {"id": "b", "title": "B", "cons": ["chậm"]}]}\n```'
    )
    with pytest.raises(OptionError, match="mặt trái"):
        LlmOptionProposer(llm=llm).propose("x?", gate_id="G1")


def test_de_xuat_mot_phuong_an_bi_chan() -> None:
    llm = _LlmGia('```json\n{"options": [{"id": "a", "title": "A", "cons": ["x"]}]}\n```')
    with pytest.raises(OptionError, match="khoác áo lựa chọn"):
        LlmOptionProposer(llm=llm).propose("x?", gate_id="G1")


def test_khong_boc_duoc_json_thi_bo_de_xuat() -> None:
    llm = _LlmGia("Tôi nghĩ nên dùng ngắt.")
    with pytest.raises(OptionError, match="không đoán thay"):
        LlmOptionProposer(llm=llm).propose("x?", gate_id="G1")


def test_prompt_cam_mo_hinh_tu_quyet_dinh() -> None:
    llm = _LlmGia(_JSON_TOT)
    LlmOptionProposer(llm=llm).propose("x?", gate_id="G1")

    van_ban = llm.prompts[0].full_text()
    assert "Không tự quyết định thay người" in van_ban
    assert "mặt trái" in van_ban


def test_ban_in_ra_noi_ro_agent_khong_tu_chon() -> None:
    tap = _tap(_pa("a", recommended=True), _pa("b"))
    van_ban = tap.render()

    assert "Agent KHÔNG tự chọn" in van_ban
    assert "Agent gợi ý" in van_ban


def test_ban_in_sau_khi_chon_danh_dau_cai_da_chon() -> None:
    tap = _tap(_pa("a"), _pa("b"))
    van_ban = tap.render(chosen_id="b")

    assert "ĐÃ CHỌN" in van_ban
    assert "Agent KHÔNG tự chọn" not in van_ban
