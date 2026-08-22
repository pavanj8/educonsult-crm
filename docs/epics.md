# EduConsult CRM — Epics

Status: **Approved**. Granularity increases strictly at each level: **Requirements (11 sections) → Journeys (46) → Epics (53) → Tasks (193)**. Nearly every epic traces to exactly one journey in [`journeys.md`](./journeys.md); a handful of cross-cutting infrastructure epics trace directly to a requirements section instead, since they underpin many journeys rather than fulfilling one. Each epic is broken into small, atomic Task issues in GitHub (one model / one endpoint / one UI component / one test suite per task). GitHub is the source of truth for live status; this document is the traceable planning record generated from `scripts/setup_github_issues.py`.

Repo: [`pavanj8/educonsult-crm`](https://github.com/pavanj8/educonsult-crm)
Epics are **not** GitHub issues — each task carries its epic in its `[E<n>]` title tag, and this document is the human-readable epic record ([ADR-0032](./adr/0032-epics-are-title-tags-not-issues.md)).
Labels: `task` + `area:*` + `phase:mvp|phase-2|phase-3`
Milestones: Phase 1 - MVP, Phase 2, Phase 3

**Totals**: 11 requirement sections → 46 journeys → 53 epics → 193 tasks

## Phase 1 — MVP (core end-to-end student pipeline)

| Key | Epic | Area | # Tasks | Traces to |
|---|---|---|---|---|
| E1 | Project Foundation & Infrastructure | foundation | 9 | Supports all journeys · Requirements §2 Tech Stack |
| E2 | RBAC & Permission Framework | foundation | 6 | Supports all journeys · Requirements §3 Roles & Hierarchy |
| E3 | Testing & QA Framework | qa | 5 | Requirements §2 Testing |
| E5 | Authentication - Login & Session | auth | 10 | Journey J44 |
| E8 | Tenant Creation & Management | tenant | 6 | Journey J1 |
| E11 | Branch Management | branch | 5 | Journey J4 |
| E12 | Staff Account Creation | staff | 3 | Journey J5 |
| E13 | Staff Deactivation & Reactivation | staff | 4 | Journey J6 |
| E16 | Student Self-Registration | student | 6 | Journey J9 |
| E18 | Student Application Creation | student | 6 | Journey J11 |
| E19 | Counselor Auto-Assignment | counseling | 3 | Journey J12 |
| E21 | Counselor Dashboard & Queue | counseling | 3 | Journey J14 |
| E25 | Application Stage Progression Engine | pipeline | 5 | Journey J18 |
| E26 | Student Document Checklist View | documents | 2 | Journey J19 |
| E27 | Student Document Upload | documents | 5 | Journey J20 |
| E28 | Document Verifier Queue | documents | 2 | Journey J21 |
| E29 | Document Approval | documents | 3 | Journey J22 |
| E30 | Document Rejection with Comments | documents | 3 | Journey J23 |
| E38 | Mark Application Enrolled | pipeline | 2 | Journey J31 |
| E39 | Mark Application Rejected | pipeline | 2 | Journey J32 |
| E40 | Mark Application Withdrawn | pipeline | 3 | Journey J33 |
| E48 | In-App Notification Generation | notifications | 3 | Journey J41 |
| E50 | Notification Center UI | notifications | 2 | Journey J43 |

## Phase 2 — Operational completeness

| Key | Epic | Area | # Tasks | Traces to |
|---|---|---|---|---|
| E4 | Deployment & On-Prem Packaging | devops | 5 | Requirements §1 Deployment |
| E6 | Password Reset | auth | 6 | Journey J45 |
| E7 | Rate Limiting & Auth Security | auth | 4 | Journey J46 |
| E10 | Tenant Branding & Profile | tenant | 5 | Journey J3 |
| E14 | Master Data Management | tenant | 5 | Journey J7 |
| E15 | Document Checklist Template Management | documents | 4 | Journey J8 |
| E17 | Staff-Created Student Records | student | 3 | Journey J10 |
| E20 | Manual Counselor Reassignment | counseling | 3 | Journey J13 |
| E22 | Meeting Scheduling (Counselor) | counseling | 3 | Journey J15 |
| E23 | Student Meeting Visibility & Notification | counseling | 2 | Journey J16 |
| E24 | Internal Counseling Notes | counseling | 3 | Journey J17 |
| E31 | Document Re-upload Flow | documents | 2 | Journey J24 |
| E32 | Document Review Outcome Notification | documents | 2 | Journey J25 |
| E49 | Email Notifications | notifications | 4 | Journey J42 |
| E51 | Internationalization (i18n) | i18n | 3 | Requirements §1 Deployment/i18n |
| E52 | Currency Display Configuration | i18n | 3 | Requirements §1 Currency |

## Phase 3 — Monetization & insight

| Key | Epic | Area | # Tasks | Traces to |
|---|---|---|---|---|
| E9 | Subscription Plan Assignment | billing | 4 | Journey J2 |
| E33 | Visa Queue View | visa | 2 | Journey J26 |
| E34 | Visa Type & Interview Recording | visa | 2 | Journey J27 |
| E35 | Visa Outcome Update | visa | 3 | Journey J28 |
| E36 | Student Loan Opt-in | loans | 2 | Journey J29 |
| E37 | Staff Loan Status Update | loans | 3 | Journey J30 |
| E41 | Branch Manager Analytics Dashboard | analytics | 3 | Journey J34 |
| E42 | Owner Cross-Branch Dashboard | analytics | 2 | Journey J35 |
| E43 | Super Admin Platform-Wide Stats | analytics | 2 | Journey J36 |
| E44 | Report Export (CSV/Excel) | analytics | 3 | Journey J37 |
| E45 | Owner Plan & Usage View | billing | 2 | Journey J38 |
| E46 | Plan Upgrade/Downgrade Checkout (Razorpay) | billing | 5 | Journey J39 |
| E47 | Super Admin Billing Status Overview | billing | 2 | Journey J40 |
| E53 | Marketing Landing Page | marketing | 3 | Requirements §10 Marketing Site |

> **Dependency note**: E14 (Master Data Management) and E15 (Document Checklist Template Management) are labeled Phase 2, but E16/E18 (self-registration, application creation) and E26/E27 (document checklist view/upload) functionally depend on them (structured dropdowns, checklist definitions). Recommend pulling minimal slices of E14/E15 forward into Phase 1 execution order even though they remain labeled phase-2.

---

## Epic Details & Tasks

### E1: Project Foundation & Infrastructure
**Traces to**: Supports all journeys · Requirements §2 Tech Stack  
**Phase**: mvp  
Monorepo scaffold, Docker Compose (Postgres/MinIO/backend/frontend/mailhog), Alembic, CI.

- Scaffold backend FastAPI app skeleton (folder structure, main.py, health check endpoint)
- Scaffold frontend Vite+React+TS app skeleton (folder structure, routing shell)
- Add Postgres service to Docker Compose with init env vars
- Add MinIO service to Docker Compose with bucket bootstrap
- Add mailhog service to Docker Compose for local email testing
- Configure SQLAlchemy engine/session + base model
- Configure Alembic and generate initial empty migration
- Set up GitHub Actions CI: backend lint (ruff) + test job
- Set up GitHub Actions CI: frontend build + lint job

### E2: RBAC & Permission Framework
**Traces to**: Supports all journeys · Requirements §3 Roles & Hierarchy  
**Phase**: mvp  
Role model, tenant/branch scoping, permission-checking dependencies.

- Backend: Role enum + Permission definitions
- Backend: require_role/require_permission FastAPI dependency
- Backend: tenant-scoping query filter helper
- Backend: branch-scoping query filter helper
- Backend: role hierarchy enforcement rules (who can act on whom)
- Tests: cross-tenant and cross-branch access denial matrix

### E3: Testing & QA Framework
**Traces to**: Requirements §2 Testing  
**Phase**: mvp  
pytest + Playwright scaffolding, fixtures, seed data for tests.

- Backend: pytest config + conftest fixtures (DB, client, auth headers)
- Backend: test data factory helpers
- Frontend: Playwright config + base test setup
- Frontend: example E2E smoke test (login flow)
- Seed script: realistic demo data for all roles/tenants

### E4: Deployment & On-Prem Packaging
**Traces to**: Requirements §1 Deployment  
**Phase**: phase-2  
Production Docker images and on-prem deployment documentation.

- Backend production Dockerfile
- Frontend production Dockerfile (build + serve)
- docker-compose.prod.yml (env-driven)
- Environment variable reference documentation
- On-prem vs SaaS deployment guide (README)

### E5: Authentication - Login & Session
**Traces to**: Journey J44  
**Phase**: mvp  
JWT-based login, token issuance/refresh for all roles.

- Backend: User DB model + migration (role, tenant_id, branch_id, email, password_hash)
- Backend: password hashing utility (bcrypt)
- Backend: JWT access + refresh token creation/verification utilities
- Backend: POST /auth/login endpoint
- Backend: POST /auth/refresh endpoint
- Backend: GET /auth/me endpoint
- Frontend: auth API client + auth state store
- Frontend: login page UI
- Frontend: protected route wrapper / redirect-if-unauthenticated
- Tests: login success/failure, token refresh, expired/invalid token handling

### E6: Password Reset
**Traces to**: Journey J45  
**Phase**: phase-2  
Forgot-password flow via emailed reset link/token.

- Backend: password reset token model + migration
- Backend: POST /auth/forgot-password endpoint (issues token, sends email)
- Backend: POST /auth/reset-password endpoint (validates token, sets new password)
- Email: password reset email template
- Frontend: forgot-password + reset-password pages
- Tests: reset flow happy path + expired/invalid token

### E7: Rate Limiting & Auth Security
**Traces to**: Journey J46  
**Phase**: phase-2  
Protect login/signup endpoints from brute force.

- Backend: rate-limiting middleware/dependency (per-IP + per-account)
- Backend: apply rate limiting to login/signup/forgot-password endpoints
- Backend: strong password policy validator
- Tests: rate limit trips after N failed attempts

### E8: Tenant Creation & Management
**Traces to**: Journey J1  
**Phase**: mvp  
Super Admin creates and manages tenants (consultancies).

- Backend: Tenant DB model + migration
- Backend: POST /tenants endpoint (super admin only)
- Backend: GET /tenants list/detail endpoints (super admin only)
- Backend: owner invite email on tenant creation
- Frontend: super admin tenant list + create tenant UI
- Tests: tenant creation, owner invite, super-admin-only access

### E9: Subscription Plan Assignment
**Traces to**: Journey J2  
**Phase**: phase-3  
Super Admin assigns/updates a tenant's subscription plan tier.

- Backend: Plan model (Starter/Growth/Enterprise) + limits fields
- Backend: assign/change plan API (super admin)
- Backend: usage limit enforcement checks (branches/staff/students)
- Tests: plan assignment and limit enforcement

### E10: Tenant Branding & Profile
**Traces to**: Journey J3  
**Phase**: phase-2  
Logo upload, brand color, currency selection per tenant.

- Backend: tenant profile fields (logo_url, brand_color, currency) + migration
- Backend: PATCH /tenants/{id}/branding endpoint
- Backend: logo upload endpoint to S3-compatible storage
- Frontend: tenant branding settings page
- Frontend: apply brand color theming across app shell

### E11: Branch Management
**Traces to**: Journey J4  
**Phase**: mvp  
Owner creates and manages branches under their tenant.

- Backend: Branch DB model + migration
- Backend: branch CRUD API (create/list/update) scoped to tenant
- Frontend: branch list UI
- Frontend: branch create/edit form
- Tests: branch CRUD + tenant scoping

### E12: Staff Account Creation
**Traces to**: Journey J5  
**Phase**: mvp  
Owner/branch manager creates a staff account with role + branch assignment.

- Backend: staff creation API (role + branch assignment, permission-checked)
- Frontend: create/edit staff form
- Tests: branch manager limited to own branch; owner can create for any branch

### E13: Staff Deactivation & Reactivation
**Traces to**: Journey J6  
**Phase**: mvp  
Owner/branch manager deactivates or reactivates a staff account.

- Backend: deactivate/reactivate staff API
- Backend: staff list/detail API scoped by branch/tenant
- Frontend: staff list UI with active/inactive status + toggle
- Tests: deactivation/reactivation permission checks

### E14: Master Data Management
**Traces to**: Journey J7  
**Phase**: phase-2  
Admin-managed lists of countries, universities, programs used in dropdowns.

- Backend: Country/University/Program models + migration
- Backend: CRUD API for master data (admin-scoped)
- Frontend: master data management UI (tabs for countries/universities/programs)
- Seed: default country/university/program list
- Tests: master data CRUD

### E15: Document Checklist Template Management
**Traces to**: Journey J8  
**Phase**: phase-2  
Define required document checklist per pipeline stage/program.

- Backend: ChecklistItemTemplate model + migration (stage, program, required flag)
- Backend: CRUD API for checklist templates
- Frontend: checklist template builder UI
- Tests: checklist template CRUD and stage/program association

### E16: Student Self-Registration
**Traces to**: Journey J9  
**Phase**: mvp  
Public student signup with profile fields and structured dropdowns.

- Backend: student profile fields on User/Student model + migration
- Backend: POST /auth/register-student endpoint
- Backend: duplicate-email validation
- Frontend: registration form UI
- Frontend: structured country/university/program dropdown components
- Tests: student signup validation and duplicate handling

### E17: Staff-Created Student Records
**Traces to**: Journey J10  
**Phase**: phase-2  
Receptionist creates a student record for walk-ins.

- Backend: POST /students endpoint (receptionist scope)
- Frontend: receptionist intake form
- Tests: receptionist-created student record permissions

### E18: Student Application Creation
**Traces to**: Journey J11  
**Phase**: mvp  
Student creates one or more university/program applications.

- Backend: Application DB model + migration (student_id, university, program, stage)
- Backend: POST /applications endpoint
- Backend: GET /applications list endpoint (per student)
- Frontend: 'new application' form on student dashboard
- Frontend: applications list view on student dashboard
- Tests: multiple applications per student, independent stage tracking

### E19: Counselor Auto-Assignment
**Traces to**: Journey J12  
**Phase**: mvp  
Round-robin counselor assignment within a branch on new application.

- Backend: round-robin assignment service (per branch)
- Backend: trigger assignment on application creation
- Tests: even distribution across branch counselors

### E20: Manual Counselor Reassignment
**Traces to**: Journey J13  
**Phase**: phase-2  
Branch manager/receptionist can manually reassign a counselor.

- Backend: PATCH /applications/{id}/counselor endpoint with permission checks
- Frontend: reassignment control on application detail view
- Tests: reassignment permission checks

### E21: Counselor Dashboard & Queue
**Traces to**: Journey J14  
**Phase**: mvp  
Counselor sees assigned students/applications with filters.

- Backend: GET /applications assigned-to-me endpoint with filters
- Frontend: counselor dashboard queue view
- Tests: queue filtering and scoping to assigned counselor

### E22: Meeting Scheduling (Counselor)
**Traces to**: Journey J15  
**Phase**: phase-2  
Counselor schedules a meeting with a student.

- Backend: Meeting DB model + migration
- Backend: schedule/list/update meeting API
- Frontend: scheduling UI (counselor side)

### E23: Student Meeting Visibility & Notification
**Traces to**: Journey J16  
**Phase**: phase-2  
Student sees upcoming meetings and is notified when one is scheduled.

- Frontend: upcoming meetings widget (student dashboard)
- Wire meeting creation into notification trigger

### E24: Internal Counseling Notes
**Traces to**: Journey J17  
**Phase**: phase-2  
Staff-only notes thread per student, hidden from student.

- Backend: Note DB model + migration (staff-only visibility)
- Backend: CRUD API for notes
- Frontend: notes thread UI on application detail view

### E25: Application Stage Progression Engine
**Traces to**: Journey J18  
**Phase**: mvp  
Advance applications through pipeline stages with history logging.

- Backend: stage enum + valid-transition rule table
- Backend: StageHistory model + migration
- Backend: advance-stage API with history logging
- Frontend: stage timeline component
- Tests: invalid transitions rejected, history recorded correctly

### E26: Student Document Checklist View
**Traces to**: Journey J19  
**Phase**: mvp  
Student views the document checklist for their application.

- Backend: checklist-for-application retrieval API (merges template + upload status)
- Frontend: checklist view component

### E27: Student Document Upload
**Traces to**: Journey J20  
**Phase**: mvp  
Student uploads a document against a checklist item.

- Backend: StudentDocument model + migration
- Backend: file upload API to S3-compatible storage
- Backend: file type/size validation (10MB, PDF/JPG/PNG/DOCX)
- Frontend: upload UI per checklist item
- Tests: upload validation and checklist completeness calculation

### E28: Document Verifier Queue
**Traces to**: Journey J21  
**Phase**: mvp  
Document Verifier reviews the pending-documents queue.

- Backend: verifier queue API (pending documents)
- Frontend: document verifier dashboard (queue view)

### E29: Document Approval
**Traces to**: Journey J22  
**Phase**: mvp  
Document Verifier approves a document.

- Backend: approve-document API with comments
- Frontend: approve action UI
- Tests: approve flow and permission checks

### E30: Document Rejection with Comments
**Traces to**: Journey J23  
**Phase**: mvp  
Document Verifier rejects a document with comments.

- Backend: reject-document API with comments
- Frontend: reject action UI with comment input
- Tests: reject flow and permission checks

### E31: Document Re-upload Flow
**Traces to**: Journey J24  
**Phase**: phase-2  
Student re-uploads a rejected document.

- Backend: re-upload/versioning support for rejected documents
- Frontend: re-upload flow UI for rejected items

### E32: Document Review Outcome Notification
**Traces to**: Journey J25  
**Phase**: phase-2  
Student receives notification of document review outcome.

- Wire document review outcome into notification trigger
- Tests: notification generated on approve/reject

### E33: Visa Queue View
**Traces to**: Journey J26  
**Phase**: phase-3  
Visa Processor views applications at the visa stage.

- Backend: visa-stage applications queue API
- Frontend: visa processor dashboard (queue view)

### E34: Visa Type & Interview Recording
**Traces to**: Journey J27  
**Phase**: phase-3  
Visa Processor records visa type & embassy interview date.

- Backend: VisaDetail model + migration (type, interview date)
- Frontend: visa detail update form (type + interview date)

### E35: Visa Outcome Update
**Traces to**: Journey J28  
**Phase**: phase-3  
Visa Processor updates visa outcome/status.

- Backend: visa outcome update API
- Frontend: visa outcome update UI
- Tests: visa stage transitions and outcome recording

### E36: Student Loan Opt-in
**Traces to**: Journey J29  
**Phase**: phase-3  
Student opts into loan tracking on an application.

- Backend: loan opt-in field on Application model + migration
- Frontend: loan opt-in UI (student application flow)

### E37: Staff Loan Status Update
**Traces to**: Journey J30  
**Phase**: phase-3  
Staff records/updates loan status, lender, amount.

- Backend: loan lender/amount/status fields + update-loan-status API
- Frontend: loan tracking UI (staff status update)
- Tests: loan field updates and permission checks

### E38: Mark Application Enrolled
**Traces to**: Journey J31  
**Phase**: mvp  
Staff marks an application Enrolled.

- Backend: mark-enrolled transition API with details capture
- Frontend: 'Mark Enrolled' action UI

### E39: Mark Application Rejected
**Traces to**: Journey J32  
**Phase**: mvp  
Staff marks an application Rejected (with reason).

- Backend: mark-rejected transition API with reason capture
- Frontend: 'Mark Rejected' action UI with reason field

### E40: Mark Application Withdrawn
**Traces to**: Journey J33  
**Phase**: mvp  
Staff marks an application Withdrawn (with reason).

- Backend: mark-withdrawn transition API with reason capture
- Frontend: 'Mark Withdrawn' action UI with reason field
- Tests: terminal states (Enrolled/Rejected/Withdrawn) are final

### E41: Branch Manager Analytics Dashboard
**Traces to**: Journey J34  
**Phase**: phase-3  
Branch Manager views branch dashboard with date-range filter.

- Backend: registrations-over-time aggregation query + API
- Backend: conversion funnel by stage aggregation query + API
- Frontend: branch manager dashboard charts with date-range filter

### E42: Owner Cross-Branch Dashboard
**Traces to**: Journey J35  
**Phase**: phase-3  
Consultancy Owner views cross-branch comparison dashboard.

- Backend: branch comparison aggregation query + API
- Frontend: owner cross-branch dashboard view

### E43: Super Admin Platform-Wide Stats
**Traces to**: Journey J36  
**Phase**: phase-3  
Super Admin views platform-wide tenant stats.

- Backend: platform-wide tenant stats aggregation query + API
- Frontend: super admin stats dashboard view

### E44: Report Export (CSV/Excel)
**Traces to**: Journey J37  
**Phase**: phase-3  
Admin role exports a report to CSV/Excel.

- Backend: CSV/Excel export endpoint for student lists
- Backend: CSV/Excel export endpoint for analytics views
- Frontend: export button integration on relevant views

### E45: Owner Plan & Usage View
**Traces to**: Journey J38  
**Phase**: phase-3  
Consultancy Owner views current plan & usage.

- Backend: current plan & usage summary API
- Frontend: billing/usage page

### E46: Plan Upgrade/Downgrade Checkout (Razorpay)
**Traces to**: Journey J39  
**Phase**: phase-3  
Consultancy Owner upgrades/downgrades plan via Razorpay checkout.

- Backend: Razorpay SDK integration + config
- Backend: create order API for plan upgrade
- Backend: Razorpay webhook handler (payment confirmation)
- Backend: apply plan change on confirmed payment
- Frontend: Razorpay checkout integration

### E47: Super Admin Billing Status Overview
**Traces to**: Journey J40  
**Phase**: phase-3  
Super Admin views all tenants' billing/subscription status.

- Backend: list endpoint for all tenants' plan/billing status
- Frontend: super admin view of all tenants' plans/billing status

### E48: In-App Notification Generation
**Traces to**: Journey J41  
**Phase**: mvp  
User receives an in-app notification on a relevant event.

- Backend: Notification model + migration
- Backend: notification-creation service + hooks into key events
- Tests: notification generated on key events

### E49: Email Notifications
**Traces to**: Journey J42  
**Phase**: phase-2  
Email delivery for key events, pluggable for future SMS/WhatsApp.

- Backend: email service abstraction (SMTP client wrapper)
- Backend: email templates for key events (stage change, doc review, meeting, invite)
- Backend: wire email sending into existing notification triggers
- Tests: email sending triggered correctly (mocked SMTP)

### E50: Notification Center UI
**Traces to**: Journey J43  
**Phase**: mvp  
User views notification center and marks items read.

- Backend: list/mark-read notification API
- Frontend: notification bell + notification center UI

### E51: Internationalization (i18n)
**Traces to**: Requirements §1 Deployment/i18n  
**Phase**: phase-2  
i18n framework with English, Hindi, Telugu translations.

- Frontend: set up i18next framework + language switcher
- Frontend: extract existing UI strings into translation keys
- Add Hindi and Telugu translation files

### E52: Currency Display Configuration
**Traces to**: Requirements §1 Currency  
**Phase**: phase-2  
Per-tenant display currency for loan/fee amounts.

- Backend: currency field on tenant + migration
- Backend/Frontend: currency formatting utility
- Frontend: currency-aware amount display components

### E53: Marketing Landing Page
**Traces to**: Requirements §10 Marketing Site  
**Phase**: phase-3  
Public landing page separate from the app login.

- Design landing page layout (hero, features, CTA sections)
- Build landing page route/component
- Wire CTA buttons to login/signup
