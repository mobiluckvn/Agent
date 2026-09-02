import os
import ctypes
import pytest
import subprocess

def compile_lib():
    src = ["src/drv_imu.c", "src/drv_i2c.c", "/Users/v/Documents/KTDT/packs/avr/hostmock/eaa_io_space.c"]
    out = "libdrv_imu.so"
    cmd = ["cc", "-std=c11", "-Wall", "-fPIC", "-shared", "-I/Users/v/Documents/KTDT/packs/avr/hostmock", "-Isrc"] + src + ["-o", out, "-lm"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())
        pytest.fail("Compilation failed")
    return out

@pytest.fixture(scope="module")
def lib():
    out = compile_lib()
    l = ctypes.CDLL(f"./{out}")
    l.imu_init.argtypes = []
    l.imu_init.restype = None
    l.imu_update.argtypes = []
    l.imu_update.restype = ctypes.c_bool
    l.imu_get_tilt_angle.argtypes = []
    l.imu_get_tilt_angle.restype = ctypes.c_float
    l.imu_calibrate_begin.argtypes = []
    l.imu_calibrate_begin.restype = None
    l.imu_calibrate_busy.argtypes = []
    l.imu_calibrate_busy.restype = ctypes.c_bool
    l.imu_calibrate_commit.argtypes = []
    l.imu_calibrate_commit.restype = None
    l.i2c_get_status.argtypes = []
    l.i2c_get_status.restype = ctypes.c_int
    return l

class TWISimulator:
    def __init__(self, lib):
        self.lib = lib
        self.TWCR = ctypes.c_uint8.in_dll(lib, "TWCR")
        self.TWSR = ctypes.c_uint8.in_dll(lib, "TWSR")
        self.TWDR = ctypes.c_uint8.in_dll(lib, "TWDR")
        self.state = 'IDLE'
        self.regs = {}
        self.mem_addr = 0
        self.read_buf = []
        self.error_on_next = False

    def step(self):
        twcr = self.TWCR.value
        if twcr & 0x80:
            if twcr & 0x20:
                if self.state != 'IDLE':
                    self.TWSR.value = 0x10
                else:
                    self.TWSR.value = 0x08
                self.state = 'START'
            elif twcr & 0x10:
                self.TWCR.value = twcr & ~0x10
                self.state = 'IDLE'
            else:
                if self.state == 'START':
                    addr = self.TWDR.value
                    if self.error_on_next:
                        self.TWSR.value = 0x20
                        self.error_on_next = False
                    else:
                        if (addr & 1) == 0:
                            self.TWSR.value = 0x18
                            self.state = 'WRITE_ADDR'
                        else:
                            self.TWSR.value = 0x40
                            self.state = 'READ'
                elif self.state == 'WRITE_ADDR':
                    self.mem_addr = self.TWDR.value
                    self.state = 'WRITE_DATA'
                    self.TWSR.value = 0x28
                elif self.state == 'WRITE_DATA':
                    self.regs[self.mem_addr] = self.TWDR.value
                    self.mem_addr += 1
                    self.TWSR.value = 0x28
                elif self.state == 'READ':
                    if len(self.read_buf) > 0:
                        self.TWDR.value = self.read_buf.pop(0)
                    else:
                        self.TWDR.value = 0
                    if twcr & 0x40:
                        self.TWSR.value = 0x50
                    else:
                        self.TWSR.value = 0x58

def pump_i2c(lib, sim):
    for _ in range(100):
        sim.step()
        if hasattr(lib, 'TWI_vect_fn'):
            lib.TWI_vect_fn()
        if hasattr(lib, 'i2c_tick'):
            lib.i2c_tick()
        if lib.i2c_get_status() != 1:
            break

def run_imu_update(lib, sim):
    for _ in range(100):
        res = lib.imu_update()
        if res:
            return True
        pump_i2c(lib, sim)
        if lib.i2c_get_status() == 0:
            pass
    return False

def test_imu_init(lib):
    sim = TWISimulator(lib)
    lib.imu_init()
    for _ in range(10):
        lib.imu_update()
        pump_i2c(lib, sim)
    
    assert sim.regs.get(0x6B) == 0x00
    assert sim.regs.get(0x1B) == 0x00
    assert sim.regs.get(0x1C) == 0x08
    assert sim.regs.get(0x1A) == 0x03

def test_imu_read_and_bus_error(lib):
    sim = TWISimulator(lib)
    lib.imu_init()
    for _ in range(10):
        lib.imu_update()
        pump_i2c(lib, sim)
    
    buf = [0]*14
    buf[4] = (1000 >> 8) & 0xFF
    buf[5] = 1000 & 0xFF
    buf[10] = (200 >> 8) & 0xFF
    buf[11] = 200 & 0xFF
    sim.read_buf = buf.copy()
    
    assert run_imu_update(lib, sim) == True
    angle1 = lib.imu_get_tilt_angle()
    
    sim.error_on_next = True
    lib.imu_update()
    pump_i2c(lib, sim)
    res = lib.imu_update()
    assert res == False
    angle2 = lib.imu_get_tilt_angle()
    assert angle1 == angle2

def test_imu_calibration(lib):
    sim = TWISimulator(lib)
    lib.imu_init()
    for _ in range(10):
        lib.imu_update()
        pump_i2c(lib, sim)
    
    lib.imu_calibrate_begin()
    assert lib.imu_calibrate_busy() == True
    
    for _ in range(500):
        buf = [0]*14
        buf[4] = (4100 >> 8) & 0xFF
        buf[5] = 4100 & 0xFF
        buf[10] = (100 >> 8) & 0xFF
        buf[11] = 100 & 0xFF
        sim.read_buf = buf
        run_imu_update(lib, sim)
    
    assert lib.imu_calibrate_busy() == False
    lib.imu_calibrate_commit()
    
    assert abs(lib.imu_get_tilt_angle()) < 0.001
    
    buf = [0]*14
    buf[4] = (4100 >> 8) & 0xFF
    buf[5] = 4100 & 0xFF
    buf[10] = (100 >> 8) & 0xFF
    buf[11] = 100 & 0xFF
    sim.read_buf = buf
    run_imu_update(lib, sim)
    
    assert abs(lib.imu_get_tilt_angle()) < 0.001

def test_imu_angle_calculation(lib):
    sim = TWISimulator(lib)
    lib.imu_init()
    for _ in range(10):
        lib.imu_update()
        pump_i2c(lib, sim)
    
    buf = [0]*14
    buf[4] = (4100 >> 8) & 0xFF
    buf[5] = 4100 & 0xFF
    buf[10] = 0
    buf[11] = 0
    sim.read_buf = buf
    run_imu_update(lib, sim)
    
    angle = lib.imu_get_tilt_angle()
    assert abs(angle - 0.012) < 0.001
