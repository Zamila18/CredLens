/**
 * "Your decision" (Merchant.dc.html) and this merchant's decision history.
 *
 * - Officers only. Admin and viewer see a read-only note and the history.
 * - "Record decision" stays disabled until an action is chosen and, for an override,
 *   the written reason is not blank. The API checks the same rule again.
 * - The score and model version are taken by the server, not from this form.
 * - Decisions are append-only: to change course, the officer records a new one.
 */
import { useState } from 'react'

import { ApiError, api } from '@/api/client'
import type { Decision, OfficerAction, Score } from '@/api/types'
import { invalidate } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { ActionCard } from '@/components/ActionCard'
import { ActionChip } from '@/components/ActionChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { ACTIONS, isOverride } from '@/lib/actions'
import { fmtDateTime } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT, type T } from '@/lib/i18n'

function reasonPlaceholder(action: OfficerAction | null, t: T) {
  if (isOverride(action)) return t('What did you see that the score did not?', 'স্কোরে যা ধরা পড়েনি, আপনি কী দেখলেন?')
  if (action === 'needs_more_info') {
    return t('What is missing? e.g. Waiting for delivery records.', 'কী নেই? যেমন: ডেলিভারির রেকর্ডের অপেক্ষা।')
  }
  return t('Anything the next officer should know', 'পরের কর্মকর্তার যা জানা দরকার')
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
  const disabled = !action || (override && blank) || saving

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
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">{t('Your decision', 'আপনার সিদ্ধান্ত')}</h2>
        <p className="m-0 text-[13px] text-muted">
          {t('The score suggests. You decide, and the record keeps why.', 'স্কোর পরামর্শ দেয়। সিদ্ধান্ত আপনার, আর রেকর্ডে কারণ থাকে।')}
        </p>
      </div>

      {recorded ? (
        <div className="flex flex-col gap-2.5 rounded-panel bg-strong-selected p-4" role="status">
          <div className="flex items-center gap-2 font-semibold text-lens-dark">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#0B4A3D" strokeWidth="2" aria-hidden="true">
              <path d="M3.5 9.5l3.5 3.5 7.5-8" />
            </svg>
            {t('Recorded:', 'রাখা হয়েছে:')} {pick(ACTION_TEXT[recorded.officer_action].label, lang)}
          </div>
          <span className="text-sm">{recorded.reason_text ? `“${recorded.reason_text}”` : t('No note added.', 'কোনো নোট নেই।')}</span>
          <span className="font-mono text-xs text-ink-3">
            {recorded.officer_id} · {t('score shown', 'দেখানো স্কোর')} {recorded.score_shown} · {t('model', 'মডেল')}{' '}
            {recorded.model_version} · {t('audit entry written', 'অডিটে লেখা হয়েছে')}
          </span>
          <span className="text-[13px] text-ink-3">
            {t(
              'Decisions are append-only. To change course, record a new decision.',
              'সিদ্ধান্ত শুধু যোগ করা যায়, বদলানো যায় না। মত বদলালে নতুন সিদ্ধান্ত রাখুন।',
            )}
          </span>
          <Button variant="outline" size="sm" className="self-start" onClick={again}>
            {t('Record another decision', 'আরেকটি সিদ্ধান্ত রাখুন')}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3.5">
          <div role="radiogroup" aria-label={t('Action', 'পদক্ষেপ')} className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2.5">
            {ACTIONS.map((a) => (
              <ActionCard
                key={a.value}
                label={pick(ACTION_TEXT[a.value].label, lang)}
                hint={pick(ACTION_TEXT[a.value].hint, lang)}
                selected={action === a.value}
                onSelect={() => setAction(a.value)}
              />
            ))}
          </div>
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">
            <span>
              {override
                ? t('Written reason (required for an override)', 'লিখিত কারণ (পরিবর্তনের জন্য বাধ্যতামূলক)')
                : t('Note (optional)', 'নোট (ঐচ্ছিক)')}
            </span>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder(action, t)}
              aria-required={override}
              className="resize-y rounded-[10px] border-[1.5px] border-button-line p-3 font-sans text-sm font-normal text-ink"
            />
          </label>
          {override && blank && (
            <span className="text-[13px] text-amber-text">
              {t('An override needs a written reason before it can be recorded.', 'পরিবর্তন রাখার আগে লিখিত কারণ দিতে হবে।')}
            </span>
          )}
          {error && <ErrorCallout error={error} />}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="font-mono text-xs text-muted-2">
              {t('Saved with: score', 'সাথে রাখা হবে: স্কোর')} {score.score} · {t('model', 'মডেল')} {score.model_version}
            </span>
            <Button size="lg" disabled={disabled} onClick={record}>
              {saving ? t('Recording…', 'রাখা হচ্ছে…') : t('Record decision', 'সিদ্ধান্ত রাখুন')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

/** For admin and viewer: who may record, and why the form is not here. */
export function ReadOnlyDecisionNote() {
  const { user } = useSession()
  const t = useT()
  return (
    <Card className="flex flex-col gap-1 p-5">
      <h2 className="m-0 text-lg font-semibold">{t('Decision', 'সিদ্ধান্ত')}</h2>
      <p className="m-0 text-sm text-ink-3">
        {t('Only officers record decisions. You are signed in as', 'শুধু কর্মকর্তারা সিদ্ধান্ত রাখেন। আপনি আছেন')}{' '}
        <span className="font-mono">{user}</span>
        {t(
          ', so this page is read-only. Switch the demo role to an officer to record one.',
          ' হিসেবে, তাই এই পাতা শুধু দেখার জন্য। সিদ্ধান্ত রাখতে ডেমো ভূমিকা কর্মকর্তা করুন।',
        )}
      </p>
    </Card>
  )
}

/** Every decision recorded on this merchant, newest first. */
export function DecisionHistory({ decisions, error }: { decisions?: Decision[]; error?: ApiError }) {
  const t = useT()
  const rows = [...(decisions ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at))
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Decisions on this merchant', 'এই মার্চেন্টের সিদ্ধান্ত')}</h2>
        <span className="text-xs text-muted-2">{t('Append-only', 'শুধু যোগ করা যায়')}</span>
      </div>
      {error ? (
        <ErrorCallout error={error} />
      ) : !decisions ? (
        <p className="m-0 text-sm text-muted">{t('Loading…', 'আসছে…')}</p>
      ) : rows.length === 0 ? (
        <p className="m-0 text-sm text-ink-3">{t('No decisions recorded yet.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি।')}</p>
      ) : (
        <ol className="m-0 flex list-none flex-col p-0">
          {rows.map((d) => (
            <li key={d.decision_id} className="flex flex-col gap-1.5 border-t border-line-soft py-3">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="font-mono text-[13px] text-ink-3 tabular">{fmtDateTime(d.decided_at, true)}</span>
                <ActionChip action={d.officer_action} />
                <span className="font-mono text-[13px] tabular">
                  {t('score shown', 'দেখানো স্কোর')} {d.score_shown}
                </span>
              </div>
              <span className="text-sm leading-5">
                {d.reason_text ??
                  (d.officer_action === 'accept'
                    ? t('No note. Accepting needs none.', 'কোনো নোট নেই। মেনে নিতে নোট লাগে না।')
                    : t('No note.', 'কোনো নোট নেই।'))}
              </span>
              <span className="font-mono text-xs text-muted-2">
                {d.officer_id} · {d.model_version}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
