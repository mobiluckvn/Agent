"""TC-100 — bộ phân rã phải biết Platform Pack đã cho sẵn những gì.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-130.

Tìm ra ở bài "robot tự cân bằng tại chỗ", ngay lần đầu chạy `eaa plan propose`.

Bản phân rã tám module rất hợp lý về mặt kiến trúc — trừ hai module **dựng lại
thứ nền tảng đã cho**, và cả hai sẽ hỏng lúc LIÊN KẾT:

    [system_timer]      chiếm timer0, cung cấp timer_init/timer_check_10ms_flag
    [main_coordinator]  cung cấp main

Khuôn `packs/avr/templates/main.c.tmpl` đã có sẵn: `int main(void)`, ngắt
`TIMER0_COMPA_vect` đếm mili giây, và một bộ định thời hợp tác gọi `step()` của
từng module theo `period_ms` khai trong `firmware.yaml`.

Nên `main_coordinator` cho ra **hai `main()`**, và `system_timer` cho ra **hai
`TIMER0_COMPA_vect`**.

Vì sao mô hình đề xuất như thế
-------------------------------

Vì không ai nói cho nó biết. Prompt phân rã chỉ có: mục tiêu, hồ sơ phần cứng,
ràng buộc. **Không một chữ nào về Platform Pack** — không nói pack sinh `main`,
không nói pack đã chiếm Timer0, không nói hợp đồng của một module là
``init``/``step`` chứ không phải ``main``.

Và không phép kiểm nào bắt: `_kiem_tai_nguyen` đối chiếu với hồ sơ phần cứng,
mà Timer0 CÓ trong hồ sơ — nó chỉ đã bị nền tảng chiếm trước.

Hai va chạm này chỉ lộ ra ở bước liên kết, tức là sau khi cả hai module đã đi
qua sinh mã, bốn cổng kiểm chứng, và G3. Chi phí của một chỗ thiếu thông tin
trong prompt được trả bằng toàn bộ vòng đời của hai module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
PACK = REPO / "packs" / "avr"


def _pack() -> dict:
    return yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))


# ═══════════ pack phải KHAI thứ nó chiếm và thứ nó cho ═══════════


def test_pack_khai_tai_nguyen_no_chiem() -> None:
    """Khuôn của pack dùng Timer0; không khai ra thì không ai đối chiếu được."""
    fw = _pack().get("firmware") or {}
    assert fw.get("reserves"), (
        "pack chưa khai `firmware.reserves` — tài nguyên khuôn main dùng riêng"
    )


def test_pack_khai_thu_no_CUNG_CAP() -> None:
    """`main`, bộ định thời, bộ đếm mili giây — module không cần viết lại."""
    fw = _pack().get("firmware") or {}
    assert fw.get("provides"), "pack chưa khai `firmware.provides`"


def test_khai_bao_KHOP_voi_khuôn_that() -> None:
    """Khai một đằng, khuôn làm một nẻo thì khai báo ấy còn tệ hơn không khai.

    Đọc thẳng khuôn: nó có `int main` và có ISR của bộ định thời nào.
    """
    import re

    khuon = (PACK / "templates" / "main.c.tmpl").read_text(encoding="utf-8")
    fw = _pack().get("firmware") or {}

    if "int main" in khuon:
        assert "main" in [str(x) for x in fw.get("provides", [])], (
            "khuôn sinh main() mà pack không khai là nó cung cấp main"
        )

    for m in re.finditer(r"ISR\(([A-Z0-9_]+)_vect\)", khuon):
        nguon = m.group(1).lower()          # ví dụ 'timer0_compa'
        bo_dem = nguon.split("_")[0]        # 'timer0'
        assert any(bo_dem in str(r).lower() for r in fw.get("reserves", [])), (
            f"khuôn dùng ngắt của {bo_dem} mà pack không khai nó trong `reserves`"
        )


# ═══════════ bộ phân rã phải ĐƯỢC BIẾT, và phải BỊ CHẶN ═══════════


def test_boi_canh_phan_ra_co_phan_nen_tang() -> None:
    """Mô hình không đoán ra được thứ không ai nói cho nó."""
    from eaa.decompose import _boi_canh_nen_tang

    van_ban = _boi_canh_nen_tang(_pack())
    assert "main" in van_ban
    assert "timer0" in van_ban.lower()
    # Phải nói cả hợp đồng, không chỉ danh sách cấm.
    assert "step" in van_ban.lower() and "init" in van_ban.lower()


def test_module_chiem_tai_nguyen_CUA_NEN_TANG_bi_canh_bao() -> None:
    from eaa.decompose import ModuleProposal, _kiem_trung_nen_tang

    m = ModuleProposal(id="system_timer", purpose="cờ 10 ms", uses=("timer0",))
    canh = _kiem_trung_nen_tang((m,), _pack())
    assert canh, "không cảnh báo module chiếm tài nguyên nền tảng đã giữ"
    assert "timer0" in " ".join(canh).lower()
    assert "system_timer" in " ".join(canh)


def test_module_cung_cap_KY_HIEU_cua_nen_tang_bi_canh_bao() -> None:
    from eaa.decompose import ModuleProposal, _kiem_trung_nen_tang

    m = ModuleProposal(id="main_coordinator", purpose="điều phối", provides=("main",))
    canh = _kiem_trung_nen_tang((m,), _pack())
    assert canh
    assert "main" in " ".join(canh)


def test_module_binh_thuong_KHONG_bi_canh_bao() -> None:
    """Cảnh báo bắn vào mọi trường hợp là cảnh báo bị bỏ qua."""
    from eaa.decompose import ModuleProposal, _kiem_trung_nen_tang

    m = ModuleProposal(
        id="pid_balancer", purpose="PID", provides=("pid_init", "pid_compute")
    )
    assert _kiem_trung_nen_tang((m,), _pack()) == []


def test_khong_co_pack_thi_khong_sap(monkeypatch) -> None:
    """Dự án chưa cài pack thì phân rã vẫn phải chạy, chỉ là không có phần ấy."""
    from eaa.decompose import ModuleProposal, _boi_canh_nen_tang, _kiem_trung_nen_tang

    assert _boi_canh_nen_tang(None) == ""
    assert _kiem_trung_nen_tang((ModuleProposal(id="mod_x", purpose="y"),), None) == []
