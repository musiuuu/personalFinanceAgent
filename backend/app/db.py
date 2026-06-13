"""Engine/session setup. SQLite in a single file; read-only mirror for NL-SQL."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url, connect_args={"check_same_thread": False}
        )
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def sqlite_path() -> str:
    """Filesystem path of the SQLite DB (for the read-only NL-SQL connection)."""
    url = get_settings().database_url
    return url.replace("sqlite:///", "", 1)
