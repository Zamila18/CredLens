/**
 * Mock consent page (ConsentMobile.dc.html): what a merchant would see on a phone.
 * A static demo: nothing is sent to the API and no consent is recorded. Labelled
 * "Demo screen · not live" on the screen itself.
 *
 * The Bangla is copied from the design and needs a native-speaker review before the demo.
 */
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { Health } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Page, PageHeader } from '@/components/Page'

type Step = 'ask' | 'done' | 'withdrawn' | 'notNow'

function En({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`font-sans text-xs leading-4 text-muted ${className}`}>{children}</span>
}

function LockedRow({ bn, en }: { bn: string; en: string }) {
  return (
    <label className="flex items-start gap-3 rounded-panel border border-card-line bg-card px-3.5 py-3">
      <input type="checkbox" checked disabled readOnly className="mt-0.5 size-5 flex-none accent-lens" />
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold">{bn}</span>
        <En>{en}</En>
      </span>
    </label>
  )
}

const bigButton = 'min-h-12 w-full cursor-pointer rounded-panel font-bn text-base'

export function ConsentDemoPage() {
  const health = useApi<Health>('/health')
  const [step, setStep] = useState<Step>('ask')
  const [questionnaire, setQuestionnaire] = useState(true)
  // First sentence of the API banner ("Synthetic demo data."), as on the design.
  const source = health.data?.banner.split('. ')[0]

  return (
    <Page>
      <PageHeader
        title="Mock consent page"
        description="What a merchant would see on their phone before any data is used. A demo screen only: nothing here is sent to the API and no consent is recorded."
        aside={
          <Link to="/consent" className="text-sm font-semibold">
            Back to consent records
          </Link>
        }
      />

      <div className="flex justify-center">
        <div
          lang="bn"
          className="box-border flex min-h-[760px] w-full max-w-[390px] flex-col overflow-hidden rounded-[28px] border-[6px] border-night bg-ground font-bn text-ink shadow-[0_8px_30px_rgba(15,29,25,.18)]"
        >
          <div className="flex items-center justify-between bg-banner px-5 py-3.5 font-sans text-xs text-banner-text" lang="en">
            <span className="font-semibold">Demo screen · not live</span>
            {source && <span>{source}.</span>}
          </div>

          {step === 'ask' && (
            <div className="flex flex-1 flex-col gap-4 px-5 pt-[22px] pb-5">
              <div className="flex flex-col gap-1.5">
                <h2 className="m-0 text-[23px] leading-8 font-bold">আপনার তথ্য ব্যবহারের অনুমতি</h2>
                <En>Permission to use your data</En>
                <p className="m-0 mt-1 text-[15px] leading-6 text-ink-2">ঋণের প্রস্তুতি যাচাই করতে আমরা নিচের তথ্য দেখব।</p>
              </div>
              <div className="flex flex-col gap-2">
                <LockedRow bn="মাল কেনার হিসাব" en="Stock purchases · Mokam" />
                <LockedRow bn="ডেলিভারির হিসাব" en="Deliveries and returns · REDX" />
                <LockedRow bn="পেমেন্টের হিসাব" en="Repayments · Baki" />
                <label className="flex cursor-pointer items-start gap-3 rounded-panel border border-card-line bg-card px-3.5 py-3">
                  <input
                    type="checkbox"
                    checked={questionnaire}
                    onChange={() => setQuestionnaire((q) => !q)}
                    className="mt-0.5 size-5 flex-none accent-lens"
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-[15px] font-semibold">আর্থিক অভ্যাসের ১০টি প্রশ্ন (ঐচ্ছিক)</span>
                    <En>10 financial-habit questions · optional, never part of the score</En>
                  </span>
                </label>
              </div>
              <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3.5 gap-y-2 rounded-panel border border-card-line bg-card p-3.5 text-sm leading-5">
                <dt className="text-muted">কেন</dt>
                <dd className="m-0">শুধু ঋণের প্রস্তুতি যাচাই</dd>
                <dt className="text-muted">কতদিন</dt>
                <dd className="m-0">২ বছর</dd>
                <dt className="text-muted">বাতিল</dt>
                <dd className="m-0">যেকোনো সময় অনুমতি তুলে নিতে পারবেন</dd>
              </dl>
              <p className="m-0 text-sm leading-[22px] font-medium text-lens-dark">সিদ্ধান্ত নেবেন একজন কর্মকর্তা, কম্পিউটার নয়।</p>
              <div className="mt-auto flex flex-col gap-2">
                <button type="button" onClick={() => setStep('done')} className={`${bigButton} min-h-[52px] border-0 bg-lens text-[17px] font-semibold text-white hover:bg-lens-dark`}>
                  অনুমতি দিন
                </button>
                <button type="button" onClick={() => setStep('notNow')} className={`${bigButton} border border-button-line bg-card font-medium text-ink-2`}>
                  এখন না
                </button>
              </div>
            </div>
          )}

          {step === 'done' && (
            <div className="flex flex-1 flex-col items-start gap-4 px-5 pt-10 pb-5">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true">
                <circle cx="24" cy="24" r="22" stroke="#0E5A4A" strokeWidth="2.5" />
                <path d="M14 25l7 7 13-15" stroke="#0E5A4A" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <h2 className="m-0 text-[23px] leading-8 font-bold">অনুমতি দেওয়া হয়েছে</h2>
              <En>Consent recorded with the date. A credit officer will now review your shop.</En>
              <p className="m-0 text-[15px] leading-6">
                {questionnaire ? 'কেনা, ডেলিভারি, পেমেন্ট এবং প্রশ্নের উত্তর।' : 'কেনা, ডেলিভারি এবং পেমেন্ট। প্রশ্নের উত্তর নয়।'}
              </p>
              <div className="mt-auto flex w-full flex-col gap-2">
                <button type="button" onClick={() => setStep('withdrawn')} className={`${bigButton} border-[1.5px] border-rust bg-card font-semibold text-rust`}>
                  অনুমতি তুলে নিন
                </button>
                <En className="text-center">Withdraw consent: your data stops being used for scoring</En>
              </div>
            </div>
          )}

          {(step === 'withdrawn' || step === 'notNow') && (
            <div className="flex flex-1 flex-col gap-4 px-5 pt-10 pb-5">
              {step === 'withdrawn' ? (
                <>
                  <h2 className="m-0 text-[23px] leading-8 font-bold">অনুমতি তুলে নেওয়া হয়েছে</h2>
                  <En>Consent withdrawn. Your data is no longer used for scoring.</En>
                </>
              ) : (
                <>
                  <h2 className="m-0 text-[23px] leading-8 font-bold">ঠিক আছে, অনুমতি দেওয়া হয়নি</h2>
                  <p className="m-0 text-[15px] leading-6">অনুমতি ছাড়া আপনার দোকানের কোনো স্কোর তৈরি হবে না। পরে চাইলে আবার দেখতে পারেন।</p>
                  <En>Not now: no consent is recorded, so no score is made.</En>
                </>
              )}
              <button type="button" onClick={() => setStep('ask')} className={`${bigButton} mt-auto border border-button-line bg-card font-medium text-ink-2`}>
                আবার দেখুন
              </button>
            </div>
          )}
        </div>
      </div>

      <p className="m-0 text-center text-[13px] text-muted">
        The Bangla on this screen needs a native-speaker review before the demo.
      </p>
    </Page>
  )
}
