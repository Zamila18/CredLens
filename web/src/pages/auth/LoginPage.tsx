/**
 * Sign in to CredLens. The first screen asks who is signing in, with three large cards:
 * a company (its Credit Officers and auditors), the Records Desk (the people who process
 * receipts) or a merchant (a shop owner). Each card opens its own short form. Companies and the
 * Records Desk use an email or mobile number and a password (POST /auth/login); a merchant uses
 * the Merchant ID from their slip and the owner's name (POST /auth/merchant-login). The server
 * decides the role and the company; the browser keeps only an HttpOnly session cookie.
 * New company: /register. Forgot the password: the owner's one-time code at /setup-password.
 */
import { ArrowLeft, Building2, ChevronRight, ClipboardCheck, LogIn, Store } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'

import { ApiError } from '@/api/client'
import { HOME } from '@/app/navigation'
import { useSession } from '@/app/session-context'
import { Field, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { AuthFrame } from './AuthFrame'

type Who = 'company' | 'desk' | 'merchant'

function WhoCard({ icon, title, text, onClick }: { icon: ReactNode; title: string; text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full cursor-pointer items-center gap-4 rounded-card border border-card-line bg-white p-5 text-left font-sans transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-lens hover:shadow-[0_14px_30px_-18px_rgba(0,97,76,0.45)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lens active:translate-y-0 active:scale-[0.99] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
    >
      <span className="flex size-14 shrink-0 items-center justify-center rounded-[14px] bg-strong-chip text-lens-dark transition-colors duration-200 group-hover:bg-lens group-hover:text-white">
        {icon}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-[18px] font-semibold text-ink">{title}</span>
        <span className="text-[14.5px] leading-[21px] text-body">{text}</span>
      </span>
      <ChevronRight size={22} aria-hidden="true" className="shrink-0 text-muted-2 transition-transform duration-200 group-hover:translate-x-1 group-hover:text-lens motion-reduce:transition-none" />
    </button>
  )
}

export function LoginPage() {
  const t = useT()
  const [params] = useSearchParams()
  const { mode, role, signIn, signInMerchant } = useSession()
  const [who, setWho] = useState<Who | null>(null)
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [portalId, setPortalId] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const next = params.get('next')
  const justRegistered = params.get('registered') === '1'

  // Signed in (also right after submitting): go where the person was heading, or home.
  if (mode === 'account') return <Navigate to={next && next.startsWith('/app') ? next : HOME[role]} replace />

  const submit = async () => {
    setPending(true)
    setError(null)
    try {
      if (who === 'merchant') await signInMerchant(portalId.trim(), ownerName.trim())
      else await signIn(identifier.trim(), password)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'The API could not be reached.'))
    } finally {
      setPending(false)
    }
  }

  const message = !error
    ? null
    : error.code === 'login_failed'
      ? who === 'merchant'
        ? t('The Merchant ID or the name is not right. Check your slip.', 'মার্চেন্ট আইডি বা নাম ঠিক নয়। আপনার স্লিপটি দেখে নিন।')
        : t('The email/number or password is not right.', 'ইমেইল/নম্বর বা পাসওয়ার্ড ঠিক নয়।')
      : error.code === 'portal_not_open'
        ? t('Your portal opens once your consent form has been checked. Ask your lender.', 'আপনার সম্মতিপত্র যাচাই হলে পোর্টাল খুলবে। আপনার ঋণদাতাকে জিজ্ঞেস করুন।')
        : error.code === 'account_locked'
          ? t('Too many wrong attempts. Wait 15 minutes and try again, or ask your administrator.', 'অনেকবার ভুল হয়েছে। ১৫ মিনিট পর আবার চেষ্টা করুন, বা অ্যাডমিনকে বলুন।')
          : error.code === 'no_active_membership'
            ? t('This account has no active access. Ask your administrator.', 'এই অ্যাকাউন্টের সক্রিয় প্রবেশাধিকার নেই। অ্যাডমিনকে বলুন।')
            : error.status === 429
              ? t('Too many attempts. Wait a few minutes and try again.', 'অনেকবার চেষ্টা হয়েছে। কয়েক মিনিট পর আবার চেষ্টা করুন।')
              : error.code === 'validation'
                ? t('Fill in both boxes.', 'দুটি ঘরই পূরণ করুন।')
                : t('Signing in did not work. Check your connection and try again.', 'সাইন ইন হয়নি। সংযোগ দেখে আবার চেষ্টা করুন।')

  if (who === null) {
    return (
      <AuthFrame wide title={t('Welcome to CredLens', 'CredLens-এ স্বাগতম')} lead={t('Who is signing in?', 'কে সাইন ইন করছেন?')}>
        {justRegistered && (
          <Notice tone="success" title={t('Registration complete', 'নিবন্ধন সম্পন্ন')}>
            {t('Your account is ready. Choose Company and sign in.', 'আপনার অ্যাকাউন্ট তৈরি হয়েছে। “প্রতিষ্ঠান” বেছে সাইন ইন করুন।')}
          </Notice>
        )}
        <div className="flex flex-col gap-3">
          <WhoCard icon={<Building2 size={28} aria-hidden="true" />} title={t('I am a company', 'আমি একটি প্রতিষ্ঠান')} text={t('Credit officers and managers of a lender', 'ঋণদাতার ক্রেডিট অফিসার ও ব্যবস্থাপক')} onClick={() => setWho('company')} />
          <WhoCard icon={<ClipboardCheck size={28} aria-hidden="true" />} title={t('I am on the Records Desk', 'আমি রেকর্ড ডেস্কের সদস্য')} text={t('The team that uploads and checks receipts', 'যে দল রসিদ আপলোড ও যাচাই করে')} onClick={() => setWho('desk')} />
          <WhoCard icon={<Store size={28} aria-hidden="true" />} title={t('I am a merchant', 'আমি একজন ব্যবসায়ী')} text={t('Shop owners: see your records and apply for a loan', 'দোকান মালিক: আপনার হিসাব দেখুন ও ঋণের জন্য আবেদন করুন')} onClick={() => setWho('merchant')} />
        </div>
        <p className="m-0 border-t border-line pt-4 text-[14.5px] text-body">
          {t('New lender?', 'নতুন ঋণদাতা?')}{' '}
          <Link to="/register" className="font-semibold no-underline">
            {t('Register your company or join with a code', 'প্রতিষ্ঠান নিবন্ধন করুন বা কোড দিয়ে যোগ দিন')}
          </Link>
        </p>
      </AuthFrame>
    )
  }

  const titles = {
    company: [t('Company sign in', 'প্রতিষ্ঠানের সাইন ইন'), t('Use the email or mobile number you registered with.', 'নিবন্ধনের সময় দেওয়া ইমেইল বা মোবাইল নম্বর ব্যবহার করুন।')],
    desk: [t('Records Desk sign in', 'রেকর্ড ডেস্কের সাইন ইন'), t('Use the email or mobile number your company registered for you.', 'আপনার প্রতিষ্ঠান যে ইমেইল বা মোবাইল নম্বর দিয়েছে তা ব্যবহার করুন।')],
    merchant: [t('Merchant sign in', 'ব্যবসায়ীর সাইন ইন'), t('Use the Merchant ID printed on your slip and the owner’s name.', 'আপনার স্লিপে ছাপা মার্চেন্ট আইডি ও মালিকের নাম লিখুন।')],
  }[who]

  return (
    <AuthFrame title={titles[0]} lead={titles[1]}>
      <button type="button" onClick={() => { setWho(null); setError(null) }} className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 self-start border-0 bg-transparent p-0 font-sans text-[14.5px] font-semibold text-lens-dark transition-transform hover:-translate-x-0.5">
        <ArrowLeft size={17} aria-hidden="true" />
        {t('Not you? Choose again', 'ভুল হলে আবার বাছুন')}
      </button>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        {who === 'merchant' ? (
          <>
            <Field label={t('Merchant ID', 'মার্চেন্ট আইডি')} required>
              <TextInput value={portalId} onChange={(e) => setPortalId(e.target.value)} autoComplete="off" autoCapitalize="characters" autoFocus />
            </Field>
            <Field label={t('Owner’s name', 'মালিকের নাম')} required>
              <TextInput value={ownerName} onChange={(e) => setOwnerName(e.target.value)} autoComplete="name" />
            </Field>
          </>
        ) : (
          <>
            <Field label={t('Email or mobile number', 'ইমেইল বা মোবাইল নম্বর')} required>
              <TextInput value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" inputMode="email" autoFocus />
            </Field>
            <Field label={t('Password', 'পাসওয়ার্ড')} required>
              <TextInput type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </Field>
          </>
        )}
        {message && (
          <p role="alert" className="m-0 rounded-[10px] border border-[#F3D0D0] bg-error-panel px-3 py-2 text-[14px] text-error">
            {message}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending || (who === 'merchant' ? !portalId.trim() || !ownerName.trim() : !identifier.trim() || !password)}>
          <LogIn size={19} aria-hidden="true" />
          {pending ? t('Signing in…', 'সাইন ইন হচ্ছে…') : t('Sign in', 'সাইন ইন')}
        </Button>
      </form>
      {who !== 'merchant' && (
        <p className="m-0 border-t border-line pt-4 text-[14px] text-body">
          {t('Forgot the password? Use the one-time code from your owner at', 'পাসওয়ার্ড ভুলে গেছেন? মালিকের দেওয়া এককালীন কোড দিন:')}{' '}
          <Link to="/setup-password" className="font-semibold no-underline">
            {t('Set a new password', 'নতুন পাসওয়ার্ড দিন')}
          </Link>
        </p>
      )}
    </AuthFrame>
  )
}
