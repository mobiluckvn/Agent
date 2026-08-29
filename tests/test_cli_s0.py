"""CLI Sprint 0 — FR-CLI-01, UC01, UC10, và mã thoát EAA-SDD-03 §6.

Định nghĩa hoàn thành của Sprint 0 (MDD §6): "``eaa init && eaa resume`` chạy
đúng". Bộ test này là bằng chứng cho câu đó, cộng thêm hai điều dễ trôi nếu
không có test canh:

* mã thoát phải đúng nghĩa — chờ gate là ``2``, lỗi môi trường là ``4``. Đây
  là giao diện mà script thực nghiệm A/B của Chương 3 sẽ dựa vào;
* lệnh chưa hiện thực phải NÓI RA rằng nó chưa hiện thực và thoát khác 0, chứ
  không im lặng trả về thành công.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_WAITING_GATE
from eaa.cli import constraints_version, main, resolve_project
from eaa.state import StateStore

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"


@pytest.fixture()
def du_an(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Bản sao dự án mẫu trong thư mục tạm — không đụng vào repo thật."""
    dich = tmp_path / "projects" / "robot_balance"
    dich.mkdir(parents=True)
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        (dich / ten).write_text((DU_AN_MAU / ten).read_text(encoding="utf-8"), encoding="utf-8")

    # packs/ dùng chung với repo thật: pack AVR là một phần của sản phẩm.
    monkeypatch.setenv("EAA_HOME", str(REPO))
    monkeypatch.setenv("EAA_PROJECT", str(dich))
    return dich


# --------------------------------------------------------------------------
# init + resume — định nghĩa hoàn thành Sprint 0
# --------------------------------------------------------------------------


def test_init_roi_resume_chay_dung(du_an: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init"]) == EXIT_OK

    state_path = du_an / "project_state.json"
    assert state_path.is_file()
    du_lieu = json.loads(state_path.read_text(encoding="utf-8"))
    assert du_lieu["phase"] == "A"
    assert du_lieu["gates"] == {g: "pending" for g in ("G1", "G2", "G3", "G4", "G5")}
    assert du_lieu["constraints_version"].startswith("sha256:")

    capsys.readouterr()
    # Dự án mới thì đang chờ G1 → mã thoát 2, không phải 0.
    assert main(["resume"]) == EXIT_WAITING_GATE
    ra = capsys.readouterr().out
    assert "Pha hiện tại : A" in ra
    assert "Đang chờ G1" in ra


def test_resume_khi_G1_da_duyet_thi_thoat_0(du_an: Path) -> None:
    assert main(["init"]) == EXIT_OK
    store = StateStore(du_an / "project_state.json")
    state = store.load()
    state.gates["G1"] = "approved"
    store.save(state)

    assert main(["resume"]) == EXIT_OK


def test_resume_khi_chua_init_bao_loi_moi_truong(du_an: Path) -> None:
    assert main(["resume"]) == EXIT_ENV_ERROR


def test_init_hai_lan_bi_chan_tru_khi_force(du_an: Path) -> None:
    assert main(["init"]) == EXIT_OK
    store = StateStore(du_an / "project_state.json")
    state = store.load()
    state.phase = "C"
    store.save(state)

    # Không có --force: từ chối, và quan trọng hơn — KHÔNG xóa mất tiến độ.
    assert main(["init"]) == EXIT_ENV_ERROR
    assert store.load().phase == "C"

    assert main(["init", "--force"]) == EXIT_OK
    assert store.load().phase == "A"


def test_init_thieu_constraints_bao_ro_thieu_gi(du_an: Path, capsys) -> None:
    (du_an / "constraints.yaml").unlink()
    assert main(["init"]) == EXIT_ENV_ERROR
    assert "constraints.yaml" in capsys.readouterr().err


def test_init_thieu_truong_platform_bi_tu_choi(du_an: Path, capsys) -> None:
    """Dự án phải chỉ rõ dùng Platform Pack nào — engine không tự đoán."""
    (du_an / "constraints.yaml").write_text("version: 1\nmcu: x\n", encoding="utf-8")
    assert main(["init"]) == EXIT_ENV_ERROR
    assert "platform" in capsys.readouterr().err


def test_init_tro_toi_pack_khong_ton_tai_bao_loi(du_an: Path, capsys) -> None:
    noi_dung = (du_an / "constraints.yaml").read_text(encoding="utf-8")
    (du_an / "constraints.yaml").write_text(
        noi_dung.replace("platform: avr", "platform: khong_co_that"), encoding="utf-8"
    )
    assert main(["init"]) == EXIT_ENV_ERROR
    assert "manifest" in capsys.readouterr().err.lower()


def test_state_hong_thi_bao_loi_chu_khong_tao_lai_am_tham(du_an: Path, capsys) -> None:
    assert main(["init"]) == EXIT_OK
    (du_an / "project_state.json").write_text("{hỏng", encoding="utf-8")

    assert main(["resume"]) == EXIT_ENV_ERROR
    assert "khôi phục từ Git" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Truy vết ràng buộc
# --------------------------------------------------------------------------


def test_constraints_version_doi_khi_noi_dung_doi(du_an: Path) -> None:
    path = du_an / "constraints.yaml"
    truoc = constraints_version(path)
    path.write_text(path.read_text(encoding="utf-8") + "\n# thêm một dòng\n", encoding="utf-8")
    assert constraints_version(path) != truoc, (
        "Băm phải đổi kể cả khi chỉ thêm chú thích: câu hỏi cần trả lời là "
        "'mã sinh ra dưới đúng văn bản ràng buộc nào'."
    )


def test_init_ghi_dung_bam_rang_buoc_vao_state(du_an: Path) -> None:
    assert main(["init"]) == EXIT_OK
    state = StateStore(du_an / "project_state.json").load()
    assert state.constraints_version == constraints_version(du_an / "constraints.yaml")


# --------------------------------------------------------------------------
# Lệnh chưa hiện thực phải trung thực
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lenh",
    ["plan", "datasheet", "gen", "gate", "sim", "tune", "ledger", "report", "doctor", "docs", "rollback"],
)
def test_lenh_chua_lam_noi_ro_va_thoat_khac_0(
    lenh: str, du_an: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ma = main([lenh])
    assert ma != EXIT_OK, f"'{lenh}' chưa làm mà lại báo thành công"
    err = capsys.readouterr().err
    assert "chưa được hiện thực hóa" in err
    assert "Sprint" in err


def test_lenh_gate_noi_ro_khong_co_co_tu_duyet(du_an: Path, capsys) -> None:
    """ADR-04: gate cưỡng chế bằng phần mềm — kể cả phần trợ giúp cũng phải
    nói đúng điều đó, để không ai đi tìm một cờ như thế."""
    main(["gate"])
    assert "chỉ được duyệt bởi con người" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Các lệnh chỉ đọc
# --------------------------------------------------------------------------


def test_policy_in_du_13_cong_doan_va_5_gate(du_an: Path, capsys) -> None:
    assert main(["policy"]) == EXIT_OK
    ra = capsys.readouterr().out
    for ma in ("A1", "B2", "C1", "D4", "E2", "F1"):
        assert ma in ra
    for gate in ("G1", "G2", "G3", "G4", "G5"):
        assert gate in ra


def test_packs_liet_ke_pack_avr_va_danh_dau_can_xac_nhan(du_an: Path, capsys) -> None:
    assert main(["packs"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "avr" in ra
    assert "cần người xác nhận" in ra, "năng lực nạp firmware phải hiện rõ là cần xác nhận"


def test_status_la_bi_danh_chi_doc_cua_resume(du_an: Path, capsys) -> None:
    main(["init"])
    capsys.readouterr()
    assert main(["status"]) == EXIT_WAITING_GATE
    assert "Pha hiện tại" in capsys.readouterr().out


def test_khong_co_lenh_thi_in_tro_giup(capsys) -> None:
    assert main([]) == EXIT_OK
    assert "Human Gate" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Định vị dự án
# --------------------------------------------------------------------------


def test_resolve_project_uu_tien_tham_so_hon_bien_moi_truong(
    du_an: Path, tmp_path: Path
) -> None:
    khac = tmp_path / "khac"
    khac.mkdir()
    assert resolve_project(str(khac)) == khac.resolve()
    assert resolve_project(None) == du_an


def test_resolve_project_bao_loi_khi_khong_co_du_an(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EAA_HOME", str(tmp_path))
    monkeypatch.delenv("EAA_PROJECT", raising=False)
    from eaa.cli import CliError

    with pytest.raises(CliError, match="Không tìm thấy dự án"):
        resolve_project(None)


def test_resolve_project_bao_loi_khi_co_nhieu_du_an(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for ten in ("mot", "hai"):
        d = tmp_path / "projects" / ten
        d.mkdir(parents=True)
        (d / "constraints.yaml").write_text("platform: avr\n", encoding="utf-8")
    monkeypatch.setenv("EAA_HOME", str(tmp_path))
    monkeypatch.delenv("EAA_PROJECT", raising=False)
    from eaa.cli import CliError

    with pytest.raises(CliError, match="nhiều dự án"):
        resolve_project(None)
