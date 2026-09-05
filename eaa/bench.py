"""Thước đo — chỉ số của văn liệu, cộng bốn trục chưa ai có (GĐ2, E1/E2).

Xem `docs/KE_HOACH_VUOT_LEN.md` §3 và `docs/SAI_LECH_THIET_KE.md` mục SL-177.

Hai nửa, và nửa thứ hai mới là đóng góp
----------------------------------------

**Nửa A — thước của họ.** ``pass@1``, ``pass@5``, và các hạng *trượt dịch / sai
hành vi / đúng*. Phải có, vì không có thì không đối thoại được với văn liệu:
IoT-SkillsBench và mọi benchmark sinh mã đều nói bằng những chữ ấy.

**Nửa B — thước của ta.** Bốn trục mà không benchmark nào trong khảo sát hỏi:

============================  ====================================================
trục                          câu nó trả lời
============================  ====================================================
độ nhạy bài kiểm              bao nhiêu % bài kiểm sinh ra **xanh cả với mã sai**?
vá chỉnh đồ đo                bao nhiêu % bản vá sửa cái đang đo thay vì cái bị đo?
mất việc im lặng              bao nhiêu lượt đánh rơi lời gọi mà mọi cổng vẫn xanh?
truy về được                  bao nhiêu % giá trị thanh ghi truy được về đúng nguồn?
============================  ====================================================

Bốn trục ấy đo **chất lượng của quá trình**, không đo chất lượng một lượt sinh.
Một hệ đạt ``pass@1`` cao mà 40% bài kiểm của nó rỗng thì con số ``pass@1`` ấy
không có nghĩa như người đọc tưởng — và không có gì trong văn liệu nói ra điều
đó, vì không ai đo.

Điều module này CỐ Ý không làm
-------------------------------

Nó **không tự chấm đúng/sai**. Hạng của một lượt chạy suy ra từ **báo cáo của
chính chuỗi cổng** — cùng bộ cổng chạy khi kỹ sư gõ ``eaa gen``. Dựng một bộ
chấm riêng cho benchmark là dựng một con đường thứ hai, và con số đi ra từ con
đường ấy nói về con đường ấy chứ không nói về sản phẩm.

Nó cũng **không gộp** kết quả chạy trên bo thật với kết quả chạy trên máy chủ.
Hai loại bằng chứng ấy khác hạng; một benchmark trộn chúng rồi báo một con số
là một benchmark nói dối — kể cả khi con số ấy đúng về số học.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb
from typing import Any, Iterable, Sequence

__all__ = [
    "HANG",
    "DUNG",
    "TRUOT_DICH",
    "SAI_HANH_VI",
    "BAN_GIAO",
    "CHAN",
    "LuotChay",
    "NhiemVu",
    "KetQuaBench",
    "hang_tu_ket_cuc",
    "pass_at_k",
    "gom",
    "doc_bo_chuan",
]

#: Ba hạng của văn liệu, cộng hai hạng mà gộp vào ba hạng kia sẽ nói sai.
DUNG = "BC"          # behaviour correct
TRUOT_DICH = "CF"    # compile failure
SAI_HANH_VI = "BF"   # behaviour failure
BAN_GIAO = "HANDOFF"
CHAN = "BLOCKED"

#: Thứ tự in ra. `HANDOFF` và `BLOCKED` đứng riêng có chủ ý — xem
#: :func:`hang_tu_ket_cuc`.
HANG: tuple[str, ...] = (DUNG, TRUOT_DICH, SAI_HANH_VI, BAN_GIAO, CHAN)

#: Cổng nào trượt thì tính là trượt DỊCH. Lấy từ tên cổng, không từ thứ tự
#: trong chuỗi: chuỗi cổng đổi thứ tự thì phép phân hạng không được đổi theo.
CONG_DICH = frozenset({"compile"})


@dataclass(frozen=True)
class LuotChay:
    """Một lượt thử một nhiệm vụ.

    Bốn trường cuối là dữ liệu của bốn trục mới. Chúng do các bộ đo ĐÃ CÓ sinh
    ra (`sensitivity`, `instrument`, `contract`, `regcheck`) — module này chỉ
    gom lại, không tự đo, vì tự đo là dựng con đường thứ hai.
    """

    hang: str
    vong_va: int = 0
    #: Bài kiểm mới sinh trong lượt này, và bao nhiêu trong số đó KHÔNG phân
    #: biệt được mã sai với mã đúng (`eaa/sensitivity.py`).
    bai_kiem_moi: int = 0
    bai_kiem_khong_phan_biet: int = 0
    #: Dấu vết bản vá chỉnh đồ đo (`eaa/instrument.py`).
    dau_vet_chinh_do_do: int = 0
    #: Lời gọi liên module bị đánh rơi (`eaa/contract.py`).
    loi_goi_bi_danh_roi: int = 0
    #: Giá trị thanh ghi ghi ra, và bao nhiêu trong số đó trích dẫn ĐÚNG nguồn
    #: (`eaa/tools/regcheck.py`).
    ghi_thanh_ghi: int = 0
    ghi_trich_dan_dung: int = 0


@dataclass(frozen=True)
class NhiemVu:
    """Một nhiệm vụ của bộ chuẩn, kèm mọi lượt đã thử."""

    ma: str
    nen_tang: str = ""
    #: Lượt chạy này có chạm phần cứng thật không. Trường này KHÔNG được gộp
    #: vào bất kỳ con số tổng nào — xem docstring đầu mô-đun.
    tren_bo: bool = False
    luot: tuple[LuotChay, ...] = ()

    @property
    def so_dung(self) -> int:
        return sum(1 for l in self.luot if l.hang == DUNG)


def hang_tu_ket_cuc(ket_cuc: Any) -> str:
    """Xếp hạng một lượt chạy TỪ BÁO CÁO CỦA CHUỖI CỔNG.

    Không đọc trường nào tự khai thành công. Một `ModuleOutcome` nói
    ``status='merged'`` mà báo cáo cổng dịch nói trượt thì hạng là **trượt
    dịch** — vì báo cáo cổng là thứ đã chạy, còn `status` là thứ được gán.

    Vì sao `HANDOFF` và `BLOCKED` đứng riêng:

    * **BLOCKED** là lỗi môi trường hoặc cấu hình — thiếu công cụ, thiếu luật
      trong pack. Tính nó vào *sai hành vi* là ghi một lỗi của MÁY TÍNH vào sổ
      của mô hình.
    * **HANDOFF** là hết vòng vá, hoặc dừng vì dấu vết chỉnh đồ đo. Nó khác
      *sai hành vi* ở chỗ hệ thống đã **chủ động dừng và hỏi người** — gộp hai
      cái là xoá mất chính thứ sản phẩm này làm khác.
    """
    bao_cao = list(getattr(ket_cuc, "reports", ()) or ())
    hong = [r for r in bao_cao if not getattr(r, "passed", True)]

    if any((r.metrics or {}).get("env_error") or (r.metrics or {}).get("config_error")
           for r in hong):
        return CHAN
    if getattr(ket_cuc, "status", "") in ("handoff", "blocked"):
        return CHAN if getattr(ket_cuc, "status", "") == "blocked" else BAN_GIAO
    if any(getattr(r, "gate", "") in CONG_DICH for r in hong):
        return TRUOT_DICH
    if hong:
        return SAI_HANH_VI
    return DUNG if bao_cao else BAN_GIAO


def pass_at_k(so_luot: int, so_dung: int, k: int) -> float:
    """Ước lượng không chệch của ``pass@k`` — công thức chuẩn của văn liệu.

    ``1 - C(n-c, k) / C(n, k)``. Dùng đúng công thức ấy chứ không dùng
    "tỉ lệ lượt đúng", vì hai thứ khác nhau và người đọc luận văn biết chúng
    khác nhau.
    """
    if so_luot <= 0 or k <= 0:
        return 0.0
    if k > so_luot:
        k = so_luot
    if so_luot - so_dung < k:
        return 1.0
    return 1.0 - comb(so_luot - so_dung, k) / comb(so_luot, k)


@dataclass(frozen=True)
class KetQuaBench:
    """Kết quả cả bộ chuẩn."""

    nhiem_vu: tuple[NhiemVu, ...] = ()

    # -- nửa A: thước của họ ------------------------------------------------

    def pass_at(self, k: int) -> float:
        """Trung bình ``pass@k`` trên các nhiệm vụ. 0.0 khi bộ rỗng."""
        if not self.nhiem_vu:
            return 0.0
        return sum(
            pass_at_k(len(n.luot), n.so_dung, k) for n in self.nhiem_vu
        ) / len(self.nhiem_vu)

    def dem_hang(self) -> dict[str, int]:
        dem = {h: 0 for h in HANG}
        for n in self.nhiem_vu:
            for l in n.luot:
                dem[l.hang] = dem.get(l.hang, 0) + 1
        return dem

    # -- nửa B: bốn trục chưa ai có -----------------------------------------

    def truc_moi(self) -> dict[str, float | None]:
        """Bốn trục. ``None`` nghĩa là CHƯA ĐO ĐƯỢC, không phải bằng 0.

        Phân biệt ấy quan trọng: một bộ chuẩn không sinh bài kiểm nào thì tỉ lệ
        bài kiểm rỗng của nó không phải 0% — nó không tồn tại. Báo 0% là khai
        một thành tích chưa đo.
        """
        luot = [l for n in self.nhiem_vu for l in n.luot]
        if not luot:
            return {k: None for k in
                    ("do_nhay", "chinh_do_do", "mat_viec_im_lang", "truy_ve_duoc")}

        tong_bai_moi = sum(l.bai_kiem_moi for l in luot)
        tong_ghi = sum(l.ghi_thanh_ghi for l in luot)
        return {
            "do_nhay": (
                sum(l.bai_kiem_khong_phan_biet for l in luot) / tong_bai_moi
                if tong_bai_moi else None
            ),
            "chinh_do_do": sum(
                1 for l in luot if l.dau_vet_chinh_do_do
            ) / len(luot),
            "mat_viec_im_lang": float(sum(l.loi_goi_bi_danh_roi for l in luot)),
            "truy_ve_duoc": (
                sum(l.ghi_trich_dan_dung for l in luot) / tong_ghi
                if tong_ghi else None
            ),
        }

    # -- hai hạng bằng chứng, không gộp -------------------------------------

    def tach_theo_bang_chung(self) -> dict[str, int]:
        return {
            "tren_bo": sum(1 for n in self.nhiem_vu if n.tren_bo),
            "tren_may_chu": sum(1 for n in self.nhiem_vu if not n.tren_bo),
        }

    def render(self) -> str:
        if not self.nhiem_vu:
            return (
                "Bộ chuẩn chưa có nhiệm vụ nào. Không có con số nào để báo, và "
                "báo 0 là khai một kết quả chưa đo."
            )
        tach = self.tach_theo_bang_chung()
        dem = self.dem_hang()
        so_luot = sum(len(n.luot) for n in self.nhiem_vu)

        dong = [
            f"Bộ chuẩn: {len(self.nhiem_vu)} nhiệm vụ, {so_luot} lượt chạy",
            "",
            "HAI HẠNG BẰNG CHỨNG — cố ý KHÔNG gộp thành một số:",
            f"  chạy trên BO THẬT   : {tach['tren_bo']} nhiệm vụ",
            f"  chạy trên máy chủ   : {tach['tren_may_chu']} nhiệm vụ",
            "",
            "── Thước của văn liệu",
            f"  pass@1 = {self.pass_at(1):.3f}    pass@5 = {self.pass_at(5):.3f}",
            "  hạng  : "
            + " · ".join(f"{h} {dem.get(h, 0)}" for h in HANG),
            "",
            "── Bốn trục chưa benchmark nào trong khảo sát hỏi",
        ]
        nhan = {
            "do_nhay": "bài kiểm KHÔNG phân biệt được mã sai",
            "chinh_do_do": "lượt có dấu vết vá chỉnh đồ đo",
            "mat_viec_im_lang": "lời gọi liên module bị đánh rơi",
            "truy_ve_duoc": "giá trị thanh ghi truy về ĐÚNG nguồn",
        }
        truc = self.truc_moi()
        for khoa, ten in nhan.items():
            gia_tri = truc[khoa]
            if gia_tri is None:
                dong.append(f"  {ten:<44} CHƯA ĐO ĐƯỢC")
            elif khoa == "mat_viec_im_lang":
                dong.append(f"  {ten:<44} {gia_tri:.0f}")
            else:
                dong.append(f"  {ten:<44} {gia_tri:6.1%}")
        return "\n".join(dong)


def gom(nhiem_vu: Iterable[NhiemVu]) -> KetQuaBench:
    return KetQuaBench(nhiem_vu=tuple(nhiem_vu))


def doc_bo_chuan(duong_dan: Any) -> KetQuaBench:
    """Đọc kết quả bộ chuẩn từ một sổ nối tiếp.

    Tệp vắng mặt trả về kết quả RỖNG chứ không ném: chưa chạy bộ chuẩn lần nào
    là một trạng thái hợp lệ, và `render()` nói thẳng ra điều đó thay vì báo
    một con số 0 nghe như đã đo.
    """
    import json
    from pathlib import Path

    p = Path(duong_dan)
    if not p.is_file():
        return KetQuaBench()

    nhiem_vu: list[NhiemVu] = []
    for so_dong, dong in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        dong = dong.strip()
        if not dong:
            continue
        try:
            r = json.loads(dong)
            nhiem_vu.append(
                NhiemVu(
                    ma=str(r["ma"]),
                    nen_tang=str(r.get("nen_tang", "")),
                    tren_bo=bool(r.get("tren_bo", False)),
                    luot=tuple(LuotChay(**l) for l in r.get("luot", ())),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"{p}:{so_dong}: dòng hỏng — {exc}") from exc
    return gom(nhiem_vu)
