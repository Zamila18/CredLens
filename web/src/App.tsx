/**
 * Part 0 placeholder: checks that the browser can reach the API through the
 * /api proxy and shows the banner from GET /health. Part 1 replaces this with
 * the app shell (sidebar, banner, role switch) and the real pages.
 */
import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router'

import { ApiError, api } from '@/api/client'
import type { Health } from '@/api/types'
import { Button } from '@/components/ui/button'

function SetupCheck() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    api<Health>('/health', { signal: controller.signal })
      .then((h) => {
        setHealth(h)
        setError(null)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(`${err.message} (${err.code})`)
      })
    return () => controller.abort()
  }, [attempt])

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="m-0 text-[30px] leading-9 font-semibold tracking-[-0.01em]">CredLens setup check</h1>
      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
        <span className="text-xs font-semibold tracking-[.06em] text-muted uppercase">GET /health</span>
        {health && (
          <>
            <p className="m-0 text-[15px]">{health.banner}</p>
            <p className="m-0 font-mono text-xs text-muted-2 tabular">data_mode {health.data_mode}</p>
          </>
        )}
        {error && <p className="m-0 text-sm text-rust">{error}</p>}
        {!health && !error && <p className="m-0 text-sm text-muted">Asking the API…</p>}
        <div>
          <Button variant="outline" size="sm" onClick={() => setAttempt((n) => n + 1)}>
            Ask again
          </Button>
        </div>
      </section>
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<SetupCheck />} />
    </Routes>
  )
}
