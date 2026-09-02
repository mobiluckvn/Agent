import os
import subprocess
import ctypes
import pytest

def setup_module(module):
    mock_src = """
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
"""
    with open("mock.c", "w") as f:
        f.write(mock_src)
    
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", "-o", "libapp.so", "src/app_balance.c", "mock.c"]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        pytest.fail("Compilation failed")
    
    global lib
    lib = ctypes.CDLL("./libapp.so")
    
    lib.app_init.argtypes = []
    lib.app_init.restype = None
    lib.app_step.argtypes = []
    lib.app_step.restype = None

def get_var(name, ctype):
    return ctype.in_dll(lib, name)

def test_full_flow():
    get_var("i2c_tick_call_count", ctypes.c_int).value = 0
    get_var("buzzer_beep_async_call_count", ctypes.c_int).value = 0
    get_var("imu_calibrate_begin_call_count", ctypes.c_int).value = 0
    get_var("imu_calibrate_commit_call_count", ctypes.c_int).value = 0
    get_var("pid_compute_call_count", ctypes.c_int).value = 0
    get_var("stepper_set_speed_call_count", ctypes.c_int).value = 0
    
    # 1. Init
    lib.app_init()
    assert get_var("buzzer_beep_async_call_count", ctypes.c_int).value == 1
    
    # 2. CHO_NUT -> HIEU_CHINH
    get_var("button_event", ctypes.c_int).value = 1
    lib.app_step()
    assert get_var("imu_calibrate_begin_call_count", ctypes.c_int).value == 1
    
    # 3. HIEU_CHINH (5 beeps)
    get_var("imu_calibrate_busy_return", ctypes.c_bool).value = True
    beep_count_before = get_var("buzzer_beep_async_call_count", ctypes.c_int).value
    for _ in range(400):
        lib.app_step()
    
    beep_count_after = get_var("buzzer_beep_async_call_count", ctypes.c_int).value
    assert beep_count_after - beep_count_before == 5
    
    # 4. HIEU_CHINH -> SAN_SANG
    get_var("imu_calibrate_busy_return", ctypes.c_bool).value = False
    lib.app_step()
    assert get_var("imu_calibrate_commit_call_count", ctypes.c_int).value == 1
    
    # 5. SAN_SANG (2 beeps)
    beep_count_before = get_var("buzzer_beep_async_call_count", ctypes.c_int).value
    for _ in range(120):
        lib.app_step()
    beep_count_after = get_var("buzzer_beep_async_call_count", ctypes.c_int).value
    assert beep_count_after - beep_count_before == 2
    
    # 6. CAN_BANG
    pid_count_before = get_var("pid_compute_call_count", ctypes.c_int).value
    lib.app_step()
    pid_count_after = get_var("pid_compute_call_count", ctypes.c_int).value
    assert pid_count_after > pid_count_before
    
    # 7. Fall (> 30 degrees)
    get_var("imu_tilt_angle", ctypes.c_float).value = 35.0
    lib.app_step()
    assert get_var("stepper_speed_left", ctypes.c_int16).value == 0
    assert get_var("stepper_speed_right", ctypes.c_int16).value == 0
    assert get_var("pid_compute_is_running", ctypes.c_bool).value == False
    
    # 8. NGA -> CHO_NUT
    get_var("imu_tilt_angle", ctypes.c_float).value = 0.0
    lib.app_step()
    pid_count_before = get_var("pid_compute_call_count", ctypes.c_int).value
    lib.app_step()
    assert get_var("pid_compute_call_count", ctypes.c_int).value == pid_count_before
    
    get_var("button_event", ctypes.c_int).value = 1
    beep_count_before = get_var("buzzer_beep_async_call_count", ctypes.c_int).value
    lib.app_step()
    assert get_var("buzzer_beep_async_call_count", ctypes.c_int).value == beep_count_before + 1

def test_missed_samples():
    lib.app_init()
    get_var("button_event", ctypes.c_int).value = 1
    lib.app_step()
    get_var("imu_calibrate_busy_return", ctypes.c_bool).value = False
    lib.app_step()
    for _ in range(120):
        lib.app_step()
    
    get_var("imu_update_return", ctypes.c_bool).value = False
    for _ in range(24):
        lib.app_step()
    
    lib.app_step()
    assert get_var("stepper_speed_left", ctypes.c_int16).value == 0
    assert get_var("pid_compute_is_running", ctypes.c_bool).value == False

def test_i2c_tick_and_pump():
    lib.app_init()
    i2c_before = get_var("i2c_tick_call_count", ctypes.c_int).value
    imu_before = get_var("imu_update_call_count", ctypes.c_int).value
    
    get_var("imu_update_return", ctypes.c_bool).value = True
    lib.app_step()
    
    assert get_var("i2c_tick_call_count", ctypes.c_int).value == i2c_before + 1
    assert get_var("imu_update_call_count", ctypes.c_int).value == imu_before + 1
    
    get_var("imu_update_return", ctypes.c_bool).value = False
    imu_before = get_var("imu_update_call_count", ctypes.c_int).value
    lib.app_step()
    assert get_var("imu_update_call_count", ctypes.c_int).value == imu_before + 129

def test_nonlinear_compensation():
    lib.app_init()
    get_var("button_event", ctypes.c_int).value = 1
    lib.app_step()
    get_var("imu_calibrate_busy_return", ctypes.c_bool).value = False
    lib.app_step()
    for _ in range(120):
        lib.app_step()
    
    get_var("imu_update_return", ctypes.c_bool).value = True
    get_var("imu_tilt_angle", ctypes.c_float).value = 0.0
    
    get_var("pid_compute_return", ctypes.c_float).value = 1.0
    lib.app_step()
    assert get_var("stepper_speed_left", ctypes.c_int16).value == 545
    
    get_var("pid_compute_return", ctypes.c_float).value = -1.0
    lib.app_step()
    assert get_var("stepper_speed_left", ctypes.c_int16).value == -545
