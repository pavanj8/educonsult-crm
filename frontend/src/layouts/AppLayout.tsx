import { Outlet } from 'react-router-dom'

export default function AppLayout() {
  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>EduConsult CRM</h1>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
