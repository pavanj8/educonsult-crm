import { useBranches } from '../hooks/useBranches'

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

export default function BranchesPage() {
  const { branches, loading, error } = useBranches()

  return (
    <div className="branches-page" data-testid="branches-page">
      <header className="branches-page__header">
        <h2>Branches</h2>
        <p className="branches-page__subtitle">Manage branches across your consultancy.</p>
      </header>

      <section className="branches-page__section" aria-labelledby="branch-list-heading">
        <h3 id="branch-list-heading">All branches</h3>
        {loading && <p className="branches-page__status">Loading branches…</p>}
        {error && (
          <p className="branches-page__status branches-page__status--error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && branches.length === 0 && (
          <p className="branches-page__status">No branches yet.</p>
        )}
        {!loading && !error && branches.length > 0 && (
          <div className="branch-table-wrapper">
            <table className="branch-table" data-testid="branch-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">City</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {branches.map((branch) => (
                  <tr key={branch.id} data-testid={`branch-row-${branch.id}`}>
                    <td>{branch.name}</td>
                    <td>{branch.city}</td>
                    <td>{formatDate(branch.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
