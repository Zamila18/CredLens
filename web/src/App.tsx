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
import { NotFound } from '@/pages/NotFound'
import { SettingsPage } from '@/pages/SettingsPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { SetupPasswordPage } from '@/pages/auth/SetupPasswordPage'
import { ReceiptReviewPage } from '@/pages/desk/ReceiptReviewPage'
import { ReceiptsPage } from '@/pages/desk/ReceiptsPage'
import { ReportsPage } from '@/pages/desk/ReportsPage'
import { PortalApplyPage } from '@/pages/portal/PortalApplyPage'
import { PortalHomePage } from '@/pages/portal/PortalHomePage'
import { PortalReportsPage } from '@/pages/portal/PortalReportsPage'
import { RangePolicyPage } from '@/pages/org/RangePolicyPage'
import { MerchantPage } from '@/pages/merchant/MerchantPage'
import { NewRegistrationPage } from '@/pages/merchants/NewRegistrationPage'
import { RegistrationPage } from '@/pages/merchants/RegistrationPage'
import { RegistrationsPage } from '@/pages/merchants/RegistrationsPage'
import { ModelCardPage } from '@/pages/model/ModelCardPage'
import { CompanyPage } from '@/pages/org/CompanyPage'
import { InvitationsPage } from '@/pages/org/InvitationsPage'
import { PeoplePage } from '@/pages/org/PeoplePage'
import { PlatformPage } from '@/pages/platform/PlatformPage'
import { HowItWorksPage } from '@/pages/public/HowItWorksPage'
import { LandingPage } from '@/pages/public/LandingPage'
import { PublicLayout } from '@/pages/public/PublicLayout'
import { SourcesPage } from '@/pages/public/SourcesPage'
import { TrustPage } from '@/pages/public/TrustPage'

const OFFICER: Role[] = ['credit_officer']
const DESK: Role[] = ['records_officer']
const MERCHANT: Role[] = ['merchant']

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
          <Route path="registrations" element={guard(OFFICER, <RegistrationsPage />)} />
          <Route path="registrations/new" element={guard(OFFICER, <NewRegistrationPage />)} />
          <Route path="registrations/:regId" element={guard(OFFICER, <RegistrationPage />)} />
          <Route path="merchants" element={guard(['credit_officer', 'auditor'], <DirectoryPage />)} />
          <Route path="merchants/:merchantId" element={guard(['credit_officer', 'auditor'], <MerchantPage />)} />
          <Route path="applications" element={guard(['credit_officer', 'auditor'], <ApplicationsPage />)} />
          <Route path="decisions" element={guard(['credit_officer', 'auditor'], <DecisionsPage />)} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="receipts" element={guard(DESK, <ReceiptsPage />)} />
          <Route path="receipts/:receiptId" element={guard(DESK, <ReceiptReviewPage />)} />
          <Route path="reports" element={guard(DESK, <ReportsPage />)} />
          <Route path="portal" element={guard(MERCHANT, <PortalHomePage />)} />
          <Route path="portal/reports" element={guard(MERCHANT, <PortalReportsPage />)} />
          <Route path="portal/apply" element={guard(MERCHANT, <PortalApplyPage />)} />
          <Route path="range-policy" element={guard(OFFICER, <RangePolicyPage />)} />
          <Route path="model" element={guard(['credit_officer', 'auditor'], <ModelCardPage />)} />
          <Route path="audit" element={guard(['credit_officer', 'auditor'], <AuditPage />)} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<OldAddressOrNotFound />} />
      </Routes>
    </SessionProvider>
  )
}
