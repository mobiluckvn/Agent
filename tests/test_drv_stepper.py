import ctypes
import pytest
import subprocess

@pytest.fixture(scope="module")
def lib():
    source_file = "src/drv_stepper.c"
    mock_file = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    output_lib = "libdrv_stepper.so"
    
    compile_cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        "-I/Users/v/Documents/KTDT/packs/avr/hostmock",
        "-Isrc",
        source_file, mock_file,
        "-o", output_lib
    ]
    
    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Compile error:")
        print(result.stderr)
        pytest.fail("Compilation failed")
        
    lib = ctypes.CDLL(f"./{output_lib}")
    
    # Setup argtypes and restypes
    lib.stepper_init.argtypes = []
    lib.stepper_init.restype = None
    
    lib.stepper_set_speed.argtypes = [ctypes.c_int16, ctypes.c_int16]
    lib.stepper_set_speed.restype = None
    
    lib.TIMER2_COMPA_vect_fn.argtypes = []
    lib.TIMER2_COMPA_vect_fn.restype = None
    
    return lib

def test_stepper_init(lib):
    # Reset registers
    ctypes.c_uint8.in_dll(lib, "DDRD").value = 0
    ctypes.c_uint8.in_dll(lib, "PORTD").value = 0
    ctypes.c_uint8.in_dll(lib, "TCCR2A").value = 0
    ctypes.c_uint8.in_dll(lib, "TCCR2B").value = 0
    ctypes.c_uint8.in_dll(lib, "OCR2A").value = 0
    ctypes.c_uint8.in_dll(lib, "TIMSK2").value = 0
    
    lib.stepper_init()
    
    ddrd = ctypes.c_uint8.in_dll(lib, "DDRD").value
    assert (ddrd & 0xF0) == 0xF0  # PD4, PD5, PD6, PD7 are outputs
    
    tccr2a = ctypes.c_uint8.in_dll(lib, "TCCR2A").value
    tccr2b = ctypes.c_uint8.in_dll(lib, "TCCR2B").value
    ocr2a = ctypes.c_uint8.in_dll(lib, "OCR2A").value
    timsk2 = ctypes.c_uint8.in_dll(lib, "TIMSK2").value
    
    assert (tccr2a & (1 << 1)) != 0  # WGM21
    assert (tccr2b & (1 << 1)) != 0  # CS21
    assert ocr2a == 39
    assert (timsk2 & (1 << 1)) != 0  # OCIE2A

def test_zero_speed_then_nonzero(lib):
    lib.stepper_init()
    lib.stepper_set_speed(0, 0)
    
    # Chạy ngắt vài nghìn lần ở tốc độ 0 TRƯỚC
    for _ in range(5000):
        lib.TIMER2_COMPA_vect_fn()
        
    # Đặt lại tốc độ khác 0
    lib.stepper_set_speed(10, 10)
    
    steps_left = 0
    steps_right = 0
    
    portd = ctypes.c_uint8.in_dll(lib, "PORTD")
    prev_step_left = 0
    prev_step_right = 0
    
    for _ in range(100):
        lib.TIMER2_COMPA_vect_fn()
        val = portd.value
        step_left = (val >> 7) & 1
        step_right = (val >> 5) & 1
        
        if step_left == 1 and prev_step_left == 0:
            steps_left += 1
        if step_right == 1 and prev_step_right == 0:
            steps_right += 1
            
        prev_step_left = step_left
        prev_step_right = step_right
        
    # Xung phát trở lại
    assert steps_left > 0
    assert steps_right > 0

def test_threshold_speed(lib):
    lib.stepper_init()
    
    def count_pulses(speed, iterations):
        lib.stepper_set_speed(0, 0)
        for _ in range(100):
            lib.TIMER2_COMPA_vect_fn()
            
        lib.stepper_set_speed(speed, speed)
        pulses = 0
        portd = ctypes.c_uint8.in_dll(lib, "PORTD")
        prev_step = 0
        for _ in range(iterations):
            lib.TIMER2_COMPA_vect_fn()
            step = (portd.value >> 7) & 1
            if step == 1 and prev_step == 0:
                pulses += 1
            prev_step = step
        return pulses
        
    pulses_fast = count_pulses(5, 1000)
    pulses_slow = count_pulses(20, 1000)
    
    # Ngưỡng nhỏ cho ra nhiều xung hơn ngưỡng lớn
    assert pulses_fast > pulses_slow

def test_direction_signs(lib):
    lib.stepper_init()
    portd = ctypes.c_uint8.in_dll(lib, "PORTD")
    
    # Tốc độ dương
    lib.stepper_set_speed(0, 0)
    for _ in range(10): lib.TIMER2_COMPA_vect_fn()
    
    lib.stepper_set_speed(10, 10)
    lib.TIMER2_COMPA_vect_fn() # Áp dụng tốc độ mới
    
    val = portd.value
    dir_left_pos = (val >> 6) & 1
    dir_right_pos = (val >> 4) & 1
    
    # Tốc độ âm
    lib.stepper_set_speed(0, 0)
    for _ in range(10): lib.TIMER2_COMPA_vect_fn()
    
    lib.stepper_set_speed(-10, -10)
    lib.TIMER2_COMPA_vect_fn() # Áp dụng tốc độ mới
    
    val = portd.value
    dir_left_neg = (val >> 6) & 1
    dir_right_neg = (val >> 4) & 1
    
    # Dấu âm và dấu dương cho ra hai mức DIR ngược nhau
    assert dir_left_pos != dir_left_neg
    assert dir_right_pos != dir_right_neg
    
    # Cùng một giá trị điều khiển thì DIR trái và DIR phải ở hai mức KHÁC nhau
    assert dir_left_pos != dir_right_pos

def test_step_pulse_duration(lib):
    lib.stepper_init()
    lib.stepper_set_speed(0, 0)
    for _ in range(10): lib.TIMER2_COMPA_vect_fn()
    
    lib.stepper_set_speed(10, 10)
    portd = ctypes.c_uint8.in_dll(lib, "PORTD")
    
    pulse_length = 0
    in_pulse = False
    
    for _ in range(50):
        lib.TIMER2_COMPA_vect_fn()
        step = (portd.value >> 7) & 1
        if step == 1:
            if not in_pulse:
                in_pulse = True
                pulse_length = 1
            else:
                pulse_length += 1
        else:
            if in_pulse:
                break
                
    # Xung STEP chỉ kéo dài đúng một khoảng ngắt rồi hạ
    assert pulse_length == 1
