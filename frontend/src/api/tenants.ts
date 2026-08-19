import { apiFetch } from './client'
import type { Tenant, TenantCreateRequest } from '../types/tenant'

export async function fetchTenants(): Promise<Tenant[]> {
  return apiFetch<Tenant[]>('/tenants')
}

export async function createTenant(payload: TenantCreateRequest): Promise<Tenant> {
  return apiFetch<Tenant>('/tenants', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
