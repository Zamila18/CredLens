/**
 * State boxes (approved design: 11-interface-states-desktop.png): ErrorCallout for an API
 * answer that says no, LoadingState and EmptyState. Every error code in docs/API_NOTES.md
 * has a message in src/api/errors.ts.
 *
 * Tone: a missing consent, a role that may not open a page or an unknown address are
 * neutral (blue-grey), never a red alarm; red is only for a real failure (the API is not
 * answering, or a server error). The technical code stays small, under a human sentence.
 */
import type { LucideIcon } from 'lucide-react'
import { FileQuestion, Info, Lock, Search, TriangleAlert } from 'lucide-react'

import type { ApiError } from '@/api/client'
import { describeError } from '@/api/errors'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

type Props = {
  error: Pick<ApiError, 'status' | 'code' | 'message'>
  className?: string
}

function look(error: Props['error']): { icon: LucideIcon; failure: boolean } {
  if (error.status === 0 || error.code === 'network' || error.status >= 500) return { icon: TriangleAlert, failure: error.code !== 'scorer_not_ready' && error.code !== 'database_not_ready' && error.code !== 'not_started' }
  if (error.code.startsWith('consent') || error.code === 'role_not_allowed' || error.code === 'rows_not_shown') return { icon: Lock, failure: false }
  if (error.status === 404) return { icon: FileQuestion, failure: false }
  return { icon: Info, failure: false }
}

export function ErrorCallout({ error, className }: Props) {
  const lang = useLang()
  const copy = describeError(error, lang)
  const { icon: Icon, failure } = look(error)
  const pill = error.status === 0 ? (lang === 'bn' ? 'সংযোগে সমস্যা' : 'Connection error') : String(error.status)
  return (
    <div
      role="alert"
      className={cn(
        'flex gap-4 rounded-card border p-4 sm:p-5',
        failure ? 'border-[#F0C7C7] border-l-4 border-l-error bg-error-panel' : 'border-card-line bg-card',
        className,
      )}
    >
      <span
        className={cn('flex size-14 shrink-0 items-center justify-center rounded-full', failure ? 'bg-[#FBE3E3] text-error' : 'bg-info-panel text-ink-2')}
        aria-hidden="true"
      >
        <Icon size={26} strokeWidth={1.7} />
      </span>
      <div className="flex min-w-0 flex-col gap-1.5">
        <span className={cn('self-start rounded-md px-2 py-0.5 text-[13px] font-semibold', failure ? 'bg-[#FBE3E3] text-error' : 'bg-info-panel text-info')}>{pill}</span>
        <span className="font-display text-lg font-semibold text-ink">{copy.title}</span>
        <span className="text-[15px] text-body">{copy.text}</span>
        {copy.useApiMessage && error.message && <span className="text-[15px] text-body">{error.message}</span>}
        <span className="self-start rounded-md bg-ground px-2 py-0.5 font-mono text-xs text-ink-2">{error.code}</span>
      </div>
    </div>
  )
}

/** "Loading the queue…" with a quiet spinner and placeholder cards. */
export function LoadingState({ title, text, className }: { title: string; text?: string; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-card border border-card-line bg-card p-5', className)} role="status" aria-live="polite">
      <span className="font-display text-lg font-semibold text-ink">{title}</span>
      {text && <span className="text-[15px] text-body">{text}</span>}
      <span className="size-6 animate-spin rounded-full border-[3px] border-mint border-t-band-strong motion-reduce:animate-none" aria-hidden="true" />
      <div className="grid gap-3 sm:grid-cols-3" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 rounded-[12px] border border-line p-3">
            <span className="size-10 rounded-[8px] bg-line-soft" />
            <span className="flex flex-1 flex-col gap-1.5">
              <span className="h-2.5 w-4/5 rounded bg-line-soft" />
              <span className="h-2.5 w-3/5 rounded bg-line-soft" />
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** "No merchants match these filters." */
export function EmptyState({ title, text, className }: { title: string; text?: string; className?: string }) {
  return (
    <div className={cn('flex flex-col items-center gap-2 rounded-card border border-card-line bg-card px-5 py-8 text-center', className)}>
      <Search size={36} strokeWidth={1.5} className="text-ink-2" aria-hidden="true" />
      <span className="font-display text-lg font-semibold text-ink">{title}</span>
      {text && <span className="text-[15px] text-body">{text}</span>}
    </div>
  )
}
