#!/usr/bin/env python3
"""One-time script to bootstrap GitHub issue tracking for EduConsult CRM.

Creates labels, milestones, Epic issues, and Task issues, wiring up
traceability: Requirements -> Journeys -> Epics -> Tasks.

Usage: python3 scripts/setup_github_issues.py
Requires: `gh` CLI authenticated, run from repo root.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = "pavanj8/educonsult-crm"
REPO_ROOT = Path(__file__).resolve().parent.parent
DOD_SOURCE = REPO_ROOT / "docs" / "definition-of-done.md"


def load_dod_checklist() -> str:
    """Derives the checklist embedded in every epic/task issue body directly
    from docs/definition-of-done.md, so there is exactly one source of
    truth -- editing that file is all that's needed to change what's shown
    on GitHub too. See docs/adr/0011 (supersedes the hand-synced constant
    from docs/adr/0010).
    """
    text = DOD_SOURCE.read_text()
    items = re.findall(r"^- \[ \] .+$", text, flags=re.MULTILINE)
    if not items:
        raise RuntimeError(
            f"No '- [ ] ...' checklist items found in {DOD_SOURCE} -- has its "
            "format changed? Update this extractor to match."
        )
    return "## Definition of Done\n" + "\n".join(items) + "\n\nFull detail: `docs/definition-of-done.md`.\n"


DOD_CHECKLIST = load_dod_checklist()


def gh_api(method, path, fields=None):
    cmd = ["gh", "api", "-X", method, f"repos/{REPO}/{path}"]
    if fields:
        for k, v in fields.items():
            cmd += ["-f", f"{k}={v}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def ensure_label(name, color, description):
    r = gh_api("POST", "labels", {"name": name, "color": color, "description": description})
    if r.returncode != 0 and "already_exists" not in r.stderr:
        print(f"  ! label {name}: {r.stderr.strip()}", file=sys.stderr)


def ensure_milestone(title, description):
    r = subprocess.run(
        ["gh", "api", f"repos/{REPO}/milestones", "--jq", ".[] | select(.title==\"%s\") | .number" % title],
        capture_output=True, text=True,
    )
    existing = r.stdout.strip()
    if existing:
        return existing
    r = gh_api("POST", "milestones", {"title": title, "description": description})
    if r.returncode != 0:
        print(f"  ! milestone {title}: {r.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(r.stdout)["number"]


AREAS = [
    ("foundation", "d4c5f9"), ("auth", "f9d0c4"), ("tenant", "c5def5"),
    ("branch", "c5def5"), ("staff", "c5def5"), ("billing", "fef2c0"),
    ("student", "bfe5bf"), ("counseling", "bfe5bf"), ("documents", "bfe5bf"),
    ("visa", "bfe5bf"), ("loans", "bfe5bf"), ("pipeline", "bfe5bf"),
    ("analytics", "c2e0c6"), ("notifications", "c2e0c6"), ("i18n", "c2e0c6"),
    ("marketing", "c2e0c6"), ("qa", "e99695"), ("devops", "e99695"),
]

PHASES = {
    "mvp": ("Phase 1 - MVP", "0e8a16", "Core end-to-end student pipeline: register, apply, assign, counsel, verify docs, resolve."),
    "phase-2": ("Phase 2", "fbca04", "Operational completeness: security hardening, branding, meetings, notes, i18n, email."),
    "phase-3": ("Phase 3", "d93f0b", "Monetization & insight: billing, visa, loans, analytics, marketing site."),
}

# Design rule: epics map 1:1 to a single journey wherever possible (a handful
# of cross-cutting/infra epics trace to a requirements section instead, since
# they underpin many journeys at once rather than fulfilling one specific
# journey). This keeps the granularity strictly increasing end-to-end:
# Requirements (11 sections) < Journeys (46) < Epics (53) < Tasks (193+).
EPICS = [
    # --- Cross-cutting / infrastructure epics (not tied to a single journey) ---
    dict(key="E1", title="Project Foundation & Infrastructure", area="foundation", phase="mvp",
         trace="Supports all journeys | Requirements §2 Tech Stack",
         desc="Monorepo scaffold, Docker Compose (Postgres/MinIO/backend/frontend/mailhog), Alembic, CI.",
         tasks=[
             ("Scaffold backend FastAPI app skeleton (folder structure, main.py, health check endpoint)", ""),
             ("Scaffold frontend Vite+React+TS app skeleton (folder structure, routing shell)", ""),
             ("Add Postgres service to Docker Compose with init env vars", ""),
             ("Add MinIO service to Docker Compose with bucket bootstrap", ""),
             ("Add mailhog service to Docker Compose for local email testing", ""),
             ("Configure SQLAlchemy engine/session + base model", ""),
             ("Configure Alembic and generate initial empty migration", ""),
             ("Set up GitHub Actions CI: backend lint (ruff) + test job", ""),
             ("Set up GitHub Actions CI: frontend build + lint job", ""),
         ]),
    dict(key="E2", title="RBAC & Permission Framework", area="foundation", phase="mvp",
         trace="Supports all journeys | Requirements §3 Roles & Hierarchy",
         desc="Role model, tenant/branch scoping, permission-checking dependencies.",
         tasks=[
             ("Backend: Role enum + Permission definitions", ""),
             ("Backend: require_role/require_permission FastAPI dependency", ""),
             ("Backend: tenant-scoping query filter helper", ""),
             ("Backend: branch-scoping query filter helper", ""),
             ("Backend: role hierarchy enforcement rules (who can act on whom)", ""),
             ("Tests: cross-tenant and cross-branch access denial matrix", ""),
         ]),
    dict(key="E3", title="Testing & QA Framework", area="qa", phase="mvp",
         trace="Requirements §2 Testing",
         desc="pytest + Playwright scaffolding, fixtures, seed data for tests.",
         tasks=[
             ("Backend: pytest config + conftest fixtures (DB, client, auth headers)", ""),
             ("Backend: test data factory helpers", ""),
             ("Frontend: Playwright config + base test setup", ""),
             ("Frontend: example E2E smoke test (login flow)", ""),
             ("Seed script: realistic demo data for all roles/tenants", ""),
         ]),
    dict(key="E4", title="Deployment & On-Prem Packaging", area="devops", phase="phase-2",
         trace="Requirements §1 Deployment",
         desc="Production Docker images and on-prem deployment documentation.",
         tasks=[
             ("Backend production Dockerfile", ""),
             ("Frontend production Dockerfile (build + serve)", ""),
             ("docker-compose.prod.yml (env-driven)", ""),
             ("Environment variable reference documentation", ""),
             ("On-prem vs SaaS deployment guide (README)", ""),
         ]),

    # --- Auth & Security (J44-J46) ---
    dict(key="E5", title="Authentication - Login & Session", area="auth", phase="mvp",
         trace="Journey J44",
         desc="JWT-based login, token issuance/refresh for all roles.",
         tasks=[
             ("Backend: User DB model + migration (role, tenant_id, branch_id, email, password_hash)", ""),
             ("Backend: password hashing utility (bcrypt)", ""),
             ("Backend: JWT access + refresh token creation/verification utilities", ""),
             ("Backend: POST /auth/login endpoint", ""),
             ("Backend: POST /auth/refresh endpoint", ""),
             ("Backend: GET /auth/me endpoint", ""),
             ("Frontend: auth API client + auth state store", ""),
             ("Frontend: login page UI", ""),
             ("Frontend: protected route wrapper / redirect-if-unauthenticated", ""),
             ("Tests: login success/failure, token refresh, expired/invalid token handling", ""),
         ]),
    dict(key="E6", title="Password Reset", area="auth", phase="phase-2",
         trace="Journey J45",
         desc="Forgot-password flow via emailed reset link/token.",
         tasks=[
             ("Backend: password reset token model + migration", ""),
             ("Backend: POST /auth/forgot-password endpoint (issues token, sends email)", ""),
             ("Backend: POST /auth/reset-password endpoint (validates token, sets new password)", ""),
             ("Email: password reset email template", ""),
             ("Frontend: forgot-password + reset-password pages", ""),
             ("Tests: reset flow happy path + expired/invalid token", ""),
         ]),
    dict(key="E7", title="Rate Limiting & Auth Security", area="auth", phase="phase-2",
         trace="Journey J46",
         desc="Protect login/signup endpoints from brute force.",
         tasks=[
             ("Backend: rate-limiting middleware/dependency (per-IP + per-account)", ""),
             ("Backend: apply rate limiting to login/signup/forgot-password endpoints", ""),
             ("Backend: strong password policy validator", ""),
             ("Tests: rate limit trips after N failed attempts", ""),
         ]),

    # --- Onboarding & Tenant Management (J1-J8) ---
    dict(key="E8", title="Tenant Creation & Management", area="tenant", phase="mvp",
         trace="Journey J1",
         desc="Super Admin creates and manages tenants (consultancies).",
         tasks=[
             ("Backend: Tenant DB model + migration", ""),
             ("Backend: POST /tenants endpoint (super admin only)", ""),
             ("Backend: GET /tenants list/detail endpoints (super admin only)", ""),
             ("Backend: owner invite email on tenant creation", ""),
             ("Frontend: super admin tenant list + create tenant UI", ""),
             ("Tests: tenant creation, owner invite, super-admin-only access", ""),
         ]),
    dict(key="E9", title="Subscription Plan Assignment", area="billing", phase="phase-3",
         trace="Journey J2",
         desc="Super Admin assigns/updates a tenant's subscription plan tier.",
         tasks=[
             ("Backend: Plan model (Starter/Growth/Enterprise) + limits fields", ""),
             ("Backend: assign/change plan API (super admin)", ""),
             ("Backend: usage limit enforcement checks (branches/staff/students)", ""),
             ("Tests: plan assignment and limit enforcement", ""),
         ]),
    dict(key="E10", title="Tenant Branding & Profile", area="tenant", phase="phase-2",
         trace="Journey J3",
         desc="Logo upload, brand color, currency selection per tenant.",
         tasks=[
             ("Backend: tenant profile fields (logo_url, brand_color, currency) + migration", ""),
             ("Backend: PATCH /tenants/{id}/branding endpoint", ""),
             ("Backend: logo upload endpoint to S3-compatible storage", ""),
             ("Frontend: tenant branding settings page", ""),
             ("Frontend: apply brand color theming across app shell", ""),
         ]),
    dict(key="E11", title="Branch Management", area="branch", phase="mvp",
         trace="Journey J4",
         desc="Owner creates and manages branches under their tenant.",
         tasks=[
             ("Backend: Branch DB model + migration", ""),
             ("Backend: branch CRUD API (create/list/update) scoped to tenant", ""),
             ("Frontend: branch list UI", ""),
             ("Frontend: branch create/edit form", ""),
             ("Tests: branch CRUD + tenant scoping", ""),
         ]),
    dict(key="E12", title="Staff Account Creation", area="staff", phase="mvp",
         trace="Journey J5",
         desc="Owner/branch manager creates a staff account with role + branch assignment.",
         tasks=[
             ("Backend: staff creation API (role + branch assignment, permission-checked)", ""),
             ("Frontend: create/edit staff form", ""),
             ("Tests: branch manager limited to own branch; owner can create for any branch", ""),
         ]),
    dict(key="E13", title="Staff Deactivation & Reactivation", area="staff", phase="mvp",
         trace="Journey J6",
         desc="Owner/branch manager deactivates or reactivates a staff account.",
         tasks=[
             ("Backend: deactivate/reactivate staff API", ""),
             ("Backend: staff list/detail API scoped by branch/tenant", ""),
             ("Frontend: staff list UI with active/inactive status + toggle", ""),
             ("Tests: deactivation/reactivation permission checks", ""),
         ]),
    dict(key="E14", title="Master Data Management", area="tenant", phase="phase-2",
         trace="Journey J7",
         desc="Admin-managed lists of countries, universities, programs used in dropdowns.",
         tasks=[
             ("Backend: Country/University/Program models + migration", ""),
             ("Backend: CRUD API for master data (admin-scoped)", ""),
             ("Frontend: master data management UI (tabs for countries/universities/programs)", ""),
             ("Seed: default country/university/program list", ""),
             ("Tests: master data CRUD", ""),
         ]),
    dict(key="E15", title="Document Checklist Template Management", area="documents", phase="phase-2",
         trace="Journey J8",
         desc="Define required document checklist per pipeline stage/program.",
         tasks=[
             ("Backend: ChecklistItemTemplate model + migration (stage, program, required flag)", ""),
             ("Backend: CRUD API for checklist templates", ""),
             ("Frontend: checklist template builder UI", ""),
             ("Tests: checklist template CRUD and stage/program association", ""),
         ]),

    # --- Student Registration (J9-J13) ---
    dict(key="E16", title="Student Self-Registration", area="student", phase="mvp",
         trace="Journey J9",
         desc="Public student signup with profile fields and structured dropdowns.",
         tasks=[
             ("Backend: student profile fields on User/Student model + migration", ""),
             ("Backend: POST /auth/register-student endpoint", ""),
             ("Backend: duplicate-email validation", ""),
             ("Frontend: registration form UI", ""),
             ("Frontend: structured country/university/program dropdown components", ""),
             ("Tests: student signup validation and duplicate handling", ""),
         ]),
    dict(key="E17", title="Staff-Created Student Records", area="student", phase="phase-2",
         trace="Journey J10",
         desc="Receptionist creates a student record for walk-ins.",
         tasks=[
             ("Backend: POST /students endpoint (receptionist scope)", ""),
             ("Frontend: receptionist intake form", ""),
             ("Tests: receptionist-created student record permissions", ""),
         ]),
    dict(key="E18", title="Student Application Creation", area="student", phase="mvp",
         trace="Journey J11",
         desc="Student creates one or more university/program applications.",
         tasks=[
             ("Backend: Application DB model + migration (student_id, university, program, stage)", ""),
             ("Backend: POST /applications endpoint", ""),
             ("Backend: GET /applications list endpoint (per student)", ""),
             ("Frontend: 'new application' form on student dashboard", ""),
             ("Frontend: applications list view on student dashboard", ""),
             ("Tests: multiple applications per student, independent stage tracking", ""),
         ]),
    dict(key="E19", title="Counselor Auto-Assignment", area="counseling", phase="mvp",
         trace="Journey J12",
         desc="Round-robin counselor assignment within a branch on new application.",
         tasks=[
             ("Backend: round-robin assignment service (per branch)", ""),
             ("Backend: trigger assignment on application creation", ""),
             ("Tests: even distribution across branch counselors", ""),
         ]),
    dict(key="E20", title="Manual Counselor Reassignment", area="counseling", phase="phase-2",
         trace="Journey J13",
         desc="Branch manager/receptionist can manually reassign a counselor.",
         tasks=[
             ("Backend: PATCH /applications/{id}/counselor endpoint with permission checks", ""),
             ("Frontend: reassignment control on application detail view", ""),
             ("Tests: reassignment permission checks", ""),
         ]),

    # --- Counseling (J14-J18) ---
    dict(key="E21", title="Counselor Dashboard & Queue", area="counseling", phase="mvp",
         trace="Journey J14",
         desc="Counselor sees assigned students/applications with filters.",
         tasks=[
             ("Backend: GET /applications assigned-to-me endpoint with filters", ""),
             ("Frontend: counselor dashboard queue view", ""),
             ("Tests: queue filtering and scoping to assigned counselor", ""),
         ]),
    dict(key="E22", title="Meeting Scheduling (Counselor)", area="counseling", phase="phase-2",
         trace="Journey J15",
         desc="Counselor schedules a meeting with a student.",
         tasks=[
             ("Backend: Meeting DB model + migration", ""),
             ("Backend: schedule/list/update meeting API", ""),
             ("Frontend: scheduling UI (counselor side)", ""),
         ]),
    dict(key="E23", title="Student Meeting Visibility & Notification", area="counseling", phase="phase-2",
         trace="Journey J16",
         desc="Student sees upcoming meetings and is notified when one is scheduled.",
         tasks=[
             ("Frontend: upcoming meetings widget (student dashboard)", ""),
             ("Wire meeting creation into notification trigger", ""),
         ]),
    dict(key="E24", title="Internal Counseling Notes", area="counseling", phase="phase-2",
         trace="Journey J17",
         desc="Staff-only notes thread per student, hidden from student.",
         tasks=[
             ("Backend: Note DB model + migration (staff-only visibility)", ""),
             ("Backend: CRUD API for notes", ""),
             ("Frontend: notes thread UI on application detail view", ""),
         ]),
    dict(key="E25", title="Application Stage Progression Engine", area="pipeline", phase="mvp",
         trace="Journey J18",
         desc="Advance applications through pipeline stages with history logging.",
         tasks=[
             ("Backend: stage enum + valid-transition rule table", ""),
             ("Backend: StageHistory model + migration", ""),
             ("Backend: advance-stage API with history logging", ""),
             ("Frontend: stage timeline component", ""),
             ("Tests: invalid transitions rejected, history recorded correctly", ""),
         ]),

    # --- Documents (J19-J25) ---
    dict(key="E26", title="Student Document Checklist View", area="documents", phase="mvp",
         trace="Journey J19",
         desc="Student views the document checklist for their application.",
         tasks=[
             ("Backend: checklist-for-application retrieval API (merges template + upload status)", ""),
             ("Frontend: checklist view component", ""),
         ]),
    dict(key="E27", title="Student Document Upload", area="documents", phase="mvp",
         trace="Journey J20",
         desc="Student uploads a document against a checklist item.",
         tasks=[
             ("Backend: StudentDocument model + migration", ""),
             ("Backend: file upload API to S3-compatible storage", ""),
             ("Backend: file type/size validation (10MB, PDF/JPG/PNG/DOCX)", ""),
             ("Frontend: upload UI per checklist item", ""),
             ("Tests: upload validation and checklist completeness calculation", ""),
         ]),
    dict(key="E28", title="Document Verifier Queue", area="documents", phase="mvp",
         trace="Journey J21",
         desc="Document Verifier reviews the pending-documents queue.",
         tasks=[
             ("Backend: verifier queue API (pending documents)", ""),
             ("Frontend: document verifier dashboard (queue view)", ""),
         ]),
    dict(key="E29", title="Document Approval", area="documents", phase="mvp",
         trace="Journey J22",
         desc="Document Verifier approves a document.",
         tasks=[
             ("Backend: approve-document API with comments", ""),
             ("Frontend: approve action UI", ""),
             ("Tests: approve flow and permission checks", ""),
         ]),
    dict(key="E30", title="Document Rejection with Comments", area="documents", phase="mvp",
         trace="Journey J23",
         desc="Document Verifier rejects a document with comments.",
         tasks=[
             ("Backend: reject-document API with comments", ""),
             ("Frontend: reject action UI with comment input", ""),
             ("Tests: reject flow and permission checks", ""),
         ]),
    dict(key="E31", title="Document Re-upload Flow", area="documents", phase="phase-2",
         trace="Journey J24",
         desc="Student re-uploads a rejected document.",
         tasks=[
             ("Backend: re-upload/versioning support for rejected documents", ""),
             ("Frontend: re-upload flow UI for rejected items", ""),
         ]),
    dict(key="E32", title="Document Review Outcome Notification", area="documents", phase="phase-2",
         trace="Journey J25",
         desc="Student receives notification of document review outcome.",
         tasks=[
             ("Wire document review outcome into notification trigger", ""),
             ("Tests: notification generated on approve/reject", ""),
         ]),

    # --- Visa Processing (J26-J28) ---
    dict(key="E33", title="Visa Queue View", area="visa", phase="phase-3",
         trace="Journey J26",
         desc="Visa Processor views applications at the visa stage.",
         tasks=[
             ("Backend: visa-stage applications queue API", ""),
             ("Frontend: visa processor dashboard (queue view)", ""),
         ]),
    dict(key="E34", title="Visa Type & Interview Recording", area="visa", phase="phase-3",
         trace="Journey J27",
         desc="Visa Processor records visa type & embassy interview date.",
         tasks=[
             ("Backend: VisaDetail model + migration (type, interview date)", ""),
             ("Frontend: visa detail update form (type + interview date)", ""),
         ]),
    dict(key="E35", title="Visa Outcome Update", area="visa", phase="phase-3",
         trace="Journey J28",
         desc="Visa Processor updates visa outcome/status.",
         tasks=[
             ("Backend: visa outcome update API", ""),
             ("Frontend: visa outcome update UI", ""),
             ("Tests: visa stage transitions and outcome recording", ""),
         ]),

    # --- Loans (J29-J30) ---
    dict(key="E36", title="Student Loan Opt-in", area="loans", phase="phase-3",
         trace="Journey J29",
         desc="Student opts into loan tracking on an application.",
         tasks=[
             ("Backend: loan opt-in field on Application model + migration", ""),
             ("Frontend: loan opt-in UI (student application flow)", ""),
         ]),
    dict(key="E37", title="Staff Loan Status Update", area="loans", phase="phase-3",
         trace="Journey J30",
         desc="Staff records/updates loan status, lender, amount.",
         tasks=[
             ("Backend: loan lender/amount/status fields + update-loan-status API", ""),
             ("Frontend: loan tracking UI (staff status update)", ""),
             ("Tests: loan field updates and permission checks", ""),
         ]),

    # --- Application Resolution (J31-J33) ---
    dict(key="E38", title="Mark Application Enrolled", area="pipeline", phase="mvp",
         trace="Journey J31",
         desc="Staff marks an application Enrolled.",
         tasks=[
             ("Backend: mark-enrolled transition API with details capture", ""),
             ("Frontend: 'Mark Enrolled' action UI", ""),
         ]),
    dict(key="E39", title="Mark Application Rejected", area="pipeline", phase="mvp",
         trace="Journey J32",
         desc="Staff marks an application Rejected (with reason).",
         tasks=[
             ("Backend: mark-rejected transition API with reason capture", ""),
             ("Frontend: 'Mark Rejected' action UI with reason field", ""),
         ]),
    dict(key="E40", title="Mark Application Withdrawn", area="pipeline", phase="mvp",
         trace="Journey J33",
         desc="Staff marks an application Withdrawn (with reason).",
         tasks=[
             ("Backend: mark-withdrawn transition API with reason capture", ""),
             ("Frontend: 'Mark Withdrawn' action UI with reason field", ""),
             ("Tests: terminal states (Enrolled/Rejected/Withdrawn) are final", ""),
         ]),

    # --- Analytics & Reporting (J34-J37) ---
    dict(key="E41", title="Branch Manager Analytics Dashboard", area="analytics", phase="phase-3",
         trace="Journey J34",
         desc="Branch Manager views branch dashboard with date-range filter.",
         tasks=[
             ("Backend: registrations-over-time aggregation query + API", ""),
             ("Backend: conversion funnel by stage aggregation query + API", ""),
             ("Frontend: branch manager dashboard charts with date-range filter", ""),
         ]),
    dict(key="E42", title="Owner Cross-Branch Dashboard", area="analytics", phase="phase-3",
         trace="Journey J35",
         desc="Consultancy Owner views cross-branch comparison dashboard.",
         tasks=[
             ("Backend: branch comparison aggregation query + API", ""),
             ("Frontend: owner cross-branch dashboard view", ""),
         ]),
    dict(key="E43", title="Super Admin Platform-Wide Stats", area="analytics", phase="phase-3",
         trace="Journey J36",
         desc="Super Admin views platform-wide tenant stats.",
         tasks=[
             ("Backend: platform-wide tenant stats aggregation query + API", ""),
             ("Frontend: super admin stats dashboard view", ""),
         ]),
    dict(key="E44", title="Report Export (CSV/Excel)", area="analytics", phase="phase-3",
         trace="Journey J37",
         desc="Admin role exports a report to CSV/Excel.",
         tasks=[
             ("Backend: CSV/Excel export endpoint for student lists", ""),
             ("Backend: CSV/Excel export endpoint for analytics views", ""),
             ("Frontend: export button integration on relevant views", ""),
         ]),

    # --- Billing (J38-J40) ---
    dict(key="E45", title="Owner Plan & Usage View", area="billing", phase="phase-3",
         trace="Journey J38",
         desc="Consultancy Owner views current plan & usage.",
         tasks=[
             ("Backend: current plan & usage summary API", ""),
             ("Frontend: billing/usage page", ""),
         ]),
    dict(key="E46", title="Plan Upgrade/Downgrade Checkout (Razorpay)", area="billing", phase="phase-3",
         trace="Journey J39",
         desc="Consultancy Owner upgrades/downgrades plan via Razorpay checkout.",
         tasks=[
             ("Backend: Razorpay SDK integration + config", ""),
             ("Backend: create order API for plan upgrade", ""),
             ("Backend: Razorpay webhook handler (payment confirmation)", ""),
             ("Backend: apply plan change on confirmed payment", ""),
             ("Frontend: Razorpay checkout integration", ""),
         ]),
    dict(key="E47", title="Super Admin Billing Status Overview", area="billing", phase="phase-3",
         trace="Journey J40",
         desc="Super Admin views all tenants' billing/subscription status.",
         tasks=[
             ("Backend: list endpoint for all tenants' plan/billing status", ""),
             ("Frontend: super admin view of all tenants' plans/billing status", ""),
         ]),

    # --- Notifications (J41-J43) ---
    dict(key="E48", title="In-App Notification Generation", area="notifications", phase="mvp",
         trace="Journey J41",
         desc="User receives an in-app notification on a relevant event.",
         tasks=[
             ("Backend: Notification model + migration", ""),
             ("Backend: notification-creation service + hooks into key events", ""),
             ("Tests: notification generated on key events", ""),
         ]),
    dict(key="E49", title="Email Notifications", area="notifications", phase="phase-2",
         trace="Journey J42",
         desc="Email delivery for key events, pluggable for future SMS/WhatsApp.",
         tasks=[
             ("Backend: email service abstraction (SMTP client wrapper)", ""),
             ("Backend: email templates for key events (stage change, doc review, meeting, invite)", ""),
             ("Backend: wire email sending into existing notification triggers", ""),
             ("Tests: email sending triggered correctly (mocked SMTP)", ""),
         ]),
    dict(key="E50", title="Notification Center UI", area="notifications", phase="mvp",
         trace="Journey J43",
         desc="User views notification center and marks items read.",
         tasks=[
             ("Backend: list/mark-read notification API", ""),
             ("Frontend: notification bell + notification center UI", ""),
         ]),

    # --- Remaining cross-cutting epics ---
    dict(key="E51", title="Internationalization (i18n)", area="i18n", phase="phase-2",
         trace="Requirements §1 Deployment/i18n",
         desc="i18n framework with English, Hindi, Telugu translations.",
         tasks=[
             ("Frontend: set up i18next framework + language switcher", ""),
             ("Frontend: extract existing UI strings into translation keys", ""),
             ("Add Hindi and Telugu translation files", ""),
         ]),
    dict(key="E52", title="Currency Display Configuration", area="i18n", phase="phase-2",
         trace="Requirements §1 Currency",
         desc="Per-tenant display currency for loan/fee amounts.",
         tasks=[
             ("Backend: currency field on tenant + migration", ""),
             ("Backend/Frontend: currency formatting utility", ""),
             ("Frontend: currency-aware amount display components", ""),
         ]),
    dict(key="E53", title="Marketing Landing Page", area="marketing", phase="phase-3",
         trace="Requirements §10 Marketing Site",
         desc="Public landing page separate from the app login.",
         tasks=[
             ("Design landing page layout (hero, features, CTA sections)", ""),
             ("Build landing page route/component", ""),
             ("Wire CTA buttons to login/signup", ""),
         ]),
]

# Planning Agent integration (docs/adr/0030): when docs/plan.json exists (produced
# by agents/planner_agent.py from requirements.md), it OVERRIDES the inline EPICS
# above, so a generated plan drives issue creation without editing this file. This
# is what makes the harness reusable: a new project supplies requirements.md, the
# planner generates plan.json, and this script creates the whole backlog.
_PLAN = REPO_ROOT / "docs" / "plan.json"
if _PLAN.exists():
    _plan = json.loads(_PLAN.read_text())
    EPICS = [
        dict(
            key=e["key"],
            title=e.get("title", ""),
            area=e.get("area", "general"),
            phase=e.get("phase", "mvp"),
            trace=f"Journey {e.get('journey_id', '')}",
            desc=e.get("desc", ""),
            tasks=[tuple(t) for t in e.get("tasks", [])],
        )
        for e in _plan.get("epics", [])
    ]
    print(f"[setup] using generated plan docs/plan.json ({len(EPICS)} epics)")


def main():
    print("Creating labels...")
    ensure_label("epic", "5319e7", "High-level feature grouping tied to one or more journeys")
    ensure_label("task", "1d76db", "Implementable unit of work under an epic")
    for area, color in AREAS:
        ensure_label(f"area:{area}", color, f"Area: {area}")
    for phase, (title, color, desc) in PHASES.items():
        ensure_label(f"phase:{phase}", color, title)

    print("Creating milestones...")
    milestone_numbers = {}
    for phase, (title, color, desc) in PHASES.items():
        num = ensure_milestone(title, desc)
        milestone_numbers[phase] = num

    print("Creating epic issues...")
    epic_issue_numbers = {}
    for epic in EPICS:
        labels = f"epic,area:{epic['area']},phase:{epic['phase']}"
        body = (
            f"**Traceability:** {epic['trace']}\n\n"
            f"**Description:** {epic['desc']}\n\n"
            f"_Tasks will be linked below as they are created._\n\n"
            f"{DOD_CHECKLIST}"
        )
        cmd = [
            "gh", "issue", "create", "-R", REPO,
            "--title", f"[EPIC] {epic['key']}: {epic['title']}",
            "--body", body,
            "--label", labels,
        ]
        if milestone_numbers.get(epic["phase"]):
            title_map = {k: v[0] for k, v in PHASES.items()}
            cmd += ["--milestone", title_map[epic["phase"]]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ! failed epic {epic['key']}: {r.stderr.strip()}", file=sys.stderr)
            continue
        url = r.stdout.strip()
        number = int(url.rstrip("/").split("/")[-1])
        epic_issue_numbers[epic["key"]] = number
        print(f"  {epic['key']} -> #{number}")

    print("Creating task issues...")
    epic_task_numbers = {k: [] for k in epic_issue_numbers}
    for epic in EPICS:
        epic_num = epic_issue_numbers.get(epic["key"])
        if not epic_num:
            continue
        for task_title, task_desc in epic["tasks"]:
            labels = f"task,area:{epic['area']},phase:{epic['phase']}"
            body = (
                f"Part of #{epic_num} ({epic['key']}: {epic['title']})\n\n"
                f"{task_desc}\n\n{DOD_CHECKLIST}"
            ).strip()
            cmd = [
                "gh", "issue", "create", "-R", REPO,
                "--title", f"[{epic['key']}] {task_title}",
                "--body", body,
                "--label", labels,
            ]
            title_map = {k: v[0] for k, v in PHASES.items()}
            if milestone_numbers.get(epic["phase"]):
                cmd += ["--milestone", title_map[epic["phase"]]]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  ! failed task '{task_title}': {r.stderr.strip()}", file=sys.stderr)
                continue
            url = r.stdout.strip()
            number = int(url.rstrip("/").split("/")[-1])
            epic_task_numbers[epic["key"]].append(number)

    print("Updating epic bodies with task checklists...")
    for epic in EPICS:
        epic_num = epic_issue_numbers.get(epic["key"])
        if not epic_num:
            continue
        task_nums = epic_task_numbers.get(epic["key"], [])
        checklist = "\n".join(f"- [ ] #{n}" for n in task_nums)
        body = (
            f"**Traceability:** {epic['trace']}\n\n"
            f"**Description:** {epic['desc']}\n\n"
            f"## Tasks\n{checklist}\n\n"
            f"An epic is Done only once every task above is Done.\n\n"
            f"{DOD_CHECKLIST}"
        )
        r = subprocess.run(
            ["gh", "issue", "edit", str(epic_num), "-R", REPO, "--body", body],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"  ! failed updating epic #{epic_num}: {r.stderr.strip()}", file=sys.stderr)

    print("Done.")
    print(json.dumps({"epics": epic_issue_numbers, "tasks": epic_task_numbers}, indent=2))


if __name__ == "__main__":
    main()
