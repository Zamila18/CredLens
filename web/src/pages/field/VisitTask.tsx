/**
 * Record a shop visit (POST /merchants/{id}/visits): a short structured outcome and an
 * optional note. A visit never changes the score.
 */
import { useState } from 'react'
import { useParams } from 'react-router'

import { api } from '@/api/client'
import type { RecordSaved, VisitCreate } from '@/api/types'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { ChoiceGroup, Field, FormActions, TextArea, TextInput } from '@/components/form'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { OUTCOME_WORDS, wordsFor } from '@/lib/fieldWords'
import { useLang, useT } from '@/lib/i18n'
import { BackLink, DemoLine, FieldPage, SavedNotice, ShopHeader } from './shared'
import { forgetShop, useDemoSettings, useWorkflow } from './fieldData'

export function VisitTask() {
  const t = useT()
  const lang = useLang()
  const { merchantId = '' } = useParams()
  const settings = useDemoSettings()
  const workflow = useWorkflow(merchantId)
  const [date, setDate] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [touched, setTouched] = useState(false)
  const save = useSubmit<RecordSaved>()
  const back = `/app/field/shops/${encodeURIComponent(merchantId)}`

  if (workflow.error || settings.error) return <FieldPage><ErrorCallout error={(workflow.error ?? settings.error)!} /></FieldPage>
  if (!workflow.data || !settings.data) return <FieldPage><LoadingState title={t('Loading…', 'আসছে…')} /></FieldPage>

  const demo = settings.data
  const day = date ?? demo.calendar_end
  const problems = {
    date: day > demo.calendar_end ? t(`Use ${fmtDate(demo.calendar_end)} or earlier.`, `${fmtDate(demo.calendar_end)} বা আগের তারিখ দিন।`) : null,
    outcome: !outcome ? t('Choose what you found.', 'কী পেলেন বেছে নিন।') : null,
    note: note.length > demo.visit_note_max_chars ? t(`Keep the note under ${demo.visit_note_max_chars} characters.`, `নোট ${demo.visit_note_max_chars} অক্ষরের মধ্যে রাখুন।`) : null,
  }
  const submit = async () => {
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    const body: VisitCreate = { business_date: day, outcome: outcome!, note: note.trim() || null }
    const saved = await save.submit(() => api<RecordSaved>(`/merchants/${encodeURIComponent(merchantId)}/visits`, { method: 'POST', json: body }))
    if (saved) {
      forgetShop(merchantId)
      setOutcome(null)
      setNote('')
      setTouched(false)
    }
  }

  return (
    <FieldPage>
      <BackLink to={back}>{t('Back to the shop', 'দোকানে ফিরে যান')}</BackLink>
      <ShopHeader status={workflow.data} title={t('Shop visit', 'দোকান পরিদর্শন')} />
      <DemoLine settings={demo} />
      <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
        <Field label={t('Visit date', 'পরিদর্শনের তারিখ')} required error={touched ? problems.date : null}>
          <TextInput type="date" value={day} max={demo.calendar_end} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label={t('What you found', 'কী পেলেন')} required error={touched ? problems.outcome : null}>
          <ChoiceGroup name="outcome" value={outcome} onChange={setOutcome} options={demo.visit_outcomes.map((o) => ({ value: o, label: wordsFor(OUTCOME_WORDS, o, lang) }))} />
        </Field>
        <Field label={t('Note', 'নোট')} hint={t('Facts only, in a sentence or two. A visit never changes the score.', 'শুধু তথ্য, এক-দুই বাক্যে। পরিদর্শন কখনো স্কোর বদলায় না।')} error={touched ? problems.note : null}>
          <TextArea value={note} onChange={(e) => setNote(e.target.value)} maxLength={demo.visit_note_max_chars} />
        </Field>
        {save.error && <ErrorCallout error={save.error} />}
        {save.result && !save.error && <SavedNotice saved={save.result} what={t('Visit', 'পরিদর্শন')} />}
        <FormActions>
          <Button type="submit" size="lg" disabled={save.pending} aria-busy={save.pending}>
            {save.pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : t('Save visit', 'পরিদর্শন সংরক্ষণ করুন')}
          </Button>
        </FormActions>
      </form>
    </FieldPage>
  )
}
