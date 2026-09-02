#include "app_balance.h"
#include "drv_imu.h"
#include "logic_pid.h"
#include "drv_stepper.h"
#include "drv_buzzer.h"
#include "drv_button.h"

#define CALIB_TIMEOUT_MS 10000
#define IMU_PUMP_LIMIT 20000

typedef enum {
    STATE_CHO_NUT,
    STATE_HIEU_CHINH,
    STATE_SAN_SANG,
    STATE_CAN_BANG,
    STATE_NGA
} app_state_t;

static uint32_t now_ms = 0;
static app_state_t state = STATE_CHO_NUT;
static uint32_t state_timer = 0;
static uint8_t beep_step = 0;
static uint32_t beep_timer = 0;
static uint8_t missing_samples = 0;

extern void i2c_tick(void);

void app_init(void) {
    imu_init();
    stepper_init();
    buzzer_init();
    button_init();
}

void app_step(void) {
    now_ms += 4;
    i2c_tick();

    bool got_sample = false;
    for (uint16_t i = 0; i < IMU_PUMP_LIMIT; i++) {
        if (imu_update()) {
            got_sample = true;
            break;
        }
    }

    if (!got_sample) {
        missing_samples++;
        if (missing_samples >= 10) {
            if (state != STATE_NGA) {
                stepper_set_speed(0, 0);
                pid_compute(0.0f, 0.0f, false);
                state = STATE_NGA;
                beep_step = 0;
            }
        }
    } else {
        missing_samples = 0;
    }

    buzzer_update(now_ms);
    button_event_t btn = button_get_event(now_ms);

    switch (state) {
        case STATE_CHO_NUT:
            if (beep_step == 0) {
                buzzer_beep_async(now_ms, 100);
                beep_step = 1;
            }
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_HIEU_CHINH;
                state_timer = now_ms;
                beep_step = 0;
                beep_timer = now_ms - 400; // Kích hoạt bíp đầu tiên ngay lập tức
                imu_calibrate_begin();
            }
            break;

        case STATE_HIEU_CHINH:
            if (beep_step < 5) {
                if (now_ms - beep_timer >= 400) {
                    buzzer_beep_async(now_ms, 100);
                    beep_timer = now_ms;
                    beep_step++;
                }
            }
            
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_CHO_NUT;
                beep_step = 0;
                missing_samples = 0;
                break;
            }

            if (!imu_calibrate_busy()) {
                imu_calibrate_commit();
                state = STATE_SAN_SANG;
                beep_step = 0;
                beep_timer = now_ms;
            } else if (now_ms - state_timer > CALIB_TIMEOUT_MS) {
                state = STATE_NGA;
                beep_step = 10; // Mã bíp lỗi
                beep_timer = now_ms;
            }
            break;

        case STATE_SAN_SANG:
            if (beep_step == 0) {
                buzzer_beep_async(now_ms, 100);
                beep_timer = now_ms;
                beep_step = 1;
            } else if (beep_step == 1 && now_ms - beep_timer >= 200) {
                buzzer_beep_async(now_ms, 100);
                beep_timer = now_ms;
                beep_step = 2;
            } else if (beep_step == 2 && now_ms - beep_timer >= 500) {
                state = STATE_CAN_BANG;
            }
            break;

        case STATE_CAN_BANG:
            if (got_sample) {
                float angle = imu_get_tilt_angle();
                if (angle > 30.0f || angle < -30.0f) {
                    stepper_set_speed(0, 0);
                    pid_compute(angle, 0.0f, false);
                    state = STATE_NGA;
                    beep_step = 0;
                } else {
                    float out = pid_compute(angle, 0.0f, true);
                    float comp = 0.0f;
                    int16_t motor = 0;
                    if (out > 0.0f) {
                        comp = 405.0f - (5500.0f / (out + 9.0f));
                        motor = 400 - (int16_t)comp;
                    } else if (out < 0.0f) {
                        comp = -(405.0f - (5500.0f / (-out + 9.0f)));
                        motor = -400 - (int16_t)comp;
                    }
                    stepper_set_speed(motor, motor);
                }
            }
            break;

        case STATE_NGA:
            if (beep_step == 10) {
                uint32_t seq_time = (now_ms - beep_timer) % 1000;
                if (seq_time == 0) buzzer_beep_async(now_ms, 50);
                else if (seq_time == 100) buzzer_beep_async(now_ms, 50);
                else if (seq_time == 200) buzzer_beep_async(now_ms, 50);
            }
            if (btn == BUTTON_EVENT_PRESSED) {
                state = STATE_CHO_NUT;
                beep_step = 0;
                missing_samples = 0;
            }
            break;
    }
}

void app_tick(void) {
    app_step();
}
