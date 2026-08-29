/* Mã khởi động và bảng vector cho Cortex-M — do PACK cấp.
 *
 * AVR không cần tệp này vì bộ dịch của nó kèm sẵn mã khởi động; ARM bare-metal
 * thì cần. Đây chính là tham số interface mà pack thứ hai làm lộ ra:
 * FirmwareTemplates.sources.
 *
 * Bảng vector ở đây cố ý TỐI GIẢN: con trỏ ngăn xếp, Reset_Handler, và các
 * ngoại lệ lõi. Ngắt ngoại vi chưa khai — thêm chúng là việc của pack khi có
 * kịch bản cần, không phải việc đoán trước.
 */

#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;

int main(void);
void Reset_Handler(void);
void Default_Handler(void);
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));

void Reset_Handler(void)
{
    uint32_t *nguon = &_sidata;
    uint32_t *dich = &_sdata;

    /* Chép phần dữ liệu đã khởi tạo từ Flash sang RAM. */
    while (dich < &_edata) {
        *dich++ = *nguon++;
    }

    /* Xóa phần dữ liệu chưa khởi tạo. Bỏ bước này thì biến static mang giá trị
     * của lần chạy trước — một lỗi chỉ hiện ra sau khi nạp lại, tức là đúng
     * lúc khó nghi ngờ nhất. */
    for (dich = &_sbss; dich < &_ebss; dich++) {
        *dich = 0u;
    }

    (void)main();

    for (;;) {
    }
}

void Default_Handler(void)
{
    /* Ngoại lệ chưa xử lý thì DỪNG HẲN, không quay về.
     *
     * Quay về sau một lỗi bus hay lệnh sai nghĩa là chạy tiếp trên một trạng
     * thái đã hỏng, và mọi số đo sau đó đều vô nghĩa mà vẫn trông bình thường. */
    for (;;) {
    }
}

__attribute__((section(".isr_vector"), used))
void (* const g_bang_vector[])(void) = {
    (void (*)(void))&_estack,
    Reset_Handler,
    Default_Handler,   /* NMI */
    Default_Handler,   /* HardFault */
    Default_Handler,   /* MemManage */
    Default_Handler,   /* BusFault */
    Default_Handler,   /* UsageFault */
    0, 0, 0, 0,
    Default_Handler,   /* SVCall */
    Default_Handler,   /* DebugMonitor */
    0,
    Default_Handler,   /* PendSV */
    SysTick_Handler,
};
