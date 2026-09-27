"""Plate, foam and case-planning outputs derived from :mod:`geometry`.

Everything is 2D (DXF, millimetres, Y up as CAD tools expect) plus a KiCad
board for an FR4 plate. The Z stack-up the case must honour lives in
``STACK`` and is documented in docs/mechanical.md.

Mounting concept: HE switches are held only by the plate, so the plate and
PCB are bolted into one rigid sandwich with M2 standoffs; that sandwich is
then gasket-mounted (poron or silicone) between an aluminium top frame and
bottom tray. The VGA daughterboard is held against the case wall by the DE-15's
screwlocks, so cable forces never reach the floating sandwich.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import ezdxf
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from . import geometry as geo

HARDWARE = Path(__file__).resolve().parent.parent
OUT = HARDWARE / "mechanical"


@dataclass(frozen=True)
class Stack:
    """Z stack-up in mm, measured up from the outside of the case floor."""
    floor: float = 3.0            # bottom tray floor thickness
    case_foam: float = 3.5        # poron 3.5 mm, or a 3-4 mm silicone pad
    foam_gap: float = 0.5         # air between foam and PCB components
    component_max: float = 3.3    # tallest B-side part (USB-C receptacle)
    pcb: float = 1.6
    plate_gap: float = 3.5        # MX standard: plate top is 5.0 mm above PCB top
    plate: float = 1.5
    gasket: float = 3.0           # each gasket strip, uncompressed (above and below the tab)
    frame_above_plate: float = 5.0  # also sets the 13.6 mm interior needed by the DE-15 flange
    roof: float = 1.5               # top-frame thickness over the inner column (module + VGA pocket)

    @property
    def pcb_bottom(self) -> float:
        return self.floor + max(self.case_foam + self.foam_gap, self.component_max + 0.5)

    @property
    def plate_bottom(self) -> float:
        return self.pcb_bottom + self.pcb + self.plate_gap

    @property
    def plate_top(self) -> float:
        return self.plate_bottom + self.plate

    @property
    def case_height(self) -> float:
        return self.plate_top + self.frame_above_plate

    # MCU module: 1.27 mm SMD socket (4.4 mm) + header base (1.0 mm), 1.0 mm module
    # PCB, LQFP-64 (1.6 mm) on its top side.
    module_stack: float = 5.4
    module_pcb: float = 1.0
    module_top_parts: float = 1.6

    @property
    def module_top(self) -> float:
        return self.pcb_bottom + self.pcb + self.module_stack + self.module_pcb + self.module_top_parts

    @property
    def module_clearance(self) -> float:
        """Gap between the module's tallest part and the case roof over the inner column."""
        return self.case_height - self.roof - self.module_top

    @property
    def pocket_interior(self) -> float:
        """Clear height at the VGA daughterboard: must exceed the 12.55 mm DE-15 flange."""
        return self.case_height - self.roof - self.floor


STACK = Stack()

SWITCH_CUTOUT = 14.0
SWITCH_CUTOUT_R = 0.3
STANDOFF_HOLE = 2.2
PLATE_FOAM_SWITCH = 15.0
TAB_W, TAB_L, TAB_R = 10.0, 4.5, 1.0
WALL_CLEARANCE = 0.75  # plate edge to inner wall
WALL = 5.0             # side wall thickness
CASE_R = 3.0

# Gasket tab anchors (Corne frame): a point near the edge; the tab is placed at
# the closest outline point, pointing outward.
_TAB_ANCHORS = [
    (-140.0, 11.9), (-119.0, -19.0), (-71.4, -26.0), (-33.3, -21.0),
    (-119.0, 43.0), (-61.9, 59.0), (-41.0, 61.5), (-9.0, 56.5),
]


def _rounded_square(k: geo.Key, size: float, r: float) -> Polygon:
    return k.square(size - 2 * r).buffer(r, join_style="round") if r else k.square(size)


def plate_outline(side: str) -> Polygon:
    return geo.plate_outline(side)


def gasket_tabs(side: str) -> list[Polygon]:
    base = plate_outline("left")
    ring = base.exterior
    tabs = []
    for ax, ay in _TAB_ANCHORS:
        p = Point(*geo.corne(ax, ay))
        on = nearest_points(ring, p)[0]
        d = ring.project(on)
        a, b = ring.interpolate(max(d - 1, 0)), ring.interpolate(d + 1)
        tx, ty = b.x - a.x, b.y - a.y
        n = math.hypot(tx, ty)
        nx, ny = ty / n, -tx / n
        if base.contains(Point(on.x + nx, on.y + ny)):
            nx, ny = -nx, -ny
        ang = math.degrees(math.atan2(ny, nx))
        tab = box(-1.0, -TAB_W / 2, TAB_L, TAB_W / 2)
        tab = affinity.rotate(tab, ang, origin=(0, 0))
        tab = affinity.translate(tab, on.x, on.y)
        tabs.append(tab.buffer(-TAB_R).buffer(TAB_R))
    return [geo.mirror(t) for t in tabs] if side == "right" else tabs


def plate(side: str) -> tuple[Polygon, list[Polygon], list[Polygon]]:
    """(outline incl. gasket tabs, switch cutouts, standoff holes)."""
    outline = unary_union([plate_outline(side), *gasket_tabs(side)])
    cutouts = [_rounded_square(k, SWITCH_CUTOUT, SWITCH_CUTOUT_R) for k in geo.keys_for(side)]
    holes = [Point(x, y).buffer(STANDOFF_HOLE / 2, 32) for x, y in geo.standoffs(side)]
    return outline, cutouts, holes


def plate_foam(side: str) -> tuple[Polygon, list[Polygon]]:
    outline = plate_outline(side).buffer(-0.5)
    cut = [k.square(PLATE_FOAM_SWITCH) for k in geo.keys_for(side)]
    cut += [Point(x, y).buffer(2.75, 32) for x, y in geo.standoffs(side)]
    return outline, cut


def case_foam(side: str, board_pcb: Path | None) -> tuple[Polygon, list[Polygon]]:
    """Case foam under the PCB with reliefs for tall bottom-side parts."""
    outline = geo.pcb_outline(side).buffer(-0.5)
    cut = [Point(x, y).buffer(3.0, 32) for x, y in geo.standoffs(side)]  # screw heads
    if board_pcb and board_pcb.exists():
        cut += _tall_parts(board_pcb)
    return outline, cut


# Bottom-side parts taller than the ~1.1 mm sensors get a relief in the case foam.
TALL_PARTS = {"J1", "J2", "J3", "SW22", "SW23"}


def _tall_parts(pcb_path: Path) -> list[Polygon]:
    import pcbnew  # only needed here

    board = pcbnew.LoadBoard(str(pcb_path))
    out = []
    for fp in board.GetFootprints():
        if fp.GetReference() not in TALL_PARTS or fp.GetLayer() != pcbnew.B_Cu:
            continue
        fp.BuildCourtyardCaches()
        bb = fp.GetCourtyard(pcbnew.B_CrtYd).BBox()
        out.append(box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                       pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())).buffer(0.5))
    return out


# ---------------------------------------------------------------------------
# Case planning
# ---------------------------------------------------------------------------

DE15_CUTOUT = (19.2, 11.1)    # typical D-shaped panel cutout, shell size E (check the datasheet)
DB_WIDTH = 33.0                # pcb.LINK_W
DB_DEPTH = 13.0                # flange + 4.3 mm body + 1.6 mm PCB + pads + wire bend room


def daughterboard_footprint(side: str) -> Polygon:
    """Plan-view envelope of the vertical daughterboard against the inner wall."""
    pocket = geo.pocket_left()
    minx, miny, maxx, maxy = pocket.bounds
    cy = (miny + maxy) / 2
    wall = maxx + WALL_CLEARANCE
    db = box(wall - DB_DEPTH, cy - DB_WIDTH / 2, wall, cy + DB_WIDTH / 2)
    return geo.mirror(db) if side == "right" else db


def access_holes(pcb_path: Path) -> list[Polygon]:
    """Floor holes under the BOOT/RESET buttons (main half only)."""
    import pcbnew

    if not pcb_path.exists():
        return []
    board = pcbnew.LoadBoard(str(pcb_path))
    return [Point(pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)).buffer(1.5, 24)
            for fp in board.GetFootprints() if fp.GetReference() in ("SW22", "SW23")]


def case(side: str) -> dict[str, list[Polygon]]:
    outline, _, _ = plate(side)
    inner_wall = geo.pcb_outline(side).buffer(WALL_CLEARANCE, join_style="round")
    # The daughterboard pocket is part of the case interior.
    pocket = geo.pocket_left() if side == "left" else geo.mirror(geo.pocket_left())
    inner_wall = unary_union([inner_wall, pocket.buffer(WALL_CLEARANCE)]).buffer(1.0).buffer(-1.0)
    gasket_pockets = [t.buffer(0.5, join_style="mitre") for t in gasket_tabs(side)]
    outer = unary_union([inner_wall, *gasket_pockets]).buffer(WALL, join_style="round")
    outer = outer.buffer(-CASE_R, join_style="round").buffer(CASE_R, join_style="round")
    db = daughterboard_footprint(side)
    # Ports: DE-15 shell opening in the inner wall, USB-C opening in the back wall (main only).
    minx, miny, maxx, maxy = db.bounds
    cy = (miny + maxy) / 2
    wall_x = maxx if side == "left" else minx
    sgn = 1 if side == "left" else -1
    # D-shaped shell opening (bounding box) and 4-40 screwlock holes, both through the wall.
    x0, x1 = sorted((wall_x, wall_x + sgn * WALL))
    vga = box(x0, cy - DE15_CUTOUT[0] / 2, x1, cy + DE15_CUTOUT[0] / 2)
    jackscrews = [box(x0, y - 1.6, x1, y + 1.6) for y in (cy - 12.5, cy + 12.5)]
    ports = [vga]
    if side == "left":
        ux, uy = geo.anchor("USB", "left")
        ports.append(box(ux - 5.0, uy - WALL - 2, ux + 5.0, uy + 1))
    # Thin the wall to 1.6 mm around the port so the plug mates fully and the screwlocks bite.
    t0, t1 = sorted((wall_x + sgn * 1.6, wall_x + sgn * (WALL + 1)))
    thin = box(t0, cy - 17.5, t1, cy + 17.5)
    layers = {"OUTER_WALL": [outer], "INNER_WALL": [inner_wall], "GASKET_POCKETS": gasket_pockets,
              "PLATE": [outline], "DAUGHTERBOARD": [db], "MCU_MODULE": [geo.module_rect(side)], "PORTS": ports,
              "JACKSCREWS": jackscrews, "WALL_RELIEF": [thin]}
    if side == "left":
        layers["FLOOR_ACCESS"] = access_holes(HARDWARE / "kicad" / "main" / "vgacorne-main.kicad_pcb")
    return layers


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _flip(poly):
    """Board coordinates are Y-down; DXF/CAD is Y-up."""
    return affinity.scale(poly, 1, -1, origin=(0, 0))


def _add(msp, geom, layer):
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for g in geoms:
        g = _flip(g)
        for ring in [g.exterior, *g.interiors]:
            msp.add_lwpolyline(list(ring.coords), close=True, dxfattribs={"layer": layer})


_SVG_COLOURS = ["#1f2937", "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#db2777", "#0891b2"]


def _svg(path: Path, layers: dict[str, list[Polygon]]) -> Path:
    """Quick-look preview of the same geometry (Y-down, like the PCB)."""
    allg = unary_union([g for gs in layers.values() for g in gs])
    minx, miny, maxx, maxy = allg.bounds
    pad = 4
    body = []
    for i, (name, geoms) in enumerate(layers.items()):
        colour = _SVG_COLOURS[i % len(_SVG_COLOURS)]
        for g in geoms:
            for poly in (g.geoms if isinstance(g, MultiPolygon) else [g]):
                for ring in [poly.exterior, *poly.interiors]:
                    pts = " ".join(f"{x - minx + pad:.3f},{y - miny + pad:.3f}" for x, y in ring.coords)
                    body.append(f'<polygon points="{pts}" fill="none" stroke="{colour}" stroke-width="0.25"/>')
        body.append(f'<text x="{pad}" y="{maxy - miny + 2 * pad + 4 * i + 3:.1f}" font-size="3" '
                    f'fill="{colour}" font-family="sans-serif">{name}</text>')
    w, h = maxx - minx + 2 * pad, maxy - miny + 2 * pad + 4 * len(layers) + 2
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * 4:.0f}" height="{h * 4:.0f}" '
                    f'viewBox="0 0 {w:.2f} {h:.2f}"><rect width="100%" height="100%" fill="white"/>'
                    + "".join(body) + "</svg>\n")
    return path


def _dxf(path: Path, layers: dict[str, list[Polygon]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _svg(path.with_suffix(".svg"), layers)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for i, (name, geoms) in enumerate(layers.items()):
        doc.layers.add(name, color=(i % 7) + 1)
        for g in geoms:
            _add(msp, g, name)
    doc.saveas(path)
    return path


def write_plate_pcb(side: str) -> Path:
    """FR4 plate as a KiCad board (Edge.Cuts only) -- order it with the PCBs."""
    import pcbnew

    outline, cutouts, holes = plate(side)
    path = OUT / f"plate-{side}" / f"vgacorne-plate-{side}.kicad_pcb"
    path.parent.mkdir(parents=True, exist_ok=True)
    board = pcbnew.NewBoard(str(path))
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.5))
    for ring in [outline.exterior, *[c.exterior for c in cutouts], *[h.exterior for h in holes]]:
        pts = list(ring.coords)
        for a, b in zip(pts, pts[1:]):
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            board.Add(s)
    board.Save(str(path))
    return path


def write_all() -> list[Path]:
    out = []
    kicad = HARDWARE / "kicad"
    for side, board in (("left", "main"), ("right", "satellite")):
        o, cut, holes = plate(side)
        out.append(_dxf(OUT / f"plate-{side}.dxf", {"OUTLINE": [o], "SWITCHES": cut, "STANDOFFS": holes}))
        out.append(_dxf(OUT / f"pcb-outline-{side}.dxf", {"OUTLINE": [geo.pcb_outline(side)]}))
        fo, fcut = plate_foam(side)
        out.append(_dxf(OUT / f"foam-plate-{side}.dxf", {"OUTLINE": [fo], "CUTOUTS": fcut}))
        co, ccut = case_foam(side, kicad / board / f"vgacorne-{board}.kicad_pcb")
        out.append(_dxf(OUT / f"foam-case-{side}.dxf", {"OUTLINE": [co], "CUTOUTS": ccut}))
        out.append(_dxf(OUT / f"case-plan-{side}.dxf", case(side)))
        out.append(write_plate_pcb(side))
    return out
