// Host test for libhmk's matrix.c with detachable.patch: simulated sensors and
// cable-detect line, the real matrix code. Build and run with ./run.sh.
// SPDX-License-Identifier: GPL-3.0-or-later
#include <stdio.h>

#include "eeconfig.h"
#include "hardware/hardware.h"
#include "matrix.h"

// --- simulated hardware ------------------------------------------------------
static uint32_t now_ms;
static bool     cable_plugged = true;
static uint16_t raw[NUM_KEYS];  // sensor output in ADC counts
static uint16_t rest[NUM_KEYS]; // this key's sensor output at rest

// A DRV5055 reads ~2400 at rest and falls towards ~1500 as the magnet comes
// down. With the cable out the remote inputs read whatever they float to: use
// 0, which looks like every remote key bottomed out.
static void press(int k, double travel) { raw[k] = (uint16_t)(rest[k] - 900 * travel); }
static void release(int k) { raw[k] = rest[k]; }

void     analog_init(void) {}
void     analog_task(void) { now_ms++; } // one call per main-loop pass, ~1 ms
uint16_t analog_read(uint8_t key) { return key >= 4 && !cable_plugged ? 0 : raw[key]; }
bool     analog_detachable_attached(void) { return cable_plugged; }
uint32_t timer_read(void) { return now_ms; }
bool     wear_leveling_write(uint32_t addr, const void *buf, uint32_t len) {
    (void)addr; (void)buf; (void)len;
    return true;
}

static eeconfig_t      config;
const eeconfig_t      *eeconfig = &config;

// --- helpers -----------------------------------------------------------------
static int failures;
#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        printf("%s  %s\n", (cond) ? "ok  " : "FAIL", msg);                     \
        failures += !(cond);                                                   \
    } while (0)

static int presses_seen; // presses of remote keys over a run() while they should be held
static void run(int ms) {
    for (int i = 0; i < ms; i++) {
        analog_task();
        matrix_scan();
        for (int k = 4; k < NUM_KEYS; k++) presses_seen += key_matrix[k].is_pressed;
    }
}
static bool down(int k) { return key_matrix[k].is_pressed; }
// The learned rest value (in inverted counts) is within the calibration epsilon of the true one.
static bool near_rest(int k) {
    const int want = 4095 - rest[k], got = key_matrix[k].adc_rest_value;
    return got >= want && got <= want + MATRIX_CALIBRATION_EPSILON;
}
static void plug(bool in) { cable_plugged = in; }
static void settle(void) { for (int k = 0; k < NUM_KEYS; k++) release(k); }

int main(void) {
    config.calibration = (eeconfig_calibration_t)DEFAULT_CALIBRATION;
    for (int k = 0; k < NUM_KEYS; k++) {
        config.profiles[0].actuation_map[k].actuation_point = 128; // fixed actuation, no rapid trigger
        rest[k] = (uint16_t)(2400 + 10 * k);
    }
    settle();

    // Boot with the cable in: every key calibrates as before.
    matrix_init();
    run(50);
    CHECK(near_rest(5), "boot, cable in: remote rest value learned");
    press(5, 1.0);
    run(50);
    CHECK(down(5), "boot, cable in: remote key presses");

    // Unplug mid-press: released at once, and the floating inputs press nothing.
    plug(false);
    presses_seen = 0;
    run(1);
    CHECK(!down(5), "unplugged: held remote key released on the next scan");
    run(2000);
    CHECK(presses_seen == 0, "unplugged: no phantom presses in 2 s of garbage readings");
    CHECK(key_matrix[5].adc_bottom_out_value < 3000, "unplugged: garbage doesn't raise the bottom-out value");
    press(1, 1.0);
    run(50);
    CHECK(down(1), "unplugged: local keys still work");
    release(1);
    run(50);

    // Plug back in with the remote rest values shifted by the cable path.
    for (int k = 4; k < NUM_KEYS; k++) rest[k] = (uint16_t)(rest[k] - 60);
    settle();
    plug(true);
    presses_seen = 0;
    press(6, 1.0); // a hand already on the key
    run(MATRIX_CALIBRATION_DURATION - 50);
    CHECK(presses_seen == 0, "re-plugged: remote keys held while they calibrate");
    press(2, 1.0);
    run(20);
    CHECK(down(2), "re-plugged: local keys work during the remote calibration");
    release(2);
    release(6);
    run(100);
    CHECK(near_rest(4), "re-plugged: new remote rest value learned");
    press(4, 1.0);
    run(50);
    CHECK(down(4), "re-plugged: remote key works after calibration");
    release(4);
    run(50);
    CHECK(!down(4), "re-plugged: and releases");

    // Contact bounce while plugging in restarts the calibration.
    plug(false);
    run(10);
    for (int i = 0; i < 5; i++) {
        plug(true);
        run(3);
        plug(false);
        run(2);
    }
    plug(true);
    settle();
    presses_seen = 0;
    press(7, 1.0);
    run(MATRIX_CALIBRATION_DURATION - 10);
    CHECK(presses_seen == 0, "bounce: remote keys held until the cable has been in for the full calibration");
    release(7);
    run(50);
    press(7, 1.0);
    run(50);
    CHECK(down(7), "bounce: remote key works once settled");
    release(7);
    run(50);

    // Boot with the cable out, then plug in.
    plug(false);
    matrix_init();
    presses_seen = 0;
    run(1000);
    CHECK(presses_seen == 0, "boot, cable out: remote keys held");
    settle();
    plug(true);
    run(MATRIX_CALIBRATION_DURATION + 20);
    press(5, 1.0);
    run(50);
    CHECK(down(5), "boot, cable out: remote keys work once plugged in");
    release(5);
    run(50);

    // Recalibrating from the configurator with the cable out keeps them held.
    plug(false);
    run(10);
    matrix_recalibrate(false);
    presses_seen = 0;
    run(500);
    CHECK(presses_seen == 0, "recalibrated with the cable out: remote keys still held");

    printf(failures ? "%d FAILED\n" : "all passed\n", failures);
    return failures != 0;
}
