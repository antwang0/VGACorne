// Copyright 2026 VGACorne contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

// Travel is expressed in distance units: 0 = at rest, 255 = bottomed out.
// With ~4 mm switches one unit is ~16 um, so 0.1 mm is about 6 units.
#define HE_UNITS_PER_TENTH_MM 6

enum {
    HE_FLAG_RAPID_TRIGGER = 0x01, // enable rapid trigger
    HE_FLAG_RT_CONTINUOUS = 0x02, // stay in rapid trigger until the key is fully up
};

typedef struct {
    uint8_t actuation;      // press point (and rapid trigger's arming point)
    uint8_t rt_sensitivity; // rapid trigger: travel needed to re-press / release
    uint8_t rt_release;     // rapid trigger: separate release travel, 0 = same as sensitivity
    uint8_t flags;          // HE_FLAG_*
} he_settings_t;

#define HE_DEFAULT_SETTINGS \
    { .actuation = 96, .rt_sensitivity = 19, .rt_release = 0, .flags = 0 } // 1.5 mm, 0.3 mm

typedef struct {
    uint16_t value;  // filtered reading, oriented so pressing increases it
    uint16_t rest;   // learned at start-up (and when the other half is plugged in)
    uint16_t bottom; // learned while typing
    uint8_t  distance;
    bool     calibrating;
} he_key_info_t;

he_settings_t *he_get_settings(void);
void           he_set_settings(const he_settings_t *settings);

// Relearn rest values for the given ADC inputs (matrix rows); keep hands off
// the keys for HE_CALIBRATION_MS. 0xFF recalibrates everything.
void he_recalibrate(uint8_t input_mask);

bool he_remote_connected(void);
bool he_key_info(uint8_t row, uint8_t col, he_key_info_t *out);
