import os
import subprocess
import ctypes
import pytest

def compile_module():
    src_file = "src/drv_buzzer.c"
    mock_src = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    include_dir = "/Users/v/Documents/KTDT/packs/avr/hostmock"
    out_file = "libdrv_buzzer.so"
    
    cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        f"-I{include_dir}",
        src_file, mock_src,
        "-o", out_file
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"Compilation failed:\n{result.stderr}")
    
    return out_file

@pytest.fixture(scope="module")
def buzzer_lib():
    lib_path = compile_module()
    lib = ctypes.CDLL(f"./{lib_path}")
    
    lib.buzzer_init.argtypes = []
    lib.buzzer_init.restype = None
    
    lib.buzzer_beep_async.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.buzzer_beep_async.restype = None
    
    lib.buzzer_update.argtypes = [ctypes.c_uint32]
    lib.buzzer_update.restype = None
    
    lib.buzzer_stop.argtypes = []
    lib.buzzer_stop.restype = None
    
    return lib

def test_buzzer_init(buzzer_lib):
    DDRB = ctypes.c_uint8.in_dll(buzzer_lib, "DDRB")
    PORTB = ctypes.c_uint8.in_dll(buzzer_lib, "PORTB")
    
    DDRB.value = 0x00
    PORTB.value = 0xFF
    
    buzzer_lib.buzzer_init()
    
    assert (DDRB.value & (1 << 2)) != 0, "PB2 should be set as output"
    assert (PORTB.value & (1 << 2)) == 0, "PB2 should be low initially"

def test_buzzer_beep_async(buzzer_lib):
    PORTB = ctypes.c_uint8.in_dll(buzzer_lib, "PORTB")
    
    buzzer_lib.buzzer_init()
    PORTB.value = 0x00
    
    buzzer_lib.buzzer_beep_async(1000, 500)
    
    assert (PORTB.value & (1 << 2)) != 0, "PB2 should be high when beeping"

def test_buzzer_update_and_stop(buzzer_lib):
    PORTB = ctypes.c_uint8.in_dll(buzzer_lib, "PORTB")
    
    buzzer_lib.buzzer_init()
    
    # Start beep at 1000ms for 500ms
    buzzer_lib.buzzer_beep_async(1000, 500)
    assert (PORTB.value & (1 << 2)) != 0
    
    # Update before duration ends
    buzzer_lib.buzzer_update(1200)
    assert (PORTB.value & (1 << 2)) != 0, "Buzzer should still be on"
    
    # Update exactly at duration end
    buzzer_lib.buzzer_update(1500)
    assert (PORTB.value & (1 << 2)) == 0, "Buzzer should be off after duration"

def test_buzzer_stop_manual(buzzer_lib):
    PORTB = ctypes.c_uint8.in_dll(buzzer_lib, "PORTB")
    
    buzzer_lib.buzzer_init()
    
    buzzer_lib.buzzer_beep_async(1000, 500)
    assert (PORTB.value & (1 << 2)) != 0
    
    buzzer_lib.buzzer_stop()
    assert (PORTB.value & (1 << 2)) == 0, "Buzzer should be off after manual stop"

def test_buzzer_beep_zero_duration(buzzer_lib):
    PORTB = ctypes.c_uint8.in_dll(buzzer_lib, "PORTB")
    
    buzzer_lib.buzzer_init()
    PORTB.value = 0x04 # Force it on to see if it turns off
    
    buzzer_lib.buzzer_beep_async(1000, 0)
    assert (PORTB.value & (1 << 2)) == 0, "Buzzer should turn off for 0 duration"
