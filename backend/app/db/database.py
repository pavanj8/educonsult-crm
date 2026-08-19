import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args(SQLALCHEMY_DATABASE_URL),
    pool_pre_ping=not SQLALCHEMY_DATABASE_URL.startswith("sqlite"),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
