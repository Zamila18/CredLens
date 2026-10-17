/**
 * How numbers, money and dates look on screen (DESIGN_SPEC.md section 2).
 * Money: Bangladeshi grouping with the taka sign, ৳1,48,000.
 * Dates: 10 Jan 2025. Times: 11 Jun · 10:42.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2025-01-10" (or a full timestamp) -> "10 Jan 2025". Empty -> "—". */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  if (!y || !m || !d) return iso
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`
}

/** "2026-06-11T10:42:00" -> "11 Jun · 10:42" (or "11 Jun 2026 · 10:42" with the year). */
export function fmtDateTime(iso: string | null | undefined, withYear = false): string {
  if (!iso) return '—'
  const [date, time = ''] = iso.split('T')
  const [y, m, d] = date.split('-')
  if (!y || !m || !d) return iso
  const day = `${Number(d)} ${MONTHS[Number(m) - 1]}${withYear ? ` ${y}` : ''}`
  return time ? `${day} · ${time.slice(0, 5)}` : day
}

/**
 * A UTC time from the API (no zone suffix, e.g. decided_at "2026-10-16T08:35:00") in
 * Bangladesh time (UTC+06:00, no daylight saving): "16 Oct 2026, 14:35".
 */
export function fmtBdTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const utc = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(utc.getTime())) return iso
  const bd = new Date(utc.getTime() + 6 * 60 * 60 * 1000)
  const hh = String(bd.getUTCHours()).padStart(2, '0')
  const mm = String(bd.getUTCMinutes()).padStart(2, '0')
  return `${bd.getUTCDate()} ${MONTHS[bd.getUTCMonth()]} ${bd.getUTCFullYear()}, ${hh}:${mm}`
}

/** The day (YYYY-MM-DD) of a UTC time in Bangladesh time, for grouping decisions by day. */
export function bdDay(iso: string): string {
  const utc = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return new Date(utc.getTime() + 6 * 60 * 60 * 1000).toISOString().slice(0, 10)
}

/** 148000 -> "৳1,48,000" (lakh grouping: last three digits, then pairs). */
export function taka(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return ''
  const sign = n < 0 ? '−' : ''
  const s = String(Math.round(Math.abs(n)))
  const last3 = s.slice(-3)
  const rest = s.slice(0, -3)
  const grouped = rest ? `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${last3}` : last3
  return `${sign}৳${grouped}`
}

/** 0.853 -> "85%" (or with decimals: pct(0.853, 1) -> "85.3%"). Empty -> "—". */
export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return `${(x * 100).toFixed(digits)}%`
}

/** Thousands with commas, for counts: 4178 -> "4,178". */
export function count(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('en-US')
}

/** A score contribution: 3 -> "+3.0 pts", -1.5 -> "−1.5 pts" (a real minus sign). */
export function pts(c: number): string {
  return `${c >= 0 ? '+' : '−'}${Math.abs(c).toFixed(1)} pts`
}
