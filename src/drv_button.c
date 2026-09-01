#include "drv_button.h"

// Thiếu thông tin tài liệu thanh ghi cho PB4.
// Không thể viết hàm cấu hình và đọc thanh ghi phần cứng.
// Không lấp chỗ trống.

static bool raw_state = false;
static bool last_reading = false;
static bool debounced_state = false;
static uint32_t last_debounce_time = 0;
static const uint32_t DEBOUNCE_DELAY_MS = 20;

void button_init(void) {
    // Thiếu thông tin cấu hình thanh ghi cho PB4 (pullup, direction).
    raw_state = false;
    last_reading = false;
    debounced_state = false;
    last_debounce_time = 0;
}

void button_set_raw_pin_level(uint8_t level) {
    // active_level = 0
    raw_state = (level == 0);
}

button_event_t button_get_event(uint32_t current_time_ms) {
    button_event_t event = BUTTON_EVENT_NONE;
    bool current_reading = raw_state; 
    
    if (current_reading != last_reading) {
        last_debounce_time = current_time_ms;
    }
    
    if ((current_time_ms - last_debounce_time) >= DEBOUNCE_DELAY_MS) {
        if (current_reading != debounced_state) {
            debounced_state = current_reading;
            if (debounced_state) {
                event = BUTTON_EVENT_PRESSED;
            } else {
                event = BUTTON_EVENT_RELEASED;
            }
        }
    }
    
    last_reading = current_reading;
    return event;
}
