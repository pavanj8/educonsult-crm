/** Document verifier pending-queue types (E28; Journey J21). */

export interface PendingDocument {
  id: number
  tenant_id: number
  application_id: number
  checklist_item_template_id: number | null
  original_filename: string
  content_type: string
  size_bytes: number
  uploaded_by_user_id: number
  uploaded_at: string
  application_stage: string
  student_id: number
  university_id: number
  program_id: number
}

export interface PendingDocumentQueue {
  items: PendingDocument[]
  total: number
  limit: number
  offset: number
}

/** A document after a verifier decision (approve/reject) — E29/E30. */
export interface VerifiedDocument {
  id: number
  tenant_id: number
  application_id: number
  status: string
  original_filename: string
  verified_by_user_id: number | null
  verified_at: string | null
  rejection_reason: string | null
  approval_comment: string | null
}
