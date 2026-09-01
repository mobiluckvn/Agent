import os
import subprocess
import ctypes
import pytest

def setup_module(module):
    source_file = "src/drv_i2c.c"
    lib_file = "./libdrv_i2c.so"
    mock_source = "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"
    
    compile_cmd = [
        "cc", "-std=c11", "-Wall", "-fPIC", "-shared",
        "-I/Users/v/Documents/KTDT/packs/avr/hostmock",
        source_file, mock_source, "-o", lib_file
    ]
    
    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"Compilation failed:\n{result.stderr}")

@pytest.fixture
def i2c_lib():
    lib = ctypes.CDLL("./libdrv_i2c.so")
    
    lib.i2c_init.argtypes = []
    lib.i2c_init.restype = None
    
    lib.i2c_write_async.argtypes = [ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
    lib.i2c_write_async.restype = ctypes.c_bool
    
    lib.i2c_read_async.argtypes = [ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
    lib.i2c_read_async.restype = ctypes.c_bool
    
    lib.i2c_get_status.argtypes = []
    lib.i2c_get_status.restype = ctypes.c_int
    
    lib.TWI_vect_fn.argtypes = []
    lib.TWI_vect_fn.restype = None
    
    return lib

def test_i2c_init(i2c_lib):
    TWSR = ctypes.c_uint8.in_dll(i2c_lib, "TWSR")
    TWBR = ctypes.c_uint8.in_dll(i2c_lib, "TWBR")
    TWCR = ctypes.c_uint8.in_dll(i2c_lib, "TWCR")
    
    i2c_lib.i2c_init()
    
    assert TWSR.value == 0x00
    assert TWBR.value == 12
    assert TWCR.value == (1 << 2)

def test_i2c_write_async(i2c_lib):
    TWCR = ctypes.c_uint8.in_dll(i2c_lib, "TWCR")
    
    data = (ctypes.c_uint8 * 2)(0xAA, 0xBB)
    res = i2c_lib.i2c_write_async(0x50, data, 2)
    
    assert res == True
    assert i2c_lib.i2c_get_status() == 1 # I2C_STATUS_BUSY
    assert TWCR.value == (1 << 7) | (1 << 5) | (1 << 2) | (1 << 0)

def test_i2c_isr_write_flow(i2c_lib):
    TWCR = ctypes.c_uint8.in_dll(i2c_lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(i2c_lib, "TWSR")
    TWDR = ctypes.c_uint8.in_dll(i2c_lib, "TWDR")
    
    data = (ctypes.c_uint8 * 2)(0xAA, 0xBB)
    i2c_lib.i2c_write_async(0x50, data, 2)
    
    TWSR.value = 0x08
    i2c_lib.TWI_vect_fn()
    assert TWDR.value == (0x50 << 1)
    assert TWCR.value == (1 << 7) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x18
    i2c_lib.TWI_vect_fn()
    assert TWDR.value == 0xAA
    assert TWCR.value == (1 << 7) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x28
    i2c_lib.TWI_vect_fn()
    assert TWDR.value == 0xBB
    assert TWCR.value == (1 << 7) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x28
    i2c_lib.TWI_vect_fn()
    assert TWCR.value == (1 << 7) | (1 << 4) | (1 << 2)
    assert i2c_lib.i2c_get_status() == 2 # I2C_STATUS_SUCCESS

def test_i2c_isr_read_flow(i2c_lib):
    TWCR = ctypes.c_uint8.in_dll(i2c_lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(i2c_lib, "TWSR")
    TWDR = ctypes.c_uint8.in_dll(i2c_lib, "TWDR")
    
    data = (ctypes.c_uint8 * 2)(0, 0)
    i2c_lib.i2c_read_async(0x50, data, 2)
    
    TWSR.value = 0x08
    i2c_lib.TWI_vect_fn()
    assert TWDR.value == (0x50 << 1) | 1
    assert TWCR.value == (1 << 7) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x40
    i2c_lib.TWI_vect_fn()
    assert TWCR.value == (1 << 7) | (1 << 6) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x50
    TWDR.value = 0xCC
    i2c_lib.TWI_vect_fn()
    assert data[0] == 0xCC
    assert TWCR.value == (1 << 7) | (1 << 2) | (1 << 0)
    
    TWSR.value = 0x58
    TWDR.value = 0xDD
    i2c_lib.TWI_vect_fn()
    assert data[1] == 0xDD
    assert TWCR.value == (1 << 7) | (1 << 4) | (1 << 2)
    assert i2c_lib.i2c_get_status() == 2 # I2C_STATUS_SUCCESS

def test_i2c_error_flow(i2c_lib):
    TWCR = ctypes.c_uint8.in_dll(i2c_lib, "TWCR")
    TWSR = ctypes.c_uint8.in_dll(i2c_lib, "TWSR")
    
    data = (ctypes.c_uint8 * 1)(0)
    i2c_lib.i2c_write_async(0x50, data, 1)
    
    TWSR.value = 0x20 # SLA+W, NACK
    i2c_lib.TWI_vect_fn()
    
    assert TWCR.value == (1 << 7) | (1 << 4) | (1 << 2)
    assert i2c_lib.i2c_get_status() == 3 # I2C_STATUS_ERROR
