"""Prompt Composer — lắp ráp ngữ cảnh có nén, có ngân sách.

EAA-SDD-03 §4 (``build(task, state) -> Prompt``), EAA-SAD-02 §3 (Prompt
Composer), EAA-AIS-05 §3 (bảy kỹ thuật nén K1–K7 và Hình 1).

Luận điểm mà module này hiện thực hóa (AIS §1): **với lập trình nhúng, ngữ
cảnh NHỎ và ĐÚNG thắng ngữ cảnh DÀI và ĐỦ.** Cửa sổ ngữ cảnh của mô hình nền
rất lớn, nhưng đề án chủ động không tận dụng tối đa — ngữ cảnh càng dài thì
tín hiệu quyết định (một bit trong một thanh ghi) càng dễ chìm trong nhiễu,
chi phí càng cao, kết quả càng khó tái lập.

Bảy kỹ thuật, và chỗ chúng nằm trong mã này:

===  ==========================================  ==========================
K1   Bảng hóa ràng buộc                          :meth:`_lop_vai_tro`
K2   Chưng cất bảng thanh ghi                    đã làm khi nạp chunk (kb.py)
K3   Interface-only                              :meth:`_lop_interface`
K4   Trích chọn trạng thái                       :meth:`_trich_trang_thai`
K5   Chưng cất lỗi thành quy tắc                 ledger.rules_for
K6   Truy vấn đồ thị                             graph.facts_for
K7   Graph-RAG chọn chunk                        graph.select_chunks
===  ==========================================  ==========================

Ba bất biến:

* **Ràng buộc có mặt trong 100% lần gọi** (FR-KB-01, TC-04). Không có nhánh
  nào lắp prompt mà bỏ lớp này — nó nằm trong ``system_instruction``, và
  ``build`` từ chối trả về prompt thiếu nó.
* **Không bao giờ gửi lại thân module đã merge** (FR-CTX-02, TC-21). Lớp
  interface chỉ đọc tệp tiêu đề; đọc tệp mã nguồn là lỗi lập trình, và có
  kiểm tra chặn ngay tại đây chứ không chờ ai đó nhớ.
* **Vượt ngân sách là lỗi lắp ráp, không phải chuyện cứ gửi thử** (FR-CTX-01,
  TC-16).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from eaa.graph import KnowledgeGraph
from eaa.kb import Chunk, KnowledgeBase
from eaa.ledger import ErrorLedger
from eaa.llm.base import (
    LAYER_BUDGETS,
    TOTAL_BUDGET,
    BudgetExceeded,
    Prompt,
    PromptLayer,
    estimate_tokens,
)

__all__ = [
    "ComposerError",
    "Task",
    "ComposerConfig",
    "PromptComposer",
    "extract_function",
    "find_header",
]


class ComposerError(Exception):
    """Không lắp ráp được prompt từ dữ liệu hiện có."""


@dataclass
class Task:
    """Nhiệm vụ đưa cho mô hình — chuẩn hóa từ mô tả của người dùng (AIS §6.1)."""

    module_id: str
    goal: str = ""
    acceptance: tuple[str, ...] = ()
    #: Tài nguyên module chiếm dụng, khi module chưa vào backlog.
    uses: tuple[str, ...] = ()
    #: Module đã merge mà module này phụ thuộc — nguồn của lớp interface (K3).
    depends_on: tuple[str, ...] = ()
    #: Đường dẫn tệp mã module này sẽ sinh ra.
    output_files: tuple[str, ...] = ()


@dataclass
class ComposerConfig:
    """Tham số nén. Đổi ở đây, không rải hằng số khắp mã."""

    top_k_chunks: int = 3
    top_k_error_rules: int = 3
    budget: int = TOTAL_BUDGET
    layer_budgets: Mapping[str, int] = field(default_factory=lambda: dict(LAYER_BUDGETS))
    temperature: float = 0.2          # sinh mã — AIS §2
    temperature_tuning: float = 0.4   # phân tích tinh chỉnh tại G4


# --------------------------------------------------------------------------
# Tiện ích dùng chung
# --------------------------------------------------------------------------


def find_header(project_dir: Path, module_id: str) -> Path | None:
    """Tìm tệp tiêu đề của một module trong cây firmware của dự án."""
    firmware = Path(project_dir) / "firmware"
    if not firmware.is_dir():
        return None
    for path in sorted(firmware.rglob(f"{module_id}.h")):
        return path
    return None


_FUNC_START = re.compile(
    r"^[A-Za-z_][\w\s\*\(\),]*\([^;]*\)\s*$|^[A-Za-z_][\w\s\*]*\s+\w+\s*\([^;]*\)\s*\{?\s*$"
)


def extract_function(source: str, line: int, *, context: int = 2) -> str:
    """Trích đúng hàm chứa dòng lỗi, thay vì gửi lại cả tệp.

    Nền của kỹ thuật vá ở AIS §3.2 và của TC-19. Ngoài chuyện nén ~70%, việc
    chỉ gửi một hàm còn chặn một lỗi kinh điển của mô hình: viết lại cả tệp
    thì "sửa chỗ này, hỏng chỗ kia".

    Cách làm: từ dòng lỗi lùi lên tìm khai báo hàm gần nhất, rồi tiến xuống
    theo cân bằng ngoặc nhọn. Không phân tích cú pháp C đầy đủ — điều đó thừa
    cho mục đích ở đây, và một bộ phân tích thất bại im lặng còn tệ hơn: khi
    không tìm ra biên hàm, hàm này trả về một cửa sổ dòng quanh chỗ lỗi và nói
    rõ trong nội dung trả về.
    """
    dong = source.splitlines()
    if not dong:
        return ""
    chi_so = max(0, min(len(dong) - 1, line - 1))

    bat_dau = None
    for i in range(chi_so, -1, -1):
        noi_dung = dong[i].strip()
        if not noi_dung or noi_dung.startswith(("//", "#", "*", "/*")):
            continue
        if "(" in noi_dung and not noi_dung.endswith(";") and not noi_dung.startswith("}"):
            bat_dau = i
            break
        if noi_dung == "{" and i > 0 and "(" in dong[i - 1]:
            bat_dau = i - 1
            break

    if bat_dau is None:
        dau = max(0, chi_so - context)
        cuoi = min(len(dong), chi_so + context + 1)
        return (
            "// (không xác định được biên hàm; trích cửa sổ quanh dòng lỗi)\n"
            + "\n".join(dong[dau:cuoi])
        )

    can_bang = 0
    da_mo = False
    ket_thuc = len(dong)
    for i in range(bat_dau, len(dong)):
        can_bang += dong[i].count("{") - dong[i].count("}")
        if "{" in dong[i]:
            da_mo = True
        if da_mo and can_bang <= 0:
            ket_thuc = i + 1
            break

    return "\n".join(dong[bat_dau:ket_thuc])


def _boi_canh_host_test(host_test: Any) -> str:
    """Nói cho bộ sinh mã biết bài kiểm trên máy chủ trông thế nào.

    Cách dịch một module cho máy chủ là chuyện của NỀN TẢNG, nên phần chữ đến
    từ pack. Engine chỉ ghép nó vào đúng chỗ — cùng ranh giới mà TC-38 canh.
    """
    if not host_test:
        return ""
    ht = host_test if isinstance(host_test, dict) else {}
    if not ht:
        for ten in ("contract", "compiler", "cflags", "mock_include"):
            gia_tri = getattr(host_test, ten, None)
            if gia_tri:
                ht[ten] = gia_tri
    if not ht.get("contract"):
        return ""

    dong = ["## BÀI KIỂM TRÊN MÁY CHỦ (cổng `unittests`)", "", str(ht["contract"]).strip()]
    if ht.get("compiler"):
        co = " ".join(str(x) for x in (ht.get("cflags") or []))
        dong += ["", f"Trình dịch máy chủ: `{ht['compiler']}` {co}".rstrip()]

    # Đường dẫn ĐÃ GIẢI, không phải tên thư mục.
    #
    # Bản trước nói "thư mục `hostmock` của Platform Pack", và mô hình viết
    # `-Ihostmock` — một đường dẫn TƯƠNG ĐỐI so với thư mục firmware, nơi không
    # có thư mục ấy. Tiêu đề giả nằm trong pack, cách đó vài tầng. Nói tên mà
    # không nói chỗ là mời một đường dẫn sai (SL-143).
    duong_dan = ht.get("mock_include_path") or ht.get("mock_include")
    if duong_dan:
        dong.append(f"Tiêu đề giả cho mã chạm thanh ghi: `-I{duong_dan}`")
    for nguon in ht.get("support_sources") or ():
        dong.append(
            f"Dịch KÈM tệp này, nếu không sẽ thiếu ký hiệu lúc liên kết: `{nguon}`"
        )
    return "\n".join(dong) + "\n"


def _boi_canh_mau_du_an(prompts: Any, module_id: str) -> str:
    """Luật thiết kế RIÊNG của dự án cho một module, nếu dự án có khai.

    `PromptLibrary` là cơ chế đã có sẵn cho đúng việc này — *"mẫu của dự án ghi
    đè mẫu của pack… để một dự án chỉnh được cách diễn đạt cho bài toán của nó
    mà không phải sửa pack"* (NFR-05). Nó được nạp vào kho tri thức từ sprint
    đầu và **chưa đường nào đọc**, nên tri thức thiết kế của dự án không có
    cách nào vào tới prompt (SL-135).

    Lấy đúng mẫu mang tên module, không lấy mẫu của module khác: nhét luật của
    module này vào prompt module kia là làm nhiễu chứ không làm giàu.
    """
    if prompts is None:
        return ""
    try:
        if not prompts.has(module_id):
            return ""
        mau = prompts.get(module_id)
    except Exception:  # noqa: BLE001 - thư mục mẫu hỏng không được chặn sinh mã
        return ""
    than = (getattr(mau, "body", "") or "").strip()
    if not than:
        return ""
    return "## LUẬT THIẾT KẾ CỦA DỰ ÁN CHO MODULE NÀY\n" + than + "\n"


def _bang_rang_buoc(constraints: Any) -> str:
    """K1 — dịch ràng buộc thành mệnh lệnh ngắn thay vì văn xuôi giải thích.

    Nén ~60%, nhưng lý do quan trọng hơn là hành vi: mệnh lệnh ngắn được mô
    hình tuân thủ tốt hơn một đoạn giải thích vì sao nên tuân thủ.
    """
    cam = constraints.forbidden
    gioi_han = constraints.limits
    phong_cach = constraints.style

    if not (cam or gioi_han or phong_cach):
        # Trả về rỗng chứ không trả về một tiêu đề trống: một bảng ràng buộc
        # chỉ có tiêu đề sẽ qua được mọi phép kiểm "có nội dung không" trong
        # khi thực chất không ràng buộc gì cả.
        return ""

    dong: list[str] = ["## RÀNG BUỘC CỨNG (bắt buộc, không thương lượng)"]

    if cam:
        dong.append("")
        for muc in cam:
            dong.append(f"- CẤM {muc}")

    if gioi_han:
        dong.append("")
        dong.append("| Giới hạn | Trần |")
        dong.append("|---|---|")
        for ten, gia_tri in gioi_han.items():
            dong.append(f"| {ten} | {gia_tri} |")

    if phong_cach:
        dong.append("")
        for ten, gia_tri in phong_cach.items():
            dong.append(f"- {ten}: {gia_tri}")

    return "\n".join(dong)


# --------------------------------------------------------------------------
# Composer
# --------------------------------------------------------------------------


class PromptComposer:
    """Ghép prompt từ Knowledge Base, Knowledge Graph và Project State."""

    #: Vai trò — phần cố định của system instruction. Cố ý không nhắc bất kỳ
    #: nền tảng nào: nền tảng đến từ Platform Pack, ràng buộc đến từ dự án.
    ROLE = (
        "Bạn là kỹ sư firmware hệ nhúng thời gian thực, viết mã C cho vi điều "
        "khiển tài nguyên hạn chế. Bạn tuân thủ tuyệt đối các ràng buộc cứng "
        "dưới đây; khi ràng buộc mâu thuẫn với cách viết thông thường, ràng "
        "buộc thắng. Bạn KHÔNG được đoán giá trị thanh ghi hay tham số điện: "
        "chỉ dùng những gì có trong trích đoạn tài liệu được cung cấp, và mỗi "
        "hàm cấu hình thanh ghi phải mang một dòng trích dẫn '// ref: <mã "
        "chunk>'. Thiếu thông tin thì nói thiếu, không lấp chỗ trống."
    )

    OUTPUT_FORMAT = (
        "## ĐỊNH DẠNG TRẢ LỜI\n"
        "Trả về mã nguồn trong các khối, mỗi tệp một khối:\n"
        "```file:<đường dẫn tương đối>\n<nội dung tệp>\n```\n"
        "Không kèm giải thích ngoài khối. Sai định dạng tính là một lần hỏng."
    )

    def __init__(
        self,
        kb: KnowledgeBase,
        graph: KnowledgeGraph,
        ledger: ErrorLedger | None = None,
        config: ComposerConfig | None = None,
    ) -> None:
        self.kb = kb
        self.graph = graph
        self.ledger = ledger
        self.config = config or ComposerConfig()
        #: Khối `host_test` của Platform Pack — cách kiểm một module trên máy
        #: chủ. Không có thì prompt không nói gì về nó, và mô hình đoán (SL-134).
        self.host_test: Any = None

    # ----------------------------------------------------------------------
    # Lắp ráp
    # ----------------------------------------------------------------------

    def build(
        self,
        task: Task,
        state: Any = None,
        *,
        counter: Callable[[str], int] | None = None,
    ) -> Prompt:
        """Lắp prompt sinh mã cho một module — EAA-SDD-03 §4."""
        dem = counter or estimate_tokens
        ngan_sach = self.config.layer_budgets

        chunks = self._chon_chunk(task)
        lop = [
            PromptLayer(
                "hardware_facts",
                self._lop_su_kien_phan_cung(task),
                budget=ngan_sach.get("hardware_facts", 0),
            ),
            PromptLayer(
                "datasheet_chunks",
                self._lop_chunk(chunks),
                budget=ngan_sach.get("datasheet_chunks", 0),
                required=True,
            ),
            PromptLayer(
                "interfaces",
                self._lop_interface(task),
                budget=ngan_sach.get("interfaces", 0),
            ),
            PromptLayer(
                "error_rules",
                self._lop_quy_tac_loi(task, chunks, dem),
                budget=ngan_sach.get("error_rules", 0),
            ),
            # Hai lớp dưới đứng TRƯỚC lớp nhiệm vụ, và sống sót qua vòng vá:
            # luật thiết kế của dự án và hợp đồng bài kiểm không được biến mất
            # đúng lúc mô hình đang sửa mã (SL-135).
            PromptLayer(
                "project_rules",
                _boi_canh_mau_du_an(getattr(self.kb, "prompts", None), task.module_id),
                budget=ngan_sach.get("project_rules", 0),
            ),
            PromptLayer(
                "host_test",
                _boi_canh_host_test(getattr(self, "host_test", None)),
                budget=ngan_sach.get("host_test", 0),
            ),
            PromptLayer(
                "task",
                self._lop_nhiem_vu(task, state),
                budget=ngan_sach.get("task", 0),
                required=True,
            ),
        ]

        prompt = Prompt(
            system_instruction=self._lop_vai_tro(),
            layers=[l for l in lop if l.content.strip() or l.required],
            module=task.module_id,
            constraints_version=self.kb.constraints.content_version,
            chunk_ids=tuple(c.id for c in chunks),
            temperature=self.config.temperature,
            budget=self.config.budget,
            system_budget=ngan_sach.get("role_constraints", 0),
        )

        self._kiem_bat_bien(prompt)
        self._vua_ngan_sach(prompt, dem)
        return prompt

    def build_repair(
        self,
        task: Task,
        state: Any,
        report: Any,
        sources: Mapping[str, str],
        *,
        counter: Callable[[str], int] | None = None,
    ) -> Prompt:
        """Lắp prompt VÁ sau khi một cổng kiểm chứng báo hỏng — AIS §3.2, TC-19.

        Khác biệt duy nhất mà cũng là toàn bộ ý nghĩa: prompt này KHÔNG chứa
        toàn văn tệp. Chỉ thông báo lỗi của cổng, đúng những hàm chứa lỗi, và
        yêu cầu trả về bản vá theo dạng khối thay thế hàm.
        """
        dem = counter or estimate_tokens
        prompt = self.build(task, state, counter=dem)

        prompt.layers = [l for l in prompt.layers if l.name != "task"]

        # Phần của lớp `repair` là SÀN, không phải trần.
        #
        # Nó là lớp cuối được thêm vào và nó thay chỗ lớp `task`, nên nó không
        # cạnh tranh với ai: chỗ các lớp khác không dùng tới thì để trống. Kích
        # thước của nó lại do THÂN HÀM ĐANG HỎNG quyết định — thứ thay đổi theo
        # từng module.
        #
        # Giữ nó làm trần cứng nghĩa là "hàm của bạn to quá, chúng tôi thậm chí
        # không thử sửa" trong khi gần nửa trần tổng bỏ không. Đo được ba lần
        # liên tiếp ở bài robot cân bằng: 1836/1600 rồi 1916/1800, với prompt
        # tổng lần lượt 4752 và 4255 trên 8000 (SL-147).
        #
        # Trần TỔNG vẫn là trần thật và vẫn chặn — chỉ chỗ trống mới được dùng.
        san = self.config.layer_budgets.get("repair", 0)
        da_dung = sum(l.tokens(dem) for l in prompt.layers)
        if prompt.system_instruction:
            da_dung += dem(prompt.system_instruction)
        cho_trong = max(0, prompt.budget - da_dung)
        phan_cua_no = max(san, cho_trong)

        prompt.layers.append(
            PromptLayer(
                "repair",
                self._lop_va(task, report, sources, tran=phan_cua_no, dem=dem),
                budget=phan_cua_no,
                required=True,
            )
        )

        self._kiem_bat_bien(prompt)
        self._vua_ngan_sach(prompt, dem)
        return prompt

    # ----------------------------------------------------------------------
    # Từng lớp
    # ----------------------------------------------------------------------

    def _lop_vai_tro(self) -> str:
        """K1 — vai trò + bảng ràng buộc, đặt vào system instruction (AIS §2)."""
        return f"{self.ROLE}\n\n{_bang_rang_buoc(self.kb.constraints)}"

    def _lop_su_kien_phan_cung(self, task: Task) -> str:
        """K6 — vài dòng sự kiện từ đồ thị, thay cho cả hồ sơ phần cứng."""
        if not self.graph.graph.has_node(task.module_id):
            self.graph.add_module(
                task.module_id, uses=task.uses, depends_on=task.depends_on
            )
        su_kien = self.graph.facts_for(task.module_id)
        if not su_kien:
            return ""
        return "## PHẦN CỨNG LIÊN QUAN\n" + "\n".join(f"- {d}" for d in su_kien)

    def _chon_chunk(self, task: Task) -> list[Chunk]:
        """K7 — Graph-RAG chọn chunk, BM25 bổ trợ khi quan hệ chưa lấp đủ.

        Hai tầng theo ADR-07, và thứ tự không đảo được: đồ thị chỉ đích danh
        trước, BM25 chỉ lấp chỗ còn trống và chỉ nhận ứng viên vượt sàn điểm.
        Xem ``eaa/rag.py`` để biết vì sao sàn ấy là thứ giữ tầng 2 khỏi thành
        tầng nhiễu.
        """
        from eaa.rag import select_chunks

        if not self.graph.graph.has_node(task.module_id):
            self.graph.add_module(
                task.module_id, uses=task.uses, depends_on=task.depends_on
            )
        chon = select_chunks(
            self.graph,
            self.kb.datasheets,
            task.module_id,
            top_k=self.config.top_k_chunks,
        )
        return [self.kb.datasheets.get(r.chunk_id) for r in chon]

    def _lop_chunk(self, chunks: Sequence[Chunk]) -> str:
        """K2 — chunk đã ở dạng bảng thanh ghi–bit từ lúc nạp kho."""
        if not chunks:
            return (
                "## TRÍCH ĐOẠN TÀI LIỆU\n"
                "(không có trích đoạn nào được duyệt cho module này — KHÔNG "
                "được đoán giá trị thanh ghi; báo thiếu thông tin.)"
            )
        phan: list[str] = ["## TRÍCH ĐOẠN TÀI LIỆU ĐÃ DUYỆT"]
        for chunk in chunks:
            phan.append(
                f"\n### {chunk.id} — {chunk.topic or chunk.peripheral}\n"
                f"Nguồn: {chunk.source}\n"
                f"Trích dẫn bắt buộc trong mã: `{chunk.citation}`\n\n"
                f"{chunk.body}"
            )
        return "\n".join(phan)

    def _lop_interface(self, task: Task, *, chi_chu_ky: bool = False) -> str:
        """K3 — module đã merge chỉ xuất hiện qua tệp tiêu đề + một dòng tóm tắt.

        Kỹ thuật nén quan trọng nhất khi dự án lớn dần (~80–90% trên phần mã
        nguồn). Ở đây nó cũng là một rào an toàn: hàm này chỉ mở tệp ``.h``,
        nên không có đường nào để thân module đã merge lọt vào prompt.
        """
        if not task.depends_on:
            return ""

        phan: list[str] = ["## INTERFACE CÁC MODULE ĐÃ CÓ (chỉ dùng, không viết lại)"]
        for module_id in task.depends_on:
            header = find_header(self.kb.project_dir, module_id)
            if header is None:
                phan.append(f"\n### {module_id}\n(chưa có tệp tiêu đề trong cây firmware)")
                continue

            noi_dung = header.read_text(encoding="utf-8")
            tom_tat = self._tom_tat_header(noi_dung)
            if chi_chu_ky:
                noi_dung = self._chi_lay_khai_bao(noi_dung)
            phan.append(f"\n### {module_id} — {tom_tat}\n```c\n{noi_dung.strip()}\n```")
        return "\n".join(phan)

    @staticmethod
    def _tom_tat_header(noi_dung: str) -> str:
        """Một dòng tóm tắt chức năng, lấy từ chú thích đầu tệp tiêu đề."""
        for dong in noi_dung.splitlines():
            sach = dong.strip().lstrip("/*").lstrip("*").strip()
            if sach and not dong.strip().startswith("#"):
                return sach[:100]
        return "(không có mô tả)"

    @staticmethod
    def _chi_lay_khai_bao(noi_dung: str) -> str:
        """Rút gọn tệp tiêu đề còn các dòng khai báo — dùng khi cần thêm chỗ."""
        giu = [
            dong
            for dong in noi_dung.splitlines()
            if dong.strip().endswith(";") or dong.strip().startswith("typedef")
        ]
        return "\n".join(giu) if giu else noi_dung

    def _lop_quy_tac_loi(
        self,
        task: Task,
        chunks: Sequence[Chunk],
        dem: Callable[[str], int] | None = None,
    ) -> str:
        """K5 — top-3 quy tắc chưng cất từ Error Ledger (FR-KB-03, TC-10).

        Lấy top-k rồi NHÉT VỪA phần của lớp, ưu tiên giữ NGUYÊN VẸN quy tắc
        xếp hạng cao nhất thay vì cắt cụt cả ba.

        Vì sao phải nhét vừa ở đây: quy tắc do người viết lúc từ chối gate
        không bị chặn độ dài (`LedgerEntry.as_rule` chỉ cắt nhánh suy ra từ mô
        tả). Một lý do từ chối viết cẩn thận dễ vượt 300 token của lớp — và
        khi lớp vượt phần, bộ lược ngân sách **xóa sạch cả lớp**. Nghĩa là câu
        người vừa viết ra để dạy mô hình đừng lặp lại lỗi sẽ không tới được
        mô hình, trong khi prompt mới dùng chưa tới một phần ba trần tổng.

        Gặp thật ở SL-135: `eaa gate reject` in ra *"Lý do đã ghi vào Error
        Ledger và sẽ có mặt trong prompt lần sinh lại"*, và nó đã không có mặt.
        """
        if self.ledger is None:
            return ""

        ngoai_vi = chunks[0].peripheral if chunks else ""
        quy_tac = self.ledger.rules_for(
            task.module_id,
            peripheral=ngoai_vi,
            registers=self.graph.registers_for(task.module_id),
            top_k=self.config.top_k_error_rules,
        )
        if not quy_tac:
            return ""

        do_dai = dem or estimate_tokens
        tran = self.config.layer_budgets.get("error_rules", 0)
        tieu_de = "## LỖI ĐÃ GẶP — TUYỆT ĐỐI TRÁNH LẶP LẠI"
        if not tran:
            return tieu_de + "\n" + "\n".join(f"- {r}" for r in quy_tac)

        # Quy tắc ĐẦU BẢNG luôn có mặt — nguyên vẹn nếu vừa, cắt có dấu nếu
        # không. Không được phép bỏ nó để lấy một quy tắc ngắn hơn ở dưới:
        # thứ hạng đã nói nó liên quan nhất (lỗi của chính module này, vừa bị
        # người từ chối), còn quy tắc dưới nó thường là lỗi cũ đã khép. Bản
        # sửa đầu của SL-136 mắc đúng lỗi này — nó "nhét vừa" bằng cách lặng
        # lẽ nhảy qua lý do từ chối mới nhất và giữ lý do của vòng trước.
        dau = f"- {quy_tac[0]}"
        if do_dai(f"{tieu_de}\n{dau}") > tran:
            duoi = " […] (rút gọn — bản đầy đủ: eaa ledger show)"
            than = quy_tac[0]
            while than and do_dai(f"{tieu_de}\n- {than}{duoi}") > tran:
                than = than[: max(0, len(than) - 40)].rstrip()
            dau = f"- {than}{duoi}"

        giu = [dau]
        for r in quy_tac[1:]:
            thu = giu + [f"- {r}"]
            if do_dai("\n".join([tieu_de, *thu])) <= tran:
                giu = thu

        return "\n".join([tieu_de, *giu])

    def _trich_trang_thai(self, task: Task, state: Any) -> list[str]:
        """K4 — chỉ phần Project State liên quan module hiện tại, không cả backlog.

        Giữ lớp trạng thái ở khoảng 100 token bất kể dự án lớn đến đâu.
        """
        if state is None:
            return []
        dong: list[str] = []
        muc = getattr(state, "module", lambda _: None)(task.module_id)
        if muc is not None:
            dong.append(f"Trạng thái module: {muc.status}, số lần tự sửa đã dùng: {muc.retries}.")
        for phu_thuoc in task.depends_on:
            khac = getattr(state, "module", lambda _: None)(phu_thuoc)
            if khac is not None:
                dong.append(f"Phụ thuộc {phu_thuoc}: {khac.status}.")
        return dong

    def _lop_nhiem_vu(self, task: Task, state: Any) -> str:
        phan: list[str] = [f"## NHIỆM VỤ\nViết module `{task.module_id}`."]
        if task.goal:
            phan.append(task.goal.strip())

        if task.output_files:
            phan.append("Tệp cần sinh: " + ", ".join(f"`{f}`" for f in task.output_files) + ".")

        if task.acceptance:
            phan.append(
                "\n### TIÊU CHÍ NGHIỆM THU\n"
                + "\n".join(f"- {tc}" for tc in task.acceptance)
            )

        trang_thai = self._trich_trang_thai(task, state)
        if trang_thai:
            phan.append("\n### TRẠNG THÁI\n" + "\n".join(f"- {d}" for d in trang_thai))

        phan.append("\n" + self.OUTPUT_FORMAT)
        return "\n\n".join(phan)

    def _lop_va(
        self,
        task: Task,
        report: Any,
        sources: Mapping[str, str],
        *,
        tran: int = 0,
        dem: Callable[[str], int] | None = None,
    ) -> str:
        """Nội dung lớp vá: lỗi của cổng + đúng hàm liên quan + yêu cầu trả bản vá."""
        cong = getattr(report, "gate", "kiểm chứng")
        loi = list(getattr(report, "errors", []) or [])

        phan: list[str] = [
            f"## SỬA LỖI — cổng `{cong}` báo không đạt",
            "Dưới đây là thông báo lỗi và ĐÚNG các hàm chứa lỗi. "
            "Toàn văn tệp cố ý không được gửi kèm.",
            "\n### THÔNG BÁO LỖI\n" + "\n".join(f"- {e}" for e in loi)
            if loi
            else "\n### THÔNG BÁO LỖI\n- (cổng không nêu lỗi cụ thể)",
        ]

        da_trich: set[tuple[str, str]] = set()
        for e in loi:
            ten_tep = getattr(e, "file", None)
            so_dong = getattr(e, "line", None)
            if not ten_tep or ten_tep not in sources or not so_dong:
                continue
            doan = extract_function(sources[ten_tep], int(so_dong))
            khoa = (ten_tep, doan[:80])
            if khoa in da_trich:
                continue
            da_trich.add(khoa)
            phan.append(f"\n### ĐOẠN LỖI — {ten_tep} (quanh dòng {so_dong})\n```c\n{doan}\n```")

        if not da_trich:
            # Không định vị được hàm lỗi — và đây KHÔNG phải lúc mời hỏi lại.
            #
            # Bản trước viết "hãy hỏi lại phần mã cần thiết". Đường ống không
            # có kênh nào nhận câu hỏi: nó chỉ bóc khối ```file:``` từ phản hồi.
            # Nên mọi vòng vá rơi vào nhánh này đều kết thúc bằng "Phản hồi
            # không chứa khối file: nào" và tính là một lần hỏng — sáu lần liên
            # tiếp trong một buổi, mỗi lần một lượt gọi mô hình (SL-149).
            #
            # Nhánh này chạy đúng khi lỗi KHÔNG nằm ở một dòng của tệp nguồn:
            # bài kiểm đỏ, lỗi liên kết, lỗi định dạng. Lúc ấy thứ mô hình cần
            # là TOÀN VĂN những tệp liên quan, không phải một lời mời hỏi.
            # Nhét vừa CHỖ TRỐNG THẬT, không dội hết. Gửi tất cả tệp làm
            # prompt vượt 8137/8000 và vòng vá lại chết — chỉ đổi một kiểu
            # hỏng lấy một kiểu hỏng khác.
            #
            # Thứ tự ưu tiên: tệp được thông báo lỗi nhắc tên trước, rồi tới
            # mã nguồn, cuối cùng là mã kiểm. Tệp nào không vừa thì NÊU TÊN —
            # mô hình cần biết nó đang không nhìn thấy gì.
            do_dai = dem or estimate_tokens
            nhac_ten = " ".join(str(e) for e in loi)
            def _uu_tien(ten: str) -> tuple[int, str]:
                return (0 if ten in nhac_ten else (1 if ten.endswith((".c", ".h")) else 2), ten)

            con_lai_tran = max(0, tran - do_dai("\n\n".join(phan)) - 200)
            bo_qua: list[str] = []
            for ten_tep in sorted(sources, key=_uu_tien):
                khoi = f"\n### TOÀN VĂN — {ten_tep}\n```\n{sources[ten_tep]}\n```"
                gia = do_dai(khoi)
                if gia <= con_lai_tran:
                    phan.append(khoi)
                    con_lai_tran -= gia
                else:
                    bo_qua.append(ten_tep)
            if bo_qua:
                phan.append(
                    "\n(KHÔNG kèm được vì hết chỗ: " + ", ".join(bo_qua)
                    + " — sửa trong phạm vi những tệp có ở trên)"
                )
            phan.append(
                "\n### ĐỊNH DẠNG TRẢ LỜI\n"
                "Lỗi này không định vị được về một hàm, nên trả về TOÀN BỘ tệp "
                "cần sửa, mỗi tệp một khối:\n"
                "```file:<đường dẫn tệp>\n<toàn bộ nội dung tệp sau khi sửa>\n```\n"
                "Chỉ gửi những tệp thật sự phải đổi. **Bắt buộc** có ít nhất một "
                "khối như trên — câu trả lời không có khối nào tính là một lần "
                "hỏng của vòng tự sửa, và không ai đọc được nó."
            )
            return "\n\n".join(phan)

        phan.append(
            "\n### ĐỊNH DẠNG TRẢ LỜI\n"
            "Chỉ trả về CÁC HÀM đã sửa, mỗi hàm trong một khối:\n"
            "```file:<đường dẫn tệp>\n<toàn bộ hàm đã sửa, kể cả dòng khai báo>\n```\n"
            "KHÔNG viết lại toàn bộ tệp — viết lại cả tệp thường sửa chỗ này, "
            "hỏng chỗ kia.\n"
            "**Bắt buộc** có ít nhất một khối như trên."
        )
        return "\n\n".join(phan)

    # ----------------------------------------------------------------------
    # Bất biến và ngân sách
    # ----------------------------------------------------------------------

    def _kiem_bat_bien(self, prompt: Prompt) -> None:
        """Chặn tại chỗ hai lỗi mà nếu lọt thì rất khó phát hiện về sau.

        Phép kiểm ràng buộc cố ý đối chiếu TỪNG MỤC của ``constraints.yaml``
        chứ không chỉ hỏi "lớp này có chữ không". Một tiêu đề "RÀNG BUỘC CỨNG"
        đứng trơ một mình qua được phép kiểm hời hợt trong khi chẳng ràng buộc
        gì — mà TC-04 đòi "100% prompt chứa NỘI DUNG constraints.yaml hiện
        hành", không phải chứa cái nhan đề của nó.
        """
        rang_buoc = self.kb.constraints
        thieu: list[str] = []

        if not prompt.system_instruction.strip():
            thieu.append("toàn bộ lớp ràng buộc")
        else:
            for cam in rang_buoc.forbidden:
                if f"CẤM {cam}" not in prompt.system_instruction:
                    thieu.append(f"điều cấm {cam!r}")
            for ten in rang_buoc.limits:
                if ten not in prompt.system_instruction:
                    thieu.append(f"giới hạn {ten!r}")

        if not (rang_buoc.forbidden or rang_buoc.limits or rang_buoc.style):
            thieu.append(
                "dự án chưa khai báo ràng buộc cứng nào — Hard Constraints Spec "
                "là sản phẩm của công đoạn A1 và là đầu vào bắt buộc của mọi prompt"
            )

        if thieu:
            raise ComposerError(
                "Prompt thiếu ràng buộc — FR-KB-01/TC-04 đòi hỏi ràng buộc có mặt "
                "trong 100% lần gọi mô hình. Thiếu: " + "; ".join(thieu)
            )

        interface = prompt.layer("interfaces")
        if interface and re.search(r"```file:[^\n]*\.c\b", interface.content):
            raise ComposerError(
                "Lớp interface chứa tệp mã nguồn — FR-CTX-02 cấm gửi lại thân "
                "module đã merge; chỉ được gửi tệp tiêu đề (K3)."
            )

    def _vua_ngan_sach(self, prompt: Prompt, dem: Callable[[str], int]) -> None:
        """Cố lược bớt phần ít quan trọng nhất trước khi tuyên bố vượt ngân sách.

        Thứ tự nhường chỗ: quy tắc lỗi → interface rút còn khai báo. Chunk tài
        liệu KHÔNG bao giờ bị lược âm thầm: lược một chunk nghĩa là để mô hình
        cấu hình một thanh ghi mà không có tài liệu, đúng thứ mà toàn bộ cơ chế
        chống ảo giác sinh ra để ngăn. Hết cách thì báo lỗi lắp ráp (FR-CTX-01).

        Mọi thứ bị lược đều được ghi vào ``prompt.trimmed`` để KPI theo dõi —
        vòng tự sửa chạm N vì thiếu ngữ cảnh là tín hiệu phải chỉnh top-k, và
        chỉ biết được nếu việc lược bỏ không im lặng (AIS §12).
        """
        try:
            prompt.check_budget(dem)
            return
        except BudgetExceeded:
            pass

        quy_tac = prompt.layer("error_rules")
        if quy_tac is not None and quy_tac.content.strip():
            prompt.layers = [l for l in prompt.layers if l.name != "error_rules"]
            prompt.trimmed.append("error_rules")
            try:
                prompt.check_budget(dem)
                return
            except BudgetExceeded:
                pass

        interface = prompt.layer("interfaces")
        if interface is not None and interface.content.strip():
            prompt.layers = [
                PromptLayer(
                    l.name,
                    self._lop_interface(
                        Task(
                            module_id=prompt.module,
                            depends_on=tuple(self._modules_trong_interface(l.content)),
                        ),
                        chi_chu_ky=True,
                    ),
                    budget=l.budget,
                    required=l.required,
                )
                if l.name == "interfaces"
                else l
                for l in prompt.layers
            ]
            prompt.trimmed.append("interfaces→chỉ khai báo")

        prompt.check_budget(dem)

    @staticmethod
    def _modules_trong_interface(noi_dung: str) -> list[str]:
        return re.findall(r"^### (\S+)", noi_dung, flags=re.MULTILINE)
