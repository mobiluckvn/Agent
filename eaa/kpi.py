"""KPI Logger — số liệu định lượng cho Chương 3.

EAA-SDD-03 §3.4 (lược đồ ``kpi_log.csv``), EAA-SRS-01 FR-KPI-01,
EAA-AIS-05 quy trình P5 (ngân sách token và chi phí), §9.3 (``env_hash``).

Tệp này là nguồn số liệu trực tiếp cho bảng so sánh A/B của đề án, nên nó có
một yêu cầu mà các module khác không có: **cột không được đổi tùy tiện.** Một
bản ghi thiếu cột hay đổi tên cột làm hỏng chuỗi số liệu đã thu, và số liệu đã
thu thì không thu lại được — thí nghiệm đã chạy qua rồi.

Vì vậy:

* Danh sách cột là hằng số có thứ tự cố định, và mọi dòng ghi ra đều đủ cột.
* Ghi nối tiếp; tiêu đề chỉ viết một lần khi tạo tệp.
* Tệp đang có tiêu đề khác với hằng số hiện tại thì báo lỗi thay vì ghi đè —
  trộn hai lược đồ trong một tệp CSV là cách chắc chắn nhất để mất dữ liệu mà
  không ai nhận ra cho tới lúc dựng bảng.

Mỗi dòng ứng với một SỰ KIỆN chứ không phải một module: một module đi trọn
vòng sinh ra nhiều dòng (mỗi lần build, mỗi lần tự sửa, lúc merge). Đó là điều
kiện để đo được số vòng tự sửa và thời gian phát triển, chứ không chỉ đo kết
quả cuối.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = ["KpiError", "KpiLogger", "COLUMNS", "EVENTS"]

#: Thứ tự cột của ``kpi_log.csv``. SDD §3.4 chốt phần đầu; AIS P5 thêm nhóm
#: token/chi phí; AIS §9.3 thêm ``env_hash``; NFR-07 thêm ``prompt_hash`` và
#: ``commit`` để mỗi dòng số liệu truy ngược được về đúng bản mã đã đo.
COLUMNS: tuple[str, ...] = (
    "ts",
    "module",
    "phase",
    "event",
    "tdev_min",
    "retries",
    "first_build_errors",
    "flash_bytes",
    "flash_pct",
    "sram_bytes",
    "sram_pct",
    "llm_model",
    "tokens_in",
    "tokens_out",
    "cost_est",
    "env_hash",
    "prompt_hash",
    "constraints_version",
    "commit",
    "gate",
    "result",
    "note",
)

#: Tên sự kiện dùng trong cột ``event``.
EVENTS: tuple[str, ...] = (
    "module_start",
    "generate",
    "verify",
    "repair",
    "gate_request",
    "gate_decision",
    "merge",
    "handoff",
    "rollback",
)


class KpiError(Exception):
    """Nhật ký KPI sai lược đồ."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class KpiLogger:
    """Ghi ``kpi_log.csv`` của một dự án."""

    path: Path
    #: Băm môi trường công cụ hiện hành; gắn vào mọi dòng (FR-ENV-04).
    env_hash: str = ""
    #: Mặc định cho các cột hay lặp lại, để nơi gọi không phải truyền mỗi lần.
    defaults: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    # ----------------------------------------------------------------------

    def log(
        self,
        *,
        event: str,
        module: str = "",
        phase: str = "",
        **truong: Any,
    ) -> dict[str, Any]:
        """Ghi một dòng. Trả về đúng bản ghi đã ghi, tiện cho kiểm thử."""
        if event not in EVENTS:
            raise KpiError(
                f"Sự kiện KPI không hợp lệ: {event!r} (hợp lệ: {list(EVENTS)}). "
                "Thêm sự kiện mới thì thêm vào EVENTS — cột 'event' là thứ Chương 3 "
                "nhóm số liệu theo, nên nó không được là trường tự do."
            )

        la = set(truong) - set(COLUMNS)
        if la:
            raise KpiError(
                f"Cột KPI không có trong lược đồ: {sorted(la)}. Thêm cột mới phải "
                "sửa COLUMNS, và phải nhận thức rằng số liệu đã thu trước đó sẽ "
                "thiếu cột ấy."
            )

        ban_ghi: dict[str, Any] = {cot: "" for cot in COLUMNS}
        ban_ghi.update(self.defaults)
        ban_ghi.update(
            {
                "ts": _now(),
                "module": module,
                "phase": phase,
                "event": event,
                "env_hash": self.env_hash or ban_ghi.get("env_hash", ""),
            }
        )
        ban_ghi.update({k: v for k, v in truong.items() if v is not None})

        self._ghi(ban_ghi)
        return ban_ghi

    def log_report(
        self,
        report: Any,
        *,
        module: str,
        phase: str = "",
        event: str = "verify",
        **truong: Any,
    ) -> dict[str, Any]:
        """Ghi một dòng từ ``ToolReport`` — số liệu của cổng đi thẳng vào cột.

        Chỉ lấy những khóa có trong lược đồ; số liệu riêng của một cổng (mã
        thoát, dòng lệnh) không lọt vào CSV làm loãng bảng.
        """
        so_lieu = {
            k: v for k, v in (getattr(report, "metrics", {}) or {}).items() if k in COLUMNS
        }
        return self.log(
            event=event,
            module=module,
            phase=phase,
            gate=getattr(report, "gate", ""),
            result="pass" if getattr(report, "passed", False) else "fail",
            **{**so_lieu, **truong},
        )

    # ----------------------------------------------------------------------

    def _ghi(self, ban_ghi: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        moi = not self.path.exists() or self.path.stat().st_size == 0

        if not moi:
            self._kiem_tieu_de()

        with open(self.path, "a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
            if moi:
                writer.writeheader()
            writer.writerow(ban_ghi)
            handle.flush()
            os.fsync(handle.fileno())

    def _kiem_tieu_de(self) -> None:
        with open(self.path, "r", encoding="utf-8", newline="") as handle:
            tieu_de = next(csv.reader(handle), [])
        if tuple(tieu_de) != COLUMNS:
            thieu = [c for c in COLUMNS if c not in tieu_de]
            thua = [c for c in tieu_de if c not in COLUMNS]
            raise KpiError(
                f"{self.path} có lược đồ khác với phiên bản hiện tại.\n"
                f"  Thiếu trong tệp: {thieu}\n"
                f"  Thừa trong tệp : {thua}\n"
                "Không ghi tiếp để tránh trộn hai lược đồ trong một tệp. Hãy đổi "
                "tên tệp cũ (giữ lại — số liệu đã thu không thu lại được) rồi để "
                "tệp mới được tạo với lược đồ mới."
            )

    # ----------------------------------------------------------------------

    def rows(self) -> list[dict[str, str]]:
        if not self.path.is_file():
            return []
        with open(self.path, "r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def rows_for(self, module: str) -> list[dict[str, str]]:
        return [r for r in self.rows() if r.get("module") == module]

    def summary(self, module: str | None = None) -> dict[str, Any]:
        """Tổng hợp thô cho ``eaa report kpi``.

        Cố ý chỉ tổng hợp những gì đọc thẳng ra được từ nhật ký, không suy diễn:
        diễn giải kết quả là trách nhiệm học thuật của tác giả (công đoạn F1),
        không phải việc của công cụ.
        """
        dong = self.rows() if module is None else self.rows_for(module)
        if not dong:
            return {"rows": 0}

        def _so(gia_tri: str) -> float | None:
            try:
                return float(gia_tri)
            except (TypeError, ValueError):
                return None

        modules = sorted({r["module"] for r in dong if r.get("module")})
        merges = [r for r in dong if r.get("event") == "merge"]
        repairs = [r for r in dong if r.get("event") == "repair"]
        tokens_in = [v for r in dong if (v := _so(r.get("tokens_in", ""))) is not None]
        tokens_out = [v for r in dong if (v := _so(r.get("tokens_out", ""))) is not None]
        tdev = [v for r in dong if (v := _so(r.get("tdev_min", ""))) is not None]

        return {
            "rows": len(dong),
            "modules": modules,
            "merges": len(merges),
            "repairs": len(repairs),
            "tokens_in_total": int(sum(tokens_in)),
            "tokens_out_total": int(sum(tokens_out)),
            "tdev_min_total": round(sum(tdev), 2),
            "models": sorted({r["llm_model"] for r in dong if r.get("llm_model")}),
            "env_hashes": sorted({r["env_hash"] for r in dong if r.get("env_hash")}),
        }

    def export(self, dest: str | Path, *, module: str | None = None) -> Path:
        """Xuất một bản sao (đã lọc) — phục vụ ``eaa report kpi --csv out.csv``."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dong = self.rows() if module is None else self.rows_for(module)
        with open(dest, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
            writer.writeheader()
            writer.writerows(dong)
        return dest
