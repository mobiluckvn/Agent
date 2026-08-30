"""Nạp firmware xuống thiết bị thật.

EAA-SRS-01 FR-DIA-02 (nạp firmware LUÔN cần người xác nhận), EAA-AIS-05 §7.3,
§9.4. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-33.

Đây là chỗ Agent chạm vào phần cứng. Mọi bất biến của bốn sprint trước — cổng
kiểm chứng, Human Gate, truy vết commit — đều quy về câu hỏi một dòng ở đây:
*thứ sắp chạy trên con chip kia có đúng là thứ đã được kiểm và được duyệt không?*

Bốn phép kiểm trước khi nạp, và cả bốn đều là "không" chứ không phải "cảnh báo"
--------------------------------------------------------------------------------

1. **Có ảnh để nạp.** Chưa ráp thì không có gì để nói.
2. **Kho mã sạch.** Còn thay đổi chưa commit thì câu "đã nạp commit X" là câu
   sai — thứ trên bàn không phải thứ trong Git, và bản ghi nạp sẽ nói dối cho
   tới tận lúc bảo vệ.
3. **Ảnh mới hơn nguồn.** Sửa mã rồi nạp mà quên ráp lại là cách hỏng âm thầm
   nhất: mạch chạy mã cũ, người đọc mã mới, và mọi suy luận sau đó đều lệch.
4. **Người xác nhận.** Không phải TTY thì KHÔNG nạp. Một phiên không có người
   không được diễn giải thành một người đã đồng ý — cùng nguyên tắc với Human
   Gate, và ở đây hậu quả là vật lý.

Nạp xong chưa phải là xong (N-075)
-----------------------------------

Một mạch nạp trả mã thoát 0 mới chỉ nói *nó đã gửi xong*, chứ chưa nói *thứ nằm
trên chip đúng bằng thứ đã gửi*. Khoảng cách giữa hai câu ấy là chỗ mà dây tín
hiệu chập chờn, nguồn yếu, hay một khối flash mòn sẽ lọt qua — và lọt qua im
lặng, vì mọi lớp phía trên đều đọc mã thoát 0 là "đạt".

Nên sau mỗi lần nạp thành công, Agent đọc ngược bộ nhớ và so với ảnh, qua năng
lực ``flash_verify`` của pack. Ba kết cục, và cả ba đều được nói thẳng:

* ``khop``            — đã đọc ngược và trùng khớp. Đây là câu *đã kiểm*.
* ``lech``            — đọc ngược và KHÔNG khớp. Lần nạp bị coi là trượt.
* ``khong-kiem-duoc`` — mạch nạp không hỗ trợ, hoặc thiếu công cụ. Bản ghi nói
  rõ là chưa kiểm, chứ không mượn mã thoát của bước nạp làm bằng chứng.

Kết cục thứ ba là lý do chính khiến phần này tồn tại. Sự cám dỗ là để trống và
coi như đạt; hậu quả là mọi số đo sau đó gắn vào một giả định chưa ai kiểm.

Bản ghi nạp là append-only
---------------------------

Mỗi lần nạp ghi lại: commit nào, ảnh nào (kèm băm), cổng nào, ai xác nhận, lúc
nào, và kiểm sau khi nạp ra sao. Khi một thí nghiệm ở Chương 3 cho số lạ, câu
đầu tiên phải trả lời được là "hôm ấy trên mạch đang chạy bản nào" — và nó phải
trả lời được mà không cần ai nhớ.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "FlashError",
    "FlashNotConfirmed",
    "FlashRecord",
    "FlashLog",
    "Flasher",
    "PreflightResult",
    "VerifyResult",
    "VERIFY_KHOP",
    "VERIFY_LECH",
    "VERIFY_KHONG_KIEM_DUOC",
]

#: Nhật ký nạp, cạnh Project State.
FLASH_LOG = "flash_log.jsonl"

#: Đã đọc ngược bộ nhớ và nội dung trùng ảnh đã gửi — câu "đã kiểm".
VERIFY_KHOP = "khop"
#: Đã đọc ngược và KHÔNG trùng. Lần nạp bị coi là trượt.
VERIFY_LECH = "lech"
#: Chưa đọc ngược được: pack không khai năng lực, hoặc thiếu công cụ trên máy.
VERIFY_KHONG_KIEM_DUOC = "khong-kiem-duoc"


class FlashError(Exception):
    """Không nạp được, hoặc điều kiện tiên quyết không thỏa."""


class FlashNotConfirmed(FlashError):
    """Không có người xác nhận — FR-DIA-02."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bam_tep(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    """Kết quả đọc ngược bộ nhớ sau khi nạp (N-075).

    ``checked`` tách khỏi ``ok`` có chủ ý: "chưa kiểm" và "đã kiểm và hỏng" là
    hai điều khác hẳn nhau, gộp chúng vào một cờ nhị phân là đúng chỗ mà thông
    tin bị mất.
    """

    status: str
    detail: str = ""

    @property
    def checked(self) -> bool:
        """Đã thật sự đọc ngược bộ nhớ chưa."""
        return self.status in (VERIFY_KHOP, VERIFY_LECH)

    @property
    def ok(self) -> bool:
        """Có bằng chứng thứ trên chip đúng bằng thứ đã gửi không."""
        return self.status == VERIFY_KHOP

    @property
    def confidence(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903)."""
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC

        return DA_KIEM if self.status == VERIFY_KHOP else KHONG_KIEM_DUOC

    def render(self) -> str:
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC

        if self.status == VERIFY_KHOP:
            return f"Kiểm sau khi nạp: {DA_KIEM} — đọc ngược khớp ảnh. {self.detail}".strip()
        if self.status == VERIFY_LECH:
            return f"Kiểm sau khi nạp: KHÔNG KHỚP — {self.detail}"
        return (
            f"Kiểm sau khi nạp: {KHONG_KIEM_DUOC} — "
            f"{self.detail}\n"
            "    'Nạp không báo lỗi' KHÔNG có nghĩa là 'nạp đúng'. Mọi số đo "
            "lấy về sau đây dựa trên một giả định chưa ai kiểm."
        )


@dataclass(frozen=True)
class FlashRecord:
    """Một lần nạp đã xảy ra."""

    image: str
    image_digest: str
    commit: str
    port: str
    actor: str
    flashed_at: str
    passed: bool
    programmer: str = ""
    note: str = ""
    #: Kết cục của phép đọc ngược — xem :class:`VerifyResult`.
    verify_status: str = VERIFY_KHONG_KIEM_DUOC
    verify_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "image_digest": self.image_digest,
            "commit": self.commit,
            "port": self.port,
            "actor": self.actor,
            "flashed_at": self.flashed_at,
            "passed": self.passed,
            "programmer": self.programmer,
            "note": self.note,
            "verify_status": self.verify_status,
            "verify_detail": self.verify_detail,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlashRecord":
        return cls(
            image=str(d.get("image", "")),
            image_digest=str(d.get("image_digest", "")),
            commit=str(d.get("commit", "")),
            port=str(d.get("port", "")),
            actor=str(d.get("actor", "")),
            flashed_at=str(d.get("flashed_at", "")),
            passed=bool(d.get("passed", False)),
            programmer=str(d.get("programmer", "")),
            note=str(d.get("note", "")),
            # Bản ghi cũ (trước N-075) không có trường này. Mặc định phải là
            # "không kiểm được" chứ không phải "khớp": suy diễn ngược lại sẽ
            # gán một bằng chứng chưa từng tồn tại cho các lần nạp đã qua.
            verify_status=str(d.get("verify_status", VERIFY_KHONG_KIEM_DUOC)),
            verify_detail=str(d.get("verify_detail", "")),
        )

    @property
    def verified(self) -> bool:
        """Có bằng chứng đọc ngược khớp không."""
        return self.verify_status == VERIFY_KHOP

    def render(self) -> str:
        ket = "ĐẠT" if self.passed else "KHÔNG ĐẠT"
        nhan_kiem = {
            VERIFY_KHOP: "đã kiểm",
            VERIFY_LECH: "ĐỌC NGƯỢC LỆCH",
        }.get(self.verify_status, "chưa kiểm")
        return (
            f"{self.flashed_at}  {ket:<10} commit {self.commit[:10]}  "
            f"cổng {self.port}  người {self.actor}  [{nhan_kiem}]"
        )


class FlashLog:
    """Nhật ký nạp — append-only, giống mọi kho tri thức khác của hệ thống."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def append(self, record: FlashRecord) -> FlashRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def all(self) -> list[FlashRecord]:
        if not self.path.is_file():
            return []
        ket_qua: list[FlashRecord] = []
        for so, dong in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            dong = dong.strip()
            if not dong:
                continue
            try:
                ket_qua.append(FlashRecord.from_dict(json.loads(dong)))
            except json.JSONDecodeError as exc:
                raise FlashError(f"{self.path}:{so}: bản ghi hỏng — {exc}") from exc
        return ket_qua

    def last_success(self) -> FlashRecord | None:
        for r in reversed(self.all()):
            if r.passed:
                return r
        return None


@dataclass
class PreflightResult:
    """Kết quả bốn phép kiểm trước khi nạp."""

    ok: bool
    problems: list[str] = field(default_factory=list)
    image: Path | None = None
    commit: str = ""

    def render(self) -> str:
        if self.ok:
            return "Kiểm trước khi nạp: đạt."
        return "Không nạp được:\n" + "\n".join(f"  · {v}" for v in self.problems)


@dataclass
class Flasher:
    """Nạp một ảnh firmware, sau khi kiểm và sau khi người xác nhận."""

    runner: Any
    #: Kho mã firmware — nguồn của commit và của phép kiểm "sạch".
    repo: Any = None
    log: FlashLog | None = None
    #: ``(tóm tắt) -> bool``. Mặc định hỏi trên terminal; không TTY thì từ chối.
    confirm: Callable[[str], bool] | None = None
    #: Nguồn để so "ảnh có mới hơn mã không".
    source_dir: Path | None = None
    source_suffixes: tuple[str, ...] = (".c", ".h")
    #: Thư mục bỏ qua khi so mốc thời gian — sản phẩm dịch sinh sau, không phải
    #: nguồn; đưa chúng vào phép so thì ảnh sẽ luôn "cũ hơn chính nó".
    skip_dirs: tuple[str, ...] = ("build",)

    def preflight(self, image: str | Path) -> PreflightResult:
        van_de: list[str] = []
        image = Path(image)

        if not image.is_file():
            van_de.append(
                f"Không có ảnh để nạp: {image}. Chạy 'eaa build' trước."
            )
            return PreflightResult(ok=False, problems=van_de)

        commit = ""
        if self.repo is not None:
            try:
                commit = self.repo.head()
            except Exception as exc:  # kho chưa có commit nào
                van_de.append(f"Không đọc được commit hiện tại: {exc}")
            if self._kho_ban():
                van_de.append(
                    "Kho firmware còn thay đổi chưa commit. Nạp lúc này thì bản "
                    "ghi 'đã nạp commit X' là câu sai — thứ trên bàn không phải "
                    "thứ trong Git, và sai lệch ấy sẽ đi theo tới tận lúc bảo vệ."
                )

        cu_hon = self._nguon_moi_hon(image)
        if cu_hon:
            van_de.append(
                f"Ảnh cũ hơn mã nguồn ({', '.join(cu_hon[:3])}"
                f"{'…' if len(cu_hon) > 3 else ''}). Ráp lại: 'eaa build'.\n"
                "    Nạp ảnh cũ là cách hỏng âm thầm nhất: mạch chạy mã cũ, "
                "người đọc mã mới."
            )

        return PreflightResult(
            ok=not van_de, problems=van_de, image=image, commit=commit
        )

    def run(
        self,
        image: str | Path,
        *,
        port: str,
        actor: str,
        params: dict[str, Any] | None = None,
        programmer: str = "",
        extra_notes: Sequence[str] = (),
    ) -> FlashRecord:
        kiem = self.preflight(image)
        if not kiem.ok:
            raise FlashError(kiem.render())
        if not actor.strip():
            raise FlashNotConfirmed(
                "Nạp firmware phải ghi tên người chịu trách nhiệm (FR-DIA-02)."
            )
        if not port.strip():
            raise FlashError("Chưa chỉ cổng để nạp. Xem 'eaa ports'.")

        anh = kiem.image
        assert anh is not None
        tom_tat = (
            f"Sắp NẠP xuống thiết bị thật:\n"
            f"    ảnh    : {anh}\n"
            f"    băm    : {_bam_tep(anh)}\n"
            f"    commit : {kiem.commit or '(không rõ)'}\n"
            f"    cổng   : {port}\n"
            f"    người  : {actor}"
        )
        if extra_notes:
            tom_tat += "\n" + "\n".join(extra_notes)
        if not self._hoi(tom_tat):
            raise FlashNotConfirmed(
                "Chưa có xác nhận của người nên KHÔNG nạp (FR-DIA-02).\n"
                "Phiên không có terminal cũng tính là chưa xác nhận — một phiên "
                "không có người không được diễn giải thành một người đã đồng ý."
            )

        goc = Path(self.runner.work_dir)
        tham_so = {
            **(params or {}),
            "port": port,
            "binary": self._tuong_doi(anh, goc),
        }
        bao_cao = self.runner.run(
            "flash", tham_so, gate_name="flash", confirmed_by=actor
        )

        # Đọc ngược chỉ có nghĩa khi bước gửi đã xong. Nạp trượt rồi mà vẫn đi
        # so nội dung thì cái "lệch" đọc được chỉ là hệ quả của lần trượt ấy,
        # không phải một dữ kiện mới.
        kiem_sau = (
            self.verify(anh, tham_so)
            if bao_cao.passed
            else VerifyResult(
                VERIFY_KHONG_KIEM_DUOC, "bước nạp đã trượt nên không đọc ngược."
            )
        )

        ban_ghi = FlashRecord(
            image=str(anh),
            image_digest=_bam_tep(anh),
            commit=kiem.commit,
            port=port,
            actor=actor,
            flashed_at=_now(),
            # Đọc ngược lệch thì lần nạp này KHÔNG đạt, dù công cụ nạp đã trả
            # về 0. Đây là toàn bộ điểm của N-075: mã thoát của công cụ nạp
            # không phải bằng chứng về nội dung nằm trên chip.
            passed=bao_cao.passed and kiem_sau.status != VERIFY_LECH,
            programmer=programmer,
            note=(
                _tom_tat_loi(bao_cao)
                if not bao_cao.passed
                else (kiem_sau.detail if kiem_sau.status == VERIFY_LECH else "")
            ),
            verify_status=kiem_sau.status,
            verify_detail=kiem_sau.detail,
        )
        if self.log is not None:
            # Ghi cả lần nạp HỎNG: "đã thử nạp và trượt" là dữ kiện cần cho
            # chẩn đoán y như "đã nạp xong".
            self.log.append(ban_ghi)
        return ban_ghi

    def verify(self, image: str | Path, params: dict[str, Any] | None = None) -> VerifyResult:
        """Đọc ngược bộ nhớ chương trình và so với ảnh vừa nạp (N-075).

        Không ném ngoại lệ: mọi kết cục — kể cả "không kiểm được" — là một dữ
        kiện phải đi vào bản ghi nạp. Ném ra ngoài thì lần nạp mất luôn phần
        ghi chép, mà thứ đã nằm trên chip thì vẫn nằm đó.
        """
        image = Path(image)
        manifest = getattr(self.runner, "manifest", None)

        if manifest is None or not manifest.has("flash_verify"):
            ten = getattr(manifest, "name", "?")
            return VerifyResult(
                VERIFY_KHONG_KIEM_DUOC,
                f"pack {ten!r} không khai năng lực 'flash_verify' — mạch nạp "
                "này không đọc ngược được, hoặc pack chưa khai cách đọc.",
            )

        if hasattr(self.runner, "available") and not self.runner.available("flash_verify"):
            return VerifyResult(
                VERIFY_KHONG_KIEM_DUOC,
                "thiếu công cụ đọc ngược trên máy này. Chạy 'eaa doctor'.",
            )

        goc = Path(self.runner.work_dir)
        tham_so = {**(params or {}), "binary": self._tuong_doi(image, goc)}
        try:
            bao_cao = self.runner.run("flash_verify", tham_so, gate_name="flash_verify")
        except Exception as exc:  # lắp lệnh sai, thiếu tham số của pack…
            return VerifyResult(
                VERIFY_KHONG_KIEM_DUOC, f"không chạy được phép đọc ngược: {exc}"
            )

        if bao_cao.metrics.get("env_error"):
            return VerifyResult(
                VERIFY_KHONG_KIEM_DUOC,
                f"thiếu công cụ {bao_cao.metrics.get('missing_tool', '?')} trên máy này.",
            )
        if bao_cao.passed:
            return VerifyResult(
                VERIFY_KHOP, f"({image.name}, băm {_bam_tep(image)[:19]}…)"
            )
        return VerifyResult(
            VERIFY_LECH,
            "nội dung đọc về từ chip KHÔNG trùng ảnh đã gửi: "
            + (_tom_tat_loi(bao_cao) or "công cụ báo không khớp"),
        )

    # -- phần bên trong -----------------------------------------------------

    def _hoi(self, tom_tat: str) -> bool:
        if self.confirm is not None:
            return bool(self.confirm(tom_tat))
        if not sys.stdin.isatty():
            return False
        print("\n" + tom_tat)
        return input("  Xác nhận nạp? [y/N]: ").strip().lower() in ("y", "yes", "c", "có")

    def _kho_ban(self) -> bool:
        for ten in ("is_dirty", "has_changes"):
            ham = getattr(self.repo, ten, None)
            if callable(ham):
                return bool(ham())
        return False

    def _nguon_moi_hon(self, image: Path) -> list[str]:
        if self.source_dir is None:
            return []
        thu_muc = Path(self.source_dir)
        if not thu_muc.is_dir():
            return []
        moc = image.stat().st_mtime
        moi_hon = [
            str(p.relative_to(thu_muc))
            for p in sorted(thu_muc.rglob("*"))
            if p.suffix in self.source_suffixes
            and p.is_file()
            and not set(p.relative_to(thu_muc).parts) & set(self.skip_dirs)
            and p.stat().st_mtime > moc
        ]
        return moi_hon

    @staticmethod
    def _tuong_doi(duong_dan: Path, goc: Path) -> str:
        p = Path(duong_dan)
        return str(p.relative_to(goc)) if p.is_absolute() and p.is_relative_to(goc) else str(p)


def _tom_tat_loi(bao_cao: Any) -> str:
    loi = getattr(bao_cao, "errors", []) or []
    return "; ".join(str(getattr(e, "message", e)) for e in loi[:3])
