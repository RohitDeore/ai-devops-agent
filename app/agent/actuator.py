"""
actuator.py — ACT phase of the Agent Loop
==========================================
Executes (or simulates) the remediation action chosen by the DecisionEngine.

In SIMULATION mode (default) every action is logged and an execution record
is returned — no real infrastructure calls are made.

In PRODUCTION mode (simulation_mode=False) real infrastructure calls are
attempted via subprocess (kubectl), requests (PagerDuty / Slack), and the
AWS CLI.  Each call falls back to a warning log on failure so the pipeline
never hard-crashes.
"""

import logging
import subprocess
import time
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


def _kubectl(*args: str, namespace: str = "default") -> bool:
    """Run a kubectl command.  Returns True on success."""
    try:
        cmd = ["kubectl", "-n", namespace, *args]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("kubectl error: %s", result.stderr.strip())
            return False
        logger.info("kubectl: %s", result.stdout.strip())
        return True
    except FileNotFoundError:
        logger.error("kubectl not found — is it installed and on PATH?")
        return False
    except subprocess.TimeoutExpired:
        logger.error("kubectl timed out.")
        return False


def _http_post(url: str, payload: dict, token: str = "") -> bool:
    """POST *payload* to *url*.  Returns True on HTTP 2xx."""
    try:
        import requests  # noqa: PLC0415
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Token {token}"
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if not resp.ok:
            logger.error("HTTP POST to %s failed: %s %s", url, resp.status_code, resp.text[:200])
            return False
        logger.info("HTTP POST to %s succeeded (%s).", url, resp.status_code)
        return True
    except Exception as exc:
        logger.error("HTTP POST to %s raised: %s", url, exc)
        return False


class ActionActuator:
    """
    Executes remediation actions for detected, analysed, and decided issues.

    Parameters
    ----------
    simulation_mode : bool
        When True, all actions are simulated (logged only).
        When False, placeholder hooks for real infrastructure calls are used.
    """

    def __init__(self, simulation_mode: bool = True) -> None:
        self.simulation_mode = simulation_mode
        self.action_log: List[Dict] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(
        self, issue_id: str, action: str, result: str, success: bool
    ) -> Dict:
        """Persist an action execution record in the internal log."""
        entry = {
            "issue_id":    issue_id,
            "action":      action,
            "result":      result,
            "success":     success,
            "executed_at": datetime.now().isoformat(),
            "mode":        "SIMULATION" if self.simulation_mode else "PRODUCTION",
        }
        self.action_log.append(entry)
        return entry

    def _sim(self, message: str) -> None:
        """Emit a simulation-mode log entry."""
        logger.info("[SIMULATION] %s", message)
        time.sleep(0.05)  # Tiny artificial delay to mimic real I/O

    # ------------------------------------------------------------------
    # Individual action handlers
    # ------------------------------------------------------------------

    def _restart_service(self, issue: Dict) -> Dict:
        """Restart the service associated with this issue."""
        svc = (
            issue.get("issue_type", "unknown-service")
            .replace("_ISSUE", "")
            .lower()
        )
        if self.simulation_mode:
            self._sim(f"Restarting '{svc}-service' …")
            result = f"Service '{svc}-service' restarted successfully (simulated)."
            success = True
        else:
            from config import KUBERNETES_NAMESPACE  # noqa: PLC0415
            success = _kubectl("rollout", "restart", f"deployment/{svc}", namespace=KUBERNETES_NAMESPACE)
            result = (
                f"kubectl rollout restart deployment/{svc} — {'succeeded' if success else 'FAILED (see logs)'}."
            )
        return self._record(issue["id"], "RESTART_SERVICE", result, success)

    def _failover_database(self, issue: Dict) -> Dict:
        """Trigger a database failover to the standby replica."""
        if self.simulation_mode:
            self._sim("Initiating database failover to standby replica …")
            result = "Database failover to standby replica completed (simulated)."
            success = True
        else:
            from config import AWS_REGION  # noqa: PLC0415
            try:
                cmd = [
                    "aws", "rds", "failover-db-cluster",
                    "--db-cluster-identifier", "main-cluster",
                    "--region", AWS_REGION,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                success = proc.returncode == 0
                result = (
                    f"AWS RDS failover {'initiated' if success else 'FAILED'}: "
                    f"{(proc.stdout or proc.stderr).strip()[:200]}"
                )
            except FileNotFoundError:
                success = False
                result = "aws CLI not found — manual failover required."
            except Exception as exc:
                success = False
                result = f"DB failover error: {exc}"
        return self._record(issue["id"], "FAILOVER_DATABASE", result, success)

    def _restart_db_connection(self, issue: Dict) -> Dict:
        """Reset the database connection pool."""
        if self.simulation_mode:
            self._sim("Resetting database connection pool …")
            result = "DB connection pool drained and re-initialised (simulated)."
            success = True
        else:
            from config import KUBERNETES_NAMESPACE  # noqa: PLC0415
            success = _kubectl("rollout", "restart", "deployment/db-proxy", namespace=KUBERNETES_NAMESPACE)
            result = f"DB connection pool reset via kubectl — {'succeeded' if success else 'FAILED (see logs)'}."
        return self._record(issue["id"], "RESTART_DB_CONNECTION", result, success)

    def _scale_up_resources(self, issue: Dict) -> Dict:
        """Trigger auto-scaling to add compute capacity."""
        if self.simulation_mode:
            self._sim("Triggering auto-scale: +2 nodes …")
            result = "Auto-scaling event triggered — 2 additional nodes provisioned (simulated)."
            success = True
        else:
            from config import KUBERNETES_NAMESPACE  # noqa: PLC0415
            # Scale the relevant deployment by 2 replicas
            svc = issue.get("issue_type", "app").replace("_ISSUE", "").lower()
            success = _kubectl(
                "scale", f"deployment/{svc}",
                "--replicas=+2",  # Note: kubectl patch is preferred for increment
                namespace=KUBERNETES_NAMESPACE,
            )
            result = f"Kubernetes scale-up for {svc} — {'succeeded' if success else 'FAILED (see logs)'}."
        return self._record(issue["id"], "SCALE_UP_RESOURCES", result, success)

    def _send_alert(self, issue: Dict) -> Dict:
        """Send an alert to the on-call channel (PagerDuty + Slack)."""
        message = (
            f"[{issue.get('severity')}] {issue.get('issue_type')} detected. "
            f"Root cause: {issue.get('root_cause', 'N/A')[:120]}"
        )
        if self.simulation_mode:
            self._sim(f"Sending alert → {message}")
            result = f"Alert delivered to on-call channel (simulated): {message[:100]}"
            success = True
        else:
            from config import PAGERDUTY_ROUTING_KEY, SLACK_WEBHOOK_URL  # noqa: PLC0415
            success = True

            # PagerDuty
            if PAGERDUTY_ROUTING_KEY:
                pd_payload = {
                    "routing_key": PAGERDUTY_ROUTING_KEY,
                    "event_action": "trigger",
                    "payload": {
                        "summary": message,
                        "severity": issue.get("severity", "error").lower(),
                        "source": "ai-devops-agent",
                    },
                }
                ok = _http_post("https://events.pagerduty.com/v2/enqueue", pd_payload)
                success = success and ok

            # Slack
            if SLACK_WEBHOOK_URL:
                ok = _http_post(SLACK_WEBHOOK_URL, {"text": f":rotating_light: {message}"})
                success = success and ok

            result = f"Alert sent via configured channels — {'all succeeded' if success else 'some failed (see logs)'}."
        return self._record(issue["id"], "SEND_ALERT", result, success)

    def _no_action(self, issue: Dict) -> Dict:
        """No remediation needed."""
        return self._record(issue["id"], "NO_ACTION", "System healthy — no action taken.", True)

    def _immediate_restart(self, issue: Dict) -> Dict:
        """Emergency (zero-grace) restart."""
        svc = (
            issue.get("issue_type", "unknown-service")
            .replace("_ISSUE", "")
            .lower()
        )
        if self.simulation_mode:
            self._sim(f"EMERGENCY restart of '{svc}-service' (zero-grace) …")
            result = f"CRITICAL: '{svc}-service' hard-restarted immediately (simulated)."
            success = True
        else:
            from config import KUBERNETES_NAMESPACE  # noqa: PLC0415
            # Delete all pods immediately; deployment controller recreates them
            success = _kubectl(
                "delete", "pods", "--selector", f"app={svc}",
                "--grace-period=0", "--force",
                namespace=KUBERNETES_NAMESPACE,
            )
            result = f"Emergency pod deletion for {svc} — {'succeeded' if success else 'FAILED (see logs)'}."
        return self._record(issue["id"], "IMMEDIATE_RESTART", result, success)

    # ------------------------------------------------------------------
    # Dispatch table
    # ------------------------------------------------------------------

    _HANDLERS = {
        "IMMEDIATE_RESTART":     _immediate_restart,
        "FAILOVER_DATABASE":     _failover_database,
        "RESTART_SERVICE":       _restart_service,
        "RESTART_DB_CONNECTION": _restart_db_connection,
        "RESTART_AUTH_SERVICE":  _restart_service,   # same handler, different label
        "SCALE_UP_RESOURCES":    _scale_up_resources,
        "SEND_ALERT":            _send_alert,
        "CREATE_INCIDENT":       _send_alert,         # treated as an alert for now
        "NO_ACTION":             _no_action,
    }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute_action(self, issue: Dict) -> Dict:
        """Route the issue to the correct handler and attach the result."""
        action = issue.get("action", "NO_ACTION")
        handler = self._HANDLERS.get(action, ActionActuator._no_action)
        action_result = handler(self, issue)
        issue["action_result"] = action_result
        return issue

    def execute_all_actions(self, issues: List[Dict]) -> List[Dict]:
        """Execute actions for every decided issue."""
        return [self.execute_action(issue) for issue in issues]

    def get_action_log(self) -> List[Dict]:
        """Return the cumulative log of all executed actions."""
        return self.action_log
