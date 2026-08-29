"""Human Gate G1–G5 — điểm dừng bắt buộc, chỉ con người mở được.

EAA-SRS-01 FR-GATE-01, EAA-SAD-02 ADR-04 và §1 (NT1), EAA-SDD-03 §4
(``request(gate_id, payload) -> approved|rejected(reason)``).

ADR-04 nói gate được cưỡng chế TRONG Orchestrator chứ không phải là quy ước.
Module này là chỗ cưỡng chế đó, và nó dựa trên ba tính chất:

1.  **Không có cờ tự duyệt.** Không tồn tại tham số, biến môi trường hay chế
    độ nào khiến một quyết định ``approved`` sinh ra mà không có người. Chỉ
    :meth:`HumanGate.approve` tạo được quyết định duyệt, và nó đòi tên người
    quyết định. Orchestrator không bao giờ gọi hàm đó — có test quét mã nguồn
    chứng minh điều này, cùng kiểu với TC-38.

2.  **Gate duyệt MỘT payload cụ thể, không duyệt chung chung.** Mỗi yêu cầu
    mang băm của thứ được đưa ra duyệt. Nếu mã đổi sau khi người đã duyệt, băm
    lệch và quyết định cũ không còn hiệu lực. Không có tính chất này thì "duyệt
    cái này rồi merge cái khác" là một đường vòng hợp lệ về mặt kỹ thuật.

3.  **Từ chối phải kèm lý do, và lý do đi vào Error Ledger** (TC-02). Một lần
    từ chối không nêu lý do thì vòng sinh lại không học được gì, và AI sẽ nộp
    lại đúng thứ vừa bị từ chối.

Mọi quyết định được ghi nối tiếp vào ``gates/decisions.jsonl`` — đây chính là
"nhật ký chứng minh không gate nào bị vượt tự động" mà tiêu chí nghiệm thu của
EAA-STP-04 §5 đòi hỏi.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eaa.policy import GATE_ORDER, GATE_PURPOSE

__all__ = [
    "GateError",
    "GateNotPending",
    "GateNotInteractive",
    "GatePayload",
    "GateRequest",
    "GateDecision",
    "HumanGate",
    "APPROVED",
    "REJECTED",
    "PENDING",
]

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


class GateError(Exception):
    """Thao tác trên gate không hợp lệ."""


class GateNotPending(GateError):
    """Không có yêu cầu nào đang chờ ở gate này."""


class GateNotInteractive(GateError):
    """Cần xác nhận của người nhưng phiên chạy không có người.

    Trường hợp này KHÔNG được diễn giải thành đồng ý. Đây đúng là đường vòng
    mà TC-01 đi tìm: chạy trong script hay CI rồi mặc định cho qua.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class GatePayload:
    """Thứ được đưa ra cho người xem xét tại một gate."""

    gate_id: str
    title: str
    module: str = ""
    #: Vài dòng tóm tắt hiện ngay trên màn hình.
    summary: tuple[str, ...] = ()
    #: Nội dung đầy đủ — thường là diff.
    details: str = ""
    #: Checklist sinh từ Knowledge Graph (AIS §5.4) — biến review từ đọc tự do
    #: thành đối chiếu có hệ thống.
    checklist: tuple[str, ...] = ()
    #: Băm của VẬT THỂ NGOÀI mà quyết định neo vào — với G3 là băm diff của
    #: nhánh, do ``GitRepo.diff_digest`` tính.
    #:
    #: Vì sao cần một trường riêng thay vì dùng luôn ``digest``: hai bên phải
    #: so được với nhau. ``digest`` băm cả tiêu đề, tóm tắt và checklist — tức
    #: băm những gì con người NHÌN THẤY; còn lúc merge thì thứ duy nhất tính
    #: lại được là nội dung nhánh. Không có trường này, chuỗi "người duyệt X →
    #: merge đúng X" bị đứt ở khớp nối, và mỗi bên chỉ tự chứng minh được nửa
    #: của mình.
    content_digest: str = ""

    def __post_init__(self) -> None:
        if self.gate_id not in GATE_ORDER:
            raise GateError(
                f"Gate không hợp lệ: {self.gate_id!r} (hợp lệ: {list(GATE_ORDER)})"
            )

    @property
    def digest(self) -> str:
        """Băm những gì con người nhìn thấy — neo quyết định vào đúng thứ đã xem."""
        noi_dung = json.dumps(
            {
                "gate": self.gate_id,
                "module": self.module,
                "title": self.title,
                "summary": list(self.summary),
                "details": self.details,
                "content_digest": self.content_digest,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256(noi_dung.encode("utf-8")).hexdigest()

    def render(self) -> str:
        dong = [f"── {self.gate_id}: {self.title} ──", f"Mục đích: {GATE_PURPOSE[self.gate_id]}"]
        if self.module:
            dong.append(f"Module: {self.module}")
        if self.summary:
            dong.append("")
            dong.extend(f"  • {d}" for d in self.summary)
        if self.checklist:
            dong.append("")
            dong.append("Checklist review (sinh từ đồ thị tri thức):")
            dong.extend(f"  [ ] {d}" for d in self.checklist)
        if self.details:
            dong.append("")
            dong.append(self.details)
        dong.append("")
        dong.append(f"Băm nội dung: {self.digest}")
        return "\n".join(dong)


@dataclass(frozen=True)
class GateRequest:
    """Một yêu cầu đang chờ người quyết định."""

    payload: GatePayload
    requested_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.payload.gate_id,
            "title": self.payload.title,
            "module": self.payload.module,
            "summary": list(self.payload.summary),
            "details": self.payload.details,
            "checklist": list(self.payload.checklist),
            "content_digest": self.payload.content_digest,
            "digest": self.payload.digest,
            "requested_at": self.requested_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateRequest":
        return cls(
            payload=GatePayload(
                gate_id=data["gate_id"],
                title=data.get("title", ""),
                module=data.get("module", ""),
                summary=tuple(data.get("summary", ())),
                details=data.get("details", ""),
                checklist=tuple(data.get("checklist", ())),
                content_digest=data.get("content_digest", ""),
            ),
            requested_at=data.get("requested_at", ""),
        )


@dataclass(frozen=True)
class GateDecision:
    """Quyết định của con người tại một gate.

    Chỉ :meth:`HumanGate.approve` và :meth:`HumanGate.reject` tạo ra vật thể
    này trong luồng sản phẩm. ``actor`` bắt buộc không rỗng — một quyết định
    không có người chịu trách nhiệm thì không phải quyết định của con người.
    """

    gate_id: str
    decision: str
    actor: str
    decided_at: str
    payload_digest: str
    #: Băm vật thể ngoài mà quyết định neo vào (với G3: nội dung nhánh).
    #: Đây là đầu nối để lúc merge kiểm được "đúng thứ đã duyệt".
    content_digest: str = ""
    module: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if self.decision not in (APPROVED, REJECTED):
            raise GateError(f"Quyết định không hợp lệ: {self.decision!r}")
        if not self.actor.strip():
            raise GateError(
                "Quyết định tại gate phải ghi tên người quyết định — một quyết "
                "định không có người chịu trách nhiệm không phải quyết định của "
                "con người (FR-GATE-01)."
            )
        if self.decision == REJECTED and not self.reason.strip():
            raise GateError(
                "Từ chối tại gate bắt buộc kèm lý do (TC-02): lý do là thứ vòng "
                "sinh lại học được, không có nó thì AI nộp lại đúng cái vừa bị từ chối."
            )

    @property
    def approved(self) -> bool:
        return self.decision == APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "decision": self.decision,
            "actor": self.actor,
            "decided_at": self.decided_at,
            "payload_digest": self.payload_digest,
            "content_digest": self.content_digest,
            "module": self.module,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateDecision":
        return cls(
            gate_id=data["gate_id"],
            decision=data["decision"],
            actor=data.get("actor", "?"),
            decided_at=data.get("decided_at", ""),
            payload_digest=data.get("payload_digest", ""),
            content_digest=data.get("content_digest", ""),
            module=data.get("module", ""),
            reason=data.get("reason", ""),
        )


class HumanGate:
    """Quản lý vòng đời yêu cầu → quyết định của năm Human Gate."""

    def __init__(
        self,
        gates_dir: str | os.PathLike[str],
        state_store: Any = None,
        ledger: Any = None,
    ) -> None:
        self.gates_dir = Path(gates_dir)
        self.state_store = state_store
        self.ledger = ledger

    # -- đường dẫn ---------------------------------------------------------

    def _pending_path(self, gate_id: str) -> Path:
        return self.gates_dir / f"pending_{gate_id}.json"

    @property
    def decisions_path(self) -> Path:
        return self.gates_dir / "decisions.jsonl"

    # -- yêu cầu -----------------------------------------------------------

    def request(self, payload: GatePayload) -> GateRequest:
        """Ghi nhận một yêu cầu chờ người quyết định.

        Hàm này KHÔNG hỏi và KHÔNG quyết định. Nó chỉ dừng máy lại và đặt hồ sơ
        lên bàn. Orchestrator gọi tới đây rồi thoát với mã 2 (chờ gate).
        """
        self.gates_dir.mkdir(parents=True, exist_ok=True)
        yeu_cau = GateRequest(payload=payload, requested_at=_now())
        self._pending_path(payload.gate_id).write_text(
            json.dumps(yeu_cau.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._ghi_state(payload.gate_id, PENDING)
        return yeu_cau

    def pending(self, gate_id: str | None = None) -> list[GateRequest]:
        if not self.gates_dir.is_dir():
            return []
        ids = [gate_id] if gate_id else list(GATE_ORDER)
        ket_qua: list[GateRequest] = []
        for gid in ids:
            path = self._pending_path(gid)
            if path.is_file():
                ket_qua.append(
                    GateRequest.from_dict(json.loads(path.read_text(encoding="utf-8")))
                )
        return ket_qua

    def _lay_pending(self, gate_id: str) -> GateRequest:
        path = self._pending_path(gate_id)
        if not path.is_file():
            raise GateNotPending(
                f"Không có yêu cầu nào đang chờ ở {gate_id}. Chạy 'eaa gate show' "
                "để xem gate nào đang chờ."
            )
        return GateRequest.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # -- quyết định --------------------------------------------------------

    def approve(
        self, gate_id: str, *, actor: str, expect_digest: str | None = None
    ) -> GateDecision:
        """Con người phê duyệt. Đây là hàm DUY NHẤT sinh ra quyết định duyệt.

        ``expect_digest`` cho phép người gọi khẳng định "tôi duyệt đúng nội dung
        có băm này". Lệch băm nghĩa là nội dung đã đổi kể từ lúc hồ sơ được đặt
        lên bàn — quyết định bị từ chối chứ không im lặng duyệt bản mới.
        """
        yeu_cau = self._lay_pending(gate_id)
        digest = yeu_cau.payload.digest

        if expect_digest and expect_digest != digest:
            raise GateError(
                f"Nội dung tại {gate_id} đã thay đổi kể từ lúc bạn xem "
                f"(chờ {expect_digest}, hiện {digest}). Xem lại bằng "
                "'eaa gate show' rồi quyết định trên bản mới."
            )

        quyet_dinh = GateDecision(
            gate_id=gate_id,
            decision=APPROVED,
            actor=actor,
            decided_at=_now(),
            payload_digest=digest,
            content_digest=yeu_cau.payload.content_digest,
            module=yeu_cau.payload.module,
        )
        self._ghi_quyet_dinh(quyet_dinh)
        self._pending_path(gate_id).unlink(missing_ok=True)
        return quyet_dinh

    def reject(self, gate_id: str, *, actor: str, reason: str) -> GateDecision:
        """Con người từ chối, kèm lý do. Lý do đi vào Error Ledger (TC-02)."""
        yeu_cau = self._lay_pending(gate_id)

        quyet_dinh = GateDecision(
            gate_id=gate_id,
            decision=REJECTED,
            actor=actor,
            decided_at=_now(),
            payload_digest=yeu_cau.payload.digest,
            content_digest=yeu_cau.payload.content_digest,
            module=yeu_cau.payload.module,
            reason=reason,
        )
        self._ghi_quyet_dinh(quyet_dinh)
        self._pending_path(gate_id).unlink(missing_ok=True)

        if self.ledger is not None:
            self.ledger.add(
                module=yeu_cau.payload.module or "(không rõ module)",
                category="gate_rejection",
                description=f"Kỹ sư từ chối tại {gate_id}: {reason}",
                evidence=f"{gate_id}, băm nội dung {yeu_cau.payload.digest}",
                rule=f"KHÔNG lặp lại lỗi đã bị từ chối tại {gate_id}: {reason}",
            )

        return quyet_dinh

    def confirm_interactive(
        self, payload: GatePayload, *, actor: str = "", stream: Any = None
    ) -> GateDecision:
        """Hỏi trực tiếp trên terminal — dùng cho xác nhận tại chỗ.

        Không phải TTY thì NÉM LỖI chứ không mặc định đồng ý. Chạy trong script
        hay CI mà im lặng cho qua chính là đường vòng TC-01 đi tìm.
        """
        ra = stream or sys.stdout
        if not sys.stdin.isatty():
            raise GateNotInteractive(
                f"{payload.gate_id} cần xác nhận của người nhưng phiên này không "
                "có terminal. Không có chế độ tự đồng ý. Chạy lại trong terminal, "
                f"hoặc dùng 'eaa gate approve {payload.gate_id}'."
            )

        print(payload.render(), file=ra)
        tra_loi = input(f"{payload.gate_id} — duyệt? [y/N]: ").strip().lower()

        if tra_loi in ("y", "yes", "c", "có"):
            self.request(payload)
            return self.approve(payload.gate_id, actor=actor or self._nguoi_dung())

        ly_do = input("Lý do từ chối: ").strip()
        self.request(payload)
        return self.reject(
            payload.gate_id,
            actor=actor or self._nguoi_dung(),
            reason=ly_do or "(người dùng từ chối, không nêu lý do)",
        )

    # -- tra cứu -----------------------------------------------------------

    def decisions(self, gate_id: str | None = None) -> list[GateDecision]:
        if not self.decisions_path.is_file():
            return []
        ket_qua: list[GateDecision] = []
        for so_dong, dong in enumerate(
            self.decisions_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                quyet_dinh = GateDecision.from_dict(json.loads(dong))
            except (json.JSONDecodeError, GateError, KeyError) as exc:
                raise GateError(
                    f"{self.decisions_path}:{so_dong}: bản ghi quyết định hỏng — {exc}"
                ) from exc
            if gate_id is None or quyet_dinh.gate_id == gate_id:
                ket_qua.append(quyet_dinh)
        return ket_qua

    def latest(self, gate_id: str) -> GateDecision | None:
        ds = self.decisions(gate_id)
        return ds[-1] if ds else None

    def status(self, gate_id: str) -> str:
        """Trạng thái hiện tại: ``pending`` / ``approved`` / ``rejected``."""
        if self._pending_path(gate_id).is_file():
            return PENDING
        quyet_dinh = self.latest(gate_id)
        return quyet_dinh.decision if quyet_dinh else PENDING

    def is_approved_for(self, gate_id: str, digest: str) -> bool:
        """Gate đã duyệt ĐÚNG nội dung có băm này chưa.

        Không hỏi "gate đã duyệt chưa" mà hỏi "đã duyệt cái này chưa" — khác
        biệt giữa hai câu là toàn bộ khoảng trống cho lối "duyệt cái này, merge
        cái khác".
        """
        quyet_dinh = self.latest(gate_id)
        return bool(
            quyet_dinh
            and quyet_dinh.approved
            and quyet_dinh.payload_digest == digest
            and not self._pending_path(gate_id).is_file()
        )

    # -- ghi ---------------------------------------------------------------

    def _ghi_quyet_dinh(self, quyet_dinh: GateDecision) -> None:
        """Nối tiếp vào nhật ký quyết định — không sửa, không xóa.

        Nhật ký này là bằng chứng cho tiêu chí nghiệm thu STP-04 §5: "không
        gate nào bị vượt tự động".
        """
        self.gates_dir.mkdir(parents=True, exist_ok=True)
        with open(self.decisions_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(quyet_dinh.to_dict(), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._ghi_state(quyet_dinh.gate_id, quyet_dinh.decision)

    def _ghi_state(self, gate_id: str, trang_thai: str) -> None:
        if self.state_store is None or not self.state_store.exists():
            return
        with self.state_store.with_lock():
            state = self.state_store.load()
            state.gates[gate_id] = trang_thai
            self.state_store.save(state)

    @staticmethod
    def _nguoi_dung() -> str:
        for bien in ("EAA_ACTOR", "USER", "USERNAME", "LOGNAME"):
            gia_tri = os.environ.get(bien)
            if gia_tri:
                return gia_tri
        return "kỹ sư"
