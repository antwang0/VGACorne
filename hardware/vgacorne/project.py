"""KiCad project files (.kicad_pro, library tables) for each board."""

from __future__ import annotations

import json
from pathlib import Path

from .customlib import write_lib_tables

# JLCPCB standard 2-layer capabilities with some margin.
RULES = {
    "min_clearance": 0.15,
    "min_connection": 0.15,
    "min_copper_edge_clearance": 0.3,
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.25,
    "min_through_hole_diameter": 0.3,
    "min_track_width": 0.15,
    "min_via_annular_width": 0.13,
    "min_via_diameter": 0.5,
    "min_silk_clearance": 0.0,
    "min_text_height": 0.8,
    "min_text_thickness": 0.08,
    "solder_mask_to_copper_clearance": 0.0,
}


def _netclass(name, track, clearance=0.2, via=0.6, drill=0.3, dp_w=0.2, dp_gap=0.2, prio=0):
    return {
        "name": name, "clearance": clearance, "track_width": track, "via_diameter": via,
        "via_drill": drill, "diff_pair_width": dp_w, "diff_pair_gap": dp_gap,
        "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
        "bus_width": 12, "wire_width": 6, "line_style": 0, "priority": prio,
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
    }


NETCLASSES = [
    _netclass("Default", 0.2, prio=2147483647),
    # 0.3 mm still carries the board's <0.5 A and fits the 0.5 mm-pitch pads
    # (USB-C VBUS, the trackpad FFC's supply) that 0.4 mm tracks can't enter.
    _netclass("Power", 0.3, prio=0),
    # USB D+/D-: 0.4 mm tracks 0.15 mm apart, with the ground pour 0.25 mm away on
    # the same layer and the other layer poured, come out at ~97 ohm differential
    # bare (a few ohm less under solder mask) on the 1.6 mm main PCB, and the same
    # on a 1.0 mm board: the coupling and the pour set it, not the far plane (2D
    # field-solver estimate). USB 2.0 wants 90 ohm +/-15%. 0.2 mm tracks would be ~120.
    _netclass("USB", 0.4, clearance=0.15, dp_w=0.4, dp_gap=0.15, prio=1),
    _netclass("Analog", 0.2, clearance=0.2, prio=2),
]
# The MCU modules: 1.0 mm 4-layer, GND plane on In1 ~0.1 mm under the outer
# layers (JLC's 3313 prepreg, er ~4.05). Tracks fan out of the LQFP-64's 0.3 mm
# pads at 0.5 mm pitch, so 0.15 mm clearance (JLC's standard 6 mil). USB at
# 0.2 mm tracks 0.15 mm apart is ~91 ohm differential over the plane (a few ohm
# less under solder mask; 2D field-solver estimate).
MODULE_NETCLASSES = [
    _netclass("Default", 0.2, clearance=0.15, prio=2147483647),
    _netclass("Power", 0.3, clearance=0.15, prio=0),
    _netclass("USB", 0.2, clearance=0.15, dp_w=0.2, dp_gap=0.15, prio=1),
    _netclass("Analog", 0.2, clearance=0.15, prio=2),
]
# Net names from local labels carry the sheet path ("/HE_C0R0"); power symbols don't ("GND").
PATTERNS = [
    ("Power", "GND"), ("Power", "+*"), ("Power", "VBUS"), ("Power", "/+5V_LINK"), ("Power", "/LINK_5V_F"),
    ("USB", "/USB_*"),
    ("Analog", "/HE_*"), ("Analog", "/ADC_*"), ("Analog", "/MUX_[ABC]"), ("Analog", "/OPA_*"),
    ("Analog", "/LINK_[ABC]"), ("Analog", "/ENC"),
]


# Custom DRC rules for the modules: route.py gives every ground and supply pad
# its own via to the inner planes, so a pad needs no thermal spokes into an
# outer pour.
MODULE_RULES = """(version 1)
(rule "module: pads reach the planes by via"
   (condition "A.Type == 'Pad'")
   (constraint min_resolved_spokes (min 0)))
"""


def write_project(project_dir: Path, name: str) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    if "module" in name:
        (project_dir / f"{name}.kicad_dru").write_text(MODULE_RULES)
    pro = {
        "board": {"design_settings": {"defaults": {}, "rules": RULES,
                                      "meta": {"version": 2}}},
        "meta": {"filename": f"{name}.kicad_pro", "version": 3},
        "net_settings": {
            "classes": MODULE_NETCLASSES if "module" in name else NETCLASSES,
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": c, "pattern": p} for c, p in PATTERNS],
        },
        "schematic": {"meta": {"version": 1}},
        "text_variables": {},
    }
    (project_dir / f"{name}.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n")
    write_lib_tables(project_dir)
