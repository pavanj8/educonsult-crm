"""Tests for conversion funnel analytics endpoint (E41; Journey J34)."""

from datetime import datetime, timedelta

from app.main import app
from app.models.application import Application
from app.models.user import User
from app.pipeline.stages import PipelineStage
from app.rbac.dependencies import get_current_user
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user


class TestConversionFunnel:
    """Black-box tests for GET /analytics/funnel (E41; Journey J34)."""

    def test_branch_manager_can_view_funnel_for_their_branch(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """A branch manager can view conversion funnel for their assigned branch."""
        # Create a branch and branch manager
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=20, tenant_id=1, branch_id=branch.id
            )
        )

        # Create a student for applications
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

        # Create applications at different stages
        stages_counts = {
            PipelineStage.REGISTERED: 10,
            PipelineStage.COUNSELING: 8,
            PipelineStage.UNIVERSITY_SHORTLISTING: 6,
            PipelineStage.APPLICATION_SUBMITTED: 5,
            PipelineStage.DOCUMENT_VERIFICATION: 4,
            PipelineStage.OFFER_LETTER: 3,
            PipelineStage.VISA_PROCESSING: 2,
            PipelineStage.ENROLLED: 5,
            PipelineStage.REJECTED: 2,
            PipelineStage.WITHDRAWN: 1,
        }

        for stage, count in stages_counts.items():
            for _ in range(count):
                app = Application(
                    tenant_id=1,
                    branch_id=branch.id,
                    student_id=student.id,
                    assigned_counselor_id=20,
                    university_id=1,
                    program_id=1,
                    stage=stage,
                )
                db_session.add(app)

        db_session.commit()

        # Call the funnel endpoint
        response = client.get("/analytics/funnel")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "funnel" in data
        assert "total_applications" in data
        assert isinstance(data["funnel"], list)

        # Verify total count
        assert data["total_applications"] == sum(stages_counts.values())

        # Verify stage counts match what we created
        funnel_by_stage = {bucket["stage"]: bucket["count"] for bucket in data["funnel"]}
        for stage, expected_count in stages_counts.items():
            assert funnel_by_stage.get(stage.value) == expected_count

    def test_funnel_filtered_by_date_range(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Date range filters correctly narrow the funnel to created_at window."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=21, tenant_id=1, branch_id=branch.id
            )
        )

        student = User(
            tenant_id=1,
            branch_id=branch.id,
            email="student2@example.com",
            password_hash="hash",
            name="Test Student 2",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Create old application (outside range)
        old_app = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=student.id,
            assigned_counselor_id=21,
            university_id=1,
            program_id=1,
            stage=PipelineStage.REGISTERED,
            created_at=ten_days_ago,
        )
        db_session.add(old_app)

        # Create new application (within range)
        new_app = Application(
            tenant_id=1,
            branch_id=branch.id,
            student_id=student.id,
            assigned_counselor_id=21,
            university_id=1,
            program_id=1,
            stage=PipelineStage.COUNSELING,
            created_at=three_days_ago,
        )
        db_session.add(new_app)

        db_session.commit()

        # Query with date range that includes only the new app
        start_date = (now - timedelta(days=5)).isoformat()
        end_date = now.isoformat()

        response = client.get(
            f"/analytics/funnel?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see the new app (counseling stage)
        assert data["total_applications"] == 1
        funnel_by_stage = {bucket["stage"]: bucket["count"] for bucket in data["funnel"]}
        assert funnel_by_stage.get("counseling") == 1
        assert funnel_by_stage.get("registered") == 0

    def test_owner_views_funnel_across_all_branches(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Consultancy owner sees funnel aggregated across all branches."""
        # Create two branches
        branch1 = seed_branch(db_session, tenant_id=1, name="Branch 1", city="City 1")
        branch2 = seed_branch(db_session, tenant_id=1, name="Branch 2", city="City 2")

        override_authenticated_user(
            make_authenticated_user(Role.CONSULTANCY_OWNER, user_id=30, tenant_id=1)
        )

        # Create a student
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

        # Create apps in both branches
        for branch in [branch1, branch2]:
            app = Application(
                tenant_id=1,
                branch_id=branch.id,
                student_id=student.id,
                assigned_counselor_id=30,
                university_id=1,
                program_id=1,
                stage=PipelineStage.REGISTERED,
            )
            db_session.add(app)

        db_session.commit()

        response = client.get("/analytics/funnel")

        assert response.status_code == 200
        data = response.json()

        # Owner should see both branches' applications
        assert data["total_applications"] == 2
        funnel_by_stage = {bucket["stage"]: bucket["count"] for bucket in data["funnel"]}
        assert funnel_by_stage.get("registered") == 2

    def test_counselor_denied_access_to_funnel(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Counselor without analytics permission cannot access funnel endpoint."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(Role.COUNSELOR, user_id=40, tenant_id=1, branch_id=branch.id)
        )

        response = client.get("/analytics/funnel")

        assert response.status_code == 403

    def test_unauthenticated_request_denied(
        self,
        client,
        override_authenticated_user,
    ):
        """Unauthenticated requests are rejected."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/analytics/funnel")

        assert response.status_code == 401

    def test_empty_funnel_returns_zeroes(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """When no applications exist, funnel returns all stages with count 0."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=50, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/funnel")

        assert response.status_code == 200
        data = response.json()

        # Should have all stages with zero count
        assert data["total_applications"] == 0
        assert len(data["funnel"]) == len(PipelineStage)
        for bucket in data["funnel"]:
            assert bucket["count"] == 0

    def test_funnel_includes_all_pipeline_stages(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Response includes every stage defined in PipelineStage enum."""
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=60, tenant_id=1, branch_id=branch.id
            )
        )

        response = client.get("/analytics/funnel")

        assert response.status_code == 200
        data = response.json()

        funnel_stages = {bucket["stage"] for bucket in data["funnel"]}
        expected_stages = {stage.value for stage in PipelineStage}

        assert funnel_stages == expected_stages

    def test_funnel_excludes_other_tenants_applications(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Branch manager cannot see applications from other tenants."""
        # Create a branch and branch manager in tenant 1
        branch = seed_branch(db_session, tenant_id=1)
        override_authenticated_user(
            make_authenticated_user(
                Role.BRANCH_MANAGER, user_id=70, tenant_id=1, branch_id=branch.id
            )
        )

        # Create application in another tenant (tenant 2)
        student = User(
            tenant_id=2,
            branch_id=1,
            email="other@example.com",
            password_hash="hash",
            name="Other Student",
            role=Role.STUDENT,
            is_active=True,
        )
        db_session.add(student)
        db_session.flush()

        app = Application(
            tenant_id=2,
            branch_id=1,
            student_id=student.id,
            assigned_counselor_id=1,
            university_id=1,
            program_id=1,
            stage=PipelineStage.REGISTERED,
        )
        db_session.add(app)
        db_session.commit()

        response = client.get("/analytics/funnel")

        assert response.status_code == 200
        data = response.json()

        # Should not see the other tenant's application
        assert data["total_applications"] == 0

