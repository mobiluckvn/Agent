"""Kỹ năng — chuỗi việc hay lặp, rút thành một thứ gọi được bằng một câu.

EAA-AIS-05 §9, §11; FR-ORC-01, NFR-08. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-81.

Khoảng trống module này lấp
----------------------------

Agent đã tự viết được **công cụ** mới (``eaa/toolforge.py``). Nhưng phần lớn
việc lặp đi lặp lại không thiếu công cụ — nó thiếu **cách gọi một chuỗi công cụ
đã có**. Trả lời câu "module này còn thiếu tri thức gì" luôn là cùng bốn lệnh
theo cùng thứ tự; xem "dự án đang mắc ở đâu" luôn là cùng ba lệnh. Mỗi lần hỏi,
Agent lại đi lại từ đầu và tốn một lượt gọi mô hình cho mỗi bước.

Chuỗi ấy hiện bị **đóng cứng trong quy trình G0→G10** hoặc nằm rải trong đầu
người dùng. Module này rút nó ra thành dữ liệu: đặt tên được, tra được, chạy
lại được, và sửa được mà không đụng vào mã.

Bất biến trung tâm: kỹ năng KHÔNG mở thêm quyền
------------------------------------------------

Đây là chỗ một tầng "kỹ năng" dễ phá hỏng mọi thứ nhất. Nếu một kỹ năng gọi
được lệnh nằm ngoài :data:`eaa.agent.TOOLBOX`, thì nó trở thành đường vòng: ai
đó đặt tên một kỹ năng là "chốt xong module" và nhét ``gate approve`` vào giữa,
và từ đó Agent duyệt gate được — bằng đúng một dòng YAML không ai đọc kỹ.

Nên cổng đầu tiên của mọi kỹ năng là: **mỗi bước phải nằm trong danh mục Agent
vốn đã được gọi.** Không có ngoại lệ, không có cờ bỏ qua. Kỹ năng là cách
*gộp* quyền đã có, không phải cách *cấp* quyền mới.

Ba cổng, cùng kỷ luật với xưởng công cụ
----------------------------------------

1. **Cổng quyền** — mọi bước nằm trong ``TOOLBOX``.
2. **Cổng tham số** — mọi chỗ giữ ``{tên}`` trong các bước đều khai trong
   ``params``, và ngược lại không khai thừa.
3. **Cổng chạy khô** — dựng đủ chuỗi lệnh cuối cùng với một bộ tham số mẫu, để
   thấy chính xác cái gì sẽ chạy trước khi có gì chạy.

Qua ba cổng thì lên ``verified``. Từ ``verified`` lên ``approved`` là việc của
người — ``eaa skill approve`` không nằm trong ``TOOLBOX``.

Khai thác từ nhật ký, không từ trí tưởng tượng
-----------------------------------------------

:func:`mine` đọc ``chat_log.jsonl`` và tìm những chuỗi lệnh **thật sự đã lặp**.
Đề xuất một kỹ năng cho việc chưa ai làm bao giờ là đoán; đề xuất cho việc đã
làm bốn lần là quan sát.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "SkillError",
    "Skill",
    "SkillStep",
    "SkillRegistry",
    "SkillReport",
    "SkillCheck",
    "SkillRun",
    "StepResult",
    "mine",
    "MinedSkill",
    "verify_skill",
    "SKILLS_FILE",
    "DE_XUAT",
    "DA_KIEM_THU",
    "DA_DUYET",
    "DAI_CHUOI_TOI_THIEU",
    "MA_DUNG_CHUOI",
    "SO_LAN_LAP_TOI_THIEU",
    "SO_BUOC_TOI_DA",
]

SKILLS_FILE = "skills.yaml"

DE_XUAT = "proposed"
DA_KIEM_THU = "verified"
DA_DUYET = "approved"

#: Chuỗi ngắn hơn thế không đáng đặt tên — gõ hai lệnh vẫn nhanh hơn nhớ một
#: cái tên.
DAI_CHUOI_TOI_THIEU = 2

#: Lặp ít hơn thế thì đó là trùng hợp, không phải thói quen.
SO_LAN_LAP_TOI_THIEU = 2

#: Trần số bước. Cùng tinh thần với ``MAX_STEPS`` = 8 của vòng hội thoại: một
#: kỹ năng dài hơn thế đang cố thay cả quy trình, và quy trình thì có gate.
SO_BUOC_TOI_DA = 8

#: ``{tên}`` — chỗ giữ tham số trong một bước.
_CHO_GIU = re.compile(r"\{([a-z][a-z0-9_]{0,31})\}")

#: Mã thoát làm DỪNG cả chuỗi.
#:
#: Cố ý KHÔNG có mã 2. Mã 2 nghĩa là "đang chờ người" — đó là một TRẠNG THÁI
#: của dự án, không phải một lỗi của lệnh. Đo được ngay ở kỹ năng đầu tiên
#: viết thử: một chuỗi xem-xét hoàn toàn hợp lý (``focus`` rồi ``sources
#: pages``) đứt ngay bước một, chỉ vì dự án đang chờ duyệt một gate — đúng cái
#: mà người dùng chạy kỹ năng ấy để tìm hiểu.
#:
#: Mã 1 (lỗi lệnh), 3 (cạn lượt tự sửa) và 4 (lỗi môi trường) thì dừng thật:
#: bước sau chạy trên kết quả của bước trước hỏng là chạy trên nền cát.
MA_DUNG_CHUOI: frozenset[int] = frozenset({1, 3, 4})


class SkillError(Exception):
    """Không dựng, không kiểm, hoặc không chạy được kỹ năng."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Kỹ năng
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillStep:
    """Một bước — argv có thể chứa chỗ giữ ``{tham_số}``."""

    argv: tuple[str, ...]
    note: str = ""
    #: Bước hỏng thì dừng cả chuỗi hay đi tiếp. Mặc định DỪNG: một bước sau
    #: chạy trên kết quả của bước trước hỏng là chạy trên nền cát.
    optional: bool = False

    @property
    def params(self) -> set[str]:
        return {m for p in self.argv for m in _CHO_GIU.findall(p)}

    def resolve(self, arguments: dict[str, Any]) -> tuple[str, ...]:
        """Điền tham số. Thiếu cái nào thì báo tên cái ấy."""
        ra: list[str] = []
        for p in self.argv:
            def thay(m: "re.Match[str]") -> str:
                ten = m.group(1)
                if ten not in arguments:
                    raise SkillError(f"thiếu tham số {ten!r}")
                return str(arguments[ten])

            ra.append(_CHO_GIU.sub(thay, p))
        return tuple(ra)

    def render(self) -> str:
        dau = "?" if self.optional else " "
        dong = f"  {dau} eaa {' '.join(self.argv)}"
        return dong + (f"\n        {self.note}" if self.note else "")


@dataclass(frozen=True)
class Skill:
    """Một chuỗi việc đã đặt tên."""

    name: str
    purpose: str
    steps: tuple[SkillStep, ...] = ()
    params: tuple[str, ...] = ()
    status: str = DE_XUAT
    source: str = ""
    created_at: str = ""
    verified_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    note: str = ""

    @property
    def runnable(self) -> bool:
        return self.status == DA_DUYET

    @property
    def used_params(self) -> set[str]:
        return {p for s in self.steps for p in s.params}

    @property
    def confidence_level(self) -> str:
        from eaa.confidence import DA_KIEM, GIA_DINH, SUY_RA

        if self.status == DA_DUYET:
            return DA_KIEM
        if self.status == DA_KIEM_THU:
            return SUY_RA
        return GIA_DINH

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "params": list(self.params),
            "steps": [
                {"argv": list(s.argv), **({"note": s.note} if s.note else {}),
                 **({"optional": True} if s.optional else {})}
                for s in self.steps
            ],
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Skill":
        return cls(
            name=str(d.get("name", "")),
            purpose=str(d.get("purpose", "")),
            steps=tuple(
                SkillStep(
                    argv=tuple(str(x) for x in (b.get("argv") or [])),
                    note=str(b.get("note", "")),
                    optional=bool(b.get("optional", False)),
                )
                for b in (d.get("steps") or [])
            ),
            params=tuple(str(x) for x in (d.get("params") or [])),
            status=str(d.get("status", DE_XUAT)),
            source=str(d.get("source", "")),
            created_at=str(d.get("created_at", "")),
            verified_at=str(d.get("verified_at", "")),
            approved_by=str(d.get("approved_by", "")),
            approved_at=str(d.get("approved_at", "")),
            note=str(d.get("note", "")),
        )

    def render(self) -> str:
        dau = {DE_XUAT: "…", DA_KIEM_THU: "✓", DA_DUYET: "★"}.get(self.status, "?")
        dong = [f"  {dau} {self.name}  [{self.status}]  ·  {len(self.steps)} bước",
                f"      {self.purpose}"]
        if self.params:
            dong.append(f"      tham số: {', '.join(self.params)}")
        dong += [f"    " + s.render().lstrip() for s in self.steps]
        if self.approved_by:
            dong.append(f"      duyệt bởi {self.approved_by} lúc {self.approved_at}")
        elif self.status == DA_KIEM_THU:
            dong.append(f"      đã qua 3 cổng — chờ người duyệt: eaa skill approve {self.name}")
        if self.source:
            dong.append(f"      rút từ: {self.source}")
        if self.note:
            dong.append(f"      {self.note}")
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Ba cổng
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillCheck:
    gate: str
    passed: bool
    detail: str = ""

    def render(self) -> str:
        return f"  {'✓' if self.passed else '✗'} {self.gate}: {self.detail}"


@dataclass
class SkillReport:
    skill: str
    checks: tuple[SkillCheck, ...] = ()
    preview: tuple[tuple[str, ...], ...] = ()

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def render(self) -> str:
        dong = [f"Kiểm kỹ năng {self.skill}", ""]
        dong += [c.render() for c in self.checks]
        if self.preview:
            dong += ["", "Chạy khô — đây chính xác là những lệnh sẽ chạy:"]
            dong += [f"    eaa {' '.join(a)}" for a in self.preview]
        dong += ["", "→ " + ("qua cả ba cổng — chờ người duyệt" if self.passed
                             else "CHƯA đạt, không được duyệt")]
        return "\n".join(dong)


def _cong_quyen(skill: Skill) -> SkillCheck:
    """Cổng 1 — mọi bước phải nằm trong danh mục Agent vốn đã được gọi.

    Đây là cổng quan trọng nhất của cả module. Không có nó, một kỹ năng tên
    "chốt xong module" với ``gate approve`` nhét ở giữa sẽ cấp cho Agent đúng
    cái quyền mà cả sản phẩm này dựng ra để giữ lại cho con người — bằng một
    dòng YAML không ai đọc kỹ.

    Kỹ năng là cách GỘP quyền đã có, không phải cách CẤP quyền mới.
    """
    from eaa.agent import NGOAI_DANH_MUC, tool_for

    if not skill.steps:
        return SkillCheck("quyền", False, "kỹ năng không có bước nào")
    if len(skill.steps) > SO_BUOC_TOI_DA:
        return SkillCheck(
            "quyền", False,
            f"{len(skill.steps)} bước, quá trần {SO_BUOC_TOI_DA}. Dài hơn thế thì "
            "nó đang cố thay cả quy trình — và quy trình thì có gate.",
        )

    ngoai: list[str] = []
    for b in skill.steps:
        if tool_for(b.argv) is None:
            ngoai.append(" ".join(b.argv))
    if ngoai:
        ly_do = ""
        goc = ngoai[0].split()[0] if ngoai[0] else ""
        for khoa, v in NGOAI_DANH_MUC.items():
            if khoa.split()[0] == goc:
                ly_do = f"  {v}"
                break
        return SkillCheck(
            "quyền", False,
            f"có bước ngoài danh mục Agent được gọi: {', '.join(ngoai)}." + ly_do
            + "  Kỹ năng gộp quyền đã có, không cấp quyền mới.",
        )
    return SkillCheck("quyền", True, f"cả {len(skill.steps)} bước đều nằm trong danh mục")


def _cong_tham_so(skill: Skill) -> SkillCheck:
    """Cổng 2 — chỗ giữ và khai báo phải khớp nhau, cả hai chiều."""
    dung = skill.used_params
    khai = set(skill.params)
    thieu = dung - khai
    thua = khai - dung
    if thieu:
        return SkillCheck(
            "tham số", False,
            f"dùng {', '.join(sorted(thieu))} trong bước nhưng không khai ở params",
        )
    if thua:
        return SkillCheck(
            "tham số", False,
            f"khai {', '.join(sorted(thua))} ở params nhưng không bước nào dùng — "
            "một tham số không ai dùng là một tham số người gọi sẽ điền nhầm chỗ",
        )
    return SkillCheck("tham số", True, f"{len(khai)} tham số, khớp cả hai chiều")


def _cong_chay_kho(skill: Skill, mau: dict[str, Any] | None = None) -> tuple[SkillCheck, tuple]:
    """Cổng 3 — dựng đủ chuỗi lệnh cuối cùng, để thấy cái gì SẼ chạy."""
    tham_so = dict(mau or {})
    for p in skill.params:
        tham_so.setdefault(p, f"<{p}>")
    try:
        lenh = tuple(b.resolve(tham_so) for b in skill.steps)
    except SkillError as exc:
        return SkillCheck("chạy khô", False, str(exc)), ()
    return SkillCheck("chạy khô", True, f"dựng được {len(lenh)} lệnh"), lenh


def verify_skill(skill: Skill, *, sample: dict[str, Any] | None = None) -> SkillReport:
    """Ba cổng, dừng ngay khi một cổng trượt."""
    quyen = _cong_quyen(skill)
    if not quyen.passed:
        return SkillReport(skill.name, (quyen,))
    tham_so = _cong_tham_so(skill)
    if not tham_so.passed:
        return SkillReport(skill.name, (quyen, tham_so))
    kho, lenh = _cong_chay_kho(skill, sample)
    return SkillReport(skill.name, (quyen, tham_so, kho), lenh)


# --------------------------------------------------------------------------
# Chạy
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StepResult:
    argv: tuple[str, ...]
    exit_code: int
    output: str = ""
    skipped: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def waiting(self) -> bool:
        """Lệnh chạy xong, nhưng dự án đang chờ một quyết định của người."""
        return self.exit_code == 2

    def render(self) -> str:
        if self.skipped:
            return f"  – eaa {' '.join(self.argv)}   (bỏ qua: {self.skipped})"
        dau = "✓" if self.ok else ("⏸" if self.waiting else "✗")
        return f"  {dau} eaa {' '.join(self.argv)}   (mã {self.exit_code})"


@dataclass
class SkillRun:
    skill: str
    results: list[StepResult] = field(default_factory=list)
    stopped_at: str = ""

    @property
    def ok(self) -> bool:
        return not self.stopped_at and all(
            r.ok or r.skipped or r.waiting for r in self.results
        )

    @property
    def waiting(self) -> list[StepResult]:
        return [r for r in self.results if r.waiting]

    def render(self, *, full: bool = False) -> str:
        dong = [f"Kỹ năng {self.skill}", ""]
        for r in self.results:
            dong.append(r.render())
            if full and r.output.strip():
                dong += [f"      {d}" for d in r.output.strip().splitlines()[:20]]
        if self.stopped_at:
            dong += ["", f"Dừng ở bước `{self.stopped_at}` vì nó không đạt. "
                         "Bước sau chạy trên kết quả của bước trước hỏng là chạy trên nền cát."]
        elif self.waiting:
            dong += ["", f"{len(self.waiting)} bước báo ĐANG CHỜ NGƯỜI (mã 2). "
                         "Đó là một trạng thái của dự án, không phải một lỗi — "
                         "chuỗi vẫn chạy hết."]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Sổ đăng ký
# --------------------------------------------------------------------------


@dataclass
class SkillRegistry:
    """Sổ kỹ năng của MỘT dự án.

    Khác sổ công cụ (ở gốc kho): kỹ năng nói về chuỗi việc của một dự án cụ
    thể — "module nào còn thiếu tri thức" chỉ có nghĩa khi có backlog. Đặt
    chung ở gốc thì một kỹ năng của dự án này sẽ hiện ra ở dự án khác và chạy
    hỏng vì thiếu dữ liệu, chứ không phải vì nó sai.
    """

    root: Path

    @property
    def path(self) -> Path:
        return self.root / SKILLS_FILE

    def all(self) -> list[Skill]:
        if not self.path.is_file():
            return []
        du_lieu = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        return [Skill.from_dict(d) for d in (du_lieu.get("skills") or [])]

    def get(self, name: str) -> Skill | None:
        for s in self.all():
            if s.name == name:
                return s
        return None

    def approved(self) -> list[Skill]:
        return [s for s in self.all() if s.runnable]

    def save(self, skill: Skill) -> Skill:
        ds = [s for s in self.all() if s.name != skill.name] + [skill]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tam = self.path.with_suffix(".tmp")
        tam.write_text(
            "# Sổ kỹ năng — chuỗi việc hay lặp, đặt tên để gọi lại.\n"
            "# Cột 'status' đi một chiều: proposed → verified → approved (NGƯỜI duyệt).\n"
            "#\n"
            "# BẤT BIẾN: mọi bước phải nằm trong danh mục Agent vốn đã được gọi\n"
            "# (eaa/agent.py TOOLBOX). Kỹ năng GỘP quyền đã có, KHÔNG cấp quyền mới.\n"
            + yaml.safe_dump(
                {"skills": [s.to_dict() for s in sorted(ds, key=lambda s: s.name)]},
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )
        tam.replace(self.path)
        return skill

    def set_status(self, name: str, status: str, **kw: Any) -> Skill:
        cu = self.get(name)
        if cu is None:
            raise SkillError(f"Sổ không có kỹ năng {name!r}")
        truong = {k: v for k, v in cu.__dict__.items() if k != "status"}
        return self.save(Skill(**{**truong, **kw, "status": status}))

    def approve(self, name: str, *, by: str) -> Skill:
        cu = self.get(name)
        if cu is None:
            raise SkillError(f"Sổ không có kỹ năng {name!r}")
        if cu.status != DA_KIEM_THU:
            raise SkillError(
                f"{name!r} đang ở trạng thái {cu.status!r}, không phải {DA_KIEM_THU!r}. "
                f"Chạy 'eaa skill verify {name}' trước."
            )
        if not by.strip():
            raise SkillError("Phải ghi ai duyệt")
        return self.set_status(name, DA_DUYET, approved_by=by.strip(), approved_at=_now())

    def verify(self, name: str, *, sample: dict[str, Any] | None = None) -> SkillReport:
        ky_nang = self.get(name)
        if ky_nang is None:
            raise SkillError(f"Sổ không có kỹ năng {name!r}")
        if ky_nang.status == DA_DUYET:
            raise SkillError(f"{name!r} đã được duyệt. Sửa bước thì phải duyệt lại.")
        bao_cao = verify_skill(ky_nang, sample=sample)
        self.set_status(
            name, DA_KIEM_THU if bao_cao.passed else DE_XUAT,
            verified_at=_now() if bao_cao.passed else "",
            note="" if bao_cao.passed else next(
                (c.detail for c in bao_cao.checks if not c.passed), ""),
        )
        return bao_cao

    def run(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        runner: Any = None,
    ) -> SkillRun:
        """Chạy một kỹ năng ĐÃ DUYỆT, dừng ở bước đầu tiên không đạt."""
        ky_nang = self.get(name)
        if ky_nang is None:
            raise SkillError(f"Sổ không có kỹ năng {name!r}")
        if not ky_nang.runnable:
            raise SkillError(
                f"{name!r} đang ở trạng thái {ky_nang.status!r}, chưa được duyệt. "
                f"Người duyệt bằng: eaa skill approve {name}"
            )

        thieu = [p for p in ky_nang.params if p not in (arguments or {})]
        if thieu:
            raise SkillError(f"Thiếu tham số: {', '.join(thieu)}")

        if runner is None:
            from eaa.agent import _chay_cli as runner  # type: ignore[assignment]

        # Kiểm quyền LẠI ngay trước khi chạy, không chỉ lúc duyệt. Sổ là một
        # tệp YAML sửa tay được: một kỹ năng đã duyệt rồi bị chèn thêm bước
        # vẫn mang trạng thái approved. Cổng lúc duyệt bảo vệ được quy trình,
        # cổng lúc chạy bảo vệ được lượt chạy này.
        quyen = _cong_quyen(ky_nang)
        if not quyen.passed:
            raise SkillError(
                f"Kỹ năng {name!r} đã được duyệt nhưng nội dung hiện tại không "
                f"qua được cổng quyền: {quyen.detail}"
            )

        lan_chay = SkillRun(skill=name)
        for b in ky_nang.steps:
            argv = b.resolve(arguments or {})
            ma, dau_ra = runner(list(argv))
            lan_chay.results.append(StepResult(argv, ma, dau_ra))
            if ma in MA_DUNG_CHUOI and not b.optional:
                lan_chay.stopped_at = " ".join(argv)
                break
        return lan_chay


# --------------------------------------------------------------------------
# Khai thác từ nhật ký
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MinedSkill:
    """Một chuỗi lệnh đã thật sự lặp trong nhật ký."""

    commands: tuple[str, ...]
    count: int

    @property
    def suggested_name(self) -> str:
        goc = [c.split()[0] for c in self.commands]
        return "_".join(dict.fromkeys(goc))[:40].replace("-", "_")

    def to_skill(self, *, name: str = "", purpose: str = "", source: str = "") -> Skill:
        buoc = tuple(SkillStep(argv=tuple(c.split())) for c in self.commands)
        return Skill(
            name=name or self.suggested_name,
            purpose=purpose or f"Chuỗi {len(self.commands)} bước đã lặp {self.count} lần",
            steps=buoc,
            params=tuple(sorted({p for b in buoc for p in b.params})),
            status=DE_XUAT,
            source=source,
            created_at=_now(),
        )

    def render(self) -> str:
        return (f"  · lặp {self.count} lần — {self.suggested_name}\n"
                + "\n".join(f"        eaa {c}" for c in self.commands))


def mine(
    chat_log: Path,
    *,
    min_len: int = DAI_CHUOI_TOI_THIEU,
    min_count: int = SO_LAN_LAP_TOI_THIEU,
    limit: int = 5,
) -> list[MinedSkill]:
    """Tìm chuỗi lệnh đã THẬT SỰ lặp trong nhật ký hội thoại.

    Đề xuất một kỹ năng cho việc chưa ai làm bao giờ là đoán; đề xuất cho việc
    đã làm bốn lần là quan sát. Nên chỗ này chỉ đọc lịch sử, không hỏi mô hình.

    Bỏ chuỗi con của một chuỗi dài hơn có cùng số lần lặp: ``[a,b]`` lặp 3 lần
    và ``[a,b,c]`` cũng lặp 3 lần thì cái ngắn không mang thêm thông tin gì.
    """
    if not Path(chat_log).is_file():
        return []

    luot: list[list[str]] = []
    for dong in Path(chat_log).read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong:
            continue
        try:
            d = json.loads(dong)
        except json.JSONDecodeError:
            continue
        lenh = [str(c) for c in (d.get("commands_run") or []) if str(c).strip()]
        if len(lenh) >= min_len:
            luot.append(lenh)

    dem: Counter[tuple[str, ...]] = Counter()
    for chuoi in luot:
        for n in range(min_len, min(len(chuoi), SO_BUOC_TOI_DA) + 1):
            for i in range(len(chuoi) - n + 1):
                dem[tuple(chuoi[i:i + n])] += 1

    ung_vien = [(c, n) for c, n in dem.items() if n >= min_count]
    ung_vien.sort(key=lambda x: (-x[1], -len(x[0])))

    ket: list[MinedSkill] = []
    for chuoi, so_lan in ung_vien:
        # Bỏ nếu đã có một chuỗi DÀI HƠN chứa nó và lặp bằng đúng số lần ấy.
        thua = any(
            len(c2) > len(chuoi) and n2 == so_lan and _la_chuoi_con(chuoi, c2)
            for c2, n2 in ung_vien
        )
        if thua:
            continue
        ket.append(MinedSkill(commands=chuoi, count=so_lan))
        if len(ket) >= limit:
            break
    return ket


def _la_chuoi_con(ngan: tuple[str, ...], dai: tuple[str, ...]) -> bool:
    n = len(ngan)
    return any(dai[i:i + n] == ngan for i in range(len(dai) - n + 1))
