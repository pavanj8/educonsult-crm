"""End-date boundary for the analytics date filters (#517).

The dashboards send a date rather than a timestamp, so ``end_date`` arrives
parsed to midnight. Filtering ``created_at <= midnight`` dropped everything
created during that day, silently removing the most recent day from every
rolling window. Each test here fails against that comparison.
"""

from datetime import datetime, time, timedelta

from app.models.application import Application
from app.models.tenant import Tenant
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


def _seed_student(
    db_session, *, branch_id: int, email: str, created_at: datetime, tenant_id: int = 1
) -> User:
    student = User(
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=email,
        password_hash="hash",
        name="Boundary Student",
        role=Role.STUDENT,
        is_active=True,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(student)
    db_session.flush()
    return student


def _seed_application(
    db_session, *, branch_id: int, student_id: int, created_at: datetime, tenant_id: int = 1
) -> None:
    db_session.add(
        Application(
            tenant_id=tenant_id,
            branch_id=branch_id,
            student_id=student_id,
            university_id=1,
            program_id=1,
            stage=PipelineStage.REGISTERED,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.flush()


class TestEndDateIncludesTheWholeDay:
    def test_funnel_counts_an_application_created_later_on_the_end_date(
        self, client, db_session, override_authenticated_user
    ):
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        today = datetime.utcnow().date()
        # Mid-afternoon on the end date: before this fix, `<= midnight` excluded it.
        created_at = datetime.combine(today, time(14, 30))
        student = _seed_student(
            db_session, branch_id=branch.id, email="afternoon@example.com", created_at=created_at
        )
        _seed_application(
            db_session, branch_id=branch.id, student_id=student.id, created_at=created_at
        )
        db_session.commit()

        response = client.get(
            f"/analytics/funnel?start_date={today - timedelta(days=7)}&end_date={today}"
        )

        assert response.status_code == 200
        assert response.json()["total_applications"] == 1

    def test_registrations_counts_a_student_registered_later_on_the_end_date(
        self, client, db_session, override_authenticated_user
    ):
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

        today = datetime.utcnow().date()
        _seed_student(
            db_session,
            branch_id=branch.id,
            email="registered-today@example.com",
            created_at=datetime.combine(today, time(23, 59, 59)),
        )
        db_session.commit()

        response = client.get(
            f"/analytics/registrations-over-time?start_date={today - timedelta(days=7)}"
            f"&end_date={today}"
        )

        assert response.status_code == 200
        assert response.json()["total_registrations"] == 1

    def test_an_explicit_timestamp_is_still_an_exact_cutoff(
        self, client, db_session, override_authenticated_user
    ):
        # Only a bare date is widened. A caller who passes a real timestamp
        # means it, so a row created after it must stay excluded.
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=22, tenant_id=1, branch_id=branch.id
            )
        )

        today = datetime.utcnow().date()
        cutoff = datetime.combine(today, time(9, 0))
        student = _seed_student(
            db_session,
            branch_id=branch.id,
            email="after-cutoff@example.com",
            created_at=datetime.combine(today, time(11, 0)),
        )
        _seed_application(
            db_session,
            branch_id=branch.id,
            student_id=student.id,
            created_at=datetime.combine(today, time(11, 0)),
        )
        db_session.commit()

        response = client.get(
            f"/analytics/funnel?start_date={today - timedelta(days=7)}"
            f"&end_date={cutoff.isoformat()}"
        )

        assert response.status_code == 200
        assert response.json()["total_applications"] == 0

    def test_start_date_still_includes_the_whole_of_its_own_day(
        self, client, db_session, override_authenticated_user
    ):
        # start_date is compared with >= against midnight, which already covers
        # the whole day; widening the end must not have disturbed that.
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=23, tenant_id=1, branch_id=branch.id
            )
        )

        today = datetime.utcnow().date()
        start = today - timedelta(days=3)
        student = _seed_student(
            db_session,
            branch_id=branch.id,
            email="on-start-date@example.com",
            created_at=datetime.combine(start, time(0, 30)),
        )
        _seed_application(
            db_session,
            branch_id=branch.id,
            student_id=student.id,
            created_at=datetime.combine(start, time(0, 30)),
        )
        db_session.commit()

        response = client.get(f"/analytics/funnel?start_date={start}&end_date={today}")

        assert response.status_code == 200
        assert response.json()["total_applications"] == 1

    def test_platform_stats_counts_both_students_and_applications_from_the_end_date(
        self, client, db_session, override_authenticated_user
    ):
        # Platform-wide stats filters students and applications separately, so
        # it is the endpoint most likely to have one comparison fixed and the
        # other left behind.
        # This endpoint aggregates per tenant, so it needs a real Tenant row --
        # without one the tenant list is empty and every count is trivially 0.
        tenant = Tenant(name="Boundary Consultancy", slug="boundary", currency="INR")
        db_session.add(tenant)
        db_session.flush()
        branch = seed_branch(db_session, tenant_id=tenant.id)
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=24, tenant_id=None)
        )

        today = datetime.utcnow().date()
        created_at = datetime.combine(today, time(16, 45))
        student = _seed_student(
            db_session,
            branch_id=branch.id,
            email="platform@example.com",
            created_at=created_at,
            tenant_id=tenant.id,
        )
        _seed_application(
            db_session,
            branch_id=branch.id,
            student_id=student.id,
            created_at=created_at,
            tenant_id=tenant.id,
        )
        db_session.commit()

        response = client.get(
            f"/analytics/platform-wide-stats?start_date={today - timedelta(days=7)}"
            f"&end_date={today}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total_students"] == 1
        assert body["total_applications"] == 1

    def test_branch_comparison_counts_an_application_from_the_end_date(
        self, client, db_session, override_authenticated_user
    ):
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=25, tenant_id=1)
        )

        today = datetime.utcnow().date()
        created_at = datetime.combine(today, time(18, 15))
        student = _seed_student(
            db_session, branch_id=branch.id, email="comparison@example.com", created_at=created_at
        )
        _seed_application(
            db_session, branch_id=branch.id, student_id=student.id, created_at=created_at
        )
        db_session.commit()

        response = client.get(
            f"/analytics/branch-comparison?start_date={today - timedelta(days=7)}"
            f"&end_date={today}"
        )

        assert response.status_code == 200
        assert response.json()["total_applications"] == 1
