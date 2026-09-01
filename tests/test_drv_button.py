import os
import subprocess
import ctypes
import pytest

def compile_lib():
    src = "src/drv_button.c"
    lib = "libdrv_button.so"
    mock_src = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    inc_dir = "/Users/v/Documents/KTDT/packs/avr/hostmock"
    
    cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        f"-I{inc_dir}",
        src, mock_src,
        "-o", lib
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Compile error:")
        print(result.stderr)
        pytest.fail("Compilation failed")
    return lib

@pytest.fixture(scope="module")
def button_lib():
    lib_path = compile_lib()
    lib = ctypes.CDLL(f"./{lib_path}")
    
    lib.button_init.argtypes = []
    lib.button_init.restype = None
    
    lib.button_get_event.argtypes = [ctypes.c_uint32]
    lib.button_get_event.restype = ctypes.c_int
    
    return lib

def test_button_init(button_lib):
    DDRB = ctypes.c_uint8.in_dll(button_lib, "DDRB")
    PORTB = ctypes.c_uint8.in_dll(button_lib, "PORTB")
    
    # Set initial values to verify changes
    DDRB.value = 0xFF
    PORTB.value = 0x00
    
    button_lib.button_init()
    
    assert (DDRB.value & (1 << 4)) == 0, "PB4 should be configured as input"
    assert (PORTB.value & (1 << 4)) != 0, "PB4 internal pull-up should be enabled"

def test_button_debounce(button_lib):
    PINB = ctypes.c_uint8.in_dll(button_lib, "PINB")
    
    # Initial state: button released (pull-up makes it high)
    PINB.value = (1 << 4)
    assert button_lib.button_get_event(0) == 0 # BUTTON_EVENT_NONE
    
    # Press button (raw state goes low)
    PINB.value = 0
    assert button_lib.button_get_event(10) == 0 # BUTTON_EVENT_NONE (debounce time not met)
    
    # Still pressed, but time < 20ms from change
    assert button_lib.button_get_event(25) == 0 # BUTTON_EVENT_NONE (10 + 20 = 30)
    
    # Time >= 20ms from change
    assert button_lib.button_get_event(30) == 1 # BUTTON_EVENT_PRESSED
    
    # Still pressed, should return NONE
    assert button_lib.button_get_event(40) == 0 # BUTTON_EVENT_NONE
    
    # Release button (raw state goes high)
    PINB.value = (1 << 4)
    assert button_lib.button_get_event(50) == 0 # BUTTON_EVENT_NONE
    
    # Time >= 20ms from change
    assert button_lib.button_get_event(70) == 2 # BUTTON_EVENT_RELEASED
    
    # Still released, should return NONE
    assert button_lib.button_get_event(80) == 0 # BUTTON_EVENT_NONE
