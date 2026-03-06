"""PII-masked logging with daily rotation."""

from __future__ import annotations

import logging
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class PIIMaskingFilter(logging.Filter):
    """Mask phone numbers, HKID numbers, and email addresses in log output."""

    _PHONE_RE = re.compile(r"\+852[\s-]?(\d)\d{3}[\s-]?\d{2}(\d{2})")
    _HKID_RE = re.compile(r"([A-Z]{1,2})\d{4}(\d{2})\(?\d\)?")
    _EMAIL_RE = re.compile(r"[\w.-]+@[\w.-]+\.\w+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)
        if record.args:
            record.args = tuple(
                self._mask(a) if isinstance(a, str) else a for a in record.args
            )
        return True

    def _mask(self, text: str) -> str:
        text = self._PHONE_RE.sub(r"+852 \1XXX XX\2", text)
        text = self._HKID_RE.sub(r"\1****\2(X)", text)
        text = self._EMAIL_RE.sub("[EMAIL]", text)
        return text


def setup_logging(
    tool_name: str,
    *,
    log_dir: str | Path = "/var/log/openclaw",
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configure logging with daily rotation and PII masking.

    Falls back to ~/Library/Logs/openclaw/ if /var/log/openclaw is not writable.
    """
    logger = logging.getLogger(f"openclaw.{tool_name}")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    pii_filter = PIIMaskingFilter()

    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
        test_file = log_path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except OSError:
        log_path = Path.home() / "Library" / "Logs" / "openclaw"
        log_path.mkdir(parents=True, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        log_path / f"{tool_name}.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(pii_filter)
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(pii_filter)
        logger.addHandler(console_handler)

    return logger
