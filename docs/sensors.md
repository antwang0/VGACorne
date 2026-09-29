# Hall-effect sensor options

VGACorne reads each key with a linear magnetic sensor on the PCB underside,
directly under the switch, through the 1.6 mm board. The sensor sees the stem
magnet's field along the switch axis (perpendicular to the PCB). It runs at
3.3 V, ratiometric to the ADC reference, and drives the analog muxes through
1 kΩ and 4.7 nF (R3nn, C2nn). The footprint is SOT-23 with **pin 1 VCC,
pin 2 OUT, pin 3 GND** (TI's DBZ pinout).

**Choice: TI DRV5055A3** (`SENSOR` in `hardware/vgacorne/circuits.py`).
- It is the best-documented drop-in part at 3.3 V: sensitivity to ±5 %, a
  guaranteed range and a full noise specification.
- It never saturates with any common switch, whichever pole faces it.
- It draws the least current of the well-documented drop-ins, provided you get
  the new LBC9 silicon ([power budget](architecture.md#power-budget-usb-500-ma)).
- It is cheap and in stock.

The **MT9102ET** is the second source: the HE60 v2 uses it, and libhmk's
defaults were tuned on it. Researched September 2026; prices and stock are
LCSC's on 2026-09-29, per part at 50. **(U)** marks figures not confirmed
from a manufacturer document.

## Field at the sensor

Switch makers quote the flux on the switch axis under a 1.2 mm or 1.6 mm PCB
with the switch seated. Converting those figures to our geometry used an
on-axis cylinder-magnet model: it reproduces TTC's own 1.2 mm → 1.6 mm figures
to within 0.5 mT. The DRV5055's sensing element sits 0.65 mm above its
seating plane. Two readings of the vendor figures give two estimates:

- **Likely:** the vendor figure is what an SOT-23 under that PCB reads.
  libhmk's defaults point this way.
- **Conservative:** the vendor figure is at the bare PCB underside, so our
  element is a further 0.65 mm away.

**All values are estimates, not measurements**; 1 Gs = 0.1 mT.

| Switch | Pole down | Published (Gs, rest / bottom-out) | Our sensor, likely (mT) | Our sensor, conservative (mT) |
|---|---|---|---|---|
| Gateron Jade Pro and most Gateron HE (Gaming, Delta, Air, Black Lotus…) | N | 120 / 700 at 1.2 mm | 10 → 54 | 8 → 37 |
| Gateron Magnetic Jade (original) | N | 120 / 700 (Wooting lists 800) | 10 → 54–60 | 8 → 37–40 |
| Gateron Jade Ultra, Dragon, Spark; MCHOSE Apollo | N | 120 / 550–570 at 1.2 mm | 10 → 44 | 8 → 31 |
| Gateron KS-20 | N | 102 / 905, PCB not stated | 9 → 68 | 7 → 44 |
| GEON Raw HE (libhmk's reference switch) | N (inferred) | 160 / 720, PCB not stated | 14–16 → 58–72 | 11–13 → 42–51 |
| TTC King, Magneto, Helios | N | 90 / 480 at 1.6 mm | 9 → 48 | 7 → 32 |
| Kailh Jellyfish / Source | Mist N; Lava, Flame S | 100 / 640 at 1.2 mm (U) | 8.5 → 49 | 7 → 32 |
| Outemu Amethyst | not published | 95 / 580 at 1.6 mm (reseller) | 9.5 → 58 | 7 → 38 |
| Wooting Lekker | not published | not published | – | – |

- **Range:** a sensor for this board should span roughly 0–75 mT on one side
  of zero.
  - The DRV5055A3 (±88 mT) never saturates. It uses about 15–30 % of its output
    span, roughly 400–1,100 ADC counts over the travel (12–19 % in the
    conservative case).
  - ±40–48 mT parts clip with the stronger switches.
- **Bottom-out threshold:** the firmware's starting value is 400 counts (~20 mT)
  and grows as keys are pressed. HE60's 650 counts (~35 mT) could exceed the
  whole swing of the weaker switches.
- **Polarity:** most switches put the N pole down, but not all, and mounting
  the sensor underneath flips the sign again. A bipolar sensor copes with
  either (`invert_adc`); a unipolar one reads nothing with the wrong pole.

## Options

| Part | Type | Drop-in? | Current at 3.3 V (typ / max) | Sensitivity, range at 3.3 V | Noise | Output load | LCSC price / stock | Verdict |
|---|---|---|---|---|---|---|---|---|
| **TI DRV5055A3** | Hall, bipolar, ratiometric | Yes | 2 / 4 mA (LBC9 parts); 6 / 10 mA (older LBC8) | 15 mV/mT ±5 %, ±88 mT | 3 mV pk-pk (0.2 mT, 20 kHz) | No capacitor straight on OUT; 1 kΩ first is fine | $0.33 / 5.9k | **Used.** Safe range, best documented |
| TI DRV5055A2 | same | Yes | same | 30 mV/mT, ±44 mT | 0.2 mT pk-pk | same | $0.49 / 6.8k | Double resolution, but clips with most switches (likely case). Only if measured peaks stay under ~40 mT |
| TI DRV5056A3 | Hall, **unipolar** (rests at 0.6 V) | Yes | 6 / 10 mA | 30 mV/mT, 0–78 mT | 6 mV pk-pk | same | $0.82 / 65 | About 2× the signal (30–70 % of span, no clipping), but only with N-pole-down switches, and low stock |
| **MT9102ET** (MagnTek / NOVOSENSE) | Hall, bipolar, ratiometric | Yes | 6.0 / 7.0 mA | 16 mV/mT, ±85 mT | 0.19 µT/√Hz (U: also lists 2.44 mV rms) | ≤ 10 nF directly; ≥ 4.7 kΩ | $0.28 / 5.4k | **Second source.** HE60 v2 and libhmk default. Reads the other way round from the DRV5055 in HE60's tests |
| TI TMAG5253BA3 | Hall, ratiometric; output off when disabled | No: X2SON-4 | 2.6 / 5 mA; 8 nA disabled | 15 mV/mT ±15 %, ±80 mT | 0.17 mT pk-pk | ≤ 1 nF | $0.42 / 10.7k | Future revision: shared ADC lines could replace the muxes |
| Semiment SC4702 / SC4703 | Hall, ratiometric ("-N" flips polarity) | Yes | 0.7 mA typ, no max | 20 mV/mT, ±72.5 mT / 30 mV/mT, ±48 mT | 6 / 9 mV pk-pk (filtered) | ≤ 470 pF | $0.13 / 2.5k | Very low power, targets magnetic keyboards; a new part with a thin datasheet. Trial only |
| Melexis MLX90290 (3.3 V trims) | Hall, ratiometric | Yes (TSOT-3) | 5 / 8 mA | 12.4–33 mV/mT | not given | ≤ 10 nF; ≥ 5 kΩ | 0 stock | Good part, not stocked |
| Allegro A1315 / A1304 | Hall, ratiometric | Check: SOT-23W, wider pad spacing | 7.7 / 10 mA; 7.7 / 9 mA | 13.5–25 / 5–40 mV/mT | 13 mV pk-pk | ≤ 10 nF | A1304 $0.70 / 1.5k | Higher current. A1318/19 not for new designs; A1308/09 5 V only |
| SS39ET, GH39FKSW, OH49E-S, other 49E clones | Hall, sourcing output (~65 µA pull-down) | Physically yes, but datasheets number the pins the TO-92 way | 4–6 mA (specified at 5 V) | ~9–13 mV/mT at 3.3 V (U); output only ~1 V from each rail | mostly not given | Weak sink | $0.09–0.30; OH49E-S out of stock | Avoid: no 3.3 V specs, uses about half the ADC range |
| TI DRV5053 / DRV5057 | Hall | Yes | 2.7 mA / 6 mA | DRV5053: saturates at ~±9 mT, not ratiometric. DRV5057: PWM | – | – | – | No (the Lucca 58HE's end-of-travel dead zone) |
| MDT TMR2617S-AAC | **TMR**, Z-axis, ratiometric, factory-programmed | Yes | ≤ 0.3 mA | -0.500 code ≈ 16.5 mV/mT, ±90 mT; output **falls** as the field rises | ≤ 10 mV pk-pk (max, 5 kHz); hysteresis 2.5 %FS | ≥ 10 kΩ, ≤ 10 nF; 1.5 mA abs max out | $0.50 ($0.20 at 200+) / 0 | Bench-test candidate. Low power, but no better noise, has hysteresis, and must be ordered pre-programmed |
| MDT TMR2615, TMR2103/H, TMR215x; Allegro CT100; GMR/AMR | TMR/GMR/AMR, **in-plane** | No | 0.07–0.24 mA | TMR2103 saturates at 7.5 mT | – | TMR2103 is a bridge needing an amplifier | 0 | No: senses the wrong axis directly under the stem |
| MDT TMR2583/2584, TMR265xDD | TMR, Z-axis | No | 1–5 mA | TMR2584 saturates at ±30 mT | – | Bridges; TMR265x in DFN6 | 0 / Digi-Key | No |

## Notes

- **49E pin numbering:**
  - 49E-class datasheets number SOT-23 pins the TO-92 way (1 VCC, 2 GND, 3 OUT),
    even though the parts are physically the same as the DRV5055. VCC is
    bottom-left, OUT bottom-right and GND on the lone top pin.
  - Place them by pad position, not by the table.
  - Don't order TO-92 versions.
- **Polarity:**
  - Diodes and Hallwee state that their SOT-23 dies are flipped relative to
    their TO-92 versions.
  - HE60 found the GH39FKSW and DRV5055A3 inverted relative to the MT9102ET and
    SS39ET.
  - A bipolar part only needs `invert_adc`. That also chooses the
    cable-unplugged pulls (R11–R13 or R14–R16), so changing sensor family means
    regenerating both.
- **Unipolar parts** (DRV5056, TMAG5253UA): TI's convention with the sensor on
  the underside gives positive field for an N pole facing the PCB. The HE60
  README's inversion notes don't all agree with that, so bench-check one
  switch first.
- **TMR in practice:**
  - Only Z-axis parts work under the stem; in-plane parts must sit beside the
    switch.
  - The shipping "TMR keyboards" don't name their chips. MDT markets the
    TMR2617S as a pin-compatible replacement for SOT-23 linear Hall sensors in
    magnetic keyboards.
  - Its main benefit, microamp current, matters little on a wired board.
  - To try one on this board:
    - Flip `invert_adc` and adjust the calibration defaults.
    - Raise R3nn to about 2.2 kΩ, so the empty 4.7 nF cap can't pull more than
      its 1.5 mA output limit at power-up.
- **Measure before changing sensitivity.** Read the raw ADC at rest and at
  bottom-out with the switches you'll use (the QMK build's `HE_DBG`, or
  hmkconf). Then:
  - Peak under ~40 mT: a DRV5055A2 doubles the resolution on the same
    footprint.
  - Peak under ~75 mT with every switch N-pole down: a DRV5056A3 does the same.
- **Changing the sensor:**
  1. Edit `SENSOR` (`lib_id`, `mpn`, `invert_adc`, calibration defaults).
  2. Run `generate.py --force schematics pcbs` and `generate.py firmware bom`.
  3. Re-fit the QMK travel curve (`travel_curve`) to the new sensor.

## Sources

- TI: [DRV5055](https://www.ti.com/lit/ds/symlink/drv5055.pdf) (SBAS640C),
  [DRV5056](https://www.ti.com/lit/ds/symlink/drv5056.pdf),
  [TMAG5253](https://www.ti.com/lit/ds/symlink/tmag5253.pdf),
  [DRV5053](https://www.ti.com/lit/ds/symlink/drv5053.pdf),
  [DRV5057](https://www.ti.com/lit/ds/symlink/drv5057.pdf).
  LBC8/LBC9 current: TI E2E threads
  [1316266](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1316266/drv5055-drv5055) and
  [1680901](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1680901/drv5055-drv5055a1qdbz-supply-current-changes).
- [MT9102 (NOVOSENSE)](https://www.novosns.com/datasheet/MT9102A/MT9102.pdf);
  [Melexis MLX90290](https://www.melexis.com/-/media/files/documents/datasheets/mlx90290-datasheet-melexis.pdf);
  Allegro [A1315](https://www.allegromicro.com/-/media/files/datasheets/a1315-datasheet.pdf),
  [A1304](https://www.allegromicro.com/-/media/files/datasheets/a1304-datasheet.pdf),
  [CT100](https://www.allegromicro.com/-/media/files/datasheets/ct100-datasheet.pdf);
  [Diodes AH49E](https://www.diodes.com/assets/Datasheets/AH49E.pdf).
  OH49E-S, GH39FKSW, SC4702/4703 and the JSMSEMI/Hallwee clones: the PDFs
  linked from LCSC C85573, C266230, C52993621, C49021369 and C7420984.
- MDT (Dowaytech): [TMR linear sensors](https://www.dowaytech.com/en/sensor/magnetic_field_sensors.html),
  [TMR2617S for magnetic keyboards](https://www.dowaytech.com/News-TMR2617S-Linear-Sensors-for-Magnetic-Axis-Keyboards.html).
- Switch flux: Gateron [Jade Pro](https://www.gateron.com/products/gateron-magnetic-jade-pro-switch-set),
  [Magnetic Jade](https://www.gateron.com/products/gateron-magic-jade-switch),
  [Jade Ultra](https://www.gateron.com/products/gateron-magnetic-jade-ultra-switch-set),
  [KS-20 White](https://www.gateron.com/products/gateron-ks-20-magnetic-white-switch-set);
  [GEON Raw HE](https://geon.works/products/geon-raw-he-switch);
  TTC [RGB King](https://ttcswitches.com/products/ttc-rgb-lighting-linear-magnetic-switch-rapid-trigger-35gf-magnetic-gaming-keyboard-switch),
  [Helios](https://ttcswitches.com/products/ttc-helios-he-magnetic-switch-new-arrival);
  [Kailh](https://kailhswitch.net/blogs/news/kailhs-source-series-magnetic-shaft-is-on-the-scene);
  [Outemu via Yushakobo](https://shop.yushakobo.jp/products/10316);
  [Akko magnetic-switch FAQ](https://en.akkogear.com/faq/compatible-magnetic-switches-for-akko-magnetic-keyboards/).
- Open source: [HE60](https://github.com/peppapighs/HE60) (README, BOMs),
  [libhmk](https://github.com/peppapighs/libhmk) (`include/distance.h`, keyboard configs),
  [Lucca 58HE](https://github.com/Maka8295/Lucca-58HE).
