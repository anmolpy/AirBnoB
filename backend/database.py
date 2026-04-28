
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


# One db instance — imported by models and the app factory
db = SQLAlchemy(model_class=Base)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    
    session: Session = db.session
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()