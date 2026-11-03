/**
 * The CredLens mark and wordmark, used by the public site, the demo entry and the app shell.
 * The mark is the favicon's lens (public/favicon.svg): an evidence ring around a lens,
 * with the amber point that stands for the one thing an officer looks at.
 */
import { cn } from '@/lib/utils'

export function LensMark({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" fill="none" aria-hidden="true" className={cn('shrink-0', className)}>
      <circle cx="15" cy="15" r="15" fill="#0F1D19" />
      <circle cx="15" cy="15" r="12" stroke="#7FB8A6" strokeWidth="2" strokeDasharray="3 3" />
      <circle cx="15" cy="15" r="7.5" stroke="#FFFFFF" strokeWidth="3" />
      <circle cx="15" cy="15" r="2.5" fill="#E0A44A" />
    </svg>
  )
}

/** Mark and name. `tone="light"` is for dark backgrounds. */
export function Wordmark({ size = 'md', tone = 'dark', className }: { size?: 'sm' | 'md' | 'lg'; tone?: 'dark' | 'light'; className?: string }) {
  const mark = size === 'lg' ? 36 : size === 'sm' ? 24 : 30
  const text = size === 'lg' ? 'text-[26px]' : size === 'sm' ? 'text-lg' : 'text-[22px]'
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LensMark size={mark} />
      <span className={cn('font-display leading-none font-bold tracking-[-0.02em]', text, tone === 'light' ? 'text-white' : 'text-ink')}>CredLens</span>
    </span>
  )
}
