"""Spracheingabe ohne Fenster – über die Windows-Spracherkennung
(``Windows.Media.SpeechRecognition``, Python-Pakete ``winrt-…``).

* Erkennt in der Windows-Sprachsprache (bei deutschem Windows: Deutsch).
* Liefert laufend Zwischenstände (``on_partial``) und am Ende den ganzen Satz
  (``on_final``), sobald man kurz nichts mehr sagt.
* Braucht in Windows „Online-Spracherkennung“ (Einstellungen → Datenschutz →
  Spracherkennung) und Mikrofonzugriff für Desktop-Apps. Fehlt etwas, meldet
  ``on_error`` einen Grund – die Chat-Blase fällt dann auf Win + H zurück.

Alle Rückrufe kommen aus einem Hintergrund-Thread (per Qt-Signal weiterreichen).
Läuft nur unter Windows; ``available()`` ist sonst False.
"""

from __future__ import annotations

import asyncio
import datetime
import importlib.util
import threading
from typing import Callable

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.speech")

# Fehlergründe für on_error
PRIVACY = "privacy"          # „Online-Spracherkennung“ in Windows aus
MICROPHONE = "microphone"    # kein Mikrofon oder kein Zugriff
LANGUAGE = "language"        # Sprache nicht installiert / nicht unterstützt
NOTHING = "nothing"          # nichts verstanden
FAILED = "failed"            # alles andere (z. B. Paket fehlt, Netzwerk)

HRESULT_PRIVACY = 0x80045509
HRESULT_ACCESS_DENIED = 0x80070005
MAX_SECONDS = 60


def available() -> bool:
    return IS_WINDOWS and importlib.util.find_spec("winrt") is not None


def _hresult(exc: BaseException) -> int:
    code = getattr(exc, "winerror", None) or getattr(exc, "hresult", None)
    if code is None and exc.args and isinstance(exc.args[0], int):
        code = exc.args[0]
    return (code or 0) & 0xFFFFFFFF


def classify(exc: BaseException) -> str:
    code = _hresult(exc)
    if code == HRESULT_PRIVACY:
        return PRIVACY
    if code == HRESULT_ACCESS_DENIED:
        return MICROPHONE
    return FAILED


class Dictation:
    def __init__(self, on_partial: Callable[[str], None], on_final: Callable[[str], None],
                 on_error: Callable[[str], None], silence: float = 1.6) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self.silence = silence
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session = None
        self._cancelled = False

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not available() or self.running:
            return False
        self._cancelled = False
        self._thread = threading.Thread(target=self._thread_main, name="speech", daemon=True)
        self._thread.start()
        return True

    def cancel(self) -> None:
        """Abbrechen (Esc, Blase zu): nichts mehr melden."""
        self._cancelled = True
        self.finish()

    def finish(self) -> None:
        """Jetzt aufhören zuzuhören und das Bisherige abschließen."""
        loop, session = self._loop, self._session
        if loop is None or session is None:
            return

        async def stop() -> None:
            try:
                await session.stop_async()
            except Exception:  # noqa: BLE001 – war schon fertig
                pass

        try:
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(stop()))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ #
    def _emit(self, fn: Callable, *args) -> None:
        if not self._cancelled:
            try:
                fn(*args)
            except Exception:  # noqa: BLE001
                log.exception("Fehler im Rückruf der Spracheingabe")

    def _thread_main(self) -> None:  # pragma: no cover – nur unter Windows
        try:
            import winrt._winrt as _w

            try:
                _w.init_apartment(_w.MTA)
            except Exception:  # noqa: BLE001 – schon initialisiert
                pass
            asyncio.run(self._run())
        except Exception as exc:  # noqa: BLE001
            reason = classify(exc)
            log.warning("Spracheingabe nicht möglich (%s, 0x%08X)", reason, _hresult(exc))
            self._emit(self.on_error, reason)
        finally:
            self._loop = None
            self._session = None

    async def _run(self) -> None:  # pragma: no cover – nur unter Windows
        from winrt.windows.media.speechrecognition import (
            SpeechRecognitionResultStatus as Status,
            SpeechRecognitionScenario,
            SpeechRecognitionTopicConstraint,
            SpeechRecognizer,
        )

        self._loop = asyncio.get_running_loop()
        recognizer = SpeechRecognizer()
        recognizer.constraints.append(
            SpeechRecognitionTopicConstraint(SpeechRecognitionScenario.DICTATION, "dictation"))
        compiled = await recognizer.compile_constraints_async()
        if compiled.status != Status.SUCCESS:
            log.warning("Spracherkennung: Sprache nicht verfügbar (%s)", compiled.status)
            self._emit(self.on_error, LANGUAGE)
            return
        recognizer.timeouts.initial_silence_timeout = datetime.timedelta(seconds=8)
        recognizer.timeouts.end_silence_timeout = datetime.timedelta(seconds=1.2)
        session = recognizer.continuous_recognition_session
        session.auto_stop_silence_timeout = datetime.timedelta(seconds=self.silence)
        self._session = session

        parts: list[str] = []
        done = asyncio.Event()
        outcome: dict[str, object] = {}
        loop = self._loop

        def on_hypothesis(_sender, args) -> None:
            self._emit(self.on_partial, " ".join(parts + [args.hypothesis.text]).strip())

        def on_result(_sender, args) -> None:
            result = args.result
            if result.status == Status.SUCCESS and result.text:
                parts.append(result.text)
                self._emit(self.on_partial, " ".join(parts).strip())

        def on_completed(_sender, args) -> None:
            outcome["status"] = args.status
            loop.call_soon_threadsafe(done.set)

        tokens = (recognizer.add_hypothesis_generated(on_hypothesis),
                  session.add_result_generated(on_result),
                  session.add_completed(on_completed))
        try:
            await session.start_async()
            try:
                await asyncio.wait_for(done.wait(), MAX_SECONDS)
            except asyncio.TimeoutError:
                await session.stop_async()
                await asyncio.wait_for(done.wait(), 5)
        finally:
            recognizer.remove_hypothesis_generated(tokens[0])
            session.remove_result_generated(tokens[1])
            session.remove_completed(tokens[2])
            recognizer.close()

        text = " ".join(parts).strip()
        status = outcome.get("status")
        if text:
            self._emit(self.on_final, text)
        elif status == Status.MICROPHONE_UNAVAILABLE:
            self._emit(self.on_error, MICROPHONE)
        elif status in (Status.NETWORK_FAILURE, Status.UNKNOWN):
            self._emit(self.on_error, FAILED)
        elif status != Status.USER_CANCELED:
            self._emit(self.on_error, NOTHING)
