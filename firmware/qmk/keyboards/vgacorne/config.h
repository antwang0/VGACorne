// Copyright 2026 VGACorne contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "he_wiring.h" // generated from the schematics, incl. the trackpad settings

// Hall-effect settings (actuation, rapid trigger) live in the keyboard datablock.
#define EECONFIG_KB_DATA_SIZE 8

// EEPROM emulation in flash sector 1 (16 KB at 0x08004000). QMK's STM32F4
// linker script keeps that sector free; its legacy wear-leveling driver only
// has presets for the F401/F411, which share the F446's sector layout.
#define WEAR_LEVELING_LEGACY_EMULATION_PAGE_SIZE 16384
#define WEAR_LEVELING_LEGACY_EMULATION_PAGE_COUNT 1
#define WEAR_LEVELING_LEGACY_EMULATION_BASE_PAGE_ADDRESS 0x08004000

// Overridable scan/calibration tuning, see he_matrix.c:
// #define HE_SETTLE_US 10
// #define HE_FILTER_SHIFT 2
// #define HE_CALIBRATION_MS 500
// #define HE_HYSTERESIS 8
