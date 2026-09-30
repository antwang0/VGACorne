#!/usr/bin/env python3
"""Autoroute a KiCad board with Freerouting: DSN export -> Freerouting (headless) -> SES import -> zone refill.

    ../.venv/bin/python route.py <board.kicad_pcb> <out.kicad_pcb> [attempts]

Needs Java >= 25 and Freerouting 2.4 (FREEROUTING_JAR, default
~/.kicad-mcp/freerouting.jar). Work on a copy of the board's project folder and
copy the result back once `generate.py check` is happy with it.

Two phases first: the signals, with the ground pours as planes; then, with
those tracks locked and the pours off, GND as tracks, so no ground pad depends
on a pour the signals cut up. If that leaves anything unconnected (dense boards,
where small ground pads get boxed in), it also tries every net in one run and
keeps whichever connects more. Boards with inner planes: every
outer SMD pad on a plane net first gets its own via (fan-out), then one run
routes the signals over the planes. Each run tries Freerouting up to ``attempts``
times with different pass limits and keeps the best session. Finally, ground
stitching vias go wherever both layers are poured, and into every pour island.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

JAR = Path(os.environ.get("FREEROUTING_JAR", Path.home() / ".kicad-mcp" / "freerouting.jar"))
PASSES = [60, 100, 150, 80, 120, 200]


def freeroute(dsn: Path, ses: Path, passes: int) -> tuple[int, str]:
    r = subprocess.run(["java", "-jar", str(JAR), "--gui.enabled=false", "-de", str(dsn), "-do", str(ses),
                        "-mp", str(passes)], capture_output=True, text=True, timeout=3600)
    out = r.stdout + r.stderr
    done = [l for l in out.splitlines() if "Auto-routing stage completed" in l]
    m = re.search(r"\((\d+) unrouted", done[-1]) if done else None
    return (int(m.group(1)) if m else 10**6), (done[-1] if done else out[-500:])


def widen_for_edge_pads(board, text: str, margin: float = 1.0) -> str:
    """Castellated pads straddle the board edge, and Freerouting won't route to a
    pad outside its boundary. Grow the boundary to the board's bounding box plus
    ``margin`` and keep wires and vias out of the added strips."""
    edge = [p for fp in board.GetFootprints() for p in fp.Pads()
            if p.GetProperty() == pcbnew.PAD_PROP_CASTELLATED]
    if not edge:
        return text
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0 = pcbnew.ToMM(bb.GetX()) * 1000, pcbnew.ToMM(bb.GetY()) * 1000
    x1, y1 = pcbnew.ToMM(bb.GetRight()) * 1000, pcbnew.ToMM(bb.GetBottom()) * 1000
    m = margin * 1000
    X0, Y0, X1, Y1 = x0 - m, y0 - m, x1 + m, y1 + m
    # DSN coordinates are um with Y negated.
    rect = f"(boundary (rect pcb {X0:.0f} {-Y1:.0f} {X1:.0f} {-Y0:.0f}))"
    text, k = re.subn(r"\(boundary\s*\(path pcb 0[^)]*\)\s*\)", rect, text, count=1)
    if not k:
        sys.exit("no board boundary in the DSN")
    # Keep the 0.3 mm copper-to-edge clearance, except over the pad rows; beyond the
    # rows' ends, and 0.6 mm out past the pads (they reach 0.55 mm past the edge).
    e = 300
    px = [pcbnew.ToMM(p.GetPosition().x) * 1000 for p in edge]
    r0, r1 = min(px) - 1000, max(px) + 1000
    strips = [(X0, Y0, X1, y0 - 600), (X0, y1 + 600, X1, Y1), (X0, Y0, x0 + e, Y1), (x1 - e, Y0, X1, Y1),
              (X0, Y0, r0, y0 + e), (r1, Y0, X1, y0 + e), (X0, y1 - e, r0, Y1), (r1, y1 - e, X1, Y1)]
    keepouts = "".join(f"    (keepout (rect signal {a:.0f} {-d:.0f} {c:.0f} {-b:.0f}))\n" for a, b, c, d in strips)
    return text.replace(rect, rect + "\n" + keepouts, 1)


def run(board, tmp: Path, tag: str, attempts: int, ground_width_um: int | None = None) -> int:
    """Export, route best-of-``attempts``, import. Returns the unrouted count."""
    dsn, best = tmp / f"{tag}.dsn", tmp / f"{tag}.ses"
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        sys.exit("DSN export failed")
    text = widen_for_edge_pads(board, dsn.read_text())
    # Inner layers are planes: no signal tracks on them, only vias.
    text = re.sub(r"(\(layer In\d+\.Cu\s*\(type )signal", r"\1power", text)
    dsn.write_text(text)
    if ground_width_um:
        # Narrower ground tracks than the Power class's: they only have to join
        # pads the pours can't reach; the pours carry the current.
        text = dsn.read_text()
        text, k = re.subn(r"(\(class Power [^)]*?\bGND\b.*?\(width )\d+", rf"\g<1>{ground_width_um}", text,
                          count=1, flags=re.S)
        if not k:
            sys.exit("no Power class with GND in the DSN")
        dsn.write_text(text)
    best_n = None
    for i in range(attempts):
        ses = tmp / f"{tag}{i}.ses"
        n, line = freeroute(dsn, ses, PASSES[i % len(PASSES)])
        print(f"{tag} attempt {i + 1} ({PASSES[i % len(PASSES)]} passes): {n} unrouted")
        if ses.exists() and (best_n is None or n < best_n):
            best_n = n
            shutil.copy(ses, best)
        if n == 0:
            break
    if best_n is None or not pcbnew.ImportSpecctraSES(board, str(best)):
        sys.exit("routing/import failed")
    return best_n


def unconnected(path: Path) -> int:
    """KiCad's count of unconnected items (after a zone refill)."""
    with tempfile.TemporaryDirectory() as tmp:
        rpt = Path(tmp) / "drc.rpt"
        subprocess.run(["kicad-cli", "pcb", "drc", "--refill-zones", "--save-board", "-o", str(rpt), str(path)],
                       check=True, capture_output=True)
        m = re.search(r"Found (\d+) unconnected", rpt.read_text())
    return int(m.group(1)) if m else 10**6


def two_phase(board, tmp: Path, attempts: int) -> None:
    """Signals with the pours as planes, then GND as tracks round the locked signals."""
    run(board, tmp, "signals", attempts)
    tracks = board.Tracks()
    for i in range(tracks.size()):
        tracks[i].SetLocked(True)
    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    run(board, tmp, "ground", attempts, ground_width_um=250)
    tracks = board.Tracks()
    for i in range(tracks.size()):
        tracks[i].SetLocked(False)
    for z in zones:
        board.Add(z)


def all_at_once(board, tmp: Path, attempts: int) -> None:
    """Every net as tracks in one run (pours off), so ground gets its vias during fan-out."""
    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    run(board, tmp, "all", attempts)
    for z in zones:
        board.Add(z)


def fanout(board, via_d: float = 0.6, drill: float = 0.3, clearance: float = 0.15, width: float = 0.25) -> int:
    """Give every outer-layer SMD pad on a net with an inner plane its own via, on
    a short track clear of every other net's copper; where there's no room, join
    it to the nearest via of its net instead. Freerouting then only has to route
    the signals. Returns the number of pads connected."""
    import math
    from shapely.geometry import LineString, Point, box as sbox
    from shapely.ops import unary_union

    inner = {z.GetNetname() for z in board.Zones() if z.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu)}
    if not inner:
        return 0
    edge = board.GetBoardEdgesBoundingBox()  # includes half the edge line's width
    m = 0.3 + via_d / 2 + 0.15  # copper-to-edge clearance, via radius, margin
    inside = sbox(pcbnew.ToMM(edge.GetX()) + m, pcbnew.ToMM(edge.GetY()) + m,
                  pcbnew.ToMM(edge.GetRight()) - m, pcbnew.ToMM(edge.GetBottom()) - m)
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            shape = sbox(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()),
                         pcbnew.ToMM(bb.GetBottom()))
            pads.append((pad, fp, shape))
    placed = []  # (net, via Point, track LineString)
    count = 0

    def add(pad, net, c, v, new_via):
        if new_via:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(v.x), pcbnew.FromMM(v.y)))
            via.SetWidth(pcbnew.FromMM(via_d))
            via.SetDrill(pcbnew.FromMM(drill))
            via.SetNet(pad.GetNet())
            via.SetLocked(True)
            board.Add(via)
        seg = pcbnew.PCB_TRACK(board)
        seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(c.x), pcbnew.FromMM(c.y)))
        seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(v.x), pcbnew.FromMM(v.y)))
        seg.SetWidth(pcbnew.FromMM(width))
        seg.SetLayer(pad.GetLayer())
        seg.SetNet(pad.GetNet())
        seg.SetLocked(True)
        board.Add(seg)
        placed.append((net, v if new_via else None, LineString([(c.x, c.y), (v.x, v.y)])))

    todo = [x for x in pads if x[0].GetNetname() in inner and x[0].GetAttribute() == pcbnew.PAD_ATTRIB_SMD]

    def try_via(pad, fp, shape, dirs_n, steps) -> bool:
        net = pad.GetNetname()
        others = unary_union([s for p, _, s in pads if p.GetNetname() != net]
                             + [v.buffer(via_d / 2) for n, v, _ in placed if n != net and v is not None]
                             + [l.buffer(width / 2) for n, _, l in placed if n != net])
        holes = [v for _, v, _ in placed if v is not None]
        c = shape.centroid
        fc = Point(pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y))
        away = math.atan2(c.y - fc.y, c.x - fc.x) if c.distance(fc) > 1e-6 else 0.0
        dirs = [away] + [k * 2 * math.pi / dirs_n for k in range(dirs_n)]
        blocked = others.difference(shape.buffer(0.01))
        for step in steps:
            for ang in dirs:
                dx, dy = math.cos(ang), math.sin(ang)
                half = abs(dx) * (shape.bounds[2] - shape.bounds[0]) / 2 + abs(dy) * (shape.bounds[3] - shape.bounds[1]) / 2
                r = half + clearance + via_d / 2 + step
                v = Point(c.x + dx * r, c.y + dy * r)
                if (inside.contains(v) and not v.buffer(via_d / 2 + clearance).intersects(others)
                        and not LineString([(c.x, c.y), (v.x, v.y)]).buffer(width / 2 + clearance).intersects(blocked)
                        and all(v.distance(h) >= drill + 0.3 for h in holes)):
                    add(pad, net, c, v, True)
                    return True
        # No room for a via: join the nearest via of the same net.
        for v in sorted((v for n, v, _ in placed if n == net and v is not None), key=c.distance)[:4]:
            if c.distance(v) < 3.0 and not LineString([(c.x, c.y), (v.x, v.y)]).buffer(
                    width / 2 + clearance).intersects(blocked):
                add(pad, net, c, v, False)
                return True
        return False

    # First pass: the 4 axes and diagonals, close in. Then the rest, harder.
    left = []
    for x in todo:
        if try_via(*x, 8, (0.0, 0.3, 0.6, 1.0)):
            count += 1
        else:
            left.append(x)
    for x in left:
        count += try_via(*x, 16, (0.0, 0.2, 0.4, 0.7, 1.0, 1.5))
    return count


def planes(board, tmp: Path, attempts: int) -> None:
    """Boards with inner planes: route over them with the outer pours off, so every
    GND and supply pad reaches its plane with a via rather than through an outer
    pour the tracks may cut up."""
    print(f"fan-out: {fanout(board)} pads joined to the planes")
    outer = [z for z in board.Zones() if z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    for z in outer:
        board.Remove(z)
    run(board, tmp, "planes", attempts)
    tracks = board.Tracks()
    for i in range(tracks.size()):
        tracks[i].SetLocked(False)
    for z in outer:
        board.Add(z)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    attempts = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    results = []
    layers = pcbnew.LoadBoard(str(src)).GetCopperLayerCount()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for strategy in ((planes,) if layers > 2 else (two_phase, all_at_once)):
            board = pcbnew.LoadBoard(str(src))
            strategy(board, tmp, attempts)
            out = tmp / f"{strategy.__name__}.kicad_pcb"
            board.Save(str(out))
            n = unconnected(out)
            print(f"{strategy.__name__}: {n} unconnected")
            results.append((n, strategy.__name__, out))
            if n == 0:
                break
        n, name, out = min(results)
        shutil.copy(out, dst)
    print(f"routed -> {dst} ({name}, {n} unconnected); {stitch(dst)} ground stitching vias")


def _polys(shape_poly_set):
    from shapely.geometry import Polygon
    out = []
    for i in range(shape_poly_set.OutlineCount()):
        o = shape_poly_set.COutline(i)
        pts = [(pcbnew.ToMM(o.CPoint(j).x), pcbnew.ToMM(o.CPoint(j).y)) for j in range(o.PointCount())]
        holes = []
        for h in range(shape_poly_set.HoleCount(i)):
            hh = shape_poly_set.CHole(i, h)
            holes.append([(pcbnew.ToMM(hh.CPoint(j).x), pcbnew.ToMM(hh.CPoint(j).y)) for j in range(hh.PointCount())])
        if len(pts) >= 3:
            out.append(Polygon(pts, holes).buffer(0))
    return out


def stitch(path: Path, pitch: float = 2.5, via_d: float = 0.6, drill: float = 0.3) -> int:
    """Ground stitching vias wherever both layers' GND pours have room, plus one in
    every pour island, so no island hangs on a pad's spokes. Returns the count."""
    from shapely.geometry import Point
    from shapely.ops import unary_union

    board = pcbnew.LoadBoard(str(path))
    gnd = board.FindNet("GND")
    fills = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
    for z in board.Zones():
        if z.GetNetname() != "GND":
            continue
        for layer in fills:
            if z.IsOnLayer(layer):
                fills[layer] += _polys(z.GetFilledPolysList(layer))
    both = unary_union(fills[pcbnew.F_Cu]).intersection(unary_union(fills[pcbnew.B_Cu]))
    room = both.buffer(-(via_d / 2 + 0.05))
    bb = board.GetBoardEdgesBoundingBox()
    from shapely.geometry import box as sbox
    room = room.intersection(sbox(pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()),
                                  pcbnew.ToMM(bb.GetBottom())).buffer(-(0.3 + via_d / 2 + 0.15)))
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                holes.append((Point(pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)),
                              pcbnew.ToMM(max(pad.GetDrillSize().x, pad.GetDrillSize().y)) / 2))
    tracks = board.Tracks()
    for i in range(tracks.size()):
        if tracks[i].GetClass() == "PCB_VIA":
            v = tracks[i].Cast()
            holes.append((Point(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)),
                          pcbnew.ToMM(v.GetDrillValue()) / 2))
    placed = []

    def ok(pt):
        return (room.contains(pt)
                and all(pt.distance(c) >= r + drill / 2 + 0.3 for c, r in holes)
                and all(pt.distance(q) >= pitch * 0.8 for q in placed))

    x0, y0, x1, y1 = room.bounds if not room.is_empty else (0, 0, 0, 0)
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            pt = Point(x, y)
            if ok(pt):
                placed.append(pt)
            x += pitch
        y += pitch
    # One in every island of either layer that the grid missed.
    for layer in fills:
        for island in fills[layer]:
            area = island.intersection(room)
            if area.is_empty or any(area.contains(q) for q in placed):
                continue
            pt = area.representative_point()
            if all(pt.distance(c) >= r + drill / 2 + 0.3 for c, r in holes):
                placed.append(pt)
    for pt in placed:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(pt.x), pcbnew.FromMM(pt.y)))
        v.SetWidth(pcbnew.FromMM(via_d))
        v.SetDrill(pcbnew.FromMM(drill))
        v.SetNet(gnd)
        board.Add(v)
    board.Save(str(path))
    subprocess.run(["kicad-cli", "pcb", "drc", "--refill-zones", "--save-board", "-o", "/dev/null", str(path)],
                   check=True, capture_output=True)
    return len(placed)


if __name__ == "__main__":
    main()
