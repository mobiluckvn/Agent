"""Tự động phát hiện, tìm và chuẩn bị công cụ — ``eaa doctor``.

EAA-AIS-05 §9, quy trình P10; FR-ENV-01..05; TC-34, TC-35, TC-36, TC-37.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-17.

Lý do tồn tại, nguyên văn AIS §9: "Thiếu hoặc lệch phiên bản bất kỳ mắt xích
nào thì cổng kiểm chứng thành vô nghĩa." Cả kiến trúc này dựa trên việc mã đi
qua một chuỗi cổng; nếu một cổng lặng lẽ không chạy vì máy thiếu công cụ, thì
mọi kết luận phía sau đều rỗng — mà nó vẫn trông y hệt như khi mọi thứ đều đạt.

Bốn tính chất, và cả bốn đều là điều kiện an toàn chứ không phải tiện nghi:

1.  **Manifest là DỮ LIỆU** (``tools.yaml``), chia phần chung của engine và
    phần theo Platform Pack. Cài pack nào thì quét thêm phần của pack đó.
2.  **Không bao giờ tự cài.** ``--fix`` sinh sẵn lệnh, HIỂN THỊ NGUYÊN VĂN, rồi
    dừng chờ người xác nhận — kể cả trong phiên chạy tự động (FR-ENV-02).
3.  **Checksum sai là từ chối**, không phải cảnh báo rồi vẫn chạy (TC-35).
4.  **Khóa môi trường** (``env_lock.json``): mỗi bản build và mỗi dòng chỉ số
    gắn ``env_hash``. Toolchain trôi phiên bản phá hỏng so sánh A/B y như mô
    hình trôi phiên bản, nên câu "hôm qua build được mà hôm nay không" phải
    trả lời được bằng cách so hai băm (TC-36).

Sau khi cài xong, doctor chạy smoke test rồi ghi **Thẻ công cụ** vào
``tools_kb/``: cú pháp gọi đã được chứng minh chạy được trên chính máy này, và
quy tắc đọc kết quả. Các adapter đọc thẻ thay vì hard-code, nên đổi phiên bản
công cụ chỉ là cập nhật thẻ (FR-ENV-05, TC-37).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "DoctorError",
    "ChecksumMismatch",
    "InstallNotConfirmed",
    "InstallApproval",
    "InstallApprovals",
    "ToolStatus",
    "ToolSpec",
    "ToolManifest",
    "ToolReport",
    "EnvLock",
    "ToolCard",
    "Doctor",
]


class ToolStatus:
    OK = "OK"
    MISSING = "THIẾU"
    OUTDATED = "QUÁ CŨ"
    UNKNOWN = "KHÔNG RÕ"


class DoctorError(Exception):
    """Lỗi khi quét hoặc chuẩn bị môi trường công cụ."""


class ChecksumMismatch(DoctorError):
    """Gói tải về không khớp checksum khai báo — TC-35."""


class InstallNotConfirmed(DoctorError):
    """Cài đặt được yêu cầu mà chưa có xác nhận của người — FR-ENV-02.

    Mang theo ``nhat_ky``: phần việc đã ghi trước lúc dừng. Dừng vì không có
    người thì người ấy, khi quay lại, cần đọc được mình sắp phải duyệt cái gì —
    vứt nhật ký đi là bắt họ chạy lại từ đầu để biết.
    """

    def __init__(self, message: str, nhat_ky: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.nhat_ky: list[str] = list(nhat_ky)


def _chuan_hoa(commands: Any) -> tuple[tuple[str, ...], ...]:
    """Nhận một lệnh hoặc một DÃY lệnh, trả về dãy — một dạng duy nhất.

    Chấp cả hai vì chỗ gọi có cả hai; nhưng lưu và băm thì chỉ một dạng, nếu
    không thì cùng một thứ có hai băm và phép so trở nên vô nghĩa.
    """
    muc = list(commands or [])
    if muc and all(isinstance(x, (str, bytes)) for x in muc):
        return (tuple(str(x) for x in muc),)
    return tuple(tuple(str(x) for x in lenh) for lenh in muc)


#: Số dòng cuối của đầu ra lệnh cài được giữ lại trong nhật ký.
#:
#: Giữ phần CUỐI vì lỗi nằm ở đó — đầu ra của trình quản lý gói mở màn bằng
#: hàng chục dòng tải về rồi mới tới câu nói thật.
SO_DONG_LOI = 12


def _loi_cua_lenh(ket_qua: Any) -> list[str]:
    """Đầu ra thật của lệnh vừa trượt, thụt vào cho dễ đọc.

    Không có nó thì nhật ký chỉ có ``mã 1`` — một con số, không phải một chẩn
    đoán. Người đọc không phân biệt nổi *mạng hỏng* với *sai tên gói*, mà hai
    chuyện ấy dẫn tới hai việc khác hẳn: một bên thử lại, một bên sửa manifest.
    Thông tin đã nằm sẵn trong tay (``capture_output=True`` bắt được nó); vứt
    đi là bỏ thông tin IM LẶNG — đúng lỗi SL-100 ở một module khác.
    """
    ra = ((getattr(ket_qua, "stderr", "") or "") + "\n"
          + (getattr(ket_qua, "stdout", "") or "")).strip()
    if not ra:
        return ["      (lệnh không in ra gì)"]
    dong = [d for d in ra.splitlines() if d.strip()]
    bo = len(dong) - SO_DONG_LOI
    giu = dong[-SO_DONG_LOI:]
    kq = [f"      {d}" for d in giu]
    if bo > 0:
        kq.insert(0, f"      … bỏ {bo} dòng đầu, giữ {SO_DONG_LOI} dòng cuối")
    return kq


#: Chỗ giữ trong lệnh cài, được thay bằng đường dẫn gói ĐÃ KIỂM CHECKSUM.
CHO_GIU_GOI = "{tai_ve}"


def _tai_ve(url: str, dich: "Path") -> None:
    """Tải một tệp về đĩa. Tách riêng để bài kiểm thay được mà không ra mạng."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=900) as nguon, open(dich, "wb") as f:
        shutil.copyfileobj(nguon, f)


def _bam_lenh(commands: Any) -> str:
    """Băm ĐÚNG dãy đối số sẽ chạy — không băm chuỗi hiển thị.

    Băm chuỗi đã nối thì ``["brew", "install", "a b"]`` và
    ``["brew", "install", "a", "b"]`` cho cùng một băm, mà đó là hai lệnh khác
    nhau. Chỗ này canh ranh giới giữa cái người đã duyệt và cái máy sắp chạy,
    nên nó phải phân biệt được đúng những gì hệ điều hành phân biệt.

    Băm CẢ DÃY chứ không riêng lệnh cuối: thứ người duyệt phải là đúng thứ máy
    chạy, kể cả những bước chuẩn bị chạy trước nó.
    """
    noi_dung = json.dumps([list(c) for c in _chuan_hoa(commands)], ensure_ascii=False)
    return "sha256:" + hashlib.sha256(noi_dung.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InstallApproval:
    """Một người đã duyệt MỘT lệnh cài cụ thể."""

    tool: str
    #: TOÀN BỘ dãy lệnh đã duyệt, đúng thứ tự sẽ chạy.
    commands: tuple[tuple[str, ...], ...]
    command_digest: str
    actor: str
    approved_at: str

    @property
    def nguyen_van(self) -> str:
        return " && ".join(" ".join(c) for c in self.commands)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "commands": [list(c) for c in self.commands],
            "command_digest": self.command_digest,
            "actor": self.actor,
            "approved_at": self.approved_at,
        }


class InstallApprovals:
    """Sổ duyệt lệnh cài — nối tiếp, không ghi đè (cùng luật với mọi kho khác).

    Vì sao cần một sổ thay vì một câu hỏi trên terminal
    ----------------------------------------------------

    Human Gate đã trả lời câu này rồi: một quyết định của người phải **ghi lại
    được**, để nó tồn tại ngoài phiên chạy đã sinh ra nó. Nhờ thế
    ``confirm_interactive`` gặp phiên không terminal còn nêu được lối đi tiếp —
    ``eaa gate approve <G>`` — thay vì dừng vào ngõ cụt.

    Cổng cài trước đây chỉ có câu hỏi trên terminal. Hệ quả không phải là an
    toàn hơn, mà là **không dùng được**: mọi phiên làm việc qua người trung
    gian, qua chat, qua CI đều cụt đường, dù người có đồng ý bao nhiêu lần.

    Bất biến không đổi một ly: không lệnh cài nào chạy mà thiếu một người duyệt
    ĐÚNG lệnh ấy. Cái đổi là ai gõ phím lúc chạy.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def approve(self, tool: str, command: Sequence[str], *, by: str) -> InstallApproval:
        if not by.strip():
            raise DoctorError(
                "Phải ghi ai duyệt lệnh cài — một quyết định không có người "
                "chịu trách nhiệm thì không phải quyết định của con người "
                "(FR-GATE-01, FR-ENV-02)."
            )
        lenh = _chuan_hoa(command)
        k = InstallApproval(
            tool=tool,
            commands=lenh,
            command_digest=_bam_lenh(lenh),
            actor=by.strip(),
            approved_at=_now(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(k.to_dict(), ensure_ascii=False) + "\n")
        return k

    def all(self) -> list[InstallApproval]:
        """Đọc cả sổ. Dòng hỏng thì BỎ QUA — hỏng chỉ được đọc thành 'chưa duyệt'."""
        if not self.path.is_file():
            return []
        ra: list[InstallApproval] = []
        for dong in self.path.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong:
                continue
            try:
                d = json.loads(dong)
                ra.append(InstallApproval(
                    tool=str(d["tool"]),
                    commands=_chuan_hoa(d["commands"]),
                    command_digest=str(d["command_digest"]),
                    actor=str(d["actor"]),
                    approved_at=str(d.get("approved_at", "")),
                ))
            except (ValueError, KeyError, TypeError):
                continue
        return ra

    def find(self, tool: str, command: Sequence[str]) -> InstallApproval | None:
        """Có ai duyệt ĐÚNG lệnh này cho ĐÚNG công cụ này chưa.

        So bằng băm chứ không bằng tên công cụ. Không có tính chất này thì
        "duyệt cài X rồi cài Y" là một đường vòng hợp lệ về mặt kỹ thuật: chỉ
        cần manifest đổi giữa lúc duyệt và lúc chạy — mà manifest là dữ liệu,
        và dữ liệu thì đổi được, kể cả bởi một đề xuất công cụ mới.
        """
        bam = _bam_lenh(command)
        for k in self.all():
            if k.tool == tool and k.command_digest == bam:
                return k
        return None


def _khong_co_ai(cho_duyet: Sequence[tuple[str, str]]) -> str:
    """Câu nói cho trường hợp không có người ở terminal — kèm LỐI ĐI TIẾP.

    Một cổng dừng mà không nói đi đâu tiếp thì không phải cổng, mà là ngõ cụt.
    Human Gate nêu đích danh ``eaa gate approve <G>``; chỗ này nêu câu tương
    đương của nó.
    """
    dong = ["Cần người duyệt trước khi cài. Các lệnh sẽ chạy:"]
    dong += [f"    {ten}:  {lenh}" for ten, lenh in cho_duyet]
    dong += [
        "",
        "Phiên này không có ai ở terminal để hỏi. Doctor KHÔNG bao giờ tự cài "
        "khi chưa có người duyệt đúng lệnh, kể cả trong phiên chạy tự động "
        "(FR-ENV-02).",
        "",
        "Bạn duyệt bằng lệnh sau, rồi chạy lại 'eaa doctor --fix' — tôi sẽ cài:",
        "    eaa doctor approve " + " ".join(ten for ten, _ in cho_duyet)
        + " --actor <tên bạn>",
    ]
    return "\n".join(dong)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_argv(argv: Sequence[str]) -> list[str]:
    """Thay chỗ giữ trong lệnh kiểm tra.

    ``{python}`` trỏ tới trình thông dịch ĐANG CHẠY engine, không phải cái đầu
    tiên gặp trong PATH. Kiểm nhầm cái trong PATH sẽ báo "quá cũ" cho một môi
    trường hoàn toàn dùng được — hoặc tệ hơn, báo "đạt" cho một trình thông
    dịch mà cổng kiểm thử đơn vị không hề dùng tới.
    """
    return [sys.executable if x == "{python}" else x for x in argv]


def _os_key() -> str:
    return {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
        platform.system(), platform.system().lower()
    )


def _parse_version(van_ban: str) -> tuple[int, ...]:
    """Nhặt bộ số phiên bản đầu tiên trong một chuỗi bất kỳ."""
    khop = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", van_ban)
    if not khop:
        return ()
    return tuple(int(g) for g in khop.groups() if g is not None)


def _compare(hien_tai: str, toi_thieu: str) -> bool:
    """So phiên bản theo semver, thiếu thành phần thì coi là 0."""
    a, b = _parse_version(hien_tai), _parse_version(toi_thieu)
    if not a or not b:
        return True  # không đọc được thì không kết luận là quá cũ
    do_dai = max(len(a), len(b))
    a += (0,) * (do_dai - len(a))
    b += (0,) * (do_dai - len(b))
    return a >= b


@dataclass(frozen=True)
class ToolSpec:
    """Khai báo một công cụ trong manifest."""

    name: str
    check: tuple[str, ...]
    min_version: str = ""
    required: bool = True
    #: Cổng kiểm chứng bị chặn nếu thiếu công cụ này — dùng để báo cáo hậu quả.
    gates: tuple[str, ...] = ()
    #: Lệnh cài theo hệ điều hành, ví dụ ``{"macos": ["brew", "install", "x"]}``.
    install: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Lệnh phải chạy TRƯỚC lệnh cài, theo hệ điều hành. Thường là thêm một kho
    #: gói ngoài.
    #:
    #: Không có trường này thì mọi công cụ chỉ cài được bằng một lệnh duy nhất,
    #: và mục manifest của những công cụ cần hai bước trở thành một khẳng định
    #: SAI: nó bảo "cài bằng lệnh này", mà lệnh ấy chưa từng chạy được lần nào
    #: trên hệ đó. Sai im lặng, vì chỉ lộ ra lúc thật sự đi cài.
    pre_install: dict[str, tuple[tuple[str, ...], ...]] = field(default_factory=dict)
    #: Checksum bắt buộc khi phải tải trực tiếp.
    checksum: str = ""
    download: str = ""
    #: Lệnh smoke test sau khi cài, và chuỗi phải có trong đầu ra.
    smoke: tuple[str, ...] = ()
    smoke_expect: str = ""
    #: Quy tắc đọc kết quả, ghi vào Thẻ công cụ.
    version_regex: str = r"(\d+\.\d+(?:\.\d+)?)"
    error_regex: str = ""
    scope: str = "engine"   # engine · pack:<tên>
    note: str = ""
    #: Cách cài — xem ``eaa/installplan.py``. Mặc định là trình quản lý gói.
    method: str = "gói"
    #: Công cụ khác phải có TRƯỚC, kèm ràng buộc phiên bản:
    #: ``{"libusb": ">=1.0"}``. Dùng cho hai việc: sắp thứ tự cài, và phát hiện
    #: hai thẻ cùng đòi một thứ ở hai phiên bản đá nhau (SL-90).
    requires: dict[str, str] = field(default_factory=dict)
    #: Công cụ thay thế được, khi cái này không cài nổi.
    alternatives: tuple[str, ...] = ()


@dataclass
class ToolReport:
    """Kết quả quét một công cụ."""

    spec: ToolSpec
    status: str
    version: str = ""
    path: str = ""
    detail: str = ""

    @property
    def blocking(self) -> bool:
        return self.spec.required and self.status in (ToolStatus.MISSING, ToolStatus.OUTDATED)


class ToolManifest:
    """``tools.yaml`` — danh mục công cụ, là dữ liệu chứ không phải mã cứng."""

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self.specs = list(specs)

    @classmethod
    def load(cls, *paths: str | Path, pack: str = "") -> "ToolManifest":
        """Nạp một hoặc nhiều tệp manifest và gộp lại.

        Phần CHUNG thuộc engine, phần THEO PACK đến từ Platform Pack — cài pack
        nào thì quét thêm phần của pack đó (AIS §9.1). Manifest của pack ghi đè
        mục trùng tên, để một pack nói được "trên nền tảng này công cụ ấy phải
        là bản khác".
        """
        theo_ten: dict[str, ToolSpec] = {}
        for path in paths:
            path = Path(path)
            if not path.is_file():
                continue
            try:
                du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise DoctorError(f"{path}: YAML không hợp lệ — {exc}") from exc

            pham_vi = str(du_lieu.get("scope", "engine"))
            for muc in du_lieu.get("tools") or []:
                spec = cls._parse(muc, path, pham_vi)
                theo_ten[spec.name] = spec

        if pack:
            theo_ten = {
                k: v
                for k, v in theo_ten.items()
                if v.scope == "engine" or v.scope == f"pack:{pack}"
            }
        return cls(sorted(theo_ten.values(), key=lambda s: (s.scope, s.name)))

    @staticmethod
    def _parse(muc: Any, path: Path, pham_vi: str) -> ToolSpec:
        if not isinstance(muc, dict) or not muc.get("name"):
            raise DoctorError(f"{path}: có mục công cụ thiếu 'name'")
        check = muc.get("check")
        if not isinstance(check, list) or not check:
            raise DoctorError(
                f"{path}: công cụ {muc['name']!r} thiếu 'check' dạng danh sách argv. "
                "Không chạy qua shell."
            )
        return ToolSpec(
            name=str(muc["name"]),
            check=tuple(str(x) for x in check),
            min_version=str(muc.get("min_version", "")),
            required=str(muc.get("level", "Must")).lower() != "optional",
            gates=tuple(str(g) for g in (muc.get("gates") or [])),
            install={
                str(k): tuple(str(x) for x in v)
                for k, v in (muc.get("install") or {}).items()
            },
            pre_install={
                str(k): tuple(tuple(str(x) for x in lenh) for lenh in (v or []))
                for k, v in (muc.get("pre_install") or {}).items()
            },
            checksum=str(muc.get("checksum", "")),
            download=str(muc.get("download", "")),
            smoke=tuple(str(x) for x in (muc.get("smoke") or [])),
            smoke_expect=str(muc.get("smoke_expect", "")),
            version_regex=str(muc.get("version_regex", r"(\d+\.\d+(?:\.\d+)?)")),
            error_regex=str(muc.get("error_regex", "")),
            scope=str(muc.get("scope", pham_vi)),
            note=str(muc.get("note", "")),
            method=str(muc.get("method", "") or "gói"),
            requires={
                str(k): str(v) for k, v in (muc.get("requires") or {}).items()
            },
            alternatives=tuple(str(x) for x in (muc.get("alternatives") or [])),
        )

    def get(self, name: str) -> ToolSpec:
        for s in self.specs:
            if s.name == name:
                return s
        raise DoctorError(f"Công cụ {name!r} không có trong manifest")


class EnvLock:
    """``env_lock.json`` — chống trôi phiên bản toolchain (FR-ENV-04)."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DoctorError(f"{self.path}: JSON hỏng — {exc}") from exc

    @staticmethod
    def compute_hash(versions: dict[str, str], os_key: str) -> str:
        noi_dung = json.dumps(
            {"os": os_key, "tools": dict(sorted(versions.items()))}, sort_keys=True
        )
        return "sha256:" + hashlib.sha256(noi_dung.encode("utf-8")).hexdigest()

    def write(self, versions: dict[str, str]) -> dict[str, Any]:
        du_lieu = {
            "os": _os_key(),
            "tools": dict(sorted(versions.items())),
            "env_hash": self.compute_hash(versions, _os_key()),
            "locked_at": _now(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tam = self.path.with_suffix(".json.tmp")
        tam.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tam, self.path)
        return du_lieu

    def drift(self, versions: dict[str, str]) -> dict[str, tuple[str, str]]:
        """So môi trường hiện tại với bản khóa — trả về những chỗ lệch.

        Đây là thứ trả lời câu "hôm qua build được mà hôm nay không" bằng một
        phép so hai băm, thay vì bằng một buổi chiều mò mẫm.
        """
        khoa = self.read().get("tools", {})
        lech: dict[str, tuple[str, str]] = {}
        for ten, hien_tai in versions.items():
            cu = khoa.get(ten)
            if cu is not None and cu != hien_tai:
                lech[ten] = (cu, hien_tai)
        for ten, cu in khoa.items():
            if ten not in versions:
                lech[ten] = (cu, "(không còn)")
        return lech


@dataclass
class ToolCard:
    """Thẻ công cụ — bộ nhớ về CÁCH DÙNG một công cụ trên chính máy này.

    AIS §9.5: cài xong chưa phải là xong; Agent phải biết công cụ đã có VÀ biết
    cách gọi nó. Cú pháp trong thẻ là cú pháp đã được smoke test chứng minh
    chạy được ở đây — khác hẳn một dòng ví dụ chép từ tài liệu.
    """

    name: str
    version: str
    executable: str
    gates: tuple[str, ...]
    invocation: tuple[str, ...]
    version_regex: str
    error_regex: str
    verified_at: str
    os: str
    smoke_output: str = ""
    known_issues: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "executable": self.executable,
            "gates": list(self.gates),
            "invocation": list(self.invocation),
            "version_regex": self.version_regex,
            "error_regex": self.error_regex,
            "verified_at": self.verified_at,
            "os": self.os,
            "smoke_output": self.smoke_output[:2000],
            "known_issues": self.known_issues,
        }

    def compact(self) -> str:
        """Một dòng để nạp vào ngữ cảnh khi Agent cần sinh lệnh (AIS §9.5)."""
        return (
            f"{self.name} {self.version} tại {self.executable}; "
            f"gọi: {' '.join(self.invocation)}"
        )

    @classmethod
    def load(cls, path: str | Path) -> "ToolCard":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=d["name"],
            version=d.get("version", ""),
            executable=d.get("executable", ""),
            gates=tuple(d.get("gates", ())),
            invocation=tuple(d.get("invocation", ())),
            version_regex=d.get("version_regex", ""),
            error_regex=d.get("error_regex", ""),
            verified_at=d.get("verified_at", ""),
            os=d.get("os", ""),
            smoke_output=d.get("smoke_output", ""),
            known_issues=list(d.get("known_issues", [])),
        )


@dataclass
class Doctor:
    """Ba chế độ của ``eaa doctor`` — AIS §9.2."""

    manifest: ToolManifest
    tools_kb: Path
    env_lock: EnvLock
    #: Hàm hỏi người: nhận mô tả lệnh, trả True nếu người đồng ý.
    #: Mặc định ``None`` nghĩa là KHÔNG CÓ AI — và không có ai thì không cài.
    confirm: Any = None
    #: Manifest của Platform Pack — NGUỒN của nhu cầu công cụ (AIS §9.2 chế độ 3).
    #: Không có nó thì doctor chỉ kiểm được những gì đã biết, và không bao giờ
    #: phát hiện ra thứ nó chưa biết.
    pack_manifest: Any = None
    #: Bộ tra cứu công cụ chưa biết; ``None`` thì chỉ phát hiện chứ không đề xuất.
    researcher: Any = None
    #: Sổ duyệt lệnh cài. ``None`` nghĩa là KHÔNG CÓ SỔ — và không có sổ thì
    #: đường "người duyệt ngoài luồng, Agent chạy" đóng lại, chỉ còn hỏi tại
    #: terminal. Cố ý mặc định như vậy: mở đường phải là một hành động rõ ràng.
    approvals: Any = None

    def __post_init__(self) -> None:
        self.tools_kb = Path(self.tools_kb)

    # ----------------------------------------------------------------------
    # Chế độ 1 — quét (chỉ đọc, không đổi gì trên máy)
    # ----------------------------------------------------------------------

    def scan(self) -> list[ToolReport]:
        return [self._check_one(spec) for spec in self.manifest.specs]

    def _check_one(self, spec: ToolSpec) -> ToolReport:
        lenh = _resolve_argv(spec.check)
        chuong_trinh = lenh[0]
        duong_dan = chuong_trinh if Path(chuong_trinh).is_file() else shutil.which(chuong_trinh)
        if duong_dan is None:
            return ToolReport(
                spec=spec,
                status=ToolStatus.MISSING,
                detail=f"không tìm thấy {chuong_trinh!r} trong PATH",
            )

        try:
            ket_qua = subprocess.run(
                lenh,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                shell=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return ToolReport(
                spec=spec,
                status=ToolStatus.UNKNOWN,
                path=duong_dan,
                detail=f"lệnh kiểm tra không chạy được: {exc}",
            )

        dau_ra = (ket_qua.stdout or "") + (ket_qua.stderr or "")
        khop = re.search(spec.version_regex, dau_ra)
        phien_ban = khop.group(1) if khop else ""

        if spec.min_version and phien_ban and not _compare(phien_ban, spec.min_version):
            return ToolReport(
                spec=spec,
                status=ToolStatus.OUTDATED,
                version=phien_ban,
                path=duong_dan,
                detail=f"cần ≥ {spec.min_version}, đang có {phien_ban}",
            )

        return ToolReport(
            spec=spec,
            status=ToolStatus.OK if phien_ban else ToolStatus.UNKNOWN,
            version=phien_ban,
            path=duong_dan,
            detail="" if phien_ban else "không đọc được phiên bản từ đầu ra",
        )

    # ----------------------------------------------------------------------
    # Chế độ 3 — phát hiện và tra cứu công cụ chưa biết (AIS §9.2)
    # ----------------------------------------------------------------------

    def discover(self) -> list[Any]:
        """Công cụ pack SẼ GỌI mà manifest chưa biết gì.

        Nhu cầu suy từ ``pack.yaml``, không từ một danh sách chép tay. Một danh
        sách chép tay lệch khỏi pack ngay lần đầu pack đổi lệnh, và lệch theo
        hướng nguy hiểm: doctor báo "đủ công cụ" trong khi cổng kiểm chứng sắp
        gọi một chương trình không có trên máy.
        """
        from eaa.toolsearch import derive_requirements

        if self.pack_manifest is None:
            return []
        da_biet = {s.name for s in self.manifest.specs}
        return [
            yc
            for yc in derive_requirements(self.pack_manifest)
            if yc.program not in da_biet
        ]

    def research(self, requirement: Any) -> Any:
        """Tra cứu một công cụ chưa biết và trả về đề xuất ĐÃ QUA KIỂM AN TOÀN."""
        from eaa.toolsearch import ToolSearchError, validate_proposal

        if self.researcher is None:
            # Thông báo phải là LỆNH GÕ ĐƯỢC. Mô tả nội tình engine ("chọn
            # provider trong Project State") bắt người dùng phải biết kiến trúc
            # bên trong mới dùng được sản phẩm — và họ không có nghĩa vụ ấy.
            from eaa.llm.base import KEY_ENV

            import os as _os

            if _os.environ.get(KEY_ENV, "").strip():
                huong_dan = (
                    f"Máy CÓ {KEY_ENV}, nhưng dự án này đang chạy adapter giả lập.\n"
                    "    Chuyển sang mô hình thật:  eaa init --force"
                )
            else:
                huong_dan = (
                    f"Chưa có {KEY_ENV}. Đặt khóa vào tệp .env ở gốc kho, rồi:\n"
                    "        eaa init --force"
                )
            raise DoctorError(
                f"Cần tra cứu {requirement.program!r} nhưng dự án chưa nối với mô "
                f"hình nền.\n    {huong_dan}"
            )
        return validate_proposal(self.researcher.propose(requirement, os_key=_os_key()))

    def render_discovery(self, requirements: Sequence[Any]) -> str:
        if not requirements:
            return (
                "Mọi chương trình mà Platform Pack sẽ gọi đều đã có trong manifest."
            )
        dong = [
            f"{len(requirements)} chương trình pack sẽ gọi mà manifest CHƯA BIẾT:",
            "",
        ]
        # Bề rộng cột theo tên DÀI NHẤT thay vì một hằng số: pack thứ hai có
        # tên công cụ dài gấp đôi pack thứ nhất, và một cột cứng thì dính chữ.
        rong = max(14, *(len(yc.program) for yc in requirements)) + 2
        for yc in requirements:
            trang_thai = "đã có trên máy" if yc.present else "chưa có trên máy"
            dong.append(
                f"  {yc.program:<{rong}}{trang_thai:<20}phục vụ: {', '.join(yc.capabilities)}"
            )
        dong += [
            "",
            "Manifest chỉ ghi những công cụ ĐÃ được người duyệt, nên chưa biết ở",
            "đây không có nghĩa là thiếu — nghĩa là chưa ai xác nhận cách kiểm và",
            "cách cài nó. Tra cứu và đề xuất:",
            "  eaa doctor --discover --propose",
        ]
        return "\n".join(dong)

    def render_scan(self, reports: Sequence[ToolReport]) -> str:
        # Bề rộng cột theo tên dài nhất — cùng lý do với render_discovery: tên
        # công cụ của pack thứ hai dài gấp đôi pack thứ nhất, và một cột cứng
        # thì dính chữ ngay ở dòng đầu.
        rong = max(16, *(len(r.spec.name) for r in reports)) + 2 if reports else 16
        dong = [f"{'công cụ':<{rong}}{'trạng thái':<12}{'phiên bản':<12}chi tiết"]
        dong.append("─" * max(78, rong + 40))
        for r in reports:
            dong.append(
                f"{r.spec.name:<{rong}}{r.status:<12}{r.version or '—':<12}{r.detail}"
            )
            if r.blocking and r.spec.gates:
                dong.append(f"    → chặn cổng: {', '.join(r.spec.gates)}")

        chan = [r for r in reports if r.blocking]
        dong.append("")
        if chan:
            dong.append(
                f"{len(chan)} công cụ bắt buộc chưa sẵn sàng. Các cổng chúng phục vụ "
                "KHÔNG được coi là đạt cho tới khi khắc phục — chạy 'eaa doctor --fix'."
            )
        else:
            dong.append("Mọi công cụ bắt buộc đã sẵn sàng.")
        return "\n".join(dong)

    # ----------------------------------------------------------------------
    # Chế độ 2 — sửa (luôn cần người xác nhận)
    # ----------------------------------------------------------------------

    def install_command(self, spec: ToolSpec) -> tuple[str, ...]:
        he_dieu_hanh = _os_key()
        lenh = spec.install.get(he_dieu_hanh)
        if not lenh:
            raise DoctorError(
                f"Manifest không có lệnh cài {spec.name!r} cho {he_dieu_hanh}. "
                f"Cài tay theo hướng dẫn của nhà phát hành rồi chạy lại 'eaa doctor'."
            )
        return lenh

    def install_steps(self, spec: ToolSpec) -> list[tuple[str, ...]]:
        """TOÀN BỘ dãy lệnh sẽ chạy để cài công cụ này, đúng thứ tự.

        Đây — chứ không phải riêng lệnh cài — mới là thứ người duyệt và thứ máy
        chạy. Hai cái ấy phải là **cùng một vật**: quyết định neo vào một lệnh
        trong khi thứ chạy là một dãy thì chèn thêm một bước vào trước là chèn
        được mã tùy ý sau lưng người duyệt, mà quyết định cũ vẫn trông hợp lệ.
        """
        return [*spec.pre_install.get(_os_key(), ()), self.install_command(spec)]

    def fix(self, reports: Sequence[ToolReport], *, dry_run: bool = False) -> list[str]:
        """Sinh lệnh cài, hiển thị nguyên văn, và CHỜ XÁC NHẬN từng lệnh.

        ``dry_run`` chỉ in ra chứ không hỏi và không chạy. Không có chế độ nào
        chạy mà không hỏi: cài đặt là thay đổi máy của kỹ sư (FR-ENV-02, §9.4).

        Ba đường tới chỗ chạy, và chỉ ba:

        1.  **Đã có trong sổ duyệt** một người duyệt ĐÚNG lệnh này — chạy. Đây
            là đường của phiên không terminal, và là đường Agent đi.
        2.  **Có người ở terminal** và người ấy trả lời đồng ý — chạy.
        3.  Không có đường nào khác.

        Không có ai để hỏi thì gom ĐỦ danh sách rồi mới dừng, kèm lệnh duyệt.
        Dừng ngay ở cái đầu tiên bắt người duyệt xong lại chạy lại để biết cái
        thứ hai — mỗi lượt một tin, và họ không bao giờ thấy toàn cảnh việc
        mình đang đồng ý.
        """
        nhat_ky: list[str] = []
        cho_duyet: list[tuple[str, str]] = []
        for r in reports:
            if not r.blocking:
                continue
            try:
                lenh = self.install_steps(r.spec)
            except DoctorError as exc:
                nhat_ky.append(f"{r.spec.name}: {exc}")
                continue

            nguyen_van = " && ".join(" ".join(b) for b in lenh)
            nhat_ky.append(f"{r.spec.name}: sẽ chạy → {nguyen_van}")
            if dry_run:
                continue

            if r.spec.download:
                # Nói SẼ làm gì, không nói ĐÃ làm gì. Việc kiểm thật nằm trong
                # `_run_install`, và nó ghi dòng "checksum KHỚP" của chính nó.
                nhat_ky.append(
                    f"{r.spec.name}: sẽ tải {r.spec.download} và bắt buộc khớp "
                    "checksum trước khi chạy lệnh nào"
                )

            da_duyet = (
                self.approvals.find(r.spec.name, lenh)
                if self.approvals is not None else None
            )
            if da_duyet is not None:
                nhat_ky.append(
                    f"{r.spec.name}: {da_duyet.actor} đã duyệt đúng lệnh này "
                    f"lúc {da_duyet.approved_at} — chạy"
                )
                nhat_ky.extend(self._run_install(r.spec, lenh))
                continue

            if self.confirm is None:
                cho_duyet.append((r.spec.name, nguyen_van))
                continue

            # Ba trạng thái, và gộp hai cái sau lại là nói sai về lý do dừng:
            #   True  — người đồng ý
            #   False — người từ chối
            #   None  — KHÔNG CÓ AI để hỏi (phiên không terminal, chạy tự động)
            tra_loi = self.confirm(r.spec.name, nguyen_van)
            if tra_loi is None:
                cho_duyet.append((r.spec.name, nguyen_van))
                continue
            if not tra_loi:
                nhat_ky.append(f"{r.spec.name}: người dùng từ chối, bỏ qua")
                continue

            nhat_ky.extend(self._run_install(r.spec, lenh))

        if cho_duyet:
            raise InstallNotConfirmed(_khong_co_ai(cho_duyet), nhat_ky)
        return nhat_ky

    def _run_install(self, spec: ToolSpec, commands: Any) -> list[str]:
        """Chạy dãy lệnh cài. Trượt bước nào thì DỪNG ở đó và nói vì sao.

        Dừng sớm là bắt buộc: bước chuẩn bị (thêm kho gói) trượt thì lệnh cài
        sau nó chắc chắn trượt theo, và chạy tiếp chỉ thêm một thông báo lỗi
        thứ hai che mất lỗi thật.
        """
        nhat_ky: list[str] = []
        day = _chuan_hoa(commands)

        # Gói tải trực tiếp: TẢI, TÍNH BĂM, ĐỐI CHIẾU — trước khi chạy bất cứ
        # lệnh nào. Trước SL-113 chỗ này chỉ in ra một dòng nhật ký khẳng định
        # việc ấy đã xảy ra, còn `verify_checksum` thì không ai gọi. Một lời hứa
        # an toàn in cho người đọc tin, không có gì đứng sau.
        thu_muc_tam = None
        if spec.download:
            if not spec.checksum:
                raise DoctorError(
                    f"{spec.name}: khai 'download' mà không khai 'checksum'. "
                    "Tải một gói rồi chạy nó mà không có gì đối chiếu thì tệ "
                    "hơn không tải: không ai biết mình vừa chạy mã của ai."
                )
            import tempfile

            thu_muc_tam = tempfile.mkdtemp(prefix="eaa-tai-")
            goi = Path(thu_muc_tam) / (spec.download.rsplit("/", 1)[-1] or "goi")
            nhat_ky.append(f"{spec.name}: tải {spec.download}")
            try:
                _tai_ve(spec.download, goi)
            except Exception as exc:  # noqa: BLE001 - mạng, DNS, quyền ghi…
                shutil.rmtree(thu_muc_tam, ignore_errors=True)
                nhat_ky.append(f"{spec.name}: KHÔNG tải được — {exc}")
                return nhat_ky
            try:
                bam = self.verify_checksum(goi, spec.checksum)
            except Exception:
                shutil.rmtree(thu_muc_tam, ignore_errors=True)
                raise
            nhat_ky.append(f"{spec.name}: checksum KHỚP ({bam[:23]}…)")
            day = tuple(
                tuple(str(goi) if x == CHO_GIU_GOI else x for x in lenh)
                for lenh in day
            )

        nhieu_buoc = len(day) > 1

        for chi_so, lenh in enumerate(day, start=1):
            nhan = f"{spec.name}" + (f" (bước {chi_so}/{len(day)})" if nhieu_buoc else "")
            xong = False
            for lan in range(1, 3):
                try:
                    ket_qua = subprocess.run(
                        list(lenh), capture_output=True, text=True, timeout=900, shell=False
                    )
                except (subprocess.TimeoutExpired, OSError) as exc:
                    nhat_ky.append(f"{nhan}: lần {lan} lỗi — {exc}")
                    continue

                if ket_qua.returncode == 0:
                    xong = True
                    break

                nhat_ky.append(f"{nhan}: lần {lan} thất bại (mã {ket_qua.returncode})")
                nhat_ky.extend(_loi_cua_lenh(ket_qua))

            if not xong:
                if thu_muc_tam:
                    shutil.rmtree(thu_muc_tam, ignore_errors=True)
                nhat_ky.append(
                    f"{spec.name}: cài thất bại sau 2 lần — dừng, không lặp vô hạn. "
                    "Cài tay theo hướng dẫn của nhà phát hành (§9.4)."
                )
                return nhat_ky

        if thu_muc_tam:
            shutil.rmtree(thu_muc_tam, ignore_errors=True)
        nhat_ky.append(f"{spec.name}: cài xong")
        # Quét lại xác nhận, rồi ghi Thẻ công cụ (AIS §9.5).
        bao_cao = self._check_one(spec)
        nhat_ky.append(f"{spec.name}: quét lại → {bao_cao.status} {bao_cao.version}")
        if bao_cao.status == ToolStatus.OK:
            the = self.write_tool_card(bao_cao)
            nhat_ky.append(f"{spec.name}: đã ghi Thẻ công cụ — {the.compact()}")
        return nhat_ky

    @staticmethod
    def verify_checksum(path: str | Path, expected: str) -> str:
        """Kiểm checksum gói tải trực tiếp; sai là TỪ CHỐI — TC-35."""
        path = Path(path)
        if not path.is_file():
            raise DoctorError(f"Không tìm thấy gói tải về: {path}")

        h = hashlib.sha256()
        with open(path, "rb") as f:
            for khoi in iter(lambda: f.read(65536), b""):
                h.update(khoi)
        thuc_te = "sha256:" + h.hexdigest()

        mong_doi = expected if expected.startswith("sha256:") else f"sha256:{expected}"
        if thuc_te != mong_doi:
            raise ChecksumMismatch(
                f"Checksum không khớp cho {path.name}: khai báo {mong_doi}, thực tế "
                f"{thuc_te}. TỪ CHỐI cài đặt. Gói tải về không đúng bản đã kiểm — "
                "có thể do tải hỏng, có thể do nguồn bị can thiệp; cả hai đều là "
                "lý do đủ để dừng (§9.4)."
            )
        return thuc_te

    # ----------------------------------------------------------------------
    # Thẻ công cụ và khóa môi trường
    # ----------------------------------------------------------------------

    def smoke_test(self, spec: ToolSpec) -> tuple[bool, str]:
        """Chứng minh công cụ chạy được TRÊN MÁY NÀY, không chỉ có mặt."""
        if not spec.smoke:
            return True, "(manifest không khai báo smoke test)"
        try:
            ket_qua = subprocess.run(
                _resolve_argv(spec.smoke),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                shell=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, f"smoke test không chạy được: {exc}"

        dau_ra = (ket_qua.stdout or "") + (ket_qua.stderr or "")
        if ket_qua.returncode != 0:
            return False, f"smoke test thoát mã {ket_qua.returncode}: {dau_ra[:500]}"
        if spec.smoke_expect and spec.smoke_expect not in dau_ra:
            return False, f"smoke test không có {spec.smoke_expect!r} trong đầu ra"
        return True, dau_ra

    def write_tool_card(self, report: ToolReport) -> ToolCard:
        """Ghi Thẻ công cụ sau khi smoke test đạt — FR-ENV-05, TC-37."""
        dat, dau_ra = self.smoke_test(report.spec)
        if not dat:
            raise DoctorError(
                f"{report.spec.name}: smoke test không đạt nên KHÔNG ghi Thẻ công "
                f"cụ. {dau_ra}\nMột thẻ ghi cú pháp chưa chứng minh được là một "
                "nguồn ảo giác cú pháp lệnh — đúng thứ thẻ sinh ra để ngăn."
            )

        the = ToolCard(
            name=report.spec.name,
            version=report.version,
            executable=report.path,
            gates=report.spec.gates,
            invocation=tuple(_resolve_argv(report.spec.check)),
            version_regex=report.spec.version_regex,
            error_regex=report.spec.error_regex,
            verified_at=_now(),
            os=_os_key(),
            smoke_output=dau_ra,
        )
        self.tools_kb.mkdir(parents=True, exist_ok=True)
        (self.tools_kb / f"{report.spec.name}.json").write_text(
            json.dumps(the.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return the

    def cards(self) -> list[ToolCard]:
        if not self.tools_kb.is_dir():
            return []
        return [ToolCard.load(p) for p in sorted(self.tools_kb.glob("*.json"))]

    def context_lines(self) -> list[str]:
        """Thẻ công cụ nén một dòng mỗi cái, để nạp vào ngữ cảnh (AIS §9.5)."""
        return [c.compact() for c in self.cards()]

    def lock(self, reports: Sequence[ToolReport]) -> dict[str, Any]:
        return self.env_lock.write(
            {r.spec.name: r.version for r in reports if r.version}
        )

    def check_drift(self, reports: Sequence[ToolReport]) -> dict[str, tuple[str, str]]:
        return self.env_lock.drift(
            {r.spec.name: r.version for r in reports if r.version}
        )
