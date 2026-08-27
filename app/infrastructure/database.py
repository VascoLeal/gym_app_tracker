"""
SQLAlchemy engine + session setup. This is the only file that knows how to
actually talk to Postgres — everything above this layer works through
Session objects it hands out, never raw connection strings.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class every SQLAlchemy ORM model inherits from."""


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: hands a route a Session, and guarantees it's
    closed afterwards even if the route raises an exception.
    Usage in a route: `db: Session = Depends(get_db)`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
