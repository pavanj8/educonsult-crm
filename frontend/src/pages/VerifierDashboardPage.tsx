import ApproveAction from '../components/documents/ApproveAction'
import RejectAction from '../components/documents/RejectAction'
import { useVerifierQueue } from '../hooks/useVerifierQueue'

function formatUploadedAt(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

/**
 * Document verifier dashboard — the pending-document queue view (E28; Journey
 * J21). Lists documents awaiting verification for the signed-in verifier's
 * tenant, with loading / error / empty states. The per-document approve/reject
 * actions land in sibling tickets (E29 #181 approve, E30 #185 reject).
 */
export default function VerifierDashboardPage() {
  const { documents, total, loading, error, reload, reject, approve } = useVerifierQueue()

  return (
    <section className="verifier-dashboard" aria-labelledby="verifier-dashboard-heading">
      <header className="verifier-dashboard__header">
        <h1 id="verifier-dashboard-heading">Document verifier queue</h1>
        <button type="button" onClick={() => void reload()} disabled={loading}>
          Refresh
        </button>
      </header>

      {loading ? (
        <p role="status" aria-live="polite" data-testid="verifier-queue-loading">
          Loading pending documents…
        </p>
      ) : error ? (
        <p role="alert" data-testid="verifier-queue-error">
          {error}
        </p>
      ) : documents.length === 0 ? (
        <p data-testid="verifier-queue-empty">No documents are pending verification.</p>
      ) : (
        <>
          <p data-testid="verifier-queue-count">
            {total} document{total === 1 ? '' : 's'} pending verification
          </p>
          <table className="verifier-queue-table" data-testid="verifier-queue-table">
            <caption className="sr-only">Documents pending verification</caption>
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Type</th>
                <th scope="col">Uploaded</th>
                <th scope="col">Application</th>
                <th scope="col">Student</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} data-testid={`verifier-queue-row-${doc.id}`}>
                  <td>{doc.original_filename}</td>
                  <td>{doc.content_type}</td>
                  <td>{formatUploadedAt(doc.uploaded_at)}</td>
                  <td>#{doc.application_id}</td>
                  <td>#{doc.student_id}</td>
                  <td>
                    <ApproveAction
                      documentId={doc.id}
                      documentLabel={doc.original_filename}
                      onApprove={approve}
                    />
                    <RejectAction
                      documentId={doc.id}
                      documentLabel={doc.original_filename}
                      onReject={reject}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
