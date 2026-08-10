"""Database engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base


def build_engine(database_url: str) -> Engine:
    """Build an engine with safe defaults for SQLite and PostgreSQL."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    database_engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_schema() -> None:
    """Create tables for zero-config local use.

    Production deployments should disable this and apply Alembic migrations.
    """
    from app.db import tables  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide one transaction-aware SQLAlchemy session per request."""
    database = SessionLocal()
    try:
        yield database
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()
