# EduConsult CRM — Requirements Specification

Status: **Approved** (baseline for Journeys → Epics → Tasks)

## 1. Product & Deployment
- **Product name**: EduConsult CRM
- **Model**: Multi-tenant SaaS, also deployable on-prem (single-tenant install) from the same codebase via Docker
- **Multi-tenancy**: Single shared PostgreSQL database; every table carries a `tenant_id`
- **Tenant provisioning**: Super Admin only creates new tenants (no self-signup for consultancies)
- **White-labeling**: Each tenant can upload a logo + set a primary brand color (no custom domains for v1)
- **Internationalization**: UI supports English + Hindi + Telugu, built on an i18n framework for easy future expansion
- **Currency**: Display/reporting currency configurable per tenant (no live FX conversion)

## 2. Tech Stack
- **Backend**: FastAPI (Python), PostgreSQL, SQLAlchemy 2.0 + Alembic migrations, JWT auth with custom RBAC
- **Frontend**: React + Vite + TypeScript SPA
- **Storage**: S3-compatible object storage (AWS S3 for SaaS, MinIO for on-prem) for documents
- **Email**: SMTP-based in-app + email notifications; architecture kept pluggable for SMS/WhatsApp later
- **Payments**: Razorpay integration for tenant subscription billing
- **Testing**: pytest (backend unit + integration) + Playwright (E2E)
- **Infra**: Monorepo (`/backend`, `/frontend`), Docker Compose for local dev and on-prem deployment

## 3. Roles & Hierarchy
1. **Super Admin** — manages all tenants/consultancies platform-wide, billing oversight
2. **Consultancy Owner** — full visibility/control across all branches in their tenant; manages staff across branches
3. **Branch Manager** — manages their own branch only (staff, students, visibility); can create/manage staff within their branch
4. **Counselor** — manages assigned students, scheduling, counseling stage decisions
5. **Document Verifier** — reviews/approves/rejects uploaded documents
6. **Visa Processor** — manages visa stage: visa type, embassy interview date/outcome tracking
7. **Receptionist** — intake only: registers/creates student records, basic front-desk info; no document verification or stage progression beyond initial registration
8. **Student** — own dashboard, applications, documents, notifications

## 4. Billing & Subscription (Platform-level, Super Admin domain)
- 3 tiers: **Starter** (1 branch, limited staff/students), **Growth** (multiple branches, higher limits), **Enterprise** (unlimited/custom)
- Razorpay integration for subscription payments
- No separate payment gateway needed for student-facing fees (out of scope for v1)

## 5. Student Journey & Data Model
- **Registration**: Both public self-registration and staff-created records supported; no email verification required for v1
- **Profile fields**: name, email, password, age/DOB, phone, plus structured (dropdown, admin-managed master list) target country / university / program
- **Applications**: A student can have **multiple applications** (university/program combinations) running in parallel, each with its own independent pipeline stage
- **Pipeline stages** (per application): Registered → Counseling → University Shortlisting → Application Submitted → Document Verification → Offer Letter → Visa Processing → Loan Processing (optional) → **Enrolled** / **Rejected** / **Withdrawn** (three distinct terminal states, each capturing a reason)
- **Counselor assignment**: Auto-assigned via round-robin within the branch, with manual reassignment allowed
- **Loans**: Tracking-only fields (opted-in, status, amount, lender) — no separate loan officer workflow for v1
- **Documents**: Per-stage/program checklist templates (defined by admin/branch); students upload against each checklist item; verifier approves/rejects with comments; default limits 10MB, PDF/JPG/PNG/DOCX
- **Meetings**: Simple internal scheduling (counselor sets date/time, student notified) — no external calendar integration
- **Internal notes**: Staff-only comment thread per student (counselor/verifier/branch manager visible), hidden from student

## 6. Notifications
- In-app + email for status changes, document verification results, meeting scheduling
- Notification service architected to plug in SMS/WhatsApp providers later without rework

## 7. Analytics & Reporting
- Metrics: new registrations, conversion funnel by stage, counselor workload/performance, branch comparison, revenue/loan stats
- Date-range filtering (weekly, 15-day, custom range) for Admin/Owner/Branch Manager dashboards
- Export: CSV/Excel for v1 (PDF export deferred)

## 8. Security & Compliance
- JWT auth with refresh tokens; strong password policy enforced; 2FA deferred (not blocking v1)
- Basic rate limiting on public auth endpoints (login, signup)
- Session/device management: skipped for v1 (JWT expiry/refresh is sufficient)
- Audit log: basic trail on key actions (stage changes, document approvals, user management)
- Data retention: soft-delete + basic data export/delete capability (not full GDPR tooling)

## 9. Out of Scope for v1
- Full GDPR tooling, live FX conversion, external calendar integrations, student-facing payment collection, SMS/WhatsApp (architecture only), native mobile apps, session/device management, 2FA

## 10. Marketing Site
- A simple public marketing/landing page is needed, separate from the app login

## 11. Process & GitHub Setup
- Workflow: Requirements → User Journeys → Epics → Tasks/Issues in GitHub → **no code written without a linked ticket**
- GitHub repo: [`pavanj8/educonsult-crm`](https://github.com/pavanj8/educonsult-crm) (private)
- Issue structure: **Epics** (large features, milestone/label-tracked) each containing linked **Task** issues
- Labels: `epic` / `task` + `area:*` + `phase:mvp|phase-2|phase-3`
- Milestones: Phase 1 - MVP, Phase 2, Phase 3

See [`journeys.md`](./journeys.md) for the atomic user journeys derived from this spec, and [`epics.md`](./epics.md) for the epics derived from those journeys (with full backtracking to this document).
