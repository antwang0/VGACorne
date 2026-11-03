# TODO

## Order the boards

Every board is routed and passes `generate.py check` (0 DRC errors, 0
unconnected items). Freerouting (`hardware/route.py`) routed everything but
the main board's USB pair; it has no differential pairs, so that was laid by
hand afterwards: 0.4 mm tracks 0.15 mm apart from the module's pads to the
vias beside the ESD array U4, with a trombone on `USB_DN` that matches the
lengths to 0.01 mm (41.46 vs 41.45 mm). The last 1–6 mm into U4 stay
single-ended, as the connector cluster leaves no room to move the vias.

- [ ] Run `hardware/generate.py fab` and order (see
      [bring-up](docs/bring-up.md#before-ordering)).
      Costs: [docs/cost.md](docs/cost.md) (about 860-1,030 for one aluminium
      unit, five board sets included).

## Also open

Details are in the linked docs.

- [ ] **Case:** print `mechanical/case-printed/` and check the fit, then quote
      `mechanical/case-machined/` in aluminium (STEP + `.dxf` drawing). Pick a tenting
      and desk setup ([mounting.md](docs/mounting.md)).
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
