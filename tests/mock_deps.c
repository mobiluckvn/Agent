
    #include <stdbool.h>
    #include <stdint.h>

    int imu_init_calls = 0;
    int stepper_init_calls = 0;
    int buzzer_init_calls = 0;
    int button_init_calls = 0;

    void imu_init(void) { imu_init_calls++; }
    void stepper_init(void) { stepper_init_calls++; }
    void buzzer_init(void) { buzzer_init_calls++; }
    void button_init(void) { button_init_calls++; }

    bool mock_imu_update_ret = true;
    int imu_update_calls = 0;
    bool imu_update(void) {
        imu_update_calls++;
        return mock_imu_update_ret;
    }

    float mock_tilt_angle = 0.0f;
    float imu_get_tilt_angle(void) { return mock_tilt_angle; }

    int imu_calibrate_begin_calls = 0;
    void imu_calibrate_begin(void) { imu_calibrate_begin_calls++; }

    bool mock_calibrate_busy = false;
    bool imu_calibrate_busy(void) { return mock_calibrate_busy; }

    int imu_calibrate_commit_calls = 0;
    void imu_calibrate_commit(void) { imu_calibrate_commit_calls++; }

    float mock_pid_out = 0.0f;
    int pid_compute_calls = 0;
    bool last_pid_running = false;
    float pid_compute(float angle, float setpoint, bool is_running) {
        pid_compute_calls++;
        last_pid_running = is_running;
        return mock_pid_out;
    }

    int stepper_set_speed_calls = 0;
    int16_t last_stepper_left = 0;
    int16_t last_stepper_right = 0;
    void stepper_set_speed(int16_t left, int16_t right) {
        stepper_set_speed_calls++;
        last_stepper_left = left;
        last_stepper_right = right;
    }

    int buzzer_beep_async_calls = 0;
    uint32_t last_beep_duration = 0;
    void buzzer_beep_async(uint32_t current_time_ms, uint32_t duration_ms) {
        buzzer_beep_async_calls++;
        last_beep_duration = duration_ms;
    }

    void buzzer_update(uint32_t current_time_ms) {}
    void buzzer_stop(void) {}

    int mock_button_event = 0;
    int button_get_event(uint32_t current_time_ms) {
        int ev = mock_button_event;
        mock_button_event = 0;
        return ev;
    }

    int i2c_tick_calls = 0;
    void i2c_tick(void) { i2c_tick_calls++; }
    