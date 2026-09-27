"""Physical layout of one VGACorne half.

Key positions are the canonical Corne v4 (foostan/crkbd corne-cherry) left-half
coordinates. Everything else -- PCB outline, standoffs, mux/MCU anchor points,
plate, foam and case envelopes -- is derived from them, so moving a key here
moves it everywhere.

All coordinates are KiCad board millimetres (Y grows downward). The left half
is the main half (MCU + USB); the right half is its mirror image.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

U = 19.05  # 1u key pitch

# Offset from Corne v4 coordinates to our board frame (keeps both halves on an A4 sheet).
ORIGIN = (150.0, 60.0)
# Right-half boards are the left half mirrored about this X.
MIRROR_X = 150.0 + 150.0


@dataclass(frozen=True)
class Key:
    name: str  # "C0R0" ... "C5R2", "T0".."T2"
    col: int  # 0 = outer pinky ... 5 = inner index; thumbs use 6
    row: int  # 0 = top ... 2 = bottom; thumbs use 3 + thumb index
    x: float
    y: float
    rot: float  # degrees, KiCad convention (counter-clockwise on screen)
    w: float = 1.0  # keycap width in u, along the key's local X axis

    def local(self, dx: float, dy: float) -> tuple[float, float]:
        """Board coordinates of a point given in the key's rotated frame."""
        a = math.radians(self.rot)
        return (self.x + dx * math.cos(a) + dy * math.sin(a),
                self.y - dx * math.sin(a) + dy * math.cos(a))

    def cell(self, margin: float = 0.0) -> Polygon:
        """Keycap grid cell (w x 1u), optionally grown by ``margin``."""
        hw, hh = self.w * U / 2 + margin, U / 2 + margin
        return affinity.rotate(affinity.translate(box(-hw, -hh, hw, hh), self.x, self.y),
                               -self.rot, origin=(self.x, self.y))

    def square(self, size: float) -> Polygon:
        """Axis-aligned (in key frame) square centred on the switch, e.g. a plate cutout."""
        h = size / 2
        return affinity.rotate(box(self.x - h, self.y - h, self.x + h, self.y + h),
                               -self.rot, origin=(self.x, self.y))


# Corne v4 left half: column X and per-row Y (mm, Corne frame).
_COLUMNS = [
    (-128.5875, (-7.14375, 11.90625, 30.95625)),
    (-109.5375, (-7.14375, 11.90625, 30.95625)),
    (-90.4875, (-11.90625, 7.14375, 26.19375)),
    (-71.4375, (-14.2875, 4.7625, 23.8125)),
    (-52.3875, (-11.90625, 7.14375, 26.19375)),
    (-33.3375, (-9.525, 9.525, 28.575)),
]
# Thumbs: (x, y, rotation, width). T2 is the tilted 1.5u key.
_THUMBS = [
    (-61.9125, 47.625, 0.0, 1.0),
    (-41.097974, 49.801677, -11.94, 1.0),
    (-19.256135, 51.882713, 66.12, 1.5),
]

# Inner (MCU-column) region of the classic Corne outline, Corne frame.
INNER_X = (-33.3375 + U / 2, -4.2625)
INNER_TOP = -17.16875
# The top of the inner column is the "tab": USB-C and regulators underneath,
# the swappable MCU module on top. Below POCKET_TOP the case holds the vertical
# VGA daughterboard instead of PCB.
POCKET_TOP = 1.0
POCKET_BOTTOM = 34.5

# MCU module (Corne frame). It sits on top of the tab on a 2x12 1.27 mm
# header/socket pair; the plate is cut away above the tab.
MODULE_RECT = (-24.0, -16.4, -4.8, 0.4)  # x0, y0, x1, y1
# 2x12 connector: runs along X below the USB-C (whose locating pegs go through the tab).
MODULE_CONN = (-14.0, -6.0)
MODULE_CONN_ROT = 90.0


def _c(x: float, y: float) -> tuple[float, float]:
    return x + ORIGIN[0], y + ORIGIN[1]


def left_keys() -> list[Key]:
    keys = []
    for col, (cx, ys) in enumerate(_COLUMNS):
        for row, cy in enumerate(ys):
            x, y = _c(cx, cy)
            keys.append(Key(f"C{col}R{row}", col, row, x, y, 0.0))
    for i, (tx, ty, rot, w) in enumerate(_THUMBS):
        x, y = _c(tx, ty)
        keys.append(Key(f"T{i}", 6, 3 + i, x, y, rot, w))
    return keys


def mirror_point(x: float, y: float) -> tuple[float, float]:
    return MIRROR_X - x, y


def keys_for(side: str) -> list[Key]:
    keys = left_keys()
    if side == "left":
        return keys
    return [replace(k, x=mirror_point(k.x, k.y)[0], rot=-k.rot) for k in keys]


def place(side: str, x: float, y: float, rot: float = 0.0) -> tuple[float, float, float]:
    """Map a left-half (board frame) placement onto ``side``."""
    if side == "left":
        return x, y, rot
    mx, my = mirror_point(x, y)
    return mx, my, -rot


def corne(x: float, y: float) -> tuple[float, float]:
    """Corne-frame coordinate -> left-half board coordinate."""
    return _c(x, y)


# ---------------------------------------------------------------------------
# Outlines
# ---------------------------------------------------------------------------

EDGE_MARGIN = 0.5  # PCB edge beyond the 19.05 key grid, as on the Corne
CORNER_R = 1.0  # convex corner radius
CLOSE_R = 5.0  # fills the wedges between rotated thumb keys and stagger notches


def _smooth(poly: Polygon) -> Polygon:
    closed = poly.buffer(CLOSE_R, join_style="round").buffer(-CLOSE_R, join_style="round")
    return closed.buffer(-CORNER_R, join_style="round").buffer(CORNER_R, join_style="round")


def inner_tab_left() -> Polygon:
    x0, x1 = INNER_X
    (ax, ay), (bx, by) = _c(x0 - 1.0, INNER_TOP), _c(x1, POCKET_TOP)
    return box(ax, ay, bx, by)


def pocket_left() -> Polygon:
    """Area reserved for the VGA daughterboard (no PCB, no plate)."""
    x0, x1 = INNER_X
    (ax, ay), (bx, by) = _c(x0, POCKET_TOP), _c(x1, POCKET_BOTTOM)
    return box(ax, ay, bx, by)


def pcb_outline(side: str, with_tab: bool = True) -> Polygon:
    keys = keys_for("left")
    cells = [k.cell(EDGE_MARGIN) for k in keys]
    shape = _smooth(unary_union(cells + ([inner_tab_left()] if with_tab else [])))
    # Closing grows into the daughterboard pocket; cut it back out, then give the
    # pocket's inside corners a router-friendly radius.
    shape = shape.difference(pocket_left())
    shape = shape.buffer(0.8, join_style="round").buffer(-0.8, join_style="round")
    if not isinstance(shape, Polygon):
        shape = max(shape.geoms, key=lambda g: g.area)
    return mirror(shape) if side == "right" else shape


def plate_outline(side: str) -> Polygon:
    """Like the PCB, minus the inner tab: the MCU module stands up there."""
    return pcb_outline(side, with_tab=False)


def module_rect(side: str) -> Polygon:
    x0, y0, x1, y1 = MODULE_RECT
    (ax, ay), (bx, by) = _c(x0, y0), _c(x1, y1)
    r = box(ax, ay, bx, by)
    return mirror(r) if side == "right" else r


def mirror(geom):
    return affinity.scale(geom, xfact=-1, yfact=1, origin=(MIRROR_X / 2, 0))


# ---------------------------------------------------------------------------
# Mechanical features shared by PCB, plate and case
# ---------------------------------------------------------------------------

# PCB <-> plate M2 standoffs (Corne frame). HE switches are not soldered, so
# the plate and PCB must be tied together rigidly or plate flex would change
# the magnet-to-sensor distance.
_STANDOFFS = [
    (-119.0625, 2.38125),   # col0/col1, rows 0-1
    (-119.0625, 21.43125),  # col0/col1, rows 1-2
    (-80.9625, -3.571875),  # col2/col3, rows 0-1
    (-80.9625, 15.478125),  # col2/col3, rows 1-2
    (-42.8625, 17.859375),  # col4/col5, rows 1-2
    (-51.5, 48.7),          # between T0 and T1
    (-100.0125, 28.0),      # col1/col2, bottom row
]


def standoffs(side: str) -> list[tuple[float, float]]:
    pts = [_c(x, y) for x, y in _STANDOFFS]
    return pts if side == "left" else [mirror_point(x, y) for x, y in pts]


# Anchor points for the analog muxes (Corne frame), one per column pair:
# mux A = col0+col1, mux B = col2+col3+T0, mux C = col4+col5+T1+T2.
MUX_ANCHORS = {
    "A": (-109.5375, 2.38125),
    "B": (-71.4375, 14.2875),
    "C": (-33.3375, 19.05),
}
USB_ANCHOR = (-13.0, -17.16875)     # top edge of the inner tab (USB-C on B.Cu)
LINK_ANCHOR = (-14.0, -2.1)         # JST-SH link on B.Cu at the tab's bottom edge, facing the pocket


def anchor(name: str, side: str) -> tuple[float, float]:
    table = {"MODULE_CONN": MODULE_CONN, "USB": USB_ANCHOR, "LINK": LINK_ANCHOR,
             **{f"MUX_{k}": v for k, v in MUX_ANCHORS.items()}}
    x, y = _c(*table[name])
    return (x, y) if side == "left" else mirror_point(x, y)


def sensor_keepouts(side: str, radius: float = 3.8) -> list[Polygon]:
    """Areas around each switch centre (sensor + its two caps) and switch pegs."""
    out = []
    for k in keys_for(side):
        out.append(Point(k.x, k.y).buffer(radius))
        for dx in (-5.08, 5.08):
            out.append(Point(*k.local(dx, 0)).buffer(1.8))
    return out
