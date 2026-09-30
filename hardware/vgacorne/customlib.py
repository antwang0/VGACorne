"""Generate the project-local KiCad library (hardware/lib).

* ``vgacorne.kicad_sym`` -- AT32F405RCT7 (LQFP-64). Pin numbering follows the
  Artery AT32F402/405 datasheet and matches the AT32F405RCT7 used on the
  fabricated HE60 (peppapighs/HE60) reference board.
* ``vgacorne.pretty`` -- Hall-effect MX switch footprints: two 1.75 mm NPTH
  side pegs, no centre post (the magnet lives there) and no pins. The sensor is
  a separate SOT-23 on B.Cu directly under the switch centre. Also the MCU
  module's castellated edge and the matching landing pads on the main PCB, and
  the VGA socket's footprint adapted to the Amphenol part.
"""

from __future__ import annotations

import itertools
import math
import os
import re
import uuid
from pathlib import Path

from .sexpr import S, Sym, dumps

LIB_DIR = Path(__file__).resolve().parent.parent / "lib"

# (number, name, electrical type)
AT32F405RCT7_PINS = [
    (1, "VDD", "power_in"), (2, "PC13", "bidirectional"), (3, "PC14/LEXT_IN", "bidirectional"),
    (4, "PC15/LEXT_OUT", "bidirectional"), (5, "PF0/HEXT_IN", "passive"),
    (6, "PF1/HEXT_OUT", "passive"), (7, "NRST", "bidirectional"), (8, "PC0", "bidirectional"),
    (9, "PC1", "bidirectional"), (10, "PC2", "bidirectional"), (11, "PC3", "bidirectional"),
    (12, "VSSA", "power_in"), (13, "VDDA", "power_in"), (14, "PA0", "bidirectional"),
    (15, "PA1", "bidirectional"), (16, "PA2", "bidirectional"), (17, "PA3", "bidirectional"),
    (18, "PF4", "bidirectional"), (19, "PF5", "bidirectional"), (20, "PA4", "bidirectional"),
    (21, "PA5", "bidirectional"), (22, "PA6", "bidirectional"), (23, "PA7", "bidirectional"),
    (24, "PC4", "bidirectional"), (25, "PC5", "bidirectional"), (26, "PB0", "bidirectional"),
    (27, "PB1", "bidirectional"), (28, "PB2", "bidirectional"), (29, "PB10", "bidirectional"),
    (30, "PB12", "bidirectional"), (31, "VSS", "power_in"), (32, "PB13", "bidirectional"),
    (33, "OTGHS1_R", "passive"), (34, "OTGHS1_D-", "bidirectional"),
    (35, "OTGHS1_D+", "bidirectional"), (36, "VDD", "power_in"), (37, "PC6", "bidirectional"),
    (38, "PC7", "bidirectional"), (39, "PC8", "bidirectional"), (40, "PC9", "bidirectional"),
    (41, "PA8", "bidirectional"), (42, "PA9", "bidirectional"), (43, "PA10", "bidirectional"),
    (44, "PA11", "bidirectional"), (45, "PA12", "bidirectional"),
    (46, "PA13/SWDIO", "bidirectional"), (47, "PF6", "bidirectional"),
    (48, "PF7", "bidirectional"), (49, "PA14/SWCLK", "bidirectional"),
    (50, "PA15", "bidirectional"), (51, "PC10", "bidirectional"), (52, "PC11", "bidirectional"),
    (53, "PC12", "bidirectional"), (54, "PD2", "bidirectional"), (55, "PB3/SWO", "bidirectional"),
    (56, "PB4", "bidirectional"), (57, "PB5", "bidirectional"), (58, "PB6", "bidirectional"),
    (59, "PB7", "bidirectional"), (60, "PF11/BOOT0", "input"), (61, "PB8", "bidirectional"),
    (62, "PB9", "bidirectional"), (63, "VSS", "power_in"), (64, "VDD", "power_in"),
]

# Left side: supplies, clocks, reset/boot, USB, then ports C/D/F.
_LEFT = [1, 36, 64, 13, None, 31, 63, 12, None, 7, 60, None, 5, 6, 3, 4, None, 33, 34, 35, None,
         8, 9, 10, 11, 24, 25, 37, 38, 39, 40, 51, 52, 53, 2, None, 54, 18, 19, 47, 48]
_RIGHT = [14, 15, 16, 17, 20, 21, 22, 23, 41, 42, 43, 44, 45, 46, 49, 50, None,
          26, 27, 28, 55, 56, 57, 58, 59, 61, 62, 29, 30, 32]

FONT = S("effects", S("font", S("size", 1.27, 1.27)))
FONT_HIDDEN = S("effects", S("font", S("size", 1.27, 1.27)), S("hide", Sym("yes")))


def _prop(name, value, x, y, hidden=False):
    return S("property", name, value, S("at", x, y, 0), FONT_HIDDEN if hidden else FONT)


def at32_symbol() -> list:
    pins = {n: (name, et) for n, name, et in AT32F405RCT7_PINS}
    rows = max(len(_LEFT), len(_RIGHT))
    half_w = 17.78
    top = (rows - 1) * 2.54 / 2
    top = round(top / 2.54) * 2.54
    body = []
    for side, order, x, ang in (("L", _LEFT, -half_w - 2.54, 0), ("R", _RIGHT, half_w + 2.54, 180)):
        for i, n in enumerate(order):
            if n is None:
                continue
            name, et = pins[n]
            y = top - i * 2.54
            body.append(S("pin", Sym(et), Sym("line"), S("at", x, y, ang), S("length", 2.54),
                          S("name", name, FONT), S("number", str(n), FONT)))
    used = {n for n in _LEFT + _RIGHT if n}
    assert used == set(pins), f"unplaced pins: {set(pins) - used}"
    bottom = top - (rows - 1) * 2.54 - 2.54
    rect = S("rectangle", S("start", -half_w, top + 2.54), S("end", half_w, bottom),
             S("stroke", S("width", 0.254), S("type", Sym("default"))),
             S("fill", S("type", Sym("background"))))
    return S("symbol", "AT32F405RCT7",
             S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")), S("on_board", Sym("yes")),
             _prop("Reference", "U", -half_w, top + 3.81),
             _prop("Value", "AT32F405RCT7", half_w - 12.7, top + 3.81),
             _prop("Footprint", "Package_QFP:LQFP-64_10x10mm_P0.5mm", 0, bottom - 2.54, True),
             _prop("Datasheet", "https://www.arterychip.com/en/product/AT32F405.jsp", 0, bottom - 5.08, True),
             _prop("Description", "Artery AT32F405 Cortex-M4F MCU, 256 KB flash, USB HS with internal PHY, LQFP-64",
                   0, 0, True),
             _prop("ki_fp_filters", "LQFP*10x10mm*P0.5mm*", 0, 0, True),
             S("symbol", "AT32F405RCT7_0_1", rect),
             S("symbol", "AT32F405RCT7_1_1", *body),
             S("embedded_fonts", Sym("no")))


def write_symbol_lib() -> Path:
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    lib = S("kicad_symbol_lib", S("version", 20241209), S("generator", "vgacorne"),
            S("generator_version", "1.0"), at32_symbol())
    path = LIB_DIR / "vgacorne.kicad_sym"
    path.write_text(dumps(lib) + "\n")
    return path


# ---------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------

_uid_counter = itertools.count()


def _uid() -> str:
    # Deterministic so regenerating the library produces no diff.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vgacorne-fp-{next(_uid_counter)}"))


def _line(x1, y1, x2, y2, layer, width=0.12):
    return S("fp_line", S("start", x1, y1), S("end", x2, y2),
             S("stroke", S("width", width), S("type", Sym("solid"))), S("layer", layer),
             S("uuid", _uid()))


def _rect(x1, y1, x2, y2, layer, width=0.05):
    return S("fp_rect", S("start", x1, y1), S("end", x2, y2),
             S("stroke", S("width", width), S("type", Sym("solid"))), S("fill", Sym("no")),
             S("layer", layer), S("uuid", _uid()))


def _text_prop(name, value, x, y, layer, hidden=False):
    eff = [S("font", S("size", 1, 1), S("thickness", 0.15))]
    node = S("property", name, value, S("at", x, y, 0), S("layer", layer))
    if hidden:
        node.append(S("hide", Sym("yes")))
    node += [S("uuid", _uid()), S("effects", *eff)]
    return node


def switch_footprint(width_u: float) -> tuple[str, list]:
    name = "SW_HE_MX_1u" if width_u == 1 else f"SW_HE_MX_{width_u:g}u"
    kw = width_u * 19.05 / 2
    items = [
        S("footprint", name, S("version", 20241229), S("generator", "vgacorne"),
          S("generator_version", "1.0"), S("layer", "F.Cu"),
          S("descr", f"Hall-effect MX-style switch, {width_u:g}u keycap. Two 1.75 mm NPTH pegs at +/-5.08 mm, "
                     "no centre post. Linear Hall sensor goes on B.Cu at (0,0)."),
          S("tags", "keyboard switch hall effect magnetic HE MX"),
          _text_prop("Reference", "REF**", 0, -8.5, "F.SilkS"),
          _text_prop("Value", name, 0, 8.5, "F.Fab"),
          _text_prop("Footprint", "", 0, 0, "F.Fab", hidden=True),
          _text_prop("Datasheet", "", 0, 0, "F.Fab", hidden=True),
          _text_prop("Description", "", 0, 0, "F.Fab", hidden=True),
          S("attr", Sym("through_hole"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")))
    ]
    fp = items[0]
    # Switch body (14 mm plate cutout) and keycap outline.
    fp.append(_rect(-7, -7, 7, 7, "F.Fab", 0.1))
    fp.append(_rect(-kw, -9.525, kw, 9.525, "Dwgs.User", 0.1))
    fp.append(_rect(-7.25, -7.25, 7.25, 7.25, "F.CrtYd", 0.05))
    for sx in (-1, 1):
        for sy in (-1, 1):
            fp.append(_line(sx * 7, sy * 7, sx * 5, sy * 7, "F.SilkS"))
            fp.append(_line(sx * 7, sy * 7, sx * 7, sy * 5, "F.SilkS"))
    # Sensor marker on the back.
    fp.append(_line(-1.6, 0, 1.6, 0, "B.Fab", 0.1))
    fp.append(_line(0, -1.6, 0, 1.6, "B.Fab", 0.1))
    for x in (-5.08, 5.08):
        fp.append(S("pad", "", Sym("np_thru_hole"), Sym("circle"), S("at", x, 0), S("size", 1.75, 1.75),
                    S("drill", 1.75), S("layers", "*.Cu", "*.Mask"), S("uuid", _uid())))
    fp.append(S("embedded_fonts", Sym("no")))
    return name, fp


def _circle(r, layer, width=0.05):
    return S("fp_circle", S("center", 0, 0), S("end", r, 0),
             S("stroke", S("width", width), S("type", Sym("solid"))), S("fill", Sym("no")),
             S("layer", layer), S("uuid", _uid()))


def standoff_footprint() -> tuple[str, list]:
    """M2 PCB-to-plate standoff: 3.5 mm hex standoff on top, M2 screw head below.

    Courtyards are sized for the real parts (4.04 mm across corners) so the
    standoff fits in the 5.05 mm gap between two MX switch bodies.
    """
    name = "Standoff_M2"
    fp = S("footprint", name, S("version", 20241229), S("generator", "vgacorne"),
           S("generator_version", "1.0"), S("layer", "F.Cu"),
           S("descr", "M2 plate standoff: 2.2 mm NPTH, 3.5 mm hex standoff (F), M2 low-profile head (B)"),
           S("tags", "mounting standoff M2 plate"),
           _text_prop("Reference", "REF**", 0, -3, "F.Fab"),
           _text_prop("Value", name, 0, 3, "F.Fab", hidden=True),
           _text_prop("Footprint", "", 0, 0, "F.Fab", hidden=True),
           _text_prop("Datasheet", "", 0, 0, "F.Fab", hidden=True),
           _text_prop("Description", "", 0, 0, "F.Fab", hidden=True),
           S("attr", Sym("exclude_from_pos_files"), Sym("exclude_from_bom")))
    hexr = 3.5 / math.sqrt(3)
    pts = [(hexr * math.cos(math.radians(a)), hexr * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        fp.append(_line(*a, *b, "F.Fab", 0.1))
    fp.append(_circle(2.1, "F.CrtYd"))
    fp.append(_circle(2.1, "B.CrtYd"))
    fp.append(S("pad", "", Sym("np_thru_hole"), Sym("circle"), S("at", 0, 0), S("size", 2.2, 2.2),
                S("drill", 2.2), S("layers", "*.Cu", "*.Mask"), S("uuid", _uid())))
    fp.append(S("embedded_fonts", Sym("no")))
    return name, fp


def wire_pads_footprint(n: int = 10, pitch: float = 1.6) -> tuple[str, list]:
    """Row of large SMD pads for soldering a JST-SH pigtail (or loose wires)."""
    name = f"WirePads_1x{n:02d}_P{pitch:g}mm"
    w = (n - 1) * pitch
    fp = S("footprint", name, S("version", 20241229), S("generator", "vgacorne"),
           S("generator_version", "1.0"), S("layer", "F.Cu"),
           S("descr", f"{n} solder pads, {pitch} mm pitch, for a pre-crimped JST-SH pigtail"),
           S("tags", "wire solder pad pigtail"),
           _text_prop("Reference", "REF**", 0, -2.8, "F.SilkS"),
           _text_prop("Value", name, 0, 2.8, "F.Fab", hidden=True),
           _text_prop("Footprint", "", 0, 0, "F.Fab", hidden=True),
           _text_prop("Datasheet", "", 0, 0, "F.Fab", hidden=True),
           _text_prop("Description", "", 0, 0, "F.Fab", hidden=True),
           S("attr", Sym("smd")))
    fp.append(_rect(-w / 2 - 0.9, -1.2, w / 2 + 0.9, 1.2, "F.CrtYd", 0.05))
    fp.append(_line(-w / 2 - 0.9, 1.1, -w / 2 - 0.9, -1.1, "F.SilkS"))  # pin-1 side marker
    for i in range(n):
        fp.append(S("pad", str(i + 1), Sym("smd"), Sym("rect"), S("at", -w / 2 + i * pitch, 0),
                    S("size", 1.0, 1.8), S("layers", "F.Cu", "F.Paste", "F.Mask"), S("uuid", _uid())))
    fp.append(S("embedded_fonts", Sym("no")))
    return name, fp


MODULE_PITCH = 1.27
MODULE_PADS = 12        # per edge; odd pins along the top edge, even along the bottom
CASTELLATION_DRILL = 0.6


def _module_pad_x(i: int) -> float:
    return (i - (MODULE_PADS - 1) / 2) * MODULE_PITCH


def _module_pins():
    """(pin, x, edge sign): pin 1 top-left, pins 1, 3 ... 23 along the top edge, 2 ... 24 below."""
    for i in range(MODULE_PADS):
        yield str(2 * i + 1), _module_pad_x(i), -1
        yield str(2 * i + 2), _module_pad_x(i), 1


def _module_header(name: str, descr: str, attrs: list) -> list:
    return S("footprint", name, S("version", 20241229), S("generator", "vgacorne"),
             S("generator_version", "1.0"), S("layer", "F.Cu"), S("descr", descr),
             S("tags", "module castellated stamp"),
             _text_prop("Reference", "REF**", 0, 0, "F.Fab"),
             _text_prop("Value", name, 0, 1.5, "F.Fab", hidden=True),
             _text_prop("Footprint", "", 0, 0, "F.Fab", hidden=True),
             _text_prop("Datasheet", "", 0, 0, "F.Fab", hidden=True),
             _text_prop("Description", "", 0, 0, "F.Fab", hidden=True),
             S("attr", *[Sym(a) for a in attrs]))


def module_edge_footprint(w: float, h: float) -> tuple[str, list]:
    """The MCU module's own connector: 2 x 12 castellated half-holes on its top and
    bottom edges (the board edge runs through the drill centres). Pads only, no parts."""
    name = f"Module_Castellated_2x12_P1.27mm_{w:g}x{h:g}mm"
    fp = _module_header(name, f"{w:g} x {h:g} mm MCU module edge: 2 x 12 castellated pads, 1.27 mm pitch, "
                              "0.6 mm half-holes on the board edge", ["through_hole", "exclude_from_pos_files",
                                                                      "exclude_from_bom"])
    fp.append(_rect(-w / 2, -h / 2, w / 2, h / 2, "F.Fab", 0.1))
    span = _module_pad_x(MODULE_PADS - 1) + 0.75
    for sy in (-1, 1):
        fp.append(_rect(-span, sy * (h / 2 + 0.3), span, sy * (h / 2 - 1.6), "F.CrtYd", 0.05))
    for pin, x, sy in _module_pins():
        # The hole sits on the edge line; the copper (offset from the hole) reaches
        # 1.25 mm into the board.
        fp.append(S("pad", pin, Sym("thru_hole"), Sym("oval"), S("at", x, sy * h / 2),
                    S("size", 0.95, 1.8), S("drill", CASTELLATION_DRILL, S("offset", 0, -sy * 0.35)),
                    S("property", Sym("pad_prop_castellated")), S("layers", "*.Cu", "*.Mask"),
                    S("uuid", _uid())))
    fp.append(S("embedded_fonts", Sym("no")))
    return name, fp


def module_landing_footprint(w: float, h: float) -> tuple[str, list]:
    """Main-PCB pads the castellated module is soldered onto, top side. Each pad
    runs 1.2 mm out from under the module edge for the iron."""
    name = f"Module_Castellated_Landing_2x12_P1.27mm_{w:g}x{h:g}mm"
    fp = _module_header(name, f"Landing pads for the {w:g} x {h:g} mm castellated MCU module (2 x 12, "
                              "1.27 mm pitch); keep the area under the module clear on this side", ["smd"])
    fp.append(_rect(-w / 2, -h / 2, w / 2, h / 2, "F.Fab", 0.1))
    fp.append(_rect(-w / 2 - 0.3, -h / 2 - 1.5, w / 2 + 0.3, h / 2 + 1.5, "F.CrtYd", 0.05))
    for sx in (-1, 1):  # module outline sides on silk (the pad rows are the top and bottom)
        fp.append(_line(sx * (w / 2 + 0.2), -h / 2 + 0.6, sx * (w / 2 + 0.2), h / 2 - 0.6, "F.SilkS"))
    x1 = _module_pad_x(0) - 1.0
    fp.append(_line(x1, -h / 2 - 1.3, x1, -h / 2 + 0.2, "F.SilkS"))  # pin-1 marker
    for pin, x, sy in _module_pins():
        fp.append(S("pad", pin, Sym("smd"), Sym("roundrect"), S("at", x, sy * h / 2), S("size", 0.85, 2.4),
                    S("layers", "F.Cu", "F.Paste", "F.Mask"), S("roundrect_rratio", 0.25), S("uuid", _uid())))
    fp.append(S("embedded_fonts", Sym("no")))
    return name, fp


STOCK_FP = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
DSUB_STOCK = "Connector_Dsub.pretty/DSUB-15-HD_Socket_Vertical_P2.29x1.98mm_MountingHoles.kicad_mod"
DSUB_NAME = "DSUB-15-HD_Socket_Vertical_P2.29x1.98mm_Amphenol_10090929"


def dsub_amphenol_footprint() -> tuple[str, str]:
    """KiCad's vertical HD-15 socket with the holes the Amphenol FCI 10090929-S154XLF
    asks for: 1.2 mm pin holes and 3.1 mm board-lock holes. The pads stay 1.6 mm
    (a 0.2 mm ring), so a track still fits between neighbouring pins."""
    text = (STOCK_FP / DSUB_STOCK).read_text()
    head = text.split("\n", 1)
    text = f'(footprint "{DSUB_NAME}"\n' + head[1]
    text = re.sub(r'\(descr "[^"]*"\)',
                  '(descr "15-pin HD D-Sub socket (female), vertical, THT, pitch 2.29x1.98mm, 4-40 clinch '
                  'nuts with board locks 25mm apart, for Amphenol FCI 10090929-S154XLF: 1.2mm pin holes, '
                  '3.1mm board-lock holes; https://www.digikey.com/en/products/detail/amphenol-fci/10090929-S154XLF/2350302")', text)
    text, pins = re.subn(r"\(size 1\.6 1\.6\)(\s*)\(drill 1\)", r"(size 1.6 1.6)\1(drill 1.2)", text)
    text, locks = re.subn(r"\(drill 3\.2\)", "(drill 3.1)", text)
    assert (pins, locks) == (15, 2), (pins, locks)
    return DSUB_NAME, text


def write_footprints() -> Path:
    pretty = LIB_DIR / "vgacorne.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    for w in (1, 1.5):
        name, fp = switch_footprint(w)
        (pretty / f"{name}.kicad_mod").write_text(dumps(fp) + "\n")
    for make in (standoff_footprint, wire_pads_footprint):
        name, fp = make()
        (pretty / f"{name}.kicad_mod").write_text(dumps(fp) + "\n")
    from .geometry import MODULE_SIZE
    for make in (module_edge_footprint, module_landing_footprint):
        name, fp = make(*MODULE_SIZE)
        (pretty / f"{name}.kicad_mod").write_text(dumps(fp) + "\n")
    name, text = dsub_amphenol_footprint()
    (pretty / f"{name}.kicad_mod").write_text(text)
    return pretty


def write_lib_tables(project_dir: Path) -> None:
    rel = "${KIPRJMOD}/../../lib"  # projects live in hardware/kicad/<board>/
    (project_dir / "sym-lib-table").write_text(
        f'(sym_lib_table\n\t(version 7)\n\t(lib (name "vgacorne")(type "KiCad")(uri "{rel}/vgacorne.kicad_sym")'
        '(options "")(descr "VGACorne project symbols"))\n)\n')
    (project_dir / "fp-lib-table").write_text(
        f'(fp_lib_table\n\t(version 7)\n\t(lib (name "vgacorne")(type "KiCad")(uri "{rel}/vgacorne.pretty")'
        '(options "")(descr "VGACorne project footprints"))\n)\n')


def build() -> None:
    write_symbol_lib()
    write_footprints()
