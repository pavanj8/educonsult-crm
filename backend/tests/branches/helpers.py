"""Branch test helpers."""

from datetime import datetime, timezone

from app.models.branch import Branch


def make_branch_payload(
    *,
    name: str = "Mumbai HQ",
    city: str = "Mumbai",
) -> dict[str, str]:
    return {"name": name, "city": city}


def seed_branch(
    db_session,
    *,
    tenant_id: int = 1,
    name: str = "Mumbai HQ",
    city: str = "Mumbai",
) -> Branch:
    now = datetime.now(timezone.utc)
    branch = Branch(
        tenant_id=tenant_id,
        name=name,
        city=city,
        created_at=now,
        updated_at=now,
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch
