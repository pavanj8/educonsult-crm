# Student Registration — Requirements (Harness Demo)

Minimal, local requirements doc for the agent harness prototype. This is
intentionally tiny and unrelated to the full EduConsult CRM spec in
`../docs/requirements.md`.

## R1: Student Registration
A prospective student can register with: name, email, password, age.
- Email must be a syntactically valid email address. Invalid format -> `400 Bad Request`.
- Email must be unique. Duplicate email -> `400 Bad Request`.
- On success -> `201 Created` with the created student (id, name, email, age, created_at).
- Password is never returned in any response.

## R2: Student Lookup
- `GET /students/{id}` returns the student or `404 Not Found`.
- `GET /students` returns all students.

## R3: Age Eligibility (not yet implemented — see TICKET-002)
The consultancy only accepts registrations from students aged 16-100 inclusive.
Registrations outside this range must be rejected with `400 Bad Request` and a
clear error message, without creating a record.
