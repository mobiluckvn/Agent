import os
import subprocess
import ctypes
import pytest

def setup_module(module):
    mock_src = """
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
"""
    os.makedirs("tests", exist_ok=True)
    with open("tests/mock_deps.c", "w") as f:
        f.write(mock_src)
    
    cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        "src/app_balance.c",
        "tests/mock_deps.c",
        "-Isrc",
        "-o", "tests/libapp.so"
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        pytest.fail("Compilation failed")

@pytest.fixture
def lib():
    lib = ctypes.CDLL("./tests/libapp.so")
    lib.app_init.argtypes = []
    lib.app_init.restype = None
    lib.app_step.argtypes = []
    lib.app_step.restype = None
    lib.app_tick.argtypes = []
    lib.app_tick.restype = None
    
    ctypes.c_int.in_dll(lib, "imu_update_calls").value = 0
    ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value = 0
    ctypes.c_int.in_dll(lib, "i2c_tick_calls").value = 0
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 0
    ctypes.c_bool.in_dll(lib, "mock_imu_update_ret").value = True
    ctypes.c_int.in_dll(lib, "imu_calib_begin_calls").value = 0
    ctypes.c_int.in_dll(lib, "imu_calib_commit_calls").value = 0
    
    lib.app_init()
    return lib

def test_initial_state(lib):
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 1
    for _ in range(10):
        lib.app_step()
    assert ctypes.c_int.in_dll(lib, "i2c_tick_calls").value == 10
    assert ctypes.c_int.in_dll(lib, "imu_update_calls").value == 10

def test_state_transitions(lib):
    ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value = 0
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    
    assert ctypes.c_int.in_dll(lib, "imu_calib_begin_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 1
    
    ctypes.c_bool.in_dll(lib, "mock_calib_busy").value = True
    for _ in range(350):
        lib.app_step()
    
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 5
    
    ctypes.c_bool.in_dll(lib, "mock_calib_busy").value = False
    lib.app_step()
    
    assert ctypes.c_int.in_dll(lib, "imu_calib_commit_calls").value == 1
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 6
    
    for _ in range(60):
        lib.app_step()
        
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value == 7
    
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 10.0
    ctypes.c_float.in_dll(lib, "mock_pid_out").value = 50.0
    lib.app_step()
    
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == True
    motor_left = ctypes.c_int16.in_dll(lib, "last_speed_left").value
    assert 87 <= motor_left <= 89

def test_fall_condition(lib):
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    ctypes.c_bool.in_dll(lib, "mock_calib_busy").value = False
    lib.app_step()
    for _ in range(60): lib.app_step()
    
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 35.0
    lib.app_step()
    
    assert ctypes.c_int16.in_dll(lib, "last_speed_left").value == 0
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == False
    
    ctypes.c_float.in_dll(lib, "mock_tilt_angle").value = 0.0
    ctypes.c_float.in_dll(lib, "mock_pid_out").value = 10.0
    lib.app_step()
    
    assert ctypes.c_int16.in_dll(lib, "last_speed_left").value == 0
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == False

def test_calib_timeout(lib):
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    
    ctypes.c_bool.in_dll(lib, "mock_calib_busy").value = True
    ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value = 0
    
    for _ in range(2501):
        lib.app_step()
        
    for _ in range(200):
        lib.app_step()
        
    assert ctypes.c_int.in_dll(lib, "buzzer_beep_calls").value >= 3

def test_missed_samples(lib):
    ctypes.c_int.in_dll(lib, "mock_button_event").value = 1
    lib.app_step()
    ctypes.c_bool.in_dll(lib, "mock_calib_busy").value = False
    lib.app_step()
    for _ in range(60): lib.app_step()
    
    ctypes.c_float.in_dll(lib, "mock_pid_out").value = 10.0
    lib.app_step()
    assert ctypes.c_int16.in_dll(lib, "last_speed_left").value != 0
    
    ctypes.c_bool.in_dll(lib, "mock_imu_update_ret").value = False
    for _ in range(9):
        lib.app_step()
        
    lib.app_step()
    
    assert ctypes.c_int16.in_dll(lib, "last_speed_left").value == 0
    assert ctypes.c_bool.in_dll(lib, "last_pid_running").value == False

def test_imu_pump_limit(lib):
    ctypes.c_int.in_dll(lib, "imu_update_calls").value = 0
    ctypes.c_bool.in_dll(lib, "mock_imu_update_ret").value = False
    
    lib.app_step()
    
    assert ctypes.c_int.in_dll(lib, "imu_update_calls").value == 1600

def test_app_tick(lib):
    lib.app_tick()
