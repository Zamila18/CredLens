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

function reasonPlaceholder(action: OfficerAction | null) {
  if (isOverride(action)) return 'What did you see that the score did not?'
  if (action === 'needs_more_info') return 'What is missing? e.g. Waiting for delivery records.'
  return 'Anything the next officer should know'
}

export function DecisionForm({ merchantId, score, onRecorded }: { merchantId: string; score: Score; onRecorded: () => void }) {
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

  const chosen = ACTIONS.find((a) => a.value === recorded?.officer_action)

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">Your decision</h2>
        <p className="m-0 text-[13px] text-muted">The score suggests. You decide, and the record keeps why.</p>
      </div>

      {recorded ? (
        <div className="flex flex-col gap-2.5 rounded-panel bg-strong-selected p-4" role="status">
          <div className="flex items-center gap-2 font-semibold text-lens-dark">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#0B4A3D" strokeWidth="2" aria-hidden="true">
              <path d="M3.5 9.5l3.5 3.5 7.5-8" />
            </svg>
            Recorded: {chosen?.label ?? recorded.officer_action}
          </div>
          <span className="text-sm">{recorded.reason_text ? `“${recorded.reason_text}”` : 'No note added.'}</span>
          <span className="font-mono text-xs text-ink-3">
            {recorded.officer_id} · score shown {recorded.score_shown} · model {recorded.model_version} · audit entry written
          </span>
          <span className="text-[13px] text-ink-3">Decisions are append-only. To change course, record a new decision.</span>
          <Button variant="outline" size="sm" className="self-start" onClick={again}>
            Record another decision
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3.5">
          <div role="radiogroup" aria-label="Action" className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2.5">
            {ACTIONS.map((a) => (
              <ActionCard key={a.value} label={a.label} hint={a.hint} selected={action === a.value} onSelect={() => setAction(a.value)} />
            ))}
          </div>
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">
            <span>{override ? 'Written reason (required for an override)' : 'Note (optional)'}</span>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder(action)}
              aria-required={override}
              className="resize-y rounded-[10px] border-[1.5px] border-button-line p-3 font-sans text-sm font-normal text-ink"
            />
          </label>
          {override && blank && <span className="text-[13px] text-amber-text">An override needs a written reason before it can be recorded.</span>}
          {error && <ErrorCallout error={error} />}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="font-mono text-xs text-muted-2">
              Saved with: score {score.score} · model {score.model_version}
            </span>
            <Button size="lg" disabled={disabled} onClick={record}>
              {saving ? 'Recording…' : 'Record decision'}
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
  return (
    <Card className="flex flex-col gap-1 p-5">
      <h2 className="m-0 text-lg font-semibold">Decision</h2>
      <p className="m-0 text-sm text-ink-3">
        Only officers record decisions. You are signed in as <span className="font-mono">{user}</span>, so this page is
        read-only. Switch the demo role to an officer to record one.
      </p>
    </Card>
  )
}

/** Every decision recorded on this merchant, newest first. */
export function DecisionHistory({ decisions, error }: { decisions?: Decision[]; error?: ApiError }) {
  const rows = [...(decisions ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at))
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">Decisions on this merchant</h2>
        <span className="text-xs text-muted-2">Append-only</span>
      </div>
      {error ? (
        <ErrorCallout error={error} />
      ) : !decisions ? (
        <p className="m-0 text-sm text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="m-0 text-sm text-ink-3">No decisions recorded yet.</p>
      ) : (
        <ol className="m-0 flex list-none flex-col p-0">
          {rows.map((d) => (
            <li key={d.decision_id} className="flex flex-col gap-1.5 border-t border-line-soft py-3">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="font-mono text-[13px] text-ink-3 tabular">{fmtDateTime(d.decided_at, true)}</span>
                <ActionChip action={d.officer_action} />
                <span className="font-mono text-[13px] tabular">score shown {d.score_shown}</span>
              </div>
              <span className="text-sm leading-5">
                {d.reason_text ?? (d.officer_action === 'accept' ? 'No note. Accepting needs none.' : 'No note.')}
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
