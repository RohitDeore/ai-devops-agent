"""
AI DevOps Autonomous Incident Response Agent
============================================
Flask Application Factory
"""

import os
import logging
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Shared limiter instance — imported by routes that need it
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app() -> Flask:
    """Create and configure the Flask application."""
    from config import FLASK_ENV, REPORTS_DIR, RATE_LIMIT

    # Ensure required directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Configure structured logging
    log_level = logging.DEBUG if FLASK_ENV == "development" else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join("logs", "agent.log"), mode="a"),
        ],
    )

    app = Flask(__name__)

    # Load secret key for session security
    app.config["SECRET_KEY"] = os.urandom(32)

    # Attach rate limiter
    limiter.init_app(app)
    # Store rate limit config so routes can reference it
    app.config["RATE_LIMIT"] = f"{RATE_LIMIT} per minute"

    # Register the API blueprint under /api prefix
    from app.api.routes import api_bp  # noqa: E402
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
