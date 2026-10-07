"""Mausjagd: Das Tier folgt dem Zeiger und „fängt“ ihn, wenn er stillsteht.

Die Entscheidung trifft das Gehirn (pet/brain.py); hier liegen Schalter und Optionen.
"""

from __future__ import annotations

from .base import Feature, Option, register


@register
class MouseChase(Feature):
    id = "mouse_chase"
    name = "Mausjagd"
    description = "Folgt dem Mauszeiger und fängt ihn"
    default_enabled = True
    allowed_in_pause = False
    pause_label = "aus"
    order = 20
    options = [
        Option("eagerness", "Jagdlust", 100, kind="int", minimum=0, maximum=200, suffix=" %"),
    ]
