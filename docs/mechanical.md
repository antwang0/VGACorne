# Mechanical design

All numbers here come from `hardware/vgacorne/mechanical.py` (`STACK` and the
constants at the top). Change them there and re-run `generate.py mechanical`.

![Case plan, right (main) half](../hardware/mechanical/case-plan-right.svg)

![Top view render](img/render-top.jpg)

## Mounting concept

Hall-effect switches are **not soldered**. The plate holds them, and their
two plastic pegs locate them in the PCB. The sensor measures the distance
from the magnet in the stem to the PCB underside, so if the plate flexed
relative to the PCB, the rest position would drift.

So the build is two assemblies:

1. **Sandwich:** plate + PCB, bolted together with **M2 standoffs**
   (3.5 mm hex, 3.5 mm tall, brass): seven on the right half, eight on the
   left, whose mouse column gets its own. They sit in the gaps between switch
   bodies, and the positions are shared by the PCB, plate and foam
   (`geometry._STANDOFFS`).
2. **Case:** CNC aluminium top frame + bottom tray. The sandwich floats between
   them on **gaskets** around eight plate tabs.

Flexing the gaskets moves the whole sandwich, not the magnet-to-sensor
distance, so you get gasket feel without the actuation point wandering.

## Stack-up

Heights are from the underside of the case.

| z (mm) | Surface |
|---|---|
| 0.0 | case underside |
| 2.0 – 3.0 | floor pockets under the USB-C and the encoder's pins (`FLOOR_POCKETS`) |
| 3.0 | floor top (3.0 mm floor) |
| 3.0 – 5.0 | case foam, 2 mm (poron sheet or silicone pad) |
| 5.5 | underside of the parts over the foam: sensors, muxes, regulators (up to 1.45 mm) |
| 7.0 | PCB underside (the USB-C hangs 3.26 mm below it, over a foam relief and a floor pocket) |
| 8.6 | PCB top |
| 12.1 | plate underside (MX spec: plate top is 5.0 mm above the PCB top) |
| 13.6 | plate top |
| 12.9 – 17.6 | trackpad module, its connector and the FFC fold, in their well (right half) |
| 8.6 – 11.3 | MCU module (under the trackpad): soldered flat, 1.0 mm board, 1.6 mm LQFP |
| 13.7 – 18.7 | encoder body top (flush with the plate) and the ~7 mm collar round its shaft (left half) |
| 19.1 – 30.6 | encoder knob (left half): clears the collar, top about 2 mm above the keycaps |
| 17.1 | underside of the 1.5 mm roof over the VGA bay and USB-C ear |
| 17.6 – 18.6 | trackpad overlay, flush with the top (right half) |
| 18.6 | top of case (frame 5 mm above the plate) |

The frame height is set by the parts under the roof: the VGA bay needs more
than the DE-15's 12.55 mm flange (it gets 14.1 mm). The MCU module is 2.7 mm
tall and sits 1.6 mm under the trackpad's well.
For a typing angle, keep these heights at the front and raise the back by
`depth × tan(angle)`. The case is 116 mm deep, so 5° adds about 10 mm.

## Poron or silicone

Every soft layer has its own DXF. Either material fits the same pockets;
silicone is springier, poron is more muted.

| Layer | File | Poron | Silicone |
|---|---|---|---|
| Gaskets (above and below each plate tab) | tabs in `plate-*.dxf`, pockets in `case-plan-*.dxf` | 3 mm PORON strips, 10 mm wide | 3 mm silicone strip or "sock" (≈ Shore 30–40A) |
| Case foam (under the PCB) | `foam-case-*.dxf` | 2 mm PORON sheet | 2 mm poured or cut silicone pad (≈ Shore 10–20A) |
| Plate foam (optional, between plate and PCB) | `foam-plate-*.dxf` | 3.5 mm PORON | 3.5 mm silicone |

- Aim for about 25 % gasket compression when the case is closed. Tune it with
  strip thickness, not by changing the pockets.
- Leave the 0.5 mm air gap between the case foam and the parts over it
  (`foam_gap`). The parts under the PCB are up to 1.45 mm tall (`bottom_parts`).
  Foam that touches the PCB or its parts preloads the gaskets and kills the
  flex, so thicker foam needs a taller case.
- The case foam has reliefs for the connectors and buttons (read from the PCB
  file) and for the standoff screw heads.
- **Magnetics:** foams, silicone, aluminium, brass and FR4 are all fine.
  **Don't use a steel plate or steel weights.** Use brass for weights and
  standoffs. Any small static field distortion (e.g. stainless screws) is
  calibrated out, but brass or titanium M2 screws near the sensors are nicer.

## Plate

- `plate-left.dxf` / `plate-right.dxf`: 14.0 mm switch cutouts (0.3 mm
  corner radius), 2.2 mm standoff holes, eight 10 × 4.5 mm gasket tabs. On the
  right half the plate stops at the keys: the trackpad sits over the inner
  column beside it, with the MCU module under it and the VGA bay behind. On the left half
  it covers the mouse column too, including a switch cutout for the rotary
  encoder.
- Aluminium 5052 or 6061 at 1.5 mm, waterjet/laser. POM or PC for a softer
  bottom-out.
- **FR4:** `hardware/mechanical/plate-{left,right}/*.kicad_pcb` are
  board-outline-only KiCad projects. Order them at 1.5 mm with the PCBs.
- Like the Corne, the 1.5u thumb key needs no stabiliser.

## Case (CNC aluminium)

`case-plan-*.dxf` layers:

| Layer | Meaning |
|---|---|
| `OUTER_WALL` | outside of the case: one smooth profile, with a flat back face at the ports |
| `INNER_WALL` | cavity: PCB outline + 0.75 mm, plus the VGA bay |
| `GASKET_POCKETS` | tab pockets (tab + 0.5 mm): gasket seat in the tray below, frame above |
| `PLATE` | plate outline with tabs, for reference |
| `ROOF` | where the top frame is a 1.5 mm roof: over the tab, the VGA bay and the USB-C ear |
| `DAUGHTERBOARD` | plan-view envelope of the vertical VGA board |
| `MCU_MODULE` | the soldered MCU module on the tab, under the trackpad |
| `PORTS` | DE-15 shell cutout and USB-C opening (right half), through the back face |
| `JACKSCREWS` | two Ø3.2 mm holes through the back face for the 4-40 jackscrews, 24.99 mm apart |
| `FLOOR_ACCESS` | Ø3 mm floor holes under the BOOT and RESET buttons (right half) |
| `FLOOR_POCKETS` | 1 mm pockets in the floor top under the USB-C (right half) and the encoder's pins (left half) |
| `TRACKPAD` | counterbore for the trackpad's overlay, 1.0 mm deep (right half; TPS65: 55.4 × 71.4 mm) |
| `TRACKPAD_WELL` | well under it for the pad module and FFC, 4.7 mm deeper; it opens into the cavity over the tab and the PCB tongue |

Suggested split: the **bottom tray** carries the floor, walls up to the lower
gasket seat and the lower tab pockets. The **top frame** carries the bezel
around the keys, the upper tab pockets and the **1.5 mm roof** (`ROOF`), which
covers the VGA bay, the tab and the USB-C ear. Join them with M3 screws from below through the wall thickness (6–8
places), clear of the gasket pockets. The left half is about 150 × 116 mm. The
right half is 202 × 116 mm with the TPS65 trackpad (171 mm with the 40 mm
Cirque).

Milling:

- **Outside:** one continuous profile. No concave radius is under 25 mm, and
  the convex corners are at least 6 mm, so a large cutter can finish it in a
  single pass. The walls are 7.25 mm thick, with at least 3 mm behind every
  gasket pocket. They don't bulge around each pocket.
- **Back face:** flat and 1.6 mm thick behind the VGA bay and USB-C, so both
  plugs mate fully. The ports are plain through-cuts from one side setup; no
  counterbores are needed.
- **Inside:** no radius under 1.5 mm (a 3 mm end mill). The inner side's
  gasket pocket is on the 1.5u thumb key's inner edge on the right half (below
  the trackpad) and on the mouse column beside M1 on the left.

### VGA daughterboard

![Daughterboard front/back](img/link-top.png) ![](img/link-bottom.png)

![VGA and USB-C plugs in the back face (render)](img/render-port.jpg)

- 33 × 13 mm board standing on edge in the **bay** at the inner-back corner,
  behind the inner column and column 5, with the DE-15 facing out of the back.
  The cable leaves backwards, away from your hands and out of the gap between
  the halves.
- The bay starts 4.5 mm further back than column 5 needs
  (`geometry.BAY_BACKSET`). That room is what lets the trackpad sit right
  beside Y/H/N; both halves share it, so their backs line up.
- The vertical DE-15F on the front is an **Amphenol FCI 10090929-S154XLF**:
  4-40 clinch nuts with board locks. The footprint is KiCad's vertical HD-15
  with the 1.2 mm pin holes and 3.1 mm board-lock holes Amphenol asks for
  (`lib/vgacorne.pretty`).
- Solder its board locks: they tie the shell to GND, and the jackscrews tie
  the case to the shell.
- The back carries 10 solder pads for a **10-pin JST-SH pigtail**, plus the
  cable-variant jumpers. Clip the DE-15's pin tails to about 1.5 mm first:
  they come through on the same side as the pads.
- The board sits about 6.1 mm (±0.3) behind the flange face on Amphenol's
  drawing. That drawing doesn't make clear which flange face it measures
  from, so check it on the first part: the 13 mm envelope leaves about
  3–4 mm for the pigtail's bend. The pigtail plugs
  into `J3`, which sits on the edge of the inner tab directly in front of the
  board, so a short (~5 cm) pigtail is enough.
- Two **4-40 female jackscrews** (Keystone 7229: 0.187" hex, 0.25" stud) go
  through the back face into the clinch nuts. They clamp the flange to the
  inside of the wall; that's the only fixing, and it sends cable forces
  straight into the case. The cable's thumbscrews thread into them.
  - A board-lock part can stop a long stud, so use a 0.25" one.
  - Keystone's figures come from distributor listings; check that the stud
    pulls the flange tight before it bottoms.
- The back face is 1.6 mm thick here, so the plug mates fully without a relief.
- Centre the shell about 7 mm above the floor top: the flange (12.55 mm) sits
  between the floor and the roof, with 14.1 mm clear.
- `PORTS` has the standard rear-mount cutout for shell size E, 20.5 × 11.4 mm
  (CECC 75 301-802); check it against your connector's datasheet.
- At full mating the plug's shell reaches about 1 mm into the 1.6 mm wall.
  That is the most D-sub makers allow with standard hardware, so the
  jackscrews' hex must be no taller than 4.8 mm (0.189"), or the plug won't
  seat. Keystone 7229's is 0.187".

### Trackpad (right half)

`hardware/vgacorne/trackpad.py` picks the pad. These notes describe the
default, the Azoteq TPS65; the 40 mm Cirque gets a round pocket on the same
principle.

- **Placement:** landscape, right beside Y/H/N over the inner column, so the
  index finger slides straight onto it. It spans the three rows: the moved VGA
  bay sets how far back it can go and the tilted 1.5u thumb key how low, which
  puts its middle about 3 mm behind the H row. It keeps 3 mm of aluminium to
  the keys, the VGA bay and the outside edge. The MCU module sits partly under
  its well, 1.6 mm below it.
- **Stack:**
  - The top is a 1 mm glass or acrylic overlay, 71 × 55 mm (the module plus
    3 mm all round) with about 7 mm corner radii. It sits flush in the
    `TRACKPAD` counterbore.
  - The 2 mm module is bonded to it with its own adhesive, centred.
  - The module hangs in `TRACKPAD_WELL` (module + 0.3 mm), so there is no
    aluminium under or right beside its electrodes.
  - The well is 4.7 mm deep under the overlay, for the module, its 2 mm ZIF
    connector and the fold of the FFC.
- **Cable:** the module's ZIF connector is 9.2 mm in from a long edge and
  25.3 mm from an end. Turn the module so that is the back edge and the end
  nearer the keys: the connector then sits right over J5 on a PCB tongue,
  and a short 6-pin 0.5 mm FFC folds down into it.
- J5 is bottom-contact and Azoteq doesn't say which side the pad's contacts are
  on. A paper mock-up decides between a same-side and an opposite-side FFC.
- **Case:** the outside profile wraps the pad with the same 25 mm minimum
  concave radius. The pad is why the right half is 51 mm wider than the left.

### Mouse column and rotary encoder (left half)

- The inner column beside T/G/B is exactly one key wide, in line with column
  5's rows: M1 (right click) beside T, M0 (left click) beside G and a rotary
  encoder beside B.
- **Encoder:** a Bourns PEC12R-4220F-N0024, upright with a 20 mm shaft, 24
  detents, no bushing and no push switch. Its 12.4 × 13.4 mm body stands on
  the PCB through an ordinary 14 mm switch cutout in the plate, like a key.
  Its body top is flush with the plate top.
  - KiCad's footprint for the bushing version (`-3x17F`) has the same pads.
    The `-4`'s mounting legs are narrower than the footprint's slots, so the
    signal pins locate it.
  - Its pins and legs come through about 3 mm: trim them to about 2 mm after
    soldering.
- **Knob:** 16 mm across and 11.5 mm tall, on the 6 mm D-flat shaft, pushed on
  to leave 2 mm above the shaft end.
  - Above the body, a ~7 mm collar round the shaft rises to 10.1 mm above the
    PCB. The flat runs from 13 mm to the shaft end at 20 mm.
  - The knob's underside clears the collar by 0.4 mm, and its D-bore (at least
    9.5 mm deep) grips the whole flat. Its top is about 2 mm above the keycaps.
  - A taller knob needs a recess at least 7.5 mm across underneath for the
    collar, or it sits higher.
  - It clears the left-click and B keycaps by 2 mm and the 1.5u thumb keycap by
    1.5 mm. A knob up to 17 mm across still leaves 1 mm.
- **Foam:** the plate foam has a switch-sized cut at the encoder, plus its
  pins. The case foam has a relief under its pins and legs, and the floor a
  1 mm pocket (`FLOOR_POCKETS`).
- **Standoff:** one extra M2 standoff between G, B, left click and the encoder,
  since the mouse column's plate would otherwise hang 20 mm off column 5.

### MCU module

- 19.4 × 25 mm castellated module, soldered flat onto landing pads J4 on top
  of the main PCB's tab, under the trackpad (see
  [architecture.md](architecture.md#mcu-modules)). It is 2.7 mm tall and
  1.6 mm below the trackpad's well, so the case needs no room for it. The
  back of the right half tapers from the keys, over the whole trackpad.
- A short PCB tongue from the tab reaches under the pad for its connector J5.
  It stays inside the pad's footprint.
- Changing module means desoldering it (hot air); the main PCB fits either.

### USB-C (right half)

The receptacle is on the PCB underside, on a small ear of the PCB that
reaches the back face behind column 4, beside the DE-15.
- **Position:** it overhangs the ear's edge by 0.46 mm, as HRO's drawing
  intends (`geometry.USB_OVERHANG`). That puts its face 1.9 mm inside the back
  face and its centre about 5.3 mm above the case underside (`USB_Z`).
- **Opening:** a fully seated plug's overmould stops about 0.45 mm short of
  the receptacle face (USB Type-C R2.5: a 6.65 mm plug in a 6.20 mm
  receptacle), so it goes ~1.4 mm into the 1.6 mm wall. The opening in `PORTS`
  is therefore 13.95 × 8.1 mm: the largest overmould the spec allows
  (12.85 × 7.0 mm) plus 0.55 mm all round for the floating sandwich. It is a
  plain through-cut.
- **Floor:** the shell hangs to 0.74 mm above the floor top, so the floor has a
  1 mm pocket under it (`FLOOR_POCKETS`), and gasket travel can't bottom it out.

## What to model next

A parametric 3D case (e.g. build123d or FreeCAD) can extrude the case-plan
layers directly:

1. Floor: `OUTER_WALL`, 3 mm, minus `FLOOR_ACCESS` and 1 mm deep `FLOOR_POCKETS`.
2. Walls: `OUTER_WALL` − `INNER_WALL`, up to 18.6 mm.
3. Tab pockets at the plate height, split between tray and frame.
4. 1.5 mm roof over `ROOF`. Port and screwlock through-cuts in the back face.
5. Optional wedge for a typing angle, brass weight pocket, tenting-leg inserts.
