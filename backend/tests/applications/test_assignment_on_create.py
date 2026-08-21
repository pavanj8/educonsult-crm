"""Counselor auto-assignment on application creation (E19; J12; #151, #152).

Verifies the trigger wired into ``POST /applications``: a new application is
assigned round-robin to a counselor in the student's branch, and over many
applications the load is distributed evenly across the branch's counselors.
"""

from __future__ import annotations

from collections import Counter

from app.models.application import Application
from app.models.tenant import Tenant
from app.rbac.roles import Role
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user
from tests.master_data.helpers import seed_master_data_chain


def _tenant(db_session, slug) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_student(override_authenticated_user, *, student, tenant_id, branch_id):
    override_authenticated_user(
        make_authenticated_user(Role.STUDENT, user_id=student.id, tenant_id=tenant_id, branch_id=branch_id)
    )


def _create_app(client, override_authenticated_user, *, student, tenant, branch, university, program):
    _auth_student(override_authenticated_user, student=student, tenant_id=tenant.id, branch_id=branch.id)
    return client.post(
        "/applications",
        json={"university_id": university.id, "program_id": program.id},
        headers={"Authorization": "Bearer test-token"},
    )


def test_create_assigns_a_branch_counselor(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "asg-one")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id, email="s1@t.test")
    _, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = _create_app(client, override_authenticated_user, student=student, tenant=tenant,
                           branch=branch, university=university, program=program)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["branch_id"] == branch.id
    assert body["assigned_counselor_id"] == counselor.id


def test_create_unassigned_when_branch_has_no_counselor(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "asg-none")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id, email="s@t.test")
    _, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    response = _create_app(client, override_authenticated_user, student=student, tenant=tenant,
                           branch=branch, university=university, program=program)

    assert response.status_code == 201, response.text
    assert response.json()["assigned_counselor_id"] is None


def test_create_distributes_evenly_across_branch_counselors(client, db_session, override_authenticated_user):
    tenant = _tenant(db_session, "asg-even")
    branch = seed_branch(db_session, tenant_id=tenant.id)
    other_branch = seed_branch(db_session, tenant_id=tenant.id, name="Other", city="Pune")
    counselors = [
        make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=branch.id, email=f"c{i}@t.test")
        for i in range(3)
    ]
    # A counselor in a different branch must never be assigned here.
    make_db_user(db_session, Role.COUNSELOR, tenant_id=tenant.id, branch_id=other_branch.id, email="cx@t.test")
    _, university, program = seed_master_data_chain(db_session, tenant_id=tenant.id)

    assigned = []
    for i in range(9):
        student = make_db_user(db_session, Role.STUDENT, tenant_id=tenant.id, branch_id=branch.id, email=f"stu{i}@t.test")
        resp = _create_app(client, override_authenticated_user, student=student, tenant=tenant,
                           branch=branch, university=university, program=program)
        assert resp.status_code == 201, resp.text
        assigned.append(resp.json()["assigned_counselor_id"])

    counselor_ids = {c.id for c in counselors}
    assert set(assigned) <= counselor_ids  # only this branch's counselors
    counts = Counter(assigned)
    assert max(counts.values()) - min(counts.values()) <= 1  # even
    assert sum(counts.values()) == 9

    # DB reflects the assignments.
    db_rows = db_session.query(Application).filter(Application.branch_id == branch.id).all()
    assert len(db_rows) == 9
    assert all(row.assigned_counselor_id in counselor_ids for row in db_rows)
