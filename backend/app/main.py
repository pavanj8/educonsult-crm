import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401 — register ORM models with Base.metadata
from app.db.database import SQLALCHEMY_DATABASE_URL, engine
from app.models.base import Base
from app.routers.auth import router as auth_router
from app.routers.branches import router as branches_router
from app.routers.counseling import router as counseling_router
from app.routers.staff import router as staff_router
from app.routers.tenants import router as tenants_router


def _ensure_sqlite_schema() -> None:
    if os.environ.get("DATABASE_OVERRIDE", "").startswith("sqlite") or SQLALCHEMY_DATABASE_URL.startswith(
        "sqlite"
    ):
        Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_sqlite_schema()
    yield


app = FastAPI(title="EduConsult CRM", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(branches_router, prefix="/branches", tags=["branches"])
app.include_router(counseling_router, prefix="/counseling", tags=["counseling"])
app.include_router(staff_router, prefix="/staff", tags=["staff"])
app.include_router(tenants_router, prefix="/tenants", tags=["tenants"])


@app.get("/health")
def health():
    return {"status": "ok"}
