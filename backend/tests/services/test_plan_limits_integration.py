"""End-to-end tests for the per-tier usage limit enforcement on HTTP endpoints
(E9 task #107).

These tests exercise the *black-box* HTTP surface:

* ``POST /branches`` -- E11 / Journey J4
* ``POST /staff`` -- E12 / Journey J5
* ``POST /students`` -- E17 / Journey J10
* ``POST /auth/register-student`` -- E16 / Journey J9

Each test seeds a tenant with an assigned plan whose cap is set just
below the threshold of what the test will attempt, then asserts that
the create endpoint returns ``422 Unprocessable Entity`` with the
plan-limit detail. The companion cases assert the create endpoint
succeeds when the tenant is at one-below-cap, when the tenant has no
plan at all, and when the assigned plan's cap is NULL (Enterprise).

The point of having both unit (in ``test_plan_limits.py``) and
integration tests is the same as for E2 / E7: the helper module is
locked in by the unit tests; the public HTTP contract (status code,
response detail, and which endpoints are guarded) is locked in here
without ever touching the helper directly.
"""

from datetime import datetime, timezone

from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.auth.register_student_helpers import make_register_student_payload
from tests.branches.helpers import make_branch_payload, seed_branch
from tests.factories.ids import next_test_id
from tests.staff.helpers import make_staff_payload


def _make_plan(
    db_session,
    *,
    code: PlanTier,
    name: str,
    max_branches: int | None,
    max_staff: int | None,
    max_students: int | None,
) -> Plan:
    now = datetime.now(timezone.utc)
    plan = Plan(
        code=code,
        name=name,
        max_branches=max_branches,
        max_staff=max_staff,
        max_students=max_students,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def _make_tenant(db_session, *, plan_id: int | None = None) -> Tenant:
    now = datetime.now(timezone.utc)
    seq = next_test_id()
    tenant = Tenant(
        name=f"Tenant {seq}",
        slug=f"tenant-{seq}",
        plan_id=plan_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def test_post_branches_rejects_when_branch_cap_reached(
    client, db_session, override_authenticated_user
):
    """``POST /branches`` returns 422 when the tenant is already at its branch cap."""
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    seed_branch(db_session, tenant_id=tenant.id)  # tenant already at cap

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post("/branches", json=make_branch_payload(name="Branch 2", city="Delhi"))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "starter" in detail
    assert "branches" in detail
    assert "1" in detail


def test_post_branches_succeeds_when_one_below_branch_cap(
    client, db_session, override_authenticated_user
):
    """``POST /branches`` returns 201 when the tenant is one below its cap."""
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.GROWTH,
        name="Growth",
        max_branches=2,
        max_staff=10,
        max_students=200,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    seed_branch(db_session, tenant_id=tenant.id)

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post("/branches", json=make_branch_payload(name="Branch 2", city="Delhi"))

    assert response.status_code == 201


def test_post_branches_succeeds_when_plan_has_no_branch_cap(
    client, db_session, override_authenticated_user
):
    """Enterprise (NULL cap) never enforces the branch limit."""
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    for i in range(3):
        seed_branch(db_session, tenant_id=tenant.id, name=f"B{i}", city="City")

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post("/branches", json=make_branch_payload(name="Branch 4", city="Pune"))

    assert response.status_code == 201


def test_post_branches_succeeds_when_tenant_has_no_plan(
    client, db_session, override_authenticated_user
):
    """A tenant with no plan assigned is not blocked by enforcement."""
    from tests.factories.users import make_authenticated_user

    tenant = _make_tenant(db_session, plan_id=None)
    seed_branch(db_session, tenant_id=tenant.id)

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post("/branches", json=make_branch_payload(name="Branch 2", city="Delhi"))

    assert response.status_code == 201


def test_post_staff_rejects_when_staff_cap_reached(
    client, db_session, override_authenticated_user
):
    """``POST /staff`` returns 422 when the tenant is at its staff cap."""
    from app.auth.password import hash_password
    from app.models.user import User
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=1,
        max_students=50,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    # Existing staff -- hits the cap.
    now = datetime.now(timezone.utc)
    db_session.add(
        User(
            email="existing.counselor@example.test",
            password_hash=hash_password("anything-strong-1"),
            role=Role.COUNSELOR,
            tenant_id=tenant.id,
            branch_id=branch.id,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(email="new.counselor@example.test", branch_id=branch.id),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "starter" in detail
    assert "staff" in detail
    assert "1" in detail


def test_post_staff_succeeds_when_plan_has_no_staff_cap(
    client, db_session, override_authenticated_user
):
    """Enterprise (NULL cap) never enforces the staff limit."""
    from app.auth.password import hash_password
    from app.models.user import User
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            User(
                email=f"existing{i}@example.test",
                password_hash=hash_password("anything-strong-1"),
                role=Role.COUNSELOR,
                tenant_id=tenant.id,
                branch_id=branch.id,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(email="new.counselor@example.test", branch_id=branch.id),
    )

    assert response.status_code == 201


def test_post_staff_succeeds_when_tenant_has_no_plan(
    client, db_session, override_authenticated_user
):
    """A tenant with no plan assigned is not blocked by staff enforcement."""
    from app.auth.password import hash_password
    from app.models.user import User
    from tests.factories.users import make_authenticated_user

    tenant = _make_tenant(db_session, plan_id=None)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            User(
                email=f"existing{i}@example.test",
                password_hash=hash_password("anything-strong-1"),
                role=Role.COUNSELOR,
                tenant_id=tenant.id,
                branch_id=branch.id,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()

    override_authenticated_user(
        make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=tenant.id)
    )

    response = client.post(
        "/staff",
        json=make_staff_payload(email="new.counselor@example.test", branch_id=branch.id),
    )

    assert response.status_code == 201


def test_post_students_rejects_when_student_cap_reached(
    client, db_session, override_authenticated_user
):
    """``POST /students`` (receptionist walk-in) returns 422 when at cap."""
    from app.auth.password import hash_password
    from app.models.user import User
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=1,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    db_session.add(
        User(
            email="existing.student@example.test",
            password_hash=hash_password("anything-strong-1"),
            role=Role.STUDENT,
            tenant_id=tenant.id,
            branch_id=branch.id,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    override_authenticated_user(
        make_authenticated_user(
            Role.RECEPTIONIST,
            user_id=42,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/students",
        json={
            "email": "new.student@example.test",
            "password": "Walkin-password-123",
            "name": "Walk In",
            "phone": "+91-9876543210",
            "date_of_birth": "2000-01-01",
            "branch_id": branch.id,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "starter" in detail
    assert "students" in detail
    assert "1" in detail


def test_post_students_succeeds_when_plan_has_no_student_cap(
    client, db_session, override_authenticated_user
):
    """Enterprise (NULL cap) never enforces the student limit."""
    from app.auth.password import hash_password
    from app.models.user import User
    from tests.factories.users import make_authenticated_user

    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            User(
                email=f"existing{i}@example.test",
                password_hash=hash_password("anything-strong-1"),
                role=Role.STUDENT,
                tenant_id=tenant.id,
                branch_id=branch.id,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()

    override_authenticated_user(
        make_authenticated_user(
            Role.RECEPTIONIST,
            user_id=99,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
    )

    response = client.post(
        "/students",
        json={
            "email": "new.student@example.test",
            "password": "Walkin-password-123",
            "name": "Walk In",
            "phone": "+91-9876543210",
            "date_of_birth": "2000-01-01",
            "branch_id": branch.id,
        },
    )

    assert response.status_code == 201


def test_post_register_student_rejects_when_student_cap_reached(
    client, db_session
):
    """``POST /auth/register-student`` returns 422 when the tenant is at cap."""
    from app.auth.password import hash_password
    from app.models.user import User

    plan = _make_plan(
        db_session,
        code=PlanTier.STARTER,
        name="Starter",
        max_branches=1,
        max_staff=5,
        max_students=1,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    db_session.add(
        User(
            email="existing.student@example.test",
            password_hash=hash_password("anything-strong-1"),
            role=Role.STUDENT,
            tenant_id=tenant.id,
            branch_id=branch.id,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant.slug,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "starter" in detail
    assert "students" in detail
    assert "1" in detail


def test_post_register_student_succeeds_when_plan_has_no_student_cap(
    client, db_session
):
    """Self-registration on Enterprise is never capped."""
    from app.auth.password import hash_password
    from app.models.user import User

    plan = _make_plan(
        db_session,
        code=PlanTier.ENTERPRISE,
        name="Enterprise",
        max_branches=None,
        max_staff=None,
        max_students=None,
    )
    tenant = _make_tenant(db_session, plan_id=plan.id)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            User(
                email=f"existing{i}@example.test",
                password_hash=hash_password("anything-strong-1"),
                role=Role.STUDENT,
                tenant_id=tenant.id,
                branch_id=branch.id,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(branch_id=branch.id),
    )

    assert response.status_code == 201


def test_post_register_student_succeeds_when_tenant_has_no_plan(client, db_session):
    """Self-registration on a tenant with no plan is never blocked."""
    tenant = _make_tenant(db_session, plan_id=None)
    branch = seed_branch(db_session, tenant_id=tenant.id)

    response = client.post(
        "/auth/register-student",
        json=make_register_student_payload(
            tenant_slug=tenant.slug,
            branch_id=branch.id,
        ),
    )

    assert response.status_code == 201