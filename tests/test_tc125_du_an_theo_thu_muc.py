"""TC-125 — thư mục đang đứng LÀ một cách chỉ định dự án.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-165.

Trước bản này, kho có nhiều dự án thì mọi lệnh đều phải nêu lại dự án bằng
``--project`` hoặc ``EAA_PROJECT`` — kể cả khi người dùng đang đứng ngay trong
thư mục dự án ấy. Đó là bắt khai một thứ hệ thống nhìn thấy được, và mỗi lần
khai lại là một lần khai nhầm được.

Bài này canh bốn điều, và điều thứ tư mới là điều dễ mất nhất về sau:

1. đứng trong dự án thì chọn đúng dự án ấy, dù kho có nhiều dự án;
2. đứng ở thư mục CON của dự án cũng vậy — người ta làm việc trong
   ``prompts/`` nhiều hơn ở gốc;
3. thứ được gõ ra thắng thứ được suy ra: ``--project`` > ``EAA_PROJECT`` > vị trí;
4. khi biến môi trường và vị trí chỉ về HAI dự án khác nhau, hệ thống phải NÓI
   RA. Im lặng ở đây là cách một buổi làm việc đi nhầm dự án mà không ai biết.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.cli import CliError, du_an_chua_thu_muc, resolve_project


def _du_an(goc: Path, ten: str) -> Path:
    """Một thư mục dự án tối thiểu — chỉ cần dấu hiệu, không cần nội dung."""
    d = goc / "projects" / ten
    (d / "prompts").mkdir(parents=True)
    (d / "constraints.yaml").write_text("mcu: x\n", encoding="utf-8")
    (d / "project_state.json").write_text("{}", encoding="utf-8")
    return d


@pytest.fixture
def kho_hai_du_an(tmp_path, monkeypatch):
    """Kho có HAI dự án: mọi phép chọn mơ hồ đều phải lộ ra ở đây."""
    monkeypatch.setenv("EAA_HOME", str(tmp_path))
    monkeypatch.delenv("EAA_PROJECT", raising=False)
    return tmp_path, _du_an(tmp_path, "bo_a"), _du_an(tmp_path, "bo_b")


# ══════════════════════ nhận ra dự án từ vị trí ══════════════════════


def test_dung_trong_du_an_thi_chon_dung_du_an_ay(kho_hai_du_an, monkeypatch):
    _, a, b = kho_hai_du_an
    monkeypatch.chdir(a)
    assert resolve_project(None) == a.resolve()

    monkeypatch.chdir(b)
    assert resolve_project(None) == b.resolve()


def test_dung_o_thu_muc_con_van_nhan_ra(kho_hai_du_an, monkeypatch):
    """Đi ngược lên như git tìm .git — không chỉ xét đúng thư mục hiện tại."""
    _, a, _ = kho_hai_du_an
    monkeypatch.chdir(a / "prompts")
    assert resolve_project(None) == a.resolve()


def test_chi_can_constraints_la_du(tmp_path, monkeypatch):
    """Quãng giữa `eaa brief` và `eaa init`: có ràng buộc, chưa có state."""
    monkeypatch.setenv("EAA_HOME", str(tmp_path))
    monkeypatch.delenv("EAA_PROJECT", raising=False)
    d = tmp_path / "projects" / "moi"
    d.mkdir(parents=True)
    (d / "constraints.yaml").write_text("mcu: x\n", encoding="utf-8")

    monkeypatch.chdir(d)
    assert du_an_chua_thu_muc() == d.resolve()


def test_ngoai_moi_du_an_thi_khong_nhan_bua(kho_hai_du_an, monkeypatch):
    """Gốc kho KHÔNG phải một dự án — nhận nhầm ở đây là nhận nhầm mọi lệnh."""
    goc, _, _ = kho_hai_du_an
    monkeypatch.chdir(goc)
    assert du_an_chua_thu_muc() is None

    with pytest.raises(CliError) as loi:
        resolve_project(None)
    assert "nhiều dự án" in str(loi.value)


def test_loi_nhieu_du_an_nhac_ca_cach_moi(kho_hai_du_an, monkeypatch):
    """Câu báo lỗi phải nêu đủ ba đường ra, không chỉ hai đường cũ."""
    goc, _, _ = kho_hai_du_an
    monkeypatch.chdir(goc)
    with pytest.raises(CliError) as loi:
        resolve_project(None)
    assert "cd vào thư mục dự án" in str(loi.value)


# ══════════════════════ thứ gõ ra thắng thứ suy ra ══════════════════════


def test_tham_so_thang_vi_tri(kho_hai_du_an, monkeypatch):
    _, a, b = kho_hai_du_an
    monkeypatch.chdir(a)
    assert resolve_project(str(b)) == b.resolve()


def test_bien_moi_truong_thang_vi_tri(kho_hai_du_an, monkeypatch):
    _, a, b = kho_hai_du_an
    monkeypatch.chdir(a)
    monkeypatch.setenv("EAA_PROJECT", str(b))
    assert resolve_project(None) == b.resolve()


def test_lech_giua_vi_tri_va_bien_moi_truong_phai_noi_ra(
    kho_hai_du_an, monkeypatch, capsys
):
    """Chọn đúng theo luật, nhưng KHÔNG được chọn im lặng."""
    _, a, b = kho_hai_du_an
    monkeypatch.chdir(a)
    monkeypatch.setenv("EAA_PROJECT", str(b))

    resolve_project(None)

    canh_bao = capsys.readouterr().err
    assert a.name in canh_bao and b.name in canh_bao
    assert "unset EAA_PROJECT" in canh_bao


def test_khong_canh_bao_khi_hai_ben_cung_tro_mot_cho(
    kho_hai_du_an, monkeypatch, capsys
):
    """Cảnh báo bắn cả lúc không có gì lệch là cảnh báo sẽ bị bỏ qua."""
    _, a, _ = kho_hai_du_an
    monkeypatch.chdir(a)
    monkeypatch.setenv("EAA_PROJECT", str(a))

    resolve_project(None)

    assert capsys.readouterr().err.strip() == ""
