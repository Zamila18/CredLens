import { pick, useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { STATUS_WORDS } from './registrationWords'

export function StatusChip({ status }: { status: string }) {
  const lang = useLang()
  const info = STATUS_WORDS[status] ?? { words: [status, status] as [string, string], tone: 'neutral' as const }
  const tone = {
    neutral: 'border-line bg-ground text-ink-2',
    warn: 'border-amber-chip bg-amber-panel text-amber-text',
    good: 'border-mint-line bg-mint text-accent-strong',
    bad: 'border-[#F3D0D0] bg-error-panel text-error',
  }[info.tone]
  return <span className={cn('inline-flex rounded-full border px-2.5 py-0.5 text-[12.5px] font-semibold', tone)}>{pick({ en: info.words[0], bn: info.words[1] }, lang)}</span>
}

