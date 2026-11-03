/** Data helpers shared by the Field Mode screens (kept apart from components for fast refresh). */
import { invalidate, useApi } from '@/api/useApi'
import type { DemoSettings, WorkflowStatus } from '@/api/types'

export function useDemoSettings() {
  return useApi<DemoSettings>('/demo/settings')
}

/** The shop's workflow status. Read fresh on every visit (the read is audited). */
export function useWorkflow(merchantId: string | undefined) {
  return useApi<WorkflowStatus>(merchantId ? `/merchants/${encodeURIComponent(merchantId)}/workflow` : null, undefined, { noCache: true })
}

/** After a save: forget what the screens read about this shop, so they ask again. */
export function forgetShop(merchantId: string) {
  invalidate(`/merchants/${encodeURIComponent(merchantId)}`)
  invalidate('/field/shops')
  invalidate('/merchants')
  invalidate('/search/merchants')
}

/** Turn a typed amount ("9,500", "৳ 12000") into a number; null when it is not one. */
export function parseAmount(text: string): number | null {
  const clean = text.replace(/[৳,\s]/g, '')
  if (!clean) return null
  const value = Number(clean)
  return Number.isFinite(value) ? value : null
}
