/**
 * The 10-question form behind "Record new answers" (officers only).
 *
 * - Every item is a whole number from 1 to 5; "Save answers" stays disabled until all
 *   ten are answered. The API checks the same rule again.
 * - Saving replaces the earlier answers (the audit log keeps who saved and when).
 * - The questionnaire never changes the score: the score is not asked again after saving.
 */
import { useState } from 'react'

import { ApiError, api } from '@/api/client'
import type { MerchantProfile, QuestionnaireCreate } from '@/api/types'
import type { Lang } from '@/app/session-context'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Button } from '@/components/ui/button'
import { GROUP_TEXT, pick, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { ITEMS, QUESTION_WORDING_IS_DRAFT, type ItemKey } from './questionnaireItems'

type Summary = NonNullable<MerchantProfile['questionnaire']>
type Answers = Partial<Record<ItemKey, number>>

const SCALE = [1, 2, 3, 4, 5]

export function QuestionnaireForm({
  merchantId,
  lang,
  onSaved,
  onCancel,
}: {
  merchantId: string
  lang: Lang
  onSaved: (summary: Summary) => void
  onCancel: () => void
}) {
  const t = useT()
  const [answers, setAnswers] = useState<Answers>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const answered = ITEMS.filter((item) => answers[item.key] !== undefined).length
  const complete = answered === ITEMS.length

  async function save() {
    if (!complete) return
    setSaving(true)
    setError(null)
    try {
      const summary = await api<Summary>(`/merchants/${encodeURIComponent(merchantId)}/questionnaire`, {
        method: 'POST',
        json: answers as QuestionnaireCreate,
      })
      onSaved(summary)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', String(err)))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 border-t border-line-soft pt-4">
      <div className="flex flex-col gap-1">
        <h3 className="m-0 text-base font-semibold">{t('Record new answers', 'নতুন উত্তর লিখুন')}</h3>
        <p className="m-0 text-[13px] text-muted">
          {t(
            'Ask the merchant each question and pick their answer from 1 to 5. Saving replaces the earlier answers. The score does not change.',
            'মার্চেন্টকে প্রতিটি প্রশ্ন করুন এবং ১ থেকে ৫-এর মধ্যে উত্তর বেছে নিন। রাখলে আগের উত্তর বদলে যায়। স্কোর বদলায় না।',
          )}
        </p>
        {QUESTION_WORDING_IS_DRAFT && (
          <p className="m-0 rounded-lg bg-amber-panel px-3 py-2 text-[13px] text-amber-deep">
            {t(
              'Draft wording: the Bangla still needs a native-speaker review (docs/QUESTIONNAIRE.md).',
              'খসড়া ভাষা: বাংলা এখনও একজন বাংলাভাষী পর্যালোচকের দেখা বাকি (docs/QUESTIONNAIRE.md)।',
            )}
          </p>
        )}
      </div>

      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {ITEMS.map((item, i) => {
          const text = lang === 'bn' && item.bn ? item.bn : item.en
          const low = lang === 'bn' ? item.lowBn : item.low
          const high = lang === 'bn' ? item.highBn : item.high
          return (
            <li key={item.key}>
              <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                <legend className="mb-2 p-0 text-sm">
                  <span className="mr-2 font-mono text-xs text-muted-2">
                    {i + 1} · {pick(GROUP_TEXT[item.group], lang)}
                  </span>
                  <span className={cn(lang === 'bn' && item.bn && 'font-bn')}>{text}</span>
                </legend>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn('w-28 text-right text-xs text-muted @max-lg:hidden', lang === 'bn' && 'font-bn')}>{low}</span>
                  <div role="radiogroup" aria-label={text} className="flex gap-1.5">
                    {SCALE.map((n) => {
                      const on = answers[item.key] === n
                      return (
                        <button
                          key={n}
                          type="button"
                          role="radio"
                          aria-checked={on}
                          aria-label={`${n}${n === 1 ? ` (${low})` : n === 5 ? ` (${high})` : ''}`}
                          onClick={() => setAnswers((prev) => ({ ...prev, [item.key]: n }))}
                          className={cn(
                            'size-11 cursor-pointer rounded-[10px] border-[1.5px] font-mono text-sm font-semibold',
                            on ? 'border-slate bg-slate text-white' : 'border-control-line bg-card text-ink hover:border-[#9FAAA3]',
                          )}
                        >
                          {n}
                        </button>
                      )
                    })}
                  </div>
                  <span className={cn('text-xs text-muted @max-lg:hidden', lang === 'bn' && 'font-bn')}>{high}</span>
                </div>
              </fieldset>
            </li>
          )
        })}
      </ol>

      {error && <ErrorCallout error={error} />}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-mono text-xs text-muted-2 tabular">
          {t(`${answered} of ${ITEMS.length} answered`, `${ITEMS.length}টির মধ্যে ${answered}টির উত্তর হয়েছে`)}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel} disabled={saving}>
            {t('Cancel', 'বাতিল')}
          </Button>
          <Button onClick={save} disabled={!complete || saving}>
            {saving ? t('Saving…', 'রাখা হচ্ছে…') : t('Save answers', 'উত্তর রাখুন')}
          </Button>
        </div>
      </div>
    </div>
  )
}
