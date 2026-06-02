"""
config.py — Centralised configuration via environment variables
===============================================================
Load once at import time.  Every module should import from here
instead of reading os.environ directly.
"""

import os
import secrets
from dotenv import load_dotenv

# Load .env if present (silently ignored when missing)
load_dotenv()


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")


def _int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
FLASK_ENV   = os.getenv("FLASK_ENV", "production")
FLASK_HOST  = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT  = _int("FLASK_PORT", 5000)
FLASK_DEBUG = _bool("FLASK_DEBUG", False)

# Never enable DEBUG in production
if FLASK_ENV == "production":
    FLASK_DEBUG = False

# ---------------------------------------------------------------------------
# API security
# ---------------------------------------------------------------------------
# Falls back to a random key so the app still starts, but logs a warning.
_raw_key = os.getenv("API_KEY", "")
if not _raw_key or _raw_key == "change_me_to_a_random_secret":
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "API_KEY not set — using a random ephemeral key. "
        "Set API_KEY in .env for persistent access."
    )
    _raw_key = secrets.token_hex(32)

API_KEY = _raw_key

# ---------------------------------------------------------------------------
# Log file
# ---------------------------------------------------------------------------
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/app.log")

# ---------------------------------------------------------------------------
# Agent behaviour
# ---------------------------------------------------------------------------
SIMULATION_MODE  = _bool("SIMULATION_MODE", True)
USE_AI_REASONING = _bool("USE_AI_REASONING", False)
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Microsoft Azure AI Foundry
# Set USE_FOUNDRY=true to replace rule-based reasoning with Foundry agent
# ---------------------------------------------------------------------------
USE_FOUNDRY               = _bool("USE_FOUNDRY", False)
AZURE_FOUNDRY_ENDPOINT    = os.getenv("AZURE_FOUNDRY_ENDPOINT", "")   # e.g. https://<hub>.openai.azure.com/
AZURE_FOUNDRY_API_KEY     = os.getenv("AZURE_FOUNDRY_API_KEY", "")
AZURE_FOUNDRY_DEPLOYMENT  = os.getenv("AZURE_FOUNDRY_DEPLOYMENT", "gpt-4o-mini")  # your deployment name
AZURE_FOUNDRY_API_VERSION = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-12-01-preview")

# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------
REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")

# ---------------------------------------------------------------------------
# Rate limiting (requests per minute per IP)
# ---------------------------------------------------------------------------
RATE_LIMIT = _int("RATE_LIMIT", 60)

# ---------------------------------------------------------------------------
# Production infrastructure (only meaningful when SIMULATION_MODE=False)
# ---------------------------------------------------------------------------
KUBERNETES_NAMESPACE   = os.getenv("KUBERNETES_NAMESPACE", "default")
PAGERDUTY_ROUTING_KEY  = os.getenv("PAGERDUTY_ROUTING_KEY", "")
SLACK_WEBHOOK_URL      = os.getenv("SLACK_WEBHOOK_URL", "")
AWS_REGION             = os.getenv("AWS_REGION", "us-east-1")
