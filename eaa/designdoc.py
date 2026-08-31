"""Dựng tài liệu thiết kế từ hồ sơ dự án — URD, SRS, SDD, chức năng, luồng.

EAA-AIS-05 §8.5 (kho phẩm xuất); FR-DOC-01. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-105.

Điều module này làm, và điều nó cố ý KHÔNG làm
------------------------------------------------

Nó **không hỏi mô hình** một chữ nào. Toàn bộ nội dung rút từ hồ sơ dự án đã
có: ``constraints.yaml``, ``hardware_profile.yaml``, backlog trong Project
State, hợp đồng gọi của module. Đó là một lựa chọn, và lý do đáng nói:

Một tài liệu thiết kế do mô hình viết ra **đọc rất hay** và không truy được về
đâu cả. Nó sẽ điền đầy mọi mục — kể cả những mục mà dự án chưa có dữ liệu — và
người đọc không có cách nào phân biệt mục nào là sự thật của dự án với mục nào
là văn mẫu. Với một tài liệu thiết kế thì đó là hỏng hoàn toàn, vì công dụng
duy nhất của nó là **được tin**.

Nên ở đây: mục nào có dữ liệu thì dựng từ dữ liệu, mục nào chưa có thì nói
thẳng là chưa có, và nói luôn phải chạy lệnh gì để có. Một mục trống trong SRS
đọc như "mục này không cần", trong khi thật ra là "chưa ai điền" — hai câu
khác hẳn nhau.

Khuôn mẫu là DỮ LIỆU
---------------------

Cấu trúc từng tài liệu nằm trong ``eaa/docspec/*.yaml``, không nằm trong mã.
Cấu trúc một tài liệu thiết kế là thứ mỗi đơn vị mỗi khác; nhúng cứng nó vào
mã là đúng cho đúng một nơi. Mã ở đây chỉ cấp **dữ liệu** cho từng mục —
những hàm ``_nguon_*`` — và một khuôn mẫu chỉ nêu tên chúng.

Ranh giới engine
-----------------

Module này nằm trong ``eaa/`` nên không được biết một tên phần cứng cụ thể nào
(TC-38). Nó đọc lược đồ chung — ``mcu``, ``peripherals``, ``pin_functions`` —
và mọi tên riêng đều tới từ hồ sơ dự án lúc chạy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml

from eaa.docmodel import Doc, Heading, Note, PageBreak, Para

__all__ = [
    "DesignDocError",
    "DocSpec",
    "DuLieuDuAn",
    "load_spec",
    "list_specs",
    "build",
    "SPEC_DIR",
]

SPEC_DIR = Path(__file__).resolve().parent / "docspec"


class DesignDocError(Exception):
    """Không dựng được tài liệu."""


# ══════════════════════════ khuôn mẫu ══════════════════════════


@dataclass(frozen=True)
class SpecSection:
    title: str
    level: int = 1
    dan: str = ""
    nguon: str = ""


@dataclass(frozen=True)
class DocSpec:
    kind: str
    title: str
    short: str = ""
    standard: str = ""
    purpose: str = ""
    mac_dinh_dinh_dang: str = "docx"
    sections: tuple[SpecSection, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DocSpec":
        muc = tuple(
            SpecSection(
                title=str(s.get("title", "")).strip(),
                level=int(s.get("level", 1)),
                dan=" ".join(str(s.get("dan", "")).split()),
                nguon=str(s.get("nguon", "")).strip(),
            )
            for s in d.get("sections", []) or []
        )
        if not muc:
            raise DesignDocError("khuôn mẫu không có mục nào")
        return cls(
            kind=str(d.get("kind", "")).strip(),
            title=str(d.get("title", "")).strip(),
            short=str(d.get("short", "")).strip(),
            standard=" ".join(str(d.get("standard", "")).split()),
            purpose=" ".join(str(d.get("purpose", "")).split()),
            mac_dinh_dinh_dang=str(d.get("mac_dinh_dinh_dang", "docx")).strip(),
            sections=muc,
        )


def list_specs(thu_muc: Path | None = None) -> list[DocSpec]:
    """Mọi khuôn mẫu đọc được, sắp theo mã loại."""
    goc = thu_muc or SPEC_DIR
    ds = []
    for p in sorted(goc.glob("*.yaml")):
        try:
            ds.append(load_spec(p.stem, goc))
        except DesignDocError:
            continue
    return ds


def load_spec(kind: str, thu_muc: Path | None = None) -> DocSpec:
    goc = thu_muc or SPEC_DIR
    p = goc / f"{kind}.yaml"
    if not p.is_file():
        co = ", ".join(sorted(q.stem for q in goc.glob("*.yaml"))) or "(không có)"
        raise DesignDocError(f"Chưa có khuôn mẫu {kind!r}. Đang có: {co}")
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DesignDocError(f"{p}: YAML không hợp lệ — {exc}") from None
    if not isinstance(d, dict):
        raise DesignDocError(f"{p}: khuôn mẫu phải là một ánh xạ")
    try:
        return DocSpec.from_dict(d)
    except DesignDocError as exc:
        raise DesignDocError(f"{p}: {exc}") from None


# ══════════════════════════ dữ liệu dự án ══════════════════════════


@dataclass
class DuLieuDuAn:
    """Mọi thứ bộ cấp dữ liệu được phép đọc. Chỉ đọc, không gọi mô hình."""

    project: Path
    rang_buoc: dict[str, Any] = field(default_factory=dict)
    phan_cung: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    #: Đường dẫn tệp đã đọc — đi vào phần "nguồn" của tài liệu để truy vết.
    nguon_tep: list[str] = field(default_factory=list)
    #: Mục nào thiếu dữ liệu; gom lại để in một lần ở cuối.
    thieu: list[str] = field(default_factory=list)

    @property
    def ten(self) -> str:
        return self.project.name

    @property
    def backlog(self) -> list[Any]:
        return list(getattr(self.state, "backlog", []) or [])

    @property
    def gates(self) -> dict[str, str]:
        return dict(getattr(self.state, "gates", {}) or {})

    def bao_thieu(self, muc: str, cach_co: str) -> Note:
        from eaa.confidence import KHONG_KIEM_DUOC

        self.thieu.append(muc)
        return Note(
            f"Chưa có dữ liệu cho mục này trong hồ sơ dự án. {cach_co}",
            KHONG_KIEM_DUOC,
        )


def _doc_yaml(p: Path) -> dict[str, Any]:
    if not p.is_file():
        return {}
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DesignDocError(f"{p}: YAML không hợp lệ — {exc}") from None
    return d if isinstance(d, dict) else {}


def thu_thap(project: Path) -> DuLieuDuAn:
    """Đọc hồ sơ dự án. Thiếu tệp nào thì bỏ qua tệp ấy, không hỏng cả lượt."""
    from eaa.cli import CONSTRAINTS_FILE, HARDWARE_PROFILE_FILE, STATE_FILE
    from eaa.state import StateStore

    du = DuLieuDuAn(project=project)
    for ten in (CONSTRAINTS_FILE, HARDWARE_PROFILE_FILE):
        p = project / ten
        if p.is_file():
            du.nguon_tep.append(ten)
    du.rang_buoc = _doc_yaml(project / CONSTRAINTS_FILE)
    du.phan_cung = _doc_yaml(project / HARDWARE_PROFILE_FILE)

    kho = StateStore(project / STATE_FILE)
    if kho.exists():
        du.state = kho.load()
        du.nguon_tep.append(STATE_FILE)
    return du


# ══════════════════════════ bộ cấp dữ liệu ══════════════════════════
#
# Mỗi hàm nhận DuLieuDuAn và trả về dãy khối. Tên hàm bỏ tiền tố ``_nguon_``
# chính là tên nêu trong khuôn mẫu YAML.

Nguon = Callable[[DuLieuDuAn], list[Any]]


def _chu(x: Any) -> str:
    """Đổi một giá trị YAML thành một dòng chữ.

    Gộp mọi khoảng trắng về một dấu cách. Giá trị nhiều dòng của YAML —
    những khối ``>-`` dài trong hồ sơ dự án — nếu giữ nguyên xuống dòng sẽ
    làm vỡ ô bảng ở cả bốn định dạng xuất, và vỡ ô bảng là loại hỏng chỉ
    thấy sau khi mở tệp, tức là sau khi đã gửi đi.
    """
    if isinstance(x, bool):
        return "có" if x else "không"
    if isinstance(x, (list, tuple)):
        return ", ".join(_chu(i) for i in x)
    if isinstance(x, dict):
        return "; ".join(f"{k}: {_chu(v)}" for k, v in x.items())
    return " ".join(str(x).split())


def _bang_phang(d: dict[str, Any], tien_to: str = "") -> list[tuple[str, str]]:
    """Trải một ánh xạ lồng nhau thành các cặp (khóa đầy đủ, giá trị)."""
    ra: list[tuple[str, str]] = []
    for k, v in (d or {}).items():
        khoa = f"{tien_to}{k}"
        if isinstance(v, dict) and v:
            ra += _bang_phang(v, f"{khoa}.")
        else:
            ra.append((khoa, _chu(v)))
    return ra


def _nguon_tong_quan(du: DuLieuDuAn) -> list[Any]:
    from eaa.confidence import DA_KIEM

    ra: list[Any] = []
    mo_ta = str(du.phan_cung.get("description", "")).strip()
    if mo_ta:
        ra.append(Para(mo_ta))
    else:
        ra.append(du.bao_thieu(
            "mô tả dự án",
            "Thêm khóa 'description' vào hardware_profile.yaml, hoặc chạy "
            "'eaa brief' để Agent dựng hồ sơ."))

    mcu = du.phan_cung.get("mcu") or {}
    hang: list[tuple[str, str]] = [("Dự án", du.ten)]
    for k in ("platform", "mcu", "clock_hz"):
        if du.rang_buoc.get(k) is not None:
            hang.append((k, _chu(du.rang_buoc[k])))
    if isinstance(mcu, dict):
        for k, v in mcu.items():
            if not isinstance(v, (dict, list)):
                hang.append((f"mcu.{k}", _chu(v)))
    if du.state is not None:
        hang.append(("pha hiện tại", _chu(getattr(du.state, "phase", ""))))
        hang.append(("số module trong backlog", str(len(du.backlog))))
    ra.append(_tao_bang(["Thuộc tính", "Giá trị"], hang, "Thông số chính"))

    if du.nguon_tep:
        ra.append(Note(
            "Số liệu trên rút từ: " + ", ".join(du.nguon_tep) + ".", DA_KIEM))
    return ra


def _nguon_cac_ben(du: DuLieuDuAn) -> list[Any]:
    """Các bên liên quan. Suy từ mô hình phân quyền, không bịa vai trò."""
    from eaa.confidence import SUY_RA

    hang = [
        ("Kỹ sư phụ trách", "Chốt ràng buộc, duyệt tại 5 cổng, cầm thiết bị đo",
         "Người duy nhất mở được cổng"),
        ("Agent (hệ này)", "Sinh mã, chạy cổng kiểm chứng, dựng tài liệu",
         "Không tự duyệt, không tự nạp firmware, không tự cài công cụ"),
        ("Người vận hành thiết bị", "Dùng sản phẩm sau khi bàn giao",
         "Đọc tài liệu vận hành, không sửa mã"),
    ]
    return [
        _tao_bang(["Bên", "Việc", "Ranh giới"], hang),
        Note("Bảng này suy từ mô hình phân quyền của sản phẩm (5 Human Gate), "
             "không phải từ hồ sơ dự án. Sửa lại nếu dự án có vai trò khác.",
             SUY_RA),
    ]


def _nguon_c1_boi_canh(du: DuLieuDuAn) -> list[Any]:
    """C1 — hệ thống và những thứ bên ngoài nó."""
    ra: list[Any] = [Para(
        "Mức C1 trả lời: hệ thống này là gì, ai dùng, và nó nối với những gì "
        "bên ngoài. Bên ngoài ở đây nghĩa là ngoài ảnh firmware.")]

    linh_kien = du.phan_cung.get("components") or []
    if linh_kien:
        hang = []
        for c in linh_kien:
            if not isinstance(c, dict):
                continue
            # Linh kiện nối bằng bus (bus:) hoặc bằng chân rời (pins:) — hai
            # cách khai khác nhau cho cùng một câu hỏi "nối vào đâu". Chỉ đọc
            # một khóa thì bảng đầy dấu gạch, và một bảng đầy dấu gạch đọc như
            # "chưa khảo sát" chứ không như "khai theo cách khác".
            noi = _chu(c.get("bus", "") or c.get("interface", ""))
            if not noi and isinstance(c.get("pins"), dict):
                noi = _chu(c["pins"])
            cung_cap = _chu(c.get("provides", []) or c.get("role", ""))
            if not c.get("populated", True):
                cung_cap = (cung_cap + " · CHƯA LẮP TRÊN BO").strip(" ·")
            hang.append((
                _chu(c.get("id", "")),
                _chu(c.get("part", "")),
                noi or "—",
                cung_cap or "—",
            ))
        ra.append(_tao_bang(
            ["Mã", "Linh kiện", "Nối vào đâu", "Cung cấp / ghi chú"], hang,
            "Thực thể ngoài mà firmware phải nói chuyện cùng"))
    else:
        ra.append(du.bao_thieu(
            "danh sách linh kiện ngoài",
            "Khai chúng ở khóa 'components' trong hardware_profile.yaml, hoặc "
            "chạy 'eaa survey <kho.zip> --extract' rồi 'eaa brief'."))

    dien = du.phan_cung.get("power") or {}
    if dien:
        ra.append(_tao_bang(["Thuộc tính", "Giá trị"], _bang_phang(dien),
                            "Nguồn điện"))
    return ra


def _nguon_c2_container(du: DuLieuDuAn) -> list[Any]:
    """C2 — những khối chạy được. Với hệ nhúng thì đây là chỗ dễ hiểu sai nhất."""
    from eaa.confidence import SUY_RA

    nen = _chu(du.rang_buoc.get("platform", "")) or "(chưa khai)"
    hang = [
        ("Ảnh firmware", f"Chạy trên vi điều khiển, dựng bởi Platform Pack "
                         f"'{nen}'", "Nạp qua công cụ nạp; không có hệ điều hành"),
        ("Bộ công cụ dựng", "Chạy trên máy chủ: biên dịch, phân tích tĩnh, "
                            "chạy test", "Gọi qua interface eaa/platform.py"),
        ("Hồ sơ dự án", "Kho dữ liệu trên đĩa: ràng buộc, hồ sơ phần cứng, "
                        "tri thức đã duyệt, Project State",
         "Append-only với kho tri thức; ghi nguyên tử với Project State"),
        ("Thiết bị đo", "Ngoài máy tính: cổng nối tiếp, máy hiện sóng",
         "Chỉ người thao tác"),
    ]
    ra: list[Any] = [
        _tao_bang(["Container", "Chạy ở đâu / là gì", "Nối bằng"], hang),
        Note("Với một hệ nhúng bare-metal, 'container' không phải tiến trình "
             "hay dịch vụ. Bốn khối trên là bốn thứ có vòng đời riêng và ranh "
             "giới rõ — đó là điều mức C2 cần nói.", SUY_RA),
    ]
    ns = du.rang_buoc.get("budget") or {}
    if isinstance(ns.get("capacity"), dict):
        ra.append(_tao_bang(["Tài nguyên", "Dung lượng"],
                            _bang_phang(ns["capacity"]),
                            "Sức chứa của container firmware"))
    return ra


def _nguon_c3_thanh_phan(du: DuLieuDuAn) -> list[Any]:
    """C3 — module bên trong firmware, lấy từ backlog."""
    ds = du.backlog
    if not ds:
        return [du.bao_thieu(
            "danh sách module",
            "Backlog đang rỗng. Thêm bằng 'eaa plan add <mã module>', hoặc để "
            "Agent đề xuất phân rã bằng 'eaa propose split'.")]

    hang = []
    for m in ds:
        hang.append((
            _chu(getattr(m, "id", "")),
            _chu(getattr(m, "status", "")),
            _chu(getattr(m, "uses", []) or "—"),
            _chu(getattr(m, "depends_on", []) or "—"),
        ))
    ra: list[Any] = [_tao_bang(
        ["Module", "Trạng thái", "Chiếm tài nguyên", "Phụ thuộc"], hang,
        "Thành phần bên trong firmware")]

    thu_tu = _thu_tu_dung(ds)
    if thu_tu:
        ra.append(Para("Thứ tự dựng suy từ quan hệ phụ thuộc:"))
        ra.append(_tao_bullets([f"{i}. {' → '.join(lop)}"
                                for i, lop in enumerate(thu_tu, 1)]))
    return ra


def _thu_tu_dung(ds: Sequence[Any]) -> list[list[str]]:
    """Xếp module thành các lớp: lớp sau chỉ phụ thuộc lớp trước."""
    con_lai = {getattr(m, "id", ""): set(getattr(m, "depends_on", []) or [])
               for m in ds if getattr(m, "id", "")}
    lop: list[list[str]] = []
    while con_lai:
        san_sang = sorted(k for k, v in con_lai.items() if not (v & con_lai.keys()))
        if not san_sang:  # vòng phụ thuộc — nói ra chứ không lặp vô hạn
            lop.append(sorted(con_lai) + ["(có vòng phụ thuộc)"])
            break
        lop.append(san_sang)
        for k in san_sang:
            con_lai.pop(k)
    return lop


def _nguon_c4_ma(du: DuLieuDuAn) -> list[Any]:
    """C4 — hợp đồng gọi của từng module, nếu đã sinh."""
    from eaa.confidence import DA_KIEM

    ra: list[Any] = []
    thu_muc = du.project / "interfaces"
    tep = sorted(thu_muc.glob("*.yaml")) if thu_muc.is_dir() else []
    if not tep:
        return [du.bao_thieu(
            "hợp đồng gọi của module",
            "Sinh bằng 'eaa interface <mã module>' — lệnh ấy chốt hợp đồng "
            "TRƯỚC khi sinh thân hàm.")]

    for p in tep:
        d = _doc_yaml(p)
        ra.append(Heading(f"{p.stem}", 2))
        ham = d.get("functions") or d.get("api") or []
        if isinstance(ham, list) and ham:
            hang = [(_chu(f.get("name", "")), _chu(f.get("returns", "")),
                     _chu(f.get("params", []) or "—"), _chu(f.get("note", "") or "—"))
                    for f in ham if isinstance(f, dict)]
            ra.append(_tao_bang(["Hàm", "Trả về", "Tham số", "Ghi chú"], hang))
        else:
            ra.append(_tao_bang(["Khóa", "Giá trị"], _bang_phang(d)))
    ra.append(Note(f"Rút từ {len(tep)} tệp trong interfaces/.", DA_KIEM))
    return ra


def _nguon_yeu_cau_chuc_nang(du: DuLieuDuAn) -> list[Any]:
    ds = du.backlog
    if not ds:
        return [du.bao_thieu(
            "yêu cầu chức năng",
            "Yêu cầu chức năng dựng từ backlog. Thêm module bằng "
            "'eaa plan add <mã module>'.")]
    hang = []
    for m in ds:
        mid = _chu(getattr(m, "id", ""))
        dung = getattr(m, "uses", []) or []
        phu = getattr(m, "depends_on", []) or []
        phat_bieu = f"Hệ thống phải cung cấp chức năng của module {mid}"
        if dung:
            phat_bieu += f", dùng tài nguyên phần cứng: {_chu(dung)}"
        if phu:
            phat_bieu += f", trên nền các module: {_chu(phu)}"
        hang.append((f"FR-{mid}", phat_bieu, _chu(getattr(m, "status", ""))))
    return [
        _tao_bang(["Mã", "Phát biểu", "Trạng thái"], hang, "Yêu cầu chức năng"),
        Note("Mã yêu cầu dùng chính mã module để truy vết được hai chiều: từ "
             "yêu cầu ra mã nguồn, và từ một commit ngược về yêu cầu."),
    ]


def _nguon_giao_dien(du: DuLieuDuAn) -> list[Any]:
    ra = _nguon_bang_chan(du)
    ngoai_vi = du.phan_cung.get("peripherals") or []
    if ngoai_vi:
        hang = []
        for p in ngoai_vi:
            if not isinstance(p, dict):
                continue
            hang.append((_chu(p.get("id", "")), _chu(p.get("kind", "")),
                         _chu(p.get("configured_by", []) or "—"),
                         _chu(p.get("note", "") or "—")))
        ra.append(_tao_bang(["Mã", "Loại", "Cấu hình qua", "Ghi chú"], hang,
                            "Ngoại vi trên chip"))
    return ra


def _nguon_bang_chan(du: DuLieuDuAn) -> list[Any]:
    chan = du.phan_cung.get("pin_functions") or {}
    ra: list[Any] = []
    if chan:
        hang = [(k, _chu(v)) for k, v in chan.items()]
        ra.append(_tao_bang(["Chân", "Chức năng khả dụng"], hang, "Bảng chân"))
    else:
        ra.append(du.bao_thieu(
            "bảng chân",
            "Khai ở khóa 'pin_functions' trong hardware_profile.yaml."))
    ra += _nguon_xung_dot(du)
    return ra


def _nguon_xung_dot(du: DuLieuDuAn) -> list[Any]:
    from eaa.confidence import DA_KIEM

    xd = du.phan_cung.get("conflicts") or []
    chua = [c for c in xd if isinstance(c, dict)
            and str(c.get("status", "")).strip() != "đã phân xử"]
    if not chua:
        return []
    hang = [(_chu(c.get("pin", "") or c.get("resource", "")),
             _chu(c.get("claimed_by", [])),
             _chu(c.get("found_in", "") or "—"),
             _chu(c.get("status", "chưa phân xử"))) for c in chua]
    return [
        _tao_bang(["Tài nguyên", "Bị hai bên đòi", "Thấy ở", "Trạng thái"], hang,
                  "XUNG ĐỘT CHƯA PHÂN XỬ"),
        Note(f"{len(chua)} xung đột chưa phân xử. Một xung đột chân không phân "
             "xử trước khi sinh mã sẽ thành một lỗi phần cứng, không phải một "
             "lỗi biên dịch — nó chỉ hiện ra khi cắm điện.", DA_KIEM),
    ]


def _nguon_yeu_cau_phi_chuc_nang(du: DuLieuDuAn) -> list[Any]:
    gh = du.rang_buoc.get("limits") or {}
    if not gh:
        return [du.bao_thieu(
            "yêu cầu phi chức năng",
            "Khai ở khóa 'limits' trong constraints.yaml. Ràng buộc cứng chốt "
            "tại cổng G1.")]
    hang = [(f"NFR-{i}", k, v) for i, (k, v) in enumerate(_bang_phang(gh), 1)]
    return [
        _tao_bang(["Mã", "Chỉ tiêu", "Giá trị"], hang,
                  "Yêu cầu phi chức năng"),
        Note("Mỗi dòng là một số kiểm được. Một yêu cầu phi chức năng không "
             "kèm số là một mong muốn."),
    ]


def _nguon_rang_buoc_cung(du: DuLieuDuAn) -> list[Any]:
    ra: list[Any] = []
    cam = du.rang_buoc.get("forbidden") or []
    if cam:
        ra.append(Para("Không được dùng trong mã sinh ra:"))
        ra.append(_tao_bullets([_chu(x) for x in cam]))
    kieu = du.rang_buoc.get("style") or {}
    if kieu:
        ra.append(_tao_bang(["Quy ước", "Bắt buộc"], _bang_phang(kieu),
                            "Quy ước bắt buộc"))
    if not ra:
        ra.append(du.bao_thieu(
            "ràng buộc cứng",
            "Khai ở khóa 'forbidden' và 'style' trong constraints.yaml."))
    return ra


def _nguon_tieu_chi_nghiem_thu(du: DuLieuDuAn) -> list[Any]:
    nt = du.rang_buoc.get("acceptance") or {}
    if not nt:
        return [du.bao_thieu(
            "tiêu chí nghiệm thu",
            "Khai ở khóa 'acceptance' trong constraints.yaml. Nghiệm thu trên "
            "thiết bị thật diễn ra tại cổng G4.")]
    ra: list[Any] = []
    do = nt.get("measurements") or []
    if isinstance(do, list) and do:
        hang = [(_chu(m.get("name", "")), _chu(m.get("key", "")),
                 _chu(m.get("unit", "")),
                 _chu(m.get("max", m.get("min", "—"))),
                 _chu(m.get("note", "") or "—"))
                for m in do if isinstance(m, dict)]
        ra.append(_tao_bang(["Phép đo", "Khóa", "Đơn vị", "Ngưỡng", "Ghi chú"],
                            hang, "Số phải đo được"))
    kb = nt.get("scenarios") or []
    if kb:
        ra.append(Para("Kịch bản nghiệm thu:"))
        ra.append(_tao_bullets([_chu(x) for x in kb], numbered=True))
    con = {k: v for k, v in nt.items() if k not in ("measurements", "scenarios")}
    if con:
        ra.append(_tao_bang(["Chỉ tiêu", "Giá trị"], _bang_phang(con)))
    return ra


def _nguon_an_toan(du: DuLieuDuAn) -> list[Any]:
    p = du.project / "safety.yaml"
    d = _doc_yaml(p)
    if not d:
        return [du.bao_thieu(
            "phân tích an toàn",
            "Dựng bằng 'eaa safety show'; kết quả lưu ở safety.yaml.")]
    ra: list[Any] = []
    hong = d.get("failures") or d.get("hazards") or []
    if isinstance(hong, list) and hong:
        hang = [(_chu(h.get("id", "")), _chu(h.get("cause", h.get("mode", ""))),
                 _chu(h.get("effect", "") or "—"),
                 _chu(h.get("mitigation", h.get("safe_state", "")) or "—"))
                for h in hong if isinstance(h, dict)]
        ra.append(_tao_bang(["Mã", "Hỏng thế nào", "Hậu quả", "Chế độ an toàn"],
                            hang, "Phân tích hỏng hóc"))
    else:
        ra.append(_tao_bang(["Khóa", "Giá trị"], _bang_phang(d)))
    return ra


def _nguon_ngan_sach(du: DuLieuDuAn) -> list[Any]:
    ns = du.rang_buoc.get("budget") or {}
    if not ns:
        return [du.bao_thieu(
            "ngân sách tài nguyên",
            "Khai ở khóa 'budget' trong constraints.yaml; xem hiện trạng bằng "
            "'eaa budget show'.")]
    return [
        _tao_bang(["Khoản", "Giá trị"], _bang_phang(ns), "Ngân sách"),
        Note("Bảng này là ngân sách ĐÃ KHAI, không phải mức tiêu thật. Số tiêu "
             "thật đo được sau khi biên dịch: 'eaa budget show'."),
    ]


def _nguon_quyet_dinh(du: DuLieuDuAn) -> list[Any]:
    p = du.project / "decisions.yaml"
    d = _doc_yaml(p)
    ds = d.get("decisions") if isinstance(d, dict) else None
    if not ds:
        return [du.bao_thieu(
            "quyết định thiết kế",
            "Dựng phương án bằng 'eaa decide <câu hỏi>'; người chọn tại cổng.")]
    hang = [(_chu(x.get("id", "")), _chu(x.get("question", "")),
             _chu(x.get("chosen", "") or "chưa chọn"),
             _chu(x.get("rationale", "") or "—"))
            for x in ds if isinstance(x, dict)]
    return [_tao_bang(["Mã", "Câu hỏi", "Đã chọn", "Vì sao"], hang,
                      "Quyết định thiết kế")]


def _nguon_gia_dinh_rui_ro(du: DuLieuDuAn) -> list[Any]:
    from eaa.confidence import GIA_DINH

    ra: list[Any] = []
    xd = [c for c in (du.phan_cung.get("conflicts") or [])
          if isinstance(c, dict) and str(c.get("status", "")) != "đã phân xử"]
    gd: list[str] = []
    if xd:
        gd.append(f"{len(xd)} xung đột tài nguyên phần cứng chưa phân xử — "
                  "xem mục bảng chân. Mọi thiết kế dưới đây giả định chúng sẽ "
                  "được phân xử trước khi sinh mã.")
    if du.state is not None and du.gates.get("G1") != "approved":
        gd.append("Cổng G1 chưa duyệt — bộ ràng buộc trong tài liệu này còn có "
                  "thể đổi.")
    if not du.backlog:
        gd.append("Backlog rỗng — phần phân rã module chưa có gì để mô tả.")
    if gd:
        ra.append(_tao_bullets(gd))
        ra.append(Note("Những điểm trên rút từ trạng thái hiện tại của hồ sơ "
                       "dự án, không phải từ một phân tích rủi ro đầy đủ.",
                       GIA_DINH))
    else:
        ra.append(Para("Không phát hiện giả định chưa chốt nào trong hồ sơ "
                       "dự án ở thời điểm dựng tài liệu."))
    return ra


def _nguon_nhu_cau_nguoi_dung(du: DuLieuDuAn) -> list[Any]:
    """Nhu cầu người dùng — phát biểu lại từ tiêu chí nghiệm thu."""
    from eaa.confidence import SUY_RA

    nt = du.rang_buoc.get("acceptance") or {}
    kb = nt.get("scenarios") or []
    do = nt.get("measurements") or []
    if not (kb or do):
        return [du.bao_thieu(
            "nhu cầu người dùng",
            "Nhu cầu suy từ tiêu chí nghiệm thu ('acceptance' trong "
            "constraints.yaml). Chốt chúng tại cổng G1.")]

    hang = []
    for i, k in enumerate(kb, 1):
        hang.append((f"UN-{i:02d}", f"Người dùng cần hệ thống hoạt động đúng "
                                    f"trong kịch bản: {_chu(k)}"))
    for j, m in enumerate(do, len(kb) + 1):
        if not isinstance(m, dict):
            continue
        nguong = _chu(m.get("max", m.get("min", "")))
        hang.append((f"UN-{j:02d}",
                     f"Người dùng cần {_chu(m.get('name', m.get('key', '')))} "
                     f"nằm trong ngưỡng {nguong} {_chu(m.get('unit', ''))}".strip()))
    return [
        _tao_bang(["Mã", "Nhu cầu"], hang, "Nhu cầu người dùng"),
        Note("Phát biểu lại từ tiêu chí nghiệm thu đã khai. Tiêu chí là thứ "
             "đo được; nhu cầu là lý do người ta muốn số ấy.", SUY_RA),
    ]


def _nguon_luong_module(du: DuLieuDuAn) -> list[Any]:
    buoc = [
        "Module vào backlog (todo) — người thêm, hoặc Agent đề xuất phân rã.",
        "Chốt hợp đồng gọi TRƯỚC khi sinh thân hàm.",
        "Tìm tri thức còn thiếu: tra tài liệu nhà sản xuất, trích đoạn cần "
        "được duyệt tại cổng G2.",
        "Sinh mã dưới bộ ràng buộc đã chốt.",
        "Chạy toàn bộ cổng kiểm chứng: biên dịch, phân tích tĩnh, kích thước, "
        "unit test.",
        "Cổng nào đỏ thì vào vòng tự sửa dạng patch, tối đa 3 lần.",
        "Quá 3 lần thì DỪNG và bàn giao lại cho người — không thử tiếp.",
        "Mọi cổng xanh thì trình hồ sơ tại G3 để người review diff.",
        "G3 duyệt thì merge. Không có nhánh nào khác dẫn tới merge.",
        "Ráp firmware, nạp (cần người xác nhận), đo trên thiết bị thật tại G4.",
    ]
    return [
        _tao_bullets(buoc, numbered=True),
        Note("Bước 7 là bước hay bị bỏ nhất khi tự động hóa, và là bước quan "
             "trọng nhất: một vòng tự sửa không có trần sẽ tiêu ngân sách để "
             "sinh ra những bản vá ngày càng xa gốc."),
    ]


def _nguon_luong_cong(du: DuLieuDuAn) -> list[Any]:
    from eaa.policy import GATE_PURPOSE

    hang = [(g, m, "Người", f"eaa gate approve {g}")
            for g, m in GATE_PURPOSE.items()]
    return [
        _tao_bang(["Cổng", "Chặn cái gì", "Ai mở", "Lệnh"], hang,
                  "Năm cổng con người"),
        Note("Không lệnh nào vượt được các cổng này. Đó là bất biến trung tâm "
             "của sản phẩm, và nó nằm trong cấu trúc chứ không trong lời dặn."),
    ]


def _nguon_hien_trang(du: DuLieuDuAn) -> list[Any]:
    if du.state is None:
        return [du.bao_thieu("hiện trạng dự án",
                             "Chưa có Project State — chạy 'eaa init'.")]
    ra: list[Any] = [_tao_bang(
        ["Cổng", "Trạng thái"], sorted(du.gates.items()), "Hiện trạng cổng")]
    ds = du.backlog
    if ds:
        dem: dict[str, int] = {}
        for m in ds:
            s = _chu(getattr(m, "status", ""))
            dem[s] = dem.get(s, 0) + 1
        ra.append(_tao_bang(["Trạng thái module", "Số lượng"],
                            sorted(dem.items()), "Backlog"))
    return ra


def _nguon_luong_hong(du: DuLieuDuAn) -> list[Any]:
    hang = [
        ("Cổng kiểm chứng đỏ", "Vòng tự sửa dạng patch",
         "Tối đa 3 lần, rồi bàn giao người"),
        ("Quá 3 lần tự sửa", "Dừng, ghi nhật ký lỗi", "Mã thoát 3"),
        ("Thiếu công cụ trên máy", "Báo cách cài, KHÔNG tự cài",
         "Mã thoát 4; cài đặt luôn cần người"),
        ("Đang chờ người tại cổng", "Dừng và nói rõ chờ cổng nào",
         "Mã thoát 2 — đây là một TRẠNG THÁI, không phải lỗi"),
        ("Mô hình trả về nội dung không dùng được", "Ghi vào nhật ký lỗi ảo giác",
         "Không im lặng bỏ qua"),
    ]
    return [_tao_bang(["Tình huống", "Hệ làm gì", "Kết thúc thế nào"], hang)]


def _nguon_bang_chuc_nang(du: DuLieuDuAn) -> list[Any]:
    """Bảng chức năng — mỗi dòng một chức năng, để lọc và đếm."""
    ds = du.backlog
    if not ds:
        return [du.bao_thieu("bảng chức năng",
                             "Bảng dựng từ backlog. Thêm bằng 'eaa plan add'.")]
    cong = du.gates
    hang = []
    for m in ds:
        mid = _chu(getattr(m, "id", ""))
        nhom = mid.split("_")[0] if "_" in mid else "—"
        hang.append((
            f"FR-{mid}", nhom, mid,
            _chu(getattr(m, "status", "")),
            _chu(getattr(m, "uses", []) or "—"),
            _chu(getattr(m, "depends_on", []) or "—"),
            str(getattr(m, "retries", 0)),
            _chu(cong.get("G3", "")),
        ))
    return [_tao_bang(
        ["Mã", "Nhóm", "Module", "Trạng thái", "Tài nguyên", "Phụ thuộc",
         "Số lần tự sửa", "Cổng G3"],
        hang, "Danh sách chức năng")]


def _nguon_ma_tran_truy_vet(du: DuLieuDuAn) -> list[Any]:
    ds = du.backlog
    if not ds:
        return [du.bao_thieu("ma trận truy vết",
                             "Ma trận dựng từ backlog và trạng thái cổng.")]
    cong = du.gates
    hang = []
    for m in ds:
        mid = _chu(getattr(m, "id", ""))
        hang.append((f"FR-{mid}", mid, f"{mid}.c / {mid}.h",
                     _chu(getattr(m, "status", "")),
                     _chu(cong.get("G2", "—")), _chu(cong.get("G3", "—")),
                     _chu(cong.get("G4", "—"))))
    return [
        _tao_bang(["Yêu cầu", "Module", "Tệp mã", "Trạng thái",
                   "G2 tri thức", "G3 review", "G4 thiết bị"], hang,
                  "Ma trận truy vết"),
        Note("Cột G2–G4 là trạng thái cổng của cả dự án, không riêng module. "
             "Trạng thái từng module nằm ở cột Trạng thái."),
    ]


#: Bảng tra: tên trong khuôn mẫu → hàm cấp dữ liệu. Đây là chỗ DUY NHẤT nối
#: hai bên; thêm một mục vào khuôn mẫu mà quên khai ở đây thì tài liệu nói
#: thẳng là thiếu bộ cấp dữ liệu, chứ không im lặng bỏ mục.
NGUON: dict[str, Nguon] = {
    "tong_quan": _nguon_tong_quan,
    "cac_ben": _nguon_cac_ben,
    "c1_boi_canh": _nguon_c1_boi_canh,
    "c2_container": _nguon_c2_container,
    "c3_thanh_phan": _nguon_c3_thanh_phan,
    "c4_ma": _nguon_c4_ma,
    "yeu_cau_chuc_nang": _nguon_yeu_cau_chuc_nang,
    "yeu_cau_phi_chuc_nang": _nguon_yeu_cau_phi_chuc_nang,
    "giao_dien": _nguon_giao_dien,
    "bang_chan": _nguon_bang_chan,
    "rang_buoc_cung": _nguon_rang_buoc_cung,
    "tieu_chi_nghiem_thu": _nguon_tieu_chi_nghiem_thu,
    "an_toan": _nguon_an_toan,
    "ngan_sach": _nguon_ngan_sach,
    "quyet_dinh": _nguon_quyet_dinh,
    "gia_dinh_rui_ro": _nguon_gia_dinh_rui_ro,
    "nhu_cau_nguoi_dung": _nguon_nhu_cau_nguoi_dung,
    "luong_module": _nguon_luong_module,
    "luong_cong": _nguon_luong_cong,
    "hien_trang": _nguon_hien_trang,
    "luong_hong": _nguon_luong_hong,
    "bang_chuc_nang": _nguon_bang_chuc_nang,
    "ma_tran_truy_vet": _nguon_ma_tran_truy_vet,
}


# ══════════════════════════ tiện ích dựng khối ══════════════════════════


def _tao_bang(header: Sequence[str], rows: Iterable[Sequence[Any]],
              caption: str = "") -> Any:
    from eaa.docmodel import Table

    ds = tuple(tuple(_chu(c) for c in r) for r in rows)
    return Table(tuple(header), ds, caption)


def _tao_bullets(items: Iterable[str], *, numbered: bool = False) -> Any:
    from eaa.docmodel import Bullets

    return Bullets(tuple(str(i) for i in items if str(i).strip()), numbered)


# ══════════════════════════ dựng tài liệu ══════════════════════════


def build(spec: DocSpec, project: Path, *, created_at: str = "",
          author: str = "EAA") -> Doc:
    """Dựng một :class:`Doc` từ khuôn mẫu và hồ sơ dự án.

    ``created_at`` truyền vào chứ không tự lấy: dựng lại từ cùng dữ liệu phải
    ra cùng nội dung, nếu không thì không so được hai bản với nhau.
    """
    from eaa.confidence import DA_KIEM, KHONG_KIEM_DUOC

    du = thu_thap(project)
    doc = Doc(
        title=spec.title,
        subtitle=f"{spec.short} · dự án {du.ten}" if spec.short else f"Dự án {du.ten}",
        kind=spec.kind, project=du.ten, author=author, created_at=created_at,
    )

    if spec.purpose:
        doc.para(spec.purpose)
    if spec.standard:
        doc.note(f"Trình bày theo: {spec.standard}")

    for muc in spec.sections:
        doc.heading(muc.title, muc.level)
        if muc.dan:
            doc.para(muc.dan)
        if not muc.nguon:
            continue
        ham = NGUON.get(muc.nguon)
        if ham is None:
            doc.note(
                f"Khuôn mẫu nêu bộ cấp dữ liệu {muc.nguon!r} nhưng chưa có bộ "
                f"nào tên ấy. Khai nó trong eaa/designdoc.py::NGUON.",
                KHONG_KIEM_DUOC)
            continue
        doc.add(*ham(du))

    doc.add(PageBreak())
    doc.heading("Phụ lục — tài liệu này dựng từ đâu", 1)
    doc.para(
        "Toàn bộ nội dung trên rút từ hồ sơ dự án. Không mục nào do mô hình "
        "ngôn ngữ viết ra: một tài liệu thiết kế do mô hình viết đọc rất hay "
        "và không truy được về đâu cả, và người đọc không phân biệt được mục "
        "nào là sự thật của dự án với mục nào là văn mẫu.")
    doc.table(["Tệp nguồn", "Vai trò"],
              [[t, _VAI_TRO.get(t, "hồ sơ dự án")] for t in du.nguon_tep]
              or [["(không đọc được tệp nào)", "—"]],
              caption="Tệp nguồn")
    if du.thieu:
        doc.note(
            f"{len(du.thieu)} mục chưa có dữ liệu: {', '.join(du.thieu)}. "
            "Từng mục ở trên đã nói rõ chạy lệnh gì để có. Một mục trống đọc "
            "như 'không cần', trong khi thật ra là 'chưa ai điền'.",
            KHONG_KIEM_DUOC)
    else:
        doc.note("Mọi mục đều có dữ liệu từ hồ sơ dự án.", DA_KIEM)
    return doc


_VAI_TRO = {
    "constraints.yaml": "ràng buộc cứng, ngân sách, tiêu chí nghiệm thu (chốt tại G1)",
    "hardware_profile.yaml": "hồ sơ phần cứng: chân, ngoại vi, linh kiện, xung đột",
    "project_state.json": "backlog module, trạng thái cổng, pha hiện tại",
}
