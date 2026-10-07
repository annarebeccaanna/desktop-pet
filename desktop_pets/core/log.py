"""Logging nach %APPDATA%\\DesktopPets\\log.txt (rotierend, ohne Geheimnisse)."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from . import paths

# Alles, was wie ein API-Key aussieht, wird vor dem Schreiben maskiert.
_SECRET_RE = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{10,}|gsk_[A-Za-z0-9]{8,}|xai-[A-Za-z0-9]{8,})")


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = _SECRET_RE.sub("***", msg)
        if redacted != msg:
            record.msg, record.args = redacted, ()
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("desktop_pets")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        fh = RotatingFileHandler(paths.log_file(), maxBytes=512_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(_RedactFilter())
        logger.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(_RedactFilter())
    logger.addHandler(sh)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"desktop_pets.{name}")
