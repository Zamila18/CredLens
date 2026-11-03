/**
 * The stored assessments of a merchant (GET/POST /merchants/{id}/assessments).
 *
 * "Run assessment" stores what the model and the company's range policy say today, with the
 * exact inputs, so it can be shown again and recomputed ("Check by recomputing"). A person
 * decides; this panel approves nothing.
 */
import { useState } from 'react'

import { api } from '@/api/client'
import type { AssessmentOut, VerifyOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Section } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime, taka } from '@/lib/format'
import { useLang, useT } from '@/lib/i18n'

export function AssessmentPanel({ merchantId, canRun, className }: { merchantId: string; canRun: boolean; className?: string }) {
  const t = useT()
  const lang = useLang()
  const base = `/merchants/${encodeURIComponent(merchantId)}/assessments`
  const list = useApi<AssessmentOut[]>(base, undefined, { noCache: true })
  const run = useSubmit<AssessmentOut>()
  const [checks, setChecks] = useState<Record<string, VerifyOut>>({})
  const current = list.data?.[0]

  const start = async () => {
    const done = await run.submit(() => api<AssessmentOut>(base, { method: 'POST' }))
    if (done) list.reload()
  }
  const verify = async (id: string) => {
    const res = await api<VerifyOut>(`${base}/${encodeURIComponent(id)}/verify`)
    setChecks({ ...checks, [id]: res })
  }

  return (
    <Section className={className} title={t('Stored assessments', 'সংরক্ষিত মূল্যায়ন')}>
      <div className="flex flex-col gap-3 text-[14px] text-body">
        <p className="m-0">
          {t(
            'Each run stores the score, the reasons, the evidence it rested on and the range (or why there is none). Decision support only: a person decides.',
            'প্রতিবার চালালে স্কোর, কারণ, ভিত্তি করা তথ্য এবং পরিসীমা (বা কেন নেই) সংরক্ষিত হয়। শুধু সিদ্ধান্তে সহায়তা: সিদ্ধান্ত একজন মানুষের।',
          )}
        </p>
        {canRun && (
          <div>
            <Button size="sm" disabled={run.pending} onClick={() => void start()}>
              {run.pending ? t('Running…', 'চলছে…') : t('Run assessment now', 'এখন মূল্যায়ন চালান')}
            </Button>
          </div>
        )}
        {run.error && <ErrorCallout error={run.error} />}
        {list.error && <ErrorCallout error={list.error} />}
        {list.data && list.data.length === 0 && <p className="m-0 text-muted-2">{t('No assessment has been stored yet.', 'এখনও কোনো মূল্যায়ন সংরক্ষিত হয়নি।')}</p>}
        {current && <p className="m-0 rounded-[10px] bg-ground p-3 text-ink">{lang === 'bn' ? current.summary_bn : current.summary_en}</p>}
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {(list.data ?? []).map((a) => (
            <li key={a.assessment_id} className="rounded-[10px] border border-line p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">
                  {t(`Score ${a.score} · ${a.band}`, `স্কোর ${a.score} · ${a.band}`)}
                  {a.status !== 'current' && <span className="ml-2 font-normal text-muted-2">{t('(earlier)', '(আগের)')}</span>}
                </span>
                <span className="text-[13px] text-muted-2">{fmtBdTime(a.assessed_at)}</span>
              </div>
              <div className="mt-1 text-[13.5px]">
                {a.range_available && a.range_min_bdt != null && a.range_max_bdt != null
                  ? t(`Range ${taka(a.range_min_bdt)} – ${taka(a.range_max_bdt)}`, `পরিসীমা ${taka(a.range_min_bdt)} – ${taka(a.range_max_bdt)}`)
                  : t('No range', 'পরিসীমা নেই')}
                {' · '}
                {t(`model ${a.model_version}`, `মডেল ${a.model_version}`)}
              </div>
              {a.range_reasoning.length > 0 && (
                <ul className="m-0 mt-1 list-disc pl-5 text-[13px] text-muted-2">
                  {a.range_reasoning.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <Button size="sm" variant="ghost" onClick={() => void verify(a.assessment_id)}>
                  {t('Check by recomputing', 'পুনরায় হিসাব করে মেলান')}
                </Button>
                {checks[a.assessment_id] && (
                  <span className="text-[13px] font-semibold text-lens-dark">
                    {checks[a.assessment_id].probability_matches && checks[a.assessment_id].range_matches
                      ? t('Identical when recomputed.', 'পুনরায় হিসাবে হুবহু মিলেছে।')
                      : t('Does not match: tell the platform team.', 'মেলেনি: প্ল্যাটফর্ম দলকে জানান।')}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  )
}
