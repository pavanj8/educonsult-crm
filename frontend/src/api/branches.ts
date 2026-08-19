import { apiFetch } from './client'
import type { Branch } from '../types/branch'

export async function fetchBranches(): Promise<Branch[]> {
  return apiFetch<Branch[]>('/branches')
}
