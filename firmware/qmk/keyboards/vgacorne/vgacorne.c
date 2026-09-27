// Copyright 2026 VGACorne contributors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Keyboard-level glue: hall-effect settings in EEPROM and the HE_* keycodes.

#include QMK_KEYBOARD_H
#include "he_matrix.h"

#define STEP HE_UNITS_PER_TENTH_MM

typedef struct {
    he_settings_t he;
} kb_config_t;

_Static_assert(sizeof(kb_config_t) <= EECONFIG_KB_DATA_SIZE, "raise EECONFIG_KB_DATA_SIZE");

static kb_config_t config;
static bool        debug_values;

void eeconfig_init_kb_datablock(void) {
    config = (kb_config_t){.he = HE_DEFAULT_SETTINGS};
    eeconfig_update_kb_datablock(&config, 0, sizeof(config));
}

static void save(void) {
    config.he = *he_get_settings();
    eeconfig_update_kb_datablock(&config, 0, sizeof(config));
}

void keyboard_post_init_kb(void) {
    if (!eeconfig_is_kb_datablock_valid()) {
        eeconfig_init_kb_datablock();
    }
    eeconfig_read_kb_datablock(&config, 0, sizeof(config));
    he_set_settings(&config.he);
    keyboard_post_init_user();
}

static uint8_t clamp_step(uint8_t value, int8_t delta, uint8_t lo, uint8_t hi) {
    const int v = value + delta;
    return v < lo ? lo : v > hi ? hi : v;
}

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_user(keycode, record)) return false;
    if (keycode < HE_ACTU || keycode > HE_DBG) return true;
    if (!record->event.pressed) return false;

    he_settings_t s = *he_get_settings();
    switch (keycode) {
        case HE_ACTU:
            s.actuation = clamp_step(s.actuation, STEP, STEP, 250);
            break;
        case HE_ACTD:
            s.actuation = clamp_step(s.actuation, -STEP, STEP, 250);
            break;
        case HE_RTTG:
            s.flags ^= HE_FLAG_RAPID_TRIGGER;
            break;
        case HE_RTSU:
            s.rt_sensitivity = clamp_step(s.rt_sensitivity, STEP / 2, 2, 120);
            break;
        case HE_RTSD:
            s.rt_sensitivity = clamp_step(s.rt_sensitivity, -(STEP / 2), 2, 120);
            break;
        case HE_CALB:
            he_recalibrate(0xFF);
            return false;
        case HE_DBG:
            debug_values = !debug_values;
            return false;
    }
    he_set_settings(&s);
    save();
#ifdef CONSOLE_ENABLE
    uprintf("HE: actuation %u, rapid trigger %s, sensitivity %u\n", s.actuation,
            (s.flags & HE_FLAG_RAPID_TRIGGER) ? "on" : "off", s.rt_sensitivity);
#endif
    return false;
}

#ifdef CONSOLE_ENABLE
// With HE_DBG on, print every key that is off its rest value, 4x a second.
// Use it at bring-up to check polarity (invert_adc) and calibration.
void housekeeping_task_kb(void) {
    static uint16_t last;
    if (!debug_values || timer_elapsed(last) < 250) return;
    last = timer_read();
    uprintf("HE: right half %s\n", he_remote_connected() ? "connected" : "absent");
    for (uint8_t row = 0; row < MATRIX_ROWS; row++) {
        for (uint8_t col = 0; col < MATRIX_COLS; col++) {
            he_key_info_t k;
            if (he_key_info(row, col, &k) && (k.distance || k.calibrating)) {
                uprintf("  [%u,%u] value %4u rest %4u bottom %4u distance %3u%s\n", row, col, k.value, k.rest,
                        k.bottom, k.distance, k.calibrating ? " (calibrating)" : "");
            }
        }
    }
}
#endif
