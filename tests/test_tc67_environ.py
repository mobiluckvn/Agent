"""TC-67 — dò môi trường: máy này là máy gì, và hệ quả là gì.

Bài này canh hai thứ. Một: mọi phép đo tiêm được, nên các nhánh xấu (không có
trình cài gói, mất mạng, đĩa gần đầy) kiểm được mà không cần dựng máy thật.
Hai: bản báo cáo phải nói ra HỆ QUẢ, không chỉ nói ra số — một bảng thông số
mà người đọc phải tự suy ra "vậy là tôi không cài được gì" là bảng chưa xong.
"""

from __future__ import annotations

import os

import pytest

from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC
from eaa.environ import (
    HOST_KIEM_MANG,
    TRINH_QUAN_LY_GOI,
    EnvironmentReport,
    NetworkCheck,
    check_network,
    probe,
)
from eaa.web import NO_NET_ENV


def _khong_co_gi(ten):
    return None


def _co(*ds):
    return lambda ten: f"/usr/bin/{ten}" if ten in ds else None


def _noi_duoc(hp, t):
    return None


def _khong_noi_duoc(hp, t):
    raise OSError("Network is unreachable")


# ------------------------------------------------------------- phép đo cơ bản ---


def test_do_duoc_may_that_va_mang_nhan_da_kiem(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    bc = probe(connector=_noi_duoc)
    assert bc.os_name and bc.arch and bc.python_version
    assert bc.python_path == __import__("sys").executable
    assert bc.cpu_count > 0
    assert bc.confidence_level == DA_KIEM
    assert bc.network.confidence_level == DA_KIEM


def test_khoa_he_dieu_hanh_khop_voi_doctor():
    """Hai chỗ chọn lệnh cài mà lệch khóa OS thì một trong hai luôn chọn sai."""
    from eaa.doctor import _os_key

    assert probe(network=False).os_key == _os_key()


def test_liet_ke_dung_trinh_quan_ly_goi_co_mat():
    bc = probe(which=_co("brew", "pip3", "docker"), network=False)
    assert bc.package_managers == ("brew", "pip3", "docker")
    assert bc.has("brew") and not bc.has("apt-get")


def test_uu_tien_trinh_cho_he_dieu_hanh_hon_trinh_theo_ngon_ngu():
    bc = probe(which=_co("pip", "npm", "apt-get"), network=False)
    assert bc.preferred_manager() == "apt-get"


def test_khong_co_trinh_nao_thi_khong_chon_bua():
    bc = probe(which=_khong_co_gi, network=False)
    assert bc.package_managers == ()
    assert bc.preferred_manager() == ""


def test_thu_tu_uu_tien_phu_het_danh_sach():
    """Mọi tên trong danh sách phải chọn được, nếu không nó là dòng chết."""
    for ten in TRINH_QUAN_LY_GOI:
        assert probe(which=_co(ten), network=False).preferred_manager() == ten


# ------------------------------------------------------------------- mạng ---


def test_mang_thong_thi_bao_thong(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    kq = check_network(connector=_noi_duoc)
    assert kq.reachable is True and kq.skipped is False
    assert kq.host == f"{HOST_KIEM_MANG[0]}:{HOST_KIEM_MANG[1]}"


def test_mat_mang_thi_bao_mat_va_keu_ro_ly_do(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    kq = check_network(connector=_khong_noi_duoc)
    assert kq.reachable is False and kq.skipped is False
    assert "unreachable" in kq.detail


def test_cong_tac_ngat_thi_khong_thu_va_ha_muc_tin_cay(monkeypatch):
    monkeypatch.setenv(NO_NET_ENV, "1")

    def khong_duoc_goi(hp, t):
        raise AssertionError("đã tắt mạng mà vẫn thử nối")

    kq = check_network(connector=khong_duoc_goi)
    assert kq.skipped is True and kq.reachable is False
    assert kq.confidence_level == KHONG_KIEM_DUOC
    assert NO_NET_ENV in kq.detail


def test_bao_cao_bo_qua_mang_khi_duoc_yeu_cau():
    assert probe(network=False).network is None
    assert probe(network=False).online is False


# --------------------------------------------------------------- proxy ---


def test_bien_proxy_duoc_doc(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.noi-bo:3128")
    assert ("HTTPS_PROXY", "http://proxy.noi-bo:3128") in probe(network=False).proxy_vars


def test_mat_khau_trong_proxy_bi_che(monkeypatch):
    """http_proxy hay chứa user:mật_khẩu@host — in nguyên là rò rỉ (NFR-06)."""
    monkeypatch.setenv("HTTP_PROXY", "http://nguoi_dung:sieu_bi_mat@proxy:3128")
    gt = dict(probe(network=False).proxy_vars)["HTTP_PROXY"]
    assert "sieu_bi_mat" not in gt


# ------------------------------------------------------------------ hệ quả ---


def test_khong_co_trinh_cai_goi_thi_noi_ra_he_qua():
    ra = probe(which=_khong_co_gi, network=False).render()
    assert "KHÔNG CÓ CÁI NÀO" in ra
    assert "doctor --fix" in ra and "HỆ QUẢ" in ra


def test_mat_mang_thi_noi_ra_moi_tra_cuu_se_hong(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    ra = probe(which=_co("brew"), connector=_khong_noi_duoc).render()
    assert "Không ra được Internet" in ra
    assert "tra cứu" in ra


def test_dia_gan_day_thi_canh_bao():
    bc = EnvironmentReport(disk_free_bytes=500 * 1024**2, package_managers=("brew",))
    assert "hụt chỗ" in bc.render()


def test_may_binh_thuong_khong_canh_bao_gi(monkeypatch):
    monkeypatch.delenv(NO_NET_ENV, raising=False)
    bc = EnvironmentReport(
        os_name="Darwin", arch="arm64", cpu_count=8, ram_bytes=16 * 1024**3,
        disk_free_bytes=200 * 1024**3, package_managers=("brew",),
        network=NetworkCheck(reachable=True, detail="nối được", host="x:443"),
    )
    assert "HỆ QUẢ" not in bc.render()


# ------------------------------------------------------------------- khác ---


def test_bao_cao_di_qua_dict_khong_mat_gi():
    d = probe(which=_co("brew"), network=False).to_dict()
    assert d["package_managers"] == ["brew"]
    assert d["online"] is False
    assert d["probed_at"]


def test_quyen_quan_tri_khong_bao_bua_khi_khong_biet():
    """Đoán nhầm rằng mình có quyền dẫn tới lệnh cài chạy nửa chừng rồi hỏng."""
    assert isinstance(probe(network=False).is_admin, bool)
