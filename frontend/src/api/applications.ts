import { apiFetch } from './client'
import type { Application } from '../types/application'

export async function fetchApplications(): Promise<Application[]> {
  return apiFetch<Application[]>('/applications')
}
