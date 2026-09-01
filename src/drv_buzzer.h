#ifndef DRV_BUZZER_H
#define DRV_BUZZER_H

#include <stdint.h>
#include <stdbool.h>

void buzzer_beep_async(uint32_t duration_ms);
void buzzer_stop(void);
void buzzer_update(uint32_t delta_ms);
bool buzzer_is_beeping(void);

#endif // DRV_BUZZER_H
