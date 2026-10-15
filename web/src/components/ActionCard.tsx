/**
 * ActionCard: one of the four officer actions in the decision form (radio card).
 * There is no Approve or Decline anywhere: the actions are Accept suggestion,
 * Override: raise, Override: lower and Needs more info.
 */
import { cn } from '@/lib/utils'

type Props = {
  label: string
  hint: string
  selected: boolean
  onSelect?: () => void
}

export function ActionCard({ label, hint, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'flex min-h-11 cursor-pointer flex-col items-start gap-0.5 rounded-panel border-[1.5px] px-3.5 py-3 text-left font-sans text-ink',
        selected
          ? 'border-lens bg-strong-selected shadow-[inset_0_0_0_1px_#0E5A4A]'
          : 'border-control-line bg-card hover:border-[#9FAAA3]',
      )}
    >
      <span className="text-sm font-semibold">{label}</span>
      <span className="text-xs text-muted">{hint}</span>
    </button>
  )
}
