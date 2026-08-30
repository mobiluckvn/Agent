"""Bảng năng lực — Agent làm được gì, cái nào đang chạy được, kiểm bằng gì.

EAA-AIS-05 §9 (môi trường công cụ), FR-ENV-01; NFR-05. Xem
`docs/SAI_LECH_THIET_KE.md` mục SL-70.

Câu hỏi module này trả lời
---------------------------

*"Agent này làm được những gì, và trong số đó cái nào đang thật sự chạy được
trên máy này?"*

Trước module này câu ấy phải ghép từ bốn chỗ: ``eaa --help`` cho danh sách
lệnh, ``eaa/agent.py`` cho biết lệnh nào Agent tự gọi được, ``eaa packs`` cho
năng lực nền tảng, ``eaa doctor`` cho công cụ ngoài. Bốn chỗ ấy đều đúng và
không chỗ nào trả lời trọn — nên người mới đến phải đọc mã trước khi biết mình
đang có gì trong tay.

Bốn tầng năng lực, và chúng hỏng theo bốn cách khác nhau
---------------------------------------------------------

1. **Lệnh CLI** — có mặt hay không là chuyện của bản cài. Hỏng thì là lỗi cài đặt.
2. **Lệnh Agent tự gọi** — tập con của tầng 1, và ranh giới ấy là một quyết
   định về QUYỀN chứ không về kỹ thuật. Xem ``eaa/agent.py``.
3. **Năng lực nền tảng** — do Platform Pack khai. Thiếu thì thêm pack, không
   sửa engine (NFR-05).
4. **Công cụ ngoài** — do máy có cài hay không. Thiếu thì ``eaa doctor --fix``.

Mỗi tầng có một cách bổ sung riêng, và trộn chúng lại là cách nhanh nhất để
người dùng đi sửa nhầm chỗ. Bảng này vì thế in ra CẢ cách bổ sung cho từng
tầng, không chỉ in trạng thái.

Điều bảng này KHÔNG làm
------------------------

Nó không chạy thử từng năng lực. Nó đọc khai báo và kiểm sự có mặt — nhanh, và
đủ để trả lời câu "tôi đang có gì". Câu "nó có chạy đúng không" thuộc về bộ
test và ``scripts/kiem_on_dinh.py``, và bảng nói rõ điều đó thay vì để người
đọc tưởng mình vừa được kiểm chứng.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "Capability",
    "CapabilityReport",
    "survey_capabilities",
    "TANG_LENH",
    "TANG_AGENT",
    "TANG_PACK",
    "TANG_CONG_CU",
]

TANG_LENH = "lệnh CLI"
TANG_AGENT = "Agent tự gọi"
TANG_PACK = "nền tảng"
TANG_CONG_CU = "công cụ ngoài"

#: Với mỗi tầng: thiếu thì bổ sung bằng cách nào. In ra cùng bảng, vì bốn tầng
#: hỏng theo bốn cách và người dùng dễ đi sửa nhầm chỗ.
CACH_BO_SUNG: dict[str, str] = {
    TANG_LENH: (
        "Thiếu nghĩa là bản cài hỏng hoặc cũ. Cài lại: pip install -e \".[dev]\""
    ),
    TANG_AGENT: (
        "Ranh giới này là một quyết định về QUYỀN, không về kỹ thuật. Thêm một "
        "lệnh vào tầng này = thêm một dòng Tool(...) trong eaa/agent.py — và đó "
        "phải là một thay đổi nhìn thấy trong lịch sử Git"
    ),
    TANG_PACK: (
        "Thiếu thì thêm hoặc sửa packs/<tên>/pack.yaml — KHÔNG sửa engine "
        "(NFR-05). Pack thứ hai đã chứng minh điều này làm được"
    ),
    TANG_CONG_CU: (
        "Thiếu thì: eaa doctor --fix (in lệnh cài, luôn hỏi trước). Công cụ lạ "
        "chưa có trong tools.yaml: eaa doctor --discover --propose"
    ),
}

#: Cách KIỂM từng tầng. Bảng này chỉ kiểm sự CÓ MẶT; muốn biết nó chạy đúng
#: không thì phải chạy những thứ dưới đây.
CACH_KIEM: dict[str, str] = {
    TANG_LENH: "pytest -q (bộ test đầy đủ) · scripts/kiem_on_dinh.py",
    TANG_AGENT: "pytest tests/test_tc61_chat.py",
    TANG_PACK: "pytest tests/test_platform_pack.py tests/test_tc47_pack_thu_hai.py",
    TANG_CONG_CU: "eaa doctor (quét) · smoke test + Tool Card sau khi cài",
}


@dataclass(frozen=True)
class Capability:
    """Một năng lực, và tình trạng thật của nó trên máy này."""

    tier: str
    name: str
    available: bool
    detail: str = ""

    def render(self) -> str:
        dau = "✓" if self.available else "✗"
        dong = f"  {dau} {self.name}"
        if self.detail:
            dong += f"   {self.detail}"
        return dong


@dataclass
class CapabilityReport:
    """Toàn bộ năng lực, xếp theo tầng."""

    capabilities: tuple[Capability, ...] = ()
    project: str = ""
    pack: str = ""

    def of_tier(self, tier: str) -> list[Capability]:
        return [c for c in self.capabilities if c.tier == tier]

    def missing(self) -> list[Capability]:
        return [c for c in self.capabilities if not c.available]

    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        SUY RA, không phải ĐÃ KIỂM: bảng này đọc khai báo và kiểm sự có mặt của
        chương trình trên PATH. Nó KHÔNG chạy thử năng lực nào, nên nó không
        chứng minh được cái gì chạy đúng — chỉ chứng minh cái gì có mặt.
        """
        from eaa.confidence import SUY_RA

        return SUY_RA

    def render(self, *, verbose: bool = False) -> str:
        from eaa.confidence import header

        dong = [
            "Bảng năng lực",
            "",
            header(self.confidence_level),
            "",
        ]
        if self.project:
            dong.append(f"  Dự án : {self.project}")
        if self.pack:
            dong.append(f"  Pack  : {self.pack}")
        dong.append("")

        for tang in (TANG_LENH, TANG_AGENT, TANG_PACK, TANG_CONG_CU):
            muc = self.of_tier(tang)
            if not muc:
                continue
            co = sum(1 for c in muc if c.available)
            dong.append(f"── {tang} — {co}/{len(muc)} có mặt")

            # Tầng lệnh dài và ít thông tin khi mọi thứ đều đủ; chỉ bung ra khi
            # được hỏi, hoặc khi có cái thiếu.
            bung = verbose or tang != TANG_LENH or co < len(muc)
            if bung:
                for c in muc:
                    if verbose or not c.available or tang != TANG_LENH:
                        dong.append(c.render())
            else:
                dong.append("      (đủ — thêm --verbose để xem từng lệnh)")

            dong.append(f"      kiểm bằng : {CACH_KIEM[tang]}")
            if co < len(muc):
                dong.append(f"      thiếu thì : {CACH_BO_SUNG[tang]}")
            dong.append("")

        thieu = self.missing()
        if thieu:
            dong += [
                f"CÒN THIẾU {len(thieu)} năng lực:",
                *[f"  · [{c.tier}] {c.name}" for c in thieu],
                "",
            ]
        dong += [
            "Bảng này kiểm SỰ CÓ MẶT, không chạy thử năng lực nào.",
            "Câu 'nó có chạy đúng không' thuộc về bộ test:  pytest -q",
            "và về  scripts/kiem_on_dinh.py  — đó mới là nơi trả lời được.",
        ]
        return "\n".join(dong)


def survey_capabilities(
    *,
    parser: Any = None,
    manifest: Any = None,
    tools_manifest: Any = None,
    project: str = "",
) -> CapabilityReport:
    """Dựng bảng năng lực từ dữ liệu thật, không từ một danh sách chép tay.

    Chép tay thì bảng lệch ngay lần thêm lệnh tiếp theo — và một bảng năng lực
    tự nó sai là thứ tệ hơn không có bảng.
    """
    from eaa.agent import TOOLBOX

    nang_luc: list[Capability] = []

    # -- tầng 1: lệnh CLI, đọc từ chính bộ phân tích đối số -----------------
    lenh_cli: set[str] = set()
    if parser is not None and getattr(parser, "_subparsers", None):
        for hd in parser._subparsers._group_actions:
            lenh_cli |= set(getattr(hd, "choices", {}) or {})
    for ten in sorted(lenh_cli):
        nang_luc.append(Capability(TANG_LENH, ten, True))

    # -- tầng 2: lệnh Agent tự gọi ------------------------------------------
    for t in TOOLBOX:
        goc = t.argv[0]
        nang_luc.append(
            Capability(
                TANG_AGENT,
                t.name,
                goc in lenh_cli if lenh_cli else True,
                "(ghi ra tệp)" if t.writes else "",
            )
        )

    # -- tầng 3: năng lực nền tảng do pack khai -----------------------------
    if manifest is not None:
        from eaa.platform import CAPABILITIES

        khai = set(getattr(manifest, "capabilities", {}) or {})
        for ten in CAPABILITIES:
            nang_luc.append(
                Capability(
                    TANG_PACK,
                    ten,
                    ten in khai,
                    "" if ten in khai else "pack chưa khai",
                )
            )
        for ten, thuoc_tinh in (
            ("khuôn firmware", "firmware"),
            ("khuôn firmware chẩn đoán", "diagnostics"),
            ("khuôn tệp tiêu đề", "interfaces"),
        ):
            nang_luc.append(
                Capability(TANG_PACK, ten, getattr(manifest, thuoc_tinh, None) is not None)
            )

    # -- tầng 4: công cụ ngoài ----------------------------------------------
    #
    # Kiểm bằng CHÍNH lệnh mà doctor kiểm, không bằng tên công cụ. Hai chỗ ấy
    # khác nhau: ``python`` được kiểm qua chỗ giữ ``{python}`` — trình thông
    # dịch đang chạy engine — chứ không phải cái đầu tiên gặp trong PATH. Kiểm
    # bằng tên trần thì bảng báo "thiếu python" cho một máy chạy được engine,
    # và một bảng năng lực tự nó sai còn tệ hơn không có bảng.
    from eaa.doctor import _resolve_argv

    for spec in sorted(tools_manifest or [], key=lambda s: getattr(s, "name", str(s))):
        ten = getattr(spec, "name", str(spec))
        argv = getattr(spec, "check", None) or [ten]
        chuong_trinh = _resolve_argv(list(argv))[0]
        duong_dan = chuong_trinh if Path(chuong_trinh).is_absolute() else shutil.which(chuong_trinh)
        nang_luc.append(
            Capability(TANG_CONG_CU, ten, duong_dan is not None, duong_dan or "không có trên PATH")
        )

    return CapabilityReport(
        capabilities=tuple(nang_luc),
        project=project,
        pack=getattr(manifest, "name", "") if manifest is not None else "",
    )
