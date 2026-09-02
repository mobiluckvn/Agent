#include <stdint.h>
#include <stdbool.h>
#include "app_balance.h"
#include "drv_imu.h"
#include "logic_pid.h"
#include "drv_stepper.h"
#include "drv_buzzer.h"
#include "drv_button.h"

#define CALIB_TIMEOUT_MS 10000
#define IMU_PUMP_LIMIT 20000

extern void i2c_tick(void);

typedef enum {
    STATE_CHO_NUT,
    STATE_HIEU_CHINH,
    STATE_SAN_SANG,
    STATE_CAN_BANG,
    STATE_NGA
} app_state_t;

static app_state_t current_state = STATE_CHO_NUT;
static bool is_first_step = true;
static uint32_t now_ms = 0;
static uint32_t calib_start_ms = 0;
static uint8_t missed_samples = 0;

static uint8_t beep_rem = 0;
static uint8_t beep_orig_count = 0;
static uint32_t next_beep_ms = 0;
static uint32_t beep_interval = 0;
static uint32_t beep_duration = 0;
static uint32_t beep_repeat_ms = 0;
static bool beep_seq_active = false;

static void start_beep_seq(uint32_t now, uint8_t count, uint32_t duration, uint32_t interval, uint32_t repeat_ms) {
    beep_orig_count = count;
    beep_rem = count;
    beep_duration = duration;
    beep_interval = interval;
    beep_repeat_ms = repeat_ms;
    beep_seq_active = true;
    next_beep_ms = now;
}

static void process_beep_seq(uint32_t now) {
    if (!beep_seq_active) return;
    if (now >= next_beep_ms) {
        if (beep_rem > 0) {
            buzzer_beep_async(now, beep_duration);
            beep_rem--;
            if (beep_rem > 0) {
                next_beep_ms = now + beep_duration + beep_interval;
            } else {
                if (beep_repeat_ms > 0) {
                    beep_rem = beep_orig_count;
                    next_beep_ms = now + beep_repeat_ms;
                } else {
                    beep_seq_active = false;
                }
            }
        }
    }
}

void app_init(void) {
    imu_init();
    stepper_init();
    buzzer_init();
    button_init();
}

void app_step(void) {
    if (is_first_step) {
        start_beep_seq(now_ms, 1, 100, 0, 0);
        is_first_step = false;
    } else {
        now_ms += 4;
    }

    i2c_tick();

    bool got_sample = false;
    for (uint32_t i = 0; i < IMU_PUMP_LIMIT; i++) {
        if (imu_update()) {
            got_sample = true;
            break;
        }
    }

    if (!got_sample) {
        if (missed_samples < 10) {
            missed_samples++;
        }
        if (missed_samples >= 10 && current_state != STATE_NGA) {
            stepper_set_speed(0, 0);
            pid_compute(0.0f, 0.0f, false);
            current_state = STATE_NGA;
            beep_seq_active = false;
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
                start_beep_seq(now_ms, 5, 100, 100, 0);
                imu_calibrate_begin();
                calib_start_ms = now_ms;
            }
            break;

        case STATE_HIEU_CHINH:
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_CHO_NUT;
                start_beep_seq(now_ms, 1, 100, 0, 0);
            } else {
                if (!imu_calibrate_busy()) {
                    imu_calibrate_commit();
                    current_state = STATE_SAN_SANG;
                    start_beep_seq(now_ms, 2, 100, 100, 0);
                } else if (now_ms - calib_start_ms > CALIB_TIMEOUT_MS) {
                    current_state = STATE_NGA;
                    start_beep_seq(now_ms, 3, 50, 50, 1000);
                }
            }
            break;

        case STATE_SAN_SANG:
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_CHO_NUT;
                start_beep_seq(now_ms, 1, 100, 0, 0);
            } else {
                float angle = imu_get_tilt_angle();
                if (angle > -0.5f && angle < 0.5f) {
                    current_state = STATE_CAN_BANG;
                }
            }
            break;

        case STATE_CAN_BANG:
            if (btn == BUTTON_EVENT_PRESSED) {
                stepper_set_speed(0, 0);
                pid_compute(0.0f, 0.0f, false);
                current_state = STATE_CHO_NUT;
                start_beep_seq(now_ms, 1, 100, 0, 0);
            } else {
                float angle = imu_get_tilt_angle();
                if (angle > 30.0f || angle < -30.0f) {
                    stepper_set_speed(0, 0);
                    pid_compute(0.0f, 0.0f, false);
                    current_state = STATE_NGA;
                    beep_seq_active = false;
                } else if (got_sample) {
                    float out = pid_compute(angle, 0.0f, true);
                    if (out > 0.0f) {
                        out = 405.0f - (5500.0f / (out + 9.0f));
                        int16_t motor = 400 - (int16_t)out;
                        stepper_set_speed(motor, motor);
                    } else if (out < 0.0f) {
                        out = -405.0f - (5500.0f / (out - 9.0f));
                        int16_t motor = -400 - (int16_t)out;
                        stepper_set_speed(motor, motor);
                    } else {
                        stepper_set_speed(0, 0);
                    }
                }
            }
            break;

        case STATE_NGA:
            if (btn == BUTTON_EVENT_PRESSED) {
                current_state = STATE_CHO_NUT;
                start_beep_seq(now_ms, 1, 100, 0, 0);
            }
            break;
    }

    process_beep_seq(now_ms);
}
