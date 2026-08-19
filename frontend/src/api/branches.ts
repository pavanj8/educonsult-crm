import { apiFetch } from './client'
import type { Branch, BranchCreateRequest, BranchUpdateRequest } from '../types/branch'

export async function fetchBranches(): Promise<Branch[]> {
  return apiFetch<Branch[]>('/branches')
}

export async function createBranch(payload: BranchCreateRequest): Promise<Branch> {
  return apiFetch<Branch>('/branches', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateBranch(
  id: number,
  payload: BranchUpdateRequest,
): Promise<Branch> {
  return apiFetch<Branch>(`/branches/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
