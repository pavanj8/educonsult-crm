"""E52 task #241 -- per-tenant currency storage on the tenant row.

Epic E52 (Currency Display Configuration) provides the per-tenant display
currency that the rest of the platform (the E52 #242 formatting utility
and the E52 #243 amount display components) relies on to render loan /
fee amounts in the tenant's home currency without a live FX conversion
(Requirements §1 Currency).

This test pins down the storage layer that E52 task #241 owns:

* The ``tenants`` table carries a ``currency`` column (NOT NULL, VARCHAR(3),
  server default ``'INR'``) so the platform always has a usable display
  currency even before a tenant picks one.
* A tenant can override the default and store a non-INR currency that the
  frontend will use to render its loan / fee amounts.
* Multiple tenants are independent -- one switching to USD does not affect
  another tenant on EUR. This is the "per-tenant" guarantee that
  Requirements §1 names explicitly.

The dedicated ``PATCH /tenants/{id}/branding`` endpoint that *writes* to
this column is owned by sibling ticket E10 #110 and is NOT exercised
here -- this issue (#241) covers the field + migration only.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.i18n.currency import (
    DEFAULT_SUPPORTED_CURRENCY_CODES,
    normalize_currency_code,
)
from app.models.tenant import Tenant


def test_tenant_model_declares_currency_column():
    """The ``Tenant`` ORM model exposes a ``currency`` column with the E52 contract."""
    currency_column = inspect(Tenant).columns.get("currency")
    assert currency_column is not None, "Tenant model must declare a currency column"
    # NOT NULL: the platform always has a usable display currency.
    assert currency_column.nullable is False
    # VARCHAR(3): ISO 4217 three-letter code.
    assert currency_column.type.length == 3
    # Server default is "INR" so existing tenants that pre-date this column
    # backfill cleanly via the E10 #109 / E52 #241 migration.
    assert currency_column.server_default.arg == "INR"


def test_tenant_default_currency_is_INR(db_session):
    """A tenant created without an explicit currency falls back to ``'INR'``."""
    tenant = Tenant(name="Defaults Tenant", slug="defaults-e52-currency")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.currency == "INR"


def test_tenant_can_override_currency_to_usd(db_session):
    """The owner can pick a non-INR display currency for loan / fee amounts."""
    tenant = Tenant(
        name="USD Tenant",
        slug="usd-tenant",
        currency="USD",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.currency == "USD"


def test_tenant_currency_persists_across_reload(db_session):
    """A tenant's chosen currency round-trips through SQL untouched.

    The storage layer must not silently mutate the currency code (e.g.
    lower-casing it or normalising JPY to something else) because the
    frontend formatter (E52 #242) and amount display components (E52 #243)
    rely on receiving the exact ISO 4217 code the tenant selected.
    """
    tenant = Tenant(
        name="Round Trip",
        slug="round-trip-e52",
        currency="AUD",
    )
    db_session.add(tenant)
    db_session.commit()

    persisted_id = tenant.id
    db_session.expire_all()
    reloaded = db_session.get(Tenant, persisted_id)

    assert reloaded is not None
    assert reloaded.currency == "AUD"


def test_tenants_have_independent_currency_settings(db_session):
    """Two tenants can each pick a different display currency simultaneously.

    This is the core 'per-tenant' promise of Requirements §1: switching one
    tenant's currency must not bleed into another tenant's display.
    """
    india_tenant = Tenant(name="India Office", slug="india-e52", currency="INR")
    us_tenant = Tenant(name="US Office", slug="us-e52", currency="USD")
    uk_tenant = Tenant(name="UK Office", slug="uk-e52", currency="GBP")

    db_session.add_all([india_tenant, us_tenant, uk_tenant])
    db_session.commit()

    # Reload each row to confirm the codes persisted as written.
    db_session.expire_all()
    reloaded = {
        slug: db_session.get(Tenant, t.id)
        for slug, t in (
            ("india-e52", india_tenant),
            ("us-e52", us_tenant),
            ("uk-e52", uk_tenant),
        )
    }

    assert reloaded["india-e52"].currency == "INR"
    assert reloaded["us-e52"].currency == "USD"
    assert reloaded["uk-e52"].currency == "GBP"


@pytest.mark.parametrize(
    "currency_code",
    sorted(DEFAULT_SUPPORTED_CURRENCY_CODES),
)
def test_tenant_supports_all_default_iso_4217_codes(db_session, currency_code: str):
    """Every ISO 4217 code in the platform's curated default set round-trips.

    The frontend formatter (E52 #242) and amount display components (E52 #243)
    both treat any code in :data:`DEFAULT_SUPPORTED_CURRENCY_CODES` as a
    well-known display currency; the storage layer must accept them all
    without truncation or coercion.
    """
    normalized = normalize_currency_code(currency_code)
    assert normalized == currency_code

    tenant = Tenant(
        name=f"{normalized} Tenant",
        slug=f"e52-{normalized.lower()}",
        currency=normalized,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.currency == normalized


def test_tenant_currency_field_lives_on_tenants_table_after_migration(
    tmp_path, monkeypatch
):
    """The ``currency`` column survives an ``alembic upgrade head`` on a clean DB.

    Mirrors the broader Alembic upgrade test in
    ``backend/tests/database/test_alembic.py`` but scoped to the E52
    acceptance criterion: a freshly migrated tenants table must include
    the ``currency`` column that E52 #241 introduced, with the correct
    NOT NULL / VARCHAR(3) shape and the ``'INR'`` server default.
    """
    # Import lazily so this test does not depend on Alembic being on the
    # sys.path at collection time -- the rest of the suite already pulls
    # it in via the model imports above.
    from alembic import command
    from alembic.config import Config

    import app.db.database as database_module

    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))

    db_path = tmp_path / "e52_currency.db"
    database_url = f"sqlite:///{db_path}"
    # Swap the runtime database URL to an isolated SQLite file so the
    # migration runs against a known-clean state and does not touch any
    # other test's database. ``monkeypatch.setenv`` is undone at teardown
    # by pytest; the autouse ``_restore_database_module_after_reload``
    # fixture in conftest then rebinds the module's engine/get_db back
    # to the originals, so no state leaks into later tests.
    monkeypatch.setenv("DATABASE_OVERRIDE", database_url)
    importlib.reload(database_module)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            table_names = inspect(connection).get_table_names()
            assert "tenants" in table_names
            tenant_columns = {
                column["name"]
                for column in inspect(connection).get_columns("tenants")
            }
            assert "currency" in tenant_columns

            # Confirm the column type / nullability on the migrated
            # schema too -- a string-only check would pass even if the
            # migration dropped the NOT NULL constraint by accident.
            column_info = next(
                column
                for column in inspect(connection).get_columns("tenants")
                if column["name"] == "currency"
            )
            assert column_info["nullable"] is False
            assert (
                column_info["type"].length == 3
            ), "currency column must remain VARCHAR(3)"

            # A freshly inserted row with no currency supplied picks
            # up the server default ``'INR'`` -- this is what keeps
            # existing tenants rendering sensibly after the migration.
            connection.execute(
                text(
                    "INSERT INTO tenants (name, slug, created_at, updated_at) "
                    "VALUES ('E52 Migration', 'e52-migration', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.commit()
            stored = connection.execute(
                text("SELECT currency FROM tenants WHERE slug = 'e52-migration'")
            ).scalar_one()
            assert stored == "INR"
    finally:
        engine.dispose()
