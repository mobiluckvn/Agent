"""Tự tìm công cụ chưa biết — chế độ thứ ba của ``eaa doctor``.

EAA-AIS-05 §9.2 (chế độ "Tìm công cụ mới"), §9.1 (manifest là một kho tri
thức, mọi thay đổi qua gate), §9.4 (giới hạn an toàn); FR-ENV-03.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-26.

Hai chế độ đầu của doctor giả định đã biết cần công cụ gì. Chế độ này trả lời
câu hỏi đứng trước đó: **nhiệm vụ cần công cụ mà manifest chưa có thì làm sao?**

Nguồn của nhu cầu là Platform Pack, không phải một danh sách viết tay
-------------------------------------------------------------------

``pack.yaml`` đã khai báo mọi chương trình nó gọi — phần tử đầu của mỗi
``command``. Vậy nhu cầu công cụ SUY RA ĐƯỢC từ pack, không cần ai chép lại.
Điều này quan trọng hơn vẻ tiện lợi của nó: một danh sách chép tay sẽ lệch khỏi
pack ngay lần đầu pack đổi lệnh, và lệch theo hướng nguy hiểm — doctor báo
"đủ công cụ" trong khi cổng kiểm chứng sắp gọi một chương trình không có.

Manifest vì thế KHÔNG phải nơi khai báo nhu cầu. Nó là nơi ghi những công cụ
đã được người DUYỆT: biết tên, biết cách kiểm phiên bản, biết cách cài. Nhu
cầu nằm ở pack; hiểu biết nằm ở manifest; khoảng cách giữa hai bên chính là
việc của chế độ này.

Ba bước, và bước nào cũng dừng trước con người
----------------------------------------------

1. **Phát hiện** — so nhu cầu suy từ pack với manifest, ra danh sách công cụ
   chưa biết gì.
2. **Tra cứu** — Agent đề xuất: công cụ là gì, phiên bản tối thiểu, nguồn cài
   theo từng hệ điều hành, và LÝ DO. Đề xuất là *proposed fact*, y như mọi
   trích xuất khác trong hệ thống này.
3. **Duyệt** — người xem đề xuất tại gate tri thức; duyệt rồi mới ghi vào
   manifest; ghi vào manifest rồi mới cài được.

**Kiểm nguồn cài trước khi tới tay người.** Một đề xuất chỉ được trình lên nếu
lệnh cài dùng trình quản lý gói chính thống, hoặc tải trực tiếp từ miền cho
phép KÈM checksum (AIS §9.4). Đề xuất không thỏa bị chặn ngay — không phải để
người khỏi phải nghĩ, mà vì một lệnh cài trông hợp lý nằm cạnh chín đề xuất
hợp lệ khác là thứ dễ được bấm duyệt nhất.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

import yaml

__all__ = [
    "ToolSearchError",
    "UnsafeInstallSource",
    "ToolRequirement",
    "ToolProposal",
    "PACKAGE_MANAGERS",
    "DOWNLOAD_WHITELIST",
    "derive_requirements",
    "validate_proposal",
    "LlmToolResearcher",
    "append_to_manifest",
]

#: Trình quản lý gói chính thống được phép dùng trong lệnh cài (AIS §9.4).
#:
#: Danh sách này hẹp có chủ ý. Mỗi mục là một trình có kho gói được ký và có
#: người duy trì; thêm một mục vào đây là mở rộng bề mặt tin cậy của cả sản
#: phẩm, nên nó phải là một quyết định tường minh chứ không phải một dòng thêm
#: cho tiện.
PACKAGE_MANAGERS: dict[str, tuple[str, ...]] = {
    "brew": ("install",),
    "apt-get": ("install",),
    "apt": ("install",),
    "dnf": ("install",),
    "pacman": ("-S",),
    "winget": ("install",),
    "choco": ("install",),
    "scoop": ("install",),
    "pip": ("install",),
    "pipx": ("install",),
}

#: Miền được phép tải trực tiếp. Tải trực tiếp LUÔN phải kèm checksum.
DOWNLOAD_WHITELIST: tuple[str, ...] = (
    "microchip.com",
    "atmel.com",
    "st.com",
    "nxp.com",
    "ti.com",
    "infineon.com",
    "espressif.com",
    "raspberrypi.com",
    "arm.com",
    "developer.arm.com",
    "gnu.org",
    "sourceware.org",
    "kernel.org",
    "python.org",
    "git-scm.com",
    "github.com",
)

#: Chương trình do chỗ giữ quyết định lúc chạy, không phải công cụ phải cài.
_PLACEHOLDER = re.compile(r"^\{\w+\}$")


def _chuan_hoa_phien_ban(rang_buoc: str) -> str:
    """``">=12.0"`` → ``"12.0"`` — manifest ghi ngưỡng trần trụi."""
    return rang_buoc.lstrip(">=~^ ").strip()


class ToolSearchError(Exception):
    """Không tra cứu hoặc không dựng được đề xuất công cụ."""


class UnsafeInstallSource(ToolSearchError):
    """Đề xuất có nguồn cài nằm ngoài giới hạn an toàn của AIS §9.4."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ToolRequirement:
    """Một chương trình mà Platform Pack sẽ gọi tới."""

    program: str
    #: Năng lực nào cần nó — dùng để nói rõ cổng nào bị chặn nếu thiếu.
    capabilities: tuple[str, ...]
    pack: str = ""
    #: Đã có mặt trên máy chưa (chỉ để hiển thị; quyết định vẫn ở doctor).
    present: bool = False
    #: Ràng buộc phiên bản pack tự khai (``tool_requirements``), nếu có.
    min_version: str = ""

    @property
    def gates(self) -> tuple[str, ...]:
        return self.capabilities


def derive_requirements(
    pack_manifest: Any, *, extra: Iterable[str] = ()
) -> list[ToolRequirement]:
    """Suy nhu cầu công cụ TỪ PACK, không từ danh sách chép tay.

    Bỏ qua phần tử argv là chỗ giữ (``{python}``): đó là chương trình do engine
    quyết định lúc chạy, không phải thứ người dùng phải đi cài.
    """
    theo_chuong_trinh: dict[str, list[str]] = {}
    for ten_nang_luc in getattr(pack_manifest, "capabilities", {}):
        goi = pack_manifest.invocation(ten_nang_luc)
        chuong_trinh = goi.command[0]
        if _PLACEHOLDER.match(chuong_trinh):
            continue
        theo_chuong_trinh.setdefault(chuong_trinh, []).append(ten_nang_luc)

    for ten in extra:
        theo_chuong_trinh.setdefault(ten, [])

    # Pack cũng tự khai ràng buộc phiên bản. Nó là tài liệu đã qua G1, nên nó
    # có tiếng nói cuối về "tối thiểu bao nhiêu" — không để mô hình đoán lại.
    rang_buoc = getattr(pack_manifest, "tool_requirements", {}) or {}

    return [
        ToolRequirement(
            program=ten,
            capabilities=tuple(sorted(nang_luc)),
            pack=getattr(pack_manifest, "name", ""),
            present=shutil.which(ten) is not None,
            min_version=str(rang_buoc.get(ten, "")),
        )
        for ten, nang_luc in sorted(theo_chuong_trinh.items())
    ]


@dataclass(frozen=True)
class ToolProposal:
    """Đề xuất một công cụ để thêm vào manifest — một *proposed fact*."""

    name: str
    description: str
    min_version: str
    check: tuple[str, ...]
    install: dict[str, tuple[str, ...]]
    rationale: str
    homepage: str = ""
    download: str = ""
    checksum: str = ""
    smoke: tuple[str, ...] = ()
    smoke_expect: str = ""
    #: Cách đọc dòng lỗi của công cụ — vào Thẻ công cụ (AIS §9.5).
    error_regex: str = ""
    version_regex: str = r"(\d+\.\d+(?:\.\d+)?)"
    gates: tuple[str, ...] = ()
    scope: str = "engine"
    #: Mô hình nào đề xuất, để truy vết như mọi tri thức khác (NFR-07).
    proposed_by: str = ""
    proposed_at: str = field(default_factory=_now)

    def to_manifest_entry(self) -> dict[str, Any]:
        muc: dict[str, Any] = {
            "name": self.name,
            "check": list(self.check),
            "min_version": self.min_version,
            "level": "Must",
            "gates": list(self.gates),
            "install": {k: list(v) for k, v in sorted(self.install.items())},
            "version_regex": self.version_regex,
            "scope": self.scope,
            "note": f"{self.description} — {self.rationale}",
        }
        if self.smoke:
            muc["smoke"] = list(self.smoke)
        if self.smoke_expect:
            muc["smoke_expect"] = self.smoke_expect
        if self.error_regex:
            muc["error_regex"] = self.error_regex
        if self.download:
            muc["download"] = self.download
            muc["checksum"] = self.checksum
        return muc

    def to_dict(self) -> dict[str, Any]:
        """Dạng lưu trữ đầy đủ — khôi phục lại được nguyên vẹn.

        Khác ``to_manifest_entry``: mục manifest gộp mô tả và lý do vào một
        dòng ``note`` cho người đọc, nên không dựng lại được đề xuất từ nó. Đề
        xuất còn phải nằm chờ giữa lúc tra cứu và lúc người duyệt, và thứ được
        duyệt phải đúng thứ đã trình.
        """
        return {
            "name": self.name,
            "description": self.description,
            "min_version": self.min_version,
            "check": list(self.check),
            "install": {k: list(v) for k, v in sorted(self.install.items())},
            "rationale": self.rationale,
            "homepage": self.homepage,
            "download": self.download,
            "checksum": self.checksum,
            "smoke": list(self.smoke),
            "smoke_expect": self.smoke_expect,
            "error_regex": self.error_regex,
            "version_regex": self.version_regex,
            "gates": list(self.gates),
            "scope": self.scope,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolProposal":
        return cls(
            name=str(d.get("name", "")),
            description=str(d.get("description", "")),
            min_version=str(d.get("min_version", "")),
            check=tuple(str(x) for x in d.get("check", ())),
            install={
                str(k): tuple(str(x) for x in v)
                for k, v in (d.get("install") or {}).items()
            },
            rationale=str(d.get("rationale", "")),
            homepage=str(d.get("homepage", "")),
            download=str(d.get("download", "")),
            checksum=str(d.get("checksum", "")),
            smoke=tuple(str(x) for x in d.get("smoke", ())),
            smoke_expect=str(d.get("smoke_expect", "")),
            error_regex=str(d.get("error_regex", "")),
            version_regex=str(d.get("version_regex", r"(\d+\.\d+(?:\.\d+)?)")),
            gates=tuple(str(x) for x in d.get("gates", ())),
            scope=str(d.get("scope", "engine")),
            proposed_by=str(d.get("proposed_by", "")),
            proposed_at=str(d.get("proposed_at", "")) or _now(),
        )

    @property
    def digest_line(self) -> str:
        """Một dòng đại diện đề xuất, để gộp vào băm nội dung của hồ sơ gate.

        Có mặt cả lệnh cài: người duyệt "công cụ X" là duyệt cả cách cài X, nên
        đổi lệnh cài sau khi trình lên phải làm quyết định cũ hết khớp.
        """
        lenh = ";".join(
            f"{he}:{' '.join(cmd)}" for he, cmd in sorted(self.install.items())
        )
        return f"{self.name}@{self.min_version}|{' '.join(self.check)}|{lenh}"

    def render(self) -> str:
        dong = [
            f"Công cụ đề xuất: {self.name}",
            f"  Mô tả        : {self.description}",
            f"  Phiên bản tối thiểu: {self.min_version or '(không nêu)'}",
            f"  Lệnh kiểm tra: {' '.join(self.check)}",
            f"  Phục vụ cổng : {', '.join(self.gates) or '—'}",
            f"  Trang chính  : {self.homepage or '—'}",
            "",
            "  Lệnh cài theo hệ điều hành:",
        ]
        for he, lenh in sorted(self.install.items()):
            dong.append(f"    {he:<9}{' '.join(lenh)}")
        if self.download:
            dong.append(f"  Tải trực tiếp: {self.download}")
            dong.append(f"  Checksum     : {self.checksum}")
        dong += ["", f"  Lý do        : {self.rationale}", f"  Đề xuất bởi  : {self.proposed_by}"]
        return "\n".join(dong)


def validate_proposal(proposal: ToolProposal) -> ToolProposal:
    """Kiểm giới hạn an toàn TRƯỚC khi đề xuất tới tay người — AIS §9.4.

    Chặn ở đây chứ không dựa vào người đọc kỹ: một lệnh cài trông hợp lý nằm
    cạnh chín đề xuất hợp lệ khác là thứ dễ được bấm duyệt nhất. Người vẫn phải
    duyệt, nhưng thứ đưa lên bàn phải đã qua một vòng lọc máy làm được.
    """
    if not proposal.name.strip():
        raise ToolSearchError("Đề xuất thiếu tên công cụ")
    if not proposal.check:
        raise ToolSearchError(
            f"{proposal.name}: thiếu lệnh kiểm tra phiên bản — không có nó thì "
            "doctor không xác nhận được công cụ đã cài hay chưa"
        )
    if not proposal.install:
        raise ToolSearchError(
            f"{proposal.name}: không có lệnh cài cho hệ điều hành nào"
        )

    for he_dieu_hanh, lenh in proposal.install.items():
        if not lenh:
            raise UnsafeInstallSource(f"{proposal.name}: lệnh cài rỗng cho {he_dieu_hanh}")

        chuong_trinh = lenh[0]
        if chuong_trinh in ("sudo", "doas"):
            if len(lenh) < 2:
                raise UnsafeInstallSource(
                    f"{proposal.name}: lệnh cài chỉ có {chuong_trinh!r}"
                )
            chuong_trinh = lenh[1]

        if chuong_trinh not in PACKAGE_MANAGERS:
            raise UnsafeInstallSource(
                f"{proposal.name} ({he_dieu_hanh}): lệnh cài dùng {chuong_trinh!r}, "
                f"không nằm trong danh sách trình quản lý gói cho phép "
                f"({', '.join(sorted(PACKAGE_MANAGERS))}).\n"
                "Cài từ một nguồn tùy ý là đường ngắn nhất để đưa mã lạ vào máy "
                "kỹ sư — đề xuất bị chặn trước khi tới tay người (AIS §9.4)."
            )

        con_lai = lenh[lenh.index(chuong_trinh) + 1 :]
        if not any(dong_tu in con_lai for dong_tu in PACKAGE_MANAGERS[chuong_trinh]):
            raise UnsafeInstallSource(
                f"{proposal.name} ({he_dieu_hanh}): lệnh {chuong_trinh!r} không có "
                f"động từ cài hợp lệ ({', '.join(PACKAGE_MANAGERS[chuong_trinh])}). "
                "Chỉ chấp nhận lệnh CÀI, không chấp nhận lệnh tùy ý."
            )

        _kiem_chuoi_nguy_hiem(proposal.name, he_dieu_hanh, lenh)

    if proposal.download:
        _kiem_tai_truc_tiep(proposal)

    return proposal


def _kiem_chuoi_nguy_hiem(ten: str, he: str, lenh: Sequence[str]) -> None:
    """Chặn dấu hiệu nối lệnh hoặc chạy mã tải về.

    Engine chạy argv không qua shell nên ``;`` hay ``|`` không tự thi hành —
    nhưng một đề xuất chứa chúng nghĩa là mô hình đang cố làm một việc khác với
    "cài một gói", và đó đủ là lý do để từ chối.
    """
    dang_ngo = (";", "&&", "||", "|", ">", "<", "`", "$(", "curl", "wget", "bash", "sh")
    for phan in lenh:
        for dau in dang_ngo:
            if dau in phan:
                raise UnsafeInstallSource(
                    f"{ten} ({he}): lệnh cài chứa {dau!r} — đề xuất đang cố làm "
                    "gì đó khác việc cài một gói. Từ chối."
                )


def _kiem_tai_truc_tiep(proposal: ToolProposal) -> None:
    phan_tich = urlparse(proposal.download)
    if phan_tich.scheme != "https":
        raise UnsafeInstallSource(
            f"{proposal.name}: tải trực tiếp phải qua HTTPS, nhận "
            f"{phan_tich.scheme or '(không có)'}"
        )

    host = (phan_tich.hostname or "").lower().rstrip(".")
    if not any(host == d or host.endswith("." + d) for d in DOWNLOAD_WHITELIST):
        raise UnsafeInstallSource(
            f"{proposal.name}: miền tải {host!r} nằm ngoài danh sách cho phép. "
            "So theo hậu tố tên miền, không so chuỗi con."
        )

    if not re.fullmatch(r"(sha256:)?[0-9a-fA-F]{64}", proposal.checksum or ""):
        raise UnsafeInstallSource(
            f"{proposal.name}: tải trực tiếp BẮT BUỘC kèm checksum sha256 hợp lệ "
            "(AIS §9.4). Không có checksum thì không có cách nào biết thứ tải về "
            "đúng là thứ đã kiểm."
        )


# --------------------------------------------------------------------------
# Tra cứu bằng mô hình
# --------------------------------------------------------------------------


_LUOC_DO = """{
  "name": "<tên chương trình gọi trên dòng lệnh>",
  "description": "<một câu công cụ này là gì>",
  "min_version": "<phiên bản tối thiểu hợp lý, dạng x.y>",
  "check": ["<chương trình>", "<cờ in phiên bản>"],
  "install": {
    "macos": ["brew", "install", "<gói>"],
    "linux": ["sudo", "apt-get", "install", "-y", "<gói>"],
    "windows": ["winget", "install", "-e", "--id", "<id>"]
  },
  "smoke": ["<chương trình>", "<cờ>"],
  "error_regex": "<regex bắt một dòng lỗi của công cụ, có nhóm tên file/line/msg; để rỗng nếu công cụ không in lỗi theo dòng>",
  "smoke_expect": "<chuỗi chắc chắn có trong đầu ra>",
  "homepage": "<trang chính thức>",
  "rationale": "<vì sao dự án này cần nó>"
}"""


@dataclass
class LlmToolResearcher:
    """Đề xuất công cụ bằng mô hình nền — AIS §9.2 chế độ ba.

    Trả về *proposed fact*, không phải kết luận. Mọi đề xuất còn phải qua
    :func:`validate_proposal` rồi mới tới tay người, và qua người rồi mới vào
    manifest.
    """

    llm: Any
    #: Ngân sách cho một lần tra cứu — nhỏ, vì đây là câu hỏi tra cứu ngắn.
    budget: int = 2000

    def propose(self, requirement: ToolRequirement, *, os_key: str = "") -> ToolProposal:
        from eaa.llm.base import Prompt, PromptLayer

        cong = ", ".join(requirement.capabilities) or "(không rõ)"
        rang_buoc = (
            f"Pack yêu cầu phiên bản {requirement.min_version}.\n"
            if requirement.min_version
            else ""
        )
        prompt = Prompt(
            system_instruction=(
                "Bạn tra cứu công cụ dòng lệnh cho một quy trình phát triển phần "
                "mềm nhúng. Chỉ đề xuất công cụ CÓ THẬT và cài được qua trình "
                "quản lý gói chính thống (brew, apt-get, winget, choco, pip). "
                "TUYỆT ĐỐI không đề xuất lệnh tải rồi chạy script. Nếu không "
                "chắc công cụ tồn tại, nói rõ là không chắc thay vì đoán."
            ),
            layers=[
                PromptLayer(
                    "task",
                    f"Platform Pack {requirement.pack!r} gọi chương trình "
                    f"{requirement.program!r} để phục vụ năng lực: {cong}.\n"
                    f"Hệ điều hành đang dùng: {os_key or 'không rõ'}.\n"
                    f"{rang_buoc}\n"
                    "Trả về ĐÚNG một khối JSON theo lược đồ sau, không kèm giải "
                    f"thích ngoài khối:\n\n```json\n{_LUOC_DO}\n```",
                    budget=self.budget,
                    required=True,
                )
            ],
            module=f"tra cứu công cụ {requirement.program}",
            budget=self.budget + 800,
        )

        van_ban = self._goi(prompt)
        du_lieu = self._boc_json(van_ban, requirement.program)

        return ToolProposal(
            name=str(du_lieu.get("name") or requirement.program),
            description=str(du_lieu.get("description", "")),
            # Pack đã khai ràng buộc thì lấy theo pack: đề xuất của mô hình là
            # tri thức tra cứu, còn pack là tài liệu thiết kế đã qua G1.
            min_version=_chuan_hoa_phien_ban(requirement.min_version)
            or str(du_lieu.get("min_version", "")),
            check=tuple(str(x) for x in (du_lieu.get("check") or [])),
            install={
                str(k): tuple(str(x) for x in v)
                for k, v in (du_lieu.get("install") or {}).items()
            },
            rationale=str(du_lieu.get("rationale", "")),
            homepage=str(du_lieu.get("homepage", "")),
            smoke=tuple(str(x) for x in (du_lieu.get("smoke") or [])),
            smoke_expect=str(du_lieu.get("smoke_expect", "")),
            error_regex=str(du_lieu.get("error_regex", "")),
            gates=requirement.capabilities,
            scope=f"pack:{requirement.pack}" if requirement.pack else "engine",
            proposed_by=getattr(self.llm, "model", "") or getattr(self.llm, "provider", ""),
        )

    def _goi(self, prompt: Any) -> str:
        """Gọi mô hình và lấy văn bản thô.

        Dùng ``complete()`` chứ không ``generate()``: tra cứu công cụ là câu hỏi
        văn xuôi, còn ``generate`` đòi khối ```file:`` và sẽ tính mọi phản hồi
        đúng đắn là hỏng định dạng.
        """
        from eaa.llm.base import LLMError

        try:
            if hasattr(self.llm, "complete"):
                return self.llm.complete(prompt)
            return self.llm.generate(prompt).raw_response
        except LLMError as exc:
            raise ToolSearchError(f"Không tra cứu được: {exc}") from exc

    @staticmethod
    def _boc_json(van_ban: str, ten: str) -> dict[str, Any]:
        khop = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", van_ban, re.DOTALL)
        thô = khop.group(1) if khop else van_ban[van_ban.find("{") : van_ban.rfind("}") + 1]
        if not thô.strip():
            raise ToolSearchError(
                f"Tra cứu {ten!r} không trả về khối JSON nào. Đề xuất bị bỏ, "
                "không đoán thay."
            )
        try:
            du_lieu = json.loads(thô)
        except json.JSONDecodeError as exc:
            raise ToolSearchError(
                f"Tra cứu {ten!r} trả về JSON hỏng — {exc}. Đề xuất bị bỏ."
            ) from exc
        if not isinstance(du_lieu, dict):
            raise ToolSearchError(f"Tra cứu {ten!r}: JSON không phải một đối tượng")
        return du_lieu


# --------------------------------------------------------------------------
# Ghi vào manifest — append + supersede, sau khi người duyệt
# --------------------------------------------------------------------------


def append_to_manifest(
    path: str | Path, proposal: ToolProposal, *, actor: str = ""
) -> Path:
    """Thêm một công cụ đã duyệt vào manifest.

    Append thuần túy: mục cũ trùng tên KHÔNG bị xóa mà được đánh dấu
    ``superseded_by``, đúng vòng đời của AIS §8.1 mà §9.1 nói manifest cũng
    phải theo. Nhờ vậy câu "hôm trước manifest ghi phiên bản nào" luôn tra được.
    """
    path = Path(path)
    du_lieu: dict[str, Any] = {"scope": proposal.scope, "tools": []}
    if path.is_file():
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or du_lieu
        except yaml.YAMLError as exc:
            raise ToolSearchError(f"{path}: YAML không hợp lệ — {exc}") from exc
    du_lieu.setdefault("tools", [])

    muc_moi = proposal.to_manifest_entry()
    muc_moi["approved_by"] = actor
    muc_moi["approved_at"] = _now()

    for muc in du_lieu["tools"]:
        if isinstance(muc, dict) and muc.get("name") == proposal.name and not muc.get("superseded_by"):
            muc["superseded_by"] = f"{proposal.name}@{muc_moi['approved_at']}"
            muc["level"] = "Optional"   # bản cũ không còn là điều kiện bắt buộc

    du_lieu["tools"].append(muc_moi)

    path.parent.mkdir(parents=True, exist_ok=True)
    tam = path.with_suffix(path.suffix + ".tmp")
    tam.write_text(
        "# Tool Manifest — bồi dần qua gate, KHÔNG chép sẵn.\n"
        "#\n"
        "# Mỗi mục ở đây là một công cụ đã được người duyệt: biết tên, biết cách\n"
        "# kiểm phiên bản, biết cách cài. Nhu cầu công cụ thì suy ra từ pack.yaml\n"
        "# chứ không khai báo ở đây (AIS §9.1, §9.2).\n\n"
        + yaml.safe_dump(du_lieu, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    import os as _os

    _os.replace(tam, path)
    return path
