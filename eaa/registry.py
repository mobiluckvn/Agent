"""Kho phẩm xuất — quản lý tài liệu đầu ra và gửi lại theo yêu cầu.

EAA-AIS-05 §8.5; FR-DOC-01/02/03; TC-32, TC-33.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-16.

Điểm thiết kế của mục này, nguyên văn AIS §8.5: **tài liệu là HÀM của dữ
liệu** — báo cáo chỉ số là hàm của nhật ký chỉ số, sơ đồ là hàm của đồ thị. Vì
vậy hai thao tác dưới đây KHÁC NHAU, và lẫn lộn chúng là một lỗi có hậu quả
thật:

* **Gửi lại** (:meth:`ArtifactRegistry.resend`) — trả về ĐÚNG bản đã phát
  hành, bất biến, khớp băm. Cần định dạng khác thì chuyển đổi từ chính bản ấy.
* **Làm mới** (:meth:`ArtifactRegistry.regen`) — chạy lại hàm trên dữ liệu hiện
  hành, ra một PHIÊN BẢN MỚI thay thế bản cũ.

Tình huống mà sự phân biệt này ngăn được: người dùng xin "báo cáo chỉ số" và
nhận về một bản vừa tái sinh, trong khi họ tưởng đó là bản đã nộp cho thầy
tuần trước. Hai bản khác số liệu, và không ai biết cho tới lúc bị hỏi.

Khi cách nói của người dùng chưa phân định rõ, :func:`interpret_request` trả
về ``AMBIGUOUS`` để nơi gọi HỎI LẠI, chứ không đoán (FR-DOC-02).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "RegistryError",
    "ArtifactNotFound",
    "AmbiguousRequest",
    "Artifact",
    "ArtifactRegistry",
    "RequestKind",
    "interpret_request",
    "ARTIFACT_KINDS",
    "CURRENT",
    "SUPERSEDED",
]

CURRENT = "current"
SUPERSEDED = "superseded"

#: Loại phẩm xuất — AIS §8.5.
ARTIFACT_KINDS: tuple[str, ...] = ("docx", "pdf", "code", "image", "csv", "md", "html")


class RegistryError(Exception):
    """Thao tác trên kho phẩm xuất không hợp lệ."""


class ArtifactNotFound(RegistryError):
    """Không tìm thấy phẩm xuất khớp yêu cầu."""


class AmbiguousRequest(RegistryError):
    """Yêu cầu chưa phân định giữa gửi lại và làm mới — phải hỏi lại.

    Cố ý là một ngoại lệ chứ không phải một giá trị trả về mặc định: đoán bừa
    ở đây tạo ra sai lệch âm thầm, còn dừng lại để hỏi thì chỉ tốn một câu.
    """


class RequestKind:
    RESEND = "resend"
    REGEN = "regen"
    AMBIGUOUS = "ambiguous"


_RESEND_HINTS = (
    "gửi lại", "gui lai", "bản đã", "ban da", "đã nộp", "da nop",
    "hôm qua", "hom qua", "tuần trước", "tuan truoc", "đã phát hành",
    "da phat hanh", "bản cũ", "ban cu", "lần trước", "lan truoc",
)
_REGEN_HINTS = (
    "mới nhất", "moi nhat", "làm mới", "lam moi", "cập nhật", "cap nhat",
    "tái sinh", "tai sinh", "hiện tại", "hien tai", "bây giờ", "bay gio",
)


def interpret_request(request: str) -> str:
    """Đoán ý người dùng: gửi lại, làm mới, hay chưa rõ — FR-DOC-02.

    Chỉ kết luận khi cách nói nghiêng hẳn về MỘT phía. Có cả dấu hiệu của hai
    phía ("gửi lại bản mới nhất") thì trả ``AMBIGUOUS``: câu đó thật sự mơ hồ,
    và người hỏi là người duy nhất biết họ muốn gì.
    """
    van_ban = request.lower()
    co_resend = any(t in van_ban for t in _RESEND_HINTS)
    co_regen = any(t in van_ban for t in _REGEN_HINTS)

    if co_resend and not co_regen:
        return RequestKind.RESEND
    if co_regen and not co_resend:
        return RequestKind.REGEN
    return RequestKind.AMBIGUOUS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_bytes(du_lieu: bytes) -> str:
    return "sha256:" + hashlib.sha256(du_lieu).hexdigest()


@dataclass(frozen=True)
class Artifact:
    """Một phẩm xuất đã đăng ký."""

    id: str
    kind: str
    title: str
    description: str
    version: int
    created_at: str
    content_hash: str
    path: str
    #: Dòng dõi dữ liệu — sinh từ commit nào, khoảng dữ liệu nào, phiên bản
    #: ràng buộc và đồ thị nào (AIS §8.5).
    lineage: dict[str, Any] = field(default_factory=dict)
    status: str = CURRENT
    supersedes: str = ""
    superseded_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "content_hash": self.content_hash,
            "path": self.path,
            "lineage": dict(self.lineage),
            "status": self.status,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Artifact":
        return cls(
            id=d["id"],
            kind=d.get("kind", "md"),
            title=d.get("title", ""),
            description=d.get("description", ""),
            version=int(d.get("version", 1)),
            created_at=d.get("created_at", ""),
            content_hash=d.get("content_hash", ""),
            path=d.get("path", ""),
            lineage=dict(d.get("lineage", {})),
            status=d.get("status", CURRENT),
            supersedes=d.get("supersedes", ""),
            superseded_by=d.get("superseded_by", ""),
        )

    @property
    def family(self) -> str:
        """Mã gốc không kèm số phiên bản — nối các phiên bản của cùng tài liệu."""
        return self.id.rsplit("@v", 1)[0]


class ArtifactRegistry:
    """Sổ đăng ký phẩm xuất — ``deliverables/registry.json``."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.index_path = self.root / "registry.json"

    # ----------------------------------------------------------------------
    # Đọc / ghi sổ
    # ----------------------------------------------------------------------

    def all(self) -> list[Artifact]:
        if not self.index_path.is_file():
            return []
        try:
            du_lieu = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RegistryError(f"{self.index_path}: JSON hỏng — {exc}") from exc
        return [Artifact.from_dict(d) for d in du_lieu.get("artifacts", [])]

    def _save(self, artifacts: Sequence[Artifact]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tam = self.index_path.with_suffix(".json.tmp")
        tam.write_text(
            json.dumps(
                {"version": 1, "artifacts": [a.to_dict() for a in artifacts]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(tam, self.index_path)

    # ----------------------------------------------------------------------
    # Phát hành
    # ----------------------------------------------------------------------

    def publish(
        self,
        *,
        family: str,
        kind: str,
        title: str,
        content: bytes | str,
        description: str = "",
        lineage: dict[str, Any] | None = None,
    ) -> Artifact:
        """Đăng ký một phẩm xuất mới. Bản phát hành là BẤT BIẾN kể từ đây."""
        if kind not in ARTIFACT_KINDS:
            raise RegistryError(
                f"Loại phẩm xuất không hợp lệ: {kind!r} (hợp lệ: {list(ARTIFACT_KINDS)})"
            )

        du_lieu = content.encode("utf-8") if isinstance(content, str) else content
        hien_co = self.all()
        cung_ho = [a for a in hien_co if a.family == family]
        phien_ban = max((a.version for a in cung_ho), default=0) + 1

        artifact_id = f"{family}@v{phien_ban}"
        duong_dan = self.root / family / f"v{phien_ban}.{kind}"
        duong_dan.parent.mkdir(parents=True, exist_ok=True)
        duong_dan.write_bytes(du_lieu)

        moi = Artifact(
            id=artifact_id,
            kind=kind,
            title=title,
            description=description,
            version=phien_ban,
            created_at=_now(),
            content_hash=_hash_bytes(du_lieu),
            path=str(duong_dan.relative_to(self.root)),
            lineage=dict(lineage or {}),
            status=CURRENT,
            supersedes=cung_ho[-1].id if cung_ho else "",
        )

        # Bản trước chuyển sang superseded — nhưng KHÔNG bị xóa và vẫn tra được.
        cap_nhat: list[Artifact] = []
        for a in hien_co:
            if a.family == family and a.status == CURRENT:
                cap_nhat.append(
                    Artifact(**{**a.__dict__, "status": SUPERSEDED, "superseded_by": artifact_id})
                )
            else:
                cap_nhat.append(a)
        cap_nhat.append(moi)
        self._save(cap_nhat)
        return moi

    # ----------------------------------------------------------------------
    # Tra cứu
    # ----------------------------------------------------------------------

    def get(self, artifact_id: str) -> Artifact:
        for a in self.all():
            if a.id == artifact_id:
                return a
        raise ArtifactNotFound(f"Không có phẩm xuất {artifact_id!r}")

    def current(self, family: str) -> Artifact:
        for a in self.all():
            if a.family == family and a.status == CURRENT:
                return a
        raise ArtifactNotFound(f"Không có bản hiện hành của {family!r}")

    def versions(self, family: str) -> list[Artifact]:
        return sorted(
            (a for a in self.all() if a.family == family), key=lambda a: a.version
        )

    def find(
        self,
        description: str = "",
        *,
        kind: str | None = None,
        on_date: str = "",
        status: str | None = None,
    ) -> list[Artifact]:
        """Truy hồi bằng mô tả tự nhiên + bộ lọc loại/thời gian — FR-DOC-03."""
        tu_khoa = [t for t in re.split(r"\W+", description.lower()) if len(t) > 2]
        ket_qua: list[Artifact] = []

        for a in self.all():
            if kind and a.kind != kind:
                continue
            if status and a.status != status:
                continue
            if on_date and not a.created_at.startswith(on_date):
                continue
            if tu_khoa:
                van_ban = f"{a.id} {a.title} {a.description}".lower()
                if not any(t in van_ban for t in tu_khoa):
                    continue
            ket_qua.append(a)

        return sorted(ket_qua, key=lambda a: (a.created_at, a.version), reverse=True)

    # ----------------------------------------------------------------------
    # TC-32 — gửi lại bản đã phát hành
    # ----------------------------------------------------------------------

    def resend(self, artifact_id: str, *, fmt: str = "", dest: Path | None = None) -> Path:
        """Trả về ĐÚNG bản đã phát hành, khớp băm — TC-32.

        Kiểm băm trước khi trao: một tệp phát hành bị sửa sau lưng thì việc gửi
        lại nó không còn là "gửi lại bản đã nộp" nữa, mà là gửi một thứ khác
        mang cùng tên. Thà báo lỗi.

        Cần định dạng khác thì chuyển đổi TỪ CHÍNH BẢN ẤY — không tái sinh từ
        dữ liệu hiện hành, và không tạo phiên bản mới trong sổ.
        """
        artifact = self.get(artifact_id)
        nguon = self.root / artifact.path
        if not nguon.is_file():
            raise RegistryError(
                f"Tệp phát hành của {artifact_id} không còn ở {nguon}. Kho phẩm "
                "xuất mất tính bất biến — khôi phục từ Git."
            )

        bam = _hash_bytes(nguon.read_bytes())
        if bam != artifact.content_hash:
            raise RegistryError(
                f"Bản phát hành {artifact_id} đã bị sửa (băm sổ {artifact.content_hash}, "
                f"băm tệp {bam}). Bản phát hành là BẤT BIẾN; muốn nội dung mới thì "
                "dùng 'làm mới' để tạo phiên bản mới, đừng sửa tại chỗ."
            )

        if not fmt or fmt == artifact.kind:
            return nguon

        du_lieu = convert(nguon.read_bytes(), artifact.kind, fmt, title=artifact.title)
        dich = dest or (self.root / artifact.family / f"v{artifact.version}.{fmt}")
        dich.parent.mkdir(parents=True, exist_ok=True)
        dich.write_bytes(du_lieu)
        return dich

    # ----------------------------------------------------------------------
    # TC-33 — làm mới từ dữ liệu hiện hành
    # ----------------------------------------------------------------------

    def regen(
        self,
        family: str,
        produce: Callable[[], tuple[bytes | str, dict[str, Any]]],
        *,
        kind: str | None = None,
        title: str = "",
        description: str = "",
    ) -> Artifact:
        """Chạy lại hàm sinh trên dữ liệu HIỆN HÀNH → phiên bản mới — TC-33.

        Bản cũ chuyển ``superseded`` nhưng còn nguyên vẹn và vẫn tra được: đó
        là điều kiện để so được hai bản khi có ai hỏi "số liệu đổi chỗ nào".
        """
        try:
            cu = self.current(family)
        except ArtifactNotFound:
            cu = None

        noi_dung, lineage = produce()
        return self.publish(
            family=family,
            kind=kind or (cu.kind if cu else "md"),
            title=title or (cu.title if cu else family),
            content=noi_dung,
            description=description or (cu.description if cu else ""),
            lineage=lineage,
        )

    # ----------------------------------------------------------------------
    # Trình bày
    # ----------------------------------------------------------------------

    def render_list(self, artifacts: Sequence[Artifact] | None = None) -> str:
        muc = list(artifacts if artifacts is not None else self.all())
        if not muc:
            return "(kho phẩm xuất trống)"

        dong = [f"{'id':<28}{'loại':<7}{'ngày':<12}{'trạng thái':<12}tiêu đề"]
        dong.append("─" * 92)
        for a in sorted(muc, key=lambda x: (x.family, x.version)):
            dong.append(
                f"{a.id:<28}{a.kind:<7}{a.created_at[:10]:<12}{a.status:<12}{a.title}"
            )
            if a.lineage:
                dong.append(
                    "    dòng dõi: "
                    + ", ".join(f"{k}={v}" for k, v in sorted(a.lineage.items()))
                )
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Chuyển đổi định dạng — luôn từ bản đã phát hành
# --------------------------------------------------------------------------


def convert(du_lieu: bytes, tu: str, sang: str, *, title: str = "") -> bytes:
    """Chuyển đổi nội dung một bản phát hành sang định dạng khác.

    Cố ý chỉ hỗ trợ những cặp chuyển đổi làm được TRỌN VẸN bằng mã trong kho
    này. Cặp nào cần công cụ ngoài thì báo lỗi nói rõ, thay vì trả về một tệp
    gần đúng — một báo cáo mất bảng biểu khi chuyển định dạng vẫn mang đúng
    tên và đúng ngày, nên sai lệch sẽ không ai phát hiện.
    """
    if tu == sang:
        return du_lieu

    van_ban: str | None = None
    if tu in ("md", "csv", "code", "html"):
        van_ban = du_lieu.decode("utf-8", errors="replace")

    if van_ban is None:
        raise RegistryError(
            f"Chưa hỗ trợ chuyển {tu} → {sang}. Cặp này cần công cụ ngoài; khai "
            "báo nó trong tool manifest rồi chạy 'eaa doctor' trước."
        )

    if tu == "csv" and sang in ("md", "pdf"):
        van_ban = _csv_sang_bang(van_ban)

    if sang == "md":
        return van_ban.encode("utf-8")
    if sang == "html":
        return _sang_html(van_ban, title).encode("utf-8")
    if sang == "pdf":
        return _sang_pdf(van_ban, title)

    raise RegistryError(f"Chưa hỗ trợ chuyển {tu} → {sang}.")


def _csv_sang_bang(van_ban: str) -> str:
    dong = list(csv.reader(io.StringIO(van_ban)))
    if not dong:
        return van_ban
    tieu_de, *than = dong
    ket_qua = ["| " + " | ".join(tieu_de) + " |", "|" + "---|" * len(tieu_de)]
    for d in than:
        ket_qua.append("| " + " | ".join(d) + " |")
    return "\n".join(ket_qua)


def _sang_html(van_ban: str, title: str) -> str:
    thoat = (
        van_ban.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        "<!doctype html>\n<meta charset=\"utf-8\">\n"
        f"<title>{title}</title>\n<pre>\n{thoat}\n</pre>\n"
    )


def _sang_pdf(van_ban: str, title: str) -> bytes:
    """Sinh PDF một cách tối giản: văn bản đơn sắc, phân trang cứng.

    Không dùng thư viện dựng PDF nào: phẩm xuất ở đây là báo cáo số liệu dạng
    văn bản và bảng, và một bộ sinh 40 dòng đủ cho việc đó. Bù lại nó không có
    phụ thuộc mới, và định dạng đầu ra không đổi theo phiên bản thư viện —
    điều đáng giá với những tệp sẽ được nộp kèm đề án.
    """
    dong_moi_trang = 55
    dong = []
    for d in (f"{title}", "") if title else []:
        dong.append(d)
    for d in van_ban.splitlines():
        # Cắt dòng dài để không tràn ra ngoài lề.
        while len(d) > 95:
            dong.append(d[:95])
            d = d[95:]
        dong.append(d)

    trang = [dong[i : i + dong_moi_trang] for i in range(0, len(dong), dong_moi_trang)] or [[""]]

    doi_tuong: list[bytes] = []

    def them(noi_dung: bytes) -> int:
        doi_tuong.append(noi_dung)
        return len(doi_tuong)

    so_font = them(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    so_trang: list[int] = []
    for cac_dong in trang:
        phan = " ".join(
            f"({_thoat_pdf(d)}) Tj 0 -13 Td" for d in cac_dong
        )
        luong = f"BT /F1 9 Tf 40 800 Td {phan} ET".encode("latin-1", errors="replace")
        so_luong = them(
            b"<< /Length " + str(len(luong)).encode() + b" >>\nstream\n" + luong + b"\nendstream"
        )
        so_trang.append(
            them(
                b"<< /Type /Page /Parent PARENT 0 R /MediaBox [0 0 595 842] /Contents "
                + str(so_luong).encode()
                + b" 0 R /Resources << /Font << /F1 "
                + str(so_font).encode()
                + b" 0 R >> >> >>"
            )
        )

    kids = b" ".join(f"{n} 0 R".encode() for n in so_trang)
    so_pages = them(
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(so_trang)).encode() + b" >>"
    )
    so_catalog = them(b"<< /Type /Catalog /Pages " + str(so_pages).encode() + b" 0 R >>")
    for i in so_trang:
        doi_tuong[i - 1] = doi_tuong[i - 1].replace(b"PARENT", str(so_pages).encode())

    ra = bytearray(b"%PDF-1.4\n")
    vi_tri: list[int] = []
    for i, noi_dung in enumerate(doi_tuong, 1):
        vi_tri.append(len(ra))
        ra += str(i).encode() + b" 0 obj\n" + noi_dung + b"\nendobj\n"

    xref = len(ra)
    ra += b"xref\n0 " + str(len(doi_tuong) + 1).encode() + b"\n0000000000 65535 f \n"
    for v in vi_tri:
        ra += f"{v:010d} 00000 n \n".encode()
    ra += (
        b"trailer\n<< /Size " + str(len(doi_tuong) + 1).encode()
        + b" /Root " + str(so_catalog).encode() + b" 0 R >>\nstartxref\n"
        + str(xref).encode() + b"\n%%EOF\n"
    )
    return bytes(ra)


def _thoat_pdf(d: str) -> str:
    return d.replace("\\", "").replace("(", "[").replace(")", "]")
