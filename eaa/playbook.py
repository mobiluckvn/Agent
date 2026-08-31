"""Sổ tay lỗi — tra chỗ mình đã biết trước khi đi hỏi chỗ khác.

EAA-AIS-05 §7, §12; FR-KB-04, NFR-08. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-75.

Khoảng trống module này lấp
----------------------------

Vòng tự sửa đã sửa thành công hàng trăm lỗi biên dịch, và mỗi lần sửa xong nó
vứt đi thứ đắt nhất vừa tạo ra: **cặp (lỗi này → cách sửa này đã hiệu quả)**.
Lần sau gặp đúng lỗi ấy, Agent lại đốt một lượt gọi mô hình để nghĩ lại từ đầu.

Sổ tay này là chỗ chứa những cặp ấy. Nó rẻ vì dữ liệu đã có sẵn — chỉ thiếu
chỗ để và chỗ tra.

Vân tay lỗi: bỏ đi phần thay đổi, giữ lại phần lặp
---------------------------------------------------

Hai lần gặp cùng một lỗi thì thông báo gần như không bao giờ giống hệt nhau:
khác đường dẫn, khác số dòng, khác địa chỉ, khác tên biến tạm. Tra theo chuỗi
nguyên văn thì tỉ lệ trúng gần bằng không.

:func:`signature` chuẩn hóa đi những phần ấy — đường dẫn tuyệt đối, số dòng,
số hex, chuỗi trong nháy, số phiên bản — rồi băm phần còn lại. Điều quan trọng
là nó **không** bỏ những từ mang nghĩa (``undefined reference``, ``permission
denied``), vì đó chính là phần phân biệt lỗi này với lỗi kia.

Vì sao có cả đếm trúng lẫn đếm trượt
-------------------------------------

Một cách sửa từng hiệu quả một lần không có nghĩa nó luôn hiệu quả. Mỗi mục
mang hai bộ đếm, và :meth:`Playbook.lookup` xếp theo tỉ lệ trúng chứ theo thứ
tự thời gian. Một sổ tay chỉ ghi thành công là một sổ tay sẽ tự tin dần lên
theo hướng sai — và nó sẽ tự tin nhất đúng ở chỗ nó sai nhiều nhất.

Phạm vi: một cách sửa cho toolchain này không đúng cho toolchain kia
---------------------------------------------------------------------

Sổ tay nằm ở gốc kho, dùng chung mọi dự án — đó là điểm của nó. Nhưng dùng
chung KHÔNG có nghĩa là áp bừa: ``undefined reference`` khi dịch cho một họ
MCU được sửa bằng một cờ liên kết mà họ khác không có.

Nên mỗi mục mang một **phạm vi**, cùng bộ với ``eaa/memory.py``:

* ``toàn cục`` — đúng ở mọi nơi. Lỗi quyền, lỗi mạng, lỗi cú pháp Python.
* ``mcu:<họ>`` — đúng theo họ chip. Phần lớn lỗi toolchain rơi vào đây, nên
  đây là mặc định khi ghi từ trong một dự án.
* ``dự án:<tên>`` — chỉ đúng ở một dự án.

:meth:`Playbook.lookup` chỉ trả về mục thuộc phạm vi áp dụng được cho bối cảnh
đang hỏi. Không có luật này, sổ tay càng dày càng nguy: nó gợi ý những cách sửa
từng đúng ở một chỗ khác, và gợi ý ấy trông y hệt gợi ý đúng.

Sổ tay KHÔNG tự áp cách sửa
----------------------------

:meth:`lookup` trả về gợi ý; áp hay không là việc của vòng tự sửa, và cách sửa
lấy từ sổ tay vẫn phải đi qua đủ các cổng như mọi patch khác. Bỏ qua cổng vì
"lần trước cách này chạy được" là đúng loại lối tắt mà cả hệ thống này dựng ra
để chặn.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from eaa.memory import MEMORY_DIR, TOAN_CUC, scope_du_an, scope_mcu

__all__ = [
    "PlaybookEntry",
    "Playbook",
    "signature",
    "normalise",
    "PLAYBOOK_FILE",
    "SO_GOI_Y_TOI_DA",
]

PLAYBOOK_FILE = "playbook.jsonl"

#: Trần số gợi ý trả về. Nhiều gợi ý không giúp mô hình chọn đúng hơn; nó chỉ
#: làm loãng prompt và đẩy phần mã cần sửa ra ngoài ngân sách.
SO_GOI_Y_TOI_DA = 3

#: Những mẫu bị xóa khỏi thông báo lỗi trước khi băm. Thứ tự có ý nghĩa: mẫu
#: hẹp chạy trước mẫu rộng.
_XOA: tuple[tuple[re.Pattern[str], str], ...] = (
    # đường dẫn tuyệt đối và tương đối có nhiều đoạn
    (re.compile(r"(?:[A-Za-z]:)?(?:/[\w.\-+]+){2,}"), " <đường-dẫn> "),
    # địa chỉ hex và số hex dài
    (re.compile(r"\b0[xX][0-9a-fA-F]+\b"), " <hex> "),
    # số phiên bản
    (re.compile(r"\b\d+\.\d+(?:\.\d+)*\b"), " <phiên-bản> "),
    # số dòng / cột kiểu :12:34
    (re.compile(r":\d+(?::\d+)?\b"), " "),
    # chuỗi trong nháy — tên tệp, tên biến, tên gói thay đổi theo lần chạy
    (re.compile(r"['\"`‘’“”]([^'\"`‘’“”]{1,80})['\"`‘’“”]"), " <tên> "),
    # thư mục tạm
    (re.compile(r"\b(?:tmp|temp)[\w\-./]*", re.I), " <tạm> "),
    # số còn lại
    (re.compile(r"\b\d+\b"), " <số> "),
)

#: Dòng mở đầu thường là dòng mang nghĩa nhất; phần đuôi hay là vết ngăn xếp.
_MAX_DONG = 6


def normalise(text: str) -> str:
    """Bỏ phần thay đổi giữa hai lần gặp, giữ phần lặp."""
    dong = [d.strip() for d in (text or "").strip().splitlines() if d.strip()]
    van_ban = " ".join(dong[:_MAX_DONG]).lower()
    for mau, thay in _XOA:
        van_ban = mau.sub(thay, van_ban)
    return re.sub(r"\s+", " ", van_ban).strip()


def signature(text: str) -> str:
    """Vân tay của một lỗi. Cùng lỗi → cùng vân tay, kể cả khác đường dẫn."""
    chuan = normalise(text)
    if not chuan:
        return ""
    return "e-" + hashlib.sha256(chuan.encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tu(van_ban: str) -> set[str]:
    return {t for t in re.split(r"\W+", normalise(van_ban)) if len(t) > 2}


@dataclass(frozen=True)
class PlaybookEntry:
    """Một cặp (lỗi → cách sửa), kèm hai bộ đếm."""

    signature: str
    symptom: str
    fix: str
    context: str = ""
    evidence: str = ""
    source_url: str = ""
    #: Phạm vi áp dụng — xem phần đầu tài liệu module.
    scope: str = TOAN_CUC
    worked: int = 0
    failed: int = 0
    created_at: str = ""
    last_used_at: str = ""

    @property
    def attempts(self) -> int:
        return self.worked + self.failed

    @property
    def success_rate(self) -> float:
        """Tỉ lệ trúng, có làm mềm để một lần trúng không nhảy lên 100%.

        Một mục 1 trúng / 0 trượt và một mục 20 trúng / 0 trượt không đáng
        được xếp ngang nhau; công thức Laplace cho cái thứ hai đứng trước mà
        không cần thêm một quy tắc riêng.
        """
        return (self.worked + 1.0) / (self.attempts + 2.0)

    @property
    def confidence_level(self) -> str:
        """SUY RA khi đã trúng ít nhất một lần; GIẢ ĐỊNH khi chưa từng thử.

        Không bao giờ ĐÃ KIỂM: cách sửa này chạy được ở LẦN TRƯỚC, trên mã
        khác, có thể trên phiên bản công cụ khác.
        """
        from eaa.confidence import GIA_DINH, SUY_RA

        return SUY_RA if self.worked else GIA_DINH

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "symptom": self.symptom,
            "fix": self.fix,
            "context": self.context,
            "evidence": self.evidence,
            "source_url": self.source_url,
            "scope": self.scope,
            "worked": self.worked,
            "failed": self.failed,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PlaybookEntry":
        return cls(
            signature=str(d.get("signature", "")),
            symptom=str(d.get("symptom", "")),
            fix=str(d.get("fix", "")),
            context=str(d.get("context", "")),
            evidence=str(d.get("evidence", "")),
            source_url=str(d.get("source_url", "")),
            scope=str(d.get("scope", TOAN_CUC)),
            worked=int(d.get("worked", 0)),
            failed=int(d.get("failed", 0)),
            created_at=str(d.get("created_at", "")),
            last_used_at=str(d.get("last_used_at", "")),
        )

    def render(self) -> str:
        diem = f"{self.worked}✓/{self.failed}✗"
        dong = [f"  [{self.signature}]  {diem}  ({self.scope})   {self.symptom[:90]}",
                f"      → {self.fix}"]
        if self.context:
            dong.append(f"      bối cảnh: {self.context}")
        if self.source_url:
            dong.append(f"      nguồn: {self.source_url}")
        return "\n".join(dong)


@dataclass
class Playbook:
    """Kho append-only các cặp (lỗi → cách sửa), dùng chung mọi dự án."""

    root: Path
    filename: str = PLAYBOOK_FILE

    @property
    def path(self) -> Path:
        return self.root / MEMORY_DIR / self.filename

    # ----------------------------------------------------------------- ghi ---

    def record(
        self,
        error_text: str,
        fix: str,
        *,
        context: str = "",
        evidence: str = "",
        source_url: str = "",
        scope: str = TOAN_CUC,
        worked: bool = True,
    ) -> PlaybookEntry:
        """Ghi một cặp mới. KHÔNG sửa dòng cũ — cộng dồn diễn ra lúc đọc."""
        van_tay = signature(error_text)
        if not van_tay:
            raise ValueError("Không rút được vân tay từ chuỗi lỗi rỗng")
        muc = PlaybookEntry(
            signature=van_tay,
            symptom=" ".join((error_text or "").split())[:400],
            fix=fix.strip(),
            context=context.strip(),
            evidence=evidence.strip(),
            source_url=source_url.strip(),
            scope=scope or TOAN_CUC,
            worked=1 if worked else 0,
            failed=0 if worked else 1,
            created_at=_now(),
            last_used_at=_now(),
        )
        self._noi_them(muc)
        return muc

    def mark(self, sig: str, *, worked: bool, fix: str = "") -> None:
        """Ghi thêm một lần thử của một mục đã có.

        Ghi THÊM một dòng chứ không sửa dòng cũ: lịch sử "cách này trúng mấy
        lần, trượt mấy lần, vào lúc nào" chính là thứ làm sổ tay đáng tin, và
        cộng dồn tại chỗ sẽ xóa mất nó.
        """
        cu = self.get(sig)
        if cu is None:
            raise KeyError(f"Sổ tay không có mục {sig!r}")
        self._noi_them(PlaybookEntry(
            signature=sig,
            symptom=cu.symptom,
            fix=fix.strip() or cu.fix,
            context=cu.context,
            evidence=cu.evidence,
            source_url=cu.source_url,
            scope=cu.scope,
            worked=1 if worked else 0,
            failed=0 if worked else 1,
            created_at=cu.created_at,
            last_used_at=_now(),
        ))

    def _noi_them(self, muc: PlaybookEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(muc.to_dict(), ensure_ascii=False) + "\n")

    # ----------------------------------------------------------------- đọc ---

    def all(self) -> list[PlaybookEntry]:
        """Đọc và cộng dồn theo vân tay. Tệp giữ nguyên từng lần thử."""
        if not self.path.is_file():
            return []
        gop: dict[str, PlaybookEntry] = {}
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                m = PlaybookEntry.from_dict(json.loads(dong))
            except json.JSONDecodeError:
                continue
            cu = gop.get(m.signature)
            if cu is None:
                gop[m.signature] = m
                continue
            gop[m.signature] = PlaybookEntry(
                signature=m.signature,
                # Cách sửa MỚI NHẤT thắng: nếu người ta ghi lại một cách khác,
                # đó là vì cách cũ không còn đúng.
                symptom=cu.symptom or m.symptom,
                fix=m.fix or cu.fix,
                context=m.context or cu.context,
                evidence=m.evidence or cu.evidence,
                source_url=m.source_url or cu.source_url,
                scope=m.scope or cu.scope,
                worked=cu.worked + m.worked,
                failed=cu.failed + m.failed,
                created_at=cu.created_at or m.created_at,
                last_used_at=max(cu.last_used_at, m.last_used_at),
            )
        return list(gop.values())

    def get(self, sig: str) -> PlaybookEntry | None:
        for m in self.all():
            if m.signature == sig:
                return m
        return None

    def in_scope(self, *, project: str = "", mcu: str = "") -> list[PlaybookEntry]:
        """Mục áp dụng được cho bối cảnh này: toàn cục + đúng họ + đúng dự án.

        KHÔNG trả về mục của dự án khác hay họ chip khác. Sổ tay càng dày thì
        luật này càng quan trọng: nó gợi ý những cách sửa từng đúng ở một chỗ
        khác, và một gợi ý sai chỗ trông y hệt một gợi ý đúng.
        """
        if not project and not mcu:
            return self.all()
        pham_vi = {TOAN_CUC, scope_du_an(project) if project else "",
                   scope_mcu(mcu) if mcu else ""}
        return [m for m in self.all() if m.scope in pham_vi]

    def lookup(
        self,
        error_text: str,
        *,
        limit: int = SO_GOI_Y_TOI_DA,
        project: str = "",
        mcu: str = "",
    ) -> list[PlaybookEntry]:
        """Tra một lỗi. Khớp vân tay trước, gần đúng sau, xếp theo tỉ lệ trúng."""
        ds = self.in_scope(project=project, mcu=mcu)
        if not ds:
            return []

        van_tay = signature(error_text)
        khop = [m for m in ds if m.signature == van_tay]
        if khop:
            return sorted(khop, key=lambda m: -m.success_rate)[:limit]

        # Không khớp chính xác thì so theo phần từ chung — cùng một loại lỗi
        # trên hai công cụ khác nhau vẫn dùng chung mấy từ mang nghĩa.
        tu = _tu(error_text)
        if not tu:
            return []
        diem: list[tuple[float, PlaybookEntry]] = []
        for m in ds:
            chung = tu & _tu(m.symptom)
            if not chung:
                continue
            phu = len(chung) / max(len(tu), 1)
            if phu >= 0.5:
                diem.append((phu * m.success_rate, m))
        return [m for _, m in sorted(diem, key=lambda x: -x[0])][:limit]

    def hint(self, error_text: str, *, limit: int = SO_GOI_Y_TOI_DA,
             project: str = "", mcu: str = "") -> str:
        """Đoạn gợi ý để chèn vào prompt tự sửa. Rỗng khi không có gì để nói.

        Nói rõ đây là gợi ý ĐÃ TỪNG hiệu quả, kèm số lần trúng/trượt — mô hình
        cần biết mức tin cậy để không bám vào một cách sửa 1 trúng / 4 trượt.
        """
        ds = self.lookup(error_text, limit=limit, project=project, mcu=mcu)
        if not ds:
            return ""
        dong = ["Sổ tay lỗi — những cách đã từng thử với lỗi giống thế này:"]
        for m in ds:
            dong.append(f"  · ({m.worked} lần trúng / {m.failed} lần trượt) {m.fix}")
            if m.source_url:
                dong.append(f"      nguồn: {m.source_url}")
        dong.append(
            "Đây là GỢI Ý, không phải kết luận: cách này chạy được trên mã khác, "
            "có thể trên phiên bản công cụ khác. Patch vẫn phải qua đủ cổng."
        )
        return "\n".join(dong)

    def render(self, *, limit: int = 30, entries: Sequence[PlaybookEntry] | None = None) -> str:
        from eaa.confidence import SUY_RA, header

        ds = sorted(self.all() if entries is None else entries,
                    key=lambda m: (-m.attempts, -m.success_rate))
        dong = ["Sổ tay lỗi", "", header(SUY_RA), ""]
        if not ds:
            # Phân biệt "sổ trống" với "sổ có nhưng không mục nào hợp bối cảnh".
            # Hai chuyện khác hẳn nhau: cái sau nghĩa là kinh nghiệm CÓ, chỉ là
            # của họ chip khác — nói "chưa ghi lỗi nào" ở đó là nói sai.
            if entries is not None and self.all():
                dong.append(
                    "  (sổ tay có mục, nhưng không mục nào thuộc phạm vi này — "
                    "kinh nghiệm của họ chip khác không tự nhiên đúng ở đây)"
                )
            else:
                dong.append(
                    "  (chưa ghi lỗi nào — sổ tay bồi lên sau mỗi lần vòng tự sửa thành công)"
                )
            return "\n".join(dong)
        dong.append(f"── {len(ds)} loại lỗi đã gặp")
        dong += [m.render() for m in ds[:limit]]
        if len(ds) > limit:
            dong.append(f"  … và {len(ds) - limit} loại nữa")
        tong = sum(m.attempts for m in ds)
        trung = sum(m.worked for m in ds)
        dong += ["", f"{trung}/{tong} lần áp dụng thành công."]
        return "\n".join(dong)
