import os
import subprocess
import ctypes
import pytest

lib = None

def setup_module(module):
    global lib
    src_file = "src/drv_button.c"
    lib_file = "drv_button.so"
    
    compile_cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", "-o", lib_file, src_file]
    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"Compilation failed:\n{result.stderr}")
        
    lib = ctypes.CDLL(f"./{lib_file}")
    
    lib.button_init.argtypes = []
    lib.button_init.restype = None
    
    lib.button_get_event.argtypes = [ctypes.c_uint32]
    lib.button_get_event.restype = ctypes.c_int
    
    lib.button_set_raw_pin_level.argtypes = [ctypes.c_uint8]
    lib.button_set_raw_pin_level.restype = None
    
    lib.button_init()

def test_debounce_press():
    # Initial state (released, level = 1)
    lib.button_set_raw_pin_level(1)
    assert lib.button_get_event(0) == 0
    
    # Press button (level = 0)
    lib.button_set_raw_pin_level(0)
    assert lib.button_get_event(10) == 0 # Not enough time
    assert lib.button_get_event(20) == 0 # Still not enough time (10ms elapsed since change)
    assert lib.button_get_event(30) == 1 # 20ms elapsed, PRESSED event
    assert lib.button_get_event(40) == 0 # No new event

def test_debounce_release():
    # Release button (level = 1)
    lib.button_set_raw_pin_level(1)
    assert lib.button_get_event(50) == 0 # Not enough time
    assert lib.button_get_event(70) == 2 # 20ms elapsed, RELEASED event
    assert lib.button_get_event(80) == 0 # No new event

def test_debounce_noise():
    # Noise (glitch to 0 then back to 1)
    lib.button_set_raw_pin_level(0)
    assert lib.button_get_event(90) == 0
    lib.button_set_raw_pin_level(1)
    assert lib.button_get_event(100) == 0 # Reset timer
    assert lib.button_get_event(120) == 0 # 20ms elapsed but state is 1 (same as debounced)
