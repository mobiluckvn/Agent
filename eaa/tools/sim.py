"""Cổng mô phỏng — mắt xích thứ năm của chuỗi kiểm chứng.

EAA-SDD-03 §2 ("gate mo phong, binding tu PlatformPack + Project"),
EAA-SRS-01 FR-VER-01 và FR-SIM-01, EAA-SAD-02 ADR-05, EAA-STP-04 TC-12/TC-13.

Vai trò của cổng này trong lập luận của đề án: nó thu hẹp vùng **mù vật lý**
(EAA-SAD-02 §8). Compile bắt lỗi cú pháp, phân tích tĩnh bắt vi phạm ràng
buộc, kiểm thử đơn vị bắt lỗi logic — nhưng không cái nào biết robot có đứng
được không. Cổng mô phỏng trả lời đúng câu ấy, và phần nó vẫn không trả lời
được thì thuộc về con người tại Gate G4.

**Điều kiện tiên quyết, không thương lượng** (EAA-SRS-01 §2.2, EAA-STP-04 §3):
bộ mô phỏng phải được kiểm chứng bằng nghiệm giải tích trước khi được dùng làm
cổng chặn. ``tests/test_sim_verification.py`` là phép kiểm chứng đó. Một cổng
dựa trên mô hình chưa kiểm chứng còn tệ hơn không có cổng — nó phát ra phán
quyết có vẻ khách quan về một thứ nó không mô tả đúng.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from eaa.tools.base import CodeArtifact, ToolError, ToolReport
from eaa.tools.runner import ToolRunner

__all__ = ["SimGate", "SimBindings", "parse_sim_output"]

_DONG_SO_LIEU = re.compile(r"^(?P<key>[a-z_]+)=(?P<value>[-\w.]+)\s*$", re.MULTILINE)
_DONG_VI_PHAM = re.compile(r"^violation:\s*(?P<msg>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class SimBindings:
    """Nối cổng mô phỏng với dữ liệu của dự án.

    Engine không biết mô hình vật lý nằm ở đâu hay bộ điều khiển được dựng thế
    nào; nó nhận những đường dẫn ấy như tham số. Đúng phân vai của EAA-SDD-03
    §2: binding đến từ Platform Pack và Project, không đến từ engine.
    """

    model: str = "sim/model.py"
    scenarios: str = "sim/scenarios.yaml"
    controller: str = ""
    profile: str = "hardware_profile.yaml"
    #: Kịch bản chạy ở cổng chặn; bỏ trống nghĩa là chạy tất cả.
    scenario: str = ""

    @classmethod
    def from_project(cls, project_dir: str | Path, **ghi_de: Any) -> "SimBindings":
        project_dir = Path(project_dir)
        mac_dinh = dict(
            model=str(project_dir / "sim" / "model.py"),
            scenarios=str(project_dir / "sim" / "scenarios.yaml"),
            controller=f"python:{project_dir / 'sim' / 'controller.py'}:create",
            profile=str(project_dir / "hardware_profile.yaml"),
        )
        mac_dinh.update({k: v for k, v in ghi_de.items() if v})
        return cls(**mac_dinh)

    @property
    def available(self) -> bool:
        return Path(self.model).is_file() and Path(self.scenarios).is_file()


def parse_sim_output(dau_ra: str) -> tuple[dict[str, Any], list[str], list[str]]:
    """Bóc số liệu, danh sách vi phạm và tên kịch bản từ đầu ra bộ chạy mô phỏng."""
    so_lieu: dict[str, Any] = {}
    kich_ban: list[str] = []

    for khop in _DONG_SO_LIEU.finditer(dau_ra):
        khoa, gia_tri = khop.group("key"), khop.group("value")
        if khoa == "scenario":
            kich_ban.append(gia_tri)
            continue
        if khoa == "stable":
            so_lieu.setdefault("scenarios_stable", 0)
            so_lieu["scenarios_stable"] += 1 if gia_tri == "true" else 0
            continue
        try:
            so = float(gia_tri)
        except ValueError:
            continue
        # Nhiều kịch bản chạy nối tiếp: giữ giá trị XẤU NHẤT của mỗi số liệu.
        # Báo cáo trung bình sẽ che mất đúng kịch bản đã hỏng.
        if khoa in so_lieu:
            so_lieu[khoa] = max(so_lieu[khoa], so) if khoa != "settling_time_s" else (
                -1.0 if -1.0 in (so_lieu[khoa], so) else max(so_lieu[khoa], so)
            )
        else:
            so_lieu[khoa] = so

    vi_pham = [m.group("msg").strip() for m in _DONG_VI_PHAM.finditer(dau_ra)]
    return so_lieu, vi_pham, kich_ban


@dataclass
class SimGate:
    """Cổng 5 — chạy mô phỏng khép kín và chặn nếu robot ảo không đứng được."""

    runner: ToolRunner
    bindings: SimBindings
    #: Tham số bộ điều khiển truyền vào mô phỏng, dạng ``kp=1,ki=2``.
    params: str = ""
    name: str = "sim"

    def run(self, artifact: CodeArtifact | None = None) -> ToolReport:
        if not self.runner.manifest.has("sim"):
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[
                    ToolError(
                        f"Platform Pack {self.runner.manifest.name!r} không khai báo "
                        "năng lực 'sim'. Chuỗi kiểm chứng FR-VER-01 kết thúc bằng "
                        "cổng mô phỏng — thiếu nó thì mã chưa được kiểm ở mức nào "
                        "biết được robot có đứng vững hay không."
                    )
                ],
                metrics={"env_error": True},
            )

        if not self.bindings.available:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[
                    ToolError(
                        f"Dự án thiếu mô hình mô phỏng ({self.bindings.model}) hoặc "
                        f"tệp kịch bản ({self.bindings.scenarios}). Cổng mô phỏng "
                        "KHÔNG được coi là đạt khi không có gì để chạy."
                    )
                ],
                metrics={"env_error": True},
            )

        bao_cao = self.runner.run(
            "sim",
            {
                "sim_model": self.bindings.model,
                "sim_scenarios": self.bindings.scenarios,
                "hal_mock": self.bindings.controller,
                "sim_profile": self.bindings.profile,
                "scenario": self.bindings.scenario or "",
                "sim_params": self.params,
            },
            gate_name=self.name,
        )

        so_lieu, vi_pham, kich_ban = parse_sim_output(bao_cao.raw_output)
        so_lieu.update(bao_cao.metrics)
        so_lieu["scenarios_run"] = len(kich_ban)

        dat = bao_cao.passed and not vi_pham
        loi = list(bao_cao.errors)
        if vi_pham:
            loi = [
                ToolError(
                    "Robot ảo không đạt kịch bản mô phỏng:\n"
                    + "\n".join(f"  • {v}" for v in vi_pham)
                    + "\n\nMã có thể biên dịch sạch và qua mọi cổng trước đó mà vẫn "
                    "hỏng ở đây — đó chính là lý do cổng này tồn tại.",
                    rule_id="sim-scenario",
                )
            ] + loi

        return ToolReport(
            gate=self.name,
            passed=dat,
            errors=loi,
            warnings=bao_cao.warnings,
            metrics=so_lieu,
            raw_output=bao_cao.raw_output,
            duration_s=bao_cao.duration_s,
        )

    # ----------------------------------------------------------------------

    def sweep(
        self, ranges: dict[str, Sequence[float]], *, scenario: str = ""
    ) -> list[dict[str, Any]]:
        """Quét tham số — TC-13, và là công cụ của công đoạn C1.

        Chạy trong tiến trình riêng qua đúng năng lực ``sim`` của pack, giống
        hệt lúc làm cổng chặn: nếu quét bằng một đường đi khác thì bộ tham số
        được chọn có thể không phải bộ sẽ bị chấm.
        """
        ket_qua: list[dict[str, Any]] = []
        for to_hop in _to_hop(ranges):
            cong = SimGate(
                runner=self.runner,
                bindings=SimBindings(**{**self.bindings.__dict__, "scenario": scenario or self.bindings.scenario}),
                params=",".join(f"{k}={v}" for k, v in sorted(to_hop.items())),
                name=self.name,
            )
            bao_cao = cong.run()
            ket_qua.append(
                {
                    **to_hop,
                    "stable": bao_cao.passed,
                    **{
                        k: v
                        for k, v in bao_cao.metrics.items()
                        if isinstance(v, (int, float)) and k != "exit_code"
                    },
                }
            )
        return ket_qua

    @staticmethod
    def format_sweep(bang: Sequence[dict[str, Any]], *, limit: int = 20) -> str:
        """Bảng kết quả quét, ĐÁNH DẤU vùng ổn định (yêu cầu của TC-13)."""
        if not bang:
            return "(không có tổ hợp nào được quét)"

        cot_tham_so = [
            k for k in sorted(bang[0]) if k not in ("stable",) and not _la_so_lieu(k)
        ]
        cot_so_lieu = [k for k in sorted(bang[0]) if _la_so_lieu(k)]

        dong = []
        tieu_de = "".join(f"{c:>10}" for c in cot_tham_so)
        tieu_de += "  ổn định" + "".join(f"{c:>16}" for c in cot_so_lieu)
        dong.append(tieu_de)
        dong.append("─" * len(tieu_de))

        on_dinh = [r for r in bang if r.get("stable")]
        xep = sorted(
            bang,
            key=lambda r: (
                not r.get("stable"),
                r.get("settling_time_s", 1e9) if r.get("settling_time_s", -1) >= 0 else 1e9,
            ),
        )
        for r in xep[:limit]:
            d = "".join(f"{r.get(c, ''):>10}" for c in cot_tham_so)
            d += f"  {'✓ ỔN ĐỊNH' if r.get('stable') else '✗ ngã/lệch'}"
            d += "".join(f"{r.get(c, float('nan')):>16.4g}" for c in cot_so_lieu)
            dong.append(d)

        if len(xep) > limit:
            dong.append(f"… còn {len(xep)-limit} tổ hợp nữa")
        dong.append("")
        dong.append(
            f"Vùng ổn định: {len(on_dinh)}/{len(bang)} tổ hợp. Máy khoanh vùng; "
            "người chọn điểm làm việc và tinh chỉnh trên thiết bị thật (công đoạn E2)."
        )
        return "\n".join(dong)


def _la_so_lieu(ten: str) -> bool:
    return ten.endswith(("_s", "_deg", "_slips")) or ten.startswith("scenarios_")


def _to_hop(ranges: dict[str, Sequence[float]]):
    ten = sorted(ranges)
    if not ten:
        return
    def de_quy(i: int, hien_tai: dict[str, float]):
        if i == len(ten):
            yield dict(hien_tai)
            return
        for gia_tri in ranges[ten[i]]:
            hien_tai[ten[i]] = gia_tri
            yield from de_quy(i + 1, hien_tai)
    yield from de_quy(0, {})
