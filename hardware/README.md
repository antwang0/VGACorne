# Hardware generator

`generate.py` builds the KiCad projects, firmware config and mechanical files
from one Python description of the keyboard.

```sh
# once: a venv that can see KiCad's pcbnew module
uv venv --system-site-packages --python /usr/bin/python3 ../.venv
uv pip install --python ../.venv/bin/python shapely ezdxf pydantic

../.venv/bin/python generate.py              # every step
../.venv/bin/python generate.py check        # verify only
```

Needs KiCad 10 (`kicad-cli` and the `pcbnew` Python module) and its stock
symbol/footprint libraries (override the paths with `KICAD10_SYMBOL_DIR` /
`KICAD10_FOOTPRINT_DIR`).

## Steps

| Step | Writes | Overwrites your edits? |
|---|---|---|
| `lib` | `lib/vgacorne.kicad_sym`, `lib/vgacorne.pretty/` | yes (generated library) |
| `schematics` | `kicad/*/…kicad_sch`, project files | **only with `--force`** |
| `pcbs` | `kicad/*/…kicad_pcb` | **only with `--force`**, and never a routed board |
| `firmware` | libhmk `keyboard.json` per module; QMK `keyboard.json`, `he_wiring.h`, `rules.mk` | yes: traced from the schematics |
| `mechanical` | `mechanical/*.dxf` (+ `.svg` previews), FR4 plate boards | yes |
| `bom` | `bom/*.csv` from the schematics | yes |
| `check` | nothing | — |

**Workflow:** the schematics and PCBs start as generated scaffolding. Once you
edit them in KiCad (routing, moving parts, swapping mux channels), KiCad is the
source of truth. Use KiCad's *Update PCB from Schematic*, since footprints are
linked to symbols by UUID. Firmware and BOM outputs keep following your edits
because they're read back from the schematics.

`check` runs:
- ERC on each schematic
- DRC with schematic parity on each PCB (unrouted nets and silkscreen
  warnings are tolerated)
- a comparison of each netlist against `circuits.py` (informational once you've
  edited)
- a check that each MCU module's castellated pads land on the main board's J4 pads pin-for-pin
- a check that each generated firmware file is current, and the QMK matrix host
  test (needs a host C compiler)

Set `LIBHMK=/path/to/libhmk` to also validate against libhmk's schema.

## Routing

`route.py` autoroutes a board with [Freerouting](https://github.com/freerouting/freerouting).
It needs Java 25 or newer and the Freerouting 2.4 jar (`FREEROUTING_JAR`, default
`~/.kicad-mcp/freerouting.jar`).

```sh
cp -r kicad/link /tmp/link && ../.venv/bin/python route.py /tmp/link/vgacorne-link.kicad_pcb /tmp/link/vgacorne-link.kicad_pcb
```

**2-layer boards:**
1. It routes the signals first, with the ground pours standing in as planes.
2. It locks those tracks, takes the pours off and routes GND as tracks, so no
   ground pad depends on a pour the signals have cut up.
3. If that leaves anything unconnected, it also tries every net in one run and
   keeps whichever connects more.

**Boards with inner planes (the 4-layer MCU modules):**
1. Every outer-layer SMD pad on a plane net gets its own via on a short track,
   placed clear of other nets' copper, or else a track to the nearest via of
   its net. Freerouting doesn't reliably connect pads to inner planes itself.
2. One run then routes the signals, with no tracks on the planes.

**Either way:** it puts the pours back and adds ground stitching vias
wherever both outer layers are poured, and into every pour island.

**Castellated edge pads:** the routing area grows past the board edge so
their outer halves count, and keepouts stop any track leaving the board.

Route on a copy, then copy the board back and run `generate.py check`. The
VGA daughterboard and both MCU modules are routed this way.

Once a board has tracks, `generate.py --force pcbs` leaves it alone. Take
circuit changes into KiCad with *Update PCB from Schematic*, or delete the
board file to regenerate it unrouted.

## Renders

`render.py` builds the assembled keyboard in Blender (the `bpy` module) from
`geometry.py` and `mechanical.py`, then renders `docs/img/render-{hero,top,port}.jpg`
with Cycles, on the GPU if one is available. bpy needs Python 3.13, so it gets its own venv:

```sh
uv venv --python 3.13 ../.venv-render
uv pip install --python ../.venv-render/bin/python bpy shapely ezdxf

../.venv-render/bin/python render.py                             # all views, 256 samples
../.venv-render/bin/python render.py hero --samples 32 --scale 0.5   # quick look
../.venv-render/bin/python render.py --blend /tmp/vgacorne.blend     # also save the scene
```

Colours, keycap sculpt, the gap between the halves and the splay angle are
constants at the top of the script.

## Where things live

| Module | Contents |
|---|---|
| `vgacorne/geometry.py` | Corne v4 key positions, `MAIN_SIDE`, the left half's mouse column and rotary encoder, PCB outline, VGA bay, USB ear, MCU module and pad tongue, standoffs, anchors |
| `vgacorne/trackpad.py` | the optional trackpad: `PADS` (Azoteq TPS65, Cirque TM040040) and `MODEL` |
| `vgacorne/circuits.py` | the five circuits (main + optional trackpad, satellite + rotary encoder, link, two MCU modules), `SENSOR`, mux channels, the VGA, link and module pinouts |
| `vgacorne/schematic.py` | label-based `.kicad_sch` writer (library symbols embedded and flattened) |
| `vgacorne/pcb.py` | pcbnew placement: per-key clusters, muxes, MCU, connectors, collision-aware auto-placer |
| `vgacorne/firmware.py` | netlist tracer → libhmk `keyboard.json`, default keymap |
| `vgacorne/qmk.py` | QMK `keyboard.json` layout, `he_wiring.h` (incl. the rotary encoder's levels) and `rules.mk` from the same trace |
| `vgacorne/mechanical.py` | stack-up, plate, gasket tabs, foams, case plan |
| `vgacorne/customlib.py` | AT32F405RCT7 symbol; HE switch, M2 standoff and pigtail-pad footprints |
| `vgacorne/checks.py` | the `check` step |
| `route.py` | Freerouting autorouting: plane fan-out, signals, ground, stitching vias |

Common changes:
- **Different sensor:** edit `SENSOR` in `circuits.py`, then regenerate
  schematics/PCBs (`--force`) and firmware. Options: `docs/sensors.md`.
- **Move a key or standoff:** edit `geometry.py`, then regenerate the PCBs and
  mechanical files.
