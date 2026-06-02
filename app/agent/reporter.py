"""
reporter.py — REPORT phase of the Agent Loop
=============================================
Generates structured JSON incident reports from fully-processed issue
dicts.  Produces both per-incident reports and an executive summary
suitable for export or display in the Streamlit dashboard.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

AGENT_VERSION = "1.0.0"


class IncidentReporter:
    """
    Generates structured incident reports for every processed issue.

    Reports follow the schema:
        incident_id, generated_at, issue, severity, root_cause,
        reasoning_method, action_taken, action_description,
        action_result, status, metadata
    """

    def __init__(self) -> None:
        self.reports: List[Dict] = []

    # ------------------------------------------------------------------
    # Per-incident report
    # ------------------------------------------------------------------

    def generate_report(self, issue: Dict) -> Dict:
        """
        Build a structured incident report dict from a single *issue*.

        The returned dict is self-contained and JSON-serialisable.
        """
        action_result_entry = issue.get("action_result", {})
        action_succeeded = action_result_entry.get("success", False)

        report: Dict = {
            "incident_id": (
                f"INC-{datetime.now().strftime('%Y%m%d')}-{issue.get('id', 'UNKNOWN')}"
            ),
            "generated_at": datetime.now().isoformat(),
            # --- What happened ---
            "issue": {
                "id":          issue.get("id"),
                "type":        issue.get("issue_type"),
                "raw_log":     issue.get("raw_log"),
                "timestamp":   issue.get("timestamp"),
                "line_number": issue.get("line_number"),
            },
            # --- Assessment ---
            "severity":         issue.get("severity", "UNKNOWN"),
            "root_cause":       issue.get("root_cause", "Root cause not determined."),
            "reasoning_method": issue.get("reasoning_method", "Rule-Based"),
            # --- Remediation ---
            "action_taken":       issue.get("action", "NO_ACTION"),
            "action_description": issue.get("action_description", ""),
            "action_result":      action_result_entry.get("result", "N/A"),
            # --- Outcome ---
            "status": "RESOLVED" if action_succeeded else "OPEN",
            # --- Metadata ---
            "metadata": {
                "simulation_mode": action_result_entry.get("mode", "SIMULATION"),
                "executed_at":     action_result_entry.get("executed_at", "N/A"),
                "agent_version":   AGENT_VERSION,
            },
        }

        self.reports.append(report)
        logger.info("Report generated: %s", report["incident_id"])
        return report

    def generate_all_reports(self, issues: List[Dict]) -> List[Dict]:
        """Generate a report for every issue in *issues*."""
        self.reports = []  # Reset for a fresh run
        return [self.generate_report(issue) for issue in issues]

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    def generate_summary_report(self, issues: List[Dict]) -> Dict:
        """
        Build an executive-level summary of the full agent run.

        Includes: totals, severity breakdown, actions taken, and a
        resolution rate suitable for an SLA dashboard.
        """
        total = len(issues)
        resolved = sum(
            1 for i in issues if i.get("action_result", {}).get("success", False)
        )

        severity_counts: Dict[str, int] = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0}
        action_counts:   Dict[str, int] = {}

        for issue in issues:
            sev = issue.get("severity", "UNKNOWN")
            if sev in severity_counts:
                severity_counts[sev] += 1

            action = issue.get("action", "NO_ACTION")
            action_counts[action] = action_counts.get(action, 0) + 1

        resolution_rate = f"{(resolved / total * 100):.1f}%" if total > 0 else "N/A"

        return {
            "summary_id":        f"SUM-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "generated_at":      datetime.now().isoformat(),
            "total_issues":      total,
            "resolved_issues":   resolved,
            "open_issues":       total - resolved,
            "resolution_rate":   resolution_rate,
            "severity_breakdown": severity_counts,
            "actions_taken":     action_counts,
            "agent_loop":        "Observe → Analyze → Reason → Decide → Act → Report",
            "agent_version":     AGENT_VERSION,
            "status":            "COMPLETED",
        }

    # ------------------------------------------------------------------
    # Serialisation helper
    # ------------------------------------------------------------------

    @staticmethod
    def to_json(data: Dict, indent: int = 2) -> str:
        """Serialise *data* to a pretty-printed JSON string."""
        return json.dumps(data, indent=indent, default=str)
