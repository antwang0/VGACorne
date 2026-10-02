"""Plate, foam and case-planning outputs derived from :mod:`geometry`.

Everything is 2D (DXF, millimetres, Y up as CAD tools expect) plus a KiCad
board for an FR4 plate. The Z stack-up the case must honour lives in
``STACK`` and is documented in docs/mechanical.md.

Mounting concept: HE switches are held only by the plate, so the plate and
PCB are bolted into one rigid sandwich with M2 standoffs; that sandwich is
then gasket-mounted (poron or silicone) between an aluminium top frame and
bottom tray. The VGA daughterboard is held against the back wall by the DE-15's
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
from .trackpad import MODEL as PAD

HARDWARE = Path(__file__).resolve().parent.parent
OUT = HARDWARE / "mechanical"


@dataclass(frozen=True)
class Stack:
    """Z stack-up in mm, measured up from the outside of the case floor."""
    floor: float = 3.5            # bottom tray floor: room for the tripod sockets' bosses 1 mm under the PCB
    case_foam: float = 1.5        # PORON 1.57 mm: thicker leaves too little air once tolerance and adhesive add up
    foam_gap: float = 1.0         # air between the foam and the lowest parts over it (corner keys flex ~0.4 mm)
    bottom_parts: float = 1.5     # B-side parts over the foam: SOT-23-5/6 1.45 mm max, sensors 1.12 mm
    component_max: float = 3.3    # tallest B-side part (USB-C receptacle, 3.26 mm), over a foam relief
    pcb: float = 1.6
    plate_gap: float = 3.5        # MX standard: plate top is 5.0 mm above PCB top
    plate: float = 1.5
    gasket: float = 3.18          # each gasket strip, uncompressed: PORON 4701-30's standard 0.125"
    frame_above_plate: float = 5.0  # also sets the VGA bay's 14.1 mm clear height (bay_interior) for the 12.55 mm DE-15 flange
    roof: float = 1.5               # top-frame thickness over the inner column and the VGA bay

    @property
    def pcb_bottom(self) -> float:
        return self.floor + max(self.case_foam + self.foam_gap + self.bottom_parts, self.component_max + 0.5)

    @property
    def plate_bottom(self) -> float:
        return self.pcb_bottom + self.pcb + self.plate_gap

    @property
    def plate_top(self) -> float:
        return self.plate_bottom + self.plate

    @property
    def case_height(self) -> float:
        return self.plate_top + self.frame_above_plate

    # MCU module: castellated, soldered flat on the main PCB (~0.1 mm of solder),
    # 1.0 mm module PCB, LQFP-64 (1.6 mm) on its top side.
    module_stack: float = 0.1
    module_pcb: float = 1.0
    module_top_parts: float = 1.6

    @property
    def module_top(self) -> float:
        return self.pcb_bottom + self.pcb + self.module_stack + self.module_pcb + self.module_top_parts

    @property
    def module_clearance(self) -> float:
        """Gap between the module's tallest part and the bottom of the trackpad's well above it."""
        return self.case_height - PAD.board_t - PAD.parts - self.module_top

    @property
    def bay_interior(self) -> float:
        """Clear height at the VGA daughterboard: must exceed the 12.55 mm DE-15 flange."""
        return self.case_height - self.roof - self.floor


STACK = Stack()

# USB-C (main half). The receptacle's mating centreline is ~1.69 mm under the
# PCB (HRO TYPE-C-31-M-12 drawing). Fully seated, a plug's overmould stops
# 6.65 - 6.20 = 0.45 mm short of the receptacle face (USB Type-C R2.5, figs 3-1
# and 3-3), and that face is WALL_CLEARANCE + PORT_WALL - geometry.USB_OVERHANG =
# 1.89 mm inside the back face, so the overmould goes ~1.4 mm into the wall. The
# opening takes the largest overmould the spec allows plus 0.55 mm all round for
# the floating sandwich.
USB_Z = STACK.pcb_bottom - 1.69            # opening centre above the case underside
USB_OVERMOLD = (12.85, 7.0)                # spec maximum, width x height
USB_OPENING = (USB_OVERMOLD[0] + 1.1, USB_OVERMOLD[1] + 1.1)

SWITCH_CUTOUT = 14.0
SWITCH_CUTOUT_R = 0.3
STANDOFF_HOLE = 2.2
PLATE_FOAM_SWITCH = 15.0
TAB_W, TAB_L, TAB_R = 10.0, 4.5, 1.0
WALL_CLEARANCE = 0.75  # plate/PCB edge to inner wall
MIN_WALL = 3.0         # thinnest wall: behind the gasket pockets
WALL = TAB_L + 0.5 - WALL_CLEARANCE + MIN_WALL  # walls thick enough to hold the gasket pockets
PORT_WALL = 1.6        # flat back face at the connectors: plugs only mate fully through a thin panel
FLOOR_POCKET = 1.0     # extra depth in the floor under the USB-C and the encoder's pins
# Underneath, the zone round the two 1/4"-20 mounts (geometry.mounts) stays
# clear of feet, 40 mm wide, so a 38 mm Arca plate seats flat. Stick-on feet go
# near the corners (FEET).
MOUNT_ZONE_W = 40.0
FOOT_D = 10.0
FOOT_INSET = 12.0      # foot centre from the outside edge: clear of the screw counterbores
OUTSIDE_R = 25.0       # smallest concave radius on the outside: one smooth profile, big cutter
CORNER_R = 6.0         # convex corners where the flat port face meets the sides (< WALL keeps PORT_WALL)
TOOL_R = 1.5           # smallest radius inside the cavity (3 mm end mill)

# Gasket tab anchors (Corne frame): a point near the edge; the tab is placed at
# the closest outline point, pointing outward. The inner side differs: the main
# half's is on the thumb key's inner edge, below the trackpad; the satellite's on
# the mouse column, beside M1.
_TAB_ANCHORS = [
    (-140.0, 11.9), (-119.0, -19.0), (-71.4, -26.0),
    (-119.0, 43.0), (-61.9, 59.0), (-41.0, 61.5), (-9.0, 56.5),
]
_INNER_TAB_ANCHOR = {geo.MAIN_SIDE: (-3.0, 45.0), geo.SATELLITE_SIDE: (-2.0, 23.0)}


def _rounded_square(k: geo.Key, size: float, r: float) -> Polygon:
    return k.square(size - 2 * r).buffer(r, join_style="round") if r else k.square(size)


def plate_outline(side: str) -> Polygon:
    return geo.plate_outline(side)


def gasket_tabs(side: str) -> list[Polygon]:
    base = geo.frame_outline(side, with_tab=False)
    ring = base.exterior
    tabs = []
    for ax, ay in _TAB_ANCHORS + [_INNER_TAB_ANCHOR[side]]:
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


def encoder_square(side: str, size: float) -> Polygon | None:
    """Satellite: a switch-sized square round the rotary encoder's shaft (its body is 12.4 x 13.4 mm)."""
    if side != geo.SATELLITE_SIDE:
        return None
    x, y = geo.corne(*geo.ENCODER)
    if side == "right":
        x, y = geo.mirror_point(x, y)
    return box(x - size / 2, y - size / 2, x + size / 2, y + size / 2)


def plate(side: str) -> tuple[Polygon, list[Polygon], list[Polygon]]:
    """(outline incl. gasket tabs, switch cutouts, standoff holes)."""
    outline = unary_union([plate_outline(side), *gasket_tabs(side)])
    cutouts = [_rounded_square(k, SWITCH_CUTOUT, SWITCH_CUTOUT_R) for k in geo.keys_for(side)]
    enc = encoder_square(side, SWITCH_CUTOUT - 2 * SWITCH_CUTOUT_R)
    if enc is not None:
        cutouts.append(enc.buffer(SWITCH_CUTOUT_R, join_style="round"))
    holes = [Point(x, y).buffer(STANDOFF_HOLE / 2, 32) for x, y in geo.standoffs(side)]
    return outline, cutouts, holes


def encoder_pins(side: str) -> Polygon | None:
    """Satellite: the encoder's A/C/B pins, 7.5 mm to one side of the shaft, with 1.5 mm round them."""
    if side != geo.SATELLITE_SIDE:
        return None
    x, y, rot = geo.encoder_placement(side)  # pin A; C and B follow 2.5 and 5 mm along the footprint's Y
    return affinity.rotate(box(x - 1.5, y - 1.5, x + 1.5, y + 6.5), -rot, origin=(x, y))


def plate_foam(side: str) -> tuple[Polygon, list[Polygon]]:
    outline = plate_outline(side).buffer(-0.5)
    cut = [k.square(PLATE_FOAM_SWITCH) for k in geo.keys_for(side)]
    cut += [Point(x, y).buffer(2.75, 32) for x, y in geo.standoffs(side)]
    enc = encoder_square(side, PLATE_FOAM_SWITCH)
    if enc is not None:
        cut += [enc, encoder_pins(side)]
    if side == geo.MAIN_SIDE:
        # The module's outer edge runs just under column 5's plate edge.
        cut.append(geo.module_rect(side).buffer(0.5, join_style="mitre"))
    return outline, cut


def case_foam(side: str, board_pcb: Path | None) -> tuple[Polygon, list[Polygon]]:
    """Case foam under the PCB with reliefs for tall bottom-side parts and the mount bosses."""
    outline = geo.pcb_outline(side).buffer(-0.5)
    cut = [Point(x, y).buffer(3.0, 32) for x, y in geo.standoffs(side)]  # screw heads
    cut += [Point(x, y).buffer(geo.MOUNT_BOSS / 2 + 0.5, 32) for x, y in geo.mounts(side)]
    if board_pcb and board_pcb.exists():
        cut += _tall_parts(board_pcb)
    return outline, cut


# Bottom-side parts taller than STACK.bottom_parts get a relief in the case
# foam, and so do the rotary encoder's through-hole legs.
TALL_PARTS = {"J1", "J2", "J3", "SW22", "SW23", "ENC1"}


def bottom_side(pcb_path: Path) -> list[tuple[Polygon, float]]:
    """What hangs under the PCB, as (plan outline, depth below the PCB): each
    bottom-side part's courtyard (TALL_PARTS at their full height), the leads of
    through-hole parts on top (trimmed to 2 mm) and the standoff screw heads."""
    import pcbnew

    board = pcbnew.LoadBoard(str(pcb_path))
    out = []
    for fp in board.GetFootprints():
        if fp.GetLayer() == pcbnew.B_Cu:
            fp.BuildCourtyardCaches()
            cy = fp.GetCourtyard(pcbnew.B_CrtYd)
            bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
            depth = STACK.component_max if fp.GetReference() in TALL_PARTS else STACK.bottom_parts
            out.append((box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                            pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())), depth))
        else:
            for pad in fp.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    bb = pad.GetBoundingBox()
                    out.append((box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                                    pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())), 2.0))
    side = geo.MAIN_SIDE if "main" in pcb_path.name else geo.SATELLITE_SIDE
    out += [(Point(x, y).buffer(1.9, 16), 2.0) for x, y in geo.standoffs(side)]  # M2 heads
    return out


def _tall_parts(pcb_path: Path) -> list[Polygon]:
    import pcbnew  # only needed here

    board = pcbnew.LoadBoard(str(pcb_path))
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in TALL_PARTS or (fp.GetLayer() != pcbnew.B_Cu and ref != "ENC1"):
            continue
        if ref == "ENC1":  # top-side part: only its legs come through
            pads = [p.GetBoundingBox() for p in fp.Pads()]
            x0 = min(pcbnew.ToMM(b.GetX()) for b in pads)
            y0 = min(pcbnew.ToMM(b.GetY()) for b in pads)
            x1 = max(pcbnew.ToMM(b.GetRight()) for b in pads)
            y1 = max(pcbnew.ToMM(b.GetBottom()) for b in pads)
            out.append(box(x0, y0, x1, y1).buffer(1.0))
            continue
        fp.BuildCourtyardCaches()
        bb = fp.GetCourtyard(pcbnew.B_CrtYd).BBox()
        out.append(box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                       pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())).buffer(0.5))
    return out


# ---------------------------------------------------------------------------
# Case planning
# ---------------------------------------------------------------------------

# Rear-mount D cutout for shell size E (CECC 75 301-802, as in Harting's catalogue):
# the plug's shell reaches ~1 mm into the 1.6 mm wall. That wall is at the limit
# for full mating, so the 4-40 jackscrews outside it must have hexes <= 4.8 mm tall.
DE15_CUTOUT = (20.5, 11.4)
VGA_Z = STACK.floor + 7.0  # DE-15 shell centre: its 12.55 mm flange between floor and roof
DB_WIDTH = 33.0                # pcb.LINK_W
# Wall to the back of the daughterboard's wiring: the Amphenol 10090929's flange
# face is 6.1 +/-0.3 mm from the board (its drawing may mean the flange's back
# face, 0.8 mm more), then the 1.6 mm board, pin tails clipped to 1.5 mm, and
# the pigtail's pads and bend in what's left (~3-4 mm).
DB_DEPTH = 13.0


def daughterboard_footprint(side: str) -> Polygon:
    """Plan-view envelope of the vertical daughterboard, DE-15 flange against the back wall."""
    x0, y0, x1, y1 = geo.bay_left().bounds
    cx, wall = (x0 + x1) / 2, y0 - WALL_CLEARANCE
    db = box(cx - DB_WIDTH / 2, wall, cx + DB_WIDTH / 2, wall + DB_DEPTH)
    return geo.mirror(db) if side == "right" else db


def access_holes(pcb_path: Path) -> list[Polygon]:
    """Floor holes under the BOOT/RESET buttons (main half only)."""
    import pcbnew

    if not pcb_path.exists():
        return []
    board = pcbnew.LoadBoard(str(pcb_path))
    return [Point(pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)).buffer(1.5, 24)
            for fp in board.GetFootprints() if fp.GetReference() in ("SW22", "SW23")]


def floor_pockets(pcb_path: Path) -> list[Polygon]:
    """FLOOR_POCKET-deep pockets in the floor top under the parts that come closest
    to it: the USB-C shell (0.7 mm above the floor otherwise) and the encoder's
    pins and legs (trim them to ~2 mm after soldering)."""
    import pcbnew

    if not pcb_path.exists():
        return []
    out = []
    for fp in pcbnew.LoadBoard(str(pcb_path)).GetFootprints():
        ref = fp.GetReference()
        if ref == "ENC1":
            pads = [p.GetBoundingBox() for p in fp.Pads()]
            out.append(box(min(pcbnew.ToMM(b.GetX()) for b in pads), min(pcbnew.ToMM(b.GetY()) for b in pads),
                           max(pcbnew.ToMM(b.GetRight()) for b in pads),
                           max(pcbnew.ToMM(b.GetBottom()) for b in pads)).buffer(1.0))
        elif ref == "J1" and fp.GetLayer() == pcbnew.B_Cu and fp.GetFPID().GetLibItemName().wx_str().startswith("USB_C"):
            fp.BuildCourtyardCaches()
            bb = fp.GetCourtyard(pcbnew.B_CrtYd).BBox()
            out.append(box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())).buffer(0.5))
    return out


def mount_zone(side: str) -> Polygon:
    """Where a plate on the two mounts sits under the floor: no feet here."""
    return unary_union([Point(x, y).buffer(MOUNT_ZONE_W / 2, 64) for x, y in geo.mounts(side)]).convex_hull


def feet(side: str, outer: Polygon, avoid: list[Polygon]) -> list[Polygon]:
    """A stick-on foot near each corner of the outline, clear of the mount zone and ``avoid``."""
    room = outer.buffer(-FOOT_INSET).difference(unary_union([mount_zone(side).buffer(3.0)]
                                                            + [a.buffer(FOOT_D / 2 + 1.0) for a in avoid]))
    x0, y0, x1, y1 = outer.bounds
    out = []
    for corner in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        p = nearest_points(room, Point(corner))[0]
        out.append(p.buffer(FOOT_D / 2, 32))
    return out


def case(side: str, floor_access: bool = True) -> dict[str, list[Polygon]]:
    """Case-plan layers. ``floor_access`` reads the button positions from the PCB (needs pcbnew)."""
    outline, _, _ = plate(side)
    # Cavity: PCB + clearance, and the daughterboard bay behind the keys. Inside
    # corners no tighter than a 3 mm end mill.
    inner_wall = unary_union([geo.pcb_outline(side).buffer(WALL_CLEARANCE, join_style="round"),
                              geo.bay(side).buffer(WALL_CLEARANCE, join_style="mitre")])
    inner_wall = inner_wall.buffer(-TOOL_R, join_style="round").buffer(TOOL_R, join_style="round")
    gasket_pockets = [t.buffer(0.5, join_style="round") for t in gasket_tabs(side)]
    # Outside: a uniform wall that swallows the gasket pockets, then one smooth
    # profile (no concave radius under OUTSIDE_R) instead of following every pocket.
    trackpad = []
    main = side == geo.MAIN_SIDE
    if main:
        # The pad's board + overlay sit in a counterbore flush with the top, the rim
        # on a ledge; its parts hang into a well that opens into the tab cavity.
        trackpad = [PAD.top(side, PAD.gap), PAD.well(side)]
    outer = unary_union([inner_wall.buffer(WALL, join_style="round"),
                         geo.inner_column(side).buffer(WALL_CLEARANCE + WALL, join_style="round"),
                         *[p.buffer(MIN_WALL, join_style="round") for p in gasket_pockets],
                         *[t.buffer(MIN_WALL, join_style="round") for t in trackpad[:1]]])
    outer = outer.buffer(OUTSIDE_R, join_style="round").buffer(-OUTSIDE_R, join_style="round")
    # Flat back face PORT_WALL behind the bay: both plugs mate through a thin wall,
    # so the ports are plain through-cuts with no side-milled reliefs.
    db = daughterboard_footprint(side)
    minx, miny, maxx, maxy = db.bounds
    face = miny - PORT_WALL
    ox0, _, ox1, oy1 = outer.bounds
    outer = outer.intersection(box(ox0 - 1, face, ox1 + 1, oy1 + 1))
    outer = outer.buffer(-CORNER_R, join_style="round").buffer(CORNER_R, join_style="round")
    # Ports through the back face: DE-15 shell cutout, 4-40 screwlocks 24.99 mm
    # apart, and the USB-C opening on the main half.
    cx = (minx + maxx) / 2
    through = (face - 1.0, miny + 0.5)
    ports = [box(cx - DE15_CUTOUT[0] / 2, through[0], cx + DE15_CUTOUT[0] / 2, through[1])]
    jackscrews = [box(x - 1.6, through[0], x + 1.6, through[1]) for x in (cx - 12.5, cx + 12.5)]
    if main:
        ux, _ = geo.anchor("USB", side)
        ports.append(box(ux - USB_OPENING[0] / 2, through[0], ux + USB_OPENING[0] / 2, through[1]))
    # The top frame is a thin roof wherever the cavity isn't under the plate
    # opening: over the MCU module, the bay and the USB ear.
    opening = plate_outline(side).buffer(WALL_CLEARANCE, join_style="round")
    roof = inner_wall.difference(opening).buffer(-0.5).buffer(0.5)
    layers = {"OUTER_WALL": [outer], "INNER_WALL": [inner_wall], "GASKET_POCKETS": gasket_pockets,
              "PLATE": [outline], "ROOF": list(getattr(roof, "geoms", [roof])), "DAUGHTERBOARD": [db],
              "PORTS": ports, "JACKSCREWS": jackscrews}
    if main:
        layers["MCU_MODULE"] = [geo.module_rect(side)]
    if trackpad:
        layers["TRACKPAD"] = trackpad[:1]
        layers["TRACKPAD_WELL"] = trackpad[1:]
    layers["MOUNTS"] = [Point(x, y).buffer(geo.MOUNT_BOSS / 2, 64) for x, y in geo.mounts(side)]
    layers["MOUNT_ZONE"] = [mount_zone(side)]
    if floor_access:
        board = "main" if main else "satellite"
        pcb_path = HARDWARE / "kicad" / board / f"vgacorne-{board}.kicad_pcb"
        if main:
            layers["FLOOR_ACCESS"] = access_holes(pcb_path)
        layers["FLOOR_POCKETS"] = [p.intersection(inner_wall) for p in floor_pockets(pcb_path)]
    layers["FEET"] = feet(side, outer, layers.get("FLOOR_ACCESS", []))
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
    for side, board in ((geo.MAIN_SIDE, "main"), (geo.SATELLITE_SIDE, "satellite")):
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
