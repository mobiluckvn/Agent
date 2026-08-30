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
    """Dòng nhắc để mọi lệnh in ra khi đang làm trong chỗ nháp."""
    if not is_scratch(project):
        return ""
    return (
        "⚠ CHỖ LÀM NHÁP. Ràng buộc và hồ sơ phần cứng ở đây do máy sinh sẵn — "
        "chúng là GIẢ ĐỊNH, không phải số đo của bo nào.\n"
        "  Cổng và gate vẫn chạy đủ như dự án thật; thứ được giảm là việc phải "
        "gõ, không phải việc phải kiểm.\n"
        "  Đưa vào việc thật thì sửa constraints.yaml và hardware_profile.yaml "
        "bằng số đo thật, rồi xóa tệp .scratch."
    )


_CONSTRAINTS = {
    "project": "nháp",
    "platform": "avr",
    "constraints_version": "nhap-1",
    "mcu": {"flash_bytes": 32768, "ram_bytes": 2048, "f_cpu_hz": 16000000},
    "budget": {"flash_bytes": 30000, "ram_bytes": 1800, "stack_headroom_bytes_min": 256},
    "limits": {"max_module_lines": 250, "max_repair_rounds": 3},
    "acceptance": [],
}

_HARDWARE = {
    "board": "chưa xác định",
    "mcu": "chưa xác định",
    "pin_functions": {},
    "components": [],
}


def create_scratch(
    repo: Path,
    *,
    name: str = BANG_TEN,
    platform: str = "avr",
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

    pack = repo / "packs" / platform
    if not pack.is_dir():
        co = sorted(p.name for p in (repo / "packs").iterdir() if p.is_dir()) \
            if (repo / "packs").is_dir() else []
        raise ScratchError(
            f"Không có Platform Pack {platform!r}. Đang có: {', '.join(co) or '(không cái nào)'}"
        )

    goc.mkdir(parents=True, exist_ok=True)
    (goc / "datasheets").mkdir(exist_ok=True)

    rb = {**_CONSTRAINTS, "project": name, "platform": platform}
    (goc / "constraints.yaml").write_text(
        "# SINH SẴN cho chỗ làm nháp — mọi số ở đây là GIẢ ĐỊNH.\n"
        "# Đưa vào việc thật thì thay bằng số đo của bo bạn đang dùng.\n"
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
