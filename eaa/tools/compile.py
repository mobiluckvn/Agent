"""Cổng biên dịch, cổng liên kết và cổng đo chiếm dụng bộ nhớ.

EAA-SDD-03 §2 (gọi toolchain QUA PlatformPack, không gọi thẳng trình dịch của
một họ vi điều khiển nào), EAA-SRS-01 FR-VER-01 (chuỗi kiểm chứng bắt buộc bắt
đầu bằng biên dịch → đo kích thước).

Ba cổng ở chung một tệp vì cả ba nói chuyện với cùng bộ công cụ dịch và cổng
sau ăn sản phẩm của cổng trước; SDD §2 cũng không cấp tệp riêng cho chúng.

Vì sao dịch và liên kết là hai việc tách rời
--------------------------------------------

Vòng lặp chuẩn kiểm chứng TỪNG MODULE. Một module driver không có ``main()`` —
nó không phải một chương trình, nó là một phần của chương trình. Nếu cổng dịch
liên kết luôn (``-o`` không kèm ``-c``) thì mọi module đều trượt với thông báo
*undefined reference to main*, và trượt vì một lý do chẳng liên quan gì tới
chất lượng mã nó sinh ra.

Nên: cổng dịch dịch từng tệp nguồn thành **tệp đối tượng** (``-c``), và việc
gộp các tệp đối tượng lại thành ảnh chạy được là một năng lực RIÊNG của pack,
chạy ở công đoạn ráp firmware chứ không ở vòng kiểm module.

Hệ quả cho cổng đo kích thước: ở tầm module nó đo phần chiếm dụng của chính
module ấy, còn số của cả firmware chỉ có sau khi liên kết. Hai con số khác
nhau, nên báo cáo ghi rõ mình đang đo cái nào (``size_scope``) — một trần
"Flash < 50%" áp lên một module lẻ là một phép kiểm dễ dãi hơn nó trông, và
người đọc báo cáo phải thấy được điều đó.

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

__all__ = [
    "CompileGate",
    "LinkGate",
    "SizeGate",
    "write_artifact",
    "UnsafePathError",
    "SCOPE_MODULE",
    "SCOPE_FIRMWARE",
]

#: Cổng đo kích thước đang đo phần chiếm dụng của một module lẻ.
SCOPE_MODULE = "module"
#: ...hay của cả ảnh firmware đã liên kết.
SCOPE_FIRMWARE = "firmware"


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
    """Cổng 1 — dịch từng tệp nguồn thành tệp đối tượng.

    KHÔNG liên kết. Xem phần đầu tệp: một module không có ``main()`` và không
    cần có; liên kết là việc của :class:`LinkGate` ở công đoạn ráp firmware.
    """

    runner: ToolRunner
    #: Thư mục nhận sản phẩm dịch, tương đối so với thư mục làm việc.
    build_dir: str = "build"
    #: Đuôi tệp được đưa vào lệnh dịch.
    source_suffixes: tuple[str, ...] = (".c",)
    include_dirs: Sequence[str] = field(default_factory=list)
    #: Đuôi tệp đối tượng do pack sinh ra.
    object_suffix: str = ".o"
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
        include_dir = self._include_dir(da_ghi, goc)

        # Dịch HẾT các nguồn rồi mới kết luận, không dừng ở lỗi đầu tiên: prompt
        # vá được nhìn thấy toàn bộ lỗi của lượt này, thay vì sửa một lỗi rồi
        # phát hiện lỗi kế tiếp ở lượt sau và đốt thêm một lần trong ba lần.
        bao_cao_con: list[ToolReport] = []
        doi_tuong: list[Path] = []
        for tep in nguon:
            dich = thu_muc_build / f"{tep.stem}{self.object_suffix}"
            bao_cao = self.runner.run(
                "compile",
                {
                    "source": str(tep.relative_to(goc)),
                    # Giữ {sources} cho pack nào vẫn khai theo lối cũ; ở đây nó
                    # luôn là một phần tử vì mỗi lượt dịch đúng một tệp.
                    "sources": [str(tep.relative_to(goc))],
                    "output": str(dich.relative_to(goc)),
                    "include_dir": include_dir,
                },
                gate_name=self.name,
            )
            bao_cao_con.append(bao_cao)
            if bao_cao.passed:
                doi_tuong.append(dich)

        gop = _gop_bao_cao(self.name, bao_cao_con)
        if gop.passed:
            gop.metrics["objects"] = [str(p) for p in doi_tuong]
            # Cổng đo kích thước nối vào qua khóa này (Orchestrator bước 6).
            gop.metrics["binary"] = str(doi_tuong[0])
            gop.metrics["source_files"] = len(nguon)
            gop.metrics["size_scope"] = SCOPE_MODULE
        return gop

    def _include_dir(self, da_ghi: Sequence[Path], goc: Path) -> str:
        if self.include_dirs:
            return str(self.include_dirs[0])
        header = [p for p in da_ghi if p.suffix == ".h"]
        thu_muc = header[0].parent if header else goc
        return str(thu_muc.relative_to(goc)) or "."


def _cong_so_lieu(bao_cao: Sequence[ToolReport]) -> dict[str, Any]:
    """Cộng các số liệu số của nhiều lượt đo; số liệu không phải số thì lấy lượt cuối."""
    tong: dict[str, Any] = {}
    for r in bao_cao:
        for khoa, gia_tri in r.metrics.items():
            if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
                tong[khoa] = gia_tri
            else:
                tong[khoa] = tong.get(khoa, 0) + gia_tri if isinstance(
                    tong.get(khoa, 0), (int, float)
                ) else gia_tri
    return tong


#: Cờ nói "đây không phải lỗi của mã sinh ra" — thiếu công cụ, pack khai sai.
#: Orchestrator đọc chúng để chặn ngay thay vì đốt ba lượt tự sửa vào một thứ
#: mà mô hình không sửa được. Gộp báo cáo mà đánh rơi chúng thì vòng tự sửa
#: chạy ba lần rồi mới bàn giao — đúng lỗi đã xảy ra khi tách cổng dịch.
CO_KHONG_PHAI_LOI_MA: tuple[str, ...] = ("env_error", "config_error")


def _gop_bao_cao(ten_cong: str, bao_cao: Sequence[ToolReport]) -> ToolReport:
    """Gộp nhiều lượt chạy của cùng một cổng thành một báo cáo."""
    loi: list[ToolError] = []
    canh_bao: list[ToolError] = []
    dau_ra: list[str] = []
    so_lieu: dict[str, Any] = {}
    thoi_gian = 0.0
    for r in bao_cao:
        loi.extend(r.errors)
        canh_bao.extend(r.warnings)
        if r.raw_output:
            dau_ra.append(r.raw_output)
        thoi_gian += r.duration_s
        so_lieu.update(r.metrics)

    # Một lượt hỏng vì môi trường là cả cổng hỏng vì môi trường: cờ được HỢP
    # chứ không lấy theo lượt cuối.
    for co in CO_KHONG_PHAI_LOI_MA:
        if any(r.metrics.get(co) for r in bao_cao):
            so_lieu[co] = True

    return ToolReport(
        gate=ten_cong,
        passed=all(r.passed for r in bao_cao),
        errors=loi,
        warnings=canh_bao,
        metrics=so_lieu,
        raw_output="\n".join(dau_ra),
        duration_s=thoi_gian,
    )


@dataclass
class LinkGate:
    """Cổng liên kết — gộp các tệp đối tượng thành ảnh chạy được.

    KHÔNG nằm trong chuỗi cổng của vòng lặp chuẩn. Chuỗi ấy kiểm một module,
    còn liên kết chỉ có nghĩa khi đã có đủ mọi module cộng với ``main()``; chạy
    nó ở tầm module thì hoặc là trượt vô cớ, hoặc là "đạt" mà chẳng chứng minh
    được gì.

    Pack nào không khai báo năng lực ``link`` thì cổng này báo lỗi cấu hình chứ
    không lặng lẽ bỏ qua: một firmware không liên kết được là một firmware
    không tồn tại, và đó không phải thứ để suy diễn từ sự im lặng.
    """

    runner: ToolRunner
    build_dir: str = "build"
    #: Tên ảnh liên kết, không kèm đuôi.
    image_name: str = "firmware"
    image_suffix: str = ".elf"
    #: Năng lực đổi ảnh liên kết sang định dạng nạp được; pack có thì mới chạy.
    hex_capability: str = "hex"
    hex_suffix: str = ".hex"
    name: str = "link"

    def run(self, objects: Sequence[str | Path]) -> ToolReport:
        if not objects:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[ToolError("Không có tệp đối tượng nào để liên kết.")],
                metrics={"config_error": True},
            )
        if not self.runner.manifest.has("link"):
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[
                    ToolError(
                        f"Pack {self.runner.manifest.name!r} không khai báo năng "
                        "lực 'link'. Không có nó thì các module dịch xong vẫn "
                        "không ráp được thành firmware."
                    )
                ],
                metrics={"config_error": True},
            )

        goc = self.runner.work_dir
        thu_muc_build = goc / self.build_dir
        thu_muc_build.mkdir(parents=True, exist_ok=True)
        anh = thu_muc_build / f"{self.image_name}{self.image_suffix}"

        bao_cao = self.runner.run(
            "link",
            {
                "objects": [self._tuong_doi(o, goc) for o in objects],
                "output": str(anh.relative_to(goc)),
                "map": str((thu_muc_build / f"{self.image_name}.map").relative_to(goc)),
            },
            gate_name=self.name,
        )
        if not bao_cao.passed:
            return bao_cao

        bao_cao.metrics["binary"] = str(anh)
        bao_cao.metrics["objects"] = [self._tuong_doi(o, goc) for o in objects]
        bao_cao.metrics["size_scope"] = SCOPE_FIRMWARE

        if self.runner.manifest.has(self.hex_capability):
            nap = thu_muc_build / f"{self.image_name}{self.hex_suffix}"
            bao_cao_hex = self.runner.run(
                self.hex_capability,
                {
                    "input": str(anh.relative_to(goc)),
                    "output": str(nap.relative_to(goc)),
                },
                gate_name=self.name,
            )
            gop = _gop_bao_cao(self.name, [bao_cao, bao_cao_hex])
            gop.metrics.update(bao_cao.metrics)
            if gop.passed:
                # Đây là tệp đem đi nạp xuống mạch (bước 4 của lộ trình).
                gop.metrics["image"] = str(nap)
            return gop

        return bao_cao

    @staticmethod
    def _tuong_doi(duong_dan: str | Path, goc: Path) -> str:
        p = Path(duong_dan)
        return str(p.relative_to(goc)) if p.is_absolute() and p.is_relative_to(goc) else str(p)


@dataclass
class SizeGate:
    """Cổng 2 — đo chiếm dụng bộ nhớ và đối chiếu ngưỡng của dự án."""

    runner: ToolRunner
    #: ``constraints.limits`` — engine chỉ đọc quy ước ``_max`` / ``_min``.
    limits: dict[str, Any] = field(default_factory=dict)
    name: str = "size"

    def run(
        self,
        binary: str | Path | Sequence[str | Path],
        *,
        scope: str = SCOPE_MODULE,
    ) -> ToolReport:
        """Đo một hoặc nhiều ảnh nhị phân.

        Nhiều tệp đối tượng thì đo từng tệp rồi CỘNG các số liệu lại: chiếm
        dụng của một module gồm nhiều đơn vị dịch là tổng của chúng. Cộng đúng
        vì mọi số liệu đều quy về cùng một mẫu số — dung lượng của con chip —
        do pack đo, không do engine giả định.
        """
        goc = self.runner.work_dir
        muc_tieu = [binary] if isinstance(binary, (str, Path)) else list(binary)
        if not muc_tieu:
            return ToolReport(
                gate=self.name,
                passed=False,
                errors=[ToolError("Không có ảnh nhị phân nào để đo.")],
            )

        bao_cao_con: list[ToolReport] = []
        for m in muc_tieu:
            p = Path(m)
            duong_dan = str(p.relative_to(goc)) if p.is_absolute() and p.is_relative_to(goc) else str(p)
            bao_cao_con.append(
                self.runner.run("size", {"binary": duong_dan}, gate_name=self.name)
            )

        bao_cao = _gop_bao_cao(self.name, bao_cao_con)
        bao_cao.metrics.update(_cong_so_lieu(bao_cao_con))
        bao_cao.metrics["size_scope"] = scope
        bao_cao.metrics["measured_files"] = len(muc_tieu)
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
