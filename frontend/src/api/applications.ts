import { apiFetch } from './client'
<<<<<<< HEAD
import type { Application } from '../types/application'

export async function fetchApplications(): Promise<Application[]> {
  return apiFetch<Application[]>('/applications')
=======
import type { Application, CreateApplicationRequest } from '../types/application'

export async function createApplication(
  payload: CreateApplicationRequest,
): Promise<Application> {
  return apiFetch<Application>('/applications', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
>>>>>>> origin/main
}
