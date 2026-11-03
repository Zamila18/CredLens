/**
 * One save at a time: the state behind every form's submit button.
 *
 * - While a save is running, `submit` does nothing (a double tap cannot send twice; the
 *   server also returns the first record for a repeat, so this complements it).
 * - A refusal keeps the form's values (the form owns them) and gives the ApiError to show.
 * - Success is reported only after the API answered with success.
 */
import { useCallback, useRef, useState } from 'react'

import { ApiError } from './client'

export function useSubmit<T>() {
  const running = useRef(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<T | null>(null)

  const submit = useCallback(async (send: () => Promise<T>): Promise<T | null> => {
    if (running.current) return null
    running.current = true
    setPending(true)
    setError(null)
    try {
      const answer = await send()
      setResult(answer)
      return answer
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'The API could not be reached.'))
      return null
    } finally {
      running.current = false
      setPending(false)
    }
  }, [])

  const reset = useCallback(() => {
    setError(null)
    setResult(null)
  }, [])

  return { submit, pending, error, result, reset }
}
