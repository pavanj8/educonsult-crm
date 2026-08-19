import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import HomePage from '../pages/HomePage'
import LoginPage from '../pages/LoginPage'
import NotFoundPage from '../pages/NotFoundPage'
import TenantsPage from '../pages/TenantsPage'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import SuperAdminRoute from './SuperAdminRoute'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route element={<SuperAdminRoute />}>
            <Route path="tenants" element={<TenantsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
