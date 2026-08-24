/** Visa-stage applications queue types (E33; Journey J26; frontend #192).

The visa processor dashboard is the read-side of the visa stage: it
lists applications currently in the ``visa_processing`` pipeline
stage so the visa processor can pick the next application to work on.
The shape mirrors the E33 backend queue item payload
(:class:`app.schemas.visa.VisaStageQueueItem` from sibling ticket
#191) and the queue-pagination convention used by the E28 verifier
queue (:ts:type:`PendingDocumentQueue`).
*/

/** One row in the visa-stage applications queue (E33; J26). */
export interface VisaStageQueueItem {
  id: number
  tenant_id: number
  branch_id: number | null
  student_id: number
  assigned_counselor_id: number | null
  university_id: number
  program_id: number
  /** Always ``"visa_processing"`` for items returned by this queue. */
  stage: string
  created_at: string
  updated_at: string
}

/** Paginated visa-stage applications queue (E33; J26). */
export interface VisaStageQueue {
  items: VisaStageQueueItem[]
  total: number
  limit: number
  offset: number
}
