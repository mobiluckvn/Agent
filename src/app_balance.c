#include "app_balance.h"
#include "drv_imu.h"
#include "logic_pid.h"
#include "drv_stepper.h"
#include "drv_buzzer.h"
#include "drv_button.h"
#include <stdint.h>
#include <stdbool.h>

// 4ms per step / 0.000031s per sample = 129.03 -> 129 iterations
#define IMU_MAX_ITERATIONS 129
#define CALIB_TIMEOUT_MS 10000
#define MISSING_SAMPLES_MAX 10

typedef enum {
    STATE_CHO_NUT,
    STATE_HIEU_CHINH,
    STATE_SAN_SANG,
    STATE_CAN_BANG,
    STATE_NGA
} app_state_t;

static app_state_t state = STATE_CHO_NUT;
static uint32_t now_ms = 0;
static uint32_t state_start_ms = 0;
static bool is_error_nga = false;
static int missing_samples_count = 0;

void i2c_tick(void);

void app_init(void) {
    imu_init();
    stepper_init();
    buzzer_init();
    button_init();
    
    state = STATE_CHO_NUT;
    now_ms = 0;
    buzzer_beep_async(now_ms, 100);
}

void app_step(void) {
    now_ms += 4;
    
    i2c_tick();
    
    bool got_sample = false;
    for (int i = 0; i < IMU_MAX_ITERATIONS; i++) {
        if (imu_update()) {
            got_sample = true;
            break;
        }
    }
    
    buzzer_update(now_ms);
    button_event_t btn = button_get_event(now_ms);
    
    if (state == STATE_HIEU_CHINH) {
        uint32_t elapsed = now_ms - state_start_ms;
        if (elapsed == 400 || elapsed == 800 || elapsed == 1200 || elapsed == 1600) {
            buzzer_beep_async(now_ms, 100);
        }
    } else if (state == STATE_SAN_SANG) {
        uint32_t elapsed = now_ms - state_start_ms;
        if (elapsed == 200) {
            buzzer_beep_async(now_ms, 100);
        }
    } else if (state == STATE_NGA && is_error_nga) {
        uint32_t elapsed = now_ms - state_start_ms;
        if (elapsed > 0) {
            uint32_t cycle = elapsed % 2000;
            if (cycle == 0 || cycle == 200 || cycle == 400) {
                buzzer_beep_async(now_ms, 100);
            }
        }
    }
    
    switch (state) {
        case STATE_CHO_NUT:
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_HIEU_CHINH;
                state_start_ms = now_ms;
                imu_calibrate_begin();
                buzzer_beep_async(now_ms, 100);
            }
            break;
            
        case STATE_HIEU_CHINH:
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_CHO_NUT;
                state_start_ms = now_ms;
                buzzer_beep_async(now_ms, 100);
            } else if (!imu_calibrate_busy()) {
                imu_calibrate_commit();
                state = STATE_SAN_SANG;
                state_start_ms = now_ms;
                buzzer_beep_async(now_ms, 100);
            } else if (now_ms - state_start_ms > CALIB_TIMEOUT_MS) {
                state = STATE_NGA;
                state_start_ms = now_ms;
                is_error_nga = true;
                buzzer_beep_async(now_ms, 100);
            }
            break;
            
        case STATE_SAN_SANG:
            if (now_ms - state_start_ms >= 1000) {
                state = STATE_CAN_BANG;
                missing_samples_count = 0;
            }
            break;
            
        case STATE_CAN_BANG:
            if (!got_sample) {
                missing_samples_count++;
                if (missing_samples_count >= MISSING_SAMPLES_MAX) {
                    stepper_set_speed(0, 0);
                    pid_compute(imu_get_tilt_angle(), 0.0f, false);
                    state = STATE_NGA;
                    is_error_nga = false;
                }
            } else {
                missing_samples_count = 0;
                float angle = imu_get_tilt_angle();
                if (angle > 30.0f || angle < -30.0f) {
                    stepper_set_speed(0, 0);
                    pid_compute(angle, 0.0f, false);
                    state = STATE_NGA;
                    is_error_nga = false;
                } else {
                    float out = pid_compute(angle, 0.0f, true);
                    int16_t motor = 0;
                    if (out > 0.0f) {
                        float comp = 405.0f - (5500.0f / (out + 9.0f));
                        motor = 400 - (int16_t)comp;
                    } else if (out < 0.0f) {
                        float comp = -405.0f + (5500.0f / (-out + 9.0f));
                        motor = -400 - (int16_t)comp;
                    }
                    stepper_set_speed(motor, motor);
                }
            }
            break;
            
        case STATE_NGA:
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_CHO_NUT;
                state_start_ms = now_ms;
                buzzer_beep_async(now_ms, 100);
            }
            break;
    }
}

void app_tick(void) {
    // Empty implementation to satisfy header
}
