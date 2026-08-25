import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import BranchesPage from '../pages/BranchesPage'
import BillingStatusPage from '../pages/BillingStatusPage'
import ChecklistTemplatesPage from '../pages/ChecklistTemplatesPage'
import ForgotPasswordPage from '../pages/ForgotPasswordPage'
import HomePage from '../pages/HomePage'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import MasterDataAdminPage from '../pages/MasterDataAdminPage'
import OwnerDashboardPage from '../pages/OwnerDashboardPage'
import ReceptionistIntakePage from '../pages/ReceptionistIntakePage'
import RegisterStudentPage from '../pages/RegisterStudentPage'
import NotFoundPage from '../pages/NotFoundPage'
import ResetPasswordPage from '../pages/ResetPasswordPage'
import StaffPage from '../pages/StaffPage'
import StudentDashboardPage from '../pages/StudentDashboardPage'
import TenantBrandingPage from '../pages/TenantBrandingPage'
import TenantsPage from '../pages/TenantsPage'
import VerifierDashboardPage from '../pages/VerifierDashboardPage'
import VisaProcessorDashboardPage from '../pages/VisaProcessorDashboardPage'
import CounselorDashboardPage from '../pages/CounselorDashboardPage'
import BranchManagerDashboardPage from '../pages/BranchManagerDashboardPage'
import SuperAdminDashboardPage from '../pages/SuperAdminDashboardPage'
import PlanAndUsagePage from '../pages/PlanAndUsagePage'
import ChecklistTemplateAdminRoute from './ChecklistTemplateAdminRoute'
import ConsultancyOwnerRoute from './ConsultancyOwnerRoute'
import CounselorRoute from './CounselorRoute'
import MasterDataAdminRoute from './MasterDataAdminRoute'
import ProtectedRoute, { LOGIN_PATH } from './ProtectedRoute'
import ReceptionistRoute from './ReceptionistRoute'
import StaffManagerRoute from './StaffManagerRoute'
import StudentRoute from './StudentRoute'
import SuperAdminRoute from './SuperAdminRoute'
import VerifierRoute from './VerifierRoute'
import VisaProcessorRoute from './VisaProcessorRoute'
import {
  BILLING_STATUS_PATH,
  CHECKLIST_TEMPLATES_PATH,
  COUNSELOR_DASHBOARD_PATH,
  FORGOT_PASSWORD_PATH,
  LANDING_PATH,
  MASTER_DATA_ADMIN_PATH,
  OWNER_DASHBOARD_PATH,
  PLAN_AND_USAGE_PATH,
  RECEPTIONIST_INTAKE_PATH,
  REGISTER_PATH,
  RESET_PASSWORD_PATH,
  STUDENT_DASHBOARD_PATH,
  TENANT_BRANDING_PATH,
  VERIFIER_DASHBOARD_PATH,
  VISA_DASHBOARD_PATH,
  BRANCH_MANAGER_DASHBOARD_PATH,
  SUPER_ADMIN_DASHBOARD_PATH,
} from './paths'

export function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path={LANDING_PATH} element={<LandingPage />} />
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route path={REGISTER_PATH} element={<RegisterStudentPage />} />
      <Route path={FORGOT_PASSWORD_PATH} element={<ForgotPasswordPage />} />
      <Route path={RESET_PASSWORD_PATH} element={<ResetPasswordPage />} />
<<<<<<< HEAD
      
      {/* Protected routes */}
=======
      <Route path={LANDING_PATH} element={<LandingPage />} />
>>>>>>> origin/main
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="app" element={<HomePage />} />
          <Route element={<SuperAdminRoute />}>
            <Route path="tenants" element={<TenantsPage />} />
            <Route
              path={SUPER_ADMIN_DASHBOARD_PATH.slice(1)}
              element={<SuperAdminDashboardPage />}
            />
            <Route
              path={BILLING_STATUS_PATH.slice(1)}
              element={<BillingStatusPage />}
            />
          </Route>
          <Route element={<ConsultancyOwnerRoute />}>
            <Route path="branches" element={<BranchesPage />} />
            <Route path={TENANT_BRANDING_PATH.slice(1)} element={<TenantBrandingPage />} />
            <Route path={OWNER_DASHBOARD_PATH.slice(1)} element={<OwnerDashboardPage />} />
            <Route path={PLAN_AND_USAGE_PATH.slice(1)} element={<PlanAndUsagePage />} />
          </Route>
          <Route element={<StaffManagerRoute />}>
            <Route path="staff" element={<StaffPage />} />
            <Route
              path={BRANCH_MANAGER_DASHBOARD_PATH.slice(1)}
              element={<BranchManagerDashboardPage />}
            />
          </Route>
          <Route element={<MasterDataAdminRoute />}>
            <Route
              path={MASTER_DATA_ADMIN_PATH.slice(1)}
              element={<MasterDataAdminPage />}
            />
          </Route>
          <Route element={<ChecklistTemplateAdminRoute />}>
            <Route
              path={CHECKLIST_TEMPLATES_PATH.slice(1)}
              element={<ChecklistTemplatesPage />}
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
          <Route element={<VisaProcessorRoute />}>
            <Route path={VISA_DASHBOARD_PATH.slice(1)} element={<VisaProcessorDashboardPage />} />
          </Route>
          <Route element={<ReceptionistRoute />}>
            <Route
              path={RECEPTIONIST_INTAKE_PATH.slice(1)}
              element={<ReceptionistIntakePage />}
            />
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
