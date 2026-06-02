"""
tests/test_reporter.py — Unit tests for IncidentReporter
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.reporter import IncidentReporter


@pytest.fixture
def reporter():
    return IncidentReporter()


def _issue(severity: str = "ERROR", success: bool = True) -> dict:
    return {
        "id": "T-001",
        "severity": severity,
        "issue_type": "SERVICE_ISSUE",
        "raw_log": "service failed to start",
        "timestamp": "2024-01-01 00:00:00",
        "line_number": 1,
        "root_cause": "Service crashed due to OOM",
        "reasoning_method": "Rule-Based",
        "action": "RESTART_SERVICE",
        "action_description": "Restart the affected service",
        "action_result": {
            "success": success,
            "result": "Restarted (simulated)",
            "mode": "SIMULATION",
            "executed_at": "2024-01-01T00:00:00",
        },
    }


def test_generate_report_has_incident_id(reporter):
    report = reporter.generate_report(_issue())
    assert "incident_id" in report
    assert report["incident_id"].startswith("INC-")


def test_generate_report_has_required_fields(reporter):
    report = reporter.generate_report(_issue())
    for field in ("incident_id", "generated_at", "issue", "severity", "root_cause",
                  "action_taken", "action_result", "status", "metadata"):
        assert field in report, f"Missing field: {field}"


def test_resolved_status_on_success(reporter):
    report = reporter.generate_report(_issue(success=True))
    assert report["status"] == "RESOLVED"


def test_open_status_on_failure(reporter):
    report = reporter.generate_report(_issue(success=False))
    assert report["status"] == "OPEN"


def test_generate_all_reports(reporter):
    issues = [_issue("CRITICAL"), _issue("ERROR"), _issue("WARNING")]
    reports = reporter.generate_all_reports(issues)
    assert len(reports) == 3


def test_generate_all_resets_internal_list(reporter):
    reporter.generate_all_reports([_issue()])
    reporter.generate_all_reports([_issue(), _issue()])
    assert len(reporter.reports) == 2


def test_summary_total_count(reporter):
    issues = [_issue("CRITICAL"), _issue("ERROR"), _issue("WARNING")]
    summary = reporter.generate_summary_report(issues)
    assert summary["total_issues"] == 3


def test_summary_resolution_rate(reporter):
    issues = [_issue(success=True), _issue(success=False)]
    summary = reporter.generate_summary_report(issues)
    assert summary["resolution_rate"] == "50.0%"


def test_summary_empty_issues(reporter):
    summary = reporter.generate_summary_report([])
    assert summary["total_issues"] == 0
    assert summary["resolution_rate"] == "N/A"


def test_to_json_serializable(reporter):
    import json
    report = reporter.generate_report(_issue())
    json_str = reporter.to_json(report)
    parsed = json.loads(json_str)
    assert parsed["incident_id"] == report["incident_id"]
