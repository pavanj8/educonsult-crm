/** Tenant types aligned with backend E8 schemas (Journey J1). */

export type Tenant = {
  id: number
  name: string
  slug: string
  created_at: string
  updated_at: string
}

export type TenantCreateRequest = {
  name: string
  slug: string
  owner_email: string
}
