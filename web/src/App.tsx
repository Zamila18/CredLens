/**
 * All the pages and their addresses (DESIGN_SPEC.md section 1).
 * Every page sits inside the app shell (sidebar + banner).
 */
import { Route, Routes } from 'react-router'

import { AppShell } from '@/app/AppShell'
import { RequireRole } from '@/app/RequireRole'
import { SessionProvider } from '@/app/SessionProvider'
import { DevStates } from '@/pages/DevStates'
import { NotFound, Placeholder } from '@/pages/Placeholder'

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Placeholder title="Review queue" part="Part 2" mockup="Main.dc.html" />} />
          <Route path="merchants/:merchantId" element={<Placeholder title="Merchant" part="Part 3" mockup="Merchant.dc.html" />} />
          <Route path="decisions" element={<Placeholder title="Decision log" part="Part 4" mockup="Decisions.dc.html" />} />
          <Route path="portfolio" element={<Placeholder title="Portfolio" part="Part 4" mockup="Portfolio.dc.html" />} />
          <Route path="model" element={<Placeholder title="Model card" part="Part 4" mockup="ModelCard.dc.html" />} />
          <Route path="consent" element={<Placeholder title="Consent" part="Part 4" mockup="Consent.dc.html" />} />
          <Route path="demo/consent" element={<Placeholder title="Mock consent page" part="Part 4" mockup="ConsentMobile.dc.html" />} />
          <Route
            path="audit"
            element={
              <RequireRole roles={['admin']}>
                <Placeholder title="Audit log" part="Part 4" mockup="Audit.dc.html" />
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
