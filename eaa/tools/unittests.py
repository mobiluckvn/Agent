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

Và một cổng "đạt" mà không nói mình KHÔNG kiểm gì cũng là một loại tin giả nhẹ
hơn (N-053)
------------------------------------------------------------------------------

Chạy trên máy chủ qua lớp phần cứng giả kiểm được tính toán và máy trạng thái —
phần lớn chỗ hay sai. Nhưng nó KHÔNG kiểm được: giá trị thật ghi vào thanh ghi,
độ trễ ngắt, hành vi của ngoại vi, và chu kỳ thật của vòng điều khiển. Một dòng
"12 passed" không phân biệt hai loại ấy, nên người đọc dễ mang cảm giác đã phủ
hết sang bước tiếp theo.

Nên cổng này còn liệt kê ĐÍCH DANH phần nó không với tới, suy từ đồ thị tài
nguyên của chính module đang kiểm. Đó là cảnh báo, không phải lỗi: thiếu sót ấy
không sửa được bằng cách viết thêm test trên máy chủ — nó được đóng ở cổng mô
phỏng và ở nghiệm thu vật lý tại G4.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from typing import Any, Sequence

from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolReport

__all__ = ["UnitTestGate", "host_gaps"]

_TOM_TAT = re.compile(
    r"(?:(?P<passed>\d+) passed)|(?:(?P<failed>\d+) failed)|(?:(?P<errors>\d+) error)"
)


def host_gaps(
    *,
    module_id: str = "",
    graph: Any = None,
    constraints: Any = None,
    registers: Sequence[str] = (),
    resources: Sequence[str] = (),
) -> list[str]:
    """Điều bộ test trên máy chủ KHÔNG kiểm được, nêu đích danh (N-053).

    Suy từ dữ liệu của chính module: nó cấu hình thanh ghi nào, chiếm ngoại vi
    nào, và dự án có ràng buộc thời gian nào. Ba nguồn ấy cho ra ba loại thiếu
    sót khác nhau, và tách chúng ra có ích vì mỗi loại được đóng ở một chỗ
    khác: thanh ghi ở nghiệm thu vật lý, ngoại vi ở chẩn đoán hai kênh, thời
    gian ở cổng mô phỏng rồi tới G4.

    Cố ý KHÔNG cố liệt kê cho đủ mọi thứ. Một danh sách dài và chung chung sẽ
    được lướt qua; ba dòng gọi đúng tên thanh ghi của module này thì không.
    """
    thieu: list[str] = []

    ten_thanh_ghi = list(registers)
    tai_nguyen = list(resources)
    if module_id and graph is not None:
        if not ten_thanh_ghi and hasattr(graph, "registers_for"):
            ten_thanh_ghi = list(graph.registers_for(module_id))
        if not tai_nguyen and hasattr(graph, "resources_of"):
            tai_nguyen = list(graph.resources_of(module_id))

    if ten_thanh_ghi:
        thieu.append(
            "Giá trị thật ghi vào "
            + ", ".join(sorted(ten_thanh_ghi)[:8])
            + (" …" if len(ten_thanh_ghi) > 8 else "")
            + " — lớp phần cứng giả nhận mọi giá trị, kể cả giá trị chip thật "
            "sẽ từ chối. Chỉ nghiệm thu trên thiết bị mới đóng được chỗ này."
        )
    if tai_nguyen:
        thieu.append(
            "Hành vi thật của "
            + ", ".join(sorted(tai_nguyen))
            + " — thời điểm cờ dựng, thứ tự sự kiện, và cách ngoại vi phản ứng "
            "khi bị dùng sai. Đóng ở chẩn đoán hai kênh (eaa diagnose)."
        )

    gioi_han = getattr(constraints, "limits", {}) or {}
    thoi_gian = sorted(
        k for k in gioi_han if k.endswith(("_ms", "_us", "_ns")) or "loop" in k
    )
    if thoi_gian:
        thieu.append(
            "Ràng buộc thời gian ("
            + ", ".join(thoi_gian)
            + ") — máy chủ chạy nhanh hơn chip nhiều bậc, nên mọi số đo thời "
            "gian ở đây đều vô nghĩa. Đóng ở cổng mô phỏng rồi ở G4."
        )
    return thieu


@dataclass
class UnitTestGate:
    """Cổng 4 — kiểm thử đơn vị."""

    tests_dir: Path
    work_dir: Path
    timeout_s: float = 300.0
    #: Cho phép cổng đạt khi dự án chưa có test nào. Mặc định KHÔNG cho phép.
    allow_empty: bool = False
    name: str = "unittests"
    #: Module đang kiểm, để suy ra phần không kiểm được trên máy chủ (N-053).
    module: str = ""
    graph: Any = None
    constraints: Any = None
    #: Thư mục tiêu đề GIẢ của Platform Pack.
    #:
    #: Đưa vào MÔI TRƯỜNG (`C_INCLUDE_PATH`) chứ không trông vào việc bài kiểm
    #: nhớ viết `-I...`. Lệnh dịch do mô hình tự gõ lại ở mỗi module, và nó đã
    #: quên cờ ấy đúng một lần trong bảy — đủ để đốt một lượt gọi cho một lỗi
    #: không liên quan gì tới mã (SL-148).
    #:
    #: Engine không biết thư mục này tên gì; nó chỉ chuyển tiếp đường dẫn pack
    #: khai (FR-PLT-01).
    mock_include: str = ""

    #: Đuôi tệp là SẢN PHẨM DỊCH của chính bộ test, không phải mã nguồn.
    DUOI_SAN_PHAM_DICH: tuple[str, ...] = (".so", ".dylib", ".dll", ".o", ".a")

    @classmethod
    def _don_san_pham_dich(cls, tests_dir: Path) -> list[str]:
        """Xóa thư viện đã dịch của lần chạy TRƯỚC, trước khi chạy lần này.

        Vì sao phải là cấu trúc chứ không phải một dòng dặn trong prompt: bộ
        test dịch mã C thành thư viện dùng chung rồi nạp bằng ``ctypes``. Nếu
        nó bọc lệnh dịch trong ``try/except`` — và mô hình đã viết đúng như
        thế — thì lệnh dịch hỏng bị nuốt, ``ctypes`` nạp thư viện CÒN SÓT của
        lần chạy trước, và cổng báo ĐẠT trên một tệp nguồn **thậm chí không
        dịch nổi**. Đo được: sau khi xóa một dấu chấm phẩy trong `logic_pid.c`,
        bộ test vẫn xanh 4/4.

        Hợp đồng của pack đã cấm nuốt lỗi dịch. Nhưng một luật chỉ sống trong
        prompt là luật phụ thuộc vào việc mô hình có đọc kỹ hay không. Xóa sản
        phẩm dịch cũ khiến việc nuốt lỗi KHÔNG CÒN CHỖ ẨN: không có thư viện cũ
        thì ``ctypes`` sập, và cổng đỏ đúng lúc phải đỏ.

        Chỉ xóa trong thư mục test, và chỉ những đuôi là sản phẩm dịch — thứ
        lần chạy sau tự tạo lại được.
        """
        da_xoa: list[str] = []
        if not tests_dir.is_dir():
            return da_xoa
        for path in sorted(tests_dir.rglob("*")):
            if path.is_file() and path.suffix in cls.DUOI_SAN_PHAM_DICH:
                path.unlink(missing_ok=True)
                da_xoa.append(path.name)
        return da_xoa

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
                        "không phải là 'đã kiểm chứng'.\n"
                        "\n"
                        "Đây KHÔNG PHẢI LỖI MÃ của module vừa sinh: thứ còn "
                        "thiếu là một phần của DỰ ÁN, không nằm trong tệp đang "
                        "sửa. Không bản vá nào của module làm cổng này đạt "
                        "được.\n"
                        "\n"
                        f"Bộ kiểm chạy bằng PYTEST trên máy chủ: đặt tệp "
                        f"`test_*.py` vào {tests_dir}. Firmware được viết tách "
                        "lớp trừu tượng phần cứng chính là để chạy được ở đây "
                        "(công đoạn C2) — test là mã PYTHON gọi vào lớp giả "
                        "lập, không phải mã C."
                    )
                ],
                # Phân loại là LỖI CẤU HÌNH để orchestrator dừng ngay thay vì mở
                # vòng tự sửa. Cơ chế ấy đã có sẵn và câu nó nói ra đã đúng; cổng
                # này chỉ chưa đặt cờ, nên lỗi rơi vào nhánh mặc định "chắc tại
                # mã" và đốt sạch ba lượt gọi mô hình (SL-133).
                #
                # CHỈ cho trường hợp CHƯA CÓ test. Test có mà đỏ thì đúng là
                # việc của vòng tự sửa — đánh dấu cả hai sẽ tắt vòng ấy ở đúng
                # chỗ nó có ích.
                # `allow_empty` là chế độ CÓ CHỦ Ý cho phép rỗng, nên nó không
                # phải một sai lệch cấu hình — đánh dấu nó là lỗi sẽ dừng cả
                # những lượt chạy đang cố tình bỏ qua cổng này.
                metrics=(
                    {"tests_found": 0}
                    if self.allow_empty
                    else {"tests_found": 0, "config_error": True}
                ),
            )

        self._don_san_pham_dich(tests_dir)

        bat_dau = time.monotonic()
        moi_truong = dict(os.environ)
        if self.mock_include:
            cu = moi_truong.get("C_INCLUDE_PATH", "")
            moi_truong["C_INCLUDE_PATH"] = (
                f"{self.mock_include}{os.pathsep}{cu}" if cu else self.mock_include
            )
        try:
            ket_qua = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--no-header"],
                cwd=str(self.work_dir),
                env=moi_truong,
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

        # Phần KHÔNG kiểm được, nêu kể cả khi mọi test đều xanh — nhất là khi
        # mọi test đều xanh, vì đó đúng là lúc người đọc dễ mang cảm giác đã
        # phủ hết sang bước tiếp theo (N-053).
        khong_kiem_duoc = host_gaps(
            module_id=self.module, graph=self.graph, constraints=self.constraints
        )
        so_lieu["host_gaps"] = len(khong_kiem_duoc)

        return ToolReport(
            gate=self.name,
            passed=dat,
            errors=loi,
            warnings=[
                ToolError(f"KHÔNG kiểm được trên máy chủ: {t}", severity=Severity.INFO)
                for t in khong_kiem_duoc
            ],
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
