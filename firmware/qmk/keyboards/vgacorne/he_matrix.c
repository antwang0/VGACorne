// Copyright 2026 VGACorne contributors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Hall-effect analog matrix (QMK custom matrix "lite").
//
// Each scan step sets the three mux select lines -- switching all six 8:1 muxes
// at once, three on this half and three on the other half over the VGA cable --
// waits for the outputs to settle, then converts every ADC input in one ADC
// sequence. Eight steps read the whole keyboard. Matrix row = ADC input,
// column = mux channel (see he_wiring.h, generated from the schematics).
//
// Per key: an exponential filter, a rest value learned at start-up, a bottom-out
// value learned while typing, a log-curve map to 0..255 of travel, and then a
// fixed actuation point or rapid trigger.
//
// One mux channel of the other half carries the scroll wheel instead of a key:
// its two encoder contacts summed into one of four levels. The scan keeps that
// reading, and QMK's quadrature driver reads the contacts back through
// encoder_quadrature_read_pin() below.

#include "quantum.h"
#include "he_matrix.h"
#include "he_wiring.h"

#ifndef HE_SETTLE_US
#    define HE_SETTLE_US 10 // after changing the selects; the buffered cable path settles in ~1 us
#endif
#ifndef HE_CALIBRATION_MS
#    define HE_CALIBRATION_MS 500
#endif
#ifndef HE_FILTER_SHIFT
// Filter weight 1/4 per scan. One scan is ~0.23 ms (8 x (settle + 6 conversions)),
// so the time constant is ~0.9 ms: enough to smooth sensor noise without adding
// noticeable latency (1/16 would be ~5 ms).
#    define HE_FILTER_SHIFT 2
#endif
#ifndef HE_BOTTOM_EPSILON
#    define HE_BOTTOM_EPSILON 5 // ADC counts of noise ignored when learning bottom-out
#endif
#ifndef HE_HYSTERESIS
#    define HE_HYSTERESIS 8 // distance units between press and release points
#endif
#ifndef HE_RELEASE_DEADZONE
#    define HE_RELEASE_DEADZONE 4 // continuous rapid trigger: "fully up" below this
#endif

#define ADC_MAX 4095
#define HE_CHANNELS (1 << HE_SELECT_COUNT)

_Static_assert(HE_INPUT_COUNT == MATRIX_ROWS, "matrix rows must be the ADC inputs");
_Static_assert(HE_CHANNELS == MATRIX_COLS, "matrix columns must be the mux channels");

enum { KEY_IDLE, KEY_DOWN, KEY_UP };

typedef struct {
    uint16_t value;
    uint16_t rest;
    uint16_t bottom;
    uint8_t  distance;
    uint8_t  extremum; // rapid trigger: deepest/shallowest point since the last change
    uint8_t  state;
} he_key_t;

static const pin_t   select_pins[HE_SELECT_COUNT] = HE_SELECT_PINS;
static const pin_t   adc_pins[HE_INPUT_COUNT]     = HE_ADC_PINS;
static const uint8_t adc_channels[HE_INPUT_COUNT] = HE_ADC_CHANNELS;
static const uint8_t used_mask[HE_INPUT_COUNT]    = HE_USED_MASK;
static const uint8_t distance_lut[HE_LUT_SIZE]    = HE_DISTANCE_LUT;

static he_key_t      keys[HE_INPUT_COUNT][HE_CHANNELS];
static bool          calibrating[HE_INPUT_COUNT];
static uint16_t      calibration_start[HE_INPUT_COUNT];
static he_settings_t settings = HE_DEFAULT_SETTINGS;
static bool          remote_connected = true;

static ADCConfig          adc_config;
static ADCConversionGroup adc_group;
static adcsample_t        samples[HE_INPUT_COUNT];

#ifdef HE_WHEEL_INPUT
static const uint16_t wheel_levels[4] = HE_WHEEL_LEVELS;
static adcsample_t    wheel_sample    = ADC_MAX; // both contacts open, as with the cable out
#endif

// ---------------------------------------------------------------------------
// Hardware
// ---------------------------------------------------------------------------

static void adc_group_init(void) {
    adc_group = (ADCConversionGroup){
        .circular     = false,
        .num_channels = HE_INPUT_COUNT,
        .cr2          = ADC_CR2_SWSTART,
        .sqr1         = ADC_SQR1_NUM_CH(HE_INPUT_COUNT),
    };
    for (uint8_t i = 0; i < HE_INPUT_COUNT; i++) {
        const uint32_t ch = adc_channels[i];
        if (ch < 10) {
            adc_group.smpr2 |= ADC_SAMPLE_56 << (3 * ch);
        } else {
            adc_group.smpr1 |= ADC_SAMPLE_56 << (3 * (ch - 10));
        }
        if (i < 6) {
            adc_group.sqr3 |= ch << (5 * i);
        } else if (i < 12) {
            adc_group.sqr2 |= ch << (5 * (i - 6));
        } else {
            adc_group.sqr1 |= ch << (5 * (i - 12));
        }
    }
}

static void select_channel(uint8_t channel) {
    for (uint8_t b = 0; b < HE_SELECT_COUNT; b++) {
        gpio_write_pin(select_pins[b], (channel >> b) & 1);
    }
}

static inline uint16_t oriented(adcsample_t sample) {
#if HE_INVERT_ADC
    return ADC_MAX - sample;
#else
    return sample;
#endif
}

// ---------------------------------------------------------------------------
// Calibration and key logic
// ---------------------------------------------------------------------------

static bool is_remote(uint8_t input) {
    return (HE_REMOTE_INPUTS >> input) & 1;
}

void he_recalibrate(uint8_t input_mask) {
    for (uint8_t in = 0; in < HE_INPUT_COUNT; in++) {
        if (!((input_mask >> in) & 1)) continue;
        calibrating[in]       = true;
        calibration_start[in] = timer_read();
        for (uint8_t ch = 0; ch < HE_CHANNELS; ch++) {
            keys[in][ch].state    = KEY_IDLE;
            keys[in][ch].distance = 0;
        }
    }
}

static void finish_calibration(void) {
    for (uint8_t in = 0; in < HE_INPUT_COUNT; in++) {
        if (!calibrating[in] || timer_elapsed(calibration_start[in]) < HE_CALIBRATION_MS) continue;
        if (is_remote(in) && !remote_connected) continue; // wait for the other half
        for (uint8_t ch = 0; ch < HE_CHANNELS; ch++) {
            he_key_t *k = &keys[in][ch];
            k->rest     = k->value;
            k->bottom   = MIN(k->rest + HE_INITIAL_BOTTOM_OUT, ADC_MAX);
        }
        calibrating[in] = false;
    }
}

static uint8_t travel(const he_key_t *k) {
    if (k->value <= k->rest || k->bottom <= k->rest) return 0;
    if (k->value >= k->bottom) return 255;
    const uint32_t index = (uint32_t)(k->value - k->rest) * (HE_LUT_SIZE - 1) / (k->bottom - k->rest);
    return distance_lut[index];
}

static bool actuate(he_key_t *k) {
    const uint8_t d   = k->distance;
    const uint8_t act = settings.actuation;

    if (!(settings.flags & HE_FLAG_RAPID_TRIGGER)) {
        if (k->state == KEY_DOWN) {
            if (d + HE_HYSTERESIS < act) k->state = KEY_IDLE;
        } else if (d >= act) {
            k->state = KEY_DOWN;
        }
        return k->state == KEY_DOWN;
    }

    // Rapid trigger: once past the actuation point, any upward movement of
    // rt_release releases and any downward movement of rt_sensitivity presses.
    // The key is fully reset above the actuation point (or near the top in
    // continuous mode).
    const uint8_t down  = MAX(settings.rt_sensitivity, 1);
    const uint8_t up    = settings.rt_release ? settings.rt_release : down;
    const uint8_t reset = (settings.flags & HE_FLAG_RT_CONTINUOUS) ? HE_RELEASE_DEADZONE : (act > HE_HYSTERESIS ? act - HE_HYSTERESIS : 0);
    switch (k->state) {
        case KEY_IDLE:
            if (d >= act) {
                k->state    = KEY_DOWN;
                k->extremum = d;
            }
            break;
        case KEY_DOWN:
            if (d < reset) {
                k->state = KEY_IDLE;
            } else if (d > k->extremum) {
                k->extremum = d;
            } else if (k->extremum - d >= up) {
                k->state    = KEY_UP;
                k->extremum = d;
            }
            break;
        case KEY_UP:
            if (d < reset) {
                k->state = KEY_IDLE;
            } else if (d < k->extremum) {
                k->extremum = d;
            } else if (d - k->extremum >= down) {
                k->state    = KEY_DOWN;
                k->extremum = d;
            }
            break;
    }
    return k->state == KEY_DOWN;
}

#ifdef HE_DET_PIN
static void update_link(void) {
    const bool connected = !gpio_read_pin(HE_DET_PIN);
    if (connected == remote_connected) return;
    remote_connected = connected;
    // Unplugged: hold the other half released. Plugged in: learn fresh rest
    // values, since the cable path shifts them slightly.
    he_recalibrate(HE_REMOTE_INPUTS);
}
#endif

// ---------------------------------------------------------------------------
// QMK custom matrix
// ---------------------------------------------------------------------------

void matrix_init_custom(void) {
    for (uint8_t b = 0; b < HE_SELECT_COUNT; b++) {
        gpio_set_pin_output(select_pins[b]);
        gpio_write_pin_low(select_pins[b]);
    }
    for (uint8_t in = 0; in < HE_INPUT_COUNT; in++) {
        palSetLineMode(adc_pins[in], PAL_MODE_INPUT_ANALOG);
    }
#ifdef HE_DET_PIN
    gpio_set_pin_input(HE_DET_PIN); // pulled up on the main PCB
    remote_connected = !gpio_read_pin(HE_DET_PIN);
#endif
    adc_group_init();
    adcStart(&ADCD1, &adc_config);
    he_recalibrate(0xFF);
}

bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    bool changed = false;
#ifdef HE_DET_PIN
    update_link();
#endif
    for (uint8_t ch = 0; ch < HE_CHANNELS; ch++) {
        select_channel(ch);
        wait_us(HE_SETTLE_US);
        adcConvert(&ADCD1, &adc_group, samples, 1);

        for (uint8_t in = 0; in < HE_INPUT_COUNT; in++) {
#ifdef HE_WHEEL_INPUT
            if (in == HE_WHEEL_INPUT && ch == HE_WHEEL_CHANNEL) {
                wheel_sample = remote_connected ? samples[in] : ADC_MAX;
            }
#endif
            if (!((used_mask[in] >> ch) & 1)) continue;
            he_key_t *k = &keys[in][ch];
            k->value    = (uint16_t)(((uint32_t)k->value * ((1u << HE_FILTER_SHIFT) - 1) + oriented(samples[in])) >> HE_FILTER_SHIFT);

            bool pressed = false;
            if (!calibrating[in]) {
                if (k->value >= k->bottom + HE_BOTTOM_EPSILON) k->bottom = k->value;
                k->distance = travel(k);
                pressed     = actuate(k);
            }

            const matrix_row_t bit = (matrix_row_t)1 << ch;
            const matrix_row_t row = current_matrix[in];
            const matrix_row_t now = pressed ? (row | bit) : (row & ~bit);
            if (now != row) {
                current_matrix[in] = now;
                changed            = true;
            }
        }
    }
    finish_calibration();
    return changed;
}

// ---------------------------------------------------------------------------
// Scroll wheel
// ---------------------------------------------------------------------------

#ifdef HE_WHEEL_INPUT
// Contact state (A | B << 1, 1 = open) whose level is nearest the last reading.
static uint8_t wheel_state(void) {
    uint8_t  best = 3;
    uint16_t err  = UINT16_MAX;
    for (uint8_t s = 0; s < 4; s++) {
        const uint16_t e = wheel_sample > wheel_levels[s] ? wheel_sample - wheel_levels[s] : wheel_levels[s] - wheel_sample;
        if (e < err) {
            err  = e;
            best = s;
        }
    }
    return best;
}

// QMK's quadrature encoder driver (ENCODER_ENABLE, no ENCODER_A_PINS) calls this
// for each contact instead of reading GPIOs.
uint8_t encoder_quadrature_read_pin(uint8_t index, bool pad_b) {
    (void)index;
    return (wheel_state() >> (pad_b ? 1 : 0)) & 1;
}
#endif

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

he_settings_t *he_get_settings(void) {
    return &settings;
}

void he_set_settings(const he_settings_t *s) {
    // No state reset: held keys (e.g. the layer keys used to reach the HE
    // keycodes) simply meet the new thresholds on the next scan.
    settings = *s;
}

bool he_remote_connected(void) {
    return remote_connected;
}

bool he_key_info(uint8_t row, uint8_t col, he_key_info_t *out) {
    if (row >= HE_INPUT_COUNT || col >= HE_CHANNELS || !((used_mask[row] >> col) & 1)) return false;
    const he_key_t *k = &keys[row][col];
    *out              = (he_key_info_t){k->value, k->rest, k->bottom, k->distance, calibrating[row]};
    return true;
}
