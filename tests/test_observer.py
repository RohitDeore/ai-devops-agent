"""
tests/test_observer.py — Unit tests for LogObserver
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.agent.observer import LogObserver


@pytest.fixture
def tmp_log(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2024-01-01 00:00:00 ERROR line one\n"
        "2024-01-01 00:00:01 WARNING line two\n"
        "2024-01-01 00:00:02 INFO line three\n",
        encoding="utf-8",
    )
    return str(log_file)


def test_read_all_logs_returns_list(tmp_log):
    obs = LogObserver(tmp_log)
    logs = obs.read_all_logs()
    assert isinstance(logs, list)
    assert len(logs) == 3


def test_read_all_logs_content(tmp_log):
    obs = LogObserver(tmp_log)
    logs = obs.read_all_logs()
    assert any("ERROR" in l for l in logs)
    assert any("WARNING" in l for l in logs)


def test_read_all_logs_missing_file():
    obs = LogObserver("/nonexistent/path/app.log")
    logs = obs.read_all_logs()
    assert logs == []


def test_get_log_stats_keys(tmp_log):
    obs = LogObserver(tmp_log)
    stats = obs.get_log_stats()
    assert "total_lines" in stats
    assert "file_size_bytes" in stats


def test_get_log_stats_line_count(tmp_log):
    obs = LogObserver(tmp_log)
    stats = obs.get_log_stats()
    assert stats["total_lines"] == 3


def test_read_new_logs_incremental(tmp_log):
    obs = LogObserver(tmp_log)
    # First read
    first = obs.read_new_logs()
    assert len(first) == 3

    # Append a new line
    with open(tmp_log, "a", encoding="utf-8") as f:
        f.write("2024-01-01 00:00:03 CRITICAL new entry\n")

    # Second read should return only the new line
    second = obs.read_new_logs()
    assert len(second) == 1
    assert "CRITICAL" in second[0]


def test_read_new_logs_no_duplicate_on_reread(tmp_log):
    obs = LogObserver(tmp_log)
    obs.read_new_logs()
    second = obs.read_new_logs()
    assert second == []
