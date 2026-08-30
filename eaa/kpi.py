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

__all__ = ["KpiError", "KpiLogger", "ProcessReview", "COLUMNS", "EVENTS"]

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
    # Hai lượt chạy KHÔNG dẫn tới merge. Ghi riêng chứ không gộp vào
    # ``generate``: nếu gộp, số liệu Chương 3 sẽ tính cả những lượt chưa từng
    # qua đủ cổng vào tỉ lệ đạt — và tỉ lệ ấy đẹp lên vì một lý do không liên
    # quan gì tới chất lượng mã.
    "draft_run",   # nháp: chạy một tập cổng nhẹ hơn (SL-88)
    "preview",     # xem trước: không cổng, không nhánh, không commit (SL-91)
)


class KpiError(Exception):
    """Nhật ký KPI sai lược đồ."""


#: Ứng với mỗi cổng hay trượt, một hướng sửa CỤ THỂ. Bảng này là dữ liệu chứ
#: không phải mã: nó nói "khi cổng X trượt nhiều thì thường là vì Y", và Y đến
#: từ quan sát chứ không từ suy luận. Thêm một cổng mới là thêm một dòng.
_HUONG_SUA: dict[str, str] = {
    "compile": (
        "Lỗi dịch lặp lại thường là do prompt thiếu tệp tiêu đề của module phụ "
        "thuộc, hoặc thiếu quy ước kiểu dữ liệu. Xem lại lớp interface (K3): "
        "'eaa interface <module>' sinh hợp đồng gọi trước khi sinh thân."
    ),
    "static": (
        "Phân tích tĩnh trượt nhiều nghĩa là điều CẤM chưa vào được prompt, "
        "hoặc dự án chưa liệt kê điều cấm mà pack có luật phát hiện. Đối chiếu "
        "'forbidden' trong constraints.yaml với rules/ của pack."
    ),
    "size": (
        "Vượt ngân sách bộ nhớ lặp lại: chia ngân sách theo module để biết sớm "
        "chứ đừng đợi tới lúc liên kết — 'eaa budget propose'."
    ),
    "unittests": (
        "Test đơn vị trượt nhiều thường là do prompt không nói rõ hợp đồng của "
        "hàm. Bổ sung tiêu chí nghiệm thu đo được: 'eaa propose acceptance'."
    ),
    "sim": (
        "Cổng mô phỏng trượt là dấu hiệu về CẤU TRÚC điều khiển chứ không về mã: "
        "không bộ tham số nào cứu được một cấu trúc sai. Xem lại mô hình đối "
        "tượng: 'eaa propose plant'."
    ),
}


@dataclass
class ProcessReview:
    """Quy trình đang hỏng ở khâu nào — N-906.

    Cố ý tách khỏi :meth:`KpiLogger.summary`: hàm kia tổng hợp mà không diễn
    giải, hàm này diễn giải. Trộn hai việc lại thì người đọc không còn biết
    con số nào là quan sát và câu nào là suy đoán.
    """

    rows: int = 0
    gate_failures: dict[str, int] = field(default_factory=dict)
    repairs_by_module: dict[str, int] = field(default_factory=dict)
    handoffs: int = 0
    merges: int = 0
    gate_rejects: int = 0
    ledger_entries: int = 0

    @property
    def worst_gate(self) -> str:
        if not self.gate_failures:
            return ""
        return max(self.gate_failures.items(), key=lambda kv: kv[1])[0]

    @property
    def worst_module(self) -> str:
        if not self.repairs_by_module:
            return ""
        return max(self.repairs_by_module.items(), key=lambda kv: kv[1])[0]

    def suggestions(self) -> list[str]:
        """Đề xuất sửa prompt hoặc sửa quy tắc, mỗi cái gắn với một con số."""
        y_kien: list[str] = []

        cong = self.worst_gate
        if cong:
            so = self.gate_failures[cong]
            huong = _HUONG_SUA.get(
                cong, "Xem lại quy tắc của cổng này và phần prompt liên quan."
            )
            y_kien.append(f"Cổng {cong!r} trượt {so} lần — nhiều nhất. {huong}")

        module = self.worst_module
        if module and self.repairs_by_module[module] >= 2:
            y_kien.append(
                f"Module {module!r} phải vá {self.repairs_by_module[module]} lần. "
                "Vá nhiều lần cho cùng một module thường KHÔNG phải vì mã khó mà "
                "vì thiếu tri thức: 'eaa resolve " + module + "' đi tìm phần còn "
                "thiếu trước khi tiêu thêm lượt gọi."
            )

        if self.handoffs:
            y_kien.append(
                f"{self.handoffs} lần chạm trần tự sửa rồi bàn giao người. Mỗi lần "
                "như thế là ba lượt gọi mô hình không thành gì — kiểm xem Bảng "
                "kiểm thông tin cần (RIC) có đang cho qua quá dễ không."
            )

        if self.gate_rejects:
            y_kien.append(
                f"{self.gate_rejects} lần người TỪ CHỐI tại gate. Lý do từ chối đã "
                "vào Error Ledger và sẽ xuất hiện ở prompt lần sau; nếu cùng một "
                "lý do lặp lại thì nó nên thành một điều CẤM trong constraints.yaml "
                "chứ không chỉ là một quy tắc mềm."
            )

        if self.ledger_entries and self.merges:
            ti_le = self.ledger_entries / max(1, self.merges)
            if ti_le >= 1.0:
                y_kien.append(
                    f"Trung bình {ti_le:.1f} mục Error Ledger cho mỗi lần merge. "
                    "Tỉ lệ này cao nghĩa là mô hình đang bịa nhiều hơn mức bộ ba "
                    "chunk hiện tại chịu được — tăng top-k truy xuất hoặc bổ sung "
                    "trích đoạn cho các thanh ghi hay bị bịa."
                )

        return y_kien


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Các con số đọc thẳng từ nhật ký. Riêng phần ĐỀ XUẤT ở cuối là suy diễn.
        """
        from eaa.confidence import DA_KIEM

        return DA_KIEM

    def render(self) -> str:
        if not self.rows:
            return (
                "Chưa có dòng KPI nào. Chạy vài module qua vòng lặp chuẩn rồi quay lại "
                "— không đo thì mọi cải tiến chỉ là cảm giác."
            )

        dong = [f"Tự đánh giá quy trình — {self.rows} dòng nhật ký", ""]
        dong.append(f"  Merge          : {self.merges}")
        dong.append(f"  Bàn giao người : {self.handoffs}")
        dong.append(f"  Bị từ chối     : {self.gate_rejects}")
        if self.ledger_entries:
            dong.append(f"  Mục ảo giác    : {self.ledger_entries}")

        if self.gate_failures:
            dong += ["", "  Cổng trượt (nhiều nhất trước):"]
            for cong, so in sorted(self.gate_failures.items(), key=lambda kv: -kv[1]):
                dong.append(f"      {cong:<14} {so}")

        if self.repairs_by_module:
            dong += ["", "  Vòng tự sửa theo module:"]
            for m, so in sorted(self.repairs_by_module.items(), key=lambda kv: -kv[1]):
                dong.append(f"      {m:<20} {so}")

        y_kien = self.suggestions()
        if y_kien:
            dong += ["", "  ĐỀ XUẤT — mỗi cái gắn với một con số ở trên:"]
            for i, y in enumerate(y_kien, 1):
                dong.append(f"      {i}. {y}")
            dong += [
                "",
                "  Đây là ĐỀ XUẤT, không phải kết luận. Máy chỉ được chỗ để nhìn;",
                "  diễn giải số liệu và quyết định đổi quy trình vẫn là việc của người.",
            ]
        else:
            dong += [
                "",
                "  Chưa thấy khâu nào nổi lên. Với ít dòng nhật ký thì điều đó",
                "  KHÔNG có nghĩa là quy trình đang tốt — chỉ có nghĩa là chưa đủ",
                "  dữ liệu để thấy.",
            ]
        return "\n".join(dong)


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

    # ----------------------------------------------------------------------
    # N-906 — tự đánh giá quy trình
    # ----------------------------------------------------------------------

    def weak_points(self, *, ledger: Any = None) -> "ProcessReview":
        """Khâu nào hay hỏng nhất, và đề xuất sửa gì.

        ``summary()`` cố ý không diễn giải — nó tổng hợp thứ đọc thẳng ra được.
        Hàm này thì diễn giải, và ranh giới giữa hai việc phải rõ: mọi đề xuất
        ở đây gắn với MỘT con số quan sát được, và câu chữ nói rõ nó là đề xuất
        chứ không phải kết luận. Diễn giải kết quả vẫn là trách nhiệm học thuật
        của tác giả (công đoạn F1); cái máy làm được là chỉ chỗ để nhìn.
        """
        dong = self.rows()
        review = ProcessReview(rows=len(dong))
        if not dong:
            return review

        # Cổng nào trượt nhiều nhất. Đây là con số hữu ích nhất trong cả bảng:
        # nó nói vòng tự sửa đang tiêu lượt gọi vào việc gì.
        for r in dong:
            if r.get("result") == "fail" and r.get("gate"):
                review.gate_failures[r["gate"]] = review.gate_failures.get(r["gate"], 0) + 1

        for r in dong:
            if r.get("event") == "repair" and r.get("module"):
                review.repairs_by_module[r["module"]] = (
                    review.repairs_by_module.get(r["module"], 0) + 1
                )

        review.handoffs = sum(1 for r in dong if r.get("event") == "handoff")
        review.merges = sum(1 for r in dong if r.get("event") == "merge")
        review.gate_rejects = sum(
            1 for r in dong if r.get("event") == "gate_decision" and r.get("result") == "reject"
        )

        if ledger is not None:
            try:
                review.ledger_entries = len(ledger.all())
            except Exception:  # sổ hỏng không được làm đứt phần tổng hợp
                review.ledger_entries = 0

        return review

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
