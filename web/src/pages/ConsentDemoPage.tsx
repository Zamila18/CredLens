/**
 * Mock consent page (approved designs: 08-consent-page-1..5 and 08-consent-phone-ask.png;
 * copy: CONSENT_PHONE_COPY.md). What a merchant would see on a phone before any data is used.
 *
 * Five states, all local to this page: Ask → Questions (read only) → back; Ask → Given →
 * Withdrawn → Ask; Ask → Not now → Ask. Nothing is sent to the API and no consent is
 * recorded or revoked: the "recorded" wording is the script of the demo.
 * Bangla first with the English under it, whatever the dashboard's language. Digits stay
 * English, as everywhere in the app. On a desktop the phone sits in a drawn frame; on a
 * phone the screen itself is used (no phone inside a phone).
 */
import { ArrowLeft, ArrowRight, Check, CircleCheck, Clock, Lock, ShieldCheck, ShieldMinus, Target, Users } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import { Page } from '@/components/Page'
import { GROUP_TEXT, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { ITEMS } from './merchant/questionnaireItems'

type Step = 'ask' | 'questions' | 'given' | 'notNow' | 'withdrawn'

const STEPS: { id: Step; n: number; en: string; bn: string }[] = [
  { id: 'ask', n: 1, en: 'Ask', bn: 'অনুরোধ' },
  { id: 'questions', n: 2, en: 'Questions opened', bn: 'প্রশ্ন খোলা' },
  { id: 'given', n: 3, en: 'Consent given', bn: 'অনুমতি দেওয়া' },
  { id: 'notNow', n: 4, en: 'Not now', bn: 'এখন না' },
  { id: 'withdrawn', n: 5, en: 'Withdrawn', bn: 'তুলে নেওয়া' },
]

/** Bangla first, the English under it. */
function Two({ bn, en, size = 'md', strong = false }: { bn: ReactNode; en: ReactNode; size?: 'lg' | 'md' | 'sm'; strong?: boolean }) {
  return (
    <span className="flex flex-col">
      <span lang="bn" className={cn('font-bn text-ink', size === 'lg' ? 'text-[24px] leading-9 font-bold' : size === 'md' ? 'text-[17px] leading-7' : 'text-[15px] leading-6', strong && 'font-semibold')}>
        {bn}
      </span>
      <span lang="en" className={cn('text-body', size === 'lg' ? 'text-lg' : size === 'md' ? 'text-[15px]' : 'text-sm')}>
        {en}
      </span>
    </span>
  )
}

function Scope({ bn, en, locked, checked, onToggle, children }: { bn: string; en: string; locked?: boolean; checked: boolean; onToggle?: () => void; children?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-[12px] border border-line bg-white px-3.5 py-3">
      {locked ? (
        // Required and always on: a green tick the merchant cannot clear (the browser would grey out a disabled box).
        <span role="img" aria-label={`${bn} · ${en} (required, always on)`} className="mt-1 flex size-6 flex-none items-center justify-center rounded-[5px] bg-band-strong text-white">
          <Check size={16} strokeWidth={3} aria-hidden="true" />
        </span>
      ) : (
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={`${bn} · ${en}`}
          className="mt-1 size-6 flex-none cursor-pointer accent-[#16845B]"
        />
      )}
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <Two bn={bn} en={en} size="sm" strong />
        {children}
      </span>
      {locked && <Lock size={18} className="mt-1 shrink-0 text-ink-2" aria-label="required" />}
    </div>
  )
}

function Fact({ icon, bn, en }: { icon: ReactNode; bn: ReactNode; en: string }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-1 shrink-0 text-lens-dark" aria-hidden="true">
        {icon}
      </span>
      <Two bn={bn} en={en} size="sm" />
    </li>
  )
}

const primary = 'flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center rounded-[12px] border-0 bg-lens-dark px-3 text-white hover:bg-lens-hover'
const secondary = 'flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center rounded-[12px] border border-ink-2 bg-white px-3 text-ink hover:bg-night-2'

function ButtonText({ bn, en }: { bn: string; en: string }) {
  return (
    <>
      <span lang="bn" className="font-bn text-[17px] font-semibold">
        {bn}
      </span>
      <span lang="en" className="text-sm">
        {en}
      </span>
    </>
  )
}

export function ConsentDemoPage() {
  const t = useT()
  const [step, setStep] = useState<Step>('ask')
  const [questionnaire, setQuestionnaire] = useState(true) // optional scope, ticked by default
  const heading = useRef<HTMLHeadingElement>(null)
  const first = useRef(true)

  // On every change of screen, move focus to its title, so a screen reader reads the new state.
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    heading.current?.focus()
  }, [step])

  const current = STEPS.find((s) => s.id === step)!

  return (
    <Page>
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <h1 className="m-0 text-[28px] leading-9 font-bold tracking-[-0.02em] sm:text-[32px] sm:leading-10">{t('Mock consent page', 'অনুমতির নমুনা পাতা')}</h1>
          <Link to="/consent" className="inline-flex items-center gap-1.5 text-[15px] font-medium no-underline">
            <ArrowLeft size={16} aria-hidden="true" /> {t('Back to Consent', 'অনুমতিতে ফিরে যান')}
          </Link>
        </div>
        <p className="m-0 text-base font-semibold text-ink">
          {t(`Consent page ${current.n} — ${current.en}`, `অনুমতির পাতা ${current.n} — ${current.bn}`)}
        </p>
        <p className="m-0 max-w-[820px] text-base text-body">
          {t(
            'What a merchant would see on their phone before any data is used. A demo screen only: nothing here is sent to the API and no consent is recorded.',
            'কোনো ডেটা ব্যবহারের আগে মার্চেন্ট তাঁর ফোনে যা দেখবেন। শুধু ডেমো: এখান থেকে API-তে কিছু যায় না, আর কোনো অনুমতি রাখা হয় না।',
          )}
        </p>
      </header>

      <div className="flex items-center justify-center gap-3" aria-hidden="true">
        <span className="flex size-10 items-center justify-center rounded-full bg-mint font-display text-lg font-bold text-lens-dark">{current.n}</span>
        <span className="font-display text-xl font-semibold text-ink">{t(current.en, current.bn)}</span>
      </div>

      {/* The phone: a drawn frame from 640px up; the plain screen on a real phone. */}
      <div className="flex justify-center">
        <div className="w-full max-w-[420px] sm:rounded-[48px] sm:border-[10px] sm:border-ink sm:bg-ink sm:p-0 sm:shadow-[0_16px_40px_rgba(17,27,66,.25)]">
          <div className="flex min-h-[720px] flex-col overflow-hidden bg-white sm:rounded-[38px]">
            <div className="hidden items-center justify-between px-7 pt-3 pb-1 text-sm font-semibold text-ink sm:flex" aria-hidden="true">
              <span>9:41</span>
              <span className="h-6 w-28 rounded-full bg-ink" />
              <span className="flex gap-1">
                <span className="h-2.5 w-4 rounded-sm bg-ink" />
              </span>
            </div>

            <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 sm:px-5" role="region" aria-label={t('Merchant phone screen (demo)', 'মার্চেন্টের ফোনের পর্দা (ডেমো)')}>
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="text-body">Demo screen · not live</span>
                <span className="rounded-full bg-mint px-3 py-1 font-medium text-lens-dark">Synthetic demo data</span>
              </div>
              <span className="font-display text-[26px] font-bold text-ink">
                Cred<span className="text-lens">Lens</span>
              </span>

              {step === 'ask' && (
                <>
                  <h2 ref={heading} tabIndex={-1} className="m-0 text-center outline-none">
                    <Two bn="আপনার তথ্য ব্যবহারের অনুমতি" en="Permission to use your data" size="lg" />
                  </h2>
                  <Two bn="ঋণের প্রস্তুতি যাচাই করতে আমরা নিচের তথ্য দেখব।" en="To check readiness for credit, we will look at the information below." size="sm" />
                  <div className="flex flex-col gap-2">
                    <Scope bn="মাল কেনার হিসাব" en="Stock purchases · Mokam" locked checked />
                    <Scope bn="ডেলিভারির হিসাব" en="Deliveries and returns · REDX" locked checked />
                    <Scope bn="পেমেন্টের হিসাব" en="Repayments · Baki" locked checked />
                    <Scope
                      bn="আর্থিক অভ্যাসের 10টি প্রশ্ন (ঐচ্ছিক)"
                      en="10 financial-habit questions · optional, never part of the score"
                      checked={questionnaire}
                      onToggle={() => setQuestionnaire((q) => !q)}
                    >
                      <button
                        type="button"
                        onClick={() => setStep('questions')}
                        className="inline-flex min-h-10 cursor-pointer items-center gap-2 self-start border-0 bg-transparent p-0 font-sans text-[15px] font-semibold text-info"
                      >
                        <span lang="bn" className="font-bn">প্রশ্নগুলো দেখুন</span> See the 10 questions <ArrowRight size={16} aria-hidden="true" />
                      </button>
                    </Scope>
                  </div>
                  <ul className="m-0 flex list-none flex-col gap-3 p-0">
                    <Fact icon={<Target size={22} />} bn={<><b>কেন:</b> শুধু ঋণের প্রস্তুতি যাচাই</>} en="Only to check readiness for credit" />
                    <Fact icon={<Clock size={22} />} bn={<><b>কতদিন:</b> 2 বছর</>} en="How long: 2 years" />
                    <Fact icon={<ShieldCheck size={22} />} bn={<><b>বাতিল:</b> যেকোনো সময় অনুমতি তুলে নিতে পারবেন</>} en="You can withdraw at any time" />
                  </ul>
                  <div className="flex items-start gap-3 rounded-[12px] bg-mint-2 p-3.5">
                    <Users size={24} className="mt-1 shrink-0 text-lens-dark" aria-hidden="true" />
                    <Two bn={<b>সিদ্ধান্ত নেবেন একজন কর্মকর্তা, কম্পিউটার নয়।</b>} en="A credit officer decides, not a computer." size="sm" />
                  </div>
                  <div className="mt-auto flex gap-3">
                    <button type="button" className={primary} onClick={() => setStep('given')}>
                      <ButtonText bn="অনুমতি দিন" en="Give permission" />
                    </button>
                    <button type="button" className={secondary} onClick={() => setStep('notNow')}>
                      <ButtonText bn="এখন না" en="Not now" />
                    </button>
                  </div>
                </>
              )}

              {step === 'questions' && (
                <>
                  <h2 ref={heading} tabIndex={-1} className="m-0 outline-none">
                    <Two bn="আর্থিক অভ্যাসের 10টি প্রশ্ন" en="The 10 financial-habit questions" size="lg" />
                  </h2>
                  <Two
                    bn="উত্তর পরে একজন কর্মকর্তা আপনার সাথে কথা বলে নেবেন। এগুলো স্কোরের অংশ নয়।"
                    en="An officer will ask you these later. They are not part of the score."
                    size="sm"
                  />
                  <ol className="m-0 flex max-h-[460px] list-none flex-col gap-3 overflow-y-auto rounded-[12px] border border-line p-3" tabIndex={0} aria-label="10 questions">
                    {ITEMS.map((item, i) => (
                      <li key={item.key} className="flex flex-col gap-0.5 border-b border-line pb-3 last:border-b-0 last:pb-0">
                        <span className="text-xs font-semibold text-lens-dark">
                          {i + 1} · <span lang="bn" className="font-bn">{GROUP_TEXT[item.group].bn}</span> — {GROUP_TEXT[item.group].en}
                        </span>
                        <Two bn={item.bn} en={item.en} size="sm" />
                      </li>
                    ))}
                  </ol>
                  <Two bn="প্রতিটি উত্তর 1 থেকে 5-এর মধ্যে।" en="Each answer is from 1 to 5." size="sm" />
                  <button type="button" className={cn(secondary, 'mt-auto flex-none')} onClick={() => setStep('ask')}>
                    <ButtonText bn="ফিরে যান" en="Go back" />
                  </button>
                </>
              )}

              {step === 'given' && (
                <>
                  <CircleCheck size={72} strokeWidth={1.5} className="mx-auto mt-6 text-band-strong" aria-hidden="true" />
                  <h2 ref={heading} tabIndex={-1} className="m-0 text-center outline-none">
                    <Two bn="অনুমতি দেওয়া হয়েছে" en="Permission given" size="lg" />
                  </h2>
                  <Two
                    bn="তারিখসহ অনুমতি রাখা হয়েছে। এখন একজন কর্মকর্তা আপনার দোকান পর্যালোচনা করবেন।"
                    en="Consent recorded with the date. A credit officer will now review your shop."
                    size="sm"
                  />
                  <div className="rounded-[12px] bg-mint-2 p-3.5">
                    {questionnaire ? (
                      <Two bn="কেনা, ডেলিভারি, পেমেন্ট এবং প্রশ্নের উত্তর।" en="Purchases, deliveries, payments and the questionnaire answers." size="sm" />
                    ) : (
                      <Two bn="কেনা, ডেলিভারি এবং পেমেন্টের হিসাব।" en="Purchases, deliveries and payments." size="sm" />
                    )}
                  </div>
                  <div className="mt-auto flex flex-col gap-2">
                    <button type="button" className={cn(secondary, 'flex-none')} onClick={() => setStep('withdrawn')}>
                      <ButtonText bn="অনুমতি তুলে নিন" en="Withdraw consent" />
                    </button>
                    <span className="text-center text-[13px] text-body">Withdraw consent: your data stops being used for scoring</span>
                  </div>
                </>
              )}

              {(step === 'notNow' || step === 'withdrawn') && (
                <>
                  <ShieldMinus size={64} strokeWidth={1.5} className="mx-auto mt-6 text-ink-2" aria-hidden="true" />
                  <h2 ref={heading} tabIndex={-1} className="m-0 text-center outline-none">
                    {step === 'notNow' ? (
                      <Two bn="ঠিক আছে, অনুমতি দেওয়া হয়নি" en="All right, no permission given" size="lg" />
                    ) : (
                      <Two bn="অনুমতি তুলে নেওয়া হয়েছে" en="Consent withdrawn" size="lg" />
                    )}
                  </h2>
                  {step === 'notNow' ? (
                    <Two
                      bn="অনুমতি ছাড়া আপনার দোকানের কোনো স্কোর তৈরি হবে না। পরে চাইলে আবার দেখতে পারেন।"
                      en="Without permission, no score is made for your shop. You can look again later."
                      size="sm"
                    />
                  ) : (
                    <Two bn="আপনার তথ্য আর স্কোরের জন্য ব্যবহার হবে না।" en="Your data is no longer used for scoring." size="sm" />
                  )}
                  <button type="button" className={cn(secondary, 'mt-auto flex-none')} onClick={() => setStep('ask')}>
                    <ButtonText bn="আবার দেখুন" en="Look again" />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <p role="note" className="m-0 self-center rounded-[10px] border border-amber-chip bg-amber-panel px-4 py-2.5 text-center text-sm text-amber-deep">
        {t('The Bangla on this screen needs a native-speaker review before the demo.', 'ডেমোর আগে এই পর্দার বাংলা একজন বাংলাভাষী পর্যালোচককে দেখাতে হবে।')}
      </p>
    </Page>
  )
}
