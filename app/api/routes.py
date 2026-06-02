"""
routes.py — Flask REST API
==========================
Provides the HTTP interface to the AI DevOps Incident Response Agent.

Endpoints
---------
GET  /api/health           — Liveness probe (no auth required)
GET  /api/logs             — Return monitored log lines
POST /api/analyze          — Run the full agent pipeline
GET  /api/report           — Full incident report (JSON)
GET  /api/report/summary   — Executive summary only
POST /api/logs/write        — Append a log entry (testing / demo)
GET  /api/report/history   — List persisted report files

Authentication
--------------
All endpoints except /health require the header:
    X-API-Key: <value of API_KEY in .env>
"""

import os
import json
import logging
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, current_app

import config
from app import limiter
from app.agent.observer import LogObserver
from app.agent.analyzer import LogAnalyzer
from app.agent.foundry_reasoner import get_reasoning_engine
from app.agent.decision import DecisionEngine
from app.agent.actuator import ActionActuator
from app.agent.reporter import IncidentReporter
from app.services.log_service import LogService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _safe_log_path(path: str) -> str:
    """Resolve and validate the log file path to prevent path traversal."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    abs_path = os.path.realpath(os.path.join(project_root, path))
    if not abs_path.startswith(project_root):
        raise ValueError("Invalid log file path — path traversal detected.")
    return abs_path


def require_api_key(f):
    """Decorator: reject requests that do not supply the correct API key."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key or key != config.API_KEY:
            logger.warning(
                "Unauthorized API access attempt from %s",
                request.remote_addr,  # IP only — no user-supplied data logged
            )
            return jsonify({"success": False, "error": "Unauthorized — invalid or missing X-API-Key header."}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Agent component instances
# ---------------------------------------------------------------------------

_LOG_FILE     = _safe_log_path(config.LOG_FILE_PATH)
_observer     = LogObserver(_LOG_FILE)
_analyzer     = LogAnalyzer()
_reasoner     = get_reasoning_engine()   # Foundry → OpenAI → Rule-Based (auto-selected)
_decision_eng = DecisionEngine()
_actuator     = ActionActuator(simulation_mode=config.SIMULATION_MODE)
_reporter     = IncidentReporter()
_log_svc      = LogService(_LOG_FILE)

# Determine reasoning mode label for /health
_REASONING_MODE = (
    "Azure AI Foundry (Multi-Step)" if config.USE_FOUNDRY
    else "OpenAI" if config.USE_AI_REASONING
    else "Rule-Based"
)


# ---------------------------------------------------------------------------
# Report persistence helper
# ---------------------------------------------------------------------------

def _persist_report(data: dict) -> str:
    """Save *data* as a JSON file under REPORTS_DIR.  Returns the file path."""
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(config.REPORTS_DIR, f"report_{ts}.json")
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    logger.info("Report persisted → %s", filepath)
    return filepath


# ---------------------------------------------------------------------------
# Pipeline helper
# ---------------------------------------------------------------------------

def _run_pipeline():
    """
    Execute: Observe → Analyze → Reason → Decide → Act.
    Returns (all_logs, issues).  Issues is an empty list when none detected.
    """
    all_logs = _observer.read_all_logs()
    issues   = _analyzer.analyze_logs(all_logs)

    if issues:
        issues = _reasoner.analyze_all_issues(issues, all_logs)
        issues = _decision_eng.decide_all(issues)
        issues = _actuator.execute_all_actions(issues)

    return all_logs, issues


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Liveness probe — no auth required."""
    return jsonify({
        "status":           "healthy",
        "agent":            "AI DevOps Incident Response Agent",
        "version":          "1.0.0",
        "simulation_mode":  config.SIMULATION_MODE,
        "reasoning_engine": _REASONING_MODE,
    })


@api_bp.route("/logs", methods=["GET"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def get_logs():
    """
    Fetch log lines from the monitored file.

    Query parameters
    ----------------
    lines : int (optional, 1–10000)
        Number of most-recent lines to return.  Omit to return all lines.
    """
    try:
        lines_param = request.args.get("lines", type=int)
        if lines_param is not None:
            if lines_param < 1 or lines_param > 10_000:
                return jsonify({"success": False, "error": "'lines' must be between 1 and 10000."}), 400

        all_logs = _observer.read_all_logs()
        if lines_param:
            all_logs = all_logs[-lines_param:]

        return jsonify({
            "success": True,
            "logs":    all_logs,
            "stats":   _observer.get_log_stats(),
            "count":   len(all_logs),
        })
    except Exception:
        logger.exception("GET /logs failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


@api_bp.route("/logs/write", methods=["POST"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def write_log():
    """
    Append a log entry to the monitored log file (for testing / demo).

    JSON body
    ---------
    { "level": "ERROR", "message": "Something went wrong" }
    """
    try:
        body    = request.get_json(silent=True) or {}
        level   = str(body.get("level", "INFO")).upper()
        message = str(body.get("message", "")).strip()

        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed_levels:
            return jsonify({"success": False, "error": f"'level' must be one of {sorted(allowed_levels)}."}), 400

        if not message:
            return jsonify({"success": False, "error": "'message' is required and must not be empty."}), 400
        if len(message) > 2000:
            return jsonify({"success": False, "error": "'message' must be 2000 characters or fewer."}), 400

        ok = _log_svc.append_log(level, message)
        if not ok:
            return jsonify({"success": False, "error": "Failed to write log entry."}), 500

        return jsonify({"success": True, "message": "Log entry written."})
    except Exception:
        logger.exception("POST /logs/write failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


@api_bp.route("/analyze", methods=["POST"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def analyze_logs():
    """
    Trigger the full agent pipeline and return detected issues with
    their root causes, decisions, and action results.
    Persists results to REPORTS_DIR automatically.
    """
    try:
        all_logs, issues = _run_pipeline()

        if not all_logs:
            return jsonify({"success": False, "error": "Log file is empty or missing."}), 404

        if not issues:
            return jsonify({
                "success":      True,
                "message":      "No actionable issues detected — system appears healthy.",
                "issues_count": 0,
                "issues":       [],
            })

        summary     = _analyzer.get_issue_summary()
        report_data = {"summary": summary, "issues": issues}
        saved_path  = _persist_report(report_data)

        return jsonify({
            "success":      True,
            "issues_count": len(issues),
            "summary":      summary,
            "issues":       issues,
            "report_saved": saved_path,
        })
    except Exception:
        logger.exception("POST /analyze failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


@api_bp.route("/report", methods=["GET"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def get_report():
    """
    Run the full pipeline and return a complete structured incident report
    covering every detected issue plus an executive summary.
    Persists results to REPORTS_DIR automatically.
    """
    try:
        all_logs, issues = _run_pipeline()
        incident_reports = _reporter.generate_all_reports(issues)
        summary          = _reporter.generate_summary_report(issues)

        report_data = {
            "summary":         summary,
            "incidents":       incident_reports,
            "total_incidents": len(incident_reports),
        }
        saved_path = _persist_report(report_data)

        return jsonify({
            "success":      True,
            "report_saved": saved_path,
            **report_data,
        })
    except Exception:
        logger.exception("GET /report failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


@api_bp.route("/report/summary", methods=["GET"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def get_summary():
    """Return the executive summary of the current system health."""
    try:
        _, issues = _run_pipeline()
        summary   = _reporter.generate_summary_report(issues)
        return jsonify({"success": True, "summary": summary})
    except Exception:
        logger.exception("GET /report/summary failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


@api_bp.route("/report/history", methods=["GET"])
@require_api_key
@limiter.limit(lambda: current_app.config["RATE_LIMIT"])
def get_report_history():
    """List all persisted report JSON files in REPORTS_DIR."""
    try:
        reports_dir = config.REPORTS_DIR
        if not os.path.isdir(reports_dir):
            return jsonify({"success": True, "reports": [], "count": 0})

        files = sorted(
            [f for f in os.listdir(reports_dir) if f.endswith(".json")],
            reverse=True,
        )
        return jsonify({"success": True, "reports": files, "count": len(files)})
    except Exception:
        logger.exception("GET /report/history failed")
        return jsonify({"success": False, "error": "Internal server error."}), 500


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@api_bp.app_errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"success": False, "error": "Rate limit exceeded. Try again later."}), 429


@api_bp.app_errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint not found."}), 404


@api_bp.app_errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "error": "Method not allowed."}), 405
