#!/usr/bin/env python3
"""Renders of the assembled keyboard with Blender Cycles (the bpy module).

    .venv-render/bin/python hardware/render.py                  # every view -> docs/img/render-*.jpg
    .venv-render/bin/python hardware/render.py hero --samples 32 --scale 0.5   # quick look
    .venv-render/bin/python hardware/render.py --blend /tmp/vgacorne.blend     # also save the scene

bpy is only published for Python 3.13, so it gets its own venv next to the
KiCad one:

    uv venv --python 3.13 .venv-render
    uv pip install --python .venv-render/bin/python bpy shapely ezdxf

The case, plate, switch positions and ports come from vgacorne.geometry and
vgacorne.mechanical, so the renders follow layout changes. Keycaps, switches,
plugs, cables and the encoder knob are stand-in models.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy  # first: it provides bmesh and mathutils
import bmesh
from mathutils import Matrix, Vector
from shapely.geometry import Point, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vgacorne import geometry as geo  # noqa: E402
from vgacorne import mechanical as mech  # noqa: E402
from vgacorne.trackpad import MODEL as PAD  # noqa: E402

OUT = HERE.parent / "docs" / "img"
MM = 0.001  # Blender works in metres; everything below is in mm
ST = mech.STACK

GAP = 100.0     # between the two inner walls
SPLAY = 8.0     # each half turned this many degrees, tops inward
KEYCAP_Z = ST.plate_top + 7.0  # keycap skirt above the plate, MX stem at rest
VGA_Z = ST.floor + 7.0         # DE-15 shell centre (docs/mechanical.md)
USB_Z = mech.USB_Z             # USB-C centre above the case underside
CASE_EDGE_R = 1.2

# Cherry-like sculpt: (height at the dish edge, tilt in degrees; + faces the typist).
PROFILE = {0: (8.6, 6.0), 1: (7.5, 0.0), 2: (8.1, -6.0), 3: (7.8, 0.0), 4: (7.8, 0.0), 5: (7.8, 0.0)}
HOMING = {"C4R1"}  # F and J

COLOURS = {  # sRGB
    "case": "#3a3d42",     # space-grey anodised aluminium
    "etch": "#9a9ea4",
    "plate": "#b8bcc2",
    "cavity": "#141517",
    "switch": "#e8e6e1",
    "alpha": "#e6e1d6",    # PBT cream
    "mod": "#6b6e74",
    "accent": "#e0662a",
    "vga": "#00309e",      # classic VGA hood: PC99 blue (Pantone 661C), a touch brighter moulded
    "vga_knob": "#0a3cae",  # thumbscrew knobs come out a little lighter than the hood
    "nickel": "#c9ccd0",
    "plug": "#1b1c1e",
    "cable": "#1d1e20",     # black jackets and ferrites, even on blue-hooded cables
    "trackpad": "#232427",
    "desk": "#d4d0c8",
}


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def srgb(h: str) -> tuple[float, float, float]:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def material(name: str, colour: str, metallic: float = 0.0, rough: float = 0.5,
             grain: float = 0.0, **inputs) -> bpy.types.Material:
    """Principled BSDF; ``grain`` adds a fine bump (bead blast, PBT texture)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*srgb(colour), 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    for k, v in inputs.items():
        bsdf.inputs[k.replace("_", " ")].default_value = v
    if grain:
        coords = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 4000.0
        noise.inputs["Detail"].default_value = 2.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = grain
        bump.inputs["Distance"].default_value = 0.00002
        nt.links.new(coords.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def materials() -> dict[str, bpy.types.Material]:
    c = COLOURS
    return {
        "case": material("anodised", c["case"], metallic=1.0, rough=0.5, grain=0.15),
        "etch": material("etched", c["etch"], metallic=0.6, rough=0.6),
        "plate": material("plate", c["plate"], metallic=1.0, rough=0.3),
        "cavity": material("cavity", c["cavity"], rough=0.8),
        "switch": material("switch", c["switch"], rough=0.35),
        "alpha": material("pbt-alpha", c["alpha"], rough=0.55, grain=0.25),
        "mod": material("pbt-mod", c["mod"], rough=0.55, grain=0.25),
        "accent": material("pbt-accent", c["accent"], rough=0.55, grain=0.25),
        "vga": material("vga-blue", c["vga"], rough=0.38),
        "vga_knob": material("vga-knob", c["vga_knob"], rough=0.42),
        "nickel": material("nickel", c["nickel"], metallic=1.0, rough=0.22),
        "ferrite": material("ferrite", c["cable"], rough=0.45),
        "trackpad": material("trackpad", c["trackpad"], rough=0.7, grain=0.4),
        "trackpad_glass": material("trackpad-glass", "#161719", rough=0.38),  # etched (anti-glare) glass
        "plug": material("plug", c["plug"], rough=0.45),
        "cable": material("cable", c["cable"], rough=0.55),
        "desk": material("desk", c["desk"], rough=0.75),
    }


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------

def link(obj: bpy.types.Object, parent: bpy.types.Object | None = None) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def evaluated_mesh(obj: bpy.types.Object) -> bpy.types.Mesh:
    return bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))


def finish(me: bpy.types.Mesh, sharp_deg: float = 35.0) -> bpy.types.Mesh:
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(sharp_deg))
    return me


def mesh_object(name: str, me: bpy.types.Mesh, mat, parent=None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, me)
    if mat is not None and not me.materials:
        me.materials.append(mat)
    return link(obj, parent)


def _rings(geom):
    for p in getattr(geom, "geoms", [geom]):
        yield p.exterior.coords
        for h in p.interiors:
            yield h.coords


def slab(name: str, geom, z0: float, z1: float, r: float, xy, mat=None, parent=None) -> bpy.types.Object:
    """Extrude a shapely polygon (board mm) from z0 to z1 with edges rounded to ``r``."""
    if r:
        # A curve's bevel grows its outline by r, so start from the shrunk shape.
        geom = geom.buffer(-r, join_style="round", quad_segs=6)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = max((z1 - z0) / 2 - r, 0.0) * MM
    cu.bevel_depth = r * MM
    cu.bevel_resolution = 3
    for coords in _rings(geom):
        pts = list(coords)[:-1]
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for p, (x, y) in zip(sp.points, pts):
            p.co = (*xy(x, y), 0.0, 1.0)
        sp.use_cyclic_u = True
    tmp = link(bpy.data.objects.new(name, cu))
    me = finish(evaluated_mesh(tmp))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    obj = mesh_object(name, me, mat, parent)
    obj.location.z = (z0 + z1) / 2 * MM
    return obj


def superellipse(a: float, b: float, n: float, count: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def ring_mesh(name: str, rings: list[list[tuple[float, float, float]]], close_start=True,
              close_end=True, sharp_deg: float = 35.0) -> bpy.types.Mesh:
    """Skin consecutive rings (equal point counts); caps are n-gons."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    for a, b in zip(vs, vs[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if close_start:
        bm.faces.new(list(reversed(vs[0])))
    if close_end:
        bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return finish(me, sharp_deg)


def loft(name: str, sections, frame, count: int = 48) -> bpy.types.Mesh:
    """Superellipse sections ``(w, half_u, half_v, n)`` along an axis; ``frame(u, v, w)`` places them."""
    rings = [[frame(u, v, w) for u, v in superellipse(a, b, n, count)] for w, a, b, n in sections]
    return ring_mesh(name, rings)


def box_mesh(name: str, u0: float, u1: float, v0: float, v1: float, w0: float, w1: float, frame) -> bpy.types.Mesh:
    """Cuboid given in a part's (u, v, w) frame, e.g. a boolean cutter."""
    rings = [[frame(u, v, w) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))] for w in (w0, w1)]
    return ring_mesh(name, rings)


def cut(obj: bpy.types.Object, cutters: list[bpy.types.Object]) -> None:
    """Apply boolean differences to ``obj`` and delete the cutters."""
    for c in cutters:
        mod = obj.modifiers.new(c.name, "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = c
    me = evaluated_mesh(obj)
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for c in cutters:
        cm = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(cm)


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

_keycap_cache: dict = {}


def keycap_mesh(w_u: float, height: float, tilt: float, homing: bool) -> bpy.types.Mesh:
    key = (w_u, height, tilt, homing)
    if key in _keycap_cache:
        return _keycap_cache[key]
    N = 64
    bw, bd = w_u * geo.U - 0.9, geo.U - 0.9   # skirt
    tw, td = bw - 5.8, bd - 5.0               # top face
    d0, fillet = 0.6, 0.45
    R = ((12.5 / 2) ** 2 + d0 ** 2) / (2 * d0)  # cylindrical dish radius, 0.6 mm deep on a 1u
    tan_t = math.tan(math.radians(tilt))

    def top_z(x: float, y: float) -> float:
        return height - d0 + (R - math.sqrt(R * R - x * x)) + tan_t * y

    top = superellipse(tw / 2, td / 2, 4.5, N)
    rings = []
    for i in range(9):  # sides, slightly convex
        t = i / 8
        bulge = 0.25 * math.sin(math.pi * t)
        pts = superellipse(bw / 2 + (tw - bw) / 2 * t + bulge, bd / 2 + (td - bd) / 2 * t + bulge,
                           7.0 + (4.5 - 7.0) * t, N)
        rings.append([(x * MM, y * MM, t * (top_z(*top[k]) - fillet) * MM) for k, (x, y) in enumerate(pts)])
    for s, dz in ((0.985, 0.12), (0.965, 0.0), (0.9, 0), (0.75, 0), (0.55, 0), (0.35, 0), (0.15, 0)):
        rings.append([(s * x * MM, s * y * MM, (top_z(s * x, s * y) - dz) * MM) for x, y in top])
    me = ring_mesh("keycap", rings, close_end=True, sharp_deg=50)
    if homing:
        bm = bmesh.new()
        bm.from_mesh(me)
        y0 = -td / 2 + 2.6
        new = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)["verts"]
        for v in new:
            v.co = Vector((v.co.x * 2.6 * MM, (v.co.y * 0.55 + y0) * MM, (v.co.z * 0.4 + top_z(0, y0) - 0.05) * MM))
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
        bm.free()
    me.materials.append(None)  # one slot, filled per object
    _keycap_cache[key] = me
    return me


_switch_mesh = None


def switch_mesh() -> bpy.types.Mesh:
    global _switch_mesh
    if _switch_mesh is None:
        secs = [(0.0, 7.45, 7.45, 10), (0.7, 7.45, 7.45, 10), (6.0, 5.5, 6.0, 5)]
        _switch_mesh = loft("switch", secs, lambda u, v, w: (u * MM, v * MM, w * MM))
    return _switch_mesh


# ---------------------------------------------------------------------------
# One half
# ---------------------------------------------------------------------------

class Half:
    def __init__(self, side: str, mats):
        self.side, self.mats = side, mats
        self.layers = mech.case(side, floor_access=False)
        self.outer = self.layers["OUTER_WALL"][0]
        minx, miny, maxx, maxy = self.outer.bounds
        self.c = ((minx + maxx) / 2, (miny + maxy) / 2)
        self.inward = 1 if side == "left" else -1  # board +x points at the other half
        half_w = (maxx - minx) / 2
        self.root = link(bpy.data.objects.new(f"{side}_half", None))
        self.root.location = (-self.inward * (GAP / 2 + half_w) * MM, 0.0, 0.0)
        self.root.rotation_euler.z = -self.inward * math.radians(SPLAY)
        self.matrix = Matrix.Translation(self.root.location) @ Matrix.Rotation(self.root.rotation_euler.z, 4, "Z")

    def xy(self, x: float, y: float) -> tuple[float, float]:
        """Board mm (Y down) -> this half's local metres (Y up)."""
        return (x - self.c[0]) * MM, -(y - self.c[1]) * MM

    def world(self, x: float, y: float, z: float) -> Vector:
        return self.matrix @ Vector((*self.xy(x, y), z * MM))

    def world_dir(self, dx: float, dy: float) -> Vector:
        return (self.matrix.to_3x3() @ Vector((dx, -dy, 0.0))).normalized()

    # -- geometry ------------------------------------------------------------

    def port_face(self) -> float:
        """Board Y of the flat back face the connectors come out of."""
        return self.layers["DAUGHTERBOARD"][0].bounds[1] - mech.PORT_WALL

    def vga_x(self) -> float:
        x0, _, x1, _ = self.layers["DAUGHTERBOARD"][0].bounds
        return (x0 + x1) / 2

    # -- build ---------------------------------------------------------------

    def build(self) -> None:
        m, xy, root = self.mats, self.xy, self.root
        opening = mech.plate_outline(self.side).buffer(mech.WALL_CLEARANCE, join_style="round")
        case = slab(f"{self.side}_case", self.outer.difference(opening), 0.0, ST.case_height,
                    CASE_EDGE_R, xy, m["case"], root)
        self._cut_ports(case)
        slab(f"{self.side}_cavity", opening.buffer(0.3), ST.floor, ST.plate_bottom - 0.5, 0.0, xy, m["cavity"], root)

        outline, cutouts, holes = mech.plate(self.side)
        slab(f"{self.side}_plate", outline.difference(unary_union(cutouts + holes)),
             ST.plate_bottom, ST.plate_top, 0.25, xy, m["plate"], root)

        for k in geo.keys_for(self.side):
            x, y = xy(k.x, k.y)
            rot = math.radians(k.rot)
            sw = mesh_object(f"{self.side}_{k.name}_switch", switch_mesh(), m["switch"], root)
            sw.location = (x, y, ST.plate_top * MM)
            sw.rotation_euler.z = rot
            height, tilt = PROFILE[k.row]
            cap = mesh_object(f"{self.side}_{k.name}_cap", keycap_mesh(k.w, height, tilt, k.name in HOMING), None, root)
            cap.location = (x, y, KEYCAP_Z * MM)
            cap.rotation_euler.z = rot
            role = "accent" if k.name == "T2" else "mod" if k.col in (0, 7) or k.row >= 3 else "alpha"
            cap.material_slots[0].link = "OBJECT"  # the mesh is shared between keys
            cap.material_slots[0].material = m[role]

        for pad in self.layers.get("TRACKPAD", []):
            # Flat overlay, flush with the case top, in a counterbore with a hairline gap.
            top = ST.case_height
            slab(f"{self.side}_trackpad", PAD.top(self.side, -0.1), top - PAD.board_t,
                 top - 0.03, 0.3, xy, m["trackpad_glass" if PAD.gloss else "trackpad"], root)

        if self.side == geo.SATELLITE_SIDE:
            self._logo()
            self._knob()
        self._vga_plug()
        if self.side == geo.MAIN_SIDE:
            self._usb_plug()

    def _cut_ports(self, case: bpy.types.Object) -> None:
        """Booleans for the DE-15 and USB-C openings in the back face, and the tray/frame seam."""
        xy, root = self.xy, self.root
        vga, *usb = self.layers["PORTS"]
        cutters = [slab("cut_vga", vga, VGA_Z - 5.55, VGA_Z + 5.55, 0.0, xy, None, root)]
        for i, u in enumerate(usb):
            h = mech.USB_OPENING[1] / 2
            cutters.append(slab(f"cut_usb{i}", u, USB_Z - h, USB_Z + h, 1.0, xy, None, root))
        seam = self.outer.buffer(1.0).difference(self.outer.buffer(-0.35))
        cutters.append(slab("cut_seam", seam, ST.plate_bottom - 0.15, ST.plate_bottom + 0.15, 0.0, xy, None, root))
        for pad in self.layers.get("TRACKPAD", []):
            top = ST.case_height
            cutters.append(slab("cut_trackpad", pad, top - PAD.board_t, top + 1.0, 0.0, xy, None, root))
        cut(case, cutters)

    def _logo(self) -> None:
        """Etched wordmark on the roof over the VGA bay, between the keys and the ports."""
        x = self.vga_x()
        y = (self.port_face() + geo.corne(0, geo.INNER_TOP)[1]) / 2 - 0.5
        cu = bpy.data.curves.new("logo", "FONT")
        cu.body = "VGACORNE"
        cu.size = 3.6 * MM
        cu.space_character = 1.25
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        obj = link(bpy.data.objects.new("logo", cu), self.root)
        obj.location = (*self.xy(x, y), ST.case_height * MM + 1e-5)
        obj.active_material = self.mats["etch"]

    def _knob(self) -> None:
        """Aluminium knob on the rotary encoder's shaft (PEC12R-4220F: shaft top 20 mm above the PCB),
        over the encoder's body (flush with the plate top) and the collar round its shaft."""
        x, y = geo.corne(*geo.ENCODER)
        if self.side == "right":
            x, y = geo.mirror_point(x, y)
        pcb_top = ST.pcb_bottom + ST.pcb
        slab("encoder_body", box(x - 6.2, y - 6.7, x + 6.2, y + 6.7), pcb_top, pcb_top + 5.1, 0.3,
             self.xy, self.mats["plug"], self.root)
        slab("encoder_collar", Point(x, y).buffer(3.5, 48), pcb_top + 5.1, pcb_top + geo.ENCODER_COLLAR, 0.2,
             self.xy, self.mats["nickel"], self.root)
        top = pcb_top + geo.ENCODER_SHAFT + 2.0
        r, h = geo.KNOB_D / 2, geo.KNOB_H

        def frame(u, v, w):  # w: up from the knob's top face, downwards negative
            return (*self.xy(x + u, y + v), (top + w) * MM)

        secs = [(-h, r - 0.6, r - 0.6, 2), (-h + 0.6, r, r, 2), (-1.2, r, r, 2),
                (-0.3, r - 0.5, r - 0.5, 2), (0.0, r - 1.4, r - 1.4, 2)]
        mesh_object("knob", loft("knob", secs, frame, 96), self.mats["case"], self.root)

    def _vga_plug(self) -> None:
        """Classic blue moulded VGA plug, after the L-com CAD models and photos:
        a collar round the flange, a body with sleeves for the thumbscrews, grip
        grooves and the monitor icon on top, long fluted knobs, a slotted strain
        relief, then a black cable with a ferrite."""
        cx, y0 = self.vga_x(), self.port_face() - 0.3
        m, root = self.mats, self.root

        def at(du: float = 0.0):
            def frame(u, v, w):
                return (*self.xy(cx + du + u, y0 - w), (VGA_Z + v) * MM)
            return frame

        f = at()

        def part(name, mesh, mat):
            return mesh_object(f"{self.side}_{name}", mesh, mat, root)

        def box(name, u0, u1, v0, v1, w0, w1, frame=f):
            return part(name, box_mesh(name, u0, u1, v0, v1, w0, w1, frame), None)

        part("vga_collar", loft("collar", [(0.0, 17.05, 7.5, 10), (3.4, 17.05, 7.5, 10)], f), m["vga"])
        body = part("vga_body", loft("body", [(3.0, 11.0, 6.9, 5), (16.5, 11.0, 6.9, 5), (19.5, 9.4, 6.6, 4.5),
                                              (26.0, 6.6, 5.9, 3.5)], f), m["vga"])
        # Four grip grooves shortening with the taper, and the debossed monitor icon.
        grooves = [box(f"groove{i}", -hl, hl, top - 0.45, top + 2, w - 0.52, w + 0.52)
                   for i, (w, hl, top) in enumerate(((12.7, 7.3, 6.9), (15.1, 6.5, 6.9), (17.6, 5.6, 6.8),
                                                     (20.1, 4.8, 6.55)))]
        wc, hu, hw, g = 6.8, 3.8, 3.15, 0.6
        icon = [box("icon_l", -hu, -hu + g, 6.55, 9, wc - hw, wc + hw), box("icon_r", hu - g, hu, 6.55, 9, wc - hw, wc + hw),
                box("icon_f", -hu, hu, 6.55, 9, wc - hw, wc - hw + g), box("icon_b", -hu, hu, 6.55, 9, wc + hw - g, wc + hw)]
        cut(body, grooves + icon)
        relief = part("vga_relief", loft("relief", [(25.5, 6.35, 5.8, 2.6), (40.5, 4.7, 4.6, 2.2),
                                                    (41.2, 4.2, 4.1, 2)], f), m["vga"])
        slots = [box(f"slot{i}{s}", -4.0, 4.0, *((2.3, 8) if s > 0 else (-8, -2.3)), w - 0.5, w + 0.5)
                 for i, w in enumerate((28.3, 30.8, 33.3, 35.8, 38.3)) for s in (1, -1)]
        cut(relief, slots)
        part("vga_core", loft("core", [(26.0, 3.75, 3.75, 2), (41.5, 3.75, 3.75, 2)], f), m["cable"])  # seen through the slots
        for du in (-12.5, 12.5):
            g = at(du)
            part("vga_ear", loft("ear", [(3.0, 4.2, 4.2, 2), (16.4, 4.2, 4.2, 2), (17.2, 3.5, 3.5, 2)], g), m["vga"])
            part("vga_shaft", loft("shaft", [(16.8, 1.5, 1.5, 2), (19.0, 1.5, 1.5, 2)], g, 24), m["nickel"])
            # Knob: 24 fine flutes, chamfered ends, a screwdriver slot across the back.
            N = 96
            rings = []
            for w, r, flute in ((18.7, 3.4, 0.0), (19.3, 3.9, 0.12), (34.9, 3.9, 0.12), (35.3, 3.5, 0.0)):
                pts = []
                for k in range(N):
                    a = 2 * math.pi * k / N
                    rr = r - flute * (0.5 + 0.5 * math.cos(24 * a))
                    pts.append(g(rr * math.cos(a), rr * math.sin(a), w))
                rings.append(pts)
            knob = part("vga_knob", ring_mesh("knob", rings, sharp_deg=60), m["vga_knob"])
            cut(knob, [box("knob_slot", -4.5, 4.5, -0.5, 0.5, 32.3, 36.0, g)])
        # Black cable, dead straight through a ferrite ~4 cm back, which rests on the desk.
        w0, w1 = 41.2, 41.2 + 40.0 + 28.5
        slope = (8.9 - VGA_Z) / (w1 - w0)
        part("ferrite", loft("ferrite", [(w1 - 28.5, 7.0, 7.0, 2), (w1 - 27.3, 8.75, 8.75, 2), (w1 - 1.2, 8.75, 8.75, 2),
                                         (w1, 7.0, 7.0, 2)], lambda u, v, w: f(u, v + slope * (w - w0), w)),
             m["ferrite"])
        self.vga_end = self.world(cx, y0 - w0, VGA_Z)
        self.vga_ferrite = self.world(cx, y0 - w1 - 1.0, 8.9)
        self.vga_dir = self.world_dir(0.0, -1.0)

    def _usb_plug(self) -> None:
        ux, _ = geo.anchor("USB", self.side)
        # Fully seated, the overmould sits 0.45 mm in front of the receptacle face, inside the wall.
        y0 = geo.anchor("USB", self.side)[1] - geo.USB_OVERHANG - 0.45

        def frame(u, v, w):
            return (*self.xy(ux + u, y0 - w), (USB_Z + v) * MM)

        secs = [(0.0, 6.0, 3.2, 3), (16.0, 6.0, 3.2, 3), (19.0, 3.5, 2.6, 2.4), (24.0, 2.2, 2.2, 2)]
        mesh_object("usb_plug", loft("usb_plug", secs, frame), self.mats["plug"], self.root)
        self.usb_end = self.world(ux, y0 - 24.0, USB_Z)
        self.usb_dir = self.world_dir(0.0, -1.0)


def cable(name: str, pts: list[Vector], radius: float, mat, straight=None) -> bpy.types.Object:
    """Bezier cable; ``straight`` pins the tangent (a direction) at chosen points."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius * MM
    cu.bevel_resolution = 6
    cu.resolution_u = 32
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for i, (bp, p) in enumerate(zip(sp.bezier_points, pts)):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
        if straight and i in straight:
            d = straight[i].normalized() * 0.012
            bp.handle_left_type = bp.handle_right_type = "FREE"
            bp.handle_left, bp.handle_right = p - d, p + d
    obj = link(bpy.data.objects.new(name, cu))
    obj.active_material = mat
    return obj


def cables(left: Half, right: Half, mats) -> None:
    r = 3.75
    desk = r * MM
    # VGA: straight out of each plug through its ferrite, then down onto the desk
    # and a lazy U behind the gap.
    a, b = left.vga_ferrite, right.vga_ferrite
    back = max(a.y, b.y)
    pts = [left.vga_end, a, a + left.vga_dir * 0.02 + Vector((0.006, 0, 0)) + Vector((0, 0, desk - a.z)),
           Vector((0.0, back + 0.075, desk)),
           b + right.vga_dir * 0.02 + Vector((-0.006, 0, 0)) + Vector((0, 0, desk - b.z)), b, right.vga_end]
    straight = {0: left.vga_dir, 1: left.vga_dir, 5: -right.vga_dir, 6: -right.vga_dir}
    cable("vga_cable", pts, r, mats["cable"], straight)
    main = left if left.side == geo.MAIN_SIDE else right
    u, d = main.usb_end, main.usb_dir
    side = Vector((-main.inward * d.y, main.inward * d.x, 0.0))  # away from the VGA cable
    pts = [u, u + d * 0.025, u + d * 0.07 + side * 0.012 + Vector((0, 0, 2.0 * MM - u.z)),
           u + d * 0.25 + side * 0.09 + Vector((0, 0, 2.0 * MM - u.z)),
           u + d * 0.6 + side * 0.16 + Vector((0, 0, 2.0 * MM - u.z))]
    cable("usb_cable", pts, 2.0, mats["cable"])


# ---------------------------------------------------------------------------
# Scene, lights, cameras
# ---------------------------------------------------------------------------

def world() -> None:
    w = bpy.data.worlds.new("studio")
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    hdri = Path(bpy.utils.system_resource("DATAFILES", path="studiolights/world")) / "studio.exr"
    env.image = bpy.data.images.load(str(hdri))
    lit = nt.nodes.new("ShaderNodeBackground")
    lit.inputs["Strength"].default_value = 0.25
    seen = nt.nodes.new("ShaderNodeBackground")  # what the camera sees past the desk
    seen.inputs["Color"].default_value = (*srgb(COLOURS["desk"]), 1.0)
    seen.inputs["Strength"].default_value = 0.25
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs["Color"], lit.inputs["Color"])
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(lit.outputs["Background"], mix.inputs[1])
    nt.links.new(seen.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def aim(obj: bpy.types.Object, loc, target) -> None:
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def area_light(name: str, loc, power: float, size: float, target=(0, 0, 0)) -> None:
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = power
    ld.shape = "DISK"
    ld.size = size
    aim(link(bpy.data.objects.new(name, ld)), loc, target)


def lights() -> None:
    area_light("key", (-0.55, -0.45, 0.85), 45.0, 0.9)
    area_light("fill", (0.75, -0.35, 0.45), 12.0, 0.8)
    area_light("rim", (0.25, 0.85, 0.55), 35.0, 0.7)


def camera(name: str, loc, target, lens: float = 50.0, fstop: float | None = None,
           ortho: float | None = None) -> bpy.types.Object:
    cd = bpy.data.cameras.new(name)
    cd.clip_start, cd.clip_end = 0.01, 20.0
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    if fstop:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    obj = link(bpy.data.objects.new(name, cd))
    aim(obj, loc, target)
    return obj


def views(left: Half, right: Half) -> dict[str, tuple[bpy.types.Object, tuple[int, int]]]:
    main = left if left.side == geo.MAIN_SIDE else right
    port = main.vga_end - main.vga_dir * 0.02  # middle of the plug
    s = main.inward  # +x points from the main half towards the other half
    return {
        "hero": (camera("cam_hero", (0.0, -0.58, 0.33), (0.03, 0.035, 0.0), lens=44, fstop=11), (2400, 1350)),
        "top": (camera("cam_top", (0.025, 0.065, 1.0), (0.025, 0.065, 0.0), ortho=0.58), (2400, 1650)),
        # From behind the main half: DE-15 and USB-C side by side in the back face.
        "port": (camera("cam_port", port + Vector((0.07 * s, 0.135, 0.085)), port + Vector((-0.012 * s, 0.0, -0.002)),
                        lens=60, fstop=16.0), (1800, 1200)),
    }


def setup_render(samples: int, cpu: bool) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    if not cpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d in gpus
                scene.cycles.device = "GPU"
                break
    scene.render.use_persistent_data = True
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "JPEG"  # photo-like: a fraction of the PNG size
    scene.render.image_settings.quality = 90


def build() -> tuple[Half, Half]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials()
    halves = []
    for side in ("left", "right"):
        h = Half(side, mats)
        h.build()
        halves.append(h)
    left, right = halves
    cables(left, right, mats)
    desk = bpy.data.meshes.new("desk")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=2.0)
    bm.to_mesh(desk)
    bm.free()
    mesh_object("desk", desk, mats["desk"])
    world()
    lights()
    return left, right


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("views", nargs="*", choices=[[], "hero", "top", "port"], help="default: all")
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--scale", type=float, default=1.0, help="resolution scale")
    ap.add_argument("--out", type=Path, default=OUT, help="output directory")
    ap.add_argument("--blend", type=Path, help="also save the scene as a .blend")
    ap.add_argument("--cpu", action="store_true", help="render on the CPU")
    args = ap.parse_args()

    left, right = build()
    setup_render(args.samples, args.cpu)
    scene = bpy.context.scene
    cams = views(left, right)
    if args.blend:
        scene.camera = cams["hero"][0]
        args.blend.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.blend.resolve()))
        print(f"  wrote {args.blend}")
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.views or ["hero", "top", "port"]:
        cam, (w, h) = cams[name]
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = round(w * args.scale), round(h * args.scale)
        path = args.out / f"render-{name}.jpg"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
