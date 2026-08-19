import { Outlet } from 'react-router-dom'

import NotificationBell from '../components/notifications/NotificationBell'

export default function AppLayout() {
  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>EduConsult CRM</h1>
        <NotificationBell />
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
