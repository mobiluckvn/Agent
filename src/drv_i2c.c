#include "drv_i2c.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stddef.h>

static volatile uint8_t i2c_status = I2C_STATUS_IDLE;
static volatile uint8_t i2c_addr;
static uint8_t * volatile i2c_buf;
static volatile uint8_t i2c_len;
static volatile uint8_t i2c_idx;

void i2c_init(void) {
    // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
    TWSR = 0x00;
    TWBR = 12;
    TWCR = (1 << 2); // TWEN
}

bool i2c_write_async(uint8_t addr, const uint8_t *data, uint8_t len) {
    if (i2c_status == I2C_STATUS_BUSY) {
        return false;
    }
    if (len == 0 || data == NULL) {
        return false;
    }

    i2c_addr = addr << 1;
    i2c_buf = (uint8_t *)data;
    i2c_len = len;
    i2c_idx = 0;
    i2c_status = I2C_STATUS_BUSY;

    // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
    TWCR = (1 << 7) | (1 << 5) | (1 << 2) | (1 << 0); // TWINT | TWSTA | TWEN | TWIE
    return true;
}

bool i2c_read_async(uint8_t addr, uint8_t *data, uint8_t len) {
    if (i2c_status == I2C_STATUS_BUSY) {
        return false;
    }
    if (len == 0 || data == NULL) {
        return false;
    }

    i2c_addr = (addr << 1) | 1;
    i2c_buf = data;
    i2c_len = len;
    i2c_idx = 0;
    i2c_status = I2C_STATUS_BUSY;

    // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
    TWCR = (1 << 7) | (1 << 5) | (1 << 2) | (1 << 0); // TWINT | TWSTA | TWEN | TWIE
    return true;
}

i2c_status_t i2c_get_status(void) {
    return (i2c_status_t)i2c_status;
}

ISR(TWI_vect) {
    // ref: ds-022, ATmega328P datasheet rev. DS40002061B, tr.228-232
    uint8_t status = TWSR & 0xF8;

    switch (status) {
        case 0x08: // START
        case 0x10: // Repeated START
            TWDR = i2c_addr;
            // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
            TWCR = (1 << 7) | (1 << 2) | (1 << 0); // TWINT | TWEN | TWIE
            break;

        case 0x18: // SLA+W, ACK
        case 0x28: // Data sent, ACK
            if (i2c_idx < i2c_len) {
                TWDR = i2c_buf[i2c_idx++];
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 2) | (1 << 0); // TWINT | TWEN | TWIE
            } else {
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 4) | (1 << 2); // TWINT | TWSTO | TWEN
                i2c_status = I2C_STATUS_SUCCESS;
            }
            break;

        case 0x40: // SLA+R, ACK
            if (i2c_len == 1) {
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 2) | (1 << 0); // TWINT | TWEN | TWIE
            } else {
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 6) | (1 << 2) | (1 << 0); // TWINT | TWEA | TWEN | TWIE
            }
            break;

        case 0x50: // Data received, ACK
            i2c_buf[i2c_idx++] = TWDR;
            if (i2c_idx == i2c_len - 1) {
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 2) | (1 << 0); // TWINT | TWEN | TWIE
            } else {
                // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
                TWCR = (1 << 7) | (1 << 6) | (1 << 2) | (1 << 0); // TWINT | TWEA | TWEN | TWIE
            }
            break;

        case 0x58: // Data received, NACK
            i2c_buf[i2c_idx++] = TWDR;
            // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
            TWCR = (1 << 7) | (1 << 4) | (1 << 2); // TWINT | TWSTO | TWEN
            i2c_status = I2C_STATUS_SUCCESS;
            break;

        case 0x20: // SLA+W, NACK
        case 0x38: // Arbitration lost
        default:
            // ref: ds-021, ATmega328P datasheet rev. DS40002061B, tr.222-224
            TWCR = (1 << 7) | (1 << 4) | (1 << 2); // TWINT | TWSTO | TWEN
            i2c_status = I2C_STATUS_ERROR;
            break;
    }
}
