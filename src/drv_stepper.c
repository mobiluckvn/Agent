#include "drv_stepper.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdbool.h>

static volatile int16_t target_left = 0;
static volatile int16_t target_right = 0;

static uint16_t counter_left = 0;
static uint16_t current_thr_left = 0;
static bool is_stopped_left = true;

static uint16_t counter_right = 0;
static uint16_t current_thr_right = 0;
static bool is_stopped_right = true;

void stepper_init(void) {
    // Cấu hình các chân điều khiển động cơ là output
    DDRD |= (1 << PD4) | (1 << PD5) | (1 << PD6) | (1 << PD7);
    PORTD &= ~((1 << PD4) | (1 << PD5) | (1 << PD6) | (1 << PD7));

    // ref: ds-atme-timer2-01, ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf, tr.155,165-166
    TCCR2A = 0;
    TCCR2B = 0;
    TCCR2B |= (1 << CS21);      // chia trước 8 -> 16 MHz/8 = 2 MHz, mỗi nhịp 0,5 µs
    OCR2A  = 39;                // (39+1) * 0.5 µs = 20 µs
    TCCR2A |= (1 << WGM21);     // Chế độ CTC
    TIMSK2 |= (1 << OCIE2A);    // Cho phép ngắt so khớp A
}

void stepper_set_speed(int16_t left, int16_t right) {
    cli();
    target_left = left;
    target_right = right;
    sei();
}

ISR(TIMER2_COMPA_vect) {
    // Xử lý động cơ trái (STEP = PD7, DIR = PD6, Tiến DIR = 1)
    if (is_stopped_left) {
        PORTD &= ~(1 << PD7); // Đảm bảo STEP ở mức thấp khi dừng
        int16_t t = target_left;
        if (t != 0) {
            is_stopped_left = false;
            counter_left = 0;
            if (t > 0) {
                current_thr_left = (uint16_t)t;
                PORTD |= (1 << PD6);
            } else {
                current_thr_left = (uint16_t)(-t);
                PORTD &= ~(1 << PD6);
            }
        }
    } else {
        counter_left++;
        if (counter_left > current_thr_left) {
            counter_left = 0;
            int16_t t = target_left;
            if (t == 0) {
                is_stopped_left = true;
            } else {
                if (t > 0) {
                    current_thr_left = (uint16_t)t;
                    PORTD |= (1 << PD6);
                } else {
                    current_thr_left = (uint16_t)(-t);
                    PORTD &= ~(1 << PD6);
                }
            }
        }
        
        if (is_stopped_left) {
            PORTD &= ~(1 << PD7);
        } else {
            if (counter_left == 1) {
                PORTD |= (1 << PD7);
            } else {
                PORTD &= ~(1 << PD7);
            }
        }
    }

    // Xử lý động cơ phải (STEP = PD5, DIR = PD4, Tiến DIR = 0)
    if (is_stopped_right) {
        PORTD &= ~(1 << PD5); // Đảm bảo STEP ở mức thấp khi dừng
        int16_t t = target_right;
        if (t != 0) {
            is_stopped_right = false;
            counter_right = 0;
            if (t > 0) {
                current_thr_right = (uint16_t)t;
                PORTD &= ~(1 << PD4);
            } else {
                current_thr_right = (uint16_t)(-t);
                PORTD |= (1 << PD4);
            }
        }
    } else {
        counter_right++;
        if (counter_right > current_thr_right) {
            counter_right = 0;
            int16_t t = target_right;
            if (t == 0) {
                is_stopped_right = true;
            } else {
                if (t > 0) {
                    current_thr_right = (uint16_t)t;
                    PORTD &= ~(1 << PD4);
                } else {
                    current_thr_right = (uint16_t)(-t);
                    PORTD |= (1 << PD4);
                }
            }
        }
        
        if (is_stopped_right) {
            PORTD &= ~(1 << PD5);
        } else {
            if (counter_right == 1) {
                PORTD |= (1 << PD5);
            } else {
                PORTD &= ~(1 << PD5);
            }
        }
    }
}
