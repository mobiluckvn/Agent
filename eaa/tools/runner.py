"""Bộ chạy công cụ ngoài — thi hành lời gọi do Platform Pack khai báo.

EAA-SDD-03 §2 (Tool Layer), EAA-AIS-05 §9.5 (adapter đọc cú pháp gọi từ dữ
liệu, không hard-code). Xem `docs/SAI_LECH_THIET_KE.md` mục SL-07.

Tất cả adapter trong ``eaa/tools/`` đều đi qua đây, nên chỉ có MỘT chỗ biết
cách chạy một tiến trình ngoài và đọc kết quả của nó. Ba luật của chỗ đó:

1.  **Không có shell.** Chạy bằng danh sách argv. Không shell thì không có
    chèn lệnh, và mẫu lệnh chạy giống nhau trên Windows lẫn Linux (NFR-04).
2.  **Công cụ thiếu là KHÔNG ĐẠT, không phải bỏ qua.** Đây là điều khiến toàn
    bộ chuỗi kiểm chứng có nghĩa: "thiếu hoặc lệch phiên bản bất kỳ mắt xích
    nào thì cổng kiểm chứng thành vô nghĩa" (AIS §9). Một cổng im lặng cho qua
    vì không tìm thấy công cụ còn tệ hơn không có cổng — nó tạo cảm giác đã
    kiểm.
3.  **Thao tác cần người xác nhận thì không chạy nếu chưa có xác nhận**, kể cả
    khi người gọi quên hỏi (FR-DIA-02).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from eaa.platform import PackError, PackManifest, ParseSpec, ToolInvocation
from eaa.tools.base import Severity, ToolError, ToolReport

__all__ = ["ToolRunner", "ConfirmationRequired", "ToolExecutionError"]


class ConfirmationRequired(Exception):
    """Năng lực chạm vào thiết bị thật/máy của kỹ sư mà chưa có người xác nhận."""


class ToolExecutionError(Exception):
    """Không dựng nổi lời gọi công cụ — lỗi lắp lệnh, không phải lỗi của công cụ."""


@dataclass
class ToolRunner:
    """Chạy một năng lực của Platform Pack và trả về báo cáo chuẩn hóa."""

    manifest: PackManifest
    work_dir: Path
    #: Tham số nền cho mọi lời gọi (thường là ``constraints.platform_params()``).
    base_params: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.work_dir = Path(self.work_dir)
        if self.base_params is None:
            self.base_params = {}

    # ----------------------------------------------------------------------

    def available(self, capability: str) -> bool:
        """Công cụ của năng lực này có trên máy không."""
        if not self.manifest.has(capability):
            return False
        chuong_trinh = self.manifest.invocation(capability).command[0]
        if re.fullmatch(r"\{\w+\}", chuong_trinh):
            # Chương trình do tham số quyết định (ví dụ trình thông dịch đang
            # chạy) — chỉ biết được lúc dựng lệnh.
            return True
        return shutil.which(chuong_trinh) is not None

    def run(
        self,
        capability: str,
        params: Mapping[str, Any] | None = None,
        *,
        gate_name: str | None = None,
        confirmed_by: str | None = None,
        cwd: Path | None = None,
    ) -> ToolReport:
        """Chạy một năng lực; mọi kết cục đều trả về ``ToolReport``.

        Cố ý không ném ngoại lệ khi công cụ chạy hỏng: Orchestrator cần một báo
        cáo để đưa vào vòng tự sửa và vào KPI, chứ không cần một ngoại lệ làm
        đứt vòng lặp. Chỉ những lỗi KHÔNG thể diễn đạt thành "cổng không đạt"
        — lắp lệnh sai, thiếu xác nhận của người — mới ném ra ngoài.
        """
        ten_cong = gate_name or capability
        goi = self.manifest.invocation(capability)

        if goi.requires_confirmation and not confirmed_by:
            raise ConfirmationRequired(
                f"Năng lực {capability!r} của pack {self.manifest.name!r} cần "
                "người xác nhận trước khi chạy (FR-DIA-02). Chưa có xác nhận "
                "thì không chạy — kể cả trong phiên tự động."
            )

        tham_so = {**dict(self.base_params), **dict(params or {})}
        try:
            argv = goi.resolve(tham_so)
        except PackError as exc:
            raise ToolExecutionError(f"Cổng {ten_cong}: {exc}") from exc

        bat_dau = time.monotonic()
        try:
            ket_qua = subprocess.run(
                argv,
                cwd=str(cwd or self.work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=goi.timeout_s,
                shell=False,
            )
        except FileNotFoundError:
            return self._bao_cao_thieu_cong_cu(ten_cong, argv, time.monotonic() - bat_dau)
        except subprocess.TimeoutExpired:
            return ToolReport(
                gate=ten_cong,
                passed=False,
                errors=[
                    ToolError(
                        f"Công cụ quá thời gian chờ {goi.timeout_s:g}s: {' '.join(argv)}"
                    )
                ],
                metrics={"timeout": True},
                duration_s=time.monotonic() - bat_dau,
            )

        return self._doc_ket_qua(
            ten_cong, goi, ket_qua, argv, time.monotonic() - bat_dau
        )

    # ----------------------------------------------------------------------

    def _bao_cao_thieu_cong_cu(
        self, ten_cong: str, argv: list[str], duration: float
    ) -> ToolReport:
        return ToolReport(
            gate=ten_cong,
            passed=False,
            errors=[
                ToolError(
                    f"Không tìm thấy công cụ {argv[0]!r} trên máy này. Cổng "
                    f"{ten_cong} KHÔNG được coi là đạt khi thiếu công cụ — "
                    "chạy 'eaa doctor' để kiểm tra môi trường.",
                    severity=Severity.ERROR,
                )
            ],
            # Cờ này để CLI trả mã thoát 4 (lỗi môi trường) thay vì mã thoát
            # của một lần kiểm chứng thất bại thông thường (SDD §6).
            metrics={"env_error": True, "missing_tool": argv[0]},
            duration_s=duration,
        )

    def _doc_ket_qua(
        self,
        ten_cong: str,
        goi: ToolInvocation,
        ket_qua: subprocess.CompletedProcess[str],
        argv: list[str],
        duration: float,
    ) -> ToolReport:
        dau_ra = (ket_qua.stdout or "") + (ket_qua.stderr or "")
        bao_cao = self.doc_ket_qua(
            goi.parse, exit_code=ket_qua.returncode, output=dau_ra, gate=ten_cong
        )
        bao_cao.metrics["command"] = " ".join(argv)
        bao_cao.duration_s = duration
        return bao_cao

    @classmethod
    def doc_ket_qua(
        cls,
        parse: Any,
        *,
        exit_code: int,
        output: str,
        gate: str = "",
    ) -> ToolReport:
        """Đọc kết quả một lượt chạy thành ToolReport.

        Tách khỏi phần gọi tiến trình để kiểm được bằng đầu ra THẬT đã ghi lại,
        không phải bằng một tiến trình giả. Chính đầu ra dưới đây từng lừa được
        cả hai phiên làm việc (SL-120), nên nó phải có mặt trong bộ kiểm.
        """
        dau_ra = output
        loi = cls._bat(parse.error_regex, dau_ra, Severity.ERROR)
        canh_bao = cls._bat(parse.warning_regex, dau_ra, Severity.WARNING)
        so_lieu = cls._do(parse, dau_ra)

        dat = exit_code in parse.success_exit_codes and not loi

        # BẰNG CHỨNG ĐÃ LÀM VIỆC. Mã thoát 0 chỉ nói công cụ không thấy lý do
        # phàn nàn — nó không nói công cụ đã làm gì. Pack khai `require_regex`
        # thì đầu ra phải mang dấu hiệu ấy, nếu không thì ĐẠT là một lời khai
        # không có gì đỡ.
        thieu_bang_chung = False
        mau_doi = getattr(parse, "require_regex", None)
        if dat and mau_doi and not re.search(mau_doi, dau_ra, flags=re.MULTILINE):
            dat = False
            thieu_bang_chung = True
            loi = loi + [
                ToolError(
                    "Công cụ thoát 0 nhưng đầu ra KHÔNG có dấu hiệu nào chứng "
                    "minh nó đã làm việc (pack đòi: "
                    f"{mau_doi!r}). Một phép kiểm không kiểm gì là KHÔNG ĐẠT, "
                    "không phải đạt. Đầu ra thô:\n"
                    f"{dau_ra.strip()[:2000]}"
                )
            ]

        if not dat and not loi and not thieu_bang_chung:
            # Công cụ báo hỏng nhưng biểu thức bắt lỗi không khớp gì. Không được
            # im lặng: giữ lại đầu ra thô làm thông báo, và nói rõ là quy tắc
            # parse của pack cần chỉnh.
            #
            # Và đánh dấu là LỖI CẤU HÌNH: thứ cần sửa là một biểu thức chính
            # quy trong `pack.yaml`, không nằm trong tệp mã đang xét. Mô hình
            # không sửa được nó, nên mở vòng tự sửa ở đây chỉ đốt ba lượt gọi
            # và làm hỏng mã đang đúng — đúng như SL-133, chỉ khác cổng.
            so_lieu["config_error"] = True
            loi = [
                ToolError(
                    f"Công cụ thoát với mã {exit_code} nhưng quy tắc "
                    f"parse của pack không bắt được lỗi nào.\n"
                    "Đây là lỗi CẤU HÌNH của Platform Pack, KHÔNG PHẢI LỖI MÃ: "
                    "sửa `parse.error_regex` (hoặc cờ dòng lệnh) trong pack.yaml "
                    "cho khớp đầu ra thật dưới đây.\n"
                    f"{dau_ra.strip()[:2000]}"
                )
            ]

        so_lieu["exit_code"] = exit_code

        return ToolReport(
            gate=gate,
            passed=dat,
            errors=loi,
            warnings=canh_bao,
            metrics=so_lieu,
            raw_output=dau_ra,
        )

    @staticmethod
    def _bat(mau: str | None, dau_ra: str, severity: str) -> list[ToolError]:
        if not mau:
            return []
        ket_qua: list[ToolError] = []
        for khop in re.finditer(mau, dau_ra, flags=re.MULTILINE):
            nhom = khop.groupdict()
            so_dong = nhom.get("line")
            ket_qua.append(
                ToolError(
                    message=(nhom.get("msg") or khop.group(0)).strip(),
                    severity=severity,
                    file=nhom.get("file"),
                    line=int(so_dong) if so_dong and so_dong.isdigit() else None,
                )
            )
        return ket_qua

    @staticmethod
    def _do(parse: ParseSpec, dau_ra: str) -> dict[str, Any]:
        so_lieu: dict[str, Any] = {}
        for ten, mau in parse.metric_regex.items():
            khop = re.search(mau, dau_ra, flags=re.MULTILINE)
            if not khop:
                continue
            gia_tri = khop.group(1)
            try:
                so_lieu[ten] = int(gia_tri)
            except ValueError:
                try:
                    so_lieu[ten] = float(gia_tri)
                except ValueError:
                    so_lieu[ten] = gia_tri
        return so_lieu
