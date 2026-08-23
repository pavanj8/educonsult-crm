import { apiFetch } from './client'
import type {
  ReceptionistIntakeRequest,
  ReceptionistIntakeResponse,
} from '../types/receptionistIntake'

/**
 * Create a student record on behalf of a walk-in (E17; Journey J10).
 *
 * Endpoint: ``POST /students`` (backend #141). The receptionist's
 * tenant is derived from the bearer token on the request; the client
 * therefore sends the auth header (unlike the public E16
 * ``/auth/register-student`` flow).
 */
export async function createStudentByReceptionist(
  payload: ReceptionistIntakeRequest,
): Promise<ReceptionistIntakeResponse> {
  return apiFetch<ReceptionistIntakeResponse>('/students', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}