"""TC-97 — duyệt một ảnh làm THIẾT BỊ CHUYỂN ĐỘNG phải khác duyệt ảnh đo tĩnh.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-124.

Chỗ hở này do **chính bản sửa SL-119 của tôi tạo ra**, và nó là chỗ hở nguy
hiểm nhất cả phiên.

Trước SL-119, đường nạp duy nhất là hỏi trực tiếp trên terminal, và bản tóm tắt
lúc hỏi có kèm thẻ đi kèm ảnh — trong đó có dòng *"⚠ ẢNH NÀY LÀM THIẾT BỊ
CHUYỂN ĐỘNG"* và checklist an toàn. Chú thích của chính hàm đọc thẻ nói rõ vì
sao nó tồn tại:

    Một ảnh chẩn đoán làm robot chuyển động trông y hệt một ảnh đo tĩnh. Thẻ
    này đưa checklist an toàn ra đúng lúc người sắp bấm đồng ý, chứ không phải
    lúc dựng ảnh — giữa hai thời điểm ấy có thể là vài ngày.

SL-119 thêm sổ duyệt ngoài luồng để phiên không có terminal vẫn nạp được. Nó
**đi vòng qua đúng chỗ ấy**: `eaa flash approve --image <ảnh>` in ra tên tệp và
băm, hết. Người duyệt không hề biết mình vừa cho phép bánh xe quay.

Đo được: duyệt ảnh DS-03 (`motion: true`, ba mục checklist) in ra đúng ba dòng
— đường dẫn, băm, và "đã ghi quyết định".

Bất biến: **thông tin đi kèm một quyết định không được biến mất khi đường đi
tới quyết định ấy đổi.** Mở một cánh cửa mới thì cửa ấy phải mang theo mọi thứ
cửa cũ mang.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

CHECKLIST = [
    "Bánh KHÔNG chạm đất",
    "Không có tay người trong vùng quay",
]


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    d = tmp_path / "da"
    d.mkdir()
    (d / "constraints.yaml").write_text(
        "version: 1\nplatform: avr\nmcu: chip_bia\nforbidden:\n  - delay()\n",
        encoding="utf-8",
    )
    (d / "hardware_profile.yaml").write_text(
        "version: 1\nproject: da\nmcu:\n  part: chip_bia\n  clock_hz: 16000000\n",
        encoding="utf-8",
    )
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), "init"],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    assert (d / "project_state.json").is_file(), f"{kq.stdout}\n{kq.stderr}"
    return d


def _anh(d: Path, *, motion: bool) -> Path:
    build = d / "firmware" / "build"
    build.mkdir(parents=True, exist_ok=True)
    anh = build / ("dong.hex" if motion else "tinh.hex")
    anh.write_text(":00000001FF\n", encoding="utf-8")
    the = {
        "scenario": "DS-X",
        "title": "Kịch bản thử",
        "motion": motion,
        "safety_checklist": CHECKLIST if motion else [],
    }
    Path(str(anh) + ".meta.json").write_text(
        json.dumps(the, ensure_ascii=False), encoding="utf-8"
    )
    return anh


def _duyet(d: Path, anh: Path, *them: str) -> tuple[int, str]:
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d),
         "flash", "approve", "--image", str(anh), "--actor", "người kiểm", *them],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    return kq.returncode, kq.stdout + kq.stderr


def _da_ghi(d: Path) -> list[dict]:
    so = d / "flash_approvals.jsonl"
    if not so.is_file():
        return []
    return [json.loads(x) for x in so.read_text(encoding="utf-8").splitlines() if x.strip()]


# ═══════════ ảnh chuyển động: phải NÓI RA, và phải ĐÒI xác nhận ═══════════


def test_anh_chuyen_dong_TU_CHOI_khi_chua_xac_nhan_an_toan(du_an: Path) -> None:
    """Điểm cốt lõi. Người duyệt phải biết mình đang cho phép cái gì."""
    anh = _anh(du_an, motion=True)
    ma, ra = _duyet(du_an, anh)

    assert ma != 0, "duyệt trót lọt một ảnh làm thiết bị chuyển động"
    assert "CHUYỂN ĐỘNG" in ra, "không nói ảnh này làm thiết bị chuyển động"
    for muc in CHECKLIST:
        assert muc in ra, f"không nêu mục checklist: {muc}"
    assert _da_ghi(du_an) == [], "đã ghi quyết định dù chưa xác nhận an toàn"


def test_xac_nhan_DU_cac_muc_thi_duyet_duoc(du_an: Path) -> None:
    anh = _anh(du_an, motion=True)
    them: list[str] = []
    for m in CHECKLIST:
        them += ["--confirm-safety", m]
    ma, ra = _duyet(du_an, anh, *them)

    assert ma == 0, ra
    assert len(_da_ghi(du_an)) == 1


def test_xac_nhan_THIEU_MOT_muc_van_bi_tu_choi(du_an: Path) -> None:
    """Xác nhận hai trong ba mục là chưa xác nhận. Không có phần điểm ở đây."""
    anh = _anh(du_an, motion=True)
    ma, ra = _duyet(du_an, anh, "--confirm-safety", CHECKLIST[0])

    assert ma != 0
    assert CHECKLIST[1] in ra, "không nêu ĐÍCH DANH mục còn thiếu"
    assert _da_ghi(du_an) == []


def test_quyet_dinh_GHI_LAI_da_xac_nhan_nhung_gi(du_an: Path) -> None:
    """Sổ phải giữ được vết: sáu tháng sau, ai đã xác nhận điều gì.

    Một quyết định an toàn không ghi lại nội dung mình xác nhận thì lúc cần
    truy nó không nói được gì hơn "có người bấm đồng ý".
    """
    anh = _anh(du_an, motion=True)
    them: list[str] = []
    for m in CHECKLIST:
        them += ["--confirm-safety", m]
    _duyet(du_an, anh, *them)

    ban_ghi = _da_ghi(du_an)[0]
    assert ban_ghi.get("motion") is True
    assert set(ban_ghi.get("safety_confirmed", [])) == set(CHECKLIST)


# ═══════════ ảnh đo tĩnh: không đổi gì ═══════════


def test_anh_TINH_van_duyet_binh_thuong(du_an: Path) -> None:
    """Cổng mới không được làm phiền đường vốn không nguy hiểm.

    Một cổng đòi thừa thì sớm muộn bị bấm cho xong, và lúc nó đòi đúng thì
    cũng bị bấm cho xong.
    """
    anh = _anh(du_an, motion=False)
    ma, _ = _duyet(du_an, anh)
    assert ma == 0
    assert len(_da_ghi(du_an)) == 1


def test_anh_KHONG_CO_THE_van_duyet_binh_thuong(du_an: Path, tmp_path: Path) -> None:
    """Ảnh dựng ngoài đường chẩn đoán thì không có thẻ — vẫn phải duyệt được."""
    anh = tmp_path / "tu_dung.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")
    ma, _ = _duyet(du_an, anh)
    assert ma == 0


# ═══════════ và đường NẠP cũng phải kiểm, không chỉ đường DUYỆT ═══════════


def test_quyet_dinh_CU_thieu_xac_nhan_an_toan_KHONG_mo_duong_nap(tmp_path: Path) -> None:
    """Sổ là append-only, nên bản ghi lỏng lẻo cũ vẫn nằm đó mãi.

    Tôi tự chứng minh điều này: lúc thử xem `flash approve` có cảnh báo không,
    tôi đã ghi một quyết định THẬT cho ảnh DS-03 với tên người vô nghĩa và
    không có xác nhận an toàn nào. Bản ghi ấy hợp lệ về băm, nên nó mở đường
    nạp cho một ảnh làm bánh xe quay.

    Sửa ở đường duyệt là chưa đủ. Đường NẠP phải tự kiểm: ảnh có thẻ chuyển
    động thì quyết định đi kèm phải phủ đủ checklist.
    """
    from eaa.flash import FlashApprovals, Flasher

    anh = tmp_path / "dong.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")

    so = FlashApprovals(tmp_path / "so.jsonl")
    so.approve(anh, by="ai đó")          # bản ghi kiểu cũ: không motion, không checklist

    f = Flasher(runner=None, approvals=so)
    assert f.da_duoc_duyet(anh) is not None, "ảnh tĩnh thì vẫn phải qua"
    assert f.da_duoc_duyet(anh, required_safety=CHECKLIST) is None, \
        "quyết định thiếu xác nhận an toàn mà vẫn mở đường nạp ảnh chuyển động"


def test_quyet_dinh_CO_du_xac_nhan_thi_mo_duong_nap(tmp_path: Path) -> None:
    from eaa.flash import FlashApprovals, Flasher

    anh = tmp_path / "dong.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")

    so = FlashApprovals(tmp_path / "so.jsonl")
    so.approve(anh, by="người kiểm", motion=True, safety_confirmed=CHECKLIST)

    f = Flasher(runner=None, approvals=so)
    assert f.da_duoc_duyet(anh, required_safety=CHECKLIST) is not None


def test_thieu_MOT_muc_trong_quyet_dinh_van_bi_chan(tmp_path: Path) -> None:
    from eaa.flash import FlashApprovals, Flasher

    anh = tmp_path / "dong.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")

    so = FlashApprovals(tmp_path / "so.jsonl")
    so.approve(anh, by="người kiểm", motion=True, safety_confirmed=CHECKLIST[:1])

    f = Flasher(runner=None, approvals=so)
    assert f.da_duoc_duyet(anh, required_safety=CHECKLIST) is None
