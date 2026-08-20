import { apiFetch } from './client'
import type { Application, CreateApplicationRequest } from '../types/application'

export async function createApplication(
  payload: CreateApplicationRequest,
): Promise<Application> {
  return apiFetch<Application>('/applications', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
