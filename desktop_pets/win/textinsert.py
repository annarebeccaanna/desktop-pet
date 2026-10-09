"""Diktierten Text dort einfügen, wo man gerade schreibt – sonst in die Zwischenablage.

* ``focus_info()`` fragt per UI Automation (nur ctypes, keine Zusatzpakete) das
  Element mit dem Tastaturfokus ab: Ist es ein beschreibbares Textfeld?
  Zusätzlich zählt ein blinkender System-Cursor (``GetGUIThreadInfo``).
* ``decide()`` ist reine Logik (testbar): "insert" sicher / "insert" unsicher / "clipboard".
* ``paste()`` drückt Strg + V (per ``SendInput``).

Auf anderen Systemen: kein Fokus erkennbar → Zwischenablage.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.textinsert")

# UI-Automation-Kennungen
UIA_CONTROLTYPE = 30003
UIA_IS_KEYBOARD_FOCUSABLE = 30009
UIA_IS_ENABLED = 30010
UIA_IS_TEXT_PATTERN = 30040
UIA_IS_VALUE_PATTERN = 30043
UIA_VALUE_IS_READONLY = 30046
CT_COMBOBOX, CT_EDIT, CT_DOCUMENT = 50003, 50004, 50030

INSERT = "insert"
CLIPBOARD = "clipboard"


@dataclass
class FocusInfo:
    control_type: int = 0
    focusable: bool = False
    enabled: bool = True
    value_pattern: bool = False
    read_only: bool | None = None
    text_pattern: bool = False
    caret: bool = False           # blinkender System-Cursor im Vordergrund-Fenster
    known: bool = False           # UI Automation hat geantwortet


def decide(info: FocusInfo) -> tuple[str, bool]:
    """(was, sicher?) – „sicher“ heißt: bestimmt ein Eingabefeld, die alte Zwischenablage
    darf danach zurück. Unsicher wird zwar eingefügt, der Text bleibt aber zusätzlich
    in der Zwischenablage (falls das Einfügen ins Leere ging)."""
    if info.known and info.enabled and info.focusable:
        if info.control_type in (CT_EDIT, CT_COMBOBOX) and info.read_only is not True:
            return INSERT, True
        if info.value_pattern and info.read_only is False:
            return INSERT, True
        if info.control_type == CT_DOCUMENT and info.text_pattern and info.read_only is not True:
            return INSERT, False             # z. B. Word, Mail-Editor – oder eine Webseite
    if info.caret:
        return INSERT, False
    return CLIPBOARD, False


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #
class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16),
                ("d4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> "_GUID":
        import uuid

        u = uuid.UUID(text)
        g = cls()
        g.d1, g.d2, g.d3 = u.fields[0], u.fields[1], u.fields[2]
        g.d4[:] = list(u.bytes[8:])
        return g


class _VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                ("r3", ctypes.c_ushort), ("value", ctypes.c_longlong), ("extra", ctypes.c_longlong)]


CLSID_CUIAutomation = "{FF48DBA4-60EF-4201-AA87-54103EEF594E}"
IID_IUIAutomation = "{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}"
VT_BOOL, VT_I4 = 11, 3


def _vcall(obj: ctypes.c_void_p, index: int, restype, argtypes: tuple, *args):
    """Methode Nr. ``index`` aus der COM-Funktionstabelle aufrufen."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtbl[index])(obj, *args)


def _release(obj: ctypes.c_void_p) -> None:
    if obj:
        _vcall(obj, 2, ctypes.c_ulong, ())


def _uia_focus(info: FocusInfo) -> None:  # pragma: no cover – nur unter Windows
    ole32 = ctypes.WinDLL("ole32")
    oleaut32 = ctypes.WinDLL("oleaut32")
    ole32.CoInitializeEx(None, 2)                 # schon initialisiert (Qt) → harmlos
    automation = ctypes.c_void_p()
    ole32.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole32.CoCreateInstance.restype = ctypes.c_long
    hr = ole32.CoCreateInstance(ctypes.byref(_GUID.parse(CLSID_CUIAutomation)), None, 1 | 4,
                                ctypes.byref(_GUID.parse(IID_IUIAutomation)), ctypes.byref(automation))
    if hr != 0 or not automation:
        return
    element = ctypes.c_void_p()
    try:
        # IUIAutomation::GetFocusedElement (Platz 8 der Funktionstabelle)
        if _vcall(automation, 8, ctypes.c_long, (ctypes.POINTER(ctypes.c_void_p),),
                  ctypes.byref(element)) != 0 or not element:
            return

        def prop(pid: int):
            v = _VARIANT()
            # IUIAutomationElement::GetCurrentPropertyValue (Platz 10)
            if _vcall(element, 10, ctypes.c_long, (ctypes.c_int, ctypes.POINTER(_VARIANT)),
                      pid, ctypes.byref(v)) != 0:
                return None
            try:
                if v.vt == VT_BOOL:
                    return (v.value & 0xFFFF) != 0
                if v.vt == VT_I4:
                    return ctypes.c_int32(v.value & 0xFFFFFFFF).value
                return None
            finally:
                oleaut32.VariantClear(ctypes.byref(v))

        info.control_type = prop(UIA_CONTROLTYPE) or 0
        info.focusable = bool(prop(UIA_IS_KEYBOARD_FOCUSABLE))
        info.enabled = prop(UIA_IS_ENABLED) is not False
        info.value_pattern = bool(prop(UIA_IS_VALUE_PATTERN))
        info.read_only = prop(UIA_VALUE_IS_READONLY) if info.value_pattern else None
        info.text_pattern = bool(prop(UIA_IS_TEXT_PATTERN))
        info.known = True
    finally:
        _release(element)
        _release(automation)


def _caret() -> bool:  # pragma: no cover – nur unter Windows
    from ctypes import wintypes

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                    ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND),
                    ("hwndMenuOwner", wintypes.HWND), ("hwndMoveSize", wintypes.HWND),
                    ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]

    user32 = ctypes.WinDLL("user32")
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    return bool(user32.GetGUIThreadInfo(thread, ctypes.byref(gti)) and gti.hwndCaret)


def focus_info() -> FocusInfo:
    info = FocusInfo()
    if not IS_WINDOWS:
        return info
    try:
        _uia_focus(info)
    except Exception:  # noqa: BLE001 – Fokus unklar → lieber Zwischenablage
        log.exception("UI Automation nicht verfügbar")
    try:
        info.caret = _caret()
    except Exception:  # noqa: BLE001
        pass
    return info


def paste() -> bool:
    """Strg + V an das Fenster mit dem Fokus schicken."""
    if not IS_WINDOWS:
        return False
    user32 = ctypes.WinDLL("user32")
    VK_CONTROL, VK_V, KEYUP = 0x11, 0x56, 0x0002
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)
    return True
