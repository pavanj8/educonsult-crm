/** Receptionist student intake types (E17; Journey J10).

 * The receptionist — already authenticated and scoped to a single
 * branch — creates a student record on behalf of a walk-in via
 * ``POST /students``. The backend derives ``tenant_id`` from the
 * receptionist's session and records the staff member as the
 * creator, so the request only carries the student's profile fields.
 */

export type ReceptionistIntakeRequest = {
  branch_id: number
  email: string
  name: string
  phone: string
  date_of_birth: string
  target_country_id?: number
  target_university_id?: number
  target_program_id?: number
}

/** Response mirrors the persisted ``Student`` row (no tokens issued). */
export type ReceptionistIntakeResponse = {
  id: number
  email: string
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