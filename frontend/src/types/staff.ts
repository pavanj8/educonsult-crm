/** Staff types aligned with backend E12 schemas (Journey J5). */

export type StaffCreatableRole =
  | 'branch_manager'
  | 'counselor'
  | 'document_verifier'
  | 'visa_processor'
  | 'receptionist'

export type StaffCreateRequest = {
  email: string
  password: string
  role: StaffCreatableRole
  branch_id: number
}

export type StaffUpdateRequest = {
  role?: StaffCreatableRole
  branch_id?: number
}

export type Staff = {
  id: number
  email: string
  role: StaffCreatableRole
  tenant_id: number
  branch_id: number
  created_at: string
  updated_at: string
}

export const STAFF_CREATABLE_ROLES: readonly StaffCreatableRole[] = [
  'branch_manager',
  'counselor',
  'document_verifier',
  'visa_processor',
  'receptionist',
] as const

export const STAFF_ROLE_LABELS: Record<StaffCreatableRole, string> = {
  branch_manager: 'Branch Manager',
  counselor: 'Counselor',
  document_verifier: 'Document Verifier',
  visa_processor: 'Visa Processor',
  receptionist: 'Receptionist',
}
