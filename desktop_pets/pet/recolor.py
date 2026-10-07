"""Fellfarbe ändern per Palettentausch (ohne Qt, testbar).

Die Paint-Palette (28 Felder) und die Abbildung von Original- auf Wunschfarben.
Linksklick = Hauptfarbe, Rechtsklick = Zweitfarbe (wie Vorder-/Hintergrundfarbe
in Paint). Die dunkle Schattierung der Hauptfarbe wird automatisch abgeleitet.
"""

from __future__ import annotations

# Klassische 28-Farben-Palette (zwei Reihen à 14), nur die RGB-Werte.
PAINT_PALETTE: list[str] = [
    "#000000", "#808080", "#800000", "#808000", "#008000", "#008080", "#000080",
    "#800080", "#808040", "#004040", "#0080FF", "#004080", "#8000FF", "#804000",
    "#FFFFFF", "#C0C0C0", "#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF",
    "#FF00FF", "#FFFF80", "#00FF80", "#80FFFF", "#8080FF", "#FF0080", "#FF8040",
]


def parse_hex(color: str) -> int:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError(f"Keine Farbe: {color!r}")
    return int(c, 16)


def to_hex(rgb: int) -> str:
    return f"#{rgb:06X}"


def shade(rgb: int, factor: float) -> int:
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    if factor < 1:
        r, g, b = (int(v * factor) for v in (r, g, b))
    else:
        r, g, b = (int(v + (255 - v) * (factor - 1)) for v in (r, g, b))
    return (max(0, min(255, r)) << 16) | (max(0, min(255, g)) << 8) | max(0, min(255, b))


def build_color_map(palette: dict[str, str], wanted: dict[str, str] | None) -> dict[int, int]:
    """Original-RGB → neue RGB. Leer, wenn nichts umgefärbt wird."""
    if not wanted:
        return {}
    out: dict[int, int] = {}
    if wanted.get("primary") and palette.get("primary"):
        new = parse_hex(wanted["primary"])
        out[parse_hex(palette["primary"])] = new
        if palette.get("primary_dark"):
            out[parse_hex(palette["primary_dark"])] = shade(new, 0.72)
    if wanted.get("secondary") and palette.get("secondary"):
        out[parse_hex(palette["secondary"])] = parse_hex(wanted["secondary"])
    # Nichts tun, wo Original = Wunsch
    return {k: v for k, v in out.items() if k != v}
