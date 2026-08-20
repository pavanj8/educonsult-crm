/** Application types aligned with backend E18/E21 schemas (Journey J11/J14). */

export type PipelineStage =
  | 'registered'
  | 'counseling'
  | 'university_shortlisting'
  | 'application_submitted'
  | 'document_verification'
  | 'offer_letter'
  | 'visa_processing'
  | 'loan_processing'
  | 'enrolled'
  | 'rejected'
  | 'withdrawn'

// Terminal stages - applications cannot progress further
export const TERMINAL_STAGES: readonly PipelineStage[] = ['enrolled', 'rejected', 'withdrawn'] as const

export function isTerminalStage(stage: PipelineStage): boolean {
  return TERMINAL_STAGES.includes(stage)
}

export type Application = {
  id: number
  tenant_id: number
  student_id: number
  assigned_counselor_id: number | null
  target_university_id: number | null
  target_program_id: number | null
  stage: PipelineStage
  stage_reason: string | null
  enrollment_date: string | null
  loan_opted_in: boolean
  loan_status: string | null
  loan_lender: string | null
  loan_amount: number | null
  created_at: string
  updated_at: string
}

export type ApplicationWithStudent = Application & {
  student_name: string | null
  student_email: string
  student_phone: string | null
  student_role: 'student'
}

export type CounselorQueueFilter = {
  stage?: PipelineStage
  search?: string
}

export type StageCount = {
  [stage: string]: number
}

export const PIPELINE_STAGES: readonly PipelineStage[] = [
  'registered',
  'counseling',
  'university_shortlisting',
  'application_submitted',
  'document_verification',
  'offer_letter',
  'visa_processing',
  'loan_processing',
  'enrolled',
  'rejected',
  'withdrawn',
] as const

export const STAGE_LABELS: Record<PipelineStage, string> = {
  registered: 'Registered',
  counseling: 'Counseling',
  university_shortlisting: 'University Shortlisting',
  application_submitted: 'Application Submitted',
  document_verification: 'Document Verification',
  offer_letter: 'Offer Letter',
  visa_processing: 'Visa Processing',
  loan_processing: 'Loan Processing',
  enrolled: 'Enrolled',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

export const STAGE_COLORS: Record<PipelineStage, string> = {
  registered: '#6b7280',
  counseling: '#3b82f6',
  university_shortlisting: '#8b5cf6',
  application_submitted: '#f59e0b',
  document_verification: '#06b6d4',
  offer_letter: '#10b981',
  visa_processing: '#f97316',
  loan_processing: '#ec4899',
  enrolled: '#22c55e',
  rejected: '#ef4444',
  withdrawn: '#78716c',
}
