import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — register ORM models with Base.metadata
from app.db.database import SQLALCHEMY_DATABASE_URL, SessionLocal, engine
from app.models.base import Base
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.branches import router as branches_router
from app.routers.checklist import router as checklist_router
from app.routers.master_data import router as master_data_router
from app.routers.staff import router as staff_router
from app.routers.tenants import router as tenants_router
from app.seed.runner import seed_demo_data_if_empty


def _owns_schema_lifecycle() -> bool:
    """Return True when this process bootstraps the DB schema itself.

    True for the SQLite path (``DATABASE_OVERRIDE=sqlite://...`` or a sqlite
    URL in the config), where ``_ensure_sqlite_schema`` creates tables via
    ``Base.metadata.create_all`` at boot. False for the production Postgres
    path, where Alembic owns schema lifecycle and runs its own seeding in
    ``f7a8b9c0d1e2_create_stage_transitions_table``. Without this gate the
    Postgres app would attempt to seed before Alembic has created the table.
    """
    if os.environ.get("DATABASE_OVERRIDE", "").startswith("sqlite"):
        return True
    return SQLALCHEMY_DATABASE_URL.startswith("sqlite")


def _ensure_sqlite_schema() -> None:
    """For the SQLite/test path: create tables from ORM metadata.

    On the production Postgres path Alembic owns schema creation, so this is
    a no-op there. The Test Agent's black-box harness (and ad-hoc local
    runs) point ``DATABASE_OVERRIDE`` at SQLite and rely on this hook to
    materialise tables on first boot.
    """
    if _owns_schema_lifecycle():
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as session:
            seed_demo_data_if_empty(session)


def _seed_stage_transition_rules() -> None:
    """Idempotently seed the platform-default stage_transitions rows.

    Runs on every app boot when this process owns the schema lifecycle
    (SQLite/test path), so the Test Agent's black-box harness sees a
    populated rule table without having to run Alembic. The production
    Postgres path runs the same seeder via the Alembic migration
    (``f7a8b9c0d1e2``) and skips this hook entirely.

    The seeder only inserts rows that are not already present, so it is
    safe to call repeatedly and does not override tenant-side
    deactivations of default rules.
    """
    if not _owns_schema_lifecycle():
        return
    session: Session = SessionLocal()
    try:
        seed_default_stage_transitions(session)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_sqlite_schema()
    _seed_stage_transition_rules()
    yield


app = FastAPI(title="EduConsult CRM", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(applications_router, prefix="/applications", tags=["applications"])
app.include_router(checklist_router, prefix="/applications", tags=["checklist"])
app.include_router(branches_router, prefix="/branches", tags=["branches"])
app.include_router(staff_router, prefix="/staff", tags=["staff"])
app.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
app.include_router(master_data_router, prefix="/tenants", tags=["master-data"])


@app.get("/health")
def health():
    return {"status": "ok"}
