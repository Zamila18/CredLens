/**
 * The small line icons drawn in the mockups, copied as SVG so they match exactly.
 * All are decorative (aria-hidden); the text next to them says what they mean.
 */
type IconProps = { size?: number; color?: string; className?: string }

export function LensMark({ size = 30, outer = '#7FB8A6', ring = '#FFFFFF' }: { size?: number; outer?: string; ring?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <circle cx="15" cy="15" r="13" stroke={outer} strokeWidth="2" strokeDasharray="3 3" />
      <circle cx="15" cy="15" r="8.5" stroke={ring} strokeWidth="3" />
      <circle cx="15" cy="15" r="2.5" fill="#E0A44A" />
    </svg>
  )
}

export function InfoIcon({ size = 16, color = '#2B3631', className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.5" aria-hidden="true" className={className}>
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 7.2v4" />
      <circle cx="8" cy="4.9" r=".6" fill={color} />
    </svg>
  )
}

export function LockIcon({ size = 18, color = '#4A524E', className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" aria-hidden="true" className={className}>
      <rect x="3.5" y="8" width="11" height="7.5" rx="1.5" />
      <path d="M6 8V5.8a3 3 0 0 1 6 0V8" />
    </svg>
  )
}

export function CheckIcon({ size = 12, color = '#0B4A3D', className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" stroke={color} strokeWidth="1.8" aria-hidden="true" className={className}>
      <path d="M2.5 6.2l2.2 2.2 4.8-5" />
    </svg>
  )
}

export function ChevronRight({ size = 14, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true" className={className}>
      <path d="M5 3l4 4-4 4" />
    </svg>
  )
}

export function SearchIcon({ size = 16, color = '#55625C' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.5" aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5 14 14" />
    </svg>
  )
}

export function WarnIcon({ size = 20, color = '#5E3403' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.6" aria-hidden="true">
      <path d="M10 3 18 17H2z" />
      <path d="M10 8v4" />
      <circle cx="10" cy="14.6" r=".7" fill={color} />
    </svg>
  )
}
