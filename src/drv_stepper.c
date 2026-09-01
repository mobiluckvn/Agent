#include "drv_stepper.h"
#include <avr/io.h>
#include <avr/interrupt.h>

#ifndef cli
#define cli() do {} while(0)
#endif
#ifndef sei
#define sei() do {} while(0)
#endif

volatile int16_t target_speed_left = 0;
volatile int16_t target_speed_right = 0;

static uint16_t counter_left = 0;
static uint16_t current_threshold_left = 0;

static uint16_t counter_right = 0;
static uint16_t current_threshold_right = 0;

void stepper_init(void) {
    // Cấu hình chân output: PD4, PD5, PD6, PD7
    DDRD |= (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7);
    PORTD &= ~((1 << 4) | (1 << 5) | (1 << 6) | (1 << 7));

    // ref: ds-atme-timer2-01, ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf, tr.155,165-166
    TCCR2A = 0;
    TCCR2B = 0;
    TCNT2 = 0;
    OCR2A = 39;
    TCCR2A |= (1 << WGM21);
    TCCR2B |= (1 << CS21);
    TIMSK2 |= (1 << OCIE2A);
}

void stepper_set_speed(int16_t speed_left, int16_t speed_right) {
    cli();
    target_speed_left = speed_left;
    target_speed_right = speed_right;
    sei();
}

ISR(TIMER2_COMPA_vect) {
    // Left motor
    counter_left++;
    if (counter_left > current_threshold_left) {
        counter_left = 0;
        int16_t target_l = target_speed_left;
        if (target_l == 0) {
            current_threshold_left = 65535;
        } else if (target_l < 0) {
            current_threshold_left = (uint16_t)(-target_l);
            PORTD &= ~(1 << 6); // DIR left = 0 (backward)
        } else {
            current_threshold_left = (uint16_t)(target_l);
            PORTD |= (1 << 6); // DIR left = 1 (forward)
        }
    }
    if (current_threshold_left != 65535) {
        if (counter_left == 1) {
            PORTD |= (1 << 7); // STEP left = 1
        } else if (counter_left == 2) {
            PORTD &= ~(1 << 7); // STEP left = 0
        }
    }

    // Right motor
    counter_right++;
    if (counter_right > current_threshold_right) {
        counter_right = 0;
        int16_t target_r = target_speed_right;
        if (target_r == 0) {
            current_threshold_right = 65535;
        } else if (target_r < 0) {
            current_threshold_right = (uint16_t)(-target_r);
            PORTD |= (1 << 4); // DIR right = 1 (backward)
        } else {
            current_threshold_right = (uint16_t)(target_r);
            PORTD &= ~(1 << 4); // DIR right = 0 (forward)
        }
    }
    if (current_threshold_right != 65535) {
        if (counter_right == 1) {
            PORTD |= (1 << 5); // STEP right = 1
        } else if (counter_right == 2) {
            PORTD &= ~(1 << 5); // STEP right = 0
        }
    }
}
