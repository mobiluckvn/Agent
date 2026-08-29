"""Cổng kiểm thử đơn vị — chạy pytest trên bộ test của dự án.

EAA-SDD-03 §2 ("pytest runner"), FR-VER-01 (mắt xích thứ tư của chuỗi kiểm
chứng), EAA-AIS-05 §9.1 (pytest thuộc phần CHUNG của manifest công cụ, không
thuộc Platform Pack).

Vì sao pytest chứ không phải một khung kiểm thử C: theo công đoạn C2 của Ma
trận Người–AI, firmware được viết tách lớp trừu tượng phần cứng để biên dịch
và chạy được trên máy tính qua lớp giả lập. Kiểm thử đơn vị vì thế là kiểm thử
mã đã chạy trên máy chủ, do Python điều khiển — cùng một khung với phần còn
lại của sản phẩm.

Không có bộ test nào là KHÔNG ĐẠT, không phải đạt-vì-không-có-gì-để-chạy: một
cổng trả về "đạt" khi chưa ai viết test là cổng báo tin giả.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from eaa.tools.base import CodeArtifact, ToolError, ToolReport

__all__ = ["UnitTestGate"]

_TOM_TAT = re.compile(
    r"(?:(?P<passed>\d+) passed)|(?:(?P<failed>\d+) failed)|(?:(?P<errors>\d+) error)"
)


@dataclass
class UnitTestGate:
    """Cổng 4 — kiểm thử đơn vị."""

    tests_dir: Path
    work_dir: Path
    timeout_s: float = 300.0
    #: Cho phép cổng đạt khi dự án chưa có test nào. Mặc định KHÔNG cho phép.
    allow_empty: bool = False
    name: str = "unittests"

    def run(self, artifact: CodeArtifact | None = None) -> ToolReport:
        tests_dir = Path(self.tests_dir)

        if not tests_dir.is_dir() or not any(tests_dir.rglob("test_*.py")):
            return ToolReport(
                gate=self.name,
                passed=self.allow_empty,
                errors=[]
                if self.allow_empty
                else [
                    ToolError(
                        f"Không có bộ kiểm thử đơn vị nào trong {tests_dir}. Cổng "
                        "này KHÔNG đạt khi chưa có test — 'chưa có gì để chạy' "
                        "không phải là 'đã kiểm chứng'."
                    )
                ],
                metrics={"tests_found": 0},
            )

        bat_dau = time.monotonic()
        try:
            ket_qua = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--no-header"],
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_s,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[ToolError(f"pytest quá thời gian chờ {self.timeout_s:g}s")],
                metrics={"timeout": True},
                duration_s=time.monotonic() - bat_dau,
            )

        dau_ra = (ket_qua.stdout or "") + (ket_qua.stderr or "")
        so_lieu = self._dem(dau_ra)
        so_lieu["exit_code"] = ket_qua.returncode

        dat = ket_qua.returncode == 0
        loi = (
            []
            if dat
            else [
                ToolError(
                    f"{so_lieu.get('failed', 0)} test không đạt, "
                    f"{so_lieu.get('errors', 0)} lỗi. Trích đầu ra:\n"
                    + "\n".join(self._dong_that_bai(dau_ra))
                )
            ]
        )

        return ToolReport(
            gate=self.name,
            passed=dat,
            errors=loi,
            metrics=so_lieu,
            raw_output=dau_ra,
            duration_s=time.monotonic() - bat_dau,
        )

    @staticmethod
    def _dem(dau_ra: str) -> dict[str, int]:
        so_lieu = {"passed": 0, "failed": 0, "errors": 0}
        for khop in _TOM_TAT.finditer(dau_ra):
            for ten, gia_tri in khop.groupdict().items():
                if gia_tri:
                    so_lieu[ten] = int(gia_tri)
        so_lieu["tests_found"] = so_lieu["passed"] + so_lieu["failed"] + so_lieu["errors"]
        return so_lieu

    @staticmethod
    def _dong_that_bai(dau_ra: str, gioi_han: int = 20) -> list[str]:
        """Giữ lại phần đầu ra thật sự hữu ích cho vòng tự sửa."""
        dong = [
            d
            for d in dau_ra.splitlines()
            if d.startswith(("E ", "FAILED", "ERROR")) or ">" == d[:1]
        ]
        return dong[:gioi_han] or dau_ra.splitlines()[-gioi_han:]
