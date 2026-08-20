import { apiFetch } from './client'
import type { Country, Program, University } from '../types/masterData'

function tenantMasterDataPath(tenantSlug: string, resource: string, query?: string): string {
  const base = `/tenants/${encodeURIComponent(tenantSlug)}/${resource}`
  return query ? `${base}?${query}` : base
}

export async function fetchCountries(tenantSlug: string): Promise<Country[]> {
  return apiFetch<Country[]>(tenantMasterDataPath(tenantSlug, 'countries'), {
    skipAuth: true,
  })
}

export async function fetchUniversities(
  tenantSlug: string,
  countryId: number,
): Promise<University[]> {
  return apiFetch<University[]>(
    tenantMasterDataPath(tenantSlug, 'universities', `country_id=${countryId}`),
    { skipAuth: true },
  )
}

export async function fetchPrograms(
  tenantSlug: string,
  universityId: number,
): Promise<Program[]> {
  return apiFetch<Program[]>(
    tenantMasterDataPath(tenantSlug, 'programs', `university_id=${universityId}`),
    { skipAuth: true },
  )
}
