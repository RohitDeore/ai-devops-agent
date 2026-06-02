"""
tests/test_foundry_reasoner.py — Unit tests for FoundryReasoningEngine
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.foundry_reasoner import FoundryReasoningEngine, get_reasoning_engine
from app.agent.reasoner import ReasoningEngine


def _issue(issue_type="SERVICE_ISSUE", severity="ERROR", raw_log="service failed"):
    return {
        "id": "T-001",
        "issue_type": issue_type,
        "severity": severity,
        "raw_log": raw_log,
    }


# ---------------------------------------------------------------------------
# FoundryReasoningEngine — no credentials (fallback mode)
# ---------------------------------------------------------------------------

def test_foundry_no_credentials_falls_back_to_rule_based():
    engine = FoundryReasoningEngine(endpoint="", api_key="")
    assert engine._available is False


def test_foundry_fallback_still_produces_root_cause():
    engine = FoundryReasoningEngine(endpoint="", api_key="")
    issue = _issue("DATABASE_ISSUE", raw_log="Database connection TIMEOUT")
    result = engine.analyze_issue(issue)
    assert "root_cause" in result
    assert len(result["root_cause"]) > 5


def test_foundry_fallback_reasoning_method_is_rule_based():
    engine = FoundryReasoningEngine(endpoint="", api_key="")
    issue = _issue()
    result = engine.analyze_issue(issue)
    assert result.get("reasoning_method") == "Rule-Based"


def test_foundry_fallback_analyze_all_issues():
    engine = FoundryReasoningEngine(endpoint="", api_key="")
    issues = [_issue("AUTH_ISSUE"), _issue("RESOURCE_ISSUE")]
    results = engine.analyze_all_issues(issues)
    assert len(results) == 2
    for r in results:
        assert "root_cause" in r


# ---------------------------------------------------------------------------
# get_reasoning_engine factory
# ---------------------------------------------------------------------------

def test_factory_returns_rule_based_by_default(monkeypatch):
    monkeypatch.setattr("config.USE_FOUNDRY", False)
    monkeypatch.setattr("config.USE_AI_REASONING", False)
    monkeypatch.setattr("config.OPENAI_API_KEY", "")
    monkeypatch.setattr("config.AZURE_FOUNDRY_ENDPOINT", "")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_KEY", "")
    engine = get_reasoning_engine()
    assert isinstance(engine, ReasoningEngine)
    assert engine.use_ai is False


def test_factory_returns_openai_engine_when_configured(monkeypatch):
    monkeypatch.setattr("config.USE_FOUNDRY", False)
    monkeypatch.setattr("config.USE_AI_REASONING", True)
    monkeypatch.setattr("config.OPENAI_API_KEY", "sk-fake-key")
    monkeypatch.setattr("config.OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("config.AZURE_FOUNDRY_ENDPOINT", "")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_KEY", "")
    engine = get_reasoning_engine()
    assert isinstance(engine, ReasoningEngine)
    assert engine.use_ai is True


def test_factory_returns_foundry_engine_when_configured(monkeypatch):
    monkeypatch.setattr("config.USE_FOUNDRY", True)
    monkeypatch.setattr("config.AZURE_FOUNDRY_ENDPOINT", "https://fake.openai.azure.com/")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_KEY", "fake-azure-key")
    monkeypatch.setattr("config.AZURE_FOUNDRY_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_VERSION", "2024-12-01-preview")
    engine = get_reasoning_engine()
    assert isinstance(engine, FoundryReasoningEngine)


def test_foundry_engine_with_bad_credentials_does_not_crash(monkeypatch):
    """Even with bad credentials, the engine should not raise on init."""
    monkeypatch.setattr("config.USE_FOUNDRY", True)
    monkeypatch.setattr("config.AZURE_FOUNDRY_ENDPOINT", "https://fake.openai.azure.com/")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_KEY", "bad-key")
    monkeypatch.setattr("config.AZURE_FOUNDRY_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.setattr("config.AZURE_FOUNDRY_API_VERSION", "2024-12-01-preview")
    # Should not raise
    engine = get_reasoning_engine()
    assert engine is not None
