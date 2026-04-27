"""
AirBnoB — Flask Application Factory
=====================================
backend/app.py

Usage:
    # Development
    flask --app app run --debug

    # Production (Gunicorn)
    gunicorn "app:create_app('production')" -w 4 -b 0.0.0.0:5000

Environment variables required in production:
    FLASK_ENV=production
    JWT_SECRET_KEY=<strong-random-secret>
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/airbnob
"""

from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import DevelopmentConfig, ProductionConfig, TestingConfig
from database import db


# Extension instances (created once, bound per app in create_app)
jwt = JWTManager()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # limits are set per-route, not globally
    storage_uri=os.environ.get("LIMITER_STORAGE_URI", "memory://"),
)


# Application factory
def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure a Flask application instance.

    Args:
        config_name: 'development' | 'production' | 'testing'
                     Falls back to FLASK_ENV env var, then 'development'.

    Returns:
        A fully configured Flask app.
    """
    app = Flask(__name__)

    # Load config
    _load_config(app, config_name)

    # Safety check: hard-block debug mode in production
    _assert_production_safe(app)

    # Initialize extensions
    _init_extensions(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    @app.get("/health")
    def health_check():
        return jsonify({"message": "ok"}), 200

    # Create DB tables (dev/testing only)
    with app.app_context():
        if app.config.get("CREATE_TABLES_ON_STARTUP", False):
            db.create_all()

    return app


# Private helpers
def _load_config(app: Flask, config_name: str | None) -> None:
    """Select and apply the correct config class."""
    config_map = {
        "development": DevelopmentConfig,
        "production":  ProductionConfig,
        "testing":     TestingConfig,
    }

    resolved = config_name or os.environ.get("FLASK_ENV", "development")
    config_cls = config_map.get(resolved, DevelopmentConfig)
    app.config.from_object(config_cls)


def _assert_production_safe(app: Flask) -> None:
    """
    OWASP A05 — Security Misconfiguration guard.
    Raises immediately if debug mode is on or the JWT secret is default
    in a production environment.
    """
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        if app.debug:
            raise RuntimeError(
                "FATAL: Flask debug mode is enabled in a production environment. "
                "Set FLASK_DEBUG=0 or FLASK_ENV=production without debug=True."
            )
        if app.config.get("JWT_SECRET_KEY") == "CHANGE_ME_IN_PROD":
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY has not been set for production. "
                "Set the JWT_SECRET_KEY environment variable to a strong random secret."
            )


def _init_extensions(app: Flask) -> None:
    """Bind all Flask extensions to this app instance."""

    # SQLAlchemy — psycopg3 engine defined in database.py
    db.init_app(app)

    # JWT — HttpOnly cookie storage, CSRF double-submit pattern
    jwt.init_app(app)

    # Flask-Limiter — brute-force protection (OWASP A07)
    limiter.init_app(app)

    # CORS — only allow the configured frontend origin(s)
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=True,  # required for cookie-based JWT
    )


def _register_blueprints(app: Flask) -> None:
    """
    Import and register all route blueprints.
    Imports are local to avoid circular imports at module load time.
    """

    # Auth blueprints
    from auth.admin_auth import admin_auth_bp
    from auth.guest_auth import guest_auth_bp

    # Route blueprints (RBAC enforced inside each blueprint)
    from routes.admin_routes import admin_bp
    from routes.staff_routes import staff_bp
    from routes.guest_routes import guest_bp

    app.register_blueprint(admin_auth_bp,  url_prefix="/auth/staff")
    app.register_blueprint(guest_auth_bp,  url_prefix="/auth/guest")
    app.register_blueprint(admin_bp,       url_prefix="/admin")
    app.register_blueprint(staff_bp,       url_prefix="/staff")
    app.register_blueprint(guest_bp,       url_prefix="/guest")


def _register_error_handlers(app: Flask) -> None:
    """
    Consistent JSON error responses for all HTTP error codes.
    Prevents Flask's default HTML error pages from leaking stack traces.
    """

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(detail="Bad request."), 400

    @app.errorhandler(401)
    def unauthorized(e):
        # Deliberately vague — don't reveal what was wrong (OWASP A02)
        return jsonify(detail="Authentication required."), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(detail="Insufficient permissions."), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(detail="Resource not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(detail="Method not allowed."), 405

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify(detail="Validation error. Check your request body."), 422

    @app.errorhandler(429)
    def rate_limited(e):
        # Triggered by Flask-Limiter on login brute-force (OWASP A07)
        return jsonify(detail="Too many requests. Try again later."), 429

    @app.errorhandler(500)
    def internal_error(e):
        # Never return exception details in production
        return jsonify(detail="An internal server error occurred."), 500

    # JWT-specific error hooks (Flask-JWT-Extended)
    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_payload):
        return jsonify(detail="Token has expired."), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify(detail="Invalid token."), 401

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify(detail="Authentication required."), 401

    @jwt.needs_fresh_token_loader
    def needs_fresh(_jwt_header, _jwt_payload):
        return jsonify(detail="Fresh token required for this action."), 401


# Dev entry point
if __name__ == "__main__":
    app = create_app("development")
    app.run(port=5000)