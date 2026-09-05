"""Cổng phân tích tĩnh — thi hành ràng buộc cứng và luật của nền tảng.

EAA-SRS-01 FR-VER-02 ("Mã vi phạm ràng buộc bị chặn tại static analysis"),
EAA-AIS-05 §4.2 (FR-RAG-02: mã cấu hình thanh ghi phải trích dẫn chunk id),
EAA-SDD-03 §2 ("nap luat tu PlatformPack").

Cổng này hợp nhất ba nguồn luật, và việc phân vai giữa chúng là điểm thiết kế
chính:

* **Dự án nói CÁI GÌ bị cấm** — ``constraints.yaml`` liệt kê tên các điều cấm.
* **Platform Pack nói PHÁT HIỆN THẾ NÀO** — ``packs/<pack>/rules/*.yaml`` cho
  biết mỗi điều cấm trông ra sao trong mã của họ vi điều khiển đó.
* **Engine chỉ thi hành**, cộng thêm vài luật thuần túy cấu trúc mà mọi nền
  tảng đều dùng chung (đệ quy trực tiếp, trích dẫn nguồn, độ dài module).

Hệ quả quan trọng: **một điều cấm không có luật kiểm là LỖI, không phải im
lặng bỏ qua.** Nếu dự án cấm một thứ mà pack không biết cách phát hiện, cổng
này báo hỏng. Cách còn lại — lặng lẽ không kiểm — biến ràng buộc cứng thành
lời khuyên, đúng thứ mà cả kiến trúc này sinh ra để ngăn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from eaa.platform import PackError, PackManifest
from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolReport
from eaa.tools.compile import UnsafePathError, write_artifact
from eaa.tools.runner import ToolRunner

__all__ = ["StaticGate", "Rule", "load_rules", "RULE_KINDS"]

#: Loại luật engine biết thi hành. ``regex`` là mặc định và do pack cung cấp
#: biểu thức; hai loại còn lại là tính chất cấu trúc của mã, không phụ thuộc
#: nền tảng, nên engine tự làm.
RULE_KINDS: tuple[str, ...] = ("regex", "self_recursion", "register_citation")

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_FUNC_DEF = re.compile(
    r"^[A-Za-z_][\w\s\*]*?(?P<name>[A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", re.MULTILINE
)


@dataclass(frozen=True)
class Rule:
    """Một luật phân tích tĩnh đã nạp, kèm loại thi hành."""

    id: str
    message: str
    kind: str = "regex"
    pattern: str = ""
    severity: str = Severity.ERROR
    ref: str = ""
    #: Bỏ qua phần trong chú thích — mặc định bật, vì một chuỗi bị cấm nhắc tới
    #: trong chú thích giải thích "tại sao không dùng" không phải vi phạm.
    skip_comments: bool = True

    def __post_init__(self) -> None:
        if self.kind not in RULE_KINDS:
            raise PackError(
                f"Luật {self.id!r} có kind={self.kind!r} engine không thi hành được "
                f"(hợp lệ: {list(RULE_KINDS)})"
            )
        if self.kind == "regex":
            if not self.pattern:
                raise PackError(f"Luật {self.id!r} kiểu regex nhưng thiếu 'pattern'")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise PackError(f"Luật {self.id!r}: biểu thức không hợp lệ — {exc}") from exc


def load_rules(rules_dir: str | Path) -> dict[str, Rule]:
    """Nạp mọi luật trong thư mục ``rules/`` của một Platform Pack."""
    rules_dir = Path(rules_dir)
    ket_qua: dict[str, Rule] = {}
    if not rules_dir.is_dir():
        return ket_qua

    for path in sorted(list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))):
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise PackError(f"{path}: YAML không hợp lệ — {exc}") from exc

        danh_sach = du_lieu.get("rules") if isinstance(du_lieu, dict) else du_lieu
        if not isinstance(danh_sach, list):
            raise PackError(f"{path}: phải chứa khóa 'rules' là một danh sách")

        for muc in danh_sach:
            if not isinstance(muc, dict) or not muc.get("id"):
                raise PackError(f"{path}: có luật thiếu 'id'")
            luat = Rule(
                id=str(muc["id"]),
                message=str(muc.get("message", muc["id"])),
                kind=str(muc.get("kind", "regex")),
                pattern=str(muc.get("pattern", "")),
                severity=str(muc.get("severity", Severity.ERROR)),
                ref=str(muc.get("ref", "")),
                skip_comments=bool(muc.get("skip_comments", True)),
            )
            if luat.id in ket_qua:
                raise PackError(f"{path}: trùng mã luật {luat.id!r}")
            ket_qua[luat.id] = luat

    return ket_qua


@dataclass
class StaticGate:
    """Cổng 3 — phân tích tĩnh."""

    #: Có thể là ``None`` khi chỉ muốn chạy luật nội bộ (ví dụ trong test).
    runner: ToolRunner | None = None
    manifest: PackManifest | None = None
    #: Danh sách tên điều cấm lấy từ ``constraints.forbidden``.
    forbidden: Sequence[str] = ()
    #: ``constraints.limits`` — dùng cho ngưỡng độ dài module.
    limits: dict[str, Any] = field(default_factory=dict)
    #: Thanh ghi module này cấu hình, lấy từ Knowledge Graph. Nguồn của luật
    #: trích dẫn (FR-RAG-02): engine không biết tên thanh ghi nào tồn tại, nó
    #: được đưa cho danh sách ứng với module đang xét.
    registers: Sequence[str] = ()
    #: Chunk đã nạp vào prompt — trích dẫn phải trỏ về một trong số này.
    allowed_chunk_ids: Sequence[str] = ()
    #: Sổ số đo trên bo (N-913). Nguồn đơn vị THẬT của các hằng số, để bắt
    #: chú thích gán nhầm đơn vị (N-911). None thì phép soi ấy im — và im vì
    #: thiếu dữ liệu khác hẳn im vì không có gì sai.
    measured: Any = None
    name: str = "static"
    _rules: dict[str, Rule] | None = None

    def _don_vi_da_dang_ky(self) -> dict[str, str]:
        """Giá trị số → đơn vị thật, dựng từ sổ số đo đã duyệt."""
        if self.measured is None:
            return {}
        try:
            return {f.value: f.unit for f in self.measured.active() if f.unit}
        except Exception:  # noqa: BLE001 - sổ hỏng không được làm hỏng cổng
            return {}

    def rules(self) -> dict[str, Rule]:
        if self._rules is None:
            self._rules = (
                load_rules(self.manifest.rules_dir) if self.manifest is not None else {}
            )
        return self._rules

    # ----------------------------------------------------------------------

    def run(self, artifact: CodeArtifact) -> ToolReport:
        loi: list[ToolError] = []
        canh_bao: list[ToolError] = []

        loi.extend(self._kiem_du_luat())

        for duong_dan, noi_dung in sorted(artifact.files.items()):
            phat_hien = self._quet_tep(duong_dan, noi_dung)
            for e in phat_hien:
                (canh_bao if e.severity == Severity.WARNING else loi).append(e)

        so_lieu: dict[str, Any] = {
            "files_scanned": len(artifact.files),
            "rules_applied": len(self._luat_ap_dung()),
        }

        # Thiếu luật kiểm là lỗi CẤU HÌNH, không phải lỗi mã. Đánh dấu để
        # Orchestrator dừng thay vì mở vòng tự sửa: mô hình không thể sửa một
        # luật còn thiếu trong Platform Pack, nên ba vòng vá ở đây chỉ đốt tiền
        # và gần như chắc chắn làm hỏng mã đang đúng.
        if any(e.rule_id == "missing-rule" for e in loi):
            so_lieu["config_error"] = True

        # Công cụ phân tích tĩnh ngoài của pack (nếu có) chạy sau luật nội bộ:
        # luật nội bộ thi hành ràng buộc của đề án, công cụ ngoài bắt phần còn
        # lại. Cả hai đều phải đạt.
        if self.runner is not None and self.manifest is not None and self.manifest.has("static"):
            bao_cao_ngoai = self._chay_cong_cu_ngoai(artifact)
            loi.extend(bao_cao_ngoai.errors)
            canh_bao.extend(bao_cao_ngoai.warnings)
            so_lieu.update(
                {f"external_{k}": v for k, v in bao_cao_ngoai.metrics.items()}
            )

        return ToolReport(
            gate=self.name,
            passed=not loi,
            errors=loi,
            warnings=canh_bao,
            metrics=so_lieu,
        )

    # ----------------------------------------------------------------------

    def _luat_ap_dung(self) -> list[Rule]:
        """Luật của pack ứng với các điều cấm dự án khai báo, cộng luật engine."""
        co_san = self.rules()
        ap_dung = [co_san[ten] for ten in self.forbidden if ten in co_san]
        ap_dung.append(
            Rule(
                id="ref-citation",
                kind="register_citation",
                message=(
                    "Hàm cấu hình thanh ghi phải mang dòng trích dẫn "
                    "'// ref: <mã chunk>' (FR-RAG-02)"
                ),
            )
        )
        return ap_dung

    def _kiem_du_luat(self) -> list[ToolError]:
        """Điều cấm không có luật kiểm là lỗi, không phải chuyện bỏ qua."""
        co_san = self.rules()
        thieu = [ten for ten in self.forbidden if ten not in co_san]
        if not thieu:
            return []
        ten_pack = self.manifest.name if self.manifest else "(chưa nạp pack)"
        return [
            ToolError(
                f"constraints.yaml cấm {ten!r} nhưng Platform Pack {ten_pack!r} "
                "không có luật nào phát hiện điều này. Ràng buộc không kiểm được "
                "là ràng buộc không được thi hành — bổ sung luật vào "
                f"packs/{ten_pack}/rules/ trước khi sinh mã.",
                rule_id="missing-rule",
            )
            for ten in thieu
        ]

    #: Đuôi tệp mà luật của cổng này áp dụng — mã NGUỒN của firmware.
    DUOI_MA_NGUON: tuple[str, ...] = (".c", ".h")

    def _quet_tep(self, duong_dan: str, noi_dung: str) -> list[ToolError]:
        phat_hien: list[ToolError] = []

        # Luật ở đây là luật của mã C: cấm `delay()`, cấm đệ quy, bắt buộc
        # trích dẫn nguồn khi cấu hình thanh ghi. Áp chúng lên tệp KIỂM viết
        # bằng Python là vô nghĩa và có hại:
        #
        #   tests/test_<module>.py:41: hàm <tên>() cấu hình <thanh ghi>
        #                              nhưng không có trích dẫn
        #
        # Dòng ấy nói về một hàm GIẢ trong bài kiểm, dựng ra để lái driver. Nó
        # không chạy trên chip, không cấu hình gì cả. Cổng đỏ, vòng tự sửa mở,
        # và mô hình được yêu cầu thêm trích dẫn tài liệu vào mã Python
        # (SL-150).
        #
        # Bộ sinh mã bắt đầu trả về tệp test từ SL-134; luật của cổng này thì
        # có từ Sprint 2 và chưa bao giờ được hỏi "áp lên tệp nào".
        if not duong_dan.endswith(self.DUOI_MA_NGUON):
            return phat_hien

        # Chú thích số học sai thứ nguyên — CẢNH BÁO, không chặn (N-911).
        # Chú thích là văn xuôi tự do; một bộ đọc văn xuôi mà chặn được đường
        # merge sẽ chặn nhầm, và một cổng chặn nhầm sớm muộn cũng bị tắt đi.
        from eaa.dimension import soi_chu_thich_so_hoc

        for dau in soi_chu_thich_so_hoc(noi_dung, self._don_vi_da_dang_ky()):
            phat_hien.append(
                ToolError(
                    message=f"{duong_dan}:{dau.dong}: {dau.loai} — {dau.chi_tiet}",
                    severity=Severity.WARNING,
                    file=duong_dan,
                    line=dau.dong,
                    rule_id="dimension",
                )
            )

        for luat in self._luat_ap_dung():
            if luat.kind == "regex":
                phat_hien.extend(self._quet_regex(luat, duong_dan, noi_dung))
            elif luat.kind == "self_recursion":
                phat_hien.extend(self._quet_de_quy(luat, duong_dan, noi_dung))
            elif luat.kind == "register_citation":
                phat_hien.extend(self._quet_trich_dan(luat, duong_dan, noi_dung))

        phat_hien.extend(self._quet_do_dai(duong_dan, noi_dung))
        return phat_hien

    @staticmethod
    def _bo_chu_thich(noi_dung: str) -> str:
        """Thay chú thích bằng dấu cách, GIỮ NGUYÊN số dòng để báo đúng vị trí."""
        def thay(khop: re.Match[str]) -> str:
            return re.sub(r"[^\n]", " ", khop.group(0))

        return _COMMENT.sub(thay, noi_dung)

    def _quet_regex(self, luat: Rule, duong_dan: str, noi_dung: str) -> list[ToolError]:
        van_ban = self._bo_chu_thich(noi_dung) if luat.skip_comments else noi_dung
        phat_hien: list[ToolError] = []
        for khop in re.finditer(luat.pattern, van_ban, flags=re.MULTILINE):
            so_dong = van_ban.count("\n", 0, khop.start()) + 1
            phat_hien.append(
                ToolError(
                    message=f"{luat.message} (khớp: {khop.group(0).strip()!r})",
                    severity=luat.severity,
                    file=duong_dan,
                    line=so_dong,
                    rule_id=luat.id,
                )
            )
        return phat_hien

    def _quet_de_quy(self, luat: Rule, duong_dan: str, noi_dung: str) -> list[ToolError]:
        """Đệ quy TRỰC TIẾP: hàm gọi chính nó trong thân của nó.

        Không bắt được đệ quy gián tiếp (A gọi B gọi A) — điều đó cần dựng đồ
        thị lời gọi. Giới hạn này được nói ra thay vì giấu: trên hệ nhúng, đệ
        quy bị cấm vì ngăn xếp, và một cổng bắt được phần lớn trường hợp vẫn
        hơn không có cổng, miễn là người đọc biết nó không bắt được cái gì.
        """
        van_ban = self._bo_chu_thich(noi_dung)
        phat_hien: list[ToolError] = []

        for khop in _FUNC_DEF.finditer(van_ban):
            ten = khop.group("name")
            than, dong_bat_dau = self._than_ham(van_ban, khop.end() - 1)
            if re.search(rf"\b{re.escape(ten)}\s*\(", than):
                phat_hien.append(
                    ToolError(
                        message=f"{luat.message}: hàm {ten}() gọi chính nó",
                        severity=luat.severity,
                        file=duong_dan,
                        line=van_ban.count("\n", 0, khop.start()) + 1,
                        rule_id=luat.id,
                    )
                )
        return phat_hien

    def _quet_trich_dan(self, luat: Rule, duong_dan: str, noi_dung: str) -> list[ToolError]:
        """TC-17 — mã cấu hình thanh ghi không trích dẫn nguồn là mã không nguồn gốc.

        Engine không biết tên thanh ghi nào tồn tại trên đời; danh sách
        ``registers`` do Knowledge Graph cấp cho đúng module đang xét. Phạm vi
        kiểm là HÀM: nếu thân một hàm có chạm thanh ghi thì hàm đó (hoặc dòng
        ngay trên khai báo của nó) phải có ``// ref:``.
        """
        if not self.registers:
            return []

        van_ban_co_chu_thich = noi_dung
        van_ban = self._bo_chu_thich(noi_dung)
        phat_hien: list[ToolError] = []
        mau_thanh_ghi = re.compile(
            r"\b(" + "|".join(re.escape(r) for r in self.registers) + r")\b"
        )

        for khop in _FUNC_DEF.finditer(van_ban):
            than, _ = self._than_ham(van_ban, khop.end() - 1)
            cham = sorted({m.group(1) for m in mau_thanh_ghi.finditer(than)})
            if not cham:
                continue

            dong_bat_dau = van_ban.count("\n", 0, khop.start()) + 1
            khoi = self._khoi_kem_chu_thich(van_ban_co_chu_thich, khop.start(), len(than))
            trich_dan = re.findall(r"//\s*ref:\s*(\S+)", khoi)

            if not trich_dan:
                phat_hien.append(
                    ToolError(
                        message=(
                            f"{luat.message} — hàm {khop.group('name')}() cấu hình "
                            f"{', '.join(cham)} nhưng không có trích dẫn"
                        ),
                        severity=luat.severity,
                        file=duong_dan,
                        line=dong_bat_dau,
                        rule_id=luat.id,
                    )
                )
                continue

            if self.allowed_chunk_ids:
                la = [t.rstrip(",;") for t in trich_dan if t.rstrip(",;") not in self.allowed_chunk_ids]
                if la:
                    phat_hien.append(
                        ToolError(
                            message=(
                                f"Hàm {khop.group('name')}() trích dẫn chunk không "
                                f"nằm trong tập đã nạp: {', '.join(la)}. Trích dẫn "
                                "một mã chunk không có thật là ảo giác có đóng dấu."
                            ),
                            severity=Severity.ERROR,
                            file=duong_dan,
                            line=dong_bat_dau,
                            rule_id="ref-unknown-chunk",
                        )
                    )
        return phat_hien

    def _quet_do_dai(self, duong_dan: str, noi_dung: str) -> list[ToolError]:
        """Kỷ luật "module ≤ N dòng" cưỡng chế ở đây, không dựa vào trần token.

        AIS §2 nói rõ điều này: trần ``max_output_tokens`` được đặt cao để không
        cắt cụt phản hồi, nên độ dài module phải có nơi khác thi hành.
        """
        tran = self.limits.get("max_module_lines")
        if not isinstance(tran, int) or isinstance(tran, bool):
            return []
        so_dong = len(noi_dung.splitlines())
        if so_dong <= tran:
            return []
        return [
            ToolError(
                f"Tệp dài {so_dong} dòng, vượt trần {tran} dòng "
                "(max_module_lines trong constraints.yaml).",
                file=duong_dan,
                line=tran + 1,
                rule_id="max-module-lines",
            )
        ]

    @staticmethod
    def _than_ham(van_ban: str, vi_tri_mo: int) -> tuple[str, int]:
        """Trích thân hàm từ dấu ngoặc nhọn mở, theo cân bằng ngoặc."""
        can_bang = 0
        for i in range(vi_tri_mo, len(van_ban)):
            if van_ban[i] == "{":
                can_bang += 1
            elif van_ban[i] == "}":
                can_bang -= 1
                if can_bang == 0:
                    return van_ban[vi_tri_mo : i + 1], vi_tri_mo
        return van_ban[vi_tri_mo:], vi_tri_mo

    @staticmethod
    def _khoi_kem_chu_thich(noi_dung: str, bat_dau: int, do_dai_than: int) -> str:
        """Lấy vùng gồm vài dòng chú thích ngay trên hàm và toàn bộ thân hàm.

        Trích dẫn thường nằm ngay trên khai báo hàm chứ không nằm trong thân —
        đó là cách người ta viết chú thích nguồn, nên phép kiểm phải nhìn cả
        vùng đó thay vì bắt bẻ vị trí.
        """
        dong = noi_dung[:bat_dau].splitlines()
        phia_tren = "\n".join(dong[-4:])
        return phia_tren + "\n" + noi_dung[bat_dau : bat_dau + do_dai_than + 200]

    def _chay_cong_cu_ngoai(self, artifact: CodeArtifact) -> ToolReport:
        """Chạy công cụ phân tích tĩnh của pack trên mã đã ghi xuống đĩa.

        Ghi lại artifact ở đây thay vì trông chờ cổng biên dịch đã ghi: cổng
        này phải chạy độc lập được. Trong vòng lặp chuẩn nó luôn chạy sau cổng
        biên dịch nên việc ghi là dư — nhưng một cổng chỉ đúng khi có cổng khác
        chạy trước là một cổng dễ hỏng thầm lặng khi thứ tự đổi.
        """
        assert self.runner is not None and self.manifest is not None
        nguon = [p for p in artifact.files if p.endswith(".c")]
        if not nguon:
            return ToolReport(gate=f"{self.name}:external", passed=True)

        try:
            write_artifact(artifact, self.runner.work_dir)
        except UnsafePathError as exc:
            return ToolReport(
                gate=f"{self.name}:external",
                passed=False,
                errors=[ToolError(str(exc))],
            )

        # Thư mục tiêu đề GIẢ của pack cũng đưa cho công cụ phân tích tĩnh.
        #
        # Không có nó, cppcheck không tìm thấy `<avr/io.h>`, ngừng phân tích cú
        # pháp ở dòng đầu và báo `unknown type name 'uint32_t'` — một lỗi CỦA
        # CÁCH GỌI CÔNG CỤ, không phải của mã. Engine không biết thư mục ấy tên
        # gì; nó chỉ chuyển tiếp đường dẫn pack khai (FR-PLT-01).
        gia = getattr(self.manifest, "root", None)
        thu_muc_gia = ""
        if gia is not None:
            ung_vien = Path(gia) / "hostmock"
            if ung_vien.is_dir():
                thu_muc_gia = str(ung_vien)

        return self.runner.run(
            "static",
            {"source": nguon[0], "sources": nguon, "mock_include": thu_muc_gia},
            gate_name=f"{self.name}:external",
        )
