"""TC-119 — bộ đếm token không được đếm lại chính con số nó vừa ghi ra.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-155.

`spent_tokens` cộng token đã tiêu bằng cách quét `kpi_log.csv` và lấy mọi dòng
có cột token khác 0. Nhật ký có ba loại dòng CHÉP LẠI con số đã đếm::

    generate      in= 47876 out= 57509 rows=13   ← 13 lượt gọi THẬT
    gate_request  in=  3078 out=  3399 rows=1    ← chép token của artifact cuối
    module_start  in= 47006 out= 56147 rows=1    ← TỔNG tích luỹ lúc cảnh báo
    handoff       in= 97960 out=117055 rows=1    ← TỔNG tích luỹ lúc chặn

Hai dòng cuối do CHÍNH phép kiểm trần ghi ra, và giá trị của chúng là tổng mà
phép kiểm ấy vừa tính. Nên bộ đếm tự bơm chính nó: mỗi lần chạm trần lại cộng
cả tổng vào tổng.

Đo được trên `drv_imu` ngày 02/09/2026
---------------------------------------

105.385 token thật của 13 lượt gọi bị báo thành 430.030 — gấp bốn. Và con số
ấy TĂNG GẤP ĐÔI ở mỗi lần chạy bị chặn: lượt chạy 06:xx đọc 215.015, ghi một
dòng `handoff` mang đúng 215.015, và lượt sau đọc 430.030.

Vì sao đây là loại lỗi tệ nhất trong ba lỗi cùng buổi
------------------------------------------------------

Module bị khoá ở mức chưa tới 90% phần của nó, và không có đường quay lại:
càng thử càng vượt xa. Lối thoát duy nhất mà hệ thống chỉ ra — nới trần tại
G1 — là đi sửa một ràng buộc vốn đang đúng, vì một con số đo sai.

Một cái trần đúng chặn đúng lúc. Một cái trần đo sai chặn công việc đang lành,
và nó chặn theo kiểu không sửa được bằng cách làm việc cẩn thận hơn.
"""

from __future__ import annotations

import sys
from pathlib import Path

from eaa.budget import SU_KIEN_TINH_TIEN, TokenBudget, spent_tokens
from eaa.kpi import KpiLogger
from eaa.llm.mock import MockLLM


def _kpi(tmp_path: Path) -> KpiLogger:
    return KpiLogger(tmp_path / "kpi_log.csv")


def test_dong_tom_tat_cua_chinh_phep_kiem_khong_duoc_cong_lai(tmp_path: Path) -> None:
    """Chỗ SL-155 nằm."""
    kpi = _kpi(tmp_path)
    kpi.log(event="generate", module="drv_imu", tokens_in=1000, tokens_out=2000)
    kpi.log(event="generate", module="drv_imu", tokens_in=1500, tokens_out=2500)
    # Phép kiểm trần ghi lại TỔNG nó vừa tính:
    kpi.log(event="module_start", module="drv_imu", tokens_in=2500, tokens_out=4500)

    dung = spent_tokens(kpi, "drv_imu")

    assert dung.total == 7000, (
        "Dòng tóm tắt của chính phép kiểm bị cộng vào như một lượt gọi mới — "
        "bộ đếm đang tự bơm chính nó."
    )
    assert dung.calls == 2


def test_moi_lan_bi_chan_lam_con_so_tang_gap_doi(tmp_path: Path) -> None:
    """Cái ratchet: bị chặn một lần là vĩnh viễn không quay lại được."""
    kpi = _kpi(tmp_path)
    kpi.log(event="generate", module="drv_imu", tokens_in=40_000, tokens_out=60_000)
    tran = TokenBudget(per_module=120_000)

    for _ in range(3):
        kiem = tran.check(spent_tokens(kpi, "drv_imu"))
        if kiem.blocked:
            kpi.log(
                event="handoff",
                module="drv_imu",
                tokens_in=kiem.usage.tokens_in,
                tokens_out=kiem.usage.tokens_out,
            )

    dung = spent_tokens(kpi, "drv_imu")
    assert dung.total == 100_000, (
        f"Ba lượt chạy bị chặn đã tự nâng số đo lên {dung.total:,} mà không gọi "
        "mô hình lần nào."
    )
    assert not tran.check(dung).blocked


def test_gate_request_chep_lai_token_cua_artifact_cuoi(tmp_path: Path) -> None:
    """Hồ sơ gate mang token của artifact để truy vết — cùng lượt gọi, không phải lượt mới."""
    kpi = _kpi(tmp_path)
    kpi.log(event="generate", module="drv_imu", tokens_in=3078, tokens_out=3399)
    kpi.log(event="gate_request", module="drv_imu", tokens_in=3078, tokens_out=3399)

    dung = spent_tokens(kpi, "drv_imu")
    assert dung.total == 6477
    assert dung.calls == 1


def test_luot_xem_truoc_van_duoc_tinh_tien(tmp_path: Path) -> None:
    """`eaa gen --preview` KHÔNG chạy cổng, nhưng nó có gọi mô hình.

    Bỏ sót nó là mở một lối tiêu tiền không ai đếm — đúng loại lỗ mà cái trần
    này sinh ra để bịt.
    """
    kpi = _kpi(tmp_path)
    kpi.log(event="preview", module="drv_imu", tokens_in=3000, tokens_out=4000)

    dung = spent_tokens(kpi, "drv_imu")
    assert dung.total == 7000
    assert dung.calls == 1


def test_vong_va_cung_phai_ghi_token(tmp_path: Path) -> None:
    """Chiều ngược của cùng một lỗi: đếm SÓT, và im lặng hơn nhiều.

    Trước khi sửa, chỉ lượt sinh ĐẦU ghi token vào KPI; mỗi vòng vá gọi mô
    hình rồi không ghi gì. Đo được trên `drv_imu`: 26 lượt gọi trong
    `llm_calls.jsonl`, 13 dòng trong `kpi_log.csv`.

    Một cái trần chỉ đếm được nửa số tiền tiêu ra là một cái trần không bảo vệ
    được gì — và chính vòng tự sửa mới là chỗ tiền chảy nhanh nhất.
    """
    assert "repair" in SU_KIEN_TINH_TIEN

    kpi = _kpi(tmp_path)
    kpi.log(event="generate", module="drv_imu", tokens_in=3000, tokens_out=4000)
    # Dòng `repair` mở vòng, ghi TRƯỚC lượt gọi nên chưa có token:
    kpi.log(event="repair", module="drv_imu", retries=1, result="fail")
    # Dòng `repair` của chính lượt gọi:
    kpi.log(event="repair", module="drv_imu", tokens_in=2000, tokens_out=2500)

    dung = spent_tokens(kpi, "drv_imu")
    assert dung.total == 11_500
    assert dung.calls == 2, "dòng mở vòng không mang token thì không phải một lượt gọi"


def test_so_do_cua_bo_dem_bang_so_mo_hinh_that_su_tra_ve(tmp_path: Path) -> None:
    """Bất biến gốc, đo bằng một lượt chạy thật thay vì bằng cách đọc mã.

    Vòng lặp chuẩn chạy trọn: một lượt sinh đầu + ba vòng vá = bốn lượt gọi.
    Số bộ đếm đọc ra phải bằng đúng tổng token bốn lượt ấy — không hơn (SL-155
    chiều thổi phồng), không kém (chiều đếm sót).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from test_tc06_orchestrator import MA_HONG_BIEN_DICH, Duan
    finally:
        sys.path.pop(0)

    du_an = Duan(tmp_path, llm=MockLLM(responses=MA_HONG_BIEN_DICH))
    that = []
    goc = du_an.llm.generate

    def _ghi(prompt):  # noqa: ANN001, ANN202
        artifact = goc(prompt)
        that.append(artifact.tokens_in + artifact.tokens_out)
        return artifact

    du_an.llm.generate = _ghi  # type: ignore[method-assign]
    du_an.orch.run_module("drv_bus_sensor")

    assert len(that) == 4, "một lượt sinh đầu + ba vòng vá"
    dung = spent_tokens(du_an.kpi, "drv_bus_sensor")

    assert dung.total == sum(that), (
        f"Bộ đếm đọc {dung.total:,} token trong khi mô hình trả về {sum(that):,}. "
        "Số đo của cái trần phải dựng lại được từ chính các lượt gọi."
    )
    assert dung.calls == 4


def test_dong_khong_phai_luot_goi_khong_lam_doi_so_do(tmp_path: Path) -> None:
    """Luật mới không được làm mất token của những lượt gọi thật."""
    kpi = _kpi(tmp_path)
    kpi.log(event="generate", module="drv_bus", tokens_in=1000, tokens_out=300)
    kpi.log(event="merge", module="drv_bus", result="pass")
    kpi.log(event="repair", module="drv_bus", retries=1)

    dung = spent_tokens(kpi, "drv_bus")
    assert (dung.tokens_in, dung.tokens_out, dung.calls) == (1000, 300, 1)
