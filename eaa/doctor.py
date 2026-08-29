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
    """Cài đặt được yêu cầu mà chưa có xác nhận của người — FR-ENV-02."""


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
            checksum=str(muc.get("checksum", "")),
            download=str(muc.get("download", "")),
            smoke=tuple(str(x) for x in (muc.get("smoke") or [])),
            smoke_expect=str(muc.get("smoke_expect", "")),
            version_regex=str(muc.get("version_regex", r"(\d+\.\d+(?:\.\d+)?)")),
            error_regex=str(muc.get("error_regex", "")),
            scope=str(muc.get("scope", pham_vi)),
            note=str(muc.get("note", "")),
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

    def render_scan(self, reports: Sequence[ToolReport]) -> str:
        dong = [f"{'công cụ':<16}{'trạng thái':<12}{'phiên bản':<12}chi tiết"]
        dong.append("─" * 78)
        for r in reports:
            dong.append(
                f"{r.spec.name:<16}{r.status:<12}{r.version or '—':<12}{r.detail}"
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

    def fix(self, reports: Sequence[ToolReport], *, dry_run: bool = False) -> list[str]:
        """Sinh lệnh cài, hiển thị nguyên văn, và CHỜ XÁC NHẬN từng lệnh.

        ``dry_run`` chỉ in ra chứ không hỏi và không chạy. Không có chế độ nào
        chạy mà không hỏi: cài đặt là thay đổi máy của kỹ sư (FR-ENV-02, §9.4).
        """
        nhat_ky: list[str] = []
        for r in reports:
            if not r.blocking:
                continue
            try:
                lenh = self.install_command(r.spec)
            except DoctorError as exc:
                nhat_ky.append(f"{r.spec.name}: {exc}")
                continue

            nguyen_van = " ".join(lenh)
            nhat_ky.append(f"{r.spec.name}: sẽ chạy → {nguyen_van}")
            if dry_run:
                continue

            if r.spec.download and r.spec.checksum:
                nhat_ky.append(
                    f"{r.spec.name}: tải trực tiếp từ {r.spec.download}, "
                    f"bắt buộc khớp checksum {r.spec.checksum}"
                )

            if self.confirm is None:
                raise InstallNotConfirmed(
                    f"Cần cài {r.spec.name} bằng lệnh:\n    {nguyen_van}\n"
                    "Phiên này không có ai để xác nhận. Doctor KHÔNG bao giờ tự "
                    "thực thi lệnh cài, kể cả trong phiên chạy tự động (FR-ENV-02)."
                )
            if not self.confirm(r.spec.name, nguyen_van):
                nhat_ky.append(f"{r.spec.name}: người dùng từ chối, bỏ qua")
                continue

            nhat_ky.extend(self._run_install(r.spec, lenh))

        return nhat_ky

    def _run_install(self, spec: ToolSpec, lenh: Sequence[str]) -> list[str]:
        nhat_ky: list[str] = []
        for lan in range(1, 3):
            try:
                ket_qua = subprocess.run(
                    list(lenh), capture_output=True, text=True, timeout=900, shell=False
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                nhat_ky.append(f"{spec.name}: lần {lan} lỗi — {exc}")
                continue

            if ket_qua.returncode == 0:
                nhat_ky.append(f"{spec.name}: cài xong ở lần {lan}")
                # Quét lại xác nhận, rồi ghi Thẻ công cụ (AIS §9.5).
                bao_cao = self._check_one(spec)
                nhat_ky.append(f"{spec.name}: quét lại → {bao_cao.status} {bao_cao.version}")
                if bao_cao.status == ToolStatus.OK:
                    the = self.write_tool_card(bao_cao)
                    nhat_ky.append(f"{spec.name}: đã ghi Thẻ công cụ — {the.compact()}")
                return nhat_ky

            nhat_ky.append(
                f"{spec.name}: lần {lan} thất bại (mã {ket_qua.returncode})"
            )

        nhat_ky.append(
            f"{spec.name}: cài thất bại sau 2 lần — dừng, không lặp vô hạn. "
            "Cài tay theo hướng dẫn của nhà phát hành (§9.4)."
        )
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
