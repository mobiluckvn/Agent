"""Chốt an toàn cho toàn bộ bộ test — không lời gọi API thật nào lọt qua.

Từ lúc ``eaa init`` biết tự nhìn môi trường (thấy ``EAA_LLM_KEY`` thì chọn mô
hình thật), bộ test có một rủi ro mới: máy của người phát triển có tệp ``.env``
với khóa thật, CLI nạp tệp ấy lúc khởi động, nên một bài test gọi ``eaa init``
rồi ``eaa gen`` sẽ lặng lẽ gọi API — tốn tiền, chậm, và tệ nhất là **kết quả
test phụ thuộc vào mạng và vào phản hồi của một mô hình**, tức là không còn tất
định.

Chốt ở đây xóa khóa khỏi môi trường của MỌI bài test. Bài nào thật sự cần mô
hình thật phải tự đặt lại khóa và nói rõ mình đang làm vậy — biến một thứ có
thể xảy ra do sơ ý thành một thứ phải viết ra mới xảy ra được.

Đây là cùng một nguyên tắc mà sản phẩm áp cho người dùng: một phiên không có
người không được diễn giải thành một người đã đồng ý. Ở đây: một máy tình cờ
có khóa không được diễn giải thành một bài test muốn gọi API.
"""

from __future__ import annotations

import pytest

from eaa.llm.base import KEY_ENV


@pytest.fixture(autouse=True)
def khong_goi_api_that(monkeypatch: pytest.MonkeyPatch) -> None:
    """Xóa khóa API khỏi môi trường của mọi bài test."""
    monkeypatch.delenv(KEY_ENV, raising=False)


@pytest.fixture(autouse=True)
def khong_cham_mang(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chặn mọi lượt gọi mạng trong bộ test.

    Chốt thứ nhất (xóa khóa) chỉ đúng khi bài test đặt ``EAA_HOME`` sang thư
    mục tạm — vì lúc ấy CLI không tìm thấy tệp ``.env`` nào để nạp lại khóa.
    Đó là một điều kiện ngầm, và một chốt an toàn phụ thuộc điều kiện ngầm thì
    sẽ hỏng lặng lẽ vào ngày ai đó thêm một bài test không đặt biến ấy.

    Chốt này không phụ thuộc gì: adapter mô hình đi ra ngoài bằng ``urlopen``,
    nên chặn đúng chỗ đó là chặn được mọi đường. Bài nào cần transport giả thì
    tiêm vào adapter như TC-11 vẫn làm — đường ấy không đi qua đây.
    """
    import urllib.request

    def _chan(*args, **kwargs):
        raise AssertionError(
            "Một bài test vừa cố gọi mạng thật. Bộ test phải tất định và chạy "
            "được khi không có mạng — dùng transport giả (TC-11) hoặc "
            "ReplayClient (TC-15) thay vì gọi ra ngoài."
        )

    monkeypatch.setattr(urllib.request, "urlopen", _chan)


@pytest.fixture(autouse=True)
def moi_truong_mang_xac_dinh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Xóa công tắc ngắt mạng khỏi môi trường của mọi bài test.

    Cùng lý do với chốt phía trên, chỉ ngược chiều. ``EAA_NO_NET=1`` trong
    shell của người phát triển làm 34 bài test về lớp truy cập mạng đổi kết
    quả — chúng tiêm lớp vận chuyển giả nên không hề chạm mạng, nhưng công tắc
    ngắt bắn TRƯỚC lớp ấy và chúng thất bại vì một lý do không liên quan gì tới
    thứ chúng kiểm.

    Bài nào cần kiểm chính công tắc thì tự bật lại bằng ``monkeypatch.setenv``
    — và như thế nó nói rõ mình đang kiểm cái gì.
    """
    monkeypatch.delenv("EAA_NO_NET", raising=False)
