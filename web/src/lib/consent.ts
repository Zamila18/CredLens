/** Small helpers for showing consent records. */

/** "credit_readiness_assessment" -> "Credit readiness assessment". */
export function humanize(value: string | null | undefined): string {
  if (!value) return '—'
  const words = value.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** "purchases|deliveries|payments" or ["purchases", ...] -> ["purchases", ...]. */
export function categoriesOf(value: string | string[] | null | undefined): string[] {
  if (!value) return []
  return Array.isArray(value) ? value : value.split('|').filter(Boolean)
}
