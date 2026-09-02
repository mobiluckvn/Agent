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
    """
    with open("mock_deps.c", "w") as f:
        f.write(mock_c)
    
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", 
           "-I/Users/v/Documents/KTDT/packs/avr/hostmock",
           "src/app_balance.c", "mock_deps.c"]
    
    if os.path.exists("/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"):
        cmd.append("/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c")
        
    cmd.extend(["-o", "libapp.so"])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr)
        pytest.fail("Compilation failed")

def test_app_flow():
    lib = ctypes.CDLL("./libapp.so")
    
    lib.app_init.argtypes = []
    lib.app_init.restype = None
    lib.app_step.argtypes = []
    lib.app_step.restype = None
    
    # 1. Init calls
    lib.app_init()
    assert ctypes.c_int.in_dll(lib, "imu_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "stepper_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_init_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "button_init_calls").value == 1
    
    # 2. CHO_NUT state
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "i2c_tick_calls").value == 1
    
    # 3. Button -> HIEU_CHINH
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_begin_calls").value == 1
    
    # 4. HIEU_CHINH beeps
    ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value = 0
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = True
    for _ in range(450): # 1800ms
        lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 5
    
    # 5. Calibrate commit -> SAN_SANG
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = False
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "imu_calibrate_commit_calls").value == 1
    
    # 6. SAN_SANG beeps
    ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value = 0
    for _ in range(200): # 800ms
        lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 2
    
    # 7. CAN_BANG state
    ctypes.c_int.in_dll(lib, "pid_compute_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "pid_compute_calls").value == 1
    
    # 8. Angle > 30 -> NGA
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 35.0
    ctypes.c_int.in_dll(lib, "stepper_set_speed_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "stepper_set_speed_calls").value > 0
    
    # 9. NGA state, angle back to 0 does not restart
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 0.0
    ctypes.c_int.in_dll(lib, "pid_compute_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "pid_compute_calls").value == 0
    
    # 10. Button -> CHO_NUT
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    
    # 11. Missing samples -> NGA
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1 # to HIEU_CHINH
    lib.app_step()
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = False
    lib.app_step() # to SAN_SANG
    for _ in range(200): lib.app_step() # to CAN_BANG
    
    ctypes.c_int.in_dll(lib, "imu_update_calls").value = 0
    ctypes.c_bool.in_dll(lib, "mock_imu_update_return").value = False
    for _ in range(10):
        lib.app_step()
    
    assert ctypes.c_int.in_dll(lib, "imu_update_calls").value >= 20000
    
    ctypes.c_int.in_dll(lib, "pid_compute_calls").value = 0
    lib.app_step()
    assert ctypes.c_int.in_dll(lib, "pid_compute_calls").value == 0 # In NGA
    
    # 12. HIEU_CHINH timeout -> NGA
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1 # to CHO_NUT
    lib.app_step()
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1 # to HIEU_CHINH
    lib.app_step()
    
    ctypes.c_bool.in_dll(lib, "mock_calibrate_busy").value = True
    ctypes.c_bool.in_dll(lib, "mock_imu_update_return").value = True
    for _ in range(2600): # 10400 ms
        lib.app_step()
    
    # Should be in NGA now, with error beeps
    ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value = 0
    for _ in range(250): # 1000 ms
        lib.app_step()
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_async_calls").value == 3
