#include "app_balance.h"
#include "drv_imu.h"
#include "logic_pid.h"
#include "drv_stepper.h"
#include "drv_buzzer.h"
#include "drv_button.h"
#include <stdint.h>
#include <stdbool.h>

// Khai báo hàm i2c_tick theo yêu cầu của hệ thống
void i2c_tick(void);

#define CALIB_TIMEOUT_MS 10000
#define IMU_PUMP_LIMIT 1600

typedef enum {
    STATE_CHO_NUT,
    STATE_HIEU_CHINH,
    STATE_SAN_SANG,
    STATE_CAN_BANG,
    STATE_NGA
} app_state_t;

static app_state_t current_state = STATE_CHO_NUT;
static uint32_t now_ms = 0;
static uint32_t state_timer = 0;
static uint32_t calib_timer = 0;
static uint32_t missed_samples = 0;
static bool nga_error = false;

void app_init(void) {
    buzzer_beep_async(now_ms, 100); // 1 bíp khi có điện
    current_state = STATE_CHO_NUT;
}

void app_tick(void) {
    // Hàm trống theo yêu cầu chữ ký
}

void app_step(void) {
    i2c_tick();

    bool got_sample = false;
    for (int i = 0; i < IMU_PUMP_LIMIT; i++) {
        if (imu_update()) {
            got_sample = true;
            break;
        }
    }

    if (!got_sample) {
        missed_samples++;
        if (missed_samples >= 10 && current_state != STATE_NGA) {
            current_state = STATE_NGA;
            nga_error = true;
            state_timer = 0;
            stepper_set_speed(0, 0);
            pid_compute(imu_get_tilt_angle(), 0.0f, false);
        }
    } else {
        missed_samples = 0;
    }

    buzzer_update(now_ms);
    button_event_t btn = button_get_event(now_ms);

    switch (current_state) {
        case STATE_CHO_NUT:
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_HIEU_CHINH;
                imu_calibrate_begin();
                calib_timer = 0;
                state_timer = 0;
                buzzer_beep_async(now_ms, 50); // Bíp 1/5
            }
            break;

        case STATE_HIEU_CHINH:
            calib_timer += 4;
            
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_CHO_NUT;
                buzzer_beep_async(now_ms, 100);
                break;
            }

            // 5 bíp rải đều
            if (state_timer == 300 || state_timer == 600 || state_timer == 900 || state_timer == 1200) {
                buzzer_beep_async(now_ms, 50);
            }

            if (!imu_calibrate_busy()) {
                imu_calibrate_commit();
                current_state = STATE_SAN_SANG;
                state_timer = 0;
                buzzer_beep_async(now_ms, 50); // Bíp 1/2
            } else if (calib_timer >= CALIB_TIMEOUT_MS) {
                current_state = STATE_NGA;
                nga_error = true;
                state_timer = 0;
            } else {
                state_timer += 4;
            }
            break;

        case STATE_SAN_SANG:
            state_timer += 4;
            if (state_timer == 240) {
                buzzer_beep_async(now_ms, 50); // Bíp 2/2
                current_state = STATE_CAN_BANG;
            }
            break;

        case STATE_CAN_BANG:
            if (got_sample) {
                float angle = imu_get_tilt_angle();
                if (angle > 30.0f || angle < -30.0f) {
                    stepper_set_speed(0, 0);
                    pid_compute(angle, 0.0f, false);
                    current_state = STATE_NGA;
                    nga_error = false;
                    state_timer = 0;
                } else {
                    float out = pid_compute(angle, 0.0f, true);
                    float motor = 0.0f;
                    if (out > 0.0f) {
                        float comp = 405.0f - (5500.0f / (out + 9.0f));
                        motor = 400.0f - comp;
                    } else if (out < 0.0f) {
                        float comp = -405.0f - (5500.0f / (out - 9.0f));
                        motor = -400.0f - comp;
                    }
                    stepper_set_speed((int16_t)motor, (int16_t)motor);
                }
            }
            break;

        case STATE_NGA:
            if (nga_error) {
                uint32_t t = state_timer % 1000;
                if (t == 0 || t == 160 || t == 320) {
                    buzzer_beep_async(now_ms, 50);
                }
            }
            state_timer += 4;
            
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_CHO_NUT;
                buzzer_beep_async(now_ms, 100);
            }
            break;
    }

    now_ms += 4;
}
