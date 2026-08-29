"""Đo kích thước giả: suy ra từ kích thước tệp nhị phân."""
import pathlib, sys

FLASH_CAP, SRAM_CAP = 32768, 2048
b = pathlib.Path(sys.argv[1])
if not b.is_file():
    print(f"khong tim thay {b}", file=sys.stderr)
    sys.exit(1)

flash = b.stat().st_size
sram = max(1, flash // 20)
print(f"flash_bytes={flash} flash_pct={100*flash/FLASH_CAP:.1f}")
print(f"sram_bytes={sram} sram_pct={100*sram/SRAM_CAP:.1f}")
