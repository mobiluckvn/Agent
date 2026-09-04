"""TC-129 — cài trượt thì nói VÌ SAO và LÀM GÌ TIẾP (C5.1–C5.3, C5.5, C5.6, C5.9, C5.10).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-169.

`eaa/installerr.py` có đủ sáu loại lỗi, thang gỡ đủ bậc, lệnh quay lui suy từ
lệnh cài, và TC-69 canh thứ tự các bậc ấy. **Không module nào trong `eaa/` gọi
tới nó.** `doctor._run_install` khi trượt thì thử lại mù hai lần rồi in đúng một
câu cho mọi kiểu hỏng: *"cài thất bại sau 2 lần — cài tay theo hướng dẫn của nhà
phát hành"*.

Bảy dòng của bảng năng lực đứng trên module ấy, cả bảy đều khai ĐỦ, và cả bảy
đều đúng theo nghĩa "có mã, có test". Chỉ thiếu một thứ: đường gọi.

Hai chuyện bài này canh
------------------------

1. **Thử lại là quyền của ĐÚNG MỘT loại lỗi.** Thử lại một lỗi quyền, hay một
   lỗi sai tên gói, là đốt thời gian và làm nhật ký dài gấp đôi mà không thêm
   một tin nào.
2. **Quay lui được NÊU RA chứ không CHẠY.** Cài dở dang là máy đã đổi; gỡ cũng
   là một lần đổi nữa, và nó phải qua đúng cái cửa mà lệnh cài vừa đi qua.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from eaa.doctor import Doctor, EnvLock, ToolManifest, ToolSpec
from eaa.installerr import SO_LAN_THU_LAI, retry_delays


@dataclass
class KetQuaGia:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class ChayGia:
    """Thay `subprocess.run`, đếm số lần chạy và trả kết quả đã dựng sẵn."""

    def __init__(self, *ket_qua: Any) -> None:
        self.ket_qua = list(ket_qua)
        self.lenh_da_chay: list[list[str]] = []

    def __call__(self, argv: Any, **_: Any) -> Any:
        self.lenh_da_chay.append(list(argv))
        kq = self.ket_qua[min(len(self.lenh_da_chay) - 1, len(self.ket_qua) - 1)]
        if isinstance(kq, Exception):
            raise kq
        return kq


@pytest.fixture()
def bac_si(tmp_path: Path) -> tuple[Doctor, list[float]]:
    da_ngu: list[float] = []
    d = Doctor(
        manifest=ToolManifest(specs=()),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
        sleep=da_ngu.append,
    )
    return d, da_ngu


SPEC = ToolSpec(name="cong-cu-x", check=("cong-cu-x", "--version"))
LENH = (("sudo", "apt-get", "install", "-y", "cong-cu-x"),)

LOI_MANG = "Could not resolve host: deb.debian.org\nTemporary failure in name resolution"
LOI_QUYEN = "E: Could not open lock file /var/lib/dpkg/lock - open (13: Permission denied)"
LOI_KHONG_CO_GOI = "E: Unable to locate package cong-cu-x"


# -- thử lại là quyền của đúng một loại lỗi ----------------------------------


def test_loi_MANG_duoc_thu_lai_du_so_lan_va_gian_dan(bac_si, monkeypatch) -> None:
    d, da_ngu = bac_si
    chay = ChayGia(KetQuaGia(1, stderr=LOI_MANG))
    monkeypatch.setattr(subprocess, "run", chay)

    nhat_ky = d._run_install(SPEC, LENH)

    assert len(chay.lenh_da_chay) == SO_LAN_THU_LAI + 1, "một lần đầu cộng ba lần thử lại"
    assert da_ngu == retry_delays(), "giãn cách phải tăng gấp đôi, không phải thử liền tay"
    assert any("lỗi MẠNG" in d_ for d_ in nhat_ky)


def test_loi_QUYEN_KHONG_duoc_thu_lai(bac_si, monkeypatch) -> None:
    """Thử lại một lỗi quyền mãi cũng ra đúng kết quả ấy."""
    d, da_ngu = bac_si
    chay = ChayGia(KetQuaGia(100, stderr=LOI_QUYEN))
    monkeypatch.setattr(subprocess, "run", chay)

    nhat_ky = d._run_install(SPEC, LENH)

    assert len(chay.lenh_da_chay) == 1
    assert da_ngu == [], "không được nghỉ giữa hai lần thử khi không có lần thử thứ hai"
    assert any("QUYỀN" in d_ and "KHÔNG thử lại" in d_ for d_ in nhat_ky)


def test_loi_SAI_TEN_GOI_KHONG_duoc_thu_lai(bac_si, monkeypatch) -> None:
    d, _ = bac_si
    chay = ChayGia(KetQuaGia(100, stderr=LOI_KHONG_CO_GOI))
    monkeypatch.setattr(subprocess, "run", chay)

    d._run_install(SPEC, LENH)
    assert len(chay.lenh_da_chay) == 1


def test_thanh_cong_o_lan_thu_lai_thi_dung_ngay(bac_si, monkeypatch) -> None:
    d, da_ngu = bac_si
    chay = ChayGia(KetQuaGia(1, stderr=LOI_MANG), KetQuaGia(0))
    monkeypatch.setattr(subprocess, "run", chay)
    monkeypatch.setattr(d, "_check_one", lambda spec: _bao_cao_ok(spec))

    nhat_ky = d._run_install(SPEC, LENH)

    assert len(chay.lenh_da_chay) == 2
    assert len(da_ngu) == 1
    assert any("cài xong" in d_ for d_ in nhat_ky)


def test_ngoai_le_cua_lenh_cung_di_qua_phan_loai(bac_si, monkeypatch) -> None:
    """Timeout là một dạng hỏng, và nó cũng phải được xếp loại như mọi dạng khác."""
    d, _ = bac_si
    chay = ChayGia(subprocess.TimeoutExpired(cmd="apt-get", timeout=900))
    monkeypatch.setattr(subprocess, "run", chay)

    nhat_ky = d._run_install(SPEC, LENH)
    assert any("loại lỗi" in d_ for d_ in nhat_ky)


# -- nhật ký nói được việc phải làm ------------------------------------------


def test_nhat_ky_mang_THANG_GO_chu_khong_mang_mot_cau_chung_chung(
    bac_si, monkeypatch
) -> None:
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(100, stderr=LOI_KHONG_CO_GOI)))

    van_ban = "\n".join(d._run_install(SPEC, LENH))

    assert "Thang gỡ" in van_ban
    assert "KHÔNG TÌM THẤY" in van_ban
    # Câu cũ dùng cho mọi kiểu hỏng phải biến mất — nó là thứ dòng này thay thế.
    assert "cài thất bại sau 2 lần" not in van_ban


def test_nhat_ky_neu_dau_hieu_da_nhan_ra_va_muc_tin_cay(bac_si, monkeypatch) -> None:
    """Phân loại là SO MẪU trên chuỗi lỗi, không phải một phép đo — phải nói ra."""
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(1, stderr=LOI_MANG)))

    van_ban = "\n".join(d._run_install(SPEC, LENH))
    assert "dấu hiệu nhận ra" in van_ban
    assert "SUY RA" in van_ban


def test_loi_KHONG_NHAN_RA_khong_bi_khai_thanh_da_biet(bac_si, monkeypatch) -> None:
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(1, stderr="một thứ lạ hoắc")))

    van_ban = "\n".join(d._run_install(SPEC, LENH))
    assert "KHÁC" in van_ban
    assert "KHÔNG KIỂM ĐƯỢC" in van_ban


# -- quay lui: nêu ra, không chạy --------------------------------------------


def test_lenh_quay_lui_duoc_NEU_RA(bac_si, monkeypatch) -> None:
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(100, stderr=LOI_QUYEN)))

    van_ban = "\n".join(d._run_install(SPEC, LENH))
    assert "quay lui" in van_ban
    assert "sudo apt-get remove -y cong-cu-x" in van_ban


def test_lenh_quay_lui_KHONG_duoc_CHAY(bac_si, monkeypatch) -> None:
    """Gỡ cũng là một lần đổi máy — nó phải qua đúng cái cửa lệnh cài đã đi qua."""
    d, _ = bac_si
    chay = ChayGia(KetQuaGia(100, stderr=LOI_QUYEN))
    monkeypatch.setattr(subprocess, "run", chay)

    d._run_install(SPEC, LENH)

    assert all("remove" not in " ".join(l) for l in chay.lenh_da_chay)
    assert len(chay.lenh_da_chay) == 1


def test_nhieu_buoc_thi_quay_lui_neu_du_buoc_da_chay(bac_si, monkeypatch) -> None:
    """Bước 2 trượt thì bước 1 đã đổi máy rồi — bỏ nó khỏi lệnh lui là bỏ sót."""
    d, _ = bac_si
    day = (
        ("sudo", "apt-get", "install", "-y", "goi-nen"),
        ("sudo", "apt-get", "install", "-y", "cong-cu-x"),
    )
    monkeypatch.setattr(
        subprocess, "run", ChayGia(KetQuaGia(0), KetQuaGia(100, stderr=LOI_QUYEN))
    )

    van_ban = "\n".join(d._run_install(SPEC, day))
    assert "goi-nen" in van_ban and "cong-cu-x" in van_ban


def test_khong_suy_duoc_lenh_lui_thi_im_chu_khong_doan(bac_si, monkeypatch) -> None:
    """Một lệnh gỡ đoán sai chạy với quyền quản trị tệ hơn hẳn không có lệnh gỡ."""
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(100, stderr=LOI_QUYEN)))

    van_ban = "\n".join(d._run_install(SPEC, (("./cai-dat.sh", "--yes"),)))
    assert "quay lui" not in van_ban


# -- ba chỗ cắt đầu ra phải cùng một chiều ------------------------------------
#
# Đầu ra của trình quản lý gói mở màn bằng hàng chục dòng tải về rồi mới tới câu
# nói thật. `doctor.SO_DONG_LOI` đã ghi đúng lý lẽ ấy và giữ phần CUỐI; hai chỗ
# còn lại trong `installerr` giữ phần ĐẦU. Mâu thuẫn ấy nằm im cho tới khi
# SL-169 nối chúng vào cùng một đường.


DAI = "\n".join(f"dòng {i}" for i in range(200))


def test_phan_may_noi_giu_duoi_chu_khong_giu_dau(bac_si, monkeypatch) -> None:
    d, _ = bac_si
    monkeypatch.setattr(subprocess, "run", ChayGia(KetQuaGia(1, stderr=DAI)))

    van_ban = "\n".join(d._run_install(SPEC, LENH))
    assert "dòng 199" in van_ban
    assert "dòng 0\n" not in van_ban and "dòng 0 " not in van_ban


def test_bac_tra_loi_dem_DONG_CUOI_di_hoi_khong_dem_dong_dau() -> None:
    """Đem dòng đầu đi tra là đem một dòng tiến trình đi hỏi Internet."""
    from eaa.installerr import KHAC, remedies

    thang = remedies(KHAC, tool="cong-cu-x", output=DAI)
    lenh = [r.command for r in thang if r.command and "research" in r.command]
    assert lenh, "thang gỡ của loại KHÁC phải có bậc tra thông báo lỗi"
    assert lenh[0][-1] == "dòng 199"


def test_dau_ra_rong_thi_tra_theo_TEN_CONG_CU() -> None:
    from eaa.installerr import KHAC, remedies

    thang = remedies(KHAC, tool="cong-cu-x", output="   \n\n  ")
    lenh = [r.command for r in thang if r.command and "research" in r.command]
    assert lenh[0][-1] == "cong-cu-x"


def test_khong_doc_duoc_dau_ra_thi_noi_thang_la_khong_phan_loai_duoc(bac_si) -> None:
    d, _ = bac_si
    dong = d._chan_doan_cai_hong(SPEC, None, LENH)
    assert len(dong) == 1
    assert "không đọc được đầu ra để phân loại" in dong[0]


def _bao_cao_ok(spec: ToolSpec) -> Any:
    from eaa.doctor import ToolReport, ToolStatus

    return ToolReport(spec=spec, status=ToolStatus.OK, version="1.0", detail="")
