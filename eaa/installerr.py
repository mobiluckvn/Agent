"""Cài hỏng thì làm gì — phân loại lỗi, rồi leo thang theo bậc.

EAA-AIS-05 §9.2, §9.4; FR-ENV-02, FR-ENV-04. Xem `docs/SAI_LECH_THIET_KE.md`
mục SL-76.

Khoảng trống module này lấp
----------------------------

``eaa doctor --fix`` biết in lệnh cài và hỏi người. Nó không biết gì về việc
lệnh ấy hỏng: mọi thất bại đều ra cùng một dòng "lệnh trả mã khác 0", và người
dùng tự đi đọc mã lỗi. Nhưng năm loại hỏng dưới đây cần năm cách xử lý khác
hẳn nhau, và đoán nhầm loại thì mọi việc sau đều đi sai hướng:

* **mạng** — thử lại là hợp lý, có khi chỉ là một lần rớt gói;
* **quyền** — thử lại vô ích, thử lại mãi cũng vô ích;
* **phụ thuộc** — phải cài thứ khác TRƯỚC, không phải cài lại thứ này;
* **build** — thiếu trình biên dịch hoặc tệp tiêu đề của hệ;
* **không tìm thấy gói** — sai tên gói, hoặc sai kho, hoặc sai hệ điều hành.

Bậc thang, và vì sao nó dừng lại
---------------------------------

:func:`remedies` trả về một thang từ rẻ tới đắt: thử lại → đổi tham số → đổi
kho/mirror → đổi công cụ tương đương → bàn giao người. Mỗi bậc nói rõ **ai
chạy**: bậc thử lại Agent tự làm được vì nó không đổi gì; bậc cài đặt thì
không, vì cài phần mềm là đổi máy của người dùng (N-022 ở mức T2).

Đó không phải một hạn chế tạm thời chờ ai đó gỡ. Một Agent tự cài được thứ nó
tự chọn là một Agent người dùng không kiểm được, và toàn bộ giá trị của sản
phẩm này nằm ở chỗ ngược lại.

Quay lui
---------

:func:`rollback_command` suy lệnh gỡ từ chính lệnh cài. Suy chứ không chép:
một trường ``uninstall`` viết tay sẽ lệch khỏi trường ``install`` ngay lần đầu
ai đó sửa một trong hai, và nó lệch theo hướng tệ nhất — gỡ nhầm gói khác.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "LoaiLoi",
    "Remedy",
    "InstallDiagnosis",
    "classify",
    "remedies",
    "rollback_command",
    "retry_delays",
    "MANG",
    "QUYEN",
    "PHU_THUOC",
    "BUILD",
    "KHONG_TIM_THAY",
    "KHAC",
    "SO_LAN_THU_LAI",
]

MANG = "mạng"
QUYEN = "quyền"
PHU_THUOC = "phụ thuộc"
BUILD = "build"
KHONG_TIM_THAY = "không tìm thấy"
KHAC = "khác"


class LoaiLoi:
    """Sáu loại, và chúng cần sáu cách xử lý khác nhau."""

    MANG = MANG
    QUYEN = QUYEN
    PHU_THUOC = PHU_THUOC
    BUILD = BUILD
    KHONG_TIM_THAY = KHONG_TIM_THAY
    KHAC = KHAC


#: Chỉ lỗi mạng mới đáng thử lại. Ba lần, giãn dần — cùng kỷ luật với vòng tự
#: sửa ≤ 3 và ``MAX_STEPS`` = 8: mọi vòng lặp trong hệ này đều có trần.
SO_LAN_THU_LAI = 3


def retry_delays(base_s: float = 2.0, n: int = SO_LAN_THU_LAI) -> list[float]:
    """Giãn cách giữa các lần thử lại, tăng gấp đôi."""
    return [base_s * (2**i) for i in range(n)]


#: Dấu hiệu nhận loại. Thứ tự QUAN TRỌNG: mẫu hẹp đứng trước mẫu rộng, vì một
#: thông báo lỗi thường chạm nhiều mẫu cùng lúc và cái khớp đầu tiên thắng.
_DAU_HIEU: tuple[tuple[str, tuple[str, ...]], ...] = (
    # BUILD hẹp phải đứng TRƯỚC "không tìm thấy". "Python.h: No such file or
    # directory" chạm cả hai, và đọc nó thành "không có gói tên Python.h" đẩy
    # người dùng đi tìm một gói không tồn tại — trong khi thứ thiếu thật là bộ
    # tệp tiêu đề của hệ. Đây đúng là kiểu phân loại sai làm mọi bước sau hỏng.
    (BUILD, (
        r"fatal error: .*\.h(?:pp)?: no such file",
        r"no such file or directory.*\.h(?:pp)?\b",
        r"\.h(?:pp)?[\"']?: no such file",
        r"failed building wheel",
        r"error: microsoft visual c\+\+.*required",
        r"\bcc1\b",
    )),
    (QUYEN, (
        r"permission denied", r"operation not permitted", r"access is denied",
        r"must be run as root", r"are you root", r"requires? (?:sudo|administrator)",
        r"eacces", r"errno 13", r"read-only file system",
    )),
    (MANG, (
        r"could not resolve host", r"temporary failure in name resolution",
        r"network is unreachable", r"connection timed out", r"connection refused",
        r"connection reset", r"failed to fetch", r"could not connect",
        r"ssl.*(?:handshake|certificate).*(?:fail|error)", r"proxy",
        r"\b(?:etimedout|econnreset|econnrefused|enetunreach)\b",
        r"http (?:429|502|503|504)", r"retrieval request timed out",
    )),
    (KHONG_TIM_THAY, (
        r"unable to locate package", r"no such package", r"no package .* available",
        r"no formul(?:a|ae) found", r"could not find a version that satisfies",
        r"no matching distribution", r"404 not found", r"e: package .* has no installation candidate",
        r"is not recognized as an internal or external command",
        r"command not found",
        # ``no such file or directory`` trần KHÔNG nằm ở đây: nó xuất hiện
        # trong lỗi build, lỗi quyền và lỗi gói như nhau, nên nó không phân
        # biệt được gì. Một dấu hiệu khớp mọi thứ là một dấu hiệu vô dụng.
    )),
    (PHU_THUOC, (
        r"unmet dependencies", r"depends on .* but", r"broken packages",
        r"conflicting (?:requirements|dependencies)", r"version conflict",
        r"incompatible", r"requires .* which is not installed",
        r"error: cannot install", r"dependency resolution failed",
        r"library not found for", r"cannot open shared object file",
    )),
    (BUILD, (
        r"\bgcc\b.*\bnot found\b", r"\bcc1\b", r"no such file.*\.h[\"']?",
        r"fatal error: .*\.h: no such file", r"error: command .*(?:gcc|clang|cc)",
        r"failed building wheel", r"error: microsoft visual c\+\+.*required",
        r"make: \*\*\*", r"linker command failed",
    )),
)

_BIEN_DICH = [(loai, [re.compile(m, re.I) for m in mau]) for loai, mau in _DAU_HIEU]


@dataclass(frozen=True)
class Remedy:
    """Một bậc trong thang gỡ."""

    step: int
    action: str
    detail: str
    #: Agent có tự làm được bậc này không. Chỉ đúng cho bậc KHÔNG đổi gì.
    agent_can_do: bool = False
    command: tuple[str, ...] = ()

    def render(self) -> str:
        ai = "Agent tự làm được" if self.agent_can_do else "CẦN BẠN chạy"
        dong = [f"  {self.step}. {self.action}   [{ai}]", f"      {self.detail}"]
        if self.command:
            dong.append(f"      $ {' '.join(self.command)}")
        return "\n".join(dong)


@dataclass(frozen=True)
class InstallDiagnosis:
    """Lệnh cài hỏng vì cái gì, và leo thang thế nào."""

    kind: str
    tool: str = ""
    signal: str = ""
    output: str = ""
    returncode: int = 0
    ladder: tuple[Remedy, ...] = ()

    @property
    def retryable(self) -> bool:
        """Chỉ lỗi mạng mới đáng thử lại. Thử lại một lỗi quyền là đốt thời gian."""
        return self.kind == MANG

    @property
    def confidence_level(self) -> str:
        """Nhận ra dấu hiệu thì SUY RA; không nhận ra thì KHÔNG KIỂM ĐƯỢC.

        Phân loại ở đây là so mẫu trên chuỗi lỗi, không phải một phép đo. Gắn
        ĐÃ KIỂM cho nó sẽ khiến người đọc bỏ qua bước tự đọc thông báo gốc —
        và loại KHÁC tồn tại chính vì bộ mẫu này không bao giờ phủ hết.
        """
        from eaa.confidence import KHONG_KIEM_DUOC, SUY_RA

        return SUY_RA if self.kind != KHAC else KHONG_KIEM_DUOC

    def render(self) -> str:
        from eaa.confidence import header

        dong = [
            f"Cài {self.tool or 'công cụ'} không thành công — loại lỗi: {self.kind.upper()}",
            "",
            header(self.confidence_level),
            "",
        ]
        if self.signal:
            dong += [f"  dấu hiệu nhận ra: {self.signal}", ""]
        if self.output:
            # Giữ phần CUỐI, không phải phần đầu. Đầu ra của trình quản lý gói
            # mở màn bằng hàng chục dòng tải về rồi mới tới câu nói thật, nên
            # tám dòng đầu thường là tám dòng vô nghĩa.
            #
            # `doctor._loi_cua_lenh` đã ghi đúng lý lẽ ấy trong chú thích của nó
            # và giữ phần cuối. Hai chỗ cắt cùng một thứ theo hai chiều ngược
            # nhau là một mâu thuẫn nằm im cho tới khi có ai đó nối chúng lại —
            # và SL-169 là lần nối ấy.
            dong += ["  máy nói:", *[f"      {d}" for d in self.output.strip().splitlines()[-8:]], ""]
        if self.ladder:
            dong.append("Thang gỡ — rẻ trước, đắt sau:")
            dong += [r.render() for r in self.ladder]
        return "\n".join(dong)


def classify(output: str, *, returncode: int = 1, tool: str = "") -> InstallDiagnosis:
    """Đọc đầu ra lệnh cài và xếp nó vào một trong sáu loại."""
    van_ban = output or ""
    for loai, mau in _BIEN_DICH:
        for m in mau:
            khop = m.search(van_ban)
            if khop:
                return InstallDiagnosis(
                    kind=loai,
                    tool=tool,
                    signal=khop.group(0)[:80],
                    output=van_ban,
                    returncode=returncode,
                    ladder=tuple(remedies(loai, tool=tool, output=van_ban)),
                )
    return InstallDiagnosis(
        kind=KHAC,
        tool=tool,
        output=van_ban,
        returncode=returncode,
        ladder=tuple(remedies(KHAC, tool=tool, output=van_ban)),
    )


def _dong_loi(output: str) -> str:
    """Dòng đáng đem đi tra — dòng CUỐI có nội dung, không phải dòng đầu.

    Cùng lý lẽ với `doctor.SO_DONG_LOI` và với phần "máy nói" của
    :meth:`InstallDiagnosis.render`: đầu ra của trình quản lý gói mở màn bằng
    hàng chục dòng tải về rồi mới tới câu nói thật. Đem dòng đầu đi tra là đem
    một dòng tiến trình đi hỏi Internet.
    """
    dong = [d.strip() for d in (output or "").strip().splitlines() if d.strip()]
    return dong[-1][:80] if dong else ""


def remedies(
    kind: str,
    *,
    tool: str = "",
    output: str = "",
    alternatives: Sequence[str] = (),
    install_command: Sequence[str] = (),
) -> list[Remedy]:
    """Thang gỡ cho một loại lỗi. Rẻ trước, đắt sau, và luôn dừng ở con người."""
    ten = tool or "công cụ"
    thang: list[Remedy] = []

    def them(action: str, detail: str, *, agent: bool = False, command: Sequence[str] = ()) -> None:
        thang.append(Remedy(len(thang) + 1, action, detail, agent, tuple(command)))

    if kind == MANG:
        them("Thử lại có giãn cách",
             f"Lỗi mạng thường là tạm thời. Thử lại {SO_LAN_THU_LAI} lần, giãn "
             f"{', '.join(f'{g:g}s' for g in retry_delays())}.",
             agent=True)
        them("Kiểm mạng ra ngoài và proxy",
             "Đo thật xem máy có ra được Internet không, và có biến proxy nào đang chặn.",
             agent=True, command=("eaa", "environ"))
        them("Đổi kho / mirror",
             "Nếu chỉ một kho hỏng, đổi sang mirror khác của cùng trình quản lý gói.")
        them("Tải gói về rồi cài ngoại tuyến",
             "Khi mạng bị chặn hẳn theo chính sách: tải trên máy khác, chép sang, cài từ tệp.")
    elif kind == QUYEN:
        them("Đọc lại lệnh, xem nó ghi vào đâu",
             "Lỗi quyền là lỗi KHÔNG đáng thử lại — thử lại bao nhiêu lần cũng vậy.",
             agent=True)
        them("Chạy lệnh với quyền quản trị",
             "Chỉ khi bạn đã đọc và đồng ý với lệnh. Agent không chạy hộ bước này.")
        them("Cài vào thư mục người dùng thay vì tầm hệ thống",
             "Nhiều trình cài có chế độ --user hoặc tiền tố riêng; tránh phải nâng quyền.")
    elif kind == PHU_THUOC:
        them("Xác định thứ còn thiếu, cài NÓ trước",
             "Cài lại chính công cụ này sẽ hỏng y hệt. Thứ tự phụ thuộc là: thư "
             "viện hệ thống trước, gói theo ngôn ngữ sau.",
             agent=True)
        them("Ghim một phiên bản cũ hơn",
             f"Khi bản mới nhất của {ten} đòi thứ máy này không có, một bản cũ hơn thường không đòi.")
        them("Cài vào môi trường cô lập",
             "Môi trường ảo riêng cho công cụ này, để không phá phụ thuộc sẵn có.")
    elif kind == BUILD:
        them("Kiểm trình biên dịch và tệp tiêu đề của hệ",
             "Gói này build từ nguồn. Thiếu trình biên dịch hoặc gói -dev của hệ là nguyên nhân thường gặp nhất.",
             agent=True)
        them("Cài bản dựng sẵn thay vì build từ nguồn",
             "Bản nhị phân dựng sẵn tránh hẳn cả lớp lỗi này.")
        them("Cài bộ công cụ biên dịch của hệ", "Trên macOS: Command Line Tools. Trên Linux: gói build-essential tương đương.")
    elif kind == KHONG_TIM_THAY:
        them("Kiểm lại TÊN gói cho đúng hệ điều hành này",
             "Cùng một công cụ mang tên khác nhau ở mỗi kho. Đây là nguyên nhân "
             "số một, và cũng là chỗ dễ gõ nhầm thành một gói khác có thật.",
             agent=True)
        them("Cập nhật danh mục gói rồi thử lại",
             "Danh mục cũ thì gói mới không có trong đó.")
        them("Tra kho chính thức của công cụ",
             f"Đọc trang cài đặt của chính {ten} thay vì đoán tên gói.",
             agent=True, command=("eaa", "research", f"{ten} official installation guide"))
    else:
        them("Đọc nguyên văn thông báo lỗi",
             "Bộ nhận dạng không khớp mẫu nào — nghĩa là nó KHÔNG biết đây là lỗi "
             "gì, chứ không phải đây là lỗi lạ. Đọc thẳng đầu ra là bước đúng.",
             agent=True)
        them("Tra thông báo lỗi này",
             "Tìm nguyên văn dòng lỗi; ưu tiên trang phát hành và kho mã của chính công cụ.",
             agent=True, command=("eaa", "research", "--", _dong_loi(output) or ten))

    if alternatives:
        them("Đổi sang công cụ tương đương",
             f"Đã khai sẵn cho {ten}: {', '.join(alternatives)}. Đổi công cụ là "
             "đổi cả cổng kiểm chứng, nên đây là quyết định của bạn.")

    # Bậc áp chót: tự viết một thứ tối thiểu thay thế. Đứng SAU mọi bậc cài
    # thật, và có lý do: một công cụ tự viết chỉ làm được phần hẹp của việc, và
    # nó không có ai bảo trì ngoài chính dự án này. Nó là lối thoát khi mọi
    # cách khác đã hết, không phải một lựa chọn ngang hàng.
    them("Tự viết một thứ tối thiểu thay thế",
         f"Khi {ten} không cài nổi bằng cách nào và việc cần nó chỉ dùng một "
         "phần nhỏ, tôi viết được một công cụ hẹp làm đúng phần ấy. Nó đi qua "
         "ba cổng rồi tới bạn duyệt, như mọi công cụ tự sinh khác.",
         agent=True, command=("tool", "propose", f"'thay {ten} cho việc đang cần'"))

    if install_command:
        them("Quay lui — gỡ phần đã cài dở",
             "Cài hỏng nửa chừng để lại môi trường ở trạng thái không ai mô tả được.",
             command=rollback_command(install_command))

    them("Bàn giao người",
         f"Thang đã hết. Ghi lại vào sổ tay lỗi để lần sau tra được, rồi dừng: "
         f"một Agent thử mãi là một Agent đốt thời gian của bạn thay vì báo cho bạn.")
    return thang


#: Ánh xạ động từ cài → động từ gỡ, theo từng trình quản lý gói.
_GO: dict[str, tuple[str, ...]] = {
    "apt-get": ("remove", "-y"),
    "apt": ("remove", "-y"),
    "brew": ("uninstall",),
    "dnf": ("remove", "-y"),
    "yum": ("remove", "-y"),
    "pacman": ("-R", "--noconfirm"),
    "zypper": ("remove", "-y"),
    "apk": ("del",),
    "choco": ("uninstall", "-y"),
    "winget": ("uninstall", "-e", "--id"),
    "scoop": ("uninstall",),
    "port": ("uninstall",),
    "pip": ("uninstall", "-y"),
    "pip3": ("uninstall", "-y"),
    "npm": ("uninstall", "-g"),
    "cargo": ("uninstall",),
}

#: Động từ cài — phần bị thay bằng động từ gỡ.
_DONG_TU_CAI = {"install", "add", "-S", "-U"}


def rollback_command(install: Sequence[str]) -> tuple[str, ...]:
    """Suy lệnh gỡ từ chính lệnh cài. Trả rỗng khi không suy được.

    Trả RỖNG chứ không đoán bừa. Một lệnh gỡ đoán sai chạy với quyền quản trị
    là cách hỏng tệ hơn hẳn việc không có lệnh gỡ nào.
    """
    argv = [x for x in install if x]
    if not argv:
        return ()

    # Bỏ tiền tố nâng quyền, nhưng giữ lại để trả về nguyên dạng.
    tien_to: list[str] = []
    while argv and argv[0] in ("sudo", "doas"):
        tien_to.append(argv.pop(0))
    if not argv:
        return ()

    trinh = argv[0]
    go = _GO.get(trinh)
    if go is None:
        return ()

    # Mọi thứ sau động từ cài, bỏ cờ, là tên gói.
    con_lai = argv[1:]
    vi_tri = next((i for i, x in enumerate(con_lai) if x in _DONG_TU_CAI), -1)
    if vi_tri < 0:
        return ()
    goi = [x for x in con_lai[vi_tri + 1:] if not x.startswith("-")]
    if not goi:
        return ()
    return tuple(tien_to + [trinh] + list(go) + goi)
