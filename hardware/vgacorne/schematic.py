"""Write a flat, label-based KiCad schematic from a :class:`Circuit`.

Every connected pin gets a short wire stub ending in either a power symbol
(for power nets) or a local net label; unconnected pins get a no-connect flag.
The layout is block based: each :class:`Part` names the block it belongs to.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import symlib
from .sexpr import S, Sym, dumps

GRID = 1.27
STUB = 2.54

# Net name -> power symbol lib id. Anything else is drawn with labels.
POWER_SYMBOLS = {
    "GND": "power:GND",
    "+3V3": "power:+3V3",
    "+3.3VA": "power:+3.3VA",
    "+5V": "power:+5V",
    "VBUS": "power:VBUS",
}
_GROUND_LIKE = {"GND"}


@dataclass
class Part:
    ref: str
    lib_id: str
    value: str
    footprint: str
    pins: dict[str, str]  # pin number (or unique pin name) -> net
    block: str = "misc"
    fields: dict[str, str] = field(default_factory=dict)
    dnp: bool = False
    rot: float = 0.0
    key: str | None = None  # switch this part belongs to (per-key parts)
    description: str | None = None


@dataclass
class Circuit:
    name: str  # project name, e.g. "vgacorne-main"
    title: str
    rev: str
    parts: list[Part]
    blocks: list[tuple[str, str, tuple[float, float], float]]  # (id, heading, origin, width)
    notes: list[tuple[str, tuple[float, float]]] = field(default_factory=list)
    paper: str = "A1"

    def part(self, ref: str) -> Part:
        return next(p for p in self.parts if p.ref == ref)

    def nets(self) -> dict[str, list[tuple[str, str]]]:
        """Net -> [(ref, pin number)] with pin names resolved to numbers."""
        out: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for p in self.parts:
            sym = symlib.load(p.lib_id)
            for key, net in p.pins.items():
                out[net].append((p.ref, sym.pin(key).number))
        return out


def _snap(v: float) -> float:
    return round(v / GRID) * GRID


def _uid(*parts) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vgacorne/" + "/".join(map(str, parts))))


FONT = S("font", S("size", 1.27, 1.27))


def _effects(hidden=False, justify=None):
    e = S("effects", FONT)
    if justify:
        e.append(S("justify", *[Sym(j) for j in justify.split()]))
    if hidden:
        e.append(S("hide", Sym("yes")))
    return e


class _Writer:
    def __init__(self, circuit: Circuit):
        self.c = circuit
        self.root = _uid(circuit.name, "root")
        self.items: list = []
        self.lib_ids: set[str] = set()
        self.pwr_n = 0
        self.flag_n = 0
        self.n = 0

    def uid(self, *k) -> str:
        self.n += 1
        return _uid(self.c.name, self.n, *k)

    # -- primitives ---------------------------------------------------------
    def wire(self, a, b):
        self.items.append(S("wire", S("pts", S("xy", *a), S("xy", *b)),
                            S("stroke", S("width", 0), S("type", Sym("default"))),
                            S("uuid", self.uid("w"))))

    def label(self, net, at, direction):
        angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[direction]
        just = "left bottom" if angle in (0, 90) else "right bottom"
        self.items.append(S("label", net, S("at", at[0], at[1], angle),
                            S("fields_autoplaced", Sym("yes")),
                            _effects(justify=just), S("uuid", self.uid("l"))))

    def no_connect(self, at):
        self.items.append(S("no_connect", S("at", *at), S("uuid", self.uid("nc"))))

    def text(self, s, at, size=2.54, bold=False):
        font = S("font", S("size", size, size))
        if bold:
            font += [S("thickness", size / 5), S("bold", Sym("yes"))]
        self.items.append(S("text", s, S("exclude_from_sim", Sym("no")), S("at", at[0], at[1], 0),
                            S("effects", font, S("justify", Sym("left"), Sym("bottom"))),
                            S("uuid", self.uid("t"))))

    def symbol(self, lib_id, ref, value, at, rot=0, unit=1, footprint="", fields=None,
               dnp=False, hidden_ref=False, hidden_value=False, datasheet=None, description=None,
               in_bom=None, on_board=None):
        sym = symlib.load(lib_id)
        if in_bom is None:
            in_bom = sym.flag("in_bom", True)
        if on_board is None:
            on_board = sym.flag("on_board", True)
        self.lib_ids.add(lib_id)
        x, y = at
        bx0, by0, bx1, by1 = symlib.body_bbox(sym, unit)
        corners = [symlib.transform(px, py, rot) for px in (bx0, bx1) for py in (by0, by1)]
        pins = sym.pins_for_unit(unit)
        right = any(symlib.outward(p, rot) == (1, 0) for p in pins)
        top = any(symlib.outward(p, rot) == (0, -1) for p in pins)
        if right and not sym.power:
            # Labels occupy the right side: put reference/value above the body
            # (and above any top-pin stubs/power symbols).
            rx = x + min(c[0] for c in corners)
            ry = y + min(c[1] for c in corners) - (STUB + 5.08 if top else 0) - 5.08
        else:
            rx = x + max(c[0] for c in corners) + 1.27
            ry = y + min(c[1] for c in corners)
        props = [
            S("property", "Reference", ref, S("at", _snap(rx), _snap(ry + 1.27), 0),
              _effects(hidden_ref, "left")),
            S("property", "Value", value, S("at", _snap(rx), _snap(ry + 3.81), 0),
              _effects(hidden_value, "left")),
            S("property", "Footprint", footprint, S("at", x, y, 0), _effects(True)),
            S("property", "Datasheet",
              datasheet if datasheet is not None else (sym.properties.get("Datasheet") or "~"),
              S("at", x, y, 0), _effects(True)),
            S("property", "Description", description or sym.properties.get("Description", ""),
              S("at", x, y, 0), _effects(True)),
        ]
        for k, v in (fields or {}).items():
            props.append(S("property", k, v, S("at", x, y, 0), _effects(True)))
        pins = [S("pin", p.number, S("uuid", self.uid(ref, "pin", p.number)))
                for p in sym.pins_for_unit(unit)]
        node = S("symbol", S("lib_id", lib_id), S("at", x, y, rot), S("unit", unit),
                 S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes" if in_bom else "no")),
                 S("on_board", Sym("yes" if on_board else "no")),
                 S("dnp", Sym("yes" if dnp else "no")),
                 S("uuid", _uid(self.c.name, "sym", ref, unit)), *props, *pins,
                 S("instances", S("project", self.c.name,
                                  S("path", f"/{self.root}", S("reference", ref), S("unit", unit)))))
        self.items.append(node)
        return sym

    # -- connections ----------------------------------------------------------
    def power_symbol(self, net, at, direction):
        lib = POWER_SYMBOLS[net]
        ground = net in _GROUND_LIKE
        # Point the symbol graphic away from the part.
        if ground:
            rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[direction]
        else:
            rot = {(0, -1): 0, (0, 1): 180, (1, 0): 270, (-1, 0): 90}[direction]
        self.pwr_n += 1
        self.symbol(lib, f"#PWR{self.pwr_n:03d}", net, at, rot, hidden_ref=True,
                    datasheet="", in_bom=False, on_board=False)

    def pwr_flag(self, net, at):
        self.flag_n += 1
        self.symbol("power:PWR_FLAG", f"#FLG{self.flag_n:02d}", "PWR_FLAG", at, 0,
                    hidden_ref=True, datasheet="~", in_bom=False, on_board=False)
        self.attach(net, at, (0, 1))

    def attach(self, net, pin_at, direction):
        end = (_snap(pin_at[0] + direction[0] * STUB), _snap(pin_at[1] + direction[1] * STUB))
        self.wire(pin_at, end)
        if net in POWER_SYMBOLS:
            self.power_symbol(net, end, direction)
        else:
            self.label(net, end, direction)

    def junction(self, at):
        self.items.append(S("junction", S("at", *at), S("diameter", 0),
                            S("color", 0, 0, 0, 0), S("uuid", self.uid("j"))))

    def power_runs(self, attachments):
        """Join adjacent side pins on the same power net: one wire, one symbol.

        Returns the attachments that still need individual treatment.
        """
        rest, groups = [], defaultdict(list)
        for net, pos, d in attachments:
            if net in POWER_SYMBOLS and d[0] != 0:  # side pins only
                groups[(net, d, pos[0])].append(pos)
            else:
                rest.append((net, pos, d))
        for (net, d, _), pts in groups.items():
            pts.sort(key=lambda p: p[1])
            runs, cur = [], [pts[0]]
            for p in pts[1:]:
                if abs(p[1] - cur[-1][1] - 2.54) < 1e-3:
                    cur.append(p)
                else:
                    runs.append(cur)
                    cur = [p]
            runs.append(cur)
            for run in runs:
                if len(run) == 1:
                    rest.append((net, run[0], d))
                    continue
                ends = [(_snap(p[0] + d[0] * STUB), p[1]) for p in run]
                for p, e in zip(run, ends):
                    self.wire(p, e)
                for a, b in zip(ends, ends[1:]):
                    self.wire(a, b)
                for e in ends[1:-1]:
                    self.junction(e)
                # One symbol, pushed further out from the first pin of the run. (Never
                # extend along the run: that line continues past other pins' stubs.)
                self.junction(ends[0])
                tip = (_snap(ends[0][0] + d[0] * STUB), ends[0][1])
                self.wire(ends[0], tip)
                self.power_symbol(net, tip, d)
        return rest

    def place_part(self, part: Part, at, unit=1):
        sym = self.symbol(part.lib_id, part.ref, part.value, at, part.rot, unit, part.footprint,
                          part.fields, part.dnp, description=part.description)
        resolved = {sym.pin(k).number: net for k, net in part.pins.items()}
        seen: dict[tuple[float, float], str | None] = {}
        attachments = []
        for pin in sym.pins_for_unit(unit):
            dx, dy = symlib.transform(pin.x, pin.y, part.rot)
            pos = (round(at[0] + dx, 4), round(at[1] + dy, 4))
            net = resolved.get(pin.number)
            if pos in seen:
                # Stacked pins share one connection point.
                if net is not None and seen[pos] is not None and net != seen[pos]:
                    raise ValueError(f"{part.ref}: stacked pins on different nets")
                continue
            seen[pos] = net
            if net is None:
                if pin.etype != "no_connect":
                    self.no_connect(pos)
                continue
            attachments.append((net, pos, symlib.outward(pin, part.rot)))
        for net, pos, d in self.power_runs(attachments):
            self.attach(net, pos, d)


def _extent(sym: symlib.LibSymbol, unit: int, rot: float) -> tuple[float, float, float, float]:
    bx0, by0, bx1, by1 = symlib.body_bbox(sym, unit)
    pts = [symlib.transform(px, py, rot) for px in (bx0, bx1) for py in (by0, by1)]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
            max(p[1] for p in pts))


LABEL_ROOM = 16.0  # space reserved beside side pins for stubs + labels
V_ROOM = 7.62


def write(circuit: Circuit, path: Path) -> None:
    w = _Writer(circuit)
    blocks = {b[0]: b for b in circuit.blocks}
    cursor = {b: [origin[0], origin[1] + 10.16, 0.0] for b, (_, _, origin, _) in blocks.items()}
    for bid, heading, origin, _ in circuit.blocks:
        w.text(heading, (origin[0], origin[1] + 2.54), size=3.0, bold=True)
    for note, at in circuit.notes:
        w.text(note, at, size=1.8)

    for part in circuit.parts:
        sym = symlib.load(part.lib_id)
        units = range(1, sym.units + 1)
        for unit in units:
            x0, y0, x1, y1 = _extent(sym, unit, part.rot)
            has_side = any(abs(symlib.outward(p, part.rot)[0]) for p in sym.pins_for_unit(unit))
            wpad = LABEL_ROOM if has_side else 5.08
            cell_w = (x1 - x0) + 2 * wpad + 6
            cell_h = (y1 - y0) + 2 * V_ROOM + 5.08
            _, _, origin, width = blocks[part.block]
            cur = cursor[part.block]
            if cur[0] + cell_w > origin[0] + width and cur[0] > origin[0]:
                cur[0] = origin[0]
                cur[1] += cur[2]
                cur[2] = 0.0
            at = (_snap(cur[0] + wpad - x0), _snap(cur[1] + V_ROOM - y0 + 2.54))
            w.place_part(part, at, unit)
            cur[0] += cell_w
            cur[2] = max(cur[2], cell_h)

    # PWR_FLAG on power nets that have power inputs but no power output.
    nets = circuit.nets()
    kinds: dict[str, set[str]] = defaultdict(set)
    for net, members in nets.items():
        for ref, num in members:
            sym = symlib.load(circuit.part(ref).lib_id)
            kinds[net] |= {p.etype for p in sym.pins if p.number == num}
        if net in POWER_SYMBOLS:
            kinds[net].add("power_in")  # the power symbols themselves
    flag_nets = sorted(n for n, k in kinds.items() if "power_in" in k and "power_out" not in k)
    if flag_nets:
        bx, by = circuit.blocks[0][2]
        fy = by - 12.7
        w.text("Power flags", (bx, fy - 5.08), size=1.8)
        for i, net in enumerate(flag_nets):
            w.pwr_flag(net, (_snap(bx + 5.08 + i * 17.78), _snap(fy)))

    lib_nodes = [symlib.load(l).node for l in sorted(w.lib_ids)]
    tree = S("kicad_sch",
             S("version", 20250114), S("generator", "vgacorne"), S("generator_version", "1.0"),
             S("uuid", w.root), S("paper", circuit.paper),
             S("title_block", S("title", circuit.title), S("rev", circuit.rev),
               S("company", "VGACorne"),
               S("comment", 1, "Generated by hardware/generate.py - see docs/architecture.md")),
             S("lib_symbols", *lib_nodes),
             *w.items,
             S("sheet_instances", S("path", "/", S("page", "1"))),
             S("embedded_fonts", Sym("no")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(tree) + "\n")


def symbol_uuid(circuit: Circuit, ref: str) -> str:
    """UUID of unit 1 of ``ref`` -- used to link PCB footprints to the schematic."""
    return _uid(circuit.name, "sym", ref, 1)
