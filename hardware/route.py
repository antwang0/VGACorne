#!/usr/bin/env python3
"""Autoroute a KiCad board with Freerouting: DSN export -> Freerouting (headless) -> SES import -> zone refill.

    ../.venv/bin/python route.py <board.kicad_pcb> <out.kicad_pcb> [attempts]

Needs Java >= 25 and Freerouting 2.4 (FREEROUTING_JAR, default
~/.kicad-mcp/freerouting.jar). Work on a copy of the board's project folder and
copy the result back once `generate.py check` is happy with it.

Two phases: the signals first, with the ground pours as planes; then, with
those tracks locked and the pours off, GND as tracks, so no ground pad depends
on a pour the signals cut up. Each phase runs Freerouting up to ``attempts``
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


def run(board, tmp: Path, tag: str, attempts: int, ground_width_um: int | None = None) -> int:
    """Export, route best-of-``attempts``, import. Returns the unrouted count."""
    dsn, best = tmp / f"{tag}.dsn", tmp / f"{tag}.ses"
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        sys.exit("DSN export failed")
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


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    attempts = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    board = pcbnew.LoadBoard(str(src))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # 1: signals, with the ground pours as planes.
        run(board, tmp, "signals", attempts)
        # 2: ground as tracks round the (locked) signals, so no pad depends on
        #    a pour the signal tracks may have cut up.
        tracks = board.Tracks()
        for i in range(tracks.size()):
            tracks[i].SetLocked(True)
        zones = list(board.Zones())
        for z in zones:
            board.Remove(z)
        n = run(board, tmp, "ground", attempts, ground_width_um=250)
        tracks = board.Tracks()
        for i in range(tracks.size()):
            tracks[i].SetLocked(False)
        for z in zones:
            board.Add(z)
    board.Save(str(dst))
    subprocess.run(["kicad-cli", "pcb", "drc", "--refill-zones", "--save-board", "-o", "/dev/null", str(dst)],
                   check=True, capture_output=True)
    print(f"routed -> {dst} ({n} unrouted in Freerouting); {stitch(dst)} ground stitching vias")


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
