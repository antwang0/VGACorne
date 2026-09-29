# Ordering, assembly and bring-up

## Before ordering

- [ ] Route the main and satellite PCBs. Run `hardware/generate.py check`:
      it must show 0 DRC errors, and after routing `unconnected_items` should
      reach 0 too.
- [ ] If you swapped mux channels while routing, run `generate.py firmware`.
- [ ] Check the AT32F405RCT7 pinout against Artery's datasheet (it was taken
      from the HE60 reference board), and the STM32F446RET6 module against ST's
      (VCAP value in particular).
- [ ] Pick a vertical DE-15F with 4-40 inserts that matches
      `DSUB-15-HD_Socket_Vertical_P2.29x1.98mm_MountingHoles`.
- [ ] Check stock for the DRV5055A3QDBZR (or an HE60-proven alternative:
      MT9102ET, SS39ET, GH39FKSW; see *Sensor polarity* below).

## What to order

| Item | Qty | Notes |
|---|---|---|
| Main PCB (right half), 2-layer 1.6 mm | 1 | bottom-side assembly, plus the trackpad FFC connector J5 on top (hand-solderable); J4 is bare landing pads for the module |
| MCU module, 2-layer **1.0 mm**, castellated holes | 1 | AT32F405 (libhmk, 8 kHz) or STM32F446 (QMK / libhmk); everything on top. Order with JLC's castellated-hole option |
| Satellite PCB (left half), 2-layer 1.6 mm | 1 | bottom-side assembly, plus the rotary encoder ENC1 on top (hand-solder) |
| VGA daughterboard | 2 | hand-solder: DE-15, 10-wire pigtail, 0402 cap |
| Plate (aluminium DXF or FR4 KiCad board) | 1 + 1 mirrored | |
| HE switches (Gateron KS-20 magnetic, GEON Raw HE, ...) | 44 | 42 + the two mouse-button keys |
| Bourns PEC12R-4220F-N0024 encoder | 1 | knob beside B (left half) |
| Knob, ~16 mm across, 14 mm tall, 6 mm D-shaft | 1 | any keyboard/audio knob up to ~18 mm across |
| M2 hex standoffs 3.5 mm, brass | 15 | plus 30 × M2 × 3 mm screws |
| 10-pin JST-SH pigtail, ~5 cm, single-ended | 2 | plugs into J3, right in front of the daughterboard |
| VGA cable, male–male | 1 | the classic blue monitor cable is fine. It needs pins 1–3, 5–10 and 12–15 (check pin 9, see JP1/JP2 below). Both ends plug into the back of the case, so ~30 cm reaches round behind the gap |
| Azoteq TPS65-201A-S trackpad (optional) | 1 | end-of-life at Azoteq and out of stock at LCSC; Keycapsss still sells it. GR-Trackpad65 is an open clone |
| Trackpad overlay, 1 mm glass or acrylic, 71 × 55 mm, ~7 mm corners | 1 | non-metal, matte/etched top; laser-cut black acrylic works |
| 6-pin 0.5 mm FFC, same-side contacts, ~30 mm | 1 | trackpad to J5 (Jushuo AFC07-S06FCA-00, LCSC C262553) |
| Poron/silicone gaskets, case foam, plate foam | | see [mechanical.md](mechanical.md) |

BOMs: `hardware/bom/*.csv`. Choose R11–R13 or R14–R16 to match `invert_adc`
(the DNP flags are already set from `SENSOR`).

## Daughterboards

1. Solder the DE-15 on the front.
2. On the back, solder the pigtail wires to pads 1–10. Pad 1 is marked by
   the silk bar and carries +5 V. Wire *n* must end up on pin *n* of the J3
   plug, so check the pigtail's colour order with a meter.
3. Leave JP1/JP2 bridged 1–2 (the default) unless your VGA cable lacks pin 9.
   In that case, cut both and bridge 2–3 on **both** boards.

## First power-up (main half alone)

1. **Before soldering the module:** plug in USB and measure +5V, +3V3 (U3)
   and +3.3VA (U2), both also on J4 pads 3 and 4.
2. Solder the module on: tack two opposite corner pads, check it sits flat and
   square on J4, then solder the rest along both edges. Plug in again with a
   USB meter. Expect about 60–90 mA with no satellite.
3. Hold **BOOT** while plugging in. The factory DFU bootloader (AT32 or STM32)
   should enumerate.

## Flashing

```sh
git clone https://github.com/peppapighs/libhmk && cd libhmk
cp -r ../VGACorne/firmware/libhmk/keyboards/vgacorne_* keyboards/
python setup.py -k vgacorne_at32 && pio run       # or -k vgacorne_f446 for the STM32 module
```

Build the keyboard that matches the fitted module: the two differ in driver,
crystal and USB speed.

**QMK (STM32F446 module):** `make vgacorne:default:flash` from a QMK checkout
with `firmware/qmk/keyboards/vgacorne` linked in (see
[firmware/README.md](../firmware/README.md#qmk-stm32f446-module)). For bring-up,
build with `CONSOLE_ENABLE = yes`, run `qmk console`, press `HE_DBG`, and watch
each key's value, rest, bottom-out and distance as you press it.

Flash over DFU (`pio run -t upload`, or WebUSB DFU as the libhmk README
suggests). After that, the `SP_BOOT` key (adjust layer: hold both
thumb-layer keys, then the top-left key) or hmkconf can re-enter the
bootloader.

## Sensor polarity and calibration

1. Connect the satellite **before** plugging in USB. libhmk learns each key's
   rest value during the first 500 ms.
2. Open [hmkconf](https://hmkconf.com) and watch the raw/distance view while
   pressing a key on each half.
   - If distance falls as you press, flip `invert_adc` in
     `hardware/vgacorne/circuits.py` (`SENSOR`), then regenerate: this also
     swaps which cable-unplugged pull resistors are fitted.
   - Set `initial_rest_value` / `initial_bottom_out_threshold` from what you
     observe. The HE60 values used here are only a starting point.
3. Check every key on both halves reaches full travel. A dead column on one
   half usually means a select or analog line isn't making it through the
   cable. Beep out the VGA cable against the pinout table in
   [architecture.md](architecture.md#vga-link-pinout).

## Rotary encoder (left half, QMK)

1. With the satellite powered, measure the `ENC` node (C5) while turning the
   shaft slowly: it should step between about 0, 1.0, 2.1 and 3.3 V. A level
   that never appears means a contact or one of R21-R24 is off.
2. In QMK the knob scrolls on the base layer, scrolls sideways on lower and
   changes the volume on raise. If it turns the wrong way, add
   `#define ENCODER_DIRECTION_FLIP` to `config.h`. One step per detent is the
   default (`ENCODER_RESOLUTION 4`); set it to 2 if an encoder gives two steps
   per detent.
3. libhmk has no encoder support: the two mouse keys work there, the knob
   doesn't.

## Trackpad (optional, QMK)

For the default Azoteq TPS65:

1. Bond the module, centred, under the overlay using its own adhesive, with a
   3 mm margin all round. Turn it so its connector is near the back edge, on
   the half nearer the keys: it then sits right over J5.
2. Mock up the FFC with a paper strip first: it drops from the module's
   connector straight into J5. Check that module pin 4 (VDDHI) lands on J5's
   +3V3 pin. The fold decides the order.
3. With USB plugged in, measure 3.3 V between the module's VDDHI and GND pads.
4. QMK looks for the pad once, at boot, about 100 ms in. If both axes come out
   reversed, add `AZOTEQ_IQS5XX_ROTATION_180` to the TPS65's `qmk_defines` in
   `trackpad.py` and regenerate (`_90`/`_270` if they come out swapped). Build
   with `CONSOLE_ENABLE = yes` and QMK's `POINTING_DEVICE_DEBUG` to see what the
   driver reads.
5. Check two known issues, see
   [firmware/pointing-devices.md](../firmware/pointing-devices.md): whether a tap
   leaves the left button held, and whether key presses lag while the pad is
   being read.

A Cirque pad (the `cirque40` entry) needs its R1 removed if it is the SPI
version (`-2024-`). Check 3.3 V on its FFC pin 12.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Left half dead, right fine | no +5 V on VGA pin 9 (cable variant → JP1/JP2), pigtail miswired, or F2 tripped |
| Left half keys stuck pressed after plugging the cable in late | rest values were learned with the cable out: recalibrate in hmkconf or re-plug USB |
| One column on the left dead | a `LINK_A/B/C` coax line: cable or daughterboard solder joint |
| Keys fine, trackpad dead | FFC reversed or folded the wrong way, the FFC seated after power-up (QMK only looks at boot), or, for a Cirque, an SPI pad with R1 still fitted |
| Knob scrolls in bursts or backwards on some detents | a missing level on `ENC` (see *Rotary encoder*) |
| Keys trigger randomly with the cable unplugged | pull resistor set doesn't match `invert_adc` |
| Rest value drifts when pressing on the plate | a standoff screw is loose, so the plate flexes against the PCB |
