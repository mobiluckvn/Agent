#include "drv_buzzer.h"

static uint32_t remaining_time_ms = 0;
static bool is_beeping = false;

void buzzer_beep_async(uint32_t duration_ms) {
    // Thiếu thông tin tài liệu cho thanh ghi điều khiển chân PB2 (active_level=1)
    remaining_time_ms = duration_ms;
    is_beeping = true;
}

void buzzer_stop(void) {
    // Thiếu thông tin tài liệu cho thanh ghi điều khiển chân PB2
    remaining_time_ms = 0;
    is_beeping = false;
}

void buzzer_update(uint32_t delta_ms) {
    if (is_beeping) {
        if (remaining_time_ms > delta_ms) {
            remaining_time_ms -= delta_ms;
        } else {
            buzzer_stop();
        }
    }
}

bool buzzer_is_beeping(void) {
    return is_beeping;
}
