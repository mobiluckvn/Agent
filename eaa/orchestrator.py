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
import shutil
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_REPAIR_LIMIT, EXIT_WAITING_GATE
from eaa.composer import Task
from eaa.contract import khai_bao_ham, mat_loi_goi, pha_vo_hop_dong
from eaa.gates import APPROVED, REJECTED, GatePayload
from eaa.instrument import NghiVan, nghi_van_chinh_do_do
from eaa.policy import PHASE_NAMES, GATE_PURPOSE, Level, check_transition, level
from eaa.sensitivity import KetQuaDoNhay, bai_kiem_doi, ket_luan
from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolReport
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
    #: Chế độ NHÁP — chạy một tập cổng nhẹ hơn để thử nhanh.
    #:
    #: Rỗng nghĩa là chạy bình thường. Khác rỗng thì vòng chạy dùng đúng tập
    #: này thay cho ``required_gates``, và **không ghi bằng chứng nào**.
    #:
    #: Chỗ ấy mới là điểm của cả tính năng. Cách hiển nhiên — thêm một cờ cho
    #: phép bỏ qua cổng — phá bất biến trung tâm: một cờ bỏ qua tồn tại là một
    #: cờ sẽ được dùng, và nó sẽ được dùng đúng vào lúc gấp. Ở đây bản nháp
    #: không thể merge được **do cấu tạo**: nó không ghi vào tệp mà đường merge
    #: đọc, nên tới bước merge đơn giản là không có bằng chứng nào để đọc.
    #: Không có một câu ``if`` nào phải nhớ đặt cho đúng.
    draft_gates: tuple[str, ...] = ()
    #: Chế độ XEM TRƯỚC — sinh mã rồi dừng, KHÔNG chạy cổng nào, KHÔNG tạo
    #: nhánh, KHÔNG commit.
    #:
    #: Dùng cho đúng một hoàn cảnh, và là hoàn cảnh rất thường gặp: máy chưa
    #: có toolchain. Khi ấy cổng ``compile`` hỏng vì lỗi môi trường và người
    #: dùng không xem được cả dòng mã nào — trong khi thứ họ muốn chỉ là *nhìn
    #: xem Agent sẽ viết gì*.
    #:
    #: An toàn hơn cả chế độ nháp: nháp không GHI BẰNG CHỨNG, còn xem trước
    #: thậm chí không tạo ra một nhánh nào để mà merge.
    preview: bool = False

    @property
    def is_draft(self) -> bool:
        return bool(self.draft_gates)

    @property
    def gates_to_run(self) -> tuple[str, ...]:
        return self.draft_gates or self.required_gates


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
        token_budget: Any = None,
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
        #: ``eaa.budget.TokenBudget`` — trần token tích lũy theo module (N-904).
        #: Không có thì vòng lặp chạy y như trước; trần ở đây là thêm một phép
        #: kiểm, không phải một điều kiện mới để hệ thống chạy được.
        self.token_budget = token_budget
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
            # Kèm backlog: cung D → E gác bằng G3, mà G3 là cổng của TỪNG
            # module. Không đưa backlog xuống thì duyệt module đầu tiên là
            # mở cửa ra khỏi cả pha phát triển (SL-146).
            check_transition(state.phase, target, state.gates, backlog=state.backlog)
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

        # Trần token tích lũy — kiểm TRƯỚC khi tiêu thêm, cùng nguyên tắc với
        # ngân sách prompt: một trần chỉ kiểm sau khi gọi thì không phải trần.
        chan = self._kiem_tran_token(module_id)
        if chan is not None:
            return chan

        muc = self._tra_policy(state)
        self._dat_trang_thai(module_id, "in_gen")
        self._kpi("module_start", module_id, note=f"mức phân quyền {muc}")

        # Bước 3–5: ghép prompt và sinh mã.
        task = self._dung_task(state, module_id)
        try:
            prompt = self.composer.build(task, state, counter=self.llm.count_tokens)
            artifact = self._sinh_ma(prompt, module_id)
            bo_ngoai_pham_vi = self.khoa_pham_vi_tep(artifact, module_id)
        except Exception as exc:  # noqa: BLE001 - mọi lỗi lắp ráp đều dừng vòng
            return self._that_bai(
                module_id,
                "blocked",
                EXIT_ENV_ERROR,
                f"Không lắp ráp hoặc không sinh được mã: {exc}",
            )

        # Xem trước dừng ở ĐÂY — trước cả khi tạo nhánh. Không nhánh nghĩa là
        # không có gì để merge, kể cả khi ai đó sau này viết nhầm một lối merge
        # thứ hai: lối ấy sẽ không tìm thấy nhánh nào của lượt chạy này.
        if self.config.preview:
            self._dat_trang_thai(module_id, "todo")
            self._kpi(
                "preview", module_id, prompt_hash=artifact.prompt_hash,
                llm_model=artifact.model, tokens_in=artifact.tokens_in,
                tokens_out=artifact.tokens_out,
                note="xem trước — không cổng, không nhánh, không commit",
            )
            return ModuleOutcome(
                module_id=module_id,
                status="preview",
                exit_code=EXIT_WAITING_GATE,
                message=(
                    f"XEM TRƯỚC — mã cho {module_id} đã sinh, và DỪNG Ở ĐÂY.\n"
                    "Không cổng nào chạy, không nhánh nào tạo, không commit nào.\n\n"
                    "Nghĩa là: mã này CHƯA ĐƯỢC KIỂM. Nó chưa từng được dịch, "
                    "chưa qua phân tích tĩnh, chưa chạy một test nào. Đọc nó như "
                    "đọc một bản nháp của người khác.\n"
                    + (
                        f"\n⚠ Dự án còn ở pha {state.phase}, chưa tới pha "
                        f"{GENERATION_PHASE}. Kiến trúc chưa chốt xong, nên mã "
                        "này dựng trên những ràng buộc còn có thể đổi. Xem để "
                        "hình dung, đừng để nó chốt hộ một quyết định bạn chưa "
                        "đưa ra.\n"
                        if state.phase != GENERATION_PHASE else ""
                    )
                    + f"\nMuốn kiểm thật thì cần toolchain: eaa doctor  →  eaa gen {module_id}"
                ),
                artifact=artifact,
            )

        da_don = self.repo.start_module(module_id)
        branch = self.repo.branch_for(module_id)
        nhat_ky: list[str] = []
        if da_don:
            # Nói ra việc dọn. Một lượt sinh hỏng để lại mã chưa commit, và
            # xóa nó im lặng là cách một tệp ai đó sửa tay biến mất không dấu
            # vết (SL-151).
            nhat_ky.append(
                "  ⚠ đã dọn mã còn sót của lượt trước: " + ", ".join(sorted(da_don)[:6])
                + (" …" if len(da_don) > 6 else "")
            )
        cau_bo = self._cau_bo_tep(bo_ngoai_pham_vi, module_id)
        if cau_bo:
            nhat_ky.append(cau_bo)
        truoc_khi_va: CodeArtifact | None = None
        canh_bao = self.canh_bao_luoc(prompt)
        if canh_bao:
            nhat_ky.append(canh_bao)
        so_lan_va = 0

        while True:
            self._dat_trang_thai(module_id, "in_verify", retries=so_lan_va)

            # Bước 6: chuỗi cổng kiểm chứng.
            #
            # Hợp đồng gọi đi TRƯỚC (SL-163). Không phải để tiết kiệm: một
            # header đã thu hẹp làm cổng dịch đỏ ở tệp của module KHÁC, và
            # thông điệp lúc ấy nói về `app_balance.c:125` chứ không nói về
            # cái vừa bị đổi. Cùng một lỗi, hai câu — câu này chỉ đúng chỗ.
            vi_pham = self._pha_vo_hop_dong(artifact, module_id)
            mat_goi = self._mat_loi_goi(artifact, module_id)
            bao_cao = (
                [self._bao_cao_hop_dong(vi_pham, mat_goi, module_id)]
                if (vi_pham or mat_goi)
                else self._chay_chuoi_cong(artifact, module_id)
            )
            nhat_ky.append(self._tom_tat_luot(so_lan_va, bao_cao))

            hong = [r for r in bao_cao if not r.passed]
            if not hong:
                break

            # Bản sắp bị vá — giữ lại để đo ĐỘ NHẠY của bài kiểm sau khi vòng vá
            # kết thúc (N-909). Phải giữ ở đây: `_va_loi` gán đè `artifact`, và
            # sau vòng lặp thì bản vừa bị cổng đánh đỏ không còn ai cầm.
            truoc_khi_va = artifact

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

            # Cổng đỏ vì mã của MODULE KHÁC cũng dừng ngay (SL-162). Lượt sinh
            # chỉ được viết `tep_can_sinh(module_id)`; một thất bại nằm hoàn
            # toàn ngoài tập ấy là thứ vòng vá không có quyền chạm tới, nên ba
            # lượt gọi bỏ ra chỉ để nó sửa mù vào mã đang đúng.
            ngoai = self._loi_ngoai_pham_vi(hong[0], module_id)
            if ngoai:
                return self._that_bai(
                    module_id,
                    "blocked",
                    EXIT_ENV_ERROR,
                    "Cổng đỏ vì mã NGOÀI phạm vi module này — vòng tự sửa không mở.\n"
                    f"Tệp đỏ: {', '.join(ngoai)}\n"
                    f"Lượt sinh {module_id} chỉ được viết: "
                    f"{', '.join(self.tep_can_sinh(module_id))}\n"
                    "Thường gặp nhất: module này đổi chữ ký trong header của nó "
                    "và làm một module ĐÃ MERGE không dịch được nữa. Xem lại "
                    "diff của header trước khi sinh lại.\n"
                    + "\n".join(str(e) for e in hong[0].errors),
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
                artifact, canh_bao = self._va_loi(task, state, hong[0], artifact, module_id)
                if canh_bao:
                    nhat_ky.append(canh_bao)
                # Bản vá vừa nhận có đang chỉnh ĐỒ ĐO thay vì chỉnh cái bị đo
                # không (N-908). Soi TRƯỚC khi chạy cổng: cổng sẽ báo ĐẠT cho
                # một bản vá như thế — đó đúng là lý do nó lọt được ba lần.
                nghi = self._nghi_van_do_do(truoc_khi_va, artifact, module_id)
                if nghi.co:
                    return self._dung_vi_chinh_do_do(
                        module_id, nghi, bao_cao, so_lan_va, nhat_ky
                    )
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

        # Độ nhạy của bài kiểm (N-909). Chỉ đo khi vòng vá đã chạy: chưa vá thì
        # chưa có "bản mã sai đã biết" nào để so, và phép đo mất nghĩa.
        do_nhay = KetQuaDoNhay()
        if so_lan_va and truoc_khi_va is not None:
            do_nhay = self._do_nhay_bai_kiem(truoc_khi_va, artifact, module_id)
            if do_nhay.bai_kiem_moi or not do_nhay.do_duoc:
                nhat_ky.append("  " + do_nhay.cau())
                self._kpi(
                    "test_sensitivity",
                    module_id,
                    retries=so_lan_va,
                    result="pass" if do_nhay.dat else "fail",
                    note=do_nhay.cau(),
                )

        # Bước 9: commit + diff.
        commit = self._commit(artifact, module_id)
        tdev = (time.monotonic() - bat_dau) / 60.0

        # Bản nháp dừng ở đây. Nó KHÔNG gọi ``_xin_gate`` và KHÔNG gọi
        # ``_luu_bang_chung`` — nên tệp mà ``load_evidence`` đọc vẫn trống, và
        # ``finalize_module`` sẽ từ chối vì thiếu bằng chứng. Không có câu
        # ``if`` nào ở phía merge phải nhớ đặt cho đúng: bản nháp không merge
        # được vì nó không để lại thứ mà merge cần đọc.
        if self.config.is_draft:
            self._dat_trang_thai(module_id, "todo", retries=so_lan_va)
            self._kpi(
                "draft_run", module_id, commit=commit, tdev_min=round(tdev, 3),
                retries=so_lan_va, prompt_hash=artifact.prompt_hash,
                llm_model=artifact.model,
                note=f"nháp qua {len(bao_cao)} cổng: {', '.join(self.config.draft_gates)}",
            )
            return ModuleOutcome(
                module_id=module_id,
                status="draft",
                exit_code=EXIT_WAITING_GATE,
                message=(
                    f"BẢN NHÁP — {module_id} qua {len(bao_cao)} cổng "
                    f"({', '.join(r.gate for r in bao_cao)}) sau {so_lan_va} vòng tự sửa.\n"
                    f"Bộ cổng đầy đủ là: {', '.join(self.config.required_gates)}.\n\n"
                    "Bản này KHÔNG merge được, và không phải vì bị chặn — vì nó "
                    "không để lại bằng chứng nào cho bước merge đọc. Muốn đưa nó "
                    f"vào thì chạy lại đủ: eaa gen {module_id}"
                ),
                reports=list(bao_cao),
                repairs=so_lan_va,
                artifact=artifact,
                commit=commit,
                attempts_log=nhat_ky,
            )

        # Bước 10: gửi diff chờ G3.
        payload = self._xin_gate(module_id, branch, bao_cao, artifact, do_nhay)
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
                required_gates=self.config.required_gates,
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
        thieu = [c for c in self.config.gates_to_run if c not in self._ten_cong()]
        if thieu:
            raise PreconditionFailed(
                f"Chuỗi kiểm chứng thiếu cổng bắt buộc {thieu} (FR-VER-01). "
                "Không chạy vòng sinh mã với một chuỗi khuyết — một cổng vắng mặt "
                "là một loại lỗi không được kiểm."
            )

        # Xem trước KHÔNG bị chặn ở pha, và chỉ ở pha.
        #
        # Cổng pha tồn tại để kiểm soát thứ ĐI VÀO sản phẩm. Xem trước không
        # đưa gì vào cả: không nhánh, không commit, không bằng chứng — mã đi
        # thẳng ra màn hình. Bắt nó đi hết đường gate là đánh mất chính lý do
        # nó tồn tại: người dùng chưa có toolchain, chỉ muốn nhìn xem Agent sẽ
        # viết gì.
        #
        # Mọi tiền điều kiện KHÁC vẫn áp: module phải có trong backlog, không
        # được xung đột tài nguyên, và phải đủ tri thức. Ba cái ấy quyết định
        # mã sinh ra có nghĩa hay không — bỏ chúng thì thứ in ra là mã bịa,
        # không phải mã xem trước.
        if state.phase != GENERATION_PHASE and not self.config.preview:
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

    def _kiem_tran_token(self, module_id: str) -> "ModuleOutcome | None":
        """Module này đã ăn hết phần token của nó chưa (N-904).

        Dừng ở đây thay vì cắt giữa chừng: một module bị chặn TRƯỚC khi gọi mô
        hình thì trạng thái của nó vẫn nguyên vẹn và người quyết định được
        trong yên tĩnh. Cắt giữa vòng tự sửa thì để lại một nhánh dở dang mà
        không ai biết nên tiếp hay bỏ.

        Vượt trần KHÔNG có cờ nào bỏ qua. Nới trần là sửa
        ``budget.tokens.per_module`` trong ``constraints.yaml`` — tệp có phiên
        bản và phải duyệt lại tại G1.
        """
        if self.token_budget is None or self.kpi is None:
            return None

        from eaa.budget import spent_tokens

        kiem = self.token_budget.check(spent_tokens(self.kpi, module_id))
        if not kiem.blocked:
            if kiem.status != "trong-phan":
                self._kpi(
                    "module_start",
                    module_id,
                    tokens_in=kiem.usage.tokens_in,
                    tokens_out=kiem.usage.tokens_out,
                    cost_est=round(kiem.cost, 6) if kiem.currency else "",
                    note="sắp chạm trần token của module",
                )
            return None

        self._kpi(
            "handoff",
            module_id,
            result="fail",
            tokens_in=kiem.usage.tokens_in,
            tokens_out=kiem.usage.tokens_out,
            cost_est=round(kiem.cost, 6) if kiem.currency else "",
            note="vượt trần token theo module",
        )
        return ModuleOutcome(
            module_id=module_id,
            status="handoff",
            exit_code=EXIT_REPAIR_LIMIT,
            message=kiem.render(),
        )

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
        return self.dung_nhiem_vu(module_id, state.module(module_id))

    @classmethod
    def dung_nhiem_vu(cls, module_id: str, muc: Any = None) -> Task:
        """Nhiệm vụ giao cho một lượt sinh mã.

        Mục tiêu lấy từ TRÁCH NHIỆM của chính module, không phải một câu chung.
        Trước SL-135 chỗ này viết cứng *"Hiện thực module X theo ràng buộc và
        tài liệu đã duyệt"* — giống hệt nhau cho mọi module — nên prompt sinh
        mã không mang theo ý định nào cả, và mã sai ý định vẫn qua sạch bốn
        cổng: cổng đo mã có chạy được không, không đo mã có làm đúng việc
        không.

        Bài kiểm cũng do cùng mô hình viết, nên nó kiểm đúng cái hiểu sai ấy.
        Một bài kiểm tự viết chỉ bắt được chỗ mã lệch với ý định; muốn nó bắt
        được ý định sai thì ý định phải đến từ chỗ khác — từ đây.
        """
        trach_nhiem = str(getattr(muc, "purpose", "") or "").strip()
        muc_tieu = (
            f"Hiện thực module {module_id}: {trach_nhiem}"
            if trach_nhiem
            else f"Hiện thực module {module_id} theo ràng buộc và tài liệu đã duyệt."
        )
        nghiem_thu = [
            "Qua toàn bộ chuỗi cổng kiểm chứng.",
            "Mọi hàm cấu hình thanh ghi có dòng trích dẫn nguồn.",
        ]
        if trach_nhiem:
            # Đặt trách nhiệm thành một tiêu chí nghiệm thu, không chỉ một câu
            # mô tả: bài kiểm sinh kèm phải chứng minh ĐÚNG việc này.
            nghiem_thu.insert(0, f"Làm đúng trách nhiệm đã duyệt: {trach_nhiem}")
        cung_cap = tuple(getattr(muc, "provides", ()) or ())
        if cung_cap:
            nghiem_thu.insert(
                1 if trach_nhiem else 0,
                "Xuất ĐÚNG những hàm bản phân rã đã hứa, giữ nguyên tên: "
                + ", ".join(f"`{h}`" for h in cung_cap)
                + ". Module khác gọi theo tên này.",
            )
        return Task(
            module_id=module_id,
            goal=muc_tieu,
            acceptance=tuple(nghiem_thu),
            uses=tuple(getattr(muc, "uses", ()) or ()),
            depends_on=tuple(getattr(muc, "depends_on", ()) or ()),
            output_files=cls.tep_can_sinh(module_id),
        )

    def khoa_pham_vi_tep(self, artifact: CodeArtifact, module_id: str) -> list[str]:
        """Bỏ khỏi artifact những tệp KHÔNG thuộc module đang sinh (SL-154).

        Bất biến: **mã đã merge chỉ đổi qua vòng sinh của CHÍNH module đó.**
        Mỗi tệp trên nhánh chính đã đi qua một lượt review G3 mang tên một
        module; một lượt sinh cho module khác viết đè lên nó là xoá quyết định
        ấy mà không ai bấm nút gì.

        Đã xảy ra: `eaa gen drv_imu` gặp bài kiểm của `drv_i2c` đỏ trong cùng
        lượt chạy pytest, và ba vòng tự sửa liên tiếp trả về `src/drv_i2c.c`
        viết lại từ đầu — xoá mất bốn hàm công khai của một module đã merge.
        `write_artifact` chặn đường dẫn THOÁT RA NGOÀI thư mục làm việc, nhưng
        bên trong thư mục ấy thì tệp nào cũng ghi được.

        Danh sách được phép sinh ra từ chính ``tep_can_sinh`` — cùng cái hàm
        viết câu "Tệp cần sinh" trong prompt. Chép tay lần thứ hai là mở đường
        cho hai bản lệch nhau.

        Tệp MỚI ngoài danh sách vẫn cho qua: một module có quyền thêm tệp phụ
        của chính nó, và tệp chưa có trên nhánh chính thì chưa là tài sản của
        ai. Chỉ chặn đúng chỗ đau: ghi đè tệp đã merge.
        """
        cho_phep = set(self.tep_can_sinh(module_id))
        da_merge = self.repo.files_on_main() if hasattr(self.repo, "files_on_main") else frozenset()
        bo_ra = [d for d in artifact.files if d not in cho_phep and d in da_merge]
        for duong_dan in bo_ra:
            artifact.files.pop(duong_dan, None)
        return sorted(bo_ra)

    def _cau_bo_tep(self, bo_ra: Sequence[str], module_id: str) -> str:
        """Nói ra việc đã bỏ. Bỏ im lặng là cách một bản vá biến mất không dấu vết."""
        if not bo_ra:
            return ""
        return (
            f"  ⚠ bỏ {len(bo_ra)} tệp ngoài phạm vi module {module_id} "
            "(đã merge, chỉ đổi được qua vòng sinh của chính nó): "
            + ", ".join(bo_ra)
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
            # Lớp nào đã bị lược để vừa ngân sách. `prompt.trimmed` được ghi từ
            # sprint đầu với chú thích "để KPI theo dõi", và KPI chưa bao giờ
            # nhận được nó — nên việc lược là im lặng tuyệt đối. Chính sự im
            # lặng ấy giấu SL-135: lý do người từ chối tại G3 bị xóa khỏi
            # prompt mà không dòng nào nói ra.
            trimmed=";".join(getattr(prompt, "trimmed", ()) or ()),
            result="pass",
        )
        return artifact

    @staticmethod
    def canh_bao_luoc(prompt: Any) -> str:
        """Câu nói ra rằng prompt vừa gửi đi thiếu một phần — rỗng nếu không thiếu.

        Vòng tự sửa chạm N vì thiếu ngữ cảnh là một chẩn đoán khác hẳn vòng tự
        sửa chạm N vì mã khó; phân biệt được hai thứ ấy chỉ khi việc lược bỏ
        không im lặng (AIS §12).
        """
        dong: list[str] = []
        da_luoc = list(getattr(prompt, "trimmed", ()) or ())
        if da_luoc:
            dong.append(
                "  ⚠ đã lược khỏi prompt để vừa ngân sách: "
                + ", ".join(da_luoc)
                + "\n    (mã sinh ra thiếu đúng phần này — xem lại nếu kết quả sai lệch)"
            )
        # Lớp dùng quá phần của nó mà trần TỔNG vẫn còn chỗ: không chặn, nhưng
        # cũng không im. Im lặng ở đây là cách một lớp phình dần tới lúc nó
        # thật sự lấn chỗ của lớp khác mà không ai thấy quá trình ấy (SL-161).
        qua_phan = list(getattr(prompt, "over_share", ()) or ())
        if qua_phan:
            dong.append(
                "  ⚠ lớp dùng quá phần nominal (trần tổng vẫn còn chỗ):\n"
                + "\n".join(qua_phan)
            )
        return "\n".join(dong)

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
        # Ở chế độ nháp chỉ chạy tập cổng người dùng chọn. Giữ nguyên THỨ TỰ
        # của chuỗi gốc chứ không theo thứ tự người dùng gõ: cổng sau ăn sản
        # phẩm của cổng trước, và đảo thứ tự thì cổng sau chạy trên thứ chưa có.
        chuoi = self.gate_chain
        if self.config.is_draft:
            chon = set(self.config.draft_gates)
            chuoi = [g for g in chuoi if getattr(g, "name", "") in chon]

        bao_cao: list[ToolReport] = []
        for cong in chuoi:
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
        """Cổng đo kích thước cần sản phẩm của cổng dịch — nối bằng metrics.

        Ưu tiên danh sách ``objects``: cổng dịch sinh một tệp đối tượng cho mỗi
        đơn vị dịch, và chiếm dụng của module là tổng của chúng. Khóa ``binary``
        giữ lại cho pack nào chỉ sinh một ảnh duy nhất.
        """
        if getattr(cong, "name", "") == "size":
            nguon_so = next(
                (
                    r.metrics
                    for r in reversed(truoc_do)
                    if r.metrics.get("objects") or r.metrics.get("binary")
                ),
                None,
            )
            if nguon_so is None:
                return ToolReport(
                    gate="size",
                    passed=False,
                    errors=[],
                    metrics={"skipped": "không có ảnh nhị phân từ cổng dịch"},
                )
            muc_tieu = nguon_so.get("objects") or nguon_so["binary"]
            return cong.run(muc_tieu, scope=nguon_so.get("size_scope", "module"))
        return cong.run(artifact)

    def _va_loi(
        self,
        task: Task,
        state: Any,
        bao_cao_hong: ToolReport,
        artifact: CodeArtifact,
        module_id: str,
    ) -> tuple[CodeArtifact, str]:
        """Bước 7–8 — prompt vá chỉ mang lỗi và hàm liên quan (AIS §3.2).

        Trả kèm câu cảnh báo lược bỏ: vòng vá là chỗ ngân sách chật nhất, nên
        cũng là chỗ dễ mất ngữ cảnh nhất mà không ai hay.
        """
        prompt = self.composer.build_repair(
            task, state, bao_cao_hong, artifact.files, counter=self.llm.count_tokens
        )
        ban_va = self.llm.generate(prompt)

        # Ghi token của LƯỢT VÁ. Không có dòng này thì trần token theo module
        # chỉ đếm lượt sinh đầu, và một module đi trọn ba vòng tự sửa báo về
        # đúng một phần tư số lượt gọi thật (SL-155). Đo được trên `drv_imu`:
        # 26 lượt trong `llm_calls.jsonl`, 13 dòng trong `kpi_log.csv`.
        #
        # Một cái trần chỉ đếm được nửa số tiền tiêu ra là một cái trần không
        # bảo vệ được gì — và chính vòng tự sửa mới là chỗ tiền chảy nhanh nhất.
        self._kpi(
            "repair",
            module_id,
            llm_model=ban_va.model,
            tokens_in=ban_va.tokens_in,
            tokens_out=ban_va.tokens_out,
            prompt_hash=ban_va.prompt_hash,
            constraints_version=ban_va.constraints_version,
            gate=bao_cao_hong.gate,
            result="pass",
            note="lượt gọi mô hình của vòng vá",
        )

        # Khoá phạm vi TRƯỚC khi gộp. Gộp xong mới lọc thì tệp của module khác
        # đã nằm lẫn trong tập và không còn phân biệt được nó đến từ bản vá hay
        # từ chính lượt sinh (SL-154).
        bo_ra = self.khoa_pham_vi_tep(ban_va, module_id)

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
        return ban_va, "\n".join(
            c for c in (self._cau_bo_tep(bo_ra, module_id), self.canh_bao_luoc(prompt)) if c
        )

    def _commit(self, artifact: CodeArtifact, module_id: str) -> str:
        """Bước 9 — ghi mã lên nhánh module với đủ dấu vết NFR-07."""
        from eaa.tools.compile import write_artifact

        write_artifact(artifact, self.repo.root)
        return self.repo.commit_artifact(artifact, module_id=module_id)

    #: Thứ không cần chép sang bản sao đo độ nhạy. Sản phẩm dịch phải bỏ vì
    #: `.so` của lần chạy trước sẽ được `ctypes` nạp thay cho mã cũ — đúng cái
    #: bẫy SL-152 đã dựng cổng để chặn, và chép nó sang là dựng lại cái bẫy ấy.
    _KHONG_CHEP = ("__pycache__", ".git", "build", "*.so", "*.dylib", "*.o", "*.a")

    def _do_nhay_bai_kiem(
        self, truoc: CodeArtifact, sau: CodeArtifact, module_id: str
    ) -> KetQuaDoNhay:
        """Bài kiểm vừa thêm có phân biệt được bản cũ với bản mới không (N-909).

        Chạy bộ kiểm MỚI trên mã CŨ, trong một bản sao tạm. Xanh trên cả hai
        bản nghĩa là nó không chứng minh được gì về lần sửa vừa rồi.

        KHÔNG chặn. Kết quả đi vào nhật ký và vào hồ sơ G3, vì bài học của
        chính ca sinh ra phép đo này là *màu của bài kiểm không thay thế được
        việc đọc mã ở G3* — một bộ đo tự nhận thay được người ở đây sẽ tái lập
        đúng cái sai nó sinh ra để chặn.
        """
        duong_dan = f"tests/test_{module_id}.py"
        moi = sau.files.get(duong_dan)
        if moi is None:
            return KetQuaDoNhay()
        bai_moi = bai_kiem_doi(truoc.files.get(duong_dan), moi)
        if not bai_moi:
            return KetQuaDoNhay()

        cong = next(
            (g for g in self.gate_chain if getattr(g, "name", "") == "unittests"), None
        )
        if cong is None:
            return ket_luan(
                bai_moi, "", do_duoc=False, ly_do="chuỗi cổng không có cổng unittests"
            )

        from eaa.tools.compile import write_artifact

        try:
            with tempfile.TemporaryDirectory(prefix="eaa-do-nhay-") as tam:
                goc = Path(tam) / "du_an"
                shutil.copytree(
                    Path(cong.work_dir),
                    goc,
                    ignore=shutil.ignore_patterns(*self._KHONG_CHEP),
                )
                # Mã CŨ trước — kèm cả bộ kiểm cũ của nó — rồi mới đặt đè bộ
                # kiểm MỚI lên. Ngược thứ tự thì bản vá ghi đè chính thứ đang đo.
                write_artifact(truoc, goc)
                (goc / duong_dan).parent.mkdir(parents=True, exist_ok=True)
                (goc / duong_dan).write_text(moi, encoding="utf-8")
                bao_cao = replace(cong, tests_dir=goc / "tests", work_dir=goc).run(None)
        except Exception as exc:  # noqa: BLE001 - đĩa, quyền, cổng tự nổ…
            return ket_luan(bai_moi, "", do_duoc=False, ly_do=f"{type(exc).__name__}: {exc}")
        return ket_luan(bai_moi, bao_cao.raw_output)

    def _xin_gate(
        self,
        module_id: str,
        branch: str,
        bao_cao: Sequence[ToolReport],
        artifact: CodeArtifact,
        do_nhay: KetQuaDoNhay | None = None,
    ) -> GatePayload:
        """Bước 10 — đặt hồ sơ lên bàn cho người, kèm checklist từ đồ thị."""
        # Độ nhạy vào ĐẦU checklist khi có bài kiểm không phân biệt được: nó là
        # câu duy nhất trong hồ sơ nói rằng một màu xanh ở đây không có nghĩa.
        muc_do_nhay: tuple[str, ...] = ()
        if do_nhay is not None and (do_nhay.bai_kiem_moi or not do_nhay.do_duoc):
            muc_do_nhay = (do_nhay.cau(),)
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
            checklist=muc_do_nhay + tuple(self.graph.review_checklist(module_id)),
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

    def _nghi_van_do_do(
        self, truoc: CodeArtifact, sau: CodeArtifact, module_id: str
    ) -> NghiVan:
        """Bản vá có chỉnh ĐỒ ĐO thay vì chỉnh cái bị đo không (N-908).

        Chỉ soi tệp `.c` của chính module. Tệp bài kiểm lấy bản MỚI, vì dấu vết
        thứ hai hỏi "mã có vừa mọc ra nhánh nhận đúng con số bài kiểm ĐANG đòi
        không" — con số ấy là con số hiện hành, không phải con số cũ.
        """
        duong_dan = f"src/{module_id}.c"
        moi = sau.files.get(duong_dan)
        cu = truoc.files.get(duong_dan)
        if not moi or not cu:
            return NghiVan()
        return nghi_van_chinh_do_do(
            cu,
            moi,
            nguon_test=sau.files.get(f"tests/test_{module_id}.py", ""),
            tep=duong_dan,
        )

    def _dung_vi_chinh_do_do(
        self,
        module_id: str,
        nghi: NghiVan,
        bao_cao: Sequence[ToolReport],
        so_lan_va: int,
        nhat_ky: Sequence[str],
    ) -> ModuleOutcome:
        """Dừng vòng vá và đưa câu hỏi về cho người (N-908 ở mức tự chủ T1).

        Câu phải trả lời là *"bài kiểm sai hay mã sai"*, và nó không trả lời
        được bằng máy: nó đòi biết bài toán. Cái máy làm được là nhận ra ba dấu
        vết mà cả ba ca đã gặp đều để lại, rồi hỏi sớm — hỏi sớm thì không đốt
        nốt ngân sách vá vào một hướng có thể đang sai.

        KHÔNG tự sửa và KHÔNG tự bỏ bản vá: sửa một bài kiểm sai là quyết định
        của người, y như sửa một trích đoạn datasheet phải đi qua G2.
        """
        self._dat_trang_thai(module_id, "handoff", retries=so_lan_va)
        self._kpi(
            "instrument_doubt",
            module_id,
            retries=so_lan_va,
            result="fail",
            note=f"{len(nghi.dau_vet)} dấu vết chỉnh đồ đo",
        )
        ghi = list(nhat_ky) + ["  ⚠ dừng: bản vá có dấu vết chỉnh đồ đo"]
        return ModuleOutcome(
            module_id=module_id,
            status="handoff",
            exit_code=EXIT_REPAIR_LIMIT,
            message=(
                f"DỪNG ở vòng vá {so_lan_va}: bản vá cho {module_id} có dấu vết "
                "SỬA CÁI ĐANG ĐO thay vì sửa cái bị đo.\n\n"
                + nghi.cau()
                + "\n\nBốn cổng sẽ báo ĐẠT cho một bản vá như thế — đó đúng là lý "
                "do dạng này lọt được ba lần trước.\n\n"
                "Câu phải trả lời, và nó là câu của người:\n"
                "  1. Con số bài kiểm đang đòi có đúng theo vật lý của bài toán không?\n"
                "     Đúng  → mã sai, sửa mã và giữ nguyên bài kiểm.\n"
                "     Sai   → bài kiểm sai, sửa bài kiểm và nói rõ vì sao bằng đại\n"
                "             lượng vật lý, không bằng 'để bài kiểm xanh'.\n"
                f"  2. Hằng số có `// ref:` mà đổi thì trích dẫn phải đổi theo — và\n"
                f"     đổi trích đoạn tài liệu là việc đi qua G2.\n\n"
                f"Bản vá vẫn nằm nguyên trong {nghi.tep or 'tệp module'} để đọc; "
                "hệ không tự sửa và cũng không tự bỏ nó.\n\n"
                "Nhật ký từng vòng:\n" + "\n".join(ghi)
            ),
            reports=list(bao_cao),
            repairs=so_lan_va,
            attempts_log=ghi,
        )

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

    def _pha_vo_hop_dong(self, artifact: CodeArtifact, module_id: str) -> list[str]:
        """Hàm công khai đã mất hoặc đổi chữ ký so với bản đang nằm trên `main`.

        Rỗng khi chưa có gì để so — module sinh lần đầu, hoặc kho chưa có nhánh
        chính. Rỗng cũng khi kho không cho đọc: một phép kiểm phụ trợ không
        được quyền làm hỏng lượt sinh vì lý do của chính nó.
        """
        duong_dan = f"src/{module_id}.h"
        moi = artifact.files.get(duong_dan)
        if not moi:
            return []
        try:
            cu = self.repo.read_on_main(duong_dan)
        except Exception:  # noqa: BLE001
            return []
        if not cu:
            return []
        return pha_vo_hop_dong(cu, moi)

    def _ham_cong_khai_module_khac(self, module_id: str) -> frozenset[str]:
        """Tên hàm công khai của MỌI module khác đã merge.

        Đây là tập "quan tâm" của phép so lời gọi (N-910). Giới hạn vào header
        của module khác có chủ ý ba lần:

        * hàm nội bộ của chính tệp này mất đi thường là tái cấu trúc;
        * hàm thư viện C không nằm trong header nào của dự án, nên tự rơi ra;
        * hàm công khai của CHÍNH module này gọi từ chính nó cũng là việc nội
          bộ — nó đã có `pha_vo_hop_dong` canh ở tầng khai báo rồi.

        Rỗng khi kho chưa có nhánh chính hoặc chưa module nào merge: lúc ấy
        chưa có việc liên module nào để mà đánh rơi.
        """
        rieng = f"src/{module_id}.h"
        ten: set[str] = set()
        try:
            tep = self.repo.files_on_main()
        except Exception:  # noqa: BLE001 - kho chưa dựng, không quyền đọc…
            return frozenset()
        for duong_dan in sorted(tep):
            if duong_dan == rieng or not duong_dan.endswith(".h"):
                continue
            if not duong_dan.startswith("src/"):
                continue
            try:
                nguon = self.repo.read_on_main(duong_dan)
            except Exception:  # noqa: BLE001
                continue
            if nguon:
                ten.update(khai_bao_ham(nguon))
        return frozenset(ten)

    def _mat_loi_goi(self, artifact: CodeArtifact, module_id: str) -> list[str]:
        """Lời gọi liên module có trong bản đã merge mà bản mới đánh rơi.

        Cùng luật "rỗng khi chưa có gì để so" như `_pha_vo_hop_dong`: một phép
        kiểm phụ trợ không được quyền làm hỏng lượt sinh vì lý do của chính nó.
        """
        duong_dan = f"src/{module_id}.c"
        moi = artifact.files.get(duong_dan)
        if moi is None:
            return []
        try:
            cu = self.repo.read_on_main(duong_dan)
        except Exception:  # noqa: BLE001
            return []
        if not cu:
            return []
        return mat_loi_goi(cu, moi, self._ham_cong_khai_module_khac(module_id))

    @staticmethod
    def _bao_cao_hop_dong(
        vi_pham: list[str], mat_goi: list[str], module_id: str
    ) -> ToolReport:
        """Vi phạm hợp đồng đi vào ĐƯỜNG VÁ, không vào đường chặn.

        Khác SL-162 ở chỗ ấy, và khác vì một lý do: lỗi ngoài phạm vi là thứ
        vòng vá KHÔNG có quyền sửa, còn đây là mã của chính nó và nó sửa được —
        thêm lại tham số đã bỏ là một lượt vá bình thường.

        Hai hạng vi phạm đi thành HAI lỗi riêng, mỗi lỗi gắn đúng tệp của nó
        (`.h` cho chữ ký, `.c` cho lời gọi). Gộp một dòng thì lớp quy lỗi về tệp
        của SL-162 chỉ còn quy được về một chỗ, và nửa kia mất địa chỉ.
        """
        loi: list[ToolError] = []
        if vi_pham:
            loi.append(
                ToolError(
                    f"Header `src/{module_id}.h` phá hợp đồng của bản ĐÃ MERGE. "
                    "Mã đang gọi những hàm này không dịch được nữa.\n"
                    + "\n".join(vi_pham)
                    + "\n\nGiữ NGUYÊN chữ ký cũ. Cần thêm khả năng thì thêm hàm "
                    "mới bên cạnh — mở rộng thì được, thu hẹp hay đổi thì không.",
                    file=f"src/{module_id}.h",
                )
            )
        if mat_goi:
            loi.append(
                ToolError(
                    f"`src/{module_id}.c` đánh rơi lời gọi sang module khác so "
                    "với bản ĐÃ MERGE. Mã vẫn dịch được và bài kiểm đơn vị vẫn "
                    "xanh — việc ấy chỉ đơn giản là KHÔNG CÒN AI LÀM.\n"
                    + "\n".join(mat_goi)
                    + "\n\nGọi lại đủ. Nếu cố ý bỏ thì đó là quyết định của "
                    "người, không phải của một lượt vá.",
                    file=f"src/{module_id}.c",
                )
            )
        return ToolReport(
            gate="contract",
            passed=False,
            errors=loi,
            metrics={
                "contract_violations": len(vi_pham),
                "lost_calls": len(mat_goi),
            },
        )

    @staticmethod
    def _loi_ngoai_pham_vi(bao_cao: ToolReport, module_id: str) -> list[str]:
        """Tệp đỏ nằm ngoài tập tệp mà lượt sinh này được phép viết (SL-162).

        Trả danh sách RỖNG trừ khi chắc chắn: phải quy được MỌI thất bại về
        một tệp, và mọi tệp ấy đều ngoài phạm vi. Một thất bại không quy được
        về tệp nào — hoặc quy được về đúng tệp của module — thì vòng vá vẫn mở.

        Ngả về phía vá là có chủ ý. Chặn nhầm thì dừng cả dây chuyền và đòi
        người; vá nhầm thì tốn lượt gọi. Chỉ hạng sai thứ hai là thứ tự nó
        khỏi được.
        """
        trong_pham_vi = set(Orchestrator.tep_can_sinh(module_id))

        tep = list(bao_cao.metrics.get("failing_files") or [])
        if not tep:
            neo = [e.file for e in bao_cao.errors if e.severity == Severity.ERROR]
            if not neo or not all(neo):
                return []
            tep = list(dict.fromkeys(neo))  # type: ignore[arg-type]

        ngoai = [t for t in tep if t.replace("\\", "/").lstrip("./") not in trong_pham_vi]
        return ngoai if len(ngoai) == len(tep) else []

    @staticmethod
    def tep_can_sinh(module_id: str) -> tuple[str, ...]:
        """Những tệp một lượt sinh mã phải trả về.

        Có tệp TEST trong này, và đó là chỗ SL-134 sửa. `unittests` nằm trong
        ``required_gates`` — không qua nó thì không merge, không merge thì không
        ráp được firmware — nhưng danh sách này trước đây chỉ có `.c` và `.h`.
        Một cổng bắt buộc đòi thứ không năng lực nào sinh ra, nên quy trình
        không có cách nào tự qua cổng của chính nó.

        Và nó không phải chuyện "quên viết test": thiết kế nói firmware được
        viết tách lớp trừu tượng phần cứng CHÍNH LÀ để chạy được trên máy chủ
        (công đoạn C2). Lời hứa ấy chỉ thành thật khi mỗi module ra đời KÈM bài
        kiểm chứng minh nó chạy được ở đó.

        Tên theo quy ước ``test_*.py`` vì cổng gom đúng mẫu ấy.
        """
        return (
            f"src/{module_id}.c",
            f"src/{module_id}.h",
            f"tests/test_{module_id}.py",
        )

    def _kpi(self, event: str, module_id: str, **truong: Any) -> None:
        if self.kpi is None:
            return
        self.kpi.log(event=event, module=module_id, phase=GENERATION_PHASE, **truong)
