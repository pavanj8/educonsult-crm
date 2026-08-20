/** Application pipeline stages (Requirements §5; backend pipeline.stages). */

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

export type CreateApplicationRequest = {
  university_id: number
  program_id: number
}
