"""Kalender: ICS (inkl. Serien, Windows-Zeitzonen), Erinnerung vorher, Beitreten-Link, Pause."""

import datetime as dt
import json
import os

import pytest

from desktop_pets.features.calendar_events import Event, describe, due, find_link, parse_ics

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TZ = dt.timezone(dt.timedelta(hours=2))
ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VTIMEZONE
TZID:W. Europe Standard Time
BEGIN:STANDARD
DTSTART:16010101T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010101T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:weekly-1
SUMMARY:Weekly Sync
DTSTART;TZID=W. Europe Standard Time:20260105T100000
DTEND;TZID=W. Europe Standard Time:20260105T103000
RRULE:FREQ=WEEKLY;BYDAY=MO,FR
EXDATE;TZID=W. Europe Standard Time:20261016T100000
LOCATION:Microsoft Teams-Besprechung
DESCRIPTION:Teilnehmen: https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0?context=x
END:VEVENT
BEGIN:VEVENT
UID:urlaub
SUMMARY:Urlaub
DTSTART;VALUE=DATE:20261009
END:VEVENT
BEGIN:VEVENT
UID:weg
SUMMARY:Abgesagt: Alter Termin
DTSTART:20261009T080000Z
END:VEVENT
BEGIN:VEVENT
UID:mittag
SUMMARY:Mittag mit Anna
DTSTART:20261009T110000Z
LOCATION:Kantine
END:VEVENT
END:VCALENDAR
"""
NOW = dt.datetime(2026, 10, 9, 9, 57, tzinfo=TZ)          # Freitag


def test_parse_recurring_skips_all_day_and_cancelled():
    events = parse_ics(ICS, NOW)
    assert [e.title for e in events] == ["Weekly Sync", "Mittag mit Anna"]
    weekly = events[0]
    assert weekly.start == dt.datetime(2026, 10, 9, 10, 0, tzinfo=TZ)
    assert weekly.link.startswith("https://teams.microsoft.com/l/meetup-join/")
    # die nächste Woche ist per EXDATE ausgenommen
    assert parse_ics(ICS, NOW + dt.timedelta(days=7)) == [] or \
        all(e.title != "Weekly Sync" for e in parse_ics(ICS, NOW + dt.timedelta(days=7)))


def test_due_only_once_and_in_window():
    events = parse_ics(ICS, NOW)
    done: set[str] = set()
    first = due(events, NOW, 5, done)
    assert [e.title for e in first] == ["Weekly Sync"]
    done.update(e.key for e in first)
    assert due(events, NOW, 5, done) == []
    assert due(events, NOW - dt.timedelta(minutes=10), 5, set()) == []


def test_describe_and_links():
    e = Event("u", "Planung", NOW + dt.timedelta(minutes=5), location="Raum 3")
    assert describe(e, NOW).startswith("Planung (Raum 3) – in 5 Minuten, um ")
    assert find_link("bla https://us02web.zoom.us/j/123?pwd=x. danke") == "https://us02web.zoom.us/j/123?pwd=x"
    assert find_link("kein Link") == ""


QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def pa(tmp_path):
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from desktop_pets.core.app import PetApp

    app = PetApp(qapp, settings_path=tmp_path / "settings.json")
    app.qapp.quit = lambda: None
    app.start()
    yield app
    app.quit()


def wait(cond, ms=3000):
    from PySide6.QtCore import QEventLoop, QTimer

    for _ in range(ms // 20):
        if cond():
            return True
        loop = QEventLoop()
        QTimer.singleShot(20, loop.quit)
        loop.exec()
    return cond()


@pytest.fixture
def cal(pa):
    c = pa.features.get("calendar_alerts")
    c.now = lambda: NOW
    c.outlook_available = lambda: False
    c.fetch = lambda link: ICS.encode()
    return c


def test_ics_link_is_secret_and_reminder_has_join_button(pa, cal, tmp_path):
    assert cal.source() == ""
    cal.secret_set("ics", "https://outlook.office365.com/owa/calendar/geheim123/calendar.ics")
    assert cal.source() == "ics"
    pa.settings.save()
    assert "geheim123" not in (tmp_path / "settings.json").read_text(encoding="utf-8")
    messages = []
    cal.check_now(messages.append)
    assert wait(lambda: len(messages) == 2)
    assert "2 Termine" in messages[1] and "Weekly Sync" in messages[1]
    assert pa.bubble.isVisible() and "Weekly Sync" in pa.bubble.text.text()
    labels = [b.text() for b in pa.bubble.findChildren(QtWidgets.QPushButton) if b.isVisibleTo(pa.bubble)]
    assert "Beitreten" in labels


def test_reminder_waits_during_pause(pa, cal):
    cal.secret_set("ics", "https://example/cal.ics")
    pa.toggle_pause()
    cal.check_now(lambda m: None)
    assert wait(lambda: not cal.loading)
    assert pa.modes.pending_count == 1 and not pa.bubble.isVisible()


def test_errors_are_reported_not_raised(pa, cal):
    cal.secret_set("ics", "https://example/cal.ics")

    def broken(link):
        raise OSError("Zeitüberschreitung")

    cal.fetch = broken
    messages = []
    cal.check_now(messages.append)
    assert wait(lambda: len(messages) == 2)
    assert "Zeitüberschreitung" in messages[1] and cal.events == []


def test_options_dialog_has_secret_field_and_button(pa, cal):
    from desktop_pets.ui.settings_dialog import OptionsDialog

    dlg = OptionsDialog(pa, cal)
    edits = [w for w in dlg.findChildren(QtWidgets.QLineEdit) if w.echoMode() == QtWidgets.QLineEdit.Password]
    assert len(edits) == 1
    edits[0].setText("https://example/neu.ics")
    edits[0].editingFinished.emit()
    assert cal.keys.get("calendar_ics") == "https://example/neu.ics" and edits[0].text() == ""
    btn = [b for b in dlg.findChildren(QtWidgets.QPushButton) if b.text() == "Jetzt laden"][0]
    btn.click()
    assert wait(lambda: any("Termine" in r.text() for r in dlg.results))
    dlg.close()
