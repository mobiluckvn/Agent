"""Danh mục model — để NGƯỜI chọn, không để hệ tự chọn.

EAA-AIS-05 §2 (cấu hình mô hình); ADR-03; NFR-04.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-103.

Vì sao có module này
---------------------

Trước đây mã model là một chuỗi mặc định trong ``eaa/llm/gemini.py`` và một cờ
``eaa init --model <chuỗi>``. Nó chạy được, nhưng nó đòi người dùng **thuộc
lòng chuỗi của nhà cung cấp** — ``gemini-3.5-flash`` hay ``gemini-3-5-flash``
hay ``gemini-flash-3.5``? Gõ sai thì lỗi hiện ra lúc gọi API, sau khi đã dựng
xong ngữ cảnh.

Danh mục này biến chuỗi ấy thành một **lựa chọn nhìn thấy được**: ``eaa models``
in ra những mã đã kiểm, kèm chỗ mạnh chỗ yếu của từng cái, và người dùng chọn.

Điều module này CỐ Ý KHÔNG làm: tự chọn model
----------------------------------------------

Cám dỗ rõ ràng là "việc nhẹ thì Flash, việc nặng thì Pro" — hệ tự đoán loại
việc rồi tự đổi model. Nó **không có ở đây**, và đó là một quyết định chứ
không phải một chỗ chưa làm:

* Chi phí và chất lượng là đánh đổi của **người trả tiền**, không phải của
  công cụ. Một người đang chạy thí nghiệm cho luận văn có thể muốn Pro cho
  MỌI lượt gọi để số liệu so sánh được với nhau; một người đang thử nghiệm
  nhanh có thể muốn Flash cho tất cả.
* Tự đổi model giữa chừng **phá hỏng tính tái lập** (rủi ro R1, EAA-STP-04):
  hai lần chạy cùng một lệnh có thể rơi vào hai model khác nhau, và lúc kết
  quả lệch thì không biết lệch vì model hay vì đầu vào.
* Một cơ chế tự chọn sai thì người dùng **không thấy nó sai** — họ chỉ thấy
  câu trả lời tệ hơn, và đi tìm nguyên nhân ở chỗ khác.

Nên: mặc định ghim trong Project State, và người dùng đổi được **tại chỗ dùng**
bằng cờ ``--model``. Hệ không bao giờ tự đổi.

Danh mục này là gợi ý, không phải hàng rào
-------------------------------------------

``eaa init --model <chuỗi bất kỳ>`` vẫn nhận mã ngoài danh mục — nhà cung cấp
ra model mới nhanh hơn tài liệu này được cập nhật, và một danh sách trắng cứng
sẽ chặn đúng thứ người dùng cần. Ngoài danh mục thì hệ nói "chưa kiểm" và chạy
tiếp; nó không từ chối.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ModelInfo", "CATALOG", "get", "khuyen_nghi", "render_catalog"]


@dataclass(frozen=True)
class ModelInfo:
    """Một mã model đã được kiểm với API nhà cung cấp."""

    id: str
    provider: str
    display: str
    #: Trần token vào/ra do nhà cung cấp khai. Ghi lại để đối chiếu — hệ vẫn
    #: hỏi model thật lúc chạy chứ không tin con số này.
    input_limit: int
    output_limit: int
    #: Một câu: mạnh ở đâu, yếu ở đâu. Đây là phần người dùng thật sự đọc.
    note: str
    #: Ngày kiểm mã này với API. Danh mục là ảnh chụp, và ảnh chụp thì cũ đi.
    verified_on: str = ""


#: Đã kiểm bằng ListModels + một lượt generateContent thật. Ngày kiểm ghi ở
#: từng mục, vì chúng không được kiểm cùng một ngày.
CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="gemini-3.8-flash",
        provider="gemini",
        display="Gemini 3.8 Flash",
        input_limit=1_048_576,
        output_limit=65_536,
        note="MẶC ĐỊNH của sản phẩm từ 04/09/2026. Thế hệ mới hơn Pro 3.1 và "
             "nhanh hơn hẳn. CÓ TẦNG SUY NGHĨ: một lượt trả về đúng chữ 'OK' "
             "vẫn tiêu 92 token suy nghĩ, nên trần `maxOutputTokens` phải nới "
             "rộng hơn độ dài câu trả lời mong đợi. Dự án CHƯA đo A/B nó với "
             "Pro 3.1 trên việc sinh mã nhúng — chưa có số thì chưa nói được "
             "cái nào sinh mã tốt hơn.",
        verified_on="2026-09-04",
    ),
    ModelInfo(
        id="gemini-3.1-pro-preview",
        provider="gemini",
        display="Gemini 3.1 Pro Preview",
        input_limit=1_048_576,
        output_limit=65_536,
        note="Lớp suy luận. LÀ MẶC ĐỊNH CHO TỚI 04/09/2026, và là model đã sinh "
             "toàn bộ firmware chạy được trên bo thật — mọi số liệu Chương 3 "
             "đứng trên nó. Chậm hơn Flash rõ rệt ở những lượt gọi ngắn.",
        verified_on="2026-08-31",
    ),
    ModelInfo(
        id="gemini-3.5-flash",
        provider="gemini",
        display="Gemini 3.5 Flash",
        input_limit=1_048_576,
        output_limit=65_536,
        note="Nhanh và rẻ hơn Pro, cùng trần ngữ cảnh 1M. Hợp cho hội thoại, tra "
             "cứu công cụ, tóm tắt tài liệu — những việc mà một câu trả lời hơi "
             "kém vẫn sửa được bằng một câu hỏi nữa.",
        verified_on="2026-08-31",
    ),
    ModelInfo(
        id="gemini-3.5-flash-lite",
        provider="gemini",
        display="Gemini 3.5 Flash Lite",
        input_limit=1_048_576,
        output_limit=65_536,
        note="Rẻ nhất. Dùng khi chạy hàng loạt lượt gọi ngắn và tự kiểm được kết "
             "quả — KHÔNG khuyến nghị cho sinh mã.",
        verified_on="2026-08-31",
    ),
    ModelInfo(
        id="mock-deterministic-1",
        provider="mock",
        display="MockLLM (tất định, không gọi mạng)",
        input_limit=0,
        output_limit=0,
        note="Không phải model thật. Trả lời tất định theo mẫu, dùng cho kiểm thử "
             "và cho Sprint 1–3. Không tốn API, không cần khóa.",
        verified_on="2026-08-31",
    ),
)

#: Model khuyến nghị theo loại việc. Đây là LỜI KHUYÊN in ra cho người đọc,
#: KHÔNG phải bảng tra để hệ tự chọn — không có mã nào đọc dict này để quyết
#: định. Nếu một ngày có, thì mục đích của module này đã bị lật ngược.
KHUYEN_NGHI: dict[str, str] = {
    "sinh mã nhúng": "gemini-3.8-flash",
    "hội thoại, tra cứu, tóm tắt": "gemini-3.8-flash",
    "dựng lại số liệu Chương 3": "gemini-3.1-pro-preview",
    "kiểm thử / phát triển ngoại tuyến": "mock-deterministic-1",
}


def get(model_id: str) -> ModelInfo | None:
    """Tra một mã trong danh mục. ``None`` nghĩa là chưa kiểm, không phải sai."""
    for m in CATALOG:
        if m.id == model_id:
            return m
    return None


def khuyen_nghi(viec: str) -> str:
    """Model khuyến nghị cho một loại việc — để IN RA cho người, không để tự chọn."""
    return KHUYEN_NGHI.get(viec, "")


def render_catalog(*, dang_dung: str = "", provider: str = "") -> str:
    """In danh mục, đánh dấu mã đang dùng."""
    from eaa.confidence import DA_KIEM, header

    dong = ["Danh mục mô hình", "", header(DA_KIEM), ""]
    dong.append("  Mỗi mã dưới đây đã được kiểm với API nhà cung cấp bằng ListModels")
    dong.append("  và một lượt gọi thật. Ngày kiểm ghi ở từng dòng.")
    dong.append("")

    for m in CATALOG:
        if provider and m.provider != provider:
            continue
        dau = "→" if m.id == dang_dung else " "
        dong.append(f" {dau} {m.id}   [{m.provider}]  {m.display}")
        if m.input_limit:
            dong.append(f"      vào ≤ {m.input_limit:,} token · ra ≤ {m.output_limit:,} token"
                        .replace(",", "."))
        dong.append(f"      {m.note}")
        dong.append(f"      kiểm ngày {m.verified_on}")
        dong.append("")

    if dang_dung and not get(dang_dung):
        dong += [
            f"  Đang dùng: {dang_dung} — KHÔNG có trong danh mục này.",
            "  Không phải lỗi: nhà cung cấp ra model mới nhanh hơn danh mục được",
            "  cập nhật. Chỉ là hệ chưa kiểm mã ấy, nên không nói gì về nó được.",
            "",
        ]

    dong += [
        "── Khuyến nghị theo loại việc (lời khuyên cho người đọc, hệ KHÔNG tự chọn)",
    ]
    for viec, mid in KHUYEN_NGHI.items():
        dong.append(f"  {viec:<34} {mid}")
    dong += [
        "",
        "  Hệ này KHÔNG tự đổi model giữa chừng. Chi phí và chất lượng là đánh đổi",
        "  của người trả tiền; và một model đổi ngầm làm hai lần chạy cùng một lệnh",
        "  không so sánh được với nhau nữa.",
        "",
        "── Chọn model",
        "  Mặc định của dự án:   eaa init --model <mã>          (GHIM vào Project State)",
        "  Đổi cho MỘT lượt:     eaa <lệnh> --model <mã>        (không ghi lại)",
        "  Cho cả phiên shell:   export EAA_LLM_MODEL=<mã>",
        "",
        "  Cờ --model nhận được cả trước lẫn sau tên lệnh. Riêng với 'init' nó có",
        "  nghĩa ghim — đó là lệnh đặt mặc định, nên ở đó ghi lại mới là đúng.",
        "",
        "  Thứ tự thắng: --model  >  Project State  >  EAA_LLM_MODEL  >  mặc định adapter.",
    ]
    return "\n".join(dong)
