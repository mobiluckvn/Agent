"""Điểm vào CLI — EAA-SDD-03 §5 (bộ lệnh) và §6 (mã thoát).

Sprint 0 giao ``eaa init``, ``eaa resume``, ``eaa status`` và ``eaa policy``
chạy thật; các lệnh còn lại đã có mặt trong bộ lệnh nhưng khai báo thẳng rằng
chúng thuộc sprint nào và thoát với mã lỗi. Cố ý KHÔNG để lệnh nào in ra thứ
trông như kết quả trong khi chưa làm gì: một cổng kiểm chứng giả vờ đạt còn
nguy hiểm hơn một cổng chưa tồn tại.

Mã thoát (SDD §6) — để script hóa thực nghiệm A/B:

* ``0`` thành công
* ``2`` chờ gate
* ``3`` quá N lần tự sửa (bàn giao người)
* ``4`` lỗi môi trường (thiếu toolchain, thiếu cấu hình dự án)

Việc đọc các kho tri thức thuộc ``eaa/kb.py``; ``cli.py`` chỉ gọi và trình bày.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from eaa import (
    EXIT_ENV_ERROR,
    EXIT_OK,
    EXIT_WAITING_GATE,
    __version__,
)
from eaa.kb import Constraints, HardwareProfile, KbError
from eaa.platform import PackError, discover_packs, load_manifest
from eaa.policy import (
    GATE_ORDER,
    GATE_PURPOSE,
    PHASE_NAMES,
    PHASE_ORDER,
    STAGES,
    PolicyViolation,
    can_transition,
    check_transition,
    gate_for_transition,
    level,
)
from eaa.state import BacklogItem, ProjectState, StateCorruptError, StateStore

CONSTRAINTS_FILE = "constraints.yaml"
HARDWARE_PROFILE_FILE = "hardware_profile.yaml"
STATE_FILE = "project_state.json"


class CliError(Exception):
    """Lỗi có thông điệp dành cho người dùng, kèm mã thoát tương ứng."""

    def __init__(self, message: str, exit_code: int = EXIT_ENV_ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# --------------------------------------------------------------------------
# Định vị dự án và nạp cấu hình
# --------------------------------------------------------------------------


ENV_FILE = ".env"


def load_env_file(root: Path | None = None) -> list[str]:
    """Nạp ``.env`` vào biến môi trường của tiến trình.

    NFR-06 nói khóa chỉ đi qua biến môi trường. Tệp này KHÔNG phá quy tắc đó:
    nó chỉ là chỗ nạp vào môi trường lúc khởi động, và adapter mô hình vẫn chỉ
    đọc ``os.environ`` chứ không biết tệp nào tồn tại.

    Hai luật:

    * **Biến đã đặt trong shell luôn thắng.** Người gõ ``EAA_LLM_KEY=... eaa
      gen`` phải nhận đúng khóa họ vừa gõ, không phải khóa cũ trong tệp.
    * **Không bao giờ in nội dung tệp ra.** Trả về TÊN biến đã nạp, không trả
      giá trị — danh sách này có thể đi vào log.
    """
    duong_dan = (root or repo_root()) / ENV_FILE
    if not duong_dan.is_file():
        return []

    da_nap: list[str] = []
    for dong in duong_dan.read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#") or "=" not in dong:
            continue
        ten, gia_tri = dong.split("=", 1)
        ten = ten.strip()
        gia_tri = gia_tri.strip().strip('"').strip("'")
        if not ten or not gia_tri:
            continue
        if os.environ.get(ten):
            continue
        os.environ[ten] = gia_tri
        da_nap.append(ten)
    return da_nap


def repo_root() -> Path:
    """Gốc cài đặt EAA — nơi chứa ``packs/`` và ``projects/``."""
    return Path(os.environ.get("EAA_HOME", Path(__file__).resolve().parent.parent))


def resolve_project(duong_dan: str | None) -> Path:
    """Tìm thư mục dự án theo thứ tự: tham số → biến môi trường → duy nhất.

    FR-PLT-03 dự trù nhiều dự án song song; ở đây chỉ chọn dự án, chưa quản lý
    vòng đời ``eaa new/switch`` (Should, chưa thuộc MVP).
    """
    if duong_dan:
        goc = Path(duong_dan).expanduser().resolve()
        if not goc.is_dir():
            raise CliError(f"Không có thư mục dự án: {goc}")
        return goc

    tu_moi_truong = os.environ.get("EAA_PROJECT")
    if tu_moi_truong:
        return resolve_project(tu_moi_truong)

    thu_muc = repo_root() / "projects"
    ung_vien = (
        sorted(p for p in thu_muc.iterdir() if (p / CONSTRAINTS_FILE).is_file())
        if thu_muc.is_dir()
        else []
    )
    if not ung_vien:
        raise CliError(
            f"Không tìm thấy dự án nào trong {thu_muc}. Dùng --project <đường dẫn> "
            "hoặc đặt biến môi trường EAA_PROJECT."
        )
    if len(ung_vien) > 1:
        ten = ", ".join(p.name for p in ung_vien)
        raise CliError(
            f"Có nhiều dự án ({ten}) — chỉ rõ bằng --project hoặc EAA_PROJECT."
        )
    return ung_vien[0]


def _nap_kho(nap, *args):  # type: ignore[no-untyped-def]
    """Gọi một bộ nạp của Knowledge Base, đổi lỗi kho thành lỗi CLI có mã thoát."""
    try:
        return nap(*args)
    except KbError as exc:
        raise CliError(str(exc)) from exc


# --------------------------------------------------------------------------
# Trình bày
# --------------------------------------------------------------------------


def _in_tieu_de(text: str) -> None:
    print(f"\n{text}\n{'─' * len(text)}")


def _nhan_gate(state: ProjectState, gate: str) -> str:
    bieu_tuong = {"approved": "✓", "pending": "…", "rejected": "✗"}
    trang_thai = state.gate_status(gate)
    return f"{bieu_tuong.get(trang_thai, '?')} {gate} {trang_thai:<9} {GATE_PURPOSE[gate]}"


def _buoc_ke_tiep(state: ProjectState) -> tuple[str, int]:
    """Câu trả lời cho "giờ làm gì tiếp" — cùng với mã thoát tương ứng."""
    chi_so = PHASE_ORDER.index(state.phase)
    dich = PHASE_ORDER[chi_so + 1] if chi_so + 1 < len(PHASE_ORDER) else None

    try:
        gate = gate_for_transition(state.phase, dich)
    except PolicyViolation as exc:  # pragma: no cover - bảng luật đã phủ hết
        return str(exc), EXIT_ENV_ERROR

    ten_dich = f"pha {dich}" if dich else "kết thúc dự án"
    if gate is None:
        return f"Chuyển sang {ten_dich} — cung này không có gate.", EXIT_OK

    if state.gate_status(gate) == "approved":
        return f"{gate} đã duyệt — chuyển sang {ten_dich}.", EXIT_OK

    return (
        f"Đang chờ {gate} ({GATE_PURPOSE[gate]}) để sang {ten_dich}. "
        f"Chạy 'eaa gate show'.",
        EXIT_WAITING_GATE,
    )


def _in_tom_tat(state: ProjectState, project: Path) -> int:
    _in_tieu_de(f"Dự án: {project.name}  ({project})")
    print(f"Pha hiện tại : {state.phase} — {PHASE_NAMES[state.phase]}")
    print(f"Mức phân quyền: {level(state.phase)}")
    print(f"Ràng buộc     : {state.constraints_version}")
    if state.llm:
        print(f"Mô hình       : {state.llm.get('provider', '?')}/{state.llm.get('model', '?')}")
    if state.env_hash:
        print(f"Môi trường    : {state.env_hash}")
    print(f"Cập nhật lúc  : {state.updated_at}")

    _in_tieu_de("Human Gate")
    for gate in GATE_ORDER:
        print("  " + _nhan_gate(state, gate))

    _in_tieu_de(f"Backlog ({len(state.backlog)} module)")
    if not state.backlog:
        print("  (trống — thêm bằng 'eaa plan add <module_id>')")
    else:
        for item in state.backlog:
            danh_dau = "→" if item.id == state.current_module else " "
            uses = f"  uses={','.join(item.uses)}" if item.uses else ""
            print(f"  {danh_dau} {item.id:<28} {item.status:<10} retries={item.retries}{uses}")

    _in_tieu_de("Bước kế tiếp")
    thong_diep, ma_thoat = _buoc_ke_tiep(state)
    print(f"  {thong_diep}")
    return ma_thoat


# --------------------------------------------------------------------------
# Lệnh
# --------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """UC01 — khởi tạo dự án: đọc ràng buộc, hồ sơ phần cứng, tạo Project State."""
    project = resolve_project(args.project)
    store = StateStore(project / STATE_FILE)

    if store.exists() and not args.force:
        raise CliError(
            f"Đã có Project State tại {store.path}. Dùng 'eaa resume' để tiếp tục, "
            "hoặc 'eaa init --force' nếu thật sự muốn khởi tạo lại."
        )

    rang_buoc: Constraints = _nap_kho(Constraints.load, project / CONSTRAINTS_FILE)
    ho_so: HardwareProfile = _nap_kho(
        HardwareProfile.load, project / HARDWARE_PROFILE_FILE
    )

    try:
        manifest = load_manifest(repo_root() / "packs" / rang_buoc.platform)
    except PackError as exc:
        raise CliError(str(exc)) from exc

    state = ProjectState(
        phase="A",
        gates={gate: "pending" for gate in GATE_ORDER},
        backlog=[],
        constraints_version=rang_buoc.content_version,
        llm={"provider": args.provider, "model": args.model},
    )
    store.save(state)

    _in_tieu_de("Đã khởi tạo dự án")
    print(f"  Thư mục       : {project}")
    print(f"  Project State : {store.path}")
    print(f"  Platform Pack : {manifest.name} v{manifest.version}")
    print(f"  Ràng buộc     : v{rang_buoc.version} {state.constraints_version}")
    print(f"  Hồ sơ phần cứng: {len(ho_so.peripherals)} ngoại vi, "
          f"{len(ho_so.components)} linh kiện, "
          f"{len(ho_so.pin_map)} chân")
    print(f"  Mô hình       : {args.provider}/{args.model}")
    print(
        f"\nDự án bắt đầu ở pha A ({PHASE_NAMES['A']}), toàn bộ gate ở trạng thái "
        "pending.\nBước kế tiếp: chốt ràng buộc & kiến trúc rồi duyệt G1."
    )
    return EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    """UC10 — khôi phục phiên làm việc từ Project State sau khi tắt máy/crash."""
    project = resolve_project(args.project)
    store = StateStore(project / STATE_FILE)
    try:
        state = store.load()
    except FileNotFoundError as exc:
        raise CliError(str(exc)) from exc
    except StateCorruptError as exc:
        raise CliError(str(exc)) from exc

    return _in_tom_tat(state, project)


def cmd_status(args: argparse.Namespace) -> int:
    """Bí danh chỉ-đọc của ``resume`` — tiện gọi trong script mà không gợi ý
    rằng có gì đó được khôi phục."""
    return cmd_resume(args)


def cmd_policy(args: argparse.Namespace) -> int:
    """In bảng phân quyền và máy trạng thái đang có hiệu lực."""
    _in_tieu_de("Ma trận Người–AI — 6 giai đoạn, 13 công đoạn")
    print(f"  {'Mã':<4}{'Pha':<5}{'Mức':<9}{'Người/AI':<10}Công đoạn")
    for ma, cd in STAGES.items():
        print(f"  {ma:<4}{cd.phase:<5}{str(cd.level):<9}{cd.human_share}/{cd.ai_share:<7}{cd.name}")

    _in_tieu_de("Máy trạng thái và gate trên cung chuyển")
    for i, pha in enumerate(PHASE_ORDER):
        dich = PHASE_ORDER[i + 1] if i + 1 < len(PHASE_ORDER) else None
        gate = gate_for_transition(pha, dich)
        ten_dich = dich if dich else "kết thúc"
        nhan = f"cần {gate} ({GATE_PURPOSE[gate]})" if gate else "không gate"
        print(f"  {pha} → {ten_dich:<9} {nhan}")
    print("  E → D         vòng lùi tinh chỉnh (luôn đi qua con người)")
    return EXIT_OK


def cmd_packs(args: argparse.Namespace) -> int:
    """Liệt kê Platform Pack đã cài — bằng chứng vận hành cho NFR-05."""
    packs = discover_packs(repo_root() / "packs")
    if not packs:
        raise CliError(f"Không tìm thấy Platform Pack nào trong {repo_root() / 'packs'}")

    _in_tieu_de(f"Platform Pack ({len(packs)})")
    for manifest in packs.values():
        print(f"  {manifest.name} v{manifest.version} — đích: {', '.join(manifest.targets) or '—'}")
        for ten in sorted(manifest.capabilities):
            goi = manifest.invocation(ten)
            ghi_chu = " [cần người xác nhận]" if goi.requires_confirmation else ""
            print(f"      {ten:<8} {goi.command[0]}{ghi_chu}")
    return EXIT_OK


def _chua_hien_thuc(ten: str, sprint: str, ghi_chu: str = "") -> Any:
    def handler(args: argparse.Namespace) -> int:
        raise CliError(
            f"Lệnh '{ten}' thuộc {sprint} và chưa được hiện thực hóa.\n"
            + (f"{ghi_chu}\n" if ghi_chu else "")
            + "Đang có: init, resume, status, policy, packs, plan, gen, gate, "
            "report, ledger.",
        )

    return handler


# --------------------------------------------------------------------------
# Lắp ráp ứng dụng — CLI là nơi ráp mọi thứ lại
# --------------------------------------------------------------------------


@dataclass
class AppContext:
    """Mọi thành phần của một dự án, đã nối dây sẵn.

    CLI là composition root: nó là nơi duy nhất biết cách ráp Knowledge Base,
    đồ thị, composer, adapter mô hình, gate, Git, KPI và chuỗi cổng lại với
    nhau. Các module khác nhận phụ thuộc qua hàm dựng và không tự đi tìm nhau —
    nhờ vậy mỗi module test được riêng, và việc thay MockLLM bằng mô hình thật
    ở Sprint 4 chỉ là đổi một dòng ở đây.
    """

    project: Path
    store: Any
    kb: Any
    graph: Any
    ledger: Any
    kpi: Any
    composer: Any
    llm: Any
    gates: Any
    repo: Any
    runner: Any
    orchestrator: Any


def _tao_llm(state: Any, project: Path) -> Any:
    """Chọn adapter mô hình theo cấu hình trong Project State (ADR-03).

    TC-11 đòi hỏi đổi nhà cung cấp không làm đổi hành vi Orchestrator, nên chỗ
    duy nhất biết adapter nào đang chạy là hàm này.

    Thứ tự quyết mã model: Project State → biến môi trường ``EAA_LLM_MODEL`` →
    mặc định của adapter. Project State thắng vì nó đi cùng dự án và nằm trong
    Git — mã model là một phần của điều kiện thí nghiệm, không phải một tùy
    chọn của phiên làm việc.
    """
    from eaa.llm.calllog import CallLog, ReplayClient
    from eaa.llm.mock import MockLLM

    provider = (state.llm or {}).get("provider", "mock")
    model = (state.llm or {}).get("model") or os.environ.get("EAA_LLM_MODEL", "")
    nhat_ky = CallLog(project / "llm_calls.jsonl")

    if provider == "mock":
        return MockLLM(model=model or "mock-deterministic-1")

    if provider == "replay":
        return ReplayClient(nhat_ky)

    if provider == "gemini":
        from eaa.llm.gemini import DEFAULT_MODEL, GeminiClient

        return GeminiClient(model=model or DEFAULT_MODEL, call_log=nhat_ky)

    raise CliError(
        f"Chưa có adapter cho nhà cung cấp {provider!r}. Đang hỗ trợ: "
        "mock (tất định, không tốn API), replay (phát lại nhật ký đã ghi), "
        "gemini (mô hình thật)."
    )


def build_context(project: Path, *, llm: Any = None) -> AppContext:
    """Nối dây toàn bộ một dự án từ thư mục của nó."""
    from eaa.composer import PromptComposer
    from eaa.gates import HumanGate
    from eaa.graph import KnowledgeGraph
    from eaa.kb import KnowledgeBase
    from eaa.kpi import KpiLogger
    from eaa.ledger import ErrorLedger
    from eaa.orchestrator import Orchestrator, OrchestratorConfig
    from eaa.readiness import ReadinessChecker
    from eaa.tools.compile import CompileGate, SizeGate
    from eaa.tools.runner import ToolRunner
    from eaa.tools.static import StaticGate
    from eaa.tools.unittests import UnitTestGate
    from eaa.vcs import GitRepo

    store = StateStore(project / STATE_FILE)
    if not store.exists():
        raise CliError(
            f"Chưa có Project State tại {store.path} — chạy 'eaa init' trước."
        )
    state = store.load()

    manifest = _nap_pack(project)
    kb = _nap_kho(KnowledgeBase.load, project, manifest.prompts_dir)

    graph = KnowledgeGraph.build(kb.hardware, kb.datasheets, modules=state.backlog)
    ledger = ErrorLedger(project / "error_ledger.jsonl")
    kb.ledger = ledger
    kpi = KpiLogger(project / "kpi_log.csv", env_hash=state.env_hash)
    composer = PromptComposer(kb, graph, ledger)
    gates = HumanGate(project / "gates", store, ledger)

    firmware = project / "firmware"
    repo = GitRepo(firmware)
    repo.init()

    runner = ToolRunner(
        manifest=manifest,
        work_dir=firmware,
        base_params={
            **kb.constraints.platform_params(),
            "python": sys.executable,
            "pack_dir": str(manifest.root),
        },
    )

    module_hien_tai = state.current_module or (
        state.backlog[0].id if state.backlog else ""
    )
    chain = [
        CompileGate(runner),
        SizeGate(runner, limits=kb.constraints.limits),
        StaticGate(
            runner=runner,
            manifest=manifest,
            forbidden=list(kb.constraints.forbidden),
            limits=kb.constraints.limits,
            registers=graph.registers_for(module_hien_tai) if module_hien_tai else [],
            allowed_chunk_ids=[c.id for c in kb.datasheets.active()],
        ),
        UnitTestGate(tests_dir=project / "tests", work_dir=project),
    ]

    orchestrator = Orchestrator(
        state_store=store,
        composer=composer,
        llm=llm or _tao_llm(state, project),
        gates=gates,
        repo=repo,
        graph=graph,
        kpi=kpi,
        ledger=ledger,
        readiness=ReadinessChecker(kb=kb, graph=graph),
        gate_chain=chain,
        config=OrchestratorConfig(actor=_nguoi_dung()),
        runs_dir=project / ".eaa" / "runs",
    )

    return AppContext(
        project=project,
        store=store,
        kb=kb,
        graph=graph,
        ledger=ledger,
        kpi=kpi,
        composer=composer,
        llm=orchestrator.llm,
        gates=gates,
        repo=repo,
        runner=runner,
        orchestrator=orchestrator,
    )


def _nap_pack(project: Path) -> Any:
    rang_buoc = _nap_kho(Constraints.load, project / CONSTRAINTS_FILE)
    try:
        return load_manifest(repo_root() / "packs" / rang_buoc.platform)
    except PackError as exc:
        raise CliError(str(exc)) from exc


def _nguoi_dung() -> str:
    for bien in ("EAA_ACTOR", "USER", "USERNAME", "LOGNAME"):
        gia_tri = os.environ.get(bien)
        if gia_tri:
            return gia_tri
    return "kỹ sư"


# --------------------------------------------------------------------------
# UC02 — quản lý backlog
# --------------------------------------------------------------------------


def cmd_plan(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    store = StateStore(project / STATE_FILE)
    if not store.exists():
        raise CliError(f"Chưa có Project State tại {store.path} — chạy 'eaa init'.")

    if args.plan_action == "list":
        return _plan_list(store)
    if args.plan_action == "add":
        return _plan_add(project, store, args)
    if args.plan_action == "order":
        return _plan_order(store, args)
    raise CliError(f"Hành động không hợp lệ: {args.plan_action!r}")


def _plan_list(store: StateStore) -> int:
    state = store.load()
    _in_tieu_de(f"Backlog ({len(state.backlog)} module)")
    if not state.backlog:
        print("  (trống — thêm bằng 'eaa plan add <module_id>')")
        return EXIT_OK
    for i, muc in enumerate(state.backlog, 1):
        uses = f"  uses={','.join(muc.uses)}" if muc.uses else ""
        pt = f"  depends_on={','.join(muc.depends_on)}" if muc.depends_on else ""
        print(f"  {i:>2}. {muc.id:<28} {muc.status:<10} retries={muc.retries}{uses}{pt}")
    return EXIT_OK


def _plan_add(project: Path, store: StateStore, args: argparse.Namespace) -> int:
    """Quy trình P2 — kiểm xung đột NGAY LÚC KHAI BÁO, trước khi vào backlog.

    Đây là điểm "shift-left" của AIS §5.2: tranh chấp tài nguyên bị bắt ở giây
    thứ nhất thay vì trên thiết bị thật. Module không vào backlog nếu còn xung
    đột — kỹ sư phân xử trước.
    """
    from eaa.graph import KnowledgeGraph

    uses = [u.strip() for u in (args.uses or "").split(",") if u.strip()]
    depends = [d.strip() for d in (args.depends_on or "").split(",") if d.strip()]

    state = store.load()
    if state.module(args.module_id) is not None:
        raise CliError(f"Module {args.module_id!r} đã có trong backlog.")

    kb = _nap_kho(__import__("eaa.kb", fromlist=["KnowledgeBase"]).KnowledgeBase.load, project)
    graph = KnowledgeGraph.build(kb.hardware, kb.datasheets, modules=state.backlog)

    xung_dot = graph.check_module(args.module_id, uses=uses, depends_on=depends)
    if xung_dot:
        _in_tieu_de(f"Không thêm {args.module_id} — có xung đột cần phân xử")
        for c in xung_dot:
            print(f"  • {c.message}")
            for bang_chung in c.evidence:
                print(f"      {bang_chung}")
        raise CliError(
            "Xung đột tài nguyên phải do kỹ sư phân xử (FR-KG-02, quy trình P2). "
            "Đổi tài nguyên của module, hoặc khai báo tài nguyên dùng chung được "
            "trong hardware_profile.yaml."
        )

    with store.with_lock():
        state = store.load()
        state.backlog.append(
            BacklogItem(id=args.module_id, status="todo", uses=uses, depends_on=depends)
        )
        store.save(state)

    # Đưa module vào đồ thị rồi mới tra: ``check_module`` chạy trên bản sao nên
    # không để lại dấu vết, và tra cứu trước khi thêm sẽ ra danh sách rỗng.
    graph.add_module(args.module_id, uses=uses, depends_on=depends)

    print(f"Đã thêm {args.module_id} vào backlog (không có xung đột tài nguyên).")
    if uses:
        thanh_ghi = graph.registers_for(args.module_id)
        print(f"  Tài nguyên chiếm dụng: {', '.join(uses)}")
        print(f"  Thanh ghi phải cấu hình: {', '.join(thanh_ghi) or '—'}")

        # Nói ngay nếu có thanh ghi chưa được tài liệu hóa — đây là mục THIẾU
        # của Bảng kiểm thông tin cần (AIS §6.2), và biết sớm thì kỹ sư còn kịp
        # nạp tài liệu trước khi mở vòng sinh mã.
        co_tai_lieu = kb.datasheets.registers()
        thieu = [r for r in thanh_ghi if r not in co_tai_lieu]
        if thieu:
            print(
                f"  ⚠ Chưa có trích đoạn tài liệu cho: {', '.join(thieu)} — "
                "nạp và duyệt tại G2 trước khi sinh mã."
            )
    return EXIT_OK


def _plan_order(store: StateStore, args: argparse.Namespace) -> int:
    thu_tu = [m.strip() for m in args.order.split(",") if m.strip()]
    with store.with_lock():
        state = store.load()
        co = {m.id for m in state.backlog}
        la = [m for m in thu_tu if m not in co]
        if la:
            raise CliError(f"Không có trong backlog: {la}")
        theo_id = {m.id: m for m in state.backlog}
        state.backlog = [theo_id[m] for m in thu_tu] + [
            m for m in state.backlog if m.id not in thu_tu
        ]
        store.save(state)
    return _plan_list(store)


# --------------------------------------------------------------------------
# UC04 — vòng lặp sinh mã
# --------------------------------------------------------------------------


def cmd_gen(args: argparse.Namespace) -> int:
    from eaa.orchestrator import PreconditionFailed

    project = resolve_project(args.project)
    ctx = build_context(project)

    try:
        ket_qua = ctx.orchestrator.run_module(args.module_id)
    except PreconditionFailed as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de(f"Vòng lặp chuẩn — {args.module_id}")
    for dong in ket_qua.attempts_log:
        print(dong)
    print()
    print(ket_qua.message)
    return ket_qua.exit_code


# --------------------------------------------------------------------------
# UC05 — Human Gate
# --------------------------------------------------------------------------


def cmd_gate(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    ctx = build_context(project)

    if args.gate_action == "show":
        return _gate_show(ctx, args)
    if args.gate_action == "approve":
        return _gate_approve(ctx, args)
    if args.gate_action == "reject":
        return _gate_reject(ctx, args)
    raise CliError(f"Hành động không hợp lệ: {args.gate_action!r}")


def _ho_so_gate(ctx: AppContext, gate_id: str) -> Any:
    """Dựng hồ sơ cho gate chưa có yêu cầu nào đang chờ.

    G3 luôn có hồ sơ do Orchestrator đặt ở bước 10. Các gate còn lại được kỹ sư
    chủ động mở, nên hồ sơ dựng từ dữ liệu hiện hành của dự án. Băm nội dung vì
    thế phản ánh đúng thứ đang có trên đĩa lúc này — duyệt xong mà dữ liệu đổi
    thì quyết định cũ không còn khớp.
    """
    from eaa.gates import GatePayload

    state = ctx.store.load()
    if gate_id == "G1":
        return GatePayload(
            gate_id="G1",
            title="Chốt ràng buộc cứng và kiến trúc",
            summary=(
                f"constraints.yaml v{ctx.kb.constraints.version} "
                f"({ctx.kb.constraints.content_version})",
                f"hardware_profile.yaml v{ctx.kb.hardware.version}",
                f"backlog: {len(state.backlog)} module",
                f"điều cấm: {', '.join(ctx.kb.constraints.forbidden) or '—'}",
            ),
            details=ctx.kb.constraints.path.read_text(encoding="utf-8"),
            content_digest=ctx.kb.constraints.content_version,
        )
    if gate_id == "G2":
        de_xuat = [c for c in ctx.kb.datasheets.all() if not c.is_active]
        return GatePayload(
            gate_id="G2",
            title="Duyệt trích đoạn tài liệu vào kho tri thức",
            summary=tuple(
                f"{c.id} · {c.device}/{c.peripheral} · {c.status} · {c.source}"
                for c in ctx.kb.datasheets.all()
            ),
            details="\n\n".join(f"### {c.id}\n{c.body}" for c in de_xuat) or
            "(không có chunk nào đang chờ duyệt)",
            content_digest="sha256:" + __import__("hashlib").sha256(
                "|".join(sorted(c.id + c.status for c in ctx.kb.datasheets.all())).encode()
            ).hexdigest(),
        )
    raise CliError(
        f"Gate {gate_id} chưa có hồ sơ nào đang chờ, và engine chưa biết cách dựng "
        f"hồ sơ cho gate này. G4/G5 thuộc Sprint 4."
    )


def _gate_show(ctx: AppContext, args: argparse.Namespace) -> int:
    cho_duyet = ctx.gates.pending(args.gate)
    if cho_duyet:
        for yeu_cau in cho_duyet:
            _in_tieu_de(f"Đang chờ quyết định — {yeu_cau.payload.gate_id}")
            print(yeu_cau.payload.render())
        return EXIT_WAITING_GATE

    if args.gate:
        payload = _ho_so_gate(ctx, args.gate)
        _in_tieu_de(f"Hồ sơ dựng từ dữ liệu hiện hành — {args.gate}")
        print(payload.render())
        return EXIT_WAITING_GATE

    state = ctx.store.load()
    _in_tieu_de("Trạng thái các Human Gate")
    for gate in GATE_ORDER:
        print("  " + _nhan_gate(state, gate))
    print("\nKhông có hồ sơ nào đang chờ quyết định.")
    return EXIT_OK


def _gate_approve(ctx: AppContext, args: argparse.Namespace) -> int:
    from eaa.gates import GateNotPending
    from eaa.vcs import MERGE_GATE

    nguoi = args.actor or _nguoi_dung()

    try:
        quyet_dinh = ctx.gates.approve(
            args.gate, actor=nguoi, expect_digest=args.expect
        )
    except GateNotPending:
        payload = _ho_so_gate(ctx, args.gate)
        print(payload.render())
        ctx.gates.request(payload)
        quyet_dinh = ctx.gates.approve(
            args.gate, actor=nguoi, expect_digest=args.expect
        )

    print(f"\n{args.gate} đã được {nguoi} phê duyệt lúc {quyet_dinh.decided_at}.")

    if args.gate == MERGE_GATE:
        return _sau_khi_duyet_G3(ctx, quyet_dinh)

    return _thu_chuyen_pha(ctx)


def _sau_khi_duyet_G3(ctx: AppContext, quyet_dinh: Any) -> int:
    """Bước 11–13 — chạy ngay sau khi con người mở cổng."""
    module_id = quyet_dinh.module or ctx.store.load().current_module
    if not module_id:
        raise CliError("Không rõ quyết định này thuộc module nào.")

    bang_chung = ctx.orchestrator.load_evidence(module_id)
    if not bang_chung:
        raise CliError(
            f"Không tìm thấy bằng chứng kiểm chứng cho {module_id!r}. Chạy lại "
            "'eaa gen' để sinh và kiểm chứng trước khi merge — merge không bao "
            "giờ xảy ra mà không có báo cáo cổng."
        )

    ket_qua = ctx.orchestrator.finalize_module(module_id, bang_chung)
    print()
    print(ket_qua.message)
    return ket_qua.exit_code


def _thu_chuyen_pha(ctx: AppContext) -> int:
    """Duyệt gate xong thì cung chuyển pha tương ứng mở ra — đi tiếp cho gọn.

    Đây không phải máy tự vượt gate: nó chỉ thi hành hệ quả của quyết định mà
    con người vừa đưa ra, và vẫn đi qua ``policy.check_transition``.
    """
    from eaa.policy import PolicyViolation

    # Đi hết những bước mà gate đã mở, không chỉ một bước. Cung B→C không có
    # gate, nên duyệt G1 xong mà chỉ tiến một bước sẽ dừng lại giữa chừng ở B
    # và người dùng phải gõ thêm một lệnh chẳng để làm gì.
    da_chuyen = False
    while True:
        state = ctx.store.load()
        chi_so = PHASE_ORDER.index(state.phase)
        dich = PHASE_ORDER[chi_so + 1] if chi_so + 1 < len(PHASE_ORDER) else None
        if dich is None:
            break
        try:
            ctx.orchestrator.advance_phase(dich)
        except PolicyViolation:
            break
        print(f"Dự án chuyển sang pha {dich} — {PHASE_NAMES[dich]}.")
        da_chuyen = True

    state = ctx.store.load()
    thong_diep, ma_thoat = _buoc_ke_tiep(state)
    print(f"Bước kế tiếp: {thong_diep}")
    return ma_thoat if not da_chuyen else EXIT_OK


def _gate_reject(ctx: AppContext, args: argparse.Namespace) -> int:
    from eaa.gates import GateNotPending

    if not (args.reason or "").strip():
        raise CliError(
            "Từ chối tại gate bắt buộc kèm --reason. Lý do là thứ vòng sinh lại "
            "học được; thiếu nó thì lần sau AI nộp lại đúng cái vừa bị từ chối."
        )

    nguoi = args.actor or _nguoi_dung()
    try:
        quyet_dinh = ctx.gates.reject(args.gate, actor=nguoi, reason=args.reason)
    except GateNotPending as exc:
        raise CliError(str(exc)) from exc

    print(f"{args.gate} bị {nguoi} từ chối: {quyet_dinh.reason}")
    print("Lý do đã ghi vào Error Ledger và sẽ có mặt trong prompt lần sinh lại.")

    if quyet_dinh.module:
        ket_qua = ctx.orchestrator.finalize_module(
            quyet_dinh.module, ctx.orchestrator.load_evidence(quyet_dinh.module)
        )
        print()
        print(ket_qua.message)
        return ket_qua.exit_code
    return EXIT_WAITING_GATE


# --------------------------------------------------------------------------
# UC03 — nạp và duyệt trích đoạn tài liệu (Gate G2)
# --------------------------------------------------------------------------


def cmd_datasheet(args: argparse.Namespace) -> int:
    from eaa.ingest import IngestError, PdfIngestor, SourceRegistry
    from eaa.kb import DatasheetStore

    project = resolve_project(args.project)

    if args.datasheet_action == "list":
        kho = DatasheetStore(project / "datasheets")
        muc = kho.all()
        _in_tieu_de(f"Datasheet Store ({len(muc)} chunk)")
        for c in sorted(muc, key=lambda x: x.id):
            danh_dau = "✓" if c.is_active else ("…" if c.status == "proposed" else "✗")
            print(f"  {danh_dau} {c.id:<24}{c.status:<12}{c.device}/{c.peripheral}")
            if c.registers:
                print(f"      thanh ghi: {', '.join(c.registers)}")
            if c.source:
                print(f"      nguồn: {c.source}")
        cho_duyet = [c for c in muc if c.status == "proposed"]
        if cho_duyet:
            print(
                f"\n{len(cho_duyet)} chunk đang chờ duyệt tại G2 — chưa truy xuất "
                "được. Xem 'eaa gate show G2' rồi 'eaa gate approve G2'."
            )
        return EXIT_WAITING_GATE if cho_duyet else EXIT_OK

    if args.datasheet_action == "add":
        try:
            de_xuat = PdfIngestor(
                datasheets_dir=project / "datasheets",
                registry=SourceRegistry(project / "sources.jsonl"),
            ).ingest(
                args.file,
                device=args.device,
                peripheral=args.peripheral,
                pages=args.pages or "",
                topic=args.topic or "",
                chunk_id=args.id or "",
            )
        except IngestError as exc:
            raise CliError(str(exc)) from exc

        _in_tieu_de(f"Đã tạo chunk ĐỀ XUẤT {de_xuat.id}")
        print(f"  Nguồn      : {de_xuat.source}")
        print(f"  Băm tài liệu: {de_xuat.source_hash}")
        print(f"  Thanh ghi đoán được: {', '.join(de_xuat.registers) or '—'}")
        print(
            "\nChunk đang ở trạng thái 'proposed' nên CHƯA truy xuất được vào "
            "prompt nào.\nKỹ sư đối chiếu từng bit với bản gốc, sửa lại phần chưa "
            "chưng cất, rồi duyệt:\n  eaa gate show G2\n  eaa gate approve G2"
        )
        return EXIT_WAITING_GATE

    raise CliError(f"Hành động không hợp lệ: {args.datasheet_action!r}")


# --------------------------------------------------------------------------
# UC06 — mô phỏng
# --------------------------------------------------------------------------


def cmd_sim(args: argparse.Namespace) -> int:
    from eaa.tools.sim import SimBindings, SimGate

    project = resolve_project(args.project)
    ctx = build_context(project)
    cong = SimGate(
        runner=ctx.runner,
        bindings=SimBindings.from_project(project, scenario=args.scenario or ""),
    )

    if args.sweep:
        dai = _doc_dai_quet(args.sweep, project)
        _in_tieu_de("Quét tham số (MIL)")
        bang = cong.sweep(dai, scenario=args.scenario or "")
        print(SimGate.format_sweep(bang))
        return EXIT_OK if any(r["stable"] for r in bang) else EXIT_ENV_ERROR

    bao_cao = cong.run()
    _in_tieu_de("Mô phỏng")
    print(bao_cao.raw_output.strip() or "(không có đầu ra)")
    print()
    print(bao_cao.summary)
    for e in bao_cao.errors:
        print(f"  {e}")
    return EXIT_OK if bao_cao.passed else EXIT_ENV_ERROR


def _doc_dai_quet(mo_ta: str, project: Path) -> dict[str, list[float]]:
    """Đọc dải quét: ``kp,ki,kd`` lấy dải từ scenarios.yaml, hoặc ``kp=1:2:3``."""
    import yaml as _yaml

    if "=" in mo_ta:
        dai: dict[str, list[float]] = {}
        for phan in mo_ta.split(","):
            if "=" not in phan:
                continue
            ten, gia_tri = phan.split("=", 1)
            dai[ten.strip()] = [float(v) for v in gia_tri.split(":") if v.strip()]
        return dai

    kich_ban = project / "sim" / "scenarios.yaml"
    if not kich_ban.is_file():
        raise CliError(f"Không có {kich_ban} để lấy dải quét mặc định.")
    cau_hinh = _yaml.safe_load(kich_ban.read_text(encoding="utf-8")) or {}
    khai_bao = cau_hinh.get("sweep") or {}
    ten_can = [t.strip() for t in mo_ta.split(",") if t.strip()]
    thieu = [t for t in ten_can if t not in khai_bao]
    if thieu:
        raise CliError(
            f"scenarios.yaml không khai báo dải quét cho {thieu}. "
            f"Đang có: {sorted(k for k in khai_bao if k != 'scenario')}"
        )
    return {t: [float(v) for v in khai_bao[t]] for t in ten_can}


# --------------------------------------------------------------------------
# AIS §9 — môi trường công cụ
# --------------------------------------------------------------------------


def _tao_doctor(project: Path) -> Any:
    from eaa.doctor import Doctor, EnvLock, ToolManifest

    rang_buoc = _nap_kho(Constraints.load, project / CONSTRAINTS_FILE)
    goc = repo_root()
    manifest = ToolManifest.load(
        goc / "tools.yaml",
        goc / "packs" / rang_buoc.platform / "tools.yaml",
        pack=rang_buoc.platform,
    )
    return Doctor(
        manifest=manifest,
        tools_kb=project / "tools_kb",
        env_lock=EnvLock(project / "env_lock.json"),
        confirm=_hoi_xac_nhan_cai,
    )


def _hoi_xac_nhan_cai(ten: str, lenh: str) -> bool:
    """Hỏi người trước mỗi lệnh cài. Không có terminal thì KHÔNG đồng ý.

    Cùng nguyên tắc với Human Gate: một phiên không có người không được diễn
    giải thành một người đã đồng ý (FR-ENV-02, §9.4).
    """
    if not sys.stdin.isatty():
        return False
    print(f"\n  Sắp chạy để cài {ten}:\n    {lenh}")
    return input("  Đồng ý chạy lệnh này? [y/N]: ").strip().lower() in ("y", "yes", "c", "có")


def cmd_doctor(args: argparse.Namespace) -> int:
    from eaa.doctor import DoctorError, InstallNotConfirmed, ToolStatus

    project = resolve_project(args.project)
    doctor = _tao_doctor(project)

    bao_cao = doctor.scan()
    _in_tieu_de("Môi trường công cụ")
    print(doctor.render_scan(bao_cao))

    # Trôi phiên bản so với bản khóa — FR-ENV-04.
    lech = doctor.check_drift(bao_cao)
    if lech:
        _in_tieu_de("Cảnh báo trôi môi trường")
        for ten, (cu, moi) in sorted(lech.items()):
            print(f"  {ten}: khóa ghi {cu}, hiện tại {moi}")
        print(
            "\nToolchain trôi phiên bản phá hỏng so sánh A/B y như mô hình trôi "
            "phiên bản.\nChấp nhận và cập nhật khóa: eaa doctor --accept-drift"
        )

    if args.accept_drift:
        khoa = doctor.lock(bao_cao)
        print(f"\nĐã cập nhật env_lock.json — env_hash mới: {khoa['env_hash']}")
        _ghi_env_hash_vao_state(project, khoa["env_hash"])
        return EXIT_OK

    chan = [r for r in bao_cao if r.blocking]

    if args.fix:
        _in_tieu_de("Chuẩn bị công cụ")
        if not chan:
            print("  Không có gì phải cài.")
        else:
            try:
                for dong in doctor.fix(bao_cao):
                    print(f"  {dong}")
            except InstallNotConfirmed as exc:
                raise CliError(str(exc), EXIT_WAITING_GATE) from exc
            except DoctorError as exc:
                raise CliError(str(exc)) from exc
        bao_cao = doctor.scan()
        chan = [r for r in bao_cao if r.blocking]

    if not chan:
        khoa = doctor.lock(bao_cao)
        print(f"\nenv_hash: {khoa['env_hash']}")
        _ghi_env_hash_vao_state(project, khoa["env_hash"])
        # Ghi Thẻ công cụ cho những công cụ đã sẵn sàng (AIS §9.5).
        da_ghi = []
        for r in bao_cao:
            if r.status == ToolStatus.OK:
                try:
                    da_ghi.append(doctor.write_tool_card(r).name)
                except DoctorError:
                    pass
        if da_ghi:
            print(f"Thẻ công cụ đã cập nhật: {', '.join(da_ghi)}")
        return EXIT_OK

    return EXIT_ENV_ERROR


def _ghi_env_hash_vao_state(project: Path, env_hash: str) -> None:
    """Gắn env_hash vào Project State để mọi dòng chỉ số mang theo nó."""
    store = StateStore(project / STATE_FILE)
    if not store.exists():
        return
    with store.with_lock():
        state = store.load()
        if state.env_hash != env_hash:
            state.env_hash = env_hash
            store.save(state)


# --------------------------------------------------------------------------
# AIS §8.5 — kho phẩm xuất
# --------------------------------------------------------------------------


def cmd_docs(args: argparse.Namespace) -> int:
    from eaa.registry import (
        ArtifactNotFound,
        ArtifactRegistry,
        RegistryError,
        RequestKind,
        interpret_request,
    )

    project = resolve_project(args.project)
    kho = ArtifactRegistry(project / "deliverables")

    if args.docs_action == "list":
        _in_tieu_de("Kho phẩm xuất")
        print(kho.render_list(kho.find(kind=args.type) if args.type else None))
        return EXIT_OK

    try:
        if args.docs_action == "get":
            return _docs_get(kho, args)
        if args.docs_action == "regen":
            return _docs_regen(kho, project, args)
    except (ArtifactNotFound, RegistryError) as exc:
        raise CliError(str(exc)) from exc

    raise CliError(f"Hành động không hợp lệ: {args.docs_action!r}")


def _docs_get(kho: Any, args: argparse.Namespace) -> int:
    """UC "gửi lại" — trả ĐÚNG bản đã phát hành (AIS §8.5, TC-32)."""
    from eaa.registry import RequestKind, interpret_request

    # Nếu người dùng gõ cả một câu, kiểm xem ý họ có rõ không (FR-DOC-02).
    if " " in args.what:
        y_dinh = interpret_request(args.what)
        if y_dinh == RequestKind.REGEN:
            raise CliError(
                "Cách nói của bạn nghiêng về LÀM MỚI (tái sinh từ dữ liệu hiện "
                "hành), nhưng 'docs get' là GỬI LẠI bản đã phát hành. "
                "Dùng 'eaa docs regen' nếu muốn bản mới."
            )
        if y_dinh == RequestKind.AMBIGUOUS:
            raise CliError(
                "Chưa rõ bạn muốn GỬI LẠI bản đã phát hành hay LÀM MỚI từ dữ liệu "
                "hiện hành — hai thứ này khác số liệu.\n"
                "  Gửi lại : eaa docs get <id>\n"
                "  Làm mới : eaa docs regen <family>\n"
                "Hỏi lại thay vì đoán, để không ai cầm bản làm mới mà tưởng là "
                "bản đã nộp (FR-DOC-02).",
                EXIT_WAITING_GATE,
            )

    ung_vien = [a for a in kho.all() if a.id == args.what] or kho.find(
        args.what, kind=args.type or None, on_date=args.date or ""
    )
    if not ung_vien:
        raise CliError(f"Không tìm thấy phẩm xuất khớp {args.what!r}.")
    if len(ung_vien) > 1 and not args.what.count("@v"):
        _in_tieu_de(f"Có {len(ung_vien)} bản khớp — chọn một mã cụ thể")
        print(kho.render_list(ung_vien))
        return EXIT_WAITING_GATE

    duong_dan = kho.resend(ung_vien[0].id, fmt=args.format or "")
    print(f"{ung_vien[0].id} → {duong_dan}")
    print(f"  băm bản phát hành: {ung_vien[0].content_hash}")
    return EXIT_OK


def _docs_regen(kho: Any, project: Path, args: argparse.Namespace) -> int:
    """UC "làm mới" — tái sinh từ dữ liệu hiện hành (AIS §8.5, TC-33)."""
    from eaa.kpi import KpiLogger

    if args.family != "bao_cao_kpi":
        raise CliError(
            f"Chưa biết cách tái sinh {args.family!r}. Hiện chỉ có 'bao_cao_kpi'; "
            "tài liệu là hàm của dữ liệu, nên mỗi loại cần một hàm sinh riêng."
        )

    kpi = KpiLogger(project / "kpi_log.csv")
    if not kpi.rows():
        raise CliError(f"Chưa có số liệu nào trong {kpi.path}.")

    def sinh() -> tuple[str, dict[str, Any]]:
        noi_dung = kpi.path.read_text(encoding="utf-8")
        state = StateStore(project / STATE_FILE)
        lineage: dict[str, Any] = {"rows": len(kpi.rows())}
        if state.exists():
            s = state.load()
            lineage.update(
                constraints_version=s.constraints_version, env_hash=s.env_hash
            )
        return noi_dung, lineage

    moi = kho.regen(
        args.family, sinh, kind="csv", title="Báo cáo chỉ số dự án"
    )
    print(f"Đã tái sinh {moi.id} (phiên bản {moi.version}) từ dữ liệu hiện hành.")
    if moi.supersedes:
        print(
            f"  Thay thế {moi.supersedes} — bản cũ vẫn tra được nguyên vẹn bằng "
            f"'eaa docs get {moi.supersedes}'."
        )
    return EXIT_OK


# --------------------------------------------------------------------------
# UC08, UC09 — nhật ký lỗi và báo cáo KPI
# --------------------------------------------------------------------------


def cmd_ledger(args: argparse.Namespace) -> int:
    from eaa.ledger import CATEGORIES, ErrorLedger, LedgerError

    project = resolve_project(args.project)
    so = ErrorLedger(project / "error_ledger.jsonl")

    if args.ledger_action == "list":
        muc = so.entries(include_resolved=not args.open_only)
        _in_tieu_de(f"Error Ledger ({len(muc)} mục)")
        for e in muc:
            print(f"  {e.id} [{e.status}] {e.module} · {e.category}")
            print(f"      {e.as_rule}")
        return EXIT_OK

    if args.ledger_action == "add":
        try:
            e = so.add(
                module=args.module,
                category=args.category,
                description=args.description,
                evidence=args.evidence or "",
                peripheral=args.peripheral or "",
                registers=[r.strip() for r in (args.registers or "").split(",") if r.strip()],
                rule=args.rule or "",
            )
        except LedgerError as exc:
            raise CliError(str(exc)) from exc
        print(f"Đã ghi {e.id}: {e.as_rule}")
        return EXIT_OK

    raise CliError(f"Hành động không hợp lệ: {args.ledger_action!r}")


def cmd_report(args: argparse.Namespace) -> int:
    from eaa.kpi import KpiLogger

    project = resolve_project(args.project)

    if args.report_kind != "kpi":
        raise CliError(
            f"Báo cáo {args.report_kind!r} chưa có. 'eaa report versions' thuộc Sprint 4."
        )

    kpi = KpiLogger(project / "kpi_log.csv")
    dong = kpi.rows()
    if not dong:
        raise CliError(f"Chưa có số liệu KPI nào trong {kpi.path}.")

    if args.csv:
        dich = kpi.export(args.csv, module=args.module)
        print(f"Đã xuất {len(dong)} dòng ra {dich}")
        return EXIT_OK

    tom_tat = kpi.summary(args.module)
    _in_tieu_de("Tổng hợp KPI")
    for khoa, gia_tri in tom_tat.items():
        print(f"  {khoa:<20} {gia_tri}")

    _in_tieu_de("Số liệu theo module")
    print(f"  {'module':<24}{'merge':<8}{'vá':<6}{'tokens vào':<12}{'tokens ra':<12}")
    for module in tom_tat.get("modules", []):
        m = kpi.summary(module)
        print(
            f"  {module:<24}{m['merges']:<8}{m['repairs']:<6}"
            f"{m['tokens_in_total']:<12}{m['tokens_out_total']:<12}"
        )
    return EXIT_OK


# --------------------------------------------------------------------------
# Bộ phân tích tham số
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eaa",
        description=(
            "Embedded AIDD Agent — agent lập trình nhúng tổng quát. "
            "Con người giữ mọi quyết định kiến trúc và an toàn qua 5 Human Gate."
        ),
    )
    parser.add_argument("--version", action="version", version=f"eaa {__version__}")
    parser.add_argument(
        "--project",
        help="Thư mục dự án (mặc định: EAA_PROJECT, hoặc dự án duy nhất trong projects/)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<lệnh>")

    p_init = sub.add_parser("init", help="Khởi tạo dự án và Project State (UC01)")
    p_init.add_argument("--force", action="store_true", help="Khởi tạo lại dù đã có state")
    p_init.add_argument("--provider", default="mock", help="Nhà cung cấp LLM (mặc định: mock)")
    p_init.add_argument(
        "--model",
        default="mock-deterministic-1",
        help="Mã mô hình, ghim phiên bản đầy đủ (Sprint 1–3 dùng MockLLM)",
    )
    p_init.set_defaults(func=cmd_init)

    p_resume = sub.add_parser("resume", help="Khôi phục phiên từ Project State (UC10)")
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser("status", help="Xem trạng thái dự án (chỉ đọc)")
    p_status.set_defaults(func=cmd_status)

    p_policy = sub.add_parser("policy", help="In bảng phân quyền và máy trạng thái")
    p_policy.set_defaults(func=cmd_policy)

    p_packs = sub.add_parser("packs", help="Liệt kê Platform Pack đã cài")
    p_packs.set_defaults(func=cmd_packs)

    # UC02 — backlog
    p_plan = sub.add_parser("plan", help="Quản lý backlog module (UC02)")
    plan_sub = p_plan.add_subparsers(dest="plan_action", required=True, metavar="<hành động>")
    pa = plan_sub.add_parser(
        "add",
        help="Thêm module; kiểm xung đột tài nguyên ngay lúc khai báo (quy trình P2)",
    )
    pa.add_argument("module_id")
    pa.add_argument("--uses", help="Tài nguyên module chiếm dụng, phân cách bằng dấu phẩy")
    pa.add_argument("--depends-on", dest="depends_on", help="Module phụ thuộc")
    plan_sub.add_parser("list", help="Liệt kê backlog")
    po = plan_sub.add_parser("order", help="Đặt lại thứ tự ưu tiên")
    po.add_argument("order", help="Danh sách module theo thứ tự, phân cách bằng dấu phẩy")
    p_plan.set_defaults(func=cmd_plan)

    # UC04 — vòng lặp sinh mã
    p_gen = sub.add_parser("gen", help="Chạy vòng lặp sinh mã chuẩn cho module (UC04)")
    p_gen.add_argument("module_id")
    p_gen.set_defaults(func=cmd_gen)

    # UC05 — Human Gate
    p_gate = sub.add_parser(
        "gate",
        help="Xem hồ sơ và quyết định tại Human Gate (UC05)",
        description=(
            "Gate chỉ được mở bởi con người. Không có cờ nào tự duyệt, và phiên "
            "không có terminal cũng không được mặc định đồng ý (FR-GATE-01)."
        ),
    )
    gate_sub = p_gate.add_subparsers(dest="gate_action", required=True, metavar="<hành động>")
    gs = gate_sub.add_parser("show", help="Xem hồ sơ đang chờ quyết định")
    gs.add_argument("gate", nargs="?", choices=list(GATE_ORDER))
    ga = gate_sub.add_parser("approve", help="Phê duyệt — hành động của con người")
    ga.add_argument("gate", choices=list(GATE_ORDER))
    ga.add_argument("--actor", help="Người quyết định (mặc định: người dùng hệ thống)")
    ga.add_argument(
        "--expect",
        help="Băm nội dung bạn đã xem; lệch băm thì từ chối duyệt bản đã đổi",
    )
    gr = gate_sub.add_parser("reject", help="Từ chối, bắt buộc kèm lý do")
    gr.add_argument("gate", choices=list(GATE_ORDER))
    gr.add_argument("--reason", required=True, help="Lý do từ chối — đi vào Error Ledger")
    gr.add_argument("--actor", help="Người quyết định")
    p_gate.set_defaults(func=cmd_gate)

    # UC08 — Error Ledger
    p_ledger = sub.add_parser("ledger", help="Nhật ký lỗi ảo giác (UC08)")
    ledger_sub = p_ledger.add_subparsers(
        dest="ledger_action", required=True, metavar="<hành động>"
    )
    la = ledger_sub.add_parser("add", help="Ghi một lỗi mới")
    la.add_argument("--module", required=True)
    la.add_argument("--category", required=True)
    la.add_argument("--description", required=True)
    la.add_argument("--evidence")
    la.add_argument("--peripheral")
    la.add_argument("--registers", help="Thanh ghi liên quan, phân cách bằng dấu phẩy")
    la.add_argument("--rule", help="Quy tắc một dòng để nạp vào prompt (K5)")
    ll = ledger_sub.add_parser("list", help="Liệt kê các mục lỗi")
    ll.add_argument("--open-only", action="store_true", help="Chỉ hiện lỗi chưa khép")
    p_ledger.set_defaults(func=cmd_ledger)

    # UC09 — báo cáo
    p_report = sub.add_parser("report", help="Xuất báo cáo KPI (UC09)")
    p_report.add_argument("report_kind", choices=["kpi", "versions"], nargs="?", default="kpi")
    p_report.add_argument("--csv", help="Xuất ra tệp CSV")
    p_report.add_argument("--module", help="Lọc theo module")
    p_report.set_defaults(func=cmd_report)

    # Các lệnh còn lại của SDD §5 và AIS: có mặt trong trợ giúp để bộ lệnh nhìn
    # thấy được ngay từ đầu, nhưng nói thẳng là chưa làm.
    # UC03 — nạp và duyệt trích đoạn tài liệu
    p_ds = sub.add_parser("datasheet", help="Nạp và duyệt trích đoạn tài liệu (UC03, G2)")
    ds_sub = p_ds.add_subparsers(dest="datasheet_action", required=True, metavar="<hành động>")
    da = ds_sub.add_parser(
        "add", help="Nạp trích đoạn PDF thành chunk ĐỀ XUẤT, chờ duyệt tại G2"
    )
    da.add_argument("file", help="Tệp PDF nguồn")
    da.add_argument("--device", required=True, help="Thiết bị, ví dụ tên chip hay mã linh kiện")
    da.add_argument("--peripheral", required=True, help="Ngoại vi trong hồ sơ phần cứng")
    da.add_argument(
        "--pages",
        help="Trang cần trích, ví dụ '222-224'. Bỏ trống là lấy cả tài liệu — "
        "nên chỉ rõ, vì việc chọn trang là việc của kỹ sư (AIS §4.1)",
    )
    da.add_argument("--topic", help="Chủ đề ngắn gọn của trích đoạn")
    da.add_argument("--id", help="Mã chunk; bỏ trống thì tự sinh")
    ds_sub.add_parser("list", help="Liệt kê chunk trong kho kèm trạng thái")
    p_ds.set_defaults(func=cmd_datasheet)

    # UC06 — mô phỏng
    p_sim = sub.add_parser("sim", help="Chạy mô phỏng MIL/SIL, quét tham số (UC06)")
    sim_sub = p_sim.add_subparsers(dest="sim_action", required=True, metavar="<hành động>")
    sr = sim_sub.add_parser("run", help="Chạy kịch bản mô phỏng")
    sr.add_argument("--scenario", help="Tên kịch bản; bỏ trống thì chạy tất cả")
    sr.add_argument(
        "--sweep",
        help="Quét tham số: 'kp,ki,kd' lấy dải từ scenarios.yaml, "
        "hoặc 'kp=30:38:46,kd=2.6:3.4'",
    )
    p_sim.set_defaults(func=cmd_sim)

    # AIS §9 — môi trường công cụ
    p_doctor = sub.add_parser(
        "doctor",
        help="Quét, chuẩn bị công cụ và khóa môi trường (AIS §9)",
        description=(
            "Chế độ quét chỉ ĐỌC, không đổi gì trên máy. --fix sinh lệnh cài và "
            "LUÔN hỏi trước từng lệnh; phiên không có terminal thì không cài."
        ),
    )
    p_doctor.add_argument(
        "--fix", action="store_true", help="Sinh lệnh cài cho công cụ thiếu, hỏi từng lệnh"
    )
    p_doctor.add_argument(
        "--accept-drift",
        action="store_true",
        dest="accept_drift",
        help="Chấp nhận môi trường hiện tại và cập nhật env_lock.json",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    # AIS §8.5 — kho phẩm xuất
    p_docs = sub.add_parser("docs", help="Kho phẩm xuất: list/get/regen (AIS §8.5)")
    docs_sub = p_docs.add_subparsers(dest="docs_action", required=True, metavar="<hành động>")
    dl = docs_sub.add_parser("list", help="Liệt kê phẩm xuất kèm trạng thái và dòng dõi")
    dl.add_argument("--type", choices=["docx", "pdf", "code", "image", "csv", "md", "html"])
    dg = docs_sub.add_parser(
        "get", help="GỬI LẠI đúng bản đã phát hành, bất biến, khớp băm"
    )
    dg.add_argument("what", help="Mã phẩm xuất, hoặc mô tả để tìm")
    dg.add_argument("--format", help="Chuyển đổi TỪ CHÍNH BẢN ẤY sang định dạng khác")
    dg.add_argument("--type", help="Lọc theo loại khi tìm bằng mô tả")
    dg.add_argument("--date", help="Lọc theo ngày phát hành, dạng YYYY-MM-DD")
    dr = docs_sub.add_parser(
        "regen", help="LÀM MỚI: tái sinh từ dữ liệu hiện hành thành phiên bản mới"
    )
    dr.add_argument("family", help="Họ phẩm xuất, ví dụ bao_cao_kpi")
    p_docs.set_defaults(func=cmd_docs)

    khung: list[tuple[str, str, str, str]] = [
        ("tune", "Nhập số đo vật lý, nhận gợi ý tinh chỉnh (UC07, G4)", "Sprint 4", ""),
        ("rollback", "Đưa module về bản known-good gần nhất (AIS §8.4)", "Sprint 4", ""),
    ]
    for ten, tro_giup, sprint, ghi_chu in khung:
        p = sub.add_parser(ten, help=f"[{sprint}] {tro_giup}")
        p.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        p.set_defaults(func=_chua_hien_thuc(ten, sprint, ghi_chu))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_env_file()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_OK

    # Lỗi miền được đổi thành thông điệp + mã thoát, không phải traceback.
    # Người dùng của công cụ này là kỹ sư đang giữa một quy trình có gate; một
    # vết ngăn xếp Python không nói cho họ biết phải làm gì tiếp.
    from eaa.gates import GateError, GateNotInteractive, GateNotPending
    from eaa.kb import KbError
    from eaa.kpi import KpiError
    from eaa.ledger import LedgerError
    from eaa.platform import PackError
    from eaa.tools.runner import ConfirmationRequired, ToolExecutionError
    from eaa.vcs import GitError, MergeNotAuthorized

    #: Lỗi nghĩa là "đang chờ người", khác với "hỏng" — mã thoát 2.
    CHO_NGUOI = (GateNotInteractive, GateNotPending, ConfirmationRequired)

    try:
        return args.func(args)
    except CliError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return exc.exit_code
    except CHO_NGUOI as exc:
        print(f"Cần người quyết định: {exc}", file=sys.stderr)
        return EXIT_WAITING_GATE
    except PolicyViolation as exc:
        print(f"Bị luật điều phối từ chối: {exc}", file=sys.stderr)
        return EXIT_ENV_ERROR
    except MergeNotAuthorized as exc:
        print(f"Không được phép merge: {exc}", file=sys.stderr)
        return EXIT_ENV_ERROR
    except (
        GateError,
        KbError,
        KpiError,
        LedgerError,
        PackError,
        GitError,
        ToolExecutionError,
    ) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return EXIT_ENV_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
