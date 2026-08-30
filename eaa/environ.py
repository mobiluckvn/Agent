"""Dò môi trường — Agent biết mình đang đứng ở đâu trước khi hứa làm gì.

EAA-AIS-05 §9.1 (kiểm môi trường công cụ), FR-ENV-01; NFR-04.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-73.

Khoảng trống module này lấp
----------------------------

``eaa doctor`` biết kiểm **những công cụ đã có trong Tool Manifest**. Nó không
biết gì về cái máy đang chạy nó: kiến trúc CPU nào, có quyền quản trị không,
mạng ra ngoài có thông không, còn bao nhiêu đĩa. Hệ quả không phải lý thuyết —
một lệnh cài chép đúng từ tài liệu vẫn hỏng vì máy dùng chip ARM chứ không
phải x86, và Agent chỉ biết điều đó sau khi đã chạy và đã hỏng.

Vì sao "mạng có thông không" phải là một PHÉP ĐO
-------------------------------------------------

Kể từ khi có :mod:`eaa.web`, gần như mọi năng lực mới đều treo vào mạng: tra
tài liệu, tìm công cụ, tra lỗi cài đặt. Một Agent không biết mình có mạng hay
không sẽ trả lời "để tôi đi tra" rồi im lặng hỏng sau hai mươi giây chờ. Nên ở
đây mạng được **thử thật** bằng một lần nối TCP có hạn giờ ngắn, và kết quả
mang nhãn ĐÃ KIỂM — khác hẳn với việc đọc biến môi trường proxy rồi đoán.

Ranh giới với ``doctor``
-------------------------

Module này trả lời "máy này là máy gì"; ``doctor`` trả lời "máy này có đủ công
cụ cho pack đang dùng chưa". Hai câu khác nhau, và trộn lại thì cái sau sẽ
nuốt cái trước: người ta chạy ``doctor``, thấy xanh, rồi vẫn không hiểu vì sao
lệnh cài hỏng.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

__all__ = [
    "EnvironmentReport",
    "NetworkCheck",
    "probe",
    "TRINH_QUAN_LY_GOI",
    "HOST_KIEM_MANG",
]

#: Trình quản lý gói mà bộ cài biết dùng. Thứ tự là thứ tự ưu tiên trên máy có
#: nhiều cái cùng lúc: cái chuyên cho hệ điều hành trước, cái theo ngôn ngữ sau.
TRINH_QUAN_LY_GOI: tuple[str, ...] = (
    "brew", "apt-get", "apt", "dnf", "yum", "pacman", "zypper", "apk",
    "choco", "winget", "scoop", "port",
    "pip", "pip3", "npm", "cargo", "go", "docker",
)

#: Đích thử mạng. Cổng 443 của một máy chủ tên miền công cộng, ổn định và
#: không phải của nhà cung cấp mô hình — thử đúng cái ta cần biết (ra được
#: Internet chưa) chứ không lẫn với "khóa API còn hạn không".
HOST_KIEM_MANG = ("one.one.one.one", 443)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class NetworkCheck:
    """Kết quả thử mạng — một phép đo, không phải một suy đoán."""

    reachable: bool
    detail: str = ""
    host: str = ""
    elapsed_ms: int = 0
    skipped: bool = False

    @property
    def confidence_level(self) -> str:
        from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC

        return KHONG_KIEM_DUOC if self.skipped else DA_KIEM

    def render(self) -> str:
        if self.skipped:
            return f"  mạng ra ngoài : không thử ({self.detail})"
        dau = "✓" if self.reachable else "✗"
        return f"  mạng ra ngoài : {dau} {self.detail}  ({self.host}, {self.elapsed_ms} ms)"


@dataclass(frozen=True)
class EnvironmentReport:
    """Máy này là máy gì."""

    os_name: str = ""
    os_release: str = ""
    arch: str = ""
    python_version: str = ""
    python_path: str = ""
    is_admin: bool = False
    cpu_count: int = 0
    ram_bytes: int = 0
    disk_free_bytes: int = 0
    package_managers: tuple[str, ...] = ()
    proxy_vars: tuple[tuple[str, str], ...] = ()
    network: NetworkCheck | None = None
    probed_at: str = ""

    @property
    def confidence_level(self) -> str:
        """ĐÃ KIỂM: mọi số ở đây là kết quả đọc trực tiếp từ hệ điều hành."""
        from eaa.confidence import DA_KIEM

        return DA_KIEM

    @property
    def os_key(self) -> str:
        """Khóa hệ điều hành dùng để chọn lệnh cài — cùng bộ với ``doctor``."""
        return {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
            self.os_name, self.os_name.lower()
        )

    @property
    def online(self) -> bool:
        return bool(self.network and self.network.reachable)

    def has(self, ten: str) -> bool:
        return ten in self.package_managers

    def preferred_manager(self) -> str:
        """Trình quản lý gói nên dùng trên máy này, hoặc chuỗi rỗng."""
        for ten in TRINH_QUAN_LY_GOI:
            if ten in self.package_managers:
                return ten
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_release": self.os_release,
            "arch": self.arch,
            "python_version": self.python_version,
            "python_path": self.python_path,
            "is_admin": self.is_admin,
            "cpu_count": self.cpu_count,
            "ram_bytes": self.ram_bytes,
            "disk_free_bytes": self.disk_free_bytes,
            "package_managers": list(self.package_managers),
            "proxy_vars": [list(x) for x in self.proxy_vars],
            "online": self.online,
            "probed_at": self.probed_at,
        }

    def render(self) -> str:
        from eaa.confidence import header

        def gb(n: int) -> str:
            return f"{n / 1024**3:.1f} GB" if n else "không đọc được"

        dong = [
            "Môi trường máy này",
            "",
            header(self.confidence_level),
            "",
            f"  hệ điều hành  : {self.os_name} {self.os_release}  ({self.os_key})",
            f"  kiến trúc CPU : {self.arch}   ·  {self.cpu_count or '?'} nhân",
            f"  bộ nhớ / đĩa  : RAM {gb(self.ram_bytes)}  ·  đĩa trống {gb(self.disk_free_bytes)}",
            f"  Python        : {self.python_version}   {self.python_path}",
            f"  quyền quản trị: {'có' if self.is_admin else 'không'}",
        ]
        dong.append(
            "  trình cài gói : "
            + (", ".join(self.package_managers) if self.package_managers else "KHÔNG CÓ CÁI NÀO")
        )
        if self.network is not None:
            dong.append(self.network.render())
        if self.proxy_vars:
            dong.append("  proxy         : " + ", ".join(f"{k}={v}" for k, v in self.proxy_vars))

        # Nói ra hệ quả, không chỉ nói ra số liệu. Một bảng thông số mà người
        # đọc phải tự suy ra "vậy là tôi không cài được gì" là một bảng chưa
        # làm xong việc của nó.
        canh_bao: list[str] = []
        if not self.package_managers:
            canh_bao.append(
                "Không có trình quản lý gói nào trên PATH — 'eaa doctor --fix' sẽ "
                "không đề xuất được lệnh cài nào cho máy này."
            )
        if self.network is not None and not self.network.reachable and not self.network.skipped:
            canh_bao.append(
                "Không ra được Internet — mọi năng lực tra cứu (tìm tài liệu, tìm "
                "công cụ, tra lỗi cài đặt) sẽ hỏng. Kiểm proxy hoặc tường lửa trước."
            )
        if self.disk_free_bytes and self.disk_free_bytes < 2 * 1024**3:
            canh_bao.append(f"Đĩa trống chỉ còn {gb(self.disk_free_bytes)} — cài toolchain có thể hụt chỗ.")
        if canh_bao:
            dong += ["", "HỆ QUẢ:"] + [f"  ⚠ {c}" for c in canh_bao]
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Các phép đo
# --------------------------------------------------------------------------


def _quyen_quan_tri() -> bool:
    """Có quyền cài ở tầm hệ thống không.

    Trên Windows không có ``geteuid``; ``False`` ở đó nghĩa là "không xác định
    được", và nghiêng về phía dè dặt là đúng — đoán nhầm rằng mình có quyền
    dẫn tới một lệnh cài chạy nửa chừng rồi hỏng.
    """
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        return False


def _ram_bytes() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return 0


def _dia_trong(duong_dan: str = ".") -> int:
    try:
        return shutil.disk_usage(duong_dan).free
    except OSError:
        return 0


def _bien_proxy() -> tuple[tuple[str, str], ...]:
    """Đọc biến proxy, CHE phần thông tin đăng nhập nếu có.

    ``http_proxy`` hay chứa ``user:mật_khẩu@host``. In nguyên ra là đúng loại
    rò rỉ mà NFR-06 cấm, chỉ khác chỗ nó không phải khóa API.
    """
    import re

    from eaa.llm.base import mask_secrets

    # ``mask_secrets`` che thứ trông giống khóa API; nó không biết gì về phần
    # ``user:mật_khẩu@`` của một URL. Hai kiểu bí mật khác nhau nên cần hai
    # bộ che khác nhau, và bộ này chạy trước để phần còn lại vẫn đọc được.
    dang_nhap = re.compile(r"://[^/@\s]*:[^/@\s]*@")

    ket: list[tuple[str, str]] = []
    for ten in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        gt = os.environ.get(ten, "").strip()
        if gt:
            ket.append((ten, mask_secrets(dang_nhap.sub("://***:***@", gt))))
    return tuple(ket)


#: Cách hỏi từng hệ sinh thái "đã cài gói nào rồi". Là DỮ LIỆU để thêm được
#: hệ sinh thái mới mà không sửa logic.
LENH_LIET_KE_GOI: dict[str, tuple[str, ...]] = {
    "python": ("{python}", "-m", "pip", "list", "--format=freeze"),
    "npm": ("npm", "ls", "--global", "--depth=0", "--parseable"),
}


def list_packages(
    *,
    ecosystem: str = "python",
    runner: Callable[[Sequence[str]], tuple[int, str]] | None = None,
    timeout_s: float = 20.0,
) -> list[str]:
    """Liệt kê gói đã cài của một hệ sinh thái.

    Vì sao cần, khi đã có ``doctor``: ``doctor`` chỉ kiểm được **thứ đã có
    trong Tool Card**. Nó trả lời "công cụ tôi cần đã cài chưa", không trả lời
    "máy này sẵn có gì". Hai câu khác nhau, và câu thứ hai là câu người ta hỏi
    trước khi quyết định cài thêm hay dùng thứ đang có.

    Trả danh sách rỗng khi không hỏi được — không có gói nào và không hỏi được
    là hai chuyện khác nhau, nhưng ở đây gộp lại được vì bên gọi luôn hiển thị
    kèm câu "hỏi bằng lệnh gì".
    """
    import subprocess

    mau = LENH_LIET_KE_GOI.get(ecosystem)
    if mau is None:
        raise ValueError(
            f"Chưa biết hỏi hệ sinh thái {ecosystem!r}. "
            f"Đang biết: {', '.join(LENH_LIET_KE_GOI)}"
        )
    argv = [sys.executable if x == "{python}" else x for x in mau]

    if runner is not None:
        ma, dau_ra = runner(argv)
    else:
        try:
            kq = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
            ma, dau_ra = kq.returncode, kq.stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
    if ma != 0:
        return []
    return [d.strip() for d in (dau_ra or "").splitlines() if d.strip()]


def check_network(
    host: tuple[str, int] = HOST_KIEM_MANG,
    *,
    timeout_s: float = 3.0,
    connector: Callable[[tuple[str, int], float], None] | None = None,
) -> NetworkCheck:
    """Thử nối ra ngoài THẬT. Nhanh, và có hạn giờ ngắn."""
    import time

    from eaa.web import NO_NET_ENV

    if os.environ.get(NO_NET_ENV, "").strip() in ("1", "true", "yes"):
        return NetworkCheck(
            reachable=False, skipped=True,
            detail=f"{NO_NET_ENV}=1 — lối ra mạng đang bị tắt có chủ ý",
        )

    noi = connector or (lambda hp, t: socket.create_connection(hp, timeout=t).close())
    bat_dau = time.monotonic()
    try:
        noi(host, timeout_s)
    except OSError as exc:
        return NetworkCheck(
            reachable=False, host=f"{host[0]}:{host[1]}",
            elapsed_ms=int((time.monotonic() - bat_dau) * 1000),
            detail=f"không nối được: {exc}",
        )
    return NetworkCheck(
        reachable=True, host=f"{host[0]}:{host[1]}",
        elapsed_ms=int((time.monotonic() - bat_dau) * 1000),
        detail="nối được",
    )


def probe(
    *,
    which: Callable[[str], str | None] = shutil.which,
    network: bool = True,
    connector: Callable[[tuple[str, int], float], None] | None = None,
    path: str = ".",
) -> EnvironmentReport:
    """Dò toàn bộ môi trường. Mọi phép đo đều tiêm được để kiểm bằng test."""
    return EnvironmentReport(
        os_name=platform.system(),
        os_release=platform.release(),
        arch=platform.machine(),
        python_version=platform.python_version(),
        python_path=sys.executable,
        is_admin=_quyen_quan_tri(),
        cpu_count=os.cpu_count() or 0,
        ram_bytes=_ram_bytes(),
        disk_free_bytes=_dia_trong(path),
        package_managers=tuple(t for t in TRINH_QUAN_LY_GOI if which(t)),
        proxy_vars=_bien_proxy(),
        network=check_network(connector=connector) if network else None,
        probed_at=_now(),
    )
