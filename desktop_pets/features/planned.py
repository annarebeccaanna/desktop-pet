"""Geplante Funktionen (spätere Phasen). Sie erscheinen ausgegraut im Dialog,
damit man sieht, was kommt – schalten lassen sie sich noch nicht."""

from __future__ import annotations

from .base import planned

# Nützlich im Arbeitsalltag – Phase 3
planned("pomodoro", "Pomodoro", "25 / 5 Minuten, Tier legt sich zur Pause hin", "work", "später", "Phase 3", 10)
planned("reminders", "Erinnerungen", "Trinken, Aufstehen, Lüften", "work", "später", "Phase 3", 20)
planned("calendar_alerts", "Kalender", "Miaut vor Terminen (Outlook oder ICS)", "work", "später", "Phase 3", 30)
planned("event_webhook", "Build & Tests", "Lokaler Webhook: Freudensprung oder Fauchen", "work", "stumm", "Phase 3", 40)
planned("system_monitor", "Systemlast", "Hohe CPU: hechelt · wenig Akku: müde", "work", "ja", "Phase 3", 50)

# Chaos & Spaß – Phase 4 (ab Werk aus)
planned("gifts", "Geschenke", "Bringt Pixelmäuse und Wollknäuel", "chaos", "aus", "Phase 4", 10)
planned("icon_shuffle", "Icons schubsen", "Verschiebt Desktop-Icons (wiederherstellbar)", "chaos", "aus", "Phase 4", 20)
planned("cursor_steal", "Maus klauen", "Schnappt sich kurz den Mauszeiger", "chaos", "aus", "Phase 4", 30)

# Sozial & Erweiterbar
planned("multi_pet", "Mehrere Tiere", "Spielen, jagen und streiten miteinander", "social", "liegen", "Phase 4", 10)
planned("ai_chat", "KI-Chat", "Chatten über eigenen API-Key", "social", "immer aus", "Phase 5", 20)
planned("network_visit", "Besuche", "Besucht Desktops von Freunden", "social", "immer aus", "Phase 5", 30)
