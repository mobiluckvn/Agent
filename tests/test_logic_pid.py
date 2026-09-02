import os
import ctypes
import pytest
import subprocess

def compile_module():
    src = "src/logic_pid.c"
    lib = "test_logic_pid.so"
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", "-o", lib, src]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"Compilation failed:\n{result.stderr}")
    return lib

@pytest.fixture(scope="module")
def pid_lib():
    lib_path = compile_module()
    lib = ctypes.CDLL(f"./{lib_path}")
    
    lib.pid_set_tunings.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
    lib.pid_set_tunings.restype = None
    
    lib.pid_compute.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_bool]
    lib.pid_compute.restype = ctypes.c_float
    
    lib.pid_get_self_balance_setpoint.argtypes = []
    lib.pid_get_self_balance_setpoint.restype = ctypes.c_float
    
    lib.pid_get_i_mem.argtypes = []
    lib.pid_get_i_mem.restype = ctypes.c_float
    
    lib.pid_get_last_d_error.argtypes = []
    lib.pid_get_last_d_error.restype = ctypes.c_float
    
    lib.pid_reset_state_for_test.argtypes = []
    lib.pid_reset_state_for_test.restype = None
    
    return lib

@pytest.fixture(autouse=True)
def reset_pid_state(pid_lib):
    pid_lib.pid_reset_state_for_test()

def test_pid_clamp_and_deadband(pid_lib):
    pid_lib.pid_set_tunings(12.0, 0.4, 10.0)
    
    # Test deadband: small angle
    out = pid_lib.pid_compute(0.1, 0.0, True)
    assert out == 0.0
    
    # Test output clamp
    out = pid_lib.pid_compute(20.0, 0.0, True)
    assert out == 400.0
    
def test_integral_clamp(pid_lib):
    pid_lib.pid_set_tunings(0.0, 100.0, 0.0)
    
    out = pid_lib.pid_compute(10.0, 0.0, True)
    assert pid_lib.pid_get_i_mem() == 400.0
    
    out = pid_lib.pid_compute(-20.0, 0.0, True)
    assert pid_lib.pid_get_i_mem() == -400.0

def test_stop_clears_state(pid_lib):
    pid_lib.pid_set_tunings(12.0, 0.4, 10.0)
    
    pid_lib.pid_compute(10.0, 0.0, True)
    assert pid_lib.pid_get_i_mem() != 0.0
    
    out = pid_lib.pid_compute(10.0, 0.0, False)
    assert out == 0.0
    assert pid_lib.pid_get_i_mem() == 0.0

def test_angle_exceeds_30_stops(pid_lib):
    pid_lib.pid_set_tunings(12.0, 0.4, 10.0)
    
    out = pid_lib.pid_compute(31.0, 0.0, True)
    assert out == 0.0
    assert pid_lib.pid_get_i_mem() == 0.0
    
    # Should not auto-restart even if angle is back to normal
    out = pid_lib.pid_compute(10.0, 0.0, True)
    assert out == 0.0

def test_change_tunings_midway(pid_lib):
    pid_lib.pid_set_tunings(12.0, 0.4, 10.0)
    
    pid_lib.pid_compute(10.0, 0.0, True)
    i_mem_before = pid_lib.pid_get_i_mem()
    d_error_before = pid_lib.pid_get_last_d_error()
    
    # Change tunings
    pid_lib.pid_set_tunings(15.0, 0.5, 12.0)
    
    # I_mem and last_d_error should not be cleared
    assert pid_lib.pid_get_i_mem() == i_mem_before
    assert pid_lib.pid_get_last_d_error() == d_error_before

def test_self_balance_setpoint(pid_lib):
    pid_lib.pid_set_tunings(12.0, 0.4, 10.0)
    
    sb_before = pid_lib.pid_get_self_balance_setpoint()
    
    # Force a negative output
    out = pid_lib.pid_compute(-10.0, 0.0, True)
    assert out < 0.0
    
    sb_after = pid_lib.pid_get_self_balance_setpoint()
    assert sb_after > sb_before # Should increase by 0.0015
    assert abs(sb_after - (sb_before + 0.0015)) < 1e-6
    
    # Force a positive output
    out = pid_lib.pid_compute(10.0, 0.0, True)
    assert out > 0.0
    
    sb_after2 = pid_lib.pid_get_self_balance_setpoint()
    assert sb_after2 < sb_after # Should decrease by 0.0015
    assert abs(sb_after2 - (sb_after - 0.0015)) < 1e-6
