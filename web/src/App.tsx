/**
 * All the pages and their addresses (DESIGN_SPEC.md section 1).
 * Every page sits inside the app shell (sidebar + banner).
 */
import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { AppShell } from '@/app/AppShell'
import { RequireRole } from '@/app/RequireRole'
import { SessionProvider } from '@/app/SessionProvider'
import { AuditPage } from '@/pages/AuditPage'
import { ConsentDemoPage } from '@/pages/ConsentDemoPage'
import { ConsentPage } from '@/pages/ConsentPage'
import { DecisionsPage } from '@/pages/DecisionsPage'
import { DevStates } from '@/pages/DevStates'
import { ImportPage } from '@/pages/ImportPage'
import { MerchantPage } from '@/pages/merchant/MerchantPage'
import { ModelCardPage } from '@/pages/model/ModelCardPage'
import { NotFound } from '@/pages/NotFound'
import { QueuePage } from '@/pages/QueuePage'

// The portfolio is the only page with a chart library (Recharts); load it only when opened.
const PortfolioPage = lazy(() => import('@/pages/PortfolioPage').then((m) => ({ default: m.PortfolioPage })))

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<QueuePage />} />
          <Route path="merchants/:merchantId" element={<MerchantPage />} />
          <Route path="decisions" element={<DecisionsPage />} />
          <Route
            path="portfolio"
            element={
              <Suspense fallback={<div className="p-8 text-sm text-muted">Loading the portfolio…</div>}>
                <PortfolioPage />
              </Suspense>
            }
          />
          <Route path="model" element={<ModelCardPage />} />
          <Route path="consent" element={<ConsentPage />} />
          <Route path="demo/consent" element={<ConsentDemoPage />} />
          <Route
            path="audit"
            element={
              <RequireRole roles={['admin']}>
                <AuditPage />
              </RequireRole>
            }
          />
          <Route
            path="admin/import"
            element={
              <RequireRole roles={['admin']}>
                <ImportPage />
              </RequireRole>
            }
          />
          {import.meta.env.DEV && <Route path="dev/states" element={<DevStates />} />}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  )
}
