import os
import ctypes
import subprocess
import pytest

@pytest.fixture(scope="module")
def lib():
    mock_c = """
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
    int buzzer_beep_calls = 0;

    bool mock_imu_update_return = true;
    int mock_imu_update_true_at = 1;
    float mock_tilt_angle = 0.0f;
    bool mock_calibrate_busy = false;
    int mock_button_event = 0;
    float mock_pid_out = 0.0f;
    int last_stepper_left = 0;
    int last_stepper_right = 0;

    void imu_init(void) { imu_init_calls++; }
    void stepper_init(void) { stepper_init_calls++; }
    void buzzer_init(void) { buzzer_init_calls++; }
    void button_init(void) { button_init_calls++; }
    void i2c_tick(void) { i2c_tick_calls++; }

    bool imu_update(void) {
        imu_update_calls++;
        if (imu_update_calls >= mock_imu_update_true_at) {
            return mock_imu_update_return;
        }
        return false;
    }

    float imu_get_tilt_angle(void) { return mock_tilt_angle; }
    void imu_calibrate_begin(void) { imu_calibrate_begin_calls++; }
    bool imu_calibrate_busy(void) { return mock_calibrate_busy; }
    void imu_calibrate_commit(void) { imu_calibrate_commit_calls++; }

    void pid_set_tunings(float kp, float ki, float kd) {}
    float pid_compute(float angle, float pid_setpoint, bool is_running) {
        pid_compute_calls++;
        return mock_pid_out;
    }

    void stepper_set_speed(int16_t speed_left, int16_t speed_right) {
        stepper_set_speed_calls++;
        last_stepper_left = speed_left;
        last_stepper_right = speed_right;
    }

    void buzzer_beep_async(uint32_t current_time_ms, uint32_t duration_ms) {
        buzzer_beep_calls++;
    }
    void buzzer_update(uint32_t current_time_ms) {}
    void buzzer_stop(void) {}

    int button_get_event(uint32_t current_time_ms) {
        int ev = mock_button_event;
        mock_button_event = 0;
        return ev;
    }
    """
    with open("mock_deps.c", "w") as f:
        f.write(mock_c)

    cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        "-I/Users/v/Documents/KTDT/packs/avr/hostmock",
        "src/app_balance.c",
        "mock_deps.c",
        "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c",
        "-o", "libapp_balance.so"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr)
        pytest.fail("Compilation failed")

    lib = ctypes.CDLL("./libapp_balance.so")
    lib.app_init.argtypes = []
    lib.app_init.restype = None
    lib.app_step.argtypes = []
    lib.app_step.restype = None
    return lib

def test_app_balance(lib):
    # 1. app_init calls 4 init functions
    lib.app_init()
    assert ctypes.c_int.in_dll(lib, "imu_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "stepper_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "button_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 1 # CHO_NUT beep

    # 2. i2c_tick called exactly once per step
    ctypes.c_int.in_dll(lib, "i2c_tick_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "i2c_tick_calls").value == 1

    # 3. Pump imu_update
    ctypes.c_int.in_dll(lib, "imu_update_calls").value = 0
    ctypes.c_int.in_dll(lib, "mock_imu_update_true_at").value = 5
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_update_calls").value == 5

    # 4. Max iterations reached, no PID call
    ctypes.c_int.in_dll(lib, "imu_update_calls").value = 0
    ctypes.c_bool.in_dll(lib, "mock_imu_update_return").value = False
    ctypes.c_int.in_dll(lib, "pid_compute_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_update_calls").value == 129
    assert ctypes.c_int.in_dll(lib, "pid_compute_calls").value == 0
    ctypes.c_bool.in_dll(lib, "mock_imu_update_return").value = True
    ctypes.c_int.in_dll(lib, "mock_imu_update_true_at").value = 1

    # 5. Button in CHO_NUT -> HIEU_CHINH
    ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value = 0
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_begin_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 1 # First beep of 5

    # 6. Button in HIEU_CHINH -> CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    # Now in CHO_NUT again. Go back to HIEU_CHINH
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_begin_calls").value == 2

    # 7. Calibration timeout -> beep error and go to NGA
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = True
    for _ in range(2500): # 10000ms / 4ms = 2500 steps
        lib.app_step()
    # Next step should trigger timeout
    ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 1 # First beep of 3 short

    # 8. Button in NGA -> CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    
    # Go to HIEU_CHINH again
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()

    # 9. SAN_SANG only after imu_calibrate_commit()
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = False
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_commit_calls").value == 1

    # Wait for SAN_SANG to finish (1000ms = 250 steps)
    for _ in range(250):
        lib.app_step()

    # 10. |angle| > 30 -> stepper_set_speed(0, 0) and NGA
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 35.0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "last_stepper_left").value == 0
    assert ctypes.c_int.in_dll(lib, "last_stepper_right").value == 0

    # 11. In NGA, angle to 0 does NOT restart
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 0.0
    ctypes.c_int.in_dll(lib, "pid_compute_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "pid_compute_calls").value == 0

    # 12. Missing samples N consecutive -> stepper_set_speed(0, 0) and NGA
    # First get back to CAN_BANG
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step() # CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step() # HIEU_CHINH
    lib.app_step() # commit -> SAN_SANG
    for _ in range(250):
        lib.app_step() # wait SAN_SANG -> CAN_BANG
    
    ctypes.c_bool.in_dll(lib, "mock_imu_update_return").value = False
    for _ in range(10):
        lib.app_step()
    assert ctypes.c_int.in_dll(lib, "last_stepper_left").value == 0
