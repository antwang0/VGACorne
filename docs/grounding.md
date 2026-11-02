# Grounding an aluminium case

The sandwich floats on PORON, so an aluminium case is an isolated conductor
right under your hands, with the plate, another conductor, floating 5 mm
inside it. This is the plan for tying every conductor a hand can reach to
the USB ground over a short, low-inductance path that doesn't run through
signal copper: the case (tray and frame), the plate, the encoder knob, both
connector shells, and whatever tripod or arm is screwed into the 1/4"-20
sockets. It also gives the trackpad the grounded surround Azoteq asks for.
Target: ±8 kV air / ±4 kV contact (IEC 61000-4-2) without a reset or damage.

The design uses one ground. The USB-C shell is tied straight to GND, so the
case ties to GND too; a separate chassis net with an RC or ferrite between
them would only add impedance to the discharge path.

## What is grounded today

| Conductor | Tied to | How | State |
|---|---|---|---|
| USB-C shell (J1, right half) | GND | four soldered shell pads | fine; the case opening clears it by 0.55 mm, so it never touches the case |
| DE-15 shell (both halves) | daughterboard GND | soldered board locks | fine |
| Case | DE-15 shell | the flange clamped against the inside of the back wall by the two 4-40 jackscrews | **only if that face is bare**; anodising is an insulator. From there to the main or satellite GND over the pigtail's two GND wires, about 50 mm of 28 AWG: a thin, inductive path (below) |
| Frame to tray | each other | eight M3 screws in masked (bare) tapped holes; heads on anodised counterbores | **unreliable** |
| Plate | nothing | the standoff holes are 2.2 mm NPTH without copper; the gaskets are insulators | **floating** |
| Encoder frame and shaft (the knob) | nothing | the footprint's two mounting-leg pads (`SH`) are plated but have no net | **floating**, 2 mm from your fingers with a metal knob |
| Tripod / arm | tray | bare 1/4"-20 threads | fine once the tray is grounded |
| Trackpad bezel (frame) | case | | needs the case grounded: Azoteq wants grounded, not floating, metal near the electrodes |

**Why the jackscrew path alone isn't enough.** An 8 kV discharge peaks near
30 A in about a nanosecond. The pigtail's two wires are roughly 30 nH in
parallel, so the case lifts about a kilovolt above PCB ground for that
nanosecond. Air breaks down at about 3 kV/mm, and the plate tabs sit 0.25 mm
from the frame in their pockets and the PCB edge 0.75 mm from the wall: a
secondary arc into the sandwich is plausible. A direct bond of a few nH
cuts that to a tenth, and a grounded plate makes an arc to the plate harmless.

## The plan

### 1. Case finish: anodise with bare spots

Keep "bead blast, then anodise". The case plan's `BARE` and `BARE_FLOOR`
layers and the hole drawings show what the anodiser masks (or the shop skims
0.05 mm after anodising):

- the **seam faces**, the tray's wall top and the frame's underside over the
  whole wall width (hidden when assembled): the frame-to-tray bond, and a
  continuous shield seam;
- the **DE-15 flange seat** inside the back wall: 32 × 13 mm around the D
  cutout, both halves;
- the **two floor pads** per half for the spring fingers (section 2), Ø8;
- the tapped holes, as already drawn.

A brush-on chromate (Alodine pen, SurTec 650) on the bare spots stops the
oxide that would otherwise raise contact resistance over the years.
Alternative: chromate conversion coating of the whole part (MIL-DTL-5541
Type II Class 3, "chem film"): conductive everywhere with no masking, but a
clear-to-gold finish that marks easily. Anodising with masks is the
recommendation.

### 2. PCB-to-case bond: two spring fingers per half

An SMD EMI spring finger on the PCB underside, pressing on a bare pad in the
floor: **Würth WE-SECF 331236362553** (G1, G2 on each half; `vgacorne:
EMI_Finger_WE-SECF_3.6x2.5mm`). Phosphor bronze, Ni/Sn, 3.6 × 2.5 mm, 5.3 mm
free height, recommended working height 3.4–5.0 mm. The floor top is at
3.5 mm and the PCB underside at 7.5 mm, so it works at **4.0 mm at rest and
3.56 mm under a hard press** (0.44 mm of gasket travel), inside its range with
±0.2 mm of tolerance to spare either way, so the floor pads stay flat. Würth
gives no force figure; two fingers against the gaskets' ~13 N preload per half
is a small fraction. No LCSC number: order four from Farnell, RS or Mouser and
fit them by hand (or leave them off for a printed case). Other candidates
checked: the 1.5–2.5 mm WE-SECF sizes and Harwin's EZ-BoardWare range don't
reach 4 mm; 331011452048 (4.8 mm) works only at 4.0–4.5 mm.

- **Where:** right half, G1 behind column 3 (the autoplacer's nearest free
  spot to the USB-C corner, so a discharge into the case leaves through the
  USB cable instead of crossing the pour) and G2 at the front outer corner.
  Left half, G1 below the VGA bay, G2 at the front outer corner. Both halves'
  spots were checked against the case plan: plain floor, clear of the bosses,
  pockets and access holes. The case foam gets a relief like the other tall
  bottom-side parts (`TALL_PARTS`); the fit check models them 3.3 mm deep,
  since they touch the floor by design.
- **Why not the mount bosses:** they stop 1 mm under the PCB (0.56 mm at a
  hard press), below any BeCu finger's working range (Würth's smallest,
  331031321515, works at 1.0–1.2 mm; NH Technology's 1 mm contact is brass
  and stainless with an undocumented compressed height). A Ø6 disc of
  conductive fabric-over-foam, 1.5 mm thick, would work there at 33–63 %
  compression, but it's a hand-fitted sticky part with more preload. Fallback
  only.
- **Why not a strap:** a 30–50 mm wire or braid from a PCB pad to an M3
  screw in the floor needs no special part, but it's hand-fitted and about
  as inductive as the pigtail. Second fallback, if fingers can't be sourced.

With the fingers in place the jackscrew path becomes a second, parallel bond
for the DE-15 shell itself. The left half's ground still reaches the USB only
over the VGA cable (pins 5/10, the coax returns and the shells), which is
fine; unplugged, it is unpowered and its case is just a metal box.

### 3. Plate

An aluminium plate must be tied to PCB ground, or it is the biggest floating
conductor under the keycap gaps. The standoff holes are **2.2 mm PTH with
3.4 mm GND pads** on both sides (`Mechanical:MountingHole_Pad`, pin 1 = GND;
the 3.5 mm hex standoff and the M2 head both sit on the pad): the brass
standoffs and M2 screws bond the plate at seven or eight points. Leave the
plate bare or bead-blasted (it's under the caps); if it is anodised, mask Ø6
on top around at least two holes, or fit M2 internal-tooth washers under
those two screw heads. FR4, POM or PC plates are insulators and need none of
this.

This applies to the printed case too: with no shielding, the plate is the
conductor nearest the fingers.

### 4. Encoder

ENC1's two mounting-leg pads (`SH`) are on GND, so a metal knob discharges
through the frame and not across the A/B contacts into the mux. The stock
`Device:RotaryEncoder` symbol has no shell pin, so the project library has
`vgacorne:RotaryEncoder_SH`, KiCad's symbol plus an `SH` pin. Applies to both
case builds.

### 5. Trackpad

Nothing to change. The overlay is glass or acrylic, the module hangs in a
well with no aluminium under or beside its electrodes, and the bezel stays
3–4 mm away; once the case is bonded that bezel is grounded, as Azoteq asks.
A floating bezel would couple hand noise into the sensor instead.

## Work list

The PCB side is done (2026-11-02), so the boards you order carry it:

- [x] `customlib.py`: `Standoff_M2` with a 2.2 mm PTH and 3.4 mm GND pads;
      the WE-SECF finger footprint; `RotaryEncoder_SH`.
- [x] `circuits.py`: standoffs as `MountingHole_Pad` on GND; G1/G2 per half
      on GND; ENC1's `SH` on GND. `pcb.py` places the fingers; the foam gets
      their reliefs.
- [x] Carried into the routed boards by script (*Update PCB from Schematic*
      is GUI-only): footprints swapped, nets set, fingers placed in free
      copper, and the tracks Freerouting had run against the old holes bent
      round the new pads (seven sites). `generate.py check` clean.
- [x] `mechanical.py` / `case3d.py`: `BARE` (seam face, flange seat) and
      `BARE_FLOOR` (Ø8 pads under G1/G2) in the case plan; the hole drawings
      outline them, list the pads as D1/D2 and carry the masking note.
- [ ] `bring-up.md`: with a meter, case to USB shell under 1 Ω on the right
      half and under a few ohms on the left through the cable; plate and knob
      to GND; trackpad sensitivity the same with the case on and off; an
      ESD-gun test at ±4 kV contact if one is to hand, or a dry-day test.

Ordering boards **without** these changes is possible with an FR4 or POM
plate, a plastic knob and the DE-15 flange seat masked: the case is then
grounded through the jackscrews alone, with the kilovolt bounce above.
