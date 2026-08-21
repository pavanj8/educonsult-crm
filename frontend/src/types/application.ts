/** Application types aligned with backend E18 schemas (Journey J11). */

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

export type Application = {
  id: number
  tenant_id: number
  student_id: number
  university_id: number
  program_id: number
  stage: PipelineStage
  created_at: string
  updated_at: string
}

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
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

export type CreateApplicationRequest = {
  university_id: number
  program_id: number
}
