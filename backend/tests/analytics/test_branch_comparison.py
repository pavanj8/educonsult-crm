"""Tests for branch comparison analytics endpoint (E42; Journey J35)."""

from datetime import datetime, timedelta

from app.main import app
from app.models.application import Application
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestBranchComparison:
    """Black-box tests for GET /analytics/branch-comparison (E42; Journey J35)."""

    def test_owner_can_view_branch_comparison_for_all_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """A consultancy owner can view branch comparison across all branches."""
        # Create two branches
        branch1 = seed_branch(db_session, tenant_id=1, name="Downtown", city="New York")
        branch2 = seed_branch(db_session, tenant_id=1, name="Uptown", city="New York")

        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=30, tenant_id=1)
        )

        # Create students
        student1 = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        student2 = User(
            tenant_id=1,
            branch_id=branch2.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add_all([student1, student2])
        db_session.flush()

        # Create applications in branch1: 5 enrolled, 3 rejected, 2 withdrawn, 10 active
        stages_branch1 = (
            [PipelineStage.ENROLLED] * 5
            + [PipelineStage.REJECTED] * 3
            + [PipelineStage.WITHDRAWN] * 2
            + [PipelineStage.COUNSELING] * 6
            + [PipelineStage.APPLICATION_SUBMITTED] * 4
        )
        for stage in stages_branch1:
            app = Application(
                tenant_id=1,
                branch_id=branch1.id,
                student_id=student1.id,
                assigned_counselor_id=30,
                university_id=1,
                program_id=1,
                stage=stage,
            )
            db_session.add(app)

        # Create applications in branch2: 2 enrolled, 1 rejected, 1 withdrawn, 5 active
        stages_branch2 = (
            [PipelineStage.ENROLLED] * 2
            + [PipelineStage.REJECTED] * 1
            + [PipelineStage.WITHDRAWN] * 1
            + [PipelineStage.DOCUMENT_VERIFICATION] * 3
            + [PipelineStage.OFFER_LETTER] * 2
        )
        for stage in stages_branch2:
            app = Application(
                tenant_id=1,
                branch_id=branch2.id,
                student_id=student2.id,
                assigned_counselor_id=30,
                university_id=1,
                program_id=1,
                stage=stage,
            )
            db_session.add(app)

        db_session.commit()

        # Call the branch comparison endpoint
        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "branches" in data
        assert "total_branches" in data
        assert "total_applications" in data
        assert isinstance(data["branches"], list)

        # Verify totals
        assert data["total_branches"] == 2
        assert data["total_applications"] == 29  # 20 + 9 = 29 total

        # Verify branch metrics
        branches_by_id = {b["branch_id"]: b for b in data["branches"]}

        # Branch1 should have 20 apps
        branch1_data = branches_by_id[branch1.id]
        assert branch1_data["branch_name"] == "Downtown"
        assert branch1_data["branch_city"] == "New York"
        assert branch1_data["total_applications"] == 20
        assert branch1_data["enrolled_count"] == 5
        assert branch1_data["rejected_count"] == 3
        assert branch1_data["withdrawn_count"] == 2
        assert branch1_data["active_count"] == 10

        # Branch2 should have 9 apps
        branch2_data = branches_by_id[branch2.id]
        assert branch2_data["branch_name"] == "Uptown"
        assert branch2_data["branch_city"] == "New York"
        assert branch2_data["total_applications"] == 9
        assert branch2_data["enrolled_count"] == 2
        assert branch2_data["rejected_count"] == 1
        assert branch2_data["withdrawn_count"] == 1
        assert branch2_data["active_count"] == 5

        # Verify ordering: should be descending by total_applications
        assert data["branches"][0]["branch_id"] == branch1.id  # 20 apps
        assert data["branches"][1]["branch_id"] == branch2.id  # 9 apps

    def test_branch_comparison_filtered_by_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Date range filters correctly narrow branch comparison to created_at window."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=31, tenant_id=1)
        )

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Test Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Create old applications (outside range)
        for _ in range(5):
            old_app = Application(
                tenant_id=1,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=31,
                university_id=1,
                program_id=1,
                stage=PipelineStage.REGISTERED,
                created_at=ten_days_ago,
            )
            db_session.add(old_app)

        # Create new applications (within range)
        for _ in range(3):
            new_app = Application(
                tenant_id=1,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=31,
                university_id=1,
                program_id=1,
                stage=PipelineStage.COUNSELING,
                created_at=three_days_ago,
            )
            db_session.add(new_app)

        db_session.commit()

        # Query with date range that includes only the new apps
        start_date = (now - timedelta(days=5)).isoformat()
        end_date = now.isoformat()

        response = client.get(
            f"/analytics/branch-comparison?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see the 3 new apps
        assert data["total_applications"] == 3
        assert data["branches"][0]["total_applications"] == 3

    def test_super_admin_can_view_branch_comparison_across_tenants(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Super admin sees branch comparison across all tenants."""
        # Create branches in different tenants
        branch1 = seed_branch(db_session, tenant_id=1, name="Tenant1 Branch", city="City1")
        branch2 = seed_branch(db_session, tenant_id=2, name="Tenant2 Branch", city="City2")

        override_authenticated_user(
            make_authenticated_user(Role.SUPER_ADMIN, user_id=1, tenant_id=None)
        )

        # Create students for each tenant
        student1 = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student1@example.com",
            password_hash="hash",
            name="Student 1",
            role=Role.STUDENT,
            is_active=True,
        )
        student2 = User(
            tenant_id=2,
            branch_id=branch2.id,
            email="student2@example.com",
            password_hash="hash",
            name="Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add_all([student1, student2])
        db_session.flush()

        # Create apps in both branches
        for branch, student in [(branch1, student1), (branch2, student2)]:
            for _ in range(5):
                app = Application(
                    tenant_id=branch.tenant_id,
                    branch_id=branch.id,
                    student_id=student.id,
                    assigned_counselor_id=1,
                    university_id=1,
                    program_id=1,
                    stage=PipelineStage.REGISTERED,
                )
                db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        # Super admin should see both tenants' branches
        assert data["total_branches"] == 2
        assert data["total_applications"] == 10

    def test_branch_manager_denied_access_to_branch_comparison(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot access cross-branch comparison endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=40, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 403

    def test_counselor_denied_access_to_branch_comparison(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselor cannot access cross-branch comparison endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=41, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 401

    def test_branch_comparison_with_branch_having_no_applications(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branches with no applications appear in comparison with zero counts."""
        branch1 = seed_branch(db_session, tenant_id=1, name="Active Branch", city="City1")
        seed_branch(db_session, tenant_id=1, name="Empty Branch", city="City2")

        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=32, tenant_id=1)
        )

        student = User(
            tenant_id=1,
            branch_id=branch1.id,
            email="student@example.com",
            password_hash="hash",
            name="Test Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        # Create applications only in branch1
        for _ in range(5):
            app = Application(
                tenant_id=1,
                branch_id=branch1.id,
                student_id=student.id,
                assigned_counselor_id=32,
                university_id=1,
                program_id=1,
                stage=PipelineStage.REGISTERED,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        # Both branches should be present
        assert data["total_branches"] == 2
        assert len(data["branches"]) == 2

        branches_by_name = {b["branch_name"]: b for b in data["branches"]}

        # Branch1 with apps
        assert branches_by_name["Active Branch"]["total_applications"] == 5

        # Branch2 with no apps should still appear with zeros
        assert branches_by_name["Empty Branch"]["total_applications"] == 0
        assert branches_by_name["Empty Branch"]["enrolled_count"] == 0
        assert branches_by_name["Empty Branch"]["rejected_count"] == 0
        assert branches_by_name["Empty Branch"]["withdrawn_count"] == 0
        assert branches_by_name["Empty Branch"]["active_count"] == 0

    def test_branch_comparison_excludes_other_tenants_for_owner(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Owner cannot see branches from other tenants."""
        # Create branches in different tenants
        branch1 = seed_branch(db_session, tenant_id=1, name="My Branch", city="City1")
        branch2 = seed_branch(db_session, tenant_id=2, name="Other Branch", city="City2")

        # Owner of tenant 1
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=33, tenant_id=1)
        )

        student = User(
            tenant_id=2,
            branch_id=branch2.id,
            email="student@example.com",
            password_hash="hash",
            name="Other Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        # Create applications in tenant 2
        for _ in range(5):
            app = Application(
                tenant_id=2,
                branch_id=branch2.id,
                student_id=student.id,
                assigned_counselor_id=1,
                university_id=1,
                program_id=1,
                stage=PipelineStage.REGISTERED,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        # Should only see tenant 1's branch (with no apps)
        assert data["total_branches"] == 1
        assert len(data["branches"]) == 1
        assert data["branches"][0]["branch_id"] == branch1.id
        assert data["total_applications"] == 0

    def test_branch_comparison_correctly_calculates_active_count(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Active count excludes terminal stages (enrolled, rejected, withdrawn)."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=34, tenant_id=1)
        )

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student@example.com",
            password_hash="hash",
            name="Test Student",
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
                tenant_id=1,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=34,
                university_id=1,
                program_id=1,
                stage=stage,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        branch_data = data["branches"][0]
        assert branch_data["total_applications"] == 19
        assert branch_data["enrolled_count"] == 5
        assert branch_data["rejected_count"] == 3
        assert branch_data["withdrawn_count"] == 2
        assert branch_data["active_count"] == 9  # Sum of non-terminal stages

    def test_branch_comparison_returns_empty_list_for_tenant_with_no_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Returns empty branches list for tenant with no branches."""
        # Owner with no branches in tenant
        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=35, tenant_id=99)
        )

        response = client.get("/analytics/branch-comparison")

        assert response.status_code == 200
        data = response.json()

        assert data["total_branches"] == 0
        assert data["total_applications"] == 0
        assert data["branches"] == []
