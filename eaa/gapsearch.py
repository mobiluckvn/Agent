"""Bậc thang tìm kiếm bổ sung — bước 3 của quy trình P7.

EAA-AIS-05 §6.2 bước 3, FR-GAP-02; TC-24. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-41.

Bảng kiểm thông tin cần (RIC) đã biết nói "thiếu thanh ghi X" từ Sprint 3, và
Readiness Check đã biết chặn vòng sinh mã. Nhưng giữa hai việc ấy còn một việc
mà thiết kế mô tả kỹ và mã thì chưa làm: **đi tìm thứ còn thiếu.**

Dấu vết của khoảng trống ấy nằm ngay trong mã: ``RicItem.search_rounds`` tồn
tại, ``MAX_SEARCH_ROUNDS`` tồn tại, dòng chặn "đã tìm N vòng — chuyển kỹ sư"
tồn tại — mà không chỗ nào tăng bộ đếm, vì không ai đi tìm. Agent nói "thiếu"
rồi đứng đó, và người dùng phải tự đoán ra rằng mình cần đi nạp thêm tài liệu.

Ba bậc, rẻ và đáng tin trước
-----------------------------

1. **Tài liệu người dùng đã cung cấp.** Rẻ nhất và đáng tin nhất, vì nguồn đã
   được người chọn. Thường thứ cần tìm đã nằm trong kho rồi — chỉ là ở trạng
   thái ``proposed`` chưa ai duyệt, hoặc thuộc một chunk chưa nối vào ngoại vi
   này trong đồ thị. Tìm ở đây trước là tôn trọng công sức người đã bỏ ra.

2. **Hỏi người dùng ĐÍCH DANH.** Không phải "thiếu thông tin, bạn bổ sung đi",
   mà "cần trang tài liệu mô tả thanh ghi TCCR1A ở chế độ CTC". Câu hỏi mơ hồ
   đẩy việc chẩn đoán ngược lại cho người, và đó đúng là việc Agent phải làm.

3. **Tra nguồn cho phép trên web.** Chỉ trong miền của nhà sản xuất, dùng đúng
   bộ lọc mà ``ingest.check_web_source`` đã dựng.

Điều không đổi ở cả ba bậc
---------------------------

Thứ tìm được là **đề xuất**, phải qua G2 như mọi chunk khác. Bậc 3 dễ khiến
người ta quên điều này nhất: một câu trả lời trôi chảy của mô hình trông y hệt
một trích đoạn tra được từ tài liệu gốc. Nên bậc 3 BẮT BUỘC kèm nguồn, nguồn
phải qua bộ lọc miền, và không có nguồn thì kết quả bị bỏ — không hạ xuống
thành "tham khảo".

Và Agent vẫn **cấm đoán** (FR-GAP-03). Bậc thang này đi tìm, không đi suy diễn.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from eaa.readiness import MAX_SEARCH_ROUNDS, ItemStatus, Ric, RicItem, SEARCH_TIERS

__all__ = [
    "GapSearchError",
    "TierResult",
    "ResolutionReport",
    "SearchLedger",
    "GapResolver",
    "SEARCH_LEDGER",
]

#: Bộ đếm vòng tìm của từng mục, sống qua nhiều phiên làm việc.
SEARCH_LEDGER = ".eaa/gap_search.json"

#: Kết cục một bậc.
FOUND = "tìm thấy"
ASKED = "đã hỏi người"
NOT_FOUND = "không thấy"
SKIPPED = "bỏ qua"
EXHAUSTED = "hết lượt"


class GapSearchError(Exception):
    """Không chạy được bậc thang tìm kiếm."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class TierResult:
    """Kết quả một bậc cho một mục."""

    item_key: str
    tier: int
    outcome: str
    detail: str = ""
    #: Chunk đề xuất, nếu bậc này tìm được thứ gì. Luôn ở trạng thái chờ G2.
    proposal: Any = None
    #: Câu hỏi đích danh, nếu là bậc 2.
    question: str = ""

    def render(self) -> str:
        nhan = f"  bậc {self.tier} ({SEARCH_TIERS[self.tier - 1].name}): {self.outcome}"
        if self.detail:
            nhan += f" — {self.detail}"
        return nhan


@dataclass
class ResolutionReport:
    """Kết quả một vòng tìm cho cả bảng kiểm."""

    module_id: str
    results: list[TierResult] = field(default_factory=list)
    #: Mục đã hết lượt tìm, phải chuyển người.
    handed_off: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    proposals: list[Any] = field(default_factory=list)

    @property
    def found_any(self) -> bool:
        return bool(self.proposals)

    def render(self) -> str:
        if not self.results and not self.handed_off:
            return "Không mục nào cần tìm — bảng kiểm đã đủ."

        dong: list[str] = []
        theo_muc: dict[str, list[TierResult]] = {}
        for r in self.results:
            theo_muc.setdefault(r.item_key, []).append(r)

        for khoa, ds in theo_muc.items():
            dong.append(f"{khoa}:")
            dong += [r.render() for r in ds]
            dong.append("")

        if self.questions:
            dong.append("CẦN BẠN CUNG CẤP — nêu đích danh:")
            dong += [f"  · {c}" for c in self.questions]
            dong.append("")

        if self.proposals:
            dong.append(
                f"{len(self.proposals)} chunk ĐỀ XUẤT đã ghi, đang chờ duyệt tại G2."
            )
            dong.append(
                "  Thứ tìm được dù từ bậc nào cũng chỉ là đề xuất — xem rồi duyệt:"
            )
            dong.append("      eaa gate approve G2")
            dong.append("")

        if self.handed_off:
            dong.append(
                f"Đã tìm đủ {MAX_SEARCH_ROUNDS} vòng cho: {', '.join(self.handed_off)}"
            )
            dong.append(
                "  Chuyển kỹ sư xử lý. Agent KHÔNG đoán giá trị để lấp chỗ trống "
                "(FR-GAP-03):\n"
                "  một giá trị đoán trông y hệt một giá trị tra được, và nó sẽ đi "
                "qua mọi cổng phía sau."
            )
        return "\n".join(dong).rstrip() + "\n"


class SearchLedger:
    """Bộ đếm vòng tìm, sống qua nhiều phiên.

    Đếm trong bộ nhớ thì mỗi lần chạy lại là một lần đếm lại từ đầu, và trần
    ``MAX_SEARCH_ROUNDS`` không bao giờ chạm tới — tức là cái trần ấy chỉ tồn
    tại trên giấy.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def _doc(self) -> dict[str, int]:
        if not self.path.is_file():
            return {}
        try:
            du_lieu = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GapSearchError(f"{self.path}: sổ đếm vòng tìm hỏng — {exc}") from exc
        return {str(k): int(v.get("rounds", 0)) for k, v in (du_lieu or {}).items()}

    @staticmethod
    def _khoa(module_id: str, item_key: str) -> str:
        return f"{module_id}::{item_key}"

    def rounds(self, module_id: str, item_key: str) -> int:
        return self._doc().get(self._khoa(module_id, item_key), 0)

    def bump(self, module_id: str, item_key: str) -> int:
        tho: dict[str, Any] = {}
        if self.path.is_file():
            try:
                tho = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except json.JSONDecodeError:
                tho = {}
        khoa = self._khoa(module_id, item_key)
        so = int((tho.get(khoa) or {}).get("rounds", 0)) + 1
        tho[khoa] = {"rounds": so, "last_search": _now()}

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(tho, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return so


_JSON_CHUNK = """{
  "found": true,
  "source": "<URL trang chính thức của nhà sản xuất; BẮT BUỘC>",
  "topic": "<một câu mô tả trích đoạn>",
  "registers": ["<TÊN_THANH_GHI>"],
  "body": "<bảng thanh ghi–bit dạng markdown, nêu rõ từng bit và giá trị>"
}"""


@dataclass
class GapResolver:
    """Chạy bậc thang ba bậc cho những mục còn THIẾU."""

    kb: Any
    graph: Any = None
    ledger: SearchLedger | None = None
    llm: Any = None
    #: Bậc 2 — hàm hỏi người. ``(câu hỏi) -> câu trả lời``; rỗng nghĩa là chưa
    #: trả lời. Không có hàm này thì bậc 2 chỉ NÊU câu hỏi, không tự trả lời hộ.
    ask: Callable[[str], str] | None = None
    #: Nơi ghi chunk đề xuất tìm được.
    datasheets_dir: Path | None = None
    #: Bật bậc 3. Tắt mặc định: bậc 3 tốn lời gọi mô hình và cần mạng.
    allow_web: bool = False

    # -- điều phối ---------------------------------------------------------

    def resolve(self, ric: Ric) -> ResolutionReport:
        bao_cao = ResolutionReport(module_id=ric.module_id)
        so = self.ledger or SearchLedger(Path(".eaa/gap_search.json"))

        for muc in ric.items:
            if muc.status != ItemStatus.MISSING:
                continue

            da_tim = so.rounds(ric.module_id, muc.key)
            if da_tim >= MAX_SEARCH_ROUNDS:
                bao_cao.handed_off.append(muc.key)
                bao_cao.results.append(
                    TierResult(muc.key, 3, EXHAUSTED, f"đã tìm {da_tim} vòng")
                )
                continue

            so.bump(ric.module_id, muc.key)
            self._mot_muc(muc, bao_cao)

        return bao_cao

    def _mot_muc(self, muc: RicItem, bao_cao: ResolutionReport) -> None:
        """Leo thang cho một mục; dừng ngay khi một bậc tìm được."""
        bac1 = self._bac1_kho_san_co(muc)
        bao_cao.results.append(bac1)
        if bac1.outcome == FOUND:
            return

        bac2 = self._bac2_hoi_nguoi(muc)
        bao_cao.results.append(bac2)
        if bac2.question:
            bao_cao.questions.append(bac2.question)
        if bac2.outcome == FOUND and bac2.proposal is not None:
            bao_cao.proposals.append(bac2.proposal)
            return

        bac3 = self._bac3_tra_web(muc)
        bao_cao.results.append(bac3)
        if bac3.outcome == FOUND and bac3.proposal is not None:
            bao_cao.proposals.append(bac3.proposal)

    # -- bậc 1 -------------------------------------------------------------

    def _bac1_kho_san_co(self, muc: RicItem) -> TierResult:
        """Lục lại tài liệu người dùng đã đưa mà chưa trích xuất hết.

        Bao gồm cả chunk ở trạng thái ``proposed``: rất thường thứ cần tìm đã
        nằm trong kho, chỉ là chưa ai duyệt nó tại G2.
        """
        try:
            tat_ca = self.kb.datasheets.all()
        except Exception as exc:  # kho chưa dựng
            return TierResult(muc.key, 1, SKIPPED, f"không đọc được kho: {exc}")

        khoa = muc.key.upper()
        ung_vien = [
            c
            for c in tat_ca
            if not c.is_active
            and (khoa in {r.upper() for r in c.registers} or khoa in c.body.upper())
        ]
        if not ung_vien:
            return TierResult(muc.key, 1, NOT_FOUND, "kho hiện có không nhắc tới mục này")

        ten = ", ".join(c.id for c in ung_vien[:3])
        return TierResult(
            muc.key,
            1,
            FOUND,
            f"đã có trong kho nhưng CHƯA DUYỆT: {ten} — duyệt tại G2 là đủ, "
            "không cần tìm thêm ở đâu",
        )

    # -- bậc 2 -------------------------------------------------------------

    def _bac2_hoi_nguoi(self, muc: RicItem) -> TierResult:
        """Nêu ĐÍCH DANH thứ còn thiếu.

        Câu hỏi mơ hồ ("thiếu thông tin, bạn bổ sung đi") đẩy việc chẩn đoán
        ngược lại cho người — mà chẩn đoán đúng là việc Agent vừa làm xong.
        """
        cau_hoi = self._cau_hoi(muc)
        if self.ask is None:
            return TierResult(muc.key, 2, ASKED, "chưa có ai để hỏi", question=cau_hoi)

        tra_loi = (self.ask(cau_hoi) or "").strip()
        if not tra_loi:
            return TierResult(muc.key, 2, NOT_FOUND, "người chưa trả lời", question=cau_hoi)

        de_xuat = self._ghi_de_xuat(
            muc,
            body=tra_loi,
            source=f"người dùng cung cấp lúc {_now()}",
            topic=f"{muc.kind} {muc.key} — người dùng cung cấp",
        )
        return TierResult(
            muc.key, 2, FOUND, f"người cung cấp → {de_xuat.id}", proposal=de_xuat
        )

    @staticmethod
    def _cau_hoi(muc: RicItem) -> str:
        loai = {
            "register": "trang tài liệu mô tả thanh ghi",
            "pin": "sơ đồ chân cho",
            "parameter": "giá trị tham số",
            "constraint": "ràng buộc",
        }.get(muc.kind, "tài liệu về")
        cau = f"Cần {loai} {muc.key}"
        if muc.detail:
            cau += f" ({muc.detail})"
        return cau + "."

    # -- bậc 3 -------------------------------------------------------------

    def _bac3_tra_web(self, muc: RicItem) -> TierResult:
        if not self.allow_web:
            return TierResult(muc.key, 3, SKIPPED, "bậc web chưa bật (--web)")
        if self.llm is None:
            return TierResult(muc.key, 3, SKIPPED, "dự án chưa nối với mô hình nền")

        from eaa.ingest import SourceRejected, check_web_source
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        prompt = Prompt(
            system_instruction=(
                "Bạn tra cứu tài liệu kỹ thuật vi điều khiển. Chỉ trả lời khi "
                "CHẮC CHẮN và nêu được nguồn là trang chính thức của nhà sản "
                "xuất. Không chắc thì đặt found=false — một giá trị thanh ghi "
                "sai còn tệ hơn không có giá trị nào, vì nó sẽ đi qua mọi cổng "
                "kiểm chứng phía sau. TUYỆT ĐỐI không suy đoán giá trị bit."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Cần: {self._cau_hoi(muc)}\n\n"
                    f"Trả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                    f"```json\n{_JSON_CHUNK}\n```",
                    budget=2000,
                    required=True,
                )
            ],
            module=f"tra cứu {muc.key}",
            budget=2800,
        )

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            return TierResult(muc.key, 3, NOT_FOUND, f"lỗi tra cứu: {exc}")

        du_lieu = _boc_json(van_ban)
        if not du_lieu or not du_lieu.get("found"):
            return TierResult(muc.key, 3, NOT_FOUND, "mô hình nói không chắc")

        nguon = str(du_lieu.get("source", "")).strip()
        if not nguon:
            return TierResult(
                muc.key, 3, NOT_FOUND, "kết quả không kèm nguồn nên bị bỏ"
            )
        try:
            check_web_source(nguon)
        except SourceRejected as exc:
            return TierResult(muc.key, 3, NOT_FOUND, f"nguồn ngoài danh sách: {exc}")

        de_xuat = self._ghi_de_xuat(
            muc,
            body=str(du_lieu.get("body", "")),
            source=nguon,
            topic=str(du_lieu.get("topic", f"{muc.key} — tra cứu web")),
            registers=tuple(str(r) for r in (du_lieu.get("registers") or [muc.key])),
        )
        return TierResult(muc.key, 3, FOUND, f"{nguon} → {de_xuat.id}", proposal=de_xuat)

    # -- ghi đề xuất -------------------------------------------------------

    def _ghi_de_xuat(
        self,
        muc: RicItem,
        *,
        body: str,
        source: str,
        topic: str,
        registers: tuple[str, ...] = (),
    ) -> Any:
        """Ghi thứ tìm được thành chunk ĐỀ XUẤT — chờ G2, không vào kho ngay."""
        import hashlib

        from eaa.ingest import ProposedChunk

        thu_muc = Path(self.datasheets_dir or getattr(self.kb.datasheets, "directory", "."))
        thu_muc.mkdir(parents=True, exist_ok=True)

        bam = hashlib.sha256(f"{source}|{body}".encode("utf-8")).hexdigest()
        ma = f"gs-{bam[:8]}"
        de_xuat = ProposedChunk(
            id=ma,
            device=str(getattr(self.kb.hardware, "mcu", {}).get("part", "")),
            peripheral=self._ngoai_vi(muc),
            registers=registers or (muc.key,),
            topic=topic,
            source=source,
            source_hash="sha256:" + bam,
            body=body,
            confidence="medium",
            note=(
                "Tìm được bằng bậc thang P7 bước 3. Là ĐỀ XUẤT — phải đối chiếu "
                "với tài liệu gốc trước khi duyệt tại G2."
            ),
        )
        (thu_muc / f"{ma}.md").write_text(de_xuat.to_markdown(), encoding="utf-8")
        return de_xuat

    def _ngoai_vi(self, muc: RicItem) -> str:
        """Ngoại vi của mục, tra ngược từ đồ thị tri thức.

        Không tra được thì để TRỐNG, và người điền lúc duyệt G2. Đoán một cái
        tên ngoại vi ở đây là đưa một dữ kiện bịa vào kho tri thức qua cửa sau
        — đúng thứ mà cả vòng RIC dựng ra để chặn.
        """
        if self.graph is None:
            return ""
        for ngoai_vi in getattr(self.graph, "peripherals", lambda: [])():
            if muc.key.upper() in {r.upper() for r in getattr(ngoai_vi, "registers", ())}:
                return str(getattr(ngoai_vi, "id", ""))
        return ""


def _boc_json(van_ban: str) -> dict[str, Any]:
    khop = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", van_ban, re.DOTALL)
    tho = khop.group(1) if khop else van_ban[van_ban.find("{") : van_ban.rfind("}") + 1]
    if not tho.strip():
        return {}
    try:
        du_lieu = json.loads(tho)
    except json.JSONDecodeError:
        return {}
    return du_lieu if isinstance(du_lieu, dict) else {}
