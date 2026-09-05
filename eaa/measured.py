"""Số đo trên CHÍNH BO NÀY — sổ append-only, và lớp ngữ cảnh K8 (N-913).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-173.

Khoảng trống module này lấp
----------------------------

Bài học từ bo thật hiện chỉ tới được mô hình qua **lý do từ chối kỹ sư gõ tay**
ở G3. Mất một lần gõ là mất hẳn: `measurements.jsonl` giữ phán quyết chẩn đoán
DS-xx, `flash_log.jsonl` giữ tốc độ nạp, `hardware_profile.yaml` giữ mấy hằng
số ai đó chép tay vào — và **không đường nào trong ba đường ấy chạm tới bộ ghép
prompt**.

Hệ quả đo được: mốc gia tốc `-535` phải một người đo bằng DS-02 rồi tự tay chép
vào hồ sơ phần cứng, và tốc độ bootloader `57600` phải một người phát hiện rồi
tự nhớ. Lượt sinh mã kế tiếp không biết gì về cả hai, trừ khi người ấy nhớ nhắc
lại.

Vì sao tách khỏi hồ sơ phần cứng
---------------------------------

`hardware_profile.yaml` tả một **thiết kế**: chân nào nối vào đâu, chip gì, thạch
anh bao nhiêu. Sổ này tả **cái bo trên bàn**: số đọc được từ chính nó, hôm nào,
bằng kịch bản nào. SL-125 là lần hai thứ ấy bị lẫn vào nhau, và cái giá là robot
lao thẳng một phía.

Hai loại sự thật ấy hỏng theo hai kiểu và được sửa bằng hai cách, nên chúng phải
đứng riêng — kể cả khi cùng chảy vào một prompt.

Ba luật
-------

1. **Append-only + supersede**, cùng luật với mọi kho tri thức khác. Duyệt một
   số đo là GHI THÊM một bản ghi, không sửa bản cũ. Số đo cũ là dữ liệu của
   chương đánh giá: hôm ấy bo đọc ra thế, và điều đó không được viết lại.
2. **Chỉ số đo ĐÃ DUYỆT mới vào prompt.** Agent đo được thì nó ĐỀ XUẤT; người
   chốt. Một con số máy tự đo rồi tự tin là đúng sẽ đi thẳng vào mã của mọi
   module sau đó.
3. **Số đo thắng tài liệu khi hai bên lệch**, và lớp prompt nói thẳng câu ấy.
   Datasheet tả một dòng sản phẩm; số đo tả cái bo trên bàn.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "BoardFact",
    "MeasuredStore",
    "MeasuredError",
    "lop_so_do",
    "DE_XUAT",
    "DA_DUYET",
]

DE_XUAT = "proposed"
DA_DUYET = "approved"


class MeasuredError(Exception):
    """Thao tác không hợp lệ trên sổ số đo."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class BoardFact:
    """Một số đo trên bo, kèm xuất xứ đủ để đi kiểm lại."""

    name: str
    value: str
    unit: str = ""
    #: Đo bằng cách nào — kịch bản DS-xx, tên lệnh, hay "tay".
    source: str = ""
    note: str = ""
    status: str = DE_XUAT
    measured_at: str = field(default_factory=_now)
    approved_by: str = ""
    approved_at: str = ""

    def mot_dong(self) -> str:
        don_vi = f" {self.unit}" if self.unit else ""
        xuat_xu = f" (đo bằng {self.source}" if self.source else " (đo"
        xuat_xu += f", {self.measured_at[:10]})"
        ghi_chu = f" — {self.note}" if self.note else ""
        return f"{self.name} = {self.value}{don_vi}{xuat_xu}{ghi_chu}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MeasuredStore:
    """Sổ số đo của một dự án — nối tiếp, không ghi đè."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -- đọc ---------------------------------------------------------------

    def all(self) -> list[BoardFact]:
        if not self.path.is_file():
            return []
        ra: list[BoardFact] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                ra.append(BoardFact(**json.loads(dong)))
            except (json.JSONDecodeError, TypeError) as exc:
                raise MeasuredError(f"{self.path}: dòng hỏng — {exc}") from exc
        return ra

    def active(self) -> list[BoardFact]:
        """Bản ĐÃ DUYỆT mới nhất của mỗi tên số đo.

        "Mới nhất" theo THỨ TỰ GHI, không theo mốc thời gian: sổ nối tiếp nên
        thứ tự ghi là thứ tự thật, còn mốc thời gian là thứ người gõ vào và gõ
        sai được.
        """
        moi_nhat: dict[str, BoardFact] = {}
        for f in self.all():
            if f.status == DA_DUYET:
                moi_nhat[f.name] = f
        return sorted(moi_nhat.values(), key=lambda f: f.name)

    def pending(self) -> list[BoardFact]:
        """Số đo đã đề xuất mà chưa có bản duyệt nào SAU nó."""
        cuoi: dict[str, BoardFact] = {}
        for f in self.all():
            cuoi[f.name] = f
        return sorted(
            (f for f in cuoi.values() if f.status != DA_DUYET), key=lambda f: f.name
        )

    # -- ghi ---------------------------------------------------------------

    def _them(self, fact: BoardFact) -> BoardFact:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(fact.to_dict(), ensure_ascii=False) + "\n")
        return fact

    def propose(
        self,
        name: str,
        value: str,
        *,
        unit: str = "",
        source: str = "",
        note: str = "",
    ) -> BoardFact:
        """Ghi một số đo ở trạng thái ĐỀ XUẤT — chưa vào prompt."""
        if not name.strip() or not str(value).strip():
            raise MeasuredError("Số đo phải có tên và giá trị.")
        return self._them(
            BoardFact(
                name=name.strip(),
                value=str(value).strip(),
                unit=unit.strip(),
                source=source.strip(),
                note=note.strip(),
            )
        )

    def approve(self, name: str, *, actor: str) -> BoardFact:
        """Duyệt số đo mới nhất mang tên này — GHI THÊM, không sửa bản cũ."""
        if not actor.strip():
            raise MeasuredError(
                "Duyệt số đo phải có tên người duyệt: một quyết định không "
                "gắn tên là một quyết định không ai chịu trách nhiệm."
            )
        ung_vien = [f for f in self.all() if f.name == name]
        if not ung_vien:
            raise MeasuredError(f"Chưa có số đo nào tên {name!r} trong sổ.")
        cuoi = ung_vien[-1]
        if cuoi.status == DA_DUYET:
            raise MeasuredError(f"{name} đã được duyệt lúc {cuoi.approved_at}.")
        from dataclasses import replace

        return self._them(
            replace(
                cuoi,
                status=DA_DUYET,
                approved_by=actor.strip(),
                approved_at=_now(),
            )
        )

    # -- hiển thị ----------------------------------------------------------

    def render(self) -> str:
        da_duyet = self.active()
        cho = self.pending()
        if not da_duyet and not cho:
            return (
                "Sổ số đo trống. Agent đề xuất bằng 'eaa measured add', "
                "người chốt bằng 'eaa measured approve'."
            )
        dong: list[str] = []
        if da_duyet:
            dong.append(f"ĐÃ DUYỆT — {len(da_duyet)} số đo, và chúng VÀO prompt:")
            dong += [f"  ✓ {f.mot_dong()}   [{f.approved_by}]" for f in da_duyet]
        if cho:
            dong.append("")
            dong.append(f"CHỜ DUYỆT — {len(cho)} số đo, KHÔNG vào prompt:")
            dong += [f"  · {f.mot_dong()}" for f in cho]
            dong.append("")
            dong.append("  Chốt một số: eaa measured approve <tên> --actor '<tên bạn>'")
        return "\n".join(dong)


def lop_so_do(facts: Iterable[BoardFact]) -> str:
    """Lớp K8 — số đo của chính bo này, cho bộ ghép prompt.

    Câu *"số đo thắng tài liệu"* nằm trong lớp, không nằm trong lời dặn chung:
    mô hình đọc lớp này ngay cạnh lớp trích đoạn tài liệu, nên chỗ nói ra thứ
    tự ưu tiên phải là chỗ hai bên gặp nhau.
    """
    muc = list(facts)
    if not muc:
        return ""
    dong = [
        "## SỐ ĐO TRÊN CHÍNH BO NÀY — ĐÃ KIỂM",
        "",
        "Những số dưới đây ĐO ĐƯỢC trên bo đang dùng, không đọc từ tài liệu.",
        "Khi số đo và tài liệu lệch nhau thì SỐ ĐO THẮNG: tài liệu tả một dòng",
        "sản phẩm, số đo tả đúng cái bo trên bàn.",
        "",
    ]
    dong += [f"- {f.mot_dong()}" for f in muc]
    return "\n".join(dong)
