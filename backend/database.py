"""
AirBnoB — Database
===================
backend/database.py

Single SQLAlchemy instance shared across all models and routes.
The engine is configured by the app factory via db.init_app(app).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    """Base class for all ORM models. Import this in each model file."""
    pass


# One db instance — imported by models and the app factory
db = SQLAlchemy(model_class=Base)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for a SQLAlchemy session outside of a request context.
    Use inside scripts, CLI commands, or background tasks.

    Usage:
        with get_session() as session:
            staff = session.scalars(select(Staff)).all()
    """
    session: Session = db.session
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()