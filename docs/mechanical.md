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
| 3.0 | floor top (3.0 mm floor) |
| 3.0 – 6.5 | case foam, 3.5 mm (poron sheet or silicone pad) |
| 7.0 | PCB underside (tallest part below it: USB-C, 3.3 mm) |
| 8.6 | PCB top |
| 12.1 | plate underside (MX spec: plate top is 5.0 mm above the PCB top) |
| 13.6 | plate top |
| 12.9 – 17.6 | trackpad module, its connector and the FFC fold, in their well (right half) |
| 14.0 – 16.6 | MCU module (behind the trackpad): 5.4 mm connector stack, 1.0 mm board, 1.6 mm LQFP |
| 17.1 | underside of the 1.5 mm roof over the MCU module and VGA bay (0.5 mm above the module) |
| 17.6 – 18.6 | trackpad overlay, flush with the top (right half) |
| 18.6 | top of case (frame 5 mm above the plate); scroll-wheel shaft (left half) |
| 27.6 | top of the scroll wheel, about level with the keycaps |

The frame height is set by the parts under the roof: the VGA bay needs more
than the DE-15's 12.55 mm flange (it gets 14.1 mm), and the module needs 8.0 mm
above the PCB (it gets 8.5 mm).
For a typing angle, keep these heights at the front and raise the back by
`depth × tan(angle)`. The case is 116 mm deep, so 5° adds about 10 mm.

## Poron or silicone

Every soft layer has its own DXF. Either material fits the same pockets;
silicone is springier, poron is more muted.

| Layer | File | Poron | Silicone |
|---|---|---|---|
| Gaskets (above and below each plate tab) | tabs in `plate-*.dxf`, pockets in `case-plan-*.dxf` | 3 mm PORON strips, 10 mm wide | 3 mm silicone strip or "sock" (≈ Shore 30–40A) |
| Case foam (under the PCB) | `foam-case-*.dxf` | 3.5 mm PORON sheet | 3.5–4 mm poured or cut silicone pad (≈ Shore 10–20A) |
| Plate foam (optional, between plate and PCB) | `foam-plate-*.dxf` | 3.5 mm PORON | 3.5 mm silicone |

- Aim for about 25 % gasket compression when the case is closed. Tune it with
  strip thickness, not by changing the pockets.
- Leave the 0.5 mm air gap above the case foam (`foam_gap`). Foam that
  touches the PCB preloads the gaskets and kills the flex.
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
  column beside it, and the VGA bay and MCU module are behind. On the left half
  it covers the mouse column too, with a notch at its inner edge for the scroll
  wheel and its encoder.
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
| `ROOF` | where the top frame is a 1.5 mm roof: over the MCU module, the VGA bay and the USB-C ear |
| `DAUGHTERBOARD` | plan-view envelope of the vertical VGA board |
| `MCU_MODULE` | the plug-in MCU module behind the trackpad (under the roof) |
| `PORTS` | DE-15 shell cutout and USB-C opening (right half), through the back face |
| `JACKSCREWS` | two Ø3.2 mm holes through the back face for the 4-40 screwlocks, 24.99 mm apart |
| `FLOOR_ACCESS` | Ø3 mm floor holes under the BOOT and RESET buttons (right half) |
| `TRACKPAD` | counterbore for the trackpad's overlay, 1.0 mm deep (right half; TPS65: 55.4 × 71.4 mm) |
| `TRACKPAD_WELL` | well under it for the module and FFC, 4.7 mm deeper; it opens into the cavity over the tab and module ear |

Suggested split: the **bottom tray** carries the floor, walls up to the lower
gasket seat and the lower tab pockets. The **top frame** carries the bezel
around the keys, the upper tab pockets and the **1.5 mm roof** (`ROOF`), which
covers the VGA bay and the MCU module and keeps the module seated in its
socket. Join them with M3 screws from below through the wall thickness (6–8
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
- The vertical DE-15F is on the front. The back carries 10 solder pads for a
  **10-pin JST-SH pigtail**, plus the cable-variant jumpers. The pigtail plugs
  into `J3`, which sits on the edge of the inner tab directly in front of the
  board, so a short (~5 cm) pigtail is enough.
- The DE-15's **4-40 screwlocks** clamp the connector flange to the inside of
  the back face. That's the only fixing, and it sends cable forces straight
  into the case.
- The back face is 1.6 mm thick here, so the plug mates fully without a relief.
- Centre the shell about 7 mm above the floor top: the flange (12.55 mm) sits
  between the floor and the roof, with 14.1 mm clear.
- Use the panel cutout from your connector's datasheet. `PORTS` is a
  19.2 mm-wide placeholder for shell size E.

### Trackpad (right half)

`hardware/vgacorne/trackpad.py` picks the pad. These notes describe the
default, the Azoteq TPS65; the 40 mm Cirque gets a round pocket on the same
principle.

- **Placement:** landscape, right beside Y/H/N over the inner column, so the
  index finger slides straight onto it. It spans the three rows: the moved VGA
  bay sets how far back it can go and the tilted 1.5u thumb key how low, which
  puts its middle about 3 mm behind the H row. It keeps 3 mm of aluminium to
  the keys, the VGA bay and the outside edge, and its well clears the MCU
  module behind it by 0.9 mm.
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
  nearer the keys: the connector then sits right over J5 on the module ear,
  and a short 6-pin 0.5 mm same-side FFC folds down into it.
- **Case:** the outside profile wraps the pad with the same 25 mm minimum
  concave radius. The pad is why the right half is 51 mm wider than the left.

### Mouse column and scroll wheel (left half)

- The inner column beside T/G/B is exactly one key wide. From the top: the
  scroll wheel, 3 mm behind T, then M0 (left click) beside G and M1 (right
  click) beside B, in line with those rows. The wheel is 4 mm clear of M0's
  keycap and 2.8 mm from T's; M1 is 2.5 mm clear of the 1.5u thumb key's.
  The wheel can't go further back because the link connector J3 is under it:
  J3 sits 3 mm toward column 5 so the encoder's legs clear it.
- **Wheel:** an 18 mm rubber wheel, 6 mm wide, on the flatted shaft of a
  Bourns PEC12R-2217F-N0024 (24 detents). The encoder stands on the PCB with
  its shaft 10 mm up, level with the case top, so the wheel's top is level
  with the keycaps and its bottom clears the PCB by 1 mm. The body (12.5 mm
  wide, 13.4 mm tall) sits on the inner side, the wheel on the shaft toward
  column 5; cut the shaft to 13 mm so it stays out from under T's keycap.
- **Plate:** a notch from the wheel's outer face out through the plate's inner
  and back edges: the wheel crosses the plate as a 13.8 mm chord, and the body
  runs to the edge anyway. The plate foam has the same notch, and the case
  foam a relief under the encoder's legs.
- **Standoff:** one extra M2 standoff between G, B and the two mouse keys,
  since the mouse column's plate would otherwise hang 20 mm off column 5.

### MCU module

- 19.2 × 16.8 mm module on a 2×12, 1.27 mm SMD socket, on a PCB ear behind
  the trackpad and beside the VGA bay (see
  [architecture.md](architecture.md#mcu-modules)). The ear runs from the back
  face forward under the pad, where it also carries the pad's connector J5.
  The top of the module is 8.0 mm above the PCB; the roof is 0.5 mm above
  that. A thin foam pad on the underside of the roof stops rattle.
- To swap it: open the case, lift the module straight up, plug in the other
  one, then flash its firmware.

### USB-C (right half)

The receptacle is on the PCB underside, on a small ear of the PCB that
reaches the back face behind column 4, beside the DE-15. Its centre is about
5.4 mm above the case underside. The opening in `PORTS` is 11 × 6 mm through the
1.6 mm back face, so the floating sandwich can move ±0.5 mm. The overmould
sits against the flat face, so no recess is needed.

## What to model next

A parametric 3D case (e.g. build123d or FreeCAD) can extrude the case-plan
layers directly:

1. Floor: `OUTER_WALL`, 3 mm, minus `FLOOR_ACCESS`.
2. Walls: `OUTER_WALL` − `INNER_WALL`, up to 18.6 mm.
3. Tab pockets at the plate height, split between tray and frame.
4. 1.5 mm roof over `ROOF`. Port and screwlock through-cuts in the back face.
5. Optional wedge for a typing angle, brass weight pocket, tenting-leg inserts.
