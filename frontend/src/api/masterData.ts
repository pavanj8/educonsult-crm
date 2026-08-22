import { apiFetch } from './client'
import type {
  Country,
  CountryCreateRequest,
  CountryUpdateRequest,
  Program,
  ProgramCreateRequest,
  ProgramUpdateRequest,
  University,
  UniversityCreateRequest,
  UniversityUpdateRequest,
} from '../types/masterData'

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

function adminResourcePath(resource: string, id?: number): string {
  const base = `/master-data/admin/${resource}`
  return typeof id === 'number' ? `${base}/${id}` : base
}

export async function fetchAdminCountries(): Promise<Country[]> {
  return apiFetch<Country[]>(adminResourcePath('countries'))
}

export async function createAdminCountry(payload: CountryCreateRequest): Promise<Country> {
  return apiFetch<Country>(adminResourcePath('countries'), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateAdminCountry(
  id: number,
  payload: CountryUpdateRequest,
): Promise<Country> {
  return apiFetch<Country>(adminResourcePath('countries', id), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteAdminCountry(id: number): Promise<void> {
  await apiFetch<void>(adminResourcePath('countries', id), {
    method: 'DELETE',
  })
}

export async function fetchAdminUniversities(): Promise<University[]> {
  return apiFetch<University[]>(adminResourcePath('universities'))
}

export async function createAdminUniversity(
  payload: UniversityCreateRequest,
): Promise<University> {
  return apiFetch<University>(adminResourcePath('universities'), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateAdminUniversity(
  id: number,
  payload: UniversityUpdateRequest,
): Promise<University> {
  return apiFetch<University>(adminResourcePath('universities', id), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteAdminUniversity(id: number): Promise<void> {
  await apiFetch<void>(adminResourcePath('universities', id), {
    method: 'DELETE',
  })
}

export async function fetchAdminPrograms(): Promise<Program[]> {
  return apiFetch<Program[]>(adminResourcePath('programs'))
}

export async function createAdminProgram(payload: ProgramCreateRequest): Promise<Program> {
  return apiFetch<Program>(adminResourcePath('programs'), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateAdminProgram(
  id: number,
  payload: ProgramUpdateRequest,
): Promise<Program> {
  return apiFetch<Program>(adminResourcePath('programs', id), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteAdminProgram(id: number): Promise<void> {
  await apiFetch<void>(adminResourcePath('programs', id), {
    method: 'DELETE',
  })
}
