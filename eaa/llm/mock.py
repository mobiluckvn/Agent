"""MockLLM — adapter tất định cho Sprint 1–3.

MDD §5: "Sprint 1–3 chạy hoàn toàn bằng MockLLM (trả code định sẵn cho các
kịch bản pass/fail/vi phạm) — không tốn API, test tất định; Gemini thật chỉ vào
từ Sprint 4." Xem `docs/SAI_LECH_THIET_KE.md` mục SL-05.

Ba điều khiến adapter này đáng tin làm chỗ dựa cho toàn bộ kiểm thử tích hợp:

1.  **Nó là adapter thật.** Cùng interface ``LLMClient``, tự kiểm ngân sách
    trước khi "gọi", tự bóc tách phản hồi theo đúng quy ước ```` ```file: ````.
    Thứ được test ở Sprint 1–3 chính là đường đi sẽ chạy ở Sprint 4 — nếu mock
    là một nhánh ``if`` trong engine thì bài kiểm thử sẽ kiểm nhầm nhánh.
2.  **Nó ghi lại mọi prompt.** Nhiều test case chấm nội dung prompt chứ không
    chấm mã sinh ra: ràng buộc có mặt trong 100% lần gọi (TC-04), chunk đúng
    được nạp (TC-05), thân module đã merge không bao giờ bị gửi lại (TC-21),
    prompt sửa lỗi không kèm cả tệp (TC-19).
3.  **Phản hồi là DỮ LIỆU.** Mã trả về do bài test hoặc dự án cung cấp, không
    nằm cứng trong engine. Ngoài lý do sạch phần cứng (FR-PLT-01), điều này
    còn khiến việc thêm một kịch bản hỏng mới không phải sửa engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from eaa.llm.base import LLMError, Prompt, estimate_tokens, parse_file_blocks
from eaa.tools.base import CodeArtifact

__all__ = ["MockLLM", "MockCall", "SCENARIOS"]

#: Kịch bản dựng sẵn. Mã ở đây cố tình TRUNG LẬP về phần cứng: nó chỉ cần đủ
#: thật để đi qua (hoặc trượt) các cổng kiểm chứng, không cần giống firmware
#: của một dự án cụ thể.
SCENARIOS: dict[str, str] = {
    # Qua mọi cổng.
    "pass": """```file:src/module.c
#include "module.h"

// ref: {chunk}
static uint8_t module_state;

void module_init(void)
{
    module_state = 0u;
}

uint8_t module_step(uint8_t input)
{
    module_state = (uint8_t)(module_state + input);
    return module_state;
}
```

```file:src/module.h
#ifndef MODULE_H
#define MODULE_H

#include <stdint.h>

void module_init(void);
uint8_t module_step(uint8_t input);

#endif
```
""",
    # Không biên dịch được: thiếu dấu chấm phẩy và gọi hàm chưa khai báo.
    "fail": """```file:src/module.c
#include "module.h"

void module_init(void)
{
    uint8_t x = 0u
    undeclared_helper(x);
}
```
""",
    # Biên dịch được nhưng vi phạm ràng buộc cứng: hàm chặn, cấp phát động, đệ quy.
    "violation": """```file:src/module.c
#include "module.h"
#include <stdlib.h>

static uint8_t descend(uint8_t n)
{
    if (n == 0u) {
        return 0u;
    }
    return descend((uint8_t)(n - 1u));
}

void module_init(void)
{
    uint8_t *buf = malloc(16);
    delay(100);
    descend(3u);
    free(buf);
}
```
""",
    # Cấu hình thanh ghi mà KHÔNG trích dẫn chunk — kịch bản của TC-17.
    "no_citation": """```file:src/module.c
#include "module.h"

void module_init(void)
{
    hw_write_register(0x21u, 0x0Cu);
}
```
""",
    # Phản hồi sai định dạng: tính là một lần fail của vòng tự sửa (SDD §6).
    "malformed": "Đây là lời giải thích bằng văn xuôi, không có khối file nào.",
}


@dataclass
class MockCall:
    """Bản ghi một lần gọi — để bài test soi được prompt đã gửi đi."""

    prompt: Prompt
    rendered: str
    response: str
    tokens_in: int


@dataclass
class MockLLM:
    """Adapter LLM giả lập, tất định.

    ``responses`` nhận một trong bốn dạng:

    * ``None`` — dùng kịch bản ``scenario``;
    * chuỗi — trả đúng chuỗi đó cho mọi lần gọi;
    * dãy chuỗi — trả lần lượt, hết dãy thì lặp lại phần tử cuối (tiện dựng
      kịch bản "hỏng hai lần rồi sửa được ở lần ba" cho vòng tự sửa);
    * ánh xạ ``module_id → phản hồi``;
    * hàm ``(prompt, lần_gọi_thứ) → phản hồi``.
    """

    provider: str = "mock"
    model: str = "mock-deterministic-1"
    scenario: str = "pass"
    responses: str | Sequence[str] | Mapping[str, str] | Callable[[Prompt, int], str] | None = None
    #: Bật để mô phỏng adapter bỏ qua kiểm ngân sách — chỉ dùng trong test
    #: chứng minh rằng cổng ngân sách thật sự chặn.
    enforce_budget: bool = True
    calls: list[MockCall] = field(default_factory=list)

    def count_tokens(self, text: str) -> int:
        """Bộ đếm tất định; mô hình thật thay bằng ``count_tokens`` của nhà cung cấp."""
        return estimate_tokens(text)

    # -- phản hồi ----------------------------------------------------------

    def _response_for(self, prompt: Prompt) -> str:
        lan = len(self.calls)
        nguon = self.responses

        if nguon is None:
            try:
                mau = SCENARIOS[self.scenario]
            except KeyError:
                raise LLMError(
                    f"Không có kịch bản MockLLM {self.scenario!r} "
                    f"(đang có: {sorted(SCENARIOS)})"
                ) from None
            chunk = prompt.chunk_ids[0] if prompt.chunk_ids else "ds-000"
            return mau.replace("{chunk}", chunk)

        if callable(nguon):
            return nguon(prompt, lan)
        if isinstance(nguon, str):
            return nguon
        if isinstance(nguon, Mapping):
            try:
                return nguon[prompt.module]
            except KeyError:
                raise LLMError(
                    f"MockLLM không có phản hồi định sẵn cho module {prompt.module!r}"
                ) from None
        if not nguon:
            raise LLMError("MockLLM được cấu hình với dãy phản hồi rỗng")
        return nguon[min(lan, len(nguon) - 1)]

    # -- interface LLMClient ----------------------------------------------

    def complete(self, prompt: Prompt) -> str:
        """Văn bản thô, không đòi khối ```file: — xem GeminiClient.complete."""
        if self.enforce_budget:
            prompt.check_budget(self.count_tokens)
        van_ban = self._response_for(prompt)
        self.calls.append(
            MockCall(
                prompt=prompt,
                rendered=prompt.full_text(),
                response=van_ban,
                tokens_in=self.count_tokens(prompt.full_text()),
            )
        )
        return van_ban

    def generate(self, prompt: Prompt) -> CodeArtifact:
        if self.enforce_budget:
            prompt.check_budget(self.count_tokens)

        rendered = prompt.full_text()
        tokens_in = self.count_tokens(rendered)
        response = self._response_for(prompt)
        self.calls.append(
            MockCall(
                prompt=prompt, rendered=rendered, response=response, tokens_in=tokens_in
            )
        )

        files = parse_file_blocks(response)
        return CodeArtifact(
            files=files,
            prompt_hash=prompt.hash,
            model=self.model,
            constraints_version=prompt.constraints_version,
            chunk_ids=list(prompt.chunk_ids),
            tokens_in=tokens_in,
            tokens_out=self.count_tokens(response),
            raw_response=response,
        )

    # -- tiện cho test -----------------------------------------------------

    @property
    def last_prompt(self) -> str:
        if not self.calls:
            raise LLMError("MockLLM chưa được gọi lần nào")
        return self.calls[-1].rendered

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()
