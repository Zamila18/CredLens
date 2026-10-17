/** ActionChip: an officer action as a pill (approved design: raise blue, lower amber, more info violet). */
import type { OfficerAction } from '@/api/types'
import { ACTION_TEXT, pick, useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const TONE: Record<OfficerAction, string> = {
  accept: 'bg-strong-chip text-lens-dark',
  override_up: 'bg-info-panel text-info',
  override_down: 'bg-amber-chip text-amber-text',
  needs_more_info: 'bg-peri-chip text-peri-text',
}

export function ActionChip({ action }: { action: OfficerAction }) {
  const lang = useLang()
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-[3px] text-xs font-semibold whitespace-nowrap', TONE[action])}>
      {pick(ACTION_TEXT[action].short, lang)}
    </span>
  )
}
