/** Receptionist student intake types (E17; Journey J10).

 * The receptionist — already authenticated and scoped to a single
 * branch — creates a student record on behalf of a walk-in via
 * ``POST /students``. The backend derives ``tenant_id`` from the
 * receptionist's session and records the staff member as the
 * creator, so the request only carries the student's profile fields.
 *
 * A ``password`` is required because the backend's
 * :class:`StaffCreateStudentRequest` schema enforces a non-empty,
 * policy-compliant password for every student account. The receptionist
 * generates a temporary password at intake time and hands it to the
 * walk-in so they can later log in via the E16 self-registration path.
 */

import type { UserRole } from './auth'

export type ReceptionistIntakeRequest = {
  branch_id: number
  email: string
  password: string
  name: string
  phone: string
  date_of_birth: string
  target_country_id?: number
  target_university_id?: number
  target_program_id?: number
}

/**
 * Response mirrors the persisted ``Student`` row (no tokens issued).
 *
 * The ``role`` field is included to match the backend's
 * :class:`StaffCreateStudentResponse` schema even though the receptionist
 * intake UI does not consume it today — keeping the contract in lockstep
 * with the backend prevents silent field drift if a caller ever reads it.
 */
export type ReceptionistIntakeResponse = {
  id: number
  email: string
  role: UserRole
  tenant_id: number
  branch_id: number
  name: string
  phone: string
  date_of_birth: string
  target_country_id: number | null
  target_university_id: number | null
  target_program_id: number | null
  created_at: string
}