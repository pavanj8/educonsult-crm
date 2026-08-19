"""CLI entry point: ``python -m app.seed``."""

from __future__ import annotations

import argparse
import json
import sys

from app.db.database import SessionLocal
from app.seed.catalog import DEMO_PASSWORD, PRIMARY_DEMO_EMAIL, get_demo_catalog
from app.seed.runner import SeedValidationError, seed_demo_data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load realistic demo data for all EduConsult CRM roles and tenants.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the demo catalog summary as JSON.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the catalog without opening a database session.",
    )
    return parser


def _catalog_summary() -> dict[str, object]:
    catalog = get_demo_catalog()
    return {
        "tenant_count": len(catalog.tenants),
        "branch_count": len(catalog.branches),
        "user_count": len(catalog.users),
        "default_password": DEMO_PASSWORD,
        "primary_login_email": PRIMARY_DEMO_EMAIL,
        "tenants": [
            {"id": tenant.id, "name": tenant.name, "slug": tenant.slug}
            for tenant in catalog.tenants
        ],
        "roles": sorted({user.role.value for user in catalog.users}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.validate_only:
            result = seed_demo_data(session=None)
        else:
            with SessionLocal() as session:
                result = seed_demo_data(session=session)
    except SeedValidationError as exc:
        print(f"Seed validation failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1

    summary = _catalog_summary()
    summary["roles_seeded"] = [role.value for role in result.roles_seeded]

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "Demo seed ready: "
            f"{result.tenant_count} tenants, "
            f"{result.branch_count} branches, "
            f"{result.user_count} users "
            f"({len(result.roles_seeded)} roles)."
        )
        print(f"Primary login: {PRIMARY_DEMO_EMAIL} / {DEMO_PASSWORD}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
