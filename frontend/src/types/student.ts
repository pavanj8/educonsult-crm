/** Student registration types aligned with backend E16 schemas (Journey J9). */

import type { UserRole } from './auth'

export type RegisterStudentRequest = {
  tenant_slug: string
  branch_id: number
  email: string
  password: string
  name: string
  phone: string
  date_of_birth: string
  target_country_id?: number
  target_university_id?: number
  target_program_id?: number
}

export type RegisterStudentResponse = {
  id: number
  email: string
  role: UserRole
  tenant_id: number
  branch_id: number
  name: string
  phone: string
  date_of_birth: string
  target_country_id: number | null
  target_university_id: number | null
  target_program_id: number | null
  access_token: string
  refresh_token: string
  token_type: string
  created_at: string
}
