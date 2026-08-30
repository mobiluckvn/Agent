"""TC-54 — Agent ĐỀ XUẤT, không chỉ đối chiếu (N-006, N-010, N-011, N-014).

Bốn việc của giai đoạn G0/G1 trước bản này đều có cơ chế và đều thiếu đúng một
nửa: engine đọc được ràng buộc, đối chiếu được tiêu chí, tra được bảng chân —
mà không tự nói ra được đề xuất nào. Đối chiếu bắt đầu từ một danh sách đã có;
đề xuất phải bắt đầu từ trang trắng, và đó mới là chỗ người dùng mắc kẹt.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-54a | Mục NGOÀI phạm vi phải có lý do | thiếu lý do là từ chối ngay lúc dựng |
| TC-54b | Mỗi ràng buộc kèm HỆ QUẢ nếu vi phạm | người duyệt cần căn cứ để BÁC |
| TC-54c | Tiêu chí nghiệm thu = số + đơn vị + cách đo | thiếu bất kỳ phần nào là từ chối |
| TC-54d | Tiêu chí kiểu 'chạy mượt' bị từ chối kèm câu hỏi làm nó đo được | N-011 |
| TC-54e | Bảng chân kiểm chức năng thay thế, ba kết cục | chưa khai bảng ≠ đạt |
| TC-54f | Hai chức năng cùng một chân bị bắt trước khi hàn | N-014 |
| TC-54g | Cả bốn dừng ở ĐỀ XUẤT | không cái nào tự có hiệu lực |

Ranh giới engine cũng được canh ở đây: engine KHÔNG biết chân nào làm được
chức năng gì. Nó đối chiếu với bảng do dự án khai, và nói thẳng khi bảng ấy
chưa có — thay vì im lặng cho qua rồi để người tưởng đã kiểm.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.propose import (
    NGOAI,
    PIN_HO_TRO,
    PIN_KHONG_HO_TRO,
    PIN_KHONG_KIEM_DUOC,
    SCOPE_FILE,
    TRONG,
    AcceptanceCriterion,
    AcceptanceProposal,
    ConstraintItem,
    ConstraintProposal,
    LlmProposer,
    PinAssignment,
    PinMapProposal,
    ProposeError,
    ScopeItem,
    ScopeProposal,
    vague_reason,
)

REPO = Path(__file__).resolve().parent.parent


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


def _json(du_lieu) -> _LlmGia:
    return _LlmGia("```json\n" + json.dumps(du_lieu, ensure_ascii=False) + "\n```")


class _HoSoGia:
    peripherals = [{"id": "twi"}, {"id": "timer1"}]
    components = [{"id": "imu", "kind": "sensor"}]
    mcu = {"part": "chip-gia", "clock_hz": 16_000_000}
    pin_functions = {
        "P1": ["scl", "gpio"],
        "P2": ["sda", "gpio"],
        "P3": ["gpio"],
    }


class _HoSoKhongCoBangChan(_HoSoGia):
    pin_functions: dict = {}


# --------------------------------------------------------------------------
# TC-54a — phạm vi
# --------------------------------------------------------------------------


def test_ngoai_pham_vi_ma_khong_neu_ly_do_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="không nêu vì sao"):
        ScopeItem(feature="điều khiển màn hình", side=NGOAI)


def test_trong_pham_vi_khong_bat_buoc_ly_do() -> None:
    """Lý do của mục trong phạm vi chính là phát biểu bài toán."""
    assert ScopeItem(feature="giữ thăng bằng", side=TRONG).reason == ""


def test_khong_co_muc_ngoai_pham_vi_la_mot_cho_ho() -> None:
    ban = ScopeProposal(items=(ScopeItem("giữ thăng bằng"),))
    assert any("NGOÀI phạm vi" in t for t in ban.gaps())
    assert any("phình" in t for t in ban.gaps())


def test_pham_vi_day_du_thi_khong_con_ho() -> None:
    ban = ScopeProposal(
        items=(
            ScopeItem("giữ thăng bằng"),
            ScopeItem("điều khiển màn hình", NGOAI, "cần thư viện hãng", architectural=True),
        )
    )
    assert ban.gaps() == []
    van_ban = ban.render()
    assert "cần thư viện hãng" in van_ban
    assert "KIẾN TRÚC" in van_ban


def test_pham_vi_song_sot_qua_vong_ghi_doc(tmp_path: Path) -> None:
    goc = ScopeProposal(
        items=(
            ScopeItem("giữ thăng bằng"),
            ScopeItem("ghi thẻ nhớ", NGOAI, "không đủ chân còn trống"),
        ),
        goal="robot hai bánh",
    )
    goc.save(tmp_path / SCOPE_FILE)
    doc = ScopeProposal.load(tmp_path / SCOPE_FILE)

    assert doc is not None
    assert doc.goal == "robot hai bánh"
    assert doc.out_of_scope[0].reason == "không đủ chân còn trống"


def test_khong_co_tep_thi_tra_none(tmp_path: Path) -> None:
    assert ScopeProposal.load(tmp_path / "khong-co.yaml") is None


def test_dung_pham_vi_tu_mo_hinh() -> None:
    llm = _json(
        {
            "goal": "robot hai bánh tự cân bằng",
            "scope": [
                {"feature": "giữ thăng bằng", "side": "trong"},
                {
                    "feature": "điều khiển qua wifi",
                    "side": "ngoai",
                    "reason": "bo không có wifi; thêm module là đổi kiến trúc nguồn",
                    "architectural": True,
                },
            ],
        }
    )
    ban = LlmProposer(llm=llm).scope(goal="robot", hardware=_HoSoGia())

    assert len(ban.in_scope) == 1 and len(ban.out_of_scope) == 1
    assert ban.out_of_scope[0].architectural
    assert ban.proposed_by == "mo-hinh-gia-1"


# --------------------------------------------------------------------------
# TC-54b — ràng buộc kèm hệ quả
# --------------------------------------------------------------------------


def test_rang_buoc_khong_co_he_qua_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="HỆ QUẢ"):
        ConstraintItem(key="control_loop_ms", value=10)


def test_he_qua_la_thu_nguoi_duyet_can_de_bac() -> None:
    muc = ConstraintItem(
        key="control_loop_ms",
        value=10,
        unit="ms",
        rationale="chu kỳ con lắc ngược chiều dài 0,3 m",
        consequence="quá 10 ms thì góc vượt ngưỡng phục hồi và robot đổ",
    )
    van_ban = muc.render()
    assert "vi phạm:" in van_ban
    assert "robot đổ" in van_ban


def test_khoi_limits_chi_mang_tri_so() -> None:
    """Tệp ràng buộc nạp vào 100% prompt — mỗi dòng thừa là token trả mãi mãi."""
    ban = ConstraintProposal(
        items=(
            ConstraintItem("control_loop_ms", 10, "ms", "động lực học", "robot đổ"),
            ConstraintItem("flash_pct_max", 50, "%", "chừa chỗ vá", "hết chỗ khi vá"),
        )
    )
    assert ban.to_limits() == {"control_loop_ms": 10, "flash_pct_max": 50}


def test_dung_rang_buoc_tu_mo_hinh() -> None:
    llm = _json(
        {
            "limits": [
                {
                    "key": "control_loop_ms",
                    "value": 10,
                    "unit": "ms",
                    "rationale": "hằng số thời gian con lắc",
                    "consequence": "vượt thì mất thăng bằng",
                }
            ],
            "forbidden": ["delay()"],
        }
    )
    ban = LlmProposer(llm=llm).constraints(goal="robot", hardware=_HoSoGia())

    assert ban.items[0].consequence
    assert ban.forbidden == ("delay()",)


def test_mo_hinh_tra_ve_rang_buoc_thieu_he_qua_thi_khong_lot() -> None:
    """Bất biến phải chặn cả khi nguồn là mô hình, không chỉ khi người gõ tay."""
    llm = _json({"limits": [{"key": "control_loop_ms", "value": 10}]})
    with pytest.raises(ProposeError, match="HỆ QUẢ"):
        LlmProposer(llm=llm).constraints(goal="robot", hardware=_HoSoGia())


# --------------------------------------------------------------------------
# TC-54c, TC-54d — tiêu chí nghiệm thu đo được
# --------------------------------------------------------------------------


def _tieu_chi(**kw) -> AcceptanceCriterion:
    kw.setdefault("name", "max_tilt_deg")
    kw.setdefault("unit", "°")
    kw.setdefault("max", 1.0)
    kw.setdefault("key", "max_tilt_deg")
    kw.setdefault("method", "đọc từ khung telemetry trong 60 s chạy liên tục")
    return AcceptanceCriterion(**kw)


def test_tieu_chi_khong_co_nguong_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="không có ngưỡng"):
        _tieu_chi(max=None, min=None)


def test_tieu_chi_khong_co_don_vi_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="đơn vị"):
        _tieu_chi(unit="")


def test_tieu_chi_khong_noi_cach_do_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="ĐO BẰNG CÁCH NÀO"):
        _tieu_chi(method="")


def test_lay_tu_telemetry_ma_khong_co_khoa_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="khóa trong khung telemetry"):
        _tieu_chi(key="")


def test_nguon_ngoai_ba_nguon_da_biet_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="không hợp lệ"):
        _tieu_chi(source="cam_giac")


def test_do_bang_dong_ho_thi_khong_can_khoa_telemetry() -> None:
    muc = _tieu_chi(
        name="dong_tieu_thu_ma",
        unit="mA",
        key="",
        source="dong_ho_do",
        method="kẹp ampe kìm vào dây nguồn động lực, đo lúc cả hai động cơ tăng tốc",
    )
    assert "dong_ho_do" in muc.render()


def test_cau_mo_ho_bi_tu_choi_kem_cau_hoi_lam_no_do_duoc() -> None:
    ly_do = vague_reason("robot phải chạy mượt và ổn định")
    assert ly_do
    assert "bao nhiêu thì đủ" in ly_do


def test_cau_co_so_thi_khong_bi_coi_la_mo_ho() -> None:
    assert vague_reason("góc nghiêng không quá 1 độ trong 60 giây") == ""


def test_cau_khong_co_so_nao_van_bi_tu_choi() -> None:
    assert "chưa phải tiêu chí" in vague_reason("robot phải đứng được")


def test_phan_tu_choi_la_phan_dang_doc_nhat() -> None:
    ban = AcceptanceProposal(
        criteria=(_tieu_chi(),),
        rejected=(("chạy mượt", "bao nhiêu độ dao động thì còn coi là mượt?"),),
    )
    van_ban = ban.render()
    assert "TỪ CHỐI vì chưa đo được" in van_ban
    assert "bao nhiêu độ dao động" in van_ban


def test_khoi_acceptance_dan_duoc_vao_constraints() -> None:
    ban = AcceptanceProposal(criteria=(_tieu_chi(),), scenarios=("khởi động tĩnh",))
    khoi = ban.to_acceptance()

    assert khoi["scenarios"] == ["khởi động tĩnh"]
    assert khoi["measurements"][0]["max"] == 1.0
    assert khoi["measurements"][0]["unit"] == "°"


def test_dung_tieu_chi_tu_mo_hinh() -> None:
    llm = _json(
        {
            "measurements": [
                {
                    "name": "max_tilt_deg",
                    "key": "max_tilt_deg",
                    "unit": "°",
                    "max": 1.0,
                    "method": "telemetry 60 s",
                    "source": "telemetry",
                }
            ],
            "scenarios": ["kháng nhiễu"],
            "rejected": [{"statement": "chạy mượt", "reason": "bao nhiêu độ?"}],
        }
    )
    ban = LlmProposer(llm=llm).acceptance(goal="robot")

    assert ban.criteria[0].name == "max_tilt_deg"
    assert ban.rejected[0][0] == "chạy mượt"


# --------------------------------------------------------------------------
# TC-54e, TC-54f — bảng chân
# --------------------------------------------------------------------------


def _bang(*cap: tuple[str, str]) -> PinMapProposal:
    return PinMapProposal(
        assignments=tuple(PinAssignment(pin=p, function=f) for p, f in cap)
    )


def test_chan_khong_neu_chuc_nang_thi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="chức năng gì"):
        PinAssignment(pin="P1", function="")


def test_chan_ho_tro_chuc_nang_thi_dat() -> None:
    ket = _bang(("P1", "scl")).check(_HoSoGia.pin_functions)
    assert ket[0].status == PIN_HO_TRO


def test_chan_khong_ho_tro_chuc_nang_bi_bat_tren_giay() -> None:
    """Loại lỗi chỉ lộ ra sau khi đã hàn — sửa trên giấy rẻ hơn sửa trên bo."""
    ket = _bang(("P3", "scl")).check(_HoSoGia.pin_functions)

    assert ket[0].status == PIN_KHONG_HO_TRO
    assert "gpio" in ket[0].detail
    assert "KHÔNG HỖ TRỢ" in ket[0].render()


def test_chua_khai_bang_chuc_nang_thi_noi_la_chua_kiem_duoc() -> None:
    ket = _bang(("P1", "scl")).check(_HoSoKhongCoBangChan.pin_functions)

    assert ket[0].status == PIN_KHONG_KIEM_DUOC
    assert "pin_functions" in ket[0].detail

    van_ban = _bang(("P1", "scl")).render(_HoSoKhongCoBangChan.pin_functions)
    assert "KHÔNG có nghĩa là 'đạt'" in van_ban


def test_chan_ngoai_bang_da_khai_cung_la_chua_kiem_duoc() -> None:
    ket = _bang(("P9", "scl")).check(_HoSoGia.pin_functions)
    assert ket[0].status == PIN_KHONG_KIEM_DUOC


def test_hai_chuc_nang_cung_mot_chan_bi_bat() -> None:
    ban = _bang(("P1", "scl"), ("P1", "pwm"))
    xung_dot = ban.conflicts()

    assert len(xung_dot) == 1
    assert "scl" in xung_dot[0] and "pwm" in xung_dot[0]
    assert "XUNG ĐỘT" in ban.render(_HoSoGia.pin_functions)


def test_khoi_pin_map_dan_duoc_vao_ho_so_phan_cung() -> None:
    ban = PinMapProposal(
        assignments=(
            PinAssignment(pin="P1", function="scl", direction="inout", peripheral="twi"),
        )
    )
    khoi = ban.to_pin_map()
    assert khoi["P1"]["function"] == "scl"
    assert khoi["P1"]["peripheral"] == "twi"
    assert "note" not in khoi["P1"], "trường rỗng không được ghi ra làm loãng tệp"


def test_ho_so_trong_thi_khong_dung_bang_chan() -> None:
    class _Trong:
        peripherals: list = []
        components: list = []

    with pytest.raises(ProposeError, match="CÓ THẬT"):
        LlmProposer(llm=_json({})).pin_map(hardware=_Trong())


def test_dung_bang_chan_tu_mo_hinh() -> None:
    llm = _json(
        {"pin_map": [{"pin": "P1", "function": "scl", "direction": "inout", "peripheral": "twi"}]}
    )
    ban = LlmProposer(llm=llm).pin_map(hardware=_HoSoGia(), goal="robot")
    assert ban.assignments[0].pin == "P1"


def test_bang_chuc_nang_da_khai_duoc_dua_vao_prompt() -> None:
    """Mô hình phải thấy bảng ấy, nếu không nó sẽ đề xuất chân không dùng được."""
    llm = _json({"pin_map": []})
    LlmProposer(llm=llm).pin_map(hardware=_HoSoGia())

    van_ban = "\n".join(l.content for l in llm.prompts[0].layers)
    assert "P1: scl, gpio" in van_ban


def test_chua_khai_bang_thi_prompt_noi_thang_la_khong_kiem_duoc() -> None:
    llm = _json({"pin_map": []})
    LlmProposer(llm=llm).pin_map(hardware=_HoSoKhongCoBangChan())

    van_ban = "\n".join(l.content for l in llm.prompts[0].layers)
    assert "KHÔNG kiểm được" in van_ban


# --------------------------------------------------------------------------
# TC-54g — cả bốn dừng ở đề xuất; ranh giới engine
# --------------------------------------------------------------------------


def test_moi_ban_deu_noi_ro_nguoi_moi_la_nguoi_chot() -> None:
    assert "người" in _bang(("P1", "scl")).render(_HoSoGia.pin_functions)
    assert "N-014" in _bang(("P1", "scl")).render(_HoSoGia.pin_functions)


def test_engine_khong_biet_chan_nao_lam_duoc_gi() -> None:
    """Bảng chức năng thay thế là tri thức của MỘT họ vi điều khiển.

    Ghim nó vào engine là đúng thứ TC-38 canh, nhìn từ một góc cụ thể.
    """
    ma = (REPO / "eaa" / "propose.py").read_text(encoding="utf-8")
    for chuc_nang in ("scl", "sda", "mosi", "miso", "ocr", "adc0"):
        assert f'"{chuc_nang}"' not in ma.lower(), f"{chuc_nang} bị ghim trong engine"


def test_ho_so_phan_cung_doc_duoc_bang_chuc_nang() -> None:
    from eaa.kb import HardwareProfile

    hp = HardwareProfile.load(REPO / "projects" / "robot_balance" / "hardware_profile.yaml")
    assert isinstance(hp.pin_functions, dict), "thuộc tính phải tồn tại kể cả khi chưa khai"
