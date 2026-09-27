#!/usr/bin/env python3
"""VGACorne generator.

    generate.py [--force] [lib|schematics|pcbs|firmware|mechanical|bom|check|all ...]

Schematics and PCBs are *scaffolding*: once you start editing them in KiCad
they are the source of truth, so they are only (re)written with --force.
Firmware config and mechanical outputs are always regenerated -- the libhmk
mux matrix is read back from the schematics, so it follows any channel swaps
you make in KiCad.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vgacorne import circuits, customlib, project, schematic  # noqa: E402

KICAD_DIR = HERE / "kicad"


def board_dir(board: str) -> Path:
    return KICAD_DIR / board


def paths(board: str) -> tuple[Path, Path, str]:
    c = circuits.BOARDS[board]()
    d = board_dir(board)
    return d / f"{c.name}.kicad_sch", d / f"{c.name}.kicad_pcb", c.name


def _guard(path: Path, force: bool) -> bool:
    if path.exists() and not force:
        print(f"  skip {path.relative_to(HERE)} (exists; use --force to overwrite)")
        return False
    return True


def do_lib(_force: bool) -> None:
    customlib.build()
    print("  wrote lib/vgacorne.kicad_sym, lib/vgacorne.pretty")


def do_schematics(force: bool) -> None:
    for board, fn in circuits.BOARDS.items():
        c = fn()
        sch, _, name = paths(board)
        project.write_project(sch.parent, name)
        if _guard(sch, force):
            schematic.write(c, sch)
            print(f"  wrote {sch.relative_to(HERE)} ({len(c.parts)} parts)")


def do_pcbs(force: bool) -> None:
    from vgacorne import pcb

    for board, fn in circuits.BOARDS.items():
        c = fn()
        _, path, name = paths(board)
        if not _guard(path, force):
            continue
        b = pcb.BUILDERS[board](c, path)
        b.save(path)
        project.write_project(path.parent, name)  # NewBoard() may have written a default one
        print(f"  wrote {path.relative_to(HERE)}")


def do_firmware(_force: bool) -> None:
    from vgacorne import firmware

    for out in firmware.write():
        print(f"  wrote {out.relative_to(HERE.parent)}")


def do_mechanical(_force: bool) -> None:
    from vgacorne import mechanical

    for p in mechanical.write_all():
        print(f"  wrote {p.relative_to(HERE)}")


def do_bom(_force: bool) -> None:
    import subprocess

    out = HERE / "bom"
    out.mkdir(exist_ok=True)
    for board in circuits.BOARDS:
        sch, _, name = paths(board)
        dest = out / f"{name}.csv"
        subprocess.run(["kicad-cli", "sch", "export", "bom", "-o", str(dest),
                        "--fields", "Reference,Value,Footprint,MPN,${QUANTITY},${DNP}",
                        "--labels", "Refs,Value,Footprint,MPN,Qty,DNP",
                        "--group-by", "Value,Footprint,MPN,${DNP}", str(sch)],
                       check=True, capture_output=True)
        print(f"  wrote {dest.relative_to(HERE)}")


def do_check(_force: bool) -> None:
    from vgacorne import checks

    ok = checks.run_all()
    if not ok:
        sys.exit(1)


STEPS = {"lib": do_lib, "schematics": do_schematics, "pcbs": do_pcbs, "firmware": do_firmware,
         "mechanical": do_mechanical, "bom": do_bom, "check": do_check}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="*", default=["all"], choices=[*STEPS, "all"])
    ap.add_argument("--force", action="store_true", help="overwrite existing schematics/PCBs")
    args = ap.parse_args()
    steps = list(STEPS) if "all" in args.steps else args.steps
    for s in steps:
        print(f"[{s}]")
        STEPS[s](args.force)


if __name__ == "__main__":
    main()
