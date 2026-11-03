/**
 * Pieces every Field Mode screen shares: the demo settings, the shop's workflow status,
 * the narrow page column, the shop header and the "saved" message.
 *
 * Field Mode runs under the officer demo identity: in this prototype the server does not
 * separate field staff from deciding officers, and the screen says so.
 */
import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { DemoSettings, RecordSaved, WorkflowStatus } from '@/api/types'
import { Notice } from '@/components/Notice'
import { StatusTag } from '@/components/StatusTag'
import { fmtDate } from '@/lib/format'
import { useSession } from '@/app/session-context'
import { pick, useLang, useT } from '@/lib/i18n'
import { ASSESSMENT_STATUS, RECORD_STATUS } from '@/lib/statuses'
import { SHOP_TYPE_WORDS, wordsFor } from '@/lib/fieldWords'




/** The narrow column of a field screen (comfortable on a phone, centred on a desk). */
export function FieldPage({ children }: { children: ReactNode }) {
  return <div className="box-border flex w-full max-w-[760px] flex-col gap-5 px-4 pt-5 pb-14 sm:px-8">{children}</div>
}

/** The line every field screen carries: in the sandbox, the demo calendar's end; for a real
 * account, that records are real and dated up to today. */
export function DemoLine({ settings }: { settings?: DemoSettings }) {
  const t = useT()
  const { mode } = useSession()
  if (!settings) return null
  if (mode === 'account') {
    return (
      <p className="m-0 text-[13px] leading-[19px] text-muted-2">
        {t(
          `Real records. Business dates up to today (${fmtDate(settings.calendar_end)}); the time of saving and your name are kept with each one.`,
          `আসল রেকর্ড। ব্যবসার তারিখ আজ (${fmtDate(settings.calendar_end)}) পর্যন্ত; প্রতিটির সাথে সংরক্ষণের সময় ও আপনার নাম রাখা হয়।`,
        )}
      </p>
    )
  }
  return (
    <p className="m-0 text-[13px] leading-[19px] text-muted-2">
      {t(
        `Sandbox: business dates end on ${fmtDate(settings.calendar_end)}; the real time of saving is kept separately.`,
        `স্যান্ডবক্স: ব্যবসার তারিখ ${fmtDate(settings.calendar_end)}-এ শেষ; সংরক্ষণের আসল সময় আলাদা রাখা হয়।`,
      )}
    </p>
  )
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-medium no-underline">
      <ArrowLeft size={17} aria-hidden="true" />
      {children}
    </Link>
  )
}

/** The shop's name and permanent id, the way staff recognise it. */
export function ShopHeader({ status, title }: { status: WorkflowStatus; title?: string }) {
  const t = useT()
  const lang = useLang()
  const shop = status.merchant
  return (
    <header className="flex flex-col gap-1">
      {title && <span className="text-sm font-semibold text-lens-dark">{title}</span>}
      <h1 className="m-0 text-[26px] leading-8 font-bold tracking-[-0.01em] break-words">{shop.shop_name ?? shop.merchant_id}</h1>
      <p className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-body">
        <span className="rounded bg-neutral-chip px-1.5 py-0.5 font-mono text-[13px] text-ink-2" aria-label={t('CredLens id', 'CredLens আইডি')}>
          {shop.merchant_id}
        </span>
        {[shop.area, shop.district, shop.shop_type ? wordsFor(SHOP_TYPE_WORDS, shop.shop_type, lang) : null].filter(Boolean).join(' · ')}
      </p>
    </header>
  )
}

/** "Saved", with what is known about the record and what happened to the assessment. */
export function SavedNotice({ saved, what }: { saved: RecordSaved; what: string }) {
  const t = useT()
  const lang = useLang()
  const assessment = ASSESSMENT_STATUS[saved.assessment.status]
  const tone = saved.assessment.status === 'not_updated' ? 'warning' : 'success'
  return (
    <Notice
      tone={tone}
      title={saved.repeat ? t(`${what} was already saved a moment ago; nothing new was added.`, `${what} একটু আগেই সংরক্ষিত হয়েছিল; নতুন কিছু যোগ হয়নি।`) : t(`${what} saved`, `${what} সংরক্ষিত`)}
    >
      <span className="flex flex-col gap-2">
        <span className="flex flex-wrap gap-2">
          <StatusTag status={RECORD_STATUS[saved.status]} />
          <StatusTag status={assessment} />
        </span>
        <span>
          {assessment ? pick(assessment.help, lang) : saved.assessment.message}
          {saved.counts_for_assessment === false &&
            ` ${t('This record is dated on or after the application date, so it does not count for this application.', 'এই রেকর্ডের তারিখ আবেদনের দিন বা পরে, তাই এই আবেদনে গোনা হবে না।')}`}
        </span>
        {saved.entered_at && (
          <span className="text-[13px] text-muted-2">
            {t(`Business date ${fmtDate(saved.business_date)} · saved at ${saved.entered_at.replace('T', ' ')} UTC`, `ব্যবসার তারিখ ${fmtDate(saved.business_date)} · সংরক্ষণ ${saved.entered_at.replace('T', ' ')} UTC`)}
          </span>
        )}
      </span>
    </Notice>
  )
}

