"""Gesprochene Satzzeichen beim Diktieren: „Punkt“ → „.“, „neue Zeile“ → Zeilenumbruch …

Reine Logik, testbar. „Punkt“ als Hauptwort („der springende Punkt“) bleibt stehen,
wenn ein Begleiter davor steht.
"""

from __future__ import annotations

import re

# (gesprochen, Zeichen) – längere Wendungen zuerst
COMMANDS: list[tuple[str, str]] = [
    ("neuer absatz", "\n\n"), ("neue zeile", "\n"), ("zeilenumbruch", "\n"), ("absatz", "\n\n"),
    ("fragezeichen", "?"), ("ausrufezeichen", "!"), ("doppelpunkt", ":"), ("semikolon", ";"),
    ("strichpunkt", ";"), ("gedankenstrich", " – "), ("bindestrich", "-"),
    ("klammer auf", "("), ("klammer zu", ")"), ("komma", ","), ("punkt", "."),
]
# Steht eins davon direkt davor, ist „Punkt“/„Komma“ ein Wort und kein Satzzeichen
NOUN_HINTS = {"der", "den", "dem", "des", "ein", "einen", "einem", "eines", "diesen", "diesem", "dieser",
              "jeden", "jedem", "welchen", "welchem", "springende", "springenden", "wichtige", "wichtigen",
              "nächste", "nächsten", "erste", "ersten", "zweite", "zweiten", "letzte", "letzten", "zum",
              "am", "beim", "im", "vom", "auf", "um"}
_WORD = re.compile(r"\S+")


def apply(text: str) -> str:
    if not text:
        return text
    out = text
    for spoken, mark in COMMANDS:
        pattern = re.compile(r"(?<![\wäöüÄÖÜß])(\S+\s+)?" + r"\s+".join(spoken.split()) + r"(?![\wäöüÄÖÜß])",
                             re.IGNORECASE)

        def repl(m: re.Match, mark=mark, single=" " not in spoken) -> str:
            before = m.group(1) or ""
            if single and before.strip().lower().strip(",.;:") in NOUN_HINTS:
                return m.group(0)                        # „der Punkt“ bleibt ein Wort
            return f"{before.rstrip()}\x00{mark}\x00"

        out = pattern.sub(repl, out)
    return _tidy(out)


def _tidy(text: str) -> str:
    text = re.sub(r"\s*\x00([.,:;!?)])\x00", r"\1", text)          # kein Leerzeichen vor Satzzeichen
    text = re.sub(r"\x00\(\x00\s*", " (", text)
    text = re.sub(r"\s*\x00(\n+)\x00\s*", r"\1", text)              # Umbrüche ohne Leerzeichen drumherum
    text = re.sub(r"\s*\x00-\x00\s*", "-", text)                    # „E Bindestrich Mail“ → „E-Mail“
    text = re.sub(r"\s*\x00 – \x00\s*", " – ", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"([.,:;!?)])(?=[^\s.,:;!?)\n\"'“”])", r"\1 ", text)   # Leerzeichen nach Satzzeichen
    # Großschreibung am Satzanfang
    text = re.sub(r"(^|[.!?]\s+|\n\s*)([a-zäöü])", lambda m: m.group(1) + m.group(2).upper(), text)
    return text.strip(" ")
