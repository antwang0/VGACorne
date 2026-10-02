"""Physical layout of one VGACorne half.

Key positions are the canonical Corne v4 (foostan/crkbd corne-cherry) left-half
coordinates. Everything else -- PCB outline, standoffs, mux/MCU anchor points,
plate, foam and case envelopes -- is derived from them, so moving a key here
moves it everywhere.

All coordinates are KiCad board millimetres (Y grows downward). Everything is
drawn for the left half; the right half is its mirror image. MAIN_SIDE picks
the half that carries the MCU module, USB-C and trackpad; the other half (the
satellite) is passive apart from its mouse column: two mouse-button keys and a
rotary encoder beside its inner column, for the hand that isn't on the trackpad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

U = 19.05  # 1u key pitch

MAIN_SIDE = "right"      # MCU module, USB-C and trackpad
SATELLITE_SIDE = "left"  # sensors, muxes and cable buffer only

# Offset from Corne v4 coordinates to our board frame (keeps both halves on an A4 sheet).
ORIGIN = (150.0, 60.0)
# Right-half boards are the left half mirrored about this X.
MIRROR_X = 150.0 + 150.0


@dataclass(frozen=True)
class Key:
    name: str  # "C0R0" ... "C5R2", "T0".."T2", satellite "M0"/"M1"
    col: int  # 0 = outer pinky ... 5 = inner index; thumbs use 6, the mouse column 7
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

# Inner region of the classic Corne outline, Corne frame: exactly one key wide.
INNER_X = (-33.3375 + U / 2, -4.2625)

# VGA daughterboard bay, (x0, y0, x1, y1): the inner-back corner, behind the
# inner column and most of column 5. The vertical board stands here with its
# DE-15 facing out of the back wall, so the cable leaves backwards, away from
# the hands. No PCB or plate. 33 mm board + 1.5 mm each side and the case wall
# 0.75 mm behind y0 make the 13 mm envelope of mechanical.DB_DEPTH. The front
# is BAY_BACKSET further back than column 5 needs: that is what lets the main
# half's trackpad sit right beside Y/H/N (its bottom corner is held up by the
# tilted thumb key), and the satellite's mouse column uses the room as well.
BAY_BACKSET = 4.5
BAY_FRONT = _COLUMNS[5][1][0] - U / 2 - 1.0 - BAY_BACKSET
BAY = (INNER_X[1] - 36.0, BAY_FRONT - 12.25, INNER_X[1], BAY_FRONT)
BACK = BAY[1]  # PCB back edge at the connectors (bay and USB ear)

# The "tab": the inner column below the bay. J3 (facing the bay) and the
# regulators underneath; on the main half the MCU module on top and the trackpad
# over both, on the satellite the mouse column's keys.
INNER_TOP = BAY_FRONT
TAB_BOTTOM = 14.0
# Below the tab down to the tilted 1.5u thumb key the case is solid; the outside
# of the case runs straight past it.
INNER_BOTTOM = 34.5

# Main half only: a PCB ear behind column 4 carries the USB-C to the back wall,
# beside the DE-15.
USB_X = _COLUMNS[4][0]
USB_EAR = (USB_X - 6.5, BACK, USB_X + 6.5, _COLUMNS[4][1][0] - U / 2)
USB_OVERHANG = 0.46  # receptacle face past the ear's edge (HRO TYPE-C-31-M-12 drawing)

# The optional trackpad on the main half is described in trackpad.py; it sits
# over the tab, beside Y/H/N.

# MCU module (Corne frame), main half: soldered flat on top of the tab by 2 x 12
# castellated pads along its top and bottom edges, under the trackpad. It is
# ~2.7 mm tall, well under the pad's well (4.3 mm above the PCB), so it needs no
# space of its own in the case. All its parts are on top; its underside is flat.
# The tab is 20.55 mm wide; the landing pads run 1.2 mm out past the module's
# top and bottom edges.
MODULE_SIZE = (19.4, 25.0)
MODULE_CONN = ((INNER_X[0] - 1.0 + INNER_X[1]) / 2, INNER_TOP + 1.7 + MODULE_SIZE[1] / 2)  # module centre
MODULE_RECT = (MODULE_CONN[0] - MODULE_SIZE[0] / 2, MODULE_CONN[1] - MODULE_SIZE[1] / 2,
               MODULE_CONN[0] + MODULE_SIZE[0] / 2, MODULE_CONN[1] + MODULE_SIZE[1] / 2)  # x0, y0, x1, y1
MODULE_CONN_ROT = 0.0
# A PCB tongue from the tab under the pad's well, carrying its FFC connector J5
# right under the pad's own connector. It stays inside the pad's footprint.
PAD_TONGUE = (INNER_X[1], -16.5, INNER_X[1] + 20.5, -8.0)

# Satellite only: the mouse column, in the inner column (Corne frame), in line
# with column 5's rows: M1 (right click) beside T, M0 (left click) beside G, and
# a rotary encoder with a knob beside B. The encoder is a Bourns
# PEC12R-4220F-N0024 (upright, 20 mm shaft, 24 detents, no push switch); its
# 12.4 x 13.4 mm body sits in a normal 14 mm switch cutout in the plate. Heights
# above the PCB top, from Bourns' drawing: body 5.1 mm, a ~7 mm collar to
# 10.1 mm, the 6 mm D-flat from 13.0 mm to the shaft end at 20.0 mm.
MOUSE_X = _COLUMNS[5][0] + U
MOUSE_KEYS = (("M0", 1), ("M1", 0))  # (name, row beside column 5)
ENCODER_ROW = 2
ENCODER = (MOUSE_X, _COLUMNS[5][1][ENCODER_ROW])  # shaft centre
ENCODER_SHAFT = 20.0            # shaft top above the PCB top
ENCODER_COLLAR = 10.1           # top of the collar round the shaft: a plain knob can't go lower
# Knob: 16 mm across, 11.5 mm tall, its top 2 mm above the shaft end, so its
# underside clears the collar by 0.4 mm and its D-bore (>= 9.5 mm deep) grips
# the whole flat. A taller knob needs a recess of >= 7.5 mm under it for the collar.
KNOB_D, KNOB_H = 16.0, 11.5


def _c(x: float, y: float) -> tuple[float, float]:
    return x + ORIGIN[0], y + ORIGIN[1]


def left_keys() -> list[Key]:
    """The Corne's 21 keys, left-half frame."""
    keys = []
    for col, (cx, ys) in enumerate(_COLUMNS):
        for row, cy in enumerate(ys):
            x, y = _c(cx, cy)
            keys.append(Key(f"C{col}R{row}", col, row, x, y, 0.0))
    for i, (tx, ty, rot, w) in enumerate(_THUMBS):
        x, y = _c(tx, ty)
        keys.append(Key(f"T{i}", 6, 3 + i, x, y, rot, w))
    return keys


def mouse_keys() -> list[Key]:
    """The satellite's two mouse-button keys, left-half frame."""
    return [Key(name, 7, row, *_c(MOUSE_X, _COLUMNS[5][1][row]), 0.0) for name, row in MOUSE_KEYS]


def all_keys() -> list[Key]:
    """Every key position of either half, left-half frame (circuits number them in this order)."""
    return left_keys() + mouse_keys()


def frame_keys(side: str) -> list[Key]:
    """The keys of ``side``, drawn in the left-half frame."""
    return left_keys() + (mouse_keys() if side == SATELLITE_SIDE else [])


def mirror_point(x: float, y: float) -> tuple[float, float]:
    return MIRROR_X - x, y


def keys_for(side: str) -> list[Key]:
    keys = frame_keys(side)
    if side == "left":
        return keys
    return [replace(k, x=mirror_point(k.x, k.y)[0], rot=-k.rot) for k in keys]


def encoder_placement(side: str) -> tuple[float, float, float]:
    """Board (x, y, rotation) of the encoder footprint (origin = pin A, shaft 7.5, 2.5 from it)."""
    x, y = _c(*ENCODER)
    if side == "left":
        return x - 7.5, y - 2.5, 0.0
    return mirror_point(x, y)[0] + 7.5, y + 2.5, 180.0


def encoder_cell_left() -> Polygon:
    """Satellite: the encoder's key-sized cell (PCB, plate and case opening), left-half frame."""
    x, y = ENCODER
    return _box(x - U / 2 - EDGE_MARGIN, y - U / 2 - EDGE_MARGIN, x + U / 2 + EDGE_MARGIN, y + U / 2 + EDGE_MARGIN)


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


def _box(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """Corne-frame rectangle -> left-half board polygon."""
    (ax, ay), (bx, by) = _c(x0, y0), _c(x1, y1)
    return box(ax, ay, bx, by)


def inner_tab_left() -> Polygon:
    return _box(INNER_X[0] - 1.0, INNER_TOP, INNER_X[1], TAB_BOTTOM)


def bay_left() -> Polygon:
    """Area reserved for the VGA daughterboard (no PCB, no plate)."""
    return _box(*BAY)


def inner_column(side: str) -> Polygon:
    """Bay + tab + the solid part below: the case's inner side follows this."""
    r = _box(INNER_X[0], BAY[1], INNER_X[1], INNER_BOTTOM)
    return mirror(r) if side == "right" else r


def bay(side: str) -> Polygon:
    return mirror(bay_left()) if side == "right" else bay_left()


def frame_outline(side: str, with_tab: bool = True) -> Polygon:
    """``pcb_outline`` of ``side`` before mirroring (left-half frame)."""
    cells = [k.cell(EDGE_MARGIN) for k in frame_keys(side)]
    extra = [inner_tab_left()] if with_tab else []
    if side == SATELLITE_SIDE:
        extra.append(encoder_cell_left())
    if with_tab and side == MAIN_SIDE:
        extra += [_box(*USB_EAR), _box(*PAD_TONGUE)]
    shape = _smooth(unary_union(cells + extra))
    # Closing grows into the daughterboard bay; cut it back out, then give the
    # bay's inside corners a router-friendly radius.
    shape = shape.difference(bay_left())
    shape = shape.buffer(0.8, join_style="round").buffer(-0.8, join_style="round")
    if not isinstance(shape, Polygon):
        shape = max(shape.geoms, key=lambda g: g.area)
    return shape


def pcb_outline(side: str, with_tab: bool = True) -> Polygon:
    shape = frame_outline(side, with_tab)
    return mirror(shape) if side == "right" else shape


def plate_outline(side: str) -> Polygon:
    """Like the PCB, minus the tab and ears (the trackpad sits over the main half's tab)."""
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


# Satellite only: the mouse column's plate would otherwise hang 20 mm off column 5.
_MOUSE_STANDOFFS = [
    (MOUSE_X - U / 2, 19.05),  # between G, B, M0 and the encoder
]


def standoffs(side: str) -> list[tuple[float, float]]:
    pts = [_c(x, y) for x, y in _STANDOFFS + (_MOUSE_STANDOFFS if side == SATELLITE_SIDE else [])]
    return pts if side == "left" else [mirror_point(x, y) for x, y in pts]


# Tripod / Arca mounts (Corne frame): two 1/4"-20 sockets per half in the floor,
# each in a boss that rises under the PCB, so they sit where the PCB's
# underside is clear: in the column gap nearest the half's centre of mass, one
# between rows 0 and 1 and one between row 2 and the thumb keys. 38 mm apart,
# inside the 28-40 mm range of Arca-Swiss's adjustable two-screw plates.
MOUNT_BOSS = 15.4  # a 1/4"-20 heat-set insert (8.7 mm) needs 3.3 mm of wall
_MOUNTS = {
    SATELLITE_SIDE: [(-61.9125, -3.571875), (-61.9125, 35.0)],   # col3/col4
    MAIN_SIDE: [(-42.8625, -1.2), (-42.8625, 37.0)],              # col4/col5: the trackpad pulls the centre of mass in
}


def mounts(side: str) -> list[tuple[float, float]]:
    pts = [_c(x, y) for x, y in _MOUNTS[side]]
    return pts if side == "left" else [mirror_point(x, y) for x, y in pts]


# Anchor points for the analog muxes (Corne frame), roughly one per column pair
# (circuits.MUX_KEYS): A = col0, col1, top of col2; B = rest of col2, col3,
# col4, T0; C = col5, T1, T2 and the satellite's mouse column.
MUX_ANCHORS = {
    "A": (-109.5375, 2.38125),
    "B": (-71.4375, 14.2875),
    "C": (-33.3375, 19.05),
}
USB_ANCHOR = (USB_X, BACK)                # back edge of the USB ear (USB-C on B.Cu), main half
LINK_ANCHOR = (-14.0, INNER_TOP + 3.1)    # JST-SH link on B.Cu at the tab's top edge, facing the bay
TAB_ANCHOR = (-14.0, -8.0)                # middle of the tab, for support parts


def anchor(name: str, side: str) -> tuple[float, float]:
    table = {"MODULE_CONN": MODULE_CONN, "USB": USB_ANCHOR, "LINK": LINK_ANCHOR, "TAB": TAB_ANCHOR,
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
