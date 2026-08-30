"""Tự nhìn lại — cái gì đang tốn công nhất, và nên làm gì với nó.

EAA-AIS-05 §11 (đo và cải tiến); N-906, NFR-08.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-84.

Khoảng trống module này lấp
----------------------------

Agent đã **viết được** công cụ mới (SL-77) và **rút được** kỹ năng (SL-81).
Nhưng cả hai vẫn phải do người gợi ý: người dùng phải tự nhận ra rằng việc này
đáng có một công cụ, rồi tự gõ ``eaa tool propose``.

Đó là đúng chỗ Agent có lợi thế mà con người không có: nó có **nhật ký**. Nó
biết chính xác lần thứ mấy nó bị hỏi một việc nó không làm được, chuỗi nào nó
lặp lại bốn lần, công cụ nào nó gọi mà hỏng ba trong năm lần. Con người chỉ có
cảm giác mơ hồ rằng "cái này hơi phiền".

Mọi đề nghị phải có SỐ ĐI KÈM
-------------------------------

Đây là luật duy nhất của module này. Một đề nghị không kèm bằng chứng đếm được
là một ý kiến, và một agent đưa ý kiến về việc nên xây gì tiếp là một agent
sớm muộn cũng đề nghị xây thứ nó thích. Nên mỗi :class:`Suggestion` mang theo
số lần, và bản in ra nêu số ấy trước khi nêu đề nghị.

Không có tín hiệu thì nói KHÔNG CÓ GÌ
--------------------------------------

Cám dỗ lớn nhất của một lệnh tên ``suggest`` là luôn tìm ra điều gì đó để nói.
Ở đây, nhật ký sạch thì đầu ra là *"chưa thấy gì đáng làm"* — và đó là một câu
trả lời đúng, không phải một thất bại của lệnh.

Ranh giới không đổi
--------------------

Đề nghị là **đề nghị**. Mọi hành động nó nêu ra đều là một lệnh người dùng gõ,
và những lệnh ấy vẫn đi qua đúng các cổng của chúng: ``tool propose`` vẫn ra
bản đề xuất chờ ba cổng, ``skill mine --save`` vẫn ra kỹ năng chờ duyệt.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "Suggestion",
    "SuggestionReport",
    "analyse",
    "LOAI_CONG_CU",
    "LOAI_KY_NANG",
    "LOAI_SUA_CONG_CU",
    "LOAI_CAU_HOI_QUA_LON",
    "LOAI_CACH_SUA_KEM",
    "SO_LAN_DANG_KE",
]

LOAI_CONG_CU = "viết công cụ mới"
LOAI_KY_NANG = "rút thành kỹ năng"
LOAI_SUA_CONG_CU = "xem lại công cụ hay hỏng"
LOAI_CAU_HOI_QUA_LON = "câu hỏi quá lớn cho một lượt"
LOAI_CACH_SUA_KEM = "cách sửa trong sổ tay hay trượt"

#: Dưới ngưỡng này thì đó là trùng hợp, không phải thói quen. Cùng con số với
#: ``SO_LAN_LAP_TOI_THIEU`` của ``eaa/skills.py`` và vì cùng một lý do.
SO_LAN_DANG_KE = 2


@dataclass(frozen=True)
class Suggestion:
    """Một đề nghị, và SỐ đứng sau nó."""

    kind: str
    subject: str
    evidence: str
    action: tuple[str, ...] = ()
    count: int = 0

    @property
    def confidence_level(self) -> str:
        """SUY RA: đếm được từ nhật ký thật, nhưng "nên làm" là một phán đoán."""
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self) -> str:
        dong = [f"  · {self.kind}: {self.subject}",
                f"      bằng chứng: {self.evidence}"]
        if self.action:
            dong.append(f"      → eaa {' '.join(self.action)}")
        return "\n".join(dong)


@dataclass
class SuggestionReport:
    suggestions: tuple[Suggestion, ...] = ()
    #: Chỗ ranh giới quyền đã chặn Agent — KHÔNG phải khoảng trống năng lực.
    boundary_hits: tuple[tuple[str, int], ...] = ()
    turns_read: int = 0

    @property
    def empty(self) -> bool:
        return not self.suggestions

    def render(self) -> str:
        from eaa.confidence import SUY_RA, header

        dong = ["Tự nhìn lại", "", header(SUY_RA), ""]
        dong.append(f"Đã đọc {self.turns_read} lượt hội thoại.")
        dong.append("")

        if self.empty:
            dong += [
                "Chưa thấy gì đáng làm.",
                "",
                "Đó là một câu trả lời, không phải một thất bại: nhật ký chưa đủ "
                "dài, hoặc chưa có việc nào lặp đến mức đáng đặt tên. Cứ dùng "
                "bình thường; chỗ này bồi lên theo thói quen thật của bạn.",
            ]
        else:
            dong.append(f"── {len(self.suggestions)} đề nghị")
            for s in sorted(self.suggestions, key=lambda x: -x.count):
                dong.append(s.render())

        if self.boundary_hits:
            dong += [
                "",
                "── Tôi đã bị chặn ở những chỗ này (ĐÚNG như thiết kế, không phải thiếu sót)",
            ]
            for ten, n in self.boundary_hits:
                dong.append(f"  · {ten} — {n} lần")
            dong.append(
                "      Đây là ranh giới quyền, không phải khoảng trống năng lực. "
                "Không có công cụ nào lấp được nó, và không nên có."
            )

        if not self.empty:
            dong += [
                "",
                "Mọi đề nghị trên là ĐỀ NGHỊ. Lệnh nào bạn gõ cũng vẫn đi qua đủ "
                "cổng của nó: công cụ mới vẫn phải qua ba cổng rồi tới bạn duyệt.",
            ]
        return "\n".join(dong)


# --------------------------------------------------------------------------


def _doc_nhat_ky(chat_log: Path) -> list[dict[str, Any]]:
    if not Path(chat_log).is_file():
        return []
    ds: list[dict[str, Any]] = []
    for dong in Path(chat_log).read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong:
            continue
        try:
            ds.append(json.loads(dong))
        except json.JSONDecodeError:
            continue
    return ds


def analyse(
    *,
    chat_log: Path,
    usage_log: Any = None,
    playbook: Any = None,
    mined: Sequence[Any] = (),
    min_count: int = SO_LAN_DANG_KE,
) -> SuggestionReport:
    """Đọc mọi nhật ký có sẵn và rút ra đề nghị. Không có tín hiệu thì không đề nghị."""
    from eaa.agent import NGOAI_DANH_MUC

    luot = _doc_nhat_ky(chat_log)
    de_nghi: list[Suggestion] = []

    # -- 1. Agent đòi một năng lực nó không có ------------------------------
    #
    # Tách làm hai loại, và tách đúng chỗ này là quan trọng nhất của cả module:
    # bị chặn ở RANH GIỚI QUYỀN không phải một khoảng trống năng lực, và đề
    # nghị "viết công cụ" cho nó là đề nghị lách rào.
    ngoai_danh_muc: Counter[str] = Counter()
    ranh_gioi: Counter[str] = Counter()
    goc_ngoai = {k.split()[0] for k in NGOAI_DANH_MUC}
    for l in luot:
        for b in l.get("steps") or []:
            if not b.get("refused"):
                continue
            argv = [str(x) for x in (b.get("argv") or [])]
            if not argv:
                continue
            ten = " ".join(argv[:2])
            if argv[0] in goc_ngoai:
                ranh_gioi[ten] += 1
            else:
                ngoai_danh_muc[ten] += 1

    for ten, n in ngoai_danh_muc.most_common():
        if n < min_count:
            continue
        de_nghi.append(Suggestion(
            kind=LOAI_CONG_CU,
            subject=f"tôi đã {n} lần muốn gọi {ten!r} — không có lệnh nào làm việc ấy",
            evidence=f"{n} lượt bị từ chối vì ngoài danh mục, và {ten!r} không phải "
                     "một lệnh bị chặn có chủ ý",
            action=("tool", "propose", f"'{ten}'"),
            count=n,
        ))

    # -- 2. chuỗi việc đã lặp -----------------------------------------------
    for m in mined:
        de_nghi.append(Suggestion(
            kind=LOAI_KY_NANG,
            subject=" → ".join(m.commands),
            evidence=f"chuỗi {len(m.commands)} bước này đã lặp {m.count} lần",
            action=("skill", "mine", "--save", m.suggested_name),
            count=m.count,
        ))

    # -- 3. câu hỏi chạm trần số bước ---------------------------------------
    cham_tran = sum(1 for l in luot if l.get("hit_limit"))
    if cham_tran >= min_count:
        de_nghi.append(Suggestion(
            kind=LOAI_CAU_HOI_QUA_LON,
            subject="nhiều lượt chạm trần số bước rồi dừng giữa chừng",
            evidence=f"{cham_tran} lượt chạm trần — câu hỏi đang to hơn một lượt "
                     "chịu được, hoặc cùng một chuỗi việc đang bị làm lại từ đầu mỗi lần",
            action=("skill", "mine"),
            count=cham_tran,
        ))

    # -- 4. công cụ tự sinh hay hỏng hoặc chậm ------------------------------
    if usage_log is not None:
        for s in usage_log.concerning():
            ly_do = "hỏng" if s.concerning else "chậm"
            de_nghi.append(Suggestion(
                kind=LOAI_SUA_CONG_CU,
                subject=f"{s.tool} hay {ly_do}",
                evidence=(f"{s.ok}/{s.runs} lần đạt, trung bình {s.avg_ms} ms"
                          + (f" · lỗi gần nhất: {s.last_error[:90]}" if s.last_error else "")),
                action=("tool", "propose", f"'viết lại {s.tool}, lần trước hay {ly_do}'"),
                count=s.failed or s.runs,
            ))

    # -- 5. cách sửa trong sổ tay hay trượt ---------------------------------
    if playbook is not None:
        for m in playbook.all():
            if m.failed >= min_count and m.failed > m.worked:
                de_nghi.append(Suggestion(
                    kind=LOAI_CACH_SUA_KEM,
                    subject=f"{m.fix[:70]}",
                    evidence=f"{m.worked} lần trúng / {m.failed} lần trượt cho lỗi "
                             f"{m.symptom[:70]!r}",
                    action=("research", f"'{m.symptom[:60]}'"),
                    count=m.failed,
                ))

    return SuggestionReport(
        suggestions=tuple(de_nghi),
        boundary_hits=tuple(ranh_gioi.most_common()),
        turns_read=len(luot),
    )
