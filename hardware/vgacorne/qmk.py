"""Generated parts of the QMK keyboard (STM32F446 module only).

QMK has no hall-effect feature, so ``firmware/qmk/keyboards/vgacorne`` carries
its own analog matrix (he_matrix.c, hand-written). This module writes the two
files that must track the hardware:

* ``keyboard.json`` -- layout with matrix positions traced from the schematics
  (matrix row = ADC input, column = mux channel), USB IDs, EEPROM, keycodes.
* ``he_wiring.h``   -- select/ADC pins, which inputs arrive over the VGA cable,
  the cable-detect pin, calibration defaults, the travel-curve table, the
  rotary encoder's channel and levels, and the trackpad's I2C bus and driver
  settings.
* ``rules.mk``      -- the hall-effect matrix source and the trackpad driver.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .circuits import ENCODER_PULL_UP, ENCODER_SUM, SENSOR
from .geometry import SATELLITE_SIDE
from .trackpad import MODEL as PAD

MODULE = "module_f446"  # QMK doesn't support the AT32F405
REPO = Path(__file__).resolve().parent.parent.parent
KEYBOARD = REPO / "firmware" / "qmk" / "keyboards" / "vgacorne"
LUT_SIZE = 1024

# QMK crkbd LAYOUT_split_3x6_3 coordinates, in firmware.key_order() order, then
# the satellite's mouse column (M0, M1) just inside the left half.
_ROW_Y_LEFT = [0.3, 0.3, 0.1, 0.0, 0.1, 0.2]
_THUMBS = [(4, 3.7, 1), (5, 3.7, 1), (6, 3.2, 1.5), (8, 3.2, 1.5), (9, 3.7, 1), (10, 3.7, 1)]
_MOUSE = [(6, 1.2, 1), (6, 0.2, 1)]  # M0 beside G, M1 beside T

KEYCODES = [
    ("HE_ACTU", "HE: actuation point deeper"),
    ("HE_ACTD", "HE: actuation point shallower"),
    ("HE_RTTG", "HE: rapid trigger on/off"),
    ("HE_RTSU", "HE: rapid trigger less sensitive"),
    ("HE_RTSD", "HE: rapid trigger more sensitive"),
    ("HE_CALB", "HE: recalibrate (hands off the keys)"),
    ("HE_DBG", "HE: toggle raw-value console output"),
]


def _xy(index: int) -> tuple[float, float, float]:
    if index < 36:
        row, col = divmod(index, 12)
        if col < 6:
            return col, _ROW_Y_LEFT[col] + row, 1
        rcol = col - 6
        return 9 + rcol, _ROW_Y_LEFT[5 - rcol] + row, 1
    if index < 42:
        return _THUMBS[index - 36]
    return _MOUSE[index - 42]


def adc_channel(pin: str) -> int:
    """STM32F4 ADC123 channel for a GPIO name."""
    port, num = pin[0], int(pin[1:])
    base = {"A": (0, 7), "B": (8, 1), "C": (10, 5)}[port]
    if num > base[1]:
        raise ValueError(f"{pin} is not an ADC pin")
    return base[0] + num


def encoder_levels(adc_max: int = 4095) -> list[int]:
    """ADC reading of the rotary encoder's summing node for each contact state.

    Index = A | B << 1, 1 meaning that contact is open (pulled up). A closed
    contact grounds its side, so with one contact open the node sits on the
    divider supply - pull-up - summing R - node - other summing R - ground.
    """
    rp, ra, rb = ENCODER_PULL_UP, ENCODER_SUM["A"], ENCODER_SUM["B"]
    node = [0.0, rb / (rp + ra + rb), ra / (rp + ra + rb), 1.0]
    return [round(adc_max * v) for v in node]


def distance_lut(a: float = SENSOR.travel_curve, n: int = LUT_SIZE) -> list[int]:
    """255 * log(1 + a x) / log(1 + a (n - 1)): field strength vs travel, normalised."""
    return [round(255 * math.log1p(a * x) / math.log1p(a * (n - 1))) for x in range(n)]


def keyboard_json(w) -> dict:
    positions = {}
    for i, row in enumerate(w.matrix):
        for c, key in enumerate(row):
            if key:
                positions[key - 1] = [i, c]
    layout = []
    for idx in range(len(positions)):
        x, y, h = _xy(idx)
        entry = {"matrix": positions[idx], "x": x, "y": y}
        if h != 1:
            entry["h"] = h
        layout.append(entry)
    return {
        "manufacturer": "VGACorne",
        "keyboard_name": "VGACorne",
        "maintainer": "antwang0",
        "processor": "STM32F446",
        "bootloader": "stm32-dfu",
        # pid.codes test ID (libhmk builds use 0x0001/0x0002): request a real PID before distributing.
        "usb": {"vid": "0x1209", "pid": "0x0003", "device_version": "0.1.0", "polling_interval": 1},
        "features": {"bootmagic": False, "extrakey": True, "mousekey": True, "nkro": True,
                     **({"encoder": True} if w.encoder else {})},
        "matrix_size": {"rows": len(w.matrix), "cols": len(w.matrix[0])},
        "matrix_pins": {"custom_lite": True},
        "debounce": 0,
        # ChibiOS's embedded-flash driver doesn't know the F446, so use QMK's legacy
        # driver on flash sector 1 (config.h), which QMK's F4 linker script keeps free.
        "eeprom": {"driver": "wear_leveling",
                   "wear_leveling": {"driver": "legacy", "backing_size": 16384, "logical_size": 2048}},
        "keycodes": [{"key": k, "label": label} for k, label in KEYCODES],
        # The Corne's 42 keys in LAYOUT_split_3x6_3 order, then the mouse column.
        "layouts": {"LAYOUT": {"layout": layout}},
    }


def wiring_h(w) -> str:
    used = [sum(1 << c for c, key in enumerate(row) if key) for row in w.matrix]
    remote = sum(1 << i for i, side in enumerate(w.input_sides) if side == SATELLITE_SIDE[0].upper())
    lut = distance_lut()
    lut_rows = ",\n    ".join(", ".join(f"{v:3d}" for v in lut[i:i + 16]) for i in range(0, len(lut), 16))
    lines = [
        "// Generated by hardware/generate.py firmware from the KiCad schematics -- do not edit.",
        "// SPDX-License-Identifier: GPL-2.0-or-later",
        "#pragma once",
        "",
        "// Mux select lines (bit 0 first) and ADC inputs. Matrix row = ADC input, column = mux channel.",
        f"#define HE_SELECT_COUNT {len(w.select_pins)}",
        f"#define HE_SELECT_PINS {{ {', '.join(w.select_pins)} }}",
        f"#define HE_INPUT_COUNT {len(w.inputs)}",
        f"#define HE_ADC_PINS {{ {', '.join(w.inputs)} }}",
        f"#define HE_ADC_CHANNELS {{ {', '.join(str(adc_channel(p)) for p in w.inputs)} }}",
        f"#define HE_USED_MASK {{ {', '.join(f'0x{m:02X}' for m in used)} }}",
        f"// Inputs that come from the {SATELLITE_SIDE} half over the VGA cable (bit per input).",
        f"#define HE_REMOTE_INPUTS 0x{remote:02X}",
    ]
    if w.det_pin:
        lines += [f"// Low when the {SATELLITE_SIDE} half is connected (1 k to GND there, 10 k pull-up here).",
                  f"#define HE_DET_PIN {w.det_pin}"]
    lines += [
        "",
        f"// Sensor: {SENSOR.mpn}. 1 = its reading falls as a key is pressed; the matrix flips it",
        "// so that pressing always increases the value.",
        f"#define HE_INVERT_ADC {1 if SENSOR.invert_adc else 0}",
        f"#define HE_INITIAL_BOTTOM_OUT {SENSOR.initial_bottom_out_threshold}",
        "",
        f"// Travel curve: 255 * log(1 + a x) / log(1 + a (N - 1)), a = {SENSOR.travel_curve}.",
        f"#define HE_LUT_SIZE {LUT_SIZE}",
        "#define HE_DISTANCE_LUT { \\",
        "    " + lut_rows.replace("\n", " \\\n") + " \\",
        "}",
        "",
    ]
    if w.encoder:
        row, col = w.encoder
        lines += [
            "// Rotary encoder on the satellite's mouse column: its A/B contacts are summed into",
            "// one level on this input and mux channel. Expected readings per contact state",
            "// (index = A | B << 1, 1 = contact open), from circuits.ENCODER_PULL_UP/ENCODER_SUM.",
            "// QMK's quadrature driver reads it through encoder_quadrature_read_pin().",
            f"#define HE_ENCODER_INPUT {row}",
            f"#define HE_ENCODER_CHANNEL {col}",
            f"#define HE_ENCODER_LEVELS {{ {', '.join(str(v) for v in encoder_levels())} }}",
            "#define NUM_ENCODERS 1",
            "",
        ]
    if w.i2c_pins:
        scl, sda = w.i2c_pins
        if {scl, sda} - {"B6", "B7", "B8", "B9"}:
            raise ValueError(f"trackpad I2C on {scl}/{sda}: expected I2C1 (PB6-PB9)")
        lines += [
            f"// Trackpad: {PAD.name}, on I2C1 with 4.7k pull-ups on the main PCB.",
            "#define I2C_DRIVER I2CD1",
            f"#define I2C1_SCL_PIN {scl}",
            f"#define I2C1_SDA_PIN {sda}",
            "#define I2C1_SCL_PAL_MODE 4",
            "#define I2C1_SDA_PAL_MODE 4",
            "#define I2C1_CLOCK_SPEED 400000",
            "#define I2C1_DUTY_CYCLE FAST_DUTY_CYCLE_2",
            *(f"#define {d}" for d in PAD.qmk_defines),
            "",
        ]
    return "\n".join(lines)


def rules_mk() -> str:
    return f"""# Generated by hardware/generate.py firmware -- do not edit.
SRC += he_matrix.c

# Optional trackpad beside Y/H/N: {PAD.name} (hardware/vgacorne/trackpad.py).
# Without a pad fitted, QMK gives up on it after one failed init at boot.
POINTING_DEVICE_ENABLE = yes
POINTING_DEVICE_DRIVER = {PAD.qmk_driver}
"""


def generate(w) -> dict[Path, str]:
    return {
        KEYBOARD / "keyboard.json": json.dumps(keyboard_json(w), indent=2) + "\n",
        KEYBOARD / "he_wiring.h": wiring_h(w),
        KEYBOARD / "rules.mk": rules_mk(),
    }
