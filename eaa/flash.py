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
    "FlashApproval",
    "FlashApprovals",
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
    def confidence_level(self) -> str:
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


@dataclass(frozen=True)
class FlashApproval:
    """Một người đã duyệt nạp MỘT ảnh cụ thể."""

    image: str
    image_digest: str
    actor: str
    approved_at: str

    def to_dict(self) -> dict:
        return {
            "image": self.image,
            "image_digest": self.image_digest,
            "actor": self.actor,
            "approved_at": self.approved_at,
        }


class FlashApprovals:
    """Sổ duyệt ảnh nạp — nối tiếp, không ghi đè.

    Vì sao cần sổ thay vì một câu hỏi trên terminal
    -----------------------------------------------

    Cùng lý do đã dựng sổ duyệt lệnh cài (SL-110), và ở đây nặng hơn: nạp là
    chặng cuối của cả sản phẩm. Trước SL-119, `eaa flash` qua hết bốn phép kiểm
    trước rồi dừng ở *"chưa có xác nhận của người"* mà **không nêu lối đi
    tiếp** — không cờ, không lệnh, không sổ. Một phiên làm việc qua người trung
    gian không bao giờ nạp được, dù người có đồng ý bao nhiêu lần.

    Bất biến không đổi: không ảnh nào được nạp mà thiếu một người duyệt ĐÚNG
    ảnh ấy. Cái đổi là ai gõ phím lúc nạp.

    Neo vào **băm NỘI DUNG ảnh**, không vào đường dẫn: đường dẫn ghi đè được,
    nên neo vào nó thì *"duyệt ảnh này rồi nạp ảnh khác"* chỉ cần một lần ráp
    lại xen vào giữa — và bản ghi vẫn nói có người duyệt.
    """

    def __init__(self, path) -> None:
        self.path = Path(path)

    @staticmethod
    def digest(image) -> str:
        return "sha256:" + hashlib.sha256(Path(image).read_bytes()).hexdigest()

    def approve(self, image, *, by: str) -> "FlashApproval":
        if not by.strip():
            raise FlashError(
                "Phải ghi ai duyệt lần nạp này — một quyết định không có người "
                "chịu trách nhiệm thì không phải quyết định của con người "
                "(FR-GATE-01, FR-DIA-02)."
            )
        anh = Path(image)
        k = FlashApproval(
            image=anh.name,
            image_digest=self.digest(anh),
            actor=by.strip(),
            approved_at=_now(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(k.to_dict(), ensure_ascii=False) + "\n")
        return k

    def all(self) -> list["FlashApproval"]:
        """Dòng hỏng thì BỎ QUA — hỏng chỉ được đọc thành 'chưa duyệt'."""
        if not self.path.is_file():
            return []
        ra: list[FlashApproval] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                d = json.loads(dong)
                ra.append(FlashApproval(
                    image=str(d["image"]),
                    image_digest=str(d["image_digest"]),
                    actor=str(d["actor"]),
                    approved_at=str(d.get("approved_at", "")),
                ))
            except (ValueError, KeyError, TypeError):
                continue
        return ra

    def find(self, image) -> "FlashApproval | None":
        anh = Path(image)
        if not anh.is_file():
            return None
        bam = self.digest(anh)
        for k in self.all():
            if k.image_digest == bam:
                return k
        return None


@dataclass
class Flasher:
    """Nạp một ảnh firmware, sau khi kiểm và sau khi người xác nhận."""

    runner: Any
    #: Kho mã firmware — nguồn của commit và của phép kiểm "sạch".
    repo: Any = None
    log: FlashLog | None = None
    #: ``(tóm tắt) -> bool``. Mặc định hỏi trên terminal; không TTY thì từ chối.
    confirm: Callable[[str], bool] | None = None
    #: Sổ duyệt ảnh nạp. ``None`` nghĩa là KHÔNG CÓ SỔ — và không có sổ thì
    #: đường "người duyệt ngoài luồng, Agent nạp" đóng lại.
    approvals: Any = None
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
        if not self._hoi(tom_tat, image=anh):
            raise FlashNotConfirmed(
                "Chưa có xác nhận của người nên KHÔNG nạp (FR-DIA-02).\n"
                "Phiên không có terminal cũng tính là chưa xác nhận — một phiên "
                "không có người không được diễn giải thành một người đã đồng ý.\n"
                "\n"
                "Bạn duyệt ảnh này bằng lệnh sau, rồi chạy lại 'eaa flash':\n"
                f"    eaa flash approve --image {anh} --actor <tên bạn>\n"
                "Quyết định neo vào BĂM NỘI DUNG ảnh, nên ráp lại là phải "
                "duyệt lại."
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

    def da_duoc_duyet(self, image) -> Any:
        """Có ai duyệt ĐÚNG ảnh này chưa. Trả quyết định, hoặc ``None``."""
        if self.approvals is None:
            return None
        return self.approvals.find(image)

    def _hoi(self, tom_tat: str, image=None) -> bool:
        # Sổ trước: đây là đường của phiên không terminal, và là đường Agent đi.
        if image is not None:
            k = self.da_duoc_duyet(image)
            if k is not None:
                print(
                    f"\n  {k.actor} đã duyệt đúng ảnh này lúc {k.approved_at} "
                    f"({k.image_digest[:23]}…) — nạp"
                )
                return True
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
        """Đường dẫn ảnh, tính theo THƯ MỤC LÀM VIỆC của công cụ nạp.

        Phải ``resolve()`` cả hai vế trước khi so. Trước SL-119, hàm này chỉ
        xử lý vế tuyệt đối; một đường dẫn TƯƠNG ĐỐI được trả về nguyên si, rồi
        công cụ nạp diễn giải nó theo thư mục làm việc của nó — một thư mục
        khác. Kết quả: `file … is not readable: No such file or directory` cho
        một tệp đang nằm ngay đó.

        Sai im lặng theo kiểu khó lần nhất: đường dẫn in ra trong nhật ký thì
        đúng, chỉ có chỗ đứng để đọc nó là sai.
        """
        p = Path(duong_dan).resolve()
        g = Path(goc).resolve()
        return str(p.relative_to(g)) if p.is_relative_to(g) else str(p)


def _tom_tat_loi(bao_cao: Any) -> str:
    loi = getattr(bao_cao, "errors", []) or []
    return "; ".join(str(getattr(e, "message", e)) for e in loi[:3])
