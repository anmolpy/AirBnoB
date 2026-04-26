"""
AirBnoB — Configuration
========================
backend/config.py

Three config classes, one per environment.
The factory in app.py selects the right one based on FLASK_ENV.
"""

from __future__ import annotations

import os
from datetime import timedelta


class BaseConfig:
    """Shared defaults inherited by all environments."""

    # JWT (Flask-JWT-Extended)
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "CHANGE_ME_IN_PROD")
    JWT_TOKEN_LOCATION: list[str] = ["cookies"]
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=1)
    GUEST_JWT_ACCESS_EXPIRES: timedelta = timedelta(minutes=15)
    JWT_COOKIE_SAMESITE: str = "Lax"
    JWT_COOKIE_CSRF_PROTECT: bool = True    # CSRF double-submit cookie pattern

    # Database
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/airbnob",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]  # Vite dev server (both hostnames are common during local dev)

    # Rate limiter storage
    LIMITER_STORAGE_URI: str = os.environ.get("LIMITER_STORAGE_URI", "memory://")

    # Table creation
    CREATE_TABLES_ON_STARTUP: bool = False


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    JWT_COOKIE_SECURE: bool = False     # HTTP ok in local dev
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///airbnob_dev.db",
    )
    CREATE_TABLES_ON_STARTUP: bool = True   # auto-create schema in dev


class TestingConfig(BaseConfig):
    TESTING: bool = True
    DEBUG: bool = True
    JWT_COOKIE_SECURE: bool = False
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"     # fast, isolated
    CREATE_TABLES_ON_STARTUP: bool = True
    JWT_COOKIE_CSRF_PROTECT: bool = False   # disable CSRF in test client
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(BaseConfig):
    DEBUG: bool = False                 # OWASP A05 — never True in prod
    JWT_COOKIE_SECURE: bool = True      # HTTPS only
    CORS_ORIGINS: list[str] = os.environ.get(
        "CORS_ORIGINS", ""
    ).split(",")                        # comma-separated list from env
    LIMITER_STORAGE_URI: str = os.environ.get(
        "LIMITER_STORAGE_URI",
        "redis://localhost:6379/0",     # swap memory:// for Redis in prod
    )
