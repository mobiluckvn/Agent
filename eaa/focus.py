"""Vào thẳng việc cần làm — không bỏ cổng nào, chỉ bỏ việc phải đoán.

EAA-SRS-01 FR-PLT-03, EAA-SAD-02 §3 (máy trạng thái 6 giai đoạn); UC04.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-82.

Khoảng trống module này lấp
----------------------------

``eaa resume`` khôi phục được sau gián đoạn, nhưng khôi phục **không phải** bắt
đầu giữa chừng. Người dùng mở công cụ ra vì muốn một việc cụ thể — *"sinh mã
cho module này"* — và cái họ nhận được là một thông báo tiền điều kiện: sai
pha. Sửa xong cái ấy thì tới cái sau: module chưa có trong backlog. Rồi tới
cái sau nữa. Mỗi lần một câu, và mỗi câu chỉ nói về **cái vừa chặn**, không
nói về **cả quãng đường còn lại**.

Điều đó làm người dùng đi mò từng bước một trong một quy trình mà chính họ
không nhìn thấy hình dạng.

Điều module này KHÔNG làm
--------------------------

Nó **không bỏ qua tiền điều kiện nào, không tự duyệt gate nào**. Cách "dễ" hơn
— một cờ cho phép nhảy thẳng vào pha D — phá đúng bất biến trung tâm, và nó sẽ
được dùng vào đúng lúc gấp.

Thứ nó làm là đảo ngược chiều thông tin: thay vì báo **cái chặn đầu tiên**, nó
tính **toàn bộ quãng đường** và nói rõ ở mỗi chặng *ai làm được*. Cùng một bộ
luật, cùng những cổng ấy — chỉ khác chỗ người dùng nhìn thấy hết một lần.

Hai loại chặng, và ranh giới giữa chúng là ranh giới cũ
--------------------------------------------------------

* :data:`AGENT` — chặng nằm trong danh mục Agent vốn đã được gọi
  (``eaa/agent.py`` ``TOOLBOX``). ``--run`` chạy được những chặng này.
* :data:`NGUOI` — quyết định tại gate, và mọi thứ khác ngoài danh mục.
  ``--run`` **dừng lại** ở chặng đầu tiên thuộc loại này và nói rõ vì sao.

Ranh giới ấy không phải luật mới của module này; nó chính là ranh giới đã có,
đọc từ cùng một chỗ. Một chặng "người" không bao giờ tự chuyển thành "agent"
bằng cách đi qua ``focus``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "FocusError",
    "Precondition",
    "FocusPlan",
    "analyse",
    "AGENT",
    "NGUOI",
    "DAT",
    "CHUA",
    "KHONG_KIEM_DUOC_O_DAY",
]

#: Ai làm được chặng này.
AGENT = "agent"
NGUOI = "người"

#: Trạng thái một tiền điều kiện.
DAT = "đạt"
CHUA = "chưa"
KHONG_KIEM_DUOC_O_DAY = "chưa kiểm được"


class FocusError(Exception):
    """Không dựng được lộ trình."""


@dataclass(frozen=True)
class Precondition:
    """Một tiền điều kiện, và cách gỡ nó."""

    name: str
    status: str
    detail: str = ""
    #: Lệnh gỡ, dạng argv. Rỗng nghĩa là không có lệnh trực tiếp.
    fix: tuple[str, ...] = ()
    who: str = NGUOI
    #: Vì sao chặng này phải là người — chỉ điền khi ``who == NGUOI``.
    reason: str = ""

    @property
    def met(self) -> bool:
        return self.status == DAT

    def render(self) -> str:
        dau = {DAT: "✓", CHUA: "✗", KHONG_KIEM_DUOC_O_DAY: "?"}.get(self.status, "?")
        dong = [f"  {dau} {self.name}"]
        if self.detail:
            dong.append(f"      {self.detail}")
        if not self.met and self.fix:
            ai = "tôi chạy được" if self.who == AGENT else "CẦN BẠN"
            dong.append(f"      → {ai}:  eaa {' '.join(self.fix)}")
            if self.who == NGUOI and self.reason:
                dong.append(f"        {self.reason}")
        return "\n".join(dong)


@dataclass
class FocusPlan:
    """Toàn bộ quãng đường từ đây tới việc muốn làm."""

    target: str
    module_id: str = ""
    preconditions: tuple[Precondition, ...] = ()

    @property
    def blocked_by(self) -> list[Precondition]:
        return [p for p in self.preconditions if not p.met]

    @property
    def ready(self) -> bool:
        return not self.blocked_by

    @property
    def agent_steps(self) -> list[Precondition]:
        """Chặng Agent tự lo được, tính tới chặng đầu tiên phải là người.

        Cắt ở đó chứ không lấy hết: một chặng "người" ở giữa nghĩa là mọi chặng
        sau nó phụ thuộc vào một quyết định chưa có. Chạy trước những chặng ấy
        là làm việc trên một giả định người dùng chưa đưa ra.
        """
        ra: list[Precondition] = []
        for p in self.blocked_by:
            if p.who != AGENT or not p.fix:
                break
            ra.append(p)
        return ra

    @property
    def first_human_step(self) -> Precondition | None:
        for p in self.blocked_by:
            if p.who != AGENT or not p.fix:
                return p
        return None

    @property
    def confidence_level(self) -> str:
        """SUY RA: lộ trình đọc từ trạng thái hiện tại, chưa chạy thử bước nào."""
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self) -> str:
        from eaa.confidence import header

        dong = [f"Để {self.target}", "", header(self.confidence_level), ""]
        dong += [p.render() for p in self.preconditions]
        dong.append("")

        if self.ready:
            dong.append("Không còn gì chặn — chạy được ngay.")
            return "\n".join(dong)

        xong = sum(1 for p in self.preconditions if p.met)
        dong.append(f"Còn {len(self.blocked_by)}/{len(self.preconditions)} chặng "
                    f"(đã qua {xong}).")

        tu_lo = self.agent_steps
        if tu_lo:
            dong += ["", "Tôi tự lo được ngay:"]
            dong += [f"    eaa {' '.join(p.fix)}" for p in tu_lo]
            dong.append("    (thêm --run để tôi chạy chúng)")

        cho_nguoi = self.first_human_step
        if cho_nguoi is not None:
            dong += ["", f"Rồi dừng ở đây — chặng này phải là bạn:",
                     f"    eaa {' '.join(cho_nguoi.fix)}" if cho_nguoi.fix
                     else f"    {cho_nguoi.name}"]
            if cho_nguoi.reason:
                dong.append(f"    {cho_nguoi.reason}")
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Chẩn đoán
# --------------------------------------------------------------------------


def _ai_chay(argv: Sequence[str]) -> str:
    """Chặng này Agent gọi được không — đọc từ CHÍNH danh mục đã có."""
    from eaa.agent import tool_for

    return AGENT if argv and tool_for(argv) is not None else NGUOI


def analyse(
    *,
    module_id: str,
    state: Any,
    gate_purpose: dict[str, str] | None = None,
    missing_chain_gates: Sequence[str] = (),
    conflicts: Sequence[Any] = (),
    readiness_error: str = "",
    budget_error: str = "",
) -> FocusPlan:
    """Tính toàn bộ quãng đường tới ``eaa gen <module_id>``.

    Nhận dữ kiện đã đọc sẵn thay vì tự đi đọc: cùng bộ luật với
    ``Orchestrator._kiem_tien_dieu_kien``, chỉ khác chỗ nó **không ném** ở cái
    chặn đầu tiên mà đi hết. Trùng lặp luật ở hai chỗ là rủi ro thật, nên chỗ
    này cố ý KHÔNG phát biểu luật nào mới — mọi câu hỏi đều do bên gọi đo và
    truyền xuống.
    """
    from eaa.orchestrator import GENERATION_PHASE
    from eaa.policy import GATE_ORDER, PHASE_NAMES, PHASE_ORDER, gate_for_transition

    muc: list[Precondition] = []
    tim = gate_purpose or {}

    # -- 1. chuỗi kiểm chứng có đủ cổng không -------------------------------
    if missing_chain_gates:
        muc.append(Precondition(
            "Chuỗi kiểm chứng đủ cổng", CHUA,
            f"thiếu {', '.join(missing_chain_gates)} — một cổng vắng mặt là một "
            "loại lỗi không được kiểm (FR-VER-01)",
            fix=("packs",), who=NGUOI,
            reason="Cổng do Platform Pack khai; thiếu thì sửa pack, không sửa engine.",
        ))
    else:
        muc.append(Precondition("Chuỗi kiểm chứng đủ cổng", DAT))

    # -- 2. pha, và các gate phải duyệt để tới được pha D -------------------
    pha = getattr(state, "phase", "")
    if pha == GENERATION_PHASE:
        muc.append(Precondition(
            f"Đang ở pha {GENERATION_PHASE} ({PHASE_NAMES[GENERATION_PHASE]})", DAT))
    elif pha not in PHASE_ORDER:
        muc.append(Precondition(
            "Pha dự án đọc được", CHUA, f"pha {pha!r} không hợp lệ",
            fix=("init",), who=NGUOI,
            reason="Project State hỏng hoặc chưa khởi tạo.",
        ))
    elif PHASE_ORDER.index(pha) > PHASE_ORDER.index(GENERATION_PHASE):
        muc.append(Precondition(
            f"Đang ở pha {GENERATION_PHASE}", CHUA,
            f"dự án đã qua pha {GENERATION_PHASE}, hiện ở {pha} ({PHASE_NAMES[pha]}) "
            "— không lùi pha được",
            who=NGUOI,
            reason="Quay lại pha trước là một quyết định về phạm vi, không phải một lệnh.",
        ))
    else:
        # Từng chặng chuyển pha là một tiền điều kiện riêng, kèm ĐÚNG gate của
        # nó. Gộp lại thành một dòng "sai pha" là đúng cái làm người dùng phải
        # mò từng bước.
        gates = getattr(state, "gates", {}) or {}
        i = PHASE_ORDER.index(pha)
        j = PHASE_ORDER.index(GENERATION_PHASE)
        # Cung không có gate (B→C) KHÔNG phải một chặng chặn: engine đi hết
        # những bước mà gate vừa duyệt đã mở ra, không dừng lại giữa chừng.
        # Liệt nó ra như một việc phải làm là bịa thêm một bước cho người dùng,
        # và tệ hơn: một bước không có lệnh nào gỡ được.
        for k in range(i, j):
            tu, den = PHASE_ORDER[k], PHASE_ORDER[k + 1]
            g = gate_for_transition(tu, den)
            if not g:
                # Cung không gate đi ngay SAU gate đứng trước nó, nên nó là một
                # ghi chú gắn vào gate ấy — không phải một mục riêng.
                if muc:
                    cu = muc[-1]
                    muc[-1] = Precondition(
                        cu.name, cu.status,
                        f"{cu.detail} · duyệt xong tự đi tiếp {tu}→{den}".lstrip(" ·"),
                        cu.fix, cu.who, cu.reason,
                    )
                continue
            trang_thai = gates.get(g, "pending")
            muc.append(Precondition(
                f"Gate {g} duyệt để đi {tu} → {den}",
                DAT if trang_thai == "approved" else CHUA,
                f"{tim.get(g, '')} · đang: {trang_thai}",
                fix=("gate", "approve", g),
                who=NGUOI,
                reason="Quyết định tại gate là của con người — đây là bất biến "
                       "trung tâm của cả sản phẩm.",
            ))

    # -- 3. module có trong backlog không -----------------------------------
    lay = getattr(state, "module", None)
    m = lay(module_id) if callable(lay) else None
    if m is None:
        co = ", ".join(x.id for x in (getattr(state, "backlog", []) or [])) or "(trống)"
        muc.append(Precondition(
            f"Module {module_id!r} có trong backlog", CHUA,
            f"backlog đang có: {co}",
            fix=("plan", "add", module_id), who=_ai_chay(("plan", "add")),
        ))
    elif getattr(m, "status", "") == "merged":
        muc.append(Precondition(
            f"Module {module_id!r} chưa merge", CHUA,
            "module đã merge — sinh lại thì đưa nó về trạng thái todo trước",
            fix=("plan", "list"), who=NGUOI,
            reason="Sinh lại một module đã merge là quyết định về phiên bản mã.",
        ))
    else:
        muc.append(Precondition(
            f"Module {module_id!r} có trong backlog", DAT,
            f"trạng thái: {getattr(m, 'status', '?')}"))

    # -- 4. xung đột tài nguyên ---------------------------------------------
    if conflicts:
        chi_tiet = "; ".join(getattr(c, "message", str(c)) for c in list(conflicts)[:3])
        muc.append(Precondition(
            "Không xung đột tài nguyên", CHUA, chi_tiet,
            fix=("plan", "list"), who=NGUOI,
            reason="Hai module cùng dùng một tài nguyên phải do kỹ sư phân xử (FR-KG-02).",
        ))
    elif m is not None:
        muc.append(Precondition("Không xung đột tài nguyên", DAT))

    # -- 5. đủ tri thức để sinh mã ------------------------------------------
    if readiness_error:
        muc.append(Precondition(
            "Đủ tri thức để sinh mã", CHUA, readiness_error.strip().splitlines()[0][:200],
            fix=("resolve", module_id), who=_ai_chay(("resolve",)),
        ))
    elif m is not None:
        muc.append(Precondition("Đủ tri thức để sinh mã", DAT))

    # -- 6. ngân sách token --------------------------------------------------
    if budget_error:
        muc.append(Precondition(
            "Còn ngân sách token", CHUA, budget_error[:200],
            fix=("budget", "tokens"), who=NGUOI,
            reason="Nới trần là sửa constraints.yaml — tệp có phiên bản và phải duyệt lại tại G1.",
        ))

    return FocusPlan(
        target=f"sinh mã cho module {module_id!r}",
        module_id=module_id,
        preconditions=tuple(muc),
    )
