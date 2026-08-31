"""TC-93 — người duyệt ẢNH nạp; Agent là kẻ nạp nó.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-119.

Cùng chỗ hở SL-110 đã sửa cho cổng cài công cụ, lần này trên **cổng nạp
firmware** — và ở đây nó nặng hơn, vì nạp là chặng cuối của cả sản phẩm.

`eaa flash` qua hết phần kiểm trước — ảnh có, kho sạch, ảnh mới hơn nguồn, cổng
tự nhận đúng — rồi dừng:

    Chưa có xác nhận của người nên KHÔNG nạp (FR-DIA-02).
    Phiên không có terminal cũng tính là chưa xác nhận.

Đúng, và không nêu lối đi tiếp. Không cờ nào, không lệnh nào, không sổ nào. Một
phiên làm việc qua người trung gian **không bao giờ** nạp được firmware, dù
người có đồng ý bao nhiêu lần.

Bất biến không đổi: **không ảnh nào được nạp mà thiếu một người duyệt đúng ảnh
ấy.** Neo vào BĂM NỘI DUNG ảnh chứ không vào đường dẫn — đường dẫn thì ghi đè
được, và "duyệt ảnh này rồi nạp ảnh khác" phải là chuyện bất khả thi, không
phải chuyện dựa vào việc không ai làm thế.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from eaa.flash import FlashApprovals


@pytest.fixture()
def anh(tmp_path: Path) -> Path:
    p = tmp_path / "firmware.hex"
    p.write_text(":00000001FF\n", encoding="utf-8")
    return p


@pytest.fixture()
def so(tmp_path: Path) -> FlashApprovals:
    return FlashApprovals(tmp_path / "flash_approvals.jsonl")


def test_duyet_roi_thi_tim_lai_duoc(so: FlashApprovals, anh: Path) -> None:
    so.approve(anh, by="Vũ Trí Công")
    k = so.find(anh)
    assert k is not None and k.actor == "Vũ Trí Công"


def test_chua_duyet_thi_KHONG_tim_thay(so: FlashApprovals, anh: Path) -> None:
    assert so.find(anh) is None


def test_neo_vao_NOI_DUNG_anh_khong_phai_duong_dan(so: FlashApprovals, anh: Path) -> None:
    """Bất biến quan trọng nhất của bản sửa này.

    Đường dẫn ghi đè được. Neo vào đường dẫn thì "duyệt ảnh này rồi nạp ảnh
    khác" chỉ cần một lần `eaa build` xen vào giữa — và bản ghi vẫn nói có
    người duyệt.
    """
    so.approve(anh, by="người duyệt")
    anh.write_text(":00000001AA\n", encoding="utf-8")   # cùng tên, khác nội dung
    assert so.find(anh) is None, "đổi nội dung ảnh mà quyết định cũ vẫn hiệu lực"


def test_duyet_anh_khac_KHONG_lay_sang_duoc(so: FlashApprovals, tmp_path: Path) -> None:
    a = tmp_path / "a.hex"
    b = tmp_path / "b.hex"
    a.write_text("A", encoding="utf-8")
    b.write_text("B", encoding="utf-8")
    so.approve(a, by="người duyệt")
    assert so.find(b) is None


def test_phai_ghi_TEN_nguoi_duyet(so: FlashApprovals, anh: Path) -> None:
    with pytest.raises(Exception, match="ai duyệt"):
        so.approve(anh, by="   ")


def test_so_ghi_NOI_TIEP_va_doc_lai_duoc(so: FlashApprovals, tmp_path: Path) -> None:
    a = tmp_path / "a.hex"
    a.write_text("A", encoding="utf-8")
    so.approve(a, by="người 1")
    so.approve(a, by="người 2")
    assert len(so.path.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert len(so.all()) == 2


def test_so_hong_doc_thanh_CHUA_DUYET(so: FlashApprovals, anh: Path) -> None:
    """Hướng hỏng an toàn chỉ có một chiều."""
    so.path.write_text("{ không phải json\n", encoding="utf-8")
    assert so.all() == []
    assert so.find(anh) is None


def test_bam_la_bam_NOI_DUNG_that(so: FlashApprovals, anh: Path) -> None:
    k = so.approve(anh, by="x")
    assert k.image_digest == "sha256:" + hashlib.sha256(anh.read_bytes()).hexdigest()


# ═══════════ ranh giới quyền của Agent ═══════════


def test_flash_approve_KHONG_nam_trong_danh_muc_Agent() -> None:
    """Agent nạp được ảnh ĐÃ DUYỆT; nó không tự duyệt được.

    Cùng hình dạng `tool approve`/`tool run` (SL-77) và
    `doctor approve`/`doctor --fix` (SL-110): mở rộng CÁI NÓ LÀM, không mở rộng
    QUYỀN NÓ CÓ.
    """
    from eaa.agent import NGOAI_DANH_MUC, TOOLBOX

    trong = {" ".join(t.argv) for t in TOOLBOX}
    assert "flash approve" not in trong
    assert "flash approve" in NGOAI_DANH_MUC or "flash" in NGOAI_DANH_MUC


def test_flasher_dung_so_duyet_khi_khong_co_terminal(tmp_path: Path, anh: Path) -> None:
    """Đường Agent đi: không terminal, nhưng sổ có chữ ký đúng ảnh này."""
    from eaa.flash import Flasher

    so = FlashApprovals(tmp_path / "so.jsonl")
    so.approve(anh, by="người duyệt")

    f = Flasher(runner=None, approvals=so)
    assert f.da_duoc_duyet(anh) is not None


def test_flasher_khong_co_chu_ky_thi_KHONG_nap(tmp_path: Path, anh: Path) -> None:
    from eaa.flash import Flasher

    f = Flasher(runner=None, approvals=FlashApprovals(tmp_path / "so.jsonl"))
    assert f.da_duoc_duyet(anh) is None
