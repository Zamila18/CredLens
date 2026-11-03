/**
 * Shop assignments: which sales representative works on which shop
 * (GET/POST /org/assignments). A shop has one SR at a time; an SR sees and works on their
 * assigned shops only (the server enforces it). A shop an SR registers is theirs at once.
 * Moving or unassigning keeps the history.
 */
import { useMemo, useState } from 'react'

import { api } from '@/api/client'
import type { EmployeeOut, ShopAssignmentOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { SearchBox } from '@/components/Filters'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function AssignmentsPage() {
  const t = useT()
  const shops = useApi<ShopAssignmentOut[]>('/org/assignments', undefined, { noCache: true })
  const accounts = useApi<EmployeeOut[]>('/org/employees', undefined, { noCache: true })
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<Record<string, string>>({})
  const save = useSubmit<unknown>()
  const srs = (accounts.data ?? []).filter((a) => a.role === 'fsr' && a.status === 'active')

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (shops.data ?? []).filter((s) => !needle || [s.shop_name, s.merchant_id, s.area, s.fsr_name].some((v) => v?.toLowerCase().includes(needle)))
  }, [shops.data, query])

  const assign = async (merchantId: string) => {
    const sr = chosen[merchantId]
    if (!sr) return
    const done = await save.submit(() => api('/org/assignments', { method: 'POST', json: { merchant_id: merchantId, fsr_user_id: sr } }))
    if (done !== null) {
      shops.reload()
      accounts.reload()
    }
  }
  const unassign = async (merchantId: string) => {
    await save.submit(() => api(`/org/assignments/${encodeURIComponent(merchantId)}/end`, { method: 'POST' }))
    shops.reload()
    accounts.reload()
  }

  const unassigned = (shops.data ?? []).filter((s) => !s.fsr_user_id).length

  return (
    <Page>
      <PageHeader
        title={t('Shop assignments', 'দোকান বণ্টন')}
        description={t(
          'Give each shop to one sales representative. They see and work on their own shops only.',
          'প্রতিটি দোকান একজন সেলস রিপ্রেজেন্টেটিভকে দিন। তাঁরা শুধু নিজের দোকান দেখেন ও কাজ করেন।',
        )}
      />
      {shops.data && srs.length === 0 && accounts.data && (
        <p className="m-0 rounded-[10px] border border-amber-chip bg-amber-panel px-4 py-3 text-[14px] text-amber-text">
          {t('There is no active sales representative yet. Add one on the Team page first.', 'এখনও কোনো সক্রিয় সেলস রিপ্রেজেন্টেটিভ নেই। আগে দল পাতায় একজন যোগ করুন।')}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[14px] text-body">
          {shops.data && t(`${shops.data.length} shops · ${unassigned} without a representative`, `${shops.data.length}টি দোকান · ${unassigned}টি প্রতিনিধি ছাড়া`)}
        </span>
        <SearchBox className="w-[300px] max-w-full" value={query} onChange={setQuery} placeholder={t('Search shop, id, area or SR', 'দোকান, আইডি, এলাকা বা SR খুঁজুন')} />
      </div>
      {save.error && <ErrorCallout error={save.error} />}
      {shops.error ? (
        <ErrorCallout error={shops.error} />
      ) : !shops.data ? (
        <LoadingState title={t('Loading shops…', 'দোকান আসছে…')} />
      ) : shops.data.length === 0 ? (
        <EmptyState title={t('No shops yet', 'এখনও কোনো দোকান নেই')} text={t('Shops appear here when a sales representative registers one in the field.', 'সেলস রিপ্রেজেন্টেটিভ মাঠে দোকান নিবন্ধন করলে এখানে দেখা যাবে।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col overflow-hidden rounded-card border border-card-line bg-card p-0">
          {visible.map((s) => (
            <li key={s.merchant_id} className="grid gap-3 border-t border-line px-4 py-3 first:border-t-0 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)] md:items-center">
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-semibold text-ink">{s.shop_name ?? s.merchant_id}</span>
                <span className="text-[13px] text-muted-2">{[s.merchant_id, s.area, s.district].filter(Boolean).join(' · ')}</span>
              </span>
              <span className="text-[14px]">
                {s.fsr_name ? (
                  <>
                    <span className="font-semibold text-ink">{s.fsr_name}</span>
                    <span className="block text-[12.5px] text-muted-2">{t(`since ${fmtBdTime(s.assigned_at)}`, `${fmtBdTime(s.assigned_at)} থেকে`)}</span>
                  </>
                ) : (
                  <span className="font-semibold text-amber-text">{t('No representative', 'প্রতিনিধি নেই')}</span>
                )}
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <select
                  aria-label={t(`Representative for ${s.shop_name ?? s.merchant_id}`, `${s.shop_name ?? s.merchant_id}-এর প্রতিনিধি`)}
                  value={chosen[s.merchant_id] ?? ''}
                  onChange={(e) => setChosen({ ...chosen, [s.merchant_id]: e.target.value })}
                  className="min-h-10 min-w-0 flex-1 rounded-[10px] border border-control-line bg-white px-2.5 text-[14px] text-ink"
                >
                  <option value="">{t('Choose a representative', 'প্রতিনিধি বাছুন')}</option>
                  {srs.filter((a) => a.user_id !== s.fsr_user_id).map((a) => (
                    <option key={a.user_id} value={a.user_id}>
                      {a.full_name}
                    </option>
                  ))}
                </select>
                <Button size="sm" disabled={!chosen[s.merchant_id] || save.pending} onClick={() => void assign(s.merchant_id)}>
                  {s.fsr_user_id ? t('Move', 'সরান') : t('Assign', 'দিন')}
                </Button>
                {s.fsr_user_id && (
                  <Button size="sm" variant="ghost" disabled={save.pending} onClick={() => void unassign(s.merchant_id)}>
                    {t('Unassign', 'সরিয়ে নিন')}
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
