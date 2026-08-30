"""Agent tự phát hiện sai lệch so với thiết kế — N-905.

`CLAUDE.md`: "code bám thiết kế; nếu buộc phải lệch, ghi rõ và cập nhật tài
liệu tương ứng, không lệch ngầm." Xem `docs/SAI_LECH_THIET_KE.md` mục SL-58.

Điều mà sổ sai lệch KHÔNG tự làm được
--------------------------------------

Sổ ở `docs/SAI_LECH_THIET_KE.md` đầy đủ, nhưng nó được ghi TAY. Một sổ ghi tay
có đúng một điểm yếu, và điểm yếu ấy nằm ở chỗ nó im lặng: nó ghi được những
lệch mà người viết NHỚ RA, và không có gì báo khi ai đó thêm một module rồi
quên ghi. Mà lệch không ghi thì tài liệu và mã kể hai câu chuyện khác nhau —
đúng thứ quy tắc trên sinh ra để chặn.

Ba phép đối chiếu máy làm được
-------------------------------

1. **Module trong `eaa/` mà cây thư mục ở EAA-SDD-03 §2 không có** — và cũng
   chưa có mục nào trong sổ nói tới. Đây là dạng lệch hay xảy ra nhất: thêm
   một năng lực thì thêm một tệp, và tệp ấy lặng lẽ không có trong thiết kế.
2. **Năng lực pack khai báo mà interface không biết** — thực ra `platform.py`
   đã chặn ở lúc nạp, nên phép này chỉ xác nhận; giữ lại vì nó rẻ.
3. **Lệnh CLI không có trong danh sách 10 lệnh của SDD §6.**

Cả ba đều là phép đối chiếu DANH SÁCH, không phải phân tích ngữ nghĩa. Máy
không đọc được ý định của thiết kế, và nó không giả vờ đọc được — nó chỉ nói
"chỗ này có trong mã mà không có trong tài liệu, và cũng chưa được ghi nhận".

Vì sao nó chỉ ĐỀ XUẤT một mục nháp
-----------------------------------

Phân loại một lệch là BỔ SUNG, DỜI CHỖ hay LỆCH THẬT là một phán đoán về ý
định, và lý do của lệch chỉ người làm mới biết. Máy dựng khung mục kèm chỗ
trống; người điền lý do rồi mới dán vào sổ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "DeviationError",
    "Deviation",
    "DeviationScan",
    "scan",
    "REGISTER_FILE",
    "BO_SUNG",
    "DOI_CHO",
    "LECH_THAT",
]

#: Sổ sai lệch, ở tầng tài liệu.
REGISTER_FILE = "docs/SAI_LECH_THIET_KE.md"

BO_SUNG = "BỔ SUNG"
DOI_CHO = "DỜI CHỖ"
LECH_THAT = "LỆCH THẬT"

#: Tệp trong ``eaa/`` không phải một module chức năng.
_BO_QUA = {"__init__.py"}

_MUC_SO = re.compile(r"^##\s+SL-(\d+)\s+·\s+([^·]+)·\s*(.+)$", re.MULTILINE)


class DeviationError(Exception):
    """Không đọc được sổ sai lệch."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Deviation:
    """Một sai lệch máy phát hiện được, chưa có trong sổ."""

    subject: str
    kind: str
    where: str
    evidence: str
    suggested_class: str = BO_SUNG

    def draft(self, next_number: int) -> str:
        """Khung mục để dán vào sổ — chỗ nào máy không biết thì để trống rõ ràng."""
        return "\n".join(
            [
                f"## SL-{next_number:02d} · {self.suggested_class} · {self.subject}",
                "",
                "| | |",
                "|---|---|",
                "| **Tài liệu** | _(điền: mục nào của tài liệu nào nói về chỗ này)_ |",
                f"| **Máy phát hiện** | {self.evidence} |",
                f"| **Ở đâu** | `{self.where}` |",
                "| **Vì sao lệch** | _(điền: lý do KỸ THUẬT — máy không biết ý định)_ |",
                "| **Ảnh hưởng chức năng** | _(điền)_ |",
                "| **Cần cập nhật** | _(điền: tài liệu nào phải sửa ở bản sau)_ |",
                "",
                f"<!-- nháp do `eaa deviations --draft` dựng lúc {_now()};"
                " phân loại và lý do phải do người điền -->",
                "",
            ]
        )

    def render(self) -> str:
        return f"  [{self.kind}] {self.subject}\n      {self.evidence}\n      tại {self.where}"


@dataclass
class DeviationScan:
    """Kết quả một lượt quét."""

    found: tuple[Deviation, ...] = ()
    recorded: int = 0
    next_number: int = 1

    @property
    def clean(self) -> bool:
        return not self.found

    def draft_all(self) -> str:
        return "\n".join(
            d.draft(self.next_number + i) for i, d in enumerate(self.found)
        )

    def render(self) -> str:
        dong = [
            f"Quét sai lệch — sổ đang có {self.recorded} mục, "
            f"máy tìm thấy {len(self.found)} chỗ chưa ghi",
            "",
        ]
        if self.clean:
            dong += [
                "  Không tìm thấy chỗ nào trong mã mà tài liệu không nói tới và sổ",
                "  chưa ghi nhận.",
                "",
                "  Phép quét này đối chiếu DANH SÁCH, không đọc ý định. Nó bắt được",
                "  'có trong mã mà không có trong tài liệu'; nó KHÔNG bắt được một",
                "  module làm khác điều tài liệu mô tả. Chỗ ấy vẫn cần người đọc.",
            ]
            return "\n".join(dong)

        dong += [d.render() for d in self.found]
        dong += [
            "",
            "  Mỗi mục trên là một chỗ mã và tài liệu đang kể hai câu chuyện khác",
            "  nhau. Dựng nháp để ghi vào sổ: eaa deviations --draft",
            "",
            "  Máy KHÔNG tự phân loại BỔ SUNG / DỜI CHỖ / LỆCH THẬT: phân loại là",
            "  một phán đoán về ý định, và lý do của lệch chỉ người làm mới biết.",
        ]
        return "\n".join(dong)


# --------------------------------------------------------------------------


def _modules_trong_tai_lieu(sdd: Path) -> set[str]:
    """Tên tệp ``.py`` xuất hiện trong cây thư mục của EAA-SDD-03."""
    if not sdd.is_file():
        return set()
    van_ban = sdd.read_text(encoding="utf-8")
    return set(re.findall(r"\b([a-z_][a-z0-9_]*\.py)\b", van_ban))


def _modules_trong_so(register: Path) -> set[str]:
    if not register.is_file():
        return set()
    van_ban = register.read_text(encoding="utf-8")
    return set(re.findall(r"\b([a-z_][a-z0-9_]*\.py)\b", van_ban))


def _so_muc_da_ghi(register: Path) -> tuple[int, int]:
    """Đếm mục trong sổ và tìm số hiệu kế tiếp."""
    if not register.is_file():
        return 0, 1
    van_ban = register.read_text(encoding="utf-8")
    so = [int(m.group(1)) for m in _MUC_SO.finditer(van_ban)]
    return len(so), (max(so) + 1 if so else 1)


def _lenh_trong_tai_lieu(sdd: Path) -> set[str]:
    if not sdd.is_file():
        return set()
    van_ban = sdd.read_text(encoding="utf-8")
    return {m.lower() for m in re.findall(r"\beaa\s+([a-z][a-z0-9-]+)", van_ban)}


def scan(
    repo_root: str | Path,
    *,
    cli_commands: Sequence[str] = (),
    sdd_path: str = "docs/md/EAA-SDD-03_Thiet_ke_chi_tiet.md",
) -> DeviationScan:
    """Đối chiếu mã hiện có với tài liệu và với sổ sai lệch (N-905).

    Cố ý KHÔNG dùng mô hình: đây là phép đối chiếu danh sách, và một phép đối
    chiếu danh sách chạy bằng mô hình sẽ vừa chậm hơn, vừa tốn tiền, vừa có
    thể bỏ sót một cách không tái hiện được.
    """
    goc = Path(repo_root)
    sdd = goc / sdd_path
    so = goc / REGISTER_FILE

    da_ghi, ke_tiep = _so_muc_da_ghi(so)
    trong_tai_lieu = _modules_trong_tai_lieu(sdd) | _modules_trong_so(so)

    tim_thay: list[Deviation] = []

    engine = goc / "eaa"
    if engine.is_dir():
        for tep in sorted(engine.rglob("*.py")):
            ten = tep.name
            if ten in _BO_QUA:
                continue
            if ten in trong_tai_lieu:
                continue
            tim_thay.append(
                Deviation(
                    subject=f"`{tep.relative_to(goc)}` — module không có trong cây thư mục thiết kế",
                    kind="module",
                    where=str(tep.relative_to(goc)),
                    evidence=(
                        "Tệp có trong mã nhưng không xuất hiện ở cây thư mục "
                        "EAA-SDD-03 §2, và sổ sai lệch cũng chưa nhắc tới."
                    ),
                )
            )

    # Lệnh được coi là "đã ghi nhận" nếu nó xuất hiện ở SDD, HOẶC đã có một
    # mục trong sổ nói tới nó. Sổ là nơi hợp lệ để ghi một lệnh phát sinh sau
    # thiết kế — đó đúng là công dụng của nó.
    lenh_tai_lieu = _lenh_trong_tai_lieu(sdd)
    if so.is_file():
        lenh_tai_lieu |= {
            m.lower()
            for m in re.findall(r"`eaa ([a-z][a-z0-9-]+)", so.read_text(encoding="utf-8"))
        }

    for lenh in cli_commands:
        if lenh.lower() in lenh_tai_lieu:
            continue
        tim_thay.append(
            Deviation(
                subject=f"Lệnh `eaa {lenh}` không có trong danh sách lệnh của thiết kế",
                kind="lệnh",
                where="eaa/cli.py",
                evidence=(
                    "Lệnh đăng ký trong CLI nhưng không xuất hiện ở EAA-SDD-03 §6, "
                    "và sổ sai lệch cũng chưa nhắc tới."
                ),
            )
        )

    return DeviationScan(
        found=tuple(tim_thay), recorded=da_ghi, next_number=ke_tiep
    )
