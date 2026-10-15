/**
 * The frame around every page: sidebar on the left, banner on top, page below.
 * The row wraps, so on a phone the sidebar sits above the page.
 */
import { Outlet } from 'react-router'

import { Banner } from './Banner'
import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-wrap bg-ground font-sans text-ink">
      <div className="flex-[1_1_248px] bg-night">
        <Sidebar />
      </div>
      <main className="flex min-w-0 flex-[999_1_560px] flex-col">
        <Banner />
        <Outlet />
      </main>
    </div>
  )
}
