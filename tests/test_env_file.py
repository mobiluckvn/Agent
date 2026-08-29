"""Nạp cấu hình từ ``.env`` — tiện cho người dùng, không nới lỏng NFR-06.

NFR-06 chốt: khóa API lưu qua biến môi trường, không ghi key ra log. Tệp
``.env`` không phá quy tắc đó — nó chỉ là chỗ nạp vào môi trường lúc khởi
động, và adapter mô hình vẫn chỉ đọc ``os.environ``.

Điều bộ test này canh là ba chỗ dễ hỏng nhất của một cơ chế như vậy: tệp lọt
vào Git, giá trị trong tệp đè mất biến người vừa gõ, và nội dung tệp bị in ra.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from eaa.cli import ENV_FILE, load_env_file

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Điều quan trọng nhất: tệp không bao giờ vào Git
# --------------------------------------------------------------------------


def test_env_bi_git_bo_qua() -> None:
    """Một khóa đã commit là một khóa phải thu hồi — không sửa được bằng git rm."""
    ket_qua = subprocess.run(
        ["git", "check-ignore", ENV_FILE],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert ket_qua.returncode == 0, (
        f"{ENV_FILE} KHÔNG nằm trong .gitignore. Thêm ngay trước khi ai đó điền "
        "khóa thật vào."
    )


def test_env_khong_nam_trong_danh_muc_theo_doi_cua_git() -> None:
    ket_qua = subprocess.run(
        ["git", "ls-files", ENV_FILE], cwd=str(REPO), capture_output=True, text=True
    )
    assert not ket_qua.stdout.strip(), f"{ENV_FILE} đang được Git theo dõi"


def test_co_ban_mau_de_nguoi_dung_chep_ra() -> None:
    mau = REPO / ".env.example"
    assert mau.is_file(), "thiếu .env.example"
    noi_dung = mau.read_text(encoding="utf-8")
    assert "EAA_LLM_KEY=" in noi_dung
    # Bản mẫu ĐƯỢC commit nên tuyệt đối không chứa giá trị thật.
    assert "EAA_LLM_KEY=\n" in noi_dung or "EAA_LLM_KEY=$" in noi_dung + "$"


def test_ban_mau_khong_chua_gia_tri_that() -> None:
    noi_dung = (REPO / ".env.example").read_text(encoding="utf-8")
    for dong in noi_dung.splitlines():
        if dong.strip().startswith("EAA_LLM_KEY="):
            assert dong.split("=", 1)[1].strip() == "", "bản mẫu có khóa thật"


# --------------------------------------------------------------------------
# Hành vi nạp
# --------------------------------------------------------------------------


@pytest.fixture()
def sach(monkeypatch: pytest.MonkeyPatch):
    for ten in ("EAA_LLM_KEY", "EAA_ACTOR", "BIEN_THU_NGHIEM"):
        monkeypatch.delenv(ten, raising=False)


def test_nap_bien_tu_tep(tmp_path: Path, sach) -> None:
    (tmp_path / ".env").write_text(
        "# chú thích\n\nEAA_LLM_KEY=khoa-tu-tep\nBIEN_THU_NGHIEM=xin-chao\n",
        encoding="utf-8",
    )
    da_nap = load_env_file(tmp_path)

    assert set(da_nap) == {"EAA_LLM_KEY", "BIEN_THU_NGHIEM"}
    assert os.environ["EAA_LLM_KEY"] == "khoa-tu-tep"


def test_bien_da_dat_trong_shell_luon_THANG(tmp_path: Path, monkeypatch) -> None:
    """Người gõ EAA_LLM_KEY=... eaa gen phải nhận đúng khóa vừa gõ."""
    monkeypatch.setenv("EAA_LLM_KEY", "khoa-nguoi-vua-go")
    (tmp_path / ".env").write_text("EAA_LLM_KEY=khoa-cu-trong-tep\n", encoding="utf-8")

    da_nap = load_env_file(tmp_path)

    assert "EAA_LLM_KEY" not in da_nap
    assert os.environ["EAA_LLM_KEY"] == "khoa-nguoi-vua-go"


def test_tra_ve_TEN_bien_khong_tra_gia_tri(tmp_path: Path, sach) -> None:
    """Danh sách trả về có thể đi vào log, nên nó không được mang giá trị."""
    (tmp_path / ".env").write_text("EAA_LLM_KEY=bi-mat-tuyet-doi\n", encoding="utf-8")
    da_nap = load_env_file(tmp_path)
    assert da_nap == ["EAA_LLM_KEY"]
    assert "bi-mat-tuyet-doi" not in " ".join(da_nap)


def test_bo_qua_dong_rong_chu_thich_va_gia_tri_rong(tmp_path: Path, sach) -> None:
    (tmp_path / ".env").write_text(
        "\n# EAA_LLM_KEY=day-la-chu-thich\nEAA_LLM_KEY=\nkhong-co-dau-bang\n",
        encoding="utf-8",
    )
    assert load_env_file(tmp_path) == []
    assert "EAA_LLM_KEY" not in os.environ


def test_go_dau_nhay_quanh_gia_tri(tmp_path: Path, sach) -> None:
    (tmp_path / ".env").write_text('EAA_ACTOR="Vũ Trí Công"\n', encoding="utf-8")
    load_env_file(tmp_path)
    assert os.environ["EAA_ACTOR"] == "Vũ Trí Công"


def test_khong_co_tep_thi_khong_no(tmp_path: Path) -> None:
    assert load_env_file(tmp_path) == []


def test_cli_nap_env_khi_khoi_dong(tmp_path: Path, monkeypatch, capsys) -> None:
    from eaa.cli import main

    monkeypatch.setenv("EAA_HOME", str(tmp_path))
    monkeypatch.delenv("EAA_ACTOR", raising=False)
    (tmp_path / ".env").write_text("EAA_ACTOR=nguoi-tu-env\n", encoding="utf-8")

    main(["policy"])
    assert os.environ["EAA_ACTOR"] == "nguoi-tu-env"
