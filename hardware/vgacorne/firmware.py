"""Generate the libhmk keyboard definition from the KiCad schematics.

The mux matrix is *traced from the netlists* rather than copied from
circuits.py. The boards form one graph: nets are joined through series
resistors, the satellite's buffer op-amps, the MCU-module connector (module
pin n mates with carrier pin n+/-1) and the 1:1 link cable. From each MCU ADC
pin we search to a mux common pin, then map every mux channel to the switch
whose sensor drives it. Swap mux channels in KiCad to ease routing, re-run
``generate.py firmware`` and the firmware follows.

One libhmk keyboard is generated per MCU module.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .circuits import LINK_PINS, SENSOR, mating_pin
from .geometry import MAIN_SIDE, SATELLITE_SIDE

HARDWARE = Path(__file__).resolve().parent.parent
REPO = HARDWARE.parent
KEYBOARDS = REPO / "firmware" / "libhmk" / "keyboards"

# Per-module libhmk settings. PIDs are pid.codes test IDs: request real ones before distributing.
MODULES = {
    "module_at32": {"keyboard": "vgacorne_at32", "name": "VGACorne AT32", "driver": "at32f405xx",
                    "hse_value": 12000000, "port": "hs", "pid": "0x0001"},
    "module_f446": {"keyboard": "vgacorne_f446", "name": "VGACorne F446", "driver": "stm32f446xx",
                    "hse_value": 8000000, "port": "fs", "pid": "0x0002"},
}


def out_path(module: str) -> Path:
    return KEYBOARDS / MODULES[module]["keyboard"] / "keyboard.json"

MUX_CHANNEL_PINS = {"13": 0, "14": 1, "15": 2, "12": 3, "1": 4, "5": 5, "2": 6, "4": 7}  # 4051 An
MUX_SELECT_PINS = {"11": 0, "10": 1, "9": 2}  # S0, S1, S2
MUX_COM_PIN = "3"
POWER = {"GND", "+3V3", "+3.3VA", "+5V", "VBUS", "/+5V_LINK"}


@dataclass
class Netlist:
    parts: dict[str, dict]  # ref -> {"value", "lib", "part"}
    pin_net: dict[tuple[str, str], str]
    net_pins: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)  # net -> [(ref, pin, func)]

    @classmethod
    def load(cls, sch: Path) -> "Netlist":
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "n.xml"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
                            "-o", str(xml), str(sch)], check=True, capture_output=True)
            root = ET.parse(xml).getroot()
        parts = {}
        for c in root.iter("comp"):
            ls = c.find("libsource")
            parts[c.get("ref")] = {"value": c.findtext("value"), "lib": ls.get("lib"), "part": ls.get("part")}
        pin_net, net_pins = {}, defaultdict(list)
        for n in root.iter("net"):
            for node in n.iter("node"):
                pin_net[(node.get("ref"), node.get("pin"))] = n.get("name")
                net_pins[n.get("name")].append((node.get("ref"), node.get("pin"), node.get("pinfunction") or ""))
        return cls(parts, pin_net, dict(net_pins))

    def is_mux(self, ref: str) -> bool:
        return self.parts[ref]["part"] == "74HC4051"

    def pass_through(self, net: str) -> list[str]:
        """Nets reachable from ``net`` through one series resistor or unity buffer."""
        out = []
        for ref, pin, _ in self.net_pins.get(net, []):
            info = self.parts[ref]
            if info["part"] == "R" and _ohms(info["value"]) <= 1000:
                other = self.pin_net[(ref, "2" if pin == "1" else "1")]
                if other not in POWER:
                    out.append(other)
            elif info["part"] == "TLV9064" and pin in OPAMP_BUFFER:
                out.append(self.pin_net[(ref, OPAMP_BUFFER[pin])])
            elif info["part"] == "TLV9064" and pin in OPAMP_BUFFER_REV:
                out.append(self.pin_net[(ref, OPAMP_BUFFER_REV[pin])])
        return out

    def trace(self, net: str, want) -> list[tuple[str, str]]:
        """BFS from ``net``; return (net, ref) for every node where ``want(ref, pin)``."""
        seen, todo, hits = {net}, [net], []
        while todo:
            n = todo.pop()
            for ref, pin, _ in self.net_pins.get(n, []):
                if want(ref, pin):
                    hits.append((n, ref))
            for m in self.pass_through(n):
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return hits


OPAMP_BUFFER = {"3": "1", "5": "7", "10": "8", "12": "14"}  # + input -> output, per unit
OPAMP_BUFFER_REV = {v: k for k, v in OPAMP_BUFFER.items()}


def _ohms(v: str) -> float:
    m = re.fullmatch(r"([\d.]+)([kKmM]?)", v.strip())
    if not m:
        return float("inf")
    return float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)]


def _gpio(pinfunction: str) -> str | None:
    """'PA3' / 'PA13/SWDIO' -> 'A3' (libhmk pin naming)."""
    m = re.match(r"P([A-F])(\d+)", pinfunction)
    return f"{m.group(1)}{m.group(2)}" if m else None


HAND = {"left": "L", "right": "R"}  # key_order() labels


# Key order seen by the firmware / configurator: the Corne's 42 keys left to
# right like QMK's LAYOUT_split_3x6_3 (three rows of 12, then the six thumbs),
# then the satellite's two mouse-button keys, so keys 0-41 keep their numbers.
def key_order() -> list[tuple[str, str]]:
    order = []
    for row in range(3):
        order += [("L", f"C{c}R{row}") for c in range(6)]
        order += [("R", f"C{c}R{row}") for c in reversed(range(6))]
    order += [("L", "T0"), ("L", "T1"), ("L", "T2"), ("R", "T2"), ("R", "T1"), ("R", "T0")]
    order += [(HAND[SATELLITE_SIDE], "M0"), (HAND[SATELLITE_SIDE], "M1")]
    return order

MODULE_CONN = ("J4", "J1")  # carrier socket, module header
LINK_CONN = "J3"            # JST-SH on both halves; the VGA path is 1:1


class Boards:
    """The carrier, satellite and one MCU module as a single connected graph."""

    def __init__(self, module: Netlist, main: Netlist, sat: Netlist):
        self.nl = {"module": module, "main": main, "sat": sat}
        mcu = [r for r, p in module.parts.items() if r == "U1"]
        if not mcu:
            raise ValueError("module has no U1")
        self.mcu = mcu[0]

    def _joins(self, board: str, net: str):
        """Nets on other boards wired to this one through a connector."""
        nl = self.nl[board]
        for ref, pin, _ in nl.net_pins.get(net, []):
            if board == "main" and ref == MODULE_CONN[0]:
                yield "module", self.nl["module"].pin_net.get((MODULE_CONN[1], mating_pin(pin)))
            elif board == "module" and ref == MODULE_CONN[1]:
                yield "main", self.nl["main"].pin_net.get((MODULE_CONN[0], mating_pin(pin)))
            elif board in ("main", "sat") and ref == LINK_CONN:
                other = "sat" if board == "main" else "main"
                yield other, self.nl[other].pin_net.get((LINK_CONN, pin))

    def reach(self, board: str, net: str, want) -> list[tuple[str, str, str, str]]:
        """All (board, net, ref, pin) reachable from ``net`` where ``want(board, ref, pin)``."""
        seen, todo, hits = {(board, net)}, [(board, net)], []
        while todo:
            b, n = todo.pop()
            nl = self.nl[b]
            for ref, pin, _ in nl.net_pins.get(n, []):
                if want(b, ref, pin):
                    hits.append((b, n, ref, pin))
            nxt = [(b, m) for m in nl.pass_through(n)] + [j for j in self._joins(b, n) if j[1]]
            for node in nxt:
                if node not in seen and node[1] not in POWER:
                    seen.add(node)
                    todo.append(node)
        return hits

    def mcu_gpio(self, pin: str) -> str | None:
        nl = self.nl["module"]
        net = nl.pin_net[(self.mcu, pin)]
        return _gpio(next(f for r, p, f in nl.net_pins[net] if r == self.mcu and p == pin))


@dataclass
class Wiring:
    """Everything the firmware needs to know about how the MCU sees the keys."""
    select_pins: list[str]          # GPIO per select bit (S0 first)
    inputs: list[str]               # GPIO per ADC input
    matrix: list[list[int]]         # [input][mux channel] -> 1-based key index, 0 = unused
    input_sides: list[str]          # hand of each input's keys: "L" or "R" (see HAND)
    det_pin: str | None             # GPIO that reads the cable-detect line
    i2c_pins: tuple[str, str] | None = None  # (SCL, SDA) GPIOs of the trackpad bus
    encoder: tuple[int, int] | None = None   # (input, mux channel) of the rotary encoder's level


def build_matrix(module: Netlist, main: Netlist, sat: Netlist) -> Wiring:
    g = Boards(module, main, sat)
    order = key_order()
    index = {k: i + 1 for i, k in enumerate(order)}  # libhmk matrix is 1-based, 0 = none
    side_of = {"main": HAND[MAIN_SIDE], "sat": HAND[SATELLITE_SIDE]}

    # --- select lines: every mux S_i on both halves must reach the same MCU pin --------
    select: dict[int, str] = {}
    for board in ("main", "sat"):
        nl = g.nl[board]
        for ref in (r for r in nl.parts if nl.is_mux(r)):
            for pin, bit in MUX_SELECT_PINS.items():
                hits = g.reach(board, nl.pin_net[(ref, pin)],
                               lambda b, r, p: b == "module" and r == g.mcu)
                srcs = {g.mcu_gpio(p) for _, _, _, p in hits}
                if len(srcs) != 1:
                    raise ValueError(f"{board} {ref} S{bit} reaches MCU pins {srcs or 'none'}")
                src = srcs.pop()
                if select.setdefault(bit, src) != src:
                    raise ValueError(f"{board} {ref} S{bit} is driven by {src}, others by {select[bit]}")
    select_pins = [select[b] for b in range(3)]

    # --- ADC inputs: each MCU pin that reaches exactly one mux common ------------------
    inputs, matrix, sides, encoder = [], [], [], None
    mnl = g.nl["module"]
    pins = sorted(((p, mnl.pin_net[(g.mcu, p)]) for r, p in mnl.pin_net if r == g.mcu),
                  key=lambda t: g.mcu_gpio(t[0]) or "")
    for pin, net in pins:
        hits = g.reach("module", net, lambda b, r, p: b in side_of and g.nl[b].is_mux(r) and p == MUX_COM_PIN)
        if not hits:
            continue
        if len(hits) != 1:
            raise ValueError(f"MCU pin {g.mcu_gpio(pin)} reaches {len(hits)} muxes")
        board, _, mux, _ = hits[0]
        nl = g.nl[board]
        row = []
        for mpin, ch in sorted(MUX_CHANNEL_PINS.items(), key=lambda t: t[1]):
            cnet = nl.pin_net[(mux, mpin)].lstrip("/")
            row.append(index[(side_of[board], cnet[3:])] if cnet.startswith("HE_") else 0)
            if cnet == "ENC":
                if encoder:
                    raise ValueError("two mux channels carry ENC")
                encoder = (len(inputs), ch)
        inputs.append(g.mcu_gpio(pin))
        matrix.append(row)
        sides.append(side_of[board])

    used = sorted(i for row in matrix for i in row if i)
    if used != list(range(1, len(order) + 1)):
        missing = set(range(1, len(order) + 1)) - set(used)
        raise ValueError(f"keys not reachable from any ADC input: {[order[i - 1] for i in missing]}")

    # --- cable detect: the MCU pin wired to LINK_DET on the link connector -------------
    det_pin_no = next(p for p, n in LINK_PINS.items() if n == "LINK_DET")
    det = {g.mcu_gpio(pin) for pin, net in pins
           if g.reach("module", net, lambda b, r, p: b == "main" and r == LINK_CONN and p == det_pin_no)}
    det.discard(None)
    if len(det) > 1:
        raise ValueError(f"several MCU pins reach LINK_DET: {det}")

    # --- trackpad I2C: the MCU pins on the module's I2C nets ---------------------------
    i2c = {net.lstrip("/"): g.mcu_gpio(pin) for pin, net in pins if net.lstrip("/") in ("I2C_SCL", "I2C_SDA")}
    i2c_pins = (i2c["I2C_SCL"], i2c["I2C_SDA"]) if len(i2c) == 2 else None
    return Wiring(select_pins, inputs, matrix, sides, det.pop() if det else None, i2c_pins, encoder)


# ---------------------------------------------------------------------------
# keyboard.json
# ---------------------------------------------------------------------------

_ = "_______"
X = "XXXXXXX"


def default_keymap() -> list[list[str]]:
    # Last two: the mouse-button keys (libhmk has no encoder support).
    base = [
        "KC_TAB", "KC_Q", "KC_W", "KC_E", "KC_R", "KC_T", "KC_Y", "KC_U", "KC_I", "KC_O", "KC_P", "KC_BSPC",
        "KC_LCTL", "KC_A", "KC_S", "KC_D", "KC_F", "KC_G", "KC_H", "KC_J", "KC_K", "KC_L", "KC_SCLN", "KC_QUOT",
        "KC_LSFT", "KC_Z", "KC_X", "KC_C", "KC_V", "KC_B", "KC_N", "KC_M", "KC_COMM", "KC_DOT", "KC_SLSH", "KC_ESC",
        "KC_LGUI", "MO(1)", "KC_SPC", "KC_ENT", "MO(2)", "KC_RALT",
        "MS_BTN1", "MS_BTN2",
    ]
    lower = [
        "KC_GRV", "KC_1", "KC_2", "KC_3", "KC_4", "KC_5", "KC_6", "KC_7", "KC_8", "KC_9", "KC_0", _,
        _, X, X, X, X, X, "KC_LEFT", "KC_DOWN", "KC_UP", "KC_RGHT", X, X,
        _, X, X, X, X, X, "KC_HOME", "KC_PGDN", "KC_PGUP", "KC_END", X, X,
        _, _, _, _, "MO(3)", _,
        _, _,
    ]
    raise_ = [
        "KC_GRV", X, X, X, X, X, "KC_MINS", "KC_EQL", "KC_LBRC", "KC_RBRC", "KC_BSLS", "KC_DEL",
        _, X, X, X, X, X, X, X, X, X, X, X,
        _, X, X, X, X, X, X, X, X, X, X, X,
        _, "MO(3)", _, _, _, _,
        _, _,
    ]
    adjust = [
        "SP_BOOT", "KC_F1", "KC_F2", "KC_F3", "KC_F4", "KC_F5", "KC_F6", "KC_F7", "KC_F8", "KC_F9", "KC_F10", "KC_F11",
        X, "PF(0)", "PF(1)", "PF(2)", "PF(3)", X, "KC_MPRV", "KC_VOLD", "KC_VOLU", "KC_MNXT", X, "KC_F12",
        X, X, X, X, X, X, "KC_MPLY", "KC_MUTE", X, X, X, X,
        _, _, _, _, _, _,
        _, _,
    ]
    return [base, lower, raise_, adjust]


def layout() -> dict:
    # The mouse column sits just inside the left half: M1 (43) on the top row,
    # M0 (42) on the home row, the rotary encoder on the bottom row.
    mouse = {0: 43, 1: 42}
    rows = []
    n = 0
    for r in range(3):
        row = [{"key": n + i} for i in range(6)]
        row += [{"key": mouse[r]}, {"key": n + 6, "x": 2}] if r in mouse else [{"key": n + 6, "x": 3}]
        row += [{"key": n + 7 + i} for i in range(5)]
        rows.append(row)
        n += 12
    rows.append([{"key": 36, "x": 4}, {"key": 37}, {"key": 38, "h": 1.5},
                 {"key": 39, "x": 1, "h": 1.5}, {"key": 40}, {"key": 41}])
    return {"keymap": rows}


def keyboard_json(module: str, w: Wiring) -> dict:
    m = MODULES[module]
    return {
        "name": m["name"],
        "manufacturer": "VGACorne",
        "maintainer": "antwang0",
        "usb": {"vid": "0x1209", "pid": m["pid"], "port": m["port"]},
        "keyboard": {"num_profiles": 4, "num_layers": 4, "num_keys": len(key_order()),
                     "num_advanced_keys": 32},
        "hardware": {"hse_value": m["hse_value"], "driver": m["driver"]},
        "analog": {
            "invert_adc": SENSOR.invert_adc,
            "mux": {"select": w.select_pins, "input": w.inputs, "matrix": w.matrix},
        },
        "calibration": {
            "initial_rest_value": SENSOR.initial_rest_value,
            "initial_bottom_out_threshold": SENSOR.initial_bottom_out_threshold,
        },
        "layout": layout(),
        "keymap": default_keymap(),
    }


def wirings() -> dict[str, Wiring]:
    kicad = HARDWARE / "kicad"
    main = Netlist.load(kicad / "main" / "vgacorne-main.kicad_sch")
    sat = Netlist.load(kicad / "satellite" / "vgacorne-satellite.kicad_sch")
    out = {}
    for module in MODULES:
        mod = Netlist.load(kicad / module / f"vgacorne-{module.replace('_', '-')}.kicad_sch")
        out[module] = build_matrix(mod, main, sat)
    return out


def generate(ws: dict[str, Wiring] | None = None) -> dict[str, dict]:
    """module key -> libhmk keyboard.json contents."""
    ws = ws or wirings()
    return {module: keyboard_json(module, w) for module, w in ws.items()}


def _dump(obj, indent: int = 0) -> str:
    """JSON that keeps short leaf arrays/objects (matrix rows, layout keys) on one line."""
    flat = json.dumps(obj)
    if len(flat) <= 100 or not isinstance(obj, (dict, list)):
        return flat
    pad, inner = "  " * indent, "  " * (indent + 1)
    if isinstance(obj, list):
        if all(not isinstance(v, (dict, list)) for v in obj):
            # Keymap layers: wrap long flat lists.
            items, lines, line = [json.dumps(v) for v in obj], [], ""
            for it in items:
                if line and len(line) + len(it) + 2 > 100:
                    lines.append(line)
                    line = ""
                line += (", " if line else "") + it
            lines.append(line)
            return "[\n" + ",\n".join(inner + l for l in lines) + "\n" + pad + "]"
        return "[\n" + ",\n".join(inner + _dump(v, indent + 1) for v in obj) + "\n" + pad + "]"
    return "{\n" + ",\n".join(f"{inner}{json.dumps(k)}: {_dump(v, indent + 1)}" for k, v in obj.items()) + \
        "\n" + pad + "}"


def write() -> list[Path]:
    from . import qmk

    ws = wirings()
    paths = []
    for module, data in generate(ws).items():
        path = out_path(module)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(data) + "\n")
        paths.append(path)
    for path, text in qmk.generate(ws[qmk.MODULE]).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        paths.append(path)
    return paths
