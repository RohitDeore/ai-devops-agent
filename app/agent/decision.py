"""
decision.py — DECIDE phase of the Agent Loop
=============================================
Maps each analysed issue (severity + issue_type) to the most
appropriate remediation action using a two-dimensional priority matrix.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action matrix: severity → issue_type → action code
# ---------------------------------------------------------------------------
ACTION_MATRIX: Dict[str, Dict[str, str]] = {
    "CRITICAL": {
        "DEFAULT":         "IMMEDIATE_RESTART",
        "DATABASE_ISSUE":  "FAILOVER_DATABASE",
        "SERVICE_ISSUE":   "IMMEDIATE_RESTART",
        "RESOURCE_ISSUE":  "SCALE_UP_RESOURCES",
        "NETWORK_ISSUE":   "SEND_ALERT",
    },
    "ERROR": {
        "DEFAULT":         "RESTART_SERVICE",
        "DATABASE_ISSUE":  "RESTART_DB_CONNECTION",
        "TIMEOUT_ISSUE":   "RESTART_SERVICE",
        "AUTH_ISSUE":      "RESTART_AUTH_SERVICE",
        "SERVICE_ISSUE":   "RESTART_SERVICE",
        "API_ISSUE":       "RESTART_SERVICE",
        "NETWORK_ISSUE":   "SEND_ALERT",
        "RESOURCE_ISSUE":  "SEND_ALERT",
    },
    "WARNING": {
        "DEFAULT":         "SEND_ALERT",
        "RESOURCE_ISSUE":  "SEND_ALERT",
        "DATABASE_ISSUE":  "SEND_ALERT",
        "TIMEOUT_ISSUE":   "SEND_ALERT",
        "API_ISSUE":       "SEND_ALERT",
        "NETWORK_ISSUE":   "SEND_ALERT",
    },
}

# Human-readable description for each action code
ACTION_DESCRIPTIONS: Dict[str, str] = {
    "IMMEDIATE_RESTART":    "Immediately restart the affected service (zero-grace).",
    "FAILOVER_DATABASE":    "Initiate failover to the standby database replica.",
    "RESTART_SERVICE":      "Gracefully restart the affected service.",
    "RESTART_DB_CONNECTION":"Reset and reinitialise the database connection pool.",
    "RESTART_AUTH_SERVICE": "Restart the authentication / identity service.",
    "SCALE_UP_RESOURCES":   "Trigger auto-scaling to provision additional compute.",
    "SEND_ALERT":           "Send a PagerDuty / Slack alert to the on-call engineer.",
    "CREATE_INCIDENT":      "Open a P1 incident ticket for manual investigation.",
    "NO_ACTION":            "No action required — system is operating normally.",
}

# Urgency priority (lower number = act first)
ACTION_PRIORITY: Dict[str, int] = {
    "IMMEDIATE_RESTART":    1,
    "FAILOVER_DATABASE":    1,
    "RESTART_SERVICE":      2,
    "RESTART_DB_CONNECTION":2,
    "RESTART_AUTH_SERVICE": 2,
    "SCALE_UP_RESOURCES":   3,
    "SEND_ALERT":           4,
    "CREATE_INCIDENT":      5,
    "NO_ACTION":            10,
}


class DecisionEngine:
    """
    Determines the optimal remediation action for each analysed issue.

    The decision is driven by the two-dimensional ACTION_MATRIX above.
    Falls back to the severity-level DEFAULT when no specific rule
    exists for the given issue_type.
    """

    def decide_action(self, issue: Dict) -> Dict:
        """
        Resolve and attach the recommended action to *issue*.

        Side-effects:
            Sets issue["action"] and issue["action_description"].
        """
        severity = issue.get("severity", "INFO")
        issue_type = issue.get("issue_type", "GENERAL_ISSUE")

        if severity == "INFO":
            action = "NO_ACTION"
        else:
            severity_rules = ACTION_MATRIX.get(severity, {})
            action = severity_rules.get(
                issue_type,
                severity_rules.get("DEFAULT", "SEND_ALERT"),
            )

        issue["action"] = action
        issue["action_description"] = ACTION_DESCRIPTIONS.get(action, "Unknown action.")
        issue["action_priority"] = ACTION_PRIORITY.get(action, 9)

        logger.info(
            "Decision [%s | %s | %s] → %s",
            issue.get("id"),
            severity,
            issue_type,
            action,
        )
        return issue

    def decide_all(self, issues: List[Dict]) -> List[Dict]:
        """Apply decision logic to every issue and return them sorted by priority."""
        decided = [self.decide_action(issue) for issue in issues]
        # Sort so the most critical actions appear first
        decided.sort(key=lambda i: i.get("action_priority", 9))
        return decided

    @staticmethod
    def get_action_priority(action: str) -> int:
        """Expose the action priority for external consumers."""
        return ACTION_PRIORITY.get(action, 9)
