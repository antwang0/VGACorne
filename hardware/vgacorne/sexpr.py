"""Minimal S-expression reader/writer for KiCad files.

Atoms keep their original spelling: quoted strings become ``str`` and bare
tokens (keywords, numbers) become ``Sym`` so that round-tripping a library
symbol does not reformat numbers.
"""

from __future__ import annotations

import re


class Sym(str):
    """An unquoted atom (keyword or number)."""

    __slots__ = ()


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parse(text: str):
    """Parse one top-level expression."""
    stack: list[list] = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"bad token at {pos}: {text[pos:pos + 40]!r}")
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            done = stack.pop()
            stack[-1].append(done)
        elif m.group(3) is not None:
            stack[-1].append(_unescape(m.group(3)))
        elif m.group(4) is not None:
            stack[-1].append(Sym(m.group(4)))
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced expression")
    return stack[0][0]


def fmt_num(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def atom(v) -> str:
    if isinstance(v, Sym):
        return str(v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return fmt_num(float(v))
    if isinstance(v, str):
        return f'"{_escape(v)}"'
    raise TypeError(f"cannot serialise {v!r}")


# Lists whose children are all short atoms/lists are written on one line.
_INLINE = {"at", "xy", "size", "start", "end", "mid", "center", "offset", "font", "color",
           "radius", "length", "width", "type", "diameter", "justify", "hide", "uuid",
           "fill", "number", "name", "unit", "exclude_from_sim", "in_bom", "on_board",
           "dnp", "fields_autoplaced", "lib_id", "reference", "page", "shape", "bold",
           "italic", "thickness", "extends", "pin_numbers", "version", "generator",
           "generator_version", "paper", "embedded_fonts", "in_pos_files", "duplicate_pin_numbers_are_jumpers"}


def dumps(node, indent: int = 0) -> str:
    if not isinstance(node, list):
        return atom(node)
    if not node:
        return "()"
    head = node[0]
    simple = all(not isinstance(c, list) for c in node)
    if simple or (isinstance(head, str) and head in _INLINE and all(
            not isinstance(c, list) or all(not isinstance(cc, list) for cc in c) for c in node)):
        return "(" + " ".join(dumps(c) for c in node) + ")"
    pad = "\t" * (indent + 1)
    parts = [atom(c) for c in node if not isinstance(c, list)]
    out = "(" + " ".join(parts)
    for c in node:
        if isinstance(c, list):
            out += "\n" + pad + dumps(c, indent + 1)
    out += "\n" + "\t" * indent + ")"
    return out


def find(node, key):
    """First child list whose head is ``key``."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def S(*items):
    """Build a list node, converting the head to a symbol."""
    return [Sym(items[0]), *items[1:]]
