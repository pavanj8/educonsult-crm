import { Fragment, useState } from 'react'

import ChecklistView from './ChecklistView'
import { useApplicationChecklist } from '../../hooks/useApplicationChecklist'
import { PIPELINE_STAGE_LABELS } from '../../types/application'
import type { Application } from '../../types/application'

interface ApplicationRowProps {
  application: Application
  universityName: string
  programName: string | null
  createdAt: string
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * One application row plus its (toggleable) inline document checklist
 * (E26; Journey J19).
 *
 * The dashboard renders one ``ApplicationRow`` per row in
 * ``StudentDashboardPage``. The checklist fetch only fires when the
 * row is expanded so a dashboard with many applications does not
 * trigger N requests on load.
 */
export default function ApplicationRow({
  application,
  universityName,
  programName,
  createdAt,
}: ApplicationRowProps) {
  const [expanded, setExpanded] = useState(false)
  const { items, loading, error, reload } = useApplicationChecklist(
    expanded ? application.id : null,
  )

  function toggle() {
    setExpanded((prev) => !prev)
  }

  return (
    <Fragment>
      <tr
        className="application-table__row"
        data-testid={`application-row-${application.id}`}
      >
        <td className="application-table__cell">{universityName}</td>
        <td className="application-table__cell">{programName}</td>
        <td className="application-table__cell">
          <span
            className="application-table__stage"
            data-testid={`application-stage-${application.id}`}
          >
            {PIPELINE_STAGE_LABELS[application.stage]}
          </span>
        </td>
        <td className="application-table__cell">{formatDate(createdAt)}</td>
        <td className="application-table__cell application-table__cell--actions">
          <button
            type="button"
            className="application-table__checklist-toggle"
            data-testid={`application-checklist-toggle-${application.id}`}
            aria-expanded={expanded}
            aria-controls={`application-checklist-${application.id}`}
            onClick={toggle}
          >
            {expanded ? 'Hide checklist' : 'View checklist'}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr
          className="application-table__checklist-row"
          data-testid={`application-checklist-row-${application.id}`}
        >
          <td
            colSpan={5}
            className="application-table__checklist-cell"
            id={`application-checklist-${application.id}`}
          >
            <ChecklistView
              applicationId={application.id}
              items={items}
              loading={loading}
              error={error}
              onReload={reload}
            />
          </td>
        </tr>
      ) : null}
    </Fragment>
  )
}