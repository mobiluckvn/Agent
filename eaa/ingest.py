"""Tầng thu nhận đầu vào đa phương thức — mọi tri thức đi VÀO hệ thống.

EAA-AIS-05 §6 (bốn loại đầu vào, proposed facts, bộ nhớ mở rộng), §4.1 (đường
ống nạp liệu P1), quy trình P6; FR-ING-01/02/03/04; TC-22, TC-25.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-15.

Tầng này đứng TRƯỚC toàn bộ đường ống ngữ cảnh của ``composer.py``: đây là nơi
tri thức đi vào các kho, còn composer là nơi tri thức đi ra khỏi kho để vào
prompt.

**Nguyên tắc bất di bất dịch** (AIS §6.1): mọi thứ máy trích xuất chỉ là
PROPOSED FACTS — mang nhãn nguồn, số trang gốc và độ tin cậy, nằm NGOÀI bộ nhớ
hệ thống cho tới khi con người duyệt tại gate tương ứng. Nhờ vậy một lần trích
xuất sai — đọc nhầm ảnh, nhận dạng sai bảng trong PDF — không bao giờ nhiễm
thẳng vào kho tri thức; nó chết ở cửa gate.

Điều đó được thi hành ở đây bằng đúng một cơ chế: chunk sinh ra luôn mang
``status: proposed``, và ``DatasheetStore`` đã từ chối trả về bản chưa duyệt
trong mọi truy vấn thường (xem ``eaa/kb.py``). Không có cờ nào ở tầng này bật
thẳng một chunk lên ``approved``.

Ba kho mở rộng của AIS §6.3 nằm ở đây: **Source Registry** (fact này từ đâu
ra), **Media Store** (ảnh gốc để đối chiếu lại khi nghi ngờ) và **Assumption
Log** (giả định bất khả kháng, để chúng hiện diện tường minh thay vì trốn
trong mã).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

import yaml

from eaa.kb import PROPOSED

__all__ = [
    "IngestError",
    "SourceRejected",
    "InputKind",
    "classify",
    "SourceRecord",
    "SourceRegistry",
    "Assumption",
    "AssumptionLog",
    "MediaStore",
    "ProposedChunk",
    "ProposedMeasurement",
    "ScopeImageReader",
    "PdfIngestor",
    "WEB_WHITELIST",
    "check_web_source",
]


class InputKind:
    """Bốn loại đầu vào của AIS §6.1."""

    COMMAND = "command"     # lệnh / mô tả của người dùng
    PDF = "pdf"             # tài liệu kỹ thuật, app note, sơ đồ xuất PDF
    IMAGE = "image"         # sơ đồ vẽ tay, màn hiện sóng, ảnh linh kiện
    CODE = "code"           # firmware có sẵn, thư viện tham khảo
    UNKNOWN = "unknown"


#: Danh sách nguồn web cho phép — AIS §6.2 bậc 3, FR-GAP-02, TC-25.
#:
#: Chỉ trang chính thức của nhà sản xuất. Diễn đàn và blog bị loại không phải
#: vì luôn sai, mà vì một trích dẫn từ đó tạo ra thứ nguy hiểm nhất: ảo giác
#: CÓ NGUỒN. Mã sai kèm một đường dẫn trông đàng hoàng thì khó bị nghi ngờ hơn
#: hẳn mã sai không có gì.
WEB_WHITELIST: tuple[str, ...] = (
    "microchip.com",
    "atmel.com",
    "invensense.tdk.com",
    "tdk-invensense.com",
    "allegromicro.com",
    "st.com",
    "nxp.com",
    "ti.com",
    "infineon.com",
    "espressif.com",
    "raspberrypi.com",
    "arm.com",
)

_BANG_THANH_GHI = re.compile(
    r"(?P<reg>[A-Z][A-Z0-9_]{2,})\s*(?:=|:|\s)\s*(?P<val>0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+)"
)
_TEN_THANH_GHI = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


class IngestError(Exception):
    """Không thu nhận được đầu vào."""


class SourceRejected(IngestError):
    """Nguồn nằm ngoài danh sách cho phép — TC-25."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for khoi in iter(lambda: f.read(65536), b""):
            h.update(khoi)
    return "sha256:" + h.hexdigest()


def classify(path: str | Path) -> str:
    """Phân loại đầu vào theo đuôi tệp — FR-ING-01."""
    duoi = Path(path).suffix.lower()
    if duoi == ".pdf":
        return InputKind.PDF
    if duoi in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"):
        return InputKind.IMAGE
    if duoi in (".c", ".h", ".cpp", ".hpp", ".cc", ".s", ".asm", ".ino"):
        return InputKind.CODE
    if duoi in (".txt", ".md", ""):
        return InputKind.COMMAND
    return InputKind.UNKNOWN


def check_web_source(url: str) -> str:
    """Kiểm nguồn web có nằm trong danh sách cho phép không — TC-25.

    So theo TÊN MIỀN có hậu tố khớp, không so theo chuỗi con: ``microchip.com``
    không được khớp với ``microchip.com.kho-tai-lieu-lau.net``. Đây là kiểu
    kiểm tra mà làm cẩu thả thì tệ hơn không làm — nó cấp cho một nguồn giả
    mạo đúng cái vẻ chính thống mà danh sách sinh ra để bảo vệ.
    """
    phan_tich = urlparse(url if "//" in url else f"https://{url}")
    host = (phan_tich.hostname or "").lower().rstrip(".")
    if not host:
        raise SourceRejected(f"Không đọc được tên miền từ {url!r}")

    for cho_phep in WEB_WHITELIST:
        if host == cho_phep or host.endswith("." + cho_phep):
            return host

    raise SourceRejected(
        f"Nguồn {host!r} nằm ngoài danh sách cho phép. Chỉ nhận trang chính thức "
        f"của nhà sản xuất ({', '.join(WEB_WHITELIST[:4])}…). Một trích dẫn từ "
        "diễn đàn hay blog tạo ra ảo giác CÓ NGUỒN — nguy hiểm hơn hẳn mã sai "
        "không có gì (FR-GAP-02, AIS §12)."
    )


# --------------------------------------------------------------------------
# Source Registry — "fact này từ đâu ra?" trả lời trong một lần tra
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRecord:
    id: str
    kind: str
    origin: str
    content_hash: str
    registered_at: str
    pages: str = ""
    note: str = ""
    #: Mã các chunk đề xuất sinh ra từ nguồn này.
    produced: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "origin": self.origin,
            "content_hash": self.content_hash,
            "registered_at": self.registered_at,
            "pages": self.pages,
            "note": self.note,
            "produced": list(self.produced),
        }


class SourceRegistry:
    """Danh mục mọi tài liệu đã nạp — AIS §6.3, append-only."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def register(
        self,
        *,
        origin: str,
        kind: str,
        content_hash: str,
        pages: str = "",
        note: str = "",
        produced: Sequence[str] = (),
        source_id: str | None = None,
    ) -> SourceRecord:
        ban_ghi = SourceRecord(
            id=source_id or f"src-{len(self.all()) + 1:04d}",
            kind=kind,
            origin=origin,
            content_hash=content_hash,
            registered_at=_now(),
            pages=pages,
            note=note,
            produced=tuple(produced),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ban_ghi.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return ban_ghi

    def all(self) -> list[SourceRecord]:
        if not self.path.is_file():
            return []
        ket_qua: list[SourceRecord] = []
        for so_dong, dong in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                d = json.loads(dong)
            except json.JSONDecodeError as exc:
                raise IngestError(f"{self.path}:{so_dong}: JSON hỏng — {exc}") from exc
            ket_qua.append(
                SourceRecord(
                    id=d["id"],
                    kind=d.get("kind", InputKind.UNKNOWN),
                    origin=d.get("origin", ""),
                    content_hash=d.get("content_hash", ""),
                    registered_at=d.get("registered_at", ""),
                    pages=d.get("pages", ""),
                    note=d.get("note", ""),
                    produced=tuple(d.get("produced", ())),
                )
            )
        return ket_qua

    def source_of(self, chunk_id: str) -> SourceRecord | None:
        """Trả lời "chunk này từ tài liệu nào" trong một lần tra."""
        for ban_ghi in self.all():
            if chunk_id in ban_ghi.produced:
                return ban_ghi
        return None

    def by_hash(self, content_hash: str) -> list[SourceRecord]:
        return [r for r in self.all() if r.content_hash == content_hash]


# --------------------------------------------------------------------------
# Assumption Log — giả định hiện diện tường minh thay vì trốn trong mã
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Assumption:
    id: str
    subject: str
    value: str
    rationale: str
    status: str          # proposed · approved · replaced_by
    created_at: str
    #: Trên bản ghi đánh dấu: giả định NÀO đã bị thay.
    replaces: str = ""
    #: Trên bản ghi đánh dấu: giả định mới thay thế nó.
    replaced_by: str = ""
    approved_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class AssumptionLog:
    """Sổ giả định — AIS §6.3 và §8.1.

    Vòng đời: ``proposed`` → ``approved`` → ``replaced_by`` khi có SỐ ĐO THẬT
    thay thế. Tri thức thực chứng luôn thắng giả định; sổ này bảo đảm việc thay
    thế ấy có chỗ để xảy ra, thay vì một con số ước lượng nằm mãi trong mã mà
    không ai nhớ nó từng là ước lượng.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def add(
        self, *, subject: str, value: str, rationale: str, status: str = "proposed"
    ) -> Assumption:
        gia_dinh = Assumption(
            id=f"asm-{len(self.all()) + 1:04d}",
            subject=subject,
            value=str(value),
            rationale=rationale,
            status=status,
            created_at=_now(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(gia_dinh.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return gia_dinh

    def replace_with_measurement(self, assumption_id: str, measurement: str) -> Assumption:
        """Thay một giả định bằng số đo thật — append, không sửa dòng cũ."""
        cu = self.get(assumption_id)
        moi = self.add(
            subject=cu.subject,
            value=measurement,
            rationale=f"Số đo thật thay giả định {assumption_id}",
            status="approved",
        )
        self.path.open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "id": f"{assumption_id}-replaced",
                    "subject": cu.subject,
                    "value": cu.value,
                    "rationale": cu.rationale,
                    "status": "replaced_by",
                    "created_at": _now(),
                    "replaces": assumption_id,
                    "replaced_by": moi.id,
                    "approved_by": "",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return moi

    def all(self) -> list[Assumption]:
        if not self.path.is_file():
            return []
        ket_qua = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            if dong.strip():
                ket_qua.append(Assumption(**json.loads(dong)))
        return ket_qua

    def get(self, assumption_id: str) -> Assumption:
        for a in self.all():
            if a.id == assumption_id:
                return a
        raise IngestError(f"Không có giả định {assumption_id!r}")

    def active(self) -> list[Assumption]:
        """Giả định còn hiệu lực.

        Loại theo trường ``replaces`` của bản ghi đánh dấu — tức loại bản CŨ.
        Loại theo ``replaced_by`` là loại nhầm bản mới, và sổ sẽ im lặng trả về
        đúng con số vừa bị số đo thật phủ nhận.
        """
        da_bi_thay = {a.replaces for a in self.all() if a.replaces}
        return [
            a
            for a in self.all()
            if a.status != "replaced_by" and a.id not in da_bi_thay
        ]


# --------------------------------------------------------------------------
# Media Store — giữ ảnh gốc để đối chiếu lại khi nghi ngờ
# --------------------------------------------------------------------------


class MediaStore:
    """Kho ảnh gốc kèm các fact đã trích — AIS §6.3.

    Giữ ảnh gốc là điều kiện để câu "máy đọc nhầm ảnh" kiểm chứng lại được.
    Không giữ thì một số đo sai từ ảnh trở thành lời khai không đối chứng.
    """

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)

    def store(self, path: str | Path, *, facts: dict[str, Any] | None = None) -> Path:
        path = Path(path)
        if not path.is_file():
            raise IngestError(f"Không tìm thấy tệp ảnh: {path}")

        self.directory.mkdir(parents=True, exist_ok=True)
        bam = _hash_file(path)
        dich = self.directory / f"{bam[7:19]}{path.suffix.lower()}"
        if not dich.exists():
            dich.write_bytes(path.read_bytes())

        (dich.with_suffix(dich.suffix + ".facts.json")).write_text(
            json.dumps(
                {
                    "origin": str(path),
                    "content_hash": bam,
                    "stored_at": _now(),
                    "facts": facts or {},
                    "status": PROPOSED,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return dich


# --------------------------------------------------------------------------
# Ảnh màn hiện sóng → số đo đề xuất — FR-ING-03, TC-23
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedMeasurement:
    """Một số đo Agent đọc được từ ảnh — ĐỀ XUẤT, chưa phải bản ghi.

    Ba trường quyết định tệp này có ích hay có hại:

    * ``uncertainty`` — sai số ĐỌC ẢNH, khai bằng chính đơn vị của số đo. Một
      con số đọc từ màn hiện sóng không bao giờ chính xác bằng con số máy đo
      gửi qua đường truyền: nó phụ thuộc vào việc con trỏ đặt ở đâu và lưới
      chia bao nhiêu ô. Bỏ trường này thì số đọc từ ảnh trông y hệt số đo được.
    * ``reading`` — Agent thấy GÌ trên ảnh để ra con số ấy (mấy ô, mỗi ô bao
      nhiêu). Đây là thứ cho phép người kiểm lại mà không cần tin.
    * ``status`` — luôn là ``proposed``. Không có đường nào để một số đo từ ảnh
      tự vào Measurement Records.
    """

    key: str
    value: float
    unit: str
    #: Sai số đọc ảnh, cùng đơn vị với ``value``. 0 nghĩa là mô hình không khai
    #: — và engine coi đó là chưa khai chứ không phải là chính xác tuyệt đối.
    uncertainty: float = 0.0
    #: Cơ sở đọc: "3,2 ô × 5 ms/ô" — để người đối chiếu với ảnh.
    reading: str = ""
    source_image: str = ""
    status: str = PROPOSED

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise IngestError("số đo từ ảnh không có khóa")
        if not self.unit.strip():
            raise IngestError(f"{self.key!r}: số đo từ ảnh không có đơn vị")
        if self.uncertainty < 0:
            raise IngestError(f"{self.key!r}: sai số âm")

    @property
    def uncertainty_declared(self) -> bool:
        return self.uncertainty > 0

    def interval(self) -> tuple[float, float]:
        return (self.value - self.uncertainty, self.value + self.uncertainty)

    def render(self) -> str:
        dong = [f"  {self.key} = {self.value:g} ± {self.uncertainty:g} {self.unit}"]
        if not self.uncertainty_declared:
            dong.append(
                "      ⚠ CHƯA KHAI SAI SỐ. Một con số đọc từ ảnh không bao giờ "
                "chính xác bằng\n"
                "        con số máy đo gửi qua đường truyền — thiếu sai số thì "
                "hai loại ấy trông giống nhau."
            )
        if self.reading:
            dong.append(f"      đọc từ ảnh: {self.reading}")
        if self.source_image:
            dong.append(f"      ảnh gốc   : {self.source_image}")
        return "\n".join(dong)

    def accept(self, value: float | None = None, *, actor: str) -> dict[str, Any]:
        """Người chốt số đo — sửa được giá trị trước khi lưu (TC-23).

        ``value`` là giá trị NGƯỜI chốt. Truyền ``None`` nghĩa là giữ nguyên
        con số Agent đọc được. Bản ghi luôn giữ CẢ HAI, và giữ cả hai mới là
        điểm chính: nếu về sau số đo này gây tranh cãi, câu "máy đọc ra bao
        nhiêu, người sửa thành bao nhiêu" phải trả lời được từ dữ liệu.
        """
        if not actor.strip():
            raise IngestError(
                f"{self.key!r}: lưu số đo phải ghi tên người chốt. Số đọc từ ảnh "
                "là ĐỀ XUẤT; không có người chốt thì nó không thành bản ghi."
            )
        chot = self.value if value is None else float(value)
        return {
            "ts": _now(),
            "key": self.key,
            "value": chot,
            "unit": self.unit,
            "channel": "anh_man_hien_song",
            "actor": actor,
            "proposed_value": self.value,
            "uncertainty": self.uncertainty,
            "edited": chot != self.value,
            "reading": self.reading,
            "source_image": self.source_image,
        }


_LUOC_DO_ANH = """{
  "measurements": [
    {
      "key": "<tên số đo, khớp khóa trong tiêu chí nghiệm thu nếu có>",
      "value": <trị số đọc được>,
      "unit": "<đơn vị — BẮT BUỘC>",
      "uncertainty": <sai số ĐỌC ẢNH, cùng đơn vị; BẮT BUỘC, đừng để 0>,
      "reading": "<thấy gì trên ảnh để ra con số ấy: mấy ô, mỗi ô bao nhiêu>"
    }
  ]
}"""


@dataclass
class ScopeImageReader:
    """Đọc số đo từ ảnh màn hiện sóng — FR-ING-03, TC-23.

    Mọi thứ trả về là *proposed fact*. Ảnh gốc được giữ lại ở ``MediaStore``
    trước khi trích, vì câu "máy đọc nhầm ảnh" chỉ kiểm chứng lại được khi ảnh
    còn đó.
    """

    llm: Any
    media: MediaStore | None = None
    budget: int = 1500

    def read(self, image: str | Path, *, expect: Sequence[str] = ()) -> list[ProposedMeasurement]:
        from eaa.llm.base import LLMError, Prompt, PromptLayer

        image = Path(image)
        if not image.is_file():
            raise IngestError(f"Không tìm thấy ảnh: {image}")
        if classify(image) != InputKind.IMAGE:
            raise IngestError(
                f"{image} không phải ảnh (nhận diện: {classify(image)}). Kịch bản "
                "này đọc màn hiện sóng, không đọc tệp khác."
            )

        luu = self.media.store(image) if self.media is not None else image

        prompt = Prompt(
            system_instruction=(
                "Bạn đọc số đo từ ảnh chụp màn hiện sóng. Với MỖI đại lượng, "
                "nêu trị số, đơn vị, và SAI SỐ ĐỌC ẢNH — sai số là bắt buộc và "
                "không được để 0: con trỏ đặt lệch nửa ô là đã lệch. Nói rõ bạn "
                "thấy gì trên ảnh để ra con số ấy (mấy ô, mỗi ô bao nhiêu). "
                "Không đọc được thì BỎ QUA đại lượng đó — một con số bịa ra kèm "
                "đơn vị đúng còn tệ hơn không có con số nào."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Ảnh: {luu.name}\n"
                    + (f"Cần đọc các đại lượng: {', '.join(expect)}\n" if expect else "")
                    + "\nTrả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                    f"```json\n{_LUOC_DO_ANH}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module="đọc màn hiện sóng",
            budget=self.budget + 600,
        )
        prompt.image_path = str(luu)

        try:
            van_ban = (
                self.llm.complete(prompt)
                if hasattr(self.llm, "complete")
                else self.llm.generate(prompt).raw_response
            )
        except LLMError as exc:
            raise IngestError(f"Không đọc được ảnh: {exc}") from exc

        from eaa.options import boc_json

        du_lieu = boc_json(van_ban, IngestError)
        ket_qua: list[ProposedMeasurement] = []
        for m in du_lieu.get("measurements") or []:
            if not isinstance(m, dict):
                continue
            try:
                gia_tri = float(m.get("value"))
            except (TypeError, ValueError):
                continue
            ket_qua.append(
                ProposedMeasurement(
                    key=str(m.get("key", "")),
                    value=gia_tri,
                    unit=str(m.get("unit", "")),
                    uncertainty=float(m.get("uncertainty") or 0.0),
                    reading=str(m.get("reading", "")),
                    source_image=str(luu),
                )
            )
        return ket_qua


# --------------------------------------------------------------------------
# Nạp PDF thành chunk đề xuất — quy trình P1
# --------------------------------------------------------------------------


@dataclass
class ProposedChunk:
    """Một chunk đề xuất, chưa vào kho cho tới khi người duyệt tại G2."""

    id: str
    device: str
    peripheral: str
    registers: tuple[str, ...]
    topic: str
    source: str
    source_hash: str
    body: str
    confidence: str = "medium"
    note: str = ""

    def to_markdown(self) -> str:
        meta = {
            "id": self.id,
            "device": self.device,
            "peripheral": self.peripheral,
            "registers": list(self.registers),
            "topic": self.topic,
            "source": self.source,
            "source_hash": self.source_hash,
            # Điểm mấu chốt: luôn là proposed. Không có tham số nào ở tầng này
            # đặt thẳng thành approved — chỉ con người tại G2 làm được điều đó.
            "status": PROPOSED,
            "confidence": self.confidence,
        }
        if self.note:
            meta["note"] = self.note
        return (
            "---\n"
            + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip("\n")
            + "\n---\n\n"
            + self.body.strip()
            + "\n"
        )


@dataclass
class PdfIngestor:
    """Nạp trích đoạn PDF thành chunk đề xuất — AIS §4.1.

    Theo đúng bước 1 của quy trình P1, **con người chọn trang**: tài liệu gốc
    hàng trăm trang chỉ cho ra vài chục chunk, và việc chọn ấy là việc của kỹ
    sư. Hàm này không nạp tự động cả tệp, và cố tình không có chế độ để làm thế.
    """

    datasheets_dir: Path
    registry: SourceRegistry | None = None
    #: Bộ định dạng: nhận văn bản thô, trả về bảng thanh ghi–bit đã chưng cất
    #: (K2). Ở Sprint 4 đây là mô hình đa phương thức; chưa có thì dùng bộ
    #: chưng cất theo luật ở dưới.
    formatter: Any = None

    def __post_init__(self) -> None:
        self.datasheets_dir = Path(self.datasheets_dir)

    # ----------------------------------------------------------------------

    @staticmethod
    def extract_text(path: str | Path, pages: str = "") -> tuple[str, list[int]]:
        """Trích văn bản của ĐÚNG những trang người chọn."""
        path = Path(path)
        if not path.is_file():
            raise IngestError(f"Không tìm thấy tệp PDF: {path}")

        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - phụ thuộc đã khai báo
            raise IngestError(
                "Thiếu thư viện đọc PDF (pypdf). Cài bằng: pip install pypdf"
            ) from exc

        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise IngestError(f"{path}: không đọc được PDF — {exc}") from exc

        so_trang = _parse_pages(pages, len(reader.pages))
        phan: list[str] = []
        for i in so_trang:
            try:
                phan.append(reader.pages[i - 1].extract_text() or "")
            except Exception as exc:  # pragma: no cover - trang hỏng
                raise IngestError(f"{path}: lỗi đọc trang {i} — {exc}") from exc

        van_ban = "\n".join(phan).strip()
        if not van_ban:
            raise IngestError(
                f"{path}: không trích được chữ nào từ trang {pages or 'toàn bộ'}. "
                "Có thể là PDF ảnh quét — cần nhận dạng ký tự, và kết quả nhận "
                "dạng vẫn phải qua G2 như mọi trích xuất khác."
            )
        return van_ban, so_trang

    def ingest(
        self,
        path: str | Path,
        *,
        device: str,
        peripheral: str,
        pages: str = "",
        topic: str = "",
        chunk_id: str = "",
        registers: Sequence[str] = (),
    ) -> ProposedChunk:
        """Nạp một trích đoạn PDF → chunk ĐỀ XUẤT, ghi vào kho ở trạng thái chờ G2."""
        path = Path(path)
        van_ban, so_trang = self.extract_text(path, pages)
        bam = _hash_file(path)

        than = (
            self.formatter(van_ban, device=device, peripheral=peripheral)
            if self.formatter is not None
            else _chung_cat_theo_luat(van_ban, peripheral)
        )

        tim_duoc = tuple(registers) or _doan_thanh_ghi(van_ban)
        de_xuat = ProposedChunk(
            id=chunk_id or self._ma_moi(device, peripheral),
            device=device,
            peripheral=peripheral,
            registers=tim_duoc,
            topic=topic or f"Trích đoạn {peripheral} từ {path.name}",
            source=f"{path.name}, tr.{_mo_ta_trang(so_trang)}",
            source_hash=bam,
            body=than,
            note=(
                "Chunk ĐỀ XUẤT do máy trích xuất. Kỹ sư phải đối chiếu từng bit với "
                "bản gốc trước khi duyệt tại G2 — chunk sai được đóng dấu là nguồn "
                "ảo giác nguy hiểm nhất (AIS §4.1 bước 2)."
            ),
        )

        self.datasheets_dir.mkdir(parents=True, exist_ok=True)
        dich = self.datasheets_dir / f"{de_xuat.id}.md"
        if dich.exists():
            raise IngestError(f"Đã có tệp chunk {dich.name} — chọn mã chunk khác")
        dich.write_text(de_xuat.to_markdown(), encoding="utf-8")

        if self.registry is not None:
            self.registry.register(
                origin=str(path),
                kind=InputKind.PDF,
                content_hash=bam,
                pages=_mo_ta_trang(so_trang),
                produced=(de_xuat.id,),
                note=f"{device}/{peripheral}",
            )
        return de_xuat

    def _ma_moi(self, device: str, peripheral: str) -> str:
        co_san = {p.stem for p in self.datasheets_dir.glob("*.md")}
        i = 1
        while f"ds-{device[:4]}-{peripheral[:4]}-{i:02d}" in co_san:
            i += 1
        return f"ds-{device[:4]}-{peripheral[:4]}-{i:02d}"


# --------------------------------------------------------------------------
# Trợ giúp
# --------------------------------------------------------------------------


def _parse_pages(pages: str, tong: int) -> list[int]:
    """Đọc mô tả trang kiểu ``222-224,230``."""
    if not pages.strip():
        return list(range(1, tong + 1))

    ket_qua: list[int] = []
    for phan in pages.split(","):
        phan = phan.strip()
        if not phan:
            continue
        if "-" in phan:
            dau, cuoi = phan.split("-", 1)
            try:
                a, b = int(dau), int(cuoi)
            except ValueError as exc:
                raise IngestError(f"Khoảng trang không hợp lệ: {phan!r}") from exc
            if a > b:
                raise IngestError(f"Khoảng trang ngược: {phan!r}")
            ket_qua.extend(range(a, b + 1))
        else:
            try:
                ket_qua.append(int(phan))
            except ValueError as exc:
                raise IngestError(f"Số trang không hợp lệ: {phan!r}") from exc

    ngoai = [i for i in ket_qua if i < 1 or i > tong]
    if ngoai:
        raise IngestError(f"Trang {ngoai} nằm ngoài tài liệu ({tong} trang)")
    return sorted(set(ket_qua))


def _mo_ta_trang(so_trang: Sequence[int]) -> str:
    if not so_trang:
        return ""
    if len(so_trang) == 1:
        return str(so_trang[0])
    return f"{so_trang[0]}-{so_trang[-1]}"


def _doan_thanh_ghi(van_ban: str) -> tuple[str, ...]:
    """Nhặt các định danh trông giống tên thanh ghi, giữ thứ tự xuất hiện.

    Đây chỉ là gợi ý để kỹ sư sửa lại, không phải kết luận — nên nó nằm trong
    frontmatter của một chunk ở trạng thái ``proposed``, chỗ mà mọi thứ đều
    đang chờ người xác nhận.
    """
    thay: list[str] = []
    for m in _TEN_THANH_GHI.finditer(van_ban):
        ten = m.group(0)
        if ten not in thay and not ten.isdigit():
            thay.append(ten)
    return tuple(thay[:12])


def _chung_cat_theo_luat(van_ban: str, peripheral: str) -> str:
    """Bộ chưng cất dự phòng khi chưa có mô hình đa phương thức.

    Cố ý làm ít: gom những dòng có dạng ``TÊN_THANH_GHI = giá trị`` thành bảng
    và giữ nguyên phần còn lại làm trích đoạn thô. Nó KHÔNG giả vờ đã chưng cất
    xong — phần thô được đánh dấu rõ để kỹ sư biết chỗ nào còn phải làm tay.
    """
    cap: list[tuple[str, str]] = []
    for m in _BANG_THANH_GHI.finditer(van_ban):
        cap.append((m.group("reg"), m.group("val")))

    phan = [f"## Trích đoạn {peripheral}", ""]
    if cap:
        phan += ["| Thanh ghi | Giá trị nêu trong tài liệu |", "|---|---|"]
        da_co: set[tuple[str, str]] = set()
        for reg, val in cap:
            if (reg, val) in da_co:
                continue
            da_co.add((reg, val))
            phan.append(f"| {reg} | {val} |")
        phan.append("")

    phan += [
        "### Trích đoạn nguyên văn (CHƯA chưng cất — kỹ sư đối chiếu và rút gọn)",
        "",
        van_ban.strip(),
    ]
    return "\n".join(phan)
