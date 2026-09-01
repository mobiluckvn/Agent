"""Tầng Git — nhánh, commit truy vết được, và BẤT BIẾN MERGE.

EAA-SDD-03 §4 ("Bất biến quan trọng nhất"), EAA-SRS-01 NFR-01 và NFR-07,
EAA-AIS-05 §8.4. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-08.

Bất biến, nguyên văn EAA-SDD-03 §4: *hàm merge của orchestrator chỉ gọi được
khi ToolReport.passed == True cho toàn bộ chuỗi cổng VÀ gates.request("G3")
trả về approved — không tồn tại nhánh mã nào khác dẫn tới merge.*

Câu cuối là phần khó. Một câu lệnh ``if`` kiểm hai điều kiện rồi mới merge thì
đúng, nhưng nó không ngăn được ai đó ngày mai viết thêm một lối merge thứ hai
quên mất câu ``if`` ấy. Ở đây bất biến được cài theo cách khác:

* :meth:`GitRepo.merge` KHÔNG nhận cờ hay điều kiện. Nó đòi một
  :class:`MergeAuthorization`.
* :class:`MergeAuthorization` TỰ KIỂM LẠI bằng chứng ngay lúc được dựng: toàn
  bộ báo cáo cổng phải đạt, quyết định phải là G3 đã duyệt, và băm nội dung
  người đã duyệt phải khớp băm nội dung sắp merge.
* Vì thế "dựng được giấy phép" và "đủ điều kiện merge" là cùng một việc. Không
  có đường nào tới merge mà không đi qua chỗ kiểm.

Còn một khe hở nữa mà điều kiện của SDD chưa bịt: duyệt bản A rồi merge bản B.
Giấy phép mang theo băm nội dung, và ``merge`` đối chiếu băm ấy với thứ đang
thực sự nằm trên nhánh — nên khe hở đó cũng đóng.

Test ``tests/test_tc01_merge_invariant.py`` quét mã nguồn engine để chứng minh
mệnh đề "không tồn tại nhánh mã nào khác", cùng kiểu với TC-38.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eaa.gates import APPROVED, GateDecision
from eaa.tools.base import CodeArtifact, ToolReport

__all__ = [
    "GitError",
    "MergeNotAuthorized",
    "MergeAuthorization",
    "GitRepo",
    "authorize_merge",
    "MERGE_GATE",
]

#: Gate quyết định việc merge — G3, "review diff từng module".
MERGE_GATE = "G3"

_TRAILER_KEYS = ("prompt-hash", "model", "constraints-version", "chunk-ids")


class GitError(Exception):
    """Lệnh Git thất bại."""


class MergeNotAuthorized(Exception):
    """Không dựng được giấy phép merge — thiếu bằng chứng kiểm chứng hoặc chữ ký người."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class MergeAuthorization:
    """Giấy phép merge — vật thể duy nhất mở được :meth:`GitRepo.merge`.

    Dựng được vật thể này ĐỒNG NGHĨA với việc đã thỏa bất biến, vì nó tự kiểm
    lại toàn bộ bằng chứng nó mang theo. Không có chỗ nào để "tin rằng người
    gọi đã kiểm rồi".
    """

    module_id: str
    branch: str
    reports: tuple[ToolReport, ...]
    decision: GateDecision
    #: Băm nội dung nhánh (``GitRepo.diff_digest``) tại lúc xin phép. Chuỗi
    #: chứng minh chạy qua đây: con người duyệt một payload mang băm này →
    #: giấy phép đòi quyết định mang đúng băm ấy → ``merge`` đòi nhánh HIỆN
    #: TẠI vẫn băm ra đúng như vậy.
    content_digest: str
    issued_at: str = field(default_factory=_now)
    #: Bộ cổng BẮT BUỘC phải có mặt trong bằng chứng. Rỗng nghĩa là bên gọi
    #: không nêu, và khi ấy chỉ kiểm được "cổng nào có thì cổng ấy đạt".
    required_gates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reports:
            raise MergeNotAuthorized(
                f"Không có báo cáo cổng kiểm chứng nào cho {self.module_id!r}. "
                "Không mã nào đến tay người mà chưa qua kiểm chứng máy (NT2) — "
                "và không mã nào vào main mà không có bằng chứng đã kiểm."
            )

        hong = [r.gate for r in self.reports if not r.passed]
        if hong:
            raise MergeNotAuthorized(
                f"Các cổng sau chưa đạt cho {self.module_id!r}: {', '.join(hong)}. "
                "Merge chỉ xảy ra khi TOÀN BỘ ToolReport.passed (SDD §4, NFR-01)."
            )

        # Phủ ĐỦ, không chỉ "cái nào có thì cái ấy đạt".
        #
        # Hai phép kiểm này khác nhau, và khác nhau ở chỗ nguy hiểm: một bằng
        # chứng chỉ chứa mỗi cổng ``compile`` — đạt — vẫn thỏa phép kiểm phía
        # trên. "Toàn bộ ToolReport.passed" khi ấy đúng về mặt chữ nghĩa mà
        # rỗng về mặt nội dung, vì bộ báo cáo mới là thứ quyết định câu ấy có
        # nghĩa gì. Một cổng VẮNG MẶT là một loại lỗi không được kiểm, y hệt
        # một cổng trượt.
        if self.required_gates:
            co = {r.gate for r in self.reports}
            thieu = [g for g in self.required_gates if g not in co]
            if thieu:
                raise MergeNotAuthorized(
                    f"Bằng chứng cho {self.module_id!r} thiếu cổng "
                    f"{', '.join(thieu)}. Merge đòi bằng chứng PHỦ ĐỦ bộ cổng bắt "
                    "buộc, không chỉ đòi những cổng có mặt đều đạt — một cổng "
                    "vắng mặt là một loại lỗi không được kiểm (FR-VER-01, NFR-01)."
                )

        if self.decision.gate_id != MERGE_GATE:
            raise MergeNotAuthorized(
                f"Merge cần quyết định tại {MERGE_GATE}, nhận quyết định của "
                f"{self.decision.gate_id!r}. Duyệt một gate khác không mở được merge."
            )

        if self.decision.decision != APPROVED:
            raise MergeNotAuthorized(
                f"{MERGE_GATE} ở trạng thái {self.decision.decision!r} cho "
                f"{self.module_id!r} — chưa có phê duyệt của người."
            )

        if not self.content_digest:
            raise MergeNotAuthorized(
                f"Giấy phép merge cho {self.module_id!r} không neo vào nội dung "
                "nào. Một giấy phép không nói rõ nó cho phép merge CÁI GÌ thì "
                "cho phép merge bất cứ thứ gì."
            )

        if self.decision.content_digest != self.content_digest:
            raise MergeNotAuthorized(
                f"Nội dung được duyệt tại {MERGE_GATE} không phải nội dung sắp "
                f"merge (đã duyệt {self.decision.content_digest}, sắp merge "
                f"{self.content_digest}). Duyệt bản này rồi merge bản khác là "
                "đúng thứ bất biến này sinh ra để ngăn."
            )

    @property
    def gates_passed(self) -> tuple[str, ...]:
        return tuple(r.gate for r in self.reports)

    def summary(self) -> str:
        return (
            f"{self.module_id}: {len(self.reports)} cổng đạt "
            f"({', '.join(self.gates_passed)}); {MERGE_GATE} duyệt bởi "
            f"{self.decision.actor} lúc {self.decision.decided_at}"
        )


def authorize_merge(
    *,
    module_id: str,
    branch: str,
    reports: Sequence[ToolReport],
    decision: GateDecision | None,
    content_digest: str,
    required_gates: Sequence[str] = (),
) -> MergeAuthorization:
    """Dựng giấy phép merge; ném :class:`MergeNotAuthorized` nếu chưa đủ điều kiện.

    Đây là cửa duy nhất. Việc nó chỉ gói lại lời gọi hàm dựng là có chủ ý — mọi
    phép kiểm nằm trong hàm dựng để không ai dựng được giấy phép mà bỏ qua kiểm.
    """
    if decision is None:
        raise MergeNotAuthorized(
            f"Chưa có quyết định nào tại {MERGE_GATE} cho {module_id!r}. "
            f"Chạy 'eaa gate show' rồi 'eaa gate approve {MERGE_GATE}'."
        )
    return MergeAuthorization(
        module_id=module_id,
        branch=branch,
        reports=tuple(reports),
        decision=decision,
        content_digest=content_digest,
        required_gates=tuple(required_gates),
    )


class GitRepo:
    """Bọc các lệnh Git mà quy trình cần.

    Git là nguồn sự thật duy nhất về phiên bản mã (AIS §8.4); module này không
    dựng thêm một sổ sách song song nào.
    """

    def __init__(self, root: str | Path, *, main_branch: str = "main") -> None:
        self.root = Path(root)
        self.main_branch = main_branch

    # -- lệnh nền ----------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> str:
        ket_qua = subprocess.run(
            ["git", *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        if check and ket_qua.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} thất bại (mã {ket_qua.returncode}):\n"
                f"{(ket_qua.stderr or ket_qua.stdout).strip()}"
            )
        return (ket_qua.stdout or "").strip()

    # -- khởi tạo và tra cứu ----------------------------------------------

    def exists(self) -> bool:
        return (self.root / ".git").is_dir()

    def init(self, *, actor: str = "Embedded AIDD Agent", email: str = "eaa@localhost") -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.exists():
            self._git("init", "-q", "-b", self.main_branch)
            self._git("config", "user.name", actor)
            self._git("config", "user.email", email)
            gitkeep = self.root / ".gitkeep"
            gitkeep.write_text("", encoding="utf-8")
            self._git("add", ".gitkeep")
            self._git("commit", "-q", "-m", "Khởi tạo kho firmware")
        self._bo_qua_san_pham_dich()

    #: Sản phẩm dịch — dẫn xuất từ mã nguồn, không thuộc lịch sử.
    #:
    #: Ba mục sau đến từ cổng kiểm trên máy chủ (SL-134): nó dịch mã C thành
    #: thư viện dùng chung rồi gọi bằng Python, nên mỗi lần chạy sinh ra
    #: ``tests/__pycache__/`` và ``tests/*.so`` NGAY TRONG kho firmware. Danh
    #: sách này không được nới theo, nên chúng lọt vào commit của module và vào
    #: đúng bản diff người phải đọc ở G3 — vài trăm dòng nhị phân xen giữa mã
    #: cần review. Và lần chạy sau, một tệp .pyc đổi nội dung đủ để chặn
    #: ``git checkout`` và làm hỏng cả lượt sinh (SL-136).
    BUILD_DIRS: tuple[str, ...] = ("build/", "__pycache__/", "*.pyc", "*.so")

    def _bo_qua_san_pham_dich(self) -> None:
        """Loại thư mục build khỏi tầm nhìn của Git, bằng .git/info/exclude.

        Không dùng ``.gitignore``: tệp ấy phải được commit, mà commit thêm vào
        một kho đang ở giữa một nhánh module là chen vào việc của người khác.
        ``info/exclude`` là chỗ đúng cho loại trừ cục bộ.

        Vì sao cần: ``eaa build`` ghi vào ``firmware/build/``, nên nếu Git vẫn
        thấy thư mục ấy thì kho LUÔN "bẩn" sau mỗi lần ráp — và phép kiểm "kho
        sạch trước khi nạp" sẽ chặn mọi lần nạp, kể cả những lần hoàn toàn hợp
        lệ. Một phép kiểm luôn báo động là một phép kiểm sẽ bị tắt.
        """
        loai_tru = self.root / ".git" / "info" / "exclude"
        if not loai_tru.parent.is_dir():
            return
        hien_co = loai_tru.read_text(encoding="utf-8") if loai_tru.is_file() else ""
        thieu = [d for d in self.BUILD_DIRS if d not in hien_co.split()]
        if thieu:
            loai_tru.write_text(
                hien_co.rstrip("\n") + "\n" + "\n".join(thieu) + "\n"
                if hien_co.strip()
                else "\n".join(thieu) + "\n",
                encoding="utf-8",
            )

    def current_branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD")

    def head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def branches(self) -> list[str]:
        ra = self._git("for-each-ref", "--format=%(refname:short)", "refs/heads")
        return [b for b in ra.splitlines() if b]

    def has_changes(self) -> bool:
        return bool(self._git("status", "--porcelain"))

    def files_on_main(self) -> frozenset[str]:
        """Những tệp đang nằm trên nhánh chính — tức mã ĐÃ QUA G3 và đã merge.

        Dùng để trả lời đúng một câu: tệp này có phải tài sản của một module
        khác đã được người duyệt hay không (SL-154). Trả về rỗng khi kho chưa
        có nhánh chính — lúc ấy chưa có gì để bảo vệ.
        """
        try:
            ra = self._git("ls-tree", "-r", "--name-only", self.main_branch)
        except GitError:
            return frozenset()
        return frozenset(d for d in ra.splitlines() if d)

    # -- nhánh -------------------------------------------------------------

    def branch_for(self, module_id: str) -> str:
        """Quy ước nhánh của AIS §8.4: mỗi module một nhánh ngắn."""
        return f"feature/{module_id}"

    def checkout(self, branch: str, *, create: bool = False) -> None:
        if create and branch not in self.branches():
            self._git("checkout", "-q", "-b", branch)
        else:
            self._git("checkout", "-q", branch)

    def start_module(self, module_id: str) -> list[str]:
        """Về nhánh chính rồi mở nhánh làm việc cho module.

        Dọn mã sinh ra còn sót TRƯỚC khi đổi nhánh. Một lượt sinh hỏng giữa
        chừng — vòng vá không trả về khối nào, cổng dịch đỏ — để lại `src/` và
        `tests/` đầy tệp chưa commit, và lượt sau chết ngay ở bước đầu::

            Lỗi: git checkout -q main thất bại (mã 1):
            error: Your local changes would be overwritten by checkout

        Câu ấy bảo người dùng đi "commit or stash" mã mà **chính Agent vừa
        viết hỏng**, và không nói ra điều đó. Gặp bốn lần trong một buổi
        (SL-151).

        Xóa được vì đây là kho SẢN PHẨM SINH: mọi thứ chưa commit trong đó là
        rác của lượt trước, không phải công của ai. Nhưng vẫn TRẢ VỀ danh sách
        đã xóa — dọn dẹp im lặng là cách một tệp người ta sửa tay biến mất mà
        không ai biết.
        """
        branch = self.branch_for(module_id)
        da_don: list[str] = []
        try:
            self.checkout(self.main_branch)
        except GitError:
            # CHỈ dọn khi việc đổi nhánh thật sự bị chặn.
            #
            # Bản đầu dọn vô điều kiện, và nó xóa cả tệp người khác đặt sẵn
            # trong kho firmware — một bài kiểm viết tay chẳng hạn. "Mọi thứ
            # chưa commit là rác của lượt trước" là một nhận định quá mạnh:
            # đúng với phần lớn trường hợp, sai với đúng trường hợp gây thiệt
            # hại. Thử trước, chỉ dọn khi buộc phải.
            da_don = self._don_rac_luot_truoc()
            self.checkout(self.main_branch)
        self.checkout(branch, create=True)
        return da_don

    def _don_rac_luot_truoc(self) -> list[str]:
        """Hoàn tác mã sinh còn sót. Trả về danh sách tệp đã đụng tới."""
        trang_thai = self._git("status", "--porcelain")
        if not trang_thai.strip():
            return []
        ten = [d[3:].strip() for d in trang_thai.splitlines() if len(d) > 3]
        self._git("checkout", "--", ".")
        return ten

    # -- commit ------------------------------------------------------------

    def commit_artifact(
        self,
        artifact: CodeArtifact,
        *,
        module_id: str,
        subject: str = "",
        extra_trailers: dict[str, str] | None = None,
    ) -> str:
        """Commit mã sinh ra kèm đủ dấu vết của NFR-07.

        Bốn thành phần (prompt hash, model, phiên bản ràng buộc, mã chunk) là
        thứ khiến một prompt tái lập được từ commit — đóng vòng truy vết hai
        chiều tri thức ⇄ mã (AIS §3.3, §8.4).
        """
        self._git("add", "-A")
        if not self._git("diff", "--cached", "--name-only"):
            raise GitError("Không có thay đổi nào để commit")

        thieu = [
            ten
            for ten, gia_tri in (
                ("prompt-hash", artifact.prompt_hash),
                ("model", artifact.model),
                ("constraints-version", artifact.constraints_version),
            )
            if not gia_tri
        ]
        if thieu:
            raise GitError(
                f"Artifact thiếu dấu vết bắt buộc {thieu} — NFR-07 đòi mọi mã "
                "sinh ra phải truy vết được về prompt, mô hình và phiên bản ràng buộc."
            )

        trailers = {
            "prompt-hash": artifact.prompt_hash,
            "model": artifact.model,
            "constraints-version": artifact.constraints_version,
            "chunk-ids": ",".join(artifact.chunk_ids) or "(không có)",
            "tokens-in": str(artifact.tokens_in),
            "tokens-out": str(artifact.tokens_out),
            **(extra_trailers or {}),
        }
        than = "\n".join(f"{k}: {v}" for k, v in trailers.items())
        tieu_de = subject or f"{module_id}: mã sinh bởi quy trình AIDD"

        self._git("commit", "-q", "-m", tieu_de, "-m", than)
        return self.head()

    def commit_message(self, rev: str = "HEAD") -> str:
        return self._git("log", "-1", "--format=%B", rev)

    def diff(self, base: str | None = None, *, stat: bool = False) -> str:
        goc = base or self.main_branch
        args = ["diff", f"{goc}...HEAD"]
        if stat:
            args.append("--stat")
        return self._git(*args)

    # -- merge -------------------------------------------------------------

    def merge(self, authorization: MergeAuthorization) -> str:
        """Merge nhánh module vào nhánh chính. **Cửa duy nhất dẫn tới merge.**

        Không có tham số nào cho phép bỏ qua kiểm tra. Giấy phép đã tự kiểm khi
        được dựng; ở đây kiểm thêm rằng nội dung trên nhánh vẫn đúng là nội
        dung đã được duyệt — giữa lúc duyệt và lúc merge, nhánh có thể đã đổi.
        """
        if not isinstance(authorization, MergeAuthorization):
            raise MergeNotAuthorized(
                "merge() chỉ nhận MergeAuthorization. Không có dạng gọi nào khác — "
                "đây là bất biến của EAA-SDD-03 §4."
            )

        # Dựng lại phép kiểm một lần nữa. Thừa nếu giấy phép vừa được tạo; không
        # thừa nếu nó được cất đi rồi dùng lại sau, hoặc bị sửa trên đường đi.
        MergeAuthorization(
            module_id=authorization.module_id,
            branch=authorization.branch,
            reports=authorization.reports,
            decision=authorization.decision,
            content_digest=authorization.content_digest,
        )

        hien_tai = self.diff_digest(authorization.branch)
        if hien_tai != authorization.content_digest:
            raise MergeNotAuthorized(
                f"Nhánh {authorization.branch} đã thay đổi kể từ khi được duyệt tại "
                f"{MERGE_GATE} (đã duyệt {authorization.content_digest}, hiện "
                f"{hien_tai}). Đưa bản mới qua gate lại."
            )

        self.checkout(self.main_branch)
        self._git(
            "merge",
            "--no-ff",
            authorization.branch,
            "-m",
            f"Merge {authorization.branch}\n\n{authorization.summary()}\n"
            f"gate-decision: {MERGE_GATE} approved by {authorization.decision.actor}\n"
            f"gates-passed: {', '.join(authorization.gates_passed)}",
        )
        return self.head()

    def diff_digest(self, branch: str) -> str:
        """Băm nội dung một nhánh so với nhánh chính — neo cho giấy phép merge."""
        import hashlib

        noi_dung = self._git("diff", f"{self.main_branch}...{branch}")
        return "sha256:" + hashlib.sha256(noi_dung.encode("utf-8")).hexdigest()

    # -- phiên bản chất lượng (AIS §8.4) ----------------------------------

    def tag(self, name: str, *, message: str = "") -> None:
        if message:
            self._git("tag", "-a", name, "-m", message)
        else:
            self._git("tag", name)

    def tags(self) -> list[str]:
        return [t for t in self._git("tag").splitlines() if t]
