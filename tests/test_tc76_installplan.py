"""TC-76 — cài theo thứ tự nào, bằng cách nào, và chỗ nào đá nhau.

Ba câu hỏi chỉ trả lời được khi nhìn TOÀN BỘ manifest cùng lúc. Một Tool Card
đọc riêng thì không biết mình đứng sau ai và không biết mình đá nhau với ai —
đặt phép kiểm ở tầng từng thẻ là đặt nó ở chỗ không có đủ thông tin.

Bài này cũng canh một kỷ luật về sự im lặng: phụ thuộc trỏ ra NGOÀI manifest
không xếp thứ tự được, nhưng bỏ im lặng thì tệ hơn — nó vẫn là thứ phải có
trước, và người dùng không có cách nào biết.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from eaa.confidence import SUY_RA
from eaa.installplan import (
    CONTAINER,
    GOI,
    NGUON,
    NHI_PHAN,
    VENV,
    CircularDependency,
    find_conflicts,
    plan_installs,
)


@dataclass
class _The:
    name: str
    requires: dict = field(default_factory=dict)
    method: str = GOI
    install: dict = field(default_factory=dict)
    checksum: str = ""


def _ten(ke_hoach):
    return [b.name for b in ke_hoach.steps]


# ═══════════════════════════════ thứ tự ═══════════════════════════════


def test_phu_thuoc_duoc_cai_truoc():
    kh = plan_installs([_The("b", {"a": ""}), _The("a")])
    assert _ten(kh) == ["a", "b"]
    assert kh.steps[1].after == ("a",)


def test_chuoi_phu_thuoc_dai():
    kh = plan_installs([_The("c", {"b": ""}), _The("b", {"a": ""}), _The("a")])
    assert _ten(kh) == ["a", "b", "c"]


def test_thu_tu_ON_DINH_giua_hai_lan_chay():
    """Hai lần chạy doctor in ra hai danh sách khác nhau là không ai hiểu vì sao."""
    the = [_The("z"), _The("y"), _The("x")]
    assert _ten(plan_installs(the)) == _ten(plan_installs(list(reversed(the))))


def test_phu_thuoc_vong_bi_bat_va_neu_ten_ca_vong():
    with pytest.raises(CircularDependency) as loi:
        plan_installs([_The("a", {"b": ""}), _The("b", {"a": ""})])
    assert "a" in str(loi.value) and "b" in str(loi.value)
    assert "máy không tự chọn hộ được" in str(loi.value)


def test_tu_phu_thuoc_khong_lam_treo():
    kh = plan_installs([_The("a", {"a": ""})])
    assert _ten(kh) == ["a"]


def test_phu_thuoc_ngoai_manifest_duoc_NEU_RA_chu_khong_nuot():
    kh = plan_installs([_The("avrdude", {"libusb": ">=1.0"})])
    assert kh.steps[0].after == ()          # không xếp thứ tự theo thứ không có
    assert "libusb >=1.0" in kh.steps[0].note
    assert "kiểm bằng tay" in kh.steps[0].note


def test_da_co_thi_danh_dau_bo_qua():
    kh = plan_installs([_The("a"), _The("b")], present=["a"])
    assert kh.steps[0].present is True
    assert [b.name for b in kh.todo] == ["b"]
    assert "✓ đã có, bỏ qua" in kh.steps[0].render(1)


def test_khong_thieu_gi_thi_noi_ro():
    kh = plan_installs([_The("a")], present=["a"])
    assert "Không thiếu công cụ nào" in kh.render()


# ═══════════════════════════════ cách cài ═══════════════════════════════


def test_lenh_cai_lay_theo_he_dieu_hanh():
    the = _The("x", install={"macos": ("brew", "install", "x"),
                             "linux": ("apt-get", "install", "x")})
    assert plan_installs([the], os_key="macos").steps[0].command == ("brew", "install", "x")
    assert plan_installs([the], os_key="linux").steps[0].command[0] == "apt-get"


def test_he_dieu_hanh_chua_khai_thi_noi_ro():
    kh = plan_installs([_The("x", install={"linux": ("a",)})], os_key="macos")
    assert kh.steps[0].command == ()
    assert "chưa khai lệnh cài" in kh.steps[0].render(1)


def test_tai_nhi_phan_ma_thieu_checksum_thi_canh_bao():
    kh = plan_installs([_The("x", method=NHI_PHAN)])
    assert "checksum" in kh.steps[0].note


def test_tai_nhi_phan_co_checksum_thi_khong_canh_bao():
    # Kiểm dấu CẢNH BÁO, không kiểm từ "checksum": từ ấy cũng nằm trong lời
    # giải thích chung về cách cải nhị phân, nên kiểm theo từ là kiểm nhầm thứ.
    kh = plan_installs([_The("x", method=NHI_PHAN, checksum="sha256:ff")])
    assert "⚠" not in kh.steps[0].note


@pytest.mark.parametrize("cach", [NGUON, CONTAINER, VENV])
def test_cach_cai_khac_mac_dinh_duoc_giai_thich(cach):
    kh = plan_installs([_The("x", method=cach)])
    assert kh.steps[0].note
    assert cach in kh.steps[0].render(1)


def test_cach_mac_dinh_KHONG_giai_thich_lai():
    """Nhắc 'đây là trình quản lý gói' ở từng dòng làm thứ đáng chú ý chìm đi."""
    kh = plan_installs([_The("x", method=GOI)])
    assert kh.steps[0].note == ""


# ═══════════════════════════════ xung đột ═══════════════════════════════


@pytest.mark.parametrize("r1,r2", [
    (">=3.0", "<2.0"),
    ("<1.5", ">=2.0"),
    ("==1.0", "==2.0"),
    ("==1.0", ">=2.0"),
])
def test_rang_buoc_loai_tru_nhau_bi_bat(r1, r2):
    xd = find_conflicts([_The("a", {"lib": r1}), _The("b", {"lib": r2})])
    assert len(xd) == 1
    assert xd[0].subject == "lib"


@pytest.mark.parametrize("r1,r2", [
    (">=1.0", ">=2.0"),      # chồng nhau được
    (">=1.0", "<=3.0"),
    ("==1.0", "==1.0"),
    (">=1.0", ""),           # một bên không nêu
    ("", ""),
    ("bat-ky", "linh-tinh"), # không đọc được số
])
def test_rang_buoc_CHUA_CHAC_da_thi_khong_bao(r1, r2):
    """Một cảnh báo sai làm người dùng bỏ qua cả những cảnh báo đúng."""
    assert find_conflicts([_The("a", {"lib": r1}), _The("b", {"lib": r2})]) == []


def test_hai_the_doi_hai_thu_khac_nhau_thi_khong_phai_xung_dot():
    assert find_conflicts([_The("a", {"x": ">=3"}), _The("b", {"y": "<1"})]) == []


def test_xung_dot_chan_ca_ke_hoach_va_noi_ro_he_qua():
    kh = plan_installs([_The("a", {"lib": ">=3.0"}), _The("b", {"lib": "<2.0"})])
    assert kh.blocked is True
    ra = kh.render()
    assert "DỪNG" in ra
    assert "cái sau làm hỏng cái trước" in ra


def test_khong_xung_dot_thi_khong_chan():
    assert plan_installs([_The("a"), _The("b")]).blocked is False


# ═══════════════════════════════ bản in ═══════════════════════════════


def test_ke_hoach_luon_la_SUY_RA():
    """Thứ tự suy từ khai báo, chưa lần cài nào chạy để xác nhận."""
    assert plan_installs([_The("a")]).confidence_level == SUY_RA


def test_ban_in_nhac_lai_rang_may_KHONG_cai():
    ra = plan_installs([_The("a", install={"macos": ("brew", "install", "a")})],
                       os_key="macos").render()
    assert "Tôi KHÔNG chạy những lệnh này" in ra
    assert "eaa doctor --fix" in ra


def test_the_cong_cu_doc_duoc_requires_va_method_tu_yaml(tmp_path):
    from eaa.doctor import ToolManifest

    (tmp_path / "tools.yaml").write_text(
        "scope: engine\ntools:\n"
        "- name: avrdude\n  check: [avrdude, -v]\n  method: nhị phân\n"
        "  checksum: 'sha256:ff'\n  requires: {libusb: '>=1.0'}\n"
        "  alternatives: [dfu-programmer]\n",
        encoding="utf-8",
    )
    m = ToolManifest.load(tmp_path / "tools.yaml")
    s = m.specs[0]
    assert s.method == "nhị phân"
    assert s.requires == {"libusb": ">=1.0"}
    assert s.alternatives == ("dfu-programmer",)


def test_manifest_that_cua_pack_xep_dung_thu_tu():
    """avr-objcopy và avr-size khai phụ thuộc avr-gcc — phải đứng sau nó."""
    from pathlib import Path

    from eaa.doctor import ToolManifest

    goc = Path(__file__).resolve().parent.parent
    m = ToolManifest.load(goc / "tools.yaml", goc / "packs" / "avr" / "tools.yaml",
                          pack="avr")
    ten = _ten(plan_installs(m.specs, os_key="macos"))
    assert ten.index("avr-gcc") < ten.index("avr-objcopy")
    assert ten.index("avr-gcc") < ten.index("avr-size")
