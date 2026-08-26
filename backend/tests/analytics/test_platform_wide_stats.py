"""Tests for platform-wide tenant stats analytics endpoint (E43; Journey J36).

This test suite validates the GET /analytics/platform-wide-stats endpoint
which provides Super Admins with aggregated metrics across all tenants
on the platform.

Traceability:
- Requirement: Requirements §7 Analytics & Reporting
- Journey: J36 - Super Admin views platform-wide tenant stats
- Epic: E43 - Super Admin Platform-Wide Stats
- Issue: #215
"""

from datetime import datetime, timedelta

from app.main import app
from app.models.application import Application
from app.models.branch import Branch
from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestPlatformWideStats:
    """Black-box tests for GET /analytics/platform-wide-stats (E43; Journey J36)."""

    def test_super_admin_can_view_platform_wide_stats(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Super admin can view aggregated stats across all tenants."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        # Create two tenants
        tenant1 = Tenant(
            name="ABC Consultancy",
            slug="abc-consultancy",
            currency="INR",
        )
        tenant2 = Tenant(
            name="XYZ Education",
            slug="xyz-education",
            currency="INR",
        )
        db_session.add_all([tenant1, tenant2])
        db_session.flush()

        # Create plans
        plan1 = Plan(code=PlanTier.STARTER, name="Starter", max_branches=1, max_staff=5)
        plan2 = Plan(code=PlanTier.GROWTH, name="Growth", max_branches=5, max_staff=20)
        db_session.add_all([plan1, plan2])
        db_session.flush()

        # Assign plans to tenants
        tenant1.plan_id = plan1.id
        tenant2.plan_id = plan2.id
        db_session.flush()

        # Create branches in both tenants
        branch1 = Branch(tenant_id=tenant1.id, name="Downtown", city="New York")
        branch2 = Branch(tenant_id=tenant2.id, name="Uptown", city="Los Angeles")
        db_session.add_all([branch1, branch2])
        db_session.flush()

        # Create staff in both tenants
        staff1 = User(
            tenant_id=tenant1.id,
            branch_id=branch1.id,
            email="staff1@example.com",
            password_hash="hash",
            name="Staff 1",
            role=Role.COUNSELOR,
            is_active=True,
        )
        staff2 = User(
            tenant_id=tenant2.id,
            branch_id=branch2.id,
            email="staff2@example.com",
            password_hash="hash",
            name="Staff 2",
            role=Role.BRANCH_MANAGER,
            is_active=True,
        )
        db_session.add_all([staff1, staff2])
        db_session.flush()

        # Create students in both tenants
        student1 = User(
            tenant_id=tenant1.id,
            branch_id=branch1.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        student2 = User(
            tenant_id=tenant2.id,
            branch_id=branch2.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add_all([student1, student2])
        db_session.flush()

        # Create applications in both tenants
        for _ in range(10):
            app1 = Application(
                tenant_id=tenant1.id,
                branch_id=branch1.id,
                student_id=student1.id,
                assigned_counselor_id=staff1.id,
                university_id=1,
                program_id=1,
                stage=PipelineStage.COUNSELING,
            )
            db_session.add(app1)

        for _ in range(5):
            app2 = Application(
                tenant_id=tenant2.id,
                branch_id=branch2.id,
                student_id=student2.id,
                assigned_counselor_id=staff2.id,
                university_id=1,
                program_id=1,
                stage=PipelineStage.APPLICATION_SUBMITTED,
            )
            db_session.add(app2)

        db_session.commit()

        # Call the platform-wide stats endpoint
        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "tenants" in data
        assert "total_tenants" in data
        assert "total_branches" in data
        assert "total_staff" in data
        assert "total_students" in data
        assert "total_applications" in data
        assert isinstance(data["tenants"], list)

        # Verify totals
        assert data["total_tenants"] == 2
        assert data["total_branches"] == 2
        assert data["total_staff"] == 2
        assert data["total_students"] == 2
        assert data["total_applications"] == 15

        # Verify tenant metrics
        tenants_by_id = {t["tenant_id"]: t for t in data["tenants"]}

        # Tenant1
        tenant1_data = tenants_by_id[tenant1.id]
        assert tenant1_data["tenant_name"] == "ABC Consultancy"
        assert tenant1_data["tenant_slug"] == "abc-consultancy"
        assert tenant1_data["plan_code"] == "starter"
        assert tenant1_data["branches_count"] == 1
        assert tenant1_data["staff_count"] == 1
        assert tenant1_data["students_count"] == 1
        assert tenant1_data["applications_count"] == 10
        assert tenant1_data["active_count"] == 10

        # Tenant2
        tenant2_data = tenants_by_id[tenant2.id]
        assert tenant2_data["tenant_name"] == "XYZ Education"
        assert tenant2_data["tenant_slug"] == "xyz-education"
        assert tenant2_data["plan_code"] == "growth"
        assert tenant2_data["branches_count"] == 1
        assert tenant2_data["staff_count"] == 1
        assert tenant2_data["students_count"] == 1
        assert tenant2_data["applications_count"] == 5
        assert tenant2_data["active_count"] == 5

        # Verify ordering: should be descending by applications_count
        assert data["tenants"][0]["tenant_id"] == tenant1.id  # 10 apps
        assert data["tenants"][1]["tenant_id"] == tenant2.id  # 5 apps

    def test_platform_wide_stats_includes_terminal_stage_breakdown(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Terminal stage counts (enrolled, rejected, withdrawn) are included."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Test Consultancy", slug="test-consultancy", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        branch = Branch(tenant_id=tenant.id, name="Main Branch", city="City")
        db_session.add(branch)
        db_session.flush()

        student = User(
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        # Create apps at various stages
        stages = (
            [PipelineStage.ENROLLED] * 5
            + [PipelineStage.REJECTED] * 3
            + [PipelineStage.WITHDRAWN] * 2
            + [PipelineStage.COUNSELING] * 4
            + [PipelineStage.DOCUMENT_VERIFICATION] * 3
        )
        for stage in stages:
            app = Application(
                tenant_id=tenant.id,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=1,
                university_id=1,
                program_id=1,
                stage=stage,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["applications_count"] == 17
        assert tenant_data["enrolled_count"] == 5
        assert tenant_data["rejected_count"] == 3
        assert tenant_data["withdrawn_count"] == 2
        assert tenant_data["active_count"] == 7  # 4 + 3 = 7

    def test_platform_wide_stats_filtered_by_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Date range filters correctly narrow stats to created_at window for students/apps."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Test Consultancy", slug="test-consultancy", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        branch = Branch(tenant_id=tenant.id, name="Main Branch", city="City")
        db_session.add(branch)
        db_session.flush()

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Create old student and applications (outside range)
        old_student = User(
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="old@student.com",
            password_hash="hash",
            name="Old Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=ten_days_ago,
        )
        db_session.add(old_student)
        db_session.flush()

        for _ in range(5):
            old_app = Application(
                tenant_id=tenant.id,
                branch_id=branch.id,
                student_id=old_student.id,
                assigned_counselor_id=1,
                university_id=1,
                program_id=1,
                stage=PipelineStage.REGISTERED,
                created_at=ten_days_ago,
            )
            db_session.add(old_app)

        # Create new student and applications (within range)
        new_student = User(
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="new@student.com",
            password_hash="hash",
            name="New Student",
            role=Role.STUDENT,
            is_active=True,
            created_at=three_days_ago,
        )
        db_session.add(new_student)
        db_session.flush()

        for _ in range(3):
            new_app = Application(
                tenant_id=tenant.id,
                branch_id=branch.id,
                student_id=new_student.id,
                assigned_counselor_id=1,
                university_id=1,
                program_id=1,
                stage=PipelineStage.COUNSELING,
                created_at=three_days_ago,
            )
            db_session.add(new_app)

        db_session.commit()

        # Query with date range that includes only the new apps/students
        start_date = (now - timedelta(days=5)).isoformat()
        end_date = now.isoformat()

        response = client.get(
            f"/analytics/platform-wide-stats?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see the new student and apps (not old ones)
        tenant_data = data["tenants"][0]
        assert tenant_data["students_count"] == 1  # Only new student
        assert tenant_data["applications_count"] == 3  # Only new apps

        # Branch and staff counts should NOT be filtered
        assert tenant_data["branches_count"] == 1

    def test_platform_wide_stats_includes_tenant_without_plan(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Tenants without assigned plans show plan_code as null."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        # Create tenant without plan
        tenant = Tenant(
            name="No Plan Consultancy",
            slug="no-plan-consultancy",
            currency="INR",
            plan_id=None,
        )
        db_session.add(tenant)
        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["tenant_name"] == "No Plan Consultancy"
        assert tenant_data["plan_code"] is None

    def test_platform_wide_stats_correctly_counts_staff_excludes_students(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Staff count excludes students; counts all other roles."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Test Consultancy", slug="test-consultancy", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        branch = Branch(tenant_id=tenant.id, name="Main Branch", city="City")
        db_session.add(branch)
        db_session.flush()

        # Create various staff roles
        staff_roles = [
            Role.CONSULTANCY_OWNER,
            Role.BRANCH_MANAGER,
            Role.COUNSELOR,
            Role.DOCUMENT_VERIFIER,
            Role.VISA_PROCESSOR,
            Role.RECEPTIONIST,
        ]

        for role in staff_roles:
            staff = User(
                tenant_id=tenant.id,
                branch_id=branch.id,
                email=f"{role.value}@example.com",
                password_hash="hash",
                name=role.value,
                role=role,
                is_active=True,
            )
            db_session.add(staff)

        # Create students
        for i in range(5):
            student = User(
                tenant_id=tenant.id,
                branch_id=branch.id,
                email=f"student{i}@example.com",
                password_hash="hash",
                name=f"Student {i}",
                role=Role.STUDENT,
                is_active=True,
            )
            db_session.add(student)

        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["staff_count"] == 6  # All staff roles
        assert tenant_data["students_count"] == 5  # Only students

    def test_platform_wide_stats_handles_tenant_with_no_applications(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Tenants with no applications appear with zero counts."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Empty Consultancy", slug="empty-consultancy", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        branch = Branch(tenant_id=tenant.id, name="Main Branch", city="City")
        db_session.add(branch)
        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["tenant_name"] == "Empty Consultancy"
        assert tenant_data["branches_count"] == 1
        assert tenant_data["staff_count"] == 0
        assert tenant_data["students_count"] == 0
        assert tenant_data["applications_count"] == 0
        assert tenant_data["enrolled_count"] == 0
        assert tenant_data["rejected_count"] == 0
        assert tenant_data["withdrawn_count"] == 0
        assert tenant_data["active_count"] == 0

    def test_platform_wide_stats_returns_empty_when_no_tenants(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Returns empty stats when platform has no tenants."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        # Ensure no tenants exist
        db_session.query(Tenant).delete()
        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_tenants"] == 0
        assert data["total_branches"] == 0
        assert data["total_staff"] == 0
        assert data["total_students"] == 0
        assert data["total_applications"] == 0
        assert data["tenants"] == []

    def test_platform_wide_stats_aggregates_multiple_branches_per_tenant(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branches count correctly aggregates all branches in a tenant."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Multi-Branch Consultancy", slug="multi-branch", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        # Create multiple branches
        for i in range(3):
            branch = Branch(
                tenant_id=tenant.id, name=f"Branch {i}", city=f"City {i}"
            )
            db_session.add(branch)

        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["branches_count"] == 3
        assert data["total_branches"] == 3

    def test_consultancy_owner_denied_access_to_platform_wide_stats(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owner cannot access platform-wide stats endpoint."""
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=30, tenant_id=1)
        )

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 403

    def test_branch_manager_denied_access_to_platform_wide_stats(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot access platform-wide stats endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=40, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 403

    def test_counselor_denied_access_to_platform_wide_stats(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselor cannot access platform-wide stats endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=41, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 403

    def test_student_denied_access_to_platform_wide_stats(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Student cannot access platform-wide stats endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.STUDENT, user_id=50, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 401

    def test_platform_wide_stats_ordering_by_applications_descending(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Tenants are ordered by applications_count descending."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        # Create three tenants
        tenants = []
        for i, (name, app_count) in enumerate(
            [
                ("Low Apps", 5),
                ("High Apps", 20),
                ("Medium Apps", 10),
            ]
        ):
            tenant = Tenant(name=name, slug=f"tenant-{i}", currency="INR")
            db_session.add(tenant)
            db_session.flush()
            tenants.append((tenant, app_count))

            branch = Branch(tenant_id=tenant.id, name=f"Branch {i}", city="City")
            db_session.add(branch)
            db_session.flush()

            student = User(
                tenant_id=tenant.id,
                branch_id=branch.id,
                email=f"student{i}@example.com",
                password_hash="hash",
                name="Student",
                role=Role.STUDENT,
                is_active=True,
            )
            db_session.add(student)
            db_session.flush()

            for _ in range(app_count):
                app = Application(
                    tenant_id=tenant.id,
                    branch_id=branch.id,
                    student_id=student.id,
                    assigned_counselor_id=1,
                    university_id=1,
                    program_id=1,
                    stage=PipelineStage.REGISTERED,
                )
                db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        # Verify ordering: High Apps (20) > Medium Apps (10) > Low Apps (5)
        assert data["tenants"][0]["tenant_name"] == "High Apps"
        assert data["tenants"][0]["applications_count"] == 20
        assert data["tenants"][1]["tenant_name"] == "Medium Apps"
        assert data["tenants"][1]["applications_count"] == 10
        assert data["tenants"][2]["tenant_name"] == "Low Apps"
        assert data["tenants"][2]["applications_count"] == 5

    def test_platform_wide_stats_correctly_calculates_active_count(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Active count excludes terminal stages (enrolled, rejected, withdrawn)."""
        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        tenant = Tenant(name="Test Consultancy", slug="test-consultancy", currency="INR")
        db_session.add(tenant)
        db_session.flush()

        branch = Branch(tenant_id=tenant.id, name="Main Branch", city="City")
        db_session.add(branch)
        db_session.flush()

        student = User(
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        # Create apps at various stages
        # Terminal: 5 enrolled, 3 rejected, 2 withdrawn = 10 terminal
        # Active: 2 registered, 3 counseling, 4 document_verification = 9 active
        stages = (
            [PipelineStage.ENROLLED] * 5
            + [PipelineStage.REJECTED] * 3
            + [PipelineStage.WITHDRAWN] * 2
            + [PipelineStage.REGISTERED] * 2
            + [PipelineStage.COUNSELING] * 3
            + [PipelineStage.DOCUMENT_VERIFICATION] * 4
        )

        for stage in stages:
            app = Application(
                tenant_id=tenant.id,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=1,
                university_id=1,
                program_id=1,
                stage=stage,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/platform-wide-stats")

        assert response.status_code == 200
        data = response.json()

        tenant_data = data["tenants"][0]
        assert tenant_data["applications_count"] == 19
        assert tenant_data["enrolled_count"] == 5
        assert tenant_data["rejected_count"] == 3
        assert tenant_data["withdrawn_count"] == 2
        assert tenant_data["active_count"] == 9  # Sum of non-terminal stages
