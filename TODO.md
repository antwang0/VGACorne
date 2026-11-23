# TODO

## Order the boards

Every board is routed and passes `generate.py check` (0 DRC errors, 0
unconnected items). Freerouting (`hardware/route.py`) routed everything but
the main board's USB pair; it has no differential pairs, so that was laid by
hand afterwards: 0.4 mm tracks 0.15 mm apart from the module's pads to the
vias beside the ESD array U4, with a trombone on `USB_DN` that matches the
lengths to 0.01 mm (41.46 vs 41.45 mm). The last 1–6 mm into U4 stay
single-ended, as the connector cluster leaves no room to move the vias.

A pre-fab review (2026-11-15: electrical, modules, footprints and JLC files,
layout, mechanical, firmware) found no blockers in the circuits; its fixes are
in: JLC rotation corrections in the CPL, select-line resistors and finger
placement for ESD, ground-only module undersides, a pin-1 mark on the modules,
and machinable case details.

Added since (2026-11-23): outside edge rounds and chamfers in the case CAD;
test pads, I2C expansion pads and a status LED on the modules; and in both
firmwares a shorter settling delay (libhmk), longer ADC sampling on the F446,
and holding a left half that is plugged in but has no power.

- [ ] **DRV5055A3QDBZR stock** (JLC 2, LCSC 0, TI out of stock on
      2026-11-15). On 2026-11-23 search listings disagreed (LCSC 1,244;
      Digi-Key backorder, possibly ~3,000 due 1 Dec 2026), and the live pages
      gave no figure: check JLC's part page for C266128 before ordering. If
      it's short, switch to the MT9102ET (C5447698): one line in
      `circuits.py`, already built and checked
      ([sensors.md](docs/sensors.md#changing-the-sensor)).
- [ ] Fix the **Before ordering** items of the [2026-11-23 audit](#audit-2026-11-23)
      below, then rerun `generate.py check`.
- [ ] Run `hardware/generate.py fab` and order (see
      [bring-up](docs/bring-up.md#before-ordering)). Check the sensors, LQFPs,
      USB-C, FFC, encoder and the modules' LED in JLC's placement preview.
      Costs: [docs/cost.md](docs/cost.md) (about 860-1,030 for one aluminium
      unit, five board sets included).
- [ ] Before or at bring-up, check one sensor's polarity with your switch
      (`invert_adc`, [sensors.md](docs/sensors.md#notes)).

## Audit (2026-11-23)

Two read-only audits: five reviewers (electrical, boards and fab files,
firmware, mechanical, OLED), then ten (satellite board, VGA link, MCU modules,
magnetics, firmware configuration, sourcing and cost, ESD/EMC/grounding,
generator code, docs, layout and assembly). No blockers. Items marked ✓ were
confirmed against the code; the rest are reviewers' findings, some of them
estimates, so check each before acting on it.

### Tooling (first: these guard everything else)

- [ ] ✓ A sensor swap through `generate.py pcbs` alone leaves the schematic
      stale, so `fab` still orders the old sensor and pull resistors. Have
      `sync_fields` update the schematic too, or make `fab` refuse on a
      schematic-parity mismatch; fix the `generate.py` docstring.
- [ ] ✓ `checks.py` `TOLERATED_DRC` includes `unconnected_items`: a board with
      a deleted track passes. Drop it now that every board is routed.
- [ ] `firmware.build_matrix` maps mux channels to keys by net name; nothing
      checks the name against the sensor behind it. Trace each channel through
      its 1k to the HE part, or make `checks.intent()` fatal and compare names.
- [ ] `invert_adc` comes from `circuits.SENSOR`, not the schematic: assert the
      HE parts' MPN and the fitted pull set (R11-R13 / R14-R16) agree with it.
- [ ] Skipped checks (no `cc`, no `LIBHMK`, no build123d) still print PASS:
      fail, or print "PASS (n skipped)".
- [ ] `project.write_project` replaces `.kicad_pro` wholesale: merge instead,
      so KiCad Board Setup edits survive.
- [ ] DRC runs on stored zone fills while `gerbers` refills: add
      `--refill-zones` to `checks.drc`.
- [ ] BOOT and RESET (both C318884) come out as two BOM rows, two JLC feeder
      fees: merge rows by LCSC number in `fab.write()`.
- [ ] Add an explicit `CORRECTION` entry for the MT9102ET (C5447698) after
      checking JLC's preview; check one bottom-side TSSOP's rotation there too
      (the 270° turns are where a sign error would show).
- [ ] Smaller: `sync_fields` leaves removed fields behind; `build_matrix`
      drops the detachable/trackpad/LED/encoder blocks silently if tracing
      fails (raise instead); `CORRECTION_BY_FOOTPRINT` misses VQFN/DFN names;
      the J4 pad check is one-directional; `libhmk/tests/run.sh` tests the
      cache checkout instead of the repo's patch when it is already applied.

### Before ordering: boards

- [ ] **Module panel.** JLC's Economic assembly doesn't take castellated
      boards; Standard needs 70 × 70 mm, rails and fiducials. Draw a 3 × 3
      panel (KiKit), tabs on the 25 mm edges only, at spots kept clear of parts
      (Y1, C7, C10, C11, D1 are 0.3-0.8 mm from those edges) with every
      layer's pour pulled back ≥ 0.5-1 mm there. Update bring-up.md and the
      module line in cost.md (~60 is low).
- [ ] **Fiducials:** none on any board. Add three per assembled side (main B,
      main F if J5 stays JLC-placed, satellite B, module F or panel rails).
- [ ] ✓ **Standoffs over tracks:** the 3.5 mm hex (Ø4.04 across corners) is
      wider than its Ø3.4 pad, and +3.3VA, MUX_S1 and HE tracks pass ~2.0 mm
      from six centres. Keep other copper ≥ 2.4 mm from each standoff (rule
      areas) and reroute.
- [ ] ✓ **J4 pad 9 is +5V beside +3V3 (pad 11)** and no module uses it: make
      it GND or no-connect in `MODULE_PINS`.
- [ ] **Left half loses its supply before cable detect:** pin 9 letting go
      first collapses the left rail in < 1 ms and every left key reads
      pressed. Gate DET with a supervisor (TLV809-class on +3.3VA) and a
      2N7002 in place of R17, or reject all-left-keys-at-once in firmware.
- [ ] **DET filtering:** footprint for 100 nF from DET to GND behind R18
      (plus the firmware debounce below).
- [ ] 1 nF C0G from each ADC_R_x to GND on the module side of R8-R10.
- [ ] 100k pull-downs on the satellite's MUX_S0-S2 (after R5-R7).
- [ ] SRV05-4 at the trackpad connector J5 (TP_SCL, TP_SDA, TP_NRST; VP on +3V3).
- [ ] U7's VP to +3.3VA instead of +5V_LINK on both halves.
- [ ] TVS (SMF5.0A class) or damping footprint on +5V for the VBUS hot-plug
      ring; scope it at bring-up either way.
- [ ] Optional: 100-220 pF C0G on LINK_S0-S2 at U6 (emissions).
- [ ] Bootloader pins: 10k pull-ups on PC11 (both modules) and PB10/PB3/PA8/PB4
      (AT32).
- [ ] Decoupling: 100 nF at mux pin 16 on main U12 and satellite U12/U13
      (6-8 mm now); U4/U6/U7 VBUS caps; satellite U5 (C4 4 mm) and U2's caps.
- [ ] **F446 module:** move Y1 against pins 5/6 (traces 7.2/6.6 mm, running
      side by side) and route NRST's In2 track off the crystal.
- [ ] Both modules: VDDA cap ground straight to VSSA (pin 12); on the AT32,
      separate C5's ground from C8's. NRST caps near pin 7.
- [ ] AT32 module USB pair: pull the F.Cu pour back ≥ 0.5 mm or stitch the
      0.41 mm strip; move the USART1_RX track and R3 off D+.
- [ ] Silkscreen below JLC's 1.0 mm / 0.15 mm, including the "USB-C edge" and
      pin-1 marks ("USB-C edge" is 0.09 mm from the edge); raise the project's
      minimum text height to 1.0.
- [ ] Main board USB pair: ~100 Ω (USB HS allows 103.5); 5.5 mm near U4/F1
      split across layers over VBUS. Re-route on one layer with a wider gap,
      or accept for the first build if HS enumerates.
- [ ] Reroute HE_C0R2 away from the right G2 finger (1.03 mm; grounding.md
      says ~3.5 mm). Spread analog/select parallel runs (HE_C2R1/MUX_S0
      10.8 mm, LINK_A/SWDIO 6.3 mm, LINK_C/MUX_S1 6.0 mm).
- [ ] A third spring finger within ~5 mm of the satellite's ENC1 SH legs, or
      move the left G2 there.
- [ ] Satellite test pads: +5V_LINK, +3.3VA, GND, the three buffer outputs,
      MUX_S0-S2.
- [ ] Encoder: C143785 out of stock at LCSC (snapshot). Switch to KiCad's
      `RotaryEncoder_Bourns_Vertical_PEC12R-3x17F-Sxxxx` so the S variant
      (C18164805) also fits, or hand-fit ENC1 from Digi-Key/Mouser.
- [ ] DE-15 (C598516): ~10 at LCSC, exactly the need; buy from Digi-Key.
- [ ] Optional: U8 RC-delayed EN (USB inrush/unconfigured current); a
      common-mode choke footprint with 0 Ω jumpers on the USB pair.

### Before ordering: case

- [ ] ✓ Frame drawing: tapped holes A1-A8 lack the `*` (drilled from below);
      add it and "from the seam face". Make the 1/4"-20 thread "thread mill
      only" (a bottoming tap can't give 4.5 mm of full thread).
- [ ] Right half tips forward: its feet sit behind the thumb cluster
      (`mechanical.feet()` uses bounding-box corners). Add feet under T0/T2
      (free spots near (165-170, 110) and (215-220, 110)) and pass the screws
      to `feet()` as obstacles.
- [ ] Trackpad overlay ledge: thicken the roof under the counterbore ring
      (a 0.5 mm lip over x 152-170); the printed frame needs a support there
      (2.9 mm overhang): fix mechanical.md's "neither needs supports".
- [ ] Aluminium: bond the plate to the case (conductive foam in 2 of the 16
      gasket pockets, on a bare tab). Printed: a plate-to-GND bond near
      J1/G1, and a braid from a DE-15 board lock to the free G1 land.
- [ ] Maximum screw protrusion for the tripod/Arca mounts on the drawing
      (0.5 mm skin above the tapped hole).

### Firmware

- [ ] ✓ QMK: keys never release at actuation ≤ 8 (`he_matrix.c:196`;
      `HE_ACTD` floors at 6). Release at `act > 2*HYST ? act - HYST : act/2`.
- [ ] Floors inside the noise: actuation ≥ ~0.3 mm (~20 units), rapid
      trigger ≥ ~0.1 mm (DRV5055) / 0.2 mm (MT9102ET); range-check settings
      loaded from EEPROM.
- [ ] ✓ QMK rest is one snapshot (`finish_calibration`): a key held then is
      dead. Track rest slowly on idle keys (also covers warm-up drift, cable
      resistance drift and a steel desk); accept a calibration only if the
      key was stable; start `HE_CALB` on release.
- [ ] ✓ QMK phantom press from one bad sample (`debounce: 0`,
      `HE_FILTER_SHIFT 2`; ~250 counts trips the default): spike rejection or
      a one-scan confirm, and learn `bottom` only after N scans.
- [ ] Debounce cable detect (≥ 2 ms) in both firmwares; filter `silent()` too.
- [ ] libhmk patch: hot-plug calibration takes in transients from late-mating
      pins (rest = running minimum): restart calibrating on rail-level
      readings or learn rest from the last ~100 ms only.
- [ ] Bottom-out only ever rises: a supply sag ratchets it (both firmwares;
      libhmk can save it to flash). Skip learning when a whole mux jumps.
- [ ] libhmk `silent()`: include the encoder slot, require N scans.
- [ ] ✓ Every layer key and the bootloader key are on the left half: with the
      cable out the right half has only its base layer. Move one layer key
      and a bootloader key to the right half.
- [ ] QMK `NKRO_DEFAULT_ON`; round the filter (`(3v + s + 2) >> 2`, or a
      fixed-point accumulator); persist each key's learned span (strong
      switches fire early until bottomed once after boot).
- [ ] MT9102ET builds: `HE_FILTER_SHIFT 3` and higher floors (~5× the noise).
- [ ] Keymaps: no Caps Lock (the LED test needs one) or left Alt; libhmk's
      raise layer is thin; the two firmwares' default actuation differs (and
      libhmk's schema `actuation_point` is ignored upstream).
- [ ] QMK: set PA0-PA5 analog in `early_hardware_init_post()` (the generic
      F446 board drives PA5 low until matrix init).
- [ ] Tests: the QMK "unused channels stay quiet" check passes even when
      broken (return the GND level for unused channels); fix the "row 3 is
      remote" comment; libhmk `run.sh` should always apply the patch to
      pristine files.
- [ ] Note in firmware/README: libhmk's F446 wear-levelling erase stalls the
      keyboard ~1-2 s; measure the QMK scan time with a GPIO toggle.
- [ ] Optional: `silent_spread` and the settling delay as generator settings
      (document `delay: 10` for cables over 5 m).

### Docs

- [ ] **Assembly procedure** in bring-up.md: module onto J4 before the plate,
      fingers, foams and gaskets, standoffs, **pigtail into J3 before the
      sandwich goes into the tray**, daughterboard and jackscrews, frame,
      trackpad FFC, keycaps, knob; check sensors before the plate goes on;
      service notes (module swap needs the plate off).
- [ ] **Cable spec** in architecture.md and bring-up.md: passive male-male
      HD-15, pins 1-3, 6-8, 9, 12-15 wired 1:1, no 3C+2, no CCA over 3 m,
      ≤ 5 m copper; meter test; bring-up check that `5VL` reads ≥ 3.5 V.
- [ ] Flashing: split libhmk and QMK, add `pip install platformio
      "pydantic~=2.11"`, QMK's Python setup, `dfu-util` and udev, and what
      `dfu-util -l` should show; drop `dfu-suffix`.
- [ ] Trackpad swap steps (architecture.md:206): J5 needs re-placing in
      KiCad; add `case fab check`.
- [ ] mounting.md: the under-desk plan contradicts itself and aims the VGA
      plug at the desk edge; the back face doesn't point at the desk when
      tented; note recalibrating on a steel desk and a nylon washer on earthed
      arms.
- [ ] cost.md: re-sum "everything else" and the totals; feeder fee is per BOM
      line on Standard (fix fab.py's comment too); satellite may be one-sided
      (Economic if ENC1 is hand-fitted); shipping, duties; 10 daughterboards
      for five sets; F446 module line.
- [ ] TPS65 trackpad isn't end-of-life per Azoteq's September 2026 list
      (Mouser ~$6): correct trackpad.py, bring-up.md and cost.md after
      checking.
- [ ] ✓ "The right half's analog muxes" in the three keyboard READMEs: it's
      the left half.
- [ ] Electrical doc fixes: bring-up.md 7628 stack-up (raises impedance, ~121 Ω),
      LA-LC rest voltage (~1.4-1.55 V), RA-RC level with the MT9102ET (0 V);
      sensors.md "three 0402s" (six); architecture.md unpowered-satellite
      explanation and the PC-plug explanation; circuits.py:142 "1 nF" (C5 is
      100 pF).
- [ ] Mechanical doc fixes: grounding.md tab gap (0.5, not 0.25), the hex
      "sits on the pad", the trackpad well wall (0.3 mm, not 3-4 mm);
      mechanical.md jackscrew gap (1.44), case-plan layer table (MOUNTS,
      MOUNT_ZONE, FEET), 400 vs 405 g; screw materials (stainless or brass).
- [ ] Ordering table: keycaps, plate left/right differ, female-female
      standoffs, encoder only if JLC can't place it, daughterboard spec, TC2030
      cable and SWD probe; check the Keystone 7229 quantity (1 = 2 sets?); FR4
      plate fab path and thickness (1.5 vs JLC's 1.6).
- [ ] Bring-up: case grounding checks (grounding.md work item), a satellite
      power-up test with pass figures, beep the pigtail through first;
      unconnected items appear only under "(tolerated)" today.
- [ ] Minor: firmware sizes (README vs firmware/README), libhmk commit dates,
      encoder stock contradictions, historical DRV5055 stock in sensors.md,
      expansion-pad order, "reachable with the tray off" wording, unused and
      stale images in docs/img, README quick start ("Open … to route",
      build123d), `silent_spread` hand-edit advice, firmware/README's
      "don't hand-edit" scope.

### Measure at bring-up

- [ ] Left +3.3VA with the real cable at low VBUS (supply headroom).
- [ ] VDDA vs VDD at USB unplug (separate LDOs).
- [ ] Hot-plug ring on +5V; ESD/dry-day test with and without the main G2
      finger.
- [ ] DET glitch margin with select activity; QMK scan time.

### OLED: not on rev 0.1

No free MCU pin (I2C only, shared with the trackpad), no room in the case
(the 0.91" panel is ~0.6 mm too thick for the roof over the VGA bay), QMK's
driver blocks the scan, libhmk has no display support. If wanted in rev 0.2:
a bare 0.91" 128x32 SSD1306 under a window over the VGA bay, a Qwiic-style
connector off I2C1, QMK only, after the trackpad thread exists.

## Also open

Details are in the linked docs.

- [ ] **Case:** print `mechanical/case-printed/` and check the fit, then quote
      `mechanical/case-machined/` in aluminium (STEP + `.dxf` drawing). Tenting
      and under-desk mounting: the plan in [mounting.md](docs/mounting.md#plan-tented-under-the-desk).
      The grounding plan ([grounding.md](docs/grounding.md)) is in the boards
      and the drawings: order the four spring fingers and ask the shop to mask
      the `BARE` areas.
      Not modelled yet: a typing angle, lightening under the trackpad.
- [ ] **QMK:**
  - Move the trackpad reads to their own thread
    ([pointing-devices.md](firmware/pointing-devices.md)).
  - Add VIA, per-key actuation and DKS/SOCD
    ([firmware/README.md](firmware/README.md)).
- [ ] **libhmk:** add the rotary encoder and the trackpad
      ([pointing-devices.md](firmware/pointing-devices.md)).
- [ ] **USB IDs:** request real PIDs to replace the pid.codes test IDs.
- [ ] **At bring-up:** confirm sensor polarity and calibration, test
      hot-plugging the VGA cable, check the settling delay on the `LA`–`LC`
      test pads, and fit QMK's travel curve to real sensor
      data ([bring-up.md](docs/bring-up.md)).
