"""
run.py — Entry point for the AI DevOps Incident Response Agent (Flask API)
===========================================================================
Starts the Flask REST API server.

Usage
-----
    python run.py                       # default: host=0.0.0.0, port=5000
    python run.py --host 127.0.0.1 --port 8000
    python run.py --debug               # enable debug mode (dev only)

Dashboard
---------
Start the Streamlit dashboard in a separate terminal:
    streamlit run ui/dashboard.py
"""

import os
import argparse

# Ensure the logs/ directory exists before the app tries to open agent.log
os.makedirs("logs", exist_ok=True)

from app import create_app  # noqa: E402  (import after makedirs)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI DevOps Autonomous Incident Response Agent — Flask API"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # nosec B104 — server intentionally binds all interfaces
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode (development only)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

def _print_banner(host: str, port: int) -> None:
    api_base = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"  # nosec B104
    print()
    print("=" * 62)
    print("  🤖  AI DevOps Autonomous Incident Response Agent  v1.0.0")
    print("=" * 62)
    print(f"  Flask API   →  {api_base}")
    print()
    print("  Endpoints:")
    print(f"    GET   {api_base}/api/health")
    print(f"    GET   {api_base}/api/logs")
    print(f"    POST  {api_base}/api/analyze")
    print(f"    GET   {api_base}/api/report")
    print(f"    GET   {api_base}/api/report/summary")
    print()
    print("  Streamlit Dashboard (separate terminal):")
    print("    streamlit run ui/dashboard.py")
    print("=" * 62)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _parse_args()
    _print_banner(args.host, args.port)

    # Pull defaults from config (CLI args override)
    from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG  # noqa: E402
    host  = args.host  if args.host  != "0.0.0.0" or not FLASK_HOST else FLASK_HOST  # nosec B104
    port  = args.port  if args.port  != 5000       or not FLASK_PORT else FLASK_PORT
    debug = args.debug or FLASK_DEBUG

    app = create_app()
    app.run(host=host, port=port, debug=debug)
else:
    # Gunicorn / WSGI entry point: gunicorn run:app
    app = create_app()
