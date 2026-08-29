"""Ráp các module đã merge thành một firmware chạy được.

EAA-SRS-01 FR-VER-01 (chuỗi kiểm chứng), EAA-SDD-03 §2 (Tool Layer), công đoạn
E của máy trạng thái. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-31.

Vòng lặp chuẩn kiểm TỪNG module: dịch được, sạch phân tích tĩnh, qua unit test,
vừa ngân sách bộ nhớ. Bốn câu ấy đúng cho từng mảnh, và không câu nào nói rằng
các mảnh ghép lại thì chạy. Module này trả lời câu còn thiếu.

Ba việc, và việc thứ ba mới là lý do hai việc kia tồn tại
--------------------------------------------------------

1. **Sinh vòng lặp chính** từ khuôn của Platform Pack và bản thiết kế ráp của
   dự án. Engine biết *module nào, gọi hàm nào, mỗi bao nhiêu mili giây*; phần
   chữ C nằm hết ở pack.
2. **Dịch và liên kết** toàn bộ: mọi module đã merge cộng với vòng lặp chính.
   Đây là lần đầu ``main()`` tồn tại, nên cũng là lần đầu liên kết có nghĩa.
3. **Đo lại kích thước ở tầm firmware.** Ở vòng kiểm module, trần
   ``flash_pct_max`` áp lên một module lẻ là phép kiểm dễ dãi hơn nó trông —
   một module chiếm 20% thì "dưới 50%" nghe như đạt, trong khi mười module như
   thế thì không. Con số thật chỉ có sau khi liên kết.

Một module đã merge mà không có trong bản thiết kế ráp là LỖI
--------------------------------------------------------------

Không phải cảnh báo. Merge nghĩa là mã ấy đã qua đủ cổng và đã được người duyệt
tại G3; nếu nó lặng lẽ không vào firmware thì thứ nạp xuống mạch thiếu một
phần mà mọi bằng chứng đều nói là có. Module nào có mặt để module khác gọi chứ
không chạy định kỳ thì khai ``step: null`` — nói ra thì được, im lặng thì không.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from eaa.tools.base import Severity, ToolError, ToolReport
from eaa.tools.compile import SCOPE_FIRMWARE, LinkGate

__all__ = [
    "FirmwareError",
    "ScheduledModule",
    "AssemblyPlan",
    "FirmwareAssembler",
    "DiagnosticFirmwareBuilder",
    "ASSEMBLY_FILE",
]

#: Bản thiết kế ráp, ở tầng dự án — cạnh constraints.yaml.
ASSEMBLY_FILE = "firmware.yaml"


class FirmwareError(Exception):
    """Bản thiết kế ráp sai, hoặc lệch với những gì đã merge."""


@dataclass(frozen=True)
class ScheduledModule:
    """Một module trong firmware, và cách vòng lặp chính gọi tới nó."""

    id: str
    init: str = ""
    #: Hàm chạy định kỳ, chữ ký ``void f(void)``. Rỗng = không chạy định kỳ.
    step: str = ""
    period_ms: int = 0
    note: str = ""
    #: Tệp nguồn của module, tương đối so với thư mục firmware. Bỏ trống thì
    #: tìm theo tên ``<id>.<đuôi>`` — quy ước hợp lý nhưng không phải luật, nên
    #: khai rõ được khi mô hình đặt tên tệp khác id.
    sources: tuple[str, ...] = ()

    @property
    def scheduled(self) -> bool:
        return bool(self.step)


@dataclass(frozen=True)
class AssemblyPlan:
    """Nội dung ``firmware.yaml`` đã kiểm lược đồ."""

    modules: tuple[ScheduledModule, ...]
    tick_ms: int = 1
    image_name: str = "firmware"
    version: int = 1
    path: Path | None = None

    @property
    def scheduled(self) -> tuple[ScheduledModule, ...]:
        return tuple(m for m in self.modules if m.scheduled)

    def ids(self) -> set[str]:
        return {m.id for m in self.modules}

    @classmethod
    def load(cls, path: str | Path) -> "AssemblyPlan":
        path = Path(path)
        if not path.is_file():
            raise FirmwareError(
                f"Không có bản thiết kế ráp firmware: {path}\n"
                "Ráp firmware là một quyết định thiết kế — module nào chạy, mỗi "
                "bao nhiêu mili giây — nên nó được KHAI BÁO chứ không suy đoán."
            )
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise FirmwareError(f"{path}: YAML không hợp lệ — {exc}") from exc
        if not isinstance(du_lieu, dict):
            raise FirmwareError(f"{path}: nội dung phải là ánh xạ khóa–giá trị")

        # Danh sách rỗng là hợp lệ: dự án chưa merge module nào thì bản thiết
        # kế ráp đúng là trống. Lỗi "không có gì để ráp" thuộc về lúc RÁP, và ở
        # đó nó nói được câu hữu ích hơn — xem FirmwareAssembler.run.
        muc = du_lieu.get("modules", [])
        if not isinstance(muc, list):
            raise FirmwareError(f"{path}: 'modules' phải là một danh sách")

        module: list[ScheduledModule] = []
        da_gap: set[str] = set()
        for i, m in enumerate(muc):
            if not isinstance(m, dict) or not m.get("id"):
                raise FirmwareError(f"{path}: mục modules[{i}] thiếu 'id'")
            ten = str(m["id"])
            if ten in da_gap:
                raise FirmwareError(f"{path}: module {ten!r} khai hai lần")
            da_gap.add(ten)

            buoc = str(m.get("step") or "")
            chu_ky = m.get("period_ms", 0)
            if buoc and not isinstance(chu_ky, int):
                raise FirmwareError(
                    f"{path}: module {ten!r} có period_ms không phải số nguyên: {chu_ky!r}"
                )
            if buoc and chu_ky <= 0:
                raise FirmwareError(
                    f"{path}: module {ten!r} chạy định kỳ thì period_ms phải dương "
                    f"(nhận {chu_ky!r}). Chu kỳ 0 nghĩa là chạy mọi vòng lặp — "
                    "muốn vậy thì nói rõ bằng period_ms: 1."
                )
            if not buoc and chu_ky:
                raise FirmwareError(
                    f"{path}: module {ten!r} khai period_ms mà không khai 'step'. "
                    "Một chu kỳ không gắn với hàm nào là một dòng không thi hành được."
                )

            nguon = m.get("sources") or ()
            if isinstance(nguon, str):
                nguon = [nguon]
            if not isinstance(nguon, (list, tuple)):
                raise FirmwareError(
                    f"{path}: module {ten!r} có 'sources' không phải danh sách"
                )

            module.append(
                ScheduledModule(
                    id=ten,
                    init=str(m.get("init") or ""),
                    step=buoc,
                    period_ms=int(chu_ky or 0),
                    note=str(m.get("note") or ""),
                    sources=tuple(str(x) for x in nguon),
                )
            )

        tick = du_lieu.get("tick_ms", 1)
        if not isinstance(tick, int) or tick <= 0:
            raise FirmwareError(f"{path}: tick_ms phải là số nguyên dương")

        return cls(
            modules=tuple(module),
            tick_ms=tick,
            image_name=str(du_lieu.get("image_name", "firmware")),
            version=int(du_lieu.get("version", 1)),
            path=path,
        )

    def check_against_merged(self, merged: Iterable[str]) -> None:
        """Đối chiếu với những module ĐÃ MERGE — xem phần đầu tệp."""
        da_merge = set(merged)
        khai = self.ids()

        thieu = sorted(da_merge - khai)
        if thieu:
            raise FirmwareError(
                f"Module đã merge nhưng không có trong {self.path}: {thieu}.\n"
                "Merge nghĩa là mã ấy đã qua đủ cổng và đã được duyệt tại G3. Bỏ "
                "quên nó ở đây thì firmware nạp xuống mạch thiếu một phần mà mọi "
                "bằng chứng đều nói là có.\n"
                "Không chạy định kỳ thì vẫn phải khai, kèm 'step: null'."
            )

        thua = sorted(khai - da_merge)
        if thua:
            raise FirmwareError(
                f"Bản thiết kế ráp nhắc tới module chưa merge: {thua}.\n"
                "Chỉ mã đã qua G3 mới được vào firmware — không có đường tắt nào "
                "đưa mã chưa duyệt xuống thiết bị."
            )


@dataclass
class FirmwareAssembler:
    """Sinh vòng lặp chính, dịch, liên kết, rồi đo lại ở tầm firmware."""

    runner: Any
    #: Thư mục chứa mã nguồn các module đã merge.
    source_dir: Path
    #: Cổng đo kích thước, để đối chiếu ngưỡng ở tầm firmware.
    size_gate: Any = None
    build_dir: str = "build"
    source_suffixes: tuple[str, ...] = (".c",)
    name: str = "assemble"

    def run(self, plan: AssemblyPlan) -> ToolReport:
        pack = self.runner.manifest
        khuon = getattr(pack, "firmware", None)
        if khuon is None:
            return self._loi_cau_hinh(
                f"Pack {pack.name!r} không khai báo mục 'firmware' — không có "
                "khuôn vòng lặp chính thì engine không tự viết ra được. Khuôn "
                "thuộc về nền tảng, không thuộc về engine."
            )
        if not Path(khuon.template).is_file():
            return self._loi_cau_hinh(f"Không tìm thấy khuôn: {khuon.template}")

        goc = Path(self.runner.work_dir)
        thu_muc_build = goc / self.build_dir
        thu_muc_build.mkdir(parents=True, exist_ok=True)

        try:
            chinh = self._sinh_vong_lap_chinh(khuon, plan, thu_muc_build)
        except FirmwareError as exc:
            return self._loi_cau_hinh(str(exc))

        # Nguồn do pack cấp (mã khởi động, bảng vector…) đi cùng mọi firmware
        # của nền tảng ấy, nên chúng được dịch chung chứ không phải module.
        nguon_pack = [Path(x) for x in getattr(khuon, "sources", ())]
        thieu_pack = [str(p) for p in nguon_pack if not p.is_file()]
        if thieu_pack:
            return self._loi_cau_hinh(
                f"Pack khai nguồn không tìm thấy: {thieu_pack}"
            )

        nguon, thieu = self._nguon_module(plan)
        if thieu:
            return self._loi_cau_hinh(
                f"Không tìm thấy tệp nguồn của module: {sorted(thieu)} "
                f"(đã tìm trong {self.source_dir}).\n"
                "Mặc định engine tìm theo tên '<id>.c' — đó là quy ước, không "
                "phải luật. Mô hình đặt tên tệp khác id thì khai rõ trong bản "
                "thiết kế ráp:\n"
                "    - id: <module>\n"
                "      sources: [src/<tên thật>.c]"
            )

        from eaa.tools.compile import _gop_bao_cao  # dùng chung phép gộp

        bao_cao_dich: list[ToolReport] = []
        doi_tuong: list[Path] = []
        for tep in [*nguon_pack, *nguon, chinh]:
            dich = thu_muc_build / f"{tep.stem}.o"
            r = self.runner.run(
                "compile",
                {
                    "source": self._tuong_doi(tep, goc),
                    "sources": [self._tuong_doi(tep, goc)],
                    "output": self._tuong_doi(dich, goc),
                    "include_dir": self._tuong_doi(self.source_dir, goc),
                },
                gate_name=self.name,
            )
            bao_cao_dich.append(r)
            if r.passed:
                doi_tuong.append(dich)

        gop = _gop_bao_cao(self.name, bao_cao_dich)
        if not gop.passed:
            gop.metrics["stage"] = "compile"
            return gop

        lien_ket = LinkGate(
            self.runner,
            build_dir=self.build_dir,
            image_name=plan.image_name,
            hex_suffix=getattr(khuon, "image_suffix", ".hex"),
        ).run(doi_tuong)
        lien_ket.gate = self.name
        if not lien_ket.passed:
            lien_ket.metrics["stage"] = "link"
            return lien_ket

        lien_ket.metrics["main_source"] = str(chinh)
        lien_ket.metrics["module_count"] = len(plan.modules)
        lien_ket.metrics["scheduled_count"] = len(plan.scheduled)

        if self.size_gate is None:
            return lien_ket

        kich_thuoc = self.size_gate.run(
            lien_ket.metrics["binary"], scope=SCOPE_FIRMWARE
        )
        cuoi = _gop_bao_cao(self.name, [lien_ket, kich_thuoc])
        cuoi.metrics.update(lien_ket.metrics)
        cuoi.metrics.update(kich_thuoc.metrics)
        if not cuoi.passed:
            cuoi.metrics["stage"] = "size"
        return cuoi

    # -- sinh mã ------------------------------------------------------------

    def _sinh_vong_lap_chinh(
        self, khuon: Any, plan: AssemblyPlan, thu_muc_build: Path
    ) -> Path:
        """Thay chỗ giữ trong khuôn của pack — không dùng ``str.format``.

        Khuôn là mã C, mà mã C đầy dấu ngoặc nhọn; ``format`` sẽ vấp ngay dòng
        đầu tiên có một khối lệnh.
        """
        van_ban = Path(khuon.template).read_text(encoding="utf-8")

        includes = [self._thay(khuon.include_line, module=m.id) for m in plan.modules]
        init = [
            self._thay(khuon.init_line, module=m.id, init=m.init)
            for m in plan.modules
            if m.init
        ]
        viec = [
            self._thay(khuon.task_line, module=m.id, step=m.step, period_ms=m.period_ms)
            for m in plan.scheduled
        ]
        if not viec:
            raise FirmwareError(
                "Không module nào chạy định kỳ. Một firmware không có việc gì để "
                "làm thì vòng lặp chính chỉ quay không — nhiều khả năng bản thiết "
                "kế ráp thiếu 'step'."
            )

        thay_the = {
            "{includes}": "\n".join(includes),
            "{init_calls}": "\n".join(init),
            "{tasks}": "\n".join(viec),
            "{tick_ms}": str(plan.tick_ms),
        }
        for cho_giu, gia_tri in thay_the.items():
            van_ban = van_ban.replace(cho_giu, gia_tri)

        con_lai = [c for c in thay_the if c in van_ban]
        if con_lai:
            raise FirmwareError(f"Khuôn còn chỗ giữ chưa thay: {con_lai}")

        dich = thu_muc_build / khuon.output
        dich.write_text(van_ban, encoding="utf-8")
        return dich

    @staticmethod
    def _thay(mau: str, **tham_so: Any) -> str:
        for ten, gia_tri in tham_so.items():
            mau = mau.replace("{" + ten + "}", str(gia_tri))
        return mau

    # -- tiện ích -----------------------------------------------------------

    def _nguon_module(self, plan: AssemblyPlan) -> tuple[list[Path], list[str]]:
        """Tệp nguồn của từng module, và tên những module không tìm thấy nguồn.

        Nêu đích danh module thiếu chứ không chỉ nói "không tìm thấy gì": một
        firmware thiếu đúng một module vẫn liên kết được nếu không ai gọi tới
        nó, và lúc ấy lỗi sẽ lộ ra trên bàn thí nghiệm chứ không ở đây.
        """
        thu_muc = Path(self.source_dir)
        ket_qua: list[Path] = []
        thieu: list[str] = []

        for m in plan.modules:
            cua_module: list[Path] = []
            if m.sources:
                cua_module = [thu_muc / x for x in m.sources]
                vang = [p for p in cua_module if not p.is_file()]
                if vang:
                    thieu.append(m.id)
                    continue
            elif thu_muc.is_dir():
                for duoi in self.source_suffixes:
                    cua_module.extend(sorted(thu_muc.rglob(f"{m.id}{duoi}")))

            if not cua_module:
                thieu.append(m.id)
                continue
            ket_qua.extend(cua_module)

        return ket_qua, thieu

    @staticmethod
    def _tuong_doi(duong_dan: Path, goc: Path) -> str:
        p = Path(duong_dan)
        return str(p.relative_to(goc)) if p.is_absolute() and p.is_relative_to(goc) else str(p)

    def _loi_cau_hinh(self, thong_diep: str) -> ToolReport:
        return ToolReport(
            gate=self.name,
            passed=False,
            errors=[ToolError(thong_diep, severity=Severity.ERROR)],
            metrics={"config_error": True},
        )


# --------------------------------------------------------------------------
# Firmware chẩn đoán — AIS §7, lấp trường firmware_template của Scenario
# --------------------------------------------------------------------------


@dataclass
class DiagnosticFirmwareBuilder:
    """Dựng firmware đo cho một kịch bản chẩn đoán.

    Ghép hai tệp bằng cách LIÊN KẾT chúng, không dán chuỗi: bộ khung của pack
    (bật UART, đóng gói khung telemetry, gọi ``diag_run()``) và phần đo của dự
    án (``firmware_template`` trong ``diagnostics.yaml``). Cả hai đều là mã C
    thật nên bộ dịch kiểm được cả hai — thứ mà một bản chắp chuỗi không cho.

    Kịch bản chưa khai phần đo thì DỪNG, không dựng một firmware rỗng: một ảnh
    nạp được mà không đo gì sẽ chạy, sẽ im lặng, và sẽ bị đọc thành "mạch hỏng".
    """

    runner: Any
    #: Nơi tìm tệp phần đo mà kịch bản trỏ tới.
    project_dir: Path
    build_dir: str = "build"
    name: str = "diag-build"

    def run(self, scenario: Any, frame_spec: Any = None) -> ToolReport:
        pack = self.runner.manifest
        khuon = getattr(pack, "diagnostics", None)
        if khuon is None:
            return self._loi_cau_hinh(
                f"Pack {pack.name!r} không khai báo mục 'diagnostics' — không có "
                "bộ khung firmware đo thì engine không tự viết ra được."
            )
        if not Path(khuon.template).is_file():
            return self._loi_cau_hinh(f"Không tìm thấy bộ khung: {khuon.template}")

        if not getattr(scenario, "firmware_template", ""):
            return self._loi_cau_hinh(
                f"Kịch bản {scenario.id} chưa khai 'firmware_template' trong "
                "diagnostics.yaml, nên không có phần đo để dựng.\n"
                "Engine KHÔNG dựng một firmware rỗng thay vào: một ảnh nạp được "
                "mà không đo gì sẽ chạy, sẽ im lặng, và sự im lặng ấy sẽ bị đọc "
                "thành 'mạch hỏng'."
            )

        phan_do = self.project_dir / scenario.firmware_template
        if not phan_do.is_file():
            return self._loi_cau_hinh(
                f"Kịch bản {scenario.id} trỏ tới phần đo {phan_do} nhưng tệp không có."
            )

        goc = Path(self.runner.work_dir)
        thu_muc_build = goc / self.build_dir
        thu_muc_build.mkdir(parents=True, exist_ok=True)

        bo_khung = self._sinh_bo_khung(khuon, scenario, frame_spec, thu_muc_build)

        from eaa.tools.compile import _gop_bao_cao

        nguon_pack = [Path(x) for x in getattr(khuon, "sources", ())]
        thieu_pack = [str(p) for p in nguon_pack if not p.is_file()]
        if thieu_pack:
            return self._loi_cau_hinh(f"Pack khai nguồn không tìm thấy: {thieu_pack}")

        bao_cao_dich: list[ToolReport] = []
        doi_tuong: list[Path] = []
        for tep in (*nguon_pack, bo_khung, phan_do):
            dich = thu_muc_build / f"{tep.stem}.o"
            r = self.runner.run(
                "compile",
                {
                    "source": self._tuong_doi(tep, goc),
                    "sources": [self._tuong_doi(tep, goc)],
                    "output": self._tuong_doi(dich, goc),
                    "include_dir": self._tuong_doi(phan_do.parent, goc),
                },
                gate_name=self.name,
            )
            bao_cao_dich.append(r)
            if r.passed:
                doi_tuong.append(dich)

        gop = _gop_bao_cao(self.name, bao_cao_dich)
        if not gop.passed:
            gop.metrics["stage"] = "compile"
            return gop

        ten_anh = khuon.image_name.replace("{scenario}", _an_toan(scenario.id))
        lien_ket = LinkGate(
            self.runner,
            build_dir=self.build_dir,
            image_name=ten_anh,
            hex_suffix=getattr(khuon, "image_suffix", ".hex"),
        ).run(doi_tuong)
        lien_ket.gate = self.name
        if not lien_ket.passed:
            lien_ket.metrics["stage"] = "link"
            return lien_ket

        lien_ket.metrics["scenario"] = scenario.id
        lien_ket.metrics["motion"] = bool(getattr(scenario, "motion", False))
        lien_ket.metrics["source"] = str(bo_khung)
        if lien_ket.metrics.get("image"):
            self._ghi_the_kem(Path(lien_ket.metrics["image"]), scenario)
        return lien_ket

    # -- sinh mã ------------------------------------------------------------

    def _sinh_bo_khung(
        self, khuon: Any, scenario: Any, frame_spec: Any, thu_muc_build: Path
    ) -> Path:
        van_ban = Path(khuon.template).read_text(encoding="utf-8")

        # Tên phép kiểm tổng do dự án khai; engine chỉ đổi nó thành một macro
        # theo quy tắc máy móc, không biết phép ấy tính ra sao trên chip.
        ten_kiem = getattr(frame_spec, "checksum", "none") or "none"
        dinh_nghia = (
            f"#define EAA_CHECKSUM_{ten_kiem.upper()} 1" if ten_kiem != "none" else ""
        )

        thay_the = {
            "{scenario_id}": scenario.id,
            "{checksum_define}": dinh_nghia,
            "{separator}": getattr(frame_spec, "separator", "*") or "*",
            "{baud}": str(getattr(frame_spec, "baud", 115200)),
        }
        for cho_giu, gia_tri in thay_the.items():
            van_ban = van_ban.replace(cho_giu, gia_tri)

        ten = khuon.output.replace("{scenario}", _an_toan(scenario.id))
        dich = thu_muc_build / ten
        dich.write_text(van_ban, encoding="utf-8")
        return dich

    @staticmethod
    def _ghi_the_kem(image: Path, scenario: Any) -> Path:
        """Thẻ đi kèm ảnh: kịch bản nào, có chuyển động không, checklist gì.

        ``eaa flash`` đọc thẻ này để đưa cảnh báo an toàn vào đúng lúc người
        sắp bấm đồng ý. Không có nó, một ảnh chẩn đoán làm robot chuyển động
        trông y hệt một ảnh đo tĩnh.
        """
        the = image.with_suffix(image.suffix + ".meta.json")
        the.write_text(
            json.dumps(
                {
                    "scenario": scenario.id,
                    "title": getattr(scenario, "title", ""),
                    "motion": bool(getattr(scenario, "motion", False)),
                    "safety_checklist": list(getattr(scenario, "safety_checklist", ())),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return the

    @staticmethod
    def _tuong_doi(duong_dan: Path, goc: Path) -> str:
        p = Path(duong_dan)
        return str(p.relative_to(goc)) if p.is_absolute() and p.is_relative_to(goc) else str(p)

    def _loi_cau_hinh(self, thong_diep: str) -> ToolReport:
        return ToolReport(
            gate=self.name,
            passed=False,
            errors=[ToolError(thong_diep, severity=Severity.ERROR)],
            metrics={"config_error": True},
        )


def _an_toan(ma: str) -> str:
    """Mã kịch bản thành phần tên tệp dùng được — chỉ giữ chữ, số, gạch."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in ma)
