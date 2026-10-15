/**
 * All the pages and their addresses (DESIGN_SPEC.md section 1).
 * Every page sits inside the app shell (sidebar + banner).
 */
import { Route, Routes } from 'react-router'

import { AppShell } from '@/app/AppShell'
import { RequireRole } from '@/app/RequireRole'
import { SessionProvider } from '@/app/SessionProvider'
import { AuditPage } from '@/pages/AuditPage'
import { DecisionsPage } from '@/pages/DecisionsPage'
import { DevStates } from '@/pages/DevStates'
import { MerchantPage } from '@/pages/merchant/MerchantPage'
import { NotFound, Placeholder } from '@/pages/Placeholder'
import { QueuePage } from '@/pages/QueuePage'

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<QueuePage />} />
          <Route path="merchants/:merchantId" element={<MerchantPage />} />
          <Route path="decisions" element={<DecisionsPage />} />
          <Route path="portfolio" element={<Placeholder title="Portfolio" part="Part 4" mockup="Portfolio.dc.html" />} />
          <Route path="model" element={<Placeholder title="Model card" part="Part 4" mockup="ModelCard.dc.html" />} />
          <Route path="consent" element={<Placeholder title="Consent" part="Part 4" mockup="Consent.dc.html" />} />
          <Route path="demo/consent" element={<Placeholder title="Mock consent page" part="Part 4" mockup="ConsentMobile.dc.html" />} />
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
                <Placeholder title="Data import" part="Part 4" mockup="Import.dc.html" />
              </RequireRole>
            }
          />
          <Route path="dev/states" element={<DevStates />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  )
}
