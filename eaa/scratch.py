"""Chỗ làm nháp — hỏi một câu mà không phải soạn cả hồ sơ dự án.

EAA-SRS-01 FR-PLT-03, EAA-MDD-00 §6. Xem `docs/SAI_LECH_THIET_KE.md` mục SL-78.

Khoảng trống module này lấp
----------------------------

34 trong 38 lệnh đòi một dự án đầy đủ: ``constraints.yaml`` và
``hardware_profile.yaml`` phải có sẵn trước khi gõ lệnh đầu tiên. Đúng cho một
sản phẩm sắp bàn giao — sai cho câu hỏi mà người ta thật sự mở công cụ ra để
hỏi: *"viết giúp tôi một hàm đọc kênh này"*, *"test riêng module kia"*.

Cửa vào ấy quá cao, và nó cao ở đúng chỗ người dùng chưa có gì để điền.

Điều module này KHÔNG làm
--------------------------

Nó **không tắt cổng nào, không nới quyền nào, không bỏ gate nào.** Một chỗ làm
nháp là một dự án thật, đầy đủ, ở một thư mục riêng — chỉ khác ở chỗ phần
YAML khuôn mẫu được sinh ra thay vì bắt người gõ.

Phân biệt này quan trọng hơn vẻ ngoài của nó. Cách "dễ" hơn — thêm một cờ cho
phép bỏ qua cổng khi làm nháp — sẽ phá đúng bất biến trung tâm của cả sản
phẩm: *merge chỉ xảy ra khi toàn bộ ToolReport.passed và G3 approved*. Một cờ
bỏ qua tồn tại là một cờ sẽ được dùng, và nó sẽ được dùng đúng vào lúc gấp.

Nên ở đây rào cản được hạ bằng cách **giảm việc phải gõ**, không phải bằng
cách giảm việc phải kiểm.

Ràng buộc mặc định là GIẢ ĐỊNH, và nói ra điều đó
--------------------------------------------------

Ràng buộc sinh sẵn (dung lượng, tần số, chân) không phải số đo của bo nào cả.
Chúng mang nhãn GIẢ ĐỊNH trong chính tệp, và ``eaa status`` nhắc lại. Một con
số mặc định trông y hệt một con số đã chốt, và đó là cách một bản nháp lặng lẽ
trở thành một bản bàn giao.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ScratchError",
    "SCRATCH_DIR",
    "SCRATCH_MARK",
    "SCRATCH_ENV",
    "is_scratch",
    "create_scratch",
    "scratch_root",
    "chon_platform",
    "packs_co_san",
    "warning_banner",
]

SCRATCH_DIR = ".eaa/scratch"

#: Tệp đánh dấu. Có mặt nghĩa là mọi ràng buộc trong thư mục này là GIẢ ĐỊNH.
SCRATCH_MARK = ".scratch"

#: Đặt biến này (hoặc dùng ``--scratch``) để lệnh tự dựng chỗ làm nháp khi
#: chưa có dự án nào.
SCRATCH_ENV = "EAA_SCRATCH"

BANG_TEN = "nhap"


class ScratchError(Exception):
    """Không dựng được chỗ làm nháp."""


def scratch_root(repo: Path, name: str = BANG_TEN) -> Path:
    return repo / SCRATCH_DIR / name


def is_scratch(project: Path) -> bool:
    return (Path(project) / SCRATCH_MARK).is_file()


def warning_banner(project: Path) -> str:
    """Dòng nhắc để mọi lệnh in ra khi đang làm trong chỗ nháp.

    Nêu ĐÍCH DANH những con số đang là giả định, không chỉ nói "có giả định".
    Người đang cầm bo thật nhìn một con số cụ thể là biết ngay nó sai; nhìn
    một câu chung chung thì không.
    """
    project = Path(project)
    if not is_scratch(project):
        return ""

    dong = [
        "⚠ CHỖ LÀM NHÁP. Ràng buộc và hồ sơ phần cứng ở đây do máy sinh sẵn — "
        "chúng là GIẢ ĐỊNH, không phải số đo của bo nào.",
    ]

    # Con số nháp không trung tính: nó là dung lượng và tần số của một họ chip
    # nào đó. Đem áp lên bo khác thì nó sai theo kiểu nhìn vẫn hợp lý — và một
    # ngân sách flash sai làm cổng size gác nhầm chỗ.
    try:
        rb = yaml.safe_load((project / "constraints.yaml").read_text(encoding="utf-8"))
        mcu = (rb or {}).get("mcu") or {}
        so = [f"{k} = {v}" for k, v in mcu.items()]
        if so:
            dong.append("  Đang giả định: " + " · ".join(so))
            dong.append("  Bo thật của bạn gần như chắc chắn KHÁC những số này.")
    except Exception:  # noqa: BLE001 - đọc không được thì bỏ phần chi tiết
        pass

    dong += [
        "  Cổng và gate vẫn chạy đủ như dự án thật; thứ được giảm là việc phải "
        "gõ, không phải việc phải kiểm.",
        "  Đưa vào việc thật thì sửa constraints.yaml và hardware_profile.yaml "
        "bằng số đo thật, rồi xóa tệp .scratch.",
    ]
    return "\n".join(dong)


_CONSTRAINTS = {
    "project": "nháp",
    "platform": "avr",
    "constraints_version": "nhap-1",
    "mcu": {"flash_bytes": 32768, "ram_bytes": 2048, "f_cpu_hz": 16000000},
    "budget": {"flash_bytes": 30000, "ram_bytes": 1800, "stack_headroom_bytes_min": 256},
    "limits": {"max_module_lines": 250, "max_repair_rounds": 3},
    "acceptance": [],
}

#: Hồ sơ phần cứng sinh sẵn. Mọi trường phải ĐÚNG KIỂU mà ``eaa/kb.py`` đọc,
#: kể cả khi chưa có nội dung.
#:
#: Bản đầu ghi ``mcu: "chưa xác định"`` — một chuỗi ở chỗ lược đồ đòi ánh xạ.
#: Chỗ nháp vì thế **sinh ra đã hỏng**: mọi lệnh dựng Knowledge Graph đều sập
#: ngay từ lượt chạy đầu tiên. Một chỗ làm nháp mà không chạy nổi một lệnh thì
#: nó không giảm việc phải gõ, nó thêm việc phải gỡ.
#:
#: Rỗng-nhưng-đúng-kiểu nói cùng một chuyện với "chưa xác định", và nói bằng
#: thứ ngôn ngữ mà phần còn lại của hệ đọc được.
_HARDWARE = {
    "board": "chưa xác định",
    "mcu": {},
    "pin_functions": {},
    "components": [],
}


def packs_co_san(repo: Path) -> list[str]:
    """Tên các Platform Pack đang cài, sắp theo thứ tự chữ."""
    thu_muc = repo / "packs"
    if not thu_muc.is_dir():
        return []
    return sorted(p.name for p in thu_muc.iterdir() if p.is_dir())


def chon_platform(repo: Path, name: str, platform: str = "") -> tuple[str, str]:
    """Chọn Platform Pack cho một chỗ nháp. Trả (tên pack, lý do chọn).

    Vì sao KHÔNG mặc định một pack cố định
    ---------------------------------------

    Bản đầu mặc định một pack cố định. Gặp thật: Agent dựng chỗ nháp cho một
    bo thuộc họ khác hẳn, và nhận về một hồ sơ khai đúng cái pack mặc định ấy
    — sai trình biên dịch, sai bộ luật phân tích tĩnh, sai khuôn mẫu firmware.

    Cái đó **tệ hơn một lần sập**. Sập thì người ta sửa; một giá trị sai mà
    im lặng thì mọi thứ dựng lên trên nó đều sai theo, và cái sai chỉ lộ ra ở
    cổng biên dịch, sau khi đã đi qua vài bước.

    Suy từ tên có phải là đoán không? Có — nhưng nó đoán từ **bằng chứng**
    (tên pack đang cài, đối chiếu với tên người dùng vừa gõ), nó **nói ra là
    mình đoán**, và nó từ chối khi bằng chứng không đủ. Một hằng số ``avr``
    cũng là đoán, chỉ khác là nó bỏ qua bằng chứng và không nói gì.
    """
    co = packs_co_san(repo)
    if platform:
        return platform, "bạn nêu bằng --platform"

    ten_thuong = name.lower()
    khop = [p for p in co if p.lower() in ten_thuong]
    if len(khop) == 1:
        return khop[0], f"suy từ tên chỗ nháp {name!r} — GIẢ ĐỊNH, kiểm lại giúp"
    if len(co) == 1:
        return co[0], f"chỉ có một Platform Pack đang cài ({co[0]})"

    if len(khop) > 1:
        raise ScratchError(
            f"Tên {name!r} khớp nhiều Platform Pack: {', '.join(khop)}. "
            "Nêu rõ bằng --platform <tên>."
        )
    raise ScratchError(
        f"Không suy được Platform Pack từ tên {name!r}, và có "
        f"{len(co)} pack đang cài: {', '.join(co) or '(không cái nào)'}.\n"
        "  Nêu rõ bằng --platform <tên>.\n"
        "  Không mặc định bừa một pack: sai pack là sai trình biên dịch và sai "
        "bộ luật phân tích tĩnh, và cái sai ấy chỉ lộ ra ở cổng biên dịch."
    )


def create_scratch(
    repo: Path,
    *,
    name: str = BANG_TEN,
    platform: str = "",
    force: bool = False,
) -> Path:
    """Dựng một dự án nháp đầy đủ, với phần YAML khuôn mẫu sinh sẵn."""
    goc = scratch_root(repo, name)
    if goc.exists() and not force:
        if not is_scratch(goc):
            raise ScratchError(
                f"{goc} đã tồn tại và KHÔNG phải chỗ làm nháp. Từ chối ghi đè: "
                "một thư mục không mang dấu .scratch có thể là việc thật."
            )
        return goc

    platform, ly_do = chon_platform(repo, name, platform)
    if not (repo / "packs" / platform).is_dir():
        co = packs_co_san(repo)
        raise ScratchError(
            f"Không có Platform Pack {platform!r}. Đang có: "
            f"{', '.join(co) or '(không cái nào)'}"
        )

    goc.mkdir(parents=True, exist_ok=True)
    (goc / "datasheets").mkdir(exist_ok=True)

    rb = {**_CONSTRAINTS, "project": name, "platform": platform}
    (goc / "constraints.yaml").write_text(
        "# SINH SẴN cho chỗ làm nháp — mọi số ở đây là GIẢ ĐỊNH.\n"
        "# Đưa vào việc thật thì thay bằng số đo của bo bạn đang dùng.\n"
        f"# Platform Pack chọn được vì: {ly_do}.\n"
        "# Sai pack là sai trình biên dịch — kiểm lại dòng 'platform' bên dưới.\n"
        + yaml.safe_dump(rb, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (goc / "hardware_profile.yaml").write_text(
        "# SINH SẴN cho chỗ làm nháp — chưa mô tả bo nào cả.\n"
        "# 'eaa brief' sẽ hỏi bạn và điền phần này.\n"
        + yaml.safe_dump(_HARDWARE, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (goc / SCRATCH_MARK).write_text(
        f"Dựng lúc {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        "Xóa tệp này khi bạn đã thay ràng buộc bằng số đo thật.\n",
        encoding="utf-8",
    )
    return goc
