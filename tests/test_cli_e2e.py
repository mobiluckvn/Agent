"""Vòng lặp chuẩn end-to-end qua CLI — định nghĩa hoàn thành Sprint 2.

MDD §6 định nghĩa xong Sprint 2 là: "Một module mock đi trọn vòng, merge chỉ
qua G3". Bộ test ở `test_tc06_orchestrator.py` chứng minh điều đó ở tầng
Orchestrator; bộ này chứng minh ở tầng người dùng thật sự chạm vào — dãy lệnh
mà kỹ sư gõ, và các mã thoát mà script thực nghiệm A/B của Chương 3 sẽ đọc.

Hai tầng đều cần: một luồng đúng ở tầng trong vẫn có thể sai ở chỗ nối dây, và
chỗ nối dây chính là nơi dễ lặng lẽ bỏ qua một cổng nhất.

Dùng Platform Pack giả lập nên không đòi máy chạy test có toolchain thật.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_REPAIR_LIMIT, EXIT_WAITING_GATE
from eaa.cli import main

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
DU_AN_MAU = REPO / "projects" / "robot_balance"


@pytest.fixture()
def moi_truong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Một cài đặt EAA hoàn chỉnh trong thư mục tạm."""
    home = tmp_path / "eaa_home"
    (home / "packs").mkdir(parents=True)
    shutil.copytree(PACK_DEMO, home / "packs" / "demo")

    project = home / "projects" / "demo_project"
    project.mkdir(parents=True)
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        (project / ten).write_text(
            (DU_AN_MAU / ten).read_text(encoding="utf-8"), encoding="utf-8"
        )
    # Trỏ dự án sang pack giả lập.
    rb = project / "constraints.yaml"
    rb.write_text(
        "\n".join(
            "platform: demo" if d.startswith("platform:") else d
            for d in rb.read_text(encoding="utf-8").splitlines()
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copytree(DU_AN_MAU / "datasheets", project / "datasheets")
    (project / "tests").mkdir()
    (project / "tests" / "test_smoke.py").write_text(
        "def test_khung_du_an():\n    assert True\n", encoding="utf-8"
    )

    monkeypatch.setenv("EAA_HOME", str(home))
    monkeypatch.setenv("EAA_PROJECT", str(project))
    monkeypatch.setenv("EAA_ACTOR", "Vũ Trí Công")
    return project


def _den_pha_D(capsys) -> None:
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    capsys.readouterr()


# --------------------------------------------------------------------------
# Trọn vòng
# --------------------------------------------------------------------------


def test_mot_module_di_tron_vong_qua_CLI(moi_truong: Path, capsys) -> None:
    _den_pha_D(capsys)

    # Bước 1–10: dừng chờ người, mã thoát 2.
    assert main(["gen", "drv_bus_sensor"]) == EXIT_WAITING_GATE
    ra = capsys.readouterr().out
    for cong in ("compile", "size", "static", "unittests"):
        assert f"{cong}: ĐẠT" in ra
    assert "eaa gate approve G3" in ra

    # Bước 11–13: con người mở cổng, và chỉ khi đó mới có merge.
    assert main(["gate", "approve", "G3"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "Đã merge drv_bus_sensor" in ra

    firmware = moi_truong / "firmware"
    assert (firmware / "src").is_dir()

    from eaa.vcs import GitRepo

    repo = GitRepo(firmware)
    assert repo.current_branch() == "main"
    assert "gate-decision: G3 approved by Vũ Trí Công" in repo.commit_message()

    # Nhật ký quyết định là bằng chứng cho tiêu chí nghiệm thu STP-04 §5.
    quyet_dinh = (moi_truong / "gates" / "decisions.jsonl").read_text(encoding="utf-8")
    assert quyet_dinh.count("approved") == 3  # G1, G2, G3


def test_kpi_xuat_duoc_bang_cho_chuong_3(moi_truong: Path, capsys, tmp_path: Path) -> None:
    _den_pha_D(capsys)
    main(["gen", "drv_bus_sensor"])
    main(["gate", "approve", "G3"])
    capsys.readouterr()

    assert main(["report", "kpi"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "drv_bus_sensor" in ra and "merges" in ra

    dich = tmp_path / "kpi_export.csv"
    assert main(["report", "kpi", "--csv", str(dich)]) == EXIT_OK
    assert dich.is_file()
    from eaa.kpi import COLUMNS

    assert dich.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNS)


# --------------------------------------------------------------------------
# Mã thoát — giao diện mà script thực nghiệm A/B dựa vào (SDD §6)
# --------------------------------------------------------------------------


def test_gen_khi_chua_duyet_gate_thi_bi_tu_choi(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    capsys.readouterr()

    assert main(["gen", "drv_bus_sensor"]) == EXIT_ENV_ERROR
    err = capsys.readouterr().err
    assert "G1" in err and "chưa duyệt" in err


def test_thieu_cong_cu_thi_thoat_ma_loi_moi_truong(
    moi_truong: Path, capsys, monkeypatch
) -> None:
    """Thiếu toolchain là mã thoát 4, không phải 'đã kiểm chứng xong'."""
    _den_pha_D(capsys)
    pack = Path(__import__("os").environ["EAA_HOME"]) / "packs" / "demo" / "pack.yaml"
    pack.write_text(
        pack.read_text(encoding="utf-8").replace(
            '"{python}"', '"chuong-trinh-khong-ton-tai"'
        ),
        encoding="utf-8",
    )

    assert main(["gen", "drv_bus_sensor"]) == EXIT_ENV_ERROR
    assert "eaa doctor" in capsys.readouterr().out


# --------------------------------------------------------------------------
# UC02 — backlog và kiểm xung đột ngay lúc khai báo (quy trình P2)
# --------------------------------------------------------------------------


def test_plan_add_chan_xung_dot_tai_nguyen(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "kernel_tick", "--uses", "timer1"]) == EXIT_OK
    capsys.readouterr()

    assert main(["plan", "add", "drv_stepper", "--uses", "timer1"]) == EXIT_ENV_ERROR
    ra = capsys.readouterr()
    assert "kernel_tick" in ra.out and "timer1" in ra.out
    assert "phân xử" in ra.err

    # Module có xung đột KHÔNG được vào backlog.
    capsys.readouterr()
    main(["plan", "list"])
    assert "drv_stepper" not in capsys.readouterr().out


def test_plan_add_bao_thanh_ghi_chua_co_tai_lieu(moi_truong: Path, capsys) -> None:
    """Mục THIẾU của Bảng kiểm thông tin cần, báo ngay lúc khai báo (AIS §6.2)."""
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "kernel_tick", "--uses", "timer0"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "Chưa có trích đoạn tài liệu cho" in ra
    assert "TCCR0A" in ra


def test_plan_order_doi_thu_tu_uu_tien(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    main(["plan", "add", "mot"])
    main(["plan", "add", "hai"])
    capsys.readouterr()

    assert main(["plan", "order", "hai,mot"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert ra.index("hai") < ra.index("mot")


# --------------------------------------------------------------------------
# TC-02 qua CLI — từ chối có hệ quả đúng
# --------------------------------------------------------------------------


def test_tu_choi_tai_G3_thi_khong_merge(moi_truong: Path, capsys) -> None:
    _den_pha_D(capsys)
    main(["gen", "drv_bus_sensor"])
    capsys.readouterr()

    ma = main(
        ["gate", "reject", "G3", "--reason", "thiếu kiểm mã trạng thái sau thao tác bus"]
    )
    assert ma != EXIT_OK
    ra = capsys.readouterr().out
    assert "bị Vũ Trí Công từ chối" in ra
    assert "Error Ledger" in ra

    from eaa.vcs import GitRepo

    repo = GitRepo(moi_truong / "firmware")
    assert repo.current_branch() == "feature/drv_bus_sensor"

    capsys.readouterr()
    main(["ledger", "list"])
    assert "thiếu kiểm mã trạng thái" in capsys.readouterr().out


def test_tu_choi_khong_co_ly_do_bi_chan(moi_truong: Path, capsys) -> None:
    _den_pha_D(capsys)
    main(["gen", "drv_bus_sensor"])
    capsys.readouterr()

    assert main(["gate", "reject", "G3", "--reason", "   "]) == EXIT_ENV_ERROR
    assert "bắt buộc kèm --reason" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Duyệt đúng thứ đã xem
# --------------------------------------------------------------------------


def test_duyet_voi_bam_lech_bi_tu_choi(moi_truong: Path, capsys) -> None:
    """`--expect` để kỹ sư ghim đúng bản mình đã đọc."""
    _den_pha_D(capsys)
    main(["gen", "drv_bus_sensor"])
    capsys.readouterr()

    ma = main(["gate", "approve", "G3", "--expect", "sha256:ban-toi-da-xem-hom-qua"])
    assert ma == EXIT_ENV_ERROR
    assert "đã thay đổi kể từ lúc bạn xem" in capsys.readouterr().err


def test_gate_show_liet_ke_trang_thai_khi_khong_co_ho_so(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    capsys.readouterr()
    assert main(["gate", "show"]) == EXIT_OK
    ra = capsys.readouterr().out
    for gate in ("G1", "G2", "G3", "G4", "G5"):
        assert gate in ra


# --------------------------------------------------------------------------
# UC08 — nhật ký lỗi
# --------------------------------------------------------------------------


def test_ledger_add_va_list(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    capsys.readouterr()

    ma = main(
        [
            "ledger", "add",
            "--module", "drv_bus_sensor",
            "--category", "hallucinated_register",
            "--description", "Mô hình dùng một thanh ghi không tồn tại",
            "--rule", "KHÔNG dùng REG_KHONG_CO",
        ]
    )
    assert ma == EXIT_OK
    assert "err-0001" in capsys.readouterr().out

    assert main(["ledger", "list"]) == EXIT_OK
    assert "KHÔNG dùng REG_KHONG_CO" in capsys.readouterr().out


def test_ledger_phan_loai_sai_bi_tu_choi(moi_truong: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    capsys.readouterr()
    ma = main(
        ["ledger", "add", "--module", "m", "--category", "tu_nghi_ra", "--description", "x"]
    )
    assert ma == EXIT_ENV_ERROR
    assert "Phân loại lỗi" in capsys.readouterr().err
