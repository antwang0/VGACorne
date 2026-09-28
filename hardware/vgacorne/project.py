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
    _netclass("Power", 0.4, prio=0),
    _netclass("USB", 0.2, clearance=0.15, dp_w=0.2, dp_gap=0.15, prio=1),
    _netclass("Analog", 0.2, clearance=0.2, prio=2),
]
# Net names from local labels carry the sheet path ("/HE_C0R0"); power symbols don't ("GND").
PATTERNS = [
    ("Power", "GND"), ("Power", "+*"), ("Power", "VBUS"), ("Power", "/+5V_LINK"), ("Power", "/LINK_5V_F"),
    ("USB", "/USB_*"),
    ("Analog", "/HE_*"), ("Analog", "/ADC_*"), ("Analog", "/MUX_[ABC]"), ("Analog", "/OPA_*"),
    ("Analog", "/LINK_[ABC]"), ("Analog", "/WHEEL"),
]


def write_project(project_dir: Path, name: str) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    pro = {
        "board": {"design_settings": {"defaults": {}, "rules": RULES,
                                      "meta": {"version": 2}}},
        "meta": {"filename": f"{name}.kicad_pro", "version": 3},
        "net_settings": {
            "classes": NETCLASSES,
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
