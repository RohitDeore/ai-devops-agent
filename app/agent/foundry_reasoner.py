"""
foundry_reasoner.py — Microsoft Azure AI Foundry Reasoning Engine
=================================================================
Replaces simple rule-based "if ERROR → restart" logic with a genuine
multi-step AI agent that:

  Step 1 — Understands the incident context
  Step 2 — Identifies the probable root cause
  Step 3 — Evaluates possible remediation options
  Step 4 — Recommends the single best action with justification

Uses Azure AI Foundry (Azure OpenAI) via the openai SDK's AzureOpenAI client.
Falls back to rule-based reasoning gracefully if Foundry is unavailable.

Configuration (.env)
--------------------
USE_FOUNDRY=true
AZURE_FOUNDRY_ENDPOINT=https://<your-hub>.openai.azure.com/
AZURE_FOUNDRY_API_KEY=<your-azure-openai-key>
AZURE_FOUNDRY_DEPLOYMENT=gpt-4o-mini          # your deployment name
AZURE_FOUNDRY_API_VERSION=2024-12-01-preview
"""

import logging
from typing import Dict, List, Optional

from app.agent.reasoner import ReasoningEngine  # used as fallback

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — instructs the Foundry agent to reason in structured steps
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert DevOps Site Reliability Engineer acting as an autonomous incident response agent.

When given a log incident, you MUST reason through it in exactly these steps:

STEP 1 — UNDERSTAND: What service/component is affected and what went wrong?
STEP 2 — ROOT CAUSE: What is the most likely technical root cause? Be specific.
STEP 3 — OPTIONS: List 2-3 possible remediation actions with brief pros/cons.
STEP 4 — RECOMMENDATION: Which single action should be taken immediately and why?

Your response must follow this exact JSON format:
{
  "step1_context": "...",
  "step2_root_cause": "...",
  "step3_options": ["option 1", "option 2", "option 3"],
  "step4_recommendation": "...",
  "action_code": (
    "<one of: IMMEDIATE_RESTART | FAILOVER_DATABASE | RESTART_SERVICE | "
    "RESTART_DB_CONNECTION | RESTART_AUTH_SERVICE | SCALE_UP_RESOURCES | "
    "SEND_ALERT | NO_ACTION>"
  ),
  "confidence": "<HIGH | MEDIUM | LOW>",
  "summary": "One sentence root cause + recommended action."
}

Be concise, technical, and decisive. Prioritise system stability above all."""


class FoundryReasoningEngine:
    """
    Multi-step reasoning engine powered by Microsoft Azure AI Foundry.

    Parameters
    ----------
    endpoint : str
        Azure AI Foundry / Azure OpenAI endpoint URL.
    api_key : str
        Azure OpenAI API key.
    deployment : str
        Azure deployment name (e.g. 'gpt-4o-mini').
    api_version : str
        Azure OpenAI API version.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str = "gpt-4o-mini",
        api_version: str = "2024-12-01-preview",
    ) -> None:
        self.deployment  = deployment
        self._client     = None
        self._available  = False
        self._fallback   = ReasoningEngine(use_ai=False)

        self._init_client(endpoint, api_key, api_version)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_client(self, endpoint: str, api_key: str, api_version: str) -> None:
        if not endpoint or not api_key:
            logger.warning(
                "Azure Foundry credentials not set — falling back to rule-based reasoning."
            )
            return
        try:
            from openai import AzureOpenAI  # noqa: PLC0415
            self._client    = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            self._available = True
            logger.info(
                "Azure AI Foundry reasoning engine initialised (deployment: %s).",
                self.deployment,
            )
        except ImportError:
            logger.error("openai package not installed — pip install openai")
        except Exception as exc:
            logger.error("Foundry client init failed: %s", exc)

    # ------------------------------------------------------------------
    # Multi-step reasoning
    # ------------------------------------------------------------------

    def _build_user_prompt(self, issue: Dict, context_logs: List[str]) -> str:
        recent = "\n".join(context_logs[-15:]) if context_logs else "N/A"
        return (
            f"INCIDENT DETAILS\n"
            f"----------------\n"
            f"Severity   : {issue.get('severity', 'UNKNOWN')}\n"
            f"Issue Type : {issue.get('issue_type', 'UNKNOWN')}\n"
            f"Log Entry  : {issue.get('raw_log', '')}\n"
            f"Timestamp  : {issue.get('timestamp', 'N/A')}\n\n"
            f"RECENT LOG CONTEXT (last 15 lines)\n"
            f"-----------------------------------\n"
            f"{recent}\n\n"
            f"Perform your 4-step reasoning and return the JSON response."
        )

    def _call_foundry(self, issue: Dict, context_logs: List[str]) -> Dict:
        """Call Azure AI Foundry and parse the structured multi-step response."""
        import json  # noqa: PLC0415

        prompt = self._build_user_prompt(issue, context_logs)

        response = self._client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=600,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        return {
            "root_cause":          parsed.get("summary", parsed.get("step2_root_cause", "N/A")),
            "reasoning_steps": {
                "step1_context":       parsed.get("step1_context", ""),
                "step2_root_cause":    parsed.get("step2_root_cause", ""),
                "step3_options":       parsed.get("step3_options", []),
                "step4_recommendation": parsed.get("step4_recommendation", ""),
            },
            "foundry_action_code": parsed.get("action_code", ""),
            "confidence":          parsed.get("confidence", "MEDIUM"),
            "reasoning_method":    "Azure AI Foundry (Multi-Step)",
        }

    # ------------------------------------------------------------------
    # Public interface (mirrors ReasoningEngine)
    # ------------------------------------------------------------------

    def analyze_issue(
        self, issue: Dict, context_logs: Optional[List[str]] = None
    ) -> Dict:
        """Enrich a single issue with Foundry multi-step reasoning."""
        if not self._available:
            return self._fallback.analyze_issue(issue, context_logs)

        try:
            result = self._call_foundry(issue, context_logs or [])
            issue.update(result)

            # If Foundry recommends a different action, log it (advisory only —
            # DecisionEngine's matrix still makes the final call unless overridden)
            if result.get("foundry_action_code"):
                logger.info(
                    "[Foundry] Issue %s → recommended action: %s (confidence: %s)",
                    issue.get("id"),
                    result["foundry_action_code"],
                    result["confidence"],
                )
                # Override DecisionEngine action with Foundry's recommendation
                issue["action"] = result["foundry_action_code"]

            return issue

        except Exception as exc:
            logger.error(
                "Foundry reasoning failed for issue %s (%s) — using rule-based fallback.",
                issue.get("id"), exc,
            )
            return self._fallback.analyze_issue(issue, context_logs)

    def analyze_all_issues(
        self, issues: List[Dict], context_logs: Optional[List[str]] = None
    ) -> List[Dict]:
        """Enrich every issue with Foundry multi-step reasoning."""
        for issue in issues:
            self.analyze_issue(issue, context_logs)
        return issues


# ---------------------------------------------------------------------------
# Factory — returns the right engine based on config
# ---------------------------------------------------------------------------

def get_reasoning_engine():
    """
    Returns the appropriate reasoning engine based on .env config:

      USE_FOUNDRY=true          → FoundryReasoningEngine (Azure AI Foundry)
      USE_AI_REASONING=true     → ReasoningEngine (OpenAI)
      default                   → ReasoningEngine (rule-based)
    """
    import config  # noqa: PLC0415

    if config.USE_FOUNDRY and config.AZURE_FOUNDRY_ENDPOINT and config.AZURE_FOUNDRY_API_KEY:
        logger.info("Reasoning engine: Azure AI Foundry (multi-step agent)")
        return FoundryReasoningEngine(
            endpoint=config.AZURE_FOUNDRY_ENDPOINT,
            api_key=config.AZURE_FOUNDRY_API_KEY,
            deployment=config.AZURE_FOUNDRY_DEPLOYMENT,
            api_version=config.AZURE_FOUNDRY_API_VERSION,
        )

    if config.USE_AI_REASONING and config.OPENAI_API_KEY:
        logger.info("Reasoning engine: OpenAI (AI-powered RCA)")
        return ReasoningEngine(
            use_ai=True,
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_MODEL,
        )

    logger.info("Reasoning engine: Rule-Based (no AI credentials set)")
    return ReasoningEngine(use_ai=False)
