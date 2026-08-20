import { apiFetch } from './client'
import type { ApplicationWithStudent, CounselorQueueFilter, StageCount } from '../types/application'

export async function fetchCounselorQueue(
  filter?: CounselorQueueFilter,
): Promise<ApplicationWithStudent[]> {
  const params = new URLSearchParams()
  if (filter?.stage) {
    params.set('stage', filter.stage)
  }
  if (filter?.search) {
    params.set('search', filter.search)
  }
  const query = params.toString()
  const path = `/counselor/queue${query ? `?${query}` : ''}`
  return apiFetch<ApplicationWithStudent[]>(path)
}

export async function fetchCounselorQueueCounts(): Promise<StageCount> {
  return apiFetch<StageCount>('/counselor/queue/counts')
}
