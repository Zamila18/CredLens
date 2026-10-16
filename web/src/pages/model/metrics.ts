/**
 * Reading values out of a model card's `metrics` safely. A key a source does not
 * report comes back undefined, and the page hides that block instead of filling it in.
 */
import type { ModelCard } from '@/api/types'

export type Metrics = ModelCard['metrics']

export function num(m: Metrics, key: string): number | undefined {
  const v = m[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

export function text(m: Metrics, key: string): string | undefined {
  const v = m[key]
  return typeof v === 'string' && v.trim() !== '' ? v : undefined
}

/**
 * A text of the card in the page's language: in Bangla the `<key>_bn` the card writer adds,
 * falling back to the English when a card has no Bangla for it.
 */
export function textIn(m: Metrics, key: string, lang: 'en' | 'bn'): string | undefined {
  return (lang === 'bn' ? text(m, `${key}_bn`) : undefined) ?? text(m, key)
}

/** A list of numbers (for example the calibration bins), or undefined. */
export function numbers(m: Metrics, key: string): number[] | undefined {
  const v = m[key]
  return Array.isArray(v) && v.every((x) => typeof x === 'number') ? (v as number[]) : undefined
}

export function range(m: Metrics, key: string): [number, number] | undefined {
  const v = m[key]
  return Array.isArray(v) && v.length === 2 && v.every((x) => typeof x === 'number') ? [v[0], v[1]] : undefined
}

/** 0.7095 -> "0.710". */
export function auc(v: number): string {
  return v.toFixed(3)
}

/** 0.0427 -> "+0.043"; -0.2377 -> "−0.238". */
export function signed(v: number, digits = 3): string {
  return `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}`
}

/** Position of a value on a bar from `lo` to `hi`, as a percentage clamped to 0–100. */
export function onScale(v: number, lo: number, hi: number): number {
  return Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100))
}
