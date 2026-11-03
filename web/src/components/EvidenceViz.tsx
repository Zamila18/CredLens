/**
 * Small charts of where evidence comes from, used by the dashboard and the merchant
 * workspace. Plain HTML, no chart library: a stacked bar of records per source, a legend
 * with the exact counts (the colour is never the only signal), and a one-hue meter.
 *
 * Source colours (src/lib/sources.ts) follow the validated categorical order (dataviz reference palette,
 * slots 1 to 4, checked for colour-blind separation). They are fixed per source, never
 * by rank, so a source keeps its colour on every screen. "Generated" is neutral grey.
 */
import { count } from '@/lib/format'
import { pick, useLang } from '@/lib/i18n'
import { SOURCE_COLOR, SOURCE_ORDER, SOURCE_WORDS } from '@/lib/sources'
import { cn } from '@/lib/utils'

const ordered = (counts: Record<string, number>) => SOURCE_ORDER.filter((s) => (counts[s] ?? 0) > 0).map((s) => [s, counts[s]] as const)

/** A 100% stacked bar of records per source, with a 2px gap between segments. */
export function SourceBar({ counts, label, className }: { counts: Record<string, number>; label: string; className?: string }) {
  const lang = useLang()
  const parts = ordered(counts)
  const total = parts.reduce((sum, [, n]) => sum + n, 0)
  const words = parts.map(([s, n]) => `${pick(SOURCE_WORDS[s], lang)} ${count(n)}`).join(', ')
  if (!total) return <div className={cn('h-2.5 rounded-full bg-track', className)} role="img" aria-label={`${label}: 0`} />
  return (
    <div className={cn('flex h-2.5 gap-[2px] overflow-hidden rounded-full', className)} role="img" aria-label={`${label}: ${words}`}>
      {parts.map(([s, n]) => (
        <span key={s} title={`${pick(SOURCE_WORDS[s], lang)}: ${count(n)}`} className="h-full first:rounded-l-full last:rounded-r-full" style={{ width: `${(n / total) * 100}%`, background: SOURCE_COLOR[s], minWidth: 4 }} />
      ))}
    </div>
  )
}

/** The legend: a swatch, the source's name and its exact count. Only sources present. */
export function SourceLegend({ counts, className }: { counts: Record<string, number>; className?: string }) {
  const lang = useLang()
  const parts = ordered(counts)
  if (!parts.length) return null
  return (
    <ul className={cn('m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-[13px] text-body', className)}>
      {parts.map(([s, n]) => (
        <li key={s} className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-[3px]" style={{ background: SOURCE_COLOR[s] }} />
          {pick(SOURCE_WORDS[s], lang)}
          <span className="font-semibold text-ink tabular">{count(n)}</span>
        </li>
      ))}
    </ul>
  )
}

/** One-hue meter: how many of a whole have something, with the numbers written out. */
export function Meter({ label, value, total, note }: { label: string; value: number; total: number; note?: string }) {
  const share = total ? value / total : 0
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-[14px]">
        <span className="text-ink">{label}</span>
        <span className="text-body tabular">
          <span className="font-semibold text-ink">{count(value)}</span> / {count(total)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-track" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={value}>
        <div className="h-full rounded-full bg-lens" style={{ width: `${share * 100}%`, minWidth: value ? 4 : 0 }} />
      </div>
      {note && <span className="text-[12.5px] text-muted-2">{note}</span>}
    </div>
  )
}
