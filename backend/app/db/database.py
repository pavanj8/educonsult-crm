import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Allows the Test Agent's harness to point each run at an isolated scratch
# DB (via DATABASE_OVERRIDE) instead of the shared Postgres instance.
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "DATABASE_OVERRIDE",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/educonsult",
    ),
)


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {"connect_args": _connect_args(database_url)}
    if database_url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_pre_ping"] = True
    return kwargs


engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs(SQLALCHEMY_DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
