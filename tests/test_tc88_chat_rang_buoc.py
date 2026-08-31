"""TC-88 — ràng buộc cứng phải vào MỌI lời gọi mô hình, kể cả hội thoại.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-112.

Tìm ra ở Bài 1 của phiên kiểm với bo thật. Người dùng giao: *"kiểm kênh UART
giữa máy tính và bo, viết mã, nạp, chạy thử, cho tôi kết quả"*. Agent trả lời
bằng một đoạn mã Arduino:

    void setup() { Serial.begin(9600); }
    void loop() { Serial.println("UART OK"); delay(1000); }

Ba chỗ sai, và cả ba đều là hệ quả của cùng một chỗ hở trong cấu trúc:

* `delay()` nằm trong danh sách **cấm** của chính dự án này.
* `Serial.println` là I/O chặn — cũng cấm (`blocking_io`).
* `9600` trái với `115200` mà hồ sơ phần cứng khai.

CLAUDE.md và FR-KB-01 nói ràng buộc cứng "được bảng hóa và nạp vào **100% lần
gọi LLM**". TC-04 canh điều đó — nhưng chỉ canh `PromptComposer`, tức đường
sinh mã. `eaa chat` dựng prompt riêng của nó, và lớp ràng buộc **không có ở
đó**. Bất biến được cưỡng chế trên một đường, và bỏ trống trên đúng đường mà
người dùng nói chuyện với hệ thống.

Bài này canh chỗ hở ấy ở mức CẤU TRÚC: không hỏi "mô hình có ngoan không" mà
hỏi "ràng buộc có trong prompt không".
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    """Một dự án tối thiểu có ràng buộc cứng và một điều cấm nhận ra được."""
    d = tmp_path / "du_an"
    d.mkdir()
    (d / "constraints.yaml").write_text(
        "version: 1\n"
        "platform: avr\n"
        "mcu: atmega328p\n"
        "forbidden:\n"
        "  - delay()\n"
        "  - blocking_io\n"
        "  - malloc/new\n"
        "style:\n"
        "  arithmetic: integer\n",
        encoding="utf-8",
    )
    (d / "project_state.json").write_text(
        '{"phase": "A", "gates": {}, "backlog": []}', encoding="utf-8"
    )
    return d


class _LlmGhiPrompt:
    """Không trả lời gì có nghĩa — chỉ giữ lại prompt đã nhận."""

    def __init__(self) -> None:
        self.prompts: list = []

    def count_tokens(self, s: str) -> int:
        return len(s.split())

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return '{"hanh_dong": "tra_loi", "noi_dung": "xong"}'


def _vong(du_an: Path, llm):
    from eaa.agent import AgentLoop

    return AgentLoop(project=du_an, llm=llm)


# ═══════════ ràng buộc phải CÓ MẶT trong prompt hội thoại ═══════════


def test_prompt_hoi_thoai_CO_rang_buoc_cung(du_an: Path) -> None:
    """Bất biến trung tâm: 100% lời gọi mô hình mang theo ràng buộc.

    "100%" phải nghĩa là 100%. Cưỡng chế trên đường sinh mã rồi bỏ trống đường
    hội thoại thì con số ấy là một lời khai sai — và nó sai ở đúng chỗ người
    dùng gõ câu hỏi vào.
    """
    llm = _LlmGhiPrompt()
    _vong(du_an, llm).ask("viết hộ tôi đoạn mã kiểm UART")

    assert llm.prompts, "không gọi mô hình lần nào"
    van_ban = llm.prompts[0].render()
    assert "delay()" in van_ban, "điều cấm của dự án không vào tới prompt"
    assert "blocking_io" in van_ban
    assert "atmega328p" in van_ban or "avr" in van_ban


def test_lop_rang_buoc_la_BAT_BUOC_khong_bi_cat(du_an: Path) -> None:
    """Cắt cho vừa ngân sách thì cắt cái khác — không cắt ràng buộc.

    Lớp ràng buộc bị cắt lặng lẽ là hỏng đúng theo kiểu nguy nhất: prompt vẫn
    gửi đi, mô hình vẫn trả lời, và không ai biết luật đã rơi mất.
    """
    llm = _LlmGhiPrompt()
    _vong(du_an, llm).ask("hỏi gì đó")
    lop = {l.name: l for l in llm.prompts[0].layers}
    assert "constraints" in lop, "không có lớp ràng buộc"
    assert lop["constraints"].required is True


def test_du_an_khong_co_rang_buoc_thi_NOI_RA(tmp_path: Path) -> None:
    """Thiếu ràng buộc là một sự kiện đáng nói, không phải một lớp rỗng im lặng."""
    d = tmp_path / "trong"
    d.mkdir()
    llm = _LlmGhiPrompt()
    _vong(d, llm).ask("hỏi gì đó")
    van_ban = llm.prompts[0].render().lower()
    assert "ràng buộc" in van_ban
    assert any(x in van_ban for x in ("chưa có ràng buộc", "không đọc được ràng buộc")), \
        "thiếu ràng buộc phải là một câu nói ra, không phải một lớp rỗng"
    assert "đừng" in van_ban, "phải dặn mô hình đừng đề xuất mã khi chưa biết luật"


# ═══════════ nói được AI chạy lệnh mình không có ═══════════


def test_lenh_ngoai_danh_muc_kem_LY_DO_va_AI_CHAY() -> None:
    """Danh sách trần tên lệnh đẩy mô hình đi tìm công cụ NGOÀI sản phẩm.

    Tìm ra cùng lúc: được hỏi việc lõi của chính sản phẩm, Agent đề xuất
    `arduino-cli` và Arduino IDE — một quy trình không nằm trong dự án, không
    có trong manifest, và sinh ra mã vi phạm ràng buộc của dự án.

    Nguyên nhân nằm ở prompt: nó chỉ nói *"KHÔNG có: build, gen, flash…"* —
    một danh sách tên trần. Mô hình đọc thành *"sản phẩm này không làm được
    việc đó"*, rồi đi tìm chỗ khác. Sự thật là ngược lại: những lệnh ấy TỒN
    TẠI và mạnh, chỉ là **người** gõ chúng.

    Lời giải thích cho từng lệnh đã được viết sẵn trong `NGOAI_DANH_MUC` —
    lại một chỗ mã đúng nằm chết vì không có đường tới nơi cần nó.
    """
    from eaa.agent import _mo_ta_danh_muc

    van_ban = _mo_ta_danh_muc()
    for lenh in ("gen", "build", "flash"):
        assert lenh in van_ban, f"không nhắc tới {lenh}"
    assert "người" in van_ban.lower(), "không nói ai là người chạy chúng"
    # Phải mời gọi ĐỀ NGHỊ người chạy, chứ không phải chỉ cấm.
    assert "đề nghị" in van_ban.lower() or "bạn gõ" in van_ban.lower()


def test_khong_duoc_bia_cong_cu_ngoai_san_pham() -> None:
    """Prompt phải nói thẳng: đường đi nằm TRONG sản phẩm này."""
    from eaa.agent import _mo_ta_danh_muc

    van_ban = _mo_ta_danh_muc().lower()
    assert "eaa" in van_ban
    assert "ngoài sản phẩm" in van_ban or "công cụ khác" in van_ban


# ═══════════ canh cấu trúc: không đường nào gọi mô hình mà thiếu ràng buộc ═══════════


def test_moi_cho_dung_Prompt_deu_phai_co_lop_rang_buoc() -> None:
    """Bài canh dạng TC-38: quét mã nguồn, không tin lời hứa.

    Một bất biến nói "100% lần gọi" chỉ đúng khi có thứ gì đó đếm được cả 100%.
    Bài này liệt kê những chỗ dựng `Prompt(` trong engine và đòi mỗi chỗ hoặc
    có lớp tên `constraints`, hoặc nằm trong danh sách miễn trừ có ghi lý do.
    """
    import re

    # Miễn trừ, kèm lý do — sửa danh sách này là một quyết định, không phải một
    # thao tác dọn dẹp.
    MIEN_TRU = {
        # Không thuộc một dự án nào nên không có ràng buộc để nạp.
        "eaa/toolsearch.py": "tra cứu công cụ — không gắn với dự án",
        "eaa/gapsearch.py": "tra cứu tri thức thiếu — chạy trước khi có dự án",
        "eaa/ingest.py": "thu nhận đầu vào thô, chưa vào vòng sinh mã",
        "eaa/docplan.py": "dựng tài liệu, không sinh mã cho thiết bị",
        "eaa/designdoc.py": "dựng tài liệu, không sinh mã cho thiết bị",
        "eaa/decompose.py": "chia nhỏ yêu cầu, chưa chạm thanh ghi",
        "eaa/brief.py": "phỏng vấn dựng hồ sơ — ràng buộc chưa tồn tại",
        "eaa/toolforge.py": "sinh công cụ chạy trên máy chủ, không phải firmware",
        "eaa/skills.py": "rút kỹ năng từ lệnh đã chạy",
        "eaa/diagnostics.py": "chẩn đoán, đọc số đo",
        "eaa/suggest.py": "gợi ý bước kế, không sinh mã",
        "eaa/propose.py": "đề xuất ràng buộc — chính nó sinh ra ràng buộc",
        "eaa/research.py": "tra cứu ngoài web",
        "eaa/memory.py": "trí nhớ dự án",
        "eaa/field.py": "phân tích sự cố hiện trường",
        "eaa/debugsession.py": "phiên gỡ lỗi, đọc số đo",
        "eaa/handover.py": "tài liệu vận hành, không sinh mã cho thiết bị",
        "eaa/options.py": "trình phương án cho người chọn",
        "eaa/registry.py": "kho phẩm xuất — quản lý tệp đã sinh, không sinh mã",
        "eaa/safety.py": "phân tích hỏng hóc, sinh văn xuôi",
        # CÒN NGỜ, cố ý ghi ra thay vì lặng lẽ bỏ qua: nó sinh CHỮ KÝ HÀM cho
        # firmware, và đã nhận `constraints.limits` — nhưng KHÔNG nhận danh
        # sách `forbidden`. Chữ ký chưa phải thân hàm, nên chưa xếp là lỗi;
        # nhưng "hàm này có chặn không" là câu hỏi mà `blocking_io` nói thẳng.
        # Xem SL-112, mục còn treo.
        "eaa/interfaces.py": "sinh chữ ký hàm; đã nhận limits, chưa nhận forbidden",
    }

    thieu = []
    for tep in sorted((REPO / "eaa").rglob("*.py")):
        ten = str(tep.relative_to(REPO))
        nguon = tep.read_text(encoding="utf-8")
        if "Prompt(" not in nguon:
            continue
        if ten in MIEN_TRU:
            continue
        # Chấp cả hai cách mang ràng buộc vào prompt: một lớp tên
        # ``constraints``, hoặc bảng K1 ``_bang_rang_buoc`` đặt trong
        # ``system_instruction`` (cách ``composer.py`` dùng).
        if 'PromptLayer("constraints"' in nguon or "_bang_rang_buoc" in nguon:
            continue
        thieu.append(ten)

    assert not thieu, (
        "Những tệp này dựng Prompt mà không có lớp ràng buộc, và cũng không "
        f"nằm trong danh sách miễn trừ có ghi lý do: {thieu}. "
        "Ràng buộc cứng phải vào 100% lần gọi mô hình (FR-KB-01) — hoặc thêm "
        "lớp, hoặc ghi rõ vì sao chỗ này không cần."
    )
