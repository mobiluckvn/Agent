"""Cổng biên dịch và cổng đo chiếm dụng bộ nhớ.

EAA-SDD-03 §2 (gọi toolchain QUA PlatformPack, không gọi thẳng trình dịch của
một họ vi điều khiển nào), EAA-SRS-01 FR-VER-01 (chuỗi kiểm chứng bắt buộc bắt
đầu bằng biên dịch → đo kích thước).

Hai cổng ở chung một tệp vì cả hai đều nói chuyện với bộ công cụ dịch và cổng
sau ăn sản phẩm của cổng trước; SDD §2 cũng không cấp tệp riêng cho cổng đo
kích thước.

Điểm thiết kế đáng chú ý — **engine không biết "Flash" hay "SRAM" là gì.**
Cổng đo kích thước chỉ áp một quy ước đặt tên: mỗi khóa ``<tên>_max`` trong
``limits`` của ``constraints.yaml`` là trần của số liệu tên ``<tên>`` mà
Platform Pack đo được; ``<tên>_min`` là sàn. Nhờ vậy thêm một ngưỡng mới (ví
dụ trần thời gian ngắt) chỉ là thêm một dòng YAML ở dự án và một biểu thức đo
ở pack — engine không đổi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolReport
from eaa.tools.runner import ToolRunner

__all__ = ["CompileGate", "SizeGate", "write_artifact", "UnsafePathError"]


class UnsafePathError(Exception):
    """Artifact chứa đường dẫn thoát ra ngoài thư mục làm việc."""


def write_artifact(artifact: CodeArtifact, work_dir: Path) -> list[Path]:
    """Ghi các tệp của artifact xuống thư mục làm việc.

    Kiểm đường dẫn trước khi ghi. Đây không phải sự cẩn thận thừa: nội dung
    đang ghi do một mô hình ngôn ngữ sinh ra, và tên tệp cũng là thứ nó sinh
    ra. Một đường dẫn tuyệt đối hay một chuỗi ``..`` — dù do ảo giác hay do
    prompt bị chèn — sẽ ghi đè tệp ngoài dự án. Chặn ở đây, một lần, thay vì
    tin rằng mọi nơi gọi tới đều nhớ kiểm.
    """
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    da_ghi: list[Path] = []

    for duong_dan, noi_dung in artifact.files.items():
        ung_vien = Path(duong_dan)
        if ung_vien.is_absolute() or ".." in ung_vien.parts:
            raise UnsafePathError(
                f"Artifact chứa đường dẫn không an toàn: {duong_dan!r}. "
                "Tệp sinh ra phải nằm trong thư mục dự án."
            )
        dich = (work_dir / ung_vien).resolve()
        if not dich.is_relative_to(work_dir):
            raise UnsafePathError(
                f"Đường dẫn {duong_dan!r} thoát ra ngoài {work_dir}."
            )
        dich.parent.mkdir(parents=True, exist_ok=True)
        dich.write_text(noi_dung, encoding="utf-8")
        da_ghi.append(dich)

    return da_ghi


@dataclass
class CompileGate:
    """Cổng 1 — dịch mã nguồn thành ảnh nhị phân."""

    runner: ToolRunner
    #: Thư mục nhận sản phẩm dịch, tương đối so với thư mục làm việc.
    build_dir: str = "build"
    #: Đuôi tệp được đưa vào lệnh dịch.
    source_suffixes: tuple[str, ...] = (".c",)
    include_dirs: Sequence[str] = field(default_factory=list)
    name: str = "compile"

    def run(self, artifact: CodeArtifact) -> ToolReport:
        try:
            da_ghi = write_artifact(artifact, self.runner.work_dir)
        except UnsafePathError as exc:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[ToolError(str(exc), severity=Severity.ERROR)],
            )

        nguon = [p for p in da_ghi if p.suffix in self.source_suffixes]
        if not nguon:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[
                    ToolError(
                        "Artifact không chứa tệp mã nguồn nào để dịch "
                        f"(đuôi chấp nhận: {', '.join(self.source_suffixes)})."
                    )
                ],
            )

        goc = self.runner.work_dir
        thu_muc_build = goc / self.build_dir
        thu_muc_build.mkdir(parents=True, exist_ok=True)
        dich = thu_muc_build / f"{self._ten_dich(artifact, nguon)}.elf"

        bao_cao = self.runner.run(
            "compile",
            {
                "sources": [str(p.relative_to(goc)) for p in nguon],
                "source": str(nguon[0].relative_to(goc)),
                "output": str(dich.relative_to(goc)),
                "include_dir": self._include_dir(da_ghi, goc),
            },
            gate_name=self.name,
        )

        if bao_cao.passed:
            bao_cao.metrics["binary"] = str(dich)
            bao_cao.metrics["source_files"] = len(nguon)
        return bao_cao

    def _include_dir(self, da_ghi: Sequence[Path], goc: Path) -> str:
        if self.include_dirs:
            return str(self.include_dirs[0])
        header = [p for p in da_ghi if p.suffix == ".h"]
        thu_muc = header[0].parent if header else goc
        return str(thu_muc.relative_to(goc)) or "."

    @staticmethod
    def _ten_dich(artifact: CodeArtifact, nguon: Sequence[Path]) -> str:
        return nguon[0].stem


@dataclass
class SizeGate:
    """Cổng 2 — đo chiếm dụng bộ nhớ và đối chiếu ngưỡng của dự án."""

    runner: ToolRunner
    #: ``constraints.limits`` — engine chỉ đọc quy ước ``_max`` / ``_min``.
    limits: dict[str, Any] = field(default_factory=dict)
    name: str = "size"

    def run(self, binary: str | Path) -> ToolReport:
        binary = Path(binary)
        goc = self.runner.work_dir
        duong_dan = str(binary.relative_to(goc)) if binary.is_relative_to(goc) else str(binary)

        bao_cao = self.runner.run(
            "size", {"binary": duong_dan}, gate_name=self.name
        )
        if not bao_cao.passed:
            return bao_cao

        vi_pham = self._doi_chieu_nguong(bao_cao.metrics)
        if vi_pham:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=vi_pham,
                warnings=bao_cao.warnings,
                metrics=bao_cao.metrics,
                raw_output=bao_cao.raw_output,
                duration_s=bao_cao.duration_s,
            )
        return bao_cao

    def _doi_chieu_nguong(self, so_lieu: dict[str, Any]) -> list[ToolError]:
        """Áp quy ước ``<tên>_max`` / ``<tên>_min`` lên số liệu pack đo được.

        Ngưỡng khai báo mà pack KHÔNG đo được số liệu tương ứng thì báo lỗi chứ
        không bỏ qua: một ngưỡng không đo được là một ngưỡng không được thi
        hành, và im lặng ở đây nghĩa là ngưỡng Flash < 50% của đề cương chỉ còn
        là một dòng chữ trong tệp cấu hình.
        """
        loi: list[ToolError] = []

        for khoa, nguong in self.limits.items():
            if not isinstance(nguong, (int, float)) or isinstance(nguong, bool):
                continue
            if khoa.endswith("_max"):
                ten, la_tran = khoa[:-4], True
            elif khoa.endswith("_min"):
                ten, la_tran = khoa[:-4], False
            else:
                continue

            if ten not in so_lieu:
                # Ngưỡng dành cho cổng khác (ví dụ chu kỳ điều khiển do cổng mô
                # phỏng đo) thì không phải việc của cổng này.
                continue

            do_duoc = so_lieu[ten]
            if not isinstance(do_duoc, (int, float)):
                loi.append(
                    ToolError(
                        f"Số liệu {ten!r} pack đo được không phải số: {do_duoc!r}"
                    )
                )
                continue

            if la_tran and do_duoc > nguong:
                loi.append(
                    ToolError(
                        f"{ten} = {do_duoc} vượt trần {nguong} khai báo trong "
                        f"constraints.yaml ({khoa})."
                    )
                )
            elif not la_tran and do_duoc < nguong:
                loi.append(
                    ToolError(
                        f"{ten} = {do_duoc} dưới sàn {nguong} khai báo trong "
                        f"constraints.yaml ({khoa})."
                    )
                )

        return loi
