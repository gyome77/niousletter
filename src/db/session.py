from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base


_engine = None
_SessionLocal = None


def init_engine(db_url: str) -> None:
    global _engine, _SessionLocal
    if _engine is None:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(db_url, future=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=_engine)


def get_session():
    if _SessionLocal is None:
        raise RuntimeError("DB engine not initialized")
    return _SessionLocal()
