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
| Main PCB, 2-layer 1.6 mm | 1 | bottom-side assembly, plus the module socket J4 on top (hand-solderable) |
| MCU module, 2-layer **1.0 mm** | 1 per firmware you want | AT32F405 (libhmk, 8 kHz) and/or STM32F446 (QMK / libhmk); LQFP on top, header underneath |
| Satellite PCB, 2-layer 1.6 mm | 1 | bottom-side assembly |
| VGA daughterboard | 2 | hand-solder: DE-15, pigtail, 0402 cap |
| Plate (aluminium DXF or FR4 KiCad board) | 1 + 1 mirrored | |
| HE switches (Gateron KS-20 magnetic, GEON Raw HE, ...) | 42 | |
| M2 hex standoffs 3.5 mm, brass | 14 | plus 28 × M2 × 3 mm screws |
| 10-pin JST-SH pigtail, ~10 cm, single-ended | 2 | plugs into J3 |
| VGA cable, male–male, pins 9/12/13/14/15 wired | 1 | as short as you like |
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

1. **Without a module:** plug in USB and measure +5V, +3V3 (U3) and +3.3VA
   (U2), both also on J4 pins 3 and 4.
2. Fit a module and plug in again with a USB meter. Expect about 60–90 mA with
   no satellite.
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

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Right half dead, left fine | no +5 V on VGA pin 9 (cable variant → JP1/JP2), pigtail miswired, or F2 tripped |
| Right half keys stuck pressed after plugging the cable in late | rest values were learned with the cable out: recalibrate in hmkconf or re-plug USB |
| One column on the right dead | a `LINK_A/B/C` coax line: cable or daughterboard solder joint |
| Keys trigger randomly with the cable unplugged | pull resistor set doesn't match `invert_adc` |
| Rest value drifts when pressing on the plate | a standoff screw is loose, so the plate flexes against the PCB |
