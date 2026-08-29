"""Quản lý phiên bản mã — ba hạng chất lượng, bản known-good, quay lui.

EAA-AIS-05 §8.4; FR-VER-01/02; TC-30, TC-31.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-21.

Câu hỏi vận hành mà module này trả lời: **bản nào là tốt, nằm ở đâu?** Không
có câu trả lời máy đọc được, mỗi lần robot hỏng là một lần mò trong lịch sử
Git để đoán xem commit nào từng chạy được.

Ba hạng chất lượng, tăng dần, gắn vào từng commit (AIS §8.4):

===============  ===========================================================
``build-ok``     Qua biên dịch, đo kích thước, phân tích tĩnh, kiểm thử đơn vị
``sim-verified`` Thêm: qua cổng mô phỏng — điều kiện để được merge qua G3
``hw-verified``  Thêm: người nghiệm thu trên thiết bị thật tại G4, kèm số đo
===============  ===========================================================

Hai bất biến:

* **``known_good.lock`` CHỈ cập nhật tại G4.** Một bản qua hết cổng máy vẫn
  chưa phải bản "biết-là-tốt": máy không nhìn thấy rung cơ khí, nhiệt độ hay
  sụt áp. Chỉ con người đứng cạnh thiết bị mới phong được hạng cao nhất.
* **Thất bại cũng là tri thức.** Mỗi lần quay lui ghi một sự kiện kèm lý do
  vào build ledger; không có chuyện lặng lẽ lùi về bản cũ rồi làm như chưa có
  gì xảy ra.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eaa.gates import APPROVED, GateDecision

__all__ = [
    "VersionError",
    "PromotionNotAuthorized",
    "NoKnownGood",
    "Tier",
    "BuildRecord",
    "Measurement",
    "VersionRegistry",
    "TIER_ORDER",
    "ACCEPTANCE_GATE",
]


class Tier:
    BUILD_OK = "build-ok"
    SIM_VERIFIED = "sim-verified"
    HW_VERIFIED = "hw-verified"


#: Thứ tự tăng dần. Dùng để so hạng, và để chặn việc phong vượt cấp.
TIER_ORDER: tuple[str, ...] = (Tier.BUILD_OK, Tier.SIM_VERIFIED, Tier.HW_VERIFIED)

#: Gate nghiệm thu vật lý — chỉ ở đây mới phong được hạng cao nhất.
ACCEPTANCE_GATE = "G4"


class VersionError(Exception):
    """Thao tác phiên bản không hợp lệ."""


class PromotionNotAuthorized(VersionError):
    """Phong hạng ``hw-verified`` mà chưa có phê duyệt của người tại G4."""


class NoKnownGood(VersionError):
    """Chưa có bản known-good nào để quay lui về."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Measurement:
    """Một bản ghi đo trên thiết bị thật — Measurement Records (AIS §8.1)."""

    name: str
    value: float
    unit: str = ""
    note: str = ""

    def __str__(self) -> str:
        return f"{self.name}={self.value:g}{self.unit}" + (f" ({self.note})" if self.note else "")


@dataclass(frozen=True)
class BuildRecord:
    """Một sự kiện trong build ledger."""

    module: str
    commit: str
    tier: str
    event: str            # promote · rollback · reject
    at: str
    reason: str = ""
    actor: str = ""
    env_hash: str = ""
    measurements: tuple[Measurement, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "commit": self.commit,
            "tier": self.tier,
            "event": self.event,
            "at": self.at,
            "reason": self.reason,
            "actor": self.actor,
            "env_hash": self.env_hash,
            "measurements": [
                {"name": m.name, "value": m.value, "unit": m.unit, "note": m.note}
                for m in self.measurements
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BuildRecord":
        return cls(
            module=d.get("module", ""),
            commit=d.get("commit", ""),
            tier=d.get("tier", ""),
            event=d.get("event", ""),
            at=d.get("at", ""),
            reason=d.get("reason", ""),
            actor=d.get("actor", ""),
            env_hash=d.get("env_hash", ""),
            measurements=tuple(
                Measurement(
                    name=m.get("name", ""),
                    value=float(m.get("value", 0)),
                    unit=m.get("unit", ""),
                    note=m.get("note", ""),
                )
                for m in d.get("measurements", [])
            ),
        )


class VersionRegistry:
    """Build ledger + ``known_good.lock`` của một dự án."""

    def __init__(
        self,
        *,
        ledger_path: str | os.PathLike[str],
        lock_path: str | os.PathLike[str],
        repo: Any = None,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.lock_path = Path(lock_path)
        self.repo = repo

    # ----------------------------------------------------------------------
    # Build ledger
    # ----------------------------------------------------------------------

    def records(self, module: str = "") -> list[BuildRecord]:
        if not self.ledger_path.is_file():
            return []
        ket_qua: list[BuildRecord] = []
        for so_dong, dong in enumerate(
            self.ledger_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                ban_ghi = BuildRecord.from_dict(json.loads(dong))
            except (json.JSONDecodeError, ValueError) as exc:
                raise VersionError(
                    f"{self.ledger_path}:{so_dong}: bản ghi hỏng — {exc}"
                ) from exc
            if not module or ban_ghi.module == module:
                ket_qua.append(ban_ghi)
        return ket_qua

    def _append(self, ban_ghi: BuildRecord) -> BuildRecord:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ban_ghi.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return ban_ghi

    # ----------------------------------------------------------------------
    # Phong hạng
    # ----------------------------------------------------------------------

    def promote(
        self,
        *,
        module: str,
        commit: str,
        tier: str,
        reason: str = "",
        actor: str = "",
        env_hash: str = "",
        decision: GateDecision | None = None,
        measurements: Sequence[Measurement] = (),
    ) -> BuildRecord:
        """Phong một commit lên một hạng chất lượng.

        Hạng ``hw-verified`` đòi phê duyệt tại G4 và đòi có SỐ ĐO đi kèm. Đây
        là chỗ ranh giới người–máy nằm rõ nhất trong cả sản phẩm: ba hạng dưới
        máy tự chấm được, hạng trên cùng thì không — nó khẳng định một điều về
        thế giới vật lý, và chỉ người đứng cạnh thiết bị mới khẳng định được.
        """
        if tier not in TIER_ORDER:
            raise VersionError(
                f"Hạng không hợp lệ: {tier!r} (hợp lệ: {list(TIER_ORDER)})"
            )
        if not commit:
            raise VersionError("Phải nêu commit được phong hạng")

        if tier == Tier.HW_VERIFIED:
            self._kiem_phe_duyet_G4(decision, module)
            if not measurements:
                raise PromotionNotAuthorized(
                    f"Phong {module!r} lên {Tier.HW_VERIFIED} mà không có số đo "
                    "nào. Hạng này khẳng định một điều về thiết bị thật, nên nó "
                    "phải đi kèm bằng chứng đo được (AIS §8.4, FR-VER-01)."
                )

        ban_ghi = self._append(
            BuildRecord(
                module=module,
                commit=commit,
                tier=tier,
                event="promote",
                at=_now(),
                reason=reason,
                actor=actor or (decision.actor if decision else ""),
                env_hash=env_hash,
                measurements=tuple(measurements),
            )
        )

        # known_good.lock CHỈ cập nhật tại G4 — FR-VER-02.
        if tier == Tier.HW_VERIFIED:
            self._cap_nhat_known_good(module, commit, ban_ghi)
            if self.repo is not None:
                self._gan_tag(module, commit)

        return ban_ghi

    @staticmethod
    def _kiem_phe_duyet_G4(decision: GateDecision | None, module: str) -> None:
        if decision is None:
            raise PromotionNotAuthorized(
                f"Phong {module!r} lên {Tier.HW_VERIFIED} cần phê duyệt tại "
                f"{ACCEPTANCE_GATE}. Máy không nhìn thấy rung cơ khí, nhiệt độ "
                "hay sụt áp — hạng cao nhất chỉ con người đứng cạnh thiết bị "
                "mới phong được."
            )
        if decision.gate_id != ACCEPTANCE_GATE:
            raise PromotionNotAuthorized(
                f"Cần quyết định tại {ACCEPTANCE_GATE}, nhận quyết định của "
                f"{decision.gate_id!r}. Duyệt một gate khác không phong được hạng."
            )
        if decision.decision != APPROVED:
            raise PromotionNotAuthorized(
                f"{ACCEPTANCE_GATE} ở trạng thái {decision.decision!r} — chưa "
                f"nghiệm thu thì chưa có {Tier.HW_VERIFIED}."
            )

    def _gan_tag(self, module: str, commit: str) -> None:
        so = len([r for r in self.records(module) if r.tier == Tier.HW_VERIFIED])
        ten = f"hw-verified/{module}/v{so}"
        try:
            self.repo.tag(ten, message=f"Nghiệm thu vật lý {module} tại {ACCEPTANCE_GATE}")
        except Exception:  # pragma: no cover - tag trùng hoặc kho chưa có commit
            pass

    # ----------------------------------------------------------------------
    # known_good.lock
    # ----------------------------------------------------------------------

    def known_good(self) -> dict[str, Any]:
        if not self.lock_path.is_file():
            return {"modules": {}, "firmware": ""}
        try:
            return json.loads(self.lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise VersionError(f"{self.lock_path}: JSON hỏng — {exc}") from exc

    def known_good_of(self, module: str) -> str:
        return (self.known_good().get("modules", {}) or {}).get(module, {}).get("commit", "")

    def _cap_nhat_known_good(self, module: str, commit: str, ban_ghi: BuildRecord) -> None:
        du_lieu = self.known_good()
        du_lieu.setdefault("modules", {})[module] = {
            "commit": commit,
            "tier": Tier.HW_VERIFIED,
            "promoted_at": ban_ghi.at,
            "actor": ban_ghi.actor,
            "measurements": [str(m) for m in ban_ghi.measurements],
        }
        du_lieu["firmware"] = commit
        du_lieu["updated_at"] = ban_ghi.at

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        tam = self.lock_path.with_suffix(".lock.tmp")
        tam.write_text(
            json.dumps(du_lieu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tam, self.lock_path)

    # ----------------------------------------------------------------------
    # TC-30 — quay lui
    # ----------------------------------------------------------------------

    def reject_acceptance(
        self, *, module: str, commit: str, reason: str, actor: str = ""
    ) -> BuildRecord:
        """Ghi nhận một bản KHÔNG đạt nghiệm thu vật lý.

        Tách khỏi ``rollback`` có chủ ý: ghi nhận thất bại và quay lui là hai
        việc, và bản ghi thất bại phải tồn tại kể cả khi kỹ sư quyết định sửa
        tiếp thay vì lùi.
        """
        if not reason.strip():
            raise VersionError(
                "Từ chối nghiệm thu bắt buộc kèm lý do — thất bại cũng là tri "
                "thức, và một dòng 'không đạt' trống rỗng thì không dạy được gì."
            )
        return self._append(
            BuildRecord(
                module=module,
                commit=commit,
                tier="",
                event="reject",
                at=_now(),
                reason=reason,
                actor=actor,
            )
        )

    def rollback(self, module: str, *, reason: str, actor: str = "") -> BuildRecord:
        """Đưa module về bản known-good gần nhất — TC-30.

        ``known_good.lock`` KHÔNG đổi: quay lui không phải một lần nghiệm thu.
        Bản đang được lùi về vốn đã là bản known-good rồi.
        """
        muc_tieu = self.known_good_of(module)
        if not muc_tieu:
            raise NoKnownGood(
                f"Chưa có bản known-good nào của {module!r} để quay lui về. "
                f"Bản known-good chỉ sinh ra khi có nghiệm thu tại {ACCEPTANCE_GATE}."
            )

        truoc = self.known_good()
        if self.repo is not None:
            self.repo.checkout(self.repo.main_branch)
            self.repo._git("checkout", muc_tieu, "--", ".")
            self.repo._git("add", "-A")
            if self.repo.has_changes() or self.repo._git("diff", "--cached", "--name-only"):
                self.repo._git(
                    "commit", "-q", "-m",
                    f"Quay lui {module} về bản known-good {muc_tieu[:8]}",
                    "-m", f"reason: {reason}\nrolled-back-by: {actor or '(không rõ)'}",
                )

        ban_ghi = self._append(
            BuildRecord(
                module=module,
                commit=muc_tieu,
                tier=Tier.HW_VERIFIED,
                event="rollback",
                at=_now(),
                reason=reason,
                actor=actor,
            )
        )

        # Bất biến của TC-30: khóa không đổi sau khi quay lui.
        assert self.known_good() == truoc, "rollback không được đụng vào known_good.lock"
        return ban_ghi

    # ----------------------------------------------------------------------
    # TC-31 — báo cáo phiên bản
    # ----------------------------------------------------------------------

    def status(self, module: str) -> dict[str, Any]:
        """Trạng thái phiên bản của một module."""
        ban_ghi = [r for r in self.records(module) if r.event == "promote"]
        hang_cao_nhat = ""
        for r in ban_ghi:
            if not hang_cao_nhat or TIER_ORDER.index(r.tier) >= TIER_ORDER.index(hang_cao_nhat):
                hang_cao_nhat = r.tier

        hw = [r for r in ban_ghi if r.tier == Tier.HW_VERIFIED]
        hien_tai = ban_ghi[-1].commit if ban_ghi else ""
        if self.repo is not None:
            try:
                hien_tai = self.repo.head()
            except Exception:  # pragma: no cover - kho chưa có commit
                pass

        return {
            "module": module,
            "current_commit": hien_tai,
            "tier": hang_cao_nhat,
            "known_good": self.known_good_of(module),
            "measurements": [str(m) for m in (hw[-1].measurements if hw else ())],
            "rollbacks": len([r for r in self.records(module) if r.event == "rollback"]),
            "rejections": len([r for r in self.records(module) if r.event == "reject"]),
        }

    def report(self, modules: Sequence[str] = ()) -> str:
        """Bảng module × (commit hiện tại, hạng, known-good, số đo) — TC-31."""
        ten = list(modules) or sorted({r.module for r in self.records() if r.module})
        if not ten:
            return "(chưa có bản build nào được ghi nhận)"

        dong = [
            f"{'module':<24}{'commit':<12}{'hạng':<15}{'known-good':<12}số đo kèm theo"
        ]
        dong.append("─" * 96)
        for m in ten:
            t = self.status(m)
            dong.append(
                f"{m:<24}{(t['current_commit'] or '—')[:10]:<12}"
                f"{t['tier'] or '—':<15}{(t['known_good'] or '—')[:10]:<12}"
                f"{', '.join(t['measurements']) or '—'}"
            )
            if t["rollbacks"] or t["rejections"]:
                dong.append(
                    f"    {t['rejections']} lần không đạt nghiệm thu, "
                    f"{t['rollbacks']} lần quay lui"
                )

        khoa = self.known_good()
        dong.append("")
        dong.append(
            f"Bản known-good của toàn firmware: {khoa.get('firmware') or '(chưa có)'}"
        )
        dong.append(
            f"Chỉ cập nhật tại {ACCEPTANCE_GATE} — một bản qua hết cổng máy vẫn "
            "chưa phải bản biết-là-tốt."
        )
        return "\n".join(dong)
