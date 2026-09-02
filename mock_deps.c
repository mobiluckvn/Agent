
    #include <stdbool.h>
    #include <stdint.h>

    int imu_init_calls = 0;
    int stepper_init_calls = 0;
    int buzzer_init_calls = 0;
    int button_init_calls = 0;
    int i2c_tick_calls = 0;
    int imu_update_calls = 0;
    int imu_calibrate_begin_calls = 0;
    int imu_calibrate_commit_calls = 0;
    int pid_compute_calls = 0;
    int stepper_set_speed_calls = 0;
    int buzzer_beep_async_calls = 0;
    int buzzer_update_calls = 0;

    bool mock_imu_update_return = true;
    float mock_tilt_angle = 0.0f;
    bool mock_calibrate_busy = false;
    float mock_pid_compute_return = 0.0f;
    int mock_button_event = 0;

    void imu_init(void) { imu_init_calls++; }
    void stepper_init(void) { stepper_init_calls++; }
    void buzzer_init(void) { buzzer_init_calls++; }
    void button_init(void) { button_init_calls++; }
    void i2c_tick(void) { i2c_tick_calls++; }

    bool imu_update(void) {
        imu_update_calls++;
        return mock_imu_update_return;
    }
    float imu_get_tilt_angle(void) { return mock_tilt_angle; }
    void imu_calibrate_begin(void) { imu_calibrate_begin_calls++; }
    bool imu_calibrate_busy(void) { return mock_calibrate_busy; }
    void imu_calibrate_commit(void) { imu_calibrate_commit_calls++; }

    void pid_set_tunings(float kp, float ki, float kd) {}
    float pid_compute(float angle, float pid_setpoint, bool is_running) {
        pid_compute_calls++;
        return mock_pid_compute_return;
    }

    void stepper_set_speed(int16_t speed_left, int16_t speed_right) {
        stepper_set_speed_calls++;
    }

    void buzzer_beep_async(uint32_t current_time_ms, uint32_t duration_ms) {
        buzzer_beep_async_calls++;
    }
    void buzzer_update(uint32_t current_time_ms) {
        buzzer_update_calls++;
    }
    void buzzer_stop(void) {}

    int button_get_event(uint32_t current_time_ms) {
        int ev = mock_button_event;
        mock_button_event = 0; // auto clear
        return ev;
    }
    