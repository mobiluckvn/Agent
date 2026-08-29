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

Ghi chú sai lệch có chủ đích so với EAA-SDD-03 §2: hàm đọc ``constraints.yaml``
và ``hardware_profile.yaml`` tạm đặt ở đây vì Sprint 0 cần chúng cho ``init``
trong khi bộ nạp 5 kho tri thức mới thuộc Sprint 1 (MDD §6). Khi S1 dựng bộ
nạp, phần này chuyển sang đó và ``cli.py`` chỉ còn gọi.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

from eaa import (
    EXIT_ENV_ERROR,
    EXIT_OK,
    EXIT_WAITING_GATE,
    __version__,
)
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
from eaa.state import ProjectState, StateCorruptError, StateStore

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


def _load_yaml(path: Path, nhan: str) -> dict[str, Any]:
    if not path.is_file():
        raise CliError(f"Thiếu {nhan}: {path}")
    try:
        du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CliError(f"{path}: YAML không hợp lệ — {exc}") from exc
    if not isinstance(du_lieu, dict):
        raise CliError(f"{path}: nội dung phải là ánh xạ khóa–giá trị")
    return du_lieu


def constraints_version(path: Path) -> str:
    """Băm nội dung ràng buộc — đi vào state và mọi commit message (NFR-07).

    Băm chính BYTE của tệp chứ không băm cấu trúc đã phân tích: mục tiêu là trả
    lời được "mã này sinh ra dưới đúng văn bản ràng buộc nào", kể cả khi thay
    đổi chỉ là một dòng chú thích làm người đọc hiểu khác đi.
    """
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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

    duong_dan_rang_buoc = project / CONSTRAINTS_FILE
    rang_buoc = _load_yaml(duong_dan_rang_buoc, "constraints.yaml (công đoạn A1)")
    ho_so = _load_yaml(
        project / HARDWARE_PROFILE_FILE, "hardware_profile.yaml (công đoạn B2)"
    )

    ten_pack = rang_buoc.get("platform")
    if not ten_pack:
        raise CliError(
            f"{duong_dan_rang_buoc}: thiếu trường 'platform' — dự án phải chỉ rõ "
            "dùng Platform Pack nào."
        )

    try:
        manifest = load_manifest(repo_root() / "packs" / str(ten_pack))
    except PackError as exc:
        raise CliError(str(exc)) from exc

    state = ProjectState(
        phase="A",
        gates={gate: "pending" for gate in GATE_ORDER},
        backlog=[],
        constraints_version=constraints_version(duong_dan_rang_buoc),
        llm={"provider": args.provider, "model": args.model},
    )
    store.save(state)

    _in_tieu_de("Đã khởi tạo dự án")
    print(f"  Thư mục       : {project}")
    print(f"  Project State : {store.path}")
    print(f"  Platform Pack : {manifest.name} v{manifest.version}")
    print(f"  Ràng buộc     : {state.constraints_version}")
    print(f"  Hồ sơ phần cứng: {len(ho_so.get('peripherals', []))} ngoại vi, "
          f"{len(ho_so.get('components', []))} linh kiện, "
          f"{len(ho_so.get('pin_map', {}))} chân")
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
            + "Sprint 0 giao: init, resume, status, policy, packs.",
        )

    return handler


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

    # Khung các lệnh còn lại của SDD §5 và AIS: có mặt trong trợ giúp để bộ
    # lệnh nhìn thấy được ngay từ đầu, nhưng nói thẳng là chưa làm.
    khung: list[tuple[str, str, str, str]] = [
        ("plan", "Quản lý backlog module (UC02)", "Sprint 1", ""),
        ("datasheet", "Nạp và duyệt trích đoạn tài liệu (UC03, G2)", "Sprint 1", ""),
        ("gen", "Chạy vòng lặp sinh mã chuẩn cho module (UC04)", "Sprint 2", ""),
        (
            "gate",
            "Xem diff và phê duyệt tại gate hiện hành (UC05)",
            "Sprint 2",
            "Gate chỉ được duyệt bởi con người — không có cờ nào tự duyệt.",
        ),
        ("sim", "Chạy mô phỏng MIL/SIL, quét tham số (UC06)", "Sprint 3", ""),
        ("tune", "Nhập số đo vật lý, nhận gợi ý tinh chỉnh (UC07, G4)", "Sprint 4", ""),
        ("ledger", "Ghi nhận lỗi ảo giác mới (UC08)", "Sprint 1", ""),
        ("report", "Xuất báo cáo KPI và bảng phiên bản (UC09)", "Sprint 2", ""),
        ("doctor", "Quét, cài đặt công cụ và khóa môi trường (AIS §9)", "Sprint 3", ""),
        ("docs", "Kho phẩm xuất: list/get/regen (AIS §8.5)", "Sprint 3", ""),
        ("rollback", "Đưa module về bản known-good gần nhất (AIS §8.4)", "Sprint 4", ""),
    ]
    for ten, tro_giup, sprint, ghi_chu in khung:
        p = sub.add_parser(ten, help=f"[{sprint}] {tro_giup}")
        p.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        p.set_defaults(func=_chua_hien_thuc(ten, sprint, ghi_chu))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_OK

    try:
        return args.func(args)
    except CliError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return exc.exit_code
    except PolicyViolation as exc:
        print(f"Bị luật điều phối từ chối: {exc}", file=sys.stderr)
        return EXIT_ENV_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
