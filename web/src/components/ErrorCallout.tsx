/**
 * ErrorCallout (States.dc.html, "When the API says no"): status pill, title, a plain
 * sentence, and the API's code in mono. Every code in docs/API_NOTES.md has a message
 * in src/api/errors.ts.
 */
import type { ApiError } from '@/api/client'
import { describeError } from '@/api/errors'
import { cn } from '@/lib/utils'

type Props = {
  error: Pick<ApiError, 'status' | 'code' | 'message'>
  className?: string
}

export function ErrorCallout({ error, className }: Props) {
  const copy = describeError(error)
  return (
    <div role="alert" className={cn('flex gap-3.5 rounded-card border border-card-line bg-card p-[18px]', className)}>
      <span className="self-start rounded-md bg-neutral-chip px-2 py-[3px] font-mono text-xs font-semibold whitespace-nowrap text-neutral-text">
        {error.status === 0 ? 'no reply' : error.status}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="font-semibold">{copy.title}</span>
        <span className="text-sm text-ink-3">{copy.text}</span>
        {copy.useApiMessage && error.message && <span className="text-sm text-ink-3">{error.message}</span>}
        <span className="font-mono text-xs text-muted-2">{error.code}</span>
      </div>
    </div>
  )
}
