"""
analyzer.py — ANALYZE phase of the Agent Loop
==============================================
Scans each log line for known severity keywords, classifies the
issue type, and returns a structured list of detected problems for
the downstream reasoning and decision modules.
"""

import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — keyword banks for severity & issue classification
# ---------------------------------------------------------------------------

# Maps severity level to the keywords that indicate that level.
# Evaluated in priority order (CRITICAL first).
SEVERITY_KEYWORDS: Dict[str, List[str]] = {
    "CRITICAL": ["CRITICAL", "FATAL", "CRASH", "PANIC", "OUTOFMEMORY"],
    "ERROR":    ["ERROR", "FAILED", "FAILURE", "EXCEPTION", "REFUSED"],
    "WARNING":  ["WARNING", "WARN", "TIMEOUT", "DEGRADED", "SPIKE", "LATENCY"],
}

# Maps issue category to the keywords that identify it inside a log line.
ISSUE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "DATABASE_ISSUE":  ["DATABASE", "DB", "SQL", "QUERY", "REPLICA"],
    "TIMEOUT_ISSUE":   ["TIMEOUT"],
    "RESOURCE_ISSUE":  ["MEMORY", "CPU", "DISK", "PARTITION", "CAPACITY"],
    "AUTH_ISSUE":      ["AUTH", "AUTHENTICATION", "LOGIN", "TOKEN", "IDENTITY"],
    "SERVICE_ISSUE":   ["SERVICE", "MICROSERVICE", "CONTAINER", "WORKER", "NODE"],
    "API_ISSUE":       ["API", "ENDPOINT", "HTTP", "ROUTE", "REST"],
    "NETWORK_ISSUE":   ["NETWORK", "CONNECTION", "LATENCY", "DNS", "FIREWALL"],
}


class LogAnalyzer:
    """
    Analyses a list of raw log lines and extracts structured issue records.

    Each detected issue dict contains:
        id, timestamp, severity, issue_type, raw_log, line_number
    """

    def __init__(self) -> None:
        self.detected_issues: List[Dict] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_severity(self, log_line: str) -> str:
        """Return the most severe level found in *log_line*, or 'INFO'."""
        upper = log_line.upper()
        for severity, keywords in SEVERITY_KEYWORDS.items():
            if any(kw in upper for kw in keywords):
                return severity
        return "INFO"

    def _detect_issue_type(self, log_line: str) -> str:
        """Return the first matching issue category, or 'GENERAL_ISSUE'."""
        upper = log_line.upper()
        for issue_type, keywords in ISSUE_TYPE_KEYWORDS.items():
            if any(kw in upper for kw in keywords):
                return issue_type
        return "GENERAL_ISSUE"

    def _extract_timestamp(self, log_line: str) -> Optional[str]:
        """Parse a ISO-style timestamp from the log line if present."""
        pattern = r"\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}"
        match = re.search(pattern, log_line)
        return match.group() if match else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze_logs(self, log_lines: List[str]) -> List[Dict]:
        """
        Scan *log_lines* and return a list of issue dicts for every line
        whose severity is WARNING, ERROR, or CRITICAL.
        """
        issues: List[Dict] = []

        for idx, line in enumerate(log_lines):
            severity = self._detect_severity(line)

            # Only surface actionable entries
            if severity == "INFO":
                continue

            issue: Dict = {
                "id": f"ISSUE-{idx + 1:04d}",
                "timestamp": (
                    self._extract_timestamp(line)
                    or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ),
                "severity": severity,
                "issue_type": self._detect_issue_type(line),
                "raw_log": line,
                "line_number": idx + 1,
            }
            issues.append(issue)

        self.detected_issues = issues
        logger.info("Analysis complete — %d issue(s) detected.", len(issues))
        return issues

    def get_issue_summary(self) -> Dict:
        """Return a count of issues grouped by severity."""
        summary: Dict = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "total": 0}
        for issue in self.detected_issues:
            sev = issue.get("severity", "INFO")
            if sev in summary:
                summary[sev] += 1
            summary["total"] += 1
        return summary
