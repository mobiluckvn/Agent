"""TC-95 — biết rồi thì phải NÓI RA, trước khi sai người đi làm việc chân tay.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-121.

Tìm ra ở Bài 2 phiên kiểm với bo thật. `eaa diagnose run DS-02` thu xong bốn
khung từ chip, trong đó có:

    {"who_am_i": "0x72"}

Kịch bản khai đích danh `who_am_i op: equals expected: "0x68"`. Tức phép kiểm
ấy **đã trượt ngay lúc dữ liệu về**. Nhưng lệnh không nói một chữ về nó — nó in
thẳng hai câu hỏi cho người:

    Nghiêng robot sang TRÁI. Giá trị góc hiển thị có chuyển sang ÂM không?
    Trục dữ liệu có khớp trục vật lý không?

Nguyên nhân: `if kich_ban.human and not tra_loi:` in câu hỏi rồi `return` — kênh
máy **chưa từng được chấm**.

Hai chuyện khác nhau, và bản sửa này chỉ đụng chuyện thứ hai:

* **Chưa kết luận khi thiếu nửa dữ liệu** — ĐÚNG, giữ nguyên. Chẩn đoán là
  phép giao của hai kênh.
* **Giấu phần đã biết** — SAI. Nó sai người đi nghiêng bo, quan sát, gõ trả
  lời, để rồi mới biết mã nhận dạng của con chip chưa bao giờ khớp. Việc chân
  tay ấy không đổi được kết cục.

Và với riêng ca này, phần bị giấu là phần quyết định nhất: mã nhận dạng sai
nghĩa là **có thể đây không phải con cảm biến dự án đang khai**. Mọi câu hỏi về
dấu và trục đều đứng sau câu hỏi ấy.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

KICH_BAN = """\
version: 1
telemetry:
  baud: 9600
  checksum: xor8
  separator: "*"
scenarios:
  - id: DS-TEST
    title: Kịch bản thử
    description: Kiểm cả hai kênh.
    motion: false
    symptoms: [thử]
    machine:
      - key: ma_nhan_dang
        description: Mã nhận dạng thiết bị
        op: equals
        expected: "0x68"
    human:
      - key: dau_dung
        question: Dấu có đúng không?
    rules:
      - machine: false
        human: {}
        verdict: sai linh kiện
        action: đối chiếu lại linh kiện trên bo
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
        "version: 1\nproject: da\nmcu:\n  part: chip_bia\n  clock_hz: 16000000\n",
        encoding="utf-8",
    )
    (d / "diagnostics.yaml").write_text(KICH_BAN, encoding="utf-8")
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), "init"],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    # ĐỪNG skip ở đây. Bản đầu của bài này dùng `pytest.skip` khi init hỏng, và
    # nó đã che mất một lỗi cú pháp tôi vừa gây ra trong `eaa/cli.py`: bốn bài
    # chuyển sang "skipped", bảng test xanh, còn CLI thì không import nổi.
    #
    # Một điều kiện bỏ qua rộng hơn cần thiết là một chỗ cho lỗi thật trốn vào.
    assert (d / "project_state.json").is_file(), (
        f"eaa init hỏng — đây là LỖI, không phải môi trường thiếu:\n"
        f"{kq.stdout}\n{kq.stderr}"
    )
    return d


def _chay_thieu_tra_loi(d: Path, telemetry: dict) -> str:
    tep = d / "telemetry.json"
    tep.write_text(json.dumps(telemetry), encoding="utf-8")
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d),
         "diagnose", "run", "DS-TEST", "--telemetry", str(tep)],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    return kq.stdout + kq.stderr


# ═══════════ phần ĐÃ BIẾT phải hiện ra ═══════════


def test_kenh_may_TRUOT_thi_noi_ngay_truoc_khi_hoi_nguoi(du_an: Path) -> None:
    """Điểm cốt lõi: đừng sai người đi làm việc chân tay khi đã biết nó trượt."""
    ra = _chay_thieu_tra_loi(du_an, {"ma_nhan_dang": "0x72"})

    assert "Mã nhận dạng thiết bị" in ra, "không nói gì về phép kiểm đã trượt"
    assert "0x72" in ra, "không nêu giá trị đo được"
    assert "0x68" in ra, "không nêu giá trị kỳ vọng"
    assert "✗" in ra, "không đánh dấu là trượt"
    assert "Cần quan sát của người" in ra, "vẫn phải hỏi tiếp — chưa được kết luận"


def test_van_KHONG_KET_LUAN_khi_thieu_nua_du_lieu(du_an: Path) -> None:
    """Bản sửa này KHÔNG được đổi chuyện đó. Chẩn đoán vẫn là phép giao."""
    ra = _chay_thieu_tra_loi(du_an, {"ma_nhan_dang": "0x72"})
    assert "Kết luận chẩn đoán" not in ra
    assert "phép GIAO" in ra or "phép giao" in ra


def test_kenh_may_DAT_thi_cung_hien_ra(du_an: Path) -> None:
    """Thấy phần đã đạt cũng có ích: người biết mình đang đi kiểm nốt phần nào."""
    ra = _chay_thieu_tra_loi(du_an, {"ma_nhan_dang": "0x68"})
    assert "✓" in ra
    assert "Cần quan sát của người" in ra


def test_canh_bao_dung_muc_khi_da_co_phep_kiem_TRUOT(du_an: Path) -> None:
    """Người sắp bỏ công ra thì phải biết công ấy có đổi được kết cục không."""
    ra = _chay_thieu_tra_loi(du_an, {"ma_nhan_dang": "0x72"})
    thap = ra.lower()
    assert "đã trượt" in thap or "trượt" in thap
