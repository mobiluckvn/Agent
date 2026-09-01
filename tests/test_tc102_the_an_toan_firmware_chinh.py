"""TC-102 — ảnh firmware CHÍNH cũng phải có thẻ an toàn.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-132.

Tìm ra khi chuẩn bị bài "robot tự cân bằng tại chỗ".

`_ghi_the_kem` chỉ chạy ở đường CHẨN ĐOÁN. Ảnh do `eaa build` ráp — tức firmware
THẬT của sản phẩm — không có `.meta.json` nào. Nên `eaa flash approve` đọc thẻ
không thấy gì, và duyệt nó **y như một ảnh đo tĩnh**: in ra đường dẫn, băm, xong.

Cùng hình dạng SL-124, nhưng ở chỗ nguy hơn hẳn
------------------------------------------------

SL-124 là ảnh chẩn đoán DS-03 quay bánh 22° trên giá. Ảnh ở đây là firmware
điều khiển của một robot **đứng trên hai bánh**: nó không quay một nhịp rồi
dừng, nó chạy vô hạn, và khi nó ngã thì không ai biết trước ngã về phía nào.

Và checklist của các kịch bản chẩn đoán KHÔNG dùng lại được: mọi mục đều bắt
đầu bằng *"robot đã kê lên giá, bánh KHÔNG chạm đất"*, trong khi cân bằng thì
bắt buộc bánh CHẠM đất. Tình huống an toàn đảo chiều, nên checklist phải là một
danh sách khác, do dự án khai.

Nơi khai là `firmware.yaml` — chỗ dự án đã khai module nào vào firmware và chạy
mỗi bao nhiêu mili giây. Nó là tệp mô tả CHÍNH ảnh ấy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


def test_firmware_yaml_khai_duoc_phan_an_toan() -> None:
    """Ảnh chính có làm thiết bị chuyển động không — chỉ dự án trả lời được."""
    d = yaml.safe_load((DU_AN / "firmware.yaml").read_text(encoding="utf-8"))
    assert "safety" in d, (
        "firmware.yaml chưa khai mục `safety` cho ảnh chính. Engine không đoán "
        "được một firmware có làm robot chạy hay không"
    )


def test_khai_motion_thi_PHAI_co_checklist() -> None:
    """Nói 'cái này làm thiết bị chuyển động' rồi không nói phải kiểm gì là nói nửa câu."""
    d = yaml.safe_load((DU_AN / "firmware.yaml").read_text(encoding="utf-8"))
    at = d.get("safety") or {}
    if at.get("motion"):
        assert at.get("checklist"), "khai motion mà không có checklist"


def test_checklist_can_bang_KHAC_checklist_chan_doan() -> None:
    """Tình huống an toàn ĐẢO CHIỀU, nên checklist không được sao chép.

    Kịch bản chẩn đoán đòi bánh KHÔNG chạm đất. Robot cân bằng thì bắt buộc
    bánh CHẠM đất — dùng lại checklist cũ là dán một câu vô nghĩa vào đúng chỗ
    người ta cần đọc kỹ nhất.
    """
    d = yaml.safe_load((DU_AN / "firmware.yaml").read_text(encoding="utf-8"))
    at = d.get("safety") or {}
    if not at.get("motion"):
        pytest.skip("ảnh chính chưa khai là làm thiết bị chuyển động")

    muc = " ".join(str(m) for m in at.get("checklist", [])).lower()
    assert "không chạm đất" not in muc, (
        "chép checklist của kịch bản chẩn đoán sang: robot cân bằng thì bánh "
        "PHẢI chạm đất"
    )


# ═══════════ thẻ phải được GHI RA cạnh ảnh ═══════════


def test_ghi_the_cho_anh_chinh(tmp_path: Path) -> None:
    from eaa.firmware import ghi_the_an_toan

    anh = tmp_path / "firmware.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")
    ghi_the_an_toan(anh, {"motion": True, "checklist": ["Sàn trống quanh robot"]})

    the = json.loads(Path(str(anh) + ".meta.json").read_text(encoding="utf-8"))
    assert the["motion"] is True
    assert the["safety_checklist"] == ["Sàn trống quanh robot"]


def test_khong_khai_gi_thi_KHONG_ghi_the(tmp_path: Path) -> None:
    """Thẻ rỗng đọc thành 'đã xét và thấy không nguy hiểm'. Không xét thì đừng ghi."""
    from eaa.firmware import ghi_the_an_toan

    anh = tmp_path / "firmware.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")
    ghi_the_an_toan(anh, {})
    assert not Path(str(anh) + ".meta.json").exists()


def test_the_dung_DUNG_dinh_dang_ma_cong_nap_doc(tmp_path: Path) -> None:
    """Ghi ra một thẻ mà cổng nạp không đọc được thì bằng không ghi."""
    from eaa.cli import _the_cua_anh
    from eaa.firmware import ghi_the_an_toan

    anh = tmp_path / "firmware.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")
    ghi_the_an_toan(anh, {"motion": True, "checklist": ["Sàn trống"]})

    the = _the_cua_anh(anh)
    assert the.get("motion") is True
    assert the.get("safety_checklist") == ["Sàn trống"]
