/**
 * Consent panel (not drawn in the mockup; DESIGN_SPEC section 6 item 1): the merchant's
 * consent as GET /merchants/{id}/consent reads it live from the database.
 * There is no revoke button on purpose: the scorer reads consent once at start-up,
 * so a revoke would not stop scoring until the API restarts.
 */
import type { ConsentView } from '@/api/types'
import { Chip } from '@/components/BandChip'
import { CheckIcon } from '@/components/icons'
import { Card } from '@/components/Page'
import { categoriesOf, humanize } from '@/lib/consent'
import { fmtDate } from '@/lib/format'
import { PURPOSE_TEXT, categoryWord, pick, useLang, useT } from '@/lib/i18n'

export function CategoryChip({ children }: { children: string }) {
  return <span className="inline-flex rounded-md border border-card-line bg-[#F1F3EE] px-2 py-0.5 text-xs text-ink-2">{children}</span>
}

export function ConsentPanel({ consent }: { consent: ConsentView }) {
  const t = useT()
  const lang = useLang()
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Consent', 'অনুমতি')}</h2>
        {consent.valid ? (
          <Chip tone="strong" className="px-2.5 py-1">
            <CheckIcon /> {t('Valid', 'বৈধ')}
          </Chip>
        ) : (
          <Chip className="px-2.5 py-1 shadow-[inset_0_0_0_1.5px_#9AA39E]">{t('No valid consent', 'বৈধ অনুমতি নেই')}</Chip>
        )}
      </div>
      <p className="m-0 text-[13px] text-muted">
        {t('Checked for', 'যাচাইয়ের তারিখ')} <span className="font-mono tabular">{fmtDate(consent.as_of)}</span>
        {t(', the last day in the data.', ', ডেটার শেষ দিন।')}
      </p>
      {consent.data_categories.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">{t('Data allowed', 'যে ডেটার অনুমতি আছে')}</span>
          <div className="flex flex-wrap gap-1.5">
            {consent.data_categories.map((c) => (
              <CategoryChip key={c}>{categoryWord(c, lang)}</CategoryChip>
            ))}
          </div>
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">{t('No data may be used for this merchant.', 'এই মার্চেন্টের কোনো ডেটা ব্যবহার করা যাবে না।')}</p>
      )}
      {consent.records.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">{t('Record', 'রেকর্ড')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Purpose', 'উদ্দেশ্য')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Granted', 'দেওয়া হয়েছে')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Expires', 'মেয়াদ শেষ')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Revoked', 'তুলে নেওয়া')}</th>
              </tr>
            </thead>
            <tbody>
              {consent.records.map((r, i) => (
                <tr key={r.consent_id ?? i} className="border-t border-line-soft align-top">
                  <td className="py-2 pr-2 font-mono">{r.consent_id ?? '—'}</td>
                  <td className="py-2 pr-2">
                    <div>{r.purpose && PURPOSE_TEXT[r.purpose] ? pick(PURPOSE_TEXT[r.purpose], lang) : humanize(r.purpose)}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {categoriesOf(r.data_categories).map((c) => (
                        <CategoryChip key={c}>{categoryWord(c, lang)}</CategoryChip>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.granted_at)}</td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.expires_at)}</td>
                  <td className="py-2 font-mono tabular">{fmtDate(r.revoked_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">{t('No consent records exist for this merchant.', 'এই মার্চেন্টের কোনো অনুমতির রেকর্ড নেই।')}</p>
      )}
      <p className="m-0 text-xs text-muted-2">
        {t(
          'Read live from the database; this read is audited. There is no revoke button here on purpose.',
          'ডেটাবেস থেকে সরাসরি পড়া; এই দেখাটা অডিটে লেখা হয়। এখানে অনুমতি তুলে নেওয়ার বোতাম ইচ্ছা করেই নেই।',
        )}
      </p>
    </Card>
  )
}
