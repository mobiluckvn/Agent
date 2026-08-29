"""Knowledge Base — bộ nạp các kho tri thức của một dự án.

EAA-SAD-02 §3 (Knowledge Base: 5 kho), EAA-SDD-03 §3 (lược đồ dữ liệu),
EAA-AIS-05 §4 (vòng đời Datasheet Store) và §8.1 (append-only + supersede).
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-03 về việc module này không có trong
cây thư mục gốc của SDD.

Ranh giới trách nhiệm — module này chỉ **ĐỌC KHO**, không nén và không ghép
prompt. Bảy kỹ thuật nén K1–K7 thuộc ``composer.py``. Tách như vậy vì hai việc
hỏng theo hai kiểu khác nhau: đọc sai kho là sai dữ liệu, nén sai là mất thông
tin quyết định — trộn chúng lại thì lỗi nào cũng khó truy.

Bất biến của module:

* **Truy vấn mặc định chỉ thấy bản ``active``** (FR-KLC-01). Chunk còn ở trạng
  thái ``proposed`` — tức chưa qua Gate G2 — không bao giờ lọt vào một truy
  xuất bình thường. Đây chính là cơ chế khiến trích xuất sai của máy "chết ở
  cửa gate" thay vì nhiễm vào kho (AIS §6.1).
* **Không ghi đè vật lý.** Kho chỉ được đọc ở đây; việc thêm bản ghi mới kèm
  con trỏ ``supersedes`` thuộc tầng vòng đời tri thức (Sprint 3).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

__all__ = [
    "KbError",
    "Constraints",
    "Chunk",
    "DatasheetStore",
    "PromptTemplate",
    "PromptLibrary",
    "HardwareProfile",
    "KnowledgeBase",
    "ACTIVE",
    "PROPOSED",
    "DEPRECATED",
]

PROPOSED = "proposed"
ACTIVE = "approved"
DEPRECATED = "deprecated"

_CHUNK_STATUSES = frozenset({PROPOSED, ACTIVE, DEPRECATED})

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


class KbError(Exception):
    """Kho tri thức thiếu, sai lược đồ hoặc mâu thuẫn nội tại."""


def _read_yaml(path: Path, nhan: str) -> dict[str, Any]:
    if not path.is_file():
        raise KbError(f"Thiếu {nhan}: {path}")
    try:
        du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise KbError(f"{path}: YAML không hợp lệ — {exc}") from exc
    if not isinstance(du_lieu, dict):
        raise KbError(f"{path}: nội dung phải là ánh xạ khóa–giá trị")
    return du_lieu


def content_hash(path: Path) -> str:
    """Băm BYTE của tệp, không băm cấu trúc đã phân tích.

    Câu hỏi cần trả lời là "mã này sinh ra dưới đúng văn bản nào" — nên một
    thay đổi chỉ ở chú thích, thứ làm người đọc hiểu khác đi, vẫn phải đổi băm
    (NFR-07).
    """
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Kho 1 — Hard Constraints Spec
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constraints:
    """Ràng buộc cứng của dự án — sản phẩm công đoạn A1, nạp vào 100% prompt."""

    path: Path
    version: int
    platform: str
    raw: dict[str, Any]
    content_version: str

    @property
    def limits(self) -> dict[str, Any]:
        return dict(self.raw.get("limits") or {})

    @property
    def forbidden(self) -> tuple[str, ...]:
        return tuple(str(x) for x in (self.raw.get("forbidden") or []))

    @property
    def style(self) -> dict[str, Any]:
        return dict(self.raw.get("style") or {})

    @property
    def acceptance(self) -> dict[str, Any]:
        return dict(self.raw.get("acceptance") or {})

    def platform_params(self) -> dict[str, Any]:
        """Tham số truyền xuống Platform Pack khi dựng lời gọi công cụ.

        Engine chuyển tiếp nguyên vẹn mọi khóa vô hướng ở mức trên cùng và mọi
        khóa trong ``limits``, KHÔNG diễn giải khóa nào. Nhờ thế pack tự quyết
        định nó cần chỗ giữ tên gì mà engine không phải biết tên đó nghĩa là gì
        — đây là điều kiện để engine sạch phần cứng (FR-PLT-01).
        """
        params: dict[str, Any] = {
            k: v
            for k, v in self.raw.items()
            if isinstance(v, (str, int, float, bool))
        }
        params.update(
            {k: v for k, v in self.limits.items() if isinstance(v, (str, int, float, bool))}
        )
        return params

    @classmethod
    def load(cls, path: str | Path) -> "Constraints":
        path = Path(path)
        raw = _read_yaml(path, "constraints.yaml (Hard Constraints Spec, công đoạn A1)")

        platform = raw.get("platform")
        if not platform:
            raise KbError(
                f"{path}: thiếu trường 'platform' — dự án phải chỉ rõ dùng "
                "Platform Pack nào; engine không đoán."
            )

        version = raw.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool):
            raise KbError(f"{path}: 'version' phải là số nguyên, nhận {version!r}")

        return cls(
            path=path,
            version=version,
            platform=str(platform),
            raw=raw,
            content_version=content_hash(path),
        )


# --------------------------------------------------------------------------
# Kho 2 — Datasheet Store (chunk RAG)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    """Một trích đoạn tài liệu đã chưng cất thành bảng thanh ghi–bit (K2)."""

    id: str
    path: Path
    device: str
    peripheral: str
    registers: tuple[str, ...]
    topic: str
    source: str
    status: str
    body: str
    source_hash: str = ""
    supersedes: str | None = None
    superseded_by: str | None = None
    note: str = ""

    @property
    def is_active(self) -> bool:
        """Chỉ chunk đã duyệt G2 và chưa bị thay thế mới được truy xuất."""
        return self.status == ACTIVE and self.superseded_by is None

    @property
    def citation(self) -> str:
        """Chuỗi trích dẫn bắt buộc trong mã cấu hình thanh ghi (FR-RAG-02)."""
        nguon = f", {self.source}" if self.source else ""
        return f"// ref: {self.id}{nguon}"

    def matches_register(self, register: str) -> bool:
        """Khớp CHÍNH XÁC tên thanh ghi, không phân biệt hoa thường.

        Cố ý không khớp một phần hay khớp tiền tố: hai thanh ghi của cùng một
        ngoại vi thường chỉ khác nhau một ký tự cuối mà điều khiển hai thứ khác
        hẳn nhau. Một truy xuất "gần đúng" ở đây đẻ ra ảo giác CÓ TRÍCH DẪN —
        loại nguy hiểm nhất, vì mã sai trông như có nguồn gốc (AIS §12).
        """
        muc_tieu = register.strip().upper()
        return any(r.upper() == muc_tieu for r in self.registers)


class DatasheetStore:
    """Kho chunk RAG của một dự án — thư mục ``datasheets/``."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._chunks: dict[str, Chunk] = {}
        self._loaded = False

    def _ensure(self) -> None:
        if self._loaded:
            return
        self._chunks = {}
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.md")):
                chunk = self._parse(path)
                if chunk.id in self._chunks:
                    khac = self._chunks[chunk.id].path
                    raise KbError(
                        f"Trùng id chunk {chunk.id!r} giữa {khac.name} và "
                        f"{path.name} — id là khóa truy vết, không được trùng."
                    )
                self._chunks[chunk.id] = chunk
        self._validate_supersede_chain()
        self._loaded = True

    def reload(self) -> None:
        self._loaded = False
        self._ensure()

    @staticmethod
    def _parse(path: Path) -> Chunk:
        text = path.read_text(encoding="utf-8")
        khop = _FRONTMATTER.match(text)
        if not khop:
            raise KbError(
                f"{path}: thiếu frontmatter YAML giữa hai dòng '---'. "
                "Metadata là khóa truy xuất và truy vết (AIS §4.1 bước 3)."
            )

        try:
            meta = yaml.safe_load(khop.group(1)) or {}
        except yaml.YAMLError as exc:
            raise KbError(f"{path}: frontmatter không phải YAML hợp lệ — {exc}") from exc
        if not isinstance(meta, dict):
            raise KbError(f"{path}: frontmatter phải là ánh xạ khóa–giá trị")

        for truong in ("id", "device", "peripheral", "status"):
            if not meta.get(truong):
                raise KbError(f"{path}: frontmatter thiếu trường bắt buộc {truong!r}")

        status = str(meta["status"])
        if status not in _CHUNK_STATUSES:
            raise KbError(
                f"{path}: status={status!r} không hợp lệ "
                f"(cho phép: {sorted(_CHUNK_STATUSES)})"
            )

        registers = meta.get("registers") or []
        if not isinstance(registers, list):
            raise KbError(f"{path}: 'registers' phải là danh sách")

        body = khop.group(2).strip()
        if not body:
            raise KbError(f"{path}: chunk rỗng — không có nội dung để trích dẫn")

        return Chunk(
            id=str(meta["id"]),
            path=path,
            device=str(meta["device"]),
            peripheral=str(meta["peripheral"]),
            registers=tuple(str(r) for r in registers),
            topic=str(meta.get("topic", "")),
            source=str(meta.get("source", "")),
            status=status,
            body=body,
            source_hash=str(meta.get("source_hash", "")),
            supersedes=meta.get("supersedes"),
            superseded_by=meta.get("superseded_by"),
            note=str(meta.get("note", "")),
        )

    def _validate_supersede_chain(self) -> None:
        """Con trỏ thay thế phải trỏ tới chunk có thật và phải nhất quán hai chiều.

        Một chuỗi supersede đứt đoạn làm hỏng đúng thứ nó sinh ra để bảo vệ:
        khả năng lập lại tập lỗi thời (stale set) khi tri thức bị thay (AIS §8.3).
        """
        for chunk in self._chunks.values():
            for truong, dich in (
                ("supersedes", chunk.supersedes),
                ("superseded_by", chunk.superseded_by),
            ):
                if dich and dich not in self._chunks:
                    raise KbError(
                        f"{chunk.path.name}: {truong} trỏ tới chunk không tồn tại: {dich!r}"
                    )

            if chunk.supersedes:
                cu = self._chunks[chunk.supersedes]
                if cu.status != DEPRECATED:
                    raise KbError(
                        f"Chunk {chunk.id!r} thay thế {cu.id!r} nhưng {cu.id!r} vẫn ở "
                        f"trạng thái {cu.status!r} — bản bị thay phải là 'deprecated' "
                        "(AIS §8.1). Không xóa, chỉ hạ trạng thái."
                    )

    # -- truy vấn ----------------------------------------------------------

    def all(self) -> list[Chunk]:
        """Toàn bộ chunk kể cả proposed và deprecated — dùng để đối chứng lịch sử."""
        self._ensure()
        return list(self._chunks.values())

    def active(self) -> list[Chunk]:
        """Chunk được phép đưa vào prompt: đã duyệt G2 và chưa bị thay thế."""
        return [c for c in self.all() if c.is_active]

    def get(self, chunk_id: str, *, include_inactive: bool = False) -> Chunk:
        self._ensure()
        try:
            chunk = self._chunks[chunk_id]
        except KeyError:
            raise KbError(f"Không có chunk id {chunk_id!r} trong {self.directory}") from None
        if not include_inactive and not chunk.is_active:
            raise KbError(
                f"Chunk {chunk_id!r} đang ở trạng thái {chunk.status!r} — chỉ chunk "
                "đã duyệt G2 mới được truy xuất (chống nhiễm bẩn kho)."
            )
        return chunk

    def by_register(self, register: str, *, include_inactive: bool = False) -> list[Chunk]:
        nguon = self.all() if include_inactive else self.active()
        return [c for c in nguon if c.matches_register(register)]

    def by_registers(
        self, registers: Iterable[str], *, include_inactive: bool = False
    ) -> list[Chunk]:
        """Chunk khớp bất kỳ thanh ghi nào trong tập, giữ thứ tự ổn định."""
        thay: dict[str, Chunk] = {}
        for reg in registers:
            for chunk in self.by_register(reg, include_inactive=include_inactive):
                thay.setdefault(chunk.id, chunk)
        return list(thay.values())

    def by_peripheral(self, peripheral: str, *, include_inactive: bool = False) -> list[Chunk]:
        nguon = self.all() if include_inactive else self.active()
        muc_tieu = peripheral.strip().lower()
        return [c for c in nguon if c.peripheral.strip().lower() == muc_tieu]

    def registers(self) -> set[str]:
        """Mọi thanh ghi có tài liệu — dùng để lập RIC và bắt mục THIẾU."""
        return {r.upper() for c in self.active() for r in c.registers}


# --------------------------------------------------------------------------
# Kho 3 — Prompt Library
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    path: Path
    body: str
    description: str = ""
    #: ``pack`` (đặc thù nền tảng) hoặc ``project`` (riêng dự án).
    origin: str = "pack"


class PromptLibrary:
    """Thư viện mẫu prompt, xếp lớp: mẫu của dự án ghi đè mẫu của pack.

    Lớp lang như vậy để một dự án chỉnh được cách diễn đạt cho bài toán của nó
    mà không phải sửa pack — pack vẫn dùng lại được cho dự án khác (NFR-05).
    """

    def __init__(self, pack_dir: str | Path | None, project_dir: str | Path | None) -> None:
        self.pack_dir = Path(pack_dir) if pack_dir else None
        self.project_dir = Path(project_dir) if project_dir else None
        self._templates: dict[str, PromptTemplate] | None = None

    def _ensure(self) -> dict[str, PromptTemplate]:
        if self._templates is not None:
            return self._templates
        ket_qua: dict[str, PromptTemplate] = {}
        for thu_muc, nguon_goc in ((self.pack_dir, "pack"), (self.project_dir, "project")):
            if not thu_muc or not thu_muc.is_dir():
                continue
            for path in sorted(thu_muc.glob("*.md")):
                mau = self._parse(path, nguon_goc)
                ket_qua[mau.id] = mau  # dự án nạp sau nên ghi đè pack
        self._templates = ket_qua
        return ket_qua

    @staticmethod
    def _parse(path: Path, origin: str) -> PromptTemplate:
        text = path.read_text(encoding="utf-8")
        khop = _FRONTMATTER.match(text)
        if khop:
            meta = yaml.safe_load(khop.group(1)) or {}
            body = khop.group(2).strip()
        else:
            meta, body = {}, text.strip()
        return PromptTemplate(
            id=str(meta.get("id", path.stem)),
            path=path,
            body=body,
            description=str(meta.get("description", "")),
            origin=origin,
        )

    def all(self) -> list[PromptTemplate]:
        return list(self._ensure().values())

    def get(self, template_id: str) -> PromptTemplate:
        try:
            return self._ensure()[template_id]
        except KeyError:
            co = sorted(self._ensure())
            raise KbError(
                f"Không có mẫu prompt {template_id!r} (đang có: {co})"
            ) from None

    def has(self, template_id: str) -> bool:
        return template_id in self._ensure()


# --------------------------------------------------------------------------
# Kho 4 — Hardware Profile
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HardwareProfile:
    """Hồ sơ phần cứng — sản phẩm công đoạn B2, nguồn dựng Knowledge Graph."""

    path: Path
    version: int
    raw: dict[str, Any]
    content_version: str

    @property
    def mcu(self) -> dict[str, Any]:
        return dict(self.raw.get("mcu") or {})

    @property
    def peripherals(self) -> list[dict[str, Any]]:
        return list(self.raw.get("peripherals") or [])

    @property
    def components(self) -> list[dict[str, Any]]:
        return list(self.raw.get("components") or [])

    @property
    def pin_map(self) -> dict[str, Any]:
        return dict(self.raw.get("pin_map") or {})

    @property
    def power(self) -> dict[str, Any]:
        return dict(self.raw.get("power") or {})

    @property
    def mechanics(self) -> dict[str, Any]:
        return dict(self.raw.get("mechanics") or {})

    def peripheral(self, peripheral_id: str) -> dict[str, Any] | None:
        for ngoai_vi in self.peripherals:
            if str(ngoai_vi.get("id", "")).lower() == peripheral_id.lower():
                return dict(ngoai_vi)
        return None

    def registers_of(self, peripheral_id: str) -> tuple[str, ...]:
        """Thanh ghi cấu hình một ngoại vi — cạnh ``configured_by`` của đồ thị."""
        ngoai_vi = self.peripheral(peripheral_id)
        if not ngoai_vi:
            return ()
        return tuple(str(r) for r in (ngoai_vi.get("configured_by") or []))

    @classmethod
    def load(cls, path: str | Path) -> "HardwareProfile":
        path = Path(path)
        raw = _read_yaml(path, "hardware_profile.yaml (Hardware Profile, công đoạn B2)")

        ids = [str(p.get("id", "")) for p in (raw.get("peripherals") or [])]
        trung = {i for i in ids if ids.count(i) > 1}
        if trung:
            raise KbError(f"{path}: trùng id ngoại vi {sorted(trung)}")

        return cls(
            path=path,
            version=int(raw.get("version", 1)),
            raw=raw,
            content_version=content_hash(path),
        )


# --------------------------------------------------------------------------
# Gộp — Knowledge Base của một dự án
# --------------------------------------------------------------------------


@dataclass
class KnowledgeBase:
    """Toàn bộ kho tri thức của một dự án, nạp một lần dùng nhiều nơi.

    Error Ledger là kho thứ năm và ở trong ``eaa/ledger.py`` theo đúng cây thư
    mục EAA-SDD-03 §2; nó được gắn vào đây qua thuộc tính ``ledger``.
    """

    project_dir: Path
    constraints: Constraints
    hardware: HardwareProfile
    datasheets: DatasheetStore
    prompts: PromptLibrary
    ledger: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        project_dir: str | Path,
        *,
        pack_prompts_dir: str | Path | None = None,
    ) -> "KnowledgeBase":
        project_dir = Path(project_dir)
        if not project_dir.is_dir():
            raise KbError(f"Không có thư mục dự án: {project_dir}")

        return cls(
            project_dir=project_dir,
            constraints=Constraints.load(project_dir / "constraints.yaml"),
            hardware=HardwareProfile.load(project_dir / "hardware_profile.yaml"),
            datasheets=DatasheetStore(project_dir / "datasheets"),
            prompts=PromptLibrary(pack_prompts_dir, project_dir / "prompts"),
        )

    @property
    def platform(self) -> str:
        return self.constraints.platform
