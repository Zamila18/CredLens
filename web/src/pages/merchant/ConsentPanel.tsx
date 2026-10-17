/**
 * Consent on the merchant page (approved design: 03-merchant-desktop.png): the merchant's
 * consent as GET /merchants/{id}/consent reads it live from the database (an audited read).
 * "Checked for" is the data's last day (the reference day of the demo data), not the
 * computer's clock. There is no revoke button on purpose: the scorer reads consent once at
 * start-up, so a revoke would not stop scoring until the API restarts.
 */
import type { ConsentView } from '@/api/types'
import { Chip } from '@/components/BandChip'
import { Section } from '@/components/Page'
import { categoriesOf, humanize } from '@/lib/consent'
import { fmtDate } from '@/lib/format'
import { PURPOSE_TEXT, categoryWord, pick, useLang, useT } from '@/lib/i18n'

export function CategoryChip({ children }: { children: string }) {
  return <span className="inline-flex rounded-full border border-mint-line bg-mint-2 px-2.5 py-0.5 text-[13px] text-lens-dark">{children}</span>
}

export function ConsentPanel({ consent }: { consent: ConsentView }) {
  const t = useT()
  const lang = useLang()
  return (
    <Section
      id="consent"
      title={t('Consent', 'অনুমতি')}
      answer={
        <>
          {t('Checked for', 'যাচাইয়ের তারিখ')} <b className="font-semibold text-ink tabular">{fmtDate(consent.as_of)}</b>
          {t(', the last day in the data.', ', ডেটার শেষ দিন।')}
        </>
      }
      aside={
        consent.valid ? (
          <Chip tone="strong" className="px-3 py-1 text-[13px]">
            {t('Valid', 'বৈধ')}
          </Chip>
        ) : (
          <Chip className="px-3 py-1 text-[13px]">{t('No valid consent', 'বৈধ অনুমতি নেই')}</Chip>
        )
      }
    >
      {consent.data_categories.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-ink-2">{t('Data allowed', 'যে ডেটার অনুমতি আছে')}</span>
          {consent.data_categories.map((c) => (
            <CategoryChip key={c}>{categoryWord(c, lang)}</CategoryChip>
          ))}
        </div>
      ) : (
        <p className="m-0 text-[15px] text-body">{t('No data may be used for this merchant.', 'এই মার্চেন্টের কোনো ডেটা ব্যবহার করা যাবে না।')}</p>
      )}
      {consent.records.length > 0 ? (
        <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Consent records', 'অনুমতির রেকর্ড')} tabIndex={0}>
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead className="bg-ground">
              <tr className="text-left text-[13px] text-muted-2">
                <th scope="col" className="px-4 py-2.5 font-medium">{t('Record', 'রেকর্ড')}</th>
                <th scope="col" className="px-4 py-2.5 font-medium">{t('Purpose', 'উদ্দেশ্য')}</th>
                <th scope="col" className="px-4 py-2.5 font-medium">{t('Granted', 'দেওয়া হয়েছে')}</th>
                <th scope="col" className="px-4 py-2.5 font-medium">{t('Expires', 'মেয়াদ শেষ')}</th>
                <th scope="col" className="px-4 py-2.5 font-medium">{t('Revoked', 'তুলে নেওয়া')}</th>
              </tr>
            </thead>
            <tbody>
              {consent.records.map((r, i) => (
                <tr key={r.consent_id ?? i} className="border-t border-line align-top">
                  <td className="px-4 py-3 font-mono">{r.consent_id ?? '—'}</td>
                  <td className="px-4 py-3">
                    <div>{r.purpose && PURPOSE_TEXT[r.purpose] ? pick(PURPOSE_TEXT[r.purpose], lang) : humanize(r.purpose)}</div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {categoriesOf(r.data_categories).map((c) => (
                        <CategoryChip key={c}>{categoryWord(c, lang)}</CategoryChip>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 tabular">{fmtDate(r.granted_at)}</td>
                  <td className="px-4 py-3 tabular">{fmtDate(r.expires_at)}</td>
                  <td className="px-4 py-3">{r.revoked_at ? fmtDate(r.revoked_at) : t('Not revoked', 'তুলে নেওয়া হয়নি')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="m-0 text-[15px] text-body">{t('No consent records exist for this merchant.', 'এই মার্চেন্টের কোনো অনুমতির রেকর্ড নেই।')}</p>
      )}
      <p className="m-0 text-[13px] text-muted-2">
        {t('Read live from the database; this read is audited.', 'ডেটাবেস থেকে সরাসরি পড়া; এই দেখাটা অডিটে লেখা হয়।')}
      </p>
    </Section>
  )
}
