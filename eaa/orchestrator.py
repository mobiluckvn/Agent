"""Orchestrator — máy trạng thái và vòng lặp sinh mã chuẩn 13 bước.

EAA-SAD-02 §4 (Hình 2 máy trạng thái, Hình 3 sequence 13 bước),
EAA-SDD-03 §4, EAA-SRS-01 FR-ORC-01/02, FR-GEN-01, UC04.

Mười ba bước, và chỗ chúng nằm trong mã này:

===  =====================================================  =====================
 1   Kỹ sư yêu cầu sinh module (backlog đã duyệt G1)         :meth:`run_module`
 2   Tra Policy Engine → mức phân quyền                      :meth:`_tra_policy`
 3   Giao nhiệm vụ + Project State cho Composer              :meth:`_dung_task`
 4   Composer ghép prompt từ Knowledge Base                  ``composer.build``
 5   LLM sinh mã                                             :meth:`_sinh_ma`
 6   compile → size → static → unit → mô phỏng               :meth:`_chay_chuoi_cong`
 7   [hỏng] báo lỗi chi tiết cho LLM                         :meth:`_va_loi`
 8   Nhận bản vá, quay lại bước 6 (≤ N lần)                   vòng trong ``run_module``
 9   [đạt] commit + diff + báo cáo build                     :meth:`_commit`
10   Gửi diff chờ phê duyệt tại G3                           :meth:`_xin_gate`
11   approve → merge / reject → lý do vào Error Ledger       :meth:`finalize_module`
12   Ghi KPI                                                 rải khắp, qua ``kpi``
13   Báo hoàn tất, chuyển module kế tiếp                     giá trị trả về
===  =====================================================  =====================

Vòng lặp cố ý DỪNG ở bước 10 và trả điều khiển về cho con người. Bước 11–13
chạy trong :meth:`finalize_module`, được gọi sau khi người đã quyết định bằng
``eaa gate approve|reject``. Không có chế độ nào nối liền bước 10 sang 11 —
đó chính là chỗ ADR-04 muốn máy phải dừng lại.

**Cách đọc "N = 3"**: N là số vòng TỰ SỬA, không phải tổng số lần gọi mô hình.
Một module hỏng đến cùng sẽ có 1 lần sinh đầu + 3 lần vá = 4 lần gọi mô hình
và 4 lượt chạy chuỗi cổng. Cách đọc này theo EAA-AIS-05 §3.2 ("ở các vòng tự
sửa… ≤ N = 3 lần") và FR-GEN-01 ("giới hạn tự sửa N"). Ghi rõ ở đây vì TC-06
chỉ nói "đúng 3 lần thử", và hai cách hiểu cho hai con số khác nhau.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_REPAIR_LIMIT, EXIT_WAITING_GATE
from eaa.composer import Task
from eaa.gates import APPROVED, REJECTED, GatePayload
from eaa.policy import PHASE_NAMES, GATE_PURPOSE, Level, check_transition, level
from eaa.tools.base import CodeArtifact, ToolReport
from eaa.vcs import MERGE_GATE, MergeNotAuthorized, authorize_merge

__all__ = [
    "OrchestratorError",
    "PreconditionFailed",
    "OrchestratorConfig",
    "ModuleOutcome",
    "Orchestrator",
    "GENERATION_PHASE",
]

#: Pha mà vòng lặp sinh mã được phép chạy — "D. PHÁT TRIỂN" trong SAD Hình 2.
GENERATION_PHASE = "D"


class OrchestratorError(Exception):
    """Lỗi điều phối."""


class PreconditionFailed(OrchestratorError):
    """Tiền điều kiện của vòng lặp chuẩn chưa thỏa (UC04)."""


@dataclass
class OrchestratorConfig:
    """Tham số vòng lặp chuẩn."""

    #: FR-GEN-01 — số vòng tự sửa tối đa, cấu hình được, mặc định 3.
    max_repairs: int = 3
    #: Cổng bắt buộc phải có mặt trong chuỗi (FR-VER-01). Cổng mô phỏng gia
    #: nhập ở Sprint 3; tới lúc đó thêm ``"sim"`` vào đây chứ không phải thêm
    #: một ngoại lệ ở chỗ khác.
    required_gates: tuple[str, ...] = ("compile", "size", "static", "unittests")
    actor: str = ""


@dataclass
class ModuleOutcome:
    """Kết cục một lượt chạy vòng lặp chuẩn cho một module."""

    module_id: str
    #: ``awaiting_gate`` · ``merged`` · ``rejected`` · ``handoff`` · ``blocked``
    status: str
    exit_code: int
    message: str
    reports: list[ToolReport] = field(default_factory=list)
    repairs: int = 0
    artifact: CodeArtifact | None = None
    commit: str = ""
    attempts_log: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK


class Orchestrator:
    """Điều phối vòng lặp chuẩn cho từng module."""

    def __init__(
        self,
        *,
        state_store: Any,
        composer: Any,
        llm: Any,
        gates: Any,
        repo: Any,
        graph: Any,
        kpi: Any = None,
        ledger: Any = None,
        readiness: Any = None,
        gate_chain: Sequence[Any] = (),
        config: OrchestratorConfig | None = None,
        runs_dir: Any = None,
    ) -> None:
        self.state_store = state_store
        self.composer = composer
        self.llm = llm
        self.gates = gates
        self.repo = repo
        self.graph = graph
        self.kpi = kpi
        self.ledger = ledger
        self.readiness = readiness
        self.gate_chain = list(gate_chain)
        self.config = config or OrchestratorConfig()
        self.runs_dir = (
            Path(runs_dir)
            if runs_dir is not None
            else Path(state_store.path).parent / ".eaa" / "runs"
        )

    # ----------------------------------------------------------------------
    # Máy trạng thái (FR-ORC-01)
    # ----------------------------------------------------------------------

    def advance_phase(self, target: str | None) -> None:
        """Chuyển pha. Luật nằm ở ``policy.check_transition``, không ở đây.

        Orchestrator TRA CỨU luật chứ không phát biểu luật — nếu nó tự phát
        biểu thì sẽ có hai nơi định nghĩa cùng một thứ, và hai nơi là hai chỗ
        để lọt lưới (ADR-04).
        """
        with self.state_store.with_lock():
            state = self.state_store.load()
            check_transition(state.phase, target, state.gates)
            if target is None:
                return
            state.phase = target
            self.state_store.save(state)

        if self.kpi is not None:
            self.kpi.log(event="module_start", phase=target, note=f"chuyển sang pha {target}")

    # ----------------------------------------------------------------------
    # Bước 1–10
    # ----------------------------------------------------------------------

    def run_module(self, module_id: str) -> ModuleOutcome:
        """Chạy vòng lặp chuẩn tới điểm dừng ở G3 (bước 1–10)."""
        bat_dau = time.monotonic()
        state = self.state_store.load()

        # Bước 1–2: tiền điều kiện và mức phân quyền.
        self._kiem_tien_dieu_kien(state, module_id)
        muc = self._tra_policy(state)
        self._dat_trang_thai(module_id, "in_gen")
        self._kpi("module_start", module_id, note=f"mức phân quyền {muc}")

        # Bước 3–5: ghép prompt và sinh mã.
        task = self._dung_task(state, module_id)
        try:
            prompt = self.composer.build(task, state, counter=self.llm.count_tokens)
            artifact = self._sinh_ma(prompt, module_id)
        except Exception as exc:  # noqa: BLE001 - mọi lỗi lắp ráp đều dừng vòng
            return self._that_bai(
                module_id,
                "blocked",
                EXIT_ENV_ERROR,
                f"Không lắp ráp hoặc không sinh được mã: {exc}",
            )

        branch = self.repo.start_module(module_id)
        nhat_ky: list[str] = []
        so_lan_va = 0

        while True:
            self._dat_trang_thai(module_id, "in_verify", retries=so_lan_va)

            # Bước 6: chuỗi cổng kiểm chứng.
            bao_cao = self._chay_chuoi_cong(artifact, module_id)
            nhat_ky.append(self._tom_tat_luot(so_lan_va, bao_cao))

            hong = [r for r in bao_cao if not r.passed]
            if not hong:
                break

            if any(r.metrics.get("env_error") for r in hong):
                return self._that_bai(
                    module_id,
                    "blocked",
                    EXIT_ENV_ERROR,
                    "Thiếu công cụ trong môi trường — chạy 'eaa doctor'.\n"
                    + "\n".join(str(e) for r in hong for e in r.errors),
                    bao_cao=bao_cao,
                    repairs=so_lan_va,
                    nhat_ky=nhat_ky,
                )

            # Lỗi cấu hình cũng dừng ngay, không vào vòng tự sửa. Mô hình không
            # sửa được một luật còn thiếu trong pack hay một ràng buộc khai báo
            # sai; đưa nó vào vòng vá chỉ đốt lượt gọi và làm hỏng mã đang đúng.
            if any(r.metrics.get("config_error") for r in hong):
                return self._that_bai(
                    module_id,
                    "blocked",
                    EXIT_ENV_ERROR,
                    "Lỗi CẤU HÌNH, không phải lỗi mã — vòng tự sửa không mở.\n"
                    + "\n".join(str(e) for r in hong for e in r.errors),
                    bao_cao=bao_cao,
                    repairs=so_lan_va,
                    nhat_ky=nhat_ky,
                )

            # Bước 7–8: vá, nếu còn lượt.
            if so_lan_va >= self.config.max_repairs:
                return self._bàn_giao(module_id, bao_cao, so_lan_va, nhat_ky, branch)

            so_lan_va += 1
            self._kpi(
                "repair",
                module_id,
                retries=so_lan_va,
                gate=hong[0].gate,
                result="fail",
                note=f"vòng tự sửa {so_lan_va}/{self.config.max_repairs}",
            )
            try:
                artifact = self._va_loi(task, state, hong[0], artifact, module_id)
            except Exception as exc:  # noqa: BLE001
                return self._that_bai(
                    module_id,
                    "blocked",
                    EXIT_ENV_ERROR,
                    f"Vòng vá thất bại: {exc}",
                    bao_cao=bao_cao,
                    repairs=so_lan_va,
                    nhat_ky=nhat_ky,
                )

        # Bước 9: commit + diff.
        commit = self._commit(artifact, module_id)
        tdev = (time.monotonic() - bat_dau) / 60.0

        # Bước 10: gửi diff chờ G3.
        payload = self._xin_gate(module_id, branch, bao_cao, artifact)
        self._luu_bang_chung(module_id, bao_cao, payload.content_digest)
        self._dat_trang_thai(module_id, "in_review", retries=so_lan_va)
        self._kpi(
            "gate_request",
            module_id,
            gate=MERGE_GATE,
            commit=commit,
            tdev_min=round(tdev, 3),
            retries=so_lan_va,
            prompt_hash=artifact.prompt_hash,
            constraints_version=artifact.constraints_version,
            llm_model=artifact.model,
            tokens_in=artifact.tokens_in,
            tokens_out=artifact.tokens_out,
            note=f"chờ người duyệt {MERGE_GATE}",
        )

        return ModuleOutcome(
            module_id=module_id,
            status="awaiting_gate",
            exit_code=EXIT_WAITING_GATE,
            message=(
                f"Module {module_id} qua đủ {len(bao_cao)} cổng kiểm chứng sau "
                f"{so_lan_va} vòng tự sửa. Đang chờ {MERGE_GATE} "
                f"({GATE_PURPOSE[MERGE_GATE]}).\n"
                f"Xem: eaa gate show {MERGE_GATE}\n"
                f"Duyệt: eaa gate approve {MERGE_GATE}"
            ),
            reports=bao_cao,
            repairs=so_lan_va,
            artifact=artifact,
            commit=commit,
            attempts_log=nhat_ky,
        )

    # ----------------------------------------------------------------------
    # Bước 11–13
    # ----------------------------------------------------------------------

    def finalize_module(
        self, module_id: str, reports: Sequence[ToolReport]
    ) -> ModuleOutcome:
        """Bước 11–13: sau khi con người đã quyết định tại G3.

        Hàm này KHÔNG quyết định thay người: nó đọc quyết định đã có. Nếu chưa
        có quyết định nào, nó dừng — không có nhánh nào ở đây tự tạo ra một
        quyết định duyệt.
        """
        quyet_dinh = self.gates.latest(MERGE_GATE)
        branch = self.repo.branch_for(module_id)

        if quyet_dinh is None or self.gates.status(MERGE_GATE) == "pending":
            return ModuleOutcome(
                module_id=module_id,
                status="awaiting_gate",
                exit_code=EXIT_WAITING_GATE,
                message=f"{MERGE_GATE} chưa có quyết định của người.",
                reports=list(reports),
            )

        if quyet_dinh.decision == REJECTED:
            self._dat_trang_thai(module_id, "todo")
            self._kpi(
                "gate_decision",
                module_id,
                gate=MERGE_GATE,
                result="reject",
                note=quyet_dinh.reason,
            )
            return ModuleOutcome(
                module_id=module_id,
                status="rejected",
                exit_code=EXIT_WAITING_GATE,
                message=(
                    f"{MERGE_GATE} từ chối: {quyet_dinh.reason}\n"
                    "Lý do đã vào Error Ledger và sẽ xuất hiện trong prompt lần "
                    "sinh lại. Chạy lại 'eaa gen' khi sẵn sàng."
                ),
                reports=list(reports),
            )

        # Bước 11 — merge. Cửa duy nhất, và nó tự kiểm bằng chứng.
        try:
            giay_phep = authorize_merge(
                module_id=module_id,
                branch=branch,
                reports=list(reports),
                decision=quyet_dinh,
                content_digest=self.repo.diff_digest(branch),
            )
            commit = self.repo.merge(giay_phep)
        except MergeNotAuthorized as exc:
            return ModuleOutcome(
                module_id=module_id,
                status="blocked",
                exit_code=EXIT_ENV_ERROR,
                message=f"Không được phép merge: {exc}",
                reports=list(reports),
            )

        self._dat_trang_thai(module_id, "merged")
        self._kpi(
            "gate_decision", module_id, gate=MERGE_GATE, result="approve",
            note=f"duyệt bởi {quyet_dinh.actor}",
        )
        self._kpi("merge", module_id, commit=commit, result="pass")

        # Bước 13 — module kế tiếp.
        ke_tiep = self._module_ke_tiep()
        loi_nhan = f"Đã merge {module_id} vào {self.repo.main_branch} ({commit[:8]})."
        if ke_tiep:
            loi_nhan += f" Module kế tiếp: {ke_tiep}."
        else:
            loi_nhan += " Backlog đã hết module chờ."

        return ModuleOutcome(
            module_id=module_id,
            status="merged",
            exit_code=EXIT_OK,
            message=loi_nhan,
            reports=list(reports),
            commit=commit,
        )

    # ----------------------------------------------------------------------
    # Các bước con
    # ----------------------------------------------------------------------

    def _kiem_tien_dieu_kien(self, state: Any, module_id: str) -> None:
        """Bước 1 — tiền điều kiện của UC04, và là nơi TC-01 gõ cửa đầu tiên."""
        thieu = [c for c in self.config.required_gates if c not in self._ten_cong()]
        if thieu:
            raise PreconditionFailed(
                f"Chuỗi kiểm chứng thiếu cổng bắt buộc {thieu} (FR-VER-01). "
                "Không chạy vòng sinh mã với một chuỗi khuyết — một cổng vắng mặt "
                "là một loại lỗi không được kiểm."
            )

        if state.phase != GENERATION_PHASE:
            raise PreconditionFailed(
                f"Dự án đang ở pha {state.phase} ({PHASE_NAMES[state.phase]}); vòng "
                f"sinh mã chỉ chạy ở pha {GENERATION_PHASE} "
                f"({PHASE_NAMES[GENERATION_PHASE]}). "
                f"{self._gate_con_thieu(state)}"
            )

        muc = state.module(module_id)
        if muc is None:
            co = ", ".join(m.id for m in state.backlog) or "(backlog trống)"
            raise PreconditionFailed(
                f"Module {module_id!r} không có trong backlog. Đang có: {co}. "
                "Thêm bằng 'eaa plan add'."
            )

        if muc.status == "merged":
            raise PreconditionFailed(
                f"Module {module_id!r} đã merge. Sinh lại thì đưa nó về trạng thái "
                "todo trước."
            )

        # FR-KG-02 — kiểm xung đột tài nguyên TRƯỚC khi sinh mã (shift-left).
        xung_dot = self.graph.check_module(module_id, uses=muc.uses, depends_on=muc.depends_on)
        chan = [c for c in xung_dot if c.kind != "unknown_resource"] + [
            c for c in xung_dot if c.kind == "unknown_resource"
        ]
        if chan:
            raise PreconditionFailed(
                "Xung đột tài nguyên phải do kỹ sư phân xử trước khi sinh mã "
                "(FR-KG-02):\n" + "\n".join(f"  • {c.message}" for c in chan)
            )

        # Readiness Check — quy trình P7, bước cuối cùng trước khi mở vòng sinh
        # mã. Đặt SAU kiểm xung đột vì xung đột tài nguyên làm cả bảng kiểm vô
        # nghĩa: không biết module rốt cuộc dùng tài nguyên nào thì không biết
        # nó cần tài liệu gì.
        if self.readiness is not None:
            from eaa.readiness import NotReady

            try:
                self.readiness.check(module_id, uses=muc.uses)
            except NotReady as exc:
                raise PreconditionFailed(str(exc)) from exc

    def _gate_con_thieu(self, state: Any) -> str:
        for gate in ("G1", "G2"):
            if state.gate_status(gate) != APPROVED:
                return (
                    f"Gate {gate} ({GATE_PURPOSE[gate]}) chưa duyệt — "
                    f"chạy 'eaa gate approve {gate}'."
                )
        return "Chuyển pha bằng 'eaa resume' để xem bước kế tiếp."

    def _tra_policy(self, state: Any) -> Level:
        """Bước 2 — tra Policy Engine."""
        return level(state.phase)

    def _dung_task(self, state: Any, module_id: str) -> Task:
        """Bước 3 — giao nhiệm vụ kèm phần Project State liên quan (K4)."""
        muc = state.module(module_id)
        return Task(
            module_id=module_id,
            goal=f"Hiện thực module {module_id} theo ràng buộc và tài liệu đã duyệt.",
            acceptance=(
                "Qua toàn bộ chuỗi cổng kiểm chứng.",
                "Mọi hàm cấu hình thanh ghi có dòng trích dẫn nguồn.",
            ),
            uses=tuple(muc.uses) if muc else (),
            depends_on=tuple(muc.depends_on) if muc else (),
            output_files=(f"src/{module_id}.c", f"src/{module_id}.h"),
        )

    def _sinh_ma(self, prompt: Any, module_id: str) -> CodeArtifact:
        """Bước 5 — gọi mô hình. Ngân sách đã được adapter kiểm trước khi gọi."""
        artifact = self.llm.generate(prompt)
        self._kpi(
            "generate",
            module_id,
            llm_model=artifact.model,
            tokens_in=artifact.tokens_in,
            tokens_out=artifact.tokens_out,
            prompt_hash=artifact.prompt_hash,
            constraints_version=artifact.constraints_version,
            result="pass",
        )
        return artifact

    def _ten_cong(self) -> list[str]:
        return [getattr(g, "name", type(g).__name__) for g in self.gate_chain]

    def _chay_chuoi_cong(
        self, artifact: CodeArtifact, module_id: str
    ) -> list[ToolReport]:
        """Bước 6 — chạy chuỗi cổng theo đúng thứ tự FR-VER-01.

        Dừng ở cổng hỏng ĐẦU TIÊN: cổng sau ăn sản phẩm của cổng trước (không
        dịch được thì không có gì để đo kích thước), và một chuỗi báo cáo lỗi
        dây chuyền chỉ làm loãng prompt vá.
        """
        bao_cao: list[ToolReport] = []
        for cong in self.gate_chain:
            ket_qua = self._chay_mot_cong(cong, artifact, bao_cao)
            bao_cao.append(ket_qua)
            if self.kpi is not None:
                self.kpi.log_report(ket_qua, module=module_id, phase=GENERATION_PHASE)
            if not ket_qua.passed:
                break
        return bao_cao

    @staticmethod
    def _chay_mot_cong(
        cong: Any, artifact: CodeArtifact, truoc_do: Sequence[ToolReport]
    ) -> ToolReport:
        """Cổng đo kích thước cần ảnh nhị phân của cổng dịch — nối bằng metrics."""
        if getattr(cong, "name", "") == "size":
            nhi_phan = next(
                (r.metrics.get("binary") for r in reversed(truoc_do) if r.metrics.get("binary")),
                None,
            )
            if not nhi_phan:
                return ToolReport(
                    gate="size",
                    passed=False,
                    errors=[],
                    metrics={"skipped": "không có ảnh nhị phân từ cổng dịch"},
                )
            return cong.run(nhi_phan)
        return cong.run(artifact)

    def _va_loi(
        self,
        task: Task,
        state: Any,
        bao_cao_hong: ToolReport,
        artifact: CodeArtifact,
        module_id: str,
    ) -> CodeArtifact:
        """Bước 7–8 — prompt vá chỉ mang lỗi và hàm liên quan (AIS §3.2)."""
        prompt = self.composer.build_repair(
            task, state, bao_cao_hong, artifact.files, counter=self.llm.count_tokens
        )
        ban_va = self.llm.generate(prompt)

        # Bản vá thay thế theo TỆP: mô hình chỉ trả về tệp nó sửa, các tệp khác
        # giữ nguyên. Ghi đè cả tập sẽ làm mất những tệp không liên quan.
        tep = dict(artifact.files)
        tep.update(ban_va.files)
        ban_va.files = tep

        if self.ledger is not None:
            self.ledger.add(
                module=module_id,
                category="tool_failure",
                description=(
                    f"Cổng {bao_cao_hong.gate} không đạt: "
                    + "; ".join(str(e) for e in bao_cao_hong.errors[:3])
                ),
                evidence=f"vòng tự sửa, cổng {bao_cao_hong.gate}",
            )
        return ban_va

    def _commit(self, artifact: CodeArtifact, module_id: str) -> str:
        """Bước 9 — ghi mã lên nhánh module với đủ dấu vết NFR-07."""
        from eaa.tools.compile import write_artifact

        write_artifact(artifact, self.repo.root)
        return self.repo.commit_artifact(artifact, module_id=module_id)

    def _xin_gate(
        self,
        module_id: str,
        branch: str,
        bao_cao: Sequence[ToolReport],
        artifact: CodeArtifact,
    ) -> GatePayload:
        """Bước 10 — đặt hồ sơ lên bàn cho người, kèm checklist từ đồ thị."""
        payload = GatePayload(
            gate_id=MERGE_GATE,
            title=f"Review diff module {module_id}",
            module=module_id,
            summary=tuple(r.summary for r in bao_cao)
            + (
                f"mô hình: {artifact.model}",
                f"chunk đã dùng: {', '.join(artifact.chunk_ids) or '(không có)'}",
            ),
            details=self.repo.diff(),
            checklist=tuple(self.graph.review_checklist(module_id)),
            content_digest=self.repo.diff_digest(branch),
        )
        self.gates.request(payload)
        return payload

    def _duong_dan_bang_chung(self, module_id: str) -> Path:
        return self.runs_dir / f"verification_{module_id}.json"

    def _luu_bang_chung(
        self, module_id: str, bao_cao: Sequence[ToolReport], content_digest: str
    ) -> None:
        """Cất bằng chứng kiểm chứng để bước 11 dùng lại.

        Bước 10 và bước 11 cách nhau một con người, nghĩa là có thể cách nhau
        một ngày và một tiến trình khác. Không cất thì tới lúc merge không còn
        gì để chứng minh "toàn bộ cổng đã đạt", và cám dỗ lúc đó sẽ là bỏ qua
        phép kiểm ấy.
        """
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._duong_dan_bang_chung(module_id).write_text(
            json.dumps(
                {
                    "module": module_id,
                    "content_digest": content_digest,
                    "reports": [r.to_dict() for r in bao_cao],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def load_evidence(self, module_id: str) -> list[ToolReport]:
        """Đọc lại bằng chứng đã cất. Không có thì trả rỗng — và giấy phép
        merge sẽ từ chối vì thiếu bằng chứng, đúng như phải thế."""
        path = self._duong_dan_bang_chung(module_id)
        if not path.is_file():
            return []
        du_lieu = json.loads(path.read_text(encoding="utf-8"))
        return [ToolReport.from_dict(r) for r in du_lieu.get("reports", [])]

    # ----------------------------------------------------------------------
    # Kết cục
    # ----------------------------------------------------------------------

    def _bàn_giao(
        self,
        module_id: str,
        bao_cao: Sequence[ToolReport],
        so_lan_va: int,
        nhat_ky: Sequence[str],
        branch: str,
    ) -> ModuleOutcome:
        """Quá N vòng tự sửa → dừng, bàn giao người KÈM ĐỦ LOG (TC-06).

        "Kèm log" không phải chi tiết phụ: sau ba lần máy không tự sửa được,
        thứ người cần là thấy được ba lần ấy hỏng khác nhau thế nào — nếu cùng
        một lỗi lặp lại thì thiếu ngữ cảnh, còn nếu lỗi nhảy lung tung thì
        nhiệm vụ mô tả chưa rõ.
        """
        self._dat_trang_thai(module_id, "handoff", retries=so_lan_va)
        self._kpi(
            "handoff",
            module_id,
            retries=so_lan_va,
            result="fail",
            note=f"quá {self.config.max_repairs} vòng tự sửa",
        )
        return ModuleOutcome(
            module_id=module_id,
            status="handoff",
            exit_code=EXIT_REPAIR_LIMIT,
            message=(
                f"Đã thử tự sửa {so_lan_va}/{self.config.max_repairs} vòng mà "
                f"module {module_id} vẫn không qua được chuỗi cổng. Dừng và bàn "
                f"giao kỹ sư.\n\nNhật ký từng vòng:\n" + "\n".join(nhat_ky)
            ),
            reports=list(bao_cao),
            repairs=so_lan_va,
            attempts_log=list(nhat_ky),
        )

    def _that_bai(
        self,
        module_id: str,
        status: str,
        exit_code: int,
        message: str,
        *,
        bao_cao: Sequence[ToolReport] = (),
        repairs: int = 0,
        nhat_ky: Sequence[str] = (),
    ) -> ModuleOutcome:
        self._dat_trang_thai(module_id, "todo", retries=repairs)
        return ModuleOutcome(
            module_id=module_id,
            status=status,
            exit_code=exit_code,
            message=message,
            reports=list(bao_cao),
            repairs=repairs,
            attempts_log=list(nhat_ky),
        )

    # ----------------------------------------------------------------------
    # Tiện ích
    # ----------------------------------------------------------------------

    @staticmethod
    def _tom_tat_luot(luot: int, bao_cao: Sequence[ToolReport]) -> str:
        nhan = "sinh lần đầu" if luot == 0 else f"vòng vá {luot}"
        dong = [f"── {nhan} ──"]
        for r in bao_cao:
            dong.append(f"  {r.summary}")
            for e in r.errors[:3]:
                dong.append(f"      {e}")
        return "\n".join(dong)

    def _dat_trang_thai(
        self, module_id: str, trang_thai: str, *, retries: int | None = None
    ) -> None:
        """Ghi state sau MỖI bước, để ``eaa resume`` biết đang dở ở đâu (TC-03)."""
        with self.state_store.with_lock():
            state = self.state_store.load()
            muc = state.module(module_id)
            if muc is None:
                return
            muc.status = trang_thai
            if retries is not None:
                muc.retries = retries
            state.current_module = module_id if trang_thai != "merged" else None
            self.state_store.save(state)

    def _module_ke_tiep(self) -> str | None:
        state = self.state_store.load()
        for muc in state.backlog:
            if muc.status in ("todo", "handoff"):
                return muc.id
        return None

    def _kpi(self, event: str, module_id: str, **truong: Any) -> None:
        if self.kpi is None:
            return
        self.kpi.log(event=event, module=module_id, phase=GENERATION_PHASE, **truong)
