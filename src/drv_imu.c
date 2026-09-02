#include "drv_imu.h"
#include "drv_i2c.h"
#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#define IMU_ADDR 0x68
#define CALIB_SAMPLES 500

typedef enum {
    IMU_STATE_INIT_PWR = 0,
    IMU_STATE_INIT_GYRO,
    IMU_STATE_INIT_ACCEL,
    IMU_STATE_INIT_CONFIG,
    IMU_STATE_READ_REQ,
    IMU_STATE_READ_WAIT_ADDR,
    IMU_STATE_READ_WAIT_DATA
} imu_state_t;

static imu_state_t state = IMU_STATE_INIT_PWR;
static uint8_t i2c_buf[14];
static float current_angle = 0.0f;

static int32_t calib_accel_z_sum = 0;
static int32_t calib_gyro_y_sum = 0;
static int16_t calib_count = 0;
static bool is_calibrating = false;

static int16_t offset_accel_z = 0;
static int16_t offset_gyro_y = 0;

void imu_init(void) {
    i2c_init();
    state = IMU_STATE_INIT_PWR;
    current_angle = 0.0f;
    offset_accel_z = 0;
    offset_gyro_y = 0;
    is_calibrating = false;
}

bool imu_update(void) {
    static uint8_t tx_buf[2];
    i2c_status_t st = i2c_get_status();
    
    if (st == I2C_BUSY) {
        return false;
    }
    
    switch (state) {
        case IMU_STATE_INIT_PWR:
            // ref: ds-031, MPU-6000/MPU-6050 Register Map rev. 4.2, tr.40-45
            tx_buf[0] = 0x6B;
            tx_buf[1] = 0x00;
            if (i2c_write_async(IMU_ADDR, tx_buf, 2)) {
                state = IMU_STATE_INIT_GYRO;
            }
            break;
            
        case IMU_STATE_INIT_GYRO:
            if (st == I2C_SUCCESS) {
                // ref: ds-032, MPU-6000/MPU-6050 Register Map rev. 4.2, tr.29-31
                tx_buf[0] = 0x1B;
                tx_buf[1] = 0x00;
                if (i2c_write_async(IMU_ADDR, tx_buf, 2)) {
                    state = IMU_STATE_INIT_ACCEL;
                }
            } else if (st == I2C_ERROR) {
                state = IMU_STATE_INIT_PWR;
            }
            break;
            
        case IMU_STATE_INIT_ACCEL:
            if (st == I2C_SUCCESS) {
                // ref: ds-032, MPU-6000/MPU-6050 Register Map rev. 4.2, tr.29-31
                tx_buf[0] = 0x1C;
                tx_buf[1] = 0x08;
                if (i2c_write_async(IMU_ADDR, tx_buf, 2)) {
                    state = IMU_STATE_INIT_CONFIG;
                }
            } else if (st == I2C_ERROR) {
                state = IMU_STATE_INIT_PWR;
            }
            break;
            
        case IMU_STATE_INIT_CONFIG:
            if (st == I2C_SUCCESS) {
                // ref: ds-031, MPU-6000/MPU-6050 Register Map rev. 4.2, tr.40-45
                tx_buf[0] = 0x1A;
                tx_buf[1] = 0x03;
                if (i2c_write_async(IMU_ADDR, tx_buf, 2)) {
                    state = IMU_STATE_READ_REQ;
                }
            } else if (st == I2C_ERROR) {
                state = IMU_STATE_INIT_PWR;
            }
            break;
            
        case IMU_STATE_READ_REQ:
            if (st == I2C_SUCCESS || st == I2C_IDLE || st == I2C_ERROR) {
                // ref: ds-032, MPU-6000/MPU-6050 Register Map rev. 4.2, tr.29-31
                tx_buf[0] = 0x3B;
                if (i2c_write_async(IMU_ADDR, tx_buf, 1)) {
                    state = IMU_STATE_READ_WAIT_ADDR;
                }
            }
            break;
            
        case IMU_STATE_READ_WAIT_ADDR:
            if (st == I2C_SUCCESS) {
                if (i2c_read_async(IMU_ADDR, i2c_buf, 14)) {
                    state = IMU_STATE_READ_WAIT_DATA;
                }
            } else if (st == I2C_ERROR) {
                state = IMU_STATE_READ_REQ;
            }
            break;
            
        case IMU_STATE_READ_WAIT_DATA:
            if (st == I2C_SUCCESS) {
                state = IMU_STATE_READ_REQ;
                
                int16_t accel_z = (int16_t)((i2c_buf[4] << 8) | i2c_buf[5]);
                int16_t gyro_y = (int16_t)((i2c_buf[10] << 8) | i2c_buf[11]);
                
                if (is_calibrating) {
                    if (calib_count < CALIB_SAMPLES) {
                        calib_accel_z_sum += accel_z;
                        calib_gyro_y_sum += gyro_y;
                        calib_count++;
                    }
                } else {
                    float az = (float)accel_z - (float)offset_accel_z;
                    if (az > 8200.0f) az = 8200.0f;
                    if (az < -8200.0f) az = -8200.0f;
                    
                    float angle_acc = asin(az / 8200.0f) * 57.296f;
                    float gyro_rate = (float)gyro_y - (float)offset_gyro_y;
                    
                    current_angle += gyro_rate * 0.000031f;
                    current_angle = current_angle * 0.9996f + angle_acc * 0.0004f;
                }
                return true;
            } else if (st == I2C_ERROR) {
                state = IMU_STATE_READ_REQ;
            }
            break;
    }
    return false;
}

float imu_get_tilt_angle(void) {
    return current_angle;
}

void imu_calibrate_begin(void) {
    calib_accel_z_sum = 0;
    calib_gyro_y_sum = 0;
    calib_count = 0;
    is_calibrating = true;
}

bool imu_calibrate_busy(void) {
    return is_calibrating && (calib_count < CALIB_SAMPLES);
}

void imu_calibrate_commit(void) {
    if (calib_count > 0) {
        offset_accel_z = (int16_t)(calib_accel_z_sum / calib_count);
        offset_gyro_y = (int16_t)(calib_gyro_y_sum / calib_count);
    }
    is_calibrating = false;
    current_angle = 0.0f;
}
