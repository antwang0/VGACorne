# TODO

## Finish routing the main PCB (by hand, in KiCad)

`hardware/route.py` autorouted every board. The main board came out with four
problems that the scripted tools can't fix well:

- **Freerouting runs out of room.** The main board has two copper layers, and
  most parts are on the bottom. Its last three connections are in the most
  crowded spots. Closing them means pushing existing tracks aside. More runs
  gave diminishing returns: 9 gaps, then 4, then 3, at 20–35 minutes a run.
- **Freerouting doesn't understand copper pours.** `route.py` routes ground as
  tracks, then adds the pour and stitching vias itself. That leaves one pad
  boxed in.
- **Freerouting has no differential pairs.** It routes D+ and D− as two
  unrelated nets.

KiCad's interactive router can shove tracks aside, route differential pairs
and tune lengths. It only runs in the editor; neither `kicad-cli` nor the
Python API exposes it. In the editor this is roughly 15–20 minutes of work.

- [ ] **Three gaps:**
  - `LINK_B`: J3 pin 7 to U7 pin 3, about 6 mm.
  - `VBUS`: USB-C pad A4 to the rest of `VBUS`.
  - `LINK_A`: R8 pad 1 to its track, which ends at (156.5, 47.6) mm.
- [ ] **C18's ground pad** (DRC `starved_thermal`, the one error that fails
      `generate.py check`). Tracks fence its patch of bottom-layer ground pour
      off from the rest, and there's no room for a ground via. Route a short
      track to ground, or nudge C18 and move a track.
- [ ] **The USB pair.** It is two loose tracks, 55 and 46 mm long and not side
      by side. That's harmless for the F446's full-speed USB, but it loses the
      ~90 Ω coupling the AT32's high-speed USB needs, and adds ~55 ps of skew.
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
      and desk setup ([mechanical.md](docs/mechanical.md#tenting-and-desk-mounting)).
      Not modelled yet: edge rounds, a typing angle, lightening under the
      trackpad.
- [ ] **QMK:**
  - Move the trackpad reads to their own thread
    ([pointing-devices.md](firmware/pointing-devices.md)).
  - Add VIA, per-key actuation and DKS/SOCD
    ([firmware/README.md](firmware/README.md)).
- [ ] **libhmk:** add the rotary encoder and the trackpad
      ([pointing-devices.md](firmware/pointing-devices.md)).
- [ ] **Hot-plugging:** use `DET` to ignore remote keys while the VGA cable
      is out, and recalibrate when it returns
      ([architecture.md](docs/architecture.md#open-items), item 2).
- [ ] **USB IDs:** request real PIDs to replace the pid.codes test IDs.
- [ ] **At bring-up:** confirm sensor polarity and calibration, and fit QMK's
      travel curve to real sensor data ([bring-up.md](docs/bring-up.md)).
