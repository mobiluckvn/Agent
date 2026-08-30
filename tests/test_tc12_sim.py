"""TC-12, TC-13 — cổng mô phỏng và quét tham số.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-12 | SIL là cổng chặn THẬT | mã biên dịch sạch nhưng robot ảo ngã → không commit, báo cáo nêu rõ fail tại cổng mô phỏng |
| TC-13 | Quét tham số MIL | xuất bảng kết quả, đánh dấu vùng ổn định, thời gian chạy hợp lý |

TC-12 là test quan trọng nhất của Sprint 3, vì nó chứng minh cổng mô phỏng
không phải đồ trang trí. Mã trong kịch bản này **qua sạch** compile, đo kích
thước, phân tích tĩnh và kiểm thử đơn vị — bốn cổng đầu không có cách nào biết
robot sẽ ngã. Chỉ cổng thứ năm biết.

Điều kiện tiên quyết của cả tệp này: `tests/test_sim_verification.py` phải
xanh. Một cổng dựa trên mô hình chưa kiểm chứng bằng nghiệm giải tích thì phán
quyết của nó không có giá trị (EAA-SRS-01 §2.2, EAA-STP-04 §3).
"""

from __future__ import annotations

import shutil
import sys
import textwrap
import time
from pathlib import Path

import pytest

from eaa.platform import load_manifest
from eaa.tools.runner import ToolRunner
from eaa.tools.sim import SimBindings, SimGate, parse_sim_output

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
SIM_MAU = REPO / "projects" / "robot_balance" / "sim"
HO_SO_MAU = REPO / "projects" / "robot_balance" / "hardware_profile.yaml"


BO_DIEU_KHIEN_HONG = '''\
"""Bộ điều khiển KHÔNG điều khiển gì — dùng để chứng minh cổng mô phỏng chặn thật.

Mã này hoàn toàn hợp lệ về cú pháp, không vi phạm ràng buộc nào, và sẽ qua sạch
bốn cổng kiểm chứng đầu tiên. Nó chỉ có đúng một vấn đề: robot sẽ ngã.
"""


class KhongLam:
    def reset(self):
        pass

    def step(self, measurement, dt):
        return 0.0


def create(params=None):
    return KhongLam()
'''

BO_DIEU_KHIEN_SAI_DAU = '''\
"""Bộ điều khiển đúng cấu trúc nhưng SAI DẤU phản hồi.

Đây là lỗi thật đã xảy ra khi dựng bộ điều khiển tham chiếu của dự án: mã biên
dịch sạch, phân tích tĩnh không nói gì, kiểm thử đơn vị của từng hàm đều đạt —
và robot lao ngược rồi ngã. Không cổng nào ngoài mô phỏng bắt được.
"""


class SaiDau:
    def __init__(self, kp=38.0):
        self.kp = kp

    def reset(self):
        pass

    def step(self, measurement, dt):
        # Dấu trừ ở đây là toàn bộ lỗi.
        return -self.kp * float(measurement.get("angle", 0.0))


def create(params=None):
    return SaiDau(float((params or {}).get("kp", 38.0)))
'''


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    """Dự án tạm mang mô hình vật lý và bộ điều khiển tham chiếu của dự án mẫu."""
    project = tmp_path / "du_an"
    (project / "sim").mkdir(parents=True)
    for ten in ("model.py", "controller.py", "scenarios.yaml"):
        shutil.copy(SIM_MAU / ten, project / "sim" / ten)
    shutil.copy(HO_SO_MAU, project / "hardware_profile.yaml")
    return project


@pytest.fixture()
def runner(du_an: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=du_an,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


def _cong(du_an: Path, runner: ToolRunner, controller: str = "", **ghi_de) -> SimGate:
    return SimGate(
        runner=runner,
        bindings=SimBindings.from_project(du_an, controller=controller, **ghi_de),
    )


# --------------------------------------------------------------------------
# Cổng mô phỏng cho qua mã tốt
# --------------------------------------------------------------------------


def test_bo_dieu_khien_tham_chieu_giu_duoc_can_bang(du_an: Path, runner: ToolRunner) -> None:
    """Cổng chạy MỌI kịch bản dự án khai, và mọi kịch bản phải xanh.

    Số kịch bản không cố định trong test: dự án thêm một kịch bản là thêm một
    phép kiểm, và một con số cứng ở đây sẽ biến việc thêm phép kiểm thành việc
    làm đỏ bộ test. Từ N-063, dự án mẫu có thêm ba kịch bản tiêm lỗi.
    """
    bao_cao = _cong(du_an, runner).run()

    assert bao_cao.passed, bao_cao.raw_output
    assert bao_cao.metrics["scenarios_run"] >= 3
    assert bao_cao.metrics["scenarios_stable"] == bao_cao.metrics["scenarios_run"]
    # Biên độ dao động xác lập phải sát ngưỡng ±1° của Gate G4.
    assert bao_cao.metrics["steady_state_deg"] < 1.0


# --------------------------------------------------------------------------
# TC-12 — cổng mô phỏng chặn thật
# --------------------------------------------------------------------------


def test_tc12_robot_ao_nga_thi_cong_mo_phong_chan(du_an: Path, runner: ToolRunner) -> None:
    (du_an / "sim" / "khong_lam.py").write_text(BO_DIEU_KHIEN_HONG, encoding="utf-8")
    bao_cao = _cong(
        du_an, runner, controller=f"python:{du_an / 'sim' / 'khong_lam.py'}:create"
    ).run()

    assert not bao_cao.passed
    assert bao_cao.gate == "sim"
    # Báo cáo phải nêu RÕ là hỏng tại cổng mô phỏng, không chỉ "hỏng".
    thong_diep = "\n".join(str(e) for e in bao_cao.errors)
    assert "Robot ảo không đạt" in thong_diep
    assert "NGÃ" in thong_diep


def test_tc12_ma_sai_dau_phan_hoi_bi_bat(du_an: Path, runner: ToolRunner) -> None:
    """Loại lỗi mà bốn cổng trước hoàn toàn không nhìn thấy."""
    (du_an / "sim" / "sai_dau.py").write_text(BO_DIEU_KHIEN_SAI_DAU, encoding="utf-8")
    bao_cao = _cong(
        du_an, runner, controller=f"python:{du_an / 'sim' / 'sai_dau.py'}:create"
    ).run()

    assert not bao_cao.passed
    assert any("NGÃ" in str(e) for e in bao_cao.errors)


def test_tc12_bao_cao_neu_dich_danh_nguong_nao_bi_vuot(du_an: Path, runner: ToolRunner) -> None:
    """Không chỉ nói "không đạt" — phải nói không đạt ở đâu, bao nhiêu."""
    kich_ban = du_an / "sim" / "scenarios.yaml"
    kich_ban.write_text(
        textwrap.dedent(
            """\
            control_period_ms: 10
            substeps: 10
            scenarios:
              - name: nguong_phi_ly
                duration_s: 3.0
                initial:
                  theta_deg: 5.0
                thresholds:
                  max_angle_deg: 0.1
                  steady_state_deg: 0.05
            """
        ),
        encoding="utf-8",
    )
    bao_cao = _cong(du_an, runner).run()

    assert not bao_cao.passed
    thong_diep = "\n".join(str(e) for e in bao_cao.errors)
    assert "max_angle_deg" in thong_diep and "vượt trần" in thong_diep


def test_thieu_mo_hinh_mo_phong_la_KHONG_DAT(du_an: Path, runner: ToolRunner) -> None:
    (du_an / "sim" / "model.py").unlink()
    bao_cao = _cong(du_an, runner).run()

    assert not bao_cao.passed
    assert bao_cao.metrics["env_error"] is True
    assert "KHÔNG được coi là đạt" in str(bao_cao.errors[0])


def test_pack_khong_khai_bao_nang_luc_sim_la_KHONG_DAT(
    du_an: Path, tmp_path: Path
) -> None:
    """Chuỗi FR-VER-01 kết thúc bằng cổng mô phỏng; thiếu nó là chuỗi khuyết."""
    pack = tmp_path / "pack_khong_sim"
    shutil.copytree(PACK_DEMO, pack)
    yaml_path = pack / "pack.yaml"
    noi_dung = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(noi_dung[: noi_dung.index("  sim:")], encoding="utf-8")

    runner = ToolRunner(
        manifest=load_manifest(pack),
        work_dir=du_an,
        base_params={"python": sys.executable, "pack_dir": str(pack)},
    )
    bao_cao = _cong(du_an, runner).run()

    assert not bao_cao.passed
    assert "không khai báo" in str(bao_cao.errors[0])


def test_chay_mot_kich_ban_cu_the(du_an: Path, runner: ToolRunner) -> None:
    bao_cao = _cong(du_an, runner, scenario="khoi_dong_tinh").run()
    assert bao_cao.passed
    assert bao_cao.metrics["scenarios_run"] == 1


# --------------------------------------------------------------------------
# TC-13 — quét tham số
# --------------------------------------------------------------------------


def test_tc13_quet_tham_so_xuat_bang_va_danh_dau_vung_on_dinh(
    du_an: Path, runner: ToolRunner
) -> None:
    bat_dau = time.monotonic()
    bang = _cong(du_an, runner, scenario="khoi_dong_tinh").sweep(
        {"kp": [10, 38], "kd": [3.4], "speed_gain": [0.02, 0.25]}
    )
    thoi_gian = time.monotonic() - bat_dau

    assert len(bang) == 4, "phải chạy đủ mọi tổ hợp"
    assert all("stable" in r for r in bang)
    assert any(r["stable"] for r in bang), "phải tìm được ít nhất một điểm ổn định"
    assert any(not r["stable"] for r in bang), "dải quét phải phủ cả vùng không ổn định"

    # "Thời gian chạy hợp lý" — yêu cầu nguyên văn của TC-13.
    assert thoi_gian < 60, f"quét 4 tổ hợp mất {thoi_gian:.1f}s, quá lâu để dùng được"


def test_tc13_bang_ket_qua_doc_duoc_va_neu_ro_vung_on_dinh(
    du_an: Path, runner: ToolRunner
) -> None:
    bang = _cong(du_an, runner, scenario="khoi_dong_tinh").sweep(
        {"kp": [10, 38], "speed_gain": [0.25]}
    )
    van_ban = SimGate.format_sweep(bang)

    assert "ổn định" in van_ban
    assert "✓ ỔN ĐỊNH" in van_ban and "✗" in van_ban
    assert "kp" in van_ban and "speed_gain" in van_ban
    assert "Vùng ổn định:" in van_ban
    # Máy khoanh vùng, người chọn điểm — bảng phải nói rõ ranh giới ấy.
    assert "người chọn điểm" in van_ban


def test_quet_rong_khong_no(du_an: Path, runner: ToolRunner) -> None:
    assert _cong(du_an, runner).sweep({}) == []
    assert "không có tổ hợp" in SimGate.format_sweep([])


# --------------------------------------------------------------------------
# Bóc tách đầu ra
# --------------------------------------------------------------------------


def test_boc_tach_dau_ra_giu_gia_tri_XAU_NHAT_qua_nhieu_kich_ban() -> None:
    """Báo trung bình sẽ che mất đúng kịch bản đã hỏng."""
    so_lieu, vi_pham, kich_ban = parse_sim_output(
        "scenario=a\nstable=true\nmax_angle_deg=1.0\n"
        "scenario=b\nstable=false\nmax_angle_deg=42.0\nviolation: robot ảo NGÃ\n"
    )
    assert kich_ban == ["a", "b"]
    assert so_lieu["max_angle_deg"] == 42.0
    assert so_lieu["scenarios_stable"] == 1
    assert vi_pham == ["robot ảo NGÃ"]


def test_boc_tach_thoi_gian_on_dinh_khong_bao_gio_lam_dep_so_lieu() -> None:
    """Một kịch bản không bao giờ ổn định (-1) phải nuốt trọn kết quả tổng hợp."""
    so_lieu, _, _ = parse_sim_output(
        "scenario=a\nsettling_time_s=1.2\nscenario=b\nsettling_time_s=-1\n"
    )
    assert so_lieu["settling_time_s"] == -1.0
