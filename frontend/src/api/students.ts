import { apiFetch } from './client'
import type { RegisterStudentRequest, RegisterStudentResponse } from '../types/student'

export async function registerStudent(
  payload: RegisterStudentRequest,
): Promise<RegisterStudentResponse> {
  return apiFetch<RegisterStudentResponse>('/auth/register-student', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  })
}
