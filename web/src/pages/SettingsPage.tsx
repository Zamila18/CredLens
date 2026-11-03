/**
 * Demo settings: the rules this demo runs on, read from the API (GET /demo/settings,
 * GET /health, GET /model/card). Read-only for every role: the settings live in
 * config/default.yaml and nothing here can change them.
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { DemoSettings, Health, ModelCard, OrganizationOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { count, fmtDate, taka } from '@/lib/format'
import { CATEGORY_WORDS, METHOD_WORDS, wordsFor } from '@/lib/fieldWords'
import { MODE_TEXT, pick, useLang, useT } from '@/lib/i18n'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-t border-line py-3 first:border-t-0 sm:grid-cols-[260px_minmax(0,1fr)] sm:gap-6">
      <dt className="text-sm text-muted-2">{label}</dt>
      <dd className="m-0 text-[15px] text-ink">{children}</dd>
    </div>
  )
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1 rounded-card border border-card-line bg-card p-4 sm:p-5">
      <h2 className="m-0 pb-1 text-[17px] font-semibold">{title}</h2>
      <dl className="m-0">{children}</dl>
    </section>
  )
}

export function SettingsPage() {
  const t = useT()
  const lang = useLang()
  const settings = useApi<DemoSettings>('/demo/settings')
  const health = useApi<Health>('/health')
  const card = useApi<ModelCard>(health.data ? '/model/card' : null)
  const org = useApi<OrganizationOut>('/organization')
  const s = settings.data
  return (
    <Page>
      <PageHeader
        title={t('Settings', 'সেটিংস')}
        description={t('Your organisation and the rules this installation runs on. Read-only: they are set in the API’s configuration.', 'আপনার প্রতিষ্ঠান আর এই ইনস্টলেশনের নিয়ম। শুধু দেখার জন্য: এগুলো API-র কনফিগারেশনে ঠিক করা।')}
      />
      {settings.error ? (
        <ErrorCallout error={settings.error} />
      ) : !s ? (
        <LoadingState title={t('Loading the settings…', 'সেটিংস আসছে…')} />
      ) : (
        <>
          {org.data && (
            <Block title={t('Organisation', 'প্রতিষ্ঠান')}>
              <Row label={t('Name', 'নাম')}>
                {org.data.name} <span className="font-mono text-[13px] text-muted-2">({org.data.organization_id})</span>
              </Row>
              <Row label={t('Environment', 'পরিবেশ')}>
                {org.data.environment === 'benchmark'
                  ? t('Benchmark: offline synthetic data, never a real company', 'বেঞ্চমার্ক: অফলাইন সিনথেটিক ডেটা, কোনো আসল প্রতিষ্ঠান নয়')
                  : org.data.environment}
              </Row>
              <Row label={t('Country', 'দেশ')}>{org.data.country}</Row>
              <Row label={t('Languages', 'ভাষা')}>{org.data.languages.join(', ')}</Row>
              <Row label={t('Currency', 'মুদ্রা')}>{org.data.currency}</Row>
              <Row label={t('Time zone', 'সময় অঞ্চল')}>{org.data.timezone}</Row>
              <Row label={t('Data access', 'ডেটা প্রবেশাধিকার')}>{t('Only this organisation’s merchants, records and decisions', 'শুধু এই প্রতিষ্ঠানের মার্চেন্ট, রেকর্ড ও সিদ্ধান্ত')}</Row>
            </Block>
          )}
          <Block title={t('Environment', 'পরিবেশ')}>
            <Row label={t('Data source', 'ডেটার উৎস')}>
              {health.data ? (
                <>
                  {pick(MODE_TEXT[health.data.data_mode], lang)} <span className="font-mono text-[13px] text-muted-2">({health.data.data_mode})</span>
                </>
              ) : (
                '—'
              )}
            </Row>
            <Row label={t('Model in use', 'ব্যবহৃত মডেল')}>
              {card.data ? <span className="font-mono text-[13px] break-all">{card.data.model_version}</span> : '—'}{' '}
              <Link to="/app/model" className="text-sm">
                {t('Model card', 'মডেল কার্ড')}
              </Link>
            </Row>
            <Row label={t('New records', 'নতুন রেকর্ড')}>
              {s.synthetic_only
                ? t('Accepted as synthetic demo records only', 'শুধু সিনথেটিক ডেমো রেকর্ড হিসেবে নেওয়া হয়')
                : t('Refused: synthetic-only mode is off, and there is no real-data path', 'বন্ধ: শুধু-সিনথেটিক মোড বন্ধ, আর আসল ডেটার কোনো পথ নেই')}
            </Row>
            <Row label={t('Sign-in', 'সাইন-ইন')}>{t('Demo roles only (a token per role). No passwords and no real identity check.', 'শুধু ডেমো ভূমিকা (প্রতি ভূমিকায় একটি টোকেন)। কোনো পাসওয়ার্ড বা আসল পরিচয়-যাচাই নেই।')}</Row>
          </Block>
          <Block title={t('Calendar', 'ক্যালেন্ডার')}>
            <Row label={t('Last business day', 'শেষ ব্যবসার দিন')}>{fmtDate(s.calendar_end)}</Row>
            <Row label={t('Dates after it', 'এর পরের তারিখ')}>{t('Refused for every record', 'সব রেকর্ডে বাতিল')}</Row>
            <Row label={t('Real time of saving', 'সংরক্ষণের আসল সময়')}>{t('Kept separately on every record', 'প্রতিটি রেকর্ডে আলাদা রাখা হয়')}</Row>
          </Block>
          <Block title={t('Consent', 'অনুমতি')}>
            <Row label={t('Kind', 'ধরন')}>{t('Simulated consent (synthetic demo): not a legal authorisation', 'সিমুলেটেড অনুমতি (সিনথেটিক ডেমো): আইনি অনুমোদন নয়')}</Row>
            <Row label={t('Wording version', 'লেখার সংস্করণ')}>
              <span className="font-mono text-[13px]">{s.consent_wording_version}</span>
            </Row>
            <Row label={t('Categories', 'ধরনসমূহ')}>{s.consent_categories.map((c) => wordsFor(CATEGORY_WORDS, c, lang)).join(', ')}</Row>
            <Row label={t('How an answer is given', 'উত্তর কীভাবে দেওয়া হয়')}>{s.consent_methods.map((m) => wordsFor(METHOD_WORDS, m, lang)).join(', ')}</Row>
            <Row label={t('Valid for', 'বৈধতা')}>{t(`${count(s.consent_valid_days)} days from its business date`, `ব্যবসার তারিখ থেকে ${count(s.consent_valid_days)} দিন`)}</Row>
          </Block>
          <Block title={t('Applications and records', 'আবেদন ও রেকর্ড')}>
            <Row label={t('Applications per shop', 'প্রতি দোকানে আবেদন')}>{t('One, ever (this prototype)', 'একটি, চিরকাল (এই প্রোটোটাইপে)')}</Row>
            <Row label={t('Largest request accepted', 'সর্বোচ্চ গ্রহণযোগ্য অনুরোধ')}>
              {taka(s.max_requested_bdt)} <span className="text-sm text-muted-2">{t('(a guard against typing errors, not a credit policy)', '(টাইপের ভুল ঠেকাতে, ঋণনীতি নয়)')}</span>
            </Row>
            <Row label={t('Excel purchase import', 'এক্সেল কেনাকাটা আমদানি')}>{t(`Up to ${s.import_max_file_mb} MB and ${count(s.import_max_rows)} rows per sheet`, `সর্বোচ্চ ${s.import_max_file_mb} MB ও প্রতি শিটে ${count(s.import_max_rows)}টি সারি`)}</Row>
            <Row label={t('Credit range guidance', 'ঋণের পরিসীমার নির্দেশনা')}>
              {s.range_policy_enabled
                ? t('A policy is switched on, but no formula has been approved, so no amount is shown', 'একটি নীতি চালু, কিন্তু কোনো সূত্র অনুমোদিত হয়নি, তাই কোনো অঙ্ক দেখানো হয় না')
                : t('Not configured: no amount is ever shown', 'ঠিক করা হয়নি: কোনো অঙ্ক দেখানো হয় না')}
            </Row>
          </Block>
        </>
      )}
    </Page>
  )
}
