"""Gom mọi phát hiện của quy trình thành CHẨN ĐOÁN cho biên tập (E2, SL-184).

Xem `docs/EAA_Backlog_Tien_hoa.xlsx` việc E2 và `eaa/jsonout.py` (E1).

Việc này gần như chỉ là XUẤT RA
--------------------------------

`ToolError` đã mang sẵn ``file``, ``line``, ``rule_id``, ``severity``, và hồ sơ
kiểm chứng cất trong ``.eaa/runs/`` giữ nguyên cả bốn trường qua vòng ghi–đọc.
Thiếu duy nhất một chỗ để đi ra.

Ba nguồn, và nguồn thứ ba mới là nguồn quan trọng nhất
-------------------------------------------------------

1. **Lỗi cổng** — có vị trí, vẽ được gạch đỏ ngay dòng.
2. **Cảnh báo cổng** — thường không có vị trí.
3. **Lý do NGƯỜI từ chối tại gate** — không có vị trí nào cả.

Phép đo ngược lịch sử (V3, SL-179) cho một con số quyết định hình dạng module
này: **8 trong 13 lần từ chối G3 là lỗi thiết kế hoặc vật lý** — sai trục cảm
biến, sai hệ số tích phân, sai thứ tự vùng chết, một lời gọi thừa giết hẳn chức
năng. Không cổng tĩnh nào bắt được chúng, nên **không cái nào có `file:line`**.

Một bảng lỗi chỉ hiện thứ có vị trí sẽ hiện đúng 0 trong 8 phát hiện ấy, và nó
dạy người dùng một câu sai: *"không gạch đỏ nghĩa là ổn"*. Với sản phẩm này thì
đó là câu sai nguy hiểm nhất — chính những lỗi không có vị trí mới là lỗi làm
robot ngã.

Nên luật của module: **phát hiện KHÔNG có vị trí vẫn phải đi ra**, neo vào một
tệp cấp dự án để nó hiện trong bảng lỗi thay vì biến mất. Và số phát hiện đi ra
phải bằng số phát hiện trong nguồn — :func:`gom` trả kèm phép đếm để bài kiểm
đối chiếu.

Không tự chấm lại, không tự xếp hạng
-------------------------------------

Module chỉ ĐỌC những gì cổng và người đã ghi. Nó không chạy cổng, không suy ra
mức nghiêm trọng mới, không gộp hai phát hiện thành một. Dựng một bộ chấm thứ
hai ở đây là dựng một con đường thứ hai, và con số đi ra sẽ nói về con đường ấy
chứ không nói về sản phẩm.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = ["ChanDoan", "GomChanDoan", "gom", "MUC_BIEN_TAP"]

#: Mức của `eaa/tools/base.py` → từ vựng bảng lỗi của biên tập. Ánh xạ tường
#: minh thay vì để lớp IDE tự đoán: đoán sai một lần là một lỗi hiện thành ghi
#: chú, và không ai nhìn ghi chú.
MUC_BIEN_TAP: dict[str, str] = {
    "error": "error",
    "warning": "warning",
    "info": "information",
}

#: Vị trí nhúng trong văn xuôi của sổ lỗi: ``src/drv_x.c:7: ...``.
#:
#: Rút vị trí từ CHỮ là việc phải làm dè dặt — `eaa/jsonout.py` đã nói đúng
#: chuyện này: dò chữ thì sớm muộn cũng sai. Nên phép khớp ở đây chặt (đường
#: dẫn tương đối, đuôi mã nguồn, số dòng dương), và mọi vị trí rút được đều
#: mang cờ riêng để lớp IDE biết nó KHÁC hạng với vị trí có cấu trúc.
#:
#: Rút hỏng thì phát hiện vẫn đi ra, chỉ mất phần vị trí. Bỏ nó đi mới là hỏng.
_VI_TRI_TRONG_CHU = re.compile(
    r"(?<![\w/.])(?P<tep>(?:[\w.\-]+/)*[\w.\-]+\.(?:c|h|cpp))"
    r":(?P<dong>[1-9]\d{0,5})(?::\d+)?:"
)

#: Neo cho phát hiện KHÔNG có vị trí. Chúng vẫn phải hiện, nên chúng cần một
#: tệp để bám — nếu không thì bảng lỗi của biên tập bỏ chúng đi trong im lặng.
TEP_NEO = "project_state.json"


@dataclass(frozen=True)
class ChanDoan:
    """Một phát hiện, ở dạng bảng lỗi của biên tập đọc được."""

    #: Đường dẫn tương đối so với thư mục dự án.
    tep: str
    #: Dòng 1-based, hoặc None khi phát hiện không gắn với dòng nào.
    dong: int | None
    muc: str
    thong_diep: str
    #: Cổng hoặc gate nào phát hiện ra.
    nguon: str
    #: Mã quy tắc, nếu có.
    quy_tac: str | None = None
    module: str = ""
    #: True khi phát hiện KHÔNG có vị trí thật và đang neo tạm vào `TEP_NEO`.
    neo_tam: bool = False
    #: True khi vị trí được RÚT TỪ VĂN XUÔI chứ không đọc từ trường có cấu
    #: trúc. Hai hạng ấy không được trộn: một cái là dữ liệu, một cái là phép
    #: đoán có căn cứ.
    vi_tri_do_doc: bool = False
    #: True khi phát hiện thuộc về LỊCH SỬ đã khép: module ấy sau đó đã qua hết
    #: cổng. Sổ lỗi là sổ append-only, nên phần lớn mục trong nó là chuyện đã
    #: sửa xong — bày chúng như lỗi hiện tại là để bảng lỗi nói dối, và một
    #: bảng lỗi nói dối tệ hơn một bảng lỗi trống.
    lich_su: bool = False

    @property
    def co_vi_tri(self) -> bool:
        """Vẽ được gạch đỏ đúng dòng hay không."""
        return not self.neo_tam and self.dong is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.tep,
            "line": self.dong,
            "severity": MUC_BIEN_TAP.get(self.muc, self.muc),
            "message": self.thong_diep,
            "source": self.nguon,
            "rule": self.quy_tac,
            "module": self.module,
            # Nói thẳng rằng chỗ neo là tạm. Lớp IDE hiện được nó khác đi, và
            # người đọc không tưởng lỗi nằm ở tệp trạng thái.
            "anchored": self.neo_tam,
            "position_parsed": self.vi_tri_do_doc,
            "state": "historical" if self.lich_su else "current",
        }


@dataclass(frozen=True)
class GomChanDoan:
    """Kết quả gom, kèm đủ số để đối chiếu với nguồn."""

    muc: tuple[ChanDoan, ...] = ()
    #: Số phát hiện ĐỌC ĐƯỢC trong nguồn. Phải bằng ``len(muc)``.
    so_trong_nguon: int = 0
    #: Module có bằng chứng kiểm chứng đọc được.
    module_da_doc: tuple[str, ...] = ()

    @property
    def hien_tai(self) -> tuple[ChanDoan, ...]:
        """Phát hiện CHƯA được khép lại. Đây mới là thứ bảng lỗi nên hiện."""
        return tuple(c for c in self.muc if not c.lich_su)

    @property
    def co_vi_tri(self) -> tuple[ChanDoan, ...]:
        """Trong số phát hiện HIỆN TẠI, cái nào vẽ được gạch đỏ.

        Tính trên phần hiện tại chứ không trên tổng: tỉ lệ E2 hỏi là *"bảng lỗi
        của biên tập vẽ được bao nhiêu"*, và nó không vẽ lịch sử.
        """
        return tuple(c for c in self.hien_tai if c.co_vi_tri)

    @property
    def ti_le_co_vi_tri(self) -> float | None:
        """Tỉ lệ phát hiện vẽ được gạch đỏ. None khi chưa có phát hiện nào.

        None chứ không phải 0: chưa có phát hiện nào thì tỉ lệ ấy **không tồn
        tại**, và báo 0% là khai một con số chưa đo — cùng luật `confidence.py`
        đặt cho mọi đầu ra khác.
        """
        if not self.hien_tai:
            return None
        return len(self.co_vi_tri) / len(self.hien_tai)

    @property
    def khop_nguon(self) -> bool:
        return len(self.muc) == self.so_trong_nguon


def _tu_loi(
    loi: dict[str, Any], *, nguon: str, module: str, mac_dinh_muc: str
) -> ChanDoan:
    tep = (loi.get("file") or "").strip()
    dong = loi.get("line")
    return ChanDoan(
        tep=tep or TEP_NEO,
        dong=dong if tep else None,
        muc=loi.get("severity") or mac_dinh_muc,
        thong_diep=loi.get("message", ""),
        nguon=nguon,
        quy_tac=loi.get("rule_id"),
        module=module,
        neo_tam=not tep,
    )


def _doc_so_loi(so: Path) -> list[dict[str, Any]]:
    """Sổ lỗi ảo giác — nguồn DUY NHẤT còn giữ chẩn đoán của lượt TRƯỢT.

    Bằng chứng trong ``.eaa/runs/`` chỉ được cất ở bước 10, tức chỉ khi mã đã
    qua hết cổng; lỗi có vị trí sinh ra ở lượt trượt không bao giờ tới đó. Nên
    nếu chỉ đọc bằng chứng thì bảng lỗi của biên tập có đúng **0** gạch đỏ, và
    con số ấy nói về chỗ cất chứ không nói về chất lượng mã.
    """
    if not so.is_file():
        return []
    ra: list[dict[str, Any]] = []
    for dong in so.read_text(encoding="utf-8").splitlines():
        if not dong.strip():
            continue
        try:
            d = json.loads(dong)
        except ValueError:
            continue
        if d.get("event") == "error":
            ra.append(d)
    return ra


def _module_da_khep(bang_chung: list[tuple[str, dict[str, Any]]]) -> set[str]:
    """Module đã qua HẾT cổng — mọi phát hiện cũ của nó thuộc về lịch sử."""
    ra: set[str] = set()
    for ten, d in bang_chung:
        bc = d.get("reports") or []
        if bc and all(r.get("passed") for r in bc):
            ra.add(ten)
    return ra


def _tu_so_loi(d: dict[str, Any], da_khep: set[str]) -> ChanDoan:
    mo_ta = str(d.get("description", ""))
    khop = _VI_TRI_TRONG_CHU.search(mo_ta)
    return ChanDoan(
        tep=khop.group("tep") if khop else TEP_NEO,
        dong=int(khop.group("dong")) if khop else None,
        muc="error",
        thong_diep=mo_ta,
        nguon=f"ledger/{d.get('category', '?')}",
        quy_tac=str(d.get("rule") or "") or None,
        module=str(d.get("module") or ""),
        neo_tam=khop is None,
        vi_tri_do_doc=khop is not None,
        lich_su=str(d.get("module") or "") in da_khep,
    )


def _doc_bang_chung(runs: Path) -> list[tuple[str, dict[str, Any]]]:
    ra: list[tuple[str, dict[str, Any]]] = []
    if not runs.is_dir():
        return ra
    for tep in sorted(runs.glob("verification_*.json")):
        try:
            d = json.loads(tep.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Một tệp bằng chứng hỏng không được làm mất những tệp còn lại —
            # nhưng nó cũng không được biến mất trong im lặng, nên nó đi vào
            # kết quả dưới dạng một phát hiện.
            ra.append((tep.stem.removeprefix("verification_"), {"__hong__": str(tep)}))
            continue
        ra.append((str(d.get("module") or tep.stem.removeprefix("verification_")), d))
    return ra


def _doc_tu_choi(quyet_dinh: Path) -> list[dict[str, Any]]:
    """Lần từ chối GẦN NHẤT của mỗi module tại mỗi gate.

    Chỉ lần gần nhất: một module bị từ chối năm lần thì bốn lần đầu đã được
    trả lời bằng bốn bản sinh lại, và bày cả năm lên bảng lỗi là bày lịch sử
    chứ không bày việc phải làm.
    """
    if not quyet_dinh.is_file():
        return []
    moi_nhat: dict[tuple[str, str], dict[str, Any]] = {}
    for dong in quyet_dinh.read_text(encoding="utf-8").splitlines():
        if not dong.strip():
            continue
        try:
            d = json.loads(dong)
        except ValueError:
            continue
        if d.get("decision") != "rejected":
            continue
        khoa = (str(d.get("module") or ""), str(d.get("gate_id") or ""))
        cu = moi_nhat.get(khoa)
        if cu is None or str(d.get("decided_at", "")) > str(cu.get("decided_at", "")):
            moi_nhat[khoa] = d
    return list(moi_nhat.values())


def gom(
    du_an: Path | str,
    *,
    runs: str = ".eaa/runs",
    quyet_dinh: str = "gates/decisions.jsonl",
    so_loi: str = "error_ledger.jsonl",
    module: Sequence[str] | None = None,
) -> GomChanDoan:
    """Gom chẩn đoán từ bằng chứng cổng và từ lý do người từ chối gate.

    ``module`` lọc theo module; None nghĩa là lấy tất cả.
    """
    goc = Path(du_an)
    loc = set(module) if module else None
    ra: list[ChanDoan] = []
    dem = 0
    da_doc: list[str] = []

    bang_chung = _doc_bang_chung(goc / runs)
    da_khep = _module_da_khep(bang_chung)

    for ten, d in bang_chung:
        if loc is not None and ten not in loc:
            continue
        if "__hong__" in d:
            dem += 1
            ra.append(ChanDoan(
                tep=TEP_NEO, dong=None, muc="error",
                thong_diep=f"Hồ sơ kiểm chứng không đọc được: {d['__hong__']}",
                nguon="evidence", module=ten, neo_tam=True,
            ))
            continue
        da_doc.append(ten)
        for bao_cao in d.get("reports", []):
            cong = str(bao_cao.get("gate", "?"))
            for khoa, mac_dinh in (("errors", "error"), ("warnings", "warning")):
                for loi in bao_cao.get(khoa, []):
                    dem += 1
                    ra.append(_tu_loi(
                        loi, nguon=cong, module=ten, mac_dinh_muc=mac_dinh
                    ))

    for d in _doc_tu_choi(goc / quyet_dinh):
        ten = str(d.get("module") or "")
        if loc is not None and ten not in loc:
            continue
        dem += 1
        ra.append(ChanDoan(
            tep=TEP_NEO,
            dong=None,
            muc="error",
            thong_diep=d.get("reason", ""),
            # Nguồn ghi rõ đây là NGƯỜI từ chối, không phải máy. Hai thứ ấy
            # khác hạng bằng chứng và không được trộn thành một dòng như nhau.
            nguon=f"{d.get('gate_id', 'gate')} (người)",
            module=ten,
            neo_tam=True,
        ))

    for d in _doc_so_loi(goc / so_loi):
        if loc is not None and str(d.get("module") or "") not in loc:
            continue
        dem += 1
        ra.append(_tu_so_loi(d, da_khep))

    return GomChanDoan(
        muc=tuple(ra), so_trong_nguon=dem, module_da_doc=tuple(sorted(set(da_doc)))
    )


def bang_chu(kq: GomChanDoan, *, tran: int = 0, tat_ca: bool = False) -> str:
    """Dạng chữ cho người đọc ở dòng lệnh."""
    if not kq.muc:
        return "Không có phát hiện nào trong bằng chứng đã cất."
    if not kq.hien_tai and not tat_ca:
        # `tat_ca` phải thắng nhánh thoát sớm này: người gõ `--all` là người
        # đang muốn xem lịch sử, và trả về một câu nói "xem `--all`" cho chính
        # họ là bỏ qua đúng cờ họ vừa gõ.
        return (f"Không phát hiện nào đang mở. "
                f"({len(kq.muc)} mục thuộc lịch sử đã khép — xem `--all`.)")
    dong: list[str] = []
    nguon_hien = kq.muc if tat_ca else kq.hien_tai
    hien: Iterable[ChanDoan] = nguon_hien[:tran] if tran else nguon_hien
    for c in hien:
        vi_tri = f"{c.tep}:{c.dong}" if c.co_vi_tri else f"{c.tep} (không rõ dòng)"
        dong.append(f"  [{c.muc:<7}] {vi_tri}  · {c.nguon}")
        dong.append(f"            {c.thong_diep.splitlines()[0][:110]}")
    if tran and len(nguon_hien) > tran:
        dong.append(f"  … còn {len(nguon_hien) - tran} phát hiện nữa "
                    "(bỏ --limit để xem đủ)")
    if not tat_ca and len(kq.muc) > len(kq.hien_tai):
        # KHÔNG lược trong im lặng: số bị giấu phải được nói ra.
        dong.append(f"  ({len(kq.muc) - len(kq.hien_tai)} mục thuộc lịch sử "
                    "đã khép, ẩn đi — `--all` để xem)")
    return "\n".join(dong)
