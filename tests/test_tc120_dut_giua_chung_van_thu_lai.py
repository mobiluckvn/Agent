"""TC-120 — kết nối đứt giữa chừng phải được thử lại như mọi lỗi mạng khác.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-156.

Ngày 02/09/2026, một lượt `eaa gen drv_imu` chết bằng đúng một dòng::

    Không lắp ráp hoặc không sinh được mã: IncompleteRead(0 bytes read)

Vòng thử lại của adapter phủ ba nhánh: `HTTPError` (máy chủ bảo thử lại),
`URLError` (không nối được), `TimeoutError` (chờ quá lâu). `IncompleteRead`
không thuộc nhánh nào: nó là `http.client.HTTPException`, không phải lỗi của
`urllib`.

Nên vòng thử lại bỏ trống đúng cái hay xảy ra nhất với một lượt gọi dài — nối
được, gửi được, rồi đường truyền chết khi câu trả lời đang về.

Vì sao thử lại là đúng dù mỗi lượt gọi đều tính tiền
-----------------------------------------------------

Phản hồi đã đứt thì không còn gì dùng được: lượt gọi ấy đã mất tiền rồi, và
không thử lại chỉ đổi "mất một lượt" thành "mất một lượt VÀ hỏng cả lượt chạy".
"""

from __future__ import annotations

import http.client
import json

import pytest

from eaa.llm.base import Prompt, PromptLayer
from eaa.llm.gemini import API_KEY_ENV, GeminiClient, GeminiError

KHOA_GIA = "AIzaSyKHOA-BI-MAT-KHONG-DUOC-LO-RA-DAU-CA-123456"

MA_TRA_VE = """```file:src/m.c
void m_init(void) {}
```
"""


def _prompt() -> Prompt:
    return Prompt(
        layers=[PromptLayer(name="task", content="viết m_init")],
        system_instruction="bạn là kỹ sư nhúng",
    )


def _phan_hoi() -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": MA_TRA_VE}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
    }


class DutRoiLanh:
    """Đứt ``so_lan_dut`` lần đầu, rồi trả lời bình thường."""

    def __init__(self, loi: Exception, so_lan_dut: int) -> None:
        self.loi = loi
        self.so_lan_dut = so_lan_dut
        self.luot = 0

    def __call__(self, url: str, than: bytes, api_key: str, timeout: float):
        if "countTokens" in url:
            van_ban = "".join(
                p.get("text", "")
                for c in json.loads(than.decode("utf-8")).get("contents", [])
                for p in c.get("parts", [])
            )
            return {"totalTokens": max(1, len(van_ban) // 4)}
        self.luot += 1
        if self.luot <= self.so_lan_dut:
            raise self.loi
        return _phan_hoi()


@pytest.fixture()
def co_khoa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(API_KEY_ENV, KHOA_GIA)


LOI_DUT = (
    pytest.param(http.client.IncompleteRead(b""), id="IncompleteRead"),
    pytest.param(http.client.RemoteDisconnected("máy chủ đóng kết nối"), id="RemoteDisconnected"),
    pytest.param(ConnectionResetError(54, "Connection reset by peer"), id="ConnectionReset"),
)


@pytest.mark.parametrize("loi", LOI_DUT)
def test_dut_mot_lan_thi_thu_lai_va_di_tiep(co_khoa, loi: Exception) -> None:
    """Chỗ SL-156 nằm: trước khi sửa, lượt chạy chết ngay ở đây."""
    mang = DutRoiLanh(loi, so_lan_dut=1)
    client = GeminiClient(transport=mang, backoff_s=0)

    artifact = client.generate(_prompt())

    assert "src/m.c" in artifact.files
    assert mang.luot == 2, "phải gọi lại đúng một lần sau khi đứt"


@pytest.mark.parametrize("loi", LOI_DUT)
def test_dut_qua_so_lan_thu_lai_thi_bao_loi_ro_rang(co_khoa, loi: Exception) -> None:
    """Thử lại không phải thử mãi — hết lượt thì nói ra, và nói đúng chuyện gì."""
    mang = DutRoiLanh(loi, so_lan_dut=99)
    client = GeminiClient(transport=mang, max_retries=2, backoff_s=0)

    with pytest.raises(GeminiError, match="đứt giữa chừng"):
        client.generate(_prompt())

    assert mang.luot == 3, "một lượt đầu + đúng hai lượt thử lại"


def test_khoa_khong_lot_ra_trong_thong_bao_dut(co_khoa) -> None:
    """NFR-06 không có ngoại lệ cho nhánh lỗi mới."""
    mang = DutRoiLanh(
        http.client.IncompleteRead(f"đang tải ?key={KHOA_GIA}".encode()), so_lan_dut=99
    )
    client = GeminiClient(transport=mang, max_retries=0, backoff_s=0)

    with pytest.raises(GeminiError) as thong_tin:
        client.generate(_prompt())

    assert KHOA_GIA not in str(thong_tin.value)
