"""Termine aus dem klassischen Outlook (Desktop-App) über COM – nur lesend.

* Nutzt Outlook nur, wenn es schon läuft (es wird nie selbst gestartet).
* Das „neue Outlook“ hat keine COM-Schnittstelle – dort bitte den ICS-Link nutzen.
* Liest nur Betreff, Ort, Beginn und Ende (kein Text der Einladung – sonst fragt
  Outlook je nach Virenschutz nach einer Zugriffserlaubnis).
"""

from __future__ import annotations

import datetime as dt

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.outlook")


class OutlookError(Exception):
    pass


def available() -> bool:
    if not IS_WINDOWS:
        return False
    import importlib.util

    return importlib.util.find_spec("win32com") is not None


def _short_date_format() -> str:  # pragma: no cover – nur unter Windows
    """Outlooks Filter erwartet das kurze Datumsformat des Systems (z. B. dd.MM.yyyy)."""
    import ctypes

    buf = ctypes.create_unicode_buffer(80)
    pattern = "dd.MM.yyyy"
    if ctypes.WinDLL("kernel32").GetLocaleInfoEx(None, 0x1F, buf, 80):      # LOCALE_SSHORTDATE
        pattern = buf.value
    for token, fmt in (("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d")):
        pattern = pattern.replace(token, fmt)
    pattern = pattern.replace("M", "%#m").replace("d", "%#d")
    return pattern + " %H:%M"


def upcoming(hours: float = 24.0):  # pragma: no cover – nur unter Windows
    """Liste von calendar_events.Event aus dem Standardkalender."""
    from ..features.calendar_events import Event, find_link

    if not available():
        raise OutlookError("Für Outlook fehlt das Paket „pywin32“.")
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        try:
            outlook = win32com.client.GetActiveObject("Outlook.Application")
        except Exception:  # noqa: BLE001
            raise OutlookError("Outlook läuft gerade nicht (oder es ist das neue Outlook – "
                               "dann bitte den ICS-Link nutzen).") from None
        items = outlook.GetNamespace("MAPI").GetDefaultFolder(9).Items     # 9 = Kalender
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        now = dt.datetime.now()
        fmt = _short_date_format()
        start = (now - dt.timedelta(minutes=5)).strftime(fmt)
        end = (now + dt.timedelta(hours=hours)).strftime(fmt)
        found = items.Restrict(f"[Start] >= '{start}' AND [Start] <= '{end}'")
        events = []
        item = found.GetFirst()
        while item is not None and len(events) < 200:
            try:
                if getattr(item, "AllDayEvent", False) or getattr(item, "MeetingStatus", 0) in (5, 7):
                    item = found.GetNext()           # ganztägig oder abgesagt
                    continue
                begin = item.Start.replace(tzinfo=None).astimezone()
                stop = item.End.replace(tzinfo=None).astimezone()
                location = str(item.Location or "")
                events.append(Event(uid=str(getattr(item, "GlobalAppointmentID", "") or item.Subject),
                                    title=str(item.Subject or "Termin"), start=begin, end=stop,
                                    location=location, link=find_link(location)))
            except Exception:  # noqa: BLE001 – einzelne kaputte Einträge überspringen
                log.debug("Outlook-Eintrag übersprungen", exc_info=True)
            item = found.GetNext()
        return sorted(events, key=lambda e: e.start)
    finally:
        pythoncom.CoUninitialize()
