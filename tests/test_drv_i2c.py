import os
import ctypes
import pytest
import subprocess

def compile_lib():
    src = "src/drv_i2c.c"
    mock = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    out = "libdrv_i2c.so"
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", 
           "-I/Users/v/Documents/KTDT/packs/avr/hostmock", 
           "-Isrc", src, mock, "-o", out]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())
        pytest.fail("Compilation failed")
    return out

@pytest.fixture(scope="module")
def lib():
    out = compile_lib()
    l = ctypes.CDLL(f"./{out}")
    
    l.i2c_init.argtypes = []
    l.i2c_init.restype = None
    
    l.i2c_write_async.argtypes = [ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
    l.i2c_write_async.restype = ctypes.c_bool
    
    l.i2c_read_async.argtypes = [ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
    l.i2c_read_async.restype = ctypes.c_bool
    
    l.i2c_get_status.argtypes = []
    l.i2c_get_status.restype = ctypes.c_int
    
    l.i2c_tick.argtypes = []
    l.i2c_tick.restype = None
    
    l.TWI_vect_fn.argtypes = []
    l.TWI_vect_fn.restype = None
    
    return l

def test_i2c_init_aborts_busy(lib):
    lib.i2c_init()
    
    data = (ctypes.c_uint8 * 2)(0x01, 0x02)
    res = lib.i2c_write_async(0x50, data, 2)
    assert res == True
    assert lib.i2c_get_status() == 1 # BUSY
    
    lib.i2c_init()
    assert lib.i2c_get_status() == 0 # IDLE
    
    res = lib.i2c_write_async(0x50, data, 2)
    assert res == True

def test_i2c_write_sequence(lib):
    lib.i2c_init()
    
    TWCR = ctypes.c_uint8.in_dll(lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(lib, "TWSR")
    TWDR = ctypes.c_uint8.in_dll(lib, "TWDR")
    
    data = (ctypes.c_uint8 * 2)(0xAA, 0xBB)
    lib.i2c_write_async(0x50, data, 2)
    
    # START sent
    assert (TWCR.value & (1 << 5)) != 0 # TWSTA
    
    TWSR.value = 0x08 # START transmitted
    lib.TWI_vect_fn()
    assert TWDR.value == (0x50 << 1)
    
    TWSR.value = 0x18 # SLA+W transmitted, ACK received
    lib.TWI_vect_fn()
    assert TWDR.value == 0xAA
    
    TWSR.value = 0x28 # Data transmitted, ACK received
    lib.TWI_vect_fn()
    assert TWDR.value == 0xBB
    
    TWSR.value = 0x28 # Data transmitted, ACK received
    lib.TWI_vect_fn()
    assert (TWCR.value & (1 << 4)) != 0 # TWSTO
    assert lib.i2c_get_status() == 2 # SUCCESS

def test_i2c_read_sequence(lib):
    lib.i2c_init()
    
    TWCR = ctypes.c_uint8.in_dll(lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(lib, "TWSR")
    TWDR = ctypes.c_uint8.in_dll(lib, "TWDR")
    
    data = (ctypes.c_uint8 * 2)(0, 0)
    lib.i2c_read_async(0x50, data, 2)
    
    TWSR.value = 0x08 # START transmitted
    lib.TWI_vect_fn()
    assert TWDR.value == (0x50 << 1) | 1
    
    TWSR.value = 0x40 # SLA+R transmitted, ACK received
    lib.TWI_vect_fn()
    assert (TWCR.value & (1 << 6)) != 0 # TWEA
    
    TWDR.value = 0xCC
    TWSR.value = 0x50 # Data received, ACK returned
    lib.TWI_vect_fn()
    assert data[0] == 0xCC
    assert (TWCR.value & (1 << 6)) == 0 # No TWEA for last byte
    
    TWDR.value = 0xDD
    TWSR.value = 0x58 # Data received, NACK returned
    lib.TWI_vect_fn()
    assert data[1] == 0xDD
    assert (TWCR.value & (1 << 4)) != 0 # TWSTO
    assert lib.i2c_get_status() == 2 # SUCCESS

def test_i2c_nack_at_slaw(lib):
    lib.i2c_init()
    
    TWCR = ctypes.c_uint8.in_dll(lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(lib, "TWSR")
    
    data = (ctypes.c_uint8 * 1)(0x01)
    lib.i2c_write_async(0x50, data, 1)
    
    TWSR.value = 0x08
    lib.TWI_vect_fn()
    
    TWSR.value = 0x20 # SLA+W transmitted, NACK received
    lib.TWI_vect_fn()
    
    assert (TWCR.value & (1 << 4)) != 0 # TWSTO
    assert lib.i2c_get_status() == 3 # ERROR

def test_i2c_timeout(lib):
    lib.i2c_init()
    
    TWCR = ctypes.c_uint8.in_dll(lib, "TWCR")
    
    data = (ctypes.c_uint8 * 1)(0x01)
    lib.i2c_write_async(0x50, data, 1)
    
    assert lib.i2c_get_status() == 1 # BUSY
    
    for _ in range(5):
        lib.i2c_tick()
        assert lib.i2c_get_status() == 1 # Still BUSY
        
    lib.i2c_tick() # 6th tick
    assert lib.i2c_get_status() == 3 # ERROR
    assert (TWCR.value & (1 << 4)) != 0 # TWSTO
    
    # New transaction can start
    res = lib.i2c_write_async(0x50, data, 1)
    assert res == True
