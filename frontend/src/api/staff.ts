import { apiFetch } from './client'
import type { Staff, StaffCreateRequest } from '../types/staff'

export async function createStaff(payload: StaffCreateRequest): Promise<Staff> {
  return apiFetch<Staff>('/staff', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
