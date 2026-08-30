"""TC-59 — bàn giao và vận hành (N-094, N-101, N-102, N-103).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-59a | Tài liệu vận hành sinh TỪ dữ liệu dự án | N-094 — không chép tay |
| TC-59b | Mục "KHÔNG làm được" dựng từ chỗ hở thật | không phải văn khiêm tốn |
| TC-59c | Đổi linh kiện chỉ đích danh module bị chạm | N-101 — bắc cầu trên đồ thị |
| TC-59d | Bảng so sánh không chứa dòng "giống nhau" | dòng khác biệt sẽ lướt qua cùng |
| TC-59e | Ca hiện trường không tái hiện ⇒ CHƯA KẾT LUẬN ĐƯỢC | N-102 |
| TC-59f | Điều kiện còn thiếu được hỏi đích danh | dựng lại mà thiếu là đoán |
| TC-59g | Bậc triển khai đầu tiên có ĐÚNG MỘT thiết bị | N-103 |
| TC-59h | Không có đường lui ⇒ không triển khai được | N-103 |

TC-59b là chỗ dễ làm cho có nhất. Một mục "giới hạn đã biết" viết tay sẽ liệt
kê những giới hạn người viết NHỚ RA, tức là những giới hạn ít nguy hiểm nhất.
Dựng từ dữ liệu thì nó liệt kê những giới hạn dự án tự khai mình còn hở — giả
định chưa kiểm, kịch bản chưa có phần đo, errata chưa tra.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.diagnostics import (
    CHUA_THU,
    KHONG_TAI_HIEN,
    TAI_HIEN_DUOC,
    FieldCase,
    ScenarioLibrary,
)
from eaa.handover import (
    ComponentDelta,
    HandoverError,
    LlmSwapAnalyst,
    OperationsHandbook,
    RolloutPlan,
    RolloutStage,
    SwapAnalysis,
)

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


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
    raw = {
        "assumptions": [
            {
                "id": "ma-sat",
                "statement": "hệ số ma sát = 0,02",
                "status": "proposed",
                "how_to_verify": "thả dốc rồi đo quãng đường trôi",
            },
            {"id": "khoi-luong", "statement": "khối lượng = 0,85 kg", "status": "verified"},
        ]
    }
    mcu = {"part": "chip-gia-1"}
    peripherals = [{"id": "bus_a", "configured_by": ["REG_A1", "REG_A2"]}]
    components: list = []

    def registers_of(self, peripheral_id: str):
        return ("REG_A1", "REG_A2") if peripheral_id == "bus_a" else ()


class _RangBuocGia:
    acceptance = {
        "measurements": [
            {"name": "max_tilt_deg", "key": "max_tilt_deg", "unit": "°", "max": 1.0}
        ]
    }


class _Module:
    def __init__(self, ma: str, *uses: str) -> None:
        self.id = ma
        self.uses = uses


class _KichBan:
    def __init__(self, ma: str, firmware_template: str = "", manual=()) -> None:
        self.id = ma
        self.title = ma
        self.firmware_template = firmware_template
        self.manual = manual
        self.symptoms: tuple[str, ...] = ()
        self.motion = False


# --------------------------------------------------------------------------
# TC-59a, TC-59b — tài liệu vận hành
# --------------------------------------------------------------------------


def _so_tay(**kw) -> OperationsHandbook:
    kw.setdefault("project", "du-an-thu")
    kw.setdefault("hardware", _HoSoGia())
    kw.setdefault("constraints", _RangBuocGia())
    return OperationsHandbook(**kw)


def test_tai_lieu_co_du_bon_phan() -> None:
    van_ban = _so_tay().render()
    for muc in ("Nạp firmware", "Đo và nghiệm thu", "Chẩn đoán", "KHÔNG làm được"):
        assert muc in van_ban


def test_bang_so_do_lay_tu_tieu_chi_nghiem_thu_cua_du_an() -> None:
    """Không chép tay: sửa constraints rồi sinh lại là tài liệu đúng trở lại."""
    van_ban = _so_tay().render()
    assert "max_tilt_deg" in van_ban
    assert "≤ 1.0" in van_ban


def test_gia_dinh_chua_kiem_vao_muc_khong_lam_duoc() -> None:
    gioi_han = _so_tay().limitations()

    assert any("hệ số ma sát" in g for g in gioi_han)
    assert any("thả dốc" in g for g in gioi_han), "phải kèm cách kiểm"
    assert not any("khối lượng" in g for g in gioi_han), "giả định đã kiểm thì không phải giới hạn"


def test_kich_ban_chua_co_phan_do_vao_muc_khong_lam_duoc() -> None:
    gioi_han = _so_tay(scenarios=(_KichBan("DS-09"),)).limitations()
    assert any("DS-09" in g and "chưa có phần đo" in g for g in gioi_han)


def test_errata_chua_tra_vao_muc_khong_lam_duoc() -> None:
    class _ErrataChuaTra:
        looked_up = False

    gioi_han = _so_tay(errata=_ErrataChuaTra()).limitations()
    assert any("Chưa tra errata" in g for g in gioi_han)


def test_kieu_hong_khong_phat_hien_duoc_vao_muc_khong_lam_duoc() -> None:
    class _KieuHong:
        id = "cam_bien_ket"
        detectable = False

    class _AnToan:
        modes = (_KieuHong(),)

    gioi_han = _so_tay(safety=_AnToan()).limitations()
    assert any("cam_bien_ket" in g and "KHÔNG phát hiện được" in g for g in gioi_han)


def test_khong_tim_thay_gioi_han_nao_thi_noi_do_la_dang_ngo() -> None:
    """Một dự án thật luôn có chỗ hở; không thấy gì nghĩa là chưa ai điền."""

    class _HoSoSach:
        raw: dict = {}
        mcu = {"part": "x"}
        peripherals: list = []
        components: list = []

    van_ban = _so_tay(hardware=_HoSoSach()).render()
    assert "đáng ngờ hơn là đáng mừng" in van_ban


def test_chua_nap_lan_nao_thi_noi_thang_la_khong_biet() -> None:
    class _NhatKyTrong:
        def last_success(self):
            return None

    van_ban = _so_tay(flash_log=_NhatKyTrong()).render()
    assert "KHÔNG biết bản nào đang trên thiết bị" in van_ban


def test_chay_that_tren_du_an_mau() -> None:
    from eaa.kb import Constraints, HardwareProfile

    thu_vien = ScenarioLibrary.load(DU_AN / "diagnostics.yaml")
    so_tay = OperationsHandbook(
        project="robot_balance",
        hardware=HardwareProfile.load(DU_AN / "hardware_profile.yaml"),
        constraints=Constraints.load(DU_AN / "constraints.yaml"),
        scenarios=thu_vien.scenarios,
    )
    van_ban = so_tay.render()

    assert "DS-03" in van_ban
    assert "cần checklist an toàn" in van_ban
    assert so_tay.limitations(), "dự án mẫu có phép đo tay, nên phải có giới hạn"


# --------------------------------------------------------------------------
# TC-59c, TC-59d — đổi linh kiện
# --------------------------------------------------------------------------


def test_khac_biet_hai_ben_giong_nhau_bi_tu_choi() -> None:
    """Bảng đầy dòng 'giống nhau' sẽ được lướt qua, và dòng khác biệt lướt cùng."""
    with pytest.raises(HandoverError, match="giống nhau"):
        ComponentDelta(aspect="dải điện áp", old="3,3 V", new="3,3 V")


def test_module_cham_khac_biet_duoc_goi_dich_danh() -> None:
    ban = SwapAnalysis(
        old_part="linh-kien-1",
        new_part="linh-kien-2",
        deltas=(
            ComponentDelta(
                aspect="địa chỉ mặc định",
                old="0x68",
                new="0x69",
                touches=("REG_A1",),
            ),
        ),
    )
    cham = ban.impacts(_HoSoGia(), [_Module("drv_a", "bus_a"), _Module("lib_toan")])

    assert len(cham) == 1
    assert cham[0].module_id == "drv_a"
    assert "REG_A1" in cham[0].reason


def test_module_cham_qua_TEN_TAI_NGUYEN_cung_duoc_goi_ten() -> None:
    ban = SwapAnalysis(
        old_part="a",
        new_part="b",
        deltas=(ComponentDelta(aspect="giao thức", old="i2c", new="spi", touches=("bus_a",)),),
    )
    assert ban.impacts(_HoSoGia(), [_Module("drv_a", "bus_a")])[0].module_id == "drv_a"


def test_thay_thang_duoc_van_phai_chay_lai_chan_doan() -> None:
    """'Thay thẳng được' là lời hứa về chân, không phải về dải hoạt động."""
    van_ban = SwapAnalysis(old_part="a", new_part="b", drop_in=True).render()

    assert "THAY THẲNG ĐƯỢC" in van_ban
    assert "Vẫn phải chạy lại" in van_ban


def test_bao_cao_khong_noi_ma_sai_o_dau() -> None:
    """Danh sách nêu module ĐỤNG TỚI thứ đã đổi; đọc mã vẫn là việc của người."""
    ban = SwapAnalysis(
        old_part="a",
        new_part="b",
        deltas=(ComponentDelta(aspect="x", old="1", new="2", touches=("bus_a",)),),
    )
    van_ban = ban.render(_HoSoGia(), [_Module("drv_a", "bus_a")])
    assert "vẫn là việc đọc mã của người" in van_ban


def test_so_linh_kien_bang_mo_hinh() -> None:
    llm = _json(
        {
            "drop_in": False,
            "deltas": [
                {
                    "aspect": "dải điện áp",
                    "old": "2,3–3,4 V",
                    "new": "1,7–3,6 V",
                    "impact": "không đổi mã, nhưng nới được nguồn cấp",
                    "touches": ["bus_a"],
                }
            ],
        }
    )
    ban = LlmSwapAnalyst(llm=llm).compare(old_part="a", new_part="b")

    assert len(ban.deltas) == 1
    assert ban.proposed_by == "mo-hinh-gia-1"


def test_mo_hinh_tra_ve_dong_giong_nhau_thi_khong_lot() -> None:
    llm = _json({"deltas": [{"aspect": "chân", "old": "8 chân", "new": "8 chân"}]})
    with pytest.raises(HandoverError, match="giống nhau"):
        LlmSwapAnalyst(llm=llm).compare(old_part="a", new_part="b")


# --------------------------------------------------------------------------
# TC-59e, TC-59f — sự cố hiện trường
# --------------------------------------------------------------------------


def test_khong_tai_hien_duoc_la_CHUA_KET_LUAN_DUOC() -> None:
    ca = FieldCase(symptom="reset ngẫu nhiên", reproduced=KHONG_TAI_HIEN)
    van_ban = ca.verdict()

    assert "CHƯA KẾT LUẬN ĐƯỢC" in van_ban
    assert "dữ kiện yếu nhất" in van_ban
    assert "ĐI LẤY THÊM DỮ KIỆN" in van_ban


def test_chua_thu_dung_lai_thi_nhac_do_la_buoc_dau_tien() -> None:
    ca = FieldCase(symptom="reset ngẫu nhiên", reproduced=CHUA_THU)
    assert "CHƯA THỬ DỰNG LẠI" in ca.verdict()
    assert "không xảy ra trước mặt ta" in ca.verdict()


def test_tai_hien_duoc_thi_di_tiep_nhu_mot_phien_tren_ban() -> None:
    ca = FieldCase(symptom="reset ngẫu nhiên", reproduced=TAI_HIEN_DUOC)
    assert "TÁI HIỆN ĐƯỢC" in ca.verdict()


def test_dieu_kien_con_thieu_duoc_hoi_dich_danh() -> None:
    ca = FieldCase(symptom="x", conditions={"uptime": "4h"})
    thieu = ca.missing_context()

    assert not any(t.startswith("uptime") for t in thieu)
    assert any(t.startswith("power") for t in thieu)
    assert any(t.startswith("recent_change") for t in thieu)


def test_du_dieu_kien_thi_khong_hoi_nua() -> None:
    ca = FieldCase(
        symptom="x",
        conditions={
            "uptime": "4h", "load": "nặng", "power": "pin yếu",
            "environment": "35°C", "recent_change": "không",
        },
    )
    assert ca.missing_context() == []


def test_chon_kich_ban_tu_trieu_chung_nguoi_ke() -> None:
    thu_vien = ScenarioLibrary.load(DU_AN / "diagnostics.yaml")
    ca = FieldCase(symptom="động cơ không quay khi bật nguồn")

    assert [s.id for s in ca.plan(thu_vien)] == ["DS-03"]


def test_trieu_chung_chua_co_kich_ban_nao_phu_cung_la_mot_du_kien() -> None:
    thu_vien = ScenarioLibrary.load(DU_AN / "diagnostics.yaml")
    ca = FieldCase(symptom="vỏ máy đổi màu")
    van_ban = ca.render(thu_vien)

    assert "không kịch bản nào khớp" in van_ban
    assert "bổ sung một kịch bản" in van_ban


# --------------------------------------------------------------------------
# TC-59g, TC-59h — cập nhật thiết bị đã triển khai
# --------------------------------------------------------------------------


def test_bac_dau_tien_phai_co_dung_mot_thiet_bi() -> None:
    """Bản vá hỏng nhân lên bằng số thiết bị đã nhận nó."""
    ke_hoach = RolloutPlan.default(from_commit="a" * 40, to_commit="b" * 40, rollback_to="a" * 40)

    assert ke_hoach.stages[0].devices == 1
    assert ke_hoach.ok


def test_bac_dau_nhieu_hon_mot_thiet_bi_bi_chan() -> None:
    ke_hoach = RolloutPlan(
        from_commit="a" * 40,
        to_commit="b" * 40,
        rollback_to="a" * 40,
        stages=(RolloutStage("thử", devices=5, soak_hours=1, stop_if=("hỏng",)),),
    )
    assert not ke_hoach.ok
    assert any("ĐÚNG MỘT" in v for v in ke_hoach.problems())


def test_khong_co_duong_lui_thi_khong_trien_khai_duoc() -> None:
    ke_hoach = RolloutPlan(from_commit="a" * 40, to_commit="b" * 40, rollback_to="")

    assert not ke_hoach.ok
    assert any("mang về xưởng" in v for v in ke_hoach.problems())
    assert "KHÔNG TRIỂN KHAI ĐƯỢC" in ke_hoach.render()


def test_ban_quay_lui_trung_ban_dang_trien_khai_bi_bat() -> None:
    ke_hoach = RolloutPlan(
        from_commit="a" * 40, to_commit="b" * 40, rollback_to="b" * 40,
        stages=(RolloutStage("thử", 1, 1, ("hỏng",)),),
    )
    assert any("không phải một đường lui" in v for v in ke_hoach.problems())


def test_bac_khong_neu_dieu_kien_dung_bi_tu_choi() -> None:
    """Không có điều kiện dừng thì mọi bậc đều chạy, dù bậc đầu đã hỏng."""
    with pytest.raises(HandoverError, match="ĐIỀU KIỆN DỪNG"):
        RolloutStage("thử", devices=1, soak_hours=24, stop_if=())


def test_so_thiet_bi_moi_bac_phai_tang_dan() -> None:
    ke_hoach = RolloutPlan(
        from_commit="a" * 40, to_commit="b" * 40, rollback_to="c" * 40,
        stages=(
            RolloutStage("thử", 1, 24, ("hỏng",)),
            RolloutStage("nhóm", 100, 72, ("hỏng",)),
            RolloutStage("cuối", 10, 0, ("hỏng",)),
        ),
    )
    assert any("tăng dần" in v for v in ke_hoach.problems())


def test_ke_hoach_hop_le_van_can_nguoi_bam_nut_tung_bac() -> None:
    van_ban = RolloutPlan.default(
        from_commit="a" * 40, to_commit="b" * 40, rollback_to="a" * 40
    ).render()
    assert "engine" in van_ban and "không tự chuyển bậc" in van_ban
