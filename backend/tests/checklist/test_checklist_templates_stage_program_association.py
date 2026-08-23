"""Comprehensive E15 stage/program-association tests (issue #134).

This module complements :mod:`tests.checklist.test_checklist_templates_crud`
(which ships with ticket #132) by exercising additional behaviors that
were deliberately out of its scope. Where the bundled tests focus on
the basic CRUD contract (HTTP verbs, tenant scoping, RBAC matrix, 503
on database failure), this module concentrates on the
*stage/program association* contract that defines the E15 ticket:

* round-trip persistence of the (stage, program_id) pair through every
  endpoint path (create, read, list, update, delete),
* mutability of each association field independently and together
  (PATCH changes the stage, PATCH changes the program_id, PATCH changes
  both at once),
* the combined ``stage`` + ``program_id`` filter on the list endpoint
  narrowing as expected,
* multi-program / multi-stage isolation when two templates share a
  stage but have different programs (and vice versa),
* the "unset program_id" semantics of PATCH (explicit ``null`` clears
  the program association; omission preserves it),
* the full :class:`PipelineStage` enum is accepted by both the create
  and update endpoints — including the terminal stages ENROLLED /
  REJECTED / WITHDRAWN, since v1 lets admins define checklist items
  for *any* stage of an application's life.

Every test seeds its own rows (no global fixture dependency on the
seed catalog) so the suite is order-independent and self-contained.

Traceability
------------
* Requirement §5 (per-stage/program checklist templates).
* Journey J8 (Owner/Branch Manager defines a document checklist
  template for a stage/program).
* Epic E15 (Document Checklist Template Management).
* Sibling: #131 (model), #132 (CRUD API + base tests), #133 (frontend
  builder UI). This module is the dedicated test deliverable for #134.
"""

from datetime import datetime, timezone

import pytest

from app.models.checklist_item_template import ChecklistItemTemplate
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user
from tests.master_data.helpers import seed_master_data_chain


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    """Create and persist a tenant for the test."""
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _owner_headers(
    db_session,
    override_authenticated_user,
    *,
    tenant_id: int,
):
    """Override the authenticated user as a CONSULTANCY_OWNER and return auth headers."""
    user_id = make_authenticated_user(
        Role.CONSULTANCY_OWNER, tenant_id=tenant_id
    ).id
    override_authenticated_user(
        make_authenticated_user(
            Role.CONSULTANCY_OWNER,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=None,
        )
    )
    return {"Authorization": "Bearer test-token"}


def _create_template_payload(
    *,
    stage: PipelineStage,
    name: str,
    program_id: int | None = None,
    required: bool = True,
    order_index: int | None = None,
    description: str | None = None,
) -> dict[str, object]:
    """Build a POST /checklist-templates body for the given stage/program."""
    body: dict[str, object] = {
        "stage": stage.value,
        "name": name,
        "required": required,
    }
    if program_id is not None:
        body["program_id"] = program_id
    if order_index is not None:
        body["order_index"] = order_index
    if description is not None:
        body["description"] = description
    return body


# ---------------------------------------------------------------------------
# Round-trip persistence: stage/program survive every read path
# ---------------------------------------------------------------------------


def test_create_template_persists_stage_and_program_on_get(
    client, db_session, override_authenticated_user
):
    """A POST then GET round-trip preserves both stage and program_id."""
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program-specific transcript",
            program_id=program.id,
        ),
        headers=headers,
    )
    assert create.status_code == 201
    template_id = create.json()["id"]

    response = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value
    assert body["program_id"] == program.id


def test_create_template_persists_stage_and_program_on_list(
    client, db_session, override_authenticated_user
):
    """A POST then LIST round-trip preserves both stage and program_id."""
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.OFFER_LETTER,
            name="Offer-letter acceptance",
            program_id=program.id,
        ),
        headers=headers,
    )
    assert create.status_code == 201
    created_id = create.json()["id"]

    response = client.get("/checklist-templates", headers=headers)

    assert response.status_code == 200
    body = response.json()
    matching = [item for item in body if item["id"] == created_id]
    assert len(matching) == 1
    assert matching[0]["stage"] == PipelineStage.OFFER_LETTER.value
    assert matching[0]["program_id"] == program.id


def test_create_template_persists_global_program_id_as_null(
    client, db_session, override_authenticated_user
):
    """A POST without program_id persists ``program_id`` as ``None`` (global)."""
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    response = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.REGISTERED,
            name="Global passport",
        ),
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["program_id"] is None
    assert body["stage"] == PipelineStage.REGISTERED.value

    # And the GET round-trip confirms it.
    followup = client.get(
        f"/checklist-templates/{body['id']}", headers=headers
    )
    assert followup.status_code == 200
    assert followup.json()["program_id"] is None


# ---------------------------------------------------------------------------
# Stage association: mutability and isolation
# ---------------------------------------------------------------------------


def test_update_template_stage_persists_through_get_and_list(
    client, db_session, override_authenticated_user
):
    """A PATCH that changes the stage is visible to both GET and LIST."""
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.REGISTERED,
            name="Passport copy",
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"stage": PipelineStage.VISA_PROCESSING.value},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["stage"] == PipelineStage.VISA_PROCESSING.value

    # GET reflects the new stage.
    followup_get = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert followup_get.status_code == 200
    assert followup_get.json()["stage"] == PipelineStage.VISA_PROCESSING.value

    # LIST filtered by the new stage includes the row.
    followup_list = client.get(
        "/checklist-templates",
        params={"stage": PipelineStage.VISA_PROCESSING.value},
        headers=headers,
    )
    assert followup_list.status_code == 200
    ids = [item["id"] for item in followup_list.json()]
    assert template_id in ids

    # LIST filtered by the OLD stage excludes the row.
    followup_old = client.get(
        "/checklist-templates",
        params={"stage": PipelineStage.REGISTERED.value},
        headers=headers,
    )
    assert followup_old.status_code == 200
    old_ids = [item["id"] for item in followup_old.json()]
    assert template_id not in old_ids


def test_update_template_stage_to_every_non_terminal_stage_is_accepted(
    client, db_session, override_authenticated_user
):
    """All non-terminal :class:`PipelineStage` values are valid update targets.

    v1 lets admins define checklist items for any stage of the
    application lifecycle; the endpoint should accept every enum value
    (no implicit restriction to "active" stages). Terminal stages are
    covered in their own test below.
    """
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    for target_stage in PipelineStage.non_terminal_stages():
        create = client.post(
            "/checklist-templates",
            json=_create_template_payload(
                stage=PipelineStage.REGISTERED,
                name=f"Stage-cycle {target_stage.value}",
            ),
            headers=headers,
        )
        assert create.status_code == 201, target_stage.value
        template_id = create.json()["id"]

        patch = client.patch(
            f"/checklist-templates/{template_id}",
            json={"stage": target_stage.value},
            headers=headers,
        )
        assert patch.status_code == 200, (
            f"stage {target_stage.value} should be accepted on update"
        )
        assert patch.json()["stage"] == target_stage.value


def test_update_template_stage_to_a_terminal_stage_is_accepted(
    client, db_session, override_authenticated_user
):
    """Even the terminal stages (ENROLLED/REJECTED/WITHDRAWN) are valid
    update targets for the ``stage`` field — the checklist endpoint does
    not gate on whether the application is "still moving".

    E40 marks an application Withdrawn / Rejected / Enrolled; an admin
    may still want to define a checklist for those stages (e.g. "exit
    interview form" for Withdrawn, "enrollment confirmation" for
    Enrolled). The API must accept the change.
    """
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    for terminal_stage in PipelineStage.terminal_stages():
        create = client.post(
            "/checklist-templates",
            json=_create_template_payload(
                stage=PipelineStage.REGISTERED,
                name=f"Terminal-stage template {terminal_stage.value}",
            ),
            headers=headers,
        )
        template_id = create.json()["id"]

        patch = client.patch(
            f"/checklist-templates/{template_id}",
            json={"stage": terminal_stage.value},
            headers=headers,
        )
        assert patch.status_code == 200
        assert patch.json()["stage"] == terminal_stage.value


def test_update_template_stage_omitting_field_preserves_existing_stage(
    client, db_session, override_authenticated_user
):
    """An update body that omits ``stage`` preserves the original stage."""
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Preserve stage",
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"description": "Updated description"},
        headers=headers,
    )

    assert patch.status_code == 200
    body = patch.json()
    assert body["stage"] == PipelineStage.DOCUMENT_VERIFICATION.value
    assert body["description"] == "Updated description"


# ---------------------------------------------------------------------------
# Program association: mutability, unset semantics, and isolation
# ---------------------------------------------------------------------------


def test_update_template_program_to_null_clears_program_association(
    client, db_session, override_authenticated_user
):
    """Explicit ``program_id: null`` on PATCH clears the program association.

    Confirms the documented Pydantic ``exclude_unset`` semantics:
    omitting the field preserves the existing value; setting it to
    ``null`` clears it. The end state is a *global* template.
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program-specific form",
            program_id=program.id,
        ),
        headers=headers,
    )
    assert create.json()["program_id"] == program.id
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"program_id": None},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["program_id"] is None

    # GET confirms the cleared state.
    followup = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert followup.json()["program_id"] is None


def test_update_template_omitting_program_preserves_existing_program(
    client, db_session, override_authenticated_user
):
    """An update body that omits ``program_id`` keeps the existing program_id.

    This is the *opposite* of the explicit-null test above: the
    ``exclude_unset`` semantics means a missing field does NOT clear the
    association. This test guards against an accidental regression to
    "PATCH always sets program_id".
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program-pinned",
            program_id=program.id,
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"name": "Program-pinned renamed"},
        headers=headers,
    )

    assert patch.status_code == 200
    body = patch.json()
    assert body["program_id"] == program.id
    assert body["name"] == "Program-pinned renamed"


def test_update_template_reassign_program_to_another_program_in_tenant(
    client, db_session, override_authenticated_user
):
    """Reassigning ``program_id`` to a different program in the same tenant persists."""
    tenant = _create_tenant(db_session)
    country, _, program_a = seed_master_data_chain(
        db_session, tenant_id=tenant.id
    )
    from tests.master_data.helpers import seed_university, seed_program

    university_b = seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=country.id,
        name="Second University",
    )
    program_b = seed_program(
        db_session,
        tenant_id=tenant.id,
        university_id=university_b.id,
        name="Second Program",
    )
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Reassignable",
            program_id=program_a.id,
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"program_id": program_b.id},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["program_id"] == program_b.id

    # GET and LIST both reflect the new program_id.
    followup_get = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert followup_get.json()["program_id"] == program_b.id

    followup_list = client.get(
        "/checklist-templates",
        params={"program_id": program_b.id},
        headers=headers,
    )
    assert followup_list.status_code == 200
    ids = [item["id"] for item in followup_list.json()]
    assert template_id in ids

    # And the old program no longer matches.
    followup_old = client.get(
        "/checklist-templates",
        params={"program_id": program_a.id},
        headers=headers,
    )
    old_ids = [item["id"] for item in followup_old.json()]
    assert template_id not in old_ids


# ---------------------------------------------------------------------------
# Combined (stage + program_id) filtering
# ---------------------------------------------------------------------------


def test_list_combines_stage_and_program_filters(
    client, db_session, override_authenticated_user
):
    """Passing BOTH ``stage`` and ``program_id`` narrows the list to the
    intersection — only templates that match *both* filters appear.

    Seeds a 3x3 grid (3 stages × 3 program scopes: global, program A,
    program B) and confirms the filter pair returns the single row at
    the requested intersection.
    """
    tenant = _create_tenant(db_session)
    country, _, program_a = seed_master_data_chain(db_session, tenant_id=tenant.id)
    from tests.master_data.helpers import seed_university, seed_program

    university_b = seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=country.id,
        name="Second University",
    )
    program_b = seed_program(
        db_session,
        tenant_id=tenant.id,
        university_id=university_b.id,
        name="Second Program",
    )

    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    # 3 stages × 3 program scopes.
    now = datetime.now(timezone.utc)
    rows: list[ChecklistItemTemplate] = []
    for stage in (
        PipelineStage.DOCUMENT_VERIFICATION,
        PipelineStage.OFFER_LETTER,
        PipelineStage.VISA_PROCESSING,
    ):
        for program_id, scope_label in (
            (None, "global"),
            (program_a.id, "A"),
            (program_b.id, "B"),
        ):
            row = ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=stage,
                program_id=program_id,
                name=f"{stage.value}/{scope_label}",
                required=True,
                created_at=now,
                updated_at=now,
            )
            rows.append(row)
    db_session.add_all(rows)
    db_session.commit()

    # Filter intersection: stage=DOCUMENT_VERIFICATION + program_id=A
    response = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program_a.id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body}
    assert names == {f"{PipelineStage.DOCUMENT_VERIFICATION.value}/A"}

    # Filter intersection: stage=OFFER_LETTER + program_id=program_a
    # (the only row at this intersection in the 3x3 grid is
    # offer_letter/A — verify the AND semantics by checking it returns
    # exactly that row, not also offer_letter/global or offer_letter/B).
    response = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.OFFER_LETTER.value,
            "program_id": program_a.id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"offer_letter/A"}

    # Confirm a stage with NO program match returns the empty set:
    # stage=REGISTERED + program_id=program_b → no row in the grid is
    # at (REGISTERED, program_b) so the result must be empty.
    response = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.REGISTERED.value,
            "program_id": program_b.id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []

    # No filter at all returns every row.
    response = client.get("/checklist-templates", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 9


def test_list_combined_filter_does_not_match_when_only_one_filter_passes(
    client, db_session, override_authenticated_user
):
    """Confirm the combined filter is an AND, not an OR.

    Seeds two rows with the same stage but different programs, and one
    row with a different stage but the requested program. A combined
    filter (stage=X, program_id=Y) must return zero rows — neither row
    matches *both* filters.
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=program.id,
                name="Correct stage, correct program",
                required=True,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="Correct stage, wrong program (global)",
                required=True,
                created_at=now,
                updated_at=now,
            ),
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.OFFER_LETTER,
                program_id=program.id,
                name="Wrong stage, correct program",
                required=True,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    # Combined filter for stage=DOCUMENT_VERIFICATION + program_id=program
    # returns ONLY the first row (correct stage AND correct program).
    response = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program.id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Correct stage, correct program"}


# ---------------------------------------------------------------------------
# Multi-program / multi-stage isolation
# ---------------------------------------------------------------------------


def test_multiple_templates_same_stage_different_programs_are_isolated(
    client, db_session, override_authenticated_user
):
    """Two templates at the same stage but different programs are
    independently listable: filtering by program A returns only A's
    template; filtering by program B returns only B's; filtering by no
    program returns the two program-scoped templates plus any globals.
    """
    tenant = _create_tenant(db_session)
    country, _, program_a = seed_master_data_chain(db_session, tenant_id=tenant.id)
    from tests.master_data.helpers import seed_university, seed_program

    university_b = seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=country.id,
        name="Second University",
    )
    program_b = seed_program(
        db_session,
        tenant_id=tenant.id,
        university_id=university_b.id,
        name="Second Program",
    )
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create_a = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program A checklist",
            program_id=program_a.id,
        ),
        headers=headers,
    )
    create_b = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program B checklist",
            program_id=program_b.id,
        ),
        headers=headers,
    )
    create_global = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Global checklist",
        ),
        headers=headers,
    )

    response_a = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program_a.id,
        },
        headers=headers,
    )
    assert response_a.status_code == 200
    a_names = {item["name"] for item in response_a.json()}
    assert a_names == {"Program A checklist"}

    response_b = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program_b.id,
        },
        headers=headers,
    )
    b_names = {item["name"] for item in response_b.json()}
    assert b_names == {"Program B checklist"}

    # Unfiltered list scoped to the stage contains all three.
    response_stage = client.get(
        "/checklist-templates",
        params={"stage": PipelineStage.DOCUMENT_VERIFICATION.value},
        headers=headers,
    )
    stage_names = {item["name"] for item in response_stage.json()}
    assert stage_names == {
        "Program A checklist",
        "Program B checklist",
        "Global checklist",
    }

    # Suppress unused-locals lints; we used the create ids for clarity.
    assert create_a.status_code == 201
    assert create_b.status_code == 201
    assert create_global.status_code == 201


def test_multiple_templates_same_program_different_stages_are_isolated(
    client, db_session, override_authenticated_user
):
    """Two templates for the same program but different stages are
    independently listable: filtering by program returns both,
    filtering by stage narrows to one.
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create_dv = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Doc-ver: program-specific",
            program_id=program.id,
        ),
        headers=headers,
    )
    create_ol = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.OFFER_LETTER,
            name="Offer-letter: program-specific",
            program_id=program.id,
        ),
        headers=headers,
    )

    # Filter only by program — both stages appear.
    by_program = client.get(
        "/checklist-templates",
        params={"program_id": program.id},
        headers=headers,
    )
    assert by_program.status_code == 200
    names = {item["name"] for item in by_program.json()}
    assert names == {
        "Doc-ver: program-specific",
        "Offer-letter: program-specific",
    }

    # Filter by program AND stage — only one matches.
    by_both = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.OFFER_LETTER.value,
            "program_id": program.id,
        },
        headers=headers,
    )
    both_names = {item["name"] for item in by_both.json()}
    assert both_names == {"Offer-letter: program-specific"}

    assert create_dv.status_code == 201
    assert create_ol.status_code == 201


# ---------------------------------------------------------------------------
# Combined-field updates
# ---------------------------------------------------------------------------


def test_update_can_change_stage_and_program_simultaneously(
    client, db_session, override_authenticated_user
):
    """A single PATCH body can carry both ``stage`` and ``program_id``
    changes — both are applied atomically.
    """
    tenant = _create_tenant(db_session)
    country, _, program_a = seed_master_data_chain(db_session, tenant_id=tenant.id)
    from tests.master_data.helpers import seed_university, seed_program

    university_b = seed_university(
        db_session,
        tenant_id=tenant.id,
        country_id=country.id,
        name="Second University",
    )
    program_b = seed_program(
        db_session,
        tenant_id=tenant.id,
        university_id=university_b.id,
        name="Second Program",
    )
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.REGISTERED,
            name="Multi-field update",
            program_id=program_a.id,
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={
            "stage": PipelineStage.VISA_PROCESSING.value,
            "program_id": program_b.id,
        },
        headers=headers,
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["stage"] == PipelineStage.VISA_PROCESSING.value
    assert body["program_id"] == program_b.id

    # GET reflects both.
    followup = client.get(
        f"/checklist-templates/{template_id}", headers=headers
    )
    assert followup.json()["stage"] == PipelineStage.VISA_PROCESSING.value
    assert followup.json()["program_id"] == program_b.id

    # Combined filter on the NEW (stage, program) intersection matches.
    by_new = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.VISA_PROCESSING.value,
            "program_id": program_b.id,
        },
        headers=headers,
    )
    new_ids = [item["id"] for item in by_new.json()]
    assert template_id in new_ids

    # Combined filter on the OLD (stage, program) intersection does NOT.
    by_old = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.REGISTERED.value,
            "program_id": program_a.id,
        },
        headers=headers,
    )
    old_ids = [item["id"] for item in by_old.json()]
    assert template_id not in old_ids


# ---------------------------------------------------------------------------
# Cross-tenant stage/program isolation (defense-in-depth)
# ---------------------------------------------------------------------------


def test_cross_tenant_program_id_is_unprocessable_on_update(
    client, db_session, override_authenticated_user
):
    """Updating a template's program_id to a row in another tenant is rejected
    with 422 (not 404) — the value is unprocessable for this tenant.

    This is a tighter assertion than the bundled CRUD tests: it
    specifically targets the stage/program association's integrity
    when the caller's tenant and the target program's tenant diverge.
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    _, _, program_b = seed_master_data_chain(db_session, tenant_id=tenant_b.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant_a.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="A's template",
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"program_id": program_b.id},
        headers=headers,
    )

    assert patch.status_code == 422
    assert patch.json()["detail"] == "Invalid program for the caller's tenant"


def test_cross_tenant_stage_change_via_reassignment_is_blocked_via_404(
    client, db_session, override_authenticated_user
):
    """A cross-tenant PATCH (different tenant's template id) is a 404 — the
    stage/program association on the foreign row is invisible.

    Confirms the stage/program association cannot be mutated by a
    hostile caller probing a different tenant's template ids.
    """
    tenant_a = _create_tenant(db_session, name="Tenant A", slug="tenant-a")
    tenant_b = _create_tenant(db_session, name="Tenant B", slug="tenant-b")
    now = datetime.now(timezone.utc)
    template_b = ChecklistItemTemplate(
        tenant_id=tenant_b.id,
        stage=PipelineStage.REGISTERED,
        program_id=None,
        name="Tenant B: target",
        required=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(template_b)
    db_session.commit()
    db_session.refresh(template_b)

    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant_a.id)

    response = client.patch(
        f"/checklist-templates/{template_b.id}",
        json={
            "stage": PipelineStage.VISA_PROCESSING.value,
            "program_id": None,
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Checklist template not found"


# ---------------------------------------------------------------------------
# List ordering when many stage/program combinations coexist
# ---------------------------------------------------------------------------


def test_list_returns_rows_in_deterministic_stage_order(
    client, db_session, override_authenticated_user
):
    """Templates are returned sorted by ``stage`` (enum value ascending),
    then ``order_index`` (NULLS LAST), then ``id`` as a stable
    tie-breaker. Confirms the contract holds when many rows with
    mixed stage/program associations are seeded.
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            # Visa stage, program-scoped, no order.
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.VISA_PROCESSING,
                program_id=program.id,
                name="Visa/program/no-order",
                required=True,
                order_index=None,
                created_at=now,
                updated_at=now,
            ),
            # Registered stage, global, order 1.
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.REGISTERED,
                program_id=None,
                name="REG/global/o1",
                required=True,
                order_index=1,
                created_at=now,
                updated_at=now,
            ),
            # Registered stage, program-scoped, order 1.
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.REGISTERED,
                program_id=program.id,
                name="REG/program/o1",
                required=True,
                order_index=1,
                created_at=now,
                updated_at=now,
            ),
            # Document-verification stage, global, order 1.
            ChecklistItemTemplate(
                tenant_id=tenant.id,
                stage=PipelineStage.DOCUMENT_VERIFICATION,
                program_id=None,
                name="DV/global/o1",
                required=True,
                order_index=1,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/checklist-templates", headers=headers)

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    # Stages sort by enum value ascending:
    #   'application_submitted' < 'document_verification' < 'registered' < 'visa_processing'
    # Within stage, order_index asc NULLS LAST; within that, id asc.
    # REG/global/o1 and REG/program/o1 share (stage, order_index) — they
    # fall back to id ordering. We don't assert their relative order
    # beyond them both appearing together; we do assert the stage
    # grouping.
    assert names[0] == "DV/global/o1"
    assert names[-1] == "Visa/program/no-order"
    assert set(names[1:3]) == {"REG/global/o1", "REG/program/o1"}


# ---------------------------------------------------------------------------
# Stage/program isolation under deletion
# ---------------------------------------------------------------------------


def test_delete_template_removes_only_the_targeted_stage_program_pair(
    client, db_session, override_authenticated_user
):
    """Deleting a template removes exactly that (stage, program_id) pair —
    other templates with the same stage or the same program survive.
    """
    tenant = _create_tenant(db_session)
    _, _, program = seed_master_data_chain(db_session, tenant_id=tenant.id)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    # Three templates at the same stage, two with the same program and
    # one global. Delete the program-scoped one and confirm the others
    # survive, including the second program-scoped row at a different
    # stage.
    keep_same_stage_global = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Same-stage global",
        ),
        headers=headers,
    ).json()
    delete_target = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Same-stage program-scoped (DELETE)",
            program_id=program.id,
        ),
        headers=headers,
    ).json()
    keep_other_stage = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.OFFER_LETTER,
            name="Other-stage program-scoped",
            program_id=program.id,
        ),
        headers=headers,
    ).json()

    delete_response = client.delete(
        f"/checklist-templates/{delete_target['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    # The other two survive.
    list_response = client.get("/checklist-templates", headers=headers)
    assert list_response.status_code == 200
    surviving_ids = {item["id"] for item in list_response.json()}
    assert keep_same_stage_global["id"] in surviving_ids
    assert keep_other_stage["id"] in surviving_ids
    assert delete_target["id"] not in surviving_ids

    # Filtering by the deleted (stage, program) intersection returns empty.
    followup = client.get(
        "/checklist-templates",
        params={
            "stage": PipelineStage.DOCUMENT_VERIFICATION.value,
            "program_id": program.id,
        },
        headers=headers,
    )
    assert followup.status_code == 200
    assert followup.json() == []


# ---------------------------------------------------------------------------
# Validation surface specific to stage/program association
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_stage",
    ["not_a_stage", "REGISTERED", "Document_Verification", " ", "123"],
)
def test_create_rejects_unknown_stage_values(
    client, db_session, override_authenticated_user, bad_stage
):
    """Unknown / typo'd stage values are rejected at the schema boundary (422).

    The Pydantic :class:`PipelineStage` enum is the source of truth for
    valid stages; the API must surface a 422 (not silently coerce to a
    matching enum value, which would be a security-relevant footgun).
    """
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    response = client.post(
        "/checklist-templates",
        json={"stage": bad_stage, "name": "x"},
        headers=headers,
    )

    assert response.status_code == 422


def test_update_rejects_unknown_stage_values(
    client, db_session, override_authenticated_user
):
    """The same schema boundary applies on PATCH: a typo'd stage is 422."""
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.REGISTERED,
            name="Will have its stage typo'd",
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    patch = client.patch(
        f"/checklist-templates/{template_id}",
        json={"stage": "totally-not-a-stage"},
        headers=headers,
    )

    assert patch.status_code == 422


def test_update_rejects_non_positive_program_id(
    client, db_session, override_authenticated_user
):
    """A zero or negative ``program_id`` is rejected (Query(ge=1) → 422)."""
    tenant = _create_tenant(db_session)
    headers = _owner_headers(db_session, override_authenticated_user, tenant_id=tenant.id)

    create = client.post(
        "/checklist-templates",
        json=_create_template_payload(
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Program validation",
        ),
        headers=headers,
    )
    template_id = create.json()["id"]

    for bad_value in (0, -1):
        patch = client.patch(
            f"/checklist-templates/{template_id}",
            json={"program_id": bad_value},
            headers=headers,
        )
        assert patch.status_code == 422, (
            f"program_id={bad_value} should be rejected"
        )
