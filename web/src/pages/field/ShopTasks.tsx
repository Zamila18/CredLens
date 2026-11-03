/**
 * One shop in Field Mode: what has been done, and the four tasks.
 *
 * Calls GET /merchants/{id}/workflow (audited). Every status shown comes from the saved
 * records: consent, record counts, the application and its assessment. A task that cannot
 * be done yet says why (consent first), instead of a button that fails.
 */
import type { LucideIcon } from 'lucide-react'
import { ChevronRight, ClipboardCheck, FileSignature, MapPin, ReceiptText, ScrollText, ShieldCheck } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'

import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Notice } from '@/components/Notice'
import { StatusTag } from '@/components/StatusTag'
import { count, taka } from '@/lib/format'
import { NEXT_STEP_WORDS, wordsFor, CATEGORY_WORDS } from '@/lib/fieldWords'
import { useSession } from '@/app/session-context'
import { pick, useLang, useT } from '@/lib/i18n'
import { ASSESSMENT_STATUS, LOAN_KIND } from '@/lib/statuses'
import { cn } from '@/lib/utils'
import { BackLink, DemoLine, FieldPage, ShopHeader } from './shared'
import { useDemoSettings, useWorkflow } from './fieldData'

function Task({
  to,
  icon: Icon,
  title,
  state,
  done,
  blocked,
}: {
  to: string
  icon: LucideIcon
  title: string
  state: string
  done: boolean
  blocked?: string
}) {
  const body = (
    <>
      <span
        className={cn('flex size-10 shrink-0 items-center justify-center rounded-full', done ? 'bg-strong-chip text-lens-dark' : 'bg-neutral-chip text-ink-2')}
        aria-hidden="true"
      >
        <Icon size={20} strokeWidth={1.8} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[16px] font-semibold text-ink">{title}</span>
        <span className="text-[13px] text-muted-2">{blocked ?? state}</span>
      </span>
      {!blocked && <ChevronRight size={18} className="shrink-0 text-muted-2" aria-hidden="true" />}
    </>
  )
  return (
    <li className="border-t border-line first:border-t-0">
      {blocked ? (
        <div className="flex min-h-16 items-center gap-3 px-1 py-3 opacity-70" aria-disabled="true">
          {body}
        </div>
      ) : (
        <Link to={to} className="flex min-h-16 items-center gap-3 px-1 py-3 no-underline hover:bg-row-hover">
          {body}
        </Link>
      )}
    </li>
  )
}

export function ShopTasks() {
  const t = useT()
  const { mode } = useSession()
  const lang = useLang()
  const { merchantId = '' } = useParams()
  const created = Boolean((useLocation().state as { created?: boolean } | null)?.created)
  const settings = useDemoSettings()
  const workflow = useWorkflow(merchantId)
  const base = `/app/field/shops/${encodeURIComponent(merchantId)}`

  if (workflow.error) {
    return (
      <FieldPage>
        <BackLink to="/app/field">{t('Field work', 'মাঠের কাজ')}</BackLink>
        <ErrorCallout error={workflow.error} />
      </FieldPage>
    )
  }
  if (!workflow.data) {
    return (
      <FieldPage>
        <LoadingState title={t('Loading the shop…', 'দোকান আসছে…')} />
      </FieldPage>
    )
  }

  const status = workflow.data
  const consented = status.consent === 'valid'
  const records = status.records
  const totalRecords = records.purchases + records.deliveries + records.repayments
  const needConsent = consented ? undefined : t('Record the merchant’s consent first.', 'আগে মার্চেন্টের অনুমতি নিন।')
  const application = status.application

  return (
    <FieldPage>
      <BackLink to="/app/field">{t('Field work', 'মাঠের কাজ')}</BackLink>
      <ShopHeader status={status} />
      <DemoLine settings={settings.data} />
      {created && (
        <Notice tone="success" title={t('Shop added', 'দোকান যোগ হয়েছে')}>
          {t(`Its permanent CredLens id is ${status.merchant.merchant_id}. Write it on any paper you keep for this shop.`, `এর স্থায়ী CredLens আইডি ${status.merchant.merchant_id}। এই দোকানের যেকোনো কাগজে এটি লিখে রাখুন।`)}
        </Notice>
      )}

      <p className="m-0 rounded-panel border border-mint-line bg-strong-panel px-4 py-3 text-[15px] font-semibold text-lens-dark">
        {pick(NEXT_STEP_WORDS[status.next_step], lang)}
      </p>

      <ul className="m-0 list-none rounded-card border border-card-line bg-white px-3 py-1 sm:px-4">
        <Task
          to="/app/registrations"
          icon={ShieldCheck}
          title={t('Consent', 'অনুমতি')}
          done={consented}
          state={
            consented
              ? mode === 'account'
                ? t(`Recorded: ${status.consent_categories.map((c) => wordsFor(CATEGORY_WORDS, c, lang)).join(', ')}`, `নেওয়া হয়েছে: ${status.consent_categories.map((c) => wordsFor(CATEGORY_WORDS, c, lang)).join(', ')}`)
                : t(`Recorded (simulated): ${status.consent_categories.map((c) => wordsFor(CATEGORY_WORDS, c, lang)).join(', ')}`, `নেওয়া হয়েছে (সিমুলেটেড): ${status.consent_categories.map((c) => wordsFor(CATEGORY_WORDS, c, lang)).join(', ')}`)
              : status.consent === 'refused'
                ? t('The merchant did not agree. Nothing can be recorded.', 'মার্চেন্ট রাজি হননি। কিছু রাখা যাবে না।')
                : t('Not recorded yet', 'এখনও নেওয়া হয়নি')
          }
        />
        <Task
          to={`${base}/records`}
          icon={ReceiptText}
          title={t('Business records', 'ব্যবসার রেকর্ড')}
          done={totalRecords > 0}
          blocked={needConsent}
          state={t(
            `${count(records.purchases)} ${records.purchases === 1 ? 'purchase' : 'purchases'} · ${count(records.deliveries)} ${records.deliveries === 1 ? 'delivery' : 'deliveries'} · ${count(records.repayments)} ${records.repayments === 1 ? 'repayment' : 'repayments'}`,
            `${count(records.purchases)}টি কেনা · ${count(records.deliveries)}টি ডেলিভারি · ${count(records.repayments)}টি পরিশোধ`,
          )}
        />
        <Task
          to={`${base}/visit`}
          icon={MapPin}
          title={t('Shop visit', 'দোকান পরিদর্শন')}
          done={records.visits > 0}
          blocked={needConsent}
          state={records.visits ? t(`${count(records.visits)} ${records.visits === 1 ? 'visit' : 'visits'} recorded`, `${count(records.visits)}টি পরিদর্শন রাখা হয়েছে`) : t('No visit recorded yet', 'এখনও কোনো পরিদর্শন নেই')}
        />
        <Task
          to={`${base}/application`}
          icon={FileSignature}
          title={t('Application', 'আবেদন')}
          done={Boolean(application)}
          blocked={needConsent}
          state={
            application
              ? t(`${taka(application.requested_amount_bdt)} requested · not a loan`, `${taka(application.requested_amount_bdt)} চাওয়া হয়েছে · ঋণ নয়`)
              : t('Not created yet', 'এখনও তৈরি হয়নি')
          }
        />
      </ul>

      {status.consent !== 'none' && (
        <Link
          to={`${base}/receipt`}
          className="flex min-h-11 items-center gap-3 rounded-card border border-card-line bg-white px-4 py-3 font-semibold text-ink no-underline hover:bg-row-hover"
        >
          <ScrollText size={20} className="shrink-0 text-lens-dark" aria-hidden="true" />
          <span className="flex flex-1 flex-col">
            {t('Data receipt for the merchant', 'মার্চেন্টের জন্য তথ্যের রসিদ')}
            <span className="text-[13px] font-normal text-body">{t('What was recorded, how and when. Show it or print it.', 'কী রাখা হয়েছে, কীভাবে ও কখন। দেখান বা প্রিন্ট করুন।')}</span>
          </span>
          <ChevronRight size={18} className="shrink-0 text-muted-2" aria-hidden="true" />
        </Link>
      )}

      {application && (
        <section className="flex flex-col gap-3 rounded-card border border-card-line bg-white p-4 sm:p-5" aria-labelledby="app-status">
          <h2 id="app-status" className="m-0 flex items-center gap-2 text-lg font-semibold">
            <ClipboardCheck size={20} aria-hidden="true" />
            {t('What happens next', 'এরপর কী হবে')}
          </h2>
          <div className="flex flex-wrap gap-2">
            <StatusTag status={LOAN_KIND.application} />
            <StatusTag status={ASSESSMENT_STATUS[application.assessment_status]} />
          </div>
          <p className="m-0 text-[15px] text-body">
            {t(
              'A credit officer reviews the evidence and the model’s assessment, and records a decision. CredLens never approves or issues credit by itself.',
              'একজন ঋণ কর্মকর্তা প্রমাণ ও মডেলের মূল্যায়ন দেখে সিদ্ধান্ত লিখবেন। CredLens নিজে কখনো ঋণ অনুমোদন বা প্রদান করে না।',
            )}
          </p>
          <Link to={`/app/merchants/${encodeURIComponent(merchantId)}`} className="inline-flex min-h-11 items-center gap-1 self-start font-semibold">
            {t('Open the officer’s view of this shop', 'এই দোকানের কর্মকর্তার দৃশ্য খুলুন')}
            <ChevronRight size={17} aria-hidden="true" />
          </Link>
        </section>
      )}
    </FieldPage>
  )
}
