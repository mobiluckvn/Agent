import os
import ctypes
import subprocess
import pytest

def build_lib():
    src_file = "src/drv_stepper.c"
    lib_file = "drv_stepper.so"
    hostmock_dir = "/Users/v/Documents/KTDT/packs/avr/hostmock"
    eaa_io_space = os.path.join(hostmock_dir, "eaa_io_space.c")
    
    cmd = [
        "cc", "-std=c11", "-Wall", "-Werror", "-fPIC", "-shared",
        f"-I{hostmock_dir}",
        "-Isrc",
        src_file, eaa_io_space,
        "-o", lib_file
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        pytest.fail("Compilation failed")
    return lib_file

@pytest.fixture(scope="module")
def stepper_lib():
    lib_path = build_lib()
    lib = ctypes.CDLL(f"./{lib_path}")
    
    # Setup argtypes and restype
    lib.stepper_init.argtypes = []
    lib.stepper_init.restype = None
    
    lib.stepper_set_speed.argtypes = [ctypes.c_int16, ctypes.c_int16]
    lib.stepper_set_speed.restype = None
    
    lib.TIMER2_COMPA_vect_fn.argtypes = []
    lib.TIMER2_COMPA_vect_fn.restype = None
    
    return lib

def test_stepper_init(stepper_lib):
    DDRD = ctypes.c_uint8.in_dll(stepper_lib, "DDRD")
    PORTD = ctypes.c_uint8.in_dll(stepper_lib, "PORTD")
    TCCR2A = ctypes.c_uint8.in_dll(stepper_lib, "TCCR2A")
    TCCR2B = ctypes.c_uint8.in_dll(stepper_lib, "TCCR2B")
    OCR2A = ctypes.c_uint8.in_dll(stepper_lib, "OCR2A")
    TIMSK2 = ctypes.c_uint8.in_dll(stepper_lib, "TIMSK2")
    
    DDRD.value = 0
    PORTD.value = 0xFF
    TCCR2A.value = 0
    TCCR2B.value = 0
    OCR2A.value = 0
    TIMSK2.value = 0
    
    stepper_lib.stepper_init()
    
    # Check pins
    assert (DDRD.value & 0xF0) == 0xF0 # PD4, PD5, PD6, PD7 are outputs
    assert (PORTD.value & 0xF0) == 0x00 # Initialized to 0
    
    # Check timer config
    assert (TCCR2A.value & (1 << 1)) != 0 # WGM21 = 1
    assert (TCCR2B.value & (1 << 1)) != 0 # CS21 = 1
    assert OCR2A.value == 39
    assert (TIMSK2.value & (1 << 1)) != 0 # OCIE2A = 1

def test_stepper_direction_and_pulses(stepper_lib):
    PORTD = ctypes.c_uint8.in_dll(stepper_lib, "PORTD")
    
    # Set speed to positive (forward)
    stepper_lib.stepper_set_speed(10, 10)
    
    # First interrupt: counter becomes 1, which is > threshold (0)
    # It resets counter to 0, sets threshold to 10, sets direction
    stepper_lib.TIMER2_COMPA_vect_fn()
    
    # Check direction: Left forward (PD6=1), Right forward (PD4=0)
    assert (PORTD.value & (1 << 6)) != 0
    assert (PORTD.value & (1 << 4)) == 0
    
    # Next interrupt: counter == 1, STEP goes high (PD7=1, PD5=1)
    stepper_lib.TIMER2_COMPA_vect_fn()
    assert (PORTD.value & (1 << 7)) != 0
    assert (PORTD.value & (1 << 5)) != 0
    
    # Next interrupt: counter == 2, STEP goes low (PD7=0, PD5=0)
    stepper_lib.TIMER2_COMPA_vect_fn()
    assert (PORTD.value & (1 << 7)) == 0
    assert (PORTD.value & (1 << 5)) == 0

def test_stepper_negative_direction(stepper_lib):
    PORTD = ctypes.c_uint8.in_dll(stepper_lib, "PORTD")
    
    # Set speed to negative (backward)
    stepper_lib.stepper_set_speed(-20, -20)
    
    # Run interrupt enough times to trigger threshold update (threshold was 10)
    for _ in range(20):
        stepper_lib.TIMER2_COMPA_vect_fn()
        
    # Check direction: Left backward (PD6=0), Right backward (PD4=1)
    assert (PORTD.value & (1 << 6)) == 0
    assert (PORTD.value & (1 << 4)) != 0

def test_stepper_speed_difference(stepper_lib):
    PORTD = ctypes.c_uint8.in_dll(stepper_lib, "PORTD")
    
    # Set left fast (small threshold), right slow (large threshold)
    stepper_lib.stepper_set_speed(5, 15)
    
    # Trigger update (previous threshold was 20)
    for _ in range(30):
        stepper_lib.TIMER2_COMPA_vect_fn()
        
    # Now left threshold = 5, right threshold = 15
    # Count pulses over 60 interrupts
    left_pulses = 0
    right_pulses = 0
    
    for _ in range(60):
        prev_portd = PORTD.value
        stepper_lib.TIMER2_COMPA_vect_fn()
        curr_portd = PORTD.value
        
        # Detect rising edge on STEP pins
        if (curr_portd & (1 << 7)) and not (prev_portd & (1 << 7)):
            left_pulses += 1
        if (curr_portd & (1 << 5)) and not (prev_portd & (1 << 5)):
            right_pulses += 1
            
    # Left should have more pulses than right
    assert left_pulses > right_pulses
