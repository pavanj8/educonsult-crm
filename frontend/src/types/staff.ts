/** Staff types aligned with backend E12 schemas (Journey J5). */

import { USER_ROLE_LABELS } from './auth'

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
  is_active: boolean
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

/** Narrowed from USER_ROLE_LABELS so the two cannot drift apart. */
export const STAFF_ROLE_LABELS: Record<StaffCreatableRole, string> = {
  branch_manager: USER_ROLE_LABELS.branch_manager,
  counselor: USER_ROLE_LABELS.counselor,
  document_verifier: USER_ROLE_LABELS.document_verifier,
  visa_processor: USER_ROLE_LABELS.visa_processor,
  receptionist: USER_ROLE_LABELS.receptionist,
}
