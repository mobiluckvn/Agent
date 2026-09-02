
#include <stdbool.h>
#include <stdint.h>

int i2c_tick_call_count = 0;
void i2c_tick(void) { i2c_tick_call_count++; }

int imu_update_call_count = 0;
bool imu_update_return = true;
bool imu_update(void) { imu_update_call_count++; return imu_update_return; }

float imu_tilt_angle = 0.0f;
float imu_get_tilt_angle(void) { return imu_tilt_angle; }

int imu_calibrate_begin_call_count = 0;
void imu_calibrate_begin(void) { imu_calibrate_begin_call_count++; }

bool imu_calibrate_busy_return = false;
bool imu_calibrate_busy(void) { return imu_calibrate_busy_return; }

int imu_calibrate_commit_call_count = 0;
void imu_calibrate_commit(void) { imu_calibrate_commit_call_count++; }

int pid_compute_call_count = 0;
float pid_compute_return = 0.0f;
bool pid_compute_is_running = true;
float pid_compute(float angle, float pid_setpoint, bool is_running) {
    pid_compute_call_count++;
    pid_compute_is_running = is_running;
    return pid_compute_return;
}

int stepper_set_speed_call_count = 0;
int16_t stepper_speed_left = 0;
int16_t stepper_speed_right = 0;
void stepper_set_speed(int16_t speed_left, int16_t speed_right) {
    stepper_set_speed_call_count++;
    stepper_speed_left = speed_left;
    stepper_speed_right = speed_right;
}

int buzzer_beep_async_call_count = 0;
void buzzer_beep_async(uint32_t current_time_ms, uint32_t duration_ms) {
    buzzer_beep_async_call_count++;
}

int button_event = 0;
int button_get_event(uint32_t current_time_ms) {
    int ev = button_event;
    button_event = 0;
    return ev;
}

void imu_init(void) {}
void stepper_init(void) {}
void buzzer_init(void) {}
void button_init(void) {}
void buzzer_update(uint32_t current_time_ms) {}
