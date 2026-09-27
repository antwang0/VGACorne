// Copyright 2026 VGACorne contributors
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include_next <mcuconf.h>

// Hall-effect matrix: all six mux outputs are read by ADC1 in one sequence.
#undef STM32_ADC_USE_ADC1
#define STM32_ADC_USE_ADC1 TRUE
