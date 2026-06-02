"""
observer.py — OBSERVE phase of the Agent Loop
==============================================
Responsible for reading and monitoring the application log file.
Supports both full reads and tail-style incremental reads so the
agent can react to new log entries without re-processing old ones.
"""

import os
import logging
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)


class LogObserver:
    """
    Monitors a log file and surfaces log entries to the rest of the pipeline.

    Attributes:
        log_file_path (str): Absolute or relative path to the log file.
        _last_position (int): Byte offset of the last read position,
                              used for incremental (tail) reads.
    """

    def __init__(self, log_file_path: str) -> None:
        self.log_file_path = log_file_path
        self._last_position: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def read_all_logs(self) -> List[str]:
        """Return every non-empty line from the log file."""
        if not os.path.exists(self.log_file_path):
            logger.warning("Log file not found: %s", self.log_file_path)
            return []

        with open(self.log_file_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        return [line.rstrip("\n").strip() for line in lines if line.strip()]

    def read_new_logs(self) -> List[str]:
        """
        Return only log lines written since the last call (tail behaviour).
        Advances the internal file pointer after each read.
        """
        if not os.path.exists(self.log_file_path):
            return []

        with open(self.log_file_path, "r", encoding="utf-8") as fh:
            fh.seek(self._last_position)
            new_lines = fh.readlines()
            self._last_position = fh.tell()

        return [line.rstrip("\n").strip() for line in new_lines if line.strip()]

    def reset_position(self) -> None:
        """Reset the read pointer to the beginning of the file."""
        self._last_position = 0

    def get_log_stats(self) -> dict:
        """Return basic metadata about the monitored log file."""
        all_logs = self.read_all_logs()
        return {
            "total_lines": len(all_logs),
            "file_path": self.log_file_path,
            "file_exists": os.path.exists(self.log_file_path),
            "file_size_bytes": (
                os.path.getsize(self.log_file_path)
                if os.path.exists(self.log_file_path)
                else 0
            ),
            "last_read": datetime.now().isoformat(),
        }
