"""
tests/test_analyzer.py — Unit tests for LogAnalyzer
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.analyzer import LogAnalyzer


@pytest.fixture
def analyzer():
    return LogAnalyzer()


def test_detects_critical_severity(analyzer):
    logs = ["2024-01-01 00:00:00 CRITICAL Database connection refused"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["severity"] == "CRITICAL" for i in issues)


def test_detects_error_severity(analyzer):
    logs = ["2024-01-01 00:00:00 ERROR service failed to start"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["severity"] == "ERROR" for i in issues)


def test_detects_warning_severity(analyzer):
    logs = ["2024-01-01 00:00:00 WARNING memory usage high"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["severity"] == "WARNING" for i in issues)


def test_info_lines_not_flagged(analyzer):
    logs = ["2024-01-01 00:00:00 INFO Application started successfully"]
    issues = analyzer.analyze_logs(logs)
    assert len(issues) == 0


def test_empty_log_returns_no_issues(analyzer):
    assert analyzer.analyze_logs([]) == []


def test_database_issue_type(analyzer):
    logs = ["2024-01-01 ERROR Database connection timeout"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["issue_type"] == "DATABASE_ISSUE" for i in issues)


def test_timeout_issue_type(analyzer):
    logs = ["2024-01-01 ERROR API request timeout after 30s"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["issue_type"] in ("TIMEOUT_ISSUE", "API_ISSUE") for i in issues)


def test_resource_issue_type(analyzer):
    logs = ["2024-01-01 WARNING memory usage at 95%"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["issue_type"] == "RESOURCE_ISSUE" for i in issues)


def test_auth_issue_type(analyzer):
    logs = ["2024-01-01 ERROR authentication failed for user admin"]
    issues = analyzer.analyze_logs(logs)
    assert any(i["issue_type"] == "AUTH_ISSUE" for i in issues)


def test_issue_has_required_fields(analyzer):
    logs = ["2024-01-01 ERROR something broke"]
    issues = analyzer.analyze_logs(logs)
    assert len(issues) > 0
    issue = issues[0]
    for field in ("id", "severity", "issue_type", "raw_log", "line_number"):
        assert field in issue, f"Missing field: {field}"


def test_get_issue_summary_after_analysis(analyzer):
    logs = [
        "2024-01-01 CRITICAL service crashed",
        "2024-01-01 ERROR db timeout",
    ]
    analyzer.analyze_logs(logs)
    summary = analyzer.get_issue_summary()
    assert summary["total"] >= 2


def test_multiple_logs_all_detected(analyzer):
    logs = [
        "2024-01-01 CRITICAL crash detected",
        "2024-01-01 ERROR connection refused",
        "2024-01-01 WARNING high cpu",
        "2024-01-01 INFO all good",
    ]
    issues = analyzer.analyze_logs(logs)
    assert len(issues) == 3  # INFO should not be counted
