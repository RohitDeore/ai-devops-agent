"""
tests/test_api.py — Integration tests for the Flask REST API
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# Set a deterministic API key before importing config/app
os.environ.setdefault("API_KEY", "test-secret-key")
os.environ.setdefault("SIMULATION_MODE", "true")
os.environ.setdefault("LOG_FILE_PATH", "logs/app.log")
os.environ.setdefault("REPORTS_DIR", "reports")

from app import create_app

API_KEY = "test-secret-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    # Override the key loaded by config so it matches our test env var
    import config
    config.API_KEY = API_KEY
    os.makedirs("logs", exist_ok=True)
    # Write minimal log content so /analyze and /report don't return 404
    with open("logs/app.log", "w") as f:
        f.write("2024-01-01 00:00:00 ERROR Database connection timeout\n")
        f.write("2024-01-01 00:00:01 CRITICAL service crashed unexpectedly\n")
        f.write("2024-01-01 00:00:02 WARNING memory usage at 90%\n")
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_no_auth_required(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_missing_api_key_returns_401(client):
    resp = client.get("/api/logs")
    assert resp.status_code == 401


def test_wrong_api_key_returns_401(client):
    resp = client.get("/api/logs", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /logs
# ---------------------------------------------------------------------------

def test_get_logs_success(client):
    resp = client.get("/api/logs", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["logs"], list)


def test_get_logs_tail(client):
    resp = client.get("/api/logs?lines=2", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] <= 2


def test_get_logs_invalid_lines(client):
    resp = client.get("/api/logs?lines=0", headers=HEADERS)
    assert resp.status_code == 400


def test_get_logs_lines_too_large(client):
    resp = client.get("/api/logs?lines=99999", headers=HEADERS)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /logs/write
# ---------------------------------------------------------------------------

def test_write_log_success(client):
    resp = client.post("/api/logs/write", json={"level": "INFO", "message": "test entry"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_write_log_invalid_level(client):
    resp = client.post("/api/logs/write", json={"level": "SUPERINFO", "message": "x"}, headers=HEADERS)
    assert resp.status_code == 400


def test_write_log_empty_message(client):
    resp = client.post("/api/logs/write", json={"level": "INFO", "message": ""}, headers=HEADERS)
    assert resp.status_code == 400


def test_write_log_message_too_long(client):
    resp = client.post("/api/logs/write", json={"level": "INFO", "message": "x" * 2001}, headers=HEADERS)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /analyze
# ---------------------------------------------------------------------------

def test_analyze_returns_issues(client):
    resp = client.post("/api/analyze", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "issues" in data


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------

def test_get_report_success(client):
    resp = client.get("/api/report", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "summary" in data


# ---------------------------------------------------------------------------
# /report/summary
# ---------------------------------------------------------------------------

def test_get_summary_success(client):
    resp = client.get("/api/report/summary", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "summary" in data


# ---------------------------------------------------------------------------
# /report/history
# ---------------------------------------------------------------------------

def test_report_history_success(client):
    resp = client.get("/api/report/history", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["reports"], list)


# ---------------------------------------------------------------------------
# 404 / 405
# ---------------------------------------------------------------------------

def test_unknown_endpoint_returns_404(client):
    resp = client.get("/api/nonexistent", headers=HEADERS)
    assert resp.status_code == 404


def test_wrong_method_returns_405(client):
    resp = client.delete("/api/health")
    assert resp.status_code == 405
