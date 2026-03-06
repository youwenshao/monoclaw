"""Folder watcher for automatic invoice ingestion.

Uses a polling approach with pathlib to monitor a directory for new
invoice files (images and PDFs). When new files appear, the configured
callback is invoked.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("openclaw.accounting.batch.watcher")

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class FolderWatcher:
    """Poll a directory for new invoice files and invoke a callback."""

    def __init__(
        self,
        watch_path: str | Path,
        callback: Callable[[Path], Any],
        poll_interval: float = 5.0,
        extensions: set[str] | None = None,
    ) -> None:
        self.watch_path = Path(watch_path)
        self.callback = callback
        self.poll_interval = poll_interval
        self.extensions = extensions or SUPPORTED_EXTENSIONS
        self._seen: set[Path] = set()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _scan(self) -> list[Path]:
        """Return new files that haven't been seen yet."""
        if not self.watch_path.exists():
            return []

        new_files: list[Path] = []
        for f in self.watch_path.iterdir():
            if f.is_file() and f.suffix.lower() in self.extensions and f not in self._seen:
                new_files.append(f)
                self._seen.add(f)

        return sorted(new_files)

    def _poll_loop(self) -> None:
        """Main polling loop running in a background thread."""
        logger.info("Watcher started on %s (interval: %.1fs)", self.watch_path, self.poll_interval)

        self._seen = set()
        for f in self.watch_path.iterdir():
            if f.is_file() and f.suffix.lower() in self.extensions:
                self._seen.add(f)

        while not self._stop_event.is_set():
            try:
                new_files = self._scan()
                for file_path in new_files:
                    logger.info("New file detected: %s", file_path.name)
                    try:
                        self.callback(file_path)
                    except Exception as exc:
                        logger.error("Callback error for %s: %s", file_path.name, exc)
            except Exception as exc:
                logger.error("Scan error: %s", exc)

            self._stop_event.wait(self.poll_interval)

        logger.info("Watcher stopped on %s", self.watch_path)

    def start_watching(self) -> None:
        """Start the watcher in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Watcher already running")
            return

        self.watch_path.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="invoice-watcher")
        self._thread.start()

    def stop_watching(self) -> None:
        """Signal the watcher to stop and wait for the thread to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 2)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


def create_watcher(
    watch_path: str | Path,
    callback: Callable[[Path], Any],
    poll_interval: float = 5.0,
) -> FolderWatcher:
    """Create a FolderWatcher instance.

    Args:
        watch_path: Directory to monitor for new files.
        callback: Function called with the Path of each new file.
        poll_interval: Seconds between directory scans.

    Returns a FolderWatcher (call .start_watching() to begin).
    """
    return FolderWatcher(
        watch_path=watch_path,
        callback=callback,
        poll_interval=poll_interval,
    )
