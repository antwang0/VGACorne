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

- [ ] **Wait for DRV5055A3QDBZR stock** (JLC 2, LCSC 0, TI out of stock on
      2026-11-15, no date): set stock alerts, or a Digi-Key backorder shows
      TI's expected date.
- [ ] Run `hardware/generate.py fab` and order (see
      [bring-up](docs/bring-up.md#before-ordering)). Check the sensors, LQFPs,
      USB-C, FFC and encoder in JLC's placement preview.
      Costs: [docs/cost.md](docs/cost.md) (about 860-1,030 for one aluminium
      unit, five board sets included).
- [ ] Before or at bring-up, check one sensor's polarity with your switch
      (`invert_adc`, [sensors.md](docs/sensors.md#notes)).

## Also open

Details are in the linked docs.

- [ ] **Case:** print `mechanical/case-printed/` and check the fit, then quote
      `mechanical/case-machined/` in aluminium (STEP + `.dxf` drawing). Tenting
      and under-desk mounting: the plan in [mounting.md](docs/mounting.md#plan-tented-under-the-desk).
      The grounding plan ([grounding.md](docs/grounding.md)) is in the boards
      and the drawings: order the four spring fingers and ask the shop to mask
      the `BARE` areas.
      Not modelled yet: edge rounds, a typing angle, lightening under the
      trackpad.
- [ ] **QMK:**
  - Move the trackpad reads to their own thread
    ([pointing-devices.md](firmware/pointing-devices.md)).
  - Add VIA, per-key actuation and DKS/SOCD
    ([firmware/README.md](firmware/README.md)).
- [ ] **libhmk:** add the rotary encoder and the trackpad
      ([pointing-devices.md](firmware/pointing-devices.md)).
- [ ] **USB IDs:** request real PIDs to replace the pid.codes test IDs.
- [ ] **At bring-up:** confirm sensor polarity and calibration, test
      hot-plugging the VGA cable, and fit QMK's travel curve to real sensor
      data ([bring-up.md](docs/bring-up.md)).
