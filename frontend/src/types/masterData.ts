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
