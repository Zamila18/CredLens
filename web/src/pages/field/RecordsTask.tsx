/**
 * Business records typed in by staff: stock purchases, parcel deliveries and repayments.
 *
 * Each form asks only for what CredLens can store (no product lists, quantities or sales).
 * A saved record is labelled "typed in by staff · not verified". A repayment must belong to
 * one of the shop's real earlier loans (GET /merchants/{id}/loans); an application is never
 * offered, and the API refuses it as well. After a save the form clears for the next record
 * and keeps the date, so several papers can be entered in a row.
 */
import { FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { api } from '@/api/client'
import type { DeliveryCreate, MerchantLoan, PurchaseCreate, RecordSaved, RepaymentCreate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterSegments } from '@/components/Filters'
import { ChoiceGroup, Field, FormActions, MoneyInput, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import type { DemoSettings } from '@/api/types'
import { fmtDate, taka } from '@/lib/format'
import { DELIVERY_STATUS_WORDS, RETURN_REASON_WORDS, wordsFor } from '@/lib/fieldWords'
import { useLang, useT } from '@/lib/i18n'
import { BackLink, DemoLine, FieldPage, SavedNotice, ShopHeader } from './shared'
import { forgetShop, parseAmount, useDemoSettings, useWorkflow } from './fieldData'

type Kind = 'purchase' | 'delivery' | 'repayment'

function PurchaseForm({ merchantId, demo }: { merchantId: string; demo: DemoSettings }) {
  const t = useT()
  const [date, setDate] = useState(demo.calendar_end)
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('')
  const [supplier, setSupplier] = useState('')
  const [reference, setReference] = useState('')
  const [touched, setTouched] = useState(false)
  const save = useSubmit<RecordSaved>()
  const value = parseAmount(amount)
  const problems = {
    date: !date ? t('Choose the purchase date.', 'কেনার তারিখ বেছে নিন।') : date > demo.calendar_end ? t(`Use ${fmtDate(demo.calendar_end)} or earlier.`, `${fmtDate(demo.calendar_end)} বা আগের তারিখ দিন।`) : null,
    amount: value === null || value <= 0 ? t('Write the total paid for the stock, in taka.', 'মালের মোট দাম টাকায় লিখুন।') : null,
  }
  const submit = async () => {
    setTouched(true)
    if (problems.date || problems.amount) return
    const body: PurchaseCreate = {
      purchase_date: date,
      amount_bdt: value!,
      category: category.trim() || null,
      supplier_reference: supplier.trim() || null,
      invoice_reference: reference.trim() || null,
    }
    const saved = await save.submit(() => api<RecordSaved>(`/merchants/${encodeURIComponent(merchantId)}/purchases`, { method: 'POST', json: body }))
    if (saved) {
      forgetShop(merchantId)
      setAmount('')
      setCategory('')
      setReference('')
      setTouched(false)
    }
  }
  return (
    <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('Purchase date', 'কেনার তারিখ')} required error={touched ? problems.date : null}>
          <TextInput type="date" value={date} max={demo.calendar_end} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label={t('Total paid for the stock', 'মালের মোট দাম')} required error={touched ? problems.amount : null}>
          <MoneyInput value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="9,500" />
        </Field>
      </div>
      <Field label={t('Kind of stock', 'মালের ধরন')} hint={t('For example rice, cooking oil, medicine.', 'যেমন চাল, তেল, ওষুধ।')}>
        <TextInput value={category} maxLength={64} onChange={(e) => setCategory(e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('Supplier', 'সরবরাহকারী')}>
          <TextInput value={supplier} maxLength={32} onChange={(e) => setSupplier(e.target.value)} />
        </Field>
        <Field label={t('Number on the receipt', 'রসিদের নম্বর')} hint={t('Lets CredLens recognise the same receipt if it is entered again.', 'একই রসিদ আবার দিলে CredLens চিনতে পারে।')}>
          <TextInput value={reference} maxLength={32} onChange={(e) => setReference(e.target.value)} />
        </Field>
      </div>
      {save.error && <ErrorCallout error={save.error} />}
      {save.result && !save.error && <SavedNotice saved={save.result} what={t('Purchase', 'কেনা')} />}
      <FormActions>
        <Button type="submit" size="lg" disabled={save.pending} aria-busy={save.pending}>
          {save.pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : t('Save purchase', 'কেনা সংরক্ষণ করুন')}
        </Button>
      </FormActions>
    </form>
  )
}

function DeliveryForm({ merchantId, demo }: { merchantId: string; demo: DemoSettings }) {
  const t = useT()
  const lang = useLang()
  const [sent, setSent] = useState(demo.calendar_end)
  const [status, setStatus] = useState<string | null>(null)
  const [arrived, setArrived] = useState('')
  const [reason, setReason] = useState('')
  const [cod, setCod] = useState<string | null>(null)
  const [codOnTime, setCodOnTime] = useState('')
  const [touched, setTouched] = useState(false)
  const save = useSubmit<RecordSaved>()
  const problems = {
    sent: !sent ? t('Choose the day it was sent.', 'পাঠানোর দিন বেছে নিন।') : sent > demo.calendar_end ? t(`Use ${fmtDate(demo.calendar_end)} or earlier.`, `${fmtDate(demo.calendar_end)} বা আগের তারিখ দিন।`) : null,
    status: !status ? t('Choose what happened to the parcel.', 'পার্সেলের কী হলো বেছে নিন।') : null,
    arrived: status === 'delivered' && !arrived ? t('Choose the day it arrived.', 'পৌঁছানোর দিন বেছে নিন।') : status === 'delivered' && arrived < sent ? t('It cannot arrive before it was sent.', 'পাঠানোর আগে পৌঁছাতে পারে না।') : null,
    cod: cod === null ? t('Say whether the customer paid on delivery.', 'ক্রেতা পৌঁছানোর সময় টাকা দিলেন কি না বলুন।') : null,
  }
  const submit = async () => {
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    const body: DeliveryCreate = {
      dispatched_at: `${sent}T10:00`,
      delivered_at: status === 'delivered' ? `${arrived}T16:00` : null,
      status: status!,
      return_reason: status === 'returned' || status === 'failed' ? reason || null : null,
      is_cod: cod === 'yes',
      cod_remitted_on_time: cod === 'yes' && codOnTime ? codOnTime === 'yes' : null,
    }
    const saved = await save.submit(() => api<RecordSaved>(`/merchants/${encodeURIComponent(merchantId)}/deliveries`, { method: 'POST', json: body }))
    if (saved) {
      forgetShop(merchantId)
      setStatus(null)
      setArrived('')
      setReason('')
      setTouched(false)
    }
  }
  return (
    <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <Field label={t('Day the parcel was sent', 'পার্সেল পাঠানোর দিন')} required error={touched ? problems.sent : null}>
        <TextInput type="date" value={sent} max={demo.calendar_end} onChange={(e) => setSent(e.target.value)} />
      </Field>
      <Field label={t('What happened', 'কী হলো')} required error={touched ? problems.status : null}>
        <ChoiceGroup name="status" value={status} onChange={setStatus} options={demo.delivery_statuses.map((s) => ({ value: s, label: wordsFor(DELIVERY_STATUS_WORDS, s, lang) }))} />
      </Field>
      {status === 'delivered' && (
        <Field label={t('Day it arrived', 'পৌঁছানোর দিন')} required error={touched ? problems.arrived : null}>
          <TextInput type="date" value={arrived} min={sent} max={demo.calendar_end} onChange={(e) => setArrived(e.target.value)} />
        </Field>
      )}
      {(status === 'returned' || status === 'failed') && (
        <Field label={t('Reason', 'কারণ')} hint={t('Courier-side problems are not held against the shop.', 'কুরিয়ারের দিকের সমস্যা দোকানের বিপক্ষে ধরা হয় না।')}>
          <Select value={reason} onChange={(e) => setReason(e.target.value)} options={[{ value: '', label: t('Not known', 'জানা নেই') }, ...demo.return_reasons.map((r) => ({ value: r, label: wordsFor(RETURN_REASON_WORDS, r, lang) }))]} />
        </Field>
      )}
      <Field label={t('Customer pays on delivery (COD)', 'পৌঁছানোর সময় ক্রেতা টাকা দেন (COD)')} required error={touched ? problems.cod : null}>
        <ChoiceGroup name="cod" value={cod} onChange={setCod} options={[{ value: 'yes', label: t('Yes', 'হ্যাঁ') }, { value: 'no', label: t('No', 'না') }]} />
      </Field>
      {cod === 'yes' && (
        <Field label={t('Was the COD money passed back on time?', 'COD-এর টাকা কি সময়মতো ফেরত এসেছে?')}>
          <Select value={codOnTime} onChange={(e) => setCodOnTime(e.target.value)} options={[{ value: '', label: t('Not known yet', 'এখনও জানা নেই') }, { value: 'yes', label: t('Yes, on time', 'হ্যাঁ, সময়মতো') }, { value: 'no', label: t('No, late', 'না, দেরিতে') }]} />
        </Field>
      )}
      {save.error && <ErrorCallout error={save.error} />}
      {save.result && !save.error && <SavedNotice saved={save.result} what={t('Delivery', 'ডেলিভারি')} />}
      <FormActions>
        <Button type="submit" size="lg" disabled={save.pending} aria-busy={save.pending}>
          {save.pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : t('Save delivery', 'ডেলিভারি সংরক্ষণ করুন')}
        </Button>
      </FormActions>
    </form>
  )
}

function RepaymentForm({ merchantId, demo }: { merchantId: string; demo: DemoSettings }) {
  const t = useT()
  const loans = useApi<MerchantLoan[]>(`/merchants/${encodeURIComponent(merchantId)}/loans`, undefined, { noCache: true })
  const [loanId, setLoanId] = useState('')
  const [due, setDue] = useState('')
  const [paid, setPaid] = useState('')
  const [amountDue, setAmountDue] = useState('')
  const [amountPaid, setAmountPaid] = useState('')
  const [touched, setTouched] = useState(false)
  const save = useSubmit<RecordSaved>()

  if (loans.error) return <ErrorCallout error={loans.error} />
  if (!loans.data) return <LoadingState title={t('Loading the shop’s loans…', 'দোকানের ঋণ আসছে…')} />
  const eligible = loans.data.filter((l) => l.repayment_allowed)
  if (eligible.length === 0) {
    return (
      <Notice tone="info" title={t('No earlier loan to repay', 'পরিশোধের মতো আগের ঋণ নেই')}>
        {loans.data.some((l) => l.kind === 'application')
          ? t('This shop has an application, which is a request, not a loan. Repayments can only be recorded for loans that were issued.', 'এই দোকানের একটি আবেদন আছে, যা অনুরোধ, ঋণ নয়। শুধু দেওয়া ঋণের পরিশোধ রাখা যায়।')
          : t('This shop has no issued loan, so there is nothing to record here.', 'এই দোকানের কোনো দেওয়া ঋণ নেই, তাই এখানে রাখার কিছু নেই।')}
      </Notice>
    )
  }
  const dueValue = parseAmount(amountDue)
  const paidValue = parseAmount(amountPaid) ?? 0
  const problems = {
    loan: !loanId ? t('Choose the loan this instalment belongs to.', 'কিস্তিটি কোন ঋণের তা বেছে নিন।') : null,
    due: !due ? t('Choose the due date.', 'পরিশোধের নির্ধারিত দিন বেছে নিন।') : due > demo.calendar_end ? t(`Use ${fmtDate(demo.calendar_end)} or earlier.`, `${fmtDate(demo.calendar_end)} বা আগের তারিখ দিন।`) : null,
    amountDue: dueValue === null || dueValue <= 0 ? t('Write the amount that was due.', 'যত টাকা দেওয়ার কথা ছিল লিখুন।') : null,
    amountPaid: dueValue !== null && (paidValue < 0 || paidValue > dueValue) ? t('Paid must be between 0 and the amount due.', 'দেওয়া টাকা ০ থেকে দেওয়ার কথার মধ্যে হতে হবে।') : paidValue > 0 && !paid ? t('Add the day it was paid.', 'যেদিন দেওয়া হয়েছে সেটি দিন।') : null,
  }
  const submit = async () => {
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    const body: RepaymentCreate = { loan_id: loanId, due_date: due, paid_date: paid || null, amount_due_bdt: dueValue!, amount_paid_bdt: paidValue }
    const saved = await save.submit(() => api<RecordSaved>(`/merchants/${encodeURIComponent(merchantId)}/repayments`, { method: 'POST', json: body }))
    if (saved) {
      forgetShop(merchantId)
      setDue('')
      setPaid('')
      setAmountDue('')
      setAmountPaid('')
      setTouched(false)
    }
  }
  return (
    <form noValidate className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <Field label={t('Loan', 'ঋণ')} required error={touched ? problems.loan : null} hint={t('Only loans that were issued are listed; applications never are.', 'শুধু দেওয়া ঋণ দেখানো হয়; আবেদন কখনো নয়।')}>
        <Select
          value={loanId}
          onChange={(e) => setLoanId(e.target.value)}
          placeholder={t('Choose a loan', 'ঋণ বেছে নিন')}
          options={eligible.map((l) => ({ value: l.loan_id, label: `${fmtDate(l.issued_at)} · ${taka(l.limit_bdt)} · ${l.loan_id}` }))}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('Due date', 'নির্ধারিত দিন')} required error={touched ? problems.due : null}>
          <TextInput type="date" value={due} max={demo.calendar_end} onChange={(e) => setDue(e.target.value)} />
        </Field>
        <Field label={t('Day it was paid', 'যেদিন দেওয়া হয়েছে')} hint={t('Leave empty if not paid yet.', 'এখনও না দিলে খালি রাখুন।')}>
          <TextInput type="date" value={paid} max={demo.calendar_end} onChange={(e) => setPaid(e.target.value)} />
        </Field>
        <Field label={t('Amount due', 'দেওয়ার কথা')} required error={touched ? problems.amountDue : null}>
          <MoneyInput value={amountDue} onChange={(e) => setAmountDue(e.target.value)} />
        </Field>
        <Field label={t('Amount paid', 'দেওয়া হয়েছে')} error={touched ? problems.amountPaid : null}>
          <MoneyInput value={amountPaid} onChange={(e) => setAmountPaid(e.target.value)} placeholder="0" />
        </Field>
      </div>
      {save.error && <ErrorCallout error={save.error} />}
      {save.result && !save.error && <SavedNotice saved={save.result} what={t('Repayment', 'পরিশোধ')} />}
      <FormActions>
        <Button type="submit" size="lg" disabled={save.pending} aria-busy={save.pending}>
          {save.pending ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : t('Save repayment', 'পরিশোধ সংরক্ষণ করুন')}
        </Button>
      </FormActions>
    </form>
  )
}

export function RecordsTask() {
  const t = useT()
  const { merchantId = '' } = useParams()
  const settings = useDemoSettings()
  const workflow = useWorkflow(merchantId)
  const [kind, setKind] = useState<Kind>('purchase')
  const back = `/app/field/shops/${encodeURIComponent(merchantId)}`

  if (workflow.error || settings.error) return <FieldPage><ErrorCallout error={(workflow.error ?? settings.error)!} /></FieldPage>
  if (!workflow.data || !settings.data) return <FieldPage><LoadingState title={t('Loading…', 'আসছে…')} /></FieldPage>

  return (
    <FieldPage>
      <BackLink to={back}>{t('Back to the shop', 'দোকানে ফিরে যান')}</BackLink>
      <ShopHeader status={workflow.data} title={t('Business records', 'ব্যবসার রেকর্ড')} />
      <DemoLine settings={settings.data} />
      <p className="m-0 text-[15px] text-body">
        {t('Copy one paper at a time. Records are kept as typed in by staff and are not verified.', 'একবারে একটি কাগজ থেকে লিখুন। রেকর্ডগুলো কর্মীর লেখা হিসেবে থাকে, যাচাই করা নয়।')}
      </p>
      <FilterSegments<Kind>
        label={t('Kind of record', 'রেকর্ডের ধরন')}
        value={kind}
        onChange={setKind}
        options={[
          { value: 'purchase', label: t('Stock purchase', 'মাল কেনা') },
          { value: 'delivery', label: t('Parcel delivery', 'পার্সেল ডেলিভারি') },
          { value: 'repayment', label: t('Loan repayment', 'ঋণ পরিশোধ') },
        ]}
      />
      {kind === 'purchase' && (
        <Link
          to={`${back}/import`}
          className="flex min-h-11 items-center gap-3 rounded-[12px] border border-mint-line bg-strong-panel px-4 py-3 font-semibold text-lens-dark no-underline hover:bg-mint-2"
        >
          <FileSpreadsheet size={20} className="shrink-0" aria-hidden="true" />
          <span className="flex flex-col">
            {t('Have the purchases in an Excel sheet? Import them', 'কেনাকাটা এক্সেল শিটে আছে? আমদানি করুন')}
            <span className="text-[13px] font-normal text-body">{t('Check every row before anything is saved.', 'কিছু সংরক্ষণের আগে প্রতিটি সারি দেখে নিন।')}</span>
          </span>
        </Link>
      )}
      {kind === 'purchase' && <PurchaseForm merchantId={merchantId} demo={settings.data} />}
      {kind === 'delivery' && <DeliveryForm merchantId={merchantId} demo={settings.data} />}
      {kind === 'repayment' && <RepaymentForm merchantId={merchantId} demo={settings.data} />}
    </FieldPage>
  )
}
