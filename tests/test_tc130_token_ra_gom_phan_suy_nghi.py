"""TC-130 — token RA phải gồm cả phần SUY NGHĨ, và mặc định là Flash 3.8 (SL-170).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-170.

Chỗ hỏng, và vì sao nó chỉ lộ ra khi đổi model
-----------------------------------------------

`GeminiClient` đọc `tokens_out` từ `candidatesTokenCount` — số token của phần
CHỮ trả về. Với model có tầng suy nghĩ, nhà cung cấp trả thêm
`thoughtsTokenCount`, và phần ấy **vẫn được tính tiền, vẫn ăn vào trần
`maxOutputTokens`**.

Đo thật ngày 04/09/2026 khi đổi sang `gemini-3.8-flash`: một lượt gọi trả về
đúng chữ "OK" báo `candidatesTokenCount = 1`, `thoughtsTokenCount = 92`. Đếm
thiếu 92 trên 93 phần — ở đúng chỗ đang làm dữ liệu gốc cho chương đánh giá và
cho `TokenBudget` (N-904).

Với Pro 3.1 chỗ này không sai rõ như vậy, nên nó sống được cho tới lần đổi
model. Đây là hạng lỗi mà kho này gọi tên nhiều lần: **đúng cho tới khi một
giả định lặng lẽ đổi.**

Bài này cũng canh chiều ngược: model KHÔNG có tầng suy nghĩ thì hành vi cũ
không được đổi một ly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.llm import catalog
from eaa.llm.base import Prompt, PromptLayer
from eaa.llm.calllog import CallLog
from eaa.llm.gemini import API_KEY_ENV, DEFAULT_MODEL, GeminiClient

KHOA_GIA = "AIzaSyKHOA-GIA-KHONG-DUOC-LO-RA-DAU-CA-1234567"

#: Adapter đòi phản hồi có khối ```file:<đường dẫn>; bài này đo SỐ TOKEN chứ
#: không đo bộ bóc tệp, nên nó dùng một khối hợp lệ tối thiểu.
MA_TRA_VE = """```file:src/m.c
#include "m.h"

// ref: ds-021
void m_init(void)
{
    static uint8_t n;
    n = 0u;
}
```
"""


def _prompt() -> Prompt:
    return Prompt(
        system_instruction="Bạn là kỹ sư firmware.",
        layers=[PromptLayer("task", "Viết module.", budget=500, required=True)],
        module="drv_bus_sensor",
        constraints_version="sha256:ab12",
        chunk_ids=("ds-021",),
    )


class MangGia:
    """Trả một phản hồi dựng sẵn; `countTokens` đếm theo độ dài thật."""

    def __init__(self, usage: dict | None, van_ban: str = MA_TRA_VE) -> None:
        self.usage = usage
        self.van_ban = van_ban

    def __call__(self, url: str, than: bytes, api_key: str, timeout: float):
        if "countTokens" in url:
            noi_dung = json.loads(than.decode("utf-8")).get("contents", [])
            chu = "".join(
                p.get("text", "") for c in noi_dung for p in c.get("parts", [])
            )
            return {"totalTokens": max(1, len(chu) // 4)}
        phan_hoi: dict = {
            "candidates": [
                {"content": {"parts": [{"text": self.van_ban}]}, "finishReason": "STOP"}
            ]
        }
        if self.usage is not None:
            phan_hoi["usageMetadata"] = self.usage
        return phan_hoi


@pytest.fixture()
def co_khoa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, KHOA_GIA)


# -- token ra ----------------------------------------------------------------


def test_cong_phan_suy_nghi_vao_token_ra(co_khoa) -> None:
    """Đúng con số đo được trên gemini-3.8-flash ngày 04/09."""
    client = GeminiClient(
        transport=MangGia({"promptTokenCount": 7, "candidatesTokenCount": 1,
                           "thoughtsTokenCount": 92})
    )
    ket_qua = client.generate(_prompt())
    assert ket_qua.tokens_out == 93, "đếm thiếu 92/93 phần token thật sự sinh ra"
    assert ket_qua.tokens_in == 7


def test_model_KHONG_co_tang_suy_nghi_giu_nguyen_hanh_vi_cu(co_khoa) -> None:
    """Chiều ngược: thêm một phép cộng không được đổi số của model cũ."""
    client = GeminiClient(
        transport=MangGia({"promptTokenCount": 1234, "candidatesTokenCount": 88})
    )
    assert client.generate(_prompt()).tokens_out == 88


def test_phan_suy_nghi_bang_khong_thi_khong_doi_gi(co_khoa) -> None:
    client = GeminiClient(
        transport=MangGia({"promptTokenCount": 10, "candidatesTokenCount": 40,
                           "thoughtsTokenCount": 0})
    )
    assert client.generate(_prompt()).tokens_out == 40


def test_khong_co_usage_thi_van_uoc_luong_chu_khong_tra_ve_khong(co_khoa) -> None:
    """Trả 0 sẽ làm `TokenBudget` tin rằng lượt gọi ấy miễn phí."""
    client = GeminiClient(transport=MangGia(None))
    assert client.generate(_prompt()).tokens_out > 0


def test_usage_toan_so_khong_cung_lui_ve_uoc_luong(co_khoa) -> None:
    client = GeminiClient(
        transport=MangGia({"candidatesTokenCount": 0, "thoughtsTokenCount": 0})
    )
    assert client.generate(_prompt()).tokens_out > 0


def test_so_da_cong_di_thang_vao_nhat_ky_bang_chung(co_khoa, tmp_path: Path) -> None:
    """Nhật ký lời gọi là dữ liệu gốc của chương đánh giá — nó phải mang số đúng."""
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    client = GeminiClient(
        transport=MangGia({"promptTokenCount": 7, "candidatesTokenCount": 1,
                           "thoughtsTokenCount": 92}),
        call_log=nhat_ky,
    )
    client.generate(_prompt())
    assert nhat_ky.summary()["tokens_out_total"] == 93


# -- danh mục và mặc định ----------------------------------------------------


def test_mac_dinh_la_flash_38() -> None:
    assert DEFAULT_MODEL == "gemini-3.8-flash"


def test_mac_dinh_phai_nam_trong_danh_muc_da_kiem() -> None:
    """Mặc định của sản phẩm là chỗ ít được phép 'chưa kiểm' nhất."""
    assert catalog.get(DEFAULT_MODEL) is not None


def test_muc_danh_muc_mang_dung_so_do_that() -> None:
    """Số lấy từ ListModels ngày 04/09/2026, không phải chép từ model khác."""
    m = catalog.get("gemini-3.8-flash")
    assert m.display == "Gemini 3.8 Flash"
    assert m.input_limit == 1_048_576
    assert m.output_limit == 65_536
    assert m.verified_on == "2026-09-04"


def test_ghi_chu_canh_bao_ve_tang_suy_nghi() -> None:
    """Người đọc phải biết trần đầu ra bị phần suy nghĩ ăn vào."""
    assert "SUY NGHĨ" in catalog.get("gemini-3.8-flash").note


def test_ghi_chu_KHONG_khai_la_da_do_A_B_voi_Pro() -> None:
    """Chưa có số thì không được nói cái nào sinh mã tốt hơn."""
    assert "CHƯA đo A/B" in catalog.get("gemini-3.8-flash").note


def test_Pro_31_van_con_trong_danh_muc() -> None:
    """Mọi số liệu Chương 3 đứng trên nó — bỏ đi là bỏ đường dựng lại."""
    m = catalog.get("gemini-3.1-pro-preview")
    assert m is not None
    assert "Chương 3" in m.note
    assert catalog.khuyen_nghi("dựng lại số liệu Chương 3") == "gemini-3.1-pro-preview"
