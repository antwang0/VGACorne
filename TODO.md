# TODO

## Route the main board's USB pair (in KiCad)

Every board is autorouted by `hardware/route.py` and passes `generate.py
check`. On the main board, getting there took spreading out the link and
ADC-resistor parts beside the module (`LINK_GAP` in `vgacorne/pcb.py`, 1.0 mm
between courtyards instead of 0.15 mm). With them packed tight, every router
tried left 1–11 connections open in that cluster: Freerouting 2.4.1 and 2.5.0,
and Quilter, which also squeezed below our track and clearance rules and
shorted nets when asked to finish the old board.

Freerouting has no differential pairs, so one thing is left for KiCad's
interactive router, roughly 10 minutes of work:

- [ ] **The USB pair.** It is two separate tracks, 41.3 and 39.0 mm long with
      one via each, not side by side. That's harmless for the F446's
      full-speed USB, but it loses the ~90 Ω coupling the AT32's high-speed
      USB needs (the 2.3 mm mismatch is only ~15 ps).
      - Delete both tracks.
      - Route `USB_DP`/`USB_DN` with the differential-pair router (the `USB`
        net class: 0.4 mm tracks, 0.15 mm gap) from U4 to J4's back corner.
      - Keep the length difference under ~1 mm.
      - Keep the ground pour beside the pair and unbroken ground under it.
- [ ] Run `hardware/generate.py check`: 0 DRC errors and 0 unconnected items
      on every board.
- [ ] Run `hardware/generate.py fab` and order (see
      [bring-up](docs/bring-up.md#before-ordering)).

## Also open

Details are in the linked docs.

- [ ] **Case:** print the `inserts` build and check the fit, then quote the
      `tapped` build in aluminium (STEP + `.dxf` hole drawing). Pick a tenting
      and desk setup ([mounting.md](docs/mounting.md)).
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
