/**
 * Trust and governance: each area says what is in place in this build and what a real
 * pilot or production deployment still needs. Nothing is claimed that the code does not do.
 */
import { CheckCircle2, CircleDashed } from 'lucide-react'

import { Reveal } from '@/components/Motion'
import { useT, type Pair } from '@/lib/i18n'
import { PublicLayout } from './PublicLayout'

const AREAS: { en: string; bn: string; now: Pair[]; next: Pair[] }[] = [
  {
    en: 'Provenance',
    bn: 'উৎস-চিহ্ন',
    now: [
      { en: 'Entry method, actor, real entry time and business date on every record', bn: 'প্রতিটি রেকর্ডে এন্ট্রির ধরন, কে, আসল সময় ও ব্যবসার তারিখ' },
      { en: 'Import batches with the file’s fingerprint and exact row counts', bn: 'ফাইলের ছাপ ও সঠিক সারি-সংখ্যাসহ আমদানির ব্যাচ' },
    ],
    next: [{ en: 'A link from each record to the original row in its source system', bn: 'প্রতিটি রেকর্ড থেকে উৎস-সিস্টেমের মূল সারির সংযোগ' }],
  },
  {
    en: 'Consent',
    bn: 'অনুমতি',
    now: [
      { en: 'Recorded per category, with the wording version, method and time', bn: 'ধরন অনুযায়ী, লেখার সংস্করণ, পদ্ধতি ও সময়সহ রাখা' },
      { en: 'Records refused for categories the merchant did not agree to', bn: 'মার্চেন্ট যে ধরনে রাজি নন, সেই রেকর্ড বাতিল' },
    ],
    next: [{ en: 'Consent wording and process reviewed by qualified counsel for each market; in the sandbox it is simulated', bn: 'প্রতিটি বাজারে যোগ্য আইনজ্ঞের পর্যালোচিত অনুমতির লেখা ও প্রক্রিয়া; স্যান্ডবক্সে এটি সিমুলেটেড' }],
  },
  {
    en: 'Data quality',
    bn: 'তথ্যের মান',
    now: [
      { en: 'Dates, amounts and the business calendar checked before saving', bn: 'রাখার আগে তারিখ, অঙ্ক ও ব্যবসার ক্যালেন্ডার যাচাই' },
      { en: 'Duplicate warnings for shops and repeated import rows; nothing merged automatically', bn: 'দোকান ও পুনরাবৃত্ত আমদানি-সারিতে দ্বৈত সতর্কতা; নিজে থেকে কিছু একীকরণ নয়' },
    ],
    next: [{ en: 'A review queue for conflicting values and unmatched records', bn: 'সাংঘর্ষিক মান ও না-মেলা রেকর্ডের পর্যালোচনা-তালিকা' }],
  },
  {
    en: 'Access control',
    bn: 'প্রবেশ নিয়ন্ত্রণ',
    now: [
      { en: 'Real accounts: Argon2id password hashing, sessions that expire, sign-in and registration rate limits', bn: 'আসল অ্যাকাউন্ট: Argon2id পাসওয়ার্ড হ্যাশ, মেয়াদী সেশন, সাইন-ইন ও নিবন্ধনে গতিসীমা' },
      { en: 'Every API call checks the caller’s role and company; Credit Officers, Field Sales Representatives and auditors can do different things', bn: 'প্রতিটি API কল ভূমিকা ও প্রতিষ্ঠান যাচাই করে; ক্রেডিট অফিসার, ফিল্ড সেলস রিপ্রেজেন্টেটিভ ও অডিটর আলাদা কাজ করতে পারেন' },
    ],
    next: [
      { en: 'Separation between organisations, tested', bn: 'প্রতিষ্ঠানগুলোর মধ্যে পরীক্ষিত আলাদা থাকা' },
    ],
  },
  {
    en: 'Audit',
    bn: 'অডিট',
    now: [{ en: 'Every read of a merchant’s data and every write is logged; decisions and the log cannot be edited or deleted', bn: 'মার্চেন্টের তথ্যের প্রতিটি দেখা ও লেখা লগ হয়; সিদ্ধান্ত ও লগ বদলানো বা মোছা যায় না' }],
    next: [{ en: 'Log export and retention rules per organisation', bn: 'প্রতিষ্ঠান অনুযায়ী লগ রপ্তানি ও সংরক্ষণের নিয়ম' }],
  },
  {
    en: 'Assessment limits',
    bn: 'মূল্যায়নের সীমা',
    now: [
      { en: 'Exact, tested reasons; missing data never lowers a score; a stale score is never shown as current', bn: 'সঠিক, পরীক্ষিত কারণ; তথ্য না থাকলে স্কোর কমে না; পুরনো স্কোর কখনো বর্তমান হিসেবে দেখানো হয় না' },
      { en: 'The model is validated on synthetic data only, and the product says so', bn: 'মডেলটি শুধু সিনথেটিক ডেটায় যাচাই করা, আর প্রোডাক্ট তা বলে' },
    ],
    next: [{ en: 'Validation on each market’s own data and an approval step before a model is used', bn: 'প্রতিটি বাজারের নিজস্ব ডেটায় যাচাই, আর মডেল ব্যবহারের আগে অনুমোদন' }],
  },
  {
    en: 'Human decisions',
    bn: 'মানুষের সিদ্ধান্ত',
    now: [{ en: 'No code path approves or declines; an override needs a written reason', bn: 'কোনো কোড অনুমোদন বা প্রত্যাখ্যান করে না; পরিবর্তনে লিখিত কারণ লাগে' }],
    next: [{ en: 'Approval limits and second review per institution policy', bn: 'প্রতিষ্ঠানের নীতি অনুযায়ী অনুমোদনের সীমা ও দ্বিতীয় পর্যালোচনা' }],
  },
  {
    en: 'Deployment boundaries',
    bn: 'ইনস্টলেশনের সীমা',
    now: [{ en: 'This installation is a sandbox: it accepts synthetic records only', bn: 'এই ইনস্টলেশন একটি স্যান্ডবক্স: শুধু সিনথেটিক রেকর্ড নেয়' }],
    next: [{ en: 'A pilot or production needs verified security, backups, monitoring and an independent review first', bn: 'পাইলট বা প্রোডাকশনের আগে যাচাইকৃত নিরাপত্তা, ব্যাকআপ, পর্যবেক্ষণ ও স্বাধীন পর্যালোচনা দরকার' }],
  },
]

export function TrustPage() {
  const t = useT()
  return (
    <PublicLayout>
      <section className="mx-auto flex max-w-[1200px] flex-col gap-4 px-4 pt-14 pb-10 sm:px-6">
        <span className="text-[13px] font-semibold tracking-[0.08em] text-lens-dark uppercase">{t('Trust and governance', 'আস্থা ও শাসন')}</span>
        <h1 className="route-enter m-0 max-w-[820px] font-display text-[38px] leading-[44px] font-bold tracking-[-0.025em] text-ink sm:text-[50px] sm:leading-[56px]">
          {t('What is in place, and what is still required.', 'কী আছে, আর কী এখনও দরকার।')}
        </h1>
        <p className="m-0 max-w-[700px] text-[18px] leading-[30px] text-ink-3">
          {t('For each area: the controls this build has today, and what a real deployment must add first.', 'প্রতিটি ক্ষেত্রে: এই সংস্করণে আজ যা আছে, আর আসল ইনস্টলেশনের আগে যা যোগ করতে হবে।')}
        </p>
      </section>
      <section className="mx-auto max-w-[1200px] px-4 pb-20 sm:px-6">
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {AREAS.map((a, i) => (
            <Reveal as="li" key={a.en} delay={(i % 4) * 50} className="grid gap-4 rounded-[16px] border border-line bg-white p-5 sm:p-6 lg:grid-cols-[220px_1fr_1fr]">
              <h2 className="m-0 text-[19px] font-semibold text-ink">{t(a.en, a.bn)}</h2>
              <div className="flex flex-col gap-2">
                <span className="text-[12px] font-semibold tracking-[0.06em] text-lens-dark uppercase">{t('In place', 'আছে')}</span>
                {a.now.map((n) => (
                  <span key={n.en} className="flex gap-2 text-[15px] leading-6 text-ink-2">
                    <CheckCircle2 size={17} aria-hidden="true" className="mt-0.5 shrink-0 text-band-strong" />
                    {t(n.en, n.bn)}
                  </span>
                ))}
              </div>
              <div className="flex flex-col gap-2">
                <span className="text-[12px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('Required for a real deployment', 'আসল ইনস্টলেশনের জন্য দরকার')}</span>
                {a.next.map((n) => (
                  <span key={n.en} className="flex gap-2 text-[15px] leading-6 text-ink-3">
                    <CircleDashed size={17} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-2" />
                    {t(n.en, n.bn)}
                  </span>
                ))}
              </div>
            </Reveal>
          ))}
        </ul>
      </section>
    </PublicLayout>
  )
}
