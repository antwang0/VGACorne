"""Design checks: ERC, DRC + schematic parity, netlist intent, firmware config.

Run with ``generate.py check``. Unrouted connections and silkscreen
cosmetics are reported but do not fail the check (routing is manual).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import circuits, firmware
from .firmware import Netlist

HARDWARE = Path(__file__).resolve().parent.parent
KICAD = HARDWARE / "kicad"
TOLERATED_DRC = {"unconnected_items", "silk_over_copper", "silk_overlap", "silk_edge_clearance"}


def _violations(report: Path) -> Counter:
    return Counter(m.group(1) for m in re.finditer(r"^\[(\w+)\]", report.read_text(), re.M))


def _kicad(*args: str) -> None:
    subprocess.run(["kicad-cli", *args], check=True, capture_output=True)


def erc(board: str, sch: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        rpt = Path(tmp) / "erc.rpt"
        _kicad("sch", "erc", "--severity-all", "-o", str(rpt), str(sch))
        v = _violations(rpt)
    print(f"  {board:9} ERC: {sum(v.values())} violations {dict(v) or ''}")
    return not v


def drc(board: str, pcb: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        rpt = Path(tmp) / "drc.rpt"
        _kicad("pcb", "drc", "--severity-all", "--schematic-parity", "-o", str(rpt), str(pcb))
        v = _violations(rpt)
    bad = {k: n for k, n in v.items() if k not in TOLERATED_DRC}
    ok_part = {k: n for k, n in v.items() if k in TOLERATED_DRC}
    print(f"  {board:9} DRC: {sum(bad.values())} errors {bad or ''} (tolerated: {ok_part})")
    return not bad


NET_CLASS_EXPECT = [(r"/HE_", "Analog"), (r"/ADC_", "Analog"), (r"/LINK_[ABC]$", "Analog"),
                    (r"/OPA_", "Analog"), (r"/MUX_[ABC]$", "Analog"), (r"/USB_", "USB"),
                    (r"/\+5V_LINK$", "Power"), (r"^(GND|VBUS|\+)", "Power")]


def net_classes(board: str, pcb: Path) -> bool:
    """Net-class patterns in the .kicad_pro must actually match (KiCad prefixes label nets with '/')."""
    import pcbnew

    wrong = []
    for name, net in pcbnew.LoadBoard(str(pcb)).GetNetsByName().items():
        name = str(name)
        for pattern, cls in NET_CLASS_EXPECT:
            if re.search(pattern, name) and net.GetNetClassName() != cls:
                wrong.append(f"{name}={net.GetNetClassName()}")
                break
    print(f"  {board:9} net classes: {'ok' if not wrong else 'WRONG ' + ', '.join(sorted(wrong)[:6])}")
    return not wrong


def intent(board: str, sch: Path) -> bool:
    """Does the schematic still say what circuits.py says? (Informational once hand-edited.)"""
    c = circuits.BOARDS[board]()
    nl = Netlist.load(sch)
    got = {frozenset(n) for net, pins in nl.net_pins.items() if not net.startswith("unconnected-")
           for n in [[(r, p) for r, p, _ in pins]]}
    want = {frozenset(v) for v in c.nets().values()}
    same = got == want
    print(f"  {board:9} netlist {'matches' if same else 'DIFFERS from'} circuits.py "
          f"({len(want)} nets{'' if same else f'; {len(want - got)} missing, {len(got - want)} extra'})")
    return same


def firmware_config() -> bool:
    from . import qmk

    ok = True
    ws = firmware.wirings()
    for path, text in qmk.generate(ws[qmk.MODULE]).items():
        same = path.exists() and path.read_text() == text
        ok &= same
        print(f"  qmk/{path.name} {'up to date' if same else 'STALE - run generate.py firmware'}")
    for module, fresh in firmware.generate(ws).items():
        path = firmware.out_path(module)
        on_disk = json.loads(path.read_text()) if path.exists() else None
        same = fresh == on_disk
        ok &= same
        print(f"  {path.parent.name}/keyboard.json {'up to date' if same else 'STALE - run generate.py firmware'}")
        libhmk = os.environ.get("LIBHMK")
        if libhmk:
            sys.path.insert(0, str(Path(libhmk) / "scripts" / "schema"))
            from keyboard import Keyboard  # type: ignore

            Keyboard.model_validate(fresh)
            print(f"  {path.parent.name}/keyboard.json validates against libhmk's schema")
    return ok


def qmk_host_test() -> bool:
    """Run the QMK hall-effect matrix against simulated sensors (needs a host C compiler)."""
    import shutil

    script = HARDWARE.parent / "firmware" / "qmk" / "tests" / "run.sh"
    if not shutil.which("cc"):
        print("  qmk host test skipped (no C compiler)")
        return True
    r = subprocess.run(["sh", str(script)], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    print(f"  qmk host test: {lines[-1] if lines else r.stderr.strip()[-200:]}")
    if r.returncode:
        print("    " + "\n    ".join(l for l in lines if l.startswith("FAIL")))
    return r.returncode == 0


def module_connector(module: str) -> bool:
    """Every module header pad must sit on the carrier socket pad carrying the same net."""
    import pcbnew

    def pads(pcb: Path, ref: str) -> dict[tuple[float, int], str]:
        """(row y, column side) -> net. SMD header and socket pads sit at different
        outward offsets from the same pins, so compare rows and sides, not pad XY."""
        board = pcbnew.LoadBoard(str(pcb))
        fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        c = fp.GetPosition()
        along_y = round(fp.GetOrientationDegrees()) % 180 == 0  # long axis along Y
        out = {}
        for p in fp.Pads():
            d = p.GetPosition() - c
            row, across = (d.y, d.x) if along_y else (d.x, d.y)
            out[(round(pcbnew.ToMM(row + (c.y if along_y else c.x)), 2), 1 if across > 0 else -1)] = p.GetNetname()
        return out

    carrier = pads(KICAD / "main" / "vgacorne-main.kicad_pcb", "J4")
    mod = pads(KICAD / module / f"vgacorne-{module.replace('_', '-')}.kicad_pcb", "J1")
    bad = [f"{xy}: module {n} / carrier {carrier.get(xy)}" for xy, n in mod.items() if carrier.get(xy) != n]
    print(f"  {module:11} header vs main J4: {'all %d pads match' % len(mod) if not bad else 'MISMATCH ' + '; '.join(bad[:3])}")
    return not bad


def run_all() -> bool:
    ok = True
    for board in circuits.BOARDS:
        c = circuits.BOARDS[board]()
        sch = KICAD / board / f"{c.name}.kicad_sch"
        pcb = sch.with_suffix(".kicad_pcb")
        ok &= erc(board, sch)
        ok &= drc(board, pcb)
        ok &= net_classes(board, pcb)
        intent(board, sch)
    for module in firmware.MODULES:
        ok &= module_connector(module)
    ok &= firmware_config()
    ok &= qmk_host_test()
    print("  PASS" if ok else "  FAIL")
    return ok
