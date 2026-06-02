"""
tests/test_reasoner.py — Unit tests for ReasoningEngine
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.reasoner import ReasoningEngine


@pytest.fixture
def reasoner():
    return ReasoningEngine(use_ai=False)


def _make_issue(issue_type: str, severity: str = "ERROR", raw_log: str = "test log") -> dict:
    return {
        "id": "TEST-001",
        "issue_type": issue_type,
        "severity": severity,
        "raw_log": raw_log,
    }


def test_rule_based_rca_database(reasoner):
    issue = _make_issue("DATABASE_ISSUE", raw_log="Database connection TIMEOUT")
    result = reasoner.analyze_issue(issue)
    assert "root_cause" in result
    assert len(result["root_cause"]) > 10


def test_rule_based_rca_timeout(reasoner):
    issue = _make_issue("TIMEOUT_ISSUE", raw_log="API timeout")
    result = reasoner.analyze_issue(issue)
    assert result["reasoning_method"] == "Rule-Based"
    assert "timeout" in result["root_cause"].lower() or "api" in result["root_cause"].lower()


def test_rule_based_rca_resource(reasoner):
    issue = _make_issue("RESOURCE_ISSUE", raw_log="memory usage 98%")
    result = reasoner.analyze_issue(issue)
    assert "root_cause" in result
    assert "memory" in result["root_cause"].lower()


def test_rule_based_rca_auth(reasoner):
    issue = _make_issue("AUTH_ISSUE", raw_log="authentication FAILED for user")
    result = reasoner.analyze_issue(issue)
    assert "root_cause" in result


def test_rule_based_rca_general_fallback(reasoner):
    issue = _make_issue("GENERAL_ISSUE", raw_log="some unknown log line")
    result = reasoner.analyze_issue(issue)
    assert "root_cause" in result
    assert len(result["root_cause"]) > 5


def test_reasoning_method_set(reasoner):
    issue = _make_issue("SERVICE_ISSUE", raw_log="service FAILED")
    result = reasoner.analyze_issue(issue)
    assert result.get("reasoning_method") == "Rule-Based"


def test_analyze_all_issues(reasoner):
    issues = [
        _make_issue("DATABASE_ISSUE", raw_log="DB TIMEOUT"),
        _make_issue("AUTH_ISSUE", raw_log="auth FAILED"),
    ]
    results = reasoner.analyze_all_issues(issues)
    assert len(results) == 2
    for r in results:
        assert "root_cause" in r


def test_no_ai_without_key():
    r = ReasoningEngine(use_ai=True, api_key=None)
    assert r.use_ai is False


def test_backwards_compat_openai_api_key_param():
    r = ReasoningEngine(use_ai=False, openai_api_key="sk-fake")
    assert r.openai_api_key == "sk-fake"
