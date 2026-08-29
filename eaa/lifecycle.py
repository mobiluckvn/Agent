"""Vòng đời tri thức — thay thế bản ghi và lập tập lỗi thời.

EAA-AIS-05 §8.1 (append-only + supersede), §8.2 (mâu thuẫn thì người phân xử),
§8.3 (tập lỗi thời), quy trình P9; FR-KLC-01/02/03.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-13.

Câu hỏi module này trả lời: **thay một mẩu tri thức thì mã cũ dựa trên nó ra
sao?** Không có câu trả lời, hệ thống mắc đúng bệnh mà nó sinh ra để chữa —
một trích đoạn tài liệu bị phát hiện sai, được sửa, nhưng ba module đã sinh
dựa trên bản sai vẫn nằm trong ``main`` và vẫn được coi là đã kiểm chứng.

Truy vấn ngược đi theo BA đường, rồi hợp lại (AIS §8.3 nêu hai đường đầu;
đường thứ ba đến từ NFR-07 và bịt một khe hở thật):

1.  **Đồ thị tri thức** — module dùng ngoại vi nào, ngoại vi ấy cấu hình bằng
    thanh ghi nào, thanh ghi ấy được tài liệu hóa ở chunk nào.
2.  **Trích dẫn trong mã** — quét ``// ref: <mã chunk>`` trong cây firmware.
    Bắt được cả module trích dẫn một chunk mà đồ thị không nối tới, chẳng hạn
    khi khai báo ``uses`` bị thiếu.
3.  **Dấu vết trong commit** — trường ``chunk-ids`` của commit đã sinh ra
    module. Bắt được trường hợp ngược lại: chunk ĐÃ được nạp vào prompt và ảnh
    hưởng tới mã, nhưng mã sinh ra không trích dẫn nó ở đâu cả.

Ba đường bắt ba loại lệ khác nhau, nên hợp của chúng mới là tập lỗi thời đúng.
Lấy một đường thôi thì luôn có một lối cho mã cũ ở lại mà không ai hỏi tới.

**Không xóa bao giờ.** Bản bị thay chuyển trạng thái ``deprecated`` kèm lý do,
NỘI DUNG giữ nguyên từng byte. Lịch sử truy vết là thứ Chương 3 cần, và nó chỉ
có giá trị khi không ai được phép viết lại.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from eaa.gates import APPROVED, GateDecision
from eaa.kb import ACTIVE, DEPRECATED, Chunk, DatasheetStore, KbError

__all__ = [
    "LifecycleError",
    "SupersedeNotAuthorized",
    "StaleEntry",
    "StaleSet",
    "KnowledgeLifecycle",
    "KNOWLEDGE_GATE",
    "STALE_STATUS",
]

#: Gate duyệt thay đổi kho tri thức — G2.
KNOWLEDGE_GATE = "G2"

#: Trạng thái module bị hạ tin cậy, buộc chạy lại chuỗi kiểm chứng.
STALE_STATUS = "stale"

_REF = re.compile(r"//\s*ref:\s*([^\s,;]+)")
_FRONTMATTER = re.compile(r"\A(---\s*\n)(.*?)(\n---\s*\n)(.*)\Z", re.DOTALL)
_CHUNK_IDS_TRAILER = re.compile(r"^chunk-ids:\s*(.+)$", re.MULTILINE)


class LifecycleError(Exception):
    """Thao tác vòng đời tri thức không hợp lệ."""


class SupersedeNotAuthorized(LifecycleError):
    """Thay thế tri thức mà chưa có phê duyệt của người tại gate tri thức."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class StaleEntry:
    """Một module bị ảnh hưởng bởi thay đổi tri thức."""

    module_id: str
    previous_status: str
    #: Lý do đi kèm bằng chứng: đường nào trong ba đường đã tìm ra nó.
    evidence: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.module_id} (đang ở {self.previous_status})"


@dataclass
class StaleSet:
    """Tập module phải xem lại sau khi một mẩu tri thức bị thay."""

    trigger: str
    reason: str
    entries: list[StaleEntry] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    @property
    def module_ids(self) -> list[str]:
        return sorted({e.module_id for e in self.entries})

    def __bool__(self) -> bool:
        return bool(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def render(self) -> str:
        if not self.entries:
            return (
                f"Không module nào dựa trên {self.trigger} — không có gì phải "
                "kiểm chứng lại."
            )
        dong = [
            f"Tập lỗi thời do thay đổi {self.trigger}: {len(self.entries)} module",
            f"Lý do: {self.reason}",
            "",
        ]
        for e in sorted(self.entries, key=lambda x: x.module_id):
            dong.append(f"  • {e}")
            for bc in e.evidence:
                dong.append(f"      {bc}")
        dong.append("")
        dong.append(
            "Các module trên bị hạ tin cậy và phải chạy lại chuỗi kiểm chứng. "
            "Module nào không đạt thì mở vòng sinh lại với tri thức mới (AIS §8.3)."
        )
        return "\n".join(dong)


class KnowledgeLifecycle:
    """Thi hành vòng đời của kho tri thức cho một dự án."""

    def __init__(
        self,
        *,
        datasheets: DatasheetStore,
        graph: Any = None,
        state_store: Any = None,
        firmware_dir: str | Path | None = None,
        repo: Any = None,
        ledger: Any = None,
    ) -> None:
        self.datasheets = datasheets
        self.graph = graph
        self.state_store = state_store
        self.firmware_dir = Path(firmware_dir) if firmware_dir else None
        self.repo = repo
        self.ledger = ledger

    # ----------------------------------------------------------------------
    # Truy vấn ngược — ba đường
    # ----------------------------------------------------------------------

    def modules_from_graph(self, chunk_id: str) -> dict[str, str]:
        """Đường 1 — quan hệ trong đồ thị tri thức."""
        if self.graph is None:
            return {}
        return {
            m: f"đồ thị: module dùng tài nguyên được tài liệu hóa bởi {chunk_id}"
            for m in self.graph.modules_documented_by(chunk_id)
        }

    def modules_from_citations(self, chunk_id: str) -> dict[str, str]:
        """Đường 2 — quét ``// ref:`` trong cây firmware.

        Bắt được module trích dẫn một chunk mà đồ thị không nối tới — thường
        là do khai báo ``uses`` của module bị thiếu, đúng rủi ro "đồ thị lệch
        thực tế" mà AIS §12 nêu.
        """
        if self.firmware_dir is None or not self.firmware_dir.is_dir():
            return {}

        ten_module = self._ten_module()
        ket_qua: dict[str, str] = {}
        for path in sorted(self.firmware_dir.rglob("*")):
            if not path.is_file() or path.suffix not in (".c", ".h", ".cpp"):
                continue
            try:
                noi_dung = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):  # pragma: no cover
                continue
            for so_dong, dong in enumerate(noi_dung.splitlines(), 1):
                for khop in _REF.finditer(dong):
                    if khop.group(1).rstrip(",;") != chunk_id:
                        continue
                    module = self._module_cua_tep(path, ten_module)
                    if module:
                        ket_qua.setdefault(
                            module,
                            f"trích dẫn trong mã: "
                            f"{path.relative_to(self.firmware_dir)}:{so_dong}",
                        )
        return ket_qua

    def modules_from_commits(self, chunk_id: str) -> dict[str, str]:
        """Đường 3 — trường ``chunk-ids`` trong commit đã sinh ra module.

        Bắt trường hợp ngược với đường 2: chunk ĐÃ vào prompt và ảnh hưởng tới
        mã, nhưng mã sinh ra không trích dẫn nó ở đâu. Nếu chỉ quét trích dẫn
        thì module ấy lọt lưới — và nó lọt lưới chính vì đã bỏ sót trích dẫn,
        tức là nó đáng ngờ hơn chứ không phải ít đáng ngờ hơn.
        """
        if self.repo is None:
            return {}
        try:
            nhat_ky = self.repo._git(
                "log", "--all", "--format=%H%x1f%B%x1e", check=False
            )
        except Exception:  # pragma: no cover - kho chưa có commit nào
            return {}

        ten_module = self._ten_module()
        ket_qua: dict[str, str] = {}
        for ban_ghi in nhat_ky.split("\x1e"):
            if "\x1f" not in ban_ghi:
                continue
            commit, thong_diep = ban_ghi.split("\x1f", 1)
            khop = _CHUNK_IDS_TRAILER.search(thong_diep)
            if not khop or chunk_id not in [
                c.strip() for c in khop.group(1).split(",")
            ]:
                continue
            for module in ten_module:
                if module in thong_diep:
                    ket_qua.setdefault(
                        module,
                        f"commit {commit.strip()[:8]} ghi chunk-ids có {chunk_id}",
                    )
        return ket_qua

    def stale_set(self, chunk_id: str, *, reason: str = "") -> StaleSet:
        """Hợp ba đường truy vấn ngược thành tập lỗi thời."""
        nguon: dict[str, list[str]] = {}
        for tim in (
            self.modules_from_graph,
            self.modules_from_citations,
            self.modules_from_commits,
        ):
            for module, bang_chung in tim(chunk_id).items():
                nguon.setdefault(module, []).append(bang_chung)

        trang_thai = self._trang_thai_module()
        return StaleSet(
            trigger=chunk_id,
            reason=reason or f"{chunk_id} bị thay thế",
            entries=[
                StaleEntry(
                    module_id=m,
                    previous_status=trang_thai.get(m, "(không có trong backlog)"),
                    evidence=tuple(sorted(bc)),
                )
                for m, bc in sorted(nguon.items())
            ],
        )

    # ----------------------------------------------------------------------
    # Thay thế tri thức
    # ----------------------------------------------------------------------

    def supersede(
        self,
        old_id: str,
        new_id: str,
        *,
        reason: str,
        decision: GateDecision | None,
    ) -> StaleSet:
        """Thay chunk cũ bằng chunk mới; trả về tập lỗi thời phát sinh.

        Đòi phê duyệt của người tại gate tri thức, giống như merge đòi giấy
        phép: thay một mẩu tri thức ảnh hưởng tới mọi mã đã sinh dựa trên nó,
        nên nó không thể là một thao tác tự động (AIS §8.1, quy trình P9).
        """
        self._kiem_phe_duyet(decision, f"thay thế {old_id} bằng {new_id}")

        cu = self.datasheets.get(old_id, include_inactive=True)
        moi = self.datasheets.get(new_id, include_inactive=True)

        if cu.id == moi.id:
            raise LifecycleError("Chunk không thể tự thay thế chính nó")
        if cu.status == DEPRECATED:
            raise LifecycleError(
                f"{old_id} đã ở trạng thái deprecated — không thay thế hai lần. "
                f"Bản đang thay nó: {cu.superseded_by or '(không ghi)'}"
            )

        tap_loi_thoi = self.stale_set(
            old_id, reason=f"{old_id} bị thay bởi {new_id}: {reason}"
        )

        self._ghi_frontmatter(
            moi.path,
            {"status": ACTIVE, "supersedes": old_id},
        )
        self._ghi_frontmatter(
            cu.path,
            {
                "status": DEPRECATED,
                "superseded_by": new_id,
                "deprecated_reason": reason,
                "deprecated_at": _now(),
                "deprecated_by": decision.actor if decision else "",
            },
        )
        self.datasheets.reload()

        if self.ledger is not None:
            self.ledger.add(
                module=", ".join(tap_loi_thoi.module_ids) or "(chưa module nào)",
                category="hallucinated_register" if "sai" in reason.lower() else "other",
                description=f"Tri thức thay thế: {old_id} → {new_id}. {reason}",
                evidence=f"{len(tap_loi_thoi)} module vào tập lỗi thời",
                rule=f"Dùng {new_id} thay cho {old_id}: {reason}",
            )

        return tap_loi_thoi

    def deprecate(
        self, chunk_id: str, *, reason: str, decision: GateDecision | None
    ) -> StaleSet:
        """Hạ một chunk xuống deprecated mà không có bản thay thế.

        Dùng khi phát hiện trích đoạn sai và chưa có bản đúng. Mã dựa trên nó
        vẫn phải vào tập lỗi thời ngay — chờ có bản thay thế mới báo động thì
        khoảng thời gian ở giữa là khoảng mà mọi người tưởng mã vẫn đúng.
        """
        self._kiem_phe_duyet(decision, f"hạ cấp {chunk_id}")

        chunk = self.datasheets.get(chunk_id, include_inactive=True)
        if chunk.status == DEPRECATED:
            raise LifecycleError(f"{chunk_id} đã ở trạng thái deprecated")

        tap_loi_thoi = self.stale_set(chunk_id, reason=f"{chunk_id} bị hạ cấp: {reason}")

        self._ghi_frontmatter(
            chunk.path,
            {
                "status": DEPRECATED,
                "deprecated_reason": reason,
                "deprecated_at": _now(),
                "deprecated_by": decision.actor if decision else "",
            },
        )
        self.datasheets.reload()
        return tap_loi_thoi

    # ----------------------------------------------------------------------
    # Áp tập lỗi thời lên Project State
    # ----------------------------------------------------------------------

    def apply(self, stale: StaleSet) -> list[str]:
        """Hạ tin cậy các module trong tập lỗi thời, buộc chạy lại kiểm chứng.

        Cố ý KHÔNG tự mở vòng sinh lại: quyết định sinh lại hay sửa tay thuộc
        về kỹ sư. Việc của máy là bảo đảm không module nào lặng lẽ giữ nguyên
        nhãn "đã kiểm chứng" khi cơ sở của nhãn ấy đã đổi.
        """
        if self.state_store is None or not stale.entries:
            return []

        da_doi: list[str] = []
        with self.state_store.with_lock():
            state = self.state_store.load()
            for e in stale.entries:
                muc = state.module(e.module_id)
                if muc is None or muc.status == STALE_STATUS:
                    continue
                muc.status = STALE_STATUS
                muc.retries = 0
                da_doi.append(e.module_id)
            if da_doi:
                self.state_store.save(state)
        return da_doi

    # ----------------------------------------------------------------------
    # Trợ giúp
    # ----------------------------------------------------------------------

    @staticmethod
    def _kiem_phe_duyet(decision: GateDecision | None, viec: str) -> None:
        if decision is None:
            raise SupersedeNotAuthorized(
                f"Không thể {viec} khi chưa có phê duyệt tại {KNOWLEDGE_GATE}. "
                "Thay đổi kho tri thức ảnh hưởng tới mọi mã đã sinh dựa trên nó "
                "nên không phải thao tác tự động (AIS §8.1)."
            )
        if decision.gate_id != KNOWLEDGE_GATE:
            raise SupersedeNotAuthorized(
                f"Thay đổi kho tri thức cần quyết định tại {KNOWLEDGE_GATE}, nhận "
                f"quyết định của {decision.gate_id!r}."
            )
        if decision.decision != APPROVED:
            raise SupersedeNotAuthorized(
                f"{KNOWLEDGE_GATE} ở trạng thái {decision.decision!r} — chưa được "
                f"phép {viec}."
            )

    def _ten_module(self) -> list[str]:
        if self.state_store is None or not self.state_store.exists():
            return []
        return [m.id for m in self.state_store.load().backlog]

    def _trang_thai_module(self) -> dict[str, str]:
        if self.state_store is None or not self.state_store.exists():
            return {}
        return {m.id: m.status for m in self.state_store.load().backlog}

    @staticmethod
    def _module_cua_tep(path: Path, ten_module: Sequence[str]) -> str | None:
        """Suy module từ đường dẫn tệp.

        Quy ước: tệp của module mang tên module. Khớp theo tên dài trước để
        ``drv_bus`` không nuốt mất ``drv_bus_sensor``.
        """
        chuoi = str(path)
        for module in sorted(ten_module, key=len, reverse=True):
            if module and module in chuoi:
                return module
        return None

    @staticmethod
    def _ghi_frontmatter(path: Path, cap_nhat: dict[str, Any]) -> None:
        """Cập nhật frontmatter, giữ NỘI DUNG nguyên từng byte.

        FR-RAG-01 nói chunk sau khi duyệt là bất biến. Bất biến ở đây là bất
        biến của NỘI DUNG — trạng thái vòng đời thì phải chuyển được, nếu không
        thì không có cách nào đánh dấu một trích đoạn đã sai. Hàm này thi hành
        đúng ranh giới đó: chỉ chạm phần siêu dữ liệu.
        """
        van_ban = path.read_text(encoding="utf-8")
        khop = _FRONTMATTER.match(van_ban)
        if not khop:
            raise KbError(f"{path}: không có frontmatter để cập nhật")

        try:
            meta = yaml.safe_load(khop.group(2)) or {}
        except yaml.YAMLError as exc:
            raise KbError(f"{path}: frontmatter hỏng — {exc}") from exc

        meta.update(cap_nhat)
        moi = (
            khop.group(1)
            + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip("\n")
            + khop.group(3)
            + khop.group(4)
        )
        path.write_text(moi, encoding="utf-8")
