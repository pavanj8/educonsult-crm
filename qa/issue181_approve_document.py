"""Black-box tests for issue #181 — Document Approval endpoint.

Issue:    #181 (E29; Journey J22)
Endpoint: POST /verifier/documents/{document_id}/approve

Tests are derived ONLY from:
  * Issue #181's acceptance criteria
  * docs/requirements.md §5 (Documents: verifier approves/rejects with
    comments), §3 (Document Verifier role), §8 (Audit log)
  * docs/journeys.md J22 (Document Verifier approves a document)
  * docs/epics.md E29 (Document Approval)
  * OpenAPI contract fetched live from /openapi.json

The seeded environment provides two pending StudentDocument rows:
  * id=1, tenant_id=1 (Apex)    — verifier@apex.demo.test can act on it
  * id=2, tenant_id=2 (GlobalReach) — verifier@globalreach.demo.test

Each test is isolated: tests that mutate document state run against a
freshly-reseeded row (handled by re-seeding at the top of the script).
"""
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "http://127.0.0.1:56108"
DB = "backend/qa_run_56108.db"


# --- helpers ---------------------------------------------------------------


def login(email: str, password: str = "demo-password") -> str:
    r = requests.post(
        f"{BASE}/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def reseed_documents():
    """Restore the two pending documents we depend on."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    # Wipe all and re-create cleanly so test order doesn't matter.
    cur.execute("DELETE FROM student_documents")
    cur.execute(
        "INSERT INTO student_documents (tenant_id, application_id, "
        "checklist_item_template_id, status, original_filename, "
        "content_type, size_bytes, storage_path, uploaded_by_user_id, "
        "uploaded_at, verified_by_user_id, verified_at, "
        "rejection_reason, approval_comment, created_at, updated_at) "
        "VALUES (1, 1, NULL, 'pending', 'transcript.pdf', "
        "'application/pdf', 1024, 'qa-seed/pending-1', 8, ?, "
        "NULL, NULL, NULL, NULL, ?, ?)",
        (now, now, now),
    )
    cur.execute(
        "INSERT INTO student_documents (tenant_id, application_id, "
        "checklist_item_template_id, status, original_filename, "
        "content_type, size_bytes, storage_path, uploaded_by_user_id, "
        "uploaded_at, verified_by_user_id, verified_at, "
        "rejection_reason, approval_comment, created_at, updated_at) "
        "VALUES (2, 2, NULL, 'pending', 'foreign.pdf', "
        "'application/pdf', 2048, 'qa-seed/foreign-2', 15, ?, "
        "NULL, NULL, NULL, NULL, ?, ?)",
        (now, now, now),
    )
    conn.commit()
    conn.close()


def doc_state(doc_id: int) -> dict:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    row = cur.execute(
        "SELECT * FROM student_documents WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


# --- test runner -----------------------------------------------------------


class TestReport:
    def __init__(self):
        self.cases = []

    def add(self, name, ok, detail=""):
        self.cases.append((name, ok, detail))
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}  {detail}")

    def summary(self):
        passed = sum(1 for _, ok, _ in self.cases if ok)
        failed = sum(1 for _, ok, _ in self.cases if not ok)
        print(f"\n{'=' * 70}")
        print(f"Total: {len(self.cases)}  Passed: {passed}  Failed: {failed}")
        if failed:
            print("\nFAILED CASES:")
            for n, ok, d in self.cases:
                if not ok:
                    print(f"  - {n}  {d}")
        return failed == 0


def run():
    print("Re-seeding pending documents...")
    reseed_documents()
    rep = TestReport()

    # Get tokens for each role
    print("\n--- acquiring tokens ---")
    tok_verifier_t1 = login("verifier@apex.demo.test")
    tok_verifier_t2 = login("verifier@globalreach.demo.test")
    tok_student_t1 = login("student@apex.demo.test")
    tok_owner_t1 = login("owner@apex.demo.test")
    tok_manager_t1 = login("manager.mumbai@apex.demo.test")
    tok_counselor_t1 = login("counselor@demo.test")  # tenant 1 counselor
    tok_visa_t1 = login("visa@apex.demo.test")  # tenant 1 visa processor
    tok_recep_t1 = login("reception@apex.demo.test")
    tok_student_t2 = login("student@globalreach.demo.test")
    rep.add(
        "login: verifier@apex",
        bool(tok_verifier_t1),
        f"len={len(tok_verifier_t1)}",
    )
    rep.add(
        "login: verifier@globalreach",
        bool(tok_verifier_t2),
        f"len={len(tok_verifier_t2)}",
    )

    DOC_T1 = 1  # pending doc owned by tenant 1
    DOC_T2 = 2  # pending doc owned by tenant 2

    # ============================================================
    # 1. Happy path: verifier approves own-tenant pending document
    # ============================================================
    print("\n--- 1. Happy-path approve ---")
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "Looks good"},
    )
    rep.add("happy: approve returns 200", r.status_code == 200, f"got {r.status_code} body={r.text[:200]}")
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "happy: response.status == 'approved'",
        body.get("status") == "approved",
        f"got status={body.get('status')!r}",
    )
    rep.add(
        "happy: response.verified_by_user_id set",
        isinstance(body.get("verified_by_user_id"), int),
        f"got {body.get('verified_by_user_id')!r}",
    )
    rep.add(
        "happy: response.verified_at is ISO timestamp",
        bool(body.get("verified_at")),
        f"got {body.get('verified_at')!r}",
    )
    rep.add(
        "happy: response.approval_comment echoed",
        body.get("approval_comment") == "Looks good",
        f"got {body.get('approval_comment')!r}",
    )
    rep.add(
        "happy: response.rejection_reason is None",
        body.get("rejection_reason") is None,
        f"got {body.get('rejection_reason')!r}",
    )
    # Verify DB row updated
    dbrow = doc_state(DOC_T1)
    rep.add(
        "happy: DB row status='approved'",
        dbrow.get("status") == "approved",
        f"got {dbrow.get('status')!r}",
    )
    rep.add(
        "happy: DB row approval_comment persisted",
        dbrow.get("approval_comment") == "Looks good",
        f"got {dbrow.get('approval_comment')!r}",
    )
    rep.add(
        "happy: DB row rejection_reason stays None",
        dbrow.get("rejection_reason") is None,
        f"got {dbrow.get('rejection_reason')!r}",
    )

    # ============================================================
    # 2. Permission denials
    # ============================================================
    print("\n--- 2. Permission denials ---")
    # Reseed to get a fresh pending doc
    reseed_documents()

    # 2a. Unauthenticated
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        json={"comment": "hi"},
    )
    rep.add(
        "perm: unauthenticated -> 401",
        r.status_code == 401,
        f"got {r.status_code}",
    )

    # 2b. Student tries to approve (has document:upload, not document:verify)
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_student_t1),
        json={"comment": "sneaky"},
    )
    rep.add(
        "perm: STUDENT -> 403",
        r.status_code == 403,
        f"got {r.status_code} body={r.text[:120]}",
    )

    # 2c. Owner tries to approve
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_owner_t1),
        json={"comment": "owner"},
    )
    rep.add(
        "perm: CONSULTANCY_OWNER -> 403",
        r.status_code == 403,
        f"got {r.status_code}",
    )

    # 2d. Branch manager tries to approve
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_manager_t1),
        json={"comment": "manager"},
    )
    rep.add(
        "perm: BRANCH_MANAGER -> 403",
        r.status_code == 403,
        f"got {r.status_code}",
    )

    # 2e. Counselor tries to approve (tolerant — some seed configs have no counselor at apex)
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_counselor_t1),
        json={"comment": "counselor"},
    )
    rep.add(
        "perm: COUNSELOR -> 403",
        r.status_code == 403,
        f"got {r.status_code} body={r.text[:120]}",
    )

    # 2f. Receptionist tries to approve
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_recep_t1),
        json={"comment": "recep"},
    )
    rep.add(
        "perm: RECEPTIONIST -> 403",
        r.status_code == 403,
        f"got {r.status_code}",
    )

    # 2g. Visa processor tries to approve
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_visa_t1),
        json={"comment": "visa"},
    )
    rep.add(
        "perm: VISA_PROCESSOR -> 403",
        r.status_code == 403,
        f"got {r.status_code}",
    )

    # ============================================================
    # 3. Cross-tenant attempt (verifier@globalreach hits apex doc)
    # ============================================================
    print("\n--- 3. Cross-tenant scoping ---")
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t2),
        json={"comment": "wrong tenant"},
    )
    rep.add(
        "cross-tenant: verifier from other tenant -> 404",
        r.status_code == 404,
        f"got {r.status_code} body={r.text[:160]}",
    )
    # Apex doc must still be pending (untouched by wrong-tenant verifier)
    dbrow = doc_state(DOC_T1)
    rep.add(
        "cross-tenant: apex doc stays pending (not modified)",
        dbrow.get("status") == "pending",
        f"got status={dbrow.get('status')!r}",
    )

    # ============================================================
    # 4. Non-existent document id
    # ============================================================
    print("\n--- 4. Non-existent doc id ---")
    r = requests.post(
        f"{BASE}/verifier/documents/999999/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "ghost"},
    )
    rep.add(
        "missing: 999999 -> 404",
        r.status_code == 404,
        f"got {r.status_code}",
    )

    # ============================================================
    # 5. 422 — document not in pending state
    # ============================================================
    print("\n--- 5. 422 on non-pending documents ---")
    # Approve doc 1 first (state from steps 2-4 left it pending), then try again.
    requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "first approval"},
    )
    dbrow = doc_state(DOC_T1)
    rep.add(
        "setup: doc 1 is now approved",
        dbrow.get("status") == "approved",
        f"got status={dbrow.get('status')!r}",
    )
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "second time"},
    )
    rep.add(
        "422: re-approve already-approved -> 422",
        r.status_code == 422,
        f"got {r.status_code} body={r.text[:200]}",
    )
    # Make a rejected row and try to approve it
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "UPDATE student_documents SET status='rejected', "
        "rejection_reason='bad' WHERE id=?",
        (DOC_T1,),
    )
    conn.commit()
    conn.close()
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "approve after reject"},
    )
    rep.add(
        "422: approve after reject -> 422",
        r.status_code == 422,
        f"got {r.status_code} body={r.text[:200]}",
    )

    # ============================================================
    # 6. Comment length validation (max 2000 chars)
    # ============================================================
    print("\n--- 6. Comment length validation ---")
    reseed_documents()
    too_long = "x" * 2001
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": too_long},
    )
    rep.add(
        "validation: 2001-char comment -> 422",
        r.status_code == 422,
        f"got {r.status_code} body={r.text[:160]}",
    )

    # Boundary: exactly 2000 chars should succeed
    ok_len = "y" * 2000
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": ok_len},
    )
    rep.add(
        "validation: 2000-char comment -> 200",
        r.status_code == 200,
        f"got {r.status_code} body={r.text[:160]}",
    )
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "validation: 2000-char comment persisted exactly",
        body.get("approval_comment") == ok_len,
        f"len got={len(body.get('approval_comment') or '')}",
    )

    # ============================================================
    # 7. Body variations
    # ============================================================
    print("\n--- 7. Body variations ---")
    reseed_documents()
    # 7a. Empty body (no comment at all)
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
    )
    rep.add(
        "body: no body -> 200 (comment optional)",
        r.status_code == 200,
        f"got {r.status_code} body={r.text[:160]}",
    )
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "body: no body -> approval_comment is null",
        body.get("approval_comment") is None,
        f"got {body.get('approval_comment')!r}",
    )

    # 7b. Empty JSON {}
    reseed_documents()
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={},
    )
    rep.add(
        "body: empty JSON {} -> 200",
        r.status_code == 200,
        f"got {r.status_code}",
    )
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "body: empty JSON {} -> approval_comment null",
        body.get("approval_comment") is None,
        f"got {body.get('approval_comment')!r}",
    )

    # 7c. Explicit null comment
    reseed_documents()
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": None},
    )
    rep.add(
        "body: explicit null comment -> 200",
        r.status_code == 200,
        f"got {r.status_code}",
    )
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "body: explicit null -> approval_comment null",
        body.get("approval_comment") is None,
        f"got {body.get('approval_comment')!r}",
    )

    # 7d. Empty-string comment
    reseed_documents()
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": ""},
    )
    rep.add(
        "body: empty-string comment -> 200 (treated as no comment)",
        r.status_code == 200,
        f"got {r.status_code}",
    )
    body = r.json() if r.status_code == 200 else {}
    # The OpenAPI docstring says empty string is stored as-is; just check
    # the endpoint accepts it without 422.
    rep.add(
        "body: empty-string comment returns string/None (not 422)",
        body.get("approval_comment") in (None, ""),
        f"got {body.get('approval_comment')!r}",
    )

    # 7e. Wrong-type body (non-JSON) returns 422
    reseed_documents()
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": 12345},
    )
    rep.add(
        "body: numeric comment -> 422 (type error)",
        r.status_code == 422,
        f"got {r.status_code} body={r.text[:160]}",
    )

    # ============================================================
    # 8. Audit trail: verified_by_user_id == caller's id
    # ============================================================
    print("\n--- 8. Audit trail ---")
    reseed_documents()
    # What is the verifier's user id?
    me = requests.get(f"{BASE}/auth/me", headers=auth(tok_verifier_t1)).json()
    verifier_id = me.get("id")
    r = requests.post(
        f"{BASE}/verifier/documents/{DOC_T1}/approve",
        headers=auth(tok_verifier_t1),
        json={"comment": "audit me"},
    )
    body = r.json() if r.status_code == 200 else {}
    rep.add(
        "audit: verified_by_user_id == calling verifier",
        body.get("verified_by_user_id") == verifier_id,
        f"got {body.get('verified_by_user_id')!r} expected {verifier_id!r}",
    )
    queue_resp = requests.get(
        f"{BASE}/verifier/documents/pending", headers=auth(tok_verifier_t1)
    )
    queue_ids = [i["id"] for i in queue_resp.json().get("items", [])]
    rep.add(
        "audit: approved doc removed from pending queue",
        DOC_T1 not in queue_ids,
        f"queue_ids={queue_ids}",
    )

    # ============================================================
    # 9. OpenAPI contract: method/path exists
    # ============================================================
    print("\n--- 9. OpenAPI contract surface ---")
    spec = requests.get(f"{BASE}/openapi.json").json()
    path = "/verifier/documents/{document_id}/approve"
    rep.add(
        "contract: path present in OpenAPI",
        path in spec["paths"],
        f"missing {path}",
    )
    op = spec["paths"].get(path, {}).get("post", {})
    rep.add(
        "contract: POST operation present",
        bool(op),
        "",
    )
    rep.add(
        "contract: requires Bearer auth",
        any(isinstance(s.get("HTTPBearer"), list)
            for s in op.get("security", [])),
        "",
    )
    rep.add(
        "contract: 200 + 422 documented",
        "200" in op.get("responses", {}) and "422" in op.get("responses", {}),
        f"responses={list(op.get('responses', {}).keys())}",
    )

    # ============================================================
    # Finalize
    # ============================================================
    print()
    return rep.summary()


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)