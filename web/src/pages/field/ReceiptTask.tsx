/**
 * The merchant's data receipt (GET /merchants/{id}/receipt): what CredLens holds about the
 * shop, how and when each thing was recorded, and what to do about a mistake.
 *
 * Staff open it in the app and show or print it for the retailer: there is no merchant
 * login and no public link. It carries no score, no decision and no officer note, and it
 * never says a record came from a provider. Printing hides the app's navigation.
 */
import { Printer } from 'lucide-react'
import { useParams } from 'react-router'

import type { Receipt, ReceiptRecord } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Notice } from '@/components/Notice'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import { CATEGORY_WORDS, DELIVERY_STATUS_WORDS, METHOD_WORDS, OUTCOME_WORDS, PURPOSE_WORDS, wordsFor } from '@/lib/fieldWords'
import { useSession } from '@/app/session-context'
import { pick, useLang, useT, type Pair } from '@/lib/i18n'
import { RECORD_STATUS, SIMULATED_CONSENT } from '@/lib/statuses'
import { BackLink, FieldPage, ShopHeader } from './shared'
import { useWorkflow } from './fieldData'

const KIND: Record<ReceiptRecord['record_type'], Pair> = {
  merchant: { en: 'Shop details', bn: 'দোকানের তথ্য' },
  purchase: { en: 'Stock purchase', bn: 'মাল কেনা' },
  delivery: { en: 'Parcel delivery', bn: 'পার্সেল ডেলিভারি' },
  payment: { en: 'Loan repayment', bn: 'ঋণ পরিশোধ' },
  visit: { en: 'Field visit', bn: 'মাঠ পরিদর্শন' },
  application: { en: 'Application (a request, not a loan)', bn: 'আবেদন (অনুরোধ, ঋণ নয়)' },
}

function detail(record: ReceiptRecord, lang: 'en' | 'bn'): string | null {
  if (!record.detail) return null
  if (record.record_type === 'delivery') return wordsFor(DELIVERY_STATUS_WORDS, record.detail, lang)
  if (record.record_type === 'visit') return wordsFor(OUTCOME_WORDS, record.detail, lang)
  if (record.record_type === 'application') return wordsFor(PURPOSE_WORDS, record.detail, lang)
  return record.detail
}

export function ReceiptTask() {
  const t = useT()
  const { mode } = useSession()
  const lang = useLang()
  const { merchantId = '' } = useParams()
  const workflow = useWorkflow(merchantId)
  const receipt = useApi<Receipt>(`/merchants/${encodeURIComponent(merchantId)}/receipt`, undefined, { noCache: true })
  const back = `/app/field/shops/${encodeURIComponent(merchantId)}`

  const error = receipt.error ?? workflow.error
  if (error) return <FieldPage><BackLink to={back}>{t('Back to the shop', 'দোকানে ফিরে যান')}</BackLink><ErrorCallout error={error} /></FieldPage>
  if (!receipt.data || !workflow.data) return <FieldPage><LoadingState title={t('Making the receipt…', 'রসিদ তৈরি হচ্ছে…')} /></FieldPage>
  const r = receipt.data

  return (
    <FieldPage>
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <BackLink to={back}>{t('Back to the shop', 'দোকানে ফিরে যান')}</BackLink>
        <Button variant="outline" onClick={() => window.print()}>
          <Printer size={18} aria-hidden="true" />
          {t('Print', 'প্রিন্ট করুন')}
        </Button>
      </div>
      <ShopHeader status={workflow.data} title={t('Data receipt', 'তথ্যের রসিদ')} />

      <Notice tone="info" title={t('What CredLens holds about this shop', 'এই দোকান সম্পর্কে CredLens-এ যা আছে')}>
        {mode === 'account'
          ? t(
              'This receipt lists what was recorded about the shop, how and when, and by whom. It is not a loan offer, an approval or a decision.',
              'এই রসিদে আছে দোকান সম্পর্কে কী রাখা হয়েছে, কীভাবে, কখন ও কে রেখেছেন। এটি ঋণের প্রস্তাব, অনুমোদন বা সিদ্ধান্ত নয়।',
            )
          : t(
              'Synthetic demonstration: the shop and its records are made up. This receipt lists what was recorded, how and when. It is not a loan offer, an approval or a decision.',
              'সিনথেটিক ডেমো: দোকান ও তার রেকর্ড বানানো। এই রসিদে আছে কী রাখা হয়েছে, কীভাবে ও কখন। এটি ঋণের প্রস্তাব, অনুমোদন বা সিদ্ধান্ত নয়।',
            )}
      </Notice>
      <p className="m-0 text-[13px] text-muted-2">
        {t(
          `Made ${fmtBdTime(r.generated_at)} (Bangladesh time). Business dates in this demo end on ${fmtDate(r.calendar_end)}; the real time each record was saved is shown beside it.`,
          `তৈরি ${fmtBdTime(r.generated_at)} (বাংলাদেশ সময়)। এই ডেমোতে ব্যবসার তারিখ ${fmtDate(r.calendar_end)}-এ শেষ; প্রতিটি রেকর্ড সংরক্ষণের আসল সময় পাশে দেখানো।`,
        )}
      </p>

      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-white p-4 sm:p-5 print:border-line" aria-labelledby="r-consent">
        <h2 id="r-consent" className="m-0 text-lg font-semibold">{t('Consent', 'অনুমতি')}</h2>
        {r.consent.length === 0 ? (
          <p className="m-0 text-[15px] text-body">{t('No consent answer is recorded.', 'কোনো অনুমতির উত্তর রাখা হয়নি।')}</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {r.consent.map((c, i) => (
              <li key={i} className="flex flex-col gap-1 border-t border-line pt-3 first:border-t-0 first:pt-0">
                <span className="text-[15px] font-semibold text-ink">
                  {c.response === 'granted' ? t('The merchant agreed', 'মার্চেন্ট রাজি হয়েছেন') : t('The merchant did not agree', 'মার্চেন্ট রাজি হননি')}
                  {c.simulated && <span className="font-normal text-body"> · {pick(SIMULATED_CONSENT, lang)}</span>}
                </span>
                {c.response === 'granted' && (
                  <span className="text-[15px] text-ink-2">
                    {t('Covers: ', 'অন্তর্ভুক্ত: ')}
                    {c.categories.map((x) => wordsFor(CATEGORY_WORDS, x, lang)).join(', ')}
                  </span>
                )}
                <span className="text-[13px] text-muted-2">
                  {t(
                    `${wordsFor(METHOD_WORDS, c.method, lang)} · business date ${fmtDate(c.business_date)} · saved ${fmtBdTime(c.recorded_at)} · wording ${c.wording_version}`,
                    `${wordsFor(METHOD_WORDS, c.method, lang)} · ব্যবসার তারিখ ${fmtDate(c.business_date)} · সংরক্ষিত ${fmtBdTime(c.recorded_at)} · লেখার সংস্করণ ${c.wording_version}`,
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-white p-4 sm:p-5 print:border-line" aria-labelledby="r-records">
        <h2 id="r-records" className="m-0 text-lg font-semibold">
          {t(`Recorded information (${count(r.records.length)})`, `রাখা তথ্য (${count(r.records.length)})`)}
        </h2>
        <ul className="m-0 flex list-none flex-col p-0">
          {r.records.map((rec, i) => {
            const words = detail(rec, lang)
            const kind = CATEGORY_WORDS[rec.source_category] ? wordsFor(CATEGORY_WORDS, rec.source_category, lang) : null
            return (
              <li key={i} className="flex flex-col gap-1 border-t border-line py-2.5 first:border-t-0 print:break-inside-avoid">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <span className="text-[15px] text-ink">
                    <span className="font-semibold">{pick(KIND[rec.record_type], lang)}</span>
                    {words && <span className="text-body"> · {words}</span>}
                  </span>
                  {rec.amount_bdt != null && <span className="text-[15px] font-semibold text-ink tabular">{taka(rec.amount_bdt)}</span>}
                </div>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-2">
                  <StatusTag status={RECORD_STATUS[rec.status]} />
                  <span>
                    {t(
                      `${rec.business_date ? `business date ${fmtDate(rec.business_date)} · ` : ''}saved ${fmtBdTime(rec.entered_at)}${kind ? ` · consent category: ${kind}` : ''}`,
                      `${rec.business_date ? `ব্যবসার তারিখ ${fmtDate(rec.business_date)} · ` : ''}সংরক্ষিত ${fmtBdTime(rec.entered_at)}${kind ? ` · অনুমতির ধরন: ${kind}` : ''}`,
                    )}
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
        <p className="m-0 text-[13px] text-body">
          {mode === 'account'
            ? t(
                'Every record was typed in or imported by staff. None has been verified against another source yet.',
                'প্রতিটি রেকর্ড কর্মীরা লিখেছেন বা আমদানি করেছেন। কোনোটি এখনও অন্য উৎসের সাথে মিলিয়ে যাচাই করা হয়নি।',
              )
            : t(
                'Every record was typed in or imported by staff, or read from a sandbox test source. None came from a real business platform or provider, and none has been verified against one.',
                'প্রতিটি রেকর্ড কর্মীরা লিখেছেন বা আমদানি করেছেন, অথবা স্যান্ডবক্সের পরীক্ষামূলক উৎস থেকে পড়া। কোনোটি আসল ব্যবসায়িক প্ল্যাটফর্ম বা প্রতিষ্ঠান থেকে আসেনি, আর কোনোটি তাদের সাথে মিলিয়ে যাচাই করা হয়নি।',
              )}
        </p>
      </section>

      <section className="flex flex-col gap-2 rounded-card border border-amber-chip bg-amber-panel p-4 sm:p-5" aria-labelledby="r-wrong">
        <h2 id="r-wrong" className="m-0 text-lg font-semibold">{t('Something wrong?', 'কিছু ভুল?')}</h2>
        <p className="m-0 text-[15px] text-ink-2">
          {t(
            `Tell the staff member who recorded it which line looks wrong and why, quoting the shop id ${r.merchant.merchant_id}. They pass it to the credit officer reviewing the shop. Nothing is deleted: the original record stays on file.`,
            `কোন লাইনটি ভুল মনে হচ্ছে ও কেন, দোকানের আইডি ${r.merchant.merchant_id} বলে, যে কর্মী রেখেছেন তাঁকে জানান। তিনি দোকানটি পর্যালোচনাকারী ঋণ কর্মকর্তাকে জানাবেন। কিছু মোছা হয় না: মূল রেকর্ড রয়ে যায়।`,
          )}
        </p>
      </section>
    </FieldPage>
  )
}
