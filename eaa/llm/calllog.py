"""Nhật ký lời gọi mô hình — bằng chứng tái lập và bộ phát lại.

EAA-AIS-05 §12 (giảm thiểu rủi ro "mô hình đổi hành vi giữa kỳ thực nghiệm":
*"lưu (prompt hash → phản hồi) làm bằng chứng"*), EAA-STP-04 §6 rủi ro R1,
NFR-07. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-19.

Module này làm hai việc từ cùng một dữ liệu:

1.  **Bằng chứng.** Mỗi lời gọi được ghi lại kèm băm prompt, mã model, số token
    và thời gian. Khi bảo vệ, câu "kết quả này sinh ra từ prompt nào, model
    nào" trả lời được bằng một lần tra — và nếu nhà cung cấp đổi hành vi giữa
    chừng, sự thay đổi ấy hiện ra thành hai phản hồi khác nhau cho cùng một băm.

2.  **Phát lại.** :class:`ReplayClient` đọc nhật ký và trả lại đúng phản hồi đã
    ghi cho cùng một băm prompt. Nhờ vậy chạy lại toàn bộ vòng lặp chuẩn không
    tốn một lời gọi API nào, và kiểm thử end-to-end chạy được trên máy không có
    khóa — kể cả trong CI.

Điểm cần nói rõ về phát lại: nó KHÔNG thay thế việc chạy thật. Một lượt phát
lại chứng minh *quy trình* xử lý đúng phản hồi ấy; nó không chứng minh mô hình
hôm nay vẫn trả lời như vậy. Hai câu khác nhau, và bộ test nào dựa vào phát
lại thì phải nói rõ mình đang chứng minh câu nào.

Prompt được ghi ở dạng ĐÃ CHE khóa (xem ``mask_secrets``), nên nhật ký này an
toàn để commit vào Git cùng phần còn lại của dự án.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eaa.llm.base import LLMError, Prompt, estimate_tokens, mask_secrets, parse_file_blocks
from eaa.tools.base import CodeArtifact

__all__ = ["CallLog", "CallRecord", "ReplayClient", "ReplayMiss"]


class ReplayMiss(LLMError):
    """Không có bản ghi nào cho prompt này trong nhật ký."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class CallRecord:
    """Một lời gọi mô hình đã ghi."""

    prompt_hash: str
    module: str
    provider: str
    model: str
    constraints_version: str
    chunk_ids: tuple[str, ...]
    response: str
    tokens_in: int
    tokens_out: int
    duration_s: float
    called_at: str
    #: Toàn văn prompt đã che khóa — để tái lập và để đối chứng khi nghi ngờ.
    prompt_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_hash": self.prompt_hash,
            "module": self.module,
            "provider": self.provider,
            "model": self.model,
            "constraints_version": self.constraints_version,
            "chunk_ids": list(self.chunk_ids),
            "response": self.response,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "duration_s": round(self.duration_s, 3),
            "called_at": self.called_at,
            "prompt_text": self.prompt_text,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CallRecord":
        return cls(
            prompt_hash=d["prompt_hash"],
            module=d.get("module", ""),
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            constraints_version=d.get("constraints_version", ""),
            chunk_ids=tuple(d.get("chunk_ids", ())),
            response=d.get("response", ""),
            tokens_in=int(d.get("tokens_in", 0)),
            tokens_out=int(d.get("tokens_out", 0)),
            duration_s=float(d.get("duration_s", 0.0)),
            called_at=d.get("called_at", ""),
            prompt_text=d.get("prompt_text", ""),
        )


class CallLog:
    """Nhật ký append-only các lời gọi mô hình — ``llm_calls.jsonl``."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def record(
        self,
        *,
        prompt: Prompt,
        response: str,
        model: str,
        provider: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_s: float = 0.0,
    ) -> CallRecord:
        ban_ghi = CallRecord(
            prompt_hash=prompt.hash,
            module=prompt.module,
            provider=provider,
            model=model,
            constraints_version=prompt.constraints_version,
            chunk_ids=tuple(prompt.chunk_ids),
            response=response,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_s=duration_s,
            called_at=_now(),
            # Che khóa trước khi ghi: nhật ký này nằm trong Git.
            prompt_text=mask_secrets(prompt.full_text()),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ban_ghi.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return ban_ghi

    def all(self) -> list[CallRecord]:
        if not self.path.is_file():
            return []
        ket_qua: list[CallRecord] = []
        for so_dong, dong in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                ket_qua.append(CallRecord.from_dict(json.loads(dong)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise LLMError(f"{self.path}:{so_dong}: bản ghi hỏng — {exc}") from exc
        return ket_qua

    def find(self, prompt_hash: str) -> list[CallRecord]:
        return [r for r in self.all() if r.prompt_hash == prompt_hash]

    def latest(self, prompt_hash: str) -> CallRecord | None:
        khop = self.find(prompt_hash)
        return khop[-1] if khop else None

    def drift(self) -> list[tuple[str, list[CallRecord]]]:
        """Cùng một băm prompt mà nhận hai phản hồi khác nhau.

        Đây chính là hiện tượng mà rủi ro R1 nói tới. Với ``temperature`` thấp
        thì khác biệt nhỏ vẫn có thể xảy ra; điều đáng chú ý là khi phản hồi
        khác nhau tới mức bóc ra tập tệp khác nhau — lúc ấy hai lần chạy của
        cùng một thí nghiệm không còn so được với nhau.
        """
        theo_bam: dict[str, list[CallRecord]] = {}
        for r in self.all():
            theo_bam.setdefault(r.prompt_hash, []).append(r)
        return [
            (bam, ds)
            for bam, ds in sorted(theo_bam.items())
            if len({r.response for r in ds}) > 1
        ]

    def summary(self) -> dict[str, Any]:
        ban_ghi = self.all()
        return {
            "calls": len(ban_ghi),
            "modules": sorted({r.module for r in ban_ghi if r.module}),
            "models": sorted({r.model for r in ban_ghi if r.model}),
            "tokens_in_total": sum(r.tokens_in for r in ban_ghi),
            "tokens_out_total": sum(r.tokens_out for r in ban_ghi),
            "drifted_prompts": len(self.drift()),
        }


@dataclass
class ReplayClient:
    """Adapter phát lại phản hồi đã ghi — tuân giao diện ``LLMClient``.

    Dùng để chạy lại toàn bộ vòng lặp chuẩn mà không tốn lời gọi API, và để
    kiểm thử end-to-end trên máy không có khóa.

    Không tìm thấy bản ghi thì NÉM LỖI chứ không sinh bừa một phản hồi: một
    lượt phát lại lặng lẽ bịa nội dung sẽ tạo ra bằng chứng giả cho Chương 3.
    """

    log: CallLog
    #: Giữ nguyên mã model của bản ghi để dấu vết truy vết không bị đổi.
    provider: str = "replay"
    model: str = ""
    calls: list[Prompt] = field(default_factory=list)

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def complete(self, prompt: Prompt) -> str:
        """Phát lại văn bản thô — xem GeminiClient.complete."""
        prompt.check_budget(self.count_tokens)
        ban_ghi = self.log.latest(prompt.hash)
        if ban_ghi is None:
            raise ReplayMiss(
                f"Không có bản ghi cho prompt {prompt.hash} trong {self.log.path}."
            )
        self.calls.append(prompt)
        return ban_ghi.response

    def generate(self, prompt: Prompt) -> CodeArtifact:
        prompt.check_budget(self.count_tokens)
        ban_ghi = self.log.latest(prompt.hash)
        if ban_ghi is None:
            raise ReplayMiss(
                f"Không có bản ghi cho prompt {prompt.hash} (module "
                f"{prompt.module!r}) trong {self.log.path}.\n"
                "Phát lại KHÔNG bịa phản hồi: một lượt phát lại tự sinh nội dung "
                "sẽ tạo bằng chứng giả cho Chương 3. Chạy lại với mô hình thật "
                "để ghi bản ghi mới, hoặc kiểm xem prompt đã đổi ở đâu."
            )

        self.calls.append(prompt)
        self.model = ban_ghi.model
        return CodeArtifact(
            files=parse_file_blocks(ban_ghi.response),
            prompt_hash=prompt.hash,
            model=ban_ghi.model,
            constraints_version=prompt.constraints_version,
            chunk_ids=list(prompt.chunk_ids),
            tokens_in=ban_ghi.tokens_in,
            tokens_out=ban_ghi.tokens_out,
            raw_response=ban_ghi.response,
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)
