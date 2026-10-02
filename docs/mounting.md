# Tenting and desk mounting

Every option here attaches to the two 1/4"-20 sockets under each half (see
[mechanical.md](mechanical.md#tenting-and-desk-mounting)).
- **One socket** takes a tripod or ball head.
- **Both sockets** take a two-screw Arca-Swiss plate (slotted, or adjustable
  28–40 mm), which stops the half twisting.
- **Spacing:** the sockets are 38.6 mm apart on the left half and 38.2 mm on the
  right.

The halves' cases weigh about 275 g (left) and 405 g (right) in aluminium,
less printed. Everything must leave the back face clear for the VGA cable and USB-C.

Prices are from 2026-10-01. Ones marked "(snippet)" came from search results,
not the vendor's page, and "?" means no price was found. Check before buying.

## Tenting

A ball head on one socket gives any angle. The outer edge drops as the half
tilts, so the socket has to stand at least this high above the desk:

| Half | Socket to outer edge | 15° | 20° | 30° | 45° |
|---|---|---|---|---|---|
| Left | 85 mm | 22 mm | 29 mm | 42 mm | 60 mm |
| Right | 104 mm | 27 mm | 35 mm | 52 mm | 73 mm |

| Option | Attaches by | Angle / height | Rated load | Price | Fit for VGACorne |
|---|---|---|---|---|---|
| **SmallRig BUT2664** tabletop tripod | 1/4"-20; the head has an Arca clamp | ball head | 2 kg (head) | $36–45 | **Recommended for aluminium.** The clamp takes the two-screw plate. |
| **Manfrotto PIXI EVO** | 1/4"-20 ball head | 10.5–20 cm tall, two leg angles | 2.5 kg | about $85 | Both builds |
| **Manfrotto PIXI** | 1/4"-20 ball head, push-button lock | ±35° tilt, up to 13.5 cm | 1 kg | $30–36 | **Recommended for printed halves.** Light for aluminium. |
| Manfrotto Pocket MP3-BK | 1/4"-20, flat folding legs | up to 34° | 1.5 kg | €33.95 | Low tents only: splitkb's Kyria hit the desk at 25°, and the right half reaches further |
| SmallRig 2948B / BUT2665 mini ball heads | 1/4"-20 | ball head; needs a base or tripod | 1.5 / 2 kg | ? | Both, on a base of your choice |
| Neewer Z-Flex tilt head | 1/4" or 3/8" underneath, quick-release plate on top | folding tilt, 0–90° | 3 kg | ? | Both. Its flat base is stable on a desk; Bastard Keyboards use it. |
| Ulanzi MT-08 | 1/4"-20 ball head | 13–23.5 cm | not rated | ? | Printed halves |
| keeb.io MagSafe stand R2 | steel ring (56/46 mm) stuck under the half; magnet on an adjustable arm | adjustable | – | $34.99 | **Not recommended:** the stand's magnet ends up 7–9 mm under the Hall sensors ([below](#why-not-magsafe)) |
| ErgoKeeb tenting kit | MagSafe ring | adjustable | – | $40 | As above |
| Keebart MagLift | MagSafe ring | adjustable | – | €39.90 | As above |
| TheKeebLab metal kit | MagSafe ring | adjustable | – | €49 | As above |
| keyboard-hoarders MagSafe kit | MagSafe ring; locking base that doesn't rotate | adjustable | – | $64 | As above |
| MoErgo Glove80 legs | M4 studs screwed into the case, feet on the ends | up to ~25–30° | – | MoErgo spares | No: needs M4 inserts on the inner edge (not modelled). The right half needs ~49 mm legs for 15°. |
| Adhesive legs (holykeebs, beekeeb Bobtail, PandaKB) | tape | 2–3 low steps (Bobtail: 6.1 / 26.9 mm) | – | $6.50–20 | Left half, low tents only |
| splitkb Tenting Puck | adds a 1/4"-20 thread to boards without one: 4 × M2 on a Ø38.1 mm circle | – | – | €28.88 a pair (snippet) | Not needed: the sockets are built in |
| Printable stands (Printables: McAbra tenting kit, Corne v4.1 tenting base) | screws or a cradle | fixed or parametric | – | free | Would need adapting, and a cradle must leave the back face open. Skip the magnetic ones (e.g. Jakmazdev's MagSafe stand), for the same reason. |

These are built for other keyboards, so they're for reference only:
- **ZSA Moonlander tripod kit:** 1/4"-20 blocks on M2.6 screws.
- **ZSA Voyager magnetic mount:** $89; magnets on its steel bottom plate.
- **Kinesis Advantage360:** a #8-32 hole.
- **Kinesis Freestyle Ascent:** 20–90° in 10° steps.
- **Dygma Raise and Defy:** stepped kits.

**Picks:** SmallRig BUT2664 for the aluminium halves and a Manfrotto PIXI for the
printed ones. To swap setups quickly, put an Arca quick release on the stand,
e.g. a Falcam F38 or Ulanzi Claw (about $30). It clicks on and off like
MagSafe, with no magnet.

### Why not MagSafe

A MagSafe stand's magnet presses against the steel ring under the case. That
puts it about 7 mm below the Hall sensors in the aluminium case and 9 mm in the
printed one. Field at the sensor (DRV5055A3 figures from
[sensors.md](sensors.md)):

| | Field at the sensor |
|---|---|
| A full keypress | about 20–55 mT (400–1,100 ADC counts) |
| The firmware's starting bottom-out threshold | about 20 mT (400 counts) |
| A MagSafe magnet directly under a sensor | about 10–35 mT (estimate, for a 1–2 mm N52 ring) |

A 56 mm ring always passes under several sensors.
- **Clipping:** the sensor reads up to ±88 mT. With a strong switch giving
  ~75 mT, an offset in the same direction pushes keys over the ring past that
  limit, so they lose the bottom of their travel.
- **Attaching or detaching while plugged in:** libhmk calibrates each key's
  resting value only in the first 500 ms after power-up. Moving the half onto
  or off the stand shifts the keys over the ring by about a full keypress.
  They read as pressed, or go dead, until you replug or recalibrate. Quick
  attach and detach is the whole point of MagSafe, so this defeats it.
- **The steel ring alone** is harmless: it's thin and far from the switch
  magnets, and calibration absorbs its small, constant effect.

If you use one anyway: put the half on the stand before plugging in USB, or
recalibrate in hmkconf afterwards. Then check in hmkconf's debug view that no
key over the ring clips at the bottom of its travel.

## Desk and chair mounting

Fit each half with an Arca plate on both sockets. Each mount then needs only an
Arca clamp. Keep the reach under about 25 cm: rest load at the end of a long arm
flexes it more than the typing does. No vendor publishes stiffness figures.

| Option | Where | Holds on by | Keyboard interface | Rated load | Price | Notes |
|---|---|---|---|---|---|---|
| **Neewer ST20** 11" arm + clamp | above the desk | clamp, 15–52 mm | 1/4"-20 | 2 kg | about $25.59 | **Budget pick.** Some flex under resting hands; add spring washers to the joints. |
| SmallRig 1138B / 4373 crab clamp + arm | above the desk | crab clamp | 1/4"-20 | 1.5 kg | $14.99 / $17.99 | Light duty |
| SmallRig 4900 Rosette 11" arm | above the desk (with a clamp) | – | 1/4" with locating pins; 3/8" ARRI end | 3 kg | $39.99–59.87 | Needs a clamp |
| SmallRig 4862 clamp + 20.6" arm | above the desk | clamp | 1/4"-20 | arm 3 kg, clamp 15 kg | $99.99 | Middle option; long reach |
| Kondor Blue Cine magic arm | above the desk | clamp | 1/4"-20 | 4–5 lb | $39.99 clamp; $95 NATO version | |
| **Manfrotto 035RL Super Clamp + 244N friction arm** | above the desk | Super Clamp, 13–55 mm | 1/4" and 3/8" | clamp 15 kg, arm 3 kg | $44.95 + $138.95 | **Premium pick.** One knob locks every joint; 53 cm long. |
| Elgato Solid Arm / Master Mount L | above the desk | pole, 22–49" | 1/4"-20 | 2 kg / 4.5 lb | $39.99 / $59.99 | |
| **Falcam F38** quick release | on the arm's end | – | Arca-type base; takes your two-screw plate | 15 kg | $29.95 | Quick on and off |
| Ulanzi Claw Gen II | on the arm's end | – | Arca-type | 50 kg (claimed) | $30.95 | |
| **Pro Signal 1290B** pole arm | beside the chair or desk | clamps a 30–60 mm post (e.g. a chair's arm post) | VESA 75/100 (add the plate below) | 10 kg | $35–70 | Most rigid in community reports; no gas spring, so fine with light loads |
| CAMVATE C3031 cheese plate | adapter | – | VESA 75 to 1/4"-20 and 3/8"-16 | – | $14.60 | Goes on the 1290B |
| MoErgo "captain's chair" build | chair arms | 2 × 1290B + C3031 + a 1/4" stud + quick release | Arca or MoErgo plate | – | $150–200 total | **Chair pick.** Users call it "rock solid". |
| **Humanscale 6G + 6G500 Big Board** (27" × 10.6") | under the desk | track | flat board: bolt an Arca clamp or ball head through it per half | – | $260–425 | **Under-desk pick.** Holds both halves up to about 510 mm apart. |
| Humanscale 6G + 900 board (19" × 10.6") | under the desk | track | flat board | – | about $390 | Halves at most about 319 mm apart: tight for shoulder width |
| 3M AKT150LE | under the desk | track | 19.5" × 10.6" board; height +4" / −6", tilt +10° / −15° | – | $227.64 list | Narrow for shoulder width |
| Fellowes Office Suites drawer | under the desk | screws into the desk | tray | – | $49.99 | |
| Stand Up Desk Store clamp-on tray | under the desk | clamps a desk up to 1.5" thick | 33" × 12" tray | – | ? | No drilling |
| VIVO MOUNT-KB02 / KB03L | on a VESA monitor arm | VESA | tray | 6.4 lb (KB03L) | ? | Community reports call VIVO's pole mount "less solid" |
| 2020/2040 aluminium extrusion | across the desk | clamps or brackets | M5 T-nuts: needs an adapter plate | – | ? | Rigid and cheap |
| Svalboard carrier plates | arm end | – | 1/4"-20 with ARRI-style anti-rotation, for SmallRig Rosette arms | – | $75 (snippet) | Made for the Svalboard |
| eLink Pro chair tray | chair | – | tray | – | ? | Reviews: wobbly, needs re-tightening |
| Rehadapt Monty 3D Plus | chair or table | frame clamp | – | 3 kg (HD: 6 kg) | $1,128 / $1,328 | Assistive-tech arm; overkill |

**Picks** (per pair of halves, with the Arca plates):

| Where | Budget | Premium |
|---|---|---|
| Above the desk | 2 × Neewer ST20 + 2 × Falcam F38: about $110 | 2 × Manfrotto 035RL + 2 × 244N + 2 × Ulanzi Claw or F38: about $430 |
| Under the desk or at the chair | MoErgo's captain's-chair parts: $150–200 | Humanscale 6G + Big Board, plus two clamps: $320–485 |

**To manufacture,** only if wanted:
- **Custom Arca foot plate,** one per half: 6061, 38 mm wide with 45° flanks,
  two counterbored 1/4"-20 holes at the socket spacing, and rubber-foot pockets
  so it doubles as a foot. Copy the flank height from a real Arca-Swiss or RRS
  plate. About $10–30 each at JLCCNC (estimate).
- **L-bracket** for vertical or side mounting: 3 mm 5052 with 1/4" slots, about
  $20–40 at SendCutSend or OSH Cut (estimate).
- **Tray adapter:** a 4–5 mm aluminium strip that bolts two Arca clamps to a
  tray at shoulder width.

## Sources

- **Tenting:**
  - [splitkb Tenting Puck](https://github.com/splitkb/tenting_puck), [Manfrotto Pocket at splitkb](https://splitkb.com/products/manfrotto-pocket-tripod)
  - [Manfrotto PIXI EVO](https://www.manfrotto.com/global-en/pixi-evo-2-section-mini-tripod-black-light-and-compact-mtpixievo-bk/), [SmallRig BUT2664](https://www.smallrig.com/smallrig-tabletop-mini-tripod-with-panoramic-ball-head-but2664.html)
  - [Ulanzi MT-08](https://www.bhphotovideo.com/c/product/1519312-REG/ulanzi_1601_mt_08_extensible_mini_tripod.html), [Neewer Z-Flex](https://neewer.com/products/neewer-upgraded-z-flex-tilt-tripod-head-66600458)
  - [keeb.io R2](https://keeb.io/products/magnetic-magsafe-tenting-stand-kit-for-split-keyboard-r2), [ErgoKeeb](https://www.ergokeeb.com/products/tenting-tilting-kit-for-split-keyboards-stand-typing-set-of-2-1-pair), [Keebart MagLift](https://www.keebart.com/products/maglift), [TheKeebLab](https://www.thekeeblab.com/products/split-keyboard-tenting-kit-metal), [keyboard-hoarders](https://keyboard-hoarders.com/products/tenting-magsafe-kit)
  - [Glove80 tenting](https://docs.moergo.com/glove80-user-guide/customizing-the-tenting-angle/), [ZSA Moonlander tripod kit](https://www.zsa.io/moonlander/tripod-kit), [ZSA Voyager mount](https://www.zsa.io/voyager/tripod-mount)
  - [Bobtail legs](https://shop.beekeeb.com/products/bobtail-keyboard-tenting-legs-for-split-keyboards), [holykeebs feet](https://holykeebs.com/products/tenting-feet)
  - Printables: [McAbra kit](https://www.printables.com/model/1655418-tenting-kit-for-a-split-keyboard), [Corne v4.1 base](https://www.printables.com/model/1364212-corne-crkbd-v41-tenting-base)
- **Mounting:**
  - [Manfrotto 244 arm](https://www.manfrotto.com/global-en/photo-variable-friction-arm-with-bracket-244/)
  - [MoErgo custom mounting](https://docs.moergo.com/glove80-user-guide/appendix-custom-mounting/), [captain's-chair build](https://the-gadgeteer.com/2025/02/26/moergo-glove80-new-switches-and-a-build-guide-for-your-very-own-captains-chair/)
  - [Svalboard carrier plates](https://svalboard.com/products/carrier-plates), [Rehadapt Monty 3D](https://rehadapt.com/product/monty-3d-plus-hd/)
  - [Community mounting notes](https://sites.google.com/view/keyboards/hardware/mounting)
- **Standards:**
  - [ISO 1222 preview](https://cdn.standards.iteh.ai/samples/55918/c73a7958dcef45ada49bf2fdcc959786/ISO-1222-2010.pdf) (tripod socket)
  - [Arca-Swiss plates](https://arca-swiss-usa.com/collections/camera-plates)
- **Manufacturing:**
  - [SendCutSend pricing](https://sendcutsend.com/pricing/), [JLCCNC](https://jlccnc.com/)
