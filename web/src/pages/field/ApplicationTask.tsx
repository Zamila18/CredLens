/**
 * The shop's working-capital request (POST /merchants/{id}/application), one per shop.
 *
 * Asked for: the amount, the purpose and an optional short explanation. Before saving, a
 * confirmation says plainly that this is a request, not a loan, and that it can be made
 * only once. The answer says that the application was saved and whether the assessment was
 * refreshed. Records dated on or after the application date do not count for it.
 */
import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { api } from '@/api/client'
import type { ApplicationCreate, RecordSaved } from '@/api/types'
import { useSubmit } from '@/api/useSubmit'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, FormActions, MoneyInput, Select, TextArea } from '@/components/form'
import { Notice } from '@/components/Notice'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { fmtDate, taka } from '@/lib/format'
import { PURPOSE_WORDS, wordsFor } from '@/lib/fieldWords'
import { pick, useLang, useT } from '@/lib/i18n'
import { ASSESSMENT_STATUS, LOAN_KIND } from '@/lib/statuses'
import { BackLink, DemoLine, FieldPage, ShopHeader } from './shared'
import { forgetShop, parseAmount, useDemoSettings, useWorkflow } from './fieldData'

export function ApplicationTask() {
  const t = useT()
  const lang = useLang()
  const { merchantId = '' } = useParams()
  const settings = useDemoSettings()
  const workflow = useWorkflow(merchantId)
  const [amount, setAmount] = useState('')
  const [purpose, setPurpose] = useState('')
  const [note, setNote] = useState('')
  const [touched, setTouched] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const save = useSubmit<RecordSaved>()
  const back = `/app/field/shops/${encodeURIComponent(merchantId)}`

  if (workflow.error || settings.error) return <FieldPage><ErrorCallout error={(workflow.error ?? settings.error)!} /></FieldPage>
  if (!workflow.data || !settings.data) return <FieldPage><LoadingState title={t('Loading…', 'আসছে…')} /></FieldPage>

  const demo = settings.data
  const status = workflow.data
  const value = parseAmount(amount)
  const problems = {
    amount:
      value === null || value <= 0
        ? t('Write the amount the shop is asking for, in taka.', 'দোকান যত টাকা চাইছে লিখুন।')
        : value > demo.max_requested_bdt
          ? t(`The most this form accepts is ${taka(demo.max_requested_bdt)}.`, `এই ফর্মে সর্বোচ্চ ${taka(demo.max_requested_bdt)}।`)
          : null,
    purpose: !purpose ? t('Choose what the money is for.', 'টাকা কীসের জন্য বেছে নিন।') : null,
  }
  const ask = () => {
    setTouched(true)
    if (!problems.amount && !problems.purpose) setConfirm(true)
  }
  const send = async () => {
    const body: ApplicationCreate = { requested_amount_bdt: value!, purpose, purpose_note: note.trim() || null }
    const saved = await save.submit(() => api<RecordSaved>(`/merchants/${encodeURIComponent(merchantId)}/application`, { method: 'POST', json: body }))
    setConfirm(false)
    if (saved) forgetShop(merchantId)
  }

  const existing = status.application
  const officerLink = (
    <Link to={`/app/merchants/${encodeURIComponent(merchantId)}`} className="inline-flex min-h-11 items-center gap-1 font-semibold">
      {t('Open the officer’s view of this shop', 'এই দোকানের কর্মকর্তার দৃশ্য খুলুন')}
      <ChevronRight size={17} aria-hidden="true" />
    </Link>
  )

  return (
    <FieldPage>
      <BackLink to={back}>{t('Back to the shop', 'দোকানে ফিরে যান')}</BackLink>
      <ShopHeader status={status} title={t('Application', 'আবেদন')} />
      <DemoLine settings={demo} />

      {save.result ? (
        <Notice
          tone={save.result.assessment.status === 'not_updated' ? 'warning' : 'success'}
          title={t('Application saved', 'আবেদন সংরক্ষিত')}
          action={officerLink}
        >
          <span className="flex flex-col gap-2">
            <span className="flex flex-wrap gap-2">
              <StatusTag status={LOAN_KIND.application} />
              <StatusTag status={ASSESSMENT_STATUS[save.result.assessment.status]} />
            </span>
            <span>
              {t('A credit officer will review it and record a decision. Nothing has been approved or issued.', 'একজন ঋণ কর্মকর্তা এটি দেখে সিদ্ধান্ত লিখবেন। কিছুই অনুমোদিত বা প্রদান করা হয়নি।')}
            </span>
          </span>
        </Notice>
      ) : existing ? (
        <Notice tone="info" title={t('This shop already has its application', 'এই দোকানের আবেদন আগেই আছে')} action={officerLink}>
          {t(
            `${taka(existing.requested_amount_bdt)} requested on ${fmtDate(existing.business_date)} for ${wordsFor(PURPOSE_WORDS, existing.purpose, lang).toLowerCase()}. It is a request, not a loan. This prototype allows one application per shop.`,
            `${fmtDate(existing.business_date)}-এ ${wordsFor(PURPOSE_WORDS, existing.purpose, lang)}-এর জন্য ${taka(existing.requested_amount_bdt)} চাওয়া হয়েছে। এটি অনুরোধ, ঋণ নয়। এই প্রোটোটাইপে দোকানপ্রতি একটি আবেদন।`,
          )}
        </Notice>
      ) : (
        <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); ask() }}>
          <Notice tone="info" title={t('Before you continue', 'এগোনোর আগে')}>
            {t(
              `Add the shop’s records first: only records dated before the application date (${fmtDate(demo.calendar_end)}) count for it. One application per shop.`,
              `আগে দোকানের রেকর্ড যোগ করুন: শুধু আবেদনের তারিখের (${fmtDate(demo.calendar_end)}) আগের রেকর্ড এতে গোনা হয়। দোকানপ্রতি একটি আবেদন।`,
            )}
          </Notice>
          <Field label={t('Amount the shop is asking for', 'দোকান যত টাকা চাইছে')} required hint={t('This is a request, not an approved limit.', 'এটি অনুরোধ, অনুমোদিত সীমা নয়।')} error={touched ? problems.amount : null}>
            <MoneyInput value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="40,000" />
          </Field>
          <Field label={t('What the money is for', 'টাকা কীসের জন্য')} required error={touched ? problems.purpose : null}>
            <Select value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder={t('Choose one', 'একটি বেছে নিন')} options={demo.application_purposes.map((p) => ({ value: p, label: wordsFor(PURPOSE_WORDS, p, lang) }))} />
          </Field>
          <Field label={t('Short explanation', 'ছোট ব্যাখ্যা')} hint={t('In the merchant’s words, if useful.', 'দরকার হলে মার্চেন্টের ভাষায়।')}>
            <TextArea value={note} onChange={(e) => setNote(e.target.value)} maxLength={demo.application_note_max_chars} />
          </Field>
          {save.error && <ErrorCallout error={save.error} />}
          <FormActions>
            <Button type="submit" size="lg" disabled={save.pending}>
              {t('Create the application', 'আবেদন তৈরি করুন')}
            </Button>
          </FormActions>
        </form>
      )}

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t('Create this application?', 'এই আবেদন তৈরি করবেন?')}
        confirmLabel={t('Create application', 'আবেদন তৈরি করুন')}
        onConfirm={() => void send()}
        pending={save.pending}
      >
        {value !== null &&
          t(
            `${taka(value)} requested for ${wordsFor(PURPOSE_WORDS, purpose, lang).toLowerCase()}. It is a request, not a loan, and this shop can make only one.`,
            `${wordsFor(PURPOSE_WORDS, purpose, lang)}-এর জন্য ${taka(value)} চাওয়া হচ্ছে। এটি অনুরোধ, ঋণ নয়, আর এই দোকান একবারই আবেদন করতে পারে।`,
          )}
        {' '}
        {pick({ en: 'The assessment runs right after saving.', bn: 'সংরক্ষণের পরপরই মূল্যায়ন চলবে।' }, lang)}
      </ConfirmDialog>
    </FieldPage>
  )
}
