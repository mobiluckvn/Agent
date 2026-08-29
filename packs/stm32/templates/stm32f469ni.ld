/* Kịch bản liên kết — bản đồ bộ nhớ của họ chip, do PACK giữ.
 *
 * Vì sao ở pack chứ không ở dự án: bản đồ này là thuộc tính của con chip, và
 * mọi dự án dùng cùng con chip đều dùng chung nó. Dự án nào cần bản đồ khác
 * (bootloader chiếm đầu Flash chẳng hạn) thì khai kịch bản riêng và trỏ
 * {linker_script} sang đó.
 *
 * STM32F469NI: 2 MB Flash, 320 KB SRAM (chỉ dùng khối liền 256 KB tại
 * 0x20000000 cho đơn giản; các khối rời để dành).
 */

ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 256K
}

/* Ngăn xếp đặt ở đỉnh RAM, mọc xuống. */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  .isr_vector : { KEEP(*(.isr_vector)) } > FLASH

  .text : {
    *(.text*)
    *(.rodata*)
    . = ALIGN(4);
    _etext = .;
  } > FLASH

  _sidata = LOADADDR(.data);

  .data : {
    . = ALIGN(4);
    _sdata = .;
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT> FLASH

  .bss : {
    . = ALIGN(4);
    _sbss = .;
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  /DISCARD/ : { *(.ARM.exidx*) }
}
