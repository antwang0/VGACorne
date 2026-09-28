// Host test for he_matrix.c: simulated sensors behind the real mux/ADC scan.
// Build and run with ./run.sh.
// SPDX-License-Identifier: GPL-2.0-or-later
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "quantum.h"
#include "he_matrix.h"
#include "he_wiring.h"

bool matrix_scan_custom(matrix_row_t current_matrix[]);
void matrix_init_custom(void);
#ifdef HE_WHEEL_INPUT
uint8_t encoder_quadrature_read_pin(uint8_t index, bool pad_b);
#endif

// --- simulated hardware ------------------------------------------------------
ADCDriver       ADCD1;
static uint64_t now_us;
static int      select_state[64];
static bool     cable_plugged = true;
static double   travel[MATRIX_ROWS][MATRIX_COLS]; // 0 = rest, 1 = bottomed out
static int      wheel_ab = 3;                     // scroll wheel contacts, A | B << 1, 1 = open
static int      wheel_offset;                     // ADC counts of supply mismatch between the halves

// A DRV5055 reading as the magnet approaches: rest ~2400, bottom-out ~1500.
// Pressing lowers the raw value (HE_INVERT_ADC = 1). The field grows faster as
// the magnet gets closer; model it as the inverse of the firmware's travel
// curve, so a correct matrix reports distance == travel.
static double field(double t) {
    const double a = 0.0082, n = HE_LUT_SIZE - 1;
    return (exp(t * log1p(a * n)) - 1) / (a * n);
}
static adcsample_t sensor(int row, int col) {
    const bool remote = (HE_REMOTE_INPUTS >> row) & 1;
    if (remote && !cable_plugged) return 4095; // R11-R13 pull the input up
#ifdef HE_WHEEL_INPUT
    if (row == HE_WHEEL_INPUT && col == HE_WHEEL_CHANNEL) {
        const uint16_t levels[] = HE_WHEEL_LEVELS;
        const int      v        = levels[wheel_ab] + wheel_offset;
        return (adcsample_t)(v < 0 ? 0 : v > 4095 ? 4095 : v);
    }
#endif
    return (adcsample_t)(2400 + 7 * row + col - 900.0 * field(travel[row][col]));
}

void adcStart(ADCDriver *d, const ADCConfig *c) { (void)d; (void)c; }
void adcConvert(ADCDriver *d, const ADCConversionGroup *g, adcsample_t *buf, int depth) {
    (void)d; (void)depth;
    const pin_t sel[] = HE_SELECT_PINS;
    int ch = 0;
    for (int b = 0; b < HE_SELECT_COUNT; b++) ch |= select_state[sel[b]] << b;
    // Decode the programmed sequence so a wrong SQR/SMPR setup shows up here.
    const uint8_t expect[] = HE_ADC_CHANNELS;
    for (uint32_t i = 0; i < g->num_channels; i++) {
        const uint32_t adc_ch = (g->sqr3 >> (5 * i)) & 0x1F;
        assert(adc_ch == expect[i]);
        buf[i] = sensor((int)i, ch);
    }
    now_us += 18;
}
void     palSetLineMode(pin_t pin, int mode) { (void)pin; (void)mode; }
void     gpio_set_pin_output(pin_t pin) { (void)pin; }
void     gpio_set_pin_input(pin_t pin) { (void)pin; }
void     gpio_write_pin(pin_t pin, int level) { select_state[pin] = level ? 1 : 0; }
void     gpio_write_pin_low(pin_t pin) { select_state[pin] = 0; }
int      gpio_read_pin(pin_t pin) { return pin == HE_DET_PIN ? !cable_plugged : 0; }
void     wait_us(uint32_t us) { now_us += us; }
uint16_t timer_read(void) { return (uint16_t)(now_us / 1000); }
uint16_t timer_elapsed(uint16_t since) { return (uint16_t)(timer_read() - since); }

// --- helpers -------------------------------------------------------------------
static matrix_row_t matrix[MATRIX_ROWS];

static void scan_ms(int ms) {
    const uint64_t end = now_us + (uint64_t)ms * 1000;
    while (now_us < end) matrix_scan_custom(matrix);
}
static bool down(int row, int col) { return (matrix[row] >> col) & 1; }
static int  pressed_count(void) {
    int n = 0;
    for (int r = 0; r < MATRIX_ROWS; r++) n += __builtin_popcount(matrix[r]);
    return n;
}
static void press_to(int row, int col, double t) {
    travel[row][col] = t;
    scan_ms(5);
}

#define CHECK(cond, msg)                                    \
    do {                                                    \
        if (!(cond)) {                                      \
            printf("FAIL: %s (line %d)\n", msg, __LINE__);  \
            return 1;                                       \
        }                                                   \
        printf("ok   %s\n", msg);                           \
    } while (0)

int main(void) {
    he_settings_t s = HE_DEFAULT_SETTINGS;
    he_set_settings(&s);
    matrix_init_custom();

    scan_ms(100);
    CHECK(pressed_count() == 0, "no presses while calibrating");
    scan_ms(500);
    he_key_info_t k;
    he_key_info(0, 0, &k);
    CHECK(!k.calibrating && k.rest > 1600 && k.rest < 1720, "rest value learned from idle readings");

    // Teach the bottom-out once, as a first keystroke would.
    press_to(0, 0, 1.0);
    press_to(0, 0, 0.0);
    he_key_info(0, 0, &k);
    CHECK(k.bottom >= k.rest + 880, "bottom-out learned from a full press");

    press_to(0, 0, 0.50);
    he_key_info(0, 0, &k);
    CHECK(k.distance > 118 && k.distance < 138, "distance tracks travel (50% -> ~128)");
    press_to(0, 0, 0.30);
    CHECK(!down(0, 0), "not pressed above the actuation point (1.5 mm of 4)");
    press_to(0, 0, 0.60);
    CHECK(down(0, 0) && pressed_count() == 1, "pressed past the actuation point, only that key");
    press_to(0, 0, 0.50);
    CHECK(down(0, 0), "held inside the hysteresis band");
    press_to(0, 0, 0.0);
    CHECK(!down(0, 0), "released at rest");

    // Unused mux channels (tied to GND) never register.
    CHECK(pressed_count() == 0, "unused channels stay quiet");

    // Right half: row 3 is remote. Full press, then rapid trigger.
    press_to(3, 0, 1.0);
    press_to(3, 0, 0.0);
    s.flags |= HE_FLAG_RAPID_TRIGGER;
    he_set_settings(&s);
    press_to(3, 0, 0.70);
    CHECK(down(3, 0), "rapid trigger: pressed past actuation");
    press_to(3, 0, 0.60);
    CHECK(!down(3, 0), "rapid trigger: released by a short lift while still past the actuation point");
    press_to(3, 0, 0.70);
    CHECK(down(3, 0), "rapid trigger: re-pressed by a short push");
    press_to(3, 0, 0.0);
    CHECK(!down(3, 0), "rapid trigger: fully released at rest");

    // Cable unplugged mid-press: the remote half releases and stays quiet.
    s.flags = 0;
    he_set_settings(&s);
    press_to(4, 1, 1.0);
    press_to(4, 1, 0.8);
    CHECK(down(4, 1), "remote key held before unplugging");
    cable_plugged = false;
    scan_ms(2000);
    CHECK(!down(4, 1) && pressed_count() == 0, "unplugged: remote keys released, no phantom presses");
    travel[4][1] = 0.0;
    cable_plugged = true;
    scan_ms(100);
    he_key_info(4, 1, &k);
    CHECK(k.calibrating && pressed_count() == 0, "re-plugged: remote rows recalibrate");
    scan_ms(600);
    press_to(4, 1, 1.0);
    CHECK(down(4, 1), "re-plugged: remote key works again");
    press_to(4, 1, 0.0);

    // Local keys are unaffected by the remote half's calibration.
    press_to(1, 2, 1.0);
    CHECK(down(1, 2), "local key works throughout");
    press_to(1, 2, 0.0);

#ifdef HE_WHEEL_INPUT
    // Scroll wheel: one detent walks the contacts through a Gray-code cycle. Each
    // state must decode, even with the two halves' supplies ~100 mV apart.
    const int cycle[] = {3, 1, 0, 2, 3, 2, 0, 1, 3};
    bool      decoded = true;
    for (int off = -120; off <= 120; off += 120) {
        wheel_offset = off;
        for (unsigned i = 0; i < sizeof cycle / sizeof cycle[0]; i++) {
            wheel_ab = cycle[i];
            scan_ms(1);
            const int got = encoder_quadrature_read_pin(0, false) | encoder_quadrature_read_pin(0, true) << 1;
            decoded &= got == cycle[i];
        }
    }
    CHECK(decoded, "wheel: every contact state decodes from its summed level");
    CHECK(pressed_count() == 0, "wheel: its channel never registers as a key");
    wheel_ab      = 0;
    cable_plugged = false;
    scan_ms(10);
    CHECK((encoder_quadrature_read_pin(0, false) | encoder_quadrature_read_pin(0, true) << 1) == 3,
          "wheel: cable out reads as a resting wheel");
    cable_plugged = true;
#endif

    printf("all passed\n");
    return 0;
}
