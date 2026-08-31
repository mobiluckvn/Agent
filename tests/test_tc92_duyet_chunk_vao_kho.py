"""TC-92 — trích đoạn tài liệu KHÔNG có đường nào vào kho tri thức.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-117.

Tìm ra ở Bài 1 phiên kiểm với bo thật, khi nạp datasheet chính chủ để lấp chỗ
thiếu mà vòng sinh mã đã nêu.

`eaa datasheet add` tạo chunk và nói:

    Chunk đang ở trạng thái 'proposed' nên CHƯA truy xuất được vào prompt nào.
    Kỹ sư đối chiếu từng bit với bản gốc, sửa lại phần chưa chưng cất, rồi duyệt:
      eaa gate show G2
      eaa gate approve G2

Làm đúng thế. Gate ghi nhận quyết định. **Chunk vẫn `proposed`.**

Không phải sai `--project`, không phải sai cú pháp. `DatasheetStore` là một kho
CHỈ ĐỌC — nó không có phương thức nào ghi, và không dòng mã nào trong engine
đổi trạng thái một chunk từ `proposed` sang `approved`. Đường ấy **chưa từng
tồn tại**.

Hệ quả đúng bằng cả sản phẩm: `eaa datasheet add` sinh ra một tệp không bao giờ
dùng được, và chỉ người dùng sang một lệnh không làm gì cả. Những chunk đang
`approved` trong dự án mẫu đều được VIẾT TAY sẵn với `status: approved`; không
cái nào đi qua đường nạp.

Và bất biến "tri thức chỉ vào kho qua G2" đúng theo nghĩa tệ nhất có thể: nó
đúng vì **không gì vào được cả**.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

CHUNK = """\
---
id: ds-thu-01
device: chip_bia
peripheral: ngoai_vi_bia
registers:
- ABC0
- DEF0
topic: thử nghiệm
source: tai_lieu_bia.pdf, tr.1-2
source_hash: sha256:0000
status: proposed
confidence: medium
note: Chunk ĐỀ XUẤT do máy trích xuất.
---

## Trích đoạn ngoai_vi_bia

Nội dung thử.
"""


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    d = tmp_path / "da"
    d.mkdir()
    (d / "constraints.yaml").write_text(
        "version: 1\nplatform: avr\nmcu: chip_bia\nforbidden:\n  - delay()\n",
        encoding="utf-8",
    )
    (d / "hardware_profile.yaml").write_text(
        "version: 1\nproject: da\n"
        "mcu:\n  part: chip_bia\n  clock_hz: 16000000\n"
        "peripherals:\n"
        "  - id: ngoai_vi_bia\n    kind: uart\n    configured_by: [ABC0, DEF0]\n",
        encoding="utf-8",
    )
    (d / "datasheets").mkdir()
    (d / "datasheets" / "ds-thu-01.md").write_text(CHUNK, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), "init"],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    if not (d / "project_state.json").is_file():
        pytest.skip("không dựng được dự án trong môi trường này")
    return d


def _chay(d: Path, *argv: str) -> str:
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), *argv],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    return kq.stdout + kq.stderr


def _trang_thai(d: Path, chunk_id: str = "ds-thu-01") -> str:
    from eaa.kb import DatasheetStore

    return DatasheetStore(d / "datasheets").get(chunk_id, include_inactive=True).status


# ═══════════ đường vào kho phải TỒN TẠI ═══════════


def test_duyet_G2_dua_chunk_de_xuat_thanh_DA_DUYET(du_an: Path) -> None:
    """Điểm cốt lõi. Không có bước này thì đường nạp tri thức là một ngõ cụt."""
    assert _trang_thai(du_an) == "proposed"

    ra = _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")

    assert _trang_thai(du_an) == "approved", (
        "duyệt G2 xong mà chunk vẫn 'proposed' — lệnh mà chính hệ chỉ sang "
        f"không đổi được gì.\n{ra}"
    )


def test_chunk_da_duyet_thi_TRUY_XUAT_duoc(du_an: Path) -> None:
    """Duyệt mà không truy xuất được thì việc duyệt chưa xong.

    `active()` là thứ bộ lắp prompt đọc. Một chunk 'approved' mà không nằm
    trong đó thì nó vẫn vô hình đúng như lúc còn 'proposed'.
    """
    _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")

    from eaa.kb import DatasheetStore

    kho = DatasheetStore(du_an / "datasheets")
    assert "ds-thu-01" in {c.id for c in kho.active()}
    assert kho.by_register("ABC0"), "đồ thị tri thức không nối được tới chunk"


def test_ghi_AI_duyet_va_LUC_NAO_vao_chinh_chunk(du_an: Path) -> None:
    """Một quyết định không có người chịu trách nhiệm không phải quyết định.

    Cùng luật với mục công cụ trong manifest của pack, vốn mang `approved_by`
    và `approved_at` ngay trong tệp.
    """
    _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")

    van_ban = (du_an / "datasheets" / "ds-thu-01.md").read_text(encoding="utf-8")
    assert "approved_by: người kiểm" in van_ban
    assert "approved_at:" in van_ban


def test_NOI_DUNG_chunk_khong_bi_dong_toi(du_an: Path) -> None:
    """Duyệt là đổi TRẠNG THÁI, không phải đổi nội dung.

    Nội dung đổi thì phải qua supersede, không phải qua một lần duyệt — nếu
    không thì "duyệt cái này rồi dùng cái khác" là một đường vòng hợp lệ.
    """
    truoc = (du_an / "datasheets" / "ds-thu-01.md").read_text(encoding="utf-8")
    than_truoc = truoc.split("---\n", 2)[2]

    _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")

    sau = (du_an / "datasheets" / "ds-thu-01.md").read_text(encoding="utf-8")
    assert sau.split("---\n", 2)[2] == than_truoc, "nội dung trích đoạn bị sửa"


def test_TU_CHOI_G2_thi_chunk_o_lai_de_xuat(du_an: Path) -> None:
    """Từ chối không được nâng hạng gì — hướng an toàn chỉ có một chiều."""
    _chay(du_an, "gate", "reject", "G2", "--actor", "người kiểm",
          "--reason", "chưa đối chiếu xong")
    assert _trang_thai(du_an) == "proposed"


def test_khong_co_chunk_cho_duyet_thi_KHONG_sap(du_an: Path) -> None:
    """Duyệt G2 khi không có gì chờ là một lượt chạy hợp lệ, không phải lỗi."""
    _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")
    ra = _chay(du_an, "gate", "approve", "G2", "--actor", "người kiểm")
    assert "Traceback" not in ra


# ═══════════ chống tái phát ═══════════


def test_co_duong_ghi_vao_kho_trich_doan() -> None:
    """Bài canh dạng quét mã nguồn: kho tri thức phải CÓ đường ghi.

    Trước SL-117, `DatasheetStore` chỉ có phương thức đọc. Một kho chỉ đọc
    trong khi cả thiết kế nói tri thức "vào kho qua G2" nghĩa là câu ấy đúng
    theo nghĩa tệ nhất: đúng vì không gì vào được cả.
    """
    from eaa.kb import DatasheetStore

    assert hasattr(DatasheetStore, "approve"), (
        "DatasheetStore không có đường ghi nào — chunk 'proposed' không bao "
        "giờ thành 'approved' được"
    )
