# EduConsult CRM — User Journeys

Status: **Approved**. Each journey is atomic (one actor, one discrete goal) and traces back to a section of [`requirements.md`](./requirements.md). Each journey is in turn referenced by one or more epics in [`epics.md`](./epics.md).

## Onboarding & Tenant Management
_Traces to Requirements §1 Product & Deployment, §3 Roles, §4 Billing_

- **J1**: Super Admin creates a new tenant
- **J2**: Super Admin sets/updates a tenant's subscription plan
- **J3**: Consultancy Owner completes tenant profile (logo, brand color, currency)
- **J4**: Consultancy Owner creates a new branch
- **J5**: Owner/Branch Manager creates a staff account
- **J6**: Owner/Branch Manager deactivates/reactivates a staff account
- **J7**: Owner/Branch Manager manages master data (countries/universities/programs)
- **J8**: Owner/Branch Manager defines a document checklist template for a stage/program

## Student Registration
_Traces to Requirements §5 Student Journey & Data Model_

- **J9**: Student self-registers an account
- **J10**: Receptionist creates a student record (walk-in)
- **J11**: Student creates a new application (university + program)
- **J12**: System auto-assigns a counselor to a new application (round-robin)
- **J13**: Branch Manager/Receptionist manually reassigns a counselor

## Counseling
_Traces to Requirements §5 Student Journey & Data Model (Meetings, Notes)_

- **J14**: Counselor views their assigned student/application queue
- **J15**: Counselor schedules a meeting with a student
- **J16**: Student views/receives a meeting notification
- **J17**: Counselor logs internal meeting notes
- **J18**: Counselor/staff advances an application to the next pipeline stage

## Documents
_Traces to Requirements §5 Student Journey & Data Model (Documents)_

- **J19**: Student views the document checklist for their application
- **J20**: Student uploads a document against a checklist item
- **J21**: Document Verifier reviews the pending-documents queue
- **J22**: Document Verifier approves a document
- **J23**: Document Verifier rejects a document with comments
- **J24**: Student re-uploads a rejected document
- **J25**: Student receives notification of document review outcome

## Visa Processing
_Traces to Requirements §3 Roles (Visa Processor)_

- **J26**: Visa Processor views applications at the visa stage
- **J27**: Visa Processor records visa type & embassy interview date
- **J28**: Visa Processor updates visa outcome/status

## Loans (tracking only)
_Traces to Requirements §5 Student Journey & Data Model (Loans)_

- **J29**: Student opts into loan tracking on an application
- **J30**: Staff records/updates loan status, lender, amount

## Application Resolution
_Traces to Requirements §5 Student Journey & Data Model (Pipeline stages)_

- **J31**: Staff marks an application Enrolled
- **J32**: Staff marks an application Rejected (with reason)
- **J33**: Staff marks an application Withdrawn (with reason)

## Analytics & Reporting
_Traces to Requirements §7 Analytics & Reporting_

- **J34**: Branch Manager views branch dashboard with date-range filter
- **J35**: Consultancy Owner views cross-branch comparison dashboard
- **J36**: Super Admin views platform-wide tenant stats
- **J37**: Admin role exports a report to CSV/Excel

## Billing
_Traces to Requirements §4 Billing & Subscription_

- **J38**: Consultancy Owner views current plan & usage
- **J39**: Consultancy Owner upgrades/downgrades plan via Razorpay checkout
- **J40**: Super Admin views all tenants' billing/subscription status

## Notifications
_Traces to Requirements §6 Notifications_

- **J41**: User receives an in-app notification on a relevant event
- **J42**: User receives an email notification on a relevant event
- **J43**: User views notification center and marks items read

## Auth & Security
_Traces to Requirements §8 Security & Compliance_

- **J44**: User logs in (any role)
- **J45**: User resets a forgotten password
- **J46**: System rate-limits repeated failed login attempts
