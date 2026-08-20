"""
logging_setup.py — production logging to a rotating file under ~/.bumpspoof/logs.

Two rules matter here:

  1. Never write secrets. Pairing material, PSKs and device UDIDs must not land in
     a log a user might paste into a bug report, so a redaction filter masks any
     UUID / long-hex token before it is written.
  2. Never let logging itself crash the app. Setup is best-effort and idempotent;
     if the log directory cannot be created the app still runs (console only).
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

APP_DIR = os.path.join(os.path.expanduser("~"), ".bumpspoof")
LOG_DIR = os.path.join(APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "bumpspoof.log")

_MAX_BYTES = 1_000_000     # ~1 MB per file
_BACKUPS = 3               # keep a little history, bounded
_configured = False

# A device UDID (e.g. DEADBEEF-1122334455667788), a UUID, or any long hex run.
# Masking these keeps pairing identities and PSKs out of the log.
_SECRET_RE = re.compile(
    r"\b([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4,}(?:-[0-9A-Fa-f]{4,})*"   # dashed hex / UUID
    r"|[0-9A-Fa-f]{16,})\b"                                       # long bare hex
)


def redact(text: str) -> str:
    """Mask UDID / UUID / long-hex tokens in a string."""
    return _SECRET_RE.sub(lambda m: m.group(0)[:4] + "…redacted", text)


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(str(record.msg))
            if record.args:
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        except Exception:
            pass
        return True


def setup_logging(level: int = logging.INFO, console: bool = True) -> logging.Logger:
    """Configure the root 'bumpspoof' logger once. Safe to call repeatedly."""
    global _configured
    logger = logging.getLogger("bumpspoof")
    if _configured:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    redactor = _RedactFilter()

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        fh.addFilter(redactor)
        logger.addHandler(fh)
    except Exception:
        pass  # console-only is an acceptable fallback

    if console:
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        ch.addFilter(redactor)
        logger.addHandler(ch)

    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    base = setup_logging()
    return base.getChild(name) if name else base


def log_dir() -> str:
    return LOG_DIR


def open_log_dir() -> bool:
    """Open the log folder in the OS file browser. Returns True on success."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(LOG_DIR)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", LOG_DIR])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", LOG_DIR])
        return True
    except Exception:
        return False
