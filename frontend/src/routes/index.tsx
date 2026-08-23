import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import BranchesPage from '../pages/BranchesPage'
import ForgotPasswordPage from '../pages/ForgotPasswordPage'
import HomePage from '../pages/HomePage'
import LoginPage from '../pages/LoginPage'
import MasterDataAdminPage from '../pages/MasterDataAdminPage'
import RegisterStudentPage from '../pages/RegisterStudentPage'
import NotFoundPage from '../pages/NotFoundPage'
import ResetPasswordPage from '../pages/ResetPasswordPage'
import StaffPage from '../pages/StaffPage'
import StudentDashboardPage from '../pages/StudentDashboardPage'
import TenantBrandingPage from '../pages/TenantBrandingPage'
import TenantsPage from '../pages/TenantsPage'
import VerifierDashboardPage from '../pages/VerifierDashboardPage'
import CounselorDashboardPage from '../pages/CounselorDashboardPage'
import ConsultancyOwnerRoute from './ConsultancyOwnerRoute'
import CounselorRoute from './CounselorRoute'
import MasterDataAdminRoute from './MasterDataAdminRoute'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import StaffManagerRoute from './StaffManagerRoute'
import StudentRoute from './StudentRoute'
import SuperAdminRoute from './SuperAdminRoute'
import VerifierRoute from './VerifierRoute'
import {
  COUNSELOR_DASHBOARD_PATH,
  FORGOT_PASSWORD_PATH,
  MASTER_DATA_ADMIN_PATH,
  REGISTER_PATH,
  RESET_PASSWORD_PATH,
  STUDENT_DASHBOARD_PATH,
  TENANT_BRANDING_PATH,
  VERIFIER_DASHBOARD_PATH,
} from './paths'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route path={REGISTER_PATH} element={<RegisterStudentPage />} />
      <Route path={FORGOT_PASSWORD_PATH} element={<ForgotPasswordPage />} />
      <Route path={RESET_PASSWORD_PATH} element={<ResetPasswordPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route element={<SuperAdminRoute />}>
            <Route path="tenants" element={<TenantsPage />} />
          </Route>
          <Route element={<ConsultancyOwnerRoute />}>
            <Route path="branches" element={<BranchesPage />} />
            <Route path={TENANT_BRANDING_PATH.slice(1)} element={<TenantBrandingPage />} />
          </Route>
          <Route element={<StaffManagerRoute />}>
            <Route path="staff" element={<StaffPage />} />
          </Route>
          <Route element={<MasterDataAdminRoute />}>
            <Route
              path={MASTER_DATA_ADMIN_PATH.slice(1)}
              element={<MasterDataAdminPage />}
            />
          </Route>
          <Route element={<StudentRoute />}>
            <Route path={STUDENT_DASHBOARD_PATH.slice(1)} element={<StudentDashboardPage />} />
          </Route>
          <Route element={<VerifierRoute />}>
            <Route path={VERIFIER_DASHBOARD_PATH.slice(1)} element={<VerifierDashboardPage />} />
          </Route>
          <Route element={<CounselorRoute />}>
            <Route path={COUNSELOR_DASHBOARD_PATH.slice(1)} element={<CounselorDashboardPage />} />
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
