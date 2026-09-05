"""Cổng 5 — đối chiếu mã với BẢN ĐỒ THANH GHI của nhà sản xuất (GĐ1, A2).

Xem `docs/KE_HOACH_VUOT_LEN.md` §2.3 và `docs/SAI_LECH_THIET_KE.md` mục SL-176.

Cổng này chặn cái gì mà bốn cổng cũ không chặn
-----------------------------------------------

Câu ấy phải trả lời được, nếu không thì thêm một cổng chỉ là làm chậm mọi lượt
sinh để đổi lấy cảm giác an toàn (luật 3 của kế hoạch).

* **cổng dịch** bắt mã không dịch được. Một giá trị sai vẫn dịch được.
* **cổng phân tích tĩnh** bắt điều cấm của dự án, và bắt mã cấu hình thanh ghi
  mà thiếu ``// ref:``. Nó kiểm **CÓ** trích dẫn, không kiểm trích dẫn **ĐÚNG**.
* **cổng kiểm thử** chạy trên máy chủ, nơi thanh ghi là biến trong bộ giả lập —
  ghi 0x1F vào một trường 3 bit ở đó là hợp lệ.

Còn lại đúng một hạng lỗi không ai bắt: **giá trị hợp cú pháp, có trích dẫn, mà
sai với silicon.** Đó là hạng lỗi cổng này sinh ra để chặn.

Bốn phép CHẶN và một phép CẢNH BÁO
-----------------------------------

Chặn — vì máy chứng minh được, không phải suy từ văn xuôi:

1. ghi vào thanh ghi không có trong bản đồ;
2. giá trị vượt độ rộng thanh ghi;
3. dịch bit ra ngoài độ rộng thanh ghi;
4. ghi vào thanh ghi hãng khai là chỉ-đọc.

Cảnh báo — vì nó suy từ ánh xạ chunk↔thanh ghi vốn do người khai:

5. hàm cấu hình thanh ghi X mà trích dẫn một chunk không nói về X.

Vắng bản đồ thì cổng ĐẠT và im
-------------------------------

Dự án chưa khai ``regmap`` trong pack thì cổng trả ĐẠT ngay, không một dòng nào.
Đây là luật 1 của kế hoạch: thêm một nguồn sự thật không được làm hỏng đường
chạy khi nguồn ấy vắng mặt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolReport

__all__ = ["RegCheckGate"]

#: Chỉ soi mã nguồn C. Luật của mã C áp lên tệp kiểm viết bằng Python là vô
#: nghĩa và có hại — hàng rào SL-150 đã dựng một lần cho cổng phân tích tĩnh.
DUOI_MA_NGUON = (".c", ".h", ".cpp")

_SO = r"0[xX][0-9a-fA-F]+|\d+"
#: `TEN = <biểu thức>;` và `TEN |= …`, `&=`, `^=`. Tên thanh ghi viết HOA theo
#: quy ước của mọi tệp hãng phát hành — nhưng phép khớp KHÔNG dựa vào quy ước
#: ấy để quyết định: nó chỉ dùng để thu hẹp, còn quyết định nằm ở chỗ tên có
#: trong bản đồ hay không.
_GAN = re.compile(
    rf"\b(?P<ten>[A-Za-z_]\w*)\s*(?P<op>\|=|&=|\^=|=)\s*(?P<ve_phai>[^;]+);"
)
_GAN_SO = re.compile(rf"^\s*\(?\s*(?P<so>{_SO})\s*\)?\s*$")
_DICH_BIT = re.compile(rf"\b1\s*<<\s*\(?\s*(?P<bit>{_SO})\s*\)?")
_REF = re.compile(r"//\s*ref:\s*([^\s,;]+)")


@dataclass
class RegCheckGate:
    """Cổng 5 — đối chiếu mã với bản đồ thanh ghi."""

    #: ``RegisterMap`` hoặc None. None nghĩa là dự án chưa khai — cổng im.
    regmap: Any = None
    #: Thanh ghi module này khai là có dùng, lấy từ Knowledge Graph. Dùng cho
    #: phép đối chiếu HỒ SƠ ↔ BẢN ĐỒ, tách khỏi phép đối chiếu MÃ ↔ BẢN ĐỒ.
    registers: Sequence[str] = ()
    #: Mã chunk → tập thanh ghi chunk ấy nói về. Thiếu thì phép cảnh báo im.
    chunk_registers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    name: str = "regcheck"

    def run(self, artifact: CodeArtifact) -> ToolReport:
        if not self.regmap:
            return ToolReport(
                gate=self.name,
                passed=True,
                metrics={"skipped": "pack chưa khai bản đồ thanh ghi"},
            )

        loi: list[ToolError] = []
        canh_bao: list[ToolError] = []
        so_kiem = 0

        loi.extend(self._ho_so_lech_ban_do())

        for duong_dan, noi_dung in sorted(artifact.files.items()):
            if not duong_dan.endswith(DUOI_MA_NGUON):
                continue
            phat_hien, dem = self._quet_tep(duong_dan, noi_dung)
            so_kiem += dem
            for e in phat_hien:
                (canh_bao if e.severity == Severity.WARNING else loi).append(e)

        return ToolReport(
            gate=self.name,
            passed=not loi,
            errors=loi,
            warnings=canh_bao,
            metrics={
                "device": getattr(self.regmap, "device", ""),
                "registers_in_map": len(self.regmap),
                "writes_checked": so_kiem,
            },
        )

    # ----------------------------------------------------------------------

    def _ho_so_lech_ban_do(self) -> list[ToolError]:
        """Hồ sơ khai một thanh ghi mà bản đồ của hãng không có.

        Đây là lỗi của HỒ SƠ, không phải của mã — nhưng nó phải đỏ ở đây, vì
        đây là chỗ đầu tiên hai nguồn ấy gặp nhau. Gõ nhầm một tên thanh ghi
        trong `hardware_profile.yaml` thì mọi lượt sinh sau đều nhận một cái
        tên không tồn tại, và không gì khác trong hệ hỏi lại.
        """
        thieu = sorted(r for r in self.registers if not self.regmap.get(r))
        if not thieu:
            return []
        return [
            ToolError(
                message=(
                    f"Hồ sơ phần cứng khai thanh ghi {', '.join(thieu)} mà bản đồ "
                    f"của hãng ({getattr(self.regmap, 'device', '?')}) KHÔNG có. "
                    "Sai ở hồ sơ hay sai ở tệp bản đồ — cả hai đều là việc của "
                    "người, và không bản vá nào của module sửa được."
                ),
                rule_id="regmap-profile-mismatch",
            )
        ]

    def _quet_tep(self, duong_dan: str, noi_dung: str) -> tuple[list[ToolError], int]:
        phat_hien: list[ToolError] = []
        dem = 0
        sach = self._bo_chu_thich(noi_dung)

        for khop in _GAN.finditer(sach):
            ten = khop.group("ten")
            thanh_ghi = self.regmap.get(ten)
            if thanh_ghi is None:
                continue
            dem += 1
            dong = sach.count("\n", 0, khop.start()) + 1
            phat_hien.extend(
                self._kiem_mot_lenh_ghi(
                    duong_dan, dong, thanh_ghi, khop.group("ve_phai")
                )
            )

        phat_hien.extend(self._kiem_trich_dan(duong_dan, noi_dung))
        return phat_hien, dem

    def _kiem_mot_lenh_ghi(
        self, duong_dan: str, dong: int, thanh_ghi: Any, ve_phai: str
    ) -> list[ToolError]:
        ra: list[ToolError] = []

        def bao(thong_diep: str, ma: str) -> None:
            ra.append(
                ToolError(
                    message=f"{duong_dan}:{dong}: {thong_diep}",
                    file=duong_dan,
                    line=dong,
                    rule_id=ma,
                )
            )

        if not thanh_ghi.ghi_duoc:
            bao(
                f"ghi vào {thanh_ghi.name} — hãng khai thanh ghi này CHỈ ĐỌC",
                "regmap-read-only",
            )

        khop_so = _GAN_SO.match(ve_phai)
        if khop_so:
            gia_tri = int(khop_so.group("so"), 0)
            if not thanh_ghi.vua(gia_tri):
                bao(
                    f"{thanh_ghi.name} rộng {thanh_ghi.size_bits} bit "
                    f"(lớn nhất {thanh_ghi.gia_tri_lon_nhat} / "
                    f"0x{thanh_ghi.gia_tri_lon_nhat:X}), mã ghi {gia_tri} "
                    f"/ 0x{gia_tri:X}",
                    "regmap-value-overflow",
                )

        for m in _DICH_BIT.finditer(ve_phai):
            bit = int(m.group("bit"), 0)
            if bit >= thanh_ghi.size_bits:
                bao(
                    f"dịch bit {bit} trong {thanh_ghi.name}, mà thanh ghi chỉ "
                    f"rộng {thanh_ghi.size_bits} bit (bit cao nhất là "
                    f"{thanh_ghi.size_bits - 1})",
                    "regmap-bit-out-of-range",
                )
        return ra

    def _kiem_trich_dan(self, duong_dan: str, noi_dung: str) -> list[ToolError]:
        """Hàm cấu hình thanh ghi X mà trích dẫn chunk không nói về X.

        CẢNH BÁO chứ không chặn: ánh xạ chunk↔thanh ghi do người khai trong
        frontmatter của trích đoạn, nên một chỗ khai thiếu sẽ thành một cổng đỏ
        oan. Nhưng nó phải được nói ra — đây đúng là chỗ *"có trích dẫn"* khác
        *"trích dẫn đúng"*.
        """
        if not self.chunk_registers:
            return []
        from eaa.contract import bo_chu_thich, vung_than_ham

        sach = bo_chu_thich(noi_dung)
        ra: list[ToolError] = []
        for ten_ham, (dau, cuoi) in sorted(vung_than_ham(noi_dung).items()):
            than_co_chu_thich = noi_dung[dau:cuoi]
            trich_dan = _REF.findall(than_co_chu_thich)
            if not trich_dan:
                continue
            cham = {
                m.group("ten").upper()
                for m in _GAN.finditer(sach[dau:cuoi])
                if self.regmap.get(m.group("ten"))
            }
            if not cham:
                continue
            duoc_phu = {
                r.upper()
                for c in trich_dan
                for r in self.chunk_registers.get(c.rstrip(",;"), ())
            }
            thieu = sorted(cham - duoc_phu)
            if thieu and duoc_phu:
                ra.append(
                    ToolError(
                        message=(
                            f"{duong_dan}: {ten_ham}() cấu hình {', '.join(thieu)} "
                            f"nhưng trích dẫn {', '.join(sorted(trich_dan))} — "
                            "chunk ấy không nói về thanh ghi này. Trích dẫn có "
                            "mặt không có nghĩa là trích dẫn đúng chỗ."
                        ),
                        severity=Severity.WARNING,
                        file=duong_dan,
                        rule_id="regmap-citation-mismatch",
                    )
                )
        return ra

    @staticmethod
    def _bo_chu_thich(nguon: str) -> str:
        from eaa.contract import bo_chu_thich

        return bo_chu_thich(nguon)
