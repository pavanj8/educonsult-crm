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
