# Architecture

## Block diagram

```
 LEFT HALF (main PCB = carrier)                             RIGHT HALF (satellite PCB)
 ──────────────────────────────                             ──────────────────────────
 21 × DRV5055 ─► 3 × SN74LV4051 ─► ADC_L_A..C ┐             21 × DRV5055 ─► 3 × SN74LV4051
                     ▲ MUX_S0..S2             │                               ▲ S0..S2   │ A/B/C
                     │                        ▼                               │          ▼
 USB-C ─► ESD ─► ┌─ J4 ═ MCU module (swappable) ─┐ ◄─ ADC_R ◄─ 100 Ω ◄──┐      │     TLV9064 ×3
   │             │  AT32F405 (libhmk, 8 kHz)  or │                      │      │     (followers)
   │             │  STM32F446 (QMK / libhmk)     │ ─ MUX_S ─► 470 Ω ─┐  │      │          │ 75 Ω
   │             └───────────────────────────────┘                   │  │      │          │
   ├─► TLV75733 ─► +3.3VA (sensors, muxes, module VDDA)              ▼  │      │          ▼
   ├─► XC6206   ─► +3V3   (module)                          J3 (JST-SH 10) ··· J3 ─► TLV75733 ─► +3.3VA
   └─► PTC ─► Schottky ─► +5V_LINK ──────────────────────────────►  │                 ▲
                                    pigtail ─► VGA daughterboard ═══ VGA cable ═══ VGA daughterboard
```

The satellite has no firmware at all, and the main PCB is only a carrier: the
microcontroller lives on a small plug-in module (see [below](#mcu-modules)).
Each scan step, the MCU sets the three
select lines. All six muxes, local and remote, switch to the same channel.
After a settling delay the ADC converts six inputs, so 8 steps read all 48 mux
channels (42 used).

## Why an analog link

A split HE board has to move 21 analog readings, or their digital results,
across the cable. The options:

| Approach | Cable | Cost |
|---|---|---|
| Two MCUs, serial link (Lucca 58HE: 2 × RP2040, UART/SPI) | 3–4 wires | second MCU, split firmware, extra latency on the slave half (the Lucca README reports it) |
| Remote ADC chip over SPI/I²C | 4–6 wires | new driver in libhmk |
| **Remote muxes, analog out** | 3 selects + N analog + power | nothing new in firmware |

libhmk already scans "select lines + a list of ADC inputs", so the right half
just becomes three more mux inputs. The firmware can't tell the difference
between a local and a remote mux.

**Why VGA?** Three 8:1 muxes cover 21 keys, which means three analog outputs.
A VGA cable has exactly three 75 Ω coax pairs (R, G, B), made to carry analog
signals over metres, plus enough plain wires for three logic lines, +5 V and
ground. It also has screw locks. RJ45 would fit the 8 conductors but has no
shielding and nothing spare.

## VGA link pinout

The two halves use identical daughterboards and a standard **male–male VGA
cable**. Both halves have female DE-15 ports, like a PC or a monitor.

| DE-15 pin | VGA name | VGACorne signal | Notes |
|---|---|---|---|
| 1 | Red (coax) | `LINK_A` | satellite mux A (col 0–1) via buffer + 75 Ω |
| 2 | Green (coax) | `LINK_B` | satellite mux B (col 2–3, T0) |
| 3 | Blue (coax) | `LINK_C` | satellite mux C (col 4–5, T1, T2) |
| 6 / 7 / 8 | R/G/B return | GND | coax shields |
| 5, 10 | GND | GND | |
| 13 | HSYNC | `LINK_S0` | mux select bit 0 |
| 14 | VSYNC | `LINK_S1` | mux select bit 1 |
| 12 | DDC SDA | `LINK_S2` | mux select bit 2 |
| 9 | +5 V (DDC power) | `+5V_LINK` | via JP1 (default) |
| 15 | DDC SCL | `LINK_DET` | cable detect, via JP2 (default) |
| 4, 11 | ID | — | unused (often not wired in cables) |
| shell | | GND | the case gets grounded through the screwlocks |

**Cable requirement:** pins 1–3, 5–10 and 12–15 must be wired. Most "full" or
"3+6" cables are, but some cheap ones leave out pin 9. Check with a meter. If
yours has no pin 9, re-jumper **both** daughterboards: cut JP1/JP2 and bridge
the other side. That puts +5 V on pin 15, and cable-detect then can't be used.
Never set JP1 and JP2 to the same pin.

**Plugged into a PC or monitor by mistake:** the analog lines see 75 Ω
terminations, the logic lines meet sync/DDC pins, and +5 V meets +5 V. The
Schottky D1 stops back-feeding and F2 limits current. Nothing is at risk.

## Signal chain details

**Sensors.** DRV5055A3 (ratiometric, SOT-23) at 3.3 V: 15 mV/mT, 20 kHz bandwidth,
2 mA typ / 4 mA max supply current (TI datasheet SBAS640C). Each sensor sits on
B.Cu directly under its switch centre, with a 100 nF supply cap and a 4.7 nF
output cap, copied from the HE60. The output cap also acts as the charge
reservoir the mux samples from.

**Local ADC path.** Mux outputs go straight to PA0–PA2, as on the HE60. On
the main half, VDDA (the ADC reference) is the same +3.3VA rail that feeds the
sensors, so LDO drift cancels out ratiometrically.

**Remote ADC path.** A TLV9064 follower (10 MHz, rail-to-rail) buffers each
satellite mux output and drives the coax through a 75 Ω back-termination. On
the main half the signal passes the ESD array and a 100 Ω series resistor
before PA3–PA5. Without the buffer, ~100 pF of cable would charge-share with
each sensor's 4.7 nF on every channel switch, an error of about 2 % of the
step between neighbouring keys. The satellite's own LDO and the cable's IR
drop cause a static gain/offset error of a few percent. libhmk's per-key
calibration absorbs that, because hall sensors draw constant current and the
drop doesn't move with key state.

**Select lines.** PC1–PC3 drive the local muxes directly and the cable
through 470 Ω. That slows the edges (≈50 ns into the cable), damps ringing,
and limits current into an unpowered satellite.

**Cable unplugged.** R11–R13 pull the remote ADC inputs toward the
"key released" end of the range. Released means high when `invert_adc` is true;
otherwise fit R14–R16 as pull-downs instead. Both the resistor choice and the
firmware flag come from `SENSOR` in `hardware/vgacorne/circuits.py`. The
satellite ties `LINK_DET` low through 1 kΩ, and the main half pulls it up, so
PC4 reads low when a satellite is attached. libhmk doesn't use DET yet; see
[open items](#open-items).

**Timing.** libhmk waits `ADC_SAMPLE_DELAY` (20 µs by default) after each
select change, so a full 8-step scan takes about 0.2 ms. The buffered cable
settles in about 1 µs, so the delay can be reduced after measuring.

## Power budget (USB 500 mA)

| Load | Typical | Worst case |
|---|---|---|
| 42 × DRV5055 at 3.3 V | 84 mA | 168 mA |
| AT32F405 with USB HS PHY | ~60 mA (estimate) | ~100 mA |
| 6 × SN74LV4051A, TLV9064 | ~3 mA | ~5 mA |
| **Total** | **≈ 150 mA** | **≈ 275 mA** |

The satellite takes about 45 mA typ / 90 mA max through VGA pin 9. F2 is a
500 mA PTC; a lower hold current (200–350 mA) would also do. No RGB, so the
budget has plenty of margin.

## MCU modules

The MCU is on a 19 × 17 mm plug-in module, so the firmware family is chosen by
which module you fit:

| Module | MCU | USB | Firmware | Crystal |
|---|---|---|---|---|
| `module_at32` | AT32F405RCT7 | high speed (internal PHY) | libhmk, 8 kHz polling | 12 MHz |
| `module_f446` | STM32F446RET6 | full speed (PA11/PA12) | QMK (generic F446 board) or libhmk, 1 kHz | 8 MHz |

![AT32 module, top and underside](img/module_at32-top.png) ![](img/module_at32-bottom.png)

QMK doesn't support the AT32F405: only the AT32F415 is in QMK `master` and
`develop`, and the AT32F405 PR was closed unmerged. That's why there are two
modules.

**Mechanics.** The module plugs into a 2×12, 1.27 mm SMD socket (J4) on top of
the main PCB's inner tab, where there are no switches and the plate is cut
away. Its header is on the underside, and the LQFP sits on top right above it.
The stack is 5.4 mm of connector, a 1.0 mm board and the 1.6 mm LQFP. That
leaves 0.5 mm under the case roof, which is what keeps the module seated; there
is no screw. Everything else stays on the carrier: USB-C and its ESD, both
regulators, and the BOOT/RESET buttons and SWD pads, reachable from under the
case.

**Connector pinout.** Numbered as on the carrier's socket J4; the module's
header meets pin *n* on pin *n*, and `generate.py check` verifies it pad by pad.

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | GND | 2 | GND |
| 3 | +3V3 (MCU supply) | 4 | +3.3VA (module VDDA = ADC reference) |
| 5 | +5V | 6 | GND |
| 7 | USB D+ | 8 | USB D− |
| 9 | GND | 10 | GND |
| 11 | ADC_L_A | 12 | ADC_L_B |
| 13 | ADC_L_C | 14 | ADC_R_A |
| 15 | ADC_R_B | 16 | ADC_R_C |
| 17 | MUX_S0 | 18 | MUX_S1 |
| 19 | MUX_S2 | 20 | DET (low = satellite connected) |
| 21 | NRST | 22 | BOOT (carrier button pulls to +3V3) |
| 23 | SWDIO | 24 | SWCLK |

A new module only has to supply 6 ADC inputs, 3 GPIO outputs and 1 GPIO input,
USB device, and some boot-mode entry driven by `BOOT`. The RP2350B (8 ADC
inputs) would qualify once QMK supports it. The RP2040 and Pro Micro-style
boards don't, with only 4 ADC inputs.

**Pin map.** The AT32F405RCT7 and STM32F446RET6 use the same LQFP-64 pin
numbers for every keyboard signal, so both modules share one map:

| LQFP pin | Port | Net | libhmk |
|---|---|---|---|
| 14, 15, 16 | PA0–PA2 | `ADC_L_A/B/C` (local muxes) | `input` A0–A2 |
| 17, 20, 21 | PA3–PA5 | `ADC_R_A/B/C` (satellite, via cable) | `input` A3–A5 |
| 9, 10, 11 | PC1–PC3 | `MUX_S0..S2` | `select` C1–C3 |
| 24 | PC4 | `DET` | — |
| 7, 60 | NRST, BOOT0 | reset / boot (buttons on the carrier) | factory DFU |
| 46, 49 | PA13, PA14 | SWD | |

They differ only in supplies and USB. The AT32 has 12 kΩ on OTGHS1_R and USB
on OTGHS1_D−/D+ (pins 34/35). The F446 has VBAT, a VCAP capacitor on pin 30,
and USB on PA11/PA12 (pins 44/45). The AT32 pinout was taken from the
fabricated HE60 board; cross-check both against the vendors' datasheets before
ordering.

## Firmware

There is one libhmk keyboard per module, `firmware/libhmk/keyboards/vgacorne_at32`
and `vgacorne_f446`, and both are **generated from the schematics**.
`hardware/vgacorne/firmware.py` exports the netlists with `kicad-cli` and
treats the boards as one graph. It joins them through series resistors, the
satellite's buffers, the module connector and the 1:1 link cable. From every
MCU ADC pin it finds a mux, then maps each mux channel to its switch. You can
swap mux channels in KiCad to make routing easier, then run
`generate.py firmware`. The check step fails if any key is unreachable or the
select wiring disagrees between halves.

Key indices follow QMK's `LAYOUT_split_3x6_3` order: three rows of 12, left to
right, then the six thumbs. The default keymap is a plain Corne layout (base /
lower / raise / adjust, with `SP_BOOT` on adjust). Tap-hold, rapid trigger and
actuation depths are configured at runtime in hmkconf.

Both definitions build against libhmk with PlatformIO. See
[firmware/README.md](../firmware/README.md).

**QMK** (F446 module only) runs with a keyboard-level analog matrix
(`firmware/qmk/keyboards/vgacorne`), since QMK mainline has no hall-effect
feature. Its `keyboard.json` layout and `he_wiring.h` are generated from the
same trace as the libhmk configs. It supports fixed actuation and rapid
trigger, adjustable with keycodes and saved to flash. It uses the cable-detect
line to pause and recalibrate the right half when the VGA cable is unplugged
and replugged. A host test runs the real matrix code against simulated
sensors. VIA support and per-key features are still to do. See
[firmware/README.md](../firmware/README.md#qmk-stm32f446-module).

## Alternatives considered

- **Unbuffered remote muxes.** Simpler, but loses accuracy to cable charge
  sharing (see above). The buffer is one TSSOP-14.
- **16:1 muxes (CD74HC4067).** Only two analog lines, but four selects and a
  16-step scan. The 3 coax / 3 × 8:1 split maps onto VGA naturally.
- **Connector on the PCB.** A DE-15 is 12.5 mm tall with its flange and the
  cable is stiff. On a gasket-mounted PCB it would load the gaskets and need a
  taller case. See [mechanical.md](mechanical.md#vga-daughterboard).
- **RGB / OLED.** Left out: they'd use pins and power budget, and libhmk
  doesn't drive them.

## Open items

1. **Route the PCBs.** Keep USB D+/D− short and paired (2-layer is what the
   HE60 uses; 4-layer would give cleaner USB and analog ground). Route analog
   nets (`HE_*`, `ADC_*`, `LINK_A/B/C`) away from the select lines.
2. **Hot-plugging.** libhmk calibrates each key's rest value only during the
   first 500 ms after boot. Connect the VGA cable *before* USB, or recalibrate
   from hmkconf. A small libhmk patch could use `DET` (PC4) to ignore remote
   keys while the cable is out and recalibrate when it returns.
3. **Sensor polarity and calibration.** `invert_adc` and the initial
   rest/bottom-out values are copied from HE60 practice. Confirm them in
   hmkconf's debug view at bring-up ([bring-up.md](bring-up.md)).
4. **Parts to confirm at ordering:** a vertical DE-15F with 4-40 inserts that
   matches the KiCad footprint; LCSC stock for the TLV9064, SRV05-4 and
   DRV5055A3. Alternative sensors used on the HE60: MT9102ET, SS39ET,
   GH39FKSW.
5. **USB IDs.** `0x1209:0x0001` (AT32) and `:0x0002` (F446) are pid.codes
   test IDs. Request real PIDs before sharing boards.
6. **QMK:** add VIA, per-key actuation and DKS/SOCD, and fit the travel curve to real
   sensor data (see [firmware/README.md](../firmware/README.md#qmk-stm32f446-module)).
7. **Module retention.** The case roof holds the module in its socket with
   0.5 mm clearance. Add a thin foam pad on the roof if it rattles.
