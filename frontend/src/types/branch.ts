/** Branch types aligned with backend E11 schemas (Journey J4). */

export type Branch = {
  id: number
  tenant_id: number
  name: string
  city: string
  created_at: string
  updated_at: string
}

export type BranchCreateRequest = {
  name: string
  city: string
}

export type BranchUpdateRequest = {
  name?: string
  city?: string
}
