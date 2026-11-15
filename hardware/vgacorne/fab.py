"""JLCPCB fabrication and assembly files for each board.

``fab/<name>/`` gets
  <name>-gerbers.zip  Gerbers with JLC's KiCad settings (Protel extensions, no X2,
                      silkscreen clipped to the solder mask) and Excellon drill
                      files in mm, plated and non-plated holes separate
  <name>-bom.csv      Comment, Designator, Footprint, LCSC Part #
  <name>-cpl.csv      Designator, Mid X, Mid Y, Layer, Rotation, in JLC's terms:
                      bottom-side angles and each package's zero angle and
                      origin corrected for JLC's footprints (CORRECTION)

Only parts with an LCSC number go into the BOM and CPL. write() returns the rest
(no number yet, or fitted by hand) so you can see what JLC won't place.
"""

from __future__ import annotations

import csv
import math
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .circuits import C0402, C0603, C0805, R0402

LAYERS = ["F.Cu", "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen",
          "F.Mask", "B.Mask", "Edge.Cuts"]


def _by_value(footprint: str, parts: dict[str, str]) -> dict[str, str]:
    return {f"{value} {footprint}": lcsc for value, lcsc in parts.items()}


# LCSC part numbers by MPN or, for passives, by "<value> <footprint>". A
# symbol's own LCSC field wins over this table. Checked against JLC's parts
# library on 2026-10-01. JLC Basic parts carry no setup fee: all the passives
# but the 75 ohm are Basic; of the rest, only those marked.
LCSC: dict[str, str] = {
    # MLCC, all >= 16 V (some sit on 5 V): 0402 X7R (100/15 pF: C0G), 0603/0805 X5R
    **_by_value(C0402, {"100n": "C1525", "4.7n": "C1538", "1n": "C1523", "100p": "C1546", "15p": "C1548"}),
    **_by_value(C0603, {"1u": "C15849", "2.2u": "C23630", "4.7u": "C19666"}),
    **_by_value(C0805, {"10u": "C15850"}),
    # 0402 1% thick film, UNI-ROYAL 0402WGF...
    **_by_value(R0402, {"75": "C25133", "100": "C25076", "470": "C25117", "1k": "C11702",
                        "4.7k": "C25900", "5.1k": "C25905", "10k": "C25744", "12k": "C25752",
                        "47k": "C25792", "100k": "C25741"}),
    "DRV5055A3QDBZR": "C266128",  # no die revision listed (sensors.md)
    "SN74LV4051APWR": "C7793",
    "TLV9064IPWR": "C779410",
    "TLV75733PDBVR": "C485517",
    "TPS2051CDBVR": "C129581",
    "USBLC6-2SC6": "C7519",
    "SRV05-4": "C13612",  # Semtech SRV05-4.TCT
    "B5819W": "C8598",  # Basic; JSCJ B5819W SL
    "SMD0805-075": "C883110",  # BHFUSE BSMD0805-075-6V: 0.75 A hold, 1.5 A trip
    "HRO TYPE-C-31-M-12": "C165948",
    "SM10B-SRSS-TB": "C160409",  # not C5306083, a discontinued duplicate
    "AFC07-S06FCA-00": "C262553",  # trackpad FFC connector J5, top side: two-sided assembly
    "PEC12R-4220F-N0024": "C143785",  # encoder ENC1, THT on top; LCSC stock was 0 in 2025, JLC may pre-order
    "TS-1187A-B-A-B": "C318884",  # Basic
    "AT32F405RCT7": "C47090415",  # 10x10 mm (the -7 suffix is 7x7); low stock
    "STM32F446RET6": "C69336",
    "X322512MOB4SI": "C70565",  # 12 pF load; the Basic C9002 is the 20 pF version
    "X32258MOB4SI": "C2682775",
}

# JLC places a part by the EasyEDA footprint of its LCSC number, whose zero angle
# and origin need not be KiCad's. A correction is (degrees added to KiCad's angle,
# (dx, dy) from KiCad's footprint origin to EasyEDA's, in mm in the KiCad
# footprint's own frame: Y down, as the footprint editor shows it). Each was
# found by fitting the part's EasyEDA footprint onto the KiCad pads (2026-11);
# the SOT-23, SOIC/TSSOP and LQFP turns match what JLC's preview showed on
# kicad-jlcpcb-tools' test board. EasyEDA's package name says where its pin 1 is
# drawn: -BR bottom right (SOT-23: 180), -BL bottom left (ICs: 270).
CORRECTION: dict[str, tuple[int, tuple[float, float]]] = {
    "C266128": (180, (0, 0)),  # DRV5055, SOT-23_..-BR
    "C129581": (180, (0, 0)),  # TPS2051C, SOT-23-5_..-BR
    "C485517": (270, (0, 0)),  # TLV757, SOT-23-5_..-BL: drawn with pins top and bottom
    "C13612": (180, (0, 0)),  # SRV05-4, SOT-23-6_..-BR
    "C7519": (270, (0, 0)),  # USBLC6-2, SOT-23-6_..-BL
    "C7793": (270, (0, 0)),  # 74LV4051, TSSOP-16_..-BL
    "C779410": (270, (0, 0)),  # TLV9064, TSSOP-14_..-BL
    "C69336": (270, (0, 0)),  # STM32F446, LQFP-64_..-BL
    "C47090415": (270, (0, 0)),  # AT32F405, LQFP-64_..-BL
    "C165948": (0, (0, -1.571)),  # USB-C: EasyEDA's origin is 1.571 mm nearer the signal pads
    "C262553": (180, (0, -0.516)),  # FFC J5: EasyEDA's origin is 0.516 mm nearer the contacts
    "C160409": (0, (0, -0.0625)),  # JST SH: EasyEDA's origin is the pads' centre
    "C143785": (270, (3.75, 2.5)),  # PEC12R: EasyEDA's origin is midway between pins and lugs
}
# Parts not listed above, by KiCad footprint name; anything else (passives, the
# SOD-123, the crystals, the tact switches) needs nothing. A SOT-23-5/6 drawn -BL
# needs 270, so list new ones by LCSC number after checking JLC's preview.
CORRECTION_BY_FOOTPRINT = [
    (r"SOT-23(-[356])?$", 180),
    (r"(LQFP|TQFP|QFN|TSSOP|SSOP|MSOP|SOIC)-", 270),
]


def _correction(part: str, footprint: str) -> tuple[int, tuple[float, float]]:
    if part in CORRECTION:
        return CORRECTION[part]
    name = footprint.split(":")[-1]
    return next(((turn, (0, 0)) for pattern, turn in CORRECTION_BY_FOOTPRINT if re.match(pattern, name)), (0, (0, 0)))


def _placement(pos: dict[str, str], part: str, footprint: str) -> list[str]:
    """Mid X, Mid Y, Layer, Rotation as JLC reads them."""
    x, y, angle = float(pos["PosX"]), float(pos["PosY"]), float(pos["Rot"])
    bottom = pos["Side"] == "bottom"
    turn, (dx, dy) = _correction(part, footprint)
    # The pos file has Y up. KiCad draws a bottom footprint mirrored in its own
    # Y and then turned by its angle, so the offset's Y flips on the top side only.
    ox, oy = dx, dy if bottom else -dy
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    x, y = x + ox * c - oy * s, y + ox * s + oy * c
    # JLC turns a bottom part as seen from below, mirrored left to right: 180 minus
    # KiCad's angle, then the correction (KiBot's mirror_bottom, kicad-jlcpcb-tools).
    rotation = round((180 - angle if bottom else angle) + turn, 3) % 360
    return [f"{x:.4f}", f"{y:.4f}", pos["Side"].capitalize(), f"{rotation:g}"]


def _cli(*args: str) -> None:
    subprocess.run(["kicad-cli", *args], check=True, capture_output=True)


def gerbers(pcb: Path, dest: Path) -> None:
    inner = sorted(set(re.findall(r'"(In\d+\.Cu)"', pcb.read_text())))
    with tempfile.TemporaryDirectory() as tmp:
        _cli("pcb", "export", "gerbers", "-o", tmp, "-l", ",".join(LAYERS + inner),
             "--no-x2", "--subtract-soldermask", "--check-zones", str(pcb))
        _cli("pcb", "export", "drill", "-o", tmp, "--excellon-units", "mm",
             "--excellon-oval-format", "alternate", "--excellon-separate-th", str(pcb))
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(Path(tmp).iterdir()):
                if f.suffix != ".gbrjob":  # JLC doesn't use the job file
                    z.write(f, f.name)


def _bom_rows(sch: Path) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "bom.csv"
        _cli("sch", "export", "bom", "-o", str(out), "--exclude-dnp",
             "--fields", "Reference,Value,Footprint,MPN,LCSC",
             "--labels", "refs,value,footprint,mpn,lcsc",
             "--group-by", "Value,Footprint,MPN,LCSC", "--ref-range-delimiter", "", str(sch))
        with out.open(newline="") as f:
            return list(csv.DictReader(f))


def lcsc(row: dict[str, str]) -> str:
    return row["lcsc"] or LCSC.get(row["mpn"]) or LCSC.get(f"{row['value']} {row['footprint']}", "")


def _positions(pcb: Path) -> dict[str, dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pos.csv"
        _cli("pcb", "export", "pos", "-o", str(out), "--format", "csv", "--units", "mm",
             "--side", "both", str(pcb))
        with out.open(newline="") as f:
            return {r["Ref"]: r for r in csv.DictReader(f)}


def write(sch: Path, pcb: Path, out: Path) -> list[str]:
    """Write the board's fab files into ``out``; return the refs JLC won't place."""
    out.mkdir(parents=True, exist_ok=True)
    name = pcb.stem
    gerbers(pcb, out / f"{name}-gerbers.zip")
    pos = _positions(pcb)
    bom, cpl, unplaced = [], [], []
    for row in _bom_rows(sch):
        refs = row["refs"].split(",")
        part = lcsc(row)
        if not part:
            unplaced += refs
            continue
        missing = [r for r in refs if r not in pos]
        if missing:
            raise ValueError(f"{name}: {', '.join(missing)} not in the position file")
        bom.append([row["value"], ",".join(refs), row["footprint"].split(":")[-1], part])
        cpl += [[r, *_placement(pos[r], part, row["footprint"])] for r in refs]
    for path, header, rows in ((out / f"{name}-bom.csv", ["Comment", "Designator", "Footprint", "LCSC Part #"], bom),
                               (out / f"{name}-cpl.csv", ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"], cpl)):
        with path.open("w", newline="") as f:
            csv.writer(f).writerows([header, *rows])
    return unplaced
