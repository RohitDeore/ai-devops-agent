"""
helpers.py — Shared utility functions
======================================
Small, stateless helpers used across multiple modules in the agent.
"""

import re
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Return a ``YYYY-MM-DD HH:MM:SS`` formatted timestamp."""
    return (dt or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def severity_icon(severity: str) -> str:
    """Map a severity label to a Unicode indicator suitable for terminals/UIs."""
    icons: Dict[str, str] = {
        "CRITICAL": "🔴",
        "ERROR":    "🟠",
        "WARNING":  "🟡",
        "INFO":     "🟢",
    }
    return icons.get(severity.upper(), "⚪")


def truncate(text: str, max_length: int = 120) -> str:
    """Truncate *text* to *max_length* characters, appending '…' if cut."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def safe_json_loads(json_str: str) -> Dict[str, Any]:
    """
    Parse *json_str* and return the resulting dict.
    Returns an empty dict on any parse error rather than raising.
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def pretty_json(data: Dict[str, Any]) -> str:
    """Serialise *data* to an indented JSON string."""
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# Log-line helpers
# ---------------------------------------------------------------------------

def extract_service_name(log_line: str) -> str:
    """
    Heuristically extract a service name from a log line.
    Returns ``'unknown-service'`` when no name is found.
    """
    patterns = [
        r"service[:\s]+([a-zA-Z0-9\-_]+)",
        r"for\s+([a-zA-Z0-9\-_]+-service)",
        r"([a-zA-Z0-9\-_]+-service)",
    ]
    for pattern in patterns:
        match = re.search(pattern, log_line, re.IGNORECASE)
        if match:
            return match.group(1)
    return "unknown-service"


def is_actionable(log_line: str) -> bool:
    """
    Quick check: return True when the log line contains any keyword
    that the analyzer would classify as WARNING, ERROR, or CRITICAL.
    """
    keywords = [
        "ERROR", "WARNING", "WARN", "TIMEOUT", "FAILED", "FAILURE",
        "CRITICAL", "FATAL", "EXCEPTION", "REFUSED", "DEGRADED",
        "CRASH", "OUTOFMEMORY",
    ]
    upper = log_line.upper()
    return any(kw in upper for kw in keywords)
