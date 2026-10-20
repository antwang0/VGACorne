// Build settings for the host test (stand-ins for what libhmk's make.py defines).
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#define NUM_PROFILES 1
#define NUM_LAYERS 1
#define NUM_KEYS 8
#define NUM_ADVANCED_KEYS 1
#define NUM_DYNAMIC_KEYSTROKE_MAX_BINDINGS 4
#define NUM_MACRO_NODES 1
#define DEFAULT_CALIBRATION {.initial_rest_value = 2400, .initial_bottom_out_threshold = 400}
#define DEFAULT_KEYMAPS {{{0}}}

#define FLASH_SIZE 524288
#define WL_VIRTUAL_SIZE 8192
#define WL_WRITE_LOG_SIZE 65536

#define F_CPU 180000000
#define ADC_RESOLUTION 12
#define ADC_NUM_CHANNELS 16
#define ADC_NUM_RAW_INPUTS 8
#define ADC_RAW_INPUT_CHANNELS {0, 1, 2, 3, 4, 5, 6, 7}
#define ADC_RAW_INPUT_VECTOR {0, 1, 2, 3, 4, 5, 6, 7}
#define MATRIX_INVERT_ADC_VALUES // as on VGACorne: pressing lowers the sensor output

// Keys 0-3 are local; keys 4-7 come over the cable.
#define DETACHABLE_KEYS {4, 5, 6, 7}
#define DETACHABLE_DETECT_ACTIVE_LOW
