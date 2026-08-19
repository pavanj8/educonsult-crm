import os
from contextlib import asynccontextmanager

import app.models  # noqa: F401 — register ORM models with Base.metadata
from fastapi import FastAPI

from app.db.database import engine
from app.models.base import Base
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Test Agent harness uses DATABASE_OVERRIDE with an empty scratch SQLite file;
    # create tables so auth queries return 401 instead of unhandled 500s.
    if os.environ.get("DATABASE_OVERRIDE"):
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="EduConsult CRM", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth", tags=["auth"])


@app.get("/health")
def health():
    return {"status": "ok"}
