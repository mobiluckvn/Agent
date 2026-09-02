#include "app_balance.h"
#include "drv_imu.h"
#include "logic_pid.h"
#include "drv_stepper.h"
#include "drv_buzzer.h"
#include "drv_button.h"
#include <stdint.h>
#include <stdbool.h>

// Hàm i2c_tick từ drv_i2c (không có header)
extern void i2c_tick(void);

// Trần bơm IMU: I2C 400kHz đọc 14 byte mất ~350us, nhưng driver giả định 31us mỗi lần bơm.
// Với chu kỳ 4ms (4000us), số lần bơm tối đa là 4000 / 31 = 129.
#define IMU_PUMP_LIMIT 129

// Mất mẫu N nhịp liên tiếp (N = 25, tương đương 100ms với chu kỳ 4ms)
#define MAX_MISSED_SAMPLES 25

typedef enum {
    STATE_CHO_NUT = 0,
    STATE_HIEU_CHINH,
    STATE_SAN_SANG,
    STATE_CAN_BANG,
    STATE_NGA
} app_state_t;

static uint32_t now_ms = 0;
static app_state_t state = STATE_CHO_NUT;
static uint8_t calib_beep_count = 0;
static uint32_t calib_start_ms = 0;
static uint8_t ready_beep_count = 0;
static uint32_t ready_last_beep_ms = 0;
static uint32_t ready_start_ms = 0;
static uint8_t missed_samples = 0;

void app_init(void) {
    imu_init();
    stepper_init();
    buzzer_init();
    button_init();
    
    now_ms = 0;
    state = STATE_CHO_NUT;
    calib_beep_count = 0;
    calib_start_ms = 0;
    ready_beep_count = 0;
    ready_last_beep_ms = 0;
    ready_start_ms = 0;
    missed_samples = 0;
    
    buzzer_beep_async(now_ms, 100);
}

void app_step(void) {
    now_ms += 4;
    i2c_tick();

    bool has_sample = false;
    for (int i = 0; i < IMU_PUMP_LIMIT; i++) {
        if (imu_update()) {
            has_sample = true;
            break;
        }
    }

    if (!has_sample) {
        if (state == STATE_CAN_BANG) {
            missed_samples++;
            if (missed_samples >= MAX_MISSED_SAMPLES) {
                stepper_set_speed(0, 0);
                pid_compute(imu_get_tilt_angle(), 0.0f, false);
                state = STATE_NGA;
            }
        }
    } else {
        missed_samples = 0;
    }

    buzzer_update(now_ms);
    button_event_t btn = button_get_event(now_ms);

    switch (state) {
        case STATE_CHO_NUT:
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_HIEU_CHINH;
                imu_calibrate_begin();
                calib_beep_count = 0;
                calib_start_ms = now_ms;
            }
            break;

        case STATE_HIEU_CHINH:
            if (calib_beep_count < 5 && (now_ms - calib_start_ms) >= (uint32_t)(calib_beep_count * 380)) {
                buzzer_beep_async(now_ms, 50);
                calib_beep_count++;
            }
            if (!imu_calibrate_busy()) {
                imu_calibrate_commit();
                state = STATE_SAN_SANG;
                ready_start_ms = now_ms;
                ready_beep_count = 0;
            }
            break;

        case STATE_SAN_SANG:
            if (ready_beep_count == 0) {
                buzzer_beep_async(now_ms, 100);
                ready_beep_count++;
                ready_last_beep_ms = now_ms;
            } else if (ready_beep_count == 1 && (now_ms - ready_last_beep_ms) >= 200) {
                buzzer_beep_async(now_ms, 100);
                ready_beep_count++;
                ready_last_beep_ms = now_ms;
            } else if (ready_beep_count == 2 && (now_ms - ready_last_beep_ms) >= 200) {
                state = STATE_CAN_BANG;
            }
            break;

        case STATE_CAN_BANG:
            if (has_sample) {
                float angle = imu_get_tilt_angle();
                if (angle > 30.0f || angle < -30.0f) {
                    stepper_set_speed(0, 0);
                    pid_compute(angle, 0.0f, false);
                    state = STATE_NGA;
                } else {
                    float out = pid_compute(angle, 0.0f, true);
                    int16_t motor = 0;
                    if (out > 0.0f) {
                        float comp = 405.0f - (5500.0f / (out + 9.0f));
                        motor = (int16_t)(400.0f - comp);
                    } else if (out < 0.0f) {
                        float comp = 405.0f - (5500.0f / (-out + 9.0f));
                        motor = (int16_t)(-400.0f + comp);
                    }
                    stepper_set_speed(motor, motor);
                }
            }
            break;

        case STATE_NGA:
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_CHO_NUT;
                buzzer_beep_async(now_ms, 100);
            }
            break;
    }
}
