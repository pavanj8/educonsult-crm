/** Master data types for tenant-scoped country/university/program dropdowns (E14/E16). */

export type Country = {
  id: number
  tenant_id: number
  name: string
  code: string
}

export type University = {
  id: number
  tenant_id: number
  country_id: number
  name: string
}

export type Program = {
  id: number
  tenant_id: number
  university_id: number
  name: string
}

/** Admin CRUD request payloads (E14 master-data admin endpoints; Journey J7). */

export type CountryCreateRequest = {
  name: string
  code: string
}

export type CountryUpdateRequest = {
  name?: string
  code?: string
}

export type UniversityCreateRequest = {
  country_id: number
  name: string
}

export type UniversityUpdateRequest = {
  country_id?: number
  name?: string
}

export type ProgramCreateRequest = {
  university_id: number
  name: string
}

export type ProgramUpdateRequest = {
  university_id?: number
  name?: string
}
