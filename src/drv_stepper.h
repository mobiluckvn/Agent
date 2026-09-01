#ifndef DRV_STEPPER_H
#define DRV_STEPPER_H

#include <stdint.h>

void stepper_init(void);
void stepper_set_speed(int16_t speed_left, int16_t speed_right);

#endif
