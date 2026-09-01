"""Interface PlatformPack — ranh giới giữa engine tổng quát và một họ MCU.

EAA-SRS-01 FR-PLT-02, EAA-SDD-03 §2 (``platform.py`` — interface
compile/size/flash/rules/sim), EAA-SAD-02 ADR-09, NFR-05.

Đây là module quyết định sản phẩm có thật sự tổng quát hay không. Luật của nó
gói trong một câu: **engine không bao giờ gọi thẳng một công cụ nào của một họ
vi điều khiển; nó chỉ gọi các năng lực được khai báo trong ``pack.yaml``.**

Hệ quả thực hành khi lập trình: "code cho một nền tảng, nhưng KHÔNG code vào
nền tảng đó" (MDD §6). Thêm một họ MCU mới = thêm một thư mục ``packs/<tên>/``
gồm dữ liệu và quy tắc, KHÔNG sửa một dòng engine. Nếu có lúc nào bạn thấy
mình muốn viết ``if pack.name == ...`` trong ``eaa/``, đó là dấu hiệu interface
này thiếu một năng lực — hãy thêm năng lực vào interface, đừng thêm nhánh rẽ.

Sprint 0 chốt LƯỢC ĐỒ và phần nạp/kiểm tra manifest. Bộ chạy lệnh thật (đọc
cú pháp gọi từ Tool Card theo AIS §9.5, FR-ENV-05) thuộc Sprint 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from eaa.tools.base import CodeArtifact, ToolReport

__all__ = [
    "CAPABILITIES",
    "REQUIRED_CAPABILITIES",
    "ASSEMBLY_CAPABILITIES",
    "CONFIRM_REQUIRED_CAPABILITIES",
    "ParseSpec",
    "ToolInvocation",
    "StaticRule",
    "FirmwareTemplates",
    "DiagnosticTemplates",
    "InterfaceTemplates",
    "PackManifest",
    "PlatformPack",
    "PackError",
    "load_manifest",
    "discover_packs",
]

#: Năng lực một Platform Pack có thể khai báo.
#:
#: * ``compile`` — dịch MỘT tệp nguồn thành tệp đối tượng. Không liên kết.
#: * ``link``    — gộp các tệp đối tượng thành ảnh chạy được.
#: * ``hex``     — đổi ảnh liên kết sang định dạng công cụ nạp đọc được.
#: * ``size``    — đo chiếm dụng bộ nhớ chương trình và bộ nhớ dữ liệu.
#: * ``static``  — phân tích tĩnh theo bộ quy tắc của nền tảng.
#: * ``flash``   — nạp ảnh nhị phân xuống thiết bị.
#: * ``flash_verify`` — đọc ngược bộ nhớ chương trình và so với ảnh vừa gửi.
#: * ``sim``     — cầu nối sang bộ mô phỏng để chạy cổng SIL.
#:
#: ``flash_verify`` tách khỏi ``flash`` có chủ ý. Không phải mạch nạp nào cũng
#: đọc ngược được, và một pack thiếu năng lực này phải nói ra là *không kiểm
#: được* chứ không được để câu "nạp không báo lỗi" âm thầm đóng vai câu "nạp
#: đúng" (N-075). Gộp hai năng lực làm một thì sự khác nhau ấy biến mất.
#:
#: ``compile`` và ``link`` tách rời có chủ ý. Vòng lặp chuẩn kiểm từng module,
#: mà một module driver không có ``main()``; pack nào để lệnh dịch liên kết
#: luôn thì mọi module đều trượt vì *undefined reference to main* — trượt vì
#: một lý do chẳng liên quan gì tới chất lượng mã. Xem eaa/tools/compile.py.
CAPABILITIES: tuple[str, ...] = (
    "compile",
    "link",
    "hex",
    "size",
    "static",
    "flash",
    "flash_verify",
    "sim",
)

#: Không có ba năng lực này thì chuỗi kiểm chứng bắt buộc (FR-VER-01) đứt
#: đoạn, nên pack không dùng được. Các năng lực còn lại là tùy chọn: một pack
#: có thể chưa hỗ trợ nạp, hoặc dự án chưa có mô hình mô phỏng.
REQUIRED_CAPABILITIES: tuple[str, ...] = ("compile", "size", "static")

#: Năng lực cần để ráp firmware hoàn chỉnh từ các module đã merge. Không bắt
#: buộc để chạy vòng kiểm module, nhưng thiếu chúng thì không có tệp nào đem
#: đi nạp được — nên ``eaa doctor`` nêu tên chúng thay vì để người tự đoán.
ASSEMBLY_CAPABILITIES: tuple[str, ...] = ("link", "hex")

#: Năng lực chạm vào thiết bị thật hoặc vào máy của kỹ sư — LUÔN phải khai báo
#: cần người xác nhận (FR-DIA-02, AIS §7.3). Engine từ chối nạp một pack lách
#: điều này, nên không thể có pack nào "tiện tay" bỏ qua xác nhận.
CONFIRM_REQUIRED_CAPABILITIES: frozenset[str] = frozenset({"flash"})


class PackError(Exception):
    """Manifest của Platform Pack sai lược đồ hoặc thiếu năng lực bắt buộc."""


@dataclass(frozen=True)
class ParseSpec:
    """Cách đọc kết quả một công cụ: mã thoát, biểu thức bắt lỗi và số liệu.

    Quy tắc parse là DỮ LIỆU của pack, không phải hằng số trong adapter — đúng
    tinh thần Tool Card ở AIS §9.5: đổi phiên bản công cụ chỉ là cập nhật khai
    báo, adapter không phải sửa.
    """

    success_exit_codes: tuple[int, ...] = (0,)
    error_regex: str | None = None
    warning_regex: str | None = None
    #: tên số liệu → regex có đúng một nhóm bắt số. Ví dụ khóa: ``flash_bytes``.
    metric_regex: dict[str, str] = field(default_factory=dict)
    #: Dấu hiệu BẮT BUỘC phải có trong đầu ra thì mới tính là ĐẠT.
    #:
    #: Mã thoát 0 không phải bằng chứng công cụ đã làm việc — nó chỉ nói công
    #: cụ không thấy lý do để phàn nàn. Một công cụ có quyền coi "không có gì
    #: để làm" là thành công; người gọi thì không, vì với một cổng kiểm chứng
    #: thì "không kiểm gì" và "kiểm và thấy khớp" là hai kết cục trái ngược.
    #:
    #: Đo được ở SL-120: lệnh nạp firmware đọc 0 byte từ tệp, ghi 0 byte, thoát
    #: 0 — và cả hai phiên làm việc đều tin rằng firmware đã nằm trên chip.
    require_regex: str | None = None

    def __post_init__(self) -> None:
        for ten, mau in [("error_regex", self.error_regex),
                         ("warning_regex", self.warning_regex),
                         ("require_regex", self.require_regex)]:
            if mau is not None:
                _compile_regex(mau, f"{ten}")
        for ten_so_lieu, mau in self.metric_regex.items():
            bien_dich = _compile_regex(mau, f"metric_regex[{ten_so_lieu}]")
            if bien_dich.groups != 1:
                raise PackError(
                    f"metric_regex[{ten_so_lieu}] phải có đúng 1 nhóm bắt giá trị, "
                    f"đang có {bien_dich.groups}"
                )


def _compile_regex(mau: str, nhan: str) -> re.Pattern[str]:
    try:
        return re.compile(mau)
    except re.error as exc:
        raise PackError(f"{nhan} không phải biểu thức chính quy hợp lệ: {exc}") from exc


@dataclass(frozen=True)
class ToolInvocation:
    """Một lời gọi công cụ do pack khai báo.

    ``command`` là mẫu argv; engine thay các chỗ giữ ``{tên}`` bằng tham số
    được truyền vào lúc chạy. Cố ý dùng danh sách argv chứ không dùng chuỗi
    shell: không có shell thì không có chèn lệnh, và mẫu vẫn chạy giống nhau
    trên Windows lẫn Linux (NFR-04, STP-04 §6).
    """

    command: tuple[str, ...]
    parse: ParseSpec = field(default_factory=ParseSpec)
    requires_confirmation: bool = False
    timeout_s: float = 120.0
    description: str = ""

    def __post_init__(self) -> None:
        if not self.command:
            raise PackError("command rỗng — phải có ít nhất tên chương trình")
        if self.timeout_s <= 0:
            raise PackError(f"timeout_s phải dương, nhận {self.timeout_s}")

    def placeholders(self) -> set[str]:
        """Các chỗ giữ ``{tên}`` xuất hiện trong mẫu argv."""
        return {
            m.group(1)
            for phan in self.command
            for m in re.finditer(r"\{(\w+)\}", phan)
        }

    def resolve(self, params: dict[str, Any]) -> list[str]:
        """Dựng argv thật từ mẫu; thiếu tham số là lỗi, không im lặng bỏ qua.

        Một phần tử argv đúng bằng một chỗ giữ (``"{sources}"``) và nhận giá
        trị là danh sách thì được TRẢI RA thành nhiều phần tử. Không có luật
        này, một danh sách tệp sẽ bị nối bằng dấu cách thành MỘT tham số duy
        nhất — trình biên dịch nhận được một tên tệp chứa dấu cách và báo
        "không tìm thấy", một lỗi trông như lỗi môi trường mà thực ra là lỗi
        lắp lệnh.
        """
        thieu = self.placeholders() - set(params)
        if thieu:
            raise PackError(
                f"Thiếu tham số cho lời gọi công cụ: {sorted(thieu)} "
                f"(mẫu: {' '.join(self.command)})"
            )

        argv: list[str] = []
        for phan in self.command:
            khop = re.fullmatch(r"\{(\w+)\}", phan)
            if khop:
                gia_tri = params[khop.group(1)]
                if isinstance(gia_tri, (list, tuple, set)):
                    argv.extend(str(x) for x in gia_tri)
                    continue
                argv.append(str(gia_tri))
                continue
            argv.append(phan.format(**params))
        return argv


@dataclass(frozen=True)
class StaticRule:
    """Một quy tắc phân tích tĩnh do pack cung cấp.

    Quy tắc cấm (``delay()``, cấp phát động, đệ quy, số thực trong ngắt…) đến
    TỪ ĐÂU là điều đáng chú ý: phần phụ thuộc nền tảng nằm trong pack, phần
    phụ thuộc dự án đến từ ``constraints.yaml`` — engine chỉ hợp nhất và thi
    hành, không tự biết cái gì bị cấm ở đâu (FR-VER-02).
    """

    id: str
    pattern: str
    message: str
    severity: str = "error"
    #: Trích dẫn nguồn của quy tắc (trang tài liệu, chuẩn mã hóa…).
    ref: str = ""

    def __post_init__(self) -> None:
        _compile_regex(self.pattern, f"quy tắc {self.id}")


@dataclass(frozen=True)
class FirmwareTemplates:
    """Khuôn để ráp các module đã merge thành một chương trình chạy được.

    Engine biết *module nào, gọi hàm nào, mỗi bao nhiêu mili giây* — đó là dữ
    liệu của dự án. Nó KHÔNG biết viết một vòng lặp chính bằng C cho một họ vi
    điều khiển: nguồn xung nhịp, cú pháp ngắt, cách bật bộ định thời đều là
    chuyện của nền tảng.

    Nên phần chữ nằm hết ở pack, còn engine chỉ thay chỗ giữ. Ba dòng mẫu
    (``include_line``, ``init_line``, ``task_line``) tồn tại đúng vì lý do ấy:
    không có chúng thì engine phải tự sinh câu lệnh C, và cái ranh giới mà
    TC-38 canh sẽ mờ dần từ chỗ đó.
    """

    #: Tệp khuôn của vòng lặp chính, tương đối so với gốc pack.
    template: Path
    #: Mẫu một dòng nạp tiêu đề module. Chỗ giữ: ``{module}``.
    include_line: str = '#include "{module}.h"'
    #: Mẫu một dòng gọi hàm khởi tạo. Chỗ giữ: ``{init}``, ``{module}``.
    init_line: str = "    {init}();"
    #: Mẫu một dòng khai một việc định kỳ. Chỗ giữ: ``{step}``, ``{period_ms}``.
    #:
    #: Chỗ giữ được thay bằng ``str.replace``, KHÔNG bằng ``str.format``: khuôn
    #: là mã C và mã C đầy dấu ngoặc nhọn, nên ``format`` sẽ vấp ngay dòng đầu
    #: tiên có một khối lệnh.
    task_line: str = "    { {step}, {period_ms} },"
    #: Tên tệp nguồn sinh ra, đặt trong thư mục build.
    output: str = "main.c"
    #: Đuôi ảnh NẠP ĐƯỢC mà năng lực 'hex' sinh ra.
    #:
    #: Pack đầu tiên dùng Intel HEX nên đuôi này từng là hằng số trong engine.
    #: Pack thứ hai nạp bằng ảnh nhị phân thô — và đó là dấu hiệu interface
    #: thiếu một tham số, không phải dấu hiệu cần thêm một nhánh rẽ.
    image_suffix: str = ".hex"
    #: Tệp nguồn do PACK cung cấp, dịch và liên kết cùng firmware. Đường dẫn
    #: tương đối so với gốc pack.
    #:
    #: Có nền tảng không cần mục này (bộ dịch đã kèm sẵn mã khởi động và bảng
    #: vector); có nền tảng thì cần. Khai ở pack vì đó đúng là thứ thuộc về
    #: nền tảng.
    sources: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, du_lieu: Any, root: Path, path: Path) -> "FirmwareTemplates":
        if not isinstance(du_lieu, dict):
            raise PackError(f"{path}: 'firmware' phải là ánh xạ khóa–giá trị")
        khuon = du_lieu.get("template")
        if not khuon:
            raise PackError(
                f"{path}: 'firmware' phải nêu 'template' — tệp khuôn vòng lặp chính"
            )
        mac_dinh = cls(template=root / str(khuon))
        return cls(
            template=root / str(khuon),
            include_line=str(du_lieu.get("include_line", mac_dinh.include_line)),
            init_line=str(du_lieu.get("init_line", mac_dinh.init_line)),
            task_line=str(du_lieu.get("task_line", mac_dinh.task_line)),
            output=str(du_lieu.get("output", mac_dinh.output)),
            image_suffix=str(du_lieu.get("image_suffix", mac_dinh.image_suffix)),
            sources=tuple(str(root / x) for x in (du_lieu.get("sources") or [])),
        )


@dataclass(frozen=True)
class DiagnosticTemplates:
    """Bộ khung firmware chẩn đoán do nền tảng cấp.

    Chia việc y như khuôn firmware sản phẩm, nhưng chia làm ba chứ không hai:

    * **Pack** giữ bộ khung — bật UART, đóng gói khung telemetry, gọi phần đo.
    * **Dự án** giữ phần đo của từng kịch bản (``firmware_template`` trong
      ``diagnostics.yaml``): quét bus nào, đọc thanh ghi nào, tính chỉ số gì.
    * **Engine** ghép hai tệp lại bằng cách LIÊN KẾT chúng, không dán chuỗi.

    Điểm cuối là chỗ đáng chú ý: cả khung lẫn phần đo đều là mã C thật, nên bộ
    dịch kiểm được cả hai và không ai phải chắp mã C bằng Python.
    """

    template: Path
    #: Tên tệp sinh ra; ``{scenario}`` được thay bằng mã kịch bản.
    output: str = "diag_{scenario}.c"
    #: Tên ảnh; cũng nhận ``{scenario}``.
    image_name: str = "diag_{scenario}"
    #: Đuôi ảnh nạp được — xem :class:`FirmwareTemplates`.
    image_suffix: str = ".hex"
    #: Tệp nguồn do pack cung cấp, liên kết cùng firmware đo.
    sources: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, du_lieu: Any, root: Path, path: Path) -> "DiagnosticTemplates":
        if not isinstance(du_lieu, dict):
            raise PackError(f"{path}: 'diagnostics' phải là ánh xạ khóa–giá trị")
        khuon = du_lieu.get("template")
        if not khuon:
            raise PackError(
                f"{path}: 'diagnostics' phải nêu 'template' — bộ khung firmware đo"
            )
        return cls(
            template=root / str(khuon),
            output=str(du_lieu.get("output", "diag_{scenario}.c")),
            image_name=str(du_lieu.get("image_name", "diag_{scenario}")),
            image_suffix=str(du_lieu.get("image_suffix", ".hex")),
            sources=tuple(str(root / x) for x in (du_lieu.get("sources") or [])),
        )


@dataclass(frozen=True)
class InterfaceTemplates:
    """Khuôn sinh tệp tiêu đề của một module — N-041.

    Cùng ranh giới với :class:`FirmwareTemplates`: engine biết module hứa cung
    cấp những hàm nào và mỗi hàm có hợp đồng gọi ra sao; nó KHÔNG biết viết một
    tệp tiêu đề C. Macro chống nạp trùng, cú pháp chú thích, cách khai báo —
    đều là chuyện của nền tảng.
    """

    template: Path
    #: Tên tệp sinh ra; ``{module}`` được thay bằng mã module.
    output: str = "{module}.h"
    #: Mẫu một dòng khai báo hàm. Chỗ giữ: ``{signature}``.
    function_line: str = "{signature};"
    #: Mẫu một dòng chú thích. Chỗ giữ: ``{comment}``.
    comment_line: str = "/* {comment} */"
    #: Mẫu một dòng nạp tệp tiêu đề khác. Chỗ giữ: ``{header}``.
    include_line: str = "#include <{header}>"

    @classmethod
    def from_dict(cls, du_lieu: Any, root: Path, path: Path) -> "InterfaceTemplates":
        if not isinstance(du_lieu, dict):
            raise PackError(f"{path}: 'interfaces' phải là ánh xạ khóa–giá trị")
        khuon = du_lieu.get("template")
        if not khuon:
            raise PackError(
                f"{path}: 'interfaces' phải nêu 'template' — tệp khuôn tiêu đề module"
            )
        mac_dinh = cls(template=root / str(khuon))
        return cls(
            template=root / str(khuon),
            output=str(du_lieu.get("output", mac_dinh.output)),
            function_line=str(du_lieu.get("function_line", mac_dinh.function_line)),
            comment_line=str(du_lieu.get("comment_line", mac_dinh.comment_line)),
            include_line=str(du_lieu.get("include_line", mac_dinh.include_line)),
        )


@dataclass(frozen=True)
class PackManifest:
    """Nội dung ``pack.yaml`` đã được kiểm tra lược đồ."""

    name: str
    version: str
    description: str
    #: Các đích/họ chip pack phục vụ — chuỗi mờ đối với engine.
    targets: tuple[str, ...]
    capabilities: dict[str, ToolInvocation]
    root: Path
    rules_dir: Path
    prompts_dir: Path
    smoke_dir: Path
    #: Phiên bản tối thiểu của từng công cụ, đối chiếu với env_lock (FR-ENV-04).
    tool_requirements: dict[str, str] = field(default_factory=dict)
    #: Trình gỡ lỗi sâu của họ MCU này (N-085). Engine chỉ nhận danh sách và
    #: kiểm sự có mặt; nó không được biết tên nào trong đây (FR-PLT-01).
    debug_tools: tuple[str, ...] = ()
    #: Khuôn ráp firmware — xem :class:`FirmwareTemplates`.
    firmware: "FirmwareTemplates | None" = None
    #: Bộ khung firmware chẩn đoán — xem :class:`DiagnosticTemplates`.
    diagnostics: "DiagnosticTemplates | None" = None
    #: Khuôn sinh tệp tiêu đề module — xem :class:`InterfaceTemplates`.
    interfaces: "InterfaceTemplates | None" = None

    def has(self, capability: str) -> bool:
        return capability in self.capabilities

    def invocation(self, capability: str) -> ToolInvocation:
        try:
            return self.capabilities[capability]
        except KeyError:
            raise PackError(
                f"Pack {self.name!r} không khai báo năng lực {capability!r} "
                f"(đang có: {sorted(self.capabilities)})"
            ) from None


def load_manifest(path: str | Path) -> PackManifest:
    """Nạp và kiểm tra một ``pack.yaml``.

    Kiểm tra chặt ngay lúc nạp thay vì để lỗi lộ ra giữa một vòng sinh mã: một
    pack khai báo sai chỉ làm hỏng phiên làm việc nếu nó được phát hiện muộn.
    """
    path = Path(path)
    if path.is_dir():
        path = path / "pack.yaml"
    if not path.is_file():
        raise PackError(f"Không tìm thấy manifest Platform Pack: {path}")

    try:
        du_lieu = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PackError(f"{path}: YAML không hợp lệ — {exc}") from exc

    if not isinstance(du_lieu, dict):
        raise PackError(f"{path}: nội dung phải là một ánh xạ khóa–giá trị")

    for truong in ("pack", "version"):
        if not du_lieu.get(truong):
            raise PackError(f"{path}: thiếu trường bắt buộc {truong!r}")

    root = path.parent
    kha_nang_raw = du_lieu.get("capabilities") or {}
    if not isinstance(kha_nang_raw, dict):
        raise PackError(f"{path}: 'capabilities' phải là ánh xạ")

    la = set(kha_nang_raw) - set(CAPABILITIES)
    if la:
        raise PackError(
            f"{path}: năng lực không nhận biết {sorted(la)} "
            f"(hợp lệ: {list(CAPABILITIES)}). Muốn thêm năng lực mới thì mở "
            "rộng interface eaa/platform.py, đừng khai báo lén trong pack."
        )

    kha_nang = {ten: _parse_invocation(ten, than, path) for ten, than in kha_nang_raw.items()}

    thieu = [c for c in REQUIRED_CAPABILITIES if c not in kha_nang]
    if thieu:
        raise PackError(
            f"{path}: thiếu năng lực bắt buộc {thieu} — không có chúng thì "
            "chuỗi kiểm chứng FR-VER-01 bị đứt đoạn."
        )

    for ten in CONFIRM_REQUIRED_CAPABILITIES & set(kha_nang):
        if not kha_nang[ten].requires_confirmation:
            raise PackError(
                f"{path}: năng lực {ten!r} phải khai báo "
                "requires_confirmation: true — thao tác chạm vào thiết bị thật "
                "luôn cần người xác nhận (FR-DIA-02)."
            )

    return PackManifest(
        name=str(du_lieu["pack"]),
        version=str(du_lieu["version"]),
        description=str(du_lieu.get("description", "")),
        targets=tuple(str(t) for t in du_lieu.get("targets", [])),
        capabilities=kha_nang,
        root=root,
        rules_dir=root / str(du_lieu.get("rules_dir", "rules")),
        prompts_dir=root / str(du_lieu.get("prompts_dir", "prompts")),
        smoke_dir=root / str(du_lieu.get("smoke_dir", "smoke")),
        firmware=(
            FirmwareTemplates.from_dict(du_lieu["firmware"], root, path)
            if du_lieu.get("firmware")
            else None
        ),
        diagnostics=(
            DiagnosticTemplates.from_dict(du_lieu["diagnostics"], root, path)
            if du_lieu.get("diagnostics")
            else None
        ),
        interfaces=(
            InterfaceTemplates.from_dict(du_lieu["interfaces"], root, path)
            if du_lieu.get("interfaces")
            else None
        ),
        tool_requirements={
            str(k): str(v) for k, v in (du_lieu.get("tool_requirements") or {}).items()
        },
        debug_tools=tuple(str(x) for x in (du_lieu.get("debug_tools") or ())),
    )


def _parse_invocation(ten: str, than: Any, path: Path) -> ToolInvocation:
    if not isinstance(than, dict):
        raise PackError(f"{path}: năng lực {ten!r} phải là ánh xạ, nhận {type(than)}")

    lenh = than.get("command")
    if isinstance(lenh, str):
        raise PackError(
            f"{path}: năng lực {ten!r} khai báo command dạng chuỗi. Phải dùng "
            "danh sách argv — engine không chạy qua shell (chống chèn lệnh và "
            "để mẫu chạy giống nhau trên Windows/Linux)."
        )
    if not isinstance(lenh, list) or not lenh:
        raise PackError(f"{path}: năng lực {ten!r} thiếu 'command' dạng danh sách")

    parse_raw = than.get("parse") or {}
    if not isinstance(parse_raw, dict):
        raise PackError(f"{path}: năng lực {ten!r} có 'parse' sai kiểu")

    try:
        parse = ParseSpec(
            success_exit_codes=tuple(parse_raw.get("success_exit_codes", (0,))),
            require_regex=parse_raw.get("require_regex"),
            error_regex=parse_raw.get("error_regex"),
            warning_regex=parse_raw.get("warning_regex"),
            metric_regex=dict(parse_raw.get("metric_regex") or {}),
        )
        return ToolInvocation(
            command=tuple(str(p) for p in lenh),
            parse=parse,
            requires_confirmation=bool(than.get("requires_confirmation", False)),
            timeout_s=float(than.get("timeout_s", 120.0)),
            description=str(than.get("description", "")),
        )
    except PackError as exc:
        raise PackError(f"{path}: năng lực {ten!r} — {exc}") from exc


def discover_packs(root: str | Path) -> dict[str, PackManifest]:
    """Nạp mọi pack trong thư mục ``packs/``."""
    root = Path(root)
    ket_qua: dict[str, PackManifest] = {}
    if not root.is_dir():
        return ket_qua
    for manifest_path in sorted(root.glob("*/pack.yaml")):
        manifest = load_manifest(manifest_path)
        ket_qua[manifest.name] = manifest
    return ket_qua


@runtime_checkable
class PlatformPack(Protocol):
    """Hợp đồng runtime mà engine trông cậy vào.

    Mọi phương thức trả ``ToolReport`` để Orchestrator kiểm tra bất biến merge
    theo cùng một cách với mọi nền tảng.
    """

    manifest: PackManifest

    def compile(self, artifact: CodeArtifact, work_dir: Path) -> ToolReport:
        """Dịch mã nguồn; ``metrics`` nên kèm đường dẫn ảnh nhị phân sinh ra."""
        ...

    def size(self, binary: Path) -> ToolReport:
        """Đo chiếm dụng bộ nhớ.

        ``metrics`` phải mang các khóa mà ``constraints.yaml`` đặt ngưỡng — tên
        khóa là hợp đồng giữa pack và ràng buộc dự án, engine chỉ so sánh số.
        """
        ...

    def static_rules(self) -> list[StaticRule]:
        """Bộ quy tắc phân tích tĩnh của nền tảng."""
        ...

    def flash(self, binary: Path, *, confirmed_by: str) -> ToolReport:
        """Nạp firmware. ``confirmed_by`` là bằng chứng người đã xác nhận.

        Tham số này bắt buộc chứ không phải cờ tùy chọn: một adapter không thể
        vô tình nạp firmware mà quên hỏi người (FR-DIA-02).
        """
        ...

    def sim_bindings(self) -> dict[str, Any]:
        """Cấu hình nối firmware vào bộ mô phỏng cho cổng SIL (FR-SIM-01)."""
        ...

    def smoke_test(self) -> ToolReport:
        """Tự kiểm tra pack chạy được trên máy này (AIS §9.5)."""
        ...
