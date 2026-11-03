# Cost

What one VGACorne costs to build, from quotes taken on 2026-11-03 and
current distributor prices. The JLC quotes are real; the rest are estimates,
marked as such. Prices in USD before shipping and tax.

## Quotes (2026-11-03)

**JLCPCB, main board:** 5 PCBs (2-layer, 1.6 mm), 5 assembled, two-sided
Standard assembly (J5 is on top).

| Line | | |
|---|---|---|
| PCB, 5 pcs | 12.70 | engineering 4.00, boards 8.70 |
| Assembly setup | 51.50 | Standard assembly; Economic would be about 8 |
| Stencils | 16.54 | two sides |
| Feeder loading | 37.20 | about 12 extended part types |
| Components, 24 lines | 52.95 | 105 × DRV5055A3 at 0.30 (the 100+ price break) is 31.35 of it |
| SMT | 3.81 | |
| **Total** | **175.22** | **35 per assembled board** |

The fixed fees (setup, stencils, feeders: about 105) are the same for 2 or
5 boards, so the per-board price drops steeply with the second to fifth.
Hand-soldering J5 and ENC1 and choosing Economic assembly would save roughly
55-60 per board type (about 12 per board at quantity 5); the fab step places
them by default ([hardware/README.md](../hardware/README.md#ordering-from-jlc)).

**JLCCNC, case-left-tray, quantity 1:** 6061, bead blasted and anodised
natural matte, threads included.

| Line | |
|---|---|
| Material | 8.95 |
| Engineering fee | 9.07 |
| Machining | 41.25 |
| Surface finish | 2.12 |
| **Total** | **61.39** |

The instant quote doesn't read the `BARE` masking from the drawing: note it in
the order remarks, or scrape the few bare spots after anodising
([grounding.md](grounding.md)).

## One keyboard (aluminium)

| Group | Estimate | Basis |
|---|---|---|
| Main board, 5 assembled | 175 | quote |
| Satellite board, 5 assembled | ~150 | estimate from the main quote: 23 sensors, fewer extended parts |
| MCU module, 5 assembled (4-layer, castellated) | ~60 | estimate; the AT32F405RCT7 (~4 each) is the low-stock part |
| VGA daughterboards, 5 bare | ~5 | estimate |
| **Electronics** | **~390** | buys five sets of boards |
| Case: 2 trays | ~125 | quote × 2 |
| Case: 2 frames | ~180-250 | estimate: bezel, pockets and the trackpad well, 1.5-2× a tray |
| **Case** | **~300-380** | |
| Hand-fit parts: 2 × DE-15, jackscrews, pigtails, encoder, knob, 4 spring fingers | 35-55 | distributor prices |
| 44 HE switches | 25-40 | |
| Keycaps (Corne set with 1.5u thumbs) | 30-80 | |
| Trackpad TPS65, overlay, FFC (optional) | 45-60 | Keycapsss; EOL at Azoteq |
| Plate, 2 × 1.5 mm aluminium, laser or waterjet | 30-60 | |
| Standoffs, screws, feet, VGA cable | 25-35 | |
| PORON gaskets and foams | 15-25 | or CustomKBD 3 mm PORON cut from the DXFs, ~6 a side |
| **Everything else** | **~170-260** | |
| **Total, one unit** | **~860-1,030** | with four spare board sets |

A printed case (`mechanical/case-printed/`, ASA or PA12 with 20 heat-set
inserts) replaces the case line with 40-60 of filament and inserts, or
100-160 from a print service: about 600-800 all-in.

## Three to five units

| | Per unit at 1 | Per unit at 5 | Why |
|---|---|---|---|
| Electronics | 390 (4 spare sets) | ~80 | the five board sets are already in the quote |
| Case | 300-380 | ~200-280 | engineering fees and setup dilute; ask JLCCNC for the 5-set price |
| Everything else | 170-260 | 150-230 | small discounts on switches and caps |
| **Total** | **860-1,030** | **~430-590** | |

The five assembled board sets are the natural reason to build more than one:
after the first unit, the PCBs for the next four are paid for.

## Before paying

- Module: the AT32F405RCT7 must show as in stock and placed (73 at JLC on
  2026-10-01).
- Satellite: the encoder (LCSC C143785) had no stock in 2025; if JLC can't
  source it, drop it from the BOM and hand-solder it.
- Case: finish bead blast + anodise, threads ticked, `.dxf` drawings
  attached, `BARE` masking in the remarks.
- Check the part rotations in JLC's placement preview
  ([hardware/README.md](../hardware/README.md#ordering-from-jlc)).
