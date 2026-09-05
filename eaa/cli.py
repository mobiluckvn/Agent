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
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from eaa import (
    EXIT_ENV_ERROR,
    EXIT_OK,
    EXIT_REPAIR_LIMIT,
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


#: Lệnh hỏng → lệnh giúp người dùng ĐI TIẾP. Xem `_goi_y_di_tiep`.
#:
#: Bảng nằm ở MỘT chỗ thay vì rải thành 182 chuỗi trong từng thông báo. Lý do
#: không phải gọn hơn: một gợi ý viết rải rác sẽ lệch với lệnh nó nói tới ngay
#: lần đầu ai đó đổi tên lệnh, và **không gì bắt được chỗ lệch ấy**. Ở đây thì
#: có — bài kiểm đối chiếu bảng này với cây argparse thật.
#:
#: Nguyên tắc chọn gợi ý: lệnh nào trả lời câu *"giờ tôi đứng ở đâu"* hoặc
#: *"cái tôi vừa gõ thiếu gì"* cho ĐÚNG việc vừa hỏng. Một gợi ý chung chung
#: dán vào mọi chỗ thì không phải gợi ý, nó là chữ độn.
GOI_Y_KHI_HONG: dict[str, tuple[str, ...]] = {
    # — dựng dự án và trạng thái —
    "init": ("eaa doctor", "eaa status"),
    "status": ("eaa focus",),
    "resume": ("eaa status", "eaa gate show"),
    "scratch": ("eaa status",),
    "focus": ("eaa status",),
    "brief": ("eaa ports", "eaa status"),
    "policy": ("eaa status",),
    "capabilities": ("eaa doctor",),
    "packs": ("eaa capabilities",),
    "survey": ("eaa capabilities",),
    "models": ("eaa models",),
    "environ": ("eaa doctor",),
    # — kế hoạch và module —
    "plan": ("eaa plan list", "eaa status"),
    "propose": ("eaa plan list",),
    "decide": ("eaa plan list",),
    "interface": ("eaa plan list",),
    "ledger": ("eaa ledger list",),
    "deviations": ("eaa deviations --draft",),
    # — tri thức —
    "datasheet": ("eaa datasheet list", "eaa sources need"),
    "sources": ("eaa sources need",),
    "errata": ("eaa errata show",),
    "resolve": ("eaa sources need", "eaa recall '<câu hỏi>'"),
    "recall": ("eaa datasheet list",),
    "research": ("eaa environ",),
    "read": ("eaa research '<câu hỏi>'",),
    "knowledge": ("eaa knowledge stale '<mã chunk>'", "eaa datasheet list"),
    "memory": ("eaa memory list",),
    "playbook": ("eaa playbook list",),
    # — sinh mã và cổng —
    "gen": ("eaa focus", "eaa status"),
    "gate": ("eaa gate show", "eaa status"),
    "build": ("eaa status", "eaa plan list"),
    "rollback": ("eaa report versions",),
    "sim": ("eaa status",),
    # — môi trường và công cụ —
    "doctor": ("eaa doctor --plan", "eaa environ"),
    "tool": ("eaa tool list", "eaa capabilities"),
    "skill": ("eaa skill list",),
    "assess": ("eaa environ",),
    # — phần cứng —
    "ports": ("eaa environ",),
    "flash": ("eaa ports", "eaa status"),
    "telemetry": ("eaa ports",),
    "diagnose": ("eaa diagnose list", "eaa ports"),
    "debug": ("eaa debug plan '<kịch bản>'",),
    "endurance": ("eaa diagnose list",),
    "scope-image": ("eaa diagnose list",),
    "tune": ("eaa report versions", "eaa status"),
    "measured": ("eaa measured list",),
    "observe": ("eaa observe",),
    "procedure": ("eaa procedure lint", "eaa gate show G2"),
    "problems": ("eaa status", "eaa gate show"),
    "safety": ("eaa safety show",),
    "budget": ("eaa budget show",),
    # — báo cáo và bàn giao —
    "report": ("eaa report kpi",),
    "docs": ("eaa docs list",),
    "design": ("eaa design list",),
    "handover": ("eaa handover doc",),
    "field": ("eaa diagnose list",),
    "suggest": ("eaa report review",),
    "chat": ("eaa status", "eaa capabilities"),
}


def _goi_y_di_tiep(ten_lenh: str, thong_diep: str) -> str:
    """Phần "làm tiếp" gắn vào cuối một thông báo lỗi.

    Trả RỖNG khi thông báo ĐÃ tự nêu một lệnh. Nói hai lần thì lần thứ hai làm
    loãng lần thứ nhất, và người đọc sẽ thôi đọc cả hai.

    Đây là chỗ sửa cho SL-178: đo được rằng chỉ 25/182 thông báo lỗi nêu được
    việc phải làm tiếp. Hai phần ba còn lại nói CÁI GÌ SAI mà không nói PHẢI
    LÀM GÌ — và với một công cụ mà người dùng đang đứng giữa một quy trình có
    gate, đó là bỏ họ lại đúng lúc họ cần một mũi tên.
    """
    if re.search(r"\beaa [a-z]", thong_diep):
        return ""
    goi_y = GOI_Y_KHI_HONG.get(ten_lenh, ())
    if not goi_y:
        return ""
    if len(goi_y) == 1:
        return f"\n  Làm tiếp: {goi_y[0]}"
    return "\n  Làm tiếp:\n" + "\n".join(f"    {g}" for g in goi_y)


# --------------------------------------------------------------------------
# Định vị dự án và nạp cấu hình
# --------------------------------------------------------------------------


ENV_FILE = ".env"

#: Sổ số đo trên bo của một dự án (N-913, SL-173).
MEASURED_FILE = "board_facts.jsonl"
#: Thư mục thủ tục theo ngoại vi (V4, K9). Hai nguồn: ngoại vi của vi điều
#: khiển thuộc Platform Pack, linh kiện ngoài gắn trên mạch thuộc dự án.
PROCEDURE_DIR = "procedures"

from eaa.jsonout import SCHEMA as _SCHEMA_JSON  # noqa: E402

#: Lệnh KHÔNG đổi trạng thái gì — phân loại tường minh, vì đây là một hợp đồng
#: an toàn chứ không phải một tiện nghi (E1, SL-182). Dạng "a b" là lệnh con.
#:
#: Phép soi cây cú pháp trong TC-148 là HÀNG RÀO MỘT CHIỀU: nó bắt được lệnh
#: khai chỉ đọc mà thật ra có ghi, nhưng nó KHÔNG chứng minh được chiều ngược.
#: Chuỗi gọi sâu quá hai tầng thì nó bỏ sót — đo thử trên `gen` và `build` đều
#: lọt. Nên danh sách này khai tay, và phép soi chỉ canh nó khỏi trôi.
LENH_CHI_DOC: frozenset[str] = frozenset({
    "capabilities", "deviations", "environ", "field", "interface", "models",
    "packs", "policy", "problems", "procedure", "recall", "report", "status",
    "suggest", "ports", "read",
    "gate show", "docs list", "docs get", "design list", "knowledge stale",
    "measured list", "ledger list", "datasheet list", "plan list",
    "budget show", "budget tokens", "safety show", "errata show",
    "errata lookup", "sources need", "sources pages", "diagnose list",
    "skill list", "tool list", "playbook list", "memory list",
})

#: Lệnh ĐÃ có `--json`. Tập con thật sự của `LENH_CHI_DOC`; phần còn lại là
#: việc chưa làm chứ không phải việc đã bỏ, và tỉ lệ được báo ra chứ không
#: được giấu bằng cách thu hẹp mẫu số.
LENH_CO_JSON: tuple[str, ...] = (
    "status", "policy", "packs", "procedure", "problems", "gate show",
)

#: Kết quả bộ chuẩn của một dự án (GĐ2, SL-177).
BENCH_FILE = "bench_results.jsonl"


def load_env_file(root: Path | None = None) -> list[str]:
    """Nạp ``.env`` vào biến môi trường của tiến trình.

    NFR-06 nói khóa chỉ đi qua biến môi trường. Tệp này KHÔNG phá quy tắc đó:
    nó chỉ là chỗ nạp vào môi trường lúc khởi động, và adapter mô hình vẫn chỉ
    đọc ``os.environ`` chứ không biết tệp nào tồn tại.

    Hai luật:

    * **Biến đã đặt trong shell luôn thắng** — kể cả khi đặt thành CHUỖI RỖNG.
      Người gõ ``EAA_LLM_KEY=... eaa gen`` phải nhận đúng khóa họ vừa gõ,
      không phải khóa cũ trong tệp; và người gõ ``EAA_LLM_KEY= eaa chat`` đang
      nói "chạy không có khóa", không phải "lấy giúp tôi khóa trong .env".
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
        # ``ten in os.environ`` chứ KHÔNG phải truthiness. Một biến đặt thành
        # chuỗi rỗng LÀ một biến đã đặt, và người gõ ``EAA_LLM_KEY= eaa chat``
        # đang nói "chạy không có khóa" — đó là cách duy nhất để thử đường
        # không-có-khóa trên một máy có sẵn .env. Dùng truthiness thì .env lặng
        # lẽ điền vào, và mã lệch với chính luật nó khai ở trên.
        if ten in os.environ:
            continue
        os.environ[ten] = gia_tri
        da_nap.append(ten)
    return da_nap


def repo_root() -> Path:
    """Gốc cài đặt EAA — nơi chứa ``packs/`` và ``projects/``."""
    return Path(os.environ.get("EAA_HOME", Path(__file__).resolve().parent.parent))


#: Dấu hiệu một thư mục LÀ thư mục dự án.
#:
#: Hai tệp chứ không một: ``eaa brief`` dựng ``constraints.yaml`` trước, còn
#: ``eaa init`` mới ghi Project State — nên trong quãng giữa hai lệnh ấy dự án
#: đã tồn tại mà chưa có state. Nhận theo một tệp thì đúng quãng người dùng cần
#: nhất lại là quãng không nhận ra.
DAU_HIEU_DU_AN = (STATE_FILE, CONSTRAINTS_FILE)


def du_an_chua_thu_muc(thu_muc: Path | None = None) -> Path | None:
    """Dự án chứa thư mục đang đứng — đi ngược lên như ``git`` tìm ``.git``.

    Vì sao vị trí được tính là một cách chỉ định
    ---------------------------------------------

    Người dùng đã ở trong thư mục dự án khi gõ lệnh. Bắt họ nói lại điều ấy
    bằng ``--project`` hoặc ``EAA_PROJECT`` là bắt khai một thứ hệ thống nhìn
    thấy được — và mỗi lần khai lại là một lần khai nhầm được, đúng ở kho có
    nhiều dự án, tức đúng lúc nhầm là tốn kém nhất.

    Đi ngược lên chứ không chỉ xét đúng thư mục hiện tại: người ta làm việc
    trong ``prompts/`` hay ``firmware/`` của dự án nhiều hơn là ở gốc của nó.

    Vì sao KHÔNG đặt trên biến môi trường
    --------------------------------------

    Thứ tự là **tham số → biến môi trường → vị trí → duy nhất**: cái được gõ ra
    thắng cái được suy ra. Một biến đã export là một câu người dùng đã nói
    thành lời; vị trí thư mục thì không. Nhưng khi hai thứ ấy chỉ về hai dự án
    khác nhau, hệ thống **nói ra** — im lặng ở đây là cách một lượt làm việc đi
    nhầm dự án suốt buổi mà không ai biết.
    """
    try:
        hien_tai = (thu_muc or Path.cwd()).resolve()
    except OSError:  # thư mục hiện tại vừa bị xóa
        return None
    for muc in (hien_tai, *hien_tai.parents):
        if any((muc / ten).is_file() for ten in DAU_HIEU_DU_AN):
            return muc
    return None


def resolve_project(duong_dan: str | None, *, phai_ton_tai: bool = True) -> Path:
    """Tìm dự án: tham số → biến môi trường → thư mục đang đứng → duy nhất.

    FR-PLT-03 dự trù nhiều dự án song song; ở đây chỉ chọn dự án, chưa quản lý
    vòng đời ``eaa new/switch`` (Should, chưa thuộc MVP).

    ``phai_ton_tai=False`` cho ``eaa brief``: lệnh ấy chạy TRƯỚC khi dự án tồn
    tại — nó chính là thứ tạo ra dự án.
    """
    if duong_dan:
        goc = Path(duong_dan).expanduser().resolve()
        if not goc.is_dir() and phai_ton_tai:
            raise CliError(f"Không có thư mục dự án: {goc}")
        return goc

    theo_vi_tri = du_an_chua_thu_muc()

    tu_moi_truong = os.environ.get("EAA_PROJECT")
    if tu_moi_truong:
        chon = resolve_project(tu_moi_truong, phai_ton_tai=phai_ton_tai)
        if theo_vi_tri is not None and theo_vi_tri != chon:
            print(
                f"⚠ Bạn đang đứng trong {theo_vi_tri.name}, nhưng EAA_PROJECT trỏ "
                f"tới {chon.name} — dùng {chon.name}.\n"
                f"  Muốn dùng chỗ đang đứng: unset EAA_PROJECT, hoặc "
                f"--project {theo_vi_tri}",
                file=sys.stderr,
            )
        return chon

    if theo_vi_tri is not None:
        return theo_vi_tri

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
            f"Có nhiều dự án ({ten}) — chỉ rõ bằng --project, đặt EAA_PROJECT, "
            "hoặc cd vào thư mục dự án rồi gõ lại."
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


def _troi_rang_buoc(state: ProjectState, project: Path) -> str:
    """Băm ràng buộc trong state có còn khớp tệp trên đĩa không.

    ``constraints_version`` không phải một nhãn trang trí: nó đi vào commit
    message theo NFR-07 làm **bằng chứng xuất xứ** — "mã này sinh ra dưới bộ
    ràng buộc ấy". Nếu ai đó sửa ``constraints.yaml`` mà băm trong state vẫn
    là băm cũ, thì mọi commit sau đó mang một khẳng định SAI, và khẳng định ấy
    nằm vĩnh viễn trong lịch sử Git.

    Trước bản sửa này ``eaa status`` in băm cũ ra như một sự thật: sửa
    constraints.yaml xong, băm trên màn hình không đổi, và không có gì báo.
    Phát hiện trong bộ ca xấu C-04.

    Trả về chuỗi rỗng khi khớp — im lặng ở đây là câu trả lời đúng.
    """
    from eaa.kb import Constraints, HardwareProfile, KbError

    duong_dan = project / CONSTRAINTS_FILE
    if not state.constraints_version or not duong_dan.is_file():
        return ""
    try:
        that = Constraints.load(duong_dan).content_version
    except (KbError, Exception):  # noqa: BLE001 - tệp hỏng cũng là một dạng trôi
        return "   ⚠ KHÔNG ĐỌC ĐƯỢC constraints.yaml — băm này không kiểm lại được"
    if that != state.constraints_version:
        return (
            f"\n                ⚠ TRÔI: constraints.yaml trên đĩa băm {that}."
            "\n                  Băm này đi vào commit message làm bằng chứng xuất xứ"
            "\n                  (NFR-07) — để lệch là ghi một khẳng định sai vào lịch"
            "\n                  sử Git. Chốt lại bộ ràng buộc mới qua gate G1."
        )

    # Hồ sơ phần cứng cũng phải soi, và vì cùng một lý do.
    #
    # Tệp ấy mở đầu bằng đúng câu "Sửa tệp này kích hoạt phân tích ảnh hưởng và
    # phải duyệt lại tại G1 (AIS §8.1) — đổi một chân là đổi mọi module chạm
    # vào chân đó". Suốt bốn sprint không cơ chế nào thi hành câu ấy: hồ sơ G1
    # in ra SỐ PHIÊN BẢN khai trong tệp chứ không phải băm nội dung, nên sửa
    # bảng chân mà giữ nguyên `version: 1` thì mọi thứ im lặng (SL-139).
    hs = project / HARDWARE_PROFILE_FILE
    if not hs.is_file():
        return ""
    if not state.hardware_version:
        # Dự án dựng trước SL-139: G1 đã duyệt mà chưa neo vào hồ sơ phần cứng.
        # Im lặng ở đây sẽ giữ nguyên đúng cái lỗ vừa tìm ra — không có mốc thì
        # không phát hiện được trôi, và "không phát hiện được" đọc y hệt
        # "không có gì trôi".
        if state.gate_status("G1") == "approved":
            return (
                "\n                ⚠ CHƯA NEO: G1 đã duyệt nhưng quyết định ấy không"
                "\n                  neo vào hardware_profile.yaml, nên từ lúc duyệt"
                "\n                  tới giờ bảng chân đổi bao nhiêu lần cũng không ai"
                "\n                  biết. Duyệt lại G1 một lần để đặt mốc."
            )
        return ""
    try:
        that_pc = HardwareProfile.load(hs).content_version
    except (KbError, Exception):  # noqa: BLE001
        return "   ⚠ KHÔNG ĐỌC ĐƯỢC hardware_profile.yaml — băm này không kiểm lại được"
    if that_pc == state.hardware_version:
        return ""
    return (
        f"\n                ⚠ TRÔI: hồ sơ phần cứng trên đĩa băm {that_pc}."
        "\n                  Bảng chân LÀ kiến trúc: đổi một chân là đổi mọi module"
        "\n                  chạm vào chân đó, và mã sinh sau đây sẽ ghi mức logic vào"
        "\n                  chân mới mà chưa ai duyệt. Chốt lại qua gate G1."
    )


def _in_cong_cu_thieu(project: Path) -> None:
    """In công cụ ngoài bắt buộc còn thiếu, kèm cổng chúng chặn.

    Im lặng khi đủ — một dòng "mọi thứ ổn" lặp ở mọi bản tóm tắt sẽ bị mắt bỏ
    qua, và lúc nó đổi thành cảnh báo thì cũng bị bỏ qua nốt.
    """
    thieu = [b for b in _tao_doctor(project).scan() if b.blocking]
    if not thieu:
        return
    cong = sorted({c for b in thieu for c in b.spec.gates})
    print()
    print(f"  ⚠ {len(thieu)} công cụ bắt buộc chưa có: "
          f"{', '.join(b.spec.name for b in thieu)}")
    if cong:
        print(f"    Các cổng {', '.join(cong)} KHÔNG chạy được cho tới khi khắc phục,")
        print("    nên mã sinh ra chưa kiểm chứng được và chưa merge được.")
    print("    → CẦN BẠN:  eaa doctor --fix")


def _in_nhan_nhap(project: Path) -> None:
    """Nhắc rằng đây là chỗ làm nháp, ở MỌI bản tóm tắt trạng thái.

    ``eaa/scratch.py`` khai ở đầu module: *"Chúng mang nhãn GIẢ ĐỊNH trong
    chính tệp, và ``eaa status`` nhắc lại."* Vế sau không đúng — dòng nhắc chỉ
    được in đúng một lần, lúc `eaa scratch` dựng chỗ nháp. Mọi lệnh sau đó im.

    Hậu quả là đúng thứ chính module ấy cảnh báo: *"một con số mặc định trông y
    hệt một con số đã chốt, và đó là cách một bản nháp lặng lẽ trở thành một
    bản bàn giao."* Con số nháp ở đây không trung tính — nó là dung lượng và
    tần số của một họ chip nào đó, và đem áp lên bo khác thì nó sai theo cách
    nhìn vẫn hợp lý.
    """
    from eaa.scratch import warning_banner

    nhan = warning_banner(project)
    if nhan:
        print()
        print(nhan)


def _in_tom_tat(state: ProjectState, project: Path) -> int:
    _in_tieu_de(f"Dự án: {project.name}  ({project})")
    print(f"Pha hiện tại : {state.phase} — {PHASE_NAMES[state.phase]}")
    print(f"Mức phân quyền: {level(state.phase)}")
    print(f"Ràng buộc     : {state.constraints_version}{_troi_rang_buoc(state, project)}")
    if state.llm:
        print(f"Mô hình       : {state.llm.get('provider', '?')}/{state.llm.get('model', '?')}")
    if state.env_hash:
        print(f"Môi trường    : {state.env_hash}")
    print(f"Cập nhật lúc  : {state.updated_at}")

    # Xung đột phần cứng chưa phân xử phải hiện ở MỌI bản tóm tắt trạng thái.
    # Ghi nó vào hồ sơ mà chỉ in ở một lệnh ít ai gõ thì cũng như không ghi.
    try:
        _in_xung_dot_phan_cung(
            _nap_kho(HardwareProfile.load, project / HARDWARE_PROFILE_FILE)
        )
    except Exception:  # noqa: BLE001 - hồ sơ hỏng không được chặn bản tóm tắt
        pass

    # Công cụ ngoài còn thiếu cũng phải hiện ở đây, cùng lý do với xung đột.
    #
    # Chỗ này từng thiếu, và nó hỏng theo đường vòng: 'status' là bản tóm tắt
    # ai cũng đọc đầu tiên, kể cả Agent khi được hỏi "cần người làm gì trước
    # khi bạn sinh mã được". Nó đọc status, thấy đủ thứ trừ chuyện thiếu
    # toolchain, rồi trả lời tự tin và THIẾU. Câu trả lời ấy không sai chỗ nào
    # kiểm được — nó chỉ bỏ mất một nửa.
    #
    # Sửa bằng cách bắt Agent gọi thêm lệnh khác là sửa bằng lời dặn. Sửa bằng
    # cách để chính bản tóm tắt nói ra thì đường tắt cũng thành đường đúng.
    try:
        _in_cong_cu_thieu(project)
    except Exception:  # noqa: BLE001 - không dò được thì im, đừng báo nhầm là ĐỦ
        pass

    _in_nhan_nhap(project)

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

    # Dữ liệu có cấu trúc cho lớp IDE (E1). Gọi vô điều kiện: không bật
    # `--json` thì đây là lệnh rỗng, nên không ai phải viết `if` quanh nó.
    from eaa import jsonout

    jsonout.ket_qua(
        project={"name": project.name, "path": str(project)},
        phase={"id": state.phase, "name": PHASE_NAMES[state.phase],
               "level": str(level(state.phase))},
        constraints_version=state.constraints_version,
        llm=dict(state.llm or {}),
        env_hash=state.env_hash,
        updated_at=state.updated_at,
        gates=[{"id": g, "label": _nhan_gate(state, g)} for g in GATE_ORDER],
        backlog=[
            {"id": m.id, "status": m.status, "retries": m.retries,
             "uses": list(m.uses), "current": m.id == state.current_module}
            for m in state.backlog
        ],
        next_step={"message": thong_diep, "exit_code": ma_thoat},
    )
    return ma_thoat


# --------------------------------------------------------------------------
# Lệnh
# --------------------------------------------------------------------------


#: Nhắc lại từ eaa.llm.base để CLI không tự đặt tên biến môi trường lần nữa.
from eaa.llm.base import KEY_ENV as LLM_KEY_ENV  # noqa: E402


def chon_llm_theo_moi_truong() -> tuple[str, str, str]:
    """Agent tự nhìn môi trường của chính nó để chọn adapter mô hình.

    Trả về ``(provider, model, lý do)``. Lý do được IN RA, vì một lựa chọn tự
    động mà không nói mình đã chọn gì thì cũng là một lựa chọn giấu.

    Vì sao đây là việc của Agent chứ không của người dùng: mặc định ``mock`` là
    di sản của Sprint 1–3, lúc chưa có khóa nào. Sang Sprint 4 khóa đã có, mà
    mặc định thì đứng yên — nên mọi dự án mới đều khởi tạo ở chế độ giả lập,
    rồi chết ở lần đầu cần mô hình thật với một thông báo nói về nội tình của
    engine thay vì nói phải gõ lệnh gì. Người dùng không có nghĩa vụ biết
    trường ``llm.provider`` trong Project State tên là gì.

    KHÔNG bao giờ đọc hay in giá trị khóa — chỉ hỏi nó có tồn tại không (NFR-06).
    """
    from eaa.llm.gemini import DEFAULT_MODEL

    if os.environ.get(LLM_KEY_ENV, "").strip():
        return (
            "gemini",
            os.environ.get("EAA_LLM_MODEL", "") or DEFAULT_MODEL,
            f"thấy {LLM_KEY_ENV} trong môi trường",
        )
    return (
        "mock",
        "mock-deterministic-1",
        f"chưa có {LLM_KEY_ENV} nên dùng adapter giả lập; "
        "đặt khóa rồi 'eaa init --force' để chuyển sang mô hình thật",
    )


def canh_bao_lech_cau_hinh(state: Any) -> str:
    """Project State nói một đằng, môi trường nói một nẻo.

    Không tự sửa: Project State đi cùng dự án và nằm trong Git — nó là một
    phần điều kiện thí nghiệm, nên chỉ người mới được đổi. Nhưng im lặng thì
    người dùng sẽ gặp một lỗi khó hiểu ở tận đâu đó phía sau.
    """
    provider = (getattr(state, "llm", None) or {}).get("provider", "mock")
    co_khoa = bool(os.environ.get(LLM_KEY_ENV, "").strip())
    if provider == "mock" and co_khoa:
        return (
            f"Project State đang dùng adapter giả lập, nhưng máy CÓ {LLM_KEY_ENV}.\n"
            "  Mọi lệnh cần mô hình thật sẽ không chạy. Chuyển sang mô hình thật:\n"
            "      eaa init --force"
        )
    if provider == "gemini" and not co_khoa:
        return (
            f"Project State đang dùng mô hình thật, nhưng KHÔNG thấy {LLM_KEY_ENV}.\n"
            f"  Đặt khóa vào .env hoặc export {LLM_KEY_ENV}=... trước khi chạy."
        )
    return ""


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

    # Người nêu rõ thì người thắng; không nêu thì Agent tự nhìn môi trường.
    tu_chon = chon_llm_theo_moi_truong()
    provider = args.provider or tu_chon[0]
    model = args.model or (tu_chon[1] if not args.provider else "")
    ly_do = "" if args.provider else tu_chon[2]

    try:
        manifest = load_manifest(repo_root() / "packs" / rang_buoc.platform)
    except PackError as exc:
        raise CliError(str(exc)) from exc

    state = ProjectState(
        phase="A",
        gates={gate: "pending" for gate in GATE_ORDER},
        backlog=[],
        constraints_version=rang_buoc.content_version,
        llm={"provider": provider, "model": model},
    )
    store.save(state)

    _in_tieu_de("Đã khởi tạo dự án")
    if ly_do:
        print(f"  Chọn mô hình tự động: {ly_do}")
    print(f"  Thư mục       : {project}")
    print(f"  Project State : {store.path}")
    print(f"  Platform Pack : {manifest.name} v{manifest.version}")
    print(f"  Ràng buộc     : v{rang_buoc.version} {state.constraints_version}")
    print(f"  Hồ sơ phần cứng: {len(ho_so.peripherals)} ngoại vi, "
          f"{len(ho_so.components)} linh kiện, "
          f"{len(ho_so.pin_map)} chân")
    print(f"  Mô hình       : {state.llm['provider']}/{state.llm['model'] or '(mặc định của adapter)'}")
    _in_xung_dot_phan_cung(ho_so)
    print(
        f"\nDự án bắt đầu ở pha A ({PHASE_NAMES['A']}), toàn bộ gate ở trạng thái "
        "pending.\nBước kế tiếp: chốt ràng buộc & kiến trúc rồi duyệt G1."
    )
    return EXIT_OK


def _in_xung_dot_phan_cung(ho_so: Any) -> None:
    """In những xung đột phần cứng đã ghi mà chưa ai phân xử.

    In ở MỌI chỗ hiển thị trạng thái, không chỉ một chỗ. Một xung đột chân đã
    biết mà chỉ hiện ở một lệnh ít ai gõ thì cũng như không ghi: nó phải đập
    vào mắt đúng lúc người ta sắp sinh mã chạm tới chân ấy.
    """
    xung_dot = getattr(ho_so, "conflicts", None) or []
    if not xung_dot:
        return
    print()
    print(f"  ⚠ {len(xung_dot)} XUNG ĐỘT PHẦN CỨNG đã ghi, CHƯA phân xử:")
    for c in xung_dot:
        ai = ", ".join(str(x) for x in (c.get("claimed_by") or []))
        print(f"      chân {c.get('pin', '?')} — {ai}")
        if c.get("found_in"):
            print(f"        thấy ở: {c['found_in']}")
        if c.get("detail"):
            print(f"        {' '.join(str(c['detail']).split())}")
    print("      Máy KHÔNG tự dời chân: đây là bo của bạn, và chọn dời cái nào")
    print("      là quyết định về phần cứng. Sửa xong thì đặt status: đã phân xử.")


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

    from eaa import jsonout

    jsonout.ket_qua(
        stages=[
            {"id": ma, "phase": cd.phase, "level": str(cd.level),
             "human_share": cd.human_share, "ai_share": cd.ai_share,
             "name": cd.name}
            for ma, cd in STAGES.items()
        ],
        transitions=[
            {"from": pha,
             "to": PHASE_ORDER[i + 1] if i + 1 < len(PHASE_ORDER) else None,
             "gate": gate_for_transition(
                 pha, PHASE_ORDER[i + 1] if i + 1 < len(PHASE_ORDER) else None)}
            for i, pha in enumerate(PHASE_ORDER)
        ],
    )
    return EXIT_OK


def cmd_design_list(args: argparse.Namespace) -> int:
    """Khuôn mẫu tài liệu thiết kế đang có (AIS §8.5)."""
    from eaa.confidence import DA_KIEM, header
    from eaa.designdoc import SPEC_DIR, list_specs
    from eaa.office import DINH_DANG

    ds = list_specs()
    _in_tieu_de(f"Khuôn mẫu tài liệu thiết kế ({len(ds)})")
    print(header(DA_KIEM))
    print()
    for s in ds:
        print(f"  {s.kind:<12} {s.short:<5} {s.title}")
        if s.standard:
            print(f"               theo: {s.standard}")
        print(f"               {len(s.sections)} mục · mặc định .{s.mac_dinh_dinh_dang}")
        print()
    # Dò công cụ ngoài NGAY Ở ĐÂY thay vì để người dùng phát hiện lúc chạy.
    # "pdf" nằm trong danh sách định dạng không có nghĩa là máy này xuất được
    # pdf — và một danh sách nói được thứ nó không làm được thì tệ hơn một
    # danh sách ngắn hơn.
    from eaa.office import tim_soffice

    soffice = tim_soffice()
    print("── Định dạng xuất được")
    for k, v in DINH_DANG.items():
        dau = ""
        if k == "pdf":
            dau = "  ✓" if soffice else "  ✗ CHƯA DÙNG ĐƯỢC trên máy này"
        print(f"  {k:<6} {v}{dau}")
    if not soffice:
        print()
        print("  PDF cần LibreOffice. Cài:  brew install --cask libreoffice")
        print("  Bốn định dạng còn lại không cần gì thêm.")
    print()
    print(f"Khuôn mẫu là DỮ LIỆU, ở {SPEC_DIR}. Sửa cấu trúc một tài liệu là sửa")
    print("tệp YAML tương ứng — không phải sửa mã, không phải chạy lại test.")
    print()
    print("  eaa design gen srs --format docx")
    return EXIT_OK


def cmd_design_gen(args: argparse.Namespace) -> int:
    """Dựng một tài liệu thiết kế từ hồ sơ dự án (AIS §8.5).

    Không hỏi mô hình một chữ nào — xem phần đầu ``eaa/designdoc.py``.
    """
    from datetime import datetime, timezone

    from eaa.designdoc import DesignDocError, build, load_spec
    from eaa.office import DINH_DANG, OfficeError, ThieuCongCu, write

    project = resolve_project(args.project)
    try:
        spec = load_spec(args.kind)
    except DesignDocError as exc:
        raise CliError(str(exc)) from None

    dinh_dang = (args.format or spec.mac_dinh_dinh_dang).lower()
    if dinh_dang not in DINH_DANG:
        raise CliError(
            f"Chưa xuất được định dạng {dinh_dang!r}. Đang có: "
            + ", ".join(sorted(DINH_DANG))
        )

    luc = args.at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        doc = build(spec, project, created_at=luc)
    except DesignDocError as exc:
        raise CliError(str(exc)) from None

    if args.out:
        dich = Path(args.out)
    else:
        thu_muc = project / "artifacts"
        dich = thu_muc / f"{spec.kind}_{project.name}.{dinh_dang}"

    try:
        p = write(doc, dich, fmt=dinh_dang)
    except ThieuCongCu as exc:
        raise CliError(str(exc)) from None
    except OfficeError as exc:
        raise CliError(str(exc)) from None

    print(f"Đã ghi {p}  ({p.stat().st_size:,} byte)".replace(",", "."))
    print(f"  {len(doc.headings)} mục · {len(doc.blocks)} khối")
    thieu = [b for b in doc.blocks
             if getattr(b, "level", "") and "Chưa có dữ liệu" in getattr(b, "text", "")]
    if thieu:
        print(f"  ⚠ {len(thieu)} mục chưa có dữ liệu — từng mục trong tài liệu đã")
        print("    nói rõ chạy lệnh gì để có. Chúng KHÔNG bị để trống: một mục")
        print("    trống đọc như 'không cần', trong khi thật ra là 'chưa ai điền'.")
    return EXIT_OK


def cmd_models(args: argparse.Namespace) -> int:
    """Danh mục mô hình — người chọn, hệ không tự chọn (AIS §2).

    Lệnh này chỉ đọc và không gọi mạng: nó in danh mục đã kiểm sẵn kèm mã đang
    dùng của dự án hiện tại. Hỏi lại nhà cung cấp mỗi lần gõ ``eaa models`` là
    biến một lệnh tra cứu thành một lệnh tốn tiền và cần mạng.
    """
    from eaa.llm.catalog import render_catalog

    dang_dung = ""
    try:
        project = resolve_project(args.project)
        store = StateStore(project / STATE_FILE)
        if store.exists():
            state = store.load()
            dang_dung = (state.llm or {}).get("model", "")
    except CliError:
        pass

    # Cờ --model của chính lượt chạy này thắng, và phải hiện đúng như thế.
    if _MODEL_LUOT_NAY:
        dang_dung = _MODEL_LUOT_NAY

    print(render_catalog(dang_dung=dang_dung, provider=args.provider))
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

    from eaa import jsonout

    jsonout.ket_qua(packs=[
        {"name": m.name, "version": m.version, "targets": list(m.targets),
         "capabilities": [
             {"name": ten,
              "command": m.invocation(ten).command[0],
              "requires_confirmation": m.invocation(ten).requires_confirmation}
             for ten in sorted(m.capabilities)
         ]}
        for m in packs.values()
    ])
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


#: Mã model do cờ ``--model`` của lượt chạy này đặt. Ghi một lần trong
#: :func:`main`, đọc trong :func:`_tao_llm`. Rỗng nghĩa là người dùng không nêu.
_MODEL_LUOT_NAY: str = ""


def _tao_llm(state: Any, project: Path, *, model_override: str = "") -> Any:
    """Chọn adapter mô hình theo cấu hình trong Project State (ADR-03).

    TC-11 đòi hỏi đổi nhà cung cấp không làm đổi hành vi Orchestrator, nên chỗ
    duy nhất biết adapter nào đang chạy là hàm này.

    Thứ tự quyết mã model, từ mạnh xuống yếu:

    1. Cờ ``--model`` của lượt chạy này. Mạnh nhất vì nó là một **hành động có
       chủ ý của người dùng ngay tại chỗ dùng** — họ gõ nó ra, họ thấy nó, và
       nó biến mất sau lượt chạy.
    2. Project State. Đi cùng dự án và nằm trong Git; mã model là một phần của
       điều kiện thí nghiệm.
    3. Biến môi trường ``EAA_LLM_MODEL`` — tiện cho cả phiên shell nhưng dễ bị
       quên là mình đã đặt, nên xếp dưới.
    4. Mặc định của adapter.

    Hệ **không bao giờ tự đổi model** theo loại việc: xem ``eaa/llm/catalog.py``
    để biết vì sao đó là một quyết định chứ không phải một chỗ chưa làm.
    """
    from eaa.llm.calllog import CallLog, ReplayClient
    from eaa.llm.mock import MockLLM

    provider = (state.llm or {}).get("provider", "mock")
    model_override = model_override or _MODEL_LUOT_NAY
    model = (
        model_override
        or (state.llm or {}).get("model")
        or os.environ.get("EAA_LLM_MODEL", "")
    )
    if model_override:
        from eaa.llm.catalog import get as tra_model

        thong_tin = tra_model(model_override)
        ghi_chu = "" if thong_tin else "  (mã này chưa có trong danh mục đã kiểm)"
        print(f"[--model] lượt chạy này dùng {model_override}, không ghi vào "
              f"Project State.{ghi_chu}")
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


def _ban_do_thanh_ghi(manifest: Any, project: Path) -> Any:
    """Bản đồ thanh ghi của pack, hoặc None khi pack chưa khai.

    Nuốt lỗi ở đây là CỐ Ý và có giới hạn: một tệp bản đồ hỏng không được làm
    `build_context` sập, vì `build_context` là cửa của MỌI lệnh — kể cả những
    lệnh chẳng liên quan gì tới thanh ghi. Cổng `regcheck` nhận None thì nó im,
    và thông báo hỏng đi ra qua `eaa doctor` chứ không qua một traceback giữa
    lúc người dùng đang gõ `eaa status`.
    """
    from eaa.regmap import RegmapError, tu_pack

    try:
        return tu_pack(manifest, project)
    except RegmapError as exc:
        import sys as _sys

        print(f"⚠ Bản đồ thanh ghi không nạp được: {exc}", file=_sys.stderr)
        return None


def build_context(project: Path, *, llm: Any = None) -> AppContext:
    """Nối dây toàn bộ một dự án từ thư mục của nó."""
    from eaa.budget import ResourceBudget, TokenBudget
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
    from eaa.tools.regcheck import RegCheckGate
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
    # Số đo trên chính bo này — lớp K8 (N-913). Nối ở đây vì CLI là composition
    # root; composer không tự đi tìm sổ nào cả.
    from eaa.measured import MeasuredStore

    composer.measured = MeasuredStore(project / MEASURED_FILE)
    composer.procedures = _kho_thu_tuc(project)
    # Cách kiểm trên máy chủ đến từ pack; engine chỉ ghép vào đúng chỗ.
    try:
        import yaml as _yaml

        _pack_yaml = _yaml.safe_load(
            (repo_root() / "packs" / kb.constraints.platform / "pack.yaml")
            .read_text(encoding="utf-8")
        ) or {}
        _ht = _pack_yaml.get("host_test")
        if isinstance(_ht, dict) and _ht.get("mock_include"):
            # Giải đường dẫn thư mục tiêu đề giả NGAY tại đây, nơi biết pack
            # nằm ở đâu. Đưa xuống một cái tên trần thì mô hình phải đoán chỗ,
            # và nó đoán tương đối so với thư mục firmware — sai (SL-143).
            _goc_pack = repo_root() / "packs" / kb.constraints.platform
            _gia = _goc_pack / str(_ht["mock_include"])
            if _gia.is_dir():
                _ht = dict(_ht)
                _ht["mock_include_path"] = str(_gia)
                _ht["support_sources"] = [
                    str(p) for p in sorted(_gia.glob("*.c"))
                ]
        composer.host_test = _ht
        _duong_dan_tieu_de_gia = str((_ht or {}).get("mock_include_path") or "")
    except Exception:  # noqa: BLE001 - chưa cài pack thì thôi
        composer.host_test = None
        _duong_dan_tieu_de_gia = ""
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
    ngan_sach = ResourceBudget.from_constraints(kb.constraints)
    chain = [
        CompileGate(runner),
        SizeGate(
            runner,
            limits=kb.constraints.limits,
            budget=ngan_sach,
            module=module_hien_tai,
        ),
        StaticGate(
            runner=runner,
            manifest=manifest,
            forbidden=list(kb.constraints.forbidden),
            limits=kb.constraints.limits,
            registers=graph.registers_for(module_hien_tai) if module_hien_tai else [],
            allowed_chunk_ids=[c.id for c in kb.datasheets.active()],
            # Nguồn đơn vị THẬT của hằng số, để bắt chú thích gán nhầm đơn vị
            # (N-911). Dùng chung đúng cái sổ mà lớp K8 của prompt đọc.
            measured=composer.measured,
        ),
        # Cổng 5 — đối chiếu mã với bản đồ thanh ghi của hãng (GĐ1, SL-176).
        #
        # Đứng SAU `static` và TRƯỚC `unittests`: nó cần mã đã qua luật cấm của
        # dự án, và kết quả của nó có nghĩa hơn khi đọc trước lúc chạy bài kiểm
        # — một giá trị sai với silicon vẫn hợp lệ trong bộ giả lập trên máy chủ.
        #
        # KHÔNG vào `required_gates`: bằng chứng merge của mọi module đã có sẽ
        # thành thiếu cổng, và dự án chưa có tệp bản đồ sẽ bị ép có. Cổng vẫn
        # CHẶN được vì chuỗi cổng dừng ở cổng hỏng đầu tiên.
        RegCheckGate(
            regmap=_ban_do_thanh_ghi(manifest, project),
            registers=graph.registers_for(module_hien_tai) if module_hien_tai else [],
            chunk_registers={
                c.id: tuple(c.registers) for c in kb.datasheets.active()
            },
        ),
        UnitTestGate(
            # ĐÚNG thư mục bộ sinh mã ghi vào. Nó ghi `src/` và `tests/` trong
            # thư mục làm việc của firmware; cổng trước đây đọc `<dự án>/tests`
            # — hai chỗ khác nhau. Nên khi mô hình viết đúng tệp test, cổng vẫn
            # báo "không có bộ kiểm thử đơn vị nào" (SL-134).
            #
            # Không ai sai một mình: bộ sinh ghi đúng chỗ của nó, cổng đọc đúng
            # chỗ của nó, và hai chỗ ấy chưa bao giờ được đối chiếu — vì chưa
            # lần nào có tệp test thật để lộ ra.
            tests_dir=firmware / "tests",
            work_dir=firmware,
            # Để cổng nêu được ĐÍCH DANH phần nó không kiểm tới (N-053). Không
            # có ba tham số này thì nó vẫn chạy y như trước, chỉ im lặng hơn.
            module=module_hien_tai,
            graph=graph,
            constraints=kb.constraints,
            # Thư mục tiêu đề giả vào MÔI TRƯỜNG, để lệnh dịch trong bài kiểm
            # tìm thấy tiêu đề nền tảng dù mô hình có nhớ viết `-I...` hay không.
            mock_include=_duong_dan_tieu_de_gia,
        ),
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
        token_budget=TokenBudget.from_constraints(kb.constraints),
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
    if args.plan_action == "propose":
        return _plan_propose(project, args)
    if args.plan_action == "accept":
        return _plan_accept(project, store, args)
    if args.plan_action == "add":
        return _plan_add(project, store, args)
    if args.plan_action == "order":
        return _plan_order(store, args)
    if args.plan_action == "reopen":
        return _plan_reopen(project, store, args)
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

    # Mã module đi thẳng vào TÊN NHÁNH GIT và TÊN TỆP sinh ra, nên nó phải hẹp.
    #
    # Không có phép kiểm này, một lệnh gõ nhầm — hay một biến shell không được
    # tách từ đúng cách — tạo ra một module tên `"drv_x --uses twi"`, và cái
    # tên ấy im lặng đi tiếp cho tới lúc dựng nhánh. Đo được ngày 31/08/2026.
    import re

    if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", args.module_id or ""):
        raise CliError(
            f"Mã module {args.module_id!r} không hợp lệ. Phải là snake_case, "
            "2–40 ký tự, chỉ chữ thường / số / gạch dưới — mã module đi vào tên "
            "nhánh Git và tên tệp sinh ra.\n"
            "    Nếu bạn định truyền thêm cờ: eaa plan add <mã> --uses a,b"
        )

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


#: Trạng thái mở lại được. `merged` là trường hợp chính; `in_review` và
#: `handoff` cho vào cùng vì chúng cũng đang ĐỨNG, và cách thoát cũng là sinh
#: lại. `todo` thì đã ở đó rồi.
TRANG_THAI_MO_LAI = ("merged", "in_review", "handoff", "stale", "blocked")


def _plan_reopen(project: Path, store: StateStore, args: argparse.Namespace) -> int:
    """Đưa một module đã merge về `todo` để sinh lại (SL-157).

    Vì sao phải có lệnh này: `eaa gen` trên module đã merge dừng lại và nói
    *"Sinh lại thì đưa nó về trạng thái todo trước"* — một câu đúng, chỉ tass
    thiếu mất chỗ làm việc ấy. Không lệnh nào trong `eaa plan` đặt lại được
    trạng thái, nên lối duy nhất đi tiếp là sửa tay `project_state.json`: đúng
    cái tệp có khoá, có ghi nguyên tử, và có một test canh nó không bị sửa
    ngoài luồng.

    Vì sao KHÔNG để `eaa gen` tự làm: mở lại mã đã merge là gỡ một quyết định
    G3 mà một người đã bấm. Việc ấy phải có người gõ ra và phải nêu lý do — lý
    do đi vào Error Ledger, nên lịch sử trả lời được câu "vì sao mã đã duyệt bị
    viết lại".

    Lệnh này KHÔNG nới lỏng bất biến nào: module quay về `todo` và phải đi lại
    trọn vòng lặp chuẩn, qua đủ cổng, rồi qua G3 một lần nữa. Nó chỉ mở đường
    vào vòng ấy.
    """
    ly_do = (getattr(args, "reason", "") or "").strip()
    if not ly_do:
        raise CliError(
            "Mở lại một module đã merge là gỡ một quyết định G3 đã có người "
            "bấm — bắt buộc kèm --reason. Lý do đi vào Error Ledger và vào "
            "prompt của lượt sinh lại."
        )

    # Kiểm TRƯỚC, chỉ đọc. Rồi ghi lý do. Rồi mới đổi trạng thái.
    #
    # Thứ tự này không phải chuyện gọn gàng: bản đầu tiên đổi trạng thái trước
    # rồi ghi ledger sau, và lần chạy thật đầu tiên ledger từ chối phân loại —
    # để lại một module đã mở lại mà không dòng nào nói vì sao. Việc cuối cùng
    # phải là việc KHÔNG hỏng được.
    state = store.load()
    muc = state.module(args.module_id)
    if muc is None:
        co = ", ".join(m.id for m in state.backlog) or "(backlog trống)"
        raise CliError(
            f"Module {args.module_id!r} không có trong backlog. Đang có: {co}."
        )
    truoc = muc.status
    if truoc == "todo":
        print(f"{args.module_id} đã ở trạng thái todo — không đổi gì.")
        return EXIT_OK
    if truoc not in TRANG_THAI_MO_LAI:
        raise CliError(
            f"{args.module_id} đang ở trạng thái {truoc!r}, không phải trạng "
            f"thái mở lại được ({', '.join(TRANG_THAI_MO_LAI)}). Một module "
            "đang chạy dở thì chờ nó dừng, đừng cắt ngang."
        )

    from eaa.ledger import ErrorLedger

    ErrorLedger(project / "error_ledger.jsonl").add(
        module=args.module_id,
        category="other",
        description=f"Mở lại từ trạng thái {truoc!r} để sinh lại: {ly_do}",
        evidence="eaa plan reopen",
    )

    with store.with_lock():
        state = store.load()
        muc = state.module(args.module_id)
        if muc is None or muc.status != truoc:
            raise CliError(
                f"{args.module_id} vừa đổi trạng thái giữa chừng — chạy lại lệnh."
            )
        muc.status = "todo"
        # Đếm vòng tự sửa thuộc về LƯỢT CHẠY, không thuộc về module. Giữ lại số
        # cũ là bắt lượt sinh mới trả nợ của lượt trước.
        muc.retries = 0
        store.save(state)

    print(f"{args.module_id}: {truoc} → todo. Lý do đã vào Error Ledger.")
    print(
        "Mã trên nhánh chính GIỮ NGUYÊN cho tới khi bản mới qua đủ cổng và qua "
        "G3 — mở lại không xoá gì cả."
    )
    print(f"Bước kế tiếp: eaa gen {args.module_id}")
    return EXIT_OK


# --------------------------------------------------------------------------
# UC04 — vòng lặp sinh mã
# --------------------------------------------------------------------------


def cmd_gen(args: argparse.Namespace) -> int:
    from eaa.orchestrator import PreconditionFailed

    project = resolve_project(args.project)
    ctx = build_context(project)

    xem_truoc = bool(getattr(args, "preview", False))
    nhap = [g.strip() for g in (getattr(args, "draft", "") or "").split(",") if g.strip()]
    if xem_truoc and nhap:
        raise CliError(
            "--preview và --draft loại trừ nhau: xem trước KHÔNG chạy cổng nào, "
            "còn nháp chạy một tập cổng. Chọn một."
        )
    if xem_truoc:
        ctx.orchestrator.config.preview = True
    if nhap:
        co = {getattr(g, "name", "") for g in ctx.orchestrator.gate_chain}
        la = [g for g in nhap if g not in co]
        if la:
            raise CliError(
                f"Chuỗi kiểm chứng không có cổng {', '.join(la)}. "
                f"Đang có: {', '.join(sorted(c for c in co if c))}"
            )
        ctx.orchestrator.config.draft_gates = tuple(nhap)

    try:
        ket_qua = ctx.orchestrator.run_module(args.module_id)
    except PreconditionFailed as exc:
        raise CliError(str(exc)) from exc

    tieu_de = ("XEM TRƯỚC — " if xem_truoc
               else "BẢN NHÁP — " if nhap else "Vòng lặp chuẩn — ")
    _in_tieu_de(tieu_de + args.module_id)
    for dong in ket_qua.attempts_log:
        print(dong)

    # Xem trước không chạy cổng nào, nên thứ duy nhất đáng in là CHÍNH MÃ.
    if xem_truoc and ket_qua.artifact is not None:
        for ten, noi_dung in (ket_qua.artifact.files or {}).items():
            print()
            print(f"── {ten}")
            print(noi_dung)

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


def _phuong_an_dang_cho(project: Path, gate_id: str) -> Any:
    """Tập phương án đang chờ người chọn tại gate này, nếu có."""
    from eaa.options import OPTIONS_FILE, OptionSet

    return OptionSet.load_all(project / OPTIONS_FILE).get(gate_id)


def dau_van_tay_G1(bam_rang_buoc: str, bam_phan_cung: str) -> str:
    """Băm mà quyết định G1 neo vào — gộp ràng buộc VÀ hồ sơ phần cứng.

    Gộp chứ không chọn một: G1 tên là *chốt ràng buộc cứng và kiến trúc*, và
    bảng chân là kiến trúc. Neo vào một nửa nghĩa là nửa còn lại đổi được sau
    khi người đã bấm duyệt, mà không dấu vết nào (SL-139).
    """
    import hashlib

    if not bam_phan_cung:
        return bam_rang_buoc
    gop = f"{bam_rang_buoc}\n{bam_phan_cung}".encode("utf-8")
    return "sha256:" + hashlib.sha256(gop).hexdigest()


def _doc_ho_so_phan_cung(project: Path) -> str:
    duong_dan = project / HARDWARE_PROFILE_FILE
    if not duong_dan.is_file():
        return "(dự án chưa có hardware_profile.yaml)"
    return duong_dan.read_text(encoding="utf-8")


def _ho_so_gate(ctx: AppContext, gate_id: str) -> Any:
    """Dựng hồ sơ cho gate chưa có yêu cầu nào đang chờ.

    G3 luôn có hồ sơ do Orchestrator đặt ở bước 10. Các gate còn lại được kỹ sư
    chủ động mở, nên hồ sơ dựng từ dữ liệu hiện hành của dự án. Băm nội dung vì
    thế phản ánh đúng thứ đang có trên đĩa lúc này — duyệt xong mà dữ liệu đổi
    thì quyết định cũ không còn khớp.
    """
    from eaa.gates import GatePayload

    state = ctx.store.load()
    phuong_an = _phuong_an_dang_cho(ctx.project, gate_id)
    if gate_id == "G1":
        # Hồ sơ neo vào CẢ HAI tệp, và cho người đọc CẢ HAI.
        #
        # Trước SL-139, dòng phần cứng dưới đây chỉ in `v{version}` — số phiên
        # bản do người khai TRONG tệp, không phải băm nội dung. Sửa bảng chân
        # mà không sửa số ấy thì dòng này giống nhau từng ký tự, `content_digest`
        # không đổi, và quyết định của người neo vào một nửa hồ sơ.
        bam_pc = getattr(ctx.kb.hardware, "content_version", "")
        return GatePayload(
            gate_id="G1",
            options=phuong_an,
            title="Chốt ràng buộc cứng và kiến trúc",
            summary=(
                f"constraints.yaml v{ctx.kb.constraints.version} "
                f"({ctx.kb.constraints.content_version})",
                f"hardware_profile.yaml v{ctx.kb.hardware.version} ({bam_pc})",
                f"backlog: {len(state.backlog)} module",
                f"điều cấm: {', '.join(ctx.kb.constraints.forbidden) or '—'}",
            ),
            details=(
                ctx.kb.constraints.path.read_text(encoding="utf-8")
                + "\n\n"
                + "═" * 70
                + "\nhardware_profile.yaml — bảng chân LÀ kiến trúc, G1 chốt cả nó\n"
                + "═" * 70
                + "\n"
                + _doc_ho_so_phan_cung(ctx.project)
            ),
            content_digest=dau_van_tay_G1(ctx.kb.constraints.content_version, bam_pc),
        )
    if gate_id == "G2":
        # G2 duyệt tri thức. Trích đoạn tài liệu và công cụ đều là tri thức
        # trong hệ thống này (AIS §9.1: manifest là một kho tri thức), nên cả
        # hai cùng lên một hồ sơ — người duyệt thấy đủ thứ sắp được ghi vào.
        de_xuat = [c for c in ctx.kb.datasheets.all() if not c.is_active]
        cong_cu = _doc_de_xuat(ctx.project)

        tom_tat = [
            f"{c.id} · {c.device}/{c.peripheral} · {c.status} · {c.source}"
            for c in ctx.kb.datasheets.all()
        ]
        tom_tat += [
            f"công cụ {dx.name} ≥{dx.min_version or '?'} · {dx.scope} · "
            f"phục vụ {', '.join(dx.gates) or '—'}"
            for dx in cong_cu
        ]

        # Thủ tục theo ngoại vi cũng là TRI THỨC, nên nó lên đúng cửa này
        # chứ không có lệnh duyệt riêng (V4). Người duyệt thấy đủ thứ sắp được
        # ghi vào kho, trong một hồ sơ.
        thu_tuc = _kho_thu_tuc(ctx.project).cho_duyet()
        tom_tat += [
            f"thủ tục {k.id} · {k.peripheral} · {len(k.thu_tu)} bước · "
            f"{len(k.bay)} bẫy · {k.status}"
            for k in thu_tuc
        ]

        chi_tiet = [f"### {c.id}\n{c.body}" for c in de_xuat]
        chi_tiet += [dx.render() for dx in cong_cu]
        chi_tiet += [k.render() for k in thu_tuc]

        return GatePayload(
            gate_id="G2",
            options=phuong_an,
            title="Duyệt trích đoạn tài liệu và công cụ vào kho tri thức",
            summary=tuple(tom_tat),
            details="\n\n".join(chi_tiet) or
            "(không có chunk hay công cụ nào đang chờ duyệt)",
            content_digest="sha256:" + __import__("hashlib").sha256(
                "|".join(
                    sorted(c.id + c.status for c in ctx.kb.datasheets.all())
                    + sorted(dx.digest_line for dx in cong_cu)
                    + sorted(k.id + k.status for k in thu_tuc)
                ).encode()
            ).hexdigest(),
        )
    if gate_id == "G4":
        return _ho_so_G4(ctx, state)
    if gate_id == "G5":
        return _ho_so_G5(ctx, state)

    raise CliError(
        f"Gate {gate_id} chưa có hồ sơ nào đang chờ và engine chưa biết cách dựng "
        "hồ sơ cho nó."
    )


def _ho_so_G4(ctx: AppContext, state: Any) -> Any:
    """Hồ sơ nghiệm thu vật lý — thứ kỹ sư cầm theo khi ra chỗ thiết bị.

    Cố ý liệt kê TIÊU CHÍ trước, số đo sau: G4 không phải chỗ xem lại mã, mà là
    chỗ đối chiếu hành vi thật với ngưỡng đã chốt từ công đoạn A1. Nếu hồ sơ mở
    đầu bằng diff thì người duyệt sẽ đọc mã, và đó đúng là việc của G3.
    """
    from eaa.gates import GatePayload

    nghiem_thu = ctx.kb.constraints.acceptance
    module = state.current_module or (
        state.backlog[-1].id if state.backlog else "(không rõ module)"
    )
    commit = ctx.repo.head()

    tieu_chi = [f"Dung sai góc: ±{nghiem_thu.get('tilt_tolerance_deg', '?')}°"]
    tieu_chi += [f"Kịch bản: {k}" for k in (nghiem_thu.get("scenarios") or [])]
    for ten, gia_tri in sorted(ctx.kb.constraints.limits.items()):
        if ten.endswith(("_max", "_min")):
            tieu_chi.append(f"{ten}: {gia_tri}")

    return GatePayload(
        gate_id="G4",
        title=f"Nghiệm thu vật lý — {module}",
        module=module,
        summary=(
            f"commit đưa lên thiết bị: {commit[:10]}",
            f"môi trường công cụ: {state.env_hash or '(chưa khóa)'}",
            *tieu_chi,
        ),
        details=(
            "TIÊU CHÍ NGHIỆM THU (chốt từ công đoạn A1, không thương lượng tại đây)\n"
            + "\n".join(f"  • {t}" for t in tieu_chi)
            + "\n\nSau khi duyệt gate này, nhập số đo bằng:\n"
            f"  eaa tune {module} --input measures.yaml\n\n"
            "Không đạt thì ghi nhận và quay lui:\n"
            f"  eaa tune {module} --reject '<lý do>'\n"
            f"  eaa rollback {module} --reason '<lý do>'"
        ),
        checklist=(
            "Robot đã kê an toàn trước khi cấp nguồn động lực",
            "Firmware đang nạp đúng commit ghi ở trên",
            "Đã chạy đủ ba kịch bản của đề cương, không bỏ kịch bản nào",
            "Số đo ghi lại từ thiết bị đo, không ước lượng bằng mắt",
        ),
        content_digest=f"sha256:{commit}",
    )


def _ho_so_G5(ctx: AppContext, state: Any) -> Any:
    """Hồ sơ duyệt kết luận — kết thúc dự án.

    Gom số liệu để người viết kết luận nhìn thấy toàn cảnh: bao nhiêu module đã
    nghiệm thu, bao nhiêu lần quay lui, chi phí token. Diễn giải kết quả vẫn là
    trách nhiệm học thuật của tác giả (công đoạn F1) — engine chỉ bày số liệu.
    """
    from eaa.gates import GatePayload
    from eaa.kpi import KpiLogger
    from eaa.llm.calllog import CallLog

    kpi = KpiLogger(ctx.project / "kpi_log.csv")
    goi = CallLog(ctx.project / "llm_calls.jsonl")
    kho_pb = _tao_versions(ctx.project, ctx.repo)

    tom_tat_kpi = kpi.summary()
    tom_tat_goi = goi.summary()

    return GatePayload(
        gate_id="G5",
        title="Duyệt kết luận đề án",
        summary=(
            f"module đã merge: {len([m for m in state.backlog if m.status == 'merged'])}"
            f"/{len(state.backlog)}",
            f"dòng chỉ số: {tom_tat_kpi.get('rows', 0)}",
            f"lời gọi mô hình: {tom_tat_goi.get('calls', 0)}"
            f" ({tom_tat_goi.get('tokens_in_total', 0)} token vào)",
            f"mô hình đã dùng: {', '.join(tom_tat_goi.get('models', [])) or '—'}",
            f"prompt bị trôi hành vi: {tom_tat_goi.get('drifted_prompts', 0)}",
        ),
        details=kho_pb.report(),
        checklist=(
            "Số liệu Chương 3 xuất được từ kpi_log.csv",
            "Mọi commit truy vết được về prompt, mô hình và phiên bản ràng buộc",
            "Nhật ký gate chứng minh không gate nào bị vượt tự động",
            "Sổ sai lệch thiết kế đã gom vào bản cập nhật tài liệu",
        ),
        content_digest="sha256:" + __import__("hashlib").sha256(
            (kho_pb.report() + str(tom_tat_kpi)).encode("utf-8")
        ).hexdigest(),
    )


def _bang_gate(ctx: AppContext, state: Any) -> list[dict[str, Any]]:
    """Toàn cảnh 5 gate cho một bảng trong biên tập (E3).

    Mỗi gate mang theo QUYẾT ĐỊNH GẦN NHẤT, và với lần từ chối thì mang cả lý
    do nguyên văn. Đó là thứ E2 đã đo được: 21 trong 22 phát hiện đang mở là lý
    do người từ chối tại gate, và chúng không có `file:line` nào — nên bảng
    gate, chứ không phải gạch đỏ, mới là mặt tiếp xúc chính của sản phẩm này.
    """
    ra: list[dict[str, Any]] = []
    for gate in GATE_ORDER:
        try:
            gan_nhat = ctx.gates.latest(gate)
        except Exception:  # noqa: BLE001 - sổ hỏng không được chặn bản tóm tắt
            gan_nhat = None
        muc: dict[str, Any] = {
            "id": gate,
            "purpose": GATE_PURPOSE[gate],
            "status": state.gate_status(gate),
            "label": _nhan_gate(state, gate),
            "last_decision": None,
        }
        if gan_nhat is not None:
            muc["last_decision"] = {
                "decision": gan_nhat.decision,
                "actor": gan_nhat.actor,
                "at": gan_nhat.decided_at,
                "module": gan_nhat.module,
                "reason": gan_nhat.reason,
                "payload_digest": gan_nhat.payload_digest,
                # Ba trạng thái, và None nghĩa là KHÔNG KIỂM ĐƯỢC — quyết định
                # ghi trước khi trường này tồn tại. Đọc None thành False là
                # khai một điều ta không biết (SL-185).
                "digest_asserted": gan_nhat.digest_asserted,
            }
        ra.append(muc)
    return ra


def _duyet_mu(ctx: AppContext) -> dict[str, int]:
    """Đếm quyết định duyệt KHÔNG khẳng định dấu vân tay.

    Không phải lỗi, và không được hiện thành lỗi. Nó là một SỐ ĐO về cách quy
    trình đang được vận hành, và nó chỉ có nghĩa khi ba trạng thái đứng riêng.
    """
    co = khong = khong_biet = 0
    try:
        for d in ctx.gates.decisions():
            if d.decision != "approved":
                continue
            if d.digest_asserted is None:
                khong_biet += 1
            elif d.digest_asserted:
                co += 1
            else:
                khong += 1
    except Exception:  # noqa: BLE001
        pass
    return {"asserted": co, "blind": khong, "unknown": khong_biet}


def _gate_show(ctx: AppContext, args: argparse.Namespace) -> int:
    from eaa import jsonout

    cho_duyet = ctx.gates.pending(args.gate)
    if cho_duyet:
        for yeu_cau in cho_duyet:
            _in_tieu_de(f"Đang chờ quyết định — {yeu_cau.payload.gate_id}")
            print(yeu_cau.payload.render())
        jsonout.ket_qua(gates=_bang_gate(ctx, ctx.store.load()),
                        digest_use=_duyet_mu(ctx),
                        pending=[
            {"gate": y.payload.gate_id, "title": y.payload.title,
             "summary": list(y.payload.summary),
             "checklist": list(y.payload.checklist),
             # Dấu vân tay nội dung PHẢI đi ra: lớp IDE duyệt gate thì nó duyệt
             # đúng nội dung này, và không có dấu vân tay thì không kiểm được.
             "content_digest": y.payload.content_digest}
            for y in cho_duyet
        ])
        return EXIT_WAITING_GATE

    if args.gate:
        payload = _ho_so_gate(ctx, args.gate)
        _in_tieu_de(f"Hồ sơ dựng từ dữ liệu hiện hành — {args.gate}")
        print(payload.render())
        jsonout.ket_qua(gates=_bang_gate(ctx, ctx.store.load()),
                        digest_use=_duyet_mu(ctx), pending=[], draft={
            "gate": payload.gate_id, "title": payload.title,
            "summary": list(payload.summary),
            "checklist": list(payload.checklist),
            "content_digest": payload.content_digest,
        })
        return EXIT_WAITING_GATE

    state = ctx.store.load()
    _in_tieu_de("Trạng thái các Human Gate")
    for gate in GATE_ORDER:
        print("  " + _nhan_gate(state, gate))
    print("\nKhông có hồ sơ nào đang chờ quyết định.")

    from eaa import jsonout

    mu = _duyet_mu(ctx)
    if mu["blind"] or mu["unknown"]:
        print(f"\nDuyệt có khẳng định nội dung: {mu['asserted']} · "
              f"không khẳng định: {mu['blind']} · không kiểm được: "
              f"{mu['unknown']}")
        print("  (KHÔNG KIỂM ĐƯỢC là quyết định ghi trước khi trường này tồn "
              "tại — khác với 'không khẳng định'.)")

    jsonout.ket_qua(
        pending=[],
        gates=_bang_gate(ctx, state),
        digest_use=mu,
    )
    return EXIT_OK


def _gate_approve(ctx: AppContext, args: argparse.Namespace) -> int:
    from eaa.gates import GateNotPending
    from eaa.vcs import MERGE_GATE

    nguoi = args.actor or _nguoi_dung()

    try:
        quyet_dinh = ctx.gates.approve(
            args.gate, actor=nguoi, expect_digest=args.expect, option=args.option
        )
    except GateNotPending:
        payload = _ho_so_gate(ctx, args.gate)
        print(payload.render())
        ctx.gates.request(payload)
        quyet_dinh = ctx.gates.approve(
            args.gate, actor=nguoi, expect_digest=args.expect, option=args.option
        )

    print(f"\n{args.gate} đã được {nguoi} phê duyệt lúc {quyet_dinh.decided_at}.")

    if quyet_dinh.chosen_option:
        from eaa.options import OPTIONS_FILE, OptionSet

        da_chon = quyet_dinh.options.get(quyet_dinh.chosen_option)
        print(f"Phương án đã chọn: [{da_chon.id}] {da_chon.title}")
        bi_loai = [o.id for o in quyet_dinh.options.options if o.id != da_chon.id]
        print(
            f"Phương án bị loại đã lưu vào quyết định: {', '.join(bi_loai)}\n"
            "  (sáu tháng sau, câu hỏi hữu ích là 'đã cân nhắc những gì', không "
            "chỉ 'đã chọn gì')"
        )
        OptionSet.clear(ctx.project / OPTIONS_FILE, args.gate)

    if args.gate == "G1":
        _ghim_lai_rang_buoc(ctx)

    if args.gate == MERGE_GATE:
        return _sau_khi_duyet_G3(ctx, quyet_dinh)

    if args.gate == "G2":
        # Trích đoạn tài liệu vào kho. Đây là đường mà SL-117 phát hiện là
        # CHƯA TỪNG TỒN TẠI: `datasheet add` sinh chunk 'proposed' rồi chỉ
        # người dùng sang đúng lệnh này, và lệnh này không đụng tới chunk.
        de_xuat = [c for c in ctx.kb.datasheets.all() if not c.is_active]
        if de_xuat:
            print("\nTrích đoạn đã vào kho tri thức:")
            for c in de_xuat:
                ctx.kb.datasheets.approve(c.id, by=nguoi)
                print(f"  {c.id} · {c.device}/{c.peripheral} · {c.source}")
            print("  Từ giờ chúng truy xuất được vào prompt sinh mã.")

        cong_cu = _doc_de_xuat(ctx.project)
        if cong_cu:
            da_ghi = _ghi_de_xuat_vao_manifest(ctx.project, cong_cu, actor=nguoi)
            print("\nCông cụ đã vào manifest:")
            for dong in da_ghi:
                print(f"  {dong}")
            print("Cài được rồi: eaa doctor --fix")

    return _thu_chuyen_pha(ctx)


def _pham_vi_bang_kiem() -> str:
    """Nói rõ bảng kiểm sẵn sàng KHÔNG phủ được cái gì.

    Bảng kiểm đi theo cạnh ``ngoại vi –configured_by→ thanh ghi`` của Knowledge
    Graph, mà ``configured_by`` là một danh sách VIẾT TAY trong hồ sơ phần
    cứng. Nên nó trả lời đúng câu nó hỏi — *"có tài liệu cho những thanh ghi
    đã khai không"* — trong khi người đọc hiểu nó là *"module này sinh mã được
    chưa"*. Hai câu ấy khác nhau, và khoảng cách giữa chúng là những thanh ghi
    không ai nghĩ tới.

    Đo được ở Bài 1 phiên kiểm bo thật: bảng kiểm báo THIẾU 0 cho một module
    cổng nối tiếp, rồi vòng sinh mã kết luận không hiện thực được hàm truyền vì
    thiếu tài liệu thanh ghi dữ liệu — một thanh ghi không có trong
    ``configured_by``.

    Không thể làm phép kiểm toàn tri; nhưng nói đúng phạm vi mình phủ thì làm
    được, và đó là khác biệt giữa một phép kiểm hữu ích và một phép kiểm gây
    hiểu nhầm.
    """
    return (
        "\n  Phạm vi bảng kiểm này: nó đi theo `configured_by` của hồ sơ phần\n"
        "  cứng — một danh sách do người VIẾT TAY. Thanh ghi nào không ai khai\n"
        "  ở đó thì không ai thấy nó thiếu, kể cả bảng này. 'THIẾU 0' nghĩa là\n"
        "  'không thiếu trong số đã khai', không phải 'không thiếu gì'."
    )


def _ghim_lai_rang_buoc(ctx: AppContext) -> None:
    """Sau khi người duyệt G1, ghim băm ràng buộc HIỆN HÀNH vào Project State.

    Đây chính là việc G1 mang tên: *chốt ràng buộc cứng*. Trước SL-113,
    ``constraints_version`` chỉ được ghi MỘT lần ở ``eaa init`` và không đường
    nào chốt lại — nên ``eaa status`` cảnh báo trôi băm, chỉ sang
    ``eaa gate approve G1``, người duyệt G1, và cảnh báo vẫn còn nguyên. Lệnh
    chỉ sang một cánh cửa không tồn tại.

    Ghim ở đây là AN TOÀN chứ không phải tiện: hồ sơ G1 mà người vừa đọc CHỨA
    nội dung ràng buộc, và quyết định của họ neo vào băm hồ sơ ấy. Ta ghi lại
    băm của đúng thứ họ vừa duyệt.

    Cố ý KHÔNG có lệnh riêng để ghim: một lệnh "chấp nhận băm mới" tách rời
    khỏi việc đọc hồ sơ chính là lối tắt mà thiết kế cấm — nó biến một quyết
    định thành một thao tác dọn cảnh báo.
    """
    from eaa.kb import Constraints, HardwareProfile

    tep = ctx.project / "constraints.yaml"
    if not tep.is_file():
        return
    try:
        bam = Constraints.load(tep).content_version
    except Exception as exc:  # noqa: BLE001 - tệp hỏng thì nói ra, không im
        print(f"\n  Không đọc lại được constraints.yaml để ghim băm: {exc}")
        return

    # Hồ sơ phần cứng chốt cùng lúc, vì người vừa đọc cả hai trong một hồ sơ.
    bam_pc = ""
    hs = ctx.project / HARDWARE_PROFILE_FILE
    if hs.is_file():
        try:
            bam_pc = HardwareProfile.load(hs).content_version
        except Exception as exc:  # noqa: BLE001
            print(f"\n  Không đọc lại được hardware_profile.yaml để ghim băm: {exc}")
            return

    state = ctx.store.load()
    if state.constraints_version == bam and state.hardware_version == bam_pc:
        return
    cu, cu_pc = state.constraints_version, state.hardware_version
    ctx.store.save(
        replace(state, constraints_version=bam, hardware_version=bam_pc)
    )
    if cu != bam:
        print(
            f"\nBăm ràng buộc đã chốt lại: {bam}\n"
            f"  (trước đó {cu or '(chưa có)'} — băm này đi vào commit message làm "
            "bằng chứng xuất xứ, NFR-07)"
        )
    if cu_pc != bam_pc:
        print(
            f"\nBăm hồ sơ phần cứng đã chốt lại: {bam_pc}\n"
            f"  (trước đó {cu_pc or '(chưa có)'} — từ đây, sửa một chân là làm"
            " trôi băm này và eaa status sẽ đòi duyệt lại)"
        )


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


def _tep_tai_lieu(nguon: str, project: Path) -> Path:
    """Nhận đường dẫn tệp HOẶC URL, trả về một tệp trên đĩa.

    Vì sao URL phải đi qua ``eaa/web.py``
    --------------------------------------

    Trước bản này lệnh chỉ nhận tệp cục bộ. Nghe có vẻ chặt hơn, thực ra là
    lỏng hơn — và lỏng ở đúng chỗ quan trọng nhất:

    ``eaa read`` từ chối PDF và chỉ người dùng sang ``eaa datasheet add``.
    Nhưng lệnh ấy không nhận URL, nên người dùng phải tự tải tệp về bằng trình
    duyệt. Việc tải ấy nằm NGOÀI ``eaa/web.py``, nên **không có phân hạng nguồn
    nào xảy ra**: một bản PDF lấy từ một trang chia sẻ tài liệu bất kỳ vào kho
    tri thức y hệt một bản lấy từ miền nhà sản xuất, và không gì ghi lại sự
    khác biệt.

    Nói cách khác: cả hệ thống hai hạng nguồn bị đi vòng qua bởi đúng con
    đường duy nhất thật sự nạp tri thức. Đưa URL vào đây đóng lỗ ấy.

    Lệnh vẫn là lệnh CỦA NGƯỜI (G2, AIS §4.1) — chọn tệp và chọn trang là việc
    của kỹ sư. Cái thêm vào là chỗ tải, không phải quyền duyệt.
    """
    from eaa.web import CHINH_CHU, WebError, WebFetcher

    if not nguon.lower().startswith(("http://", "https://")):
        return Path(nguon)

    try:
        noi_dung, doc = WebFetcher(cache=None).fetch_binary(nguon)
    except WebError as exc:
        raise CliError(f"Không tải được {nguon}: {exc}") from None

    if doc.tier != CHINH_CHU:
        raise CliError(
            f"{doc.url} thuộc hạng {doc.tier!r}, không phải nguồn chính chủ.\n"
            "  Chỉ tài liệu từ miền nhà sản xuất mới được thành trích đoạn tri\n"
            "  thức — một bản sao trên trang chia sẻ tài liệu có thể đã bị sửa,\n"
            "  và ta kiểm được nguồn chứ không kiểm được nội dung.\n"
            "  Tìm bản trên miền nhà sản xuất; hoặc nếu bạn ĐÃ tự đối chiếu bản\n"
            "  này với bản gốc thì tải về rồi nêu đường dẫn tệp."
        )

    from urllib.parse import urlparse

    dich = project / "datasheets" / "_taive"
    dich.mkdir(parents=True, exist_ok=True)
    ten = Path(urlparse(doc.url).path).name or "tai_lieu.pdf"
    tep = dich / ten
    tep.write_bytes(noi_dung)
    print(f"Đã tải {len(noi_dung):,} byte từ {doc.url}".replace(",", "."))
    print(f"  hạng nguồn: {doc.tier}  ·  lưu tại {tep}")
    return tep


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
        nguon_tep = _tep_tai_lieu(args.file, project)
        try:
            de_xuat = PdfIngestor(
                datasheets_dir=project / "datasheets",
                registry=SourceRegistry(project / "sources.jsonl"),
            ).ingest(
                str(nguon_tep),
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
        from eaa.ingest import canh_bao_ten_chung

        canh = canh_bao_ten_chung(de_xuat.registers)
        if canh:
            print(canh)
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
    # Nhu cầu công cụ SUY TỪ pack; manifest chỉ ghi thứ đã được người duyệt.
    pack = load_manifest(goc / "packs" / rang_buoc.platform)

    researcher = None
    store = StateStore(project / STATE_FILE)
    if store.exists():
        try:
            llm = _tao_llm(store.load(), project)
            if getattr(llm, "provider", "") not in ("mock", "replay"):
                from eaa.toolsearch import LlmToolResearcher

                researcher = LlmToolResearcher(llm=llm)
        except CliError:
            researcher = None

    from eaa.doctor import InstallApprovals

    return Doctor(
        manifest=manifest,
        tools_kb=project / "tools_kb",
        env_lock=EnvLock(project / "env_lock.json"),
        approvals=InstallApprovals(project / "install_approvals.jsonl"),
        confirm=_hoi_xac_nhan_cai,
        pack_manifest=pack,
        researcher=researcher,
    )


def _hoi_xac_nhan_cai(ten: str, lenh: str) -> bool | None:
    """Hỏi người trước mỗi lệnh cài. Không có terminal thì KHÔNG đồng ý.

    Cùng nguyên tắc với Human Gate: một phiên không có người không được diễn
    giải thành một người đã đồng ý (FR-ENV-02, §9.4).

    Trả ``None`` chứ không phải ``False`` khi không có terminal. Kết cục an
    toàn giống hệt nhau — không cài — nhưng **lý do** thì khác hẳn, và bên gọi
    in lý do ra cho người đọc. Trả ``False`` ở đây làm lệnh khai *"người dùng
    từ chối"* trong khi không có ai được hỏi cả: kỹ sư sẽ đi tìm xem ai đã từ
    chối, hoặc đọc thành "đã có người quyết định không cài" rồi đi tiếp.
    """
    if not sys.stdin.isatty():
        return None
    print(f"\n  Sắp chạy để cài {ten}:\n    {lenh}")
    return input("  Đồng ý chạy lệnh này? [y/N]: ").strip().lower() in ("y", "yes", "c", "có")


def _doctor_plan(doctor: Any, bao_cao: Any) -> int:
    """Kế hoạch cài: thứ tự, cách cài, và chỗ đá nhau (C2.9, C4.1, C4.3)."""
    from eaa.doctor import _os_key
    from eaa.installplan import CircularDependency, plan_installs

    specs = [k.spec for k in bao_cao]
    da_co = {k.spec.name for k in bao_cao if not k.blocking}
    try:
        ke_hoach = plan_installs(specs, os_key=_os_key(), present=da_co)
    except CircularDependency as exc:
        raise CliError(str(exc)) from None

    _in_tieu_de("Kế hoạch cài")
    print(ke_hoach.render())
    if ke_hoach.blocked:
        return EXIT_ENV_ERROR
    return EXIT_OK if not ke_hoach.todo else EXIT_WAITING_GATE


def _doctor_approve(project: Path, doctor: Any, args: argparse.Namespace) -> int:
    """Người duyệt lệnh cài. KHÔNG nằm trong danh mục Agent tự gọi.

    Duyệt cái gì thì phải nhìn thấy cái đó: lệnh được in nguyên văn TRƯỚC khi
    ghi vào sổ. Quyết định neo vào chính dãy đối số ấy, nên manifest đổi sau đó
    là quyết định cũ hết hiệu lực — cùng tính chất mà Human Gate giữ bằng
    ``content_digest``.
    """
    from eaa.doctor import DoctorError

    ai = (args.actor or os.environ.get("USER", "")).strip()
    if not ai:
        raise CliError(
            "Phải ghi ai duyệt: thêm --actor <tên bạn>. Một quyết định không "
            "có người chịu trách nhiệm thì không phải quyết định của con người."
        )

    _in_tieu_de("Duyệt lệnh cài")
    da_duyet = []
    for ten in args.tools:
        spec = doctor.manifest.get(ten)
        if spec is None:
            raise CliError(
                f"Manifest không có công cụ {ten!r}. Chạy 'eaa doctor' để xem "
                "danh sách đúng tên."
            )
        try:
            lenh = doctor.install_steps(spec)
        except DoctorError as exc:
            raise CliError(str(exc)) from None
        k = doctor.approvals.approve(ten, lenh, by=ai)
        da_duyet.append(k)
        # In TỪNG bước: người duyệt phải nhìn thấy đủ những gì sẽ chạy, kể cả
        # bước thêm kho gói — đó thường là bước đáng cân nhắc nhất.
        print(f"  {ten}:")
        for b in lenh:
            print(f"      {' '.join(b)}")

    print(f"\nĐã ghi {len(da_duyet)} quyết định — {ai}.")
    print("Lệnh cài chạy được từ giờ:  eaa doctor --fix")
    print(
        "Quyết định neo vào ĐÚNG dãy đối số trên. Manifest đổi lệnh cài thì "
        "quyết định này hết hiệu lực và phải duyệt lại."
    )
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    from eaa.doctor import DoctorError, InstallNotConfirmed, ToolStatus

    project = resolve_project(args.project)
    doctor = _tao_doctor(project)

    if getattr(args, "action", None) == "approve":
        if not args.tools:
            raise CliError(
                "Duyệt cái gì? Cú pháp: eaa doctor approve <công cụ>... --actor <tên bạn>\n"
                "Chạy 'eaa doctor' để xem công cụ nào đang thiếu."
            )
        return _doctor_approve(project, doctor, args)

    if args.discover:
        return _doctor_discover(project, doctor, args)

    bao_cao = doctor.scan()

    if getattr(args, "plan", False):
        return _doctor_plan(doctor, bao_cao)

    _in_tieu_de("Môi trường công cụ")
    print(doctor.render_scan(bao_cao))

    chua_biet = doctor.discover()
    if chua_biet:
        _in_tieu_de("Công cụ pack sẽ gọi mà manifest chưa biết")
        print(doctor.render_discovery(chua_biet))

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
                # Phần việc đã ghi trước lúc dừng vẫn phải tới được người —
                # họ quay lại là để duyệt đúng những lệnh này.
                for dong in exc.nhat_ky:
                    print(f"  {dong}")
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


def _doctor_discover(project: Path, doctor: Any, args: argparse.Namespace) -> int:
    """Chế độ 3 của AIS §9.2 — phát hiện, tra cứu, đề xuất qua gate."""
    from eaa.doctor import DoctorError
    from eaa.toolsearch import ToolSearchError, UnsafeInstallSource

    chua_biet = doctor.discover()
    _in_tieu_de("Phát hiện nhu cầu công cụ")
    print(doctor.render_discovery(chua_biet))

    if not chua_biet or not args.propose:
        return EXIT_OK if not chua_biet else EXIT_WAITING_GATE

    de_xuat: list[Any] = []
    for yc in chua_biet:
        _in_tieu_de(f"Tra cứu {yc.program}")
        try:
            dx = doctor.research(yc)
        except UnsafeInstallSource as exc:
            print(f"  ĐỀ XUẤT BỊ TỪ CHỐI — {exc}")
            continue
        except (ToolSearchError, DoctorError) as exc:
            print(f"  Không tra cứu được: {exc}")
            continue
        print(dx.render())
        de_xuat.append(dx)

    if not de_xuat:
        raise CliError(
            "Không có đề xuất nào qua được kiểm an toàn. Cài tay theo hướng dẫn "
            "của nhà phát hành, rồi chạy lại 'eaa doctor'."
        )

    _luu_de_xuat(project, de_xuat)
    print()
    print(
        f"{len(de_xuat)} đề xuất đã ghi lại và đang CHỜ DUYỆT. Đề xuất là "
        "proposed fact — chưa vào manifest, nên chưa cài được.\n"
        "  Xem lại rồi duyệt: eaa gate approve G2"
    )
    return EXIT_WAITING_GATE


def _duong_dan_de_xuat(project: Path) -> Path:
    return project / ".eaa" / "tool_proposals.json"


def _luu_de_xuat(project: Path, de_xuat: Sequence[Any]) -> None:
    """Ghi đề xuất đang chờ duyệt — dạng đầy đủ, khôi phục lại được.

    Đề xuất phải sống qua khoảng giữa lúc tra cứu và lúc người duyệt, và thứ
    được ghi vào manifest phải đúng thứ đã trình lên. Vì vậy lưu nguyên đề
    xuất chứ không lưu bản rút gọn cho người đọc.
    """
    import json as _json

    path = _duong_dan_de_xuat(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _json.dumps([dx.to_dict() for dx in de_xuat], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _doc_de_xuat(project: Path) -> list[Any]:
    """Đề xuất công cụ đang chờ duyệt, nếu có."""
    import json as _json

    from eaa.toolsearch import ToolProposal

    path = _duong_dan_de_xuat(project)
    if not path.is_file():
        return []
    try:
        du_lieu = _json.loads(path.read_text(encoding="utf-8"))
    except _json.JSONDecodeError as exc:
        raise CliError(f"{path}: hồ sơ đề xuất công cụ hỏng — {exc}") from exc
    return [ToolProposal.from_dict(d) for d in du_lieu]


def _ghi_de_xuat_vao_manifest(
    project: Path, de_xuat: Sequence[Any], *, actor: str
) -> list[str]:
    """Sau khi người duyệt: đề xuất vào manifest, append + supersede.

    Manifest của pack và của engine là hai tệp khác nhau; ``scope`` của đề xuất
    quyết định nó thuộc bên nào. Một công cụ chỉ pack AVR mới gọi mà nằm ở
    manifest engine sẽ thành điều kiện bắt buộc cho mọi dự án, kể cả dự án
    dùng nền khác — đúng thứ kiến trúc ba tầng dựng ra để tránh.
    """
    from eaa.toolsearch import append_to_manifest

    goc = repo_root()
    da_ghi: list[str] = []
    for dx in de_xuat:
        if dx.scope.startswith("pack:"):
            duong_dan = goc / "packs" / dx.scope.split(":", 1)[1] / "tools.yaml"
        else:
            duong_dan = goc / "tools.yaml"
        append_to_manifest(duong_dan, dx, actor=actor)
        da_ghi.append(f"{dx.name} → {duong_dan.relative_to(goc)}")

    # Đã vào manifest thì không còn là đề xuất chờ duyệt. Bản ghi không mất:
    # mục manifest mang theo approved_by/approved_at, và mục cũ trùng tên được
    # đánh dấu superseded_by chứ không bị xóa.
    _duong_dan_de_xuat(project).unlink(missing_ok=True)
    return da_ghi


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


def _kho_thu_tuc(project: Path) -> Any:
    """Kho thủ tục gộp từ Platform Pack và dự án (V4).

    Hỏng thì trả kho RỖNG chứ không ném: một tệp thủ tục viết sai không được
    chặn đường sinh mã, nó chỉ được làm lớp K9 vắng mặt. `eaa procedure lint`
    là chỗ nói ra tệp nào sai.
    """
    from eaa.procedure import KhoKyNang

    nguon = [project / PROCEDURE_DIR]
    pack = _thu_muc_pack(project)
    if pack:
        nguon.insert(0, pack / PROCEDURE_DIR)
    try:
        return KhoKyNang.nap_nhieu(*nguon)
    except Exception:  # noqa: BLE001
        return KhoKyNang()


def _thu_muc_pack(project: Path) -> Path | None:
    """Thư mục Platform Pack của dự án, nếu tra được."""
    import yaml

    try:
        d = yaml.safe_load((project / CONSTRAINTS_FILE).read_text()) or {}
        # Khoá là `platform` (constraints.yaml dòng 33), không phải
        # `platform_pack`. Nhận cả hai vì đọc sai khoá ở đây thì kho thủ tục
        # của pack lặng lẽ rỗng — và một nguồn tri thức vắng mặt trong im lặng
        # là chỗ khó lần nhất.
        ten = d.get("platform") or d.get("platform_pack")
    except Exception:  # noqa: BLE001
        return None
    if not ten:
        return None
    d = Path("packs") / str(ten)
    return d if d.is_dir() else None


def cmd_problems(args: argparse.Namespace) -> int:
    """Mọi phát hiện của quy trình, ở dạng bảng lỗi của biên tập (E2).

    CHỈ ĐỌC: nó đọc bằng chứng cổng đã cất và nhật ký quyết định gate, không
    chạy lại cổng nào. Chạy cổng là việc của `eaa gen`, và nó đổi trạng thái.
    """
    from eaa.confidence import DA_KIEM, header
    from eaa.diagnostic import bang_chu, gom
    from eaa import jsonout

    project = resolve_project(args.project)
    kq = gom(project, module=[args.module] if getattr(args, "module", "") else None)

    print(header(DA_KIEM, "Phát hiện của quy trình"))
    print()
    print(bang_chu(kq, tran=getattr(args, "limit", 0) or 0,
                   tat_ca=bool(getattr(args, "all", False))))

    ti_le = kq.ti_le_co_vi_tri
    print()
    if ti_le is None:
        # CHƯA ĐO ĐƯỢC khác BẰNG KHÔNG: chưa phát hiện nào thì tỉ lệ ấy không
        # tồn tại, và in 0% là khai một con số chưa đo.
        print("  Tỉ lệ có vị trí: CHƯA ĐO ĐƯỢC (chưa phát hiện nào)")
    else:
        print(f"  {len(kq.co_vi_tri)}/{len(kq.hien_tai)} phát hiện ĐANG MỞ vẽ được "
              f"gạch đỏ "
              f"đúng dòng ({ti_le:.0%})")
        print("  Số còn lại KHÔNG có vị trí — phần lớn là lỗi thiết kế người "
              "bắt ở gate,")
        print("  và đó đúng là hạng lỗi làm robot ngã. Chúng vẫn hiện, neo vào "
              "tệp trạng thái.")

    jsonout.ket_qua(
        diagnostics=[c.to_dict() for c in kq.muc],
        modules_read=list(kq.module_da_doc),
        counts={
            "total": len(kq.muc),
            "current": len(kq.hien_tai),
            "historical": len(kq.muc) - len(kq.hien_tai),
            "with_position": len(kq.co_vi_tri),
            "in_source": kq.so_trong_nguon,
        },
    )
    return EXIT_OK


def cmd_procedure(args: argparse.Namespace) -> int:
    """Thủ tục theo ngoại vi — xem và soi (V4, K9).

    KHÔNG có `eaa procedure approve`. Thủ tục là tri thức, và tri thức vào kho
    qua đúng một cửa: G2. Một lệnh duyệt riêng ở đây là một cửa sau, và cửa sau
    thì không ai nhớ nó tồn tại cho tới lúc có người đi qua.
    """
    from eaa.confidence import DA_KIEM, header

    project = resolve_project(args.project)
    ctx = build_context(project)
    kho = _kho_thu_tuc(project)
    muc = kho.tat_ca()
    if not muc:
        print("Chưa có thủ tục nào. Đặt tệp YAML vào "
              f"packs/<pack>/{PROCEDURE_DIR}/ hoặc <dự án>/{PROCEDURE_DIR}/.")
        return EXIT_OK

    if getattr(args, "procedure_action", None) == "lint":
        co_that = {c.id for c in ctx.kb.datasheets.all()}
        thieu = kho.chunk_thieu(co_that)
        khong_bang_chung = [k.id for k in muc if not k.co_bang_chung_that]
        if thieu:
            print("Thủ tục trỏ vào trích đoạn KHÔNG có trong kho:")
            for d in thieu:
                print(f"  - {d}")
        if khong_bang_chung:
            print("Thủ tục chưa có bẫy nào rút từ chuyện ĐÃ XẢY RA "
                  f"(mức {DA_KIEM}): {', '.join(khong_bang_chung)}")
            print("  Không phải lỗi — nhưng một thủ tục toàn bẫy nghĩ ra thì "
                  "nó là lời khuyên, không phải bằng chứng.")
        if not thieu and not khong_bang_chung:
            print("Không thấy chỗ nào đáng ngờ.")
        return EXIT_OK

    print(header(DA_KIEM, "Thủ tục theo ngoại vi (lớp K9)"))
    for k in muc:
        nhan = "đã duyệt G2" if k.da_duyet else "CHỜ DUYỆT G2 — chưa vào prompt"
        that = sum(1 for b in k.bay if b.muc == DA_KIEM)
        print(f"\n{k.id} · {k.peripheral} · {nhan}")
        print(f"  {len(k.thu_tu)} bước · {len(k.bay)} bẫy "
              f"({that} rút từ chuyện đã xảy ra)")
        if k.source:
            print(f"  nguồn: {k.source}")
    cho = kho.cho_duyet()
    if cho:
        print(f"\n{len(cho)} thủ tục chờ duyệt — `eaa gate show G2` để đọc, "
              "rồi `eaa gate approve G2`.")

    from eaa import jsonout

    jsonout.ket_qua(procedures=[
        {"id": k.id, "peripheral": k.peripheral, "status": k.status,
         "approved": k.da_duyet, "steps": list(k.thu_tu),
         "source": k.source,
         # Mức tin cậy đi qua `muc()` thành TRƯỜNG RIÊNG, không trộn vào câu.
         # Làm phẳng nó ở đây là bỏ mất đúng thứ `confidence.py` giữ (SL-182).
         "traps": [
             {"wrong": b.mo_ta, "right": b.dung_la, "source": b.xuat_xu,
              "level": b.muc}
             for b in k.bay
         ]}
        for k in muc
    ], pending_g2=[k.id for k in cho])
    return EXIT_OK


def cmd_observe(args: argparse.Namespace) -> int:
    """Module nào chưa nói được nó sống hay chết — N-912.

    Chỉ đọc và chỉ NÊU RA. Hai câu phải trả lời đều là câu của người: engine
    không biết thứ gì trên bo này người nghe được hay nhìn được, và nó không
    được phép đoán.
    """
    from eaa.confidence import DA_KIEM, header
    from eaa.observability import soi_quan_sat

    project = resolve_project(args.project)
    ctx = build_context(project)

    if getattr(args, "observe_action", None) == "set":
        if not (args.song or args.hong):
            raise CliError(
                "Phải nêu ít nhất một trong --song / --hong. Hai câu ấy là hai "
                "câu khác nhau: 'nó đang chạy' và 'nó vừa hỏng' không nhận ra "
                "bằng cùng một dấu hiệu."
            )
        with ctx.store.with_lock():
            state = ctx.store.load()
            muc = state.module(args.module_id)
            if muc is None:
                raise CliError(f"Không có module {args.module_id!r} trong backlog.")
            if args.song:
                muc.dau_hieu_song = args.song.strip()
            if args.hong:
                muc.dau_hieu_hong = args.hong.strip()
            ctx.store.save(state)
        _in_tieu_de(f"Đã khai dấu hiệu cho {args.module_id}")
        print(f"  sống: {muc.dau_hieu_song or '(chưa khai)'}")
        print(f"  hỏng: {muc.dau_hieu_hong or '(chưa khai)'}")
        return EXIT_OK

    bao_cao = soi_quan_sat(ctx.store.load().backlog, getattr(ctx.kb, "hardware", None))

    _in_tieu_de("Lỗi có kêu lên được không")
    # ĐÃ KIỂM: đây là phép đếm trên dữ liệu đã khai, không phải một suy đoán.
    # Cái nó KHÔNG nói là dấu hiệu ấy có đủ rõ trên bo hay không — câu ấy thuộc
    # về người, và bản báo cáo nói thẳng như vậy ở cuối.
    print(header(DA_KIEM))
    print()
    print(bao_cao.render())
    # Luôn thoát 0. Đây là một BÁO CÁO, không phải một cổng: thiếu dấu hiệu là
    # khoảng trống thiết kế, và chặn đường merge vì nó sẽ biến một câu hỏi hay
    # thành một thủ tục người ta tìm cách đi vòng.
    return EXIT_OK


def cmd_measured(args: argparse.Namespace) -> int:
    """Sổ số đo trên chính bo này — N-913.

    Trước SL-173, bài học từ bo chỉ tới mô hình qua LÝ DO TỪ CHỐI kỹ sư gõ tay
    ở G3: mất một lần gõ là mất hẳn. Sổ này là đường thứ hai, và là đường không
    phụ thuộc trí nhớ của ai.
    """
    from eaa.measured import MeasuredError, MeasuredStore

    project = resolve_project(args.project)
    so = MeasuredStore(project / MEASURED_FILE)

    try:
        if args.measured_action == "list":
            _in_tieu_de("Số đo trên bo")
            print(so.render())
            return EXIT_OK

        if args.measured_action == "add":
            f = so.propose(
                args.name,
                args.value,
                unit=args.unit or "",
                source=args.source or "",
                note=args.note or "",
            )
            _in_tieu_de(f"Đã ghi ĐỀ XUẤT: {f.name}")
            print(f"  {f.mot_dong()}")
            print()
            print(
                "Số đo này CHƯA vào prompt. Nó chỉ vào sau khi một người chốt:\n"
                f"  eaa measured approve {f.name} --actor '<tên bạn>'"
            )
            return EXIT_OK

        f = so.approve(args.name, actor=args.actor)
    except MeasuredError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de(f"Đã duyệt: {f.name}")
    print(f"  {f.mot_dong()}   [{f.approved_by}]")
    print()
    print(
        "Từ lượt sinh mã kế tiếp, số này nằm trong prompt kèm câu: khi số đo và\n"
        "tài liệu lệch nhau thì SỐ ĐO thắng."
    )
    return EXIT_OK


def cmd_knowledge(args: argparse.Namespace) -> int:
    """Vòng đời tri thức — N-036, và câu hỏi của N-100.

    `eaa/lifecycle.py` có đủ ba đường truy ngược và có TC-29 canh, nhưng cho
    tới SL-172 thì **không lệnh nào gọi tới nó**. Hệ quả đúng bằng cái nó sinh
    ra để chữa: sửa một trích đoạn tài liệu xong, không có cách nào hỏi *"mã
    nào bị ảnh hưởng"* — và ba module sinh trên bản sai vẫn nằm trong `main`,
    vẫn mang nhãn đã kiểm chứng.
    """
    from eaa.confidence import SUY_RA, header
    from eaa.lifecycle import KNOWLEDGE_GATE, KnowledgeLifecycle, LifecycleError

    project = resolve_project(args.project)
    ctx = build_context(project)
    vong_doi = KnowledgeLifecycle(
        datasheets=ctx.kb.datasheets,
        graph=ctx.graph,
        state_store=ctx.store,
        firmware_dir=project / "firmware",
        repo=ctx.repo,
        ledger=ctx.ledger,
    )

    try:
        if args.knowledge_action == "stale":
            _in_tieu_de(f"Mã nào dựa trên {args.chunk_id}")
            tap = vong_doi.stale_set(args.chunk_id)
            print(header(SUY_RA))
            print()
            print(
                "  Hợp của BA đường: quan hệ trong đồ thị, trích dẫn `// ref:` trong\n"
                "  mã, và trường chunk-ids của commit. Ba đường bắt ba loại lệ khác\n"
                "  nhau — nhưng đường đồ thị đọc khai báo `uses`, và một khai báo\n"
                "  thiếu thì đường ấy mù. Nên đây là SUY RA, không phải ĐÃ KIỂM."
            )
            print()
            print(tap.render())
            print()
            print("Lệnh này KHÔNG đổi gì. Muốn hạ cấp thật thì:")
            print(f"  eaa knowledge deprecate {args.chunk_id} --reason '<vì sao>'")
            return EXIT_OK

        quyet_dinh = ctx.gates.latest(KNOWLEDGE_GATE)
        if args.knowledge_action == "supersede":
            tap = vong_doi.supersede(
                args.old_id, args.new_id, reason=args.reason, decision=quyet_dinh
            )
            _in_tieu_de(f"Đã thay {args.old_id} bằng {args.new_id}")
        else:
            tap = vong_doi.deprecate(
                args.chunk_id, reason=args.reason, decision=quyet_dinh
            )
            _in_tieu_de(f"Đã hạ cấp {args.chunk_id}")
    except LifecycleError as exc:
        raise CliError(str(exc)) from exc

    print(tap.render())
    print()

    # Hạ tin cậy NGAY trong cùng lệnh, không để thành một bước rời phải nhớ gõ.
    # Cả giá trị của việc này nằm ở chỗ không module nào lặng lẽ giữ nhãn "đã
    # kiểm chứng" khi cơ sở của nhãn ấy vừa đổi; một bước rời là một bước sẽ
    # quên, và quên ở đây thì im lặng.
    da_ha = vong_doi.apply(tap)
    if da_ha:
        print(f"Đã hạ {len(da_ha)} module xuống 'stale': {', '.join(da_ha)}")
        print(
            "Chúng phải chạy lại chuỗi kiểm chứng. Hệ KHÔNG tự mở vòng sinh lại — "
            "sinh lại hay sửa tay là quyết định của bạn."
        )
    else:
        print("Không module nào trong backlog phải hạ cấp.")
    return EXIT_OK


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


def _llm_cho_truy_hoi(args: argparse.Namespace) -> Any:
    """Adapter mô hình cho bậc 2 của truy hồi — thiếu thì bỏ qua bậc ấy.

    Trả ``None`` khi không dựng được: truy hồi phẩm xuất phải chạy được cả khi
    chưa có khóa API, vì nó là lệnh người ta gõ lúc đang cần một tệp gấp.
    """
    try:
        return build_context(resolve_project(args.project)).llm
    except Exception:
        return None


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

    ung_vien = [a for a in kho.all() if a.id == args.what]
    bac = "tu-khoa"
    if not ung_vien:
        ung_vien, bac = kho.find_smart(
            args.what,
            llm=_llm_cho_truy_hoi(args),
            kind=args.type or None,
            on_date=args.date or "",
        )
    if not ung_vien:
        raise CliError(f"Không tìm thấy phẩm xuất khớp {args.what!r}.")
    if bac == "mo-hinh":
        print(
            "  [mô hình đoán] Không phẩm xuất nào khớp đúng chữ bạn gõ; danh sách\n"
            "  dưới đây là phỏng đoán về ý bạn. Đối chiếu tiêu đề trước khi dùng.\n"
        )
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
# AIS §8.4 — phiên bản mã, known-good, quay lui
# --------------------------------------------------------------------------


def _tao_versions(project: Path, repo: Any = None) -> Any:
    from eaa.versions import VersionRegistry

    return VersionRegistry(
        ledger_path=project / "build_ledger.jsonl",
        lock_path=project / "known_good.lock",
        repo=repo,
    )


def cmd_build(args: argparse.Namespace) -> int:
    """Ráp các module đã merge thành firmware nạp được — công đoạn E."""
    from eaa.budget import ResourceBudget
    from eaa.firmware import ASSEMBLY_FILE, AssemblyPlan, FirmwareAssembler, FirmwareError
    from eaa.tools.compile import SizeGate

    project = resolve_project(args.project)
    ctx = build_context(project)
    state = ctx.store.load()

    try:
        plan = AssemblyPlan.load(project / ASSEMBLY_FILE)
    except FirmwareError as exc:
        raise CliError(str(exc)) from exc

    da_merge = [m.id for m in state.backlog if m.status == "merged"]
    if not da_merge:
        raise CliError(
            "Chưa module nào được merge, nên chưa có gì để ráp.\n"
            "Firmware chỉ gồm mã đã qua đủ cổng và đã được duyệt tại G3 — "
            "không có đường nào khác đưa mã vào ảnh nạp xuống thiết bị.",
            EXIT_WAITING_GATE,
        )

    try:
        plan.check_against_merged(da_merge)
    except FirmwareError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Ráp firmware")
    print(f"  Bản thiết kế : {plan.path}")
    print(f"  Module        : {len(plan.modules)} ({len(plan.scheduled)} chạy định kỳ)")
    for m in plan.modules:
        nhip = f"mỗi {m.period_ms} ms" if m.scheduled else "không chạy định kỳ"
        print(f"    {m.id:<24} {nhip}")

    bao_cao = FirmwareAssembler(
        runner=ctx.runner,
        source_dir=project / "firmware",
        size_gate=SizeGate(
            ctx.runner,
            limits=ctx.kb.constraints.limits,
            # Ở tầm firmware, bản chia ngân sách còn dùng để SUY RA khoảng trống
            # ngăn xếp (N-071) — thứ không công cụ nào in ra sẵn.
            budget=ResourceBudget.from_constraints(ctx.kb.constraints),
        ),
    ).run(plan)

    print()
    if not bao_cao.passed:
        cong_doan = bao_cao.metrics.get("stage", "ráp")
        print(f"KHÔNG RÁP ĐƯỢC — dừng ở công đoạn {cong_doan}.")
        for loi in bao_cao.errors[:20]:
            vi_tri = f"{loi.file}:{loi.line}: " if loi.file else ""
            print(f"  {vi_tri}{loi.message}")
        if bao_cao.metrics.get("config_error"):
            return EXIT_ENV_ERROR
        return EXIT_REPAIR_LIMIT

    print(f"  Vòng lặp chính: {bao_cao.metrics['main_source']}")
    print(f"  Ảnh liên kết  : {bao_cao.metrics['binary']}")
    if bao_cao.metrics.get("image"):
        print(f"  Ảnh nạp được  : {bao_cao.metrics['image']}")

        # Thẻ an toàn cho ảnh CHÍNH. Trước SL-132 chỉ ảnh chẩn đoán mới có thẻ,
        # nên firmware thật của sản phẩm được cổng nạp duyệt y như một ảnh đo
        # tĩnh — kể cả khi nó điều khiển một robot đứng trên hai bánh.
        from eaa.firmware import ghi_the_an_toan

        an_toan = AssemblyPlan.load(project / ASSEMBLY_FILE).safety
        if ghi_the_an_toan(bao_cao.metrics["image"], an_toan):
            print("  Thẻ an toàn   : đã ghi (cổng nạp sẽ đọc trước khi bạn duyệt)")
        else:
            print(
                "  ⚠ firmware.yaml chưa khai mục 'safety' — cổng nạp sẽ coi ảnh\n"
                "    này là ảnh đo tĩnh. Khai đi nếu nó làm thiết bị chuyển động."
            )
    for khoa in sorted(bao_cao.metrics):
        if khoa.endswith(("_bytes", "_pct")):
            print(f"  {khoa:<14}: {bao_cao.metrics[khoa]}")
    print(
        "\nĐây là lần đầu ngưỡng bộ nhớ được đo trên CẢ firmware chứ không trên\n"
        "từng module lẻ — con số ở vòng kiểm module luôn dễ dãi hơn con số này."
    )
    return EXIT_OK


def cmd_ports(args: argparse.Namespace) -> int:
    """Bước đầu chạm vào thế giới vật lý: máy đang thấy cổng nào."""
    from eaa.serialport import declared_usb_ids, list_ports, match_declared, render_ports

    project = resolve_project(args.project)
    hardware = _nap_kho(HardwareProfile.load, project / "hardware_profile.yaml")

    khai, goi_y = declared_usb_ids(hardware)

    if getattr(args, "watch", False):
        return _canh_usb(khai, timeout_s=args.timeout)

    cong = match_declared(
        list_ports(include_virtual=args.all), khai, port_hint=goi_y
    )

    _in_tieu_de("Cổng nối tiếp")
    print(render_ports(cong))

    # Cổng nối tiếp KHÔNG phải câu hỏi duy nhất, và với nhiều bo nó còn không
    # phải câu hỏi đúng: một bo nối máy qua mạch nạp gắn sẵn hiện ra như thiết
    # bị USB thô, không sinh cổng nối tiếp nào. Trả lời "không cổng nào khớp"
    # ở đó đọc thành "chưa cắm", trong khi sự thật có thể là "cắm rồi, chỉ là
    # bo này không hiện ra cổng nối tiếp".
    from eaa.usbdev import list_usb_devices, match_usb, render_usb

    quet = match_usb(list_usb_devices(), khai)
    _in_tieu_de("Thiết bị USB")
    print(render_usb(quet, declared=bool(khai)))

    la = _thiet_bi_la(quet, khai)
    if la:
        print()
        print(f"  ⚠ Đang cắm {len(la)} thiết bị ngoài, KHÔNG cái nào khớp bo của dự án:")
        for d in la:
            print(f"      {d.id}  {(d.vendor + ' ' + d.name).strip() or '(không tên)'}")
        print("    Cắm nhầm bo là chuyện xảy ra thật, và nó hỏng theo kiểu tệ:")
        print("    mã dịch xong, nạp xong, rồi mới không chạy. Đối chiếu trước.")

    if not khai:
        print(
            "\nHồ sơ phần cứng chưa khai mục 'programmer.usb', nên engine không "
            "có gì để đối chiếu.\nKhai VID/PID của bo ở đó thì lệnh này nói được "
            "cổng nào — và thiết bị USB nào — là mạch của dự án."
        )
    return EXIT_OK


#: Nhà sản xuất máy tính chủ. Thiết bị của họ là bàn phím, camera, bộ điều
#: khiển nội bộ — không phải bo người dùng vừa cắm, nên lọc ra khỏi phần cảnh
#: báo. Đây là dữ liệu về MÁY CHỦ, không phải về phần cứng đích, nên nó không
#: vi phạm ranh giới engine.
_VENDOR_MAY_CHU = {"05ac", "8087", "1d6b", "0e0f", "1b1c"}


def _canh_usb(khai: Sequence[Any], *, timeout_s: float = 120.0,
              nhip_s: float = 1.0) -> int:
    """Canh liên tục bus USB cho tới khi thấy đổi, hoặc hết giờ.

    Vì sao một lệnh chụp-một-lần là chưa đủ
    ----------------------------------------

    Khi bo không hiện ra, người dùng phải đoán giữa nhiều nguyên nhân — dây chỉ
    có nguồn, sai cổng trên bo, hỏng cáp chuyển, cổng máy chết. Cách duy nhất
    phân biệt là **thử từng cái và xem ngay kết quả**, mà chụp một lần thì mỗi
    lần thử lại phải gõ lại lệnh và tự nhớ lần trước thấy gì.

    Chỗ này chỉ ĐỌC, không đổi gì trên máy, và có hạn giờ — nên nó không phải
    một chế độ chạy dài mà là một phép đo có kết thúc.
    """
    import time

    from eaa.usbdev import list_usb_devices, match_usb

    def _chup() -> tuple[UsbScanKieu, frozenset]:
        q = match_usb(list_usb_devices(), khai)
        return q, frozenset((d.vid, d.pid) for d in q.devices)

    dau, truoc = _chup()
    if not dau.usable:
        print(dau.note)
        return EXIT_ENV_ERROR

    _in_tieu_de("Canh cổng USB")
    print(f"  Đang thấy {len(truoc)} thiết bị. Rút/cắm bo đi — tôi báo ngay khi đổi.")
    print(f"  Dừng bằng Ctrl-C, hoặc tự hết sau {timeout_s:.0f} giây.")
    print()

    het = time.monotonic() + timeout_s
    try:
        while time.monotonic() < het:
            time.sleep(nhip_s)
            nay, sau = _chup()
            if sau == truoc:
                continue
            for d in nay.devices:
                if (d.vid, d.pid) not in truoc:
                    dau_hieu = "  ← KHỚP bo của dự án" if d.matched else ""
                    print(f"  + CẮM VÀO   {d.id}  "
                          f"{(d.vendor + ' ' + d.name).strip() or '(không tên)'}{dau_hieu}")
                    if not d.matched and khai and d.vid not in _VENDOR_MAY_CHU:
                        print("              ⚠ KHÔNG khớp bo đã khai trong hồ sơ dự án")
            for v, p in truoc - sau:
                print(f"  − RÚT RA    {v}:{p}")
            truoc = sau
    except KeyboardInterrupt:
        print("\n  (dừng theo yêu cầu)")
    else:
        print(f"\n  Hết {timeout_s:.0f} giây, không thấy thay đổi nào.")
        print("  Bus USB không đổi nghĩa là máy KHÔNG nhận được gì mới — chuyện")
        print("  này xảy ra trước cả tầng trình điều khiển, nên kiểm dây có đủ")
        print("  đường dữ liệu chưa, và kiểm đúng cổng trên bo.")
    return EXIT_OK


#: Kiểu trả về của lượt quét; khai riêng để chú thích không phải nạp module sớm.
UsbScanKieu = Any


def _thiet_bi_la(quet: Any, khai: Sequence[Any]) -> list[Any]:
    """Thiết bị ngoài đang cắm mà không khớp phần khai của dự án.

    Chỉ có nghĩa khi dự án ĐÃ khai bo của mình: chưa khai thì mọi thiết bị đều
    "không khớp", và một cảnh báo bắn vào mọi trường hợp là một cảnh báo bị bỏ
    qua.

    Và cũng chỉ có nghĩa khi bo ấy **chưa thấy đâu**. Cảnh báo này tồn tại vì
    một lý do hẹp: mã dịch xong, nạp xong, rồi mới không chạy, do thứ đang cắm
    không phải bo ta tưởng. Lý do ấy tắt ngay khi bo đã khai có mặt trên bus —
    lúc đó câu hỏi đã có trả lời, và mọi thiết bị còn lại chỉ là đồ trên bàn:
    hub, card mạng, đầu đọc thẻ. Kể chúng ra thành "thiết bị lạ" biến cảnh báo
    thành thứ nổ ở mọi chỗ có đế cắm, tức là thành thứ bị bỏ qua.
    """
    if not khai or not getattr(quet, "usable", False):
        return []
    if any(d.matched for d in quet.devices):
        return []
    return [d for d in quet.devices
            if not d.matched and d.vid not in _VENDOR_MAY_CHU]


def _tham_so_nap(ctx: AppContext, hardware: Any) -> dict[str, Any]:
    """Tham số truyền xuống năng lực 'flash' của pack.

    Chuyển tiếp nguyên vẹn, không diễn giải. Giao thức nạp và tốc độ truyền là
    chuỗi mờ đối với engine — nó chỉ biết pack có hai chỗ giữ mang tên ấy, còn
    giá trị nghĩa là gì thì chỉ hồ sơ phần cứng của dự án mới biết.
    """
    khai = (getattr(hardware, "raw", {}) or {}).get("programmer") or {}
    tham_so = dict(ctx.kb.constraints.platform_params())
    if isinstance(khai, dict):
        if khai.get("tool"):
            tham_so["programmer"] = str(khai["tool"])
        if khai.get("baud"):
            tham_so["baud"] = str(khai["baud"])
    return tham_so


def _chon_cong(project: Path, hardware: Any, chi_dinh: str) -> str:
    from eaa.serialport import declared_usb_ids, list_ports, match_declared

    if chi_dinh:
        return chi_dinh

    khai, goi_y = declared_usb_ids(hardware)
    cong = match_declared(list_ports(), khai, port_hint=goi_y)
    khop = [c for c in cong if c.matched]
    chac_chan = [c for c in khop if c.match_confirmed]

    # Tự chọn CHỈ khi danh tính đã xác nhận bằng VID/PID. Khớp theo tên cổng là
    # phỏng đoán, và một phỏng đoán đủ để nạp nhầm bo thì không được phép thành
    # mặc định — cắm hai bo cùng lúc là chuyện bình thường trên bàn thí nghiệm.
    if len(chac_chan) == 1:
        print(f"  Tự chọn cổng: {chac_chan[0].device} ({chac_chan[0].matched})")
        return chac_chan[0].device

    if khop and not chac_chan:
        ten = ", ".join(c.device for c in khop)
        raise CliError(
            f"Có cổng khớp theo TÊN ({ten}) nhưng chưa xác nhận được VID/PID, "
            "nên engine KHÔNG tự chọn.\n"
            "    Một gợi ý tên có thể trúng đúng cái bo khác đang cắm cùng lúc.\n"
            "    Chỉ rõ bằng --port, hoặc cài pyserial để đọc được VID/PID:\n"
            "        pip install pyserial"
        )

    if not khop:
        raise CliError(
            "Không nhận ra cổng nào là mạch của dự án. Chỉ rõ bằng --port, "
            "và xem 'eaa ports' để biết máy đang thấy gì.\n"
            "Engine KHÔNG đoán bừa một cổng: nạp nhầm thiết bị là hỏng thật, "
            "không phải một lượt chạy lại."
        )

    ten = ", ".join(c.device for c in chac_chan)
    raise CliError(
        f"Có {len(chac_chan)} cổng cùng khớp bo đã khai ({ten}). Chỉ rõ bằng --port."
    )


def cmd_flash(args: argparse.Namespace) -> int:
    """Nạp firmware xuống thiết bị — LUÔN cần người xác nhận (FR-DIA-02)."""
    from eaa.firmware import ASSEMBLY_FILE, AssemblyPlan, FirmwareError
    from eaa.flash import FLASH_LOG, FlashError, FlashLog, Flasher, VerifyResult

    project = resolve_project(args.project)
    nhat_ky = FlashLog(project / FLASH_LOG)

    if args.history:
        _in_tieu_de("Nhật ký nạp")
        ban_ghi = nhat_ky.all()
        if not ban_ghi:
            print("  Chưa lần nào nạp.")
        for r in ban_ghi:
            print(f"  {r.render()}")
        return EXIT_OK

    ctx = build_context(project)
    hardware = _nap_kho(HardwareProfile.load, project / "hardware_profile.yaml")

    if not ctx.runner.manifest.has("flash"):
        raise CliError(
            f"Pack {ctx.runner.manifest.name!r} không khai báo năng lực 'flash'."
        )

    if args.image:
        anh = Path(args.image)
    else:
        try:
            plan = AssemblyPlan.load(project / ASSEMBLY_FILE)
            ten_anh = plan.image_name
        except FirmwareError:
            ten_anh = "firmware"
        khuon = getattr(ctx.runner.manifest, "firmware", None)
        duoi = getattr(khuon, "image_suffix", ".hex") if khuon else ".hex"
        anh = project / "firmware" / "build" / f"{ten_anh}{duoi}"

    nguoi = args.actor or _nguoi_dung()
    _in_tieu_de("Nạp firmware")

    from eaa.flash import FlashApprovals

    so_duyet = FlashApprovals(project / "flash_approvals.jsonl")

    if getattr(args, "flash_action", None) == "approve":
        if not anh or not Path(anh).is_file():
            raise CliError(
                "Duyệt ảnh nào? Cú pháp:\n"
                "    eaa flash approve --image <đường dẫn .hex> --actor <tên bạn>"
            )
        ai = (args.actor or os.environ.get("USER", "")).strip()
        if not ai:
            raise CliError(
                "Phải ghi ai duyệt: thêm --actor <tên bạn>. Nạp firmware chạm "
                "vào thiết bị thật; một quyết định không có người chịu trách "
                "nhiệm thì không phải quyết định của con người."
            )
        _in_tieu_de("Duyệt ảnh nạp")
        print(f"  ảnh : {anh}")

        # Ảnh làm THIẾT BỊ CHUYỂN ĐỘNG trông y hệt ảnh đo tĩnh. Trước SL-124,
        # đường duyệt ngoài luồng này in ra đúng tên tệp và băm — người duyệt
        # không hề biết mình vừa cho phép bánh xe quay. Cảnh báo ấy có sẵn ở
        # nhánh hỏi trên terminal; mở một cánh cửa mới thì cửa ấy phải mang
        # theo mọi thứ cửa cũ mang.
        the = _the_cua_anh(anh)
        muc_an_toan = [str(m) for m in (the.get("safety_checklist") or [])]
        da_xac_nhan: list[str] = []
        if the.get("motion"):
            print(f"  kịch bản: {the.get('scenario', '?')} — {the.get('title', '')}")
            print("\n  ⚠ ẢNH NÀY LÀM THIẾT BỊ CHUYỂN ĐỘNG. Checklist an toàn:")
            khai = {c.strip().lower() for c in (args.confirm_safety or [])}
            thieu = [m for m in muc_an_toan if m.strip().lower() not in khai]
            for m in muc_an_toan:
                dau = "[ ]" if m in thieu else "[x]"
                print(f"      {dau} {m}")
            if thieu:
                raise CliError(
                    f"Chưa xác nhận {len(thieu)} mục an toàn. Duyệt một ảnh làm "
                    "thiết bị chuyển động là cho phép nó QUAY ngay khi nạp "
                    "xong.\n"
                    "Xác nhận từng mục, nguyên văn:\n"
                    + "\n".join(f'    --confirm-safety "{m}"' for m in thieu),
                    EXIT_WAITING_GATE,
                )
            da_xac_nhan = list(muc_an_toan)

        k = so_duyet.approve(
            anh, by=ai, motion=bool(the.get("motion")), safety_confirmed=da_xac_nhan
        )
        print(f"  băm : {k.image_digest}")
        print(f"\nĐã ghi quyết định — {k.actor}.")
        print("Nạp được rồi:  eaa flash --image " + str(anh))
        print(
            "Quyết định neo vào BĂM NỘI DUNG ảnh, không vào đường dẫn. Ráp lại "
            "là ảnh khác, và phải duyệt lại."
        )
        return EXIT_OK

    flasher = Flasher(
        runner=ctx.runner,
        repo=ctx.repo,
        log=nhat_ky,
        source_dir=project / "firmware",
        approvals=so_duyet,
    )

    kiem = flasher.preflight(anh)
    if not kiem.ok:
        raise CliError(kiem.render())
    print(f"  {kiem.render()}")

    cong = _chon_cong(project, hardware, args.port)
    tham_so = _tham_so_nap(ctx, hardware)

    try:
        ban_ghi = flasher.run(
            anh,
            port=cong,
            actor=nguoi,
            params=tham_so,
            programmer=str(tham_so.get("programmer", "")),
            extra_notes=_canh_bao_an_toan_cua_anh(anh),
            required_safety=(
                [str(m) for m in (_the_cua_anh(anh).get("safety_checklist") or [])]
                if _the_cua_anh(anh).get("motion") else []
            ),
        )
    except FlashError as exc:
        raise CliError(str(exc), EXIT_WAITING_GATE) from exc

    print()
    if not ban_ghi.passed:
        print(f"NẠP KHÔNG THÀNH CÔNG — {ban_ghi.note}")
        print("Đã ghi vào nhật ký nạp: một lần thử trượt cũng là dữ kiện chẩn đoán.")
        return EXIT_REPAIR_LIMIT

    print(f"Đã nạp {ban_ghi.image_digest[:19]}… lên {ban_ghi.port}.")
    print(f"Commit đang chạy trên thiết bị: {ban_ghi.commit[:10]}")
    print(VerifyResult(ban_ghi.verify_status, ban_ghi.verify_detail).render())
    print(
        "\nTừ đây mọi số đo lấy về đều gắn với commit trên. Xem lại lịch sử:\n"
        "  eaa flash --history"
    )
    return EXIT_OK


def _thu_telemetry(project: Path, port: str, seconds: float, max_frames: int = 0) -> Any:
    """Thu telemetry từ mạch — dùng chung cho 'eaa telemetry' và 'eaa diagnose run'."""
    from eaa.kb import HardwareProfile as _HP
    from eaa.telemetry import SerialTelemetryReader, TelemetryError, load_frame_spec

    khung = load_frame_spec(project / "diagnostics.yaml")
    hardware = _nap_kho(_HP.load, project / "hardware_profile.yaml")
    cong = _chon_cong(project, hardware, port)

    print(f"  Đang thu {seconds:g}s từ {cong} ở {khung.baud} baud…")
    try:
        return SerialTelemetryReader(port=cong, spec=khung).read(
            duration_s=seconds, max_frames=max_frames
        )
    except TelemetryError as exc:
        raise CliError(str(exc)) from exc


def cmd_telemetry(args: argparse.Namespace) -> int:
    """Thu telemetry từ mạch — kênh máy của chẩn đoán hai kênh."""
    from eaa.telemetry import TelemetryError, read_capture

    project = resolve_project(args.project)
    _in_tieu_de("Thu telemetry")

    if args.replay:
        from eaa.telemetry import load_frame_spec

        try:
            ban_thu = read_capture(args.replay, load_frame_spec(project / "diagnostics.yaml"))
        except TelemetryError as exc:
            raise CliError(str(exc)) from exc
    else:
        ban_thu = _thu_telemetry(project, args.port, args.seconds, args.frames)

    print(ban_thu.render())

    if args.out:
        da_loc, tho = ban_thu.write(args.out)
        print(f"\n  Đã lọc     : {da_loc}")
        print(f"  Nguyên văn : {tho}")
        print(
            "\nBản nguyên văn là bằng chứng: khi một số đo gây tranh cãi, câu\n"
            "\"mạch thật sự gửi gì\" phải trả lời được từ dữ liệu chứ không từ trí nhớ."
        )

    if not ban_thu.frames:
        return EXIT_ENV_ERROR
    return EXIT_OK if ban_thu.trustworthy else EXIT_REPAIR_LIMIT


def _the_cua_anh(image: Path) -> dict:
    """Thẻ đi kèm ảnh, dạng dữ liệu. Không có thẻ thì trả ánh xạ rỗng."""
    import json as _json

    the = Path(str(image) + ".meta.json")
    if not the.is_file():
        return {}
    try:
        d = _json.loads(the.read_text(encoding="utf-8"))
    except _json.JSONDecodeError:
        return {}
    return d if isinstance(d, dict) else {}


def _canh_bao_an_toan_cua_anh(image: Path) -> list[str]:
    """Đọc thẻ đi kèm ảnh chẩn đoán, nếu có.

    Một ảnh chẩn đoán làm robot chuyển động trông y hệt một ảnh đo tĩnh. Thẻ
    này đưa checklist an toàn ra đúng lúc người sắp bấm đồng ý, chứ không phải
    lúc dựng ảnh — giữa hai thời điểm ấy có thể là vài ngày.
    """
    import json as _json

    the = Path(str(image) + ".meta.json")
    if not the.is_file():
        return []
    try:
        du_lieu = _json.loads(the.read_text(encoding="utf-8"))
    except _json.JSONDecodeError:
        return []

    dong = [f"    kịch bản: {du_lieu.get('scenario', '?')} — {du_lieu.get('title', '')}"]
    if du_lieu.get("motion"):
        dong.append("    ⚠ ẢNH NÀY LÀM THIẾT BỊ CHUYỂN ĐỘNG. Checklist an toàn:")
        dong += [f"        [ ] {m}" for m in du_lieu.get("safety_checklist", [])]
    return dong


def _hoi_tren_terminal(cau_hoi: str) -> str:
    """Bậc 2 của thang tìm kiếm — hỏi người ngay trên dòng lệnh.

    Không có terminal thì trả rỗng: một phiên không có người không được diễn
    giải thành một người đã trả lời. Cùng nguyên tắc với mọi cổng khác.
    """
    if not sys.stdin.isatty():
        return ""
    print(f"\n  {cau_hoi}")
    print("  Dán nội dung (bảng thanh ghi–bit), hoặc Enter để bỏ qua:")
    return input("  > ").strip()


def _llm_khong_can_du_an(project: Path) -> Any:
    """Dựng adapter mô hình khi CHƯA có Project State.

    ``eaa brief`` chạy trước ``eaa init``, nên nó không thể lấy cấu hình từ
    Project State — cái đó chưa tồn tại. Lấy từ môi trường, đúng như Agent tự
    làm ở N-001.
    """
    from eaa.llm.calllog import CallLog

    provider, model, _ = chon_llm_theo_moi_truong()
    if provider != "gemini":
        return None
    from eaa.llm.gemini import GeminiClient

    return GeminiClient(model=model, call_log=CallLog(project / "llm_calls.jsonl"))


def cmd_brief(args: argparse.Namespace) -> int:
    """N-001..N-006 — dò, nhận dạng, hỏi, rồi dựng hồ sơ dự án ở dạng nháp."""
    from eaa.brief import (
        BriefError,
        ProjectDraft,
        identify_board,
        probe_hardware,
        remaining_questions,
    )

    project = resolve_project(args.project, phai_ton_tai=False)

    # --- bước 1: dò trước khi hỏi ---
    _in_tieu_de("Máy tự dò phần cứng")
    do_duoc = probe_hardware()
    print(do_duoc.render())

    # --- bước 2: nhận dạng ---
    _in_tieu_de("Nhận dạng bo")
    if args.board:
        # Người đã nêu rõ bo thì KHÔNG hỏi mô hình nữa. Nhận dạng là để trả lời
        # câu người chưa trả lời; hỏi lại thứ vừa được nói là tốn một lời gọi
        # để xác nhận điều đã chắc chắn hơn mọi phỏng đoán.
        ung_vien = []
        print(f"  Bạn đã nêu rõ: {args.board} — bỏ qua bước nhận dạng.")
    else:
        try:
            ung_vien = identify_board(
                do_duoc,
                _llm_khong_can_du_an(project),
                platforms=discover_packs(repo_root() / "packs"),
            )
        except BriefError as exc:
            raise CliError(str(exc)) from exc

    if not ung_vien and not args.board:
        print(
            "  Chưa nhận dạng được bo từ dấu hiệu dò được.\n"
            "  Nêu rõ bằng --board '<tên bo>' để đi tiếp."
        )
    for c in ung_vien:
        print(c.render())

    chon = None
    if args.board:
        chon = next((c for c in ung_vien if args.board.lower() in c.name.lower()), None)
        if chon is None:
            from eaa.brief import BoardCandidate

            chon = BoardCandidate(
                name=args.board, platform=args.platform or "", confidence="người nói"
            )
    elif len(ung_vien) == 1 and ung_vien[0].confidence == "high":
        chon = ung_vien[0]
        print(f"\n  Chỉ một ứng viên và tin cậy cao → chọn {chon.name}.")
    elif ung_vien:
        raise CliError(
            f"Có {len(ung_vien)} ứng viên bo. Agent KHÔNG chọn hộ — chọn nhầm bo "
            "là sai toàn bộ thanh ghi và bản đồ bộ nhớ.\n"
            "    Xem phần 'phân biệt' ở trên rồi nêu rõ: eaa brief --board '<tên>'",
            EXIT_WAITING_GATE,
        )

    if chon is None:
        raise CliError("Chưa xác định được bo — dừng ở đây.", EXIT_WAITING_GATE)

    # --- bước 3: hỏi đúng phần máy không biết ---
    tra_loi = _doc_tra_loi_brief(args)
    con_lai = remaining_questions(tra_loi)
    bat_buoc = [q for q in con_lai if q.required]

    if bat_buoc and args.ask and sys.stdin.isatty():
        _in_tieu_de("Agent hỏi — những gì máy không tự biết được")
        for q in con_lai:
            print(q.render())
            dap = input("      > ").strip()
            if dap:
                tra_loi[q.key] = dap
        con_lai = remaining_questions(tra_loi)
        bat_buoc = [q for q in con_lai if q.required]

    if bat_buoc:
        _in_tieu_de("Agent cần bạn trả lời")
        for q in bat_buoc:
            print(q.render())
            print()
        print(
            "Trả lời bằng một trong hai cách:\n"
            "    eaa brief --ask                      # hỏi ngay trên dòng lệnh\n"
            "    eaa brief --answers <tệp.yaml>       # trả lời sẵn theo khóa ở trên\n\n"
            "Agent KHÔNG tự trả lời hộ: chu kỳ điều khiển và chế độ an toàn là\n"
            "quyết định vật lý, không suy được từ dấu hiệu nào trên máy."
        )
        return EXIT_WAITING_GATE

    # --- bước 4: dựng bản nháp ---
    ban_nhap = ProjectDraft(
        project_dir=project, board=chon, answers=tra_loi, probe=do_duoc
    )
    if chon.confidence != "high":
        ban_nhap.gia_dinh(
            "board_identity",
            f"Bo được nhận dạng là {chon.name} với mức tin cậy {chon.confidence}.",
            chon.how_to_tell or "Đối chiếu mã in trên chip với datasheet.",
            ["mọi thứ trong hồ sơ này"],
        )
    if not chon.clock_hz:
        ban_nhap.gia_dinh(
            "clock_hz",
            "Tần số đồng hồ sau reset chưa xác định.",
            "Đọc mục hệ thống đồng hồ trong datasheet, hoặc đo bằng chân xuất xung.",
            ["mọi tính toán thời gian"],
        )
    ban_nhap.gia_dinh(
        "so_do_chan",
        "Sơ đồ chân của bo chưa nạp — mục pin_map còn trống.",
        "Đọc sơ đồ nguyên lý của bo, hoặc dò từng chân và quan sát.",
        ["mọi module chạm vào chân"],
    )

    try:
        da_ghi = ban_nhap.write()
    except BriefError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Đã dựng bản nháp hồ sơ dự án")
    for d in da_ghi:
        print(f"  {d}")
    print(
        f"\n  Giả định chưa kiểm: {len(ban_nhap.assumptions)} mục — xem mục "
        "'assumptions' trong hồ sơ phần cứng.\n"
        "\nĐây là ĐỀ XUẤT, chưa phải quyết định. Đọc kỹ rồi:\n"
        "    eaa init                 # khởi tạo dự án từ hồ sơ này\n"
        "    eaa gate approve G1      # chốt ràng buộc và kiến trúc"
    )
    return EXIT_WAITING_GATE


def _doc_tra_loi_brief(args: argparse.Namespace) -> dict[str, Any]:
    import yaml as _yaml

    if not args.answers:
        return {}
    duong_dan = Path(args.answers)
    if not duong_dan.is_file():
        raise CliError(f"Không tìm thấy tệp trả lời: {duong_dan}")
    try:
        du_lieu = _yaml.safe_load(duong_dan.read_text(encoding="utf-8")) or {}
    except _yaml.YAMLError as exc:
        raise CliError(f"{duong_dan}: YAML không hợp lệ — {exc}") from exc
    if not isinstance(du_lieu, dict):
        raise CliError(f"{duong_dan}: nội dung phải là ánh xạ khóa–giá trị")
    return {str(k): v for k, v in du_lieu.items()}


def _plan_propose(project: Path, args: argparse.Namespace) -> int:
    """N-040..N-043 — Agent đề xuất phân rã, người quyết."""
    from eaa.decompose import PLAN_FILE, DecomposeError, LlmDecomposer

    ctx = build_context(project)
    muc_tieu = args.goal or _muc_tieu_tu_ho_so(project)

    try:
        ban = LlmDecomposer(llm=ctx.llm, pack_manifest=_nap_pack(project)).propose(
            muc_tieu,
            hardware=ctx.kb.hardware,
            constraints=ctx.kb.constraints,
            # Kèm TRÁCH NHIỆM, không chỉ tên và ngoại vi: `purpose` nằm sẵn
            # trong backlog từ SL-135, và bỏ nó lại ở đây khiến bộ phân rã biết
            # module tồn tại mà không biết nó làm gì (SL-141).
            existing=[
                (m.id, tuple(m.uses or ()), getattr(m, "purpose", ""))
                for m in ctx.store.load().backlog
            ],
        )
    except DecomposeError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Phân rã module — ĐỀ XUẤT")
    print(ban.render())
    ban.save(project / PLAN_FILE)
    return EXIT_WAITING_GATE


def _muc_tieu_tu_ho_so(project: Path) -> str:
    """Lấy mục tiêu từ mô tả hồ sơ phần cứng, nếu người không nêu."""
    import yaml as _yaml

    duong_dan = project / HARDWARE_PROFILE_FILE
    if not duong_dan.is_file():
        return ""
    du_lieu = _yaml.safe_load(duong_dan.read_text(encoding="utf-8")) or {}
    return str(du_lieu.get("description", ""))


def _plan_accept(project: Path, store: Any, args: argparse.Namespace) -> int:
    """Người nhận bản phân rã — module vào backlog theo đúng thứ tự phụ thuộc."""
    from eaa.decompose import PLAN_FILE, DecomposeError, DecompositionPlan
    from eaa.state import BacklogItem

    try:
        ban = DecompositionPlan.load(project / PLAN_FILE)
    except DecomposeError as exc:
        raise CliError(str(exc)) from exc
    if ban is None:
        raise CliError("Chưa có bản phân rã nào đang chờ. Dựng bằng: eaa plan propose")

    _in_tieu_de("Nhận bản phân rã")
    print(ban.render())

    if ban.overloaded and not args.du_biet_qua_tai:
        raise CliError(
            "Bản phân rã vượt trần tải CPU ước lượng — không nhận tự động.\n"
            "    Sửa chu kỳ rồi đề xuất lại, hoặc nhận có chủ ý bằng "
            "--du-biet-qua-tai nếu bạn cho rằng ước lượng quá thận trọng.",
            EXIT_WAITING_GATE,
        )

    with store.with_lock():
        state = store.load()
        da_co = {m.id for m in state.backlog}
        them_moi: list[str] = []
        for ma in ban.order():
            if ma in da_co:
                continue
            de_xuat = next(x for x in ban.modules if x.id == ma)
            state.backlog.append(
                BacklogItem(
                    id=de_xuat.id,
                    # Trách nhiệm module đi cùng vào backlog. Nó là thứ người
                    # vừa đọc và duyệt; vứt ở đây thì lượt sinh mã không còn
                    # nguồn nào biết module này để làm gì (SL-135).
                    purpose=de_xuat.purpose,
                    provides=list(de_xuat.provides),
                    uses=list(de_xuat.uses),
                    depends_on=list(de_xuat.depends_on),
                )
            )
            them_moi.append(de_xuat.id)
        store.save(state)

    print()
    if not them_moi:
        print("  Mọi module trong bản này đã có trong backlog.")
    else:
        print(f"  Đã thêm {len(them_moi)} module theo đúng thứ tự phụ thuộc:")
        for ma in them_moi:
            print(f"    {ma}")
    (project / PLAN_FILE).unlink(missing_ok=True)
    print("\nBước kế tiếp: eaa resolve <module>  rồi  eaa gen <module>")
    return EXIT_OK


def cmd_safety(args: argparse.Namespace) -> int:
    """N-016, N-017 — phân tích hỏng hóc và chế độ an toàn."""
    from eaa.safety import SAFETY_FILE, LlmSafetyAnalyst, SafetyAnalysis, SafetyError

    project = resolve_project(args.project)
    ctx = build_context(project)
    duong_dan = project / SAFETY_FILE

    if args.safety_action == "show":
        try:
            ban = SafetyAnalysis.load(duong_dan)
        except SafetyError as exc:
            raise CliError(str(exc)) from exc
        if ban is None:
            raise CliError(
                "Chưa có phân tích an toàn. Dựng bằng: eaa safety propose"
            )
        _in_tieu_de("Phân tích hỏng hóc và chế độ an toàn")
        print(ban.render(ctx.kb.hardware))
        return EXIT_OK if not ban.gaps(ctx.kb.hardware) else EXIT_WAITING_GATE

    if args.safety_action == "propose":
        if duong_dan.is_file() and not args.force:
            raise CliError(
                f"{duong_dan} đã có. Agent KHÔNG ghi đè phân tích an toàn: bản cũ "
                "có thể đã được chốt tại G1.\n"
                "    Xem bản hiện có: eaa safety show\n"
                "    Dựng lại có chủ ý: eaa safety propose --force"
            )
        try:
            ban = LlmSafetyAnalyst(llm=ctx.llm).analyse(
                hardware=ctx.kb.hardware,
                constraints=ctx.kb.constraints,
                goal=args.goal or _muc_tieu_tu_ho_so(project),
            )
        except SafetyError as exc:
            raise CliError(str(exc)) from exc

        _in_tieu_de("Phân tích hỏng hóc — ĐỀ XUẤT")
        print(ban.render(ctx.kb.hardware))
        ban.save(duong_dan)
        print(f"\n  Đã ghi: {duong_dan}")
        return EXIT_WAITING_GATE

    raise CliError(f"Hành động không hợp lệ: {args.safety_action!r}")


def cmd_interface(args: argparse.Namespace) -> int:
    """N-041 — sinh hợp đồng gọi TRƯỚC khi sinh thân module."""
    from eaa.interfaces import (
        InterfaceError,
        InterfaceGenerator,
        LlmInterfaceDesigner,
    )

    project = resolve_project(args.project)
    ctx = build_context(project)
    state = ctx.store.load()

    muc = state.module(args.module)
    if muc is None:
        co = ", ".join(m.id for m in state.backlog) or "(backlog trống)"
        raise CliError(
            f"Module {args.module!r} không có trong backlog. Đang có: {co}.\n"
            "    Giao diện là hợp đồng của một module đã khai, không phải của "
            "một cái tên bất kỳ."
        )

    try:
        spec = LlmInterfaceDesigner(llm=ctx.llm).design(
            module_id=muc.id,
            purpose=getattr(muc, "note", "") or getattr(muc, "purpose", ""),
            provides=tuple(getattr(muc, "provides", ()) or ()),
            uses=tuple(muc.uses),
            constraints=ctx.kb.constraints,
        )
        _in_tieu_de(f"Giao diện {muc.id} — ĐỀ XUẤT")
        print(spec.render())

        if args.write:
            duong_dan = InterfaceGenerator(ctx.runner.manifest).write(
                spec, project / "firmware"
            )
            print(f"\n  Đã ghi: {duong_dan}")
            print(
                "  Tệp mang dòng đầu nói rõ đây là GIAO DIỆN ĐỀ XUẤT — dòng ấy đi\n"
                "  thẳng vào prompt của module phụ thuộc (lớp K3), nên mô hình biết\n"
                "  nó đang dựa vào một lời hứa chứ không vào mã đã kiểm."
            )
        else:
            print("\n  Chưa ghi tệp. Thêm --write để sinh tệp tiêu đề vào firmware/.")
    except InterfaceError as exc:
        raise CliError(str(exc)) from exc

    return EXIT_WAITING_GATE


def cmd_sources(args: argparse.Namespace) -> int:
    """N-004, N-030 — cần tài liệu nào, và cần trang nào trong đó."""
    from eaa.docplan import DocPlanError, LlmDocLookup, plan_documents, plan_pages
    from eaa.ingest import SourceRegistry

    project = resolve_project(args.project)
    ctx = build_context(project)

    try:
        if args.sources_action == "need":
            ke_hoach = plan_documents(ctx.kb.hardware, silicon_rev=args.rev)
            kho = SourceRegistry(project / "sources.jsonl")
            ke_hoach = ke_hoach.match_provided(kho)

            if args.lookup:
                print("  Đang tra trang chính thức của hãng…")
                ke_hoach = ke_hoach.with_sources(LlmDocLookup(llm=ctx.llm).sources(ke_hoach))

            _in_tieu_de("Tài liệu cần — ĐÍCH DANH")
            print(ke_hoach.render())
            if not args.lookup:
                print(
                    "\n  Chưa tra đường dẫn trang hãng. Thêm --lookup để Agent đi tìm\n"
                    "  (chỉ trong danh sách nguồn cho phép)."
                )
            return EXIT_WAITING_GATE if ke_hoach.missing else EXIT_OK

        if args.sources_action == "pages":
            state = ctx.store.load()
            muc = state.module(args.module) if args.module else None
            ke_hoach = plan_pages(
                hardware=ctx.kb.hardware,
                graph=ctx.graph,
                datasheets=ctx.kb.datasheets,
                module_id=args.module,
                uses=tuple(muc.uses) if muc else (),
            )
            _in_tieu_de("Trang cần trích — ĐÍCH DANH")
            print(ke_hoach.render())
            return EXIT_WAITING_GATE if ke_hoach.requests else EXIT_OK
    except DocPlanError as exc:
        raise CliError(str(exc)) from exc

    raise CliError(f"Hành động không hợp lệ: {args.sources_action!r}")


def cmd_errata(args: argparse.Namespace) -> int:
    """N-037 — errata theo đúng rev silicon, và module nào chạm vào."""
    from eaa.docplan import ERRATA_FILE, DocPlanError, ErrataAnalysis, LlmDocLookup

    project = resolve_project(args.project)
    ctx = build_context(project)
    duong_dan = project / ERRATA_FILE
    state = ctx.store.load()

    try:
        if args.errata_action == "show":
            ban = ErrataAnalysis.load(duong_dan)
            if ban is None:
                ban = ErrataAnalysis(
                    part=str((ctx.kb.hardware.mcu or {}).get("part", "")), looked_up=False
                )
            _in_tieu_de("Errata")
            print(ban.render(ctx.kb.hardware, state.backlog))
            if not ban.looked_up:
                print("\n  Tra bằng: eaa errata lookup --rev <rev in trên chip>")
            return EXIT_OK if ban.looked_up and ban.rev_known else EXIT_WAITING_GATE

        if args.errata_action == "lookup":
            ma_chip = str((ctx.kb.hardware.mcu or {}).get("part", ""))
            if not ma_chip:
                raise CliError("Hồ sơ phần cứng chưa khai 'mcu.part'.")
            if not args.rev:
                print(
                    "  Chưa có rev silicon. Vẫn tra được, nhưng kết luận sẽ áp cho\n"
                    "  MỌI rev — có thể thừa hoặc thiếu. Rev in trên mặt chip.\n"
                )
            ngoai_vi = [str(p.get("id", "")) for p in ctx.kb.hardware.peripherals]
            ban = LlmDocLookup(llm=ctx.llm).errata(
                part=ma_chip,
                silicon_rev=args.rev,
                peripherals=[x for x in ngoai_vi if x],
            )
            _in_tieu_de("Errata — ĐỀ XUẤT")
            print(ban.render(ctx.kb.hardware, state.backlog))
            ban.save(duong_dan)
            print(f"\n  Đã ghi: {duong_dan}")
            print("  Mọi mục ở đây là proposed fact — duyệt tại G2 trước khi dựa vào.")
            return EXIT_WAITING_GATE
    except DocPlanError as exc:
        raise CliError(str(exc)) from exc

    raise CliError(f"Hành động không hợp lệ: {args.errata_action!r}")


def cmd_propose(args: argparse.Namespace) -> int:
    """N-006, N-010, N-011, N-014 — Agent đề xuất, người chốt tại gate."""
    import yaml as _yaml

    from eaa.propose import (
        SCOPE_FILE,
        LlmProposer,
        ProposeError,
        ScopeProposal,
    )

    project = resolve_project(args.project)
    ctx = build_context(project)
    muc_tieu = args.goal or _muc_tieu_tu_ho_so(project)

    def _khoi(nhan: str, du_lieu: Any) -> None:
        print(f"\nChép khối sau vào {nhan}:\n")
        print(_yaml.safe_dump(du_lieu, allow_unicode=True, sort_keys=False))

    try:
        if args.propose_action == "scope":
            duong_dan = project / SCOPE_FILE
            if duong_dan.is_file() and not args.force:
                ban = ScopeProposal.load(duong_dan)
                _in_tieu_de("Phạm vi dự án")
                print(ban.render() if ban else "")
                print(f"\n  Đọc từ: {duong_dan}")
                print("  Dựng lại có chủ ý: eaa propose scope --force")
                return EXIT_OK if ban and not ban.gaps() else EXIT_WAITING_GATE

            ban = LlmProposer(llm=ctx.llm).scope(
                goal=muc_tieu, hardware=ctx.kb.hardware
            )
            _in_tieu_de("Phạm vi dự án — ĐỀ XUẤT")
            print(ban.render())
            ban.save(duong_dan)
            print(f"\n  Đã ghi: {duong_dan}")
            print("  Chốt cùng ràng buộc và kiến trúc: eaa gate approve G1")
            return EXIT_WAITING_GATE

        if args.propose_action == "constraints":
            ban = LlmProposer(llm=ctx.llm).constraints(
                goal=muc_tieu, plant=args.plant, hardware=ctx.kb.hardware
            )
            _in_tieu_de("Ràng buộc cứng — ĐỀ XUẤT")
            print(ban.render())
            print(
                "\nMỗi ràng buộc kèm HỆ QUẢ để người duyệt có căn cứ mà BÁC, không\n"
                "chỉ có căn cứ mà gật. Đọc phần 'vi phạm' trước phần con số."
            )
            _khoi("'limits' của constraints.yaml", {"limits": ban.to_limits()})
            if ban.forbidden:
                _khoi("'forbidden' của constraints.yaml", {"forbidden": list(ban.forbidden)})
            return EXIT_WAITING_GATE

        if args.propose_action == "acceptance":
            ban = LlmProposer(llm=ctx.llm).acceptance(
                goal=muc_tieu, constraints=ctx.kb.constraints
            )
            _in_tieu_de("Tiêu chí nghiệm thu — ĐỀ XUẤT")
            print(ban.render())
            print(
                "\nMỗi tiêu chí là MỘT CON SỐ, có ĐƠN VỊ, và có CÁCH ĐO. Phần\n"
                "'TỪ CHỐI' là phần đáng đọc nhất: đó là những yêu cầu nghe thì\n"
                "hợp lý mà tới lúc bàn giao không ai chứng minh được."
            )
            _khoi("'acceptance' của constraints.yaml", {"acceptance": ban.to_acceptance()})
            return EXIT_WAITING_GATE

        if args.propose_action == "plant":
            if not args.plant:
                raise CliError(
                    "Chưa nêu đối tượng điều khiển. Ví dụ:\n"
                    "    eaa propose plant --plant 'con lắc ngược hai bánh'\n"
                    "    Engine KHÔNG đoán đối tượng từ hồ sơ phần cứng: cùng một\n"
                    "    bo mạch dùng cho một cánh tay máy và cho một bộ điều nhiệt."
                )
            ban = LlmProposer(llm=ctx.llm).plant_model(
                plant=args.plant, goal=muc_tieu, hardware=ctx.kb.hardware
            )
            _in_tieu_de("Mô hình đối tượng — ĐỀ XUẤT")
            print(ban.render())
            if ban.to_assumption_log():
                _khoi(
                    "'assumptions' của hardware_profile.yaml",
                    {"assumptions": ban.to_assumption_log()},
                )
            return EXIT_WAITING_GATE

        if args.propose_action == "pinmap":
            ban = LlmProposer(llm=ctx.llm).pin_map(
                hardware=ctx.kb.hardware, goal=muc_tieu
            )
            _in_tieu_de("Bảng chân — ĐỀ XUẤT")
            print(ban.render(ctx.kb.hardware.pin_functions))
            _khoi("'pin_map' của hardware_profile.yaml", {"pin_map": ban.to_pin_map()})
            return EXIT_WAITING_GATE
    except ProposeError as exc:
        raise CliError(str(exc)) from exc

    raise CliError(f"Hành động không hợp lệ: {args.propose_action!r}")


def cmd_budget(args: argparse.Namespace) -> int:
    """N-015, N-071, N-904 — chia ngân sách trước khi viết mã, không đo sau."""
    import yaml as _yaml

    from eaa.budget import (
        BudgetError,
        DerivedMetric,
        ResourceBudget,
        TokenBudget,
        propose_split,
        spent_tokens,
        weights_from_modules,
    )
    from eaa.kpi import KpiLogger

    project = resolve_project(args.project)
    ctx = build_context(project)

    try:
        ngan_sach = ResourceBudget.from_constraints(ctx.kb.constraints)
        tran_token = TokenBudget.from_constraints(ctx.kb.constraints)
    except BudgetError as exc:
        raise CliError(str(exc)) from exc

    if args.budget_action == "show":
        _in_tieu_de("Ngân sách tài nguyên")
        if ngan_sach is None:
            print(
                "  constraints.yaml chưa có khối 'budget'.\n"
                "  Đang chỉ có trần TỔNG ở 'limits' — phép kiểm ấy đúng nhưng chỉ\n"
                "  trả lời được vào lúc liên kết, tức là lúc muộn nhất.\n\n"
                "  Đề xuất một bản chia: eaa budget propose"
            )
            return EXIT_WAITING_GATE
        print(ngan_sach.render())
        if tran_token is not None:
            print(
                f"\nTrần token mỗi module: {tran_token.per_module:,} "
                f"(cảnh báo từ {tran_token.warn_at_pct:g}%)"
                + (f", đơn giá theo {tran_token.currency}" if tran_token.currency else "")
            )
        return EXIT_OK if not ngan_sach.validate() else EXIT_WAITING_GATE

    if args.budget_action == "tokens":
        kpi = KpiLogger(project / "kpi_log.csv")
        _in_tieu_de("Token và chi phí theo module")
        if tran_token is None:
            print(
                "  Chưa khai 'budget.tokens' trong constraints.yaml, nên KHÔNG có\n"
                "  trần nào đang được thi hành. Số dưới đây chỉ là thống kê."
            )
            tran_token = TokenBudget()
        state = ctx.store.load()
        ten_module = [args.module] if args.module else sorted(
            {r["module"] for r in kpi.rows() if r.get("module")}
            | {m.id for m in state.backlog}
        )
        if not ten_module:
            print("  Chưa module nào gọi mô hình.")
            return EXIT_OK
        vuot = 0
        for ten in ten_module:
            kiem = tran_token.check(spent_tokens(kpi, ten))
            print("  " + kiem.render().replace("\n", "\n  "))
            vuot += 1 if kiem.blocked else 0
        return EXIT_WAITING_GATE if vuot else EXIT_OK

    if args.budget_action == "propose":
        state = ctx.store.load()
        if not state.backlog:
            raise CliError(
                "Backlog trống — chưa có module nào để chia phần.\n"
                "    Ngân sách chia cho những việc đã biết tên; chia cho một danh\n"
                "    sách rỗng thì chỉ là chia cho dự phòng.\n"
                "    Khai module trước: 'eaa plan add', hoặc 'eaa plan propose'."
            )
        if ngan_sach is None or not ngan_sach.capacity:
            raise CliError(
                "constraints.yaml chưa khai 'budget.capacity' — không có mẫu số thì\n"
                "    không chia được. Lấy dung lượng từ hardware_profile.yaml và khai\n"
                "    lại ở đây, vì đây là nơi nó được dùng để chia."
            )

        so_lieu = list(args.metric) or [
            k for k in ngan_sach.capacity if k in ngan_sach.capacity
        ]
        try:
            de_xuat = propose_split(
                weights_from_modules(state.backlog),
                ngan_sach.capacity,
                metrics=so_lieu,
                reserve_pct=ngan_sach.reserve_pct,
                derived=ngan_sach.derived,
            )
        except BudgetError as exc:
            raise CliError(str(exc)) from exc

        _in_tieu_de("Ngân sách tài nguyên — ĐỀ XUẤT")
        print(de_xuat.render())
        print(
            "\nBản chia này là ĐỀ XUẤT, suy từ dữ liệu đã khai (số tài nguyên mỗi\n"
            "module dùng, có chạy định kỳ hay không) chứ không từ mô hình. Nó\n"
            "chắc chắn còn thô: một module cấu hình nhiều thanh ghi mà ít mã, và\n"
            "một module ít thanh ghi mà nhiều tính toán, sẽ nhận cùng một phần.\n"
            "Sửa nó là việc của người, và sửa xong thì duyệt lại tại G1."
        )
        print("\nChép khối sau vào 'budget.modules' của constraints.yaml:\n")
        print(
            _yaml.safe_dump(
                {"modules": de_xuat.to_yaml_block()["modules"]},
                allow_unicode=True,
                sort_keys=True,
            )
        )
        return EXIT_WAITING_GATE

    raise CliError(f"Hành động không hợp lệ: {args.budget_action!r}")


def cmd_resolve(args: argparse.Namespace) -> int:
    """Đi TÌM thứ bảng kiểm còn thiếu — P7 bước 3, thang ba bậc."""
    from eaa.gapsearch import SEARCH_LEDGER, GapResolver, GapSearchError, SearchLedger
    from eaa.readiness import ReadinessChecker

    project = resolve_project(args.project)
    ctx = build_context(project)
    state = ctx.store.load()

    muc = next((m for m in state.backlog if m.id == args.module_id), None)
    if muc is None:
        raise CliError(
            f"Không có module {args.module_id!r} trong backlog. "
            f"Thêm bằng: eaa plan add {args.module_id}"
        )

    bang_kiem = ReadinessChecker(kb=ctx.kb, graph=ctx.graph).build_ric(
        args.module_id, uses=muc.uses
    )
    _in_tieu_de(f"Bảng kiểm thông tin cần — {args.module_id}")
    print(bang_kiem.render())
    print(_pham_vi_bang_kiem())

    if bang_kiem.ready:
        print(
            "\nĐủ điều kiện — TRONG PHẠM VI ĐÃ KHAI — mở vòng sinh mã: "
            "eaa gen " + args.module_id
        )
        return EXIT_OK

    if bang_kiem.conflicts:
        raise CliError(
            f"{len(bang_kiem.conflicts)} mục MÂU THUẪN — thang tìm kiếm KHÔNG chạy "
            "khi kho tri thức đang tự mâu thuẫn.\n"
            "  Hai nguồn nói khác nhau thì người phân xử, máy không chọn hộ "
            "(AIS §8.2).",
            EXIT_WAITING_GATE,
        )

    _in_tieu_de("Đi tìm thứ còn thiếu")
    try:
        bao_cao = GapResolver(
            kb=ctx.kb,
            graph=ctx.graph,
            ledger=SearchLedger(project / SEARCH_LEDGER),
            llm=ctx.llm,
            ask=_hoi_tren_terminal if args.ask else None,
            allow_web=args.web,
        ).resolve(bang_kiem)
    except GapSearchError as exc:
        raise CliError(str(exc)) from exc

    print(bao_cao.render())

    if bao_cao.found_any:
        return EXIT_WAITING_GATE
    if bao_cao.handed_off:
        return EXIT_REPAIR_LIMIT
    return EXIT_WAITING_GATE


def cmd_decide(args: argparse.Namespace) -> int:
    """Dựng tập phương án cho một quyết định, để người chọn tại gate."""
    from eaa.options import OPTIONS_FILE, LlmOptionProposer, OptionError, OptionSet

    project = resolve_project(args.project)
    ctx = build_context(project)

    if args.show:
        _in_tieu_de("Phương án đang chờ chọn")
        tat_ca = OptionSet.load_all(project / OPTIONS_FILE)
        if not tat_ca:
            print("  Không có tập phương án nào đang chờ.")
            return EXIT_OK
        for gate_id, tap in sorted(tat_ca.items()):
            print(f"── {gate_id} ──")
            print(tap.render())
        return EXIT_WAITING_GATE

    if args.gate not in GATE_ORDER:
        raise CliError(f"Gate không hợp lệ: {args.gate!r} (hợp lệ: {list(GATE_ORDER)})")

    boi_canh = Path(args.context).read_text(encoding="utf-8") if args.context else ""
    try:
        tap = LlmOptionProposer(llm=ctx.llm).propose(
            args.question, context=boi_canh, gate_id=args.gate, count=args.count
        )
    except OptionError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de(f"Phương án cho {args.gate}")
    print(tap.render())
    tap.save(project / OPTIONS_FILE)

    print(
        f"Đã ghi lại {len(tap.options)} phương án, đang CHỜ NGƯỜI CHỌN.\n"
        "Agent không tự chọn: gợi ý là gợi ý, quyết định là quyết định.\n"
        f"  Xem lại rồi chọn: eaa gate approve {args.gate} --option <mã>"
    )
    return EXIT_WAITING_GATE


def cmd_rollback(args: argparse.Namespace) -> int:
    from eaa.versions import NoKnownGood, VersionError

    project = resolve_project(args.project)
    ctx = build_context(project)
    kho = _tao_versions(project, ctx.repo)

    if not (args.reason or "").strip():
        raise CliError(
            "Quay lui bắt buộc kèm --reason. Thất bại cũng là tri thức, và một "
            "dòng 'không đạt' trống rỗng thì không dạy được gì (AIS §8.4)."
        )

    try:
        ban_ghi = kho.rollback(
            args.module_id, reason=args.reason, actor=args.actor or _nguoi_dung()
        )
    except (NoKnownGood, VersionError) as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de(f"Đã quay lui {args.module_id}")
    print(f"  Về bản known-good: {ban_ghi.commit}")
    print(f"  Lý do            : {ban_ghi.reason}")
    print(
        "\nknown_good.lock KHÔNG đổi — quay lui không phải một lần nghiệm thu; "
        "bản vừa lùi về vốn đã là bản biết-là-tốt."
    )
    return EXIT_OK


def cmd_tune(args: argparse.Namespace) -> int:
    """UC07 — nhập số đo vật lý tại G4, phong hạng hoặc ghi nhận không đạt."""
    from eaa.versions import Measurement, PromotionNotAuthorized, Tier, VersionError

    project = resolve_project(args.project)
    ctx = build_context(project)
    kho = _tao_versions(project, ctx.repo)

    so_do = _doc_so_do(Path(args.input)) if args.input else []
    rut_ra = None
    if args.port or args.seconds:
        rut_ra = _rut_so_do_tu_mach(project, ctx, args)
        so_do = rut_ra.measurements

    if args.reject:
        ban_ghi = kho.reject_acceptance(
            module=args.module_id,
            commit=ctx.repo.head(),
            reason=args.reject,
            actor=args.actor or _nguoi_dung(),
        )
        _in_tieu_de(f"Ghi nhận KHÔNG ĐẠT nghiệm thu — {args.module_id}")
        print(f"  Lý do: {ban_ghi.reason}")
        print(
            f"\nBản known-good vẫn là {kho.known_good_of(args.module_id) or '(chưa có)'}. "
            f"Quay lui bằng: eaa rollback {args.module_id} --reason '...'"
        )
        return EXIT_WAITING_GATE

    # Chốt: commit sắp phong hạng phải là commit ĐANG CHẠY trên thiết bị.
    # Không có phép so này thì quy trình cho phép nạp bản A, đo bản A, rồi
    # phong hạng hw-verified cho bản B — và known_good.lock sẽ nói bản B đã
    # chạy trên phần cứng, điều mà mọi lần quay lui về sau tin theo.
    from eaa.acceptance import check_device_commit
    from eaa.flash import FLASH_LOG, FlashLog

    thiet_bi = check_device_commit(ctx.repo.head(), FlashLog(project / FLASH_LOG))
    if thiet_bi.blocking:
        raise CliError(thiet_bi.message, EXIT_WAITING_GATE)
    if not thiet_bi.verified:
        print(f"\n  {thiet_bi.message}\n")

    if rut_ra is not None and not rut_ra.ok:
        raise CliError(
            "Không phong hạng được:\n" + rut_ra.render(), EXIT_WAITING_GATE
        )

    quyet_dinh = ctx.gates.latest("G4")
    try:
        ban_ghi = kho.promote(
            module=args.module_id,
            commit=ctx.repo.head(),
            tier=Tier.HW_VERIFIED,
            decision=quyet_dinh,
            measurements=so_do,
            env_hash=ctx.store.load().env_hash,
            reason=(
                "nghiệm thu vật lý tại G4; "
                f"device_verified={'true' if thiet_bi.verified else 'false'}"
            ),
        )
    except (PromotionNotAuthorized, VersionError) as exc:
        raise CliError(str(exc), EXIT_WAITING_GATE) from exc

    _in_tieu_de(f"Đã nghiệm thu {args.module_id} — {Tier.HW_VERIFIED}")
    for m in ban_ghi.measurements:
        print(f"  {m}")
    print(f"\nknown_good.lock cập nhật: {ban_ghi.commit}")
    return EXIT_OK


def _rut_so_do_tu_mach(project: Path, ctx: AppContext, args: argparse.Namespace) -> Any:
    """Thu telemetry rồi rút số đo theo đúng những gì dự án đã khai."""
    from eaa.acceptance import AcceptanceError, AcceptanceSpec, derive_measurements
    from eaa.diagnostics import DiagnosticSession

    ban_thu = _thu_telemetry(project, args.port, args.seconds or 10.0)
    print(ban_thu.render())
    if not ban_thu.trustworthy:
        raise CliError(
            "Phiên thu không tin được — không nghiệm thu trên dữ liệu này.",
            EXIT_REPAIR_LIMIT,
        )
    if args.out:
        da_loc, tho = ban_thu.write(args.out)
        print(f"\n  Bản thu    : {da_loc}")
        print(f"  Nguyên văn : {tho}")

    try:
        spec = AcceptanceSpec.from_acceptance(ctx.kb.constraints.acceptance)
        rut_ra = derive_measurements(
            DiagnosticSession.parse_telemetry(ban_thu.stream()), spec
        )
    except AcceptanceError as exc:
        raise CliError(str(exc)) from exc

    print()
    print(rut_ra.render())
    return rut_ra


def _doc_so_do(path: Path) -> list[Any]:
    """Đọc measures.yaml do kỹ sư nhập sau khi đo trên thiết bị thật."""
    import yaml as _yaml

    from eaa.versions import Measurement

    if not path.is_file():
        raise CliError(f"Không tìm thấy tệp số đo: {path}")
    try:
        du_lieu = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except _yaml.YAMLError as exc:
        raise CliError(f"{path}: YAML không hợp lệ — {exc}") from exc

    ket_qua = []
    for m in du_lieu.get("measurements") or []:
        if not isinstance(m, dict) or "name" not in m or "value" not in m:
            raise CliError(f"{path}: mục số đo thiếu 'name' hoặc 'value': {m!r}")
        ket_qua.append(
            Measurement(
                name=str(m["name"]),
                value=float(m["value"]),
                unit=str(m.get("unit", "")),
                note=str(m.get("note", "")),
            )
        )
    if not ket_qua:
        raise CliError(
            f"{path} không có số đo nào. Hạng hw-verified khẳng định một điều về "
            "thiết bị thật nên phải kèm bằng chứng đo được."
        )
    return ket_qua


# --------------------------------------------------------------------------
# AIS §7 — chẩn đoán phần cứng
# --------------------------------------------------------------------------


def cmd_diagnose(args: argparse.Namespace) -> int:
    from eaa.diagnostics import (
        DiagnosticError,
        DiagnosticSession,
        SafetyChecklistNotConfirmed,
        ScenarioLibrary,
    )
    from eaa.ledger import ErrorLedger

    project = resolve_project(args.project)
    try:
        thu_vien = ScenarioLibrary.load(project / "diagnostics.yaml")
    except DiagnosticError as exc:
        raise CliError(str(exc)) from exc

    phien = DiagnosticSession(
        library=thu_vien,
        records_path=project / "measurements.jsonl",
        ledger=ErrorLedger(project / "error_ledger.jsonl"),
    )

    if args.diagnose_action == "list":
        _in_tieu_de(f"Kịch bản chẩn đoán ({len(thu_vien.scenarios)})")
        for s in thu_vien.scenarios:
            nhan = "chuyển động" if s.motion else "tĩnh"
            kenh = "tự động" if s.fully_automatic else f"{len(s.human)} mục người quan sát"
            print(f"  {s.id:<8}{nhan:<13}{kenh:<26}{s.title}")
        return EXIT_OK

    if args.diagnose_action == "select":
        from eaa.diagnostics import MO_HINH

        # Bậc 1 khớp từ khóa; trượt thì mới hỏi mô hình. Không đảo thứ tự:
        # bậc 1 tất định và kiểm lại được, và ta chỉ cần bậc 2 khi nó trượt.
        mo_hinh = None if args.khong_hoi_mo_hinh else build_context(project).llm
        chon = thu_vien.select_smart(args.symptom, mo_hinh)

        if not chon:
            raise CliError(
                f"Không kịch bản nào khớp triệu chứng {args.symptom!r}.\n"
                "    Đây cũng là một dữ kiện: có thể dự án còn thiếu một kịch bản\n"
                "    cho hiện tượng này. Xem danh sách hiện có: eaa diagnose list"
            )

        _in_tieu_de(f"Kịch bản gợi ý cho: {args.symptom}")
        for m in chon:
            print(m.render())
            if m.scenario.motion:
                print("      ⚠ Có chuyển động. Checklist an toàn bắt buộc:")
                for muc in m.scenario.safety_checklist:
                    print(f"        [ ] {muc}")
        return EXIT_WAITING_GATE if any(m.tier == MO_HINH for m in chon) else EXIT_OK

    if args.diagnose_action == "build":
        from eaa.firmware import DiagnosticFirmwareBuilder
        from eaa.telemetry import load_frame_spec

        ctx = build_context(project)
        kich_ban = thu_vien.get(args.scenario)

        _in_tieu_de(f"Dựng firmware chẩn đoán — {kich_ban.id}")
        print(f"  {kich_ban.title}")
        if kich_ban.motion:
            print("\n  ⚠ Kịch bản này làm THIẾT BỊ CHUYỂN ĐỘNG. Checklist an toàn:")
            for muc in kich_ban.safety_checklist:
                print(f"      [ ] {muc}")

        bao_cao = DiagnosticFirmwareBuilder(
            runner=ctx.runner, project_dir=project
        ).run(kich_ban, load_frame_spec(project / "diagnostics.yaml"))

        print()
        if not bao_cao.passed:
            for loi in bao_cao.errors[:10]:
                print(f"  {loi.message}")
            thieu_moi_truong = bao_cao.metrics.get("config_error") or bao_cao.metrics.get("env_error")
            return EXIT_ENV_ERROR if thieu_moi_truong else EXIT_REPAIR_LIMIT

        print(f"  Bộ khung   : {bao_cao.metrics['source']}")
        print(f"  Ảnh nạp được: {bao_cao.metrics.get('image', bao_cao.metrics['binary'])}")
        print(
            f"\nNạp nó: eaa flash --image {bao_cao.metrics.get('image', '')}\n"
            "Thu số đo rồi kết luận: eaa diagnose run "
            f"{kich_ban.id} --port <cổng>"
        )
        return EXIT_OK

    if args.diagnose_action == "run":
        try:
            kich_ban = phien.prepare(
                args.scenario,
                safety_confirmed=(args.confirm_safety or []),
            )
        except SafetyChecklistNotConfirmed as exc:
            raise CliError(str(exc), EXIT_WAITING_GATE) from exc
        except DiagnosticError as exc:
            raise CliError(str(exc)) from exc

        if args.port or args.seconds:
            # Kênh máy đọc THẲNG từ mạch thay vì từ tệp người tự bắt về.
            # Ưu tiên cờ người gõ, rồi tới khai báo của kịch bản, rồi mới
            # tới mặc định. Kịch bản biết nó chạy bao lâu; lệnh thì không.
            giay = args.seconds or kich_ban.collect_seconds or 5.0
            ban_thu = _thu_telemetry(project, args.port, giay)
            print(ban_thu.render())
            if not ban_thu.trustworthy:
                raise CliError(
                    "Phiên thu telemetry không tin được — không kết luận chẩn đoán "
                    "trên dữ liệu này.\nSố rút ra từ một phiên nhiều khung hỏng vẫn "
                    "trông hợp lý, và đó mới là chỗ nguy hiểm.",
                    EXIT_REPAIR_LIMIT,
                )
            if args.telemetry:
                ban_thu.write(args.telemetry)
            telemetry = ban_thu.stream()
            print()
        else:
            telemetry = (
                Path(args.telemetry).read_text(encoding="utf-8") if args.telemetry else "{}"
            )
        tra_loi = _doc_tra_loi_nguoi(args.answer or [])

        if kich_ban.human and not tra_loi:
            # Chấm kênh máy TRƯỚC rồi mới hỏi người. Chưa kết luận khi thiếu
            # nửa dữ liệu là đúng; GIẤU phần đã biết thì không.
            #
            # Đo được ở Bài 2 phiên kiểm bo thật: phép kiểm mã nhận dạng đã
            # trượt ngay lúc dữ liệu về, và lệnh vẫn sai người đi nghiêng bo,
            # quan sát, gõ trả lời — một việc chân tay không đổi được kết cục
            # (SL-121).
            # `telemetry` ở đây là CHUỖI khung thô, không phải dict — cùng thứ
            # `diagnose()` nhận và tự bóc. Truyền thẳng vào `evaluate_machine`
            # thì nó lấy chỉ số trên một chuỗi và sập.
            do_duoc = (
                phien.parse_telemetry(telemetry)
                if isinstance(telemetry, str) else dict(telemetry)
            )
            dat_may, bang_chung = phien.evaluate_machine(kich_ban, do_duoc)
            if bang_chung:
                _in_tieu_de(f"Kênh máy đã có — {kich_ban.id}")
                for dong in bang_chung:
                    print(f"  {dong}")

            _in_tieu_de(f"Cần quan sát của người — {kich_ban.id}")
            for h in kich_ban.human:
                print(f"  --answer {h.key}=<có|không>")
                print(f"      {h.question}")
            print(
                "\nChẩn đoán là phép GIAO của hai kênh. Với nửa dữ liệu, kết luận "
                "nào cũng có thể sai mà vẫn nghe chắc chắn."
            )
            if not dat_may:
                print(
                    "\n  ⚠ Kênh máy ĐÃ TRƯỢT ở trên. Quan sát của bạn vẫn cần để\n"
                    "    chốt VÙNG LỖI, nhưng nó sẽ không lật được kết cục — biết\n"
                    "    trước thì bạn chọn được có bỏ công ra bây giờ hay không."
                )
            return EXIT_WAITING_GATE

        ket_luan = phien.diagnose(
            args.scenario, telemetry=telemetry, human_answers=tra_loi
        )
        print()
        print(ket_luan.render())
        return EXIT_OK if ket_luan.verdict in ("không phát hiện lỗi",) else EXIT_WAITING_GATE

    if args.diagnose_action == "measure":
        kich_ban = thu_vien.get(args.scenario)
        if not kich_ban.manual:
            raise CliError(
                f"Kịch bản {kich_ban.id} không khai phép đo tay nào.\n"
                "    Kênh này dành cho đại lượng không con chip nào tự đo được "
                "về chính nó\n"
                "    — dòng tổng, sụt áp trên dây, nhiệt độ vỏ linh kiện (N-084)."
            )

        so_do = _doc_so_do_tay(args.value or [])
        _in_tieu_de(f"Đo bằng dụng cụ — {kich_ban.id}")

        if not so_do:
            print(f"  {kich_ban.title}\n")
            if kich_ban.motion:
                print("  ⚠ Kịch bản này làm THIẾT BỊ CHUYỂN ĐỘNG. Checklist an toàn:")
                for muc in kich_ban.safety_checklist:
                    print(f"      [ ] {muc}")
                print()
            for m in kich_ban.manual:
                print(m.instructions())
                print()
            print("Nhập số đo về:")
            for m in kich_ban.manual:
                print(f"  --value {m.key}=<số {m.unit}>")
            print(
                "\nAgent KHÔNG đoán những con số này. Không có ai cầm dụng cụ thì\n"
                "phần này của kịch bản là chưa đo, chứ không phải là đạt."
            )
            return EXIT_WAITING_GATE

        thieu = [m.key for m in kich_ban.manual if m.key not in so_do]
        vi_pham: list[str] = []
        for m in kich_ban.manual:
            if m.key not in so_do:
                continue
            dat, mo_ta = m.evaluate(so_do[m.key])
            print(f"  {'✓' if dat else '✗'} {m.key}: {mo_ta}")
            if not dat:
                vi_pham.append(f"{m.quantity}: {mo_ta}")

        if thieu:
            print(f"\n  CHƯA ĐO: {', '.join(thieu)}")
            print("  Một bản ghi thiếu số đo trông y hệt một bản ghi đủ — nên nó")
            print("  được nói ra, không được im lặng bỏ qua.")

        _ghi_so_do_tay(project, kich_ban.id, so_do)
        print(f"\n  Đã ghi vào {project / 'measurements.jsonl'}")
        return EXIT_OK if not (vi_pham or thieu) else EXIT_WAITING_GATE

    raise CliError(f"Hành động không hợp lệ: {args.diagnose_action!r}")


def _doc_so_do_tay(cap: Sequence[str]) -> dict[str, float]:
    """Đọc các cặp ``khóa=số`` từ dòng lệnh."""
    ket_qua: dict[str, float] = {}
    for muc in cap:
        if "=" not in muc:
            raise CliError(f"Số đo phải có dạng khóa=giá_trị, nhận {muc!r}")
        khoa, gia_tri = muc.split("=", 1)
        try:
            ket_qua[khoa.strip()] = float(gia_tri.strip().replace(",", "."))
        except ValueError as exc:
            raise CliError(
                f"Số đo {khoa.strip()!r} không phải một con số: {gia_tri.strip()!r}"
            ) from exc
    return ket_qua


def _ghi_so_do_tay(project: Path, scenario: str, values: dict[str, float]) -> None:
    """Ghi số đo tay vào Measurement Records — append-only như mọi kho khác."""
    import json as _json
    from datetime import datetime, timezone

    duong_dan = project / "measurements.jsonl"
    ban_ghi = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario,
        "channel": "dong_ho_do",
        "actor": _nguoi_dung(),
        "values": values,
    }
    with open(duong_dan, "a", encoding="utf-8") as f:
        f.write(_json.dumps(ban_ghi, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def cmd_scope_image(args: argparse.Namespace) -> int:
    """TC-23 — đọc số đo từ ảnh màn hiện sóng; người sửa được trước khi lưu."""
    from eaa.ingest import IngestError, MediaStore, ScopeImageReader

    project = resolve_project(args.project)
    ctx = build_context(project)

    try:
        de_xuat = ScopeImageReader(
            llm=ctx.llm, media=MediaStore(project / "media")
        ).read(args.image, expect=tuple(args.expect or []))
    except IngestError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Số đo đọc từ ảnh — ĐỀ XUẤT")
    if not de_xuat:
        print(
            "  Không đọc được số đo nào từ ảnh này.\n"
            "  Đó là một kết cục hợp lệ: một con số bịa ra kèm đơn vị đúng còn\n"
            "  tệ hơn không có con số nào."
        )
        return EXIT_WAITING_GATE

    for m in de_xuat:
        print(m.render())

    chot = _doc_so_do_tay(args.accept or [])
    if not chot:
        print(
            "\nCHƯA LƯU. Số đọc từ ảnh là ĐỀ XUẤT, không tự vào Measurement Records.\n"
            "Đối chiếu từng con số với ảnh gốc rồi chốt:\n"
        )
        for m in de_xuat:
            print(f"  --accept {m.key}={m.value:g}      # giữ nguyên số Agent đọc")
        print(
            "\nSửa được giá trị trước khi chốt — bản ghi giữ CẢ HAI con số, để về sau\n"
            "câu 'máy đọc ra bao nhiêu, người sửa thành bao nhiêu' trả lời được."
        )
        return EXIT_WAITING_GATE

    import json as _json

    nguoi = args.actor or _nguoi_dung()
    duong_dan = project / "measurements.jsonl"
    da_luu = 0
    with open(duong_dan, "a", encoding="utf-8") as f:
        for m in de_xuat:
            if m.key not in chot:
                continue
            ban_ghi = m.accept(chot[m.key], actor=nguoi)
            f.write(_json.dumps(ban_ghi, ensure_ascii=False) + "\n")
            da_luu += 1
            nhan = " (người SỬA)" if ban_ghi["edited"] else ""
            print(f"  ✓ {m.key} = {ban_ghi['value']:g} {m.unit}{nhan}")
        f.flush()
        os.fsync(f.fileno())

    print(f"\nĐã ghi {da_luu} số đo vào {duong_dan}, người chốt: {nguoi}")
    return EXIT_OK


def cmd_capabilities(args: argparse.Namespace) -> int:
    """Bảng năng lực: Agent làm được gì, cái nào chạy được, kiểm bằng gì."""
    from eaa.capabilities import survey_capabilities
    from eaa.doctor import ToolManifest

    manifest = None
    cong_cu: list[str] = []
    ten_du_an = ""
    try:
        project = resolve_project(args.project)
        ten_du_an = project.name
        manifest = _nap_pack(project)
        rang_buoc = _nap_kho(Constraints.load, project / CONSTRAINTS_FILE)
        goc = repo_root()
        cong_cu = list(
            ToolManifest.load(
                goc / "tools.yaml",
                goc / "packs" / rang_buoc.platform / "tools.yaml",
                pack=rang_buoc.platform,
            ).specs
        )
    except Exception:
        # Bảng năng lực phải trả lời được cả khi CHƯA có dự án nào — đó đúng là
        # lúc người ta hỏi "cái này làm được gì" lần đầu tiên.
        pass

    print(
        survey_capabilities(
            parser=build_parser(),
            manifest=manifest,
            tools_manifest=cong_cu,
            project=ten_du_an,
        ).render(verbose=args.verbose)
    )
    return EXIT_OK


def _llm_ngoai_du_an(args: argparse.Namespace) -> Any:
    """Mô hình cho những lệnh KHÔNG gắn với một dự án.

    Tra web, viết công cụ, tra lỗi — ba việc này đúng là những việc người ta
    cần TRƯỚC khi có dự án nào. Bắt chúng đi qua Project State là dựng lại đúng
    cái cửa vào mà ``eaa scratch`` sinh ra để hạ xuống.

    Có dự án thì vẫn theo dự án: mã model là một phần điều kiện thí nghiệm.
    Trả ``None`` khi không có mô hình nào — bên gọi tự quyết làm gì tiếp.
    """
    try:
        project = resolve_project(getattr(args, "project", None))
        state = StateStore(project / STATE_FILE).load()
        return _tao_llm(state, project)
    except Exception:  # noqa: BLE001 - chưa có dự án là chuyện bình thường ở đây
        pass

    provider, model, _ly_do = chon_llm_theo_moi_truong()
    if provider != "gemini":
        return None
    from eaa.llm.gemini import GeminiClient

    return GeminiClient(model=model)


def _bo_tra_web(args: argparse.Namespace, **kw: Any):
    """Dựng bộ tra web dùng chung cho các lệnh cần mạng.

    Bộ đệm đặt ở gốc kho chứ không trong dự án: một trang tài liệu tải cho dự
    án này thì dự án sau cũng dùng được, và đó chính là điểm của bộ nhớ liên
    dự án.
    """
    from eaa.web import WebCache, WebFetcher
    from eaa.websearch import WebResearcher, default_backend

    fetcher = WebFetcher(cache=WebCache(repo_root() / "memory" / "web_cache"))
    llm = _llm_ngoai_du_an(args)
    return WebResearcher(backend=default_backend(llm=llm, fetcher=fetcher),
                         fetcher=fetcher, **kw)


def cmd_environ(args: argparse.Namespace) -> int:
    """Dò môi trường: máy này là máy gì (C2.3–C2.5, N-020)."""
    from eaa.environ import probe

    if getattr(args, "packages", None):
        from eaa.environ import LENH_LIET_KE_GOI, list_packages

        he = args.packages
        try:
            ds = list_packages(ecosystem=he)
        except ValueError as exc:
            raise CliError(str(exc)) from None
        print(f"Gói đã cài — hệ sinh thái {he}")
        print(f"  hỏi bằng: {' '.join(LENH_LIET_KE_GOI[he])}")
        print()
        if not ds:
            print("  (không hỏi được, hoặc chưa cài gói nào)")
            return EXIT_OK
        for d in ds:
            print(f"  {d}")
        print()
        print(f"{len(ds)} gói. Đây là 'máy này sẵn có gì' — khác với 'công cụ "
              "trong Tool Card đã cài chưa', câu ấy do 'eaa doctor' trả lời.")
        return EXIT_OK

    bao_cao = probe(network=not args.no_network)
    print(bao_cao.render())

    if args.remember:
        from eaa.memory import MemoryStore

        ds = MemoryStore(repo_root()).remember_environment(bao_cao)
        print(f"\nĐã ghi {len(ds)} sự kiện vào bộ nhớ liên dự án.")
    return EXIT_OK


def cmd_research(args: argparse.Namespace) -> int:
    """Tìm trên web rồi ĐỌC trang (C3.1–C3.2, N-035 bậc 3)."""
    from eaa.web import WebError
    from eaa.websearch import SearchError

    cau = " ".join(args.query)
    tra = _bo_tra_web(args, official_only=args.official_only, max_docs=args.max_docs)
    try:
        ket = tra.research(cau, sites=args.site)
    except (SearchError, WebError) as exc:
        raise CliError(str(exc)) from None

    print(ket.render())
    if args.full and ket.documents:
        print()
        print(ket.context())
    return EXIT_OK


def cmd_read(args: argparse.Namespace) -> int:
    """Tải một trang và in nội dung chữ (C3.2)."""
    from eaa.web import WebCache, WebError, WebFetcher

    f = WebFetcher(cache=WebCache(repo_root() / "memory" / "web_cache"))
    try:
        doc = f.fetch(args.url, refresh=args.refresh)
    except WebError as exc:
        raise CliError(str(exc)) from None

    print(doc.render())
    print()
    print(doc.excerpt(args.limit))
    return EXIT_OK


def cmd_recall(args: argparse.Namespace) -> int:
    """Tra kho tri thức ĐÃ DUYỆT của dự án bằng một câu hỏi tự do.

    Đây là chiều ĐỌC của kho mà trước đó chỉ có chiều GHI ở tầm hỏi-đáp: trước
    lệnh này, ``eaa/rag.py`` chỉ được gọi từ ``composer`` (đường sinh mã) và
    ``goldenset`` (đo chất lượng truy xuất). Người hỏi một câu thì không có
    đường nào tới trích đoạn đã duyệt — nên hoặc trả lời bằng trí nhớ mô hình,
    hoặc ra web hỏi lại thứ mình đã có.
    """
    from eaa.rag import search_chunks

    project = resolve_project(args.project)
    ctx = build_context(project)

    cau_hoi = " ".join(args.question).strip()
    if not cau_hoi:
        raise CliError("Cần một câu hỏi. Ví dụ: eaa recall \"tốc độ I2C đặt ở đâu\"")

    ket = search_chunks(
        ctx.kb.datasheets, cau_hoi, graph=ctx.graph, top_k=args.top_k
    )

    _in_tieu_de(f"Kho tri thức đã duyệt — {cau_hoi!r}")

    for r in ket:
        chunk = ctx.kb.datasheets.get(r.chunk_id)
        print(f"\n  {r.render().strip()}   [{r.confidence_level}]")
        print(f"      {chunk.device}/{chunk.peripheral}" + (
            f" · thanh ghi: {', '.join(chunk.registers)}" if chunk.registers else ""))
        if chunk.source:
            print(f"      nguồn: {chunk.source}")
        than = " ".join((chunk.body or "").split())
        if than:
            print(f"      {than[:args.chars]}" + ("…" if len(than) > args.chars else ""))
        print(f"      trích dẫn khi sinh mã: {chunk.citation}")

    # Chunk CHƯA duyệt không bao giờ nằm trong phần trả lời — nhưng im lặng về
    # nó thì người dùng kết luận "kho không có", trong khi thứ họ cần đang nằm
    # sau đúng một lần bấm G2. Nói ra, và nói rõ nó chưa dùng được.
    cho_duyet = [c for c in ctx.kb.datasheets.all() if c.status == "proposed"]
    if not ket:
        print("\n  Kho không có trích đoạn nào đã duyệt khớp câu hỏi này.")
    if cho_duyet:
        print(
            f"\n  {len(cho_duyet)} chunk đang CHỜ DUYỆT tại G2 — chúng không được "
            "tính vào\n  kết quả trên vì chưa ai đối chiếu với bản gốc: "
            + ", ".join(sorted(c.id for c in cho_duyet)[:8])
        )
        print("  Duyệt: eaa gate show G2 → eaa gate approve G2")
    if not ket:
        print(
            "\n  Không có trong kho thì đi tìm, đừng đoán:\n"
            f"    eaa research \"{cau_hoi}\" --official-only    # tìm và ĐỌC trang chính chủ\n"
            "    eaa datasheet add <URL hoặc tệp> --device <chip> --peripheral <ngoại vi>\n"
            "    eaa gate approve G2                          # mới thành tri thức"
        )
        return EXIT_WAITING_GATE
    return EXIT_OK


def cmd_memory_list(args: argparse.Namespace) -> int:
    """Bộ nhớ liên dự án (C8.2)."""
    from eaa.memory import MemoryStore

    kho = MemoryStore(repo_root())
    if args.kind or args.all:
        ds = kho.find(kind=args.kind, include_superseded=args.all)
        for f in ds:
            print(f.render())
        print(f"\n{len(ds)} sự kiện.")
        return EXIT_OK

    # Không nêu gì thì lọc theo dự án đang dùng — bài học của dự án khác không
    # tự chảy sang, và đó là điểm quan trọng nhất của kho này. Lọc cả theo họ
    # MCU: một mục ghi cho họ chip khác cũng là bài học sai chỗ.
    ten, ho = _boi_canh_du_an(args)
    print(kho.render(project=ten, mcu=ho))
    return EXIT_OK


def cmd_memory_add(args: argparse.Namespace) -> int:
    from eaa.memory import TOAN_CUC, MemoryError_, MemoryStore

    try:
        f = MemoryStore(repo_root()).add(
            args.kind, args.subject, args.statement,
            scope=args.scope or TOAN_CUC, evidence=args.evidence,
        )
    except MemoryError_ as exc:
        raise CliError(str(exc)) from None
    print(f"Đã ghi {f.id}")
    print(f.render())
    return EXIT_OK


def _boi_canh_du_an(args: argparse.Namespace) -> tuple[str, str]:
    """Trả ``(tên dự án, họ MCU)`` để lọc kho dùng chung.

    Kho dùng chung mà không lọc là kho rò rỉ: một cách sửa cho toolchain họ này
    được gợi ý cho họ khác, và gợi ý sai chỗ trông y hệt gợi ý đúng. Không xác
    định được dự án thì trả rỗng — khi ấy bên gọi thấy TOÀN BỘ, và đó là đúng:
    người đang đứng ngoài mọi dự án thì không có bối cảnh nào để lọc theo.
    """
    try:
        project = resolve_project(args.project)
    except CliError:
        return "", ""
    try:
        rb = _nap_kho(Constraints.load, project / CONSTRAINTS_FILE)
        return project.name, str(getattr(rb, "platform", "") or "")
    except Exception:  # noqa: BLE001 - chưa có ràng buộc thì vẫn lọc theo tên
        return project.name, ""


def cmd_playbook_list(args: argparse.Namespace) -> int:
    """Sổ tay lỗi (C8.3)."""
    from eaa.playbook import Playbook

    ten, ho = _boi_canh_du_an(args)
    so = Playbook(repo_root())
    ds = so.in_scope(project=ten, mcu=ho)
    if ten or ho:
        print(f"(lọc theo bối cảnh: dự án {ten or '—'}, họ MCU {ho or '—'} — "
              f"{len(ds)}/{len(so.all())} mục áp dụng được ở đây)")
        print()
    print(so.render(entries=ds))
    return EXIT_OK


def cmd_playbook_lookup(args: argparse.Namespace) -> int:
    from eaa.playbook import Playbook, signature

    loi = " ".join(args.error)
    ten, ho = _boi_canh_du_an(args)
    so = Playbook(repo_root())
    goi_y = so.hint(loi, project=ten, mcu=ho)
    print(f"Vân tay: {signature(loi)}")
    print()
    print(goi_y or "Sổ tay chưa có gì cho lỗi này. Sau khi sửa được, ghi lại bằng:\n"
                    "  eaa playbook record '<lỗi>' '<cách sửa>'")
    return EXIT_OK


def cmd_playbook_record(args: argparse.Namespace) -> int:
    from eaa.memory import TOAN_CUC, scope_mcu
    from eaa.playbook import Playbook

    try:
        ten, ho = _boi_canh_du_an(args)
        # Mặc định ghi theo HỌ MCU: phần lớn lỗi toolchain đúng theo họ chip,
        # không đúng ở mọi nơi và cũng không chỉ đúng ở một dự án.
        pham_vi = args.scope or (scope_mcu(ho) if ho else TOAN_CUC)
        m = Playbook(repo_root()).record(
            args.error, args.fix, context=args.context,
            source_url=args.source, scope=pham_vi, worked=not args.failed,
        )
    except ValueError as exc:
        raise CliError(str(exc)) from None
    print(f"Đã ghi vào sổ tay: {m.signature}")
    print(m.render())
    return EXIT_OK


def _xuong_cong_cu(args: argparse.Namespace, *, can_llm: bool = False):
    from eaa.toolforge import ToolForge, ToolRegistry

    llm = _llm_ngoai_du_an(args) if can_llm else None
    if can_llm and llm is None:
        raise CliError(
            "Xưởng công cụ cần một mô hình thật để viết mã. Đặt khóa:\n"
            f"    export {LLM_KEY_ENV}='<khóa của bạn>'"
        )
    return ToolForge(registry=ToolRegistry(repo_root()), llm=llm)


def cmd_tool_list(args: argparse.Namespace) -> int:
    """Sổ công cụ Agent tự viết (C6, C7.1)."""
    from eaa.confidence import SUY_RA, header
    from eaa.toolforge import ToolRegistry
    from eaa.toolusage import UsageLog

    goc = repo_root()
    ds = ToolRegistry(goc).all()
    print("Công cụ Agent tự viết")
    print()
    print(header(SUY_RA))
    print()
    if not ds:
        print("  (chưa có cái nào)")
        print()
        print("  Đặt hàng một cái:  eaa tool propose 'gom số liệu từ mấy tệp báo cáo'")
        return EXIT_OK

    nhat_ky = UsageLog(goc)
    so_do = nhat_ky.stats()
    for t in ds:
        print(t.render())
        if t.name in so_do:
            print(so_do[t.name].render())

    da_duyet = sum(1 for t in ds if t.runnable)
    print()
    print(f"{da_duyet}/{len(ds)} đã được người duyệt và chạy được.")

    dang_lo = nhat_ky.concerning()
    if dang_lo:
        print()
        print("ĐÁNG XEM LẠI — số đo sau khi dùng thật:")
        for s in dang_lo:
            print(f"  ⚠ {s.tool}: {s.ok}/{s.runs} lần đạt"
                  + (f", trung bình {s.avg_ms} ms" if s.slow else ""))
        print()
        print("  Tôi KHÔNG tự gỡ cái nào — gỡ là một quyết định: có khi công cụ")
        print("  đúng còn dữ liệu vào sai. Xem đề nghị cụ thể: eaa suggest")
    return EXIT_OK


def cmd_tool_propose(args: argparse.Namespace) -> int:
    from eaa.toolforge import ForgeError

    try:
        t = _xuong_cong_cu(args, can_llm=True).design(" ".join(args.need))
    except ForgeError as exc:
        raise CliError(str(exc)) from None
    print(f"Đã dựng bản đề xuất: {t.name}")
    print(t.render())
    print()
    print(f"Bước tiếp: eaa tool verify {t.name}")
    return EXIT_OK


def cmd_tool_verify(args: argparse.Namespace) -> int:
    from eaa.toolforge import ForgeError

    try:
        bao_cao = _xuong_cong_cu(args).verify(args.name)
    except ForgeError as exc:
        raise CliError(str(exc)) from None
    print(bao_cao.render())
    if bao_cao.passed:
        print(f"\nBước tiếp — CHỈ bạn làm được: eaa tool approve {args.name} --actor <tên bạn>")
        return EXIT_OK
    return EXIT_WAITING_GATE


def cmd_tool_approve(args: argparse.Namespace) -> int:
    """Người duyệt một công cụ tự sinh. KHÔNG nằm trong danh mục Agent tự gọi."""
    from eaa.toolforge import ForgeError, ToolRegistry

    ai = args.actor or os.environ.get("USER", "")
    try:
        t = ToolRegistry(repo_root()).approve(args.name, by=ai)
    except ForgeError as exc:
        raise CliError(str(exc)) from None
    print(f"Đã duyệt {t.name} — {t.approved_by} lúc {t.approved_at}")
    print(f"Agent gọi được nó từ giờ:  eaa tool run {t.name} --args '{{...}}'")
    return EXIT_OK


def cmd_tool_run(args: argparse.Namespace) -> int:
    from eaa.options import OptionError, boc_json
    from eaa.toolforge import ForgeError

    try:
        tham_so = boc_json(args.args) if args.args.strip() not in ("", "{}") else {}
    except OptionError as exc:
        raise CliError(f"--args phải là JSON: {exc}") from None
    try:
        ten, _ = _boi_canh_du_an(args)
        print(_xuong_cong_cu(args).run(args.name, tham_so, project=ten))
    except ForgeError as exc:
        raise CliError(str(exc)) from None
    return EXIT_OK


def _so_ky_nang(args: argparse.Namespace):
    from eaa.skills import SkillRegistry

    return SkillRegistry(resolve_project(args.project))


def cmd_skill_list(args: argparse.Namespace) -> int:
    """Sổ kỹ năng của dự án (C7.5)."""
    from eaa.confidence import SUY_RA, header

    ds = _so_ky_nang(args).all()
    print("Kỹ năng — chuỗi việc đã đặt tên")
    print()
    print(header(SUY_RA))
    print()
    if not ds:
        print("  (chưa có cái nào)")
        print()
        print("  Tìm chuỗi việc bạn đã lặp:  eaa skill mine")
        return EXIT_OK
    for s in ds:
        print(s.render())
    print()
    print(f"{sum(1 for s in ds if s.runnable)}/{len(ds)} đã được người duyệt và chạy được.")
    return EXIT_OK


def cmd_skill_mine(args: argparse.Namespace) -> int:
    """Tìm chuỗi việc ĐÃ lặp trong nhật ký hội thoại (C7.5)."""
    from eaa.agent import CHAT_LOG
    from eaa.skills import SkillRegistry, mine

    project = resolve_project(args.project)
    ds = mine(project / CHAT_LOG, min_count=args.min_count)

    print("Chuỗi việc đã lặp trong nhật ký hội thoại")
    print()
    if not ds:
        print(f"  (chưa thấy chuỗi nào lặp từ {args.min_count} lần trở lên)")
        print()
        print("  Đề xuất một kỹ năng cho việc chưa ai làm bao giờ là đoán.")
        print("  Cứ dùng 'eaa chat' bình thường; chỗ này bồi lên theo thói quen thật của bạn.")
        return EXIT_OK

    for d in ds:
        print(d.render())
        print()

    if args.save:
        kn = ds[0].to_skill(name=args.save, source=CHAT_LOG)
        SkillRegistry(project).save(kn)
        print(f"Đã lưu đề xuất thứ nhất thành kỹ năng {kn.name!r} (trạng thái: đề xuất).")
        print(f"Bước tiếp: eaa skill verify {kn.name}")
    else:
        print("Lưu một cái lại:  eaa skill mine --save <tên>")
    return EXIT_OK


def cmd_skill_add(args: argparse.Namespace) -> int:
    """Tự viết một kỹ năng (C7.5).

    ``mine`` chỉ phát hiện được thứ đã lặp. Người dùng biết trước mình muốn
    chuỗi nào thì không có lý do gì bắt họ lặp bốn lần rồi mới được đặt tên.
    """
    from eaa.skills import Skill, SkillStep, _now

    tuy_chon = {s.strip() for s in args.optional}
    buoc = tuple(
        SkillStep(argv=tuple(s.split()), optional=s.strip() in tuy_chon)
        for s in args.step if s.strip()
    )
    if not buoc:
        raise CliError("Kỹ năng phải có ít nhất một bước (--step)")

    kn = Skill(
        name=args.name,
        purpose=args.purpose or f"Chuỗi {len(buoc)} bước",
        steps=buoc,
        params=tuple(sorted({p for b in buoc for p in b.params})),
        source="viết tay",
        created_at=_now(),
    )
    _so_ky_nang(args).save(kn)
    print(f"Đã lưu kỹ năng {kn.name!r} (trạng thái: đề xuất).")
    print(kn.render())
    print(f"\nBước tiếp: eaa skill verify {kn.name}")
    return EXIT_OK


def cmd_skill_verify(args: argparse.Namespace) -> int:
    from eaa.skills import SkillError

    try:
        bao_cao = _so_ky_nang(args).verify(args.name)
    except SkillError as exc:
        raise CliError(str(exc)) from None
    print(bao_cao.render())
    if bao_cao.passed:
        print(f"\nBước tiếp — CHỈ bạn làm được: eaa skill approve {args.name} --actor <tên bạn>")
        return EXIT_OK
    return EXIT_WAITING_GATE


def cmd_skill_approve(args: argparse.Namespace) -> int:
    """Người duyệt một kỹ năng. KHÔNG nằm trong danh mục Agent tự gọi."""
    from eaa.skills import SkillError

    try:
        s = _so_ky_nang(args).approve(args.name, by=args.actor or os.environ.get("USER", ""))
    except SkillError as exc:
        raise CliError(str(exc)) from None
    print(f"Đã duyệt kỹ năng {s.name} — {s.approved_by} lúc {s.approved_at}")
    print(f"Gọi nó:  eaa skill run {s.name}"
          + (f" --args '{{\"{s.params[0]}\": ...}}'" if s.params else ""))
    return EXIT_OK


def cmd_skill_run(args: argparse.Namespace) -> int:
    from eaa.options import OptionError, boc_json
    from eaa.skills import SkillError

    try:
        tham_so = boc_json(args.args) if args.args.strip() not in ("", "{}") else {}
    except OptionError as exc:
        raise CliError(f"--args phải là JSON: {exc}") from None
    try:
        lan = _so_ky_nang(args).run(args.name, tham_so)
    except SkillError as exc:
        raise CliError(str(exc)) from None
    print(lan.render(full=args.full))
    return EXIT_OK if lan.ok else EXIT_WAITING_GATE


def cmd_focus(args: argparse.Namespace) -> int:
    """Còn gì chặn giữa đây và việc muốn làm — cả quãng đường, một lần (C10.2)."""
    from eaa.focus import analyse
    from eaa.orchestrator import OrchestratorConfig
    from eaa.policy import GATE_PURPOSE
    from eaa.readiness import NotReady

    project = resolve_project(args.project)
    ctx = build_context(project)
    state = ctx.store.load()

    # Đo từng câu hỏi Ở ĐÂY rồi truyền xuống, để eaa/focus.py không phát biểu
    # lại luật nào — trùng luật ở hai chỗ là cách chúng lệch nhau về sau.
    ten_cong = {
        getattr(g, "name", type(g).__name__) for g in ctx.orchestrator.gate_chain
    }
    thieu_cong = [c for c in OrchestratorConfig().required_gates if c not in ten_cong]

    # Công cụ ngoài: hỏi doctor chứ không tự dò. Hai bộ dò công cụ lệch nhau
    # thì cái lỏng hơn luôn là cái được tin.
    thieu_cong_cu: list[tuple[str, tuple[str, ...]]] = []
    try:
        for bc in _tao_doctor(project).scan():
            if bc.blocking:
                thieu_cong_cu.append((bc.spec.name, tuple(bc.spec.gates)))
    except Exception:  # noqa: BLE001 - không dò được thì im, đừng báo nhầm là ĐỦ
        thieu_cong_cu = []

    muc = state.module(args.module_id)
    xung_dot: list = []
    loi_tri_thuc = ""
    if muc is not None:
        xung_dot = list(ctx.graph.check_module(
            args.module_id, uses=muc.uses, depends_on=muc.depends_on))
        # Bộ kiểm đủ-tri-thức thuộc về Orchestrator, không phải AppContext:
        # nó là một phần của vòng lặp chuẩn, và nối dây nó ở hai chỗ là hai chỗ
        # sẽ dùng hai bộ luật khác nhau.
        kiem_tri_thuc = getattr(ctx.orchestrator, "readiness", None)
        if not xung_dot and kiem_tri_thuc is not None:
            try:
                kiem_tri_thuc.check(args.module_id, uses=muc.uses)
            except NotReady as exc:
                loi_tri_thuc = str(exc)

    lo_trinh = analyse(
        module_id=args.module_id,
        state=state,
        gate_purpose=GATE_PURPOSE,
        missing_chain_gates=thieu_cong,
        missing_tools=thieu_cong_cu,
        conflicts=xung_dot,
        readiness_error=loi_tri_thuc,
    )
    print(lo_trinh.render())

    if lo_trinh.ready:
        print()
        print(f"    eaa gen {args.module_id}")
        return EXIT_OK

    if not args.run:
        return EXIT_WAITING_GATE

    tu_lo = lo_trinh.agent_steps
    if not tu_lo:
        print()
        print("Không chặng nào tôi tự lo được — chặng kế tiếp phải là bạn.")
        return EXIT_WAITING_GATE

    from eaa.agent import _chay_cli

    print()
    _in_tieu_de("Chạy những chặng tôi tự lo được")
    for p in tu_lo:
        ma, dau_ra = _chay_cli(list(p.fix))
        print(f"  {'✓' if ma == 0 else '✗'} eaa {' '.join(p.fix)}   (mã {ma})")
        if ma != 0:
            print(f"      {dau_ra.strip().splitlines()[-1][:200] if dau_ra.strip() else ''}")
            print("\nDừng ở đây: chặng sau chạy trên kết quả của chặng này.")
            return EXIT_WAITING_GATE

    print()
    print("Chạy lại 'eaa focus' để xem quãng đường còn lại.")
    return EXIT_WAITING_GATE


def cmd_suggest(args: argparse.Namespace) -> int:
    """Tự nhìn lại (C6.1, C8.5, N-906)."""
    from eaa.agent import CHAT_LOG
    from eaa.playbook import Playbook
    from eaa.skills import mine
    from eaa.suggest import analyse
    from eaa.toolusage import UsageLog

    project = resolve_project(args.project)
    goc = repo_root()
    bao_cao = analyse(
        chat_log=project / CHAT_LOG,
        usage_log=UsageLog(goc),
        playbook=Playbook(goc),
        mined=mine(project / CHAT_LOG, min_count=args.min_count),
        min_count=args.min_count,
    )
    print(bao_cao.render())
    return EXIT_OK


def cmd_assess(args: argparse.Namespace) -> int:
    """Gói này có đáng cài không (C3.3, C3.4)."""
    from eaa.toolassess import AssessError, assess
    from eaa.web import WebCache, WebFetcher

    f = WebFetcher(cache=WebCache(repo_root() / "memory" / "web_cache"))
    try:
        kq = assess(args.name, registry=args.registry, fetcher=f,
                    similar_to=args.similar_to)
    except AssessError as exc:
        raise CliError(str(exc)) from None
    print(kq.render())
    return EXIT_OK if kq.clean else EXIT_WAITING_GATE


def _nhat_ky_go_loi(args: argparse.Namespace):
    from eaa.debugsession import SessionLog

    return SessionLog(resolve_project(args.project))


def cmd_debug_plan(args: argparse.Namespace) -> int:
    """Dựng kế hoạch phiên gỡ lỗi sâu (N-085, mức T0)."""
    from eaa.debugsession import build_plan
    from eaa.diagnostics import DiagnosticError, ScenarioLibrary

    project = resolve_project(args.project)

    kich_ban = None
    if args.scenario:
        try:
            thu_vien = ScenarioLibrary.load(project / "diagnostics.yaml")
            kich_ban = thu_vien.get(args.scenario)
        except DiagnosticError as exc:
            raise CliError(f"{exc}\n    Xem danh sách: eaa diagnose list") from None

    cong = []
    try:
        from eaa.serialport import list_ports

        cong = list(list_ports())
    except Exception:  # noqa: BLE001 - không dò được cổng thì kế hoạch vẫn dựng được
        pass

    dung_cu: tuple[str, ...] = ()
    try:
        dung_cu = tuple(getattr(_nap_pack(project), "debug_tools", ()) or ())
    except Exception:  # noqa: BLE001 - chưa nạp được pack thì kế hoạch vẫn dựng được
        pass

    print(build_plan(scenario=kich_ban, ports=cong, tools=dung_cu).render())
    return EXIT_OK


def cmd_debug_log(args: argparse.Namespace) -> int:
    print(_nhat_ky_go_loi(args).render())
    return EXIT_OK


def cmd_debug_record(args: argparse.Namespace) -> int:
    from eaa.debugsession import DebugError

    try:
        ban = _nhat_ky_go_loi(args).record(
            actor=args.actor or os.environ.get("USER", ""),
            note=args.note, scenario_id=args.scenario,
            outcome=args.outcome, tool=args.tool,
        )
    except DebugError as exc:
        raise CliError(str(exc)) from None
    print("Đã ghi phiên gỡ lỗi:")
    print(ban.render())
    return EXIT_OK


def _tu_khoi_tao_neu_la_nhap(project: Path, args: argparse.Namespace) -> bool:
    """Khởi tạo hộ, NHƯNG chỉ ở chỗ làm nháp. Trả về ``True`` nếu đã làm.

    Ranh giới ở đây có chủ ý và hẹp. Trên một dự án thật, ``eaa init`` là một
    quyết định: nó đọc ràng buộc đã chốt, chọn nhà cung cấp mô hình, và ghi
    Project State — người dùng cần biết mình vừa bắt đầu cái gì. Làm hộ ở đó là
    lấy mất một quyết định.

    Ở chỗ làm nháp thì không có gì để lấy: ràng buộc do máy sinh sẵn và mang
    nhãn GIẢ ĐỊNH, nên bước khởi tạo chỉ còn là thủ tục. Bắt gõ nó là dựng lại
    đúng cái cửa vào mà ``eaa scratch`` sinh ra để hạ xuống.
    """
    from eaa.scratch import is_scratch

    if (project / STATE_FILE).is_file() or not is_scratch(project):
        return False

    print("Chỗ làm nháp chưa khởi tạo — tôi tự làm bước ấy (ở đây nó chỉ là thủ tục).")
    cmd_init(argparse.Namespace(
        project=str(project), force=False,
        provider=getattr(args, "provider", "") or "",
        model=getattr(args, "model", "") or "",
    ))
    print()
    return True


def cmd_tool_rollback(args: argparse.Namespace) -> int:
    """Quay về bản công cụ đã duyệt gần nhất (C7.3)."""
    from eaa.toolforge import ForgeError

    try:
        t = _xuong_cong_cu(args).rollback(args.name)
    except ForgeError as exc:
        raise CliError(str(exc)) from None
    print(f"Đã quay {t.name} về bản trước — trạng thái: {t.status}")
    print(f"  {t.note}")
    print(f"\nBước tiếp: eaa tool verify {t.name}")
    return EXIT_OK


def cmd_tool_doc(args: argparse.Namespace) -> int:
    """Sinh tài liệu cho một công cụ tự sinh (C6.8)."""
    from eaa.toolforge import ForgeError, ToolRegistry
    from eaa.toolusage import UsageLog

    goc = repo_root()
    try:
        van_ban = _xuong_cong_cu(args).document(args.name, usage=UsageLog(goc))
    except ForgeError as exc:
        raise CliError(str(exc)) from None

    if args.save:
        dich = ToolRegistry(goc).dir / f"{args.name}.md"
        dich.write_text(van_ban + "\n", encoding="utf-8")
        print(f"Đã ghi {dich}")
        return EXIT_OK
    print(van_ban)
    return EXIT_OK


def cmd_scratch(args: argparse.Namespace) -> int:
    """Dựng chỗ làm nháp (C10.1)."""
    from eaa.scratch import ScratchError, create_scratch, warning_banner

    try:
        goc = create_scratch(repo_root(), name=args.name,
                             platform=args.platform, force=args.force)
    except ScratchError as exc:
        raise CliError(str(exc)) from None

    print(f"Chỗ làm nháp: {goc}")
    print()
    print(warning_banner(goc))
    print()

    # Khởi tạo luôn: ở chỗ nháp bước ấy không quyết định gì (xem
    # ``_tu_khoi_tao_neu_la_nhap``), và bắt gõ nó là để lại đúng một bậc thềm
    # nữa ở cửa vào mà lệnh này sinh ra để dọn.
    if not (goc / STATE_FILE).is_file():
        cmd_init(argparse.Namespace(project=str(goc), force=False, provider="", model=""))
        print()

    print("Dùng nó ngay:")
    print(f"  export EAA_PROJECT={goc}")
    print('  eaa chat "viết giúp tôi một hàm đọc kênh ADC"')
    return EXIT_OK


def _doc_tep_trong_kho(project: Path, duong_dan: str) -> int:
    """Đọc MỘT tệp trong kho đã giải nén — kể cả PDF (SL-94).

    Chặn ở đây chứ không tin đường dẫn: tham số này do mô hình điền, và một
    ``../../..`` trong đó là đường đọc bất cứ tệp nào trên máy. Mọi đường dẫn
    phải nằm trong ``<dự án>/sources/`` sau khi đã giải hết liên kết mềm.
    """
    from eaa.pdftext import PdfError, extract_text

    goc = (project / "sources").resolve()
    tep = (goc / duong_dan).resolve() if not Path(duong_dan).is_absolute() \
        else Path(duong_dan).resolve()
    if not (tep == goc or goc in tep.parents):
        raise CliError(
            f"Chỉ đọc được tệp nằm trong {goc}. Đường dẫn {duong_dan!r} trỏ ra "
            "ngoài — từ chối, vì một đường dẫn trỏ ra ngoài kho không phải một "
            "tệp tài liệu."
        )
    if not tep.is_file():
        raise CliError(f"Không có tệp: {tep}")

    if tep.suffix.lower() == ".pdf":
        try:
            kq = extract_text(tep)
        except PdfError as exc:
            raise CliError(str(exc)) from None
        print(kq.render())
        return EXIT_OK if not kq.empty else EXIT_WAITING_GATE

    from eaa.archive import _doc_van_ban

    noi_dung = _doc_van_ban(tep)
    if not noi_dung.strip():
        raise CliError(
            f"{tep.name} không đọc được thành chữ. Nếu là ảnh hoặc tệp nhị "
            "phân thì hệ này chưa có công cụ đọc nó."
        )
    print(f"── {tep.relative_to(goc)}  ({len(noi_dung)} ký tự)")
    print()
    print(noi_dung)
    return EXIT_OK


def _liet_ke_trong_kho(project: Path, mau: str) -> int:
    """Liệt kê tệp trong kho đã giải nén khớp một mẫu.

    Bản khảo sát tổng phải cắt bớt để không nuốt hết ngân sách ngữ cảnh, và
    cái bị cắt thì Agent không biết là có. Đo được ở bài kiểm BLKLab: Agent mô
    tả đúng phần nó thấy nhưng bỏ sót hai cảm biến chỉ vì chúng nằm ngoài phần
    tóm tắt. Lệnh này để soi kỹ MỘT phần, thay vì phải in tất cả mọi lúc.
    """
    goc = (project / "sources").resolve()
    if not goc.is_dir():
        raise CliError(
            f"Chưa có kho nào được giải nén ở {goc}. "
            "Chạy 'eaa survey <tệp .zip> --extract' trước."
        )

    tim = sorted(p for p in goc.rglob(mau) if p.is_file())
    print(f"Tệp khớp {mau!r} trong kho đã giải nén")
    print()
    if not tim:
        print(f"  (không có tệp nào khớp)")
        return EXIT_OK
    for p in tim[:200]:
        co = p.stat().st_size
        print(f"  {p.relative_to(goc)}   ({co:,} byte)".replace(",", "."))
    print()
    print(f"{len(tim)} tệp." + (f" (in 200 đầu)" if len(tim) > 200 else ""))
    print("Đọc một tệp:  eaa survey --read '<đường dẫn ở trên>'")
    return EXIT_OK


def cmd_survey(args: argparse.Namespace) -> int:
    """N-004, FR-ING-01 — khảo sát một kho nén hồ sơ dự án."""
    from eaa.archive import ArchiveError, read_archive

    project = resolve_project(args.project)

    if getattr(args, "read", ""):
        return _doc_tep_trong_kho(project, args.read)

    if getattr(args, "files", ""):
        return _liet_ke_trong_kho(project, args.files)

    if not args.archive:
        raise CliError(
            "Cần đường dẫn tệp .zip, hoặc --read <tệp> / --files <mẫu> để soi "
            "kho đã giải nén."
        )

    dich = None
    if args.extract:
        dich = project / "sources" / Path(args.archive).stem

    try:
        khao_sat = read_archive(args.archive, extract_to=dich)
    except ArchiveError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Khảo sát kho tài liệu")
    print(khao_sat.render())

    if not args.extract:
        print(
            "\n  Mới đọc mục lục, chưa ghi gì ra đĩa. Thêm --extract để giải ra\n"
            f"  {project / 'sources'} và giữ bản gốc làm bằng chứng."
        )
    return EXIT_OK


def cmd_chat(args: argparse.Namespace) -> int:
    """Nói bằng tiếng Việt, Agent tự chọn và chạy lệnh để trả lời."""
    from eaa.agent import MAX_STEPS, AgentError, AgentLoop

    project = resolve_project(args.project)
    _tu_khoi_tao_neu_la_nhap(project, args)
    ctx = build_context(project)
    vong = AgentLoop(llm=ctx.llm, project=project, max_steps=args.max_steps)

    def _mot_luot(cau_hoi: str) -> int:
        try:
            ket = vong.ask(cau_hoi)
        except AgentError as exc:
            raise CliError(str(exc)) from exc
        print(ket.render())
        if ket.clarifying:
            return EXIT_WAITING_GATE
        if ket.suggested:
            return EXIT_WAITING_GATE
        return EXIT_OK

    if args.question:
        return _mot_luot(" ".join(args.question))

    if not sys.stdin.isatty():
        raise CliError(
            "Không có terminal nên không mở được phiên hội thoại.\n"
            "    Hỏi một câu trực tiếp: eaa chat \"câu hỏi của bạn\""
        )

    _in_tieu_de("Hội thoại với Agent")
    print(
        "Nói điều bạn muốn bằng tiếng Việt. Tôi tự chạy các lệnh chỉ-đọc và các\n"
        "lệnh đề xuất để tìm câu trả lời.\n\n"
        "Điều tôi KHÔNG tự làm: quyết định tại gate, nạp firmware, cài công cụ,\n"
        "phong hạng. Những việc ấy tôi chỉ soạn lệnh để bạn chạy.\n\n"
        f"Trần {MAX_STEPS} bước mỗi lượt. Gõ 'thoát' để dừng.\n"
    )

    while True:
        try:
            cau_hoi = input("bạn > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return EXIT_OK
        if not cau_hoi:
            continue
        if cau_hoi.lower() in ("thoát", "thoat", "exit", "quit", ":q"):
            return EXIT_OK
        print()
        _mot_luot(cau_hoi)
        print()


def cmd_deviations(args: argparse.Namespace) -> int:
    """N-905 — Agent tự phát hiện chỗ mã và tài liệu kể hai câu chuyện khác nhau."""
    from eaa.deviation import DeviationError, scan

    goc = Path(__file__).resolve().parent.parent

    # Danh sách lệnh lấy từ CHÍNH bộ phân tích đối số đang chạy, không chép tay:
    # chép tay thì nó lệch ngay lần thêm lệnh tiếp theo, và một bộ dò sai lệch
    # tự nó lệch là thứ tệ hơn không có.
    bo_phan_tich = build_parser()
    lenh: list[str] = []
    for hanh_dong in bo_phan_tich._subparsers._group_actions if bo_phan_tich._subparsers else []:
        lenh.extend(getattr(hanh_dong, "choices", {}) or {})

    try:
        ket_qua = scan(goc, cli_commands=sorted(set(lenh)))
    except DeviationError as exc:
        raise CliError(str(exc)) from exc

    _in_tieu_de("Sai lệch so với thiết kế")
    print(ket_qua.render())

    if args.draft and ket_qua.found:
        print("\n" + "─" * 70)
        print("Nháp để dán vào docs/SAI_LECH_THIET_KE.md:\n")
        print(ket_qua.draft_all())

    return EXIT_OK if ket_qua.clean else EXIT_WAITING_GATE


def cmd_handover(args: argparse.Namespace) -> int:
    """N-094, N-101, N-103 — bàn giao, đổi linh kiện, cập nhật hiện trường."""
    from eaa.handover import (
        HandoverError,
        LlmSwapAnalyst,
        OperationsHandbook,
        RolloutPlan,
    )

    project = resolve_project(args.project)
    ctx = build_context(project)
    state = ctx.store.load()

    try:
        if args.handover_action == "doc":
            from eaa.diagnostics import ScenarioLibrary
            from eaa.docplan import ERRATA_FILE, ErrataAnalysis
            from eaa.flash import FLASH_LOG, FlashLog
            from eaa.safety import SAFETY_FILE, SafetyAnalysis

            thu_vien = (
                ScenarioLibrary.load(project / "diagnostics.yaml")
                if (project / "diagnostics.yaml").is_file()
                else None
            )
            so_tay = OperationsHandbook(
                project=project.name,
                hardware=ctx.kb.hardware,
                constraints=ctx.kb.constraints,
                scenarios=thu_vien.scenarios if thu_vien else (),
                safety=SafetyAnalysis.load(project / SAFETY_FILE),
                errata=ErrataAnalysis.load(project / ERRATA_FILE),
                flash_log=FlashLog(project / FLASH_LOG),
            )
            van_ban = so_tay.render()

            if args.publish:
                from eaa.registry import ArtifactRegistry

                kho = ArtifactRegistry(project / "deliverables")
                pham_xuat = kho.publish(
                    family="tai_lieu_van_hanh",
                    kind="md",
                    title=f"Tài liệu vận hành — {project.name}",
                    content=van_ban,
                    description="Sinh từ dữ liệu dự án bằng 'eaa handover doc'.",
                    lineage={
                        "constraints_version": ctx.kb.constraints.content_version,
                        "hardware_version": ctx.kb.hardware.content_version,
                    },
                )
                print(f"Đã đăng ký phẩm xuất: {pham_xuat.id} → {pham_xuat.path}")
            else:
                print(van_ban)
                print(
                    "\n<!-- Chưa đăng ký vào kho phẩm xuất. Thêm --publish để lưu "
                    "bản có phiên bản và có dòng dõi dữ liệu. -->"
                )
            return EXIT_OK if not so_tay.limitations() else EXIT_WAITING_GATE

        if args.handover_action == "swap":
            ngoai_vi = [str(p.get("id", "")) for p in ctx.kb.hardware.peripherals]
            thanh_ghi = sorted(
                {
                    r
                    for nv in ngoai_vi
                    if nv
                    for r in ctx.kb.hardware.registers_of(nv)
                }
            )
            ban = LlmSwapAnalyst(llm=ctx.llm).compare(
                old_part=args.old,
                new_part=args.new,
                used_for=args.used_for,
                registers=thanh_ghi,
            )
            _in_tieu_de("Đổi linh kiện — ĐỀ XUẤT")
            print(ban.render(ctx.kb.hardware, state.backlog, ctx.graph))
            return EXIT_WAITING_GATE

        if args.handover_action == "rollout":
            from eaa.versions import VersionRegistry

            hien_tai = ctx.repo.head()
            known_good = args.rollback_to
            if not known_good:
                # Bản để quay lui phải là bản ĐÃ TỪNG chạy trên thiết bị, nên
                # nó lấy từ known_good.lock — nơi chỉ được cập nhật tại G4 sau
                # khi có số đo vật lý (FR-VER-02), chứ không lấy từ commit nào
                # đó trông có vẻ ổn định.
                known_good = str(VersionRegistry(project).known_good().get("firmware", ""))

            ke_hoach = RolloutPlan.default(
                from_commit=args.from_commit or known_good,
                to_commit=args.to_commit or hien_tai,
                rollback_to=known_good,
            )
            _in_tieu_de("Cập nhật thiết bị đã triển khai — ĐỀ XUẤT")
            print(ke_hoach.render())
            print(
                "\nCon số ở mỗi bậc là ĐỀ XUẤT: quy mô triển khai thật là thứ engine\n"
                "không biết. Điều KHÔNG thương lượng là bậc đầu có đúng một thiết bị."
            )
            return EXIT_OK if ke_hoach.ok else EXIT_WAITING_GATE
    except HandoverError as exc:
        raise CliError(str(exc)) from exc

    raise CliError(f"Hành động không hợp lệ: {args.handover_action!r}")


def cmd_field(args: argparse.Namespace) -> int:
    """N-102 — chẩn đoán sự cố ngoài hiện trường."""
    from eaa.diagnostics import (
        CHUA_THU,
        KHONG_TAI_HIEN,
        TAI_HIEN_DUOC,
        DiagnosticError,
        FieldCase,
        ScenarioLibrary,
    )

    project = resolve_project(args.project)
    try:
        thu_vien = ScenarioLibrary.load(project / "diagnostics.yaml")
    except DiagnosticError as exc:
        raise CliError(str(exc)) from exc

    dieu_kien: dict[str, Any] = {}
    for muc in args.condition or []:
        if "=" not in muc:
            raise CliError(f"Điều kiện phải có dạng khóa=giá_trị, nhận {muc!r}")
        khoa, gia_tri = muc.split("=", 1)
        dieu_kien[khoa.strip()] = gia_tri.strip()

    ca = FieldCase(
        symptom=args.symptom,
        conditions=dieu_kien,
        occurrences=args.occurrences,
        reproduced={
            "co": TAI_HIEN_DUOC,
            "khong": KHONG_TAI_HIEN,
            "chua": CHUA_THU,
        }[args.reproduced],
        scenarios=tuple(args.scenario or []),
    )

    _in_tieu_de("Chẩn đoán sự cố hiện trường")
    print(ca.render(thu_vien))
    return EXIT_OK if ca.reproduced == TAI_HIEN_DUOC else EXIT_WAITING_GATE


def cmd_endurance(args: argparse.Namespace) -> int:
    """N-086 — chạy dài, phát hiện reset qua bộ đếm thời gian chạy."""
    from eaa.endurance import analyse
    from eaa.telemetry import load_frame_spec, read_capture

    project = resolve_project(args.project)
    _in_tieu_de("Kiểm độ bền dài hạn")

    if args.replay:
        ban_thu = read_capture(args.replay, load_frame_spec(project / "diagnostics.yaml"))
    else:
        if not args.seconds:
            raise CliError(
                "Chưa nêu chạy bao lâu. Ví dụ: eaa endurance --seconds 600\n"
                "    Con số này là thứ quyết định kết luận nói được về quãng nào,\n"
                "    nên nó không có mặc định."
            )
        ban_thu = _thu_telemetry(project, args.port, args.seconds)
        if args.save:
            ban_thu.write(args.save)

    print(ban_thu.render())
    print()

    yeu_cau = args.required
    if yeu_cau <= 0:
        # Lấy từ tiêu chí nghiệm thu của dự án nếu có — ngưỡng đã chốt ở G1
        # đáng tin hơn một con số gõ vội trên dòng lệnh.
        ctx_kb = _nap_kho(Constraints.load, project / "constraints.yaml")
        for m in (ctx_kb.acceptance.get("measurements") or []):
            if str(m.get("key")) == args.key and m.get("min") is not None:
                yeu_cau = float(m["min"])
                break

    bao_cao = analyse(
        ban_thu,
        uptime_key=args.key,
        required_s=yeu_cau,
        drift_keys=tuple(args.drift or []),
    )
    print(bao_cao.render())
    return EXIT_OK if bao_cao.ok else EXIT_WAITING_GATE


def _doc_tra_loi_nguoi(cap: Sequence[str]) -> dict[str, bool]:
    dung = {"co", "có", "yes", "y", "true", "1"}
    sai = {"khong", "không", "no", "n", "false", "0"}
    ket_qua: dict[str, bool] = {}
    for muc in cap:
        if "=" not in muc:
            raise CliError(f"Câu trả lời phải có dạng khóa=giá_trị, nhận {muc!r}")
        khoa, gia_tri = muc.split("=", 1)
        gia_tri = gia_tri.strip().lower()
        if gia_tri in dung:
            ket_qua[khoa.strip()] = True
        elif gia_tri in sai:
            ket_qua[khoa.strip()] = False
        else:
            raise CliError(f"Không hiểu câu trả lời {gia_tri!r} cho {khoa!r}")
    return ket_qua


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

    if args.report_kind == "versions":
        ctx = build_context(project)
        kho = _tao_versions(project, ctx.repo)
        _in_tieu_de("Phiên bản mã theo hạng chất lượng")
        print(kho.report())
        return EXIT_OK

    if args.report_kind == "bench":
        from eaa.bench import doc_bo_chuan

        _in_tieu_de("Thước đo")
        try:
            ket_qua = doc_bo_chuan(project / BENCH_FILE)
        except Exception as exc:  # noqa: BLE001
            raise CliError(str(exc)) from exc
        print(ket_qua.render())
        return EXIT_OK

    if args.report_kind == "retrieval":
        from eaa.goldenset import GOLDEN_FILE, GoldenSet, GoldenSetError

        ctx = build_context(project)
        try:
            bo_chuan = GoldenSet.load(project / GOLDEN_FILE)
        except GoldenSetError as exc:
            raise CliError(str(exc)) from exc
        if bo_chuan is None:
            raise CliError(
                f"Dự án chưa có bộ chuẩn truy xuất ({project / GOLDEN_FILE}).\n"
                "    Với module nào thì trích đoạn nào ĐÚNG LÀ liên quan — câu ấy\n"
                "    do người viết ra một lần, rồi máy đối chiếu mãi."
            )

        sai = bo_chuan.check_ids(ctx.kb.datasheets)
        if sai:
            raise CliError(
                "Bộ chuẩn trỏ tới chunk không có thật:\n"
                + "\n".join(f"    · {s}" for s in sai)
                + "\n    Một đáp án trỏ vào hư không kéo precision xuống mãi mãi mà"
                "\n    chẳng vì lỗi nào của bộ chọn — và người ta sẽ đi sửa bộ chọn."
            )

        _in_tieu_de("Bộ chuẩn truy xuất")
        # Đo ĐÚNG đường truy xuất mà prompt dùng — cả hai tầng.
        bao_cao = bo_chuan.evaluate(ctx.graph, datasheets=ctx.kb.datasheets)
        print(bao_cao.render())
        return EXIT_OK if bao_cao.ok else EXIT_REPAIR_LIMIT

    if args.report_kind == "review":
        from eaa.ledger import ErrorLedger

        kpi = KpiLogger(project / "kpi_log.csv")
        so_ao_giac = ErrorLedger(project / "error_ledger.jsonl")
        _in_tieu_de("Tự đánh giá quy trình")
        print(kpi.weak_points(ledger=so_ao_giac).render())
        return EXIT_OK

    if args.report_kind != "kpi":
        raise CliError(f"Chưa có loại báo cáo {args.report_kind!r}.")

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
    # Cờ toàn cục chứ không phải cờ của từng lệnh: nếu chỉ vài lệnh nhận được
    # thì người dùng phải nhớ lệnh nào nhận, và một lần nhớ sai là một lượt
    # chạy bằng model khác với ý định.
    parser.add_argument(
        "--model",
        default="",
        metavar="<mã>",
        help="Đổi mô hình cho RIÊNG lượt chạy này, không ghi vào Project State. "
             "Xem lựa chọn: eaa models",
    )

    sub = parser.add_subparsers(dest="command", metavar="<lệnh>")

    p_design = sub.add_parser(
        "design",
        help="Dựng tài liệu thiết kế từ hồ sơ dự án: URD, SRS, SDD, chức năng, luồng",
    )
    s_design = p_design.add_subparsers(dest="hanh_dong", metavar="<hành động>")
    p_dl = s_design.add_parser("list", help="Khuôn mẫu và định dạng đang có")
    p_dl.set_defaults(func=cmd_design_list)
    p_dg = s_design.add_parser("gen", help="Dựng một tài liệu")
    p_dg.add_argument("kind", help="Loại tài liệu: urd, srs, sdd, chuc_nang, luong")
    p_dg.add_argument("--format", default="", metavar="<md|docx|xlsx|pptx|pdf>",
                      help="Định dạng xuất; bỏ trống thì lấy mặc định của khuôn mẫu")
    p_dg.add_argument("--out", default="", help="Đường dẫn tệp ra")
    p_dg.add_argument(
        "--at", default="",
        help="Mốc thời gian ghi vào tài liệu. Nêu nó thì hai lần dựng từ cùng "
             "dữ liệu ra hai tệp so sánh được với nhau",
    )
    p_dg.set_defaults(func=cmd_design_gen)
    p_design.set_defaults(func=cmd_design_list)

    p_models = sub.add_parser(
        "models",
        help="Danh mục mô hình đã kiểm — để người chọn, hệ không tự chọn",
    )
    p_models.add_argument("--provider", default="", help="Chỉ in của một nhà cung cấp")
    p_models.set_defaults(func=cmd_models)

    p_init = sub.add_parser("init", help="Khởi tạo dự án và Project State (UC01)")
    p_init.add_argument("--force", action="store_true", help="Khởi tạo lại dù đã có state")
    p_init.add_argument(
        "--provider",
        default="",
        help="Nhà cung cấp LLM; bỏ trống thì Agent tự chọn theo môi trường",
    )
    p_init.add_argument(
        "--model",
        default=argparse.SUPPRESS,
        help="Mã mô hình, GHIM vào Project State (khác cờ --model toàn cục — cờ ấy "
             "chỉ đổi cho một lượt chạy). Bỏ trống thì lấy mặc định của adapter",
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
    pp = plan_sub.add_parser(
        "propose", help="Agent đề xuất phân rã module (N-040..N-043)"
    )
    pp.add_argument("--goal", default="", help="Mục tiêu; bỏ trống thì lấy từ hồ sơ")

    pac = plan_sub.add_parser("accept", help="Nhận bản phân rã vào backlog")
    pac.add_argument(
        "--du-biet-qua-tai",
        dest="du_biet_qua_tai",
        action="store_true",
        help="Nhận dù ước lượng tải CPU vượt trần",
    )

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
    pr = plan_sub.add_parser(
        "reopen",
        help="Đưa module đã merge về todo để sinh lại (bắt buộc kèm lý do)",
        description=(
            "Mở lại mã đã merge là gỡ một quyết định G3 đã có người bấm, nên "
            "lệnh này đòi --reason và ghi vào Error Ledger. Nó KHÔNG nới lỏng "
            "bất biến nào: module quay về todo và phải đi lại trọn vòng lặp "
            "chuẩn rồi qua G3 một lần nữa. Mã trên nhánh chính giữ nguyên cho "
            "tới khi bản mới được duyệt."
        ),
    )
    pr.add_argument("module_id")
    pr.add_argument(
        "--reason", required=True, help="Vì sao mã đã duyệt cần viết lại — vào Error Ledger"
    )
    p_plan.set_defaults(func=cmd_plan)

    # UC04 — vòng lặp sinh mã
    p_gen = sub.add_parser(
        "gen",
        help="Chạy vòng lặp sinh mã chuẩn cho module (UC04)",
        description=(
            "'--draft' chạy một tập cổng nhẹ hơn để thử nhanh. Bản nháp KHÔNG "
            "merge được — và không phải vì bị chặn, mà vì nó không để lại bằng "
            "chứng nào cho bước merge đọc."
        ),
    )
    p_gen.add_argument("module_id")
    p_gen.add_argument(
        "--draft", metavar="CỔNG",
        help="Chế độ nháp: chỉ chạy các cổng này (ngăn phẩy). Ví dụ: --draft compile,static",
    )
    p_gen.add_argument(
        "--preview", action="store_true",
        help="Sinh mã rồi DỪNG: không cổng, không nhánh, không commit. "
             "Dùng khi máy chưa có toolchain và bạn chỉ muốn xem mã",
    )
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
    ga.add_argument(
        "--option",
        default="",
        help="Mã phương án được chọn, bắt buộc khi hồ sơ có nhiều phương án",
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
    p_report.add_argument(
        "report_kind",
        choices=["kpi", "versions", "review", "retrieval", "bench"],
        nargs="?",
        default="kpi",
        help=(
            "kpi = số liệu thô · versions = hạng chất lượng · "
            "review = khâu nào hay hỏng (N-906) · retrieval = bộ chuẩn truy xuất (TC-20) · "
            "bench = pass@k CỘNG bốn trục chưa benchmark nào hỏi (GĐ2)"
        ),
    )
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
            "Chế độ quét chỉ ĐỌC, không đổi gì trên máy. --fix chỉ chạy lệnh cài "
            "mà một người đã duyệt — hỏi ngay tại terminal, hoặc đọc quyết định "
            "đã ghi bằng 'eaa doctor approve'. Không có chế độ tự duyệt."
        ),
    )
    # `eaa doctor approve <công cụ>...` — quyết định của NGƯỜI, ghi vào sổ để
    # nó sống ngoài phiên chạy đã sinh ra nó. Không có nó thì mọi phiên không
    # terminal đều cụt đường ở chỗ cài, dù người có đồng ý bao nhiêu lần.
    p_doctor.add_argument(
        "action", nargs="?", choices=["approve"],
        help="approve <công cụ>...: bạn duyệt lệnh cài, sau đó 'doctor --fix' chạy nó",
    )
    p_doctor.add_argument("tools", nargs="*", help="Tên công cụ cần duyệt lệnh cài")
    p_doctor.add_argument(
        "--actor", default="", help="Tên người duyệt (bắt buộc khi 'doctor approve')"
    )
    p_doctor.add_argument(
        "--fix", action="store_true",
        help="Cài công cụ thiếu: hỏi tại terminal, hoặc chạy lệnh bạn đã duyệt",
    )
    p_doctor.add_argument(
        "--discover",
        action="store_true",
        help="Phát hiện công cụ pack sẽ gọi mà manifest chưa biết (AIS §9.2)",
    )
    p_doctor.add_argument(
        "--propose",
        action="store_true",
        help="Tra cứu và đề xuất công cụ chưa biết; đề xuất phải qua gate mới vào manifest",
    )
    p_doctor.add_argument(
        "--accept-drift",
        action="store_true",
        dest="accept_drift",
        help="Chấp nhận môi trường hiện tại và cập nhật env_lock.json",
    )
    p_doctor.add_argument(
        "--plan",
        action="store_true",
        help="Kế hoạch cài: THỨ TỰ theo phụ thuộc, cách cài từng cái, và chỗ "
             "hai thẻ công cụ đòi cùng một thứ ở hai phiên bản đá nhau",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    # Phát hiện của quy trình ở dạng bảng lỗi biên tập — E2 (SL-184)
    p_pb = sub.add_parser(
        "problems",
        help="Mọi phát hiện của quy trình, dạng bảng lỗi cho biên tập (E2)",
    )
    p_pb.add_argument("--module", default="", help="Chỉ một module")
    p_pb.add_argument("--all", action="store_true",
                      help="Kể cả phát hiện thuộc lịch sử đã khép")
    p_pb.add_argument("--limit", type=int, default=0,
                      help="Chỉ in N phát hiện đầu (dạng chữ)")
    p_pb.set_defaults(func=cmd_problems)

    # Thủ tục theo ngoại vi — V4 (SL-180)
    p_pr = sub.add_parser(
        "procedure", help="Thủ tục đã đúc kết cho từng ngoại vi (lớp K9, V4)"
    )
    pr_sub = p_pr.add_subparsers(
        dest="procedure_action", required=False, metavar="<hành động>"
    )
    pr_sub.add_parser(
        "lint", help="Soi thủ tục: trích dẫn có thật không, bẫy có bằng chứng không"
    )
    p_pr.set_defaults(func=cmd_procedure)

    # AIS §8.5 — kho phẩm xuất
    # Lỗi có kêu lên được không — N-912 (SL-175)
    p_ob = sub.add_parser(
        "observe", help="Module nào chưa nói được nó sống hay chết (N-912)"
    )
    ob_sub = p_ob.add_subparsers(
        dest="observe_action", required=False, metavar="<hành động>"
    )
    ob_set = ob_sub.add_parser("set", help="Khai dấu hiệu sống / dấu hiệu hỏng")
    ob_set.add_argument("module_id")
    ob_set.add_argument("--song", help="Người nhận ra nó ĐANG CHẠY bằng cách nào")
    ob_set.add_argument("--hong", help="Khi nó HỎNG, người nhận ra bằng cách nào")
    p_ob.set_defaults(func=cmd_observe, observe_action=None)

    # Số đo trên chính bo này — N-913 (SL-173)
    p_me = sub.add_parser(
        "measured", help="Sổ số đo trên bo: list/add/approve (N-913)"
    )
    me_sub = p_me.add_subparsers(
        dest="measured_action", required=True, metavar="<hành động>"
    )
    me_sub.add_parser("list", help="Số đo đã duyệt và số đo còn chờ")
    me_a = me_sub.add_parser(
        "add", help="ĐỀ XUẤT một số đo — chưa vào prompt tới khi có người chốt"
    )
    me_a.add_argument("name", help="Tên số đo, ví dụ ACCEL_BALANCE_OFFSET")
    me_a.add_argument("value", help="Giá trị đọc được")
    me_a.add_argument("--unit", help="Đơn vị, ví dụ LSB, Hz, baud")
    me_a.add_argument("--source", help="Đo bằng gì: DS-02, eaa telemetry, tay…")
    me_a.add_argument("--note", help="Điều kiện đo, dải đo, thứ cần biết để đo lại")
    me_ap = me_sub.add_parser(
        "approve", help="CHỐT một số đo — từ đây nó vào prompt sinh mã"
    )
    me_ap.add_argument("name")
    me_ap.add_argument("--actor", required=True, help="Tên người chốt")
    p_me.set_defaults(func=cmd_measured)

    # Vòng đời tri thức — AIS §8.1–8.3, quy trình P9 (SL-172)
    p_kn = sub.add_parser(
        "knowledge",
        help="Vòng đời tri thức: stale/supersede/deprecate (AIS §8.1-8.3)",
    )
    kn_sub = p_kn.add_subparsers(
        dest="knowledge_action", required=True, metavar="<hành động>"
    )
    kn_s = kn_sub.add_parser(
        "stale", help="Mã nào dựa trên một trích đoạn — CHỈ ĐỌC, không đổi gì"
    )
    kn_s.add_argument("chunk_id", help="Mã trích đoạn, ví dụ ds-021")
    kn_sup = kn_sub.add_parser(
        "supersede", help="Thay trích đoạn cũ bằng bản mới — cần duyệt G2"
    )
    kn_sup.add_argument("old_id")
    kn_sup.add_argument("new_id")
    kn_sup.add_argument("--reason", required=True, help="Vì sao bản cũ không còn đúng")
    kn_d = kn_sub.add_parser(
        "deprecate", help="Hạ cấp một trích đoạn khi chưa có bản thay — cần duyệt G2"
    )
    kn_d.add_argument("chunk_id")
    kn_d.add_argument("--reason", required=True, help="Vì sao trích đoạn này sai")
    p_kn.set_defaults(func=cmd_knowledge)

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

    # UC07 — nghiệm thu vật lý tại G4
    p_tune = sub.add_parser(
        "tune", help="Nhập số đo vật lý tại G4, phong hạng hoặc ghi không đạt (UC07)"
    )
    p_tune.add_argument("module_id")
    p_tune.add_argument("--input", help="Tệp measures.yaml chứa số đo đã thực hiện")
    p_tune.add_argument("--port", default="", help="Đọc số đo thẳng từ cổng này")
    p_tune.add_argument(
        "--seconds", type=float, default=0.0, help="Thu bao lâu (mặc định 10s khi có --port)"
    )
    p_tune.add_argument("--out", help="Ghi lại phiên thu làm bằng chứng nghiệm thu")
    p_tune.add_argument("--reject", help="Ghi nhận KHÔNG đạt nghiệm thu, kèm lý do")
    p_tune.add_argument("--actor", help="Người nghiệm thu")
    p_tune.set_defaults(func=cmd_tune)

    # Công đoạn E — ráp firmware
    p_build = sub.add_parser(
        "build",
        help="Ráp các module đã merge thành firmware nạp được",
        description=(
            "Vòng lặp chuẩn kiểm từng module. Lệnh này kiểm điều còn lại: các "
            "module ghép lại có dịch, liên kết và vừa bộ nhớ hay không."
        ),
    )
    p_build.set_defaults(func=cmd_build)

    # N-016, N-017 — phân tích hỏng hóc và chế độ an toàn
    p_safety = sub.add_parser(
        "safety",
        help="Phân tích hỏng hóc và chế độ an toàn (N-016, N-017)",
        description=(
            "Câu hỏi trung tâm không phải 'cái gì có thể hỏng' mà là 'hỏng thì "
            "có ai biết không'. Hệ nhúng không có ai ngồi nhìn."
        ),
    )
    safety_sub = p_safety.add_subparsers(
        dest="safety_action", required=True, metavar="<hành động>"
    )
    sp = safety_sub.add_parser("propose", help="Agent dựng bản phân tích")
    sp.add_argument("--goal", default="", help="Mục tiêu hệ thống")
    sp.add_argument("--force", action="store_true", help="Dựng lại dù đã có bản cũ")
    safety_sub.add_parser("show", help="Xem bản hiện có và chỗ còn hở")
    p_safety.set_defaults(func=cmd_safety)

    # N-041 — sinh giao diện trước thân
    p_iface = sub.add_parser(
        "interface",
        help="Sinh hợp đồng gọi của module TRƯỚC khi sinh thân (N-041)",
        description=(
            "Giao diện có trước thì hai thân module viết song song được, mỗi "
            "bên chỉ trông vào lời hứa của bên kia. Mỗi hàm phải trả lời ba "
            "câu chữ ký không nói được: gọi trong ngắt được không, có chặn "
            "không, tái nhập được không."
        ),
    )
    p_iface.add_argument("module", help="Mã module trong backlog")
    p_iface.add_argument(
        "--write", action="store_true", help="Ghi tệp tiêu đề vào firmware/"
    )
    p_iface.set_defaults(func=cmd_interface)

    # N-004, N-030 — tài liệu đích danh và trang đích danh
    p_sources = sub.add_parser(
        "sources",
        help="Tài liệu cần và trang cần trích, nêu đích danh (N-004, N-030)",
        description=(
            "Không phải 'hãy đưa datasheet' mà là một danh sách đích danh — và "
            "trong mỗi tài liệu, đích danh phần cần trích. Một datasheet vài "
            "trăm trang chỉ cho ra vài chục trích đoạn có ích."
        ),
    )
    sources_sub = p_sources.add_subparsers(
        dest="sources_action", required=True, metavar="<hành động>"
    )
    sn = sources_sub.add_parser("need", help="Danh sách tài liệu cần, và cái còn thiếu")
    sn.add_argument("--rev", default="", help="Rev silicon in trên mặt chip")
    sn.add_argument(
        "--lookup",
        action="store_true",
        help="Agent đi tìm đường dẫn trang chính thức (chỉ trong danh sách cho phép)",
    )
    sp2 = sources_sub.add_parser("pages", help="Phần tài liệu còn phải trích")
    sp2.add_argument("module", nargs="?", default="", help="Chỉ xét một module")
    p_sources.set_defaults(func=cmd_sources)

    # N-037 — errata theo đúng rev silicon
    p_errata = sub.add_parser(
        "errata",
        help="Lỗi chip đã công bố, theo đúng rev silicon (N-037)",
        description=(
            "Mã ĐÚNG THEO DATASHEET vẫn có thể chạy sai nếu chip có lỗi đã công "
            "bố — loại lỗi mọi cổng kiểm chứng đều cho qua, vì mã thật sự đúng "
            "với thứ nó được bảo. Danh sách trống KHÔNG có nghĩa là chip sạch."
        ),
    )
    errata_sub = p_errata.add_subparsers(
        dest="errata_action", required=True, metavar="<hành động>"
    )
    errata_sub.add_parser("show", help="Xem kho errata và module nào chạm vào")
    el = errata_sub.add_parser("lookup", help="Agent tra errata cho đúng rev")
    el.add_argument("--rev", default="", help="Rev silicon in trên mặt chip")
    p_errata.set_defaults(func=cmd_errata)

    # N-006, N-010, N-011, N-014 — Agent đề xuất, người chốt tại gate
    p_propose = sub.add_parser(
        "propose",
        help="Agent đề xuất phạm vi / ràng buộc / tiêu chí / bảng chân (G0–G1)",
        description=(
            "Đối chiếu là việc dễ hơn: nó bắt đầu từ một danh sách đã có. Đề "
            "xuất phải bắt đầu từ trang trắng — và đó đúng là chỗ người mới vào "
            "nghề mắc kẹt. Cả bốn bản đều dừng ở ĐỀ XUẤT."
        ),
    )
    propose_sub = p_propose.add_subparsers(
        dest="propose_action", required=True, metavar="<hành động>"
    )
    for ten, tro_giup in (
        ("scope", "Phạm vi và cái KHÔNG làm, kèm lý do (N-006)"),
        ("constraints", "Ràng buộc cứng, mỗi cái kèm hệ quả nếu vi phạm (N-010)"),
        ("acceptance", "Tiêu chí nghiệm thu đo được: số + đơn vị + cách đo (N-011)"),
        ("pinmap", "Bảng chân, kèm kiểm chức năng thay thế (N-014)"),
        ("plant", "Mô hình đối tượng, kèm hiện tượng nó bỏ qua (N-060)"),
    ):
        sp = propose_sub.add_parser(ten, help=tro_giup)
        sp.add_argument("--goal", default="", help="Mục tiêu hệ thống")
        if ten == "scope":
            sp.add_argument("--force", action="store_true", help="Dựng lại dù đã có bản cũ")
        if ten in ("constraints", "plant"):
            sp.add_argument("--plant", default="", help="Đối tượng điều khiển")
    p_propose.set_defaults(func=cmd_propose)

    # N-015, N-071, N-904 — ngân sách tài nguyên và token theo module
    p_budget = sub.add_parser(
        "budget",
        help="Ngân sách flash/RAM/token chia theo module (N-015, N-904)",
        description=(
            "Trần TỔNG trả lời 'còn chỗ không?' vào lúc liên kết — lúc muộn "
            "nhất. Chia phần trước thì câu hỏi thành 'module này có ở trong "
            "phần của nó không?', và trả lời được ngay ở module đầu tiên."
        ),
    )
    budget_sub = p_budget.add_subparsers(
        dest="budget_action", required=True, metavar="<hành động>"
    )
    budget_sub.add_parser("show", help="Xem bản chia hiện hành và chỗ tự mâu thuẫn")
    bp = budget_sub.add_parser("propose", help="Agent đề xuất cách chia theo backlog")
    bp.add_argument(
        "--metric",
        action="append",
        default=[],
        help="Số liệu cần chia (mặc định: mọi khóa trong budget.capacity)",
    )
    bt = budget_sub.add_parser("tokens", help="Token đã tiêu và chi phí theo module")
    bt.add_argument("module", nargs="?", default="", help="Chỉ xem một module")
    p_budget.set_defaults(func=cmd_budget)

    # N-001..N-006 — khởi tạo dự án bằng hội thoại
    p_brief = sub.add_parser(
        "brief",
        help="Dò phần cứng, hỏi, rồi dựng hồ sơ dự án ở dạng nháp",
        description=(
            "Chạy TRƯỚC 'eaa init'. Agent dò trước khi hỏi, chỉ hỏi những gì "
            "máy không tự biết được, rồi dựng constraints.yaml và "
            "hardware_profile.yaml ở dạng ĐỀ XUẤT để bạn duyệt tại G1."
        ),
    )
    p_brief.add_argument("--board", default="", help="Nêu rõ tên bo, khi Agent chưa chắc")
    p_brief.add_argument("--platform", default="", help="Tên Platform Pack, khi tự nêu bo")
    p_brief.add_argument("--ask", action="store_true", help="Hỏi ngay trên dòng lệnh")
    p_brief.add_argument("--answers", help="Tệp YAML trả lời sẵn theo khóa câu hỏi")
    p_brief.set_defaults(func=cmd_brief)

    # P7 bước 3 — đi tìm thứ bảng kiểm còn thiếu
    p_resolve = sub.add_parser(
        "resolve",
        help="Đi tìm tri thức còn thiếu của một module (thang ba bậc)",
        description=(
            "Bảng kiểm nói THIẾU thì Agent đi tìm, thay vì đứng im. Bậc 1 lục "
            "lại tài liệu đã nạp; bậc 2 hỏi bạn đích danh; bậc 3 tra miền nhà "
            "sản xuất. Thứ tìm được luôn là đề xuất, phải qua G2."
        ),
    )
    p_resolve.add_argument("module_id")
    p_resolve.add_argument(
        "--ask", action="store_true", help="Bật bậc 2: hỏi ngay trên dòng lệnh"
    )
    p_resolve.add_argument(
        "--web", action="store_true", help="Bật bậc 3: tra nguồn cho phép trên web"
    )
    p_resolve.set_defaults(func=cmd_resolve)

    # Bước 8 — cổng quyết định, không chỉ cổng duyệt
    p_decide = sub.add_parser(
        "decide",
        help="Dựng các phương án cho một quyết định, để người chọn tại gate",
        description=(
            "Ở những chỗ có nhiều cách làm đều đúng, một nút 'duyệt' buộc con "
            "người duyệt cái Agent đã tự chọn — và lựa chọn thật sự đã xảy ra "
            "trước đó, ở chỗ không ai nhìn thấy."
        ),
    )
    p_decide.add_argument("question", nargs="?", default="", help="Câu hỏi cần quyết")
    p_decide.add_argument("--gate", default="G1", help="Gate sẽ đặt quyết định này lên")
    p_decide.add_argument("--context", help="Tệp bối cảnh gửi kèm cho mô hình")
    p_decide.add_argument("--count", type=int, default=3, help="Số phương án cần nêu")
    p_decide.add_argument("--show", action="store_true", help="Xem phương án đang chờ")
    p_decide.set_defaults(func=cmd_decide)

    # Bước 5 — kênh máy đọc thẳng từ mạch
    p_tele = sub.add_parser(
        "telemetry",
        help="Thu telemetry từ mạch qua cổng nối tiếp",
        description=(
            "Luôn có hạn thời gian: một lệnh đọc không hạn chờ sẽ treo mãi khi "
            "mạch không nói gì, và 'treo' trông giống hệt 'đang đo'."
        ),
    )
    p_tele.add_argument("--port", default="", help="Cổng nối tiếp; bỏ trống thì tự nhận")
    p_tele.add_argument("--seconds", type=float, default=5.0, help="Thu bao lâu")
    p_tele.add_argument("--frames", type=int, default=0, help="Dừng sớm khi đủ N khung đạt")
    p_tele.add_argument("--out", help="Ghi bản thu ra tệp (kèm bản nguyên văn .raw)")
    p_tele.add_argument("--replay", help="Phân tích lại một bản thu nguyên văn, không cần mạch")
    p_tele.set_defaults(func=cmd_telemetry)

    # Bước 3 — cổng nối tiếp
    p_ports = sub.add_parser(
        "ports",
        help="Liệt kê cổng nối tiếp và nhận diện mạch đang cắm",
    )
    p_ports.add_argument(
        "--all", action="store_true", help="Kể cả cổng ảo (Bluetooth, debug console)"
    )
    p_ports.add_argument(
        "--watch", action="store_true",
        help="Canh liên tục: rút/cắm bo và xem thay đổi ngay, thay vì chụp một lần",
    )
    p_ports.add_argument(
        "--timeout", type=float, default=120.0, metavar="<giây>",
        help="Hạn giờ cho --watch (mặc định 120)",
    )
    p_ports.set_defaults(func=cmd_ports)

    # Bước 4 — nạp firmware (FR-DIA-02)
    p_flash = sub.add_parser(
        "flash",
        help="Nạp firmware xuống thiết bị (luôn cần người xác nhận)",
        description=(
            "Nạp chỉ xảy ra khi: có ảnh đã ráp, kho mã sạch, ảnh mới hơn nguồn, "
            "và có người xác nhận. Không cờ nào bỏ qua được bốn điều này."
        ),
    )
    # `eaa flash approve --image <ảnh>` — quyết định của NGƯỜI, ghi vào sổ để
    # nó sống ngoài phiên chạy đã sinh ra nó (SL-119). Không có nó thì mọi phiên
    # không terminal đều cụt đường ở chặng cuối của sản phẩm.
    p_flash.add_argument(
        "flash_action", nargs="?", choices=["approve"],
        help="approve --image <ảnh>: bạn duyệt ảnh này, sau đó 'eaa flash' nạp nó",
    )
    p_flash.add_argument("--port", default="", help="Cổng nối tiếp; bỏ trống thì tự nhận")
    p_flash.add_argument("--image", help="Ảnh cần nạp; mặc định lấy bản vừa ráp")
    p_flash.add_argument("--actor", help="Người chịu trách nhiệm lần nạp này")
    p_flash.add_argument(
        "--confirm-safety", action="append", dest="confirm_safety", default=[],
        help="Xác nhận một mục checklist an toàn, nguyên văn (ảnh làm thiết bị "
             "chuyển động thì bắt buộc, mỗi mục một lần)",
    )
    p_flash.add_argument(
        "--history", action="store_true", help="Xem nhật ký nạp thay vì nạp"
    )
    p_flash.set_defaults(func=cmd_flash)

    # AIS §8.4 — quay lui
    p_rb = sub.add_parser(
        "rollback", help="Đưa module về bản known-good gần nhất (AIS §8.4)"
    )
    p_rb.add_argument("module_id")
    p_rb.add_argument("--reason", required=True, help="Lý do quay lui — vào build ledger")
    p_rb.add_argument("--actor")
    p_rb.set_defaults(func=cmd_rollback)

    # FR-ING-03, TC-23 — ảnh màn hiện sóng thành số đo
    p_si = sub.add_parser(
        "scope-image",
        help="Đọc số đo từ ảnh màn hiện sóng, người chốt trước khi lưu (TC-23)",
        description=(
            "Số đọc từ ảnh là ĐỀ XUẤT kèm sai số đọc ảnh, không tự vào "
            "Measurement Records. Người đối chiếu với ảnh gốc, sửa được giá "
            "trị, rồi mới chốt — và bản ghi giữ cả hai con số."
        ),
    )
    p_si.add_argument("image", help="Đường dẫn ảnh")
    p_si.add_argument(
        "--expect", action="append", help="Đại lượng cần đọc; lặp lại được"
    )
    p_si.add_argument(
        "--accept", action="append",
        help="Chốt một số đo, dạng khóa=giá_trị; không có thì chỉ in đề xuất",
    )
    p_si.add_argument("--actor", default="", help="Người chốt số đo")
    p_si.set_defaults(func=cmd_scope_image)

    # Bảng năng lực — một chỗ trả lời trọn câu "Agent làm được gì"
    p_cap = sub.add_parser(
        "capabilities",
        help="Agent làm được gì, cái nào đang chạy được, kiểm bằng gì",
        description=(
            "Bốn tầng năng lực — lệnh CLI, lệnh Agent tự gọi, năng lực nền "
            "tảng, công cụ ngoài — và bốn tầng ấy hỏng theo bốn cách khác "
            "nhau, nên bảng in ra cả cách bổ sung cho từng tầng. Bảng kiểm SỰ "
            "CÓ MẶT; câu 'nó chạy đúng không' thuộc về bộ test."
        ),
    )
    p_cap.add_argument(
        "--verbose", action="store_true", help="Liệt kê từng lệnh, kể cả khi đủ"
    )
    p_cap.set_defaults(func=cmd_capabilities)

    # ── Nhóm năng lực độc lập: dò môi trường, ra mạng, nhớ, tự làm công cụ ──

    p_env = sub.add_parser(
        "environ",
        help="Máy này là máy gì: OS, kiến trúc, quyền, trình cài gói, mạng",
        description=(
            "'doctor' trả lời 'máy này có đủ công cụ cho pack chưa'; lệnh này "
            "trả lời câu đứng trước đó — 'máy này là máy gì'. Mạng được THỬ "
            "THẬT bằng một lần nối, không phải đọc biến proxy rồi đoán."
        ),
    )
    p_env.add_argument("--no-network", action="store_true", help="Bỏ qua bước thử mạng")
    p_env.add_argument(
        "--packages", metavar="HỆ", nargs="?", const="python",
        help="Liệt kê gói đã cài của một hệ sinh thái (python | npm). "
             "'doctor' chỉ kiểm thứ có trong Tool Card; cái này trả lời 'máy này sẵn có gì'",
    )
    p_env.add_argument("--remember", action="store_true",
                       help="Ghi kết quả vào bộ nhớ liên dự án")
    p_env.set_defaults(func=cmd_environ)

    p_recall = sub.add_parser(
        "recall",
        help="Tra kho tri thức ĐÃ DUYỆT của dự án bằng một câu hỏi",
        description=(
            "Hai tầng như đường sinh mã: đồ thị chỉ đích danh trước, BM25 lấp "
            "sau. Chỉ trả trích đoạn đã duyệt G2 — chunk còn chờ duyệt được "
            "NÊU RA nhưng không tính vào kết quả. Tra đây TRƯỚC khi ra web."
        ),
    )
    p_recall.add_argument("question", nargs="+", help="Câu hỏi bằng tiếng Việt")
    p_recall.add_argument("--top-k", type=int, default=5, help="Số trích đoạn tối đa")
    p_recall.add_argument("--chars", type=int, default=600,
                          help="Số ký tự nội dung in ra cho mỗi trích đoạn")
    p_recall.set_defaults(func=cmd_recall)

    p_res = sub.add_parser(
        "research",
        help="Tìm trên web rồi ĐỌC trang, không hỏi trí nhớ mô hình",
        description=(
            "Tìm kiếm trả về ĐỊA CHỈ; nội dung do bộ tải lấy về qua bộ kiểm "
            "nguồn. Trang của nhà sản xuất là hạng 'chính chủ' và dùng làm tri "
            "thức được; phần còn lại của web là hạng 'mở' — manh mối để gỡ lỗi "
            "hoặc so công cụ, không phải nguồn cho giá trị cấu hình."
        ),
    )
    p_res.add_argument("query", nargs="+", help="Câu cần tra")
    p_res.add_argument("--site", action="append", default=[],
                       help="Buộc truy vấn về tên miền này (lặp lại được)")
    p_res.add_argument("--official-only", action="store_true",
                       help="Chỉ đọc trang thuộc miền nhà sản xuất")
    p_res.add_argument("--max-docs", type=int, default=3, help="Trần số trang đọc")
    p_res.add_argument("--full", action="store_true", help="In cả nội dung đã đọc")
    p_res.set_defaults(func=cmd_research)

    p_read = sub.add_parser(
        "read",
        help="Tải một trang web và in nội dung chữ của nó",
        description=(
            "Chặn địa chỉ nội bộ, chỉ nhận http/https, có trần byte và trần "
            "thời gian, và tính lại hạng tin cậy theo URL CUỐI sau chuyển hướng."
        ),
    )
    p_read.add_argument("url")
    p_read.add_argument("--refresh", action="store_true", help="Bỏ qua bộ đệm")
    p_read.add_argument("--limit", type=int, default=4000, help="Số ký tự in ra")
    p_read.set_defaults(func=cmd_read)

    p_mem = sub.add_parser(
        "memory",
        help="Bộ nhớ liên dự án: môi trường, công cụ, bài học",
        description=(
            "Kho append-only ở gốc kho mã, dùng chung mọi dự án. Phạm vi phải "
            "khai rõ — bài học của dự án này KHÔNG tự chảy sang dự án khác."
        ),
    )
    sub_mem = p_mem.add_subparsers(dest="memory_cmd", required=True)
    m_ls = sub_mem.add_parser("list", help="Sự kiện đang hiệu lực")
    m_ls.add_argument("--kind", default="", help="Lọc theo loại")
    m_ls.add_argument("--all", action="store_true", help="Kể cả bản đã bị thay")
    m_ls.set_defaults(func=cmd_memory_list)
    m_add = sub_mem.add_parser("add", help="Ghi một sự kiện")
    m_add.add_argument("subject")
    m_add.add_argument("statement")
    m_add.add_argument("--kind", default="bài học")
    m_add.add_argument("--scope", default="", help="'toàn cục', 'dự án:<tên>', 'mcu:<họ>'")
    m_add.add_argument("--evidence", default="")
    m_add.set_defaults(func=cmd_memory_add)

    p_pb = sub.add_parser(
        "playbook",
        help="Sổ tay lỗi: lỗi nào đã gặp, cách nào đã sửa được",
        description=(
            "Tra chỗ mình đã biết trước khi đi hỏi chỗ khác. Mỗi mục mang hai "
            "bộ đếm trúng/trượt — một sổ tay chỉ ghi thành công sẽ tự tin dần "
            "lên theo hướng sai."
        ),
    )
    sub_pb = p_pb.add_subparsers(dest="playbook_cmd", required=True)
    pb_ls = sub_pb.add_parser("list", help="Toàn bộ sổ tay")
    pb_ls.set_defaults(func=cmd_playbook_list)
    pb_lk = sub_pb.add_parser("lookup", help="Tra một thông báo lỗi")
    pb_lk.add_argument("error", nargs="+")
    pb_lk.set_defaults(func=cmd_playbook_lookup)
    pb_rec = sub_pb.add_parser("record", help="Ghi một cặp (lỗi → cách sửa)")
    pb_rec.add_argument("error")
    pb_rec.add_argument("fix")
    pb_rec.add_argument("--context", default="")
    pb_rec.add_argument("--source", default="", help="Địa chỉ trang đã tra")
    pb_rec.add_argument("--failed", action="store_true", help="Ghi là cách này KHÔNG hiệu quả")
    pb_rec.add_argument("--scope", default="",
                        help="'toàn cục' | 'mcu:<họ>' | 'dự án:<tên>'. "
                             "Bỏ trống thì lấy họ MCU của dự án đang dùng")
    pb_rec.set_defaults(func=cmd_playbook_record)

    p_tool = sub.add_parser(
        "tool",
        help="Công cụ Agent tự viết: đề xuất, kiểm, duyệt, chạy",
        description=(
            "Agent mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ. Ba cổng — "
            "cấu tạo, an toàn, chạy thử — rồi mới tới người duyệt; 'tool "
            "approve' KHÔNG nằm trong danh mục Agent tự gọi được."
        ),
    )
    sub_tool = p_tool.add_subparsers(dest="tool_cmd", required=True)
    t_ls = sub_tool.add_parser("list", help="Sổ công cụ tự sinh và trạng thái")
    t_ls.set_defaults(func=cmd_tool_list)
    t_pr = sub_tool.add_parser("propose", help="Nhờ mô hình viết một công cụ")
    t_pr.add_argument("need", nargs="+", help="Nhu cầu, nói bằng tiếng Việt")
    t_pr.set_defaults(func=cmd_tool_propose)
    t_vf = sub_tool.add_parser("verify", help="Cho một công cụ đi qua ba cổng")
    t_vf.add_argument("name")
    t_vf.set_defaults(func=cmd_tool_verify)
    t_ap = sub_tool.add_parser("approve", help="NGƯỜI duyệt — chỉ đi được từ 'verified'")
    t_ap.add_argument("name")
    t_ap.add_argument("--actor", default="", help="Ai duyệt")
    t_ap.set_defaults(func=cmd_tool_approve)
    t_run = sub_tool.add_parser("run", help="Chạy một công cụ ĐÃ DUYỆT")
    t_run.add_argument("name")
    t_run.add_argument("--args", default="{}", help="Tham số dạng JSON")
    t_run.set_defaults(func=cmd_tool_run)
    t_rb = sub_tool.add_parser(
        "rollback",
        help="Quay về bản đã duyệt gần nhất trước bản hiện tại",
        description=(
            "Bản quay về KHÔNG tự lên lại 'approved' — nó về 'proposed' và phải "
            "đi lại ba cổng. Mã ấy từng chạy được, nhưng 'từng' là ở một môi "
            "trường khác."
        ),
    )
    t_rb.add_argument("name")
    t_rb.set_defaults(func=cmd_tool_rollback)
    t_doc = sub_tool.add_parser(
        "doc", help="Sinh tài liệu ngắn cho một công cụ tự sinh")
    t_doc.add_argument("name")
    t_doc.add_argument("--save", action="store_true",
                       help="Ghi ra tools_local/<tên>.md thay vì in ra")
    t_doc.set_defaults(func=cmd_tool_doc)

    p_scr = sub.add_parser(
        "scratch",
        help="Dựng chỗ làm nháp — hỏi một câu mà không phải soạn cả hồ sơ dự án",
        description=(
            "KHÔNG tắt cổng nào, không bỏ gate nào. Nó chỉ SINH SẴN phần YAML "
            "khuôn mẫu để cửa vào không còn nằm ở chỗ bạn chưa có gì để điền. "
            "Mọi ràng buộc sinh sẵn mang nhãn GIẢ ĐỊNH."
        ),
    )
    p_scr.add_argument("--name", default="nhap")
    p_scr.add_argument(
        "--platform", default="",
        help="Tên Platform Pack. Bỏ trống thì suy từ tên chỗ nháp; "
             "không suy được thì hệ HỎI chứ không mặc định bừa",
    )
    p_scr.add_argument("--force", action="store_true")
    p_scr.set_defaults(func=cmd_scratch)

    p_skill = sub.add_parser(
        "skill",
        help="Kỹ năng: chuỗi việc hay lặp, đặt tên để gọi lại bằng một câu",
        description=(
            "Kỹ năng GỘP quyền đã có, KHÔNG cấp quyền mới: mọi bước bắt buộc "
            "nằm trong danh mục Agent vốn đã được gọi. Ba cổng — quyền, tham "
            "số, chạy khô — rồi mới tới người duyệt."
        ),
    )
    sub_skill = p_skill.add_subparsers(dest="skill_cmd", required=True)
    s_ls = sub_skill.add_parser("list", help="Sổ kỹ năng và trạng thái")
    s_ls.set_defaults(func=cmd_skill_list)
    s_mine = sub_skill.add_parser("mine", help="Tìm chuỗi việc ĐÃ lặp trong nhật ký hội thoại")
    s_mine.add_argument("--min-count", type=int, default=2, help="Số lần lặp tối thiểu")
    s_mine.add_argument("--save", default="", help="Lưu đề xuất thứ nhất thành kỹ năng tên này")
    s_mine.set_defaults(func=cmd_skill_mine)
    s_add = sub_skill.add_parser(
        "add",
        help="Tự viết một kỹ năng khi bạn đã biết mình muốn chuỗi nào",
        description=(
            "Không phải kỹ năng nào cũng cần đợi 'mine' phát hiện. Dùng "
            "{tên} trong bước để khai tham số: --step 'resolve {module}'."
        ),
    )
    s_add.add_argument("name")
    s_add.add_argument("--step", action="append", required=True, default=[],
                       help="Một bước, lặp lại được. Ví dụ: --step 'plan list'")
    s_add.add_argument("--purpose", default="", help="Một câu: kỹ năng này để làm gì")
    s_add.add_argument("--optional", action="append", default=[],
                       help="Bước được phép hỏng mà vẫn đi tiếp (chép nguyên văn bước ấy)")
    s_add.set_defaults(func=cmd_skill_add)

    s_vf = sub_skill.add_parser("verify", help="Cho một kỹ năng đi qua ba cổng")
    s_vf.add_argument("name")
    s_vf.set_defaults(func=cmd_skill_verify)
    s_ap = sub_skill.add_parser("approve", help="NGƯỜI duyệt — chỉ đi được từ 'verified'")
    s_ap.add_argument("name")
    s_ap.add_argument("--actor", default="")
    s_ap.set_defaults(func=cmd_skill_approve)
    s_run = sub_skill.add_parser("run", help="Chạy một kỹ năng ĐÃ DUYỆT")
    s_run.add_argument("name")
    s_run.add_argument("--args", default="{}", help="Tham số dạng JSON")
    s_run.add_argument("--full", action="store_true", help="In cả đầu ra từng bước")
    s_run.set_defaults(func=cmd_skill_run)

    p_focus = sub.add_parser(
        "focus",
        help="Còn gì chặn giữa đây và việc bạn muốn làm — cả quãng đường, một lần",
        description=(
            "KHÔNG bỏ tiền điều kiện nào, không tự duyệt gate nào. Nó đảo chiều "
            "thông tin: thay vì báo CÁI CHẶN ĐẦU TIÊN, nó tính TOÀN BỘ quãng "
            "đường và nói rõ ở mỗi chặng ai làm được. '--run' chạy những chặng "
            "trong danh mục Agent rồi DỪNG ở chặng đầu tiên phải là bạn."
        ),
    )
    p_focus.add_argument("module_id", help="Module muốn sinh mã")
    p_focus.add_argument("--run", action="store_true",
                         help="Chạy luôn những chặng tôi tự lo được")
    p_focus.set_defaults(func=cmd_focus)

    p_sug = sub.add_parser(
        "suggest",
        help="Tự nhìn lại: cái gì đang tốn công nhất, và nên làm gì với nó",
        description=(
            "Mọi đề nghị đều kèm SỐ đếm được từ nhật ký thật. Không có tín hiệu "
            "thì nói thẳng là chưa thấy gì đáng làm — đó là một câu trả lời, "
            "không phải một thất bại của lệnh."
        ),
    )
    p_sug.add_argument("--min-count", type=int, default=2,
                       help="Số lần lặp tối thiểu để coi là một tín hiệu")
    p_sug.set_defaults(func=cmd_suggest)

    p_ass = sub.add_parser(
        "assess",
        help="Gói này có đáng cài không: còn bảo trì, license, độ phổ biến, tên có thật",
        description=(
            "Đọc siêu dữ liệu từ kho gói — hạng MỞ. Dùng để so công cụ và gỡ "
            "lỗi; KHÔNG dùng làm nguồn cho giá trị cấu hình phần cứng."
        ),
    )
    p_ass.add_argument("name", help="Tên gói")
    p_ass.add_argument("--registry", default="pypi", help="pypi | npm | github (github dùng chủ/kho)")
    p_ass.add_argument("--similar-to", action="append", default=[],
                       help="Tên gói phổ biến để so, bắt tên gõ nhầm một ký tự")
    p_ass.set_defaults(func=cmd_assess)

    p_dbg = sub.add_parser(
        "debug",
        help="Phiên gỡ lỗi sâu: tôi dựng kế hoạch và ghi vết, BẠN cầm dụng cụ",
        description=(
            "N-085 ở mức tự chủ T0 — Agent không chạy phiên gỡ lỗi. Nó dò dụng "
            "cụ, dựng kế hoạch từ kịch bản chẩn đoán đã duyệt, và ghi lại ai "
            "làm gì, thấy gì."
        ),
    )
    sub_dbg = p_dbg.add_subparsers(dest="debug_cmd", required=True)
    d_plan = sub_dbg.add_parser("plan", help="Dựng kế hoạch một phiên")
    d_plan.add_argument("--scenario", default="", help="Mã kịch bản chẩn đoán, ví dụ DS-03")
    d_plan.set_defaults(func=cmd_debug_plan)
    d_log = sub_dbg.add_parser("log", help="Các phiên đã ghi")
    d_log.set_defaults(func=cmd_debug_log)
    d_rec = sub_dbg.add_parser("record", help="Ghi lại một phiên đã làm")
    d_rec.add_argument("--note", required=True, help="Thấy gì")
    d_rec.add_argument("--actor", default="", help="Ai làm")
    d_rec.add_argument("--scenario", default="")
    d_rec.add_argument("--outcome", default="", help="Kết luận rút ra")
    d_rec.add_argument("--tool", default="", help="Dụng cụ đã dùng")
    d_rec.set_defaults(func=cmd_debug_record)

    # FR-ING-01, N-004 — đọc kho nén hồ sơ dự án
    p_survey = sub.add_parser(
        "survey",
        help="Khảo sát một kho nén hồ sơ: kiểm kê, phân loại, rút dữ kiện từ mã",
        description=(
            "Hồ sơ gốc của một dự án thường tới dưới dạng một kho nén. Lệnh này "
            "bày ra thứ CÓ TRONG kho và rút các dữ kiện xác định từ mã nguồn "
            "kèm theo — nó KHÔNG kết luận đây là bo gì."
        ),
    )
    p_survey.add_argument("archive", nargs="?", default="",
                          help="Đường dẫn tệp .zip (bỏ trống khi dùng --read/--files)")
    p_survey.add_argument(
        "--extract", action="store_true",
        help="Giải ra <dự án>/sources/ sau khi kiểm an toàn",
    )
    p_survey.add_argument(
        "--read", default="", metavar="TỆP",
        help="Đọc MỘT tệp trong kho đã giải nén, kể cả PDF. Đường dẫn tính từ "
             "<dự án>/sources/",
    )
    p_survey.add_argument(
        "--files", default="", metavar="MẪU",
        help="Liệt kê tệp trong kho đã giải nén khớp mẫu, ví dụ '*.pdf'. "
             "Bản khảo sát tổng bị cắt bớt; cái này để soi kỹ một phần",
    )
    p_survey.set_defaults(func=cmd_survey)

    # Vòng hội thoại — nói bằng tiếng Việt, Agent tự tìm đường
    p_chat = sub.add_parser(
        "chat",
        help="Nói bằng tiếng Việt; Agent tự chọn và chạy lệnh để trả lời",
        description=(
            "Agent tự chạy các lệnh chỉ-đọc và lệnh đề xuất để tìm câu trả "
            "lời. Nó KHÔNG có lệnh nào để quyết định tại gate, nạp firmware, "
            "cài công cụ hay phong hạng — không phải vì bị dặn, mà vì danh "
            "mục công cụ của nó không chứa chúng."
        ),
    )
    p_chat.add_argument(
        "question", nargs="*", help="Hỏi một câu rồi thoát; bỏ trống thì mở phiên"
    )
    p_chat.add_argument(
        "--max-steps", type=int, default=8, dest="max_steps",
        help="Trần số lệnh Agent được chạy trong một lượt",
    )
    p_chat.set_defaults(func=cmd_chat)

    # N-905 — Agent tự phát hiện sai lệch thiết kế
    p_dev = sub.add_parser(
        "deviations",
        help="Quét chỗ mã và tài liệu kể hai câu chuyện khác nhau (N-905)",
        description=(
            "Sổ sai lệch ghi được những lệch mà người viết NHỚ RA. Phép quét "
            "này đối chiếu danh sách module và lệnh với tài liệu — nó bắt được "
            "'có trong mã mà không có trong tài liệu', và KHÔNG bắt được một "
            "module làm khác điều tài liệu mô tả."
        ),
    )
    p_dev.add_argument(
        "--draft", action="store_true", help="In khung mục để dán vào sổ sai lệch"
    )
    p_dev.set_defaults(func=cmd_deviations)

    # N-094, N-101, N-103 — bàn giao và vận hành
    p_ho = sub.add_parser(
        "handover",
        help="Tài liệu vận hành, đổi linh kiện, cập nhật hiện trường (G9–G10)",
        description=(
            "Ba việc của giai đoạn cuối, và cả ba đều là viết ra thứ đã biết. "
            "Tài liệu vận hành gom từ dữ liệu dự án; đổi linh kiện bắc cầu trên "
            "đồ thị tài nguyên; cập nhật hiện trường bắt đầu từ MỘT thiết bị."
        ),
    )
    ho_sub = p_ho.add_subparsers(dest="handover_action", required=True, metavar="<hành động>")
    hd = ho_sub.add_parser("doc", help="Sinh tài liệu vận hành, kèm mục KHÔNG làm được")
    hd.add_argument("--publish", action="store_true", help="Đăng ký vào kho phẩm xuất")
    hs = ho_sub.add_parser("swap", help="So linh kiện thay thế, chỉ đích danh mã bị chạm")
    hs.add_argument("--old", required=True, help="Linh kiện đang dùng")
    hs.add_argument("--new", required=True, help="Linh kiện thay thế")
    hs.add_argument("--used-for", default="", dest="used_for", help="Dự án dùng nó để làm gì")
    hr = ho_sub.add_parser("rollout", help="Kế hoạch cập nhật có đường lui")
    hr.add_argument("--from-commit", default="", dest="from_commit")
    hr.add_argument("--to-commit", default="", dest="to_commit")
    hr.add_argument("--rollback-to", default="", dest="rollback_to")
    p_ho.set_defaults(func=cmd_handover)

    # N-102 — sự cố ngoài hiện trường
    p_field = sub.add_parser(
        "field",
        help="Chẩn đoán sự cố ngoài hiện trường (N-102)",
        description=(
            "Khác một phiên trên bàn ở đúng một điểm, và điểm ấy quyết định mọi "
            "thứ: hiện tượng không xảy ra trước mặt ta. Bước đầu không phải là "
            "đo mà là DỰNG LẠI ĐIỀU KIỆN."
        ),
    )
    p_field.add_argument("symptom", help="Người ở hiện trường mô tả thế nào")
    p_field.add_argument(
        "--condition", action="append",
        help="Điều kiện lúc xảy ra, dạng khóa=giá_trị; lặp lại được",
    )
    p_field.add_argument("--occurrences", type=int, default=1, help="Đã gặp bao nhiêu lần")
    p_field.add_argument(
        "--reproduced", choices=["co", "khong", "chua"], default="chua",
        help="Dựng lại trên bàn được chưa",
    )
    p_field.add_argument(
        "--scenario", action="append", help="Chỉ định kịch bản thay vì để Agent chọn"
    )
    p_field.set_defaults(func=cmd_field)

    # N-086 — kiểm độ bền dài hạn
    p_end = sub.add_parser(
        "endurance",
        help="Chạy dài, phát hiện reset và trôi (N-086)",
        description=(
            "Ba thứ chỉ lộ ra khi chạy dài: reset ngầm, trôi, rò bộ nhớ. Báo "
            "cáo luôn mở đầu bằng THỜI GIAN đã quan sát thật — 10 phút không "
            "kết luận được cho 10 giờ."
        ),
    )
    p_end.add_argument("--port", default="", help="Cổng nối tiếp")
    p_end.add_argument("--seconds", type=float, default=0.0, help="Thu bao lâu")
    p_end.add_argument("--replay", help="Phân tích lại một bản thu đã có")
    p_end.add_argument("--save", help="Ghi bản thu ra tệp")
    p_end.add_argument(
        "--key", default="uptime_s", help="Khóa bộ đếm thời gian chạy trong telemetry"
    )
    p_end.add_argument(
        "--required", type=float, default=0.0,
        help="Yêu cầu chạy liên tục bao lâu (mặc định lấy từ acceptance của dự án)",
    )
    p_end.add_argument(
        "--drift", action="append", help="Khóa cần theo dõi trôi; lặp lại được"
    )
    p_end.set_defaults(func=cmd_endurance)

    # AIS §7 — chẩn đoán phần cứng
    p_dg = sub.add_parser(
        "diagnose",
        help="Chẩn đoán phần cứng hai kênh (AIS §7)",
        description=(
            "Chẩn đoán là phép GIAO của kênh máy và kênh người. Kịch bản làm "
            "thiết bị chuyển động luôn đòi xác nhận checklist an toàn trước."
        ),
    )
    dg_sub = p_dg.add_subparsers(dest="diagnose_action", required=True, metavar="<hành động>")
    dg_sub.add_parser("list", help="Liệt kê kịch bản chẩn đoán của dự án")
    ds = dg_sub.add_parser(
        "select",
        help="Chọn kịch bản từ mô tả triệu chứng",
        description=(
            "Bậc 1 khớp từ khóa dự án đã khai — tất định và kiểm lại được. "
            "Trượt thì bậc 2 hỏi mô hình, và kết quả bậc 2 được đánh dấu rõ là "
            "PHỎNG ĐOÁN."
        ),
    )
    ds.add_argument("symptom")
    ds.add_argument(
        "--khong-hoi-mo-hinh",
        action="store_true",
        dest="khong_hoi_mo_hinh",
        help="Chỉ dùng bậc 1; hữu ích khi cần kết quả tất định tuyệt đối",
    )
    db = dg_sub.add_parser(
        "build", help="Dựng firmware đo của một kịch bản (AIS §7)"
    )
    db.add_argument("scenario")

    dm = dg_sub.add_parser(
        "measure",
        help="Hướng dẫn đo bằng dụng cụ, và nhận số đo về (N-084)",
        description=(
            "Kênh thứ ba, bên cạnh kênh máy và kênh quan sát. Dòng tổng, sụt "
            "áp trên dây, nhiệt độ vỏ linh kiện — không con chip nào tự đo "
            "được về chính nó. Gọi không kèm --value thì in hướng dẫn đo."
        ),
    )
    dm.add_argument("scenario")
    dm.add_argument(
        "--value", action="append",
        help="Số đo về, dạng khóa=giá_trị; lặp lại cho từng mục",
    )

    dr = dg_sub.add_parser("run", help="Chạy một kịch bản và kết luận")
    dr.add_argument("scenario")
    dr.add_argument(
        "--telemetry",
        help="Tệp telemetry JSON từng dòng; kèm --port thì đây là nơi GHI bản thu",
    )
    dr.add_argument("--port", default="", help="Đọc telemetry thẳng từ cổng này")
    dr.add_argument(
        "--seconds", type=float, default=0.0, help="Thu bao lâu (mặc định 5s khi có --port)"
    )
    dr.add_argument(
        "--answer", action="append",
        help="Quan sát của người, dạng khóa=có|không; lặp lại cho từng mục",
    )
    dr.add_argument(
        "--confirm-safety", action="append", dest="confirm_safety",
        help="Xác nhận một mục checklist an toàn, nguyên văn",
    )
    p_dg.set_defaults(func=cmd_diagnose)

    khung: list[tuple[str, str, str, str]] = []
    for ten, tro_giup, sprint, ghi_chu in khung:
        p = sub.add_parser(ten, help=f"[{sprint}] {tro_giup}")
        p.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        p.set_defaults(func=_chua_hien_thuc(ten, sprint, ghi_chu))

    # --model nhận được ở CẢ HAI vị trí: trước tên lệnh (nó là cờ của parser
    # gốc) và sau tên lệnh. Chỗ thứ hai là chỗ người ta gõ theo bản năng —
    # "eaa chat --model flash" — và nếu chỉ vị trí đầu chạy được thì thông báo
    # lỗi argparse trả về ("unrecognized arguments") không hề gợi ý vị trí đúng.
    #
    # default=SUPPRESS là mấu chốt: không nêu thì lệnh con KHÔNG ghi thuộc tính,
    # nên giá trị đặt ở parser gốc sống sót. Thiếu nó thì "eaa --model X chat"
    # bị chính mặc định rỗng của lệnh con xóa mất.
    for ten_lenh, p_con in sub.choices.items():
        try:
            p_con.add_argument(
                "--model", default=argparse.SUPPRESS, metavar="<mã>",
                help="Đổi mô hình cho riêng lượt chạy này (xem: eaa models)",
            )
        except argparse.ArgumentError:
            # Lệnh đã tự khai --model với nghĩa riêng — 'init' ghim vào state.
            pass

    _gan_co_json(sub)
    return parser


def _gan_co_json(sub: argparse._SubParsersAction) -> None:
    """Gắn `--json` cho ĐÚNG những parser trong `LENH_CO_JSON`.

    Gắn ở parser nào là chuyện quan trọng: `eaa gate` có `approve` và `reject`
    nên KHÔNG được nhận cờ, còn `eaa gate show` thì được. Gắn ở cha thì
    `gate approve --json` cũng chạy, và lúc ấy có hai đường cùng đổi trạng thái
    mà chỉ một đường được canh.
    """
    for duong in LENH_CO_JSON:
        phan = duong.split()
        pr = sub.choices.get(phan[0])
        for ten in phan[1:]:
            con = next(
                (a for a in (pr._actions if pr else [])
                 if isinstance(a, argparse._SubParsersAction)), None
            )
            pr = con.choices.get(ten) if con else None
        if pr is None:
            raise RuntimeError(f"LENH_CO_JSON nhắc lệnh không có: {duong!r}")
        pr.add_argument(
            "--json", action="store_true",
            help="Đầu ra máy đọc được (lược đồ v%d)" % _SCHEMA_JSON,
        )


def main(argv: Sequence[str] | None = None) -> int:
    load_env_file()
    parser = build_parser()
    args = parser.parse_args(argv)

    # Cờ --model đặt MỘT lần ở đây thay vì luồn qua 25 chỗ gọi build_context().
    # Luồn tham số thì chắc chắn sót một chỗ, và chỗ sót ấy bỏ im lặng đúng cái
    # cờ người dùng vừa gõ ra — hỏng theo kiểu không ai thấy. Đây là biến toàn
    # cục ghi-một-lần-lúc-vào, đọc ở đúng một hàm.
    global _MODEL_LUOT_NAY
    _MODEL_LUOT_NAY = (getattr(args, "model", "") or "").strip()

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

    # Tên lệnh người dùng vừa gõ — chỉ chỗ này biết nó, và chỉ chỗ này gắn được
    # câu "làm tiếp" cho đúng việc vừa hỏng (SL-178).
    #
    # Lấy từ `args.command`, tức từ chính argparse. Bản đầu quét argv tìm đối
    # số đầu không bắt đầu bằng dấu gạch, và nó nhặt nhầm GIÁ TRỊ của cờ đứng
    # trước: `eaa --project x tune` cho ten_lenh = "x", nên câu "làm tiếp" mất
    # đi trong im lặng. Việc E1 làm lộ chỗ này (SL-182).
    ten_lenh = getattr(args, "command", "") or ""

    # Chế độ máy đọc (E1). Bật thì văn xuôi bị NUỐT: trộn văn xuôi với JSON
    # trên cùng một luồng thì không bên nào đọc được. Lệnh không phải sửa gì —
    # chúng cứ in như cũ, chỉ có điều không ai nghe.
    from eaa import jsonout

    che_do_json = bool(getattr(args, "json", False))
    if che_do_json:
        con = next(
            (v for k, v in vars(args).items()
             if k.endswith("_action") and isinstance(v, str) and v),
            "",
        )
        jsonout.bat(f"{ten_lenh} {con}".strip())

    def _bao(nhan: str, exc: BaseException) -> None:
        if che_do_json:
            jsonout.in_loi(
                getattr(exc, "exit_code", EXIT_ENV_ERROR),
                str(exc),
                GOI_Y_KHI_HONG.get(ten_lenh, ()),
            )
            return
        print(f"{nhan}: {exc}{_goi_y_di_tiep(ten_lenh, str(exc))}", file=sys.stderr)

    def _chay() -> int:
        if not che_do_json:
            return args.func(args)
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            ma = args.func(args)
        jsonout.in_ket_qua(ma)
        return ma

    try:
        return _chay()
    except CliError as exc:
        _bao("Lỗi", exc)
        return exc.exit_code
    except CHO_NGUOI as exc:
        _bao("Cần người quyết định", exc)
        return EXIT_WAITING_GATE
    except PolicyViolation as exc:
        _bao("Bị luật điều phối từ chối", exc)
        return EXIT_ENV_ERROR
    except MergeNotAuthorized as exc:
        _bao("Không được phép merge", exc)
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
        _bao("Lỗi", exc)
        return EXIT_ENV_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
