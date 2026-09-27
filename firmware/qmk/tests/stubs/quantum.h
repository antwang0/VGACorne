// Host-side stand-ins for the bits of QMK/ChibiOS that he_matrix.c uses.
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define MATRIX_ROWS 6
#define MATRIX_COLS 8
typedef uint8_t  matrix_row_t;
typedef uint32_t pin_t;
typedef uint16_t adcsample_t;
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

// Pin names used by he_wiring.h: port letter * 16 + number.
#define A0 0
#define A1 1
#define A2 2
#define A3 3
#define A4 4
#define A5 5
#define C1 33
#define C2 34
#define C3 35
#define C4 36

typedef struct { int dummy; } ADCConfig;
typedef struct { int dummy; } ADCDriver;
typedef struct {
    bool     circular;
    uint32_t num_channels;
    void    *end_cb, *error_cb;
    uint32_t cr1, cr2, smpr1, smpr2;
    uint16_t htr, ltr;
    uint32_t sqr1, sqr2, sqr3;
} ADCConversionGroup;
#define ADC_CR2_SWSTART (1u << 30)
#define ADC_SAMPLE_56 3u
#define ADC_SQR1_NUM_CH(n) (((n) - 1) << 20)
#define PAL_MODE_INPUT_ANALOG 3
extern ADCDriver ADCD1;

void     adcStart(ADCDriver *d, const ADCConfig *c);
void     adcConvert(ADCDriver *d, const ADCConversionGroup *g, adcsample_t *buf, int depth);
void     palSetLineMode(pin_t pin, int mode);
void     gpio_set_pin_output(pin_t pin);
void     gpio_set_pin_input(pin_t pin);
void     gpio_write_pin(pin_t pin, int level);
void     gpio_write_pin_low(pin_t pin);
int      gpio_read_pin(pin_t pin);
void     wait_us(uint32_t us);
uint16_t timer_read(void);
uint16_t timer_elapsed(uint16_t since);
