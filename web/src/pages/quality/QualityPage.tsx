/**
 * Data quality (GET /quality/issues, POST /quality/reviews): what in the organisation's
 * records needs a person's attention, why, where to act, and a written review of what was
 * found. Issues are worked out from the records; a review never changes, merges or deletes
 * a record and never changes a score. `?merchant=` keeps one shop's issues.
 */
import { ArrowRight, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { api } from '@/api/client'
import type { QualityIssueOut, QualityReport } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { useSession } from '@/app/session-context'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterChip, FilterSegments } from '@/components/Filters'
import { ChoiceGroup, Field, FormActions, TextArea } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { MetricTile } from '@/components/Workspace'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { actionsOf, describe, GROUPS, ISSUE_STATUS, ORIGIN, OUTCOMES } from './words'

type Status = 'open' | 'reviewed' | 'all'
const NOTE_MIN = 10

function ReviewForm({ issue, onDone }: { issue: QualityIssueOut; onDone: () => void }) {
  const t = useT()
  const lang = useLang()
  const [outcome, setOutcome] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [touched, setTouched] = useState(false)
  const save = useSubmit<QualityIssueOut>()
  const short = note.trim().length < NOTE_MIN
  const submit = async () => {
    setTouched(true)
    if (!outcome || short) return
    const done = await save.submit(() =>
      api<QualityIssueOut>('/quality/reviews', {
        method: 'POST',
        json: { issue_key: issue.issue_key, fingerprint: issue.fingerprint, outcome, note: note.trim() },
      }),
    )
    if (done) onDone()
  }
  return (
    <form noValidate className="flex flex-col gap-4 rounded-panel border border-line bg-ground p-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <Field label={t('What did you find?', 'কী পেলেন?')} required error={touched && !outcome ? t('Choose one.', 'একটি বেছে নিন।') : null}>
        <ChoiceGroup
          name={`outcome-${issue.issue_key}`}
          value={outcome}
          onChange={setOutcome}
          options={issue.outcomes.map((o) => ({ value: o, label: pick(OUTCOMES[o] ?? { en: o, bn: o }, lang), detail: OUTCOMES[o] ? pick(OUTCOMES[o].detail, lang) : undefined }))}
        />
      </Field>
      <Field
        label={t('Note', 'নোট')}
        required
        hint={t('What you checked and with whom, e.g. “Called the owner; two memos that day.”', 'কী ও কার সাথে যাচাই করলেন, যেমন “মালিককে ফোন করেছি; সেদিন দুটি মেমো।”')}
        error={touched && short ? t(`Write at least ${NOTE_MIN} characters.`, `অন্তত ${NOTE_MIN} অক্ষর লিখুন।`) : null}
      >
        <TextArea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </Field>
      {save.error && <ErrorCallout error={save.error} />}
      <FormActions>
        <Button type="submit" disabled={save.pending}>{save.pending ? t('Saving…', 'রাখা হচ্ছে…') : t('Save review', 'পর্যালোচনা রাখুন')}</Button>
        <span className="text-[13px] text-muted-2">{t('No record is changed or deleted.', 'কোনো রেকর্ড বদলায় বা মোছে না।')}</span>
      </FormActions>
    </form>
  )
}

function IssueCard({ issue, staff, onChanged }: { issue: QualityIssueOut; staff: boolean; onChanged: () => void }) {
  const t = useT()
  const lang = useLang()
  const [reviewing, setReviewing] = useState(false)
  const { title, text } = describe(issue, lang)
  const latest = issue.reviews[0]
  const status = issue.status === 'reviewed' && latest?.concern ? ISSUE_STATUS.concern : ISSUE_STATUS[issue.status]
  const canReview = staff && issue.outcomes.length > 0
  return (
    <li className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[12px] font-semibold tracking-[0.07em] text-muted-2 uppercase">{pick(GROUPS[issue.group] ?? { en: issue.group, bn: issue.group }, lang)}</span>
          <span className="text-[17px] font-semibold text-ink">{title}</span>
        </span>
        <StatusTag status={status} />
      </div>
      <p className="m-0 max-w-[78ch] text-[15px] leading-[23px] text-body">{text}</p>

      {issue.evidence.length > 0 && (
        <details className="group rounded-panel border border-line">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[14px] font-semibold text-lens-dark">
            <ChevronDown size={16} aria-hidden="true" className="transition-transform group-open:rotate-180" />
            {t(`The records (${count(issue.evidence.length)})`, `রেকর্ডগুলো (${count(issue.evidence.length)})`)}
          </summary>
          <ul className="m-0 list-none border-t border-line p-0">
            {issue.evidence.map((e) => (
              <li key={e.record_id} className="grid gap-1 border-t border-line px-3 py-2 text-[13.5px] first:border-t-0 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)] sm:gap-3">
                <span className="font-mono text-ink">{e.record_id}</span>
                <span className="text-body">
                  {[e.business_date && fmtDate(e.business_date), e.amount != null && taka(e.amount), e.detail].filter(Boolean).join(' · ') || e.record_type}
                </span>
                <span className="text-muted-2">
                  {e.origin ? pick(ORIGIN[e.origin] ?? { en: e.origin, bn: e.origin }, lang) : t('Origin not recorded', 'উৎস লেখা নেই')}
                  {e.origin_name && ` · ${e.origin_name}`}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {latest && (
        <div className="flex flex-col gap-1 rounded-panel bg-ground px-3 py-2 text-[14px]">
          <span className="font-semibold text-ink">
            {pick(OUTCOMES[latest.outcome] ?? { en: latest.outcome, bn: latest.outcome }, lang)}
            {!latest.current && <span className="ml-2 font-normal text-amber-text">{t('(the records changed after this review)', '(এই পর্যালোচনার পরে রেকর্ড বদলেছে)')}</span>}
          </span>
          <span className="text-body">“{latest.note}”</span>
          <span className="text-[12.5px] text-muted-2">{latest.actor} · {fmtBdTime(latest.decided_at)}{issue.reviews.length > 1 && t(` · ${issue.reviews.length - 1} earlier reviews kept`, ` · আগের ${issue.reviews.length - 1}টি পর্যালোচনা রাখা`)}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {actionsOf(issue).map((a) => (
          <Link key={a.to} to={a.to} className="inline-flex items-center gap-1 text-[14px] font-semibold no-underline">
            {pick(a.label, lang)}
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        ))}
        {canReview && !reviewing && (
          <Button size="sm" variant={issue.status === 'reviewed' ? 'outline' : 'primary'} onClick={() => setReviewing(true)}>
            {issue.status === 'reviewed' ? t('Review again', 'আবার পর্যালোচনা') : t('Record a review', 'পর্যালোচনা লিখুন')}
          </Button>
        )}
        {issue.outcomes.length === 0 && <span className="text-[13px] text-muted-2">{t('Fixed by adding or correcting evidence, not by a review.', 'পর্যালোচনায় নয়, প্রমাণ যোগ বা ঠিক করে সমাধান হয়।')}</span>}
      </div>
      {reviewing && <ReviewForm issue={issue} onDone={() => { setReviewing(false); onChanged() }} />}
    </li>
  )
}

export function QualityPage() {
  const t = useT()
  const lang = useLang()
  const { role } = useSession()
  const [params, setParams] = useSearchParams()
  const merchant = params.get('merchant') ?? undefined
  const [status, setStatus] = useState<Status>('open')
  const [group, setGroup] = useState<string | null>(null)
  const report = useApi<QualityReport>('/quality/issues', { status, merchant_id: merchant }, { noCache: true })
  const staff = ['officer', 'admin', 'org_admin', 'credit_officer'].includes(role)
  const issues = (report.data?.issues ?? []).filter((i) => !group || i.group === group)
  const groupCounts = (report.data?.issues ?? []).reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.group]: (acc[i.group] ?? 0) + 1 }), {})

  return (
    <Page>
      <PageHeader
        title={t('Data quality', 'ডেটার মান')}
        description={t(
          'What in your organisation’s records needs a person’s attention: shops that may be the same, possible duplicates, rows a source or file left out, and gaps in the evidence.',
          'আপনার প্রতিষ্ঠানের রেকর্ডে কী মানুষের মনোযোগ চায়: একই হতে পারে এমন দোকান, সম্ভাব্য দ্বৈত, উৎস বা ফাইলে বাদ পড়া সারি, আর প্রমাণের ফাঁক।',
        )}
      />
      <Notice tone="info" title={t('Reviews never change the records', 'পর্যালোচনা রেকর্ড বদলায় না')}>
        {t(
          'Issues are worked out from the records each time. A review records what a person found, with a note; nothing is merged, deleted or overwritten, and no score changes. If the records change later, the issue opens again.',
          'প্রতিবার রেকর্ড থেকে সমস্যা বের করা হয়। পর্যালোচনায় একজন যা পেলেন তা নোটসহ রাখা হয়; কিছু একত্র, মোছা বা বদলানো হয় না, কোনো স্কোরও বদলায় না। পরে রেকর্ড বদলালে সমস্যাটি আবার খোলে।',
        )}
      </Notice>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricTile label={t('Need attention', 'মনোযোগ দরকার')} value={report.data?.open} tone="attention" hint={t('Not reviewed, or changed since', 'পর্যালোচনা হয়নি, বা পরে বদলেছে')} />
        <MetricTile label={t('Reviewed', 'পর্যালোচিত')} value={report.data?.reviewed} hint={t('With a written note', 'লিখিত নোটসহ')} />
        <MetricTile label={t('Problems confirmed', 'নিশ্চিত সমস্যা')} value={report.data?.concerns} hint={t('Kept and shown on the merchant’s review', 'রাখা থাকে, মার্চেন্টের পর্যালোচনায় দেখায়')} />
      </div>

      <div className="flex flex-col gap-3">
        <FilterSegments<Status>
          label={t('Show', 'দেখান')}
          value={status}
          onChange={setStatus}
          options={[
            { value: 'open', label: t('Needs attention', 'মনোযোগ দরকার') },
            { value: 'reviewed', label: t('Reviewed', 'পর্যালোচিত') },
            { value: 'all', label: t('All', 'সব') },
          ]}
        />
        <div role="group" aria-label={t('Kind of issue', 'সমস্যার ধরন')} className="flex flex-wrap gap-2">
          <FilterChip on={group === null} onClick={() => setGroup(null)}>{t('Every kind', 'সব ধরন')}</FilterChip>
          {Object.keys(GROUPS).map((g) => (
            <FilterChip key={g} on={group === g} onClick={() => setGroup(group === g ? null : g)}>
              {pick(GROUPS[g], lang)}{groupCounts[g] ? ` · ${count(groupCounts[g])}` : ''}
            </FilterChip>
          ))}
        </div>
        {merchant && (
          <Notice
            tone="info"
            title={t(`Showing ${merchant} only`, `শুধু ${merchant} দেখানো হচ্ছে`)}
            action={<button type="button" className="cursor-pointer border-0 bg-transparent p-0 font-sans text-[14px] font-semibold text-lens-dark underline" onClick={() => setParams({})}>{t('Show every shop', 'সব দোকান দেখান')}</button>}
          />
        )}
      </div>

      {report.error ? (
        <ErrorCallout error={report.error} />
      ) : !report.data ? (
        <LoadingState title={t('Checking the records…', 'রেকর্ড যাচাই হচ্ছে…')} />
      ) : issues.length === 0 ? (
        <EmptyState
          title={status === 'reviewed' ? t('No reviewed issues', 'কোনো পর্যালোচিত সমস্যা নেই') : t('Nothing needs attention', 'কিছুই মনোযোগ চায় না')}
          text={t(
            `Checked against records entered in the app, as of ${fmtDate(report.data.as_of)}. The read-only benchmark data is generated and is not checked here.`,
            `${fmtDate(report.data.as_of)} পর্যন্ত অ্যাপে লেখা রেকর্ডের সাথে যাচাই। কেবল-পাঠ্য বেঞ্চমার্ক ডেটা তৈরি করা, এখানে যাচাই হয় না।`,
          )}
        />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {issues.map((i) => <IssueCard key={i.issue_key} issue={i} staff={staff} onChanged={report.reload} />)}
        </ul>
      )}
    </Page>
  )
}
