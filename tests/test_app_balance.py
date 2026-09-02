import os
import subprocess
import ctypes
import pytest

def setup_module():
    mock_c = """
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
    """
    os.makedirs("tests", exist_ok=True)
    with open("tests/mock_deps.c", "w") as f:
        f.write(mock_c)

    cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        "-Isrc",
        "src/app_balance.c",
        "tests/mock_deps.c"
    ]
    
    # Include eaa_io_space.c if it exists in the environment
    io_space_path = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    if os.path.exists(io_space_path):
        cmd.append("-I/Users/v/Documents/KTDT/packs/avr/hostmock")
        cmd.append(io_space_path)
        
    cmd.extend(["-o", "tests/libapp.so"])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr)
        pytest.fail("Compilation failed")

def test_app_balance():
    lib = ctypes.CDLL("./tests/libapp.so")
    
    lib.app_init.argtypes = []
    lib.app_init.restype = None
    lib.app_step.argtypes = []
    lib.app_step.restype = None

    # 1. Init
    lib.app_init()
    assert ctypes.c_int.in_dll(lib, "imu_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "stepper_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "button_init_calls").value == 1

    # 2. First step -> CHO_NUT, 1 beep
    ctypes.c_bool.in_dll(lib, "mock_imu_update_ret").value = True
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 1

    # 3. Button -> HIEU_CHINH, 5 beeps
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = True
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_begin_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 2

    # 4. Calib timeout -> NGA, 3 beeps
    calls_before = ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value
    for _ in range(2501):
        lib.app_step()
    calls_after = ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value
    assert calls_after > calls_before

    # 5. Recover to CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()

    # 6. Button -> HIEU_CHINH again
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = True
    lib.app_step()

    # 7. Calib success -> SAN_SANG, 2 beeps
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = False
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_commit_calls").value == 1

    # 8. SAN_SANG -> CAN_BANG
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 1.0
    lib.app_step()
    
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 0.4
    lib.app_step()

    # 9. CAN_BANG logic
    ctypes.c_float.in_dll(lib, "mock_pid_out").value = 10.0
    lib.app_step()
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == True
    left = ctypes.c_int16.in_dll(lib, "last_stepper_left").value
    assert left in [284, 285]

    # 10. Fall detection
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 31.0
    lib.app_step()
    assert ctypes.c_int16.in_dll(lib, "last_stepper_left").value == 0
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == False

    # 11. Recover to CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()

    # 12. Missed samples
    ctypes.c_bool.in_dll(lib, "mock_imu_update_ret").value = False
    for _ in range(10):
        lib.app_step()
    
    assert ctypes.c_int16.in_dll(lib, "last_stepper_left").value == 0
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == False
