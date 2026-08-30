"""Bộ chuẩn đánh giá truy xuất — TC-20.

EAA-AIS-05 §4 (truy xuất Graph-RAG), ADR-07; FR-KG-03.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-61.

Câu hỏi mà bộ này trả lời
--------------------------

Kho tri thức lớn dần theo dự án. Mỗi trích đoạn mới được duyệt vào là một ứng
viên nữa cạnh tranh ba chỗ trong prompt, và không có gì bảo đảm bộ chọn vẫn
chọn đúng khi kho có 60 chunk như khi nó có 6. Đó là kiểu thoái lui **không
làm đỏ một test nào**: mã vẫn chạy, prompt vẫn lắp được, chỉ là nội dung dần
kém liên quan — và hậu quả hiện ra ở chỗ khác hẳn, dưới dạng mô hình bịa giá
trị thanh ghi vì thứ nó cần không có trong prompt.

Nên phải đo, và phải đo bằng một bộ chuẩn cố định: với module này thì trích
đoạn nào ĐÚNG LÀ liên quan. Câu trả lời ấy do người viết ra một lần, rồi máy
đối chiếu mãi.

precision@k, và vì sao không đo recall
---------------------------------------

Prompt chỉ có chỗ cho ``k`` trích đoạn, nên câu hỏi đúng là *"trong k cái được
chọn, bao nhiêu cái liên quan"* — đó là precision@k. Recall (lấy được bao nhiêu
phần trong số liên quan) đo một thứ mà ngân sách token vốn đã chặn: một module
cần năm chunk mà prompt chỉ chứa ba thì recall thấp là hệ quả của thiết kế,
không phải của bộ chọn.

Phép kiểm chunk nhiễu
----------------------

Một bộ chọn có thể giữ precision cao mà vẫn hỏng theo cách khác: nó kéo một
chunk chẳng liên quan vào một module chẳng liên quan, chỉ vì chunk ấy trùng
vài từ. Nên ngoài precision còn một phép kiểm nhị phân: chunk được đánh dấu
là nhiễu KHÔNG được xuất hiện trong kết quả của bất kỳ module nào không khai
nó là liên quan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

__all__ = [
    "GoldenSetError",
    "GoldenCase",
    "GoldenSet",
    "CaseResult",
    "RetrievalReport",
    "GOLDEN_FILE",
    "PRECISION_TOI_THIEU",
]

#: Bộ chuẩn ở tầng dự án — trích đoạn nào liên quan tới module nào là tri thức
#: của dự án, không phải của engine.
GOLDEN_FILE = "retrieval_golden.yaml"

#: Ngưỡng của TC-20. Không phải một con số tròn cho đẹp: với k=3, precision 0,9
#: nghĩa là trung bình chưa tới một phần ba của một chunk bị chọn nhầm trên mỗi
#: module — đủ chặt để bắt thoái lui, đủ lỏng để một ca biên không làm đỏ cả bộ.
PRECISION_TOI_THIEU = 0.9


class GoldenSetError(Exception):
    """Bộ chuẩn sai lược đồ, hoặc trỏ tới chunk không có thật."""


@dataclass(frozen=True)
class GoldenCase:
    """Một ca: module này thì trích đoạn nào ĐÚNG LÀ liên quan."""

    module_id: str
    uses: tuple[str, ...]
    relevant: tuple[str, ...]
    note: str = ""

    def __post_init__(self) -> None:
        if not self.module_id.strip():
            raise GoldenSetError("ca chuẩn không có mã module")
        if not self.relevant:
            raise GoldenSetError(
                f"{self.module_id!r}: không khai trích đoạn nào là liên quan. Một "
                "ca không có đáp án thì không đo được gì — nếu module này thật sự "
                "không cần trích đoạn nào thì đừng đưa nó vào bộ chuẩn."
            )


@dataclass(frozen=True)
class CaseResult:
    """Kết quả một ca."""

    module_id: str
    selected: tuple[str, ...]
    relevant: tuple[str, ...]
    noise_selected: tuple[str, ...] = ()

    @property
    def hits(self) -> tuple[str, ...]:
        return tuple(c for c in self.selected if c in self.relevant)

    @property
    def precision(self) -> float:
        """Tỉ lệ trúng trên số chunk THẬT SỰ được chọn.

        Mẫu số là ``len(selected)`` chứ không phải ``k``: khi kho chưa đủ chunk,
        bộ chọn trả về ít hơn k, và chia cho k sẽ phạt bộ chọn vì một chỗ thiếu
        của kho — một phép đo đổ lỗi nhầm chỗ.
        """
        if not self.selected:
            return 0.0
        return len(self.hits) / len(self.selected)

    def render(self) -> str:
        dong = [
            f"  {self.module_id:<22} precision {self.precision:.2f}  "
            f"({len(self.hits)}/{len(self.selected)})"
        ]
        sai = [c for c in self.selected if c not in self.relevant]
        if sai:
            dong.append(f"      chọn nhầm: {', '.join(sai)}")
        if self.noise_selected:
            dong.append(f"      ✗ KÉO VÀO CHUNK NHIỄU: {', '.join(self.noise_selected)}")
        return "\n".join(dong)


@dataclass
class RetrievalReport:
    """Kết quả chạy cả bộ chuẩn."""

    cases: tuple[CaseResult, ...] = ()
    top_k: int = 3
    noise_ids: tuple[str, ...] = ()

    @property
    def precision_at_k(self) -> float:
        """Trung bình precision trên các ca — mỗi module một phiếu.

        Không lấy trung bình gộp (tổng trúng / tổng chọn): làm thế thì module
        nào có nhiều chunk liên quan sẽ có tiếng nói lớn hơn, trong khi điều ta
        muốn biết là bộ chọn phục vụ TỪNG module ra sao.
        """
        if not self.cases:
            return 0.0
        return sum(c.precision for c in self.cases) / len(self.cases)

    @property
    def noise_leaks(self) -> tuple[CaseResult, ...]:
        return tuple(c for c in self.cases if c.noise_selected)

    @property
    def ok(self) -> bool:
        return self.precision_at_k >= PRECISION_TOI_THIEU and not self.noise_leaks


    @property
    def confidence_level(self) -> str:
        """Mức tin cậy theo bộ từ vựng chung của hệ (N-903).

        Đây là SỐ ĐO trên bộ chuẩn, không phải nhận định.
        """
        from eaa.confidence import DA_KIEM

        return DA_KIEM

    def render(self) -> str:
        dong = [
            f"Bộ chuẩn truy xuất — {len(self.cases)} ca, top-{self.top_k}",
            "",
            f"  precision@{self.top_k} = {self.precision_at_k:.3f} "
            f"(ngưỡng {PRECISION_TOI_THIEU})",
            "",
        ]
        dong += [c.render() for c in self.cases]

        if self.noise_ids:
            dong += ["", f"  Chunk nhiễu trong kho: {', '.join(self.noise_ids)}"]
        if self.noise_leaks:
            dong += [
                "",
                "  CHUNK NHIỄU BỊ KÉO VÀO. Một bộ chọn có thể giữ precision cao mà",
                "  vẫn hỏng theo cách này — kéo thứ chẳng liên quan vào chỉ vì trùng",
                "  vài từ. Đây là đường mà ảo giác 'có nguồn' đi vào prompt.",
            ]
        elif not self.ok:
            dong += [
                "",
                "  precision dưới ngưỡng. Kho lớn dần mà bộ chọn không theo kịp là",
                "  kiểu thoái lui KHÔNG làm đỏ test nào: mã vẫn chạy, prompt vẫn lắp",
                "  được, chỉ là nội dung dần kém liên quan — và hậu quả hiện ra ở chỗ",
                "  khác, dưới dạng mô hình bịa giá trị vì thứ nó cần không có.",
            ]
        else:
            dong += ["", "  ĐẠT — không chunk nhiễu nào lọt, precision trên ngưỡng."]
        return "\n".join(dong)


@dataclass
class GoldenSet:
    """Bộ chuẩn của một dự án."""

    cases: tuple[GoldenCase, ...] = ()
    #: Chunk cố ý KHÔNG liên quan tới ca nào — dùng để đo nhiễu.
    noise_ids: tuple[str, ...] = ()
    top_k: int = 3

    @classmethod
    def load(cls, path: str | Path) -> "GoldenSet | None":
        path = Path(path)
        if not path.is_file():
            return None
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise GoldenSetError(f"{path}: YAML không hợp lệ — {exc}") from exc
        if not isinstance(du_lieu, dict):
            raise GoldenSetError(f"{path}: nội dung phải là ánh xạ khóa–giá trị")

        cases: list[GoldenCase] = []
        for c in du_lieu.get("cases") or []:
            if not isinstance(c, dict):
                raise GoldenSetError(f"{path}: ca chuẩn phải là ánh xạ")
            cases.append(
                GoldenCase(
                    module_id=str(c.get("module", "")),
                    uses=tuple(str(x) for x in (c.get("uses") or [])),
                    relevant=tuple(str(x) for x in (c.get("relevant") or [])),
                    note=str(c.get("note", "")),
                )
            )
        return cls(
            cases=tuple(cases),
            noise_ids=tuple(str(x) for x in (du_lieu.get("noise") or [])),
            top_k=int(du_lieu.get("top_k", 3)),
        )

    def check_ids(self, datasheets: Any) -> list[str]:
        """Bộ chuẩn có trỏ tới chunk không có thật không.

        Một đáp án trỏ vào hư không sẽ kéo precision xuống mãi mãi mà chẳng vì
        lỗi nào của bộ chọn — và người ta sẽ đi sửa bộ chọn.
        """
        co = {c.id for c in datasheets.all()} if hasattr(datasheets, "all") else set()
        thieu: list[str] = []
        for ca in self.cases:
            for cid in ca.relevant:
                if cid not in co:
                    thieu.append(f"{ca.module_id}: đáp án {cid!r} không có trong kho")
        for cid in self.noise_ids:
            if cid not in co:
                thieu.append(f"chunk nhiễu {cid!r} không có trong kho")
        return thieu

    def evaluate(
        self, graph: Any, *, top_k: int | None = None, datasheets: Any = None
    ) -> RetrievalReport:
        """Chạy bộ chuẩn trên ĐÚNG đường truy xuất mà prompt dùng.

        Truyền ``datasheets`` thì bộ chuẩn đo cả hai tầng (quan hệ + BM25) —
        tức đúng thứ Composer lắp vào prompt. Bỏ trống thì chỉ đo tầng quan
        hệ, tiện để so xem tầng 2 thêm hay bớt được gì.

        Đo đúng đường thật là điều kiện để con số này có nghĩa: một bộ chuẩn đo
        một nhánh khác với nhánh chạy thật sẽ xanh trong khi prompt đang hỏng.
        """
        from eaa.rag import select_chunks

        k = top_k or self.top_k
        ket_qua: list[CaseResult] = []

        for ca in self.cases:
            if not graph.graph.has_node(ca.module_id):
                graph.add_module(ca.module_id, uses=ca.uses)
            chon = tuple(
                r.chunk_id
                for r in select_chunks(
                    graph, datasheets, ca.module_id, top_k=k, enable_bm25=datasheets is not None
                )
            )
            ket_qua.append(
                CaseResult(
                    module_id=ca.module_id,
                    selected=chon,
                    relevant=ca.relevant,
                    noise_selected=tuple(
                        c for c in chon if c in self.noise_ids and c not in ca.relevant
                    ),
                )
            )

        return RetrievalReport(cases=tuple(ket_qua), top_k=k, noise_ids=self.noise_ids)
