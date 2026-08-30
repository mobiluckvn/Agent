"""TC-57 — tiêm lỗi trong mô phỏng và đề xuất mô hình đối tượng (N-063, N-060).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-57a | Bốn kiểu hỏng ở N-016 tiêm được vào mô phỏng | rác, kẹt, mất mẫu, sụt nguồn |
| TC-57b | Kịch bản đòi chế độ an toàn: không vào là KHÔNG ĐẠT | N-063 |
| TC-57c | Bộ điều khiển không báo trạng thái an toàn ⇒ KHÔNG KIỂM ĐƯỢC | khác hẳn "không vào" |
| TC-57d | Vào được chế độ an toàn rồi ngã KHÔNG bị tính là trượt | cắt lệnh thì phải ngã |
| TC-57e | Dự án mẫu vào được chế độ an toàn với cả rác lẫn kẹt | chạy thật, không dựng cảnh |
| TC-57f | Tham số mô hình chưa đo phải nói cách đo | N-060 |
| TC-57g | Mô hình phải nêu hiện tượng nó BỎ QUA | không nêu là từ chối |

TC-57c là chỗ dễ mất thông tin nhất. "Đã kiểm và hệ không vào chế độ an toàn"
với "chưa kiểm được vì bộ điều khiển không báo" là hai điều khác hẳn nhau, và
gộp chúng vào một cờ nhị phân là đúng lỗi mà N-075 mắc phải ở chỗ nạp firmware.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from eaa.propose import (
    DA_DO,
    TU_TAI_LIEU,
    UOC_LUONG,
    LlmProposer,
    PlantModelProposal,
    PlantParameter,
    ProposeError,
)
from eaa.tools.sim_runner import (
    FAULT_KINDS,
    FaultSpec,
    Scenario,
    SimError,
    run_scenario,
)

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


# --------------------------------------------------------------------------
# Mô hình và bộ điều khiển tối giản — kiểm CƠ CHẾ, không kiểm vật lý
# --------------------------------------------------------------------------


class _TrangThai:
    def __init__(self) -> None:
        self.theta = 0.0
        self.theta_dot = 0.0
        self.x_dot = 0.0


class _PlantGia:
    """Tích phân lệnh vào góc. Đủ để cơ chế tiêm lỗi lộ ra, không hơn."""

    def __init__(self, nga_o: float = 1.0) -> None:
        self.state = _TrangThai()
        self.fallen = False
        self.nga_o = nga_o

    def reset(self, theta: float = 0.0, theta_dot: float = 0.0) -> None:
        self.state = _TrangThai()
        self.state.theta = theta
        self.state.theta_dot = theta_dot
        self.fallen = False

    def step(self, u: float, dt: float) -> None:
        self.state.theta += u * dt
        if abs(self.state.theta) > self.nga_o:
            self.fallen = True


class _CtlKhongBaoAnToan:
    """Không có ``safe`` lẫn ``is_safe()`` — cố ý."""

    def __init__(self) -> None:
        self.nhin_thay: list[float] = []

    def reset(self) -> None:
        self.nhin_thay = []

    def step(self, measurement: dict[str, float], dt: float) -> float:
        self.nhin_thay.append(float(measurement.get("angle", 0.0)))
        return 0.0


class _CtlBaoAnToan(_CtlKhongBaoAnToan):
    """Vào chế độ an toàn khi số đo ra ngoài dải."""

    def __init__(self, nguong: float = 10.0) -> None:
        super().__init__()
        self.safe = False
        self.nguong = nguong

    def reset(self) -> None:
        super().reset()
        self.safe = False

    def step(self, measurement: dict[str, float], dt: float) -> float:
        goc = float(measurement.get("angle", 0.0))
        self.nhin_thay.append(goc)
        if abs(goc) > self.nguong:
            self.safe = True
        return 0.0 if self.safe else 1.0


def _kich_ban(**kw) -> Scenario:
    kw.setdefault("name", "thu")
    kw.setdefault("duration_s", 1.0)
    return Scenario(**kw)


# --------------------------------------------------------------------------
# TC-57a — bốn kiểu hỏng
# --------------------------------------------------------------------------


def test_du_bon_kieu_hong_cua_danh_sach_N016() -> None:
    assert set(FAULT_KINDS) == {"stuck", "garbage", "dropout", "power_sag"}


def test_kieu_hong_la_bi_tu_choi_ngay_luc_doc_kich_ban() -> None:
    with pytest.raises(SimError, match="không nhận biết"):
        FaultSpec(kind="chay_no")


def test_loi_khong_neu_thoi_luong_thi_hong_luon_khong_hoi_phuc() -> None:
    """Đúng dạng của phần lớn hỏng hóc thật."""
    loi = FaultSpec(kind="stuck", at_s=1.0)
    assert not loi.active_at(0.5)
    assert loi.active_at(1.0) and loi.active_at(1000.0)


def test_loi_co_thoi_luong_thi_het_han(_=None) -> None:
    loi = FaultSpec(kind="power_sag", at_s=1.0, duration_s=0.5)
    assert loi.active_at(1.2)
    assert not loi.active_at(1.6)


def test_rac_day_so_do_ra_ngoai_moi_dai_vat_ly() -> None:
    ctl = _CtlKhongBaoAnToan()
    run_scenario(
        _PlantGia(nga_o=10**9),
        ctl,
        _kich_ban(faults=[FaultSpec(kind="garbage", at_s=0.5)]),
        control_period_s=0.01,
        substeps=1,
    )
    assert max(abs(x) for x in ctl.nhin_thay) > 50.0


def test_ket_giu_nguyen_so_do_cuoi() -> None:
    ctl = _CtlKhongBaoAnToan()
    plant = _PlantGia(nga_o=10**9)

    class _CtlDay(_CtlKhongBaoAnToan):
        def step(self, measurement, dt):
            super().step(measurement, dt)
            return 1.0

    ctl = _CtlDay()
    run_scenario(
        plant,
        ctl,
        _kich_ban(faults=[FaultSpec(kind="stuck", at_s=0.5)]),
        control_period_s=0.01,
        substeps=1,
    )
    sau_khi_hong = ctl.nhin_thay[55:]
    assert len(set(sau_khi_hong)) == 1, "kẹt nghĩa là mọi mẫu về sau giống hệt nhau"


def test_sut_nguon_lam_yeu_luc_that_su_ra_duoc() -> None:
    """Sụt áp tác động SAU mô hình chấp hành — nó không sửa lệnh đã phát."""

    class _CtlDay(_CtlKhongBaoAnToan):
        def step(self, measurement, dt):
            super().step(measurement, dt)
            return 1.0

    day_du = _PlantGia(nga_o=10**9)
    run_scenario(day_du, _CtlDay(), _kich_ban(), control_period_s=0.01, substeps=1)

    sut = _PlantGia(nga_o=10**9)
    run_scenario(
        sut,
        _CtlDay(),
        _kich_ban(faults=[FaultSpec(kind="power_sag", at_s=0.0, magnitude=0.25)]),
        control_period_s=0.01,
        substeps=1,
    )
    assert sut.state.theta == pytest.approx(day_du.state.theta * 0.25, rel=1e-6)


def test_khong_tiem_loi_thi_khong_co_so_lieu_lien_quan() -> None:
    kq = run_scenario(
        _PlantGia(), _CtlKhongBaoAnToan(), _kich_ban(), control_period_s=0.01, substeps=1
    )
    assert "safe_state_entered" not in kq.metrics
    assert "faults_injected" not in kq.metrics


# --------------------------------------------------------------------------
# TC-57b, TC-57c, TC-57d — phán quyết
# --------------------------------------------------------------------------


def test_doi_che_do_an_toan_ma_khong_vao_thi_khong_dat() -> None:
    kq = run_scenario(
        _PlantGia(nga_o=10**9),
        _CtlBaoAnToan(nguong=10**9),   # ngưỡng cao nên không bao giờ vào
        _kich_ban(
            faults=[FaultSpec(kind="garbage", at_s=0.2)],
            thresholds={"require_safe_state": True},
        ),
        control_period_s=0.01,
        substeps=1,
    )
    assert not kq.passed
    assert kq.metrics["safe_state_entered"] == 0.0
    assert any("KHÔNG vào chế độ an toàn" in v for v in kq.violations)


def test_khong_bao_trang_thai_an_toan_la_KHONG_KIEM_DUOC_chu_khong_phai_khong_vao() -> None:
    """Hai điều khác hẳn nhau. Gộp chúng là đúng lỗi mà N-075 mắc ở chỗ nạp."""
    kq = run_scenario(
        _PlantGia(nga_o=10**9),
        _CtlKhongBaoAnToan(),
        _kich_ban(
            faults=[FaultSpec(kind="garbage", at_s=0.2)],
            thresholds={"require_safe_state": True},
        ),
        control_period_s=0.01,
        substeps=1,
    )
    assert kq.metrics["safe_state_entered"] == -1.0
    assert any("KHÔNG kiểm được" in v for v in kq.violations)
    assert any("không phải là đạt" in v for v in kq.violations)


def test_vao_duoc_che_do_an_toan_thi_dat() -> None:
    kq = run_scenario(
        _PlantGia(nga_o=10**9),
        _CtlBaoAnToan(nguong=50.0),
        _kich_ban(
            faults=[FaultSpec(kind="garbage", at_s=0.2)],
            thresholds={"require_safe_state": True},
        ),
        control_period_s=0.01,
        substeps=1,
    )
    assert kq.passed
    assert kq.metrics["safe_state_entered"] == 1.0


def test_vao_an_toan_roi_nga_khong_bi_tinh_la_truot() -> None:
    """Chế độ an toàn cắt lệnh chấp hành, và một robot bị cắt lệnh thì ngã.

    Đòi nó vừa vào chế độ an toàn vừa đứng vững là đòi hai điều loại trừ nhau.
    """
    kq = run_scenario(
        _PlantGia(nga_o=0.001),   # ngã gần như ngay lập tức
        _CtlBaoAnToan(nguong=50.0),
        _kich_ban(
            faults=[FaultSpec(kind="garbage", at_s=0.0)],
            thresholds={"require_safe_state": True},
        ),
        control_period_s=0.01,
        substeps=1,
    )
    assert kq.passed, "vào được chế độ an toàn là đạt, dù có ngã"
    assert not any("NGÃ" in v for v in kq.violations)


def test_nga_ma_KHONG_vao_an_toan_thi_van_bi_tinh_la_nga() -> None:
    kq = run_scenario(
        _PlantGia(nga_o=0.001),
        _CtlBaoAnToan(nguong=10**9),
        _kich_ban(
            faults=[FaultSpec(kind="garbage", at_s=0.0)],
            thresholds={"require_safe_state": True},
        ),
        control_period_s=0.01,
        substeps=1,
    )
    assert not kq.passed
    assert any("NGÃ" in v for v in kq.violations)


def test_kich_ban_khong_doi_an_toan_thi_nga_van_la_truot() -> None:
    class _CtlDay(_CtlKhongBaoAnToan):
        def step(self, measurement, dt):
            super().step(measurement, dt)
            return 1.0

    kq = run_scenario(
        _PlantGia(nga_o=0.001),
        _CtlDay(),
        _kich_ban(faults=[FaultSpec(kind="power_sag", at_s=0.0, magnitude=1.0)]),
        control_period_s=0.01,
        substeps=1,
    )
    assert not kq.passed and any("NGÃ" in v for v in kq.violations)


# --------------------------------------------------------------------------
# TC-57e — chạy thật trên dự án mẫu
# --------------------------------------------------------------------------


def _chay_that(ten: str) -> dict[str, str]:
    ket_qua = subprocess.run(
        [
            sys.executable,
            "-m",
            "eaa.tools.sim_runner",
            f"--model={DU_AN / 'sim' / 'model.py'}",
            f"--scenarios={DU_AN / 'sim' / 'scenarios.yaml'}",
            f"--controller=python:{DU_AN / 'sim' / 'controller.py'}:create",
            f"--scenario={ten}",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert ket_qua.returncode in (0, 1), ket_qua.stderr
    return dict(
        d.split("=", 1)
        for d in ket_qua.stdout.splitlines()
        if "=" in d and not d.startswith("violation")
    )


@pytest.mark.parametrize("ten", ["loi_cam_bien_tra_rac", "loi_cam_bien_ket"])
def test_du_an_mau_vao_duoc_che_do_an_toan(ten: str) -> None:
    """Hai kiểu hỏng, hai cơ chế phát hiện khác nhau, cùng một kết cục."""
    so_lieu = _chay_that(ten)

    assert so_lieu["stable"] == "true"
    assert so_lieu["safe_state_entered"] == "1"


def test_du_an_mau_chiu_duoc_sut_nguon_ngan() -> None:
    """Sụt áp ngắn là điều hệ phải chịu được, không phải điều nó được bỏ cuộc."""
    so_lieu = _chay_that("loi_nguon_sut_ap")

    assert so_lieu["stable"] == "true"
    assert so_lieu["safe_state_entered"] == "0", "không được bỏ cuộc quá sớm"
    assert float(so_lieu["max_angle_deg"]) < 3.0


def test_ba_kich_ban_cu_van_xanh_sau_khi_them_che_do_an_toan() -> None:
    """Chống thoái lui: thêm cơ chế phát hiện không được làm hỏng phần đang chạy."""
    for ten in ("khoi_dong_tinh", "khang_nhieu", "hoat_dong_dai_han"):
        assert _chay_that(ten)["stable"] == "true", ten


# --------------------------------------------------------------------------
# TC-57f, TC-57g — mô hình đối tượng
# --------------------------------------------------------------------------


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


def test_tham_so_uoc_luong_phai_noi_cach_do() -> None:
    with pytest.raises(ProposeError, match="đo bằng cách nào"):
        PlantParameter(name="khoi_luong", value=0.85, unit="kg", source=UOC_LUONG)


def test_tham_so_da_do_thi_khong_phai_noi_cach_do() -> None:
    p = PlantParameter(name="khoi_luong", value=0.85, unit="kg", source=DA_DO)
    assert p.verified and "đã đo" in p.render()


def test_tham_so_khong_co_don_vi_bi_tu_choi() -> None:
    with pytest.raises(ProposeError, match="đơn vị"):
        PlantParameter(name="khoi_luong", value=0.85, unit="", source=DA_DO)


def test_mo_hinh_khong_neu_thu_bi_bo_qua_thi_tu_choi() -> None:
    """Một mô hình tự nhận không bỏ qua gì sẽ được tin quá mức."""
    with pytest.raises(ProposeError, match="bỏ qua"):
        PlantModelProposal(kind="con lắc ngược", ignored=())


def test_tham_so_chua_do_di_vao_assumption_log() -> None:
    ban = PlantModelProposal(
        kind="con lắc ngược",
        parameters=(
            PlantParameter("khoi_luong", 0.85, "kg", DA_DO),
            PlantParameter(
                "he_so_ma_sat", 0.02, "1", UOC_LUONG, how_to_measure="thả dốc, đo quãng đường"
            ),
        ),
        ignored=("ma sát trục bánh",),
    )
    nhat_ky = ban.to_assumption_log()

    assert len(nhat_ky) == 1
    assert nhat_ky[0]["id"] == "plant-he_so_ma_sat"
    assert nhat_ky[0]["status"] == "proposed"
    assert "thả dốc" in nhat_ky[0]["how_to_verify"]


def test_ban_do_neu_ro_bao_nhieu_tham_so_chua_do() -> None:
    ban = PlantModelProposal(
        kind="con lắc ngược",
        parameters=(
            PlantParameter("m", 0.85, "kg", DA_DO),
            PlantParameter("b", 0.02, "1", UOC_LUONG, how_to_measure="thả dốc"),
        ),
        ignored=("ma sát trục",),
    )
    van_ban = ban.render()

    assert "1/2 tham số CHƯA ĐO" in van_ban
    assert "BỎ QUA" in van_ban
    assert "thừa hưởng sai số" in van_ban


def test_dung_mo_hinh_tu_mo_hinh_nen() -> None:
    llm = _json(
        {
            "kind": "con lắc ngược trên hai bánh",
            "states": ["theta (rad)", "theta_dot (rad/s)"],
            "equations": "(I+m l^2) θ̈ = m g l θ − m l ẍ",
            "parameters": [
                {"name": "m", "value": 0.85, "unit": "kg", "source": "da_do"},
                {
                    "name": "b",
                    "value": 0.02,
                    "unit": "1",
                    "source": "uoc_luong",
                    "how_to_measure": "thả dốc rồi đo quãng đường trôi",
                },
            ],
            "ignored": ["độ mềm của lốp", "trễ truyền động"],
            "validity": "góc nghiêng dưới 15°",
        }
    )
    ban = LlmProposer(llm=llm).plant_model(plant="robot hai bánh")

    assert len(ban.parameters) == 2
    assert len(ban.assumptions) == 1
    assert "độ mềm của lốp" in ban.ignored


def test_mo_hinh_nen_khong_neu_thu_bi_bo_qua_thi_khong_lot() -> None:
    llm = _json({"kind": "con lắc", "parameters": [], "ignored": []})
    with pytest.raises(ProposeError, match="bỏ qua"):
        LlmProposer(llm=llm).plant_model(plant="robot")


def test_thong_so_co_khi_da_khai_duoc_dua_vao_prompt() -> None:
    class _HoSo:
        raw = {"mechanics": {"wheel_radius_m": 0.0425, "body_mass_kg": 0.85}}

    llm = _json({"ignored": ["x"], "parameters": []})
    LlmProposer(llm=llm).plant_model(plant="robot", hardware=_HoSo())
    van_ban = "\n".join(l.content for l in llm.prompts[0].layers)

    assert "wheel_radius_m=0.0425" in van_ban


# --------------------------------------------------------------------------
# Ranh giới engine
# --------------------------------------------------------------------------


def test_kieu_hong_dat_ten_theo_hanh_vi_chu_khong_theo_linh_kien() -> None:
    """Engine không được biết tên một họ cảm biến nào (FR-PLT-01)."""
    ma = (REPO / "eaa" / "tools" / "sim_runner.py").read_text(encoding="utf-8").lower()
    for ten in ("mpu6050", "gyro", "accelerometer", "a4988"):
        assert ten not in ma, f"{ten} bị ghim trong engine"
