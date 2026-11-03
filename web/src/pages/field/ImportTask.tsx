/**
 * Import stock purchases from an Excel workbook, in four steps on one page:
 * choose the file → say which column is which → check every row → confirm and save.
 *
 * Calls POST /merchants/{id}/purchase-import/inspect, /preview and /commit with the workbook
 * as the request body. Inspect and preview save nothing. The preview is bound to the file,
 * sheet, columns and date order: change any of them and the screen asks for a new preview;
 * the API refuses a commit that does not match (preview_changed). Rows that look like a
 * purchase already saved are saved only if the person ticks them.
 */
import { FileSpreadsheet, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { api } from '@/api/client'
import type { ImportInspect, ImportPreview, ImportResult, ImportRow } from '@/api/types'
import { useSubmit } from '@/api/useSubmit'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterSegments } from '@/components/Filters'
import { ChoiceGroup, Field, FormActions, Select } from '@/components/form'
import { Notice } from '@/components/Notice'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { count, fmtDate, taka } from '@/lib/format'
import { pick, useLang, useT, type Pair } from '@/lib/i18n'
import { ASSESSMENT_STATUS, RECORD_STATUS, type StatusWords } from '@/lib/statuses'
import { BackLink, DemoLine, FieldPage, ShopHeader } from './shared'
import { forgetShop, useDemoSettings, useWorkflow } from './fieldData'

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const FIELD_WORDS: Record<string, Pair & { hint: Pair }> = {
  purchase_date: { en: 'Purchase date', bn: 'কেনার তারিখ', hint: { en: 'The day the stock was bought.', bn: 'যেদিন মাল কেনা হয়েছে।' } },
  amount_bdt: { en: 'Amount paid (taka)', bn: 'দেওয়া টাকা', hint: { en: 'The total of the bill.', bn: 'বিলের মোট অঙ্ক।' } },
  category: { en: 'Kind of stock', bn: 'মালের ধরন', hint: { en: 'For example rice, oil, medicine.', bn: 'যেমন চাল, তেল, ওষুধ।' } },
  invoice_reference: { en: 'Memo or invoice number', bn: 'মেমো বা চালান নম্বর', hint: { en: 'Lets CredLens recognise a paper already entered.', bn: 'আগে লেখা কাগজ চিনতে CredLens-কে সাহায্য করে।' } },
  supplier_reference: { en: 'Supplier', bn: 'সরবরাহকারী', hint: { en: 'Who sold the stock.', bn: 'কে মাল বিক্রি করেছে।' } },
}

const OUTCOME: Record<ImportRow['outcome'], StatusWords> = {
  add: { en: 'Will be added', bn: 'যোগ হবে', tone: 'strong', help: { en: 'A new purchase.', bn: 'নতুন কেনাকাটা।' } },
  skip: { en: 'Already saved', bn: 'আগেই সংরক্ষিত', tone: 'neutral', help: { en: 'Nothing is added for this row.', bn: 'এই সারির জন্য কিছু যোগ হবে না।' } },
  flag: { en: 'Check: possible duplicate', bn: 'দেখুন: হয়তো দুবার', tone: 'amber', help: { en: 'Saved only if you keep it.', bn: 'রাখলে তবেই সংরক্ষণ হবে।' } },
  reject: { en: 'Cannot be read', bn: 'পড়া যায়নি', tone: 'peri', help: { en: 'Fix the row in the file and import again.', bn: 'ফাইলে সারিটি ঠিক করে আবার আমদানি করুন।' } },
}

const REASON: Record<string, Pair> = {
  new: { en: 'New purchase.', bn: 'নতুন কেনাকাটা।' },
  reference_saved: { en: 'A purchase with this memo number is already saved.', bn: 'এই মেমো নম্বরের কেনাকাটা আগেই সংরক্ষিত।' },
  row_imported_before: { en: 'This row of this file was imported before.', bn: 'এই ফাইলের এই সারি আগে আমদানি হয়েছে।' },
  possible_duplicate: { en: 'A purchase with the same date and amount is already saved or appears earlier in the file.', bn: 'একই তারিখ ও অঙ্কের কেনাকাটা আগেই সংরক্ষিত, বা ফাইলে আগে আছে।' },
  missing_date: { en: 'The date is empty.', bn: 'তারিখ খালি।' },
  bad_date: { en: 'The date cannot be read. Write it like 25/07/2026.', bn: 'তারিখ পড়া যায়নি। 25/07/2026 এভাবে লিখুন।' },
  ambiguous_date: { en: 'The date can be read two ways. Choose how dates are written above.', bn: 'তারিখ দুইভাবে পড়া যায়। ওপরে তারিখ লেখার ধরন বেছে নিন।' },
  date_after_calendar: { en: 'The date is later than the last date allowed (today, or the end of the demo calendar).', bn: 'তারিখটি অনুমোদিত শেষ তারিখের পরে (আজ, বা ডেমো ক্যালেন্ডারের শেষ)।' },
  missing_amount: { en: 'The amount is empty.', bn: 'অঙ্ক খালি।' },
  bad_amount: { en: 'The amount is not a number above 0.', bn: 'অঙ্কটি 0-এর বেশি কোনো সংখ্যা নয়।' },
  category_too_long: { en: 'The kind of stock is too long.', bn: 'মালের ধরন খুব লম্বা।' },
  reference_too_long: { en: 'The memo number or supplier is too long.', bn: 'মেমো নম্বর বা সরবরাহকারী খুব লম্বা।' },
  reference_twice_in_file: { en: 'The same memo number is on another row of this file.', bn: 'একই মেমো নম্বর এই ফাইলের অন্য সারিতেও আছে।' },
}

type Filter = 'attention' | 'add' | 'skip' | 'all'
type Mapping = Record<string, string | null>
const NONE = ''

export function ImportTask() {
  const t = useT()
  const lang = useLang()
  const { merchantId = '' } = useParams()
  const settings = useDemoSettings()
  const workflow = useWorkflow(merchantId)
  const base = `/app/merchants/${encodeURIComponent(merchantId)}/purchase-import`
  const back = `/app/field/shops/${encodeURIComponent(merchantId)}`
  const input = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<{ name: string; data: ArrayBuffer } | null>(null)
  const [sheet, setSheet] = useState('')
  const [mapping, setMapping] = useState<Mapping>({})
  const [dateOrder, setDateOrder] = useState<'auto' | 'dmy' | 'mdy'>('auto')
  const [keep, setKeep] = useState<number[]>([])
  const [filter, setFilter] = useState<Filter>('attention')
  const [confirm, setConfirm] = useState(false)
  const inspect = useSubmit<ImportInspect>()
  const preview = useSubmit<ImportPreview>()
  const commit = useSubmit<ImportResult>()

  const workbook = inspect.result
  const current = workbook?.sheets.find((s) => s.name === sheet)
  // A preview counts only while the file, sheet, columns and date order are the ones it was made for.
  const [previewFor, setPreviewFor] = useState('')
  const choices = JSON.stringify({ sheet, mapping, dateOrder, file: workbook?.file_sha256 })
  const shown = preview.result && previewFor === choices ? preview.result : null

  const rows = useMemo(() => {
    const all = shown?.rows ?? []
    if (filter === 'attention') return all.filter((r) => r.outcome === 'flag' || r.outcome === 'reject')
    if (filter === 'all') return all
    return all.filter((r) => r.outcome === filter)
  }, [shown, filter])

  if (workflow.error || settings.error) return <FieldPage><ErrorCallout error={(workflow.error ?? settings.error)!} /></FieldPage>
  if (!workflow.data || !settings.data) return <FieldPage><LoadingState title={t('Loading…', 'আসছে…')} /></FieldPage>

  const body = file ? { content: new Blob([file.data], { type: XLSX }), contentType: XLSX } : undefined
  const mappingText = JSON.stringify(mapping)
  const missingRequired = (workbook?.required ?? []).filter((f) => !mapping[f])

  const choose = async (picked: File | undefined) => {
    if (!picked) return
    const data = await picked.arrayBuffer()
    setFile({ name: picked.name, data })
    preview.reset()
    commit.reset()
    setKeep([])
    const answer = await inspect.submit(() =>
      api<ImportInspect>(`${base}/inspect`, { method: 'POST', body: { content: new Blob([data], { type: XLSX }), contentType: XLSX } }),
    )
    const first = answer?.sheets[0]
    if (first) {
      setSheet(first.name)
      setMapping(first.suggested)
      setDateOrder('auto')
    }
  }

  const pickSheet = (name: string) => {
    setSheet(name)
    const s = workbook?.sheets.find((x) => x.name === name)
    if (s) setMapping(s.suggested)
    setKeep([])
  }

  const runPreview = async () => {
    if (!body) return
    setKeep([])
    const made = choices
    const answer = await preview.submit(() =>
      api<ImportPreview>(`${base}/preview`, { method: 'POST', body, query: { sheet, mapping: mappingText, date_order: dateOrder } }),
    )
    if (answer) {
      setPreviewFor(made)
      setFilter(answer.counts.flag + answer.counts.reject > 0 ? 'attention' : 'add')
    }
  }

  const save = async () => {
    if (!body || !shown) return
    const answer = await commit.submit(() =>
      api<ImportResult>(`${base}/commit`, {
        method: 'POST',
        body,
        query: {
          sheet,
          mapping: mappingText,
          date_order: dateOrder,
          preview_token: shown.preview_token,
          keep_flagged: keep.join(','),
          file_name: file?.name ?? 'workbook.xlsx',
        },
      }),
    )
    setConfirm(false)
    if (answer) forgetShop(merchantId)
  }

  const startAgain = () => {
    setFile(null)
    inspect.reset()
    preview.reset()
    commit.reset()
    setSheet('')
    setMapping({})
    setKeep([])
    if (input.current) input.current.value = ''
  }

  const toAdd = shown ? shown.counts.add + keep.length : 0
  const result = commit.result

  return (
    <FieldPage>
      <BackLink to={`${back}/records`}>{t('Back to business records', 'ব্যবসার রেকর্ডে ফিরে যান')}</BackLink>
      <ShopHeader status={workflow.data} title={t('Import purchases from Excel', 'এক্সেল থেকে কেনাকাটা আমদানি')} />
      <DemoLine settings={settings.data} />

      {result ? (
        <Notice tone="success" title={t(`${count(result.added)} purchases added`, `${count(result.added)}টি কেনাকাটা যোগ হয়েছে`)}>
          <span className="flex flex-col gap-2">
            <span>
              {t(
                `Already saved, skipped: ${count(result.skipped)} · possible duplicates left out: ${count(result.flagged_left)} · kept after checking: ${count(result.flagged_kept)} · could not be read: ${count(result.rejected)}.`,
                `আগেই সংরক্ষিত, বাদ: ${count(result.skipped)} · হয়তো দুবার, বাদ: ${count(result.flagged_left)} · দেখে রাখা হয়েছে: ${count(result.flagged_kept)} · পড়া যায়নি: ${count(result.rejected)}।`,
              )}
            </span>
            <span className="flex flex-wrap items-center gap-2">
              <StatusTag status={RECORD_STATUS.imported_spreadsheet} />
              {result.assessment.status !== 'no_application' && <StatusTag status={ASSESSMENT_STATUS[result.assessment.status]} />}
            </span>
            {result.rejected > 0 && (
              <span className="text-[13px] text-body">
                {t('Rows that could not be read were not saved. Fix them in the file and import it again: rows already saved will be skipped.', 'যে সারি পড়া যায়নি তা সংরক্ষণ হয়নি। ফাইলে ঠিক করে আবার আমদানি করুন: আগে সংরক্ষিত সারি বাদ যাবে।')}
              </span>
            )}
            <span className="flex flex-wrap gap-3 pt-1">
              <Link to={back} className="inline-flex min-h-11 items-center font-semibold">
                {t('Back to the shop', 'দোকানে ফিরে যান')}
              </Link>
              <Button variant="outline" onClick={startAgain}>
                {t('Import another file', 'আরেকটি ফাইল আমদানি করুন')}
              </Button>
            </span>
          </span>
        </Notice>
      ) : (
        <>
          <ol className="m-0 flex list-none flex-col gap-4 p-0">
            <Step n={1} title={t('Choose the Excel file', 'এক্সেল ফাইল বেছে নিন')}>
              <p className="m-0 text-[15px] text-body">
                {t(
                  `An .xlsx workbook with one purchase per row and a header row on top: up to ${settings.data.import_max_file_mb} MB and ${count(settings.data.import_max_rows)} rows. Nothing is saved until you confirm. The file itself is not kept.`,
                  `প্রতি সারিতে একটি কেনাকাটা আর ওপরে শিরোনাম-সারিসহ একটি .xlsx ওয়ার্কবুক: সর্বোচ্চ ${settings.data.import_max_file_mb} MB ও ${count(settings.data.import_max_rows)}টি সারি। আপনি নিশ্চিত না করা পর্যন্ত কিছু সংরক্ষণ হয় না। ফাইলটি রাখা হয় না।`,
                )}
              </p>
              <input
                ref={input}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="sr-only"
                id="workbook"
                onChange={(e) => void choose(e.target.files?.[0])}
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant={file ? 'outline' : 'primary'} size="lg" onClick={() => input.current?.click()} disabled={inspect.pending}>
                  <Upload size={18} aria-hidden="true" />
                  {file ? t('Choose another file', 'অন্য ফাইল বেছে নিন') : t('Choose file', 'ফাইল বেছে নিন')}
                </Button>
                {file && (
                  <span className="flex min-w-0 items-center gap-2 text-[15px] text-ink">
                    <FileSpreadsheet size={18} className="shrink-0 text-lens-dark" aria-hidden="true" />
                    <span className="truncate">{file.name}</span>
                  </span>
                )}
              </div>
              {inspect.pending && <p className="m-0 text-sm text-body">{t('Reading the workbook…', 'ওয়ার্কবুক পড়া হচ্ছে…')}</p>}
              {inspect.error && <ErrorCallout error={inspect.error} />}
            </Step>

            {workbook && current && (
              <Step n={2} title={t('Say which column is which', 'কোন কলামে কী আছে বলুন')}>
                {workbook.sheets.length > 1 && (
                  <Field label={t('Sheet', 'শিট')} required>
                    <Select value={sheet} onChange={(e) => pickSheet(e.target.value)} options={workbook.sheets.map((s) => ({ value: s.name, label: t(`${s.name} (${count(s.rows)} ${s.rows === 1 ? 'row' : 'rows'})`, `${s.name} (${count(s.rows)}টি সারি)`) }))} />
                  </Field>
                )}
                <p className="m-0 text-[15px] text-body">
                  {t(`${count(current.rows)} rows below the header. The columns are guessed from their names; check them.`, `শিরোনামের নিচে ${count(current.rows)}টি সারি। কলামগুলো নাম দেখে আন্দাজ করা হয়েছে; মিলিয়ে নিন।`)}
                  {current.truncated && t(' Only the first rows are read; split the file for the rest.', ' শুধু প্রথম সারিগুলো পড়া হবে; বাকিগুলোর জন্য ফাইল ভাগ করুন।')}
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  {workbook.fields.map((f) => {
                    const words = FIELD_WORDS[f]
                    const required = workbook.required.includes(f)
                    return (
                      <Field key={f} label={pick(words, lang)} hint={pick(words.hint, lang)} required={required}>
                        <Select
                          value={mapping[f] ?? NONE}
                          onChange={(e) => setMapping({ ...mapping, [f]: e.target.value || null })}
                          placeholder={required ? t('Choose a column', 'একটি কলাম বেছে নিন') : undefined}
                          options={[
                            ...(required ? [] : [{ value: NONE, label: t('Not in this sheet', 'এই শিটে নেই') }]),
                            ...current.columns.filter(Boolean).map((c) => ({ value: c, label: c })),
                          ]}
                        />
                      </Field>
                    )
                  })}
                </div>
                {shown?.date_order_needed || dateOrder !== 'auto' ? (
                  <Field label={t('How are dates written?', 'তারিখ কীভাবে লেখা?')} required hint={t('Some dates, like 03/04/2026, can be read two ways.', 'কিছু তারিখ, যেমন 03/04/2026, দুইভাবে পড়া যায়।')}>
                    <ChoiceGroup
                      name="date-order"
                      value={dateOrder === 'auto' ? null : dateOrder}
                      onChange={(v) => setDateOrder(v as 'dmy' | 'mdy')}
                      options={[
                        { value: 'dmy', label: t('Day first: 25/07/2026', 'আগে দিন: 25/07/2026') },
                        { value: 'mdy', label: t('Month first: 07/25/2026', 'আগে মাস: 07/25/2026') },
                      ]}
                    />
                  </Field>
                ) : null}
                <FormActions>
                  <Button size="lg" onClick={() => void runPreview()} disabled={preview.pending || missingRequired.length > 0}>
                    {preview.pending ? t('Checking rows…', 'সারি দেখা হচ্ছে…') : shown ? t('Check rows again', 'আবার সারি দেখুন') : t('Check the rows', 'সারিগুলো দেখুন')}
                  </Button>
                  {missingRequired.length > 0 && <span className="text-[13px] text-amber-text">{t('Choose the date and amount columns first.', 'আগে তারিখ ও অঙ্কের কলাম বেছে নিন।')}</span>}
                  {preview.result && !shown && !preview.pending && (
                    <span className="text-[13px] text-amber-text">{t('Your choices changed. Check the rows again before saving.', 'আপনার পছন্দ বদলেছে। সংরক্ষণের আগে আবার সারি দেখুন।')}</span>
                  )}
                </FormActions>
                {preview.error && <ErrorCallout error={preview.error} />}
              </Step>
            )}

            {shown && (
              <Step n={3} title={t('Check every row', 'প্রতিটি সারি দেখুন')}>
                <dl className="m-0 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Count label={t('Will be added', 'যোগ হবে')} value={shown.counts.add} tone="text-lens-dark" />
                  <Count label={t('Already saved', 'আগেই সংরক্ষিত')} value={shown.counts.skip} tone="text-ink-2" />
                  <Count label={t('To check', 'দেখতে হবে')} value={shown.counts.flag} tone="text-amber-text" />
                  <Count label={t('Cannot be read', 'পড়া যায়নি')} value={shown.counts.reject} tone="text-peri-text" />
                </dl>
                {shown.date_order_needed && (
                  <Notice tone="warning" title={t('Choose how dates are written', 'তারিখ কীভাবে লেখা তা বেছে নিন')}>
                    {t('Some dates can be read two ways. Choose day first or month first above, then check the rows again.', 'কিছু তারিখ দুইভাবে পড়া যায়। ওপরে আগে দিন বা আগে মাস বেছে নিয়ে আবার সারি দেখুন।')}
                  </Notice>
                )}
                <FilterSegments<Filter>
                  label={t('Show', 'দেখান')}
                  value={filter}
                  onChange={setFilter}
                  options={[
                    { value: 'attention', label: t(`Needs attention (${shown.counts.flag + shown.counts.reject})`, `মনোযোগ দরকার (${shown.counts.flag + shown.counts.reject})`) },
                    { value: 'add', label: t(`To add (${shown.counts.add})`, `যোগ হবে (${shown.counts.add})`) },
                    { value: 'skip', label: t(`Already saved (${shown.counts.skip})`, `আগেই সংরক্ষিত (${shown.counts.skip})`) },
                    { value: 'all', label: t('All', 'সব') },
                  ]}
                />
                {rows.length === 0 ? (
                  <p className="m-0 text-sm text-body">{t('No rows here.', 'এখানে কোনো সারি নেই।')}</p>
                ) : (
                  <ul className="m-0 flex max-h-[520px] list-none flex-col overflow-y-auto rounded-[12px] border border-line p-0">
                    {rows.map((row) => (
                      <RowItem
                        key={row.row_number}
                        row={row}
                        kept={keep.includes(row.row_number)}
                        onKeep={(on) => setKeep(on ? [...keep, row.row_number] : keep.filter((n) => n !== row.row_number))}
                      />
                    ))}
                  </ul>
                )}
              </Step>
            )}

            {shown && (
              <Step n={4} title={t('Save', 'সংরক্ষণ')}>
                <p className="m-0 text-[15px] text-body">
                  {t(
                    'Saved rows are marked “From a spreadsheet · not verified”. Rows that cannot be read are not saved.',
                    'সংরক্ষিত সারিতে লেখা থাকবে “স্প্রেডশিট থেকে · যাচাই হয়নি”। যে সারি পড়া যায়নি তা সংরক্ষণ হবে না।',
                  )}
                </p>
                {commit.error && <ErrorCallout error={commit.error} />}
                <FormActions>
                  <Button size="lg" onClick={() => setConfirm(true)} disabled={commit.pending || toAdd === 0 || shown.date_order_needed}>
                    {t(`Save ${count(toAdd)} purchases`, `${count(toAdd)}টি কেনাকাটা সংরক্ষণ করুন`)}
                  </Button>
                  {toAdd === 0 && <span className="text-[13px] text-body">{t('Nothing new to save.', 'নতুন কিছু সংরক্ষণের নেই।')}</span>}
                </FormActions>
              </Step>
            )}
          </ol>
        </>
      )}

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t(`Save ${count(toAdd)} purchases?`, `${count(toAdd)}টি কেনাকাটা সংরক্ষণ করবেন?`)}
        confirmLabel={t('Save purchases', 'কেনাকাটা সংরক্ষণ করুন')}
        onConfirm={() => void save()}
        pending={commit.pending}
      >
        {t(
          `From ${file?.name ?? 'the file'}, sheet ${sheet}. ${keep.length ? `Includes ${count(keep.length)} row(s) you kept after checking.` : ''}`,
          `${file?.name ?? 'ফাইল'} থেকে, শিট ${sheet}। ${keep.length ? `দেখে রাখা ${count(keep.length)}টি সারিসহ।` : ''}`,
        )}
      </ConfirmDialog>
    </FieldPage>
  )
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex flex-col gap-4 rounded-card border border-card-line bg-white p-4 sm:p-5">
      <h2 className="m-0 flex items-center gap-3 text-lg font-semibold">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-strong-chip text-sm font-bold text-lens-dark" aria-hidden="true">
          {n}
        </span>
        {title}
      </h2>
      {children}
    </li>
  )
}

function Count({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-[10px] border border-line bg-ground px-3 py-2">
      <dt className="text-[13px] text-muted-2">{label}</dt>
      <dd className={`m-0 font-display text-2xl font-bold tabular ${tone}`}>{count(value)}</dd>
    </div>
  )
}

function RowItem({ row, kept, onKeep }: { row: ImportRow; kept: boolean; onKeep: (on: boolean) => void }) {
  const t = useT()
  const lang = useLang()
  return (
    <li className="flex flex-col gap-1.5 border-t border-line px-3 py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-muted-2">{t(`Row ${row.row_number}`, `সারি ${row.row_number}`)}</span>
        <StatusTag status={OUTCOME[row.outcome]} />
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[15px]">
        <span className="text-ink">
          {row.purchase_date ? fmtDate(row.purchase_date) : t('No date', 'তারিখ নেই')}
          {row.category && <span className="text-body"> · {row.category}</span>}
          {row.invoice_reference && <span className="text-muted-2"> · {t('memo', 'মেমো')} {row.invoice_reference}</span>}
        </span>
        <span className="font-semibold text-ink tabular">{row.amount_bdt != null ? taka(row.amount_bdt) : '—'}</span>
      </div>
      <span className="text-[13px] text-body">{pick(REASON[row.code] ?? { en: row.code, bn: row.code }, lang)}</span>
      {row.outcome === 'flag' && (
        <label className="flex min-h-11 cursor-pointer items-center gap-2.5 self-start text-[15px] font-medium text-ink">
          <input type="checkbox" checked={kept} onChange={(e) => onKeep(e.target.checked)} className="size-4 accent-[#00735a]" />
          {t('It is a different purchase: keep it', 'এটি আলাদা কেনাকাটা: রাখুন')}
        </label>
      )}
    </li>
  )
}
