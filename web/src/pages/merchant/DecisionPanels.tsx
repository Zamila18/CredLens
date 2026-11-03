/**
 * "Your decision" and this merchant's decision history (approved design: 03-merchant-desktop.png).
 *
 * - Officers only. Admin and viewer see a read-only note naming who they are, and the history.
 * - "Record decision" stays disabled until an action is chosen and, for an override, the
 *   written reason is not blank (whitespace does not count). The API checks the same rules
 *   again, including the 2,000-character limit (`api.reason_max_chars`).
 * - The score, band, coverage and model version are taken by the server, not from this form.
 * - Decisions are append-only: to change course, the officer records a new one.
 * - No form when nothing is waiting for a decision (the API would answer no_pending_loan).
 */
import { useState } from 'react'

import { ApiError, api } from '@/api/client'
import type { Decision, OfficerAction, Score } from '@/api/types'
import { invalidate } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { ActionCard } from '@/components/ActionCard'
import { ActionChip } from '@/components/ActionChip'
import { BandChip, Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Section } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { ACTIONS, isOverride } from '@/lib/actions'
import { fmtBdTime, pct } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT, type T } from '@/lib/i18n'

/** The API's limit on a written reason (config `api.reason_max_chars`). */
export const REASON_MAX = 2000

function reasonPlaceholder(action: OfficerAction | null, t: T) {
  if (isOverride(action)) return t('What did you see that the score did not?', 'স্কোরে যা ধরা পড়েনি, আপনি কী দেখলেন?')
  if (action === 'needs_more_info') return t('What is missing? e.g. Waiting for delivery records.', 'কী নেই? যেমন: ডেলিভারির রেকর্ডের অপেক্ষা।')
  return t('Add a note about your decision (optional).', 'আপনার সিদ্ধান্ত নিয়ে একটি নোট লিখুন (ঐচ্ছিক)।')
}

export function DecisionForm({ merchantId, score, onRecorded }: { merchantId: string; score: Score; onRecorded: () => void }) {
  const t = useT()
  const lang = useLang()
  const [action, setAction] = useState<OfficerAction | null>(null)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [recorded, setRecorded] = useState<Decision | null>(null)

  const override = isOverride(action)
  const blank = reason.trim() === ''
  const tooLong = reason.trim().length > REASON_MAX
  const disabled = !action || (override && blank) || tooLong || saving

  async function record() {
    if (!action) return
    setSaving(true)
    setError(null)
    try {
      const decision = await api<Decision>(`/merchants/${encodeURIComponent(merchantId)}/decision`, {
        method: 'POST',
        json: { officer_action: action, reason_text: blank ? null : reason.trim() },
      })
      setRecorded(decision)
      // The queue status, the decision log and this merchant's history have changed.
      invalidate('/merchants')
      invalidate('/decisions')
      onRecorded()
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', String(err)))
    } finally {
      setSaving(false)
    }
  }

  function again() {
    setRecorded(null)
    setAction(null)
    setReason('')
    setError(null)
  }

  return (
    <Section
      id="decision"
      title={t('Your decision', 'আপনার সিদ্ধান্ত')}
      answer={t('The score suggests. You decide, and the record keeps why.', 'স্কোর পরামর্শ দেয়। সিদ্ধান্ত আপনার, আর রেকর্ডে কারণ থাকে।')}
    >
      {recorded ? (
        <div className="flex flex-col gap-2.5 rounded-[12px] border border-mint-line bg-mint-2 p-4" role="status">
          <span className="text-base font-semibold text-lens-dark">
            {t('Recorded:', 'রাখা হয়েছে:')} {pick(ACTION_TEXT[recorded.officer_action].label, lang)}
          </span>
          <span className="text-[15px]">{recorded.reason_text ? `“${recorded.reason_text}”` : t('No note added.', 'কোনো নোট নেই।')}</span>
          <span className="text-[13px] text-body">
            {recorded.officer_id} · {fmtBdTime(recorded.decided_at)} {t('(Bangladesh time)', '(বাংলাদেশ সময়)')} · {t('score shown', 'দেখানো স্কোর')}{' '}
            {recorded.score_shown}
            {recorded.band_shown && ` · ${recorded.band_shown}`}
            {recorded.coverage_shown != null && ` · ${pct(recorded.coverage_shown)} ${t('coverage', 'কভারেজ')}`} · {t('model', 'মডেল')}{' '}
            <span className="font-mono">{recorded.model_version}</span>
          </span>
          <span className="text-[13px] text-body">
            {t('Decisions are append-only. To change course, record a new decision.', 'সিদ্ধান্ত শুধু যোগ করা যায়, বদলানো যায় না। মত বদলালে নতুন সিদ্ধান্ত রাখুন।')}
          </span>
          <Button variant="outline" size="sm" className="self-start" onClick={again}>
            {t('Record another decision', 'আরেকটি সিদ্ধান্ত রাখুন')}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div role="radiogroup" aria-label={t('Action', 'পদক্ষেপ')} className="grid gap-3 @lg:grid-cols-2 @4xl:grid-cols-4">
            {ACTIONS.map((a) => (
              <ActionCard
                key={a.value}
                action={a.value}
                label={pick(ACTION_TEXT[a.value].label, lang)}
                hint={pick(ACTION_TEXT[a.value].hint, lang)}
                selected={action === a.value}
                onSelect={() => setAction(a.value)}
              />
            ))}
          </div>
          <label className="flex flex-col gap-1.5 text-sm font-semibold text-ink">
            <span>
              {override ? t('Written reason (required for an override)', 'লিখিত কারণ (পরিবর্তনের জন্য বাধ্যতামূলক)') : t('Note (optional)', 'নোট (ঐচ্ছিক)')}
            </span>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder(action, t)}
              aria-required={override}
              aria-invalid={tooLong || undefined}
              className="resize-y rounded-[10px] border border-control-line p-3 font-sans text-[15px] font-normal text-ink"
            />
            <span className={tooLong ? 'self-end text-xs font-medium text-error' : 'self-end text-xs font-normal text-muted-2'}>
              {reason.trim().length.toLocaleString('en-US')} / {REASON_MAX.toLocaleString('en-US')}
            </span>
          </label>
          {override && blank && (
            <span className="text-[13px] text-amber-text">
              {t('An override needs a written reason before it can be recorded.', 'পরিবর্তন রাখার আগে লিখিত কারণ দিতে হবে।')}
            </span>
          )}
          {tooLong && (
            <span className="text-[13px] text-error">
              {t(`A reason may be at most ${REASON_MAX.toLocaleString('en-US')} characters.`, `কারণ সর্বোচ্চ ${REASON_MAX.toLocaleString('en-US')} অক্ষরের হতে পারে।`)}
            </span>
          )}
          {error && <ErrorCallout error={error} />}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[13px] text-body">
              {t('Saved with score', 'সাথে রাখা হবে: স্কোর')} {score.score} · {score.band} · {pct(score.coverage)} {t('coverage', 'কভারেজ')} ·{' '}
              {t('model', 'মডেল')} <span className="font-mono">{score.model_version}</span>
            </span>
            <Button size="lg" disabled={disabled} onClick={record}>
              {saving ? t('Recording…', 'রাখা হচ্ছে…') : t('Record decision', 'সিদ্ধান্ত রাখুন')}
            </Button>
          </div>
        </div>
      )}
    </Section>
  )
}

/** For admin and viewer: who may record, and why the form is not here. Names the actual demo user. */
export function ReadOnlyDecisionNote() {
  const { user } = useSession()
  const t = useT()
  return (
    <Section id="decision" title={t('Your decision', 'আপনার সিদ্ধান্ত')}>
      <p className="m-0 text-[15px] text-body">
        {t('Only officers record decisions. You are using the demo role', 'শুধু কর্মকর্তারা সিদ্ধান্ত রাখেন। আপনি ডেমো ভূমিকায় আছেন')}{' '}
        <span className="font-mono font-semibold text-ink">{user}</span>
        {t(', so this page is read-only. Switch the demo role to an officer to record one.', ', তাই এই পাতা শুধু দেখার জন্য। সিদ্ধান্ত রাখতে ডেমো ভূমিকা কর্মকর্তা করুন।')}
      </p>
    </Section>
  )
}

/** When the merchant's latest loan already has an outcome: nothing is waiting for a decision. */
export function NoPendingLoanNote() {
  const t = useT()
  return (
    <Section id="decision" title={t('Your decision', 'আপনার সিদ্ধান্ত')}>
      <p className="m-0 text-[15px] text-body">
        {t(
          'No loan is waiting for a decision on this merchant: the latest loan already has an outcome. The form appears when a new loan is waiting.',
          'এই মার্চেন্টের কোনো ঋণ সিদ্ধান্তের অপেক্ষায় নেই: সর্বশেষ ঋণের ফলাফল জানা। নতুন ঋণ অপেক্ষায় থাকলে ফর্ম দেখা যাবে।',
        )}
      </p>
    </Section>
  )
}

/** Every decision recorded on this merchant, newest first, with what was on screen then. */
export function DecisionHistory({ decisions, error }: { decisions?: Decision[]; error?: ApiError }) {
  const t = useT()
  const rows = [...(decisions ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at))
  return (
    <Section
      id="history"
      title={t('Decisions on this merchant', 'এই মার্চেন্টের সিদ্ধান্ত')}
      aside={
        <Chip tone="strong" className="px-3 py-1 text-[13px]">
          {t('Append-only', 'শুধু যোগ করা যায়')}
        </Chip>
      }
    >
      {error ? (
        <ErrorCallout error={error} />
      ) : !decisions ? (
        <p className="m-0 text-sm text-body">{t('Loading…', 'আসছে…')}</p>
      ) : rows.length === 0 ? (
        <div className="rounded-[12px] border border-line bg-ground px-4 py-3">
          <p className="m-0 text-[15px] font-semibold text-ink">{t('No decisions recorded yet.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি।')}</p>
          <p className="m-0 text-[13px] text-body">
            {t('Decisions are append-only. To change course, record a new decision.', 'সিদ্ধান্ত শুধু যোগ করা যায়। মত বদলালে নতুন সিদ্ধান্ত রাখুন।')}
          </p>
        </div>
      ) : (
        <ol className="m-0 flex list-none flex-col p-0">
          {rows.map((d) => (
            <li key={d.decision_id} className="flex flex-col gap-1.5 border-t border-line py-3 first:border-t-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="text-sm text-ink-2 tabular">
                  {fmtBdTime(d.decided_at)} <span className="text-muted-2">{t('BD time', 'বাংলাদেশ সময়')}</span>
                </span>
                <ActionChip action={d.officer_action} />
                <span className="text-sm text-ink tabular">
                  {t('score', 'স্কোর')} <b>{d.score_shown}</b>
                </span>
                {d.band_shown && <BandChip band={d.band_shown} />}
                {d.coverage_shown != null && (
                  <span className="text-sm text-body tabular">
                    {pct(d.coverage_shown)} {t('coverage', 'কভারেজ')}
                  </span>
                )}
              </div>
              <span className="text-[15px] leading-[22px] text-ink">
                {d.reason_text ??
                  (d.officer_action === 'accept' ? t('No note. Accepting needs none.', 'কোনো নোট নেই। মেনে নিতে নোট লাগে না।') : t('No note.', 'কোনো নোট নেই।'))}
              </span>
              <span className="text-xs text-muted-2">
                {d.officer_id} · <span className="font-mono">{d.model_version}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </Section>
  )
}
