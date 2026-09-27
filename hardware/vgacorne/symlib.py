"""Load KiCad library symbols, flattening ``extends`` inheritance."""

from __future__ import annotations

import copy
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .sexpr import Sym, find, find_all, parse

KICAD_SYMBOL_DIR = Path(os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols"))
LOCAL_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"


@dataclass
class Pin:
    number: str
    name: str
    etype: str
    x: float  # library coordinates, Y up
    y: float
    angle: float  # direction from connection point toward the body
    unit: int  # 0 = shared by all units
    hidden: bool


@dataclass
class LibSymbol:
    lib_id: str
    node: list  # flattened symbol, named "<lib>:<name>" for embedding
    pins: list[Pin]
    units: int
    power: bool
    properties: dict[str, str]

    def flag(self, name: str, default: bool) -> bool:
        node = find(self.node, name)
        return default if node is None else node[1] == "yes"

    def pins_for_unit(self, unit: int) -> list[Pin]:
        return [p for p in self.pins if p.unit in (0, unit)]

    def pin(self, key: str) -> Pin:
        """Look a pin up by number, falling back to a unique name."""
        by_num = [p for p in self.pins if p.number == key]
        if by_num:
            return by_num[0]
        by_name = [p for p in self.pins if p.name == key]
        if len(by_name) == 1:
            return by_name[0]
        raise KeyError(f"{self.lib_id}: no unique pin {key!r}")


def _lib_path(lib: str) -> Path:
    local = LOCAL_LIB_DIR / f"{lib}.kicad_sym"
    if local.exists():
        return local
    return KICAD_SYMBOL_DIR / f"{lib}.kicad_sym"


@lru_cache(maxsize=None)
def _library(lib: str) -> dict[str, list]:
    tree = parse(_lib_path(lib).read_text())
    return {str(s[1]): s for s in find_all(tree, "symbol")}


def _flatten(lib: str, name: str) -> list:
    syms = _library(lib)
    node = copy.deepcopy(syms[name])
    ext = find(node, "extends")
    if ext is None:
        return node
    parent = _flatten(lib, str(ext[1]))
    parent_name = str(parent[1])
    out = [Sym("symbol"), name]
    overridden = {str(p[1]) for p in find_all(node, "property")}
    for child in parent[2:]:
        if not isinstance(child, list):
            continue
        head = child[0]
        if head == "property":
            if str(child[1]) in overridden:
                continue
            out.append(child)
        elif head == "symbol":
            sub = copy.deepcopy(child)
            sub[1] = re.sub(rf"^{re.escape(parent_name)}_", f"{name}_", str(sub[1]))
            out.append(sub)
        elif head == "embedded_fonts":
            continue
        else:
            # Flags such as pin_names, in_bom; the derived symbol may override them.
            if find(node, head) is None:
                out.append(child)
    for child in node[2:]:
        if isinstance(child, list) and child[0] not in ("extends", "symbol", "embedded_fonts"):
            out.append(child)
    # Keep the conventional order: flags first, then properties, then units.
    order = {"pin_numbers": 0, "pin_names": 1, "exclude_from_sim": 2, "in_bom": 3,
             "on_board": 4, "power": 0, "property": 5, "symbol": 6}
    body = sorted(out[2:], key=lambda c: order.get(str(c[0]), 5))
    return [out[0], out[1], *body]


@lru_cache(maxsize=None)
def load(lib_id: str) -> LibSymbol:
    lib, name = lib_id.split(":", 1)
    flat = _flatten(lib, name)
    pins: list[Pin] = []
    units = 1
    for sub in find_all(flat, "symbol"):
        m = re.match(rf"^{re.escape(name)}_(\d+)_(\d+)$", str(sub[1]))
        if not m:
            raise ValueError(f"unexpected sub-symbol {sub[1]} in {lib_id}")
        unit, style = int(m.group(1)), int(m.group(2))
        units = max(units, unit)
        if style not in (0, 1):
            continue
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            pins.append(Pin(
                number=str(find(p, "number")[1]),
                name=str(find(p, "name")[1]),
                etype=str(p[1]),
                x=float(at[1]), y=float(at[2]), angle=float(at[3]) if len(at) > 3 else 0.0,
                unit=unit,
                hidden=_is_hidden(p),
            ))
    embedded = copy.deepcopy(flat)
    embedded[1] = f"{lib}:{name}"
    props = {str(p[1]): str(p[2]) for p in find_all(flat, "property")}
    return LibSymbol(lib_id, embedded, pins, units, find(flat, "power") is not None, props)


def _is_hidden(pin: list) -> bool:
    if any(c == "hide" for c in pin):  # pre-KiCad 9 bare flag
        return True
    hide = find(pin, "hide")
    return hide is not None and (len(hide) < 2 or hide[1] != "no")


def transform(x: float, y: float, rot: float) -> tuple[float, float]:
    """Library point -> schematic offset (Y down) for a symbol rotated ``rot`` degrees."""
    r = math.radians(rot)
    rx = x * math.cos(r) - y * math.sin(r)
    ry = x * math.sin(r) + y * math.cos(r)
    return rx, -ry


def outward(pin: Pin, rot: float) -> tuple[float, float]:
    """Unit vector (schematic coordinates) pointing away from the body at a pin."""
    a = math.radians(pin.angle + rot)
    dx, dy = math.cos(a), -math.sin(a)
    return -round(dx), -round(dy)


def body_bbox(sym: LibSymbol, unit: int) -> tuple[float, float, float, float]:
    """Rough bounding box (lib coords) from pins and graphics of one unit."""
    xs, ys = [], []
    for p in sym.pins_for_unit(unit):
        xs.append(p.x)
        ys.append(p.y)
    name = sym.lib_id.split(":", 1)[1]
    for sub in find_all(sym.node, "symbol"):
        m = re.match(rf"^{re.escape(name)}_(\d+)_(\d+)$", str(sub[1]))
        if not m or int(m.group(1)) not in (0, unit):
            continue
        for g in sub[2:]:
            if not isinstance(g, list) or g[0] == "pin":
                continue
            for c in _walk(g):
                if c and c[0] in ("start", "end", "center", "xy", "mid") and len(c) >= 3:
                    try:
                        xs.append(float(c[1]))
                        ys.append(float(c[2]))
                    except ValueError:
                        pass
    if not xs:
        return (-2.54, -2.54, 2.54, 2.54)
    return (min(xs), min(ys), max(xs), max(ys))


def _walk(node):
    yield node
    for c in node:
        if isinstance(c, list):
            yield from _walk(c)
