import os
import subprocess
import ctypes
import pytest

def compile_lib():
    src = "src/drv_buzzer.c"
    lib = "./drv_buzzer.so"
    if os.path.exists(lib):
        os.remove(lib)
    
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", "-o", lib, src]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed:\n{result.stderr}")
        
    return lib

@pytest.fixture(scope="session")
def buzzer_lib():
    lib_path = compile_lib()
    lib = ctypes.CDLL(lib_path)
    
    lib.buzzer_beep_async.argtypes = [ctypes.c_uint32]
    lib.buzzer_beep_async.restype = None
    
    lib.buzzer_stop.argtypes = []
    lib.buzzer_stop.restype = None
    
    lib.buzzer_update.argtypes = [ctypes.c_uint32]
    lib.buzzer_update.restype = None
    
    lib.buzzer_is_beeping.argtypes = []
    lib.buzzer_is_beeping.restype = ctypes.c_bool
    
    return lib

def test_buzzer_beep_async(buzzer_lib):
    # Đảm bảo trạng thái ban đầu là tắt
    buzzer_lib.buzzer_stop()
    assert not buzzer_lib.buzzer_is_beeping()
    
    # Bật còi trong 100ms
    buzzer_lib.buzzer_beep_async(100)
    assert buzzer_lib.buzzer_is_beeping()
    
    # Cập nhật 40ms, còi vẫn phải đang kêu
    buzzer_lib.buzzer_update(40)
    assert buzzer_lib.buzzer_is_beeping()
    
    # Cập nhật thêm 60ms, còi phải tự tắt
    buzzer_lib.buzzer_update(60)
    assert not buzzer_lib.buzzer_is_beeping()

def test_buzzer_stop(buzzer_lib):
    # Bật còi trong 200ms
    buzzer_lib.buzzer_beep_async(200)
    assert buzzer_lib.buzzer_is_beeping()
    
    # Dừng còi ngay lập tức
    buzzer_lib.buzzer_stop()
    assert not buzzer_lib.buzzer_is_beeping()
