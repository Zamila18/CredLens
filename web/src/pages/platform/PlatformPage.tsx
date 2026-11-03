/**
 * Companies on the platform (CredLens platform administrators only): head counts, suspend or
 * reactivate a company, and a one-time code for an owner who lost their password. Never a
 * company's merchants, records or documents.
 */
import { useState } from 'react'

import { Field, TextInput } from '@/components/form'

import { api } from '@/api/client'
import type { ConsentTemplateOut, PlatformOrgOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function PlatformPage() {
  const t = useT()
  const orgs = useApi<PlatformOrgOut[]>('/platform/orgs', undefined, { noCache: true })
  const templates = useApi<ConsentTemplateOut[]>('/platform/consent-templates', undefined, { noCache: true })
  const [review, setReview] = useState('')
  const act = useSubmit<{ setup_code?: string; employee?: { full_name: string } }>()
  const [code, setCode] = useState<{ name: string; code: string } | null>(null)

  const run = (path: string, json?: unknown) =>
    void act.submit(() => api(path, { method: 'POST', json })).then((r) => {
      const c = r as { setup_code?: string; employee?: { full_name: string } } | null
      if (c?.setup_code) setCode({ name: c.employee?.full_name ?? '', code: c.setup_code })
      orgs.reload()
      templates.reload()
    })

  return (
    <Page>
      <PageHeader
        title={t('Companies', 'প্রতিষ্ঠানসমূহ')}
        description={t('The companies registered on CredLens. You see head counts only; a company’s merchants and documents stay private to that company.', 'CredLens-এ নিবন্ধিত প্রতিষ্ঠান। আপনি শুধু সংখ্যা দেখেন; প্রতিষ্ঠানের মার্চেন্ট ও নথি সেই প্রতিষ্ঠানেরই থাকে।')}
      />
      {code && (
        <Notice tone="success" title={t(`One-time code for ${code.name}`, `${code.name}-এর একবারের কোড`)}>
          <span className="w-fit rounded-[10px] border border-mint-line bg-white px-3 py-1.5 font-mono text-[20px] font-semibold tracking-[0.08em] text-ink">{code.code}</span>
        </Notice>
      )}
      {orgs.error ? (
        <ErrorCallout error={orgs.error} />
      ) : !orgs.data ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : orgs.data.length === 0 ? (
        <EmptyState title={t('No company has registered yet', 'এখনও কোনো প্রতিষ্ঠান নিবন্ধন করেনি')} text="" />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {orgs.data.map((o) => (
            <li key={o.organization_id} className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-card-line bg-card p-4">
              <span className="flex min-w-0 flex-col">
                <span className="text-[16px] font-semibold text-ink">{o.name}</span>
                <span className="text-[13px] text-muted-2">
                  {[o.legal_name, o.org_type, o.city].filter(Boolean).join(' · ')} · {t('registered', 'নিবন্ধিত')} {fmtDate(o.created_at)}
                </span>
                <span className="text-[13px] text-muted-2">
                  {t(`${o.credit_officers} credit officers · ${o.fsrs} FSRs · ${o.merchants} merchants`, `${o.credit_officers} ক্রেডিট অফিসার · ${o.fsrs} FSR · ${o.merchants} মার্চেন্ট`)}
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <span className={o.status === 'active' ? 'font-semibold text-lens-dark' : 'font-semibold text-error'}>
                  {o.status === 'active' ? t('Active', 'সক্রিয়') : t('Suspended', 'স্থগিত')}
                </span>
                <Button size="sm" variant="outline" disabled={act.pending} onClick={() => run(`/platform/orgs/${o.organization_id}/owner-reset`)}>
                  {t('Owner reset code', 'মালিকের রিসেট কোড')}
                </Button>
                <Button size="sm" variant="ghost" disabled={act.pending} onClick={() => run(`/platform/orgs/${o.organization_id}/status`, { status: o.status === 'active' ? 'suspended' : 'active' })}>
                  {o.status === 'active' ? t('Suspend', 'স্থগিত করুন') : t('Reactivate', 'সক্রিয় করুন')}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {act.error && <ErrorCallout error={act.error} />}
      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
        <h2 className="m-0 text-[18px] font-semibold">{t('Consent document', 'সম্মতিপত্র')}</h2>
        <p className="m-0 text-[14px] text-body">
          {t('Companies can issue the consent form to merchants in production only after you approve it, which needs a record of who reviewed the text (a lawyer in Bangladesh).', 'আপনি অনুমোদন দেওয়ার পরেই কোম্পানিগুলো প্রোডাকশনে মার্চেন্টদের সম্মতিপত্র দিতে পারে; অনুমোদনের জন্য কে লেখাটি পর্যালোচনা করেছেন (বাংলাদেশের আইনজীবী) তার রেকর্ড দরকার।')}
        </p>
        {(templates.data ?? []).map((tpl) => (
          <div key={tpl.version} className="flex flex-col gap-2 rounded-[12px] border border-line p-3">
            <span className="font-semibold text-ink">
              {tpl.version} · {tpl.status}
            </span>
            <span className="text-[13px] text-muted-2">{tpl.note}</span>
            {tpl.legal_review_ref && <span className="text-[13px] text-body">{t('Reviewed by:', 'পর্যালোচক:')} {tpl.legal_review_ref}</span>}
            <Field label={t('Who reviewed it (name, firm, date)', 'কে পর্যালোচনা করেছেন (নাম, প্রতিষ্ঠান, তারিখ)')}>
              <TextInput value={review} onChange={(e) => setReview(e.target.value)} />
            </Field>
            <span className="flex flex-wrap gap-2">
              <Button size="sm" disabled={act.pending || review.trim().length < 8} onClick={() => run(`/platform/consent-templates/${tpl.version}/status`, { status: 'approved', legal_review_ref: review })}>
                {t('Approve', 'অনুমোদন')}
              </Button>
              <Button size="sm" variant="outline" disabled={act.pending} onClick={() => run(`/platform/consent-templates/${tpl.version}/status`, { status: 'draft' })}>
                {t('Back to draft', 'খসড়ায় ফেরত')}
              </Button>
            </span>
          </div>
        ))}
      </section>
    </Page>
  )
}
