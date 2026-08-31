"""TC-90 — bảng kiểm sẵn sàng chỉ thấy được thứ ĐÃ CÓ AI KHAI.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-115.

Tìm ra ở Bài 1 phiên kiểm với bo thật. `eaa resolve drv_uart` kết luận:

    CÓ 6 · THIẾU 0 · MÂU THUẪN 0
    Đủ điều kiện mở vòng sinh mã: eaa gen drv_uart

Vòng sinh mã chạy ngay sau đó, và mô hình viết vào tệp tiêu đề:

    THIẾU THÔNG TIN: ds-041 chỉ cung cấp cấu hình tốc độ baud và khung truyền.
    Không có thông tin về thanh ghi dữ liệu (UDR0) và các cờ trạng thái
    (UDRE0, RXC0). […] module này không lấp chỗ trống để hiện thực các hàm
    truyền/nhận dữ liệu.

Cả hai đều đúng phần của mình, và đó mới là vấn đề. Bảng kiểm đi theo cạnh
`ngoại vi –configured_by→ thanh ghi` của Knowledge Graph, mà `configured_by`
là một danh sách VIẾT TAY trong `hardware_profile.yaml`. Nó liệt kê năm thanh
ghi CẤU HÌNH của cổng nối tiếp và không liệt kê thanh ghi DỮ LIỆU.

Nên phép kiểm trả lời đúng câu nó hỏi — *"có tài liệu cho những thanh ghi đã
khai không"* — trong khi người đọc hiểu nó là *"module này sinh mã được
chưa"*. Một thanh ghi không ai nghĩ tới là một chỗ thiếu không ai thấy, và
thứ duy nhất tìm ra nó là chính vòng sinh mã, sau khi đã trả tiền cho nó.

Bài này không đòi phép kiểm trở nên toàn tri. Nó đòi phép kiểm **nói đúng
phạm vi mình phủ**.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _du_an(tmp_path: Path) -> Path:
    d = tmp_path / "da"
    d.mkdir()
    (d / "constraints.yaml").write_text(
        "version: 1\nplatform: avr\nmcu: atmega328p\nforbidden:\n  - delay()\n",
        encoding="utf-8",
    )
    (d / "hardware_profile.yaml").write_text(
        "version: 1\nproject: da\n"
        "mcu:\n  part: atmega328p\n  clock_hz: 16000000\n"
        "peripherals:\n"
        "  - id: cong_noi_tiep\n"
        "    kind: uart\n"
        "    configured_by: [REG_A]\n",
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), "init"],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    return d


def _chay(d: Path, *argv: str) -> str:
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(d), *argv],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    return kq.stdout + kq.stderr


def test_bang_kiem_NOI_RO_no_suy_tu_danh_sach_viet_tay(tmp_path: Path) -> None:
    """Kết luận "đủ điều kiện" phải kèm phạm vi, nếu không nó nói quá.

    Không có câu ấy thì người đọc — và Agent đọc lại đầu ra này — hiểu "THIẾU 0"
    thành "không thiếu gì", trong khi nó chỉ có nghĩa "không thiếu trong số đã
    khai".
    """
    d = _du_an(tmp_path)
    if not (d / "project_state.json").is_file():
        import pytest

        pytest.skip("không dựng được dự án trong môi trường này")

    _chay(d, "plan", "add", "mod_x", "--uses", "cong_noi_tiep")
    ra = _chay(d, "resolve", "mod_x")

    assert "configured_by" in ra, "không nói bảng kiểm suy từ đâu"
    assert any(x in ra.lower() for x in ("viết tay", "khai tay", "do người khai")), \
        "không nói danh sách ấy do người viết"
    assert "không ai khai" in ra or "chưa khai" in ra, \
        "không cảnh báo rằng thanh ghi không ai khai thì không ai thấy thiếu"


def test_khong_tuyen_DU_DIEU_KIEN_tran_trui(tmp_path: Path) -> None:
    """"Đủ điều kiện mở vòng sinh mã" là một khẳng định mạnh hơn thứ đã kiểm."""
    d = _du_an(tmp_path)
    if not (d / "project_state.json").is_file():
        import pytest

        pytest.skip("không dựng được dự án trong môi trường này")

    _chay(d, "plan", "add", "mod_x", "--uses", "cong_noi_tiep")
    ra = _chay(d, "resolve", "mod_x")

    if "Đủ điều kiện" in ra:
        dong = next(d_ for d_ in ra.splitlines() if "Đủ điều kiện" in d_)
        assert "đã khai" in dong or "ĐÃ KHAI" in dong, (
            f"câu kết luận không nêu phạm vi: {dong!r}"
        )
