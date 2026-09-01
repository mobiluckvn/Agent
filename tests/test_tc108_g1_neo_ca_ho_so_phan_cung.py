"""TC-108 — quyết định G1 phải neo vào CẢ hồ sơ phần cứng.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-139.

Tìm ra khi sửa hồ sơ phần cứng để thêm còi và nút nhấn cho giao thức khởi
động: đổi bảng chân của bốn chân động cơ, thêm hai linh kiện, thêm một bộ đếm
— rồi chạy `eaa status`::

    ✓ G1 approved  chốt ràng buộc cứng & kiến trúc

Không cảnh báo, không đòi duyệt lại, không gì cả.

Thiết kế nói ngược lại, bằng chữ
---------------------------------

`hardware_profile.yaml` mở đầu bằng đúng câu này:

    Sửa tệp này kích hoạt phân tích ảnh hưởng và phải duyệt lại tại G1
    (AIS §8.1) — đổi một chân là đổi mọi module chạm vào chân đó.

Không cơ chế nào thi hành câu ấy:

* hồ sơ G1 in ``hardware_profile.yaml v{version}`` — **số phiên bản khai
  trong tệp**, không phải băm nội dung. Sửa nội dung mà không sửa số ấy thì
  dòng này giống hệt nhau từng ký tự;
* ``content_digest`` của G1 chỉ là băm `constraints.yaml`, nên quyết định của
  người **không neo vào** thứ họ vừa đọc ở dòng trên;
* phép kiểm trôi băm ở `eaa status` cũng chỉ soi `constraints.yaml`.

Và băm ấy vẫn được tính
------------------------

``HardwareProfile.content_version`` có sẵn, đúng tên, đúng cách tính — nó được
dùng ở một chỗ khác trong `cli.py` để ghi phẩm xuất. Chỉ là cổng không hỏi tới.
Lần thứ **bảy** của dạng "mã đúng nằm chết".

Vì sao chỗ này đắt hơn vẻ ngoài
--------------------------------

G1 tên là *chốt ràng buộc cứng và kiến trúc*. Bảng chân LÀ kiến trúc: đổi một
chân là đổi mọi module chạm vào chân đó, và mã sinh sau đó sẽ ghi mức logic
vào chân mới mà không ai từng duyệt việc ấy. Một cổng neo vào nửa hồ sơ là một
cổng cho qua nửa còn lại.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_ho_so_G1_neo_vao_CA_HAI_tep(tmp_path: Path) -> None:
    """Băm quyết định phải đổi khi hồ sơ phần cứng đổi."""
    from eaa.cli import dau_van_tay_G1

    a = dau_van_tay_G1("bam-rang-buoc", "bam-phan-cung")
    b = dau_van_tay_G1("bam-rang-buoc", "bam-phan-cung-KHAC")

    assert a and b
    assert a != b, (
        "đổi hồ sơ phần cứng mà băm quyết định G1 không đổi — người duyệt một "
        "thứ, hệ ghi lại một thứ khác"
    )


def test_doi_rang_buoc_cung_lam_doi_bam() -> None:
    from eaa.cli import dau_van_tay_G1

    assert dau_van_tay_G1("x", "p") != dau_van_tay_G1("y", "p")


def test_thieu_ho_so_phan_cung_van_ra_bam() -> None:
    """Dự án chưa có hồ sơ phần cứng thì G1 vẫn phải chốt được ràng buộc."""
    from eaa.cli import dau_van_tay_G1

    assert dau_van_tay_G1("x", "").strip()


def test_status_BAO_TROI_khi_ho_so_phan_cung_doi(tmp_path: Path) -> None:
    """Im lặng ở đây nghĩa là người không bao giờ biết cần duyệt lại."""
    from eaa.cli import _troi_rang_buoc
    from eaa.state import ProjectState

    (tmp_path / "constraints.yaml").write_text(
        "version: 1\nplatform: avr\nmcu: atmega328p\nclock_hz: 16000000\n",
        encoding="utf-8",
    )
    (tmp_path / "hardware_profile.yaml").write_text(
        "version: 1\nproject: p\nmcu:\n  part: atmega328p\n  clock_hz: 16000000\n",
        encoding="utf-8",
    )

    from eaa.kb import Constraints, HardwareProfile

    bam_rb = Constraints.load(tmp_path / "constraints.yaml").content_version
    bam_pc = HardwareProfile.load(tmp_path / "hardware_profile.yaml").content_version

    state = ProjectState(constraints_version=bam_rb, hardware_version=bam_pc)
    assert _troi_rang_buoc(state, tmp_path) == "", "khớp mà vẫn báo trôi"

    # Sửa MỘT chân, giữ nguyên `version: 1` — đúng như lần sửa thật.
    (tmp_path / "hardware_profile.yaml").write_text(
        "version: 1\nproject: p\nmcu:\n  part: atmega328p\n  clock_hz: 16000000\n"
        "pin_map:\n  PB2: {net: BUZZER, direction: out}\n",
        encoding="utf-8",
    )
    canh_bao = _troi_rang_buoc(state, tmp_path)

    assert canh_bao, "đổi hồ sơ phần cứng mà status im lặng"
    assert "phần cứng" in canh_bao.lower() or "hardware" in canh_bao.lower()
    assert "G1" in canh_bao, "không chỉ ra cửa nào mở lại được"


def test_state_giu_duoc_bam_phan_cung(tmp_path: Path) -> None:
    from eaa.state import ProjectState, StateStore

    kho = StateStore(tmp_path / "project_state.json")
    kho.save(ProjectState(hardware_version="sha256:abc"))
    assert kho.load().hardware_version == "sha256:abc"


def test_state_cu_khong_co_truong_nay_van_doc_duoc(tmp_path: Path) -> None:
    import json

    from eaa.state import StateStore

    (tmp_path / "project_state.json").write_text(
        json.dumps({"phase": "A", "constraints_version": "sha256:x"}), encoding="utf-8"
    )
    assert StateStore(tmp_path / "project_state.json").load().hardware_version == ""


def test_ho_so_G1_cho_NGUOI_DOC_ca_bang_chan() -> None:
    """Neo vào một thứ người không được đọc thì cái neo ấy vô nghĩa.

    G1 tên là *chốt ràng buộc cứng và kiến trúc*, và bảng chân LÀ kiến trúc.
    Trước đây phần `details` của hồ sơ chỉ có nguyên văn `constraints.yaml`.
    """
    import inspect

    from eaa import cli

    nguon = inspect.getsource(cli._ho_so_gate) if hasattr(cli, "_ho_so_gate") else ""
    if not nguon:  # pragma: no cover - đổi tên hàm thì bài này phải được sửa theo
        pytest.skip("không tìm thấy hàm dựng hồ sơ gate")
    i = nguon.index('gate_id == "G1"')
    khoi = nguon[i:i + 1500]
    assert "hardware" in khoi, "hồ sơ G1 không cho người đọc hồ sơ phần cứng"


def test_tai_lieu_thiet_ke_van_doi_dieu_nay() -> None:
    """Bài canh neo vào chính câu chữ đã hứa, để nó không bị lặng lẽ bỏ."""
    van_ban = (
        REPO / "projects" / "robot_balance" / "hardware_profile.yaml"
    ).read_text(encoding="utf-8")
    assert "duyệt lại tại G1" in van_ban
