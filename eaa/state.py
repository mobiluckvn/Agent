"""Project State — đọc/ghi trạng thái dự án một cách nguyên tử, có khóa.

EAA-SDD-03 §3.2 (lược đồ) và §4 (giao diện ``load() / save(state) /
with_lock()``). Hiện thực hóa FR-ORC-02 và NFR-02.

Vì sao module này quan trọng hơn kích thước của nó: Project State là bộ nhớ
DUY NHẤT của hệ thống giữa các lần gọi LLM. Nguyên tắc NT3 (SAD §1) nói mọi
lần gọi mô hình là stateless — ngữ cảnh được lắp ráp lại từ các kho chứ không
nối dài hội thoại. Hệ quả: file này hỏng thì phiên làm việc mất trí nhớ, và
không có bản sao nào trong LLM để khôi phục. Vì vậy mọi lần ghi đều đi theo
đường ghi-tạm-rồi-đổi-tên, không có ngoại lệ.

Bất biến của module:

* Không bao giờ mở file đích ở chế độ cắt ngắn. Ghi ra file tạm cùng thư mục,
  ``fsync``, rồi ``os.replace`` — thao tác đổi tên là nguyên tử trên cả POSIX
  lẫn Windows, nên file trên đĩa luôn là TOÀN BỘ bản cũ hoặc TOÀN BỘ bản mới.
* Vùng găng đọc–sửa–ghi được bảo vệ bằng khóa file liên tiến trình, có thu hồi
  khóa mồ côi (chủ khóa bị ``kill -9`` không kịp chạy ``finally``).
* Mỗi lần ghi đóng dấu thời gian, phục vụ đo Tdev cho Chương 3 (FR-KPI-01).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "BacklogItem",
    "ProjectState",
    "StateStore",
    "StateError",
    "StateCorruptError",
    "StateLockTimeout",
    "PHASES",
    "GATE_STATUSES",
    "MODULE_STATUSES",
]

# Sáu giai đoạn của máy trạng thái Orchestrator — SAD §4.1, Hình 2.
PHASES: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")

GATE_STATUSES: frozenset[str] = frozenset({"pending", "approved", "rejected"})

MODULE_STATUSES: frozenset[str] = frozenset(
    {"todo", "in_gen", "in_verify", "in_review", "merged", "handoff", "stale"}
)

_SCHEMA_VERSION = 1
_LOCK_SUFFIX = ".lock"
_TMP_SUFFIX = ".tmp"


class StateError(Exception):
    """Lỗi gốc của tầng Project State."""


class StateCorruptError(StateError):
    """File state tồn tại nhưng không đọc được thành trạng thái hợp lệ.

    Cố ý KHÔNG tự sửa, không tự tạo lại state rỗng: mất trạng thái âm thầm còn
    nguy hiểm hơn dừng lại: kỹ sư sẽ tưởng dự án đang ở phase khác với thực tế.
    """


class StateLockTimeout(StateError):
    """Không giành được khóa trong thời gian cho phép — có tiến trình khác đang ghi."""


def _now() -> str:
    """Dấu thời gian UTC, đủ mịn để so sánh hai lần ghi liên tiếp."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _process_alive(pid: int) -> bool:
    """Tiến trình còn sống không — dùng để nhận diện khóa mồ côi.

    Trên Windows KHÔNG được dùng ``os.kill(pid, 0)``: khác với POSIX, nó gọi
    thẳng ``TerminateProcess`` và sẽ giết thật tiến trình đang bị hỏi thăm.
    """
    if pid <= 0:
        return False

    if sys.platform == "win32":  # pragma: no cover - nhánh Windows
        import ctypes

        SYNCHRONIZE = 0x00100000
        ERROR_ACCESS_DENIED = 5
        WAIT_TIMEOUT = 258

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            # Mở thất bại KHÔNG đồng nghĩa tiến trình đã chết: bị từ chối quyền
            # nghĩa là nó đang sống và thuộc về người dùng khác. Nhầm hai thứ
            # này sẽ thu hồi khóa của một tiến trình còn đang ghi.
            return kernel32.GetLastError() == ERROR_ACCESS_DENIED
        try:
            # WAIT_TIMEOUT = còn chạy; WAIT_OBJECT_0 (0) = đã kết thúc.
            return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Tiến trình của người dùng khác — tồn tại, chỉ là ta không đụng được.
        return True
    return True


@dataclass
class BacklogItem:
    """Một module trong backlog — EAA-SDD-03 §3.2."""

    id: str
    status: str = "todo"
    retries: int = 0
    #: Một câu module này chịu trách nhiệm gì — do bước phân rã viết ra và
    #: người duyệt ở G1. Giữ lại vì đây là thứ DUY NHẤT nói được Ý ĐỊNH của
    #: module cho lượt sinh mã; bỏ nó thì mọi module nhận cùng một câu giao
    #: việc chung chung, và mã sai ý định vẫn qua sạch bốn cổng (SL-135).
    purpose: str = ""
    #: Hàm module này hứa cung cấp cho module khác, theo bản phân rã đã duyệt.
    #: Cùng lý do với ``purpose``: đây là phần HỢP ĐỒNG người đã đọc, và nếu
    #: không ai mang nó tới lượt sinh mã thì mô hình đặt tên hàm khác đi cũng
    #: không cổng nào biết (SL-135).
    provides: list[str] = field(default_factory=list)
    #: Tài nguyên phần cứng module này chiếm dụng; nguồn dựng Knowledge Graph
    #: và kiểm tra xung đột ngay lúc khai báo (FR-KG-01/02, quy trình P2).
    #: Engine chỉ coi đây là chuỗi mờ — ý nghĩa do Platform Pack và Project định.
    uses: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "retries": self.retries,
            "purpose": self.purpose,
            "provides": list(self.provides),
            "uses": list(self.uses),
            "depends_on": list(self.depends_on),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BacklogItem":
        try:
            module_id = data["id"]
        except (KeyError, TypeError) as exc:
            raise StateCorruptError(f"mục backlog thiếu trường 'id': {data!r}") from exc

        status = data.get("status", "todo")
        if status not in MODULE_STATUSES:
            raise StateCorruptError(
                f"module {module_id!r} có status không hợp lệ: {status!r} "
                f"(cho phép: {sorted(MODULE_STATUSES)})"
            )

        retries = data.get("retries", 0)
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
            raise StateCorruptError(
                f"module {module_id!r} có retries không hợp lệ: {retries!r} "
                "(phải là số nguyên không âm — vòng tự sửa so sánh với N)"
            )

        return cls(
            id=module_id,
            status=status,
            retries=retries,
            purpose=str(data.get("purpose", "")),
            provides=[str(x) for x in (data.get("provides") or [])],
            uses=list(data.get("uses", [])),
            depends_on=list(data.get("depends_on", [])),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class ProjectState:
    """Trạng thái dự án — bộ nhớ sống ngoài LLM (ADR-02)."""

    phase: str = "A"
    gates: dict[str, str] = field(default_factory=dict)
    backlog: list[BacklogItem] = field(default_factory=list)
    #: Băm của constraints.yaml đang hiệu lực; đi vào commit message (NFR-07).
    constraints_version: str = ""
    llm: dict[str, str] = field(default_factory=dict)
    #: Băm môi trường công cụ do ``eaa doctor`` ghi — FR-ENV-04.
    env_hash: str = ""
    #: Module đang được xử lý, để ``eaa resume`` nói được "đang dở ở đâu".
    current_module: str | None = None
    created_at: str = ""
    updated_at: str = ""

    # -- truy vấn tiện dụng -------------------------------------------------

    def gate_status(self, gate_id: str) -> str:
        """Trạng thái một gate; gate chưa từng đụng tới coi như ``pending``.

        Mặc định là "chưa duyệt", không phải "đã duyệt" — thiếu dữ liệu không
        bao giờ được diễn giải thành có quyền đi tiếp (FR-GATE-01).
        """
        return self.gates.get(gate_id, "pending")

    def module(self, module_id: str) -> BacklogItem | None:
        for item in self.backlog:
            if item.id == module_id:
                return item
        return None

    # -- tuần tự hóa --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "phase": self.phase,
            "gates": dict(self.gates),
            "backlog": [item.to_dict() for item in self.backlog],
            "constraints_version": self.constraints_version,
            "llm": dict(self.llm),
            "env_hash": self.env_hash,
            "current_module": self.current_module,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        if not isinstance(data, dict):
            raise StateCorruptError(f"state phải là một đối tượng JSON, nhận {type(data)}")

        phase = data.get("phase", "A")
        if phase not in PHASES:
            raise StateCorruptError(
                f"phase không hợp lệ: {phase!r} (cho phép: {list(PHASES)})"
            )

        gates = data.get("gates", {}) or {}
        if not isinstance(gates, dict):
            raise StateCorruptError(f"'gates' phải là đối tượng, nhận {type(gates)}")
        for gate_id, status in gates.items():
            if status not in GATE_STATUSES:
                raise StateCorruptError(
                    f"gate {gate_id} có trạng thái không hợp lệ: {status!r} "
                    f"(cho phép: {sorted(GATE_STATUSES)})"
                )

        backlog_raw = data.get("backlog", []) or []
        if not isinstance(backlog_raw, list):
            raise StateCorruptError(f"'backlog' phải là mảng, nhận {type(backlog_raw)}")

        return cls(
            phase=phase,
            gates=dict(gates),
            backlog=[BacklogItem.from_dict(item) for item in backlog_raw],
            constraints_version=data.get("constraints_version", ""),
            llm=dict(data.get("llm", {}) or {}),
            env_hash=data.get("env_hash", ""),
            current_module=data.get("current_module"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class StateStore:
    """Cổng truy cập file ``project_state.json`` của một dự án."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._lock_path = self.path.with_name(self.path.name + _LOCK_SUFFIX)
        self._lock_depth = 0
        self._lock_fd: int | None = None

    def __repr__(self) -> str:  # pragma: no cover - tiện gỡ rối
        return f"StateStore({str(self.path)!r})"

    # -- đọc / ghi ----------------------------------------------------------

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> ProjectState:
        """Đọc state từ đĩa. Đây chính là phần lõi của ``eaa resume``."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Chưa có Project State tại {self.path} — chạy 'eaa init' trước."
            ) from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StateCorruptError(
                f"Project State tại {self.path} không phải JSON hợp lệ ({exc}). "
                "File không được sửa tự động: hãy khôi phục từ Git rồi chạy lại."
            ) from exc

        return ProjectState.from_dict(data)

    def save(self, state: ProjectState) -> None:
        """Ghi state xuống đĩa một cách nguyên tử, dưới khóa.

        Đường đi: khóa → tạo file tạm CÙNG thư mục (để ``os.replace`` không
        phải vượt ranh giới hệ thống tệp) → ghi → ``flush`` → ``fsync`` →
        ``os.replace``. Chết ở bất kỳ điểm nào trước ``os.replace``, file đích
        vẫn nguyên bản cũ; sau ``os.replace``, nó là bản mới trọn vẹn.
        """
        with self.with_lock():
            now = _now()
            if not state.created_at:
                state.created_at = now
            state.updated_at = now

            payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n"

            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self.path.parent),
                prefix=self.path.name + ".",
                suffix=_TMP_SUFFIX,
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self.path)
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise

            self._fsync_dir()

    def _fsync_dir(self) -> None:
        """Ép thư mục ghi xuống đĩa để bản thân thao tác đổi tên cũng bền.

        Không có bước này, ``os.replace`` đã nguyên tử về mặt hiển thị nhưng
        vẫn có thể mất khi mất điện đột ngột. Windows không hỗ trợ mở thư mục
        theo kiểu này nên bỏ qua.
        """
        if sys.platform == "win32":  # pragma: no cover - nhánh Windows
            return
        try:
            dir_fd = os.open(str(self.path.parent), os.O_RDONLY)
        except OSError:  # pragma: no cover - hệ thống tệp không cho mở thư mục
            return
        try:
            os.fsync(dir_fd)
        except OSError:  # pragma: no cover
            pass
        finally:
            os.close(dir_fd)

    # -- khóa liên tiến trình ----------------------------------------------

    @contextmanager
    def with_lock(self, timeout: float = 10.0, poll: float = 0.05) -> Iterator[None]:
        """Vùng găng cho chuỗi đọc–sửa–ghi.

        Tái nhập được trong cùng một ``StateStore``: ``save()`` tự khóa, nên
        ``with store.with_lock(): store.save(s)`` không tự khóa chính mình.
        """
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return

        self._acquire(timeout=timeout, poll=poll)
        self._lock_depth = 1
        try:
            yield
        finally:
            self._lock_depth = 0
            self._release()

    def _acquire(self, timeout: float, poll: float) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        han_chot = time.monotonic() + timeout

        while True:
            try:
                fd = os.open(
                    str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
                )
            except FileExistsError:
                if self._reclaim_if_orphan():
                    continue
                if time.monotonic() >= han_chot:
                    raise StateLockTimeout(
                        f"Không giành được khóa {self._lock_path} sau {timeout:g}s — "
                        f"{self._lock_owner_note()}"
                    ) from None
                time.sleep(poll)
                continue

            os.write(
                fd,
                json.dumps(
                    {"pid": os.getpid(), "host": socket.gethostname(), "at": _now()}
                ).encode("utf-8"),
            )
            os.close(fd)
            self._lock_fd = fd
            return

    def _release(self) -> None:
        self._lock_path.unlink(missing_ok=True)
        self._lock_fd = None

    def _read_lock_info(self) -> dict[str, Any] | None:
        try:
            return json.loads(self._lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _lock_owner_note(self) -> str:
        info = self._read_lock_info()
        if not info:
            return "không đọc được thông tin chủ khóa"
        return f"đang bị giữ bởi pid {info.get('pid')} trên {info.get('host')}"

    def _reclaim_if_orphan(self) -> bool:
        """Thu hồi khóa của tiến trình đã chết.

        ``kill -9`` không cho tiến trình chạy ``finally``, nên khóa nằm lại
        trên đĩa mãi mãi — đúng kịch bản TC-03. Chỉ thu hồi khi chắc chắn:
        cùng máy VÀ pid đã không còn. Khóa từ máy khác thì chờ chứ không đoán.
        """
        info = self._read_lock_info()
        if info is None:
            # Khóa hỏng hoặc vừa bị chủ nó xóa; thử lại vòng sau.
            self._lock_path.unlink(missing_ok=True)
            return True

        if info.get("host") != socket.gethostname():
            return False

        pid = info.get("pid")
        if not isinstance(pid, int) or _process_alive(pid):
            return False

        self._lock_path.unlink(missing_ok=True)
        return True
