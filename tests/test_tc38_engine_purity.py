"""TC-38 — Engine sạch tuyệt đối khỏi phần cứng cụ thể (FR-PLT-01, ADR-09).

Quét toàn bộ mã nguồn engine (``eaa/``) tìm tên MCU, thanh ghi, linh kiện và
trình toolchain đặc thù một họ vi điều khiển. Kết quả mong đợi: 0 vi phạm —
mọi đặc thù phần cứng chỉ được phép nằm trong ``packs/`` và ``projects/``.

Test này chạy trong CI mỗi commit kể từ commit đầu tiên của dự án
(EAA-MDD-00 §6; CLAUDE.md "Kiến trúc 3 tầng — quy tắc số 1").

Vì sao là một test chứ không phải một quy ước: tính TỔNG QUÁT là định vị sản
phẩm (quyết định #14, NFR-05). Một hằng số phần cứng lọt vào engine không làm
hỏng bản build nào — nó chỉ âm thầm biến agent tổng quát thành agent chuyên
dụng cho một mạch. Chỉ có kiểm thử tự động mới bắt được kiểu thoái hóa đó.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "eaa"

# Đuôi file được quét trong engine: mã nguồn và cả dữ liệu đi kèm engine —
# một hằng số phần cứng giấu trong YAML của engine cũng là vi phạm.
SCANNED_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".toml", ".md", ".txt"}

# Danh mục cấm, nhóm theo loại để thông báo lỗi nói được VÌ SAO bị chặn.
# Mỗi mẫu là regex có biên từ, so khớp không phân biệt hoa thường.
FORBIDDEN_PATTERNS: dict[str, tuple[str, ...]] = {
    "Tên MCU / họ vi điều khiển": (
        r"atmega\w*",
        r"attiny\w*",
        r"atxmega\w*",
        r"stm32\w*",
        r"esp32\w*",
        r"esp8266",
        r"rp2040",
        r"nrf5\d*",
        r"msp430\w*",
        r"riscv",
        r"cortex[-_]?m\d*",
    ),
    "Tên thanh ghi phần cứng": (
        r"tccr\d?[a-c]?",
        r"tcnt\d",
        r"ocr\d[a-c]?",
        r"timsk\d?",
        r"tifr\d?",
        r"twbr",
        r"twcr",
        r"twsr",
        r"twdr",
        r"twar",
        r"ubrr\d?[hl]?",
        r"ucsr\d?[a-c]?",
        r"spcr",
        r"spsr",
        r"spdr",
        r"admux",
        r"adcsra?",
        r"ddr[a-l]",
        r"portb|portc|portd",  # PORTA/PORTE… quá dễ trùng từ thường
        r"pin[b-d]\b",
        r"sreg",
        r"gpior\d",
        r"wgm\d\d?",
        r"cs\d\d",
    ),
    "Mã linh kiện cụ thể": (
        r"mpu6050",
        r"mpu9250",
        r"a4988",
        r"drv8825",
        r"l298n?",
        r"hc[-_]?sr04",
        r"ds18b20",
        r"bmp\d{3}",
        r"nrf24l01",
    ),
    "Toolchain đặc thù nền tảng": (
        r"avr[-_]gcc",
        r"avr[-_]size",
        r"avr[-_]objcopy",
        r"avrdude",
        r"arm[-_]none[-_]eabi[-_]gcc",
        r"openocd",
        r"st[-_]?link",
        r"avr[-_]libc",
        r"<avr/",
    ),
    "Tên nền tảng / hệ sinh thái cụ thể": (
        r"arduino",
        r"platformio",
        r"wokwi",
    ),
}

# Bọc trong nhóm không bắt: nếu không, mẫu có dấu | như "portb|portc|portd"
# sẽ bị đọc thành (\bportb)|(portc)|(portd\b) — mất biên từ ở các nhánh giữa.
_COMPILED = {
    category: [re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE) for pattern in patterns]
    for category, patterns in FORBIDDEN_PATTERNS.items()
}


def _engine_files() -> list[Path]:
    return sorted(
        path
        for path in ENGINE_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SCANNED_SUFFIXES
        and "__pycache__" not in path.parts
    )


def test_engine_directory_exists() -> None:
    """Bản thân việc thiếu thư mục engine phải là fail, không phải pass rỗng."""
    assert ENGINE_DIR.is_dir(), f"Không tìm thấy thư mục engine: {ENGINE_DIR}"
    assert _engine_files(), "Engine rỗng — TC-38 sẽ pass giả tạo, kiểm tra lại cây thư mục"


def test_tc38_engine_khong_chua_ten_phan_cung_cu_the() -> None:
    """TC-38: quét engine tìm tên phần cứng cụ thể → mong đợi 0 kết quả."""
    violations: list[str] = []

    for path in _engine_files():
        rel = path.relative_to(ENGINE_DIR.parent)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:  # pragma: no cover - engine chỉ chứa file text
            pytest.fail(f"{rel}: không đọc được dạng UTF-8, engine chỉ chứa file văn bản")

        for lineno, line in enumerate(lines, start=1):
            for category, regexes in _COMPILED.items():
                for regex in regexes:
                    match = regex.search(line)
                    if match:
                        violations.append(
                            f"{rel}:{lineno}: {category} — {match.group(0)!r}\n"
                            f"    {line.strip()}"
                        )

    assert not violations, (
        "Engine chứa tham chiếu phần cứng cụ thể — vi phạm FR-PLT-01 / ADR-09.\n"
        "Mọi đặc thù phần cứng phải nằm trong packs/ (theo họ MCU) hoặc "
        "projects/ (theo dự án); engine chỉ được gọi toolchain qua "
        "interface eaa/platform.py.\n\n" + "\n".join(violations)
    )


def test_danh_muc_cam_tu_bat_duoc_vi_pham_that() -> None:
    """Meta-test: bảo đảm bộ quét thật sự bắt được, không phải regex chết.

    Một test purity hỏng sẽ luôn xanh và không ai biết. Ở đây ta bắn qua bộ
    quét vài dòng mã vi phạm điển hình và đòi nó phải kêu.
    """
    mau_vi_pham = [
        "TCCR1A |= (1 << WGM11);",
        "if mcu == 'atmega328p':",
        'subprocess.run(["avr-gcc", "-mmcu=..."])',
        "# driver cho cảm biến MPU6050",
        "TWBR = 12;",
    ]
    for dong in mau_vi_pham:
        assert any(
            regex.search(dong) for regexes in _COMPILED.values() for regex in regexes
        ), f"Bộ quét TC-38 KHÔNG bắt được vi phạm hiển nhiên: {dong!r}"

    mau_hop_le = [
        "def compile(self, artifact: CodeArtifact) -> ToolReport:",
        "pack = load_platform_pack(state.platform)",
        "logger.info('gate %s approved', gate_id)",
        "registers = graph.registers_for(module_id)",
    ]
    for dong in mau_hop_le:
        assert not any(
            regex.search(dong) for regexes in _COMPILED.values() for regex in regexes
        ), f"Bộ quét TC-38 báo nhầm mã engine hợp lệ: {dong!r}"
