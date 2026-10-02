"""3D case: a CNC aluminium bottom tray and top frame per half, as STEP files.

Everything comes from the 2D case plan (:func:`mechanical.case`, the layers of
``case-plan-*.dxf``) and the Z stack-up (:data:`mechanical.STACK`):

* **Tray** (z 0 to the seam at the plate's underside): the floor with its
  access holes and pockets, the walls, the lower gasket pockets, and M3
  clearance holes counterbored from below.
* **Frame** (seam to the top): the walls, the upper gasket pockets, the bezel
  opening round the plate, the 1.5 mm roof over the tab, bay and USB ear,
  the trackpad's counterbore and well, and blind M3 tap holes.
* Both: the DE-15, USB-C and jackscrew holes through the flat back face.
* Underneath: two 1/4"-20 mounts for tripods, tenting heads and desk arms, in
  bosses that rise into clear spots under the PCB.

Two builds (``BUILDS``) differ in their holes, and the printed one in a floor
2 mm thicker underneath: ``tapped`` for aluminium (drill and tap), ``inserts``
for FDM prints (heat-set inserts).

Each gasket pocket holds a strip under and over the plate tab at 25 %
compression (``GASKET_COMPRESSION``). :func:`fit_check` builds the parts
inside the case (PCB, plate, daughterboard, MCU module, trackpad, encoder,
USB-C) as solids and reports any that run into the tray or frame.

Coordinates are those of the DXFs: board millimetres with Y flipped (CAD is Y
up), Z up from the case underside.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from pathlib import Path

from build123d import (Compound, Cylinder, Edge, ExportSVG, Face, Location, Part, Plane, RectangleRounded,
                       Wire, export_step, export_stl, extrude)
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from . import geometry as geo
from . import mechanical as mech
from .trackpad import MODEL as PAD

ST = mech.STACK
SEAM = ST.plate_bottom          # tray / frame split
TOP = ST.case_height
GASKET_COMPRESSION = 0.25
GASKET_SET = ST.gasket * (1 - GASKET_COMPRESSION)  # each strip, compressed



@dataclass(frozen=True)
class Build:
    """How a case is made, and so how its M3 x 12 button-head screws (ISO 7380,
    5.7 mm head) hold the frame to the tray. The frame is only 6.5 mm tall, so
    the heads sit 4 mm up their counterbores, leaving ~4 mm of thread in the
    frame and 1.5 mm of material over its blind hole."""
    name: str                       # file suffix
    material: str
    clear: float                    # screw clearance hole through the tray
    head: tuple[float, float]       # counterbore from below: diameter, depth
    hole: tuple[float, float]       # blind hole up into the frame: diameter, depth above the seam
    fastener: str                   # what makes the thread
    bottom: float                   # extra floor under the case (z 0 is the aluminium case's underside)
    mount_hole: tuple[float, float]  # each 1/4"-20 mount: diameter, depth up from the underside
    mount: str


# The mounts sit in bosses that stop 0.5 mm under the PCB, so the floor and boss
# give 6.5 mm. Tapped aluminium needs 5.5 mm of it (ISO 1222: a 5.5 mm socket
# with 4 mm of full thread; tripod screws stand 4.5 mm proud). A 6.4 mm insert
# needs 7.4 mm, so the printed floor is 2 mm thicker underneath: a pad round
# just the mounts would leave the rest of the floor overhanging the print bed.
# Hole sizes for prints are CAD sizes: printed holes come out ~0.2 mm small.
TAPPED = Build("tapped", "aluminium (CNC 6061, or printed AlSi10Mg)", 3.4, (6.0, 4.0), (2.5, 5.0),
               "M3 x 0.5 tapped, ~3.5 mm full thread (2.5 mm drill, 5 mm deep)", 0.0, (5.1, 5.5),
               '1/4"-20 UNC tapped, 4.5 mm full thread (#7 = 5.1 mm drill, 5.5 mm deep)')
INSERTS = Build("inserts", "FDM print (PLA, ABS/ASA, nylon)", 3.5, (6.2, 4.0), (4.2, 5.0),
                "M3 x 4.0 heat-set insert (ruthex RX-M3Sx4.0, or CNC Kitchen M3 x 3), flush", 2.0, (8.2, 7.4),
                '1/4"-20 x 6.4 heat-set insert (CNC Kitchen or ruthex "short"), flush with the underside')
BOSS_TOP = ST.pcb_bottom - 0.5
BUILDS = (TAPPED, INSERTS)
SCREW = "M3 x 12 ISO 7380"
SCREW_EDGE = 0.5                # material between the counterbore and the cavity
SCREW_KEEP = 2.0                # from gasket pockets, ports and the trackpad

DB_HEIGHT = 13.0                # pcb.LINK_H: the daughterboard stands on edge, the DE-15 at its centre
ENCODER_BODY = (12.4, 13.4)
ENCODER_COLLAR_D = 7.0
KNOB = (16.0, 11.5)             # diameter, height
KNOB_Z = 19.1

# Curves come from shapely as polylines, sampled ever finer by repeated
# buffering. _wire turns them back into the fewest lines and true arcs that
# stay within _FIT_TOL of every vertex: G1/G2/G3 moves for the machinist, and a
# compact STEP.
_FIT_TOL = 0.02
_CORNER = math.radians(15)      # a sharper turn always ends a line or arc
_MAX_ARC = math.radians(170)    # three-point arcs: keep each under a half turn
_CHORD_ANGLE = math.radians(12)  # shapely samples arcs at 5.6 degrees
_CHORD_SAG = 0.05


def _flip(geom):
    return affinity.scale(geom, 1, -1, origin=(0, 0))


def _polys(geom) -> list[Polygon]:
    """The polygons in ``geom``, without the slivers that 2D booleans leave."""
    if isinstance(geom, (list, tuple)):
        return [p for g in geom for p in _polys(g)]
    if isinstance(geom, MultiPolygon) or hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in _polys(g)]
    return [geom] if isinstance(geom, Polygon) and geom.area > 0.5 else []


def _circle(a, b, c):
    """Centre and radius of the circle through three points (None if nearly straight)."""
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.dist((ux, uy), a)
    return ((ux, uy), r) if r < 1000 else None


def _wire(ring) -> Wire:
    pts = []
    for q in ring.coords[:-1]:
        if not pts or math.dist(pts[-1], q) > 1e-4:
            pts.append(q)
    if math.dist(pts[0], pts[-1]) <= 1e-4:
        pts.pop()
    n = len(pts)

    def p(i):
        return pts[i % n]

    def turn(i):  # signed turn at vertex i
        (ax, ay), (bx, by), (cx, cy) = p(i - 1), p(i), p(i + 1)
        a1, a2 = math.atan2(by - ay, bx - ax), math.atan2(cy - by, cx - bx)
        return (a2 - a1 + math.pi) % (2 * math.pi) - math.pi

    turns = [turn(i) for i in range(n)]
    corner = [abs(a) >= _CORNER for a in turns]

    def line_fits(i, j):
        (ax, ay), (bx, by) = p(i), p(j)
        length = math.dist((ax, ay), (bx, by))
        if length < 1e-9:
            return False
        return all(abs((bx - ax) * (ay - p(k)[1]) - (ax - p(k)[0]) * (by - ay)) / length <= _FIT_TOL
                   for k in range(i + 1, j))

    def middle(i, j):  # the vertex halfway along the run by length
        run = [math.dist(p(k), p(k + 1)) for k in range(i, j)]
        half, acc = sum(run) / 2, 0.0
        for k, length in enumerate(run):
            acc += length
            if acc >= half:
                return min(max(i + k + 1 if acc - half < length / 2 else i + k, i + 1), j - 1)
        return (i + j) // 2

    def arc_fits(i, j):
        m = middle(i, j)
        circle = _circle(p(i), p(m), p(j))
        if circle is None:
            return None
        centre, r = circle
        span = abs(sum(turns[k % n] for k in range(i + 1, j)))
        if span > _MAX_ARC or any(turns[k % n] * turns[(i + 1) % n] < 0 for k in range(i + 1, j)):
            return None
        on_circle = all(abs(math.dist(centre, p(k)) - r) <= _FIT_TOL for k in range(i, j + 1))
        # ...and every chord could be shapely's sampling of the arc: short and
        # shallow (a long straight side would bow out).
        chords = [math.dist(p(k), p(k + 1)) for k in range(i, j)]
        sampled = all(c <= 2 * r * math.sin(_CHORD_ANGLE / 2) and
                      r - math.sqrt(max(r * r - (c / 2) ** 2, 0)) <= _CHORD_SAG for c in chords)
        return m if on_circle and sampled else None

    # Start at a corner if there is one, so nothing wraps round the start.
    start = next((i for i in range(n) if corner[i]), 0)
    edges, i, end = [], start, start + n
    while i < end:
        j = i + 1
        while j < end and not corner[j % n] and line_fits(i, j + 1):
            j += 1
        a = i + 2
        if a <= end and not corner[(i + 1) % n] and arc_fits(i, a):
            while a < end and not corner[a % n] and arc_fits(i, a + 1):
                a += 1
        else:
            a = i
        if a > j:
            edges.append(Edge.make_three_point_arc((*p(i), 0), (*p(arc_fits(i, a)), 0), (*p(a), 0)))
            i = a
        else:
            edges.append(Edge.make_line((*p(i), 0), (*p(j), 0)))
            i = j
    return Wire(edges)


def _face(poly: Polygon) -> Face:
    poly = orient(_flip(poly))  # exterior anticlockwise: the face's normal is +Z
    return Face(_wire(poly.exterior), [_wire(r) for r in poly.interiors])


def prism(geom, z0: float, z1: float) -> Part | None:
    """Extrude 2D board-coordinate polygons between two heights. Overlapping
    polygons are merged first, so the solids are disjoint and go into one
    compound rather than through a fuse each."""
    polys = _polys(unary_union(_polys(geom))) if len(_polys(geom)) > 1 else _polys(geom)
    solids = [extrude(_face(p), amount=z1 - z0, dir=(0, 0, 1)).moved(Location((0, 0, z0))) for p in polys]
    if not solids:
        return None
    return solids[0] if len(solids) == 1 else Part(Compound(children=solids).wrapped)


def _cut(part: Part, cutters) -> Part:
    for c in cutters:
        if c is not None:
            part = part - c
    return part


def _through_back(cx: float, cz: float, w: float, h: float, r: float, y0: float, y1: float) -> Part:
    """A w x h opening (corner radius r) centred on board x ``cx`` and height ``cz``,
    from board y ``y0`` to ``y1``."""
    sk = Plane.XZ * RectangleRounded(w, h, r)
    return extrude(sk, amount=(y1 - y0) / 2, both=True).moved(Location((cx, -(y0 + y1) / 2, cz)))


def _hole(x: float, y: float, d: float, z0: float, z1: float) -> Part:
    return Cylinder(d / 2, z1 - z0).moved(Location((x, -y, (z0 + z1) / 2)))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class Half:
    def __init__(self, side: str, build: Build = TAPPED):
        self.side, self.build = side, build
        self.main = side == geo.MAIN_SIDE
        self.layers = mech.case(side)
        self.outer = self.layers["OUTER_WALL"][0]
        self.inner = self.layers["INNER_WALL"][0]
        self.roof = unary_union(self.layers["ROOF"])
        self.pockets = self.layers["GASKET_POCKETS"]
        db = self.layers["DAUGHTERBOARD"][0]
        self.db = db
        self.face = db.bounds[1] - mech.PORT_WALL          # board y of the back face
        self.through = (self.face - 1.0, db.bounds[1] + 0.5)
        self.vga_x = (db.bounds[0] + db.bounds[2]) / 2
        self.screws = self._screw_positions()

    def _keepout(self):
        keep = [p.buffer(SCREW_KEEP) for p in self.pockets]
        keep += [p.buffer(SCREW_KEEP) for p in self.layers["PORTS"] + self.layers["JACKSCREWS"]]
        keep += [p.buffer(SCREW_KEEP) for p in self.layers.get("TRACKPAD", []) + self.layers.get("TRACKPAD_WELL", [])]
        return unary_union(keep)

    def _screw_positions(self) -> list[tuple[float, float]]:
        """Evenly spread points on the wall's midline with room for the hole."""
        wall = self.outer.difference(self.inner)
        need = max(b.head[0] for b in BUILDS) / 2 + SCREW_EDGE  # same places in every build
        hole = max(max(b.clear, b.hole[0]) for b in BUILDS)
        line = self.inner.buffer(mech.WALL / 2).exterior
        keep = self._keepout()
        cands = []
        for i in range(int(line.length)):
            p = line.interpolate(i)
            if wall.contains(p.buffer(need, 16)) and not keep.intersects(p.buffer(hole / 2)):
                cands.append((p.x, p.y))
        count = max(6, min(8, round(self.outer.exterior.length / 60)))
        # Farthest-point sampling from the point nearest the back face's middle.
        chosen = [min(cands, key=lambda c: math.dist(c, (self.vga_x, self.face)))]
        while len(chosen) < count:
            chosen.append(max(cands, key=lambda c: min(math.dist(c, q) for q in chosen)))
        cx, cy = self.outer.centroid.x, self.outer.centroid.y
        return sorted(chosen, key=lambda c: math.atan2(c[1] - cy, c[0] - cx))  # numbered round the case

    # -- ports ---------------------------------------------------------------

    def _ports(self) -> list[Part]:
        y0, y1 = self.through
        cut = [_through_back(self.vga_x, mech.VGA_Z, *mech.DE15_CUTOUT, 1.0, y0, y1)]
        for hole in self.layers["JACKSCREWS"]:
            x0, _, x1, _ = hole.bounds
            cut.append(Cylinder((x1 - x0) / 2, y1 - y0, rotation=(90, 0, 0)).moved(
                Location(((x0 + x1) / 2, -(y0 + y1) / 2, mech.VGA_Z))))
        if self.main:
            ux, _ = geo.anchor("USB", self.side)
            cut.append(_through_back(ux, mech.USB_Z, *mech.USB_OPENING, 1.0, y0, y1))
        return cut

    # -- parts ---------------------------------------------------------------

    def tray(self) -> Part:
        b = self.build
        under = -b.bottom
        part = prism(self.outer, under, SEAM) - prism(self.inner, ST.floor, SEAM + 1)
        part = part + prism(self.layers["MOUNTS"], ST.floor - 1.0, BOSS_TOP)  # overlaps the floor
        cutters = [prism(self.pockets, SEAM - GASKET_SET, SEAM + 1),
                   prism(self.layers.get("FLOOR_ACCESS", []), under - 1, ST.floor + 1),
                   prism(self.layers.get("FLOOR_POCKETS", []), ST.floor - mech.FLOOR_POCKET, ST.floor + 1),
                   *self._ports()]
        for x, y in self.screws:  # heads sit up the counterbore by the same amount in every build
            cutters += [_hole(x, y, b.clear, under - 1, SEAM + 1), _hole(x, y, b.head[0], under - 1, b.head[1])]
        for x, y in geo.mounts(self.side):
            cutters.append(_hole(x, y, b.mount_hole[0], under - 1, under + b.mount_hole[1]))
        return _cut(part, cutters)

    def frame(self) -> Part:
        # The wall ring, plus the roof grown 0.05 mm so it overlaps the walls
        # rather than meeting them face to face (near-coincident faces break
        # OpenCascade's booleans).
        part = prism(self.outer.difference(self.inner), SEAM, TOP)
        part = part + prism(self.roof.buffer(0.05, join_style="mitre"), TOP - ST.roof, TOP)
        cutters = [prism(self.pockets, SEAM - 1, ST.plate_top + GASKET_SET), *self._ports()]
        for pad in self.layers.get("TRACKPAD", []):
            cutters.append(prism(pad, TOP - PAD.board_t, TOP + 1))
        for well in self.layers.get("TRACKPAD_WELL", []):
            cutters.append(prism(well, TOP - PAD.board_t - PAD.parts, TOP - PAD.board_t + 0.01))
        for x, y in self.screws:
            cutters.append(_hole(x, y, self.build.hole[0], SEAM - 1, SEAM + self.build.hole[1]))
        return _cut(part, cutters)

    # -- what goes inside ----------------------------------------------------

    def contents(self) -> dict[str, Part]:
        return contents(self.side)


@functools.cache
def contents(side: str) -> dict[str, Part]:
    """Solids for the parts inside the case, at their nominal positions, inset
    FIT_SLACK in plan so parts that touch by design (the DE-15's flange on the
    back wall) don't count."""
    def body(geom, z0, z1):
        return prism(_inset(geom), z0, z1)

    main = side == geo.MAIN_SIDE
    pcb_top = ST.pcb_bottom + ST.pcb
    board = "main" if main else "satellite"
    under = mech.bottom_side(mech.HARDWARE / "kicad" / board / f"vgacorne-{board}.kicad_pcb")
    db = mech.daughterboard_footprint(side)
    out = {
        "PCB": body(geo.pcb_outline(side), ST.pcb_bottom, pcb_top),
        "plate": body(mech.plate(side)[0], ST.plate_bottom, ST.plate_top),
        "daughterboard": body(db, mech.VGA_Z - DB_HEIGHT / 2, mech.VGA_Z + DB_HEIGHT / 2),
    }
    for depth in sorted({d for _, d in under}):
        out[f"parts under the PCB ({depth:g} mm)"] = body(
            [p for p, d in under if d == depth], ST.pcb_bottom - depth, ST.pcb_bottom)
    if main:
        out["MCU module"] = body(geo.module_rect(side), pcb_top, ST.module_top)
        out["trackpad overlay"] = body(PAD.top(side), TOP - PAD.board_t, TOP)
        out["trackpad module"] = body(PAD.outline(side), TOP - PAD.board_t - PAD.parts, TOP - PAD.board_t)
    else:
        x, y = geo.corne(*geo.ENCODER)
        if side == "right":
            x, y = geo.mirror_point(x, y)
        w, h = ENCODER_BODY
        out["encoder"] = body(box(x - w / 2, y - h / 2, x + w / 2, y + h / 2), pcb_top, ST.plate_top + 0.1)
        out["encoder collar"] = body(Point(x, y).buffer(ENCODER_COLLAR_D / 2, 32), pcb_top,
                                     pcb_top + geo.ENCODER_COLLAR)
        out["knob"] = body(Point(x, y).buffer(KNOB[0] / 2, 64), KNOB_Z, KNOB_Z + KNOB[1])
    return out


FIT_SLACK = 0.05


def _inset(geom):
    return unary_union([p.buffer(-FIT_SLACK, join_style="mitre") for p in _polys(geom)])


def fit_check(half: Half, tray: Part, frame: Part, tolerance: float = 1e-3) -> list[str]:
    """Interference between the case parts and what goes inside (mm^3 above ``tolerance``)."""
    problems = []
    for name, body in half.contents().items():
        for part_name, part in (("tray", tray), ("frame", frame)):
            v = (body & part).volume
            if v > tolerance:
                problems.append(f"{half.side} {name} runs into the {part_name} ({v:.2f} mm^3)")
    v = (tray & frame).volume
    if v > tolerance:
        problems.append(f"{half.side} tray and frame overlap ({v:.2f} mm^3)")
    return problems


def _step_body(path: Path) -> str:
    """A STEP file without its header, which carries a timestamp."""
    return path.read_text().split("ENDSEC;", 1)[1] if path.exists() else ""


def _export(part: Part, path: Path) -> bool:
    """Write ``path`` unless only its header would change; True if written."""
    part.label = path.stem
    tmp = path.with_suffix(".tmp")
    export_step(part, str(tmp))
    if _step_body(tmp) == _step_body(path):
        tmp.unlink()
        return False
    tmp.replace(path)
    return True


def preview(tray: Part, frame: Part, side: str, path: Path) -> Path | None:
    """Exploded view of the tray and frame, visible edges only; None if unchanged."""
    bb = tray.bounding_box()
    cx, cy = (bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2
    away = -1 if side == "right" else 1  # look from the outer end
    shapes = Compound(children=[tray, frame.moved(Location((0, 0, 30)))])
    visible, _ = shapes.project_to_viewport((cx - away * 250, cy - 300, 300), viewport_up=(0, 0, 1),
                                            look_at=(cx, cy, 20))
    svg = ExportSVG(scale=200 / max(*Compound(children=visible).bounding_box().size))
    svg.add_layer("visible", line_weight=0.12)
    svg.add_shape(visible, layer="visible")
    tmp = path.with_suffix(".tmp")
    svg.write(str(tmp))
    if path.exists() and path.read_bytes() == tmp.read_bytes():
        tmp.unlink()
        return None
    tmp.replace(path)
    return path


DRAWING_NOTES = [
    "Units mm. Plan view from above; holes marked * are drilled from below.",
    "Material: aluminium 6061-T6 (CNC) or AlSi10Mg (SLM). General tolerance +/-0.1.",
    "Threads as tabulated, cutting taps. Mask all tapped holes when anodising.",
    "Break all sharp edges 0.2-0.5. Bead blast, then anodise.",
]


def drawing(half: Half, part: str, path: Path) -> Path | None:
    """The tapped holes of one part of a ``tapped`` half as a DXF drawing: what
    CNC shops need beside the STEP, since none reads threads from it."""
    import ezdxf

    b = half.build
    holes = []
    if part == "frame":
        holes += [("A", xy, f"M3 x 0.5: {b.fastener}") for xy in half.screws]
    else:
        holes += [("B", xy, f"Clearance {b.clear} thru, counterbore {b.head[0]} x {b.head[1]} deep*")
                  for xy in half.screws]
        holes += [("C", xy, f"{b.mount}*") for xy in geo.mounts(half.side)]
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for name in ("OUTLINE", "HOLES", "TEXT"):
        doc.layers.add(name)
    for ring in [half.outer.exterior]:
        msp.add_lwpolyline([(x, -y) for x, y in ring.coords], close=True, dxfattribs={"layer": "OUTLINE"})
    rows = {}
    for kind, (x, y), spec in holes:
        n = sum(1 for k in rows if k.startswith(kind)) + 1
        rows[f"{kind}{n}"] = spec
        d = b.hole[0] if kind == "A" else b.clear if kind == "B" else b.mount_hole[0]
        msp.add_circle((x, -y), d / 2, dxfattribs={"layer": "HOLES"})
        msp.add_text(f"{kind}{n}", height=2.0, dxfattribs={"layer": "TEXT"}).set_placement((x + 3, -y + 1))
    x0, y0, x1, y1 = half.outer.bounds
    lines = [f"{path.stem}: {b.material}"] + DRAWING_NOTES + [""]
    for kind in sorted({k[0] for k in rows}):
        refs = [k for k in rows if k[0] == kind]
        lines.append(f"{refs[0]}-{refs[-1]} ({len(refs)}x): {rows[refs[0]]}")
    for i, line in enumerate(lines):
        msp.add_text(line, height=2.5, dxfattribs={"layer": "TEXT"}).set_placement((x0, -y1 - 10 - 4.5 * i))
    tmp = path.with_suffix(".tmp")
    doc.saveas(tmp)
    # ezdxf stamps a time and fresh handles: keep the old file unless the drawing changed.
    if path.exists() and _dxf_entities(path) == _dxf_entities(tmp):
        tmp.unlink()
        return None
    tmp.replace(path)
    return path


def _dxf_entities(path: Path) -> list:
    import ezdxf

    return sorted(str((e.dxftype(), e.dxf.layer, getattr(e.dxf, "text", ""),
                       [tuple(round(v, 4) for v in p) for p in e.get_points()] if e.dxftype() == "LWPOLYLINE"
                       else tuple(round(v, 4) for v in getattr(e.dxf, "center", getattr(e.dxf, "insert", ())))))
                  for e in ezdxf.readfile(path).modelspace())


def _stl(part: Part, path: Path) -> None:
    export_stl(part, str(path), tolerance=0.01, angular_tolerance=0.1)


def write(side: str, out: Path) -> tuple[list[Path], list[str]]:
    """Write ``case-<side>-<tray|frame>-<build>.step`` for every build (and an STL
    of each printed part) plus a ``case-<side>.svg`` preview; return the paths
    written and any fit problems."""
    written, problems = [], []
    for build in BUILDS:
        half = Half(side, build)
        tray, frame = half.tray(), half.frame()
        for name, part in (("tray", tray), ("frame", frame)):
            path = out / f"case-{side}-{name}-{build.name}.step"
            stl = path.with_suffix(".stl")
            if _export(part, path):
                written.append(path)
            if build is INSERTS and (path in written or not stl.exists()):
                _stl(part, stl)
                written.append(stl)
        problems += fit_check(half, tray, frame)
        if build is TAPPED:
            written += [p for p in [preview(tray, frame, side, out / f"case-{side}.svg"),
                                    drawing(half, "tray", out / f"case-{side}-tray-tapped.dxf"),
                                    drawing(half, "frame", out / f"case-{side}-frame-tapped.dxf")] if p]
    return written, problems


def check() -> list[str]:
    """Fit problems, and any STEP file that is out of date."""
    problems = []
    for side in (geo.MAIN_SIDE, geo.SATELLITE_SIDE):
        for build in BUILDS:
            half = Half(side, build)
            tray, frame = half.tray(), half.frame()
            problems += fit_check(half, tray, frame)
            for name, part in (("tray", tray), ("frame", frame)):
                path = mech.OUT / f"case-{side}-{name}-{build.name}.step"
                tmp = path.with_suffix(".check")
                part.label = path.stem
                export_step(part, str(tmp))
                if _step_body(tmp) != _step_body(path):
                    problems.append(f"{path.name} is out of date: run generate.py case")
                tmp.unlink()
    return problems
