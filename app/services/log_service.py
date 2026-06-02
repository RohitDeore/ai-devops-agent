"""
log_service.py — Service layer for log-file management
=======================================================
Provides write/append/clear operations on top of the raw log file so
the rest of the application never needs to touch the filesystem directly.
"""

import os
import logging
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class LogService:
    """
    Manages application log files: creation, appending, sizing, and clearing.

    Parameters
    ----------
    log_file_path : str
        Path to the log file this service manages.
    """

    def __init__(self, log_file_path: str) -> None:
        self.log_file_path = log_file_path
        self._ensure_log_dir()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _ensure_log_dir(self) -> None:
        """Create the parent directory if it does not already exist."""
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def append_log(self, level: str, message: str) -> bool:
        """
        Append a single formatted log entry to the file.

        Format: ``YYYY-MM-DD HH:MM:SS LEVEL message``
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"{timestamp} {level.upper()} {message}\n"
            with open(self.log_file_path, "a", encoding="utf-8") as fh:
                fh.write(entry)
            return True
        except OSError as exc:
            logger.error("Failed to append log entry: %s", exc)
            return False

    def append_bulk(self, entries: List[str]) -> int:
        """
        Append multiple raw log lines at once.

        Returns the number of lines successfully written.
        """
        written = 0
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as fh:
                for line in entries:
                    fh.write(line.rstrip("\n") + "\n")
                    written += 1
        except OSError as exc:
            logger.error("Bulk append failed after %d lines: %s", written, exc)
        return written

    # ------------------------------------------------------------------
    # Read / metadata operations
    # ------------------------------------------------------------------

    def get_log_size(self) -> int:
        """Return the number of lines currently in the log file."""
        if not os.path.exists(self.log_file_path):
            return 0
        with open(self.log_file_path, "r", encoding="utf-8") as fh:
            return sum(1 for _ in fh)

    def get_file_size_bytes(self) -> int:
        """Return the file size in bytes, or 0 if the file does not exist."""
        if not os.path.exists(self.log_file_path):
            return 0
        return os.path.getsize(self.log_file_path)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_logs(self) -> bool:
        """
        Truncate the log file to zero bytes.
        Use with caution — this is irreversible.
        """
        try:
            with open(self.log_file_path, "w", encoding="utf-8") as fh:
                fh.write("")
            logger.warning("Log file cleared: %s", self.log_file_path)
            return True
        except OSError as exc:
            logger.error("Failed to clear log file: %s", exc)
            return False
