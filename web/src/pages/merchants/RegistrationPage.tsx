/**
 * One registration case, start to finish: the details, the consent form to print, the signed
 * copy to upload, what the reader found (to check, field by field, against the document), and
 * the verification that records the consent.
 *
 * The reading is a machine's: EasyOCR is not trained on handwriting, so handwritten values are
 * often wrong or uncertain and are flagged. A person looks at the document, confirms or
 * corrects each field, and confirms the reference and that the signature appears to match the
 * owner. Ink in the signature box proves nothing about whose signature it is.
 */
import { Check, FileUp, Printer, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError, api, apiBlob } from '@/api/client'
import type { DemoSettings, ExtractionFieldOut, ExtractionOut, RegistrationOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, Select, TextArea, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { SHOP_TYPE_WORDS, wordsFor } from '@/lib/fieldWords'
import { fmtBdTime } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { CORE_BOXES, DETAILS, FIELD_STATE_WORDS, OPTIONAL_BOXES, OWNERSHIP, saveBlob } from './registrationWords'
import { StatusChip } from './StatusChip'

const EDITABLE = ['draft', 'form_issued', 'needs_correction', 'signed_uploaded', 'under_review']

function FieldChip({ state }: { state: string }) {
  const lang = useLang()
  const info = FIELD_STATE_WORDS[state] ?? { words: [state, state] as [string, string], tone: 'neutral' as const }
  const tone = {
    neutral: 'border-line bg-ground text-ink-2',
    warn: 'border-amber-chip bg-amber-panel text-amber-text',
    good: 'border-mint-line bg-mint text-accent-strong',
    bad: 'border-[#F3D0D0] bg-error-panel text-error',
  }[info.tone]
  return <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[12px] font-semibold', tone)}>{pick({ en: info.words[0], bn: info.words[1] }, lang)}</span>
}

function Card({ title, children, step }: { title: string; children: React.ReactNode; step?: string }) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
      <h2 className="m-0 flex items-center gap-2 text-[17px] font-semibold">
        {step && <span className="flex size-6 items-center justify-center rounded-full bg-deep text-[12px] text-white">{step}</span>}
        {title}
      </h2>
      {children}
    </section>
  )
}

export function RegistrationPage() {
  const t = useT()
  const lang = useLang()
  const { regId = '' } = useParams()
  const reg = useApi<RegistrationOut>(`/registrations/${encodeURIComponent(regId)}`, undefined, { noCache: true })
  const reading = useApi<ExtractionOut>(`/registrations/${encodeURIComponent(regId)}/extraction`, undefined, { noCache: true })
  const settings = useApi<DemoSettings>('/demo/settings')
  const file = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<Record<string, string> | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [viewUrl, setViewUrl] = useState<string | null>(null)
  const [viewMime, setViewMime] = useState('')
  const [boxes, setBoxes] = useState<Record<string, boolean> | null>(null)
  const [signer, setSigner] = useState<string | null>(null)
  const [signedOn, setSignedOn] = useState('')
  const [looked, setLooked] = useState(false)
  const [refOk, setRefOk] = useState(false)
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const save = useSubmit<RegistrationOut>()
  const act = useSubmit<RegistrationOut>()
  const review = useSubmit<ExtractionFieldOut>()

  const r = reg.data
  const jobBusy = r?.job?.status === 'queued' || r?.job?.status === 'running'
  // keep checking while the reader works
  const { reload: reloadReg } = reg
  const { reload: reloadReading } = reading
  useEffect(() => {
    if (!jobBusy) return
    const timer = setInterval(() => {
      reloadReg()
      reloadReading()
    }, 4000)
    return () => clearInterval(timer)
  }, [jobBusy, reloadReg, reloadReading])
  useEffect(
    () => () => {
      if (viewUrl) URL.revokeObjectURL(viewUrl)
    },
    [viewUrl],
  )

  if (reg.error) return <Page><ErrorCallout error={reg.error} /></Page>
  if (!r) return <Page><LoadingState title={t('Loading…', 'আসছে…')} /></Page>

  const values = form ?? Object.fromEntries(DETAILS.map(([k]) => [k, String(r.details[k] ?? '')]))
  const fields = reading.data?.fields ?? []
  const byKey = Object.fromEntries(fields.map((f) => [f.key, f]))
  const suggested = (key: string) => byKey[`tick:${key}`]?.value === 'yes'
  const ticked = boxes ?? Object.fromEntries([...CORE_BOXES, ...OPTIONAL_BOXES].map(([k]) => [k, suggested(k)]))
  const signerName = signer ?? byKey.signer_name?.reviewed_value ?? byKey.signer_name?.value ?? r.details.owner_name?.toString() ?? ''
  const closed = !EDITABLE.includes(r.status)
  const canEditDetails = !closed
  const refresh = () => {
    reg.reload()
    reading.reload()
  }

  const saveDetails = async () => {
    setFieldErrors({})
    try {
      await save.submit(() => api<RegistrationOut>(`/registrations/${encodeURIComponent(regId)}/details`, { method: 'PATCH', json: values }))
      setForm(null)
      setNotice(t('Details saved.', 'তথ্য সংরক্ষিত।'))
      refresh()
    } catch {
      /* shown below */
    }
  }
  const sendSigned = async (chosen: File | undefined) => {
    if (!chosen) return
    const done = await act.submit(() =>
      api<RegistrationOut>(`/registrations/${encodeURIComponent(regId)}/signed`, {
        method: 'POST',
        query: { name: chosen.name },
        body: { content: chosen, contentType: chosen.type || 'application/octet-stream' },
      }),
    )
    if (done) {
      setNotice(t('Uploaded. The text is being read; this can take a few minutes.', 'আপলোড হয়েছে। লেখা পড়া হচ্ছে; কয়েক মিনিট লাগতে পারে।'))
      refresh()
    }
  }
  const showDocument = async () => {
    if (viewUrl) {
      setViewUrl(null)
      return
    }
    const blob = await apiBlob(`/registrations/${encodeURIComponent(regId)}/document`)
    setViewMime(blob.type)
    setViewUrl(URL.createObjectURL(blob))
  }
  const fieldAction = async (f: ExtractionFieldOut, value?: string) => {
    await review.submit(() => api<ExtractionFieldOut>(`/registrations/${encodeURIComponent(regId)}/fields/${f.field_id}`, { method: 'PATCH', json: { value: value ?? null } }))
    reading.reload()
  }
  const verify = async () => {
    const categories = CORE_BOXES.map(([k]) => k).filter((k) => ticked[k])
    const optional = OPTIONAL_BOXES.map(([k]) => k).filter((k) => ticked[k])
    const done = await act.submit(() =>
      api<RegistrationOut>(`/registrations/${encodeURIComponent(regId)}/verify`, {
        method: 'POST',
        json: { categories, optional, signer_name: signerName, signed_on: signedOn || null, signature_checked: looked, reference_matches: refOk },
      }),
    )
    if (done) {
      setNotice(t('Verified. The consent is recorded and the merchant can now be assessed.', 'যাচাই হয়েছে। অনুমতি রাখা হয়েছে, এখন মার্চেন্টের মূল্যায়ন করা যাবে।'))
      refresh()
    }
  }
  const close = async (path: 'return' | 'reject') => {
    const done = await act.submit(() => api<RegistrationOut>(`/registrations/${encodeURIComponent(regId)}/${path}`, { method: 'POST', json: { reason } }))
    if (done) {
      setReason('')
      refresh()
    }
  }
  const apiFields = (err: unknown) => (err instanceof ApiError ? ((err.facts as { fields?: Record<string, string> }).fields ?? {}) : {})
  const waitingForSigned = r.method === 'manual' && ['draft', 'form_issued', 'needs_correction'].includes(r.status)
  const verifiable = ['signed_uploaded', 'under_review'].includes(r.status)

  const control = (key: string) => {
    if (key === 'district')
      return <Select value={values.district} onChange={(e) => setForm({ ...values, district: e.target.value })} placeholder={t('Choose a district', 'জেলা বাছুন')} options={(settings.data?.districts ?? []).map((d) => ({ value: d, label: d }))} />
    if (key === 'shop_type')
      return <Select value={values.shop_type} onChange={(e) => setForm({ ...values, shop_type: e.target.value })} placeholder={t('Choose one', 'একটি বাছুন')} options={(settings.data?.shop_types ?? []).map((s) => ({ value: s, label: wordsFor(SHOP_TYPE_WORDS, s, lang) }))} />
    if (key === 'ownership_type')
      return <Select value={values.ownership_type} onChange={(e) => setForm({ ...values, ownership_type: e.target.value })} placeholder={t('Choose one', 'একটি বাছুন')} options={Object.entries(OWNERSHIP).map(([value, p]) => ({ value, label: pick({ en: p[0], bn: p[1] }, lang) }))} />
    return <TextInput value={values[key]} onChange={(e) => setForm({ ...values, [key]: e.target.value })} />
  }

  return (
    <Page>
      <PageHeader
        title={r.shop_name ?? t('Registration from a filled form', 'ভরা ফর্ম থেকে নিবন্ধন')}
        description={`${r.reg_ref} · ${r.method === 'manual' ? t('typed details', 'টাইপ করা তথ্য') : t('blank form filled by hand', 'হাতে ভরা ফাঁকা ফর্ম')}`}
        aside={<StatusChip status={r.status} />}
      />
      {notice && <Notice tone="success" title={notice}>{''}</Notice>}
      {r.reviewer_note && (r.status === 'needs_correction' || r.status === 'rejected' || r.status === 'withdrawn') && (
        <Notice tone="warning" title={t('Note from the reviewer', 'পর্যালোচকের নোট')}>{r.reviewer_note}</Notice>
      )}
      {r.merchant_id && (
        <p className="m-0 text-[14px] text-body">
          {t('Merchant', 'মার্চেন্ট')}:{' '}
          <Link to={`/app/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-mono font-semibold">{r.merchant_id}</Link>
        </p>
      )}

      <Card step="1" title={t('Merchant details', 'মার্চেন্টের তথ্য')}>
        {r.method === 'blank_form' && !r.merchant_id && (
          <Notice tone="info" title={t('These were read from the form', 'এগুলো ফর্ম থেকে পড়া হয়েছে')}>
            {t('Handwriting is often misread. Compare with the document, correct what is wrong, fill in what is missing, then save: the merchant is created once every required detail is there.', 'হাতের লেখা প্রায়ই ভুল পড়া হয়। নথির সাথে মিলিয়ে ভুল ঠিক করুন, বাদ পড়া ভরুন, তারপর সংরক্ষণ করুন: সব আবশ্যক তথ্য থাকলে মার্চেন্ট তৈরি হবে।')}
          </Notice>
        )}
        <div className="grid gap-3 md:grid-cols-2">
          {DETAILS.map(([key, en, bn, required]) => (
            <Field key={key} label={t(en, bn)} required={required} error={fieldErrors[key] ?? apiFields(save.error)[key] ?? null}>
              {canEditDetails ? control(key) : <span className="text-[15px] text-ink">{values[key] || '—'}</span>}
            </Field>
          ))}
        </div>
        {save.error && !Object.keys(apiFields(save.error)).length && <ErrorCallout error={save.error} />}
        {canEditDetails && <Button className="self-start" disabled={save.pending} onClick={() => void saveDetails()}>{t('Save details', 'তথ্য সংরক্ষণ')}</Button>}
      </Card>

      {r.method === 'manual' && (
        <Card step="2" title={t('Print the consent form', 'সম্মতিপত্র প্রিন্ট করুন')}>
          <p className="m-0 text-[14px] text-body">{t('The form has these details, the company’s name, the eleven-section consent text in English and Bangla, and the reference number. The merchant reads it, ticks the boxes and signs.', 'ফর্মে এই তথ্য, প্রতিষ্ঠানের নাম, ইংরেজি ও বাংলায় এগারো অংশের সম্মতিপত্র এবং রেফারেন্স নম্বর আছে। মার্চেন্ট পড়ে, বাক্সে টিক দিয়ে সই করেন।')}</p>
          {!r.template_approved && <Notice tone="warning" title={t('Draft wording', 'খসড়া ভাষা')}>{t('The form is stamped DRAFT: the text has not been reviewed by a lawyer and approved yet.', 'ফর্মে খসড়া ছাপ আছে: লেখাটি এখনও আইনজীবী পর্যালোচনা করে অনুমোদিত হয়নি।')}</Notice>}
          {['draft', 'form_issued', 'needs_correction'].includes(r.status) && (
            <Button className="self-start" variant="outline" onClick={() => void saveBlob(`/registrations/${encodeURIComponent(regId)}/consent.pdf`, `${r.reg_ref}.pdf`).then(refresh)}>
              <Printer size={17} aria-hidden="true" />
              {t('Download the form (PDF) to print', 'ফর্ম (PDF) নামান, প্রিন্টের জন্য')}
            </Button>
          )}
        </Card>
      )}

      {waitingForSigned && (
        <Card step="3" title={t('Upload the signed form', 'সই করা ফর্ম আপলোড করুন')}>
          <p className="m-0 text-[14px] text-body">{t('A clear photo or scan of every page (JPEG, PNG or PDF, up to 8 MB). Keep the reference number visible.', 'প্রতিটি পাতার পরিষ্কার ছবি বা স্ক্যান (JPEG, PNG বা PDF, ৮ MB পর্যন্ত)। রেফারেন্স নম্বর দেখা যেন যায়।')}</p>
          <Button className="self-start" variant="outline" disabled={act.pending} onClick={() => file.current?.click()}>
            <FileUp size={17} aria-hidden="true" />
            {act.pending ? t('Uploading…', 'আপলোড হচ্ছে…') : t('Choose the photo or scan', 'ছবি বা স্ক্যান বাছুন')}
          </Button>
          <input ref={file} type="file" hidden accept="image/jpeg,image/png,application/pdf" capture="environment" onChange={(e) => void sendSigned(e.target.files?.[0])} />
          {act.error && <ErrorCallout error={act.error} />}
        </Card>
      )}

      {r.job && (
        <Card step={r.method === 'manual' ? '4' : '2'} title={t('What was read from the document', 'নথি থেকে যা পড়া হয়েছে')}>
          <p className="m-0 text-[13.5px] text-muted-2">
            {r.job.status === 'queued' && t('Waiting to be read…', 'পড়ার অপেক্ষায়…')}
            {r.job.status === 'running' && t('Being read now. This can take a few minutes.', 'এখন পড়া হচ্ছে। কয়েক মিনিট লাগতে পারে।')}
            {r.job.status === 'failed' && t(`The reader could not read this document (${r.job.error}). Check the document yourself.`, `রিডার নথিটি পড়তে পারেনি (${r.job.error})। নিজে নথি দেখে নিন।`)}
            {r.job.status === 'done' && t(`Read with ${r.job.engine} ${r.job.engine_version ?? ''}, ${r.job.pages} page(s), ${r.job.finished_at ? fmtBdTime(r.job.finished_at) : ''}. Handwriting is not reliably read: check every field.`, `${r.job.engine} ${r.job.engine_version ?? ''} দিয়ে পড়া, ${r.job.pages} পাতা। হাতের লেখা নির্ভরযোগ্যভাবে পড়া যায় না: প্রতিটি ঘর দেখে নিন।`)}
          </p>
          {fields.length > 0 && (
            <ul className="m-0 flex list-none flex-col p-0">
              {fields.filter((f) => !f.key.startsWith('tick:')).map((f) => (
                <li key={f.field_id} className="grid gap-2 border-t border-line py-2.5 first:border-t-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_auto] md:items-center">
                  <span className="flex flex-col text-[14px]">
                    <span className="font-semibold text-ink">{t(f.label_en, f.label_bn)}</span>
                    {f.expected && f.state !== 'matched' && <span className="text-[12.5px] text-muted-2">{t('Typed:', 'টাইপ করা:')} {f.expected}</span>}
                  </span>
                  <span className="min-w-0 text-[14.5px] text-ink">
                    {f.reviewed_value ?? f.value ?? '—'}
                    {f.confidence != null && <span className="ml-2 text-[12px] text-muted-2">{Math.round(f.confidence * 100)}%</span>}
                  </span>
                  <span className="flex flex-wrap items-center gap-2">
                    <FieldChip state={f.state} />
                    {!['signature'].includes(f.key) && f.state !== 'confirmed' && f.state !== 'corrected' && (
                      <>
                        <Button size="sm" variant="ghost" disabled={review.pending || !f.value} onClick={() => void fieldAction(f)}>
                          <Check size={14} aria-hidden="true" />
                          {t('Confirm', 'নিশ্চিত')}
                        </Button>
                        <Button size="sm" variant="outline" disabled={review.pending} onClick={() => { const v = window.prompt(t('Correct value', 'সঠিক মান'), f.value ?? ''); if (v !== null) void fieldAction(f, v) }}>
                          {t('Correct', 'ঠিক করুন')}
                        </Button>
                      </>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {verifiable && (
        <Card step="✓" title={t('Check the document and verify', 'নথি দেখে যাচাই করুন')}>
          {!r.can_verify && <Notice tone="warning" title={t('Another Credit Officer must verify this', 'এটি অন্য একজন ক্রেডিট অফিসারকে যাচাই করতে হবে')}>{t('You uploaded this form. When the company has another active Credit Officer, that person verifies it.', 'আপনি এই ফর্ম আপলোড করেছেন। প্রতিষ্ঠানে অন্য সক্রিয় ক্রেডিট অফিসার থাকলে তিনিই যাচাই করেন।')}</Notice>}
          {r.can_verify && r.uploaded_by && <p className="m-0 text-[13px] text-muted-2">{t('If you uploaded this yourself and nobody else can verify, it is recorded as self-verified.', 'আপনি নিজে আপলোড করে থাকলে এবং আর কেউ যাচাই করার না থাকলে, এটি “নিজে যাচাই” হিসেবে রাখা হয়।')}</p>}
          {r.has_document && (
            <>
              <Button className="self-start" variant="outline" onClick={() => void showDocument()}>
                {viewUrl ? t('Hide the signed form', 'সই করা ফর্ম লুকান') : t('Look at the signed form', 'সই করা ফর্ম দেখুন')}
              </Button>
              {viewUrl && (viewMime === 'application/pdf'
                ? <iframe src={viewUrl} title={t('Signed form', 'সই করা ফর্ম')} className="h-[620px] w-full rounded-[10px] border border-line" />
                : <img src={viewUrl} alt={t('Signed form', 'সই করা ফর্ম')} className="max-h-[620px] w-full rounded-[10px] border border-line object-contain" />)}
            </>
          )}
          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="mb-1 p-0 text-[14px] font-semibold text-ink">{t('Boxes the merchant ticked on the paper', 'কাগজে মার্চেন্ট যে বাক্সে টিক দিয়েছেন')}</legend>
            <p className="m-0 text-[12.5px] text-muted-2">{t('Boxes the reader thinks are ticked start ticked; you decide. Nothing else is ticked for you.', 'রিডার যেগুলো টিক-করা মনে করেছে সেগুলো আগে থেকে টিক থাকে; সিদ্ধান্ত আপনার। আর কিছু আপনার হয়ে টিক হয় না।')}</p>
            {[...CORE_BOXES, ...OPTIONAL_BOXES].map(([key, words]) => (
              <label key={key} className="flex items-start gap-2 text-[14px] text-ink">
                <input type="checkbox" className="mt-1" checked={!!ticked[key]} onChange={(e) => setBoxes({ ...ticked, [key]: e.target.checked })} />
                <span>{pick({ en: words[0], bn: words[1] }, lang)}{suggested(key) && <span className="ml-2 text-[12px] text-muted-2">{t('(reader saw a mark)', '(রিডার চিহ্ন দেখেছে)')}</span>}</span>
              </label>
            ))}
          </fieldset>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label={t('Name of the person who signed', 'যিনি সই করেছেন তাঁর নাম')} required>
              <TextInput value={signerName} onChange={(e) => setSigner(e.target.value)} />
            </Field>
            <Field label={t('Date signed', 'সইয়ের তারিখ')} hint={t('Leave empty for today.', 'আজকের জন্য খালি রাখুন।')}>
              <TextInput type="date" value={signedOn || byKey.signed_on?.value || ''} onChange={(e) => setSignedOn(e.target.value)} />
            </Field>
          </div>
          <label className="flex items-start gap-2 text-[14px] text-ink"><input type="checkbox" className="mt-1" checked={refOk} onChange={(e) => setRefOk(e.target.checked)} />{t(`The reference on the paper is ${r.reg_ref}${r.form_serial ? ` / ${r.form_serial}` : ''}.`, `কাগজের রেফারেন্স ${r.reg_ref}${r.form_serial ? ` / ${r.form_serial}` : ''}।`)}</label>
          <label className="flex items-start gap-2 text-[14px] text-ink"><input type="checkbox" className="mt-1" checked={looked} onChange={(e) => setLooked(e.target.checked)} />{t('I looked at the signed page: the name and signature appear to match the shop owner.', 'আমি সই করা পাতা দেখেছি: নাম ও সই দোকানমালিকের সাথে মেলে বলে মনে হয়।')}</label>
          {!r.merchant_id && <Notice tone="warning" title={t('Save the details first', 'আগে তথ্য সংরক্ষণ করুন')}>{t('The merchant is created when every required detail is saved.', 'সব আবশ্যক তথ্য সংরক্ষণ হলে মার্চেন্ট তৈরি হয়।')}</Notice>}
          {act.error && <ErrorCallout error={act.error} />}
          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={act.pending || !r.merchant_id || !r.can_verify || !looked || !refOk} onClick={() => void verify()}>
              <ShieldCheck size={17} aria-hidden="true" />
              {t('Verify and record the consent', 'যাচাই করে অনুমতি রাখুন')}
            </Button>
          </div>
          <div className="flex flex-col gap-2 border-t border-line pt-3">
            <Field label={t('Reason (to send back or reject), at least 10 characters', 'কারণ (ফেরত বা প্রত্যাখ্যানের জন্য), কমপক্ষে ১০ অক্ষর')}>
              <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
            </Field>
            <div className="flex gap-2">
              <Button variant="outline" disabled={act.pending || reason.trim().length < 10} onClick={() => void close('return')}>{t('Send back for correction', 'সংশোধনের জন্য ফেরত')}</Button>
              <Button variant="ghost" disabled={act.pending || reason.trim().length < 10} onClick={() => void close('reject')}>{t('Reject', 'প্রত্যাখ্যান')}</Button>
            </div>
          </div>
        </Card>
      )}

      {r.status === 'active' && (
        <Card title={t('Consent recorded', 'অনুমতি রাখা হয়েছে')}>
          <p className="m-0 text-[14.5px] text-body">
            {t(`Signed by ${r.signer_name} on ${r.signed_on}. Verified by ${r.verified_by} (${r.verification_mode === 'self_verified' ? 'self-verified: the company has no other Credit Officer' : 'a different Credit Officer'}). Template ${r.template_version}.`, `${r.signer_name} সই করেছেন ${r.signed_on}। যাচাই করেছেন ${r.verified_by}। টেমপ্লেট ${r.template_version}।`)}
          </p>
          {r.has_document && <Button className="self-start" variant="outline" onClick={() => void showDocument()}>{viewUrl ? t('Hide the signed form', 'সই করা ফর্ম লুকান') : t('Look at the signed form', 'সই করা ফর্ম দেখুন')}</Button>}
          {viewUrl && (viewMime === 'application/pdf' ? <iframe src={viewUrl} title="signed" className="h-[620px] w-full rounded-[10px] border border-line" /> : <img src={viewUrl} alt="signed" className="max-h-[620px] w-full rounded-[10px] border border-line object-contain" />)}
        </Card>
      )}
    </Page>
  )
}
