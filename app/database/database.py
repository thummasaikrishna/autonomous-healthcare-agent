"""
Database engine and session factory. Call init_db() once at application
startup to create tables if they do not already exist.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.database.models import Base
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized at %s", settings.database_url)
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        raise


@contextmanager
def get_db_session():
    session: SASession = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
