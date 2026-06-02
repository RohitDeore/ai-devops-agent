"""
reasoner.py — REASON phase of the Agent Loop
=============================================
Performs root-cause analysis (RCA) on each detected issue.

Two reasoning modes are supported:
  1. Rule-Based (default) — fast, deterministic, no external dependencies.
  2. AI-Powered (optional) — uses the OpenAI Chat Completions API for
     richer, context-aware explanations when an API key is provided.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule-based RCA knowledge base
# ---------------------------------------------------------------------------
# Structure: { issue_type: { keyword_in_log: root_cause_message, "DEFAULT": ... } }

ROOT_CAUSE_RULES: Dict[str, Dict[str, str]] = {
    "DATABASE_ISSUE": {
        "TIMEOUT":  "Database connection timeout — likely caused by network latency, "
                    "an overloaded DB server, or exhausted connection pool.",
        "FAILED":   "Database connection failure — check credentials, host reachability, "
                    "and whether the connection pool is saturated.",
        "REFUSED":  "Database server actively refused the connection — verify the DB "
                    "process is running and accepting connections on the expected port.",
        "REPLICA":  "Replica lag or failover event detected — primary/replica sync may "
                    "be broken; investigate replication health.",
        "DEFAULT":  "General database issue — inspect DB server health, slow-query logs, "
                    "and connection parameters.",
    },
    "TIMEOUT_ISSUE": {
        "API":        "API request timeout — a downstream service is overloaded or network "
                      "latency is abnormally high.",
        "CONNECTION": "Connection timeout — check network path, DNS resolution, and "
                      "firewall rules between services.",
        "DEFAULT":    "Generic timeout — system resources may be exhausted or a dependency "
                      "is unresponsive.",
    },
    "RESOURCE_ISSUE": {
        "MEMORY":   "High memory utilisation — likely a memory leak in the application "
                    "or insufficient heap allocation; consider a rolling restart.",
        "CPU":      "CPU saturation — a runaway process or sudden traffic spike; "
                    "profile the hot path and consider horizontal scaling.",
        "DISK":     "Disk capacity critical — implement log rotation / archiving "
                    "immediately to prevent write failures.",
        "DEFAULT":  "Resource constraint — review current utilisation dashboards and "
                    "adjust auto-scaling thresholds.",
    },
    "AUTH_ISSUE": {
        "FAILED":   "Authentication failure — invalid credentials supplied or the "
                    "identity provider is returning errors.",
        "TIMEOUT":  "Auth-service timeout — the identity provider (SSO / LDAP / OAuth "
                    "server) may be down or overloaded.",
        "TOKEN":    "Token validation failure — the JWT/session token may be expired, "
                    "malformed, or signed with a rotated key.",
        "DEFAULT":  "Authentication issue — check identity provider health and token "
                    "expiry configuration.",
    },
    "SERVICE_ISSUE": {
        "FAILED":   "Service health-check failure — the container/process has likely "
                    "crashed; trigger a graceful restart.",
        "REFUSED":  "Service port unreachable — the process may have exited or the "
                    "port binding has changed.",
        "DEFAULT":  "Service disruption — examine service logs for crash stack-traces "
                    "and restart if confirmed crashed.",
    },
    "API_ISSUE": {
        "TIMEOUT":  "API endpoint timeout — backend processing is taking too long; "
                    "check DB query performance and downstream dependencies.",
        "DEFAULT":  "API degradation detected — review endpoint metrics and error rates "
                    "to identify the slow path.",
    },
    "NETWORK_ISSUE": {
        "LATENCY":  "Elevated network latency — inspect routing between nodes; "
                    "a congested link or misconfigured MTU may be the cause.",
        "DEFAULT":  "Network connectivity issue — check DNS, firewall rules, VPC "
                    "routing, and NIC health.",
    },
    "GENERAL_ISSUE": {
        "DEFAULT":  "Unclassified issue — manual investigation required; attach full "
                    "stack-trace / correlation ID for faster triage.",
    },
}


class ReasoningEngine:
    """
    Enriches issue dicts with a *root_cause* explanation.

    Parameters
    ----------
    use_ai : bool
        If True, attempts to use OpenAI for reasoning (requires *api_key*).
    api_key : str or None
        API key for OpenAI. If None, falls back to rule-based reasoning.
    model : str
        OpenAI model to use (default: gpt-4o-mini).
    openai_api_key : str or None
        Deprecated alias for *api_key*; kept for backwards compatibility.
    """

    def __init__(
        self,
        use_ai: bool = False,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        openai_api_key: Optional[str] = None,  # backwards-compat alias
    ) -> None:
        # Support the old kwarg name
        resolved_key = api_key or openai_api_key
        self.use_ai = use_ai and bool(resolved_key)
        self.openai_api_key = resolved_key
        self.model = model
        self._openai_client = None

        if self.use_ai:
            self._init_openai_client()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_openai_client(self) -> None:
        """Try to import and initialise the OpenAI client."""
        try:
            import openai  # noqa: PLC0415

            self._openai_client = openai.OpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI reasoning engine initialised.")
        except ImportError:
            logger.warning(
                "openai package not installed — falling back to rule-based reasoning."
            )
            self.use_ai = False

    # ------------------------------------------------------------------
    # Reasoning strategies
    # ------------------------------------------------------------------

    def _rule_based_rca(self, issue: Dict) -> str:
        """Match the log entry against the RCA knowledge base."""
        issue_type = issue.get("issue_type", "GENERAL_ISSUE")
        raw_upper = issue.get("raw_log", "").upper()

        rules = ROOT_CAUSE_RULES.get(issue_type, ROOT_CAUSE_RULES["GENERAL_ISSUE"])

        for keyword, cause in rules.items():
            if keyword != "DEFAULT" and keyword in raw_upper:
                return cause

        return rules["DEFAULT"]

    def _ai_based_rca(self, issue: Dict, context_logs: List[str]) -> str:
        """
        Ask OpenAI for a root-cause explanation, using the surrounding
        log context to improve accuracy.  Falls back to rule-based on error.
        """
        try:
            context_snippet = "\n".join(context_logs[-10:])
            prompt = (
                "You are a senior DevOps engineer performing root-cause analysis.\n"
                "Provide a concise explanation (1–2 sentences) of why this issue occurred.\n\n"
                f"Issue type : {issue.get('issue_type')}\n"
                f"Severity   : {issue.get('severity')}\n"
                f"Log entry  : {issue.get('raw_log')}\n\n"
                f"Recent log context:\n{context_snippet}\n\n"
                "Root cause:"
            )
            response = self._openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("OpenAI RCA failed (%s) — using rule-based fallback.", exc)
            return self._rule_based_rca(issue)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze_issue(
        self, issue: Dict, context_logs: Optional[List[str]] = None
    ) -> Dict:
        """Enrich a single *issue* dict with root-cause information."""
        if self.use_ai and context_logs:
            root_cause = self._ai_based_rca(issue, context_logs)
            method = "AI-Powered (OpenAI)"
        else:
            root_cause = self._rule_based_rca(issue)
            method = "Rule-Based"

        issue["root_cause"] = root_cause
        issue["reasoning_method"] = method
        return issue

    def analyze_all_issues(
        self, issues: List[Dict], context_logs: Optional[List[str]] = None
    ) -> List[Dict]:
        """Enrich every issue in *issues* with a root-cause explanation."""
        for issue in issues:
            self.analyze_issue(issue, context_logs)
            logger.debug("RCA [%s]: %s", issue["id"], issue["root_cause"][:80])
        return issues
