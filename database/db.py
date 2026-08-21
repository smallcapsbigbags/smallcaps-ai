from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base


def normalise_database_url(url: str) -> str:
    """Normalise common Railway/Postgres URL variants for psycopg 3."""

    value = (url or "").strip()
    if not value:
        return "sqlite+pysqlite:///data/smallcaps.db"
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://") and "+" not in value.split(":", 1)[0]:
        value = "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


def create_database_engine(url: str, *, echo: bool = False) -> Engine:
    normalised = normalise_database_url(url)
    kwargs: dict[str, object] = {"echo": echo, "future": True, "pool_pre_ping": True}
    if normalised in {"sqlite://", "sqlite+pysqlite:///:memory:"}:
        kwargs.update(
            {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        )
    elif normalised.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(normalised, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
