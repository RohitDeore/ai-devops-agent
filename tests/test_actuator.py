"""
tests/test_actuator.py — Unit tests for ActionActuator (simulation mode)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.actuator import ActionActuator


@pytest.fixture
def actuator():
    return ActionActuator(simulation_mode=True)


def _issue(action: str, issue_type: str = "SERVICE_ISSUE", severity: str = "ERROR") -> dict:
    return {
        "id": "T-001",
        "action": action,
        "issue_type": issue_type,
        "severity": severity,
        "root_cause": "Test root cause",
        "action_description": "Test description",
    }


def test_restart_service_simulated(actuator):
    issue = _issue("RESTART_SERVICE")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True
    assert "simulated" in result["action_result"]["result"].lower()


def test_immediate_restart_simulated(actuator):
    issue = _issue("IMMEDIATE_RESTART")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True


def test_failover_database_simulated(actuator):
    issue = _issue("FAILOVER_DATABASE", issue_type="DATABASE_ISSUE")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True
    assert "failover" in result["action_result"]["result"].lower()


def test_scale_up_resources_simulated(actuator):
    issue = _issue("SCALE_UP_RESOURCES", issue_type="RESOURCE_ISSUE")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True


def test_send_alert_simulated(actuator):
    issue = _issue("SEND_ALERT")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True


def test_no_action(actuator):
    issue = _issue("NO_ACTION")
    result = actuator.execute_action(issue)
    assert result["action_result"]["success"] is True
    assert "no action" in result["action_result"]["result"].lower()


def test_unknown_action_falls_back_to_no_action(actuator):
    issue = _issue("NONEXISTENT_ACTION")
    result = actuator.execute_action(issue)
    assert "action_result" in result


def test_action_log_populated(actuator):
    issues = [_issue("RESTART_SERVICE"), _issue("SEND_ALERT")]
    actuator.execute_all_actions(issues)
    log = actuator.get_action_log()
    assert len(log) == 2


def test_simulation_mode_flag_in_record(actuator):
    issue = _issue("NO_ACTION")
    result = actuator.execute_action(issue)
    assert result["action_result"]["mode"] == "SIMULATION"


def test_execute_all_actions_length(actuator):
    issues = [_issue("RESTART_SERVICE"), _issue("FAILOVER_DATABASE"), _issue("NO_ACTION")]
    results = actuator.execute_all_actions(issues)
    assert len(results) == 3
