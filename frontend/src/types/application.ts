/** Application types aligned with backend E18 schemas (Journey J11).

Defines the canonical pipeline stage set and the terminal/non-terminal
partition used across the UI. The terminal/non-terminal split lives
here (not in feature pages) so any future pipeline stage added in
:ts:type:`PipelineStage` is automatically picked up by code that asks
"which stages still allow document collection?" without having to
duplicate the membership list (E15 / Journey J8 — terminal applications
never need a checklist template).
*/

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

/**
 * Stages that resolve an application to a final state. Requirements §5
 * (Pipeline stages) names the three: enrolled / rejected / withdrawn.
 * Document collection stops here — the J8 checklist builder UI excludes
 * these from its template picker (E15).
 */
export const TERMINAL_PIPELINE_STAGES: ReadonlySet<PipelineStage> = new Set<
  PipelineStage
>(['enrolled', 'rejected', 'withdrawn'])

/**
 * Pipeline stages that may still collect documents (Requirements §5) — used by
 * e.g. the E15 checklist template picker.
 *
 * This is a manually-maintained list of every :ts:type:`PipelineStage`, then
 * filtered to drop :ts:var:`TERMINAL_PIPELINE_STAGES`. It is NOT auto-derived
 * from the type: adding a new stage to :ts:type:`PipelineStage` also requires
 * adding it to the literal below (TypeScript does not enumerate union members
 * at runtime).
 */
export const NON_TERMINAL_PIPELINE_STAGES: readonly PipelineStage[] = (
  [
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
  ] as PipelineStage[]
).filter((stage) => !TERMINAL_PIPELINE_STAGES.has(stage))

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
