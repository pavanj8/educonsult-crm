from datetime import datetime, timezone

from sqlalchemy import inspect

from app.models.branch import Branch


def test_branch_model_has_required_columns():
    column_names = {column.key for column in inspect(Branch).columns}
    assert column_names == {
        "id",
        "tenant_id",
        "name",
        "city",
        "created_at",
        "updated_at",
    }


def test_branch_persists_row(db_session):
    now = datetime.now(timezone.utc)
    branch = Branch(
        tenant_id=1,
        name="Mumbai HQ",
        city="Mumbai",
        created_at=now,
        updated_at=now,
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)

    assert branch.id is not None
    assert branch.tenant_id == 1
    assert branch.name == "Mumbai HQ"
    assert branch.city == "Mumbai"
    assert branch.created_at is not None
    assert branch.updated_at is not None


def test_branch_allows_same_name_in_different_tenants(db_session):
    now = datetime.now(timezone.utc)
    first = Branch(
        tenant_id=1,
        name="Main Office",
        city="Mumbai",
        created_at=now,
        updated_at=now,
    )
    second = Branch(
        tenant_id=2,
        name="Main Office",
        city="Delhi",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([first, second])
    db_session.commit()

    assert first.id is not None
    assert second.id is not None
    assert first.id != second.id
