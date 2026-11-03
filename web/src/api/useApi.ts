/**
 * useApi: load something from the API inside a component.
 *
 *   const { data, error, loading, reload } = useApi<QueueItem[]>('/merchants')
 *
 * - Results are kept in memory per demo user, so the sidebar badge and the queue
 *   page share one download of the queue.
 * - While the API is starting (no answer yet, or 503 "scorer_not_ready"), the call
 *   is retried every few seconds on its own, as the error callout promises.
 * - Pass `null` as the path to skip the call (for example before an id is known).
 * - `{ noCache: true }` asks the API again on every visit. Used for merchant reads:
 *   each profile or score read writes an audit entry, so a saved copy would hide a view.
 */
import { useCallback, useEffect, useState } from 'react'

import { useSession } from '@/app/session-context'
import { ApiError, api } from './client'

type Query = Record<string, string | number | boolean | undefined | null>

/** Errors that go away by themselves once the API has finished starting. */
const RETRY_CODES = new Set(['network', 'scorer_not_ready', 'database_not_ready', 'not_started'])
const RETRY_MS = 5000

type Entry = { data?: unknown; promise?: Promise<unknown> }
const cache = new Map<string, Entry>()

/** "/merchants" + {status: "pending"} -> "/merchants?status=pending" (empty values left out). */
function withQuery(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

/** Forget cached results whose path starts with `prefix`, e.g. after recording a decision. */
export function invalidate(prefix: string) {
  for (const key of [...cache.keys()]) {
    const path = key.slice(key.indexOf('|') + 1)
    if (path.startsWith(prefix)) cache.delete(key)
  }
}

/** Forget every cached answer (on sign-in, sign-out or a change of demo user). */
export function clearApiCache() {
  cache.clear()
}

function toApiError(err: unknown): ApiError {
  return err instanceof ApiError ? err : new ApiError(0, 'network', String(err))
}

type Options = { noCache?: boolean }

export function useApi<T>(path: string | null, query?: Query, options: Options = {}) {
  const { noCache = false } = options
  const { user } = useSession()
  const url = path ? withQuery(path, query) : null
  // Results are cached per demo user: an admin and a viewer may get different answers.
  const key = url ? `${user}|${url}` : null
  const [tick, setTick] = useState(0)
  const [state, setState] = useState<{ key: string | null; data?: T; error?: ApiError }>({ key: null })

  // Already downloaded (by this or another component)? Use it straight away.
  const cached = key && !noCache ? (cache.get(key)?.data as T | undefined) : undefined

  useEffect(() => {
    if (!key || !url) return
    if (cache.get(key)?.data !== undefined) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined

    let entry = cache.get(key)
    if (!entry?.promise) {
      const fresh: Entry = {}
      fresh.promise = api<T>(url).then(
        (data) => {
          // noCache: share only the call in flight (React may mount twice), keep nothing after.
          if (noCache) cache.delete(key)
          else fresh.data = data
          fresh.promise = undefined
          return data
        },
        (err: unknown) => {
          cache.delete(key) // do not keep failures; the next try asks again
          throw err
        },
      )
      cache.set(key, fresh)
      entry = fresh
    }

    entry.promise!.then(
      (data) => {
        if (alive) setState({ key, data: data as T })
      },
      (err: unknown) => {
        if (!alive) return
        const apiError = toApiError(err)
        setState({ key, error: apiError })
        if (RETRY_CODES.has(apiError.code)) timer = setTimeout(() => setTick((t) => t + 1), RETRY_MS)
      },
    )
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [key, url, tick, noCache])

  const reload = useCallback(() => {
    if (key) cache.delete(key)
    setTick((t) => t + 1)
  }, [key])

  const mine = state.key === key ? state : { data: undefined, error: undefined }
  const data = cached ?? mine.data
  const error = data === undefined ? mine.error : undefined
  return { data, error, loading: Boolean(key) && data === undefined && !error, reload }
}
