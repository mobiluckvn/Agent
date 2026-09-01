#ifndef DRV_I2C_H
#define DRV_I2C_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    I2C_STATUS_IDLE = 0,
    I2C_STATUS_BUSY,
    I2C_STATUS_SUCCESS,
    I2C_STATUS_ERROR
} i2c_status_t;

void i2c_init(void);
bool i2c_write_async(uint8_t addr, const uint8_t *data, uint8_t len);
bool i2c_read_async(uint8_t addr, uint8_t *data, uint8_t len);
i2c_status_t i2c_get_status(void);

#endif // DRV_I2C_H
