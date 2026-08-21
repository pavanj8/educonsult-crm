/** Stage history entry type aligned with the backend E25 StageHistory model (Journey J18).
 *
 * Mirrors `backend/app/models/stage_history.py`:
 *   - `from_stage` is null for the initial row (the application was just registered)
 *   - `to_stage` is the resulting stage after the transition
 *   - `changed_at` is the event timestamp (UTC, ISO-8601)
 *   - `reason` is optional free-text (required by REJECTED / WITHDRAWN, otherwise null)
 *   - `changed_by_user_id` is null when the actor is unknown / the user was later deleted
 */
import type { PipelineStage } from './application'

export interface StageHistoryEntry {
  id: number
  application_id: number
  from_stage: PipelineStage | null
  to_stage: PipelineStage
  changed_at: string
  reason: string | null
  changed_by_user_id: number | null
}
