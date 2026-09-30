"""Build starting-point KiCad PCBs from the circuits.

Switches, sensors, per-key capacitors, muxes, the MCU, connectors and
standoffs are placed deterministically from :mod:`geometry`; remaining support
parts are auto-placed near their functional anchor, avoiding everything else.
Nets and schematic links (footprint paths) are assigned so that KiCad's
"Update PCB from Schematic" keeps working once you start routing.

Routing is intentionally left to a human (or Freerouting).
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from . import geometry as geo
from .trackpad import MODEL as PAD
from .circuits import MUX_REFS, key_index
from .schematic import Circuit, symbol_uuid

STOCK_FP = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
LOCAL_FP = Path(__file__).resolve().parent.parent / "lib"


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def vec(x: float, y: float):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def _fp_path(lib: str) -> str:
    local = LOCAL_FP / f"{lib}.pretty"
    return str(local if local.exists() else STOCK_FP / f"{lib}.pretty")


def netlist_pins(sch: Path) -> dict[tuple[str, str], str]:
    """(ref, pad) -> net name, exactly as KiCad names them (incl. unconnected-(...))."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "net.xml"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
                        "-o", str(out), str(sch)], check=True, capture_output=True)
        root = ET.parse(out).getroot()
    def internal(name: str) -> str:
        # The XML export un-escapes "/" inside pin names; KiCad's own net names keep {slash}.
        if name.startswith("unconnected-("):
            return "unconnected-(" + name[len("unconnected-("):].replace("/", "{slash}")
        return name

    return {(n.get("ref"), n.get("pin")): internal(net.get("name"))
            for net in root.iter("net") for n in net.iter("node")}


class Builder:
    def __init__(self, circuit: Circuit, side: str, outline: Polygon, pcb_path: Path,
                 has_keys: bool = True, layers: int = 2, thickness: float = 1.6):
        self.c = circuit
        self.pin_nets = netlist_pins(pcb_path.with_suffix(".kicad_sch"))
        self.has_keys = has_keys
        self.side = side
        self.outline = outline
        self.board = pcbnew.NewBoard(str(pcb_path))
        self.board.GetDesignSettings().SetCopperLayerCount(layers)
        self.board.GetDesignSettings().SetBoardThickness(mm(thickness))
        self.nets: dict[str, pcbnew.NETINFO_ITEM] = {}
        self.fps: dict[str, pcbnew.FOOTPRINT] = {}
        self.occupied = {"F": [], "B": []}
        self.inside = outline.buffer(-0.4)
        self._load_all()

    # -- footprints -----------------------------------------------------------
    def net(self, name: str):
        if name not in self.nets:
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.nets[name] = item
        return self.nets[name]

    def _load_all(self) -> None:
        from . import symlib
        for part in self.c.parts:
            lib, name = part.footprint.split(":", 1)
            fp = pcbnew.FootprintLoad(_fp_path(lib), name)
            if fp is None:
                raise FileNotFoundError(part.footprint)
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            fp.SetReference(part.ref)
            fp.SetValue(part.value)
            fp.SetPath(pcbnew.KIID_PATH(f"/{symbol_uuid(self.c, part.ref)}"))
            for setter, val in (("SetSheetfile", f"{self.c.name}.kicad_sch"), ("SetSheetname", "")):
                if hasattr(fp, setter):
                    getattr(fp, setter)(val)
            if part.dnp:
                fp.SetDNP(True)
            sym = symlib.load(part.lib_id)
            ds = sym.properties.get("Datasheet") or ""
            fp.SetField("Datasheet", "" if ds == "~" else ds)
            fp.SetField("Description", part.description or sym.properties.get("Description", ""))
            for k, v in part.fields.items():
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)  # MPN, tolerance: BOM data, not silkscreen
            for pad in fp.Pads():
                n = self.pin_nets.get((part.ref, pad.GetNumber()))
                if n is not None:
                    pad.SetNet(self.net(n))
            self.board.Add(fp)
            self.fps[part.ref] = fp

    def put(self, ref: str, x: float, y: float, rot: float, layer: str = "B",
            mirror: bool = True) -> pcbnew.FOOTPRINT:
        """Place ``ref``. Coordinates are left-half frame unless ``mirror`` is False."""
        if mirror:
            x, y, rot = geo.place(self.side, x, y, rot)
        fp = self.fps[ref]
        fp.SetPosition(vec(x, y))
        if layer == "B" and fp.GetLayer() == pcbnew.F_Cu:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        self.occupied[layer].append((ref, self.poly(fp, layer)))
        return fp

    def poly(self, fp, layer: str, grow: float = 0.0) -> Polygon:
        fp.BuildCourtyardCaches()
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if layer == "B" else pcbnew.F_CrtYd)
        if cy.OutlineCount() == 0:
            bb = fp.GetBoundingBox(False)
        else:
            bb = cy.BBox()
        p = box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
        return p.buffer(grow, join_style="mitre") if grow else p

    def face(self, ref: str, x: float, y: float, direction: tuple[float, float], layer="B",
             mirror=True) -> None:
        """Place a connector so its mouth points along ``direction`` (left-half frame)."""
        if mirror and self.side == "right":
            direction = (-direction[0], direction[1])
            x, y = geo.mirror_point(x, y)
        fp = self.fps[ref]
        best = None
        for rot in (0, 90, 180, 270):
            fp.SetPosition(vec(x, y))
            if layer == "B" and fp.GetLayer() == pcbnew.F_Cu:
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(rot)
            m = self._mouth(fp, layer)
            score = m[0] * direction[0] + m[1] * direction[1]
            if best is None or score > best[0]:
                best = (score, rot)
        fp.SetOrientationDegrees(best[1])
        self.occupied[layer].append((ref, self.poly(fp, layer)))

    def _mouth(self, fp, layer) -> tuple[float, float]:
        pads = [p for p in fp.Pads() if p.GetNumber() not in ("", "SH", "MP")]
        px = sum(pcbnew.ToMM(p.GetPosition().x) for p in pads) / len(pads)
        py = sum(pcbnew.ToMM(p.GetPosition().y) for p in pads) / len(pads)
        c = self.poly(fp, layer).centroid
        dx, dy = c.x - px, c.y - py
        n = math.hypot(dx, dy) or 1
        return dx / n, dy / n

    def keepouts(self) -> list[Polygon]:
        if not self.has_keys:
            return []
        k = geo.sensor_keepouts(self.side)
        k += [Point(x, y).buffer(2.6) for x, y in geo.standoffs(self.side)]
        return k

    def autoplace(self, ref: str, near: tuple[float, float], rot: float = 0.0, layer="B",
                  max_r: float = 30.0, mirror=True, avoid=None) -> None:
        if mirror:
            near = geo.mirror_point(*near) if self.side == "right" else near
            rot = -rot if self.side == "right" else rot
        fp = self.fps[ref]
        blocked = unary_union([p for _, p in self.occupied[layer]] + self.keepouts()
                              + list(avoid or []))
        step = 0.5
        r = 0.0
        while r <= max_r:
            n = max(1, int(2 * math.pi * r / step))
            for i in range(n):
                a = 2 * math.pi * i / n
                x, y = near[0] + r * math.cos(a), near[1] + r * math.sin(a)
                for ro in (rot, rot + 90):
                    fp.SetPosition(vec(x, y))
                    if layer == "B" and fp.GetLayer() == pcbnew.F_Cu:
                        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                    fp.SetOrientationDegrees(ro)
                    p = self.poly(fp, layer, grow=0.15)
                    if self.inside.contains(p) and not p.intersects(blocked):
                        self.occupied[layer].append((ref, self.poly(fp, layer)))
                        return
            r += step
        raise RuntimeError(f"could not place {ref} near {near}")

    # -- board ----------------------------------------------------------------
    def edge(self, poly: Polygon) -> None:
        rings = [poly.exterior, *poly.interiors]
        for ring in rings:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                s = pcbnew.PCB_SHAPE(self.board)
                s.SetShape(pcbnew.SHAPE_T_SEGMENT)
                s.SetStart(vec(*a))
                s.SetEnd(vec(*b))
                s.SetLayer(pcbnew.Edge_Cuts)
                s.SetWidth(mm(0.1))
                self.board.Add(s)

    def ground_zones(self, poly: Polygon, planes: dict | None = None) -> None:
        """GND pours on both outer layers, plus any inner planes ({layer: net})."""
        for layer, net in [(pcbnew.F_Cu, "GND"), (pcbnew.B_Cu, "GND"), *(planes or {}).items()]:
            z = pcbnew.ZONE(self.board)
            z.SetLayer(layer)
            z.SetNet(self.net(net))
            z.SetLocalClearance(mm(0.25))
            z.SetMinThickness(mm(0.2))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            ol = z.Outline()
            ol.NewOutline()
            for x, y in list(poly.exterior.coords)[:-1]:
                ol.Append(mm(x), mm(y))
            self.board.Add(z)

    def text(self, s: str, x: float, y: float, layer=pcbnew.B_SilkS, size=1.2) -> None:
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetPosition(vec(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(size * 0.15))
        if layer in (pcbnew.B_SilkS, pcbnew.B_Fab):
            t.SetMirrored(True)
        self.board.Add(t)

    def save(self, path: Path) -> None:
        # Bottom silk is hidden inside the case; keep it for ICs/connectors only.
        for ref, fp in self.fps.items():
            if ref[0] in "RC" and ref[1:].isdigit():
                fp.Reference().SetVisible(False)
        self.board.Save(str(path))


# ---------------------------------------------------------------------------
# Shared placements
# ---------------------------------------------------------------------------

def place_keys(b: Builder) -> None:
    """Switch pegs on F.Cu; sensor, its two caps and output resistor on B.Cu under the switch centre.

    The sensor/cap arrangement matches the proven HE60 layout; the output
    resistor sits in line below the output cap.
    """
    for key in geo.keys_for(b.side):
        n = key_index(key.name)
        b.put(f"SW{n}", key.x, key.y, key.rot, "F", mirror=False)
        b.put(f"HE{n}", key.x, key.y, key.rot - 90, "B", mirror=False)
        x, y = key.local(-2.6, -0.8)
        b.put(f"C{100 + n}", x, y, key.rot - 90, "B", mirror=False)
        x, y = key.local(2.6, -0.8)
        b.put(f"C{200 + n}", x, y, key.rot + 90, "B", mirror=False)
        x, y = key.local(2.6, 1.35)
        b.put(f"R{300 + n}", x, y, key.rot + 90, "B", mirror=False)
        for ref in (f"HE{n}", f"C{100 + n}", f"R{300 + n}", f"C{200 + n}"):
            b.fps[ref].Reference().SetVisible(False)


def switch_bodies(b: Builder) -> list[Polygon]:
    return [k.square(15.0) for k in geo.keys_for(b.side)]


def place_muxes(b: Builder) -> None:
    for i, (mux, ref) in enumerate(MUX_REFS.items()):
        x, y = geo.anchor(f"MUX_{mux}", "left")
        b.put(ref, x, y, -90, "B")
        b.autoplace(f"C{31 + i}", (x + 3.6, y), 90)


def place_standoffs(b: Builder) -> None:
    for i, (x, y) in enumerate(geo.standoffs(b.side)):
        b.put(f"H{i + 1}", x, y, 0, "F", mirror=False)


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

def build_main(c: Circuit, pcb_path: Path) -> Builder:
    b = Builder(c, geo.MAIN_SIDE, geo.pcb_outline(geo.MAIN_SIDE), pcb_path)
    place_keys(b)
    place_standoffs(b)
    place_muxes(b)

    # USB-C on the ear behind column 4, J3 at the top of the tab: both face the back wall.
    # The footprint's body front is 3.65 mm from its origin; HRO's drawing puts
    # it USB_OVERHANG past the board edge.
    ux, uy = geo.anchor("USB", "left")
    b.face("J1", ux, uy + 3.65 - geo.USB_OVERHANG, (0, -1))
    lx, ly = geo.anchor("LINK", "left")
    b.face("J3", lx, ly, (0, -1))
    # Landing pads for the castellated MCU module, on top of the tab under the
    # trackpad; nothing else goes on top there.
    mx, my = geo.anchor("MODULE_CONN", "left")
    b.put("J4", mx, my, geo.MODULE_CONN_ROT, "F")
    b.occupied["F"].append(("module", geo.module_rect(b.side)))
    tx, ty = geo.anchor("TAB", "left")
    # Tag-Connect guide pins poke through the board: keep them out from under switches
    # and the soldered-down module.
    b.autoplace("J2", (tx - 3, ty + 2), 0, max_r=24,
                avoid=switch_bodies(b) + [b.poly(b.fps["J4"], "F", grow=0.5)])

    # USB input on the ear, spilling under column 4; regulators under the tab,
    # module decoupling right under the module.
    for ref, rot in (("U4", 0), ("R1", 90), ("R2", 90), ("F1", 0), ("C1", 0)):
        b.autoplace(ref, (ux, uy + 9), rot, max_r=26)
    for ref in ("U2", "U3", "C2", "C3", "C4", "C5"):
        b.autoplace(ref, (tx + 2, ty), 0, max_r=26)
    for ref in ("C9", "C10"):
        b.autoplace(ref, (mx, my), 0, max_r=20)
    for ref in ("SW22", "SW23"):
        b.autoplace(ref, (tx - 12, ty + 5), 0, max_r=24)
    # Link: between the JST and the module socket.
    for ref in ("U8", "C18", "D1", "C15", "U6", "U7"):
        b.autoplace(ref, (lx - 4, ly + 3), 0, max_r=26)
    for ref in ("R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "R16",
                "R17", "R18"):
        b.autoplace(ref, (lx - 9, ly + 6), 90, max_r=26)
    # Trackpad FFC connector on top of the board, under the pad's well, its mouth
    # toward the pad's own connector; the pull-ups beside it.
    fx, fy = geo.corne(*PAD.fpc)
    b.face("J5", fx, fy, PAD.fpc_mouth, layer="F")
    for ref, rot in (("R19", 90), ("R20", 90), ("C16", 0), ("C17", 0)):
        if ref in b.fps:
            b.autoplace(ref, (fx, fy), rot, max_r=20)

    outline = b.outline
    b.edge(outline)
    b.ground_zones(outline)
    # Strip between the middle column's bottom key and T0: visible between keycaps.
    b.text(f"VGACorne  {b.side}  rev {c.rev}", *geo.place(b.side, *geo.corne(-64.0, 35.7))[:2],
           pcbnew.F_SilkS, size=0.9)
    return b


def build_satellite(c: Circuit, pcb_path: Path) -> Builder:
    b = Builder(c, geo.SATELLITE_SIDE, geo.pcb_outline(geo.SATELLITE_SIDE), pcb_path)
    place_keys(b)
    place_standoffs(b)
    place_muxes(b)

    lx, ly = geo.anchor("LINK", "left")
    b.face("J3", lx, ly, (0, -1))
    # Rotary encoder on top of the mouse column's bottom cell, through the plate
    # like a switch; its legs come through, so keep the underside clear there too.
    ex, ey, erot = geo.encoder_placement(b.side)
    b.put("ENC1", ex, ey, erot, "F", mirror=False)
    b.occupied["B"] += [("ENC1", box(pcbnew.ToMM(p.GetBoundingBox().GetX()), pcbnew.ToMM(p.GetBoundingBox().GetY()),
                                     pcbnew.ToMM(p.GetBoundingBox().GetRight()),
                                     pcbnew.ToMM(p.GetBoundingBox().GetBottom())).buffer(0.5))
                        for p in b.fps["ENC1"].Pads()]
    for ref in ("R21", "R22", "R23", "R24", "C5"):
        b.autoplace(ref, (ex, ey), 90, max_r=20, mirror=False)
    b.autoplace("R17", (lx, ly + 5), 0, max_r=15)
    for ref in ("U6", "U7"):
        b.autoplace(ref, (lx, ly + 6), 0, max_r=20)
    tx, ty = geo.anchor("TAB", "left")
    b.autoplace("U5", (tx, ty), 0, max_r=24)
    for ref in ("R1", "R2", "R3", "C4"):
        b.autoplace(ref, (tx, ty), 90, max_r=24)
    for ref in ("U2", "C1", "C2", "C3"):
        b.autoplace(ref, (tx - 4, ty + 5), 0, max_r=26)

    b.edge(b.outline)
    b.ground_zones(b.outline)
    b.text(f"VGACorne  {b.side}  rev {c.rev}", *geo.place(b.side, *geo.corne(-64.0, 35.7))[:2],
           pcbnew.F_SilkS, size=0.9)
    return b


# Daughterboard: stands vertically against the case wall. Its height is capped
# by the case's internal height (see mechanical.STACK).
LINK_W, LINK_H = 33.0, 13.0
DSUB_CENTRE = (-4.315, 1.98)  # connector centre relative to pin 1


def link_outline(x0=100.0, y0=100.0) -> Polygon:
    cx, cy = x0 + DSUB_CENTRE[0], y0 + DSUB_CENTRE[1]
    return box(cx - LINK_W / 2, cy - LINK_H / 2, cx + LINK_W / 2, cy + LINK_H / 2).buffer(
        -1.0).buffer(1.0)


def build_link(c: Circuit, pcb_path: Path) -> Builder:
    outline = link_outline()
    b = Builder(c, "left", outline, pcb_path, has_keys=False)
    b.put("J1", 100, 100, 0, "F", mirror=False)
    # The connector's THT pins and board locks come through to the back.
    pins = [box(pcbnew.ToMM(p.GetPosition().x) - 1.3, pcbnew.ToMM(p.GetPosition().y) - 1.3,
                pcbnew.ToMM(p.GetPosition().x) + 1.3, pcbnew.ToMM(p.GetPosition().y) + 1.3)
            for p in b.fps["J1"].Pads()]
    b.occupied["B"] += [("J1", g) for g in pins]
    cx, cy = 100 + DSUB_CENTRE[0], 100 + DSUB_CENTRE[1]
    # Pigtail pads along the top edge, leaving a via channel above the DE-15's pins.
    b.put("J2", cx, cy - LINK_H / 2 + 1.45, 0, "B", mirror=False)
    # Both cable-variant jumpers need pins 9 and 15: side by side under the
    # connector's left end, with +5V_LINK's cap beside them.
    y = cy + LINK_H / 2 - 1.55
    b.put("JP1", cx - 7.9, y, 0, "B", mirror=False)
    b.put("JP2", cx - 3.05, y, 0, "B", mirror=False)
    b.put("C1", cx + 0.9, y, 0, "B", mirror=False)
    b.edge(outline)
    b.ground_zones(outline)
    b.text("VGACorne", cx + 13.0, cy - LINK_H / 2 + 1.6, pcbnew.B_SilkS, size=0.8)
    return b


def place_beside_pins(b: Builder, cx: float, cy: float) -> None:
    """Put each MCU support part just outside the LQFP pin it serves.

    The crystal goes at the oscillator pins with its load caps beside its pads;
    parts on one MCU signal (reference resistor, boot and reset parts) at that
    pin; supply caps shared out over the supply pins of their rail, smallest
    value first, so each supply pin gets its own 100 nF.
    """
    u1 = b.fps["U1"]
    net_pads: dict[str, list] = {}
    for p in u1.Pads():
        net_pads.setdefault(p.GetNetname(), []).append(p)

    def outside(pad, dist=2.1):
        px, py = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
        dx, dy = px - cx, py - cy
        if abs(dx) > abs(dy):
            return px + math.copysign(dist, dx), py
        return px, py + math.copysign(dist, dy)

    def nets_of(ref):
        return [p.GetNetname() for p in b.fps[ref].Pads() if p.GetNetname() not in ("GND", "")]

    def value(ref):
        v = b.fps[ref].GetValue().lower().replace("u", "e-6").replace("n", "e-9").replace("p", "e-12")
        try:
            return float(v)
        except ValueError:
            return 0.0

    rest = [r for r in b.fps if r not in ("J1", "U1")]
    crystal = [r for r in rest if r.startswith("Y")]
    for ref in crystal:
        pads = [p for n in nets_of(ref) for p in net_pads.get(n, [])]
        x = sum(outside(p, 3.2)[0] for p in pads) / len(pads)
        y = sum(outside(p, 3.2)[1] for p in pads) / len(pads)
        b.autoplace(ref, (x, y), 0, layer="F", max_r=8, mirror=False)
    xpads = {p.GetNetname(): p for r in crystal for p in b.fps[r].Pads()}
    load = [r for r in rest if r not in crystal and any(n in xpads for n in nets_of(r))]
    for ref in load:
        p = xpads[next(n for n in nets_of(ref) if n in xpads)]
        b.autoplace(ref, (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)), 0,
                    layer="F", max_r=8, mirror=False)
    power = {"+3V3", "+3.3VA", "/VCAP"}
    single = [r for r in rest if r not in crystal + load and any(n not in power for n in nets_of(r))]
    for ref in single:
        pads = [p for n in nets_of(ref) if n not in power for p in net_pads.get(n, [])]
        target = outside(pads[0]) if pads else (cx, cy)
        b.autoplace(ref, target, 0, layer="F", max_r=10, mirror=False)
    used: dict[str, int] = {}
    for ref in sorted((r for r in rest if r not in crystal + load + single), key=value):
        pads = [p for n in nets_of(ref) for p in net_pads.get(n, [])]
        if not pads:
            b.autoplace(ref, (cx, cy), 0, layer="F", max_r=14, mirror=False)
            continue
        pad = min(pads, key=lambda p: (used.get(p.GetNumber(), 0), int(p.GetNumber())))
        used[pad.GetNumber()] = used.get(pad.GetNumber(), 0) + 1
        b.autoplace(ref, outside(pad), 0, layer="F", max_r=10, mirror=False)


def build_module(c: Circuit, pcb_path: Path) -> Builder:
    """MCU module, drawn in the carrier's coordinates so its edge pads land on J4.

    A castellated "stamp" module: soldered flat onto the main PCB, so every part
    is on top and the underside stays flat. It sits under the trackpad, which
    leaves 4.3 mm above the PCB (see mechanical.STACK).
    """
    side = geo.MAIN_SIDE
    outline = geo.module_rect(side).buffer(-0.5).buffer(0.5)
    b = Builder(c, side, outline, pcb_path, has_keys=False, layers=4, thickness=1.0)
    cx, cy, rot = geo.place(side, *geo.corne(*geo.MODULE_CONN), geo.MODULE_CONN_ROT)
    b.put("J1", cx, cy, rot, "F", mirror=False)  # same place and way round as J4 below it
    # J1's courtyard is two strips along the edges; its bounding box would block the lot.
    rows: dict[bool, list[Polygon]] = {}
    for p in b.fps["J1"].Pads():
        bb = p.GetBoundingBox()
        rows.setdefault(bb.GetY() < mm(cy), []).append(
            box(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
    b.occupied["F"] = [(r, g) for r, g in b.occupied["F"] if r != "J1"] + [
        ("J1", box(*unary_union(row).bounds).buffer(0.35, join_style="mitre")) for row in rows.values()]
    b.put("U1", cx, cy, 0, "F", mirror=False)
    place_beside_pins(b, cx, cy)
    b.edge(outline)
    # Four layers: solid GND and +3V3 planes under everything, so every cap and
    # supply pin drops a via and the signals route over unbroken ground.
    b.ground_zones(outline, planes={pcbnew.In1_Cu: "GND", pcbnew.In2_Cu: "+3V3"})
    # The chip's own marking names the module on top; label the flat underside too,
    # for telling them apart before soldering.
    b.text(c.part("U1").value, cx, cy, pcbnew.B_SilkS, size=1.2)
    return b


BUILDERS = {"main": build_main, "satellite": build_satellite, "link": build_link,
            "module_at32": build_module, "module_f446": build_module}
