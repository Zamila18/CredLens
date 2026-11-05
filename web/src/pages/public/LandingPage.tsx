/**
 * The public landing page: CredLens as a provider-independent platform for business
 * evidence and responsible credit assessment.
 *
 * Honesty rules for this page: the shop picture is an illustration and says so; the app
 * window shows a real screenshot of this build (synthetic data); no statistics, partners,
 * customers, certifications or accuracy claims. (The data-source status list lives on the
 * /sources page, from catalog.ts.)
 */
import { ArrowRight, Check, Globe2, Languages, ScrollText, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import heroLarge from '@/assets/hero-shop-1400.webp'
import heroSmall from '@/assets/hero-shop-800.webp'
import workflowLarge from '@/assets/loan-workflow-2172.webp'
import workflowSmall from '@/assets/loan-workflow-1400.webp'
import { Reveal } from '@/components/Motion'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { PublicLayout } from './PublicLayout'

function Eyebrow({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return <span className={cn('text-[13px] font-semibold tracking-[0.08em] uppercase', light ? 'text-[#7fd1b9]' : 'text-lens-dark')}>{children}</span>
}

function Heading({ eyebrow, title, lead, light = false }: { eyebrow: string; title: string; lead?: string; light?: boolean }) {
  return (
    <div className="flex max-w-[680px] flex-col gap-3">
      <Eyebrow light={light}>{eyebrow}</Eyebrow>
      <h2 className={cn('m-0 font-display text-[30px] leading-[38px] font-bold tracking-[-0.02em] sm:text-[38px] sm:leading-[46px]', light ? 'text-white' : 'text-ink')}>{title}</h2>
      {lead && <p className={cn('m-0 text-[17px] leading-7', light ? 'text-[#c9d2ea]' : 'text-ink-3')}>{lead}</p>}
    </div>
  )
}

/** Sources flow into one merchant profile, which feeds the assessment and the officer. */
function EvidenceFlow() {
  const t = useT()
  const left = [t('Field entry', 'মাঠের এন্ট্রি'), t('Spreadsheets', 'স্প্রেডশিট'), t('Institution files', 'প্রতিষ্ঠানের ফাইল'), t('Connected systems', 'সংযুক্ত সিস্টেম')]
  const right = [
    { title: t('Assessment', 'মূল্যায়ন'), text: t('Score, coverage, exact reasons', 'স্কোর, কভারেজ, সঠিক কারণ') },
    { title: t('Evidence review', 'প্রমাণ পর্যালোচনা'), text: t('Ready, check needed or more information', 'প্রস্তুত, যাচাই বাকি বা আরও তথ্য') },
    { title: t('Officer decides', 'কর্মকর্তা সিদ্ধান্ত নেন'), text: t('With a written reason, audited', 'লিখিত কারণসহ, অডিটকৃত') },
  ]
  return (
    <div className="grid items-center gap-6 lg:grid-cols-[1fr_auto_1.1fr_auto_1fr]">
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {left.map((l) => (
          <li key={l} className="rounded-[12px] border border-dashed border-[#3a4c86] px-4 py-3 text-[15px] text-[#d7def2]">
            {l}
          </li>
        ))}
      </ul>
      <svg className="hidden h-40 w-16 lg:block" viewBox="0 0 64 160" aria-hidden="true">
        {[20, 60, 100, 140].map((y) => (
          <path key={y} d={`M0 ${y} C 32 ${y}, 32 80, 64 80`} fill="none" stroke="#7fd1b9" strokeWidth="1.5" className="flow-line" />
        ))}
      </svg>
      <div className="flex flex-col gap-3 rounded-[18px] bg-white p-5 text-ink shadow-[0_24px_60px_-30px_rgba(0,0,0,0.6)]">
        <span className="text-[12px] font-semibold tracking-[0.06em] text-lens-dark uppercase">{t('One merchant evidence profile', 'একটি মার্চেন্টের প্রমাণ-প্রোফাইল')}</span>
        {[
          [t('Stock purchase', 'মাল কেনা'), t('Typed in by staff · not verified', 'কর্মী লিখেছেন · যাচাই হয়নি')],
          [t('Stock purchase', 'মাল কেনা'), t('From a spreadsheet · not verified', 'স্প্রেডশিট থেকে · যাচাই হয়নি')],
          [t('Repayment of an earlier loan', 'আগের ঋণের পরিশোধ'), t('From institution records', 'প্রতিষ্ঠানের রেকর্ড থেকে')],
          [t('Field visit', 'মাঠ পরিদর্শন'), t('Typed in by staff · not verified', 'কর্মী লিখেছেন · যাচাই হয়নি')],
        ].map(([what, how], i) => (
          <div key={i} className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5">
            <span className="text-[14px] font-medium">{what}</span>
            <span className="rounded-md bg-neutral-chip px-2 py-0.5 text-[11.5px] font-semibold text-neutral-text">{how}</span>
          </div>
        ))}
        <span className="text-[12px] text-muted-2">{t('Each record keeps its origin, entry time and business date.', 'প্রতিটি রেকর্ডে উৎস, এন্ট্রির সময় ও ব্যবসার তারিখ থাকে।')}</span>
      </div>
      <svg className="hidden h-40 w-16 lg:block" viewBox="0 0 64 160" aria-hidden="true">
        {[30, 80, 130].map((y) => (
          <path key={y} d={`M0 80 C 32 80, 32 ${y}, 64 ${y}`} fill="none" stroke="#7fd1b9" strokeWidth="1.5" className="flow-line" />
        ))}
      </svg>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {right.map((r) => (
          <li key={r.title} className="flex flex-col rounded-[12px] border border-[#2c3d78] bg-deep-2 px-4 py-3">
            <span className="text-[15px] font-semibold text-white">{r.title}</span>
            <span className="text-[13px] text-[#b9c3e0]">{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function LandingPage() {
  const t = useT()
  return (
    <PublicLayout>
      {/* Hero: copy on the left; the shop illustration on the right. */}
      <section className="overflow-hidden bg-paper">
        <div className="mx-auto grid max-w-[1200px] items-center gap-12 px-4 pt-12 pb-16 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:pt-20 lg:pb-24">
          <div className="route-enter flex flex-col gap-6">
            <Eyebrow>{t('Business evidence intelligence', 'ব্যবসায়িক প্রমাণ-বুদ্ধিমত্তা')}</Eyebrow>
            <h1 className="m-0 font-display text-[40px] leading-[46px] font-bold tracking-[-0.03em] text-ink sm:text-[56px] sm:leading-[60px]">
              {t('Understand small businesses beyond the credit file.', 'ক্রেডিট ফাইলের বাইরেও ছোট ব্যবসাকে বুঝুন।')}
            </h1>
            <p className="m-0 max-w-[540px] text-[18px] leading-[30px] text-ink-3">
              {t(
                'CredLens turns fragmented business records into structured, traceable evidence, so financial institutions can assess small businesses responsibly, with a person making every decision.',
                'CredLens ছড়ানো ব্যবসায়িক রেকর্ডকে গোছানো, উৎস-চেনা প্রমাণে রূপ দেয়, যাতে আর্থিক প্রতিষ্ঠান ছোট ব্যবসাকে দায়িত্বের সাথে মূল্যায়ন করতে পারে, আর প্রতিটি সিদ্ধান্ত নেন একজন মানুষ।',
              )}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/login" className="lift inline-flex min-h-12 items-center gap-2 rounded-[12px] bg-lens-dark px-6 text-base font-semibold text-white no-underline hover:bg-lens-hover hover:text-white">
                {t('Sign in', 'সাইন ইন')}
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link to="/register" className="lift inline-flex min-h-12 items-center rounded-[12px] border border-control-line bg-white px-6 text-base font-semibold text-ink no-underline hover:border-lens hover:text-lens-dark">
                {t('Register your company', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন')}
              </Link>
            </div>
            <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0 text-[14px] text-ink-2">
              {[t('Works without any partner integration', 'কোনো পার্টনার-সংযোগ ছাড়াই কাজ করে'), t('Every record keeps its origin', 'প্রতিটি রেকর্ডে উৎস থাকে'), t('A person decides', 'সিদ্ধান্ত নেন মানুষ')].map((x) => (
                <li key={x} className="flex items-center gap-1.5">
                  <Check size={16} aria-hidden="true" className="text-lens" />
                  {x}
                </li>
              ))}
            </ul>
          </div>
          <figure className="relative m-0">
            <div className="overflow-hidden rounded-[22px] border border-line">
              <img src={heroLarge} srcSet={`${heroSmall} 800w, ${heroLarge} 1400w`} sizes="(min-width: 1024px) 600px, 100vw" alt="" className="block aspect-[4/3] w-full object-cover" />
            </div>
            <figcaption className="absolute top-3 left-3 rounded-full bg-white/90 px-3 py-1 text-[12px] font-medium text-ink-2 backdrop-blur-sm">
              {t('Illustration of a shop', 'দোকানের চিত্র')}
            </figcaption>
          </figure>
        </div>
      </section>

      {/* Problem and solution */}
      <section className="bg-deep text-white">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-12 px-4 py-20 sm:px-6">
          <Reveal>
            <Heading
              light
              eyebrow={t('The problem, and the answer', 'সমস্যা, আর সমাধান')}
              title={t('A small business’s track record exists. It is just scattered.', 'ছোট ব্যবসার লেনদেনের ইতিহাস আছে। শুধু ছড়ানো।')}
              lead={t(
                'Purchases sit in memo books and supplier sheets, deliveries with couriers, repayments in another system. CredLens brings them into one profile without losing where each record came from.',
                'কেনাকাটা মেমো-খাতা ও সরবরাহকারীর শিটে, ডেলিভারি কুরিয়ারের কাছে, পরিশোধ আরেক সিস্টেমে। CredLens এগুলোকে এক প্রোফাইলে আনে, প্রতিটি রেকর্ডের উৎস না হারিয়ে।',
              )}
            />
          </Reveal>
          <Reveal>
            <EvidenceFlow />
          </Reveal>
        </div>
      </section>

      {/* End-to-end workflow: full width, touching the block above (the picture's own cream is the background) */}
      <section className="m-0 bg-[#fdfbfa] px-5 py-0 sm:px-10 lg:px-16">
        <figure className="m-0 p-0">
          <div className="overflow-x-auto">
            <img
              src={workflowLarge}
              srcSet={`${workflowSmall} 1400w, ${workflowLarge} 2172w`}
              sizes="100vw"
              width={2172}
              height={724}
              alt={t(
                'End-to-end business loan workflow in seven steps: the merchant starts an application, submits it to the organisation, an assessment is prepared, a credit officer reviews it, the officer takes the final decision, the loan is disbursed, and the merchant repays over the agreed period.',
                'ব্যবসায়িক ঋণের সাত ধাপ: মার্চেন্ট আবেদন শুরু করেন, প্রতিষ্ঠানে জমা দেন, মূল্যায়ন তৈরি হয়, ক্রেডিট অফিসার যাচাই করেন, অফিসার চূড়ান্ত সিদ্ধান্ত নেন, ঋণ বিতরণ হয়, এবং মার্চেন্ট নির্ধারিত সময়ে পরিশোধ করেন।',
              )}
              className="m-0 block h-auto w-full min-w-[900px] p-0"
            />
          </div>
          <figcaption className="pb-3 text-[12px] text-muted-2">
            {t('Illustration of the workflow. The figures shown are examples.', 'কাজের ধাপের চিত্র। দেখানো সংখ্যাগুলো উদাহরণ।')}
          </figcaption>
        </figure>
      </section>

      {/* Trust */}
      <section className="mx-auto grid max-w-[1200px] gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Reveal>
          <Heading
            eyebrow={t('Trust and governance', 'আস্থা ও শাসন')}
            title={t('Evidence, assessment and decision stay separate.', 'প্রমাণ, মূল্যায়ন ও সিদ্ধান্ত আলাদা থাকে।')}
            lead={t('So anyone can see what is known, what is estimated and who decided.', 'যাতে যে কেউ দেখতে পারেন কী জানা, কী অনুমান আর কে সিদ্ধান্ত নিলেন।')}
          />
          <Link to="/trust" className="mt-5 inline-flex items-center gap-1.5 font-semibold no-underline">
            {t('How CredLens handles trust', 'CredLens কীভাবে আস্থা রক্ষা করে')}
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </Reveal>
        <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
          {[
            [ScrollText, t('Origin on every record', 'প্রতিটি রেকর্ডে উৎস'), t('How it entered, who entered it, when, and what is known about it.', 'কীভাবে এলো, কে রাখলেন, কখন, আর কী জানা আছে।')],
            [ShieldCheck, t('Consent before collection', 'সংগ্রহের আগে অনুমতি'), t('Records are accepted only for the categories a merchant agreed to.', 'মার্চেন্ট যে ধরনে রাজি, শুধু সেই রেকর্ডই নেওয়া হয়।')],
            [Check, t('Missing is not negative', 'না থাকা মানে খারাপ নয়'), t('Missing data lowers coverage, never the score.', 'তথ্য না থাকলে কভারেজ কমে, স্কোর নয়।')],
            [ArrowRight, t('A request is not a loan', 'অনুরোধ মানে ঋণ নয়'), t('Applications stay apart from issued loans everywhere.', 'আবেদন সব জায়গায় দেওয়া ঋণ থেকে আলাদা।')],
          ].map(([Icon, title, text], i) => {
            const I = Icon as typeof Check
            return (
              <Reveal as="li" key={title as string} delay={i * 60} className="flex flex-col gap-2 rounded-[16px] border border-line bg-white p-5">
                <I size={20} aria-hidden="true" className="text-lens-dark" />
                <span className="text-[16px] font-semibold text-ink">{title as string}</span>
                <span className="text-[14.5px] leading-6 text-ink-3">{text as string}</span>
              </Reveal>
            )
          })}
        </ul>
      </section>

      {/* International */}
      <section className="border-y border-line bg-white">
        <div className="mx-auto grid max-w-[1200px] items-center gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2">
          <Reveal>
            <Heading
              eyebrow={t('Built for more than one market', 'একাধিক বাজারের জন্য')}
              title={t('Configured per market, validated per market.', 'প্রতিটি বাজারের নিজস্ব কনফিগারেশন ও যাচাই।')}
              lead={t(
                'Languages, currency, business calendar, consent wording, data sources and the assessment are set for each market. A model is only used where it has been validated with that market’s data.',
                'ভাষা, মুদ্রা, ব্যবসার ক্যালেন্ডার, অনুমতির লেখা, ডেটার উৎস ও মূল্যায়ন প্রতিটি বাজারের জন্য ঠিক করা হয়। কোনো মডেল কেবল সেখানেই ব্যবহার হয়, যেখানে সেই বাজারের ডেটায় তা যাচাই হয়েছে।',
              )}
            />
          </Reveal>
          <Reveal className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-2 rounded-[16px] border border-mint-line bg-mint-2 p-5">
              <Languages size={20} aria-hidden="true" className="text-lens-dark" />
              <span className="text-[15px] font-semibold text-ink">{t('Configured today', 'আজ কনফিগার করা')}</span>
              <span className="text-[14px] leading-6 text-ink-2">{t('Bangladesh: English and Bangla, taka, Dhaka time, the district list and consent wording v1.', 'বাংলাদেশ: ইংরেজি ও বাংলা, টাকা, ঢাকার সময়, জেলার তালিকা ও অনুমতির লেখা v1।')}</span>
            </div>
            <div className="flex flex-col gap-2 rounded-[16px] border border-line bg-paper p-5">
              <Globe2 size={20} aria-hidden="true" className="text-ink-2" />
              <span className="text-[15px] font-semibold text-ink">{t('Adding a market', 'নতুন বাজার যোগ')}</span>
              <span className="text-[14px] leading-6 text-ink-3">{t('Its own language pack, currency, calendar, consent template and data sources, and an assessment validated on its own data.', 'নিজস্ব ভাষা, মুদ্রা, ক্যালেন্ডার, অনুমতির টেমপ্লেট ও ডেটার উৎস, আর নিজের ডেটায় যাচাই করা মূল্যায়ন।')}</span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Call to action */}
      <section className="px-4 py-20 sm:px-6">
        <Reveal className="mx-auto flex max-w-[1200px] flex-col items-start gap-5 rounded-[22px] bg-deep px-6 py-12 text-white sm:px-12 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-2">
            <h2 className="m-0 font-display text-[28px] leading-9 font-bold tracking-[-0.02em] text-white">{t('Bring your field team and your merchants onto one platform.', 'আপনার মাঠকর্মী ও মার্চেন্টদের এক প্ল্যাটফর্মে আনুন।')}</h2>
            <p className="m-0 text-[16px] text-[#c9d2ea]">{t('From registering a shop to an audited decision, with a person deciding at every step.', 'দোকান নিবন্ধন থেকে অডিটকৃত সিদ্ধান্ত পর্যন্ত, প্রতিটি ধাপে একজন মানুষ সিদ্ধান্ত নেন।')}</p>
          </div>
          <Link to="/register" className="lift inline-flex min-h-12 items-center gap-2 rounded-[12px] bg-[#1fb58f] px-6 text-base font-semibold text-deep no-underline hover:bg-[#2cc79f] hover:text-deep">
            {t('Register your company', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন')}
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </Reveal>
      </section>
    </PublicLayout>
  )
}
