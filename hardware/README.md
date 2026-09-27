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
| `pcbs` | `kicad/*/…kicad_pcb` | **only with `--force`** |
| `firmware` | libhmk `keyboard.json` per module; QMK `keyboard.json` + `he_wiring.h` | yes: traced from the schematics |
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
- a check that each MCU module's header meets the main board's socket pin-for-pin
- a check that each generated firmware file is current, and the QMK matrix host
  test (needs a host C compiler)

Set `LIBHMK=/path/to/libhmk` to also validate against libhmk's schema.

## Where things live

| Module | Contents |
|---|---|
| `vgacorne/geometry.py` | Corne v4 key positions, PCB outline, daughterboard pocket, standoffs, anchors |
| `vgacorne/circuits.py` | the five circuits (main, satellite, link, two MCU modules), `SENSOR`, the VGA, link and module pinouts |
| `vgacorne/schematic.py` | label-based `.kicad_sch` writer (library symbols embedded and flattened) |
| `vgacorne/pcb.py` | pcbnew placement: per-key clusters, muxes, MCU, connectors, collision-aware auto-placer |
| `vgacorne/firmware.py` | netlist tracer → libhmk `keyboard.json`, default keymap |
| `vgacorne/qmk.py` | QMK `keyboard.json` layout and `he_wiring.h` from the same trace |
| `vgacorne/mechanical.py` | stack-up, plate, gasket tabs, foams, case plan |
| `vgacorne/customlib.py` | AT32F405RCT7 symbol; HE switch, M2 standoff and pigtail-pad footprints |
| `vgacorne/checks.py` | the `check` step |

Common changes:
- **Different sensor:** edit `SENSOR` in `circuits.py`, then regenerate
  schematics/PCBs (`--force`) and firmware.
- **Move a key or standoff:** edit `geometry.py`, then regenerate the PCBs and
  mechanical files.
