"""
tests/test_decision.py — Unit tests for DecisionEngine
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.decision import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()


def _issue(severity: str, issue_type: str) -> dict:
    return {"id": "T-001", "severity": severity, "issue_type": issue_type}


def test_critical_database_maps_to_failover(engine):
    issue = _issue("CRITICAL", "DATABASE_ISSUE")
    result = engine.decide_action(issue)
    assert result["action"] in ("FAILOVER_DATABASE", "IMMEDIATE_RESTART")


def test_critical_resource_maps_to_restart_or_scale(engine):
    issue = _issue("CRITICAL", "RESOURCE_ISSUE")
    result = engine.decide_action(issue)
    assert result["action"] in ("IMMEDIATE_RESTART", "SCALE_UP_RESOURCES")


def test_error_service_maps_to_restart(engine):
    issue = _issue("ERROR", "SERVICE_ISSUE")
    result = engine.decide_action(issue)
    assert result["action"] in ("RESTART_SERVICE", "IMMEDIATE_RESTART", "SEND_ALERT")


def test_warning_maps_to_alert_or_scale(engine):
    issue = _issue("WARNING", "RESOURCE_ISSUE")
    result = engine.decide_action(issue)
    assert result["action"] in ("SCALE_UP_RESOURCES", "SEND_ALERT", "NO_ACTION")


def test_action_field_present(engine):
    issue = _issue("ERROR", "GENERAL_ISSUE")
    result = engine.decide_action(issue)
    assert "action" in result


def test_action_description_present(engine):
    issue = _issue("ERROR", "GENERAL_ISSUE")
    result = engine.decide_action(issue)
    assert "action_description" in result


def test_decide_all_returns_same_length(engine):
    issues = [
        _issue("CRITICAL", "DATABASE_ISSUE"),
        _issue("ERROR", "AUTH_ISSUE"),
        _issue("WARNING", "NETWORK_ISSUE"),
    ]
    results = engine.decide_all(issues)
    assert len(results) == 3


def test_unknown_issue_type_falls_back_gracefully(engine):
    issue = _issue("ERROR", "UNKNOWN_WEIRD_TYPE")
    result = engine.decide_action(issue)
    assert "action" in result
