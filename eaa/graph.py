"""Knowledge Graph phần cứng — quan hệ giữa tài nguyên, tri thức và mã.

EAA-AIS-05 §5, ADR-08, FR-KG-01/02/03. Xem `docs/SAI_LECH_THIET_KE.md` mục
SL-04 về việc module này không có trong cây thư mục gốc của SDD.

Đồ thị làm ba việc mà truy xuất văn bản thuần túy không làm được:

1.  **Kiểm xung đột tài nguyên trước khi sinh mã** (§5.2). Hai module cùng
    chiếm một bộ đếm hay một chân là loại lỗi AI hoàn toàn không nhìn thấy —
    nó nằm NGOÀI tệp đang viết. Bắt ở giây thứ nhất, ngay lúc khai báo module
    (quy trình P2), thay vì bắt trên thiết bị thật.
2.  **Graph-RAG** (§5.3): chọn chunk theo chuỗi quan hệ
    ``module –uses→ ngoại vi –configured_by→ thanh ghi –documented_in→ chunk``.
    Kết quả là tập chunk đúng theo CẤU TRÚC phần cứng, không phải "giống về từ
    ngữ" — tính tất định mà khớp văn bản không bảo đảm được.
3.  **Phân tích ảnh hưởng ngược** (§5.4, §8.3): đổi một tài nguyên hay thay
    một chunk thì những module nào phải xem lại. Đây là nền của tập lỗi thời
    (stale set).

Bất biến quan trọng nhất của module — **mặc định là ĐỘC CHIẾM**. Engine không
biết bộ đếm thì độc chiếm còn bus thì dùng chung được; nó chỉ biết hỏi hồ sơ
phần cứng. Tài nguyên không khai báo ``shareable: true`` được coi là độc
chiếm, nên quên khai báo dẫn tới một cảnh báo thừa (phiền), chứ không dẫn tới
một xung đột lọt lưới (hỏng thiết bị).

Đồ thị DỰNG TỰ ĐỘNG từ dữ liệu đã có — hồ sơ phần cứng, khai báo ``uses`` của
module, frontmatter chunk. Không nhập tay lần thứ hai, nên nó không thể lệch
khỏi nguồn theo kiểu tài liệu lệch khỏi code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import networkx as nx
import yaml

from eaa.kb import Chunk, DatasheetStore, HardwareProfile

__all__ = [
    "GraphError",
    "Conflict",
    "KnowledgeGraph",
    "NODE_KINDS",
    "EDGE_KINDS",
    "DEFAULT_TOP_K",
]

#: Loại nút — cố ý là danh từ chung; engine không biết một "peripheral" cụ thể
#: nào tồn tại trên đời (FR-PLT-01).
NODE_KINDS: tuple[str, ...] = (
    "mcu",
    "peripheral",
    "component",
    "register",
    "pin",
    "module",
    "chunk",
    "constraint",
)

EDGE_KINDS: tuple[str, ...] = (
    "has",           # mcu → peripheral
    "configured_by", # peripheral → register
    "on_bus",        # component → peripheral
    "connects_to",   # component → pin
    "belongs_to",    # pin → peripheral
    "documented_in", # register|component → chunk
    "uses",          # module → peripheral|component
    "depends_on",    # module → module
    "constrained_by",# module → constraint
)

#: AIS §4.2: lấy top-k = 3, mỗi chunk ≤ 300 token.
DEFAULT_TOP_K = 3


class GraphError(Exception):
    """Đồ thị không dựng được từ dữ liệu đã cho."""


#: Thuộc tính nút do đồ thị tự quản; dữ liệu dự án không được ghi đè.
_RESERVED_ATTRS = frozenset({"kind", "shareable", "id"})


def _attrs(source: dict[str, Any], *, exclude: Iterable[str] = ()) -> dict[str, Any]:
    """Lọc thuộc tính từ hồ sơ phần cứng để gắn vào nút đồ thị.

    Hồ sơ dùng khóa ``kind`` cho loại ngoại vi ("timer", "i2c"…), trùng tên với
    thuộc tính ``kind`` mà đồ thị dùng để phân loại nút. Đổi tên thành
    ``subkind`` thay vì bỏ đi: đó là dữ liệu của kỹ sư, mất đi thì báo cáo
    nghèo hơn mà chẳng được gì.
    """
    bo_qua = _RESERVED_ATTRS | set(exclude)
    ket_qua = {k: v for k, v in source.items() if k not in bo_qua}
    if source.get("kind"):
        ket_qua["subkind"] = source["kind"]
    return ket_qua


@dataclass(frozen=True)
class Conflict:
    """Một phát hiện của bộ kiểm xung đột, đủ để con người phân xử ngay."""

    kind: str
    resource: str
    modules: tuple[str, ...]
    message: str
    #: Đường đi trong đồ thị dẫn tới phát hiện — để báo cáo giải thích được.
    evidence: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.message


@dataclass
class KnowledgeGraph:
    """Đồ thị tri thức của một dự án."""

    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    version: int = 1

    # ----------------------------------------------------------------------
    # Dựng
    # ----------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        hardware: HardwareProfile,
        datasheets: DatasheetStore | None = None,
        modules: Iterable[Any] = (),
        *,
        constraints: Any = None,
    ) -> "KnowledgeGraph":
        """Dựng đồ thị từ hồ sơ phần cứng + chunk đã duyệt + backlog.

        ``modules`` nhận các đối tượng có ``id``, ``uses`` và ``depends_on`` —
        tức ``BacklogItem`` của Project State, nhưng không ràng buộc kiểu để
        kiểm xung đột chạy được cả với module CHƯA vào backlog (quy trình P2:
        kiểm ngay lúc khai báo, trước khi duyệt).
        """
        kg = cls()
        g = kg.graph

        mcu = hardware.mcu
        mcu_id = str(mcu.get("part") or "mcu")
        g.add_node(mcu_id, kind="mcu", **_attrs(mcu, exclude=("part",)))

        for ngoai_vi in hardware.peripherals:
            pid = str(ngoai_vi.get("id", "")).strip()
            if not pid:
                raise GraphError("Hồ sơ phần cứng có ngoại vi thiếu 'id'")
            g.add_node(
                pid,
                kind="peripheral",
                shareable=bool(ngoai_vi.get("shareable", False)),
                **_attrs(ngoai_vi, exclude=("configured_by",)),
            )
            g.add_edge(mcu_id, pid, kind="has")

            for reg in ngoai_vi.get("configured_by") or []:
                reg = str(reg).upper()
                g.add_node(reg, kind="register")
                g.add_edge(pid, reg, kind="configured_by")

        for chan, thuoc_tinh in hardware.pin_map.items():
            chan = str(chan)
            g.add_node(chan, kind="pin", **(thuoc_tinh if isinstance(thuoc_tinh, dict) else {}))
            if isinstance(thuoc_tinh, dict) and thuoc_tinh.get("peripheral"):
                ngoai_vi_id = str(thuoc_tinh["peripheral"])
                if g.has_node(ngoai_vi_id):
                    g.add_edge(chan, ngoai_vi_id, kind="belongs_to")

        for linh_kien in hardware.components:
            cid = str(linh_kien.get("id", "")).strip()
            if not cid:
                raise GraphError("Hồ sơ phần cứng có linh kiện thiếu 'id'")
            g.add_node(
                cid,
                kind="component",
                shareable=bool(linh_kien.get("shareable", False)),
                part=str(linh_kien.get("part", "")),
                **_attrs(linh_kien, exclude=("part", "pins")),
            )
            if linh_kien.get("bus") and g.has_node(str(linh_kien["bus"])):
                g.add_edge(cid, str(linh_kien["bus"]), kind="on_bus")
            for _vai_tro, chan in (linh_kien.get("pins") or {}).items():
                chan = str(chan)
                if not g.has_node(chan):
                    g.add_node(chan, kind="pin")
                g.add_edge(cid, chan, kind="connects_to")

        if datasheets is not None:
            kg._attach_chunks(datasheets)

        if constraints is not None:
            kg._attach_constraints(constraints)

        for module in modules:
            kg.add_module(
                str(getattr(module, "id")),
                uses=list(getattr(module, "uses", []) or []),
                depends_on=list(getattr(module, "depends_on", []) or []),
            )

        return kg

    def _attach_chunks(self, datasheets: DatasheetStore) -> None:
        """Chỉ nối chunk ACTIVE.

        Chunk chưa qua G2 không có mặt trong đồ thị, nên Graph-RAG không thể
        chọn phải nó dù có tìm cách nào đi nữa — bất biến FR-KLC-01 được thi
        hành ở tầng cấu trúc chứ không chỉ ở tầng truy vấn.
        """
        for chunk in datasheets.active():
            self.graph.add_node(
                chunk.id,
                kind="chunk",
                device=chunk.device,
                peripheral=chunk.peripheral,
                topic=chunk.topic,
                source=chunk.source,
                registers=list(chunk.registers),
            )
            for reg in chunk.registers:
                reg = str(reg).upper()
                if not self.graph.has_node(reg):
                    self.graph.add_node(reg, kind="register")
                self.graph.add_edge(reg, chunk.id, kind="documented_in")

            for nut, thuoc_tinh in list(self.graph.nodes(data=True)):
                if (
                    thuoc_tinh.get("kind") == "component"
                    and thuoc_tinh.get("part")
                    and str(thuoc_tinh["part"]).lower() == chunk.device.lower()
                ):
                    self.graph.add_edge(nut, chunk.id, kind="documented_in")

    def _attach_constraints(self, constraints: Any) -> None:
        for ten, gia_tri in (getattr(constraints, "limits", {}) or {}).items():
            nut = f"limit:{ten}"
            self.graph.add_node(nut, kind="constraint", name=ten, value=gia_tri)
        for cam in getattr(constraints, "forbidden", ()) or ():
            self.graph.add_node(f"forbid:{cam}", kind="constraint", name=str(cam))

    def add_module(
        self, module_id: str, uses: Sequence[str] = (), depends_on: Sequence[str] = ()
    ) -> None:
        """Thêm một module và các cạnh ``uses`` / ``depends_on`` của nó."""
        self.graph.add_node(module_id, kind="module")
        for tai_nguyen in uses:
            tai_nguyen = str(tai_nguyen)
            if not self.graph.has_node(tai_nguyen):
                # Giữ nút để bộ kiểm xung đột báo được "tài nguyên không có
                # trong hồ sơ", thay vì âm thầm bỏ qua khai báo sai chính tả.
                self.graph.add_node(tai_nguyen, kind="unknown")
            self.graph.add_edge(module_id, tai_nguyen, kind="uses")
        for phu_thuoc in depends_on:
            phu_thuoc = str(phu_thuoc)
            if not self.graph.has_node(phu_thuoc):
                self.graph.add_node(phu_thuoc, kind="module")
            self.graph.add_edge(module_id, phu_thuoc, kind="depends_on")

    # ----------------------------------------------------------------------
    # Truy vấn cơ bản
    # ----------------------------------------------------------------------

    def nodes_of_kind(self, kind: str) -> list[str]:
        return sorted(n for n, d in self.graph.nodes(data=True) if d.get("kind") == kind)

    def kind_of(self, node: str) -> str:
        if not self.graph.has_node(node):
            raise GraphError(f"Không có nút {node!r} trong đồ thị")
        return str(self.graph.nodes[node].get("kind", "unknown"))

    def _edges_from(self, node: str, kind: str) -> list[str]:
        if not self.graph.has_node(node):
            return []
        return [v for _, v, d in self.graph.out_edges(node, data=True) if d.get("kind") == kind]

    def _edges_to(self, node: str, kind: str) -> list[str]:
        if not self.graph.has_node(node):
            return []
        return [u for u, _, d in self.graph.in_edges(node, data=True) if d.get("kind") == kind]

    def resources_of(self, module_id: str) -> list[str]:
        return sorted(self._edges_from(module_id, "uses"))

    def modules_using(self, resource: str) -> list[str]:
        return sorted(self._edges_to(resource, "uses"))

    def registers_for(self, module_id: str) -> list[str]:
        """Thanh ghi mà module này sẽ phải cấu hình.

        Chuỗi ``module –uses→ ngoại vi –configured_by→ thanh ghi``. Đây cũng là
        đầu vào lập Bảng kiểm thông tin cần (RIC) ở AIS §6.2.
        """
        ket_qua: set[str] = set()
        for tai_nguyen in self._edges_from(module_id, "uses"):
            ket_qua.update(self._edges_from(tai_nguyen, "configured_by"))
            # Linh kiện gắn trên bus kéo theo thanh ghi của chính bus đó.
            for bus in self._edges_from(tai_nguyen, "on_bus"):
                ket_qua.update(self._edges_from(bus, "configured_by"))
        return sorted(ket_qua)

    def pins_for(self, module_id: str) -> list[str]:
        ket_qua: set[str] = set()
        for tai_nguyen in self._edges_from(module_id, "uses"):
            ket_qua.update(
                chan
                for chan in self._edges_from(tai_nguyen, "connects_to")
                if self.graph.nodes[chan].get("kind") == "pin"
            )
        return sorted(ket_qua)

    # ----------------------------------------------------------------------
    # Ứng dụng 1 — kiểm xung đột tài nguyên (§5.2, FR-KG-02, TC-18)
    # ----------------------------------------------------------------------

    def _is_shareable(self, resource: str) -> bool:
        return bool(self.graph.nodes.get(resource, {}).get("shareable", False))

    def conflicts(self) -> list[Conflict]:
        """Mọi xung đột hiện có trong đồ thị, sắp xếp tất định."""
        phat_hien: list[Conflict] = []

        for tai_nguyen, thuoc_tinh in self.graph.nodes(data=True):
            loai = thuoc_tinh.get("kind")

            if loai == "unknown":
                for module in self.modules_using(tai_nguyen):
                    phat_hien.append(
                        Conflict(
                            kind="unknown_resource",
                            resource=tai_nguyen,
                            modules=(module,),
                            message=(
                                f"Module {module!r} khai báo dùng {tai_nguyen!r} nhưng "
                                "hồ sơ phần cứng không có tài nguyên nào tên như vậy. "
                                "Sai chính tả trong khai báo, hoặc hồ sơ phần cứng "
                                "chưa cập nhật."
                            ),
                        )
                    )
                continue

            if loai not in ("peripheral", "component"):
                continue

            dung_chung = self.modules_using(tai_nguyen)
            if len(dung_chung) > 1 and not self._is_shareable(tai_nguyen):
                phat_hien.append(
                    Conflict(
                        kind="resource_shared",
                        resource=tai_nguyen,
                        modules=tuple(dung_chung),
                        message=(
                            f"Tranh chấp tài nguyên: {', '.join(dung_chung)} cùng khai "
                            f"báo dùng {tai_nguyen!r}, vốn là tài nguyên độc chiếm. "
                            "Kỹ sư phân xử: đổi một module sang tài nguyên khác, hoặc "
                            f"khai báo 'shareable: true' cho {tai_nguyen!r} nếu nó thật "
                            "sự dùng chung được."
                        ),
                        evidence=tuple(f"{m} –uses→ {tai_nguyen}" for m in dung_chung),
                    )
                )

        phat_hien.extend(self._pin_conflicts())
        return sorted(phat_hien, key=lambda c: (c.kind, c.resource, c.modules))

    def _pin_conflicts(self) -> list[Conflict]:
        """Hai module điều khiển cùng một chân qua hai linh kiện khác nhau.

        Loại xung đột này không lộ ra ở tầng khai báo ``uses`` — nó chỉ hiện
        khi đi thêm một bước trong đồ thị. Đúng thứ mà đọc từng tệp mã không
        thấy được.
        """
        theo_chan: dict[str, dict[str, set[str]]] = {}
        for module in self.nodes_of_kind("module"):
            for tai_nguyen in self._edges_from(module, "uses"):
                for chan in self._edges_from(tai_nguyen, "connects_to"):
                    if self.graph.nodes[chan].get("kind") != "pin":
                        continue
                    theo_chan.setdefault(chan, {}).setdefault(module, set()).add(tai_nguyen)

        ket_qua: list[Conflict] = []
        for chan, theo_module in theo_chan.items():
            if len(theo_module) < 2:
                continue
            qua = {m: sorted(r) for m, r in theo_module.items()}
            ket_qua.append(
                Conflict(
                    kind="pin_shared",
                    resource=chan,
                    modules=tuple(sorted(theo_module)),
                    message=(
                        f"Tranh chấp chân {chan}: "
                        + "; ".join(f"{m} qua {', '.join(r)}" for m, r in sorted(qua.items()))
                        + ". Hai module cùng điều khiển một chân là lỗi phần cứng, "
                        "không phải lỗi mã — kỹ sư phân xử."
                    ),
                    evidence=tuple(
                        f"{m} –uses→ {r} –connects_to→ {chan}"
                        for m, rs in sorted(qua.items())
                        for r in rs
                    ),
                )
            )
        return ket_qua

    def check_module(
        self, module_id: str, uses: Sequence[str], depends_on: Sequence[str] = ()
    ) -> list[Conflict]:
        """Kiểm một module TRƯỚC khi nó vào backlog — quy trình P2, TC-18.

        Không làm thay đổi đồ thị gọi tới: chạy trên bản sao, để một lần kiểm
        thất bại không để lại nửa vời trạng thái.
        """
        ban_sao = KnowledgeGraph(graph=self.graph.copy(), version=self.version)
        if ban_sao.graph.has_node(module_id):
            ban_sao.graph.remove_node(module_id)
        ban_sao.add_module(module_id, uses=uses, depends_on=depends_on)
        return [c for c in ban_sao.conflicts() if module_id in c.modules]

    # ----------------------------------------------------------------------
    # Ứng dụng 2 — Graph-RAG (§5.3, FR-KG-03, TC-05)
    # ----------------------------------------------------------------------

    def chunks_for(self, module_id: str, top_k: int = DEFAULT_TOP_K) -> list[str]:
        """Chọn chunk cho một module theo quan hệ, không theo độ giống từ ngữ.

        Xếp hạng: (1) số thanh ghi của module mà chunk phủ được — chunk nói về
        đúng nhiều thứ module phải cấu hình thì hữu ích hơn; (2) chunk gắn trực
        tiếp với một linh kiện module dùng; (3) mã chunk, để kết quả TẤT ĐỊNH.

        Tính tất định của bước (3) không phải chi tiết làm đẹp: cùng một đầu vào
        phải cho cùng một prompt, nếu không thực nghiệm A/B của Chương 3 không
        tái lập được.
        """
        thanh_ghi = set(self.registers_for(module_id))
        tai_nguyen = set(self._edges_from(module_id, "uses"))

        diem: dict[str, tuple[int, int]] = {}
        for reg in thanh_ghi:
            for chunk_id in self._edges_from(reg, "documented_in"):
                phu, truc_tiep = diem.get(chunk_id, (0, 0))
                diem[chunk_id] = (phu + 1, truc_tiep)

        for res in tai_nguyen:
            for chunk_id in self._edges_from(res, "documented_in"):
                phu, truc_tiep = diem.get(chunk_id, (0, 0))
                diem[chunk_id] = (phu, truc_tiep + 1)

        xep_hang = sorted(
            diem.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0])
        )
        return [chunk_id for chunk_id, _ in xep_hang[:top_k]]

    def select_chunks(
        self, module_id: str, datasheets: DatasheetStore, top_k: int = DEFAULT_TOP_K
    ) -> list[Chunk]:
        """Như :meth:`chunks_for` nhưng trả về chunk đầy đủ để ghép prompt."""
        return [datasheets.get(cid) for cid in self.chunks_for(module_id, top_k=top_k)]

    # ----------------------------------------------------------------------
    # Ứng dụng 3 — phân tích ảnh hưởng và checklist review (§5.4, §8.3)
    # ----------------------------------------------------------------------

    def modules_documented_by(self, chunk_id: str) -> list[str]:
        """Module nào dựa trên một chunk — nền của tập lỗi thời (AIS §8.3).

        Đây mới là nửa "đồ thị" của truy vấn ngược; nửa còn lại là quét trích
        dẫn ``// ref:`` trong mã, thuộc tầng vòng đời tri thức (Sprint 3).
        """
        if not self.graph.has_node(chunk_id):
            return []
        ket_qua: set[str] = set()
        for nguon in self._edges_to(chunk_id, "documented_in"):
            loai = self.graph.nodes[nguon].get("kind")
            if loai == "register":
                for ngoai_vi in self._edges_to(nguon, "configured_by"):
                    ket_qua.update(self.modules_using(ngoai_vi))
                    for linh_kien in self._edges_to(ngoai_vi, "on_bus"):
                        ket_qua.update(self.modules_using(linh_kien))
            elif loai == "component":
                ket_qua.update(self.modules_using(nguon))
        return sorted(ket_qua)

    def impact_of(self, resource: str) -> dict[str, list[str]]:
        """Đổi một tài nguyên thì phải xem lại những gì (§5.4)."""
        if not self.graph.has_node(resource):
            raise GraphError(f"Không có tài nguyên {resource!r} trong đồ thị")

        thanh_ghi = self._edges_from(resource, "configured_by")
        chunks: set[str] = set()
        for reg in thanh_ghi:
            chunks.update(self._edges_from(reg, "documented_in"))
        chunks.update(self._edges_from(resource, "documented_in"))

        return {
            "modules": self.modules_using(resource),
            "registers": sorted(thanh_ghi),
            "chunks": sorted(chunks),
            "pins": sorted(
                chan
                for chan in self._edges_to(resource, "belongs_to")
                if self.graph.nodes[chan].get("kind") == "pin"
            ),
        }

    def facts_for(self, module_id: str) -> list[str]:
        """Vài dòng sự kiện thay cho cả hồ sơ phần cứng — kỹ thuật nén K6.

        Cố tình ngắn: mục đích của K6 là thay thế việc gửi cả hardware_profile,
        nên đầu ra ở đây phải đọc như một bản ghi chú, không như một tài liệu.
        """
        dong: list[str] = []
        tai_nguyen = self.resources_of(module_id)
        if tai_nguyen:
            dong.append(f"Module dùng: {', '.join(tai_nguyen)}.")

        thanh_ghi = self.registers_for(module_id)
        if thanh_ghi:
            dong.append(f"Thanh ghi phải cấu hình: {', '.join(thanh_ghi)}.")

        chan = self.pins_for(module_id)
        if chan:
            dong.append(f"Chân liên quan: {', '.join(chan)}.")

        for res in tai_nguyen:
            thuoc_tinh = self.graph.nodes.get(res, {})
            chi_tiet = [
                f"{k}={v}"
                for k, v in sorted(thuoc_tinh.items())
                if k not in ("kind", "shareable") and isinstance(v, (str, int, float, bool))
            ]
            if chi_tiet:
                dong.append(f"{res}: {', '.join(chi_tiet)}.")

        for xung_dot in self.conflicts():
            if module_id in xung_dot.modules:
                dong.append(f"CẢNH BÁO XUNG ĐỘT: {xung_dot.message}")

        return dong

    def review_checklist(self, module_id: str) -> list[str]:
        """Checklist review cho Gate G3, sinh từ đồ thị (§5.4).

        Biến review của kỹ sư từ đọc tự do thành đối chiếu có hệ thống: mỗi
        dòng là một câu hỏi có thể trả lời có/không bằng cách nhìn vào diff.
        """
        muc: list[str] = []
        for res in self.resources_of(module_id):
            muc.append(f"Module chạm {res} — kiểm cấu hình khớp hồ sơ phần cứng.")
        for reg in self.registers_for(module_id):
            chunks = self._edges_from(reg, "documented_in")
            if chunks:
                muc.append(
                    f"Mã cấu hình {reg} phải trích dẫn {' hoặc '.join(sorted(chunks))} "
                    "và khớp từng bit với chunk đó."
                )
            else:
                muc.append(
                    f"Mã cấu hình {reg} nhưng KHÔNG có chunk nào tài liệu hóa thanh "
                    "ghi này — nạp tài liệu qua G2 trước khi duyệt."
                )
        for chan in self.pins_for(module_id):
            muc.append(f"Chân {chan}: xác nhận hướng và mức logic khớp sơ đồ nối dây.")

        cua_module = {
            r
            for m in self.nodes_of_kind("module")
            if m != module_id
            for r in self.resources_of(m)
        }
        va_cham = sorted(set(self.resources_of(module_id)) & cua_module)
        for res in va_cham:
            khac = [m for m in self.modules_using(res) if m != module_id]
            muc.append(
                f"{res} cũng được {', '.join(khac)} dùng — xác nhận không giẫm chân nhau."
            )
        return muc

    # ----------------------------------------------------------------------
    # Lưu trữ — graph.yaml (ADR-08)
    # ----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "nodes": [
                {"id": n, **{k: v for k, v in d.items()}}
                for n, d in sorted(self.graph.nodes(data=True))
            ],
            "edges": [
                {"from": u, "to": v, **{k: w for k, w in d.items()}}
                for u, v, d in sorted(self.graph.edges(data=True))
            ],
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        path = Path(path)
        if not path.is_file():
            raise GraphError(f"Không tìm thấy graph.yaml: {path}")
        try:
            du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise GraphError(f"{path}: YAML không hợp lệ — {exc}") from exc

        kg = cls(version=int(du_lieu.get("version", 1)))
        for nut in du_lieu.get("nodes") or []:
            thuoc_tinh = dict(nut)
            kg.graph.add_node(thuoc_tinh.pop("id"), **thuoc_tinh)
        for canh in du_lieu.get("edges") or []:
            thuoc_tinh = dict(canh)
            kg.graph.add_edge(thuoc_tinh.pop("from"), thuoc_tinh.pop("to"), **thuoc_tinh)
        return kg

    def __len__(self) -> int:
        return self.graph.number_of_nodes()
