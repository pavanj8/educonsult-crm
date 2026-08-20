import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import BranchesPage from '../pages/BranchesPage'
import CounselorDashboardPage from '../pages/CounselorDashboardPage'
import HomePage from '../pages/HomePage'
import LoginPage from '../pages/LoginPage'
import RegisterStudentPage from '../pages/RegisterStudentPage'
import NotFoundPage from '../pages/NotFoundPage'
import StaffPage from '../pages/StaffPage'
import StudentDashboardPage from '../pages/StudentDashboardPage'
import TenantsPage from '../pages/TenantsPage'
import ConsultancyOwnerRoute from './ConsultancyOwnerRoute'
import CounselorRoute from './CounselorRoute'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import StaffManagerRoute from './StaffManagerRoute'
import StudentRoute from './StudentRoute'
import SuperAdminRoute from './SuperAdminRoute'
import { REGISTER_PATH, STUDENT_DASHBOARD_PATH } from './paths'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route path={REGISTER_PATH} element={<RegisterStudentPage />} />
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
<<<<<<< HEAD
          <Route element={<CounselorRoute />}>
            <Route path="counselor/queue" element={<CounselorDashboardPage />} />
=======
          <Route element={<StudentRoute />}>
            <Route path={STUDENT_DASHBOARD_PATH.slice(1)} element={<StudentDashboardPage />} />
>>>>>>> origin/main
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
