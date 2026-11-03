/**
 * A small labelled status (provenance of a record, assessment freshness, application or
 * loan). Text always says the state; the colour and the dot only repeat it. The longer
 * explanation is the tag's tooltip and its accessible description.
 */
import type { StatusWords, Tone } from '@/lib/statuses'
import { pick, useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const TONES: Record<Tone, { chip: string; dot: string }> = {
  neutral: { chip: 'bg-neutral-chip text-neutral-text', dot: 'bg-[#7b8aa0]' },
  strong: { chip: 'bg-strong-chip text-lens-dark', dot: 'bg-band-strong' },
  amber: { chip: 'bg-amber-chip text-amber-text', dot: 'bg-amber' },
  peri: { chip: 'bg-peri-chip text-peri-text', dot: 'bg-band-nmi' },
  info: { chip: 'bg-info-panel text-[#245C93]', dot: 'bg-info' },
}

export function StatusTag({ status, className }: { status: StatusWords | undefined; className?: string }) {
  const lang = useLang()
  if (!status) return null
  const tone = TONES[status.tone]
  return (
    <span
      title={pick(status.help, lang)}
      className={cn(
        'inline-flex max-w-full items-center gap-1.5 rounded-md px-2 py-0.5 text-xs leading-[18px] font-semibold',
        tone.chip,
        className,
      )}
    >
      <span className={cn('size-1.5 shrink-0 rounded-full', tone.dot)} aria-hidden="true" />
      <span className="min-w-0 truncate">{pick(status, lang)}</span>
      <span className="sr-only">. {pick(status.help, lang)}</span>
    </span>
  )
}
