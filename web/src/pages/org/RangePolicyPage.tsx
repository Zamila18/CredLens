/**
 * The company's credit-range policy (GET/POST /org/range-policies). Every number is the
 * company's own: nothing is pre-filled as a recommendation. Only the owner Credit Officer
 * writes and approves a policy; an approved policy is retired, never edited, when replaced.
 */
import { useState } from 'react'

import { api } from '@/api/client'
import type { PolicyOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { useSession } from '@/app/session-context'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime } from '@/lib/format'
import { useT } from '@/lib/i18n'

const BANDS = ['Strong', 'Review']

export function RangePolicyPage() {
  const t = useT()
  const session = useSession() as { isOwner?: boolean; me?: { is_owner?: boolean } | null }
  const isOwner = Boolean(session.isOwner ?? session.me?.is_owner)
  const list = useApi<PolicyOut[]>('/org/range-policies', undefined, { noCache: true })
  const save = useSubmit<PolicyOut>()
  const act = useSubmit<PolicyOut>()
  const [f, setF] = useState({ window_days: '', min_verified_months: '', min_purchase_records: '', round_to_bdt: '', cap_at_requested: true, note: '' })
  const [mult, setMult] = useState<Record<string, [string, string]>>({ Strong: ['', ''], Review: ['', ''] })

  const create = async () => {
    const multiples = Object.fromEntries(
      Object.entries(mult)
        .filter(([, v]) => v[0] !== '' && v[1] !== '')
        .map(([k, v]) => [k, [Number(v[0]), Number(v[1])]]),
    )
    const done = await save.submit(() =>
      api<PolicyOut>('/org/range-policies', {
        method: 'POST',
        json: {
          note: f.note || null,
          parameters: {
            window_days: Number(f.window_days),
            min_verified_months: Number(f.min_verified_months),
            min_purchase_records: Number(f.min_purchase_records),
            round_to_bdt: Number(f.round_to_bdt),
            cap_at_requested: f.cap_at_requested,
            multiples_by_band: multiples,
          },
        },
      }),
    )
    if (done) list.reload()
  }
  const move = async (id: string, what: 'approve' | 'retire') => {
    await act.submit(() => api<PolicyOut>(`/org/range-policies/${encodeURIComponent(id)}/${what}`, { method: 'POST' }))
    list.reload()
  }
  const input = 'min-h-10 w-full rounded-[10px] border border-control-line bg-white px-2.5 text-[14px] text-ink'
  const num = (k: 'window_days' | 'min_verified_months' | 'min_purchase_records' | 'round_to_bdt', label: string) => (
    <label className="flex flex-col gap-1 text-[13px] text-body">
      {label}
      <input className={input} inputMode="decimal" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </label>
  )

  return (
    <Page>
      <PageHeader
        title={t('Range policy', 'পরিসীমা-নীতি')}
        description={t(
          'How verified purchases become an indicative credit range. Your company sets every number; until the owner approves a policy, assessments show no range. Sales are not used.',
          'যাচাইকৃত ক্রয় থেকে কীভাবে ইঙ্গিতমূলক ঋণ-পরিসীমা হয়। প্রতিটি সংখ্যা আপনার প্রতিষ্ঠানের; মালিক নীতি অনুমোদন না করা পর্যন্ত মূল্যায়নে পরিসীমা দেখানো হয় না। বিক্রয় ধরা হয় না।',
        )}
      />
      {(save.error || act.error) && <ErrorCallout error={(save.error ?? act.error)!} />}
      {list.error ? (
        <ErrorCallout error={list.error} />
      ) : !list.data ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : list.data.length === 0 ? (
        <EmptyState title={t('No policy yet', 'এখনও কোনো নীতি নেই')} text={t('Write the first policy below.', 'নিচে প্রথম নীতিটি লিখুন।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {list.data.map((p) => (
            <li key={p.policy_id} className="rounded-card border border-card-line bg-card p-4 text-[14px] text-body">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">
                  {t(`Version ${p.version}`, `সংস্করণ ${p.version}`)} · {p.status}
                </span>
                <span className="text-[13px] text-muted-2">{fmtBdTime(p.created_at)}</span>
              </div>
              <pre className="m-0 mt-2 overflow-x-auto rounded-[10px] bg-ground p-3 text-[12.5px]">{JSON.stringify(p.parameters, null, 2)}</pre>
              {isOwner && p.status !== 'retired' && (
                <div className="mt-2 flex gap-2">
                  {p.status === 'draft' && (
                    <Button size="sm" disabled={act.pending} onClick={() => void move(p.policy_id, 'approve')}>
                      {t('Approve', 'অনুমোদন')}
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" disabled={act.pending} onClick={() => void move(p.policy_id, 'retire')}>
                    {t('Retire', 'বন্ধ করুন')}
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {isOwner ? (
        <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-4">
          <h2 className="m-0 text-[17px] font-semibold">{t('Write a new policy (a draft until approved)', 'নতুন নীতি লিখুন (অনুমোদনের আগে খসড়া)')}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {num('window_days', t('Days of purchases looked at', 'কত দিনের ক্রয় দেখা হবে'))}
            {num('min_verified_months', t('Months with verified purchases needed', 'কত মাসের যাচাইকৃত ক্রয় লাগবে'))}
            {num('min_purchase_records', t('Verified purchase records needed', 'কতটি যাচাইকৃত ক্রয় লাগবে'))}
            {num('round_to_bdt', t('Round down to (BDT)', 'নিচের দিকে রাউন্ড (টাকা)'))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {BANDS.map((b) => (
              <fieldset key={b} className="m-0 grid grid-cols-2 gap-2 border-0 p-0">
                <legend className="mb-1 text-[13px] text-body">{t(`Multiples of monthly purchases, band ${b} (low, high)`, `মাসিক ক্রয়ের গুণিতক, ব্যান্ড ${b} (কম, বেশি)`)}</legend>
                {[0, 1].map((i) => (
                  <input
                    key={i}
                    className={input}
                    inputMode="decimal"
                    aria-label={`${b} ${i ? 'high' : 'low'}`}
                    value={mult[b][i]}
                    onChange={(e) => setMult({ ...mult, [b]: i ? [mult[b][0], e.target.value] : [e.target.value, mult[b][1]] })}
                  />
                ))}
              </fieldset>
            ))}
          </div>
          <label className="flex items-center gap-2 text-[14px] text-body">
            <input type="checkbox" checked={f.cap_at_requested} onChange={(e) => setF({ ...f, cap_at_requested: e.target.checked })} />
            {t('Never above the amount the shop asked for', 'দোকানের চাওয়া অঙ্কের বেশি নয়')}
          </label>
          <label className="flex flex-col gap-1 text-[13px] text-body">
            {t('Note (optional)', 'নোট (ঐচ্ছিক)')}
            <input className={input} maxLength={300} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} />
          </label>
          <div>
            <Button disabled={save.pending} onClick={() => void create()}>
              {t('Save as draft', 'খসড়া হিসেবে সংরক্ষণ')}
            </Button>
          </div>
        </section>
      ) : (
        <p className="m-0 text-[14px] text-muted-2">{t('Only the owner Credit Officer can write or approve a policy.', 'শুধু মালিক ক্রেডিট অফিসার নীতি লিখতে বা অনুমোদন করতে পারেন।')}</p>
      )}
    </Page>
  )
}
