/**
 * All the pages and their addresses.
 * - Public: `/` (landing page), How it works, Sources, Trust, `/login`, `/register`.
 * - Workspace: everything under `/app`, inside the app shell. The menu shows each role only
 *   what it may open; RequireRole guards the address and the API enforces it again.
 * - Addresses from before Oct 31 (`/merchants/…`, `/field/…`) redirect to `/app/…`.
 */
import { Navigate, Route, Routes, useLocation } from 'react-router'

import type { ReactNode } from 'react'

import type { Role } from '@/api/types'
import { AppShell } from '@/app/AppShell'
import { RequireRole } from '@/app/RequireRole'
import { SessionProvider } from '@/app/SessionProvider'
import { ApplicationsPage } from '@/pages/ApplicationsPage'
import { AuditPage } from '@/pages/AuditPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { DecisionsPage } from '@/pages/DecisionsPage'
import { DirectoryPage } from '@/pages/DirectoryPage'
import { ImportBatchPage, ImportsPage } from '@/pages/ImportsPage'
import { NotFound } from '@/pages/NotFound'
import { SettingsPage } from '@/pages/SettingsPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { SetupPasswordPage } from '@/pages/auth/SetupPasswordPage'
import { ApplicationTask } from '@/pages/field/ApplicationTask'
import { FieldHome } from '@/pages/field/FieldHome'
import { DailySheetPage } from '@/pages/fsr/DailySheetPage'
import { MyShopsPage } from '@/pages/fsr/MyShopsPage'
import { RangePolicyPage } from '@/pages/org/RangePolicyPage'
import { SubmissionsPage } from '@/pages/org/SubmissionsPage'
import { ImportTask } from '@/pages/field/ImportTask'
import { ReceiptTask } from '@/pages/field/ReceiptTask'
import { RecordsTask } from '@/pages/field/RecordsTask'
import { ShopTasks } from '@/pages/field/ShopTasks'
import { VisitTask } from '@/pages/field/VisitTask'
import { MerchantPage } from '@/pages/merchant/MerchantPage'
import { NewRegistrationPage } from '@/pages/merchants/NewRegistrationPage'
import { RegistrationPage } from '@/pages/merchants/RegistrationPage'
import { RegistrationsPage } from '@/pages/merchants/RegistrationsPage'
import { ModelCardPage } from '@/pages/model/ModelCardPage'
import { AssignmentsPage } from '@/pages/org/AssignmentsPage'
import { CompanyPage } from '@/pages/org/CompanyPage'
import { InvitationsPage } from '@/pages/org/InvitationsPage'
import { PeoplePage } from '@/pages/org/PeoplePage'
import { PlatformPage } from '@/pages/platform/PlatformPage'
import { QualityPage } from '@/pages/quality/QualityPage'
import { HowItWorksPage } from '@/pages/public/HowItWorksPage'
import { LandingPage } from '@/pages/public/LandingPage'
import { PublicLayout } from '@/pages/public/PublicLayout'
import { SourcesPage } from '@/pages/public/SourcesPage'
import { TrustPage } from '@/pages/public/TrustPage'
import { NewSourcePage } from '@/pages/sources/NewSourcePage'
import { SourceDetailPage } from '@/pages/sources/SourceDetailPage'
import { SourcesPage as DataSourcesPage } from '@/pages/sources/SourcesPage'

const OFFICER: Role[] = ['credit_officer']
const FIELD: Role[] = ['credit_officer', 'fsr']

/** The first part of every workspace address used before the workspace moved to /app. */
const OLD_ADDRESSES = new Set(['field', 'merchants', 'decisions', 'model', 'audit'])

/** An old address goes to its new home; anything else is a public "page not found". */
function OldAddressOrNotFound() {
  const { pathname, search } = useLocation()
  if (OLD_ADDRESSES.has(pathname.split('/')[1] ?? '')) {
    return <Navigate to={`/app${pathname}${search}`} replace />
  }
  return (
    <PublicLayout>
      <NotFound />
    </PublicLayout>
  )
}

function guard(roles: Role[], page: ReactNode, owner = false) {
  return (
    <RequireRole roles={roles} owner={owner}>
      {page}
    </RequireRole>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route index element={<LandingPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="setup-password" element={<SetupPasswordPage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="trust" element={<TrustPage />} />
        <Route path="app" element={<AppShell />}>
          <Route index element={guard(['credit_officer', 'auditor'], <DashboardPage />)} />
          <Route path="platform" element={guard(['platform_admin'], <PlatformPage />)} />
          <Route path="team" element={guard(OFFICER, <PeoplePage />)} />
          <Route path="invitations" element={guard(OFFICER, <InvitationsPage />, true)} />
          <Route path="company" element={guard(OFFICER, <CompanyPage />)} />
          <Route path="assignments" element={guard(OFFICER, <AssignmentsPage />)} />
          <Route path="registrations" element={guard(OFFICER, <RegistrationsPage />)} />
          <Route path="registrations/new" element={guard(OFFICER, <NewRegistrationPage />)} />
          <Route path="registrations/:regId" element={guard(OFFICER, <RegistrationPage />)} />
          <Route path="merchants" element={guard(['credit_officer', 'auditor'], <DirectoryPage />)} />
          <Route path="merchants/:merchantId" element={guard(['credit_officer', 'auditor'], <MerchantPage />)} />
          <Route path="applications" element={guard(['credit_officer', 'auditor'], <ApplicationsPage />)} />
          <Route path="decisions" element={guard(['credit_officer', 'auditor'], <DecisionsPage />)} />
          <Route path="imports" element={guard(OFFICER, <ImportsPage />)} />
          <Route path="imports/:batchId" element={guard(OFFICER, <ImportBatchPage />)} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="sources" element={guard(OFFICER, <DataSourcesPage />)} />
          <Route path="sources/new" element={guard(OFFICER, <NewSourcePage />)} />
          <Route path="sources/:connectionId" element={guard(OFFICER, <SourceDetailPage />)} />
          <Route path="quality" element={guard(['credit_officer', 'auditor'], <QualityPage />)} />
          <Route path="shops" element={guard(['fsr'], <MyShopsPage />)} />
          <Route path="shops/:merchantId/daily" element={guard(['fsr'], <DailySheetPage />)} />
          <Route path="submissions" element={guard(['credit_officer', 'auditor'], <SubmissionsPage />)} />
          <Route path="range-policy" element={guard(OFFICER, <RangePolicyPage />)} />
          <Route path="field" element={guard(FIELD, <FieldHome />)} />
          <Route path="field/shops/:merchantId" element={guard(FIELD, <ShopTasks />)} />
          <Route path="field/shops/:merchantId/records" element={guard(FIELD, <RecordsTask />)} />
          <Route path="field/shops/:merchantId/receipt" element={guard(FIELD, <ReceiptTask />)} />
          <Route path="field/shops/:merchantId/import" element={guard(FIELD, <ImportTask />)} />
          <Route path="field/shops/:merchantId/visit" element={guard(FIELD, <VisitTask />)} />
          <Route path="field/shops/:merchantId/application" element={guard(FIELD, <ApplicationTask />)} />
          <Route path="model" element={guard(['credit_officer', 'auditor'], <ModelCardPage />)} />
          <Route path="audit" element={guard(['credit_officer', 'auditor'], <AuditPage />)} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<OldAddressOrNotFound />} />
      </Routes>
    </SessionProvider>
  )
}
