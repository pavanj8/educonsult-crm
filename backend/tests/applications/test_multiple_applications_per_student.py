"""Tests for the E18 student application feature, focused on issue #149.

Acceptance criterion (issue #149, E18, "Tests: multiple applications per
student, independent stage tracking"):

  A single student can have multiple (university, program) applications
  running in parallel.  Each application carries its own independent
  pipeline stage and the stages do not bleed across applications.

These tests are black-box against the public API surface (POST /applications
and GET /applications) and the persistence layer (Application rows), with
direct DB seeding used to stage applications at non-initial stages because
the API does not yet expose a stage-mutation endpoint (E25 will provide it).
"""

from datetime import datetime, timezone

from app.models.application import Application
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user
from tests.master_data.helpers import seed_master_data_chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_tenant(
    db_session,
    *,
    name: str = "Apex EduConsult",
    slug: str = "apex",
) -> Tenant:
    """Create a Tenant row directly -- the only tenant-creation surface is
    the super-admin POST /tenants endpoint, but for the E18 student-application
    tests we only care about the tenant_id FK; seeding it inline is simpler
    than rewiring every test through that endpoint.
    """
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_student(db_session, *, tenant_id: int, branch_id: int, email: str = "student@example.test"):
    return make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=email,
    )


def _authenticate_student(override_authenticated_user, *, student, tenant_id, branch_id):
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=student.id,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
    )


def _seed_application_at_stage(
    db_session,
    *,
    tenant_id: int,
    student_id: int,
    university_id: int,
    program_id: int,
    stage: PipelineStage,
) -> Application:
    """Persist an Application row at a specified stage, bypassing the
    stage-mutation API (E25 will provide that -- tests for E18 #149 only
    need to demonstrate that the schema and list endpoint treat stages as
    per-row state, not as student-wide state).
    """
    now = datetime.now(timezone.utc)
    application = Application(
        tenant_id=tenant_id,
        student_id=student_id,
        university_id=university_id,
        program_id=program_id,
        stage=stage,
        created_at=now,
        updated_at=now,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


# ---------------------------------------------------------------------------
# Multiple applications per student
# ---------------------------------------------------------------------------

class TestStudentCanHaveMultipleApplications:
    """The core acceptance criterion: a student can have multiple applications."""

    def test_student_can_create_two_applications_via_api(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """POST /applications twice in a row for the same student -- both 201."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chain_one = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_two = seed_master_data_chain(db_session, tenant_id=tenant.id)
        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        first = client.post(
            "/applications",
            json={"university_id": chain_one[1].id, "program_id": chain_one[2].id},
        )
        second = client.post(
            "/applications",
            json={"university_id": chain_two[1].id, "program_id": chain_two[2].id},
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]
        assert first.json()["student_id"] == student.id
        assert second.json()["student_id"] == student.id
        # Both start at REGISTERED, the initial pipeline stage.
        assert first.json()["stage"] == PipelineStage.REGISTERED.value
        assert second.json()["stage"] == PipelineStage.REGISTERED.value

    def test_student_can_create_three_or_more_applications(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Three POSTs all succeed; GET returns them all."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chains = [
            seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(3)
        ]
        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        created_ids = []
        for _, university, program in chains:
            response = client.post(
                "/applications",
                json={"university_id": university.id, "program_id": program.id},
            )
            assert response.status_code == 201
            created_ids.append(response.json()["id"])
        assert len(set(created_ids)) == 3  # all distinct row IDs

        list_response = client.get("/applications")
        assert list_response.status_code == 200
        body = list_response.json()
        assert len(body) == 3
        assert {row["id"] for row in body} == set(created_ids)
        # All point back at the same student.
        assert {row["student_id"] for row in body} == {student.id}

    def test_student_can_have_two_applications_to_same_university_and_program(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """The data model allows parallel applications with identical
        (university, program) on the same student -- the requirement is
        "multiple applications ... in parallel", with no uniqueness
        constraint at the (student, university, program) level."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        _, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        payload = {"university_id": university.id, "program_id": program.id}
        first = client.post("/applications", json=payload)
        second = client.post("/applications", json=payload)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]
        assert (
            first.json()["university_id"]
            == second.json()["university_id"]
            == university.id
        )
        assert (
            first.json()["program_id"]
            == second.json()["program_id"]
            == program.id
        )


# ---------------------------------------------------------------------------
# Independent stage tracking
# ---------------------------------------------------------------------------

class TestIndependentStageTracking:
    """Each application tracks its own stage; stages do not bleed across
    applications belonging to the same student (Requirements §5:
    "multiple applications ... each with its own independent pipeline stage").
    """

    def test_list_returns_each_application_with_its_own_stage(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Two applications on the same student, seeded at different stages,
        both come back from GET /applications with their stages intact."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chain_one = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_two = seed_master_data_chain(db_session, tenant_id=tenant.id)

        first = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_one[1].id,
            program_id=chain_one[2].id,
            stage=PipelineStage.COUNSELING,
        )
        second = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_two[1].id,
            program_id=chain_two[2].id,
            stage=PipelineStage.APPLICATION_SUBMITTED,
        )

        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2

        by_id = {row["id"]: row for row in body}
        assert by_id[first.id]["stage"] == PipelineStage.COUNSELING.value
        assert by_id[second.id]["stage"] == PipelineStage.APPLICATION_SUBMITTED.value
        # Stages are NOT shared: changing one's stage column does not propagate.
        assert by_id[first.id]["stage"] != by_id[second.id]["stage"]

    def test_updating_one_applications_stage_leaves_others_unchanged(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Writing a new stage to one application row does not affect the
        stage column of a sibling application on the same student -- proves
        stage is per-row state, not student-wide state."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chain_one = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_two = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_three = seed_master_data_chain(db_session, tenant_id=tenant.id)
        first = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_one[1].id,
            program_id=chain_one[2].id,
            stage=PipelineStage.REGISTERED,
        )
        second = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_two[1].id,
            program_id=chain_two[2].id,
            stage=PipelineStage.REGISTERED,
        )
        third = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_three[1].id,
            program_id=chain_three[2].id,
            stage=PipelineStage.REGISTERED,
        )

        # Mutate the stage column directly.  This is the same write the E25
        # stage-mutation endpoint will perform -- verifying that the column
        # is independent per row is independent of how the write arrives.
        first.stage = PipelineStage.VISA_PROCESSING
        db_session.commit()
        db_session.refresh(first)

        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        by_id = {row["id"]: row for row in body}

        assert by_id[first.id]["stage"] == PipelineStage.VISA_PROCESSING.value
        # siblings untouched
        assert by_id[second.id]["stage"] == PipelineStage.REGISTERED.value
        assert by_id[third.id]["stage"] == PipelineStage.REGISTERED.value
        # sanity: the three IDs are all distinct
        assert {first.id, second.id, third.id} == {
            by_id[row["id"]]["id"] for row in body
        }

    def test_three_applications_hold_three_different_stages(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Three applications, three stages -- a stronger variant that
        confirms no implicit 'all share one stage' assumption lurks in the
        serializer or query path."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chain_one = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_two = seed_master_data_chain(db_session, tenant_id=tenant.id)
        chain_three = seed_master_data_chain(db_session, tenant_id=tenant.id)

        at_registered = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_one[1].id,
            program_id=chain_one[2].id,
            stage=PipelineStage.REGISTERED,
        )
        at_offer_letter = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_two[1].id,
            program_id=chain_two[2].id,
            stage=PipelineStage.OFFER_LETTER,
        )
        at_withdrawn = _seed_application_at_stage(
            db_session,
            tenant_id=tenant.id,
            student_id=student.id,
            university_id=chain_three[1].id,
            program_id=chain_three[2].id,
            stage=PipelineStage.WITHDRAWN,
        )

        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        by_id = {row["id"]: row for row in body}
        assert (
            by_id[at_registered.id]["stage"] == PipelineStage.REGISTERED.value
        )
        assert (
            by_id[at_offer_letter.id]["stage"] == PipelineStage.OFFER_LETTER.value
        )
        assert (
            by_id[at_withdrawn.id]["stage"] == PipelineStage.WITHDRAWN.value
        )
        # All three stages distinct (catches any 'pick the first stage and
        # reuse it for all rows' bug).
        stages_returned = {by_id[row["id"]]["stage"] for row in body}
        assert stages_returned == {
            PipelineStage.REGISTERED.value,
            PipelineStage.OFFER_LETTER.value,
            PipelineStage.WITHDRAWN.value,
        }


# ---------------------------------------------------------------------------
# Cross-student isolation under multiple applications each
# ---------------------------------------------------------------------------

class TestMultiApplicationCrossStudentIsolation:
    """Two students, each with multiple applications.  The list endpoint
    and direct DB queries must not leak applications across students -- the
    multi-tenant / per-student isolation holds even when each student has
    many applications."""

    def test_get_for_student_a_does_not_include_student_b_apps(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student_a = _seed_student(
            db_session,
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="a-isolation@example.test",
        )
        student_b = _seed_student(
            db_session,
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="b-isolation@example.test",
        )
        a_chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(2)]
        b_chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(2)]
        a_apps = [
            _seed_application_at_stage(
                db_session,
                tenant_id=tenant.id,
                student_id=student_a.id,
                university_id=chain[1].id,
                program_id=chain[2].id,
                stage=PipelineStage.REGISTERED,
            )
            for chain in a_chains
        ]
        b_apps = [
            _seed_application_at_stage(
                db_session,
                tenant_id=tenant.id,
                student_id=student_b.id,
                university_id=chain[1].id,
                program_id=chain[2].id,
                stage=PipelineStage.REGISTERED,
            )
            for chain in b_chains
        ]

        _authenticate_student(
            override_authenticated_user,
            student=student_a,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        returned_ids = {row["id"] for row in body}
        assert returned_ids == {a.id for a in a_apps}
        # Defensive: nothing from student_b leaks through.
        assert not returned_ids & {b.id for b in b_apps}

    def test_get_for_student_b_returns_only_student_b_apps(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Symmetric check: switching the authenticated user swaps which
        subset of applications is visible."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student_a = _seed_student(
            db_session,
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="a-isolation2@example.test",
        )
        student_b = _seed_student(
            db_session,
            tenant_id=tenant.id,
            branch_id=branch.id,
            email="b-isolation2@example.test",
        )
        a_chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(2)]
        b_chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(2)]
        a_apps = [
            _seed_application_at_stage(
                db_session,
                tenant_id=tenant.id,
                student_id=student_a.id,
                university_id=chain[1].id,
                program_id=chain[2].id,
                stage=PipelineStage.REGISTERED,
            )
            for chain in a_chains
        ]
        b_apps = [
            _seed_application_at_stage(
                db_session,
                tenant_id=tenant.id,
                student_id=student_b.id,
                university_id=chain[1].id,
                program_id=chain[2].id,
                stage=PipelineStage.REGISTERED,
            )
            for chain in b_chains
        ]

        _authenticate_student(
            override_authenticated_user,
            student=student_b,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        returned_ids = {row["id"] for row in body}
        assert returned_ids == {b.id for b in b_apps}
        assert not returned_ids & {a.id for a in a_apps}


# ---------------------------------------------------------------------------
# List ordering & row identity with many applications
# ---------------------------------------------------------------------------

class TestMultiApplicationListing:
    """Behavioural expectations of GET /applications when one student has
    several rows."""

    def test_list_returns_applications_in_stable_order(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Three applications seeded in a known order come back from the API
        in a stable order (by id ascending) -- this is the contract that
        the frontend list view relies on."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(3)]
        created = [
            _seed_application_at_stage(
                db_session,
                tenant_id=tenant.id,
                student_id=student.id,
                university_id=chain[1].id,
                program_id=chain[2].id,
                stage=PipelineStage.REGISTERED,
            )
            for chain in chains
        ]

        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )

        response = client.get("/applications")
        assert response.status_code == 200
        body = response.json()
        ids_returned = [row["id"] for row in body]
        assert ids_returned == sorted(ids_returned)
        # And the set matches what we seeded.
        assert set(ids_returned) == {a.id for a in created}

    def test_each_application_response_carries_distinct_ids_and_persists_student_ownership(
        self,
        client,
        db_session,
        override_authenticated_user,
    ):
        """Each row in the list endpoint response is a distinct application
        and every row's ``student_id`` is the calling student's -- even with
        multiple applications."""
        tenant = _create_tenant(db_session)
        branch = seed_branch(db_session, tenant_id=tenant.id)
        student = _seed_student(db_session, tenant_id=tenant.id, branch_id=branch.id)
        chains = [seed_master_data_chain(db_session, tenant_id=tenant.id) for _ in range(4)]
        _authenticate_student(
            override_authenticated_user,
            student=student,
            tenant_id=tenant.id,
            branch_id=branch.id,
        )
        for _, university, program in chains:
            response = client.post(
                "/applications",
                json={"university_id": university.id, "program_id": program.id},
            )
            assert response.status_code == 201

        response = client.get("/applications")
        body = response.json()
        assert len(body) == 4
        ids = [row["id"] for row in body]
        assert len(set(ids)) == 4  # all distinct
        assert {row["student_id"] for row in body} == {student.id}
        assert {row["tenant_id"] for row in body} == {tenant.id}
