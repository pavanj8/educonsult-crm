from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models.tenant import Tenant


def test_tenant_model_has_required_columns():
    column_names = {column.key for column in inspect(Tenant).columns}
    assert column_names == {
        "id",
        "name",
        "slug",
        "logo_url",
        "brand_color",
        "currency",
        "created_at",
        "updated_at",
    }


def test_tenant_persists_row(db_session):
    now = datetime.now(timezone.utc)
    tenant = Tenant(
        name="Apex EduConsult",
        slug="apex",
        logo_url="https://cdn.example.test/apex/logo.png",
        brand_color="#1A2B3C",
        currency="USD",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.name == "Apex EduConsult"
    assert tenant.slug == "apex"
    assert tenant.logo_url == "https://cdn.example.test/apex/logo.png"
    assert tenant.brand_color == "#1A2B3C"
    assert tenant.currency == "USD"
    assert tenant.created_at is not None
    assert tenant.updated_at is not None


def test_tenant_branding_fields_default_to_null(db_session):
    now = datetime.now(timezone.utc)
    tenant = Tenant(
        name="Plain Tenant",
        slug="plain",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.logo_url is None
    assert tenant.brand_color is None
    assert tenant.currency is None


def test_tenant_slug_is_unique(db_session):
    now = datetime.now(timezone.utc)
    first = Tenant(
        name="First Consultancy",
        slug="duplicate-slug",
        created_at=now,
        updated_at=now,
    )
    second = Tenant(
        name="Second Consultancy",
        slug="duplicate-slug",
        created_at=now,
        updated_at=now,
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
