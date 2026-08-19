# TICKET-002: Reject registrations with age outside 16-100

**Epic**: EPIC-002 Age Eligibility Validation
**Traces to requirement**: R3 (requirements.md)
**Status**: Open

## Description
`POST /students/register` currently accepts any integer age, including
negative numbers, zero, and unrealistically high values. The consultancy
only accepts registrations from students aged 16 to 100 inclusive.

## Acceptance Criteria
- Registering with `age < 16` returns `400 Bad Request` with a clear error
  message (e.g. mentioning the age must be at least 16), and does **not**
  create a student record.
- Registering with `age > 100` returns `400 Bad Request` with a clear error
  message, and does **not** create a student record.
- Registering with `age == 16` or `age == 100` (boundary values) succeeds
  normally (`201 Created`).
- All existing tests in `backend/tests/` must continue to pass.
- Add new automated tests covering: age below range, age above range, and
  both boundary values.

## Out of Scope
- Do not change anything unrelated to age validation (e.g. do not touch
  email validation, duplicate-email handling, or the GET endpoints).
