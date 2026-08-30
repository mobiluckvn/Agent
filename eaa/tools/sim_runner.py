"""Bộ chạy mô phỏng — khung tổng quát, mô hình vật lý do dự án cung cấp.

EAA-SAD-02 ADR-05 (bộ mô phỏng tự viết thay công cụ mô phỏng có sẵn),
EAA-SRS-01 FR-SIM-01,
Ma trận Người–AI công đoạn C1/C2. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-11.

Module này được Platform Pack gọi như một công cụ ngoài (khai báo ở năng lực
``sim`` trong ``pack.yaml``), nên nó chạy như một tiến trình riêng và in số
liệu ra thiết bị ra chuẩn theo đúng khuôn mà quy tắc parse của pack chờ đợi.

**Engine không biết con lắc ngược là gì.** Nó chỉ biết ba khái niệm:

* *plant* — một vật thể có ``reset()``, ``step(u, dt)``, ``state`` và ``fallen``;
* *controller* — một vật thể có ``reset()`` và ``step(measurement, dt) -> lệnh``;
* *scenario* — thời lượng, trạng thái đầu, nhiễu loạn, và các ngưỡng phải đạt.

Cả ba do DỰ ÁN cung cấp. Nhờ vậy một dự án khác — cánh tay máy, xe dò đường,
bộ điều nhiệt — dùng lại được đúng bộ khung này mà không sửa engine.

Hai chế độ, đúng phân vai của công đoạn C1 và C2:

* ``python:<tệp>:<hàm>`` — **MIL**: bộ điều khiển là mã Python của dự án. Dùng
  để quét tham số hàng loạt và khoanh vùng ổn định.
* ``process:<argv…>`` — **SIL**: bộ điều khiển là một tiến trình ngoài, thường
  là chính firmware đã biên dịch cho máy chủ qua lớp giả lập phần cứng. Trao
  đổi bằng JSON từng dòng qua stdin/stdout.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

import yaml

__all__ = [
    "SimError",
    "Scenario",
    "SimResult",
    "FaultSpec",
    "FAULT_KINDS",
    "load_module",
    "run_scenario",
    "sweep",
    "main",
]


class SimError(Exception):
    """Không dựng hoặc không chạy được mô phỏng."""


# --------------------------------------------------------------------------
# Kịch bản và kết quả
# --------------------------------------------------------------------------


#: Bốn kiểu hỏng tiêm được, đặt tên theo HÀNH VI chứ không theo linh kiện —
#: engine không được biết tên một họ cảm biến nào (N-063, FR-PLT-01).
#:
#: * ``stuck``     — số đo đứng yên ở giá trị cuối. Kiểu hỏng khó nhất, vì giá
#:   trị vẫn nằm trong dải hợp lý; không phát hiện được bằng kiểm biên.
#: * ``garbage``   — số đo nhảy ra ngoài dải vật lý.
#: * ``dropout``   — mất mẫu: không có số đo mới trong khoảng thời gian ấy.
#: * ``power_sag`` — nguồn sụt: cơ cấu chấp hành chỉ ra được một phần lực lệnh.
FAULT_KINDS: tuple[str, ...] = ("stuck", "garbage", "dropout", "power_sag")


@dataclass
class FaultSpec:
    """Một lỗi tiêm vào mô phỏng — N-063, lấy từ danh sách hỏng hóc ở N-016."""

    kind: str
    at_s: float = 0.0
    #: 0 nghĩa là hỏng rồi không hồi phục — đúng dạng của phần lớn hỏng hóc thật.
    duration_s: float = 0.0
    magnitude: float = 1.0

    def __post_init__(self) -> None:
        if self.kind not in FAULT_KINDS:
            raise SimError(
                f"Kiểu hỏng {self.kind!r} không nhận biết (hợp lệ: {list(FAULT_KINDS)})"
            )
        if self.at_s < 0 or self.duration_s < 0:
            raise SimError(f"Lỗi {self.kind!r} có mốc thời gian âm")

    def active_at(self, t: float) -> bool:
        if t < self.at_s:
            return False
        return self.duration_s <= 0 or t < self.at_s + self.duration_s

    @classmethod
    def from_dict(cls, data: Any) -> "FaultSpec":
        if not isinstance(data, dict):
            raise SimError(f"mục tiêm lỗi phải là ánh xạ, nhận {type(data)}")
        return cls(
            kind=str(data.get("kind", "")),
            at_s=float(data.get("at_s", 0.0)),
            duration_s=float(data.get("duration_s", 0.0)),
            magnitude=float(data.get("magnitude", 1.0)),
        )


@dataclass
class Scenario:
    """Một kịch bản mô phỏng, đọc từ ``scenarios.yaml`` của dự án."""

    name: str
    duration_s: float = 5.0
    description: str = ""
    initial: dict[str, float] = field(default_factory=dict)
    disturbances: list[dict[str, float]] = field(default_factory=list)
    sensor: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    #: Lỗi tiêm vào trong lượt chạy này (N-063).
    faults: list[FaultSpec] = field(default_factory=list)

    @property
    def injects_faults(self) -> bool:
        return bool(self.faults)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        if not data.get("name"):
            raise SimError("Kịch bản thiếu trường 'name'")
        return cls(
            name=str(data["name"]),
            duration_s=float(data.get("duration_s", 5.0)),
            description=str(data.get("description", "")),
            initial=dict(data.get("initial") or {}),
            disturbances=list(data.get("disturbances") or []),
            sensor=dict(data.get("sensor") or {}),
            thresholds=dict(data.get("thresholds") or {}),
            faults=[FaultSpec.from_dict(f) for f in (data.get("faults") or [])],
        )


@dataclass
class SimResult:
    """Kết quả một lượt chạy, kèm phán quyết đạt/không đạt."""

    scenario: str
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)
    samples: int = 0

    def render(self) -> str:
        """In ra khuôn mà quy tắc parse của pack đọc được."""
        dong = [f"scenario={self.scenario}", f"stable={'true' if self.passed else 'false'}"]
        dong += [f"{k}={v:.6g}" for k, v in sorted(self.metrics.items())]
        for vi_pham in self.violations:
            dong.append(f"violation: {vi_pham}")
        return "\n".join(dong)


# --------------------------------------------------------------------------
# Nạp thành phần của dự án
# --------------------------------------------------------------------------


def load_module(path: str | Path, ten: str = "eaa_sim_project"):
    """Nạp một tệp Python của dự án như một module.

    Nạp theo ĐƯỜNG DẪN chứ không theo tên gói: mô hình vật lý thuộc thư mục dự
    án, nằm ngoài cây gói của engine, và engine không được phép giả định dự án
    đã được cài đặt ở đâu đó trong ``sys.path``.
    """
    path = Path(path)
    if not path.is_file():
        raise SimError(f"Không tìm thấy tệp mô hình: {path}")

    spec = importlib.util.spec_from_file_location(f"{ten}_{path.stem}", path)
    if spec is None or spec.loader is None:  # pragma: no cover - đường dẫn lạ
        raise SimError(f"Không nạp được module từ {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProcessController:
    """Bộ điều khiển là một tiến trình ngoài — chế độ SIL.

    Giao thức cố ý tối giản: mỗi chu kỳ gửi một dòng JSON số đo, đọc lại một
    dòng JSON có khóa ``u``. Đủ đơn giản để lớp giả lập phần cứng trong firmware
    hiện thực bằng vài chục dòng C, và đủ tường minh để gỡ rối bằng mắt.
    """

    def __init__(self, argv: list[str], *, timeout_s: float = 30.0) -> None:
        self.argv = argv
        self.timeout_s = timeout_s
        self.proc: subprocess.Popen[str] | None = None

    def reset(self) -> None:
        self.close()
        try:
            self.proc = subprocess.Popen(
                self.argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise SimError(
                f"Không chạy được bộ điều khiển ngoài {self.argv[0]!r}: {exc}. "
                "Cổng mô phỏng KHÔNG được coi là đạt khi thiếu công cụ."
            ) from exc

    def step(self, measurement: dict[str, float], dt: float) -> float:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise SimError("Bộ điều khiển ngoài chưa được khởi động")
        self.proc.stdin.write(json.dumps({**measurement, "dt": dt}) + "\n")
        self.proc.stdin.flush()

        dong = self.proc.stdout.readline()
        if not dong:
            loi = (self.proc.stderr.read() if self.proc.stderr else "").strip()
            raise SimError(
                "Bộ điều khiển ngoài dừng giữa chừng"
                + (f": {loi[:500]}" if loi else " mà không nói gì")
            )
        try:
            return float(json.loads(dong)["u"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SimError(
                f"Bộ điều khiển ngoài trả về dòng không hợp lệ: {dong.strip()[:200]!r}"
            ) from exc

    def close(self) -> None:
        if self.proc is not None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:  # pragma: no cover - dọn dẹp không được phép nổ
                self.proc.kill()
            self.proc = None


def build_controller(spec: str, params: dict[str, Any]) -> Any:
    """Dựng bộ điều khiển từ chuỗi mô tả."""
    if spec.startswith("python:"):
        phan = spec.split(":", 2)
        if len(phan) < 2 or not phan[1]:
            raise SimError(f"Mô tả bộ điều khiển không hợp lệ: {spec!r}")
        duong_dan = phan[1]
        ten_ham = phan[2] if len(phan) > 2 and phan[2] else "create"
        module = load_module(duong_dan, "eaa_sim_controller")
        try:
            factory = getattr(module, ten_ham)
        except AttributeError as exc:
            raise SimError(
                f"{duong_dan} không có hàm {ten_ham!r} để dựng bộ điều khiển"
            ) from exc
        return factory(params)

    if spec.startswith("process:"):
        argv = spec[len("process:") :].split()
        if not argv:
            raise SimError("Mô tả tiến trình rỗng")
        return ProcessController(argv)

    raise SimError(
        f"Không hiểu mô tả bộ điều khiển {spec!r}. Dạng hợp lệ: "
        "'python:<tệp>:<hàm>' hoặc 'process:<lệnh> <tham số…>'"
    )


# --------------------------------------------------------------------------
# Vòng chạy
# --------------------------------------------------------------------------


class _TiemLoi:
    """Áp lỗi lên số đo và lên lệnh chấp hành (N-063).

    Nằm GIỮA mô hình và bộ điều khiển, không nằm trong mô hình: một mô hình có
    sẵn chỗ để hỏng thì mãi mãi chỉ hỏng theo những cách đã nghĩ ra lúc viết
    nó. Đặt ở đây thì thêm một kiểu hỏng là thêm một dòng YAML ở kịch bản.
    """

    #: Ngoài dải này thì số đo là rác theo bất kỳ nghĩa vật lý nào của một góc.
    GOC_RAC_RAD = 100.0

    def __init__(self, faults: Sequence[FaultSpec]) -> None:
        self.faults = list(faults)
        self._giu: tuple[float, float] | None = None
        self.applied: dict[str, int] = {}

    def _dang_hong(self, kind: str, t: float) -> FaultSpec | None:
        for f in self.faults:
            if f.kind == kind and f.active_at(t):
                return f
        return None

    def measure(self, goc: float, toc_do: float, t: float) -> tuple[float, float]:
        if self._giu is None:
            self._giu = (goc, toc_do)

        loi = (
            self._dang_hong("stuck", t)
            or self._dang_hong("dropout", t)
            or self._dang_hong("garbage", t)
        )
        if loi is None:
            self._giu = (goc, toc_do)
            return goc, toc_do

        self.applied[loi.kind] = self.applied.get(loi.kind, 0) + 1
        if loi.kind in ("stuck", "dropout"):
            # Mất mẫu và kẹt số đo trông giống nhau ở đầu vào bộ điều khiển:
            # cả hai đều là "không có tin mới". Khác nhau ở chỗ firmware thật
            # CÓ THỂ phân biệt được (một bên cờ dữ liệu sẵn sàng không bật),
            # nên chúng vẫn là hai kiểu hỏng riêng ở danh sách N-016.
            return self._giu
        # garbage: đẩy ra ngoài mọi dải vật lý của một góc.
        rac = self.GOC_RAC_RAD * max(1.0, loi.magnitude)
        return rac, rac

    def actuate(self, u: float, t: float) -> float:
        loi = self._dang_hong("power_sag", t)
        if loi is None:
            return u
        self.applied["power_sag"] = self.applied.get("power_sag", 0) + 1
        # magnitude là phần lực CÒN LẠI: 0,3 nghĩa là sụt còn 30%.
        return u * max(0.0, min(1.0, loi.magnitude))


def _trang_thai_an_toan(controller: Any) -> bool | None:
    """Bộ điều khiển có báo mình đã vào chế độ an toàn không.

    Hợp đồng cố ý tối giản và TÙY CHỌN: thuộc tính ``safe`` hoặc phương thức
    ``is_safe()``. Không có cả hai thì trả ``None`` — *không kiểm được*, và đó
    là câu trả lời trung thực. Trả ``False`` sẽ là một lời khẳng định (hệ KHÔNG
    vào chế độ an toàn) mà ta không có căn cứ để nói.
    """
    ham = getattr(controller, "is_safe", None)
    if callable(ham):
        return bool(ham())
    if hasattr(controller, "safe"):
        return bool(getattr(controller, "safe"))
    return None


def run_scenario(
    plant: Any,
    controller: Any,
    scenario: Scenario,
    *,
    control_period_s: float = 0.01,
    substeps: int = 10,
    sensor: Any = None,
    actuator: Any = None,
) -> SimResult:
    """Chạy một kịch bản khép kín và chấm theo ngưỡng của nó."""
    if control_period_s <= 0 or substeps < 1:
        raise SimError("Chu kỳ điều khiển và số bước tích phân phải dương")

    goc_ban_dau = math.radians(float(scenario.initial.get("theta_deg", 0.0)))
    plant.reset(
        theta=goc_ban_dau,
        theta_dot=float(scenario.initial.get("theta_dot", 0.0)),
    )
    controller.reset()
    if sensor is not None:
        sensor.reset()
    if actuator is not None:
        actuator.reset()

    dt_con = control_period_s / substeps
    so_chu_ky = int(round(scenario.duration_s / control_period_s))
    # Nhiễu loạn trải trên một khoảng thời gian, không chỉ một chu kỳ điều
    # khiển: một xung 10 ms truyền cho robot 1 kg chưa tới 2 cm/s — quá nhỏ để
    # thử được bất cứ điều gì, và kịch bản "kháng nhiễu" sẽ luôn qua một cách
    # vô nghĩa.
    nhieu: dict[int, float] = {}
    for d in scenario.disturbances:
        bat_dau = int(round(float(d.get("at_s", 0.0)) / control_period_s))
        thoi_luong = max(1, int(round(float(d.get("duration_s", 0.05)) / control_period_s)))
        for k in range(bat_dau, bat_dau + thoi_luong):
            nhieu[k] = nhieu.get(k, 0.0) + float(d.get("impulse_n", 0.0))

    goc_max = 0.0
    # Định nghĩa chuẩn của thời gian ổn định: thời điểm CUỐI CÙNG tín hiệu ra
    # khỏi dải, tính từ sự kiện kích thích gần nhất.
    #
    # Hai cách hiểu sai đã thử và loại bỏ. Đo từ gốc thời gian: với kịch bản
    # nhiễu ở giây thứ 5, "ổn định lúc 5,3s" chẳng nói gì về chất lượng điều
    # khiển và trượt mọi ngưỡng hợp lý. Đo từ lần lệch GẦN NHẤT: hệ dao động
    # nhẹ quanh mép dải sẽ luôn cho ra một con số bé xíu và đẹp đẽ, che mất
    # việc nó chưa bao giờ thật sự đứng yên.
    lan_cuoi_ra_khoi_dai: float | None = None
    nguong_on_dinh = math.radians(float(scenario.thresholds.get("steady_state_deg", 1.0)))
    can_lien_tiep = int(round(0.5 / control_period_s))  # cửa sổ đo trạng thái xác lập
    da_nga = False

    # Mốc tính thời gian ổn định: thời điểm kết thúc nhiễu loạn cuối cùng. Với
    # kịch bản không có nhiễu thì là gốc thời gian.
    moc_kich_thich = 0.0
    for d in scenario.disturbances:
        moc_kich_thich = max(
            moc_kich_thich,
            float(d.get("at_s", 0.0)) + float(d.get("duration_s", 0.05)),
        )
    goc_cuoi_ky: list[float] = []

    tiem = _TiemLoi(scenario.faults) if scenario.faults else None
    da_vao_an_toan = False
    biet_an_toan = _trang_thai_an_toan(controller) is not None

    for i in range(so_chu_ky):
        t = i * control_period_s
        trang_thai = plant.state

        if sensor is not None:
            goc_do, toc_do_do = sensor.measure(trang_thai, control_period_s)
        else:
            goc_do, toc_do_do = trang_thai.theta, trang_thai.theta_dot

        if tiem is not None:
            goc_do, toc_do_do = tiem.measure(goc_do, toc_do_do, t)

        u = float(
            controller.step(
                {
                    "angle": goc_do,
                    "rate": toc_do_do,
                    # Firmware thật suy ra vận tốc từ số xung bước đã phát; ở
                    # đây lấy thẳng từ mô hình. Không có đại lượng này thì bộ
                    # điều khiển không có cách nào biết mình đang trôi đi.
                    "speed": trang_thai.x_dot,
                    "t": t,
                },
                control_period_s,
            )
        )
        if biet_an_toan and _trang_thai_an_toan(controller):
            da_vao_an_toan = True

        if actuator is not None:
            u = actuator.apply(u, trang_thai, control_period_s)
        if tiem is not None:
            # Nguồn sụt áp SAU mô hình chấp hành: nó làm yếu lực thật sự ra
            # được, chứ không sửa lệnh mà bộ điều khiển nghĩ mình đã phát.
            u = tiem.actuate(u, t)
        u += nhieu.get(i, 0.0)

        for _ in range(substeps):
            plant.step(u, dt_con)

        goc = abs(plant.state.theta)
        goc_max = max(goc_max, goc)

        if goc > nguong_on_dinh:
            lan_cuoi_ra_khoi_dai = t

        if i >= so_chu_ky - can_lien_tiep:
            goc_cuoi_ky.append(goc)

        if getattr(plant, "fallen", False):
            da_nga = True
            break

    so_lieu: dict[str, float] = {
        "max_angle_deg": math.degrees(goc_max),
        "settling_time_s": _thoi_gian_on_dinh(
            lan_cuoi_ra_khoi_dai, moc_kich_thich, scenario.duration_s, da_nga
        ),
        "final_angle_deg": math.degrees(goc_cuoi_ky[-1]) if goc_cuoi_ky else math.degrees(goc_max),
        "steady_state_deg": math.degrees(max(goc_cuoi_ky)) if goc_cuoi_ky else -1.0,
    }
    if actuator is not None:
        so_lieu["step_slips"] = float(getattr(actuator, "slips", 0))

    if tiem is not None:
        so_lieu["faults_injected"] = float(len(scenario.faults))
        so_lieu["fault_cycles"] = float(sum(tiem.applied.values()))
        # -1 = KHÔNG KIỂM ĐƯỢC (bộ điều khiển không báo trạng thái an toàn).
        # Tách khỏi 0 = đã kiểm và KHÔNG vào. Gộp hai cái ấy vào một cờ nhị
        # phân là đúng chỗ thông tin bị mất — cùng lỗi với "nạp không báo lỗi
        # nghĩa là nạp đúng" ở N-075.
        so_lieu["safe_state_entered"] = (
            float(da_vao_an_toan) if biet_an_toan else -1.0
        )

    vi_pham = _cham_diem(scenario, so_lieu, da_nga)
    return SimResult(
        scenario=scenario.name,
        passed=not vi_pham,
        metrics=so_lieu,
        violations=vi_pham,
        samples=so_chu_ky,
    )


def _thoi_gian_on_dinh(
    lan_cuoi_ra: float | None, moc: float, duration: float, da_nga: bool
) -> float:
    """Thời gian từ kích thích cuối tới lúc tín hiệu ở yên trong dải.

    Trả ``-1`` khi hệ chưa bao giờ đứng yên — kể cả khi nó còn dao động ngay ở
    những giây cuối. Một hệ vẫn đang lắc lúc hết giờ thì không có thời gian ổn
    định, và báo con số nào cũng là bịa.
    """
    if da_nga:
        return -1.0
    if lan_cuoi_ra is None:
        return 0.0
    if lan_cuoi_ra > duration - 0.5:
        return -1.0
    return max(0.0, lan_cuoi_ra - moc)


def _cham_diem(scenario: Scenario, so_lieu: dict[str, float], da_nga: bool) -> list[str]:
    """Đối chiếu số liệu với ngưỡng của kịch bản.

    Robot ngã là hỏng dứt khoát, không cần xét thêm ngưỡng nào: đây chính là
    chỗ cổng mô phỏng trở thành cổng chặn thật (TC-12).
    """
    vi_pham: list[str] = []

    # Kịch bản tiêm lỗi đòi chế độ an toàn thì phép kiểm ấy chạy TRƯỚC cả phép
    # kiểm ngã: một hệ ngã mà không kịp vào chế độ an toàn hỏng theo hai cách,
    # và cách thứ hai mới là cách nguy hiểm — nó nghĩa là cơ cấu chấp hành vẫn
    # đang được cấp lệnh trong lúc mọi thứ đã sai.
    if scenario.thresholds.get("require_safe_state"):
        vao = so_lieu.get("safe_state_entered", -1.0)
        if vao < 0:
            vi_pham.append(
                "kịch bản đòi vào chế độ an toàn nhưng bộ điều khiển KHÔNG báo "
                "trạng thái an toàn (thiếu thuộc tính 'safe' hoặc 'is_safe()'), "
                "nên KHÔNG kiểm được — không phải là đạt"
            )
        elif vao == 0:
            vi_pham.append(
                "đã tiêm lỗi mà hệ KHÔNG vào chế độ an toàn — cơ cấu chấp hành "
                "vẫn nhận lệnh trong lúc số đo đã hỏng"
            )

    if da_nga:
        # Ngoại lệ duy nhất, và nó có lý do vật lý chứ không phải lý do tiện
        # tay: một kịch bản tiêm lỗi ĐÒI chế độ an toàn thì chế độ ấy đúng
        # nghĩa là cắt lệnh chấp hành — và một robot bị cắt lệnh thì ngã. Đòi
        # nó vừa vào chế độ an toàn vừa đứng vững là đòi hai điều loại trừ
        # nhau, và kịch bản sẽ không bao giờ đạt dù firmware làm đúng.
        #
        # Ngã ở đây vẫn được GHI vào số liệu; chỉ phán quyết là khác.
        an_toan_da_vao = so_lieu.get("safe_state_entered", -1.0) == 1.0
        if not (scenario.thresholds.get("require_safe_state") and an_toan_da_vao):
            vi_pham.append(
                f"robot ảo NGÃ trong kịch bản {scenario.name!r} — góc vượt biên cứu vãn"
            )
        return vi_pham

    for ten, nguong in scenario.thresholds.items():
        if ten == "require_safe_state":
            continue
        nguong = float(nguong)
        if ten == "max_slips":
            do_duoc = so_lieu.get("step_slips", 0.0)
            if do_duoc > nguong:
                vi_pham.append(f"trượt bước {do_duoc:.0f} lần, trần {nguong:.0f}")
            continue

        if ten == "settling_time_s":
            do_duoc = so_lieu.get(ten, -1.0)
            if do_duoc < 0:
                vi_pham.append(
                    f"không bao giờ ổn định trong {scenario.duration_s:g}s "
                    f"(yêu cầu ≤ {nguong:g}s)"
                )
            elif do_duoc > nguong:
                vi_pham.append(f"thời gian ổn định {do_duoc:.2f}s vượt trần {nguong:g}s")
            continue

        do_duoc = so_lieu.get(ten)
        if do_duoc is None:
            continue
        if do_duoc > nguong:
            vi_pham.append(f"{ten} = {do_duoc:.3f} vượt trần {nguong:g}")

    return vi_pham


# --------------------------------------------------------------------------
# Quét tham số — TC-13
# --------------------------------------------------------------------------


def _to_hop(dai: dict[str, list[float]]) -> Iterator[dict[str, float]]:
    ten = sorted(dai)
    if not ten:
        return
    def de_quy(i: int, hien_tai: dict[str, float]) -> Iterator[dict[str, float]]:
        if i == len(ten):
            yield dict(hien_tai)
            return
        for gia_tri in dai[ten[i]]:
            hien_tai[ten[i]] = float(gia_tri)
            yield from de_quy(i + 1, hien_tai)
    yield from de_quy(0, {})


def sweep(
    make_plant: Any,
    controller_spec: str,
    scenario: Scenario,
    ranges: dict[str, list[float]],
    *,
    control_period_s: float = 0.01,
    substeps: int = 10,
    make_sensor: Any = None,
    make_actuator: Any = None,
) -> list[dict[str, Any]]:
    """Quét tổ hợp tham số, trả bảng kết quả có đánh dấu vùng ổn định.

    Đây là thứ mô phỏng làm được mà robot thật không: chạy hàng trăm cấu hình
    trong vài giây để khoanh vùng, rồi con người mới tinh chỉnh bằng cảm nhận
    vật lý trên thiết bị (công đoạn E2). Máy khoanh vùng, người chọn điểm.
    """
    ket_qua: list[dict[str, Any]] = []
    for tham_so in _to_hop(ranges):
        controller = build_controller(controller_spec, tham_so)
        try:
            r = run_scenario(
                make_plant(),
                controller,
                scenario,
                control_period_s=control_period_s,
                substeps=substeps,
                sensor=make_sensor() if make_sensor else None,
                actuator=make_actuator() if make_actuator else None,
            )
        finally:
            if hasattr(controller, "close"):
                controller.close()
        ket_qua.append({**tham_so, "stable": r.passed, **r.metrics})
    return ket_qua


# --------------------------------------------------------------------------
# Điểm vào dòng lệnh — Platform Pack gọi tới đây
# --------------------------------------------------------------------------


def _nap_cau_hinh(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SimError(f"Không tìm thấy tệp kịch bản: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SimError(f"{path}: YAML không hợp lệ — {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eaa.tools.sim_runner",
        description="Chạy mô phỏng khép kín cho cổng MIL/SIL.",
    )
    parser.add_argument("--model", required=True, help="Tệp Python chứa mô hình vật lý")
    parser.add_argument("--scenarios", required=True, help="Tệp scenarios.yaml của dự án")
    parser.add_argument("--scenario", help="Tên kịch bản; bỏ trống thì chạy tất cả")
    parser.add_argument(
        "--controller",
        required=True,
        help="'python:<tệp>:<hàm>' (MIL) hoặc 'process:<lệnh>' (SIL)",
    )
    parser.add_argument("--params", default="", help="Tham số bộ điều khiển: kp=1,ki=2")
    parser.add_argument("--profile", help="hardware_profile.yaml để lấy tham số vật lý")
    args = parser.parse_args(argv)

    try:
        return _chay(args)
    except SimError as exc:
        print(f"sim error: {exc}", file=sys.stderr)
        return 1


def _chay(args: argparse.Namespace) -> int:
    cau_hinh = _nap_cau_hinh(Path(args.scenarios))
    model = load_module(args.model, "eaa_sim_plant")

    if not hasattr(model, "create_plant"):
        raise SimError(
            f"{args.model} phải có hàm 'create_plant(profile) -> plant'. Engine "
            "không biết mô hình vật lý của dự án được dựng thế nào."
        )

    profile: dict[str, Any] = {}
    if args.profile:
        profile = _nap_cau_hinh(Path(args.profile))

    kich_ban = [Scenario.from_dict(s) for s in (cau_hinh.get("scenarios") or [])]
    if args.scenario:
        kich_ban = [s for s in kich_ban if s.name == args.scenario]
        if not kich_ban:
            raise SimError(
                f"Không có kịch bản {args.scenario!r} trong {args.scenarios}. "
                f"Đang có: {[s['name'] for s in (cau_hinh.get('scenarios') or [])]}"
            )

    tham_so = dict(
        muc.split("=", 1) for muc in args.params.split(",") if "=" in muc
    )
    tham_so = {k.strip(): float(v) for k, v in tham_so.items()}

    chu_ky = float(cau_hinh.get("control_period_ms", 10)) / 1000.0
    substeps = int(cau_hinh.get("substeps", 10))

    tat_ca_dat = True
    for kb in kich_ban:
        controller = build_controller(args.controller, tham_so)
        try:
            ket_qua = run_scenario(
                model.create_plant(profile),
                controller,
                kb,
                control_period_s=chu_ky,
                substeps=substeps,
                sensor=model.create_sensor(kb.sensor) if hasattr(model, "create_sensor") else None,
                actuator=model.create_actuator(profile) if hasattr(model, "create_actuator") else None,
            )
        finally:
            if hasattr(controller, "close"):
                controller.close()

        print(ket_qua.render())
        tat_ca_dat = tat_ca_dat and ket_qua.passed

    return 0 if tat_ca_dat else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
