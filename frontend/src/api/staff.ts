import { apiFetch } from './client'
import type { Staff, StaffCreateRequest, StaffUpdateRequest } from '../types/staff'

export async function fetchStaff(): Promise<Staff[]> {
  return apiFetch<Staff[]>('/staff')
}

export async function fetchStaffById(id: number): Promise<Staff> {
  return apiFetch<Staff>(`/staff/${id}`)
}

export async function createStaff(payload: StaffCreateRequest): Promise<Staff> {
  return apiFetch<Staff>('/staff', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateStaff(id: number, payload: StaffUpdateRequest): Promise<Staff> {
  return apiFetch<Staff>(`/staff/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
