
#include <stdbool.h>
#include <stdint.h>

bool mock_imu_update_ret = true;
int imu_update_calls = 0;
float mock_tilt_angle = 0.0f;
bool mock_calib_busy = false;
int imu_calib_begin_calls = 0;
int imu_calib_commit_calls = 0;

void imu_init(void) {}
bool imu_update(void) {
    imu_update_calls++;
    return mock_imu_update_ret;
}
float imu_get_tilt_angle(void) { return mock_tilt_angle; }
void imu_calibrate_begin(void) { imu_calib_begin_calls++; mock_calib_busy = true; }
bool imu_calibrate_busy(void) { return mock_calib_busy; }
void imu_calibrate_commit(void) { imu_calib_commit_calls++; }

float mock_pid_out = 0.0f;
bool last_pid_running = false;
void pid_set_tunings(float kp, float ki, float kd) {}
float pid_compute(float angle, float pid_setpoint, bool is_running) {
    last_pid_running = is_running;
    return mock_pid_out;
}

int16_t last_speed_left = 0;
int16_t last_speed_right = 0;
void stepper_init(void) {}
void stepper_set_speed(int16_t speed_left, int16_t speed_right) {
    last_speed_left = speed_left;
    last_speed_right = speed_right;
}

int buzzer_beep_calls = 0;
uint32_t last_beep_duration = 0;
void buzzer_init(void) {}
void buzzer_beep_async(uint32_t current_time_ms, uint32_t duration_ms) {
    buzzer_beep_calls++;
    last_beep_duration = duration_ms;
}
void buzzer_update(uint32_t current_time_ms) {}
void buzzer_stop(void) {}

int mock_button_event = 0;
void button_init(void) {}
int button_get_event(uint32_t current_time_ms) {
    int ev = mock_button_event;
    mock_button_event = 0;
    return ev;
}

int i2c_tick_calls = 0;
void i2c_tick(void) {
    i2c_tick_calls++;
}
