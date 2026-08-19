import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Allows the Test Agent's harness to point each run at an isolated scratch
# DB (via DATABASE_OVERRIDE) instead of mutating the real app.db.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_OVERRIDE", "sqlite:///./app.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
