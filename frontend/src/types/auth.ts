/** Auth types aligned with backend E5 schemas (Journey J44). */

export type UserRole =
  | 'super_admin'
  | 'consultancy_owner'
  | 'branch_manager'
  | 'counselor'
  | 'document_verifier'
  | 'visa_processor'
  | 'receptionist'
  | 'student'

export type LoginCredentials = {
  email: string
  password: string
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
}

export type AuthUser = {
  id: number
  email: string
  role: UserRole
  tenant_id: number | null
  branch_id: number | null
}

/**
 * Display labels for every role, including the three that are not staff-
 * creatable (super admin, consultancy owner, student) and so are absent from
 * STAFF_ROLE_LABELS. Anything rendering the signed-in user's own role needs
 * the full set.
 */
export const USER_ROLE_LABELS: Record<UserRole, string> = {
  super_admin: 'Super Admin',
  consultancy_owner: 'Consultancy Owner',
  branch_manager: 'Branch Manager',
  counselor: 'Counselor',
  document_verifier: 'Document Verifier',
  visa_processor: 'Visa Processor',
  receptionist: 'Receptionist',
  student: 'Student',
}
