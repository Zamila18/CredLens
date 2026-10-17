/**
 * ActionCard: one of the four officer actions in the decision form (approved design sheet,
 * section 6). A radio card with an icon, the action and what it means. There is no Approve
 * or Decline anywhere: Accept suggestion, Override: raise, Override: lower, Needs more info.
 */
import type { LucideIcon } from 'lucide-react'
import { ArrowDown, ArrowUp, Check, FileSearch } from 'lucide-react'

import type { OfficerAction } from '@/api/types'
import { cn } from '@/lib/utils'

const LOOK: Record<OfficerAction, { icon: LucideIcon; tile: string; on: string; dot: string }> = {
  accept: { icon: Check, tile: 'bg-mint-2', on: 'border-band-strong bg-mint shadow-[inset_0_0_0_1px_#16845B]', dot: 'bg-mint text-band-strong' },
  override_up: { icon: ArrowUp, tile: 'bg-info-panel', on: 'border-info bg-info-panel shadow-[inset_0_0_0_1px_#2F6FB0]', dot: 'bg-[#DCEAF8] text-info' },
  override_down: { icon: ArrowDown, tile: 'bg-amber-panel', on: 'border-band-review bg-amber-panel shadow-[inset_0_0_0_1px_#B7791F]', dot: 'bg-amber-chip text-amber-text' },
  needs_more_info: { icon: FileSearch, tile: 'bg-peri-panel', on: 'border-band-nmi bg-peri-panel shadow-[inset_0_0_0_1px_#6555A6]', dot: 'bg-peri-chip text-peri-text' },
}

type Props = {
  action: OfficerAction
  label: string
  hint: string
  selected: boolean
  onSelect?: () => void
}

export function ActionCard({ action, label, hint, selected, onSelect }: Props) {
  const look = LOOK[action]
  const Icon = look.icon
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'flex min-h-11 cursor-pointer items-start gap-3 rounded-[12px] border-[1.5px] p-4 text-left font-sans text-ink',
        selected ? look.on : cn('border-card-line hover:border-control-line', look.tile),
      )}
    >
      <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', look.dot)} aria-hidden="true">
        <Icon size={18} strokeWidth={2.2} />
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold">{label}</span>
        <span className="text-[13px] leading-[18px] text-body">{hint}</span>
      </span>
    </button>
  )
}
