"""Erkennt eine laufende Bildschirmfreigabe (Teams, Zoom, Webex, Browser …).

Windows meldet nicht, ob der Bildschirm gerade geteilt wird. Die Programme zeigen
aber währenddessen eine eigene Freigabe-Leiste („Freigabe beenden“, „… teilt
Ihren Bildschirm“). Diese Fenster werden hier über Regeln erkannt.

Die Regeln stehen in ``share_signatures.json`` (mitgeliefert) und können in
``%APPDATA%\\DesktopPets\\share_signatures.json`` ergänzt werden – ohne Codeänderung.
Eine Regel passt, wenn *alle* angegebenen Felder passen:

    {"app": "Microsoft Teams",
     "process": ["ms-teams.exe", "teams.exe"],     # Programmdatei (ohne Pfad)
     "title": "(?i)freigabe|sharing",               # regulärer Ausdruck auf den Fenstertitel
     "class": "…"}                                  # optional: Fensterklasse

Die Erkennung ist eine Heuristik (darum „experimentell“).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.share")

BUILTIN = Path(__file__).with_name("share_signatures.json")


@dataclass(frozen=True)
class WindowInfo:
    title: str
    class_name: str
    process: str          # z. B. "ms-teams.exe" (klein geschrieben)
    width: int = 0
    height: int = 0


@dataclass
class Rule:
    app: str
    processes: set[str] = field(default_factory=set)
    title: re.Pattern | None = None
    class_name: re.Pattern | None = None

    def matches(self, w: WindowInfo) -> bool:
        if self.processes and w.process.lower() not in self.processes:
            return False
        if self.title is not None and not self.title.search(w.title or ""):
            return False
        if self.class_name is not None and not self.class_name.search(w.class_name or ""):
            return False
        return bool(self.processes or self.title or self.class_name)


def parse_rules(data: list[dict]) -> list[Rule]:
    rules = []
    for entry in data:
        try:
            procs = entry.get("process") or []
            if isinstance(procs, str):
                procs = [procs]
            rules.append(Rule(
                app=str(entry.get("app", "?")),
                processes={p.lower() for p in procs},
                title=re.compile(entry["title"]) if entry.get("title") else None,
                class_name=re.compile(entry["class"]) if entry.get("class") else None,
            ))
        except (re.error, TypeError, AttributeError) as exc:
            log.warning("Freigabe-Regel übersprungen (%s): %s", exc, entry)
    return rules


def load_rules(user_file: Path | None = None) -> list[Rule]:
    data: list[dict] = []
    for path in (BUILTIN, user_file):
        if path is None or not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data.extend(raw.get("rules", raw) if isinstance(raw, dict) else raw)
        except (OSError, ValueError) as exc:
            log.warning("Freigabe-Regeln %s unlesbar: %s", path, exc)
    return parse_rules(data)


def find_sharing(windows: list[WindowInfo], rules: list[Rule]) -> list[tuple[str, WindowInfo]]:
    """Alle (App, Fenster), die auf eine Freigabe hindeuten."""
    out = []
    for w in windows:
        for rule in rules:
            if rule.matches(w):
                out.append((rule.app, w))
                break
    return out


def relevant_processes(rules: list[Rule]) -> set[str]:
    procs: set[str] = set()
    for r in rules:
        procs |= r.processes
    return procs


# --------------------------------------------------------------------------- #
# Windows: alle sichtbaren Top-Level-Fenster inkl. kleiner Werkzeugleisten
# --------------------------------------------------------------------------- #
def list_all_windows() -> list[WindowInfo]:
    if not IS_WINDOWS:
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    own_pid = os.getpid()
    names: dict[int, str] = {}
    out: list[WindowInfo] = []
    title_buf = ctypes.create_unicode_buffer(512)
    class_buf = ctypes.create_unicode_buffer(256)

    def process_name(pid: int) -> str:
        if pid in names:
            return names[pid]
        name = ""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value).lower()
            kernel32.CloseHandle(handle)
        names[pid] = name
        return name

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(raw, _lparam):
        hwnd = ctypes.c_void_p(raw)
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        user32.GetWindowTextW(hwnd, title_buf, 512)
        user32.GetClassNameW(hwnd, class_buf, 256)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        out.append(WindowInfo(title_buf.value, class_buf.value, process_name(pid.value),
                              rect.right - rect.left, rect.bottom - rect.top))
        return True

    user32.EnumWindows(callback, 0)
    return out


class ShareDetector:
    """Prüft regelmäßig, ob eine Freigabe läuft. ``lister`` ist in Tests ersetzbar."""

    def __init__(self, user_file: Path | None = None, lister=list_all_windows) -> None:
        self.user_file = user_file
        self.lister = lister
        self.rules = load_rules(user_file)

    def reload(self) -> None:
        self.rules = load_rules(self.user_file)

    def check(self) -> list[tuple[str, WindowInfo]]:
        try:
            return find_sharing(self.lister(), self.rules)
        except Exception:  # noqa: BLE001 – Erkennung darf die App nie stören
            log.exception("Freigabe-Erkennung fehlgeschlagen")
            return []

    def diagnose(self) -> list[WindowInfo]:
        """Sichtbare Fenster der bekannten Meeting-Programme und Browser (zum Nachschärfen der Regeln)."""
        procs = relevant_processes(self.rules)
        return [w for w in self.lister() if w.process in procs]
