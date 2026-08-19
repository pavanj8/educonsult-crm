import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import BranchesPage from '../pages/BranchesPage'
import HomePage from '../pages/HomePage'
import LoginPage from '../pages/LoginPage'
import NotFoundPage from '../pages/NotFoundPage'
import StaffPage from '../pages/StaffPage'
import TenantsPage from '../pages/TenantsPage'
import ConsultancyOwnerRoute from './ConsultancyOwnerRoute'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import StaffManagerRoute from './StaffManagerRoute'
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
          <Route element={<ConsultancyOwnerRoute />}>
            <Route path="branches" element={<BranchesPage />} />
          </Route>
          <Route element={<StaffManagerRoute />}>
            <Route path="staff" element={<StaffPage />} />
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
