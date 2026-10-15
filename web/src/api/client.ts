/**
 * The one place the dashboard talks to the API. The dashboard never talks to the
 * database.
 *
 * - Every call goes to `/api/...`. In development Vite forwards it to the FastAPI
 *   server on :8000 (see vite.config.ts); on the server Nginx does the same.
 * - Every call except GET /health carries the `X-Demo-Token` header with the demo
 *   user picked in the sidebar. This is a demo role switch, not a login.
 * - Every error becomes an ApiError with the API's `code` (for example
 *   "consent_required"), so pages can show the matching message.
 */
import type { DemoUser } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

let demoUser: DemoUser = 'officer-1'

/** Called by the role switch; later calls use the new X-Demo-Token. */
export function setDemoUser(user: DemoUser) {
  demoUser = user
}

/** An error from the API (or from the network), with the API's error code. */
export class ApiError extends Error {
  /** HTTP status; 0 when the API could not be reached at all. */
  readonly status: number
  /** The API's code, e.g. "consent_required"; "validation" for a 422; "network" when unreachable. */
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST'
  /** Query string values; undefined and empty values are left out. */
  query?: Record<string, string | number | boolean | undefined | null>
  /** A JSON body (sent as application/json). */
  json?: unknown
  /** A raw text body, e.g. a CSV file, with its content type. */
  body?: { content: Blob | string; contentType: string }
  signal?: AbortSignal
}

/** Read the `{"detail": {"code", "message"}}` error shape, or FastAPI's 422 list. */
async function toApiError(res: Response): Promise<ApiError> {
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    // Not JSON (for example a proxy error page). Fall through to a generic error.
  }
  const detail = (data as { detail?: unknown } | null)?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const d = detail as { code?: string; message?: string }
    return new ApiError(res.status, d.code ?? `http_${res.status}`, d.message ?? res.statusText)
  }
  if (res.status === 422 && Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined
    return new ApiError(422, 'validation', first?.msg ?? 'The request was refused.')
  }
  return new ApiError(res.status, `http_${res.status}`, res.statusText || 'Request failed.')
}

/** Call the API and return the parsed JSON response. Throws ApiError. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (path !== '/health') headers['X-Demo-Token'] = demoUser

  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  } else if (options.body) {
    headers['Content-Type'] = options.body.contentType
    body = options.body.content
  }

  let res: Response
  try {
    res = await fetch(url, { method: options.method ?? 'GET', headers, body, signal: options.signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'network', 'The API could not be reached.')
  }
  // Vite's proxy answers 502/504 when the API is not running (it is still starting up, or stopped).
  if (res.status === 502 || res.status === 504) {
    throw new ApiError(0, 'network', 'The API could not be reached.')
  }
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as T
}
